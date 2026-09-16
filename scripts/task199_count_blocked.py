#!/usr/bin/env python3
"""TASK-199: count the blocked populations and their overlap.

Three counts:
  A. Records blocked at ICP for want of evidence (geography or company_type UNKNOWN)
  B. Records blocked at generation by check_evidence (verified, no usable research)
  C. The overlap: records in both A and B

Predicates are stated exactly so the count is reproducible.
"""
import hashlib
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from src import icpstructural, clients, segments


def load_snapshot(path):
    recs = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                recs.append(json.loads(line))
    return recs


def hash_id(rec_id):
    return hashlib.sha256(str(rec_id).encode()).hexdigest()[:12]


def is_blocked_at_icp(rec, config):
    """Predicate: geography or company_type is UNKNOWN.

    A record is blocked at ICP when at least one of the two DEFINING criteria
    (geography, company_type) has status UNKNOWN. This is the predicate from
    icpstructural.verdict_of: if both DEFINING are PASS, the record is at
    least ICP_PASS_WITH_UNCERTAINTY (eligible). If either is UNKNOWN, the
    verdict is ICP_REVIEW.
    """
    segment = segments.classify(rec, config)
    criteria = icpstructural.structural(rec, config, segment=segment)
    unknowns = criteria.get("unknown_criteria", [])
    return "geography" in unknowns or "company_type" in unknowns


def is_blocked_at_generation(rec):
    """Predicate: verified state, zero usable research rows.

    A record is blocked at generation when it is verified (has sendable
    contacts) but has no research rows with quality medium or strong. The
    persona_angle step requires evidence traceable to research rows; with
    zero usable rows, check_evidence structurally cannot pass.
    """
    if rec.get("state") not in ("verified", "held"):
        return False
    research = rec.get("research") or []
    usable = [r for r in research
              if isinstance(r, dict)
              and r.get("quality") in ("medium", "strong")]
    return len(usable) == 0


def main():
    snapshot = os.path.join(ROOT, "work", "queue.snapshot.jsonl")
    if not os.path.exists(snapshot):
        # Try the Claude worktree
        alt = os.path.join(ROOT, "..", "resonate-group-automation",
                           "work", "queue.snapshot.jsonl")
        if os.path.exists(alt):
            snapshot = alt
        else:
            print("ERROR: no queue.snapshot.jsonl found")
            sys.exit(1)

    recs = load_snapshot(snapshot)
    config = clients.load("productive")

    blocked_icp = []
    blocked_gen = []
    overlap = []

    for rec in recs:
        icp_blocked = is_blocked_at_icp(rec, config)
        gen_blocked = is_blocked_at_generation(rec)

        if icp_blocked:
            blocked_icp.append(rec)
        if gen_blocked:
            blocked_gen.append(rec)
        if icp_blocked and gen_blocked:
            overlap.append(rec)

    print(f"Snapshot: {len(recs)} records")
    print()
    print(f"A. Blocked at ICP (geography or company_type UNKNOWN): {len(blocked_icp)}")
    print(f"   Predicate: icpstructural.structural verdict has")
    print(f"   'geography' or 'company_type' in unknown_criteria")
    print()
    print(f"B. Blocked at generation (verified/held, 0 usable research): {len(blocked_gen)}")
    print(f"   Predicate: state in (verified, held) AND")
    print(f"   len([r for r in research if quality in (medium, strong)]) == 0")
    print()
    print(f"C. Overlap (blocked at BOTH): {len(overlap)}")
    print(f"   One purchase unblocks these records twice.")
    print()

    # Breakdown of ICP-blocked by which criterion is unknown
    geo_unknown = sum(1 for r in blocked_icp
                      if "geography" in
                      icpstructural.structural(r, config).get("unknown_criteria", []))
    ct_unknown = sum(1 for r in blocked_icp
                     if "company_type" in
                     icpstructural.structural(r, config).get("unknown_criteria", []))
    both_unknown = sum(1 for r in blocked_icp
                       if "geography" in icpstructural.structural(r, config).get("unknown_criteria", [])
                       and "company_type" in icpstructural.structural(r, config).get("unknown_criteria", []))

    print(f"ICP breakdown:")
    print(f"  geography UNKNOWN:      {geo_unknown}")
    print(f"  company_type UNKNOWN:   {ct_unknown}")
    print(f"  both UNKNOWN:           {both_unknown}")
    print()

    # Hashed IDs of the overlap
    print(f"Overlap records (hashed):")
    for rec in overlap:
        print(f"  {hash_id(rec['id']):12s}  state={rec.get('state')}  "
              f"research={len(rec.get('research') or [])}  "
              f"company={rec.get('company', '?')[:30]}")


if __name__ == "__main__":
    main()
