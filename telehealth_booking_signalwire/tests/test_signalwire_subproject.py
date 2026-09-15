# -*- coding: utf-8 -*-
from datetime import date
from unittest.mock import MagicMock, patch

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSignalWireSubprojectVideoCdrSync(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.server = cls.env['signalwire.server'].create({
            'name': 'Test SignalWire', 'space': 'example.signalwire.com',
            'project_id': 'pid123', 'api_token': 'tok456', 'markup_percentage': 20.0,
        })
        cls.subproject = cls.env['signalwire.subproject'].create({
            'name': 'Dr Jane Video', 'server_id': cls.server.id,
            'account_sid': 'sub-abc', 'state': 'active',
        })
        cls.partner = cls.env['res.partner'].create({'name': 'Dr. Jane'})
        usage_product = cls.env.ref(
            'telehealth_booking_signalwire.product_telehealth_premium_usage')
        cls.contract = cls.env['contract.contract'].create({
            'name': 'Test Contract', 'partner_id': cls.partner.id,
            'contract_type': 'sale', 'line_recurrence': True,
            'contract_line_ids': [(0, 0, {
                'product_id': usage_product.id, 'name': 'Premium video usage',
                'quantity': 1, 'price_unit': 0.0,
                'date_start': date(2026, 9, 1), 'recurring_interval': 1,
                'recurring_rule_type': 'monthly', 'recurring_invoicing_type': 'post-paid',
                'is_signalwire_metered': True, 'signalwire_usage_type': 'video',
                'signalwire_subproject_id': cls.subproject.id,
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

    def _mock_two_level_api(self, sessions, members_by_session):
        def side_effect(path, **kw):
            if path == 'room_sessions':
                return {'data': sessions}
            for session_id, members in members_by_session.items():
                if path == f'room_sessions/{session_id}/members':
                    return {'data': members}
            return {'data': []}
        self.signalwire_client.video_get.side_effect = side_effect

    def test_sync_creates_a_video_cdr_per_member(self):
        self._mock_two_level_api(
            sessions=[{'id': 'sess-1', 'name': 'telehealth-1-abcd1234'}],
            members_by_session={'sess-1': [{
                'id': 'mem-1', 'name': 'Dr. Jane', 'join_time': '2026-09-03 14:00:00',
                'duration': '600', 'cost_in_dollars': '0.05',
            }]})

        cdrs = self.subproject._sync_video_cdrs(self.line, date(2026, 9, 1), date(2026, 9, 30))

        self.assertEqual(len(cdrs), 1)
        self.assertEqual(cdrs.sid, 'mem-1')
        self.assertEqual(cdrs.record_type, 'video')
        self.assertEqual(cdrs.duration, 600)
        self.assertEqual(cdrs.wholesale_cost, 0.05)
        self.assertEqual(cdrs.to_number, 'telehealth-1-abcd1234')

    def test_video_cdr_billed_amount_and_rate_use_the_markup(self):
        self._mock_two_level_api(
            sessions=[{'id': 'sess-1', 'name': 'telehealth-1-abcd1234'}],
            members_by_session={'sess-1': [{
                'id': 'mem-1', 'name': 'Dr. Jane', 'join_time': '2026-09-03 14:00:00',
                'duration': '600', 'cost_in_dollars': '0.05',
            }]})

        cdrs = self.subproject._sync_video_cdrs(self.line, date(2026, 9, 1), date(2026, 9, 30))

        self.assertAlmostEqual(cdrs.billed_amount, 0.05 * 1.2)
        expected_rate = (0.05 * 1.2) / (600 / 60.0)
        self.assertAlmostEqual(cdrs.rate, expected_rate)

    def test_sync_queries_both_levels_of_the_api(self):
        self._mock_two_level_api(
            sessions=[{'id': 'sess-1', 'name': 'room-a'}],
            members_by_session={'sess-1': []})

        self.subproject._sync_video_cdrs(self.line, date(2026, 9, 1), date(2026, 9, 30))

        calls = [c.args[0] for c in self.signalwire_client.video_get.call_args_list]
        self.assertIn('room_sessions', calls)
        self.assertIn('room_sessions/sess-1/members', calls)

    def test_multiple_members_in_one_session_each_become_their_own_cdr(self):
        self._mock_two_level_api(
            sessions=[{'id': 'sess-1', 'name': 'room-a'}],
            members_by_session={'sess-1': [
                {'id': 'mem-1', 'name': 'Dr. Jane', 'join_time': '2026-09-03 14:00:00',
                 'duration': '600', 'cost_in_dollars': '0.05'},
                {'id': 'mem-2', 'name': 'Patient', 'join_time': '2026-09-03 14:00:00',
                 'duration': '600', 'cost_in_dollars': '0.05'},
            ]})

        cdrs = self.subproject._sync_video_cdrs(self.line, date(2026, 9, 1), date(2026, 9, 30))

        self.assertEqual(len(cdrs), 2)

    def test_sync_does_not_duplicate_an_already_pulled_member(self):
        self._mock_two_level_api(
            sessions=[{'id': 'sess-1', 'name': 'room-a'}],
            members_by_session={'sess-1': [{
                'id': 'mem-1', 'name': 'Dr. Jane', 'join_time': '2026-09-03 14:00:00',
                'duration': '600', 'cost_in_dollars': '0.05',
            }]})

        self.subproject._sync_video_cdrs(self.line, date(2026, 9, 1), date(2026, 9, 30))
        self.subproject._sync_video_cdrs(self.line, date(2026, 9, 1), date(2026, 9, 30))

        self.assertEqual(
            self.env['signalwire.cdr'].search_count([('sid', '=', 'mem-1')]), 1)
