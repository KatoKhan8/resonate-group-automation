#!/usr/bin/env python3
"""Emit ONE line whenever campaign 487's provider truth changes. READ-ONLY.

    py -3 scripts/bison_watch_loop.py [--interval 300]

Built for a background monitor: one line per EVENT, nothing while the picture
is unchanged, everything flushed.

WHAT IT EMITS, deliberately wider than the good news, because silence has to
mean "unchanged" rather than "died an hour ago":

    SEND        emails_sent rose, or a scheduled-email row reads sent
    REPLY       a reply was recorded
    BOUNCE      a bounce was recorded
    UNSUB       an unsubscribe was recorded
    STATUS      the campaign left `active` (paused, stopped, archived)
    COHORT      the lead count moved - the audience changed under us
    READ-ERROR  the provider could not be read, after it repeats

TWO WITNESSES FOR A SEND, not one. `emails_sent` is the campaign counter;
`scheduled_emails` returns one ROW PER MESSAGE and a sent one says so. Campaign
451 proved the second is readable before a send is visible in aggregate, and
the counter alone has been wrong on this provider before - `max_emails_per_day`
was silently discarded on create and read back 1000.
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.providers import bison, load_env                       # noqa: E402

PROVIDER_ID = 487
SENT_WORDS = {"sent", "delivered"}


def emit(line):
    print(line, flush=True)


def snapshot():
    row = bison.campaign(PROVIDER_ID) or {}
    queue = bison.scheduled_emails(PROVIDER_ID) or []
    sent_rows = 0
    for entry in queue:
        state = str(entry.get("status") or entry.get("state") or "").lower()
        if state in SENT_WORDS or entry.get("sent_at"):
            sent_rows += 1
    return {
        "status": str(row.get("status") or "").lower(),
        "emails_sent": int(row.get("emails_sent") or 0),
        "replied": int(row.get("replied") or 0),
        "bounced": int(row.get("bounced") or 0),
        "unsubscribed": int(row.get("unsubscribed") or 0),
        "leads": int(row.get("total_leads") or 0),
        "queue_rows": len(queue),
        "sent_rows": sent_rows,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--interval", type=float, default=300.0)
    args = parser.parse_args(argv)

    load_env(os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "config", ".env"))

    previous = None
    errors = 0
    while True:
        try:
            current = snapshot()
            errors = 0
        except Exception as exc:
            errors += 1
            if errors in (3, 12):
                emit(f"READ-ERROR 487 unreadable {errors}x: "
                     f"{type(exc).__name__}")
            time.sleep(args.interval)
            continue

        if previous is None:
            emit(f"WATCHING 487 status={current['status']} "
                 f"leads={current['leads']} sent={current['emails_sent']}")
            previous = current
            time.sleep(args.interval)
            continue

        if current["status"] != previous["status"]:
            emit(f"STATUS 487 {previous['status']} -> {current['status']}")
        if current["leads"] != previous["leads"]:
            emit(f"COHORT 487 leads {previous['leads']} -> {current['leads']}")
        if current["emails_sent"] > previous["emails_sent"]:
            emit(f"SEND 487 emails_sent {previous['emails_sent']} -> "
                 f"{current['emails_sent']}")
        if current["sent_rows"] > previous["sent_rows"]:
            emit(f"SEND 487 queue rows sent {previous['sent_rows']} -> "
                 f"{current['sent_rows']} of {current['queue_rows']}")
        if current["replied"] > previous["replied"]:
            emit(f"REPLY 487 replied {previous['replied']} -> "
                 f"{current['replied']}")
        if current["bounced"] > previous["bounced"]:
            emit(f"BOUNCE 487 bounced {previous['bounced']} -> "
                 f"{current['bounced']}")
        if current["unsubscribed"] > previous["unsubscribed"]:
            emit(f"UNSUB 487 unsubscribed {previous['unsubscribed']} -> "
                 f"{current['unsubscribed']}")

        previous = current
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
