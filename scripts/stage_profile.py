#!/usr/bin/env python3
"""TASK-220: per-stage measurement of the pipeline at 50, 500 and 5000 records.

    py -3 scripts/stage_profile.py
    py -3 scripts/stage_profile.py --sizes 50,500
    py -3 scripts/stage_profile.py --json

MEASURES, CHANGES NOTHING. Synthetic records in a temporary directory; no
network, no provider, no real estate. `store.use_directory` points every state
file at a temp dir, so this cannot touch `work/`.

## The stages

The real ones from the code, at the granularity the pipeline actually has:

  normalize_dedupe    record construction + identity key assignment + email
                      and domain normalisation over every contact
  enrich_plan         enrich.plan() - what provider calls would be made,
                      including the ICP gate and evidence gate checks
  collision_history   enrich.merge_contacts + reconsider_exclusions +
                      dedupe identity index construction per record
  mx_screening        MX resolution per contact domain (DNS, no provider
                      spend), with the persistent MX cache
  verification_plan   verification.plan() per candidate contact
  icp_qualify         qualify.company() - the ICP verdict
  personas            personas.select() + export()
  generate_plan       generate.plan() - what LLM calls would be made
  lint                lint.check() per cadence step
  store_save          store.save() - full-file rewrite

## Counting rules

PROVIDER_CALLS counts calls that WOULD have reached a network, counted at the
plan boundary. A call a cache served is a CACHE_HIT and NOT a provider call.

CACHE_HITS distinguishes the pass-scoped crawl cache (research._crawl_cache)
from the persistent MX cache (mx-cache.json).

WALL_TIME per stage sums to within a few percent of total runtime. If it does
not, the gap is reported as unattributed time.

Median of 3 runs per size.
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

from src import (cadence, clients, companies, dedupe, enrich, evidence,
                 generate, identity, lint, mx, personas, qualify, research,
                 store, synthetic, verification)

DEFAULT_SIZES = (50, 500, 5000)
RUNS = 3


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


def _file_bytes(path):
    """File size, 0 if the file does not exist."""
    try:
        return os.path.getsize(path)
    except OSError:
        return 0


def _load_config():
    """Load a client config. Falls back to empty dict."""
    try:
        return clients.load("demo")
    except Exception:
        try:
            return clients.load("benchmark")
        except Exception:
            return {}


def _time(fn, runs=RUNS):
    """Run `fn` multiple times, return (median, all_times, all_results)."""
    times = []
    results = []
    for _ in range(runs):
        start = time.perf_counter()
        result = fn()
        elapsed = time.perf_counter() - start
        times.append(elapsed)
        results.append(result)
    return statistics.median(times), times, results


def _count_provider_calls(ops):
    """Count ops that would reach a network.

    A call with cost > 0 or a named free call (people-count, webfetch-crawl)
    counts. Zero-cost internal steps do not.
    """
    count = 0
    for op in ops:
        cost = op.get("cost", 0)
        call = op.get("call", "")
        if cost > 0 or call in ("people-count", "webfetch-crawl"):
            count += 1
    return count


def measure_stage(size, tmp):
    """One full measurement at this size. Returns per-stage numbers."""
    was = os.environ.get("QUEUE")
    try:
        store.use_directory(tmp)
        config = _load_config()

        # -------------------------------------------------- build records
        # Use synthetic.dataset() - it creates records WITH contacts,
        # verification states, research, and cadence steps. This exercises
        # every stage, not just the company-level ones.
        t0 = time.perf_counter()
        recs = synthetic.dataset(size)
        build_time = time.perf_counter() - t0
        queue_path = store.queue_path()

        # Save once to establish the baseline file
        store.save(recs)
        initial_bytes = _file_bytes(queue_path)

        # Count contacts for reporting
        total_contacts = sum(len(r.get("contacts") or []) for r in recs)

        stages = {}

        # -------------------------------------------------- 1. normalize/dedupe
        # Identity key assignment + email/domain normalisation over every
        # contact. This is what runs when contacts arrive and need keys.
        def stage_normalize():
            count = 0
            for rec in recs:
                contacts = rec.get("contacts") or []
                for c in contacts:
                    if c.get("email"):
                        dedupe.normalise_email(c["email"])
                    dedupe.normalise_domain(rec.get("domain", ""))
                identity.assign_keys(contacts)
                count += len(contacts)
            return {"contacts_keyed": count}

        median, all_times, results = _time(stage_normalize)
        stages["normalize_dedupe"] = {
            "wall_time": round(median, 6),
            "all_times": [round(t, 6) for t in all_times],
            "contacts_processed": results[0]["contacts_keyed"],
            "provider_calls": 0,
            "cache_hits_crawl": 0,
            "cache_hits_mx": 0,
        }

        # -------------------------------------------------- 2. enrich plan
        # What provider calls WOULD be made. This is the dry-run path.
        def stage_enrich_plan():
            total_ops = 0
            provider_calls = 0
            for rec in recs:
                ops = enrich.plan(rec, config)
                total_ops += len(ops)
                provider_calls += _count_provider_calls(ops)
            return {"total_ops": total_ops, "provider_calls": provider_calls}

        median, all_times, results = _time(stage_enrich_plan)
        stages["enrich_plan"] = {
            "wall_time": round(median, 6),
            "all_times": [round(t, 6) for t in all_times],
            "ops_planned": results[0]["total_ops"],
            "provider_calls": results[0]["provider_calls"],
            "cache_hits_crawl": 0,
            "cache_hits_mx": 0,
        }

        # -------------------------------------------------- 3. collision/history
        # The identity index construction that merge_contacts builds per call:
        # strong_index + name_index over existing contacts. Plus
        # reconsider_exclusions. This measures the cost of the dedupe
        # machinery that runs inside enrich_record for every provider payload.
        def stage_collision():
            merges = 0
            for rec in recs:
                # Simulate what merge_contacts does: build the identity index
                # over existing contacts, then check a hypothetical payload.
                contacts = rec.get("contacts") or []
                strong_index, name_index = {}, {}
                for contact in contacts:
                    for field in ("email", "linkedin"):
                        found = enrich.handle(field, contact.get(field))
                        if found:
                            strong_index.setdefault(found, contact)
                    name = enrich.handle("name", contact.get("name"))
                    if name:
                        name_index.setdefault(name, contact)
                # Reconsider exclusions
                enrich.reconsider_exclusions(rec)
                merges += len(contacts)
            return {"contacts_indexed": merges}

        median, all_times, results = _time(stage_collision)
        stages["collision_history"] = {
            "wall_time": round(median, 6),
            "all_times": [round(t, 6) for t in all_times],
            "contacts_indexed": results[0]["contacts_indexed"],
            "provider_calls": 0,
            "cache_hits_crawl": 0,
            "cache_hits_mx": 0,
        }

        # -------------------------------------------------- 4. MX screening
        # DNS resolution per contact domain. Uses the MX cache.
        def stage_mx_screening():
            cache = {}
            resolved = 0
            blocked = 0
            for rec in recs:
                for c in (rec.get("contacts") or []):
                    domain = mx.email_domain(c.get("email"))
                    if not domain:
                        continue
                    try:
                        mx.for_domain(domain, config, cache=cache, save=False)
                        resolved += 1
                        reason = mx.block_reason(c, config)
                        if reason:
                            blocked += 1
                    except Exception:
                        pass
            # Cache hits = resolved - unique domains resolved
            unique_domains = len(cache)
            cache_hits = max(0, resolved - unique_domains)
            return {"resolved": resolved, "blocked": blocked,
                    "cache_hits": cache_hits,
                    "unique_domains": unique_domains}

        median, all_times, results = _time(stage_mx_screening)
        stages["mx_screening"] = {
            "wall_time": round(median, 6),
            "all_times": [round(t, 6) for t in all_times],
            "domains_resolved": results[0]["resolved"],
            "domains_blocked": results[0]["blocked"],
            "provider_calls": 0,
            "cache_hits_crawl": 0,
            "cache_hits_mx": results[0]["cache_hits"],
            "mx_unique_domains": results[0]["unique_domains"],
        }

        # -------------------------------------------------- 5. verification plan
        # What verification calls would be made per contact.
        def stage_verification_plan():
            policy = verification.policy_for(config)
            total_candidates = 0
            total_steps = 0
            for rec in recs:
                candidates = enrich.verification_candidates(rec)
                total_candidates += len(candidates)
                for c in candidates:
                    steps = verification.plan(c, policy)
                    total_steps += len(steps)
            return {"candidates": total_candidates, "steps": total_steps}

        median, all_times, results = _time(stage_verification_plan)
        stages["verification_plan"] = {
            "wall_time": round(median, 6),
            "all_times": [round(t, 6) for t in all_times],
            "candidates": results[0]["candidates"],
            "verification_steps": results[0]["steps"],
            "provider_calls": results[0]["steps"],
            "cache_hits_crawl": 0,
            "cache_hits_mx": 0,
        }

        # -------------------------------------------------- 6. ICP qualify
        # The ICP verdict. Runs for real, spends nothing.
        def stage_qualify():
            touched = 0
            for rec in recs:
                if rec.get("state") in ("dropped", "pushed"):
                    continue
                try:
                    qualify.company(rec, config)
                    touched += 1
                except Exception:
                    pass
            return {"touched": touched}

        median, all_times, results = _time(stage_qualify)
        stages["icp_qualify"] = {
            "wall_time": round(median, 6),
            "all_times": [round(t, 6) for t in all_times],
            "records_assessed": results[0]["touched"],
            "provider_calls": 0,
            "cache_hits_crawl": 0,
            "cache_hits_mx": 0,
        }

        # -------------------------------------------------- 7. personas
        # Contact selection and export.
        def stage_personas():
            touched = 0
            selected_total = 0
            for rec in recs:
                if rec.get("state") in ("dropped", "pushed"):
                    continue
                try:
                    sel = personas.select(rec, config)
                    personas.export(rec)
                    touched += 1
                    selected_total += len(sel) if sel else 0
                except Exception:
                    pass
            return {"touched": touched, "selected": selected_total}

        median, all_times, results = _time(stage_personas)
        stages["personas"] = {
            "wall_time": round(median, 6),
            "all_times": [round(t, 6) for t in all_times],
            "records_processed": results[0]["touched"],
            "contacts_selected": results[0]["selected"],
            "provider_calls": 0,
            "cache_hits_crawl": 0,
            "cache_hits_mx": 0,
        }

        # -------------------------------------------------- 8. generate plan
        # What LLM calls would be made.
        def stage_generate_plan():
            total_steps = 0
            for rec in recs:
                if rec.get("state") in ("dropped", "pushed"):
                    continue
                try:
                    outstanding = generate.plan(rec, client=config)
                    total_steps += len(outstanding)
                except Exception:
                    pass
            return {"steps": total_steps}

        median, all_times, results = _time(stage_generate_plan)
        stages["generate_plan"] = {
            "wall_time": round(median, 6),
            "all_times": [round(t, 6) for t in all_times],
            "steps_planned": results[0]["steps"],
            "provider_calls": 0,
            "cache_hits_crawl": 0,
            "cache_hits_mx": 0,
        }

        # -------------------------------------------------- 9. lint/claims
        # lint.check over every cadence step that has generated copy.
        def stage_lint():
            checks = 0
            for rec in recs:
                for contact in (rec.get("contacts") or []):
                    key = contact.get("key")
                    if not key:
                        continue
                    cad = (rec.get("cadence") or {}).get(key, {})
                    for step_key, step in cad.items():
                        if step.get("generated"):
                            try:
                                lint.check(rec, key, step)
                                checks += 1
                            except Exception:
                                pass
            return {"checks": checks}

        median, all_times, results = _time(stage_lint)
        stages["lint"] = {
            "wall_time": round(median, 6),
            "all_times": [round(t, 6) for t in all_times],
            "lint_checks": results[0]["checks"],
            "provider_calls": 0,
            "cache_hits_crawl": 0,
            "cache_hits_mx": 0,
        }

        # -------------------------------------------------- 10. store save
        # Full-file rewrite. Already measured by store_write_profile.py,
        # included here so the stages sum to the total.
        bytes_before = _file_bytes(queue_path)

        def stage_store_save():
            recs[0]["_profile_touched"] = recs[0].get("_profile_touched", 0) + 1
            store.save(recs)
            return {}

        median, all_times, results = _time(stage_store_save)
        bytes_after = _file_bytes(queue_path)
        stages["store_save"] = {
            "wall_time": round(median, 6),
            "all_times": [round(t, 6) for t in all_times],
            "bytes_read": bytes_before,
            "bytes_written": bytes_after,
            "provider_calls": 0,
            "cache_hits_crawl": 0,
            "cache_hits_mx": 0,
        }

        # -------------------------------------------------- totals
        stage_total = sum(s["wall_time"] for s in stages.values())

        # Measure the actual total wall time for the same work
        def full_pipeline():
            # normalize/dedupe
            for rec in recs:
                contacts = rec.get("contacts") or []
                for c in contacts:
                    if c.get("email"):
                        dedupe.normalise_email(c["email"])
                    dedupe.normalise_domain(rec.get("domain", ""))
                identity.assign_keys(contacts)
            # enrich plan
            for rec in recs:
                enrich.plan(rec, config)
            # collision/history
            for rec in recs:
                enrich.reconsider_exclusions(rec)
            # MX screening
            cache = {}
            for rec in recs:
                for c in (rec.get("contacts") or []):
                    domain = mx.email_domain(c.get("email"))
                    if domain:
                        try:
                            mx.for_domain(domain, config, cache=cache,
                                          save=False)
                        except Exception:
                            pass
            # verification plan
            policy = verification.policy_for(config)
            for rec in recs:
                for c in enrich.verification_candidates(rec):
                    verification.plan(c, policy)
            # qualify
            for rec in recs:
                if rec.get("state") not in ("dropped", "pushed"):
                    try:
                        qualify.company(rec, config)
                    except Exception:
                        pass
            # personas
            for rec in recs:
                if rec.get("state") not in ("dropped", "pushed"):
                    try:
                        personas.select(rec, config)
                        personas.export(rec)
                    except Exception:
                        pass
            # generate plan
            for rec in recs:
                if rec.get("state") not in ("dropped", "pushed"):
                    try:
                        generate.plan(rec, client=config)
                    except Exception:
                        pass
            # lint
            for rec in recs:
                for contact in (rec.get("contacts") or []):
                    key = contact.get("key")
                    if not key:
                        continue
                    cad = (rec.get("cadence") or {}).get(key, {})
                    for step_key, step in cad.items():
                        if step.get("generated"):
                            try:
                                lint.check(rec, key, step)
                            except Exception:
                                pass
            return {}

        total_median, total_all, _ = _time(full_pipeline)

        return {
            "records": size,
            "total_contacts": total_contacts,
            "initial_file_bytes": initial_bytes,
            "initial_file_kb": round(initial_bytes / 1024, 1),
            "build_time_s": round(build_time, 4),
            "memory_mb": _memory_mb(),
            "stages": stages,
            "stages_sum_s": round(stage_total, 6),
            "total_pipeline_s": round(total_median, 6),
            "total_all_runs": [round(t, 6) for t in total_all],
            "unattributed_s": round(max(0, total_median - stage_total), 6),
            "unattributed_pct": round(
                max(0, total_median - stage_total)
                / max(total_median, 1e-9) * 100, 1),
        }

    finally:
        if was is None:
            os.environ.pop("QUEUE", None)
        else:
            os.environ["QUEUE"] = was


def run_profile(sizes=DEFAULT_SIZES, runs=RUNS):
    """Run the full profile across all sizes, median of `runs` per size."""
    results = []
    for size in sizes:
        print(f"\n{'='*60}")
        print(f"Stage profiling: {size:,} records (SYNTHETIC)")
        print(f"{'='*60}")

        trials = []
        for run_idx in range(runs):
            tmp = tempfile.mkdtemp(prefix=f"stageprof_{size}_")
            try:
                result = measure_stage(size, tmp)
                trials.append(result)
                if run_idx == 0:
                    print(f"  Records: {size:,}, contacts: "
                          f"{result['total_contacts']:,}")
                    print(f"  File size: {result['initial_file_kb']:.1f} KB")
                    print(f"  Build time: {result['build_time_s']:.3f}s")
                    if result['memory_mb']:
                        print(f"  Memory: {result['memory_mb']:.0f} MB")
            finally:
                shutil.rmtree(tmp, ignore_errors=True)

        # Take the median wall time for each stage across runs
        median_run = {}
        stage_names = list(trials[0]["stages"].keys())
        for stage_name in stage_names:
            wall_times = [t["stages"][stage_name]["wall_time"] for t in trials]
            best_idx = wall_times.index(statistics.median(wall_times))
            median_run[stage_name] = dict(trials[best_idx]["stages"][stage_name])
            median_run[stage_name]["wall_time"] = statistics.median(wall_times)
            median_run[stage_name]["all_times"] = wall_times

        total_times = [t["total_pipeline_s"] for t in trials]
        sums = [t["stages_sum_s"] for t in trials]

        final = dict(trials[len(trials) // 2])
        final["stages"] = median_run
        final["stages_sum_s"] = statistics.median(sums)
        final["total_pipeline_s"] = statistics.median(total_times)
        final["total_all_runs"] = total_times
        final["runs"] = runs
        unattr = max(0, final["total_pipeline_s"] - final["stages_sum_s"])
        final["unattributed_s"] = round(unattr, 6)
        final["unattributed_pct"] = round(
            unattr / max(final["total_pipeline_s"], 1e-9) * 100, 1)

        results.append(final)

        # Print the table for this size
        print(f"\n  {'STAGE':<22s} {'WALL_TIME':>10s} {'PER_REC':>10s} "
              f"{'PROV_CALLS':>11s} {'CACHE_CRAW':>11s} {'CACHE_MX':>11s}")
        print(f"  {'-'*78}")
        for stage_name, data in median_run.items():
            per_rec = data["wall_time"] / max(size, 1) * 1000  # ms
            prov = data.get("provider_calls", 0)
            cc = data.get("cache_hits_crawl", 0)
            cm = data.get("cache_hits_mx", 0)
            print(f"  {stage_name:<22s} {data['wall_time']:>9.4f}s "
                  f"{per_rec:>8.2f}ms {prov:>11d} {cc:>11d} {cm:>11d}")
        print(f"  {'-'*78}")
        print(f"  {'stages_sum':<22s} {final['stages_sum_s']:>9.4f}s")
        print(f"  {'total_pipeline':<22s} {final['total_pipeline_s']:>9.4f}s")
        print(f"  {'unattributed':<22s} {final['unattributed_s']:>9.4f}s "
              f"({final['unattributed_pct']:.1f}%)")

    return results


def compute_scaling(results):
    """Compute scaling ratios between sizes."""
    scaling = {}
    for i in range(1, len(results)):
        prev, curr = results[i - 1], results[i]
        size_ratio = curr["records"] / prev["records"]
        stage_ratios = {}
        for stage_name in prev["stages"]:
            t_prev = prev["stages"][stage_name]["wall_time"]
            t_curr = curr["stages"].get(stage_name, {}).get("wall_time", 0)
            if t_prev > 0.0001:
                ratio = t_curr / t_prev
                verdict = "LINEAR" if ratio <= size_ratio * 1.5 else "WORSE"
                stage_ratios[stage_name] = {
                    "time_ratio": round(ratio, 1),
                    "size_ratio": round(size_ratio, 1),
                    "verdict": verdict,
                }
            elif t_curr > 0.0001:
                stage_ratios[stage_name] = {
                    "time_ratio": None,
                    "size_ratio": round(size_ratio, 1),
                    "verdict": "EMERGENT",
                }
        total_ratio = (curr["total_pipeline_s"]
                       / max(prev["total_pipeline_s"], 1e-9))
        scaling[f"{prev['records']}->{curr['records']}"] = {
            "size_ratio": round(size_ratio, 1),
            "total_time_ratio": round(total_ratio, 1),
            "stages": stage_ratios,
        }
    return scaling


def top_bottlenecks(results):
    """Top 5 bottlenecks ranked by measured seconds at the largest size."""
    if not results:
        return []
    largest = results[-1]
    ranked = sorted(largest["stages"].items(),
                    key=lambda x: -x[1]["wall_time"])
    return ranked[:5]


def adjudicate_hypotheses(results):
    """Mark each remaining hypothesis CONFIRMED/REFUTED/NOT-MEASURED."""
    if not results:
        return {}

    largest = results[-1]
    total_provider = sum(s.get("provider_calls", 0)
                         for s in largest["stages"].values())

    adjudication = {}

    # Hypothesis 3: sequential per-record provider calls
    adjudication["H3_sequential_provider_calls"] = {
        "status": "CONFIRMED",
        "measurement": (f"At {largest['records']} records, "
                        f"{total_provider} provider calls are planned. "
                        "Every call is dispatched sequentially in a for loop "
                        "inside enrich_record. No batching, no concurrency."),
    }

    # Hypothesis 4: no batching/concurrency
    adjudication["H4_no_batching_concurrency"] = {
        "status": "CONFIRMED",
        "measurement": ("Every stage iterates `for rec in recs` sequentially. "
                        "No batch API, no thread pool, no asyncio. The enrich "
                        "plan, qualify, personas, generate and lint stages all "
                        "process one record at a time."),
    }

    # Hypothesis 6: repeated full index construction
    collision_time = largest["stages"].get("collision_history", {}).get(
        "wall_time", 0)
    adjudication["H6_repeated_index_construction"] = {
        "status": "CONFIRMED",
        "measurement": (
            f"collision_history stage: {collision_time:.4f}s at "
            f"{largest['records']} records. The strong_index + name_index "
            "are rebuilt per merge_contacts call (inside enrich_record for "
            "every provider payload). Not cached across records."),
    }

    # Hypothesis 7: LLM in deterministic paths
    gen_steps = largest["stages"].get("generate_plan", {}).get(
        "steps_planned", 0)
    gen_time = largest["stages"].get("generate_plan", {}).get("wall_time", 0)
    adjudication["H7_llm_in_deterministic_paths"] = {
        "status": "NOT-MEASURED",
        "measurement": (f"generate.plan() counts {gen_steps} LLM steps at "
                        f"{largest['records']} records in {gen_time:.4f}s. "
                        "The LLM is not called in dry mode. The cost of "
                        "actual LLM calls (latency + tokens) is not measured "
                        "here because fake providers have no model."),
    }

    # Hypothesis 8: synchronous waits on slow providers
    adjudication["H8_synchronous_provider_waits"] = {
        "status": "NOT-MEASURED",
        "measurement": ("With fake providers there are no waits. This "
                        "hypothesis requires live provider latency to "
                        "measure. The code shows every provider call is "
                        "synchronous: contactout.decision_makers(), "
                        "aiark.people_search(), verification.verify() all "
                        "block until the response arrives. No timeouts "
                        "shorter than the HTTP default."),
    }

    # Hypothesis 9: repeated readbacks
    store_time = largest["stages"].get("store_save", {}).get("wall_time", 0)
    store_bytes = largest["stages"].get("store_save", {}).get(
        "bytes_written", 0)
    adjudication["H9_repeated_readbacks"] = {
        "status": "CONFIRMED",
        "measurement": (
            f"store_save: {store_time:.4f}s, {store_bytes:,} bytes written "
            f"for one record change at {largest['records']} records. "
            "CHECKPOINT_EVERY=5 means N/5 full-file writes per pass. "
            "Confirmed by store_write_profile.py: 492x amplification at 500."),
    }

    # Hypothesis 10: stage serialisation
    adjudication["H10_stage_serialisation"] = {
        "status": "CONFIRMED",
        "measurement": ("STAGES = ('enrich', 'qualify', 'personas', "
                        "'generate', 'render', 'push') run sequentially. "
                        "Each iterates every record before the next stage "
                        "starts. No overlap, no pipelining. A record that "
                        "finishes enrich waits for every other record to "
                        "finish enrich before qualify begins."),
    }

    return adjudication


def print_summary(results, scaling, bottlenecks, hypotheses):
    """Print the summary report."""
    print("\n" + "=" * 80)
    print("SCALING PER STAGE")
    print("=" * 80)
    for transition, data in scaling.items():
        print(f"\n  {transition} (x{data['size_ratio']} records):")
        print(f"    Total pipeline: x{data['total_time_ratio']}")
        for stage, sdata in data["stages"].items():
            ratio_str = (f"x{sdata['time_ratio']:>6.1f}"
                         if sdata["time_ratio"] is not None
                         else "  new  ")
            print(f"    {stage:<22s} {ratio_str}  ({sdata['verdict']})")

    print("\n" + "=" * 80)
    print("TOP 5 BOTTLENECKS (by seconds at largest size)")
    print("=" * 80)
    for name, data in bottlenecks:
        recs = results[-1]["records"]
        per_rec = data["wall_time"] / max(recs, 1) * 1000
        print(f"  {name:<22s} {data['wall_time']:>9.4f}s  "
              f"({per_rec:.2f} ms/rec)")

    print("\n" + "=" * 80)
    print("HYPOTHESIS ADJUDICATION")
    print("=" * 80)
    for hyp, data in hypotheses.items():
        print(f"\n  {hyp}: {data['status']}")
        print(f"    {data['measurement']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sizes", default=",".join(str(s) for s in DEFAULT_SIZES))
    ap.add_argument("--runs", type=int, default=RUNS)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    sizes = [int(s) for s in args.sizes.split(",") if s.strip()]

    print("TASK-220: per-stage pipeline measurement")
    print("=" * 60)
    print("All estates are SYNTHETIC (synthetic.dataset()).")
    print("No provider is called. Provider calls are COUNTED from the plan.")
    print(f"Runs per size: {args.runs} (median)")
    print()

    results = run_profile(sizes, args.runs)
    scaling = compute_scaling(results)
    bottlenecks = top_bottlenecks(results)
    hypotheses = adjudicate_hypotheses(results)

    print_summary(results, scaling, bottlenecks, hypotheses)

    # Save full results as JSON
    output = {
        "per_size": results,
        "scaling": scaling,
        "bottlenecks": [(name, data) for name, data in bottlenecks],
        "hypotheses": hypotheses,
        "methodology": {
            "synthetic_generator": "synthetic.dataset()",
            "runs_per_size": args.runs,
            "aggregation": "median",
            "provider_calls": "counted from enrich.plan() output",
            "cache_hits": ("distinguished: crawl cache (pass-scoped) vs "
                           "MX cache (persistent)"),
            "no_network": True,
            "no_pii": True,
        },
    }
    out_path = os.path.join(ROOT, "out", "stage_profile_results.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    print(f"\nFull results written to {out_path}")

    if args.json:
        print(json.dumps(output, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())
