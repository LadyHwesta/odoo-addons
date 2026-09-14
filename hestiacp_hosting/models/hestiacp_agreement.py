# -*- coding: utf-8 -*-
from odoo import fields, models


class HestiaCPAgreement(models.Model):
    """The Hosting Service Agreement a customer must accept - on the
    checkout's own payment page, not buried in generic site-wide terms -
    before a hosting order can be paid for. See ``_get_active`` for how
    the checkout picks which one to show, and
    ``sale_order._hestiacp_requires_aup_acceptance`` /
    ``controllers/agreement.py`` for where acceptance is actually
    enforced and recorded.
    """
    _name = 'hestiacp.agreement'
    _description = 'Hosting Service Agreement'
    _order = 'create_date desc'

    name = fields.Char(required=True, default='Hosting Service Agreement')
    version = fields.Char(
        required=True, default='1.0',
        help="Bump this whenever body_html changes materially - it's "
             "stamped onto every order/account that accepts this record, "
             "so a later dispute can point at exactly what was agreed to.")
    body_html = fields.Html(
        required=True, sanitize=False,
        help="Shown as-is on the checkout's agreement page. DRAFT "
             "TEMPLATE, not legal advice - the seed data in "
             "data/hestiacp_agreement_data.xml needs review by a real "
             "lawyer for your jurisdiction before relying on it, "
             "particularly the anti-spam/CAN-SPAM-or-equivalent and "
             "limitation-of-liability sections.")
    active = fields.Boolean(
        default=True,
        help="Only one agreement should be active at a time - the "
             "checkout shows whichever active record was created most "
             "recently. Archive the old one instead of editing it in "
             "place once it's been accepted by real customers, so past "
             "acceptances still point at the text they actually agreed "
             "to.")

    def _get_active(self):
        return self.search([('active', '=', True)], order='create_date desc', limit=1)
