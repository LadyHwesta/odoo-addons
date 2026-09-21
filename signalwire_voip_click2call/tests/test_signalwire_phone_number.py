# -*- coding: utf-8 -*-
from datetime import datetime
from unittest.mock import MagicMock, patch

from odoo.exceptions import UserError
from odoo.fields import Datetime
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSignalWirePhoneNumberClick2Call(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.server = cls.env['signalwire.server'].create({
            'name': 'Test SignalWire',
            'space': 'example.signalwire.com',
            'sip_domain': 'example-abc123.sip.signalwire.com',
            'project_id': 'pid123',
            'api_token': 'tok456',
        })
        cls.subproject = cls.env['signalwire.subproject'].create({
            'name': 'Internal Team', 'server_id': cls.server.id,
            'account_sid': 'sub-abc', 'state': 'active',
        })
        cls.number = cls.env['signalwire.phone_number'].create({
            'name': '+12084449665', 'sid': 'pn-123',
            'subproject_id': cls.subproject.id,
        })
        cls.user = cls.env['res.users'].create({
            'name': 'Jane Agent', 'login': 'jane.agent@example.com',
        })

    def setUp(self):
        super().setUp()
        self.signalwire_client = MagicMock()
        patcher = patch(
            'odoo.addons.signalwire_voip.models.signalwire_server.'
            'SignalWireServer._get_client', return_value=self.signalwire_client)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.env['ir.config_parameter'].sudo().set_param(
            'web.base.url', 'https://odoo.example.com')

    def test_configure_routing_requires_an_assigned_user(self):
        with self.assertRaises(UserError):
            self.number.action_configure_inbound_routing()

    def test_configure_routing_requires_a_provisioned_softphone(self):
        self.number.assigned_user_id = self.user
        with self.assertRaises(UserError):
            self.number.action_configure_inbound_routing()

    def test_configure_routing_sets_the_voice_url(self):
        self.user.write({'voip_username': f'user{self.user.id}'})
        self.number.assigned_user_id = self.user

        self.number.action_configure_inbound_routing()

        self.signalwire_client.compat_post.assert_called_once_with(
            'Accounts/sub-abc/IncomingPhoneNumbers/pn-123.json',
            VoiceUrl='https://odoo.example.com/signalwire/voice/inbound')

    def test_configure_routing_via_group_requires_a_provisioned_member(self):
        group = self.env['signalwire.call.group'].create({
            'name': 'Sales', 'member_ids': [(6, 0, [self.user.id])]})
        self.number.write({'route_type': 'group', 'call_group_id': group.id})

        with self.assertRaises(UserError):
            self.number.action_configure_inbound_routing()

    def test_configure_routing_via_group_succeeds_with_a_provisioned_member(self):
        self.user.write({'voip_username': f'user{self.user.id}'})
        group = self.env['signalwire.call.group'].create({
            'name': 'Sales', 'member_ids': [(6, 0, [self.user.id])]})
        self.number.write({'route_type': 'group', 'call_group_id': group.id})

        self.number.action_configure_inbound_routing()

        self.signalwire_client.compat_post.assert_called_once()

    def test_effective_route_with_no_calendar_always_uses_the_day_route(self):
        self.number.write({'route_type': 'user', 'assigned_user_id': self.user.id})
        route_type, target = self.number._effective_route()
        self.assertEqual((route_type, target), ('user', self.user))

    def test_effective_route_within_business_hours(self):
        calendar = self.env['resource.calendar'].create({
            'name': 'Test Hours', 'tz': 'UTC',
            'attendance_ids': [(0, 0, {
                'name': 'All Day Monday', 'dayofweek': '0',
                'hour_from': 0.0, 'hour_to': 24.0, 'day_period': 'morning',
            })],
        })
        after_hours_user = self.env['res.users'].create({
            'name': 'Night Owl', 'login': 'night.owl@example.com'})
        self.number.write({
            'route_type': 'user', 'assigned_user_id': self.user.id,
            'calendar_id': calendar.id,
            'after_hours_route_type': 'user', 'after_hours_user_id': after_hours_user.id,
        })
        monday_noon = Datetime.to_string(datetime(2026, 9, 21, 12, 0, 0))  # a real Monday

        with patch('odoo.fields.Datetime.now', return_value=Datetime.from_string(monday_noon)):
            route_type, target = self.number._effective_route()

        self.assertEqual((route_type, target), ('user', self.user))

    def test_effective_route_outside_business_hours_uses_after_hours_target(self):
        calendar = self.env['resource.calendar'].create({
            'name': 'Test Hours', 'tz': 'UTC',
            'attendance_ids': [(0, 0, {
                'name': 'All Day Monday', 'dayofweek': '0',
                'hour_from': 0.0, 'hour_to': 24.0, 'day_period': 'morning',
            })],
        })
        after_hours_user = self.env['res.users'].create({
            'name': 'Night Owl', 'login': 'night.owl@example.com'})
        self.number.write({
            'route_type': 'user', 'assigned_user_id': self.user.id,
            'calendar_id': calendar.id,
            'after_hours_route_type': 'user', 'after_hours_user_id': after_hours_user.id,
        })
        sunday = Datetime.to_string(datetime(2026, 9, 20, 12, 0, 0))  # a real Sunday

        with patch('odoo.fields.Datetime.now', return_value=Datetime.from_string(sunday)):
            route_type, target = self.number._effective_route()

        self.assertEqual((route_type, target), ('user', after_hours_user))
