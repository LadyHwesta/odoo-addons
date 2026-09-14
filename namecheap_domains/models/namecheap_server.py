# -*- coding: utf-8 -*-
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .namecheap_api import NamecheapClient

_logger = logging.getLogger(__name__)


class NamecheapServer(models.Model):
    """One Namecheap reseller account's connection settings, plus the
    business policy (markup %) applied on top of whatever it charges -
    kept on the same record as the credentials, matching how
    hestiacp.server holds this integration's per-connection settings,
    since in practice there's one Namecheap account for the business.
    """
    _name = 'namecheap.server'
    _description = 'Namecheap Reseller Account'

    name = fields.Char(required=True, default='Namecheap')
    api_user = fields.Char(
        string="API User", required=True, groups="base.group_system",
        help="The Namecheap account username API access was enabled "
             "on - almost always the same as Username below.")
    api_key = fields.Char(
        string="API Key", required=True, groups="base.group_system",
        help="Generated under Namecheap's Profile > Tools > API Access "
             "once enabled. Production API access itself requires the "
             "account to have 20+ domains, or a $50+ balance, or $50+ "
             "spent in the last 2 years - the sandbox has no such gate.")
    username = fields.Char(
        string="Username", required=True, groups="base.group_system",
        help="Almost always the same as API User - kept separate "
             "because Namecheap's own API does, to support reseller "
             "sub-accounts.")
    client_ip = fields.Char(
        string="Whitelisted IP", required=True, groups="base.group_system",
        help="This Odoo server's own outbound IP. Must be added to "
             "this account's API IP whitelist (Namecheap: Profile > "
             "Tools > API Access > Whitelisted IPs, up to 10 IPv4 "
             "addresses) before any call will succeed - otherwise "
             "every call fails with an error that looks like a bad "
             "key rather than a missing whitelist entry.")
    sandbox = fields.Boolean(
        default=True,
        help="Use api.sandbox.namecheap.com (fake domains, fake money, "
             "a separate account signup at sandbox.namecheap.com "
             "unconnected to the real one) instead of the production "
             "API. Leave this on until everything's been tested end "
             "to end - nothing here should touch a real balance or "
             "register a real domain before then.")
    markup_percentage = fields.Float(
        string="Markup %", default=20.0, required=True,
        help="Applied over Namecheap's own registration/renewal price "
             "for every TLD - a single global percentage, not set per "
             "TLD, so it scales naturally even though TLD costs vary "
             "a lot (e.g. a $9 .com and a $40 ccTLD both get the same "
             "% on top).")
    active = fields.Boolean(default=True)

    def _get_client(self):
        self.ensure_one()
        return NamecheapClient(
            api_user=self.api_user, api_key=self.api_key,
            username=self.username, client_ip=self.client_ip,
            sandbox=self.sandbox)

    def action_test_connection(self):
        self.ensure_one()
        client = self._get_client()
        result = client.call('namecheap.users.getBalances')
        balances = result.find('UserGetBalancesResult')
        available = balances.get('AvailableBalance') if balances is not None else '?'
        raise UserError(_(
            "Connected. Available balance: %(balance)s %(currency)s.",
            balance=available,
            currency=balances.get('Currency') if balances is not None else ''))

    def check_domain_availability(self, domain_names):
        """Check up to 50 domains at once (Namecheap's own limit per
        call - not enforced here, callers shouldn't exceed it) and
        return one dict per domain:

        ``{'domain': ..., 'available': bool, 'premium': bool,
        'sell_price': float or None}``

        For a normal (non-premium) domain, sell_price comes from the
        cached namecheap.tld.price sheet (see that model - not fetched
        live here); a TLD with no cached price yet returns
        ``sell_price: None`` rather than guessing. A premium domain's
        price is Namecheap's own ad-hoc PremiumRegistrationPrice for
        that exact name (there's no per-TLD sheet rate for these), with
        the same markup applied on top.
        """
        self.ensure_one()
        result = self._get_client().call(
            'namecheap.domains.check', DomainList=','.join(domain_names))
        markup = 1 + (self.markup_percentage or 0.0) / 100.0
        prices_by_tld = {
            p.tld: p for p in self.env['namecheap.tld.price'].search(
                [('server_id', '=', self.id)])
        }

        results = []
        for node in result.iter('DomainCheckResult'):
            domain = node.get('Domain') or ''
            available = (node.get('Available') or '').lower() == 'true'
            premium = (node.get('IsPremiumName') or '').lower() == 'true'
            sell_price = None
            if available and premium:
                premium_cost = float(node.get('PremiumRegistrationPrice') or 0.0)
                sell_price = premium_cost * markup
            elif available:
                tld = domain.split('.', 1)[1] if '.' in domain else ''
                cached = prices_by_tld.get(tld)
                if cached:
                    sell_price = cached.sell_register_price
            results.append({
                'domain': domain,
                'available': available,
                'premium': premium,
                'sell_price': sell_price,
            })
        return results

    def _get_available_balance(self):
        """Namecheap's real account balance right now, in whatever
        currency the account is denominated in - used for the
        low-balance alert (see the pricing-sync cron), since
        registering a domain draws this down immediately with no
        separate authorize/capture step: if it runs out between a
        customer paying via Stripe and this module calling
        domains.create, the business has been paid and can't deliver.
        """
        self.ensure_one()
        result = self._get_client().call('namecheap.users.getBalances')
        balances = result.find('UserGetBalancesResult')
        if balances is None:
            raise UserError(_("Namecheap didn't return a balance."))
        return float(balances.get('AvailableBalance', 0.0))
