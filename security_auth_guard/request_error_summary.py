# -*- coding: utf-8 -*-
"""One line that says what went wrong, on Odoo's request error log entry.

Core logs every failed request as "Exception during request handling."
followed by the traceback. Monitoring that reads the log line by line
(Zabbix here) only sees that first line, which says nothing. This adds a
summary to the same line, so an alert already names the error, where it
happened, the address asked for, and whether a signed-in user or an
anonymous visitor (usually a bot) sent it:

    Exception during request handling. TypeError: ...missing 'state' |
    at odoo/service/model.py:97 call_kw | POST /web/dataset/call_kw/... |
    user tiesa | 203.0.113.5

The traceback is still logged in full underneath. Nothing from the query
string or body is included, since those can hold tokens or passwords.

A logging filter is process-wide: once this module is loaded, every
database served by the same Odoo process gets the summary.
"""
import logging
import os
import sys
import traceback

import odoo
from odoo.http import request

CORE_MESSAGE = "Exception during request handling."
MAX_MESSAGE = 300
MAX_PATH = 200

ODOO_ROOT = os.path.dirname(os.path.realpath(list(odoo.__path__)[0])) + os.sep
LIBRARY_ROOTS = tuple({
    os.path.realpath(p) + os.sep
    for p in (sys.prefix, sys.base_prefix, os.path.dirname(os.__file__))
})
# Overrides every request passes through on its way to the real code;
# naming one of them as "our code" would point at the wrong module.
PASS_THROUGH = {
    "_dispatch", "_serve_fallback", "_pre_dispatch", "_post_dispatch",
    "_authenticate", "_auth_method_user", "_auth_method_public",
    "_handle_error", "route_wrapper",
}


def _short(filename):
    real = os.path.realpath(filename)
    if real.startswith(ODOO_ROOT):
        return real[len(ODOO_ROOT):]
    marker = os.sep + "addons" + os.sep
    if marker in real:
        return real.split(marker)[-1]
    return os.path.basename(real)


def _is_addon_frame(filename):
    real = os.path.realpath(filename)
    return not real.startswith(ODOO_ROOT) and not real.startswith(LIBRARY_ROOTS) \
        and "site-packages" not in real and "dist-packages" not in real


def summarize(exc, tb, method=None, path=None, login=None, ip=None):
    """The summary text for one failed request."""
    message = " ".join(str(exc).split())
    if len(message) > MAX_MESSAGE:
        message = message[:MAX_MESSAGE] + "..."
    parts = [f"{type(exc).__name__}: {message}" if message else type(exc).__name__]
    frames = traceback.extract_tb(tb) if tb else []
    if frames:
        last = frames[-1]
        parts.append(f"at {_short(last.filename)}:{last.lineno} {last.name}")
        ours = [f for f in frames
                if _is_addon_frame(f.filename) and f.name not in PASS_THROUGH]
        if ours and ours[-1] is not last:
            parts.append(f"via {_short(ours[-1].filename)}:{ours[-1].lineno} {ours[-1].name}")
    if path:
        parts.append(f"{method or ''} {path[:MAX_PATH]}".strip())
    parts.append(f"user {login}" if login else "anonymous")
    if ip:
        parts.append(ip)
    return " | ".join(parts)


class RequestErrorSummary(logging.Filter):
    """Adds the summary to core's request error line; never blocks a record."""

    def filter(self, record):
        try:
            if record.msg == CORE_MESSAGE and record.exc_info and not record.args:
                _type, exc, tb = record.exc_info
                method = path = login = ip = None
                if request:
                    httprequest = request.httprequest
                    method, path = httprequest.method, httprequest.path
                    ip = httprequest.environ.get("REMOTE_ADDR")
                    session = getattr(request, "session", None)
                    if session is not None and session.uid:
                        login = session.login or f"uid {session.uid}"
                record.msg = f"{CORE_MESSAGE} {summarize(exc, tb, method, path, login, ip)}"
        except Exception:  # noqa: BLE001 - logging must never fail
            pass
        return True


def install():
    http_logger = logging.getLogger("odoo.http")
    if not any(isinstance(f, RequestErrorSummary) for f in http_logger.filters):
        http_logger.addFilter(RequestErrorSummary())


install()
