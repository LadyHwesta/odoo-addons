# -*- coding: utf-8 -*-
from unittest.mock import MagicMock, patch

from odoo import http
from odoo.tests.common import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestPiperPreviewController(HttpCase):
    """The backend-only "Preview" widget's own endpoint - synthesizes
    on demand for a Voice/Speaker/typed-sample-text combination, never
    touches signalwire.piper.audio.cache (a one-off sample has no
    business becoming a permanent cached greeting).
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.server = cls.env['signalwire.server'].create({
            'name': 'Test SignalWire', 'space': 'example.signalwire.com',
            'sip_domain': 'example-abc123.sip.signalwire.com',
            'project_id': 'pid123', 'api_token': 'tok456',
            'piper_url': 'http://localhost:5000',
        })
        cls.user = cls.env['res.users'].create({
            'name': 'Jane Agent', 'login': 'jane.agent.preview@example.com',
        })
        cls.user.sudo().write({'password': 'preview_test_pw_123'})

    def setUp(self):
        super().setUp()
        self.piper_client = MagicMock()
        self.piper_client.synthesize.return_value = b'RIFF....WAVE'
        patcher = patch(
            'odoo.addons.signalwire_voip_piper_tts.models.signalwire_server.'
            'SignalWireServer._get_piper_client', return_value=self.piper_client)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _post(self, **data):
        self.authenticate('jane.agent.preview@example.com', 'preview_test_pw_123')
        data['csrf_token'] = http.Request.csrf_token(self)
        return self.url_open('/signalwire/piper/preview', data=data)

    def test_preview_returns_real_audio_for_valid_text_and_voice(self):
        response = self._post(text='Hello there', voice='en_US-ljspeech-medium')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get('Content-Type'), 'audio/wav')
        self.assertEqual(response.content, b'RIFF....WAVE')
        self.piper_client.synthesize.assert_called_once_with('Hello there', 'en_US-ljspeech-medium', None)

    def test_preview_passes_the_chosen_speaker_id_through(self):
        self._post(text='Hello there', voice='en_US-libritts_r-medium', speaker_id='42')

        self.piper_client.synthesize.assert_called_once_with(
            'Hello there', 'en_US-libritts_r-medium', 42)

    def test_preview_never_creates_a_cache_row(self):
        before = self.env['signalwire.piper.audio.cache'].search_count([])

        self._post(text='Hello there', voice='en_US-ljspeech-medium')

        after = self.env['signalwire.piper.audio.cache'].search_count([])
        self.assertEqual(before, after)

    def test_preview_requires_text(self):
        response = self._post(voice='en_US-ljspeech-medium')

        self.assertEqual(response.status_code, 400)
        self.piper_client.synthesize.assert_not_called()

    def test_preview_requires_voice(self):
        response = self._post(text='Hello there')

        self.assertEqual(response.status_code, 400)
        self.piper_client.synthesize.assert_not_called()

    def test_preview_without_a_configured_server_fails_cleanly(self):
        self.server.piper_url = False

        response = self._post(text='Hello there', voice='en_US-ljspeech-medium')

        self.assertEqual(response.status_code, 400)
        self.assertIn(b'error', response.content)

    def test_preview_surfaces_a_piper_failure_as_a_clean_error(self):
        from odoo.addons.signalwire_voip_piper_tts.models.piper_client import PiperError
        self.piper_client.synthesize.side_effect = PiperError('down')

        response = self._post(text='Hello there', voice='en_US-ljspeech-medium')

        self.assertEqual(response.status_code, 400)
        self.assertIn(b'down', response.content)

    def test_preview_is_not_reachable_without_logging_in(self):
        # No self.authenticate() and no csrf_token - a real anonymous
        # caller has neither. Whether CSRF or the auth='user' check is
        # what actually blocks it first is an implementation detail;
        # what matters is that no real audio ever comes back.
        response = self.url_open(
            '/signalwire/piper/preview',
            data={'text': 'Hello there', 'voice': 'en_US-ljspeech-medium'},
            allow_redirects=False)

        self.assertNotEqual(response.status_code, 200)
        self.assertNotEqual(response.headers.get('Content-Type'), 'audio/wav')
        self.piper_client.synthesize.assert_not_called()
