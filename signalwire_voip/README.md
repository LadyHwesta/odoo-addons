# SignalWire VoIP

Core connector for [SignalWire](https://signalwire.com/), a Twilio-API-
compatible communications platform - Phase 1 of a larger VoIP-reselling
project (see the memory doc `signalwire-voip-scoping.md` for the full
plan: click-to-call via `voip_oca`, two-way SMS, and a metered-billing
public storefront are separate modules layered on top of this one).

## What this module provides

- **`signalwire.server`**: one project's connection settings (Space
  domain, Project ID, API Token) and a connection test.
- **`signalwire.subproject`**: a provisioned container for one resold
  customer (SignalWire's own term is "subproject" - Twilio calls the
  same concept a "subaccount"). **Subprojects share the parent
  project's balance** - what they isolate is *resources* (a customer's
  own numbers, calls, recordings), not billing. Any customer-facing
  billing gets tracked and invoiced by Odoo itself in a later phase.
- **`signalwire.phone_number`**: numbers purchased into a subproject,
  with a staff-driven search+purchase wizard (Sales/VoIP menu -> a
  subproject -> "Search Phone Numbers").

## Architecture note: one set of credentials manages every subproject

**Confirmed live 2026-09-15**: a subproject's own `auth_token` comes
back *masked* from SignalWire's API on creation - there's no way to
retrieve it to authenticate as that subproject specifically. This
doesn't actually matter: **the parent project's own credentials can
manage a subproject's resources directly**, just by putting that
subproject's Account SID in the URL path (e.g.
`GET /Accounts/{subproject_sid}/AvailablePhoneNumbers/...` using the
parent's own Basic Auth). So `signalwire.server` only ever needs ONE
set of credentials, full stop - `signalwire.subproject` doesn't store
or need a token of its own.

## Live-verified against the user's real trial account, 2026-09-15

**This is a real trial account, not a fake-money sandbox like
Namecheap's** - purchasing a number or sending a real call/SMS draws
real trial credit and creates a real telecom resource. Everything
below is free/reversible and was run without asking first, same as
Namecheap's sandbox; buying an actual number was *not* attempted here
and should be confirmed with the user first when that's actually
needed (Phase 2 onward).

- **Auth/base URL**: `https://{space}/api/laml/2010-04-01/...`
  (Compatibility API) with HTTP Basic Auth, `ProjectID:APIToken`.
- **`action_test_connection`**: works through the real model, reports
  the project's live status.
- **Subproject creation** (`POST /Accounts.json` with `FriendlyName`):
  works through the real model, returns a real Account SID.
- **Subproject closing** (`POST /Accounts/{sid}.json` with
  `Status=closed`): **known gap** - this did NOT actually change the
  subproject's status when tested (stayed `active`). Unclear whether
  it needs a different token scope or whether every resource under the
  subproject has to be released first. `action_close` still marks the
  record closed locally and posts a chatter note telling whoever
  clicked it to verify (and finish closing, if needed) in the
  SignalWire dashboard by hand - same class of gap as HestiaCP having
  no Access Key category for package management.
- **Number search**: since 2026-11-11 the wizard and the storefront use
  `signalwire.server.search_numbers` (Relay REST `GET phone_numbers/search`:
  local or toll-free, starts with / contains / ends with, area code, state,
  city), mocked in tests and **not yet run against the live API**. The older
  `search_available_numbers` (`GET /Accounts/{sid}/AvailablePhoneNumbers/US/Local.json`)
  stays for compatibility and was the one live-tested here: Note: searching with a specific
  `AreaCode` (415 was tried) came back empty, but searching the same
  subproject with no area code returned 100 real available numbers
  (in a different area code) - the trial account may restrict which
  area codes it'll actually return, or 415 specifically had none
  available at the time. Not fully understood yet; don't be surprised
  if a specific area code search comes back empty when a broader one
  wouldn't.
- **A real (empty) test subproject was left behind** in the user's
  SignalWire account, named "Claude Odoo Live Test" - it owns no
  numbers and costs nothing, but exists because closing it via the API
  didn't work (see the gap above). Safe to ignore or delete by hand
  via the dashboard.

**Not yet live-verified**: actually purchasing a number
(`POST .../IncomingPhoneNumbers.json`) and releasing one (`DELETE`) -
both cost real trial credit/create a real resource, so these are
deferred to whichever later phase first needs a real owned number
(click-to-call needs one to receive calls on) and will be confirmed
with the user first.

## A third API surface: Project Tokens (added for Phase 3's reseller access)

**Confirmed live 2026-09-15**: `POST /api/project/tokens` (a third base
path - `/api/`, not versioned like the Compatibility API) creates a
named, permission-scoped API token for a specific subproject
(`subproject_id` param), and - unlike a subproject's own `auth_token` -
**returns the real secret value**, once, in full. This is how a resold
customer gets independently-usable SignalWire credentials without ever
needing that unretrievable masked token: create one of these scoped to
their subproject instead. See `signalwire_sms`'s own README for how
this gets used.

One non-obvious thing confirmed by testing both ways: the resulting
token authenticates as **`{subproject_sid}:{token}`** - the
subproject's own Account SID as the Basic Auth username, NOT the
parent project's ID. Pairing the parent's ID with the new token
returns `200` with an empty body (silently useless) rather than an
error - easy to misdiagnose as "the token doesn't work" if only the
parent pairing is tried.

## Error handling: two different error shapes

The Compatibility API and the newer Relay REST API (used for SIP
Endpoints in the click-to-call phase) return **different error JSON
shapes** - confirmed live by deliberately triggering a validation
error on each:

- Compatibility API: `{"code": "...", "message": "..."}`
- Relay API: `{"errors": [{"detail": "...", ...}, ...]}`
- A bad-auth 401 comes back as **plain text** ("Unauthorized"), not
  JSON, on either surface.

`SignalWireClient._extract_error_message` normalizes all three into
one readable string rather than leaking a raw response body.

## Testing

All business logic (the API client's URL-building/auth/error handling,
`signalwire.server`, `signalwire.subproject`, `signalwire.phone_number`,
and the search+purchase wizard) is covered by tests mocking
`requests.request`/`_get_client()` - nothing in the automated suite
makes a real HTTP call. 25 tests, all green.

## E911 (2026-11-13, not yet live-verified)

Built from SignalWire's REST docs (read 2026-11-13); no real address or
assignment has been sent yet.

- **Emergency Addresses** (VoIP › Configuration): `POST /api/relay/rest/addresses`
  with `emergency_enabled: true` (US only). The carrier validates it; a 422
  can carry `candidates`, which are kept on the address and shown to the
  user. A registered address is read-only: make a new one and move the
  numbers. The dispatcher name is capped at 32 characters (the emergency
  network's limit); Odoo refuses longer ones rather than truncating.
- **Per number** (phone number form): `POST /api/relay/rest/phone_numbers/{sid}/e911_address`
  with `e911_address_id`; status `pending` → `active` (or `failed`), checked
  by Check Status and an hourly cron, since no webhook is sent. Remove =
  `DELETE` on the same path (`pending_removal`). `_on_e911_status_changed`
  is the hook other modules use.
- **Why it matters:** SignalWire charges **$100 per 911 call from a number
  with no registered address**. Test with **933**, which reads the address
  back and is free.
- Dashboard tile: numbers without active E911.

Unverified assumptions: that the number's `sid` (from the Compatibility
API) is the Relay REST phone-number id; and that a parent project's token
can register addresses for numbers in its subprojects (the docs say the
address must be "in the same project"). On a customer's own Odoo connected
with a token scoped to their subproject (as TFL is), both are the same
project, so that's the safe place to set E911.

## E911 status kept in step, customers kept apart (2026-11-16)

Found live: every number showed "Not registered". Odoo only re-checked
numbers it already thought were Pending, so E911 registered anywhere else
(the provider's control panel, a customer's own Odoo) never showed, and the
form's Check Status button was hidden for exactly those numbers.

- **Daily check** (`_cron_refresh_e911_all`): every one of our own numbers
  is asked for its real E911 status (one savepoint each; a failure is logged
  and the rest carry on). Check Status is always on the form; Import Numbers
  checks new numbers straight away. Hook `_after_e911_refresh_all`
  (signalwire_voip_click2call re-applies outside-call rules there).
- **Customer numbers** (`number_use = 'customer'`): their sub-account isn't
  readable with this account (the provider answers 404, confirmed live), and
  their own Odoo manages routing, E911 and caller ID name. So nothing is
  asked about them, the form says so, and E911 / caller ID actions refuse
  them (`_check_not_customer`). Release is allowed: customers release their
  own numbers through the portal, which runs here.
- **Customers section** in the VoIP app: Sub-accounts and Customer Numbers
  (plus 10DLC and call records from the reseller modules). Phone Numbers, the
  dashboard and Messages show only our own numbers.

## Caller ID name (CNAM) (2026-11-16, not yet live-verified)

The name people see when a number calls them, requested through the
provider's API (`POST /api/relay/rest/phone_numbers/{id}/cnam {"name"}`, the
same `{id}` as our other number calls; `GET` for the latest request). On the
number form: **Caller ID Name** and **Request Caller ID Name**; a list action
requests it for several numbers. Without a name, one is made from the
company name. Rules checked before sending (the provider's own): at most 15
characters after upper-casing and collapsing spaces, starting with a letter
or digit, only letters, digits, spaces and `& ' . , -`. Toll-free numbers are
refused up front (carriers don't show names for them); names don't show to
Canadian phones. The provider reviews each request (pending, in review,
approved, rejected with a reason, failed); an hourly job follows pending ones
up and posts the outcome on the sub-account. Approved names can take up to
48 hours to show. A "isn't available for this number" answer (422) means the
carrier doesn't offer it; the provider's support can sometimes arrange it with
proof of the business name. Each customer's own Odoo requests names for its
own numbers, so nobody processes them by hand.

## Checking for leftover phone logins

Every softphone and desk phone has its own login (SIP endpoint) at the
provider. To list them against the ones Odoo knows (read-only), on the
server:

```
sudo -u odoo /opt/odoo19/venv/bin/python /opt/odoo19/odoo/odoo-bin shell -c /etc/odoo/odoo.conf -d meskis --no-http <<'EOF2'
known = set(env['res.users'].search([('signalwire_sip_endpoint_id', '!=', False)]).mapped('signalwire_sip_endpoint_id'))
known |= set(env['signalwire.desk_phone'].search([]).mapped('signalwire_sip_endpoint_id'))
for server in env['signalwire.server'].search([]):
    data = server._get_client().relay_get('endpoints/sip')
    for ep in data.get('data', data if isinstance(data, list) else []):
        print('ENDPOINT', ep.get('id'), ep.get('username'), 'in Odoo' if ep.get('id') in known else 'NOT IN ODOO')
EOF2
```

A "NOT IN ODOO" login is a leftover (2026-11-16: `fabrictest1`, from early
testing). Releasing a softphone in Odoo deletes its login at the provider.

