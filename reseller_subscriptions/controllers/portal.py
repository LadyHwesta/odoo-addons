# -*- coding: utf-8 -*-
from odoo import http
from odoo.exceptions import UserError
from odoo.http import request

from odoo.addons.hestiacp_hosting.models.hestiacp_api import HestiaCPAPIError
from odoo.addons.portal.controllers.portal import CustomerPortal


class SubscriptionsPortal(CustomerPortal):
    """One page aggregating every subscription across hestiacp_hosting,
    namecheap_domains_sale, and signalwire_voip_sale - each still owns
    its own model and its own real action methods, this controller
    only reads a uniform _subscription_summary() from each and adds
    thin, ownership-checked dispatch to the handful of self-service
    actions that didn't have a portal route at all before this module
    (hosting's change-package wizard was staff-only; domains had no
    cancel; SignalWire had neither a portal page nor billing-aware
    release). Ownership is enforced the same way every other portal
    controller in this repo does it (see e.g. signalwire_sms's own
    controllers/portal.py) - search scoped to the logged-in user's own
    partner_id (record rules apply too, but this is belt-and-suspenders
    and makes the scoping explicit here), then .filtered() against the
    id in the URL; a record that isn't actually theirs (or doesn't
    exist) just silently no-ops rather than raising - same convention.
    """

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'subscription_count' in counters:
            values['subscription_count'] = (
                len(self._my_hosting_accounts())
                + len(self._my_domains())
                + len(self._my_signalwire_numbers())
            )
        return values

    def _my_hosting_accounts(self):
        partner = request.env.user.partner_id
        return request.env['hestiacp.account'].search([('partner_id', '=', partner.id)])

    def _my_domains(self):
        partner = request.env.user.partner_id
        return request.env['namecheap.domain'].search([('partner_id', '=', partner.id)])

    def _my_signalwire_numbers(self):
        partner = request.env.user.partner_id
        return request.env['signalwire.phone_number'].search(
            [('subproject_id.partner_id', '=', partner.id)])

    def _my_subscription_rows(self):
        rows = []
        for kind, records in (
                ('hosting', self._my_hosting_accounts()),
                ('domain', self._my_domains()),
                ('signalwire', self._my_signalwire_numbers())):
            for record in records:
                summary = record.sudo()._subscription_summary()
                summary['kind'] = kind
                summary['id'] = record.id
                rows.append(summary)
        return rows

    @http.route(['/my/subscriptions'], type='http', auth='user', website=True)
    def portal_my_subscriptions(self, **kw):
        partner = request.env.user.partner_id
        values = self._prepare_portal_layout_values()
        values.update({
            'rows': self._my_subscription_rows(),
            'payment_tokens': partner.sudo().payment_token_ids,
            'page_name': 'subscriptions',
            'default_url': '/my/subscriptions',
        })
        return request.render('reseller_subscriptions.portal_my_subscriptions', values)

    # -- hosting: change package (wraps the existing staff-only wizard,
    #    doesn't duplicate its logic) --------------------------------------

    def _eligible_hosting_products(self, account):
        return request.env['product.template'].sudo().search([
            ('is_hosting_package', '=', True),
            ('hestiacp_server_id', '=', account.server_id.id),
            ('id', '!=', account.product_id.id),
        ])

    @http.route(
        ['/my/subscriptions/hosting/<int:account_id>/upgrade'],
        type='http', auth='user', methods=['GET', 'POST'], website=True)
    def portal_hosting_upgrade(self, account_id, new_product_id=None, **kw):
        account = self._my_hosting_accounts().filtered(lambda a: a.id == account_id)
        if not account:
            return request.redirect('/my/subscriptions')

        error = None
        if request.httprequest.method == 'POST':
            eligible = self._eligible_hosting_products(account)
            product = eligible.filtered(lambda p: p.id == int(new_product_id or 0))
            if not product:
                error = "Choose a package to switch to."
            else:
                wizard = request.env['hestiacp.account.change.package'].sudo().create({
                    'account_id': account.id, 'new_product_id': product.id,
                })
                try:
                    wizard.action_confirm()
                    return request.redirect('/my/subscriptions')
                except (UserError, HestiaCPAPIError) as exc:
                    error = str(exc)

        values = self._prepare_portal_layout_values()
        values.update({
            'account': account.sudo(),
            'eligible_products': self._eligible_hosting_products(account),
            'error': error,
            'page_name': 'subscriptions',
        })
        return request.render(
            'reseller_subscriptions.portal_my_subscriptions_hosting_upgrade', values)

    @http.route(
        ['/my/subscriptions/hosting/<int:account_id>/cancel'],
        type='http', auth='user', methods=['POST'], website=True)
    def portal_hosting_cancel(self, account_id, **kw):
        account = self._my_hosting_accounts().filtered(lambda a: a.id == account_id)
        if account:
            account.sudo().action_terminate()
        return request.redirect('/my/subscriptions')

    # -- domains --------------------------------------------------------

    @http.route(
        ['/my/subscriptions/domain/<int:domain_id>/cancel_renewal'],
        type='http', auth='user', methods=['POST'], website=True)
    def portal_domain_cancel_renewal(self, domain_id, **kw):
        domain = self._my_domains().filtered(lambda d: d.id == domain_id)
        if domain:
            domain.sudo().action_cancel_renewal()
        return request.redirect('/my/subscriptions')

    # -- signalwire numbers -----------------------------------------------

    @http.route(
        ['/my/subscriptions/signalwire/<int:number_id>/release'],
        type='http', auth='user', methods=['POST'], website=True)
    def portal_signalwire_release(self, number_id, **kw):
        number = self._my_signalwire_numbers().filtered(lambda n: n.id == number_id)
        if number:
            number.sudo().action_release()
        return request.redirect('/my/subscriptions')

    # -- shared: apply an already-saved card to a subscription -------------

    def _my_subscription_finder(self, kind):
        return {
            'hosting': self._my_hosting_accounts,
            'domain': self._my_domains,
            'signalwire': self._my_signalwire_numbers,
        }.get(kind)

    @http.route(
        ['/my/subscriptions/<string:kind>/<int:record_id>/payment_method'],
        type='http', auth='user', methods=['POST'], website=True)
    def portal_subscription_set_payment_method(self, kind, record_id, token_id=None, **kw):
        finder = self._my_subscription_finder(kind)
        if not finder:
            return request.redirect('/my/subscriptions')

        record = finder().filtered(lambda r: r.id == record_id)
        if not record:
            return request.redirect('/my/subscriptions')

        partner = request.env.user.partner_id
        token = request.env['payment.token'].sudo().search([
            ('id', '=', int(token_id or 0)), ('partner_id', '=', partner.id)])
        if token:
            record.sudo().payment_token_id = token.id
        return request.redirect('/my/subscriptions')
