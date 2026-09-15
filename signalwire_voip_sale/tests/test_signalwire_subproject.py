# -*- coding: utf-8 -*-
from datetime import date
from unittest.mock import MagicMock, patch

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSignalWireSubprojectCdrSync(TransactionCase):

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
        cls.partner = cls.env['res.partner'].create({'name': 'Jane Customer'})
        usage_product = cls.env.ref('signalwire_voip_sale.product_signalwire_usage')
        cls.contract = cls.env['contract.contract'].create({
            'name': 'Test Contract', 'partner_id': cls.partner.id,
            'contract_type': 'sale', 'line_recurrence': True,
            'contract_line_ids': [(0, 0, {
                'product_id': usage_product.id, 'name': 'Metered usage',
                'quantity': 1, 'price_unit': 0.0,
                'date_start': date(2026, 9, 1), 'recurring_interval': 1,
                'recurring_rule_type': 'monthly', 'recurring_invoicing_type': 'post-paid',
                'is_signalwire_metered': True, 'signalwire_subproject_id': cls.subproject.id,
            })],
        })
        cls.line = cls.contract.contract_line_ids

    def setUp(self):
        super().setUp()
        self.signalwire_client = MagicMock()
        patcher = patch(
            'odoo.addons.signalwire_voip.models.signalwire_server.'
            'SignalWireServer._get_client', return_value=self.signalwire_client)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _mock_records(self, calls=None, messages=None):
        self.signalwire_client.compat_get.side_effect = lambda path, **kw: (
            {'calls': calls or []} if 'Calls' in path else {'messages': messages or []})

    def test_sync_creates_a_cdr_per_call(self):
        self._mock_records(calls=[{
            'sid': 'CA1', 'price': '-0.0150', 'duration': '134',
            'from': '+12084449665', 'to': '+15551234567', 'start_time': '2026-09-03 14:22:00',
        }])

        cdrs = self.subproject._sync_cdrs(self.line, date(2026, 9, 1), date(2026, 9, 30))

        self.assertEqual(len(cdrs), 1)
        self.assertEqual(cdrs.sid, 'CA1')
        self.assertEqual(cdrs.record_type, 'call')
        self.assertEqual(cdrs.duration, 134)
        self.assertEqual(cdrs.wholesale_cost, 0.0150)
        self.assertEqual(cdrs.contract_line_id, self.line)

    def test_call_billed_amount_and_rate_use_the_markup(self):
        self._mock_records(calls=[{
            'sid': 'CA1', 'price': '-0.0150', 'duration': '134',
            'from': '+12084449665', 'to': '+15551234567', 'start_time': '2026-09-03 14:22:00',
        }])

        cdrs = self.subproject._sync_cdrs(self.line, date(2026, 9, 1), date(2026, 9, 30))

        self.assertAlmostEqual(cdrs.billed_amount, 0.0150 * 1.2)
        # rate is $/minute, computed from the *billed* (marked-up)
        # amount, not SignalWire's own wholesale price - the whole
        # point of pricing per-record.
        expected_rate = (0.0150 * 1.2) / (134 / 60.0)
        self.assertAlmostEqual(cdrs.rate, expected_rate)

    def test_sms_has_no_duration_and_rate_equals_billed_amount(self):
        self._mock_records(messages=[{
            'sid': 'SM1', 'price': '-0.0079',
            'from': '+12084449665', 'to': '+15551234567', 'date_sent': '2026-09-05 09:01:00',
        }])

        cdrs = self.subproject._sync_cdrs(self.line, date(2026, 9, 1), date(2026, 9, 30))

        self.assertEqual(cdrs.record_type, 'sms')
        self.assertEqual(cdrs.duration, 0)
        self.assertAlmostEqual(cdrs.rate, cdrs.billed_amount)

    def test_sync_uses_the_correct_date_filter_params(self):
        self._mock_records()

        self.subproject._sync_cdrs(self.line, date(2026, 9, 1), date(2026, 9, 30))

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

    def test_sync_does_not_duplicate_an_already_pulled_record(self):
        self._mock_records(calls=[{
            'sid': 'CA1', 'price': '-0.0150', 'duration': '60',
            'from': '+1', 'to': '+2', 'start_time': '2026-09-03 14:22:00',
        }])

        self.subproject._sync_cdrs(self.line, date(2026, 9, 1), date(2026, 9, 30))
        self.subproject._sync_cdrs(self.line, date(2026, 9, 1), date(2026, 9, 30))

        self.assertEqual(
            self.env['signalwire.cdr'].search_count([('sid', '=', 'CA1')]), 1)

    def test_records_with_no_price_are_zero_cost(self):
        self._mock_records(calls=[{
            'sid': 'CA1', 'price': None, 'duration': '10',
            'from': '+1', 'to': '+2', 'start_time': '2026-09-03 14:22:00',
        }])

        cdrs = self.subproject._sync_cdrs(self.line, date(2026, 9, 1), date(2026, 9, 30))

        self.assertEqual(cdrs.wholesale_cost, 0.0)
        self.assertEqual(cdrs.billed_amount, 0.0)

    def test_sync_returns_only_records_for_this_line_and_period(self):
        self._mock_records(calls=[{
            'sid': 'CA1', 'price': '-0.01', 'duration': '60',
            'from': '+1', 'to': '+2', 'start_time': '2026-09-03 14:22:00',
        }])
        self.subproject._sync_cdrs(self.line, date(2026, 9, 1), date(2026, 9, 30))

        # A second, unrelated line/period shouldn't pick up the first
        # line's already-tagged CDR.
        other_line = self.env['contract.line'].create({
            'contract_id': self.contract.id,
            'product_id': self.env.ref('signalwire_voip_sale.product_signalwire_usage').id,
            'name': 'Other period', 'quantity': 1, 'price_unit': 0.0,
            'date_start': date(2026, 10, 1), 'recurring_interval': 1,
            'recurring_rule_type': 'monthly', 'recurring_invoicing_type': 'post-paid',
            'is_signalwire_metered': True, 'signalwire_subproject_id': self.subproject.id,
        })
        self._mock_records()
        cdrs = self.subproject._sync_cdrs(other_line, date(2026, 10, 1), date(2026, 10, 31))

        self.assertFalse(cdrs)
