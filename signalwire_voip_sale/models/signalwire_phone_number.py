# -*- coding: utf-8 -*-
from odoo import models


class SignalWirePhoneNumber(models.Model):
    _inherit = 'signalwire.phone_number'

    def _signalwire_after_provisioned(self, contract, checkout_transaction):
        """No-op hook, called right after checkout provisions this
        number and creates its billing contract (see sale_order.py's
        own _signalwire_provision_number_lines) - this module keeps no
        contract/payment-token back-reference on the number itself,
        so by default this does nothing. reseller_subscriptions (if
        installed) overrides it to store one - kept as a hook rather
        than a field/write here, since this module shouldn't reach
        forward into an optional extension's own schema, and this way
        nothing breaks whether or not that module is present.
        """
        return
