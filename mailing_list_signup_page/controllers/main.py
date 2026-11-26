# -*- coding: utf-8 -*-
import logging

from odoo import http, tools
from odoo.exceptions import UserError, ValidationError
from odoo.http import request

from odoo.addons.mailing_list_welcome.controllers.main import WelcomeMassMailController
from odoo.addons.website_mass_mailing.controllers.main import MassMailController

_logger = logging.getLogger(__name__)


class MailingListSignupPage(http.Controller):

    @http.route('/join/<string:slug>', type='http', auth='public', website=True,
                sitemap=False, methods=['GET', 'POST'])
    def signup_page(self, slug, **post):
        mailing_list = request.env['mailing.list'].sudo().search([
            ('signup_page_slug', '=', slug), ('is_public', '=', True)], limit=1)
        if not mailing_list:
            raise request.not_found()
        kiosk = bool(post.get('kiosk'))
        form_url = f'/join/{slug}' + ('?kiosk=1' if kiosk else '')
        values = {
            'mailing_list': mailing_list,
            'kiosk': kiosk,
            'form_url': form_url,
            'thanks': False,
            'error': False,
            'name': '',
            'email': '',
        }
        if request.httprequest.method == 'GET':
            values['thanks'] = bool(post.get('thanks'))
            return request.render('mailing_list_signup_page.signup_page', values)

        name = (post.get('name') or '').strip()[:128]
        email = (post.get('email') or '').strip()[:254]
        thanks_url = f'/join/{slug}?thanks=1' + ('&kiosk=1' if kiosk else '')
        if post.get('nickname'):
            # Only a bot fills in the hidden field: look the same, do nothing.
            return request.redirect(thanks_url)
        values.update(name=name, email=email)
        try:
            request.env['ir.http']._verify_request_recaptcha_token('mailing_list_signup')
        except (UserError, ValidationError) as e:
            values['error'] = str(e)
            return request.render('mailing_list_signup_page.signup_page', values)
        normalized = tools.email_normalize(email)
        if not normalized:
            values['error'] = request.env._("That email address doesn't look right. Could you check it?")
            return request.render('mailing_list_signup_page.signup_page', values)

        was_subscribed = bool(WelcomeMassMailController._welcome_subscription(mailing_list, normalized))
        refused = MassMailController.subscribe_to_newsletter(
            'email', normalized, mailing_list.id, 'email', address_name=name or None)
        if refused:
            raise request.not_found()
        if kiosk:
            # Odoo remembers the last signup in the visitor's session and would show
            # the next person "already subscribed": forget it on a shared device.
            request.session.pop('mass_mailing_email', None)
        welcome = mailing_list.welcome_mailing_id
        if welcome and not was_subscribed:
            subscription = WelcomeMassMailController._welcome_subscription(mailing_list, normalized)
            if subscription:
                try:
                    welcome.sudo()._send_welcome(subscription.contact_id)
                except Exception:
                    # The signup itself worked; a welcome email problem mustn't undo it.
                    _logger.exception("Welcome email for mailing list %s failed", mailing_list.id)
        return request.redirect(thanks_url)
