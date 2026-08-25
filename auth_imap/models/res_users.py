# -*- coding: utf-8 -*-
from odoo import _, models
from odoo.exceptions import AccessDenied, UserError


class ResUsers(models.Model):
    _inherit = 'res.users'

    def _check_credentials(self, credential, env):
        """Fall back to IMAP LOGIN when the local Odoo password check fails.

        Mirrors auth_ldap's own override: the local password is always
        tried first (via super()), so a user who still has a local password
        set is never at risk of being locked out just because the IMAP
        server is unreachable. Only users who already exist in Odoo are
        ever authenticated this way - unlike auth_ldap, this module does
        not auto-provision new users from a successful external login.
        """
        try:
            return super()._check_credentials(credential, env)
        except AccessDenied:
            if not (credential['type'] == 'password' and credential.get('password')):
                raise
            passwd_allowed = env['interactive'] or not self.env.user._rpc_api_keys_only()
            if passwd_allowed and self.env.user.active:
                Imap = self.env['res.company.imap']
                for conf in Imap._get_imap_dicts():
                    if Imap._authenticate(conf, self.env.user.login, credential['password']):
                        return {
                            'uid': self.env.user.id,
                            'auth_method': 'imap',
                            'mfa': 'default',
                        }
            raise

    def action_convert_to_imap_auth(self):
        """Clear these users' local Odoo password so every future login for
        them falls straight through to the IMAP check (an empty/NULL
        password can never satisfy the local check - same technique
        auth_ldap uses after an LDAP-driven password change).
        """
        if not self.env['res.company.imap'].sudo().search_count([]):
            raise UserError(_('Configure at least one IMAP server before converting users to IMAP authentication.'))
        for user in self:
            user._auth_imap_clear_password()

    def _auth_imap_clear_password(self):
        # Deliberately not named _set_empty_password: auth_ldap defines its
        # own method of that name for the same purpose: if both modules are
        # ever installed together, each should keep calling its own, not
        # silently share one via the res.users MRO.
        self.flush_recordset(['password'])
        self.env.cr.execute(
            'UPDATE res_users SET password=NULL WHERE id=%s',
            (self.id,),
        )
        self.invalidate_recordset(['password'])
