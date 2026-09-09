# -*- coding: utf-8 -*-
from datetime import date

from odoo import api, fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    @api.model
    def _cron_roll_membership_year(self):
        """On/after New Year, move any prorated membership product whose
        period has ended into the current calendar year, so
        `membership_prorate` keeps billing new members the right fraction
        without an admin remembering to edit the dates every January."""
        today = fields.Date.context_today(self)
        stale = self.search([
            ("membership", "=", True),
            ("membership_prorate", "=", True),
            ("membership_date_to", "<", today),
        ])
        for product in stale:
            product.write({
                "membership_date_from": date(today.year, 1, 1),
                "membership_date_to": date(today.year, 12, 31),
            })
        return len(stale)
