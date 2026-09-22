# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSignalWireCallGroup(TransactionCase):

    def test_create_and_membership(self):
        alice = self.env['res.users'].create({
            'name': 'Alice', 'login': 'alice@example.com'})
        bob = self.env['res.users'].create({
            'name': 'Bob', 'login': 'bob@example.com'})

        group = self.env['signalwire.call.group'].create({
            'name': 'Sales', 'member_ids': [(6, 0, [alice.id, bob.id])],
        })

        self.assertEqual(group.member_ids, alice | bob)

    def test_voicemail_user_is_optional(self):
        group = self.env['signalwire.call.group'].create({'name': 'Support'})
        self.assertFalse(group.voicemail_user_id)

    def test_voicemail_mode_defaults_to_none(self):
        group = self.env['signalwire.call.group'].create({'name': 'Support'})
        self.assertEqual(group.voicemail_mode, 'none')
