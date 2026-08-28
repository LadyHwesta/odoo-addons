# -*- coding: utf-8 -*-
from odoo import models


class CalendarRecurrence(models.Model):
    _inherit = 'calendar.recurrence'

    def write(self, vals):
        res = super().write(vals)
        # Every structural change (interval/count/until/weekdays/...) funnels
        # through a rewrite of the computed `rrule` field (see
        # calendar_recurrence.py::_compute_rrule upstream), so watching just
        # this one key is enough to catch recurrence-pattern edits made
        # without touching the base calendar.event's own fields.
        if not self.env.context.get('caldav_no_sync') and 'rrule' in vals:
            dirty = self.mapped('base_event_id').filtered(
                lambda e: not e.need_caldav_sync and not e.caldav_account_id.read_only)
            if dirty:
                dirty.write({'need_caldav_sync': True})
        return res
