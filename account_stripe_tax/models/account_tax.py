# -*- coding: utf-8 -*-
from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError


class AccountTax(models.Model):
    _inherit = 'account.tax'

    is_stripe_tax = fields.Boolean(
        readonly=True, copy=False,
        help="Created and applied by Stripe Tax; the rate comes from Stripe.")

    @api.model
    def _stripe_tax_for_rate(self, company, rate):
        """The sales tax at this rate (percent) for the company, made on
        first use: an ordinary percentage tax posting to the configured
        sales-tax account."""
        rate = round(rate, 4)
        tax = self.with_context(active_test=False).search([
            ('is_stripe_tax', '=', True), ('company_id', '=', company.id),
            ('type_tax_use', '=', 'sale'), ('amount', '=', rate)], limit=1)
        if tax:
            if not tax.active:
                tax.active = True
            return tax
        account = company.stripe_tax_account_id
        if not account:
            raise UserError(_(
                "Choose the Sales Tax Account for Stripe Tax first "
                "(Accounting > Configuration > Settings > Taxes)."))
        country = company.account_fiscal_country_id or company.country_id
        group = self.env['account.tax.group'].search([
            ('name', '=', 'Sales Tax'), ('company_id', '=', company.id),
            ('country_id', 'in', (country.id, False))], limit=1)
        if not group:
            group = self.env['account.tax.group'].create({
                'name': 'Sales Tax', 'company_id': company.id, 'country_id': country.id})

        def lines(document_type):
            return [
                Command.create({'document_type': document_type, 'repartition_type': 'base'}),
                Command.create({'document_type': document_type, 'repartition_type': 'tax',
                                'account_id': account.id}),
            ]
        label = f"{rate:g}%"
        return self.create({
            'name': _("Sales Tax %(rate)s", rate=label),
            'invoice_label': _("Sales tax %(rate)s", rate=label),
            'amount': rate,
            'amount_type': 'percent',
            'type_tax_use': 'sale',
            'company_id': company.id,
            'country_id': country.id,
            'tax_group_id': group.id,
            'is_stripe_tax': True,
            'invoice_repartition_line_ids': lines('invoice'),
            'refund_repartition_line_ids': lines('refund'),
        })
