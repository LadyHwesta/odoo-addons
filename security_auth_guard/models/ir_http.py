# -*- coding: utf-8 -*-
import logging
from datetime import timedelta

import werkzeug.exceptions

from odoo import fields, models
from odoo.http import request

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
        if request:
            ip = request.httprequest.environ.get("REMOTE_ADDR")
            if ip and request.env["security.ip_rule"].sudo()._is_blocked(ip):
                _logger.warning("Blocked request from %s (security.ip_rule).", ip)
                cls._security_log_block_once(ip)
                raise werkzeug.exceptions.Forbidden()
        return super()._dispatch(endpoint)

    @classmethod
    def _security_log_block_once(cls, ip):
        Event = request.env["security.event"].sudo()
        since = fields.Datetime.now() - timedelta(minutes=EVENT_DEDUP_MINUTES)
        recent = Event.search_count([
            ("event_type", "=", "ip_blocked"), ("source_ip", "=", ip),
            ("create_date", ">=", since)])
        if recent:
            return
        Event.create({
            "event_type": "ip_blocked",
            "severity": "warning",
            "source_ip": ip,
            "detail": f"Request(s) from {ip} refused by an active "
                      f"security.ip_rule.",
        })
