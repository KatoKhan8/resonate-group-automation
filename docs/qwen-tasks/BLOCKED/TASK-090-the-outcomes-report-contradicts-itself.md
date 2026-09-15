# TASK-090 - the estate outcomes report contradicts itself in four places

## WHERE THIS CAME FROM

TASK-059 ran to completion overnight and wrote
`docs/ESTATE-BISON-OUTCOMES-2026-09-15.md` at 01:26 before the laptop shut
down. The run is RECOVERED - it is on branch `qwen-worker-4` at `f164f8c`
together with `scripts/bison_outcomes_analysis.py`. **Do not re-run the
collection to "be sure". It cost hours and the output survived.**

It was not integrated, because the numbers disagree with themselves.

## THE FOUR CONTRADICTIONS

**1. "Matched" counts rows that did not match.**

    Reply rows with scheduled_email_id     934 / 9726
    Matched dataset rows (reply + sched)   9726
    Scheduled status: sent 934 / unknown 8792

934 + 8792 = 9726. So 8792 rows have NO scheduled email and are still counted
as "matched". The matched figure is the TOTAL, relabelled.

**2. An empty body is reported as 0.0% unreadable.**

    Unreadable (extraction yielded empty)   0 of 9726 -> 0.0%
    Subject shape "(empty)"                 8792
    Body length band "<100"                 8792

The same 8792 rows have no subject and a body under 100 characters, and the
report calls the unreadable rate ZERO against a previous measurement of
46.5%. Checkpoint D's rule applies exactly: **a zero and a wrong lookup are
indistinguishable from the outside.**

**3. 1561 of 1570 positives come from rows with no body.**

    positive total        1570 (16.1%)
    positive at step 1-8     9
    positive at "? step"  1561

Every positive but nine sits in the bucket with no scheduled email, no
subject and a sub-100-character body. **Classifying an empty string as
positive is the failure mode TASK-067 was rejected for** - inventing a yes.

**4. 16.14% positive contradicts every other measurement in the repository.**

`docs/BISON-CADENCE-FINDINGS-2026-09-14.md` measured campaign 352 at 0.4%
reply and 327 at 0.3%. `docs/TAXONOMY-PRECISION-2026-09-14.md` measured
INTERESTED precision at 0.44. A 16% positive rate is not consistent with
either and no reconciliation is offered.

## WHAT TO DO

Work on branch `qwen-worker-4` so you have the script and the report.

1. **Find what those 8792 rows actually are** and what field the classifier
   read for them. The report itself says they are historical replies with no
   `campaign_id`, predating API lead creation. If the body lives under a
   different key on that shape - the way `company_facts` held what a reader
   looked for under `sizing` and got a false zero three times in one session -
   then find the key.
2. **Fix the reporting so a row that did not match is not counted as
   matched.** Report matched and unmatched separately with both denominators
   visible.
3. **Re-classify with the CURRENT taxonomy** and report positives separately
   for matched rows and unmatched rows. If the unmatched rows cannot be
   classified, they must report as UNKNOWN, not positive. Checkpoint D:
   do not reduce unknown by guessing, and 53.4% of unknowns are correctly
   unknown.
4. **Reconcile or retract the 16.14%.** Either explain why it differs from
   0.3-0.4% or state that it cannot be compared and why.

## WHAT NOT TO DO

- Do not re-walk the scheduled-email listings. The report is right that
  campaign 352 is 95,459 emails across 6,364 pages and that per-step
  denominators are out of budget. **Absent denominators is a legitimate
  finding.** Keep it.
- Do not quote 8.49%. It is unreproduced and this report correctly says so.
- Do not quote any open rate. `open_tracking` is False on all 22 campaigns.

---

## RESULT

**STATUS:** BLOCKED - requires branch qwen-worker-4

**COMMIT SHA:** N/A

**TESTS:** N/A

**FILES CHANGED:** None

**FINDINGS:**

### Blocker

This task explicitly requires working on branch `qwen-worker-4`:
> "Work on branch `qwen-worker-4` so you have the script and the report."

The script (`scripts/bison_outcomes_analysis.py`) and report (`docs/ESTATE-BISON-OUTCOMES-2026-09-15.md`) exist only on that branch. I am on branch `qwen-worker-3-r6` and cannot switch branches in this worktree.

I can read the files via `git show qwen-worker-4:...` but cannot modify them or run the script from this worktree.

### What the task requires

1. Find what the 8792 unmatched rows actually are and what field the classifier read
2. Fix the reporting so unmatched rows are not counted as matched
3. Re-classify with current taxonomy, report positives separately for matched/unmatched
4. Reconcile or retract the 16.14% positive rate

All four require modifying `scripts/bison_outcomes_analysis.py` and regenerating the report, which must happen on qwen-worker-4.

### What would unblock this

1. **Run this task from a worktree on qwen-worker-4** (e.g., qwen-worker-4-r2)
2. **Cherry-pick or merge the files to this branch** (but the task says to work on qwen-worker-4 deliberately)
3. **Claude runs this task** from the qwen-worker-4 worktree

### What I verified

I can read the report from qwen-worker-4 and confirm the four contradictions exist:
- Line 19: "Matched dataset rows (reply + sched) 9726" but only 934 have scheduled_email_id
- The 8792 unmatched rows are being counted as matched
- This inflates the positive rate to 16.14% (1561/9726) when the real matched positives are 9/934 = 0.96%

The contradictions are real and the task is valid, but it must be done on qwen-worker-4.

**RECOMMENDED CLAUDE ACTION:**
Queue this task for a qwen-worker-4 session, or run it from Claude's worktree if qwen-worker-4 is not available.
- Do not put unhashed prospect PII in the report. The existing one hashes
  addresses, company names and reply text. Keep that.

## DELIVERABLE

A corrected `docs/ESTATE-BISON-OUTCOMES-2026-09-15.md` where every number has
a denominator you can point at, plus a short section naming which of the
original numbers were wrong and why. A report that says "we could not measure
this" in four places is worth more than one that says 16.14%.
