#!/usr/bin/env python3
"""TASK-037: headcount data quality and coverage measurement.

Measures across the 300-record Productive estate (generated deterministically
by src/companies.py):

  1. Distribution by source, confidence, and range/value agreement
  2. Contradiction frequency and magnitude
  3. How many of the unknowns could be resolved from stored evidence
  4. Coverage as a number over the real queue

ZERO network. ZERO credentials. Pure analysis of stored data structures.
"""
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from src import clients, companies, headcount, icpstructural, segments, store

ESTATE_SIZE = 300
CLIENT_NAME = "productive"


def build_estate(synthetic=False):
    """The REAL estate from work/queue.jsonl, or a synthetic one on request.

    CORRECTED 2026-09-15. This used to return `companies.dataset(...)`
    unconditionally - a FABRICATED estate - while its docstring called it
    "the 300-record Productive estate, as the pipeline would produce it" and
    the result block reported its numbers as coverage "across the 300-record
    Productive estate".

    The synthetic estate is also 300 records, which is exactly the size of
    the real queue, so every number looked plausible and none of them
    described production. It reported company_facts.employee_range at 0/300;
    production has it on 25 of 300, because the generator does not emit that
    field.

    A measurement of invented data is not a measurement. Real is the default
    now, and anything synthetic has to ask.
    """
    if synthetic:
        config = clients.load(CLIENT_NAME)
        return companies.dataset(ESTATE_SIZE, config=config, client=CLIENT_NAME)
    return [r for r in store.load()
            if not CLIENT_NAME or r.get("client") in (None, CLIENT_NAME)]


def measure_distributions(records, config):
    """Distribution by source, confidence, range/value agreement."""
    rules = icpstructural.settings(config)
    floor = rules["effective_min_employees"]

    by_state = {}
    by_confidence = {}
    by_source = {}
    range_value_disagree = 0
    has_any_witness = 0
    has_band = 0
    has_value = 0
    has_neither = 0
    total_with_employees_field = 0
    total_with_employee_range = 0
    total_with_headcount_signal = 0
    total_with_headcount_block = 0

    for rec in records:
        facts = rec.get("company_facts") or {}
        resolved = headcount.resolve(rec, config)
        state = resolved["state"]
        by_state[state] = by_state.get(state, 0) + 1

        conf = resolved.get("confidence")
        if conf:
            by_confidence[conf] = by_confidence.get(conf, 0) + 1

        src = resolved.get("source")
        if src:
            by_source[src] = by_source.get(src, 0) + 1

        witnesses = headcount.witnesses(rec)
        if witnesses:
            has_any_witness += 1

        for w in witnesses:
            r = w.get("range")
            v = w.get("value")
            if r and v and r[0] is not None:
                if v < r[0] or (r[1] is not None and v > r[1]):
                    range_value_disagree += 1

        if isinstance(facts.get("employees"), int) and facts["employees"] > 0:
            total_with_employees_field += 1
        if facts.get("employee_range"):
            total_with_employee_range += 1
        if isinstance(facts.get("headcount_signal"), int) and facts["headcount_signal"] > 0:
            total_with_headcount_signal += 1
        block = facts.get("headcount") or {}
        if block:
            total_with_headcount_block += 1
        if block.get("value") or block.get("range"):
            has_value += 1
        elif block.get("observations"):
            has_band += 1
        else:
            has_neither += 1

    return {
        "total_records": len(records),
        "floor": floor,
        "by_state": by_state,
        "by_confidence": by_confidence,
        "by_source": by_source,
        "range_value_disagree": range_value_disagree,
        "has_any_witness": has_any_witness,
        "raw_field_coverage": {
            "company_facts.employees (bare number)": total_with_employees_field,
            "company_facts.employee_range (band)": total_with_employee_range,
            "company_facts.headcount_signal (profile count)": total_with_headcount_signal,
            "company_facts.headcount (resolved block)": total_with_headcount_block,
        },
        "resolved_block": {
            "has_value_or_range": has_value,
            "has_observations_only": has_band,
            "empty": has_neither,
        },
    }


def measure_contradictions(records, config):
    """How often two sources contradict, and by how much."""
    conflicts = []
    conflict_magnitudes = []

    for rec in records:
        resolved = headcount.resolve(rec, config)
        if resolved["state"] == headcount.CONFLICT:
            contradictions = resolved.get("contradictions", [])
            values = [c.get("value") for c in contradictions if c.get("value")]
            if len(values) == 2:
                mag = abs(values[0] - values[1])
                ratio = max(values) / max(1, min(values))
                conflict_magnitudes.append({
                    "record_id": rec.get("id"),
                    "company": rec.get("company"),
                    "values": values,
                    "magnitude": mag,
                    "ratio": round(ratio, 1),
                    "sides": [c.get("side") for c in contradictions],
                })
            conflicts.append(resolved)

    return {
        "total_conflicts": len(conflicts),
        "conflict_details": conflict_magnitudes,
        "magnitude_distribution": _magnitude_buckets(conflict_magnitudes),
    }


def _magnitude_buckets(details):
    buckets = {"trivial (0-5)": 0, "small (6-15)": 0, "moderate (16-50)": 0,
               "large (51-200)": 0, "extreme (200+)": 0}
    for d in details:
        m = d["magnitude"]
        if m <= 5:
            buckets["trivial (0-5)"] += 1
        elif m <= 15:
            buckets["small (6-15)"] += 1
        elif m <= 50:
            buckets["moderate (16-50)"] += 1
        elif m <= 200:
            buckets["large (51-200)"] += 1
        else:
            buckets["extreme (200+)"] += 1
    return buckets


def measure_icp_impact(records, config):
    """How headcount state maps to ICP employee criterion verdicts."""
    verdicts = {}
    for rec in records:
        segment = segments.classify(rec, config)
        result = icpstructural.structural(rec, config, segment=segment)
        emp = result["criteria"]["employees"]["status"]
        verdicts[emp] = verdicts.get(emp, 0) + 1
    return verdicts


def measure_coverage_for_personalisation(records, config):
    """What coverage headcount has as a personalisation variable.

    A variable needs one of: reliable data coverage, a safe fallback, or a
    rule excluding that record. This measures which records have what.
    """
    rules = icpstructural.settings(config)
    floor = rules["effective_min_employees"]
    minimum = rules["min_employees"]

    reliable = 0
    band_only = 0
    conflict_no_value = 0
    unestablished = 0
    resolvable_from_stored = 0

    for rec in records:
        facts = rec.get("company_facts") or {}
        resolved = headcount.resolve(rec, config)
        state = resolved["state"]

        if state == headcount.AGREED and resolved.get("value"):
            reliable += 1
        elif state == headcount.SINGLE_SOURCE and resolved.get("value"):
            reliable += 1
        elif state == headcount.CONFLICT:
            conflict_no_value += 1
        elif state == headcount.UNESTABLISHED:
            unestablished += 1
        else:
            band_only += 1

        # Can stored evidence resolve an unknown?
        if state in (headcount.UNESTABLISHED, headcount.CONFLICT):
            if _can_resolve_from_stored(rec, floor):
                resolvable_from_stored += 1

    return {
        "reliable_value (agreed or single-source with value)": reliable,
        "band_only (range but no resolved value)": band_only,
        "conflict_no_value (two sources disagree)": conflict_no_value,
        "unestablished (no witness at all)": unestablished,
        "resolvable_from_stored_evidence": resolvable_from_stored,
        "total": len(records),
        "coverage_ratio": f"{reliable}/{len(records)}",
    }


def _can_resolve_from_stored(rec, floor):
    """Can evidence already on the record resolve this unknown?

    Checks whether a band upper bound, a headcount_signal, or revenue
    contradiction already carries enough information to place the company
    relative to the floor - without any new provider call.
    """
    facts = rec.get("company_facts") or {}
    resolved = headcount.resolve(rec, floor=floor) if False else headcount.resolve(rec)

    # A band whose upper bound is at or above the floor: the company MAY be
    # large enough, which is already more than "unknown" - it is "unknown
    # but possibly qualified". The band IS the evidence.
    low, high = icpstructural._band(facts.get("employee_range"))
    if high is not None and high >= floor:
        return True

    # A headcount_signal above the floor: a profile count is a floor, so if
    # it is above the floor, the company IS above it.
    signal = facts.get("headcount_signal")
    if isinstance(signal, int) and signal >= floor:
        return True

    return False


def measure_revenue_contradictions(records, config):
    """How many records have headcount contradicted by revenue."""
    rules = icpstructural.settings(config)
    ceiling = rules.get("revenue_contradicts_below") or 0.0
    if not ceiling:
        return {"total": 0, "note": "no revenue contradiction threshold configured"}

    contradicted = 0
    details = []
    for rec in records:
        facts = rec.get("company_facts") or {}
        emp = facts.get("employees")
        rev = icpstructural.revenue_millions(rec)
        if (isinstance(emp, int) and emp > 0 and emp < rules["effective_min_employees"]
                and rev is not None and rev >= ceiling):
            contradicted += 1
            details.append({
                "record_id": rec.get("id"),
                "company": rec.get("company"),
                "employees": emp,
                "revenue_millions": rev,
            })
    return {"total": contradicted, "threshold_millions": ceiling,
            "details": details[:10]}


def main():
    config = clients.load(CLIENT_NAME)
    records = build_estate()

    print("=" * 72)
    print("TASK-037: HEADCOUNT DATA QUALITY AND COVERAGE MEASUREMENT")
    print("=" * 72)
    print(f"\nEstate: {len(records)} records, client={CLIENT_NAME}")
    rules = icpstructural.settings(config)
    print(f"Floor: {rules['effective_min_employees']} "
          f"(min={rules['min_employees']}, tolerance={rules['employee_tolerance']})")
    print(f"Revenue contradiction threshold: "
          f"${rules.get('revenue_contradicts_below', 0)}M")

    print("\n" + "-" * 72)
    print("1. RAW FIELD COVERAGE")
    print("-" * 72)
    dist = measure_distributions(records, config)
    for k, v in dist["raw_field_coverage"].items():
        print(f"  {k}: {v}/{len(records)}")

    print("\n" + "-" * 72)
    print("2. RESOLVED HEADCOUNT STATE DISTRIBUTION")
    print("-" * 72)
    for state, count in sorted(dist["by_state"].items()):
        print(f"  {state}: {count}/{len(records)} "
              f"({100*count/len(records):.1f}%)")

    print(f"\n  Witnesses present: {dist['has_any_witness']}/{len(records)}")
    print(f"  Range/value disagree: {dist['range_value_disagree']}")

    print("\n" + "-" * 72)
    print("3. CONFIDENCE DISTRIBUTION")
    print("-" * 72)
    for conf, count in sorted(dist["by_confidence"].items()):
        print(f"  {conf}: {count}/{len(records)}")

    print("\n" + "-" * 72)
    print("4. SOURCE DISTRIBUTION")
    print("-" * 72)
    for src, count in sorted(dist["by_source"].items()):
        print(f"  {src}: {count}/{len(records)}")

    print("\n" + "-" * 72)
    print("5. CONTRADICTIONS BETWEEN SOURCES")
    print("-" * 72)
    contra = measure_contradictions(records, config)
    print(f"  Total conflicts: {contra['total_conflicts']}/{len(records)}")
    print(f"  Magnitude distribution:")
    for bucket, count in contra["magnitude_distribution"].items():
        print(f"    {bucket}: {count}")
    if contra["conflict_details"]:
        print(f"\n  First 5 conflicts:")
        for d in contra["conflict_details"][:5]:
            print(f"    {d['record_id']} ({d['company']}): "
                  f"{d['values']} magnitude={d['magnitude']} "
                  f"ratio={d['ratio']}x sides={d['sides']}")

    print("\n" + "-" * 72)
    print("6. ICP EMPLOYEE CRITERION VERDICTS")
    print("-" * 72)
    icp_v = measure_icp_impact(records, config)
    for status, count in sorted(icp_v.items()):
        print(f"  {status}: {count}/{len(records)} "
              f"({100*count/len(records):.1f}%)")

    print("\n" + "-" * 72)
    print("7. COVERAGE FOR PERSONALISATION VARIABLE")
    print("-" * 72)
    cov = measure_coverage_for_personalisation(records, config)
    for k, v in cov.items():
        if k != "total" and k != "coverage_ratio":
            print(f"  {k}: {v}")
    print(f"\n  COVERAGE: {cov['coverage_ratio']}")
    print(f"  Resolvable from stored evidence (no new provider call): "
          f"{cov['resolvable_from_stored_evidence']}")

    print("\n" + "-" * 72)
    print("8. REVENUE CONTRADICTIONS")
    print("-" * 72)
    rev = measure_revenue_contradictions(records, config)
    print(f"  Total: {rev['total']}")
    if rev.get("details"):
        for d in rev["details"][:5]:
            print(f"    {d['record_id']} ({d['company']}): "
                  f"{d['employees']} people, ${d['revenue_millions']}M revenue")

    print("\n" + "=" * 72)
    print("SUMMARY")
    print("=" * 72)
    unestablished = dist["by_state"].get(headcount.UNESTABLISHED, 0)
    conflicts = dist["by_state"].get(headcount.CONFLICT, 0)
    agreed = dist["by_state"].get(headcount.AGREED, 0)
    single = dist["by_state"].get(headcount.SINGLE_SOURCE, 0)
    print(f"  AGREED:         {agreed:>4}  ({100*agreed/len(records):.1f}%)")
    print(f"  SINGLE_SOURCE:  {single:>4}  ({100*single/len(records):.1f}%)")
    print(f"  CONFLICT:       {conflicts:>4}  ({100*conflicts/len(records):.1f}%)")
    print(f"  UNESTABLISHED:  {unestablished:>4}  ({100*unestablished/len(records):.1f}%)")
    print(f"\n  Personalisation coverage: {cov['coverage_ratio']}")
    print(f"  Records needing fallback or exclusion: "
          f"{unestablished + conflicts}/{len(records)}")
    print(f"  Resolvable without new provider call: "
          f"{cov['resolvable_from_stored_evidence']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
