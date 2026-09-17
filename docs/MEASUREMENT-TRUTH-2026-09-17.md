# Measurement Truth — what the 5,000-domain benchmark can actually measure

**Date:** 2026-09-17
**Instruction being served:** *"Measure first. Do not optimize from assumptions."*
**Scope:** no provider WRITE, no `--live`, nothing committed, HeyReach 605732 and
EmailBison 487 untouched. Providers were read-only and in fact were not called at all:
every number below comes from source read on 2026-09-17 and from the offline suite.

This document exists because the previous one (`docs/SCALE-HARDENING-2026-09-17.md`)
found two counters that nothing produced. A benchmark built on those would have
produced a `CACHE_HIT_RATE` of 0% and a set of routing counters that were never
computed at all — confident numbers that are fiction, which is worse than no numbers
because they would be believed.

The rule applied throughout: **a counter that is always zero is worse than an absent
one, and UNKNOWN is never silently a number.**

---

## 1. The truth table

Status vocabulary, used strictly:

| status | means |
|---|---|
| **INSTRUMENTED** | A producer writes it, a reader computes it, and a production caller runs the reader. |
| **PARTLY** | Real data exists but is incomplete, in-memory only, or unreached by any caller. The gap is named in the note. |
| **NOT INSTRUMENTED** | No producer. The number cannot be obtained today at any price short of new code. |

`†` = changed by this task. Line numbers are post-change.

| metric | status | where the number comes from | note |
|---|---|---|---|
| **TOTAL_DOMAINS** | INSTRUMENTED | `funnel.counts(recs)["input_domains"]` — `src/funnel.py:191`; cohort filter `funnel.cohort_of` `src/funnel.py:424` | Trivially correct: it is `len(recs)`. |
| **DETERMINISTIC_RESOLUTION_RATE** | **NOT INSTRUMENTED** | would be `count(resolved_by == 1) / count(rows)` off a reasoning ledger | **Nothing records a non-call.** `generate.plan` (`src/generate.py:804`) simply does not emit an op, which is indistinguishable from "nobody looked". Needs the `reasoning` waterfall stage designed in SCALE-HARDENING §2.4. Deliberately NOT built here: inventing the rate without the ledger would be exactly the fiction this task forbids. |
| **CONTACTOUT_RESOLUTION_RATE** | **INSTRUMENTED †** | `waterfall.counters(records)` — `src/waterfall.py:574`; called from `run.run` at `src/run.py:471` | **Was PARTLY.** The function computed six correct counters for no production caller; repo-wide its only callers were four assertions in `tests/test_contactout_fallback_semantics.py:256-292`. Now every run reports `CONTACTOUT_CALLS`, `CONTACTOUT_CONFIRMED_MISSES`, `CONTACTOUT_ERRORS`, `CRAWLER_CALLS`, `GROK_ESCALATIONS`, `OTHER_PROVIDER_ESCALATIONS` + `escalation_reasons`. |
| **CACHE_HIT_RATE** | **NOT INSTRUMENTED — and now says so †** | `waterfall.counters(...)["CONTACTOUT_CACHE_HITS"]` — `src/waterfall.py:634` | **The metric measures something that does not exist.** `grep -c cache src/providers/contactout.py` = **0**. No cache is read, none is written, and no caller ever passed the `cache_hits` parameter. The default was `0`; it is now `UNKNOWN`. See §3. |
| **RESEARCH_REQUIRED_RATE** | PARTLY | `research.why(rec)` — `src/research.py:183`, free and pure; five named reasons at `src/research.py:23-27` | Derivable today with no new counters, by a dry pass that iterates and tallies. No such script exists. This is a script-shaped gap, not a code-shaped one. |
| **LLM_REQUIRED_RATE** | PARTLY | `generate.model_calls` — `src/generate.py:86`, incremented by `count_model_call` `:159` | **In-memory, per-process, never persisted**; its only reader is `scripts/task197_generate.py:311`. The *denominator* is sound offline: `benchmark.llm_calls_would_be` (`src/benchmark.py:79`). The numerator now has a durable source for calls that actually happened — `rec["model_calls"]` (§4) — but "would have been needed" still requires the reasoning ledger. |
| **STRONG_MODEL_ESCALATION_RATE** | **NOT INSTRUMENTED** | — | **Not expressible.** There is no model tier. `llm.from_env()` (`src/llm.py:466`) selects ONE model for the whole run; nothing routes between a weak and a strong one, so there is no escalation event to count. `rec["model_calls"][*]["model"]` now records *which* model answered, which is the field a future router would be measured on — but a rate over one model is not a rate. |
| **ICP pass / fail / unknown** | INSTRUMENTED | `icp.summarise` `src/icp.py:863`; `icpstructural.summarise` `src/icpstructural.py:623`; `qualify.summarise` `src/qualify.py:377` | Three reconciling vocabularies. `icpstructural` already treats UNKNOWN as distinct from FAIL, which is the convention this document applies elsewhere. |
| **CONTACTS_FOUND_PER_DOMAIN** | INSTRUMENTED | `funnel.counts["people_found"]` — `src/funnel.py:200`, over `["qualified"]` | Estate baseline ≈ 2.5. |
| **VERIFIED_CONTACTS_PER_DOMAIN** | INSTRUMENTED | `funnel.counts["emails_2_of_2_verified"]` — `src/funnel.py:203` | Two independent confirmations, not a flag. |
| **CAMPAIGN_READY_PER_DOMAIN** | INSTRUMENTED | `funnel.counts["campaign_ready"]` → `funnel._campaign_ready` `src/funnel.py:220` | Asks `eligibility.decide` rather than reading a stored flag, so it cannot go stale. |
| **SECONDS_PER_DOMAIN** | PARTLY | `run.report["seconds"]["per_record"]` — `src/run.py:445` | It is `sum(stage_times) / len(targets)`: an average over the run, not a per-record measurement, and it cannot separate a slow domain from a slow stage. **The LLM half is now per-record**: `rec["model_calls"][*]["seconds"]`, aggregated by `llm.token_usage(...)["by_model"][m]["seconds"]`. The provider and store halves are still run-level only. |
| **COST_PER_DOMAIN — ContactOut** | PARTLY | `waterfall.spend(rec)["by_provider"]["contactout"]["expected"]` — `src/waterfall.py:430` | **Expected only.** `actual_cost` is a real ledger field and is always `None` from the `enrich.spend()` path. `costs.reconcile()` (`src/costs.py:234`) can close it against ContactOut's own counters but is never called in the pipeline. |
| **COST_PER_DOMAIN — crawl** | PARTLY | `waterfall.ledger` rows where `call == "webfetch-crawl"` vs `"apify-research"` | webfetch is genuinely free (`COSTS["webfetch-crawl"] = 0`, `src/enrich.py:42`). Apify is **UNPRICED by declaration** — `COSTS["apify-research"] = 0` because it bills compute units, stated at `src/enrich.py:48` and `:111-114`. **Starts are countable; money is not**, and must come from Apify out of band. Baseline to beware of: 0 webfetch rows against 298 apify rows across 550 records (`src/research.py:386`) — the free leg has never run at scale. |
| **COST_PER_DOMAIN — LLM** | PARTLY † | `rec["model_calls"][*]["cost"]`, aggregated by `llm.token_usage` — `src/llm.py:896` | **Was NOT INSTRUMENTED.** `enrich.spend()` never witnesses a model call, and `src/campaigns.py:763` literally stores `"llm_cost": "unknown"`. A charge is now recorded **when the endpoint reports one** — OpenRouter does, under `usage.cost` (`src/llm.py:315`). Where it does not, the field is absent, never 0. Converting tokens to money for an endpoint that does not bill inline still needs a price table; none exists in `src/`. |
| **COST_PER_DOMAIN — provider (send)** | PARTLY | `work/spend-ledger.jsonl` via `spendledger.report()` — `src/spendledger.py:191` | Expected **credits**, live-only (`src/enrich.py:920`). No currency. `cost_unit` is free text (`src/waterfall.py:297`): `xai-research` is priced at `2_000_000_000` ticks in the same integer column as 1-credit calls (`src/enrich.py:43`). Do not sum that column. |
| **TOKENS_PER_DOMAIN by model** | PARTLY † | `llm.token_usage(records)` — `src/llm.py:896`, called from `src/run.py:475` | **Was NOT INSTRUMENTED** — captured per call and dropped on the floor. Now durable per record and per model for the OpenAI-compatible path. **Unobtainable for the Qwen lane**: `QwenCliModel.complete` (`src/llm.py:458`) records model, seconds and chars only, because the CLI returns text and there is no usage object to read. That lane reports UNKNOWN, not 0. See §4. |

### What `enrich.spend()` captures, exactly

`spend(call, why, provider="contactout", reason_code=None)` is a closure inside
`enrich_record` at `src/enrich.py:865`. It is the one door every paid provider call
passes through — a call that reaches a provider without passing here would not be
charged either, so there is nowhere for one to hide.

**It writes four sinks:**

| sink | line | durable? | payload |
|---|---|---|---|
| `budget.charge(...)` | `src/enrich.py:895` | No — in-memory, dies with the process | credits only |
| `spendledger.record(client, provider, call, cost)` | `src/enrich.py:933` | Yes → `work/spend-ledger.jsonl`. **`live` only** (`:920`) | `at, day, client, provider, call, expected_cost, run_id` |
| `done.append({...})` | `src/enrich.py:934` | No — returned as the run report | `call, why, cost, provider, reason_code` |
| `waterfall.record_step(...)` | `src/enrich.py:946` | **Yes** → `rec["waterfall"]`. Runs in **both dry and live** | `stage, provider, call, cost_unit, reason, expected_cost, actual_cost, result, next_reason, at` (`src/waterfall.py:393`) |

Plus record events: `PROVIDER_CALL_PLANNED` (`:892`, carries `estimated_cost`),
`PROVIDER_CALL_SKIPPED` (`:875`, `:888`, `:897`, `:929`), `PROVIDER_CREDIT_ESTIMATED`
(`:937`). `PROVIDER_CREDIT_SPENT` exists in the vocabulary (`src/events.py:184`) and is
**never emitted**.

**It does NOT capture — each one is a hole in the benchmark:**

- **Tokens.** No token field exists on any path through `spend()`. It is provider
  enrichment only; a model call never reaches it. (Closed for the model side by §4,
  in a separate place, deliberately — credits and currency are different units and
  `docs/AI-SPEND-LEDGER-2026-09-15.md` is right that merging them corrupts both.)
- **Wall clock.** No timer in `spend()` or in `enrich_record`. Timing exists only per
  *stage per run* (`src/run.py:414`).
- **LLM cost of any kind.**
- **Actual cost.** `actual_cost` is a declared ledger field and is always `None` from
  this path (`src/waterfall.py:407`, `src/enrich.py:946-949`). Everything reported as
  "cost" from the waterfall is *expected* cost.
- **Cache hits.** No concept at all — see §3.
- **Currency.** Only a free-text `cost_unit` (`src/waterfall.py:297`), never converted.
- **Record id on the row.** The row is nested in the record; identity is positional.
  `waterfall.audit` adds `record_id` only to its own output (`src/waterfall.py:471`).
- **Whether the call succeeded.** `spend()` returns *before* the call happens, and
  `result` is never written back.

---

## 2. Gap one — `waterfall.counters()` had no production caller

**The counters were not in the wrong place.** They read `rec["waterfall"]`, which is the
durable ledger and the single source of truth for provider routing; the module's own
comment already refuses a second counter store on the grounds that it would drift. The
defect was narrower and worse: six correct counters, derived from real rows, that
nothing ever ran. The routing policy was enforced per-step by `may_fall_back` and never
once observed in aggregate.

**Fix:** `src/run.py:471` — `report["counters"] = waterfall.counters(targets)`.

`run.run` is the right caller because it is the one place that holds the cohort just
processed, next to `report["spend"]`, `report["states"]` and `report["failures"]`. The
counters remain a *read of durable state*: nothing is accumulated in memory, so the same
numbers can be recomputed from the queue at any later time by any other tool. A run that
processes nothing reports zeros that are real zeros — the ledger was read and held no
rows.

---

## 3. Gap two — `CONTACTOUT_CACHE_HITS` had no producer, and the thing it counts does not exist

`grep -c cache src/providers/contactout.py` returns **0**. There is no ContactOut cache:
no read, no write, no store, no TTL. The parameter's own comment claimed the count was
"tracked separately at the call site in `src/providers/contactout.py`". That was never
true.

**Per instruction, no cache was built.** The metric was made honest instead.

`waterfall.counters(records, cache_hits=None)` (`src/waterfall.py:574`) now emits
`waterfall.UNKNOWN` unless a caller passes a real count (`src/waterfall.py:634`). The
reasoning, recorded in the module:

> Zero is a claim — it says a cache was consulted and never answered — and it is
> indistinguishable in a report from the truth, which is that nothing was consulted at
> all. A benchmark that read 0 here would compute a `CACHE_HIT_RATE` of 0% and believe it.

A producer that genuinely measured zero hits may still report `0`; that is a different
statement and the parameter still accepts it (tested).

### What a real `CACHE_HIT_RATE` would take

Three things, in this order, none of them done here:

1. **A cache to hit.** The template already exists and should be copied rather than
   designed: `mx.load_cache` / `save_cache` / `_fresh` (`src/mx.py:451`, `:462`, `:473`)
   — domain-keyed, TTL'd, atomically written, `store.lock`-honouring, and it already
   knows never to cache a transient failure (`src/mx.py:608` refuses to cache
   `DNS_FAILURE`; `waterfall.may_fall_back` refuses a transient as a fallback reason).
2. **The right key.** `dedupe.normalise_domain` (`src/dedupe.py:257`), not `record_id`.
   And the normalisation split must be fixed first — `src/ingest.py:48` uses its own
   `norm_domain` and calls neither canonical normaliser, so a domain-keyed cache would
   show one company as two entries.
3. **A counter at the read**, incremented only on a hit that avoided a call, passed into
   `counters(records, cache_hits=n)`. Until step 1 exists, step 3 cannot be written
   honestly, which is why it is not.

Note that `enrich.already_bought(rec, call)` (`src/enrich.py:737`) is **not** this. It
reads the waterfall ledger to avoid re-buying within one record. It is per-record reuse,
not a cross-record cache, and counting it as a cache hit would inflate the rate with
work that was never at risk of being paid for twice.

---

## 4. Tokens and model spend

### What each path records

| adapter | `complete()` appends to `self.calls` | tokens? |
|---|---|---|
| `OpenAICompatibleModel` — `src/llm.py:308` | `model, seconds, chars, prompt_tokens, completion_tokens, total_tokens`, plus `cost` where the endpoint reports one | **Yes** |
| `QwenCliModel` — `src/llm.py:458` | `model, seconds, chars` | **No — and not obtainable.** The CLI is driven with `-o text`; it returns a completion, not a usage object. This is a provider limit, not a wiring gap. |
| `ScriptedModel` — `src/llm.py:160` | nothing; it has no `calls` attribute | n/a (tests) |
| `NoModel` — `src/llm.py:149` | raises | n/a |
| `providers/glm.py` — `_usage` at `:417` | returns `prompt_tokens, completion_tokens, total_tokens, reasoning_tokens, cached_tokens` per call, and already declines to write 0 for a count the API omitted (`:420`) | **Yes — and nothing in `src/` consumes it.** `glm` is not wired into `llm.py` at all; its only non-test importer is `scripts/glm_audit_safety.py:34`. Out of scope to change (`src/providers/glm.py` is owned elsewhere), and its usage shape is already correct. |
| `providers/xai.py:275` — Grok | `prompt/completion/total/cached/reasoning` tokens + `cost_in_usd_ticks` | Captured; the provider is **unwired** — nothing calls it. |

**The defect was uniform: `self.calls` had zero readers in `src/`, and the list dies with
the process.** Every token that has ever been counted in this repository has been thrown
away.

### The fix

Three functions in `src/llm.py`, and the record as the sink:

- `usage_mark(model)` — `src/llm.py:846`. The adapter's call count *before* a call.
- `record_usage_since(rec, step, model, mark)` — `src/llm.py:867`. Appends exactly the
  rows that call produced to `rec["model_calls"]`. Returns how many it appended.
- `token_usage(records)` — `src/llm.py:896`. Aggregates by model.

Wired at:

- `llm.ask` — `src/llm.py:974-976`, around every `model.complete()`, so **every attempt is
  recorded, not only the one that validated**. A rejected answer is billed exactly like
  an accepted one, and `MAX_ATTEMPTS = 3`, so a token count that ignored retries would
  understate a step by up to 3×.
- `src/generate.py:1392, 1487, 1545, 1635` — the four direct `llm.ask` sites that were
  not passing `rec`. (`hook` `:1499` and `persona_angle` `:1509` already did.) Passing
  `rec` for `draft`, `linkedin_note` and `diagnose` changes nothing else: the
  rec-dependent checks in `ask` are gated on `step == "persona_angle"` and
  `step == "hook"`.
- `src/variantgen.py:597-599` — recorded *around* the injected `llm_ask` seam rather
  than through it. This is the largest multiplier in the inventory (up to five
  approaches per generated step), so a `TOKENS_PER_DOMAIN` that skipped it would be
  dominated by calls it could not see. Recorded around the seam because three callers
  pass a three-argument fake (`tests/test_variantgen.py:63`, `scripts/task077_detailed.py:61`),
  and widening the signature would break them for no measurement gain. A fake reports no
  `calls`, so the pair is a no-op there.

### Why the record and not a new ledger

The record is already durable state (`work/queue.jsonl`, through `store.py`), already
keyed by domain — which is precisely what `TOKENS_PER_DOMAIN` is asking for — and already
carries `rec["waterfall"]` for provider spend. A parallel file would be a second
representation of the same fact, which CLAUDE.md names as how two states drift.

`scripts/task151_ai_spend_writer.py` remains a complete, dead, unimported AI spend
ledger with a richer row (prompt version, price table version, cost source). It is still
the right destination for *priced* AI spend in currency. It was not wired here because
pricing needs a price table that does not exist, and because this task's requirement was
that tokens become answerable — which they now are, in the unit the adapters actually
report.

### Two rules the aggregator holds

1. **Absent is not zero.** A field the adapter did not report is left *off* the row.
2. **A partial measurement never masquerades as a total.** A model reports
   `total_tokens` only when *every* one of its calls reported one; otherwise it is
   `UNKNOWN`, and the part that *was* measured is reported under
   `measured_total_tokens` so nothing is discarded. `tokens_per_domain` for the whole
   run is `UNKNOWN` unless every model is complete, and `UNKNOWN` (not `0.0`) when no
   model was called at all — because `0.0` would read as "the model was free" rather
   than "nobody asked".

---

## 5. Files changed

| file | change |
|---|---|
| `src/waterfall.py` | `UNKNOWN` constant (`:571`); `counters(records, cache_hits=None)` (`:574`); `CONTACTOUT_CACHE_HITS` reports `UNKNOWN` with no producer (`:634`); the false comment about `providers/contactout.py` replaced with the measured truth |
| `src/llm.py` | `UNKNOWN` (`:30`); `USAGE_FIELDS_RECORDED`, `usage_mark` (`:846`), `record_usage_since` (`:867`), `token_usage` (`:896`); `ask` records every attempt (`:974-976`) |
| `src/run.py` | imports `waterfall`; `report["counters"]` (`:471`) — the production caller; `report["tokens"]` (`:475`) |
| `src/generate.py` | four `llm.ask` sites now pass `rec` (`:1392`, `:1487`, `:1545`, `:1635`) |
| `src/variantgen.py` | `_generate_one` records usage around the injected seam (`:597-599`) |
| `tests/test_measurement_truth.py` | new, 23 tests |

Nothing under the forbidden set was touched: `executionguard.py`, `collision.py`,
`providerwrites.py`, `bisonfactory.py`, `approve.py`, `heyreachfactory.py`,
`configdiff.py`, `senderidentity.py`, `senderinventory.py`,
`providers/{bison,heyreach,glm}.py`.

---

## 5a. One bug this found, in the instrumentation itself

`usage_mark` originally read `len(getattr(model, "calls", None) or ())`.
**`calls` is not a reserved name.** `tests/test_e2e.py`'s `E2EModel.calls`
(`tests/test_e2e.py:67`) is an **integer call counter**, so `len()` raised
`TypeError` — which is not a `SchemaError`, so it escaped `ask`'s retry loop,
failed the generate stage for every record in the batch, and turned eight
`test_e2e` assertions red (0 emails generated, every record stuck at
`verified` instead of `approved`).

Caught by running `tests/test_e2e.py` before and after a revert of only the
five files this task changed, which separated it from one failure already
present at HEAD.

`usage_mark` and `record_usage_since` now require `calls` to be a `list` and
each row to be a `dict`, and skip anything else. **Telemetry must never be able
to break the thing it measures**; an adapter whose `calls` means something else
reports nothing at all, which is the correct answer rather than a crash. Two
tests hold it (`test_an_adapter_whose_calls_is_not_a_usage_list_is_ignored`,
`test_a_non_dict_row_is_skipped_rather_than_recorded`), and the first calls
`ask` **twice** on purpose: the counter starts at 0, `0 or ()` is `()`, so a
single call slips past the bug and the test would have passed against it.

---

## 6. UNANSWERABLE today, and why

Ranked by how much the benchmark needs them.

1. **DETERMINISTIC_RESOLUTION_RATE** — *no producer.* A decision not to call a model
   leaves no trace anywhere: `generate.plan` simply does not emit an op, which is
   byte-identical to nobody having looked. Requires the `reasoning` stage in
   `waterfall.STAGES` and `record_reasoning(rec, call, resolved_by, refused)` called
   from `plan()` for ops emitted **and declined** — SCALE-HARDENING §2.4/§2.5. Not built
   here because the fix is a policy change to the generation path, not a measurement fix,
   and this task's mandate was to stop inventing metrics rather than to add one.
2. **CACHE_HIT_RATE** — *the event does not occur.* No ContactOut cache exists. Now
   reports `UNKNOWN`. §3 says what it would take.
3. **STRONG_MODEL_ESCALATION_RATE** — *the event does not exist.* There is no model tier
   and no router; one model is selected per run at `llm.from_env()` (`src/llm.py:466`).
   A rate over a single model is not a rate. `GROK_ESCALATIONS` is the nearest existing
   counter and can only fire on rows that nothing currently writes, because xAI is
   declared in `waterfall.STAGES` and has no executor.
4. **TOKENS_PER_DOMAIN on the Qwen lane** — *provider limit, not a wiring gap.* The CLI
   returns text. It would take either a Qwen endpoint that speaks
   `/chat/completions` (in which case `OpenAICompatibleModel` already handles it) or a
   local tokeniser, whose count would be an estimate and must be labelled one.
5. **Actual (as opposed to expected) COST_PER_DOMAIN, every provider** — `actual_cost`
   is never written back; `spend()` returns before the call happens. Closing it means
   calling `costs.reconcile()` (`src/costs.py:234`) in the pipeline against the
   providers' own counters, which is an out-of-band read per provider.
6. **Apify crawl cost in money** — declared UNPRICED at `src/enrich.py:48`; it bills
   compute units. Starts are countable; currency must come from Apify.
7. **Per-record SECONDS_PER_DOMAIN outside the model** — `run.py:445` averages stage
   times over the cohort and cannot separate a slow domain from a slow stage. A timer
   around `enrich_record` / `generate_record` is a two-line addition and was out of
   scope.
8. **Day-one CACHE_HIT_RATE even once a cache exists** — depends on what fraction of the
   5,000 Productive domains already appear in the 550-record estate, which cannot be
   established without reading the cohort CSV.

## 6a. Verification

```
tests.test_measurement_truth                                    23 tests  OK
+ test_contactout_fallback_semantics, test_variantgen,
  test_run, test_generate, test_invariants, test_preproduction,
  test_crash_restart_idempotency                     Ran 293 tests  OK
tests.test_e2e                              Ran 62 tests, 1 failure
    test_the_state_of_every_record - PRE-EXISTING, reproduced with all five
    changed files reverted to HEAD. Not from this work.
```

**Deliberate-break proofs.** Each break applied, module run, intended test
confirmed failing for the intended reason with no other guard firing first,
then reverted and re-run green.

| break | intended failure | exactly the intended set | first error |
|---|---|---|---|
| `counters(cache_hits=0)` — the old default restored | `test_cache_hits_are_unknown_because_there_is_no_cache`, `test_the_run_report_says_cache_hits_are_unknown` | yes | `AssertionError: 0 != 'UNKNOWN'` |
| `record_usage_since` attributes `calls[-1]`, ignoring the mark | `test_a_stale_row_is_never_attributed_to_a_call_that_reported_none` | yes | `AssertionError: 2 != 1 : a call that reported no usage must add no row` |
| `token_usage` sums a partial measurement into `total_tokens` | `test_tokens_are_unknown_for_a_model_that_reports_none`, `test_a_partial_measurement_does_not_masquerade_as_a_total` | yes | `AssertionError: 0 != 'UNKNOWN'` |
| the production caller for `waterfall.counters` removed | `test_a_dry_run_reports_the_seven_policy_counters`, `test_the_run_report_says_cache_hits_are_unknown`, `test_the_counters_agree_with_the_ledger_they_are_derived_from` | yes | `AssertionError: 'counters' not found in {...}` |
| `usage_mark` assumes `calls` is a list (the real §5a bug) | `test_an_adapter_whose_calls_is_not_a_usage_list_is_ignored` | yes | `TypeError: object of type 'int' has no len()` |

All five reverted; module green afterwards.

---

## 7. Two cautions for the benchmark harness

- **A dry run produces a full waterfall ledger and an empty spend ledger.**
  `waterfall.record_step` runs in both dry and live (`src/enrich.py:946`);
  `spendledger.record` runs only when `live` (`:920`). This is correct and will look
  like a bug if unstated.
- **Do not benchmark `src/companies.py`.** It builds a deterministic synthetic
  5,000-company universe (`:374`) at ~4.2 KB per record. Real records measure ~31.8 KB.
  It is the control, not the subject.
