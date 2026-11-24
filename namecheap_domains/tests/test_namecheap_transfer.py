# -*- coding: utf-8 -*-
from datetime import date
from unittest.mock import MagicMock, patch
from xml.etree import ElementTree

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged

# Shapes as in Namecheap's official Go SDK (domains_transfer_*.go,
# domains_get_info.go), namespace already stripped by NamecheapClient.call().
TRANSFER_CREATE = """<CommandResponse>
    <DomainTransferCreateResult DomainName="hers.com" TransferID="15" StatusID="1"
        OrderID="1200" TransactionID="1300" ChargedAmount="10.98" />
</CommandResponse>"""


def _status(text):
    return f"""<CommandResponse>
    <DomainTransferGetStatusResult TransferID="15" StatusID="5" Status="{text}" />
</CommandResponse>"""


GET_INFO = """<CommandResponse>
    <DomainGetInfoResult Status="Ok" ID="77" DomainName="hers.com" IsOwner="true">
        <DomainDetails>
            <CreatedDate>03/14/2019</CreatedDate>
            <ExpiredDate>06/02/2028</ExpiredDate>
            <NumYears>0</NumYears>
        </DomainDetails>
    </DomainGetInfoResult>
</CommandResponse>"""


@tagged('post_install', '-at_install')
class TestNamecheapTransfer(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.server = cls.env['namecheap.server'].create({
            'name': 'Test Namecheap', 'api_user': 'tester', 'api_key': 'key123',
            'username': 'tester', 'client_ip': '1.2.3.4', 'sandbox': True,
            'markup_percentage': 20.0,
        })

    def _mock(self, *responses):
        client = MagicMock()
        client.call.side_effect = [ElementTree.fromstring(r) for r in responses]
        patcher = patch(
            'odoo.addons.namecheap_domains.models.namecheap_server.NamecheapServer._get_client',
            return_value=client)
        patcher.start()
        self.addCleanup(patcher.stop)
        return client

    def test_transfer_sends_the_epp_code_and_returns_the_transfer(self):
        client = self._mock(TRANSFER_CREATE)
        result = self.server.transfer_domain('hers.com', 1, 'Ab#12-xY')
        self.assertEqual(result, {'transfer_id': 15, 'status_id': 1, 'order_id': 1200,
                                  'charged': 10.98})
        args, kwargs = client.call.call_args
        self.assertEqual(args[0], 'namecheap.domains.transfer.create')
        self.assertEqual(kwargs['DomainName'], 'hers.com')
        self.assertEqual(kwargs['EPPCode'], 'Ab#12-xY')
        self.assertEqual(kwargs['Years'], 1)
        self.assertNotIn('RegistrantFirstName', kwargs)

    def test_a_transfer_without_an_id_is_an_error(self):
        self._mock("<CommandResponse><DomainTransferCreateResult DomainName='x.com' /></CommandResponse>")
        with self.assertRaises(UserError):
            self.server.transfer_domain('x.com', 1, 'code')

    def test_statuses_are_classified(self):
        for text, expected in (
                ('Transferred', 'in_progress'),
                ('Awaiting EPP', 'in_progress'),
                ('Completed', 'completed'),
                ('Transfer completed', 'completed'),
                ('Cancelled', 'cancelled'),
                ('Transfer cancelled: invalid EPP code', 'cancelled')):
            self._mock(_status(text))
            self.assertEqual(self.server.get_transfer_status(15), (expected, text), text)
            patch.stopall()

    def test_resubmit_asks_namecheap_to_try_again(self):
        client = self._mock("<CommandResponse><DomainTransferUpdateStatusResult TransferID='15' Resubmit='true' /></CommandResponse>")
        self.server.resubmit_transfer(15)
        args, kwargs = client.call.call_args
        self.assertEqual(args[0], 'namecheap.domains.transfer.updateStatus')
        self.assertEqual(kwargs, {'TransferID': 15, 'Resubmit': 'true'})

    def test_domain_dates_are_read_from_get_info(self):
        self._mock(GET_INFO)
        self.assertEqual(self.server.get_domain_dates('hers.com'),
                         (date(2019, 3, 14), date(2028, 6, 2)))

    def test_transfer_prices_follow_the_markup(self):
        price = self.env['namecheap.tld.price'].create({
            'server_id': self.server.id, 'tld': 'com', 'transfer_cost': 10.0})
        self.assertAlmostEqual(price.sell_transfer_price, 12.0)
