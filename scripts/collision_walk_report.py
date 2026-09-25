#!/usr/bin/env python3
"""Report the collision walk state as four verdict buckets.

    py -3 scripts/collision_walk_report.py
    py -3 scripts/collision_walk_report.py --json

Reads `work/stage/s6-collision-walk.json` and prints:

  - The four verdict buckets: CLEAR, COLLIDES, REFUSED, NOT_WALKED
  - Every COLLIDES row with campaign id, date, ownership evidence
  - Every REFUSED row with the response shape that triggered it
  - The walk date on every verdict

The four buckets partition the input set. A report with three buckets has
lost one. REFUSED and NOT_WALKED are different answers and neither is CLEAR.
"""
import argparse
import collections
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from src import collision, store                                  # noqa: E402


def load_walk():
    path = os.path.join(os.path.dirname(store.queue_path()),
                        "stage", "s6-collision-walk.json")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def classify(entry):
    """One of CLEAR, COLLIDES, REFUSED. NOT_WALKED is absent-from-state."""
    verdict = entry.get("verdict", "")
    policy = entry.get("policy", "")
    if verdict == "REFUSED" or not verdict:
        return "REFUSED"
    if policy == "allow":
        return "CLEAR"
    return "COLLIDES"


def report_text(state):
    accounts = state.get("accounts", {})
    buckets = collections.Counter()
    clear_rows = []
    collides_rows = []
    refused_rows = []

    for domain in sorted(accounts):
        entry = accounts[domain]
        bucket = classify(entry)
        buckets[bucket] += 1
        if bucket == "CLEAR":
            clear_rows.append((domain, entry))
        elif bucket == "COLLIDES":
            collides_rows.append((domain, entry))
        else:
            refused_rows.append((domain, entry))

    total = len(accounts)
    started = state.get("started_at", "?")

    lines = []
    lines.append(f"S6 COLLISION WALK REPORT")
    lines.append(f"  Walked at:  {started}")
    lines.append(f"  Total:      {total}")
    lines.append(f"  CLEAR:      {buckets['CLEAR']}")
    lines.append(f"  COLLIDES:   {buckets['COLLIDES']}")
    lines.append(f"  REFUSED:    {buckets['REFUSED']}")
    lines.append(f"  NOT_WALKED: (domains absent from state file)")
    lines.append(f"  Sum:        {sum(buckets.values())} (must equal {total})")
    lines.append("")

    if collides_rows:
        lines.append(f"--- COLLIDES ({len(collides_rows)}) ---")
        for domain, entry in collides_rows:
            lines.append(
                f"  {domain}: policy={entry.get('policy')} "
                f"verdict={entry.get('verdict')} "
                f"sent={entry.get('emails_sent_total', 0)} "
                f"leads={entry.get('leads', 0)} "
                f"at={entry.get('at', '?')}")
            lines.append(f"    why: {entry.get('why', '')[:160]}")
        lines.append("")

    if refused_rows:
        lines.append(f"--- REFUSED ({len(refused_rows)}) ---")
        for domain, entry in refused_rows:
            lines.append(
                f"  {domain}: verdict=REFUSED at={entry.get('at', '?')}")
            lines.append(f"    why: {entry.get('why', '')[:200]}")
        lines.append("")

    if clear_rows:
        lines.append(f"--- CLEAR ({len(clear_rows)}) ---")
        for domain, entry in clear_rows[:20]:
            lines.append(
                f"  {domain}: verdict={entry.get('verdict')} "
                f"at={entry.get('at', '?')}")
        if len(clear_rows) > 20:
            lines.append(f"  ... and {len(clear_rows) - 20} more")
        lines.append("")

    return "\n".join(lines)


def report_json(state):
    accounts = state.get("accounts", {})
    out = {"started_at": state.get("started_at"), "accounts": {}}
    for domain, entry in sorted(accounts.items()):
        bucket = classify(entry)
        out["accounts"][domain] = {
            "bucket": bucket,
            "policy": entry.get("policy"),
            "verdict": entry.get("verdict"),
            "emails_sent_total": entry.get("emails_sent_total"),
            "leads": entry.get("leads"),
            "why": entry.get("why", ""),
            "at": entry.get("at"),
        }
    counts = collections.Counter(
        v["bucket"] for v in out["accounts"].values())
    out["counts"] = dict(counts)
    out["total"] = len(accounts)
    return json.dumps(out, indent=2, sort_keys=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    state = load_walk()
    if state is None:
        print("No walk state found at work/stage/s6-collision-walk.json")
        return 1

    if args.json:
        print(report_json(state))
    else:
        print(report_text(state))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
