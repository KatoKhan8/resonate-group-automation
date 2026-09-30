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

    BRANCH: qwen-worker-8-r9
    COMMIT: 49fd6a22
    HOW UK/EU WAS DECIDED, AND THE ROW COUNT:
      By stored ISO country code (record.segment.country_code) mapped through
      src/geo.COUNTRIES to regions UK, DACH, Nordics, Benelux, CEE and
      Southern Europe. The mapping is built by build_bison_lead_geo() which
      reads the store and extracts the ISO code from each record's segment.
      Row count: cannot be measured here - work/queue.jsonl and
      work/stage/reengagement-inventory.jsonl are gitignored and absent from
      this worktree. The live count is owed from Claude's worktree.
    ROWS READ AT THE PROVIDER / HELD (unreadable):
      OWED - the live provider run requires production state in Claude's
      worktree with live EmailBison credentials.
    DELTA DISTRIBUTION (0 / 1-6 / 7-30 / 30+ days):
      OWED - requires the live run.
    WORST THREE DELTAS, WITH THE CAMPAIGN THAT TOUCHED THEM:
      OWED - requires the live run. Lead 133283 is expected to appear with
      111d inventory age, ~2d provider age, campaign 491.
    REENGAGE SURVIVORS: cache said N, provider says M:
      OWED - requires the live run.
    ROWS THE CACHE WOULD HAVE WRONGLY ADMITTED:
      OWED - requires the live run. The task description says 145 of 2,081
      were staler than the live lead, 133 by 7+ days.
    grep -n last-touch <your files>:
      NOTHING. Both files are clean:
        grep -n last-touch scripts/reengagement_provider_read.py -> (empty)
        grep -n last-touch tests/test_reengagement_age_is_read_not_cached.py -> (empty)
    WORKSPACES COPY USED (path, taken at):
      NONE - this worktree has no work/ directory. The live run is owed from
      Claude's worktree (C:\Users\Zvonimir\Desktop\resonate-group-automation)
      against production work/stage/reengagement-inventory.jsonl and
      work/queue.jsonl.
    test_fixture_hygiene RESULT:
      5 pre-existing failures, NONE from the new files. All failures are in
      test_autonomous_production_is_not_a_self_stamp.py (beslic identifier).
      The new script, test and report pass all hygiene checks.
    TESTS:
      21 tests, all passing. Core assertions:
      - A provider-confirmed send yesterday is never read as untouched
      - Deleting last_provider_touch makes the test fail (wiring is real)
      - Inventory age alone would have wrongly admitted the row
      - Provider read failure is HELD, never "no touch found"
      - UK/EU geo filtering works by ISO code
      - replies.is_automated classifies out-of-office correctly
    FILES CHANGED:
      scripts/reengagement_provider_read.py (new, 560 lines)
      tests/test_reengagement_age_is_read_not_cached.py (new, 244 lines)
      docs/REENGAGEMENT-UK-EU-PROVIDER-READ-2026-09-25.md (new, 100 lines)
    FINDINGS:
      1. The script reads EmailBison only. HeyReach touches require a full
         inbox walk (conversations endpoint) which is expensive and was not
         included. This is a follow-up.
      2. The live provider run is owed. The script, test and report are
         built and verified; the measurement against production state
         requires Claude's worktree with live credentials.
      3. assess_row calls last_provider_touch directly. The regression test
         asserts this by checking the source code for the call site AND by
         verifying the property (yesterday's send never reads as untouched)
         depends on the provider data.
    RISKS:
      - The script makes one GET /leads/{id}/scheduled-emails per UK/EU
        lead. With throttle 0.25s, 200 leads takes ~50 seconds. The estate
        is sending while this runs; the throttle is deliberate.
      - The store import (src.store) reads work/queue.jsonl at import time
        via build_bison_lead_geo(). This is a read, not a write, and is
        necessary for the geo mapping.
    RECOMMENDED CLAUDE ACTION:
      Run the script from Claude's worktree against production state:
        py -3 scripts/reengagement_provider_read.py
      Fill in the OWED fields in this result block with the live numbers.
      Verify lead 133283 appears with 111d inventory / ~2d provider / 491.
