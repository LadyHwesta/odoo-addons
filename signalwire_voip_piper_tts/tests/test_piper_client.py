# -*- coding: utf-8 -*-
from unittest.mock import MagicMock, patch

import requests

from odoo.addons.signalwire_voip_piper_tts.models.piper_client import PiperClient, PiperError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestPiperClient(TransactionCase):

    def test_synthesize_posts_the_right_request(self):
        client = PiperClient('http://localhost:5000')
        with patch('requests.post') as mocked_post:
            mocked_post.return_value = MagicMock(status_code=200, content=b'RIFF....WAVE')
            result = client.synthesize('Hello there', 'en_US-ljspeech-medium')

        mocked_post.assert_called_once_with(
            'http://localhost:5000/synthesize',
            json={'text': 'Hello there', 'voice': 'en_US-ljspeech-medium'},
            timeout=30)
        self.assertEqual(result, b'RIFF....WAVE')

    def test_synthesize_omits_speaker_id_when_not_given(self):
        client = PiperClient('http://localhost:5000')
        with patch('requests.post') as mocked_post:
            mocked_post.return_value = MagicMock(status_code=200, content=b'x')
            client.synthesize('Hi', 'en_US-ljspeech-medium')

        _args, kwargs = mocked_post.call_args
        self.assertNotIn('speaker_id', kwargs['json'])

    def test_synthesize_includes_speaker_id_when_given(self):
        client = PiperClient('http://localhost:5000')
        with patch('requests.post') as mocked_post:
            mocked_post.return_value = MagicMock(status_code=200, content=b'x')
            client.synthesize('Hi', 'en_US-libritts_r-medium', speaker_id=42)

        _args, kwargs = mocked_post.call_args
        self.assertEqual(kwargs['json']['speaker_id'], 42)

    def test_synthesize_strips_a_trailing_slash_from_the_base_url(self):
        client = PiperClient('http://localhost:5000/')
        with patch('requests.post') as mocked_post:
            mocked_post.return_value = MagicMock(status_code=200, content=b'x')
            client.synthesize('Hi', 'en_US-ljspeech-medium')

        args, _kwargs = mocked_post.call_args
        self.assertEqual(args[0], 'http://localhost:5000/synthesize')

    def test_synthesize_raises_without_a_configured_url(self):
        client = PiperClient('')
        with self.assertRaises(PiperError):
            client.synthesize('Hi', 'en_US-ljspeech-medium')

    def test_synthesize_raises_on_an_error_status(self):
        client = PiperClient('http://localhost:5000')
        with patch('requests.post') as mocked_post:
            mocked_post.return_value = MagicMock(status_code=500, text='boom', content=b'')
            with self.assertRaises(PiperError):
                client.synthesize('Hi', 'en_US-ljspeech-medium')

    def test_synthesize_raises_on_an_empty_response(self):
        client = PiperClient('http://localhost:5000')
        with patch('requests.post') as mocked_post:
            mocked_post.return_value = MagicMock(status_code=200, content=b'')
            with self.assertRaises(PiperError):
                client.synthesize('Hi', 'en_US-ljspeech-medium')

    def test_synthesize_raises_on_a_network_error(self):
        client = PiperClient('http://localhost:5000')
        with patch('requests.post', side_effect=requests.ConnectionError('down')):
            with self.assertRaises(PiperError):
                client.synthesize('Hi', 'en_US-ljspeech-medium')
