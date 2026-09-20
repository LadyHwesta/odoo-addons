# -*- coding: utf-8 -*-
from odoo import models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    def format_partner(self):
        """voip_oca's own format_partner() hands the softphone the raw
        ``phone`` field verbatim - fine for voip_oca's own
        provider-agnostic design, but SignalWire's SIP trunk expects a
        fully-qualified number (country code included) to route a
        call, and click_to_call's own dial logic
        (voip_agent_service.esm.js's call()) only ever strips
        non-digit characters, it never adds a country code. A contact
        whose phone field was entered without one (e.g. a local
        "(707) 555-1234" rather than "+1 707 555 1234") would silently
        just sit at a dialtone - not a SignalWire bug, a missing
        digits-count on our own end.

        Using core's own _phone_format(force_format='E164') derives
        the country code from the partner's own country_id (falling
        back to the company's) instead of requiring every contact's
        phone number to be re-entered with one - and is a no-op for a
        number that already has one, so this is safe either way.
        """
        vals = super().format_partner()
        vals['phone'] = self._phone_format(fname='phone', force_format='E164') or self.phone
        return vals
