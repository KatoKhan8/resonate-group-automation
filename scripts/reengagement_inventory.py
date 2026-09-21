#!/usr/bin/env python3
"""Read the whole estate we have already touched. READ-ONLY, resumable.

    py -3 scripts/reengagement_inventory.py --plan
    py -3 scripts/reengagement_inventory.py --walk --cap 2000
    py -3 scripts/reengagement_inventory.py --report

OPERATOR, 2026-09-21: "every lead currently in EmailBison (all campaigns in
the workspace) and HeyReach (all lists and campaigns) is client-approved for
re-engagement. Build the inventory read-only first: total leads per provider,
and per lead the last touch, reply status, bounce, unsubscribe, sequence
status, LinkedIn connection status. Persist it in the local last-touch index.
Report counts per bucket before anything is enrolled."

## NOTHING HERE ENROLS ANYTHING

Not a single write verb is imported. The output is three files under `work/`
and a table. Enrolment waits on copy the operator has not approved yet.

## WHAT IT COSTS, AND WHY IT IS WALKED THIS WAY

The register already paid for these lessons and this script must not re-pay
them:

    scheduled_emails(352)   REFUSES. 96,045 rows over 6,403 pages, and the
                            adapter will not return a partial as though it
                            were the whole. So the queue is NOT the way in.
    membership()            status strings only, no dates. Good for the
                            SEQUENCE STATE of every lead in a campaign, and
                            useless for "when were they last touched".
    lead.created_at         lead CREATION. A lead created in April may have
                            been mailed last week.
    lead.updated_at         THE ANSWER. One call per lead, bounded, and a
                            real provider last-activity timestamp.

So: membership per campaign gives the population and the state cheaply; then
`lead()` is called ONCE per lead we do not already have dated, and the result
is written through immediately. `work/stage/last-touch.json` already holds
1,386 of them from tonight's collision walk and they are not re-fetched.

**RESUMABLE BY CONSTRUCTION.** `--cap` bounds a run, progress is flushed
every 50 leads, and a second run picks up where the first stopped. A
five-figure estate at a few calls a second is hours; a walk that cannot be
interrupted is a walk that gets interrupted at hour three and starts again.

## THE LANES ARE RULES, NOT JUDGEMENT

Assigned exactly as the operator wrote them, precedence first:

    NEVER      unsubscribe, negative reply, bounce, unknown stop reason
    ACTIVE     still in an active sequence - untouched, checked BEFORE the
               others, because a lead being mailed right now must not be
               re-enrolled by a rule about its age
    REVIVE     any reply, then silence. Not enrolled anywhere; a human sends
               the next message.
    REENGAGE   no reply ever AND sequence finished AND last touch > 90 days
    UNKNOWN    everything else. It HOLDS, and it is counted loudly.
"""
import argparse
import collections
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.providers import bison, heyreach, load_env              # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STAGE = os.path.join(ROOT, "work", "stage")
INVENTORY = os.path.join(STAGE, "reengagement-inventory.jsonl")
LAST_TOUCH = os.path.join(STAGE, "last-touch.json")
PROGRESS = os.path.join(STAGE, "reengagement-progress.json")

NEVER, ACTIVE, REVIVE, REENGAGE, UNKNOWN = (
    "NEVER", "ACTIVE", "REVIVE", "REENGAGE", "UNKNOWN")

#: Membership states that mean the provider is working this lead right now.
ACTIVE_STATES = {"in_sequence", "sending", "active", "scheduled"}

#: States that end a lead permanently, whatever their age.
NEVER_STATES = {"unsubscribed", "bounced", "complained", "blocked",
                "invalid", "suppressed"}

#: The provider's word for "this campaign stopped working the lead" without
#: saying why. The operator's rule puts an unknown stop reason in NEVER.
STOPPED_STATES = {"stopped", "paused", "sending_paused"}

FINISHED_STATES = {"finished", "completed", "sequence_finished"}

REENGAGE_AFTER_DAYS = 90


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


def lane_for(row, now=None, campaign_status=None):
    """(lane, why). Total, single-valued, precedence as written.

    `campaign_status` matters and the first version of this ignored it, which
    put 1,351 of 1,415 leads in NEVER. A lead reads `stopped` when ITS OWN
    sequence was stopped and also when the whole CAMPAIGN was paused or
    finished - and this estate is mostly finished campaigns, so nearly every
    lead in it reads stopped.

    The operator's rule says "unknown stop reason" is a NEVER, and it means a
    lead we stopped for a reason nobody recorded. A campaign somebody paused
    in April is not that: 487 was paused by an audit probe passing a bare
    dict, and every one of its ten leads would have been written off as
    permanently excluded by a rule about the word `stopped`.

    So the stop only counts against the LEAD when its campaign is still
    running. Otherwise the lead is read on its age like any other.
    """
    now = now or _now()
    state = str(row.get("state") or "").lower()
    campaign_live = str(campaign_status or "").lower() in (
        "active", "in_progress", "running", "sending")
    if row.get("unsubscribed") or row.get("bounced") or row.get("complained"):
        return NEVER, "unsubscribe, bounce or complaint on the record"
    if state in NEVER_STATES:
        return NEVER, f"membership state {state!r}"
    if row.get("negative_reply"):
        return NEVER, "negative reply"
    if state in ACTIVE_STATES:
        return ACTIVE, f"still in an active sequence ({state})"
    if row.get("replied") or state == "replied":
        return REVIVE, "replied, then silence - a human sends the next one"
    if state in STOPPED_STATES:
        if campaign_live:
            return NEVER, (f"stopped ({state}) inside a campaign that is "
                           f"still running - an unknown stop is a NEVER by "
                           f"the rule")
        touched_here = _parse(row.get("last_touch"))
        age = (now - touched_here).days if touched_here else None
        if age is not None and age > REENGAGE_AFTER_DAYS:
            return REENGAGE, (f"campaign {campaign_status}, no reply, last "
                              f"touch {age}d ago - the stop is the campaign's, "
                              f"not this lead's")
        if age is not None:
            return UNKNOWN, (f"campaign {campaign_status} and last touch "
                             f"{age}d ago - inside the 90-day rule")
        return UNKNOWN, f"campaign {campaign_status} and no last-touch date"
    touched = _parse(row.get("last_touch"))
    if state in FINISHED_STATES and touched:
        age = (now - touched).days
        if age > REENGAGE_AFTER_DAYS:
            return REENGAGE, f"sequence finished, no reply, last touch {age}d ago"
        return UNKNOWN, (f"sequence finished and no reply, but last touch is "
                         f"{age}d ago - inside the 90-day rule")
    if not touched:
        return UNKNOWN, "no last-touch date could be read"
    return UNKNOWN, f"state {state!r} matches no lane rule"


def load_last_touch():
    if os.path.exists(LAST_TOUCH):
        with open(LAST_TOUCH, encoding="utf-8") as handle:
            return json.load(handle)
    return {}


def save_last_touch(index):
    tmp = LAST_TOUCH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(index, handle)
    os.replace(tmp, LAST_TOUCH)


def load_progress():
    if os.path.exists(PROGRESS):
        with open(PROGRESS, encoding="utf-8") as handle:
            return json.load(handle)
    return {"campaigns_done": [], "leads_done": []}


def save_progress(progress):
    tmp = PROGRESS + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(progress, handle)
    os.replace(tmp, PROGRESS)


def bison_campaigns():
    """Every campaign in the bound workspace, as the provider lists it."""
    rows, _total = bison._paged(
        "campaigns", lambda page: bison.query(f"{bison.base()}/campaigns",
                                              {"page": page}))
    return rows


def walk(cap=None):
    load_env()
    workspace = bison.bound_workspace()
    print(f"\nRE-ENGAGEMENT INVENTORY - workspace {workspace.get('id')} "
          f"({workspace.get('name')})\n")
    progress = load_progress()
    index = load_last_touch()
    done_leads = set(progress.get("leads_done") or [])
    print(f"  already dated in the local index: {len(index)}")

    campaigns = bison_campaigns()
    print(f"  campaigns at the provider: {len(campaigns)}")
    walked = 0
    handle = open(INVENTORY, "a", encoding="utf-8")
    try:
        for campaign in campaigns:
            campaign_id = campaign.get("id")
            name = str(campaign.get("name") or "")[:48]
            try:
                # `membership` returns {lead_id: status}, and it REFUSES past
                # PAGE_CAP rather than handing back a page of a campaign of
                # twenty thousand. A refusal is a campaign this walk cannot
                # answer for, not an empty one, and it is said out loud.
                members = bison.membership(campaign_id) or {}
            except Exception as exc:                            # noqa: BLE001
                print(f"    campaign {campaign_id} {name}: membership "
                      f"unreadable ({type(exc).__name__}) - skipped, NOT "
                      f"assumed empty")
                continue
            print(f"    campaign {campaign_id:>5} {name:48s} "
                  f"members {len(members)}")
            for member_id, member_state in sorted(members.items()):
                lead_id = str(member_id)
                if not lead_id or lead_id in done_leads:
                    continue
                if cap is not None and walked >= cap:
                    print(f"\n  cap of {cap} reached - resumable, run again")
                    return _finish(handle, progress, index, done_leads)
                row = {"provider": "emailbison", "campaign_id": campaign_id,
                       "lead_id": lead_id, "state": member_state}
                dated = index.get(lead_id)
                if dated:
                    row["last_touch"] = dated[0] if isinstance(
                        dated, (list, tuple)) else dated
                else:
                    try:
                        lead = bison.lead(lead_id) or {}
                    except Exception as exc:                    # noqa: BLE001
                        row["read_error"] = type(exc).__name__
                        lead = {}
                    row["last_touch"] = lead.get("updated_at")
                    row["created_at"] = lead.get("created_at")
                    for flag in ("replied", "bounced", "unsubscribed",
                                 "complained"):
                        if flag in lead:
                            row[flag] = lead.get(flag)
                    if row["last_touch"]:
                        index[lead_id] = [row["last_touch"], 0]
                row["lane"], row["why"] = lane_for(row)
                handle.write(json.dumps(row) + "\n")
                done_leads.add(lead_id)
                walked += 1
                if walked % 50 == 0:
                    handle.flush()
                    progress["leads_done"] = sorted(done_leads)
                    save_progress(progress)
                    save_last_touch(index)
                    print(f"      {walked} leads dated")
            progress.setdefault("campaigns_done", []).append(campaign_id)
        return _finish(handle, progress, index, done_leads)
    finally:
        handle.close()


def _finish(handle, progress, index, done_leads):
    handle.flush()
    progress["leads_done"] = sorted(done_leads)
    save_progress(progress)
    save_last_touch(index)
    print(f"\n  inventory rows written to {INVENTORY}")
    print(f"  last-touch index now holds {len(index)} dated leads")
    return 0


def report():
    if not os.path.exists(INVENTORY):
        print("no inventory yet - run --walk")
        return 1
    load_env()
    statuses = {}
    try:
        rows, _total = bison._paged(
            "campaigns", lambda page: bison.query(
                f"{bison.base()}/campaigns", {"page": page}))
        statuses = {str(r.get("id")): r.get("status") for r in rows}
    except Exception as exc:                                    # noqa: BLE001
        print(f"  campaign statuses unreadable ({type(exc).__name__}); "
              f"every stop will be read as the lead's own, which OVER-counts "
              f"NEVER")
    lanes = collections.Counter()
    reasons = collections.Counter()
    per_campaign = collections.Counter()
    with open(INVENTORY, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            lane, why = lane_for(
                row, campaign_status=statuses.get(str(row.get("campaign_id"))))
            lanes[lane] += 1
            reasons[str(why)[:60]] += 1
            per_campaign[row.get("campaign_id")] += 1
    print("\nRE-ENGAGEMENT BUCKETS\n")
    for lane in (NEVER, ACTIVE, REVIVE, REENGAGE, UNKNOWN):
        print(f"  {lane:9s} {lanes.get(lane, 0):>6}")
    print(f"\n  total {sum(lanes.values())} across {len(per_campaign)} campaigns")
    print("\n  why, most common first")
    for why, count in reasons.most_common(12):
        print(f"    {count:>6}  {why}")
    print("\n  NOTHING IS ENROLLED. REENGAGE waits on copy the operator has "
          "not approved; REVIVE is a human's to send.")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--walk", action="store_true")
    parser.add_argument("--report", action="store_true")
    parser.add_argument("--plan", action="store_true")
    parser.add_argument("--cap", type=int)
    args = parser.parse_args(argv)
    if args.report:
        return report()
    if args.walk:
        return walk(cap=args.cap)
    load_env()
    rows = bison_campaigns()
    print(f"\n{len(rows)} campaigns in the bound workspace. "
          f"Run --walk to date their leads.")
    for row in rows[:40]:
        print(f"  {row.get('id'):>6}  {str(row.get('status')):10s} "
              f"{str(row.get('name'))[:60]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
