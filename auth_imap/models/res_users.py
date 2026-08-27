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

        Unlike auth_ldap, the fallback only fires for users who were
        actually converted to IMAP authentication (empty local password -
        see action_convert_to_imap_auth). Any user still on a local
        password never reaches the IMAP server at all: without this gate,
        every mistyped password for every user - converted or not - would
        try a real LOGIN against each configured IMAP server, and mail
        providers commonly block/throttle a source IP after enough failed
        logins.
        """
        try:
            return super()._check_credentials(credential, env)
        except AccessDenied:
            if not (credential['type'] == 'password' and credential.get('password')):
                raise
            passwd_allowed = env['interactive'] or not self.env.user._rpc_api_keys_only()
            if passwd_allowed and self.env.user.active and self._auth_imap_local_password_is_empty():
                Imap = self.env['res.company.imap']
                for conf in Imap._get_imap_dicts():
                    if Imap._authenticate(conf, self.env.user.login, credential['password']):
                        return {
                            'uid': self.env.user.id,
                            'auth_method': 'imap',
                            'mfa': 'default',
                        }
            raise

    def _auth_imap_local_password_is_empty(self):
        # 'password' is write-only on the res.users model (its compute
        # always reports '' - see _compute_password), so like core's own
        # _check_credentials we have to read it back with raw SQL instead
        # of the ORM.
        self.env.cr.execute(
            'SELECT password IS NULL FROM res_users WHERE id=%s',
            (self.env.user.id,),
        )
        [is_empty] = self.env.cr.fetchone()
        return is_empty

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
        # 'password' feeds _compute_session_token() (an ormcache'd method),
        # so bypassing write() here would leave every worker process - not
        # just this one - serving stale session tokens for this user until
        # its cache happens to be evicted some other way. Concretely: an
        # already-logged-in user would get bounced between "valid session"
        # and "session expired" depending on which worker handles each
        # request, flooding odoo.log with "Session expired" and hammering
        # the client with re-auth retries. registry.clear_cache() busts the
        # cache locally and signals every other worker to do the same, the
        # same call core's own write() makes for this same field (see
        # ResUsers._get_invalidation_fields()).
        self.env.registry.clear_cache()
