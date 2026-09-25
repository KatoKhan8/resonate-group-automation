#!/usr/bin/env python3
"""TASK-305 probe: 20 calls to Groq at concurrency 50.

This is the acceptance test.  It measures:
  - calls attempted / succeeded / failed
  - latency p50, p95, max
  - cost total and per call, from the ledger
  - tokens prompt and completion, from the response
  - the exact model string the provider echoed back

Acceptance criterion (verifiable in one command):

    py -3 -c "import sys;sys.path.insert(0,'.');from src import spendledger as s;\\
    rows=[r for r in s.load() if r.get('provider')=='groq'];\\
    print(len(rows),'ledgered groq calls');assert len(rows)>=20"

## STATUS 2026-09-25

GROQ_API_KEY is NOT SET in config/.env.  The probe CANNOT run successfully.
The adapters are built and ready; the live probe is blocked on the credential.
"""
import concurrent.futures
import os
import statistics
import sys
import time

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from src.providers import load_env
load_env()

from src.providers import groq
from src import spendledger


PROMPT = "What is 2+2? Reply with the number only."
N_CALLS = 20
CONCURRENCY = 50


def one_call(i):
    """One probe call.  Returns (success, result_or_error, latency)."""
    started = time.monotonic()
    try:
        result = groq.complete(PROMPT, reasoning_effort="low",
                               client="task305-probe")
        latency = round(time.monotonic() - started, 3)
        return True, result, latency
    except Exception as e:
        latency = round(time.monotonic() - started, 3)
        return False, f"{type(e).__name__}: {str(e)[:120]}", latency


def main():
    print("=" * 72)
    print("  TASK-305 GROQ PROBE")
    print(f"  {N_CALLS} calls at concurrency {CONCURRENCY}")
    print("=" * 72)

    # Check credential first
    try:
        from src.providers import key
        key(groq.ENV_KEY)
        print(f"  {groq.ENV_KEY}: configured")
    except Exception as e:
        print(f"  {groq.ENV_KEY}: NOT SET - {e}")
        print()
        print("  The probe CANNOT run.  The adapter is built; the credential")
        print("  is missing.  This is the honest state, not a silent skip.")
        return 1

    print(f"  model: {groq.configured_model()}")
    print(f"  base:  {groq.base_url()}")
    print()

    started_all = time.monotonic()
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        futures = [pool.submit(one_call, i) for i in range(N_CALLS)]
        for f in concurrent.futures.as_completed(futures):
            results.append(f.result())
    total_time = round(time.monotonic() - started_all, 3)

    succeeded = [r for r in results if r[0]]
    failed = [r for r in results if not r[0]]

    print(f"  calls attempted:  {len(results)}")
    print(f"  succeeded:        {len(succeeded)}")
    print(f"  failed:           {len(failed)}")
    print(f"  total time:       {total_time}s")
    print()

    if succeeded:
        latencies = [r[2] for r in succeeded]
        latencies.sort()
        p50 = statistics.median(latencies)
        p95_idx = int(len(latencies) * 0.95)
        p95 = latencies[min(p95_idx, len(latencies) - 1)]
        pmax = max(latencies)

        print(f"  latency  p50={p50:.3f}s  p95={p95:.3f}s  max={pmax:.3f}s")

        prompt_tokens = []
        completion_tokens = []
        models_seen = set()
        for _, result, _ in succeeded:
            usage = result.get("usage") or {}
            pt = usage.get("prompt_tokens")
            ct = usage.get("completion_tokens")
            if pt is not None:
                prompt_tokens.append(pt)
            if ct is not None:
                completion_tokens.append(ct)
            m = result.get("model")
            if m:
                models_seen.add(m)

        total_prompt = sum(prompt_tokens)
        total_completion = sum(completion_tokens)
        print(f"  tokens   prompt={total_prompt}  completion={total_completion}")
        print(f"  model    {', '.join(sorted(models_seen)) or 'unknown'}")
    else:
        print("  (no successful calls to report latency/tokens)")

    if failed:
        print()
        print("  failures:")
        for _, err, lat in failed[:5]:
            print(f"    {lat:.3f}s  {err}")
        if len(failed) > 5:
            print(f"    ... and {len(failed) - 5} more")

    # Ledger check
    print()
    rows = [r for r in spendledger.load() if r.get("provider") == "groq"
            and r.get("client") == "task305-probe"]
    print(f"  ledgered groq calls (this probe): {len(rows)}")
    if rows:
        total_cost = sum(int(r.get("expected_cost") or 0) for r in rows)
        print(f"  total cost (ledger):              {total_cost} microusd")
        sample = rows[0]
        print(f"  sample row metadata:")
        for k in ("prompt_tokens", "completion_tokens", "served_model",
                   "reasoning_effort", "latency_seconds"):
            print(f"    {k}: {sample.get(k)}")

    print()
    if len(succeeded) >= N_CALLS:
        print("  ACCEPTANCE: PASSED")
        return 0
    else:
        print(f"  ACCEPTANCE: FAILED ({len(succeeded)}/{N_CALLS} calls succeeded)")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
