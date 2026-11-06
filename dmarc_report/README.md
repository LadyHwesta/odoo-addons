# DMARC Reports

Mail providers such as Google and Microsoft send a daily DMARC aggregate report
to the address in a domain's DMARC record. This module reads those reports and
tells you, per domain and in plain language, who is sending mail as you, what
passes, what fails and what to fix.

## Setup

1. **A mailbox for the reports.** Create a real mailbox such as `dmarc@example.com`.
2. **DNS.** Add the address to each domain's DMARC record, for example
   `_dmarc  TXT  "v=DMARC1; p=none; rua=mailto:dmarc@example.com"`. Start new
   domains at `p=none` and tighten once the findings show everything passes.
   If the reporting address is on a different domain from the one being
   reported on, that domain must allow it:
   `<reported-domain>._report._dmarc.<reporting-domain>  TXT  "v=DMARC1"`.
   A wildcard, `*._report._dmarc  TXT  "v=DMARC1"`, allows any domain at once,
   for example so customers can send their reports to you.
3. **Settings › DMARC.** Enter the reporting address. Each domain then shows the
   exact records to publish under **DNS setup**.
4. **Incoming Mail Server.** Open it from Settings › DMARC, point it at the
   mailbox, and set **Create a New Record** to **DMARC Report**.

## What it does

- Reads reports sent as XML, gzip or zip. Unpacked size is capped at 20 MB, and
  the XML parser resolves no entities and fetches nothing, since the files come
  from strangers.
- Skips a report it has already read (same reporter and report ID). A message it
  can't read becomes a report marked "Couldn't read", with the reason, rather
  than vanishing.
- Names each sending server from its reverse DNS: Google, Microsoft 365,
  PlanetHoster, UpCloud and other common providers. Unknown servers show their
  hostname or IP.
- **Findings** on each domain cover the last 30 days by default: the pass rate,
  each failing sender with what to do about it, mail that passed through
  forwarding, and when the policy can safely be tightened.
- Posts on the domain, emailing its followers, the first time a sender fails for
  it. Managers follow new domains automatically.

## Access

DMARC **Viewer** can read everything. **Manager** can also change settings and
domains. The admin user is a Manager on install.

## Not yet

- Forensic (`ruf`) reports, which contain parts of real messages.
- A customer portal view of their own domains.
