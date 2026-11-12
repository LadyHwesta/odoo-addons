# -*- coding: utf-8 -*-
import base64
from datetime import datetime, timedelta

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestOnlyofficeMeeting(TransactionCase):

    def setUp(self):
        super().setUp()
        start = datetime.now() + timedelta(days=7)
        self.meeting = self.env['calendar.event'].create({
            'name': 'Board Meeting', 'start': start, 'stop': start + timedelta(hours=1)})

    def test_new_agenda_and_minutes_are_word_documents_on_the_meeting(self):
        action = self.meeting.action_new_agenda()
        self.meeting.action_new_minutes()
        names = sorted(self.meeting.document_ids.mapped('name'))
        self.assertEqual(names, ['Agenda - Board Meeting.docx', 'Minutes - Board Meeting.docx'])
        agenda = self.meeting.document_ids.filtered(lambda a: a.name.startswith('Agenda'))
        self.assertEqual((agenda.res_model, agenda.res_id), ('calendar.event', self.meeting.id))
        self.assertTrue(agenda.raw.startswith(b'PK'), "a real .docx")
        self.assertIn(action['type'], ('ir.actions.client', 'ir.actions.act_url'))
        target = action['params']['attachment_id'] if action['type'] == 'ir.actions.client' \
            else int(action['url'].rsplit('/', 1)[1])
        self.assertEqual(target, agenda.id)

    def test_open_button_only_for_files_onlyoffice_can_open(self):
        word = self.env['ir.attachment'].create({'name': 'Notes.docx', 'datas': base64.b64encode(b'x')})
        zipped = self.env['ir.attachment'].create({'name': 'Archive.zip', 'datas': base64.b64encode(b'x')})
        self.assertTrue(word.calendar_can_open_onlyoffice)
        self.assertFalse(zipped.calendar_can_open_onlyoffice)
        with self.assertRaises(UserError):
            zipped.action_calendar_open_onlyoffice()
