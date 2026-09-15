# -*- coding: utf-8 -*-
from unittest.mock import MagicMock, patch

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSignalWireSubproject(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.server = cls.env['signalwire.server'].create({
            'name': 'Test SignalWire',
            'space': 'example.signalwire.com',
            'project_id': 'pid123',
            'api_token': 'tok456',
        })
        cls.partner = cls.env['res.partner'].create({'name': 'Jane Customer'})

    def setUp(self):
        super().setUp()
        self.signalwire_client = MagicMock()
        patcher = patch(
            'odoo.addons.signalwire_voip.models.signalwire_server.'
            'SignalWireServer._get_client', return_value=self.signalwire_client)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _subproject(self):
        return self.env['signalwire.subproject'].create({
            'name': 'Jane Customer VoIP',
            'server_id': self.server.id,
            'partner_id': self.partner.id,
        })

    def test_provision_creates_the_subproject_and_stores_the_sid(self):
        self.signalwire_client.compat_post.return_value = {'sid': 'sub-abc'}
        subproject = self._subproject()

        subproject.action_provision()

        self.signalwire_client.compat_post.assert_called_once_with(
            'Accounts.json', FriendlyName='Jane Customer VoIP')
        self.assertEqual(subproject.account_sid, 'sub-abc')
        self.assertEqual(subproject.state, 'active')

    def test_provision_twice_raises(self):
        self.signalwire_client.compat_post.return_value = {'sid': 'sub-abc'}
        subproject = self._subproject()
        subproject.action_provision()

        with self.assertRaises(UserError):
            subproject.action_provision()

    def test_close_calls_the_api_and_marks_closed_locally(self):
        self.signalwire_client.compat_post.return_value = {'sid': 'sub-abc'}
        subproject = self._subproject()
        subproject.action_provision()

        subproject.action_close()

        self.signalwire_client.compat_post.assert_called_with(
            'Accounts/sub-abc.json', Status='closed')
        self.assertEqual(subproject.state, 'closed')

    def test_close_logs_a_manual_verification_note(self):
        # Known gap: SignalWire's own API didn't confirm closure took
        # effect when tested live - this note is the mitigation.
        self.signalwire_client.compat_post.return_value = {'sid': 'sub-abc'}
        subproject = self._subproject()
        subproject.action_provision()

        subproject.action_close()

        self.assertTrue(any(
            'dashboard' in (msg.body or '') for msg in subproject.message_ids))

    def test_close_unprovisioned_subproject_raises(self):
        subproject = self._subproject()
        with self.assertRaises(UserError):
            subproject.action_close()

    def test_purchase_number_requires_an_active_subproject(self):
        subproject = self._subproject()  # never provisioned - state='draft'
        with self.assertRaises(UserError):
            subproject.purchase_number('+14155550100')

    def test_purchase_number_creates_a_phone_number_record(self):
        self.signalwire_client.compat_post.side_effect = [
            {'sid': 'sub-abc'},  # provisioning
            {'sid': 'pn-123', 'phone_number': '+14155550100'},  # purchase
        ]
        subproject = self._subproject()
        subproject.action_provision()

        number = subproject.purchase_number('+14155550100')

        self.signalwire_client.compat_post.assert_called_with(
            'Accounts/sub-abc/IncomingPhoneNumbers.json', PhoneNumber='+14155550100')
        self.assertEqual(number.name, '+14155550100')
        self.assertEqual(number.sid, 'pn-123')
        self.assertEqual(number.subproject_id, subproject)

    def test_purchased_number_carries_the_subprojects_partner(self):
        self.signalwire_client.compat_post.side_effect = [
            {'sid': 'sub-abc'},
            {'sid': 'pn-123', 'phone_number': '+14155550100'},
        ]
        subproject = self._subproject()
        subproject.action_provision()

        number = subproject.purchase_number('+14155550100')

        self.assertEqual(number.partner_id, self.partner)
