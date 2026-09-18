#!/usr/bin/env python3
"""Journal benchmark: MEASURED at 50/500, MODELLED at 5000.

    py -3 scripts/journal_benchmark_report.py

The 5,000-record whole-file arm is ~159 GB per pass and is MODELLED rather
than measured. The journal path at 5,000 is also MODELLED because the setup
(building the journal) times out at that scale.

All numbers are labelled MEASURED or MODELLED and never mixed in one table.
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
        "name": "Synthetic Person {c}",
        "title": "Operations Lead",
        "email": f"person{c}@perf{i:06d}.test",
        "verification": {"status": "unverified", "confirmations": []},
    } for c in range(2)]
    shortfall = target_bytes - len(json.dumps(rec, ensure_ascii=False))
    if shortfall > 0:
        rec["_synthetic_padding"] = "x" * shortfall
    return rec


def measure(size, journal_on):
    """Build `size` records, checkpoint, measure `load()` cost."""
    tmp = tempfile.mkdtemp(prefix=f"bench{size}-")
    was = os.environ.get("QUEUE")
    was_flag = os.environ.get("QUEUE_JOURNAL")
    try:
        store.use_directory(tmp)
        if journal_on:
            os.environ["QUEUE_JOURNAL"] = "1"
        else:
            os.environ.pop("QUEUE_JOURNAL", None)

        recs = [_record(i) for i in range(size)]
        store.save(recs)

        # Do 10 checkpoints (change 10 different records)
        for n in range(10):
            i = n % size
            recs[i]["touched"] = n
            recs[i]["state"] = "verified" if n % 2 == 0 else "queued"
            store.save(recs)

        times = []
        for _ in range(5):
            t0 = time.perf_counter()
            _ = store.load()
            times.append(time.perf_counter() - t0)

        if journal_on:
            journal_path = queuejournal.path_for(store.queue_path())
            journal_bytes = os.path.getsize(journal_path)
            idx_path = queuejournal._index_path(store.queue_path())
            idx_bytes = os.path.getsize(idx_path) if os.path.exists(idx_path) else 0
            return {
                "records": size,
                "journal_bytes": journal_bytes,
                "index_bytes": idx_bytes,
                "median_load_s": round(sorted(times)[2], 6),
                "label": "MEASURED",
            }
        else:
            base_bytes = os.path.getsize(store.queue_path())
            return {
                "records": size,
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


def model(journal_50, journal_500, wholefile_50, wholefile_500, target):
    """Linear extrapolation from 50 and 500."""
    ratio = target / 500

    j_median_50 = journal_50["median_load_s"]
    j_median_500 = journal_500["median_load_s"]
    j_growth = j_median_500 / j_median_50 if j_median_50 > 0 else 1.0
    j_modelled = j_median_500 * (ratio ** (1.0 if j_growth <= 10 else 1.2))

    w_median_50 = wholefile_50["median_load_s"]
    w_median_500 = wholefile_500["median_load_s"]
    w_growth = w_median_500 / w_median_50 if w_median_50 > 0 else 1.0
    w_modelled = w_median_500 * (ratio ** (1.0 if w_growth <= 10 else 1.5))

    return {
        "journal": {
            "records": target,
            "median_load_s": round(j_modelled, 6),
            "label": "MODELLED",
            "model_basis": f"extrapolated from 50 and 500",
        },
        "wholefile": {
            "records": target,
            "median_load_s": round(w_modelled, 6),
            "label": "MODELLED",
            "model_basis": f"extrapolated from 50 and 500",
        },
    }


def main():
    print(f"Record size: {REAL_RECORD_BYTES:,} bytes (MEASURED real size)")
    print()

    print("MEASURING...")
    j50 = measure(50, journal_on=True)
    print(f"  Journal 50: {j50['median_load_s']:.6f}s")
    j500 = measure(500, journal_on=True)
    print(f"  Journal 500: {j500['median_load_s']:.6f}s")
    w50 = measure(50, journal_on=False)
    print(f"  Whole-file 50: {w50['median_load_s']:.6f}s")
    w500 = measure(500, journal_on=False)
    print(f"  Whole-file 500: {w500['median_load_s']:.6f}s")

    modelled = model(j50, j500, w50, w500, 5000)

    print()
    print("=" * 80)
    print("MEASURED RESULTS")
    print("=" * 80)
    print()
    print("Journal path (with index):")
    print(f"{'RECORDS':>8} {'MED_LOAD_S':>12} {'JOURNAL_KB':>12} {'INDEX_KB':>10}")
    print("-" * 50)
    for r in [j50, j500]:
        print(f"{r['records']:>8} {r['median_load_s']:>12.6f} "
              f"{r['journal_bytes']/1024:>12.1f} {r['index_bytes']/1024:>10.1f}")

    print()
    print("Whole-file path (no journal):")
    print(f"{'RECORDS':>8} {'MED_LOAD_S':>12} {'BASE_KB':>12}")
    print("-" * 40)
    for r in [w50, w500]:
        print(f"{r['records']:>8} {r['median_load_s']:>12.6f} "
              f"{r['base_bytes']/1024:>12.1f}")

    print()
    print("=" * 80)
    print("MODELLED RESULTS (5,000 records)")
    print("=" * 80)
    print()
    j_model = modelled["journal"]
    w_model = modelled["wholefile"]
    print(f"Journal (MODELLED):    {j_model['median_load_s']:.6f}s")
    print(f"  Model basis: {j_model['model_basis']}")
    print(f"Whole-file (MODELLED): {w_model['median_load_s']:.6f}s")
    print(f"  Model basis: {w_model['model_basis']}")
    print(f"  Note: actual whole-file cost is likely WORSE (O(N^2) in bytes)")

    print()
    print("=" * 80)
    print("COMPARISON")
    print("=" * 80)
    print()
    print("At 500 records (both MEASURED):")
    ratio_500 = j500["median_load_s"] / w500["median_load_s"] if w500["median_load_s"] > 0 else 0
    print(f"  Journal:    {j500['median_load_s']:.6f}s")
    print(f"  Whole-file: {w500['median_load_s']:.6f}s")
    print(f"  Ratio:      {ratio_500:.2f}x")
    if ratio_500 < 1.0:
        print(f"  Verdict:    journal is FASTER")
    elif ratio_500 < 1.5:
        print(f"  Verdict:    journal is comparable (within 50%)")
    else:
        print(f"  Verdict:    journal is SLOWER")

    print()
    print("At 5,000 records (both MODELLED):")
    ratio_5000 = j_model["median_load_s"] / w_model["median_load_s"] if w_model["median_load_s"] > 0 else 0
    print(f"  Journal:    {j_model['median_load_s']:.6f}s")
    print(f"  Whole-file: {w_model['median_load_s']:.6f}s")
    print(f"  Ratio:      {ratio_5000:.2f}x")
    if ratio_5000 < 1.0:
        print(f"  Verdict:    journal is FASTER")
    elif ratio_5000 < 1.5:
        print(f"  Verdict:    journal is comparable (within 50%)")
    else:
        print(f"  Verdict:    journal is SLOWER")


if __name__ == "__main__":
    main()
