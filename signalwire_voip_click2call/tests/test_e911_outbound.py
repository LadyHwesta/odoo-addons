# -*- coding: utf-8 -*-
from unittest.mock import MagicMock, patch

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestE911Outbound(TransactionCase):
    """Phones may call outside numbers only while their Calls Out As
    number's E911 is active."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.server = cls.env['signalwire.server'].create({
            'name': 'Test SignalWire', 'space': 'example.signalwire.com',
            'sip_domain': 'example-abc123.sip.signalwire.com',
            'project_id': 'pid123', 'api_token': 'tok456',
        })
        sub = cls.env['signalwire.subproject'].create({
            'name': 'Sub', 'server_id': cls.server.id, 'account_sid': 'pid123', 'state': 'active'})
        cls.number = cls.env['signalwire.phone_number'].create(
            {'name': '+17075550100', 'sid': 'pn-1', 'subproject_id': sub.id})
        cls.user = cls.env['res.users'].create({'name': 'Jane Agent', 'login': 'jane.e911@example.com'})
        cls.user.write({'signalwire_sip_endpoint_id': 'ep-1', 'signalwire_server_id': cls.server.id})

    def setUp(self):
        super().setUp()
        self.client = MagicMock()
        patcher = patch(
            'odoo.addons.signalwire_voip.models.signalwire_server.'
            'SignalWireServer._get_client', return_value=self.client)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _last_put(self):
        args, kwargs = self.client.relay_put.call_args
        return args[0], kwargs

    def test_no_e911_means_internal_calls_only(self):
        self.user.signalwire_outbound_number_id = self.number
        path, body = self._last_put()
        self.assertEqual(path, 'endpoints/sip/ep-1')
        self.assertEqual(body, {'call_handler': 'block-pstn'})
        self.assertFalse(self.user.signalwire_outbound_allowed)

    def test_active_e911_allows_outside_calls_as_that_number(self):
        self.number.e911_status = 'active'
        self.user.signalwire_outbound_number_id = self.number
        path, body = self._last_put()
        self.assertEqual(body, {'call_handler': 'passthrough', 'send_as': '+17075550100'})
        self.assertTrue(self.user.signalwire_outbound_allowed)

    def test_e911_becoming_active_opens_outside_calls(self):
        self.user.signalwire_outbound_number_id = self.number
        self.number._e911_apply({'e911_status': 'active'})
        self.assertEqual(self._last_put()[1]['call_handler'], 'passthrough')

    def test_e911_removed_closes_outside_calls(self):
        self.number.e911_status = 'active'
        self.user.signalwire_outbound_number_id = self.number
        self.number._e911_apply({'e911_status': 'pending_removal'})
        self.assertEqual(self._last_put()[1], {'call_handler': 'block-pstn'})

    def test_new_softphone_gets_the_rule(self):
        user = self.env['res.users'].create({'name': 'New Agent', 'login': 'new.e911@example.com'})
        self.client.relay_post.return_value = {'id': 'ep-new', 'username': 'new.agent'}
        user.action_provision_signalwire_sip()
        path, body = self._last_put()
        self.assertEqual(path, 'endpoints/sip/ep-new')
        self.assertEqual(body, {'call_handler': 'block-pstn'})

    def test_desk_phones_follow_their_user(self):
        phone = self.env['signalwire.desk_phone'].create({
            'name': 'Front desk', 'user_id': self.user.id, 'mac_address': '00:15:65:aa:bb:cc', 'brand': 'yealink',
            'signalwire_sip_endpoint_id': 'ep-desk', 'signalwire_server_id': self.server.id})
        self.number.e911_status = 'active'
        self.user.signalwire_outbound_number_id = self.number
        paths = [c.args[0] for c in self.client.relay_put.call_args_list]
        self.assertIn('endpoints/sip/ep-1', paths)
        self.assertIn(f'endpoints/sip/{phone.signalwire_sip_endpoint_id}', paths)

    def test_apply_to_all_phones(self):
        result = self.server.action_apply_e911_to_phones()
        self.assertTrue(self.client.relay_put.called)
        self.assertEqual(result['tag'], 'display_notification')
