PRIORITY: P1
DEPENDS:

# TASK-151 - the question nobody can currently answer

## THE QUESTION

    "What did Productive cost us in AI today, and which stages spent it?"

Right now the answer is "App: Unknown" on an OpenRouter dashboard. That is the
entire visibility, and it is not enough to optimise against - every routing
decision in the parallel cost track is otherwise a guess with a story
attached.

## WHAT EXISTS ALREADY, AND FIND IT BEFORE BUILDING ANYTHING

This repository already has a spend ledger for PROVIDER credits.
`enrich.spend()` writes the waterfall ledger and `CLAUDE.md` makes it a rule:
*"Every paid call goes through enrich's `spend()`... A provider call that
skips it is invisible to the spend audit, and an audit that reports clean
because it watched nothing is worse than none."*

**The same sentence is true of model calls and there is no equivalent.**

So the first job is to read `src/spendledger.py` (and `enrich.spend`) and say
whether the model lane belongs in that ledger or beside it. Prefer the
existing one if it fits - a second spend ledger is a second answer to one
question, and this repository has been bitten by exactly that three times
today.

## THE DESIGN

Per call, recorded durably:

    workspace/client        stage            task
    record/company/contact identifier (HASHED - see below)
    model                   provider         prompt_version
    input_tokens            output_tokens    cached_tokens if available
    latency                 retry_count      estimated_cost
    success/failure         cache_hit where known

`src/llm.py` is the chokepoint. If every model call already goes through one
function there, this is one wrapper and a writer. **Verify that** - run
`grep -rn "llm\." src/` and check whether anything bypasses it. A ledger that
watches one of two paths is the "audit that reports clean because it watched
nothing" the rule warns about, and finding a bypass is a result.

Cost needs a price table. OpenRouter publishes per-model pricing; put it in
config, version it, and record which version priced a row - a cost computed
from a price that later changed is a number nobody can reproduce.

## WHAT MUST NOT GO IN IT

- **No prompt contents.** Not truncated, not "just the first line". Prompts
  carry prospect names, domains and reply text.
- **No raw identifiers.** Hash the record/contact id. The ledger must answer
  "which stage spent this" without becoming a second copy of the estate.
- Where the ledger lives matters: `work/` is gitignored and is where
  production state belongs. It is not committed.

## ALSO: OPENROUTER ATTRIBUTION

OpenRouter supports request metadata. Establish from its documentation what
fields are available and whether they would let the dashboard answer
per-client and per-stage questions directly. Say what to set and what it
would buy. If the answer is "our own ledger is better", say that.

## DELIVERABLE, AND KEEP IT SMALL

This is the instrument, not the optimisation. A working ledger that answers
the headline question for one day of real running is worth more than a
complete design that is not wired.

    docs/AI-SPEND-LEDGER-2026-09-15.md   design + what exists + the bypass
                                          check result
    src/                                  ONLY if the design lands on a
                                          wrapper small enough to be obviously
                                          correct - propose it in the doc
                                          first and let Claude take it

## WHAT YOU MAY NOT DO

- Do not wire a ledger into the production generation path yourself. Propose
  it; Claude integrates. A half-wired ledger on the live path is worse than
  none.
- Do not call the model to test it - unit-test the writer.
- No provider writes. Do not write to `work/` outside a temp directory.

## FILES ALLOWED

    docs/AI-SPEND-LEDGER-2026-09-15.md   (new)
    scripts/task151_*.py
    tests/test_ai_spend_ledger.py        (if you build the writer)
    the task file itself

## FILES FORBIDDEN

    src/generate.py   src/llm.py   src/variantgen.py   work/   config/

## DELIVERABLE

Whether the existing spend ledger fits, the bypass-check grep result, the
record shape with hashing, the price-table versioning, the OpenRouter
attribution verdict, and a tested writer if it is small enough to be
obviously correct.

## RESULT

**STATUS:** DONE

**COMMIT:** 73cf3e8

**TESTS:** 35 tests in `tests/test_ai_spend_ledger.py`, all passing.
No model calls. Pure writer verification with temp directories.

**FILES CHANGED:**
- `docs/AI-SPEND-LEDGER-2026-09-15.md` — design document
- `scripts/task151_ai_spend_writer.py` — tested writer module
- `tests/test_ai_spend_ledger.py` — 35 tests

**FINDINGS:**

1. **The existing spend ledger does NOT fit.** It tracks provider credits
   (ContactOut, Reoon) as integer expected costs. Model calls need currency
   (float USD), token counts, latency, model name, and price versioning.
   Different shapes, different questions. Verdict: beside it, not in it.

2. **Bypass check: no bypasses exist.**
   `grep -rn "\.complete(" src/` returns ONE hit: `src/llm.py:827`, inside
   `ask()`. The three modules that import `llm` (generate.py, run.py,
   variantgen.py) all go through `llm.ask`. The chokepoint is real.

3. **OpenRouter already returns cost** in `usage.cost`, captured in
   `self.calls` by `OpenAICompatibleModel.complete()` but never persisted.
   The ledger's job is to persist what already exists in memory.

4. **OpenRouter attribution is app-level only.** HTTP-Referer + X-Title
   identify the app, not the stage or client. Per-request `metadata`
   supports trace_id for observability. Our own ledger answers the
   question OpenRouter cannot: "which stage spent what on which client."

5. **The writer is ~30 lines of real logic.** Small enough to be obviously
   correct. Not wired into production — Claude integrates.

**RISKS:**
- The writer is not wired into `llm.ask`. Until Claude integrates it, no
  rows are recorded. The instrument exists; the measurement does not start
  until the wiring lands.
- No price table file was created (config/ is forbidden). The writer works
  without one, using OpenRouter's reported cost. A price table is needed
  for non-OpenRouter endpoints and for pre-call estimation.

**RECOMMENDED CLAUDE ACTION:**
Wire `record_call()` into `llm.ask()` after the `model.complete()` call.
The wrapper extracts usage from `model.calls[-1]`, hashes `rec["id"]` if
a rec is available, and appends one row. Approximately 15 lines of wiring.
