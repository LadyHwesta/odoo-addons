# -*- coding: utf-8 -*-
{
    "name": "Security Auth Guard",
    "version": "19.0.1.0.0",
    "category": "Tools",
    "summary": "Persisted brute-force login reporting, permanent IP "
               "blocking, and a unified security event log",
    "description": """
Security Auth Guard
=====================

Odoo core already rate-limits logins per IP (``res.users.
_assert_can_auth``/``_on_login_cooldown``, configurable via the
``base.login_cooldown_after``/``base.login_cooldown_duration`` system
parameters) - but only in memory (lost on every restart) and silently (a
log line, nothing queryable). This module doesn't duplicate that logic -
it extends it:

* **``security.login_attempt``** - every login, success or failure, with
  IP and login, persisted and reportable (core's own counter never
  survives a restart).
* **``security.event``** - fires whenever core's cooldown actually
  triggers, and escalates to a permanent block once the same IP triggers
  it more than a configurable number of times in a day - the one real
  gap core's cooldown leaves, since it's always temporary.
* **``security.ip_rule``** - a manual or auto-escalated allow/block list,
  enforced in ``ir.http._dispatch`` - the earliest point in Odoo's own
  request handling, before any controller (including login) runs.
* A Security app with a dashboard of recent events by severity/type, and
  Settings exposing the two existing cooldown parameters plus the new
  escalation threshold.

Generic and dependency-light on purpose - installable standalone on any
Odoo instance, not just ones running the rest of this author's other
modules. If ``signalwire_sms``/``signalwire_voip`` happens to also be
installed, a critical-severity event can optionally send an SMS alert -
checked at runtime, never a hard dependency.
""",
    "author": "Tiesa",
    "license": "LGPL-3",
    "website": "https://github.com/LadyHwesta/odoo-addons",
    "depends": ["base", "mail", "web"],
    "data": [
        "security/security_auth_guard_security.xml",
        "security/ir.model.access.csv",
        "views/security_event_views.xml",
        "views/security_ip_rule_views.xml",
        "views/security_login_attempt_views.xml",
        "views/res_config_settings_views.xml",
        "views/security_menus.xml",
    ],
    "installable": True,
    "application": True,
}
