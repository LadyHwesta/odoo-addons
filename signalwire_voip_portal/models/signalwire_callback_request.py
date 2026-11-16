# -*- coding: utf-8 -*-
from odoo import models


class SignalWireCallbackRequest(models.Model):
    """Moved to signalwire_voip_click2call in 19.0.4.16.0, so callers on
    hold, portal customers and receptionists share one list of callback
    requests. This module still adds the portal side (the request form,
    the portal access rule) and keeps this class so the model stays
    registered under this module's name too: its access rows and record
    rules refer to model_signalwire_callback_request."""
    _inherit = 'signalwire.callback_request'
