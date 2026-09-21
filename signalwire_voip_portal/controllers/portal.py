# -*- coding: utf-8 -*-
from odoo import _
from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.http import request, route


class SignalWirePortalSupport(CustomerPortal):

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'signalwire_callback_request_count' in counters:
            partner = request.env.user.partner_id
            if partner.signalwire_portal_support_tier != 'none':
                values['signalwire_callback_request_count'] = request.env[
                    'signalwire.callback_request'
                ].search_count([('partner_id', '=', partner.id)])
        return values

    @route(
        '/my/support/call', type='http', auth='user', website=True,
        methods=['GET'])
    def support_call_form(self, **kwargs):
        """The gate lives here, server-side, not just in the template
        that hides/shows the home-page card - a portal user with
        tier='none' hitting this URL directly still gets refused,
        matching this project's own "never trust that hiding a button
        is enough" discipline (the receptionist panel's own backend
        methods already work this way).
        """
        partner = request.env.user.partner_id
        if partner.signalwire_portal_support_tier == 'none':
            return request.not_found()
        requests_ = request.env['signalwire.callback_request'].search(
            [('partner_id', '=', partner.id)], limit=20)
        return request.render('signalwire_voip_portal.portal_support_call', {
            'page_name': 'signalwire_support_call',
            'partner': partner,
            'requests': requests_,
        })

    @route(
        '/my/support/call/submit', type='http', auth='user', website=True,
        methods=['POST'], csrf=True)
    def support_call_submit(self, phone_number=None, note=None, **kwargs):
        partner = request.env.user.partner_id
        if partner.signalwire_portal_support_tier == 'none':
            return request.not_found()
        if not (phone_number or '').strip():
            return request.redirect('/my/support/call')
        request.env['signalwire.callback_request'].sudo().create({
            'partner_id': partner.id,
            'phone_number': phone_number.strip(),
            'note': (note or '').strip() or False,
        })
        return request.redirect('/my/support/call')
