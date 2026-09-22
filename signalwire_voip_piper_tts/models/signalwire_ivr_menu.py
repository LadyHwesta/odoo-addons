# -*- coding: utf-8 -*-
from odoo import api, fields, models

PIPER_VOICES = [
    ('en_US-ljspeech-medium', "LJSpeech (public domain)"),
    ('en_US-libritts_r-medium', "LibriTTS-R (CC BY 4.0)"),
]

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
            cache.get_or_synthesize(menu.piper_voice, menu.greeting_text or '')
            cache.get_or_synthesize(menu.piper_voice, IVR_NO_SELECTION_MESSAGE)
            cache.get_or_synthesize(menu.piper_voice, IVR_INVALID_OPTION_MESSAGE)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sync_piper_audio()
        return records

    def write(self, vals):
        res = super().write(vals)
        if 'piper_voice' in vals or 'greeting_text' in vals:
            self._sync_piper_audio()
        return res
