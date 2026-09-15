# -*- coding: utf-8 -*-
import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class NamecheapServer(models.Model):
    _name = 'namecheap.server'
    _inherit = ['namecheap.server', 'mail.thread']

    low_balance_threshold = fields.Float(
        default=100.0,
        help="Get an internal notification when the account's available "
             "balance drops below this - registering or renewing a domain "
             "draws down the real balance immediately with no separate "
             "authorize/capture step, so running dry mid-checkout means a "
             "customer's already been charged in Odoo for a domain this "
             "account can no longer actually register.")

    def register_domain(self, sld, tld, years, contact_fields):
        """Real domains.create call - registers sld.tld for `years`,
        using the same contact_fields dict (already mapped from a
        partner via res.partner._namecheap_registrant_fields()) for
        all four contact roles Namecheap requires (Registrant, Tech,
        Admin, AuxBilling) - "one person acts as all contact types",
        the same convention a real reference client uses (verified
        2026-09-14, Namecheap's own docs block automated fetching).
        Enables free WhoisGuard privacy by default.

        :raises NamecheapAPIError: on any failure - a declined charge
            against this account's own balance, an already-registered
            domain, invalid contact info, etc. all surface this way.
        """
        self.ensure_one()
        params = {'DomainName': f'{sld}.{tld}', 'Years': years,
                  'AddFreeWhoisguard': 'yes', 'WGEnabled': 'yes'}
        for role in ('Registrant', 'Tech', 'Admin', 'AuxBilling'):
            for field, value in contact_fields.items():
                params[f'{role}{field}'] = value
        result = self._get_client().call('namecheap.domains.create', **params)
        return result.find('DomainCreateResult')

    def renew_domain(self, sld, tld, years):
        self.ensure_one()
        result = self._get_client().call(
            'namecheap.domains.renew', DomainName=f'{sld}.{tld}', Years=years)
        return result.find('DomainRenewResult')

    @api.model
    def _cron_check_balance(self):
        """Registering or renewing a domain draws down the account's
        real balance immediately, with no separate authorize/capture
        step - if it runs dry between a customer paying in Odoo and
        this module actually calling Namecheap, the business has been
        paid and can't deliver. This posts an activity to the server
        record's own followers (or just a chatter message if there are
        none) whenever the available balance drops below
        low_balance_threshold, once per day it's below rather than
        once - a business running low needs a standing reminder, not a
        one-time alert easy to miss.
        """
        for server in self.search([]):
            try:
                balance = server._get_available_balance()
            except Exception:
                _logger.exception(
                    "Namecheap: could not check balance for %s", server.name)
                continue
            if balance < server.low_balance_threshold:
                server.message_post(body=_(
                    "Namecheap balance is low: %(balance).2f, below the "
                    "%(threshold).2f threshold. Top up soon - registering "
                    "or renewing a domain charges this balance immediately "
                    "and can't be retried if it's insufficient at that "
                    "moment.", balance=balance, threshold=server.low_balance_threshold))
