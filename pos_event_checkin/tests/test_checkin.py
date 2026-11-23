# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase, new_test_user, tagged


@tagged('post_install', '-at_install')
class TestPosEventCheckin(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.config = cls.env['pos.config'].create({'name': 'Door'})
        now = fields.Datetime.now()
        Event = cls.env['event.event']
        cls.tonight = Event.create({'name': 'Disco Night', 'date_tz': 'UTC',
                                    'date_begin': now, 'date_end': now + timedelta(hours=5)})
        cls.next_week = Event.create({'name': 'Next Week Party', 'date_tz': 'UTC',
                                      'date_begin': now + timedelta(days=7),
                                      'date_end': now + timedelta(days=7, hours=4)})
        cls.last_week = Event.create({'name': 'Last Week', 'date_tz': 'UTC',
                                      'date_begin': now - timedelta(days=7),
                                      'date_end': now - timedelta(days=7) + timedelta(hours=4)})
        other_company = cls.env['res.company'].create({'name': 'Elsewhere Inc'})
        cls.elsewhere = Event.create({'name': 'Elsewhere Gala', 'date_tz': 'UTC', 'company_id': other_company.id,
                                      'date_begin': now, 'date_end': now + timedelta(hours=5)})
        Reg = cls.env['event.registration']
        cls.ana = Reg.create({'event_id': cls.tonight.id, 'name': 'Ana Reyes', 'email': 'ana@example.com'})
        cls.ben = Reg.create({'event_id': cls.tonight.id, 'name': 'Ben Ortiz', 'email': 'ben@example.com'})
        cls.cat = Reg.create({'event_id': cls.tonight.id, 'name': 'Cat Lee'})

    def _scan(self, registration):
        return self.config.event_checkin_scan(registration.barcode)

    def test_scan_checks_in_once(self):
        result = self._scan(self.ana)
        self.assertEqual((result['status'], result['name'], result['event']),
                         ('checked_in', 'Ana Reyes', 'Disco Night'))
        self.assertEqual(self.ana.state, 'done')
        again = self._scan(self.ana)
        self.assertEqual(again['status'], 'already')
        self.assertTrue(again['checked_in_at'])

    def test_cancelled_and_unconfirmed_are_refused(self):
        self.ben.action_cancel()
        self.assertEqual(self._scan(self.ben)['status'], 'cancelled')
        self.cat.state = 'draft'
        self.assertEqual(self._scan(self.cat)['status'], 'unconfirmed')
        self.assertNotEqual(self.cat.state, 'done')

    def test_another_day_says_when(self):
        future = self.env['event.registration'].create({'event_id': self.next_week.id, 'name': 'Early Bird'})
        result = self._scan(future)
        self.assertEqual(result['status'], 'other_day')
        self.assertTrue(result['event_date'])
        self.assertEqual(future.state, 'open')
        past = self.env['event.registration'].create({'event_id': self.last_week.id, 'name': 'Late'})
        self.assertEqual(self._scan(past)['status'], 'finished')

    def test_other_companies_and_unknown_codes_are_not_tickets(self):
        theirs = self.env['event.registration'].create({'event_id': self.elsewhere.id, 'name': 'Not Ours'})
        self.assertEqual(self._scan(theirs), {'status': 'invalid_ticket'})
        self.assertEqual(theirs.state, 'open')
        self.assertEqual(self.config.event_checkin_scan('5901234123457'), {'status': 'invalid_ticket'})
        self.assertEqual(self.config.event_checkin_scan(''), {'status': 'invalid_ticket'})

    def test_door_list_counts_and_search(self):
        self._scan(self.ana)
        data = self.config.event_checkin_list()
        self.assertEqual([e['name'] for e in data['events']], ['Disco Night'])
        self.assertEqual((data['events'][0]['checked_in'], data['events'][0]['total']), (1, 3))
        self.assertEqual([a['name'] for a in data['attendees']], ['Ana Reyes', 'Ben Ortiz', 'Cat Lee'])
        self.assertEqual(data['attendees'][0]['status'], 'already')
        self.assertEqual([a['name'] for a in self.config.event_checkin_list('ben@')['attendees']], ['Ben Ortiz'])
        by_ticket = self.config.event_checkin_list(self.cat.barcode)['attendees']
        self.assertEqual([a['name'] for a in by_ticket], ['Cat Lee'])
        result = self.config.event_checkin_registration(self.cat.id)
        self.assertEqual(result['status'], 'checked_in')
        self.assertEqual(self.cat.state, 'done')

    def test_only_point_of_sale_users(self):
        cashier = new_test_user(self.env, 'door.cashier', groups='point_of_sale.group_pos_user')
        outsider = new_test_user(self.env, 'not.a.cashier', groups='base.group_portal')
        self.assertEqual(self.config.with_user(cashier).event_checkin_scan(self.ana.barcode)['status'],
                         'checked_in')
        with self.assertRaises(AccessError):
            self.config.with_user(outsider).event_checkin_list()
