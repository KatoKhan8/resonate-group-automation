# Merge request — the re-engagement cohort, 2026-09-25

Lane I, own worktree, own branch. **READ-ONLY at both providers.** Every
EmailBison call was a `GET`; every HeyReach call went through
`heyreach._read`, which refuses any path off `READ_ROUTES_ALL`. Nothing was
created, enrolled, activated, paused, stopped or written. No paid call was
made and the spend ledger is untouched.

    branch      worktree-agent-a665dface2ba16da0
    HEAD        d043671d  (plus this document)
    base        24acafff  "The handoff carried the test identity slug"

**Counts, provider ids, campaign ids and timestamps only.** No prospect name,
address, company name, domain or LinkedIn URL appears in this document. The
per-lead lists live in `work/stage/ri-*.json`, which stays gitignored.

**Every load-bearing number below was re-derived from the staged files and
checked against the text: 58 claims, 58 agree, 0 disagree.** That check found
one real defect — the staged funnel omitted the LinkedIn gate's 9 and summed
to 2,122 against a base of 2,131, while the printed report was right. Fixed,
and the check is why this document does not carry it.

---

## 0. THE NUMBER I WOULD PUSH TODAY IS ZERO, AND THE COHORT IS 1,031

    PROVIDER-CONFIRMED COHORT, 2026-09-25T08:44Z            1,031
      on distinct accounts                                    762
      US subset (campaign 264)                                335 on 162 accounts
      AU subset (campaigns 262 + 263)                         694 on 600 accounts
      read in 481                                               4

    of those, carrying a research pack fact today                0
    of those, whose account has a colleague mid-sequence
      in a campaign running right now                           257 on 89 accounts
    of those, whose account appears at all in a live campaign   956 on 696 accounts
    of those, whose address has ever been verified               0

**1,031 is an eligible population. It is not a batch, and today it is not a
push.** §8 says what has to be true first and who owns each item. What I am
holding, and why, is in §9.

---

## 1. WHAT THIS ADDS TO THE 2026-09-24 WORK, AND WHY IT WAS NEEDED

`docs/REENGAGEMENT-COHORT-PROVIDER-CONFIRMED-2026-09-24.md` did the hard
part: it found the two EmailBison routes that answer "no reply EVER" and
"when was this person last actually SENT to", and it caught the 73 that the
membership-state lane would have mailed after they had replied. This lane
did not redo that. It closed the three holes that document names in its own
§6 and §7, all three of which are load-bearing for a push:

| hole, in its words | what this lane did |
|---|---|
| *"HeyReach was not read at all this session"* | read it. §5 |
| *"1,026 of the 1,039 have no store record"* | measured what that costs. §5, §6 |
| *"it is not the same 1,039 tomorrow"* | re-read every clause at today's clock from a fresh provider read. §2, §3 |

And one the document could not have known about, because it is a property of
re-running it rather than of what it found:

**RECOMPUTING THE FROZEN SNAPSHOT AT A LATER CLOCK IS WRONG IN THE UNSAFE
DIRECTION, BY CONSTRUCTION.** `--report` takes `now` from the system clock
and the send dates from a file written at 2026-09-24T18:27Z. Age only ever
grows, so re-running it only ever ADMITS leads and can never eject one. A
lead mailed at 19:00 last night still reads as 90+ days clear. Running it
this morning gives **1,040** and every one of those numbers is derived from
last night's evidence.

That is not hypothetical here. Between the snapshot and this morning's read,
**five campaigns sent mail**: the client's 327 (+64), 328 (+26) and **352
(+19)**, and our own 489 (+1) and 491 (+1). 352 alone has dated sends to 939 of
this cohort. Three campaigns also changed status under us: 495 archived → paused,
497 and 498 active → completed, and three new campaigns appeared (500, 501,
502). Every one of those moves a clause.

---

## 2. WHAT WAS READ TODAY, AND WHEN

    EmailBison, all campaign counters + statuses    2026-09-25T08:30:06Z
    EmailBison, all 16 estate campaigns' leads      2026-09-25T08:30-08:31Z
    EmailBison, complete per-lead send history      2026-09-25T08:31-08:43Z
    HeyReach, campaign list + per-campaign stats    2026-09-25T08:46-08:47Z
    HeyReach, per-lead campaign membership          2026-09-25T08:47Z
    EmailBison, live campaigns 327/328/501 (offset)    2026-09-25T08:45-09:05Z
    EmailBison, live campaign 352 (CURSOR)             2026-09-25T09:08-09:28Z

    leads re-read at the provider                            2,131
    leads skipped                                                0
    per-lead queue reads issued                              1,392
    per-lead reads that FAILED                                   0
    per-lead queue rows read                                20,847
    HeyReach campaigns whose stats were read                    37
    HeyReach per-lead reads                                     13
    live-campaign leads read (327/328/352/501)              42,454
    EmailBison GET requests                                 ~5,079
    HeyReach read-route POSTs                                   53
    PROVIDER WRITES                                              0
    PAID CALLS                                                   0

`spendledger.caps({productive})` reads `per_run` 2,000, `per_day` 5,000,
`per_provider_per_day` none, `total` 50,000; committed today **0** and
**4,444 of 50,000** in total. Nothing in this lane touched it, and no ceiling
was changed.

### 2.1 The same policy deviation as last night, recorded again

`scripts/reengagement_inventory.py` carries the operator's 2026-09-23 rule
that a walk of this kind runs after 18:00 Zagreb and outside the
07:00–21:00Z sending window. **This ran 08:30–09:29Z on a Friday, inside that
window, and it was ~5,079 requests rather than last night's 2,563.** It is
the second consecutive deviation, it is larger than the first, and it should
stop being routine.

The mitigation used: a 0.25 s throttle throughout, roughly two requests a
second, and the per-lead route in preference to a per-campaign walk wherever
one would do. **The live-campaign walk is 2,833 of those 5,079** and it is
the part to move to after 21:00Z if it is repeated — it is also the part
that produced §7.2 and §7.3, so it earned its cost once. It should not be
run again this week.

---

## 3. THE FUNNEL, WITH EVERY DENOMINATOR NAMED

Disjoint. First clause that disqualifies. It sums to the base.

    base — every lead in the 16 campaigns holding the candidate
           estate, re-read at the provider 2026-09-25T08:30Z       2,131
      - replied                                                      138
      - bounced                                                       28
      - unsubscribed                                                   0
      - in a live sequence somewhere                                 573
      - a sending campaign was never read                              0
      - sends do not reconcile with the provider's own count           1
      - never sent to at all                                          32
      - last confirmed send inside 90 days                           319
      - a campaign moved since the read that dated this lead           0
      - the operator's test identity                                   0
      - our store holds a reply, stop, out-of-office or DNC            0
      - the provider lead carries no address                           0
    = COHORT, EmailBison clauses only                              1,040
      - THE LINKEDIN GATE (HeyReach)                                   9
    = FINAL COHORT                                                 1,031
                                                                   -----
      check sum                                                    2,131

**The base is 2,131, not 2,081.** Exactly fifty leads entered the estate
campaigns between the two reads and none left:

    496   9 -> 43   (+34)     497   7 -> 20   (+13)
    498  13 -> 15   (+2)      491 332 -> 333  (+1)

The three archived April campaigns (262, 263, 264) are unchanged at 591, 329
and 403. Quoting 2,081 today would be quoting last night's denominator. All
fifty are excluded: 33 `too_recent`, 16 `never_sent`, 1 `live_sequence` —
they are the leads attached to 496/497/498 last night, and a lead attached
last night is the opposite of a re-engagement candidate.

### 3.1 The cohort by the campaign it was read in

    262  archived   499   PRODUCTIVE - MARKETING AGENCY - AUSTRALIA - APRIL
    263  archived   208   v2 PRODUCTIVE - MARKETING AGENCY - AUSTRALIA - APRIL
    264  archived   335   PRODUCTIVE - MARKETING AGENCY - USA - APRIL 4TH
    481  active       4   RESONATE - PRODUCTIVE - EMAIL - ZAGREB-HOURS - BUYER
    ---------------------
               1,046 memberships over 1,031 leads (15 appear in two)

**No cohort member is now read in 491, 492 or 495.** Yesterday's cohort had
nine there; all nine are the leads the LinkedIn gate removed (§5.3), which is
a coincidence of who our store happens to know rather than a pattern.

**Geography comes from the campaign's name at the provider, not from the lead** —
no lead payload carries a country field. 264 is the April USA campaign, 262
and 263 its Australian siblings. That gives **335 US on 162 accounts** and
**694 AU on 600 accounts**, and it is the like-for-like successor to "the
289" and to yesterday's 335.

### 3.2 THE SEVENTY-THREE REPRODUCE EXACTLY, from today's read

The whole reason this lane exists is commit `7a68505d` / `62efb2f6`,
*"Seventy-three of the re-engagement cohort had already replied"*. That was
measured against last night's staged files. Against today's independent
provider read, compared with the membership-derived lane's own 1,066:

    the old membership-derived REENGAGE lane                  1,066
      also in today's provider-confirmed cohort                 962
      the old lane would have mailed, TODAY EXCLUDES            104
          73  HAD REPLIED
          14  HAD BOUNCED
          13  were mailed inside 90 days
           4  are in a live LinkedIn sequence right now
      in today's cohort, the old lane MISSED                    69

**73, and 14, to the lead.** Not an approximation of last night's figure —
the same number from different bytes, fourteen hours later. The failure the
operator named is real, it is stable, and a lane that reads one membership
state string still reproduces it today.

The 4 at the bottom of that list are new: leads the old lane would have
mailed, that EmailBison also calls clean, and that are being worked on
LinkedIn this morning. Nothing before this lane could see them.

### 3.3 The three denominators that are NOT the same question

1. **2,131 is what was read, not what exists.** 16 of the workspace's 36
   campaigns were walked. The other 20 report 54,923 leads between them —
   a figure from the same `total_leads` field that is wrong on two campaigns
   (§7.4), so treat it as an order of magnitude. This lane claims nothing
   about them: a lead that lives only in the client's 274 or 331 is not in
   the base and is not in the cohort.
2. **1,040 is the EmailBison answer, and EmailBison cannot answer the
   question.** Its reply history is per channel. §5.
3. **1,031 is what survives both providers. It is still not "pushable".**
   §6 (evidence) and §7 (accounts) each cut it further, and neither cut has
   been applied to the number above, deliberately — they are different
   questions and folding them in would hide which one bit.

### 3.4 Every clause counted separately

A lead may trip several; these do not sum.

    replied                                         138
    bounced                                          31
    unsubscribed                                      0
    in a live sequence somewhere                    573
    a sending campaign was never read               222
    sends do not reconcile                          729
    never sent to at all                            771
    last confirmed send inside 90 days              319
    a campaign moved since this lead was dated      478
    the operator's test identity                      3
    our store holds a negative                       26

**Two of these are not comparable with last night's table and it matters.**
`sends do not reconcile` (729) and `never sent to at all` (771) are inflated
because 739 leads were excluded by a cheap clause and therefore never got a
per-lead queue read — with no rows to reconcile against, both clauses fire
trivially. Of the **1,392 leads that DID get a complete per-lead read,
exactly one failed to reconcile** (lead 132479: the provider counts 10 sends
and 9 are dated). It is OUT. That "one" is the number to quote, not 729.

The same caveat applies to `a campaign moved` (478): it can only fire on a
lead with no fresh queue read, and every one of those 478 was already out on
an earlier clause. Its funnel contribution is 0 and that is correct, not an
oversight — the clause exists so that a future run which reuses a stale
send file cannot pass a lead that a moved campaign might have mailed.

### 3.5 The exclusions, with the provider's own words

Every excluded lead is written to `work/stage/ri-cohort.json` under
`excluded`, carrying its clause, the provider's own phrasing, every other
clause it also trips, whether it got a per-lead queue read, and the instant
of the read that says so. **1,100 exclusion rows, none of them derived from
our store's opinion of who replied.**

| class | n | the evidence, verbatim from the run |
|---|---|---|
| replied | 138 | 108 `overall_stats.replies > 0`; 30 `campaign <id> reads replied` / counts a reply |
| bounced | 28 | e.g. `campaign 352 reads bounced` (9), `campaign 262 reads bounced` (6), `campaign 274` (3), `campaign 264` (3), then 327/328/334/418/491/492/495 one each |
| unsubscribed | 0 | see §4 — this is a confirmed zero that proves very little |
| live sequence | 573 | 491×273, 492×166, 494×69, 418×23, 493×22, 481×9, 489×5, **352×4**, 487×1, 496×1 |
| sends do not reconcile | 1 | lead 132479: `provider counts 10 sends and 9 are dated` |
| never sent to | 32 | `no dated sent row exists anywhere` — re-engagement presupposes engagement |
| last send inside 90d | 319 | ages 0–89 days. **134 of them were mailed within the last 7 days and 131 within the last 3** |
| LinkedIn gate | 9 | §5 |

**Those 131 are the whole argument for reading the provider.** They are
people our campaigns and the client's mailed this week. A cohort derived
from a cached last-touch field would have put them in a re-engagement
campaign, and the 2026-09-24 handoff measured that field reading 111 days
stale on a lead sent two days earlier.

### 3.6 Both directions were checked against routes the build never used

The cohort was built from `GET /campaigns/{id}/leads` and
`GET /leads/{id}/scheduled-emails`. The check used `GET /leads/{id}` and
`GET /leads/{id}/replies`, neither of which the build reads.

**14 cohort members, including the youngest (90d) and the oldest (173d):
0 replies, 0 unique replies, no live membership, and dated sends equal to
`overall_stats.emails_sent` exactly. 14 of 14 agree.**

**25 exclusions across all 7 classes: 0 unreadable, every reason confirmed on
the independent route.** Four of the `replied` sample are the 73-shape again,
visible in one line each — lead 132936 reads `stopped` in campaign 263 and
`replied` in 352; 132913 reads `stopped` in 263 and `replied` in 328. A lane
reading the April campaign's membership string alone would mail both.

### 3.7 `GET /leads/{id}/replies` IS NOT A REPLY FEED, and the 2026-09-24 document leans on it

The exclusion check turned up a bounced lead whose `/replies` total was 1
while `overall_stats.replies` was 0. Measured properly:

    group      n     route total == overall_stats.replies   route HIGHER   route LOWER
    replied    30                    12                          3            15
    bounced    28                     0                         28             0
    cohort     30                    30                          0             0

    row `type` values the route actually returns:
      on repliers   Tracked Reply 9, Outgoing Email 3, Bounced 1
      on bounces    Bounced 30

**It returns bounces and our own outgoing mail as rows.** Reading its total as
a reply count turns every one of the 28 bounced leads into a replier, and it
*also* under-reports: for 15 of 30 leads the provider counts a reply for, the
route returned fewer rows than `overall_stats.replies`.

`docs/REENGAGEMENT-COHORT-PROVIDER-CONFIRMED-2026-09-24.md` §1 validated this
route against **two** leads — *"route totals 1 and 2"* against
`overall_stats.replies` of 1 and 1, which is a disagreement presented as a
validation — and §5 used it to settle the store disagreements. That
conclusion should be re-derived from `overall_stats` before it is relied on
again.

**This does not move today's cohort.** This lane never used that route as a
witness: the reply clause reads `overall_stats.replies`, `unique_replies`,
every `lead_campaign_data[].replies`, the `interested` flag and the queue
rows' own reply counts. The 30 cohort members sampled return 0 on both. The
finding is a correction to the earlier lane's evidence, not to this cohort.

### 3.8 The test identity

`src/testidentity.py` names leads **204966 and 204967**. The lane briefing
also names **205079 and 205081**. I treated all four as excluded — a lead id
that might be the operator is excluded and the discrepancy reported rather
than resolved by me. Where each actually lands:

    204966   never_sent     (no dated sent row anywhere)
    204967   never_sent     (no dated sent row anywhere)
    205079   live_sequence  (in_sequence in live campaign 491)
    205081   not present in the estate read at all

So the test-identity clause contributes 0 to the funnel — not because it was
skipped, but because all four are already out on a provider fact. **Please
reconcile `testidentity.LEAD_IDS` with the briefing.** If 205079 and 205081
are genuinely the operator, the module is missing two ids and every other
consumer of that module is missing them too.

---

## 4. THE UNSUBSCRIBE ZERO IS CONFIRMED AND IT IS NOT REASSURANCE

Unchanged from 2026-09-24 and re-read today: no membership state, no queue
row state, and every campaign in the workspace reports `unsubscribed: 0`.
**And every one also reports `can_unsubscribe: false`** — this workspace has
never put an unsubscribe link in an email, and there is no suppression route
on the instance (`/unsubscribes`, `/suppressions`, `/blocklist`,
`/do-not-contact` all 404).

A counter that cannot go up is not evidence that nobody wanted out. What
actually protects against "remove me" is the reply clause. That makes the
unsubscribe-classification work in
`.claude/worktrees/agent-a229ee3cba3357ce9` (handoff §3.2 — 14 English-only
patterns, no bare "stop", against nineteen countries) a **dependency of this
cohort**, not an unrelated task.

---

## 5. THE LINKEDIN SIDE: NINE REMOVED, AND 1,027 UNANSWERABLE

HeyReach was read for the first time against this cohort.

### 5.1 Ownership was asked of the provider, not of a literal

`inbound.OWNED_CAMPAIGNS` is four **HeyReach** ids that `_positively_not_ours`
compares against EmailBison event ids without asking which provider they came
from. That logic was not reused. Instead: `docs/state/PROVIDER-CAMPAIGNS.json`
for which campaigns the provider says we created, and a fresh
`/campaign/GetAll` for what exists now.

    the ownership readback is dated 2026-09-23T10:02Z — 47 HOURS OLD
    and `inbound._owned` would REFUSE to license a drop on it

    campaigns in the HeyReach workspace, right now              120
      the readback says are ours                                 37
      not ours, or unclassified                                  83
      of those, IN_PROGRESS right now                            13

I did **not** run `scripts/provider_truth.py` to refresh that readback: the
2026-09-24 handoff §6 item 1 forbids it until the per-provider resolution
lands, because running it arms a silent drop of our own EmailBison replies.
So **ownership in this document rests on a 47-hour-old readback** and that is
a stated limit, not a hidden one.

### 5.2 Our own LinkedIn campaigns have now taken two replies

Read per CAMPAIGN, which is the unit of ownership — a seat total would carry
the client's traffic, and the workspace inbox is 26,973 conversations of
which the client's own is nearly all.

    across the 37 campaigns the readback says are ours:
      connections sent                     137
      connections accepted                   6
      unique leads contacted               139
      TOTAL MESSAGE REPLIES                  2

REFUTED-006 recorded **0 replies** on 2026-09-23. It is 2 now. Those are
almost certainly the two real unmatched replies on 613744 that the
notifications repair found buried in 103 posts. **They are not cohort
members** — §5.3 — but they are the first LinkedIn replies this estate has
taken, and the drop hazard in `inbound` is no longer purely latent.

### 5.3 The join, and the size of the hole

    cohort leads                                            1,040
    joined to a store contact by bison_lead_id                 13
      of those, carrying a LinkedIn URL                        13
      of those, carrying a heyreach_lead_id                     0
    STRUCTURALLY UNANSWERABLE on LinkedIn                   1,027

**Exactly one contact in the entire 1,065-contact store carries a
`heyreach_lead_id`, and it is not in this cohort.** The briefing's ISSUE-041
says zero; the measured number is one. Either way the conclusion is the same
and it is the one that matters:

> For 1,027 of these people, "no LinkedIn reply recorded" is not evidence
> that nobody replied. It is evidence that nothing could ever have recorded
> one. There is no identity to ask HeyReach about — no LinkedIn URL, no
> name, no store record, nothing but an EmailBison lead id.

Of the 13 that could be asked, the provider placed 8 in a LinkedIn campaign,
answered 404 for 1, and reported **0 replies**:

    removed by the LinkedIn gate                                9
      in a LIVE LinkedIn sequence right now                     8
        of those, live in a campaign WE own                     5
      HeyReach returned 404 and could not answer                1

**Eight of the leads EmailBison called clean are being worked on LinkedIn
today, five of them by us.** That is the "currently in a live sequence
anywhere" clause, and EmailBison cannot see it. The gate is applied the same
way the store-negatives gate is: it may only ever REMOVE a lead the provider
admitted, never add one, and unreadable removes as well — a 404 is not a
statement that this person is in no LinkedIn campaign.

### 5.4 One correction I made to my own run

The first version of the LinkedIn script printed **"leads reading REPLIED on
LinkedIn: 1"**. It was the 404. The exception handler appended the lead to
the same list the reply count was taken from, so an unreadable lead was
reported under a reason the provider never gave. Fixed in `a4b08359`:
unreadable excludes, fail-closed, **under its own name**. The true LinkedIn
reply count among the 13 is **0**.

The first run also reported **"0 of 1,040 join a store contact"**. That was
a path fault, not a finding: the script ran in a worktree, `store.queue_path()`
resolved to that worktree's own `work/queue.jsonl`, which does not exist, and
an absent file read as a store holding nobody. The real answer is 13.
`_store_contacts` now refuses on an empty store rather than reporting the
empty join as an answer.

---

## 6. PACK COVERAGE: ZERO, AND THE FREE CRAWL WOULD TAKE ABOUT HALF AN HOUR

Stated separately from eligibility, as asked.

    cohort accounts                                             762
    carrying a research pack fact today                           0
    carrying any company fact in our store at all                27
    carrying NOTHING                                            735

That first zero is not a near miss. Every servable pack cache on disk —
`research-pack-cache.json`, `researchpack-cohort-uk-eu-cache.json`,
`researchpack-cohort-sitegap-cache.json` — carries facts for **197 domains
between them, and not one of them is a cohort account.** The packs that exist
were built for the UK/EU batch-1 cohort. This cohort is the client's April
lists and nothing has ever been researched about it.

(The pilot cache adds 46 more domains but is named
`researchpack-pilot-cache.PRE-FIX-DO-NOT-SERVE.json` and is not counted.)

### 6.1 What the free crawl would cost, from the run that actually happened

Lane C's site-content crawl on 2026-09-24T22:47Z, measured rather than
estimated:

    accounts selected                       153
    site_content addressable                116
    site_content COVERED                    116   =  100% of addressable
                                                  =   75.8% of all 153
    site requests                           277
    site seconds                          334.2
    observed USD                          0.000
    ledger credits charged                    0

**Note the two denominators in that run's own summary: `of_addressable` 1.0
and `of_all` 0.758.** The crawl covered 116 of 153, not 153 of 153. Quoting
100% would be the recurring mistake.

Projected onto 762 accounts at the same measured rate (2.18 s/account):

    wall clock            ~28 minutes        (762 x 2.18s = 1,661s)
    expected coverage     ~578 accounts      (762 x 0.758)
    expected misses       ~184 accounts      JS_RENDERING_REQUIRED, BLOCKED,
                                             NON_2XX, TIMEOUT, HTTP_INSUFFICIENT
    cost                  $0.00 and 0 ledger credits

**Yes, this cohort needs one, and it should run before any copy is written
for it.** Twenty-eight minutes and no money against 735 accounts we currently
know nothing about is the cheapest thing on this page. No Apify call is
wanted or needed: the operator has already ruled that site content comes
from our own free crawler.

### 6.2 BUT IT CANNOT BE AIMED AT THIS COHORT YET, AND THAT IS THE REAL BLOCKER

I checked before recommending it, and the recommendation does not survive
contact with the wiring.

`scripts/researchpack_cohort.py` (lane C's worktree
`agent-aea4a82ef07084898`, not on master) selects accounts in
`selection()` by reading **`work/stage/s7-copy.jsonl` for rendered copy rows
and `work/stage/s3-icp.jsonl` for the country**, then grouping by cohort
label. The underlying primitive, `research.run(rec, ...)`, takes a **record**.

**This cohort has no rendered copy, no ICP row, and — for 1,018 of its 1,031
members — no record at all.** There is nothing for either entry point to
select. Pointing the free crawl at these 762 domains needs a domain-list
entry point that does not exist today.

And that is the general shape of it, not a detail about one script:

> **Every downstream gate in this system is store-driven, and this cohort is
> not in the store.** Pack facts are keyed by a record's domain. The ICP
> verdict is a record field. Copy renders from `s7-copy.jsonl`, which is
> built from records. The account rule, the collision gate, suppression and
> DNC all read records. The cohort is 1,031 EmailBison lead ids and an email
> address each, and nothing else.

So the first thing this cohort needs is not a crawl and not copy. **It needs
to exist in `work/queue.jsonl` as 762 records carrying the domain and the
`bison_lead_id` of each contact.** That is the link between "provider-
confirmed" and every gate that would otherwise have to be bypassed — and
bypassing them is how ISSUE-019, ISSUE-023 and the 76 blank emails of
ISSUE-025 happened.

I did not create those records. Writing 762 records into the canonical
store is not a read, this lane is read-only, and the adoption path already
has a register row against it.

### 6.3 The evidence gap is wider than packs

    cohort leads whose EmailBison record reads `unverified`   1,031  (all of them)
    cohort leads on an account with a known_allowed MX          533  on 335 accounts
    cohort leads on an account never MX-checked                 484  on 420 accounts
    cohort leads on an account with a known_blocked MX            5  on 2 accounts
    cohort leads on an `unknown_provider` MX                     18  on 14 accounts

**Every lead in the estate reads `unverified` at EmailBison — all 2,130 of
them.** That is a property of this workspace (verification has never been run
here), not a per-lead finding, so it should not be read as 1,031 bad
addresses. But it does mean the provider offers no address evidence at all,
and CLAUDE.md's standing rule is *"No email is generated for an unverified
address."* The MX table above is the only deliverability evidence this cohort
has, and it covers 533 of 1,031.

---

## 7. ACCOUNTS, NOT LEADS — AND THE COLLISION DENOMINATOR THAT NEARLY FOOLED ME

    cohort leads                                              1,031
    distinct accounts (email domain)                            762
    accounts carrying more than one cohort lead                 132
    cohort leads sitting on those accounts                      401
    leads per account   1x630  2x96  3x17  4x5  5x3  6x2  7x3  8x1  9x1
                        14x2  18x1  27x1

No account resolves to a free mailbox provider, so the domain is a sound
account key here — 0 of 762 are gmail/outlook/yahoo and the like.

**401 of the 1,031 sit on an account that already has another cohort member
on it.** One account carries 27. Under the account rule as the operator
states it — same contact never twice, a second persona only after a gap, a
third after a further gap — a naive push of 1,031 would put up to 27 people
at one company into the same campaign on the same day. The account rule and
the collision gate are lane G's and are not merged; **this cohort must not be
pushed before they are, and the 132 accounts are the reason.**

### 7.1 940 of the 1,031 are ALREADY LEADS IN A CAMPAIGN THAT IS RUNNING RIGHT NOW

This is not the account question and it is not a clause violation. It is the
one number on this page I would want a person to look at before approving a
push, and no stage of the funnel asks it.

    cohort members holding a membership in a CURRENTLY-LIVE campaign   940 of 1,031
      their membership status there:  sequence_finished 1,127   stopped 70
      by campaign:   352 x 939     327 x 253     481 x 4     328 x 1

They pass clause 4 correctly — `sequence_finished` and `stopped` are not live
memberships, so nobody is mid-sequence. But 939 of them are enrolled leads
inside the client's campaign 352, which is ACTIVE, has 21,530 leads, and sent
nineteen emails between last night's snapshot and this morning's read. 253
are enrolled in 327, also active, which sent sixty-four in the same window.

**Pushing these people creates a person who is a live lead in two campaigns
at the same provider simultaneously**, one of them the client's own and not
ours to pause. ISSUE-025 is the same shape from the other end (adoption by
email carries the CLIENT's lead into our campaign) and ISSUE-014 is what
makes it hard to undo. Whether 352's scheduler can re-engage a
`sequence_finished` lead is **not something I verified**, and it is the
question that decides whether this is a footnote or a blocker.

### 7.2 The collision count over the wrong denominator is 1. Over the right one it is 89.

The first number this lane computed was **1 cohort account with a colleague
live in a current campaign**. It was computed over the 16 estate campaigns,
and it is the exact shape of the failure the handoff catalogues — 1,508
exportable that was 114, 330 selected of which 212 were spoken for. The
account rule is about a **colleague**, and a colleague at a cohort account
who sits in the client's live campaign 352 and was never in one of our 16 is
invisible to the estate read. 939 of this cohort have dated sends from 352, and
352 is running right now with 21,530 leads.

So the live campaigns outside the estate were walked — **all four of them,
completely**: 327 (10,008 leads), 328 (10,915), 352 (21,530) and 501 (1).
42,454 lead rows. 352 needed cursor pagination and §7.3 is why.

    live campaign   leads read   holding a LIVE membership   distinct domains
        327            10,008              3,462                   2,389
        328            10,915              4,917                   4,493
        352            21,530                570                     557
        501                 1                  1                       1

Against that, the cohort's 762 accounts:

    cohort accounts with a colleague MID-SEQUENCE right now      89   (257 cohort leads)
      in 327                                                     81
      in 328                                                     12
      in 352                                                      5
    cohort accounts with NO actively-live colleague             673   (774 cohort leads)

    and the wider question, which is not the same one:
    cohort accounts present AT ALL in a live client campaign     696   (956 cohort leads)
    cohort accounts in no live client campaign at any status      66   ( 75 cohort leads)

**89, not 1.** Eighty-nine times the estate-only reading would have said
"clear" about an account where a colleague is being emailed today. And the
second pair is the one that should worry a person more: **696 of 762 cohort
accounts — 91% — already have somebody in a campaign the client is running
right now.** Only 66 accounts, carrying 75 cohort leads, are untouched by
live client traffic.

Note what 352 does to the two readings. It holds 21,530 leads and contributes
only 5 actively-live collisions, because 570 of its leads carry a live
membership and the rest are finished. Had it stayed unreadable, the honest
answer for it would have been UNKNOWN and every one of its accounts would
have had to be held — which is the fail-closed behaviour the first walk
correctly produced, and the reason it was worth an hour to get past it.

### 7.3 THE REASON THE BIG CAMPAIGNS WERE "TOO BIG TO WALK" HAS A NAME, AND A FIX

The first live-campaign walk refused on 352, fail-closed, with
`ProviderError` and *"the collision answer for it is UNKNOWN, never clean"*.
Rather than accept that, I asked what the error actually was. Binary-searched
against the provider:

    GET /campaigns/352/leads?page=1000   ->  200, 15 rows, last_page 1436
    GET /campaigns/352/leads?page=1001   ->  422

    {"success": false, "message": "You are requesting too many pages. Please
     use the cursor pagination type to traverse large datasets."}

**Offset pagination stops at exactly page 1,000 — 15,000 rows — on every
paginated route this repository walks.** `meta.last_page` cheerfully reports
1,436 and the provider will not serve page 1,001. Every walk in this codebase
uses `page=`, so every dataset over 15,000 rows has been unreachable, and
that is the real content of the 2026-09-24 document's *"campaign 352 alone is
6,428 queue pages… skipped by name, never attempted"*: not a choice about
cost, a limit nobody had named.

**And the provider names the fix in the refusal.** Measured:

    GET /campaigns/352/leads?pagination_type=cursor
      -> 200, meta carries next_cursor and prev_cursor (no total, no last_page)

    per_page is IGNORED on this route: 15, 50, 100, 200 and 500 all return
    fifteen rows, so a large campaign still costs total/15 requests. What
    cursor buys is REACHING them at all, not reaching them faster.

`_walk_cursor` in `scripts/reengagement_cohort_lane_i.py` implements it, and
implements the termination condition carefully, because this meta block has
no `total` to check a short read against: a repeated cursor, a non-list page
and the page cap are all **refusals**, never ends. A short read that reads as
end-of-data is exactly what `_walk`'s total check exists to prevent, and
cursor pagination takes that check away.

This is worth more than this cohort. It is the route by which the client's
own campaigns — 352 at 21,530 leads and 96,419 queue rows, 327, 328, 274 —
become readable for the first time.

### 7.4 What the campaign-level counters are worth

Two of them are demonstrably wrong and neither should be trusted as a
denominator:

    campaign 262 reports total_leads = 3 and its leads route returns 591
    campaign 327 reports total_leads = 9,676 and its leads route returns 10,008

`emails_sent` was used in this lane only as a **change detector** — "did
anything at all happen in this campaign since the snapshot" — never as a
count, and every lead the detector flagged got a fresh per-lead read anyway.

---

## 8. THE 1,031 IS STABLE ACROSS FOURTEEN HOURS, AND THAT IS A REAL RESULT

The 2026-09-24 staged files and today's fresh read are independent: different
provider reads, fourteen hours apart, different files on disk. Recomputed at
the same clock:

    2026-09-24 staged files, EmailBison clauses          1,040
    2026-09-25 fresh read,   EmailBison clauses          1,040
      in both                                            1,040
      in today's only                                        0
      in last night's only                                   0

**The sets are identical.** So the freshness risk in §1 was real — 352 did
send nineteen emails overnight — and none of them landed on a cohort member.
The check was necessary and its answer was "nothing moved". That is worth
saying plainly rather than presenting the re-read as having caught something
it did not.

What the re-read DID catch is in §5: nine leads EmailBison called clean that
the LinkedIn side does not, eight of them mid-sequence today.

---

## 9. WHAT IS PUSHABLE, WHAT I AM HOLDING, AND WHY

**Genuinely pushable today: 0. Held: all 1,031.** Not because the cohort is
unsound — it is the best-evidenced cohort this project has built, and §3.6
checked it in both directions on routes the build never used — but because
five things that gate a push are not in place, and four of them belong to
other lanes or to nobody.

The honest one-line version: *the cohort is finished and nothing downstream
of it is.*

| blocker | owner | state |
|---|---|---|
| the cadence is HALF-APPLIED: `productive.yaml` still declares em1..em3, `thread_reply_pattern` has 3 entries and needs 4, `CADENCE_STEPS` in `batch1_build.py` must match, final step `wait_in_days` must be 1 | lane B | not landed. `bisonfactory` REFUSES when provider sequence keys and cadence keys disagree, and it refuses in a place that does not name the cause |
| the account rule and the collision gate | lane G | TASK-275's tests are written and RED, not merged. 132 cohort accounts carry more than one member, one of them 27 |
| **the cohort does not exist in `work/queue.jsonl`** — 1,018 of 1,031 have no record, so every store-driven gate has nothing to read | unassigned | §6.2. This is the one I would put first, because the other three are all downstream of it |
| pack coverage is 0 of 762 accounts | free crawl, ~28 min, $0.00 | cannot be aimed at this cohort yet: both entry points select from stage files or records, and this cohort has neither. §6.2 |
| the unsubscribe reply patterns are 14 English-only strings with no bare "stop", and the unsubscribe LINK has been removed so the reply is the only opt-out | the a229ee3c worktree | nothing committed. §4 |
| 940 of 1,031 are already enrolled leads in a campaign running right now, 939 of them the client's own 352 | unassigned | §7.1. Not a clause violation and possibly not a problem; it is unverified, which is the problem |

**And one that is mine to state rather than to fix:** these 1,031 people are
the client's April lists. 1,018 of them have no record in our store at all —
no ICP verdict, no verified address, no MX result for 420 of their accounts,
no suppression history. The 2026-09-21 grant covers mailing them. It does not
supply the evidence, and `PRODUCTION-SCALE-POLICY.md`'s gates have never run
on them.

### 9.1 What I would do instead, in order

1. **Land the cohort in the store as 762 records** carrying the domain and
   each contact's `bison_lead_id`, sourced from `work/stage/ri-cohort.json`.
   Nothing else on this list can start until this does, and it is the piece
   nobody currently owns.
2. **Then run the free crawl over those 762 accounts.** 28 minutes, $0.00.
   It converts 735 accounts we know nothing about into ~578 with site
   content. Needs either the records from step 1 or a `--domains` entry
   point on `researchpack_cohort.py`; the records are the better answer
   because the ICP verdict and the account rule need them anyway.
3. **Finish the cadence, then S7, then the account rule.** Nothing about this
   cohort changes those and they gate every push, not just this one.
4. **Then a canary of 3.** The selection is already computable from
   `work/stage/ri-cohort.json`: the US subset (335 leads on 162 accounts),
   one lead per account, on a `known_allowed` MX domain, and **not** on one
   of the 89 accounts carrying a colleague mid-sequence today. Whether it
   should also avoid the 696 accounts merely PRESENT in a live campaign is
   a judgement for the operator, and it would leave 66 accounts to pick
   from. That is the operator's own
   3 → 10 → 25 → 50 progression, and this cohort has no readback history to
   justify starting anywhere higher.
5. **Size the batch against the forward book, not the mailbox count.** The
   book was walked 2026-09-24T18:03Z, is COMPLETE across 14 campaigns and
   14.8 hours old. Today it shows 1,356 sends already committed. The
   attested cap is 154 mailboxes × 15 = 2,310. **Re-walk it before sizing
   anything** — 2,310 is a ceiling and the free figure is the book's.

### 9.2 The fatigue question, which is not an eligibility question

    emails already sent to cohort members, per member:
      min 1   median 6   max 23      total 10,214
    members who have had 10 or more                256
    members who have had 20 or more                236

    last-send age: min 90d  median 111d  max 173d
    at exactly 90 days today                         3   (it was 42 yesterday)

236 of the 1,031 have already received twenty or more emails, and 939 were
mailed by the client's own campaign 352. They are 90+ days clear, which is
what the rule asks. Whether a twenty-first email is a good idea is a
different question and it is the operator's.

---

## 10. WHAT I COULD NOT VERIFY

1. **The LinkedIn channel, for 1,027 of 1,031.** No identity exists to ask
   about. This is the single largest hole in the cohort and it is
   structural, not an oversight. Closing it needs a LinkedIn URL per lead,
   which is a paid ContactOut call — not made, not in scope, and the
   operator's to authorise.
2. **HeyReach ownership rests on a 47-hour-old readback**, because refreshing
   it means running `provider_truth.py`, which the handoff forbids until
   `inbound.OWNED_CAMPAIGNS` resolves per provider.
3. **Whether `GET /leads/{id}/replies` can be repaired into a reply witness.**
   §3.7 shows what it returns; I did not work out whether filtering its rows
   by `type == "Tracked Reply"` would reconcile it with `overall_stats`. It
   was not needed here and it is needed by §5 of the 2026-09-24 document.
4. **Lead 140769.** `/campaign/GetCampaignsForLead` answered 404. Excluded
   fail-closed as unreadable, not as replied.
5. **The 20 unwalked campaigns**, reporting 54,923 leads between them —
   though §7.3 means they are now walkable, which they were not this
   morning. A lead living only there is not in the base and this document
   claims nothing about it.
6. **Whether campaign 352's scheduler can re-engage a `sequence_finished`
   lead.** 939 of the cohort are in exactly that state inside it (§7.1).
   This decides whether pushing them creates a live double-enrolment or
   merely an untidy one, and it is the highest-value unanswered question
   on this page.
7. **Whether `emails_sent` is a reliable change detector.** It was used as
   one. Two campaign-level counters in the same response are demonstrably
   wrong (§7.4), so this is an assumption, mitigated by the fact that every
   flagged lead got a fresh per-lead read regardless.
8. **`docs/DECISIONS-2026-09-25-OPTION-A-AND-THE-FREE-CRAWL.md` does not
   exist.** The lane briefing names it as required reading. Nothing matching
   it is in `docs/`. If Option A constrains this cohort, I have not read the
   constraint.
9. **ISSUE-041 through ISSUE-045 do not exist either.** The register's
   highest row is ISSUE-037. The substance the briefing attributes to
   ISSUE-041 is real and measured (§5.3), but it has no row, so it is not in
   the canonical list and the next session will not find it there.
10. **Five registrable findings from this lane have no register row**, and I
   did not add them because the register is not mine to renumber. Proposed,
   for whoever holds it:

   - `GET /leads/{id}/replies` returns bounces and outgoing mail as rows and
     under-reports real replies (§3.7). **HIGH** — a merged document uses it
     as a reply witness.
   - Exactly one contact in 1,065 carries a `heyreach_lead_id`, so LinkedIn
     reply state is unrecordable for the estate (§5.3). **HIGH.**
   - `reengagement_provider_confirmed.py --report` dates frozen sends against
     a live clock, so re-running it can only ever ADMIT leads (§1).
     **MEDIUM** — it is the documented reproduction command.
   - **Offset pagination refuses past page 1,000 and every walk in this
     repository uses it** (§7.3). **HIGH** — it silently caps every read at
     15,000 rows while `meta.last_page` promises more, and `_walk`'s
     completeness check turns that into a refusal rather than a short read,
     which is why it has cost availability rather than correctness so far.
   - `total_leads` is wrong on at least two campaigns, by 588 and by 332
     (§7.4). **LOW**, but it is a denominator people quote.

---

## 11. REPRODUCING THIS

    py -3 scripts/reengagement_cohort_lane_i.py --freshen
    py -3 scripts/reengagement_cohort_lane_i.py --sends
    py -3 scripts/reengagement_cohort_lane_i.py --livebook
    QUEUE=<production work/queue.jsonl> \
      py -3 scripts/reengagement_linkedin_lane_i.py --read
    py -3 scripts/reengagement_cohort_lane_i.py --report

`--report` makes no network call and is the only phase that is cheap to
repeat. Staged output is under `work/stage/`, which stays gitignored:
`ri-campaigns.json`, `ri-leads.jsonl`, `ri-lead-sends.jsonl`,
`ri-livebook.jsonl`, `ri-linkedin.json`, `ri-cohort.json`.

**`ri-cohort.json` is the deliverable, not this document.** It carries the
1,031 lead ids; a per-lead inclusion reason with the dated-send count and
age; the 1,100 exclusions with clause, the provider's own phrasing, every
other clause tripped and the read timestamp; the 762 accounts; and the
collision verdict per account. This file is what a push should be built
from, and it should be REBUILT rather than reused if it is more than a few
hours old — see §1.

**`--livebook` is the expensive phase** (2,833 requests) and it is
resumable: campaigns already on disk are skipped. It only needs re-running
when the set of live campaigns changes.

**Set `QUEUE` to production's `work/queue.jsonl`.** A worktree has its own
`work/`, usually stale and here entirely absent, and the LinkedIn join reads
as a complete miss when it is really a path fault. `_store_contacts` now
refuses rather than answering from an empty store, but the environment still
has to be right.

Do not read `lane`, `lane_at_walk` or `last_touch` from
`reengagement-inventory.jsonl`. And **do not re-run
`reengagement_provider_confirmed.py --report` for a current answer** — it
dates leads from a frozen file against a live clock and can only ever admit.

One more thing for whoever picks this up: **`_walk_cursor` is reusable and
nothing else in the repository has it yet.** Any route that is currently
"too big to walk" is a `?pagination_type=cursor` away from being readable,
and the termination contract in that function is the part to copy carefully
— cursor pagination removes the `meta.total` check that makes `_walk`
refuse a short read, so the refusals have to be put back by hand.
