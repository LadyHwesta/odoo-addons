# -*- coding: utf-8 -*-
from odoo import fields, models

from .piper_client import PiperClient


class SignalWireServer(models.Model):
    _inherit = 'signalwire.server'

    piper_url = fields.Char(
        string="Piper TTS Server URL",
        help="Where your own self-hosted Piper TTS server "
             "(python3 -m piper.http_server) is reachable, e.g. "
             "\"http://localhost:5000\". Leave blank to skip Piper "
             "entirely - every IVR menu/voicemail greeting falls "
             "back to the plain built-in voice. Piper's own server "
             "has no authentication of its own, so this should be a "
             "private/internal address, never a public one.")

    def _get_piper_client(self):
        self.ensure_one()
        return PiperClient(self.piper_url)
