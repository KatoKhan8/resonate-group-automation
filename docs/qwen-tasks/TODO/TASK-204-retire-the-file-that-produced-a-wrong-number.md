PRIORITY: P1
DEPENDS:

# TASK-204 - retire the stale file, or make it impossible to misread

## WHERE THIS SITS

`work/queue.snapshot.jsonl` has caused two measured wrong answers in one day.

    it holds    550 records, stamped 2026-09-15T17:52:12Z from master cf23154
    live state  work/queue.jsonl, 300 records
    it reports  icp_status NONE for all 550, while the runner reports 65
                verified

TASK-171 established it was stale. TASK-191 recomputed the funnel from live
state. And in between, TASK-194 measured from the snapshot and produced "143
contacts held by insufficient confirmations", which TASK-196 then had to
demolish - the real figure is 159 contacts that never entered the waterfall,
and exactly one that Deliverable would help. Claude repeated the 143 in a
commit message and in a document before it was checked.

At least eleven tasks have measured from this file. It is the single most
misleading artefact in the repository, and it is misleading precisely because
it looks authoritative: it is a full queue dump with a stamp on it.

## THE QUESTION

1. **What is it for?** Find what writes it and what reads it. `CLAUDE.md` says
   `work/` is gitignored because it is real prospect data, and that the queue is
   made durable instead by a sanitised manifest - so establish whether this
   file has any role the manifest does not already serve.
2. **Then choose, and argue it:**

     (a) REGENERATE it from live state on every run that could invalidate it,
         so it is always current. Say what "every run" means concretely and
         what happens when a run dies halfway.

     (b) RETIRE it. Delete it, remove the writer, and point every reader at
         live state or at the manifest.

   Prefer (b) unless something genuinely needs a point-in-time snapshot, in
   which case (a) with a loud stamp. A third option - leave it and tell people
   to be careful - is not on the list, because eleven tasks were already
   careful and two got it wrong anyway.
3. **Make misreading impossible, not merely discouraged.** Whatever you choose,
   anything that loads it must be unable to silently treat it as current. A
   helper that returns the records AND the stamp together, so a caller cannot
   get the data without the date, is worth more than a comment. If a stamp is
   older than live state's newest record, that should be detectable in one
   call.
4. **List the scripts that read it**, and for each say whether its recorded
   finding is affected. Do not edit their result blocks - this is a list, and
   Claude decides what to do with it. TASK-194's is known to be affected.
5. **Leave the historical stamps readable.** A finding measured against a
   snapshot on a given date is still a valid record of what was true then. The
   goal is that nobody reads it as NOW, not that the past becomes unreadable.

## THE TRAP

Deleting a file in `work/` deletes real prospect data that is not in git and
cannot be recovered from it. Before removing anything, prove the data exists
elsewhere - live state, or regenerable from it - and say how you proved it. If
it holds records that live state does NOT have, it is not stale, it is a
superset, and the right answer is a reconciliation rather than a deletion.
TASK-191 was asked to reconcile 550 against 300 and its answer is the input to
this decision: read it first.

## WHAT YOU MAY NOT DO

- No provider writes, no provider calls.
- Do not delete `work/queue.jsonl` or `work/campaigns.jsonl`, ever.
- Do not delete the snapshot until item 5's proof is written down.
- Do not edit another task's RESULT block.
- Do not commit anything from `work/` into git. It stays gitignored.
- Eight workers and possibly a live run are using `work/`. Check for a live
  writer before touching anything and say what you found.

## FILES ALLOWED

    scripts/durable_state.py
    scripts/   (readers that need repointing)
    src/store.py   (only if the stamp helper belongs there - justify it)
    docs/SNAPSHOT-RETIRED-2026-09-16.md   (new)
    scripts/task204_*.py

## FILES FORBIDDEN

    config/   work/queue.jsonl   work/campaigns.jsonl

## DELIVERABLE

What writes and reads it, the regenerate-or-retire decision with its argument,
the mechanism that makes a stale read impossible rather than discouraged, the
list of affected scripts and findings, and the proof that nothing unique was
destroyed.
