# -*- coding: utf-8 -*-
from odoo import api, fields, models

DISPOSITIONS = [('none', 'Delivered'), ('quarantine', 'Sent to spam'), ('reject', 'Rejected')]


class DmarcRecord(models.Model):
    """Mail from one sending server, as counted in one report."""
    _name = 'dmarc.record'
    _description = 'DMARC Report Source'
    _order = 'count desc, id'
    _rec_name = 'sender_label'

    report_id = fields.Many2one('dmarc.report', required=True, ondelete='cascade', index=True)
    domain_id = fields.Many2one(related='report_id.domain_id', store=True, index=True)
    date_end = fields.Datetime(related='report_id.date_end', store=True, string='Report date')
    source_ip = fields.Char(string='Server IP', required=True)
    hostname = fields.Char(string='Server name')
    provider = fields.Char(string='Provider')
    sender_label = fields.Char(compute='_compute_sender_label', store=True, string='Sender')
    count = fields.Integer(string='Messages')
    disposition = fields.Selection(DISPOSITIONS, string='What happened', default='none')
    dkim_aligned = fields.Boolean(string='DKIM passed')
    spf_aligned = fields.Boolean(string='SPF passed')
    passed = fields.Boolean(compute='_compute_passed', store=True, string='DMARC passed')
    header_from = fields.Char(string='From domain')
    envelope_from = fields.Char(string='Return-path domain')
    dkim_results = fields.Char(string='DKIM signatures')
    spf_results = fields.Char(string='SPF checks')

    @api.depends('provider', 'hostname', 'source_ip')
    def _compute_sender_label(self):
        for record in self:
            record.sender_label = record.provider or record.hostname or record.source_ip

    @api.depends('dkim_aligned', 'spf_aligned')
    def _compute_passed(self):
        for record in self:
            record.passed = record.dkim_aligned or record.spf_aligned

    @api.model_create_multi
    def create(self, vals_list):
        allowed = {key for key, _label in DISPOSITIONS}
        for vals in vals_list:
            if vals.get('disposition') not in allowed:
                vals['disposition'] = 'none'
        return super().create(vals_list)
