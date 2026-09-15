# -*- coding: utf-8 -*-
from odoo import fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    telehealth_video_tier = fields.Selection(
        [('basic', 'Basic (built-in)'), ('premium', 'Premium')],
        default='basic', required=True,
        help="Which video backend this provider's own bookings use. "
             "Basic is Odoo's own built-in (Discuss) video calling - "
             "free, works well for one-to-one calls, no recording, "
             "and needs a TURN server configured somewhere (either "
             "here or via Twilio credentials) to reliably connect "
             "callers on restrictive networks. Premium needs a "
             "bridge module installed (e.g. "
             "telehealth_booking_signalwire) to actually mean "
             "anything - with none installed, this setting has no "
             "effect and every booking still uses Basic.")
