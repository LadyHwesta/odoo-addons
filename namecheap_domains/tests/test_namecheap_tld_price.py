# -*- coding: utf-8 -*-
from unittest.mock import MagicMock, patch
from xml.etree import ElementTree

from odoo.tests.common import TransactionCase, tagged


def _pricing_response(price_attr='YourPrice'):
    return f"""<CommandResponse>
        <UserGetPricingResult>
            <ProductType Name="DOMAINS">
                <ProductCategory Name="register">
                    <Product Name="com">
                        <Price Duration="1" DurationType="YEAR" {price_attr}="10.98" />
                        <Price Duration="2" DurationType="YEAR" {price_attr}="21.96" />
                    </Product>
                    <Product Name="net">
                        <Price Duration="1" DurationType="YEAR" {price_attr}="12.98" />
                    </Product>
                </ProductCategory>
            </ProductType>
        </UserGetPricingResult>
    </CommandResponse>"""


@tagged('post_install', '-at_install')
class TestNamecheapTldPrice(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.server = cls.env['namecheap.server'].create({
            'name': 'Test Namecheap',
            'api_user': 'tester', 'api_key': 'key123', 'username': 'tester',
            'client_ip': '1.2.3.4', 'sandbox': True, 'markup_percentage': 25.0,
        })

    def _mock_client(self):
        mock_client = MagicMock()
        mock_client.call.return_value = ElementTree.fromstring(_pricing_response())
        patcher = patch(
            'odoo.addons.namecheap_domains.models.namecheap_server.'
            'NamecheapServer._get_client',
            return_value=mock_client)
        patcher.start()
        self.addCleanup(patcher.stop)
        return mock_client

    def test_sync_creates_one_price_record_per_tld(self):
        self._mock_client()

        self.env['namecheap.tld.price']._sync_from_namecheap(self.server)

        tlds = self.env['namecheap.tld.price'].search([('server_id', '=', self.server.id)])
        self.assertEqual(set(tlds.mapped('tld')), {'com', 'net'})

    def test_sync_only_keeps_the_one_year_price(self):
        self._mock_client()

        self.env['namecheap.tld.price']._sync_from_namecheap(self.server)

        com = self.env['namecheap.tld.price'].search(
            [('server_id', '=', self.server.id), ('tld', '=', 'com')])
        self.assertEqual(com.register_cost, 10.98)

    def test_sell_price_applies_the_servers_markup(self):
        self._mock_client()

        self.env['namecheap.tld.price']._sync_from_namecheap(self.server)

        com = self.env['namecheap.tld.price'].search(
            [('server_id', '=', self.server.id), ('tld', '=', 'com')])
        self.assertAlmostEqual(com.sell_register_price, 10.98 * 1.25)

    def test_sync_updates_an_existing_price_rather_than_duplicating(self):
        self._mock_client()
        existing = self.env['namecheap.tld.price'].create({
            'server_id': self.server.id, 'tld': 'com', 'register_cost': 1.0,
        })

        self.env['namecheap.tld.price']._sync_from_namecheap(self.server)

        self.assertEqual(existing.register_cost, 10.98)
        self.assertEqual(
            self.env['namecheap.tld.price'].search_count(
                [('server_id', '=', self.server.id), ('tld', '=', 'com')]),
            1)

    def test_cron_sync_pricing_does_not_stop_on_one_servers_failure(self):
        self._mock_client()
        other_server = self.env['namecheap.server'].create({
            'name': 'Broken Namecheap', 'api_user': 'x', 'api_key': 'x',
            'username': 'x', 'client_ip': '1.2.3.4', 'sandbox': True,
        })
        with patch(
                'odoo.addons.namecheap_domains.models.namecheap_tld_price.'
                'NamecheapTldPrice._sync_from_namecheap',
                side_effect=[Exception('boom'), None]) as sync:
            self.env['namecheap.tld.price']._cron_sync_pricing()
        self.assertEqual(sync.call_count, 2)
