#!/usr/bin/env python3
"""TASK-305 probe: 20 calls to Groq at concurrency 50, reasoning effort low.

Reports:
    calls attempted / succeeded / failed
    latency  p50, p95, max      (per call, measured)
    cost     total, and per call, from the ledger
    tokens   prompt and completion, from the response
    the exact model string the provider echoed back

Acceptance:
    py -3 -c "import sys;sys.path.insert(0,'.');from src import spendledger as s;\\
    rows=[r for r in s.load() if r.get('provider')=='groq'];\\
    print(len(rows),'ledgered groq calls');assert len(rows)>=20"
"""
import os
import sys
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from src.providers import load_env
load_env()

from src.providers import groq


def one_call(i):
    """One probe call.  Returns a dict with timing and usage."""
    started = time.monotonic()
    try:
        result = groq.complete(
            prompt=f"Probe call {i}.  Reply with exactly: OK",
            system="You are a probe test.  Reply briefly.",
            model="openai/gpt-oss-120b",
            max_tokens=2048,  # Reasoning tokens count against this; 16 is too low.
            reasoning_effort="low",
            client="groq-probe",
        )
        elapsed = round(time.monotonic() - started, 3)
        return {
            "i": i,
            "ok": True,
            "seconds": elapsed,
            "model": result.get("model"),
            "usage": result.get("usage", {}),
            "error": None,
        }
    except Exception as e:
        elapsed = round(time.monotonic() - started, 3)
        return {
            "i": i,
            "ok": False,
            "seconds": elapsed,
            "model": None,
            "usage": {},
            "error": f"{type(e).__name__}: {str(e)[:120]}",
        }


def main():
    n_calls = 20
    concurrency = 50

    print(f"TASK-305 Groq probe: {n_calls} calls at concurrency {concurrency}")
    print(f"Model: {groq.DEFAULT_MODEL}")
    print(f"Reasoning effort: {groq.DEFAULT_REASONING_EFFORT}")
    print()

    started = time.monotonic()
    results = []
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = {pool.submit(one_call, i): i for i in range(n_calls)}
        for future in as_completed(futures):
            results.append(future.result())
    total_seconds = round(time.monotonic() - started, 3)

    results.sort(key=lambda r: r["i"])

    succeeded = [r for r in results if r["ok"]]
    failed = [r for r in results if not r["ok"]]

    print(f"calls attempted:  {n_calls}")
    print(f"calls succeeded:  {len(succeeded)}")
    print(f"calls failed:     {len(failed)}")
    print(f"wall time:        {total_seconds}s")
    print()

    if succeeded:
        latencies = [r["seconds"] for r in succeeded]
        latencies.sort()
        p50 = statistics.median(latencies)
        p95_idx = max(0, int(len(latencies) * 0.95) - 1)
        p95 = latencies[p95_idx]
        print(f"latency (per call, seconds)")
        print(f"  p50:   {p50:.3f}")
        print(f"  p95:   {p95:.3f}")
        print(f"  max:   {max(latencies):.3f}")
        print(f"  min:   {min(latencies):.3f}")
        print()

        # Token usage from responses
        prompt_tokens = [r["usage"].get("prompt_tokens", 0) or 0 for r in succeeded]
        completion_tokens = [r["usage"].get("completion_tokens", 0) or 0 for r in succeeded]
        total_tokens = [r["usage"].get("total_tokens", 0) or 0 for r in succeeded]
        print(f"tokens (from response, not estimated)")
        print(f"  prompt:     sum={sum(prompt_tokens)}, per_call_avg={sum(prompt_tokens)/len(succeeded):.0f}")
        print(f"  completion: sum={sum(completion_tokens)}, per_call_avg={sum(completion_tokens)/len(succeeded):.0f}")
        print(f"  total:      sum={sum(total_tokens)}")
        print()

        # Model echoed back
        models = {r["model"] for r in succeeded if r["model"]}
        print(f"model(s) echoed by provider: {', '.join(sorted(models))}")
        print()

    if failed:
        print("FAILURES:")
        for r in failed:
            print(f"  call {r['i']}: {r['error']}")
        print()

    # Ledger check
    from src import spendledger
    rows = [r for r in spendledger.load() if r.get("provider") == "groq"]
    probe_rows = [r for r in rows if r.get("client") == "groq-probe"]
    print(f"ledger: {len(rows)} total groq rows, {len(probe_rows)} from this probe")
    if probe_rows:
        sample = probe_rows[0]
        print(f"  sample row keys: {sorted(sample.keys())}")
        print(f"  sample prompt_tokens: {sample.get('prompt_tokens')}")
        print(f"  sample completion_tokens: {sample.get('completion_tokens')}")

    # Acceptance assertion
    assert len(rows) >= 20, f"Expected >=20 ledgered groq calls, got {len(rows)}"
    print()
    print("ACCEPTANCE: >= 20 ledgered groq calls confirmed.")


if __name__ == "__main__":
    main()
