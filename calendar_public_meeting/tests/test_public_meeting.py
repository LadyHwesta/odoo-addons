# -*- coding: utf-8 -*-
import base64
import json
import re
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from odoo import Command
from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import HttpCase, TransactionCase, tagged

CLIENT = 'odoo.addons.signalwire_voip.models.signalwire_server.SignalWireServer._get_client'


class PublicMeetingCase:

    def _setup_common(self):
        self.env['signalwire.server'].create({
            'name': 'Phone', 'space': 'x.signalwire.com', 'project_id': 'p', 'api_token': 't'})
        self.client = MagicMock()
        self.client.video_post.side_effect = lambda path, **body: (
            {'token': f"tok-{body.get('user_name')}"} if path == 'room_tokens' else {'id': 'r1'})
        patcher = patch(CLIENT, return_value=self.client)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.speaker = self.env['res.partner'].create({'name': 'Board Chair', 'email': 'chair@x.org'})

    def _meeting(self, **vals):
        start = datetime.now() + timedelta(hours=1)
        return self.env['calendar.event'].create(dict({
            'name': 'Board Meeting', 'start': start, 'stop': start + timedelta(hours=1),
            'partner_ids': [Command.set([self.speaker.id])], 'public_meeting': True,
        }, **vals))


@tagged('post_install', '-at_install')
class TestPublicMeeting(PublicMeetingCase, TransactionCase):

    def setUp(self):
        super().setUp()
        self._setup_common()

    def test_a_public_meeting_gets_a_watch_link_and_a_speakers_link(self):
        meeting = self._meeting()
        self.assertTrue(meeting.public_watch_url.endswith(f"/meeting/watch/{meeting.public_watch_token}"))
        self.assertTrue(meeting.videocall_location.endswith(f"/meeting/join/{meeting.access_token}"))
        self.assertNotEqual(meeting.public_watch_token, meeting.access_token)

    def test_odoo_meeting_button_keeps_the_speakers_link(self):
        meeting = self._meeting()
        meeting._set_discuss_videocall_location()
        self.assertIn('/meeting/join/', meeting.videocall_location)

    def test_turning_it_off_removes_the_speakers_link(self):
        meeting = self._meeting()
        meeting.public_meeting = False
        self.assertFalse(meeting.videocall_location)
        self.assertFalse(meeting.public_watch_url)

    def test_needs_the_phone_service(self):
        self.env['signalwire.server'].search([]).unlink()
        with self.assertRaisesRegex(UserError, 'phone service'):
            self._meeting()

    def test_viewer_limit(self):
        with self.assertRaises(ValidationError):
            self._meeting(public_max_viewers=300)

    def test_room_made_once_with_room_for_viewers_and_speakers(self):
        meeting = self._meeting(public_max_viewers=50)
        meeting._public_room_token('Pat', viewer=True)
        meeting._public_room_token('Chair', viewer=False)
        rooms = [c for c in self.client.video_post.call_args_list if c.args[0] == 'rooms']
        self.assertEqual(len(rooms), 1)
        self.assertEqual(rooms[0].kwargs['max_members'], 50 + 1 + 5)

    def test_viewers_can_only_listen(self):
        meeting = self._meeting()
        meeting._public_room_token('Pat', viewer=True)
        body = [c.kwargs for c in self.client.video_post.call_args_list if c.args[0] == 'room_tokens'][-1]
        self.assertTrue(body['join_audio_muted'] and body['join_video_muted'])
        for permission in ('room.self.audio_unmute', 'room.self.video_unmute', 'room.self.screenshare'):
            self.assertNotIn(permission, body['permissions'])

    def test_speakers_get_the_defaults_plus_putting_questions_on_screen(self):
        meeting = self._meeting()
        meeting._public_room_token('Chair', viewer=False)
        body = [c.kwargs for c in self.client.video_post.call_args_list if c.args[0] == 'room_tokens'][-1]
        for permission in ('room.self.audio_unmute', 'room.self.video_unmute',
                           'room.self.screenshare', 'room.set_meta'):
            self.assertIn(permission, body['permissions'])
        self.assertNotIn('room.member.remove', body['permissions'])

    def test_only_shared_documents_are_listed(self):
        docs = self.env['ir.attachment'].create([
            {'name': 'Agenda.pdf', 'datas': base64.b64encode(b'a')},
            {'name': 'Legal.pdf', 'datas': base64.b64encode(b'b'), 'meeting_private': True}])
        meeting = self._meeting(document_ids=[Command.set(docs.ids)])
        self.assertEqual([d['name'] for d in meeting._public_documents()], ['Agenda.pdf'])


@tagged('post_install', '-at_install')
class TestPublicMeetingPages(PublicMeetingCase, HttpCase):

    def setUp(self):
        super().setUp()
        self._setup_common()

    def _csrf(self, url):
        page = self.url_open(url).text
        return re.search(r'name="csrf_token" value="([^"]+)"', page).group(1), page

    def test_the_public_signs_in_then_watches(self):
        meeting = self._meeting()
        url = f"/meeting/watch/{meeting.public_watch_token}"
        csrf, page = self._csrf(url)
        self.assertIn('Board Meeting', page)
        response = self.url_open(url, data={'csrf_token': csrf, 'name': 'Pat Public',
                                             'email': 'pat@example.com'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('data-role="viewer"', response.text)
        self.assertIn('tok-Pat Public', response.text)
        self.assertEqual(meeting.public_viewer_ids.mapped('email'), ['pat@example.com'])

    def test_a_bad_email_is_asked_again(self):
        meeting = self._meeting()
        url = f"/meeting/watch/{meeting.public_watch_token}"
        csrf, _page = self._csrf(url)
        response = self.url_open(url, data={'csrf_token': csrf, 'name': 'Pat', 'email': 'nope'})
        self.assertIn('valid email', response.text)
        self.assertFalse(meeting.public_viewer_ids)

    def test_speakers_join_from_their_link(self):
        meeting = self._meeting()
        url = f"/meeting/join/{meeting.access_token}"
        csrf, page = self._csrf(url)
        self.assertIn('joining as a speaker', page)
        response = self.url_open(url, data={'csrf_token': csrf, 'name': 'Board Chair'})
        self.assertIn('data-role="speaker"', response.text)

    def test_unknown_or_private_meetings_are_not_found(self):
        meeting = self._meeting()
        token = meeting.public_watch_token
        meeting.public_meeting = False
        self.assertEqual(self.url_open(f"/meeting/watch/{token}").status_code, 404)
        self.assertEqual(self.url_open("/meeting/watch/nonsense").status_code, 404)

    # -- In the room -------------------------------------------------------------

    def _seat_key(self, page):
        return re.search(r'data-seat="([0-9a-f]{64})"', page).group(1)

    def _enter(self, meeting, role):
        if role == 'speaker':
            url = f"/meeting/join/{meeting.access_token}"
            csrf, _page = self._csrf(url)
            page = self.url_open(url, data={'csrf_token': csrf, 'name': 'Board Chair'}).text
        else:
            url = f"/meeting/watch/{meeting.public_watch_token}"
            csrf, _page = self._csrf(url)
            page = self.url_open(url, data={'csrf_token': csrf, 'name': 'Pat Public',
                                            'email': 'pat@example.com'}).text
        return self._seat_key(page)

    def _post(self, key, action, body):
        return self.url_open(f"/meeting/room/{key}/{action}", data=json.dumps(body),
                             headers={'Content-Type': 'application/json'})

    def test_viewer_asks_and_speakers_see_it_with_their_chat(self):
        meeting = self._meeting()
        speaker = self._enter(meeting, 'speaker')
        viewer = self._enter(meeting, 'viewer')
        self.assertEqual(self._post(viewer, 'send', {'body': 'Will minutes be posted?'}).status_code, 200)
        self.assertEqual(self._post(speaker, 'send', {'body': 'I can take that one'}).status_code, 200)
        data = self._post(speaker, 'poll', {'after': 0}).json()
        self.assertEqual([(m['kind'], m['author'], m['body']) for m in data['messages']], [
            ('question', 'Pat Public', 'Will minutes be posted?'),
            ('chat', 'Board Chair', 'I can take that one')])
        # Only new ones next time, and the answered flag comes back.
        question = data['messages'][0]['id']
        self._post(speaker, 'answered', {'id': question, 'answered': True})
        again = self._post(speaker, 'poll', {'after': data['messages'][-1]['id'],
                                             'documents_version': data['documents_version']}).json()
        self.assertEqual(again['messages'], [])
        self.assertEqual(again['answered'], [question])
        self.assertNotIn('documents', again)
        self.assertEqual(meeting.public_message_ids.mapped('kind'), ['question', 'chat'])

    def test_viewers_can_only_ask(self):
        meeting = self._meeting()
        viewer = self._enter(meeting, 'viewer')
        self._post(viewer, 'send', {'body': 'Hello speakers'})
        self.assertEqual(meeting.public_message_ids.kind, 'question')
        self.assertEqual(self._post(viewer, 'poll', {}).status_code, 403)
        self.assertEqual(self._post(viewer, 'answered', {'id': meeting.public_message_ids.id}).status_code, 403)
        upload = self.url_open(f"/meeting/room/{viewer}/upload",
                               files={'file': ('x.pdf', b'x', 'application/pdf')})
        self.assertEqual(upload.status_code, 403)

    def test_viewers_cant_flood_the_questions(self):
        meeting = self._meeting()
        viewer = self._enter(meeting, 'viewer')
        self.assertEqual(self._post(viewer, 'send', {'body': 'One'}).status_code, 200)
        self.assertEqual(self._post(viewer, 'send', {'body': 'Two'}).status_code, 429)
        self.assertEqual(len(meeting.public_message_ids), 1)

    def test_long_questions_are_cut_and_empty_ones_refused(self):
        meeting = self._meeting()
        viewer = self._enter(meeting, 'viewer')
        self.assertEqual(self._post(viewer, 'send', {'body': '   '}).status_code, 400)
        self._post(viewer, 'send', {'body': 'x' * 2000})
        self.assertEqual(len(meeting.public_message_ids.body), 500)

    def test_a_speaker_adds_a_document_everyone_can_open(self):
        meeting = self._meeting()
        speaker = self._enter(meeting, 'speaker')
        viewer = self._enter(meeting, 'viewer')
        response = self.url_open(f"/meeting/room/{speaker}/upload",
                                 files={'file': ('Budget.pdf', b'%PDF-1.4', 'application/pdf')})
        self.assertEqual(response.status_code, 200)
        self.assertEqual([d['name'] for d in response.json()['documents']], ['Budget.pdf'])
        self.assertEqual(meeting.document_ids.mapped('name'), ['Budget.pdf'])
        self.assertFalse(meeting.document_ids.meeting_private)
        listed = self.url_open(f"/meeting/room/{viewer}/documents").json()
        self.assertEqual([d['name'] for d in listed['documents']], ['Budget.pdf'])
        self.assertIn('access_token=', listed['documents'][0]['url'])
        self.assertIn('Budget.pdf', meeting.message_ids[0].body)

    def test_seats_dont_work_on_other_meetings_or_after_the_end(self):
        meeting = self._meeting()
        speaker = self._enter(meeting, 'speaker')
        self.assertEqual(self._post('f' * 64, 'poll', {}).status_code, 403)
        meeting.write({'start': datetime.now() - timedelta(hours=6),
                       'stop': datetime.now() - timedelta(hours=5)})
        self.assertEqual(self._post(speaker, 'poll', {}).status_code, 403)

    def test_room_page_has_lobby_chat_and_documents(self):
        meeting = self._meeting()
        url = f"/meeting/join/{meeting.access_token}"
        csrf, _page = self._csrf(url)
        page = self.url_open(url, data={'csrf_token': csrf, 'name': 'Board Chair'}).text
        for part in ('Check your camera and sound', 'data-device="videoinput"', 'data-tab="chat"',
                     'data-tab="questions"', 'Add a document', 'data-action="settings"'):
            self.assertIn(part, page)
        url = f"/meeting/watch/{meeting.public_watch_token}"
        csrf, _page = self._csrf(url)
        page = self.url_open(url, data={'csrf_token': csrf, 'name': 'Pat', 'email': 'p@x.org'}).text
        self.assertIn('data-tab="ask"', page)
        self.assertNotIn('data-tab="chat"', page)
        self.assertNotIn('Add a document', page)
        self.assertNotIn('data-device="videoinput"', page)

    def test_an_ended_meeting_says_so(self):
        start = datetime.now() - timedelta(hours=5)
        meeting = self._meeting(start=start, stop=start + timedelta(hours=1))
        page = self.url_open(f"/meeting/watch/{meeting.public_watch_token}").text
        self.assertIn('This meeting has ended', page)
