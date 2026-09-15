# -*- coding: utf-8 -*-
import json
import logging

from odoo import _, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class NamecheapDomain(models.Model):
    _inherit = 'namecheap.domain'

    hestiacp_account_id = fields.Many2one(
        'hestiacp.account', string="HestiaCP Account",
        help="Deploy this domain onto this hosting account: adds it as "
             "a web/DNS/mail domain there (v-add-domain). Not every "
             "domain needs this - leave blank for one that isn't going "
             "to HestiaCP.")
    manage_dns_via_hestiacp = fields.Boolean(
        string="Let HestiaCP Manage DNS", default=True,
        help="On deploy, also point this domain's nameservers at "
             "HestiaCP's own (whatever this account's package already "
             "has configured), so HestiaCP is fully authoritative for "
             "this domain's DNS as well as its web/mail. Turn this off "
             "for a domain that's hosted (web/mail) on HestiaCP but "
             "has its DNS managed elsewhere instead - e.g. Cloudflare, "
             "for its proxy/CDN/DDoS features. With this off, deploying "
             "still adds the web/mail domain to HestiaCP as normal, but "
             "never touches this domain's nameservers at Namecheap - "
             "use the Nameservers field and Update Nameservers button "
             "(both on namecheap.domain itself) to point them at the "
             "other provider once it's set up, by hand, separately.")
    hestiacp_deployed_on = fields.Datetime(readonly=True)
    dkim_record_name = fields.Char(readonly=True)
    dkim_record_value = fields.Text(readonly=True)

    def action_fetch_dkim_record(self):
        """Pull this domain's DKIM TXT record out of HestiaCP's own DNS
        zone for it - relevant specifically when DNS is managed
        elsewhere (manage_dns_via_hestiacp off): HestiaCP still
        generates DKIM for the mail domain and stores it in that
        otherwise-unused zone, and it needs to be copied by hand into
        whatever's actually authoritative (Cloudflare, etc.) for mail
        to pass SPF/DKIM checks there.

        Uses v-list-dns-records, which needs the ``update-dns-records``
        Access Key category enabled - a different one than everything
        else in this project, which only ever needed ``billing``.
        Verified against HestiaCP's own source
        (2026-09-14): the DKIM record is named ``mail._domainkey`` by
        default, but this looks for any TXT record containing
        "_domainkey" rather than that exact name, in case a different
        selector's in use.
        """
        self.ensure_one()
        account = self.hestiacp_account_id
        if not account:
            raise UserError(_("This domain isn't deployed to a HestiaCP account."))

        records_raw = account.server_id._get_client().call(
            'v-list-dns-records', account.username, self.name, 'json')
        records = json.loads(records_raw)
        dkim = next(
            (r for r in records.values()
             if r.get('TYPE') == 'TXT' and '_domainkey' in (r.get('RECORD') or '')),
            None)
        if not dkim:
            raise UserError(_(
                "No DKIM record found for %(domain)s yet on HestiaCP - "
                "mail may not be fully set up there yet.", domain=self.name))

        self.write({
            'dkim_record_name': dkim['RECORD'],
            'dkim_record_value': dkim['VALUE'],
        })
        self.message_post(body=_(
            "DKIM record fetched from HestiaCP - copy this into whatever's "
            "authoritative for this domain's DNS:<br/>"
            "<b>Name:</b> %(name)s<br/><b>Type:</b> TXT<br/>"
            "<b>Value:</b> %(value)s",
            name=dkim['RECORD'], value=dkim['VALUE']))

    def action_deploy_to_hestiacp(self):
        """Add this domain to hestiacp_account_id's HestiaCP account
        and point it at that account's own nameservers so it actually
        resolves there - not just "added" in HestiaCP with Namecheap
        still serving stale/default DNS.

        Two real gotchas, both verified against HestiaCP's own source
        (2026-09-14) rather than assumed:

        - v-add-domain (the ``billing`` Access Key category already
          used everywhere else in hestiacp_hosting) actually handles
          web+DNS+mail domain setup in one call - no separate
          v-add-web-domain/v-add-dns-domain calls needed.
        - It does NOT raise a clean error when only one of those three
          domain types is already at its package limit - only when
          ALL THREE are. Left alone, a full Web Domains limit would
          silently skip the web vhost while still "succeeding" overall,
          which would look like a working deploy right up until the
          site never actually loads. v-list-user (also ``billing``) is
          checked first instead, to fail loudly and specifically if
          there's no room.
        """
        self.ensure_one()
        account = self.hestiacp_account_id
        if not account:
            raise UserError(_("Pick a HestiaCP account to deploy this domain to first."))
        if account.state != 'active':
            raise UserError(_(
                "%(username)s is not active - can't deploy a domain to it.",
                username=account.username))

        hestia_client = account.server_id._get_client()

        user_info_raw = hestia_client.call('v-list-user', account.username, 'json')
        user_info = json.loads(user_info_raw).get(account.username, {})
        web_limit = user_info.get('WEB_DOMAINS')
        web_used = int(user_info.get('U_WEB_DOMAINS') or 0)
        if web_limit not in (None, '', 'unlimited') and web_used >= int(web_limit):
            raise UserError(_(
                "%(username)s's package is already at its Web Domains "
                "limit (%(used)s/%(limit)s) - increase the package or "
                "remove an existing domain before deploying another one.",
                username=account.username, used=web_used, limit=web_limit))

        hestia_client.call('v-add-domain', account.username, self.name)
        # DNS_SYSTEM being on for the server means v-add-domain just now
        # also created a DNS zone for this domain in HestiaCP - harmless
        # but unused if manage_dns_via_hestiacp is off below, since
        # nothing on the internet will ever query it while the domain's
        # real nameservers point elsewhere. There's no per-call flag to
        # skip that; it's a HestiaCP server-wide feature, not something
        # this module can turn off just for one domain.

        if not self.manage_dns_via_hestiacp:
            ns_note = _(
                " DNS left as-is (Let HestiaCP Manage DNS is off) - "
                "set up DNS with whatever provider this domain is using "
                "instead, and use the Nameservers field/Update "
                "Nameservers button once that's ready.")
        else:
            nameservers = [ns for ns in (user_info.get('NS') or '').split(',') if ns]
            if nameservers:
                self.server_id.set_custom_nameservers(self.name, nameservers)
                self.nameservers = ','.join(nameservers)
                ns_note = _(" Nameservers updated at Namecheap.")
            else:
                _logger.warning(
                    "Namecheap: %s's HestiaCP user has no NS configured - "
                    "%s was added to HestiaCP but its nameservers were NOT "
                    "updated at Namecheap, so it won't resolve there until "
                    "that's done, by hand or otherwise.",
                    account.username, self.name)
                ns_note = _(
                    " Nameservers were NOT updated - the account's "
                    "HestiaCP user has no NS configured.")

        self.write({
            'hestiacp_deployed_on': fields.Datetime.now(),
            'state': 'active',
        })
        self.message_post(body=_(
            "Deployed to HestiaCP account %(username)s.%(ns_note)s",
            username=account.username, ns_note=ns_note))
