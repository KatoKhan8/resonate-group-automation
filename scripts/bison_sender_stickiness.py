#!/usr/bin/env python3
"""Does EmailBison keep one sender per lead across a sequence? Measured.

    py -3 scripts/bison_sender_stickiness.py
    py -3 scripts/bison_sender_stickiness.py --campaign 352 --pages 40

READ-ONLY. GETs on `/campaigns/{id}/scheduled-emails` and nothing else. It
writes no state and attaches no sender.

## The question, and why it is the most expensive open one

`executionguard._sender_for` refuses any campaign whose canonical row names
more than one sender: "a guarded action is attributed to exactly one". The
failure it guards against is concrete - a prospect hearing from Human A in the
opener and Human B in the follow-up, because the provider rotated mailboxes
and nothing recorded which.

Nobody knew whether this provider actually does that. So a campaign is pinned
to ONE inbox while the estate carries thousands of emails a day of measured
idle capacity (`docs/REAL-AVAILABLE-CAPACITY-2026-09-17.md`).

Our own campaigns cannot answer it: 481 holds two senders and has never sent,
485 and 487 hold one each. The client's own campaigns can - 327, 328 and 352
each hold **59 senders** and have sent 173,558 emails between them.

## Why `bison.scheduled_emails` is not used here

That function walks every page and REFUSES a queue too large to walk, which is
correct for "what is about to go out" and useless here: campaign 352's queue
reports `meta.total: 48,759`. This reads a bounded number of pages, counts
nothing as capacity, and looks at exactly one thing.

## What it measures, and what it cannot

For every lead appearing more than once in the sampled pages, at more than one
`sequence_step_id`: how many distinct `sender_email.id` values its rows carry.

    one  -> the provider kept that lead's sender across steps
    more -> the provider rotated, and the arity rule is load-bearing

**This is OBSERVED, never DOCUMENTED.** It is behaviour in this workspace on
one day, not a contract the vendor offers, and it says nothing about HOW the
first sender is chosen. It also cannot see across an already-sent step and a
future one - the queue holds scheduled rows.

A result here does not by itself license attaching a second inbox to a
campaign. It licenses asking the next question.
"""

import argparse
import collections
import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.providers import bison, load_env, ok, request  # noqa: E402

DEFAULT_CAMPAIGNS = (328, 352, 327)


def h(value):
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:10]


def sample(campaign_id, pages):
    """Rows per lead over a bounded page walk. Raises on an unreadable page."""
    by_lead = collections.defaultdict(list)
    read = 0
    meta = {}
    for page in range(1, pages + 1):
        url = bison.query(
            f"{bison.base()}/campaigns/{campaign_id}/scheduled-emails",
            {"page": page})
        status, data = request("GET", url, bison.headers())
        if not ok(status):
            if page == 1:
                raise RuntimeError(
                    f"campaign {campaign_id} page 1 -> {status}; a sample of "
                    f"zero pages is not a sample of zero rotations")
            break
        meta = meta or ((data or {}).get("meta") or {})
        rows = (data or {}).get("data") or []
        if not rows:
            break
        read += 1
        for row in rows:
            lead = row.get("lead") or {}
            key = h(lead.get("email") if isinstance(lead, dict) else lead)
            sender = (row.get("sender_email") or {}).get("id")
            by_lead[key].append({"step": row.get("sequence_step_id"),
                                 "sender": sender,
                                 "at": row.get("scheduled_date")})
    return by_lead, read, meta


def verdict(by_lead):
    multi = {k: v for k, v in by_lead.items() if len(v) > 1}
    cross_step = {k: v for k, v in multi.items()
                  if len({e["step"] for e in v}) > 1}
    rotated = {k: v for k, v in cross_step.items()
               if len({e["sender"] for e in v}) > 1}
    return {"leads_sampled": len(by_lead),
            "leads_with_several_rows": len(multi),
            "leads_across_several_steps": len(cross_step),
            "leads_that_ROTATED_sender": len(rotated),
            "examples": {k: sorted(v, key=lambda e: str(e["at"]))
                         for k, v in list(cross_step.items())[:3]},
            "rotations": {k: v for k, v in list(rotated.items())[:3]}}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--campaign", action="append", type=int,
                        dest="campaigns")
    parser.add_argument("--pages", type=int, default=20)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    load_env(os.path.join(ROOT, "config", ".env"))
    report = {}
    for campaign_id in (args.campaigns or list(DEFAULT_CAMPAIGNS)):
        senders = bison.campaign_senders(campaign_id) or []
        try:
            by_lead, read, meta = sample(campaign_id, args.pages)
        except Exception as exc:                  # noqa: BLE001 - classified
            report[campaign_id] = {"error": f"{type(exc).__name__}: {exc}"}
            continue
        entry = verdict(by_lead)
        entry.update(senders_attached=len(senders), pages_read=read,
                     queue_total=meta.get("total"))
        report[campaign_id] = entry

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True, default=str))
        return 0

    total_cross = total_rotated = 0
    for campaign_id, entry in report.items():
        print(f"=== campaign {campaign_id} ===")
        if entry.get("error"):
            print(f"  UNREADABLE: {entry['error']}")
            continue
        print(f"  senders attached            {entry['senders_attached']}")
        print(f"  queue total (provider meta) {entry['queue_total']}")
        print(f"  pages read / leads sampled  {entry['pages_read']} / "
              f"{entry['leads_sampled']}")
        print(f"  leads across several STEPS  "
              f"{entry['leads_across_several_steps']}")
        print(f"  ... that ROTATED sender     "
              f"{entry['leads_that_ROTATED_sender']}")
        for key, rows in (entry.get("examples") or {}).items():
            print(f"    {key}: " + ", ".join(
                f"step {r['step']} sender {r['sender']} at {str(r['at'])[:16]}"
                for r in rows))
        total_cross += entry["leads_across_several_steps"]
        total_rotated += entry["leads_that_ROTATED_sender"]

    print(f"\nACROSS ALL SAMPLED CAMPAIGNS: {total_cross} leads seen at more "
          f"than one step, {total_rotated} rotated sender.")
    if total_cross and not total_rotated:
        print("  OBSERVED: this provider keeps one sender per lead across "
              "steps, on this")
        print("  workspace, on this day, at this sample size. NOT documented "
              "and NOT a")
        print("  contract - and it says nothing about how the FIRST sender is "
              "chosen.")
    elif total_rotated:
        print("  OBSERVED: the provider DOES rotate senders within a lead's "
              "sequence.")
        print("  The arity rule is load-bearing and must not be relaxed.")
    else:
        print("  INCONCLUSIVE: no lead was seen at more than one step. "
              "Sample more pages.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
