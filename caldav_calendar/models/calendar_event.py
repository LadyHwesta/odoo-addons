# -*- coding: utf-8 -*-
import logging
import re
import uuid
from datetime import datetime, timedelta

import pytz
import vobject

from odoo import api, fields, models
from odoo.tools import html2plaintext, plaintext2html

_logger = logging.getLogger(__name__)

RRULE_RE = re.compile(r'^RRULE:(.+)$', re.MULTILINE)

# Fields whose change on an event means it needs to be (re-)pushed to CalDAV.
CALDAV_SYNC_FIELDS = {
    'name', 'description', 'location', 'start', 'stop', 'allday',
    'start_date', 'stop_date', 'partner_ids', 'active', 'alarm_ids',
    'follow_recurrence',
}


class CalendarEvent(models.Model):
    _inherit = 'calendar.event'

    caldav_uid = fields.Char(copy=False, index='btree', help='iCalendar UID of the linked CalDAV resource.')
    caldav_href = fields.Char(copy=False, help='Full URL of the linked CalDAV resource on the server.')
    caldav_etag = fields.Char(copy=False, help='Last known ETag of the CalDAV resource, used to detect conflicts.')
    caldav_account_id = fields.Many2one(
        'caldav.account', copy=False, index=True,
        help='Which of the organizer\'s CalDAV calendars this event is synced through.')
    need_caldav_sync = fields.Boolean(default=False, copy=False, index=True)
    caldav_recurrence_id_date = fields.Datetime(
        copy=False,
        help="RFC 5545 RECURRENCE-ID: this occurrence's original, per-RRULE slot time. "
             "Stamped once when the occurrence row is first created and never touched again, "
             "so it stays a stable anchor even after the occurrence itself is moved - which is "
             "exactly what lets a later sync find 'the same occurrence' again by identity "
             "instead of by its (possibly now-wrong) current start time. Empty on the series "
             "master and on plain non-recurring events.")

    # ------------------------------------------------------------------
    # CRUD / dirty-tracking
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.context.get('caldav_no_sync'):
            self._caldav_assign_default_account(vals_list)
        events = super().create(vals_list)
        events._caldav_stamp_recurrence_anchor()
        if not self.env.context.get('caldav_no_sync'):
            # Not excluded for read-only accounts: `need_caldav_sync` also
            # doubles as the "this was edited locally since the last pull"
            # signal _caldav_apply_remote_event() uses to log a conflict
            # before an incoming remote version overwrites it. Read-only
            # accounts never push (that's still gated at the account level
            # in _caldav_push), so setting it here is harmless - it just
            # keeps that conflict detection working for them too.
            events.filtered(lambda e: not e.need_caldav_sync).write({'need_caldav_sync': True})
        return events

    def _caldav_assign_default_account(self, vals_list):
        """A brand-new event with no calendar chosen syncs automatically
        only when its organizer has exactly one active, writable CalDAV
        account - the common case, and the one that used to be the only
        case. With two or more accounts there's no way to guess which
        calendar it belongs to, so it's left unsynced until the user picks
        one on the event itself. Read-only subscriptions are skipped
        entirely here: auto-assigning to one would just mark the event
        dirty forever for a push that can never land.
        """
        accounts_by_user = {}
        for vals in vals_list:
            if vals.get('caldav_account_id'):
                continue
            user_id = vals.get('user_id') or self.env.user.id
            if user_id not in accounts_by_user:
                accounts = self.env['caldav.account'].sudo().search([
                    ('user_id', '=', user_id), ('active', '=', True), ('read_only', '=', False),
                ])
                accounts_by_user[user_id] = accounts.id if len(accounts) == 1 else False
            if accounts_by_user[user_id]:
                vals['caldav_account_id'] = accounts_by_user[user_id]

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get('caldav_no_sync') and not vals.get('need_caldav_sync'):
            if CALDAV_SYNC_FIELDS & set(vals.keys()):
                self._caldav_flag_dirty()
        return res

    def unlink(self):
        if not self.env.context.get('caldav_no_sync'):
            to_delete = self.filtered(
                lambda e: e.caldav_href and e.caldav_account_id and not e.caldav_account_id.read_only)
            for event in to_delete:
                self.env['caldav.pending.delete'].sudo().create({
                    'account_id': event.caldav_account_id.id,
                    'href': event.caldav_href,
                    'etag': event.caldav_etag,
                })
            # A lone occurrence of a series being unlinked (not the whole series)
            # needs the master re-pushed so its next .ics picks up a fresh EXDATE
            # for the now-missing slot.
            occurrence_deletes = self.filtered(lambda e: not e._caldav_is_recurrence_master())
            masters = occurrence_deletes.mapped('recurrence_id.base_event_id')
            # Not excluded for read-only accounts here either - see the
            # matching note in create().
            masters = (masters - self).filtered(lambda e: not e.need_caldav_sync)
            if masters:
                masters.with_context(caldav_no_sync=True).write({'need_caldav_sync': True})
        return super().unlink()

    def _caldav_is_recurrence_master(self):
        """True for a standalone event, or the base/master event of a series -
        i.e. the record that owns the single CalDAV resource for that series.
        False for any other occurrence row (those live inside the master's
        .ics as RECURRENCE-ID overrides, they don't have their own resource).
        """
        self.ensure_one()
        return not self.recurrency or not self.recurrence_id or self.recurrence_id.base_event_id.id == self.id

    def _caldav_stamp_recurrence_anchor(self):
        """Give every freshly created recurring-series occurrence a stable
        RECURRENCE-ID anchor: its own start, captured now, before anything
        can move it. Skipped for the master (it defines the pattern, it
        doesn't occupy a slot within it) and for rows that already came in
        with an explicit anchor (e.g. a CalDAV override being created with
        the server's real RECURRENCE-ID, which may differ from `start`).
        """
        for event in self:
            if event.caldav_recurrence_id_date or not event.start:
                continue
            if event.recurrence_id and event.recurrence_id.base_event_id.id != event.id:
                event.with_context(caldav_no_sync=True).caldav_recurrence_id_date = event.start

    def _caldav_flag_dirty(self):
        """Flag the calendar.event that actually needs to be PUT to CalDAV.

        A recurring series is ONE resource on the server, so an edit to any
        of its occurrences must flag the series' master, not the occurrence
        itself (which would then just get silently filtered out of the push
        query - see res_users.py::_caldav_push).

        Also makes sure any occurrence that was just meaningfully edited is
        marked `follow_recurrence=False` (Odoo core only does this itself
        for edits to start/stop; we care about name/description/location/
        attendees too; here it's what marks an occurrence as an override, so
        our own ics builder can find it later).
        """
        targets = self.env['calendar.event']
        exceptions = self.env['calendar.event']
        for event in self:
            if event._caldav_is_recurrence_master():
                targets |= event
            else:
                targets |= event.recurrence_id.base_event_id
                if event.follow_recurrence:
                    exceptions |= event
        if exceptions:
            exceptions.with_context(caldav_no_sync=True).write({'follow_recurrence': False})
        # Not excluded for read-only accounts here either - see the matching
        # note in create().
        targets = targets.filtered(lambda e: not e.need_caldav_sync)
        if targets:
            targets.with_context(caldav_no_sync=True).write({'need_caldav_sync': True})

    # ------------------------------------------------------------------
    # Odoo -> iCalendar
    # ------------------------------------------------------------------
    def _caldav_ensure_uid(self):
        self.ensure_one()
        if not self.caldav_uid:
            self.with_context(caldav_no_sync=True).write({
                'caldav_uid': f'{uuid.uuid4()}@odoo-caldav-calendar',
            })
        return self.caldav_uid

    def _caldav_build_ics(self):
        """Serialize this master event to a full iCalendar resource: its own
        VEVENT (with RRULE + EXDATE if it's a recurring series), plus one
        extra VEVENT per known exception, each carrying a RECURRENCE-ID -
        exactly the multi-VEVENT-per-resource shape RFC 5545 §3.8.5.3 uses
        to represent "this one occurrence is different".
        """
        self.ensure_one()
        uid = self._caldav_ensure_uid()
        cal = vobject.iCalendar()
        cal.add('prodid').value = '-//Odoo//CalDAV Calendar Sync//EN'
        cal.add('version').value = '2.0'
        self._caldav_add_vevent(cal, uid)

        rrule = self._caldav_get_rrule_text()
        if rrule and self.recurrence_id:
            exceptions = self.recurrence_id.calendar_event_ids.filtered(
                lambda e: e.id != self.id and not e.follow_recurrence and e.active)
            for occurrence in exceptions:
                anchor = occurrence.caldav_recurrence_id_date or occurrence.start
                occurrence._caldav_add_vevent(cal, uid, recurrence_id=anchor)

        ics = cal.serialize()
        if rrule:
            # count=1: every VEVENT block shares the same UID line, only the
            # first (the master, always added first above) may carry RRULE.
            ics = ics.replace('UID:' + uid, 'UID:' + uid + '\r\nRRULE:' + rrule, 1)
            exdate_text = self._caldav_build_exdate_text()
            if exdate_text:
                ics = ics.replace('RRULE:' + rrule, 'RRULE:' + rrule + '\r\n' + exdate_text, 1)
        return ics

    def _caldav_add_vevent(self, cal, uid, recurrence_id=None):
        """Add one VEVENT for `self` to `cal`. Shared by the master and by
        each RECURRENCE-ID override, so both stay in sync field-for-field.
        """
        self.ensure_one()
        vevent = cal.add('vevent')
        vevent.add('uid').value = uid
        if recurrence_id:
            rid = vevent.add('recurrence-id')
            if self.allday:
                rid.value = recurrence_id.date()
                rid.value_param = 'DATE'
            else:
                rid.value = pytz.utc.localize(recurrence_id)
        vevent.add('summary').value = self.name or ''
        if self.description:
            vevent.add('description').value = html2plaintext(self.description)
        if self.location:
            vevent.add('location').value = self.location

        if self.allday:
            vevent.add('dtstart').value = self.start_date
            vevent.dtstart.value_param = 'DATE'
            vevent.add('dtend').value = self.stop_date + timedelta(days=1)
            vevent.dtend.value_param = 'DATE'
        else:
            vevent.add('dtstart').value = pytz.utc.localize(self.start)
            vevent.add('dtend').value = pytz.utc.localize(self.stop)
        vevent.add('dtstamp').value = pytz.utc.localize(fields.Datetime.now())

        for attendee in self.attendee_ids:
            if not attendee.email:
                continue
            att = vevent.add('attendee')
            att.value = f'mailto:{attendee.email}'
            att.params['CN'] = [attendee.common_name or attendee.partner_id.name or attendee.email]
            att.params['PARTSTAT'] = [{
                'needsAction': 'NEEDS-ACTION',
                'accepted': 'ACCEPTED',
                'declined': 'DECLINED',
                'tentative': 'TENTATIVE',
            }.get(attendee.state, 'NEEDS-ACTION')]
        return vevent

    def _caldav_get_rrule_text(self):
        self.ensure_one()
        if self.recurrency and self.recurrence_id and self.recurrence_id.base_event_id.id == self.id:
            return self.recurrence_id.rrule or False
        return False

    def _caldav_build_exdate_text(self):
        """EXDATE line for slots the master's RRULE would generate but that
        no local occurrence row exists for any more - i.e. someone deleted
        a single occurrence in Odoo (a plain row unlink; Odoo has no EXDATE
        concept of its own, so there's nothing else marking this).
        """
        self.ensure_one()
        recurrence = self.recurrence_id
        if not recurrence:
            return False
        # Anchor on the master's own start, not recurrence.dtstart: the latter
        # is min(all occurrences' start), which a moved-earlier exception can
        # drag away from the series' true original start.
        expected = set(recurrence._get_occurrences(self.start))
        existing = {e.caldav_recurrence_id_date or e.start for e in recurrence.calendar_event_ids}
        missing = sorted(expected - existing)
        if not missing:
            return False
        if self.allday:
            dates = ','.join(dt.strftime('%Y%m%d') for dt in missing)
            return f'EXDATE;VALUE=DATE:{dates}'
        dates = ','.join(pytz.utc.localize(dt).strftime('%Y%m%dT%H%M%SZ') for dt in missing)
        return f'EXDATE:{dates}'

    # ------------------------------------------------------------------
    # iCalendar -> Odoo
    # ------------------------------------------------------------------
    @api.model
    def _caldav_parse_ics(self, ics_text):
        """Parse a raw .ics document that may contain a recurring master
        VEVENT plus RECURRENCE-ID overrides and EXDATEs (RFC 5545 §3.8.5.3).

        Returns False if there's no usable VEVENT, else:
            {
                'master': {'vals': {...}, 'attendee_emails': [...], 'rrule': str|False},
                'overrides': [{'recurrence_id': datetime, 'vals': {...}, 'attendee_emails': [...]}],
                'exdates': [datetime, ...],
            }
        """
        try:
            cal = vobject.readOne(ics_text)
        except Exception:
            _logger.warning('CalDAV: could not parse ics payload, skipping.', exc_info=True)
            return False
        if hasattr(cal, 'vevent_list'):
            vevents = cal.vevent_list
        elif hasattr(cal, 'vevent'):
            vevents = [cal.vevent]
        else:
            return False

        master_vevent = None
        override_vevents = []
        for vevent in vevents:
            if hasattr(vevent, 'recurrence_id'):
                override_vevents.append(vevent)
            elif master_vevent is None:
                master_vevent = vevent
        if master_vevent is None:
            # Nothing without a RECURRENCE-ID came back (e.g. a targeted
            # multiget on a single override) - nothing to anchor a series
            # on, so just treat the first component as a plain event.
            master_vevent = vevents[0]
            override_vevents = vevents[1:]

        master_vals, master_emails = self._caldav_vevent_to_vals(master_vevent)
        rrule_match = RRULE_RE.search(ics_text)
        rrule = rrule_match.group(1).strip() if rrule_match else False

        exdates = []
        for exdate_prop in getattr(master_vevent, 'exdate_list', []):
            values = exdate_prop.value if isinstance(exdate_prop.value, list) else [exdate_prop.value]
            exdates += [self._caldav_to_utc_naive(dt) for dt in values]

        overrides = []
        for vevent in override_vevents:
            vals, emails = self._caldav_vevent_to_vals(vevent)
            overrides.append({
                'recurrence_id': self._caldav_to_utc_naive(vevent.recurrence_id.value),
                'vals': vals,
                'attendee_emails': emails,
            })

        return {
            'master': {'vals': master_vals, 'attendee_emails': master_emails, 'rrule': rrule},
            'overrides': overrides,
            'exdates': exdates,
        }

    @api.model
    def _caldav_vevent_to_vals(self, vevent):
        """Map one VEVENT component (master or override alike) to Odoo vals."""
        vals = {'caldav_uid': getattr(vevent, 'uid', None) and vevent.uid.value}
        vals['name'] = getattr(vevent, 'summary', None) and vevent.summary.value or ''
        if hasattr(vevent, 'description'):
            vals['description'] = plaintext2html(vevent.description.value)
        if hasattr(vevent, 'location'):
            vals['location'] = vevent.location.value

        dtstart = vevent.dtstart.value
        dtend = vevent.dtend.value if hasattr(vevent, 'dtend') else None
        allday = not hasattr(dtstart, 'hour')
        if allday:
            vals['allday'] = True
            vals['start_date'] = dtstart
            vals['stop_date'] = (dtend - timedelta(days=1)) if dtend else dtstart
        else:
            vals['allday'] = False
            vals['start'] = self._caldav_to_utc_naive(dtstart)
            vals['stop'] = self._caldav_to_utc_naive(dtend) if dtend else vals['start']

        attendee_emails = []
        for att in getattr(vevent, 'attendee_list', []):
            value = att.value or ''
            if value.lower().startswith('mailto:'):
                attendee_emails.append(value[7:].strip())
        return vals, attendee_emails

    @staticmethod
    def _caldav_to_utc_naive(dt):
        if not hasattr(dt, 'hour'):
            # Bare date (VALUE=DATE) - used by all-day EXDATE/RECURRENCE-ID.
            dt = datetime.combine(dt, datetime.min.time())
        if dt.tzinfo is not None:
            return dt.astimezone(pytz.utc).replace(tzinfo=None)
        return dt  # floating time, best-effort: treat as UTC

    def _caldav_apply_attendees(self, emails):
        self.ensure_one()
        if not emails:
            return
        Partner = self.env['res.partner']
        partners = self.env['res.partner']
        for email in emails:
            partner = Partner.search([('email', '=ilike', email)], limit=1)
            if not partner:
                partner = Partner.create({'name': email, 'email': email})
            partners |= partner
        self.with_context(caldav_no_sync=True).write({'partner_ids': [(6, 0, partners.ids)]})
