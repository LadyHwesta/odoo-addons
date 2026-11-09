# -*- coding: utf-8 -*-
import logging

from odoo import tools
from odoo.http import request, route

from odoo.addons.website_mass_mailing.controllers.main import MassMailController

_logger = logging.getLogger(__name__)


class WelcomeMassMailController(MassMailController):

    @route()
    def subscribe(self, list_id, value, subscription_type, **post):
        mailing_list = request.env['mailing.list'].sudo().browse(int(list_id)).exists()
        welcome = mailing_list.welcome_mailing_id if mailing_list else False
        if not welcome or subscription_type != 'email':
            return super().subscribe(list_id, value, subscription_type, **post)

        email = tools.parse_contact_from_email(value)[1]
        was_subscribed = bool(self._welcome_subscription(mailing_list, email))
        result = super().subscribe(list_id, value, subscription_type, **post)
        subscription = self._welcome_subscription(mailing_list, email)
        if result.get('toast_type') == 'success' and subscription and not was_subscribed:
            try:
                welcome.sudo()._send_welcome(subscription.contact_id)
            except Exception:
                # The signup itself worked; a welcome email problem mustn't undo it.
                _logger.exception("Welcome email for mailing list %s failed", mailing_list.id)
        return result

    @staticmethod
    def _welcome_subscription(mailing_list, email):
        """The address's active (not opted-out) subscription to the list, if any."""
        if not email:
            return request.env['mailing.subscription']
        return request.env['mailing.subscription'].sudo().search([
            ('list_id', '=', mailing_list.id),
            ('contact_id.email', '=', email),
            ('opt_out', '=', False),
        ], limit=1)
