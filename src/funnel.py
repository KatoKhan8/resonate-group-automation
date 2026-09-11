#!/usr/bin/env python3
"""Where a cohort's domains went, with every rate carrying its own denominator.

## Why this is not `report.funnel`

`report.funnel` gives raw counts and is right to: it is the campaign screen's
numbers. What it cannot answer is "of the two hundred that entered, how many
should have got here, and what happened to the rest" - it has no denominators,
no stage relationships and no loss reasons. A count without a denominator is
the shape of claim that let `conversionRate` in a reference implementation
silently fall as its corpus grew.

So each stage here declares FOUR things as data rather than computing a
percentage in passing:

    count        the numerator
    of           which earlier stage is the denominator
    eligible     who was even a candidate, when that differs from `of`
    truth        the canonical field the count is read from

A rate is only emitted when its denominator is non-zero, and a stage that does
not exist yet reports MISSING rather than 0 - because "no campaign has been
staged" and "staging is not built" are different facts and only one of them is
a funnel result.

## Attrition is per record, and it is the useful half

A stage table says 105 domains are UNKNOWN. It does not say whether that is a
correct business answer or a software failure, and those need opposite
responses. `attrition()` gives every record one dominant reason from a closed
vocabulary, and `GOOD` marks the reasons that are the system working -
a four-person agency is not a funnel loss, it is a correct rejection.

Nothing here calls a provider or mutates a record.
"""
import argparse
import collections
import json

from src import store

MISSING = "MISSING"

# ---------------------------------------------------------------- the stages
#
# Ordered, and each names its own denominator. `of=None` means this is the
# entry stage and its own denominator.
RECORDS, PEOPLE, ACTIONS = "records", "people", "actions"

STAGES = (
    ("input_domains", None, RECORDS, "every record in the cohort", "queue row"),
    ("valid_domains", "input_domains", RECORDS, "a parseable domain",
     "rec.domain"),
    ("company_facts", "valid_domains", RECORDS,
     "anything learned about the company",
     "rec.company_facts beyond headcount_signal"),
    ("researched", "valid_domains", RECORDS, "public evidence was gathered",
     "rec.research"),
    ("scoreable", "company_facts", RECORDS,
     "at least one ICP dimension scored",
     "verdict.positive_signals + negative_signals"),
    ("confidence_medium_or_high", "scoreable", RECORDS,
     "evidence good enough to act on", "verdict.icp_confidence"),
    ("qualified", "scoreable", RECORDS, "an ICP verdict of qualified",
     "verdict.icp_status"),
    ("people_found", "qualified", PEOPLE,
     "a person discovered at a qualified company", "rec.contacts"),
    ("emails_found", "people_found", PEOPLE, "a person with an address",
     "contact.email"),
    ("emails_2_of_2_verified", "emails_found", PEOPLE,
     "two independent verifier confirmations",
     "contact.verification.confirmation_count"),
    ("linkedin_found", "people_found", PEOPLE,
     "a person with a usable profile", "contact.linkedin"),
    ("campaign_ready", "people_found", PEOPLE,
     "every gate passed, not merely verification", "eligibility.decide"),
    ("approved", "campaign_ready", PEOPLE,
     "a human approved this exact copy", "approval fingerprint"),
    # "THIS SYSTEM staged it", not "the provider holds it". Those are two
    # different claims and today they disagree: HeyReach campaign 594061 holds
    # one real staged lead, and this reads 0, because the lead was put there by
    # a person in the vendor UI. It is correct - the ledger records what this
    # system did, and this system did not do that - and the old wording
    # promised provider truth from a source that cannot answer for it.
    #
    # Worth knowing which way it errs: every staging today happens outside this
    # system, because `AddLeadsToCampaignV2` is deliberately unimplemented and
    # `providerwrites.SUPPORTED` is empty. So this stage under-reports, which
    # is the safe direction for a count of prospect-facing actions, and it will
    # keep reading 0 until a supported staging write exists. The same is true
    # one row down for `live`.
    ("provider_staged", "approved", ACTIONS,
     "this system staged the lead with the provider", "action ledger"),
    ("readback_verified", "provider_staged", ACTIONS,
     "provider truth matched approved material", "configdiff"),
    ("live", "readback_verified", ACTIONS,
     "this system confirmed a prospect-facing action",
     "action ledger state SENT"),
    ("replied", "live", ACTIONS, "an authoritative inbound event",
     "rec.events"),
    ("positive", "replied", ACTIONS, "a reply classified positive",
     "reply state"),
    ("meeting", "replied", ACTIONS, "an authoritative booking signal",
     "not built"),
)

# A rate across two different units is not a rate. See `measure`.
UNIT_OF = {name: unit for name, _of, unit, _e, _t in STAGES}

# ------------------------------------------------------------- the attrition
#
# One dominant reason per record, from a closed vocabulary. GOOD names the
# ones that are the system working correctly rather than failing.
ICP_REJECT = "ICP_REJECT"
ICP_REVIEW = "ICP_REVIEW"
LOW_CONFIDENCE = "LOW_CONFIDENCE"
MISSING_EVIDENCE = "MISSING_EVIDENCE"
NO_COMPANY_DATA = "NO_COMPANY_DATA"
NO_PERSON = "NO_PERSON"
NO_EMAIL = "NO_EMAIL"
EMAIL_VERIFY_FAILED = "EMAIL_VERIFY_FAILED"
NO_LINKEDIN = "NO_LINKEDIN"
SUPPRESSED = "SUPPRESSED"
DROPPED = "DROPPED"
READY = "READY"
OTHER = "OTHER"
# Low confidence because nothing was GATHERED, not because the evidence was
# weighed and found wanting.
#
# MEASURED, and it is the difference between two opposite fixes. Of 75
# LOW_CONFIDENCE records in the 250 cohort, 74 had never been researched at
# all - `max_runs_per_batch` is 10, so 183 of 200 domains never got a scrape.
# The one that WAS researched classified successfully. So this bucket is a
# throughput ceiling, recoverable by spending, and reporting it as
# LOW_CONFIDENCE invites somebody to go looking for a scoring bug that is not
# there.
RESEARCH_NOT_RUN = "RESEARCH_NOT_RUN"
# We asked and the provider had nothing. Distinct from a budget limit, because
# spending more buys the same empty answer.
#
# MEASURED: all 28 such records in the 250 cohort have `headcount_signal = 0` -
# ContactOut knows zero people at the domain - and the company lookup RAN and
# returned nothing. Reporting that as a software question sends somebody to
# read code about a domain the vendor has never heard of.
NO_PROVIDER_COVERAGE = "NO_PROVIDER_COVERAGE"

# FOUR outcomes, because the fixes are four different things and a report that
# conflates them points at the wrong one. Good: the rule worked. Bounded: we
# chose not to spend, recoverable by spending. Provider: we spent and the
# vendor had nothing, recoverable only by a different source. Software:
# somebody has to read code.
GOOD = frozenset((ICP_REJECT, SUPPRESSED, READY))
BOUNDED = frozenset((RESEARCH_NOT_RUN,))
PROVIDER = frozenset((NO_PROVIDER_COVERAGE,))
# A verdict of `review` is the model saying a person should decide. That is a
# QUEUE, not a defect and not a loss - but it is also the state most likely to
# become a graveyard, so it gets its own line rather than being folded into
# "working".
NEEDS_HUMAN = frozenset((ICP_REVIEW,))


def _verdict(rec):
    return ((rec.get("qualification") or {}).get("verdict") or {})


def _dimensions(rec):
    v = _verdict(rec)
    return len(v.get("positive_signals") or []) + len(v.get("negative_signals") or [])


def _has_company_data(rec):
    """More than the free headcount probe, which every domain gets."""
    facts = rec.get("company_facts") or {}
    return bool(set(facts) - {"headcount_signal"})


def _contacts(rec):
    return list(rec.get("contacts") or [])


def _confirmations(contact):
    return int(((contact.get("verification") or {}).get("confirmation_count")
                or 0))


def counts(recs):
    """The numerator for every stage. MISSING where the stage is not built."""
    contacts = [c for r in recs for c in _contacts(r)]
    qualified = [r for r in recs if _verdict(r).get("icp_status") == "qualified"]
    return {
        "input_domains": len(recs),
        "valid_domains": sum(1 for r in recs if r.get("domain")),
        "company_facts": sum(1 for r in recs if _has_company_data(r)),
        "researched": sum(1 for r in recs if r.get("research")),
        "scoreable": sum(1 for r in recs if _dimensions(r) > 0),
        "confidence_medium_or_high": sum(
            1 for r in recs
            if _verdict(r).get("icp_confidence") in ("medium", "high")),
        "qualified": len(qualified),
        "people_found": sum(len(_contacts(r)) for r in qualified),
        "emails_found": sum(1 for r in qualified for c in _contacts(r)
                            if c.get("email")),
        "emails_2_of_2_verified": sum(1 for r in qualified for c in _contacts(r)
                                      if _confirmations(c) >= 2),
        "linkedin_found": sum(1 for r in qualified for c in _contacts(r)
                              if c.get("linkedin")),
        # Read from canonical state, never inferred. An empty action ledger
        # means nothing has been staged, which is a real answer.
        "campaign_ready": _campaign_ready(recs),
        "approved": _approved(recs),
        "provider_staged": _ledger_count(("attempted", "sent", "unresolved")),
        "readback_verified": MISSING,
        "live": _ledger_count(("sent",)),
        "replied": _replies(recs),
        "positive": _positive(recs),
        "meeting": MISSING,
    }


def _campaign_ready(recs):
    """Every gate, not merely verification. Counted by asking the authority."""
    from src import clients, eligibility

    ready, configs = 0, {}
    for rec in recs:
        if _verdict(rec).get("icp_status") != "qualified":
            continue
        client = rec.get("client")
        if client not in configs:
            try:
                configs[client] = clients.load(client)
            except Exception:
                configs[client] = None
        for contact in _contacts(rec):
            for step_key, steps in (rec.get("cadence") or {}).items():
                pass
            for contact_key, steps in (rec.get("cadence") or {}).items():
                if contact_key != contact.get("key"):
                    continue
                for step_key, step in steps.items():
                    try:
                        got = eligibility.decide(
                            rec, contact, step_key,
                            channel=step.get("channel"), step=step,
                            config=configs[client])
                    except Exception:
                        continue
                    if got.get("verdict") == eligibility.ELIGIBLE:
                        ready += 1
                        break
    return ready


def _approved(recs):
    from src import approval

    n = 0
    for rec in recs:
        for contact_key, steps in (rec.get("cadence") or {}).items():
            for step_key, step in steps.items():
                if approval.is_approved(rec, contact_key, step_key, step):
                    n += 1
    return n


def _ledger_count(states):
    from src import actionledger

    rows, latest = actionledger.load(), {}
    for row in rows:
        latest[row.get("key")] = row
    return sum(1 for row in latest.values() if row.get("state") in states)


def _replies(recs):
    from src import events

    return sum(1 for r in recs for e in (r.get("events") or [])
               if events.is_reply(e))


def _positive(recs):
    return sum(1 for r in recs
               if ((r.get("suppression") or {}) or {}).get("positive"))


def measure(recs=None, cohort=None):
    """The whole funnel: count, denominator, rate and loss for every stage."""
    recs = store.load() if recs is None else recs
    got = counts(recs)
    rows = []
    for name, of, unit, eligible, truth in STAGES:
        count = got.get(name)
        denominator = got.get(of) if of else count
        # A RATE ONLY WHERE THE UNITS MATCH. A first version divided people by
        # companies and printed "people_found 3 of 2 = 150.0%", which is a
        # ratio with two denominators wearing a percent sign. Where the units
        # differ the row carries `per` instead and says what it is per.
        comparable = of is not None and UNIT_OF.get(of) == unit
        rate = per = lost = None
        usable = (count is not MISSING and isinstance(count, int)
                  and isinstance(denominator, int) and denominator > 0)
        if of is None:
            pass                   # the entry stage is its own denominator
        elif usable and comparable:
            rate = round(count / denominator, 4)
            lost = max(0, denominator - count)
        elif usable:
            per = round(count / denominator, 3)
        rows.append({"stage": name, "count": count, "of": of, "unit": unit,
                     "denominator": denominator, "rate": rate, "per": per,
                     "per_label": (None if per is None
                                   else unit + " per " + str(UNIT_OF.get(of))),
                     "lost": lost, "eligible": eligible, "truth": truth})
    return {"cohort": cohort, "records": len(recs), "stages": rows}


def attrition(recs=None):
    """One dominant reason per record, and whether it is the system working."""
    recs = store.load() if recs is None else recs
    out = collections.Counter()
    per_record = {}
    for rec in recs:
        reason = _reason(rec)
        out[reason] += 1
        per_record[rec.get("id")] = reason
    return {"counts": dict(out), "per_record": per_record,
            "good": {k: v for k, v in out.items() if k in GOOD},
            "bounded": {k: v for k, v in out.items() if k in BOUNDED},
            "provider": {k: v for k, v in out.items() if k in PROVIDER},
            "needs_human": {k: v for k, v in out.items() if k in NEEDS_HUMAN},
            "software": {k: v for k, v in out.items()
                         if k not in GOOD | BOUNDED | PROVIDER | NEEDS_HUMAN}}


def _reason(rec):
    """The FIRST thing that stopped this record, reading forward.

    Order matters and is the point: a record with no person and no email is
    reported as NO_PERSON, because buying an address for a person nobody found
    is not the next question.
    """
    verdict = _verdict(rec)
    status = verdict.get("icp_status")
    if (rec.get("suppression") or {}).get("suppressed"):
        return SUPPRESSED
    if rec.get("state") == "dropped" and status != "rejected":
        return DROPPED
    if not _has_company_data(rec):
        # Did we ask? `headcount_signal` is written by the free probe, so a 0
        # there means the vendor was asked and knows nobody at this domain.
        facts = rec.get("company_facts") or {}
        if facts.get("headcount_signal") == 0:
            return NO_PROVIDER_COVERAGE
        return NO_COMPANY_DATA
    if status == "rejected":
        return ICP_REJECT
    if _dimensions(rec) == 0:
        return MISSING_EVIDENCE
    if verdict.get("icp_confidence") == "low" and status in ("unknown", None):
        # WHY it is low decides who fixes it. Nothing gathered is a budget
        # answer; gathered and still low is a model or a parser answer.
        if not rec.get("research"):
            return RESEARCH_NOT_RUN
        return LOW_CONFIDENCE
    if status == "review":
        return ICP_REVIEW
    if status != "qualified":
        return LOW_CONFIDENCE
    contacts = _contacts(rec)
    if not contacts:
        return NO_PERSON
    if not any(c.get("email") for c in contacts):
        return NO_EMAIL
    if not any(_confirmations(c) >= 2 for c in contacts):
        return EMAIL_VERIFY_FAILED
    if not any(c.get("linkedin") for c in contacts):
        return NO_LINKEDIN
    return READY


def report(measured, attrited=None):
    """Text form. Every rate shows its own denominator, never a bare percent."""
    lines = [f"FUNNEL  cohort={measured.get('cohort') or 'all'}  "
             f"records={measured['records']}", ""]
    lines.append(f"  {'stage':<28}{'count':>8}{'of':>8}{'rate':>9}{'lost':>7}")
    for row in measured["stages"]:
        count = row["count"]
        shown = "MISSING" if count is MISSING else str(count)
        den = "" if row["of"] is None else str(row["denominator"])
        if row["rate"] is not None:
            rate = f"{row['rate']:.1%}"
        elif row["per"] is not None:
            rate = f"x{row['per']}"            # a ratio, not a percentage
        else:
            rate = ""
        lost = "" if row["lost"] is None else str(row["lost"])
        lines.append(f"  {row['stage']:<28}{shown:>8}{den:>8}{rate:>9}{lost:>7}")
    if attrited:
        lines += ["", "ATTRITION  (dominant reason per record)"]
        for reason, n in sorted(attrited["counts"].items(),
                                key=lambda kv: -kv[1]):
            tag = ("good" if reason in GOOD else
                   "bounded" if reason in BOUNDED else
                   "provider" if reason in PROVIDER else
                   "human queue" if reason in NEEDS_HUMAN else "SOFTWARE?")
            lines.append(f"  {reason:<28}{n:>6}   {tag}")
        good = sum(attrited["good"].values())
        bounded = sum(attrited.get("bounded", {}).values())
        soft = sum(attrited["software"].values())
        provider = sum(attrited.get("provider", {}).values())
        lines += ["",
                  f"  the system working:      {good}",
                  f"  bounded by budget:       {bounded}  "
                  f"(recoverable by spending)",
                  f"  no provider coverage:    {provider}  "
                  f"(recoverable only by another source)",
                  f"  waiting on a human:      "
                  f"{sum(attrited.get('needs_human', {}).values())}",
                  f"  needing explanation:     {soft}"]
    return "\n".join(lines)


def cohort_of(recs, batch_contains):
    return [r for r in recs if batch_contains in str(r.get("batch") or "")]


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m src.funnel")
    p.add_argument("--cohort", help="substring of the batch id to filter on")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)
    recs = store.load()
    if a.cohort:
        recs = cohort_of(recs, a.cohort)
    measured = measure(recs, cohort=a.cohort)
    attrited = attrition(recs)
    if a.json:
        print(json.dumps({"funnel": measured, "attrition": attrited},
                         indent=1, default=str))
    else:
        print(report(measured, attrited))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
