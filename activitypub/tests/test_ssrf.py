# -*- coding: utf-8 -*-
"""Tests for the SSRF guard on outbound dereferences."""
import socket
import unittest
from unittest import mock

from odoo.addons.activitypub.models import activitypub_service as svc


def _fake_getaddrinfo(ip):
    def _inner(host, port, *a, **kw):
        return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, '', (ip, port))]
    return _inner


class TestAssertPublicUrl(unittest.TestCase):

    def test_rejects_non_http_scheme(self):
        with self.assertRaises(svc.RemoteFetchError):
            svc.assert_public_url('ftp://example.com/x')

    def test_rejects_url_without_host(self):
        with self.assertRaises(svc.RemoteFetchError):
            svc.assert_public_url('https:///nohost')

    def test_rejects_loopback(self):
        with mock.patch.object(svc.socket, 'getaddrinfo', _fake_getaddrinfo('127.0.0.1')):
            with self.assertRaises(svc.RemoteFetchError):
                svc.assert_public_url('https://sneaky.example/x')

    def test_rejects_private_ranges(self):
        for ip in ('10.1.2.3', '192.168.0.9', '172.16.5.5', '169.254.1.1'):
            with mock.patch.object(svc.socket, 'getaddrinfo', _fake_getaddrinfo(ip)):
                with self.assertRaises(svc.RemoteFetchError, msg=ip):
                    svc.assert_public_url('https://sneaky.example/x')

    def test_rejects_ipv6_loopback(self):
        with mock.patch.object(svc.socket, 'getaddrinfo', _fake_getaddrinfo('::1')):
            with self.assertRaises(svc.RemoteFetchError):
                svc.assert_public_url('https://sneaky.example/x')

    def test_allows_public_address(self):
        with mock.patch.object(svc.socket, 'getaddrinfo', _fake_getaddrinfo('93.184.216.34')):
            svc.assert_public_url('https://example.com/users/foo')  # no raise

    def test_unresolvable_host_rejected(self):
        def _boom(*a, **kw):
            raise socket.gaierror('nope')
        with mock.patch.object(svc.socket, 'getaddrinfo', _boom):
            with self.assertRaises(svc.RemoteFetchError):
                svc.assert_public_url('https://does-not-resolve.invalid/x')

    def test_allowlisted_host_skips_the_check(self):
        # Resolves to loopback, which would normally be refused...
        with mock.patch.object(svc.socket, 'getaddrinfo', _fake_getaddrinfo('127.0.0.1')):
            with self.assertRaises(svc.RemoteFetchError):
                svc.assert_public_url('https://mastodon.internal.lan/inbox')
            # ...but an explicit allowlist entry lets it through.
            svc.assert_public_url('https://mastodon.internal.lan/inbox',
                                  allow_hosts=('mastodon.internal.lan',))


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
