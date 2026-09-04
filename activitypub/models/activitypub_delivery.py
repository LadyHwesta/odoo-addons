# -*- coding: utf-8 -*-
import logging
from datetime import timedelta

import requests

from odoo import api, fields, models

from .activitypub_object import federation_enabled, ssrf_allow_hosts
from .activitypub_service import ActivityPubError, post_activity

_logger = logging.getLogger(__name__)

# Give up on an inbox after this many attempts. With the backoff below that
# is a bit over two hours of trying - long enough to ride out a restart or a
# short outage, short enough that a decommissioned server stops costing us.
MAX_ATTEMPTS = 8
# Exponential backoff, capped. attempt n waits min(3600, 60 * 2**(n-1)) s.
BACKOFF_CAP_SECONDS = 3600
BATCH_SIZE = 50


class ActivityPubDelivery(models.Model):
    """One pending / completed POST of an activity to one remote inbox.

    Every activity we send is idempotent on the receiving side (it carries a
    stable ``id``), so a retry after a response we never saw is at worst a
    duplicate the receiver discards - it is always safe to try again.
    """
    _name = 'activitypub.delivery'
    _description = 'ActivityPub Delivery'
    _rec_name = 'inbox_url'
    _order = 'id'

    activity_id = fields.Many2one(
        'activitypub.activity', required=True, ondelete='cascade', index=True)
    inbox_url = fields.Char(required=True)
    state = fields.Selection([
        ('pending', 'Pending'),
        ('retry', 'Waiting to retry'),
        ('delivered', 'Delivered'),
        ('failed', 'Failed'),
    ], default='pending', required=True, index=True, copy=False)
    attempts = fields.Integer(default=0, copy=False)
    last_error = fields.Text(copy=False)
    next_attempt = fields.Datetime(copy=False)
    delivered_at = fields.Datetime(copy=False)

    _activity_inbox_uniq = models.Constraint(
        'unique(activity_id, inbox_url)',
        'This activity is already queued for that inbox.',
    )

    # ------------------------------------------------------------------
    @api.model
    def _cron_deliver(self, limit=BATCH_SIZE):
        # The master switch promises nothing is delivered to remote servers
        # while off. Objects/activities still get created locally (they're
        # harmless, and dropping them would lose real content if someone
        # publishes with the switch off by mistake) - this is the one place
        # that actually has to stop: queued deliveries just wait, and
        # resume automatically once federation is re-enabled.
        if not federation_enabled(self.env):
            return 0
        now = fields.Datetime.now()
        due = self.search([
            ('state', 'in', ('pending', 'retry')),
            ('attempts', '<', MAX_ATTEMPTS),
            '|', ('next_attempt', '=', False), ('next_attempt', '<=', now),
        ], order='id', limit=limit)
        for delivery in due:
            # ``_attempt_once`` swallows the expected network / SSRF failures,
            # so one bad inbox does not abort the batch. Anything it does not
            # catch is a bug: the batch rolls back and the still-pending rows
            # are simply retried on the next run a minute later.
            delivery._attempt_once()
        return len(due)

    def _attempt_once(self):
        self.ensure_one()
        activity = self.activity_id
        actor = activity.actor_id
        if not actor or not actor.private_key_pem:
            self.write({'state': 'failed', 'last_error': 'sending actor has no key'})
            return
        try:
            status, text = post_activity(
                self.inbox_url, activity.payload, actor.key_id, actor.private_key_pem,
                allow_hosts=ssrf_allow_hosts(self.env))
        except ActivityPubError as exc:
            # SSRF block or malformed target - not worth retrying.
            self.write({
                'state': 'failed',
                'attempts': self.attempts + 1,
                'last_error': str(exc),
            })
            return
        except requests.RequestException as exc:
            self._schedule_retry(f'{type(exc).__name__}: {exc}')
            return

        if 200 <= status < 300:
            self.write({
                'state': 'delivered',
                'attempts': self.attempts + 1,
                'last_error': False,
                'delivered_at': fields.Datetime.now(),
            })
            self._settle_activity()
        elif status in (408, 429) or 500 <= status < 600:
            self._schedule_retry(f'HTTP {status}: {text[:300]}')
        else:
            self.write({
                'state': 'failed',
                'attempts': self.attempts + 1,
                'last_error': f'HTTP {status}: {text[:300]}',
            })
            self._settle_activity()

    def _schedule_retry(self, error):
        attempts = self.attempts + 1
        if attempts >= MAX_ATTEMPTS:
            self.write({'state': 'failed', 'attempts': attempts, 'last_error': error})
            self._settle_activity()
            return
        delay = min(BACKOFF_CAP_SECONDS, 60 * (2 ** (attempts - 1)))
        self.write({
            'state': 'retry',
            'attempts': attempts,
            'last_error': error,
            'next_attempt': fields.Datetime.now() + timedelta(seconds=delay),
        })

    def _settle_activity(self):
        """Reflect the delivery outcomes back onto the parent activity's
        state, once none of its deliveries are still in flight."""
        activity = self.activity_id
        states = set(activity.delivery_ids.mapped('state'))
        if states & {'pending', 'retry'}:
            return
        if 'delivered' in states:
            activity.state = 'delivered'
        else:
            activity.state = 'failed'

    # ------------------------------------------------------------------
    @api.model
    def _cron_gc(self, max_age_days=30):
        """Drop long-settled delivery rows so the table does not grow without
        bound. The parent activities (the outbox) are kept."""
        cutoff = fields.Datetime.now() - timedelta(days=max_age_days)
        stale = self.search([
            ('state', 'in', ('delivered', 'failed')),
            ('write_date', '<', cutoff),
        ])
        count = len(stale)
        stale.unlink()
        return count
