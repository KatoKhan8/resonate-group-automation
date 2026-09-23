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
