"""Replay a window of unmatched events through the new path. Posts NOTHING.

    py -3 scripts/notifications_replay.py --hours 72
    py -3 scripts/notifications_replay.py --hours 72 --no-lookup

## What it counts, and why it is two numbers and not one

BEFORE is measured, not modelled: every `unmatched_reply_needs_review` row in
`work/notifications.jsonl` whose status is `sent`, inside the window. Those
posts happened and the channel has them.

AFTER is those same events, re-attributed by `src/unmatched.py` and batched
into one digest per hour. The two numbers answer the same question about the
same set, which is the only way the comparison means anything.

## It cannot post, and that is a property rather than a promise

`NOTIFICATIONS` is pointed at a scratch file before `src.notify` resolves a
path, so the digests it plans are written to a temporary directory that
`scripts/notify_deliver_loop.py` does not read. `notify.deliver` is never
called. Nothing here reaches `slack.post`.

It also never writes the real ledger: `UNMATCHED_LEDGER` moves with it.

## The provider reads

Attribution needs the campaign, and a notification row carries only the
provider's event id. So the window is walked once per provider - EmailBison
`/replies` by cursor, the HeyReach inbox by page - and the events are joined
back on that id. Both are READS. `--no-lookup` skips the per-lead HeyReach
campaign resolution, which is the only call made per event rather than per
page; the events it would have resolved stay UNATTRIBUTED, which is the
fail-closed direction and gives the PESSIMISTIC after-count.
"""
import argparse
import collections
import datetime
import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

SCRATCH = tempfile.mkdtemp(prefix="replay-notifications-")
# BEFORE THE IMPORT. `notify.path()` and `unmatched.path()` resolve at call
# time, but pointing them here first means no ordering question exists.
os.environ["NOTIFICATIONS"] = os.path.join(SCRATCH, "notifications.jsonl")
os.environ["UNMATCHED_LEDGER"] = os.path.join(SCRATCH, "unmatched-ledger.jsonl")

from src import notify, store, unmatched                      # noqa: E402
from src.providers import load_env                            # noqa: E402

UNMATCHED_TYPE = "unmatched_reply_needs_review"


def _parse(stamp):
    try:
        at = datetime.datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return at if at.tzinfo else at.replace(tzinfo=datetime.timezone.utc)


def posted_before(path, since, until):
    """`(posted, raised)` - what reached the channel, and what was built.

    POSTED is `status == sent`: the transport confirmed it and the channel
    has it. RAISED includes the rows that were planned, unconfigured or
    suppressed. The before/after comparison uses POSTED, because a row that
    never left the file is not what made the channel unusable.
    """
    raised = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("type") != UNMATCHED_TYPE:
                continue
            at = _parse(row.get("at"))
            if at is None or not (since <= at <= until):
                continue
            raised.append(row)
    return [r for r in raised if r.get("status") == "sent"], raised


def bison_campaigns(since):
    """`{provider_event_id: (campaign_id, domain, kind, at)}` from /replies."""
    from src.providers import bison
    out, cursor, seen, pages = {}, None, set(), 0
    while pages < 400:
        page, cursor = bison.fetch_replies(cursor=cursor)
        pages += 1
        oldest = None
        for row in page:
            at = _parse(row.get("date_received") or row.get("created_at"))
            oldest = at if oldest is None or (at and at < oldest) else oldest
            identifier = f"emailbison:{row.get('uuid') or row.get('id')}"
            address = str(row.get("from_email_address") or "")
            out[identifier] = {
                "campaign_id": row.get("campaign_id"),
                "lead": address.rsplit("@", 1)[-1].lower() if "@" in address
                        else None,
                "event_type": bison.classify_reply_row(row),
                "at": row.get("date_received"),
            }
        if not page or not cursor or cursor in seen:
            break
        seen.add(cursor)
        if oldest and oldest < since:
            break
    return out


def heyreach_threads(since, pages=40):
    """`{thread_id: (profile_url, seat)}` from the inbox, newest first."""
    from src.providers import heyreach
    out = {}
    for page in range(pages):
        items, _total = heyreach.conversations(offset=page * 50, limit=50)
        if not items:
            break
        oldest = None
        for item in items:
            at = _parse(item.get("lastMessageAt"))
            oldest = at if oldest is None or (at and at < oldest) else oldest
            profile = item.get("correspondentProfile") or {}
            url = item.get("profileUrl") or profile.get("profileUrl")
            out[str(item.get("id"))] = {
                "profile_url": url,
                # The same field `unmatched.record` would have written: the
                # handle, never the name and never the message.
                "lead": unmatched.subject_of({"linkedin": url}),
                "seat": item.get("linkedInAccountId"),
            }
        if oldest and oldest < since:
            break
    return out


def _thread_of(identifier):
    """`heyreach:<thread>:<stamp>` -> the thread id."""
    parts = str(identifier or "").split(":")
    return parts[1] if len(parts) >= 3 and parts[0] == "heyreach" else None


def rebuild(rows, bison_index, heyreach_index):
    """The notification rows, as ledger rows the new path would have written."""
    out = []
    for row in rows:
        identifier = (row.get("ids") or {}).get("provider_event_id")
        payload = row.get("payload") or {}
        provider = payload.get("provider")
        known = (bison_index.get(identifier)
                 or heyreach_index.get(_thread_of(identifier)) or {})
        out.append({
            "at": row.get("at"),
            "hour": unmatched.hour_of(row.get("at")),
            "provider": provider,
            "provider_event_id": identifier,
            "event_type": known.get("event_type") or "reply_received",
            "campaign_id": known.get("campaign_id"),
            "lead": known.get("lead"),
            "profile_url": known.get("profile_url"),
            "held": payload.get("held") or 0,
            "why": payload.get("why"),
            "verdict": None, "campaign_name": None, "verdict_why": None,
            "digest": None,
        })
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--hours", type=int, default=72)
    parser.add_argument("--notifications",
                        default=os.path.join(ROOT, "work",
                                             "notifications.jsonl"))
    parser.add_argument("--no-lookup", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    load_env()
    until = datetime.datetime.now(datetime.timezone.utc)
    since = until - datetime.timedelta(hours=args.hours)

    before, raised = posted_before(args.notifications, since, until)
    print(f"window      {since.isoformat()}  ->  {until.isoformat()}")
    print(f"BEFORE      {len(before)} posts to the channel "
          f"({len(raised)} {UNMATCHED_TYPE} rows raised)")

    bison_index = bison_campaigns(since) if any(
        (r.get('payload') or {}).get('provider') == 'emailbison'
        for r in before) else {}
    heyreach_index = heyreach_threads(since) if any(
        (r.get('payload') or {}).get('provider') == 'heyreach'
        for r in before) else {}
    print(f"joined      {len(bison_index)} EmailBison replies, "
          f"{len(heyreach_index)} HeyReach threads")

    ledger = rebuild(before, bison_index, heyreach_index)
    # `now` is one hour past the newest row, so the newest hour has CLOSED and
    # is digested. Left at the real now, the last partial hour would be held
    # back and the after-count would flatter itself by one.
    newest = max([_parse(r["at"]) for r in ledger if _parse(r["at"])],
                 default=until)
    results = unmatched.flush(
        now=newest + datetime.timedelta(hours=1), rows=ledger,
        lookup=None if args.no_lookup else unmatched.heyreach_lookup)

    verdicts = collections.Counter(r.get("verdict") for r in ledger)
    posts = [r for r in results if r["posted"]]
    print(f"AFTER       {len(posts)} posts "
          f"(one digest per hour with at least one row of ours)")
    print(f"verdicts    " + ", ".join(f"{k}={v}" for k, v in
                                      sorted(verdicts.items(), key=str)))
    by_campaign = collections.Counter(
        (r.get("provider"), r.get("campaign_id"), r.get("verdict"))
        for r in ledger)
    print("attribution, provider / campaign / verdict:")
    for (provider, campaign, verdict), count in sorted(
            by_campaign.items(), key=lambda kv: (-kv[1], str(kv[0]))):
        print(f"  {str(provider):<11} {str(campaign):<10} "
              f"{str(verdict):<14} {count}")
    print("hours with a digest: "
          + (", ".join(r["hour"] for r in posts) or "none"))

    # THE LIST OF OURS. The point of the whole exercise: which events an
    # operator should have been shown, and could not find in a hundred
    # identical posts.
    print("\nOURS, and unresolved - the events that reach the channel:")
    for row in sorted(ledger, key=lambda r: str(r.get("at"))):
        if row.get("verdict") == unmatched.THEIRS:
            continue
        print(f"  {row.get('at')}  {row.get('verdict'):<13} "
              f"{row.get('provider')} campaign "
              f"{row.get('campaign_id') or '-'} "
              f"{row.get('campaign_name') or ''}".rstrip())
        print(f"      {row.get('provider_event_id')}")
        print(f"      {row.get('verdict_why')}")
    print(f"\nnothing was posted. notifications written to {SCRATCH}")

    if args.json:
        print(json.dumps({"before": len(before), "after": len(posts),
                          "verdicts": dict(verdicts),
                          "hours": [r["hour"] for r in posts]}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
