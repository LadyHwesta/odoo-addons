# Reload After Upgrades

After the server's modules are upgraded, an Odoo window that was already
open keeps running the old screens until it's reloaded. The installed app
(PWA) often has no reload button at all, so people end up quitting and
reopening it. This module makes open windows catch up by themselves.

## What it does

The web client starts with a registry fingerprint
(`session.registry_hash`), which changes whenever modules are installed or
upgraded. A small route, `/web_reload_on_upgrade/version`, returns the
server's current one, worked out the same way. The window compares the two:

- **when it comes back to the front** (switching back to the app or tab,
  or clicking into a window that stayed visible behind another app);
- **when the live connection reconnects**, as it does after the server
  restarts;
- **every ten minutes** while it's on screen.

When they differ:

- **Coming back to the front:** the open record is saved, the app's offline
  copy of the page is cleared, and the window reloads. A reload is enough,
  because Odoo's own cache of screens and menus is keyed to the
  fingerprint and throws itself away.
- **Noticed while someone is using the window**, or a dialog is open, or
  the record can't be saved: an "Update available" notification offers a
  Reload button instead, and the next return to the front reloads.

Odoo's own "The page appears to be out of date" notice doesn't cover this
case. It compares Odoo's version number, which an upgrade of our modules
doesn't change.

## Tests

`tests/test_reload_on_upgrade.py`:

- the route returns the same fingerprint the web client starts with, and
  needs a login;
- browser tests: no reload when nothing changed, a reload on return after
  an upgrade, and the offer-then-Reload path while the window is in use.
