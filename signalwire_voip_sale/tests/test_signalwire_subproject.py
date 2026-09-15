# -*- coding: utf-8 -*-
from datetime import date
from unittest.mock import MagicMock, patch

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSignalWireSubprojectUsage(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.server = cls.env['signalwire.server'].create({
            'name': 'Test SignalWire', 'space': 'example.signalwire.com',
            'project_id': 'pid123', 'api_token': 'tok456', 'markup_percentage': 20.0,
        })
        cls.subproject = cls.env['signalwire.subproject'].create({
            'name': 'Customer Subproject', 'server_id': cls.server.id,
            'account_sid': 'sub-abc', 'state': 'active',
        })

    def setUp(self):
        super().setUp()
        self.signalwire_client = MagicMock()
        patcher = patch(
            'odoo.addons.signalwire_voip.models.signalwire_server.'
            'SignalWireServer._get_client', return_value=self.signalwire_client)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_usage_cost_sums_calls_and_messages_prices(self):
        def side_effect(path, **params):
            if path == 'Accounts/sub-abc/Calls.json':
                return {'calls': [{'price': '-0.0150'}, {'price': '-0.0075'}]}
            if path == 'Accounts/sub-abc/Messages.json':
                return {'messages': [{'price': '-0.0079'}]}
            return {}
        self.signalwire_client.compat_get.side_effect = side_effect

        cost = self.subproject._compute_usage_cost(date(2026, 9, 1), date(2026, 9, 30))

        self.assertAlmostEqual(cost, 0.0150 + 0.0075 + 0.0079)

    def test_usage_cost_uses_the_correct_date_filter_params(self):
        self.signalwire_client.compat_get.return_value = {}

        self.subproject._compute_usage_cost(date(2026, 9, 1), date(2026, 9, 30))

        calls_call = next(
            c for c in self.signalwire_client.compat_get.call_args_list
            if c.args[0] == 'Accounts/sub-abc/Calls.json')
        self.assertEqual(calls_call.kwargs['StartTime>'], '2026-09-01')
        self.assertEqual(calls_call.kwargs['StartTime<'], '2026-09-30')

        messages_call = next(
            c for c in self.signalwire_client.compat_get.call_args_list
            if c.args[0] == 'Accounts/sub-abc/Messages.json')
        self.assertEqual(messages_call.kwargs['DateSent>'], '2026-09-01')
        self.assertEqual(messages_call.kwargs['DateSent<'], '2026-09-30')

    def test_usage_cost_ignores_records_with_no_price(self):
        self.signalwire_client.compat_get.side_effect = lambda path, **kw: (
            {'calls': [{'price': None}, {}]} if 'Calls' in path else {'messages': []})

        cost = self.subproject._compute_usage_cost(date(2026, 9, 1), date(2026, 9, 30))

        self.assertEqual(cost, 0.0)

    def test_billed_usage_applies_the_markup(self):
        self.signalwire_client.compat_get.side_effect = lambda path, **kw: (
            {'calls': [{'price': '-1.00'}]} if 'Calls' in path else {'messages': []})

        billed = self.subproject._compute_billed_usage(date(2026, 9, 1), date(2026, 9, 30))

        self.assertAlmostEqual(billed, 1.20)
