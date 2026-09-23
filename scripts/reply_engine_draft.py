#!/usr/bin/env python3
"""Draft a reply for every real inbound reply. Sends nothing, ever.

    py -3 scripts/reply_engine_draft.py --since 2026-09-22 --limit 10

READ-ONLY at the provider and write-free everywhere else except
`work/reply-drafts.jsonl`, which is the log the operator asked for. There is
no `--live`: `src.replyengine.send` refuses by construction and this script
never calls it.

## WHY IT EXISTS SEPARATELY FROM THE WATCHER

The reply watcher's job is to STOP people, and that path is now live and
narrow (`inbound.STOP_ROUTES`). Drafting is a different job with a different
blast radius, so it runs as a command a person invokes rather than inside the
loop that protects prospects. When the engine is trusted the two can meet;
they should not meet before then.
"""
import argparse
import datetime
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import replies, replyengine                            # noqa: E402
from src.providers import bison, load_env                       # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DRAFTS = os.path.join(ROOT, "work", "reply-drafts.jsonl")


def inbound_rows(since, cap_pages=40):
    """Real reply rows from the provider, newest first, back to `since`."""
    out, cursor, pages = [], None, 0
    while pages < cap_pages:
        page, cursor = bison.fetch_replies(cursor=cursor, per_page=100)
        pages += 1
        if not page:
            break
        stop = False
        for row in page:
            stamp = row.get("date_received") or row.get("created_at")
            at = None
            if stamp:
                at = datetime.datetime.fromisoformat(
                    str(stamp).replace("Z", "+00:00"))
            if at and at < since:
                stop = True
                continue
            out.append((at, row))
        if stop or not cursor:
            break
    return out


def as_event(row, kind):
    """A provider row as the neutral shape `replyengine.draft` reads."""
    lead = row.get("lead") or {}
    return {
        "provider": "emailbison",
        "provider_event_id": "emailbison:%s" % row.get("id"),
        "channel": "email",
        "contact": lead.get("email"),
        "text": row.get("text_body") or "",
        "subject": row.get("subject"),
        "campaign": row.get("campaign_id"),
        "automated": bool(row.get("automated_reply")),
        "kind": kind,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--since", default="2026-09-22")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--tz-offset", type=float, default=None,
                        help="recipient's UTC offset. Omitted means UNKNOWN, "
                             "which the engine treats as outside business "
                             "hours - a guessed timezone is worse than none.")
    args = parser.parse_args(argv)

    load_env(os.path.join(ROOT, "config", ".env"))
    since = datetime.datetime.fromisoformat(args.since).replace(
        tzinfo=datetime.timezone.utc)

    print(f"\nREPLY ENGINE - DRAFT ONLY.  SENDING_ENABLED="
          f"{replyengine.SENDING_ENABLED}")
    print(f"register present: {replyengine.have_register()}  "
          f"({os.path.relpath(replyengine.REGISTER_PATH, ROOT)})\n")

    rows = inbound_rows(since)
    drafted, counts = [], {}
    for at, row in sorted(rows, key=lambda r: r[0] or since):
        kind = bison.classify_reply_row(row)
        if kind != "reply":
            counts[f"[{kind}]"] = counts.get(f"[{kind}]", 0) + 1
            continue
        event = as_event(row, kind)
        # The SUBJECT is passed deliberately: it is where an autoresponder
        # announces itself in every language, and the body is where it
        # fooled the classifier into REFERRAL on 2026-09-22.
        verdict = replies.classify(event["text"],
                                   subject=event.get("subject"))
        record = replyengine.draft(event, verdict,
                                   tz_offset_hours=args.tz_offset)
        record["at_inbound"] = at.strftime("%Y-%m-%dT%H:%M:%SZ") if at else None
        drafted.append(record)
        counts[record["action"]] = counts.get(record["action"], 0) + 1
        if len(drafted) >= args.limit:
            break

    os.makedirs(os.path.dirname(DRAFTS), exist_ok=True)
    with open(DRAFTS, "a", encoding="utf-8") as handle:
        for record in drafted:
            handle.write(json.dumps(record, default=str) + "\n")

    for i, record in enumerate(drafted, 1):
        print(f"--- {i}. {record['at_inbound']}  campaign "
              f"{record.get('provider_event_id')}")
        print(f"    class      {record['classification']} "
              f"({record['confidence']})")
        print(f"    action     {record['action']}  -  {record['why']}")
        body = re.sub(r"\s+", " ", record["inbound"])[:110]
        print(f"    inbound    {body!r}")
        if record.get("ticket"):
            print(f"    ticket     {record['ticket']}")
        print(f"    reply      {record['reply']!r}")
        print()

    print("counts:", json.dumps(counts))
    print(f"{len(drafted)} draft(s) appended to "
          f"{os.path.relpath(DRAFTS, ROOT)}")
    print("\nNOTHING WAS SENT. replyengine.send refuses while "
          "SENDING_ENABLED is False.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
