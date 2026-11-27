# Support Requests

A way for everyone in a company to report a problem with Odoo without leaving
it, and for the company's own support people to solve it or pass it on to
their Odoo provider.

1. **Anyone reports it.** **Report a problem** in the user menu (top right)
   asks what's wrong, what they were trying to do and how urgent it is. The
   screen and page they were on are filled in for them.
2. **Support coordinators get it.** Each coordinator gets a to-do (it shows on
   My Day too) and follows the request. **Take it** says someone's on it and
   clears the others' to-dos.
3. **Solved here**, or **Send to support**: the coordinator emails the request,
   with its details and the page it came from, to the provider's support. A
   note can explain what they already tried; the provider's own note (for
   example how help outside a support plan is billed) is shown first.
4. **Replies come back into the request.** The email goes out from this
   database's catchall address, so the provider's replies are filed on the
   request by Odoo's mail gateway, and everyone following it is notified. The
   provider stays a follower, so later messages on the request reach them too.

People see only the requests they reported or follow; coordinators see them all.

## Set it up

- **Settings › Support Requests**: the provider's name, support email, and an
  optional note shown before escalating. With no support email, requests stay
  in-house and **Send to support** doesn't appear.
- **Settings › Users**: give **Support Coordinator** (Support Requests) to
  whoever should triage requests. Administrators have it already.
- Escalation replies need incoming mail (a catchall address with an alias
  domain). Without one, the email goes out from the coordinator's own address
  and replies reach their mailbox instead.

### For hosting providers

Set the defaults once per server in `odoo.conf`, for every database on it
(a database's own Settings still win):

```
support_provider_name = Your Company
support_provider_email = support@example.com
support_provider_note = Help outside your support plan is billed by the hour.
```

Odoo logs "unknown option ... stored as-is" for these at startup; that's
expected. Each escalation ends with a line
`[support-system <url> <database>]`, so the provider's helpdesk can tell which
customer system it came from.

## Tests

8 tests: reporting reaches the coordinators, privacy, only coordinators move a
request along, taking it clears the others' to-dos, no escalation without a
provider, the odoo.conf default, the escalation email (sender, details,
system line, provider following), and a provider reply landing back on the
request through the mail gateway.
