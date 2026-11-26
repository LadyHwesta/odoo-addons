# -*- coding: utf-8 -*-
from datetime import timedelta
from odoo import fields
from odoo.exceptions import AccessError, ValidationError
from odoo.tests.common import TransactionCase, new_test_user, tagged


@tagged('post_install', '-at_install')
class TestMyDay(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = new_test_user(cls.env, 'day.user', groups='base.group_user', tz='UTC', name='Robin Day')
        cls.MyDay = cls.env['my.day'].with_user(cls.user)
        cls.today = fields.Date.context_today(cls.MyDay)

    def _section(self, day, key):
        return next((s for s in day['sections'] if s['key'] == key), None)

    def test_header_and_columns(self):
        day = self.MyDay.get_day()
        self.assertTrue(day['greeting'].endswith('Robin'))
        self.assertTrue(day['date'])
        self.assertIn('plan', {s['column'] for s in day['sections']})
        self.assertEqual(self._section(day, 'todo')['column'], 'plan')

    def test_schedule_lists_todays_meetings_only(self):
        now = fields.Datetime.now()
        Event = self.env['calendar.event']
        Event.create({'name': 'Stand-up', 'start': now, 'stop': now + timedelta(minutes=30),
                      'partner_ids': [(6, 0, [self.user.partner_id.id])]})
        Event.create({'name': 'Next week', 'start': now + timedelta(days=7), 'stop': now + timedelta(days=7, hours=1),
                      'partner_ids': [(6, 0, [self.user.partner_id.id])]})
        Event.create({'name': 'Not mine', 'start': now, 'stop': now + timedelta(hours=1)})
        Event.create({'name': 'Invoice day', 'allday': True, 'start_date': self.today, 'stop_date': self.today,
                      'partner_ids': [(6, 0, [self.user.partner_id.id])]})
        names = [i['name'] for i in self._section(self.MyDay.get_day(), 'schedule')['items']]
        self.assertEqual(names, ['Invoice day', 'Stand-up'])

    def test_todos_overdue_and_today_with_done(self):
        partner = self.env['res.partner'].create({'name': 'Call me back'})
        todo = self.env.ref('mail.mail_activity_data_todo')
        Activity = self.env['mail.activity']
        common = {'res_model_id': self.env['ir.model']._get_id('res.partner'), 'res_id': partner.id,
                  'activity_type_id': todo.id, 'user_id': self.user.id}
        late = Activity.create({**common, 'summary': 'Late one', 'date_deadline': self.today - timedelta(days=2)})
        Activity.create({**common, 'summary': 'Today one', 'date_deadline': self.today})
        Activity.create({**common, 'summary': 'Thursday', 'date_deadline': self.today + timedelta(days=3)})
        section = self._section(self.MyDay.get_day(), 'todo')
        self.assertEqual([i['name'] for i in section['items']], ['Late one', 'Today one'])
        self.assertTrue(section['items'][0]['overdue'])
        self.assertEqual(section['items'][0]['record'], {'model': 'res.partner', 'id': partner.id})
        self.assertEqual(section['items'][0]['buttons'][0]['method'], 'action_feedback')
        self.assertIn('1', section['note'])
        late.with_user(self.user).action_feedback()
        names = [i['name'] for i in self._section(self.MyDay.get_day(), 'todo')['items']]
        self.assertEqual(names, ['Today one'])

    def test_sections_need_the_app_and_the_rights(self):
        day = self.MyDay.get_day()
        if 'account.move' in self.env:
            self.assertIsNone(self._section(day, 'money'), "only people who handle invoices see money")

    def test_start_on_my_day(self):
        action = self.env.ref('my_day.action_my_day')
        prefs = self.user.with_user(self.user)
        prefs.write({'my_day_home': True})
        self.assertEqual(self.user.action_id.id, action.id)
        self.assertTrue(self.user.my_day_home)
        prefs.write({'my_day_home': False})
        self.assertFalse(self.user.action_id)

    def test_tasks_due_this_week(self):
        if 'project.task' not in self.env:
            self.skipTest('project not installed')
        self.user.group_ids |= self.env.ref('project.group_project_user')
        project = self.env['project.project'].create({'name': 'Gigs'})
        Task = self.env['project.task']
        now = fields.Datetime.now()
        Task.create({'name': 'Overdue task', 'project_id': project.id, 'user_ids': [(6, 0, [self.user.id])],
                     'date_deadline': now - timedelta(days=3)})
        Task.create({'name': 'Friday task', 'project_id': project.id, 'user_ids': [(6, 0, [self.user.id])],
                     'date_deadline': now + timedelta(days=3)})
        Task.create({'name': 'Next month', 'project_id': project.id, 'user_ids': [(6, 0, [self.user.id])],
                     'date_deadline': now + timedelta(days=30)})
        Task.create({'name': 'Someone else', 'project_id': project.id, 'date_deadline': now})
        section = self._section(self.MyDay.get_day(), 'tasks')
        self.assertEqual([i['name'] for i in section['items']], ['Overdue task', 'Friday task'])
        self.assertTrue(section['items'][0]['overdue'])


    def test_background_built_in_own_picture_and_none(self):
        day = self.MyDay.get_day()
        self.assertEqual(day['background'], '')
        self.assertEqual(len(day['backgrounds']), 6)
        url = self.MyDay.set_background('lagoon')
        self.assertEqual(url, '/my_day/static/src/img/bg_lagoon.jpg')
        self.assertEqual(self.MyDay.get_day()['background'], url)
        png = ('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk'
               '+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==')
        url = self.MyDay.set_background('custom', png)
        self.assertIn(f'/web/image/res.users/{self.user.id}/my_day_background_image', url)
        self.assertEqual(self.MyDay.set_background('none'), '')

    def test_sections_have_their_colour_keys(self):
        keys = [key for _column, key in self.env['my.day']._my_day_sections()]
        for key in ('sms', 'security', 'leads'):
            self.assertIn(key, keys)

    def test_leads_mine_first_then_new_in_my_team(self):
        if 'crm.lead' not in self.env:
            self.skipTest('CRM not installed')
        self.user.group_ids |= self.env.ref('sales_team.group_sale_salesman')
        team = self.env['crm.team'].create({'name': 'Gig sales'})
        self.env['crm.team.member'].create({'crm_team_id': team.id, 'user_id': self.user.id})
        Lead = self.env['crm.lead']
        todo = self.env.ref('mail.mail_activity_data_todo')
        later = Lead.create({'name': 'Wedding in June', 'user_id': self.user.id, 'team_id': team.id})
        urgent = Lead.create({'name': 'Corporate party', 'user_id': self.user.id, 'team_id': team.id})
        urgent.activity_schedule(activity_type_id=todo.id, date_deadline=self.today - timedelta(days=1),
                                 user_id=self.user.id)
        fresh = Lead.create({'name': 'Website enquiry', 'user_id': False, 'team_id': team.id})
        Lead.create({'name': 'Other team', 'user_id': False})
        Lead.create({'name': 'Gone quiet', 'user_id': self.user.id, 'team_id': team.id, 'active': False})
        parked = self.env['crm.stage'].create({'name': 'Archived', 'fold': True, 'sequence': 90})
        Lead.create({'name': 'Parked', 'user_id': self.user.id, 'team_id': team.id, 'stage_id': parked.id})
        won = self.env['crm.stage'].search([('is_won', '=', True)], limit=1)
        Lead.create({'name': 'Signed', 'user_id': self.user.id, 'team_id': team.id, 'stage_id': won.id})
        section = self._section(self.MyDay.get_day(), 'leads')
        names = [i['name'] for i in section['items']]
        self.assertEqual(names, ['Corporate party', 'Wedding in June', 'Website enquiry'])
        self.assertTrue(section['items'][0]['overdue'])
        self.assertEqual(section['items'][2]['badge'], 'Unassigned')
        self.assertIn('1', section['note'])
        self.env['my.day'].with_user(self.user).browse(fresh.id).take_lead()
        self.assertEqual(fresh.user_id, self.user)
        self.assertNotIn('Unassigned', [i.get('badge') for i in self._section(self.MyDay.get_day(), 'leads')['items']])
        self.assertTrue(later)

    def test_threat_status_only_for_security_officers(self):
        if 'security.event' not in self.env:
            self.skipTest('login protection not installed')
        self.assertIsNone(self._section(self.MyDay.get_day(), 'security'))
        self.user.group_ids |= self.env.ref('security_auth_guard.group_security_officer')
        Event = self.env['security.event'].sudo()
        Event.search([('state', '=', 'new')]).write({'state': 'reviewed'})
        section = self._section(self.MyDay.get_day(), 'security')
        self.assertEqual(section['status']['level'], 'ok')
        # Blocks that worked are counted, never listed for review.
        Event.create([{'event_type': 'probe_blocked', 'severity': 'info', 'source_ip': '203.0.113.8'}
                      for _i in range(5)])
        section = self._section(self.MyDay.get_day(), 'security')
        self.assertEqual(section['status']['level'], 'ok')
        self.assertFalse(section['items'])
        self.assertIn("5 automatic blocks this week", section['status']['facts'])
        Event.create({'event_type': 'login_cooldown', 'severity': 'warning', 'source_ip': '203.0.113.9'})
        Event.create({'event_type': 'anomaly', 'severity': 'critical', 'detail': 'Bank account changed'})
        section = self._section(self.MyDay.get_day(), 'security')
        self.assertEqual(section['status']['level'], 'critical')
        self.assertEqual(len(section['items']), 2)
        self.assertTrue(section['items'][0]['overdue'], "critical first")
        self.assertEqual(section['items'][0]['buttons'][0]['method'], 'action_mark_reviewed')

    def test_texts_mine_and_unassigned_to_answer(self):
        if 'signalwire.sms' not in self.env or 'handled' not in self.env['signalwire.sms']._fields:
            self.skipTest('texting not installed')
        server = self.env['signalwire.server'].create({
            'name': 'Test', 'space': 'example.signalwire.com', 'project_id': 'p', 'api_token': 't'})
        sub = self.env['signalwire.subproject'].create({
            'name': 'Team', 'server_id': server.id, 'account_sid': 's', 'state': 'active'})
        number = self.env['signalwire.phone_number'].create({'name': '+12084449665', 'sid': 'pn', 'subproject_id': sub.id})
        other = new_test_user(self.env, 'day.other', groups='base.group_user')
        Sms = self.env['signalwire.sms']
        common = {'phone_number_id': number.id, 'direction': 'inbound', 'from_number': '+15556102107',
                  'to_number': '+12084449665', 'state': 'received'}
        Sms.create({**common, 'body': 'Mine', 'user_id': self.user.id})
        Sms.create({**common, 'body': 'Nobody yet', 'user_id': False})
        Sms.create({**common, 'body': 'Theirs', 'user_id': other.id})
        Sms.create({**common, 'body': 'Answered', 'user_id': self.user.id, 'handled': True})
        Sms.create({**common, 'body': 'We sent this', 'direction': 'outbound'})
        section = self._section(self.MyDay.get_day(), 'sms')
        self.assertEqual(sorted(i['meta'] for i in section['items']), ['Mine', 'Nobody yet'])
        nobody = next(i for i in section['items'] if i['meta'] == 'Nobody yet')
        self.assertEqual([b['method'] for b in nobody['buttons']], ['action_take', 'action_reply', 'action_mark_handled'])


@tagged('post_install', '-at_install')
class TestMyDayCompanies(TransactionCase):
    """Money per company, within the companies selected in the switcher."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if 'account.move' not in cls.env:
            return
        cls.main = cls.env.company
        cls.branch = cls.env['res.company'].create({'name': 'North Branch', 'parent_id': cls.main.id})
        cls.accountant = new_test_user(
            cls.env, 'day.accountant', tz='UTC',
            groups='base.group_user,account.group_account_invoice',
            company_ids=[(6, 0, [cls.main.id, cls.branch.id])], company_id=cls.main.id)

    def _overdue_invoice(self, company, amount):
        partner = self.env['res.partner'].create({'name': f'Late payer {company.name}'})
        move = self.env['account.move'].with_company(company).create({
            'move_type': 'out_invoice', 'partner_id': partner.id, 'company_id': company.id,
            'invoice_date': fields.Date.today() - timedelta(days=40),
            'invoice_date_due': fields.Date.today() - timedelta(days=10),
            'invoice_line_ids': [(0, 0, {'name': 'Gig', 'quantity': 1, 'price_unit': amount, 'tax_ids': [(5, 0, 0)]})],
        })
        move.action_post()
        return move

    def test_money_per_company_in_the_switcher(self):
        if 'account.move' not in self.env:
            self.skipTest('accounting not installed')
        if not self.env['account.journal'].search([('type', '=', 'sale'), ('company_id', '=', self.main.id)], limit=1):
            self.skipTest('no chart of accounts')
        self._overdue_invoice(self.main, 300)
        branch_has_books = self.env['account.journal'].search(
            [('type', '=', 'sale'), ('company_id', '=', self.branch.id)], limit=1)
        both = self.env['my.day'].with_user(self.accountant).with_context(
            allowed_company_ids=[self.main.id, self.branch.id])
        day = both.get_day()
        self.assertEqual(len(day['companies']), 2)
        self.assertTrue(any(c['branch'] for c in day['companies']))
        money = next(s for s in day['sections'] if s['key'] == 'money')
        overdue = [i for i in money['items'] if i['overdue']]
        self.assertTrue(overdue)
        self.assertEqual(overdue[0]['company'], self.main.name)  # marked when several are shown
        self.assertIn('300', overdue[0]['when'])
        only_branch = self.env['my.day'].with_user(self.accountant).with_context(
            allowed_company_ids=[self.branch.id])
        money = next(s for s in only_branch.get_day()['sections'] if s['key'] == 'money')
        self.assertFalse([i for i in money['items'] if i['overdue']] if not branch_has_books else
                         [i for i in money['items'] if i['company'] == self.main.name])


@tagged('post_install', '-at_install')
class TestMyDaySections(TransactionCase):
    """The phone and helpdesk sections, when those apps are installed."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.admin = cls.env.ref('base.user_admin')
        cls.admin.tz = 'UTC'
        cls.MyDay = cls.env['my.day'].with_user(cls.admin)

    def _section(self, key, **kw):
        return next((s for s in self.MyDay.get_day(**kw)['sections'] if s['key'] == key), None)

    def test_phone_voicemails_and_callbacks(self):
        if 'signalwire.voicemail' not in self.env:
            self.skipTest('phone modules not installed')
        server = self.env['signalwire.server'].create({
            'name': 'S', 'space': 'x.signalwire.com', 'project_id': 'p', 'api_token': 't'})
        sub = self.env['signalwire.subproject'].create({
            'name': 'Sub', 'server_id': server.id, 'account_sid': 'sub-x', 'state': 'active'})
        number = self.env['signalwire.phone_number'].create({'name': '+12085550001', 'sid': 'pn-1', 'subproject_id': sub.id})
        group = self.env['signalwire.call.group'].create({'name': 'Front desk', 'member_ids': [(6, 0, [self.admin.id])]})
        other = self.env['res.users'].create({'name': 'Someone Else', 'login': 'else.myday@example.com'})
        caller = self.env['res.partner'].create({'name': 'Carla Caller'})
        VM = self.env['signalwire.voicemail']
        mine = VM.create({'phone_number_id': number.id, 'user_id': self.admin.id, 'from_number': '+15551230000',
                          'partner_id': caller.id, 'transcription_text': 'Hi, calling about Saturday.'})
        VM.create({'phone_number_id': number.id, 'call_group_id': group.id, 'from_number': '+15559990000'})
        VM.create({'phone_number_id': number.id, 'user_id': self.admin.id, 'from_number': '+1555', 'is_read': True})
        VM.create({'phone_number_id': number.id, 'user_id': other.id, 'from_number': '+15558887777'})
        self.env['signalwire.callback_request'].create({
            'phone_number': '+15554443333', 'target_user_id': self.admin.id, 'note': 'Wants a quote'})
        section = self._section('phone')
        names = [i['name'] for i in section['items']]
        self.assertIn('Voicemail from Carla Caller', names)
        self.assertIn('Voicemail from +15559990000', names)  # my call group's box
        self.assertIn('Call back +15554443333', names)
        self.assertEqual(section['count'], 3)
        item = next(i for i in section['items'] if i['id'] == mine.id and i['model'] == 'signalwire.voicemail')
        self.assertIn('Saturday', item['meta'])
        self.assertEqual([b['method'] for b in item['buttons']], [False, 'action_mark_read'])
        self.assertEqual(item['buttons'][0]['dial'], '+15551230000')  # Call back dials the caller
        mine.with_user(self.admin).action_mark_read()
        self.assertEqual(self._section('phone')['count'], 2)

    def test_callbacks_open_what_theyre_about(self):
        if 'signalwire.callback_request' not in self.env:
            self.skipTest('phone modules not installed')
        contact = self.env['res.partner'].create({'name': 'Dana Contact'})
        about = self.env['res.partner'].create({'name': 'The Thing It Is About'})
        Callback = self.env['signalwire.callback_request']
        plain = Callback.create({'phone_number': '+15550001111', 'partner_id': contact.id,
                                 'target_user_id': self.admin.id, 'source': 'phone'})
        noted = Callback.create({'phone_number': '+15550002222', 'partner_id': contact.id,
                                 'target_user_id': self.admin.id, 'related_ref': f'res.partner,{about.id}'})
        items = {i['id']: i for i in self._section('phone')['items'] if i['model'] == 'signalwire.callback_request'}
        self.assertEqual(items[plain.id]['record'], {'model': 'res.partner', 'id': contact.id})
        self.assertEqual(items[noted.id]['record'], {'model': 'res.partner', 'id': about.id})
        self.assertIn('The Thing It Is About', items[noted.id]['meta'])
        self.assertEqual([b['method'] for b in items[plain.id]['buttons']], ['action_call_now', 'action_complete'])
        self.assertEqual(plain.with_user(self.admin).action_call_now(), '+15550001111')
        self.assertEqual(plain.state, 'completed')
        noted.with_user(self.admin).action_complete()
        self.assertFalse([i for i in self._section('phone')['items'] if i['model'] == 'signalwire.callback_request'])

    def test_helpdesk_tickets(self):
        if 'helpdesk.ticket' not in self.env:
            self.skipTest('helpdesk not installed')
        Ticket = self.env['helpdesk.ticket']
        team = self.env['helpdesk.ticket.team'].create({'name': 'Support', 'user_ids': [(6, 0, [self.admin.id])]})
        closed_stage = self.env['helpdesk.ticket.stage'].search([('closed', '=', True)], limit=1)
        Ticket.create({'name': 'Printer on fire', 'description': 'x', 'user_id': self.admin.id, 'team_id': team.id})
        Ticket.create({'name': 'Already fixed', 'description': 'x', 'user_id': self.admin.id,
                       'stage_id': closed_stage.id})
        Ticket.create({'name': 'Nobody yet', 'description': 'x', 'team_id': team.id, 'user_id': False})
        section = self._section('helpdesk')
        self.assertEqual([i['name'].split(' ', 1)[-1] for i in section['items']], ['Printer on fire'])
        self.assertIn('1', section['note'])  # one unassigned in my team

    def test_picking_a_company(self):
        branch = self.env['res.company'].create({'name': 'Picked Branch', 'parent_id': self.env.company.id})
        self.admin.company_ids |= branch
        MyDay = self.MyDay.with_context(allowed_company_ids=[self.env.company.id, branch.id])
        both = MyDay.get_day()
        self.assertTrue(all(c['on'] for c in both['companies']))
        only = MyDay.get_day(company_ids=[branch.id])
        self.assertEqual([c['name'] for c in only['companies'] if c['on']], ['Picked Branch'])
        self.assertEqual(len(only['companies']), 2, "the other company stays listed, to pick it again")
        stranger = self.env['res.company'].create({'name': 'Not In Switcher'})
        ignored = MyDay.get_day(company_ids=[stranger.id])
        self.assertTrue(all(c['on'] for c in ignored['companies']), "only switcher companies can be picked")


@tagged('post_install', '-at_install')
class TestMyDayChoices(TransactionCase):
    """Each person chooses their own sections and options (Preferences > My Day)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = new_test_user(cls.env, 'day.chooser', groups='base.group_user', tz='UTC', name='Sam Chooser')
        cls.other = new_test_user(cls.env, 'day.other2', groups='base.group_user', tz='UTC', name='Alex Other')
        cls.MyDay = cls.env['my.day'].with_user(cls.user)
        cls.today = fields.Date.context_today(cls.MyDay)
        partner = cls.env['res.partner'].create({'name': 'Somebody'})
        todo = cls.env.ref('mail.mail_activity_data_todo')
        common = {'res_model_id': cls.env['ir.model']._get_id('res.partner'), 'res_id': partner.id,
                  'activity_type_id': todo.id, 'user_id': cls.user.id}
        cls.env['mail.activity'].create([
            {**common, 'summary': f'Today {i}', 'date_deadline': cls.today} for i in range(5)])
        cls.env['mail.activity'].create(
            {**common, 'summary': 'In three days', 'date_deadline': cls.today + timedelta(days=3)})

    def _section(self, key):
        return next((s for s in self.MyDay.get_day()['sections'] if s['key'] == key), None)

    def _rows(self, user=None):
        return self.env['my.day.section.setting'].search([('user_id', '=', (user or self.user).id)])

    def _row(self, key, user=None):
        return self._rows(user).filtered(lambda r: r.key == key)

    def _prefs(self, commands, user=None):
        """Save Preferences the way the dialog does: as the person, on their own user."""
        user = user or self.user
        user.with_user(user).write({'my_day_section_ids': commands})

    def test_rows_appear_with_the_defaults(self):
        self.MyDay.get_day()
        todo = self._row('todo')
        self.assertEqual((todo.column, todo.limit, todo.days, todo.visible), ('plan', 24, 0, True))
        self.assertTrue(todo.has_days)
        self.assertEqual(todo.name, 'To-dos')
        self.assertEqual(self._row('schedule').column, 'plan')
        self.assertFalse(self._row('schedule').has_days)

    def test_hide_move_and_limit(self):
        self.MyDay.get_day()
        self._prefs([(1, self._row('schedule').id, {'visible': False}),
                     (1, self._row('todo').id, {'column': 'attention', 'limit': 2})])
        day = self.MyDay.get_day()
        keys = [s['key'] for s in day['sections']]
        self.assertNotIn('schedule', keys)
        todo = next(s for s in day['sections'] if s['key'] == 'todo')
        self.assertEqual(todo['column'], 'attention')
        self.assertEqual(len(todo['items']), 2)

    def test_order_follows_the_person(self):
        self.MyDay.get_day()
        self._prefs([(1, self._row('todo').id, {'sequence': 1}), (1, self._row('schedule').id, {'sequence': 2})])
        keys = [s['key'] for s in self.MyDay.get_day()['sections']]
        self.assertLess(keys.index('todo'), keys.index('schedule'))

    def test_days_ahead_option(self):
        self.assertNotIn('In three days', [i['name'] for i in self._section('todo')['items']])
        self._prefs([(1, self._row('todo').id, {'days': 3})])
        self.assertIn('In three days', [i['name'] for i in self._section('todo')['items']])

    def test_nobody_changes_someone_elses_my_day(self):
        self.env['my.day'].with_user(self.other).get_day()
        self.MyDay.get_day()
        theirs = self._row('todo', self.other)
        with self.assertRaises(AccessError):
            self._prefs([(1, theirs.id, {'visible': False})])
        self.assertTrue(theirs.visible)

    def test_only_the_options_can_change(self):
        self.MyDay.get_day()
        with self.assertRaises(AccessError):
            self._prefs([(1, self._row('todo').id, {'key': 'security'})])
        with self.assertRaises(AccessError):
            self._prefs([(2, self._row('todo').id)])
        with self.assertRaises(AccessError):
            self.env['my.day.section.setting'].with_user(self.user).create(
                {'user_id': self.user.id, 'key': 'x', 'column': 'plan'})

    def test_numbers_are_kept_sensible(self):
        self.MyDay.get_day()
        with self.assertRaises(ValidationError):
            self._prefs([(1, self._row('todo').id, {'limit': 0})])

    def test_preferences_list_only_what_the_person_can_see(self):
        # The user menu calls it on the model, with no record (core's own is @api.model).
        self.env['res.users'].with_user(self.user).action_get()
        keys = set(self.user.with_user(self.user).my_day_section_ids.mapped('key'))
        self.assertIn('todo', keys)
        if 'security.event' in self.env:
            # Only security officers see Threat status.
            self.assertNotIn('security', keys)
            self.assertFalse(self._row('security').available)
