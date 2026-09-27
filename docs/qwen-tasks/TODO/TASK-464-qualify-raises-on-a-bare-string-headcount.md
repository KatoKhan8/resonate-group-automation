PRIORITY: P0
SIZE: S
DEPENDS:

# TASK-464 — `qualify.company` RAISES on a record the ingest itself wrote

**`ISSUE-049`, filed 2026-09-28.** Found while implementing decision B and
deliberately parked rather than fixed, because it is a different defect. It is
P0 because it is a crash on the qualification path, not a wrong answer.

## THE DEFECT

`src/ingest.py` writes the client CSV's `company_employee_count` into
`company_facts["headcount"]` **as a bare string**. `headcount.block_of` and
`headcount.witnesses` assume a **dict block**. So:

    qualify.company(rec)  ->  AttributeError

on any record the ingest wrote with that column populated. Reproduced on master
with decision B's change stashed, so it is **pre-existing and not caused by B**.

**What it means, and this is the part worth pausing on:** one half of the very
employee count decision B was written to protect **was never usable by
qualification at all.** The value was carried in, stored, and then crashed the
function that was supposed to read it. A fact that is computed and stored and
then breaks its own consumer is the sharpest form of this repository's signature
defect — worse than a value nothing reads, because it takes the caller down with
it.

## IT MAY ALREADY BE AFFECTING A RUNNING TASK

`TASK-430`, the read-only ICP audit of the 786 contacts in campaigns 491-500, is
classifying companies. **If it reaches `qualify.company` on a record with a
bare-string headcount, it crashes or silently skips that company** — and a
skipped company in that audit would be reported as one fewer company evaluated
rather than as an error, which would understate the answer the operator asked
for. **Check this first, before fixing anything**, and say in your result whether
`TASK-430`'s numbers are affected. If they are, the audit needs re-running after
the fix, and that matters more than the fix itself.

## SCOPE

1. **Reproduce it** on a record shaped the way `ingest.run` actually writes one —
   not a hand-made fixture. Name the ingest line that writes the string and the
   `headcount` line that assumes a dict.
2. **Decide which side is wrong and say why.** Either the ingest should write the
   canonical block shape, or `headcount` should accept a bare value. Prefer
   canonical state: whatever shape the rest of the system already treats as the
   truth for a headcount wins, and the other side is corrected to match. Do not
   add a second representation, and do not "handle both" unless you can show both
   are legitimately produced elsewhere.
3. **Do not swallow it.** An `except AttributeError` that returns UNKNOWN would
   turn a crash into a silent wrong answer, which is worse. No silent fallbacks
   on a qualification path: classify explicitly and fail closed.
4. Count how many records in the real store carry the bare-string shape. **Work
   on a COPY of `work/queue.jsonl` and never mutate the production store** —
   verify byte-identity (md5) before and after and say so.

## ACCEPTANCE

1. `qualify.company` returns a verdict, not an exception, for a record the real
   ingest wrote with `company_employee_count` populated — proved through
   `ingest.run` on a small CSV rather than a fixture dict.
2. The count of affected records in the real store is reported, with the method.
3. **A statement of whether `TASK-430`'s ICP audit numbers are affected**, and if
   so, that it must be re-run.
4. Missing evidence is never positive evidence: a record with no headcount at all
   still yields the same verdict as before this change — assert it.
5. MUTATION: reintroduce the shape mismatch and confirm the intended test fails
   for the intended reason, with no other guard firing first. Assert the file
   changed before running; this tree is CRLF, so a text-mode rewrite that
   normalises to LF is not a restoration.
6. No new failing name in the suite, compared by NAME with the same harness on
   both sides (`scripts/suite_baseline.py`). The baseline is known to be short by
   4 verified names; report, never adopt a new one, do not edit that file.

## BOUNDARIES

Provider writes 0. Never call a real provider or model. The freeze is in force;
do not touch campaigns 487/489/493; `sending.live` stays off for productive.
Reserved files — do not edit: `src/bisonfactory.py`, `src/generate.py`,
`src/generate_campaign.py`, `tests/test_generate.py`, `src/claims.py`,
`src/executionguard.py`, `src/copylint.py`, `src/packfacts.py`.
**`src/ingest.py` may be edited for this task** if that is the side that is wrong.
