# -*- coding: utf-8 -*-
"""Names the servers that send mail, from their reverse DNS."""
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
import socket

LOOKUP_TIMEOUT = 3

# Reverse DNS suffix -> provider name. Longest suffix wins.
KNOWN_PROVIDERS = {
    'google.com': 'Google',
    '1e100.net': 'Google',
    'googleusercontent.com': 'Google Cloud',
    'outlook.com': 'Microsoft 365',
    'protection.outlook.com': 'Microsoft 365',
    'hotmail.com': 'Microsoft (Outlook.com)',
    'n0c.com': 'PlanetHoster',
    'planethoster.net': 'PlanetHoster',
    'upcloud.host': 'UpCloud server',
    'amazonses.com': 'Amazon SES',
    'sendgrid.net': 'SendGrid',
    'mailgun.net': 'Mailgun',
    'mailgun.org': 'Mailgun',
    'mcsv.net': 'Mailchimp',
    'mandrillapp.com': 'Mailchimp Transactional',
    'zoho.com': 'Zoho Mail',
    'zohomail.com': 'Zoho Mail',
    'yahoo.com': 'Yahoo',
    'protonmail.ch': 'Proton Mail',
    'mailjet.com': 'Mailjet',
    'sparkpostmail.com': 'SparkPost',
    'postmarkapp.com': 'Postmark',
    'brevo.com': 'Brevo',
    'sendinblue.com': 'Brevo',
    'odoo.com': 'Odoo Online',
}

_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix='dmarc-rdns')


def reverse_dns(ip):
    """Hostname for an IP, or '' if it has none or the lookup is slow."""
    if not ip:
        return ''
    future = _executor.submit(socket.gethostbyaddr, ip)
    try:
        return future.result(timeout=LOOKUP_TIMEOUT)[0].lower().rstrip('.')
    except (FutureTimeout, OSError, UnicodeError):
        return ''


def provider_for(hostname):
    hostname = (hostname or '').lower().rstrip('.')
    best = ''
    for suffix in KNOWN_PROVIDERS:
        if (hostname == suffix or hostname.endswith('.' + suffix)) and len(suffix) > len(best):
            best = suffix
    return KNOWN_PROVIDERS.get(best, '')
