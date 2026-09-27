# Verification — `42114d2f`, sequencegate enforces the messaging rules

**Verifier:** Claude (orchestrator), 2026-09-27 evening.
**Branch:** `worktree-agent-a61927afe01ec9ccf`
**Branch head SHA reviewed:** `42114d2f2ed9a498c132fe60e902494214507c32`
**Master at verification time:** `8f17d103`
**Verdict:** **PASS, MERGE-READY — HELD, not merged, for a stated reason.**

A verdict that does not name the branch head SHA it reviewed is void in this
project; three of five GLM verdicts were void on exactly that. This one names it.

## Why this branch matters now

It is what turns `messaging_rules` from data into a gate. The offers library
carries `enforcement_status: DATA_ONLY_NOT_YET_ENFORCED` precisely because
`sequencegate` on master does not read `step_objectives` — a config block is not
enforcement, and this is the instance of that invariant the one-account dry run
trips over. **TASK-425 acceptance criterion 3 requires offer sequencing enforced
by `sequencegate` with a negative test, so this branch is on the critical path
for that milestone rather than beside it.**

It also fixes a real claim-licensing defect, and that defect is the same class as
launch blocker 5. "AI Time Tracking removes the need to think about admin ever
again" came back LICENSED because the feature's own name shares the word "time"
with its own page text. Grounding is supposed to bind a claim to evidence
MEANING, not a token to the same token somewhere in the source.

## What was verified, and how

1. **Scope is clean.** `git diff master...42114d2f --stat` touches exactly two
   files: `src/sequencegate.py` (+264) and a new
   `tests/test_sequencegate_enforces_messaging_rules.py` (+271). No junk, no
   scope drift, nothing to cherry-pick around. This matters because merging
   pollution to save time is forbidden here, and one such branch would have
   silently reverted the provenance fix.
2. **Its own tests pass on its own head.** 19/19 in a scratch worktree checked
   out at `42114d2f` — not on master, and not on a rebase that would have
   changed what was measured.
3. **It composes with current master.** Master `8f17d103` merged into
   `42114d2f` with NO conflicts, and the combined tree runs 52/52 green across
   the enforcement tests, the killswitch module, and the new
   `sending.live` scope proof.
4. **Signature compatibility with TASK-426 was checked deliberately**, because
   both touch the same seam from opposite sides. `sequencegate.check`'s signature
   is UNCHANGED on this branch — every addition is inside the function body. So
   TASK-426, which fixes the CALL SITE in `bisonfactory` to pass all five
   inputs, does not collide with it.
5. The author's own record claims 19 tests and five mutations each caught by the
   intended test. The 19 tests are confirmed. **The five mutations were NOT
   independently reproduced by this verification** and are carried as the
   author's claim, not as verified fact. Stated rather than absorbed.

## Why it is HELD rather than merged

TASK-426 is being implemented right now, and its acceptance check is that
`tests/test_lead_writes_respect_the_killswitch` goes 5/5 — which requires
`bisonfactory.stage()` to SUCCEED. This branch adds `fail("step_objectives", …)`
outcomes to the gate that `stage()` calls. Absence of `step_objectives` only
`warn`s, so the likely interaction is benign, but "likely benign" is not a
verification.

So the merge order is: **TASK-426 lands first, then this branch, then the
three-way combination is verified before either reaches master.** Merging this
first would risk moving the target of the highest-value fix in the repo while a
subagent is aiming at it.

## Remaining risk

- The five mutations are unreproduced (above).
- `enforcement_status: DATA_ONLY_NOT_YET_ENFORCED` in
  `config/clients/productive-offers.yaml` becomes FALSE the moment this merges.
  That line must be updated in the same merge, or the library will claim nothing
  enforces a rule that now does — the same stale-prose failure just corrected on
  the `sending.live` settings entry.
