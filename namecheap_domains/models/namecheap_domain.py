# -*- coding: utf-8 -*-
from odoo import api, fields, models


class NamecheapDomain(models.Model):
    """One domain this business owns through a namecheap.server account.

    Phase 1/2 don't yet automate actual registration
    (namecheap.domains.create isn't called anywhere yet - see the
    module README), so for now these are created by hand as domains
    are bought; a later phase should create them automatically as part
    of checkout instead of replacing this model.
    """
    _name = 'namecheap.domain'
    _description = 'Owned Domain'
    _inherit = ['mail.thread']
    _rec_name = 'name'
    _order = 'name'

    name = fields.Char(
        required=True, help="The full domain, e.g. \"example.com\".")
    tld = fields.Char(compute='_compute_tld', store=True)
    server_id = fields.Many2one('namecheap.server', required=True)
    partner_id = fields.Many2one('res.partner', string="Owner")
    registered_on = fields.Date()
    expires_on = fields.Date()
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('expired', 'Expired'),
    ], default='draft', required=True)
    active = fields.Boolean(default=True)

    _name_uniq = models.Constraint('unique(name)', "This domain is already tracked.")

    @api.depends('name')
    def _compute_tld(self):
        for domain in self:
            domain.tld = domain.name.split('.', 1)[1] if domain.name and '.' in domain.name else False
