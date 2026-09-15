# Namecheap - HestiaCP Bridge

A small connecting module between [`namecheap_domains`](../namecheap_domains/)
and [`hestiacp_hosting`](../hestiacp_hosting/) - deliberately **not** merged
into either one, since not every domain bought through Namecheap ends up
hosted on HestiaCP, and each of those two modules should stay installable
without the other.

## What "Deploy to HestiaCP" actually does

Adds `hestiacp_account_id` to `namecheap.domain` and a "Deploy to
HestiaCP" button, which:

1. **Checks the account's Web Domains headroom first**, via `v-list-user`
   (already used elsewhere in `hestiacp_hosting`, part of the `billing`
   Access Key category). This exists because `v-add-domain` - see next
   step - doesn't raise a clean error when only *one* of web/DNS/mail
   domain types is already at its package limit, only when all three
   are; left unchecked, a full Web Domains limit would silently skip
   just the web vhost while the command still reports success overall,
   which would look like a working deploy right up until the site
   never actually loads. Verified against `v-add-domain`'s own source
   (`bin/v-add-domain`), 2026-09-14.
2. **Adds the domain to the account** via `v-add-domain` - one call
   handles web, DNS, and mail domain setup together (respecting each
   type's own package limit independently), also `billing`-category.
3. **Points the domain's nameservers at HestiaCP**, via Namecheap's
   `domains.dns.setCustom`, using whatever nameservers (`NS`) are
   already configured on the HestiaCP account (inherited from its
   package) - without this step the domain would be "added" in
   HestiaCP but still resolve through Namecheap's own default DNS, so
   the site wouldn't actually be reachable there. If the account has no
   `NS` configured, the deploy still completes (the domain is usable in
   HestiaCP for when nameservers get sorted out by hand) but logs a
   clear chatter note that DNS wasn't touched.

## What this does NOT do

- **Doesn't touch domain registration.** `namecheap_domains` itself
  doesn't call `namecheap.domains.create` yet (see its own README) -
  this module assumes the domain is already owned and tracked as a
  `namecheap.domain` record.
- **Doesn't undo itself.** There's no "remove from HestiaCP" action -
  if a domain needs to move off an account, that's a manual HestiaCP
  operation for now (`v-delete-domain` on the HestiaCP side, plus
  reverting nameservers at Namecheap via `domains.dns.setDefault` if
  needed).
- **One deploy per domain, not re-deployable.** The button disappears
  once `hestiacp_deployed_on` is set - there's no "redeploy"/"move to a
  different account" flow yet.

## Testing

All business logic is covered by tests mocking both
`hestiacp.server._get_client()` and `namecheap.server._get_client()` -
nothing here makes a real HTTP call to either HestiaCP or Namecheap.
