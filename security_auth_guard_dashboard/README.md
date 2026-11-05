# Security Auth Guard Dashboard

Adds a **Threats** dashboard to the Dashboards app, and as the first page of
the Security app. Only Security Officers can see it. Installs automatically
when `security_auth_guard` and `spreadsheet_dashboard` are both present.

It shows a threat level, counts for the last 24 hours, events waiting for
review, failed logins per day, the top addresses and logins being tried,
active block rules and recent successful logins. The data refreshes when the
dashboard is opened.

## How the threat level works

It's a simple rule, not an analysis of what an attacker is doing:

- **HIGH**: a critical event is waiting for review, or 100 or more failed
  logins in 24 hours. It stays HIGH until the critical events are marked as
  reviewed.
- **ELEVATED**: 20 or more failed logins, any login cooldown, or any
  automatic block in 24 hours.
- **NORMAL**: none of the above.

The failed-login numbers are cells on the dashboard's `Data` sheet. Edits made
in the spreadsheet are replaced by a module update.
