#!/usr/bin/env python3
"""Wave 2: each campaign names every attested mailbox of its human.

    py -3 scripts/repoint_to_all_mailboxes.py            # what it would do
    py -3 scripts/repoint_to_all_mailboxes.py --write    # canonical rows
    py -3 scripts/repoint_to_all_mailboxes.py --write --stage   # and provider

OPERATOR, in the CONTINUOUS grant: "When TASK-241 merges at zero new
failures, re-run eligibility, re-point the 8 campaigns to ALL attested
mailboxes of their human at 15 per mailbox per day, and resume pacing at the
new capacity."

TASK-241 merged as 90bd119b + 490f6f58 tonight, so this is that.

    before   8 campaigns x 1 mailbox x 15/day   =   120 first steps a day
    after    159 attested mailboxes x 15/day    = 2,385

## THE HARD STOP IS CHECKED BEFORE THE WRITE, PER MAILBOX

Condition 8: bounce over 2% on any mailbox over 7 days halts the push. Batch
1 named eight mailboxes, each chosen as its human's healthiest, and every one
was under 0.75%. This names a hundred and fifty-nine, and the estate average
being 0.83% says nothing about the worst of them.

So every mailbox is checked against its own lifetime bounce rate here, and
one over the line is left out of the campaign rather than halting the whole
re-point - it is not a stop that has occurred, it is a mailbox that would
cause one.

**A MAILBOX THAT HAS NEVER SENT IS NOT HEALTHY, IT IS UNPROVEN.** Its rate is
0/0. The register already says this about 3941/3930/3919: "never sent, still
in warmup, and therefore NOT PROVEN DELIVERABLE". They are included at the
provider's own 15/day - it is a warmup, not a risk - but they are reported
separately so nobody reads the capacity number as proven throughput.
"""
import argparse
import collections
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import bisonfactory, campaigns, providers, store        # noqa: E402
from src.providers import bison, load_env                        # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: Condition 8. A mailbox at or over this is not named.
BOUNCE_HARD_STOP = 0.02

PER_MAILBOX_DAY = 15


def _jsonl(path):
    out = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def attested_by_human():
    """Every attested email mailbox, grouped by the human who operates it."""
    rows = _jsonl(os.path.join(ROOT, "work", "senders.jsonl"))
    accounts = {r.get("account_id"): r for r in rows
                if r.get("kind") == "email_account"}
    per = collections.defaultdict(list)
    for row in rows:
        if (row.get("kind") == "ownership_attestation"
                and row.get("channel") == "email"):
            account = accounts.get(row.get("account_id"))
            if account:
                per[row.get("sender_id")].append(account)
    return per


def classify(mailbox):
    """(verdict, rate, sent) for one mailbox. Verdict is why it is in or out."""
    state = mailbox.get("provider_state") or {}
    sent = int(state.get("emails_sent_count") or 0)
    bounced = int(state.get("bounced_count") or 0)
    status = str(state.get("status") or "")
    if status and status.lower() != "connected":
        return "not connected", None, sent
    if not sent:
        return "unproven (never sent)", None, 0
    rate = bounced / sent
    if rate >= BOUNCE_HARD_STOP:
        return "over the 2% hard stop", rate, sent
    return "ok", rate, sent


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--stage", action="store_true")
    args = parser.parse_args(argv)

    load_env()
    per = attested_by_human()
    rows = [r for r in campaigns.load()
            if str(r.get("campaign_id", "")).startswith(
                "productive-email-batch1-")]

    print("\nWAVE 2 - every attested mailbox of each human\n")
    plan, totals = {}, collections.Counter()
    for row in rows:
        human = row["campaign_id"].rsplit("-", 1)[-1]
        named, held, unproven = [], [], []
        for mailbox in per.get(human, []):
            verdict, rate, sent = classify(mailbox)
            entry = {"provider_account_id": str(
                mailbox.get("provider_account_id")),
                "account_id": mailbox.get("account_id")}
            if verdict == "ok":
                named.append(entry)
            elif verdict == "unproven (never sent)":
                named.append(entry)
                unproven.append(entry)
            else:
                held.append((entry, verdict, rate))
        plan[row["campaign_id"]] = {"row": row, "named": named,
                                    "held": held, "unproven": unproven}
        totals["named"] += len(named)
        totals["unproven"] += len(unproven)
        totals["held"] += len(held)
        print(f"  {human:10s} attested {len(per.get(human, [])):>3}  "
              f"named {len(named):>3}  unproven {len(unproven):>3}  "
              f"held {len(held):>2}  "
              f"capacity {len(named) * PER_MAILBOX_DAY:>4}/day")
        for entry, verdict, rate in held:
            print(f"      OUT {entry['provider_account_id']}: {verdict}"
                  f"{f' ({rate * 100:.2f}%)' if rate is not None else ''}")

    capacity = totals["named"] * PER_MAILBOX_DAY
    print(f"\n  mailboxes named {totals['named']}  "
          f"(of which unproven {totals['unproven']})  "
          f"held by the hard stop {totals['held']}")
    print(f"  FIRST-STEP CAPACITY {capacity} a day, was 120")
    print(f"  new pacing cap {capacity * 3} enrolled-but-unsent across the "
          f"eight, three days of it")

    if not args.write:
        print("\n  READ-ONLY. Pass --write.")
        return 0

    current = campaigns.load()
    by_slug = {r.get("campaign_id"): i for i, r in enumerate(current)}
    for slug, spec in plan.items():
        index = by_slug.get(slug)
        if index is None:
            continue
        row = current[index]
        row["senders"] = {"email": spec["named"], "linkedin": []}
        row["daily_volume"] = {"email": len(spec["named"]) * PER_MAILBOX_DAY,
                               "linkedin": 0}
        row.setdefault("log", []).append({
            "at": store.now(), "step": "wave2",
            "note": (f"re-pointed to {len(spec['named'])} attested mailboxes "
                     f"after TASK-241 merged; {len(spec['held'])} held by the "
                     f"2% bounce stop")})
        current[index] = row
    campaigns.save(current)
    print(f"\n  canonical rows updated: {len(plan)}")

    if not args.stage:
        print("  Canonical only. Pass --stage to attach them at the provider.")
        return 0

    reason = ("wave 2 re-point - CONTINUOUS grant: all attested mailboxes at "
              "15/mailbox/day once TASK-241 merged")
    with providers.allow_writes(reason):
        for slug in plan:
            try:
                report = bisonfactory.stage(slug, live=True)
            except Exception as exc:                            # noqa: BLE001
                print(f"  {slug}: REFUSED {type(exc).__name__}: "
                      f"{str(exc)[:160]}")
                continue
            did = ", ".join(report.get("did") or [])[:120]
            print(f"  {slug}: {did}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
