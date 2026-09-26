PRIORITY: P1
SIZE: S
DEPENDS:

# TASK-300 — the variant experiment runs on the send path and nothing acts on what it learns

## The question this answers

**`variants.shifted_allocation()` computes a shift of traffic toward the
winning copy variant. Does anything in production ever write that shift — and
if not, is that a deliberate gate or a wire nobody connected?**

Answer it, then either prove the wiring exists or write down that the gate is
deliberate and why. **Both are acceptable outcomes. "It looks wired" is not.**

## What is already established — do not re-derive it

Measured on master, 2026-09-25:

    src/variants.py:526          def shifted_allocation(node, verdict, config=None)
    src/web/demovariants.py:218  shifted = V.shifted_allocation(...)   <- the ONLY
                                 non-test caller in the repository
    tests/test_variants.py       5 further calls, all tests

`src/web/demovariants.py` describes itself in its own first line as *"Demo
copy experiments: five styles per message step, and five outcomes. Fictional,
and labelled so."*

**And the send path DOES reach `variants`** — this is the part that makes the
finding interesting rather than dead code:

    src/bisonfactory.py:793      from . import variants
    src/bisonfactory.py:803      variants.apply_to_step(...)
    src/cadence.py:222           from . import variants

So variants are **allocated and applied to real sends**. `bisonfactory`'s own
comment at line 663 says *"VARIANTS ARE RESOLVED HERE, not downstream. A step
carrying five variants assigns one per contact deterministically."* The
experiment therefore runs against real prospects. What is missing is the other
half: the result feeding back into the allocation.

## The acceptance bar

1. **Name every production writer of a variant allocation, or state that there
   is none.** A writer means something that changes what future contacts are
   assigned — a store write, a config write, a campaign row update. Walking
   the call graph is the evidence; a grep for the function name is not enough,
   because a caller may pass the result somewhere else.
2. **Decide and record which of these is true**, with the evidence:
   - the shift is computed and written, and you can name the write; or
   - the shift is computed and discarded, in which case say where the result
     dies; or
   - the shift is deliberately gated pending an operator decision, in which
     case find the gate and quote it.
3. If there is no writer, **do not build one.** Changing how traffic is
   allocated across copy variants is a prospect-facing decision and is the
   operator's. Write the finding and stop.
4. Record whether the experiment can even reach a verdict: `shifted_allocation`
   takes a `verdict`, so say who produces one in production and whether any
   real campaign has ever had enough data to leave `exploring` /
   `insufficient_data`.

## What would make this a FALSE PASS

- **Concluding "it is wired" because the send path imports `variants`.** It
  does, for `apply_to_step`. That is allocation, not learning. The two are
  different functions and only one of them is on the send path.
- **Concluding "it is dead code" because the only caller is a demo.** The
  allocation it would shift is live; a demo caller means the *learning* is
  unwired, not that the feature is unused.
- **Reading `src/web/demovariants.py`'s fixtures as evidence about production.**
  They are fictional and the file says so. A verdict in a fixture is not a
  verdict any campaign produced.
- **Answering from the test suite.** Five of the six callers are tests, and a
  test calling a function proves the function runs, not that production calls
  it — this is exactly the defect TASK-277 shipped, where a lint was proved by
  eight tests that called it directly and zero that called the send path.
- Any answer that does not distinguish "no writer exists" from "a writer
  exists and is gated".

## Why it is sized S

It is a read and a write-up. No implementation is authorised by this task.

## Provenance

Operator, 2026-09-25, correcting their own earlier label: the finding was
first filed against TASK-279, which is actually "the 19,612 packs arrive in
chunks". TASK-279 stays as it is. This is the real finding from the OSS
survey, which stays open until the operator has read it.

---

## RESULT

### STATUS
DONE

### COMMIT SHA
8be37c4b

### TESTS
Read-only investigation. No code changed. No tests run.

### FILES CHANGED
None. This task authorised no implementation.

### FINDINGS

**1. Every production writer of a variant allocation: there is none.**

The only code in `src/` that calls `shifted_allocation()` AND writes its
result is `src/web/demovariants.py:218-222`. That module is the demo. It
builds a fresh in-memory graph from planted fixtures, shifts the winner's
allocation, and returns the graph to the API endpoint for display. The
graph is never persisted. It is rebuilt from scratch on every request.

Full evidence — every occurrence of `shifted_allocation` in the codebase:

    src/variants.py:140          comment only, mentions the function by name
    src/variants.py:526          definition
    src/web/demovariants.py:218  the ONLY non-test caller
    tests/test_variants.py       5 calls, all unit tests

No other production module calls it. No scheduled job, no API route, no
store write, no campaign update.

**2. The shift is computed and discarded. Here is where the result dies.**

The learning loop has two halves. The first half — allocation and
attribution — IS connected to production:

    src/bisonfactory.py:967   variants.apply_to_step(...)   <- assigns copy
    src/cadence.py:229        variants.resolve(...)          <- sticky assignment
    src/cadence.py:967        variants.apply_to_step(...)    <- same, other path

Touch events carry `variant_id` (COPY-EXPERIMENTS.md §10, confirmed in
`tests/test_variant_attribution.py`), so `variants.results_from()` CAN
count exposures and outcomes per variant.

The second half — evaluation and feedback — is where the wire is
disconnected:

- `variants.evaluate()` IS called in three production sites:
  - `src/web/api.py:6551` — experiment dashboard, serves JSON
  - `src/cadencereport.py:116` — arm comparison report
  - `src/outcomes.py:715` — instrumentation dashboard

  All three compute a verdict (which may be WINNER). None of them call
  `shifted_allocation()` with that verdict.

- The experiment dashboard (`api.py:6555-6583`) reads the EXISTING
  allocation via `allocation_of()`, serves it alongside the verdict, and
  includes a `shifted` boolean that merely checks whether the current
  allocation is already uneven. It never computes a new allocation.

- `cadencereport.py:130-165` determines `actionable` and `leader`,
  applies three refusal gates (IMMATURE, NO_WINNER, SAFETY_DISAGREES),
  and reports the result. Even when `actionable=True` and a leader
  exists, nothing calls `shifted_allocation()` or writes a new
  allocation.

- `outcomes.py:715-720` reports the verdict state, leader, and cells.
  No shift, no write.

**The result dies at the dashboard response.** The verdict is computed,
serialised to JSON, sent to the browser, and forgotten.

**3. This is NOT a deliberate gate. It is an unconnected wire.**

There is no code that says "wait for operator approval before shifting
traffic." The refusal logic in `cadencereport.py` gates whether a
verdict is *actionable*, but even an actionable verdict with a confirmed
leader triggers no allocation write. The `client_status` field on
variants can be set to "winner" by a human through `clientreview.py`'s
CSV editing, but this is a display/status field — it does not trigger
`shifted_allocation()` or change any allocation.

The distinction the task asks for: this is "no writer exists", not "a
writer exists and is gated". A gate would be code that computes the
shift and then refuses to apply it pending approval. What exists instead
is code that computes the verdict and never computes the shift at all.

**4. Can the experiment reach a verdict in production?**

Yes. The evaluator (`variants.evaluate`) is reachable from production
paths, the attribution wiring is connected (touch events carry
`variant_id`), and `results_from()` can count real outcomes. The
thresholds (10% checkpoint, 30 exposures per variant, 8 total outcomes,
Wilson lower bound clearing all others, ≥30% lift) are achievable with
real sends but require volume. Whether any real campaign has actually
reached WINNER is a live-state question I cannot answer from this
worktree (per QWEN.md rules on `work/queue.jsonl`).

The demo module's planted verdicts (WINNER on one step, LEADING on
another, etc.) are fictional — `demovariants.py` says so in its first
line. They are not evidence that any campaign has reached any state.

### RISKS

- **The experiment is open-loop.** Traffic is allocated, variants are
  served, outcomes are counted, verdicts are computed — and the
  computed verdict never changes future allocation. The only way
  allocation changes is if a human manually edits the `allocation`
  field on a variant entry, or edits `client_status` to "winner"
  (which itself has no allocation effect).
- **This is invisible to the operator.** The dashboard shows verdicts
  and shows allocations side by side. An operator could be forgiven for
  assuming the shift happened automatically. The `shifted` boolean on
  the dashboard response is true only if the allocation is ALREADY
  uneven — it does not say "the system shifted this" vs "a human set
  this".
- **No data is lost.** The attribution is connected, the counts are
  real, and the evaluator is correct. When a writer is eventually
  added, the data it needs to read exists.

### RECOMMENDED CLAUDE ACTION

This is an operator decision, not an engineering one. The task
explicitly says "do not build a writer." The question for the operator:

1. Should the system automatically shift traffic toward a winner when
   `cadencereport.py` reports `actionable=True` and a leader? If so,
   the wire to connect is: `evaluate()` → `shifted_allocation()` →
   write new `allocation` values back to the campaign's step spec,
   bumping `allocation_version` so future assignments use the new
   shares.
2. Or should the shift remain manual, with the dashboard showing the
   verdict and a human deciding? If so, the dashboard should say so
   explicitly — "allocation unchanged; shift manually" — rather than
   showing a `shifted` boolean that could be read as "the system did
   this."

Either answer is acceptable. The finding that must not stand is the
current one, where the two halves of the loop are built and connected
to nothing.
