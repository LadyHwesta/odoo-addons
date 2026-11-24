# -*- coding: utf-8 -*-
from odoo.tests import tagged

from odoo.addons.payment.tests.http_common import PaymentHttpCommon


@tagged('post_install', '-at_install')
class TestDonorCoversFees(PaymentHttpCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.write({
            'donation_cover_fees': True, 'donation_fee_percent': 2.9, 'donation_fee_fixed': 0.30})
        cls.usd = cls.currency

    def test_the_gift_arrives_whole_after_the_fees(self):
        for gift in (5.0, 25.0, 100.0, 1234.56):
            covered = self.company._donation_cover_fee_amount(gift, self.usd)
            total = gift + covered
            fees = self.usd.round(total * 0.029 + 0.30)
            self.assertGreaterEqual(
                self.usd.round(total - fees), gift, f"gift {gift}: {total} - {fees}")
            # and not more than a cent over
            self.assertLessEqual(self.usd.round(total - fees - gift), 0.01, f"gift {gift}")

    def test_a_25_gift_adds_1_06(self):
        # (25 + 0.30) / (1 - 0.029) = 26.0556... -> 26.06
        self.assertAlmostEqual(self.company._donation_cover_fee_amount(25.0, self.usd), 1.06)

    def test_nothing_added_for_no_gift(self):
        self.assertEqual(self.company._donation_cover_fee_amount(0.0, self.usd), 0.0)

    def _donate(self, cover):
        route_values = self._prepare_transaction_values(self.payment_method_id, None, 'direct')
        route_values.update({
            'amount': 25.0,
            'partner_details': {'name': 'Ada Donor', 'email': 'ada@example.com',
                                'country_id': self.env.ref('base.us').id},
            'donation_comment': '', 'donation_recipient_email': '',
            'donation_cover_fees': cover,
        })
        self.authenticate(None, None)
        processing_values = self._portal_transaction(
            tx_route='/donation/transaction/0', **route_values)
        return self.env['payment.transaction'].search(
            [('reference', '=', processing_values['reference'])])

    def test_ticked_the_server_adds_the_fees_itself(self):
        tx = self._donate(cover=True)
        self.assertTrue(tx.is_donation)
        self.assertAlmostEqual(tx.amount, 26.06)
        self.assertAlmostEqual(tx.donation_gift_amount, 25.0)
        self.assertAlmostEqual(tx.donation_fee_covered, 1.06)

    def test_unticked_the_gift_is_charged_as_is(self):
        tx = self._donate(cover=False)
        self.assertAlmostEqual(tx.amount, 25.0)
        self.assertFalse(tx.donation_fee_covered)

    def test_switched_off_the_box_does_nothing(self):
        self.company.donation_cover_fees = False
        tx = self._donate(cover=True)
        self.assertAlmostEqual(tx.amount, 25.0)

    def test_the_form_offers_the_box_unticked(self):
        self.authenticate(None, None)
        html = self.url_open('/donation/pay?amount=25').text
        self.assertIn('id="o_donation_cover_fees"', html)
        self.assertNotIn('id="o_donation_cover_fees" name="o_donation_cover_fees" checked', html)
        self.assertIn('data-fee-percent="2.9"', html)
