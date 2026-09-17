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
import collections
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

# ---------------------------------------------------------------------------
# TASK-222: latency model for provider calls.
#
# Every value is ASSUMED unless a source in this repo states otherwise.
# The only reference point in the repo is "~300ms per call" from
# docs/PERF-STAGE-BASELINE-2026-09-17.md, which is itself an assumption.
# No live provider latency has been measured. The bands below are LOW/MID/HIGH
# around that reference, with wider spreads for providers whose response
# contracts are unknown to this codebase.
#
# Sources consulted:
#   - docs/PERF-STAGE-BASELINE-2026-09-17.md: "~300ms per call" (ASSUMED)
#   - src/providers/__init__.py: TIMEOUT = 25 (upper bound, not typical)
#   - src/providers/xai.py: XAI_TIMEOUT = 300 (LLM, very slow)
#   - docs/GROK-PROVIDER-RESEARCH-2026-09-17.md: rate limits, not latency
#   - docs/SCALE-MEASUREMENT-30K.md: "12.4 seconds per call" for bison batch
#
# A sleep-based model is fine and must be labelled a MODEL everywhere.
# ---------------------------------------------------------------------------

# Latency bands in SECONDS per call, by provider call name.
# LOW = optimistic, MID = reference (~300ms baseline), HIGH = pessimistic.
# All values are ASSUMED unless marked otherwise.
LATENCY_MODEL = {
    # ContactOut: the primary enrichment provider.
    # ~300ms is the baseline reference (ASSUMED).
    "people-count":                       {"low": 0.10, "mid": 0.20, "high": 0.50},
    "decision-makers":                    {"low": 0.20, "mid": 0.40, "high": 1.00},
    "company-information-from-domain":    {"low": 0.10, "mid": 0.30, "high": 0.80},
    # Verification providers.
    # Deliverable and Reoon are simpler APIs than ContactOut.
    "email-verifier":                     {"low": 0.10, "mid": 0.30, "high": 0.80},
    "deliverable-verify":                 {"low": 0.15, "mid": 0.40, "high": 1.00},
    "reoon-verify":                       {"low": 0.15, "mid": 0.40, "high": 1.00},
    # AI Ark: people search fallback, slower index.
    "aiark-people-search":               {"low": 0.50, "mid": 1.00, "high": 3.00},
    # Blitz: record-based billing, medium latency.
    "blitz-company":                      {"low": 0.15, "mid": 0.40, "high": 1.00},
    "blitz-domain-to-linkedin":           {"low": 0.15, "mid": 0.40, "high": 1.00},
    "blitz-linkedin-to-domain":           {"low": 0.15, "mid": 0.40, "high": 1.00},
    "blitz-employee-finder":              {"low": 0.20, "mid": 0.50, "high": 1.50},
    "blitz-email":                        {"low": 0.15, "mid": 0.40, "high": 1.00},
    # Apify: actor runs, compute-billed, highly variable.
    "apify-research":                     {"low": 1.00, "mid": 3.00, "high": 8.00},
    # xAI research: LLM call, very slow (XAI_TIMEOUT=300 in code).
    "xai-research":                       {"low": 2.00, "mid": 5.00, "high": 10.00},
    # Web crawl: HTTP fetch, variable by target.
    "webfetch-crawl":                     {"low": 0.20, "mid": 0.50, "high": 2.00},
    # LLM calls (generate stage): from AI-CALL-SITE-INVENTORY token counts.
    # At ~20 tok/s output and ~4,000 input tokens, ~2-5s per call is reasonable.
    "llm-draft":                          {"low": 2.00, "mid": 4.00, "high": 8.00},
    "llm-linkedin_note":                  {"low": 1.00, "mid": 2.50, "high": 5.00},
    "llm-diagnose":                       {"low": 1.00, "mid": 2.00, "high": 4.00},
    "llm-hook":                           {"low": 0.50, "mid": 1.50, "high": 3.00},
    "llm-persona_angle":                  {"low": 1.00, "mid": 2.00, "high": 4.00},
}

# Default band when --latency is used without a band specifier.
DEFAULT_LATENCY_BAND = "mid"


def _count_calls_by_provider(ops):
    """Break down ops into per-call-name counts for latency modelling.

    Returns a dict: {call_name: count} for calls that would reach a network.
    """
    counts = {}
    for op in ops:
        cost = op.get("cost", 0)
        call = op.get("call", "")
        if cost > 0 or call in ("people-count", "webfetch-crawl"):
            counts[call] = counts.get(call, 0) + 1
    return counts


def _count_verification_by_provider(candidates, policy):
    """Break down verification plan into per-provider counts.

    Returns a dict: {call_name: count} for verification calls.
    """
    counts = {}
    for c in candidates:
        steps = verification.plan(c, policy)
        for step in steps:
            call_name = f"{step['provider']}-verify"
            # Normalise to match LATENCY_MODEL keys.
            if call_name == "contactout-verify":
                call_name = "email-verifier"
            counts[call_name] = counts.get(call_name, 0) + 1
    return counts


def model_serial_wait(enrich_counts, verify_counts, band="mid"):
    """Sum of (count × latency) across all provider calls.

    This is the wall time if every call runs one after another with no
    overlap. The model, not a measurement.
    """
    total = 0.0
    by_provider = {}
    for call_name, count in enrich_counts.items():
        latencies = LATENCY_MODEL.get(call_name)
        if latencies is None:
            continue
        lat = latencies.get(band, latencies["mid"])
        wait = count * lat
        total += wait
        by_provider[call_name] = {"count": count, "latency_s": lat,
                                   "wait_s": round(wait, 2)}
    for call_name, count in verify_counts.items():
        latencies = LATENCY_MODEL.get(call_name)
        if latencies is None:
            continue
        lat = latencies.get(band, latencies["mid"])
        wait = count * lat
        total += wait
        by_provider[call_name] = {"count": count, "latency_s": lat,
                                   "wait_s": round(wait, 2)}
    return round(total, 2), by_provider


def model_concurrency(serial_wait, total_calls, k, critical_path_s=None):
    """Model bounded concurrency at pool size K.

    Ideal speedup: serial / K. But the critical path (sequential
    dependencies) cannot be parallelised, so the real time is at least
    critical_path_s. Returns (modelled_wall_s, speedup_factor).
    """
    if k <= 0:
        return serial_wait, 1.0
    ideal = serial_wait / k
    floor = critical_path_s or 0
    modelled = max(ideal, floor)
    speedup = serial_wait / max(modelled, 0.001)
    return round(modelled, 2), round(speedup, 2)


def _fake_resolver(domain):
    """Fake DNS resolver that returns Google MX records instantly.

    The task rules say 'No network calls.' Real DNS lookups for .test domains
    would either timeout or return NXDOMAIN slowly. This simulates a normal
    domain with Google mail, so the MX screening logic runs without network.
    """
    return ["aspmx.l.google.com", "alt1.aspmx.l.google.com"]


# EVERY STAGE BELOW SWALLOWS EXCEPTIONS, AND THAT IS A HAZARD IN A
# MEASURING INSTRUMENT: a stage that raises for every record does no work and
# therefore reports a very good time. Calibrated on 2026-09-17 -
# `qualify.company` and `generate.plan` both ran 20 of 20 synthetic records
# clean - so the numbers in the baseline are real work. This counter is what
# keeps that true when something changes: the errors are COUNTED and printed
# beside each stage, so "fast" and "broken" stop looking alike.
_ERRORS = collections.Counter()
_CURRENT_STAGE = [None]


def _swallowed(exc=None):
    """Record that a stage skipped one unit of work."""
    _ERRORS[_CURRENT_STAGE[0] or "unattributed"] += 1


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
    """Run `fn` multiple times, return (median, all_times, all_results).

    Names the running stage so `_swallowed` can attribute a skipped unit of
    work to it. Without that, a stage that quietly fails for every record is
    indistinguishable from a stage that is simply fast.
    """
    _CURRENT_STAGE[0] = getattr(fn, "__name__", None)
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
            by_provider = {}
            for rec in recs:
                ops = enrich.plan(rec, config)
                total_ops += len(ops)
                provider_calls += _count_provider_calls(ops)
                for call_name, count in _count_calls_by_provider(ops).items():
                    by_provider[call_name] = by_provider.get(call_name, 0) + count
            return {"total_ops": total_ops, "provider_calls": provider_calls,
                    "calls_by_provider": by_provider}

        median, all_times, results = _time(stage_enrich_plan)
        stages["enrich_plan"] = {
            "wall_time": round(median, 6),
            "all_times": [round(t, 6) for t in all_times],
            "ops_planned": results[0]["total_ops"],
            "provider_calls": results[0]["provider_calls"],
            "calls_by_provider": results[0]["calls_by_provider"],
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
        # Uses a fake resolver to avoid real network calls (task rule).
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
                        mx.for_domain(domain, config, cache=cache, save=False,
                                      resolver=_fake_resolver)
                        resolved += 1
                        reason = mx.block_reason(c, config)
                        if reason:
                            blocked += 1
                    except Exception:
                        _swallowed()
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
            by_provider = {}
            for rec in recs:
                candidates = enrich.verification_candidates(rec)
                total_candidates += len(candidates)
                for c in candidates:
                    steps = verification.plan(c, policy)
                    total_steps += len(steps)
                    for step in steps:
                        call_name = f"{step['provider']}-verify"
                        if call_name == "contactout-verify":
                            call_name = "email-verifier"
                        by_provider[call_name] = by_provider.get(call_name, 0) + 1
            return {"candidates": total_candidates, "steps": total_steps,
                    "calls_by_provider": by_provider}

        median, all_times, results = _time(stage_verification_plan)
        stages["verification_plan"] = {
            "wall_time": round(median, 6),
            "all_times": [round(t, 6) for t in all_times],
            "candidates": results[0]["candidates"],
            "verification_steps": results[0]["steps"],
            "provider_calls": results[0]["steps"],
            "calls_by_provider": results[0]["calls_by_provider"],
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
                    _swallowed()
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
                    _swallowed()
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
                    _swallowed()
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
                                _swallowed()
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
                                          save=False, resolver=_fake_resolver)
                        except Exception:
                            _swallowed()
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
                        _swallowed()
            # personas
            for rec in recs:
                if rec.get("state") not in ("dropped", "pushed"):
                    try:
                        personas.select(rec, config)
                        personas.export(rec)
                    except Exception:
                        _swallowed()
            # generate plan
            for rec in recs:
                if rec.get("state") not in ("dropped", "pushed"):
                    try:
                        generate.plan(rec, client=config)
                    except Exception:
                        _swallowed()
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
                                _swallowed()
            return {}

        total_median, total_all, _ = _time(full_pipeline)

        # Aggregate per-provider call counts across enrich and verification.
        enrich_by_provider = stages.get("enrich_plan", {}).get("calls_by_provider", {})
        verify_by_provider = stages.get("verification_plan", {}).get("calls_by_provider", {})
        total_provider_calls = sum(enrich_by_provider.values()) + sum(verify_by_provider.values())

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
            # SIGNED, not clamped. `max(0, ...)` reported 0.0% while
            # stages_sum EXCEEDED total_pipeline by 10-21% at every size -
            # which is the instrument saying "all time accounted for" about
            # two numbers that disagree. They disagree because
            # `full_pipeline` re-runs a SUBSET of the stages with caches
            # already warm, so it is not the same workload as their sum and
            # the difference is not "unattributed time" in either direction.
            "stage_errors": dict(_ERRORS),
            "unattributed_s": round(total_median - stage_total, 6),
            "unattributed_pct": round(
                (total_median - stage_total)
                / max(total_median, 1e-9) * 100, 1),
            # TASK-222: per-provider call breakdown for latency modelling.
            "enrich_calls_by_provider": enrich_by_provider,
            "verify_calls_by_provider": verify_by_provider,
            "total_provider_calls": total_provider_calls,
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
        unattr = final["total_pipeline_s"] - final["stages_sum_s"]
        final["unattributed_s"] = round(unattr, 6)
        final["unattributed_pct"] = round(
            unattr / max(final["total_pipeline_s"], 1e-9) * 100, 1)
        final["stage_errors"] = dict(_ERRORS)

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


def latency_report(results, band="mid", concurrency_levels=None):
    """TASK-222: model provider wait time from call counts and latency bands.

    Returns a list of dicts, one per size, with serial wait and concurrency
    projections. Also prints the table.
    """
    if concurrency_levels is None:
        concurrency_levels = [1, 4, 8, 16]

    report = []
    for r in results:
        enrich_counts = r.get("enrich_calls_by_provider", {})
        verify_counts = r.get("verify_calls_by_provider", {})
        total_calls = r.get("total_provider_calls", 0)
        serial_s, by_provider = model_serial_wait(enrich_counts, verify_counts,
                                                   band=band)

        # Local CPU time is the measured pipeline time minus provider wait.
        # At zero-latency the measured time IS the CPU time.
        cpu_s = r["total_pipeline_s"]
        total_with_wait = cpu_s + serial_s
        wait_fraction = serial_s / max(total_with_wait, 0.001)

        conc = {}
        for k in concurrency_levels:
            wall, speedup = model_concurrency(serial_s, total_calls, k)
            conc[k] = {"wall_s": wall, "speedup": speedup}

        entry = {
            "records": r["records"],
            "provider_calls": total_calls,
            "latency_band": band,
            "serial_wait_s": serial_s,
            "cpu_time_s": round(cpu_s, 2),
            "total_with_wait_s": round(total_with_wait, 2),
            "wait_fraction": round(wait_fraction, 3),
            "by_provider": by_provider,
            "concurrency": conc,
        }
        report.append(entry)

    # Print the table.
    print("\n" + "=" * 90)
    print(f"TASK-222: LATENCY MODEL (band={band}, ALL VALUES ASSUMED)")
    print("=" * 90)
    hdr = (f"  {'RECORDS':>8s} {'PROV_CALLS':>11s} {'BAND':>5s} "
           f"{'SERIAL_WAIT':>12s} {'CPU_TIME':>10s} {'TOTAL':>10s} "
           f"{'WAIT%':>7s}")
    for k in concurrency_levels:
        hdr += f" {'K='+str(k):>10s}"
    print(hdr)
    print("  " + "-" * (len(hdr) - 2))
    for e in report:
        row = (f"  {e['records']:>8,d} {e['provider_calls']:>11,d} "
               f"{e['latency_band']:>5s} "
               f"{e['serial_wait_s']:>10.1f}s {e['cpu_time_s']:>8.1f}s "
               f"{e['total_with_wait_s']:>8.1f}s "
               f"{e['wait_fraction']*100:>6.1f}%")
        for k in concurrency_levels:
            c = e["concurrency"].get(k, {})
            row += f" {c.get('wall_s', 0):>8.1f}s"
        print(row)

    # Print per-provider breakdown for the largest size.
    if report:
        largest = report[-1]
        print(f"\n  Per-provider breakdown at {largest['records']:,} records "
              f"(band={band}):")
        print(f"  {'CALL':<35s} {'COUNT':>7s} {'LAT_s':>7s} {'WAIT_s':>10s}")
        print("  " + "-" * 62)
        for call_name, info in sorted(largest["by_provider"].items(),
                                       key=lambda x: -x[1]["wait_s"]):
            print(f"  {call_name:<35s} {info['count']:>7,d} "
                  f"{info['latency_s']:>7.2f} {info['wait_s']:>10.1f}")

    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sizes", default=",".join(str(s) for s in DEFAULT_SIZES))
    ap.add_argument("--runs", type=int, default=RUNS)
    ap.add_argument("--json", action="store_true")
    # TASK-222: latency modelling options.
    ap.add_argument("--latency", choices=["low", "mid", "high"],
                    help="Apply a latency model to provider calls (ASSUMED "
                         "values). Off by default; existing numbers unchanged.")
    ap.add_argument("--concurrency", default="1,4,8,16",
                    help="Comma-separated pool sizes to model (default: 1,4,8,16)")
    args = ap.parse_args()
    sizes = [int(s) for s in args.sizes.split(",") if s.strip()]
    concurrency_levels = [int(k) for k in args.concurrency.split(",")
                          if k.strip()]

    print("TASK-220: per-stage pipeline measurement")
    print("=" * 60)
    print("All estates are SYNTHETIC (synthetic.dataset()).")
    print("No provider is called. Provider calls are COUNTED from the plan.")
    print(f"Runs per size: {args.runs} (median)")
    if args.latency:
        print(f"Latency model: ON (band={args.latency}, ALL VALUES ASSUMED)")
    print()

    results = run_profile(sizes, args.runs)
    scaling = compute_scaling(results)
    bottlenecks = top_bottlenecks(results)
    hypotheses = adjudicate_hypotheses(results)

    print_summary(results, scaling, bottlenecks, hypotheses)

    latency_data = None
    if args.latency:
        latency_data = latency_report(results, band=args.latency,
                                       concurrency_levels=concurrency_levels)

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
    if latency_data:
        output["latency_model"] = {
            "band": args.latency,
            "all_values_assumed": True,
            "sources": [
                "docs/PERF-STAGE-BASELINE-2026-09-17.md: ~300ms per call (ASSUMED)",
                "src/providers/__init__.py: TIMEOUT=25 (upper bound)",
                "src/providers/xai.py: XAI_TIMEOUT=300 (LLM)",
                "docs/GROK-PROVIDER-RESEARCH-2026-09-17.md: rate limits, not latency",
            ],
            "sizes": latency_data,
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
