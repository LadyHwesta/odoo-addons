# -*- coding: utf-8 -*-
from odoo import fields, http
from odoo.http import request

from odoo.addons.portal.controllers.portal import CustomerPortal

# Keys a customer can create per hour: enough for a few calls, not for
# filling the table.
MAX_KEYS_PER_HOUR = 10


class SupportKeyPortal(CustomerPortal):

    @http.route('/my/support-key', type='http', auth='user', website=True, methods=['GET'])
    def support_key(self, **kw):
        return request.render('helpdesk_support_verification.portal_support_key', {
            'page_name': 'support_key',
        })

    @http.route('/my/support-key', type='http', auth='user', website=True, methods=['POST'])
    def support_key_new(self, **kw):
        partner = request.env.user.partner_id
        codes = request.env['support.verification.code']
        values = {'page_name': 'support_key'}
        if codes._count_recent(partner, 'support_key') >= MAX_KEYS_PER_HOUR:
            values['too_many'] = True
        else:
            key, expires_at = codes._issue(partner, 'support_key')
            values.update(key=key, expires_at=fields.Datetime.context_timestamp(
                request.env.user, expires_at).strftime('%H:%M'))
        response = request.render('helpdesk_support_verification.portal_support_key', values)
        response.headers['Cache-Control'] = 'no-store'
        return response
