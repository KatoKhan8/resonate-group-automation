"""TASK-145: Cohort analysis of the queue snapshot.

Reads work/queue.snapshot.jsonl and produces six counts:
  1. Total records
  2. Records with at least one verified email address
  3. Records with at least one contact carrying a bison_lead_id
  4. Cold email cohort: verified email AND no bison_lead_id
  5. Prior-outreach-no-reply cohort: bison_lead_id AND no reply
  6. Unverified email: not in either cohort (no verified email, no bison_lead_id)

Schema notes (discovered from the snapshot):
  - Each line is a JSON object (one record).
  - contacts[] is a list; each contact may have:
      verification.state  - "verified" | "held" | "accept_all_uncleared" | "unknown"
      bison_lead_id       - integer or null/absent
      email               - string or null
  - There is no reply-tracking field anywhere in the snapshot.
    Records with bison_lead_id are therefore all "no reply" by construction:
    the snapshot contains no evidence of a reply for any of them.
"""

import json
import os
import sys


def load_records(snapshot_path):
    """Load all JSONL records from the snapshot file."""
    records = []
    with open(snapshot_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def record_has_verified_email(record):
    """True if any contact has verification.state == 'verified'."""
    for contact in record.get("contacts", []):
        verification = contact.get("verification") or {}
        if verification.get("state") == "verified":
            return True
    return False


def record_has_bison_lead_id(record):
    """True if any contact has a non-null bison_lead_id."""
    for contact in record.get("contacts", []):
        if contact.get("bison_lead_id") is not None:
            return True
    return False


def record_has_reply(record):
    """Check whether the record has any reply evidence.

    The snapshot schema has no dedicated reply field.  We scan the log
    for any step whose name or note contains 'reply' as a defensive
    measure, but as of this snapshot no such entries exist.
    """
    for entry in record.get("log", []):
        step = (entry.get("step") or "").lower()
        note = (entry.get("note") or "").lower()
        if "reply" in step or "replied" in note:
            return True
    return False


def analyse(snapshot_path):
    records = load_records(snapshot_path)
    total = len(records)

    verified_email = 0
    has_bison = 0
    cold_email_cohort = 0        # verified AND no bison
    prior_outreach_no_reply = 0  # bison AND no reply (any verification)
    unverified_neither = 0       # no verified email AND no bison
    verified_and_bison = 0       # overlap: both verified and bison

    for rec in records:
        v = record_has_verified_email(rec)
        b = record_has_bison_lead_id(rec)
        r = record_has_reply(rec)

        if v:
            verified_email += 1
        if b:
            has_bison += 1

        if v and b:
            verified_and_bison += 1
        if v and not b:
            cold_email_cohort += 1
        if b and not r:
            prior_outreach_no_reply += 1
        if not v and not b:
            unverified_neither += 1

    return {
        "total_records": total,
        "verified_email": verified_email,
        "has_bison_lead_id": has_bison,
        "cold_email_cohort": cold_email_cohort,
        "prior_outreach_no_reply": prior_outreach_no_reply,
        "unverified_neither": unverified_neither,
        "verified_and_bison": verified_and_bison,
    }


def main():
    # Resolve path relative to the repository root (one level above scripts/)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(script_dir)
    snapshot_path = os.path.join(repo_root, "work", "queue.snapshot.jsonl")

    if not os.path.exists(snapshot_path):
        print(f"ERROR: snapshot not found at {snapshot_path}", file=sys.stderr)
        sys.exit(1)

    # Read stamp file if available
    stamp_path = os.path.join(repo_root, "work", "queue.snapshot.STAMP")
    stamp = "unknown"
    if os.path.exists(stamp_path):
        with open(stamp_path, encoding="utf-8") as f:
            stamp = f.read().strip()

    results = analyse(snapshot_path)

    print(f"Queue snapshot stamp: {stamp}")
    print(f"Snapshot path: {snapshot_path}")
    print()
    print(f"  1. Total records:                    {results['total_records']}")
    print(f"  2. Verified email:                   {results['verified_email']}")
    print(f"  3. Has bison_lead_id:                {results['has_bison_lead_id']}")
    print(f"  4. Cold email cohort (verified, no bison): {results['cold_email_cohort']}")
    print(f"  5. Prior outreach, no reply (bison, no reply): {results['prior_outreach_no_reply']}")
    print(f"  6. Unverified, neither cohort:       {results['unverified_neither']}")
    print()

    # Sanity: mutually exclusive partition.
    # Every record falls into exactly one of:
    #   (a) has bison, no reply   → prior_outreach_no_reply
    #   (b) has bison, has reply  → bison_with_reply (0 in this snapshot)
    #   (c) no bison, verified    → cold_email_cohort
    #   (d) no bison, not verified→ unverified_neither
    bison_with_reply = results["has_bison_lead_id"] - results["prior_outreach_no_reply"]
    partition_sum = (
        results["prior_outreach_no_reply"]
        + bison_with_reply
        + results["cold_email_cohort"]
        + results["unverified_neither"]
    )
    print(f"  Records with BOTH verified email and bison_lead_id: {results['verified_and_bison']}")
    print(f"  Records with bison AND reply: {bison_with_reply}")
    print(f"  Sanity: prior({results['prior_outreach_no_reply']}) + bison_reply({bison_with_reply}) "
          f"+ cold({results['cold_email_cohort']}) + unverified({results['unverified_neither']}) "
          f"= {partition_sum} (total={results['total_records']}, match={partition_sum == results['total_records']})")


if __name__ == "__main__":
    main()
