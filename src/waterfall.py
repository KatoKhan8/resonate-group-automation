#!/usr/bin/env python3
"""The provider waterfall, written down so it can be argued with.

The rule is one sentence: ContactOut first wherever it can supply the data, and
a paid fallback only when there is a stated reason it could not. The rest of
this module exists because that sentence is easy to agree with and easy to
violate quietly - a fallback that runs "just in case" spends real money and
looks exactly like one that ran because it was needed.

So every stage names its providers in order, and every step down the waterfall
must carry:

    reason          why the provider above it did not answer
    provider        who is being asked instead
    expected_cost   what we believe it costs, in that provider's own units
    actual_cost     what it actually cost, when the provider tells us
    result          what came back
    next_reason     what would have to be true to go one step further

A step with no reason is refused rather than logged, because "we called it
anyway" is the failure this whole module is built to make visible.

Nothing here calls a provider. It plans, records and audits; `src/enrich.py`
and `src/research.py` do the calling.

  python -m src.waterfall --describe
  python -m src.waterfall --record acme
"""
import argparse
import json

from . import enrich, store

# ----------------------------------------- the five ContactOut outcome classes
#
# PROVIDER-ROUTING-POLICY.md requires these to be distinguishable. Only the
# first two may license a paid fallback; the other three are transient failures
# that must retry or hold, never switch providers silently.
#
# An error is not a miss. A timeout is not a miss. A rate limit is not a miss.
# Only a confirmed miss or a structural capability gap licenses paying a second
# provider for data ContactOut has and was simply not asked properly.

CONTACTOUT_CONFIRMED_MISS = "contactout_confirmed_miss"
CONTACTOUT_CAPABILITY_UNAVAILABLE = "contactout_capability_unavailable"
CONTACTOUT_ERROR = "contactout_error"
CONTACTOUT_TIMEOUT = "contactout_timeout"
CONTACTOUT_RATE_LIMITED = "contactout_rate_limited"

# The three transient classes. A reason in this set is NEVER in any
# accepted_reasons list, so may_fall_back refuses it by construction.
TRANSIENT_REASONS = frozenset({
    CONTACTOUT_ERROR,
    CONTACTOUT_TIMEOUT,
    CONTACTOUT_RATE_LIMITED,
})

# Every accepted fallback reason maps to exactly one outcome class. Two state
# machines for one fact is how they drift, so this is the ONLY mapping.
REASON_CLASS = {
    enrich.CONTACTOUT_NO_PEOPLE:              CONTACTOUT_CONFIRMED_MISS,
    enrich.CONTACTOUT_NO_TARGET_PERSONA:      CONTACTOUT_CONFIRMED_MISS,
    enrich.CONTACTOUT_RESULT_COLLISION:       CONTACTOUT_CONFIRMED_MISS,
    enrich.CONTACTOUT_REBRAND_DETECTED:       CONTACTOUT_CONFIRMED_MISS,
    enrich.DOMAIN_UNSTAFFED:                  CONTACTOUT_CONFIRMED_MISS,
    enrich.CONTACTOUT_INCOMPLETE:             CONTACTOUT_CONFIRMED_MISS,
    enrich.CONTACTOUT_NO_COMPANY_LINKEDIN:    CONTACTOUT_CONFIRMED_MISS,
    enrich.CONTACTOUT_MISSING_COMPANY_DATA:   CONTACTOUT_CONFIRMED_MISS,
    enrich.PUBLIC_EVIDENCE_REQUIRED:          CONTACTOUT_CAPABILITY_UNAVAILABLE,
    enrich.CONTACTOUT_NO_EMAIL_DOMAIN:        CONTACTOUT_CAPABILITY_UNAVAILABLE,
    "verification_inconclusive":              CONTACTOUT_CONFIRMED_MISS,
    "verification_contradiction":             CONTACTOUT_CONFIRMED_MISS,
    CONTACTOUT_ERROR:                         CONTACTOUT_ERROR,
    CONTACTOUT_TIMEOUT:                       CONTACTOUT_TIMEOUT,
    CONTACTOUT_RATE_LIMITED:                  CONTACTOUT_RATE_LIMITED,
}


def classify(reason):
    """Map a fallback reason to its outcome class, or None if unknown."""
    return REASON_CLASS.get(reason)


def is_transient(reason):
    """True when the reason is a transient failure that must NOT license fallback."""
    return reason in TRANSIENT_REASONS


# ---------------------------------------------------------------- the stages
#
# Ordered. Position 0 is ContactOut wherever ContactOut can answer at all, and
# where it cannot the comment says why rather than leaving it to be inferred.

CONTACTOUT = "contactout"
WEBFETCH = "webfetch"
XAI = "xai"
AIARK = "aiark"
DELIVERABLE = "deliverable"
REOON = "reoon"
APIFY = "apify"
BLITZ = "blitz"

COMPANY_INFO = "company_information"
PEOPLE_DISCOVERY = "people_discovery"
LINKEDIN_URL = "linkedin_url"
EMAIL_DISCOVERY = "email_discovery"
EMAIL_VERIFICATION = "email_verification"
COMPANY_RESEARCH = "company_research"
PERSON_RESEARCH = "person_research"

STAGES = {
    COMPANY_INFO: {
        "question": "who is this company?",
        "providers": (
            {"provider": CONTACTOUT, "call": "company-information-from-domain",
             "why": "ContactOut resolves a domain to a company record, and the "
                    "call is one credit",
             "sufficient_when": "industry, size and a name all came back"},
            {"provider": WEBFETCH, "call": "webfetch-crawl",
             "why": "free HTTP read of the company's own website; one crawl "
                    "per company, cached across its contacts",
             "sufficient_when": "usable prose came back from the site's own "
                                "pages"},
            {"provider": XAI, "call": "xai-research",
             "why": "Grok with web search for current, ambiguous company facts "
                    "that structured data and a static crawl cannot answer; "
                    "off by default, enabled per workspace via xai.enabled",
             "is_fallback": True,
             "requires_reason": enrich.CONTACTOUT_MISSING_COMPANY_DATA,
             "sufficient_when": "a sourced, current fact about the company "
                                "came back with source URLs"},
            {"provider": BLITZ, "call": "blitz-domain-to-linkedin",
             "why": "ContactOut's /domain/enrich carries li_vanity, so this "
                    "runs only when that company record came back without a "
                    "LinkedIn URL - and every Blitz search is addressed by "
                    "company LinkedIn URL rather than by domain",
             "requires_reason": enrich.CONTACTOUT_NO_COMPANY_LINKEDIN,
             "sufficient_when": "a /company/ URL came back"},
            {"provider": BLITZ, "call": "blitz-linkedin-to-domain",
             "why": "the mail domain is not always the website domain (trap "
                    "3) and no ContactOut response carries one under any "
                    "spelling: this is a gap, not a miss",
             "requires_reason": enrich.CONTACTOUT_NO_EMAIL_DOMAIN,
             "sufficient_when": "an email domain came back"},
            {"provider": BLITZ, "call": "blitz-company",
             "why": "the ContactOut company record was missing what the "
                    "verdict or the copy needs",
             "requires_reason": enrich.CONTACTOUT_MISSING_COMPANY_DATA,
             "sufficient_when": "the missing firmographic came back"},
            {"provider": APIFY, "call": "apify-research",
             "why": "the structured record was missing what the copy needs",
             "requires_reason": enrich.CONTACTOUT_MISSING_COMPANY_DATA,
             "sufficient_when": "the homepage or about page supplied the gap"},
        ),
    },
    PEOPLE_DISCOVERY: {
        "question": "who works there that we should talk to?",
        "providers": (
            {"provider": CONTACTOUT, "call": "people-count",
             "why": "free, and it answers whether anybody is there at all",
             "sufficient_when": "the count is zero - which ends the record"},
            {"provider": CONTACTOUT, "call": "decision-makers",
             "why": "returns the people and their addresses in one call",
             "sufficient_when": "a contact in a target persona came back"},
            {"provider": BLITZ, "call": "blitz-employee-finder",
             "why": "ContactOut produced no usable person, and Blitz indexes "
                    "the company by its LinkedIn URL rather than by its "
                    "domain - a different index, so it is the fallback most "
                    "likely to answer where a domain lookup could not",
             "requires_reason": (enrich.CONTACTOUT_NO_PEOPLE,
                                 enrich.CONTACTOUT_NO_TARGET_PERSONA,
                                 enrich.CONTACTOUT_RESULT_COLLISION,
                                 enrich.CONTACTOUT_REBRAND_DETECTED,
                                 enrich.DOMAIN_UNSTAFFED),
             "sufficient_when": "a person in a target persona came back"},
            {"provider": AIARK, "call": "aiark-people-search",
             "why": "ContactOut found nobody, or nobody in a target persona, "
                    "and Blitz did not resolve one either",
             # Every way ContactOut can come back with nobody usable, which is
             # more than "the list was empty". A parked domain (people-count
             # 0), a rebrand onto another domain and a result set that was
             # entirely name collisions are all BUILD-SPEC section 9 traps, and
             # all three are the same fact: ContactOut has been paid and has no
             # usable person. Naming only two of the five left the other three
             # unjustifiable at audit while enrich produced them happily.
             "requires_reason": (enrich.CONTACTOUT_NO_PEOPLE,
                                 enrich.CONTACTOUT_NO_TARGET_PERSONA,
                                 enrich.CONTACTOUT_RESULT_COLLISION,
                                 enrich.CONTACTOUT_REBRAND_DETECTED,
                                 enrich.DOMAIN_UNSTAFFED),
             "sufficient_when": "a person in a target persona came back"},
        ),
    },
    LINKEDIN_URL: {
        "question": "what is this person's profile?",
        "providers": (
            {"provider": CONTACTOUT, "call": "decision-makers",
             "why": "the profile arrives with the person; no separate call",
             "sufficient_when": "a canonical /in/ URL came back"},
            {"provider": BLITZ, "call": "blitz-employee-finder",
             "why": "Blitz is addressed by company LinkedIn URL and returns "
                    "the profile with the person, so it answers this question "
                    "in the same call that answers people discovery - and it "
                    "goes ahead of AI Ark because ContactOut's own miss is "
                    "what licenses it",
             "requires_reason": enrich.CONTACTOUT_INCOMPLETE,
             "sufficient_when": "a canonical /in/ URL came back"},
            {"provider": AIARK, "call": "aiark-people-search",
             "why": "no profile arrived with the ContactOut result and Blitz "
                    "did not resolve one either",
             "requires_reason": enrich.CONTACTOUT_INCOMPLETE,
             "sufficient_when": "a canonical /in/ URL came back"},
        ),
    },
    EMAIL_DISCOVERY: {
        "question": "what is this person's address?",
        "providers": (
            {"provider": CONTACTOUT, "call": "decision-makers",
             "why": "the address arrives with the person; no separate call",
             "sufficient_when": "a work address came back"},
            {"provider": BLITZ, "call": "blitz-email",
             "why": "the person is known by their LinkedIn profile and still "
                    "has no address. Ahead of AI Ark: Blitz is addressed by "
                    "the profile we already hold, so it answers the narrower "
                    "question, and one record beats a two-credit search",
             "requires_reason": enrich.CONTACTOUT_INCOMPLETE,
             "sufficient_when": "a work address came back - unverified, and "
                                "still subject to section 6.1"},
            {"provider": AIARK, "call": "aiark-people-search",
             "why": "ContactOut returned the person without an address and "
                    "Blitz had no profile to address, or missed",
             "requires_reason": enrich.CONTACTOUT_INCOMPLETE,
             "sufficient_when": "a work address came back"},
        ),
    },
    EMAIL_VERIFICATION: {
        "question": "may we write to this address?",
        "providers": (
            {"provider": CONTACTOUT, "call": "email-verifier",
             "why": "one credit, and it is the provider that supplied the "
                    "address",
             "sufficient_when": "the verdict is valid or invalid - both are "
                                "answers"},
            {"provider": DELIVERABLE, "call": "deliverable-verify",
             "why": "ContactOut returned accept_all or unknown, which is not "
                    "an answer",
             "requires_reason": "verification_inconclusive",
             "sufficient_when": "a definite deliverable verdict came back"},
            {"provider": REOON, "call": "reoon-verify",
             "why": "the second opinion disagreed with the first, or was also "
                    "inconclusive",
             "requires_reason": "verification_contradiction",
             "sufficient_when": "never automatically - a third disagreement "
                                "holds the contact rather than resolving it"},
        ),
    },
    COMPANY_RESEARCH: {
        "question": "what is true about this company that is worth writing?",
        "providers": (
            {"provider": CONTACTOUT, "call": "company-information-from-domain",
             "why": "structured facts are already paid for and need no parsing",
             "sufficient_when": "the facts support a hook and an angle"},
            {"provider": WEBFETCH, "call": "webfetch-crawl",
             "why": "free HTTP read of the company's own website; one crawl "
                    "per company, cached across its contacts",
             "sufficient_when": "a dated, attributable fact from the company's "
                                "own pages came back"},
            {"provider": APIFY, "call": "apify-research",
             "why": "the structured facts do not support a specific hook, or "
                    "the client's research policy asks for web research",
             "requires_reason": (enrich.PUBLIC_EVIDENCE_REQUIRED,
                                 enrich.CONTACTOUT_MISSING_COMPANY_DATA),
             "sufficient_when": "a dated, attributable fact came back"},
        ),
    },
    PERSON_RESEARCH: {
        "question": "what is true about this person that is worth writing?",
        "providers": (
            {"provider": CONTACTOUT, "call": "decision-makers",
             "why": "role, seniority and tenure arrive with the person",
             "sufficient_when": "the role itself carries the angle"},
            {"provider": APIFY, "call": "apify-research",
             "why": "the role alone does not personalise, and public "
                    "professional content may exist",
             "requires_reason": enrich.PUBLIC_EVIDENCE_REQUIRED,
             "sufficient_when": "a dated, attributable, publicly accessible "
                                "fact about this person came back"},
        ),
    },
}

STAGE_NAMES = tuple(STAGES)

# What each provider actually bills in. Apify costing 0 *credits* is true and
# misleading on its own: it bills compute units, which are real money in a
# different currency. Naming the unit keeps "0" from reading as "free".
COST_UNITS = {
    CONTACTOUT: "contactout credits",
    WEBFETCH: "free (HTTP read, no credit cost)",
    XAI: "xAI ticks (10B ticks per USD)",
    AIARK: "ai ark credits",
    DELIVERABLE: "deliverable credits",
    REOON: "reoon credits",
    APIFY: "apify compute units (not credits; not counted in the credit cap)",
    BLITZ: "blitz records (fair_usage.records_used on the response is the "
           "real cost; a missing block means unknown, never zero)",
}


class WaterfallViolation(RuntimeError):
    """A paid fallback was asked for without a reason the stage recognises."""


def providers_for(stage):
    return tuple(step["provider"] for step in STAGES[stage]["providers"])


def first_provider(stage):
    return providers_for(stage)[0]


def contactout_is_first(stage):
    """The invariant, asked as a question so a test can assert it."""
    return first_provider(stage) == CONTACTOUT


def step_for(stage, provider, call=None):
    for step in STAGES[stage]["providers"]:
        if step["provider"] == provider and (call is None
                                             or step["call"] == call):
            return step
    return None


def accepted_reasons(stage, provider, call=None):
    step = step_for(stage, provider, call)
    if step is None:
        return ()
    required = step.get("requires_reason")
    if required is None:
        return ()
    return (required,) if isinstance(required, str) else tuple(required)


def is_fallback(stage, provider, call=None):
    """A step is a fallback when it declares what must be true to reach it.

    Two ContactOut calls in sequence - a free count, then the paid lookup it
    justifies - are the primary path, not a fallback, and demanding a reason
    for the second would be theatre. What needs justifying is leaving the
    provider we already paid.
    """
    step = step_for(stage, provider, call)
    return bool(step and step.get("requires_reason"))


def may_fall_back(stage, provider, reason, call=None):
    """Is this step permitted, given the reason offered for it?

    Primary-path steps need no reason. Fallback steps need one the stage
    names, and "we called it anyway" is not one. A transient failure - an
    error, a timeout, a rate limit - is never a reason to pay a second
    provider; retry or hold instead.
    """
    if stage not in STAGES:
        raise KeyError(stage)
    step = step_for(stage, provider, call)
    if step is None:
        return False, f"{provider} is not part of the {stage} waterfall"
    if not is_fallback(stage, provider, call):
        return True, "primary path for this stage; no fallback reason needed"
    if not reason:
        return False, "a paid fallback needs a reason; this one offered none"
    if is_transient(reason):
        return False, (f"{reason!r} is a transient failure, not a miss; "
                       f"a fallback would pay twice for data ContactOut has")
    allowed = accepted_reasons(stage, provider, call)
    if reason not in allowed:
        return False, (f"{reason!r} is not a reason to fall back to {provider} "
                       f"for {stage}; accepted: {', '.join(allowed)}")
    return True, f"{reason} is an accepted reason to ask {provider}"


def require(stage, provider, reason, call=None):
    ok, why = may_fall_back(stage, provider, reason, call)
    if not ok:
        raise WaterfallViolation(why)
    return True


# --------------------------------------------------------------- the ledger

def entry(stage, provider, call, reason=None, result=None, expected_cost=None,
          actual_cost=None, next_reason=None, at=None):
    """One rung of the waterfall, as it actually happened."""
    if expected_cost is None:
        expected_cost = enrich.COSTS.get(call, 0)
    return {
        "stage": stage,
        "provider": provider,
        "call": call,
        "cost_unit": COST_UNITS.get(provider, "unknown"),
        "reason": reason,
        "expected_cost": expected_cost,
        # None rather than a copy of the estimate: most providers do not tell
        # us, and a guess in this field would make the ledger useless.
        "actual_cost": actual_cost,
        "result": result,
        "next_reason": next_reason,
        "at": at or store.now(),
    }


def record_step(rec, stage, provider, call, reason=None, result=None,
                expected_cost=None, actual_cost=None, next_reason=None,
                enforce=True):
    """Append to this record's waterfall ledger, refusing an unjustified step."""
    if enforce:
        require(stage, provider, reason, call)
    row = entry(stage, provider, call, reason, result, expected_cost,
                actual_cost, next_reason)
    rec.setdefault("waterfall", []).append(row)
    return row


def ledger(rec):
    return list(rec.get("waterfall") or [])


def spend(rec):
    """What this record cost, split by what we believe and what we were told."""
    rows = ledger(rec)
    told = [r["actual_cost"] for r in rows if r.get("actual_cost") is not None]
    return {
        "expected": sum(r.get("expected_cost") or 0 for r in rows),
        "reported": sum(told) if told else None,
        "calls": len(rows),
        "by_provider": _by(rows, "provider"),
        "by_stage": _by(rows, "stage"),
    }


def _by(rows, field):
    out = {}
    for row in rows:
        key = row.get(field) or "unknown"
        bucket = out.setdefault(key, {"calls": 0, "expected": 0})
        bucket["calls"] += 1
        bucket["expected"] += row.get("expected_cost") or 0
    return out


def audit(rec):
    """Every step that was taken without a reason the waterfall accepts.

    This is the report that answers "are we spending money we did not need
    to?", and it reads the ledger rather than the code, so it catches a
    fallback that bypassed `record_step` only if that fallback logged itself
    at all. What it cannot see is named in `unlogged`.
    """
    problems = []
    for row in ledger(rec):
        ok, why = may_fall_back(row.get("stage"), row.get("provider"),
                                row.get("reason"), row.get("call"))
        if not ok:
            problems.append({"stage": row.get("stage"),
                             "provider": row.get("provider"),
                             "call": row.get("call"),
                             "reason": row.get("reason"), "why": why})
    return {
        "record_id": rec.get("id"),
        "steps": len(ledger(rec)),
        "unjustified": problems,
        "spend": spend(rec),
        "unlogged": "a provider call that never called record_step is "
                    "invisible here; the tests assert enrich.py logs its own",
    }


def describe():
    """The whole waterfall as data, for the preview page and for reading."""
    out = {}
    for stage, spec in STAGES.items():
        out[stage] = {
            "question": spec["question"],
            "contactout_first": contactout_is_first(stage),
            "providers": [
                {"provider": step["provider"], "call": step["call"],
                 "why": step["why"],
                 "expected_cost": enrich.COSTS.get(step["call"], 0),
                 "cost_unit": COST_UNITS.get(step["provider"], "unknown"),
                 "is_fallback": is_fallback(stage, step["provider"],
                                            step["call"]),
                 "sufficient_when": step["sufficient_when"],
                 "requires_reason": accepted_reasons(stage, step["provider"],
                                                     step["call"]) or None}
                for step in spec["providers"]],
        }
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--describe", action="store_true")
    p.add_argument("--record")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)

    if a.record:
        rec = store.get(a.record)
        if rec is None:
            print(f"REFUSED: no such record: {a.record}")
            return 2
        result = audit(rec)
        print(json.dumps(result, indent=2) if a.json else
              _text_audit(result, rec))
        return 0

    described = describe()
    if a.json or not a.describe:
        print(json.dumps(described, indent=2))
        return 0
    for stage, spec in described.items():
        print(f"\n{stage}  -  {spec['question']}")
        for n, step in enumerate(spec["providers"]):
            lead = "  1." if n == 0 else f"  {n + 1}."
            print(f"{lead} {step['provider']} / {step['call']} "
                  f"(expected {step['expected_cost']} {step['cost_unit']})")
            print(f"      why: {step['why']}")
            print(f"      enough when: {step['sufficient_when']}")
            if step["requires_reason"]:
                print(f"      only after: {', '.join(step['requires_reason'])}")
    return 0


def _text_audit(result, rec):
    lines = [f"{result['record_id']}: {result['steps']} waterfall step(s), "
             f"expected spend {result['spend']['expected']}"]
    for problem in result["unjustified"]:
        lines.append(f"  UNJUSTIFIED: {problem['why']}")
    if not result["unjustified"]:
        lines.append("  every step carries a reason the waterfall accepts")
    return "\n".join(lines)


# --------------------------------------------------------- telemetry counters
#
# Aggregated from the waterfall ledger, which is the single source of truth.
# A second counter store would drift from it; these read the rows.
#
# PROVIDER-ROUTING-POLICY.md names seven counters. CONTACTOUT_CACHE_HITS
# cannot be derived from the ledger (a cache hit does not produce a row), so
# it is tracked separately at the call site in src/providers/contactout.py
# and merged in here by the caller.

def counters(records, cache_hits=0):
    """Aggregate the policy's seven counters from a collection of records.

    Each escalation carries its WHY: the reason code from the ledger row that
    licensed leaving ContactOut. A fallback without a reason is counted under
    CONTACTOUT_ERRORS because an unjustified fallback is the failure this
    module exists to make visible.

    CONTACTOUT_CONFIRMED_MISSES counts the fallback steps whose reason
    classifies as a confirmed miss - that is the event that licensed paying
    the next provider. CONTACTOUT_ERRORS counts fallback steps whose reason
    is transient (error, timeout, rate limit) - these should never appear
    because may_fall_back refuses them, but the counter makes a violation
    visible rather than silent.
    """
    contactout_calls = 0
    contactout_confirmed_misses = 0
    contactout_errors = 0
    crawler_calls = 0
    grok_escalations = 0
    other_provider_escalations = 0
    escalation_reasons = []

    for rec in records:
        for row in ledger(rec):
            provider = row.get("provider")
            call = row.get("call")
            reason = row.get("reason")

            if provider == CONTACTOUT:
                contactout_calls += 1
                continue

            cls = classify(reason) if reason else None

            if cls == CONTACTOUT_CONFIRMED_MISS:
                contactout_confirmed_misses += 1
            elif cls in (CONTACTOUT_ERROR, CONTACTOUT_TIMEOUT,
                         CONTACTOUT_RATE_LIMITED):
                contactout_errors += 1

            if provider in ("apify",) and call and "research" in call:
                crawler_calls += 1

            if call and "xai" in call:
                grok_escalations += 1
                escalation_reasons.append({"provider": provider,
                                           "call": call, "reason": reason})
            elif is_fallback(row.get("stage"), provider, call):
                other_provider_escalations += 1
                escalation_reasons.append({"provider": provider,
                                           "call": call, "reason": reason})

    return {
        "CONTACTOUT_CALLS": contactout_calls,
        "CONTACTOUT_CACHE_HITS": cache_hits,
        "CONTACTOUT_CONFIRMED_MISSES": contactout_confirmed_misses,
        "CONTACTOUT_ERRORS": contactout_errors,
        "CRAWLER_CALLS": crawler_calls,
        "GROK_ESCALATIONS": grok_escalations,
        "OTHER_PROVIDER_ESCALATIONS": other_provider_escalations,
        "escalation_reasons": escalation_reasons,
    }


if __name__ == "__main__":
    raise SystemExit(main())
