# -*- coding: utf-8 -*-
import functools
import json

from odoo.tests import BaseCase, HttpCase, tagged

from ..models.ir_http import required_params


class TestRequiredParams(BaseCase):

    def test_reads_only_values_without_a_default(self):
        def endpoint(self, app_id, path='', *, token, mode=None, **kw):
            pass
        self.assertEqual(required_params(endpoint), {'app_id', 'token'})

    def test_controller_instance_is_never_required(self):
        def endpoint(self):
            pass
        self.assertEqual(required_params(endpoint), frozenset())

    def test_catch_all_signatures_require_nothing(self):
        def endpoint(self, *args, **kwargs):
            pass
        self.assertEqual(required_params(endpoint), frozenset())

    def test_values_a_decorator_supplies_are_not_required(self):
        def inject_order(func):
            @functools.wraps(func)
            def wrapper(self, *args, **kwargs):
                return func(self, *args, order=object(), **kwargs)
            return wrapper

        @inject_order
        def endpoint(self, order):
            pass
        self.assertEqual(required_params(endpoint), frozenset())


@tagged('post_install', '-at_install')
class TestRouteArgsGuard(HttpCase):

    def test_missing_value_is_a_quiet_404(self):
        # Core's own pages that crash with a TypeError without app_id.
        for path in ('/scoped_app', '/scoped_app_icon_png',
                     '/web/manifest.scoped_app_manifest?app_id=web'):
            with self.subTest(path=path), self.assertNoLogs('odoo.http', 'ERROR'):
                response = self.url_open(path, allow_redirects=False)
                self.assertEqual(response.status_code, 404, path)

    def test_page_with_its_values_still_works(self):
        response = self.url_open('/scoped_app?app_id=web&path=odoo', allow_redirects=False)
        self.assertEqual(response.status_code, 200)

    def test_jsonrpc_missing_value_is_a_404_error(self):
        self.authenticate('admin', 'admin')
        payload = {'jsonrpc': '2.0', 'method': 'call', 'id': 1, 'params': {}}
        with self.assertNoLogs('odoo.http', 'ERROR'):
            response = self.url_open(
                '/web/action/load', data=json.dumps(payload),
                headers={'Content-Type': 'application/json'},
            )
        self.assertEqual(response.json()['error']['code'], 404)

    def test_jsonrpc_with_its_values_still_works(self):
        self.authenticate('admin', 'admin')
        action = self.env.ref('base.action_res_users')
        payload = {'jsonrpc': '2.0', 'method': 'call', 'id': 1,
                   'params': {'action_id': action.id}}
        response = self.url_open(
            '/web/action/load', data=json.dumps(payload),
            headers={'Content-Type': 'application/json'},
        )
        self.assertEqual(response.json()['result']['id'], action.id)
