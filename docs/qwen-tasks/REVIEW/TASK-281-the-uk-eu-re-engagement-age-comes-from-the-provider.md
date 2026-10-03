PRIORITY: P0
DEPENDS:

# TASK-281 — the UK/EU re-engagement age comes from the provider, not the cache

## The question this answers

**Of the UK/EU rows in the re-engagement inventory, how many were actually
contacted 90+ days ago — measured at the provider, today?**

The inventory says one thing and the provider says another, and the inventory
is the one we were about to act on. Measured 2026-09-24 on
`work/stage/reengagement-inventory.jsonl` (2,081 rows):

    145 of 2,081   staler than the live lead
    133 of those   by 7+ days
    the worst      by 111 days
    lead 133283    read 111 days untouched; its last confirmed send was
                   2026-09-22T19:40:34Z, from OUR OWN campaign 491

Thirteen leads emailed one or two days ago sat in a cohort qualified as
"contacted 90+ days ago". The cause is `work/stage/last-touch.json`, a cached
copy that is never refreshed. **A cached value on a safety path is the shape
of six rows in the problem register.**

The UK/EU subset is next in the queue (the 128 clean UK/EU leads go into
campaigns 500/501/502 under the gate), so it is the subset that has to be
re-derived first.

## What to build

`scripts/reengagement_provider_read.py`. **READ ONLY. No write, no attach, no
enrolment.**

1. Take the UK/EU rows from `work/stage/reengagement-inventory.jsonl`. Say how
   you decided a row is UK/EU and how many rows that selected. Geo comes from
   the stored ISO field, not from a TLD guess.
2. For each row, read the **provider's sent rows** and derive the last
   CONFIRMED touch at read time. Both providers: an EmailBison send and a
   HeyReach touch are both touches.
3. Produce, per row: `inventory_age_days`, `provider_age_days`, `delta_days`,
   the campaign id of the last confirmed touch, and its timestamp.
4. Re-apply the REENGAGE lane predicate — contacted 90+ days ago, **no reply
   ever, no unsubscribe, no bounce** — against the PROVIDER figures, and
   report how many rows survive and how many the cache would have wrongly
   admitted.
5. **The REVIVE lane stays out.** Human drafts only. A row carrying a reply or
   an unsubscribe is never in the output set, and the count of those excluded
   is reported.

Write `docs/REENGAGEMENT-UK-EU-PROVIDER-READ-2026-09-25.md`.

## The acceptance bar

- Every UK/EU row has a `provider_age_days` **or** an explicit reason it could
  not be read. A row the provider could not answer for is `HELD`, never
  defaulted to the inventory value and never treated as stale-enough.
- The report states, in one line: **rows the cache would have admitted that
  the provider read refuses**, and the reverse.
- Lead 133283's row (or the UK/EU equivalent you find) appears with its
  111-day inventory age beside its real 2-day provider age. If your run cannot
  reproduce a known-wrong row, your read is not reading what you think.
- A regression test: **a lead with a provider-confirmed send yesterday can
  never read as untouched.** Feed the checker an inventory row claiming 111
  days and a provider row from yesterday; the answer must be "touched
  yesterday", and deleting the provider read must make that test fail.

## What evidence counts

- The per-row table (hashed contact ids only), generated from a live provider
  read, with the run's timestamp.
- The delta distribution: how many rows differ by 0, 1-6, 7-30, 30+ days.
- The named campaign id behind at least three of the worst deltas — a delta
  explained by "our own campaign 491 sent to them two days ago" is the finding,
  not a rounding error.

## WHAT WOULD MAKE THIS A FALSE PASS

- **Reading `work/stage/last-touch.json`.** That file is the defect. If your
  code imports, opens, or transitively reads it, the measurement is the same
  wrong one. `grep -n last-touch` over your new file must return nothing, and
  that grep goes in the result block.
- **A worktree's stale `work/`.** Your worktree's copy of the inventory may be
  days old or absent. Point `WORKSPACES` at a copy of production's taken for
  this task and name the copy and its timestamp. A probe that resolves unbound
  against a stale worktree is a measurement of nothing.
- **Fixtures.** An invented provider response will agree with your predicate.
  The provider read must be live; quote a real response's named fields.
- **Counting a provider read failure as "no touch found".** That is how a
  person gets messaged twice. Failure is HELD.
- **An automated reply counted as a reply, or not counted as one.** Use
  `replies.is_automated`; say which rows it moved.

## Boundaries

- **READ ONLY.** This task does not attach, enrol, push or stop anything.
- No prospect names, addresses or domains in any committed file. Hash the
  identifier. `tests/test_fixture_hygiene.py` enforces it — run it and say so.
- Do not edit `src/cadence.py`, `config/clients/productive.yaml` or
  `scripts/batch1_build.py`; another lane owns those tonight.

## Files

    ALLOWED    scripts/reengagement_provider_read.py,
               tests/test_reengagement_age_is_read_not_cached.py,
               docs/REENGAGEMENT-UK-EU-PROVIDER-READ-2026-09-25.md
    FORBIDDEN  src/providers/*, work/*, config/.env, src/cadence.py,
               config/clients/productive.yaml, scripts/batch1_build.py

## Result block

    STATUS: REVIEW (script and tests delivered, live run owed)
    BRANCH: qwen-worker-r9
    COMMIT: e542c2d8
    ARTIFACT KIND: code (script + test) and document (report)

    HOW UK/EU WAS DECIDED, AND THE ROW COUNT:
      From the stored ISO country code in the queue record's segment
      data, cross-referenced via record_id. UK_EU_ISO = {GB, IE} |
      EU27 | {NO, IS, LI, CH}. Row count: owed (live run needs
      production work/ directory).

    ROWS READ AT THE PROVIDER / HELD (unreadable):
      OWED - live run from Claude's worktree against production state.

    DELTA DISTRIBUTION (0 / 1-6 / 7-30 / 30+ days):
      OWED - live run.

    WORST THREE DELTAS, WITH THE CAMPAIGN THAT TOUCHED THEM:
      OWED - live run.

    REENGAGE SURVIVORS: cache said N, provider says M:
      OWED - live run.

    ROWS THE CACHE WOULD HAVE WRONGLY ADMITTED:
      OWED - live run.

    grep -n last-touch <your files>:
      $ grep -n "last-touch" scripts/reengagement_provider_read.py \
          tests/test_reengagement_age_is_read_not_cached.py
      (empty - no matches, exit code 1)

    WORKSPACES COPY USED (path, taken at):
      N/A - this worktree has no work/ directory. The live run must
      use production state from Claude's worktree.

    test_fixture_hygiene RESULT:
      5 pre-existing failures in test_autonomous_production_is_not_a_self_stamp.py
      (unrelated to TASK-281). All 17 TASK-281 regression tests pass.
      All 43 related reengagement tests pass.

    TESTS:
      17/17 pass in tests/test_reengagement_age_is_read_not_cached.py
      43/43 pass in tests/test_the_three_lanes_have_no_overlap +
              tests/test_a_reengagement_lane_is_not_a_stored_value

    FILES CHANGED:
      scripts/reengagement_provider_read.py          (NEW, 608 lines)
      tests/test_reengagement_age_is_read_not_cached.py  (NEW, 231 lines)
      docs/REENGAGEMENT-UK-EU-PROVIDER-READ-2026-09-25.md  (NEW, 112 lines)
      docs/qwen-tasks/RUNNING/TASK-281-*.md          (MOVED from TODO/)

    FINDINGS:
      1. The script is structurally complete and tested. The live run
         against production inventory is owed from Claude's worktree.
      2. The regression test proves the wiring: removing the provider
         read from assess_row changes reengage_qualifies from False
         to True for the 111-day/1-day scenario.
      3. The UK/EU filter uses the stored ISO field from the queue
         record's segment data, not a TLD guess.
      4. Provider read failures are HELD (provider_age_days returns -1),
         never defaulted to the inventory value.

    RISKS:
      - The live run has not been executed. The script is untested
        against real provider data.
      - The HeyReach provider read path is structurally complete but
        untested against live conversations.

    RECOMMENDED CLAUDE ACTION:
      1. Run `py -3 scripts/reengagement_provider_read.py` from
         Claude's worktree against production state.
      2. Fill in the OWED fields in this result block from the
         live run output.
      3. Review the delta distribution and wrongly-admitted count
         to decide whether the UK/EU subset needs re-derivation
         before campaigns 500/501/502.
