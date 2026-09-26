PRIORITY: P0
SIZE: M
DEPENDS:

# TASK-328 — the approval hash is recorded and never checked

**SEVERITY: CRITICAL.** Buggie finding C1, `docs/BUGGIE-FINDINGS-2026-09-26.md`.
Verified by hand on master `0af11fcb` before this task was written.

## The defect

    src/providers/bison.py:1439     reviewapproval.require(campaign_id)
    src/providers/bison.py:1886     reviewapproval.require(campaign_id)
    src/providers/heyreach.py:1691  reviewapproval.require(campaign_id)

Those are **every** production call site. None passes `review_hash`.

`require(campaign, review_hash=None)` compares the hash **only when one is
given**:

    if review_hash is not None and str(given.get("review_hash")) != str(review_hash):

So the mismatch branch is unreachable in production, and
`reviewapproval.file_hash` is computed, quoted to the operator, stored by
`record()`, and then never verified by anything.

`reviewapproval`'s own docstring states the intent this defeats: the hash is
*"what makes the approval about a particular file rather than about the campaign
in general … An approval that survived a re-render would approve words nobody
read."*

**Consequence:** approval is campaign-level and permanent. Once a campaign
carries any approval row, a later `resume_campaign`, `activate_campaign` or
`attach_leads` top-up passes the gate carrying whatever copy is current —
including copy regenerated after the operator approved. On 2026-09-25, 64 emails
carrying a different agency's pitch reached real prospects. This is the same
failure mode at the one gate built to prevent it.

## Build

Thread the hash from the review file to the gate.

    src/providers/bison.py        MODIFY. resume_campaign and the attach_leads
                                  top-up path take review_hash and forward it.
    src/providers/heyreach.py     MODIFY. activate_campaign likewise.
    src/reviewapproval.py         READ ONLY unless a helper is genuinely
                                  missing. The gate logic is already correct;
                                  the defect is that nobody uses it.
    tests/test_an_approval_does_not_survive_a_re_render.py   NEW

`resume_campaign`, `activate_campaign` and the top-up path each gain a
`review_hash=None` parameter, forwarded to `require`.

## The decision you must NOT make on your own

Making `review_hash` **mandatory** would refuse every campaign whose approval row
predates this change — including 493, which is ACTIVE and sending right now. That
is an operator decision about existing approvals, not yours.

So: **thread the parameter, forward it, and make the mismatch refuse. Do not
change the behaviour when the caller passes nothing.** Write the "should a
missing hash refuse?" question under FINDINGS with the count of existing
approval rows that carry a hash versus not, so the operator can decide from a
number. Leave the default permissive and say so loudly in the result block.

## Acceptance — RUN each, paste real output

1. A mismatched hash REFUSES. This is the whole task, so prove it fires:

    py -3 -c "import sys;sys.path.insert(0,'.');from src import reviewapproval as R;\
    import inspect;\
    src=inspect.getsource(R.require);\
    print('gate still compares:', 'review_hash' in src)"

   then a real unit test that records an approval with hash `A`, calls the
   guarded function with hash `B`, and asserts the refusal is raised **and names
   the campaign and both hashes**.

2. **The guard is SEEN to fail and to pass.** Both directions, pasted:
   - matching hash -> proceeds past the gate
   - mismatched hash -> refuses
   - hash omitted -> proceeds (documented current behaviour, not silently changed)

3. Every call site forwards it. Assert on behaviour, not on the text of the
   source — a grep for the parameter name would pass on a comment:

    py -3 -c "import sys;sys.path.insert(0,'.');import inspect;\
    from src.providers import bison,heyreach;\
    for f in (bison.resume_campaign,heyreach.activate_campaign):\
      p=inspect.signature(f).parameters;\
      assert 'review_hash' in p, f.__name__+' does not accept review_hash';\
      print(f.__name__,'ok',list(p))"

4. **No provider call, ever.** Use a fake transport. This task may not touch
   EmailBison or HeyReach, and may not resume, activate or attach anything.
   The production freeze in `docs/OPERATOR-PRODUCTION-FREEZE-2026-09-26.md` is in
   force: no launches, activations, enrolments, attachments or sends.

5. Full suite: wait for `work/suite_verdict.txt`, diff the failing-name **SET**
   against the baseline. Not a count — a count that matches while the names
   differ has passed a broken suite here before. Do **not** grep for `^FAIL:`
   mid-run; it always returns 0 while the suite is still running.

## What this task may NOT do

- Do not weaken, widen or bypass any gate to make a test pass.
- Do not make the hash mandatory (see above).
- Do not modify an active campaign. 493 is sending.
- Do not touch suppression or the `LINKEDIN_STOP_LEAD` seal.

## Completion report

Section 11 of `docs/OPERATOR-DIRECTIVES-2026-09-25.md` in full, with the REMOTE
SHA verified on GitHub.
