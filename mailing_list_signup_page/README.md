# Mailing List Signup Page

A simple, phone-friendly signup page for a mailing list, for example
`yoursite.com/join/news`, with a QR code and a printable table sign.
Made for meeting people in person: hand someone your business card with the
QR code on it, put the sign on your table at a mixer, or let people type
their address straight into your own phone in kiosk mode.

## Set it up

1. **Email Marketing → Mailing Lists**, open the list.
2. Tick **Show In Preferences** (the list must be public).
3. Under **Signup Page**, fill in:
   - **Signup Page Address**: the last part of the address, such as `news`
     (lowercase letters, digits and hyphens). The page is then at `/join/news`.
   - **Signup Page Title**: defaults to "Nice to meet you!".
   - **Signup Page Introduction**: a sentence or two about what people will get.
4. The form then shows the page's full address and a **Download the QR code**
   link (a PNG to put on business cards or flyers).

If the list has a **Welcome Email** (Mailing List Welcome), everyone who signs
up on the page gets it, once per address.

## At an event

- **A table sign:** on the mailing list, the ⚙ menu next to its name has **Signup Sign** under Print. It gives a PDF
  with the title, a large QR code and the address to type.
- **Kiosk mode:** open the page on your own phone or tablet with `?kiosk=1`
  at the end, for example `/join/news?kiosk=1`. Each person enters their name
  and email and gets a "Thank you!", and after a few seconds the page is ready
  for the next person. In kiosk mode:
  - each signup is forgotten as soon as it's done, so the next person sees an
    empty form, not "already subscribed";
  - the browser isn't asked to remember or suggest earlier addresses;
  - the site's header and footer are hidden, so nobody wanders off.

  Use a browser window where you're **not** logged in to the site (a private
  window works), so nothing of yours is shown.

## How it behaves

- **Bot protection:** the form uses whichever protection your site has for
  Odoo's forms (Cloudflare Turnstile or Google reCAPTCHA), plus a hidden field
  that only bots fill in.
- **Signing up twice** is harmless: one subscription, one welcome email.
- **Someone who had unsubscribed** and signs up again is put back on the list
  (their own choice, made on the page).
- The page isn't listed in the sitemap.

## Tests

10 tests: the address rules, the page and its QR code, a signup with its one
welcome email, kiosk mode forgetting each person, a mistyped address, the bot
trap, and the printed sign.
