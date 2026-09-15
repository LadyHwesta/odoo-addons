# -*- coding: utf-8 -*-
from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSignalWireVoicemail(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.server = cls.env['signalwire.server'].create({
            'name': 'Test SignalWire', 'space': 'example.signalwire.com',
            'project_id': 'pid123', 'api_token': 'tok456',
        })
        cls.subproject = cls.env['signalwire.subproject'].create({
            'name': 'Internal Team', 'server_id': cls.server.id,
            'account_sid': 'sub-abc', 'state': 'active',
        })
        cls.number = cls.env['signalwire.phone_number'].create({
            'name': '+12084449665', 'sid': 'pn-123', 'subproject_id': cls.subproject.id,
        })
        cls.user = cls.env['res.users'].create({
            'name': 'Jane Agent', 'login': 'jane.agent@example.com',
        })
        cls.other_user = cls.env['res.users'].create({
            'name': 'Other Agent', 'login': 'other.agent@example.com',
        })
        cls.voicemail = cls.env['signalwire.voicemail'].create({
            'phone_number_id': cls.number.id, 'user_id': cls.user.id,
            'from_number': '+15551234567', 'duration': 20,
        })

    def test_new_voicemail_is_unread(self):
        self.assertFalse(self.voicemail.is_read)

    def test_mark_read_and_unread(self):
        self.voicemail.action_mark_read()
        self.assertTrue(self.voicemail.is_read)

        self.voicemail.action_mark_unread()
        self.assertFalse(self.voicemail.is_read)

    def test_recording_download_url_is_empty_without_an_attachment(self):
        self.assertFalse(self.voicemail.recording_download_url)

    def test_recording_download_url_points_at_the_attachment(self):
        attachment = self.env['ir.attachment'].create({
            'name': 'vm.mp3', 'type': 'binary', 'raw': b'audio', 'mimetype': 'audio/mpeg',
        })
        self.voicemail.recording_attachment_id = attachment.id

        self.assertEqual(
            self.voicemail.recording_download_url,
            f'/web/content/{attachment.id}?download=false')

    def test_get_systray_data_counts_only_the_current_users_unread(self):
        other_voicemail = self.voicemail.copy({'user_id': self.other_user.id})
        self.voicemail.action_mark_read()

        data = self.voicemail.with_user(self.other_user).get_systray_data()

        self.assertEqual(data['count'], 1)
        self.assertEqual(data['voicemails'][0]['id'], other_voicemail.id)

    def test_get_systray_data_is_empty_once_everything_is_read(self):
        self.voicemail.action_mark_read()

        data = self.voicemail.with_user(self.user).get_systray_data()

        self.assertEqual(data['count'], 0)
        self.assertEqual(data['voicemails'], [])

    def test_a_plain_user_cannot_see_someone_elses_voicemail(self):
        with self.assertRaises(AccessError):
            self.voicemail.with_user(self.other_user).read(['from_number'])

    def test_a_plain_user_can_delete_their_own_voicemail(self):
        self.voicemail.with_user(self.user).unlink()
        self.assertFalse(self.voicemail.exists())
