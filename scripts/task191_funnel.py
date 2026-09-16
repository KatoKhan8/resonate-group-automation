#!/usr/bin/env python3
"""TASK-191: Compute the funnel from live queue state.

Reads work/queue.jsonl from the authoritative source (Claude's worktree or
local) and produces a PII-safe funnel with explicit predicates for every stage.

Usage:
    py -3 scripts/task191_funnel.py [--queue PATH]

Defaults to C:/Users/Zvonimir/Desktop/resonate-group-automation/work/queue.jsonl
"""

import json
import os
import sys
import time
from collections import Counter
from datetime import datetime, timezone

# Default: Claude's worktree, where queue.jsonl lives
DEFAULT_QUEUE = (
    r"C:\Users\Zvonimir\Desktop\resonate-group-automation\work\queue.jsonl"
)


def load_records(path):
    records = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


def has_company_facts(r):
    """Predicate: record has non-empty company_facts."""
    cf = r.get("company_facts")
    return bool(cf and isinstance(cf, (dict, list)) and len(cf) > 0)


def has_research(r):
    """Predicate: record has non-empty research."""
    res = r.get("research")
    return bool(res and isinstance(res, list) and len(res) > 0)


def get_icp_status(r):
    """Extract icp_status from the nested verdict structure."""
    v = r.get("qualification", {}).get("verdict", {})
    return v.get("icp_status") if isinstance(v, dict) else None


def get_icp_confidence(r):
    """Extract icp_confidence from the nested verdict structure."""
    v = r.get("qualification", {}).get("verdict", {})
    return v.get("icp_confidence") if isinstance(v, dict) else None


def has_contacts(r):
    """Predicate: record has at least one contact."""
    c = r.get("contacts")
    return bool(c and isinstance(c, list) and len(c) > 0)


def has_enrichment(r):
    """Predicate: record has been through enrichment (enrich stage exists)."""
    e = r.get("stages", {}).get("enrich", {})
    return bool(e.get("status"))


def has_verification(r):
    """Predicate: record has at least one contact with verification state."""
    for c in r.get("contacts", []):
        if isinstance(c, dict):
            v = c.get("verification")
            if isinstance(v, dict) and v.get("state"):
                return True
    return False


def has_sendable_contact(r):
    """Predicate: record has at least one verified+sendable contact."""
    for c in r.get("contacts", []):
        if isinstance(c, dict):
            v = c.get("verification", {})
            if isinstance(v, dict) and v.get("state") == "verified" and v.get("sendable"):
                return True
    return False


def has_cadence(r):
    """Predicate: record has a cadence assigned."""
    return bool(r.get("cadence"))


def has_generate(r):
    """Predicate: record has been through generation (generate stage done)."""
    g = r.get("stages", {}).get("generate", {})
    return g.get("status") == "done"


def has_draft(r):
    """Predicate: record has at least one draft_generated event."""
    for e in r.get("events", []):
        if isinstance(e, dict) and e.get("type") == "draft_generated":
            return True
    return False


def has_approval(r):
    """Predicate: record has at least one draft_approved event."""
    for e in r.get("events", []):
        if isinstance(e, dict) and e.get("type") == "draft_approved":
            return True
    return False


def is_dropped(r):
    """Predicate: record is dropped."""
    return r.get("state") == "dropped" or bool(r.get("drop_reason"))


def is_held(r):
    """Predicate: record is held."""
    return r.get("state") == "held"


def compute_funnel(records):
    """Compute the funnel with explicit predicates for each stage.

    Each stage counts records that satisfy the predicate, regardless of
    whether they also satisfy later stages. This is a "has reached at least"
    funnel, not a "currently at" funnel.
    """
    total = len(records)

    # Stage predicates - each counts records that have REACHED this stage
    stages = [
        ("RECEIVED",
         "All records in queue.jsonl",
         lambda r: True),
        ("NORMALIZED",
         "Record has non-empty company_facts (company research ingested)",
         has_company_facts),
        ("FREE_RESEARCH",
         "Record has non-empty research list (free evidence gathered)",
         has_research),
        ("PRELIMINARY_ICP",
         "Record has stages.qualify.status = 'done' (ICP scoring ran)",
         lambda r: r.get("stages", {}).get("qualify", {}).get("status") == "done"),
        ("QUALIFIED",
         "Record has qualification.verdict.icp_status = 'qualified'",
         lambda r: get_icp_status(r) == "qualified"),
        ("ICP_REVIEW",
         "Record has qualification.verdict.icp_status = 'review'",
         lambda r: get_icp_status(r) == "review"),
        ("PERSON_DISCOVERY",
         "Record has at least one contact in contacts[]",
         has_contacts),
        ("ENRICHMENT",
         "Record has stages.enrich.status set (enrichment ran, partial or done)",
         has_enrichment),
        ("VERIFICATION",
         "Record has at least one contact with verification.state set",
         has_verification),
        ("VERIFIED_SENDABLE",
         "Record has at least one contact with verification.state='verified' AND sendable=True",
         has_sendable_contact),
        ("CAMPAIGN_READY",
         "Record has cadence assigned (non-empty cadence field)",
         has_cadence),
        ("GENERATED",
         "Record has stages.generate.status = 'done'",
         has_generate),
        ("APPROVAL",
         "Record has at least one draft_approved event",
         has_approval),
    ]

    results = []
    for name, predicate_desc, pred in stages:
        count = sum(1 for r in records if pred(r))
        results.append({
            "stage": name,
            "count": count,
            "predicate": predicate_desc,
            "pct_of_received": round(100.0 * count / total, 1) if total else 0,
        })

    # Terminal states
    dropped = sum(1 for r in records if is_dropped(r))
    held = sum(1 for r in records if is_held(r))
    dropped_reasons = Counter()
    for r in records:
        if is_dropped(r):
            dropped_reasons[r.get("drop_reason", "UNSPECIFIED")] += 1

    return results, dropped, held, dropped_reasons


def state_distribution(records):
    """Current state distribution (where records ARE, not where they've been)."""
    return dict(Counter(r.get("state", "MISSING") for r in records))


def icp_distribution(records):
    """ICP status distribution from verdict."""
    return dict(Counter(get_icp_status(r) or "NO_VERDICT" for r in records))


def contact_summary(records):
    """PII-safe contact summary."""
    total = 0
    verified = 0
    sendable = 0
    no_verification = 0
    for r in records:
        for c in r.get("contacts", []):
            if isinstance(c, dict):
                total += 1
                v = c.get("verification")
                if isinstance(v, dict):
                    if v.get("state") == "verified":
                        verified += 1
                    if v.get("state") == "verified" and v.get("sendable"):
                        sendable += 1
                else:
                    no_verification += 1
    return {
        "total_contacts": total,
        "verified_contacts": verified,
        "sendable_contacts": sendable,
        "contacts_without_verification": no_verification,
        "records_with_contacts": sum(1 for r in records if has_contacts(r)),
    }


def reconcile_populations(queue_path, snapshot_path, snapshot_stamp_path):
    """Explain the three populations: 550, 316, 300."""
    queue_count = 0
    if os.path.exists(queue_path):
        with open(queue_path, encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    queue_count += 1

    snapshot_count = 0
    if os.path.exists(snapshot_path):
        with open(snapshot_path, encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    snapshot_count += 1

    stamp = ""
    if os.path.exists(snapshot_stamp_path):
        with open(snapshot_stamp_path, encoding="utf-8") as fh:
            stamp = fh.read().strip()

    return {
        "live_queue": {
            "path": queue_path,
            "records": queue_count,
            "present": os.path.exists(queue_path),
        },
        "snapshot": {
            "path": snapshot_path,
            "records": snapshot_count,
            "present": os.path.exists(snapshot_path),
            "stamp": stamp,
        },
        "reconciliation": {
            "550": "Total records in live queue.jsonl AND current snapshot. "
                   "The full estate as of 2026-09-15T17:52:12Z.",
            "316": "Subset of 550 that were in 'queued' state in the snapshot. "
                   "These were the records with no company_facts, no research, "
                   "no stages - the target of the free-path run (TASK-163, TASK-171). "
                   "NOT a separate population; it is 316 of the 550.",
            "300": "Total records in the OLD snapshot from 2026-09-14T21:52:15Z "
                   "(master 0ac5e60). The estate grew from 300 to 550 between "
                   "Sept 14 evening and Sept 15 afternoon. The PRODUCTION-DASHBOARD.md "
                   "was generated from this old snapshot and carries the 300 number. "
                   "A free-path run then processed the 316 queued records, mutating "
                   "live state.",
        },
    }


def main():
    queue_path = DEFAULT_QUEUE
    if "--queue" in sys.argv:
        idx = sys.argv.index("--queue")
        if idx + 1 < len(sys.argv):
            queue_path = sys.argv[idx + 1]

    if not os.path.exists(queue_path):
        print(f"ERROR: queue not found at {queue_path}", file=sys.stderr)
        return 1

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    snapshot_path = os.path.join(root, "work", "queue.snapshot.jsonl")
    stamp_path = os.path.join(root, "work", "queue.snapshot.STAMP")

    # Check if queue is being actively written to
    mtime = os.path.getmtime(queue_path)
    age_minutes = (time.time() - mtime) / 60
    run_in_flight = age_minutes < 5

    records = load_records(queue_path)
    funnel, dropped, held, drop_reasons = compute_funnel(records)
    states = state_distribution(records)
    icp = icp_distribution(records)
    contacts = contact_summary(records)
    populations = reconcile_populations(queue_path, snapshot_path, stamp_path)

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": {
            "file": queue_path,
            "records": len(records),
            "mtime": datetime.fromtimestamp(mtime, timezone.utc).isoformat(),
            "age_minutes": round(age_minutes, 1),
            "run_in_flight": run_in_flight,
            "provisional": run_in_flight,
        },
        "populations": populations,
        "funnel": funnel,
        "terminal_states": {
            "dropped": dropped,
            "held": held,
            "drop_reasons": dict(drop_reasons),
        },
        "current_state_distribution": states,
        "icp_distribution": icp,
        "contacts": contacts,
    }

    print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
