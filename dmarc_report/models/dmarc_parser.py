# -*- coding: utf-8 -*-
"""Reads DMARC aggregate reports (RFC 7489, appendix C).

Reports arrive as plain XML, gzip or zip. Everything here treats the input as
hostile: decompressed size is capped, and the XML parser resolves no entities
and fetches nothing from the network.
"""
import gzip
import io
import zipfile
from datetime import datetime, timezone

from lxml import etree

MAX_XML_BYTES = 20 * 1024 * 1024
XML_SUFFIXES = ('.xml',)
GZIP_MAGIC = b'\x1f\x8b'
ZIP_MAGIC = b'PK\x03\x04'


class DmarcParseError(ValueError):
    pass


def _limited_read(stream):
    data = stream.read(MAX_XML_BYTES + 1)
    if len(data) > MAX_XML_BYTES:
        raise DmarcParseError('report is larger than %s MB once unpacked' % (MAX_XML_BYTES // 1048576))
    return data


def extract_xml_documents(filename, content):
    """Return the XML documents (as bytes) inside one email attachment."""
    if isinstance(content, str):
        content = content.encode('utf-8')
    if not content:
        return []
    name = (filename or '').lower()
    if content[:4] == ZIP_MAGIC or name.endswith('.zip'):
        try:
            archive = zipfile.ZipFile(io.BytesIO(content))
        except zipfile.BadZipFile as exc:
            raise DmarcParseError('not a readable zip file') from exc
        documents = []
        for member in archive.infolist():
            if member.is_dir() or not member.filename.lower().endswith(XML_SUFFIXES):
                continue
            with archive.open(member) as handle:
                documents.append(_limited_read(handle))
        return documents
    if content[:2] == GZIP_MAGIC or name.endswith('.gz'):
        try:
            with gzip.GzipFile(fileobj=io.BytesIO(content)) as handle:
                return [_limited_read(handle)]
        except (OSError, EOFError) as exc:
            raise DmarcParseError('not a readable gzip file') from exc
    if name.endswith(XML_SUFFIXES) or content.lstrip()[:5] in (b'<?xml', b'<feed'):
        if len(content) > MAX_XML_BYTES:
            raise DmarcParseError('report is too large')
        return [content]
    return []


def _text(node, path, default=''):
    found = node.find(path)
    return (found.text or '').strip() if found is not None and found.text else default


def _timestamp(value):
    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc).replace(tzinfo=None)
    except (TypeError, ValueError, OverflowError, OSError):
        return False


def parse_report(xml_bytes):
    """Parse one aggregate report into plain dicts."""
    parser = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=False, remove_comments=True)
    try:
        root = etree.fromstring(xml_bytes, parser=parser)
    except etree.XMLSyntaxError as exc:
        raise DmarcParseError('not valid XML: %s' % exc) from exc
    # Some reporters add a namespace; strip it so the paths below always match.
    for element in root.iter():
        if isinstance(element.tag, str) and '}' in element.tag:
            element.tag = element.tag.split('}', 1)[1]
    if root.tag != 'feedback':
        raise DmarcParseError('not a DMARC aggregate report')
    meta = root.find('report_metadata')
    policy = root.find('policy_published')
    if meta is None or policy is None:
        raise DmarcParseError('report is missing its metadata or published policy')
    report = {
        'org_name': _text(meta, 'org_name') or 'Unknown reporter',
        'org_email': _text(meta, 'email'),
        'external_id': _text(meta, 'report_id'),
        'date_begin': _timestamp(_text(meta, 'date_range/begin')),
        'date_end': _timestamp(_text(meta, 'date_range/end')),
        'domain': _text(policy, 'domain').lower().rstrip('.'),
        'policy_p': _text(policy, 'p'),
        'policy_sp': _text(policy, 'sp'),
        'policy_pct': _text(policy, 'pct'),
        'policy_adkim': _text(policy, 'adkim') or 'r',
        'policy_aspf': _text(policy, 'aspf') or 'r',
        'records': [],
    }
    if not report['external_id'] or not report['domain']:
        raise DmarcParseError('report has no report ID or domain')
    for record in root.findall('record'):
        row = record.find('row')
        if row is None:
            continue
        try:
            count = int(_text(row, 'count', '0'))
        except ValueError:
            count = 0
        dkim_results = [
            '%s=%s' % (_text(node, 'domain'), _text(node, 'result'))
            for node in record.findall('auth_results/dkim')]
        spf_results = [
            '%s=%s' % (_text(node, 'domain'), _text(node, 'result'))
            for node in record.findall('auth_results/spf')]
        report['records'].append({
            'source_ip': _text(row, 'source_ip'),
            'count': count,
            'disposition': _text(row, 'policy_evaluated/disposition') or 'none',
            'dkim_aligned': _text(row, 'policy_evaluated/dkim') == 'pass',
            'spf_aligned': _text(row, 'policy_evaluated/spf') == 'pass',
            'header_from': _text(record, 'identifiers/header_from').lower(),
            'envelope_from': _text(record, 'identifiers/envelope_from').lower(),
            'dkim_results': ', '.join(dkim_results),
            'spf_results': ', '.join(spf_results),
        })
    return report
