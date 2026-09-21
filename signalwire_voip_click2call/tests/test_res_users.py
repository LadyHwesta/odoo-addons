# -*- coding: utf-8 -*-
from unittest.mock import MagicMock, patch

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestResUsersSignalWireSip(TransactionCase):

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

    def test_provision_creates_a_sip_endpoint_and_wires_voip_oca_fields(self):
        expected_username = f'jane.agent{self.user.id}'
        self.signalwire_client.relay_post.return_value = {
            'id': 'ep-abc', 'username': expected_username,
        }

        self.user.action_provision_signalwire_sip()

        self.signalwire_client.relay_post.assert_called_once()
        args, kwargs = self.signalwire_client.relay_post.call_args
        self.assertEqual(args[0], 'endpoints/sip')
        self.assertEqual(kwargs['username'], expected_username)
        self.assertEqual(self.user.signalwire_sip_endpoint_id, 'ep-abc')
        self.assertEqual(self.user.voip_username, expected_username)
        self.assertTrue(self.user.voip_password)
        self.assertEqual(self.user.voip_pbx_id.name, 'Test SignalWire')

    def test_sip_username_is_built_from_the_users_real_name(self):
        self.assertEqual(
            self.user._signalwire_sip_username(), f'jane.agent{self.user.id}')

    def test_sip_username_normalizes_accented_characters(self):
        user = self.env['res.users'].create({
            'name': 'José Núñez', 'login': 'jose.nunez@example.com',
        })
        self.assertEqual(user._signalwire_sip_username(), f'jose.nunez{user.id}')

    def test_sip_username_collapses_punctuation_and_symbols(self):
        user = self.env['res.users'].create({
            'name': "O'Brien & Sons, LLC!", 'login': 'obrien@example.com',
        })
        self.assertEqual(user._signalwire_sip_username(), f'o.brien.sons.llc{user.id}')

    def test_sip_username_falls_back_to_plain_user_when_nothing_slugifiable_remains(self):
        # A non-empty name that's still entirely punctuation/symbols -
        # required=True on the name field means it can't be truly
        # blank, but this exercises the same "nothing survived
        # slugification" fallback path.
        user = self.env['res.users'].create({
            'name': '!@#$%', 'login': 'symbolname@example.com',
        })
        self.assertEqual(user._signalwire_sip_username(), f'user{user.id}')

    def test_sip_username_is_unique_per_user_even_with_identical_names(self):
        jane1 = self.env['res.users'].create({
            'name': 'Jane Smith', 'login': 'jane.smith1@example.com',
        })
        jane2 = self.env['res.users'].create({
            'name': 'Jane Smith', 'login': 'jane.smith2@example.com',
        })
        self.assertNotEqual(
            jane1._signalwire_sip_username(), jane2._signalwire_sip_username())

    def test_provision_creates_the_pbx_if_missing(self):
        self.signalwire_client.relay_post.return_value = {
            'id': 'ep-abc', 'username': f'user{self.user.id}',
        }
        self.assertFalse(self.env['voip.pbx'].search([('name', '=', 'Test SignalWire')]))

        self.user.action_provision_signalwire_sip()

        self.assertTrue(self.env['voip.pbx'].search([('name', '=', 'Test SignalWire')]))

    def test_provision_reuses_an_existing_pbx(self):
        pbx = self.server.action_setup_click2call()
        self.signalwire_client.relay_post.return_value = {
            'id': 'ep-abc', 'username': f'user{self.user.id}',
        }

        self.user.action_provision_signalwire_sip()

        self.assertEqual(self.user.voip_pbx_id, pbx)

    def test_provision_twice_raises(self):
        self.signalwire_client.relay_post.return_value = {
            'id': 'ep-abc', 'username': f'user{self.user.id}',
        }
        self.user.action_provision_signalwire_sip()

        with self.assertRaises(UserError):
            self.user.action_provision_signalwire_sip()

    def test_release_calls_the_delete_endpoint_and_clears_fields(self):
        self.signalwire_client.relay_post.return_value = {
            'id': 'ep-abc', 'username': f'user{self.user.id}',
        }
        self.user.action_provision_signalwire_sip()

        self.user.action_release_signalwire_sip()

        self.signalwire_client.relay_delete.assert_called_once_with('endpoints/sip/ep-abc')
        self.assertFalse(self.user.signalwire_sip_endpoint_id)
        self.assertFalse(self.user.voip_username)
        self.assertFalse(self.user.voip_password)

    def test_release_without_provisioning_raises(self):
        with self.assertRaises(UserError):
            self.user.action_release_signalwire_sip()

    def test_get_turn_credentials_returns_false_when_unconfigured(self):
        self.assertFalse(self.user.get_signalwire_turn_credentials())

    def test_get_turn_credentials_delegates_to_the_configured_server(self):
        self.server.write({'turn_host': '203.0.113.4:3478', 'turn_secret': 'sekrit'})

        result = self.user.get_signalwire_turn_credentials()

        self.assertEqual(
            result['urls'],
            ['turn:203.0.113.4:3478?transport=udp', 'turn:203.0.113.4:3478?transport=tcp'])

    def test_get_turn_credentials_works_for_a_user_without_server_access(self):
        # A plain softphone user shouldn't need (and per turn_secret's
        # own groups="base.group_system" shouldn't have) read access
        # to the server record - the method must still work via sudo().
        self.server.write({'turn_host': '203.0.113.4:3478', 'turn_secret': 'sekrit'})
        plain_user = self.env['res.users'].create({
            'name': 'Plain Agent', 'login': 'plain.agent@example.com',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])],
        })

        result = plain_user.with_user(plain_user).get_signalwire_turn_credentials()

        self.assertTrue(result)

    def test_search_colleagues_only_returns_provisioned_users_excluding_self(self):
        self.user.voip_username = 'user_jane'
        no_softphone = self.env['res.users'].create({
            'name': 'No Phone', 'login': 'no.phone@example.com'})

        result = self.user.with_user(self.user).search_signalwire_colleagues('')

        names = [c['name'] for c in result]
        self.assertNotIn(self.user.name, names)
        self.assertNotIn(no_softphone.name, names)

    def test_search_colleagues_filters_by_query_and_company(self):
        self.user.voip_username = 'user_jane'
        other_company = self.env['res.company'].create({'name': 'Other Co'})
        outside_user = self.env['res.users'].create({
            'name': 'Outsider', 'login': 'outsider4@example.com',
            'voip_username': 'user_outsider',
            'company_ids': [(6, 0, [other_company.id])],
            'company_id': other_company.id,
        })

        result = self.env['res.users'].search_signalwire_colleagues('jane')

        names = [c['name'] for c in result]
        self.assertIn('Jane Agent', names)
        self.assertNotIn(outside_user.name, names)

    def test_plain_user_can_self_write_voicemail_preferences(self):
        # Real, pre-existing gap caught while adding
        # signalwire_call_state: none of this module's own fields
        # were ever added to res.users' own SELF_WRITEABLE_FIELDS -
        # a plain (non-admin) user editing their own record was
        # always rejected with a real AccessError, contradicting the
        # module's own "self-service, not admin-only" documentation.
        plain_user = self.env['res.users'].create({
            'name': 'Plain Agent 2', 'login': 'plain.agent2@example.com'})

        plain_user.with_user(plain_user).signalwire_voicemail_enabled = False
        plain_user.with_user(plain_user).signalwire_voicemail_transcribe = False
        plain_user.with_user(plain_user).signalwire_call_state = 'on_call'

        self.assertFalse(plain_user.signalwire_voicemail_enabled)
        self.assertFalse(plain_user.signalwire_voicemail_transcribe)
        self.assertEqual(plain_user.signalwire_call_state, 'on_call')

    def test_set_signalwire_call_state_writes_the_calling_users_own_state(self):
        plain_user = self.env['res.users'].create({
            'name': 'Plain Agent 3', 'login': 'plain.agent3@example.com'})

        plain_user.with_user(plain_user).set_signalwire_call_state('ringing')

        self.assertEqual(plain_user.signalwire_call_state, 'ringing')

    def test_set_signalwire_call_state_ignores_an_invalid_value(self):
        self.user.signalwire_call_state = 'idle'

        self.user.set_signalwire_call_state('not_a_real_state')

        self.assertEqual(self.user.signalwire_call_state, 'idle')
