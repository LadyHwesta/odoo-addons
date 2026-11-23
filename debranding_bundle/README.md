# Debranding Bundle

One install for OCA's debranding (OCA/server-brand, 19.0), so customers never
mistake the provider of their Odoo for Odoo S.A.:

- `disable_odoo_online`: no Odoo online account and publisher links
- `remove_odoo_enterprise`: no Enterprise upsells in Settings
- `mail_debranding`: no "Powered by Odoo" in sent emails
- `portal_debranding`: none in the customer portal

Companion modules install themselves whenever their app is installed, now
or later:

- `debranding_bundle_sale`: brings `sale_portal_debranding` (quotes and orders in the portal)
- `debranding_bundle_website`: brings `website_debranding` (the website's "Powered by Odoo")
- `debranding_bundle_account`: with OCA's financial reports and bank statement
  import, plain labels instead of "OCA accounting reports" and "Import (OCA)"
  (now "Financial Reports" and "Import File")

Needs OCA/server-brand on the addons path. Managed Odoo installs it on every
instance.
