# Mailing List Welcome Email

Sends a welcome email to each person who signs up for a mailing list
through a website newsletter block. The email carries Odoo's normal
per-recipient unsubscribe link and one-click unsubscribe headers. If
someone types in an address that isn't theirs, its owner can leave the
list with one click.

## Set it up

1. **Email Marketing → New mailing.** Choose your list as the recipients
   and write the welcome email in the normal editor. Keep the footer with
   the **Unsubscribe** link. Don't send it yourself.
2. **Email Marketing → Mailing Lists**, open the list, and choose that
   mailing as its **Welcome Email**.

From then on, every new website signup to that list gets the welcome
email, queued for the next run of the outgoing mail queue (usually
within a minute or two).

## How it behaves

- **Once per address.** An address that already got it never gets it
  again, even if it is signed up repeatedly or leaves and re-joins. This
  also keeps the form from being used to send someone the same email
  over and over.
- **Blocklisted and opted-out addresses get nothing.** Odoo's own
  exclusion rules apply.
- **Website signups only.** Contacts you import or add by hand don't
  get it.
- **Statistics:** each welcome email shows up in that mailing's own
  statistics (sent, opened, clicked) like any other mailing. The mailing
  itself stays a draft, ready for the next signup.
- **Safety checks:** the list refuses a welcome email that has no
  unsubscribe link, or that isn't addressed to that list.

## Notes

- Commercial email in the US (CAN-SPAM) must include a postal address.
  Put one in the welcome email's footer.
- The signup form's bot protection comes from whatever protects Odoo's
  newsletter blocks on your site, for example `website_cf_turnstile`.

## Tests

6 tests: one welcome email per signup with its own unsubscribe link and
headers, never twice to the same address, nothing to a blocklisted
address, nothing for lists without a welcome email, and both safety
checks.
