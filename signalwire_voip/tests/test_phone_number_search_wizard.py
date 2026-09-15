# -*- coding: utf-8 -*-
from unittest.mock import MagicMock, patch

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestPhoneNumberSearchWizard(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.server = cls.env['signalwire.server'].create({
            'name': 'Test SignalWire',
            'space': 'example.signalwire.com',
            'project_id': 'pid123',
            'api_token': 'tok456',
        })
        cls.subproject = cls.env['signalwire.subproject'].create({
            'name': 'Test Subproject',
            'server_id': cls.server.id,
            'account_sid': 'sub-abc',
            'state': 'active',
        })

    def setUp(self):
        super().setUp()
        self.signalwire_client = MagicMock()
        patcher = patch(
            'odoo.addons.signalwire_voip.models.signalwire_server.'
            'SignalWireServer._get_client', return_value=self.signalwire_client)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_search_populates_result_lines(self):
        self.signalwire_client.compat_get.return_value = {'available_phone_numbers': [
            {'phone_number': '+14155550100'},
            {'phone_number': '+14155550101'},
        ]}
        wizard = self.env['signalwire.phone_number.search'].create({
            'subproject_id': self.subproject.id,
            'country': 'US',
        })

        wizard.action_search()

        self.assertEqual(
            sorted(wizard.result_ids.mapped('phone_number')),
            ['+14155550100', '+14155550101'])

    def test_searching_again_clears_the_previous_results(self):
        self.signalwire_client.compat_get.return_value = {'available_phone_numbers': [
            {'phone_number': '+14155550100'},
        ]}
        wizard = self.env['signalwire.phone_number.search'].create({
            'subproject_id': self.subproject.id,
        })
        wizard.action_search()
        self.assertEqual(len(wizard.result_ids), 1)

        self.signalwire_client.compat_get.return_value = {'available_phone_numbers': []}
        wizard.action_search()

        self.assertEqual(len(wizard.result_ids), 0)

    def test_purchase_from_a_result_row_buys_the_number(self):
        self.signalwire_client.compat_get.return_value = {'available_phone_numbers': [
            {'phone_number': '+14155550100'},
        ]}
        wizard = self.env['signalwire.phone_number.search'].create({
            'subproject_id': self.subproject.id,
        })
        wizard.action_search()
        self.signalwire_client.compat_post.return_value = {
            'sid': 'pn-123', 'phone_number': '+14155550100',
        }

        wizard.result_ids.action_purchase()

        purchased = self.env['signalwire.phone_number'].search(
            [('sid', '=', 'pn-123')])
        self.assertTrue(purchased)
        self.assertEqual(purchased.subproject_id, self.subproject)
