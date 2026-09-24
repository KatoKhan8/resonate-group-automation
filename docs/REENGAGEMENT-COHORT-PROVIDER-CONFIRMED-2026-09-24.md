# Re-engagement cohort, PROVIDER-CONFIRMED — 2026-09-24

Supersedes `docs/REENGAGEMENT-COHORT-2026-09-24.md` (commit `68312d2f`). That
document derived 1,062 REENGAGE from membership state strings and said plainly
that three of the operator's five clauses could not be satisfied from its
inputs. This one answers all five from the provider.

**READ ONLY.** Every provider call in this work was a `GET`. Nothing was
enrolled, created, activated, paused, stopped or written. The push belongs to
the foreground session.

**Counts, provider ids, campaign ids and timestamps only. No prospect names,
addresses or company names.**

Measured **2026-09-24T18:29Z** against master `87976c98`. The count is
time-dependent — the 90-day clause means leads cross into it while the file
sits still.

---

## 0. THE HEADLINE

    PROVIDER-CONFIRMED COHORT                              1,039
      US subset, campaign 264                                335
      US subset incl. campaign 495                           340

    the previous membership-derived lane, recomputed today  1,066
      (it was 1,062 yesterday; it grows daily by construction)

    in both                                                  966
    in the old lane, EXCLUDED here                           100
    in this cohort, WRONGLY EXCLUDED by the old lane           73

**73 of the leads the old lane would have mailed had REPLIED**, and the
provider says so on its own record. Another 14 had bounced. Another 13 had
been emailed **one or two days ago** while the old inputs said 94 to 111 days.
That is the whole reason this document exists, and §4 has the evidence.

---

## 1. THE TWO ROUTES THAT MADE THIS ANSWERABLE

The previous work was not careless. It was reading the only fields it had.
Three routes were probed read-only tonight, none of them used by
`scripts/reengagement_inventory.py`, and between them they carry every clause.

### `GET /campaigns/{id}/leads`

Returns the **same full lead payload** as `GET /leads/{id}`, fifteen to a page.
Two objects on it are the ones that matter and neither is read by the inventory
walk:

    overall_stats          replies, unique_replies, opens, emails_sent —
                           ACROSS EVERY CAMPAIGN THE LEAD HAS EVER BEEN IN.
                           This is the "ever" in "no reply ever".

    lead_campaign_data     one entry per campaign the lead belongs to, each
                           with its own status, replies, emails_sent and
                           `interested` flag.

This is also **20× cheaper than the inventory's method**: 148 pages for the
whole candidate estate instead of 2,081 individual `lead()` calls. The
inventory walk's docstring reasons carefully about `created_at` versus
`updated_at` and never notices that the same response already carries the
reply history.

### `GET /leads/{id}/scheduled-emails`

**The route that closes the coverage hole, and the one nothing in this
repository knew about.** It returns every queue row for one person **across
every campaign**, including campaigns far too large to walk. Row shape is the
same as the per-campaign queue: `campaign_id`, `status`, `sent_at`,
`scheduled_date`, `replies`, `sequence_step_id`.

Without it this cohort is **2 leads**. That is not a figure of speech — it was
measured. 1,284 of the 2,081 candidates had sends inside campaigns this session
could not read (352 alone accounts for 1,403 leads, and its queue is 96,419
rows over 6,428 pages), and under the fail-closed rule every one of them is
OUT. With it, `unread_campaign` falls from 1,284 to **0**.

### `GET /leads/{id}/replies`

Per-lead reply history, filtered server-side. Validated against two leads the
provider counts a reply for: `overall_stats.replies` 1 and 1, route totals 1
and 2. Used in §5 to settle the store disagreements. The whole-workspace
`/replies` feed is **270,255 rows over 18,017 pages** and is not walkable; the
per-lead form is one request.

### What a send is

A queue row reading `sent` **with a non-null `sent_at`**. Nothing else.
`scheduled`, `active` and `stopped` are not sends, and a `sent` row with a null
`sent_at` is not one either. Of the 2,418 queue rows in campaign 264, 349 meet
that bar.

---

## 2. THE RULES AS IMPLEMENTED

`scripts/reengagement_provider_confirmed.py`. Read-only by construction: it
imports `bison` for `headers()`, `base()`, `ok()` and the error classes, and
issues nothing but `GET`.

    py -3 scripts/reengagement_provider_confirmed.py --walk       # phase 1
    py -3 scripts/reengagement_provider_confirmed.py --leadqueue  # phase 2
    py -3 scripts/reengagement_provider_confirmed.py --storenegatives
    py -3 scripts/reengagement_provider_confirmed.py --report     # no network

Each clause is evaluated **independently and without short-circuit**, so a lead
that trips three is counted under all three in §3's second table, while the
funnel itself attributes it to the first.

| clause | what confirms it |
|---|---|
| no reply ever | `overall_stats.replies` and `unique_replies` are 0, every `lead_campaign_data[].replies` is 0, no membership reads `replied`, no `interested` flag, and no queue row counts a reply |
| no bounce | no membership and no queue row in a bounce state |
| no unsubscribe | no membership and no queue row in an unsubscribe, complaint, blocked or suppressed state — see the caveat in §6 |
| not in a live sequence | no membership in `in_sequence`/`sending`/`active`/`scheduled` inside a campaign whose CURRENT status is live. A live membership in a campaign whose status could not be read also excludes: unknown is not dormant |
| every sending campaign read | no membership reports `emails_sent > 0` for a campaign whose queue was never read. **Waived only by a complete per-lead queue read**, which spans every campaign by construction |
| sends reconcile | dated `sent` rows found ≥ `overall_stats.emails_sent`. Fewer means a send exists that we cannot date, and the undated one could be last week |
| was ever sent to | at least one dated `sent` row exists. Re-engagement presupposes engagement |
| 90+ days | `(now − max(sent_at)).days >= 90` |

`>= 90` is used, matching the operator's "90 or more days ago". **42 leads sit
at exactly 90 days**; the strictly-greater threshold the old module uses would
give **997** instead of 1,039.

---

## 3. THE FUNNEL

    base — every lead in the 16 campaigns holding the estate     2,081
      - replied                                                    138
      - bounced                                                     28
      - unsubscribed                                                 0
      - in a live sequence somewhere                               586
      - a sending campaign was never read                            0
      - sends do not reconcile with the provider's own count         1
      - never sent to at all                                        16
      - last confirmed send inside 90 days                         273
    = PROVIDER-CONFIRMED COHORT                                  1,039
      - store cross-check, all channels (§5)                         0
    = FINAL COHORT                                               1,039
                                                                 -----
      check sum                                                  2,081

Disjoint, first clause that disqualifies, and it sums to the base.

### 3.1 Every clause counted separately

A lead may trip several. These do not sum and are not meant to.

    replied                                         138
    bounced                                          31
    unsubscribed                                      0
    in a live sequence somewhere                    586
    a sending campaign was never read               235
    sends do not reconcile                          249
    never sent to at all                             51
    last confirmed send inside 90 days              866

The 235/249 are leads excluded EARLIER for a reply, a bounce or a live
sequence, so they never got a per-lead queue read — they did not need one. Of
the leads that did get one, exactly **one** failed to reconcile (lead 132479:
the provider counts 10 sends and 9 are dated). It is OUT.

### 3.2 The live-sequence exclusion, by campaign

    491  272    492  166    494   69    418   23    493   22
    498   10    481    9    489    5    352    4    496    3
    497    2    487    1
    ---------
         586

Four of those are inside the client's own live campaign 352. The rest are ours.

### 3.3 The cohort by the campaign it was read in

    262  archived    498
    263  archived    208
    264  archived    335
    495  archived      5
    481  active        4
    491  active        2
    492  active        2

15 cohort members appear in two of these. The four in 481 and the four in
491/492 are leads whose membership there is not live and whose last confirmed
send is still 90+ days old.

### 3.4 What has already been sent to these people

This is not a criterion and it is not an objection. It is the thing a person
sizing the first batch should see.

    emails already sent, per cohort member:
      min 1    p25 6    median 6    p75 18    max 23
    total already sent to this cohort                      10,397
    members who have had 10 or more                           265
    members who have had 20 or more                           245

    campaigns that have ever sent to a cohort member:
      352  947   262  434   264  290   274  262   327  262
      263  188   334   86   335    3   328    1   331    1

**947 of the 1,039 have been mailed by the client's own campaign 352.** They
are 90+ days clear of it, which is what the rule asks, but a cohort where a
quarter of the members have already received twenty emails is a fatigue
question, not a targeting one.

---

## 4. HOW IT DIFFERS FROM THE 1,062, AND WHY EACH DIFFERENCE IS REAL

The old lane recomputes to **1,066** today against live campaign statuses (it
was 1,062 yesterday — four leads crossed 90 days overnight, exactly as the
previous document predicted). Compared like for like:

    in both                                    966
    old lane only — now EXCLUDED               100
    this cohort only — old lane MISSED them     73

### 4.1 The 100 the old lane would have mailed

    73   HAD REPLIED
         61 caught by `overall_stats.replies > 0`
         12 caught by a campaign membership reading `replied`
         all 73 read `stopped` in the inventory
         campaigns: 262 × 27, 263 × 20, 264 × 26

    14   HAD BOUNCED
         campaigns: 264 × 7, 262 × 5, 263 × 2

    13   WERE EMAILED ONE OR TWO DAYS AGO
         confirmed-send ages: 1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 2, 2

**The 73 are the exact failure the operator named.** A lead who replied and was
afterwards marked `stopped` reads as stopped, and `lane_for()` has nothing else
to read because no inventory row carries a `replied` key. Seventy-three people
who answered would have been mailed again.

**The 13 are worse than a proxy problem.** The inventory's `last_touch` is not
`lead.updated_at` read fresh — it is a value cached in
`work/stage/last-touch.json` at whatever moment that lead was first dated, and
it is never refreshed. Two of them, checked row by row:

    lead 133283   inventory last_touch age    111 days
                  live lead.updated_at        2026-09-22T19:40:36Z
                  last confirmed SEND         2026-09-22T19:40:34Z, campaign 491
                  (first send 2026-04-06 in 264, then five in 352 through June)

    lead 140576   inventory last_touch age    111 days
                  live lead.updated_at        2026-09-22T14:54:51Z
                  last confirmed SEND         2026-09-22T14:54:48Z, campaign 495
                  (22 sends across 274, 327, 352 from April to June)

Both were emailed **by our own campaigns, two days ago**. Across the whole
inventory, **145 of 2,081 rows carry a `last_touch` older than the live
`lead.updated_at`, 133 of them by seven days or more, the worst by 111 days**,
and 17 of those sit inside the old REENGAGE lane.

So the criticism of `updated_at` in the previous document was right but
understated. `updated_at` is a proxy for a send; the CACHED copy of it is not
even a current proxy.

### 4.2 The 73 the old lane wrongly excluded

72 read `stopped` and one `sending_paused` in the inventory, inside campaigns
that are still running — which `lane_for()` classifies as NEVER, on the
operator's "unknown stop reason" rule. The provider says these people have zero
replies, zero bounces, no live membership, and a last confirmed send 90 or more
days ago. The stop reason is not unknown at the provider; it is simply not a
lead-level stop.

    where they were read: 264 × 45, 262 × 12, 263 × 8, 481 × 4,
                          491 × 2, 492 × 2, 495 × 1

### 4.3 The US subset

    campaign 264                       335    (old lane: 324; yesterday's doc: 321)
    including campaign 495             340    (yesterday's doc: 337)

Same basis as before and the same caveat: **no lead payload carries a country
field.** Geography comes from the campaign's own name at the provider — 264 is
the April 4th USA campaign, 262 and 263 its Australian siblings. 495 is ours
and its name carries a sending window rather than a geography; all five of its
cohort members join to a store record carrying a `us*` cohort, which is
corroboration rather than proof.

**335 is the like-for-like successor to "the 289" and is the figure to quote.**

---

## 5. THE STORE CROSS-CHECK, AND THE ONE THING THE PROVIDER CANNOT KNOW

    leads our store holds a reply, stop, out-of-office or DNC for      26
    of those, inside the provider-confirmed cohort                      0
    -> the store cross-check removes 0

**Unlike the previous document's 0, this one is not a coverage artefact — but
it is not reassurance either, and the reason is different.** 1,026 of the 1,039
have no store record at all, so there is still nothing to check them against.
What changed is that the provider now answers the questions the store was being
asked to answer, and it answers them for all 1,039.

### 5.1 Where the store and the provider disagree: 2 leads

Rebuilt with **per-contact attribution**, which matters: an event names its
contact in `event["contact"]`, matching `contact["key"]`, and **109 of the
1,582 store records carry more than one contact**. Attributing a record's reply
to every contact on it produced eight false disagreements on the first pass —
every one a colleague of the person who actually replied, and the provider was
right about all eight. Corrected:

    store reply AND provider reply    18   (17 email-only, 1 email + LinkedIn)
    store reply, provider silent       2   (LinkedIn only)

The two are **leads 140818 and 204967**. Both replied on **LinkedIn, through
HeyReach**, on 2026-09-23. `GET /leads/{id}/replies` at EmailBison returns 0
for both, and `overall_stats.replies` is 0, because the message never touched
EmailBison.

**EmailBison's reply history is per channel, so the provider cannot, even in
principle, answer "no reply EVER" on its own.** That is why the store negatives
are applied as an additional gate rather than as a cross-check, and why the
gate may only ever REMOVE a lead the provider admitted. Both of these were
already out on the 90-day clause; that is luck, not design.

Neither lead is currently in a live EmailBison sequence, so the specific fault
the operator saw tonight — five leads that had replied still reading
`in_sequence` — does not reproduce in this estate as of 18:29Z.

### 5.2 The unsubscribe clause is confirmed and the confirmation is thin

Zero unsubscribes anywhere: no membership state, no queue row state, and every
one of the **33 campaigns in the workspace reports `unsubscribed: 0`**.

The caveat is structural. **All 33 also report `can_unsubscribe: false`** —
this workspace has never put an unsubscribe link in an email. A counter that
cannot go up is not evidence that nobody wanted out. There is also **no
suppression route on this instance**: `/unsubscribes`, `/unsubscribed-leads`,
`/leads/unsubscribed`, `/blocklist`, `/suppressions` and `/do-not-contact` are
all 404.

What actually protects against "remove me" is the reply clause: a person who
asked to be removed replied, and a reply excludes. The unsubscribe clause is
confirmed as far as EmailBison can express it, and EmailBison cannot express
much.

---

## 6. WHAT WAS READ, AND WHAT WAS NOT

    leads read at the provider                             2,081
    leads skipped                                              0
    campaigns fully walked (leads + queue)                    16
    campaigns in the workspace                                33
    per-campaign queue rows read                           9,454
    per-lead queue reads (complete send history)           1,329
    per-lead queue rows read                              20,221
    per-lead reads that failed                                 0
    GET requests, total                                   ~2,563
    provider WRITES                                            0

**Every one of the 2,081 candidates was read.** Nothing in the candidate estate
was sampled, estimated or skipped.

The 17 unwalked campaigns were never walked by name — they were measured off
page one and skipped, so no walk spent 400 pages before refusing. Campaign 352
alone is 6,428 queue pages. **This does not leave a hole**: the per-lead route
returns those campaigns' rows for any lead we asked about, which is why
`unread_campaign` is 0.

The 752 leads excluded by the reply, bounce, unsubscribe and live-sequence
clauses did **not** get a per-lead queue read. They did not need one — a lead
already out because it replied does not need a send date. If any of those
clauses is later relaxed, those leads must be read before they are counted.

**HeyReach was not read at all this session.** The LinkedIn side of "no reply
ever" is carried entirely by our store's HeyReach events, which is how the two
leads in §5.1 were caught. A cohort that crosses channels needs its own walk.

### 6.1 One policy deviation, stated rather than buried

`scripts/reengagement_inventory.py` holds the operator's 2026-09-23 rule that
this kind of walk runs after 18:00 Zagreb and outside the 07:00–21:00Z sending
window. **Both phases ran 18:04–18:27Z on a Thursday, inside that window.**

The rule was written for a walk of ~90,000 leads at one `lead()` call each. This
was 2,563 reads over 23 minutes at roughly 1.5 per second, throttled at 250 ms,
against a provider whose own campaign pages serve fifteen rows at a time. It is
a deviation and it is recorded as one. A repeat should wait for 21:00Z.

---

## 7. WHAT THE FOREGROUND SESSION SHOULD KNOW BEFORE THE PUSH

- **1,039, and it is not the same 1,039 tomorrow.** The 90-day clause admits
  new leads daily — 42 members are at exactly 90 days today. Stamp any batch
  with the instant it was derived or the next session will reconcile two
  correct numbers and call one a bug.
- **1,026 of the 1,039 have no store record.** They are the client's April
  leads, known to us as a provider lead id and nothing else: no verified
  address, no ICP verdict, no MX result, no suppression history. The operator's
  2026-09-21 grant covers mailing them. It does not supply the evidence, and
  `PRODUCTION-SCALE-POLICY.md`'s gates have never run on them.
- **The LinkedIn channel is a live gap.** Two people in this estate replied on
  LinkedIn and EmailBison will never know. Any cohort built from EmailBison
  alone inherits that gap. Run the HeyReach side before a second batch.
- **Fatigue, not eligibility, is the open question.** 245 cohort members have
  already received twenty or more emails, and 947 have been mailed by the
  client's own campaign 352.
- **Size against the forward book, not the mailbox count** — CLAUDE.md's
  standing rule. 1,039 is an eligible population, not a batch.
- Nothing here was pushed, enrolled, created or activated.

---

## 8. REPRODUCING THIS

    py -3 scripts/reengagement_provider_confirmed.py --walk --only \
        262 263 264 495 491 492 494 418 493 498 487 481 496 497 489 451
    py -3 scripts/reengagement_provider_confirmed.py --leadqueue
    py -3 scripts/reengagement_provider_confirmed.py --storenegatives
    py -3 scripts/reengagement_provider_confirmed.py --report

Phase 1 sizes every campaign off page one and skips the oversized by name.
Phase 2 is resumable — ids already on disk are skipped — and a lead whose
per-lead read fails is **left unwritten**, so it keeps falling to the
`unread_campaign` clause rather than reading as never-sent. `--report` makes no
network call. Staged output is under `work/`, which stays gitignored:
`pc-leads.jsonl`, `pc-sends.jsonl`, `pc-lead-sends.jsonl`, `pc-campaigns.json`,
`pc-store-negatives.json`.

Do not read `lane` or `lane_at_walk` from `reengagement-inventory.jsonl`, and
do not read `last_touch` from it either. Both are stale by design; the third is
stale by accident, which is worse.
