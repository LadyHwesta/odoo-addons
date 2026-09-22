# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .signalwire_ivr_menu import MULTI_SPEAKER_MAX_ID, MULTI_SPEAKER_VOICE, PIPER_VOICES


class SignalWireCallGroup(models.Model):
    _inherit = 'signalwire.call.group'

    voicemail_piper_voice = fields.Selection(
        PIPER_VOICES, string="Voicemail Voice",
        help="Speak this group's own shared voicemail greeting using "
             "a self-hosted Piper voice instead of the plain built-in "
             "one - only relevant when \"If Nobody Answers\" is set "
             "to this group's own shared voicemail box. Only applies "
             "to the text-to-speech greeting, not a custom uploaded "
             "recording. Requires your admin to have configured "
             "Piper's own server URL. Leave blank to keep the plain "
             "voice.")
    voicemail_piper_speaker_id = fields.Integer(
        string="Speaker ID",
        help="Only used for LibriTTS-R, which has 904 different "
             "speakers (id 0-903) - leave blank for its own default "
             "speaker. There's no built-in way to preview a speaker "
             "by ear before picking one; see signalwire_voip_piper_tts's "
             "README for how to try a few via Piper's own /synthesize "
             "endpoint directly. Ignored for LJSpeech, which only has "
             "one voice.")

    @api.constrains('voicemail_piper_voice', 'voicemail_piper_speaker_id')
    def _check_piper_speaker_id(self):
        for group in self:
            if not group.voicemail_piper_speaker_id:
                continue
            if group.voicemail_piper_voice != MULTI_SPEAKER_VOICE:
                raise ValidationError(_(
                    "Speaker ID only applies to LibriTTS-R - leave it "
                    "blank for LJSpeech, which has just one voice."))
            if not (0 <= group.voicemail_piper_speaker_id <= MULTI_SPEAKER_MAX_ID):
                raise ValidationError(_(
                    "Speaker ID must be between 0 and %(max)s for LibriTTS-R.",
                    max=MULTI_SPEAKER_MAX_ID))

    def _sync_piper_audio(self):
        # Not wrapped in _() - see signalwire_ivr_menu.py's own note on
        # why the cache key has to match controllers/main.py's exact
        # literal, untranslated.
        cache = self.env['signalwire.piper.audio.cache']
        for group in self:
            if not group.voicemail_piper_voice:
                continue
            cache.get_or_synthesize(
                group.voicemail_piper_voice,
                group.voicemail_greeting_text or '',
                group.voicemail_piper_speaker_id or None)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sync_piper_audio()
        return records

    def write(self, vals):
        res = super().write(vals)
        if 'voicemail_piper_voice' in vals or 'voicemail_greeting_text' in vals or \
                'voicemail_piper_speaker_id' in vals:
            self._sync_piper_audio()
        return res
