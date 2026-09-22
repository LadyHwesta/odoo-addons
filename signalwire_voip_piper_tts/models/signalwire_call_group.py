# -*- coding: utf-8 -*-
from odoo import api, fields, models

from .signalwire_ivr_menu import PIPER_VOICES

# Kept in sync with SignalWireVoiceController.DEFAULT_VOICEMAIL_GREETING
# - a call group's own shared voicemail box always uses this same
# generic greeting (no per-group custom text, unchanged scope
# boundary from the original shared-mailbox work), so that's the one
# string this model ever needs to get synthesized.
DEFAULT_VOICEMAIL_GREETING = "Please leave a message after the tone."


class SignalWireCallGroup(models.Model):
    _inherit = 'signalwire.call.group'

    voicemail_piper_voice = fields.Selection(
        PIPER_VOICES, string="Voicemail Voice",
        help="Speak this group's own shared voicemail greeting using "
             "a self-hosted Piper voice instead of the plain built-in "
             "one - only relevant when \"If Nobody Answers\" is set "
             "to this group's own shared voicemail box. Requires your "
             "admin to have configured Piper's own server URL. Leave "
             "blank to keep the plain voice.")

    def _sync_piper_audio(self):
        # Not wrapped in _() - see signalwire_ivr_menu.py's own note on
        # why the cache key has to match controllers/main.py's exact
        # literal, untranslated.
        cache = self.env['signalwire.piper.audio.cache']
        for group in self:
            if not group.voicemail_piper_voice:
                continue
            cache.get_or_synthesize(group.voicemail_piper_voice, DEFAULT_VOICEMAIL_GREETING)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sync_piper_audio()
        return records

    def write(self, vals):
        res = super().write(vals)
        if 'voicemail_piper_voice' in vals:
            self._sync_piper_audio()
        return res
