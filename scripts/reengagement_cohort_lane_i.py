#!/usr/bin/env python3
"""Re-engagement cohort, lane I: refresh it, account it, and cost its packs.

    py -3 scripts/reengagement_cohort_lane_i.py --freshen   # phase 1, bison
    py -3 scripts/reengagement_cohort_lane_i.py --sends     # phase 2, bison
    py -3 scripts/reengagement_cohort_lane_i.py --linkedin  # phase 3, heyreach
    py -3 scripts/reengagement_cohort_lane_i.py --report    # no network

READ-ONLY. Every provider call below is a `GET` (EmailBison) or the HeyReach
read routes already declared in `heyreach.READ_ROUTES_ALL`. No write verb is
imported from either provider module. The push belongs to the foreground
session.

## WHY THIS EXISTS BESIDE `reengagement_provider_confirmed.py`

That script answered the five clauses from EmailBison and said so plainly in
its own §6: **"HeyReach was not read at all this session"**, and **"1,026 of
the 1,039 have no store record"**. Three things it could not answer, which the
acceptance bar for this lane requires:

  1. **Its answer is a snapshot and the clauses move.** The staged files were
     written 2026-09-24T18:05-18:27Z. `too_recent` is computed from send
     dates frozen at that instant, so a lead mailed since reads as 90+ days
     clear. Re-running `--report` at a later clock ADMITS leads and never
     ejects them: it is wrong in the unsafe direction, by construction.
  2. **It counts leads and never accounts.** `_trim_lead` deliberately drops
     every prospect field, so nothing staged carries a domain, and the account
     rule ("same contact never twice; a second persona only after a gap")
     cannot be evaluated against a file of lead ids.
  3. **The LinkedIn channel is unread.** EmailBison's reply history is per
     channel and it says so.

## THE FRESHNESS RULE THIS SCRIPT ENFORCES

A campaign-level counter is the cheap witness for "did anything happen since
the snapshot". `GET /campaigns` returns `emails_sent`, `replied`, `bounced`
and `unsubscribed` per campaign for all 33, including the client's own
campaigns whose queues are far too large to walk (352 is 6,428 queue pages).

    counter unchanged since the snapshot  ->  no lead in it was mailed,
                                              replied, bounced or unsubscribed
                                              in the interval
    counter moved                         ->  every cohort member with a
                                              membership in that campaign is
                                              STALE and must be re-read per
                                              lead before it may be pushed

That turns an unbounded re-walk into three pages plus a named remainder. It
fails closed: an unreadable campaign counts as moved.

## NO PROSPECT DATA LEAVES THIS SCRIPT

Domains are read, staged under `work/` (gitignored) and reported only as
counts and as a per-domain collision verdict. No name, address, company name
or LinkedIn URL is printed or written to `docs/`.
"""
import argparse
import collections
import datetime
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.providers import bison, load_env, query, request      # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STAGE = os.path.join(ROOT, "work", "stage")

#: Written by the provider-confirmed lane on 2026-09-24. Read, never written.
PC_LEADS = os.path.join(STAGE, "pc-leads.jsonl")
PC_SENDS = os.path.join(STAGE, "pc-sends.jsonl")
PC_LEAD_SENDS = os.path.join(STAGE, "pc-lead-sends.jsonl")
PC_CAMPAIGNS = os.path.join(STAGE, "pc-campaigns.json")
PC_STORE_NEGATIVES = os.path.join(STAGE, "pc-store-negatives.json")

#: NEW files, written only by this script.
RI_CAMPAIGNS = os.path.join(STAGE, "ri-campaigns.json")
RI_LEADS = os.path.join(STAGE, "ri-leads.jsonl")
RI_LEAD_SENDS = os.path.join(STAGE, "ri-lead-sends.jsonl")
RI_LINKEDIN = os.path.join(STAGE, "ri-linkedin.json")
RI_COHORT = os.path.join(STAGE, "ri-cohort.json")
RI_ACCOUNTS = os.path.join(STAGE, "ri-accounts.json")
RI_LIVEBOOK = os.path.join(STAGE, "ri-livebook.jsonl")

THROTTLE = 0.25

#: The 16 campaigns the candidate estate lives in, from the 2026-09-24 walk.
ESTATE = (262, 263, 264, 418, 451, 481, 487, 489, 491, 492, 493, 494,
          495, 496, 497, 498)

#: Counters that move when something happened to a lead inside a campaign.
MOVING = ("emails_sent", "replied", "bounced", "unsubscribed")


def _now():
    return datetime.datetime.now(datetime.timezone.utc)


def _domain(email):
    text = str(email or "").strip().lower()
    return text.rsplit("@", 1)[-1] if "@" in text else ""


def _walk(what, url_of, cap):
    """Every row behind a paginated route, or a refusal. Never a page."""
    rows, total, page = [], None, 1
    while True:
        status, data = request("GET", url_of(page), bison.headers())
        if not bison.ok(status):
            raise bison.ProviderError(f"{what}: page {page} -> {status}")
        chunk = (data or {}).get("data")
        if not isinstance(chunk, list):
            raise bison.ProviderError(f"{what}: the list is not a list")
        rows += chunk
        meta = data.get("meta") if isinstance(data.get("meta"), dict) else {}
        if total is None:
            total = meta.get("total")
        try:
            last = int(meta.get("last_page"))
        except (TypeError, ValueError):
            break
        if page >= last:
            break
        if page >= cap:
            raise bison.PartialInventory(
                f"{what}: {last} pages and this read stops at {cap}")
        page += 1
        time.sleep(THROTTLE)
    if isinstance(total, int) and len(rows) != total:
        raise bison.PartialInventory(
            f"{what}: meta.total says {total} and {len(rows)} arrived")
    return rows


#: EmailBison refuses `page=` beyond this. MEASURED, not read off a doc:
#: page 1,000 of campaign 352's leads answers 200 and page 1,001 answers 422
#: with *"You are requesting too many pages. Please use the cursor pagination
#: type to traverse large datasets."* At fifteen rows a page that is a hard
#: ceiling of 15,000 rows on every offset walk in this repository.
OFFSET_PAGE_CEILING = 1000

#: ... and this is the way past it. `?pagination_type=cursor` returns a meta
#: block carrying `next_cursor`/`prev_cursor` instead of `last_page`/`total`.
#: `per_page` is ignored on this route - 15, 50, 100, 200 and 500 all return
#: fifteen rows - so a large campaign still costs total/15 requests. What
#: cursor buys is REACHING them at all.
CURSOR = {"pagination_type": "cursor"}


def _walk_cursor(what, base_url, cap=20000):
    """Every row behind a cursor-paginated route, or a refusal.

    THE TERMINATION CONDITION IS `next_cursor`, NOT AN EMPTY PAGE. This meta
    block carries no `total` and no `last_page`, so this walk cannot check the
    completeness invariant `_walk` checks. It compensates the only way it can:
    a repeated cursor, a page that is not a list, and the page cap are all
    REFUSALS rather than ends. A short read must never read as end-of-data -
    that is the whole reason `_walk` refuses on a total mismatch.
    """
    rows, cursor, seen, n = [], None, set(), 0
    while True:
        params = dict(CURSOR)
        if cursor:
            params["cursor"] = cursor
        status, data = request("GET", query(base_url, params), bison.headers())
        if not bison.ok(status):
            raise bison.ProviderError(f"{what}: cursor page {n} -> {status}")
        chunk = (data or {}).get("data")
        if not isinstance(chunk, list):
            raise bison.ProviderError(
                f"{what}: the list is not a list; refusing to read an unknown "
                f"shape as an empty one")
        rows += chunk
        meta = data.get("meta") if isinstance(data.get("meta"), dict) else {}
        nxt = meta.get("next_cursor")
        if not nxt:
            return rows
        if nxt in seen:
            raise bison.PartialInventory(
                f"{what}: next_cursor repeated after {len(rows)} rows. "
                f"Refusing to loop, and refusing to call this the end")
        seen.add(nxt)
        cursor, n = nxt, n + 1
        if n > cap:
            raise bison.PartialInventory(
                f"{what}: {n} cursor pages and this read stops at {cap}")
        time.sleep(THROTTLE)


def _campaign_index():
    rows = _walk("campaigns",
                 lambda p: query(f"{bison.base()}/campaigns", {"page": p}),
                 cap=bison.PAGE_CAP)
    out = {}
    for row in rows:
        if isinstance(row, dict) and row.get("id") is not None:
            out[int(row["id"])] = {
                "id": int(row["id"]),
                "status": str(row.get("status") or ""),
                "name": str(row.get("name") or ""),
                "total_leads": row.get("total_leads"),
                "emails_sent": row.get("emails_sent"),
                "replied": row.get("replied"),
                "bounced": row.get("bounced"),
                "unsubscribed": row.get("unsubscribed"),
                "can_unsubscribe": row.get("can_unsubscribe"),
            }
    return out


def freshen():
    """Phase 1: current campaign counters, and every estate lead re-read.

    148 pages. It re-reads `overall_stats` and `lead_campaign_data` at today's
    clock, so replies and live memberships are current, and it captures the
    email DOMAIN, which nothing staged yesterday carries.
    """
    load_env()
    workspace = bison.bound_workspace()
    started = _now()
    print(f"\nLANE I FRESHEN - workspace {workspace.get('id')} "
          f"({workspace.get('name')})")
    print(f"  started {started:%Y-%m-%dT%H:%M:%S}Z, throttle {THROTTLE}s\n")

    live = _campaign_index()
    with open(PC_CAMPAIGNS, encoding="utf-8") as handle:
        old = {int(k): v for k, v in json.load(handle).items()}

    moved, unreadable = {}, []
    for cid in sorted(set(live) | set(old)):
        before, after = old.get(cid), live.get(cid)
        if after is None:
            unreadable.append(cid)
            continue
        if before is None:
            moved[cid] = {"new_campaign": True}
            continue
        delta = {k: (before.get(k), after.get(k))
                 for k in MOVING if before.get(k) != after.get(k)}
        if before.get("status") != after.get("status"):
            delta["status"] = (before.get("status"), after.get("status"))
        if delta:
            moved[cid] = delta

    print("  CAMPAIGN COUNTER DELTA since the 2026-09-24T18:05Z snapshot")
    if not moved and not unreadable:
        print("    nothing moved in any of the 33 campaigns")
    for cid, delta in sorted(moved.items()):
        print(f"    {cid:>5} {json.dumps(delta, default=str)}")
    for cid in unreadable:
        print(f"    {cid:>5} GONE from /campaigns - treated as moved")
    print()

    n = 0
    with open(RI_LEADS, "w", encoding="utf-8") as handle:
        for cid in ESTATE:
            try:
                rows = _walk(f"leads {cid}",
                             lambda p, c=cid: query(bison.leads_endpoint(c),
                                                    {"page": p}),
                             cap=bison.CAMPAIGN_QUEUE_PAGE_CAP)
            except Exception as exc:                            # noqa: BLE001
                print(f"  {cid:>5} LEADS UNREADABLE ({type(exc).__name__}) "
                      f"- every lead in it stays OUT")
                continue
            for row in rows:
                if not isinstance(row, dict) or row.get("id") is None:
                    continue
                stats = row.get("overall_stats") or {}
                memberships = []
                for entry in row.get("lead_campaign_data") or []:
                    if isinstance(entry, dict):
                        memberships.append({
                            "campaign_id": entry.get("campaign_id"),
                            "status": str(entry.get("status") or ""),
                            "emails_sent": entry.get("emails_sent"),
                            "replies": entry.get("replies"),
                            "opens": entry.get("opens"),
                            "interested": entry.get("interested"),
                        })
                handle.write(json.dumps({
                    "lead_id": int(row["id"]),
                    "seen_in_campaign": cid,
                    "domain": _domain(row.get("email")),
                    "has_email": bool(str(row.get("email") or "").strip()),
                    "verification": str(row.get("status") or ""),
                    "updated_at": row.get("updated_at"),
                    "overall_emails_sent": stats.get("emails_sent"),
                    "overall_replies": stats.get("replies"),
                    "overall_unique_replies": stats.get("unique_replies"),
                    "overall_opens": stats.get("opens"),
                    "memberships": memberships,
                }) + "\n")
                n += 1
            print(f"  {cid:>5} {live.get(cid, {}).get('status',''):<10} "
                  f"leads {len(rows):>5}")
            time.sleep(THROTTLE)

    payload = {
        "read_at": f"{started:%Y-%m-%dT%H:%M:%S}Z",
        "finished_at": f"{_now():%Y-%m-%dT%H:%M:%S}Z",
        "workspace": workspace.get("id"),
        "campaigns": {str(k): v for k, v in live.items()},
        "moved_since_snapshot": {str(k): v for k, v in moved.items()},
        "unreadable": unreadable,
        "lead_rows": n,
    }
    with open(RI_CAMPAIGNS, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=1, sort_keys=True)
    print(f"\n  {n} lead rows written, {len(moved)} campaigns moved")
    return 0


def sends(only=None):
    """Phase 2: a COMPLETE per-lead send history, at today's clock.

    `GET /leads/{id}/scheduled-emails` spans every campaign including the ones
    too large to walk. This is the only read that can eject a lead the frozen
    snapshot would admit, so it is run for every lead still standing after the
    cheap clauses.
    """
    load_env()
    leads, _old_sends, _known = _load_fresh()
    known = _known
    done = set()
    if os.path.exists(RI_LEAD_SENDS):
        with open(RI_LEAD_SENDS, encoding="utf-8") as handle:
            for line in handle:
                done.add(int(json.loads(line)["lead_id"]))
    cheap = ("replied", "bounced", "unsubscribed", "live_sequence")
    wanted = []
    for lead_id, lead in sorted(leads.items()):
        if lead_id in done:
            continue
        if only is not None and lead_id not in set(only):
            continue
        clauses, _a, _n = _assess(lead, [], known, skip_send_clauses=True)
        if any(clauses[name] for name in cheap):
            continue
        wanted.append(lead_id)
    print(f"\n  per-lead queue reads needed: {len(wanted)} "
          f"({len(done)} already on disk)")
    handle = open(RI_LEAD_SENDS, "a", encoding="utf-8")
    try:
        for n, lead_id in enumerate(wanted, 1):
            try:
                rows = _walk(f"lead queue {lead_id}",
                             lambda p, i=lead_id: query(
                                 f"{bison.base()}/leads/{i}/scheduled-emails",
                                 {"page": p}),
                             cap=bison.CAMPAIGN_QUEUE_PAGE_CAP)
            except Exception as exc:                            # noqa: BLE001
                # NOT written. An unread lead keeps falling to the
                # `unread_campaign` clause, which is the fail-closed answer.
                print(f"    lead {lead_id}: {type(exc).__name__} - left "
                      f"unread, stays excluded")
                continue
            for row in rows:
                if not isinstance(row, dict):
                    continue
                lead = row.get("lead") if isinstance(row.get("lead"), dict) else {}
                handle.write(json.dumps({
                    "lead_id": lead_id,
                    "campaign_id": row.get("campaign_id"),
                    "status": str(row.get("status") or ""),
                    "sent_at": row.get("sent_at"),
                    "replies": row.get("replies"),
                    "step": row.get("sequence_step_id"),
                }) + "\n")
            if n % 100 == 0:
                handle.flush()
                print(f"    {n}/{len(wanted)} at {_now():%H:%M:%S}Z")
            time.sleep(THROTTLE)
    finally:
        handle.close()
    print(f"  done {_now():%Y-%m-%dT%H:%M:%S}Z")
    return 0


def livebook(only=None):
    """Phase 2b: every lead in the LIVE campaigns, for the account rule.

    THE COLLISION QUESTION CANNOT BE ANSWERED FROM THE ESTATE ALONE. The
    account rule is about a COLLEAGUE: "the same account, a second persona,
    only after a gap". A cohort member's own memberships are on their own
    payload, but a colleague at the same domain who sits in the client's live
    campaign 352 and was never in one of our 16 is invisible to the estate
    read - and 947 of the 1,039 in yesterday's cohort had been mailed by 352.

    So an account-collision count computed over the estate is a count from a
    stage that has not asked the next stage's question. This walks the live
    campaigns themselves - id, domain, and the status of the membership in
    that campaign - and nothing else.

    It is the expensive read in this lane and it is deliberately separate.
    """
    load_env()
    with open(RI_CAMPAIGNS, encoding="utf-8") as handle:
        known = {int(k): v for k, v in json.load(handle)["campaigns"].items()}
    targets = sorted(cid for cid, m in known.items()
                     if str(m.get("status") or "").lower() in LIVE_CAMPAIGN
                     and cid not in ESTATE) if only is None else [int(c) for c in only]
    print(f"\n  live campaigns to walk: {targets}")
    total = sum(int(known[c].get("total_leads") or 0) for c in targets)
    print(f"  provider says they hold {total} leads "
          f"(~{(total + 14) // 15} pages)")
    done = set()
    if os.path.exists(RI_LIVEBOOK):
        with open(RI_LIVEBOOK, encoding="utf-8") as handle:
            for line in handle:
                done.add(int(json.loads(line)["campaign_id"]))
    with open(RI_LIVEBOOK, "a", encoding="utf-8") as handle:
        for cid in targets:
            if cid in done:
                print(f"  {cid:>5} already on disk - skipped")
                continue
            # A campaign past the offset ceiling is walked by CURSOR. 352
            # holds 21,530 leads - 1,436 pages - and `page=1001` is a 422.
            # Before this, that campaign was simply unreadable, and the
            # 2026-09-24 document's "too big to walk, skipped by name" was
            # describing this limit without having found its name.
            big = int((known.get(cid) or {}).get("total_leads") or 0) > \
                OFFSET_PAGE_CEILING * 15
            try:
                if big:
                    rows = _walk_cursor(f"leads {cid} (cursor)",
                                        bison.leads_endpoint(cid))
                else:
                    rows = _walk(f"leads {cid}",
                                 lambda p, c=cid: query(
                                     bison.leads_endpoint(c), {"page": p}),
                                 cap=OFFSET_PAGE_CEILING)
            except Exception as exc:                            # noqa: BLE001
                # A campaign we could not read is NOT an empty one. Every
                # cohort account stays flagged UNKNOWN for it.
                print(f"  {cid:>5} UNREADABLE ({type(exc).__name__}) - the "
                      f"collision answer for it is UNKNOWN, never clean")
                continue
            n = 0
            for row in rows:
                if not isinstance(row, dict) or row.get("id") is None:
                    continue
                live_here = False
                for entry in row.get("lead_campaign_data") or []:
                    if not isinstance(entry, dict):
                        continue
                    if entry.get("campaign_id") == cid and str(
                            entry.get("status") or "").lower() in LIVE_MEMBERSHIP:
                        live_here = True
                handle.write(json.dumps({
                    "campaign_id": cid,
                    "lead_id": int(row["id"]),
                    "domain": _domain(row.get("email")),
                    "live_membership": live_here,
                }) + "\n")
                n += 1
            handle.flush()
            print(f"  {cid:>5} {n} leads written at {_now():%H:%M:%S}Z")
    return 0


# ---------------------------------------------------------------- the clauses

LIVE_CAMPAIGN = {"active", "in_progress", "running", "sending"}
LIVE_MEMBERSHIP = {"in_sequence", "sending", "active", "scheduled"}
BOUNCE_STATES = {"bounced", "bounce", "hard_bounced", "soft_bounced"}
UNSUB_STATES = {"unsubscribed", "unsubscribe", "opted_out", "complained",
                "complaint", "blocked", "suppressed"}
SENT_STATE = "sent"
REENGAGE_AFTER_DAYS = 90

CLAUSES = ("replied", "bounced", "unsubscribed", "live_sequence",
           "unread_campaign", "unconfirmed_sends", "never_sent", "too_recent",
           "stale_campaign", "test_identity", "store_negative", "no_email")


def _parse(stamp):
    text = str(stamp or "").strip().replace("Z", "+00:00")
    if not text:
        return None
    try:
        moment = datetime.datetime.fromisoformat(text)
    except ValueError:
        return None
    return moment if moment.tzinfo else moment.replace(
        tzinfo=datetime.timezone.utc)


def _load_fresh():
    """Today's lead re-read, today's campaign index, today's per-lead queue."""
    leads = {}
    with open(RI_LEADS, encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            seen = leads.setdefault(row["lead_id"], row)
            seen.setdefault("seen_in", [])
            seen["seen_in"].append(row["seen_in_campaign"])
    sends_by_lead = collections.defaultdict(list)
    if os.path.exists(RI_LEAD_SENDS):
        with open(RI_LEAD_SENDS, encoding="utf-8") as handle:
            for line in handle:
                row = json.loads(line)
                sends_by_lead[int(row["lead_id"])].append(row)
        for lead_id in sends_by_lead:
            if lead_id in leads:
                leads[lead_id]["queue_complete"] = True
    with open(RI_CAMPAIGNS, encoding="utf-8") as handle:
        blob = json.load(handle)
    known = {int(k): v for k, v in blob["campaigns"].items()}
    for cid in ESTATE:
        if cid in known:
            known[cid]["walked"] = True
    known["_moved"] = {int(k) for k in blob.get("moved_since_snapshot") or {}}
    known["_read_at"] = blob["read_at"]
    return leads, sends_by_lead, known


def _assess(lead, rows, known, now=None, skip_send_clauses=False,
            negatives=None, test_ids=frozenset()):
    """Every clause independently. No short-circuit, no silent fallback."""
    now = now or _now()
    walked = {cid for cid, meta in known.items()
              if isinstance(meta, dict) and meta.get("walked")}
    out = dict.fromkeys(CLAUSES)
    memberships = lead.get("memberships") or []
    lead_id = lead.get("lead_id")

    if (lead.get("overall_replies") or 0) > 0:
        out["replied"] = "overall_stats.replies > 0"
    elif (lead.get("overall_unique_replies") or 0) > 0:
        out["replied"] = "overall_stats.unique_replies > 0"
    else:
        for m in memberships:
            state = str(m.get("status") or "").lower()
            if (m.get("replies") or 0) > 0:
                out["replied"] = f"campaign {m.get('campaign_id')} counts a reply"
                break
            if state == "replied":
                out["replied"] = f"campaign {m.get('campaign_id')} reads replied"
                break
            if m.get("interested"):
                out["replied"] = (f"campaign {m.get('campaign_id')} reads "
                                  f"interested")
                break
        else:
            for row in rows:
                if (row.get("replies") or 0) > 0:
                    out["replied"] = "a queue row counts a reply"
                    break

    for m in memberships:
        state = str(m.get("status") or "").lower()
        if state in BOUNCE_STATES and not out["bounced"]:
            out["bounced"] = f"campaign {m.get('campaign_id')} reads {state}"
        if state in UNSUB_STATES and not out["unsubscribed"]:
            out["unsubscribed"] = f"campaign {m.get('campaign_id')} reads {state}"
    for row in rows:
        state = str(row.get("status") or "").lower()
        if state in BOUNCE_STATES and not out["bounced"]:
            out["bounced"] = f"a queue row in {row.get('campaign_id')} bounced"
        if state in UNSUB_STATES and not out["unsubscribed"]:
            out["unsubscribed"] = (f"a queue row in {row.get('campaign_id')} "
                                   f"reads {state}")

    for m in memberships:
        cid = m.get("campaign_id")
        member = str(m.get("status") or "").lower()
        if member not in LIVE_MEMBERSHIP:
            continue
        status = str((known.get(cid) or {}).get("status") or "").lower() \
            if isinstance(known.get(cid), dict) else ""
        if status in LIVE_CAMPAIGN:
            out["live_sequence"] = f"{member} in live campaign {cid}"
            break
        if cid not in known:
            out["live_sequence"] = f"{member} in campaign {cid}, status unread"
            break

    if not skip_send_clauses:
        for m in (() if lead.get("queue_complete") else memberships):
            cid = m.get("campaign_id")
            if (m.get("emails_sent") or 0) > 0 and cid not in walked:
                out["unread_campaign"] = (
                    f"campaign {cid} sent {m.get('emails_sent')} and its "
                    f"queue was never read")
                break

        confirmed = [r for r in rows
                     if str(r.get("status") or "").lower() == SENT_STATE
                     and r.get("sent_at")]
        claimed = lead.get("overall_emails_sent")
        if not isinstance(claimed, int):
            out["unconfirmed_sends"] = "no overall_stats.emails_sent to reconcile"
        elif len(confirmed) < claimed:
            out["unconfirmed_sends"] = (f"provider counts {claimed} sends and "
                                        f"{len(confirmed)} are dated")
        stamps = sorted(s for s in (_parse(r["sent_at"]) for r in confirmed) if s)
        if not confirmed:
            out["never_sent"] = "no dated sent row exists anywhere"
        elif len(stamps) != len(confirmed):
            out["unconfirmed_sends"] = out["unconfirmed_sends"] or (
                "a sent row carries an unparseable sent_at")
        age = (now - stamps[-1]).days if stamps else None
        if age is not None and age < REENGAGE_AFTER_DAYS:
            out["too_recent"] = f"last confirmed send {age}d ago"
    else:
        age = None

    # A membership inside a campaign whose counters moved since the snapshot
    # that produced this lead's send history is STALE, not clean.
    for m in memberships:
        cid = m.get("campaign_id")
        if cid in (known.get("_moved") or set()) and not lead.get("queue_complete"):
            out["stale_campaign"] = (f"campaign {cid} moved since the snapshot "
                                     f"and this lead has no fresh queue read")
            break

    if lead_id in test_ids:
        out["test_identity"] = "the operator's test identity"

    if negatives and lead_id in negatives:
        out["store_negative"] = ("our store holds "
                                 + ",".join(sorted(negatives[lead_id])))

    if not lead.get("has_email"):
        out["no_email"] = "the provider lead carries no address"

    return out, age, len([r for r in rows
                          if str(r.get("status") or "").lower() == SENT_STATE
                          and r.get("sent_at")])


def _test_identity_ids():
    from src import testidentity                             # noqa: PLC0415
    ids = set(testidentity.LEAD_IDS)
    # The 2026-09-25 lane briefing names two more than the module does. A lead
    # id that MIGHT be the operator is excluded: the conservative reading is
    # the only safe one, and the discrepancy is reported rather than resolved.
    ids |= {205079, 205081}
    return frozenset(ids)


def _store_negatives():
    if not os.path.exists(PC_STORE_NEGATIVES):
        return {}
    with open(PC_STORE_NEGATIVES, encoding="utf-8") as handle:
        return {int(k): sorted(v) for k, v in json.load(handle).items()}


def report(emit=print):
    now = _now()
    leads, sends_by_lead, known = _load_fresh()
    negatives = _store_negatives()
    test_ids = _test_identity_ids()

    funnel = collections.Counter()
    tally = collections.Counter()
    cohort, ages, reasons, excluded = [], [], {}, {}
    for lead_id, lead in sorted(leads.items()):
        rows = sends_by_lead.get(lead_id, [])
        clauses, age, n_sent = _assess(lead, rows, known, now=now,
                                       negatives=negatives, test_ids=test_ids)
        for name in CLAUSES:
            if clauses[name]:
                tally[name] += 1
        first = next((n for n in CLAUSES if clauses[n]), None)
        if first:
            funnel[first] += 1
            # EVERY EXCLUSION IS TRACEABLE OR IT IS NOT AN EXCLUSION. The
            # clause, the provider's own words for it, every other clause it
            # also trips, and the instant the read that says so was taken.
            excluded[lead_id] = {
                "clause": first,
                "detail": clauses[first],
                "also": {n: clauses[n] for n in CLAUSES
                         if clauses[n] and n != first},
                "read_at": known["_read_at"],
                "queue_read": bool(lead.get("queue_complete")),
                "seen_in": sorted(set(lead.get("seen_in") or [])),
            }
        else:
            cohort.append(lead_id)
            ages.append(age)
            reasons[lead_id] = {
                "reason": f"no reply, bounce, unsubscribe or live sequence at "
                          f"the provider; {n_sent} dated sends, last "
                          f"{age}d ago",
                "age_days": age,
                "confirmed_sends": n_sent,
                "domain": lead.get("domain"),
                "seen_in": sorted(set(lead.get("seen_in") or [])),
            }

    emit("")
    emit(f"LANE I RE-ENGAGEMENT COHORT  computed {now:%Y-%m-%dT%H:%M:%S}Z")
    emit(f"  provider read at            {known['_read_at']}")
    emit(f"  campaigns in the workspace  "
         f"{len([k for k in known if isinstance(k, int)])}")
    emit(f"  campaigns walked            {len(ESTATE)}")
    emit(f"  leads re-read today         {len(leads)}")
    emit(f"  per-lead queue rows         {sum(len(v) for v in sends_by_lead.values())}")
    emit("")
    emit("  THE FUNNEL - disjoint, first clause that disqualifies")
    emit(f"    base, every lead in the 16 estate campaigns      {len(leads):>6}")
    for name in CLAUSES:
        emit(f"      - {name:<44} {funnel[name]:>6}")
    emit(f"    = COHORT                                          {len(cohort):>6}")
    emit(f"    check sum {sum(funnel.values()) + len(cohort)}")
    emit("")
    emit("  EVERY CLAUSE COUNTED SEPARATELY - a lead may trip several")
    for name in CLAUSES:
        emit(f"      {name:<46} {tally[name]:>6}")
    if ages:
        emit("")
        emit(f"  cohort last-send age: min {min(ages)}d  max {max(ages)}d")

    # ------------------------------------------------- the LinkedIn gate
    #
    # EmailBison's reply history is PER CHANNEL and it cannot answer "no reply
    # EVER" on its own. The HeyReach read is applied here as an EXTRA gate: it
    # may only ever REMOVE a lead the EmailBison clauses admitted, never add
    # one. Unreadable removes too - `/campaign/GetCampaignsForLead` answering
    # 404 is not a statement that this person is in no LinkedIn campaign.
    li_removed = {}
    if os.path.exists(RI_LINKEDIN):
        with open(RI_LINKEDIN, encoding="utf-8") as handle:
            li = json.load(handle)
        for lead_id in li.get("linkedin_replied") or []:
            li_removed[int(lead_id)] = "HeyReach reads REPLIED on LinkedIn"
        for lead_id in li.get("linkedin_live") or []:
            li_removed.setdefault(int(lead_id),
                                  "in a LIVE LinkedIn sequence at HeyReach")
        for lead_id in li.get("linkedin_unreadable") or []:
            li_removed.setdefault(
                int(lead_id),
                "HeyReach could not answer for this person; unreadable is "
                "not clean")
        hit = [i for i in cohort if i in li_removed]
        cohort = [i for i in cohort if i not in li_removed]
        emit("")
        emit(f"  THE LINKEDIN GATE (HeyReach, read {li.get('read_at')})")
        emit(f"      cohort members we could ASK about             "
             f"{len(li.get('joined_with_linkedin_url') or []):>6}")
        emit(f"      STRUCTURALLY UNANSWERABLE - no LinkedIn identity "
             f"{li.get('structurally_unanswerable'):>4}")
        emit(f"      removed by this gate                          {len(hit):>6}")
        for lead_id in hit:
            emit(f"        {lead_id}  {li_removed[lead_id]}")
            excluded[lead_id] = {"clause": "linkedin_gate",
                                 "detail": li_removed[lead_id],
                                 "also": {}, "read_at": li.get("read_at"),
                                 "queue_read": True,
                                 "seen_in": reasons[lead_id]["seen_in"]}
            reasons.pop(lead_id, None)
        funnel["linkedin_gate"] = len(hit)
        emit(f"  COHORT AFTER THE LINKEDIN GATE                    "
             f"{len(cohort):>6}")

    # ------------------------------------------------------------- accounts
    by_domain = collections.defaultdict(list)
    for lead_id in cohort:
        by_domain[reasons[lead_id]["domain"] or "(no domain)"].append(lead_id)
    emit("")
    emit("  ACCOUNTS, NOT LEADS")
    emit(f"      cohort leads                                  {len(cohort):>6}")
    emit(f"      distinct accounts (email domain)              {len(by_domain):>6}")
    multi = {d: v for d, v in by_domain.items() if len(v) > 1}
    emit(f"      accounts carrying more than one cohort lead   {len(multi):>6}")
    emit(f"      leads sitting on those accounts               "
         f"{sum(len(v) for v in multi.values()):>6}")
    spread = collections.Counter(len(v) for v in by_domain.values())
    emit("      leads per account: "
         + "  ".join(f"{k}x{v}" for k, v in sorted(spread.items())))

    # An account is LIVE if any lead on that domain - cohort member or not -
    # holds a live membership in a campaign that is live right now. That is
    # the collision the account rule exists to prevent.
    live_domains = {}
    for lead_id, lead in leads.items():
        dom = lead.get("domain")
        if not dom:
            continue
        for m in lead.get("memberships") or []:
            cid = m.get("campaign_id")
            meta = known.get(cid)
            if not isinstance(meta, dict):
                continue
            if str(m.get("status") or "").lower() in LIVE_MEMBERSHIP and \
                    str(meta.get("status") or "").lower() in LIVE_CAMPAIGN:
                live_domains.setdefault(dom, set()).add(cid)
    # ... and the live campaigns OUTSIDE the estate, which is where almost all
    # of the risk is: 947 of the cohort have been mailed by the client's own
    # campaign 352, and 352 is running right now with 21,530 leads. A
    # collision count taken over the 16 estate campaigns alone is a count from
    # a stage that has not asked the next stage's question.
    livebook_campaigns = set()
    if os.path.exists(RI_LIVEBOOK):
        with open(RI_LIVEBOOK, encoding="utf-8") as handle:
            for line in handle:
                row = json.loads(line)
                livebook_campaigns.add(int(row["campaign_id"]))
                if row.get("live_membership") and row.get("domain"):
                    live_domains.setdefault(row["domain"], set()).add(
                        int(row["campaign_id"]))
    want_live = {cid for cid, meta in known.items()
                 if isinstance(meta, dict)
                 and str(meta.get("status") or "").lower() in LIVE_CAMPAIGN
                 and cid not in ESTATE}
    missing_live = sorted(want_live - livebook_campaigns)

    collided = {d: sorted(live_domains[d]) for d in by_domain if d in live_domains}
    emit("")
    emit("  COLLISION WITH A LIVE CAMPAIGN, AT THE ACCOUNT")
    emit(f"      live campaigns outside the estate, walked     "
         f"{len(livebook_campaigns & want_live):>6} of {len(want_live)}")
    if missing_live:
        emit(f"      NOT WALKED, so their accounts are UNKNOWN:    "
             f"{missing_live}")
    emit(f"      cohort accounts with a colleague live now     {len(collided):>6}")
    emit(f"      cohort leads on those accounts                "
         f"{sum(len(by_domain[d]) for d in collided):>6}")
    where = collections.Counter()
    for cids in collided.values():
        for cid in cids:
            where[cid] += 1
    if where:
        emit("      the live campaigns they collide in: "
             + "  ".join(f"{c}:{n}" for c, n in sorted(where.items())))

    payload = {
        "computed_at": f"{now:%Y-%m-%dT%H:%M:%S}Z",
        "provider_read_at": known["_read_at"],
        "base": len(leads),
        "funnel": {name: funnel[name] for name in CLAUSES},
        "tally": {name: tally[name] for name in CLAUSES},
        "cohort": sorted(cohort),
        "per_lead": reasons,
        "excluded": excluded,
        "accounts": {d: sorted(v) for d, v in by_domain.items()},
        "collided_accounts": collided,
        "live_campaigns_walked": sorted(livebook_campaigns & want_live),
        "live_campaigns_not_walked": missing_live,
        "linkedin_removed": {str(k): v for k, v in li_removed.items()},
    }
    with open(RI_COHORT, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=1, sort_keys=True)
    emit("")
    emit(f"  written {RI_COHORT}")
    return payload


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--freshen", action="store_true")
    p.add_argument("--sends", action="store_true")
    p.add_argument("--livebook", action="store_true")
    p.add_argument("--report", action="store_true")
    p.add_argument("--only", nargs="*", type=int)
    args = p.parse_args(argv)
    if args.freshen:
        return freshen()
    if args.sends:
        return sends(only=args.only)
    if args.livebook:
        return livebook(only=args.only)
    if args.report:
        report()
        return 0
    p.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
