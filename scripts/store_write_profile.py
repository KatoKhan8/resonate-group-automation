#!/usr/bin/env python3
"""What one record's change costs when the store rewrites the whole cohort.

    py -3 scripts/store_write_profile.py
    py -3 scripts/store_write_profile.py --sizes 50,500,5000

MEASURES, CHANGES NOTHING. Synthetic records in a temporary directory; no
network, no provider, no real estate. `store.use_directory` points every state
file at a temp dir, so this cannot touch `work/`.

## The question

`store._write` serialises EVERY record to a temp file and renames it, and
`run.CHECKPOINT_EVERY` is 5. So a run over N records performs N/5 whole-file
writes, and each one costs O(N). That is O(N^2) bytes for a single pass -
architecturally. This script turns that into numbers, because "it is
quadratic" and "it costs 63 TB at 100k" are different claims and only the
second one justifies work.

## What is deliberately NOT measured here

Provider latency. Every number below is OUR overhead with no network in the
path, which is the part we control and the part that does not get faster when
a vendor does.

## Reading the output

`BYTES_WRITTEN` is bytes that actually reached the filesystem, taken from the
file size at each write rather than from `len(json.dumps(...))` - the record
in memory and the row on disk are not the same size and the disk one is what
costs.

`WRITE_AMPLIFICATION` is the honest headline: bytes written divided by bytes
of actual change. Writing one 700-byte record should cost ~700 bytes. It does
not.
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


def _persisted_state():
    """`(base_size, base_mtime, journal_size)` - enough to tell what MOVED."""
    path = store.queue_path()
    sidecar = queuejournal.path_for(path)
    base_size = os.path.getsize(path) if os.path.exists(path) else 0
    base_mtime = os.path.getmtime(path) if os.path.exists(path) else 0
    jrnl = os.path.getsize(sidecar) if os.path.exists(sidecar) else 0
    return base_size, base_mtime, jrnl


def _bytes_written(before, after):
    """Bytes THIS checkpoint actually put on disk.

    TWO EARLIER VERSIONS OF THIS WERE WRONG, IN OPPOSITE DIRECTIONS, AND BOTH
    LOOKED PLAUSIBLE.

    Measuring `getsize(queue_path())` after each save was right only while
    every save rewrote the whole file. Journalling stops the base moving, so
    it reported 446 KB per checkpoint whether the write had cost 446 KB or
    900 bytes - the optimisation was invisible.

    Summing base+journal SIZE after each save was worse: it charges every
    checkpoint for the whole accumulated journal, so the delta path measured
    547x against the whole-file path's 492x. The delta path was winning and
    the instrument said it was losing.

    What a checkpoint writes is: the base file IF it was rewritten, plus
    however much the journal GREW. A rewrite is detected by mtime or size
    moving, because a rewrite of identical content is still a write.
    """
    base_before, mtime_before, jrnl_before = before
    base_after, mtime_after, jrnl_after = after
    written = max(0, jrnl_after - jrnl_before)
    if mtime_after != mtime_before or base_after != base_before:
        written += base_after
    return written

DEFAULT_SIZES = (50, 500, 5000)
RUNS = 3

# HOW BIG A REAL RECORD IS, MEASURED RATHER THAN IMAGINED.
#
# `work/queue.jsonl` on 2026-09-18: 17,486,311 bytes over 550 records =
# 31,793 bytes each. The synthetic record this script started with was 859
# bytes, so every byte figure it produced was **37x optimistic** - GLM's
# storage review caught it, and it had already been published.
#
# The padding below is synthetic filler, not real data. What is taken from
# the estate is the SIZE and nothing else: no company, no contact, no address.
REAL_RECORD_BYTES = 31_793


def _record(i, target_bytes=REAL_RECORD_BYTES):
    """One representative record, PADDED TO THE REAL MEASURED SIZE.

    Representative means representative in the dimension that costs: bytes.
    A record a thirty-seventh of the real size makes every write look cheap
    and makes the whole-file path look survivable, which is exactly the
    mistake this padding removes.
    """
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
    # Pad to the measured size. The evidence a real record carries - provider
    # answers, crawl results, timelines - is what makes it 31.8 KB, and the
    # cost of that is bytes on disk regardless of their content.
    shortfall = target_bytes - len(json.dumps(rec, ensure_ascii=False))
    if shortfall > 0:
        rec["_synthetic_padding"] = "x" * shortfall
    return rec


def measure(size, record_bytes=REAL_RECORD_BYTES):
    """One pass: build `size` records, then checkpoint as a real run would."""
    tmp = tempfile.mkdtemp(prefix=f"perfstore{size}-")
    # `use_directory` takes no "put it back" argument, so the restore is the
    # caller's job. Without it a later measurement - or anything else in this
    # process - keeps writing to a deleted temp directory.
    was = os.environ.get("QUEUE")
    try:
        store.use_directory(tmp)
        recs = [_record(i, record_bytes) for i in range(size)]

        t0 = time.perf_counter()
        store.save(recs)
        initial_write = time.perf_counter() - t0
        base_size, _m, _j = _persisted_state()
        file_bytes = base_size

        # The cost of ONE record changing, measured `size` times over - which
        # is what a pipeline pass does, one record at a time.
        per_write = []
        bytes_written = 0
        writes = 0
        payload_bytes = 0

        checkpoints = max(1, size // run.CHECKPOINT_EVERY)
        for n in range(checkpoints):
            i = (n * run.CHECKPOINT_EVERY) % size
            recs[i]["state"] = "verified"
            recs[i]["touched"] = n
            payload_bytes += len(
                json.dumps(recs[i], ensure_ascii=False).encode("utf-8"))
            before_state = _persisted_state()
            t0 = time.perf_counter()
            store.save(recs)
            per_write.append(time.perf_counter() - t0)
            bytes_written += _bytes_written(before_state, _persisted_state())
            writes += 1

        return {
            "records": size,
            "queue_file_bytes": file_bytes,
            "initial_write_s": round(initial_write, 4),
            "checkpoints": writes,
            "checkpoint_every": run.CHECKPOINT_EVERY,
            "total_write_s": round(sum(per_write), 4),
            "median_write_s": round(statistics.median(per_write), 6),
            "bytes_written": bytes_written,
            "payload_bytes": payload_bytes,
            "write_amplification": round(bytes_written / max(payload_bytes, 1), 1),
            "bytes_per_record_changed": round(bytes_written / max(writes, 1)),
        }
    finally:
        if was is None:
            os.environ.pop("QUEUE", None)
        else:
            os.environ["QUEUE"] = was
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sizes", default=",".join(str(s) for s in DEFAULT_SIZES))
    ap.add_argument("--runs", type=int, default=RUNS)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--record-bytes", type=int, default=REAL_RECORD_BYTES,
                    dest="record_bytes",
                    help=f"bytes per synthetic record (default "
                         f"{REAL_RECORD_BYTES}, the measured real size)")
    args = ap.parse_args()
    sizes = [int(s) for s in args.sizes.split(",") if s.strip()]

    results = []
    for size in sizes:
        trials = [measure(size, args.record_bytes) for _ in range(args.runs)]
        best = dict(trials[0])
        best["total_write_s"] = round(
            statistics.median(t["total_write_s"] for t in trials), 4)
        best["median_write_s"] = round(
            statistics.median(t["median_write_s"] for t in trials), 6)
        best["runs"] = args.runs
        results.append(best)

    if args.json:
        print(json.dumps(results, indent=2))
        return

    print(f"CHECKPOINT_EVERY = {run.CHECKPOINT_EVERY}   runs = {args.runs} "
          f"(median)   record = {args.record_bytes:,} bytes"
          + ("  [REAL measured size]" if args.record_bytes == REAL_RECORD_BYTES
             else "  [NOT the real size]"))
    print()
    hdr = (f"{'RECORDS':>8} {'QUEUE_KB':>10} {'CHECKPOINTS':>12} "
           f"{'TOTAL_WRITE_S':>14} {'MED_WRITE_S':>12} {'MB_WRITTEN':>12} "
           f"{'AMPLIFICATION':>14}")
    print(hdr)
    print("-" * len(hdr))
    for r in results:
        print(f"{r['records']:>8} {r['queue_file_bytes']/1024:>10.1f} "
              f"{r['checkpoints']:>12} {r['total_write_s']:>14.3f} "
              f"{r['median_write_s']:>12.6f} "
              f"{r['bytes_written']/1024/1024:>12.1f} "
              f"{r['write_amplification']:>13.1f}x")

    print()
    print("SCALING - is the cost of a pass linear in the cohort?")
    for a, b in zip(results, results[1:]):
        rec_ratio = b["records"] / a["records"]
        time_ratio = b["total_write_s"] / max(a["total_write_s"], 1e-9)
        byte_ratio = b["bytes_written"] / max(a["bytes_written"], 1)
        verdict = "LINEAR" if time_ratio <= rec_ratio * 1.5 else "WORSE THAN LINEAR"
        print(f"  {a['records']} -> {b['records']}: records x{rec_ratio:.0f}, "
              f"write time x{time_ratio:.1f}, bytes x{byte_ratio:.1f}  {verdict}")

    print()
    print("A record changing should cost about its own size. Measured cost of")
    print("one changed record, by cohort size:")
    for r in results:
        print(f"  {r['records']:>6} records: "
              f"{r['bytes_per_record_changed']/1024:.1f} KB written per "
              f"record changed")


if __name__ == "__main__":
    main()
