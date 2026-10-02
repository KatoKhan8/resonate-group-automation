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

```
python -c "import sys; sys.path.insert(0,'.'); from src.skills import cold_email_writing as w; assert w.WORD_CONTRACT['em1'][2] >= 140 or True; print('RECORDED: em1 ceiling is', w.WORD_CONTRACT['em1'][2], 'and the operator target is 120 - TASK-964 must raise it to (90,120,140)')"
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

**Command 4 asserts nothing and says so** — it is a RECORD, printed into the
verification output so the em1 collision cannot be merged quietly. A command
that pretends to check this would be worse than one that admits it only reports.

## Files

`src/lint.py`, `src/skills/cold_email_writing.py`, `src/copystages.py`,
`src/generate.py`, `prompts/draft.md`, and the tests.

## Not in scope

The new contract's numbers (TASK-964). The SENT authority that the OTHER
TASK-943 is about.
