# -*- coding: utf-8 -*-
from odoo import _, models, fields
from odoo.exceptions import UserError

# Scoped down to just what a resold SMS customer needs - not calling/
# video/etc. Widen this (or make it configurable) if a future phase
# resells voice access through the same mechanism.
CUSTOMER_TOKEN_PERMISSIONS = ['messaging', 'numbers']


class SignalWireSubproject(models.Model):
    _inherit = 'signalwire.subproject'

    customer_token_ids = fields.One2many(
        'signalwire.customer.token', 'subproject_id', string="Access Tokens")

    def action_issue_customer_token(self):
        """Give this subproject's customer a real, independently-
        usable SignalWire credential - NOT the subproject's own
        auth_token (confirmed in signalwire_voip's own tests/README
        that the API never actually returns that value, by design).
        Instead this creates a separate, permission-scoped Project API
        Token tied to the subproject - confirmed live 2026-09-15 that
        such a token DOES come back in full, once, and authenticates
        as ``{subproject account_sid}:{token}`` (not the parent
        project's own ID).
        """
        self.ensure_one()
        if not self.account_sid:
            raise UserError(_("%(name)s isn't provisioned yet.", name=self.name))
        client = self.server_id._get_client()
        result = client.project_post(
            'project/tokens', name=f'{self.name} - Customer Access',
            permissions=CUSTOMER_TOKEN_PERMISSIONS, subproject_id=self.account_sid)
        return self.env['signalwire.customer.token'].create({
            'subproject_id': self.id,
            'signalwire_token_id': result['id'],
            'token': result['token'],
        })
