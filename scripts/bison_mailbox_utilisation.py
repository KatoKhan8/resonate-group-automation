#!/usr/bin/env python3
"""What the EMAIL mailbox estate is actually sending, sampled over time.

## The question this answers

`docs/PRODUCTION-HANDOFF-2026-09-17.md` says campaign 487's real capacity is
"NOT 15/day" because sender 2736 also serves three other ACTIVE campaigns, so
487's share of a per-MAILBOX limit is a fraction of 15 and "today it is zero".

That is a hypothesis about a shared limit. It has never been MEASURED. The
provider exposes `emails_sent_count` per sender email - a LIFETIME counter -
and a lifetime counter says nothing about today until you difference it.

So this differences it. Two samples of the same mailbox an interval apart give
sends-in-that-interval, and a day of samples gives sends-today. That turns
"the mailbox is probably saturated" into a number, and it makes the falsifier
concrete: **if 2736's counter does not move all day while the sibling
campaigns' counters do, then 487 is not starved by a shared mailbox limit and
the explanation for its zero lies somewhere else.**

## Why the whole estate rather than one mailbox

One paged read returns all 225. The marginal cost of recording every mailbox
is zero and the marginal value is P3: "real available capacity" for the estate
is exactly this table, and no other tool in the repository produces it.

## UNKNOWN is never 0

A sample that fails is recorded as an ERROR row and never as zeros. A delta is
only computed between two SUCCESSFUL samples of the same sender, and a sender
that appears in the later sample but not the earlier one has an UNKNOWN delta,
not a delta equal to its lifetime count.

`sender_emails` raises `PartialInventory` rather than returning a short list,
so a truncated page cannot be recorded as "senders that stopped sending".

## PII

A sender inbox is a real person at the client. The id and the numbers are what
capacity planning needs; the address and the display name are hashed. The
output goes to `work/`, which is gitignored.

READ-ONLY. Writes nothing to any provider.
"""

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.providers import bison, load_env  # noqa: E402

OUT = os.path.join(ROOT, "work", "bison-mailbox-utilisation.jsonl")

# The counters worth differencing. `emails_sent_count` is the one the capacity
# question turns on; the other two are recorded because a mailbox whose bounce
# count climbs while its send count climbs is the containment signal, and
# finding that out later from a single snapshot is impossible.
COUNTERS = ("emails_sent_count", "bounced_count", "total_leads_contacted_count")


def h(value):
    text = " ".join(str(value or "").split()).lower()
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12] if text else None


def sample():
    """One reading of every mailbox, or an ERROR row. Never a partial one."""
    at = datetime.now(timezone.utc).isoformat()
    try:
        rows, meta = bison.sender_emails()
    except Exception as exc:                      # noqa: BLE001 - classified
        return {"at": at, "ok": False, "error": f"{type(exc).__name__}: {exc}"}
    senders = {}
    for row in rows:
        ident = row.get("id")
        if ident is None:
            continue
        entry = {"email_h": h(row.get("email")), "name_h": h(row.get("name")),
                 "daily_limit": row.get("daily_limit"),
                 "status": row.get("status"),
                 "warmup_enabled": row.get("warmup_enabled")}
        for key in COUNTERS:
            entry[key] = row.get(key)
        senders[str(ident)] = entry
    return {"at": at, "ok": True, "total": meta.get("total"),
            "read": len(rows), "senders": senders}


def deltas(earlier, later):
    """Per-sender movement between two SUCCESSFUL samples.

    A sender missing from either side is reported as UNKNOWN rather than as a
    zero: "we did not see it" and "it did not send" are the two answers this
    repository exists to keep apart.
    """
    if not (earlier.get("ok") and later.get("ok")):
        return {}
    out = {}
    for ident, now in (later.get("senders") or {}).items():
        was = (earlier.get("senders") or {}).get(ident)
        if was is None:
            out[ident] = {key: "UNKNOWN" for key in COUNTERS}
            continue
        row = {}
        for key in COUNTERS:
            a, b = was.get(key), now.get(key)
            row[key] = (b - a) if isinstance(a, int) and isinstance(b, int) \
                else "UNKNOWN"
        out[ident] = row
    return out


def append(record, path=OUT):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def load(path=OUT):
    if not os.path.exists(path):
        return []
    rows = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def report(rows, watch_ids=()):
    """Movement between the first and last successful samples on file."""
    good = [r for r in rows if r.get("ok")]
    print(f"samples on file   : {len(rows)} ({len(good)} ok, "
          f"{len(rows) - len(good)} error)")
    if len(good) < 2:
        print("movement          : UNKNOWN - needs two successful samples")
        return
    first, last = good[0], good[-1]
    print(f"window            : {first['at']} -> {last['at']}")
    moved = deltas(first, last)
    sending = {i: d for i, d in moved.items()
               if isinstance(d.get("emails_sent_count"), int)
               and d["emails_sent_count"] > 0}
    print(f"mailboxes sending : {len(sending)} of {len(moved)}")
    total = sum(d["emails_sent_count"] for d in sending.values())
    print(f"emails in window  : {total}")
    for ident, delta in sorted(sending.items(),
                               key=lambda kv: -kv[1]["emails_sent_count"])[:10]:
        limit = (last["senders"].get(ident) or {}).get("daily_limit")
        print(f"  sender {ident:>5}      +{delta['emails_sent_count']} "
              f"(daily_limit {limit}, bounced +{delta['bounced_count']})")
    for ident in watch_ids:
        ident = str(ident)
        delta = moved.get(ident)
        row = (last.get("senders") or {}).get(ident) or {}
        if delta is None:
            print(f"  WATCH {ident:>5}      UNKNOWN - not in the later sample")
            continue
        print(f"  WATCH {ident:>5}      +{delta['emails_sent_count']} in window"
              f", lifetime {row.get('emails_sent_count')}, "
              f"daily_limit {row.get('daily_limit')}, "
              f"status {row.get('status')}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--interval", type=int, default=300,
                        help="seconds between samples when watching")
    parser.add_argument("--samples", type=int, default=1,
                        help="how many samples to take before exiting")
    parser.add_argument("--report", action="store_true",
                        help="report movement on the existing file and exit")
    parser.add_argument("--watch-id", action="append", default=[],
                        help="sender id to report explicitly, repeatable")
    args = parser.parse_args(argv)

    watch = args.watch_id or ["2736", "3941", "3930", "3919"]
    if args.report:
        report(load(), watch)
        return 0

    load_env()
    for n in range(args.samples):
        record = sample()
        append(record)
        if record.get("ok"):
            print(f"[{record['at']}] SAMPLE ok  read={record['read']} "
                  f"total={record['total']}", flush=True)
        else:
            print(f"[{record['at']}] SAMPLE ERROR {record['error']}",
                  flush=True)
        if n + 1 < args.samples:
            time.sleep(args.interval)
    report(load(), watch)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
