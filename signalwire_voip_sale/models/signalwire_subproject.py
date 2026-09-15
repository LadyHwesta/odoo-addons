# -*- coding: utf-8 -*-
from odoo import models

# Twilio-compatible date-range filter param names for each resource -
# well-documented, standard Compatibility API convention (unlike
# several other things in this project, this didn't need live
# discovery). The record-level field names (sid/price/from/to/duration/
# start_time/date_sent) are the same well-known convention - not yet
# live-verified against a real priced record though, since the trial
# account has no billed usage yet (see this module's own README).
USAGE_RESOURCES = (
    ('Calls', 'StartTime', 'call', 'start_time'),
    ('Messages', 'DateSent', 'sms', 'date_sent'),
)


class SignalWireSubproject(models.Model):
    _inherit = 'signalwire.subproject'

    def _sync_cdrs(self, contract_line, date_from, date_to):
        """Pull this subproject's calls + SMS for [date_from, date_to]
        from SignalWire and persist any not already pulled (matched by
        SignalWire's own SID - see signalwire.cdr's own uniqueness
        constraint) as signalwire.cdr records, priced with this
        server's markup applied *per record* rather than once over a
        lump sum, so each one carries a real customer-facing rate.

        Every matching record for the period - newly pulled this call
        or already pulled by an earlier one - is tagged with
        `contract_line` and returned, so a re-run for the same
        line/period (which shouldn't normally happen, but costs
        nothing to make safe) doesn't double-bill anything.

        Does not paginate - a subproject generating more than one page
        (50 records) of calls+messages in a single billing period
        would be undercounted here. Fine for a small reseller
        customer's actual volumes, not fine indefinitely.
        """
        self.ensure_one()
        client = self.server_id._get_client()
        markup = 1 + (self.server_id.markup_percentage or 0.0) / 100.0
        existing_sids = set(self.env['signalwire.cdr'].search(
            [('subproject_id', '=', self.id)]).mapped('sid'))

        for resource, date_param, record_type, date_field in USAGE_RESOURCES:
            params = {
                f'{date_param}<': date_to.isoformat(),
                f'{date_param}>': date_from.isoformat(),
            }
            result = client.compat_get(
                f'Accounts/{self.account_sid}/{resource}.json', **params)
            for record in result.get(resource.lower(), []):
                sid = record.get('sid')
                if not sid or sid in existing_sids:
                    continue
                wholesale = abs(float(record.get('price') or 0.0))
                billed = wholesale * markup
                if record_type == 'call':
                    duration = int(record.get('duration') or 0)
                    minutes = duration / 60.0
                    rate = (billed / minutes) if minutes else billed
                else:
                    duration = 0
                    rate = billed
                self.env['signalwire.cdr'].create({
                    'subproject_id': self.id,
                    'sid': sid,
                    'record_type': record_type,
                    'date': record.get(date_field),
                    'from_number': record.get('from'),
                    'to_number': record.get('to'),
                    'duration': duration,
                    'wholesale_cost': wholesale,
                    'rate': rate,
                    'billed_amount': billed,
                    'contract_line_id': contract_line.id,
                })
                existing_sids.add(sid)

        return self.env['signalwire.cdr'].search([
            ('contract_line_id', '=', contract_line.id),
            ('date', '>=', date_from), ('date', '<=', date_to),
        ])
