#!/usr/bin/env python3
"""What a cadence cost the people who received it.

## The number that is missing from every reply rate

A seven-step arm that earns two percentage points more replies and three
times the unsubscribes is not better. It is a different trade, and the
trade is not this system's to make: an unsubscribe is a person saying stop,
a spam complaint is a deliverability problem for every campaign that shares
the domain, and neither converts into replies at any exchange rate.

So this module reports the cost beside the return and **refuses to net
them**. There is no score here that combines a reply with an unsubscribe.
A single number would be the most useful-looking output in the codebase and
the one most likely to burn a sending domain, because whoever read it would
stop looking at the two columns underneath.

`src/fatigue.py` answers a different question - how often somebody *may* be
contacted, configured in advance. This one answers what actually happened
to the people who were.

## Harm, and context

    unsubscribed          they asked to be removed
    stopped               a stop was recorded against the contact
    account_suppressed    the whole company was suppressed
    negative_reply        they answered, and the answer was no

Those four are harm and they share a denominator: one person who replies
negatively and then unsubscribes is one person harmed, not two.

    bounced   held   dropped

Those three are context, counted separately. A bounce is a fact about an
address, a hold is a pause somebody applied, and a drop is an operator's
decision - none of them is a recipient telling us we went too far, and
mixing them into a harm rate would let list quality masquerade as fatigue.

## Where it happened

Each outcome is placed after the last confirmed touch before it, by the
same rule `cadencereplies` uses and through the same function. "Half the
unsubscribes arrive after step five" is the finding that decides whether
step five should exist; "the seven-step arm has more unsubscribes" is not,
because it has more steps for them to arrive after.

## What it refuses to say

That one arm is safer than another when the intervals overlap. Three
unsubscribes against one, on forty people each, is not evidence of
anything, and a comparison that names a winner there would license
lengthening a cadence on noise.
"""
import argparse
import json

from . import (account, cadencearms, cadenceexposure, cadencereplies, events,
               variants)

UNSUBSCRIBED = "unsubscribed"
STOPPED = "stopped"
ACCOUNT_SUPPRESSED = "account_suppressed"
NEGATIVE_REPLY = "negative_reply"

BOUNCED = "bounced"
HELD = "held"
DROPPED = "dropped"

# One person who replies negatively and then unsubscribes is one person
# harmed. These share a denominator and are deduplicated by contact.
HARM = (UNSUBSCRIBED, STOPPED, ACCOUNT_SUPPRESSED, NEGATIVE_REPLY)

# Counted, never added to the harm rate. None of these is a recipient
# telling us we went too far.
CONTEXT = (BOUNCED, HELD, DROPPED)

KIND_OF_EVENT = {
    events.CONTACT_SUPPRESSED: UNSUBSCRIBED,
    events.CONTACT_STOPPED: STOPPED,
    events.ACCOUNT_SUPPRESSED: ACCOUNT_SUPPRESSED,
    events.RECORD_SUPPRESSED: ACCOUNT_SUPPRESSED,
    events.EMAIL_BOUNCED: BOUNCED,
    events.CONTACT_HELD: HELD,
    events.RECORD_DROPPED: DROPPED,
}

LABEL = {
    UNSUBSCRIBED: "asked to be removed",
    STOPPED: "a stop was recorded",
    ACCOUNT_SUPPRESSED: "the company was suppressed",
    NEGATIVE_REPLY: "answered, and the answer was no",
    BOUNCED: "the address bounced",
    HELD: "put on hold",
    DROPPED: "dropped by an operator",
}


def _at(value):
    return str(value or "")


def _events_for(rec, contact_key):
    """Safety events belonging to this contact, or to the whole record.

    A record-level suppression has no contact on it and applies to
    everybody at the company, so it counts once for each contact who was
    actually in the experiment - which is what the denominator counts too.
    """
    out = []
    for entry in rec.get("events") or []:
        kind = KIND_OF_EVENT.get(entry.get("type"))
        if kind is None:
            continue
        who = entry.get("contact")
        if who and who != contact_key:
            continue
        out.append((kind, entry))
    return out


def contact_outcomes(exp, rec, contact, campaign=None):
    """Every safety outcome for one contact, placed in its arm and step.

    `None` when the contact is not in the experiment; an empty list when
    they are in it and nothing went wrong.
    """
    exposure = cadenceexposure.contact_exposure(exp, rec, contact, campaign)
    if exposure is None:
        return None

    steps = exposure["steps"]
    order = {row.get("key"): index + 1 for index, row in enumerate(steps)}

    found = _events_for(rec, contact.get("key"))
    for reply in account.replies(rec, contact.get("key")):
        if reply.get("classification") in ("negative", "unsubscribe"):
            found.append((NEGATIVE_REPLY, reply))

    out = []
    for kind, entry in found:
        after = cadencereplies.attribute_to_step(entry.get("at"), steps)
        key = (after or {}).get("key")
        out.append({
            "experiment_id": exposure["experiment_id"],
            "arm_id": exposure["arm_id"],
            "record_id": exposure["record_id"],
            "contact_key": exposure["contact_key"],
            "kind": kind,
            "label": LABEL[kind],
            "harm": kind in HARM,
            "at": entry.get("at"),
            "after_step": key or cadencereplies.UNATTRIBUTED,
            "after_step_index": order.get(key),
            "attributed": key is not None,
        })
    return sorted(out, key=lambda row: _at(row["at"]))


def outcomes_for(exp, recs, campaign=None):
    out = []
    for rec in recs or []:
        for contact in account.contacts_of(rec):
            found = contact_outcomes(exp, rec, contact, campaign)
            if found:
                out.extend(found)
    return out


def by_arm(exp, recs, campaign=None):
    """Per arm: who was exposed, what it cost them, and after which step."""
    rows = cadenceexposure.exposures(exp, recs, campaign)
    found = outcomes_for(exp, recs, campaign)

    out = {}
    for entry in cadencearms.arms_of(exp):
        arm_id = entry["arm_id"]
        arm = cadencearms.arm_by_id(exp, arm_id) or {}
        mine = [row for row in rows if row["arm_id"] == arm_id]
        exposed = [row for row in mine if row["started"]]
        theirs = [row for row in found if row["arm_id"] == arm_id]

        harmed = {(row["record_id"], row["contact_key"])
                  for row in theirs if row["harm"]}
        kinds = {kind: len({(r["record_id"], r["contact_key"])
                            for r in theirs if r["kind"] == kind})
                 for kind in HARM + CONTEXT}
        after = {}
        for row in theirs:
            if not row["harm"]:
                continue
            after[row["after_step"]] = after.get(row["after_step"], 0) + 1

        out[arm_id] = {
            "arm_id": arm_id,
            "label": arm.get("label"),
            "steps": len(arm.get("steps") or []),
            "exposed": len(exposed),
            "harmed": len(harmed),
            "rate": (len(harmed) / len(exposed)) if exposed else None,
            "low": (variants.wilson_low(len(harmed), len(exposed))
                    if exposed else None),
            "high": (variants.wilson_high(len(harmed), len(exposed))
                     if exposed else None),
            "by_kind": {k: v for k, v in kinds.items() if k in HARM},
            # Counted, never added in. A bounce is a fact about an address
            # and a hold is a pause somebody applied.
            "context": {k: v for k, v in kinds.items() if k in CONTEXT},
            "after_step": after,
            "note": "one person is counted once however many ways it went "
                    "wrong; bounces, holds and drops are context and are "
                    "not in this rate",
        }
    return out


def compare(exp, recs, campaign=None):
    """Arms side by side, with a verdict that refuses to be talked into one.

    Overlapping intervals mean the difference is not distinguishable from
    noise, and a comparison that named a safer arm there would license
    lengthening a cadence on three unsubscribes against one.
    """
    arms = by_arm(exp, recs, campaign)
    measured = {k: v for k, v in arms.items() if v["exposed"]}

    worse = None
    if len(measured) >= 2:
        ordered = sorted(measured.values(), key=lambda row: row["rate"])
        best, rest = ordered[0], ordered[1:]
        clear = [row for row in rest if row["low"] > best["high"]]
        if len(clear) == len(rest):
            worse = [row["arm_id"] for row in clear]

    return {
        "experiment_id": exp.get("experiment_id"),
        "arms": arms,
        "measured": sorted(measured),
        "costs_more": worse,
        "comparable": bool(worse) or len(measured) >= 2,
        "why": ("no arm's harm rate is distinguishable from another's"
                if worse is None else
                "harm is higher in " + ", ".join(worse)
                + " than in the lowest arm, by more than the intervals"),
        "note": "reply rates are not in this comparison and must not be "
                "netted against it: an unsubscribe does not convert into a "
                "reply at any exchange rate",
    }


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m src.cadencesafety",
                                description=__doc__)
    p.add_argument("--campaign", required=True)
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)

    from . import campaigns, store

    campaign = campaigns.get(a.campaign, campaigns.load())
    exp = (campaign or {}).get(cadencearms.EXPERIMENT_KEY)
    if not exp:
        print("no cadence experiment on that campaign")
        return 1
    recs = [r for r in store.load()
            if r.get("id") in (campaign.get("record_ids") or [])]
    found = compare(exp, recs, campaign)
    if a.json:
        print(json.dumps(found, indent=2, default=str))
        return 0

    for arm_id, row in sorted(found["arms"].items()):
        rate = "-" if row["rate"] is None else f"{row['rate']:.1%}"
        print(f"{arm_id:<10} {row['steps']} steps  "
              f"{row['harmed']}/{row['exposed']} ({rate})")
        for kind, count in sorted(row["by_kind"].items()):
            if count:
                print(f"    {kind:<20} {count}")
        for step, count in sorted(row["after_step"].items()):
            print(f"    after {step:<14} {count}")
    print("\n" + found["why"])
    print(found["note"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
