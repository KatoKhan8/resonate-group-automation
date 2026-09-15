# AI Spend Ledger — Design, 2026-09-15

## The question this answers

> "What did Productive cost us in AI today, and which stages spent it?"

Right now the answer is "App: Unknown" on an OpenRouter dashboard. That is
the entire visibility.

## What already exists

### The provider spend ledger (`src/spendledger.py`)

Tracks **provider credits** (ContactOut, Reoon, Deliverable, etc.) as
expected costs at the moment of the call. Shape:

    {at, day, client, provider, call, expected_cost, run_id}

- `expected_cost` is in **credits**, not currency.
- It is a **pre-call estimate**, not an observed charge.
- It has budget enforcement (`check()`) with per-day, per-provider, and
  total ceilings.
- It lives in `work/spend-ledger.jsonl` alongside the queue.

**Does the model lane belong here?** No. The shapes are different:

| Dimension        | Provider ledger        | Model ledger needs           |
|------------------|------------------------|------------------------------|
| Unit             | Credits (integer)      | Currency (float, USD)        |
| Granularity      | Provider + call type   | Model + stage + record       |
| Token tracking   | None                   | Input, output, cached        |
| Latency          | None                   | Seconds                      |
| Price versioning | Not needed (fixed)     | Required (prices change)     |
| Budget enforce   | Yes (refuse on exceed) | No (observe only, for now)   |

A second spend ledger is a second answer to one question — but these are
**different questions**. The provider ledger answers "how many credits has
this client consumed?" The model ledger answers "how much money did AI
spend, on what, and for whom?" Merging them would mean adding token counts
to a credit ledger that has no concept of tokens, or adding credit counts
to a currency ledger that has no concept of credits. Neither is clean.

**Verdict: beside it, not in it.** A new `src/aispendledger.py` that follows
the same patterns (JSONL, `store.refuse_production_write`, `store.now()`)
but lives at `work/ai-spend-ledger.jsonl`.

### The model chokepoint (`src/llm.py`)

`llm.ask(model, step, prompt, ...)` is the **sole entry point** for every
model call in the codebase.

**Bypass check result:**

    grep -rn "\.complete(" src/

Returns ONE hit: `src/llm.py:827` — inside `ask()` itself. No code in `src/`
calls `model.complete()` directly. The three modules that import `llm`:

    src/generate.py    — calls llm.ask for diagnose, hook, persona_angle,
                         linkedin_note, draft
    src/run.py         — constructs OpenAICompatibleModel, passes to generate
    src/variantgen.py  — receives llm.ask as a parameter (llm_ask)

**No bypasses exist.** A wrapper around `llm.ask` catches everything.

### What OpenRouter already gives us

`OpenAICompatibleModel.complete()` already captures usage data in
`self.calls`:

    {"model", "seconds", "chars", "prompt_tokens", "completion_tokens",
     "total_tokens", "cost"}

The `cost` field is OpenRouter's reported charge for that request. This
data **exists today** and is thrown away at the end of every run. The
ledger's job is to persist it.

## The design

### Record shape

Per call, recorded durably:

```json
{
  "at": "2026-09-15T14:23:01+00:00",
  "day": "2026-09-15",
  "client": "productive",
  "stage": "draft",
  "task": "generate.draft",
  "record_id": "a3f8c1...",
  "model": "anthropic/claude-3.5-sonnet",
  "provider": "openrouter",
  "prompt_version": "v1",
  "input_tokens": 1842,
  "output_tokens": 356,
  "cached_tokens": null,
  "latency": 2.341,
  "retry_count": 0,
  "estimated_cost": 0.00891,
  "cost_source": "openrouter_reported",
  "price_table_version": "openrouter-2026-09-15",
  "success": true,
  "cache_hit": false
}
```

### Field decisions

- **`record_id`**: SHA-256 of the record's `id` field, truncated to 16
  hex chars. Same pattern as `generate.fingerprint()` and 14 other
  modules. The ledger answers "which stage spent this" without becoming a
  second copy of the estate.
- **`client`**: The workspace/client name. Already available on every
  record as `rec.get("client")`.
- **`stage`**: The `llm.ask` step parameter: `diagnose`, `hook`,
  `persona_angle`, `draft`, `linkedin_note`. This is what answers
  "which stages spent it."
- **`task`**: The calling function: `generate.draft`, `generate.hook`,
  etc. More specific than stage; useful for finding which code path
  spent the money.
- **`prompt_version`**: Initially `"v1"`. No prompt versioning exists
  today. When prompts change, this version bumps. A cost computed from
  a prompt that later changed is a number nobody can reproduce — this
  field makes that reproducible.
- **`estimated_cost`**: OpenRouter's reported `cost` when available
  (`cost_source: "openrouter_reported"`). Falls back to a local price
  table calculation (`cost_source: "price_table"`) when the endpoint
  does not report cost.
- **`price_table_version`**: Identifies which price table priced this
  row. A cost computed from a price that later changed is a number
  nobody can reproduce.
- **`cached_tokens`**: OpenRouter reports `cached_tokens` in some
  responses. Null when absent.
- **`cache_hit`**: Derived from `cached_tokens > 0` when available.

### What must NOT go in it

- **No prompt contents.** Not truncated, not "just the first line."
  Prompts carry prospect names, domains and reply text.
- **No raw identifiers.** The record id is hashed.
- **No API keys, no bearer tokens.** The ledger is observability, not
  a credential store.

### Where it lives

`work/ai-spend-ledger.jsonl` — beside the existing
`work/spend-ledger.jsonl`. Same directory, same `store` patterns, same
`refuse_production_write` guard. `work/` is gitignored; production
state belongs there.

### Price table

OpenRouter's response already includes `usage.cost` — the actual charge
for that request. This is the primary cost source and needs no local
price table at all for OpenRouter-routed calls.

A local price table is a fallback for:
1. Endpoints that do not report cost (local models, non-OpenRouter
   providers).
2. Reproducibility — verifying that OpenRouter's reported cost matches
   what the published prices say.
3. Pre-call estimation (what WILL this cost?) before the call happens.

The price table lives in `config/ai-prices.json`:

```json
{
  "version": "openrouter-2026-09-15",
  "models": {
    "anthropic/claude-3.5-sonnet": {
      "input_per_1m": 3.00,
      "output_per_1m": 15.00,
      "cached_input_per_1m": 0.30
    }
  }
}
```

Versioned, so a row's `price_table_version` can be checked against the
current version. A row priced with a stale table is still a real cost —
it just needs to be re-priced if you want today's numbers.

**This task does not create the price table file.** That belongs in
`config/` which is forbidden. The writer accepts a price table as a
parameter and works without one (using OpenRouter's reported cost).

### The wrapper

The wrapper goes in `llm.ask` — the sole chokepoint. It would:

1. Call `model.complete()` as today.
2. Extract usage data from the model's `calls` list (already populated).
3. Hash the record id if a `rec` is available.
4. Append one row to the ledger.

The wrapper is approximately 30 lines. It is small enough to be
obviously correct. **It is not wired into the production path by this
task.** The task delivers a tested writer; Claude integrates.

### OpenRouter attribution verdict

OpenRouter supports three attribution headers:

| Header                | Purpose                                    |
|-----------------------|--------------------------------------------|
| `HTTP-Referer`        | App URL; primary identifier for rankings   |
| `X-OpenRouter-Title`  | Display name (legacy `X-Title` supported)  |
| `X-OpenRouter-Categories` | Marketplace categories                 |

Additionally, per-request `metadata` supports key-value pairs (max 16,
64-char keys, 512-char values) for observability. Known special keys:
`trace_id`, `trace_name`, `span_name`, `generation_name`,
`parent_span_id`. A `user` field provides per-end-user isolation.

**What this buys us:** The dashboard can distinguish "Resonate OS" from
other apps using the same API key. The `metadata` field can carry a
`trace_id` per request for observability tools.

**What it cannot do:** Per-client attribution (which workspace spent
this), per-stage attribution (draft vs hook vs diagnose), or
per-record attribution. The dashboard sees one app, not many stages.

**Verdict: our own ledger is better for the question we need to
answer.** OpenRouter attribution answers "how much did this app spend
total" — which is already visible in billing. It does not answer
"which stage spent what on which client" — which is the question that
drives optimisation. The two are complementary: set the headers so
OpenRouter knows who we are, and run our own ledger for the granularity
that matters.

**Recommendation:** Set `HTTP-Referer` to the workspace URL and
`X-OpenRouter-Title` to "Resonate OS" (already done in
`OpenAICompatibleModel._headers()` when `referer` is configured). Add
`metadata={"trace_id": ...}` per request when the ledger is wired in,
so the OpenRouter dashboard can at least correlate with our rows.

## The bypass check

    grep -rn "\.complete(" src/

Result: ONE hit at `src/llm.py:827`, inside `ask()`. No bypasses.

    grep -rn "llm\.ask(" src/

Hits in `src/generate.py` (6 call sites) and `src/variantgen.py`
(receives `llm.ask` as `llm_ask` parameter). All go through `ask()`.

**The chokepoint is real.** A wrapper around `ask()` catches every
model call in the codebase.

## What this task delivers

1. This design document.
2. A tested writer module (`scripts/task151_ai_spend_writer.py`) that
   appends rows to a JSONL ledger, with hashing and cost calculation.
3. Tests (`tests/test_ai_spend_ledger.py`) that verify the writer
   without calling a model.

What this task does NOT deliver:
- Wiring into the production `llm.ask` path. Claude integrates.
- A price table file in `config/`. The writer works without one.
- A reporting CLI. The data is JSONL; `jq` works today, a proper
  reporter comes later.
