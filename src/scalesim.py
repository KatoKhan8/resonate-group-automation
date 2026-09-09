#!/usr/bin/env python3
"""Five thousand domains through the whole pre-production path, offline.

`src/benchmark.py` measures the pipeline's own overhead on uniform records.
This measures the *simulator* path on the messy synthetic dataset, which is a
different question: how long does it take to produce the thing a human reads
before approving a campaign, how big is that thing, how many provider calls
would it imply, and what would they cost.

No network, no model, no provider, no DNS. Every number below is produced by
running the real code against synthetic records; nothing is extrapolated from a
smaller run, because extrapolation is how a linear-looking system turns out to
be quadratic at the size that matters.

  python -m src.scalesim --size 5000
  python -m src.scalesim --sizes 100,1000,5000 --json
"""
import argparse
import json
import os
import time

from . import (cadence, channels, clients, companies, enrich, mx,
               previewpage, qualify, quality, simulator, store,
               synthetic, waterfall)

SIZES = (100, 1000, 5000)

# Where the time is expected to go, so an unexpected line stands out.
PHASES = ("build_dataset", "save", "load", "mx_resolve", "channels",
          "quality", "simulate", "render_html", "write_files")

# The company-first pass, measured separately: it runs before a person costs
# anything, so its cost is the one that decides whether 5,000 domains is a
# reasonable thing to upload.
QUALIFY_PHASES = ("build_companies", "qualify", "summarise", "segment")


def qualify_scale(size, config=None, client="benchmark"):
    """The whole pre-enrichment path over `size` companies, offline.

    Reports what the brief asks for: runtime, memory, the verdict spread, the
    distributions and what person enrichment would cost if every qualified
    company were approved.
    """
    config = config or {}
    timings = {}

    start = time.perf_counter()
    recs = companies.dataset(size, config, client=client, batch="scale")
    timings["build_companies"] = time.perf_counter() - start

    start = time.perf_counter()
    result = qualify.run(recs, client=client, batch="scale", config=config,
                         store_result=False)
    timings["qualify"] = time.perf_counter() - start

    start = time.perf_counter()
    summary = qualify.summarise(result, config)
    timings["summarise"] = time.perf_counter() - start

    start = time.perf_counter()
    ordered = qualify.prioritise(result["companies"])
    timings["segment"] = time.perf_counter() - start

    total = sum(timings.values())
    return {
        "size": size,
        "seconds": round(total, 2),
        "companies_per_second": round(size / total, 1) if total else None,
        "timings": {name: round(timings.get(name, 0.0), 3)
                    for name in QUALIFY_PHASES},
        "memory_mb": _memory_mb(),
        "status": summary["icp"]["status"],
        "tier": summary["icp"]["tier"],
        "confidence": summary["icp"]["confidence"],
        "needs_manual_review": summary["icp"]["needs_manual_review"],
        "schedulable": summary["schedulable"],
        "not_schedulable": summary["not_schedulable"],
        "distribution": summary["distribution"],
        "segments": {
            "count": summary["segments"]["segments"],
            "below_minimum": len(summary["segments"]["below_minimum"]),
            # Which rungs those segments stopped at, because the count alone
            # cannot say whether the ladder failed or simply ran out. A
            # segment at the last rung has nowhere left to merge: a persona
            # rarer than the floor cannot reach it, and that is the model
            # describing the market rather than the merge going wrong.
            "below_minimum_rungs": sorted({
                (summary["segments"]["sizes"].get(key) or {}).get("rung")
                for key in summary["segments"]["below_minimum"]} - {None}),
            "eligible_for_splitting":
                len(summary["segments"]["eligible_for_splitting"]),
            "largest": next(iter(summary["segments"]["sizes"].items()), None),
        },
        "cost": summary["cost"],
        "highest_priority": [e["record"]["domain"] for e in ordered[:3]],
        "bottleneck": max(timings, key=timings.get) if timings else None,
    }


def _memory_mb():
    """Resident memory where the platform will say, None rather than a guess."""
    try:
        import resource
        usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return round(usage / (1024 * 1024 if usage > 1 << 20 else 1024), 1)
    except Exception:
        pass
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
        # The handle must be typed. GetCurrentProcess returns -1 as a plain
        # int, and passing that untyped truncates to 32 bits on a 64-bit
        # build, so the call fails and memory silently reads as unknown.
        handle = ctypes.wintypes.HANDLE(
            ctypes.windll.kernel32.GetCurrentProcess())
        if ctypes.windll.psapi.GetProcessMemoryInfo(
                handle, ctypes.byref(counters), counters.cb):
            return round(counters.PeakWorkingSetSize / (1024 * 1024), 1)
    except Exception:
        pass
    return None


class CountingResolver:
    """A DNS resolver that answers instantly and counts who asked.

    The point is the count, not the answer: fifty contacts at one company must
    produce one lookup, and if the cache ever stops working this is where it
    shows up as a number rather than as a slow afternoon.
    """

    def __init__(self):
        self.calls = 0
        self.domains = set()

    def __call__(self, domain, **kw):
        self.calls += 1
        self.domains.add(domain)
        # Deterministic from the domain, so a run is repeatable.
        if domain.startswith("syn") and domain.endswith(".test"):
            index = int(domain[3:8]) if domain[3:8].isdigit() else 0
            if index % 7 == 0:
                return ["mx1-us1.ppe-hosted.com"]
        return ["aspmx.l.google.com"]


def _provider_calls(recs, config):
    """What running this batch for real would ask of each provider.

    Planned, not performed. `enrich.plan` is the same function the live path
    uses, so this is the actual call list rather than an estimate of one.
    """
    calls, expected, maximum = {}, 0, 0
    for rec in recs:
        ops = enrich.plan(rec, config) or []
        for op in ops:
            key = f"{op['provider']}:{op['call']}"
            bucket = calls.setdefault(key, {"planned": 0, "conditional": 0,
                                            "credits": 0})
            bucket["planned"] += 1
            bucket["conditional"] += int(bool(op.get("conditional")))
            bucket["credits"] += op.get("cost") or 0
        exposure = enrich.exposure(ops)
        expected += exposure["expected"]
        maximum += exposure["maximum"]
    return {"by_call": calls, "expected_credits": expected,
            "maximum_credits": maximum}


def measure(size, config=None, out_dir=None, max_cards=previewpage.MAX_CARDS):
    """One full pre-production pass over `size` domains. Returns the numbers."""
    config = config or clients.load("demo")
    timings = {}

    start = time.perf_counter()
    recs = synthetic.dataset(size, config)
    timings["build_dataset"] = time.perf_counter() - start

    start = time.perf_counter()
    store.save(recs)
    timings["save"] = time.perf_counter() - start

    start = time.perf_counter()
    recs = store.load()
    timings["load"] = time.perf_counter() - start

    # MX with a counting resolver and one shared cache, which is how the live
    # path runs it: domain-level, so contacts at one company resolve once.
    resolver = CountingResolver()
    cache = {}
    start = time.perf_counter()
    domains = 0
    for rec in recs:
        for contact in rec.get("contacts") or []:
            domain = mx.email_domain(contact.get("email"))
            if not domain:
                continue
            domains += 1
            contact["mx"] = mx.for_domain(domain, config, cache=cache,
                                          resolver=resolver, save=False)
    timings["mx_resolve"] = time.perf_counter() - start

    start = time.perf_counter()
    coverage = channels.summarise(recs, config)
    timings["channels"] = time.perf_counter() - start

    start = time.perf_counter()
    bands = quality.distribution(recs, config)
    timings["quality"] = time.perf_counter() - start

    start = time.perf_counter()
    result = simulator.simulate(recs=recs, client="demo", config=config)
    timings["simulate"] = time.perf_counter() - start

    start = time.perf_counter()
    page = previewpage.page(result, max_cards=max_cards)
    timings["render_html"] = time.perf_counter() - start

    sizes = {"preview_html_bytes": len(page.encode("utf-8"))}
    if out_dir:
        start = time.perf_counter()
        paths = previewpage.write_all(result, out_dir, max_cards=max_cards)
        timings["write_files"] = time.perf_counter() - start
        for name, path in paths.items():
            sizes[name] = os.path.getsize(path)
    else:
        timings["write_files"] = 0.0

    calls = _provider_calls(recs, config)
    total = sum(timings.values())

    return {
        "size": size,
        "seconds": round(total, 2),
        "domains_per_second": round(size / total, 1) if total else None,
        "timings": {name: round(timings.get(name, 0.0), 3) for name in PHASES},
        "memory_mb": _memory_mb(),
        "mx_cache": {
            "contacts_with_an_address": domains,
            "dns_lookups": resolver.calls,
            "unique_domains": len(resolver.domains),
            # The number that matters: one lookup per domain, never per contact.
            "lookups_per_contact": (round(resolver.calls / domains, 3)
                                    if domains else None),
            "hit_rate": (round(1 - resolver.calls / domains, 3)
                         if domains else None),
        },
        "provider_calls": calls,
        "coverage": {k: coverage[k] for k in
                     ("contacts", "email_eligible", "linkedin_eligible",
                      "multichannel", "held")},
        "personalization": bands["bands"],
        "preview": sizes,
        "queue_bytes": os.path.getsize(store.queue_path())
        if os.path.exists(store.queue_path()) else None,
        "bottleneck": max(timings, key=timings.get) if timings else None,
    }


def linearity(results):
    """Is each phase growing with the batch, or with its square?

    Reported per phase rather than in total, because one quadratic phase inside
    an otherwise linear run is exactly what a single total hides.
    """
    if len(results) < 2:
        return {}
    first, last = results[0], results[-1]
    ratio = last["size"] / first["size"] if first["size"] else 1
    out = {}
    for phase in PHASES:
        before = first["timings"].get(phase) or 0
        after = last["timings"].get(phase) or 0
        if before < 0.01:
            out[phase] = {"growth": None,
                          "why": "too fast at the small size to measure"}
            continue
        growth = (after / before) / ratio
        out[phase] = {
            "growth": round(growth, 2),
            "verdict": ("linear or better" if growth <= 1.3
                        else "superlinear" if growth <= 2.5
                        else "quadratic: fix before running this size"),
        }
    return out


def run(sizes=SIZES, config=None, out_dir=None):
    results = [measure(size, config, out_dir) for size in sizes]
    return {"results": results, "linearity": linearity(results)}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--size", type=int)
    p.add_argument("--sizes", help="comma separated, e.g. 100,1000,5000")
    p.add_argument("--out", help="also write the five preview files here")
    p.add_argument("--qualify", action="store_true",
                   help="measure the company-first qualification path instead")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)

    if a.qualify:
        sizes = ([a.size] if a.size else
                 [int(s) for s in a.sizes.split(",")] if a.sizes else [5000])
        for size in sizes:
            result = qualify_scale(size)
            if a.json:
                print(json.dumps(result, indent=2))
                continue
            print(f"\n{result['size']} companies in {result['seconds']}s "
                  f"({result['companies_per_second']}/s), peak memory "
                  f"{result['memory_mb']} MB")
            for phase in QUALIFY_PHASES:
                print(f"    {phase:<18} {result['timings'][phase]:>8.3f}s")
            print(f"    status   {result['status']}")
            print(f"    tier     {result['tier']}")
            print(f"    review   {result['needs_manual_review']} company/companies")
            print(f"    schedulable {result['schedulable']} "
                  f"(no timezone: {result['not_schedulable']})")
            print(f"    segments {result['segments']['count']} "
                  f"({result['segments']['below_minimum']} below minimum)")
            cost = result["cost"]
            print(f"    planned DM searches {cost['planned_dm_searches']}, "
                  f"max contacts {cost['maximum_contacts']}")
            print(f"    credits: {cost['expected_credits']} expected, "
                  f"{cost['maximum_credits']} maximum "
                  f"({cost['fallback_exposure']} of that is fallback)")
            print(f"    slowest phase: {result['bottleneck']}")
        print("\nNo provider, model or network was touched.")
        return 0

    sizes = ([a.size] if a.size else
             [int(s) for s in a.sizes.split(",")] if a.sizes else list(SIZES))
    report = run(sizes, out_dir=a.out)
    if a.json:
        print(json.dumps(report, indent=2))
        return 0

    for result in report["results"]:
        print(f"\n{result['size']} domains in {result['seconds']}s "
              f"({result['domains_per_second']}/s), "
              f"peak memory {result['memory_mb']} MB")
        for phase in PHASES:
            print(f"    {phase:<16} {result['timings'][phase]:>8.3f}s")
        cache = result["mx_cache"]
        print(f"    MX: {cache['dns_lookups']} lookup(s) for "
              f"{cache['contacts_with_an_address']} contact(s) across "
              f"{cache['unique_domains']} domain(s) "
              f"(hit rate {cache['hit_rate']})")
        calls = result["provider_calls"]
        print(f"    provider calls: {sum(c['planned'] for c in calls['by_call'].values())} "
              f"planned, {calls['expected_credits']} credits expected, "
              f"{calls['maximum_credits']} at most")
        print(f"    preview.html {result['preview']['preview_html_bytes']:,} bytes"
              f" · queue {result['queue_bytes']:,} bytes"
              if result["queue_bytes"] else "")
        print(f"    slowest phase: {result['bottleneck']}")
    if report["linearity"]:
        print("\ngrowth per phase, relative to the batch:")
        for phase, verdict in report["linearity"].items():
            if verdict.get("growth") is None:
                continue
            print(f"    {phase:<16} x{verdict['growth']:<6} {verdict['verdict']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
