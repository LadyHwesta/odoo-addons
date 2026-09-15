# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal


class SignalWireSmsPortal(CustomerPortal):

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'signalwire_number_count' in counters:
            partner = request.env.user.partner_id
            values['signalwire_number_count'] = request.env['signalwire.phone_number'].search_count(
                [('subproject_id.partner_id', '=', partner.id)])
        return values

    def _my_numbers(self):
        """Every signalwire.phone_number belonging to a subproject
        that's actually this portal user's own - searched as the
        portal user so the record rule enforces that, not just this
        domain (belt and suspenders, same as hestiacp_hosting's own
        portal controller).
        """
        partner = request.env.user.partner_id
        return request.env['signalwire.phone_number'].search(
            [('subproject_id.partner_id', '=', partner.id)])

    @http.route(['/my/sms'], type='http', auth='user', website=True)
    def portal_my_sms(self, **kw):
        numbers = self._my_numbers()
        values = self._prepare_portal_layout_values()
        values.update({
            'numbers': numbers.sudo(),
            'page_name': 'sms',
            'default_url': '/my/sms',
        })
        return request.render('signalwire_sms.portal_my_sms', values)

    @http.route(['/my/sms/send'], type='http', auth='user', methods=['POST'], website=True)
    def portal_sms_send(self, phone_number_id=None, to=None, body=None, **kw):
        number = self._my_numbers().filtered(lambda n: n.id == int(phone_number_id or 0))
        if number and to and body:
            number.sudo().send_sms(to, body)
        return request.redirect('/my/sms')

    @http.route(
        ['/my/sms/webhook'], type='http', auth='user', methods=['POST'], website=True)
    def portal_sms_webhook(self, phone_number_id=None, sms_webhook_url=None, **kw):
        number = self._my_numbers().filtered(lambda n: n.id == int(phone_number_id or 0))
        if number:
            number.sudo().sms_webhook_url = sms_webhook_url or False
        return request.redirect('/my/sms')

    @http.route(
        ['/my/sms/token/issue'], type='http', auth='user', methods=['POST'], website=True)
    def portal_sms_token_issue(self, phone_number_id=None, **kw):
        number = self._my_numbers().filtered(lambda n: n.id == int(phone_number_id or 0))
        if number:
            number.sudo().subproject_id.action_issue_customer_token()
        return request.redirect('/my/sms')

    @http.route(
        ['/my/sms/token/revoke'], type='http', auth='user', methods=['POST'], website=True)
    def portal_sms_token_revoke(self, token_id=None, **kw):
        partner = request.env.user.partner_id
        token = request.env['signalwire.customer.token'].sudo().search([
            ('id', '=', int(token_id or 0)),
            ('subproject_id.partner_id', '=', partner.id),
        ])
        if token:
            token.action_revoke()
        return request.redirect('/my/sms')
