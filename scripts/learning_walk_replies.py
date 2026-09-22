#!/usr/bin/env python3
"""Walk every reply EmailBison holds, for the learning analysis.

    py -3 scripts/learning_walk_replies.py            # walk/resume
    py -3 scripts/learning_walk_replies.py --report

READ-ONLY GETs. Writes one progress file. No message bodies are stored - only
the facts the analysis needs, because a reply body is a real person's words and
this file is not the place for them.

## WHY REPLIES FIRST

The learning question is reply rate and POSITIVE rate by subject, step,
persona, sender, hour, weekday, industry and headcount. Replies are the
numerator and they are cheap: `/api/replies` is cursor-paginated and the whole
history is a few hundred pages. The denominator - every send, with its subject,
step, sender and hour - is a walk of ~186,000 scheduled-email rows across
327/328/352, which is an overnight job.

So this half runs now and is useful on its own: a reply count per campaign and
per lead, and `interested` per reply, which is the only positive signal the
provider carries.

## `interested` IS THE PROVIDER'S FLAG, NOT OUR CLASSIFICATION

It is recorded as-is and never inferred from the body. A reply with
`automated_reply` true is kept and marked, because an out-of-office is a reply
the send produced and excluding it silently would flatter every rate computed
from this file.
"""
import argparse
import collections
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from src.providers import bison, load_env                       # noqa: E402

OUT = os.path.join(ROOT, "work", "learning-replies.jsonl")
STATE = os.path.join(ROOT, "work", "learning-replies.state.json")


def load_state():
    if os.path.exists(STATE):
        with open(STATE, encoding="utf-8") as handle:
            return json.load(handle)
    return {"cursor": None, "pages": 0, "rows": 0, "complete": False}


def save_state(state):
    tmp = f"{STATE}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(state, handle, indent=1)
    os.replace(tmp, STATE)


def trim(row):
    """Only what the analysis needs. No bodies, no names, no addresses."""
    lead = row.get("lead") or {}
    email = str(lead.get("email") or "")
    return {
        "reply_id": row.get("id"),
        "campaign_id": row.get("campaign_id"),
        "lead_id": row.get("lead_id"),
        "domain": email.split("@")[-1].lower() if "@" in email else "",
        "received_at": row.get("date_received") or row.get("created_at"),
        "interested": bool(row.get("interested")),
        "automated": bool(row.get("automated_reply")),
    }


def walk(cap_pages=None):
    load_env()
    state = load_state()
    if state.get("complete"):
        print(f"  already complete: {state['rows']} replies in "
              f"{state['pages']} pages")
        return 0
    handle = open(OUT, "a", encoding="utf-8", newline="\n")
    try:
        while True:
            if cap_pages and state["pages"] >= cap_pages:
                print(f"  stopped at --pages ({state['rows']} rows). Resumable")
                save_state(state)
                return 0
            rows, cursor = bison.fetch_replies(cursor=state["cursor"])
            for row in rows:
                handle.write(json.dumps(trim(row)) + "\n")
            state["rows"] += len(rows)
            state["pages"] += 1
            state["cursor"] = cursor
            if state["pages"] % 10 == 0:
                handle.flush()
                save_state(state)
                print(f"    {state['rows']} replies, {state['pages']} pages",
                      flush=True)
            if not rows or not cursor:
                state["complete"] = True
                save_state(state)
                print(f"\n  COMPLETE: {state['rows']} replies in "
                      f"{state['pages']} pages")
                return 0
    finally:
        handle.flush()
        handle.close()
        save_state(state)


def report():
    if not os.path.exists(OUT):
        print("no replies walked yet")
        return 1
    per_campaign = collections.Counter()
    interested = collections.Counter()
    automated = 0
    total = 0
    seen = set()
    with open(OUT, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if row["reply_id"] in seen:
                continue
            seen.add(row["reply_id"])
            total += 1
            per_campaign[row["campaign_id"]] += 1
            if row["interested"]:
                interested[row["campaign_id"]] += 1
            if row["automated"]:
                automated += 1
    print(f"\n  {total} distinct replies, {automated} automated")
    print(f"  {sum(interested.values())} marked interested by the provider\n")
    print(f"  {'campaign':>10} {'replies':>8} {'interested':>11}")
    for cid, n in per_campaign.most_common(20):
        print(f"  {str(cid):>10} {n:>8} {interested.get(cid, 0):>11}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--pages", type=int, default=None)
    args = ap.parse_args(argv)
    if args.report:
        return report()
    return walk(cap_pages=args.pages)


if __name__ == "__main__":
    raise SystemExit(main())
