#!/usr/bin/env python3
"""Measure research freshness across the live queue. TASK-416.

For every record with rec["research"] populated, reports:
  - how old each research entry is (published_at age, retrieved_at age)
  - frozen quality vs re-aged quality (what it was when stored vs now)
  - whether stale research is silently informing current copy

Run from the repository root:
    python scripts/measure_research_freshness.py

Requires the live queue at work/queue.jsonl (Claude's worktree only).
"""
import collections
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from src import evidence


def load_queue():
    path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..",
                                        "work", "queue.jsonl"))
    if not os.path.exists(path):
        print(f"ERROR: {path} not found. This script must run against the live queue.")
        sys.exit(1)
    records = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def main():
    today = datetime.date.today()
    records = load_queue()
    today_iso = today.isoformat()

    researched = [r for r in records if r.get("research")]
    print(f"Total records: {len(records)}")
    print(f"Records with research: {len(researched)}")
    print(f"Today: {today_iso}")
    print()

    if not researched:
        print("No records with research found. Nothing to measure.")
        return

    sample = researched[:min(50, len(researched))]

    age_buckets = collections.Counter()
    quality_shifts = collections.Counter()
    frozen_vs_reaged = {"same": 0, "downgraded": 0, "upgraded": 0}
    has_published_at = 0
    has_retrieved_at = 0
    published_ages = []
    retrieved_ages = []
    records_with_stale = []

    print("=" * 80)
    print("PER-RECORD DETAIL (up to 50 records)")
    print("=" * 80)

    for rec in sample:
        rid = rec.get("id", "?")
        state = rec.get("state", "?")
        research_entries = rec.get("research", [])
        research_state = rec.get("research_state") or {}
        company_at = research_state.get("company_at", "")

        record_has_stale = False
        print(f"\n--- {rid} (state={state}) ---")
        if company_at:
            print(f"  research_state.company_at: {company_at}")

        for i, entry in enumerate(research_entries):
            pub_at = entry.get("published_at", "")
            ret_at = entry.get("retrieved_at", "")
            frozen_quality = entry.get("quality", "?")
            frozen_bucket = entry.get("freshness_bucket", "?")
            stored_age = entry.get("age_days")

            reaged = evidence.recheck(entry, today_iso)
            current_age = reaged.get("age_days")
            current_bucket = reaged.get("freshness_bucket", "?")
            current_quality = reaged.get("quality", "?")

            if pub_at:
                has_published_at += 1
            if ret_at:
                has_retrieved_at += 1

            if current_age is not None:
                published_ages.append(current_age)
                if current_age <= 30:
                    age_buckets["0-30d (HIGH)"] += 1
                elif current_age <= 90:
                    age_buckets["31-90d (MEDIUM)"] += 1
                elif current_age <= 365:
                    age_buckets["91-365d (LOW)"] += 1
                else:
                    age_buckets["365d+ (BACKGROUND)"] += 1
                    record_has_stale = True

            if ret_at:
                try:
                    ret_date = datetime.datetime.fromisoformat(
                        ret_at.replace("Z", "+00:00")).date()
                    ret_age = (today - ret_date).days
                    retrieved_ages.append(ret_age)
                except (ValueError, AttributeError):
                    pass

            shift = "same"
            if frozen_quality != current_quality:
                usable_old = frozen_quality in ("strong", "medium")
                usable_new = current_quality in ("strong", "medium")
                if usable_old and not usable_new:
                    shift = "downgraded"
                    quality_shifts[f"{frozen_quality} -> {current_quality}"] += 1
                elif not usable_old and usable_new:
                    shift = "upgraded"
                    quality_shifts[f"{frozen_quality} -> {current_quality}"] += 1
                else:
                    shift = "same"
                    quality_shifts[f"{frozen_quality} -> {current_quality} (lateral)"] += 1

            if shift != "same":
                frozen_vs_reaged["downgraded" if "downgrade" in shift or
                                 (frozen_quality in ("strong", "medium") and
                                  current_quality not in ("strong", "medium"))
                                 else "upgraded"] += 1
            else:
                frozen_vs_reaged["same"] += 1

            stale_marker = " ** STALE **" if current_age and current_age > 365 else ""
            print(f"  [{i}] published_at={pub_at or 'N/A'}"
                  f"  age={current_age if current_age is not None else '?'}d"
                  f"  bucket={current_bucket}"
                  f"  quality: {frozen_quality} -> {current_quality}"
                  f"{stale_marker}")

        if record_has_stale:
            records_with_stale.append(rid)

    print()
    print("=" * 80)
    print("DISTRIBUTION SUMMARY (all records with research, n={})".format(
        len(researched)))
    print("=" * 80)

    all_entries = []
    for rec in researched:
        all_entries.extend(rec.get("research", []))

    print(f"\nTotal research entries: {len(all_entries)}")
    print(f"  with published_at: {sum(1 for e in all_entries if e.get('published_at'))}")
    print(f"  with retrieved_at: {sum(1 for e in all_entries if e.get('retrieved_at'))}")

    reaged_ages = []
    reaged_buckets = collections.Counter()
    reaged_qualities = collections.Counter()
    frozen_qualities = collections.Counter()
    aged_out_count = 0

    for entry in all_entries:
        frozen_qualities[entry.get("quality", "?")] += 1
        reaged = evidence.recheck(entry, today_iso)
        age = reaged.get("age_days")
        if age is not None:
            reaged_ages.append(age)
        reaged_buckets[reaged.get("freshness_bucket", "?")] += 1
        reaged_qualities[reaged.get("quality", "?")] += 1
        if reaged.get("aged_out"):
            aged_out_count += 1

    print(f"\nFrozen quality (at time of storage):")
    for q in ("strong", "medium", "weak", "unusable"):
        print(f"  {q}: {frozen_qualities.get(q, 0)}")

    print(f"\nRe-aged quality (as of {today_iso}):")
    for q in ("strong", "medium", "weak", "unusable"):
        print(f"  {q}: {reaged_qualities.get(q, 0)}")

    print(f"\nRe-aged freshness buckets:")
    for b in ("high", "medium", "low", "background", "unknown"):
        print(f"  {b}: {reaged_buckets.get(b, 0)}")

    if reaged_ages:
        reaged_ages.sort()
        print(f"\nPublished-at age distribution (days):")
        print(f"  min: {reaged_ages[0]}")
        print(f"  p25: {reaged_ages[len(reaged_ages)//4]}")
        print(f"  p50: {reaged_ages[len(reaged_ages)//2]}")
        print(f"  p75: {reaged_ages[3*len(reaged_ages)//4]}")
        print(f"  max: {reaged_ages[-1]}")
        print(f"  mean: {sum(reaged_ages)/len(reaged_ages):.0f}")

    if retrieved_ages:
        retrieved_ages.sort()
        print(f"\nRetrieved-at age distribution (days):")
        print(f"  min: {retrieved_ages[0]}")
        print(f"  p50: {retrieved_ages[len(retrieved_ages)//2]}")
        print(f"  max: {retrieved_ages[-1]}")
        print(f"  mean: {sum(retrieved_ages)/len(retrieved_ages):.0f}")

    print(f"\nAged out (was USABLE, now not): {aged_out_count}")
    print(f"Records with any entry > 365d old: {len(records_with_stale)}")
    if records_with_stale:
        print(f"  IDs: {', '.join(records_with_stale[:20])}")

    print()
    print("=" * 80)
    print("CODE PATH ANALYSIS")
    print("=" * 80)
    print("""
Paths that DO re-age (safe):
  - personalization.stored() -> evidence.recheck(entry, today)
  - research.for_prompt() -> evidence.select() -> usable() -> reaged()
  - quality.evidence_recency() -> evidence.recheck(item, today)

Paths that read FROZEN quality (potentially stale):
  - generate.research_block() filters by e.get("quality") in ("medium","strong")
    without re-aging. A fact that was strong 6 months ago still passes.
  - claims._support_text() reads rec["research"] raw for claim checking.
  - eligibility.py reads research without re-aging.
  - dossier.py counts research entries without re-aging.
  - preview.py filters research without re-aging.

Mitigation: research.for_prompt() IS the prompt path and DOES re-age through
evidence.select(). The prompt sees current quality. But generate.research_block()
is a SEPARATE block also injected into the prompt context, and it reads frozen
quality. If both blocks reach the model, stale evidence could appear via
research_block even though for_prompt filtered it correctly.
""")


if __name__ == "__main__":
    main()
