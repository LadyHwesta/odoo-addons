# Customer deployment checklists

Plain CSV files for Odoo's built-in Project task import - not an Odoo
module, just reference files you re-use by hand every time a new
customer needs onboarding. One file per service line, so you only
import the ones that match what the customer actually bought.

## How to use these

1. Create (or open) the customer's own `project.project` - one
   project per customer is the convention `managed_odoo_instances`
   already uses for its own auto-generated deployment checklists.
2. Open that project's **Tasks** list view.
3. Favorites menu (or the gear icon, depending on your Odoo version) →
   **Import records**.
4. Upload the CSV, confirm the column mapping (`name`, `sequence`,
   `description` map straight across, no manual mapping needed), and
   import. The project is picked up automatically from where you're
   standing - the files don't carry a `project_id` column on purpose.
5. Always start with `01_new_customer_onboarding.csv`, then import
   whichever of `02`-`07` match the order.

**Import each file at most once per customer.** These files
deliberately have no `id` (External ID) column - every import creates
brand-new task rows, so re-importing the same file into the same
project just duplicates the checklist rather than updating it. That's
intentional: an External ID column would let you re-import safely, but
it would also mean importing the *same* file for a *second* customer
could silently move the first customer's tasks into the second
customer's project instead of creating fresh ones, since External IDs
are unique across the whole database, not per project. Plain re-create
is the safer default here.

## Which files apply to which purchase

| File | When to import it |
|---|---|
| `01_new_customer_onboarding.csv` | Every customer, every time. |
| `02_hestiacp_hosting.csv` | Hosting package purchased. |
| `03_domain_registration.csv` | Domain(s) purchased. |
| `04_signalwire_voip_setup.csv` | VoIP number(s)/softphone/desk phones purchased. |
| `05_signalwire_sms_setup.csv` | SMS reselling purchased (own API token) or SMS enabled on a number. |
| `06_signalwire_10dlc_registration.csv` | Customer needs to send SMS and hasn't registered a brand/campaign yet. |
| `07_managed_odoo_instance_prerequisites.csv` | Managed Odoo hosting purchased - **only covers the manual work before clicking Request**; that button auto-generates its own much longer checklist (server bootstrap, vhost, SSL, database, go-live) as real project tasks on the instance's own project, so don't also import a static version of that part - it would just duplicate what the code already creates. |

## Keeping these current

These reflect the actual button/action names in each module as of
2026-09-16 (`action_provision`, `action_request_sms_enablement`,
"Configure Inbound Routing", etc.) - if a module's UI changes, these
files drift out of date silently, the same way any static
documentation does. Worth a quick skim against the real screens every
few months, or whenever a module's button labels change.
