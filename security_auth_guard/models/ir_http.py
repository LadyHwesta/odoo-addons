# -*- coding: utf-8 -*-
import logging
from datetime import timedelta

import werkzeug.exceptions

from odoo import fields, models
from odoo.http import request

from .security_ip_rule import own_transaction
from .security_probe_hit import probe_reason

_logger = logging.getLogger(__name__)

# A blocked IP that keeps hammering the site would otherwise flood
# security.event with one row per request - one event per IP per window
# is plenty to know it's still happening.
EVENT_DEDUP_MINUTES = 5


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    @classmethod
    def _dispatch(cls, endpoint):
        """The earliest point in Odoo's own request handling that runs
        for every single controller, including login - the standard
        extension point for an IP block list, same reasoning core's own
        dbfilter/maintenance-mode checks use this same method for.
        """
        cls._security_refuse_if_blocked()
        return super()._dispatch(endpoint)

    @classmethod
    def _serve_fallback(cls):
        """Every address no controller matched: website pages, redirects,
        attachments, and everything bots probe for. Blocked addresses are
        refused here too, and once nothing was found, a request for an
        address only attackers ask for (/.env, /wp-login.php, ../) counts
        towards a temporary block.
        """
        cls._security_refuse_if_blocked()
        response = super()._serve_fallback()
        if not response and request:
            cls._security_count_probe()
        return response

    @classmethod
    def _security_refuse_if_blocked(cls):
        if not request:
            return
        ip = request.httprequest.environ.get("REMOTE_ADDR")
        if ip and request.env["security.ip_rule"].sudo()._is_blocked(ip):
            _logger.warning("Blocked request from %s (security.ip_rule).", ip)
            try:
                cls._security_log_block_once(ip)
            except Exception:
                # The event is best-effort; the refusal is what matters.
                _logger.warning("Could not record the block of %s", ip, exc_info=True)
            raise werkzeug.exceptions.Forbidden()

    @classmethod
    def _security_count_probe(cls):
        httprequest = request.httprequest
        reason = probe_reason(
            httprequest.path, httprequest.query_string.decode("latin-1"))
        ip = httprequest.environ.get("REMOTE_ADDR")
        if not reason or not ip:
            return
        # Website reroutes a "not found" address through the fallback a
        # second time (to try it with a language prefix); count it once.
        if httprequest.environ.get("security_auth_guard.probe_counted"):
            return
        httprequest.environ["security_auth_guard.probe_counted"] = True
        _logger.info("Probe from %s: %s (%s)", ip, httprequest.path, reason)
        # Its own transaction: the 404 that follows rolls back the
        # request's, which may also be read-only.
        try:
            with own_transaction(request.env) as env:
                env["security.probe_hit"]._record(ip, httprequest.path, reason)
        except Exception:
            # Counting is best-effort: the visitor still gets the 404.
            _logger.warning("Could not record the probe from %s", ip, exc_info=True)

    @classmethod
    def _security_log_block_once(cls, ip):
        # Its own transaction: the Forbidden raised right after this rolls
        # back the request's transaction, which may also be read-only.
        with own_transaction(request.env) as env:
            Event = env["security.event"]
            since = fields.Datetime.now() - timedelta(minutes=EVENT_DEDUP_MINUTES)
            if Event._count_from_source("ip_blocked", ip, since):
                return
            Event.create({
                "event_type": "ip_blocked",
                "severity": "warning",
                "source_ip": ip,
                "detail": f"Request(s) from {ip} refused by an active "
                          f"security.ip_rule.",
            })
