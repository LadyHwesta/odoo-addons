# -*- coding: utf-8 -*-
from odoo import _, models


class SignalWireDashboard(models.AbstractModel):
    _inherit = 'signalwire.dashboard'

    def _dashboard_parts(self, data):
        super()._dashboard_parts(data)
        Request = self.env['signalwire.callback_request']
        if not Request.has_access('read'):
            return
        pending = Request.search_count([('state', '=', 'pending')])
        data['tiles'].append({
            'key': 'callbacks', 'sequence': 20,
            'label': _("Callback requests"), 'value': pending,
            'hint': _("Customers waiting for a call back"),
            'tone': 'warning' if pending else 'ok',
            'action': self._list_action(_("Callback Requests"), Request._name,
                                        [('state', '=', 'pending')]),
        })
