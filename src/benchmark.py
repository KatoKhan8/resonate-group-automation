#!/usr/bin/env python3
"""How the architecture behaves at 10, 50, 100 and 5,000 domains, offline.

This measures *our* overhead, not a provider's latency. Every provider is a
fake that returns instantly, so what is left is the cost of the pipeline
itself: building timelines, scoring evidence, selecting contacts, fingerprints,
and the store. That is the part we control and the part that turns into an
afternoon of waiting if it is quadratic.

Nothing here calls a network, and 5,000 domains is fully synthetic.

  python -m src.benchmark
  python -m src.benchmark --sizes 10,50,100,5000
"""
import argparse
import json
import os
import sys
import time

from . import (cadence, campaigns, clients, evidence, lint, personalization,
               store)

SIZES = (10, 50, 100, 5000)

# What a synthetic company looks like. Deliberately average: two contacts, one
# piece of evidence, so the per-record work is representative rather than best
# case.
CONTACTS_PER_COMPANY = 2
FOUND_PER_COMPANY = 6          # what ContactOut would return before selection


def fake_record(index, config, today="2026-08-26"):
    rid = f"bench{index:05d}"
    rec = store.new_record(rid, "cold", "demo", f"Bench Co {index}",
                           f"bench{index:05d}.test")
    rec["state"] = "drafted"
    rec["hook"] = "runs delivery across several teams"
    rec["company_facts"] = {"industry": "Professional services",
                            "employees": 40 + (index % 200),
                            "specialties": ["delivery"]}
    rec["contacts"] = []
    for n in range(FOUND_PER_COMPANY):
        persona = "champion" if n < 2 else "economic_buyer"
        rec["contacts"].append({
            "key": f"{rid}-c{n}", "name": f"Person {n}",
            "title": "Operations Manager", "persona": persona,
            "angle": "ops", "sendable": True,
            "email": f"p{n}@{rid}.test",
            "linkedin": f"https://www.linkedin.com/in/{rid}-c{n}",
            "verification": {"state": "verified", "evidence": []},
        })
    rec["research"] = [evidence.make(
        f"Bench Co {index} is hiring a delivery manager to improve utilisation "
        "across the team.",
        f"https://bench{index:05d}.test/careers", "careers_page", "apify", rid,
        published_at="2026-08-20", persona="operations",
        angle_words=["utilisation", "capacity"], today=today)]
    gen_keys = cadence.generated_keys(cadence.steps_for(config=config))
    for contact in rec["contacts"][:CONTACTS_PER_COMPANY]:
        rec.setdefault("cadence", {})[contact["key"]] = {
            key: {"channel": "email", "generated": True,
                  "subject": f"quick question about Bench Co {index}",
                  "body": ("Hi Person,\n\nNoticed you are hiring a delivery "
                           "manager to improve utilisation across the team. "
                           "Most operations leads we speak to lose the better "
                           "part of a day every month reconciling time before "
                           "they can answer a question anyone actually asked.\n\n"
                           "Is that roughly how it works with you today?\n")}
            for key in gen_keys}
    return rec


def measure(size, config, today="2026-08-26"):
    """One pass over `size` synthetic domains. Returns counts and timings."""
    counters = {"records": 0, "contacts_found": 0, "contacts_selected": 0,
                "person_research_planned": 0, "company_research_planned": 0,
                "email_steps": 0, "linkedin_steps": 0, "lint_checks": 0,
                "evidence_scored": 0, "llm_calls_would_be": 0,
                "verification_ops_would_be": 0}
    timings = {}

    start = time.perf_counter()
    recs = [fake_record(i, config, today) for i in range(size)]
    timings["build_records"] = time.perf_counter() - start

    start = time.perf_counter()
    for rec in recs:
        counters["records"] += 1
        counters["contacts_found"] += len(rec["contacts"])
        selected = personalization.selected_contacts(rec, config)
        counters["contacts_selected"] += len(selected)
        plan = personalization.plan(rec, config)
        counters["company_research_planned"] += int(plan["company"]["planned"])
        counters["person_research_planned"] += sum(
            1 for s in plan["people"] if s["planned"])
        counters["evidence_scored"] += len(rec.get("research") or [])
        # One verification per selected contact with an address; the rest are
        # never verified because they are never written to.
        counters["verification_ops_would_be"] += len(selected)
        counters["llm_calls_would_be"] += len(selected) * len(
            cadence.generated_keys(cadence.steps_for(config=config)))
    timings["select_and_plan"] = time.perf_counter() - start

    start = time.perf_counter()
    paused_set = cadence.paused_domains(recs)
    for rec in recs:
        timeline = cadence.build(rec, config, paused_set=paused_set)
        for steps in timeline["contacts"].values():
            for step in steps.values():
                if step.get("channel") == "email":
                    counters["email_steps"] += 1
                else:
                    counters["linkedin_steps"] += 1
    timings["cadence"] = time.perf_counter() - start

    start = time.perf_counter()
    for rec in recs[:min(size, 200)]:          # lint is the expensive one
        for contact in personalization.selected_contacts(rec, config):
            for key in cadence.generated_keys(cadence.steps_for(config=config)):
                step = (rec.get("cadence") or {}).get(contact["key"], {}).get(key)
                if step:
                    lint.check(rec, contact["key"], step)
                    counters["lint_checks"] += 1
    timings["lint_sample"] = time.perf_counter() - start

    total = sum(timings.values())
    return {
        "size": size,
        "seconds": round(total, 3),
        "records_per_second": round(size / total, 1) if total else None,
        "timings": {k: round(v, 3) for k, v in timings.items()},
        "counters": counters,
        "fallback_percent": 0.0,
        "memory_mb": _memory_mb(),
    }


def _memory_mb():
    """Resident memory, where the platform will say. None rather than a guess."""
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


def run(sizes=SIZES, config=None):
    config = config or clients.load("demo")
    return [measure(size, config) for size in sizes]


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m src.benchmark")
    p.add_argument("--sizes", default=",".join(str(s) for s in SIZES))
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)
    sizes = [int(s) for s in a.sizes.split(",") if s.strip()]

    # Records are built in memory and never saved, so there is no queue to
    # point anywhere: store.new_record() is a constructor, not a write.
    results = run(sizes)

    if a.json:
        print(json.dumps(results, indent=2))
        return 0

    print("offline benchmark: fake providers, so this is our overhead only\n")
    print(f"{'domains':>8} {'seconds':>9} {'rec/s':>9} {'selected':>9} "
          f"{'person res':>11} {'email':>8} {'linkedin':>9} {'mem MB':>8}")
    for row in results:
        c = row["counters"]
        print(f"{row['size']:>8} {row['seconds']:>9} "
              f"{row['records_per_second'] or '-':>9} "
              f"{c['contacts_selected']:>9} {c['person_research_planned']:>11} "
              f"{c['email_steps']:>8} {c['linkedin_steps']:>9} "
              f"{row['memory_mb'] or '-':>8}")
    print("\nper-stage timings for the largest run:")
    for stage, seconds in results[-1]["timings"].items():
        print(f"  {stage:<18} {seconds:>8}s")
    print("\nNo provider was called. These numbers are architecture overhead, "
          "not real-world duration.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
