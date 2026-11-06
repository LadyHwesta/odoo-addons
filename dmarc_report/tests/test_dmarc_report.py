# -*- coding: utf-8 -*-
from unittest.mock import patch

from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, new_test_user, tagged

from .common import gzipped, report_email, report_xml, zipped

RDNS = 'odoo.addons.dmarc_report.models.dmarc_report.reverse_dns'
HOSTS = {'192.0.2.10': 'mail-sor-f41.google.com', '192.0.2.20': 'node30-ca.n0c.com',
         '198.51.100.66': 'scanner.badhost.example'}


def fake_rdns(ip):
    return HOSTS.get(ip, '')


@tagged('post_install', '-at_install')
class TestDmarcReport(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Report = cls.env['dmarc.report']
        params = cls.env['ir.config_parameter'].sudo()
        params.set_param('dmarc_report.reporting_address', 'dmarc@meskis.net')
        params.set_param('dmarc_report.alert_new_senders', 'True')

    def _receive(self, xml, filename='google.com!example.com!1!2.xml.gz', message_id='<r1@google.com>'):
        payload = gzipped(xml) if filename.endswith('.gz') else zipped(xml)
        with patch(RDNS, side_effect=fake_rdns):
            thread_id = self.env['mail.thread'].message_process(
                'dmarc.report', report_email(payload, filename, message_id=message_id))
        return self.Report.browse(thread_id)

    def test_a_real_email_becomes_a_report_with_named_senders(self):
        report = self._receive(report_xml(records=[
            ('192.0.2.10', 40, True, True, 'none'),
            ('198.51.100.66', 3, False, False, 'none'),
        ]))

        self.assertEqual(report.state, 'done')
        self.assertEqual(report.domain_id.name, 'example.com')
        self.assertEqual(report.org_name, 'google.com')
        self.assertEqual(report.message_count, 43)
        self.assertEqual(report.pass_count, 40)
        google = report.record_ids.filtered(lambda r: r.source_ip == '192.0.2.10')
        self.assertEqual(google.sender_label, 'Google')
        unknown = report.record_ids - google
        self.assertEqual(unknown.sender_label, 'scanner.badhost.example')
        self.assertFalse(unknown.passed)

    def test_zip_attachments_work_too(self):
        report = self._receive(report_xml(org='outlook.com', report_id='z1',
                                          records=[('192.0.2.20', 2, True, False, 'none')]),
                               filename='report.zip', message_id='<z1@outlook.com>')
        self.assertEqual(report.record_ids.sender_label, 'PlanetHoster')

    def test_the_same_report_is_only_read_once(self):
        xml = report_xml(records=[('192.0.2.10', 1, True, True, 'none')])
        first = self._receive(xml, message_id='<a@google.com>')
        second = self._receive(xml, message_id='<b@google.com>')
        self.assertEqual(first, second)
        self.assertEqual(self.Report.search_count([('external_id', '=', 'r1')]), 1)

    def test_unreadable_attachment_is_kept_as_an_error(self):
        with patch(RDNS, side_effect=fake_rdns):
            thread_id = self.env['mail.thread'].message_process(
                'dmarc.report', report_email(b'not really gzip', 'r.xml.gz', message_id='<bad@x>'))
        report = self.Report.browse(thread_id)
        self.assertEqual(report.state, 'error')
        self.assertIn('gzip', report.error)

    def test_findings_explain_known_and_unknown_failures(self):
        report = self._receive(report_xml(p='quarantine', records=[
            ('192.0.2.10', 10, False, False, 'quarantine'),
            ('198.51.100.66', 4, False, False, 'quarantine'),
            ('192.0.2.20', 6, True, False, 'none'),
        ]))
        findings = report.domain_id.findings_html

        self.assertIn('20 messages were sent as example.com', findings)
        self.assertIn('Google sent 10 of its 10 messages as you without passing', findings)
        self.assertIn('set up DKIM signing for example.com there', findings)
        self.assertIn('An unrecognized server, scanner.badhost.example', findings)
        self.assertIn('sent some of it to spam', findings)
        self.assertIn('6 messages passed on DKIM alone', findings)
        self.assertEqual(report.domain_id.failing_sender_count, 2)
        self.assertAlmostEqual(report.domain_id.pass_rate, 30.0)

    def test_suggests_tightening_a_policy_that_everything_passes(self):
        for day in range(7):
            self._receive(report_xml(report_id='d%s' % day, days_ago=day + 1,
                                     records=[('192.0.2.10', 50, True, True, 'none')]),
                          message_id='<d%s@google.com>' % day)
        domain = self.env['dmarc.domain'].search([('name', '=', 'example.com')])
        self.assertIn('p=quarantine', domain.findings_html)

    def test_findings_only_cover_the_chosen_window(self):
        report = self._receive(report_xml(days_ago=60, records=[('198.51.100.66', 9, False, False, 'none')]))
        self.assertEqual(report.domain_id.message_total, 0)
        self.assertIn('No reports in the last 30 days', report.domain_id.findings_html)

    def test_alerts_once_per_new_failing_sender(self):
        report = self._receive(report_xml(records=[('198.51.100.66', 3, False, False, 'none')]))
        domain = report.domain_id
        alerts = lambda: domain.message_ids.filtered(lambda m: 'New sender failing DMARC' in (m.body or ''))
        self.assertEqual(len(alerts()), 1)

        self._receive(report_xml(report_id='r2', records=[('198.51.100.66', 5, False, False, 'none')]),
                      message_id='<r2@google.com>')
        self.assertEqual(len(alerts()), 1)

    def test_managers_follow_new_domains_and_alerts_name_the_server_once(self):
        manager = new_test_user(self.env, login='dmarc_mgr', groups='base.group_user,dmarc_report.group_dmarc_manager')
        report = self._receive(report_xml(records=[('198.51.100.66', 3, False, False, 'none'),
                                                   ('192.0.2.10', 2, False, False, 'none')]))
        domain = report.domain_id

        self.assertIn(manager.partner_id, domain.message_partner_ids)
        bodies = domain.message_ids.mapped('body')
        self.assertTrue(any('scanner.badhost.example (server 198.51.100.66) sent 3' in (b or '') for b in bodies))
        self.assertTrue(any('Google (server 192.0.2.10) sent 2' in (b or '') for b in bodies))

    def test_alerts_can_be_switched_off(self):
        self.env['ir.config_parameter'].sudo().set_param('dmarc_report.alert_new_senders', False)
        report = self._receive(report_xml(records=[('198.51.100.66', 3, False, False, 'none')]))
        self.assertFalse(report.domain_id.message_ids.filtered(
            lambda m: 'New sender failing DMARC' in (m.body or '')))

    def test_suggested_records_include_the_permission_record(self):
        domain = self.env['dmarc.domain'].create({'name': 'example.com'})
        self.assertEqual(domain.suggested_record, 'v=DMARC1; p=none; rua=mailto:dmarc@meskis.net')
        self.assertEqual(domain.permission_record, 'example.com._report._dmarc.meskis.net  TXT  "v=DMARC1"')
        own = self.env['dmarc.domain'].create({'name': 'meskis.net'})
        self.assertFalse(own.permission_record)

    def test_viewers_can_read_but_not_change(self):
        report = self._receive(report_xml(records=[('192.0.2.10', 1, True, True, 'none')]))
        viewer = new_test_user(self.env, login='dmarc_viewer', groups='base.group_user,dmarc_report.group_dmarc_user')
        outsider = new_test_user(self.env, login='dmarc_outsider', groups='base.group_user')

        self.assertTrue(report.domain_id.with_user(viewer).findings_html)
        with self.assertRaises(AccessError):
            report.domain_id.with_user(viewer).write({'name': 'other.com'})
        with self.assertRaises(AccessError):
            report.with_user(outsider).read(['org_name'])
