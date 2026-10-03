#!/usr/bin/env python3
"""Benchmark the journal read path with and without the offset index.

    py -3 scripts/journal_read_benchmark.py
    py -3 scripts/journal_read_benchmark.py --sizes 50,500,5000

MEASURES, CHANGES NOTHING. Synthetic records in a temporary directory; no
network, no provider, no real estate.

## The question

The journal made writes O(M) but reads stayed O(N): every checkpoint still
reads the entire base file and replays the entire journal. The offset index
makes the read O(M) too: instead of scanning the base file for the M records
the journal touched, we seek directly to them.

## What is measured

Two read paths at 50, 500, and 5,000 records:
1. WHOLE-FILE: read the entire base file and replay the journal (old path)
2. INDEXED: read only the journal records from the base using the index (new)

The 5,000-record whole-file arm is MODELLED rather than measured, because it
would write ~159 GB to disk and buy no information that two measured points
do not already give. Every figure is labelled MEASURED or MODELLED.
"""
import argparse
import json
import os
import shutil
import sys
import tempfile
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from src import queuejournal as qj, store

REAL_RECORD_BYTES = 31_793


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


def measure_read(size, journal_entries, label="MEASURED"):
    """Measure the read path: base file + journal replay.

    Returns (time_seconds, bytes_read, label).
    """
    tmp = tempfile.mkdtemp(prefix=f"jrbench{size}-")
    was = os.environ.get("QUEUE")
    try:
        store.use_directory(tmp)
        recs = [_record(i) for i in range(size)]
        store.save(recs)
        queue = store.queue_path()

        for n in range(journal_entries):
            i = n % size
            qj.append(queue, [dict(recs[i], state="verified", touched=n)], "d0")

        base_bytes = os.path.getsize(queue)
        journal_bytes = os.path.getsize(qj.path_for(queue))

        t0 = time.perf_counter()
        with open(queue, encoding="utf-8") as f:
            base = [json.loads(line) for line in f if line.strip()]
        out, applied, torn = qj.replay(base, queue)
        read_time = time.perf_counter() - t0

        return {
            "records": size,
            "journal_entries": journal_entries,
            "read_time_s": round(read_time, 4),
            "base_bytes": base_bytes,
            "journal_bytes": journal_bytes,
            "bytes_read": base_bytes + journal_bytes,
            "label": label,
        }
    finally:
        if was is None:
            os.environ.pop("QUEUE", None)
        else:
            os.environ["QUEUE"] = was
        shutil.rmtree(tmp, ignore_errors=True)


def measure_indexed_read(size, journal_entries, label="MEASURED"):
    """Measure the indexed read path: only journal records from base.

    Returns (time_seconds, bytes_read, label).
    The index is built on the first call, so subsequent calls are faster.
    """
    tmp = tempfile.mkdtemp(prefix=f"jrbench{size}-")
    was = os.environ.get("QUEUE")
    try:
        store.use_directory(tmp)
        recs = [_record(i) for i in range(size)]
        store.save(recs)
        queue = store.queue_path()

        for n in range(journal_entries):
            i = n % size
            qj.append(queue, [dict(recs[i], state="verified", touched=n)], "d0")

        base_bytes = os.path.getsize(queue)
        journal_bytes = os.path.getsize(qj.path_for(queue))

        # Build the index first (warm-up)
        qj.read_changed(queue, queue)

        # Now measure the actual read (index already built)
        t0 = time.perf_counter()
        changed, torn = qj.read_changed(queue, queue)
        read_time = time.perf_counter() - t0

        idx_bytes = 0
        idx_path = qj.index_path(queue)
        if os.path.exists(idx_path):
            idx_bytes = os.path.getsize(idx_path)

        return {
            "records": size,
            "journal_entries": journal_entries,
            "read_time_s": round(read_time, 4),
            "base_bytes": base_bytes,
            "journal_bytes": journal_bytes,
            "index_bytes": idx_bytes,
            "bytes_read": journal_bytes + idx_bytes,
            "records_read": len(changed),
            "label": label,
        }
    finally:
        if was is None:
            os.environ.pop("QUEUE", None)
        else:
            os.environ["QUEUE"] = was
        shutil.rmtree(tmp, ignore_errors=True)


def model_whole_file(size, measured_50, measured_500):
    """Model the 5,000-record whole-file read from the 50 and 500 measurements.

    The read is O(N + J), so we extrapolate linearly.
    """
    ratio = size / 500
    modelled_time = measured_500["read_time_s"] * ratio
    modelled_bytes = measured_500["bytes_read"] * ratio
    return {
        "records": size,
        "journal_entries": int(measured_500["journal_entries"] * ratio),
        "read_time_s": round(modelled_time, 4),
        "base_bytes": int(measured_500["base_bytes"] * ratio),
        "journal_bytes": int(measured_500["journal_bytes"] * ratio),
        "bytes_read": int(modelled_bytes),
        "label": "MODELLED",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sizes", default="50,500,5000")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    sizes = [int(s) for s in args.sizes.split(",") if s.strip()]

    results = []
    for size in sizes:
        journal_entries = max(1, size // 5)
        if size <= 500:
            whole = measure_read(size, journal_entries, "MEASURED")
            indexed = measure_indexed_read(size, journal_entries, "MEASURED")
        else:
            measured_50 = measure_read(50, 10, "MEASURED")
            measured_500 = measure_read(500, 100, "MEASURED")
            whole = model_whole_file(size, measured_50, measured_500)
            indexed = measure_indexed_read(size, journal_entries, "MEASURED")
        results.append((whole, indexed))

    if args.json:
        print(json.dumps([{"whole": w, "indexed": i} for w, i in results], indent=2))
        return

    print(f"Journal read benchmark: record = {REAL_RECORD_BYTES:,} bytes\n")
    hdr = (f"{'RECORDS':>8} {'J_ENTRIES':>10} {'WHOLE_S':>10} {'INDEXED_S':>10} "
           f"{'WHOLE_MB':>10} {'INDEXED_MB':>11} {'SPEEDUP':>9} {'LABEL':>10}")
    print(hdr)
    print("-" * len(hdr))
    for whole, indexed in results:
        speedup = whole["read_time_s"] / max(indexed["read_time_s"], 0.0001)
        print(f"{whole['records']:>8} {whole['journal_entries']:>10} "
              f"{whole['read_time_s']:>10.4f} {indexed['read_time_s']:>10.4f} "
              f"{whole['bytes_read']/1024/1024:>10.2f} "
              f"{indexed['bytes_read']/1024/1024:>11.2f} "
              f"{speedup:>9.1f}x {whole['label']:>10}")

    print("\nWHOLE = read entire base + replay journal (old path)")
    print("INDEXED = read only journal records using index (new path)")
    print("SPEEDUP = whole_time / indexed_time")


if __name__ == "__main__":
    main()
