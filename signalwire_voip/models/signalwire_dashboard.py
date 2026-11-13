# -*- coding: utf-8 -*-
"""The VoIP dashboard's data: everything about the phone system on one page.

Each SignalWire module adds its own part by overriding ``_dashboard_parts``
(numbers and call counts here; routing, extensions and voicemail in
signalwire_voip_click2call; texts in signalwire_sms; callback requests in
signalwire_voip_portal), so a database shows only what it has installed.
The page itself (static/src/dashboard) knows nothing about any of them: it
draws a status banner, tiles and tables from the shapes described in
``get_dashboard_data``.
"""
import logging
import time
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime

import pytz

from odoo import _, api, models

_logger = logging.getLogger(__name__)

# Call counts come from SignalWire's call log; asking on every refresh would
# be slow and pointless, so they're kept this long per company.
CALL_COUNT_SECONDS = 300
_call_count_cache = {}


class SignalWireDashboard(models.AbstractModel):
    _name = 'signalwire.dashboard'
    _description = 'VoIP Dashboard'

    @api.model
    def get_dashboard_data(self, refresh=False):
        """{'status': {...} or False, 'tiles': [...], 'tables': [...]}

        tile:  {key, label, value, hint, tone ('ok'|'warning'|'info'|'muted'),
                sequence, action (an act_window dict or False)}
        table: {key, title, sequence, columns: [label, ...],
                rows: [{cells: [text, ...], tone, open: {res_model, res_id}}],
                empty: text}
        """
        data = {'status': False, 'tiles': [], 'tables': []}
        self.with_context(signalwire_dashboard_refresh=refresh)._dashboard_parts(data)
        data['tiles'].sort(key=lambda t: t.get('sequence', 50))
        data['tables'].sort(key=lambda t: t.get('sequence', 50))
        return data

    def _dashboard_parts(self, data):
        numbers = self.env['signalwire.phone_number'].search([], order='name')
        data['tables'].append({
            'key': 'numbers',
            'title': _("Your Numbers"),
            'sequence': 10,
            'columns': [_("Number"), _("Where calls go now")],
            'rows': [{'cells': [n.name, self._number_route_now(n)],
                      'tone': self._number_tone(n),
                      'open': {'res_model': n._name, 'res_id': n.id}} for n in numbers],
            'empty': _("No phone numbers yet."),
        })
        data['tiles'].extend(self._call_count_tiles(numbers))

    def _number_route_now(self, number):
        """Plain words for where this number's calls go right now; the
        routing module overrides this."""
        return _("Not set up in Odoo")

    def _number_tone(self, number):
        return 'muted'

    # --- Call counts from SignalWire's own call log -----------------------

    def _local_today(self):
        tz = pytz.timezone(self.env.user.tz or 'UTC')
        return datetime.now(tz).date(), tz

    def _call_count_tiles(self, numbers):
        if not numbers:
            return []
        counts = self._call_counts(numbers)
        common = {'sequence': 60, 'action': False}
        if counts is None:
            return [dict(common, key='calls_today', label=_("Calls today"), value="-",
                         hint=_("Couldn't reach the phone service just now"), tone='muted')]
        return [
            dict(common, key='calls_today', label=_("Calls today"), value=counts['today'],
                 hint=_("%(inbound)s in, %(outbound)s out",
                        inbound=counts['today_in'], outbound=counts['today_out']),
                 tone='info'),
            dict(common, key='calls_week', label=_("Calls in the last 7 days"),
                 value=counts['week'], hint=_("From the phone service's call log"), tone='info',
                 sequence=61),
        ]

    def _call_counts(self, numbers):
        """Counts of calls today and over the last 7 days (today included),
        in the user's time zone, across the subprojects these numbers live
        in. Each call is counted once: the extra legs SignalWire creates to
        ring each phone (those with a parent call) are skipped. None when
        SignalWire can't be reached."""
        key = (self.env.cr.dbname, self.env.company.id, self.env.user.tz)
        cached = _call_count_cache.get(key)
        if cached and not self.env.context.get('signalwire_dashboard_refresh') \
                and time.time() - cached[0] < CALL_COUNT_SECONDS:
            return cached[1]

        today, tz = self._local_today()
        week_start = today - timedelta(days=6)
        counts = {'today': 0, 'today_in': 0, 'today_out': 0, 'week': 0}
        subprojects = numbers.sudo().subproject_id.filtered('account_sid')
        try:
            for subproject in subprojects:
                client = subproject.server_id._get_client()
                result = client.compat_get(
                    f'Accounts/{subproject.account_sid}/Calls.json',
                    PageSize=1000,
                    # On or after this (UTC) date; one day early so a local
                    # day that starts before midnight UTC is covered.
                    **{'StartTime>': (week_start - timedelta(days=1)).isoformat()})
                for call in result.get('calls', []):
                    if call.get('parent_call_sid') or not call.get('start_time'):
                        continue
                    local_day = parsedate_to_datetime(call['start_time']).astimezone(tz).date()
                    if local_day < week_start:
                        continue
                    counts['week'] += 1
                    if local_day == today:
                        counts['today'] += 1
                        if call.get('direction') == 'inbound':
                            counts['today_in'] += 1
                        else:
                            counts['today_out'] += 1
        except Exception as exc:
            _logger.warning("VoIP dashboard: couldn't read SignalWire's call log: %s", exc)
            return None
        _call_count_cache[key] = (time.time(), counts)
        return counts

    # --- Helpers for the parts other modules add ---------------------------

    def _list_action(self, name, model, domain, context=None):
        return {
            'type': 'ir.actions.act_window',
            'name': name,
            'res_model': model,
            'domain': domain,
            'views': [[False, 'list'], [False, 'form']],
            'context': context or {},
        }
