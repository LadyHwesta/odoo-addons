# -*- coding: utf-8 -*-
from unittest.mock import MagicMock, patch

from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestAccountMoveCdrStatement(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.server = cls.env['signalwire.server'].create({
            'name': 'Test SignalWire', 'space': 'example.signalwire.com',
            'project_id': 'pid123', 'api_token': 'tok456',
        })
        cls.subproject = cls.env['signalwire.subproject'].create({
            'name': 'Customer Subproject', 'server_id': cls.server.id,
            'account_sid': 'sub-abc', 'state': 'active',
        })
        # A bare test company has no Chart of Accounts installed by
        # default - same gotcha (and same fix) as namecheap_domains_sale's
        # and signalwire_sms's own renewal-cron tests.
        cls.income_account = cls.env['account.account'].create({
            'name': 'Test Income', 'code': 'TINC', 'account_type': 'income',
        })
        cls.receivable_account = cls.env['account.account'].create({
            'name': 'Test Receivable', 'code': 'TREC',
            'account_type': 'asset_receivable', 'reconcile': True,
        })
        if not cls.env['account.journal'].search([('type', '=', 'sale')]):
            cls.env['account.journal'].create({
                'name': 'Test Sales Journal', 'code': 'TSALE', 'type': 'sale',
            })
        cls.partner = cls.env['res.partner'].create({
            'name': 'Jane Customer',
            'property_account_receivable_id': cls.receivable_account.id,
        })
        cls.usage_product = cls.env.ref('signalwire_voip_sale.product_signalwire_usage')
        cls.usage_product.property_account_income_id = cls.income_account.id
        cls.contract = cls.env['contract.contract'].create({
            'name': 'Test Contract', 'partner_id': cls.partner.id,
            'contract_type': 'sale', 'line_recurrence': True,
            'contract_line_ids': [(0, 0, {
                'product_id': cls.usage_product.id, 'name': '+12084449665 - metered usage',
                'quantity': 1, 'price_unit': 0.0,
                'date_start': fields.Date.context_today(cls.env.user),
                'recurring_interval': 1, 'recurring_rule_type': 'monthly',
                'recurring_invoicing_type': 'post-paid',
                'is_signalwire_metered': True, 'signalwire_subproject_id': cls.subproject.id,
            })],
        })
        cls.line = cls.contract.contract_line_ids

    def _due_date(self):
        # A post-paid line's own recurring_next_date is the END of its
        # first period (date_start + the recurrence interval), not
        # date_start itself - a post-paid charge is only due once the
        # period it covers has actually elapsed. Passing today as
        # date_ref (matching how a cron fires "right now") wouldn't
        # find this line due yet.
        return fields.Date.context_today(self.env.user) + relativedelta(months=1)

    def _cdr(self, sid, billed_amount=1.0):
        return self.env['signalwire.cdr'].create({
            'subproject_id': self.subproject.id, 'sid': sid, 'record_type': 'call',
            'date': fields.Datetime.now(), 'billed_amount': billed_amount,
            'wholesale_cost': billed_amount, 'rate': billed_amount,
            'contract_line_id': self.line.id,
        })

    def test_recurring_create_invoice_attaches_a_cdr_statement(self):
        cdrs = self._cdr('CA1') | self._cdr('CA2')
        with patch.object(
                type(self.subproject), '_sync_cdrs', return_value=cdrs), \
             patch(
                'odoo.addons.base.models.ir_actions_report.IrActionsReport._render_qweb_pdf',
                return_value=(b'%PDF-fake%', 'pdf')) as mocked_render:
            moves = self.contract._recurring_create_invoice(
                date_ref=self._due_date())

        self.assertEqual(len(moves), 1)
        mocked_render.assert_called_once()
        attachment = self.env['ir.attachment'].search([
            ('res_model', '=', 'account.move'), ('res_id', '=', moves.id),
        ])
        self.assertTrue(any(a.mimetype == 'application/pdf' for a in attachment))

    def test_recurring_create_invoice_links_cdrs_to_the_move_line(self):
        cdrs = self._cdr('CA1')
        with patch.object(type(self.subproject), '_sync_cdrs', return_value=cdrs), \
             patch(
                'odoo.addons.base.models.ir_actions_report.IrActionsReport._render_qweb_pdf',
                return_value=(b'%PDF-fake%', 'pdf')):
            moves = self.contract._recurring_create_invoice(
                date_ref=self._due_date())

        self.assertTrue(cdrs.move_line_id)
        self.assertEqual(cdrs.move_id, moves)

    def test_no_cdrs_still_generates_a_statement(self):
        with patch.object(
                type(self.subproject), '_sync_cdrs',
                return_value=self.env['signalwire.cdr']), \
             patch(
                'odoo.addons.base.models.ir_actions_report.IrActionsReport._render_qweb_pdf',
                return_value=(b'%PDF-fake%', 'pdf')) as mocked_render:
            self.contract._recurring_create_invoice(
                date_ref=self._due_date())

        mocked_render.assert_called_once()
