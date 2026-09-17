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
    QUEUED      the scheduled-email queue gained or lost rows WITHOUT a send
    TOUCHED     the provider moved the campaign's own `updated_at`
    SCHEDULE-MOVED  the EARLIEST scheduled_date changed - when the first
                prospect hears from us is not the same fact as whether a row
                exists, and 451's moved once overnight
    READ-ERROR  the provider could not be read, after it repeats

WHY `QUEUED` AND `TOUCHED` EXIST, added 2026-09-17, and they are the whole
falsifier for why this campaign has sent nothing.

`scheduled_emails` is a LOOKAHEAD queue, not a receipt. Campaign 451's row
appeared carrying `scheduled_date: 2026-09-13T13:19Z` - nineteen minutes after
its window opened - then moved overnight to 16:24Z on the 14th and fired there
twenty seconds late. So a row appears BEFORE anything is sent, and 487 has
none: the provider has not queued this campaign at all, which is a different
and much more specific fact than "it has not sent".

`updated_at` is the same question asked of the campaign row. Sibling campaigns
352 and 328 - ACTIVE, sharing 487's mailbox - move theirs every few minutes
while the provider works them. 487's has not moved since OUR last write at
2026-09-17T10:45:10Z, through 36 minutes of an open window.

Together they make the standing hypothesis testable tomorrow rather than
next week: if the provider assigns a day's leads at or near the window
opening, then at 07:00-07:30Z on 2026-09-18 - 09:00 Europe/Zagreb - 487
should emit TOUCHED and then QUEUED. **If the window opens and both stay
silent, the hypothesis is dead and must be discarded rather than extended a
day.**

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
        # Carried verbatim and compared for movement, never parsed: a format
        # this system has not seen still reports a touch rather than raising.
        "updated_at": row.get("updated_at"),
        # A SCHEDULED DATE ON THIS PROVIDER IS AN INTENTION, NOT A COMMITMENT.
        # Canary 451's single row moved once overnight - 2026-09-13T13:19Z to
        # 2026-09-14T16:24Z, with nothing staged in between - and then fired
        # twenty seconds late. So the row appearing is one event and the date
        # it carries is another, and only the first was being watched.
        # `min` because the question this answers is "when does the first
        # prospect hear from us", and it is the number an operator plans on.
        "first_scheduled": min(
            [str(e.get("scheduled_date")) for e in queue
             if e.get("scheduled_date")] or ["none"]),
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
        # AFTER the send lines, and only when they did not fire. A queue that
        # grew because something was sent is already reported above; this is
        # the other case - the provider planning work it has not done yet,
        # which is the first observable sign it has looked at this campaign.
        if (current["queue_rows"] != previous["queue_rows"]
                and current["sent_rows"] == previous["sent_rows"]):
            emit(f"QUEUED 487 scheduled rows {previous['queue_rows']} -> "
                 f"{current['queue_rows']} (none sent)")
        if current["updated_at"] != previous["updated_at"]:
            emit(f"TOUCHED 487 updated_at {previous['updated_at']} -> "
                 f"{current['updated_at']} (sent={current['emails_sent']}, "
                 f"queue={current['queue_rows']})")
        if current["first_scheduled"] != previous["first_scheduled"]:
            emit(f"SCHEDULE-MOVED 487 first send "
                 f"{previous['first_scheduled']} -> "
                 f"{current['first_scheduled']}")

        previous = current
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
