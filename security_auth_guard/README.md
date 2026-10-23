# Security Auth Guard

Application-layer intrusion detection/prevention for Odoo itself - the
one layer only Odoo can meaningfully protect, since it has business
context a network firewall never will. Deliberately does **not** try to
be a network IDS - Odoo never sees raw traffic, only HTTP requests that
already reached it; real network-level prevention belongs to purpose-
built tools (see this author's `managed_odoo_instances`/
`meskis-deploy-agent` for the host-level half of that story).

## Builds on Odoo core, doesn't duplicate it

Odoo 19 already rate-limits logins per IP
(`res.users._assert_can_auth`/`_on_login_cooldown`, configurable via the
`base.login_cooldown_after`/`base.login_cooldown_duration` system
parameters) - just in memory, lost on every restart, and silent (a log
line, nothing queryable). This module extends that instead of
reinventing it:

- **`security.login_attempt`** - every login, success or failure,
  persisted with IP and login (core's own counter never survives a
  restart).
- Overriding `_on_login_cooldown` (the method core's own docstring names
  as the intended extension point) to fire a `security.event` every time
  the cooldown actually triggers, and escalate to a **permanent**
  `security.ip_rule` block once the same IP triggers it more than a
  configurable number of times in a day - core's own cooldown is always
  temporary; this is the one real gap worth closing.

## IP allow/block list

`security.ip_rule` (a single IP or a CIDR range, allow or block, an
optional expiry) is enforced in `ir.http._dispatch` - the earliest point
in Odoo's own request handling, before any controller including login
even runs. An `allow` rule always wins over a matching `block`, so it can
deliberately carve out an exception inside an otherwise-blocked range.

## Security Events

One unified log (`security.event`) everything in this module - and
anything that extends it, e.g. a financial-record anomaly monitor - posts
to. A Security app menu (gated to the new `group_security_officer` group,
granted to admins by default) shows a dashboard, filterable by severity/
type, with a one-click "Block This IP" escalation from any event.

## Optional SMS alerting

If `signalwire_sms`/`signalwire_voip` happens to also be installed, a
`critical`-severity event can send an SMS to a number configured in
Settings. Checked at runtime (`self.env.get('signalwire.phone_number')`)
- never a hard dependency, so this module installs standalone on any
Odoo instance.

## Testing

Local `testing/` harness, same as every other module in this repo.
`HttpCase` tests exercise the real `ir.http._dispatch` block end to end
(the test client always connects as `127.0.0.1`, so blocking that address
directly - with an `addCleanup` removing the block immediately,
registered *before* the assertion - gives a genuine HTTP round-trip
without needing to fake `X-Forwarded-For`/`proxy_mode`). Cooldown
escalation is tested by calling `_security_maybe_escalate` directly
rather than real repeated brute-force logins - faster, and avoids the
same self-lockout risk the IP-block test is careful about.
