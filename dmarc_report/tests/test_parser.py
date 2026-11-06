# -*- coding: utf-8 -*-
import gzip

from odoo.tests import BaseCase, tagged

from ..models.dmarc_parser import DmarcParseError, extract_xml_documents, parse_report
from ..models.dmarc_senders import provider_for
from .common import gzipped, report_xml, zipped


@tagged('post_install', '-at_install')
class TestDmarcParser(BaseCase):

    def test_reads_plain_gzip_and_zip_reports(self):
        xml = report_xml(records=[('192.0.2.1', 5, True, True, 'none')])
        for name, payload in (('r.xml', xml), ('r.xml.gz', gzipped(xml)), ('r.zip', zipped(xml))):
            with self.subTest(name=name):
                [document] = extract_xml_documents(name, payload)
                report = parse_report(document)
                self.assertEqual(report['domain'], 'example.com')
                self.assertEqual(report['records'][0]['count'], 5)
                self.assertTrue(report['records'][0]['dkim_aligned'])

    def test_reads_xml_delivered_as_text(self):
        xml = report_xml(records=[('192.0.2.1', 1, False, True, 'none')])
        [document] = extract_xml_documents('report.xml', xml.decode())
        self.assertEqual(parse_report(document)['records'][0]['source_ip'], '192.0.2.1')

    def test_ignores_namespaces(self):
        xml = report_xml().replace(b'<feedback>', b'<feedback xmlns="urn:ietf:params:xml:ns:dmarc-2.0">')
        self.assertEqual(parse_report(xml)['org_name'], 'google.com')

    def test_does_not_resolve_external_entities(self):
        xml = (b'<?xml version="1.0"?><!DOCTYPE feedback [<!ENTITY x SYSTEM "file:///etc/passwd">]>'
               + report_xml().split(b'?>', 1)[1].replace(b'<org_name>google.com', b'<org_name>&x;google.com'))
        report = parse_report(xml)
        self.assertNotIn('root:', report['org_name'])

    def test_refuses_oversized_archives(self):
        bomb = gzip.compress(b'<feedback>' + b' ' * (21 * 1024 * 1024))
        with self.assertRaises(DmarcParseError):
            extract_xml_documents('bomb.xml.gz', bomb)

    def test_rejects_things_that_are_not_reports(self):
        with self.assertRaises(DmarcParseError):
            parse_report(b'<html><body>hi</body></html>')
        with self.assertRaises(DmarcParseError):
            extract_xml_documents('broken.zip', b'PK\x03\x04garbage')
        self.assertEqual(extract_xml_documents('logo.png', b'\x89PNG...'), [])

    def test_names_providers_from_hostnames(self):
        self.assertEqual(provider_for('mail-sor-f41.google.com'), 'Google')
        self.assertEqual(provider_for('node30-ca.n0c.com'), 'PlanetHoster')
        self.assertEqual(provider_for('mail.protection.outlook.com'), 'Microsoft 365')
        self.assertEqual(provider_for('209-151-144-11.us-sjo1.upcloud.host'), 'UpCloud server')
        self.assertEqual(provider_for('evilgoogle.com'), '')
        self.assertEqual(provider_for(''), '')
