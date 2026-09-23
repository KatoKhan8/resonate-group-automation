"""Per-mailbox room TODAY, from the counters - not from a 12,438-page walk.

WHY THIS EXISTS. The forward book census is the only thing that can say what a
mailbox is committed to on a FUTURE day, and it costs 12,438 pages. The
operator asked whether `sending_schedules(day)` could replace it. MEASURED
2026-09-23: it cannot. Both routes return `{campaign_id, emails_being_sent}`
and nothing else - no sender, no mailbox, no per-sender breakdown - and only
three day tokens exist (`today`, `tomorrow`, `day_after_tomorrow`). A
campaign-level total cannot answer a per-MAILBOX question, because the cap is
per mailbox and mailboxes are shared across campaigns.

WHAT CAN BE ANSWERED WITHOUT THE WALK, AND IT IS THE QUESTION A PUSH TODAY
ACTUALLY ASKS. `emails_sent_count` is a LIFETIME counter per mailbox. Diffed
against a sample taken before midnight UTC it gives sends-today, and

    room today = daily_limit - sent_today

is then exact, per mailbox, for 0 extra provider pages. This says nothing
about tomorrow and does not pretend to; `REFUSED IS NOT ROOM` and neither is
`UNKNOWN`, so a mailbox with no baseline sample is reported UNKNOWN and never
as free.

    py -3 scripts/bison_room_today.py
"""

import argparse
import collections
import datetime
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.providers import bison, load_env                      # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLES = os.path.join(ROOT, "work", "bison-mailbox-utilisation.jsonl")


def _counters(sample):
    out = {}
    s = sample["senders"]
    items = s.items() if isinstance(s, dict) else ((x.get("id"), x) for x in s)
    for k, v in items:
        n = v.get("emails_sent_count") if isinstance(v, dict) else v
        if n is not None:
            out[str(k)] = int(n)
    return out


def baseline(now=None):
    """The last successful sample at or before midnight UTC today."""
    now = now or datetime.datetime.now(datetime.timezone.utc)
    cut = now.replace(hour=0, minute=0, second=0, microsecond=0)
    rows = []
    with io.open(SAMPLES, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            if r.get("ok"):
                rows.append(r)
    rows.sort(key=lambda r: r["at"])
    before = [r for r in rows
              if datetime.datetime.fromisoformat(r["at"]) <= cut]
    if not before:
        return None, ("no successful sample before midnight UTC today; "
                      "room today cannot be differenced")
    return before[-1], None


def room(now=None):
    """[{id, email, limit, sent_today, room, status}], and the unknowns."""
    base, why = baseline(now=now)
    if base is None:
        return [], [], why
    b = _counters(base)
    senders = bison.sender_emails()
    if isinstance(senders, tuple):
        senders = senders[0]
    out, unknown = [], []
    for s in senders:
        sid = str(s.get("id"))
        limit = s.get("daily_limit")
        lifetime = s.get("emails_sent_count")
        if sid not in b or limit is None or lifetime is None:
            unknown.append({"id": sid, "email": s.get("email"),
                            "why": "no baseline sample for this mailbox"})
            continue
        sent = int(lifetime) - b[sid]
        out.append({"id": sid, "email": s.get("email"),
                    "limit": int(limit), "sent_today": sent,
                    "room": max(int(limit) - sent, 0),
                    "status": s.get("status")})
    return out, unknown, base["at"]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--connected-only", action="store_true",
                    help="count only mailboxes the provider calls Connected")
    args = ap.parse_args(argv)
    load_env()
    rows, unknown, at = room()
    if not rows:
        print(at)
        return 1
    if args.connected_only:
        rows = [r for r in rows if r.get("status") == "Connected"]
    free = [r for r in rows if r["room"] > 0]
    full = [r for r in rows if r["room"] == 0]
    print(f"baseline sample      {at}")
    print(f"mailboxes measured   {len(rows):,}")
    print(f"  with room today    {len(free):,}")
    print(f"  FULL today         {len(full):,}")
    print(f"  UNKNOWN (no base)  {len(unknown):,}   <- never counted as room")
    print(f"\nTOTAL FREE SLOTS TODAY: {sum(r['room'] for r in rows):,}")
    print(f"emails sent today     : {sum(r['sent_today'] for r in rows):,}")
    st = collections.Counter(r.get("status") for r in rows)
    print(f"\nby provider status: {dict(st)}")
    print("\ntop mailboxes by room:")
    for r in sorted(rows, key=lambda r: -r["room"])[:10]:
        print(f"  {r['id']:>6}  {str(r['email'])[:38]:<38} "
              f"{r['sent_today']:>3}/{r['limit']:<3} room {r['room']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
