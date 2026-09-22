# -*- coding: utf-8 -*-
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestPiperSpeakerIdConstraint(TransactionCase):
    """Speaker ID only makes sense for LibriTTS-R (904 speakers) -
    LJSpeech is a single fixed voice, and Piper's own server only
    honors a speaker_id at all when the loaded voice has more than
    one. Checked on all three owner models (IVR menu, user voicemail,
    call group voicemail), each with its own real Piper server
    already configured so create()/write() actually reach the
    constraint rather than short-circuiting on a missing server.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['signalwire.server'].create({
            'name': 'Test SignalWire', 'space': 'example.signalwire.com',
            'sip_domain': 'example-abc123.sip.signalwire.com',
            'project_id': 'pid123', 'api_token': 'tok456',
        })

    def test_ivr_menu_rejects_a_speaker_id_on_a_single_speaker_voice(self):
        with self.assertRaises(ValidationError):
            self.env['signalwire.ivr.menu'].create({
                'name': 'Menu', 'greeting_text': 'Hi', 'piper_voice': 'en_US-ljspeech-medium',
                'piper_speaker_id': 5,
            })

    def test_ivr_menu_rejects_a_speaker_id_with_no_voice_at_all(self):
        with self.assertRaises(ValidationError):
            self.env['signalwire.ivr.menu'].create({
                'name': 'Menu', 'greeting_text': 'Hi', 'piper_speaker_id': 5,
            })

    def test_ivr_menu_rejects_an_out_of_range_speaker_id(self):
        with self.assertRaises(ValidationError):
            self.env['signalwire.ivr.menu'].create({
                'name': 'Menu', 'greeting_text': 'Hi',
                'piper_voice': 'en_US-libritts_r-medium', 'piper_speaker_id': 9999,
            })

    def test_ivr_menu_accepts_a_valid_speaker_id(self):
        menu = self.env['signalwire.ivr.menu'].create({
            'name': 'Menu', 'greeting_text': 'Hi',
            'piper_voice': 'en_US-libritts_r-medium', 'piper_speaker_id': 42,
        })
        self.assertEqual(menu.piper_speaker_id, 42)

    def test_user_rejects_a_speaker_id_on_a_single_speaker_voice(self):
        with self.assertRaises(ValidationError):
            self.env['res.users'].create({
                'name': 'Jane', 'login': 'jane.speaker.constraint@example.com',
                'signalwire_voicemail_piper_voice': 'en_US-ljspeech-medium',
                'signalwire_voicemail_piper_speaker_id': 5,
            })

    def test_call_group_rejects_a_speaker_id_on_a_single_speaker_voice(self):
        with self.assertRaises(ValidationError):
            self.env['signalwire.call.group'].create({
                'name': 'Sales', 'voicemail_piper_voice': 'en_US-ljspeech-medium',
                'voicemail_piper_speaker_id': 5,
            })

    def test_call_group_accepts_a_valid_speaker_id(self):
        group = self.env['signalwire.call.group'].create({
            'name': 'Sales', 'voicemail_piper_voice': 'en_US-libritts_r-medium',
            'voicemail_piper_speaker_id': 100,
        })
        self.assertEqual(group.voicemail_piper_speaker_id, 100)
