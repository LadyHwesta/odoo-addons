# -*- coding: utf-8 -*-
"""Inbox flood guard, tracked independently of whether a request ever turns
out to be a legitimate, verifiable activity.

The rate limit has to fire *before* the expensive part (an SSRF-checked DNS
resolution + HTTP GET to dereference the claimed actor, with up to a 20s
read timeout) - a guard that only counts requests which already passed
signature verification never bounds the cost of a flood using forged or
simply unverifiable actor claims, since those are rejected (401) before
anything gets that far.
"""
from datetime import timedelta

from odoo import api, fields, models


class ActivityPubInboxAttempt(models.Model):
    """One inbound POST, recorded the moment its claimed actor's host is
    known - before any network dereference or signature check. Deliberately
    minimal: no link to an actor/activity, just enough to count a window."""
    _name = 'activitypub.inbox.attempt'
    _description = 'ActivityPub Inbox Attempt'
    _rec_name = 'host'

    host = fields.Char(required=True, index=True)

    @api.model
    def _record(self, host):
        self.create({'host': host})

    @api.model
    def _is_flooding(self, host, window_seconds, limit):
        """True once ``limit`` attempts (including the one just recorded by
        ``_record``) have been seen from ``host`` within the trailing
        window. Keyed by host, not the exact claimed URI, so a flood
        varying the path on one attacker-controlled host is still caught -
        the trade-off is that a single very busy legitimate remote server
        (many of its users interacting with us in the same burst) shares
        one bucket too; the threshold is picked generously enough that
        this should not matter in practice.
        """
        cutoff = fields.Datetime.now() - timedelta(seconds=window_seconds)
        return self.search_count([
            ('host', '=', host),
            ('create_date', '>=', cutoff),
        ]) >= limit

    @api.model
    def _cron_gc(self, max_age_days=1):
        cutoff = fields.Datetime.now() - timedelta(days=max_age_days)
        stale = self.search([('create_date', '<', cutoff)])
        count = len(stale)
        stale.unlink()
        return count
