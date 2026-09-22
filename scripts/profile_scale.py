#!/usr/bin/env python3
"""TASK-040: what gets slow first, and at what size.

Measures LOCAL operations against synthetic estates at 300, 1K, 5K and 30K
records, plus models the PROVIDER pagination cost based on measured EmailBison
behaviour (15 rows per page, per_page ignored, offset pagination refused with
422 beyond ~500 pages).

Nothing here calls a network or a provider. Provider pagination is MODELLED
from measured facts, not measured live. The measured facts are:

  - EmailBison returns exactly 15 rows per page on every route, regardless
    of per_page (probed 2026-09-13 on campaign 352)
  - Campaign 352 holds ~95,000 scheduled emails -> ~6,400 sequential pages
  - Joining a reply to its step costs one additional request per reply
  - Offset pagination is refused with 422 beyond ~500 pages

The snapshot stamp is quoted in the result block. companies.dataset() builds
a SYNTHETIC estate and is labelled as such throughout.

  python -m scripts.profile_scale
  python scripts/profile_scale.py
"""
import json
import os
import shutil
import statistics
import sys
import tempfile
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from src import (benchmark, cadence, companies, funnel, personalization,
                 store, synthetic)

SIZES = (300, 1_000, 5_000, 30_000)
RUNS_PER_SIZE = 3


def _memory_mb():
    """Resident memory. None if the platform will not say."""
    try:
        import resource
        return round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)
    except Exception:
        try:
            import ctypes
            import ctypes.wintypes

            class Counters(ctypes.Structure):
                _fields_ = [("cb", ctypes.wintypes.DWORD),
                            ("PageFaultCount", ctypes.wintypes.DWORD),
                            ("PeakWorkingSetSize", ctypes.c_size_t),
                            ("WorkingSetSize", ctypes.c_size_t),
                            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                            ("PagefileUsage", ctypes.c_size_t),
                            ("PeakPagefileUsage", ctypes.c_size_t)]

            counters = Counters()
            counters.cb = ctypes.sizeof(counters)
            handle = ctypes.windll.kernel32.GetCurrentProcess()
            if ctypes.windll.psapi.GetProcessMemoryInfo(
                    handle, ctypes.byref(counters), counters.cb):
                return round(counters.WorkingSetSize / (1024 * 1024), 1)
        except Exception:
            return None
    return None


def _make_estate(size, tmp):
    """Build a synthetic estate of `size` records in a temp directory.

    Uses companies.dataset() which is SYNTHETIC - 21 archetypes cycled
    deterministically. Labelled as such throughout.
    """
    store.use_directory(tmp)
    recs = companies.dataset(size, client="benchmark", batch="profile")
    store.save(recs)
    return recs


def _time(fn, runs=RUNS_PER_SIZE):
    """Run `fn` multiple times, return (median_seconds, all_times)."""
    times = []
    for _ in range(runs):
        start = time.perf_counter()
        fn()
        times.append(time.perf_counter() - start)
    return statistics.median(times), times


def profile_store_load(size, recs, tmp):
    """store.load: read and parse the whole JSONL file."""
    store.use_directory(tmp)
    store.save(recs)

    def do_load():
        store.load()

    median, all_times = _time(do_load)
    return {"median_s": round(median, 4), "all_s": [round(t, 4) for t in all_times]}


def profile_store_save(size, recs, tmp):
    """store.save: write the whole JSONL file atomically."""
    store.use_directory(tmp)

    def do_save():
        store.save(recs)

    median, all_times = _time(do_save)
    return {"median_s": round(median, 4), "all_s": [round(t, 4) for t in all_times]}


def profile_refuse_history_loss(size, recs, tmp):
    """refuse_history_loss: the guard that runs on every save via transaction."""
    store.use_directory(tmp)
    store.save(recs)

    def do_check():
        # EXEMPT: profiles the raw read_jsonl primitive that refuse_history_loss
        # takes in production (store.save passes it the un-replayed base file).
        # Switching to store.load() would measure a Snapshot with journal replay,
        # which is a different operation and would invalidate the measurement.
        on_disk = store.read_jsonl(store.queue_path())
        store.refuse_history_loss(on_disk, recs)

    median, all_times = _time(do_check)
    return {"median_s": round(median, 4), "all_s": [round(t, 4) for t in all_times]}


def profile_funnel(size, recs, tmp):
    """funnel.counts + funnel.attrition: the whole funnel computation."""
    store.use_directory(tmp)

    def do_funnel():
        funnel.counts(recs)
        funnel.attrition(recs)

    median, all_times = _time(do_funnel)
    return {"median_s": round(median, 4), "all_s": [round(t, 4) for t in all_times]}


def profile_cadence_steps_for(size, recs, tmp):
    """cadence.steps_for across every record in the estate."""
    config = {}

    def do_steps():
        for rec in recs:
            cadence.steps_for(config=config, rec=rec)

    median, all_times = _time(do_steps)
    return {"median_s": round(median, 4), "all_s": [round(t, 4) for t in all_times]}


def profile_personalization(size, recs, tmp):
    """personalization.selected_contacts + personalization.plan across estate."""
    config = _load_config()

    def do_plan():
        for rec in recs:
            personalization.selected_contacts(rec, config)
            personalization.plan(rec, config)

    median, all_times = _time(do_plan)
    return {"median_s": round(median, 4), "all_s": [round(t, 4) for t in all_times]}


def profile_snapshot_merge(size, recs, tmp):
    """Snapshot.merge_onto: the three-way merge that runs on every save
    when recs came from load(). This is the cost of a checkpoint."""
    store.use_directory(tmp)
    store.save(recs)
    snap = store.load()

    def do_merge():
        # EXEMPT: profiles the raw merge_onto primitive against the on-disk
        # base file, which is what store.save passes it. Switching to
        # store.load() would feed it an already-merged Snapshot and the
        # measurement would no longer reflect the checkpoint cost.
        on_disk = store.read_jsonl(store.queue_path())
        snap.merge_onto(on_disk)

    median, all_times = _time(do_merge)
    return {"median_s": round(median, 4), "all_s": [round(t, 4) for t in all_times]}


def profile_transaction(size, recs, tmp):
    """The full transaction: lock + load + yield + guards + write.
    This is what run.checkpoint, enrich.run and inbound.ingest all take."""
    store.use_directory(tmp)
    store.save(recs)

    def do_transaction():
        with store.transaction() as recs_tx:
            pass

    median, all_times = _time(do_transaction)
    return {"median_s": round(median, 4), "all_s": [round(t, 4) for t in all_times]}


def _load_config():
    """Load a client config for personalization. Falls back to empty dict."""
    try:
        from src import clients
        return clients.load("demo")
    except Exception:
        return {}


def model_provider_pagination():
    """Model the EmailBison pagination cost from measured facts.

    MEASURED FACTS (probed 2026-09-13 on the live estate):
    - Every route returns exactly 15 rows per page (per_page ignored)
    - Campaign 352: ~95,000 scheduled emails -> ~6,400 pages
    - Offset pagination refused with 422 beyond ~500 pages
    - Joining a reply to its step: one GET /scheduled-emails/{id} per reply

    We model at campaign sizes: 1K, 5K, 20K, 50K, 95K scheduled emails.
    """
    PAGE_SIZE = 15
    LATENCY_PER_REQUEST = 0.3  # seconds - conservative for a simple GET

    sizes = [1_000, 5_000, 20_000, 50_000, 95_000]
    results = []
    for n in sizes:
        pages = (n + PAGE_SIZE - 1) // PAGE_SIZE
        walk_seconds = pages * LATENCY_PER_REQUEST
        results.append({
            "scheduled_emails": n,
            "pages_needed": pages,
            "walk_seconds": round(walk_seconds, 1),
            "walk_minutes": round(walk_seconds / 60, 1),
            "walk_hours": round(walk_seconds / 3600, 2),
            "within_500_page_limit": pages <= 500,
        })

    # Reply-to-step join cost
    reply_counts = [100, 500, 2_000, 5_000, 10_000]
    reply_results = []
    for n_replies in reply_counts:
        join_seconds = n_replies * LATENCY_PER_REQUEST
        reply_results.append({
            "replies": n_replies,
            "requests": n_replies,
            "join_seconds": round(join_seconds, 1),
            "join_minutes": round(join_seconds / 60, 1),
        })

    return {
        "campaign_walk": results,
        "reply_step_join": reply_results,
        "assumptions": {
            "page_size": PAGE_SIZE,
            "latency_per_request_s": LATENCY_PER_REQUEST,
            "offset_limit_pages": 500,
            "source": "probed 2026-09-13 on campaign 352",
        }
    }


def _shape_label(times_by_size):
    """Determine the complexity shape from the timing data.

    Compare the growth rate to known shapes:
    - Linear: doubling size -> ~2x time
    - Quadratic: doubling size -> ~4x time
    - Sub-linear: doubling size -> <1.5x time
    """
    sizes = sorted(times_by_size.keys())
    if len(sizes) < 2:
        return "unknown"

    ratios = []
    for i in range(1, len(sizes)):
        size_ratio = sizes[i] / sizes[i-1]
        time_ratio = times_by_size[sizes[i]] / max(times_by_size[sizes[i-1]], 0.0001)
        ratios.append((size_ratio, time_ratio))

    avg_time_ratio = statistics.geometric_mean([t for _, t in ratios])
    avg_size_ratio = statistics.geometric_mean([s for s, _ in ratios])

    # Compare to linear (ratio ~1.0 when normalized)
    normalized = avg_time_ratio / avg_size_ratio

    if normalized < 0.7:
        return "sub-linear"
    elif normalized < 1.5:
        return "linear"
    elif normalized < 3.0:
        return "between linear and quadratic"
    else:
        return "quadratic or worse"


def run_full_profile():
    """Run the full profiling suite across all sizes."""
    results = {}

    for size in SIZES:
        print(f"\n{'='*60}")
        print(f"Profiling estate size: {size:,} records (SYNTHETIC)")
        print(f"{'='*60}")

        tmp = tempfile.mkdtemp(prefix=f"profile_{size}_")
        try:
            # Build the estate
            start = time.perf_counter()
            recs = _make_estate(size, tmp)
            build_time = time.perf_counter() - start
            file_size = os.path.getsize(store.queue_path())
            print(f"  Built {len(recs)} records in {build_time:.2f}s")
            print(f"  Queue file size: {file_size:,} bytes "
                  f"({file_size/1024/1024:.1f} MB)")

            mem = _memory_mb()
            if mem:
                print(f"  Memory: {mem:.0f} MB")

            results[size] = {
                "records": len(recs),
                "file_bytes": file_size,
                "file_mb": round(file_size / 1024 / 1024, 2),
                "build_time_s": round(build_time, 3),
                "memory_mb": mem,
                "operations": {}
            }

            # Profile each operation
            ops = [
                ("store.load", profile_store_load),
                ("store.save", profile_store_save),
                ("refuse_history_loss", profile_refuse_history_loss),
                ("snapshot.merge_onto", profile_snapshot_merge),
                ("transaction (full)", profile_transaction),
                ("funnel.counts+attrition", profile_funnel),
                ("cadence.steps_for", profile_cadence_steps_for),
                ("personalization.plan", profile_personalization),
            ]

            for name, fn in ops:
                try:
                    result = fn(size, recs, tmp)
                    results[size]["operations"][name] = result
                    print(f"  {name:<30s} {result['median_s']:.4f}s "
                          f"(runs: {result['all_s']})")
                except Exception as e:
                    results[size]["operations"][name] = {"error": str(e)}
                    print(f"  {name:<30s} ERROR: {e}")

        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    return results


def print_summary(results, provider_model):
    """Print the summary table and name the bottleneck."""
    print("\n" + "=" * 80)
    print("SUMMARY TABLE: Operation x Estate Size")
    print("=" * 80)

    ops_names = [
        "store.load", "store.save", "refuse_history_loss",
        "snapshot.merge_onto", "transaction (full)",
        "funnel.counts+attrition", "cadence.steps_for",
        "personalization.plan",
    ]

    header = f"{'operation':<30s}"
    for size in SIZES:
        header += f" {size:>10,}"
    header += f" {'shape':>15s}"
    print(header)
    print("-" * len(header))

    for op in ops_names:
        row = f"{op:<30s}"
        times_by_size = {}
        for size in SIZES:
            op_data = results.get(size, {}).get("operations", {}).get(op, {})
            median = op_data.get("median_s")
            if median is not None:
                row += f" {median:>10.4f}"
                times_by_size[size] = median
            else:
                row += f" {'ERR':>10s}"
        shape = _shape_label(times_by_size) if len(times_by_size) >= 2 else "?"
        row += f" {shape:>15s}"
        print(row)

    # File size row
    row = f"{'file size (MB)':<30s}"
    for size in SIZES:
        mb = results.get(size, {}).get("file_mb", 0)
        row += f" {mb:>10.1f}"
    print(row)

    # Provider pagination model
    print("\n" + "=" * 80)
    print("PROVIDER PAGINATION MODEL (EmailBison - modelled from measured facts)")
    print("=" * 80)
    print(f"  Page size: {provider_model['assumptions']['page_size']} rows "
          f"(per_page IGNORED by provider)")
    print(f"  Latency assumption: "
          f"{provider_model['assumptions']['latency_per_request_s']}s per request")
    print(f"  Offset limit: ~{provider_model['assumptions']['offset_limit_pages']} "
          f"pages before 422")
    print()

    print(f"  {'scheduled':>12s} {'pages':>8s} {'walk time':>12s} {'within limit':>14s}")
    for entry in provider_model["campaign_walk"]:
        n = entry["scheduled_emails"]
        pages = entry["pages_needed"]
        walk = f"{entry['walk_minutes']:.0f}m" if entry['walk_minutes'] < 60 \
            else f"{entry['walk_hours']:.1f}h"
        ok = "YES" if entry["within_500_page_limit"] else "NO - 422"
        print(f"  {n:>12,} {pages:>8,} {walk:>12s} {ok:>14s}")

    print()
    print(f"  Reply-to-step join cost:")
    print(f"  {'replies':>12s} {'requests':>10s} {'join time':>12s}")
    for entry in provider_model["reply_step_join"]:
        n = entry["replies"]
        req = entry["requests"]
        jt = f"{entry['join_minutes']:.1f}m" if entry['join_minutes'] >= 1 \
            else f"{entry['join_seconds']:.0f}s"
        print(f"  {n:>12,} {req:>10,} {jt:>12s}")


def name_bottleneck(results, provider_model):
    """Name the single worst bottleneck with evidence."""
    print("\n" + "=" * 80)
    print("BOTTLENECK ANALYSIS")
    print("=" * 80)

    # Find the operation that grows fastest
    ops_growth = {}
    ops_names = [
        "store.load", "store.save", "refuse_history_loss",
        "snapshot.merge_onto", "transaction (full)",
        "funnel.counts+attrition", "cadence.steps_for",
        "personalization.plan",
    ]

    for op in ops_names:
        times_by_size = {}
        for size in SIZES:
            op_data = results.get(size, {}).get("operations", {}).get(op, {})
            median = op_data.get("median_s")
            if median is not None:
                times_by_size[size] = median
        if len(times_by_size) >= 2:
            shape = _shape_label(times_by_size)
            # Extrapolate to 30K
            t_30k = times_by_size.get(30_000, 0)
            ops_growth[op] = {
                "shape": shape,
                "t_30k": t_30k,
                "times": times_by_size,
            }

    # Sort by time at 30K
    ranked = sorted(ops_growth.items(), key=lambda x: -x[1]["t_30k"])

    print("\n  Local operations ranked by time at 30,000 records:")
    for op, data in ranked:
        print(f"    {op:<30s} {data['t_30k']:>8.3f}s  ({data['shape']})")

    # Provider pagination at campaign scale
    biggest_campaign = provider_model["campaign_walk"][-1]
    provider_walk_s = biggest_campaign["walk_seconds"]

    print(f"\n  Provider pagination (95K scheduled emails): "
          f"{provider_walk_s:.0f}s = {provider_walk_s/60:.0f} minutes")
    print(f"  Provider reply join (10K replies): "
          f"{provider_model['reply_step_join'][-1]['join_seconds']:.0f}s = "
          f"{provider_model['reply_step_join'][-1]['join_minutes']:.1f} minutes")

    # The verdict
    worst_local = ranked[0] if ranked else None
    worst_local_s = worst_local[1]["t_30k"] if worst_local else 0

    print(f"\n  WORST LOCAL OPERATION at 30K: {worst_local[0] if worst_local else '?'} "
          f"at {worst_local_s:.3f}s")
    print(f"  WORST PROVIDER OPERATION at 95K: campaign walk at "
          f"{provider_walk_s:.0f}s ({provider_walk_s/60:.0f} min)")

    if provider_walk_s > worst_local_s * 10:
        verdict = "PROVIDER PAGINATION"
        detail = (
            f"Provider pagination is {provider_walk_s/worst_local_s:.0f}x slower "
            f"than the worst local operation. At 95K scheduled emails the campaign "
            f"walk takes {provider_walk_s/60:.0f} minutes of sequential HTTP "
            f"requests. The offset pagination limit (~500 pages) is reached at "
            f"~7,500 emails, meaning the walk CANNOT COMPLETE for campaign 352 "
            f"without cursor pagination or a different approach."
        )
    elif worst_local and worst_local[1]["shape"] in ("quadratic or worse",
                                                       "between linear and quadratic"):
        verdict = worst_local[0].upper()
        detail = (
            f"{worst_local[0]} grows {worst_local[1]['shape']} and takes "
            f"{worst_local_s:.3f}s at 30K records."
        )
    else:
        verdict = "PROVIDER PAGINATION"
        detail = (
            f"Local operations are all manageable at 30K records. "
            f"Provider pagination at 95K scheduled emails takes "
            f"{provider_walk_s/60:.0f} minutes and hits the 422 limit."
        )

    print(f"\n  VERDICT: {verdict}")
    print(f"  {detail}")

    return verdict, detail


def main():
    print("TASK-040: What gets slow first, and at what size")
    print("=" * 60)
    print("All estates are SYNTHETIC (companies.dataset()).")
    print("No provider is called. Provider pagination is MODELLED")
    print("from measured facts on campaign 352.")
    print()

    # Read the snapshot stamp
    stamp_path = os.path.join(ROOT, "work", "queue.snapshot.STAMP")
    if os.path.exists(stamp_path):
        with open(stamp_path) as f:
            stamp = f.read().strip()
        print(f"Queue snapshot stamp: {stamp}")
    else:
        print("No queue snapshot found in this worktree.")

    results = run_full_profile()
    provider_model = model_provider_pagination()
    print_summary(results, provider_model)
    verdict, detail = name_bottleneck(results, provider_model)

    # Save full results as JSON
    output = {
        "local_profile": results,
        "provider_model": provider_model,
        "verdict": verdict,
        "detail": detail,
    }
    out_path = os.path.join(ROOT, "out", "profile_scale_results.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    print(f"\nFull results written to {out_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
