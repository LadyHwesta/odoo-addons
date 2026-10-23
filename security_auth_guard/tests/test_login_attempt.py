# -*- coding: utf-8 -*-
from odoo.exceptions import AccessDenied
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestLoginAttempt(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = cls.env["res.users"].create({
            "name": "Login Test User", "login": "login_attempt_test",
            "password": "correct-password-123",
        })

    def test_successful_login_is_persisted(self):
        self.env["res.users"]._login(
            {"type": "password", "login": "login_attempt_test",
             "password": "correct-password-123"}, {})
        attempt = self.env["security.login_attempt"].search(
            [("login", "=", "login_attempt_test")], order="id desc", limit=1)
        self.assertTrue(attempt)
        self.assertTrue(attempt.success)

    def test_failed_login_is_persisted(self):
        # Deliberately a plain try/except, not self.assertRaises -
        # TransactionCase's own assertRaises wraps its block in a
        # savepoint that gets rolled back the moment the expected
        # exception fires (odoo/tests/common.py's _assertRaises, "this
        # ensures the savepoint gets rolled back when yield raises
        # exception"), which would erase the very audit record this
        # test is checking for - it's a side effect of the exception,
        # not of anything after it. Confirmed real: using assertRaises
        # here made the record vanish even though a debug log proved
        # create() had actually run.
        try:
            self.env["res.users"]._login(
                {"type": "password", "login": "login_attempt_test",
                 "password": "wrong-password"}, {})
            self.fail("Expected AccessDenied")
        except AccessDenied:
            pass
        attempt = self.env["security.login_attempt"].search(
            [("login", "=", "login_attempt_test")], order="id desc", limit=1)
        self.assertTrue(attempt)
        self.assertFalse(attempt.success)
