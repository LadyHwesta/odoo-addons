# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal


class HestiaCPPortal(CustomerPortal):

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if "hestiacp_account_count" in counters:
            partner = request.env.user.partner_id
            values["hestiacp_account_count"] = request.env["hestiacp.account"].search_count([
                ("partner_id", "=", partner.id),
                ("state", "!=", "terminated"),
            ])
        return values

    @http.route(["/my/hosting"], type="http", auth="user", website=True)
    def portal_my_hosting(self, **kw):
        partner = request.env.user.partner_id
        # searched as the user so the record rule enforces "own accounts
        # only"; rendered sudo so the template can read the linked
        # package/server names without granting portal users blanket
        # product.template/hestiacp.server access
        accounts = request.env["hestiacp.account"].search(
            [("partner_id", "=", partner.id)], order="create_date desc")
        values = self._prepare_portal_layout_values()
        values.update({
            "accounts": accounts.sudo(),
            "page_name": "hosting",
            "default_url": "/my/hosting",
        })
        return request.render("hestiacp_hosting.portal_my_hosting", values)
