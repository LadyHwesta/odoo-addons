# -*- coding: utf-8 -*-
"""Bug: `_get_imap_dicts()` ignored `res.company.imap.company` entirely -
every active IMAP server across every company was tried for every IMAP
fallback login attempt, so a Company A user's mistyped password could
reach Company B's mail server. `_authenticate` is mocked throughout: these
tests are about which server(s) a login attempt is scoped to, not about
talking to a real IMAP server (see the module's own manual-verification
note for that).
"""
from unittest.mock import patch

from odoo.exceptions import AccessDenied, UserError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestImapCompanyScoping(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_a = cls.env['res.company'].create({'name': 'Company A'})
        cls.company_b = cls.env['res.company'].create({'name': 'Company B'})
        cls.company_c = cls.env['res.company'].create({'name': 'Company C (unconfigured)'})
        cls.imap_a = cls.env['res.company.imap'].create({
            'company': cls.company_a.id,
            'imap_server': 'imap.company-a.example',
        })
        cls.imap_b = cls.env['res.company.imap'].create({
            'company': cls.company_b.id,
            'imap_server': 'imap.company-b.example',
        })
        cls.user_a = cls.env['res.users'].create({
            'name': 'Alice', 'login': 'alice@company-a.example',
            'company_id': cls.company_a.id,
            'company_ids': [(6, 0, [cls.company_a.id])],
        })
        cls.user_c = cls.env['res.users'].create({
            'name': 'Carol', 'login': 'carol@company-c.example',
            'company_id': cls.company_c.id,
            'company_ids': [(6, 0, [cls.company_c.id])],
        })

    # ------------------------------------------------------------------
    def test_get_imap_dicts_only_returns_the_given_companys_servers(self):
        confs = self.env['res.company.imap']._get_imap_dicts(self.company_a)
        self.assertEqual([c['id'] for c in confs], [self.imap_a.id])

    def test_get_imap_dicts_returns_nothing_for_an_unconfigured_company(self):
        confs = self.env['res.company.imap']._get_imap_dicts(self.company_c)
        self.assertFalse(confs)

    # ------------------------------------------------------------------
    def test_check_credentials_never_tries_another_companys_server(self):
        self.user_a._auth_imap_clear_password()
        seen_confs = []

        def fake_authenticate(imap_self, conf, login, password):
            seen_confs.append(conf['id'])
            return False

        # _check_credentials is only ever meaningfully exercised bound to
        # its own user's env, exactly as core's _login() calls it
        # (`user.with_user(user).sudo()._check_credentials(...)`) - both
        # self and self.env.user need to be Alice for the company lookup
        # and the local-password check to see the right record.
        target = self.user_a.with_user(self.user_a).sudo()
        with patch.object(type(self.env['res.company.imap']), '_authenticate', fake_authenticate):
            with self.assertRaises(AccessDenied):
                target._check_credentials(
                    {'type': 'password', 'password': 'whatever'}, {'interactive': True})

        self.assertEqual(
            seen_confs, [self.imap_a.id],
            "Company A's user must only ever be tried against Company A's own IMAP server(s)")

    def test_check_credentials_succeeds_against_own_companys_server(self):
        self.user_a._auth_imap_clear_password()
        target = self.user_a.with_user(self.user_a).sudo()

        def fake_authenticate(imap_self, conf, login, password):
            return conf['id'] == self.imap_a.id and password == 'correct-horse'

        with patch.object(type(self.env['res.company.imap']), '_authenticate', fake_authenticate):
            result = target._check_credentials(
                {'type': 'password', 'password': 'correct-horse'}, {'interactive': True})
        self.assertEqual(result['auth_method'], 'imap')

    # ------------------------------------------------------------------
    def test_convert_raises_when_the_users_own_company_has_no_server(self):
        # Company C has no res.company.imap row at all, even though
        # Company A and B both do - a global "does *some* company have a
        # server" check would wrongly let this through and then lock Carol
        # out (empty local password, nothing to IMAP-check against either).
        with self.assertRaises(UserError):
            self.user_c.action_convert_to_imap_auth()

    def test_convert_succeeds_when_the_users_own_company_has_a_server(self):
        self.user_a.action_convert_to_imap_auth()
        self.env.cr.execute('SELECT password IS NULL FROM res_users WHERE id=%s', (self.user_a.id,))
        [is_empty] = self.env.cr.fetchone()
        self.assertTrue(is_empty)
