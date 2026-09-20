# -*- coding: utf-8 -*-
from odoo.tests.common import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestVoicemailTranscriptionController(HttpCase):

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
        cls.voicemail = cls.env['signalwire.voicemail'].create({
            'phone_number_id': cls.number.id, 'user_id': cls.user.id,
            'from_number': '+15551234567', 'duration': 30,
            'recording_url': 'https://example.com/rec1',
            'partner_id': cls.partner.id, 'transcription_status': 'pending',
        })
        cls.voicemail._log_and_notify()

    def _post(self, **form):
        url = (f'/signalwire/voice/voicemail_transcription/'
               f'{self.user.id}/{self.number.id}')
        return self.url_open(url, data=form)

    def test_completed_status_stores_the_transcript(self):
        self._post(
            RecordingUrl='https://example.com/rec1', TranscriptionStatus='completed',
            TranscriptionText='Please call me back about the invoice.')

        self.assertEqual(self.voicemail.transcription_status, 'completed')
        self.assertEqual(
            self.voicemail.transcription_text, 'Please call me back about the invoice.')

    def test_completed_transcript_is_posted_to_chatter(self):
        self._post(
            RecordingUrl='https://example.com/rec1', TranscriptionStatus='completed',
            TranscriptionText='Please call me back about the invoice.')

        self.assertTrue(any(
            'Please call me back' in (msg.body or '')
            for msg in self.voicemail.message_ids))
        self.assertTrue(any(
            'Please call me back' in (msg.body or '')
            for msg in self.partner.message_ids))

    def test_completed_transcript_is_folded_into_the_activity_note(self):
        self._post(
            RecordingUrl='https://example.com/rec1', TranscriptionStatus='completed',
            TranscriptionText='Please call me back about the invoice.')

        self.assertTrue(self.voicemail.activity_ids)
        self.assertIn('Please call me back', self.voicemail.activity_ids.note or '')

    def test_failed_status_leaves_no_transcript_text(self):
        self._post(RecordingUrl='https://example.com/rec1', TranscriptionStatus='failed')

        self.assertEqual(self.voicemail.transcription_status, 'failed')
        self.assertFalse(self.voicemail.transcription_text)

    def test_no_matching_recording_url_does_not_crash(self):
        response = self._post(
            RecordingUrl='https://example.com/no-such-recording',
            TranscriptionStatus='completed', TranscriptionText='Orphaned transcript')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.voicemail.transcription_status, 'pending')
