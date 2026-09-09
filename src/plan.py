#!/usr/bin/env python3
"""How big this campaign really is, and how many days it actually takes.

Two questions get answered badly by everyone before they get answered well.
The first is "how many emails is this?", where the honest answer is much
smaller than the domain count — a 5,000-domain upload is not 5,000 people,
because contacts are selected, addresses fail verification, gateways block and
companies pause. The second is "when is it done?", where the honest answer is
governed by the daily volume cap rather than the cadence: seven steps over
twenty-one days is the *shape*, but two hundred emails a day is the *rate*, and
at 5,000 domains the rate decides everything.

Both are computed from stored state with no network and no provider call. The
plan below never sends, and a test reads this module's source to keep it that
way: no push, no provider request, no provider module.

  python -m src.plan --campaign q3-cold
  python -m src.plan --campaign q3-cold --days 40 --json
"""
import argparse
import json

from . import (cadence, campaigns, clients, eligibility, ingest, lint,
               mx, personalization, store)

# A working week. A campaign that "takes 25 days" over weekends is a campaign
# that takes five weeks, and saying 25 to a client is how you get asked why it
# is late.
SENDING_DAYS_PER_WEEK = 5


def _records(campaign, recs):
    if campaign is None:
        return list(recs)
    ids = set(campaign.get("record_ids") or [])
    return [r for r in recs if r.get("id") in ids]


def size(campaign=None, recs=None, config=None):
    """What this campaign contains, counted at every narrowing point.

    The interesting number is not any single total but the drop between them:
    that is where a client's five thousand domains became eight hundred
    conversations, and it is the first thing anyone asks about.
    """
    recs = store.load() if recs is None else recs
    mine = _records(campaign, recs)
    if config is None:
        client = (campaign or {}).get("client") or (
            mine[0].get("client") if mine else None)
        try:
            config = clients.load(client)
        except Exception:
            config = {}

    counts = {
        "domains": len(mine),
        "domains_qualified": 0,
        "domains_paused": 0,
        "contacts_found": 0,
        "contacts_selected": 0,
        "contacts_emailable": 0,
        "contacts_mx_blocked": 0,
        "contacts_linkedin": 0,
        "contacts_unreachable": 0,
        "email_steps": 0,
        "linkedin_steps": 0,
        "steps_already_pushed": 0,
    }

    paused_set = cadence.paused_domains(recs)
    for rec in mine:
        if cadence.pause_state(rec):
            counts["domains_paused"] += 1
        if rec.get("state") != "dropped" and not rec.get("drop_reason"):
            counts["domains_qualified"] += 1
        contacts = rec.get("contacts") or []
        counts["contacts_found"] += len(contacts)
        selected = personalization.selected_contacts(rec, config)
        counts["contacts_selected"] += len(selected)
        for contact in selected:
            emailable = lint.sendable(contact)
            allowed, _ = mx.allows_email(contact, config)
            if emailable and not allowed:
                counts["contacts_mx_blocked"] += 1
            if emailable and allowed:
                counts["contacts_emailable"] += 1
            if contact.get("linkedin"):
                counts["contacts_linkedin"] += 1
            if not (emailable and allowed) and not contact.get("linkedin"):
                counts["contacts_unreachable"] += 1

        timeline = cadence.build(rec, config, paused_set=paused_set,
                                 campaign=campaign)
        for steps in (timeline.get("contacts") or {}).values():
            for step in steps.values():
                if step.get("status") == "pushed":
                    counts["steps_already_pushed"] += 1
                    continue
                if step.get("channel") == "linkedin":
                    counts["linkedin_steps"] += 1
                else:
                    counts["email_steps"] += 1

    counts["total_steps"] = counts["email_steps"] + counts["linkedin_steps"]
    # What it would cost in model calls if every generated step were regenerated
    # from scratch. Named as a ceiling, because most are already written.
    counts["llm_calls_if_regenerated"] = (counts["contacts_selected"]
                                          * len(cadence.GENERATED_KEYS))
    return counts


def _caps(campaign, config):
    """Daily volume, from the campaign first and the client config second."""
    volume = (campaign or {}).get("daily_volume") or {}
    fallback = ((config or {}).get("sending") or {}).get("daily_volume") or {}
    email = volume.get("email") or fallback.get("email") or 0
    linkedin = volume.get("linkedin") or fallback.get("linkedin") or 0
    return {"email": int(email), "linkedin": int(linkedin)}


def schedule(campaign=None, recs=None, config=None, days=None, counts=None):
    """Day by day, what would go out, and what queues up behind it.

    The cadence says a step is due on day N. The cap says only so many may
    leave in one day. Where those disagree the cap wins and the rest becomes
    backlog, which is the number nobody plans for and everybody discovers in
    week three.
    """
    recs = store.load() if recs is None else recs
    if config is None:
        try:
            config = clients.load((campaign or {}).get("client"))
        except Exception:
            config = {}
    counts = size(campaign, recs, config) if counts is None else counts
    caps = _caps(campaign, config)

    mine = _records(campaign, recs)
    paused_set = cadence.paused_domains(recs)
    due = {}                                   # day -> {channel: count}
    for rec in mine:
        timeline = cadence.build(rec, config, paused_set=paused_set,
                                 campaign=campaign)
        for steps in (timeline.get("contacts") or {}).values():
            for step in steps.values():
                if step.get("status") == "pushed":
                    continue
                day = step.get("day")
                if day is None:
                    continue
                channel = step.get("channel") or "email"
                due.setdefault(day, {"email": 0, "linkedin": 0})
                due[day][channel] = due[day].get(channel, 0) + 1

    horizon = days or (max(due) if due else 0)
    # A channel with work but no cap is modelled as unlimited, which is the
    # optimistic answer and therefore the one worth saying out loud. It is not
    # a launch blocker here - campaigns.check_daily_volume owns that - but a
    # schedule that quietly assumes infinite throughput is how a plan ends up
    # promising a week and taking a month.
    warnings = []
    for channel in ("email", "linkedin"):
        if counts[f"{channel}_steps"] and not caps[channel]:
            warnings.append(f"no daily cap is set for {channel}, so this "
                            "schedule assumes every due step goes out the same "
                            "day; it will not")

    rows, backlog = [], {"email": 0, "linkedin": 0}
    for day in range(1, horizon + 1):
        today = due.get(day) or {"email": 0, "linkedin": 0}
        row = {"day": day}
        for channel in ("email", "linkedin"):
            wanted = today.get(channel, 0) + backlog[channel]
            cap = caps[channel]
            sent = wanted if not cap else min(wanted, cap)
            backlog[channel] = wanted - sent
            row[channel] = {"due": today.get(channel, 0), "sent": sent,
                            "backlog": backlog[channel], "cap": cap or None}
        rows.append(row)

    remaining = backlog["email"] + backlog["linkedin"]
    # How many further days the leftovers need at the same rate. Reported
    # separately from the horizon so nobody reads "40 days" as "finished".
    per_day = (caps["email"] or 0) + (caps["linkedin"] or 0)
    extra = None if not per_day else -(-remaining // per_day)

    return {
        "campaign_id": (campaign or {}).get("campaign_id"),
        "caps": caps,
        "warnings": warnings,
        "days_modelled": horizon,
        "days": rows,
        "unsent_at_horizon": {"email": backlog["email"],
                              "linkedin": backlog["linkedin"]},
        "further_days_needed": extra,
        "calendar_weeks": (None if extra is None else
                           round((horizon + extra) / SENDING_DAYS_PER_WEEK, 1)),
        "counts": counts,
    }


def execution_plan(campaign, recs=None, config=None, days=None):
    """Everything a launch would do, without doing any of it.

    This is the artefact to read before approving a big campaign: the size, the
    schedule, the launch blockers, and the eligibility verdict for every step
    with its reason. It calls no provider and it sends nothing.
    """
    recs = store.load() if recs is None else recs
    if config is None:
        try:
            config = clients.load(campaign.get("client"))
        except Exception:
            config = {}
    counts = size(campaign, recs, config)
    rows = schedule(campaign, recs, config, days=days, counts=counts)

    # Both hoisted out of the loop: one pause scan and one read of the
    # suppression list for the whole batch, not one of each per record.
    paused_set = cadence.paused_domains(recs)
    suppressed = ingest.load_suppress()
    rows = []
    for rec in _records(campaign, recs):
        rows.extend(eligibility.for_record(rec, campaign, recs, config,
                                           suppressed=suppressed,
                                           paused_set=paused_set))
    summary = eligibility.summarise(rows)

    validation = campaigns.validate(campaign.get("campaign_id"), recs, config,
                                    campaign=campaign, ignore_status=True)
    return {
        "campaign_id": campaign.get("campaign_id"),
        "status": campaign.get("status"),
        "frozen": campaigns.is_frozen(campaign),
        "would_send": 0,                 # always. This module cannot send.
        "size": counts,
        "schedule": rows,
        "eligibility": summary,
        "launch_blockers": validation.get("blockers") or [],
        "fingerprint": validation.get("fingerprint"),
    }


def _print(result):
    counts = result["size"]
    print(f"{result['campaign_id']} ({result['status']}"
          + (", FROZEN" if result["frozen"] else "") + ")")
    print(f"  {counts['domains']} domains -> "
          f"{counts['domains_qualified']} qualified -> "
          f"{counts['contacts_found']} contacts found -> "
          f"{counts['contacts_selected']} selected -> "
          f"{counts['contacts_emailable']} emailable, "
          f"{counts['contacts_linkedin']} on LinkedIn")
    print(f"  {counts['email_steps']} email step(s), "
          f"{counts['linkedin_steps']} LinkedIn step(s), "
          f"{counts['steps_already_pushed']} already pushed")
    sched = result["schedule"]
    caps = sched["caps"]
    print(f"  caps: {caps['email']}/day email, {caps['linkedin']}/day LinkedIn")
    print(f"  modelled over {sched['days_modelled']} sending day(s)")
    left = sched["unsent_at_horizon"]
    if left["email"] or left["linkedin"]:
        print(f"  UNSENT at that horizon: {left['email']} email, "
              f"{left['linkedin']} LinkedIn "
              f"(about {sched['further_days_needed']} more day(s), "
              f"{sched['calendar_weeks']} calendar weeks in total)")
    print(f"  would send now: {result['would_send']}")
    for verdict, count in sorted(result["eligibility"]["counts"].items()):
        print(f"    {verdict:<10} {count}")
    for warning in sched.get("warnings") or []:
        print(f"  WARNING: {warning}")
    for blocker in result["launch_blockers"]:
        print(f"  BLOCKER: {blocker}")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--campaign")
    p.add_argument("--days", type=int)
    p.add_argument("--size-only", action="store_true")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)

    recs = store.load()
    campaign = campaigns.get(a.campaign) if a.campaign else None
    if a.campaign and campaign is None:
        print(f"REFUSED: no such campaign: {a.campaign}")
        return 2

    if a.size_only or campaign is None:
        counts = size(campaign, recs)
        print(json.dumps(counts, indent=2) if a.json
              else "\n".join(f"  {k:<26} {v}" for k, v in counts.items()))
        return 0

    result = execution_plan(campaign, recs, days=a.days)
    if a.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        _print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
