# -*- coding: utf-8 -*-
from datetime import timedelta
from odoo import fields
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
