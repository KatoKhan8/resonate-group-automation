#!/usr/bin/env python3
"""TASK-154: Which accounts actually need a crawl, and what would it cost?

Reads the snapshot (read-only copy of production queue) and answers four
questions:
1. How many records have NO evidence at all, and would research.why() fire?
2. How many have evidence that is now STALE under the TTL, by field?
3. How many have evidence that is present but UNUSABLE (boilerplate)?
4. Of the records that need research, how many are ICP-qualified?

Produces a prioritised worklist.
"""
import json
import os
import sys
import datetime

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from src import research, evidence as ev, segments, icp

SNAPSHOT = os.path.join(ROOT, "work", "queue.snapshot.jsonl")
STAMP = os.path.join(ROOT, "work", "queue.snapshot.STAMP")
TODAY = datetime.datetime(2026, 9, 15, tzinfo=datetime.timezone.utc)


def load_snapshot():
    records = []
    with open(SNAPSHOT, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def read_stamp():
    with open(STAMP, encoding="utf-8") as f:
        return f.read().strip()


def get_icp_verdict(rec):
    """Return (verdict, icp_status) from the record."""
    qual = rec.get("qualification") or {}
    verdict_obj = qual.get("verdict") or {}
    return verdict_obj.get("verdict"), verdict_obj.get("icp_status")


def classify_evidence_quality(rec):
    """For a record with evidence, classify each row.
    Returns (total_rows, unusable_count, usable_count, stale_count, fields_stale).
    """
    rows = rec.get("research") or []
    total = len(rows)
    unusable = 0
    usable = 0
    stale_count = 0
    fields_stale = {}

    for row in rows:
        fact = row.get("fact", "")
        bp = ev.boilerplate(fact)
        if bp:
            unusable += 1
        else:
            usable += 1

        age = research.age_of(row, TODAY)
        if age is not None and age > research.ttl_for(row.get("field")):
            stale_count += 1
            field = row.get("field", "unknown")
            fields_stale[field] = fields_stale.get(field, 0) + 1

    return total, unusable, usable, stale_count, fields_stale


def main():
    records = load_snapshot()
    stamp = read_stamp()
    print(f"Snapshot stamp: {stamp}")
    print(f"Total records: {len(records)}")
    print()

    # ---- Q1: Records with NO evidence at all, and why() reasons ----
    no_evidence = []
    why_reasons = {}
    for rec in records:
        existing = research.existing_evidence(rec)
        if not existing:
            no_evidence.append(rec)
            reason = research.why(rec, today=TODAY)
            if reason:
                why_reasons[reason] = why_reasons.get(reason, 0) + 1

    print("=" * 70)
    print("Q1: RECORDS WITH NO EVIDENCE AT ALL")
    print("=" * 70)
    print(f"Records with no research evidence: {len(no_evidence)} / {len(records)}")
    print()
    print("Breakdown by research.why() reason:")
    for reason, count in sorted(why_reasons.items(), key=lambda x: -x[1]):
        print(f"  {reason}: {count}")
    no_reason = len(no_evidence) - sum(why_reasons.values())
    print(f"  (no reason / would not fire): {no_reason}")
    print()

    # ---- Q2: Records with STALE evidence ----
    stale_records = []
    all_stale_fields = {}
    for rec in records:
        stale = research.stale_evidence(rec, TODAY)
        if stale:
            stale_records.append((rec, stale))
            for entry in stale:
                field = entry.get("field", "unknown")
                all_stale_fields[field] = all_stale_fields.get(field, 0) + 1

    print("=" * 70)
    print("Q2: RECORDS WITH STALE EVIDENCE (under TTL)")
    print("=" * 70)
    print(f"Records with at least one stale row: {len(stale_records)}")
    print()
    print("Stale rows by field:")
    for field, count in sorted(all_stale_fields.items(), key=lambda x: -x[1]):
        ttl = research.ttl_for(field)
        print(f"  {field} (TTL={ttl}d): {count} stale row(s)")
    print()

    # ---- Q3: Evidence present but UNUSABLE (boilerplate) ----
    records_with_only_boilerplate = []
    records_with_mixed = []
    total_rows_all = 0
    total_unusable_all = 0
    for rec in records:
        rows = rec.get("research") or []
        if not rows:
            continue
        total, unusable, usable, stale_count, fields_stale = classify_evidence_quality(rec)
        total_rows_all += total
        total_unusable_all += unusable
        if usable == 0 and unusable > 0:
            records_with_only_boilerplate.append(rec)
        elif usable > 0 and unusable > 0:
            records_with_mixed.append(rec)

    print("=" * 70)
    print("Q3: EVIDENCE PRESENT BUT UNUSABLE (BOILERPLATE)")
    print("=" * 70)
    print(f"Total research rows across all records: {total_rows_all}")
    print(f"Total rows classified as boilerplate: {total_unusable_all}")
    if total_rows_all:
        print(f"  Boilerplate rate: {100*total_unusable_all/total_rows_all:.1f}%")
    print()
    print(f"Records with ONLY boilerplate evidence (nothing usable): {len(records_with_only_boilerplate)}")
    print(f"Records with mixed usable+boilerplate evidence: {len(records_with_mixed)}")
    print()

    # Records left with nothing usable to show = no_evidence + only_boilerplate
    nothing_usable = len(no_evidence) + len(records_with_only_boilerplate)
    print(f"Records with NOTHING usable to show: {nothing_usable}")
    print()

    # ---- Q4: ICP qualification of records needing research ----
    # "Need research" = why() fires OR stale evidence OR only-boilerplate
    needs_research_ids = set()
    for rec in no_evidence:
        if research.why(rec, today=TODAY):
            needs_research_ids.add(rec["id"])
    for rec, _ in stale_records:
        needs_research_ids.add(rec["id"])
    for rec in records_with_only_boilerplate:
        needs_research_ids.add(rec["id"])

    needs_research = [rec for rec in records if rec["id"] in needs_research_ids]

    icp_qualified = 0
    icp_rejected = 0
    icp_review = 0
    icp_unknown = 0
    icp_no_verdict = 0

    for rec in needs_research:
        verdict, icp_status = get_icp_verdict(rec)
        if verdict == "qualified":
            icp_qualified += 1
        elif verdict == "rejected":
            icp_rejected += 1
        elif verdict == "review":
            icp_review += 1
        elif verdict == "unknown":
            icp_unknown += 1
        else:
            icp_no_verdict += 1

    print("=" * 70)
    print("Q4: ICP QUALIFICATION OF RECORDS NEEDING RESEARCH")
    print("=" * 70)
    print(f"Total records needing research: {len(needs_research)}")
    print(f"  ICP qualified: {icp_qualified}")
    print(f"  ICP review: {icp_review}")
    print(f"  ICP unknown: {icp_unknown}")
    print(f"  ICP rejected: {icp_rejected}")
    print(f"  No ICP verdict: {icp_no_verdict}")
    print()

    # ---- WORKLIST ----
    print("=" * 70)
    print("PRIORITISED RESEARCH WORKLIST")
    print("=" * 70)

    worklist = []
    for rec in records:
        rid = rec["id"]
        domain = rec.get("domain", "")
        lane = rec.get("lane", "")
        verdict, icp_status = get_icp_verdict(rec)
        reason = research.why(rec, today=TODAY)
        stale = research.stale_evidence(rec, today=TODAY)
        rows = rec.get("research") or []

        # Classify usability
        total, unusable, usable, stale_count, fields_stale = classify_evidence_quality(rec) if rows else (0, 0, 0, 0, {})

        needs = None
        if reason:
            needs = reason
        elif stale:
            needs = research.NEED_REFRESH
        elif rows and usable == 0 and unusable > 0:
            needs = "all_evidence_boilerplate"

        if not needs:
            continue

        # Determine free vs paid likelihood
        # webfetch works for static sites; JS-heavy or blocked sites need Apify
        # We cannot know without probing, but we can note the domain for free leg first
        free_first = True  # always try free first per the waterfall design

        # Priority: ICP-qualified > review/unknown > rejected (skip rejected)
        if verdict == "rejected":
            priority = 3  # lowest - do not crawl rejected companies
        elif verdict == "qualified":
            priority = 0  # highest value
        elif verdict in ("review", "unknown"):
            priority = 1
        else:
            priority = 2  # no verdict yet

        worklist.append({
            "id": rid,
            "domain": domain,
            "lane": lane,
            "company": rec.get("company", ""),
            "reason": needs,
            "icp_verdict": verdict or "none",
            "icp_status": icp_status or "none",
            "priority": priority,
            "free_first": free_first,
            "stale_fields": list(fields_stale.keys()) if fields_stale else [],
            "existing_rows": total,
            "usable_rows": usable,
        })

    # Sort: priority asc (qualified first), then by reason
    worklist.sort(key=lambda x: (x["priority"], x["reason"], x["id"]))

    # Summary counts
    qualified_wl = [w for w in worklist if w["icp_verdict"] == "qualified"]
    review_wl = [w for w in worklist if w["icp_verdict"] in ("review", "unknown")]
    rejected_wl = [w for w in worklist if w["icp_verdict"] == "rejected"]
    no_verdict_wl = [w for w in worklist if w["icp_verdict"] == "none"]

    print(f"Total worklist entries: {len(worklist)}")
    print(f"  ICP-qualified (highest value): {len(qualified_wl)}")
    print(f"  ICP review/unknown: {len(review_wl)}")
    print(f"  No ICP verdict yet: {len(no_verdict_wl)}")
    print(f"  ICP-rejected (do not crawl): {len(rejected_wl)}")
    print()

    # Reason breakdown in worklist
    reason_counts = {}
    for w in worklist:
        r = w["reason"]
        reason_counts[r] = reason_counts.get(r, 0) + 1
    print("Worklist by reason:")
    for r, c in sorted(reason_counts.items(), key=lambda x: -x[1]):
        print(f"  {r}: {c}")
    print()

    # Print the actionable worklist (excluding rejected)
    actionable = [w for w in worklist if w["icp_verdict"] != "rejected"]
    print(f"Actionable records (non-rejected): {len(actionable)}")
    print()

    # Output the full worklist as JSON for the report
    output_path = os.path.join(ROOT, "scripts", "task154_worklist.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "stamp": stamp,
            "generated_at": TODAY.isoformat(),
            "summary": {
                "total_records": len(records),
                "no_evidence": len(no_evidence),
                "why_fires": sum(why_reasons.values()),
                "why_reasons": why_reasons,
                "stale_records": len(stale_records),
                "stale_fields": all_stale_fields,
                "total_research_rows": total_rows_all,
                "boilerplate_rows": total_unusable_all,
                "records_only_boilerplate": len(records_with_only_boilerplate),
                "records_mixed": len(records_with_mixed),
                "nothing_usable": nothing_usable,
                "needs_research": len(needs_research),
                "icp_qualified": icp_qualified,
                "icp_review": icp_review,
                "icp_unknown": icp_unknown,
                "icp_rejected": icp_rejected,
                "icp_no_verdict": icp_no_verdict,
                "worklist_total": len(worklist),
                "worklist_actionable": len(actionable),
            },
            "worklist": worklist,
        }, f, indent=2, ensure_ascii=False)
    print(f"Worklist written to: {output_path}")


if __name__ == "__main__":
    main()
