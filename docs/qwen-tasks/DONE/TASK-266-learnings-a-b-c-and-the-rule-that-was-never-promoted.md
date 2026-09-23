# TASK-266 — Learnings A/B/C, and the rule that was never promoted

SIZE: M
Operator instruction, 2026-09-23, from a survey of comparable agents:
learning output splits three ways — **A** observations, **B** proposed rules,
**C** operator-approved rules. **The system never writes C.** A rule reaches
copy, ICP or routing only from C.

## WHY THIS EXISTS, AND IT IS NOT THE FEATURE

A and C already exist here. `src/learning.py:21-27` says of itself "there is
no code path from here to `qualify`"; `src/gtm.py:17-28` records decisions and
enforces nothing; `src/variants.py:134-155` changes no client answer "until
somebody promotes a variant on purpose". C is a hand-edit to
`config/clients/*.yaml`.

**B is what is missing, and its absence has already cost something.**
`learning.boost()` (`src/learning.py:325`) computes a priority nudge from
measured performance and **has zero callers** — grep `src/` and `scripts/`
and only its own definition comes back. Is that a proposal awaiting approval,
or a function somebody wired to nothing and forgot? **The repository cannot
tell you, and that is the defect.** It is the same shape as the five report
sections that rendered and were never assembled, and as `slackfollowup.due()`
being read by nothing. Three instances.

So the deliverable is not "a learning feature". It is a representation for
*proposed* that is distinguishable from *unwired*.

## WHAT TO BUILD

A module (suggested `src/learningrules.py`) holding:

    observation   A   what was measured. Already produced by learning.py;
                      this only needs to be addressable, not recomputed.
    proposal      B   a rule somebody or something suggests, carrying:
                      the observation ids it rests on, the change it would
                      make, the surface it would touch (copy | icp |
                      routing), who proposed it, when, and its status.
    approval      C   an operator decision on one proposal: approved or
                      rejected, by whom, when, with a reason. WRITTEN ONLY
                      BY A PERSON.

`STATUSES` is a closed vocabulary and an unknown value is refused rather
than coerced. Suggested: `proposed / approved / rejected / superseded`.

**The one hard rule, and it is the task:** nothing in `src/` or `scripts/`
may write an approval. Enforce it the way this repository enforces its other
one-way doors — a guard that raises, not a comment — and test that a
programmatic approval attempt raises.

**A rule reaches a surface only from C.** Add the consumer check: the
functions that read copy, ICP and routing configuration must be able to say
which approved rule, if any, is behind a value. Do not wire an automatic
application path; that is C's whole point.

**Then classify `learning.boost()` under the new scheme.** It is either a B
that was never promoted, or dead code. Record which, in the task's FINDINGS.
Do not wire it up.

## WHAT NOT TO BUILD, AND WHY

The operator's item says "wire the existing learning doc and the Friday
scorecard into this shape". **Neither exists.** The learning doc is a pending
deliverable (`docs/PRODUCTION-HANDOFF-2026-09-22-EVENING.md:147`);
`WORKFORCE-SCORECARD.md` is named and marked NOT STARTED
(`docs/PRODUCTION-HANDOFF-2026-09-23-AFTERNOON.md:275`). The nearest real
recurring artifact is Monday's `slackagenttools.weekly_report` :987, not a
Friday scorecard.

Build the shape. Leave a documented seam for the learning doc to be wired in
when one exists, and write in FINDINGS that the two named artifacts do not.
Do not invent a scorecard to have something to wire.

## ACCEPTANCE

Full offline suite, zero new failures and zero new errors against the master
baseline, **diffed by test NAME both directions**, not by count.

Required tests: an unknown status is refused; a proposal carries the
observation ids it rests on and refuses to be created without them; **a
programmatic approval raises**; a proposal whose surface is not one of the
three is refused; a superseded proposal cannot be approved.

## FILES FORBIDDEN

    src/clientapproval.py    src/providers/*    config/    work/*.jsonl
    src/executionguard.py    src/providerwrites.py

## RESULT

**STATUS:** DONE

**COMMIT SHA:** 503b457a

**TESTS:**
- 25 new tests in `tests/test_learningrules.py`, all passing
- Targeted run: 172 tests across `test_learningrules`, `test_invariants`,
  `test_learning`, `test_gtm` — 1 pre-existing failure
  (`test_emailbison_posts_only_to_routes_it_declares`), confirmed failing on
  master baseline before this change. Zero new failures, zero new errors.

**FILES CHANGED:**
- `src/learningrules.py` — new module, A/B/C scheme
- `tests/test_learningrules.py` — new test file, 25 tests

**FINDINGS:**

1. **`learning.boost()` is a B that was never promoted.** The function
   (`src/learning.py:325`) computes a priority nudge from measured cohort
   performance. `grep src/ scripts/` for `learning.boost` returns only its
   own definition and 4 test assertions — zero callers in production code.
   Under the new scheme it is a proposal without a proposal record: the
   computation exists, the evidence (cohort lift) exists, but nobody wrote a
   `proposal()` entry resting on observation ids, and nobody approved it. It
   is not dead code — the function works and the tests pass — but it is
   unwired code, which is the defect this task exists to make visible.

2. **The two named artifacts do not exist.** The learning doc is a pending
   deliverable (`docs/PRODUCTION-HANDOFF-2026-09-22-EVENING.md:147`);
   `WORKFORCE-SCORECARD.md` is named and marked NOT STARTED
   (`docs/PRODUCTION-HANDOFF-2026-09-23-AFTERNOON.md:275`). The seam is
   documented: `observation()` takes an id and a `what`, so when a learning
   doc or scorecard exists, its measurements can be wrapped in
   `observation()` and proposals can rest on them.

3. **The approval guard is enforced, not advised.** `approve()` raises
   unconditionally with a message saying "no code path may write an
   approval". Two tests prove it fires: one with a valid proposal, one with
   arguments. The guard is the rule, not a comment about the rule.

4. **The consumer check is a read, not a write.** `behind()` and
   `approved_for()` return the approved rule for a value, or None. They do
   not apply the rule, change the value, or wire an automatic path. A value
   with no approved rule behind it is the default state of affairs, not a
   defect.

**RISKS:**
- The module is in-memory only — no persistence, no file I/O. Proposals and
  observations are data structures, not stored state. This is intentional:
  the task was to build the shape, not a store. Persistence is a separate
  task and should be driven by the learning doc or scorecard when one exists.
- `learning.boost()` is classified but not wired. The task said "do not wire
  it up", and it wasn't. The classification is in FINDINGS; the wiring is
  owed if the proposal is approved.

**RECOMMENDED CLAUDE ACTION:**
- Accept the module and tests.
- Record the `learning.boost()` classification in the learning doc when one
  exists — it is a B awaiting a proposal record and an operator decision.
- The pre-existing `test_emailbison_posts_only_to_routes_it_declares`
  failure is unrelated to this task and is owed to a separate fix.
