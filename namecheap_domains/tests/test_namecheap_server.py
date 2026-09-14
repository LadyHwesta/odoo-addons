# -*- coding: utf-8 -*-
from unittest.mock import MagicMock, patch
from xml.etree import ElementTree

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged

# These are pre-stripped (no namespace) - representing what
# NamecheapClient.call() actually hands back after parsing, since
# these tests are about namecheap.server's own logic, not the client's
# XML parsing (see test_namecheap_api.py for that).
DOMAIN_CHECK_RESPONSE = """<CommandResponse>
    <DomainCheckResult Domain="taken.com" Available="false" IsPremiumName="false" />
    <DomainCheckResult Domain="free.com" Available="true" IsPremiumName="false" />
    <DomainCheckResult Domain="free.net" Available="true" IsPremiumName="false" />
    <DomainCheckResult Domain="lux.com" Available="true" IsPremiumName="true"
                        PremiumRegistrationPrice="500.00" />
</CommandResponse>"""

BALANCES_RESPONSE = """<CommandResponse>
    <UserGetBalancesResult Currency="USD" AvailableBalance="42.50" AccountBalance="42.50" />
</CommandResponse>"""


@tagged('post_install', '-at_install')
class TestNamecheapServer(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.server = cls.env['namecheap.server'].create({
            'name': 'Test Namecheap',
            'api_user': 'tester',
            'api_key': 'key123',
            'username': 'tester',
            'client_ip': '1.2.3.4',
            'sandbox': True,
            'markup_percentage': 20.0,
        })

    def _mock_client(self, call_return_value):
        mock_client = MagicMock()
        mock_client.call.return_value = ElementTree.fromstring(call_return_value)
        patcher = patch(
            'odoo.addons.namecheap_domains.models.namecheap_server.'
            'NamecheapServer._get_client',
            return_value=mock_client)
        patcher.start()
        self.addCleanup(patcher.stop)
        return mock_client

    def test_check_availability_reports_taken_and_free_domains(self):
        self._mock_client(DOMAIN_CHECK_RESPONSE)

        results = self.server.check_domain_availability(['taken.com', 'free.com'])

        by_domain = {r['domain']: r for r in results}
        self.assertFalse(by_domain['taken.com']['available'])
        self.assertTrue(by_domain['free.com']['available'])

    def test_check_availability_uses_cached_price_for_a_normal_tld(self):
        self._mock_client(DOMAIN_CHECK_RESPONSE)
        self.env['namecheap.tld.price'].create({
            'server_id': self.server.id, 'tld': 'com', 'register_cost': 10.0,
        })

        results = self.server.check_domain_availability(['free.com'])

        by_domain = {r['domain']: r for r in results}
        self.assertAlmostEqual(by_domain['free.com']['sell_price'], 12.0)  # 10 * 1.2

    def test_check_availability_returns_none_price_with_no_cached_tld(self):
        self._mock_client(DOMAIN_CHECK_RESPONSE)

        results = self.server.check_domain_availability(['free.net'])

        by_domain = {r['domain']: r for r in results}
        self.assertIsNone(by_domain['free.net']['sell_price'])

    def test_check_availability_marks_up_a_premium_domain_from_its_own_price(self):
        self._mock_client(DOMAIN_CHECK_RESPONSE)

        results = self.server.check_domain_availability(['lux.com'])

        by_domain = {r['domain']: r for r in results}
        result = by_domain['lux.com']
        self.assertTrue(result['premium'])
        self.assertAlmostEqual(result['sell_price'], 600.0)  # 500 * 1.2

    def test_test_connection_reports_the_balance(self):
        self._mock_client(BALANCES_RESPONSE)

        with self.assertRaises(UserError) as cm:
            self.server.action_test_connection()
        self.assertIn('42.5', str(cm.exception))

    def test_get_available_balance_returns_a_float(self):
        self._mock_client(BALANCES_RESPONSE)

        self.assertEqual(self.server._get_available_balance(), 42.5)
