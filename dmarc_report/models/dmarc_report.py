# -*- coding: utf-8 -*-
import logging

from odoo import api, fields, models

from .dmarc_parser import DmarcParseError, extract_xml_documents, parse_report
from .dmarc_senders import provider_for, reverse_dns

_logger = logging.getLogger(__name__)


class DmarcReport(models.Model):
    """One aggregate report from one mail provider about one domain."""
    _name = 'dmarc.report'
    _description = 'DMARC Report'
    _inherit = ['mail.thread']
    _order = 'date_end desc, id desc'

    name = fields.Char(compute='_compute_name', store=True)
    state = fields.Selection([
        ('done', 'Read'),
        ('error', "Couldn't read"),
    ], default='done', required=True)
    error = fields.Text(string='Problem', readonly=True)
    domain_id = fields.Many2one('dmarc.domain', ondelete='cascade', index=True)
    org_name = fields.Char(string='Reported by')
    org_email = fields.Char(string='Reporter email')
    external_id = fields.Char(string='Report ID', index=True)
    date_begin = fields.Datetime(string='From')
    date_end = fields.Datetime(string='To')
    policy_p = fields.Char(string='Policy')
    policy_sp = fields.Char(string='Subdomain policy')
    policy_pct = fields.Char(string='Percent')
    policy_adkim = fields.Char(string='DKIM alignment')
    policy_aspf = fields.Char(string='SPF alignment')
    record_ids = fields.One2many('dmarc.record', 'report_id', string='Sources')
    message_count = fields.Integer(compute='_compute_counts', store=True, string='Messages sent')
    pass_count = fields.Integer(compute='_compute_counts', store=True, string='Passed')

    _report_unique = models.Constraint(
        'unique(org_name, external_id)',
        'This report has already been read.')

    @api.depends('org_name', 'domain_id', 'date_end', 'state')
    def _compute_name(self):
        for report in self:
            if report.state == 'error':
                report.name = self.env._("Unreadable report")
            else:
                report.name = '%s: %s' % (report.org_name or '?', report.domain_id.name or '?')

    @api.depends('record_ids.count', 'record_ids.passed')
    def _compute_counts(self):
        for report in self:
            report.message_count = sum(report.record_ids.mapped('count'))
            report.pass_count = sum(report.record_ids.filtered('passed').mapped('count'))

    # -- Incoming mail --------------------------------------------------

    @api.model
    def message_new(self, msg_dict, custom_values=None):
        """Called by an Incoming Mail Server set to create DMARC Reports.

        One email normally holds one report, but every report attached is
        read. A report already read (same reporter and report ID) is skipped.
        Anything unreadable becomes an error record, so it's visible rather
        than silently dropped.
        """
        reports = self.browse()
        problems = []
        for attachment in msg_dict.get('attachments') or []:
            filename, content = attachment[0], attachment[1]
            try:
                documents = extract_xml_documents(filename, content)
            except DmarcParseError as exc:
                problems.append('%s: %s' % (filename, exc))
                continue
            for document in documents:
                try:
                    reports |= self._create_from_xml(document)
                except DmarcParseError as exc:
                    problems.append('%s: %s' % (filename, exc))
        if reports:
            return reports[0]
        return self.create({
            'state': 'error',
            'error': '\n'.join(problems) or self.env._(
                "The email had no DMARC report attached: %(subject)s",
                subject=msg_dict.get('subject') or ''),
            'org_email': msg_dict.get('email_from'),
        })

    @api.model
    def _create_from_xml(self, xml_bytes):
        data = parse_report(xml_bytes)
        existing = self.search([
            ('org_name', '=', data['org_name']), ('external_id', '=', data['external_id'])], limit=1)
        if existing:
            return existing
        domain = self.env['dmarc.domain']._get_or_create(data['domain'])
        rows = data.pop('records')
        data.pop('domain')
        hostnames = {}
        for row in rows:
            ip = row['source_ip']
            if ip not in hostnames:
                hostnames[ip] = reverse_dns(ip)
            row['hostname'] = hostnames[ip]
            row['provider'] = provider_for(hostnames[ip])
        report = self.create(dict(data, domain_id=domain.id, record_ids=[(0, 0, row) for row in rows]))
        domain._announce_new_failing_senders(report.record_ids)
        return report
