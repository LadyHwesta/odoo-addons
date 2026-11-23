# -*- coding: utf-8 -*-
from datetime import datetime, time

import pytz

from odoo import _, models


class SignalWireDashboard(models.AbstractModel):
    _inherit = 'signalwire.dashboard'

    def _dashboard_parts(self, data):
        super()._dashboard_parts(data)
        today, tz = self._local_today()
        start = tz.localize(datetime.combine(today, time.min)).astimezone(pytz.UTC).replace(tzinfo=None)
        Sms = self.env['signalwire.sms']
        today_domain = [('create_date', '>=', start)]
        received = Sms.search_count(today_domain + [('direction', '=', 'inbound')])
        sent = Sms.search_count(today_domain + [('direction', '=', 'outbound')])
        data['tiles'].append({
            'key': 'texts_today', 'sequence': 30,
            'label': _("Texts received today"), 'value': received,
            'hint': _("%(sent)s sent", sent=sent),
            'tone': 'info' if received else 'muted',
            'action': self._list_action(_("Texts Today"), Sms._name, today_domain),
        })
