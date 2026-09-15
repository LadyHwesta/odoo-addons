# -*- coding: utf-8 -*-
from odoo import _, fields, models


class NamecheapDomain(models.Model):
    _inherit = 'namecheap.domain'

    state = fields.Selection(
        selection_add=[('cancelled', 'Not Renewing')],
        ondelete={'cancelled': 'set default'})

    def action_cancel_renewal(self):
        """Domains had no cancel action at all before this module.
        Stops both sides of auto-renewal, not just the Odoo-side
        billing: namecheap_domains_sale's own _cron_renew_domains only
        ever considers domains with state == 'active' in its search
        domain, so moving to this new 'cancelled' state is what
        actually stops the real registrar-side renewal attempt (ending
        the contract line alone would NOT have stopped it - that cron
        gates on "no unpaid invoice on the contract", not on whether
        the contract line is still open, so a cancelled-but-still-
        'active' domain would keep getting renewed for real at
        Namecheap with nothing billing the customer for it). Ending
        the currently-open contract line on top of that stops future
        invoices being generated at all. Doesn't touch the domain's
        real registration at Namecheap - it simply won't be renewed
        once it's due to expire.
        """
        today = fields.Date.context_today(self)
        for domain in self:
            if domain.contract_id:
                domain.contract_id.contract_line_ids.filtered(
                    lambda line: not line.date_end or line.date_end >= today
                ).write({'date_end': today})
            domain.state = 'cancelled'

    def _subscription_summary(self):
        self.ensure_one()
        line = self.env['contract.line']
        if self.contract_id:
            today = fields.Date.context_today(self)
            line = self.contract_id.contract_line_ids.filtered(
                lambda l: not l.date_end or l.date_end >= today)[:1]
        return {
            'name': _("Domain: %(domain)s", domain=self.name),
            'state': self.state,
            'next_invoice_date': line.recurring_next_date if line else False,
            'monthly_amount': line.price_unit if line else 0.0,
            'can_upgrade': False,
            'can_cancel': self.state == 'active',
            'has_payment_method': bool(self.payment_token_id),
            'portal_view_url': f'/my/contracts/{self.contract_id.id}' if self.contract_id else False,
        }
