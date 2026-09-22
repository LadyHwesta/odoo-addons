# -*- coding: utf-8 -*-
from unittest.mock import MagicMock, patch

from odoo.tests.common import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestInboundControllerPiper(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.server = cls.env['signalwire.server'].create({
            'name': 'Test SignalWire', 'space': 'example.signalwire.com',
            'sip_domain': 'example-abc123.sip.signalwire.com',
            'project_id': 'pid123', 'api_token': 'tok456',
            'piper_url': 'http://localhost:5000',
        })
        cls.subproject = cls.env['signalwire.subproject'].create({
            'name': 'Internal Team', 'server_id': cls.server.id,
            'account_sid': 'sub-abc', 'state': 'active',
        })
        cls.user = cls.env['res.users'].create({
            'name': 'Jane Agent', 'login': 'jane.agent.piper@example.com',
            'voip_username': 'user_jane_piper',
        })

    def setUp(self):
        super().setUp()
        self.piper_client = MagicMock()
        self.piper_client.synthesize.return_value = b'RIFF....WAVE'
        patcher = patch(
            'odoo.addons.signalwire_voip_piper_tts.models.signalwire_server.'
            'SignalWireServer._get_piper_client', return_value=self.piper_client)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.env['ir.config_parameter'].sudo().set_param(
            'web.base.url', 'https://odoo.example.com')

    def _cached_attachment_id(self, voice, text, speaker_id=0):
        cache = self.env['signalwire.piper.audio.cache'].search([
            ('voice', '=', voice), ('speaker_id', '=', speaker_id)])
        row = cache.filtered(lambda c: c.text == text)
        self.assertTrue(row, "expected a cached row for this text")
        return row.audio_attachment_id.id

    def test_ivr_menu_greeting_plays_the_cached_piper_audio(self):
        menu = self.env['signalwire.ivr.menu'].create({
            'name': 'Main Menu', 'greeting_text': 'Press 1 for sales.',
            'piper_voice': 'en_US-ljspeech-medium',
        })
        number = self.env['signalwire.phone_number'].create({
            'name': '+12084449665', 'sid': 'pn-piper-1',
            'subproject_id': self.subproject.id,
            'route_type': 'ivr', 'ivr_menu_id': menu.id,
        })
        attachment_id = self._cached_attachment_id(
            'en_US-ljspeech-medium', 'Press 1 for sales.')

        response = self.url_open(
            '/signalwire/voice/inbound',
            data={'To': '+12084449665', 'From': '+15551234567'})

        body = response.text
        self.assertIn(
            f'<Play>https://odoo.example.com/signalwire/voice/piper_audio/'
            f'{attachment_id}</Play>', body)
        self.assertNotIn('<Say>Press 1 for sales.</Say>', body)

    def test_ivr_menu_without_a_piper_voice_still_uses_plain_say(self):
        menu = self.env['signalwire.ivr.menu'].create({
            'name': 'Plain Menu', 'greeting_text': 'Press 1 for sales.',
        })
        number = self.env['signalwire.phone_number'].create({
            'name': '+12084449666', 'sid': 'pn-piper-2',
            'subproject_id': self.subproject.id,
            'route_type': 'ivr', 'ivr_menu_id': menu.id,
        })

        response = self.url_open(
            '/signalwire/voice/inbound',
            data={'To': '+12084449666', 'From': '+15551234567'})

        body = response.text
        self.assertIn('<Say>Press 1 for sales.</Say>', body)
        self.assertNotIn('piper_audio', body)

    def test_ivr_invalid_digit_plays_cached_piper_audio_too(self):
        menu = self.env['signalwire.ivr.menu'].create({
            'name': 'Main Menu', 'greeting_text': 'Press 1 for sales.',
            'piper_voice': 'en_US-ljspeech-medium',
        })
        number = self.env['signalwire.phone_number'].create({
            'name': '+12084449667', 'sid': 'pn-piper-3',
            'subproject_id': self.subproject.id,
        })
        attachment_id = self._cached_attachment_id(
            'en_US-ljspeech-medium', 'Sorry, that is not a valid option.')

        response = self.url_open(
            f'/signalwire/voice/ivr/{menu.id}/{number.id}/digit', data={'Digits': '9'})

        self.assertIn(
            f'<Play>https://odoo.example.com/signalwire/voice/piper_audio/'
            f'{attachment_id}</Play>', response.text)

    def test_user_voicemail_greeting_plays_cached_piper_audio(self):
        self.user.write({
            'signalwire_voicemail_piper_voice': 'en_US-ljspeech-medium',
            'signalwire_voicemail_greeting_text': 'Leave a message for Jane.',
        })
        number = self.env['signalwire.phone_number'].create({
            'name': '+12084449668', 'sid': 'pn-piper-4',
            'subproject_id': self.subproject.id, 'assigned_user_id': self.user.id,
        })
        attachment_id = self._cached_attachment_id(
            'en_US-ljspeech-medium', 'Leave a message for Jane.')

        response = self.url_open(
            f'/signalwire/voice/route_to_voicemail/{self.user.id}/{number.id}',
            data={'CallSid': 'CA000'})

        self.assertIn(
            f'<Play>https://odoo.example.com/signalwire/voice/piper_audio/'
            f'{attachment_id}</Play>', response.text)

    def test_group_voicemail_greeting_plays_cached_piper_audio(self):
        group = self.env['signalwire.call.group'].create({
            'name': 'Sales', 'voicemail_mode': 'group',
            'voicemail_piper_voice': 'en_US-libritts_r-medium',
        })
        number = self.env['signalwire.phone_number'].create({
            'name': '+12084449669', 'sid': 'pn-piper-5',
            'subproject_id': self.subproject.id,
            'route_type': 'group', 'call_group_id': group.id,
        })
        attachment_id = self._cached_attachment_id(
            'en_US-libritts_r-medium', 'Please leave a message after the tone.')

        response = self.url_open(
            f'/signalwire/voice/group_fallback/{group.id}/{number.id}',
            data={'DialCallStatus': 'no-answer'})

        self.assertIn(
            f'<Play>https://odoo.example.com/signalwire/voice/piper_audio/'
            f'{attachment_id}</Play>', response.text)

    def test_ivr_menu_greeting_uses_the_chosen_speaker_id(self):
        menu = self.env['signalwire.ivr.menu'].create({
            'name': 'Multi-speaker Menu', 'greeting_text': 'Press 1 for sales.',
            'piper_voice': 'en_US-libritts_r-medium', 'piper_speaker_id': 42,
        })
        number = self.env['signalwire.phone_number'].create({
            'name': '+12084449671', 'sid': 'pn-piper-7',
            'subproject_id': self.subproject.id,
            'route_type': 'ivr', 'ivr_menu_id': menu.id,
        })
        self.piper_client.synthesize.assert_any_call(
            'Press 1 for sales.', 'en_US-libritts_r-medium', 42)
        attachment_id = self._cached_attachment_id(
            'en_US-libritts_r-medium', 'Press 1 for sales.', speaker_id=42)

        response = self.url_open(
            '/signalwire/voice/inbound',
            data={'To': '+12084449671', 'From': '+15551234567'})

        self.assertIn(
            f'<Play>https://odoo.example.com/signalwire/voice/piper_audio/'
            f'{attachment_id}</Play>', response.text)

    def test_group_voicemail_uses_its_own_custom_greeting_text_via_piper(self):
        group = self.env['signalwire.call.group'].create({
            'name': 'Sales', 'voicemail_mode': 'group',
            'voicemail_piper_voice': 'en_US-ljspeech-medium',
            'voicemail_greeting_text': "You've reached Sales. Leave a message!",
        })
        number = self.env['signalwire.phone_number'].create({
            'name': '+12084449672', 'sid': 'pn-piper-8',
            'subproject_id': self.subproject.id,
            'route_type': 'group', 'call_group_id': group.id,
        })
        attachment_id = self._cached_attachment_id(
            'en_US-ljspeech-medium', "You've reached Sales. Leave a message!")

        response = self.url_open(
            f'/signalwire/voice/group_fallback/{group.id}/{number.id}',
            data={'DialCallStatus': 'no-answer'})

        self.assertIn(
            f'<Play>https://odoo.example.com/signalwire/voice/piper_audio/'
            f'{attachment_id}</Play>', response.text)

    def test_falls_back_to_say_when_synthesis_failed(self):
        from odoo.addons.signalwire_voip_piper_tts.models.piper_client import PiperError
        self.piper_client.synthesize.side_effect = PiperError('down')
        menu = self.env['signalwire.ivr.menu'].create({
            'name': 'Broken Piper Menu', 'greeting_text': 'Press 1 for sales.',
            'piper_voice': 'en_US-ljspeech-medium',
        })
        number = self.env['signalwire.phone_number'].create({
            'name': '+12084449670', 'sid': 'pn-piper-6',
            'subproject_id': self.subproject.id,
            'route_type': 'ivr', 'ivr_menu_id': menu.id,
        })

        response = self.url_open(
            '/signalwire/voice/inbound',
            data={'To': '+12084449670', 'From': '+15551234567'})

        self.assertIn('<Say>Press 1 for sales.</Say>', response.text)

    def test_piper_audio_route_serves_a_real_cached_attachment(self):
        self.env['signalwire.ivr.menu'].create({
            'name': 'Main Menu', 'greeting_text': 'Press 1 for sales.',
            'piper_voice': 'en_US-ljspeech-medium',
        })
        attachment_id = self._cached_attachment_id(
            'en_US-ljspeech-medium', 'Press 1 for sales.')

        response = self.url_open(f'/signalwire/voice/piper_audio/{attachment_id}')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'RIFF....WAVE')

    def test_piper_audio_route_404s_for_an_unrelated_attachment(self):
        attachment = self.env['ir.attachment'].sudo().create({
            'name': 'unrelated.wav', 'raw': b'not piper audio'})

        response = self.url_open(f'/signalwire/voice/piper_audio/{attachment.id}')

        self.assertEqual(response.status_code, 404)
