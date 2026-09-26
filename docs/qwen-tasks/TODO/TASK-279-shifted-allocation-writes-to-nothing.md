# TASK-279 — `shifted_allocation` computes a real number and nothing writes it anywhere

SIZE: S

OSS survey, 2026-09-25 (`docs/OSS-SURVEY-2026-09-25.md`): a candidate
(PyBandits, Thompson-sampling bandits) looked like it would improve how
copy-variant traffic shifts toward a winner. Checking the premise found a
smaller, prior bug instead — the algorithm already in this codebase for
that job has no production caller at all.

## THE FINDING

`src/variants.shifted_allocation()` (`src/variants.py:526-545`) takes a
`WINNER` verdict from `variants.evaluate()` and returns new traffic
shares — the winning variant gets `winner_share` (default 0.75), the rest
split the remainder, deliberately never to zero unless
`node.get("winner_takes_all")` is set. Its own docstring states why: *"a
variant that stops being served stops being measured, and an experiment
that stops measuring cannot notice that its winner has stopped working."*

That's the right design. But:

    grep -rn "shifted_allocation" src/ scripts/

returns exactly **one** call site: `src/web/demovariants.py:218`. That
module is a demo web surface. Nothing that persists a real campaign's
experiment state — nothing that could write back into
`node["variants"][i]["allocation"]`, the field `variants.allocation_of()`
(`src/variants.py:308-323`) actually reads when deciding future
assignments via `assign()`/`resolve()` — calls `shifted_allocation` at
all.

So today: an experiment can reach `WINNER` state
(`variants.evaluate`, called from `src/outcomes.py:715` and
`src/cadencereport.py:116`, both read-only reporting paths), and **the
traffic split future contacts get assigned to stays exactly what it was
before the winner was found.** The winner is reported. Nothing acts on
it. This is the same shape CLAUDE.md already names three times:
`learning.boost()` (still zero non-test callers — reconfirmed this run),
`slackfollowup.due()`, and the unassembled report sections. A verdict
computed correctly and read by nothing is indistinguishable from a
verdict nobody trusts.

## WHAT THIS TASK IS NOT

Not "implement Thompson sampling." Not "make `shifted_allocation`
smarter." The simpler function that already exists has never been
exercised in production, so upgrading its statistics now would be adding
more unread code on top of unread code. If this task's own tracing work
turns up a real reason no writer exists (e.g. an explicit, intentional
`GTM`/`clientreview` decision-log requirement that a human approve every
reallocation — check `src/gtm.py` and `src/clientreview.py` for this
before assuming it's simply missing), **write that down in FINDINGS and
stop there.** Do not build a writer to satisfy the acceptance criteria if
tracing shows the absence is a deliberate approval gate rather than an
oversight.

## WHAT TO TRACE FIRST

1. Where does a real campaign's experiment node
   (`variants.experiment_of(node)`) actually live and get read from in a
   live send path — not the demo — and where would a shifted allocation
   need to be written for `assign()` to see it on the next call? Follow
   `src/cadencearms.py` and `src/nextaction.py:660`
   (`Deterministic on (experiment_id, unit_key, allocation_version)`) —
   both reference `allocation_version` and look like the closest thing to
   a real consumer; confirm whether either one reads a *shifted* share or
   only ever reads the stored/even one.
2. Is there an existing writer for `node["variants"][i]["allocation"]`
   anywhere in `src/` outside of test fixtures and `demovariants.py`? If
   yes, why doesn't it call `shifted_allocation`? If no, that confirms the
   gap.
3. Check `src/gtm.py`'s decision log and `src/clientreview.py` for
   whether a reallocation is supposed to require an explicit recorded
   decision (per the A/B/C shape TASK-266 already built) before it's
   allowed to change what ships. If so, the missing piece may be "wire
   `shifted_allocation`'s output into a `gtm.decision()`-gated write," not
   a bare automatic writer.

## THE MINIMUM CHANGE, IF THE GAP IS CONFIRMED AS AN OVERSIGHT

Wire one real consumer: when `variants.evaluate()` returns `WINNER` for a
live experiment node, the shares `shifted_allocation()` computes must
reach the same node `assign()` reads on the next call for a new contact —
through whatever the tracing in step 1 finds is the actual persisted
node, and gated the way step 3 finds the rest of this codebase requires
(explicit decision record, not silent auto-apply, if that's the house
pattern — see TASK-266's A/B/C boundary before assuming otherwise).

Do not invent a new persistence format. `allocation_of()` already reads
`v["allocation"]` off stored variant entries — the fix is making a real
write reach that field, not a new field or file.

## ACCEPTANCE

Full offline test suite, zero new failures and zero new errors against
the master baseline, diffed by test NAME both directions.

Required tests:
- A node with a `WINNER` verdict, run through the real (non-demo)
  write path this task adds or confirms, produces an `allocation_of()`
  read that differs from even split — proving the shift is actually
  consumed by `assign()`, not merely computed.
- A contact assigned before the shift and a contact assigned after it
  can land in different cells for the same `_bucket()` point, and the
  **before** assignment (the `recorded` one) is unchanged on re-read —
  `resolve()`'s existing "recorded wins" rule must still hold.
- If tracing shows the missing writer is a deliberate approval gate
  rather than an oversight: a test is not required, but FINDINGS must
  name the gate (file:line) and RECOMMENDED CLAUDE ACTION must say
  plainly that no writer was built and why.
- `demovariants.py`'s existing behaviour is unchanged.

## FILES FORBIDDEN

    src/clientapproval.py    src/providers/*    config/    work/*.jsonl
