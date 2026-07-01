"""
Send the cold email template to enriched leads over SMTP.

Defaults to --dry-run (prints what would be sent, sends nothing). Pass
--live to actually send, which requires every var in .env to be set —
this is a deliberate gate, not boilerplate: CAN-SPAM requires a real
physical mailing address, a working unsubscribe mechanism, and accurate
sender info in every commercial email you send.

Setup:
    cp .env.example .env   # fill in your SMTP creds + business info
    python send_emails.py --in leads_enriched.csv --dry-run
    python send_emails.py --in leads_enriched.csv --live

Sends are logged to sent_log.csv and skipped on rerun, so this is safe
to re-run after interruptions without double-emailing anyone.
"""
import argparse
import csv
import os
import smtplib
import sys
import time
from email.mime.text import MIMEText
from email.utils import formataddr

from dotenv import load_dotenv

REQUIRED_LIVE_VARS = [
    "SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASS",
    "FROM_EMAIL", "FROM_NAME", "REPLY_TO_EMAIL",
    "MAILING_ADDRESS", "UNSUBSCRIBE_URL",
]

SENT_LOG = "sent_log.csv"


def load_template(path):
    with open(path) as f:
        text = f.read()
    subject_line, _, body = text.partition("\n\n")
    subject = subject_line.replace("SUBJECT:", "").strip()
    return subject, body


def render(text, row, env):
    return (
        text
        .replace("{{org_name}}", row.get("org_name", "there"))
        .replace("{{sender_name}}", env["FROM_NAME"])
        .replace("{{sender_title}}", env.get("SENDER_TITLE", ""))
        .replace("{{mailing_address}}", env["MAILING_ADDRESS"])
        .replace("{{unsubscribe_url}}", env["UNSUBSCRIBE_URL"])
        .replace("{{reply_phone}}", env.get("REPLY_PHONE", ""))
    )


def load_sent_log():
    if not os.path.exists(SENT_LOG):
        return set()
    with open(SENT_LOG, newline="") as f:
        return {row["email"] for row in csv.DictReader(f)}


def append_sent_log(email, status):
    exists = os.path.exists(SENT_LOG)
    with open(SENT_LOG, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["email", "status", "timestamp"])
        if not exists:
            writer.writeheader()
        writer.writerow({"email": email, "status": status, "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")})


def send_one(smtp, subject, body, to_email, env):
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = formataddr((env["FROM_NAME"], env["FROM_EMAIL"]))
    msg["To"] = to_email
    msg["Reply-To"] = env["REPLY_TO_EMAIL"]
    msg["List-Unsubscribe"] = f"<{env['UNSUBSCRIBE_URL']}>"
    smtp.sendmail(env["FROM_EMAIL"], [to_email], msg.as_string())


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--in", dest="infile", required=True)
    ap.add_argument("--template", default="email_template.txt")
    ap.add_argument("--live", action="store_true", help="Actually send. Default is dry-run.")
    ap.add_argument("--rate-limit", type=float, default=3.0, help="Seconds between sends")
    ap.add_argument("--test-email", help="Send only to this address, for a single test send")
    args = ap.parse_args()

    load_dotenv()
    env = {k: os.environ.get(k, "") for k in REQUIRED_LIVE_VARS}
    env["SENDER_TITLE"] = os.environ.get("SENDER_TITLE", "")
    env["REPLY_PHONE"] = os.environ.get("REPLY_PHONE", "")

    if args.live:
        missing = [k for k in REQUIRED_LIVE_VARS if not env[k]]
        if missing:
            sys.exit(f"Refusing to send live: missing required .env vars: {', '.join(missing)}")

    subject, body = load_template(args.template)

    with open(args.infile, newline="") as f:
        rows = [r for r in csv.DictReader(f) if r.get("email")]

    already_sent = load_sent_log()
    smtp = None
    if args.live:
        smtp = smtplib.SMTP(env["SMTP_HOST"], int(env["SMTP_PORT"]))
        smtp.starttls()
        smtp.login(env["SMTP_USER"], env["SMTP_PASS"])

    try:
        targets = rows
        if args.test_email:
            targets = [{**rows[0], "email": args.test_email}] if rows else [{"org_name": "Test", "email": args.test_email}]

        for row in targets:
            to_email = row["email"]
            if to_email in already_sent and not args.test_email:
                print(f"skip (already sent): {to_email}", file=sys.stderr)
                continue
            rendered_subject = render(subject, row, env if args.live else {**env, "FROM_NAME": env["FROM_NAME"] or "[FROM_NAME]", "MAILING_ADDRESS": env["MAILING_ADDRESS"] or "[MAILING_ADDRESS]", "UNSUBSCRIBE_URL": env["UNSUBSCRIBE_URL"] or "[UNSUBSCRIBE_URL]"})
            rendered_body = render(body, row, env if args.live else {**env, "FROM_NAME": env["FROM_NAME"] or "[FROM_NAME]", "MAILING_ADDRESS": env["MAILING_ADDRESS"] or "[MAILING_ADDRESS]", "UNSUBSCRIBE_URL": env["UNSUBSCRIBE_URL"] or "[UNSUBSCRIBE_URL]"})

            if not args.live:
                print(f"--- DRY RUN: would send to {to_email} ---")
                print(f"Subject: {rendered_subject}")
                print(rendered_body)
                print()
                continue

            send_one(smtp, rendered_subject, rendered_body, to_email, env)
            append_sent_log(to_email, "sent")
            print(f"sent: {to_email}", file=sys.stderr)
            time.sleep(args.rate_limit)
    finally:
        if smtp:
            smtp.quit()


if __name__ == "__main__":
    main()
