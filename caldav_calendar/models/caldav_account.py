# -*- coding: utf-8 -*-
import logging
import traceback

from odoo import api, fields, models
from odoo.exceptions import UserError

from .caldav_service import (
    CalDAVAuthError,
    CalDAVClient,
    CalDAVError,
    CalDAVPreconditionFailedError,
)

_logger = logging.getLogger(__name__)


class CalDAVAccount(models.Model):
    """One CalDAV calendar subscription. A user can have several - each is
    an independent sync unit with its own credentials, sync token and
    cursor, so one account's incremental sync state never gets tangled up
    with another's.
    """
    _name = 'caldav.account'
    _description = 'CalDAV Calendar Account'
    _rec_name = 'name'

    user_id = fields.Many2one(
        'res.users', required=True, index=True, ondelete='cascade',
        default=lambda self: self.env.user.id)
    name = fields.Char(
        required=True, default='Calendar',
        help='A label to tell your calendars apart, e.g. "Personal" or "Work".')
    active = fields.Boolean(default=True, help='Uncheck to pause syncing this account without deleting it.')
    read_only = fields.Boolean(
        string='Read-Only Subscription', default=False,
        help='Tick this for calendars you can only view, not change: subscribed '
             'holiday feeds, team calendars you lack write access to, ICS '
             'subscriptions. Odoo still pulls remote changes for these, but '
             'never pushes local edits back - so a local change to one of these '
             'events stays local, and nothing queues up waiting for a write the '
             'server would only reject.')

    discovery_url = fields.Char(
        string='CalDAV Server URL',
        help='Base URL of your CalDAV server, e.g. https://cloud.example.com/ '
             'Used only by "Discover Calendars" to look up which calendars are available.')
    url = fields.Char(
        string='Calendar URL',
        help='Full URL of the specific CalDAV calendar collection to sync with, e.g. '
             'https://cloud.example.com/remote.php/dav/calendars/john/personal/')
    username = fields.Char(string='CalDAV Username')
    password = fields.Char(string='CalDAV Password', help='An app-specific password is strongly recommended.')

    sync_status = fields.Selection([
        ('not_configured', 'Not Configured'),
        ('active', 'Active'),
        ('paused', 'Paused'),
        ('error', 'Error'),
    ], string='CalDAV Sync Status', default='not_configured', copy=False)
    sync_token = fields.Char(copy=False, help='RFC 6578 sync-collection token.')
    sync_ctag = fields.Char(copy=False, help='Fallback change tag when sync-collection is unsupported.')
    last_sync = fields.Datetime(string='Last CalDAV Sync', copy=False)
    last_sync_error = fields.Text(string='Last CalDAV Sync Error', copy=False)

    # ------------------------------------------------------------------
    # Client / actions
    # ------------------------------------------------------------------
    def _caldav_get_client(self, url=None):
        self.ensure_one()
        target_url = url or self.url
        if not target_url:
            raise UserError(self.env._('Please fill in the CalDAV URL first.'))
        if not self.read_only and not (self.username and self.password):
            raise UserError(self.env._(
                'Please fill in the CalDAV username and password, or tick '
                '"Read-Only Subscription" if this calendar needs no login.'))
        return CalDAVClient(target_url, self.username, self.password, timeout=self._caldav_request_timeout())

    @api.model
    def _caldav_request_timeout(self):
        """Per-request read timeout (seconds), overridable via the
        ``caldav_calendar.request_timeout`` system parameter for servers that
        need longer than the default. Falls back to the client's own default
        when unset or unparseable.
        """
        raw = self.env['ir.config_parameter'].sudo().get_param('caldav_calendar.request_timeout')
        try:
            value = int(raw)
        except (TypeError, ValueError):
            return None
        return value if value > 0 else None

    def action_caldav_test_connection(self):
        self.ensure_one()
        try:
            client = self._caldav_get_client()
            name = client.test_connection()
        except CalDAVAuthError as exc:
            raise UserError(self.env._('Authentication failed: %s', exc))
        except CalDAVError as exc:
            raise UserError(self.env._('Could not reach the calendar: %s', exc))
        if self.sync_status == 'not_configured':
            self.sync_status = 'active'
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': self.env._('Connection successful'),
                'message': self.env._('Connected to calendar "%s".', name),
                'type': 'success',
            },
        }

    def action_caldav_discover_calendars(self):
        self.ensure_one()
        base_url = self.discovery_url or self.url
        if not base_url:
            raise UserError(self.env._('Please fill in the server URL first.'))
        if not self.read_only and not (self.username and self.password):
            raise UserError(self.env._('Please fill in the username and password first.'))
        try:
            client = self._caldav_get_client(url=base_url)
            calendars = client.discover_calendars()
        except CalDAVAuthError as exc:
            raise UserError(self.env._('Authentication failed: %s', exc))
        except CalDAVError as exc:
            raise UserError(self.env._('Calendar discovery failed: %s', exc))
        if not calendars:
            raise UserError(self.env._('No calendars were found on this server for this account.'))
        wizard = self.env['caldav.calendar.select'].create({
            'account_id': self.id,
            'line_ids': [(0, 0, {
                'name': cal['display_name'],
                'url': cal['url'],
            }) for cal in calendars],
        })
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Select CalDAV Calendar'),
            'res_model': 'caldav.calendar.select',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_caldav_sync_now(self):
        self.ensure_one()
        try:
            self._caldav_sync()
        except CalDAVError as exc:
            raise UserError(self.env._('CalDAV sync failed: %s', exc))
        if self.sync_status == 'error':
            error = self.last_sync_error or self.env._('unknown error')
            raise UserError(self.env._('CalDAV sync failed: %s', error))
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {'title': self.env._('CalDAV sync complete'), 'type': 'success'},
        }

    @api.model
    def _cron_caldav_sync_all(self):
        accounts = self.sudo().search([('sync_status', '=', 'active'), ('url', '!=', False)])
        for account in accounts:
            try:
                account._caldav_sync()
            except CalDAVError as exc:
                # An expected CalDAV/network failure: server unreachable, auth
                # rejected, sync token stale, timeout past its retries. Store
                # the one-line reason, not a stack trace nobody needs to read.
                _logger.warning(
                    'CalDAV: sync failed for account %s (user %s): %s',
                    account.name, account.user_id.login, exc,
                )
                account.write({'sync_status': 'error', 'last_sync_error': str(exc)})
            except Exception:
                _logger.exception('CalDAV: sync failed for account %s (user %s)', account.name, account.user_id.login)
                account.write({
                    'sync_status': 'error',
                    'last_sync_error': traceback.format_exc(),
                })

    # ------------------------------------------------------------------
    # Sync orchestration
    # ------------------------------------------------------------------
    def _caldav_sync(self):
        self.ensure_one()
        account = self.sudo()
        client = account._caldav_get_client()
        try:
            if not account.read_only:
                account._caldav_push(client)
            account._caldav_pull(client)
        except CalDAVError as exc:
            account.write({'sync_status': 'error', 'last_sync_error': str(exc)})
            raise
        account.write({
            'last_sync': fields.Datetime.now(),
            'sync_status': 'active',
            'last_sync_error': False,
        })

    def _caldav_push(self, client):
        self.ensure_one()
        Event = self.env['calendar.event'].sudo()
        PendingDelete = self.env['caldav.pending.delete'].sudo()

        for pending in PendingDelete.search([('account_id', '=', self.id)]):
            try:
                client.delete_event(pending.href, pending.etag)
            except CalDAVPreconditionFailedError:
                _logger.info('CalDAV: remote changed before delete could propagate for %s', pending.href)
            except CalDAVError:
                _logger.exception('CalDAV: failed to delete remote event %s', pending.href)
                continue
            pending.unlink()

        dirty = Event.search([('need_caldav_sync', '=', True), ('caldav_account_id', '=', self.id)])
        dirty = dirty.filtered(lambda e: e._caldav_is_recurrence_master())
        for event in dirty:
            ics = event._caldav_build_ics()
            try:
                if event.caldav_href:
                    url, etag = client.put_event(event.caldav_href, ics, etag=event.caldav_etag, create=False)
                else:
                    url, etag = client.put_event(event.caldav_uid, ics, create=True)
            except CalDAVPreconditionFailedError:
                _logger.info('CalDAV: push conflict on event %s, will reconcile from remote on pull', event.id)
                continue
            except CalDAVError:
                _logger.exception('CalDAV: failed to push event %s', event.id)
                continue
            event.with_context(caldav_no_sync=True).write({
                'caldav_href': url,
                'caldav_etag': etag,
                'caldav_account_id': self.id,
                'need_caldav_sync': False,
            })

    def _caldav_pull(self, client):
        self.ensure_one()
        Event = self.env['calendar.event'].sudo()

        try:
            # sync_collection(None) is a valid RFC 6578 bootstrap request (an
            # empty <d:sync-token/>): it returns the full listing *and* a
            # fresh token in one round-trip, so there's no reason to skip
            # straight to the calendar-query fallback just because we don't
            # have a stored token yet. Only fall back when the server
            # actually rejects sync-collection outright (unsupported, or -
            # on a later call - the stored token itself was rejected).
            changes, new_token = client.sync_collection(self.sync_token or None)
        except CalDAVError:
            changes, new_token = self._caldav_full_resync(client)

        deleted_hrefs = [c['href'] for c in changes if c['deleted']]
        changed_hrefs = [c['href'] for c in changes if not c['deleted']]

        if deleted_hrefs:
            stale = Event.search([('caldav_href', 'in', deleted_hrefs), ('caldav_account_id', '=', self.id)])
            self._caldav_unlink_events(stale)

        if changed_hrefs:
            for item in client.multiget(changed_hrefs):
                try:
                    self._caldav_apply_remote_event(item)
                except Exception:
                    _logger.exception('CalDAV: failed to apply remote event %s', item.get('href'))

        self.write({'sync_token': new_token or self.sync_token})

    def _caldav_full_resync(self, client):
        self.ensure_one()
        listing = client.list_all_events()
        changes = [{'href': e['href'], 'etag': e['etag'], 'deleted': False} for e in listing]

        remote_hrefs = {e['href'] for e in listing}
        local = self.env['calendar.event'].sudo().search([
            ('caldav_account_id', '=', self.id), ('caldav_href', '!=', False),
        ])
        for stale_event in local.filtered(lambda e: e.caldav_href not in remote_hrefs):
            changes.append({'href': stale_event.caldav_href, 'etag': False, 'deleted': True})

        try:
            self.sync_ctag = client.get_ctag()
        except CalDAVError:
            pass
        return changes, False

    def _caldav_apply_remote_event(self, item):
        self.ensure_one()
        Event = self.env['calendar.event'].sudo()
        parsed = Event._caldav_parse_ics(item['ics'])
        if not parsed:
            return
        master_info = parsed['master']

        existing = Event.search([
            ('caldav_href', '=', item['href']), ('caldav_account_id', '=', self.id),
        ], limit=1)
        if not existing and master_info['vals'].get('caldav_uid'):
            existing = Event.search([
                ('caldav_uid', '=', master_info['vals']['caldav_uid']), ('caldav_account_id', '=', self.id),
            ], limit=1)

        vals = dict(master_info['vals'])
        vals.update({
            'caldav_href': item['href'],
            'caldav_etag': item['etag'],
            'caldav_account_id': self.id,
            'need_caldav_sync': False,
        })

        if existing:
            if existing.need_caldav_sync:
                _logger.warning(
                    'CalDAV: event %s (account %s) was edited locally since the '
                    'last sync; the incoming remote version overwrites it '
                    '(remote wins) and the local edit is lost.',
                    existing.id, self.display_name,
                )
            existing.with_context(caldav_no_sync=True).write(vals)
            target = existing
        else:
            vals['user_id'] = self.user_id.id
            target = Event.with_context(caldav_no_sync=True).create(vals)

        target._caldav_apply_attendees(master_info['attendee_emails'])
        if master_info['rrule']:
            self._caldav_apply_rrule(target, master_info['rrule'])
            self._caldav_apply_overrides_and_exdates(target, parsed['overrides'], parsed['exdates'])

    def _caldav_apply_rrule(self, event, rrule_text):
        """Apply an incoming RRULE to `event` and actually expand it into the
        series of `calendar.event` instances Odoo displays.

        Writing `rrule` on a `calendar.recurrence` only updates its structured
        fields (rrule_type/interval/count/...) via its inverse compute - it
        does NOT create/reconcile the occurrence rows by itself. That requires
        an explicit call to `_apply_recurrence()` (existing recurrence) or
        `_apply_recurrence_values()` (brand new recurrence), which is what
        creates/detaches `calendar.event` rows to match the rule.

        Guarded to only run when the rule text actually changed: Odoo's own
        reconciliation (`_apply_recurrence` -> `_reconcile_events`) matches
        occurrences by their CURRENT start/stop against freshly-computed
        pattern ranges - an exception occurrence that's been moved will never
        match, and would get silently detached from the series. Re-running
        that on every pull (even when the rule is unchanged) would eventually
        strip every exception out of every synced series. Only a genuine rule
        change is worth that risk, and it's the same trade-off Odoo's own UI
        makes when you edit a whole series' pattern.
        """
        self.ensure_one()
        if event.recurrence_id and event.recurrence_id.rrule == rrule_text:
            return
        try:
            # A savepoint, not a bare try/except: write({'rrule': ...}) below
            # persists the new rule before _apply_recurrence[_values]() ever
            # runs, so a failure partway through expansion (a rule write()
            # accepts but expansion chokes on, say) would otherwise leave the
            # stored rrule and the actual occurrence rows disagreeing with
            # each other. Rolling back the whole savepoint on any exception
            # here restores exactly the state from before this call, instead
            # of trying to hand-reconstruct it field by field.
            with self.env.cr.savepoint():
                if event.recurrence_id:
                    recurrence = event.recurrence_id.with_context(caldav_no_sync=True)
                    recurrence.write({'rrule': rrule_text})
                    recurrence._apply_recurrence()
                else:
                    event.with_context(caldav_no_sync=True)._apply_recurrence_values({'rrule': rrule_text})
        except Exception:
            _logger.warning(
                'CalDAV: could not apply recurrence rule %r to event %s; rolled '
                'back to the previous state so the stored rule and its '
                'occurrences stay consistent.',
                rrule_text, event.id, exc_info=True,
            )

    def _caldav_apply_overrides_and_exdates(self, master_event, overrides, exdates):
        """Apply RECURRENCE-ID overrides and EXDATEs onto an already-expanded
        series. Must run after `_caldav_apply_rrule` so the occurrence rows
        (and their `caldav_recurrence_id_date` anchors) already exist.
        """
        self.ensure_one()
        recurrence = master_event.recurrence_id
        if not recurrence:
            return  # rrule application failed upstream; nothing to anchor these on
        Event = self.env['calendar.event'].sudo()

        for override in overrides:
            anchor = override['recurrence_id']
            occurrence = recurrence.calendar_event_ids.filtered(
                lambda e, anchor=anchor: e.caldav_recurrence_id_date == anchor)[:1]
            vals = dict(override['vals'])
            vals.update({'follow_recurrence': False, 'caldav_recurrence_id_date': anchor})
            if occurrence:
                occurrence.with_context(caldav_no_sync=True).write(vals)
            else:
                # Slot not materialized locally (e.g. beyond Odoo's expansion
                # horizon) - attach a standalone exception row directly.
                vals.update({
                    'recurrence_id': recurrence.id, 'recurrency': False,
                    'user_id': self.user_id.id, 'caldav_account_id': self.id,
                })
                occurrence = Event.with_context(caldav_no_sync=True).create(vals)
            occurrence._caldav_apply_attendees(override['attendee_emails'])

        if exdates:
            stale = recurrence.calendar_event_ids.filtered(lambda e: e.caldav_recurrence_id_date in exdates)
            stale.with_context(caldav_no_sync=True).unlink()

    def _caldav_unlink_events(self, events):
        """Unlink `events`, cascading to the rest of their recurring series.

        CalDAV represents an entire recurring series as a single resource (one
        href for the master VEVENT + its RRULE); a remote delete of that
        resource means the whole series is gone, not just its base occurrence.
        Plain `unlink()` on the base event alone would leave the other
        instances behind as an orphaned local-only recurrence.
        """
        self.ensure_one()
        recurrences = events.mapped('recurrence_id')
        all_events = events | recurrences.mapped('calendar_event_ids')
        all_events.with_context(caldav_no_sync=True).unlink()
        recurrences.exists().unlink()
