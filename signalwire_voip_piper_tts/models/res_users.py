# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .signalwire_ivr_menu import MULTI_SPEAKER_MAX_ID, MULTI_SPEAKER_VOICE, PIPER_VOICES


class ResUsers(models.Model):
    _inherit = 'res.users'

    signalwire_voicemail_piper_voice = fields.Selection(
        PIPER_VOICES, string="Voicemail Voice",
        help="Speak your voicemail greeting using a self-hosted Piper "
             "voice instead of the plain built-in one - only applies "
             "to the text-to-speech greeting, not a custom uploaded "
             "recording. Requires your admin to have configured "
             "Piper's own server URL. Leave blank to keep the plain "
             "voice.")
    signalwire_voicemail_piper_speaker_id = fields.Integer(
        string="Speaker ID",
        help="Only used for LibriTTS-R, which has 904 different "
             "speakers (id 0-903) - leave blank for its own default "
             "speaker. There's no built-in way to preview a speaker "
             "by ear before picking one; see signalwire_voip_piper_tts's "
             "README for how to try a few via Piper's own /synthesize "
             "endpoint directly. Ignored for LJSpeech, which only has "
             "one voice.")

    @property
    def SELF_READABLE_FIELDS(self):
        return super().SELF_READABLE_FIELDS + [
            'signalwire_voicemail_piper_voice', 'signalwire_voicemail_piper_speaker_id']

    @property
    def SELF_WRITEABLE_FIELDS(self):
        return super().SELF_WRITEABLE_FIELDS + [
            'signalwire_voicemail_piper_voice', 'signalwire_voicemail_piper_speaker_id']

    @api.constrains('signalwire_voicemail_piper_voice', 'signalwire_voicemail_piper_speaker_id')
    def _check_piper_speaker_id(self):
        for user in self:
            if not user.signalwire_voicemail_piper_speaker_id:
                continue
            if user.signalwire_voicemail_piper_voice != MULTI_SPEAKER_VOICE:
                raise ValidationError(_(
                    "Speaker ID only applies to LibriTTS-R - leave it "
                    "blank for LJSpeech, which has just one voice."))
            if not (0 <= user.signalwire_voicemail_piper_speaker_id <= MULTI_SPEAKER_MAX_ID):
                raise ValidationError(_(
                    "Speaker ID must be between 0 and %(max)s for LibriTTS-R.",
                    max=MULTI_SPEAKER_MAX_ID))

    def _sync_piper_audio(self):
        cache = self.env['signalwire.piper.audio.cache']
        for user in self:
            if not user.signalwire_voicemail_piper_voice:
                continue
            cache.get_or_synthesize(
                user.signalwire_voicemail_piper_voice,
                user.signalwire_voicemail_greeting_text or '',
                user.signalwire_voicemail_piper_speaker_id or None)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sync_piper_audio()
        return records

    def write(self, vals):
        res = super().write(vals)
        if 'signalwire_voicemail_piper_voice' in vals or \
                'signalwire_voicemail_greeting_text' in vals or \
                'signalwire_voicemail_piper_speaker_id' in vals:
            self._sync_piper_audio()
        return res
