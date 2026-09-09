#!/usr/bin/env python3
"""What finding the people would cost, worked out before anybody is found.

A 5,000-domain upload must never fan out into thousands of paid person
searches because somebody ran the next command. So the plan is computed first,
in full, and person enrichment is gated behind an explicit approval that
fingerprints what was approved.

Three numbers, and they are different on purpose:

    expected_credits   what we believe this costs if it goes normally
    maximum_credits    what it costs if every conditional call fires
    fallback_exposure  the part of the maximum that only exists because a
                       fallback might be needed

Reporting one number would be a forecast pretending to be a limit. The cap is
set against the maximum, because that is the number that can actually arrive on
an invoice.

The approval fingerprints the qualification result. Requalify a batch and the
verdicts change, so the approval that was given for the old verdicts is stale
and says so - the same rule the campaign approval already uses.

  python -m src.dmplan --batch 2026-08 --client productive
"""
import argparse
import hashlib
import json

from . import enrich, icp, store, waterfall

# ----------------------------------------------------------------- states
#
# The progression the brief requires, as states a batch can be in. Each one is
# a gate: nothing may skip forward, and a batch that stops halfway resumes
# from where it actually is rather than from the beginning.

NOT_PROCESSED = "not_processed"
COMPANY_ENRICHED = "company_enriched"
CLASSIFIED = "classified"
REVIEW_REQUIRED = "review_required"
QUALIFIED = "qualified"
REJECTED = "rejected"
DM_APPROVED = "dm_enrichment_approved"
DM_PENDING = "dm_enrichment_pending"
DM_COMPLETE = "dm_enrichment_complete"

STATES = (NOT_PROCESSED, COMPANY_ENRICHED, CLASSIFIED, REVIEW_REQUIRED,
          QUALIFIED, REJECTED, DM_APPROVED, DM_PENDING, DM_COMPLETE)

# States from which person enrichment may run at all.
ENRICHABLE = (DM_APPROVED,)

# What one company's person search costs, from the same table enrichment uses,
# so this cannot drift from what actually gets charged.
SEARCH_CALL = "decision-makers"
VERIFY_CALL = "email-verifier"
FALLBACK_CALL = "aiark-people-search"


class NotApproved(RuntimeError):
    """Person enrichment was attempted before the plan was approved."""


def settings(config):
    block = ((config or {}).get("dm_plan") or {})
    merged = {
        # A hard ceiling on the whole batch, in credits. None means the only
        # limit is the per-tier caps, which is a decision rather than a default.
        "max_batch_credits": None,
        # Whether a company under review may be enriched without a human.
        # False, and it takes saying otherwise in words.
        "allow_review_enrichment": block.get("allow_review_enrichment") is True,
        # Whether a verification call is planned per found contact.
        "verify_found_contacts": block.get("verify_found_contacts") is not False,
    }
    cap = block.get("max_batch_credits")
    if cap is not None:
        try:
            merged["max_batch_credits"] = max(0, int(cap))
        except (TypeError, ValueError):
            pass
    return merged


def for_company(rec, persona_plan, verdict, config=None):
    """The calls one company would need, and what they would cost."""
    policy = settings(config)
    contacts = persona_plan.get("max_contacts_to_enrich") or 0
    status = verdict.get("icp_status")

    if contacts <= 0:
        return {
            "record_id": rec.get("id"),
            "domain": rec.get("domain"),
            "enrichment_required": False,
            "planned_contacts": 0,
            "calls": [],
            "expected_credits": 0,
            "maximum_credits": 0,
            "fallback_exposure": 0,
            "why": persona_plan.get("cap_reason")
            or f"status is {status}: nothing is planned",
        }

    calls = [{
        "stage": waterfall.PEOPLE_DISCOVERY,
        "provider": waterfall.CONTACTOUT,
        "call": SEARCH_CALL,
        "conditional": False,
        "credits": enrich.COSTS.get(SEARCH_CALL, 0),
        "why": "ContactOut returns the people and their addresses in one call",
    }]
    if policy["verify_found_contacts"]:
        calls.append({
            "stage": waterfall.EMAIL_VERIFICATION,
            "provider": waterfall.CONTACTOUT,
            "call": VERIFY_CALL,
            "conditional": False,
            "credits": enrich.COSTS.get(VERIFY_CALL, 0) * contacts,
            "why": f"one verification per planned contact ({contacts})",
        })
    # Conditional, and it needs a reason the waterfall accepts before it may
    # actually run. Counted in the maximum, never in the expectation.
    calls.append({
        "stage": waterfall.PEOPLE_DISCOVERY,
        "provider": waterfall.AIARK,
        "call": FALLBACK_CALL,
        "conditional": True,
        "credits": enrich.COSTS.get(FALLBACK_CALL, 0),
        "why": "only if ContactOut finds nobody, or nobody in a target persona",
        "requires_reason": list(waterfall.accepted_reasons(
            waterfall.PEOPLE_DISCOVERY, waterfall.AIARK, FALLBACK_CALL)),
    })

    expected = sum(c["credits"] for c in calls if not c["conditional"])
    maximum = sum(c["credits"] for c in calls)
    return {
        "record_id": rec.get("id"),
        "domain": rec.get("domain"),
        "enrichment_required": True,
        "planned_contacts": contacts,
        "calls": calls,
        "expected_credits": expected,
        "maximum_credits": maximum,
        "fallback_exposure": maximum - expected,
        "why": persona_plan.get("cap_reason"),
    }


def for_batch(companies, config=None):
    """The whole batch, with the three numbers and what is being skipped.

    `companies` is a list of {record, persona_plan, verdict} - the output of
    the qualification pass, before anything has been spent.
    """
    policy = settings(config)
    plans, by_tier = [], {}
    for entry in companies:
        plan = for_company(entry["record"], entry["persona_plan"],
                           entry["verdict"], config)
        plans.append(plan)
        tier = entry["verdict"].get("icp_tier")
        bucket = by_tier.setdefault(tier, {"companies": 0, "contacts": 0,
                                           "expected": 0, "maximum": 0})
        bucket["companies"] += 1
        bucket["contacts"] += plan["planned_contacts"]
        bucket["expected"] += plan["expected_credits"]
        bucket["maximum"] += plan["maximum_credits"]

    enriching = [p for p in plans if p["enrichment_required"]]
    expected = sum(p["expected_credits"] for p in plans)
    maximum = sum(p["maximum_credits"] for p in plans)

    over_cap = (policy["max_batch_credits"] is not None
                and maximum > policy["max_batch_credits"])

    return {
        "companies": len(plans),
        "companies_requiring_enrichment": len(enriching),
        "companies_skipped": len(plans) - len(enriching),
        "planned_dm_searches": len(enriching),
        "maximum_contacts": sum(p["planned_contacts"] for p in plans),
        "expected_credits": expected,
        "maximum_credits": maximum,
        "fallback_exposure": maximum - expected,
        "by_tier": by_tier,
        "max_batch_credits": policy["max_batch_credits"],
        "over_cap": over_cap,
        "cap_note": (f"the maximum exposure of {maximum} exceeds the batch cap "
                     f"of {policy['max_batch_credits']}: the plan cannot be "
                     "approved as it stands" if over_cap else
                     "within the configured batch cap"
                     if policy["max_batch_credits"] is not None else
                     "no batch credit cap is configured; the per-tier caps are "
                     "the only limit"),
        "plans": plans,
    }


# ---------------------------------------------------------- the approval

def fingerprint(companies):
    """A digest of the qualification result the plan was built from.

    Deliberately covers the verdict and the contact cap for every company: if
    a requalification changes who is qualified or how many people we would
    look for, the approval was given for a different plan and must go stale.
    Ordered by record id so the digest is stable across runs.

    Credit exposure is covered transitively rather than stored: expected and
    maximum spend are computed from the tier and the contact cap, both of which
    are here, so a cost that moved without one of them moving would be a bug in
    the cost model rather than a gap in this digest.

    `segment_key` is covered directly, because it is the one material field
    that is *not* derivable from this company alone - the rung a company lands
    on depends on how many others share its key, so adding companies to a batch
    can re-segment ones nobody touched. That makes the approval more brittle
    than a per-company digest would be, and that is the right direction to err:
    the cost of a stale approval is somebody looking again, and the cost of a
    fresh-looking one is a campaign that is not the campaign that was approved.
    """
    material = sorted(
        ({
            "record_id": entry["record"].get("id"),
            "status": entry["verdict"].get("icp_status"),
            "tier": entry["verdict"].get("icp_tier"),
            "contacts": entry["persona_plan"].get("max_contacts_to_enrich"),
            "titles": entry["persona_plan"].get("target_titles"),
            "segment_key": entry.get("segment_key"),
        } for entry in companies),
        key=lambda row: row["record_id"] or "")
    blob = json.dumps(material, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def approve(batch, companies, by, config=None, at=None):
    """Record that a human approved this exact plan.

    The batch is a plain dict the caller persists. It carries the fingerprint,
    so `is_current` can tell an approval of *this* plan from an approval of
    something that has since changed.
    """
    summary = for_batch(companies, config)
    if summary["over_cap"]:
        raise NotApproved(summary["cap_note"])
    batch["dm_approval"] = {
        "by": by,
        "at": at or store.now(),
        "fingerprint": fingerprint(companies),
        "expected_credits": summary["expected_credits"],
        "maximum_credits": summary["maximum_credits"],
        "companies": summary["companies_requiring_enrichment"],
        "contacts": summary["maximum_contacts"],
    }
    return batch["dm_approval"]


def is_current(batch, companies):
    """Does the stored approval still describe this qualification result?"""
    approval = (batch or {}).get("dm_approval") or {}
    if not approval:
        return False, "no person-enrichment approval has been given"
    if approval.get("fingerprint") != fingerprint(companies):
        return False, ("the qualification result changed after approval: "
                       "re-approve before spending anything")
    return True, f"approved by {approval.get('by')} at {approval.get('at')}"


def human_review(rec):
    """The current human review of this company's verdict, or None.

    Read off the record rather than through `qualify`, which imports this
    module. The staleness rule is the same one `qualify.review_of` applies and
    is repeated here rather than shared, because this is the gate that spends
    money and it must not depend on an import that could be removed: a review
    whose fingerprint no longer matches the inputs the verdict came from is
    not a review of this company any more.
    """
    qualification = (rec or {}).get("qualification") or {}
    review = qualification.get("human_review")
    if not review:
        return None
    if review.get("inputs_fingerprint") != qualification.get(
            "inputs_fingerprint"):
        return None
    return review


def may_enrich(batch, companies, rec, verdict, config=None):
    """The single gate. Returns (allowed, reason) and never spends anything."""
    policy = settings(config)
    status = verdict.get("icp_status")
    review = human_review(rec)

    if status == icp.REJECTED:
        return False, "the company was rejected: no person enrichment, ever"

    # A human saying no outranks everything below, including a qualified
    # verdict. Refusing to spend is never the dangerous direction, so this
    # needs no policy behind it and applies at every status.
    if review and review.get("decision") == "reject":
        return False, (f"a human reviewed this company on {review.get('at')} "
                       "and rejected it: no person enrichment")

    if status in (icp.REVIEW, icp.UNKNOWN):
        if not policy["allow_review_enrichment"]:
            if review:
                # The decision was recorded. It is the client's policy, not
                # the absence of a reviewer, that keeps this shut - and saying
                # which of the two it is saves an operator an afternoon.
                return False, (
                    f"the company is {status} and was accepted by "
                    f"{review.get('by')}, but this client has not enabled "
                    "dm_plan.allow_review_enrichment: a company that did not "
                    "qualify on evidence is not enriched here")
            return False, (f"the company is {status}: person enrichment waits "
                           "for a human decision")
        if not review:
            return False, (f"the company is {status}: policy allows enrichment "
                           "after review, and no review has been recorded")
        ok, why = is_current(batch, companies)
        if not ok:
            return False, why
        return True, (f"{status}, accepted by {review.get('by')} at "
                      f"{review.get('at')}, and the client allows enrichment "
                      "after review")
    if status != icp.QUALIFIED:
        return False, f"unrecognised status {status!r}"

    ok, why = is_current(batch, companies)
    if not ok:
        return False, why
    return True, "qualified, and the person-enrichment plan is approved"


def require(batch, companies, rec, verdict, config=None):
    allowed, why = may_enrich(batch, companies, rec, verdict, config)
    if not allowed:
        raise NotApproved(f"{rec.get('domain')}: {why}")
    return True


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--batch")
    p.add_argument("--client")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)

    from . import clients, qualify
    config = {}
    try:
        config = clients.load(a.client)
    except Exception:
        config = {}
    result = qualify.run(store.load(), client=a.client, batch=a.batch,
                         config=config)
    summary = for_batch(result["companies"], config)
    if a.json:
        print(json.dumps({k: v for k, v in summary.items() if k != "plans"},
                         indent=2))
        return 0
    for name in ("companies", "companies_requiring_enrichment",
                 "companies_skipped", "planned_dm_searches",
                 "maximum_contacts", "expected_credits", "maximum_credits",
                 "fallback_exposure"):
        print(f"  {name:<32} {summary[name]}")
    print(f"  {summary['cap_note']}")
    print("  Nothing has been spent: this is a plan.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
