# -*- coding: utf-8 -*-
from odoo import fields, http
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal


class ClubPortal(CustomerPortal):

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if "club_attention_count" in counters:
            partner = request.env.user.partner_id
            attention = 0
            if partner.ham_license_expiring_soon:
                attention += 1
            attention += request.env["club.equipment.loan"].search_count([
                ("borrower_id", "=", partner.id), ("is_overdue", "=", True)])
            values["club_attention_count"] = attention
        return values

    @staticmethod
    def _selection_label(record, field_name):
        value = record[field_name]
        if not value:
            return ""
        # membership_state's selection is a callable, so resolve it properly
        # rather than dict()-ing the raw attribute.
        resolved = record._fields[field_name]._description_selection(record.env)
        return dict(resolved).get(value, value)

    @http.route(["/my/club"], type="http", auth="user", website=True)
    def my_club(self, **kw):
        partner = request.env.user.partner_id
        loans = request.env["club.equipment.loan"].search([
            ("borrower_id", "=", partner.id),
            ("state", "in", ("reserved", "out")),
        ], order="due_date")
        volunteering = request.env["event.volunteer.assignment"].search([
            ("partner_id", "=", partner.id),
            ("state", "=", "confirmed"),
            ("event_date_begin", ">=", fields.Datetime.now()),
        ], order="event_date_begin")
        values = self._prepare_portal_layout_values()
        values.update({
            "partner": partner,
            "membership_state_label": self._selection_label(partner, "membership_state"),
            "license_class_label": self._selection_label(partner, "ham_license_class"),
            "loans": loans.sudo(),
            "volunteering": volunteering.sudo(),
            "page_name": "club",
            "default_url": "/my/club",
        })
        return request.render("club_membership.portal_my_club", values)
