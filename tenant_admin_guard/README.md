# Hosted Database Admin Guard

For an Odoo database someone else hosts. The customer's own administrators keep
Odoo's normal **Settings** role. They manage company details, users and their
access, and every app's settings page. The hosting provider keeps one thing back:
the **Technical Administrator (hosting provider)** role.

Only that role can:

| What | Where it's stopped |
|---|---|
| Install, remove or upgrade apps | Every module button, the upgrade, update and uninstall wizards, and a module's state |
| Turn on a setting that installs or removes an app | Saving the settings page, before anything is saved |
| See the Apps and Technical menus | Hidden when each user's menu is built, whatever other modules set the menus' groups to |
| Write code | Server and scheduled actions of type "Execute Code", computed custom fields |
| Change a technical administrator's login, password, email, groups or active status, or delete them | Users and their contact's email |
| Give anyone the role | Users, groups, and groups that would imply it |

The built-in admin user (`base.user_admin`) gets the role when the module is installed.
Code running with sudo is let through, because Odoo itself installs a few modules
behind the scenes (a company's localization when its country is set, for example),
and nobody can reach sudo from the web client or the API.

A customer who tries any of these sees: "… is handled by your hosting provider. Ask
them in the customer portal or by email."

## What it doesn't do

It isn't a sandbox. The Settings role can still do a lot, on purpose: it's the
customer's database. It stops the things a hosting provider has to control to keep
the database updatable and supportable.

Meskis Works' deploy agent installs this in every new Managed Odoo database and
makes the built-in admin Meskis Works' own account (see `meskis-deploy-agent`).
