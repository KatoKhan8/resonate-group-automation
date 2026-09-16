"""TASK-163: does the free webfetch research path trigger for these records?

Checks research.why() for the same 5 evidence-free records, with and without
a pre-computed verdict. This determines whether stage_enrich --spend --cap 0
would populate research before qualify runs.
"""
import json
import sys
import os
import copy

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import clients, qualify, research


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

    try:
        config = clients.load("productive")
    except Exception:
        config = {}

    five = queued_no_evidence[:5]
    print("=" * 78)
    print("DOES FREE RESEARCH TRIGGER FOR THESE RECORDS?")
    print("=" * 78)

    for rec in five:
        work = copy.deepcopy(rec)
        rec_id = rec["id"]
        domain = rec.get("domain")
        lane = rec.get("lane")
        contacts = rec.get("contacts") or []

        # Check research.why BEFORE any verdict
        why_before = research.why(work)

        # Compute a free verdict (store_result=False)
        result = qualify.company(work, config, store_result=False)
        verdict = result.get("verdict")

        # Check research.why AFTER verdict
        why_after = research.why(work, verdict=verdict)

        print(f"\n--- {rec_id} ({domain}) ---")
        print(f"  lane:             {lane}")
        print(f"  contacts:         {len(contacts)}")
        print(f"  research.why() before verdict: {why_before}")
        print(f"  verdict.icp_status:            {verdict.get('icp_status')}")
        print(f"  research.why(verdict) after:   {why_after}")

        if why_before:
            print(f"  -> webfetch WOULD trigger (reason: {why_before})")
        elif why_after:
            print(f"  -> webfetch WOULD trigger after verdict (reason: {why_after})")
        else:
            print(f"  -> webfetch would NOT trigger for this record")
            print(f"     (domains lane with 0 contacts: needs_angle is False)")

    # Also check: what about records that DO have company_facts but no research?
    print()
    print("=" * 78)
    print("WHAT ABOUT THE 66 RECORDS WITH company_facts BUT NO research?")
    print("=" * 78)
    with_facts_no_research = [
        r for r in recs
        if r.get("state") == "queued"
        and r.get("company_facts")
        and not r.get("research")
        and not r.get("stages")
    ][:3]
    for rec in with_facts_no_research:
        work = copy.deepcopy(rec)
        facts = work.get("company_facts", {})
        why_before = research.why(work)
        result = qualify.company(work, config, store_result=False)
        verdict = result.get("verdict")
        why_after = research.why(work, verdict=verdict)
        print(f"\n--- {rec['id']} ({rec.get('domain')}) ---")
        print(f"  industry: {facts.get('industry')}, employees: {facts.get('employees')}")
        print(f"  research.why() before: {why_before}")
        print(f"  verdict.icp_status:    {verdict.get('icp_status')}")
        print(f"  research.why(verdict): {why_after}")


if __name__ == "__main__":
    main()
