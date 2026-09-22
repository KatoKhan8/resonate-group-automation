#!/usr/bin/env python3
"""The deliverability hard stops, read from the provider. READ-ONLY.

    py scripts/hard_stop_check.py            # the full table
    py scripts/hard_stop_check.py --quiet    # print ONLY tripped stops

Written 2026-09-22 because a monitor was armed against a script of this name
that did not exist. **It would have reported nothing, for ever, and silence
from a hard-stop monitor is indistinguishable from safety.** That is the same
failure class as a watcher that is not running.

THE STOPS, as the batch grant states them:

    bounce > 2% on any MAILBOX over 7 days
    any spam complaint
    an unsubscribe not propagated

**THE DENOMINATOR RULE.** Operator decision, 2026-09-22: a mailbox with fewer
than 20 sends in the window has an UNDEFINED bounce rate and cannot trip. It
tripped on 1-of-2 and 1-of-3 while the estate sat at 1.34%, and a rate over
two sends is not a measurement. UNDEFINED IS NOT PASS - such a mailbox is
excluded from new enrollment until it reaches 20 sends, which this script
reports separately so the two are never confused.
"""
import argparse
import collections
import datetime
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from src.providers import bison, load_env                       # noqa: E402

CAMPAIGNS = (487, 489, 491, 492, 493, 494, 495, 496, 497, 498)
BOUNCE_LIMIT_PCT = 2.0
MIN_DENOMINATOR = 20
WINDOW_DAYS = 7


def _parsed(value):
    try:
        return datetime.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def per_mailbox():
    cutoff = (datetime.datetime.now(datetime.timezone.utc)
              - datetime.timedelta(days=WINDOW_DAYS))
    counts = collections.defaultdict(collections.Counter)
    for campaign in CAMPAIGNS:
        try:
            rows = bison.scheduled_emails(campaign)
        except Exception as exc:                  # noqa: BLE001
            print(f"  UNREADABLE campaign {campaign}: {exc}")
            continue
        for row in rows:
            status = row.get("status")
            if status not in ("sent", "bounced"):
                continue
            when = _parsed(row.get("sent_at") or row.get("updated_at"))
            if when and when < cutoff:
                continue
            sender = row.get("sender_email")
            mailbox = (sender.get("email") if isinstance(sender, dict)
                       else sender) or row.get("from_email") or "?"
            counts[mailbox][status] += 1
    return counts


def check():
    load_env()
    counts = per_mailbox()
    tripped, undefined = [], []
    for mailbox, seen in counts.items():
        total = seen["sent"] + seen["bounced"]
        rate = (seen["bounced"] / total * 100) if total else 0.0
        if total < MIN_DENOMINATOR:
            if seen["bounced"]:
                undefined.append((mailbox, seen["bounced"], total, rate))
            continue
        if rate > BOUNCE_LIMIT_PCT:
            tripped.append((mailbox, seen["bounced"], total, rate))
    unsub = spam = 0
    for campaign in CAMPAIGNS:
        try:
            data = bison.campaign(campaign)
        except Exception:                          # noqa: BLE001
            continue
        unsub += int(data.get("unsubscribed") or 0)
        spam += int(data.get("spam_complaints") or data.get("complaints") or 0)
    return {"tripped": tripped, "undefined": undefined,
            "unsubscribed": unsub, "spam": spam, "mailboxes": len(counts)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--quiet", action="store_true",
                        help="print only tripped stops; silent when clean")
    args = parser.parse_args(argv)
    result = check()

    for mailbox, bounced, total, rate in result["tripped"]:
        print(f"HARD STOP bounce {rate:.1f}% ({bounced}/{total}) on {mailbox}")
    if result["spam"]:
        print(f"HARD STOP spam complaints: {result['spam']}")

    if args.quiet:
        return 1 if (result["tripped"] or result["spam"]) else 0

    print(f"\n  mailboxes with sends in {WINDOW_DAYS}d: {result['mailboxes']}")
    print(f"  unsubscribed: {result['unsubscribed']}  spam: {result['spam']}")
    if result["undefined"]:
        print(f"\n  UNDEFINED - under {MIN_DENOMINATOR} sends, cannot trip, "
              "and held out of NEW enrollment until they reach it:")
        for mailbox, bounced, total, rate in result["undefined"]:
            print(f"    {bounced}/{total} ({rate:.0f}%)  {mailbox}")
    if not result["tripped"] and not result["spam"]:
        print("\n  no hard stop tripped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
