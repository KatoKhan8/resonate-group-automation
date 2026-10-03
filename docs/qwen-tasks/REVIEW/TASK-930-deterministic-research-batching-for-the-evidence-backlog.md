PRIORITY: P0
SIZE: M
DEPENDS: 

# TASK-930 — batch the evidence backlog through the EXISTING canonical path

**Operator decision, Zvonimir, 2026-09-30:** the evidence bar stays. A
shortfall is a research problem, per company: *insufficient evidence → run
the canonical Apify/research path → richer sourced pack → re-evaluate →
still insufficient → HELD with the exact reason → continue.*

**And:** do not make Claude process 614 accounts one at a time, and do not
bulk-run 614 paid researches until one account has proved the path.

## The path is already proved. Do not rebuild it.

Measured on master `e7e7de7a`, `sohoexp-com` (source row 65):

    before   0 research rows, 0 admitted
    ops      people-count (free), then apify-research, reason
             `public_evidence_required_for_prospect_facing_copy`
    bounded  5 pages, 20 items, 180s, RunBudget(1)
    after    4 rows, 1 admitted

The wiring exists: `research.NEED_COPY_EVIDENCE`, `research.why(...,
for_copy=True)`, `research.run(..., for_copy=True)` and
`enrich.enrich_record(..., for_copy=True)`. **`enrich_record` is the only
call site that owns the `spend` ledger and you must go through it.** A second
research caller with its own ledger is invisible to the spend audit, and an
audit that reports clean because it watched nothing is worse than none.

## What to build

A deterministic, resumable batch controller over the accounts that
`research.why(rec, for_copy=True)` reports as `NEED_COPY_EVIDENCE` — **614 of
1,582 at the time of writing**.

1. **Order is the operator's approved source order**, from
   `work/Productive/productive_ICP_safe_to_send (1).csv`, not queue order and
   not "whatever is cheapest". `scripts/canary_candidate_walk.py` already
   walks that file and is the precedent for the ordering and the
   QUALIFIED/HELD/NOT_QUALIFIED vocabulary.
2. **A cap per run, refused rather than exceeded**, in the shape
   `enrich.Budget` and `research.RunBudget` already have. An uncapped default
   is not acceptable: `require_cap` exists because an operator's omission is
   where unbounded spend comes from.
3. **Resumable from the estate, not from a checkpoint file.** An account that
   now has enough admitted rows is simply no longer in the set, so re-running
   the command IS the resume. Do not invent a second state file.
4. **Re-evaluate after each account** and record the disposition: reached the
   bar, or HELD with the exact evidence reason and the admitted-row count.
5. **Report qualified / held / not-qualified separately.** The operator asked
   for this explicitly: the ramp counts companies ATTEMPTED, and an easy
   account must never quietly stand in for an attempted one.

## What it must not do

- **Never lower `MIN_RELEVANCE` (0.65) or `MIN_COPY_EVIDENCE_ROWS` (3).**
  Two accounts already sit 0.05 under the relevance threshold, which is
  exactly the near-miss that invites tuning. Tuning it turns a measured
  shortfall into a silent pass on every record in the estate. The floor of 3
  is a measurement: TWO IS THE NUMBER THAT FAILED on `2020companies-com`.
- Never research a REJECTED account, or one with no contact to write to.
  `_copy_evidence_missing` already refuses both; do not route around it.
- No new features, no new state, no second representation of "does this
  account need research".

## Done means

A capped run over a named set of accounts produces per-account dispositions,
spends through the canonical ledger, is safe to re-run, and a dry run
performs no actor call at all. Prove the dry run writes nothing by asserting
on the estate, not by reading the code.

## RESULT

**STATUS:** REVIEW
**COMMIT:** a69e4960
**TESTS:** 18/18 pass in `tests/test_research_batch.py`. 10/10 pass in
  `tests/test_research_knows_the_writer_needs_facts.py` (prerequisite).
**FILES CHANGED:**
  - `scripts/research_batch.py` (new) — the batch controller
  - `tests/test_research_batch.py` (new) — 18 tests proving the properties
  - `docs/qwen-tasks/RUNNING/TASK-930-...` (moved from TODO/)

**ARTIFACT KIND:** code + test

**FINDINGS:**

1. The `for_copy` feature (`NEED_COPY_EVIDENCE`, `MIN_COPY_EVIDENCE_ROWS`,
   `research.why(..., for_copy=True)`, `enrich.enrich_record(..., for_copy=True)`)
   was NOT on the remote `qwen-worker-r9` branch. Cherry-picked the two
   prerequisite commits (`4ae050c1`, `e7e7de7a`) that add it. Both apply
   cleanly and their tests pass.

2. The batch controller goes through `enrich.enrich_record` — the only call
   site that owns the `spend` ledger. Verified by test: the script imports
   `enrich.enrich_record` and does NOT call `research.run` directly.

3. Dry run writes nothing — proved by snapshotting the estate before and
   after a dry run and asserting byte-identical JSON serialization of every
   record. Not by reading the code.

4. Cap is refused rather than exceeded. Live run without `--cap` raises
   `enrich.NoBudget`. Live run with `--cap 0` also raises it, because Apify
   bills in compute units the credit cap cannot see.

5. Resumable from estate: an account with enough admitted rows is classified
   QUALIFIED and not re-attempted. Re-running the command IS the resume.

6. Dispositions reported separately: QUALIFIED / HELD / NOT_QUALIFIED /
   SKIPPED, each in its own bucket.

7. Order follows the CSV, not queue order. Verified by test.

8. `MIN_RELEVANCE` (0.65) and `MIN_COPY_EVIDENCE_ROWS` (3) are unchanged.
   Asserted by test.

9. Never researches rejected or contactless accounts — they are NOT_QUALIFIED
   and never attempted.

**RISKS:**
- The prerequisite commits (`4ae050c1`, `e7e7de7a`) were cherry-picked from
  a branch that had them but the remote did not. If another branch also
  carries them, a merge may see duplicates. The commits are identical in
  content.
- The batch controller has only been tested in dry-run mode. A live run has
  not been executed (no Apify credentials in this worktree, by design).

**RECOMMENDED CLAUDE ACTION:**
- Review the script and tests.
- Run the first live batch from Claude's worktree with `--cap 1` to prove
  the end-to-end path on one account before widening.
- The generation step (writing to the production queue) is owed — this
  script reads the estate but does not write to `work/queue.jsonl`.
