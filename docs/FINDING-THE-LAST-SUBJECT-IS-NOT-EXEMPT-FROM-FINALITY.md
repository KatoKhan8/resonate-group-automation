# copylint refuses a correct breakup subject on the last step

**Found 2026-09-28 while rebasing `task400-rework3` onto master. Reproduced
directly, with all four controls. NOT FIXED — fixing it means changing a lint
rule, and the branch that found it may not.**

Status: **OPEN, pre-existing on master, with production consequence the moment
`TASK-400` merges.**

## THE DEFECT

`src/copylint.py` builds the surface the finality rule reads as:

    non_final = "\n".join([str(b) for b in bodies[:-1]] + [subjects, extra])

`bodies[:-1]` correctly exempts the LAST email body — a sentence claiming
finality is *true* there, because it IS the last step. But `subjects` is the
concatenation of **all five** subjects and goes in whole, so the last step's
SUBJECT never receives the same exemption. A finality phrase in em5's subject is
therefore reported as `finality_before_last_step` — "a step claims to be the
last one while a later step still sends" — when no later step sends.

`FINALITY_RE` matches, among others, `closing the loop`, `last email|note|
message`, `final email|note`, `i will stop here`, `leave you alone`,
`won't email|write|follow up`.

## MEASURED, WITH CONTROLS

Five-step lead, one pack fact, everything else clean. Only the named surface
varied:

    all five subjects neutral              ->  not refused      CONTROL
    finality in the LAST subject           ->  REFUSED          FALSE POSITIVE
    finality in the LAST body              ->  not refused      exempt, correct
    finality in an EARLY subject           ->  REFUSED          true positive

The rule itself is right, and it is not unconditional: the control passes and
the early-subject case correctly fires. Only the exemption is incomplete.

## WHY IT HAS BEEN INVISIBLE

`copylint.check_batch`'s verdict on generated copy was **computed and read by
nothing** on the campaign path — this repository's signature defect, and the one
`TASK-400` exists to close. `TASK-400` makes the verdict act: a refused draft is
regenerated, and after `MAX_WRITER_ATTEMPTS` the copy is refused and the
sequences emptied. So the false positive only becomes observable once the gate
is load-bearing.

This is the same shape as the two items in handoff section 9 — a pre-existing
problem that became visible the moment a gate could run. It is not a regression
and **it must not be fixed by relaxing anything.**

## WHY IT WILL REFUSE REAL LEADS

`src/copyprompts.py` instructs the model, for the canonical five-email cadence:

    em5  day 21  NEW THREAD, breakup, subject C - short, its own
    subject_breakup C - short, three or four words, no hook, no question

A short breakup subject is precisely what `FINALITY_RE` is built to match. So
after `TASK-400` merges, a lead whose em5 subject is a natural breakup line is
regenerated three times and then **HELD** — correct copy, refused. That is a
candidate blocker for `TASK-425`'s one-account dry run, alongside the three
already recorded.

It was found through a test fixture, but the fixture is not the problem: the
fixture was modelling what production is instructed to produce.

## HOW IT SHOWED UP

`tests/test_changing_an_approved_fact_changes_the_output.py`'s Checkpoint A
control asserted `'' == ''` — both sides empty, so the comparison proved nothing
in either direction. The contact came back `hold_kind=copy_refused`,
`gate_attempts=3`, `sequences={}`, with the same rejection three times. A
vacuous assertion is worth naming on its own: it would have passed as
"unchanged" under an `assertEqual`, and it failed only because this test asserts
`assertNotEqual`.

That fixture now uses a breakup subject asserting no finality — which also
matches `copyprompts`' own instruction — and its falsifiability was re-proved by
mutation afterwards. That is a workaround in a test, not a fix to the defect.

## WHAT A FIX HAS TO DO, AND WHAT IT MUST NOT

Give the last step's subject the same exemption its body already has, so the
rule reads per-step rather than over a pooled string. Concretely: the finality
check needs the subjects paired with their step index, exempting only the final
one, exactly as `bodies[:-1]` already does.

**It must not:** widen or delete `FINALITY_RE`, drop `subjects` from
`non_final`, or exempt LinkedIn/P.S. text. A finality claim in an early subject,
in a P.S. line, or in a non-final LinkedIn message is a real defect the rule
correctly catches today — TASK-378 pointed it at the full rendered surface for
that reason, and that part is right. Only the last step's own subject is
wrongly included.

Needs a test in both directions: the last subject may say it, an earlier one may
not.

## OWNERSHIP

`src/copylint.py` is on the stricter-copy-rules path (`TASK-330` / `TASK-378`).
This finding is filed rather than fixed because the rebase branch's remit is
`src/generate.py`, `src/generate_campaign.py`, `src/approve.py`, `src/run.py`
and its own tests — and because a branch that widens a lint rule to make its own
fixture pass is the exact failure mode `CLAUDE.md` names.
