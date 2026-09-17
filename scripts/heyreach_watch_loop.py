#!/usr/bin/env python3
"""Emit ONE line whenever campaign 605732's provider truth changes. READ-ONLY.

    py -3 scripts/heyreach_watch_loop.py [--interval 300]

Built for a background monitor, so it prints one line per EVENT and nothing
while the picture is unchanged. Every line is flushed, because a line sitting
in a buffer is a line nobody sees.

WHAT IT EMITS, and the list is deliberately wider than the good news:

    SEND        a lead's leadMessageStatus reached MessageSent/MessageReply
    CONNECT     a lead's leadConnectionStatus reached ConnectionSent/Accepted
    REPLY       a lead replied
    LEAD-ERROR  a lead carries an error_code, or its status went to Failed
    STATUS      the campaign left IN_PROGRESS (paused, finished, failed)
    COHORT      the enrolled lead count moved - the audience changed under us
    READ-ERROR  the provider could not be read (reported, not fatal)

Silence means "nothing changed", and that is only trustworthy because a
failure has its own line. A watcher that emits only on success is
indistinguishable from a watcher whose campaign died an hour ago.
"""
import argparse
import hashlib
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import liststaging                                     # noqa: E402
from src.providers import heyreach, load_env                     # noqa: E402

PROVIDER_ID = 605732
SENT_MESSAGE = {"MessageSent", "MessageReply"}
SENT_CONNECTION = {"ConnectionSent", "ConnectionAccepted"}


def h12(value):
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:12]


def emit(line):
    print(line, flush=True)


def snapshot():
    row = heyreach.campaign_read(PROVIDER_ID) or {}
    rows, total = heyreach.campaign_leads(PROVIDER_ID)
    leads = {}
    for lead in rows or []:
        raw = lead.get("raw") or {}
        url = liststaging.canonical_profile_url(lead.get("profile_url"))
        leads[h12((url or "").lower())] = {
            "message": str(raw.get("leadMessageStatus") or "None"),
            "connection": str(raw.get("leadConnectionStatus") or "None"),
            "campaign": str(raw.get("leadCampaignStatus") or ""),
            "error": lead.get("error_code"),
        }
    return {"status": str(row.get("status") or "").upper(),
            "total": total, "leads": leads}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--interval", type=float, default=300.0)
    args = parser.parse_args(argv)

    load_env(os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "config", ".env"))

    previous = None
    consecutive_errors = 0
    while True:
        try:
            current = snapshot()
            consecutive_errors = 0
        except Exception as exc:
            consecutive_errors += 1
            # Transient provider timeouts are common on this estate today, so
            # one failure is noted only after it repeats - but it IS noted.
            if consecutive_errors in (3, 12):
                emit(f"READ-ERROR 605732 unreadable {consecutive_errors}x: "
                     f"{type(exc).__name__}")
            time.sleep(args.interval)
            continue

        if previous is None:
            emit(f"WATCHING 605732 status={current['status']} "
                 f"leads={current['total']} sent=0")
            previous = current
            time.sleep(args.interval)
            continue

        if current["status"] != previous["status"]:
            emit(f"STATUS 605732 {previous['status']} -> {current['status']}")
        if current["total"] != previous["total"]:
            emit(f"COHORT 605732 enrolled {previous['total']} -> "
                 f"{current['total']}")

        for phash, now in current["leads"].items():
            was = previous["leads"].get(phash) or {}
            if now["message"] != was.get("message"):
                if now["message"] in SENT_MESSAGE:
                    label = "REPLY" if now["message"] == "MessageReply" else "SEND"
                    emit(f"{label} 605732 {phash} message={now['message']}")
                else:
                    emit(f"LEAD-CHANGE 605732 {phash} "
                         f"message={was.get('message')} -> {now['message']}")
            if (now["connection"] != was.get("connection")
                    and now["connection"] in SENT_CONNECTION):
                emit(f"CONNECT 605732 {phash} "
                     f"connection={now['connection']}")
            if now.get("error") and now.get("error") != was.get("error"):
                emit(f"LEAD-ERROR 605732 {phash} error={now['error']}")
            if now["campaign"] == "Failed" and was.get("campaign") != "Failed":
                emit(f"LEAD-ERROR 605732 {phash} campaignStatus=Failed")

        previous = current
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
