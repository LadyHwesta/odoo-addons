# -*- coding: utf-8 -*-
from unittest.mock import MagicMock, patch

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestResUsersTelehealthUpgrade(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.server = cls.env['signalwire.server'].create({
            'name': 'Test SignalWire', 'space': 'example.signalwire.com',
            'project_id': 'pid123', 'api_token': 'tok456',
        })
        cls.user = cls.env['res.users'].create({
            'name': 'Dr. Jane', 'login': 'dr.jane@example.com',
        })

    def setUp(self):
        super().setUp()
        self.signalwire_client = MagicMock()
        patcher = patch(
            'odoo.addons.signalwire_voip.models.signalwire_server.'
            'SignalWireServer._get_client', return_value=self.signalwire_client)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.signalwire_client.compat_post.return_value = {'sid': 'sub-abc'}

    def test_upgrade_flips_the_tier(self):
        self.user.action_upgrade_telehealth_video()
        self.assertEqual(self.user.telehealth_video_tier, 'premium')

    def test_upgrade_does_not_eagerly_provision_billing(self):
        self.user.action_upgrade_telehealth_video()
        self.assertFalse(self.user.signalwire_video_subproject_id)
        self.assertFalse(self.user.signalwire_video_contract_id)

    def test_upgrade_twice_raises(self):
        self.user.action_upgrade_telehealth_video()
        with self.assertRaises(UserError):
            self.user.action_upgrade_telehealth_video()

    def test_downgrade_flips_back(self):
        self.user.action_upgrade_telehealth_video()
        self.user.action_downgrade_telehealth_video()
        self.assertEqual(self.user.telehealth_video_tier, 'basic')

    def test_downgrade_when_already_basic_raises(self):
        with self.assertRaises(UserError):
            self.user.action_downgrade_telehealth_video()

    def test_ensure_billing_provisions_subproject_and_contract(self):
        self.user._ensure_telehealth_video_billing()

        self.assertTrue(self.user.signalwire_video_subproject_id)
        self.assertEqual(self.user.signalwire_video_subproject_id.account_sid, 'sub-abc')
        self.assertTrue(self.user.signalwire_video_contract_id)
        line = self.user.signalwire_video_contract_id.contract_line_ids
        self.assertTrue(line.is_signalwire_metered)
        self.assertEqual(line.signalwire_usage_type, 'video')
        self.assertEqual(line.recurring_invoicing_type, 'post-paid')

    def test_ensure_billing_is_idempotent(self):
        self.user._ensure_telehealth_video_billing()
        subproject = self.user.signalwire_video_subproject_id
        contract = self.user.signalwire_video_contract_id

        self.user._ensure_telehealth_video_billing()

        self.assertEqual(self.user.signalwire_video_subproject_id, subproject)
        self.assertEqual(self.user.signalwire_video_contract_id, contract)
