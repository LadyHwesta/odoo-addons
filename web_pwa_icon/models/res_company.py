# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    pwa_icon = fields.Image(
        string='Progressive Web App Icon',
        max_width=512, max_height=512,
        help="Shown as the app icon when someone installs Odoo as an app "
             "(Chrome/Edge \"Install app\", Android \"Add to Home Screen\", "
             "iOS Safari \"Add to Home Screen\"). Use a square image, at "
             "least 512x512, ideally with no transparency - some platforms "
             "mask it into a circle or squircle. Leave empty to keep "
             "Odoo's own icon.",
    )
