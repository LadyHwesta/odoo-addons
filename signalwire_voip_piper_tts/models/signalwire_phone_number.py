# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .libritts_r_speakers import LIBRITTS_R_SPEAKERS
from .signalwire_ivr_menu import MULTI_SPEAKER_VOICE, PIPER_VOICES


class SignalWirePhoneNumber(models.Model):
    _inherit = 'signalwire.phone_number'

    hold_piper_voice = fields.Selection(
        PIPER_VOICES, string="Hold Message Voice",
        help="Speak the receptionist-park hold message using a self-"
             "hosted Piper voice instead of the plain built-in one. "
             "Requires your admin to have configured Piper's own "
             "server URL. Leave blank to keep the plain voice.")
    hold_piper_speaker_id = fields.Selection(
        LIBRITTS_R_SPEAKERS, string="Speaker",
        help="Only used for LibriTTS-R, which has 904 different "
             "speakers, each named after the LibriVox reader whose "
             "recordings trained it - leave blank for its own default "
             "speaker. Ignored for LJSpeech, which only has one voice.")

    @api.constrains('hold_piper_voice', 'hold_piper_speaker_id')
    def _check_hold_piper_speaker_id(self):
        for number in self:
            if number.hold_piper_speaker_id and \
                    number.hold_piper_voice != MULTI_SPEAKER_VOICE:
                raise ValidationError(_(
                    "Speaker only applies to LibriTTS-R - leave it "
                    "blank for LJSpeech, which has just one voice."))

    def _sync_hold_piper_audio(self):
        cache = self.env['signalwire.piper.audio.cache']
        for number in self:
            if not number.hold_piper_voice:
                continue
            speaker_id = int(number.hold_piper_speaker_id) \
                if number.hold_piper_speaker_id else None
            cache.get_or_synthesize(
                number.hold_piper_voice, number.hold_message_text or '', speaker_id)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sync_hold_piper_audio()
        return records

    def write(self, vals):
        res = super().write(vals)
        if 'hold_piper_voice' in vals or 'hold_message_text' in vals or \
                'hold_piper_speaker_id' in vals:
            self._sync_hold_piper_audio()
        return res
