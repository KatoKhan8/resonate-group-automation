# TASK-975 — the gate tells a reviewer every file is complete while handing it a file cut in half

The **fourth** defect found tonight in the merge gate itself rather than in a
branch, and like the other three it surfaced because a clean branch was refused
for a reason that turned out to be the tool's.

## What happened

GLM part 5 of 5 on `task-guard-regressions-rebased` returned:

> VERDICT: NEEDS_CLAUDE — the branch's committed SUITE evidence is cut
> mid-file, so whether its 232 fail/error outcomes are the pre-branch baseline
> or a live regression behind a 1-of-81-module acceptance run cannot be settled
> here.
>
> "The file is cut mid-file (28,863 of 51,319 chars): I cannot count entries
> against 232, cannot see whether the branch-touched modules' entries appear."

**The file is not cut on the branch.** Measured there:

    docs/state/SUITE-task-guard-regressions-2026-10-02.json
      49,758 chars, json.loads() -> OK, 81 modules, total 232

It parses whole. The cut was in the prompt the gate built, and under the
operator's standing rule NEEDS_CLAUDE does not pass — so this defect can stop
any branch that commits a large generated state file.

## The cause, measured

`fit_patch` is not at fault: given a file larger than the room it withholds it
whole and NAMES it, which was verified against a 4,000-line fixture. The defect
is one layer up, between two functions that contradict each other.

`patch_parts` gives an oversized file its own part, and its docstring says so
plainly:

> "A single file larger than `room` becomes its own part. The prompt then
> declares that part a mid-file cut, which is the honest description of it."

But `part_sentence` — the one sentence each call is given about the rest of the
patch, and the sentence that tells the reviewer **not** to abstain — states
unconditionally:

> "Every file is shown COMPLETE in exactly one part, and the branch's full file
> list is above. A question whose answer lies in another part is answered by
> NAMING THAT PART - not by NEEDS_CLAUDE."

Reproduced with a two-file patch, one small file and one far over the room:

    parts: 2  [['src/a.py'], ['docs/state/BIG.json']]
      part 1:    263 chars  over_room=False  sentence_claims_complete=True
      part 2:  28107 chars  over_room=True   sentence_claims_complete=True
                ^^ this part is CUT and its sentence says every file is complete

28,107 against the 28,863 GLM reported — the same shape, the same place.

**So the reviewer was told its file was complete and handed half of it.** It
noticed, said exactly which half it had, and refused to reconcile numbers it
could not see. That is the correct behaviour against a prompt that lied to it,
and the verdict should be read as a report on the gate, not on the branch.

## What to do

1. When a part holds a file larger than the room, its sentence must say so —
   name the file, state the characters shown against the total, and tell the
   reviewer that THIS is the one case where NEEDS_CLAUDE on that file's content
   is correct. The promise of completeness must become conditional on the fact.
2. **Do not spend the room on generated state at all.** `docs/state/*.json` is
   evidence, not code; the gate already sorts prose last (`PROSE_PREFIX`), and
   generated state belongs in the same bucket or behind a summary — count,
   `commit`, module total — instead of 50,000 characters of entries. That is
   the fix with leverage, because it removes the reason an oversized file was
   in the prompt in the first place.

## Acceptance

```
python -c "import sys; sys.path.insert(0,'scripts'); import glm_verify_branch as g; small='diff --git a/src/a.py b/src/a.py\n--- a/src/a.py\n+++ b/src/a.py\n'+'+ok\n'*50; big='diff --git a/docs/state/BIG.json b/docs/state/BIG.json\n--- a/docs/state/BIG.json\n+++ b/docs/state/BIG.json\n'+'+entry\n'*4000; room=5000; parts=g.patch_parts(small+big, room); assert len(parts)==2, [len(p) for p in parts]; bad=[i for i,p in enumerate(parts,1) if sum(len(t) for _,t in p)>room and 'shown COMPLETE in exactly one part' in g.part_sentence(i,parts) and 'BIG.json' not in g.part_sentence(i,parts).split('COMPLETE')[0]]; assert not bad, 'part(s) %s are cut and their sentence still promises every file is complete' % bad; assert 'src/a.py' in g.part_sentence(2,parts), 'the sentence stopped naming what the other parts hold'; print('OK an oversized part declares its own cut, and the other parts are still named')"
```

```
python -c "import sys; sys.path.insert(0,'scripts'); import glm_verify_branch as g; patch='diff --git a/src/a.py b/src/a.py\n--- a/src/a.py\n+++ b/src/a.py\n'+'+ok\n'*20; parts=g.patch_parts(patch, 5000); assert len(parts)==1, len(parts); assert g.part_sentence(1,parts)=='', 'a one-part review gained a part sentence, which would tell a complete review it is partial'; text,withheld=g.fit_patch(patch, 5000); assert not withheld and text==patch, 'a patch that fits whole was altered'; print('OK the single-part path is untouched')"
```

### NEGATIVE CONTROL

**Command 1 fails today**, naming part 2, which is the measurement above turned
into an assertion. It cannot be satisfied by deleting the completeness promise
wholesale: its last assertion requires the sentence to keep naming what the
other parts hold, which is the operator's condition for the multi-part design
and the thing that stops a reviewer abstaining because a caller lives
elsewhere. Nor can it be satisfied by refusing oversized files, since the part
count is asserted at 2 — the file must still be reviewed, just honestly
labelled.

Command 2 is the regression control in the other direction: a patch that fits
in one part must gain no sentence at all and must pass through `fit_patch`
byte-identical. A fix that starts appending a cut notice everywhere fails here.

Both run against the gate on `task-959-multipart-review`, where these functions
live.

## A second, narrower cut in the same file

`fit_patch` line 802 — `return patch[:room], []` — fires when
`split_patch_by_file` finds no files at all, and that path cuts silently with
an empty withheld list. It is not what happened here (the patch split fine into
16 files), and a patch with no parseable file header is a different problem, but
it is the same shape and it is the only remaining place in this file that cuts
without saying so. Worth closing in the same change.

## Files

`scripts/glm_verify_branch.py` — `part_sentence`, `patch_parts`, and whatever
decides what generated state contributes to a prompt.
`tests/test_the_glm_verdict_compares_like_with_like.py` for the regression.

## The other three, for the record

A44 (the path-substring exemption), TASK-969 (test files the branch deleted),
TASK-971 (the test-step budget). All three are fixed in the tool and **all
three are still OPEN**, because none has landed on master through its own gate.
This is the fourth, and it is not fixed yet.
