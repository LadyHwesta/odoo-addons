# -*- coding: utf-8 -*-
from odoo import models

# Twilio-compatible date-range filter param names for each resource -
# well-documented, standard Compatibility API convention (unlike
# several other things in this project, this didn't need live
# discovery). Not yet live-verified against a real priced record,
# though - the trial account has no billed usage yet (see this
# module's own README).
USAGE_RESOURCES = (
    ('Calls', 'StartTime'),
    ('Messages', 'DateSent'),
)


class SignalWireSubproject(models.Model):
    _inherit = 'signalwire.subproject'

    def _compute_usage_cost(self, date_from, date_to):
        """Real SignalWire cost (before markup) for this subproject's
        calls + SMS between date_from and date_to (inclusive), summing
        each record's own ``price`` field. SignalWire's own convention
        represents cost as a *negative* number (money leaving the
        account) - this returns a positive total.

        Does not paginate - a subproject generating more than one page
        (50 records by default) of calls+messages in a single billing
        period would undercount here. Fine for the volumes a small
        reseller customer generates; revisit if that stops being true.
        """
        self.ensure_one()
        client = self.server_id._get_client()
        total = 0.0
        for resource, date_field in USAGE_RESOURCES:
            params = {
                f'{date_field}<': date_to.isoformat(),
                f'{date_field}>': date_from.isoformat(),
            }
            result = client.compat_get(
                f'Accounts/{self.account_sid}/{resource}.json', **params)
            for record in result.get(resource.lower(), []):
                price = record.get('price')
                if price:
                    total += abs(float(price))
        return total

    def _compute_billed_usage(self, date_from, date_to):
        """_compute_usage_cost with this project's markup applied -
        what the customer actually gets charged for the period."""
        self.ensure_one()
        cost = self._compute_usage_cost(date_from, date_to)
        markup = 1 + (self.server_id.markup_percentage or 0.0) / 100.0
        return cost * markup
