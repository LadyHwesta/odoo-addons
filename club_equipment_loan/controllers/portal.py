# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal


class EquipmentLoanPortal(CustomerPortal):

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if "equipment_loan_count" in counters:
            partner = request.env.user.partner_id
            values["equipment_loan_count"] = request.env["club.equipment.loan"].search_count([
                ("borrower_id", "=", partner.id),
                ("state", "in", ("reserved", "out")),
            ])
        return values

    @http.route(["/my/loans"], type="http", auth="user", website=True)
    def portal_my_loans(self, **kw):
        partner = request.env.user.partner_id
        # searched as the user so the record rule enforces "own loans only";
        # rendered sudo so the template can read the linked equipment's name
        # without granting portal users blanket maintenance.equipment access.
        loans = request.env["club.equipment.loan"].search(
            [("borrower_id", "=", partner.id)], order="checkout_date desc")
        values = self._prepare_portal_layout_values()
        values.update({
            "loans": loans.sudo(),
            "page_name": "equipment_loan",
            "default_url": "/my/loans",
        })
        return request.render("club_equipment_loan.portal_my_loans", values)
