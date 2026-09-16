"""TASK-163: measure what ICP says about evidence-free records.

Reads the snapshot (read-only), picks 5 queued records with no company_facts
and no research, runs qualify.company(store_result=False) on each, and reports
the verdict. Does NOT write to the snapshot.

The question: does evidence-free ICP return dropped/rejected, or review/unknown?
"""
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import clients, qualify, segments, icp, icpstructural, store


SNAPSHOT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "work", "queue.snapshot.jsonl",
)


def load_snapshot():
    recs = []
    with open(SNAPSHOT, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                recs.append(json.loads(line))
    return recs


def main():
    recs = load_snapshot()
    queued_no_evidence = [
        r for r in recs
        if r.get("state") == "queued"
        and not r.get("company_facts")
        and not r.get("research")
        and not r.get("stages")
    ]
    print(f"Snapshot: {len(recs)} records total")
    print(f"Queued with no facts/research/stages: {len(queued_no_evidence)}")
    print()

    try:
        config = clients.load("productive")
    except Exception as e:
        print(f"Config load failed: {e}")
        config = {}

    five = queued_no_evidence[:5]
    print("=" * 78)
    print("MEASUREMENT: qualify.company on 5 evidence-free records")
    print("=" * 78)

    verdicts = []
    for rec in five:
        # Deep-copy the record so nothing mutates the snapshot data
        import copy
        work = copy.deepcopy(rec)

        # Run qualify without storing
        result = qualify.company(work, config, store_result=False)

        verdict = result["verdict"]
        segment = result["segment"]
        rec_id = rec["id"]
        domain = rec.get("domain")
        company = rec.get("company")

        icp_status = verdict.get("icp_status")
        icp_tier = verdict.get("icp_tier")
        icp_score = verdict.get("icp_score")
        icp_confidence = verdict.get("icp_confidence")
        vertical = segment.get("vertical")
        missing = verdict.get("missing_evidence", [])
        negative = verdict.get("negative_signals", [])
        positive = verdict.get("positive_signals", [])
        structural = verdict.get("structural", {})
        struct_verdict = structural.get("verdict")
        struct_criteria = structural.get("criteria", {})

        print(f"\n--- {rec_id} ({domain}) ---")
        print(f"  company name:     {company}")
        print(f"  vertical:         {vertical}")
        print(f"  icp_status:       {icp_status}")
        print(f"  icp_tier:         {icp_tier}")
        print(f"  icp_score:        {icp_score}")
        print(f"  icp_confidence:   {icp_confidence}")
        print(f"  structural:       {struct_verdict}")
        for name, answer in struct_criteria.items():
            print(f"    {name:<20} {answer['status']}: {answer['why'][:80]}")
        print(f"  positive signals: {len(positive)}")
        print(f"  negative signals: {len(negative)}")
        print(f"  missing evidence: {len(missing)} items")
        for m in missing[:5]:
            print(f"    - {m}")

        # What is the record's state after qualify?
        state_after = work.get("state")
        print(f"  state after:      {state_after}")

        verdicts.append({
            "id": rec_id,
            "domain": domain,
            "icp_status": icp_status,
            "icp_tier": icp_tier,
            "icp_score": icp_score,
            "icp_confidence": icp_confidence,
            "structural_verdict": struct_verdict,
            "state_after": state_after,
        })

    print()
    print("=" * 78)
    print("SUMMARY")
    print("=" * 78)
    status_counts = {}
    for v in verdicts:
        s = v["icp_status"]
        status_counts[s] = status_counts.get(s, 0) + 1
    for s, c in sorted(status_counts.items()):
        print(f"  {s:<20} {c}")

    dropped = sum(1 for v in verdicts if v["state_after"] == "dropped")
    rejected = sum(1 for v in verdicts if v["icp_status"] == "rejected")
    print()
    print(f"  DROPPED:  {dropped}/5  (terminal, unrecoverable)")
    print(f"  REJECTED: {rejected}/5  (recoverable if verdict changes)")
    print(f"  REVIEW:   {status_counts.get('review', 0)}/5  (recoverable)")
    print(f"  UNKNOWN:  {status_counts.get('unknown', 0)}/5  (recoverable)")
    print()
    if dropped == 0:
        print("  CONCLUSION: No evidence-free record was dropped.")
        print("  qualify.company on empty records returns review/unknown,")
        print("  which is recoverable. The batch is safe to qualify.")
    else:
        print(f"  WARNING: {dropped} record(s) were DROPPED. This is terminal.")


if __name__ == "__main__":
    main()
