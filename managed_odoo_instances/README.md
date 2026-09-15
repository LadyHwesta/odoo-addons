# Managed Odoo Instances

Phase 2 of the reseller-subscriptions project (Phase 1:
[`reseller_subscriptions`](../reseller_subscriptions/)). Treats "we
stand up and run a dedicated Odoo instance for you" as a real,
trackable, billable product - either on the shared multi-tenant
server for smaller customers, or a dedicated VPS/customer-provided
server for anyone who needs their own.

## Where the actual work happens

This module never runs a shell command or holds an SSH credential.
The real system-level work - nginx vhost creation, SSL via certbot,
database creation + app install - is done by a small standalone
companion service, [`meskis-deploy-agent`](https://github.com/LadyHwesta/meskis-deploy-agent)
(its own repo - genuinely different software, not an Odoo addon),
called over HTTPS with a bearer token via `DeploymentAgentClient`
(`models/deployment_agent_client.py`) - the same
`SignalWireClient`/`HestiaCPClient` pattern already used throughout
this repo.

## The models

- **`deployment.server`** - one record per Odoo-hosting server. Exactly
  one `kind='shared'` record should exist, pointing at the
  already-running shared box (set up once, by hand - this module
  never bootstraps it). One new `kind='dedicated'` record per customer
  needing their own VPS.
- **`deployment.instance`** - one record per customer database. Bills
  through `reseller_subscriptions`'s own `contract.billing.mixin` -
  `action_request()` creates the contract as an empty shell (for
  tracking) and a real `project.project` deployment checklist;
  `action_mark_live()` is what actually adds the recurring contract
  line(s) and starts invoicing, so a customer isn't billed for
  however long it takes to actually stand their instance up.
- **`deployment.app`** - a small curated catalog (seed data covers the
  three existing suites - nonprofit/club/paramedic) mapping to real
  technical module names, each optionally linked to a sellable
  `product.template` for billing.

## The generated deployment checklist

`action_request()` always creates: "Create nginx vhost", "Issue SSL
certificate", "Create the database and install apps", "Preliminary
configuration" (manual - chart of accounts, fiscal localization, and
anything else deeper stays a real conversation with the customer, not
automated blind), "Mark instance live".

**For a dedicated server that hasn't been bootstrapped yet**, three
more tasks come first: "Confirm server access", "Run the bootstrap
script on the server" (the script itself is attached as a real file,
generated from `data/bootstrap_script.sh` - a bundled copy of
`meskis-deploy-agent`'s own `scripts/bootstrap.sh`, kept in sync by
hand between the two repos), and "Confirm the agent is reachable".
This is deliberately sent to **Tiesa**, never the customer - most
customers aren't technical enough for "SSH in and run this" to make
sense, and this project checklist is itself the real onboarding
runbook, not just a delivery mechanism for one script.

## Automated VPS creation via UpCloud

For a dedicated server whose `deployment.server.vps_provider` is set
to `upcloud`, the "does the box even exist yet" prerequisite is
automated too - `upcloud_account.py`/`upcloud_client.py`, and three
new buttons on the server record (Create UpCloud Server, Check VPS
Status, Destroy VPS). This doesn't change the bootstrap-script
decision at all: the generated checklist just gains one more task,
"Create the UpCloud VPS," ahead of "Confirm server access" - once the
VPS exists and SSH is reachable, everything from there is exactly as
before (Tiesa runs the bootstrap script by hand).

**Live-verified 2026-09-15** against the user's real UpCloud account -
created a real `STARTER-1xCPU-1GB` server from the Debian 12 template
in `us-chi1`, confirmed SSH login with the injected key actually
worked, then stopped and deleted it (confirmed gone via a follow-up
404). Two real findings baked into the client, not obvious from a
casual reading of UpCloud's docs:

- `metadata` in the create-server request body must be the **string**
  `"yes"`, not a JSON boolean - `true` is rejected outright
  (`METADATA_INVALID`). It's required at all because cloning a
  cloud-init-based template (the standard Debian/Ubuntu ones) fails
  with `METADATA_DISABLED_ON_CLOUD-INIT` without it.
- A server reaching UpCloud's own `state: "started"` does **not**
  mean SSH is actually reachable yet - a real connection attempt got
  refused immediately after `started`, and only succeeded about 15
  seconds later. `action_check_upcloud_status()`'s own notification
  text says as much rather than implying "started" means "ready."

`upcloud.account` (System group only - not even plain internal users
can read it, since a compromised token can spend real money broadly
across every server, not just one deployment) holds the API token,
Tiesa's own SSH public key (injected into every new server's root
login, matching the "Tiesa runs the bootstrap script, never the
customer" decision), and default zone/plan/OS-template - each
`deployment.server` can override any of those per-server.

## What's a deliberate manual step, not automated

- **The X-Odoo-Dbfilter routing middleware itself.** The shared
  server's real nginx snippet (shipped verbatim in
  `meskis-deploy-agent`'s own `templates/odoo_proxy.conf`) sets a
  per-vhost header that a custom middleware already installed on that
  box reads to route straight to the right database - "makes it
  easier for ensuring a customer is only ever connected to their
  database and the db chooser won't be displayed for them," per the
  user's own description of why. That middleware already exists on
  the shared server but isn't part of this project - a brand-new
  dedicated server needs it installed by hand too, flagged again at
  the end of the bootstrap script's own output.
- **Deeper per-instance configuration** (chart of accounts, fiscal
  localization, anything beyond company name + admin login) - a
  checklist item, reviewed with the customer directly.
- **Suite module names in `data/deployment_app_data.xml`** - the club
  suite's are confirmed against this repo directly; nonprofit and
  paramedic's are recalled from memory of their own separate repos,
  not re-verified against those repos' current `__manifest__.py`
  files while writing this. Confirm before actually deploying either
  for a real customer.
- **The target server's addons_path actually containing those suites'
  code.** Deploying "Nonprofit Suite" onto a customer's database only
  works if that server's Odoo installation can already find
  `nonprofit_base` etc. on its addons path - cloning the right repos
  onto a freshly bootstrapped server isn't part of `bootstrap.sh`
  today, a real gap worth closing before this handles a suite
  deployment for real.

## Testing

Local `testing/` harness, same as every other module in this repo.
Covers: domain/db-name validation constraints, the full
`action_request()` project-generation logic (shared vs. pending-
dedicated vs. already-bootstrapped-dedicated - task counts, the
bootstrap script actually attached where expected), every deployment
action calling the (mocked) agent client with the right arguments,
`_all_module_names()` de-duplicating across selected apps, and that
billing only actually starts at `action_mark_live()` - not at
request time, not twice on a repeated call. `DeploymentAgentClient`
and `deployment.server._get_client()`/`action_test_connection()` are
tested against `requests` mocked at the module boundary, same
convention as `HestiaCPClient`'s/`SignalWireClient`'s own tests.
`UpCloudClient` and the three `deployment.server` UpCloud actions get
the same treatment, plus a project-generation test confirming the
extra "Create the UpCloud VPS" task appears (and in the right order)
only when `vps_provider == 'upcloud'`.

Not run against the real shared Meskis Works server or any real
dedicated VPS - see `meskis-deploy-agent`'s own README for what's
still unverified there (`scripts/bootstrap.sh` itself, specifically).
**The UpCloud integration itself is the one piece of this whole
project actually live-verified against real infrastructure** - see
"Automated VPS creation via UpCloud" above.
