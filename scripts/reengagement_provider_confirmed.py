#!/usr/bin/env python3
"""Rebuild the re-engagement cohort from PROVIDER-CONFIRMED facts only.

    py -3 scripts/reengagement_provider_confirmed.py --walk
    py -3 scripts/reengagement_provider_confirmed.py --report

READ-ONLY. Not one write verb is imported from the provider module; every
call below is a `GET`. Nothing is enrolled, created, activated or stopped.

## WHY THIS EXISTS BESIDE `reengagement_inventory.py`

`work/stage/reengagement-inventory.jsonl` derives its lanes from ONE
membership state string per lead. Three of the operator's five clauses cannot
be answered from it at all:

    "no reply ever"      no row carries a `replied` flag, so `lane_for` reads
                         None on all 2,081 and reply detection collapses to
                         the 57 rows whose state is literally `replied`. A
                         lead who replied and was afterwards marked `stopped`
                         reads as stopped and lands in REENGAGE.
    "no unsubscribe"     nothing in the file can produce a non-zero.
    "90+ days"           `lead.updated_at` is LAST ACTIVITY, not a send.

## THE TWO ROUTES THAT DO ANSWER THEM

Both were probed read-only on 2026-09-24 and neither is used by the inventory
walk.

    GET /campaigns/{id}/leads              the SAME full lead payload that
                                           `GET /leads/{id}` returns, fifteen
                                           to a page. It carries
                                           `overall_stats` - replies, unique
                                           replies and emails_sent ACROSS
                                           EVERY CAMPAIGN - and
                                           `lead_campaign_data`, one entry per
                                           campaign the lead is in, each with
                                           its own status, replies and
                                           emails_sent.

                                           This is what makes "no reply EVER,
                                           across every campaign" a provider
                                           fact rather than a reading of one
                                           string. It costs total/15 pages per
                                           campaign instead of one call per
                                           lead - 148 pages for the whole
                                           estate rather than 2,081 calls.

    GET /campaigns/{id}/scheduled-emails   one row per planned message, with
                                           `status` and `sent_at`. A row
                                           reading `sent` WITH a `sent_at` is
                                           the only witness this file accepts
                                           for a send. `scheduled`, `active`
                                           and `stopped` are not sends, and a
                                           `sent` row with a null `sent_at` is
                                           not one either.

## THE COVERAGE RULE, WHICH IS THE WHOLE POINT

`overall_stats.emails_sent` is the provider's own count of every message this
lead has ever been sent, in any campaign, including campaigns this walk never
read. So the sends we found are checked against it:

    confirmed sent rows  <  overall_stats.emails_sent   ->  OUT

because the unread remainder could be last week. A lead is only in the cohort
when every message the provider says it sent has a dated `sent` row behind it.
MISSING EVIDENCE IS NEVER POSITIVE EVIDENCE.

## NO PROSPECT DATA LEAVES THIS SCRIPT

Lead ids, campaign ids, counts and timestamps. The lead payload carries name,
email, company and title and none of them is read, stored or printed.
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
LEADS_OUT = os.path.join(STAGE, "pc-leads.jsonl")
SENDS_OUT = os.path.join(STAGE, "pc-sends.jsonl")
LEAD_SENDS_OUT = os.path.join(STAGE, "pc-lead-sends.jsonl")
CAMPAIGNS_OUT = os.path.join(STAGE, "pc-campaigns.json")
#: Written by `--storenegatives`: every bison lead id our own store holds a
#: reply, stop, out-of-office or DNC for, ON ANY CHANNEL.
STORE_NEGATIVES = os.path.join(STAGE, "pc-store-negatives.json")

#: Seconds between requests. The estate is sending while this runs and the
#: provider it reads is the one that has to deliver today's mail.
THROTTLE = 0.25

REENGAGE_AFTER_DAYS = 90

#: A campaign in one of these is working its leads right now.
LIVE_CAMPAIGN = {"active", "in_progress", "running", "sending"}

#: A membership in one of these is a live sequence, whatever the campaign says.
LIVE_MEMBERSHIP = {"in_sequence", "sending", "active", "scheduled"}

#: Membership or queue-row states that are a bounce.
BOUNCE_STATES = {"bounced", "bounce", "hard_bounced", "soft_bounced"}

#: Membership or queue-row states that are an unsubscribe or a complaint.
UNSUB_STATES = {"unsubscribed", "unsubscribe", "opted_out", "complained",
                "complaint", "blocked", "suppressed"}

#: A queue row that proves a send. Nothing else does.
SENT_STATE = "sent"


def _now():
    return datetime.datetime.now(datetime.timezone.utc)


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


def _walk(what, url_of, cap):
    """Every row behind a paginated route, or a refusal. Never a page.

    `bison._paged` with a throttle and a page callback. The refusal contract
    is the same and is the reason this is not a hand-rolled loop: a short read
    of a membership reads as an absence, and an absence is what every clause
    below turns on.
    """
    rows, total, page, last = [], None, 1, None
    while True:
        status, data = request("GET", url_of(page), bison.headers())
        if not bison.ok(status):
            raise bison.ProviderError(f"{what}: page {page} -> {status}")
        chunk = (data or {}).get("data")
        if not isinstance(chunk, list):
            raise bison.ProviderError(
                f"{what}: the list is not a list; refusing to read an "
                f"unknown shape as an empty one")
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
                f"{what}: {last} pages and this read stops at {cap}. "
                f"Refusing to return {len(rows)} of {total} as though it "
                f"were all of them")
        page += 1
        time.sleep(THROTTLE)
    if isinstance(total, int) and len(rows) != total:
        raise bison.PartialInventory(
            f"{what}: meta.total says {total} and {len(rows)} arrived. "
            f"Refusing to report a partial read as a complete one")
    return rows


def _pages(url):
    """`meta.last_page` off page one, or None. One request, no walk."""
    status, data = request("GET", query(url, {"page": 1}), bison.headers())
    time.sleep(THROTTLE)
    if not bison.ok(status) or not isinstance(data, dict):
        return None
    meta = data.get("meta") if isinstance(data.get("meta"), dict) else {}
    try:
        return int(meta.get("last_page"))
    except (TypeError, ValueError):
        return None


def campaigns():
    """Every campaign in the bound workspace, with its CURRENT status."""
    rows = _walk("campaigns",
                 lambda p: query(f"{bison.base()}/campaigns", {"page": p}),
                 cap=bison.PAGE_CAP)
    out = {}
    for row in rows:
        if isinstance(row, dict) and row.get("id") is not None:
            out[int(row["id"])] = {
                "id": int(row["id"]),
                "status": str(row.get("status") or ""),
                # Name is a CAMPAIGN name, not a person's - it is how the US
                # subset is identified and the operator's own "289" used it.
                "name": str(row.get("name") or ""),
                "total_leads": row.get("total_leads"),
                "emails_sent": row.get("emails_sent"),
                "replied": row.get("replied"),
                "bounced": row.get("bounced"),
                "unsubscribed": row.get("unsubscribed"),
            }
    return out


def _trim_lead(row):
    """The lead, reduced to ids, counts and timestamps. No prospect data."""
    stats = row.get("overall_stats") if isinstance(
        row.get("overall_stats"), dict) else {}
    memberships = []
    for entry in row.get("lead_campaign_data") or []:
        if not isinstance(entry, dict):
            continue
        memberships.append({
            "campaign_id": entry.get("campaign_id"),
            "status": str(entry.get("status") or ""),
            "emails_sent": entry.get("emails_sent"),
            "replies": entry.get("replies"),
            "opens": entry.get("opens"),
            "interested": entry.get("interested"),
        })
    return {
        "lead_id": int(row["id"]),
        "updated_at": row.get("updated_at"),
        "created_at": row.get("created_at"),
        "verification": str(row.get("status") or ""),
        "overall_emails_sent": stats.get("emails_sent"),
        "overall_replies": stats.get("replies"),
        "overall_unique_replies": stats.get("unique_replies"),
        "overall_opens": stats.get("opens"),
        "memberships": memberships,
    }


def _trim_send(row):
    """One queue row, reduced. `lead` is read for its ID and nothing else."""
    lead = row.get("lead") if isinstance(row.get("lead"), dict) else {}
    return {
        "campaign_id": row.get("campaign_id"),
        "lead_id": lead.get("id"),
        "status": str(row.get("status") or ""),
        "sent_at": row.get("sent_at"),
        "scheduled_date": row.get("scheduled_date"),
        "replies": row.get("replies"),
        "step": row.get("sequence_step_id"),
    }


def walk(only=None, append=False):
    load_env()
    workspace = bison.bound_workspace()
    print(f"\nPROVIDER-CONFIRMED RE-ENGAGEMENT WALK - workspace "
          f"{workspace.get('id')} ({workspace.get('name')})")
    print(f"  started {_now():%Y-%m-%dT%H:%M}Z, throttle {THROTTLE}s\n")

    known = campaigns()
    if append and os.path.exists(CAMPAIGNS_OUT):
        with open(CAMPAIGNS_OUT, encoding="utf-8") as handle:
            for cid, meta in json.load(handle).items():
                known.setdefault(int(cid), {}).update(
                    {k: v for k, v in meta.items()
                     if k in ("lead_pages", "queue_pages")})
    with open(CAMPAIGNS_OUT, "w", encoding="utf-8") as handle:
        json.dump(known, handle, indent=1, sort_keys=True)
    print(f"  campaigns at the provider: {len(known)}")

    # A CAMPAIGN TOO BIG TO WALK IS MEASURED, NOT ATTEMPTED. The client's own
    # campaigns run to 96,000 queue rows over 6,403 pages; starting that walk
    # spends 400 pages before the refusal it was always going to reach. So
    # `last_page` is read off page one and the oversized ones are skipped by
    # name - and every lead whose sends are in one of them is then excluded by
    # rule 5 below rather than passed as clean.
    wanted = sorted(known) if only is None else [int(c) for c in only]
    sized = []
    for cid in wanted:
        pages = _pages(bison.leads_endpoint(cid))
        qpages = _pages(f"{bison.base()}/campaigns/{cid}/scheduled-emails")
        known.setdefault(cid, {})["lead_pages"] = pages
        known[cid]["queue_pages"] = qpages
        if pages is None or qpages is None:
            print(f"  {cid:>5} UNSIZEABLE - skipped, not assumed empty")
            continue
        if max(pages, qpages) > bison.CAMPAIGN_QUEUE_PAGE_CAP:
            print(f"  {cid:>5} TOO BIG ({pages} lead pages, {qpages} queue "
                  f"pages) - skipped by name, never attempted")
            continue
        sized.append(cid)
    wanted = sized
    with open(CAMPAIGNS_OUT, "w", encoding="utf-8") as handle:
        json.dump(known, handle, indent=1, sort_keys=True)
    print(f"  walking {len(wanted)} campaigns, "
          f"{sum(known[c]['lead_pages'] + known[c]['queue_pages'] for c in wanted)} "
          f"pages\n")
    mode = "a" if append else "w"
    leads = open(LEADS_OUT, mode, encoding="utf-8")
    sends = open(SENDS_OUT, mode, encoding="utf-8")
    try:
        for cid in wanted:
            meta = known.get(cid) or {}
            label = f"{cid:>5} {meta.get('status',''):<10}"
            try:
                rows = _walk(f"leads {cid}",
                             lambda p, c=cid: query(bison.leads_endpoint(c),
                                                    {"page": p}),
                             cap=bison.CAMPAIGN_QUEUE_PAGE_CAP)
            except Exception as exc:                            # noqa: BLE001
                print(f"  {label} LEADS UNREADABLE ({type(exc).__name__}) - "
                      f"every lead in it is OUT, not assumed clean")
                continue
            n_leads = 0
            for row in rows:
                if isinstance(row, dict) and row.get("id") is not None:
                    trimmed = _trim_lead(row)
                    trimmed["seen_in_campaign"] = cid
                    leads.write(json.dumps(trimmed) + "\n")
                    n_leads += 1
            leads.flush()
            try:
                queue = _walk(
                    f"queue {cid}",
                    lambda p, c=cid: query(
                        f"{bison.base()}/campaigns/{c}/scheduled-emails",
                        {"page": p}),
                    cap=bison.CAMPAIGN_QUEUE_PAGE_CAP)
            except Exception as exc:                            # noqa: BLE001
                print(f"  {label} leads {n_leads:>4}  QUEUE UNREADABLE "
                      f"({type(exc).__name__}) - no send in it is confirmable")
                continue
            n_sent = 0
            for row in queue:
                if not isinstance(row, dict):
                    continue
                trimmed = _trim_send(row)
                if trimmed["lead_id"] is None:
                    continue
                sends.write(json.dumps(trimmed) + "\n")
                if trimmed["status"].lower() == SENT_STATE and trimmed["sent_at"]:
                    n_sent += 1
            sends.flush()
            print(f"  {label} leads {n_leads:>4}  queue {len(queue):>5}  "
                  f"confirmed sent rows {n_sent:>5}")
    finally:
        leads.close()
        sends.close()
    print(f"\n  done {_now():%Y-%m-%dT%H:%M}Z")
    return 0


# ------------------------------------------------------------------ the rules


def load():
    leads = {}
    with open(LEADS_OUT, encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            # A lead in two walked campaigns arrives twice with an identical
            # payload; `memberships` and `overall_stats` are lead-wide.
            leads.setdefault(row["lead_id"], row)
            leads[row["lead_id"]].setdefault("seen_in", [])
            leads[row["lead_id"]]["seen_in"].append(row["seen_in_campaign"])
    sends = collections.defaultdict(list)
    with open(SENDS_OUT, encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            sends[int(row["lead_id"])].append(row)
    # THE PER-LEAD QUEUE IS THE COMPLETE ONE AND IT REPLACES THE OTHER.
    #
    # `GET /leads/{id}/scheduled-emails` returns every queue row for one
    # person ACROSS EVERY CAMPAIGN, including campaigns far too big to walk -
    # lead 133155 came back with 33 rows spanning five campaigns, 23 of them
    # dated `sent`, reconciling exactly with its `overall_stats.emails_sent`.
    # So where this read exists it is authoritative and the per-campaign rows
    # are dropped rather than merged: merging would double-count the campaigns
    # that appear in both.
    if os.path.exists(LEAD_SENDS_OUT):
        complete = {}
        with open(LEAD_SENDS_OUT, encoding="utf-8") as handle:
            for line in handle:
                row = json.loads(line)
                complete.setdefault(int(row["lead_id"]), []).append(row)
        for lead_id, rows in complete.items():
            sends[lead_id] = rows
            if lead_id in leads:
                leads[lead_id]["queue_complete"] = True
    with open(CAMPAIGNS_OUT, encoding="utf-8") as handle:
        known = {int(k): v for k, v in json.load(handle).items()}
    return leads, sends, known


def lead_queue(only=None):
    """Phase two: one person's WHOLE send history, for the leads that need it.

    Only the leads still standing after the reply, bounce, unsubscribe and
    live-sequence clauses are read - a lead already out because it replied
    does not need a send date. Resumable: ids already on disk are skipped.
    """
    load_env()
    leads, sends, known = load()
    for lead in leads.values():
        for cid in lead.get("seen_in") or []:
            if cid in known:
                known[cid]["walked"] = True
    done = set()
    if os.path.exists(LEAD_SENDS_OUT):
        with open(LEAD_SENDS_OUT, encoding="utf-8") as handle:
            for line in handle:
                done.add(int(json.loads(line)["lead_id"]))
    cheap = ("replied", "bounced", "unsubscribed", "live_sequence")
    wanted = []
    for lead_id, lead in sorted(leads.items()):
        if lead_id in done:
            continue
        if only is not None and lead_id not in set(only):
            continue
        clauses, _age, _n = assess(lead, sends.get(lead_id, []), known)
        if any(clauses[name] for name in cheap):
            continue
        wanted.append(lead_id)
    print(f"\n  per-lead queue reads needed: {len(wanted)} "
          f"({len(done)} already on disk)")
    handle = open(LEAD_SENDS_OUT, "a", encoding="utf-8")
    try:
        for n, lead_id in enumerate(wanted, 1):
            try:
                rows = _walk(f"lead queue {lead_id}",
                             lambda p, i=lead_id: query(
                                 f"{bison.base()}/leads/{i}/scheduled-emails",
                                 {"page": p}),
                             cap=bison.CAMPAIGN_QUEUE_PAGE_CAP)
            except Exception as exc:                            # noqa: BLE001
                # NOT written. A lead with no per-lead read keeps falling to
                # the `unread_campaign` clause, which is the fail-closed
                # answer. Writing an empty list would read as "never sent".
                print(f"    lead {lead_id}: {type(exc).__name__} - left "
                      f"unread, stays excluded")
                continue
            for row in rows:
                if not isinstance(row, dict):
                    continue
                trimmed = _trim_send(row)
                trimmed["lead_id"] = lead_id
                handle.write(json.dumps(trimmed) + "\n")
            if n % 50 == 0:
                handle.flush()
                print(f"    {n}/{len(wanted)} at {_now():%H:%M}Z")
            time.sleep(THROTTLE)
    finally:
        handle.close()
    print(f"  done {_now():%Y-%m-%dT%H:%M}Z")
    return 0


#: The clauses, in the order the funnel reports them. Each is a separate
#: question and each is counted on its own as well as in the disjoint funnel,
#: because "how many replied" and "how many were excluded FIRST for replying"
#: are different numbers and only the second one sums.
CLAUSES = ("replied", "bounced", "unsubscribed", "live_sequence",
           "unread_campaign", "unconfirmed_sends", "never_sent", "too_recent")


def assess(lead, rows, known, now=None):
    """Every clause evaluated INDEPENDENTLY. No short-circuit.

    Returns `(clauses, age, confirmed_sends)`. `clauses` carries one entry per
    clause - a reason string when it disqualifies, None when it does not - so a
    lead excluded for three reasons can be counted under all three. `verdict`
    below collapses that to one answer for the disjoint funnel.
    """
    now = now or _now()
    walked = {cid for cid, meta in known.items() if meta.get("walked")}
    out = dict.fromkeys(CLAUSES)
    memberships = lead.get("memberships") or []

    # 1. NO REPLY EVER, across every campaign the lead has ever been in.
    #    `overall_stats` is the lead's whole history at this provider, which is
    #    the "ever" that one membership string cannot answer. A lead who
    #    replied in April and was afterwards marked `stopped` still carries the
    #    reply here.
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

    # 2. NO BOUNCE.  3. NO UNSUBSCRIBE.
    #    Membership state and queue-row state are both consulted. This instance
    #    exposes NO suppression list - `/unsubscribes`, `/suppressions`,
    #    `/blocklist`, `/do-not-contact` are all 404 - so the campaign-level
    #    `unsubscribed` counter is the only other witness, and it is reported
    #    beside this rather than inferred from.
    for m in memberships:
        state = str(m.get("status") or "").lower()
        if state in BOUNCE_STATES and not out["bounced"]:
            out["bounced"] = f"campaign {m.get('campaign_id')} reads {state}"
        if state in UNSUB_STATES and not out["unsubscribed"]:
            out["unsubscribed"] = f"campaign {m.get('campaign_id')} reads {state}"
    for row in rows:
        state = row["status"].lower()
        if state in BOUNCE_STATES and not out["bounced"]:
            out["bounced"] = f"a queue row in {row.get('campaign_id')} bounced"
        if state in UNSUB_STATES and not out["unsubscribed"]:
            out["unsubscribed"] = (f"a queue row in {row.get('campaign_id')} "
                                   f"reads {state}")

    # 4. NOT IN A LIVE SEQUENCE ANYWHERE. A live membership inside a campaign
    #    whose status could not be read counts too: unknown is not dormant.
    for m in memberships:
        cid = m.get("campaign_id")
        member = str(m.get("status") or "").lower()
        if member not in LIVE_MEMBERSHIP:
            continue
        status = str((known.get(cid) or {}).get("status") or "").lower()
        if status in LIVE_CAMPAIGN:
            out["live_sequence"] = f"{member} in live campaign {cid}"
            break
        if cid not in known:
            out["live_sequence"] = f"{member} in campaign {cid}, status unread"
            break

    # 5. EVERY CAMPAIGN THAT SENT TO THIS LEAD MUST HAVE BEEN READ.
    #    Waived only by a COMPLETE per-lead queue read, which spans every
    #    campaign by construction and so cannot be missing one.
    for m in (() if lead.get("queue_complete") else memberships):
        cid = m.get("campaign_id")
        if (m.get("emails_sent") or 0) > 0 and cid not in walked:
            out["unread_campaign"] = (f"campaign {cid} sent "
                                      f"{m.get('emails_sent')} and its queue "
                                      f"was never read")
            break

    # 6/7/8. THE SENDS THEMSELVES.
    confirmed = [row for row in rows
                 if row["status"].lower() == SENT_STATE and row["sent_at"]]
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
    return out, age, len(confirmed)


def verdict(lead, rows, known, now=None):
    """(ok, clause, detail). The first clause that disqualifies, or None."""
    clauses, age, _n = assess(lead, rows, known, now=now)
    for name in CLAUSES:
        if clauses[name]:
            return False, name, clauses[name]
    return True, None, f"last confirmed send {age}d ago"


def report(now=None, emit=print):
    leads, sends, known = load()
    now = now or _now()
    for lead in leads.values():
        for cid in lead.get("seen_in") or []:
            if cid in known:
                known[cid]["walked"] = True
    walked = sorted(cid for cid, m in known.items() if m.get("walked"))

    funnel = collections.Counter()
    tally = collections.Counter()
    cohort, ages, per_lead = [], [], {}
    for lead_id, lead in sorted(leads.items()):
        rows = sends.get(lead_id, [])
        clauses, age, n_sent = assess(lead, rows, known, now=now)
        for name in CLAUSES:
            if clauses[name]:
                tally[name] += 1
        first = next((n for n in CLAUSES if clauses[n]), None)
        per_lead[lead_id] = (first, age, n_sent)
        if first:
            funnel[first] += 1
        else:
            cohort.append(lead_id)
            ages.append(age)

    emit("")
    emit(f"PROVIDER-CONFIRMED RE-ENGAGEMENT COHORT  {now:%Y-%m-%dT%H:%M}Z")
    emit(f"  campaigns walked: {len(walked)} of {len(known)} in the workspace")
    emit(f"  leads read at the provider: {len(leads)}")
    emit(f"  queue rows read: {sum(len(v) for v in sends.values())}")
    emit("")
    emit("  THE FUNNEL - disjoint, first clause that disqualifies")
    emit(f"    base, leads read                                {len(leads):>6}")
    for name in CLAUSES:
        emit(f"      - {name:<42} {funnel[name]:>6}")
    emit(f"    = COHORT                                        {len(cohort):>6}")
    emit(f"    check sum {sum(funnel.values()) + len(cohort)}")
    emit("")
    emit("  EVERY CLAUSE COUNTED SEPARATELY - a lead may trip several")
    for name in CLAUSES:
        emit(f"      {name:<44} {tally[name]:>6}")
    if ages:
        emit("")
        emit(f"  cohort last-send age: min {min(ages)}d  max {max(ages)}d")
    by_campaign = collections.Counter()
    for lead_id in cohort:
        for cid in sorted(set(leads[lead_id].get("seen_in") or [])):
            by_campaign[cid] += 1
    emit("")
    emit("  COHORT BY CAMPAIGN WALKED IN")
    for cid, n in sorted(by_campaign.items()):
        meta = known.get(cid) or {}
        emit(f"      {cid:>5} {meta.get('status',''):<10} {n:>6}")

    # THE STORE IS A SECOND SOURCE, NOT A SECOND OPINION.
    #
    # EmailBison's reply history is PER CHANNEL. Two people in this estate
    # replied on LinkedIn through HeyReach: our store holds the reply, and
    # `GET /leads/{id}/replies` at EmailBison returns 0 for them because the
    # message never touched EmailBison. So the provider cannot, even in
    # principle, answer "no reply EVER" on its own, and the store's own
    # negatives are applied on top as an EXTRA exclusion. It is never allowed
    # to admit a lead the provider excluded.
    removed = []
    if os.path.exists(STORE_NEGATIVES):
        with open(STORE_NEGATIVES, encoding="utf-8") as handle:
            negatives = {int(k): v for k, v in json.load(handle).items()}
        removed = [i for i in cohort if i in negatives]
        cohort = [i for i in cohort if i not in negatives]
        emit("")
        emit(f"  STORE CROSS-CHECK (all channels): {len(negatives)} leads carry "
             f"a reply, stop or DNC")
        emit(f"    removed from the provider-confirmed cohort: {len(removed)}")
        emit(f"  FINAL COHORT {len(cohort)}")
    return per_lead, cohort, leads, sends, known



#: Contact-level events that mean this person has already answered, been
#: stopped, or must not be mailed. Record-level flags are handled separately
#: because they are about the COMPANY.
CONTACT_NEGATIVES = ("reply_received", "positive_reply_detected",
                     "reply_classified", "contact_stopped",
                     "provider_stop_confirmed", "out_of_office_recorded")


def store_negatives():
    """Write every bison lead id our store holds a negative for. No network.

    THE ATTRIBUTION IS PER CONTACT, NOT PER RECORD, and getting that wrong is
    how a clean lead reads as a replier. An event names its contact in
    `event["contact"]`, which matches `contact["key"]` - and 109 of the 1,582
    records carry more than one contact. Spreading a record's reply across
    every contact on it reported EIGHT leads as "the store says replied and
    the provider says nothing"; every one of those eight was a colleague of
    the person who actually replied, and the provider was right.

    The record-level flags (`do_not_contact`, `paused`) ARE company-wide and
    are applied to every contact on the record, which is what they mean.
    """
    from src import store                                   # noqa: PLC0415

    out = {}
    for record in store.load():
        contacts = record.get("contacts") or []
        by_key = {c.get("key"): c for c in contacts}
        every = [int(c["bison_lead_id"]) for c in contacts
                 if c.get("bison_lead_id")]
        if record.get("do_not_contact") or record.get("paused"):
            for lead_id in every:
                out.setdefault(str(lead_id), {}).setdefault(
                    "record_dnc_or_paused", ["record"])
        for event in record.get("events") or []:
            if not isinstance(event, dict):
                continue
            if event.get("type") not in CONTACT_NEGATIVES:
                continue
            contact = by_key.get(event.get("contact"))
            if not contact or not contact.get("bison_lead_id"):
                continue
            entry = out.setdefault(str(int(contact["bison_lead_id"])), {})
            channels = set(entry.get(event["type"]) or [])
            channels.add(str(event.get("channel") or "?"))
            entry[event["type"]] = sorted(channels)
    with open(STORE_NEGATIVES, "w", encoding="utf-8") as handle:
        json.dump(out, handle, indent=0, sort_keys=True)
    print(f"  store negatives written: {len(out)} bison lead ids")
    return 0


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--walk", action="store_true")
    p.add_argument("--report", action="store_true")
    p.add_argument("--only", nargs="*", type=int)
    p.add_argument("--leadqueue", action="store_true")
    p.add_argument("--storenegatives", action="store_true")
    p.add_argument("--append", action="store_true")
    args = p.parse_args(argv)
    if args.walk:
        return walk(only=args.only, append=args.append)
    if args.leadqueue:
        return lead_queue(only=args.only)
    if args.storenegatives:
        return store_negatives()
    if args.report:
        # `--report` reads the three staged files and makes NO provider call,
        # which is the difference between it and `--walk`.
        report()
        return 0
    p.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
