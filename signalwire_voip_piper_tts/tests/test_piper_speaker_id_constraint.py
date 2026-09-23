# -*- coding: utf-8 -*-
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestPiperSpeakerIdConstraint(TransactionCase):
    """Speaker selection only makes sense for LibriTTS-R (904 real
    named speakers) - LJSpeech is a single fixed voice, and Piper's
    own server only honors a speaker_id at all when the loaded voice
    has more than one. An out-of-range/unknown value is structurally
    impossible now that this is a real Selection field (Odoo's own
    ORM rejects an unrecognized key before this ever reaches our own
    code) - only "picked for the wrong voice" needs our own check.
    Exercised on all three owner models (IVR menu, user voicemail,
    call group voicemail), each with a real Piper server already
    configured so create()/write() actually reach the constraint
    rather than short-circuiting on a missing server.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['signalwire.server'].create({
            'name': 'Test SignalWire', 'space': 'example.signalwire.com',
            'sip_domain': 'example-abc123.sip.signalwire.com',
            'project_id': 'pid123', 'api_token': 'tok456',
        })

    def test_ivr_menu_rejects_a_speaker_on_a_single_speaker_voice(self):
        with self.assertRaises(ValidationError):
            self.env['signalwire.ivr.menu'].create({
                'name': 'Menu', 'greeting_text': 'Hi', 'piper_voice': 'en_US-ljspeech-medium',
                'piper_speaker_id': '42',
            })

    def test_ivr_menu_rejects_a_speaker_with_no_voice_at_all(self):
        with self.assertRaises(ValidationError):
            self.env['signalwire.ivr.menu'].create({
                'name': 'Menu', 'greeting_text': 'Hi', 'piper_speaker_id': '42',
            })

    def test_ivr_menu_accepts_a_valid_speaker(self):
        menu = self.env['signalwire.ivr.menu'].create({
            'name': 'Menu', 'greeting_text': 'Hi',
            'piper_voice': 'en_US-libritts_r-medium', 'piper_speaker_id': '42',
        })
        self.assertEqual(menu.piper_speaker_id, '42')

    def test_user_rejects_a_speaker_on_a_single_speaker_voice(self):
        with self.assertRaises(ValidationError):
            self.env['res.users'].create({
                'name': 'Jane', 'login': 'jane.speaker.constraint@example.com',
                'signalwire_voicemail_piper_voice': 'en_US-ljspeech-medium',
                'signalwire_voicemail_piper_speaker_id': '42',
            })

    def test_call_group_rejects_a_speaker_on_a_single_speaker_voice(self):
        with self.assertRaises(ValidationError):
            self.env['signalwire.call.group'].create({
                'name': 'Sales', 'voicemail_piper_voice': 'en_US-ljspeech-medium',
                'voicemail_piper_speaker_id': '42',
            })

    def test_call_group_accepts_a_valid_speaker(self):
        group = self.env['signalwire.call.group'].create({
            'name': 'Sales', 'voicemail_piper_voice': 'en_US-libritts_r-medium',
            'voicemail_piper_speaker_id': '100',
        })
        self.assertEqual(group.voicemail_piper_speaker_id, '100')
