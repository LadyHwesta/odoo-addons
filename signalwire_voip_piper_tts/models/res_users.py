# -*- coding: utf-8 -*-
from odoo import api, fields, models

from .signalwire_ivr_menu import PIPER_VOICES


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

    @property
    def SELF_READABLE_FIELDS(self):
        return super().SELF_READABLE_FIELDS + ['signalwire_voicemail_piper_voice']

    @property
    def SELF_WRITEABLE_FIELDS(self):
        return super().SELF_WRITEABLE_FIELDS + ['signalwire_voicemail_piper_voice']

    def _sync_piper_audio(self):
        cache = self.env['signalwire.piper.audio.cache']
        for user in self:
            if not user.signalwire_voicemail_piper_voice:
                continue
            cache.get_or_synthesize(
                user.signalwire_voicemail_piper_voice,
                user.signalwire_voicemail_greeting_text or '')

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sync_piper_audio()
        return records

    def write(self, vals):
        res = super().write(vals)
        if 'signalwire_voicemail_piper_voice' in vals or \
                'signalwire_voicemail_greeting_text' in vals:
            self._sync_piper_audio()
        return res
