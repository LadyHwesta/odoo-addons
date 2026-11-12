# -*- coding: utf-8 -*-
from unittest.mock import MagicMock, patch

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSignalWireLiveCall(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.server = cls.env['signalwire.server'].create({
            'name': 'Test SignalWire', 'space': 'example.signalwire.com',
            'sip_domain': 'example-abc123.sip.signalwire.com',
            'project_id': 'pid123', 'api_token': 'tok456',
        })
        cls.subproject = cls.env['signalwire.subproject'].create({
            'name': 'Internal Team', 'server_id': cls.server.id,
            'account_sid': 'sub-abc', 'state': 'active',
        })
        cls.number = cls.env['signalwire.phone_number'].create({
            'name': '+12084449665', 'sid': 'pn-123', 'subproject_id': cls.subproject.id,
        })
        cls.user = cls.env['res.users'].create({
            'name': 'Jane Agent', 'login': 'jane.agent2@example.com',
            'voip_username': 'user_jane',
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

    def _call(self, **extra):
        vals = {
            'call_sid': 'CA123', 'phone_number_id': self.number.id,
            'from_number': '+15551234567',
        }
        vals.update(extra)
        return self.env['signalwire.live_call'].create(vals)

    def test_create_defaults_to_ringing(self):
        call = self._call()
        self.assertEqual(call.state, 'ringing')

    def test_route_to_user_requires_a_provisioned_softphone(self):
        call = self._call()
        no_phone_user = self.env['res.users'].create({
            'name': 'No Phone', 'login': 'no.phone2@example.com'})
        with self.assertRaises(UserError):
            call.action_route_to_user(no_phone_user.id)

    def test_route_to_user_redirects_and_updates_state(self):
        call = self._call()

        call.action_route_to_user(self.user.id)

        self.signalwire_client.compat_post.assert_called_once()
        args, kwargs = self.signalwire_client.compat_post.call_args
        self.assertEqual(args[0], 'Accounts/sub-abc/Calls/CA123.json')
        self.assertIn(
            f'/signalwire/voice/route_to_user/{self.user.id}/{self.number.id}',
            kwargs['Url'])
        self.assertEqual(call.assigned_user_id, self.user)
        self.assertEqual(call.state, 'ringing')

    def test_park_redirects_to_the_hold_loop_and_updates_state(self):
        call = self._call()

        call.action_park()

        args, kwargs = self.signalwire_client.compat_post.call_args
        self.assertIn(f'/signalwire/voice/hold_loop/{self.number.id}', kwargs['Url'])
        self.assertEqual(call.state, 'parked')

    def test_send_to_voicemail_redirects_and_updates_state(self):
        call = self._call()

        call.action_send_to_voicemail(self.user.id)

        args, kwargs = self.signalwire_client.compat_post.call_args
        self.assertIn(
            f'/signalwire/voice/route_to_voicemail/{self.user.id}/{self.number.id}',
            kwargs['Url'])
        self.assertEqual(call.assigned_user_id, self.user)

    def _call_aged(self, sid, minutes):
        call = self.env['signalwire.live_call'].create({
            'call_sid': sid, 'phone_number_id': self.number.id, 'from_number': '+15550001111'})
        self.env.cr.execute(
            "UPDATE signalwire_live_call SET create_date = now() at time zone 'UTC' - %s * interval '1 minute' "
            "WHERE id = %s", (minutes, call.id))
        call.invalidate_recordset(['create_date'])
        return call

    def test_cron_ends_calls_signalwire_says_are_over(self):
        just_started = self._call_aged('CA-new', 1)
        hung_up = self._call_aged('CA-gone', 10)
        still_talking = self._call_aged('CA-live', 10)
        ancient = self._call_aged('CA-old', 7 * 60)
        statuses = {'CA-gone': 'completed', 'CA-live': 'in-progress'}
        self.signalwire_client.compat_get.side_effect = lambda path: {
            'status': statuses[path.rsplit('/', 1)[1].removesuffix('.json')]}

        self.env['signalwire.live_call']._cron_close_finished_calls()

        self.assertEqual(hung_up.state, 'ended')
        self.assertEqual(ancient.state, 'ended')
        self.assertNotEqual(still_talking.state, 'ended')
        self.assertNotEqual(just_started.state, 'ended', "too new to ask about")
        asked = [c.args[0] for c in self.signalwire_client.compat_get.call_args_list]
        self.assertEqual(sorted(asked), ['Accounts/sub-abc/Calls/CA-gone.json',
                                         'Accounts/sub-abc/Calls/CA-live.json'])

    def test_cron_keeps_going_when_signalwire_cannot_answer(self):
        call = self._call_aged('CA-x', 10)
        self.signalwire_client.compat_get.side_effect = RuntimeError('down')
        self.env['signalwire.live_call']._cron_close_finished_calls()
        self.assertNotEqual(call.state, 'ended')

    def test_administrators_are_receptionists(self):
        admin = self.env['res.users'].create({
            'name': 'Ada Admin', 'login': 'ada.admin@example.com',
            'group_ids': [(6, 0, [self.env.ref('base.group_system').id])]})
        self.assertTrue(admin.has_group('signalwire_voip_click2call.group_signalwire_receptionist'))
