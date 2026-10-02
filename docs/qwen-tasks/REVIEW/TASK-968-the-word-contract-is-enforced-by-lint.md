# TASK-968 — the writer contract becomes the thing that refuses

Written 2026-10-03 for work already finished on `task-word-contract-enforced`,
because the branch carried no task file and `glm_verify_branch.py` extracts its
acceptance from one: no file, no GLM verdict, and UNKNOWN does not pass.

**This file was written AFTER the code and says so.** Every command below was
executed before being written down, and the output is recorded under it.

## THE NUMBER 943 NAMES TWO DIFFERENT TASKS, AND THAT IS A FINDING

The operator's queue calls this branch "the lint contract (with 943)", and
`CLAUDE.md` records *"THE WRITER CONTRACT IS THE ONLY AUTHORITY FOR A BODY'S
WORD COUNT — operator, 2026-10-02, TASK-943"*.

But a file called `docs/qwen-tasks/TODO/TASK-943-name-the-authority-for-sent.md`
exists in history (commit `ae030997`, the ramp lane) and it is a **different
task**: *"the readback must declare which provider field decided SENT, and
refuse without it"*, P0, with four competing candidate fields for email alone.

One id, two tasks. This file takes a free number rather than adding a third
meaning to 943, and the collision is recorded here so the next reader does not
have to rediscover it.

## What the branch does

`src/skills/cold_email_writing.py` carries the contract AS DATA — "a contract
nothing can read is not a contract" — and `src/lint.py` now refuses against it.
Measured through the code:

    WORD_CONTRACT = {"em1": (60, 75, 90), "em2": (45, 60, 90),
                     "em3": (60, 75, 90), "em4": (45, 60, 90),
                     "em5": (45, 65, 90)}      # (floor, target, ceiling)

It also carries its own guard against the defect that produced it: **every step
must have at least thirty allowed lengths**, because the abolished 15-to-60
thread-reply range and a 60-to-90 em2 once intersected to the single value 60 —
an equality presented as a threshold.

## ⚠ THE OPERATOR'S NEW CONTRACT COLLIDES WITH THIS ONE AT em1

The operator set a new contract the same night: **em1 90–140, target 120**;
em2–em5 45–90; em4 target 50.

**This branch's em1 CEILING is 90.** So on the merged master, an em1 of 120
words — the operator's own target — would be REFUSED. The two contracts
intersect at exactly ONE value, 90, which is the same shape this branch exists
to prevent.

Nothing generates a 120-word em1 today, because the new contract is not
implemented anywhere (TASK-964 is TODO), so merging this enforcement is safe
NOW and strictly better than a contract nothing reads. **But `WORD_CONTRACT`
must become `em1: (90, 120, 140)` as part of TASK-964, in the same commit that
teaches the writer the new ladder** — and em4's target becomes 50 there too.
Merging this branch without recording that would leave the operator's own
instruction impossible to satisfy and the reason invisible.

## Acceptance

```
python -c "import sys; sys.path.insert(0,'.'); from src.skills import cold_email_writing as w; c=w.WORD_CONTRACT; assert set(c)=={'em1','em2','em3','em4','em5'}, c; assert all(len(v)==3 and v[0]<=v[1]<=v[2] for v in c.values()), c; assert c['em1'][0]==60 and c['em3'][0]==60 and c['em2'][0]==45, c; print('OK the contract is data and ordered:', c)"
```

```
python -c "import sys; sys.path.insert(0,'.'); from src import lint; KEY='k'; rec=lambda sk,n: {'id':'r','domain':'example.test','contacts':[{'key':KEY,'email':'a@example.test','cadence':{sk:{'channel':'email','generated':True,'subject':'a subject that is fine','body':' '.join(['word']*n)}}}]}; r=rec('em2',41); step=r['contacts'][0]['cadence']['em2']; bad=lint.check_step(r, KEY, step, step_key='em2'); good=lint.check_step(rec('em2',61), KEY, rec('em2',61)['contacts'][0]['cadence']['em2'], step_key='em2'); words_bad=[f for f in (bad or []) if 'word' in str(f).lower()]; assert words_bad, 'an em2 of 41 words was not refused on word count: '+str(bad); words_good=[f for f in (good or []) if 'word' in str(f).lower()]; assert not words_good, 'a 61-word em2 was refused for its length, so the rule refuses everything: '+str(words_good); print('OK 41 refused on words, 61 not:', [str(f)[:60] for f in words_bad][:1])"
```

```
python -c "import sys; sys.path.insert(0,'.'); from src.skills import cold_email_writing as w; room={k:(v[2]-v[0]+1) for k,v in w.WORD_CONTRACT.items()}; assert min(room.values())>=30, room; print('OK every step has at least thirty allowed lengths:', room)"
```

### NEGATIVE CONTROL

Command 1 fails if the contract stops being an ordered triple per step — which
is what a half-applied edit to those numbers looks like.

Command 2 is the operator's own case: an em2 of 41 words, the length the
approved canary copy actually shipped, must be REFUSED. It fails on master,
where `lint`'s floor is 40 and no 60 or 90 exists as a word bound at all. Its
second half is the control: a 61-word em2 must not be refused for length, or the
rule refuses everything and proves nothing.

Command 3 is the branch's own anti-equality guard: thirty allowed lengths per
step, so no future edit can reduce a range to a single legal value.

**THERE WAS A FOURTH COMMAND AND IT IS DELETED.** It read
`assert w.WORD_CONTRACT['em1'][2] >= 140 or True` and I labelled it "a record,
not a check". GLM's review called it exactly what it was — *"a print statement
wearing an assert"* — and made the sharper point: the em1 bound was then
"accepted by a check that is unfalsifiable by construction". A disclosed
vacuous assertion is still a vacuous assertion sitting in an acceptance list,
and this repository has been burned by those. The em1 collision is recorded in
the prose above, where a record belongs.

## WHAT GLM'S MULTI-PART REVIEW FOUND, AND WHAT EACH FINDING TURNED OUT TO BE

Three parts: 1=FAIL, 2=FAIL, 3=PASS, so the branch FAILED by conjunction. Four
grounds, measured one by one rather than accepted or dismissed as a set:

1. **`lint.is_contract_failure` had no production caller** — TRUE. Its only
   caller was this branch's own test helper, which is the "helper nothing calls"
   shape the branch itself deleted `_selected_offer` for. **Fixed**: the helper
   is removed and the test now asks through `lint.explain_contract`, which
   production DOES call (`lint.explain`, `src/lint.py:405`). One authority, one
   caller, 53/53 green.
2. **Acceptance command 4 was `or True`-vacuous** — TRUE, and mine. Deleted; see
   the negative-control note.
3. **"`lint.word_range` was deleted and a caller may now raise
   AttributeError"** — **REFUTED by measurement.** The function MOVED:
   `src/lint.py:735` calls `writercontract.word_range(...)` and the definition
   lives at `src/skills/cold_email_writing.py:48`. A grep over `src/` and
   `scripts/` finds no remaining `lint.word_range` call — only comments
   describing the move.
4. **The loader ERROR for the deleted
   `test_a_thread_reply_has_its_own_word_range` module** — NOT the branch's.
   Measured: nothing in `tests/`, `src/` or `scripts/` registers that module;
   the only references are prose in the new test's docstrings. The verifier's
   own `_changed_test_files` takes git's changed-file list, which INCLUDES
   deletions, and then runs them. That is a verifier defect and it has its own
   task.

**THE FRESH RUN IS DONE AND IT IS CLEAN.** Finding 1's fix touched `src/lint.py`
and a test, which superseded the first 231/0/0 — so the branch was measured
again at `70e86de2`: **231 failing names against the reference's 231, 0 new, 0
gone**, 2,086 seconds, one `Ran` line, both of refdiff's controls passing, and
both sides measured in neutrally-named trees (`wt-wordcontract` and
`resonate-ops/ref-cd8e00bc`) so A44's path exemption cannot distort either.

The sentence that used to sit here said a fresh run was still required. It was
true when written and GLM's second review quoted it back as a reason to refuse —
correctly, from what it could see. **A task file that goes stale inside one night
is a task file that misleads its own reviewer.**

## THE REMAINING BLOCKER, from the second review: the KEYLESS doors are untested

GLM's part 3 FAILed the branch on this and it is real:

> "none of the four keyless production lint doors the contract exists to gate is
> called by any test on the branch"

Four production callers reach `lint.check(rec, key, step)` **without** a step
key — `approve`, `eligibility`, `executionguard` and `campaigns` — and the
contract only applies to them through `step_key_of`, the recovery that infers
the step from the record. The branch tests that recovery DIRECTLY
(`TestTheKeyIsRecovered`), but the **deleted** 295-line module was the only
place the keyless path itself was driven, and nothing replaced it.

So the gate the contract exists to stand in front of is, for those four doors,
covered by a test of its helper rather than by a test of the door.

**What closes it:** one test per door, or one test that drives at least one of
them end to end — build a record whose stored step is an under-contract body,
call the door the way production calls it (no `step_key`), and assert the
contract refusal comes back. Then mutate `step_key_of` to return None and watch
it go green, which is the proof that the recovery is what carries the contract
through.

That is the branch author's work, not a third repair pass from the gate: it
needs a test under `tests/`, which means another full run before this merges.

## Files

`src/lint.py`, `src/skills/cold_email_writing.py`, `src/copystages.py`,
`src/generate.py`, `prompts/draft.md`, and the tests.

## Not in scope

The new contract's numbers (TASK-964). The SENT authority that the OTHER
TASK-943 is about.
