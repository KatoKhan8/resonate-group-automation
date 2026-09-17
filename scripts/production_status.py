#!/usr/bin/env python3
"""The live production numbers, read from provider truth and canonical state.

    py -3 scripts/production_status.py
    py -3 scripts/production_status.py --json

READ-ONLY. It makes read-only provider calls and reads `work/` state. It writes
nothing, anywhere.

WHY A SCRIPT RATHER THAN A PARAGRAPH IN A REPORT. Every number here has been
wrong at least once this week because somebody carried it forward by hand:
the LinkedIn cohort was reported as 4 and was 3, the email cohort was reported
as 10 and was 10 for a different reason than the one written down, and
`work/queue.snapshot.jsonl` produced two wrong figures in one day. A number
that is recomputed is a number that can be checked; a number that is quoted is
a number that drifts.

UNKNOWN IS PRINTED AS UNKNOWN. A provider that cannot be read, or a metric no
route exposes, says so. It never falls back to zero - a zero that means "we
could not ask" is indistinguishable from a zero that means "nothing happened",
and those are the two answers this whole system exists to keep apart.

WHAT A SEND MEANS HERE, PER CHANNEL, because the two providers answer
differently:

  HeyReach    `/campaign/GetLeadsFromCampaign` per lead:
              leadMessageStatus MessageSent/MessageReply. NOT
              `leadCampaignStatus` - leads in this estate read `Failed` while
              also reading `MessageSent` - and NOT `progressStats`, which
              returns negative numbers.
  EmailBison  the campaign's `emails_sent` counter AND `scheduled_emails`,
              which returns one ROW PER MESSAGE. Two witnesses, because this
              provider silently discarded `max_emails_per_day` on create and
              read it back as 1000.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import actionledger, campaigns, store                  # noqa: E402
from src.providers import bison, heyreach, load_env             # noqa: E402

UNKNOWN = "UNKNOWN"

LINKEDIN_CAMPAIGN = 605732
LINKEDIN_LIST = 944355
EMAIL_CAMPAIGN = 487

SENT_MESSAGE = {"MessageSent", "MessageReply"}
SENT_CONNECTION = {"ConnectionSent", "ConnectionAccepted"}
EMAIL_SENT_WORDS = {"sent", "delivered"}


def _try(fn, *args, **kw):
    """The value, or UNKNOWN. Never a zero standing in for a failed read."""
    try:
        return fn(*args, **kw)
    except Exception as exc:                        # provider transport only
        return f"{UNKNOWN} ({type(exc).__name__})"


def linkedin():
    out = {"campaign": LINKEDIN_CAMPAIGN, "list": LINKEDIN_LIST}
    row = _try(heyreach.campaign_read, LINKEDIN_CAMPAIGN)
    if isinstance(row, str):
        return dict(out, status=row, live=UNKNOWN, sent=UNKNOWN)
    out["status"] = str(row.get("status") or "").upper()
    out["live"] = out["status"] == "IN_PROGRESS"
    out["started_at"] = row.get("startedAt")
    out["seats"] = row.get("campaignAccountIds") or []

    leads = _try(heyreach.campaign_leads, LINKEDIN_CAMPAIGN)
    if isinstance(leads, str):
        return dict(out, cohort=UNKNOWN, sent=UNKNOWN)
    rows, total = leads
    out["cohort"] = total
    messaged = connected = replied = pending = 0
    for lead in rows or []:
        raw = lead.get("raw") or {}
        message = str(raw.get("leadMessageStatus") or "None")
        connection = str(raw.get("leadConnectionStatus") or "None")
        if message in SENT_MESSAGE:
            messaged += 1
        if message == "MessageReply":
            replied += 1
        if connection in SENT_CONNECTION:
            connected += 1
        if message == "None" and connection == "None":
            pending += 1
    out.update(sent=messaged, connection_requests=connected,
               replies=replied, pending=pending,
               first_send=bool(messaged or connected))
    return out


def email():
    out = {"campaign": EMAIL_CAMPAIGN}
    row = _try(bison.campaign, EMAIL_CAMPAIGN)
    if isinstance(row, str):
        return dict(out, status=row, live=UNKNOWN, sent=UNKNOWN)
    out["status"] = str(row.get("status") or "").lower()
    out["live"] = out["status"] == "active"
    out["cohort"] = row.get("total_leads")
    out["cap_per_day"] = row.get("max_emails_per_day")
    out["senders"] = _try(bison.campaign_senders, EMAIL_CAMPAIGN)

    counter = row.get("emails_sent")
    queue = _try(bison.scheduled_emails, EMAIL_CAMPAIGN)
    if isinstance(queue, str):
        queue_sent = UNKNOWN
        queue_rows = UNKNOWN
    else:
        queue_rows = len(queue or [])
        queue_sent = 0
        for entry in queue or []:
            state = str(entry.get("status") or entry.get("state") or "").lower()
            if state in EMAIL_SENT_WORDS or entry.get("sent_at"):
                queue_sent += 1
    out.update(sent_counter=counter, queue_rows=queue_rows,
               queue_sent=queue_sent,
               replies=row.get("replied"), bounced=row.get("bounced"),
               unsubscribed=row.get("unsubscribed"))
    # A send is claimed only when a witness says so. Two witnesses; either is
    # sufficient to say a person was reached, neither is inferred from status.
    witnesses = [v for v in (counter, queue_sent) if isinstance(v, int)]
    out["sent"] = max(witnesses) if witnesses else UNKNOWN
    out["first_send"] = (bool(out["sent"]) if isinstance(out["sent"], int)
                         else UNKNOWN)
    return out


def ledger():
    """What this system's own audit trail says, by latest state per key."""
    try:
        rows = actionledger.load()
    except Exception as exc:                        # noqa: BLE001
        return {"state": f"{UNKNOWN} ({type(exc).__name__})"}
    latest = {}
    for row in rows:
        if isinstance(row, dict) and row.get("key"):
            latest[row["key"]] = row
    counts = {}
    for row in latest.values():
        state = str(row.get("state") or "?")
        counts[state] = counts.get(state, 0) + 1
    return counts


def estate():
    """Canonical state. Counts only - never a name, address or domain."""
    try:
        recs = store.load()
    except Exception as exc:                        # noqa: BLE001
        return {"records": f"{UNKNOWN} ({type(exc).__name__})"}
    contacts = sum(len(r.get("contacts") or []) for r in recs)
    with_email_cadence = with_li_cadence = 0
    for rec in recs:
        cadence = rec.get("cadence") or {}
        for steps in cadence.values():
            if not isinstance(steps, dict):
                continue
            if any(k.startswith("em") for k in steps):
                with_email_cadence += 1
            if any(k.startswith("li") for k in steps):
                with_li_cadence += 1
    return {"records": len(recs), "contacts": contacts,
            "contacts_with_email_cadence": with_email_cadence,
            "contacts_with_linkedin_cadence": with_li_cadence}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    load_env(os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "config", ".env"))

    report = {"linkedin": linkedin(), "email": email(),
              "ledger": ledger(), "estate": estate()}
    if args.json:
        print(json.dumps(report, indent=1, default=str))
        return 0

    li, em = report["linkedin"], report["email"]
    print("=== PRODUCTION ===")
    print(f"  HEYREACH_LIVE        = {li.get('live')}")
    print(f"  HEYREACH_LIVE_COHORT = {li.get('cohort')}")
    print(f"  HEYREACH_SENT        = {li.get('sent')}")
    print(f"  HEYREACH_CONNECTS    = {li.get('connection_requests')}")
    print(f"  HEYREACH_REPLIES     = {li.get('replies')}")
    print(f"  HEYREACH_FIRST_SEND  = {li.get('first_send')}")
    print(f"  EMAILBISON_LIVE      = {em.get('live')}")
    print(f"  EMAILBISON_COHORT    = {em.get('cohort')}")
    print(f"  EMAILBISON_SENT      = {em.get('sent')}  "
          f"(counter={em.get('sent_counter')} "
          f"queue_sent={em.get('queue_sent')}/{em.get('queue_rows')})")
    print(f"  EMAILBISON_REPLIES   = {em.get('replies')}")
    print(f"  EMAILBISON_BOUNCED   = {em.get('bounced')}")
    print(f"  EMAILBISON_FIRST_SEND= {em.get('first_send')}")
    print("\n=== LEDGER (latest state per key) ===")
    for state, count in sorted(report["ledger"].items()):
        print(f"  {state:12s} {count}")
    print("\n=== ESTATE ===")
    for key, value in sorted(report["estate"].items()):
        print(f"  {key:32s} {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
