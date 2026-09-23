# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .libritts_r_speakers import LIBRITTS_R_SPEAKERS

PIPER_VOICES = [
    ('en_US-ljspeech-medium', "LJSpeech (public domain)"),
    ('en_US-libritts_r-medium', "LibriTTS-R (CC BY 4.0)"),
]

# The only voice in PIPER_VOICES with more than one speaker (904,
# confirmed against the voice's own real .onnx.json config on
# HuggingFace) - ljspeech is a single fixed voice, so a speaker
# selector is meaningless for it.
MULTI_SPEAKER_VOICE = 'en_US-libritts_r-medium'

# Kept in sync with SignalWireVoiceController.DEFAULT_VOICEMAIL_GREETING
# and the two fixed IVR messages in controllers/main.py - duplicated
# here (a model file) rather than imported from the controller, since
# controllers importing into models is the normal direction, not the
# other way around. A small, stable set of literal strings; if they
# ever change on the controller side, they need to change here too.
IVR_NO_SELECTION_MESSAGE = "We did not receive a selection. Goodbye."
IVR_INVALID_OPTION_MESSAGE = "Sorry, that is not a valid option."


class SignalWireIvrMenu(models.Model):
    _inherit = 'signalwire.ivr.menu'

    piper_voice = fields.Selection(
        PIPER_VOICES, string="Voice",
        help="Speak this menu's greeting (and its own \"no selection\"/"
             "\"invalid option\" messages) using a self-hosted Piper "
             "voice instead of the plain built-in one - requires "
             "signalwire.server.piper_url to be configured. Leave "
             "blank to keep the plain voice.")
    piper_speaker_id = fields.Selection(
        LIBRITTS_R_SPEAKERS, string="Speaker",
        help="Only used for LibriTTS-R, which has 904 different "
             "speakers, each named after the LibriVox reader whose "
             "recordings trained it - leave blank for its own default "
             "speaker. This is Piper's own real per-speaker metadata "
             "(LibriTTS-R's own speakers.tsv from OpenSLR), not a "
             "curated pick - nobody's actually listened to all 904, "
             "so a name here is not a guarantee of quality. Ignored "
             "for LJSpeech, which only has one voice.")

    @api.constrains('piper_voice', 'piper_speaker_id')
    def _check_piper_speaker_id(self):
        for menu in self:
            if menu.piper_speaker_id and menu.piper_voice != MULTI_SPEAKER_VOICE:
                raise ValidationError(_(
                    "Speaker only applies to LibriTTS-R - leave it "
                    "blank for LJSpeech, which has just one voice."))

    def _sync_piper_audio(self):
        # Neither fixed message is wrapped in Odoo's own _() - the
        # cache key has to match the exact literal controllers/main.py
        # calls _say_or_play() with at call time, and a translated
        # string here (resolved in whatever language context a config-
        # time save happens to run under) could permanently mismatch
        # that, silently never hitting the cache.
        cache = self.env['signalwire.piper.audio.cache']
        for menu in self:
            if not menu.piper_voice:
                continue
            speaker_id = int(menu.piper_speaker_id) if menu.piper_speaker_id else None
            cache.get_or_synthesize(menu.piper_voice, menu.greeting_text or '', speaker_id)
            cache.get_or_synthesize(menu.piper_voice, IVR_NO_SELECTION_MESSAGE, speaker_id)
            cache.get_or_synthesize(menu.piper_voice, IVR_INVALID_OPTION_MESSAGE, speaker_id)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sync_piper_audio()
        return records

    def write(self, vals):
        res = super().write(vals)
        if 'piper_voice' in vals or 'greeting_text' in vals or 'piper_speaker_id' in vals:
            self._sync_piper_audio()
        return res
