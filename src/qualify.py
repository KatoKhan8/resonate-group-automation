#!/usr/bin/env python3
"""Company first: everything that must happen before a person costs money.

    domains -> normalise -> dedupe -> suppress -> classify -> score -> segment
            -> prioritise -> route personas -> plan the spend -> STOP

The stop is the point. Decision-maker enrichment is the first genuinely
expensive operation in this system, and it is the last thing this module does
not do. A rejected company consumes zero person credits, a company under review
consumes zero person credits, and both keep their records and their reasons so
the decision is answerable later.

Every stage is resumable. A batch that stops at company 2,731 resumes at 2,731,
because each record carries the state it actually reached rather than the stage
somebody thinks the batch is on.

Nothing here calls a provider. The company facts are read from the record; this
module decides what they mean.

  python -m src.qualify --client productive --batch 2026-08
  python -m src.qualify --client productive --dossier northwind
"""
import argparse
import json

from . import (campaignseg, clients, dmplan, geo, icp, ingest, routing,
               segments, store, strategy)

# The order a batch moves through, and the field each stage writes.
STAGES = ("normalised", "deduped", "suppressed", "classified", "scored",
          "segmented", "routed", "planned")


def _qualification_of(rec):
    return rec.get("qualification") or {}


def state_of(rec):
    """Where this record actually is, read from the record itself."""
    qualification = _qualification_of(rec)
    if not qualification:
        return dmplan.NOT_PROCESSED
    if qualification.get("dm_approved"):
        return dmplan.DM_APPROVED
    status = (qualification.get("verdict") or {}).get("icp_status")
    if status == icp.REJECTED:
        return dmplan.REJECTED
    # A human who looked and said no leaves a company that is rejected, not a
    # company still waiting to be looked at. The review queue must not keep
    # handing back work somebody already did.
    if (dmplan.human_review(rec) or {}).get("decision") == REJECT:
        return dmplan.REJECTED
    if status == icp.QUALIFIED:
        return dmplan.QUALIFIED
    if status in (icp.REVIEW, icp.UNKNOWN):
        return dmplan.REVIEW_REQUIRED
    return dmplan.CLASSIFIED


def needs_work(rec, force=False):
    """Has this company already been qualified against the current inputs?

    Cheap and deliberate: the stored fingerprint covers the company facts the
    verdict was derived from, so re-running a batch re-does the companies whose
    facts changed and skips the rest.
    """
    if force:
        return True
    qualification = _qualification_of(rec)
    if not qualification:
        return True
    return qualification.get("inputs_fingerprint") != _inputs_fingerprint(rec)


def _inputs_fingerprint(rec):
    """A digest of everything a verdict is derived from."""
    import hashlib

    facts = rec.get("company_facts") or {}
    material = {
        "company": rec.get("company"),
        "domain": rec.get("domain"),
        "hook": rec.get("hook"),
        "facts": {k: facts.get(k) for k in sorted(facts)},
        "research": sorted(item.get("evidence_id") or ""
                           for item in (rec.get("research") or [])),
    }
    blob = json.dumps(material, sort_keys=True, separators=(",", ":"),
                      default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


# ------------------------------------------------------------ one company

def company(rec, config=None, store_result=True):
    """Classify, score, route and plan one company. Spends nothing."""
    segment = segments.classify(rec, config)
    verdict = icp.score(rec, config, segment=segment)
    persona_plan = routing.plan(rec, segment, verdict, config)
    messaging = strategy.for_company(segment, verdict, persona_plan, config)
    cost = dmplan.for_company(rec, persona_plan, verdict, config)

    result = {
        "record": rec,
        "segment": segment,
        "verdict": verdict,
        "persona_plan": persona_plan,
        "messaging": messaging,
        "cost_plan": cost,
    }
    if store_result:
        rec["qualification"] = {
            "inputs_fingerprint": _inputs_fingerprint(rec),
            "at": store.now(),
            "segment": segment,
            "verdict": verdict,
            "persona_plan": persona_plan,
            "messaging": messaging,
            "cost_plan": cost,
            "dm_approved": (rec.get("qualification") or {}).get("dm_approved",
                                                                False),
            # Carried through requalification rather than dropped. It is safe
            # to carry because every reader compares its fingerprint against
            # the one written above, so a review of the old facts authorises
            # nothing - and keeping it is how the review queue can say "this
            # was reviewed, and then it changed" instead of silently asking
            # for the work again with no explanation.
            "human_review": (rec.get("qualification") or {}).get(
                "human_review"),
        }
        _release_stale_icp_drop(rec)
    return result


# `enrich.outcome` retires a company with no contacts and a rejected verdict
# as `dropped`, with this exact reason, and that is right: it is a decision.
# What it is NOT is an independent fact. The drop is DERIVED from the verdict,
# so when the verdict stops saying rejected the drop has lost the only thing
# holding it up.
#
# Measured on the Productive estate the moment the client's structural
# criteria became the gate: 11 companies the client's own criteria qualify sat
# `dropped` under this reason, written from a verdict the twelve-dimension
# model produced and nothing now agrees with. `dropped` is terminal in
# `run.TERMINAL`, outside `enrich.run`'s states and `blocked` in
# `eligibility._record_state` - so a better verdict would have been computed,
# stored, reported, and been unable to reach a single one of them.
#
# This re-derives it, and only in the safe direction. It never drops anything,
# it touches no record dropped for any other reason - a suppression, a
# duplicate, a human's own rejection, no contact found - and a human's
# recorded `reject` still reads REJECTED through `state_of`, so a person who
# said no is not overruled by a model that changed its mind. The record
# returns to `queued`, which is where the runner already looks, and the log
# says why.
ICP_DROP_RELEASED = ("the ICP rejection this record was dropped under no "
                     "longer stands: returned to the queue as %s")


def _release_stale_icp_drop(rec):
    """Undo a drop whose only justification was a verdict that has changed."""
    from . import enrich

    if rec.get("state") != "dropped":
        return None
    if rec.get("drop_reason") != enrich.ICP_REJECTED:
        return None
    state = state_of(rec)
    if state == dmplan.REJECTED:
        return None
    rec["state"] = "queued"
    rec["drop_reason"] = None
    store.log(rec, "qualify", ICP_DROP_RELEASED % state)
    return state


# --------------------------------------------------- the human review

# A verdict of `review` or `unknown` is not a decision. PLAYBOOK section 1 is
# explicit that both mean zero person credits "until a human decides", and
# until now there was no way to record that a human had. `dmplan.may_enrich`
# even said so out loud - "no review has been recorded" - about a field that
# did not exist.
#
# This is that field. Two things about its shape are deliberate:
#
# **A review is of a verdict, not of a company.** It carries the inputs
# fingerprint the verdict was derived from, so a review given on Monday stops
# authorising anything the moment the company facts change. That is the same
# staleness rule the campaign approval and the person-enrichment approval
# already use, and for the same reason: an approval that survives the thing it
# approved is not an approval.
#
# **Accepting is weaker than rejecting.** A recorded `reject` blocks
# enrichment permanently and needs no policy behind it, because refusing to
# spend is never the dangerous direction. A recorded `accept` only unblocks a
# company where the client's own config has opted in with
# `dm_plan.allow_review_enrichment`, and is otherwise recorded and inert. One
# reviewer clicking a button in a browser must not be able to widen what a
# client agreed to.

ACCEPT = "accept"
REJECT = "reject"
DECISIONS = (ACCEPT, REJECT)


class BadDecision(ValueError):
    """A review decision that is not one of the two there are."""


def record_review(rec, decision, by, note="", at=None):
    """Record that a human looked at this company's verdict and decided.

    Writes onto the record and returns the review. Spends nothing, changes no
    verdict: the score stays what the evidence earned. What this adds is the
    fact that a person saw it, which is a different fact and is stored as one.
    """
    if decision not in DECISIONS:
        raise BadDecision(
            f"{decision!r} is not a review decision; expected one of "
            f"{', '.join(DECISIONS)}")
    qualification = rec.get("qualification")
    if not qualification:
        raise BadDecision(
            "this company has not been qualified yet, so there is no verdict "
            "to review")
    verdict = qualification.get("verdict") or {}
    review = {
        "decision": decision,
        "by": str(by or "unknown"),
        "at": at or store.now(),
        "note": str(note or "")[:500],
        "reviewed_status": verdict.get("icp_status"),
        "reviewed_tier": verdict.get("icp_tier"),
        "reviewed_score": verdict.get("icp_score"),
        # What the verdict was derived from. If this changes, the review is
        # about a company that no longer exists as described.
        "inputs_fingerprint": qualification.get("inputs_fingerprint"),
    }
    qualification["human_review"] = review
    return review


def review_of(rec):
    """The recorded review, or None. Stale reviews are not returned.

    A review whose fingerprint no longer matches the record's current inputs
    is deliberately dropped rather than shown with a warning: every caller of
    this function is asking "may this proceed", and the honest answer once the
    facts moved is no.
    """
    qualification = _qualification_of(rec)
    review = qualification.get("human_review")
    if not review:
        return None
    if review.get("inputs_fingerprint") != qualification.get(
            "inputs_fingerprint"):
        return None
    return review


def stale_review_of(rec):
    """A review that was recorded and has since been outrun by the facts."""
    qualification = _qualification_of(rec)
    review = qualification.get("human_review")
    if not review:
        return None
    if review.get("inputs_fingerprint") == qualification.get(
            "inputs_fingerprint"):
        return None
    return review


def from_stored(rec):
    """Rebuild the result object from what a previous run persisted."""
    qualification = _qualification_of(rec)
    if not qualification:
        return None
    return {
        "record": rec,
        "segment": qualification.get("segment") or {},
        "verdict": qualification.get("verdict") or {},
        "persona_plan": qualification.get("persona_plan") or {},
        "messaging": qualification.get("messaging") or {},
        "cost_plan": qualification.get("cost_plan") or {},
    }


# -------------------------------------------------------------- the batch

def run(recs=None, client=None, batch=None, config=None, force=False,
        limit=None, store_result=True):
    """Qualify a whole batch, skipping companies already done.

    Returns the companies with their segment keys assigned. Nothing about a
    person is looked up, and `dmplan.for_batch` is what says what that would
    cost.
    """
    recs = store.load() if recs is None else recs
    if config is None:
        try:
            config = clients.load(client)
        except Exception:
            config = {}

    mine = [r for r in recs
            if (not client or r.get("client") == client)
            and (not batch or r.get("batch") == batch
                 or r.get("batch_id") == batch)]

    processed, reused, results = 0, 0, []
    for rec in mine:
        if limit is not None and processed >= limit:
            # Stopping early is a normal outcome, not a failure: the rest keep
            # whatever state they had and the next run picks them up.
            break
        if needs_work(rec, force):
            results.append(company(rec, config, store_result))
            processed += 1
        else:
            stored = from_stored(rec)
            results.append(stored if stored else company(rec, config,
                                                         store_result))
            reused += 1

    assigned = campaignseg.assign(results, config)
    # The segment is decided across the whole batch - which rung a company
    # lands on depends on how many others share its key - so it can only be
    # written after `assign`. Persisting it here is what makes "why are these
    # two in the same campaign?" answerable from the record a year later, and
    # what lets the reporting surface count segments without re-running the
    # merge.
    if store_result:
        for entry in assigned:
            qualification = entry["record"].get("qualification")
            if qualification is None:
                continue
            qualification["segment_key"] = entry.get("segment_key")
            qualification["segment_parts"] = entry.get("segment_parts")
            qualification["segment_rung"] = entry.get("segment_rung")
            qualification["segment_reason"] = entry.get("segment_reason")
    return {
        "client": client,
        "batch": batch,
        "companies": assigned,
        "processed": processed,
        "reused": reused,
        "remaining": max(0, len(mine) - len(results)),
        "at": store.now(),
    }


def prioritise(companies):
    """Best first: tier, then score, then how reachable the timezone makes them.

    Deterministic ties: two identical companies must not swap places between
    runs, so the domain is the final key.
    """
    tier_order = {icp.TIER_A: 0, icp.TIER_B: 1, icp.TIER_C: 2,
                  icp.TIER_REVIEW: 3, icp.TIER_NOT_ICP: 4}
    confidence_order = {icp.HIGH: 0, icp.MEDIUM: 1, icp.LOW: 2}

    def key(entry):
        verdict = entry["verdict"]
        return (
            tier_order.get(verdict.get("icp_tier"), 9),
            -float(verdict.get("icp_score") or 0),
            confidence_order.get(verdict.get("icp_confidence"), 9),
            # A company we cannot schedule is worth less than one we can.
            0 if entry["segment"].get("timezone") else 1,
            entry["record"].get("domain") or "",
        )

    return sorted(companies, key=key)


def summarise(result, config=None):
    """The batch numbers, before anything has been spent."""
    companies = result["companies"]
    verdicts = [entry["verdict"] for entry in companies]
    segs = [entry["segment"] for entry in companies]

    return {
        "client": result.get("client"),
        "batch": result.get("batch"),
        "uploaded": len(companies),
        "processed_this_run": result.get("processed"),
        "reused_from_previous_run": result.get("reused"),
        "icp": icp.summarise(verdicts),
        "distribution": {
            "vertical": segments.distribution(segs, "vertical"),
            "subvertical": segments.distribution(segs, "subvertical"),
            "region": segments.distribution(segs, "region"),
            "country": segments.distribution(segs, "country"),
            "employee_band": segments.distribution(segs, "employee_band"),
            "timezone": segments.distribution(segs, "timezone"),
            "business_model": segments.distribution(segs, "business_model"),
        },
        "segments": campaignseg.summarise(companies, config),
        "cost": {k: v for k, v in dmplan.for_batch(companies, config).items()
                 if k != "plans"},
        "schedulable": sum(1 for s in segs if s.get("timezone")),
        "not_schedulable": sum(1 for s in segs if not s.get("timezone")),
    }


# ------------------------------------------------------------- the dossier

def dossier(entry, config=None):
    """Everything known about one company, before any person is looked up.

    This is the object a reviewer reads to decide whether to spend anything.
    It is deliberately complete: an operator who has to open four other tools
    to check a verdict will stop checking verdicts.
    """
    rec = entry["record"]
    segment = entry["segment"]
    verdict = entry["verdict"]
    persona_plan = entry["persona_plan"]
    messaging = entry.get("messaging") or {}
    cost = entry.get("cost_plan") or {}
    facts = rec.get("company_facts") or {}

    schedulable, schedule_why = geo.schedulable(segment, config)

    return {
        "company": rec.get("company"),
        "domain": rec.get("domain"),
        "record_id": rec.get("id"),
        "state": state_of(rec),

        # Whether a person has looked at this verdict, and whether what they
        # decided still applies. A stale review is reported separately rather
        # than folded into the live one, because "nobody has reviewed this"
        # and "somebody reviewed a version of this that no longer exists" are
        # different pieces of work.
        "human_review": review_of(rec),
        "stale_human_review": stale_review_of(rec),

        "icp": {
            "score": verdict.get("icp_score"),
            "tier": verdict.get("icp_tier"),
            "status": verdict.get("icp_status"),
            "confidence": verdict.get("icp_confidence"),
            "reasons": verdict.get("classification_reasons"),
            "positive_signals": verdict.get("positive_signals"),
            "negative_signals": verdict.get("negative_signals"),
            "missing_evidence": verdict.get("missing_evidence"),
        },

        "segment": {
            "vertical": segment.get("vertical"),
            "subvertical": segment.get("subvertical"),
            "vertical_why": segment.get("vertical_why"),
            "industry": segment.get("industry"),
            "business_model": segment.get("business_model"),
            "employee_band": segment.get("employee_band"),
            "employees": segment.get("employees"),
            "company_maturity": segment.get("company_maturity"),
            "delivery_model": segment.get("delivery_model"),
            "office_count": segment.get("office_count"),
            "distributed": segment.get("distributed"),
            "country": segment.get("country"),
            "region": segment.get("region"),
            "region_confidence": segment.get("region_confidence"),
            "city": segment.get("city"),
            "timezone": segment.get("timezone"),
            "timezone_source": segment.get("timezone_source"),
            "timezone_confidence": segment.get("timezone_confidence"),
            "schedulable": schedulable,
            "schedulable_why": schedule_why,
        },

        "evidence": {
            "company_facts": {k: facts.get(k) for k in sorted(facts)
                              if k not in ("icp_flags",)},
            "facts_used": [
                {"fact": item.get("fact"),
                 "source_url": item.get("source_url"),
                 "source_type": item.get("source_type"),
                 "retrieved_at": item.get("retrieved_at"),
                 "published_at": item.get("published_at"),
                 "confidence": item.get("confidence")}
                for item in (rec.get("research") or [])],
            "evidence_count": len(rec.get("research") or []),
        },

        "persona_plan": {
            "strategy": persona_plan.get("strategy"),
            "strategy_reason": persona_plan.get("strategy_reason"),
            "priority_personas": persona_plan.get("persona_priority"),
            "target_titles": persona_plan.get("target_titles"),
            "max_contacts": persona_plan.get("max_contacts_to_enrich"),
            "reason": persona_plan.get("cap_reason"),
        },

        "messaging_plan": {
            "recommended_angles": messaging.get("recommended_angles"),
            "pain_categories": messaging.get("relevant_pain_categories"),
            "persona_angles": messaging.get("persona_angles"),
            "unsupported_hypotheses": messaging.get("unsupported_hypotheses"),
            "why": messaging.get("why"),
        },

        "cost_plan": {
            "enrichment_required": cost.get("enrichment_required"),
            "planned_contacts": cost.get("planned_contacts"),
            "expected_credits": cost.get("expected_credits"),
            "maximum_credits": cost.get("maximum_credits"),
            "fallback_exposure": cost.get("fallback_exposure"),
            "calls": cost.get("calls"),
            "why": cost.get("why"),
        },

        "campaign": {
            "segment_key": entry.get("segment_key"),
            "segment_rung": entry.get("segment_rung"),
            "segment_reason": entry.get("segment_reason"),
        },
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--client")
    p.add_argument("--batch")
    p.add_argument("--dossier", help="a record id to print in full")
    p.add_argument("--force", action="store_true",
                   help="requalify even companies whose inputs have not changed")
    p.add_argument("--limit", type=int)
    p.add_argument("--json", action="store_true")
    p.add_argument("--dry-run", action="store_true",
                   help="score and print without writing verdicts to the queue")
    a = p.parse_args(argv)

    config = {}
    try:
        config = clients.load(a.client)
    except Exception:
        config = {}

    # Verdicts are written back by default. Qualification spends nothing, so
    # the usual dry-run-first rule does not apply here - and without the write
    # the whole resume path is dead: `needs_work` compares against a stored
    # fingerprint, so a run that persists nothing re-derives all 5,000
    # companies every time and `--limit` can never be continued.
    if a.dry_run:
        result = run(client=a.client, batch=a.batch, config=config,
                     force=a.force, limit=a.limit, store_result=False)
    else:
        with store.transaction() as recs:
            result = run(recs, client=a.client, batch=a.batch, config=config,
                         force=a.force, limit=a.limit, store_result=True)

    if a.dossier:
        entry = next((e for e in result["companies"]
                      if e["record"].get("id") == a.dossier), None)
        if entry is None:
            print(f"REFUSED: no such record in this batch: {a.dossier}")
            return 2
        print(json.dumps(dossier(entry, config), indent=2, ensure_ascii=False))
        return 0

    summary = summarise(result, config)
    if a.json:
        print(json.dumps(summary, indent=2))
        return 0

    icp_counts = summary["icp"]
    print(f"  uploaded                {summary['uploaded']}")
    for status, count in icp_counts["status"].items():
        print(f"    {status:<20} {count}")
    for tier, count in icp_counts["tier"].items():
        print(f"    tier {tier:<15} {count}")
    print(f"  needs manual review     {icp_counts['needs_manual_review']}")
    print(f"  schedulable             {summary['schedulable']}"
          f" (no timezone: {summary['not_schedulable']})")
    print(f"  campaign segments       {summary['segments']['segments']}")
    cost = summary["cost"]
    print(f"  planned DM searches     {cost['planned_dm_searches']}")
    print(f"  maximum contacts        {cost['maximum_contacts']}")
    print(f"  expected credits        {cost['expected_credits']}")
    print(f"  maximum exposure        {cost['maximum_credits']}")
    print("  Nothing has been spent. Person enrichment needs an approved plan.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
