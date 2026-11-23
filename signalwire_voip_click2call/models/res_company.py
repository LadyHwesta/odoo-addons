# -*- coding: utf-8 -*-
from datetime import datetime, time, timedelta

import pytz

from odoo import fields, models

# "Close for the rest of today" lasts until this local time tomorrow:
# late enough that tonight stays closed, early enough that no business
# opens before it.
REOPEN_AT = time(4, 0)


class ResCompany(models.Model):
    _inherit = 'res.company'

    signalwire_closed_until = fields.Datetime(
        string="Phones Closed Until", copy=False,
        help="While set and in the future, every number with Business Hours "
             "uses its outside-business-hours routing, as if the business "
             "were closed. Set by \"Close for the Rest of Today\"; clears "
             "itself overnight.")

    def _signalwire_closed_until(self):
        """The closed-early end time if it's still in the future, else
        False. An expired value is simply ignored, so nothing has to run
        overnight to reopen."""
        self.ensure_one()
        until = self.signalwire_closed_until
        return until if until and until > fields.Datetime.now() else False

    def _signalwire_next_reopen(self, tz_name):
        """REOPEN_AT tomorrow in `tz_name`, as a naive UTC datetime."""
        tz = pytz.timezone(tz_name or 'UTC')
        local_now = pytz.UTC.localize(fields.Datetime.now()).astimezone(tz)
        tomorrow = local_now.date() + timedelta(days=1)
        local_reopen = tz.localize(datetime.combine(tomorrow, REOPEN_AT))
        return local_reopen.astimezone(pytz.UTC).replace(tzinfo=None)

    def action_signalwire_close_today(self):
        for company in self:
            company.signalwire_closed_until = company._signalwire_next_reopen(self.env.context.get('tz') or self.env.user.tz)

    def action_signalwire_reopen(self):
        self.signalwire_closed_until = False
