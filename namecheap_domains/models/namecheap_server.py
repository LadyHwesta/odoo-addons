# -*- coding: utf-8 -*-
import logging
from datetime import datetime

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

    def set_custom_nameservers(self, domain_name, nameservers):
        """Point `domain_name` at `nameservers` (a list of hostnames)
        instead of Namecheap's own DNS, via domains.dns.setCustom.
        Needed for a domain to actually resolve wherever it's hosted -
        adding it to a hosting account's control panel (HestiaCP or
        otherwise) doesn't touch DNS at the registrar by itself.

        Note this method's own name: URL forwarding, email forwarding,
        and Namecheap's Dynamic DNS stop working for a domain once it's
        on custom nameservers, per Namecheap's own docs for this
        method - expected and fine once the destination's own DNS
        (e.g. HestiaCP's) is what's actually serving the domain, but
        worth knowing before calling this for any other reason.
        """
        self.ensure_one()
        if '.' not in domain_name:
            raise UserError(_("%(domain)s doesn't look like a valid domain.",
                               domain=domain_name))
        sld, tld = domain_name.split('.', 1)
        self._get_client().call(
            'namecheap.domains.dns.setCustom',
            SLD=sld, TLD=tld, NameServers=','.join(nameservers))

    # -- Transfers in -------------------------------------------------------
    # Commands and fields as in Namecheap's official Go SDK
    # (github.com/namecheap/go-namecheap-sdk, namecheap/domains_transfer_*.go,
    # read 2026-11-24): Namecheap's own docs pages refuse automated fetching.

    def transfer_domain(self, domain_name, years, epp_code):
        """Start a transfer in (domains.transfer.create). Namecheap charges the
        account's balance and adds `years` to the domain. Its contacts come
        across with it, so none are sent.

        :return: dict with transfer_id, status_id, order_id, charged (float)
        :raises NamecheapAPIError: e.g. an extension that can't be
            transferred through the API, or an insufficient balance.
        """
        self.ensure_one()
        result = self._get_client().call(
            'namecheap.domains.transfer.create', DomainName=domain_name, Years=years,
            EPPCode=epp_code, AddFreeWhoisguard='yes', WGenable='yes')
        node = result.find('DomainTransferCreateResult')
        if node is None or not node.get('TransferID'):
            raise UserError(_("Namecheap didn't return a transfer for %(domain)s.",
                              domain=domain_name))
        return {
            'transfer_id': int(node.get('TransferID')),
            'status_id': int(node.get('StatusID') or 0),
            'order_id': int(node.get('OrderID') or 0),
            'charged': float(node.get('ChargedAmount') or 0.0),
        }

    def get_transfer_status(self, transfer_id):
        """Where a transfer stands (domains.transfer.getStatus).

        :return: (state, status text), state one of 'completed', 'cancelled'
            or 'in_progress', classified as the SDK does: Namecheap's status
            texts vary, but end in "complete" or "cancel".
        """
        self.ensure_one()
        result = self._get_client().call(
            'namecheap.domains.transfer.getStatus', TransferID=transfer_id)
        node = result.find('DomainTransferGetStatusResult')
        status = (node.get('Status') if node is not None else '') or ''
        lowered = status.strip().lower()
        if 'complete' in lowered:
            state = 'completed'
        elif 'cancel' in lowered:
            state = 'cancelled'
        else:
            state = 'in_progress'
        return state, status.strip()

    def resubmit_transfer(self, transfer_id):
        """Try a stuck transfer again (domains.transfer.updateStatus, Resubmit),
        e.g. once the domain has been unlocked at the old registrar."""
        self.ensure_one()
        self._get_client().call(
            'namecheap.domains.transfer.updateStatus', TransferID=transfer_id,
            Resubmit='true')

    def get_domain_dates(self, domain_name):
        """(created, expires) as dates, from domains.getInfo; dates come as
        M/D/YYYY."""
        self.ensure_one()
        result = self._get_client().call('namecheap.domains.getInfo', DomainName=domain_name)
        details = result.find('DomainGetInfoResult/DomainDetails')

        def parse(tag):
            text = (details.findtext(tag) if details is not None else '') or ''
            text = text.strip().split(' ')[0]
            for fmt in ('%m/%d/%Y', '%m/%d/%y', '%Y-%m-%d'):
                try:
                    return datetime.strptime(text, fmt).date()
                except ValueError:
                    continue
            return False

        return parse('CreatedDate'), parse('ExpiredDate')

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
