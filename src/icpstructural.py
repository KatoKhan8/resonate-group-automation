#!/usr/bin/env python3
"""Does this company belong in the client's ICP? Structure only.

## Why this is a separate question from `icp.score`

`icp.score` weighs twelve dimensions and returns a number. Five of those are
structural - agency fit, project delivery, employee count, geography, service
not product - and seven are PAIN: does the company's website mention
utilisation, profitability, resource planning, timesheets, operational
complexity. The weights sum to 100 and the structural five sum to 55, while
`tier_b` is 60.

So the arithmetic said: a flawless marketing agency, right size, right
country, whose website happens never to say "utilisation", CANNOT be
qualified. Measured on the 300-domain Productive cohort: 16 qualified, and
300 of 300 records carried "no evidence for time tracking need".

That is not what the client asked for. Their criteria are structural -
services business, marketing or software agency, a geography they sell to,
20+ people - and pain evidence decides WHAT WE SAY rather than WHOM WE
TARGET. This module answers the client's question. `icp.score` keeps
answering its own, and the two are stored side by side: the score becomes a
PRIORITY within the eligible pool rather than the gate into it.

## UNKNOWN is not FAIL, and that is the whole point

A criterion this system could not establish leaves the company eligible with
uncertainty. Only affirmative evidence of a violation fails it.

    FAIL     we know this company does not fit
    UNKNOWN  we could not establish it

Collapsing those two is how a cohort hand-picked as a client's market comes
back 5% qualified. "The homepage did not mention time tracking" is not
evidence that the company does not track time, and `location_why: no usable
location evidence` is not evidence of being in an excluded country.

## Everything here is configuration

There is no `if client == "productive"` in this file and there must not be.
The lists, the minimum, the tolerance and which criteria are required all
come from `config["icp"]["structural"]`. A client who sells to product
companies sets `services_business_required: false` and this module changes
its answer without changing its code.
"""
import argparse
import json

from . import clients, segments, store

# Per-criterion answers.
PASS = "pass"
PASS_WITH_TOLERANCE = "pass_with_tolerance"
FAIL = "fail"
UNKNOWN = "unknown"
NOT_REQUIRED = "not_required"

PASSING = (PASS, PASS_WITH_TOLERANCE, NOT_REQUIRED)

# Whole-company answers.
ICP_PASS = "icp_pass"
ICP_PASS_WITH_UNCERTAINTY = "icp_pass_with_uncertainty"
ICP_REVIEW = "icp_review"
ICP_FAIL = "icp_fail"

ELIGIBLE = (ICP_PASS, ICP_PASS_WITH_UNCERTAINTY)

CRITERIA = ("geography", "company_type", "services_business", "employees",
            "tracks_time")

# The two that decide whether this is even the right KIND of company. With
# both satisfied, an unknown elsewhere is uncertainty rather than ignorance -
# without them, it is ignorance and the company goes to review.
DEFINING = ("geography", "company_type")

# Business models that are affirmative evidence AGAINST a services business.
# A company selling licences or stock is not failing to prove it sells time;
# it is known to sell something else.
NOT_SERVICES = (segments.PRODUCT, segments.ECOMMERCE)
SERVICES = (segments.AGENCY, segments.CONSULTANCY)


def _float(value, fallback):
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def settings(config):
    """The client's structural criteria, with the derived floor.

    `effective_min_employees` is computed here and nowhere else, so the number
    14 never appears in the engine: it is 20 x (1 - 0.30) for this client and
    something else for the next one.
    """
    block = ((config or {}).get("icp") or {}).get("structural") or {}
    geo = block.get("geographies") or {}
    types = block.get("company_types") or {}
    people = block.get("employees") or {}
    minimum = _float(people.get("min"), 0.0)
    tolerance = _float(people.get("tolerance"), 0.0)
    return {
        "configured": bool(block),
        "include_geos": tuple(geo.get("include") or ()),
        "exclude_geos": tuple(geo.get("exclude") or ()),
        "verticals": tuple(types.get("verticals") or ()),
        "primary_types": tuple(types.get("primary") or ()),
        "services_required": bool(block.get("services_business_required")),
        "tracks_time_required": bool(block.get("tracks_time_required")),
        "min_employees": minimum,
        "employee_tolerance": tolerance,
        "revenue_contradicts_below": _float(
            people.get("revenue_contradicts_below_millions"), 0.0),
        "effective_min_employees": minimum * (1.0 - tolerance),
    }


def _norm(value):
    return str(value or "").strip().lower()


# --------------------------------------------------- resolving the evidence
#
# THE SEGMENT IS NOT THE ONLY WITNESS, AND IT WAS THE ONLY ONE BEING ASKED.
#
# `segments.classify` reads a narrower slice of the record than the record
# actually holds, so a first run of this module failed 151 of 300 companies on
# headcount and left 97 in review - while the evidence to answer both sat in
# `company_facts` untouched. Measured on the cohort:
#
#   `location_why: no usable location evidence` fired on 227 records, and 157
#   of those carry an ISO country code in `company_facts.offices`.
#
#   `employees: 11` is frequently the LOWER BOUND OF A BAND - the same record
#   carries `employee_range: "11-50 employees"`. Reading 11 as a headcount and
#   failing it against a floor of 14 rejects a company that may have fifty
#   people.
#
#   159 verticals are UNKNOWN, and 116 of those carry a marketing or software
#   services `industry` the vertical classifier never consulted.
#
# So these resolvers ask every witness on the record and say which one
# answered. None of them widens a criterion: they establish the fact the
# criterion is about, which is the difference between "we could not prove it"
# and "it is not so".

# The trailing token of an office line is an ISO country code: "Islands
# Brygge 79A , Kobenhavn S, Hovedstaden, 2300, DK".
ISO_TO_NAME = {
    "GB": "United Kingdom", "UK": "United Kingdom", "IE": "Ireland",
    "NL": "Netherlands", "DE": "Germany", "FR": "France", "SE": "Sweden",
    "NO": "Norway", "DK": "Denmark", "FI": "Finland", "BE": "Belgium",
    "AT": "Austria", "CH": "Switzerland", "ES": "Spain", "IT": "Italy",
    "PT": "Portugal", "PL": "Poland", "AU": "Australia",
    "NZ": "New Zealand", "US": "United States", "CA": "Canada",
    "IN": "India", "PK": "Pakistan", "AE": "United Arab Emirates",
    "BD": "Bangladesh", "LK": "Sri Lanka", "PH": "Philippines",
    "ID": "Indonesia", "VN": "Vietnam", "TH": "Thailand", "MY": "Malaysia",
    "CN": "China", "SG": "Singapore", "HK": "Hong Kong", "JP": "Japan",
    "KR": "South Korea", "TW": "Taiwan",
}


def resolve_country(rec, segment):
    """(name, source). The segment first, then the office lines."""
    if segment.get("country"):
        return segment["country"], "segment.country"
    code = _norm(segment.get("country_code")).upper()
    if code in ISO_TO_NAME:
        return ISO_TO_NAME[code], "segment.country_code"
    for line in (rec.get("company_facts") or {}).get("offices") or ():
        token = str(line).strip().rstrip(".").split(",")[-1].strip().upper()
        if token in ISO_TO_NAME:
            return ISO_TO_NAME[token], "company_facts.offices"
    return None, None


def _band(text):
    """(low, high) from "11-50 employees", or (None, None)."""
    digits, numbers = "", []
    for char in str(text or ""):
        if char.isdigit():
            digits += char
            continue
        if digits:
            numbers.append(int(digits))
            digits = ""
    if digits:
        numbers.append(int(digits))
    if len(numbers) >= 2:
        return numbers[0], numbers[1]
    if len(numbers) == 1:
        return numbers[0], None
    return None, None


def resolve_employees(rec, segment):
    """(lower_bound, upper_bound, source). A band stays a band.

    `employees` is a band's lower bound whenever `employee_range` is present,
    so reading it as a headcount understates the company by up to the width of
    the band. `headcount_signal` is how many people a provider actually found,
    which is a floor rather than an estimate.
    """
    facts = rec.get("company_facts") or {}
    low, high = _band(facts.get("employee_range"))
    sources, lower = [], []
    if low is not None:
        sources.append("company_facts.employee_range")
        lower.append(low)
    exact = facts.get("employees")
    if isinstance(exact, int) and exact > 0:
        lower.append(exact)
        sources.append("company_facts.employees")
    elif isinstance(segment.get("employees"), int) and segment["employees"] > 0:
        lower.append(segment["employees"])
        sources.append("segment.employees")
    signal = facts.get("headcount_signal")
    if isinstance(signal, int) and signal > 0:
        lower.append(signal)
        sources.append("company_facts.headcount_signal")
    if not lower:
        return None, high, None
    return max(lower), high, "+".join(sources)


# An industry string is weaker evidence than a classified vertical, and it is
# evidence. These are the industry labels this cohort actually carries.
AGENCY_INDUSTRY = ("advertising", "marketing", "design", "public relations",
                   "graphic design", "media production", "software",
                   "information technology", "web", "digital", "branding",
                   "creative", "communications")


def revenue_millions(rec):
    """Stored revenue as a number of millions, or None.

    `"$21.1M"`, `"$1.2B"`, `"$900K"`. Parsed rather than trusted as a float
    because the providers return a display string.
    """
    raw = str((rec.get("company_facts") or {}).get("revenue") or "").strip()
    if not raw:
        return None
    digits = "".join(c for c in raw if c.isdigit() or c == ".")
    if not digits or digits.count(".") > 1:
        return None
    try:
        value = float(digits)
    except ValueError:
        return None
    upper = raw.upper()
    if "B" in upper:
        return value * 1000.0
    if "K" in upper:
        return value / 1000.0
    return value


def resolve_company_type(rec, segment):
    """(label, source). The vertical, then the stored industry."""
    vertical = segment.get("vertical")
    if vertical and _norm(vertical) != _norm(segments.UNKNOWN):
        return vertical, "segment.vertical"
    industry = (rec.get("company_facts") or {}).get("industry")
    if industry and _norm(industry) != _norm(segments.UNKNOWN):
        return industry, "company_facts.industry"
    return None, None


def _answer(status, why, evidence=(), source=None):
    return {"status": status, "why": why, "evidence": list(evidence),
            "source": source}


def _geography(rec, segment, rules):
    include = {_norm(g) for g in rules["include_geos"]}
    exclude = {_norm(g) for g in rules["exclude_geos"]}
    if not include and not exclude:
        return _answer(NOT_REQUIRED, "this client declares no geography rule")
    country, source = resolve_country(rec, segment)
    region = segment.get("region")
    pairs = ((country, source), (region, "segment.region"))
    for label, where in pairs:
        if label and _norm(label) in exclude:
            return _answer(FAIL, "%r is on the client's exclude list" % label,
                           source=where)
    for label, where in pairs:
        if label and _norm(label) in include:
            return _answer(PASS, "%r is a market this client sells to" % label,
                           source=where)
    if not country and not _norm(region):
        return _answer(UNKNOWN, "no usable location evidence anywhere on the "
                                "record; absence of a country is not evidence "
                                "of an excluded one")
    return _answer(UNKNOWN,
                   "%r is on neither list, so it is unestablished rather than "
                   "excluded" % (country or region),
                   source=source or "segment.region")


def _company_type(rec, segment, rules):
    if not rules["verticals"]:
        return _answer(NOT_REQUIRED, "this client declares no company type rule")
    wanted = {_norm(v) for v in rules["verticals"]}
    label, source = resolve_company_type(rec, segment)
    if label is None:
        return _answer(UNKNOWN, "neither a vertical nor an industry could be "
                                "established, which is not evidence of the "
                                "wrong vertical")
    if _norm(label) in wanted:
        return _answer(PASS, "classified as %s" % label,
                       evidence=segment.get("vertical_matched") or (),
                       source=source)
    # The industry string is weaker evidence than a classified vertical, and
    # it is evidence: 116 records on this cohort carry an agency industry
    # while the vertical classifier reports "only 1 weak signal, not enough to
    # classify". A match there says this is the right KIND of company; it is
    # reported as such rather than promoted to a classification.
    if source == "company_facts.industry":
        if any(word in _norm(label) for word in AGENCY_INDUSTRY):
            return _answer(PASS, "industry %r is one this client targets, "
                                 "though the vertical classifier could not "
                                 "place it" % label, source=source)
        return _answer(UNKNOWN, "industry %r is not recognisably one of this "
                                "client's types, and no vertical was "
                                "classified" % label, source=source)
    return _answer(FAIL, "classified as %s, which is not one of the company "
                         "types this client targets" % label,
                   evidence=segment.get("vertical_matched") or (),
                   source=source)


def _services_business(segment, rules):
    if not rules["services_required"]:
        return _answer(NOT_REQUIRED, "this client does not require a services "
                                     "business")
    model = _norm(segment.get("business_model"))
    if model in {_norm(m) for m in SERVICES}:
        return _answer(PASS, f"business model is {segment.get('business_model')}",
                       source="segment.business_model")
    if model in {_norm(m) for m in NOT_SERVICES}:
        return _answer(FAIL, f"business model is "
                             f"{segment.get('business_model')}, which sells "
                             f"something other than time",
                       evidence=segment.get("non_icp_signals") or (),
                       source="segment.business_model")
    return _answer(UNKNOWN, f"business model is "
                            f"{segment.get('business_model') or 'unestablished'}",
                   source="segment.business_model")


def _employees(rec, segment, rules):
    """A BAND IS NOT A HEADCOUNT, and reading it as one rejected 151 companies.

    `employees: 11` beside `employee_range: "11-50 employees"` means somewhere
    between eleven and fifty, not eleven. Failing that against a floor of
    fourteen rejects a company that may have fifty people, on evidence that
    says no such thing. The records know it too: `recovered_from.confidence`
    says in as many words that `employees` is the lower bound of a band and
    not a measured headcount, and the scorer read it as one anyway.

    So a band that STRADDLES the floor is unknown - which side it falls is
    unestablished - and only a band lying wholly below the floor fails. An
    exact count with nothing to contradict it still fails, because that is a
    measurement of a company too small for this client.
    """
    if not rules["min_employees"]:
        return _answer(NOT_REQUIRED, "this client declares no size rule")
    minimum, floor = rules["min_employees"], rules["effective_min_employees"]
    lower, upper, source = resolve_employees(rec, segment)
    if lower is None and upper is None:
        return _answer(UNKNOWN, "headcount could not be established; an "
                                "unknown headcount is not a small company")
    if lower is not None and lower >= minimum:
        return _answer(PASS, "%d people, at or above the client's minimum of "
                             "%g" % (lower, minimum), source=source)
    if lower is not None and lower >= floor:
        return _answer(PASS_WITH_TOLERANCE,
                       "%d people. Below the client's stated minimum of %g, "
                       "but within the %.0f%% tolerance on an estimated "
                       "headcount, whose floor is %g"
                       % (lower, minimum, rules["employee_tolerance"] * 100,
                          floor), source=source)
    if upper is not None and upper >= floor:
        return _answer(UNKNOWN,
                       "the evidence is a band of %s-%s people, which "
                       "straddles the tolerated floor of %g. Which side it "
                       "falls is unestablished, and a band is not a headcount"
                       % (lower, upper, floor), source=source)
    # Before rejecting on a number, ask whether the record contradicts it.
    ceiling = rules.get("revenue_contradicts_below") or 0.0
    revenue = revenue_millions(rec) if ceiling else None
    if revenue is not None and revenue >= ceiling:
        return _answer(UNKNOWN,
                       "the stored headcount is %s, which revenue of $%gM "
                       "contradicts: the two cannot both be right, so the "
                       "size is unestablished rather than small"
                       % (lower, revenue),
                       evidence=[(rec.get("company_facts") or {}).get("revenue")],
                       source="company_facts.revenue")
    return _answer(FAIL, "%s people, below the tolerated floor of %g (%g less "
                         "a %.0f%% tolerance)"
                   % (lower, floor, minimum,
                      rules["employee_tolerance"] * 100), source=source)


def _tracks_time(rec, segment, rules):
    """The client's must-have, and the criterion most at risk of a false FAIL.

    A homepage that does not mention timesheets is not a company that does not
    keep them. So this fails ONLY on affirmative evidence that the company
    sells something other than time - a product or ecommerce business model -
    and is otherwise UNKNOWN unless the evidence positively says so.

    Establishing it properly is a research question, not a scoring one: job
    postings, billing language, a PSA or time-tracking tool in the stack. Until
    research produces that, UNKNOWN is the honest answer and the company stays
    eligible with uncertainty.
    """
    if not rules["tracks_time_required"]:
        return _answer(NOT_REQUIRED, "this client does not require it")
    model = _norm(segment.get("business_model"))
    if model in {_norm(m) for m in NOT_SERVICES}:
        return _answer(FAIL, f"a {segment.get('business_model')} business does "
                             f"not bill time",
                       source="segment.business_model")
    found = tracks_time_evidence(rec)
    if found:
        return _answer(PASS, "billable or time-tracking language found in the "
                             "evidence gathered for this company",
                       evidence=found, source="company_facts")
    return _answer(UNKNOWN, "no evidence either way. Absence of the phrase on "
                            "a website is not evidence that the company does "
                            "not track time",
                   source="company_facts")


# Phrases that are affirmative evidence a company bills or tracks time. Kept
# narrow on purpose: "capacity" alone is on every consultancy's homepage and
# proves nothing.
TIME_EVIDENCE = ("billable", "timesheet", "time tracking", "time-tracking",
                 "hourly rate", "per hour", "utilisation", "utilization",
                 "chargeable", "logged hours", "retainer", "day rate",
                 "time and materials")


def tracks_time_evidence(rec):
    """Phrases already stored on the record that bear on billing time."""
    from . import icp

    text = _norm(icp._structured_text(rec))
    return [phrase for phrase in TIME_EVIDENCE if phrase in text]


def verdict_of(criteria):
    """One answer from five, and the rules are the client's own.

    FAIL beats everything: affirmative evidence against a client criterion is
    a rejection however good the rest looks. Otherwise every criterion
    satisfied is a pass, and an unknown is uncertainty when the two DEFINING
    criteria are satisfied and ignorance when they are not.
    """
    statuses = {name: answer["status"] for name, answer in criteria.items()}
    if FAIL in statuses.values():
        return ICP_FAIL
    if all(status in PASSING for status in statuses.values()):
        return ICP_PASS
    if all(statuses.get(name) in PASSING for name in DEFINING):
        return ICP_PASS_WITH_UNCERTAINTY
    return ICP_REVIEW


def structural(rec, config=None, segment=None):
    """The client's structural ICP answer for one company. Spends nothing."""
    config = config if config is not None else clients.load(rec.get("client"))
    rules = settings(config)
    segment = segment if segment is not None else segments.classify(rec, config)
    criteria = {
        "geography": _geography(rec, segment, rules),
        "company_type": _company_type(rec, segment, rules),
        "services_business": _services_business(segment, rules),
        "employees": _employees(rec, segment, rules),
        "tracks_time": _tracks_time(rec, segment, rules),
    }
    verdict = verdict_of(criteria)
    failed = [name for name, answer in criteria.items()
              if answer["status"] == FAIL]
    return {
        "verdict": verdict,
        "eligible": verdict in ELIGIBLE,
        "criteria": criteria,
        # ONE primary reason, so a rejection audit reconciles. The order is
        # the client's own sequence, so the first thing that disqualified the
        # company is the thing reported.
        "primary_reason": next((name for name in CRITERIA if name in failed),
                               None),
        "unknown_criteria": sorted(name for name, answer in criteria.items()
                                   if answer["status"] == UNKNOWN),
        "effective_min_employees": rules["effective_min_employees"],
        "configured": rules["configured"],
        "at": store.now(),
    }


def summarise(results):
    """Counts by verdict and by primary rejection reason. They reconcile."""
    counts, reasons = {}, {}
    for result in results:
        counts[result["verdict"]] = counts.get(result["verdict"], 0) + 1
        if result["verdict"] == ICP_FAIL:
            key = result.get("primary_reason") or "unstated"
            reasons[key] = reasons.get(key, 0) + 1
    return {"verdicts": counts, "fail_reasons": reasons,
            "total": len(results),
            "eligible": sum(counts.get(v, 0) for v in ELIGIBLE)}


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m src.icpstructural",
                                description=__doc__)
    p.add_argument("--client", default="productive")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)
    config = clients.load(a.client)
    recs = [r for r in store.load() if r.get("client") == a.client]
    results = [structural(rec, config) for rec in recs]
    out = summarise(results)
    if a.json:
        print(json.dumps(out, indent=1))
        return 0
    print(f"STRUCTURAL ICP  client={a.client}  records={out['total']}")
    for verdict in (ICP_PASS, ICP_PASS_WITH_UNCERTAINTY, ICP_REVIEW, ICP_FAIL):
        n = out["verdicts"].get(verdict, 0)
        print(f"  {verdict:28s} {n:5d}  {100 * n / out['total']:5.1f}%"
              if out["total"] else f"  {verdict:28s} {n:5d}")
    print(f"  {'ELIGIBLE':28s} {out['eligible']:5d}")
    if out["fail_reasons"]:
        print("\n  primary rejection reason")
        for name, n in sorted(out["fail_reasons"].items(),
                              key=lambda kv: -kv[1]):
            print(f"    {name:26s} {n:5d}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
