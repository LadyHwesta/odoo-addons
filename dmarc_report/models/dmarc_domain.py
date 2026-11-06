# -*- coding: utf-8 -*-
from collections import OrderedDict
from datetime import timedelta

from markupsafe import Markup, escape

from odoo import api, fields, models

PARAM = 'dmarc_report.'
POLICY_LABELS = {'none': 'monitor only (none)', 'quarantine': 'send to spam (quarantine)',
                 'reject': 'reject'}


class DmarcDomain(models.Model):
    """A domain that receives DMARC reports, with what they say about it."""
    _name = 'dmarc.domain'
    _description = 'DMARC Domain'
    _inherit = ['mail.thread']
    _order = 'name'

    name = fields.Char(required=True, index=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    report_ids = fields.One2many('dmarc.report', 'domain_id')
    record_ids = fields.One2many('dmarc.record', 'domain_id')
    report_count = fields.Integer(compute='_compute_summary', string='Reports')
    message_total = fields.Integer(compute='_compute_summary', string='Messages sent')
    pass_rate = fields.Float(compute='_compute_summary', string='Passed (%)', digits=(5, 1))
    failing_sender_count = fields.Integer(compute='_compute_summary', string='Failing senders')
    last_report_date = fields.Datetime(compute='_compute_summary', string='Latest report')
    current_policy = fields.Char(compute='_compute_summary', string='Published policy')
    findings_html = fields.Html(compute='_compute_summary', sanitize=False, string='Findings')
    suggested_record = fields.Char(compute='_compute_suggested_record', string='Suggested DMARC record')
    permission_record = fields.Char(compute='_compute_suggested_record', string='Permission record')

    _name_unique = models.Constraint('unique(name, company_id)', 'This domain is already listed.')

    # -- Settings -------------------------------------------------------

    def _param(self, key, default=None):
        return self.env['ir.config_parameter'].sudo().get_param(PARAM + key, default)

    def _window_days(self):
        try:
            return max(int(self._param('window_days', 30)), 1)
        except (TypeError, ValueError):
            return 30

    @api.model
    def _get_or_create(self, name):
        name = (name or '').lower().rstrip('.')
        domain = self.with_context(active_test=False).search([('name', '=', name)], limit=1)
        if domain:
            return domain
        domain = self.create({'name': name})
        # Followers are notified by email or in Odoo's Inbox, whichever they've chosen.
        managers = self.env.ref('dmarc_report.group_dmarc_manager').sudo().all_user_ids
        domain.message_subscribe(partner_ids=managers.filtered(lambda u: u.active and not u.share).partner_id.ids)
        return domain

    # -- Summary and findings -------------------------------------------

    def _recent_records(self):
        since = fields.Datetime.now() - timedelta(days=self._window_days())
        return self.record_ids.filtered(lambda r: r.date_end and r.date_end >= since)

    @api.model
    def _group_by_sender(self, records):
        senders = OrderedDict()
        for record in records.sorted('count', reverse=True):
            entry = senders.setdefault(record.sender_label, {
                'label': record.sender_label, 'known': bool(record.provider),
                'total': 0, 'passed': 0, 'dkim_only': 0, 'spf_only': 0,
                'dispositions': set(), 'example_ip': record.source_ip,
                'hostname': record.hostname,
            })
            entry['total'] += record.count
            if record.passed:
                entry['passed'] += record.count
                if record.dkim_aligned and not record.spf_aligned:
                    entry['dkim_only'] += record.count
            else:
                entry['dispositions'].add(record.disposition)
        return list(senders.values())

    @api.depends('record_ids', 'report_ids')
    def _compute_summary(self):
        for domain in self:
            reports = domain.report_ids.filtered(lambda r: r.state == 'done')
            records = domain._recent_records()
            total = sum(records.mapped('count'))
            passed = sum(records.filtered('passed').mapped('count'))
            senders = domain._group_by_sender(records)
            latest = reports.sorted('date_end', reverse=True)[:1]
            domain.report_count = len(reports)
            domain.message_total = total
            domain.pass_rate = (100.0 * passed / total) if total else 0.0
            domain.failing_sender_count = len([s for s in senders if s['passed'] < s['total']])
            domain.last_report_date = latest.date_end
            domain.current_policy = latest.policy_p or False
            domain.findings_html = domain._findings_html(senders, total, passed, latest)

    def _findings_html(self, senders, total, passed, latest):
        days = self._window_days()
        if not total:
            return Markup('<p>%s</p>') % self.env._(
                "No reports in the last %(days)s days. Providers send them once a day, so the first "
                "ones arrive a day or two after the DMARC record lists a reporting address.", days=days)
        items = []
        rate = 100.0 * passed / total
        items.append(self.env._(
            "In the last %(days)s days, %(total)s messages were sent as %(domain)s from %(sources)s "
            "sources, and %(rate)s%% passed DMARC.",
            days=days, total=total, domain=self.name, sources=len(senders), rate='%.1f' % rate))
        for sender in senders:
            failed = sender['total'] - sender['passed']
            if not failed:
                continue
            outcome = self._outcome(sender['dispositions'])
            if sender['known']:
                items.append(self.env._(
                    "%(sender)s sent %(failed)s of its %(total)s messages as you without passing. If you "
                    "send mail through %(sender)s, set up DKIM signing for %(domain)s there, or add it to "
                    "your SPF record. %(outcome)s",
                    sender=sender['label'], failed=failed, total=sender['total'],
                    domain=self.name, outcome=outcome))
            else:
                items.append(self.env._(
                    "An unrecognized server, %(sender)s, sent %(failed)s messages as you that failed. If "
                    "it isn't yours, someone may be impersonating your domain. If it is, it needs DKIM "
                    "or SPF set up for %(domain)s. %(outcome)s",
                    sender=sender['label'], failed=failed, domain=self.name, outcome=outcome))
        forwarded = sum(sender['dkim_only'] for sender in senders)
        if forwarded:
            items.append(self.env._(
                "%(count)s messages passed on DKIM alone. That's normal for mail that was forwarded, "
                "and nothing to fix.", count=forwarded))
        policy = latest.policy_p
        if policy == 'none' and rate >= 98 and len(self.report_ids) >= 7:
            items.append(self.env._(
                "Nearly everything passes, so you can move from monitoring (p=none) to p=quarantine, "
                "which sends failing mail to spam."))
        elif policy == 'quarantine' and rate >= 99.5 and len(self.report_ids) >= 14:
            items.append(self.env._(
                "Everything passes under p=quarantine. When you're confident, p=reject blocks failing "
                "mail outright."))
        rows = Markup('').join(
            Markup('<tr><td>%s</td><td class="text-end">%s</td><td class="text-end">%s</td><td class="text-end">%s</td></tr>') % (
                s['label'], s['total'], s['passed'], s['total'] - s['passed'])
            for s in senders)
        table = Markup(
            '<table class="table table-sm mt-3"><thead><tr><th>%s</th><th class="text-end">%s</th>'
            '<th class="text-end">%s</th><th class="text-end">%s</th></tr></thead><tbody>%s</tbody></table>') % (
            self.env._("Sender"), self.env._("Messages"), self.env._("Passed"), self.env._("Failed"), rows)
        bullets = Markup('').join(Markup('<li>%s</li>') % escape(item) for item in items)
        return Markup('<ul>%s</ul>') % bullets + table

    def _outcome(self, dispositions):
        if 'reject' in dispositions:
            return self.env._("Receivers rejected some of it.")
        if 'quarantine' in dispositions:
            return self.env._("Receivers sent some of it to spam.")
        return self.env._("Receivers still delivered it, because your policy doesn't ask them to act.")

    @api.depends('name', 'report_ids.policy_p')
    def _compute_suggested_record(self):
        address = (self._param('reporting_address') or '').strip()
        report_domain = address.rsplit('@', 1)[-1].lower() if '@' in address else ''
        for domain in self:
            latest = domain.report_ids.filtered(lambda r: r.state == 'done').sorted('date_end', reverse=True)[:1]
            policy = latest.policy_p or 'none'
            if address:
                domain.suggested_record = 'v=DMARC1; p=%s; rua=mailto:%s' % (policy, address)
            else:
                domain.suggested_record = 'v=DMARC1; p=%s' % policy
            if report_domain and report_domain != domain.name:
                domain.permission_record = '%s._report._dmarc.%s  TXT  "v=DMARC1"' % (domain.name, report_domain)
            else:
                domain.permission_record = False

    # -- Alerts ---------------------------------------------------------

    def _announce_new_failing_senders(self, new_records):
        """Post once per sender the first time it fails for this domain."""
        self.ensure_one()
        failing = new_records.filtered(lambda r: not r.passed)
        # Turned on at install; unticking the setting deletes the value.
        if not failing or not self._param('alert_new_senders'):
            return
        earlier = self.record_ids.filtered(lambda r: not r.passed) - new_records
        seen = set(earlier.mapped('sender_label'))
        for label in OrderedDict.fromkeys(failing.mapped('sender_label')):
            if label in seen:
                continue
            records = failing.filtered(lambda r, label=label: r.sender_label == label)
            ip = records[0].source_ip
            sender = label if label == ip else '%s (server %s)' % (label, ip)
            self.message_post(
                body=self.env._(
                    "New sender failing DMARC for %(domain)s: %(sender)s sent %(count)s messages. "
                    "If you don't recognize it, someone may be sending as you.",
                    domain=self.name, sender=sender, count=sum(records.mapped('count'))),
                subtype_xmlid='mail.mt_comment',
            )
