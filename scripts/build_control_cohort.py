#!/usr/bin/env python3
"""Install the CONTROL arm's copy on a cohort, and approve it.

WHY THIS EXISTS, AND WHY IT IS NOT A GENERATOR.

Three human reads - TASK-098, TASK-130, TASK-136 - compared generated LinkedIn
copy against the operator's own hand-written fallbacks and returned DOES NOT
BEAT FALLBACKS every time. The named defects each read found were fixed and the
verdict did not move, because the constraint is the SHAPE of the sequence
rather than the words inside a step. So the fallbacks are the validated CONTROL
arm and generated variants are challengers that have to beat them.

The fallbacks already live in the client config under
`linkedin_sequence.fallbacks`, where they serve as HeyReach's `fallbackMessage`
- what a lead receives when a merge variable cannot be filled. That is a
backstop, not a deployment: `heyreachfactory._plan` refuses a contact who has
no APPROVED copy for every role the graph requires, so a cohort carrying only
fallbacks is a cohort that cannot ship.

This closes that gap the honest way. It writes the client's own fallback text
into each contact's cadence steps and approves it through `approve.approve_step`
- the same path a person uses, running the same gates - so the words that reach
a prospect are words the operator wrote and a record shows who approved them
and when. It invents nothing. If the config has no fallback for a role, it
refuses rather than composing one, for the reason `merge_sequence_copy` already
gives: a fallback invented here is unapproved copy nobody read.

IDEMPOTENT. A contact already carrying this exact approved text is skipped, so
a re-run after a crash costs reads and writes nothing. The fingerprint is
`approval.fingerprint`, so a contact whose text has drifted is re-installed
rather than trusted.

DRY RUN BY DEFAULT.

    py -3 scripts/build_control_cohort.py --campaign productive-linkedin-production-v1
    py -3 scripts/build_control_cohort.py --campaign ... --limit 3 --live
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import (approval, approve, campaigns, clients, eligibility,  # noqa: E402
                 heyreachfactory, store)

# Which cadence step carries which role's words. `heyreachfactory.COPY_MAPPING`
# is the authority; this reads it rather than restating it, so a step that
# gains or loses a role does not need a second edit here.
STEP_ROLES = heyreachfactory.COPY_MAPPING

BY = "operator-control-arm"


class CohortRefused(RuntimeError):
    """The cohort cannot be built, and the reason is on the exception."""


def control_copy(config):
    """`{role: text}` from the client config, or refuse naming what is absent.

    Deliberately the same source and the same refusal as
    `heyreachfactory.merge_sequence_copy`, which builds the GRAPH's fallbacks
    from it. One text, two consumers: the graph's backstop and the lead's own
    variable now carry the same approved words, so a merge failure at HeyReach
    degrades to the identical sentence rather than to something nobody read.
    """
    configured = ((config or {}).get(
        heyreachfactory.FALLBACK_CONFIG_KEY) or {}).get("fallbacks") or {}
    copy, missing = {}, []
    for role in heyreachfactory.REQUIRED_ROLES:
        text = str(configured.get(role) or "").strip()
        if text:
            copy[role] = text
        else:
            missing.append(role)
    if missing:
        raise CohortRefused(
            f"the client config declares no fallback copy for "
            f"{', '.join(sorted(missing))}. This script installs the "
            f"operator's own words and composes none of its own; declare "
            f"them under {heyreachfactory.FALLBACK_CONFIG_KEY}.fallbacks")
    return copy


def step_texts(copy):
    """`{step_key: text}` - the one sentence each cadence step carries.

    A step maps to one or two roles (li2 is both `connected_1` and
    `message_2`, the already-connected and cold branches of the same beat).
    Those two roles must carry the SAME words or the branch a prospect happens
    to walk decides what they read, so a disagreement refuses here rather than
    being resolved by whichever role sorted first.
    """
    texts = {}
    for step_key, mapping in STEP_ROLES.items():
        roles = mapping["role"]
        roles = (roles,) if isinstance(roles, str) else tuple(roles)
        values = {copy[role] for role in roles if role in copy}
        if len(values) != 1:
            raise CohortRefused(
                f"step {step_key} carries roles {roles} and the config gives "
                f"them {len(values)} different texts. Both branches of one "
                f"beat must say the same thing, or what a prospect reads "
                f"depends on whether they had already connected")
        texts[step_key] = values.pop()
    return texts


def _already_control(rec, contact_key, texts):
    """True when this contact already carries exactly this approved copy."""
    for step_key, text in texts.items():
        slot = approval.stored(rec, contact_key, step_key)
        if (slot.get("note") or "").strip() != text:
            return False
        if not approval.is_approved(rec, contact_key, step_key):
            return False
    return True


def eligible_contacts(recs, client, *, config, skip_with_history=True):
    """Every contact this cohort may legitimately contain, with a reason for
    each one it may not.

    Returns `(eligible, skipped)` where each entry is
    `(record, contact, why)` - `why` is None for the eligible.

    THE HISTORY RULE IS NOT COSMETIC. A contact carrying a `bison_lead_id` has
    been written to before, so they are not a cold prospect and the control
    arm's first line - "thought it would be good to connect" - is the wrong
    thing to say to them. They are held out of the first campaign rather than
    dropped: they need their own treatment, not this one.
    """
    eligible, skipped = [], []
    for rec in recs:
        if rec.get("client") != client:
            continue
        if rec.get("dropped") or rec.get("state") == "dropped":
            continue
        if rec.get("paused"):
            continue
        for contact in rec.get("contacts") or []:
            key = contact.get("key")
            if not contact.get("linkedin"):
                skipped.append((rec, contact, "no LinkedIn profile"))
                continue
            if skip_with_history and contact.get("bison_lead_id"):
                skipped.append((rec, contact,
                                "prior EmailBison outreach; not a cold "
                                "prospect"))
                continue
            stops = [r for r in eligibility.must_not_contact(
                rec, contact, config=config) if r]
            if stops:
                skipped.append((rec, contact, "; ".join(stops)))
                continue
            eligible.append((rec, contact, None))
    return eligible, skipped


def install(rec, contact_key, texts, *, config, campaign=None, by=BY):
    """Write the control copy onto one contact's steps and approve each.

    Returns the list of step keys that were installed. Raises
    `approve.NotApprovable` if any step cannot be approved - the whole
    contact, because a cohort member with four approved steps and one refused
    would be pushed and then send a fallback for the fifth.
    """
    cadence_slots = rec.setdefault("cadence", {}).setdefault(contact_key, {})
    installed = []
    for step_key, text in texts.items():
        slot = cadence_slots.setdefault(step_key, {})
        # OVERWRITE, DELIBERATELY. `approve_step` copies a field onto the slot
        # only when the slot does not already have it, so a contact carrying
        # generated challenger copy would keep those words and receive an
        # approval stamped for these ones - approved text and sent text
        # disagreeing, which is the exact failure `_require_approved_words`
        # exists to catch later and should never be manufactured here.
        slot["channel"] = "linkedin"
        slot["note"] = text
        slot.pop("approval", None)
        # The challenger's provenance is dropped with it: a step carrying the
        # operator's words is not generated, and leaving the flag would make
        # the arm unreadable in the record's own log.
        slot.pop("generated", None)
        step = {"channel": "linkedin", "note": text}
        approve.approve_step(rec, contact_key, step_key, by=by, config=config,
                             step=step, sync=False, campaign=campaign)
        installed.append(step_key)
    approve.sync_state(rec, config, campaign)
    return installed


def main(argv=None):
    p = argparse.ArgumentParser(prog="build_control_cohort",
                                description=__doc__)
    p.add_argument("--campaign", required=True)
    p.add_argument("--client", default="productive")
    p.add_argument("--limit", type=int, default=3,
                   help="how many CONTACTS to put in the cohort. The operator "
                        "batch progression is 3 -> 10 -> 25 -> 50, each stage "
                        "gated on a provider readback of the one before")
    p.add_argument("--include-prior-outreach", action="store_true",
                   help="include contacts carrying a prior EmailBison lead "
                        "id. They are not cold prospects; off by default")
    p.add_argument("--live", action="store_true",
                   help="write the copy and the campaign's record set. "
                        "Without it, nothing is saved")
    a = p.parse_args(argv)

    config = clients.load(a.client)
    copy = control_copy(config)
    texts = step_texts(copy)

    rows = campaigns.load()
    campaign = campaigns.require(str(a.campaign), rows)
    if campaign.get("client") != a.client:
        raise CohortRefused(
            f"campaign {a.campaign!r} belongs to client "
            f"{campaign.get('client')!r}, not {a.client!r}")

    # READ, CHANGE, WRITE UNDER ONE LOCK. `store.save` on a list loaded
    # earlier writes that opening snapshot back, which is how a concurrent
    # enrichment batch loses the record it had just finished. `transaction`
    # holds the lock across all three and runs the evidence and history
    # guards on the way out.
    with store.transaction() as recs:
        return _run(a, config, texts, rows, campaign, recs)


def _run(a, config, texts, rows, campaign, recs):
    eligible, skipped = eligible_contacts(
        recs, a.client, config=config,
        skip_with_history=not a.include_prior_outreach)

    print(f"control copy      {len(texts)} steps from the client config")
    for step_key in sorted(texts):
        print(f"  {step_key}  {texts[step_key][:72]}")
    print(f"eligible contacts {len(eligible)}")
    print(f"skipped           {len(skipped)}")
    reasons = {}
    for _rec, _contact, why in skipped:
        reasons[why] = reasons.get(why, 0) + 1
    for why, count in sorted(reasons.items(), key=lambda kv: -kv[1])[:6]:
        print(f"  {count:5d}  {why}")

    chosen = eligible[:a.limit] if a.limit and a.limit > 0 else eligible
    print(f"cohort            {len(chosen)} contact(s)")

    touched, already, failed = [], [], []
    for rec, contact, _why in chosen:
        key = contact.get("key")
        if _already_control(rec, key, texts):
            already.append((rec.get("id"), key))
            continue
        if not a.live:
            touched.append((rec.get("id"), key))
            continue
        try:
            install(rec, key, texts, config=config, campaign=campaign)
        except approve.NotApprovable as e:
            failed.append((rec.get("id"), key, str(e)))
            continue
        touched.append((rec.get("id"), key))

    for rid, key in already:
        print(f"  already control   {rid}/{key}")
    for rid, key in touched:
        print(f"  {'installed' if a.live else 'would install'}         "
              f"{rid}/{key}")
    for rid, key, why in failed:
        print(f"  REFUSED           {rid}/{key}: {why}")

    record_ids = sorted({rec.get("id") for rec, _c, _w in chosen})
    if not a.live:
        print(f"\nDRY RUN. Would set campaign record_ids to "
              f"{len(record_ids)} record(s): {record_ids}")
        return 0

    # The records are written by the transaction this runs inside, so
    # nothing is saved here. Campaign state lives in its own file - a
    # campaign is not a record - and is written now.
    campaign["record_ids"] = record_ids
    campaigns.save(rows)
    print(f"\ncampaign {a.campaign} record_ids = {len(record_ids)}: "
          f"{record_ids}")
    if failed:
        print("SOME CONTACTS REFUSED. They are not in the cohort.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
