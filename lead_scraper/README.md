# Home health agency lead gen + cold outreach

Three-stage pipeline: pull leads from public data, find contact emails,
send a compliant cold email.

## 0. Where to run this

This won't run inside a network-sandboxed environment (e.g. a locked-down
Claude Code on the web session) — it needs outbound access to
npiregistry.cms.hhs.gov, DuckDuckGo, agency websites, and your SMTP
provider. Run it locally or in an environment with open network access.

## 1. Get leads

```
pip install -r requirements.txt
python npi_leads.py --state TX --out leads_tx.csv
```

Pulls home health agencies from the NPI Registry (NPPES) — free, public,
official U.S. government provider data. No API key, no ToS issue. Gives
you org name, address, phone. No email/website (NPI doesn't have it).

## 2. Find emails

```
python find_emails.py --in leads_tx.csv --out leads_tx_enriched.csv --limit 50
```

For each lead, searches for the agency's website and pulls a contact email
off the site itself (homepage/contact/about pages). This is best-effort —
expect well under 100% hit rate, and spot-check results before using them.
Keep `--limit` modest; this hits DuckDuckGo's HTML search and other
sites' servers directly, so don't run it against thousands of leads in
one go.

If you'd rather avoid scraping search results, swap in the Google Places
API (Text Search + Place Details) in `find_website()` — paid, but has a
free monthly credit and is fully within ToS.

## 3. Send

```
cp .env.example .env   # fill in real SMTP creds + business info
python send_emails.py --in leads_tx_enriched.csv --dry-run   # review first
python send_emails.py --in leads_tx_enriched.csv --test-email you@you.com  # dry-run only sends nothing; use --live for a real single test
python send_emails.py --in leads_tx_enriched.csv --live
```

`--live` refuses to run unless every compliance field in `.env` is set
(real mailing address, real unsubscribe link, real reply-to). Sends are
logged to `sent_log.csv` and skipped on rerun.

## Compliance (CAN-SPAM, since this is unsolicited commercial email)

- Use accurate From/Reply-To — no spoofed headers.
- Include a real physical mailing address (`MAILING_ADDRESS`) — done automatically.
- Include a working unsubscribe mechanism (`UNSUBSCRIBE_URL`) — done automatically, but you must actually build the unsubscribe endpoint and honor requests within 10 business days.
- Don't email anyone who's opted out. `sent_log.csv` only tracks sends, not opt-outs — you need to maintain a suppression list yourself if you use a real unsubscribe link.
- If a state's licensing/directory terms restrict commercial reuse of the data, check them — NPI Registry data is explicitly public and reusable, but if you add other lead sources later, verify each one.
