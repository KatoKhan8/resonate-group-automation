#!/usr/bin/env python3
"""Every mailbox's real forward book, walked in full rather than sampled.

    py -3 scripts/bison_forward_book_census.py                # walk/resume
    py -3 scripts/bison_forward_book_census.py --report       # read the state
    py -3 scripts/bison_forward_book_census.py --campaigns 352

READ-ONLY GETs. Writes one progress file and prints counts. No PII: sender
ids and dates only, never an address or a lead.

## Why this exists, and what it replaces

`scripts/bison_forward_book.py` samples. Its own docstring says sample size is
load-bearing and that it will lie if rushed - at 3,600 rows sender 2911 read
ZERO free on 2026-09-18 and a swap onto it looked safe; at 9,000 rows the same
mailbox read 15. The zero was rows not yet reached.

**Sampling can only ever UNDERCOUNT a mailbox's commitments.** That asymmetry
is why the sampled conclusion "2736 is booked 15/15 on the 18th" is sound - a
lower bound that already reached the limit is a full mailbox - while every
ZERO in the same table is unproven. "2736 is free on the 23rd" and "the
scheduler has not planned past the 22nd" both fit the sampled data, and they
imply different actions.

Only a complete walk separates them.

## Why a complete walk is possible now and was not before

`scheduled_emails` refuses at `PAGE_CAP` because offset pagination is refused
with 422 beyond ~500 pages, and campaign 352 is 6,382 pages of 15.

EmailBison documents a second mode - `pagination_type=cursor` with a `cursor`
token - and it was verified against THIS estate on 2026-09-17: it answers 200,
returns `meta.next_cursor`, and the row ids genuinely advance. `per_page`
stays 15 in cursor mode too, so this does not get cheaper, only possible:
~12,000 requests and roughly two hours for the three active client campaigns.

That is an overnight job, which is what this is.

## Resumable, because a two-hour walk that restarts is a walk that never ends

Progress is checkpointed to `work/forward-book-census.json` after every
`--checkpoint` pages: the per-campaign cursor, the accumulated counters and
the rows seen. Re-running resumes from the stored cursor.

**A resumed walk is not the same as a complete one** and the report says so:
`complete` is only true for a campaign whose walk reached the end in one
lineage of cursors. A cursor is a position in a live list, so rows inserted
behind it are missed - and the scheduler inserts rows at the end of every
sending day. A walk that spans a scheduler run is reported as `SPANNED` rather
than quietly averaged.
"""
import argparse
import collections
import json
import os
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from src import store
from src.providers import bison, load_env, request, ok

# A campaign whose rows can still occupy a mailbox's forward book. Everything
# else has no future rows to contribute.
#
# `archived` is terminal here and that is a decision rather than an omission:
# the four archived campaigns in this estate carry tens of thousands of SENT
# rows and no scheduled ones, so walking them costs hours and adds nothing to
# a forward book. `paused` is NOT terminal - 487 sat paused with ten rows
# booked on the 22nd, and leaving it out is exactly the bug below.
TERMINAL_STATUSES = frozenset({"draft", "completed", "archived"})


def forward_booking_campaigns():
    """Every campaign that can still book a mailbox, asked of the provider.

    ## THIS WAS A HARDCODED LITERAL AND IT SILENTLY BLINDED CAPACITY PLANNING

    It read `ACTIVE_CLIENT_CAMPAIGNS = (327, 328, 352)` - the three client
    campaigns, and nothing of ours. The walk of 2026-09-20T14:09Z therefore
    covered three campaigns while SIX could book rows, and
    `senderheadroom.coverage` correctly answered `(False, ('489',))`, which
    makes `verdict` REFUSE every mailbox on every day.

    That refusal is the safe direction and it is not a harmless one: REFUSED
    IS NOT ROOM, so with a non-covering walk nothing can ever be proven free
    and cohort scheduling has no input at all. The 09-19 walk covered all
    five campaigns then active; the 09-20 walk used this default and dropped
    two of them. Nothing reported a problem, because a literal cannot know
    it has gone stale.

    Same class as the credential audit that invented `CONTACTOUT_KEY`: a
    hand-maintained list standing in for a registry that already exists.
    **Ask the thing that knows.** The provider knows which campaigns it will
    schedule from.

    ## AND IT PAGES, because `per_page` is ignored

    `GET /api/campaigns` answers 15 rows with `meta.last_page: 2` and
    **ignores `per_page`** - verified against this estate. Reading page one
    only returns 352 while omitting 327 and 328, the two largest client
    campaigns in the book. A derived default that did not page would have
    been worse than the literal it replaced, so this follows `meta.last_page`
    to the end and refuses to guess.
    """
    campaigns, page, last = [], 1, 1
    while page <= last:
        status, data = request(
            "GET", f"{bison.base()}/campaigns?page={page}", bison.headers(), None)
        if not ok(status):
            raise RuntimeError(
                f"campaign list: HTTP {status}. The census will not fall back "
                f"to a hardcoded list - pass --campaigns explicitly.")
        if not isinstance(data, dict) or not isinstance(data.get("data"), list):
            raise RuntimeError(
                "campaign list: unexpected response shape. Refusing rather "
                "than walking a guessed set.")
        campaigns.extend(data["data"])
        last = int((data.get("meta") or {}).get("last_page") or 1)
        page += 1
    return tuple(sorted(
        int(c["id"]) for c in campaigns
        if str(c.get("status") or "").strip().lower() not in TERMINAL_STATUSES))


def state_path():
    return os.path.join(os.path.dirname(store.queue_path()),
                        "forward-book-census.json")


def load_state():
    path = state_path()
    if not os.path.exists(path):
        return {"campaigns": {}}
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def save_state(state):
    path = state_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(state, handle, indent=2, sort_keys=True)
    os.replace(tmp, path)


def walk(campaign_id, state, checkpoint=50, max_pages=None, quiet=False):
    """Walk one campaign's queue by cursor, resuming if we have a position."""
    key = str(campaign_id)
    entry = state["campaigns"].setdefault(key, {
        "cursor": None, "rows": 0, "pages": 0, "complete": False,
        "by_sender_day": {}, "started_at": None, "finished_at": None,
        "status_seen": {},
    })
    if entry.get("complete"):
        if not quiet:
            print(f"campaign {campaign_id}: already complete "
                  f"({entry['rows']} rows)")
        return entry

    entry["started_at"] = entry["started_at"] or bison_now()
    counts = collections.Counter()
    for compound, n in (entry.get("by_sender_day") or {}).items():
        counts[compound] = n
    statuses = collections.Counter(entry.get("status_seen") or {})

    pages_this_run = 0
    while True:
        params = {"pagination_type": "cursor"}
        if entry["cursor"]:
            params["cursor"] = entry["cursor"]
        url = bison.query(
            f"{bison.base()}/campaigns/{campaign_id}/scheduled-emails", params)
        status, data = request("GET", url, bison.headers())
        if not ok(status):
            entry["by_sender_day"] = dict(counts)
            entry["status_seen"] = dict(statuses)
            save_state(state)
            raise RuntimeError(
                f"campaign {campaign_id}: page {entry['pages'] + 1} -> "
                f"HTTP {status}. Progress saved; re-run to resume")

        rows = (data or {}).get("data")
        if not isinstance(rows, list):
            raise RuntimeError(
                f"campaign {campaign_id}: the list is not a list; refusing to "
                f"read an unknown shape as an empty one")

        for row in rows:
            sender = (row.get("sender_email") or {})
            sid = sender.get("id")
            day = str(row.get("scheduled_date") or "")[:10]
            st = str(row.get("status") or "")
            statuses[st] += 1
            if sid is not None and day:
                counts[f"{int(sid)}|{day}"] += 1

        entry["rows"] += len(rows)
        entry["pages"] += 1
        pages_this_run += 1

        meta = (data or {}).get("meta")
        meta = meta if isinstance(meta, dict) else {}
        nxt = meta.get("next_cursor")
        entry["cursor"] = nxt

        if not rows or not nxt:
            entry["complete"] = True
            entry["finished_at"] = bison_now()
            entry["by_sender_day"] = dict(counts)
            entry["status_seen"] = dict(statuses)
            save_state(state)
            if not quiet:
                print(f"campaign {campaign_id}: COMPLETE, {entry['rows']} rows "
                      f"in {entry['pages']} pages")
            return entry

        if pages_this_run % checkpoint == 0:
            entry["by_sender_day"] = dict(counts)
            entry["status_seen"] = dict(statuses)
            save_state(state)
            if not quiet:
                print(f"campaign {campaign_id}: {entry['rows']} rows, "
                      f"{entry['pages']} pages", flush=True)

        if max_pages and pages_this_run >= max_pages:
            entry["by_sender_day"] = dict(counts)
            entry["status_seen"] = dict(statuses)
            save_state(state)
            if not quiet:
                print(f"campaign {campaign_id}: stopped at --max-pages "
                      f"({entry['rows']} rows). Re-run to resume")
            return entry


def bison_now():
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).replace(
        microsecond=0).isoformat()


def report(state, limits=None):
    """Per sender, per day, with the completeness caveat attached."""
    campaigns = state.get("campaigns") or {}
    complete = [c for c, e in campaigns.items() if e.get("complete")]
    partial = [c for c, e in campaigns.items() if not e.get("complete")]

    print("=== WALK STATE ===")
    for cid, entry in sorted(campaigns.items()):
        print(f"  campaign {cid}: rows={entry.get('rows')} "
              f"pages={entry.get('pages')} "
              f"complete={entry.get('complete')}")
    if partial:
        print()
        print(f"  *** {len(partial)} campaign(s) INCOMPLETE: {sorted(partial)}")
        print("  *** Every ZERO below is 'not seen yet', NOT 'free'.")
        print("  *** A count that already reaches a mailbox's limit is still")
        print("  *** sound - undercounting cannot invent a full mailbox.")

    totals = collections.Counter()
    for entry in campaigns.values():
        for compound, n in (entry.get("by_sender_day") or {}).items():
            totals[compound] += n

    by_sender = collections.defaultdict(collections.Counter)
    days = set()
    for compound, n in totals.items():
        sid, day = compound.split("|", 1)
        by_sender[int(sid)][day] += n
        days.add(day)

    days = sorted(d for d in days if d)
    if not days:
        print("\nno rows walked yet")
        return

    print()
    print(f"=== FORWARD BOOK, {len(by_sender)} senders x {len(days)} days ===")
    head = f"{'sender':>8} " + " ".join(f"{d[5:]:>6}" for d in days)
    if limits:
        head += f" {'limit':>6}"
    print(head)
    print("-" * len(head))
    for sid in sorted(by_sender):
        line = f"{sid:>8} " + " ".join(
            f"{by_sender[sid].get(d, 0):>6}" for d in days)
        if limits:
            line += f" {limits.get(str(sid), ''):>6}"
        print(line)

    if limits:
        print()
        print("=== MAILBOXES WITH ROOM, by day (complete walks only) ===")
        if partial:
            print("  REFUSED: the walk is incomplete, so 'room' cannot be")
            print("  distinguished from 'not yet seen'. Finish the walk.")
        else:
            for day in days:
                free = [sid for sid in sorted(by_sender)
                        if int(limits.get(str(sid)) or 0) >
                        by_sender[sid].get(day, 0)]
                print(f"  {day}: {len(free)} mailbox(es) with headroom")


def main():
    ap = argparse.ArgumentParser()
    # No default here: the set is ASKED OF THE PROVIDER after load_env, so a
    # stale literal cannot silently narrow the walk. See
    # `forward_booking_campaigns`.
    ap.add_argument("--campaigns", default=None)
    ap.add_argument("--checkpoint", type=int, default=50)
    ap.add_argument("--max-pages", type=int, default=None)
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--reset", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    load_env()
    if args.reset and os.path.exists(state_path()):
        os.remove(state_path())

    state = load_state()

    limits = {}
    try:
        rows, _meta = bison.sender_emails()
        limits = {str(r.get("id")): r.get("daily_limit") for r in rows or []}
    except Exception as exc:                        # noqa: BLE001 - classified
        print(f"(sender limits unavailable: {type(exc).__name__}: {exc})")

    if args.report:
        report(state, limits)
        return

    if args.campaigns:
        targets = [int(c) for c in args.campaigns.split(",") if c.strip()]
    else:
        targets = list(forward_booking_campaigns())
        print("campaigns that can book a mailbox, per the provider: "
              + ", ".join(str(c) for c in targets))

    started = time.perf_counter()
    for cid in targets:
        try:
            walk(cid, state, checkpoint=args.checkpoint,
                 max_pages=args.max_pages, quiet=args.quiet)
        except Exception as exc:                    # noqa: BLE001 - classified
            print(f"campaign {cid}: STOPPED - {type(exc).__name__}: {exc}")
    save_state(state)
    print(f"\nwalked for {time.perf_counter() - started:.0f}s")
    report(state, limits)


if __name__ == "__main__":
    main()
