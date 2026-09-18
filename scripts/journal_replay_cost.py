#!/usr/bin/env python3
"""Isolated replay cost: how long does `load()` take with a journal of N entries?

    py -3 scripts/journal_replay_cost.py

Builds a journal with a known number of entries, then measures the cost of
`store.load()` which reads the base and replays the journal. This isolates
the READ cost from the WRITE cost.

## What is measured

- Journal replay at 50, 500, 5,000 entries: build a journal with that many
  entries (touching M unique records), measure `store.load()`.
- Whole-file read at 50, 500, 5,000 records: build a base file with that many
  records, measure `store.load()`.

## Record size

31,793 bytes per record, the MEASURED real size.
"""
import json
import os
import shutil
import sys
import tempfile
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from src import queuejournal, store

REAL_RECORD_BYTES = 31_793


def _record(i, target_bytes=REAL_RECORD_BYTES):
    rec = store.new_record(f"perf{i:06d}", "cold", "demo",
                           f"Perf Co {i}", f"perf{i:06d}.test")
    rec["state"] = "queued"
    rec["company_facts"] = {
        "industry": "Professional services",
        "employees": 40 + (i % 200),
        "country": "HR",
        "summary": "a synthetic company used only for benchmarking. " * 3,
    }
    rec["contacts"] = [{
        "contact_id": f"perf{i:06d}-c{c}",
        "name": f"Synthetic Person {c}",
        "title": "Operations Lead",
        "email": f"person{c}@perf{i:06d}.test",
        "verification": {"status": "unverified", "confirmations": []},
    } for c in range(2)]
    shortfall = target_bytes - len(json.dumps(rec, ensure_ascii=False))
    if shortfall > 0:
        rec["_synthetic_padding"] = "x" * shortfall
    return rec


def measure_journal_replay(num_entries, unique_records):
    """Build a journal with `num_entries` touching `unique_records` records.

    Measure the cost of `store.load()` which replays the journal.
    """
    tmp = tempfile.mkdtemp(prefix=f"jreplay{num_entries}-")
    was = os.environ.get("QUEUE")
    was_flag = os.environ.get("QUEUE_JOURNAL")
    try:
        store.use_directory(tmp)
        os.environ["QUEUE_JOURNAL"] = "1"

        recs = [_record(i) for i in range(unique_records)]
        store.save(recs)

        for n in range(num_entries):
            i = n % unique_records
            recs[i]["touched"] = n
            recs[i]["state"] = "verified" if n % 2 == 0 else "queued"
            store.save(recs)

        journal_path = queuejournal.path_for(store.queue_path())
        journal_bytes = os.path.getsize(journal_path)
        idx_path = queuejournal._index_path(store.queue_path())
        idx_bytes = os.path.getsize(idx_path) if os.path.exists(idx_path) else 0

        times = []
        for _ in range(5):
            t0 = time.perf_counter()
            _ = store.load()
            times.append(time.perf_counter() - t0)

        return {
            "journal_entries": num_entries,
            "unique_records": unique_records,
            "journal_bytes": journal_bytes,
            "index_bytes": idx_bytes,
            "median_load_s": round(sorted(times)[2], 6),
            "label": "MEASURED",
        }
    finally:
        for name, value in (("QUEUE", was), ("QUEUE_JOURNAL", was_flag)):
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        shutil.rmtree(tmp, ignore_errors=True)


def measure_wholefile_read(num_records):
    """Build a base file with `num_records` records. Measure `store.load()`."""
    tmp = tempfile.mkdtemp(prefix=f"wread{num_records}-")
    was = os.environ.get("QUEUE")
    was_flag = os.environ.get("QUEUE_JOURNAL")
    try:
        store.use_directory(tmp)
        os.environ.pop("QUEUE_JOURNAL", None)

        recs = [_record(i) for i in range(num_records)]
        store.save(recs)

        base_bytes = os.path.getsize(store.queue_path())

        times = []
        for _ in range(5):
            t0 = time.perf_counter()
            _ = store.load()
            times.append(time.perf_counter() - t0)

        return {
            "records": num_records,
            "base_bytes": base_bytes,
            "median_load_s": round(sorted(times)[2], 6),
            "label": "MEASURED",
        }
    finally:
        for name, value in (("QUEUE", was), ("QUEUE_JOURNAL", was_flag)):
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    print(f"Record size: {REAL_RECORD_BYTES:,} bytes (MEASURED real size)")
    print()

    print("Measuring journal replay cost...")
    journal_results = []
    for entries, unique in [(50, 50), (500, 500), (5000, 5000)]:
        print(f"  {entries} entries, {unique} unique records...")
        result = measure_journal_replay(entries, unique)
        journal_results.append(result)

    print()
    print("Measuring whole-file read cost...")
    wholefile_results = []
    for num in [50, 500, 5000]:
        print(f"  {num} records...")
        result = measure_wholefile_read(num)
        wholefile_results.append(result)

    print()
    print("=" * 80)
    print("MEASURED RESULTS")
    print("=" * 80)
    print()
    print("Journal replay (with index):")
    print(f"{'ENTRIES':>8} {'UNIQUE':>8} {'MED_LOAD_S':>12} {'JOURNAL_KB':>12} {'INDEX_KB':>10}")
    print("-" * 60)
    for r in journal_results:
        print(f"{r['journal_entries']:>8} {r['unique_records']:>8} "
              f"{r['median_load_s']:>12.6f} "
              f"{r['journal_bytes']/1024:>12.1f} {r['index_bytes']/1024:>10.1f}")

    print()
    print("Whole-file read (no journal):")
    print(f"{'RECORDS':>8} {'MED_LOAD_S':>12} {'BASE_KB':>12}")
    print("-" * 40)
    for r in wholefile_results:
        print(f"{r['records']:>8} {r['median_load_s']:>12.6f} "
              f"{r['base_bytes']/1024:>12.1f}")

    print()
    print("=" * 80)
    print("COMPARISON")
    print("=" * 80)
    print()
    for j, w in zip(journal_results, wholefile_results):
        ratio = j["median_load_s"] / w["median_load_s"] if w["median_load_s"] > 0 else 0
        print(f"At {j['journal_entries']:>5} entries / {w['records']:>5} records:")
        print(f"  Journal:    {j['median_load_s']:.6f} s")
        print(f"  Whole-file: {w['median_load_s']:.6f} s")
        print(f"  Ratio:      {ratio:.2f}x")
        if ratio < 1.0:
            print(f"  Verdict:    journal is FASTER")
        elif ratio < 1.5:
            print(f"  Verdict:    journal is comparable (within 50%)")
        else:
            print(f"  Verdict:    journal is SLOWER")
        print()


if __name__ == "__main__":
    main()
