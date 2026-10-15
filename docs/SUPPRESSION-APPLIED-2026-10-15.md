# THE 90 ARE ON THE LIST — applied 2026-10-15T08:34:13Z

TASK 0055, suppression lane. Ordered by the operator in
`DECISION-2026-10-15-three.md` item 3 ("primijeni 90"). Executed against the
plan in `docs/SUPPRESSION-APPLY-PLAN-2026-10-15.md` (TASK 0020), unchanged.

**VERDICT: APPLIED AND VERIFIED BY NAME-SET, BOTH DIRECTIONS.** 15 → 105
fingerprints. 90 added, 0 lost, 0 unexpected, 0 damaged lines.

**NO CONSUMER SENDS MORE.** The one substitution effect and the one new
outbound path are in §5 and are both unchanged from the 0020 finding.

---

## 0. The plan survived contact with the data

Every premise was re-measured before anything was written, because a plan that
no longer matches the data is a finding and not an obstacle. All four held:

| premise, from TASK 0020 | re-measured 2026-10-15 | holds |
|---|---|---|
| production file has 15 fingerprints, 15 rows, 0 damaged | 15 / 15 / NONE | yes |
| `the-94-classified.json` has 94 people, 4 already on the list | 94 / 4 | yes |
| the 4 `already_on_dnc` really are on the production file | all 4 present | yes |
| 0 of the 90 collide with an existing row | 0 collisions | yes |
| buckets of the 90 | 82 suppressed / 3 hold / 5 needs-review | yes |

The production file was last modified **2026-10-02 10:41 local** and had not
been touched since, so the 0020 measurement was still current rather than
merely still plausible.

## 1. The UNKNOWN from 0020 is now a number: the queue overlap is 0

TASK 0020 recorded "whether any of the 90 holds a queue record is UNKNOWN",
named `work/queue.jsonl` as the authority, and wrote the one read-only command
down rather than guessing. That command was run, from its own §5 pre-apply
checklist:

    0 of 90 hold a queue record        (1,584 records, 1,381 contacts)

**And the obvious control for that zero does not work, so a second one was
built.** Intersecting the 15 *pre-existing* production fingerprints against the
queue also returns 0 — so "0" is exactly what a broken reader would print, and
the pre-existing rows cannot serve as the positive control. The control that
does work: take one real queue contact, make its own fingerprint the target
set, and require the identical expression to find it.

    control target  record ogpartner-dk, contact jacob-faertz
    control hits    1
    CONTROL         READER WORKS

So 0 is a measurement. **The effect of this apply is latent today** — armed for
every future import, matching nobody currently in the queue and (0020,
measured) nobody in the 749-lead staged snapshot either.

## 2. What was written, and where

**File:** `C:\Users\Zvonimir\Desktop\resonate-group-automation\work\agency-dnc.jsonl`
— the MAIN checkout's, which is the only one anything reads.

**The command**, exactly as §2 of the plan names it, with `AGENCY_DNC` carrying
the production path because this lane works in a worktree and `work/` is
per-worktree and gitignored:

    AGENCY_DNC='C:\Users\Zvonimir\Desktop\resonate-group-automation\work\agency-dnc.jsonl' \
    py -3 scripts/apply_the_90.py --set the-90 --reason-undecided requested \
        --apply --backup 'C:\Users\Zvonimir\Desktop\resonate-group-automation\work\dnc-backup'

`--set the-90` is the operator's order read literally — reading A, the
proposal's own `to_add: 90`. `--reason-undecided requested` is forced by it:
without that flag the set resolves to 85 and the script refuses the whole run,
exercised again on the live path immediately before the apply and naming all
five. It is the recommendation 0020 recorded, and it is a disagreement with
this lane's own classifier for 8 people, in the conservative direction. Stated
again so it is not lost: **8 of the 90 were not called a clean opt-out by this
lane's independent pass** — 3 `hold` (2 gdpr-erasure, 1 company-closed) and 5
`needs-review`.

**Reasons written, derived from the classifying rule and never guessed:**
`{'requested': 87, 'legal': 2, 'internal': 1}`.

**No existing record changed.** The write is a pure append, and that is proven
by bytes rather than asserted: the 105-row file is **byte-prefix-identical** to
the 15-row backup. Line endings are uniform CRLF, 105 of 105, 0 bare LF, file
ends in a newline.

## 3. Snapshots. Two of them, taken before anything was written

    work/agency-dnc.jsonl.20261015T083351Z.bak     2,128 bytes   (task step 1)
    work/dnc-backup/agency-dnc.20261015T083413Z.jsonl
                                                   2,128 bytes   (script)
    work/dnc-backup/REVERSAL-20261015T083413Z.json 15,949 bytes  (manifest)

Both copies hash to the pre-apply original
`1f04997ff41ebd04ecdd96ec30ca187319a658eeecf740da9aa165fe510dc1c2`, and the
`.bak` was additionally confirmed with `cmp`, not only by hash. The manifest is
the only thing that makes the reversal provable; it is not disposable.

**Nothing else in `work/` was written.** `work/queue.jsonl` was opened for
reading only and is unchanged.

## 4. The verification, and why it is not the script's own read-back

The script proves itself (`NEW 90, GONE 0, 15 -> 105, damaged NONE,
APPLIED AND PROVEN BY NAME-SET`). That is the writer certifying its own write,
so it was redone by an independent reader whose before-authority is the
**`.bak` snapshot taken by hand**, not the manifest the script wrote.

    DIRECTION 1   all 90 targets PRESENT        0 absent
    DIRECTION 2   all 15 prior rows STILL PRESENT   0 lost
    CLOSURE       0 unexpected new fingerprints
                  after total 105, expected 105, damaged NONE

Both full lists are printed in
`work/suppression-measure/0055-verify-by-name.txt` (gitignored, so the names
are reproduced in the lane file entry). `UNKNOWN_IS_NOT_A_PASS` had nothing to
fire on: every one of the 90 was confirmed present individually, by name.

**The consumer chain was proven armed on a file of this exact shape**, because
105 parseable rows is not the same claim as "the send path refuses". The 90
digests have no plaintext on disk by design, so no candidate can be
constructed that hashes to one of them; instead the live 105-row file was
copied to a temp path, one row of the shape the apply wrote was appended for a
probe address, and the real consumer asked:

    before   lookup -> None       must_not_contact -> []
    after    lookup -> suppressed by agency safety policy (asked us directly)
             must_not_contact -> ['blocked:agency_dnc']

Production was untouched by that control and its hash was re-read afterwards to
prove it.

**The reversal was proven runnable, not described.** Dry run against the real
manifest and the real file: `would remove 90 physical row(s) of 90
fingerprint(s), would keep 15 row(s)`. Production hash unchanged by it.

## 5. Downstream — what each consumer does differently from now on

All 19 line references in the 0020 blast radius were re-read on disk today and
every one still carries the code it was recorded against; `agencydnc` still
appears 0 times in `account.py`, `fatigue.py` and `channels.py`. **No consumer sends more.** One behaves
differently in a way worth catching, one creates new outbound activity if
somebody runs it, and one statement from 0020 has changed.

### LOUD — the two that are not simply "fewer"

1. **`leadstop.sweep --live` would now issue provider STOP writes.** Each of
   the 90 holding a staged lead becomes `_must_stop` with
   `blocked:agency_dnc`. Those are provider writes, under the 2026-09-26
   freeze, and provider writes from this system remain 0. Stopping somebody who
   asked to be stopped is the *correct* write and it still needs the operator's
   explicit `APPROVED`. **Measured mitigation: overlap with the staged snapshot
   is 0 and overlap with the queue is now also 0 (§1), so no such write is
   reachable today.** `sweep` defaults to a dry run. **Do not sweep as part of
   this apply.** Applying the list and sweeping the provider are two decisions
   and only the first was ordered.

2. **Cohort composition changes; volume does not.**
   `scripts/build_control_cohort.py:153` filters on `must_not_contact` and then
   takes the first `limit` eligible. Removing 90 people from the eligible
   stream moves the cut line **down** and admits people who were below it. The
   limit binds, so nobody gets an extra email — but **any cohort built before
   today and shipped after it is not the cohort that was reviewed.** Rebuild
   and re-review any unshipped cohort. Hold at Batch 01 regardless.

### CHANGED SINCE 0020 — `suppression.reconcile` now has a caller

0020 recorded "zero callers in `src/` or `scripts/`". That is no longer
literally true: `scripts/suppression_snapshot.py`, added by this lane's own
TASK 0060, calls `suppression.reconcile` and `reconcile_all`. It is a
measurement harness, not production. **No production caller, unchanged and
still inert**, and this apply changes nothing about it.

### The rest, one line each

| consumer | call site | from now on |
|---|---|---|
| `eligibility.must_not_contact` → `_suppressed` → `agencydnc.lookup` | `eligibility.py:363` | returns `blocked:agency_dnc` for any of the 90 — **the root**, read off disk on every call, so it is in force with no restart and no cache to flush. |
| `nextaction.decide` | `nextaction.py:521`, `750` | `STOP / suppressed` for the **whole account**, before candidate selection, because the reason is in both `TERMINAL_CONTACT_REASONS` and `ACCOUNT_TERMINAL_REASONS`. Strictly fewer. |
| `eligibility.decide` | `eligibility.py:756` | `BLOCKED` instead of a step. Fewer. |
| `bisonfactory._refuse_suppressed_leads` | `bisonfactory.py:2497`, `2054` | the **whole enrolment run refuses** if a cohort contains one of the 90 — by design, and it will look like a breakage. Fewer, loudly. |
| `executionguard.revalidate` | `executionguard.py:1071` | the send door refuses at the last gate. Fewer. |
| `providerwrites.CONDITIONAL[EMAIL_RESUME]` | `providerwrites.py:1482` | a resume refuses when any contact on any record the campaign names is suppressed — so 487 / 489 / 493 can only have got **harder** to resume, never easier. Fewer. |
| `heyreachfactory.ensure_leads` | `heyreachfactory.py:1225` | refuses the LinkedIn push. Fewer. |
| `hygiene.check` | `hygiene.py:374` | verdict `agency_suppressed`, action `suppress`. |
| `web/upload.parse` import preview | `upload.py:307`, `560`; `app.py:1275` | **labels** the row rather than dropping it, deliberately, so the operator can read why. The record still imports and the send gates refuse later. A gap, not a leak — and not a send. |
| `web/api.py` hygiene / screen routes | `api.py:6304`, `6364` | the screen reports suppressed. Read-only. |
| `referral.resolve` | `referral.py:284` | a referred person on the list is `SUPPRESSED` instead of `READY`; the promotion path stops. Fewer. |
| `operatorexclusion.origins` | `operatorexclusion.py:661` | reports a `COMPLIANCE` origin. Read-only. |
| `fatigue.account_check` | `fatigue.py:243` | **nothing.** Checked specifically because it was the one plausible send-more mechanism: `active` derives from `confirmed_touches` and account state and is blind to the DNC, so a suppressed contact still occupies its concurrency slot rather than freeing it for somebody else. And it could not matter anyway — `nextaction` stops the whole account first. |
| `channels.evaluate` | — | **nothing.** `channels._suppressed` is a different, domain-level function that never reaches the agency list. Not a defect: `must_not_contact` runs at step 1, channels at step 2. |

One performance note, filed and not fixed because it is outside this task:
`operatorexclusion.origins` calls `agencydnc.lookup` with **no index** inside a
per-contact loop, so it re-reads the whole file once per contact. The file grew
15 → 105 rows, 7×. Irrelevant at this size; real if this list ever reaches
thousands.

## 6. What this task did not do

Did not run a provider call. Did not sweep. Did not resume 487 / 489 / 493.
Did not push or merge to master (`origin/master` still `b1f290c84`). Did not
release the suite lock. Did not read or apply or escrow a key, and did not open
`config/.env`. Did not delete the `.bak`. Did not write anything in `work/`
other than `agency-dnc.jsonl`, its two snapshots, the manifest and this lane's
own gitignored scratch under `work/suppression-measure/`. Did not change a
threshold, a gate, a cap, `src/` or `tests/`.
