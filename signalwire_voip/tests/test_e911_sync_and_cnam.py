# -*- coding: utf-8 -*-
from unittest.mock import MagicMock, patch

from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.signalwire_voip.models.signalwire_api import SignalWireAPIError
from odoo.addons.signalwire_voip.models.signalwire_phone_number import (
    cnam_problem, normalize_cnam, suggest_cnam)


@tagged('post_install', '-at_install')
class TestE911SyncAndCnam(TransactionCase):
    """E911 status set up anywhere else shows here; customer numbers are
    left to the customer's own Odoo; caller ID names are requested and
    followed up automatically."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.server = cls.env['signalwire.server'].create({
            'name': 'Test', 'space': 'example.signalwire.com',
            'project_id': 'pid123', 'api_token': 'tok456'})
        cls.own_sub = cls.env['signalwire.subproject'].create({
            'name': 'Ours', 'server_id': cls.server.id, 'account_sid': 'pid123', 'state': 'active'})
        cls.customer = cls.env['res.partner'].create({'name': 'TFL Conference'})
        cls.customer_sub = cls.env['signalwire.subproject'].create({
            'name': 'TFL', 'server_id': cls.server.id, 'account_sid': 'sub-tfl', 'state': 'active',
            'partner_id': cls.customer.id})
        cls.own = cls.env['signalwire.phone_number'].create({
            'name': '+17078021991', 'sid': 'pn-own', 'subproject_id': cls.own_sub.id})
        cls.theirs = cls.env['signalwire.phone_number'].create({
            'name': '+17075898352', 'sid': 'pn-tfl', 'subproject_id': cls.customer_sub.id})

    def setUp(self):
        super().setUp()
        self.client = MagicMock()
        self.startPatcher(patch(
            'odoo.addons.signalwire_voip.models.signalwire_server.'
            'SignalWireServer._get_client', return_value=self.client))

    # ---- E911 ----

    def test_daily_check_finds_e911_registered_elsewhere(self):
        self.client.relay_get.return_value = {'e911_status': 'active'}
        self.assertEqual(self.own.e911_status, 'none')
        self.env['signalwire.phone_number']._cron_refresh_e911_all()
        self.assertEqual(self.own.e911_status, 'active')
        paths = [c.args[0] for c in self.client.relay_get.call_args_list]
        self.assertIn('phone_numbers/pn-own', paths)
        self.assertNotIn('phone_numbers/pn-tfl', paths)  # their sub-account: 404 from here

    def test_one_failing_number_doesnt_stop_the_others(self):
        other = self.env['signalwire.phone_number'].create({
            'name': '+17073590900', 'sid': 'pn-two', 'subproject_id': self.own_sub.id})

        def answer(path):
            if path == 'phone_numbers/pn-own':
                raise SignalWireAPIError('boom')
            return {'e911_status': 'active'}
        self.client.relay_get.side_effect = answer
        self.env['signalwire.phone_number']._cron_refresh_e911_all()
        self.assertEqual(other.e911_status, 'active')

    def test_customer_numbers_cant_be_changed_from_here(self):
        for action in ('action_refresh_e911', 'action_assign_e911', 'action_remove_e911',
                       'action_request_cnam', 'action_refresh_cnam'):
            with self.subTest(action=action), self.assertRaises(UserError):
                getattr(self.theirs, action)()
        self.client.relay_get.assert_not_called()
        self.client.relay_post.assert_not_called()

    def test_own_lists_leave_customers_out(self):
        own_action = self.env.ref('signalwire_voip.action_signalwire_phone_number')
        customer_action = self.env.ref('signalwire_voip.action_signalwire_customer_phone_number')
        Number = self.env['signalwire.phone_number']
        own_ids = Number.search(eval(own_action.domain)).ids
        customer_ids = Number.search(eval(customer_action.domain)).ids
        self.assertIn(self.own.id, own_ids)
        self.assertNotIn(self.theirs.id, own_ids)
        self.assertIn(self.theirs.id, customer_ids)
        data = self.env['signalwire.dashboard'].get_dashboard_data()
        numbers = next(t for t in data['tables'] if t['key'] == 'numbers')
        self.assertNotIn('+17075898352', [r['cells'][0] for r in numbers['rows']])

    # ---- caller ID name ----

    def test_name_rules(self):
        self.assertEqual(normalize_cnam('  Meskis   works\t'), 'MESKIS WORKS')
        self.assertIsNone(cnam_problem('MESKIS WORKS'))
        self.assertIsNone(cnam_problem("O'NEIL & CO."))
        self.assertTrue(cnam_problem('A' * 16))
        self.assertTrue(cnam_problem('-MESKIS'))
        self.assertTrue(cnam_problem('MESKIS!'))
        self.assertEqual(suggest_cnam('Meskis Works, LLC (Santa Rosa)'), 'MESKIS WORKS')
        self.assertLessEqual(len(suggest_cnam('The Very Long Company Name Inc')), 15)
        with self.assertRaises(ValidationError):
            self.own.cnam_name = 'Way too long a caller name'

    def test_request_stores_the_pending_review(self):
        self.client.relay_post.return_value = {'status': 'pending', 'name': 'MESKIS WORKS'}
        self.own.cnam_name = 'Meskis Works'
        self.own.action_request_cnam()
        self.client.relay_post.assert_called_once_with('phone_numbers/pn-own/cnam', name='MESKIS WORKS')
        self.assertEqual((self.own.cnam_name, self.own.cnam_status), ('MESKIS WORKS', 'pending'))

    def test_no_name_uses_the_company_name(self):
        self.client.relay_post.return_value = {'status': 'pending'}
        self.own.company_id.name = 'Meskis Works'
        self.own.action_request_cnam()
        self.client.relay_post.assert_called_once_with('phone_numbers/pn-own/cnam', name='MESKIS WORKS')

    def test_carrier_without_caller_id_names_is_explained(self):
        self.client.relay_post.side_effect = SignalWireAPIError(
            "Caller ID name isn't available for this number.", status=422)
        self.own.cnam_name = 'MESKIS WORKS'
        with self.assertRaisesRegex(UserError, "doesn't offer caller ID names"):
            self.own.action_request_cnam()

    def test_toll_free_is_refused_up_front(self):
        toll_free = self.env['signalwire.phone_number'].create({
            'name': '+18885550100', 'sid': 'pn-tf', 'subproject_id': self.own_sub.id,
            'cnam_name': 'MESKIS WORKS'})
        with self.assertRaisesRegex(UserError, 'toll-free'):
            toll_free.action_request_cnam()
        self.client.relay_post.assert_not_called()

    def test_pending_requests_are_followed_up(self):
        self.own.write({'cnam_name': 'MESKIS WORKS', 'cnam_status': 'pending'})
        self.client.relay_get.return_value = {'status': 'rejected', 'reason': 'too_generic'}
        self.env['signalwire.phone_number']._cron_refresh_cnam()
        self.assertEqual((self.own.cnam_status, self.own.cnam_reason), ('rejected', 'too_generic'))

    def test_never_requested_reads_as_none(self):
        self.client.relay_get.side_effect = SignalWireAPIError('Not Found', status=404)
        self.own.action_refresh_cnam()
        self.assertEqual(self.own.cnam_status, 'none')
