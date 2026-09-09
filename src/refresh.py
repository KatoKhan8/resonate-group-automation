#!/usr/bin/env python3
"""Which accounts we already know are worth spending on again, and which are not.

## The question this answers

Discovery asks "who else is there". This asks the other half: of the
companies already in the estate, which ones have gone stale enough that
what we hold about them no longer supports a message, and of those, which
are worth a credit this week.

Both halves are needed and they are not the same work. Rediscovering a
company we already have is waste; refreshing all thirty thousand of them
every week is a larger waste with a tidier name.

## Staleness is per kind, never one number

A company's public evidence, a person's public evidence, the contacts we
hold and the verification on their mailboxes age at different rates and
cost different amounts to renew. One "days since last touched" number
would be a number nobody could defend, and it would put a re-verification
that costs one credit in the same queue as a decision-maker search that
costs eight.

So each kind carries its own threshold, its own provider call, and its own
cost read from `enrich.COSTS` rather than invented here.

## Never researched is not stale

A record with no company evidence at all has not gone stale; it has never
been done. It costs the same, it is often more valuable, and it belongs in
a queue with a different name - a weekly refresh that silently contains
first-time work reports maintenance and performs discovery.

Both appear here. `never` is on the row, and the counts are reported
separately.

## What it refuses to spend on

Refreshing an account that may never be written to buys nothing. Dropped
records, suppressed domains, a company that asked us to stop, and a
company already in a live conversation are excluded before anything is
ranked, each with the reason on the row.

The priority floor works differently from the exclusions above, and the
difference matters: an account below it is not dropped, it is reduced to
the work that costs nothing. A company scores low partly because nothing
is known about it, and free company research is how that stops being
true - a floor that refused it would hold an account below the floor
permanently and call the result thrift.

Person-level kinds carry a further rule, and it is not this module's:
PLAYBOOK says no paid person-level call happens before a company reaches
an explicit ICP verdict, and that rejected, review and unknown all mean
zero person credits. So a company without an accepted verdict can be
offered company research - which is free - and nothing else.

## It plans and never spends

Nothing here calls a provider, and nothing here writes state. It returns
what a run *would* do, with an estimate, and the estimate says it is one.
The cap is applied before the fan-out rather than after, and what fell
below the line is counted rather than dropped silently - a plan that
described the first two hundred of nine hundred without saying so would
read as the whole answer.

## There is no scheduler

"Weekly" describes the intended cadence. Nothing in this repository runs
on a timer; a refresh happens when somebody asks for one. That is the same
statement DISCOVERY.md makes about discovery, and for the same reason: a
timer that does not exist must not be implied by a name.
"""
import argparse
import json

from . import (accountpolicy as ap, clients, enrich, evidence, icp,
               ingest, personalization, priority as priority_module,
               signals as signal_module, store)

# ------------------------------------------------------------------- kinds

COMPANY_RESEARCH = "company_research"
PERSON_RESEARCH = "person_research"
CONTACT_DISCOVERY = "contact_discovery"
REVERIFICATION = "reverification"

KINDS = (COMPANY_RESEARCH, PERSON_RESEARCH, CONTACT_DISCOVERY, REVERIFICATION)

KIND_LABEL = {
    COMPANY_RESEARCH: "Company evidence",
    PERSON_RESEARCH: "Person evidence",
    CONTACT_DISCOVERY: "Decision makers",
    REVERIFICATION: "Mailbox re-verification",
}

# The provider call each kind would make. Named so the cost comes from
# `enrich.COSTS` - the same table the spend ledger charges against - rather
# than from a second list here that could drift from it.
CALL_OF = {
    COMPANY_RESEARCH: "apify-research",
    PERSON_RESEARCH: "apify-research",
    CONTACT_DISCOVERY: "decision-makers",
    REVERIFICATION: "email-verifier",
}

# Whether a kind spends on a *person*. PLAYBOOK gates these on an explicit
# ICP verdict, and the gate is a company-level fact, so it is applied once
# per record rather than per contact.
PERSON_LEVEL = {PERSON_RESEARCH, CONTACT_DISCOVERY, REVERIFICATION}

# Per-contact rather than per-company: one mailbox, one verifier credit.
PER_CONTACT = {REVERIFICATION}

DEFAULTS = {
    # How old each kind may get before it is worth renewing. Company
    # evidence outlasts a person's: an office opening is still true next
    # quarter, and a job change is not.
    "company_research_days": 90,
    "person_research_days": 60,
    "contact_discovery_days": 120,
    "reverification_days": 120,

    # The line. Two hundred accounts is a week of work at a scale a person
    # can look at; the number is a setting because the right one is a
    # client's, not this module's.
    "weekly_cap": 200,

    # How many of the stalest accounts get a priority assessment. Assessing
    # every record in a thirty-thousand-record estate to rank two hundred
    # is work nobody reads.
    "scan_cap": 500,

    # Below this an account buys no *credits*, however stale it is: keeping
    # a record tidy is not a reason to spend one. Free work is deliberately
    # not gated by it - a company scores low partly because nothing is
    # known about it, and company research costs nothing and is how that
    # changes. A floor that refused free research would keep an account
    # below the floor forever and call it thrift.
    #
    # 40 is `priority.DEFAULT_THRESHOLDS[MEDIUM]`, the existing line between
    # medium and low, rather than a second number invented here.
    "minimum_priority": 40.0,
}


def settings(config):
    merged = dict(DEFAULTS)
    merged.update(((config or {}).get("refresh") or {}))
    return merged


# ------------------------------------------------------------- exclusions

DROPPED = "record_dropped"
SUPPRESSED = "domain_suppressed"
ASKED_US_TO_STOP = "company_asked_us_to_stop"
CONVERSATION_LIVE = "conversation_is_live"
BELOW_PRIORITY = "below_the_priority_floor"

EXCLUSION_LABEL = {
    DROPPED: "dropped from its batch",
    SUPPRESSED: "on a suppression list",
    ASKED_US_TO_STOP: "the company asked us to stop",
    CONVERSATION_LIVE: "already in a live conversation",
    BELOW_PRIORITY: "below the priority floor",
}


def excluded(rec, suppressed=None):
    """Why this account is not a refresh candidate at all, or None.

    Checked before anything is ranked and before anything is costed,
    because the cheapest credit is the one not spent on an account that
    may never be written to.
    """
    if rec.get("state") == "dropped":
        # Only dropped. `lint.UNSHIPPABLE` also names "pushed", which means
        # a campaign went out - a reason to refresh this account before the
        # next one, not a reason to skip it.
        return DROPPED
    domain = ingest.norm_domain(rec.get("domain"))
    if domain and domain in (suppressed or ingest.load_suppress()):
        return SUPPRESSED
    state, _ = ap.account_state(rec)
    if state == ap.SUPPRESS:
        return ASKED_US_TO_STOP
    if state == ap.HOLD:
        return CONVERSATION_LIVE
    return None


# -------------------------------------------------------------- staleness

def _newest(rows):
    """The most recent publication date among some evidence, or None."""
    dates = [r.get("published_at") for r in rows or [] if r.get("published_at")]
    return max(dates) if dates else None


def _last_checked(contacts):
    """When these mailboxes were last checked by any verifier.

    Read from `verification.evidence_of`, which is the history each result
    was normalised into, rather than from the projected `sendable` flag -
    SCHEMA warns about that flag by name, and a projection carries no date.

    The oldest of them, deliberately. One contact re-verified last week
    does not make the account's verification current; the one nobody has
    checked since March is what a re-verification would be for.
    """
    from . import verification

    dates = []
    for contact in contacts or []:
        entries = [e.get("at") for e in verification.evidence_of(contact)
                   if e.get("at")]
        if not entries:
            return None          # somebody here has never been checked
        dates.append(max(entries))
    return min(dates) if dates else None


def _icp_accepted(rec):
    """Has this company reached an explicit qualified ICP verdict?

    Anything else - rejected, review, unknown, absent - means zero person
    credits. Read rather than re-derived: `qualify` decides it, and a
    second opinion here would be a second ICP.

    The status lives at `qualification.verdict.icp_status`, one level below
    where a reader expects it. `priority._icp_fit` carries a warning about
    exactly this path, and it is worth repeating: reading
    `qualification.verdict` directly returns a dict, compares unequal to
    every status string, and silently answers "not qualified" for the whole
    estate - which looks identical to a working check that found nothing.
    """
    verdict = (rec.get("qualification") or {}).get("verdict") or {}
    return verdict.get("icp_status") == icp.QUALIFIED


def staleness(rec, today=None, config=None, policy=None):
    """One row per kind of work: how old it is, and whether it is due.

    `age_days` is measured from the newest thing of that kind we hold, so a
    company researched twice reports the second date. `never` means there is
    nothing of that kind at all, which is a different statement from old and
    is counted separately.
    """
    policy = policy or settings(config)
    company = personalization.stored(rec, subject=evidence.COMPANY,
                                     today=today)
    person = personalization.stored(rec, subject=evidence.PERSON, today=today)
    contacts = rec.get("contacts") or []
    selected = [c for c in contacts if c.get("selected")]

    ages = {
        COMPANY_RESEARCH: _newest(company),
        PERSON_RESEARCH: _newest(person),
        # The best proxy the record carries for "when did we last look for
        # people here": the freshest person-level evidence, or nothing.
        CONTACT_DISCOVERY: _newest(person) if contacts else None,
        REVERIFICATION: _last_checked(selected),
    }
    accepted = _icp_accepted(rec)

    rows = []
    for kind in KINDS:
        newest = ages[kind]
        age = evidence.age_days(newest, today) if newest else None
        limit = int(policy[f"{kind}_days"])
        units = len(selected) if kind in PER_CONTACT else 1
        blocked = (None if accepted or kind not in PERSON_LEVEL
                   else "no accepted ICP verdict, so no person credits")
        if blocked is None and kind in PER_CONTACT and not units:
            # Nothing to re-verify. Without this it reports as never done,
            # due, and free - a work item with no work in it, which would
            # walk straight through the priority floor.
            blocked = "no selected contacts to check"
        rows.append({
            "kind": kind,
            "label": KIND_LABEL[kind],
            "newest": newest,
            "age_days": age,
            "limit_days": limit,
            "never": newest is None,
            # Never-done counts as due. It is not stale - it has not
            # happened - and `never` is on the row so a reader can tell
            # the two apart.
            "due": blocked is None and (newest is None or age >= limit),
            "urgency": 0.0 if newest is None else round(age / limit, 3),
            "call": CALL_OF[kind],
            "units": units,
            "credits": enrich.COSTS.get(CALL_OF[kind], 0) * units,
            "person_level": kind in PERSON_LEVEL,
            "blocked": blocked,
        })
    return rows


# A never-researched account has no age to divide, and ordering it by 0.0
# would put the work most worth doing at the bottom. It sorts as if it were
# exactly at its limit plus a margin: due, and ahead of anything merely
# approaching due, but not ahead of something years overdue.
NEVER_URGENCY = 1.25


def urgency_of(rows):
    """How overdue this account is, across every kind that is due."""
    due = [r for r in rows if r["due"]]
    if not due:
        return 0.0
    return round(max(NEVER_URGENCY if r["never"] else r["urgency"]
                     for r in due), 3)


# --------------------------------------------------------------- planning

def candidates(recs, today=None, config=None, suppressed=None):
    """Every record, with its exclusion or its staleness. Free: nothing paid.

    Returned for all of them rather than filtered, because the counts a
    refresh screen needs - how many were excluded and why - are lost by a
    filter.
    """
    policy = settings(config)
    suppressed = ingest.load_suppress() if suppressed is None else suppressed
    out = []
    for rec in recs:
        why = excluded(rec, suppressed)
        if why:
            out.append({"record_id": rec.get("id"),
                        "company": rec.get("company"),
                        "domain": rec.get("domain"),
                        "excluded": why,
                        "excluded_label": EXCLUSION_LABEL[why],
                        "kinds": [], "urgency": 0.0, "due": []})
            continue
        rows = staleness(rec, today, config, policy)
        due = [r for r in rows if r["due"]]
        out.append({"record_id": rec.get("id"),
                    "company": rec.get("company"),
                    "domain": rec.get("domain"),
                    "excluded": None,
                    "excluded_label": None,
                    "kinds": rows,
                    "due": due,
                    "urgency": urgency_of(rows),
                    "credits": sum(r["credits"] for r in due)})
    return out


def plan(recs, today=None, config=None, workspace=None, suppressed=None,
         cap=None, assess=True):
    """What a refresh run would do this week, and what it would leave.

    The order is priority multiplied by how overdue the account is, and
    both halves matter: the stalest account in the estate is not worth a
    credit if nobody would write to it, and the highest-priority account
    does not need refreshing the week after it was done.

    Priority is only assessed for the stalest `scan_cap` accounts. Assessing
    thirty thousand to rank two hundred is work nobody reads, and the number
    scanned is on the result rather than implied by it.
    """
    policy = settings(config)
    cap = policy["weekly_cap"] if cap is None else cap
    suppressed = ingest.load_suppress() if suppressed is None else suppressed

    rows = candidates(recs, today, config, suppressed)
    by_id = {rec.get("id"): rec for rec in recs}

    skipped = {}
    for row in rows:
        if row["excluded"]:
            skipped[row["excluded"]] = skipped.get(row["excluded"], 0) + 1

    due = sorted((r for r in rows if not r["excluded"] and r["due"]),
                 key=lambda r: (-r["urgency"], str(r["record_id"])))
    scan_cap = int(policy["scan_cap"])
    scanned = due[:scan_cap]

    floor = float(policy["minimum_priority"])
    # Same reason as `revival.candidates`: `priority.assess` re-reads the
    # whole signal file for every account it is not handed an index for,
    # and its own docstring says so. Bounded here by `scan_cap`, which
    # makes it five hundred whole-file reads rather than thirty thousand -
    # still five hundred more than one.
    index = signal_module.index(workspace)
    ranked = []
    for row in scanned:
        score, why, limited = None, None, None
        if assess:
            found = priority_module.assess(by_id[row["record_id"]], workspace,
                                           config, suppressed=suppressed,
                                           signal_index=index)
            score, why = found["score"], found["why_now"]
            if score < floor:
                # Not dropped: reduced to the work that costs nothing. An
                # account scores low partly because nothing is known about
                # it, and free research is how that stops being true.
                free = [k for k in row["due"] if not k["credits"]]
                if not free:
                    skipped[BELOW_PRIORITY] = skipped.get(BELOW_PRIORITY,
                                                          0) + 1
                    continue
                limited = ("below the priority floor, so only the work that "
                           "costs nothing")
                row = {**row, "due": free, "credits": 0}
        ranked.append({**row, "priority": score, "why_now": why,
                       "floor_limited": limited,
                       # Priority is a 0-100 score and urgency is a
                       # multiple of a threshold; the product orders them
                       # without either being able to win alone.
                       "rank": round((score if score is not None else 50.0)
                                     * row["urgency"], 2)})

    ranked.sort(key=lambda r: (-r["rank"], str(r["record_id"])))
    selected = ranked[:max(0, cap)]

    estimate = {}
    for row in selected:
        for kind_row in row["due"]:
            call = kind_row["call"]
            entry = estimate.setdefault(call, {"call": call, "calls": 0,
                                               "credits": 0})
            entry["calls"] += kind_row["units"]
            entry["credits"] += kind_row["credits"]

    return {
        "workspace": workspace,
        "considered": len(rows),
        # Reason, what it means, and how many - rather than a bare count
        # keyed by a code. A screen that had to look the sentence up would
        # need this module, and a template that can reach a decision module
        # can make a decision.
        "excluded": [{"reason": reason, "label": EXCLUSION_LABEL[reason],
                      "count": count}
                     for reason, count in sorted(skipped.items())],
        "excluded_total": sum(skipped.values()),
        "due": len(due),
        "scanned": len(scanned),
        # Said rather than implied. A plan that described the first five
        # hundred of nine hundred without saying so would read as the
        # whole answer.
        "capped_scan": len(due) > len(scanned),
        "cap": cap,
        "selected": selected,
        "below_the_line": max(0, len(ranked) - len(selected)),
        "floor_limited": sum(1 for r in selected if r.get("floor_limited")),
        "never_done": sum(1 for r in selected
                          for k in r["due"] if k["never"]),
        "estimate": {
            "by_call": sorted(estimate.values(), key=lambda e: -e["credits"]),
            "credits": sum(e["credits"] for e in estimate.values()),
            # The number is arithmetic over `enrich.COSTS`, which is itself
            # an assumption in places. It is what a run would be charged if
            # every call it plans is made and none is skipped.
            "note": "an estimate: what this plan would cost if every call "
                    "it names is made and none is skipped or cached",
        },
        "spent": 0,
        "note": "nothing here is refreshed. This is what a run would do, "
                "and no provider is called to produce it",
    }


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m src.refresh", description=__doc__)
    p.add_argument("--client")
    p.add_argument("--cap", type=int)
    p.add_argument("--today")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)

    recs = [r for r in store.load()
            if not a.client or r.get("client") == a.client]
    config = clients.load(a.client) if a.client else {}
    found = plan(recs, today=a.today, config=config, workspace=a.client,
                 cap=a.cap)
    if a.json:
        print(json.dumps(found, indent=2, sort_keys=True))
        return 0

    print(f"considered {found['considered']}, due {found['due']}, "
          f"selected {len(found['selected'])} (cap {found['cap']})")
    for row in found["excluded"]:
        print(f"  excluded {row['count']}: {row['label']}")
    if found["capped_scan"]:
        print(f"  priority assessed for the stalest {found['scanned']} only")
    print(f"  below the line: {found['below_the_line']}")
    print(f"  estimated credits: {found['estimate']['credits']} "
          f"({found['estimate']['note']})")
    for row in found["selected"][:20]:
        kinds = ", ".join(k["label"] for k in row["due"])
        print(f"  {row['record_id']:<20} {row['company'] or '':<28} "
              f"rank {row['rank']:>7}  {kinds}")
    print("\n" + found["note"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
