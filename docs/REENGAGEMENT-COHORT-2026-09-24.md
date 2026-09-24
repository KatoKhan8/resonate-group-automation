# Re-engagement cohort — 2026-09-24

Built to §7.2 of `docs/PRODUCTION-HANDOFF-2026-09-24-EVENING.md`. **BUILD AND
REPORT ONLY.** Nothing was pushed to a provider, nothing was enrolled, no
campaign was created or activated. The only provider traffic was
`GET /campaigns` (read-only, one paged walk) to obtain current campaign
statuses, on which every lane depends.

**Counts and provider ids only. No prospect names, companies or addresses.**

Measured at master `0c6fdc71`, as of **2026-09-24T17:48Z**. The count is
time-dependent — see §0.

---

## 0. THE HEADLINE

    REENGAGE, derived from the operator's criteria   1,062
    US subset (campaign 264)                           321
    US subset incl. campaign 495                       337

    the operator's 985   reproduces exactly as the same lane at ~01:00-02:00Z
                         on 2026-09-22
    the operator's 289   reproduces exactly as campaign 264's REENGAGE from
                         ~03:00Z on 2026-09-22 onward

Both figures reconcile. Neither is wrong and neither is today's answer: **this
lane grows every day by construction**, because it is defined by an age
threshold and leads cross 90 days while the file sits still. The inventory is
the same 2,081 rows in both cases.

**But the cohort is not pushable as it stands — see §5.** 1,045 of the 1,062
are the client's own April campaigns and have no record in our store at all.

---

## 1. WHAT WAS READ, AND THE TWO CORRECTIONS TO THE HANDOFF

`src/reengagement_inventory.py` **does not exist**. The module is
`scripts/reengagement_inventory.py` (495 lines).

The handoff records both modules as "read-only and make no provider calls".
Half of that is right and the half that is wrong matters:

- **No provider WRITES.** Confirmed. `scripts/reengagement_inventory.py`
  imports no write verb; `src/providers/bison._paged` issues
  `request("GET", ...)` only.
- **It does make provider calls.** `--walk` calls `bison.membership()` and
  `bison.lead()` per lead; `--report` → `lanes_now()` → `live_statuses()`
  issues a paged `GET /campaigns`. A session that believes "no provider calls"
  and then runs `--report` has made network calls it did not intend.
- `src/revival.py` has no network primitive and no provider import on its own
  path — it reads canonical state only (`account`, `accountpolicy`, `fatigue`,
  `store`). Provider modules are reachable transitively via `adapters` and
  `clients`, but nothing in revival's call path invokes them. Read-only:
  confirmed.

`src/revival.py` is the REVIVE-side module and is **not used to build this
cohort**. The REVIVE lane stays out, per the operator.

---

## 2. THE INVENTORY IS THE RIGHT FILE, AND ITS STORED LANE COLUMN IS A TRAP

`work/stage/reengagement-inventory.jsonl`, 2,081 rows, 0 duplicate lead ids,
0 rows missing `last_touch`. Membership states match the operator's figures
exactly:

    stopped            1,400
    in_sequence          530
    sending_paused        80
    replied               57
    bounced               13
    sequence_finished      1
    total              2,081

File mtime is **2026-09-23 23:05**, not 09-22. It is the 09-22 inventory
extended by a later resumed walk — the walk is resumable by construction and
appends.

**The file carries two stale lane columns and neither may be read.** It is a
mix of two schema generations:

    lane / why                1,415 rows   pre-ISSUE-017: computed with NO
                                           campaign status. Says NEVER 1,360,
                                           REENGAGE 0.
    lane_at_walk / why_at_walk  666 rows   stamped campaign_status_at_walk
                                           "active" — but campaign 495 has
                                           archived since, which moves its
                                           leads.

This is ISSUE-017 exactly as the module's own comment describes it: a reader
who trusted the stored column "saw REENGAGE 0 against a live answer of 985".
Every number below is from `lane_for()` **recomputed against current provider
status**, which is what `lanes_now()` exists to do.

All 16 campaigns in the inventory resolved at the provider — no campaign was
missing, so no lane was derived from a guessed status.

    262 archived   263 archived   264 archived   495 archived
    418 active     481 active     487 active     489 active
    491 active     492 active     493 active     494 active
    496 active     497 active     498 active     451 completed

---

## 3. THE FUNNEL

As of **2026-09-24T17:48Z**. Each exclusion is disjoint and the column sums to
the base.

    base inventory                                        2,081
      - bounced                                              13
      - replied  (REVIVE — human drafts only, stays out)      57
      - unsubscribed                                           0
      - already in a live sequence                           530
      - stopped inside a still-running campaign
        (unknown stop reason — NEVER by the operator's rule)  160
      - too recent (last touch <= 90 days)                   259
      - no touch date                                          0
    = REENGAGE                                            1,062
                                                          ------
      check sum                                           2,081

Lane totals for cross-reference: NEVER 173, ACTIVE 530, REVIVE 57,
REENGAGE 1,062, UNKNOWN 259.

### 3.1 The 90-day boundary is worth one decision

The code uses `age > 90` (strictly greater). The operator's wording is
"contacted 90+ days ago", which reads as `age >= 90`. **48 rows sit at exactly
90 days.** On the operator's literal wording the lane is **1,110**, not 1,062.
Flagged rather than chosen — the code's threshold is used throughout this
document.

### 3.2 REENGAGE by campaign

    262   504    archived, client campaign, AU
    263   221    archived, client campaign, AU (v2)
    264   321    archived, client campaign, USA
    495    16    archived, ours (US-HOURS batch1)
    ----------
        1,062

---

## 4. THE US SUBSET, AND WHAT IT RESTS ON

**321** (campaign 264), or **337** including campaign 495.

The honest caveat: **no row in the inventory carries a country field.** The
row keys are `provider, campaign_id, lead_id, state, last_touch, created_at`
plus the two stale lane columns. Nothing else. So geography is derived from
the **campaign name** at the provider — 264 is the USA campaign of the April
4th set, 262/263 are its Australian siblings. That is the same basis the
operator's "289" used, and it reproduces the 289 exactly, so the two agree on
method as well as number.

Campaign 495 is ours and its name carries `US-HOURS`, which is a **sending
window, not a geography**. Independent corroboration exists for it: all 16 of
its REENGAGE leads join to a store record and every one carries `cohort: us*`.
So 495's 16 are genuinely US and 337 is defensible — but 321 is the direct
like-for-like successor to "the 289" and is the figure to quote.

---

## 5. THE STORE CROSS-CHECK REMOVES 0, AND THAT IS NOT REASSURANCE

Join key is `contacts[].bison_lead_id`, present on 756 store contacts.

    REENGAGE candidates                        1,062
      joined to a store record                    17
      NOT joined — no store record exists       1,045
      of the 17, carrying a reply/unsub/stop       0

    -> the store cross-check EXCLUDES 0 candidates

**The 0 is a coverage artefact, not a clean bill of health.** 1,045 of 1,062
are campaigns 262/263/264 — the client's own April campaigns. They have no
store record, so no contact, no email, no domain, no ICP verdict, no MX
result, no verification and no engagement history. There is nothing to
cross-check them against.

The check does work where there is data. Across the whole 2,081-row inventory
**28 leads carry a store-side reply, stop or DNC**, and every one of them was
already excluded by the lane rules:

    REVIVE  17     campaigns 491, 492, 497 — membership state `replied`
    NEVER    6     campaigns 491, 492, 497
    ACTIVE   5     campaigns 491, 492
    REENGAGE 0

Store and provider agree on all 23 of the REVIVE/NEVER cases. **They disagree
on 5**: those leads carry a reply or stop event in the store and are still
`in_sequence` at the provider. That is outside this cohort and does not change
any number here, but a lead the store says replied is still being mailed and
that is worth someone's attention.

### 5.1 Three criteria cannot be fully satisfied from the data

Stated rather than approximated, as instructed.

1. **"Contacted 90+ days ago" has no confirmed touch event.** `last_touch` is
   bison `lead.updated_at` — a provider **last-activity** timestamp. The
   module's docstring chooses it deliberately and correctly over `created_at`
   ("a lead created in April may have been mailed last week"), and it is the
   best field available. It is still a proxy: no row in this inventory carries
   a confirmed send event. The 90-day criterion rests on last-activity, not on
   a proven touch.

2. **"No reply ever" rests entirely on one membership state string.** No row
   in the file carries a `replied`, `bounced`, `unsubscribed` or `complained`
   flag — the walk writes those keys only when it fetches `lead()` fresh, and
   every row here was dated from the cached `last-touch.json` index instead.
   `lane_for()` reads `row.get("replied")`, which is `None` on all 2,081 rows.
   So reply detection is the 57 rows whose membership state is literally
   `replied`. A lead who replied and was afterwards marked `stopped` reads as
   stopped and lands in REENGAGE.

3. **"No unsubscribe" is unverified on both sides.** Zero inventory rows carry
   an unsubscribe state or flag, and **the store has no unsubscribe event type
   at all** — 41 distinct event types, none of them an unsubscribe or opt-out.
   The exclusion is reported as 0 because nothing in either source can produce
   a non-zero. This criterion is not currently checkable.

---

## 6. WHAT THIS MEANS FOR THE PUSH

The push stays with the foreground session. Three things it should know:

- **1,045 of the 1,062 have never passed this system's own gates.** They are
  the client's leads from April, known to us only as a provider lead id and a
  membership state. The operator's 2026-09-21 grant does cover them ("every
  lead currently in EmailBison ... is client-approved for re-engagement"), so
  this is not a permission problem. It is an evidence problem: there is no
  verified address, no ICP verdict and no suppression history for any of them.
- **The number moves daily.** 1,062 today, 985 on 09-22. Any cohort built from
  this lane must be stamped with the instant it was derived, or the next
  session will reconcile two correct numbers and conclude one is a bug.
- **Campaigns are their own, `source = reengagement`** — unchanged, and not
  created here.

---

## 7. REPRODUCING THIS

    py -3 scripts/reengagement_inventory.py --report

recomputes the lanes against live campaign status. It refuses with
`StatusesUnreadable` rather than guessing if the provider cannot be read,
which is correct — a stop read without a campaign status becomes NEVER and
over-counts the exclusion. Do not read `lane` or `lane_at_walk` from the
JSONL; both are stale by design.
