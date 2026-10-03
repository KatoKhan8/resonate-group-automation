# TASK-980: The five-step lead classification has no implementation

**Opened by** the phase-2 120-day simulation, 2026-10-03, on branch `task-phase2-simclock`.
**Status** TODO. **For** the operator.

## What was measured

CLAUDE.md rule 2 is a PERMANENT operator rule describing five ordered, mutually exclusive lead classes. No module computes it. `BLOCKED_FOREVER`, `ON_HOLD`, `COLD_LEAD` and `STARI` return ZERO grep hits across `src/`.

What exists instead is four partial authorities that nothing composes:

- `hygiene.check` - 12 verdicts from LOCAL history
- `collision.account_policy` - 3 verdicts from PROVIDER truth
- `eligibility.must_not_contact` - 6 person-level blocks
- `reengagement.classify` - 5 lanes under different names, with NO production caller

Rule 2's load-bearing split - *did RESONATE OS contact them, judged by provider truth about sends in campaigns positively recorded as ours* - is implemented nowhere.

## Scenarios that surfaced it

`S01`, `S02`, `S03`, `S04`, `S05`, `S06`, `S07`, `S08`, `S10`, `S14`, `S18`, `S19`, `S21`, `S22`, `S23`, `S25`

## Proposal

Add `src/leadclass.py` with one function, `classify(rec, contact, provider_truth, config)`, returning exactly one of `BLOCKED_FOREVER` / `ON_HOLD` / `STARI_LEAD` / `COLD_LEAD` / `UNKNOWN` plus the reason and the authority that decided it. It COMPOSES the four existing authorities in rule 2's order and implements none of their logic itself, so there is no second representation of suppression or of provider truth. It must fail CLOSED: an unreadable provider walk returns `UNKNOWN`, and UNKNOWN is treated as blocked - never cold, never revival. The eight scenarios S04, S05, S06, S07, S08, S22, S23 and S25 become its acceptance tests and are already written.

## What this task is NOT

It is not a licence to weaken a gate, a lint rule or an assertion to make a scenario pass. If the only way through is to loosen something, that is a finding with both sides, not a fix.

## Provenance

Measured on the merged base containing master `7e8eee41`. No provider call, no provider write, no Slack post, and production `work/` md5-unchanged across the run.
