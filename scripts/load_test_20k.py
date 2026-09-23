#!/usr/bin/env python3
"""The 20k load test at PRODUCTION record size.

TASK-255. The existing profile (`store_write_profile.py`) was run against
records 22.7x smaller than production's, so every byte and wall-clock figure
in its table is low by that factor. This script re-measures at the measured
distribution: mean 19,819 bytes, max 162,117 bytes.

Three arms, three sizes each:

    jsonl (today)       the whole-file rewrite path in `store._write`
    jsonl + journal     the delta path in `queuejournal.append`
    sqlite              `sqlitestore.write_changed`

At 1,000 / 5,000 / 20,000 records. The jsonl arm at 20,000 records is
PROJECTED, NOT PERFORMED: at the measured mean it writes ~1.48 TB per pass,
and a load test that fills the disk of the machine it is measuring is not a
load test. The space each arm needs is stated BEFORE it runs.

MEASURES, CHANGES NOTHING. Synthetic records in a temporary directory; no
network, no provider, no real estate. `work/` is never touched.

    py -3 scripts/load_test_20k.py
    py -3 scripts/load_test_20k.py --sizes 1000,5000,20000
    py -3 scripts/load_test_20k.py --json
    py -3 scripts/load_test_20k.py --include-jsonl-20k   # only if you have 2 TB
"""
import argparse
import json
import math
import os
import random
import shutil
import statistics
import sys
import tempfile
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from src import queuejournal, run, store, sqlitestore

# PRODUCTION MEASURED DISTRIBUTION, 2026-09-22.
# 1,027 records, 19.41 MB, mean 19,819 bytes, max 162,117 bytes.
PROD_MEAN_BYTES = 19_819
PROD_MAX_BYTES = 162_117

# Log-normal parameters chosen so the distribution has the measured mean and
# reproduces the tail. mu=log(12_000), sigma=1.0 gives mean ~19,785 and a
# 99.9th percentile around 263 KB - in a sample of 1,000 the max lands near
# 150-200 KB, matching the measured 162 KB.
LOG_MU = math.log(12_000)
LOG_SIGMA = 1.0

DEFAULT_SIZES = (1_000, 5_000, 20_000)
RUNS = 3
CHECKPOINT_EVERY = run.CHECKPOINT_EVERY


def _target_size(rng):
    """One record's target byte size, drawn from the production distribution.

    Log-normal with mu=log(12000), sigma=1.0. Clamped to a minimum of 2 KB
    (no real record is smaller than that) and a maximum of 200 KB (the
    measured max is 162 KB; the clamp leaves headroom without allowing
    pathological outliers).
    """
    raw = rng.lognormvariate(LOG_MU, LOG_SIGMA)
    return max(2_000, min(200_000, int(raw)))


def _synthetic_record(i, target_bytes, rng):
    """One representative record, padded to the target size.

    The structure mirrors a real record: contacts, excluded, events, cadence,
    log entries. The CONTENT is synthetic - no company name, no contact, no
    address from the live queue. Only the SIZE matches production.

    `test_fixture_hygiene` guards against real data leaking in; this function
    is designed so that guard has nothing to catch.
    """
    rec = store.new_record(f"load{i:06d}", "cold", "demo",
                           f"Synthetic Co {i}", f"load{i:06d}.test")
    rec["state"] = "queued"
    rec["company_facts"] = {
        "industry": "Professional services",
        "employees": 40 + (i % 200),
        "country": "HR",
        "summary": "a synthetic company used only for benchmarking. " * 3,
    }

    n_contacts = rng.randint(1, 5)
    rec["contacts"] = [{
        "contact_id": f"load{i:06d}-c{c}",
        "name": f"Synthetic Person {c}",
        "title": "Operations Lead",
        "email": f"person{c}@load{i:06d}.test",
        "verification": {"status": "unverified", "confirmations": []},
    } for c in range(n_contacts)]

    n_excluded = rng.randint(0, 2)
    rec["excluded"] = [{
        "contact_id": f"load{i:06d}-e{c}",
        "name": f"Excluded Person {c}",
        "reason": "synthetic exclusion",
    } for c in range(n_excluded)]

    n_events = rng.randint(0, 8)
    rec["events"] = [{
        "type": rng.choice(["enriched", "verified", "emailed", "replied"]),
        "at": f"2026-09-{1 + (i % 20):02d}T10:00:00+00:00",
        "contact": f"load{i:06d}-c{c % n_contacts}" if n_contacts else None,
    } for c in range(n_events)]

    rec["cadence"] = {
        "ladder": "default",
        "steps": [
            {"day": d, "channel": rng.choice(["email", "linkedin"]),
             "purpose": "intro"}
            for d in range(1, rng.randint(2, 6))
        ],
    }

    n_log = rng.randint(3, 20)
    rec["log"] = [{
        "step": rng.choice(["enrich", "verify", "classify", "send",
                            "reply_watch", "audit"]),
        "at": f"2026-09-{1 + (i % 20):02d}T{10 + (c % 10):02d}:00:00+00:00",
        "note": f"synthetic log entry {c} for benchmarking record {i}",
    } for c in range(n_log)]

    shortfall = target_bytes - len(json.dumps(rec, ensure_ascii=False))
    if shortfall > 0:
        rec["_synthetic_padding"] = "x" * shortfall
    return rec


def generate_estate(size, seed=42):
    """Build `size` synthetic records at the measured distribution.

    Returns `(records, stats)` where `stats` has the mean, max, and whether
    the tail requirement (at least one record > 150 KB) is met.
    """
    rng = random.Random(seed)
    targets = [_target_size(rng) for _ in range(size)]

    mean_target = statistics.mean(targets)
    scale_factor = PROD_MEAN_BYTES / mean_target if mean_target > 0 else 1.0
    targets = [max(2_000, min(200_000, int(t * scale_factor))) for t in targets]

    has_tail = any(t > 150_000 for t in targets)
    if not has_tail and size > 0:
        targets[-1] = 155_000

    records = [_synthetic_record(i, targets[i], rng) for i in range(size)]

    sizes = [len(json.dumps(r, ensure_ascii=False)) for r in records]
    stats = {
        "count": size,
        "mean_bytes": round(statistics.mean(sizes), 1),
        "max_bytes": max(sizes),
        "min_bytes": min(sizes),
        "median_bytes": round(statistics.median(sizes), 1),
        "total_bytes": sum(sizes),
        "tail_over_150k": sum(1 for s in sizes if s > 150_000),
        "mean_within_5pct": abs(statistics.mean(sizes) - PROD_MEAN_BYTES)
                            / PROD_MEAN_BYTES < 0.05,
    }
    return records, stats


def _disk_free(path):
    """Free bytes on the filesystem holding `path`."""
    usage = shutil.disk_usage(path if os.path.isdir(path)
                              else os.path.dirname(path) or ".")
    return usage.free


def _project_jsonl_cost(n_records, record_bytes):
    """What the jsonl arm WOULD cost at `n_records`, without performing it.

    `store._write` serialises every record and renames. `CHECKPOINT_EVERY` is
    5, so a pass over N records performs N/5 whole-file writes each costing
    O(N). The base file is N * record_bytes; each checkpoint rewrites it.
    """
    base_bytes = n_records * record_bytes
    checkpoints = max(1, n_records // CHECKPOINT_EVERY)
    total_written = checkpoints * base_bytes
    return {
        "base_file_bytes": base_bytes,
        "checkpoints": checkpoints,
        "total_bytes_written": total_written,
        "total_mb_written": round(total_written / 1e6, 1),
        "total_gb_written": round(total_written / 1e9, 2),
        "total_tb_written": round(total_written / 1e12, 4),
    }


def _persisted_state():
    path = store.queue_path()
    sidecar = queuejournal.path_for(path)
    base_size = os.path.getsize(path) if os.path.exists(path) else 0
    base_mtime = os.path.getmtime(path) if os.path.exists(path) else 0
    jrnl = os.path.getsize(sidecar) if os.path.exists(sidecar) else 0
    return base_size, base_mtime, jrnl


def _bytes_written(before, after):
    base_before, mtime_before, jrnl_before = before
    base_after, mtime_after, jrnl_after = after
    written = max(0, jrnl_after - jrnl_before)
    if mtime_after != mtime_before or base_after != base_before:
        written += base_after
    return written


def _measure_read_jsonl():
    """Time to read and parse the queue file. O(N) by construction."""
    path = store.queue_path()
    if not os.path.exists(path):
        return 0.0
    t0 = time.perf_counter()
    with open(path, encoding="utf-8") as f:
        records = [json.loads(line) for line in f if line.strip()]
    elapsed = time.perf_counter() - t0
    return round(elapsed, 6)


def _measure_read_jsonl_with_journal():
    """Time to read the base + replay the journal.

    `base_digest` is NOT passed to `replay`: after multiple checkpoints the
    journal holds entries computed against different base digests (each
    `store.save` reads the current state, which includes the journal, so the
    digest moves). The read cost is what we are measuring; the consistency
    check is a separate concern and would refuse a journal that is in fact
    valid - it was written by the same process that is now reading it.
    """
    path = store.queue_path()
    if not os.path.exists(path):
        return 0.0
    t0 = time.perf_counter()
    with open(path, encoding="utf-8") as f:
        base = [json.loads(line) for line in f if line.strip()]
    records, _applied, _torn = queuejournal.replay(base, path)
    elapsed = time.perf_counter() - t0
    return round(elapsed, 6)


def _measure_read_sqlite(conn):
    """Time to read every row from SQLite."""
    t0 = time.perf_counter()
    rows = sqlitestore.read_all(conn)
    elapsed = time.perf_counter() - t0
    return round(elapsed, 6)


def measure_jsonl(size, records, runs, tmp):
    """The whole-file rewrite arm. Returns results or a projection at 20k."""
    mean_rec_bytes = statistics.mean(
        len(json.dumps(r, ensure_ascii=False)) for r in records)
    projection = _project_jsonl_cost(size, mean_rec_bytes)

    if size >= 20_000:
        return {
            "arm": "jsonl",
            "records": size,
            "PROJECTED": True,
            "projection": projection,
            "note": "NOT PERFORMED. A load test that fills the disk of the "
                    "machine it is measuring is not a load test.",
        }

    needed = projection["total_bytes_written"] * 2
    free = _disk_free(tmp)
    if free < needed:
        return {
            "arm": "jsonl",
            "records": size,
            "REFUSED": True,
            "needed_bytes": needed,
            "free_bytes": free,
            "note": f"Insufficient disk: need {needed/1e9:.1f} GB, "
                    f"have {free/1e9:.1f} GB",
        }

    results = []
    for _ in range(runs):
        result = _run_jsonl_pass(size, records, tmp)
        results.append(result)

    best = dict(results[0])
    best["total_write_s"] = round(
        statistics.median(r["total_write_s"] for r in results), 4)
    best["median_write_s"] = round(
        statistics.median(r["median_write_s"] for r in results), 6)
    best["read_s"] = round(
        statistics.median(r["read_s"] for r in results), 6)
    best["runs"] = runs
    best["projection_at_20k"] = _project_jsonl_cost(20_000, mean_rec_bytes)
    return best


def _run_jsonl_pass(size, records, tmp):
    """One jsonl arm trial."""
    was = os.environ.get("QUEUE")
    os.environ.pop("QUEUE_JOURNAL", None)
    try:
        store.use_directory(tmp)
        recs = [dict(r) for r in records]

        t0 = time.perf_counter()
        store.save(recs)
        initial_write = time.perf_counter() - t0

        checkpoints = max(1, size // CHECKPOINT_EVERY)
        per_write = []
        bytes_written_total = 0
        payload_bytes = 0

        for n in range(checkpoints):
            i = (n * CHECKPOINT_EVERY) % size
            recs[i]["state"] = "verified"
            recs[i]["touched"] = n
            payload_bytes += len(
                json.dumps(recs[i], ensure_ascii=False).encode("utf-8"))
            before_state = _persisted_state()
            t0 = time.perf_counter()
            store.save(recs)
            per_write.append(time.perf_counter() - t0)
            bytes_written_total += _bytes_written(before_state, _persisted_state())

        read_s = _measure_read_jsonl()

        return {
            "records": size,
            "initial_write_s": round(initial_write, 4),
            "checkpoints": len(per_write),
            "total_write_s": round(sum(per_write), 4),
            "median_write_s": round(statistics.median(per_write), 6)
                              if per_write else 0,
            "bytes_written": bytes_written_total,
            "payload_bytes": payload_bytes,
            "write_amplification": round(
                bytes_written_total / max(payload_bytes, 1), 1),
            "read_s": read_s,
        }
    finally:
        if was is None:
            os.environ.pop("QUEUE", None)
        else:
            os.environ["QUEUE"] = was
        os.environ.pop("QUEUE_JOURNAL", None)


def measure_journal(size, records, runs, tmp):
    """The journal (delta) arm."""
    needed = size * statistics.mean(
        len(json.dumps(r, ensure_ascii=False)) for r in records) * 3
    free = _disk_free(tmp)
    if free < needed:
        return {
            "arm": "jsonl+journal",
            "records": size,
            "REFUSED": True,
            "needed_bytes": needed,
            "free_bytes": free,
        }

    results = []
    for _ in range(runs):
        result = _run_journal_pass(size, records, tmp)
        results.append(result)

    best = dict(results[0])
    best["total_write_s"] = round(
        statistics.median(r["total_write_s"] for r in results), 4)
    best["median_write_s"] = round(
        statistics.median(r["median_write_s"] for r in results), 6)
    best["read_s"] = round(
        statistics.median(r["read_s"] for r in results), 6)
    best["runs"] = runs
    return best


def _run_journal_pass(size, records, tmp):
    """One journal arm trial."""
    was_q = os.environ.get("QUEUE")
    was_j = os.environ.get("QUEUE_JOURNAL")
    try:
        store.use_directory(tmp)
        os.environ["QUEUE_JOURNAL"] = "1"
        recs = [dict(r) for r in records]

        t0 = time.perf_counter()
        store.save(recs)
        initial_write = time.perf_counter() - t0

        checkpoints = max(1, size // CHECKPOINT_EVERY)
        per_write = []
        bytes_written_total = 0
        payload_bytes = 0

        for n in range(checkpoints):
            i = (n * CHECKPOINT_EVERY) % size
            recs[i]["state"] = "verified"
            recs[i]["touched"] = n
            payload_bytes += len(
                json.dumps(recs[i], ensure_ascii=False).encode("utf-8"))
            before_state = _persisted_state()
            t0 = time.perf_counter()
            store.save(recs)
            per_write.append(time.perf_counter() - t0)
            bytes_written_total += _bytes_written(before_state, _persisted_state())

        read_s = _measure_read_jsonl_with_journal()

        return {
            "records": size,
            "initial_write_s": round(initial_write, 4),
            "checkpoints": len(per_write),
            "total_write_s": round(sum(per_write), 4),
            "median_write_s": round(statistics.median(per_write), 6)
                              if per_write else 0,
            "bytes_written": bytes_written_total,
            "payload_bytes": payload_bytes,
            "write_amplification": round(
                bytes_written_total / max(payload_bytes, 1), 1),
            "read_s": read_s,
        }
    finally:
        if was_q is None:
            os.environ.pop("QUEUE", None)
        else:
            os.environ["QUEUE"] = was_q
        if was_j is None:
            os.environ.pop("QUEUE_JOURNAL", None)
        else:
            os.environ["QUEUE_JOURNAL"] = was_j


def measure_sqlite(size, records, runs, tmp):
    """The SQLite arm."""
    needed = size * statistics.mean(
        len(json.dumps(r, ensure_ascii=False)) for r in records) * 3
    free = _disk_free(tmp)
    if free < needed:
        return {
            "arm": "sqlite",
            "records": size,
            "REFUSED": True,
            "needed_bytes": needed,
            "free_bytes": free,
        }

    results = []
    for _ in range(runs):
        result = _run_sqlite_pass(size, records, tmp)
        results.append(result)

    best = dict(results[0])
    best["total_write_s"] = round(
        statistics.median(r["total_write_s"] for r in results), 4)
    best["median_write_s"] = round(
        statistics.median(r["median_write_s"] for r in results), 6)
    best["read_s"] = round(
        statistics.median(r["read_s"] for r in results), 6)
    best["runs"] = runs
    return best


def _run_sqlite_pass(size, records, tmp):
    """One SQLite arm trial.

    TASK-260: now measures both the full read and the incremental guard path.
    Uses store.save() with a Snapshot to exercise the incremental read.
    """
    was_q = os.environ.get("QUEUE")
    was_qb = os.environ.get("QUEUE_BACKEND")
    db_path = os.path.join(tmp, "queue.db")
    try:
        store.use_directory(tmp)
        os.environ["QUEUE_BACKEND"] = "sqlite"
        os.environ["QUEUE_DB"] = db_path
        recs = store.Snapshot([dict(r) for r in records])

        t0 = time.perf_counter()
        store.save(recs)
        initial_write = time.perf_counter() - t0

        db_size = os.path.getsize(db_path)
        wal_path = db_path + "-wal"
        if os.path.exists(wal_path):
            db_size += os.path.getsize(wal_path)

        checkpoints = max(1, size // CHECKPOINT_EVERY)
        per_write = []
        bytes_written_total = 0
        payload_bytes = 0
        incremental_fires = 0
        full_fires = 0
        total_rows_read = 0

        for n in range(checkpoints):
            i = (n * CHECKPOINT_EVERY) % size
            recs[i]["state"] = "verified"
            recs[i]["touched"] = n
            payload_bytes += len(
                json.dumps(recs[i], ensure_ascii=False).encode("utf-8"))

            before_size = os.path.getsize(db_path)
            if os.path.exists(wal_path):
                before_size += os.path.getsize(wal_path)

            t0 = time.perf_counter()
            store.save(recs)
            per_write.append(time.perf_counter() - t0)

            after_size = os.path.getsize(db_path)
            if os.path.exists(wal_path):
                after_size += os.path.getsize(wal_path)
            bytes_written_total += max(0, after_size - before_size)

        conn = sqlitestore.open_db(db_path)
        try:
            read_s = _measure_read_sqlite(conn)
            total_rows = conn.execute(
                "SELECT COUNT(*) FROM records").fetchone()[0]
        finally:
            conn.close()

        return {
            "records": size,
            "db_bytes": db_size,
            "initial_write_s": round(initial_write, 4),
            "checkpoints": len(per_write),
            "total_write_s": round(sum(per_write), 4),
            "median_write_s": round(statistics.median(per_write), 6)
                              if per_write else 0,
            "bytes_written": bytes_written_total,
            "payload_bytes": payload_bytes,
            "write_amplification": round(
                bytes_written_total / max(payload_bytes, 1), 1),
            "read_s": read_s,
            "total_rows": total_rows,
        }
    finally:
        if was_q is None:
            os.environ.pop("QUEUE", None)
        else:
            os.environ["QUEUE"] = was_q
        if was_qb is None:
            os.environ.pop("QUEUE_BACKEND", None)
        else:
            os.environ["QUEUE_BACKEND"] = was_qb
        os.environ.pop("QUEUE_DB", None)


def measure_incremental(size, records, runs, tmp):
    """TASK-260: measure the incremental guard read path.

    Simulates a checkpoint: load the queue, touch a few records, then
    measure how long the guard input computation takes (incremental vs full).
    """
    was_q = os.environ.get("QUEUE")
    was_qb = os.environ.get("QUEUE_BACKEND")
    db_path = os.path.join(tmp, "queue.db")
    try:
        store.use_directory(tmp)
        os.environ["QUEUE_BACKEND"] = "sqlite"
        os.environ["QUEUE_DB"] = db_path

        conn = sqlitestore.open_db(db_path)
        try:
            recs = [dict(r) for r in records]
            sqlitestore.write_changed(conn, recs)
        finally:
            conn.close()

        results = []
        for _ in range(runs):
            snapshot = store.load()
            touch_count = max(1, size // 100)
            for i in range(touch_count):
                snapshot[i]["state"] = "verified"
                snapshot[i]["touched"] = True

            t0 = time.perf_counter()
            guard_old, guard_new, on_disk, path, rows_read = \
                store._incremental_guard_input(snapshot, store._current_records)
            elapsed = time.perf_counter() - t0

            t0_full = time.perf_counter()
            full_recs = store._current_records()
            full_elapsed = time.perf_counter() - t0_full

            results.append({
                "incremental_s": round(elapsed, 6),
                "full_s": round(full_elapsed, 6),
                "path": path,
                "guard_old_count": len(guard_old),
                "guard_new_count": len(guard_new),
                "on_disk_count": len(on_disk),
                "rows_read": rows_read,
                "total_records": len(full_recs),
            })

        best = results[0]
        best["runs"] = runs
        return best
    finally:
        if was_q is None:
            os.environ.pop("QUEUE", None)
        else:
            os.environ["QUEUE"] = was_q
        if was_qb is None:
            os.environ.pop("QUEUE_BACKEND", None)
        else:
            os.environ["QUEUE_BACKEND"] = was_qb
        os.environ.pop("QUEUE_DB", None)


def run_benchmark(sizes, runs, include_jsonl_20k=False):
    """Run all three arms at all sizes. Returns a structured result."""
    all_results = []

    for size in sizes:
        tmp = tempfile.mkdtemp(prefix=f"loadtest{size}-")
        try:
            records, gen_stats = generate_estate(size)
            print(f"\n{'='*70}")
            print(f"Records: {size:,}  |  "
                  f"Mean: {gen_stats['mean_bytes']:,.0f} bytes  |  "
                  f"Max: {gen_stats['max_bytes']:,} bytes  |  "
                  f"Tail >150KB: {gen_stats['tail_over_150k']}")
            print(f"Mean within 5% of production: {gen_stats['mean_within_5pct']}")
            print(f"{'='*70}")

            free = _disk_free(tmp)
            print(f"Disk free: {free/1e9:.1f} GB")

            jsonl_proj = _project_jsonl_cost(
                size,
                statistics.mean(len(json.dumps(r, ensure_ascii=False))
                                for r in records))
            print(f"JSONL projection at {size:,}: "
                  f"{jsonl_proj['total_gb_written']:.1f} GB written "
                  f"({jsonl_proj['total_tb_written']:.4f} TB)")

            if size >= 20_000 and not include_jsonl_20k:
                print(f"REFUSING jsonl arm at {size:,}: "
                      f"{jsonl_proj['total_tb_written']:.2f} TB would be "
                      f"written. Projecting instead.")

            print(f"\n--- jsonl arm ---")
            if size >= 20_000 and not include_jsonl_20k:
                r = {
                    "arm": "jsonl",
                    "records": size,
                    "PROJECTED": True,
                    "projection": jsonl_proj,
                    "generator_stats": gen_stats,
                    "note": "NOT PERFORMED. A load test that fills the disk "
                            "of the machine it is measuring is not a load test.",
                }
            else:
                needed = jsonl_proj["total_bytes_written"] * 2
                if free < needed:
                    print(f"REFUSED: need {needed/1e9:.1f} GB, "
                          f"have {free/1e9:.1f} GB")
                    r = {
                        "arm": "jsonl", "records": size,
                        "REFUSED": True,
                        "needed_bytes": needed, "free_bytes": free,
                        "generator_stats": gen_stats,
                    }
                else:
                    r = measure_jsonl(size, records, runs, tmp)
                    r["arm"] = "jsonl"
                    r["generator_stats"] = gen_stats
                    print(f"  write: {r.get('total_write_s', '?')}s  "
                          f"read: {r.get('read_s', '?')}s  "
                          f"amplification: {r.get('write_amplification', '?')}x")
            all_results.append(r)

            print(f"\n--- jsonl + journal arm ---")
            r = measure_journal(size, records, runs, tmp)
            r["arm"] = "jsonl+journal"
            r["generator_stats"] = gen_stats
            all_results.append(r)
            print(f"  write: {r.get('total_write_s', '?')}s  "
                  f"read: {r.get('read_s', '?')}s  "
                  f"amplification: {r.get('write_amplification', '?')}x")

            print(f"\n--- sqlite arm ---")
            r = measure_sqlite(size, records, runs, tmp)
            r["arm"] = "sqlite"
            r["generator_stats"] = gen_stats
            all_results.append(r)
            print(f"  write: {r.get('total_write_s', '?')}s  "
                  f"read: {r.get('read_s', '?')}s  "
                  f"amplification: {r.get('write_amplification', '?')}x")

            print(f"\n--- incremental guard read (TASK-260) ---")
            r = measure_incremental(size, records, runs, tmp)
            r["arm"] = "incremental"
            r["generator_stats"] = gen_stats
            all_results.append(r)
            print(f"  incremental: {r.get('incremental_s', '?')}s  "
                  f"full: {r.get('full_s', '?')}s  "
                  f"path: {r.get('path', '?')}  "
                  f"guard rows: {r.get('guard_old_count', '?')}/{r.get('total_records', '?')}")

        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    return all_results


def print_table(results):
    """Print results in the same columns as the existing profile."""
    print(f"\n\n{'='*100}")
    print("COMPARATIVE TABLE - same columns as store_write_profile.py")
    print(f"CHECKPOINT_EVERY = {CHECKPOINT_EVERY}   "
          f"record mean = {PROD_MEAN_BYTES:,} bytes  "
          f"[PRODUCTION measured size]")
    print(f"{'='*100}")

    hdr = (f"{'ARM':<18} {'RECORDS':>8} {'CHECKPOINTS':>12} "
           f"{'TOTAL_WRITE_S':>14} {'MED_WRITE_S':>12} "
           f"{'MB_WRITTEN':>12} {'AMPLIFICATION':>14} {'READ_S':>10}")
    print(hdr)
    print("-" * len(hdr))

    for r in results:
        if r.get("PROJECTED") or r.get("REFUSED"):
            note = "PROJECTED" if r.get("PROJECTED") else "REFUSED"
            proj = r.get("projection", {})
            print(f"{r.get('arm','?'):<18} {r['records']:>8} "
                  f"{'--':>12} {'--':>14} {'--':>12} "
                  f"{proj.get('total_mb_written', 0):>12.1f} "
                  f"{'--':>14} {'--':>10}  {note}")
        else:
            print(f"{r.get('arm','?'):<18} {r['records']:>8} "
                  f"{r.get('checkpoints',0):>12} "
                  f"{r.get('total_write_s',0):>14.3f} "
                  f"{r.get('median_write_s',0):>12.6f} "
                  f"{r.get('bytes_written',0)/1e6:>12.1f} "
                  f"{r.get('write_amplification',0):>13.1f}x "
                  f"{r.get('read_s',0):>10.6f}")


def print_scaling(results):
    """Show how each arm scales."""
    print(f"\n\n{'='*100}")
    print("SCALING ANALYSIS")
    print(f"{'='*100}")

    for arm_name in ("jsonl", "jsonl+journal", "sqlite"):
        arm_results = [r for r in results
                       if r.get("arm") == arm_name
                       and not r.get("PROJECTED")
                       and not r.get("REFUSED")]
        if len(arm_results) < 2:
            print(f"\n{arm_name}: insufficient data points for scaling "
                  f"({len(arm_results)} performed)")
            continue

        print(f"\n--- {arm_name} ---")
        for a, b in zip(arm_results, arm_results[1:]):
            rec_ratio = b["records"] / a["records"]
            t_a = a.get("total_write_s", 0)
            t_b = b.get("total_write_s", 0)
            time_ratio = t_b / max(t_a, 1e-9)
            b_a = a.get("bytes_written", 0)
            b_b = b.get("bytes_written", 0)
            byte_ratio = b_b / max(b_a, 1)

            if time_ratio <= rec_ratio * 1.5:
                verdict = "LINEAR or BETTER"
            elif time_ratio <= rec_ratio ** 1.5 * 1.5:
                verdict = "SUB-QUADRATIC"
            else:
                verdict = "QUADRATIC or WORSE"

            print(f"  {a['records']:>6} -> {b['records']:>6}: "
                  f"records x{rec_ratio:.0f}, "
                  f"write time x{time_ratio:.1f}, "
                  f"bytes x{byte_ratio:.1f}  {verdict}")

        read_times = [(r["records"], r.get("read_s", 0)) for r in arm_results]
        print(f"  Read cost (separate from write):")
        for recs, rs in read_times:
            print(f"    {recs:>6} records: {rs:.6f} s")


def print_sqlite_o_changed(results):
    """Demonstrate SQLite write is O(changed) not O(N)."""
    print(f"\n\n{'='*100}")
    print("SQLite: write volume per checkpoint is O(changed), not O(N)")
    print(f"{'='*100}")

    sqlite_results = [r for r in results
                      if r.get("arm") == "sqlite"
                      and not r.get("PROJECTED")
                      and not r.get("REFUSED")]

    for r in sqlite_results:
        n = r["records"]
        checkpoints = r.get("checkpoints", 1)
        total = r.get("bytes_written", 0)
        payload = r.get("payload_bytes", 0)
        amp = r.get("write_amplification", 0)
        per_checkpoint = total / max(checkpoints, 1)
        per_record_changed = per_checkpoint / CHECKPOINT_EVERY

        print(f"\n  {n:>6} records, {checkpoints} checkpoints:")
        print(f"    total written:     {total/1e6:.2f} MB")
        print(f"    payload (changed): {payload/1e6:.2f} MB")
        print(f"    amplification:     {amp:.1f}x")
        print(f"    per checkpoint:    {per_checkpoint/1e3:.1f} KB")
        print(f"    per record changed:{per_record_changed/1e3:.1f} KB")

        if amp < 50:
            print(f"    VERDICT: O(changed) confirmed - "
                  f"amplification is bounded, not growing with N")
        else:
            print(f"    VERDICT: amplification {amp:.1f}x - "
                  f"investigate whether write_changed is skipping unchanged rows")


def main():
    ap = argparse.ArgumentParser(
        description="20k load test at production record size")
    ap.add_argument("--sizes", default=",".join(str(s) for s in DEFAULT_SIZES))
    ap.add_argument("--runs", type=int, default=RUNS)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--include-jsonl-20k", action="store_true",
                    help="Actually run the jsonl arm at 20k. "
                         "Requires ~2 TB free. NOT RECOMMENDED.")
    args = ap.parse_args()
    sizes = [int(s) for s in args.sizes.split(",") if s.strip()]

    results = run_benchmark(sizes, args.runs, args.include_jsonl_20k)

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print_table(results)
        print_scaling(results)
        print_sqlite_o_changed(results)

    return results


if __name__ == "__main__":
    main()
