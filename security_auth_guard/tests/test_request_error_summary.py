# -*- coding: utf-8 -*-
import json
import sys

from odoo.tests import BaseCase, HttpCase, tagged

from ..request_error_summary import summarize


class TestSummarize(BaseCase):

    def test_names_the_error_place_request_and_visitor(self):
        try:
            {}["missing"]
        except KeyError:
            _type, exc, tb = sys.exc_info()
        line = summarize(exc, tb, "POST", "/web/dataset/call_kw/x/y",
                         "tiesa", "203.0.113.5")
        self.assertIn("KeyError: 'missing'", line)
        self.assertIn("test_request_error_summary.py", line)
        self.assertIn("POST /web/dataset/call_kw/x/y", line)
        self.assertIn("user tiesa", line)
        self.assertIn("203.0.113.5", line)

    def test_anonymous_and_long_messages(self):
        line = summarize(ValueError("x" * 1000), None, "GET", "/a", None, None)
        self.assertIn("anonymous", line)
        self.assertLess(len(line), 400)


@tagged("post_install", "-at_install")
class TestSummaryInTheLog(HttpCase):

    def test_request_error_line_carries_the_summary(self):
        self.authenticate("admin", "admin")
        payload = {"jsonrpc": "2.0", "method": "call", "id": 1,
                   "params": {"model": "res.partner", "method": "read",
                              "args": [], "kwargs": {}}}
        with self.assertLogs("odoo.http", "ERROR") as logs:
            self.url_open("/web/dataset/call_kw/res.partner/read",
                          data=json.dumps(payload),
                          headers={"Content-Type": "application/json"})
        line = logs.records[-1].getMessage()
        self.assertTrue(line.startswith("Exception during request handling. IndexError"), line)
        self.assertIn("POST /web/dataset/call_kw/res.partner/read", line)
        self.assertIn("user admin", line)
        self.assertIn("127.0.0.1", line)
