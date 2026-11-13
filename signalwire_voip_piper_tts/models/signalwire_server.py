# -*- coding: utf-8 -*-
from odoo import fields, models

from .piper_client import PiperClient


class SignalWireServer(models.Model):
    _inherit = 'signalwire.server'

    piper_url = fields.Char(
        string="Voice Server URL",
        help="Where the natural-voice server is reachable, e.g. "
             "\"http://localhost:5000\". Leave blank to use the plain "
             "built-in voice for every greeting. The voice server has no "
             "login of its own, so use a private address, never a "
             "public one.")

    def _get_piper_client(self):
        self.ensure_one()
        return PiperClient(self.piper_url)
