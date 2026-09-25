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
