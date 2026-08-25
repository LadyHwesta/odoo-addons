# IMAP Authentication

Lets existing Odoo users log in with their mailbox password, by
authenticating against an IMAP server (`LOGIN`) instead of a separate Odoo
password. No extra Python packages: uses `imaplib` from the standard
library.

## How it works

Mirrors the structure of core's own `auth_ldap` module:

- A user's local Odoo password is checked **first**. Only if that fails
  does Odoo attempt an IMAP `LOGIN` with the submitted credentials against
  each configured server (in `sequence` order). This means an admin
  account, or anyone who still has a local password set, is never at risk
  of being locked out just because the mail server is unreachable.
- **Does not auto-provision new users** (unlike `auth_ldap`'s optional
  `create_user` behavior): IMAP only ever authenticates a login that
  already has an Odoo `res.users` record. A valid mailbox password alone
  can't create an Odoo account.

## Setup

1. Settings → Users & Companies → **IMAP Authentication** (admin only):
   add a server (host, port, SSL/TLS or STARTTLS or none), **Test
   Connection** to confirm it's reachable.
2. For each existing user who should authenticate via IMAP: open their
   user record → **Convert to IMAP Authentication** (in the Security tab),
   or select several users in the Users list and use the same action from
   the Action menu. This clears their local Odoo password - from then on,
   every login for them falls through to the IMAP check.

There's no reverse "convert back" button: just set a new local Odoo
password for the user (Security tab → Change Password, as an admin) and
the local check will succeed again first, same as any other user.

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
  fallback login. If you have several servers configured and the first one
  is down, expect each of its failed logins to pay that server's connection
  timeout (15s) before trying the next.
