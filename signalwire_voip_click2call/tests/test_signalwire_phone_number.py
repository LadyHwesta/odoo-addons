# -*- coding: utf-8 -*-
from datetime import datetime
from unittest.mock import MagicMock, patch

from odoo.exceptions import AccessError, UserError
from odoo.fields import Datetime
from odoo.tests.common import HttpCase, TransactionCase, tagged


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

    def test_configure_routing_confirms_success_with_a_notification(self):
        # Regression test: this used to return nothing at all on
        # success - no error, no visible change on screen, so clicking
        # the button looked like it "did nothing" even when it worked.
        self.user.write({'voip_username': f'user{self.user.id}'})
        self.number.assigned_user_id = self.user

        result = self.number.action_configure_inbound_routing()

        self.assertEqual(result['type'], 'ir.actions.client')
        self.assertEqual(result['tag'], 'display_notification')
        self.assertEqual(result['params']['type'], 'success')
        self.assertIn(self.number.name, result['params']['message'])
        self.assertTrue(self.number.inbound_connected)

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

    def test_effective_route_after_hours_straight_to_user_voicemail(self):
        calendar = self.env['resource.calendar'].create({
            'name': 'Test Hours', 'tz': 'UTC',
            'attendance_ids': [(0, 0, {
                'name': 'All Day Monday', 'dayofweek': '0',
                'hour_from': 0.0, 'hour_to': 24.0, 'day_period': 'morning',
            })],
        })
        after_hours_user = self.env['res.users'].create({
            'name': 'Night Owl', 'login': 'night.owl.vm@example.com'})
        self.number.write({
            'route_type': 'user', 'assigned_user_id': self.user.id,
            'calendar_id': calendar.id,
            'after_hours_route_type': 'user_voicemail',
            'after_hours_user_id': after_hours_user.id,
        })
        sunday = Datetime.to_string(datetime(2026, 9, 20, 12, 0, 0))  # a real Sunday

        with patch('odoo.fields.Datetime.now', return_value=Datetime.from_string(sunday)):
            route_type, target = self.number._effective_route()

        self.assertEqual((route_type, target), ('user_voicemail', after_hours_user))

    def test_effective_route_after_hours_straight_to_group_voicemail(self):
        calendar = self.env['resource.calendar'].create({
            'name': 'Test Hours', 'tz': 'UTC',
            'attendance_ids': [(0, 0, {
                'name': 'All Day Monday', 'dayofweek': '0',
                'hour_from': 0.0, 'hour_to': 24.0, 'day_period': 'morning',
            })],
        })
        group = self.env['signalwire.call.group'].create({'name': 'Sales'})
        self.number.write({
            'route_type': 'user', 'assigned_user_id': self.user.id,
            'calendar_id': calendar.id,
            'after_hours_route_type': 'group_voicemail',
            'after_hours_call_group_id': group.id,
        })
        sunday = Datetime.to_string(datetime(2026, 9, 20, 12, 0, 0))  # a real Sunday

        with patch('odoo.fields.Datetime.now', return_value=Datetime.from_string(sunday)):
            route_type, target = self.number._effective_route()

        self.assertEqual((route_type, target), ('group_voicemail', group))

    def test_effective_route_via_ivr_menu(self):
        menu = self.env['signalwire.ivr.menu'].create({
            'name': 'Main Menu', 'greeting_text': 'Press 1 for sales.'})
        self.number.write({'route_type': 'ivr', 'ivr_menu_id': menu.id})

        route_type, target = self.number._effective_route()

        self.assertEqual((route_type, target), ('ivr', menu))

    def test_list_shows_where_calls_go_and_whether_connected(self):
        view = self.env['signalwire.phone_number'].get_view(
            view_id=self.env.ref('signalwire_voip.view_signalwire_phone_number_list').id,
            view_type='list')
        self.assertIn('call_flow_summary', view['arch'])
        self.assertIn('inbound_connected', view['arch'])
        self.assertNotIn('action_configure_inbound_routing', view['arch'])

    def test_form_view_shows_after_hours_user_field_for_voicemail_route(self):
        view = self.env['signalwire.phone_number'].get_view(
            view_id=self.env.ref(
                'signalwire_voip.view_signalwire_phone_number_form').id,
            view_type='form')
        self.assertIn(
            "after_hours_route_type not in ('user', 'user_voicemail')", view['arch'])
        self.assertIn(
            "after_hours_route_type not in ('group', 'group_voicemail')", view['arch'])

    def test_assigned_user_from_a_different_company_is_rejected(self):
        other_company = self.env['res.company'].create({'name': 'Other Co'})
        outside_user = self.env['res.users'].create({
            'name': 'Outsider', 'login': 'outsider3@example.com',
            'company_ids': [(6, 0, [other_company.id])],
            'company_id': other_company.id,
        })
        with self.assertRaises(UserError):
            self.number.assigned_user_id = outside_user

    # --- Closing early, the plain-English summary, connecting ---------------

    def _business_hours_number(self):
        calendar = self.env['resource.calendar'].create({
            'name': 'Shop Hours', 'tz': 'UTC',
            'attendance_ids': [(0, 0, {
                'name': 'All Day Monday', 'dayofweek': '0',
                'hour_from': 0.0, 'hour_to': 24.0, 'day_period': 'morning',
            })],
        })
        group = self.env['signalwire.call.group'].create({'name': 'Front Desk'})
        self.number.write({
            'route_type': 'group', 'call_group_id': group.id,
            'calendar_id': calendar.id,
            'after_hours_route_type': 'user_voicemail', 'after_hours_user_id': self.user.id,
        })
        return group

    def test_closing_early_uses_the_after_hours_route_until_reopened(self):
        group = self._business_hours_number()
        monday_noon = datetime(2026, 9, 21, 12, 0, 0)
        with patch('odoo.fields.Datetime.now', return_value=monday_noon):
            self.assertEqual(self.number._effective_route(), ('group', group))
            self.number.company_id.action_signalwire_close_today()
            self.assertEqual(self.number._effective_route(), ('user_voicemail', self.user))
            self.number.company_id.action_signalwire_reopen()
            self.assertEqual(self.number._effective_route(), ('group', group))

    def test_closing_early_reopens_by_itself_overnight(self):
        group = self._business_hours_number()
        company = self.number.company_id
        with patch('odoo.fields.Datetime.now', return_value=datetime(2026, 9, 21, 22, 0, 0)):
            company.with_context(tz='America/Los_Angeles').action_signalwire_close_today()
        # 15:00 PDT Monday -> reopens 04:00 PDT Tuesday = 11:00 UTC
        self.assertEqual(company.signalwire_closed_until, datetime(2026, 9, 22, 11, 0, 0))
        with patch('odoo.fields.Datetime.now', return_value=datetime(2026, 9, 22, 10, 59, 0)):
            self.assertTrue(company._signalwire_closed_until())
        with patch('odoo.fields.Datetime.now', return_value=datetime(2026, 9, 28, 12, 0, 0)):
            self.assertFalse(company._signalwire_closed_until())
            self.assertEqual(self.number._effective_route(), ('group', group))

    def test_numbers_without_business_hours_ignore_closing_early(self):
        self.number.write({'route_type': 'user', 'assigned_user_id': self.user.id})
        self.number.company_id.action_signalwire_close_today()
        self.assertEqual(self.number._effective_route(), ('user', self.user))

    def test_summary_says_where_calls_go_in_plain_words(self):
        self.assertEqual(self.number.call_flow_summary,
                         'Calls go nowhere yet (choose where below), at any time.')
        self._business_hours_number()
        self.number.invalidate_recordset(['call_flow_summary'])
        self.assertEqual(
            self.number.call_flow_summary,
            "During Shop Hours, calls ring the Front Desk group. Outside those hours, "
            "calls go straight to Jane Agent's voicemail.")
        self.number.company_id.action_signalwire_close_today()
        self.number.invalidate_recordset(['call_flow_summary', 'company_closed_early'])
        self.assertTrue(self.number.call_flow_summary.startswith('Closed early until '))
        self.assertTrue(self.number.company_closed_early)

    def test_connecting_checks_the_business_hours_route_even_at_night(self):
        self._business_hours_number()
        self.number.company_id.action_signalwire_close_today()
        with self.assertRaisesRegex(UserError, 'no members'):
            self.number.action_configure_inbound_routing()
        self.assertFalse(self.number.inbound_connected)


@tagged('post_install', '-at_install')
class TestOpenStatusAndExtensions(TransactionCase):

    def test_receptionist_can_close_and_reopen_their_company(self):
        receptionist = self.env['res.users'].create({
            'name': 'Rita', 'login': 'rita.reception@example.com',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id,
                                  self.env.ref('signalwire_voip_click2call.group_signalwire_receptionist').id])]})
        Wizard = self.env['signalwire.open.status'].with_user(receptionist)
        wizard = Wizard.create({})
        self.assertFalse(wizard.is_closed)
        wizard.action_close_today()
        self.assertTrue(self.env.company._signalwire_closed_until())
        self.assertTrue(Wizard.create({}).is_closed)
        Wizard.create({}).action_reopen()
        self.assertFalse(self.env.company.signalwire_closed_until)

    def test_nobody_can_close_another_companys_phones(self):
        other = self.env['res.company'].create({'name': 'Elsewhere'})
        receptionist = self.env['res.users'].create({
            'name': 'Rita', 'login': 'rita2.reception@example.com',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id,
                                  self.env.ref('signalwire_voip_click2call.group_signalwire_receptionist').id])]})
        wizard = self.env['signalwire.open.status'].create({'company_id': other.id}).with_user(receptionist)
        with self.assertRaises(AccessError):
            wizard.action_close_today()
        self.assertFalse(other.signalwire_closed_until)

    def test_extensions_list_shows_internal_people_and_their_phone_setup(self):
        action = self.env.ref('signalwire_voip_click2call.action_signalwire_extensions')
        user = self.env['res.users'].create({'name': 'Desk Person', 'login': 'desk.person@example.com'})
        found = self.env['res.users'].search(eval(action.domain))
        self.assertIn(user, found)
        self.assertNotIn(self.env.ref('base.public_user'), found)
        self.assertFalse(user.signalwire_has_softphone)
        user.signalwire_sip_endpoint_id = 'ep-1'
        self.assertTrue(user.signalwire_has_softphone)
        for view in ('view_users_signalwire_extension_list', 'view_users_signalwire_extension_form'):
            self.env['res.users'].get_view(
                view_id=self.env.ref(f'signalwire_voip_click2call.{view}').id)

    def test_menus_are_grouped_into_sections(self):
        phones = self.env.ref('signalwire_voip.menu_signalwire_section_phones')
        call_flow = self.env.ref('signalwire_voip.menu_signalwire_section_call_flow')
        self.assertEqual(self.env.ref('signalwire_voip_click2call.menu_signalwire_voicemail').parent_id, phones)
        self.assertEqual(self.env.ref('signalwire_voip_click2call.menu_signalwire_call_group').parent_id, call_flow)
        self.assertEqual(self.env.ref('signalwire_voip.menu_signalwire_phone_numbers').parent_id, call_flow)

    def test_opening_the_app_shows_a_page_not_a_pop_up(self):
        root = self.env.ref('signalwire_voip.menu_signalwire_root')
        self.assertEqual(root.action, self.env.ref('signalwire_voip.action_signalwire_dashboard'))
        self.assertEqual(root.action.type, 'ir.actions.client')


@tagged('post_install', '-at_install')
class TestVoipDashboardRouting(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        server = cls.env['signalwire.server'].create({
            'name': 'Test SignalWire', 'space': 'example.signalwire.com',
            'sip_domain': 'example-abc123.sip.signalwire.com',
            'project_id': 'pid123', 'api_token': 'tok456'})
        sub = cls.env['signalwire.subproject'].create({
            'name': 'Office', 'server_id': server.id, 'account_sid': 'sub-abc', 'state': 'active'})
        cls.user = cls.env['res.users'].create({
            'name': 'Jane Agent', 'login': 'jane.dash@example.com',
            'signalwire_sip_endpoint_id': 'ep-1'})
        cls.number = cls.env['signalwire.phone_number'].create({
            'name': '+17075550100', 'sid': 'pn-1', 'subproject_id': sub.id,
            'assigned_user_id': cls.user.id})

    def setUp(self):
        super().setUp()
        client = MagicMock()
        client.compat_get.return_value = {'calls': []}
        patcher = patch('odoo.addons.signalwire_voip.models.signalwire_server.'
                        'SignalWireServer._get_client', return_value=client)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _data(self, user=None):
        Dashboard = self.env['signalwire.dashboard']
        if user:
            Dashboard = Dashboard.with_user(user)
        return Dashboard.get_dashboard_data(refresh=True)

    def test_numbers_show_where_calls_go_now_and_need_connecting(self):
        row = next(t for t in self._data()['tables'] if t['key'] == 'numbers')['rows'][0]
        self.assertEqual(row['cells'][1], 'Ring Jane Agent')
        self.assertEqual(row['tone'], 'warning', "not connected yet")
        self.number.inbound_connected = True
        row = next(t for t in self._data()['tables'] if t['key'] == 'numbers')['rows'][0]
        self.assertEqual(row['tone'], 'ok')

    def test_extensions_table_and_voicemail_tile(self):
        self.env['signalwire.voicemail'].create({
            'phone_number_id': self.number.id, 'user_id': self.user.id,
            'from_number': '+15550001111'})
        data = self._data()
        extensions = next(t for t in data['tables'] if t['key'] == 'extensions')
        self.assertEqual(extensions['rows'][0]['cells'][:2], ['Jane Agent', 'Available'])
        self.assertEqual(extensions['rows'][0]['open']['view_id'],
                         self.env.ref('signalwire_voip_click2call.view_users_signalwire_extension_form').id)
        voicemail = next(t for t in data['tiles'] if t['key'] == 'voicemail')
        self.assertEqual(voicemail['value'], 1)
        self.assertEqual(voicemail['tone'], 'warning')

    def test_open_closed_banner_and_switch(self):
        data = self._data()
        self.assertFalse(data['status']['closed'])
        self.assertTrue(data['status']['can_toggle'])
        self.env['signalwire.dashboard'].set_phones_closed(True)
        self.assertTrue(self._data()['status']['closed'])
        self.env['signalwire.dashboard'].set_phones_closed(False)
        self.assertFalse(self.env.company.signalwire_closed_until)

    def test_ordinary_staff_see_the_banner_but_cannot_switch(self):
        staff = self.env['res.users'].create({
            'name': 'Sam', 'login': 'sam.dash@example.com',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])]})
        data = self._data(staff)
        self.assertFalse(data['status']['can_toggle'])
        self.assertNotIn('live_calls', [t['key'] for t in data['tiles']])
        with self.assertRaises(AccessError):
            self.env['signalwire.dashboard'].with_user(staff).set_phones_closed(True)


@tagged('post_install', '-at_install')
class TestVoipDashboardPage(HttpCase):
    """The dashboard page itself, in a real browser: it loads, draws the
    open/closed banner, tiles and tables, and the switch works."""

    def test_dashboard_page_draws_and_switches(self):
        server = self.env['signalwire.server'].create({
            'name': 'Test SignalWire', 'space': 'example.signalwire.com',
            'sip_domain': 'example-abc123.sip.signalwire.com',
            'project_id': 'pid123', 'api_token': 'tok456'})
        sub = self.env['signalwire.subproject'].create({
            'name': 'Office', 'server_id': server.id, 'account_sid': 'sub-abc', 'state': 'active'})
        self.env['signalwire.phone_number'].create({
            'name': '+17075550100', 'sid': 'pn-1', 'subproject_id': sub.id})
        client = MagicMock()
        client.compat_get.return_value = {'calls': []}
        code = """
            const wait = (ms) => new Promise((r) => setTimeout(r, ms));
            const page = document.querySelector('.o_signalwire_dashboard');
            if (!page.querySelector('.o_signalwire_tile')) { throw new Error('no tiles'); }
            if (!page.textContent.includes('+17075550100')) { throw new Error('no numbers table'); }
            const close = [...page.querySelectorAll('button')].find(b => b.textContent.includes('Close for the Rest of Today'));
            if (!close) { throw new Error('no close button'); }
            close.click();
            for (let i = 0; i < 50 && !page.textContent.includes('Reopen Now'); i++) { await wait(100); }
            if (!page.textContent.includes('Reopen Now')) { throw new Error('switch did not take'); }
            console.log('test successful');
        """
        with patch('odoo.addons.signalwire_voip.models.signalwire_server.'
                   'SignalWireServer._get_client', return_value=client):
            self.browser_js('/odoo/action-signalwire_voip.action_signalwire_dashboard',
                            '(async () => {' + code + '})().catch((e) => console.error(e.message))',
                            ready="!!document.querySelector('.o_signalwire_dashboard h4')",
                            login='admin', timeout=120)
        self.assertTrue(self.env.company.signalwire_closed_until)
