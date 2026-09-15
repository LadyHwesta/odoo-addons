# -*- coding: utf-8 -*-
from datetime import date

from odoo import Command
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestNamecheapCancelRenewal(TransactionCase):
    """namecheap.domain had no way to stop auto-renewing before this
    module. action_cancel_renewal needs to do two real things: move
    state off 'active' (so namecheap_domains_sale's own
    _cron_renew_domains - which searches [('state', '=', 'active'),
    ...] - naturally stops attempting the real registrar-side renewal,
    without this module having to touch that cron at all) and end the
    open contract line (so no further invoices get generated either).
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.server = cls.env['namecheap.server'].create({
            'name': 'Test Namecheap', 'api_user': 'testuser', 'api_key': 'testkey',
            'username': 'testuser', 'client_ip': '127.0.0.1', 'sandbox': True,
        })
        cls.partner = cls.env['res.partner'].create({'name': 'Jane Customer'})
        template = cls.env['product.template'].create({
            'name': 'Domain Registration', 'is_domain_registration': True,
        })
        cls.domain_product = template.product_variant_id

    def _domain_with_contract(self):
        domain = self.env['namecheap.domain'].create({
            'name': 'example.com', 'server_id': self.server.id,
            'partner_id': self.partner.id, 'state': 'active',
        })
        contract = self.env['contract.contract'].create({
            'name': 'Test domain contract', 'partner_id': self.partner.id,
            'contract_type': 'sale', 'line_recurrence': True,
            'contract_line_ids': [Command.create({
                'product_id': self.domain_product.id,
                'name': 'example.com renewal', 'quantity': 1, 'price_unit': 12.0,
                'date_start': '2026-01-01', 'recurring_interval': 1,
                'recurring_rule_type': 'yearly', 'recurring_invoicing_type': 'pre-paid',
            })],
        })
        domain.contract_id = contract
        return domain, contract

    def test_cancel_renewal_sets_state_to_cancelled(self):
        domain, _contract = self._domain_with_contract()
        domain.action_cancel_renewal()
        self.assertEqual(domain.state, 'cancelled')

    def test_cancel_renewal_ends_the_open_contract_line(self):
        domain, contract = self._domain_with_contract()
        line = contract.contract_line_ids
        self.assertFalse(line.date_end)

        domain.action_cancel_renewal()

        self.assertEqual(line.date_end, date.today())

    def test_cancelled_domain_no_longer_matches_the_renewal_crons_own_search(self):
        """Proves the actual fix, without needing to run the real
        cron (which would call out to Namecheap's live API): the exact
        domain used by namecheap_domains_sale's _cron_renew_domains
        stops matching once cancelled.
        """
        domain, _contract = self._domain_with_contract()
        self.assertIn(domain, self.env['namecheap.domain'].search([('state', '=', 'active')]))

        domain.action_cancel_renewal()

        self.assertNotIn(domain, self.env['namecheap.domain'].search([('state', '=', 'active')]))

    def test_cancel_renewal_without_a_contract_does_not_raise(self):
        domain = self.env['namecheap.domain'].create({
            'name': 'example.com', 'server_id': self.server.id,
            'partner_id': self.partner.id, 'state': 'active',
        })
        domain.action_cancel_renewal()  # should not raise
        self.assertEqual(domain.state, 'cancelled')
