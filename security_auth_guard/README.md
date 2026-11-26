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

### IPv6

An IPv6 connection normally controls a whole `/64` and can change address
within it at will. So core's login cooldown, the escalation count, and
automatic or one-click blocks all treat a `/64` as one source. Login
attempts and events still record the exact address. The trade-off is the
same as a shared IPv4 address: everyone on that `/64`, usually one
household or site, shares the cooldown and any block. An `allow` rule for
one address still wins.

### Protected ranges

Automatic and one-click blocks refuse loopback, private and Cloudflare
addresses, because blocking one could cut off everyone behind it. If one
reaches the escalation threshold, a critical `anomaly` event is posted
instead, since it usually means the proxy has stopped passing on real
visitor addresses. A daily scheduled action adds Cloudflare's current ranges
from `api.cloudflare.com`, sending nothing but the request itself, and keeps
the last good list if the fetch fails or looks wrong. Add other proxies as a
comma-separated list in the `security_auth_guard.protected_ranges` system
parameter. Rules created by hand aren't checked.

All of this depends on Odoo seeing real addresses. Behind Cloudflare, that
means configuring nginx's `set_real_ip_from` for Cloudflare's ranges and
`real_ip_header CF-Connecting-IP`.

## Security Events

One unified log (`security.event`) everything in this module - and
anything that extends it, e.g. a financial-record anomaly monitor - posts
to. A Security app menu (gated to the new `group_security_officer` group,
granted to admins by default) shows a dashboard, filterable by severity/
type, with a one-click "Block This IP" escalation from any event.

**What needs attention, and what doesn't.** Every event has a severity:

| Severity | Means | Examples |
|---|---|---|
| Info | Handled automatically: a block that worked | a scanner blocked (`probe_blocked`), a login attacker blocked (`ip_blocked`), a blocked address coming back and refused again (`request_refused`, once per 5 minutes per address), a login cooldown for a made-up login name |
| Warning | A person should look | a login cooldown while someone keeps guessing at one of your real logins |
| Critical | Act on it | `anomaly`: a bank account changed outside business hours (financial monitor), a proxy hiding real visitor addresses |

**Security › Security Events** opens on **Needs Attention** (new warnings and
criticals). **Security › Blocks Over Time** charts the automatic blocks per
day, with a pivot for totals. Info events are deleted after 90 days
(Settings › Security Events; at least 31, -1 keeps them); events that need
attention are never deleted. Before 19.0.1.4.0 every block was a Warning and
a returning address looked like a new block: on a public site that buried
the few events that matter under hundreds of routine ones, and upgrading
converts the old events.

## Probe blocking

Scanners ask every site for the same handful of addresses: secrets and
version control left in a web root (`/.env`, `/.git/config`), other
platforms' admin pages and scripts (`/wp-login.php`, `/xmlrpc.php`,
`/phpmyadmin`, anything ending `.php`), and `../` tricks to reach outside
it. Odoo never serves any of these, and search engines never ask for them.

`ir.http._serve_fallback` (every address no controller matched) counts a
request as a probe only **after** Odoo has found nothing for it, so a real
page, redirect or file can never match. `/wp-content/` and
`/wp-includes/` are left out on purpose: a site moved from WordPress still
has old links to images there.

- 3 probes from one address (its /64 for IPv6) within 10 minutes: blocked
  for 24 hours, with one `probe_blocked` event.
- The 3rd probe block within 30 days is permanent.
- All three numbers are in Settings > Security > Probe Blocking; -1 turns
  blocking (or the permanent step) off.
- Probes are kept a day under Security > Probe Requests, then cleaned up.
- Protected addresses (Cloudflare, private, loopback) are never blocked: a
  critical `anomaly` event says the proxy may have stopped passing on
  real addresses, as for login escalation.
- Blocked addresses are now refused on unmatched addresses (website pages,
  404s) as well as on controllers.

## Request error summary

Core logs a failed request as "Exception during request handling." with
the traceback underneath. Monitoring that reads the log line by line only
sees that first line. `request_error_summary.py` adds a filter to the
`odoo.http` logger that appends one summary to that same line:

```text
Exception during request handling. TypeError: ...missing 1 required positional argument: 'state' | at odoo/service/model.py:97 call_kw | POST /web/dataset/call_kw/res.users/set_signalwire_call_state | user tiesa | 203.0.113.5
```

The error, where it was raised (plus the deepest frame in an add-on, when
that's somewhere else), the method and path, the signed-in login or
"anonymous", and the address. Nothing from the query string or body, which
can hold tokens. The traceback is still logged in full. The filter is
process-wide, so every database on the same Odoo process gets it.

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
escalation is tested by calling `_security_maybe_escalate` directly for
the threshold rules - faster, and avoids the same self-lockout risk the
IP-block test is careful about. Real repeated failed logins over HTTP are
covered from `127.0.0.1`, a protected address, so nothing gets blocked.

A failed login on a JSON route such as `/web/session/authenticate` rolls
back the request's transaction, so security records are written in their
own. Test mode nests that transaction inside the rolled-back one, which
means surviving records can only be checked against a real running server.
