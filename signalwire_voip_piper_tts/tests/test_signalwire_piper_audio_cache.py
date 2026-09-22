# -*- coding: utf-8 -*-
from unittest.mock import MagicMock, patch

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSignalWirePiperAudioCache(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.server = cls.env['signalwire.server'].create({
            'name': 'Test SignalWire', 'space': 'example.signalwire.com',
            'project_id': 'pid123', 'api_token': 'tok456',
            'piper_url': 'http://localhost:5000',
        })

    def setUp(self):
        super().setUp()
        self.piper_client = MagicMock()
        patcher = patch(
            'odoo.addons.signalwire_voip_piper_tts.models.signalwire_server.'
            'SignalWireServer._get_piper_client', return_value=self.piper_client)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_get_cached_returns_nothing_when_nothing_is_cached(self):
        result = self.env['signalwire.piper.audio.cache'].get_cached(
            'en_US-ljspeech-medium', 'Hello there')
        self.assertFalse(result)

    def test_get_cached_never_calls_piper(self):
        self.env['signalwire.piper.audio.cache'].get_cached(
            'en_US-ljspeech-medium', 'Hello there')
        self.piper_client.synthesize.assert_not_called()

    def test_get_or_synthesize_creates_and_caches_the_attachment(self):
        self.piper_client.synthesize.return_value = b'RIFF....WAVE'

        attachment = self.env['signalwire.piper.audio.cache'].get_or_synthesize(
            'en_US-ljspeech-medium', 'Hello there')

        self.assertTrue(attachment)
        self.assertEqual(attachment.raw, b'RIFF....WAVE')
        self.piper_client.synthesize.assert_called_once_with(
            'Hello there', 'en_US-ljspeech-medium', None)

    def test_get_or_synthesize_reuses_the_cache_on_a_second_call(self):
        self.piper_client.synthesize.return_value = b'RIFF....WAVE'
        first = self.env['signalwire.piper.audio.cache'].get_or_synthesize(
            'en_US-ljspeech-medium', 'Hello there')

        second = self.env['signalwire.piper.audio.cache'].get_or_synthesize(
            'en_US-ljspeech-medium', 'Hello there')

        self.assertEqual(first, second)
        self.piper_client.synthesize.assert_called_once()

    def test_get_cached_finds_what_get_or_synthesize_created(self):
        self.piper_client.synthesize.return_value = b'RIFF....WAVE'
        created = self.env['signalwire.piper.audio.cache'].get_or_synthesize(
            'en_US-ljspeech-medium', 'Hello there')

        found = self.env['signalwire.piper.audio.cache'].get_cached(
            'en_US-ljspeech-medium', 'Hello there')

        self.assertEqual(found, created)

    def test_get_or_synthesize_returns_empty_without_a_configured_server(self):
        self.server.piper_url = False

        result = self.env['signalwire.piper.audio.cache'].get_or_synthesize(
            'en_US-ljspeech-medium', 'Hello there')

        self.assertFalse(result)
        self.piper_client.synthesize.assert_not_called()

    def test_get_or_synthesize_swallows_a_piper_failure(self):
        from odoo.addons.signalwire_voip_piper_tts.models.piper_client import PiperError
        self.piper_client.synthesize.side_effect = PiperError('down')

        result = self.env['signalwire.piper.audio.cache'].get_or_synthesize(
            'en_US-ljspeech-medium', 'Hello there')

        self.assertFalse(result)

    def test_get_or_synthesize_without_a_voice_returns_empty(self):
        result = self.env['signalwire.piper.audio.cache'].get_or_synthesize(
            False, 'Hello there')
        self.assertFalse(result)
        self.piper_client.synthesize.assert_not_called()

    def test_different_speaker_id_gets_a_different_cache_entry(self):
        self.piper_client.synthesize.return_value = b'RIFF....WAVE'
        default_speaker = self.env['signalwire.piper.audio.cache'].get_or_synthesize(
            'en_US-libritts_r-medium', 'Hello there')

        speaker_42 = self.env['signalwire.piper.audio.cache'].get_or_synthesize(
            'en_US-libritts_r-medium', 'Hello there', speaker_id=42)

        self.assertNotEqual(default_speaker, speaker_42)
        self.piper_client.synthesize.assert_any_call('Hello there', 'en_US-libritts_r-medium', None)
        self.piper_client.synthesize.assert_any_call('Hello there', 'en_US-libritts_r-medium', 42)

    def test_get_cached_finds_a_specific_speakers_own_entry(self):
        self.piper_client.synthesize.return_value = b'RIFF....WAVE'
        created = self.env['signalwire.piper.audio.cache'].get_or_synthesize(
            'en_US-libritts_r-medium', 'Hello there', speaker_id=42)

        found = self.env['signalwire.piper.audio.cache'].get_cached(
            'en_US-libritts_r-medium', 'Hello there', speaker_id=42)
        not_found = self.env['signalwire.piper.audio.cache'].get_cached(
            'en_US-libritts_r-medium', 'Hello there')

        self.assertEqual(found, created)
        self.assertFalse(not_found)

    def test_cache_key_for_the_default_speaker_matches_the_pre_speaker_format(self):
        # Confirms the cache key hasn't changed shape for the common
        # case (no speaker override) - real cached rows from before
        # speaker selection existed must still hit.
        cache = self.env['signalwire.piper.audio.cache']
        self.assertEqual(
            cache._make_cache_key('en_US-ljspeech-medium', 'Hello there'),
            cache._make_cache_key('en_US-ljspeech-medium', 'Hello there', speaker_id=None))

    def test_different_text_gets_a_different_cache_entry(self):
        self.piper_client.synthesize.return_value = b'RIFF....WAVE'
        self.env['signalwire.piper.audio.cache'].get_or_synthesize(
            'en_US-ljspeech-medium', 'Hello there')

        self.env['signalwire.piper.audio.cache'].get_or_synthesize(
            'en_US-ljspeech-medium', 'Goodbye now')

        self.assertEqual(self.piper_client.synthesize.call_count, 2)
        self.assertEqual(
            self.env['signalwire.piper.audio.cache'].search_count([]), 2)
