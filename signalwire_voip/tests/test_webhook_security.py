# -*- coding: utf-8 -*-
from odoo.exceptions import ValidationError
from odoo.tests.common import BaseCase, TransactionCase, tagged

from odoo.addons.signalwire_voip import webhook_security

# SignalWire's own published test vector for form-encoded (cXML) webhooks:
# signalwire-python tests/unit/security/test_webhook_validator.py, VECTOR_B.
VECTOR_PARAMS = [('CallSid', 'CA1234567890ABCDE'), ('Caller', '+14158675309'),
                 ('Digits', '1234'), ('From', '+14158675309'), ('To', '+18005551212')]
VECTOR_URL = 'https://mycompany.com/myapp.php?foo=1&bar=2'
VECTOR_SIGNATURE = 'RSOYDt4T1cUTdK1PDd93/VVr8B8='


@tagged('post_install', '-at_install')
class TestSignatureMath(BaseCase):

    def test_matches_signalwires_own_vector(self):
        self.assertEqual(webhook_security.compute_signature('12345', VECTOR_URL, VECTOR_PARAMS),
                         VECTOR_SIGNATURE)
        shuffled = list(reversed(VECTOR_PARAMS))
        self.assertTrue(webhook_security.is_valid(['other', '12345'], VECTOR_SIGNATURE,
                                                  [VECTOR_URL], shuffled))

    def test_wrong_key_body_or_missing_signature_fail(self):
        self.assertFalse(webhook_security.is_valid(['nope'], VECTOR_SIGNATURE, [VECTOR_URL], VECTOR_PARAMS))
        tampered = VECTOR_PARAMS[:-1] + [('To', '+18005550000')]
        self.assertFalse(webhook_security.is_valid(['12345'], VECTOR_SIGNATURE, [VECTOR_URL], tampered))
        self.assertFalse(webhook_security.is_valid(['12345'], '', [VECTOR_URL], VECTOR_PARAMS))

    def test_standard_port_is_tried_both_ways(self):
        signed_with_port = webhook_security.compute_signature(
            '12345', 'https://mycompany.com:443/myapp.php', VECTOR_PARAMS)
        self.assertTrue(webhook_security.is_valid(['12345'], signed_with_port,
                                                  ['https://mycompany.com/myapp.php'], VECTOR_PARAMS))
        self.assertEqual(webhook_security.candidate_urls('https://x.com:8443/a'), ['https://x.com:8443/a'])


@tagged('post_install', '-at_install')
class TestSignatureSetting(TransactionCase):

    def test_rejecting_needs_a_signing_key(self):
        server = self.env['signalwire.server'].create({
            'name': 'SW', 'space': 'example.signalwire.com', 'project_id': 'p', 'api_token': 't'})
        self.assertEqual(server.webhook_signature_mode, 'log', "safe default")
        with self.assertRaises(ValidationError):
            server.webhook_signature_mode = 'enforce'
        server.write({'signing_key': 'PSK123', 'webhook_signature_mode': 'enforce'})
