#!/usr/bin/env python3
"""The LinkedIn side of "no reply ever", for the re-engagement cohort.

    py -3 scripts/reengagement_linkedin_lane_i.py --read

READ-ONLY. Every call goes through `heyreach._read`, which refuses any path
not on `READ_ROUTES_ALL`. Nothing is added, stopped, paused or created.

## THE QUESTION AND THE TWO REASONS IT IS HARD

`docs/REENGAGEMENT-COHORT-PROVIDER-CONFIRMED-2026-09-24.md` §6 says plainly:
*"HeyReach was not read at all this session"*, and §5.1 shows why that
matters - two leads replied on LinkedIn and EmailBison returns 0 replies for
both, because the message never touched EmailBison.

Two things stand between us and an answer, and they are different:

1. **THE KEY IS WORKSPACE-WIDE AND THE INBOX IS MOSTLY THE CLIENT'S.**
   26,973 conversations; of the 400 most recent, 12 end with a correspondent
   message and none matches any record of ours (REFUTED-006). A seat is not a
   campaign. So a reply is only OURS when it sits in a campaign the provider
   says we created, and this script asks the provider which those are rather
   than trusting `inbound.OWNED_CAMPAIGNS` - four HeyReach ids that a register
   row records being compared against EmailBison event ids without asking
   which provider they came from.

2. **THE BINDING IS STRUCTURALLY ABSENT.** `heyreach_lead_id` is carried by
   ONE contact in the whole store. So "no LinkedIn reply recorded" is not
   evidence of no reply; for almost every lead it is evidence that nothing
   could ever have recorded one. The join that does exist is
   `bison_lead_id -> contact -> linkedin url`, and it only exists for the
   minority of cohort members our store knows at all.

This script therefore reports THREE numbers and never collapses them:
answerable-and-clean, answerable-and-dirty, and STRUCTURALLY UNANSWERABLE.
"""
import argparse
import collections
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.providers import heyreach, load_env                  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STAGE = os.path.join(ROOT, "work", "stage")
RI_COHORT = os.path.join(STAGE, "ri-cohort.json")
RI_LINKEDIN = os.path.join(STAGE, "ri-linkedin.json")

READBACK = os.path.join(ROOT, "docs", "state", "PROVIDER-CAMPAIGNS.json")

#: A HeyReach lead state that means this person answered on LinkedIn.
REPLY_STATES = {heyreach.REPLIED}
#: ... and one that means they are being worked right now.
LIVE_STATES = {heyreach.REQUEST_PENDING, heyreach.REQUEST_SENT,
               heyreach.ACCEPTED}


def _now():
    return datetime.datetime.now(datetime.timezone.utc)


def _ours():
    """Campaign ids the provider readback says WE created, and its age.

    The readback is a floor, never a ceiling, and its age is reported rather
    than swallowed: `inbound._owned` refuses to license a drop on a readback
    older than 24h, and the same caution applies to calling a reply ours.
    `scripts/provider_truth.py` is NOT run from here - the 2026-09-24 handoff
    §6 item 1 forbids it until `inbound.OWNED_CAMPAIGNS` resolves per provider.
    """
    with open(READBACK, encoding="utf-8") as handle:
        data = json.load(handle)
    block = (data or {}).get("heyreach") or {}
    ids = set()
    for row in block.get("resonate_campaigns") or []:
        cid = row.get("heyreach_campaign_id")
        if cid is not None:
            ids.add(int(cid))
    stamp = data.get("generated_at")
    at = datetime.datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
    if at.tzinfo is None:
        at = at.replace(tzinfo=datetime.timezone.utc)
    return ids, stamp, (_now() - at).total_seconds() / 3600.0


def _store_contacts():
    """bison lead id -> the LinkedIn identity our store holds for it.

    REFUSES ON AN EMPTY STORE, and that refusal is not decoration. The first
    run of this script reported "0 of 1,040 join a store contact" and the
    number was an artefact: it ran inside a worktree, `store.queue_path()`
    resolved to that worktree's own `work/queue.jsonl`, which does not exist,
    and an absent file read as a store holding nobody. An empty join is
    indistinguishable from a complete miss, and this lane's whole subject is
    the difference between those two. Point `QUEUE` at production's file.
    """
    from src import store                                    # noqa: PLC0415
    records = store.load()
    if not records:
        raise RuntimeError(
            f"the store at {store.queue_path()} holds no records. That is a "
            f"path fault, not a finding: set QUEUE to production's "
            f"work/queue.jsonl. Refusing to report an empty join as an "
            f"answered question")
    out = {}
    for record in records:
        for contact in record.get("contacts") or []:
            bid = contact.get("bison_lead_id")
            if not bid:
                continue
            out[int(bid)] = {
                "record": record.get("id"),
                "domain": record.get("domain"),
                "linkedin": contact.get("linkedin"),
                "heyreach_lead_id": contact.get("heyreach_lead_id"),
                "heyreach_campaign_id": contact.get("heyreach_campaign_id"),
            }
    return out


def read():
    load_env()
    with open(RI_COHORT, encoding="utf-8") as handle:
        cohort_blob = json.load(handle)
    cohort = [int(i) for i in cohort_blob["cohort"]]

    ours, stamp, age_h = _ours()
    print(f"\nLANE I LINKEDIN READ  {_now():%Y-%m-%dT%H:%M:%S}Z")
    print(f"  ownership readback {stamp} ({age_h:.0f}h old, "
          f"{'STALE' if age_h > 24 else 'fresh'})")
    print(f"  campaigns the readback says are ours: {len(ours)}")

    # 1. WHAT THE WORKSPACE HOLDS RIGHT NOW, asked of the provider.
    rows, total = [], None
    offset = 0
    while True:
        page, count = heyreach.campaigns(offset=offset, limit=50)
        if total is None:
            total = count
        rows += page
        offset += len(page)
        if not page or (isinstance(total, int) and offset >= total):
            break
        if offset > 5000:
            raise RuntimeError("campaign listing did not terminate")
    by_id = {}
    for row in rows:
        cid = row.get("id")
        if cid is None:
            continue
        by_id[int(cid)] = {"name": str(row.get("name") or ""),
                           "status": str(row.get("status") or "")}
    print(f"  campaigns in the workspace: {len(by_id)} "
          f"(provider totalCount {total})")
    mine = {cid: meta for cid, meta in by_id.items() if cid in ours}
    theirs = {cid: meta for cid, meta in by_id.items() if cid not in ours}
    print(f"    ours per the readback:   {len(mine)}")
    print(f"    NOT ours / unclassified: {len(theirs)}")
    live_theirs = {c: m for c, m in theirs.items()
                   if m["status"].upper() in ("IN_PROGRESS", "STARTED")}
    print(f"    of theirs, running now:  {len(live_theirs)}")

    # 2. HAVE OUR OWN LINKEDIN CAMPAIGNS TAKEN A REPLY AT ALL?
    #    This is per CAMPAIGN, which is the unit of ownership. A seat total
    #    would carry the client's traffic and is not asked for.
    stats, replies_total, unreadable = {}, 0, []
    for cid in sorted(mine):
        try:
            stat = heyreach.campaign_stats(cid)
        except Exception as exc:                              # noqa: BLE001
            unreadable.append(cid)
            print(f"    {cid} stats UNREADABLE ({type(exc).__name__}) - "
                  f"counted as unknown, never as zero")
            continue
        stats[cid] = stat
        replies_total += int(stat.get("totalMessageReplies") or 0)
    print(f"\n  OUR HEYREACH CAMPAIGNS, per the provider's own counters")
    print(f"    campaigns with readable stats: {len(stats)} of {len(mine)}")
    print(f"    connections sent:      "
          f"{sum(int(s.get('connectionsSent') or 0) for s in stats.values())}")
    print(f"    connections accepted:  "
          f"{sum(int(s.get('connectionsAccepted') or 0) for s in stats.values())}")
    print(f"    unique leads contacted:"
          f"{sum(int(s.get('uniqueLeadsContacted') or 0) for s in stats.values())}")
    print(f"    TOTAL MESSAGE REPLIES: {replies_total}")

    # 3. THE JOIN, AND THE SIZE OF THE HOLE.
    contacts = _store_contacts()
    joinable = {i: contacts[i] for i in cohort if i in contacts}
    with_li = {i: c for i, c in joinable.items() if c.get("linkedin")}
    print(f"\n  THE JOIN FROM THIS COHORT TO LINKEDIN")
    print(f"    cohort leads                                  {len(cohort):>6}")
    print(f"    joined to a store contact by bison_lead_id    {len(joinable):>6}")
    print(f"    of those, carrying a LinkedIn URL             {len(with_li):>6}")
    print(f"    carrying a heyreach_lead_id                   "
          f"{sum(1 for c in joinable.values() if c.get('heyreach_lead_id')):>6}")
    print(f"    STRUCTURALLY UNANSWERABLE on LinkedIn         "
          f"{len(cohort) - len(with_li):>6}")

    # 4. ASK THE PROVIDER ABOUT THE ONES WE CAN ASK ABOUT.
    # UNREADABLE IS NOT REPLIED, and the first version of this script conflated
    # them: an exception appended the lead to `dirty` and it was then printed
    # under "leads reading REPLIED on LinkedIn". That is a fabricated exclusion
    # reason - the provider never said it. Unreadable excludes (fail closed)
    # under its own name, and is reported separately.
    per_lead, dirty, live, unreadable_leads = {}, [], [], []
    for lead_id, contact in sorted(with_li.items()):
        try:
            found, _count = heyreach.campaigns_for_lead(
                profile_url=contact["linkedin"])
        except Exception as exc:                              # noqa: BLE001
            per_lead[lead_id] = {"error": f"{type(exc).__name__}: {exc}"}
            unreadable_leads.append(lead_id)
            continue
        entries = []
        for row in found:
            cid = row.get("campaignId")
            entries.append({
                "campaign_id": cid,
                "ours": cid in ours,
                "campaign_status": row.get("campaignStatus"),
                "lead_status": row.get("leadStatus"),
            })
        per_lead[lead_id] = {"campaigns": entries}
        for entry in entries:
            word = str(entry["lead_status"] or "").strip().lower()
            if word in ("replied", "messagereply"):
                dirty.append(lead_id)
            if word in ("insequence", "pending") and \
                    str(entry["campaign_status"] or "").upper() in (
                        "IN_PROGRESS", "STARTED"):
                live.append(lead_id)
    ours_live = sorted({i for i in live
                        for e in per_lead[i]["campaigns"]
                        if e["ours"] and str(e["lead_status"] or "").lower()
                        in ("insequence", "pending")
                        and str(e["campaign_status"] or "").upper()
                        in ("IN_PROGRESS", "STARTED")})
    print(f"\n  PER-LEAD LINKEDIN READ ({len(with_li)} asked)")
    print(f"    leads the provider places in a LinkedIn campaign   "
          f"{sum(1 for v in per_lead.values() if v.get('campaigns')):>6}")
    print(f"    leads the provider could not answer for            "
          f"{len(set(unreadable_leads)):>6}")
    print(f"    leads reading REPLIED on LinkedIn                  "
          f"{len(set(dirty)):>6}")
    print(f"    leads in a LIVE LinkedIn sequence                  "
          f"{len(set(live)):>6}")
    print(f"      of those, live in a campaign WE own              "
          f"{len(ours_live):>6}")

    payload = {
        "read_at": f"{_now():%Y-%m-%dT%H:%M:%S}Z",
        "ownership_readback": {"generated_at": stamp, "age_hours": age_h,
                               "campaign_ids": sorted(ours)},
        "workspace_campaigns": len(by_id),
        "ours": sorted(mine),
        "theirs_running_now": len(live_theirs),
        "our_campaign_stats": {str(k): v for k, v in stats.items()},
        "our_stats_unreadable": unreadable,
        "our_total_message_replies": replies_total,
        "cohort_size": len(cohort),
        "joined_to_store": sorted(joinable),
        "joined_with_linkedin_url": sorted(with_li),
        "structurally_unanswerable": len(cohort) - len(with_li),
        "per_lead": {str(k): v for k, v in per_lead.items()},
        "linkedin_replied": sorted(set(dirty)),
        "linkedin_live": sorted(set(live)),
        "linkedin_live_in_our_campaign": ours_live,
        "linkedin_unreadable": sorted(set(unreadable_leads)),
    }
    with open(RI_LINKEDIN, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=1, sort_keys=True)
    print(f"\n  written {RI_LINKEDIN}")
    return 0


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--read", action="store_true")
    args = p.parse_args(argv)
    if args.read:
        return read()
    p.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
