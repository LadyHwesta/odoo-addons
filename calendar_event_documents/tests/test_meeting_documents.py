# -*- coding: utf-8 -*-
import base64
from datetime import datetime, timedelta
from unittest.mock import patch

from odoo import Command
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestMeetingDocuments(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.guest = cls.env['res.partner'].create({'name': 'Board Member', 'email': 'board@example.com'})
        cls.start = datetime.now() + timedelta(days=7)

    def _doc(self, name='Agenda.txt', data=b'1. Welcome'):
        return self.env['ir.attachment'].create({'name': name, 'datas': base64.b64encode(data)})

    def _meeting(self, **vals):
        return self.env['calendar.event'].create(dict({
            'name': 'Board Meeting', 'start': self.start, 'stop': self.start + timedelta(hours=1),
            'partner_ids': [Command.set([self.guest.id])],
        }, **vals))

    def _invitation_files(self, meeting):
        messages = self.env['mail.message'].search([
            ('model', '=', 'calendar.event'), ('res_id', '=', meeting.id),
            ('attachment_ids', '!=', False)])
        return messages.attachment_ids.mapped('name')

    def test_documents_added_before_saving_belong_to_the_meeting(self):
        doc = self._doc()
        meeting = self._meeting(document_ids=[Command.link(doc.id)])
        self.assertEqual((doc.res_model, doc.res_id), ('calendar.event', meeting.id))
        self.assertEqual(meeting.document_count, 1)

    def test_invitations_carry_the_documents(self):
        meeting = self._meeting(document_ids=[Command.link(self._doc().id)])
        files = self._invitation_files(meeting)
        self.assertIn('Agenda.txt', files)
        self.assertIn('invitation.ics', files)
        # The email gets copies; the meeting keeps its own document.
        self.assertEqual(meeting.document_ids.res_model, 'calendar.event')

    def test_documents_can_stay_out_of_invitations(self):
        meeting = self._meeting(documents_in_invitations=False,
                                document_ids=[Command.link(self._doc().id)])
        self.assertNotIn('Agenda.txt', self._invitation_files(meeting))

    def test_other_emails_dont_carry_them(self):
        meeting = self._meeting(document_ids=[Command.link(self._doc().id)])
        self.env['mail.message'].search([('model', '=', 'calendar.event'), ('res_id', '=', meeting.id)]).unlink()
        reminder = self.env.ref('calendar.calendar_template_meeting_reminder')
        meeting.attendee_ids._notify_attendees(reminder)
        self.assertNotIn('Agenda.txt', self._invitation_files(meeting))

    def test_too_large_documents_are_mentioned_not_attached(self):
        with patch('odoo.addons.calendar_event_documents.models.calendar_event.MAX_MAIL_DOCUMENTS_BYTES', 5):
            meeting = self._meeting(document_ids=[Command.link(self._doc(data=b'0123456789').id)])
        self.assertNotIn('Agenda.txt', self._invitation_files(meeting))
        bodies = self.env['mail.message'].search([
            ('model', '=', 'calendar.event'), ('res_id', '=', meeting.id)]).mapped('body')
        self.assertTrue(any('too large to email' in (b or '') for b in bodies))

    def test_screens_load(self):
        for xmlid, kind in (('calendar.view_calendar_event_form', 'form'),
                            ('calendar.view_calendar_event_calendar', 'calendar')):
            arch = self.env['calendar.event'].get_view(self.env.ref(xmlid).id, kind)['arch']
            self.assertIn('document_ids', arch)


from odoo.tests.common import HttpCase  # noqa: E402


@tagged('post_install', '-at_install')
class TestMeetingDocumentsPage(HttpCase):

    def test_documents_tab_shows_in_the_browser(self):
        start = datetime.now() + timedelta(days=7)
        meeting = self.env['calendar.event'].create({
            'name': 'Board Meeting', 'start': start, 'stop': start + timedelta(hours=1)})
        meeting.document_ids = [Command.create({'name': 'Agenda.txt', 'datas': base64.b64encode(b'x'),
                                                'res_model': 'calendar.event', 'res_id': meeting.id})]
        code = """
            (async () => {
                const tab = [...document.querySelectorAll('.o_notebook .nav-link')].find(a => a.textContent.trim() === 'Documents');
                if (!tab) { throw new Error('no Documents tab'); }
                tab.click();
                for (let i = 0; i < 50 && !document.body.textContent.includes('Agenda.txt'); i++) {
                    await new Promise((r) => setTimeout(r, 100));
                }
                if (!document.body.textContent.includes('Agenda.txt')) { throw new Error('document not listed'); }
                console.log('test successful');
            })().catch((e) => console.error(e.message));
        """
        self.browser_js(f'/odoo/calendar/{meeting.id}', code,
                        ready="!!document.querySelector('.o_notebook')", login='admin', timeout=120)


@tagged('post_install', '-at_install')
class TestMeetingDocumentsInCalls(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.guest = cls.env['res.partner'].create({'name': 'Guest', 'email': 'guest@example.com'})
        cls.start = datetime.now() + timedelta(days=7)

    def _doc(self, name='Agenda.txt'):
        return self.env['ir.attachment'].create({'name': name, 'datas': base64.b64encode(b'x')})

    def _meeting(self, **vals):
        return self.env['calendar.event'].create(dict({
            'name': 'Board Meeting', 'start': self.start, 'stop': self.start + timedelta(hours=1),
            'partner_ids': [Command.set([self.guest.id])],
        }, **vals))

    def test_chatter_files_become_documents(self):
        meeting = self._meeting()
        meeting.message_post(body="Minutes attached", attachments=[('Minutes.txt', b'notes')])
        self.assertIn('Minutes.txt', meeting.document_ids.mapped('name'))

    def test_paperclip_upload_becomes_a_document(self):
        meeting = self._meeting()
        attachment = self.env['ir.attachment'].create({
            'name': 'Budget.txt', 'datas': base64.b64encode(b'1'),
            'res_model': 'calendar.event', 'res_id': meeting.id})
        attachment._post_add_create()
        self.assertIn(attachment, meeting.document_ids)

    def test_joining_the_call_pins_the_documents_in_its_chat(self):
        doc = self._doc()
        meeting = self._meeting(document_ids=[Command.link(doc.id)])
        meeting._create_videocall_channel()
        message = meeting.videocall_documents_message_id
        self.assertEqual((message.model, message.res_id),
                         ('discuss.channel', meeting.videocall_channel_id.id))
        self.assertTrue(message.pinned_at)
        self.assertIn('Agenda.txt', message.body)
        self.assertIn(f'/web/content/{doc.id}?access_token={doc.access_token}', message.body)

    def test_the_call_list_follows_document_changes(self):
        meeting = self._meeting(document_ids=[Command.link(self._doc().id)])
        meeting._create_videocall_channel()
        message = meeting.videocall_documents_message_id
        meeting.document_ids = [Command.link(self._doc('Minutes.txt').id)]
        self.assertEqual(meeting.videocall_documents_message_id, message)
        self.assertIn('Minutes.txt', message.body)
        meeting.document_ids = [Command.clear()]
        self.assertIn('No documents for this meeting', message.body)

    def test_no_documents_no_message(self):
        meeting = self._meeting()
        meeting._create_videocall_channel()
        self.assertFalse(meeting.videocall_documents_message_id)


@tagged('post_install', '-at_install')
class TestPrivateMeetingDocuments(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.guest = cls.env['res.partner'].create({'name': 'Guest', 'email': 'guest@example.com'})
        cls.start = datetime.now() + timedelta(days=7)

    def _doc(self, name, private=False):
        return self.env['ir.attachment'].create({
            'name': name, 'datas': base64.b64encode(b'x'), 'meeting_private': private})

    def _meeting(self, docs):
        return self.env['calendar.event'].create({
            'name': 'Board Meeting', 'start': self.start, 'stop': self.start + timedelta(hours=1),
            'partner_ids': [Command.set([self.guest.id])],
            'document_ids': [Command.set(docs.ids)]})

    def test_private_documents_stay_out_of_invitations(self):
        meeting = self._meeting(self._doc('Agenda.txt') | self._doc('Legal notes.txt', private=True))
        self.assertEqual(meeting._shared_documents().mapped('name'), ['Agenda.txt'])
        sent = self.env['mail.message'].search([
            ('model', '=', 'calendar.event'), ('res_id', '=', meeting.id),
            ('attachment_ids', '!=', False)]).attachment_ids.mapped('name')
        self.assertIn('Agenda.txt', sent)
        self.assertNotIn('Legal notes.txt', sent)

    def test_private_documents_stay_out_of_the_call(self):
        meeting = self._meeting(self._doc('Agenda.txt') | self._doc('Legal notes.txt', private=True))
        meeting._create_videocall_channel()
        body = meeting.videocall_documents_message_id.body
        self.assertIn('Agenda.txt', body)
        self.assertNotIn('Legal notes.txt', body)

    def test_making_a_document_private_takes_it_out_of_the_call(self):
        doc = self._doc('Agenda.txt')
        meeting = self._meeting(doc)
        meeting._create_videocall_channel()
        old_token = doc.access_token
        self.assertTrue(old_token)
        doc.meeting_private = True
        self.assertFalse(doc.access_token)  # the shared link no longer works
        self.assertNotIn('Agenda.txt', meeting.videocall_documents_message_id.body)
        self.assertIn('Agenda.txt', meeting.document_ids.mapped('name'))
