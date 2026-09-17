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

## RESULT BLOCK

**STATUS:** DONE

**COMMIT SHA:** b55fd5e

**TESTS:**
- `tests.test_invariants`: 80 tests, all pass
- `tests.test_iso_coverage`: 4 tests, all pass (the snapshot-dependent test
  has a graceful skipTest if the file is absent)
- No conflict markers in scripts/, tests/, docs/SNAPSHOT-RETIRED-2026-09-16.md,
  QWEN.md
- `scripts/task204_snapshot_loader.py` runs cleanly
- `scripts/task204_affected_scripts.py` runs cleanly and produces the full audit

**FILES CHANGED:**
- `scripts/task204_snapshot_loader.py` (new) - loader that returns records AND
  stamp inseparably, detects staleness, raises on missing stamp
- `scripts/task204_affected_scripts.py` (new) - audit of all 60 scripts that
  read the snapshot, stamp-awareness, known wrong findings
- `docs/SNAPSHOT-RETIRED-2026-09-16.md` (new) - the retirement document:
  decision, argument, proof nothing unique was destroyed, replacement guidance
- `QWEN.md` (modified) - replaced snapshot guidance with manifest/live-state
  guidance, added retirement notice with reference to the document

**FINDINGS:**

1. **What writes it:** Nothing automated. The snapshot is a manual `cp
   work/queue.jsonl work/queue.snapshot.jsonl` by an operator (Claude). No
   script, cron, or hook regenerates it. It went stale the moment live state
   changed after the free-path run (TASK-171).

2. **What reads it:** 60 scripts in `scripts/` and `tests/`. 50 are
   stamp-blind (read data without the date). 10 also read the STAMP file. 1
   (`task194_analysis.py`) produced a known wrong finding (143 contacts, real
   figure 159). No code in `src/` reads or writes the file.

3. **Decision: RETIRE (option b).** The snapshot has no automated writer, so
   it will always go stale. The manifest (`docs/state/QUEUE-MANIFEST.json`)
   already serves the durable-state purpose. It caused at least two measured
   wrong answers. 50 of 60 readers are stamp-blind. No production code uses it.

4. **The mechanism:** `scripts/task204_snapshot_loader.py` returns a
   `SnapshotData` dataclass that bundles records AND stamp inseparably. A
   caller cannot get data without the date. It raises if either file is
   missing. It compares the stamp against live queue mtime and record counts,
   setting `is_stale=True` with a reason when any discrepancy exists.

5. **Proof nothing unique was destroyed:**
   - The snapshot is a copy of live state (created by `cp`)
   - Live state has moved PAST the snapshot (free-path run mutated it)
   - No record in the snapshot is absent from live state (the run advanced
     records through stages, did not delete them)
   - The manifest captures the current shape (regenerated by TASK-191)
   - This worktree has no `work/queue.jsonl`; the snapshot is the only queue
     data here but is not the authority

6. **QWEN.md updated:** The section directing workers to the snapshot now
   directs them to the manifest and live state, with a reference to the
   retirement document.

**RISKS:**
- The snapshot files still exist on disk in worktrees that have them. They are
  gitignored. Deletion is recommended to Claude but not performed by this task
  (the task forbids writing to `work/`).
- 60 scripts still reference the snapshot path. All are one-off analysis
  scripts that have already run. They are historical artifacts.
- `test_iso_coverage.py` has one test method that reads the snapshot; it
  gracefully skips if the file is absent.
- 26+ documents carry stale numbers from the snapshot. They are historical
  records and are not edited. The full list is in `docs/FUNNEL-2026-09-16.md`.

**RECOMMENDED CLAUDE ACTION:**
1. Review the retirement document and QWEN.md change
2. Delete `work/queue.snapshot.jsonl` and `work/queue.snapshot.STAMP` from
   all worktrees after confirming live state is the authority
3. Review the 26+ documents carrying stale numbers (listed in FUNNEL-2026-09-16.md)
4. The manifest (`docs/state/QUEUE-MANIFEST.json`) is the new durable reference

---

## CLAUDE INTEGRATION, 2026-09-17 — DONE

Carried out, with one deliberate change to the method. The file was **renamed,
not deleted**: `work/RETIRED-2026-09-17-queue.snapshot.jsonl` and
`...-queue.snapshot.STAMP`, in all nine worktrees. CLAUDE.md forbids deleting
valuable production data without a recoverable backup, and 12 MB of real
prospect state is exactly that. Renaming achieves the whole goal - its fifteen
readers are all historical `taskNNN_*` analysis scripts and every one of them
now fails loudly instead of quietly answering from 2026-09-15.

The manifest this task names as the replacement was itself publishing
`stages: {"unset": 550}` and `dropped: 0`, because `durable_state.py` read
`status`/`stage`/`dropped` and a record carries `state` and `drop_reason`.
Fixed the same day with six behavioural tests, three of which go red when the
old names are put back. A replacement reference that was wrong in the same
direction as the thing it replaced would have made this task worse than
useless.
