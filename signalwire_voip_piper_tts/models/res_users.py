# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .libritts_r_speakers import LIBRITTS_R_SPEAKERS
from .signalwire_ivr_menu import MULTI_SPEAKER_VOICE, PIPER_VOICES


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
    signalwire_voicemail_piper_speaker_id = fields.Selection(
        LIBRITTS_R_SPEAKERS, string="Speaker",
        help="Only used for LibriTTS-R, which has 904 different "
             "speakers, each named after the LibriVox reader whose "
             "recordings trained it - leave blank for its own default "
             "speaker. This is Piper's own real per-speaker metadata, "
             "not a curated pick - nobody's actually listened to all "
             "904, so a name here is not a guarantee of quality. "
             "Ignored for LJSpeech, which only has one voice.")

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
            if user.signalwire_voicemail_piper_speaker_id and \
                    user.signalwire_voicemail_piper_voice != MULTI_SPEAKER_VOICE:
                raise ValidationError(_(
                    "Speaker only applies to LibriTTS-R - leave it "
                    "blank for LJSpeech, which has just one voice."))

    def _sync_piper_audio(self):
        cache = self.env['signalwire.piper.audio.cache']
        for user in self:
            if not user.signalwire_voicemail_piper_voice:
                continue
            speaker_id = int(user.signalwire_voicemail_piper_speaker_id) \
                if user.signalwire_voicemail_piper_speaker_id else None
            cache.get_or_synthesize(
                user.signalwire_voicemail_piper_voice,
                user.signalwire_voicemail_greeting_text or '',
                speaker_id)

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
