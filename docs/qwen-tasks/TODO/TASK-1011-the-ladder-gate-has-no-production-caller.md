# TASK-1011 — the ladder gate has no production caller

**WRITE `REPORT.md` NOW, EMPTY, IN YOUR WORKTREE ROOT, BEFORE YOU READ
ANYTHING ELSE.** Then append as you go. A report written at the end is a
report that does not exist when the session dies.

**THIS BLOCKS GENERATION.** Operator, 2026-10-03: the ladder gate goes into a
task, and that task comes BEFORE generation. The 215 emails of phase 0b are
to be written "under the new contract AND the ladder". The contract is
enforced. The ladder is not.

## The defect, measured

Found by GLM reviewing `task-copy-exemplars`, and confirmed independently:

    grep -rn 'role_ladder' src/ --include=*.py | grep -v 'def role_ladder'
    -> 2 hits, and BOTH ARE COMMENTS
       src/copylint.py:1899      (prose)
       src/sequencegate.py:1013  (prose, beside the def)

    scripts/ callers: 0        tests/ callers: 1

Control that the search is not blind: `sequencegate.check` and
`sequencegate.check_cta` ARE called from `src/bisonfactory.py` (lines 421,
778, 823, 838). So other functions in that module have production callers
and `role_ladder` does not.

**`sequencegate.role_ladder` is the named artefact of TASK-964 and it is
inert in production.** The branch's own documentation admits it, under "What
is NOT done": *"`sequencegate.role_ladder` still has no production caller. It
was not wired."*

**The measurable cost, in GLM's words:** every sequence shaped like the
committed fixture — a bump without a thread, non-descending asks — is still
accepted by production generation today. The gate that refuses it exists
only in tests.

This is this repository's signature defect, named in CLAUDE.md: *a thing
computed correctly that nothing downstream reads.* An evaluator reported
INSUFFICIENT_DATA forever because nothing wrote the field it read, which is
indistinguishable from an evaluator waiting for volume.

## The deliverable

1. **MEASURE THE BLAST RADIUS BEFORE WIRING ANYTHING.** `role_ladder` applies
   four refusals. Run it, unwired, over every sequence the test suite builds
   and over the real cadences in `config/`, and COUNT how many it would
   refuse and WHY. Write that table into `REPORT.md` first. If wiring it
   turns forty fixtures red, that is a finding the operator needs before the
   wiring lands, not after — and it may mean the fixtures are wrong rather
   than the gate.
2. **Wire it on the real path.** The question to answer first is WHERE: the
   natural seam is beside the existing `sequencegate.check` call in
   `bisonfactory.stage`, but `generate_campaign` builds the sequence and may
   be the honest place. Read both and justify the choice by what the gate
   needs to see, not by what is easiest to reach.
3. **Prove it is consumed, by effect.** A test that drives the REAL path with
   a ladder-violating sequence and shows the refusal, plus the control from
   `TheControlPasses.test_a_sequence_built_to_the_ladder_is_not_refused`
   showing a compliant sequence is NOT refused. A gate that refuses
   everything is as useless as one that refuses nothing.
4. **Mutation**: disable the call and show the violating sequence is accepted
   again. `__pycache__` wiped on both sides; the restore verified BY EFFECT.

## Constraints

- **NO FULL SUITE** — the coordinator holds the machine-wide lock. Individual
  modules only, reported BY NAME. Two modules are already red on master
  standalone and are NOT yours:
  `test_replies.TestTheClassifier.test_every_verdict_carries_its_evidence`
  and `test_taxonomy_safety.GenuineInterestStillClassifies.test_genuine_curiosity_reaches_interested`.
  `test_generate` also carries 2F+1E on master standalone
  (`KeyError: 'rowan-blake'`, `9 != 1` twice) — measured on a neutral
  worktree detached at `2bf7b8a5`, identical error text on both sides.
- Base on the integration branch `task-integration-2026-10-03`, which carries
  the ladder work from `task-copy-exemplars`. **Do not base on master** — the
  ladder does not exist there.
- Your worktree name must contain none of `aiark`, `apify`, `blitz`, `bison`,
  `contactout`, `glm`, `heyreach`, `slack`, `xai` — that list is
  substring-matched against the ABSOLUTE PATH by `test_invariants`' send
  guard, and such a name exempts every file in the repository.
- **No `git stash`** (the stack is shared across ~40 worktrees) — WIP commit.
- `git push` is refused by the classifier. Commit locally, report branch + SHA.
- **Never widen a rule to make a sequence pass**, and never weaken a refusal
  to reduce the blast radius. If the gate is too strict, that is a finding
  and an operator decision, not an edit.

## Acceptance

    py -3 -m unittest tests.test_the_ladder_gate_is_consumed -v

Must pass wired, and the violating-sequence test inside it must FAIL with the
call disabled — the exact failure text recorded in `REPORT.md` rather than
asserted.
