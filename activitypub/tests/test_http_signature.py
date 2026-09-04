# -*- coding: utf-8 -*-
"""Tests for the HTTP Signatures / key helpers.

These touch no Odoo API - only ``cryptography`` and the stdlib - so the
class body is equally valid as a plain ``unittest`` module; it is imported
through ``odoo.addons`` only so the standard ``odoo-bin ... --test-enable``
run picks it up with everything else.
"""
import unittest
from datetime import datetime, timedelta, timezone

from odoo.addons.activitypub.models.activitypub_service import (
    SignatureError,
    build_signature_headers,
    digest_header,
    generate_rsa_keypair,
    parse_signature_header,
    verify_signature,
)

INBOX = "https://remote.example/users/alice/inbox"
KEY_ID = "https://odoo.example/ap/actors/1#main-key"


class TestKeypair(unittest.TestCase):
    def test_generate_keypair_is_usable_pem(self):
        private_pem, public_pem = generate_rsa_keypair(key_size=2048)
        self.assertIn("BEGIN PRIVATE KEY", private_pem)
        self.assertIn("BEGIN PUBLIC KEY", public_pem)
        # A second pair must differ.
        other_private, _ = generate_rsa_keypair(key_size=2048)
        self.assertNotEqual(private_pem, other_private)


class TestHttpSignatureRoundTrip(unittest.TestCase):
    def setUp(self):
        self.private_pem, self.public_pem = generate_rsa_keypair()
        self.body = b'{"type":"Create","actor":"https://odoo.example/ap/actors/1"}'

    def _headers(self, **kw):
        return build_signature_headers(
            "POST", INBOX, KEY_ID, self.private_pem, body=self.body, **kw)

    def test_sign_then_verify_ok(self):
        headers = self._headers()
        self.assertIn("Signature", headers)
        self.assertEqual(headers["Digest"], digest_header(self.body))
        sig = verify_signature(
            "post", "/users/alice/inbox", headers, self.body, self.public_pem)
        self.assertEqual(sig["keyId"], KEY_ID)

    def test_tampered_body_fails_on_digest(self):
        headers = self._headers()
        with self.assertRaises(SignatureError):
            verify_signature("post", "/users/alice/inbox", headers,
                             self.body + b"x", self.public_pem)

    def test_tampered_signature_fails(self):
        headers = self._headers()
        headers["Signature"] = headers["Signature"].replace(
            'signature="', 'signature="AAAA')
        with self.assertRaises(SignatureError):
            verify_signature("post", "/users/alice/inbox", headers,
                             self.body, self.public_pem)

    def test_wrong_key_fails(self):
        headers = self._headers()
        _, other_public = generate_rsa_keypair()
        with self.assertRaises(SignatureError):
            verify_signature("post", "/users/alice/inbox", headers,
                             self.body, other_public)

    def test_wrong_request_target_fails(self):
        headers = self._headers()
        with self.assertRaises(SignatureError):
            verify_signature("post", "/users/bob/inbox", headers,
                             self.body, self.public_pem)

    def test_stale_date_rejected(self):
        old = datetime.now(timezone.utc) - timedelta(hours=2)
        headers = self._headers(now=old)
        with self.assertRaises(SignatureError):
            verify_signature("post", "/users/alice/inbox", headers,
                             self.body, self.public_pem)

    def test_clock_skew_within_tolerance_ok(self):
        recent = datetime.now(timezone.utc) - timedelta(minutes=5)
        headers = self._headers(now=recent)
        verify_signature("post", "/users/alice/inbox", headers,
                         self.body, self.public_pem)

    def test_signed_get_has_no_digest(self):
        headers = build_signature_headers("GET", INBOX, KEY_ID, self.private_pem)
        self.assertNotIn("Digest", headers)
        self.assertIn("headers=\"(request-target) host date\"", headers["Signature"])

    def test_post_signature_not_covering_digest_is_rejected(self):
        # A real Digest header is present and correct, but the signature
        # itself only covers (request-target)/host/date - exactly what a
        # sender omitting "digest" from its own headers list would send.
        # The body must never be trusted just because *some* signature
        # verifies; it has to be the body this signature actually covers.
        headers = self._headers(sign_digest=False)
        self.assertIn("Digest", headers)  # header is sent...
        self.assertNotIn("digest", headers["Signature"])  # ...just not signed
        with self.assertRaises(SignatureError):
            verify_signature("post", "/users/alice/inbox", headers,
                             self.body, self.public_pem)

    def test_get_without_body_does_not_require_digest(self):
        headers = build_signature_headers("GET", INBOX, KEY_ID, self.private_pem)
        verify_signature("get", "/users/alice/inbox", headers, b"", self.public_pem)


class TestParseSignatureHeader(unittest.TestCase):
    def test_missing_raises(self):
        with self.assertRaises(SignatureError):
            parse_signature_header("")

    def test_missing_keyid_raises(self):
        with self.assertRaises(SignatureError):
            parse_signature_header('signature="abc"')

    def test_defaults_filled_in(self):
        parsed = parse_signature_header('keyId="k",signature="s"')
        self.assertEqual(parsed["algorithm"], "rsa-sha256")
        self.assertEqual(parsed["headers"], "date")


if __name__ == "__main__":  # pragma: no cover - allows standalone runs
    unittest.main()
