# -*- coding: utf-8 -*-
from urllib.parse import quote

from odoo import http
from odoo.http import request

from odoo.addons.signalwire_sms.controllers.portal import SignalWireSmsPortal


class SignalWire10DLCPortal(SignalWireSmsPortal):
    """Extends signalwire_sms's own portal controller (not just its
    view) - reuses _my_numbers() directly rather than duplicating that
    same partner-scoped query a third time in this repo.
    """

    def _my_brand(self):
        partner = request.env.user.partner_id
        return request.env['signalwire.brand'].search(
            [('partner_id', '=', partner.id)], limit=1, order='create_date desc')

    @http.route(['/my/sms/compliance'], type='http', auth='user', methods=['GET'], website=True)
    def portal_sms_compliance_form(self, **kw):
        values = self._prepare_portal_layout_values()
        values.update({
            'brand': self._my_brand().sudo(),
            'page_name': 'sms',
            'error': kw.get('error'),
        })
        return request.render('signalwire_10dlc.portal_sms_compliance', values)

    @http.route(['/my/sms/compliance'], type='http', auth='user', methods=['POST'], website=True)
    def portal_sms_compliance_submit(self, **post):
        partner = request.env.user.partner_id
        if self._my_brand():
            return request.redirect('/my/sms')

        csp_self_registered = bool(post.get('csp_self_registered'))
        brand_vals = {
            'partner_id': partner.id,
            'name': post.get('name'),
            'company_name': post.get('company_name') or partner.name,
            'csp_self_registered': csp_self_registered,
            'csp_brand_reference': post.get('csp_brand_reference'),
            'contact_email': post.get('contact_email') or partner.email,
            'contact_phone': post.get('contact_phone') or partner.phone,
            'ein_issuing_country': post.get('ein_issuing_country') or 'US',
            'legal_entity_type': post.get('legal_entity_type'),
            'ein': post.get('ein'),
            'company_address': post.get('company_address'),
            'company_website': post.get('company_website'),
            'company_vertical': post.get('company_vertical'),
        }
        brand = request.env['signalwire.brand'].sudo().create(brand_vals)

        try:
            brand.action_submit()
        except Exception as exc:
            brand.unlink()
            return request.redirect(f'/my/sms/compliance?error={quote(str(exc))}')

        campaign_vals = {
            'brand_id': brand.id,
            'name': post.get('campaign_name') or brand.name,
            'sms_use_case': post.get('sms_use_case'),
            'description': post.get('description'),
            'message_flow': post.get('message_flow'),
            'sample1': post.get('sample1'),
            'sample2': post.get('sample2'),
            'sample3': post.get('sample3'),
            'opt_in_message': post.get('opt_in_message'),
            'opt_out_message': post.get('opt_out_message'),
            'help_message': post.get('help_message'),
        }
        campaign = request.env['signalwire.campaign'].sudo().create(campaign_vals)
        try:
            campaign.action_submit()
        except Exception as exc:
            return request.redirect(f'/my/sms/compliance?error={quote(str(exc))}')

        return request.redirect('/my/sms')

    @http.route(
        ['/my/sms/<int:phone_number_id>/enable_sms'],
        type='http', auth='user', methods=['POST'], website=True)
    def portal_sms_enable(self, phone_number_id, **kw):
        number = self._my_numbers().filtered(lambda n: n.id == int(phone_number_id))
        if not number:
            return request.redirect('/my/sms')

        if not self._my_brand():
            return request.redirect('/my/sms/compliance')

        number.sudo().action_request_sms_enablement()
        return request.redirect('/my/sms')
