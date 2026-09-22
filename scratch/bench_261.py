"""Benchmark: pass wall clock at 1k and 5k records on sqlite.

TASK-261. A pass is N/5 checkpoints, 5 records changed per checkpoint,
every one going through store.save() with the full guard path. Records are
generated at realistic size (~20 KB mean).

Usage:
    py -3 scratch/bench_261.py [N]

Detached, no timeout wrapper. The 5k arm takes ~25 minutes at the old
shape; should be much faster with dirty tracking.
"""
import json
import os
import random
import sys
import tempfile
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

os.environ["QUEUE_BACKEND"] = "sqlite"


def make_record(rid, rng):
    """A realistic record at the measured production mean (~19,819 bytes)."""
    n_contacts = rng.randint(1, 4)
    contacts = []
    for ci in range(n_contacts):
        n_evidence = rng.randint(1, 3)
        evidence = []
        for ei in range(n_evidence):
            evidence.append({
                "email": f"person-{rid}-{ci}@example{ei}.com",
                "provider": rng.choice(["reo", "deliverable", "contactout"]),
                "status": rng.choice(["valid", "risky", "invalid"]),
                "at": f"2026-09-{rng.randint(1,22):02d}T{rng.randint(0,23):02d}:00:00+00:00",
                "extra_data": "x" * rng.randint(50, 500),
            })
        contacts.append({
            "key": f"{rid}:person-{ci}",
            "name": f"Person {ci} of {rid}",
            "email": f"person-{rid}-{ci}@example.com",
            "title": rng.choice(["CEO", "CTO", "VP Sales", "Head of Growth"]),
            "verification": {
                "evidence": evidence,
                "status": rng.choice(["valid", "risky"]),
            },
            "linkedin": f"linkedin.com/in/person-{rid}-{ci}",
            "phone": f"+1-555-{rng.randint(1000,9999)}",
            "extra_fields": {"notes": "y" * rng.randint(20, 200)},
        })
    n_events = rng.randint(2, 10)
    events = []
    for ei in range(n_events):
        events.append({
            "id": f"evt-{rid}-{ei}",
            "type": rng.choice(["ingested", "enriched", "verified",
                                 "draft_generated", "push_prepared"]),
            "contact": f"{rid}:person-{rng.randint(0, n_contacts-1)}",
            "at": f"2026-09-{rng.randint(1,22):02d}T{rng.randint(0,23):02d}:00:00+00:00",
            "details": {"data": "z" * rng.randint(20, 300)},
        })
    n_log = rng.randint(2, 8)
    log_entries = []
    for li in range(n_log):
        log_entries.append({
            "step": rng.choice(["queued", "enriched", "verified", "drafted"]),
            "at": f"2026-09-{rng.randint(1,22):02d}T{rng.randint(0,23):02d}:00:00+00:00",
            "note": f"log entry {li} for {rid}: " + "w" * rng.randint(10, 100),
        })
    cadence = {}
    for day in range(1, rng.randint(2, 6)):
        cadence[f"day{day}"] = {
            "body": "Hello " + "body text " * rng.randint(5, 30),
            "subject": f"Subject for day {day} of {rid}",
            "step": rng.choice(["em1", "em2", "li1", "li2"]),
        }
    padding = "padding_" + "p" * rng.randint(5000, 15000)
    return {
        "id": rid,
        "lane": rng.choice(["revive", "cold", "domains"]),
        "client": "productive",
        "company": f"Company {rid} Inc.",
        "domain": f"{rid}.example.com",
        "context": f"Context for {rid}: " + "c" * rng.randint(50, 300),
        "signal": f"Signal for {rid}: " + "s" * rng.randint(20, 100),
        "state": "queued",
        "drop_reason": None,
        "company_facts": {
            "employees": rng.randint(10, 10000),
            "revenue": f"${rng.randint(1, 100)}M",
            "industry": rng.choice(["SaaS", "Fintech", "HealthTech"]),
            "description": "Company desc " * rng.randint(5, 20),
        },
        "contacts": contacts,
        "excluded": [],
        "diagnosis": {"score": rng.randint(0, 100), "tier": "A"},
        "hook": f"Hook for {rid}: " + "h" * rng.randint(20, 100),
        "sizing": {"fit": rng.choice(["small", "medium", "large"])},
        "cadence": cadence,
        "events": events,
        "log": log_entries,
        "_padding": padding,
    }


def run_pass(n_records):
    """One pass: load, walk N records changing 5 each, checkpoint every 5."""
    from src import store

    tmp = tempfile.mkdtemp(prefix=f"bench_261_{n_records}_")
    store.use_directory(tmp)
    db_path = os.path.join(tmp, "queue.db")
    os.environ["QUEUE_DB"] = db_path

    rng = random.Random(42)

    # Generate and ingest records
    records = [make_record(f"rec-{i:05d}", rng) for i in range(n_records)]
    store.append(records)

    # Now simulate a pass: load, walk, change 5 per checkpoint
    recs = store.load()
    t0 = time.time()
    n_checkpoints = 0
    for idx, rec in enumerate(recs):
        # Mutate this record
        rec["state"] = "enriched"
        rec["contacts"][0]["verification"]["status"] = "valid"
        rec["log"].append({
            "step": "enriched",
            "at": "2026-09-22T12:00:00+00:00",
            "note": f"enriched pass at {idx}",
        })

        # Checkpoint every 5
        if (idx + 1) % 5 == 0:
            store.save(recs)
            n_checkpoints += 1

    elapsed = time.time() - t0
    return elapsed, n_checkpoints


def main():
    sizes = [1000, 5000]
    if len(sys.argv) > 1:
        sizes = [int(x) for x in sys.argv[1:]]

    results = []
    for n in sizes:
        print(f"Running {n} records...", flush=True)
        elapsed, checkpoints = run_pass(n)
        print(f"  {n} records: {elapsed:.2f}s ({checkpoints} checkpoints)",
              flush=True)
        results.append((n, elapsed, checkpoints))

    print("\nSummary:", flush=True)
    base_s, base_t = results[0][0], results[0][1]
    for n, elapsed, checkpoints in results:
        ratio = elapsed / base_t if base_t > 0 else 0
        record_ratio = n / base_s
        print(f"  {n:>6} records: {elapsed:>10.2f}s  "
              f"ratio vs {base_s}: {ratio:.1f}x  "
              f"(record ratio: {record_ratio:.1f}x, "
              f"checkpoints: {checkpoints})", flush=True)


if __name__ == "__main__":
    main()
