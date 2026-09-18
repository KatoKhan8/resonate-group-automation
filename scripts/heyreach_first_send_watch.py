#!/usr/bin/env python3
"""Has HeyReach campaign 605732 actually sent anything to a real person?

    py -3 scripts/heyreach_first_send_watch.py              # one read
    py -3 scripts/heyreach_first_send_watch.py --settle      # + settle SENT

READ-ONLY unless `--settle` is passed, and even then the only write is to this
system's own action ledger. It makes no provider write.

WHAT COUNTS AS A SEND, AND WHAT DOES NOT. `/campaign/GetLeadsFromCampaign` is
the endpoint that knows. Per lead:

    leadMessageStatus     MessageSent / MessageReply   <- a message went out
    leadConnectionStatus  ConnectionSent / ConnectionAccepted
    lastActionTime        non-null when something happened

`leadCampaignStatus` is NOT the answer and must not be read as one: leads in
this estate read `Failed` while also reading `ConnectionAccepted, MessageSent`,
so the campaign-level word disagrees with what the person received.
`progressStats` is not the answer either - it returns negative numbers.

WHY THE LEDGER IS SETTLED SEPARATELY. Activation is not a send. The three keys
were left `unresolved` on purpose: the campaign started, the people are
enrolled, and nothing had reached them yet. `unresolved` is the honest word for
that, and it BLOCKS a retry, which is what it is for. A key moves to `sent`
only when this script reads a real message status for that exact profile -
never because a campaign is running.
"""
import argparse
import hashlib
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import actionledger, campaigns, liststaging, store        # noqa: E402
from src.providers import (ProviderError, heyreach,                # noqa: E402
                           load_env)


# HEYREACH IS INTERMITTENT AND A DIAGNOSTIC THAT DIES ON IT IS NOT A
# DIAGNOSTIC. Measured 2026-09-18 around 07:20Z: `campaign_read` answered
# 500 on 2 of 8 consecutive calls and twice hung to the full 25s timeout,
# then recovered. This script crashed on the first one, on the morning its
# whole job was to say whether the falsifier had fired.
#
# READS ONLY, and that is the entire licence for retrying here. A retried
# GET asks the same question again; a retried write is a second write, and
# `src/ratelimit.py` refuses to retry a non-idempotent verb without an
# explicit idempotency assertion for exactly that reason. Nothing in this
# file writes.
#
# It also gives up rather than looping: a provider that is down stays down,
# and a script that retries forever reports nothing while looking busy.
READ_ATTEMPTS = 4
READ_BACKOFF = 2.0


def _read(what, fn):
    """One read, retried on a provider error, or raised with the count."""
    last = None
    for attempt in range(1, READ_ATTEMPTS + 1):
        try:
            return fn()
        except ProviderError as exc:
            last = exc
            if attempt < READ_ATTEMPTS:
                time.sleep(READ_BACKOFF * attempt)
    raise SystemExit(
        f"REFUSED: {what} failed {READ_ATTEMPTS} times, last: "
        f"{type(last).__name__}: {str(last)[:120]}. The provider could not "
        f"be read, which is NOT the same as nothing having been sent - "
        f"UNKNOWN IS NEVER 0. Read `work/replywatch.json` for whether reply "
        f"protection is also degraded, and try again.")

CANONICAL = "productive-linkedin-cohort-v2"
PROVIDER_ID = 605732
STEP_KEY = "li1"

SENT_MESSAGE = {"MessageSent", "MessageReply"}
SENT_CONNECTION = {"ConnectionSent", "ConnectionAccepted"}


def h12(value):
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:12]


def ledger_keys():
    """profile hash -> the ledger key for that contact's li1."""
    campaign = campaigns.require(CANONICAL)
    out = {}
    for rec in store.load():
        if rec["id"] not in (campaign.get("record_ids") or []):
            continue
        for contact in rec.get("contacts") or []:
            url = liststaging.canonical_profile_url(contact.get("linkedin"))
            if not url:
                continue
            out[h12(url.lower())] = (
                f"{rec['id']}:{contact.get('key')}:{STEP_KEY}:linkedin")
    return out


def read():
    row = _read(f"campaign_read({PROVIDER_ID})",
                lambda: heyreach.campaign_read(PROVIDER_ID)) or {}
    rows, total = _read(f"campaign_leads({PROVIDER_ID})",
                        lambda: heyreach.campaign_leads(PROVIDER_ID))
    leads = []
    for lead in rows or []:
        raw = lead.get("raw") or {}
        url = liststaging.canonical_profile_url(lead.get("profile_url"))
        message = str(raw.get("leadMessageStatus") or "None")
        connection = str(raw.get("leadConnectionStatus") or "None")
        leads.append({
            "hash": h12((url or "").lower()),
            "message": message,
            "connection": connection,
            "campaign_status": str(raw.get("leadCampaignStatus") or ""),
            "last_action": lead.get("at") or raw.get("lastActionTime"),
            "sent": message in SENT_MESSAGE,
            "connection_sent": connection in SENT_CONNECTION,
        })
    return row, total, leads


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--settle", action="store_true",
                        help="settle the ledger key of any lead the provider "
                             "says has been messaged")
    args = parser.parse_args(argv)

    load_env(os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "config", ".env"))

    row, total, leads = read()
    status = str(row.get("status") or "").upper()
    print("=== CAMPAIGN ===")
    print(f"  id                : {row.get('id')}")
    print(f"  status            : {status}")
    print(f"  startedAt         : {row.get('startedAt')}")
    print(f"  leads enrolled    : {total}")

    print("\n=== PER LEAD, PROVIDER TRUTH ===")
    for lead in leads:
        print(f"  {lead['hash']}  message={lead['message']:<14} "
              f"connection={lead['connection']:<20} "
              f"campaign={lead['campaign_status']:<10} "
              f"last={lead['last_action']}")

    messaged = [lead for lead in leads if lead["sent"]]
    connected = [lead for lead in leads if lead["connection_sent"]]
    print(f"\n  HEYREACH_LIVE       = {status == 'IN_PROGRESS'}")
    print(f"  HEYREACH_LIVE_COHORT= {total}")
    print(f"  HEYREACH_SENT       = {len(messaged)}")
    print(f"  connection requests = {len(connected)}")
    print(f"  HEYREACH_FIRST_SEND = {bool(messaged or connected)}")

    if not args.settle:
        return 0

    keys = ledger_keys()
    print("\n=== LEDGER ===")
    for lead in messaged:
        key = keys.get(lead["hash"])
        if not key:
            print(f"  {lead['hash']}  NO LEDGER KEY - not settling")
            continue
        state = actionledger.state_of(key)
        if state == actionledger.SENT:
            print(f"  {key}  already sent")
            continue
        actionledger.settle(
            key, actionledger.SENT,
            why=(f"HeyReach campaign {PROVIDER_ID} reports "
                 f"leadMessageStatus={lead['message']} for this profile"),
            provider_response=lead)
        print(f"  SETTLED {key} -> {actionledger.state_of(key)}")
    if not messaged:
        print("  nothing to settle: no lead has been messaged yet")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
