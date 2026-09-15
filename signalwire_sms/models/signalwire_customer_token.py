# -*- coding: utf-8 -*-
from odoo import models, fields


class SignalWireCustomerToken(models.Model):
    """A real, independently-usable SignalWire API credential handed
    to a subproject's customer - see
    signalwire.subproject.action_issue_customer_token for why this
    exists instead of the subproject's own (unretrievable) auth_token.

    The secret is stored in plain text, same as every other API
    credential in this project (signalwire.server.api_token,
    namecheap.server.api_key, ...) - visible to the owning customer on
    their own portal page (the whole point - they need to copy it into
    their own systems) and to internal staff, not hidden behind
    developer mode or similar.
    """
    _name = 'signalwire.customer.token'
    _description = 'SignalWire Customer Access Token'
    _rec_name = 'name'

    name = fields.Char(default='Customer Access Token', required=True)
    subproject_id = fields.Many2one(
        'signalwire.subproject', required=True, ondelete='cascade')
    signalwire_token_id = fields.Char(
        string="SignalWire Token ID", required=True,
        help="Needed to revoke this token later - not the secret "
             "itself, just SignalWire's own record ID for it.")
    token = fields.Char(
        required=True,
        help="The actual secret - pairs with this subproject's own "
             "Account SID (not the parent project's ID) as the Basic "
             "Auth username for any Twilio-compatible client.")
    active = fields.Boolean(default=True)

    def action_revoke(self):
        """**Known gap, confirmed live 2026-09-15**: this genuinely
        deletes the token's own metadata record at SignalWire (a
        second DELETE, or a GET, on the same token ID afterward both
        correctly 404 - it's really gone from the token list) - but
        the secret itself kept authenticating successfully against
        the Compatibility API for at least 15 seconds afterward, with
        no sign of it ever stopping. Same broken-DELETE pattern as
        signalwire.subproject.action_close's own gap - possibly a
        trial-account restriction on destructive actions specifically
        (returns success without completing, to avoid revealing the
        restriction), not confirmed either way.

        Bottom line: **do not treat this button as an actual security
        boundary yet**. If a customer's access genuinely needs to be
        cut off, this alone isn't proven sufficient - escalate to
        SignalWire support, or as a heavier hammer, close the whole
        subproject (which has the same unconfirmed-effect caveat).
        """
        for token in self:
            client = token.subproject_id.server_id._get_client()
            client.project_delete(f'project/tokens/{token.signalwire_token_id}')
            token.active = False
