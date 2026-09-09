#!/usr/bin/env python3
"""The service contract a segment explorer UI will consume.

Not a web app. This is the query layer underneath one: the filters a person
would reach for, the drill path from a batch down to a company, and the facet
counts that make a filter usable before you apply it.

Two decisions worth stating. Filtering is **exact-match on stated vocabulary**
rather than free text: `vertical=Software Development Agency` either matches or
does not, so a saved view means the same thing next month. And every list
response carries the total alongside the page, because a UI that shows "20
results" when there are 4,000 teaches people to trust a number that is wrong.

Nothing here spends anything. Every function reads the qualification already
stored on the records.

  python -m src.explorer --facets --client productive
  python -m src.explorer --filter vertical="Consulting" --filter region=UK
"""
import argparse
import json

from . import campaignseg, dmplan, icp, qualify, segments, store

# The filters the UI may offer. Each names where the value comes from, so a
# new filter is a deliberate addition rather than a string somebody guessed.
FILTERS = {
    "icp_status": ("verdict", "icp_status", icp.STATUSES),
    "icp_tier": ("verdict", "icp_tier", icp.TIERS),
    "icp_confidence": ("verdict", "icp_confidence", icp.CONFIDENCE),
    "vertical": ("segment", "vertical", segments.VERTICALS),
    "subvertical": ("segment", "subvertical", segments.VERTICALS),
    "industry": ("segment", "industry", None),
    "business_model": ("segment", "business_model", segments.BUSINESS_MODELS),
    "employee_band": ("segment", "employee_band", segments.BAND_NAMES),
    "country": ("segment", "country", None),
    "region": ("segment", "region", None),
    "timezone": ("segment", "timezone", None),
    "timezone_confidence": ("segment", "timezone_confidence", None),
    "company_maturity": ("segment", "company_maturity", segments.MATURITIES),
    "delivery_model": ("segment", "delivery_model", segments.DELIVERY_MODELS),
    "persona": ("persona_plan", "persona_priority", None),
    "strategy": ("persona_plan", "strategy", None),
    "segment_key": (None, "segment_key", None),
    "state": (None, "_state", tuple(dmplan.STATES)),
}

# Filters that are not equality: a range, a flag, a membership test.
RANGE_FILTERS = ("score_min", "score_max")
FLAG_FILTERS = ("manual_review", "requires_enrichment", "schedulable")

# The facets worth counting for a UI to render as filter chips.
FACETS = ("icp_status", "icp_tier", "icp_confidence", "vertical", "region",
          "country", "employee_band", "business_model", "timezone",
          "delivery_model", "strategy", "segment_key")


def _value(entry, source, field):
    if source is None:
        if field == "_state":
            return qualify.state_of(entry["record"])
        return entry.get(field)
    return (entry.get(source) or {}).get(field)


def _matches(entry, name, wanted):
    """One filter against one company. Lists match on membership."""
    if name in RANGE_FILTERS:
        score = (entry.get("verdict") or {}).get("icp_score")
        if score is None:
            return False
        return (score >= float(wanted) if name == "score_min"
                else score <= float(wanted))

    if name == "manual_review":
        status = (entry.get("verdict") or {}).get("icp_status")
        return bool(wanted) == (status in (icp.REVIEW, icp.UNKNOWN))
    if name == "requires_enrichment":
        required = (entry.get("cost_plan") or {}).get("enrichment_required")
        return bool(wanted) == bool(required)
    if name == "schedulable":
        return bool(wanted) == bool((entry.get("segment") or {}).get("timezone"))

    if name not in FILTERS:
        raise KeyError(f"unknown filter: {name}")
    source, field, _ = FILTERS[name]
    value = _value(entry, source, field)
    if isinstance(value, list):
        return str(wanted) in [str(v) for v in value]
    return str(value) == str(wanted)


def valid_filters():
    return tuple(sorted(set(FILTERS) | set(RANGE_FILTERS) | set(FLAG_FILTERS)))


def apply_filters(companies, filters):
    """Every filter must match. An unknown filter name raises rather than
    silently returning everything, which is the failure that makes a UI lie."""
    for name in filters:
        if name not in valid_filters():
            raise KeyError(f"unknown filter: {name}")
    return [entry for entry in companies
            if all(_matches(entry, name, value)
                   for name, value in filters.items())]


def facets(companies):
    """Counts per filter value, so a UI can show what is worth clicking."""
    out = {}
    for name in FACETS:
        counts = {}
        if name == "segment_key":
            for entry in companies:
                key = entry.get("segment_key")
                if key:
                    counts[key] = counts.get(key, 0) + 1
        else:
            source, field, _ = FILTERS[name]
            for entry in companies:
                value = _value(entry, source, field)
                if isinstance(value, list):
                    value = value[0] if value else None
                counts[str(value)] = counts.get(str(value), 0) + 1
        out[name] = dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))
    return out


def _row(entry):
    """One company as a list row: enough to decide, not enough to be slow."""
    verdict = entry.get("verdict") or {}
    segment = entry.get("segment") or {}
    plan = entry.get("persona_plan") or {}
    cost = entry.get("cost_plan") or {}
    return {
        "record_id": entry["record"].get("id"),
        "company": entry["record"].get("company"),
        "domain": entry["record"].get("domain"),
        "state": qualify.state_of(entry["record"]),
        "icp_status": verdict.get("icp_status"),
        "icp_tier": verdict.get("icp_tier"),
        "icp_score": verdict.get("icp_score"),
        "icp_confidence": verdict.get("icp_confidence"),
        "vertical": segment.get("vertical"),
        "subvertical": segment.get("subvertical"),
        "employee_band": segment.get("employee_band"),
        "country": segment.get("country"),
        "region": segment.get("region"),
        "timezone": segment.get("timezone"),
        "schedulable": bool(segment.get("timezone")),
        "strategy": plan.get("strategy"),
        "personas": plan.get("persona_priority"),
        "max_contacts": plan.get("max_contacts_to_enrich"),
        "expected_credits": cost.get("expected_credits"),
        "segment_key": entry.get("segment_key"),
    }


def list_companies(companies, filters=None, sort="priority", limit=50,
                   offset=0):
    """A page of companies, with the honest total beside it."""
    filtered = apply_filters(companies, filters or {})
    if sort == "priority":
        filtered = qualify.prioritise(filtered)
    elif sort == "score":
        filtered = sorted(filtered,
                          key=lambda e: -float((e.get("verdict") or {})
                                               .get("icp_score") or 0))
    elif sort == "company":
        filtered = sorted(filtered,
                          key=lambda e: (e["record"].get("company") or "").lower())

    page = filtered[offset:offset + limit] if limit else filtered
    return {
        "total": len(filtered),
        "offset": offset,
        "limit": limit,
        "returned": len(page),
        "filters": dict(filters or {}),
        "sort": sort,
        "rows": [_row(entry) for entry in page],
    }


# ---------------------------------------------------------- the drill path
#
#   batch -> segment -> company -> persona plan -> (later) contacts
#
# Each level answers one question and links to the next. Contacts are named as
# a future level rather than omitted, so the shape of the UI does not have to
# change when they exist.

def batch_view(result, config=None):
    """The top of the drill: what this batch contains."""
    companies = result["companies"]
    summary = qualify.summarise(result, config)
    return {
        "level": "batch",
        "client": result.get("client"),
        "batch": result.get("batch"),
        "companies": len(companies),
        "summary": summary,
        "facets": facets(companies),
        "segments": [
            {"segment_key": key, "companies": info["companies"],
             "rung": info["rung"], "reason": info["reason"],
             "drill": {"level": "segment", "segment_key": key}}
            for key, info in summary["segments"]["sizes"].items()],
        "unsegmented": summary["segments"]["unsegmented_companies"],
    }


def segment_view(companies, segment_key, limit=50, offset=0):
    """One campaign segment: who is in it, and why they are together."""
    members = apply_filters(companies, {"segment_key": segment_key})
    if not members:
        return {"level": "segment", "segment_key": segment_key,
                "companies": 0, "rows": [],
                "why": "no company is in this segment"}
    listed = list_companies(members, limit=limit, offset=offset)
    return {
        "level": "segment",
        "segment_key": segment_key,
        "companies": len(members),
        "rung": members[0].get("segment_rung"),
        "why_together": members[0].get("segment_reason"),
        "shared": (members[0].get("segment_parts") or {}),
        "facets": facets(members),
        **listed,
    }


def company_view(companies, record_id, config=None):
    """One company: the full pre-enrichment dossier."""
    entry = next((e for e in companies
                  if e["record"].get("id") == record_id), None)
    if entry is None:
        return None
    return {
        "level": "company",
        **qualify.dossier(entry, config),
        "drill": {"level": "persona_plan", "record_id": record_id},
    }


def persona_view(companies, record_id):
    """The persona plan, and what it would cost to act on."""
    entry = next((e for e in companies
                  if e["record"].get("id") == record_id), None)
    if entry is None:
        return None
    plan = entry.get("persona_plan") or {}
    cost = entry.get("cost_plan") or {}
    return {
        "level": "persona_plan",
        "record_id": record_id,
        "strategy": plan.get("strategy"),
        "strategy_reason": plan.get("strategy_reason"),
        "personas": plan.get("personas"),
        "priority": plan.get("persona_priority"),
        "target_titles": plan.get("target_titles"),
        "max_contacts": plan.get("max_contacts_to_enrich"),
        "reason": plan.get("cap_reason"),
        "cost": {"expected_credits": cost.get("expected_credits"),
                 "maximum_credits": cost.get("maximum_credits"),
                 "calls": cost.get("calls")},
        # Named rather than omitted: the level exists, it is just empty until
        # somebody approves the spend.
        "contacts": [],
        "contacts_available": False,
        "why_no_contacts": (plan.get("cap_reason")
                            or "no person enrichment has been approved or run"),
        "drill": {"level": "contacts", "record_id": record_id,
                  "available": False},
    }


def contract():
    """The service contract, as data a UI developer can read."""
    return {
        "filters": {name: {"values": list(values) if values else "open",
                           "source": source or "company"}
                    for name, (source, _, values) in FILTERS.items()},
        "range_filters": list(RANGE_FILTERS),
        "flag_filters": list(FLAG_FILTERS),
        "facets": list(FACETS),
        "sorts": ["priority", "score", "company"],
        "drill": ["batch", "segment", "company", "persona_plan", "contacts"],
        "notes": [
            "every list response carries `total` beside the page",
            "an unknown filter name raises rather than returning everything",
            "no endpoint here spends a credit or calls a provider",
            "contacts are a declared level that is empty until enrichment is "
            "approved and run",
        ],
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--client")
    p.add_argument("--batch")
    p.add_argument("--contract", action="store_true")
    p.add_argument("--facets", action="store_true")
    p.add_argument("--segment")
    p.add_argument("--company")
    p.add_argument("--filter", action="append", default=[],
                   help="name=value, repeatable")
    p.add_argument("--limit", type=int, default=20)
    a = p.parse_args(argv)

    if a.contract:
        print(json.dumps(contract(), indent=2))
        return 0

    from . import clients
    config = {}
    try:
        config = clients.load(a.client)
    except Exception:
        config = {}
    result = qualify.run(store.load(), client=a.client, batch=a.batch,
                         config=config, store_result=False)
    companies = result["companies"]

    if a.segment:
        print(json.dumps(segment_view(companies, a.segment, a.limit), indent=2))
        return 0
    if a.company:
        view = company_view(companies, a.company, config)
        if view is None:
            print(f"REFUSED: no such company in this batch: {a.company}")
            return 2
        print(json.dumps(view, indent=2, ensure_ascii=False))
        return 0
    if a.facets:
        print(json.dumps(facets(companies), indent=2))
        return 0

    filters = {}
    for pair in a.filter:
        name, _, value = pair.partition("=")
        filters[name.strip()] = value.strip()
    try:
        print(json.dumps(list_companies(companies, filters, limit=a.limit),
                         indent=2))
    except KeyError as e:
        print(f"REFUSED: {e}")
        print(f"valid filters: {', '.join(valid_filters())}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
