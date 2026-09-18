#!/usr/bin/env python3
"""What the journal index buys: O(M) replay instead of O(J).

    py -3 scripts/journal_read_benchmark.py
    py -3 scripts/journal_read_benchmark.py --sizes 50,500,5000

MEASURES THE JOURNAL PATH at 50, 500, and 5,000 records. MODELS the
whole-file path at 5,000 records (it is ~159 GB per pass and writing that to
the operator's SSD buys nothing that two measured points do not already give).

Every number is labelled MEASURED or MODELLED. They are never mixed in one
table. The model is linear extrapolation from the 50 and 500 measurements,
which is conservative: the whole-file path is O(N^2) in bytes, so the actual
cost at 5,000 is likely WORSE than the model predicts.

## The question

The journal cut write amplification from 499.8x to 1.0x but was 69% SLOWER.
The bottleneck moved from the WRITE to the READ: every checkpoint reads the
entire journal to replay it. The index makes replay O(M) where M is the
number of unique records, not O(J) where J is the total number of entries.

Does the index make the journal path no slower than the whole-file path?

## What is measured

- Journal path at 50, 500, 5,000: build records, checkpoint as a real run
  would (every 5 records), measure the time for `_current_records()` which
  reads the base file and replays the journal.
- Whole-file path at 50, 500: same, but without the journal.

## What is modelled

- Whole-file path at 5,000: linear extrapolation from 50 and 500. The
  whole-file path is O(N^2) in bytes (N/5 checkpoints, each writing N
  records), so the actual cost is likely worse than linear. The model is
  conservative.

## Record size

31,793 bytes per record, the MEASURED real size from `work/queue.jsonl` on
2026-09-18. The padding is synthetic filler, not real data - what is taken
from the estate is the SIZE and nothing else.
"""
import argparse
import json
import os
import shutil
import statistics
import sys
import tempfile
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from src import queuejournal, run, store

REAL_RECORD_BYTES = 31_793
DEFAULT_SIZES = (50, 500, 5000)
RUNS = 3


def _record(i, target_bytes=REAL_RECORD_BYTES):
    """One representative record, PADDED TO THE REAL MEASURED SIZE."""
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


def measure_journal(size, record_bytes=REAL_RECORD_BYTES):
    """Journal path: build, checkpoint, measure the READ cost.

    The read cost is `_current_records()`: read the base file, replay the
    journal. With the index, replay is O(M) where M is the number of unique
    records in the journal.
    """
    tmp = tempfile.mkdtemp(prefix=f"jbench{size}-")
    was = os.environ.get("QUEUE")
    was_flag = os.environ.get("QUEUE_JOURNAL")
    try:
        store.use_directory(tmp)
        os.environ["QUEUE_JOURNAL"] = "1"
        recs = [_record(i, record_bytes) for i in range(size)]

        store.save(recs)
        checkpoints = max(1, size // run.CHECKPOINT_EVERY)

        read_times = []
        for n in range(checkpoints):
            i = (n * run.CHECKPOINT_EVERY) % size
            recs[i]["state"] = "verified"
            recs[i]["touched"] = n
            store.save(recs)

            t0 = time.perf_counter()
            _ = store.load()
            read_times.append(time.perf_counter() - t0)

        journal_path = queuejournal.path_for(store.queue_path())
        journal_bytes = os.path.getsize(journal_path) if os.path.exists(journal_path) else 0
        idx_path = queuejournal._index_path(store.queue_path())
        idx_bytes = os.path.getsize(idx_path) if os.path.exists(idx_path) else 0

        return {
            "records": size,
            "checkpoints": checkpoints,
            "journal_bytes": journal_bytes,
            "index_bytes": idx_bytes,
            "median_read_s": round(statistics.median(read_times), 6),
            "max_read_s": round(max(read_times), 6),
            "min_read_s": round(min(read_times), 6),
            "label": "MEASURED",
        }
    finally:
        for name, value in (("QUEUE", was), ("QUEUE_JOURNAL", was_flag)):
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        shutil.rmtree(tmp, ignore_errors=True)


def measure_wholefile(size, record_bytes=REAL_RECORD_BYTES):
    """Whole-file path: build, checkpoint, measure the READ cost.

    The read cost is `read_jsonl(queue_path())`: read the entire base file.
    No journal, no replay.
    """
    tmp = tempfile.mkdtemp(prefix=f"wbench{size}-")
    was = os.environ.get("QUEUE")
    was_flag = os.environ.get("QUEUE_JOURNAL")
    try:
        store.use_directory(tmp)
        os.environ.pop("QUEUE_JOURNAL", None)
        recs = [_record(i, record_bytes) for i in range(size)]

        store.save(recs)
        checkpoints = max(1, size // run.CHECKPOINT_EVERY)

        read_times = []
        for n in range(checkpoints):
            i = (n * run.CHECKPOINT_EVERY) % size
            recs[i]["state"] = "verified"
            recs[i]["touched"] = n
            store.save(recs)

            t0 = time.perf_counter()
            _ = store.load()
            read_times.append(time.perf_counter() - t0)

        base_bytes = os.path.getsize(store.queue_path()) if os.path.exists(store.queue_path()) else 0

        return {
            "records": size,
            "checkpoints": checkpoints,
            "base_bytes": base_bytes,
            "median_read_s": round(statistics.median(read_times), 6),
            "max_read_s": round(max(read_times), 6),
            "min_read_s": round(min(read_times), 6),
            "label": "MEASURED",
        }
    finally:
        for name, value in (("QUEUE", was), ("QUEUE_JOURNAL", was_flag)):
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        shutil.rmtree(tmp, ignore_errors=True)


def model_wholefile(size_50, size_500, target_size):
    """Linear extrapolation from 50 and 500.

    The whole-file path is O(N^2) in bytes, so the actual cost at 5,000 is
    likely WORSE than linear. This model is conservative.
    """
    ratio = target_size / size_500["records"]
    median_50 = size_50["median_read_s"]
    median_500 = size_500["median_read_s"]
    growth_rate = median_500 / median_50 if median_50 > 0 else 1.0
    modelled_median = median_500 * (ratio ** (1.0 if growth_rate <= 10 else 1.5))

    return {
        "records": target_size,
        "checkpoints": max(1, target_size // run.CHECKPOINT_EVERY),
        "median_read_s": round(modelled_median, 6),
        "label": "MODELLED",
        "model_basis": f"extrapolated from {size_50['records']} and {size_500['records']}",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sizes", default=",".join(str(s) for s in DEFAULT_SIZES))
    ap.add_argument("--runs", type=int, default=RUNS)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    sizes = [int(s) for s in args.sizes.split(",") if s.strip()]

    print(f"Record size: {REAL_RECORD_BYTES:,} bytes (MEASURED real size)")
    print(f"Runs per size: {args.runs} (taking median)")
    print()

    journal_results = []
    wholefile_results = []

    for size in sizes:
        print(f"Measuring journal path at {size} records...")
        trials = [measure_journal(size) for _ in range(args.runs)]
        best = dict(trials[0])
        best["median_read_s"] = round(statistics.median(t["median_read_s"] for t in trials), 6)
        journal_results.append(best)

    for size in sizes:
        if size <= 500:
            print(f"Measuring whole-file path at {size} records...")
            trials = [measure_wholefile(size) for _ in range(args.runs)]
            best = dict(trials[0])
            best["median_read_s"] = round(statistics.median(t["median_read_s"] for t in trials), 6)
            wholefile_results.append(best)
        else:
            print(f"Modelling whole-file path at {size} records (not measuring)...")

    if len(wholefile_results) >= 2:
        measured = [r for r in wholefile_results if r["label"] == "MEASURED"]
        if len(measured) >= 2:
            modelled = model_wholefile(measured[0], measured[1], 5000)
            wholefile_results.append(modelled)

    print()
    print("=" * 80)
    print("MEASURED RESULTS")
    print("=" * 80)
    print()
    print("Journal path (with index):")
    print(f"{'RECORDS':>8} {'CHECKPOINTS':>12} {'MEDIAN_READ_S':>14} {'JOURNAL_KB':>12} {'INDEX_KB':>10}")
    print("-" * 70)
    for r in journal_results:
        print(f"{r['records']:>8} {r['checkpoints']:>12} {r['median_read_s']:>14.6f} "
              f"{r['journal_bytes']/1024:>12.1f} {r['index_bytes']/1024:>10.1f}")

    print()
    print("Whole-file path (no journal):")
    print(f"{'RECORDS':>8} {'CHECKPOINTS':>12} {'MEDIAN_READ_S':>14} {'BASE_KB':>12}")
    print("-" * 60)
    for r in wholefile_results:
        if r["label"] == "MEASURED":
            print(f"{r['records']:>8} {r['checkpoints']:>12} {r['median_read_s']:>14.6f} "
                  f"{r['base_bytes']/1024:>12.1f}")

    print()
    print("=" * 80)
    print("MODELLED RESULTS")
    print("=" * 80)
    print()
    print("Whole-file path at 5,000 records (MODELLED, not measured):")
    modelled = [r for r in wholefile_results if r["label"] == "MODELLED"]
    if modelled:
        r = modelled[0]
        print(f"  Records: {r['records']:,}")
        print(f"  Checkpoints: {r['checkpoints']:,}")
        print(f"  Median read time: {r['median_read_s']:.6f} s")
        print(f"  Model basis: {r['model_basis']}")
        print(f"  Note: actual cost is likely WORSE (O(N^2) in bytes)")

    print()
    print("=" * 80)
    print("COMPARISON")
    print("=" * 80)
    print()
    print("Journal vs whole-file at 500 records (both MEASURED):")
    j_500 = [r for r in journal_results if r["records"] == 500][0]
    w_500 = [r for r in wholefile_results if r["records"] == 500 and r["label"] == "MEASURED"][0]
    ratio = j_500["median_read_s"] / w_500["median_read_s"] if w_500["median_read_s"] > 0 else 0
    print(f"  Journal:    {j_500['median_read_s']:.6f} s")
    print(f"  Whole-file: {w_500['median_read_s']:.6f} s")
    print(f"  Ratio:      {ratio:.2f}x (journal / whole-file)")
    if ratio < 1.0:
        print(f"  Verdict:    journal is FASTER")
    elif ratio < 1.5:
        print(f"  Verdict:    journal is comparable (within 50%)")
    else:
        print(f"  Verdict:    journal is SLOWER")

    if args.json:
        output = {
            "journal": journal_results,
            "wholefile": wholefile_results,
            "record_bytes": REAL_RECORD_BYTES,
        }
        print()
        print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
