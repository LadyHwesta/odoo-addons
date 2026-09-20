# -*- coding: utf-8 -*-
from unittest.mock import MagicMock, patch

from odoo.tests.common import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestVoicemailCompleteController(HttpCase):

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
        cls.user = cls.env['res.users'].create({
            'name': 'Jane Agent', 'login': 'jane.agent@example.com',
            'voip_username': 'user_jane',
        })
        cls.number = cls.env['signalwire.phone_number'].create({
            'name': '+12084449665', 'sid': 'pn-123',
            'subproject_id': cls.subproject.id, 'assigned_user_id': cls.user.id,
        })
        cls.partner = cls.env['res.partner'].create({
            'name': 'Caller Contact', 'phone': '+15551234567',
        })

    def _post(self, transcribe=None, **form):
        url = f'/signalwire/voice/voicemail_complete/{self.user.id}/{self.number.id}'
        if transcribe is not None:
            url += f'?transcribe={transcribe}'
        return self.url_open(url, data=form)

    def test_creates_a_voicemail_record(self):
        with patch('requests.get') as mocked_get:
            mocked_get.return_value = MagicMock(ok=True, content=b'fake-audio-bytes')
            response = self._post(
                From='+15551234567', RecordingUrl='https://example.com/rec1',
                RecordingDuration='42')

        self.assertIn('<Hangup', response.text)
        voicemail = self.env['signalwire.voicemail'].search(
            [('user_id', '=', self.user.id)])
        self.assertEqual(len(voicemail), 1)
        self.assertEqual(voicemail.from_number, '+15551234567')
        self.assertEqual(voicemail.duration, 42)

    def test_fetches_and_attaches_the_recording(self):
        with patch('requests.get') as mocked_get:
            mocked_get.return_value = MagicMock(ok=True, content=b'fake-audio-bytes')
            self._post(
                From='+15551234567', RecordingUrl='https://example.com/rec1',
                RecordingDuration='42')

        mocked_get.assert_called_once()
        args, kwargs = mocked_get.call_args
        self.assertEqual(args[0], 'https://example.com/rec1.mp3')
        self.assertEqual(kwargs['auth'], ('pid123', 'tok456'))

        voicemail = self.env['signalwire.voicemail'].search(
            [('user_id', '=', self.user.id)])
        self.assertTrue(voicemail.recording_attachment_id)
        self.assertEqual(voicemail.recording_attachment_id.raw, b'fake-audio-bytes')

    def test_matches_the_caller_to_a_partner(self):
        with patch('requests.get') as mocked_get:
            mocked_get.return_value = MagicMock(ok=True, content=b'x')
            self._post(
                From='+15551234567', RecordingUrl='https://example.com/rec1',
                RecordingDuration='10')

        voicemail = self.env['signalwire.voicemail'].search(
            [('user_id', '=', self.user.id)])
        self.assertEqual(voicemail.partner_id, self.partner)

    def test_logs_to_the_matched_partners_chatter(self):
        with patch('requests.get') as mocked_get:
            mocked_get.return_value = MagicMock(ok=True, content=b'x')
            self._post(
                From='+15551234567', RecordingUrl='https://example.com/rec1',
                RecordingDuration='10')

        self.assertTrue(any(
            'Voicemail' in (msg.body or '') for msg in self.partner.message_ids))

    def test_schedules_an_activity_for_the_agent(self):
        with patch('requests.get') as mocked_get:
            mocked_get.return_value = MagicMock(ok=True, content=b'x')
            self._post(
                From='+15551234567', RecordingUrl='https://example.com/rec1',
                RecordingDuration='10')

        voicemail = self.env['signalwire.voicemail'].search(
            [('user_id', '=', self.user.id)])
        self.assertTrue(voicemail.activity_ids)
        self.assertEqual(voicemail.activity_ids.user_id, self.user)

    def test_no_transcribe_param_leaves_status_none(self):
        with patch('requests.get') as mocked_get:
            mocked_get.return_value = MagicMock(ok=True, content=b'x')
            self._post(From='+15551234567', RecordingUrl='https://example.com/rec1',
                       RecordingDuration='10')

        voicemail = self.env['signalwire.voicemail'].search(
            [('user_id', '=', self.user.id)])
        self.assertEqual(voicemail.transcription_status, 'none')

    def test_transcribe_param_sets_pending_and_stores_recording_url(self):
        with patch('requests.get') as mocked_get:
            mocked_get.return_value = MagicMock(ok=True, content=b'x')
            self._post(transcribe='1', From='+15551234567',
                       RecordingUrl='https://example.com/rec1', RecordingDuration='10')

        voicemail = self.env['signalwire.voicemail'].search(
            [('user_id', '=', self.user.id)])
        self.assertEqual(voicemail.transcription_status, 'pending')
        self.assertEqual(voicemail.recording_url, 'https://example.com/rec1')

    def test_failed_recording_fetch_does_not_crash(self):
        import requests
        with patch('requests.get', side_effect=requests.ConnectionError('boom')):
            response = self._post(
                From='+15551234567', RecordingUrl='https://example.com/rec1',
                RecordingDuration='10')

        self.assertIn('<Hangup', response.text)
        voicemail = self.env['signalwire.voicemail'].search(
            [('user_id', '=', self.user.id)])
        self.assertTrue(voicemail)
        self.assertFalse(voicemail.recording_attachment_id)
