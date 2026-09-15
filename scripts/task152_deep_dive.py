#!/usr/bin/env python3
"""TASK-152 deep dive: held records, qualified-queued records, and cost detail."""
import json
import os
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SNAPSHOT = os.path.join(ROOT, "work", "queue.snapshot.jsonl")


def load_records():
    records = []
    with open(SNAPSHOT, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def main():
    records = load_records()

    # ---- HELD RECORDS: WHY? ----
    print("=" * 60)
    print("HELD RECORDS: WHY ARE THEY HELD?")
    print("=" * 60)
    held = [r for r in records if r.get("state") == "held"]
    print(f"Total held: {len(held)}")

    held_reasons = Counter()
    for r in held:
        # Check last log entry for reason
        log = r.get("log") or []
        held_entries = [e for e in log if e.get("step") == "held"]
        if held_entries:
            last_held = held_entries[-1]
            note = last_held.get("note", "no note")
            held_reasons[note[:80]] += 1
        else:
            # Check what the last step was
            if log:
                last = log[-1]
                held_reasons[f"last_step:{last.get('step')}:{last.get('note','')[:50]}"] += 1
            else:
                held_reasons["no log entries"] += 1

    for reason, count in held_reasons.most_common():
        print(f"  {reason:<80} {count:>4}")
    print()

    # ---- QUALIFIED BUT STILL QUEUED ----
    print("=" * 60)
    print("QUALIFIED BUT STILL QUEUED: WHY NOT ENRICHED?")
    print("=" * 60)
    qual_queued = [r for r in records
                   if r.get("state") == "queued" and r.get("qualification")]
    print(f"Total qualified but queued: {len(qual_queued)}")

    # Break down by ICP status
    icp_breakdown = Counter()
    for r in qual_queued:
        q = r.get("qualification") or {}
        verdict = q.get("verdict") or {}
        status = verdict.get("icp_status", "unknown")
        icp_breakdown[status] += 1
    print("  By ICP status:")
    for status, count in icp_breakdown.most_common():
        print(f"    {status:<20} {count:>5}")
    print()

    # ---- NOT YET QUALIFIED ----
    print("=" * 60)
    print("NOT YET QUALIFIED: WHAT STATE ARE THEY IN?")
    print("=" * 60)
    unqualified = [r for r in records
                   if r.get("state") == "queued" and not r.get("qualification")]
    print(f"Total not yet qualified: {len(unqualified)}")

    # Do they have company_facts?
    with_facts = sum(1 for r in unqualified if r.get("company_facts"))
    with_research = sum(1 for r in unqualified if r.get("research"))
    with_contacts = sum(1 for r in unqualified if r.get("contacts"))
    print(f"  With company_facts: {with_facts}")
    print(f"  With research: {with_research}")
    print(f"  With contacts: {with_contacts}")

    # Log steps for unqualified
    unqual_steps = Counter()
    for r in unqualified:
        for e in (r.get("log") or []):
            unqual_steps[e.get("step", "")] += 1
    print("  Log step counts across all unqualified:")
    for step, count in unqual_steps.most_common():
        print(f"    {step:<20} {count:>5}")
    print()

    # ---- DROPPED: ICP REJECTED DETAIL ----
    print("=" * 60)
    print("DROPPED ICP REJECTED: SIZE BREAKDOWN")
    print("=" * 60)
    dropped_icp = [r for r in records
                   if r.get("state") == "dropped"
                   and r.get("drop_reason", "").startswith("rejected at ICP")]
    print(f"Total dropped at ICP: {len(dropped_icp)}")

    # Employee counts
    emp_counts = []
    for r in dropped_icp:
        facts = r.get("company_facts") or {}
        emp = facts.get("employees")
        if emp is not None:
            try:
                emp_counts.append(int(emp))
            except (ValueError, TypeError):
                pass
    if emp_counts:
        emp_counts.sort()
        print(f"  Employee counts: min={min(emp_counts)}, max={max(emp_counts)}, "
              f"median={emp_counts[len(emp_counts)//2]}")
        under_5 = sum(1 for e in emp_counts if e < 5)
        under_10 = sum(1 for e in emp_counts if e < 10)
        under_15 = sum(1 for e in emp_counts if e < 15)
        under_20 = sum(1 for e in emp_counts if e < 20)
        print(f"  Under 5: {under_5}, Under 10: {under_10}, "
              f"Under 15: {under_15}, Under 20: {under_20}")
    print()

    # Geo breakdown for ICP rejected
    geo_counts = Counter()
    for r in dropped_icp:
        facts = r.get("company_facts") or {}
        flags = facts.get("icp_flags") or []
        for flag in flags:
            if "geo" in flag.lower():
                geo_counts[flag] += 1
    print("  Geo rejection reasons:")
    for reason, count in geo_counts.most_common():
        print(f"    {reason:<60} {count:>4}")
    print()

    # ---- DRAFTED BUT NOT APPROVED ----
    print("=" * 60)
    print("DRAFTED BUT NOT APPROVED: WHAT'S PENDING?")
    print("=" * 60)
    drafted = [r for r in records if r.get("state") == "drafted"]
    print(f"Total drafted: {len(drafted)}")
    for r in drafted[:3]:
        log = r.get("log") or []
        drafts = [e for e in log if e.get("step") == "draft"]
        approvals = [e for e in log if e.get("step") == "approved"]
        print(f"  {r['id']}: {len(drafts)} drafts, {len(approvals)} approvals")
    print()

    # ---- VERIFIED BUT NOT DRAFTED ----
    print("=" * 60)
    print("VERIFIED BUT NOT DRAFTED")
    print("=" * 60)
    verified = [r for r in records if r.get("state") == "verified"]
    print(f"Total verified: {len(verified)}")
    for r in verified[:3]:
        log = r.get("log") or []
        contacts = r.get("contacts") or []
        sendable = [c for c in contacts if c.get("sendable")]
        print(f"  {r['id']}: {len(contacts)} contacts, {len(sendable)} sendable")
    print()

    # ---- COST PER STAGE DETAIL ----
    print("=" * 60)
    print("COST PER STAGE DETAIL (from 550 records)")
    print("=" * 60)

    # Enrich costs
    dm_calls = 0
    pc_calls = 0
    for r in records:
        for e in (r.get("log") or []):
            if e.get("step") == "enrich":
                note = e.get("note", "")
                if "people-count" in note:
                    pc_calls += 1
                elif "decision-makers" in note:
                    dm_calls += 1

    print(f"  Enrich/people-count: {pc_calls} calls x 0 credits = 0 credits")
    print(f"  Enrich/decision-makers: {dm_calls} calls x 10 credits = {dm_calls * 10} credits")

    # Verify costs
    verify_credits = 0
    co_calls = 0
    del_calls = 0
    reoon_calls = 0
    for r in records:
        for c in (r.get("contacts") or []):
            verif = c.get("verification") or {}
            results = verif.get("results") or {}
            if "contactout" in results:
                co_calls += 1
                verify_credits += 3
            if "deliverable" in results:
                del_calls += 1
                verify_credits += 1
            if "reoon" in results:
                reoon_calls += 1
                verify_credits += 1

    print(f"  Verify/ContactOut: {co_calls} calls x 3 credits = {co_calls * 3} credits")
    print(f"  Verify/Deliverable: {del_calls} calls x 1 credit = {del_calls} credits")
    print(f"  Verify/Reoon: {reoon_calls} calls x 1 credit = {reoon_calls} credits")
    print(f"  Total verify credits: {verify_credits}")

    # MX checks
    mx_checks = sum(1 for r in records for c in (r.get("contacts") or []) if c.get("mx"))
    print(f"  MX checks: {mx_checks} (free - DNS lookup)")

    # Model calls
    model_calls = 0
    model_steps = Counter()
    for r in records:
        for e in (r.get("log") or []):
            if e.get("step") in ("draft", "linkedin_note"):
                attempts = e.get("attempts", 1)
                model_calls += attempts
                model_steps[e["step"]] += attempts
    print(f"  Model calls (draft): {model_steps.get('draft', 0)}")
    print(f"  Model calls (linkedin_note): {model_steps.get('linkedin_note', 0)}")
    print(f"  Total model calls: {model_calls}")

    total_provider = dm_calls * 10 + verify_credits
    print()
    print(f"  TOTAL PROVIDER CREDITS: {total_provider}")
    print(f"  TOTAL MODEL CALLS: {model_calls}")
    print(f"  Provider credits per record (all 550): {total_provider/550:.2f}")
    print(f"  Model calls per record (all 550): {model_calls/550:.2f}")
    print()

    # ---- COST PER COMPLETED RECORD ----
    print("=" * 60)
    print("COST PER COMPLETED (SENDABLE) RECORD")
    print("=" * 60)
    sendable = sum(1 for r in records
                   if any(c.get("sendable") for c in (r.get("contacts") or [])))
    print(f"  Records with sendable contacts: {sendable}")
    if sendable:
        print(f"  Provider credits per sendable record: {total_provider/sendable:.1f}")
        print(f"  Model calls per sendable record: {model_calls/sendable:.1f}")
    print()

    # ---- THE 250 NOT YET QUALIFIED ----
    print("=" * 60)
    print("THE 250 NOT YET QUALIFIED: BATCH ORIGIN")
    print("=" * 60)
    unqualified = [r for r in records
                   if r.get("state") == "queued" and not r.get("qualification")]
    batch_origins = Counter()
    for r in unqualified:
        batch = r.get("batch") or {}
        source = batch.get("source", "unknown")
        batch_origins[source] += 1
    print("  By batch source:")
    for source, count in batch_origins.most_common():
        print(f"    {source:<50} {count:>5}")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
