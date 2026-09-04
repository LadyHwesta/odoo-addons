# IMAP Authentication

Lets existing Odoo users log in with their mailbox password, by
authenticating against an IMAP server (`LOGIN`) instead of a separate Odoo
password. No extra Python packages: uses `imaplib` from the standard
library.

## How it works

Mirrors the structure of core's own `auth_ldap` module:

- A user's local Odoo password is checked **first**. Only if that fails,
  **and only for a user who was actually converted to IMAP authentication**
  (see Setup below - their local password is empty), does Odoo attempt an
  IMAP `LOGIN` with the submitted credentials against each server
  configured **for that user's own company** (in `sequence` order) - a
  Company A user's mistyped password is never even attempted against
  Company B's mail server, in a multi-company database. This means an
  admin account, or anyone who
  still has a local password set, is never at risk of being locked out
  just because the mail server is unreachable - and, just as importantly,
  never triggers a real login attempt against the IMAP server just because
  they mistyped their Odoo password. Mail providers commonly rate-limit or
  block a source IP after enough failed logins, so this gate isn't just an
  optimization: without it, *every* user's password typo - converted or
  not - would count against that limit.
- **Does not auto-provision new users** (unlike `auth_ldap`'s optional
  `create_user` behavior): IMAP only ever authenticates a login that
  already has an Odoo `res.users` record. A valid mailbox password alone
  can't create an Odoo account.

## Setup

1. Settings → Users & Companies → **IMAP Authentication** (admin only):
   add a server (host, port, SSL/TLS or STARTTLS or none) **for the
   relevant company**, **Test Connection** to confirm it's reachable. In a
   multi-company database, each server belongs to exactly one company -
   only that company's users are ever checked against it, so a user whose
   company has no server configured can never authenticate via IMAP even
   if another company does.
2. For each existing user who should authenticate via IMAP: open their
   user record → **Convert to IMAP Authentication** (in the Security tab),
   or select several users in the Users list and use the same action from
   the Action menu. This clears their local Odoo password - from then on,
   every login for them falls through to the IMAP check. Refuses up front
   (naming the affected company/companies) if any selected user's own
   company has no IMAP server configured yet - converting them anyway
   would just lock them out with nothing left to fall back on.

There's no reverse "convert back" button: just set a new local Odoo
password for the user (Security tab → Change Password, as an admin) and
the local check will succeed again first, same as any other user.

## Testing status

Verified end-to-end against a real IMAP server (Dovecot-family, port 993
implicit SSL): Test Connection, converting a real user, a full login with
the correct mailbox password through the actual `_check_credentials`
fallback chain (not stubbed), and rejection of a wrong password. Also
confirmed against the same server that port 993 expects immediate TLS
(`ssl` encryption) rather than a plaintext-then-`STARTTLS` upgrade -
`STARTTLS` on that server works on port 143 instead. If your server's
combination doesn't connect, that's the first thing to check.

**Multi-company scoping (19.0.1.1.0)**, covered by
`tests/test_imap_company_scoping.py` (`_authenticate` mocked - these are
about which server(s) a login is scoped to, not a live connection):
a Company A user's fallback login only ever queries Company A's own IMAP
server(s), never Company B's even though both exist in the same database;
and converting a user whose own company has no server configured is
refused up front rather than silently succeeding and locking them out.
Not yet re-verified end-to-end against two real IMAP servers in one
multi-company database.

## Known limitations

- The Odoo login and the IMAP username must be the same string (typically
  both are the user's email address). There's no LDAP-style filter/template
  to derive one from the other.
- No password-change bridge: unlike `auth_ldap`'s `change_password`
  override (which can push a new password to the LDAP server), Odoo's
  "Change Password" for an IMAP-converted user just sets a new *local*
  Odoo password - it does not change the actual mailbox password. That's
  probably what you want (don't let Odoo write to the mail server), but it
  does mean the two passwords can diverge from that point on.
- One connection attempt per configured server, in sequence, on every
  fallback login *for an IMAP-converted user*. If you have several servers
  configured and the first one is down, expect each of that user's failed
  logins to pay that server's connection timeout (15s) before trying the
  next.
