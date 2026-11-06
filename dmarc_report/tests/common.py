# -*- coding: utf-8 -*-
import gzip
import io
import time
import zipfile
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def report_xml(domain='example.com', org='google.com', report_id='r1', p='none', days_ago=1, records=()):
    """A DMARC aggregate report in the format providers send.

    records: (ip, count, dkim_pass, spf_pass, disposition) tuples.
    """
    end = int(time.time()) - days_ago * 86400
    rows = ''.join(f"""
  <record>
    <row><source_ip>{ip}</source_ip><count>{count}</count>
      <policy_evaluated><disposition>{disposition}</disposition>
        <dkim>{'pass' if dkim else 'fail'}</dkim><spf>{'pass' if spf else 'fail'}</spf></policy_evaluated></row>
    <identifiers><header_from>{domain}</header_from></identifiers>
    <auth_results><dkim><domain>{domain}</domain><result>{'pass' if dkim else 'fail'}</result></dkim>
      <spf><domain>{domain}</domain><result>{'pass' if spf else 'fail'}</result></spf></auth_results>
  </record>""" for ip, count, dkim, spf, disposition in records)
    return f"""<?xml version="1.0" encoding="UTF-8" ?>
<feedback>
  <report_metadata><org_name>{org}</org_name><email>noreply-dmarc-support@{org}</email>
    <report_id>{report_id}</report_id><date_range><begin>{end - 86400}</begin><end>{end}</end></date_range>
  </report_metadata>
  <policy_published><domain>{domain}</domain><adkim>r</adkim><aspf>r</aspf><p>{p}</p><sp>{p}</sp><pct>100</pct></policy_published>{rows}
</feedback>
""".encode()


def gzipped(data):
    return gzip.compress(data)


def zipped(data, name='report.xml'):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(name, data)
    return buffer.getvalue()


def report_email(attachment, filename, message_id='<r1@google.com>', to='dmarc@example.com'):
    """A raw email as Google sends it, with the report attached."""
    msg = MIMEMultipart()
    msg['From'] = 'noreply-dmarc-support@google.com'
    msg['To'] = to
    msg['Subject'] = 'Report domain: example.com Submitter: google.com Report-ID: r1'
    msg['Message-Id'] = message_id
    msg.attach(MIMEText('This is an aggregate report from google.com.', 'plain'))
    part = MIMEApplication(attachment, 'gzip' if filename.endswith('.gz') else 'zip')
    part.add_header('Content-Disposition', 'attachment', filename=filename)
    msg.attach(part)
    return msg.as_string()
