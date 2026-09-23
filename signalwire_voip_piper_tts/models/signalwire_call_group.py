# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .libritts_r_speakers import LIBRITTS_R_SPEAKERS
from .signalwire_ivr_menu import MULTI_SPEAKER_VOICE, PIPER_VOICES


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
    voicemail_piper_speaker_id = fields.Selection(
        LIBRITTS_R_SPEAKERS, string="Speaker",
        help="Only used for LibriTTS-R, which has 904 different "
             "speakers, each named after the LibriVox reader whose "
             "recordings trained it - leave blank for its own default "
             "speaker. This is Piper's own real per-speaker metadata, "
             "not a curated pick - nobody's actually listened to all "
             "904, so a name here is not a guarantee of quality. "
             "Ignored for LJSpeech, which only has one voice.")

    @api.constrains('voicemail_piper_voice', 'voicemail_piper_speaker_id')
    def _check_piper_speaker_id(self):
        for group in self:
            if group.voicemail_piper_speaker_id and \
                    group.voicemail_piper_voice != MULTI_SPEAKER_VOICE:
                raise ValidationError(_(
                    "Speaker only applies to LibriTTS-R - leave it "
                    "blank for LJSpeech, which has just one voice."))

    def _sync_piper_audio(self):
        # Not wrapped in _() - see signalwire_ivr_menu.py's own note on
        # why the cache key has to match controllers/main.py's exact
        # literal, untranslated.
        cache = self.env['signalwire.piper.audio.cache']
        for group in self:
            if not group.voicemail_piper_voice:
                continue
            speaker_id = int(group.voicemail_piper_speaker_id) \
                if group.voicemail_piper_speaker_id else None
            cache.get_or_synthesize(
                group.voicemail_piper_voice,
                group.voicemail_greeting_text or '',
                speaker_id)

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
