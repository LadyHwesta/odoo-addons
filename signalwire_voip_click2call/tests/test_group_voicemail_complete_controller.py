# -*- coding: utf-8 -*-
from unittest.mock import MagicMock, patch

from odoo.tests.common import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestGroupVoicemailCompleteController(HttpCase):

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
        cls.member = cls.env['res.users'].create({
            'name': 'Jane Agent', 'login': 'jane.agent.group@example.com',
        })
        cls.other_user = cls.env['res.users'].create({
            'name': 'Not In Group', 'login': 'outsider.group@example.com',
        })
        cls.group = cls.env['signalwire.call.group'].create({
            'name': 'Sales', 'member_ids': [(6, 0, [cls.member.id])],
            'voicemail_mode': 'group',
        })
        cls.number = cls.env['signalwire.phone_number'].create({
            'name': '+12084449665', 'sid': 'pn-123',
            'subproject_id': cls.subproject.id,
            'route_type': 'group', 'call_group_id': cls.group.id,
        })
        cls.partner = cls.env['res.partner'].create({
            'name': 'Caller Contact', 'phone': '+15551234567',
        })

    def _post(self, **form):
        url = f'/signalwire/voice/group_voicemail_complete/{self.group.id}/{self.number.id}'
        return self.url_open(url, data=form)

    def test_creates_a_voicemail_owned_by_the_group_not_a_user(self):
        with patch('requests.get') as mocked_get:
            mocked_get.return_value = MagicMock(ok=True, content=b'fake-audio-bytes')
            response = self._post(
                From='+15551234567', RecordingUrl='https://example.com/rec1',
                RecordingDuration='42')

        self.assertIn('<Hangup', response.text)
        voicemail = self.env['signalwire.voicemail'].search(
            [('call_group_id', '=', self.group.id)])
        self.assertEqual(len(voicemail), 1)
        self.assertFalse(voicemail.user_id)
        self.assertEqual(voicemail.from_number, '+15551234567')
        self.assertEqual(voicemail.duration, 42)

    def test_matches_the_caller_to_a_partner(self):
        with patch('requests.get') as mocked_get:
            mocked_get.return_value = MagicMock(ok=True, content=b'x')
            self._post(
                From='+15551234567', RecordingUrl='https://example.com/rec1',
                RecordingDuration='10')

        voicemail = self.env['signalwire.voicemail'].search(
            [('call_group_id', '=', self.group.id)])
        self.assertEqual(voicemail.partner_id, self.partner)

    def test_posts_to_the_groups_own_chatter_not_a_personal_activity(self):
        with patch('requests.get') as mocked_get:
            mocked_get.return_value = MagicMock(ok=True, content=b'x')
            self._post(
                From='+15551234567', RecordingUrl='https://example.com/rec1',
                RecordingDuration='10')

        voicemail = self.env['signalwire.voicemail'].search(
            [('call_group_id', '=', self.group.id)])
        self.assertFalse(voicemail.activity_ids)
        self.assertTrue(any(
            'Voicemail' in (msg.body or '') for msg in self.group.message_ids))

    def test_group_member_can_read_the_shared_voicemail(self):
        with patch('requests.get') as mocked_get:
            mocked_get.return_value = MagicMock(ok=True, content=b'x')
            self._post(
                From='+15551234567', RecordingUrl='https://example.com/rec1',
                RecordingDuration='10')

        found = self.env['signalwire.voicemail'].with_user(self.member).search(
            [('call_group_id', '=', self.group.id)])
        self.assertEqual(len(found), 1)

    def test_non_member_cannot_read_the_shared_voicemail(self):
        with patch('requests.get') as mocked_get:
            mocked_get.return_value = MagicMock(ok=True, content=b'x')
            self._post(
                From='+15551234567', RecordingUrl='https://example.com/rec1',
                RecordingDuration='10')

        found = self.env['signalwire.voicemail'].with_user(self.other_user).search(
            [('call_group_id', '=', self.group.id)])
        self.assertFalse(found)
