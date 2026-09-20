# GLM adversarial review - writeguard

2026-09-20T15:09:43.394846+00:00. One call per function.

A SECOND OPINION, NOT A VERDICT. Every line below is a lead to check against the code and the tests by hand.

---

## providers.refuse_unauthorized_write

`glm-5.3`, 71.082s, usage {'prompt_tokens': 382, 'completion_tokens': 4361, 'total_tokens': 4743, 'reasoning_tokens': 3837, 'cached_tokens': 0}.

**1. Finding: yes — the guard is defeated by its own opt-in mechanism, from inside the process.**

**2. Trigger.** The docstring names the adversary explicitly: "an audit agent … simply by importing src and calling through." That same adversary self-authorizes in one line before calling:

```python
import os
os.environ["RESONATE_PROVIDER_WRITES"] = "1"          # or:
with providers.allow_writes("any string"):            # reason is unauthenticated
    providers.transport("POST", prospect_facing_url)  # writes_allowed() -> True
```

Call order/state: guard → `is_prospect_facing` True → `writes_allowed()` True (env var present / context active) → early `return`, **no refusal, no `_log_refusal` entry**. Consequence: the write to the prospect goes out — the exact campaign-487 incident class recurs, this time with zero forensic trace (the bypass path is silent). Any imported dependency, plugin, or agent gets this for free; per-bypass cost is one mutating call to a real prospect, unbounded in count.

**3. Smallest fix.** Snapshot the env flag once at entry-point import into an immutable module constant (`_WRITES = os.environ.get(...)` read at startup, never re-read), and make `allow_writes(reason)` require a token/flag handed only to the entry point rather than a free string. Risks: (a) deployments that set `RESONATE_PROVIDER_WRITES` after import now fail closed — authorized campaigns halt (availability cost, but in the safe direction); (b) no in-process fix survives `monkeypatch.setattr(providers, "writes_allowed", ...)`, so honest residual risk is "process boundary or nothing" — the guard is then audit/deterrent, not enforcement.

**Secondary, mechanical:** `str(method).upper()` mis-normalizes bytes. Input `method=b"post"`: guard compares `"B'POST'"` ∉ WRITE_METHODS → returns; requests (`to_native_string(...).upper()`) and httpx both normalize `b"post"` → `POST` on the wire. Fix: decode+strip before comparing (`method = to_str(method).strip().upper()`), matching the transport's normalization. Also note the guard is method-gated: a GET-with-side-effects provider endpoint (legacy ESP send/webhook style) skips the guard at line 1 entirely — worth checking `is_prospect_facing` coverage for those hosts.

## providers.is_prospect_facing

`glm-5.3`, 67.864s, usage {'prompt_tokens': 206, 'completion_tokens': 4250, 'total_tokens': 4456, 'reasoning_tokens': 3693, 'cached_tokens': 128}.

**1. Finding: uncaught `ValueError` — the function violates its bool contract and crashes the caller on dirty URLs.**

**2. Trigger and consequence.**
- `is_prospect_facing("http://[unsubscribe]")` — unmatched `[`/`]` in the authority — makes `urllib.parse.urlsplit` itself raise `ValueError: Invalid IPv6 URL` (the bracket check runs inside `urlsplit`, before `.hostname` is ever reached).
- Second input class: netlocs that NFKC-normalize into `/?#@:` — e.g. `"https://user＠linkedin.com"` (fullwidth `＠` U+FF20) → `ValueError: netloc contains invalid characters under NFKC normalization` (Python ≥ 3.6.13/3.7.11 security backports).

Call order: any loop that pulls URLs from scraped pages / CRM fields / email signatures and calls this per record. Bracket placeholders like `http://[tracking-link]` are extremely common in raw signature HTML. At 10k scraped URLs per campaign and even a 0.1% corruption rate, that's ~10 raised exceptions per run — one aborts the enrichment batch (or 500s the endpoint, or burns retries) depending on the caller. The function is designed to be total over garbage input (`str(url or "")` proves the intent) but isn't.

**Secondary (provable, smaller):** exact-string host match with no trailing-dot strip. `is_prospect_facing("https://linkedin.com.")` returns `False` even if `linkedin.com ∈ _prospect_facing_hosts`, because a trailing-dot FQDN (what DNS tooling emits) is a different string. Same class: punycode vs unicode IDN hosts never match. Cost is silent misclassification, not a crash.

**3. Smallest fix:**
```python
try:
    host = urllib.parse.urlsplit(str(url or "")).hostname
except ValueError:
    return False
```
Risks: (a) the fail-safe direction is now a policy choice — `False` on a malformed URL is fail-closed; if any downstream branch reads "not prospect-facing" as "safe to attach internal data," you've converted a crash into a leak; (b) swallowing the exception hides the data-quality problem instead of logging it. Add a counter/log line at minimum. For the secondary, `host.rstrip(".")` — risks nothing measurable, but only helps if the set itself is dot-free, which is unverifiable from this snippet.

## providers.allow_writes

`glm-5.3`, 54.171s, usage {'prompt_tokens': 379, 'completion_tokens': 3416, 'total_tokens': 3795, 'reasoning_tokens': 2957, 'cached_tokens': 128}.

**1. Finding: the authorization is process-global, not caller-scoped — it leaks across concurrent tasks/threads.**

**2. Trigger and consequence.** `_write_scopes` is a plain module-level list (as the bare `append`/`pop` implies), and the gate (`writes_allowed()`) reads that shared stack. Call order, asyncio flavor:

- Task A enters `allow_writes("resume 487 per OPERATOR-AUTH …")`, then awaits inside `bison.resume_campaign(487, expect_leads=10)` — a network call, so the loop switches.
- Task B (campaign 512's dispatch loop, never authorized) calls `bison.pause_campaign(512)`.
- Gate reads the shared stack → non-empty → the write executes.

Identical with threads: any write from *any* thread during an open window passes. Two costs: (a) unauthorized writes succeed — precisely the 487-pause class of incident the docstring says this guard exists to prevent; (b) audit misattribution — B's write is recorded under A's reason, so the incident question "who authorised this and for what" gets a *wrong* answer, which is worse than none. Scale: with K campaigns dispatched concurrently, effectively every write issued while any scope is open anywhere is authorized; the exposure window is the duration of the slowest scoped network call (seconds per block, continuously overlapping under load).

Single-threaded synchronous use is sound — the defeat requires interleaving, which production dispatch (asyncio or sender threads) supplies.

**3. Smallest fix.** Replace the list with a `contextvars.ContextVar` (in CPython this isolates both asyncio Tasks and threads); `__enter__`/`__exit__` become `set()`/`reset(token)`. Risks: it fails *closed* into code that silently relied on the global scope — e.g., a worker thread or spawned task inside the block that flushes writes will now be refused, surfacing as a throughput drop until authorization is threaded through explicitly; and any consumer of "all open reasons" (if `writes_allowed()` exposes the stack) must be reduced to the single visible value.

