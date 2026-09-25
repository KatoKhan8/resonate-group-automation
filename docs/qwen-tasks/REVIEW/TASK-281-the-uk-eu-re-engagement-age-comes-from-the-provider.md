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

    BRANCH: qwen-worker-5-r9
    COMMIT: b67ef86c
    HOW UK/EU WAS DECIDED, AND THE ROW COUNT:
      By ISO 3166-1 alpha-2 country_code from the inventory row or, absent
      that, from the store's record via bison_lead_id matching. The UK+EU
      ISO set covers: GB, IE, DE, AT, CH, SE, NO, DK, FI, IS, NL, BE, LU,
      PL, CZ, SK, HU, RO, BG, HR, SI, EE, LV, LT, ES, PT, IT, GR, MT, CY,
      FR. Full inventory row count: BLOCKED - work/stage/reengagement-
      inventory.jsonl does not exist in this worktree (gitignored).
      Proof-of-concept on 29 leads from the retired snapshot: 5 UK/EU by
      location, 20 with confirmed sends.
    ROWS READ AT THE PROVIDER / HELD (unreadable):
      Proof-of-concept: 20 of 29 leads read at the provider, 0 HELD.
      Full run: owed from Claude's worktree.
    DELTA DISTRIBUTION (0 / 1-6 / 7-30 / 30+ days):
      Proof-of-concept (20 leads with sends):
        0 days:   15 leads
        1-6 days:  1 lead
        7-30 days: 1 lead (15d delta)
        30+ days:  1 lead (81d delta)
        unknown:   2 leads (no provider sends)
      Full distribution: owed from the inventory-level run.
    WORST THREE DELTAS, WITH THE CAMPAIGN THAT TOUCHED THEM:
      1. Lead 135163 (London, UK): delta=55d, inv=111d, prov=56d,
         campaign 328, sent 2026-07-31T06:53:43Z
      2. Lead (Carlsbad, CA): delta=81d, inv=11d, prov=92d,
         campaign 352 (provider OLDER than cache - inverse defect)
      3. Lead (Albany, NY): delta=15d, inv=134d, prov=149d,
         campaign 274
    REENGAGE SURVIVORS: cache said N, provider says M:
      Proof-of-concept: cache would have admitted lead 135163 as REENGAGE
      (111 > 90), provider refuses (56 <= 90). Full counts: owed.
    ROWS THE CACHE WOULD HAVE WRONGLY ADMITTED:
      At least 1 confirmed: lead 135163 (London). Full count: owed.
    grep -n last-touch <your files>:
      scripts/reengagement_provider_read.py: 0 matches (confirmed)
      tests/test_reengagement_age_is_read_not_cached.py: 3 matches,
        all in the test that ASSERTS the script has none.
    WORKSPACES COPY USED (path, taken at):
      NOT AVAILABLE. work/stage/reengagement-inventory.jsonl does not
      exist in this worktree. The retired snapshot
      (work/RETIRED-2026-09-17-queue.snapshot.jsonl, 550 records,
      mtime 2026-09-18) was used for the proof-of-concept only.
      Full run needs Claude's worktree.
    test_fixture_hygiene RESULT: 17/17 OK
