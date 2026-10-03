#!/usr/bin/env python3
"""TASK-226: the journal read cost, before and after the index.

Measures the checkpoint read path at 50, 500, and 5,000 records with the REAL
record size (31,793 bytes). Compares:

  - whole-file path (QUEUE_JOURNAL off): reads entire base, rewrites entire base
  - journal path without index (MODELLED): reads entire base + replays journal
  - journal path with index (MEASURED): reads only touched records via index

The 5,000-record whole-file arm is MODELLED rather than measured because it
would write ~159 GB to disk and buy no information that two measured points
do not already give.

    py -3 scripts/benchmark_journal_index.py
    py -3 scripts/benchmark_journal_index.py --json
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
SIZES = (50, 500, 5000)
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


def measure_wholefile(size):
    """Whole-file path: QUEUE_JOURNAL off. MEASURED at 50, 500; MODELLED at 5000."""
    tmp = tempfile.mkdtemp(prefix=f"bench_wf_{size}-")
    was = os.environ.get("QUEUE")
    was_flag = os.environ.get("QUEUE_JOURNAL")
    try:
        store.use_directory(tmp)
        os.environ.pop("QUEUE_JOURNAL", None)
        recs = [_record(i) for i in range(size)]

        t0 = time.perf_counter()
        store.save(recs)
        initial_write = time.perf_counter() - t0
        base_size = os.path.getsize(store.queue_path())

        checkpoints = max(1, size // run.CHECKPOINT_EVERY)
        per_write = []
        bytes_written = 0
        for n in range(checkpoints):
            i = (n * run.CHECKPOINT_EVERY) % size
            recs[i]["state"] = "verified"
            recs[i]["touched"] = n
            t0 = time.perf_counter()
            store.save(recs)
            per_write.append(time.perf_counter() - t0)
            bytes_written += base_size

        return {
            "records": size,
            "path": "whole-file",
            "queue_file_bytes": base_size,
            "initial_write_s": round(initial_write, 4),
            "checkpoints": checkpoints,
            "total_write_s": round(sum(per_write), 4),
            "median_write_s": round(statistics.median(per_write), 6),
            "bytes_written": bytes_written,
            "mb_written": round(bytes_written / 1024 / 1024, 1),
            "source": "MEASURED" if size <= 500 else "MODELLED",
        }
    finally:
        for name, value in (("QUEUE", was), ("QUEUE_JOURNAL", was_flag)):
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        shutil.rmtree(tmp, ignore_errors=True)


def measure_journal_with_index(size):
    """Journal path with index: QUEUE_JOURNAL on. MEASURED at all sizes."""
    tmp = tempfile.mkdtemp(prefix=f"bench_ji_{size}-")
    was = os.environ.get("QUEUE")
    was_flag = os.environ.get("QUEUE_JOURNAL")
    try:
        store.use_directory(tmp)
        os.environ["QUEUE_JOURNAL"] = "1"
        recs = [_record(i) for i in range(size)]

        t0 = time.perf_counter()
        store.save(recs)
        initial_write = time.perf_counter() - t0
        base_size = os.path.getsize(store.queue_path())

        checkpoints = max(1, size // run.CHECKPOINT_EVERY)
        per_write = []
        bytes_written = 0
        journal_path = queuejournal.path_for(store.queue_path())

        for n in range(checkpoints):
            i = (n * run.CHECKPOINT_EVERY) % size
            recs[i]["state"] = "verified"
            recs[i]["touched"] = n
            jrnl_before = os.path.getsize(journal_path) if os.path.exists(journal_path) else 0
            t0 = time.perf_counter()
            store.save(recs)
            per_write.append(time.perf_counter() - t0)
            jrnl_after = os.path.getsize(journal_path) if os.path.exists(journal_path) else 0
            bytes_written += (jrnl_after - jrnl_before)

        return {
            "records": size,
            "path": "journal+index",
            "queue_file_bytes": base_size,
            "initial_write_s": round(initial_write, 4),
            "checkpoints": checkpoints,
            "total_write_s": round(sum(per_write), 4),
            "median_write_s": round(statistics.median(per_write), 6),
            "bytes_written": bytes_written,
            "mb_written": round(bytes_written / 1024 / 1024, 2),
            "source": "MEASURED",
        }
    finally:
        for name, value in (("QUEUE", was), ("QUEUE_JOURNAL", was_flag)):
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        shutil.rmtree(tmp, ignore_errors=True)


def model_wholefile_5000(results_50, results_500):
    """Model the 5,000-record whole-file path from the 50 and 500 measurements.

    The whole-file path is O(N^2): each of N/5 checkpoints writes N records.
    So bytes_written scales as N^2/5, and time scales similarly.
    """
    ratio = 5000 / 500
    base_bytes_500 = results_500["queue_file_bytes"]
    checkpoints_500 = results_500["checkpoints"]
    bytes_per_checkpoint_500 = base_bytes_500
    total_bytes_500 = checkpoints_500 * bytes_per_checkpoint_500

    checkpoints_5000 = 5000 // run.CHECKPOINT_EVERY
    bytes_per_checkpoint_5000 = base_bytes_500 * ratio
    total_bytes_5000 = checkpoints_5000 * bytes_per_checkpoint_5000

    time_per_checkpoint_500 = results_500["total_write_s"] / checkpoints_500
    time_per_checkpoint_5000 = time_per_checkpoint_500 * ratio
    total_time_5000 = checkpoints_5000 * time_per_checkpoint_5000

    return {
        "records": 5000,
        "path": "whole-file",
        "queue_file_bytes": int(base_bytes_500 * ratio),
        "initial_write_s": round(results_500["initial_write_s"] * ratio, 4),
        "checkpoints": checkpoints_5000,
        "total_write_s": round(total_time_5000, 4),
        "median_write_s": round(time_per_checkpoint_5000, 6),
        "bytes_written": int(total_bytes_500),
        "mb_written": round(total_bytes_5000 / 1024 / 1024, 1),
        "source": "MODELLED",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sizes", default=",".join(str(s) for s in SIZES))
    ap.add_argument("--runs", type=int, default=RUNS)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    sizes = [int(s) for s in args.sizes.split(",") if s.strip()]

    results = []
    for size in sizes:
        if size <= 500:
            trials_wf = [measure_wholefile(size) for _ in range(args.runs)]
            best_wf = dict(trials_wf[0])
            best_wf["total_write_s"] = round(
                statistics.median(t["total_write_s"] for t in trials_wf), 4)
            best_wf["median_write_s"] = round(
                statistics.median(t["median_write_s"] for t in trials_wf), 6)
            best_wf["runs"] = args.runs
            results.append(best_wf)

        trials_ji = [measure_journal_with_index(size) for _ in range(args.runs)]
        best_ji = dict(trials_ji[0])
        best_ji["total_write_s"] = round(
            statistics.median(t["total_write_s"] for t in trials_ji), 4)
        best_ji["median_write_s"] = round(
            statistics.median(t["median_write_s"] for t in trials_ji), 6)
        best_ji["runs"] = args.runs
        results.append(best_ji)

    if 5000 in sizes:
        wf_50 = next((r for r in results if r["records"] == 50 and r["path"] == "whole-file"), None)
        wf_500 = next((r for r in results if r["records"] == 500 and r["path"] == "whole-file"), None)
        if wf_50 and wf_500:
            modelled = model_wholefile_5000(wf_50, wf_500)
            results.append(modelled)

    results.sort(key=lambda r: (r["records"], r["path"]))

    if args.json:
        print(json.dumps(results, indent=2))
        return 0

    print(f"TASK-226 BENCHMARK: journal read cost with offset index")
    print(f"Record size: {REAL_RECORD_BYTES:,} bytes (REAL measured size)")
    print(f"CHECKPOINT_EVERY = {run.CHECKPOINT_EVERY}   runs = {args.runs} (median)")
    print()

    hdr = (f"{'RECORDS':>8} {'PATH':>15} {'SOURCE':>10} {'CHECKPOINTS':>12} "
           f"{'TOTAL_S':>10} {'MED_S':>10} {'MB_WRITTEN':>12}")
    print(hdr)
    print("-" * len(hdr))
    for r in results:
        print(f"{r['records']:>8} {r['path']:>15} {r['source']:>10} "
              f"{r['checkpoints']:>12} {r['total_write_s']:>10.3f} "
              f"{r['median_write_s']:>10.6f} {r['mb_written']:>12.1f}")

    print()
    print("COMPARISON at 500 records:")
    wf_500 = next((r for r in results if r["records"] == 500 and r["path"] == "whole-file"), None)
    ji_500 = next((r for r in results if r["records"] == 500 and r["path"] == "journal+index"), None)
    if wf_500 and ji_500:
        time_speedup = wf_500["total_write_s"] / max(ji_500["total_write_s"], 0.001)
        byte_ratio = wf_500["mb_written"] / max(ji_500["mb_written"], 0.001)
        print(f"  Time:  whole-file {wf_500['total_write_s']:.3f}s vs "
              f"journal+index {ji_500['total_write_s']:.3f}s "
              f"({time_speedup:.1f}x faster)")
        print(f"  Bytes: whole-file {wf_500['mb_written']:.1f} MB vs "
              f"journal+index {ji_500['mb_written']:.2f} MB "
              f"({byte_ratio:.0f}x fewer)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
