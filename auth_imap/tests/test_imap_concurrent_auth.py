# -*- coding: utf-8 -*-
"""Tech debt: `_check_credentials` used to try each of a company's
configured IMAP servers strictly sequentially. `_authenticate` blocks on
real socket I/O for up to CONNECT_TIMEOUT (15s) per server, so a company
with N servers configured paid up to N * 15s in the worst case (a wrong
password, or a login whose matching server isn't first in `sequence`) -
every second of it spent holding the login request (and, in prefork mode,
the whole worker) open. `_authenticate_any` now tries them concurrently
instead, bounding the wait to roughly one server's timeout. `_authenticate`
is mocked throughout via `time.sleep` stand-ins to prove the *timing*
behavior, not to talk to a real IMAP server.
"""
import time
from unittest.mock import patch

from odoo.tests.common import TransactionCase, tagged

# Comfortably longer than one mocked "slow" call but much shorter than two
# or three of them summed - the actual assertion threshold below.
SLOW_CALL_SECONDS = 0.3


@tagged('post_install', '-at_install')
class TestImapConcurrentAuth(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({'name': 'Multi-IMAP Co'})
        cls.confs = cls.env['res.company.imap'].create([
            {'company': cls.company.id, 'imap_server': f'imap{i}.example', 'sequence': i * 10}
            for i in range(1, 4)
        ])

    def test_single_server_calls_authenticate_directly(self):
        single_company = self.env['res.company'].create({'name': 'One-IMAP Co'})
        self.env['res.company.imap'].create({
            'company': single_company.id, 'imap_server': 'imap.example',
        })
        with patch.object(type(self.env['res.company.imap']), '_authenticate',
                           return_value=True) as mock_auth:
            result = self.env['res.company.imap']._authenticate_any(
                single_company, 'someone', 'pw')
        self.assertTrue(result)
        mock_auth.assert_called_once()

    def test_no_configured_servers_returns_false_without_calling_authenticate(self):
        unconfigured = self.env['res.company'].create({'name': 'No-IMAP Co'})
        with patch.object(type(self.env['res.company.imap']), '_authenticate') as mock_auth:
            result = self.env['res.company.imap']._authenticate_any(
                unconfigured, 'someone', 'pw')
        self.assertFalse(result)
        mock_auth.assert_not_called()

    def test_returns_true_when_any_configured_server_matches(self):
        matching_id = self.confs[1].id  # the middle one, not first-by-sequence

        def fake_authenticate(imap_self, conf, login, password):
            return conf['id'] == matching_id

        with patch.object(type(self.env['res.company.imap']), '_authenticate', fake_authenticate):
            result = self.env['res.company.imap']._authenticate_any(
                self.company, 'someone', 'correct-password')
        self.assertTrue(result)

    def test_returns_false_when_no_configured_server_matches(self):
        with patch.object(type(self.env['res.company.imap']), '_authenticate',
                           return_value=False):
            result = self.env['res.company.imap']._authenticate_any(
                self.company, 'someone', 'wrong-password')
        self.assertFalse(result)

    def test_servers_are_tried_concurrently_not_sequentially(self):
        # All 3 configured servers "take" SLOW_CALL_SECONDS to answer (all
        # fail). Sequential trying would take ~3x that; concurrent trying
        # should take about 1x, with some slack for scheduling overhead.
        def slow_fail(imap_self, conf, login, password):
            time.sleep(SLOW_CALL_SECONDS)
            return False

        start = time.monotonic()
        with patch.object(type(self.env['res.company.imap']), '_authenticate', slow_fail):
            result = self.env['res.company.imap']._authenticate_any(
                self.company, 'someone', 'wrong-password')
        elapsed = time.monotonic() - start

        self.assertFalse(result)
        self.assertLess(
            elapsed, SLOW_CALL_SECONDS * 2,
            f"took {elapsed:.2f}s for 3 servers at {SLOW_CALL_SECONDS}s each - "
            "looks sequential, not concurrent")

    def test_returns_promptly_when_a_fast_match_beats_a_slow_server(self):
        # confs[0] matches immediately; confs[1] and confs[2] are slow and
        # never match. The call should return as soon as confs[0] answers,
        # not wait for the slow ones to finish first.
        fast_match_id = self.confs[0].id

        def mixed_speed(imap_self, conf, login, password):
            if conf['id'] == fast_match_id:
                return True
            time.sleep(SLOW_CALL_SECONDS)
            return False

        start = time.monotonic()
        with patch.object(type(self.env['res.company.imap']), '_authenticate', mixed_speed):
            result = self.env['res.company.imap']._authenticate_any(
                self.company, 'someone', 'correct-password')
        elapsed = time.monotonic() - start

        self.assertTrue(result)
        self.assertLess(
            elapsed, SLOW_CALL_SECONDS,
            f"took {elapsed:.2f}s to return - looks like it waited for the "
            "slow servers instead of returning as soon as the fast one matched")
