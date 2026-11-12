# -*- coding: utf-8 -*-
from datetime import datetime
from unittest.mock import MagicMock, patch

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.signalwire_voip.models import signalwire_dashboard

CLIENT = ('odoo.addons.signalwire_voip.models.signalwire_server.'
          'SignalWireServer._get_client')


def call(when, direction='inbound', parent=None):
    return {'start_time': when, 'direction': direction, 'parent_call_sid': parent}


@tagged('post_install', '-at_install')
class TestVoipDashboard(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        server = cls.env['signalwire.server'].create({
            'name': 'Test SignalWire', 'space': 'example.signalwire.com',
            'project_id': 'pid123', 'api_token': 'tok456'})
        sub = cls.env['signalwire.subproject'].create({
            'name': 'Office', 'server_id': server.id, 'account_sid': 'sub-abc', 'state': 'active'})
        cls.number = cls.env['signalwire.phone_number'].create({
            'name': '+17075550100', 'sid': 'pn-1', 'subproject_id': sub.id})
        cls.env.user.tz = 'America/Los_Angeles'

    def setUp(self):
        super().setUp()
        signalwire_dashboard._call_count_cache.clear()
        self.client = MagicMock()
        patcher = patch(CLIENT, return_value=self.client)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _data(self, refresh=False):
        # Thursday 2026-11-12, 10:00 in Santa Rosa
        with patch.object(type(self.env['signalwire.dashboard']), '_local_today',
                          lambda self: (datetime(2026, 11, 12).date(),
                                        __import__('pytz').timezone('America/Los_Angeles'))):
            return self.env['signalwire.dashboard'].get_dashboard_data(refresh=refresh)

    def _tile(self, data, key):
        return next(t for t in data['tiles'] if t['key'] == key)

    def test_numbers_table_lists_every_number(self):
        self.client.compat_get.return_value = {'calls': []}
        table = next(t for t in self._data()['tables'] if t['key'] == 'numbers')
        self.assertEqual(table['rows'][0]['cells'][0], '+17075550100')
        self.assertEqual(table['rows'][0]['open'],
                         {'res_model': 'signalwire.phone_number', 'res_id': self.number.id})

    def test_calls_are_counted_once_per_call_in_local_days(self):
        self.client.compat_get.return_value = {'calls': [
            call('Thu, 12 Nov 2026 18:00:00 +0000'),                      # today 10:00
            call('Thu, 12 Nov 2026 18:00:05 +0000', 'outbound-dial', parent='CA1'),  # its ringing leg
            call('Thu, 12 Nov 2026 19:30:00 +0000', 'outbound-api'),      # today, out
            call('Thu, 12 Nov 2026 07:30:00 +0000'),                      # Wed 23:30 local
            call('Fri, 06 Nov 2026 18:00:00 +0000'),                      # 6 days ago: in the week
            call('Thu, 05 Nov 2026 18:00:00 +0000'),                      # 7 days ago: out
        ]}
        data = self._data()
        today = self._tile(data, 'calls_today')
        self.assertEqual(today['value'], 2)
        self.assertEqual(today['hint'], '1 in, 1 out')
        self.assertEqual(self._tile(data, 'calls_week')['value'], 4)
        args, kwargs = self.client.compat_get.call_args
        self.assertEqual(args[0], 'Accounts/sub-abc/Calls.json')
        self.assertEqual(kwargs['StartTime>'], '2026-11-05')

    def test_call_counts_are_cached_unless_refreshed(self):
        self.client.compat_get.return_value = {'calls': []}
        self._data()
        self._data()
        self.assertEqual(self.client.compat_get.call_count, 1)
        self._data(refresh=True)
        self.assertEqual(self.client.compat_get.call_count, 2)

    def test_signalwire_trouble_shows_a_dash_not_an_error(self):
        self.client.compat_get.side_effect = RuntimeError('down')
        tile = self._tile(self._data(), 'calls_today')
        self.assertEqual(tile['value'], '-')
        self.assertIn("Couldn't reach SignalWire", tile['hint'])

    def test_opening_voip_shows_the_dashboard(self):
        root = self.env.ref('signalwire_voip.menu_signalwire_root')
        self.assertEqual(root.action, self.env.ref('signalwire_voip.action_signalwire_dashboard'))
