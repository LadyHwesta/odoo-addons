# -*- coding: utf-8 -*-
import base64
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

    def test_speakers_get_the_default_permissions(self):
        meeting = self._meeting()
        meeting._public_room_token('Chair', viewer=False)
        body = [c.kwargs for c in self.client.video_post.call_args_list if c.args[0] == 'room_tokens'][-1]
        self.assertNotIn('permissions', body)

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

    def test_an_ended_meeting_says_so(self):
        start = datetime.now() - timedelta(hours=5)
        meeting = self._meeting(start=start, stop=start + timedelta(hours=1))
        page = self.url_open(f"/meeting/watch/{meeting.public_watch_token}").text
        self.assertIn('This meeting has ended', page)
