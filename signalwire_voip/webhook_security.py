# -*- coding: utf-8 -*-
"""Checking that a webhook POST really came from SignalWire.

SignalWire signs every webhook with the project's Signing Key (Dashboard >
API Credentials > Signing Key; not the API token) in the
``X-SignalWire-Signature`` header. For form-encoded webhooks (cXML calls,
texts, status callbacks) the signature is
``base64(HMAC-SHA1(signing_key, url + every form field's name and value,
sorted by name))``. This follows SignalWire's own validator
(signalwire-python, signalwire/core/security/webhook_validator.py, MIT),
including trying the URL with and without its standard port.

Use ``@signalwire_signed`` on a controller method, under ``@http.route``.
What happens to a request that fails is up to the SignalWire Project's
"Webhook Signatures" setting: off, log only (the default, so turning this on
can't cut off calls), or reject.
"""
import base64
import functools
import hashlib
import hmac
from urllib.parse import urlsplit, urlunsplit

from odoo.http import request

HEADER = 'X-SignalWire-Signature'
STANDARD_PORTS = {'http': 80, 'https': 443}


def compute_signature(signing_key, url, params):
    """base64 HMAC-SHA1 of the URL followed by each (name, value) pair,
    sorted by name; repeated names keep their submitted order."""
    pairs = sorted(params, key=lambda kv: kv[0])
    message = url + ''.join(f'{name}{value}' for name, value in pairs)
    digest = hmac.new(signing_key.encode(), message.encode(), hashlib.sha1).digest()
    return base64.b64encode(digest).decode('ascii')


def candidate_urls(url):
    """The URL as given, plus the same URL with its standard port added or
    removed: SignalWire may sign either form."""
    parts = urlsplit(url)
    standard = STANDARD_PORTS.get(parts.scheme)
    if not parts.hostname or not standard:
        return [url]
    host = parts.hostname
    if parts.port is None:
        other = parts._replace(netloc=f'{host}:{standard}')
    elif parts.port == standard:
        other = parts._replace(netloc=host)
    else:
        return [url]
    return [url, urlunsplit(other)]


def is_valid(signing_keys, signature, urls, params):
    if not signature:
        return False
    for key in signing_keys:
        for base in urls:
            for url in candidate_urls(base):
                if hmac.compare_digest(compute_signature(key, url, params), signature):
                    return True
    return False


def signalwire_signed(handler):
    """Checks the SignalWire signature before running a webhook handler;
    answers 403 when the Project is set to reject and the check fails."""
    @functools.wraps(handler)
    def wrapper(self, *args, **kwargs):
        if not request.env['signalwire.server'].sudo()._check_webhook_signature(request.httprequest):
            return request.make_response('Invalid signature', status=403)
        return handler(self, *args, **kwargs)
    return wrapper
