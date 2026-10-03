# LinkedIn — second brain

Everything here is a measurement with its source, its date, its window and its
`n`. Nothing in this file is advice that is not a number. It is appended to at
each finding and never rewritten backwards.

Read 2026-10-03 by TASK-981 (lane D), branch `task-981-second-brain-linkedin`.
**Provider reads only. Zero provider writes. Zero model spend** — every
classification below comes from `src/replies.classify_rules`, which is the
deterministic pass and calls no model.

**The writer reads only APPROVED EXEMPLARS from this file, never the
syntheses, until the operator approves. Nothing on this page has been copied to
`prompts/exemplars/`.**

---

## 1. How this was read, and what it cost

| | |
|---|---|
| Provider | HeyReach, `https://api.heyreach.io/api/public` |
| Credential | `HEYREACH_KEY` — the name comes from the registry in `src/config.py:148`, not from a guess |
| Organisation unit | `118832`, and it is the **only** one on this key: all 121 campaigns carry `organizationUnitId: 118832` |
| Routes used | `POST /campaign/GetAll`, `POST /stats/GetOverallStats`, `POST /inbox/GetConversationsV2`, `POST /li_account/GetAll`, `GET /campaign/GetCampaignSequence`, `GET /list/GetById` — all read-only, all on `heyreach.READ_ROUTES_ALL` / `READ_GET_ROUTES` |
| Read at | 2026-10-03, 13:2x–14:0x UTC |
| Stats window on every number below | `startDate = 2026-04-01T00:00:00Z`, `endDate = 2026-10-04T00:00:00Z` |

The window covers the whole life of the estate: the earliest `creationTime` on
any of the 121 campaigns is `2026-04-04T21:23:51Z` and the latest is
`2026-09-25T12:11:20Z`.

**What it cost, measured.**

| walk | provider calls | seconds | per unit |
|---|---|---|---|
| 121 campaigns: stats + sequence + list + inbox count | 446 | 263 | 2.18 s/campaign |
| 17,732 conversation→campaign pairs, with message bodies and profile fields | 226 | 200 | 0.011 s/conversation |
| whole inbox, no filter, 28,041 conversations | 281 | 297 | 0.011 s/conversation |
| probes (route shapes, additivity controls, seat stats) | ~25 | ~20 | |

≈ **980 read calls, ≈ 13 minutes of provider time**, 0 writes, 0 credits, 0
model tokens. The cap-before-fan-out order was honoured: one campaign was read
first, the per-campaign cost measured at 2.18 s, and only then the full walk
issued.

**Coverage, stated as read / not read.**

- campaigns: **121 of 121** (`/campaign/GetAll` `totalCount` = 121, two pages).
  Zero could not be read.
- campaign stats: **121 of 121**. Zero failures.
- campaign sequences: **119 of 121**. Two failed —
  **594057** and **594060**, both `DRAFT`, both
  `ProviderError: heyreach /campaign/GetCampaignSequence: unexpected response
  shape`. Their copy is therefore UNKNOWN, not empty.
- lead lists: resolved by `linkedInUserListId` for every campaign that has one.
- inbox: **28,041 of 28,041** conversations (`totalCount` = 28,041).

---

## 2. The measurement that gates every number on this page

The operator's rule — numbers come from the stats endpoint with
`startDate`/`endDate` and never `timeFrom`/`timeTo` — was re-measured here
rather than assumed. Campaign **605732**, four calls, 2026-10-03:

| body | `connectionsSent` returned |
|---|---|
| `timeFrom: null, timeTo: null` | 3 |
| `timeFrom: 2026-09-01, timeTo: 2026-09-02` (a one-day window) | **3** |
| `startDate: 2026-09-01, endDate: 2026-09-02` (the same one-day window) | **0** |
| `startDate: 2020-01-01, endDate: 2027-01-01` | 3 |

`timeFrom`/`timeTo` returned the lifetime figure for a one-day window, i.e. it
was discarded in silence. `startDate`/`endDate` returned 0 for that day and 3
for a covering window. **`src/providers/heyreach.campaign_stats` still sends
`timeFrom`/`timeTo` (hardcoded to `None`), so it can only ever report
lifetime.** That is correct for its one caller's question and wrong for any
windowed one; nothing on this page used it.

**Two more key-level traps, both measured, both of the shape "a reader asking
the wrong key prints empty and looks like empty data".**

1. `/stats/GetOverallStats` returns **22** numeric keys in `overallStats`.
   `campaign_stats` trims to four. The four do not include InMail, so an
   InMail campaign reads as a campaign that did nothing.
2. **`inmailMessagesSent` is 0 on all 121 campaigns.** The InMail volume is in
   **`totalInmailStarted` = 4,657** with **`totalInmailReplies` = 287**. A
   reader asking `inmailMessagesSent` concludes this estate has never sent an
   InMail. It has sent 4,657.
3. On messages, **`isInMail` is `false` on all 57,811 messages read**,
   including every message in the three campaigns the stats credit with 4,657
   InMails. The field that does separate them is `subject`: 4,996 of 54,647
   outbound messages carry one, and 4,648 of those 4,996 sit in campaigns
   `406850`, `524000` and `467951` — against `totalInmailStarted` of 4,657.
   **`subject` is the InMail marker on this provider; `isInMail` is dead.**

---

## 3. Ownership, by the authority, unchanged

Three states, per OPERATING-MODE "DVA TIPA KAMPANJA U SVAKOM WORKSPACEU",
Zvonimir, 2026-10-01, point 6 ("isto vrijedi za HeyReach kampanje, istim trima
stanjima").

| state | authority | count |
|---|---|---|
| `resonate_os` | a row in `work/campaigns.jsonl` carrying `heyreach_campaign_id` | **40** |
| `resonate_internal` | the operator's declared list | **0** |
| `unknown` | neither | **81** |

**121 total.** All 40 ledger ids are present on the seat and none is missing.

**The 0 is itself the finding.** The operator's declaration of 2026-10-01 names
**EmailBison** 274, 327, 328 and 352. There is **no operator-declared list of
internal HeyReach campaigns** anywhere in `src/`, `config/` or `docs/` — I
searched for one and found none. So the 81 non-ledger campaigns are `unknown`,
which under the standing rule means **do-not-touch and members NOT CLEAN**.
This brief's framing of "5 the client's, 76 unknown" is not supported by any
authority I can read: the provider's campaign record carries **no owner,
creator, user, team or tenant field** — confirmed across the full key set, all
16 keys, on all 121 campaigns:

```
campaignAccountIds  creationTime  excludeContactedFromSenderInOtherCampaign
excludeFromCompanyBlacklist  excludeFromLeadBlacklist
excludeHasOtherAccConversations  excludeInOtherCampaigns  excludeListId
id  linkedInUserListId  linkedInUserListName  name  organizationUnitId
progressStats  startedAt  status
```

Marking any of the 81 as the client's would be the same mistake
`provider_truth.owned_by_resonate` made on EmailBison: writing "not provably
ours" down as "the client's". **UNKNOWN is a state. It stays 81 until the
operator declares otherwise.**

Provider status across the 121: `PAUSED` 66, `FINISHED` 34, `IN_PROGRESS` 12,
`DRAFT` 9.

---

## 4. The estate, in one table

Window 2026-04-01 .. 2026-10-04, summed over all 121 campaigns from
`/stats/GetOverallStats`.

| metric | value |
|---|---|
| connection requests sent | **116,923** |
| connection requests accepted | **12,954** → **11.08%** (12,954 / 116,923) |
| unique leads contacted | 123,192 |
| ordinary messages sent | 25,551 |
| message threads started | 12,684 |
| message replies | **1,972** → **15.55%** of threads started (1,972 / 12,684), **7.72%** of messages sent (1,972 / 25,551) |
| InMail threads started | 4,657 |
| InMail replies | **287** → **6.16%** (287 / 4,657) |
| provider's own `autoTaggedInterested` | 460 |
| provider's own `totalAutoTagged` | 2,261 |
| profile views / follows / post likes | 179,802 / 125,121 / 89,081 |
| **meetings** | **not a field. See §9.** |

65 of 121 campaigns sent at least one connection request; 56 sent none.

**Seat 174810, which the brief names.** `accountIds: [174810]`, window
2026-04-01 .. 2026-10-04: **4,258 sent / 416 accepted = 9.77%**; 769 messages
sent, 59 replies (**7.67%** of messages), `autoTaggedInterested` 12. The brief's
4,256 / 415 = 9.75% is the same seat read earlier — two more requests and one
more acceptance have landed since, which is the seat still working, not a
disagreement. Note the seat is **not** a campaign: 174810 appears as a sender on
campaign `613741` (5 requests) and its remaining 4,253 requests were sent inside
campaigns it shares with other seats.

**All 41 seats together**, same window: 117,701 sent / 13,052 accepted =
**11.09%**; 25,564 messages, 1,987 replies; `autoTaggedInterested` 471. That is
778 more requests than the 121 campaigns account for, i.e. a small amount of
seat activity sits outside these campaigns.

---

## 5. THE ORDERING: positive replies per 100 connection requests sent

**Every rate in this section is `classifier unaudited`.** It is
`src/replies.classify_rules` (`VERSION = "rules-4"`), rules only, no model.
`§8` is the sample the operator reviews before any of it is trusted, and §8.1
is the measured reason to distrust it.

**What counts as positive, the operator's definition applied literally:**
classes `positive`, `meeting_intent` and `question`. **A referral is not
positive. `send_info` — "send me some information and I will see" — is not
positive.** Those are counted and reported separately.

Across the 17,732 conversation→campaign pairs: **3,164 inbound messages**, of
which

| class | n | share of inbound |
|---|---|---|
| `unknown` | 1,828 | 57.77% |
| `negative` | 628 | 19.85% |
| **`positive`** | **164** | 5.18% |
| `not_relevant` | 162 | 5.12% |
| `automated` | 156 | 4.93% |
| **`question`** | **83** | 2.62% |
| `objection` | 39 | 1.23% |
| `unsubscribe` | 30 | 0.95% |
| `out_of_office` | 30 | 0.95% |
| `not_now` | 26 | 0.82% |
| `send_info` | 10 | 0.32% — **counted separately, not positive** |
| `referral` | 5 | 0.16% — **counted separately, not positive** |
| `assistant_redirect` | 3 | 0.09% |
| **`meeting_intent`** | **0** | 0.00% |

**operator-positive = 164 + 83 + 0 = 247** of 3,164 inbound = 7.81% of inbound
messages, and **0.211 per 100 connection requests sent** (247 / 116,923).

`meeting_intent` fired zero times in 3,164 real LinkedIn replies. That is a
measurement about the rule table, not about the estate.

### 5.1 The ranking, `n` floor stated

Ordered by positives per 100 requests sent, over the **18** campaigns with
`connectionsSent >= 1,000` (112,230 of the estate's 116,923 requests, 211 of
its 247 positives). Campaigns below the floor are in §11 and are not ranked: at
`n = 4` a single positive reads as 25 per 100.

| rank | id | owner | sent | accepted | acc% | positives | **pos/100 sent** | pos/100 accepted |
|---|---|---|---|---|---|---|---|---|
| 1 | 388939 | unknown | 1,650 | 183 | 11.09% | 16 | **0.970** | 8.74 |
| 2 | 388958 | unknown | 3,913 | 406 | 10.38% | 20 | **0.511** | 4.93 |
| 3 | 388942 | unknown | 1,650 | 168 | 10.18% | 8 | **0.485** | 4.76 |
| 4 | 388953 | unknown | 1,634 | 172 | 10.53% | 7 | **0.428** | 4.07 |
| 5 | 388949 | unknown | 6,890 | 1,256 | 18.23% | 23 | **0.334** | 1.83 |
| 6 | 467366 | unknown | 7,988 | 1,091 | 13.66% | 23 | 0.288 | 2.11 |
| 7 | 428674 | unknown | 4,545 | 985 | 21.67% | 12 | 0.264 | 1.22 |
| 8 | 388951 | unknown | 1,219 | 275 | 22.56% | 3 | 0.246 | 1.09 |
| 9 | 523983 | unknown | 18,053 | 2,096 | 11.61% | 43 | 0.238 | 2.05 |
| 10 | 388955 | unknown | 5,880 | 547 | 9.30% | 12 | 0.204 | 2.19 |
| 11 | 429679 | unknown | 8,709 | 1,280 | 14.70% | 13 | 0.149 | 1.02 |
| 12 | 473854 | unknown | 3,808 | 472 | 12.39% | 4 | 0.105 | 0.85 |
| 13 | 388960 | unknown | 6,002 | 499 | 8.31% | 5 | 0.083 | 1.00 |
| 14 | 524002 | unknown | 30,207 | 1,862 | 6.16% | 18 | **0.060** | 0.97 |
| 15 | 523922 | unknown | 1,951 | 48 | 2.46% | 1 | **0.051** | 2.08 |
| 16 | 429680 | unknown | 5,911 | 754 | 12.76% | 3 | **0.051** | 0.40 |
| 17 | 523987 | unknown | 1,091 | 20 | 1.83% | 0 | **0.000** | 0.00 |
| 18 | 523932 | unknown | 1,129 | 15 | 1.33% | 0 | **0.000** | 0.00 |

**Not one Resonate OS campaign is on this table.** The 40 ledger campaigns have
sent **172 connection requests between them** — 3 to 5 each — and hold **2** of
the 247 positives. Everything that has ever worked on LinkedIn in this estate
was sent by a campaign whose owner is `unknown`.

### 5.2 What separates the top 5 from the bottom 5, as numbers

The spread is **16x on positives per 100 sent** (0.970 → 0.060 at the volume
end) and **22x on positives per 100 accepted** (8.74 → 0.40). The acceptance
half of the funnel explains almost none of it:

| | top 5 | bottom 5 | ratio |
|---|---|---|---|
| requests sent (`n`) | 15,737 | 40,289 | |
| acceptance | 2,185 / 15,737 = **13.88%** | 2,699 / 40,289 = **6.70%** | 2.1x |
| positives per 100 sent | 74 / 15,737 = **0.470** | 22 / 40,289 = **0.055** | **8.6x** |
| positives per 100 accepted | 74 / 2,185 = **3.39** | 22 / 2,699 = **0.82** | **4.1x** |

So 2.1x of the 8.6x is acceptance and 4.1x of it happens *after* the person has
already accepted — i.e. **the first message after acceptance is where most of
the gap is**, not the connection note. Three differences in the copy, measured:

1. **When the first message lands.** Top-5 campaigns put the first message
   **3.00 days** after the connection request (388939/388953/388958) or
   **3.00 days** after it (388942, whose request is itself at day 9 behind
   VIEW_PROFILE → LIKE_POST → FOLLOW). 524002 puts it at **day 8.12**, behind
   `FOLLOW` (3h) → `CONNECTION_REQUEST` (+5 days) → message (+3 days).
2. **Variant count.** Top 5: **3 variants** per message step. 524002: **11**
   variants at step 1, of which variants 3,4,5,6,7 are byte-identical and
   8,9,10 are byte-identical — so 11 slots carry **4** distinct texts. 429680
   rotates **15** connection-note variants. More slots did not buy more
   positives.
3. **Register.** The top 5 open with an un-pitched sentence and an explicit
   release ("No pressure on that though, good to be connected either way");
   524002 opens with the pitch and a joke at the prospect's expense ("what's
   your current setup for tracking it at {COMPANY}, a tool, spreadsheets, or
   vibes?"). Both are ~370 chars, so **this is not a length difference** — see
   §6.2, where length does separate at the message level.

The full copy of all ten is in §11 under each id. The two step-1 texts that
carry the whole difference are reproduced here, in full, because they are ours:

**388939 / 388953 / 388958 — step 1, day 3.00 after the request, variant 1 of 3
(510 chars, 80 words), rank 1/2/4:**

```
Hi {FIRST_NAME}, appreciate the add.

I help {INDUSTRY} agencies in {LOCATION} replace the usual pile of disconnected tools with one platform that ties together projects, time tracking, budgets and invoicing. The idea being that a {POSITION} can actually see whether a project is profitable while it is still running rather than finding out after the invoice goes out.

Thought {COMPANY} might be worth a conversation at some point. No pressure on that though, good to be connected either way.

{MY_FIRST_NAME}
```

**524002 — step 1, day 8.12, variant 1 of 11 (370 chars, 55 words), rank
14/18 and the single largest spend in the estate at 30,207 requests:**

```
thanks for accepting {FIRST_NAME}, now i'll earn the connection. 

the usual agency pain is utilization, you don't really know who's overloaded and who's idle until something breaks. 

Productive gives you that view live, alongside budgets and billing in one place. what's your current setup for tracking it at {COMPANY}, a tool, spreadsheets, or vibes?
 {MY_FIRST_NAME}
```

**Confounds, named rather than hidden.** These are campaign-level comparisons.
Top-5 campaigns ran April–May on `MARKETING AGENCIES` lists in AU/USA/EU;
bottom-5 ran July–October, two of them (`523987`, `523932`) on the 33,710-lead
OMEGA list whose acceptance is 1.3–1.8% — a tenth of the estate's. List
quality, geography, seat, send period and copy all move together here, and
nothing in this corpus separates them. A campaign-level ranking is the unit the
provider gives; it is not an experiment.

---

## 6. Measurements

### 6.1 Reply and positive rate by our step number

One touch = one outbound message. A touch "drew a reply" when the next message
in the conversation is inbound. Over the 17,732 joined conversations.

| our step | touches | replied | reply% | positive | pos% |
|---|---|---|---|---|---|
| 1 | 17,696 | 1,061 | 6.00% | 113 | 0.639% |
| 2 | 11,468 | 678 | 5.91% | 45 | 0.392% |
| 3 | 9,984 | 532 | 5.33% | 21 | 0.210% |
| 4 | 6,086 | 274 | 4.50% | 16 | 0.263% |
| 5 | 4,350 | 136 | 3.13% | 8 | 0.184% |
| 6 | 2,676 | 97 | 3.62% | 2 | 0.075% |
| 7 | 1,158 | 36 | 3.11% | 2 | 0.173% |
| 8 | 851 | 50 | 5.88% | 0 | 0.000% |
| 9+ | 378 | 27 | 7.14% | 2 | 0.529% |

**Step 1 carries 113 of 247 positives (45.7%) and steps 1–2 carry 158 (64.0%).**
Positive rate per touch falls **8.5x** from step 1 (0.639%, n=17,696) to step 6
(0.075%, n=2,676) while reply rate falls only 1.7x. Later steps keep producing
replies and stop producing interest.

Counted over the positives themselves rather than over touches: of the 247,
**17** arrived before any message of ours (a reply to the connection request
itself), **123** after exactly one, **49** after two, **22** after three. Median
touches before a positive = **1**. Median elapsed time from the first event in
the conversation to the positive = **0.87 days**; p90 = 32.87 days; max =
134.70 days (n=247).

### 6.2 Reply and positive rate by the length of the message we sent

| length of our message | touches | replied | reply% | positive | pos% |
|---|---|---|---|---|---|
| 1–99 chars | 6,055 | 370 | 6.11% | 20 | 0.330% |
| **100–299 chars** | **22,163** | **1,394** | **6.29%** | **122** | **0.550%** |
| 300–499 chars | 23,495 | 949 | 4.04% | 59 | 0.251% |
| 500–699 chars | 2,203 | 125 | 5.67% | 6 | 0.272% |
| 700+ chars | 731 | 53 | 7.25% | 2 | 0.274% |

**100–299 characters is 2.2x better on positives than 300–499** (0.550% vs
0.251%) on 22,163 against 23,495 touches — the two largest buckets in the
corpus and almost the same size, which is the cleanest comparison on this page.
Reply rate alone would have told you 6.29% vs 4.04%, a 1.6x gap; the positive
rate gap is larger.

### 6.3 Reply and positive rate by the gap since our previous message

| gap | touches | replied | reply% | positive | pos% |
|---|---|---|---|---|---|
| < 1 day | 1,119 | 347 | 31.01% | 19 | 1.698% |
| 1–3 days | 1,545 | 202 | 13.07% | 13 | 0.841% |
| 3–5 days | 9,117 | 360 | 3.95% | 28 | 0.307% |
| 5–10 days | 19,518 | 718 | 3.68% | 25 | 0.128% |
| 10+ days | 5,652 | 203 | 3.59% | 11 | 0.195% |

**The `< 1 day` row is confounded and must not be read as a cadence finding.** A
sub-day gap is overwhelmingly our own answer inside a live thread — the person
had already engaged — so a reply following it is near-tautological. The rows
that are a cadence finding are 3–5 vs 5–10 days: **0.307% vs 0.128% positives
per touch, a 2.4x difference on n=9,117 against n=19,518**. The estate's own
default is the worse of the two: 19,518 of its 37,000 touches sit in the 5–10
day bucket.

### 6.4 Connection note: with, without, how long, what kind

The note is a campaign-level property, so the unit is campaign-weighted
requests. **Warmup campaigns (470010/470035/470037/470038/470039/470040) are
excluded from every note comparison**: they are 832 requests at **57.69%**
acceptance (480/832), which is not prospecting, and leaving them in would move
the no-note row by 0.4pp on its own.

Prospecting campaigns with `connectionsSent > 0`: **59**, 116,091 requests,
12,474 accepted = **10.75%**.

| | campaigns | accepted / sent | acceptance |
|---|---|---|---|
| connection request **carries a note** | 9 | 2,769 / 23,874 | **11.60%** |
| connection request note is **empty** | 50 | 9,705 / 92,217 | **10.52%** |

**A note is worth +1.08 percentage points on acceptance, 11.60% against 10.52%,
on 23,874 requests against 92,217.** That is a 10% relative lift and it is the
whole effect: the note's own text barely moves it further.

| mean note length (chars, whitespace-normalised) | campaigns | accepted / sent | acceptance |
|---|---|---|---|
| none (0) | 50 | 9,705 / 92,217 | 10.52% |
| short, 1–99 | 2 | 1,091 / 7,991 | **13.65%** |
| medium, 100–179 | 6 | 1,179 / 9,881 | 11.93% |
| long, 180+ | 1 | 499 / 6,002 | **8.31%** |

| note type | campaigns | accepted / sent | acceptance |
|---|---|---|---|
| contains a question mark | 2 | 1,253 / 11,913 | 10.52% |
| statement only | 7 | 1,516 / 11,961 | **12.67%** |

| note names the company | campaigns | accepted / sent | acceptance |
|---|---|---|---|
| merges `{COMPANY}` | 6 | 924 / 9,972 | **9.27%** |
| does not | 3 | 1,845 / 13,902 | **13.27%** |

| note variants rotated | campaigns | accepted / sent | acceptance |
|---|---|---|---|
| 1 | 2 | 1,091 / 7,991 | **13.65%** |
| 2–4 | 5 | 425 / 3,970 | 10.71% |
| 5+ | 2 | 1,253 / 11,913 | 10.52% |

**The caveat that undoes most of the note reading, and it has to be said
loudly.** The `short, 1–99` bucket, the `1 variant` bucket and the `does not
merge {COMPANY}` bucket are all dominated by **one campaign, 467366, 7,988
requests, 13.66% acceptance** — and its note is nineteen characters:

```
Hey, let's connect!
```

That is not copy anybody wrote for this client; it is a generic opener. It is
not on `heyreach.DEFAULT_NOTES` (which holds `hey, would love to connect!`,
`hi, would love to connect!`, `would love to connect!`,
`hi {{firstname}}, would love to connect!`), so `note_is_placeholder` returns
False for it and no gate would stop it. **With 467366 removed, the remaining 8
note-carrying campaigns are 1,678 / 15,886 = 10.56% — statistically the same as
the no-note 10.52%.** So the honest claim is: *the only note in this estate that
beat no-note at scale is a nineteen-character generic one*, and the long
personalised notes (164–234 chars, merging `{COMPANY}`, `{INDUSTRY}`,
`{LOCATION}`) did not.

And the single worst acceptance among note-carrying campaigns is the longest
note: **388960, 6,002 requests, 8.31%**, 9 variants averaging 218 chars, the
"honest sales connect" angle. It is ours, so here is one in full:

```
hi {FIRST_NAME}, i'll be straight with you, i work with marketing agencies on getting projects and finances into one place, and i'd love to pitch you at some point. Connecting first felt more honest than pretending otherwise. {MY_FIRST_NAME}
```

Declaring the pitch in the note cost **2.2 percentage points of acceptance
against the 10.52% no-note baseline, on n=6,002** — and 388960 also sits at rank
13 of 18 on positives (0.083 per 100). Measured, on this list, in this period:
it did not pay for itself at either end of the funnel.

### 6.5 Our own four Resonate OS sequences send a merge variable, not a note

`599020`, `604869`, `605487` and `605732` each carry exactly one
`CONNECTION_REQUEST` note and its text is the literal string:

```
{connection_note}
```

That is by design — the HeyReach sequence holds merge variables and the words
arrive per lead in `customUserFields` — but it has two measured consequences.
First, `note_is_placeholder("{connection_note}")` is **False**, and
`connection_notes()` reports a non-empty note, so **every note check in this
repository passes on a sequence whose note text is a variable name**. Second,
whether it ever rendered is **UNKNOWN**: 605732 sent **3** requests and got
**0** acceptances, which proves nothing either way, and 599020/604869/605487
sent **0**. The canary `594061` is the one of ours that holds real words, and it
sent 0 requests.

### 6.6 Persona, from the public headline only

Bucketed by regex over `correspondentProfile.headline` + `position`. No name and
no company enters this table. Per joined conversation (i.e. per lead who got
that far), n = 17,732.

| persona bucket | conversations | replied | reply% | with a positive | pos% |
|---|---|---|---|---|---|
| ops / delivery | 5,185 | 627 | 12.09% | 57 | 1.10% |
| **founder / owner** | 3,278 | 449 | 13.70% | 61 | **1.86%** |
| ceo / md | 2,447 | 257 | 10.50% | 28 | 1.14% |
| other, unclassified | 2,259 | 338 | 14.96% | 18 | 0.80% |
| **marketing** | 2,205 | 292 | 13.24% | 36 | **1.63%** |
| c-suite other | 1,531 | 185 | 12.08% | 16 | 1.05% |
| sales / bd | 304 | 47 | 15.46% | 8 | 2.63% |
| creative / design | 181 | 18 | 9.94% | 1 | 0.55% |
| director / head | 153 | 23 | 15.03% | 0 | 0.00% |
| engineering | 84 | 17 | 20.24% | 4 | 4.76% |
| finance | 63 | 10 | 15.87% | 1 | 1.59% |
| no headline | 42 | 3 | 7.14% | 0 | 0.00% |

**Founder/owner is 1.69x ops/delivery on positives (1.86% of 3,278 against
1.10% of 5,185)** and the estate sent 1.58x more at ops/delivery than at
founders. `sales/bd` (2.63%) and `engineering` (4.76%) are above everything on
`n` = 304 and 84 and are observations, not learnings.

Counted over the 247 positives themselves: founder/owner **89**, ops/delivery
**65**, ceo/md **38**, c-suite other **19**, marketing **17**, other 8, sales/bd
5, engineering 3, creative 1, director 1, finance 1.

Verticals are not a provider field. The only vertical signal is in our own list
names — `MARKETING AGENCIES`, `SOFTWARE DEVELOPMENT`, `inmails`,
`SAFE TO SEND EMAIL - DOUBLE DOWN` — and the geography likewise:
`EU`, `EUROPE`, `USA 1ST`, `USA 2ND`, `AUSTRALIA`. Those are recorded per
campaign in §11. **`correspondentProfile` carries `location` and
`companyUrl`, so a real vertical/geography cut is possible from data already
read and is not done here.**

### 6.7 InMail against the ordinary message

Per touch, over the joined set, `subject`-bearing outbound = InMail (§2).

| | touches | replied | reply% | positive | pos% |
|---|---|---|---|---|---|
| InMail | 4,996 | 300 | **6.00%** | 7 | **0.140%** |
| ordinary message | 49,651 | 2,591 | 5.22% | 202 | **0.407%** |

**InMail replies 1.15x more often and produces 2.9x fewer positives per touch.**
It also skips the acceptance gate entirely, which is why `connectionsSent` is 0
on `406850`, `524000` and `467951` and why those three look dead to any reader
using the four-key trim.

---

## 7. Joining replies to campaigns — and the 284 that stay `unknown campaign`

**A HeyReach conversation does not carry a campaign id as a top-level field.**
Confirmed on the full key set of `/inbox/GetConversationsV2` rows: `blockedByMe`,
`blockedByParticipant`, `correspondentProfile`, `groupChat`, `id`,
`lastMessageAt`, `lastMessageSender`, `lastMessageText`, `lastMessageType`,
`linkedInAccount`, `linkedInAccountId`, `messages`, `read`, `totalMessages`. No
campaign.

**But the route's `campaignIds` filter is honoured, and that is the join.**
Measured 2026-10-03:

| query | `totalCount` |
|---|---|
| no filter | 28,041 |
| `campaignIds: [565765]` | 132 |
| `campaignIds: [605732]` | 0 |
| `campaignIds: [565765, 605732]` | 132 |
| `campaignIds: [999999999]` | **HTTP 400** — a refusal, not the whole inbox |
| `campaignIds: [`all 121`]` | **15,885** |

A nonexistent id answers 400 rather than returning 28,041, which is how an
*ignored* filter behaves on this route — so the filter is doing work. The join
is therefore **server-side and exact**, not a date-and-list guess.

**It is not perfectly disjoint.** `campaignIds: [388949]` → 1,257 and
`[429679]` → 1,255, but the pair → 2,506: **6 conversations belong to both**.
Summed per campaign the 121 give 17,732 conversation→campaign pairs against a
union of 15,885 — **1,847 pairs are a second attribution of a conversation
already counted.** A lead worked by two campaigns on the same seat produces one
conversation and two attributions.

**What cannot be joined, deduplicated by (lead, message timestamp):**

| | whole inbox | joined to ≥1 of the 121 | **not joinable** |
|---|---|---|---|
| conversations | 28,041 | 15,885 (union) | 12,156 |
| distinct leads | 22,045 | 12,407 | **9,638 = 43.7%** |
| inbound messages | 6,273 | 2,944 | **3,329 = 53.1%** |
| operator-positive replies | **513** | **229** | **284 = 55.4%** |

**284 operator-positive replies on this seat cannot be attributed to any
campaign and are recorded here as `unknown campaign`.** They are not guessed
onto a campaign. 40 distinct seats appear in the inbox; the largest by
conversation count are 116988 (1,738), 129531 (1,675), 125748 (1,642), 116989
(1,470), 125775 (1,380). It is **not** explained by an off-roster seat: 39 of
the 41 seats on `/li_account/GetAll` are used by at least one of the 121
campaigns, and the two that are not — 170308 and 210951 — are small. The
mechanism left is the one the operator already named: the inbox is each seat's
whole LinkedIn history, including everything the client's team did by hand and
every campaign that no longer exists.

**The operator's standing warning holds and is now quantified: more than half of
the positive-looking replies in this inbox are not ours to claim.** Before
calling any reply ours, ask `campaignIds` for the campaign and require a
non-zero answer.

**There is a second, independent join that this walk found and did not need to
use.** `correspondentProfile.autoTags` is a list of
`{name, campaignId, campaignName}` — so a conversation *does* carry a campaign
id, nested two levels down, whenever HeyReach has auto-tagged the lead. That is
a cross-check on the `campaignIds` filter and a route to attribution for
conversations the filter misses. Not measured here beyond its existence and its
shape.

---

## 8. The positive-reply corpus — `n = 247`, and it is for review, not for use

The operator reviews this before any positive rate on this page is trusted.
**Nothing here has been or may be copied to `prompts/exemplars/`** until that
review lands.

**Shape, so it assembles with the email lane's rows.** One object per line in
`work/task981/positive-replies.jsonl` (gitignored, un-redacted), keys:
`channel`, `campaign`, `campaign_name`, `ownership`, `lead_anon`, `persona`,
`seat`, `step`, `touches_before`, `day`, `at`, `class`, `confidence`, `reason`,
`evidence_redacted`, `provider_tags`, `our_text_template`,
`our_text_matched_a_template`, `our_text_rendered_redacted`,
`reply_text_redacted`, `our_text_RAW`, `reply_text_RAW`.
`separate-classes.jsonl` beside it holds the 15 `referral` and `send_info` rows
that are deliberately **not** positive.

By channel: 247 of 247 `linkedin_message`, **0 `linkedin_inmail`** — the 7
InMail positives of §6.7 are counted there per touch; none of them is the
message immediately preceding a positive, because an InMail positive arrives
against a `subject`-less follow-up.

By ownership: **245 `unknown`, 2 `resonate_os`** (both on `613744`/`613761`, 4
requests each).

### 8.1 The classifier is wrong often enough that the rate must not be used yet

This is the measured reason for the `classifier unaudited` label, and it is
worse than a caveat.

- **36 of 247 (14.6%) rest entirely on a connection-acceptance pleasantry.**
  The matched phrase is `happy to connect` and the reply is, in full,
  `I'm happy to connect, <our own seat owner's first name>`. That is somebody
  accepting a connection request. It is not interest in anything.
- **6 rest on `how are you?`, 4 on `what do you do?`, 4 on
  `how can i help you?`.** Those are the `question` class firing on politeness,
  not on a question about the offer.
- **83 of 247 (33.6%) are replies of six words or fewer.**
- **HeyReach's own tagger disagrees with 49 of the 247 (19.8%)**: those
  conversations carry an `autoTags` entry whose name contains "not interested".
  It agrees — an interest-bearing tag on the same conversation — on 180 of 247
  (72.9%).
- The whole evidence distribution behind the 247, phrase → count:
  `interested` 55, `happy to connect` 36, `sounds good` 11, `let's do it` 7,
  `tell me more` 6, `sure` 6, `how are you?` 6, `sounds interesting` 4,
  `i'm interested` 4, `calendar` 4, `i'd love to learn more` 4, `yes please` 4,
  `curious how` 4, `what is it` 4, `curious what` 4, `what do you do?` 4,
  `how can i help you?` 4, `pricing` 3, `sounds great` 3, `keen to` 2,
  `availability` 2, `i am interested` 2, `happy to hear more` 2, `yes, please` 2,
  `sure thing` 2+2, `send me more info` 2, `set up a call` 2,
  `what do you have in mind?` 2, and 11 singletons.

**A defensible lower bound, pending the operator's review:** strip the 36
connection pleasantries and the 14 politeness questions and
**247 − 50 = 197** remain, which is **0.168 positives per 100 requests sent**
(197 / 116,923) rather than 0.211. The review may cut it further. **Do not
quote 0.211 as the estate's positive rate without saying it is unaudited.**

### 8.2 The rows

`n` = 247: every operator-positive reply this walk could join to a campaign.
All 247 are in **`work/task981/positive-replies.jsonl`** — gitignored, one JSON
object per line, carrying `reply_text_RAW` and `our_text_RAW` **un-redacted**.
That file is the reviewable list; `separate-classes.jsonl` beside it holds the
15 `referral` / `send_info` rows that are deliberately NOT positive.

**Why the recipients' words are not reproduced here, and it is a measurement.**
The first draft of this section printed each reply with the correspondent's own
`firstName` / `lastName` / `companyName` / `location` / `position`
substituted out — an exact substitution, not a guess. The PII scan then found
**86 hits** in it, and three classes of them were real: a recipient signing a
reply with a name that was not on their profile, a reply naming a colleague who
is not the recipient, and a reply naming a company that is not the
correspondent's `companyName`. **A free-text reply cannot be anonymised by
substituting the fields we hold, and the scan is what proved it rather than an
argument.** So the words stay in `work/`, which is gitignored and is where the
operator's rule puts real recipient data, and what is reproduced below is
everything about each reply that is not the recipient's own prose — including
**our** preceding message in full.

**How our own text is shown.** The message HeyReach actually sent carries the
recipient's company, industry and city, because that is what the merge
variables put there. So each sent message is matched back to its own campaign's
template by turning the template into a regex — every `{VAR}` becomes a
wildcard — and the template is printed, which is our copy in full and carries
no recipient at all. **132 of 247 rows matched a template.** The 115 that did not
are a hand-typed message from the seat owner or a template edited since, and
those rows say so and print no text, because the sent string is the one that
holds the rendered recipient.

**Every class on this page is `classifier unaudited`. §8.1 says by how much.**

| # | campaign | own | step | day | class | conf | persona | seat | reply words | names a person | asks a question | HeyReach tag | our text |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| P001 | 388939 | unk | 1 | 0.21 | `positive` | 0.75 | ceo/md | 174748 | 5 | yes | no | `NOT INTERESTED` | template below |
| P002 | 388939 | unk | 1 | 0.0 | `positive` | 0.75 | other / unclassified | 174845 | 5 | yes | no | `NOT INTERESTED` | template below |
| P003 | 388939 | unk | 1 | 0.6 | `positive` | 0.75 | founder/owner | 174845 | 5 | yes | no | `NOT INTERESTED` | template below |
| P004 | 388939 | unk | 1 | 0.0 | `positive` | 0.75 | c-suite other | 174748 | 5 | yes | no | `NOT INTERESTED` | template below |
| P005 | 388939 | unk | 1 | 0.0 | `positive` | 0.75 | ceo/md | 174803 | 5 | yes | no | `NOT INTERESTED` | template below |
| P006 | 388939 | unk | 1 | 0.0 | `positive` | 0.75 | founder/owner | 174742 | 5 | yes | no | `Information Request` | template below |
| P007 | 388939 | unk | 2 | 0.79 | `positive` | 0.75 | founder/owner | 174742 | 2 | no | no | `Information Request` | template below |
| P008 | 388939 | unk | 2 | 0.79 | `positive` | 0.75 | founder/owner | 174742 | 3 | no | no | `Information Request` | template below |
| P009 | 388939 | unk | 1 | 0.0 | `positive` | 0.75 | ceo/md | 174742 | 5 | yes | no | `NOT INTERESTED` | template below |
| P010 | 388939 | unk | 1 | 11.83 | `positive` | 0.75 | ops/delivery | 174742 | 5 | yes | no | `NOT INTERESTED` | template below |
| P011 | 388939 | unk | 7 | 134.67 | `positive` | 0.75 | founder/owner | 174892 | 1 | no | no | `HOT LEAD`, `Interested` | hand-typed, withheld |
| P012 | 388942 | unk | 3 | 7.07 | `positive` | 0.75 | founder/owner | 175455 | 45 | yes | yes | `Not ICP` | hand-typed, withheld |
| P013 | 388942 | unk | 4 | 16.43 | `positive` | 0.75 | other / unclassified | 174822 | 12 | no | yes | `NOT INTERESTED` | template below |
| P014 | 388942 | unk | 1 | 0.02 | `positive` | 0.75 | ops/delivery | 174822 | 15 | yes | no | `NOT INTERESTED` | template below |
| P015 | 388942 | unk | 1 | 3.3 | `positive` | 0.75 | ops/delivery | 174748 | 57 | yes | no | `Interested` | template below |
| P016 | 388942 | unk | 2 | 4.44 | `positive` | 0.75 | ops/delivery | 174748 | 59 | yes | yes | `Interested` | hand-typed, withheld |
| P017 | 388942 | unk | 3 | 5.82 | `positive` | 0.75 | ops/delivery | 174748 | 44 | yes | yes | `Interested` | hand-typed, withheld |
| P018 | 388949 | unk | 1 | 0.0 | `positive` | 0.75 | founder/owner | 174797 | 18 | no | yes | `Sales Pitch` | hand-typed, withheld |
| P019 | 388949 | unk | 1 | 2.68 | `positive` | 0.75 | ops/delivery | 174822 | 29 | yes | no | `NOT INTERESTED` | hand-typed, withheld |
| P020 | 388949 | unk | 1 | 0.0 | `positive` | 0.75 | founder/owner | 174797 | 21 | yes | yes | `NOT INTERESTED` | hand-typed, withheld |
| P021 | 388949 | unk | 2 | 5.98 | `positive` | 0.75 | ops/delivery | 174822 | 28 | yes | no | `NOT INTERESTED` | template below |
| P022 | 388949 | unk | 3 | 6.75 | `positive` | 0.75 | c-suite other | 174742 | 217 | yes | yes | `NOT INTERESTED` | template below |
| P023 | 388949 | unk | 1 | 0.0 | `positive` | 0.75 | founder/owner | 174742 | 3 | no | no | `Client` | hand-typed, withheld |
| P024 | 388949 | unk | 1 | 0.0 | `positive` | 0.75 | founder/owner | 174748 | 104 | yes | no | `Client` | hand-typed, withheld |
| P025 | 388949 | unk | 1 | 0.01 | `positive` | 0.75 | ops/delivery | 174742 | 19 | no | no | `Client` | hand-typed, withheld |
| P026 | 388949 | unk | 1 | 0.31 | `positive` | 0.75 | founder/owner | 174742 | 11 | no | yes | `Maybe baby`, `Information Request` | hand-typed, withheld |
| P027 | 388949 | unk | 1 | 0.0 | `positive` | 0.75 | c-suite other | 174845 | 12 | yes | yes | `Information Request` | hand-typed, withheld |
| P028 | 388949 | unk | 1 | 0.87 | `positive` | 0.75 | other / unclassified | 174742 | 29 | yes | no | `Not ICP` | hand-typed, withheld |
| P029 | 388949 | unk | 1 | 2.23 | `positive` | 0.75 | founder/owner | 174822 | 5 | yes | no | `Not ICP` | hand-typed, withheld |
| P030 | 388949 | unk | 1 | 0.01 | `positive` | 0.75 | marketing | 174822 | 16 | no | no | `Interested` | template below |
| P031 | 388949 | unk | 2 | 3.91 | `positive` | 0.75 | founder/owner | 174742 | 78 | no | no | `Not Right Now` | template below |
| P032 | 388949 | unk | 3 | 5.59 | `positive` | 0.75 | ceo/md | 174797 | 29 | yes | no | `FUP end 2026`, `Interested` | hand-typed, withheld |
| P033 | 388949 | unk | 2 | 6.78 | `positive` | 0.75 | founder/owner | 174332 | 7 | no | no | `BOOKED`, `Meeting Request` | template below |
| P034 | 388949 | unk | 0 | 0.0 | `positive` | 0.75 | ceo/md | 174332 | 53 | yes | no | `NOT INTERESTED` | none — reply to the request itself |
| P035 | 388949 | unk | 5 | 22.7 | `positive` | 0.75 | founder/owner | 174892 | 11 | yes | no | `NOT INTERESTED` | hand-typed, withheld |
| P036 | 388949 | unk | 6 | 58.42 | `positive` | 0.75 | sales/bd | 175455 | 32 | yes | no | `HOT LEAD`, `Not ICP`, `Meeting Request` | hand-typed, withheld |
| P037 | 388951 | unk | 0 | 0.0 | `positive` | 0.75 | founder/owner | 174742 | 144 | yes | yes | `Client` | none — reply to the request itself |
| P038 | 388953 | unk | 1 | 0.0 | `positive` | 0.75 | marketing | 174845 | 5 | yes | no | `Not ICP` | template below |
| P039 | 388953 | unk | 1 | 1.89 | `positive` | 0.75 | ops/delivery | 174742 | 5 | yes | no | `NOT INTERESTED` | template below |
| P040 | 388953 | unk | 1 | 0.53 | `positive` | 0.75 | ops/delivery | 174845 | 4 | no | no | `NOT INTERESTED` | template below |
| P041 | 388953 | unk | 1 | 0.02 | `positive` | 0.75 | ops/delivery | 174742 | 4 | yes | no | `No longer in company` | template below |
| P042 | 388953 | unk | 1 | 0.0 | `positive` | 0.75 | ops/delivery | 174742 | 5 | yes | no | `NOT INTERESTED` | template below |
| P043 | 388953 | unk | 1 | 0.0 | `positive` | 0.75 | founder/owner | 175455 | 78 | yes | no | `Not Right Now` | template below |
| P044 | 388955 | unk | 3 | 5.1 | `positive` | 0.75 | ops/delivery | 174803 | 23 | yes | no | `NOT INTERESTED` | hand-typed, withheld |
| P045 | 388955 | unk | 3 | 6.81 | `positive` | 0.75 | engineering | 174748 | 4 | no | no | `NOT INTERESTED` | hand-typed, withheld |
| P046 | 388955 | unk | 0 | 0.0 | `positive` | 0.75 | founder/owner | 174797 | 49 | yes | no | `Not Right Now` | none — reply to the request itself |
| P047 | 388955 | unk | 2 | 6.51 | `positive` | 0.75 | c-suite other | 125748 | 3 | no | no | `Wrong Person` | hand-typed, withheld |
| P048 | 388955 | unk | 2 | 6.52 | `positive` | 0.75 | c-suite other | 169600 | 4 | no | no | `NOT INTERESTED` | template below |
| P049 | 388955 | unk | 1 | 0.01 | `positive` | 0.75 | c-suite other | 129531 | 44 | yes | no | `Interested` | template below |
| P050 | 388955 | unk | 2 | 7.1 | `positive` | 0.75 | ceo/md | 125775 | 126 | yes | no | `Information Request` | template below |
| P051 | 388955 | unk | 1 | 0.04 | `positive` | 0.75 | founder/owner | 116988 | 9 | no | no | `Not ICP`, `Meeting Request` | template below |
| P052 | 388955 | unk | 2 | 30.33 | `positive` | 0.75 | sales/bd | 116973 | 29 | yes | no | `Not ICP`, `Wrong Person` | hand-typed, withheld |
| P053 | 388958 | unk | 1 | 0.0 | `positive` | 0.75 | marketing | 174748 | 5 | yes | no | `Not ICP` | hand-typed, withheld |
| P054 | 388958 | unk | 1 | 1.0 | `positive` | 0.75 | founder/owner | 174748 | 5 | yes | no | `NOT INTERESTED` | hand-typed, withheld |
| P055 | 388958 | unk | 1 | 0.0 | `positive` | 0.75 | ops/delivery | 174332 | 5 | yes | no | `Not ICP` | hand-typed, withheld |
| P056 | 388958 | unk | 1 | 1.72 | `positive` | 0.75 | ops/delivery | 174742 | 5 | yes | no | `NOT INTERESTED` | hand-typed, withheld |
| P057 | 388958 | unk | 2 | 4.78 | `positive` | 0.75 | founder/owner | 174748 | 8 | no | no | `NOT INTERESTED` | template below |
| P058 | 388958 | unk | 2 | 7.39 | `positive` | 0.75 | marketing | 174748 | 9 | yes | no | `Not ICP` | hand-typed, withheld |
| P059 | 388958 | unk | 1 | 0.0 | `positive` | 0.75 | ops/delivery | 174892 | 4 | no | no | `Not ICP` | hand-typed, withheld |
| P060 | 388958 | unk | 1 | 0.0 | `positive` | 0.75 | ops/delivery | 174332 | 5 | yes | no | `Not ICP` | hand-typed, withheld |
| P061 | 388958 | unk | 1 | 0.44 | `positive` | 0.75 | founder/owner | 174332 | 75 | yes | no | `Not Right Now` | template below |
| P062 | 388958 | unk | 3 | 26.36 | `positive` | 0.75 | marketing | 174803 | 5 | yes | no | `NOT INTERESTED` | hand-typed, withheld |
| P063 | 388958 | unk | 1 | 0.27 | `positive` | 0.75 | ops/delivery | 174822 | 4 | no | no | `NOT INTERESTED` | template below |
| P064 | 388958 | unk | 3 | 16.67 | `positive` | 0.75 | ops/delivery | 174892 | 14 | yes | yes | `BOOKED`, `Meeting Request` | template below |
| P065 | 388958 | unk | 1 | 0.1 | `positive` | 0.75 | ops/delivery | 174845 | 2 | no | no | `Not ICP`, `Interested` | template below |
| P066 | 388958 | unk | 1 | 4.76 | `positive` | 0.75 | ops/delivery | 175455 | 2 | no | no | `Information Request` | template below |
| P067 | 388958 | unk | 3 | 14.66 | `positive` | 0.75 | ops/delivery | 175455 | 60 | yes | yes | `Information Request` | none — reply to the request itself |
| P068 | 388958 | unk | 7 | 73.31 | `positive` | 0.75 | founder/owner | 175455 | 6 | no | no | `Not Right Now` | hand-typed, withheld |
| P069 | 388960 | unk | 0 | 0.0 | `positive` | 0.75 | founder/owner | 174742 | 71 | yes | no | `Not Right Now` | none — reply to the request itself |
| P070 | 388960 | unk | 1 | 1.56 | `positive` | 0.75 | founder/owner | 139699 | 81 | yes | no | `NOT INTERESTED` | template below |
| P071 | 388960 | unk | 6 | 24.81 | `positive` | 0.75 | c-suite other | 125748 | 7 | no | no | `BOOKED`, `Interested` | hand-typed, withheld |
| P072 | 388960 | unk | 11 | 26.83 | `positive` | 0.75 | c-suite other | 125748 | 23 | no | no | `BOOKED`, `Interested` | hand-typed, withheld |
| P073 | 406850 | unk | 1 | 0.0 | `positive` | 0.75 | founder/owner | 174797 | 18 | no | yes | `Sales Pitch` | hand-typed, withheld |
| P074 | 406850 | unk | 2 | 4.27 | `positive` | 0.75 | ops/delivery | 174742 | 2 | no | no | `FUP end 2026`, `Interested` | hand-typed, withheld |
| P075 | 406850 | unk | 1 | 2.03 | `positive` | 0.75 | ops/delivery | 174797 | 19 | no | yes | `Angry Response` | hand-typed, withheld |
| P076 | 428674 | unk | 5 | 1.58 | `positive` | 0.75 | ops/delivery | 174742 | 6 | no | no | `Interested` | hand-typed, withheld |
| P077 | 428674 | unk | 4 | 15.87 | `positive` | 0.75 | founder/owner | 174803 | 8 | yes | no | `BOOKED`, `Meeting Request` | hand-typed, withheld |
| P078 | 428674 | unk | 4 | 13.14 | `positive` | 0.75 | founder/owner | 174748 | 13 | no | yes | `BOOKED`, `Meeting Request` | hand-typed, withheld |
| P079 | 429679 | unk | 1 | 0.08 | `positive` | 0.75 | founder/owner | 181653 | 32 | yes | no | `NOT INTERESTED` | template below |
| P080 | 429679 | unk | 1 | 0.38 | `positive` | 0.75 | c-suite other | 116968 | 69 | yes | yes | `Wrong Person` | template below |
| P081 | 429679 | unk | 4 | 16.64 | `positive` | 0.75 | founder/owner | 174332 | 99 | yes | no | `Sales Pitch` | hand-typed, withheld |
| P082 | 429679 | unk | 1 | 2.56 | `positive` | 0.75 | ops/delivery | 174332 | 24 | no | no | `NOT INTERESTED` | template below |
| P083 | 429679 | unk | 1 | 7.04 | `positive` | 0.75 | founder/owner | 174810 | 22 | yes | no | `NOT INTERESTED` | template below |
| P084 | 429679 | unk | 2 | 6.27 | `positive` | 0.75 | ops/delivery | 174822 | 1 | no | no | `Not Right Now` | hand-typed, withheld |
| P085 | 429679 | unk | 4 | 74.54 | `positive` | 0.75 | ops/delivery | 174797 | 21 | yes | yes | `HOT LEAD`, `Information Request` | hand-typed, withheld |
| P086 | 429679 | unk | 5 | 75.63 | `positive` | 0.75 | ops/delivery | 174797 | 35 | yes | yes | `HOT LEAD`, `Information Request` | hand-typed, withheld |
| P087 | 429679 | unk | 5 | 62.12 | `positive` | 0.75 | founder/owner | 125775 | 2 | no | no | `HOT LEAD`, `Interested` | hand-typed, withheld |
| P088 | 429680 | unk | 3 | 0.29 | `positive` | 0.75 | marketing | 125748 | 1 | no | no | `NOT INTERESTED` | hand-typed, withheld |
| P089 | 467366 | unk | 1 | 0.0 | `positive` | 0.75 | founder/owner | 191848 | 3 | no | no | `NOT INTERESTED` | template below |
| P090 | 467366 | unk | 1 | 0.0 | `positive` | 0.75 | founder/owner | 175455 | 3 | no | no | `NOT INTERESTED` | template below |
| P091 | 467366 | unk | 1 | 0.0 | `positive` | 0.75 | c-suite other | 208253 | 3 | no | no | `NOT INTERESTED` | template below |
| P092 | 467366 | unk | 1 | 0.09 | `positive` | 0.75 | founder/owner | 174797 | 3 | no | no | `NOT INTERESTED` | template below |
| P093 | 467366 | unk | 0 | 0.0 | `positive` | 0.75 | founder/owner | 175552 | 67 | yes | no | `Not Right Now` | none — reply to the request itself |
| P094 | 467366 | unk | 4 | 14.99 | `positive` | 0.75 | other / unclassified | 174810 | 16 | no | no | `NOT INTERESTED` | hand-typed, withheld |
| P095 | 467366 | unk | 1 | 0.0 | `positive` | 0.75 | ceo/md | 169600 | 3 | no | no | `NOT INTERESTED` | template below |
| P096 | 467366 | unk | 4 | 22.67 | `positive` | 0.75 | ceo/md | 177751 | 11 | no | no | `NOT INTERESTED` | template below |
| P097 | 467366 | unk | 0 | 0.0 | `positive` | 0.75 | ceo/md | 177751 | 105 | yes | no | `Automated Response` | none — reply to the request itself |
| P098 | 467366 | unk | 1 | 0.02 | `positive` | 0.75 | founder/owner | 174797 | 3 | no | no | `NOT INTERESTED` | template below |
| P099 | 467366 | unk | 1 | 0.0 | `positive` | 0.75 | founder/owner | 175455 | 8 | yes | no | `Not Right Now` | template below |
| P100 | 467366 | unk | 2 | 7.71 | `positive` | 0.75 | founder/owner | 175455 | 92 | yes | no | `Not Right Now` | hand-typed, withheld |
| P101 | 467366 | unk | 4 | 67.14 | `positive` | 0.75 | ops/delivery | 129082 | 10 | no | no | `FUP end 2026`, `Interested` | hand-typed, withheld |
| P102 | 467366 | unk | 3 | 73.58 | `positive` | 0.75 | founder/owner | 116968 | 38 | yes | yes | `Sales Pitch` | hand-typed, withheld |
| P103 | 467366 | unk | 4 | 45.27 | `positive` | 0.75 | founder/owner | 174822 | 19 | yes | no | `NOT INTERESTED` | hand-typed, withheld |
| P104 | 467951 | unk | 1 | 0.21 | `positive` | 0.75 | ceo/md | 174748 | 5 | yes | no | `NOT INTERESTED` | hand-typed, withheld |
| P105 | 467951 | unk | 1 | 0.0 | `positive` | 0.75 | ceo/md | 174803 | 5 | yes | no | `NOT INTERESTED` | hand-typed, withheld |
| P106 | 467951 | unk | 3 | 6.81 | `positive` | 0.75 | engineering | 174748 | 4 | no | no | `NOT INTERESTED` | hand-typed, withheld |
| P107 | 467951 | unk | 1 | 0.05 | `positive` | 0.75 | c-suite other | 175455 | 8 | yes | no | `BOOKED`, `Interested` | hand-typed, withheld |
| P108 | 473854 | unk | 0 | 0.0 | `positive` | 0.75 | founder/owner | 179527 | 53 | yes | no | `Not Right Now` | none — reply to the request itself |
| P109 | 473854 | unk | 2 | 8.56 | `positive` | 0.75 | ceo/md | 119588 | 35 | yes | yes | `FUP end 2026`, `Meeting Request` | template below |
| P110 | 473854 | unk | 5 | 51.4 | `positive` | 0.75 | ops/delivery | 119588 | 2 | no | no | `NOT INTERESTED` | hand-typed, withheld |
| P111 | 523896 | unk | 1 | 0.0 | `positive` | 0.75 | founder/owner | 174822 | 28 | yes | no | `Wrong Person` | template below |
| P112 | 523896 | unk | 1 | 0.0 | `positive` | 0.75 | founder/owner | 208242 | 5 | yes | no | `NOT INTERESTED` | template below |
| P113 | 523896 | unk | 1 | 0.0 | `positive` | 0.75 | founder/owner | 208242 | 13 | yes | yes | `Information Request` | template below |
| P114 | 523922 | unk | 2 | 4.6 | `positive` | 0.75 | ops/delivery | 208253 | 2 | no | no | `Interested` | hand-typed, withheld |
| P115 | 523983 | unk | 1 | 0.0 | `positive` | 0.75 | other / unclassified | 174332 | 16 | yes | no | `Information Request` | hand-typed, withheld |
| P116 | 523983 | unk | 1 | 0.48 | `positive` | 0.75 | ops/delivery | 208253 | 15 | yes | yes | `NOT INTERESTED` | template below |
| P117 | 523983 | unk | 1 | 0.0 | `positive` | 0.75 | ops/delivery | 174845 | 1 | no | no | `NOT INTERESTED` | hand-typed, withheld |
| P118 | 523983 | unk | 1 | 0.92 | `positive` | 0.75 | ops/delivery | 125748 | 12 | yes | yes | `Wrong Person` | template below |
| P119 | 523983 | unk | 2 | 3.94 | `positive` | 0.75 | marketing | 179527 | 74 | yes | no | `Meeting Request` | template below |
| P120 | 523983 | unk | 2 | 2.16 | `positive` | 0.75 | ops/delivery | 174810 | 51 | yes | no | `Wrong Person` | template below |
| P121 | 523983 | unk | 2 | 8.8 | `positive` | 0.75 | ops/delivery | 116973 | 36 | yes | no | `NOT INTERESTED` | template below |
| P122 | 523983 | unk | 1 | 0.0 | `positive` | 0.75 | ops/delivery | 201959 | 43 | yes | yes | `Sales Pitch` | template below |
| P123 | 523983 | unk | 3 | 4.98 | `positive` | 0.75 | founder/owner | 174742 | 117 | yes | no | `HOT LEAD`, `Information Request` | hand-typed, withheld |
| P124 | 523983 | unk | 4 | 12.25 | `positive` | 0.75 | ops/delivery | 181658 | 20 | yes | no | `Referral` | hand-typed, withheld |
| P125 | 523983 | unk | 1 | 0.18 | `positive` | 0.75 | founder/owner | 201978 | 38 | yes | yes | `Information Request` | template below |
| P126 | 523983 | unk | 1 | 1.16 | `positive` | 0.75 | founder/owner | 208253 | 2 | no | no | `NOT INTERESTED` | template below |
| P127 | 523983 | unk | 1 | 0.61 | `positive` | 0.75 | other / unclassified | 116989 | 1 | no | no | `Not ICP`, `Interested` | hand-typed, withheld |
| P128 | 523983 | unk | 2 | 0.96 | `positive` | 0.75 | ceo/md | 181653 | 23 | no | no | `HOT LEAD`, `Meeting Request` | hand-typed, withheld |
| P129 | 523983 | unk | 2 | 3.24 | `positive` | 0.75 | ops/delivery | 212356 | 65 | yes | no | `Not ICP`, `Meeting Request` | template below |
| P130 | 523983 | unk | 4 | 10.4 | `positive` | 0.75 | ops/delivery | 181658 | 19 | no | no | `Wrong Person` | hand-typed, withheld |
| P131 | 523983 | unk | 3 | 3.91 | `positive` | 0.75 | founder/owner | 201978 | 2 | no | no | `Not Right Now` | hand-typed, withheld |
| P132 | 523983 | unk | 4 | 10.64 | `positive` | 0.75 | founder/owner | 116988 | 3 | no | no | `NOT INTERESTED` | hand-typed, withheld |
| P133 | 523983 | unk | 3 | 9.74 | `positive` | 0.75 | ops/delivery | 208253 | 13 | no | no | `NOT INTERESTED` | template below |
| P134 | 523983 | unk | 3 | 10.56 | `positive` | 0.75 | founder/owner | 169600 | 1 | no | no | `Not Right Now` | hand-typed, withheld |
| P135 | 523983 | unk | 2 | 0.41 | `positive` | 0.75 | ops/delivery | 208242 | 25 | no | no | `Information Request` | hand-typed, withheld |
| P136 | 523997 | unk | 1 | 0.02 | `positive` | 0.75 | ops/delivery | 181658 | 45 | yes | no | `Not ICP`, `Interested` | template below |
| P137 | 524000 | unk | 1 | 0.4 | `positive` | 0.75 | ops/delivery | 208242 | 24 | yes | no | `NOT INTERESTED` | hand-typed, withheld |
| P138 | 524000 | unk | 1 | 0.48 | `positive` | 0.75 | founder/owner | 174742 | 85 | yes | no | `Not Right Now` | hand-typed, withheld |
| P139 | 524002 | unk | 1 | 0.0 | `positive` | 0.75 | founder/owner | 174845 | 26 | yes | no | `NOT INTERESTED` | hand-typed, withheld |
| P140 | 524002 | unk | 2 | 3.54 | `positive` | 0.75 | founder/owner | 174742 | 102 | yes | no | `FUP end 2026`, `Meeting Request` | template below |
| P141 | 524002 | unk | 1 | 0.0 | `positive` | 0.75 | ceo/md | 174332 | 13 | no | no | `NOT INTERESTED` | hand-typed, withheld |
| P142 | 524002 | unk | 2 | 6.12 | `positive` | 0.75 | founder/owner | 143105 | 5 | no | no | `Not Right Now` | template below |
| P143 | 524002 | unk | 2 | 6.13 | `positive` | 0.75 | ceo/md | 119588 | 5 | no | no | `Not Right Now` | template below |
| P144 | 524002 | unk | 1 | 0.0 | `positive` | 0.75 | ops/delivery | 174845 | 36 | no | no | `Not ICP`, `Information Request` | hand-typed, withheld |
| P145 | 524002 | unk | 1 | 0.73 | `positive` | 0.75 | creative/design | 201978 | 77 | yes | no | `Sales Pitch` | template below |
| P146 | 524002 | unk | 1 | 0.17 | `positive` | 0.75 | ops/delivery | 159259 | 88 | yes | no | `Not ICP`, `Wrong Person` | template below |
| P147 | 524002 | unk | 1 | 0.03 | `positive` | 0.75 | founder/owner | 174742 | 55 | yes | yes | `Information Request` | hand-typed, withheld |
| P148 | 524002 | unk | 1 | 0.04 | `positive` | 0.75 | ops/delivery | 191848 | 44 | yes | no | `Interested` | template below |
| P149 | 524002 | unk | 1 | 0.1 | `positive` | 0.75 | ops/delivery | 174892 | 7 | no | no | `Meeting Request` | template below |
| P150 | 565193 | unk | 7 | 134.67 | `positive` | 0.75 | founder/owner | 174892 | 1 | no | no | `HOT LEAD`, `Interested` | template below |
| P151 | 565195 | unk | 4 | 74.54 | `positive` | 0.75 | ops/delivery | 174797 | 21 | yes | yes | `HOT LEAD`, `Information Request` | template below |
| P152 | 565195 | unk | 5 | 75.63 | `positive` | 0.75 | ops/delivery | 174797 | 35 | yes | yes | `HOT LEAD`, `Information Request` | hand-typed, withheld |
| P153 | 565211 | unk | 6 | 58.42 | `positive` | 0.75 | sales/bd | 175455 | 32 | yes | no | `HOT LEAD`, `Not ICP`, `Meeting Request` | template below |
| P154 | 565211 | unk | 7 | 73.31 | `positive` | 0.75 | founder/owner | 175455 | 6 | no | no | `Not Right Now` | template below |
| P155 | 565223 | unk | 4 | 45.27 | `positive` | 0.75 | founder/owner | 174822 | 19 | yes | no | `NOT INTERESTED` | template below |
| P156 | 565765 | unk | 1 | 2.85 | `positive` | 0.75 | ceo/md | 174822 | 26 | yes | yes | `Not Right Now` | hand-typed, withheld |
| P157 | 565765 | unk | 1 | 1.15 | `positive` | 0.75 | c-suite other | 208242 | 11 | yes | no | `HOT LEAD`, `Interested` | hand-typed, withheld |
| P158 | 565765 | unk | 3 | 10.02 | `positive` | 0.75 | founder/owner | 174892 | 2 | no | no | `NOT INTERESTED` | template below |
| P159 | 565765 | unk | 3 | 10.06 | `positive` | 0.75 | ceo/md | 181658 | 22 | yes | no | `NOT INTERESTED` | template below |
| P160 | 567698 | unk | 5 | 62.12 | `positive` | 0.75 | founder/owner | 125775 | 2 | no | no | `HOT LEAD`, `Interested` | template below |
| P161 | 567708 | unk | 2 | 30.33 | `positive` | 0.75 | sales/bd | 116973 | 29 | yes | no | `Not ICP`, `Wrong Person` | template below |
| P162 | 567747 | unk | 5 | 51.4 | `positive` | 0.75 | ops/delivery | 119588 | 2 | no | no | `NOT INTERESTED` | hand-typed, withheld |
| P163 | 613744 | OS | 1 | 0.05 | `positive` | 0.75 | marketing | 174892 | 3 | no | no | `Interested` | template below |
| P164 | 620829 | OS | 1 | 0.05 | `positive` | 0.75 | marketing | 174892 | 3 | no | no | `Interested` | template below |
| P165 | 384897 | unk | 2 | 134.7 | `question` | 0.75 | founder/owner | 174332 | 3 | no | yes | `Referral` | hand-typed, withheld |
| P166 | 388939 | unk | 1 | 0.0 | `question` | 0.75 | ceo/md | 174822 | 14 | yes | yes | `NOT INTERESTED` | template below |
| P167 | 388939 | unk | 1 | 0.01 | `question` | 0.75 | founder/owner | 174332 | 12 | yes | yes | `Maybe baby` | template below |
| P168 | 388939 | unk | 3 | 6.37 | `question` | 0.75 | founder/owner | 174803 | 6 | no | yes | `NOT INTERESTED` | template below |
| P169 | 388939 | unk | 1 | 0.0 | `question` | 0.75 | founder/owner | 174742 | 10 | yes | yes | `Interested` | template below |
| P170 | 388939 | unk | 1 | 0.0 | `question` | 0.75 | ops/delivery | 174845 | 21 | yes | yes | `Not ICP` | template below |
| P171 | 388942 | unk | 2 | 8.79 | `question` | 0.75 | engineering | 174822 | 5 | no | yes | `Information Request` | template below |
| P172 | 388942 | unk | 1 | 0.0 | `question` | 0.75 | ops/delivery | 174332 | 21 | yes | yes | `Information Request` | template below |
| P173 | 388949 | unk | 1 | 0.0 | `question` | 0.75 | marketing | 174822 | 16 | yes | yes | `Maybe baby`, `Information Request` | hand-typed, withheld |
| P174 | 388949 | unk | 1 | 0.08 | `question` | 0.75 | founder/owner | 174332 | 22 | yes | yes | `Not ICP` | hand-typed, withheld |
| P175 | 388949 | unk | 0 | 0.0 | `question` | 0.75 | founder/owner | 174332 | 7 | yes | yes | `Interested` | none — reply to the request itself |
| P176 | 388949 | unk | 0 | 0.0 | `question` | 0.75 | founder/owner | 174742 | 64 | yes | yes | `Maybe baby` | none — reply to the request itself |
| P177 | 388951 | unk | 0 | 0.0 | `question` | 0.75 | ceo/md | 174822 | 13 | no | yes | `Not Right Now` | none — reply to the request itself |
| P178 | 388951 | unk | 1 | 1.03 | `question` | 0.75 | c-suite other | 174822 | 9 | yes | yes | `No longer in company` | template below |
| P179 | 388953 | unk | 1 | 0.02 | `question` | 0.75 | ops/delivery | 174797 | 36 | yes | no | `NOT INTERESTED` | template below |
| P180 | 388955 | unk | 1 | 0.82 | `question` | 0.75 | ops/delivery | 174803 | 11 | yes | yes | `NOT INTERESTED` | template below |
| P181 | 388955 | unk | 1 | 2.54 | `question` | 0.75 | ceo/md | 139699 | 3 | no | yes | `Interested` | template below |
| P182 | 388955 | unk | 2 | 12.44 | `question` | 0.75 | founder/owner | 208253 | 100 | yes | yes | `Automated Response` | template below |
| P183 | 388958 | unk | 1 | 0.0 | `question` | 0.75 | director/head | 174797 | 39 | yes | yes | `No longer in company` | hand-typed, withheld |
| P184 | 388958 | unk | 3 | 7.2 | `question` | 0.75 | marketing | 174742 | 18 | no | no | `Wrong Person` | template below |
| P185 | 388958 | unk | 2 | 32.87 | `question` | 0.75 | c-suite other | 174797 | 18 | yes | no | `NOT INTERESTED` | template below |
| P186 | 388958 | unk | 10 | 55.06 | `question` | 0.75 | ops/delivery | 174892 | 25 | yes | yes | `BOOKED`, `Meeting Request` | hand-typed, withheld |
| P187 | 388960 | unk | 2 | 6.48 | `question` | 0.75 | ceo/md | 174845 | 4 | no | yes | `Referral` | template below |
| P188 | 406850 | unk | 1 | 4.45 | `question` | 0.75 | c-suite other | 174797 | 67 | yes | yes | `Not ICP` | hand-typed, withheld |
| P189 | 428674 | unk | 1 | 1.6 | `question` | 0.75 | ceo/md | 174742 | 6 | no | yes | `Interested` | template below |
| P190 | 428674 | unk | 0 | 0.0 | `question` | 0.75 | c-suite other | 174845 | 10 | no | yes | `Add to Blocklist` | none — reply to the request itself |
| P191 | 428674 | unk | 1 | 0.35 | `question` | 0.75 | ops/delivery | 174332 | 8 | yes | yes | `NOT INTERESTED` | template below |
| P192 | 428674 | unk | 1 | 0.12 | `question` | 0.75 | ops/delivery | 174332 | 5 | no | yes | `NOT INTERESTED` | template below |
| P193 | 428674 | unk | 2 | 0.71 | `question` | 0.75 | ops/delivery | 174810 | 4 | no | yes | `NOT INTERESTED` | hand-typed, withheld |
| P194 | 428674 | unk | 4 | 0.97 | `question` | 0.75 | ops/delivery | 174892 | 23 | no | yes | `NOT INTERESTED` | hand-typed, withheld |
| P195 | 428674 | unk | 1 | 0.11 | `question` | 0.75 | ops/delivery | 174845 | 32 | no | yes | `Information Request` | template below |
| P196 | 428674 | unk | 1 | 0.0 | `question` | 0.75 | founder/owner | 174748 | 5 | no | yes | `BOOKED`, `Meeting Request` | template below |
| P197 | 428674 | unk | 2 | 29.23 | `question` | 0.75 | founder/owner | 174332 | 70 | yes | yes | `Sales Pitch` | hand-typed, withheld |
| P198 | 429679 | unk | 2 | 0.28 | `question` | 0.75 | ceo/md | 119588 | 6 | no | yes | `NOT INTERESTED` | hand-typed, withheld |
| P199 | 429679 | unk | 0 | 0.0 | `question` | 0.75 | founder/owner | 125775 | 10 | yes | yes | `Sales Pitch` | none — reply to the request itself |
| P200 | 429679 | unk | 3 | 44.57 | `question` | 0.75 | founder/owner | 169600 | 100 | yes | yes | `Automated Response` | template below |
| P201 | 429679 | unk | 4 | 62.72 | `question` | 0.75 | ceo/md | 191848 | 18 | no | yes | `Not ICP`, `Information Request` | hand-typed, withheld |
| P202 | 429680 | unk | 1 | 0.22 | `question` | 0.75 | ceo/md | 181658 | 8 | yes | yes | `Information Request` | template below |
| P203 | 429680 | unk | 2 | 3.24 | `question` | 0.75 | founder/owner | 208253 | 55 | no | yes | `Interested` | template below |
| P204 | 467366 | unk | 1 | 3.03 | `question` | 0.75 | ceo/md | 125775 | 36 | yes | yes | `Not Right Now` | template below |
| P205 | 467366 | unk | 1 | 0.0 | `question` | 0.75 | founder/owner | 116968 | 5 | no | yes | `Sales Pitch` | template below |
| P206 | 467366 | unk | 1 | 0.0 | `question` | 0.75 | ops/delivery | 116988 | 9 | yes | yes | `NOT INTERESTED` | template below |
| P207 | 467366 | unk | 2 | 0.65 | `question` | 0.75 | marketing | 174797 | 14 | no | yes | `NOT INTERESTED` | hand-typed, withheld |
| P208 | 467366 | unk | 2 | 3.29 | `question` | 0.75 | marketing | 129082 | 17 | no | yes | `Sales Pitch` | template below |
| P209 | 467366 | unk | 1 | 4.33 | `question` | 0.75 | marketing | 116973 | 26 | yes | yes | `HOT LEAD`, `Information Request` | template below |
| P210 | 467366 | unk | 2 | 14.91 | `question` | 0.75 | ceo/md | 129082 | 13 | yes | yes | `NOT INTERESTED` | template below |
| P211 | 467366 | unk | 0 | 0.0 | `question` | 0.75 | ceo/md | 181658 | 4 | no | yes | `Information Request` | none — reply to the request itself |
| P212 | 467951 | unk | 1 | 0.02 | `question` | 0.75 | ops/delivery | 174797 | 36 | yes | no | `NOT INTERESTED` | hand-typed, withheld |
| P213 | 473854 | unk | 1 | 0.31 | `question` | 0.75 | c-suite other | 156360 | 43 | yes | yes | `Information Request` | template below |
| P214 | 523983 | unk | 1 | 0.03 | `question` | 0.75 | marketing | 191848 | 5 | no | yes | `Information Request` | template below |
| P215 | 523983 | unk | 1 | 0.03 | `question` | 0.75 | marketing | 191848 | 6 | no | yes | `Information Request` | template below |
| P216 | 523983 | unk | 0 | 0.0 | `question` | 0.75 | other / unclassified | 181658 | 23 | yes | no | `NOT INTERESTED` | none — reply to the request itself |
| P217 | 523983 | unk | 4 | 5.02 | `question` | 0.75 | ceo/md | 174822 | 24 | no | yes | `Information Request` | hand-typed, withheld |
| P218 | 523983 | unk | 2 | 2.45 | `question` | 0.75 | founder/owner | 174742 | 53 | yes | yes | `HOT LEAD`, `Information Request` | template below |
| P219 | 523983 | unk | 2 | 3.05 | `question` | 0.75 | founder/owner | 208242 | 25 | yes | yes | `Not Right Now` | template below |
| P220 | 523983 | unk | 2 | 5.28 | `question` | 0.75 | founder/owner | 191848 | 5 | yes | yes | `Information Request` | template below |
| P221 | 523983 | unk | 1 | 0.0 | `question` | 0.75 | founder/owner | 169600 | 10 | no | yes | `Not ICP`, `Information Request` | template below |
| P222 | 523983 | unk | 1 | 0.06 | `question` | 0.75 | founder/owner | 159259 | 7 | yes | yes | `NOT INTERESTED` | template below |
| P223 | 523983 | unk | 0 | 0.0 | `question` | 0.75 | other / unclassified | 116989 | 8 | no | yes | `Not ICP`, `Interested` | none — reply to the request itself |
| P224 | 523983 | unk | 2 | 7.56 | `question` | 0.75 | ceo/md | 174822 | 7 | no | yes | `Not ICP`, `Interested` | template below |
| P225 | 523983 | unk | 1 | 0.51 | `question` | 0.75 | ceo/md | 174332 | 6 | no | yes | `Maybe baby`, `Information Request` | template below |
| P226 | 523983 | unk | 1 | 0.58 | `question` | 0.75 | founder/owner | 129082 | 16 | yes | yes | `Maybe baby`, `Not ICP`, `Information Request` | template below |
| P227 | 523983 | unk | 1 | 1.73 | `question` | 0.75 | ceo/md | 129082 | 13 | yes | yes | `Maybe baby`, `Information Request` | template below |
| P228 | 523983 | unk | 2 | 3.58 | `question` | 0.75 | founder/owner | 169600 | 7 | no | yes | `Information Request` | template below |
| P229 | 523983 | unk | 2 | 6.36 | `question` | 0.75 | founder/owner | 125748 | 18 | yes | yes | `NOT INTERESTED` | template below |
| P230 | 523983 | unk | 3 | 18.28 | `question` | 0.75 | ceo/md | 191848 | 5 | yes | yes | `Information Request` | template below |
| P231 | 523983 | unk | 2 | 3.46 | `question` | 0.75 | ops/delivery | 174742 | 38 | no | yes | `Information Request` | template below |
| P232 | 523983 | unk | 2 | 3.61 | `question` | 0.75 | finance | 116968 | 22 | yes | yes | `Information Request` | template below |
| P233 | 523983 | unk | 0 | 0.0 | `question` | 0.75 | ceo/md | 174332 | 67 | yes | no | `Sales Pitch` | none — reply to the request itself |
| P234 | 523983 | unk | 1 | 0.02 | `question` | 0.75 | ceo/md | 116968 | 15 | yes | yes | `Information Request` | template below |
| P235 | 523983 | unk | 1 | 0.0 | `question` | 0.75 | marketing | 174742 | 20 | yes | yes | `Information Request` | template below |
| P236 | 524000 | unk | 1 | 0.0 | `question` | 0.75 | sales/bd | 174892 | 14 | no | yes | `NOT INTERESTED` | hand-typed, withheld |
| P237 | 524000 | unk | 1 | 0.54 | `question` | 0.75 | founder/owner | 175455 | 15 | no | yes | `NOT INTERESTED` | hand-typed, withheld |
| P238 | 524002 | unk | 1 | 0.0 | `question` | 0.75 | founder/owner | 174803 | 49 | yes | yes | `Information Request` | hand-typed, withheld |
| P239 | 524002 | unk | 1 | 0.26 | `question` | 0.75 | founder/owner | 174803 | 61 | yes | yes | `Information Request` | hand-typed, withheld |
| P240 | 524002 | unk | 1 | 0.0 | `question` | 0.75 | ceo/md | 175455 | 10 | no | yes | `Not ICP`, `Interested` | hand-typed, withheld |
| P241 | 524002 | unk | 1 | 0.01 | `question` | 0.75 | c-suite other | 175552 | 3 | no | yes | `NOT INTERESTED` | template below |
| P242 | 524002 | unk | 1 | 0.0 | `question` | 0.75 | ceo/md | 174810 | 9 | no | yes | `Not ICP`, `Interested` | hand-typed, withheld |
| P243 | 524002 | unk | 0 | 0.0 | `question` | 0.75 | founder/owner | 175552 | 27 | yes | yes | `NOT INTERESTED` | none — reply to the request itself |
| P244 | 524002 | unk | 6 | 22.46 | `question` | 0.75 | founder/owner | 174803 | 10 | yes | yes | `Not ICP`, `Information Request` | template below |
| P245 | 562830 | unk | 2 | 134.7 | `question` | 0.75 | founder/owner | 174332 | 3 | no | yes | `Referral` | template below |
| P246 | 565195 | unk | 2 | 32.87 | `question` | 0.75 | c-suite other | 174797 | 18 | yes | no | `NOT INTERESTED` | hand-typed, withheld |
| P247 | 567689 | unk | 4 | 62.72 | `question` | 0.75 | ceo/md | 191848 | 18 | no | yes | `Not ICP`, `Information Request` | template below |

#### The distinct templates that preceded a positive, each in full, with the count

51 distinct templates account for the 132 rows above that matched one.

**T01 — 20 positive replies; campaign/step pairs 388939/1, 388953/1, 523896/1; 124 chars, 22 words**

```
Hi, found your profile while exploring agency businesses in the area. Would love to connect and see what you are working on.
```

**T02 — 10 positive replies; campaign/step pairs 388939/2, 388949/1, 388949/2, 388958/1, 388958/2; 322 chars, 52 words**

```
Hi, appreciate the add.

I work with agencies on the ops and profitability side, specifically helping teams replace their disconnected tool stack with one platform that ties together projects, time tracking, budgets and invoicing.

Happy to share more if it is ever relevant to your setup. Good to be connected either way.
```

**T03 — 10 positive replies; campaign/step pairs 467366/1; 19 chars, 3 words**

```
Hey, let's connect!
```

**T04 — 10 positive replies; campaign/step pairs 429680/1, 523983/1, 523983/2; 125 chars, 24 words**

```
Hi {FIRST_NAME}, following up.

I think your team's a strong fit for what we do.

Happy to show you.

Let me know either way.
```

**T05 — 7 positive replies; campaign/step pairs 428674/1, 467366/1, 467366/2, 523997/1; 125 chars, 22 words**

```
hey, do you guys have project management, resourcing and finances in one place or is it spread across like 4 different tools?
```

**T06 — 6 positive replies; campaign/step pairs 388942/1, 388951/1, 388955/1; 453 chars, 81 words**

```
Hey, a colleague of mine probably reached out recently about Productive. I wanted to follow up from my side because your agency looks like a strong fit for what we do, and I did not want it to get lost.

The short version is that Productive is an agency management platform that connects project management, time tracking, budgets, and invoicing so everything talks to each other. Happy to give you a fresh perspective on it if the timing is better now.
```

**T07 — 5 positive replies; campaign/step pairs 388939/3, 388949/2, 388949/3, 388958/2, 388958/3; 323 chars, 56 words**

```
Hey {FIRST_NAME}, wanted to ask you something directly.

How does {COMPANY} know if a project is going to hit its margin before it is finished? Is that something you can see at any point or does it only become clear after the fact?

Genuinely curious because the answer changes what I would share with you.

{MY_FIRST_NAME}
```

**T08 — 4 positive replies; campaign/step pairs 523983/2; 169 chars, 26 words**

```
{FIRST_NAME}, just checking in, is this landing with the wrong person? happy to connect with whoever handles ops or tooling at {COMPANY} if thats easier, {MY_FIRST_NAME}
```

**T09 — 4 positive replies; campaign/step pairs 523983/1; 124 chars, 22 words**

```
Hi {FIRST_NAME}, won't keep chasing.

I genuinely think {COMPANY} is a fit.

If I'm wrong, tell me and I'll back off.

Fair?
```

**T10 — 3 positive replies; campaign/step pairs 523983/1; 145 chars, 23 words**

```
Hi {FIRST_NAME}, following up.

Curious if project profitability visibility is even a priority right now.

Only reaching out because I see a fit.
```

**T11 — 3 positive replies; campaign/step pairs 467366/2, 523983/2; 174 chars, 30 words**

```
hey {FIRST_NAME}! bumping this up, is now just a bad time or is operational tooling not really a priority at {COMPANY} right now? either way just let me know, {MY_FIRST_NAME}
```

**T12 — 3 positive replies; campaign/step pairs 562830/2, 565195/4, 567689/4; 351 chars, 61 words**

```
Hi {FIRST_NAME}, we've been connected but never actually chatted. I'll be direct about why I'm reaching out. Productive is a platform I think makes sense for {COMPANY}, and I'd love to show you what it does in 20 minutes. And because I know calendars are packed, there's no pitch deck involved, just a straight look at whether it's useful. Sound fair?
```

**T13 — 2 positive replies; campaign/step pairs 388955/2, 388960/2; 297 chars, 52 words**

```
Hey {FIRST_NAME}, just circling back.

I will be straight with you. Between my colleague and I we have both reached out now and I think {COMPANY} is genuinely worth a conversation rather than just another follow up. What would make it worth 15 minutes of your time to take a look?

{MY_FIRST_NAME}
```

**T14 — 2 positive replies; campaign/step pairs 523983/2; 184 chars, 30 words**

```
hey {FIRST_NAME}, following up on my last message. not trying to be annoying, genuinely curious if operational visibility is something {COMPANY} has sorted or if its still a pain point
```

**T15 — 2 positive replies; campaign/step pairs 524002/1, 524002/2; 375 chars, 58 words**

```
here's the actual hook {FIRST_NAME}. most agencies don't have a margin problem, they have a visibility problem, the data's just scattered across too many tools to see clearly. 
Productive consolidates it so profitability is obvious, live, per project. would seeing that in one place actually change how you run things at {COMPANY}, or are you already there? 

{MY_FIRST_NAME}
```

**T16 — 2 positive replies; campaign/step pairs 524002/1; 381 chars, 54 words**

```
told you i'd eventually say something useful {FIRST_NAME}, so here it is. the agencies i work with kept losing time to manual reporting and billable hours slipping through cracks. 

Productive ties projects, resourcing and finances together so that stops happening. genuinely curious what your biggest time-sink is at {COMPANY}, reporting, billing, or resourcing?

 {MY_FIRST_NAME}
```

**T17 — 2 positive replies; campaign/step pairs 565211/6, 565211/7; 77 chars, 14 words**

```
Yes to 20 minutes at some point, {FIRST_NAME}, or should I stop reaching out?
```

**T18 — 2 positive replies; campaign/step pairs 613744/1, 620829/1; 256 chars, 44 words**

```
Hey, we built Productive so budgets, time tracking and resourcing actually talk to each other, so you can see if a project's making money while it's still running, not just after it gets invoiced.
 
Can show you what that looks like if you're interested.

```

**T19 — 2 positive replies; campaign/step pairs 388942/2, 388955/2; 247 chars, 49 words**

```
Hey, just following up on my last message.

Rather than repeat the pitch I wanted to ask directly. What would need to be true about a tool for it to be worth 15 minutes of your time right now? Happy to tell you whether Productive fits that or not.
```

**T20 — 2 positive replies; campaign/step pairs 523983/2; 170 chars, 28 words**

```
{FIRST_NAME} following up, i know its probably not top of mind but curious, how are you guys currently handling resource planning, got something or still figuring it out?
```

**T21 — 1 positive replies; campaign/step pairs 388939/1; 173 chars, 23 words**

```
Hi {FIRST_NAME}, found {COMPANY} while browsing {INDUSTRY} businesses in {LOCATION}. Always good to connect with people doing interesting work in the space.

{MY_FIRST_NAME}
```

**T22 — 1 positive replies; campaign/step pairs 388942/4; 469 chars, 77 words**

```
Hey {FIRST_NAME}, last proper pitch from me before I wrap up.

Three things Productive does that most agency tools do not. Time tracked connects directly to budget burn so you see profit impact as work happens. Resource planning shows utilization across the whole team in real time. Invoicing pulls from actual project data so there is no manual assembly.

If {COMPANY} is doing any of those things manually right now that is the gap Productive closes.

{MY_FIRST_NAME}
```

**T23 — 1 positive replies; campaign/step pairs 388955/2; 328 chars, 52 words**

```
Hey {FIRST_NAME}, following up on my last note.

Quick question about {COMPANY}. How does your team currently know whether you are fully utilizing your people across projects? Not a trick question, I am asking because that visibility gap is exactly what most {INDUSTRY} agencies I work with are trying to close.

{MY_FIRST_NAME}
```

**T24 — 1 positive replies; campaign/step pairs 388958/3; 442 chars, 75 words**

```
Hey, wanted to share what I actually work with.

The tool is called Productive. It is an agency management platform that connects project management, time tracking, budgets and invoicing in one place so the data updates automatically rather than sitting in separate tools. Most agency owners and ops leads use it to get a live view of margin and utilization without manual reporting.

Worth a 15-minute call if you want to see how it works?

```

**T25 — 1 positive replies; campaign/step pairs 388960/1; 357 chars, 58 words**

```
So... here's the actual hook. 

Most agencies don't have a margin problem; they have a visibility problem, the data's just scattered across too many tools to see clearly. 

Productive consolidates it so profitability is obvious, live, per project. would seeing that in one place actually change how you run things at your company, or are you already there? 
```

**T26 — 1 positive replies; campaign/step pairs 429679/1; 550 chars, 90 words**

```
Hi {FIRST_NAME}, thanks for the add.

I'm a sales rep at Productive, where we help agencies see project profitability while work is still live, not weeks after invoicing. Everything sits in one platform: projects, resourcing, time, budgets and billing.

Most leaders we speak to are stuck with no real time margin view, billable hours lost to manual tracking, and a stack of tools that don't connect.

If that's true for {COMPANY}, a quick call gets your whole team a free premium trial.

How are you tracking profitability right now? {MY_FIRST_NAME}
```

**T27 — 1 positive replies; campaign/step pairs 429679/1; 364 chars, 59 words**

```
Hi {FIRST_NAME}, good to connect. Quick context, I'm a sales rep at Productive. 

How are you managing agency ops at {COMPANY} right now, solid system or still stitching things together? 

I ask because if you're stuck with gut feel forecasting, no live view of margin per project, or three to five disconnected tools, that's exactly what we fix. 

{MY_FIRST_NAME}
```

**T28 — 1 positive replies; campaign/step pairs 429679/1; 522 chars, 87 words**

```
Hi {FIRST_NAME}, appreciate the connection.

I'm in sales at Productive. We replace the usual pile of agency tools with one platform that ties projects, resourcing, budgets and invoicing together.

Teams come to us when they're running four or five tools that don't sync, can't get a clean profitability number, and keep losing billable hours in the gaps.

If that sounds familiar at {COMPANY}, one short call and I'll set the whole team up on a free premium trial.

Is that close to how you operate today? {MY_FIRST_NAME}
```

**T29 — 1 positive replies; campaign/step pairs 429679/1; 539 chars, 88 words**

```
Hi, thanks for connecting.

I'm a sales rep at Productive, the platform that brings project management, resourcing, time tracking, budgets and invoicing into one place for agencies.

We mostly help teams who lose billable hours to manual timesheets, can't see project profitability in real time, and are juggling four or five disconnected tools.

If any of that sounds familiar, one brief call and we'll set your whole team up with a free premium trial.

How are you managing ops right now, solid system or still stitching things together?
```

**T30 — 1 positive replies; campaign/step pairs 467366/4; 96 chars, 15 words**

```
{FIRST_NAME}, still think there could be something here for {COMPANY}. wdyt, worth a quick call?
```

**T31 — 1 positive replies; campaign/step pairs 473854/2; 343 chars, 55 words**

```
Hi {FIRST_NAME}, last one from me so I'm not cluttering your inbox.

If the disconnected tools, hidden profitability and lost billable hours stuff ever becomes a priority at {COMPANY}, the door's open and the free team trial offer stands.

Just say the word and we'll grab 20 minutes. Otherwise, genuinely good to be connected. {MY_FIRST_NAME}
```

**T32 — 1 positive replies; campaign/step pairs 523983/3; 96 chars, 18 words**

```
hey {FIRST_NAME}! just lmk if this isnt relevant and ill get out of your inbox, no hard feelings
```

**T33 — 1 positive replies; campaign/step pairs 524002/2; 197 chars, 33 words**

```
hey {FIRST_NAME}, a week of silence, which is either "not interested" or "saw it, got distracted by actual work." totally fine if it's the first. if it's the second, i'm still here. {MY_FIRST_NAME}
```

**T34 — 1 positive replies; campaign/step pairs 524002/2; 180 chars, 31 words**

```
hey {FIRST_NAME}, no guilt-trip here, i know exactly how fast a message gets buried. just floating this back up before i let it go. one word reply works, even "no." {MY_FIRST_NAME}
```

**T35 — 1 positive replies; campaign/step pairs 524002/1; 370 chars, 55 words**

```
thanks for accepting {FIRST_NAME}, now i'll earn the connection. 

the usual agency pain is utilization, you don't really know who's overloaded and who's idle until something breaks. 

Productive gives you that view live, alongside budgets and billing in one place. what's your current setup for tracking it at {COMPANY}, a tool, spreadsheets, or vibes?
 {MY_FIRST_NAME}
```

**T36 — 1 positive replies; campaign/step pairs 524002/1; 363 chars, 56 words**

```
okay {FIRST_NAME}, cards on the table. Productive is one platform for agencies that runs projects, time tracking, budgets and invoicing together, so you get live profitability instead of a month-end guessing game. {COMPANY} looked like the kind of team it fits. before i assume anything though, what's the most annoying part of your current stack? {MY_FIRST_NAME}
```

**T37 — 1 positive replies; campaign/step pairs 565193/7; 337 chars, 59 words**

```
Hi {FIRST_NAME}, we've been connected a while but never actually talked. I'll be direct about why I'm reaching out, I'm on the team at Productive, we help agencies get a live view of project profitability instead of finding out after the invoice's gone out. Think it's relevant for what you do at {COMPANY}. Worth 20 minutes to show you?
```

**T38 — 1 positive replies; campaign/step pairs 565223/4; 75 chars, 16 words**

```
Should I take this as a no for now, {FIRST_NAME}, or keep it on your radar?
```

**T39 — 1 positive replies; campaign/step pairs 565765/3; 59 chars, 10 words**

```
Is this worth pursuing or should I stop here, {FIRST_NAME}?
```

**T40 — 1 positive replies; campaign/step pairs 565765/3; 84 chars, 17 words**

```
{FIRST_NAME}, should I drop this or send you an overview if you want to take a look?
```

**T41 — 1 positive replies; campaign/step pairs 567698/5; 309 chars, 54 words**

```
{FIRST_NAME}, not sure my last message actually landed, so trying again. No pressure either way on the 20 minutes. The actual value is Productive connecting your project data to the financial side, so your team stops piecing it together after the fact and just sees it live. 

Would you like me to share more?
```

**T42 — 1 positive replies; campaign/step pairs 567708/2; 315 chars, 56 words**

```
Hi, we've been connected a while but never actually talked. 

I'll be direct about why I'm reaching out, I'm on the team at Productive, we help agencies get a live view of project profitability instead of finding out after the invoice's gone out. Think it's relevant for what you do. 

Worth 20 minutes to show you?
```

**T43 — 1 positive replies; campaign/step pairs 388939/1; 173 chars, 26 words**

```
Hi {FIRST_NAME}, saw {COMPANY} pop up while looking at {INDUSTRY} agencies in {LOCATION}. Looks like interesting work, would love to have you in my network.

{MY_FIRST_NAME}
```

**T44 — 1 positive replies; campaign/step pairs 388942/1; 429 chars, 74 words**

```
Hey {FIRST_NAME}, you may have already heard from someone on my team about Productive. I am reaching out separately because I look at the {INDUSTRY} space in {LOCATION} specifically and {COMPANY} keeps coming up as a business that would get a lot out of the platform.

Happy to give you a different perspective on it if the first message did not land at the right time. Sometimes it just takes the right framing.

{MY_FIRST_NAME}
```

**T45 — 1 positive replies; campaign/step pairs 388955/1; 429 chars, 74 words**

```
Hey {FIRST_NAME}, one of my colleagues reached out to you about Productive recently. I am following up because I wanted to make this feel less like a blast and more like a real conversation.

I spend most of my time working with {POSITION}s at {INDUSTRY} agencies and the problems I hear consistently are the same ones Productive was built to solve. Thought it was worth one more shot before leaving it with you.

{MY_FIRST_NAME}
```

**T46 — 1 positive replies; campaign/step pairs 428674/1; 186 chars, 32 words**

```
{FIRST_NAME} hi! as {POSITION} at a {INDUSTRY} agency curious if you have clear visibility on team capacity at any given time or if thats always a bit of a guessing game, {MY_FIRST_NAME}
```

**T47 — 1 positive replies; campaign/step pairs 429679/3; 189 chars, 33 words**

```
Hey {FIRST_NAME}, still relevant or just bad timing?

If now's not it, tell me when to circle back and I'll get out of your inbox.

The free team trial isn't going anywhere. {MY_FIRST_NAME}
```

**T48 — 1 positive replies; campaign/step pairs 429680/2; 191 chars, 32 words**

```
hey {FIRST_NAME}, just circling back. not asking for a demo or anything, just curious, is agency ops something that feels under control at {COMPANY} right now or more of an ongoing challenge?
```

**T49 — 1 positive replies; campaign/step pairs 473854/1; 276 chars, 44 words**

```
Hi {FIRST_NAME}, thanks for the add. I'm a sales rep at Productive. If at {COMPANY} you're battling lost billable hours, no real time profitability, and too many disconnected tools, we bring all of it into one platform. 

How's your current setup holding up? 

{MY_FIRST_NAME}
```

**T50 — 1 positive replies; campaign/step pairs 523983/3; 140 chars, 23 words**

```
{FIRST_NAME}, i'll leave it here. if the timing ever feels right for a chat about how {COMPANY} manages agency ops just lmk, {MY_FIRST_NAME}
```

**T51 — 1 positive replies; campaign/step pairs 524002/6; 305 chars, 60 words**

```
Hey, last message from me on this.

My colleague and I have both reached out now and I do not want to keep taking up space in your inbox. If the timing is ever right, Productive has a free trial at productive.io and you do not need to speak to anyone to get started.

Thanks for bearing with the outreach.
```

---

## 9. Meetings are recorded nowhere, and here is where they should be

**Measured, not inferred.**

- **The provider has no meeting field.** `overallStats` returns 22 numeric keys
  and they are: `profileViews`, `postLikes`, `follows`, `messagesSent`,
  `totalMessageStarted`, `totalMessageReplies`, `voiceNoteConversations`,
  `repliedToVoiceNotes`, `voiceNotesSent`, `inmailMessagesSent`,
  `totalInmailStarted`, `totalInmailReplies`, `connectionsSent`,
  `connectionsAccepted`, `uniqueLeadsContacted`, `autoTaggedInterested`,
  `totalAutoTagged`, plus five `…Rate` floats. None is a meeting, a booking, a
  call or a demo.
- **This repository has the event and nothing writes it.** `src/events.py`
  defines `MEETING_MARKED`; `src/outcomes.py:216 _meeting()` reads
  `rec.events` for it; `outcomes.funnel` reports a `MEETINGS` stage from it and
  its own note says *"nothing observes a booking; a person marks it"*
  (`src/outcomes.py:893`, `observable=False`).
- **Across all 1,584 records in `work/queue.jsonl` there are
  ZERO `meeting_marked` events.** 42 event types are present — 3,563
  `draft_approved`, 2,760 `enrichment_completed`, 29 `reply_received`, 2
  `positive_reply_detected` — and `meeting_marked` is not among them.
- So the count of LinkedIn meetings this system can evidence is **0**, and that
  is a statement about the ledger, not about the business.

**Where a meeting SHOULD be recorded, in order of authority:**

1. **`rec.events` with `events.MEETING_MARKED`, on the queue record of the
   contact**, carrying `contact`, `at`, the channel and the campaign id. That is
   the only authority `outcomes.funnel` reads, and it is the one that makes a
   meeting countable per campaign and per step. The write path already exists in
   intent: the Slack alert offers a `MARK_MEETING` action
   (`src/replies.py` comment, TASK-020 decision) — **it needs a caller that
   actually appends the event.**
2. **`work/campaigns.jsonl`**, as a campaign-level `meetings` count, so a
   campaign can be ranked on the metric the operator says is the metric. It is
   not a key there today: the 41 keys present are listed in §1 of the ledger and
   `meetings` is absent.
3. **`docs/second-brain/linkedin.md`** — this file — as a measured line per
   campaign, once 1 exists.

**Until (1) has a caller, "35 meetings" or any other meeting figure cannot be
derived from this repository or from HeyReach, and a report that states one is
quoting a person's memory.**

---

## 10. FARSEER: not on this seat, and precisely where it is missing

The brief names a Farseer campaign as the golden corpus — 35 meetings in 14
countries, channels coordinated per account. **It is not in this data.** What I
can state:

- **No campaign among the 121 on organisation unit 118832 has a name containing
  "farseer", case-insensitively.** All 121 names are reproduced in §11; the
  substrings `FARS` and `SEER` match none of them.
- **This API key reaches exactly one organisation unit**, 118832, on all 121
  campaigns. `config.VARIABLES` holds exactly one HeyReach credential,
  `HEYREACH_KEY` (`src/config.py:148`). There is no second key and therefore no
  second workspace this session can read.
- **In the repository, "farseer" occurs twice and both are a client/agency
  name, not a campaign:** `tests/test_fixture_hygiene.py:60` lists the domain
  `farseer.io` among forbidden fixture domains, and
  `scripts/slack_question_catalogue.py:97` lists `farseer` among agency names.
  So Farseer is an **account** in this estate's vocabulary.
- **`work/campaigns.jsonl` cannot claim it either**: all 40 of its
  `heyreach_campaign_id` rows are `productive`, and none carries a Farseer name.

**What is therefore missing, named exactly, with where it should live:**

| what the operator asked for | where it SHOULD be recorded | state |
|---|---|---|
| the whole cadence per channel with the days | the campaign's `sequence` graph in HeyReach (LinkedIn) and its EmailBison sequence, joined by a row in `work/campaigns.jsonl` carrying both `heyreach_campaign_id` and `bison_campaign_id` | **no such row exists**; of the 40 ledger rows with a HeyReach id, 0 also carry a Bison id |
| the text of every step | the same two sequence graphs | unreadable — no campaign to read |
| the order of channels per account | `src/cadence.py` / the account-level cadence state for that account | not populated for any Farseer account |
| which step and which channel produced each positive reply | a `reply_received` / `positive_reply_detected` event on the record, carrying `channel` and `step` | the queue holds 29 `reply_received` and 2 `positive_reply_detected` events in total, none attributable to Farseer |
| touches before the first positive | derivable from the above once the events exist | not derivable |
| the persona that replied | `correspondentProfile.headline` on the conversation, or `persona_selected` on the record (132 present) | not derivable for an unknown campaign |
| **35 meetings in 14 countries** | `rec.events` `meeting_marked`, per §9 | **0 such events exist anywhere** |

**I have not reconstructed any of it.** If Farseer ran on a different HeyReach
workspace, a second `HEYREACH_KEY`-shaped credential has to be registered in
`config.VARIABLES` and declared, and this walk re-run against it; that is a
credential the operator holds and this session does not. If it ran on this
workspace under another name, the operator naming the id makes it readable in
about 3 seconds of provider time — §1's per-campaign cost is 2.18 s.

---

## 11. Every campaign, one section each — 121 of 121

Ownership on each is the authority's answer and is not adjusted. Recipients are
anonymised everywhere; **our own copy — connection notes, message variants and
fallbacks — is reproduced in full**, and it carries merge variables rather than
rendered names, so it contains no recipient.

### 384886 — PRODUCTIVE - MARKETING AGENCIES - AUSTRALIA - CLEANED - ZVONIMIR APRIL 4TH

- ownership: **unknown** — not in the ledger and not on any operator-declared internal list; UNKNOWN is the state, not a gap
- provider status `PAUSED`; created `2026-04-04T21:23:51.163936Z`; started `2026-04-04T21:25:30.767387Z`
- seats (`campaignAccountIds`): 174892, 174748, 175455, 174742, 174332, 174810, 174822, 174803, 174797
- lead list `599816` (prod), list size `totalItemsCount` = 1142; campaign holds `progressStats.totalUsers` = 1142, finished 0
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **0**, accepted **0** (n/a (denominator 0))
  - messages sent **0**, message threads started **0**, replies **0** (n/a (denominator 0) of threads started)
  - unique leads contacted **0**; profile views 181, follows 0, post likes 0
  - provider's own tags: `autoTaggedInterested` **0**, `totalAutoTagged` **0**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 0 conversations joined, 0 operator-positive replies = **n/a (0 requests sent) per 100 requests sent**
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- sequence node types present in the whole graph: END, FOLLOW, LIKE_POST, VIEW_PROFILE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   VIEW_PROFILE          wait 0H      day  0.00
  step 1   FOLLOW                wait 10D     day 10.00
  step 2   LIKE_POST             wait 10D     day 20.00
  step 3   VIEW_PROFILE          wait 10D     day 30.00
  step 4   LIKE_POST             wait 10D     day 40.00
  step 5   LIKE_POST             wait 10D     day 50.00
  step 6   END                   wait 1D      day 51.00
```

**Connection note:** this graph has no `CONNECTION_REQUEST` node, so no note is sent.


### 384887 — PRODUCTIVE - MARKETING AGENCIES - AUSTRALIA - CLEANED - ZVONIMIR APRIL 4TH v2 

- ownership: **unknown** — not in the ledger and not on any operator-declared internal list; UNKNOWN is the state, not a gap
- provider status `PAUSED`; created `2026-04-04T21:25:46.606856Z`; started `2026-04-04T21:46:39.82639Z`
- seats (`campaignAccountIds`): 174892, 174748, 175455, 174742, 174332, 174822, 174803, 174797
- lead list `599816` (prod), list size `totalItemsCount` = 1142; campaign holds `progressStats.totalUsers` = 1142, finished 1
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **164**, accepted **31** (18.90%)
  - messages sent **0**, message threads started **31**, replies **2** (6.45% of threads started)
  - unique leads contacted **164**; profile views 0, follows 0, post likes 0
  - provider's own tags: `autoTaggedInterested` **1**, `totalAutoTagged` **2**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 35 conversations joined, 0 operator-positive replies = **0.000 per 100 requests sent**
- reply classes in this campaign: `unknown` 2
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-04-07 .. 2026-09-08 (4 days)
- sequence node types present in the whole graph: CONNECTION_REQUEST, END, INMAIL, LIKE_POST, MESSAGE, VIEW_PROFILE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CONNECTION_REQUEST    wait 0H      day  0.00
  step 1   MESSAGE               wait 3D      day  3.00
  step 2   VIEW_PROFILE          wait 1D      day  4.00
  step 3   LIKE_POST             wait 1D      day  5.00
  step 4   MESSAGE               wait 1D      day  6.00
  step 5   LIKE_POST             wait 4D      day 10.00
  step 6   VIEW_PROFILE          wait 4D      day 14.00
  step 7   MESSAGE               wait 1D      day 15.00
  step 8   LIKE_POST             wait 7D      day 22.00
  step 9   MESSAGE               wait 1D      day 23.00
  step 10  VIEW_PROFILE          wait 4D      day 27.00
  step 11  MESSAGE               wait 1D      day 28.00
  step 12  VIEW_PROFILE          wait 1D      day 29.00
  step 13  LIKE_POST             wait 1D      day 30.00
  step 14  END                   wait 1D      day 31.00
```

**Connection note — our text, in full (3 variant(s)):**

1. (164 chars, 22 words) `Hi {FIRST_NAME}, came across {COMPANY} while exploring {INDUSTRY} businesses in {LOCATION}. Would love to connect and follow what you are building.

{MY_FIRST_NAME}`
2. (173 chars, 26 words) `Hi {FIRST_NAME}, saw {COMPANY} pop up while looking at {INDUSTRY} agencies in {LOCATION}. Looks like interesting work, would love to have you in my network.

{MY_FIRST_NAME}`
3. (173 chars, 23 words) `Hi {FIRST_NAME}, found {COMPANY} while browsing {INDUSTRY} businesses in {LOCATION}. Always good to connect with people doing interesting work in the space.

{MY_FIRST_NAME}`

**Message steps — our text, in full:**

- message at day 3.00, 3 variant(s):
  - variant 1 (510 chars, 80 words): `Hi {FIRST_NAME}, appreciate the add.

I help {INDUSTRY} agencies in {LOCATION} replace the usual pile of disconnected tools with one platform that ties together projects, time tracking, budgets and invoicing. The idea being that a {POSITION} can actually see whether a project is profitable while it is still running rather than finding out after the invoice goes out.

Thought {COMPANY} might be worth a conversation at some point. No pressure on that though, good to be connected either way.

{MY_FIRST_NAME}`
  - variant 2 (374 chars, 60 words): `Hey {FIRST_NAME}, thanks for connecting.

I work with {INDUSTRY} agencies on the ops side, specifically helping teams get a real time view of project profitability and utilization without juggling five different tools to do it. Given what you are doing at {COMPANY} I thought it could be relevant at some point.

Happy to share more whenever it makes sense.

{MY_FIRST_NAME}`
  - variant 3 (376 chars, 65 words): `Hi {FIRST_NAME}, good to be connected.

I spend most of my time working with {INDUSTRY} agencies on the gap between time logged and money made. Most {POSITION}s I speak with know something is leaking but cannot pinpoint where until it is too late to fix it.

Thought {COMPANY} might find it useful to see how other teams are solving that. No rush on anything.

{MY_FIRST_NAME}`
  - fallback (322 chars): `Hi, appreciate the add.

I work with agencies on the ops and profitability side, specifically helping teams replace their disconnected tool stack with one platform that ties together projects, time tracking, budgets and invoicing.

Happy to share more if it is ever relevant to your setup. Good to be connected either way.`
- message at day 6.00, 3 variant(s):
  - variant 1 (310 chars, 54 words): `Hey {FIRST_NAME}, quick question for you.

What does {COMPANY} currently use to track project profitability in real time? Not after the work is done, I mean while a project is still live.

Asking because the answer tells me a lot about whether what I do would actually be useful to you or not.

{MY_FIRST_NAME}`
  - variant 2 (323 chars, 56 words): `Hey {FIRST_NAME}, wanted to ask you something directly.

How does {COMPANY} know if a project is going to hit its margin before it is finished? Is that something you can see at any point or does it only become clear after the fact?

Genuinely curious because the answer changes what I would share with you.

{MY_FIRST_NAME}`
  - variant 3 (276 chars, 49 words): `Hey {FIRST_NAME}, just a quick one.

When a project at {COMPANY} goes over budget who is the first person to find out and how do they find out?

Asking because that gap between when something goes wrong and when someone catches it is exactly what I help with.

{MY_FIRST_NAME}`
  - fallback (251 chars): `Hey, quick question.

How does your team currently track whether a project is going to hit its margin before it wraps up?

Not looking to pitch anything, I just find the answer changes a lot about whether what I do is even relevant. Genuinely curious.`
- message at day 15.00, 3 variant(s):
  - variant 1 (577 chars, 99 words): `Hey {FIRST_NAME}, wanted to share what I actually work with in case it is relevant.

The tool is called Productive. It is built for {INDUSTRY} agencies and brings project management, time tracking, budgets and invoicing into one place so the data connects automatically. Most {POSITION}s use it to get a clear picture of utilization and margin without pulling numbers from four different tools every time someone asks how a project is tracking.

{COMPANY} came to mind as a good fit. Would you be open to a 15 minute call to see how it maps to how you operate?

{MY_FIRST_NAME}`
  - variant 2 (467 chars, 75 words): `Hey {FIRST_NAME}, sharing this because I think it is actually relevant to {COMPANY}.

The platform is called Productive and it was built specifically for {INDUSTRY} businesses. It replaces the need to run separate tools for project management, time, budgets and invoicing by connecting all of it in one place. A {POSITION} can see live margin and utilization without anyone building a manual report.

Worth 15 minutes if you want to see it in action?

{MY_FIRST_NAME}`
  - variant 3 (475 chars, 76 words): `Hey {FIRST_NAME}, I should have mentioned this earlier.

The product I work with is Productive. It is an agency management platform that connects time tracking to budgets to invoicing so the financial picture updates automatically as work happens. Teams in {LOCATION} use it to replace Harvest, Asana and whatever spreadsheet is doing the reporting work right now.

Happy to walk you through how it works for a business like {COMPANY} if you have 15 minutes.

{MY_FIRST_NAME}`
  - fallback (442 chars): `Hey, wanted to share what I actually work with.

The tool is called Productive. It is an agency management platform that connects project management, time tracking, budgets and invoicing in one place so the data updates automatically rather than sitting in separate tools. Most agency owners and ops leads use it to get a live view of margin and utilization without manual reporting.

Worth a 15-minute call if you want to see how it works?

`
- message at day 23.00, 3 variant(s):
  - variant 1 (536 chars, 90 words): `Hey {FIRST_NAME}, one more thought and then I will leave it with you.

Most {INDUSTRY} agencies in {LOCATION} that switch to Productive end up replacing Harvest or Toggl for time, Monday or Asana for projects and whatever spreadsheet was doing the budget reporting. The reason it sticks is that the data finally connects rather than sitting in separate tools that someone at {COMPANY} has to reconcile by hand.

If that sounds familiar I am happy to send over a short walkthrough instead of a call if that feels easier.

{MY_FIRST_NAME}`
  - variant 2 (455 chars, 77 words): `Hey {FIRST_NAME}, circling back one more time.

The agencies in {LOCATION} that get the most out of Productive are usually running exactly the kind of setup {COMPANY} is likely running right now. Multiple tools that work fine on their own but do not talk to each other, so a {POSITION} ends up doing the connecting manually.

Productive removes that entirely. Happy to show you a quick walkthrough if a call feels like too much right now.

{MY_FIRST_NAME}`
  - variant 3 (467 chars, 85 words): `Hey {FIRST_NAME}, wanted to try a different angle.

The question I get most from {POSITION}s before they see Productive is something like how long does it take you to answer whether we made money on that project? At most agencies it takes a day or two of pulling data together. In Productive the answer is on screen in real time.

If that gap sounds familiar at {COMPANY} it is worth seeing. I can send a walkthrough if a call does not fit right now.

{MY_FIRST_NAME}`
  - fallback (444 chars): `Hey, one more thought before I leave it with you.

Most agencies that switch to Productive end up replacing Harvest or Toggl for time, Monday or Asana for projects and whatever spreadsheet was doing the budget reporting. The reason it sticks is that the data finally connects rather than sitting in separate tools someone has to reconcile by hand.

Happy to send a short walkthrough if you want to see how it works without committing to a call.`
- message at day 28.00, 4 variant(s):
  - variant 1 (431 chars, 75 words): `Hey {FIRST_NAME}, last message from me on this.

If the timing is off or it is just not relevant to where {COMPANY} is right now that is completely fine. I would rather know than keep nudging you.

If things change and getting a cleaner view of profitability and utilisation ever becomes a priority, Productive has a free 14 day trial at productive.io and you can explore it without having to talk to anyone first.

{MY_FIRST_NAME}`
  - variant 2 (385 chars, 66 words): `Hey {FIRST_NAME}, I have sent a few messages without hearing back so I will leave it here.

No hard feelings at all, timing is everything with this kind of thing. If {COMPANY} ever gets to a point where the tool stack becomes a real headache or you want better visibility into project margins, Productive is worth a look. Free trial at productive.io, no call required.

{MY_FIRST_NAME}`
  - variant 3 (385 chars, 66 words): `Hey {FIRST_NAME}, I have sent a few messages without hearing back so I will leave it here.

No hard feelings at all, timing is everything with this kind of thing. If {COMPANY} ever gets to a point where the tool stack becomes a real headache or you want better visibility into project margins, Productive is worth a look. Free trial at productive.io, no call required.

{MY_FIRST_NAME}`
  - variant 4 (357 chars, 62 words): `Hey {FIRST_NAME}, wrapping up my end of this.

I know these messages land at all kinds of bad times so no offence taken. If the problem I have been describing ever becomes urgent at {COMPANY} you can start a free trial of Productive at productive.io without talking to anyone. Wanted to make sure you had that before I stopped reaching out.

{MY_FIRST_NAME}`
  - fallback (306 chars): `Hey, last message from me on this.

No hard feelings if the timing has not been right. If things ever change and you want a cleaner way to track project profitability and team utilization, Productive is worth a look. Free 14 day trial at productive.io and you do not need to speak to anyone to get started.`

### 384890 — PRODUCTIVE - MARKETING AGENCIES - AUSTRALIA - CLEANED - ZVONIMIR APRIL 4TH v3

- ownership: **unknown** — not in the ledger and not on any operator-declared internal list; UNKNOWN is the state, not a gap
- provider status `PAUSED`; created `2026-04-04T21:48:20.839516Z`; started `2026-04-04T21:54:31.882548Z`
- seats (`campaignAccountIds`): 174892, 174748, 175455, 174742, 174332, 174822, 174803, 174797, 174810
- lead list `599816` (prod), list size `totalItemsCount` = 1142; campaign holds `progressStats.totalUsers` = 1142, finished 0
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **0**, accepted **0** (n/a (denominator 0))
  - messages sent **0**, message threads started **0**, replies **0** (n/a (denominator 0) of threads started)
  - unique leads contacted **0**; profile views 61, follows 0, post likes 25
  - provider's own tags: `autoTaggedInterested` **0**, `totalAutoTagged` **0**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 0 conversations joined, 0 operator-positive replies = **n/a (0 requests sent) per 100 requests sent**
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- sequence node types present in the whole graph: CONNECTION_REQUEST, END, FOLLOW, LIKE_POST, MESSAGE, VIEW_PROFILE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   VIEW_PROFILE          wait 0H      day  0.00
  step 1   LIKE_POST             wait 3D      day  3.00
  step 2   FOLLOW                wait 3D      day  6.00
  step 3   CONNECTION_REQUEST    wait 3D      day  9.00
  step 4   MESSAGE               wait 3H      day  9.12
  step 5   LIKE_POST             wait 1D      day 10.12
  step 6   LIKE_POST             wait 4D      day 14.12
  step 7   MESSAGE               wait 1D      day 15.12
  step 8   VIEW_PROFILE          wait 1D      day 16.12
  step 9   VIEW_PROFILE          wait 1D      day 17.12
  step 10  LIKE_POST             wait 1D      day 18.12
  step 11  MESSAGE               wait 1D      day 19.12
  step 12  MESSAGE               wait 5D      day 24.12
  step 13  VIEW_PROFILE          wait 1D      day 25.12
  step 14  LIKE_POST             wait 1D      day 26.12
  step 15  MESSAGE               wait 1D      day 27.12
  step 16  END                   wait 1D      day 28.12
```

**Connection note:** 5 `CONNECTION_REQUEST` note slot(s), every one of them EMPTY — this campaign sends connection requests with no note.

**Message steps — our text, in full:**

- message at day 9.12, 3 variant(s):
  - variant 1 (607 chars, 105 words): `Hey {FIRST_NAME}, a colleague of mine probably reached out to you about Productive recently. I wanted to add my own note because {COMPANY} genuinely looks like a strong fit for what we do and I did not want it to get buried in a busy inbox.

I work with {INDUSTRY} agencies in {LOCATION} on the ops and profitability side. The short version is that Productive replaces the disconnected tool stack most agencies run on and gives a {POSITION} a real time view of project margins, utilization and forecasts in one place.

Worth a quick conversation to see if it maps to how {COMPANY} operates?

{MY_FIRST_NAME}`
  - variant 2 (429 chars, 74 words): `Hey {FIRST_NAME}, you may have already heard from someone on my team about Productive. I am reaching out separately because I look at the {INDUSTRY} space in {LOCATION} specifically and {COMPANY} keeps coming up as a business that would get a lot out of the platform.

Happy to give you a different perspective on it if the first message did not land at the right time. Sometimes it just takes the right framing.

{MY_FIRST_NAME}`
  - variant 3 (429 chars, 74 words): `Hey {FIRST_NAME}, one of my colleagues reached out to you about Productive recently. I am following up because I wanted to make this feel less like a blast and more like a real conversation.

I spend most of my time working with {POSITION}s at {INDUSTRY} agencies and the problems I hear consistently are the same ones Productive was built to solve. Thought it was worth one more shot before leaving it with you.

{MY_FIRST_NAME}`
  - fallback (453 chars): `Hey, a colleague of mine probably reached out recently about Productive. I wanted to follow up from my side because your agency looks like a strong fit for what we do, and I did not want it to get lost.

The short version is that Productive is an agency management platform that connects project management, time tracking, budgets, and invoicing so everything talks to each other. Happy to give you a fresh perspective on it if the timing is better now.`
- message at day 15.12, 3 variant(s):
  - variant 1 (392 chars, 66 words): `Hey {FIRST_NAME}, checking in to see if my last message landed.

Rather than send another pitch I wanted to ask a genuine question. When a project at {COMPANY} goes over budget or under delivers on margin, how long does it typically take before someone catches it?

The answer to that is usually what tells me whether Productive would actually change anything for you or not.

{MY_FIRST_NAME}`
  - variant 2 (328 chars, 52 words): `Hey {FIRST_NAME}, following up on my last note.

Quick question about {COMPANY}. How does your team currently know whether you are fully utilizing your people across projects? Not a trick question, I am asking because that visibility gap is exactly what most {INDUSTRY} agencies I work with are trying to close.

{MY_FIRST_NAME}`
  - variant 3 (297 chars, 52 words): `Hey {FIRST_NAME}, just circling back.

I will be straight with you. Between my colleague and I we have both reached out now and I think {COMPANY} is genuinely worth a conversation rather than just another follow up. What would make it worth 15 minutes of your time to take a look?

{MY_FIRST_NAME}`
  - fallback (247 chars): `Hey, just following up on my last message.

Rather than repeat the pitch I wanted to ask directly. What would need to be true about a tool for it to be worth 15 minutes of your time right now? Happy to tell you whether Productive fits that or not.`
- message at day 19.12, 3 variant(s):
  - variant 1 (544 chars, 93 words): `Hey {FIRST_NAME}, one more thought in case the timing is better now.

The thing most {POSITION}s at {INDUSTRY} agencies tell me after they see Productive is that they wish they had seen it before their last hire. The reason is that resourcing and growth decisions get made on utilization data and most agencies are working from numbers that are a month old and manually assembled.

Productive puts that in front of you in real time so the decisions at {COMPANY} are based on what is actually happening now.

Still worth a look?

{MY_FIRST_NAME}`
  - variant 2 (486 chars, 83 words): `Hey {FIRST_NAME}, trying a different angle this time.

Most {INDUSTRY} agencies in {LOCATION} that switch to Productive do it because of one specific moment. Someone asks how a project is tracking, the answer requires pulling from three different tools and an hour of work, and whoever is responsible decides there has to be a better way.

If that moment has not happened at {COMPANY} yet it probably will. Happy to show you what it looks like when it does not need to.

{MY_FIRST_NAME}`
  - variant 3 (282 chars, 51 words): `Hey {FIRST_NAME}, keeping this one short.

Productive has a 14 day free trial and no card required. If a call feels like too much of a commitment right now you can start at productive.io and see the platform on your own terms first.

Still here if you want to chat.

{MY_FIRST_NAME}`
  - fallback (440 chars): `Hey, trying a different angle this time.

The moment most agencies decide to switch to Productive is when someone asks a simple question about project profitability and the answer takes an hour to pull together from separate tools. If that has happened recently it is probably worth 15 minutes to see what it looks like when it does not.

Happy to set up a call or you can start a free trial at productive.io if you prefer to explore first.`
- message at day 24.12, 3 variant(s):
  - variant 1 (604 chars, 95 words): `Hey {FIRST_NAME}, sharing something specific in case it is useful.

{INDUSTRY} agencies in {LOCATION} that use Productive typically replace Harvest or Toggl for time tracking, Monday or Asana for project management and whatever spreadsheet was doing the budget reporting. The economics tend to work out well because they are paying for fewer tools and making better decisions with the data they were already capturing.

For a {POSITION} at {COMPANY} the main shift is that you stop being the person assembling the picture and start being the person who already has it.

Worth 15 minutes?

{MY_FIRST_NAME}`
  - variant 2 (566 chars, 99 words): `Hey {FIRST_NAME}, I realize I have sent a few messages now so I will make this one count.

The agencies that get the most out of Productive are the ones where a {POSITION} is spending real time each week on work that should happen automatically. Pulling utilization reports, reconciling budgets, chasing time logs, building invoices from scratch. Productive handles all of that so the focus shifts to what the data is telling you rather than how to get the data in the first place.

If any of that sounds like {COMPANY} right now it is worth a look.

{MY_FIRST_NAME}`
  - variant 3 (469 chars, 77 words): `Hey {FIRST_NAME}, last proper pitch from me before I wrap up.

Three things Productive does that most agency tools do not. Time tracked connects directly to budget burn so you see profit impact as work happens. Resource planning shows utilization across the whole team in real time. Invoicing pulls from actual project data so there is no manual assembly.

If {COMPANY} is doing any of those things manually right now that is the gap Productive closes.

{MY_FIRST_NAME}`
  - fallback (426 chars): `Hey, making this one specific.

Three things Productive does that most agency tools do not. Time tracked connects directly to budget burn so you see profit impact as work happens. Resource planning shows team utilization in real time. Invoicing pulls from actual project data so there is no manual assembly.

If your agency is doing any of those things manually right now that is the gap Productive closes. Worth 15 minutes?

`
- message at day 27.12, 3 variant(s):
  - variant 1 (402 chars, 72 words): `Hey {FIRST_NAME}, wrapping up from my end.

Between my colleague and I we have sent a handful of messages and I do not want to keep landing in your inbox if the timing is just not right for {COMPANY}. No hard feelings at all.

If it ever becomes relevant, Productive has a free trial at productive.io and you can explore it without talking to anyone first. Worth knowing that is there.

{MY_FIRST_NAME}`
  - variant 2 (297 chars, 51 words): `Hey {FIRST_NAME}, last one from me.

I get it, the timing might just not be right. If things change at {COMPANY} and getting a cleaner view of margins and utilization becomes a priority, feel free to reach out directly or start a free trial at productive.io.

Leaving it with you.

{MY_FIRST_NAME}`
  - variant 3 (350 chars, 62 words): `Hey {FIRST_NAME}, closing the loop on my end.

My colleague reached out, I followed up a few times and I think we have both made a reasonable case for why Productive could work well for {COMPANY}. At this point it is in your hands.

If the moment ever comes where the current setup stops working, productive.io is the place to start.

{MY_FIRST_NAME}`
  - fallback (305 chars): `Hey, last message from me on this.

My colleague and I have both reached out now and I do not want to keep taking up space in your inbox. If the timing is ever right, Productive has a free trial at productive.io and you do not need to speak to anyone to get started.

Thanks for bearing with the outreach.`

### 384897 — CLEANED - OUT OF 50K - PRODUCTIVE - MARKETING AGENCIES - AUSTRALIA - CLEANED - ZVONIMIR APRIL 4TH v2

- ownership: **unknown** — not in the ledger and not on any operator-declared internal list; UNKNOWN is the state, not a gap
- provider status `PAUSED`; created `2026-04-04T22:13:55.765779Z`; started `2026-04-04T22:14:45.348795Z`
- seats (`campaignAccountIds`): 174892, 174748, 175455, 174742, 174332, 174822, 174803, 174797
- lead list `599816` (prod), list size `totalItemsCount` = 1142; campaign holds `progressStats.totalUsers` = 1142, finished 1
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **57**, accepted **12** (21.05%)
  - messages sent **0**, message threads started **12**, replies **2** (16.67% of threads started)
  - unique leads contacted **57**; profile views 0, follows 0, post likes 0
  - provider's own tags: `autoTaggedInterested` **2**, `totalAutoTagged` **2**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 13 conversations joined, 1 operator-positive replies = **1.754 per 100 requests sent**
- reply classes in this campaign: `unknown` 6, `negative` 2, `question` 1
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-04-06 .. 2026-08-25 (3 days)
- sequence node types present in the whole graph: CONNECTION_REQUEST, END, LIKE_POST, MESSAGE, VIEW_PROFILE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CONNECTION_REQUEST    wait 0H      day  0.00
  step 1   MESSAGE               wait 3D      day  3.00
  step 2   VIEW_PROFILE          wait 1D      day  4.00
  step 3   LIKE_POST             wait 1D      day  5.00
  step 4   MESSAGE               wait 1D      day  6.00
  step 5   LIKE_POST             wait 4D      day 10.00
  step 6   VIEW_PROFILE          wait 4D      day 14.00
  step 7   MESSAGE               wait 1D      day 15.00
  step 8   LIKE_POST             wait 7D      day 22.00
  step 9   MESSAGE               wait 1D      day 23.00
  step 10  VIEW_PROFILE          wait 4D      day 27.00
  step 11  MESSAGE               wait 1D      day 28.00
  step 12  VIEW_PROFILE          wait 1D      day 29.00
  step 13  LIKE_POST             wait 1D      day 30.00
  step 14  END                   wait 1D      day 31.00
```

**Connection note — our text, in full (3 variant(s)):**

1. (164 chars, 22 words) `Hi {FIRST_NAME}, came across {COMPANY} while exploring {INDUSTRY} businesses in {LOCATION}. Would love to connect and follow what you are building.

{MY_FIRST_NAME}`
2. (173 chars, 26 words) `Hi {FIRST_NAME}, saw {COMPANY} pop up while looking at {INDUSTRY} agencies in {LOCATION}. Looks like interesting work, would love to have you in my network.

{MY_FIRST_NAME}`
3. (173 chars, 23 words) `Hi {FIRST_NAME}, found {COMPANY} while browsing {INDUSTRY} businesses in {LOCATION}. Always good to connect with people doing interesting work in the space.

{MY_FIRST_NAME}`

**Message steps — our text, in full:**

- message at day 3.00, 3 variant(s):
  - variant 1 (510 chars, 80 words): `Hi {FIRST_NAME}, appreciate the add.

I help {INDUSTRY} agencies in {LOCATION} replace the usual pile of disconnected tools with one platform that ties together projects, time tracking, budgets and invoicing. The idea being that a {POSITION} can actually see whether a project is profitable while it is still running rather than finding out after the invoice goes out.

Thought {COMPANY} might be worth a conversation at some point. No pressure on that though, good to be connected either way.

{MY_FIRST_NAME}`
  - variant 2 (374 chars, 60 words): `Hey {FIRST_NAME}, thanks for connecting.

I work with {INDUSTRY} agencies on the ops side, specifically helping teams get a real time view of project profitability and utilization without juggling five different tools to do it. Given what you are doing at {COMPANY} I thought it could be relevant at some point.

Happy to share more whenever it makes sense.

{MY_FIRST_NAME}`
  - variant 3 (376 chars, 65 words): `Hi {FIRST_NAME}, good to be connected.

I spend most of my time working with {INDUSTRY} agencies on the gap between time logged and money made. Most {POSITION}s I speak with know something is leaking but cannot pinpoint where until it is too late to fix it.

Thought {COMPANY} might find it useful to see how other teams are solving that. No rush on anything.

{MY_FIRST_NAME}`
  - fallback (322 chars): `Hi, appreciate the add.

I work with agencies on the ops and profitability side, specifically helping teams replace their disconnected tool stack with one platform that ties together projects, time tracking, budgets and invoicing.

Happy to share more if it is ever relevant to your setup. Good to be connected either way.`
- message at day 6.00, 3 variant(s):
  - variant 1 (310 chars, 54 words): `Hey {FIRST_NAME}, quick question for you.

What does {COMPANY} currently use to track project profitability in real time? Not after the work is done, I mean while a project is still live.

Asking because the answer tells me a lot about whether what I do would actually be useful to you or not.

{MY_FIRST_NAME}`
  - variant 2 (323 chars, 56 words): `Hey {FIRST_NAME}, wanted to ask you something directly.

How does {COMPANY} know if a project is going to hit its margin before it is finished? Is that something you can see at any point or does it only become clear after the fact?

Genuinely curious because the answer changes what I would share with you.

{MY_FIRST_NAME}`
  - variant 3 (276 chars, 49 words): `Hey {FIRST_NAME}, just a quick one.

When a project at {COMPANY} goes over budget who is the first person to find out and how do they find out?

Asking because that gap between when something goes wrong and when someone catches it is exactly what I help with.

{MY_FIRST_NAME}`
  - fallback (251 chars): `Hey, quick question.

How does your team currently track whether a project is going to hit its margin before it wraps up?

Not looking to pitch anything, I just find the answer changes a lot about whether what I do is even relevant. Genuinely curious.`
- message at day 15.00, 3 variant(s):
  - variant 1 (577 chars, 99 words): `Hey {FIRST_NAME}, wanted to share what I actually work with in case it is relevant.

The tool is called Productive. It is built for {INDUSTRY} agencies and brings project management, time tracking, budgets and invoicing into one place so the data connects automatically. Most {POSITION}s use it to get a clear picture of utilization and margin without pulling numbers from four different tools every time someone asks how a project is tracking.

{COMPANY} came to mind as a good fit. Would you be open to a 15 minute call to see how it maps to how you operate?

{MY_FIRST_NAME}`
  - variant 2 (467 chars, 75 words): `Hey {FIRST_NAME}, sharing this because I think it is actually relevant to {COMPANY}.

The platform is called Productive and it was built specifically for {INDUSTRY} businesses. It replaces the need to run separate tools for project management, time, budgets and invoicing by connecting all of it in one place. A {POSITION} can see live margin and utilization without anyone building a manual report.

Worth 15 minutes if you want to see it in action?

{MY_FIRST_NAME}`
  - variant 3 (475 chars, 76 words): `Hey {FIRST_NAME}, I should have mentioned this earlier.

The product I work with is Productive. It is an agency management platform that connects time tracking to budgets to invoicing so the financial picture updates automatically as work happens. Teams in {LOCATION} use it to replace Harvest, Asana and whatever spreadsheet is doing the reporting work right now.

Happy to walk you through how it works for a business like {COMPANY} if you have 15 minutes.

{MY_FIRST_NAME}`
  - fallback (442 chars): `Hey, wanted to share what I actually work with.

The tool is called Productive. It is an agency management platform that connects project management, time tracking, budgets and invoicing in one place so the data updates automatically rather than sitting in separate tools. Most agency owners and ops leads use it to get a live view of margin and utilization without manual reporting.

Worth a 15-minute call if you want to see how it works?

`
- message at day 23.00, 3 variant(s):
  - variant 1 (536 chars, 90 words): `Hey {FIRST_NAME}, one more thought and then I will leave it with you.

Most {INDUSTRY} agencies in {LOCATION} that switch to Productive end up replacing Harvest or Toggl for time, Monday or Asana for projects and whatever spreadsheet was doing the budget reporting. The reason it sticks is that the data finally connects rather than sitting in separate tools that someone at {COMPANY} has to reconcile by hand.

If that sounds familiar I am happy to send over a short walkthrough instead of a call if that feels easier.

{MY_FIRST_NAME}`
  - variant 2 (455 chars, 77 words): `Hey {FIRST_NAME}, circling back one more time.

The agencies in {LOCATION} that get the most out of Productive are usually running exactly the kind of setup {COMPANY} is likely running right now. Multiple tools that work fine on their own but do not talk to each other, so a {POSITION} ends up doing the connecting manually.

Productive removes that entirely. Happy to show you a quick walkthrough if a call feels like too much right now.

{MY_FIRST_NAME}`
  - variant 3 (467 chars, 85 words): `Hey {FIRST_NAME}, wanted to try a different angle.

The question I get most from {POSITION}s before they see Productive is something like how long does it take you to answer whether we made money on that project? At most agencies it takes a day or two of pulling data together. In Productive the answer is on screen in real time.

If that gap sounds familiar at {COMPANY} it is worth seeing. I can send a walkthrough if a call does not fit right now.

{MY_FIRST_NAME}`
  - fallback (444 chars): `Hey, one more thought before I leave it with you.

Most agencies that switch to Productive end up replacing Harvest or Toggl for time, Monday or Asana for projects and whatever spreadsheet was doing the budget reporting. The reason it sticks is that the data finally connects rather than sitting in separate tools someone has to reconcile by hand.

Happy to send a short walkthrough if you want to see how it works without committing to a call.`
- message at day 28.00, 4 variant(s):
  - variant 1 (431 chars, 75 words): `Hey {FIRST_NAME}, last message from me on this.

If the timing is off or it is just not relevant to where {COMPANY} is right now that is completely fine. I would rather know than keep nudging you.

If things change and getting a cleaner view of profitability and utilisation ever becomes a priority, Productive has a free 14 day trial at productive.io and you can explore it without having to talk to anyone first.

{MY_FIRST_NAME}`
  - variant 2 (385 chars, 66 words): `Hey {FIRST_NAME}, I have sent a few messages without hearing back so I will leave it here.

No hard feelings at all, timing is everything with this kind of thing. If {COMPANY} ever gets to a point where the tool stack becomes a real headache or you want better visibility into project margins, Productive is worth a look. Free trial at productive.io, no call required.

{MY_FIRST_NAME}`
  - variant 3 (385 chars, 66 words): `Hey {FIRST_NAME}, I have sent a few messages without hearing back so I will leave it here.

No hard feelings at all, timing is everything with this kind of thing. If {COMPANY} ever gets to a point where the tool stack becomes a real headache or you want better visibility into project margins, Productive is worth a look. Free trial at productive.io, no call required.

{MY_FIRST_NAME}`
  - variant 4 (357 chars, 62 words): `Hey {FIRST_NAME}, wrapping up my end of this.

I know these messages land at all kinds of bad times so no offence taken. If the problem I have been describing ever becomes urgent at {COMPANY} you can start a free trial of Productive at productive.io without talking to anyone. Wanted to make sure you had that before I stopped reaching out.

{MY_FIRST_NAME}`
  - fallback (306 chars): `Hey, last message from me on this.

No hard feelings if the timing has not been right. If things ever change and you want a cleaner way to track project profitability and team utilization, Productive is worth a look. Free 14 day trial at productive.io and you do not need to speak to anyone to get started.`

### 384901 — PRODUCTIVE - USA - MARKETING AGNECIES - ZVONIMIR - APRIL 5TH

- ownership: **unknown** — not in the ledger and not on any operator-declared internal list; UNKNOWN is the state, not a gap
- provider status `PAUSED`; created `2026-04-04T22:34:28.317961Z`; started `2026-04-04T22:36:07.703677Z`
- seats (`campaignAccountIds`): 174892, 174748, 175455, 174742, 174332, 174810, 174822, 174803, 174797
- lead list `599838` (ZVONIMIR ICP MARKETING APRIL FIFTH), list size `totalItemsCount` = 2481; campaign holds `progressStats.totalUsers` = 2481, finished 0
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **0**, accepted **0** (n/a (denominator 0))
  - messages sent **0**, message threads started **0**, replies **0** (n/a (denominator 0) of threads started)
  - unique leads contacted **0**; profile views 197, follows 0, post likes 0
  - provider's own tags: `autoTaggedInterested` **0**, `totalAutoTagged` **0**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 0 conversations joined, 0 operator-positive replies = **n/a (0 requests sent) per 100 requests sent**
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- sequence node types present in the whole graph: END, FOLLOW, LIKE_POST, VIEW_PROFILE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   VIEW_PROFILE          wait 0H      day  0.00
  step 1   FOLLOW                wait 10D     day 10.00
  step 2   LIKE_POST             wait 10D     day 20.00
  step 3   LIKE_POST             wait 10D     day 30.00
  step 4   LIKE_POST             wait 10D     day 40.00
  step 5   LIKE_POST             wait 10D     day 50.00
  step 6   LIKE_POST             wait 10D     day 60.00
  step 7   LIKE_POST             wait 10D     day 70.00
  step 8   END                   wait 1D      day 71.00
```

**Connection note:** this graph has no `CONNECTION_REQUEST` node, so no note is sent.


### 388938 — PRODUCTIVE - MARKETING AGENCIES - AUSTRALIA - CLEANED - ZVONIMIR - soft

- ownership: **unknown** — not in the ledger and not on any operator-declared internal list; UNKNOWN is the state, not a gap
- provider status `PAUSED`; created `2026-04-08T14:58:27.749087Z`; started `2026-04-08T14:58:53.375949Z`
- seats (`campaignAccountIds`): 174892, 174748, 175455, 174742, 174332, 174810, 174822, 174803, 174797, 174845
- lead list `605364` (PRODUCTIVE - AUSTRALIA - ICP - FILTERED OUT OF 200K LEADS), list size `totalItemsCount` = 5133; campaign holds `progressStats.totalUsers` = 5133, finished 725
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **0**, accepted **0** (n/a (denominator 0))
  - messages sent **0**, message threads started **0**, replies **0** (n/a (denominator 0) of threads started)
  - unique leads contacted **0**; profile views 3566, follows 2196, post likes 2882
  - provider's own tags: `autoTaggedInterested` **0**, `totalAutoTagged` **0**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 0 conversations joined, 0 operator-positive replies = **n/a (0 requests sent) per 100 requests sent**
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- sequence node types present in the whole graph: END, FOLLOW, LIKE_POST, VIEW_PROFILE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   VIEW_PROFILE          wait 0H      day  0.00
  step 1   FOLLOW                wait 10D     day 10.00
  step 2   LIKE_POST             wait 10D     day 20.00
  step 3   VIEW_PROFILE          wait 10D     day 30.00
  step 4   LIKE_POST             wait 10D     day 40.00
  step 5   LIKE_POST             wait 10D     day 50.00
  step 6   END                   wait 1D      day 51.00
```

**Connection note:** this graph has no `CONNECTION_REQUEST` node, so no note is sent.


### 388939 — PRODUCTIVE - MARKETING AGENCIES - AUSTRALIA - CLEANED - ZVONIMIR v2

- ownership: **unknown** — not in the ledger and not on any operator-declared internal list; UNKNOWN is the state, not a gap
- provider status `PAUSED`; created `2026-04-08T14:59:06.572479Z`; started `2026-04-08T14:59:28.339086Z`
- seats (`campaignAccountIds`): 174892, 174748, 175455, 174742, 174332, 174822, 174803, 174797, 174845
- lead list `605364` (PRODUCTIVE - AUSTRALIA - ICP - FILTERED OUT OF 200K LEADS), list size `totalItemsCount` = 5133; campaign holds `progressStats.totalUsers` = 5133, finished 99
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **1650**, accepted **183** (11.09%)
  - messages sent **590**, message threads started **207**, replies **47** (22.71% of threads started)
  - unique leads contacted **1650**; profile views 438, follows 0, post likes 1227
  - provider's own tags: `autoTaggedInterested` **23**, `totalAutoTagged` **47**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 203 conversations joined, 16 operator-positive replies = **0.970 per 100 requests sent**
- reply classes in this campaign: `unknown` 37, `negative` 11, `positive` 11, `question` 5, `automated` 4, `not_relevant` 2, `not_now` 1
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-04-08 .. 2026-09-16 (57 days)
- sequence node types present in the whole graph: CONNECTION_REQUEST, END, INMAIL, LIKE_POST, MESSAGE, VIEW_PROFILE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CONNECTION_REQUEST    wait 0H      day  0.00
  step 1   MESSAGE               wait 3D      day  3.00
  step 2   VIEW_PROFILE          wait 1D      day  4.00
  step 3   LIKE_POST             wait 1D      day  5.00
  step 4   MESSAGE               wait 1D      day  6.00
  step 5   LIKE_POST             wait 4D      day 10.00
  step 6   VIEW_PROFILE          wait 4D      day 14.00
  step 7   MESSAGE               wait 1D      day 15.00
  step 8   LIKE_POST             wait 7D      day 22.00
  step 9   MESSAGE               wait 1D      day 23.00
  step 10  VIEW_PROFILE          wait 4D      day 27.00
  step 11  MESSAGE               wait 1D      day 28.00
  step 12  VIEW_PROFILE          wait 1D      day 29.00
  step 13  LIKE_POST             wait 1D      day 30.00
  step 14  END                   wait 1D      day 31.00
```

**Connection note — our text, in full (3 variant(s)):**

1. (164 chars, 22 words) `Hi {FIRST_NAME}, came across {COMPANY} while exploring {INDUSTRY} businesses in {LOCATION}. Would love to connect and follow what you are building.

{MY_FIRST_NAME}`
2. (173 chars, 26 words) `Hi {FIRST_NAME}, saw {COMPANY} pop up while looking at {INDUSTRY} agencies in {LOCATION}. Looks like interesting work, would love to have you in my network.

{MY_FIRST_NAME}`
3. (173 chars, 23 words) `Hi {FIRST_NAME}, found {COMPANY} while browsing {INDUSTRY} businesses in {LOCATION}. Always good to connect with people doing interesting work in the space.

{MY_FIRST_NAME}`

**Message steps — our text, in full:**

- message at day 3.00, 3 variant(s):
  - variant 1 (510 chars, 80 words): `Hi {FIRST_NAME}, appreciate the add.

I help {INDUSTRY} agencies in {LOCATION} replace the usual pile of disconnected tools with one platform that ties together projects, time tracking, budgets and invoicing. The idea being that a {POSITION} can actually see whether a project is profitable while it is still running rather than finding out after the invoice goes out.

Thought {COMPANY} might be worth a conversation at some point. No pressure on that though, good to be connected either way.

{MY_FIRST_NAME}`
  - variant 2 (374 chars, 60 words): `Hey {FIRST_NAME}, thanks for connecting.

I work with {INDUSTRY} agencies on the ops side, specifically helping teams get a real time view of project profitability and utilization without juggling five different tools to do it. Given what you are doing at {COMPANY} I thought it could be relevant at some point.

Happy to share more whenever it makes sense.

{MY_FIRST_NAME}`
  - variant 3 (376 chars, 65 words): `Hi {FIRST_NAME}, good to be connected.

I spend most of my time working with {INDUSTRY} agencies on the gap between time logged and money made. Most {POSITION}s I speak with know something is leaking but cannot pinpoint where until it is too late to fix it.

Thought {COMPANY} might find it useful to see how other teams are solving that. No rush on anything.

{MY_FIRST_NAME}`
  - fallback (322 chars): `Hi, appreciate the add.

I work with agencies on the ops and profitability side, specifically helping teams replace their disconnected tool stack with one platform that ties together projects, time tracking, budgets and invoicing.

Happy to share more if it is ever relevant to your setup. Good to be connected either way.`
- message at day 6.00, 3 variant(s):
  - variant 1 (310 chars, 54 words): `Hey {FIRST_NAME}, quick question for you.

What does {COMPANY} currently use to track project profitability in real time? Not after the work is done, I mean while a project is still live.

Asking because the answer tells me a lot about whether what I do would actually be useful to you or not.

{MY_FIRST_NAME}`
  - variant 2 (323 chars, 56 words): `Hey {FIRST_NAME}, wanted to ask you something directly.

How does {COMPANY} know if a project is going to hit its margin before it is finished? Is that something you can see at any point or does it only become clear after the fact?

Genuinely curious because the answer changes what I would share with you.

{MY_FIRST_NAME}`
  - variant 3 (276 chars, 49 words): `Hey {FIRST_NAME}, just a quick one.

When a project at {COMPANY} goes over budget who is the first person to find out and how do they find out?

Asking because that gap between when something goes wrong and when someone catches it is exactly what I help with.

{MY_FIRST_NAME}`
  - fallback (251 chars): `Hey, quick question.

How does your team currently track whether a project is going to hit its margin before it wraps up?

Not looking to pitch anything, I just find the answer changes a lot about whether what I do is even relevant. Genuinely curious.`
- message at day 15.00, 3 variant(s):
  - variant 1 (577 chars, 99 words): `Hey {FIRST_NAME}, wanted to share what I actually work with in case it is relevant.

The tool is called Productive. It is built for {INDUSTRY} agencies and brings project management, time tracking, budgets and invoicing into one place so the data connects automatically. Most {POSITION}s use it to get a clear picture of utilization and margin without pulling numbers from four different tools every time someone asks how a project is tracking.

{COMPANY} came to mind as a good fit. Would you be open to a 15 minute call to see how it maps to how you operate?

{MY_FIRST_NAME}`
  - variant 2 (467 chars, 75 words): `Hey {FIRST_NAME}, sharing this because I think it is actually relevant to {COMPANY}.

The platform is called Productive and it was built specifically for {INDUSTRY} businesses. It replaces the need to run separate tools for project management, time, budgets and invoicing by connecting all of it in one place. A {POSITION} can see live margin and utilization without anyone building a manual report.

Worth 15 minutes if you want to see it in action?

{MY_FIRST_NAME}`
  - variant 3 (475 chars, 76 words): `Hey {FIRST_NAME}, I should have mentioned this earlier.

The product I work with is Productive. It is an agency management platform that connects time tracking to budgets to invoicing so the financial picture updates automatically as work happens. Teams in {LOCATION} use it to replace Harvest, Asana and whatever spreadsheet is doing the reporting work right now.

Happy to walk you through how it works for a business like {COMPANY} if you have 15 minutes.

{MY_FIRST_NAME}`
  - fallback (442 chars): `Hey, wanted to share what I actually work with.

The tool is called Productive. It is an agency management platform that connects project management, time tracking, budgets and invoicing in one place so the data updates automatically rather than sitting in separate tools. Most agency owners and ops leads use it to get a live view of margin and utilization without manual reporting.

Worth a 15-minute call if you want to see how it works?

`
- message at day 23.00, 3 variant(s):
  - variant 1 (536 chars, 90 words): `Hey {FIRST_NAME}, one more thought and then I will leave it with you.

Most {INDUSTRY} agencies in {LOCATION} that switch to Productive end up replacing Harvest or Toggl for time, Monday or Asana for projects and whatever spreadsheet was doing the budget reporting. The reason it sticks is that the data finally connects rather than sitting in separate tools that someone at {COMPANY} has to reconcile by hand.

If that sounds familiar I am happy to send over a short walkthrough instead of a call if that feels easier.

{MY_FIRST_NAME}`
  - variant 2 (455 chars, 77 words): `Hey {FIRST_NAME}, circling back one more time.

The agencies in {LOCATION} that get the most out of Productive are usually running exactly the kind of setup {COMPANY} is likely running right now. Multiple tools that work fine on their own but do not talk to each other, so a {POSITION} ends up doing the connecting manually.

Productive removes that entirely. Happy to show you a quick walkthrough if a call feels like too much right now.

{MY_FIRST_NAME}`
  - variant 3 (467 chars, 85 words): `Hey {FIRST_NAME}, wanted to try a different angle.

The question I get most from {POSITION}s before they see Productive is something like how long does it take you to answer whether we made money on that project? At most agencies it takes a day or two of pulling data together. In Productive the answer is on screen in real time.

If that gap sounds familiar at {COMPANY} it is worth seeing. I can send a walkthrough if a call does not fit right now.

{MY_FIRST_NAME}`
  - fallback (444 chars): `Hey, one more thought before I leave it with you.

Most agencies that switch to Productive end up replacing Harvest or Toggl for time, Monday or Asana for projects and whatever spreadsheet was doing the budget reporting. The reason it sticks is that the data finally connects rather than sitting in separate tools someone has to reconcile by hand.

Happy to send a short walkthrough if you want to see how it works without committing to a call.`
- message at day 28.00, 4 variant(s):
  - variant 1 (431 chars, 75 words): `Hey {FIRST_NAME}, last message from me on this.

If the timing is off or it is just not relevant to where {COMPANY} is right now that is completely fine. I would rather know than keep nudging you.

If things change and getting a cleaner view of profitability and utilisation ever becomes a priority, Productive has a free 14 day trial at productive.io and you can explore it without having to talk to anyone first.

{MY_FIRST_NAME}`
  - variant 2 (385 chars, 66 words): `Hey {FIRST_NAME}, I have sent a few messages without hearing back so I will leave it here.

No hard feelings at all, timing is everything with this kind of thing. If {COMPANY} ever gets to a point where the tool stack becomes a real headache or you want better visibility into project margins, Productive is worth a look. Free trial at productive.io, no call required.

{MY_FIRST_NAME}`
  - variant 3 (385 chars, 66 words): `Hey {FIRST_NAME}, I have sent a few messages without hearing back so I will leave it here.

No hard feelings at all, timing is everything with this kind of thing. If {COMPANY} ever gets to a point where the tool stack becomes a real headache or you want better visibility into project margins, Productive is worth a look. Free trial at productive.io, no call required.

{MY_FIRST_NAME}`
  - variant 4 (357 chars, 62 words): `Hey {FIRST_NAME}, wrapping up my end of this.

I know these messages land at all kinds of bad times so no offence taken. If the problem I have been describing ever becomes urgent at {COMPANY} you can start a free trial of Productive at productive.io without talking to anyone. Wanted to make sure you had that before I stopped reaching out.

{MY_FIRST_NAME}`
  - fallback (306 chars): `Hey, last message from me on this.

No hard feelings if the timing has not been right. If things ever change and you want a cleaner way to track project profitability and team utilization, Productive is worth a look. Free 14 day trial at productive.io and you do not need to speak to anyone to get started.`

### 388942 — PRODUCTIVE - MARKETING AGENCIES - AUSTRALIA - CLEANED - ZVONIMIR v2

- ownership: **unknown** — not in the ledger and not on any operator-declared internal list; UNKNOWN is the state, not a gap
- provider status `PAUSED`; created `2026-04-08T14:59:39.830483Z`; started `2026-04-08T15:00:08.998058Z`
- seats (`campaignAccountIds`): 174892, 174748, 175455, 174742, 174332, 174822, 174803, 174797, 174810
- lead list `605364` (PRODUCTIVE - AUSTRALIA - ICP - FILTERED OUT OF 200K LEADS), list size `totalItemsCount` = 5133; campaign holds `progressStats.totalUsers` = 5133, finished 152
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **1650**, accepted **168** (10.18%)
  - messages sent **544**, message threads started **167**, replies **41** (24.55% of threads started)
  - unique leads contacted **1650**; profile views 4141, follows 1699, post likes 2439
  - provider's own tags: `autoTaggedInterested` **7**, `totalAutoTagged` **41**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 166 conversations joined, 8 operator-positive replies = **0.485 per 100 requests sent**
- reply classes in this campaign: `unknown` 29, `negative` 10, `automated` 8, `positive` 6, `question` 2, `not_relevant` 2, `objection` 1
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-04-17 .. 2026-09-09 (106 days)
- sequence node types present in the whole graph: CONNECTION_REQUEST, END, FOLLOW, LIKE_POST, MESSAGE, VIEW_PROFILE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   VIEW_PROFILE          wait 0H      day  0.00
  step 1   LIKE_POST             wait 3D      day  3.00
  step 2   FOLLOW                wait 3D      day  6.00
  step 3   CONNECTION_REQUEST    wait 3D      day  9.00
  step 4   MESSAGE               wait 3D      day 12.00
  step 5   LIKE_POST             wait 1D      day 13.00
  step 6   LIKE_POST             wait 4D      day 17.00
  step 7   MESSAGE               wait 1D      day 18.00
  step 8   VIEW_PROFILE          wait 1D      day 19.00
  step 9   VIEW_PROFILE          wait 1D      day 20.00
  step 10  LIKE_POST             wait 1D      day 21.00
  step 11  MESSAGE               wait 1D      day 22.00
  step 12  MESSAGE               wait 5D      day 27.00
  step 13  VIEW_PROFILE          wait 1D      day 28.00
  step 14  LIKE_POST             wait 1D      day 29.00
  step 15  MESSAGE               wait 1D      day 30.00
  step 16  END                   wait 1D      day 31.00
```

**Connection note:** 5 `CONNECTION_REQUEST` note slot(s), every one of them EMPTY — this campaign sends connection requests with no note.

**Message steps — our text, in full:**

- message at day 12.00, 3 variant(s):
  - variant 1 (607 chars, 105 words): `Hey {FIRST_NAME}, a colleague of mine probably reached out to you about Productive recently. I wanted to add my own note because {COMPANY} genuinely looks like a strong fit for what we do and I did not want it to get buried in a busy inbox.

I work with {INDUSTRY} agencies in {LOCATION} on the ops and profitability side. The short version is that Productive replaces the disconnected tool stack most agencies run on and gives a {POSITION} a real time view of project margins, utilization and forecasts in one place.

Worth a quick conversation to see if it maps to how {COMPANY} operates?

{MY_FIRST_NAME}`
  - variant 2 (429 chars, 74 words): `Hey {FIRST_NAME}, you may have already heard from someone on my team about Productive. I am reaching out separately because I look at the {INDUSTRY} space in {LOCATION} specifically and {COMPANY} keeps coming up as a business that would get a lot out of the platform.

Happy to give you a different perspective on it if the first message did not land at the right time. Sometimes it just takes the right framing.

{MY_FIRST_NAME}`
  - variant 3 (429 chars, 74 words): `Hey {FIRST_NAME}, one of my colleagues reached out to you about Productive recently. I am following up because I wanted to make this feel less like a blast and more like a real conversation.

I spend most of my time working with {POSITION}s at {INDUSTRY} agencies and the problems I hear consistently are the same ones Productive was built to solve. Thought it was worth one more shot before leaving it with you.

{MY_FIRST_NAME}`
  - fallback (453 chars): `Hey, a colleague of mine probably reached out recently about Productive. I wanted to follow up from my side because your agency looks like a strong fit for what we do, and I did not want it to get lost.

The short version is that Productive is an agency management platform that connects project management, time tracking, budgets, and invoicing so everything talks to each other. Happy to give you a fresh perspective on it if the timing is better now.`
- message at day 18.00, 3 variant(s):
  - variant 1 (392 chars, 66 words): `Hey {FIRST_NAME}, checking in to see if my last message landed.

Rather than send another pitch I wanted to ask a genuine question. When a project at {COMPANY} goes over budget or under delivers on margin, how long does it typically take before someone catches it?

The answer to that is usually what tells me whether Productive would actually change anything for you or not.

{MY_FIRST_NAME}`
  - variant 2 (328 chars, 52 words): `Hey {FIRST_NAME}, following up on my last note.

Quick question about {COMPANY}. How does your team currently know whether you are fully utilizing your people across projects? Not a trick question, I am asking because that visibility gap is exactly what most {INDUSTRY} agencies I work with are trying to close.

{MY_FIRST_NAME}`
  - variant 3 (297 chars, 52 words): `Hey {FIRST_NAME}, just circling back.

I will be straight with you. Between my colleague and I we have both reached out now and I think {COMPANY} is genuinely worth a conversation rather than just another follow up. What would make it worth 15 minutes of your time to take a look?

{MY_FIRST_NAME}`
  - fallback (247 chars): `Hey, just following up on my last message.

Rather than repeat the pitch I wanted to ask directly. What would need to be true about a tool for it to be worth 15 minutes of your time right now? Happy to tell you whether Productive fits that or not.`
- message at day 22.00, 3 variant(s):
  - variant 1 (544 chars, 93 words): `Hey {FIRST_NAME}, one more thought in case the timing is better now.

The thing most {POSITION}s at {INDUSTRY} agencies tell me after they see Productive is that they wish they had seen it before their last hire. The reason is that resourcing and growth decisions get made on utilization data and most agencies are working from numbers that are a month old and manually assembled.

Productive puts that in front of you in real time so the decisions at {COMPANY} are based on what is actually happening now.

Still worth a look?

{MY_FIRST_NAME}`
  - variant 2 (486 chars, 83 words): `Hey {FIRST_NAME}, trying a different angle this time.

Most {INDUSTRY} agencies in {LOCATION} that switch to Productive do it because of one specific moment. Someone asks how a project is tracking, the answer requires pulling from three different tools and an hour of work, and whoever is responsible decides there has to be a better way.

If that moment has not happened at {COMPANY} yet it probably will. Happy to show you what it looks like when it does not need to.

{MY_FIRST_NAME}`
  - variant 3 (282 chars, 51 words): `Hey {FIRST_NAME}, keeping this one short.

Productive has a 14 day free trial and no card required. If a call feels like too much of a commitment right now you can start at productive.io and see the platform on your own terms first.

Still here if you want to chat.

{MY_FIRST_NAME}`
  - fallback (440 chars): `Hey, trying a different angle this time.

The moment most agencies decide to switch to Productive is when someone asks a simple question about project profitability and the answer takes an hour to pull together from separate tools. If that has happened recently it is probably worth 15 minutes to see what it looks like when it does not.

Happy to set up a call or you can start a free trial at productive.io if you prefer to explore first.`
- message at day 27.00, 3 variant(s):
  - variant 1 (604 chars, 95 words): `Hey {FIRST_NAME}, sharing something specific in case it is useful.

{INDUSTRY} agencies in {LOCATION} that use Productive typically replace Harvest or Toggl for time tracking, Monday or Asana for project management and whatever spreadsheet was doing the budget reporting. The economics tend to work out well because they are paying for fewer tools and making better decisions with the data they were already capturing.

For a {POSITION} at {COMPANY} the main shift is that you stop being the person assembling the picture and start being the person who already has it.

Worth 15 minutes?

{MY_FIRST_NAME}`
  - variant 2 (566 chars, 99 words): `Hey {FIRST_NAME}, I realize I have sent a few messages now so I will make this one count.

The agencies that get the most out of Productive are the ones where a {POSITION} is spending real time each week on work that should happen automatically. Pulling utilization reports, reconciling budgets, chasing time logs, building invoices from scratch. Productive handles all of that so the focus shifts to what the data is telling you rather than how to get the data in the first place.

If any of that sounds like {COMPANY} right now it is worth a look.

{MY_FIRST_NAME}`
  - variant 3 (469 chars, 77 words): `Hey {FIRST_NAME}, last proper pitch from me before I wrap up.

Three things Productive does that most agency tools do not. Time tracked connects directly to budget burn so you see profit impact as work happens. Resource planning shows utilization across the whole team in real time. Invoicing pulls from actual project data so there is no manual assembly.

If {COMPANY} is doing any of those things manually right now that is the gap Productive closes.

{MY_FIRST_NAME}`
  - fallback (426 chars): `Hey, making this one specific.

Three things Productive does that most agency tools do not. Time tracked connects directly to budget burn so you see profit impact as work happens. Resource planning shows team utilization in real time. Invoicing pulls from actual project data so there is no manual assembly.

If your agency is doing any of those things manually right now that is the gap Productive closes. Worth 15 minutes?

`
- message at day 30.00, 3 variant(s):
  - variant 1 (402 chars, 72 words): `Hey {FIRST_NAME}, wrapping up from my end.

Between my colleague and I we have sent a handful of messages and I do not want to keep landing in your inbox if the timing is just not right for {COMPANY}. No hard feelings at all.

If it ever becomes relevant, Productive has a free trial at productive.io and you can explore it without talking to anyone first. Worth knowing that is there.

{MY_FIRST_NAME}`
  - variant 2 (297 chars, 51 words): `Hey {FIRST_NAME}, last one from me.

I get it, the timing might just not be right. If things change at {COMPANY} and getting a cleaner view of margins and utilization becomes a priority, feel free to reach out directly or start a free trial at productive.io.

Leaving it with you.

{MY_FIRST_NAME}`
  - variant 3 (350 chars, 62 words): `Hey {FIRST_NAME}, closing the loop on my end.

My colleague reached out, I followed up a few times and I think we have both made a reasonable case for why Productive could work well for {COMPANY}. At this point it is in your hands.

If the moment ever comes where the current setup stops working, productive.io is the place to start.

{MY_FIRST_NAME}`
  - fallback (305 chars): `Hey, last message from me on this.

My colleague and I have both reached out now and I do not want to keep taking up space in your inbox. If the timing is ever right, Productive has a free trial at productive.io and you do not need to speak to anyone to get started.

Thanks for bearing with the outreach.`

### 388947 — PRODUCTIVE - MARKETING AGENCIES SOFT - EUROPE - CLEANED - ZVONIMIR

- ownership: **unknown** — not in the ledger and not on any operator-declared internal list; UNKNOWN is the state, not a gap
- provider status `PAUSED`; created `2026-04-08T15:00:57.683954Z`; started `2026-04-08T15:01:31.890333Z`
- seats (`campaignAccountIds`): 174892, 174748, 175455, 174742, 174332, 174810, 174822, 174803, 174797, 174845
- lead list `605361` (PRODUCTIVE - EUROPE - ICP - FILTERED OUT OF 200K LEADS), list size `totalItemsCount` = 44157; campaign holds `progressStats.totalUsers` = 44157, finished 1091
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **0**, accepted **0** (n/a (denominator 0))
  - messages sent **0**, message threads started **0**, replies **0** (n/a (denominator 0) of threads started)
  - unique leads contacted **0**; profile views 7730, follows 3861, post likes 6928
  - provider's own tags: `autoTaggedInterested` **0**, `totalAutoTagged` **0**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 0 conversations joined, 0 operator-positive replies = **n/a (0 requests sent) per 100 requests sent**
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- sequence node types present in the whole graph: END, FOLLOW, LIKE_POST, VIEW_PROFILE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   VIEW_PROFILE          wait 0H      day  0.00
  step 1   FOLLOW                wait 10D     day 10.00
  step 2   LIKE_POST             wait 10D     day 20.00
  step 3   VIEW_PROFILE          wait 10D     day 30.00
  step 4   LIKE_POST             wait 10D     day 40.00
  step 5   LIKE_POST             wait 10D     day 50.00
  step 6   LIKE_POST             wait 10D     day 60.00
  step 7   VIEW_PROFILE          wait 10D     day 70.00
  step 8   END                   wait 1D      day 71.00
```

**Connection note:** this graph has no `CONNECTION_REQUEST` node, so no note is sent.


### 388949 — PRODUCTIVE - MARKETING AGENCIES - EUROPE - CLEANED - ZVONIMIR

- ownership: **unknown** — not in the ledger and not on any operator-declared internal list; UNKNOWN is the state, not a gap
- provider status `PAUSED`; created `2026-04-08T15:01:44.29938Z`; started `2026-04-08T15:02:10.190528Z`
- seats (`campaignAccountIds`): 174892, 174748, 175455, 174742, 174332, 174822, 174803, 174797, 174845
- lead list `605361` (PRODUCTIVE - EUROPE - ICP - FILTERED OUT OF 200K LEADS), list size `totalItemsCount` = 44157; campaign holds `progressStats.totalUsers` = 44157, finished 864
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **6890**, accepted **1256** (18.23%)
  - messages sent **3758**, message threads started **1164**, replies **246** (21.13% of threads started)
  - unique leads contacted **6833**; profile views 3345, follows 0, post likes 4427
  - provider's own tags: `autoTaggedInterested` **53**, `totalAutoTagged` **247**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 1257 conversations joined, 23 operator-positive replies = **0.334 per 100 requests sent**
- reply classes in this campaign: `unknown` 241, `negative` 47, `positive` 19, `automated` 19, `not_relevant` 10, `objection` 9, `out_of_office` 8, `unsubscribe` 6, `question` 4, `not_now` 1
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-04-08 .. 2026-09-30 (128 days)
- sequence node types present in the whole graph: CONNECTION_REQUEST, END, INMAIL, LIKE_POST, MESSAGE, VIEW_PROFILE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CONNECTION_REQUEST    wait 0H      day  0.00
  step 1   MESSAGE               wait 3D      day  3.00
  step 2   VIEW_PROFILE          wait 1D      day  4.00
  step 3   LIKE_POST             wait 1D      day  5.00
  step 4   MESSAGE               wait 1D      day  6.00
  step 5   LIKE_POST             wait 4D      day 10.00
  step 6   VIEW_PROFILE          wait 4D      day 14.00
  step 7   MESSAGE               wait 1D      day 15.00
  step 8   LIKE_POST             wait 7D      day 22.00
  step 9   MESSAGE               wait 1D      day 23.00
  step 10  VIEW_PROFILE          wait 4D      day 27.00
  step 11  MESSAGE               wait 1D      day 28.00
  step 12  VIEW_PROFILE          wait 1D      day 29.00
  step 13  LIKE_POST             wait 1D      day 30.00
  step 14  END                   wait 1D      day 31.00
```

**Connection note:** 1 `CONNECTION_REQUEST` note slot(s), every one of them EMPTY — this campaign sends connection requests with no note.

**Message steps — our text, in full:**

- message at day 3.00, 3 variant(s):
  - variant 1 (510 chars, 80 words): `Hi {FIRST_NAME}, appreciate the add.

I help {INDUSTRY} agencies in {LOCATION} replace the usual pile of disconnected tools with one platform that ties together projects, time tracking, budgets and invoicing. The idea being that a {POSITION} can actually see whether a project is profitable while it is still running rather than finding out after the invoice goes out.

Thought {COMPANY} might be worth a conversation at some point. No pressure on that though, good to be connected either way.

{MY_FIRST_NAME}`
  - variant 2 (374 chars, 60 words): `Hey {FIRST_NAME}, thanks for connecting.

I work with {INDUSTRY} agencies on the ops side, specifically helping teams get a real time view of project profitability and utilization without juggling five different tools to do it. Given what you are doing at {COMPANY} I thought it could be relevant at some point.

Happy to share more whenever it makes sense.

{MY_FIRST_NAME}`
  - variant 3 (376 chars, 65 words): `Hi {FIRST_NAME}, good to be connected.

I spend most of my time working with {INDUSTRY} agencies on the gap between time logged and money made. Most {POSITION}s I speak with know something is leaking but cannot pinpoint where until it is too late to fix it.

Thought {COMPANY} might find it useful to see how other teams are solving that. No rush on anything.

{MY_FIRST_NAME}`
  - fallback (322 chars): `Hi, appreciate the add.

I work with agencies on the ops and profitability side, specifically helping teams replace their disconnected tool stack with one platform that ties together projects, time tracking, budgets and invoicing.

Happy to share more if it is ever relevant to your setup. Good to be connected either way.`
- message at day 6.00, 3 variant(s):
  - variant 1 (310 chars, 54 words): `Hey {FIRST_NAME}, quick question for you.

What does {COMPANY} currently use to track project profitability in real time? Not after the work is done, I mean while a project is still live.

Asking because the answer tells me a lot about whether what I do would actually be useful to you or not.

{MY_FIRST_NAME}`
  - variant 2 (323 chars, 56 words): `Hey {FIRST_NAME}, wanted to ask you something directly.

How does {COMPANY} know if a project is going to hit its margin before it is finished? Is that something you can see at any point or does it only become clear after the fact?

Genuinely curious because the answer changes what I would share with you.

{MY_FIRST_NAME}`
  - variant 3 (276 chars, 49 words): `Hey {FIRST_NAME}, just a quick one.

When a project at {COMPANY} goes over budget who is the first person to find out and how do they find out?

Asking because that gap between when something goes wrong and when someone catches it is exactly what I help with.

{MY_FIRST_NAME}`
  - fallback (251 chars): `Hey, quick question.

How does your team currently track whether a project is going to hit its margin before it wraps up?

Not looking to pitch anything, I just find the answer changes a lot about whether what I do is even relevant. Genuinely curious.`
- message at day 15.00, 3 variant(s):
  - variant 1 (577 chars, 99 words): `Hey {FIRST_NAME}, wanted to share what I actually work with in case it is relevant.

The tool is called Productive. It is built for {INDUSTRY} agencies and brings project management, time tracking, budgets and invoicing into one place so the data connects automatically. Most {POSITION}s use it to get a clear picture of utilization and margin without pulling numbers from four different tools every time someone asks how a project is tracking.

{COMPANY} came to mind as a good fit. Would you be open to a 15 minute call to see how it maps to how you operate?

{MY_FIRST_NAME}`
  - variant 2 (467 chars, 75 words): `Hey {FIRST_NAME}, sharing this because I think it is actually relevant to {COMPANY}.

The platform is called Productive and it was built specifically for {INDUSTRY} businesses. It replaces the need to run separate tools for project management, time, budgets and invoicing by connecting all of it in one place. A {POSITION} can see live margin and utilization without anyone building a manual report.

Worth 15 minutes if you want to see it in action?

{MY_FIRST_NAME}`
  - variant 3 (475 chars, 76 words): `Hey {FIRST_NAME}, I should have mentioned this earlier.

The product I work with is Productive. It is an agency management platform that connects time tracking to budgets to invoicing so the financial picture updates automatically as work happens. Teams in {LOCATION} use it to replace Harvest, Asana and whatever spreadsheet is doing the reporting work right now.

Happy to walk you through how it works for a business like {COMPANY} if you have 15 minutes.

{MY_FIRST_NAME}`
  - fallback (442 chars): `Hey, wanted to share what I actually work with.

The tool is called Productive. It is an agency management platform that connects project management, time tracking, budgets and invoicing in one place so the data updates automatically rather than sitting in separate tools. Most agency owners and ops leads use it to get a live view of margin and utilization without manual reporting.

Worth a 15-minute call if you want to see how it works?

`
- message at day 23.00, 3 variant(s):
  - variant 1 (536 chars, 90 words): `Hey {FIRST_NAME}, one more thought and then I will leave it with you.

Most {INDUSTRY} agencies in {LOCATION} that switch to Productive end up replacing Harvest or Toggl for time, Monday or Asana for projects and whatever spreadsheet was doing the budget reporting. The reason it sticks is that the data finally connects rather than sitting in separate tools that someone at {COMPANY} has to reconcile by hand.

If that sounds familiar I am happy to send over a short walkthrough instead of a call if that feels easier.

{MY_FIRST_NAME}`
  - variant 2 (455 chars, 77 words): `Hey {FIRST_NAME}, circling back one more time.

The agencies in {LOCATION} that get the most out of Productive are usually running exactly the kind of setup {COMPANY} is likely running right now. Multiple tools that work fine on their own but do not talk to each other, so a {POSITION} ends up doing the connecting manually.

Productive removes that entirely. Happy to show you a quick walkthrough if a call feels like too much right now.

{MY_FIRST_NAME}`
  - variant 3 (467 chars, 85 words): `Hey {FIRST_NAME}, wanted to try a different angle.

The question I get most from {POSITION}s before they see Productive is something like how long does it take you to answer whether we made money on that project? At most agencies it takes a day or two of pulling data together. In Productive the answer is on screen in real time.

If that gap sounds familiar at {COMPANY} it is worth seeing. I can send a walkthrough if a call does not fit right now.

{MY_FIRST_NAME}`
  - fallback (444 chars): `Hey, one more thought before I leave it with you.

Most agencies that switch to Productive end up replacing Harvest or Toggl for time, Monday or Asana for projects and whatever spreadsheet was doing the budget reporting. The reason it sticks is that the data finally connects rather than sitting in separate tools someone has to reconcile by hand.

Happy to send a short walkthrough if you want to see how it works without committing to a call.`
- message at day 28.00, 4 variant(s):
  - variant 1 (431 chars, 75 words): `Hey {FIRST_NAME}, last message from me on this.

If the timing is off or it is just not relevant to where {COMPANY} is right now that is completely fine. I would rather know than keep nudging you.

If things change and getting a cleaner view of profitability and utilisation ever becomes a priority, Productive has a free 14 day trial at productive.io and you can explore it without having to talk to anyone first.

{MY_FIRST_NAME}`
  - variant 2 (385 chars, 66 words): `Hey {FIRST_NAME}, I have sent a few messages without hearing back so I will leave it here.

No hard feelings at all, timing is everything with this kind of thing. If {COMPANY} ever gets to a point where the tool stack becomes a real headache or you want better visibility into project margins, Productive is worth a look. Free trial at productive.io, no call required.

{MY_FIRST_NAME}`
  - variant 3 (385 chars, 66 words): `Hey {FIRST_NAME}, I have sent a few messages without hearing back so I will leave it here.

No hard feelings at all, timing is everything with this kind of thing. If {COMPANY} ever gets to a point where the tool stack becomes a real headache or you want better visibility into project margins, Productive is worth a look. Free trial at productive.io, no call required.

{MY_FIRST_NAME}`
  - variant 4 (357 chars, 62 words): `Hey {FIRST_NAME}, wrapping up my end of this.

I know these messages land at all kinds of bad times so no offence taken. If the problem I have been describing ever becomes urgent at {COMPANY} you can start a free trial of Productive at productive.io without talking to anyone. Wanted to make sure you had that before I stopped reaching out.

{MY_FIRST_NAME}`
  - fallback (306 chars): `Hey, last message from me on this.

No hard feelings if the timing has not been right. If things ever change and you want a cleaner way to track project profitability and team utilization, Productive is worth a look. Free 14 day trial at productive.io and you do not need to speak to anyone to get started.`

### 388951 — PRODUCTIVE - MARKETING AGENCIES - EUROPE - CLEANED - ZVONIMIR V3

- ownership: **unknown** — not in the ledger and not on any operator-declared internal list; UNKNOWN is the state, not a gap
- provider status `PAUSED`; created `2026-04-08T15:02:20.548163Z`; started `2026-04-08T15:02:44.547279Z`
- seats (`campaignAccountIds`): 174892, 174748, 175455, 174742, 174332, 174822, 174803, 174797, 174810, 174845
- lead list `605361` (PRODUCTIVE - EUROPE - ICP - FILTERED OUT OF 200K LEADS), list size `totalItemsCount` = 44157; campaign holds `progressStats.totalUsers` = 44157, finished 78
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **1219**, accepted **275** (22.56%)
  - messages sent **374**, message threads started **205**, replies **41** (20.00% of threads started)
  - unique leads contacted **1219**; profile views 2240, follows 1466, post likes 2195
  - provider's own tags: `autoTaggedInterested` **3**, `totalAutoTagged` **41**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 302 conversations joined, 3 operator-positive replies = **0.246 per 100 requests sent**
- reply classes in this campaign: `unknown` 38, `negative` 9, `not_relevant` 3, `objection` 3, `question` 2, `unsubscribe` 2, `not_now` 1, `out_of_office` 1, `positive` 1, `automated` 1
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-04-17 .. 2026-10-02 (45 days)
- sequence node types present in the whole graph: CONNECTION_REQUEST, END, FOLLOW, LIKE_POST, MESSAGE, VIEW_PROFILE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   VIEW_PROFILE          wait 0H      day  0.00
  step 1   LIKE_POST             wait 3D      day  3.00
  step 2   FOLLOW                wait 3D      day  6.00
  step 3   CONNECTION_REQUEST    wait 3D      day  9.00
  step 4   MESSAGE               wait 3D      day 12.00
  step 5   LIKE_POST             wait 1D      day 13.00
  step 6   LIKE_POST             wait 4D      day 17.00
  step 7   MESSAGE               wait 1D      day 18.00
  step 8   VIEW_PROFILE          wait 1D      day 19.00
  step 9   VIEW_PROFILE          wait 1D      day 20.00
  step 10  LIKE_POST             wait 1D      day 21.00
  step 11  MESSAGE               wait 1D      day 22.00
  step 12  MESSAGE               wait 5D      day 27.00
  step 13  VIEW_PROFILE          wait 1D      day 28.00
  step 14  LIKE_POST             wait 1D      day 29.00
  step 15  MESSAGE               wait 1D      day 30.00
  step 16  END                   wait 1D      day 31.00
```

**Connection note:** 5 `CONNECTION_REQUEST` note slot(s), every one of them EMPTY — this campaign sends connection requests with no note.

**Message steps — our text, in full:**

- message at day 12.00, 3 variant(s):
  - variant 1 (607 chars, 105 words): `Hey {FIRST_NAME}, a colleague of mine probably reached out to you about Productive recently. I wanted to add my own note because {COMPANY} genuinely looks like a strong fit for what we do and I did not want it to get buried in a busy inbox.

I work with {INDUSTRY} agencies in {LOCATION} on the ops and profitability side. The short version is that Productive replaces the disconnected tool stack most agencies run on and gives a {POSITION} a real time view of project margins, utilization and forecasts in one place.

Worth a quick conversation to see if it maps to how {COMPANY} operates?

{MY_FIRST_NAME}`
  - variant 2 (429 chars, 74 words): `Hey {FIRST_NAME}, you may have already heard from someone on my team about Productive. I am reaching out separately because I look at the {INDUSTRY} space in {LOCATION} specifically and {COMPANY} keeps coming up as a business that would get a lot out of the platform.

Happy to give you a different perspective on it if the first message did not land at the right time. Sometimes it just takes the right framing.

{MY_FIRST_NAME}`
  - variant 3 (429 chars, 74 words): `Hey {FIRST_NAME}, one of my colleagues reached out to you about Productive recently. I am following up because I wanted to make this feel less like a blast and more like a real conversation.

I spend most of my time working with {POSITION}s at {INDUSTRY} agencies and the problems I hear consistently are the same ones Productive was built to solve. Thought it was worth one more shot before leaving it with you.

{MY_FIRST_NAME}`
  - fallback (453 chars): `Hey, a colleague of mine probably reached out recently about Productive. I wanted to follow up from my side because your agency looks like a strong fit for what we do, and I did not want it to get lost.

The short version is that Productive is an agency management platform that connects project management, time tracking, budgets, and invoicing so everything talks to each other. Happy to give you a fresh perspective on it if the timing is better now.`
- message at day 18.00, 3 variant(s):
  - variant 1 (392 chars, 66 words): `Hey {FIRST_NAME}, checking in to see if my last message landed.

Rather than send another pitch I wanted to ask a genuine question. When a project at {COMPANY} goes over budget or under delivers on margin, how long does it typically take before someone catches it?

The answer to that is usually what tells me whether Productive would actually change anything for you or not.

{MY_FIRST_NAME}`
  - variant 2 (328 chars, 52 words): `Hey {FIRST_NAME}, following up on my last note.

Quick question about {COMPANY}. How does your team currently know whether you are fully utilizing your people across projects? Not a trick question, I am asking because that visibility gap is exactly what most {INDUSTRY} agencies I work with are trying to close.

{MY_FIRST_NAME}`
  - variant 3 (297 chars, 52 words): `Hey {FIRST_NAME}, just circling back.

I will be straight with you. Between my colleague and I we have both reached out now and I think {COMPANY} is genuinely worth a conversation rather than just another follow up. What would make it worth 15 minutes of your time to take a look?

{MY_FIRST_NAME}`
  - fallback (247 chars): `Hey, just following up on my last message.

Rather than repeat the pitch I wanted to ask directly. What would need to be true about a tool for it to be worth 15 minutes of your time right now? Happy to tell you whether Productive fits that or not.`
- message at day 22.00, 3 variant(s):
  - variant 1 (544 chars, 93 words): `Hey {FIRST_NAME}, one more thought in case the timing is better now.

The thing most {POSITION}s at {INDUSTRY} agencies tell me after they see Productive is that they wish they had seen it before their last hire. The reason is that resourcing and growth decisions get made on utilization data and most agencies are working from numbers that are a month old and manually assembled.

Productive puts that in front of you in real time so the decisions at {COMPANY} are based on what is actually happening now.

Still worth a look?

{MY_FIRST_NAME}`
  - variant 2 (486 chars, 83 words): `Hey {FIRST_NAME}, trying a different angle this time.

Most {INDUSTRY} agencies in {LOCATION} that switch to Productive do it because of one specific moment. Someone asks how a project is tracking, the answer requires pulling from three different tools and an hour of work, and whoever is responsible decides there has to be a better way.

If that moment has not happened at {COMPANY} yet it probably will. Happy to show you what it looks like when it does not need to.

{MY_FIRST_NAME}`
  - variant 3 (282 chars, 51 words): `Hey {FIRST_NAME}, keeping this one short.

Productive has a 14 day free trial and no card required. If a call feels like too much of a commitment right now you can start at productive.io and see the platform on your own terms first.

Still here if you want to chat.

{MY_FIRST_NAME}`
  - fallback (440 chars): `Hey, trying a different angle this time.

The moment most agencies decide to switch to Productive is when someone asks a simple question about project profitability and the answer takes an hour to pull together from separate tools. If that has happened recently it is probably worth 15 minutes to see what it looks like when it does not.

Happy to set up a call or you can start a free trial at productive.io if you prefer to explore first.`
- message at day 27.00, 3 variant(s):
  - variant 1 (604 chars, 95 words): `Hey {FIRST_NAME}, sharing something specific in case it is useful.

{INDUSTRY} agencies in {LOCATION} that use Productive typically replace Harvest or Toggl for time tracking, Monday or Asana for project management and whatever spreadsheet was doing the budget reporting. The economics tend to work out well because they are paying for fewer tools and making better decisions with the data they were already capturing.

For a {POSITION} at {COMPANY} the main shift is that you stop being the person assembling the picture and start being the person who already has it.

Worth 15 minutes?

{MY_FIRST_NAME}`
  - variant 2 (566 chars, 99 words): `Hey {FIRST_NAME}, I realize I have sent a few messages now so I will make this one count.

The agencies that get the most out of Productive are the ones where a {POSITION} is spending real time each week on work that should happen automatically. Pulling utilization reports, reconciling budgets, chasing time logs, building invoices from scratch. Productive handles all of that so the focus shifts to what the data is telling you rather than how to get the data in the first place.

If any of that sounds like {COMPANY} right now it is worth a look.

{MY_FIRST_NAME}`
  - variant 3 (469 chars, 77 words): `Hey {FIRST_NAME}, last proper pitch from me before I wrap up.

Three things Productive does that most agency tools do not. Time tracked connects directly to budget burn so you see profit impact as work happens. Resource planning shows utilization across the whole team in real time. Invoicing pulls from actual project data so there is no manual assembly.

If {COMPANY} is doing any of those things manually right now that is the gap Productive closes.

{MY_FIRST_NAME}`
  - fallback (426 chars): `Hey, making this one specific.

Three things Productive does that most agency tools do not. Time tracked connects directly to budget burn so you see profit impact as work happens. Resource planning shows team utilization in real time. Invoicing pulls from actual project data so there is no manual assembly.

If your agency is doing any of those things manually right now that is the gap Productive closes. Worth 15 minutes?

`
- message at day 30.00, 3 variant(s):
  - variant 1 (402 chars, 72 words): `Hey {FIRST_NAME}, wrapping up from my end.

Between my colleague and I we have sent a handful of messages and I do not want to keep landing in your inbox if the timing is just not right for {COMPANY}. No hard feelings at all.

If it ever becomes relevant, Productive has a free trial at productive.io and you can explore it without talking to anyone first. Worth knowing that is there.

{MY_FIRST_NAME}`
  - variant 2 (297 chars, 51 words): `Hey {FIRST_NAME}, last one from me.

I get it, the timing might just not be right. If things change at {COMPANY} and getting a cleaner view of margins and utilization becomes a priority, feel free to reach out directly or start a free trial at productive.io.

Leaving it with you.

{MY_FIRST_NAME}`
  - variant 3 (350 chars, 62 words): `Hey {FIRST_NAME}, closing the loop on my end.

My colleague reached out, I followed up a few times and I think we have both made a reasonable case for why Productive could work well for {COMPANY}. At this point it is in your hands.

If the moment ever comes where the current setup stops working, productive.io is the place to start.

{MY_FIRST_NAME}`
  - fallback (305 chars): `Hey, last message from me on this.

My colleague and I have both reached out now and I do not want to keep taking up space in your inbox. If the timing is ever right, Productive has a free trial at productive.io and you do not need to speak to anyone to get started.

Thanks for bearing with the outreach.`

### 388952 — PRODUCTIVE - MARKETING AGENCIES - USA 1- CLEANED - ZVONIMIR

- ownership: **unknown** — not in the ledger and not on any operator-declared internal list; UNKNOWN is the state, not a gap
- provider status `PAUSED`; created `2026-04-08T15:03:17.594688Z`; started `2026-04-08T15:03:31.926418Z`
- seats (`campaignAccountIds`): 174892, 174748, 175455, 174742, 174332, 174810, 174822, 174803, 174797, 174845
- lead list `605355` (PRODUCTIVE - USA 1ST - ICP - FILTERED OUT OF 200K LEADS), list size `totalItemsCount` = 50563; campaign holds `progressStats.totalUsers` = 50563, finished 692
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **0**, accepted **0** (n/a (denominator 0))
  - messages sent **0**, message threads started **0**, replies **0** (n/a (denominator 0) of threads started)
  - unique leads contacted **0**; profile views 6433, follows 3236, post likes 5172
  - provider's own tags: `autoTaggedInterested` **0**, `totalAutoTagged` **0**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 0 conversations joined, 0 operator-positive replies = **n/a (0 requests sent) per 100 requests sent**
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- sequence node types present in the whole graph: END, FOLLOW, LIKE_POST, VIEW_PROFILE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   VIEW_PROFILE          wait 0H      day  0.00
  step 1   FOLLOW                wait 10D     day 10.00
  step 2   LIKE_POST             wait 10D     day 20.00
  step 3   VIEW_PROFILE          wait 10D     day 30.00
  step 4   LIKE_POST             wait 10D     day 40.00
  step 5   LIKE_POST             wait 10D     day 50.00
  step 6   LIKE_POST             wait 10D     day 60.00
  step 7   VIEW_PROFILE          wait 10D     day 70.00
  step 8   END                   wait 1D      day 71.00
```

**Connection note:** this graph has no `CONNECTION_REQUEST` node, so no note is sent.


### 388953 — PRODUCTIVE - MARKETING AGENCIES - USA 1 ST- CLEANED - ZVONIMIR V2

- ownership: **unknown** — not in the ledger and not on any operator-declared internal list; UNKNOWN is the state, not a gap
- provider status `PAUSED`; created `2026-04-08T15:03:51.243069Z`; started `2026-04-08T15:04:07.356314Z`
- seats (`campaignAccountIds`): 174892, 174748, 175455, 174742, 174332, 174822, 174803, 174797, 174845
- lead list `605355` (PRODUCTIVE - USA 1ST - ICP - FILTERED OUT OF 200K LEADS), list size `totalItemsCount` = 50563; campaign holds `progressStats.totalUsers` = 50563, finished 59
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **1634**, accepted **172** (10.53%)
  - messages sent **436**, message threads started **184**, replies **27** (14.67% of threads started)
  - unique leads contacted **1634**; profile views 312, follows 0, post likes 1019
  - provider's own tags: `autoTaggedInterested` **12**, `totalAutoTagged` **27**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 186 conversations joined, 7 operator-positive replies = **0.428 per 100 requests sent**
- reply classes in this campaign: `unknown` 24, `positive` 6, `negative` 6, `automated` 2, `not_now` 1, `unsubscribe` 1, `question` 1
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-04-10 .. 2026-09-01 (47 days)
- sequence node types present in the whole graph: CONNECTION_REQUEST, END, INMAIL, LIKE_POST, MESSAGE, VIEW_PROFILE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CONNECTION_REQUEST    wait 0H      day  0.00
  step 1   MESSAGE               wait 3D      day  3.00
  step 2   VIEW_PROFILE          wait 1D      day  4.00
  step 3   LIKE_POST             wait 1D      day  5.00
  step 4   MESSAGE               wait 1D      day  6.00
  step 5   LIKE_POST             wait 4D      day 10.00
  step 6   VIEW_PROFILE          wait 4D      day 14.00
  step 7   MESSAGE               wait 1D      day 15.00
  step 8   LIKE_POST             wait 7D      day 22.00
  step 9   MESSAGE               wait 1D      day 23.00
  step 10  VIEW_PROFILE          wait 4D      day 27.00
  step 11  MESSAGE               wait 1D      day 28.00
  step 12  VIEW_PROFILE          wait 1D      day 29.00
  step 13  LIKE_POST             wait 1D      day 30.00
  step 14  END                   wait 1D      day 31.00
```

**Connection note — our text, in full (3 variant(s)):**

1. (164 chars, 22 words) `Hi {FIRST_NAME}, came across {COMPANY} while exploring {INDUSTRY} businesses in {LOCATION}. Would love to connect and follow what you are building.

{MY_FIRST_NAME}`
2. (173 chars, 26 words) `Hi {FIRST_NAME}, saw {COMPANY} pop up while looking at {INDUSTRY} agencies in {LOCATION}. Looks like interesting work, would love to have you in my network.

{MY_FIRST_NAME}`
3. (173 chars, 23 words) `Hi {FIRST_NAME}, found {COMPANY} while browsing {INDUSTRY} businesses in {LOCATION}. Always good to connect with people doing interesting work in the space.

{MY_FIRST_NAME}`

**Message steps — our text, in full:**

- message at day 3.00, 3 variant(s):
  - variant 1 (510 chars, 80 words): `Hi {FIRST_NAME}, appreciate the add.

I help {INDUSTRY} agencies in {LOCATION} replace the usual pile of disconnected tools with one platform that ties together projects, time tracking, budgets and invoicing. The idea being that a {POSITION} can actually see whether a project is profitable while it is still running rather than finding out after the invoice goes out.

Thought {COMPANY} might be worth a conversation at some point. No pressure on that though, good to be connected either way.

{MY_FIRST_NAME}`
  - variant 2 (374 chars, 60 words): `Hey {FIRST_NAME}, thanks for connecting.

I work with {INDUSTRY} agencies on the ops side, specifically helping teams get a real time view of project profitability and utilization without juggling five different tools to do it. Given what you are doing at {COMPANY} I thought it could be relevant at some point.

Happy to share more whenever it makes sense.

{MY_FIRST_NAME}`
  - variant 3 (376 chars, 65 words): `Hi {FIRST_NAME}, good to be connected.

I spend most of my time working with {INDUSTRY} agencies on the gap between time logged and money made. Most {POSITION}s I speak with know something is leaking but cannot pinpoint where until it is too late to fix it.

Thought {COMPANY} might find it useful to see how other teams are solving that. No rush on anything.

{MY_FIRST_NAME}`
  - fallback (322 chars): `Hi, appreciate the add.

I work with agencies on the ops and profitability side, specifically helping teams replace their disconnected tool stack with one platform that ties together projects, time tracking, budgets and invoicing.

Happy to share more if it is ever relevant to your setup. Good to be connected either way.`
- message at day 6.00, 3 variant(s):
  - variant 1 (310 chars, 54 words): `Hey {FIRST_NAME}, quick question for you.

What does {COMPANY} currently use to track project profitability in real time? Not after the work is done, I mean while a project is still live.

Asking because the answer tells me a lot about whether what I do would actually be useful to you or not.

{MY_FIRST_NAME}`
  - variant 2 (323 chars, 56 words): `Hey {FIRST_NAME}, wanted to ask you something directly.

How does {COMPANY} know if a project is going to hit its margin before it is finished? Is that something you can see at any point or does it only become clear after the fact?

Genuinely curious because the answer changes what I would share with you.

{MY_FIRST_NAME}`
  - variant 3 (276 chars, 49 words): `Hey {FIRST_NAME}, just a quick one.

When a project at {COMPANY} goes over budget who is the first person to find out and how do they find out?

Asking because that gap between when something goes wrong and when someone catches it is exactly what I help with.

{MY_FIRST_NAME}`
  - fallback (251 chars): `Hey, quick question.

How does your team currently track whether a project is going to hit its margin before it wraps up?

Not looking to pitch anything, I just find the answer changes a lot about whether what I do is even relevant. Genuinely curious.`
- message at day 15.00, 3 variant(s):
  - variant 1 (577 chars, 99 words): `Hey {FIRST_NAME}, wanted to share what I actually work with in case it is relevant.

The tool is called Productive. It is built for {INDUSTRY} agencies and brings project management, time tracking, budgets and invoicing into one place so the data connects automatically. Most {POSITION}s use it to get a clear picture of utilization and margin without pulling numbers from four different tools every time someone asks how a project is tracking.

{COMPANY} came to mind as a good fit. Would you be open to a 15 minute call to see how it maps to how you operate?

{MY_FIRST_NAME}`
  - variant 2 (467 chars, 75 words): `Hey {FIRST_NAME}, sharing this because I think it is actually relevant to {COMPANY}.

The platform is called Productive and it was built specifically for {INDUSTRY} businesses. It replaces the need to run separate tools for project management, time, budgets and invoicing by connecting all of it in one place. A {POSITION} can see live margin and utilization without anyone building a manual report.

Worth 15 minutes if you want to see it in action?

{MY_FIRST_NAME}`
  - variant 3 (475 chars, 76 words): `Hey {FIRST_NAME}, I should have mentioned this earlier.

The product I work with is Productive. It is an agency management platform that connects time tracking to budgets to invoicing so the financial picture updates automatically as work happens. Teams in {LOCATION} use it to replace Harvest, Asana and whatever spreadsheet is doing the reporting work right now.

Happy to walk you through how it works for a business like {COMPANY} if you have 15 minutes.

{MY_FIRST_NAME}`
  - fallback (442 chars): `Hey, wanted to share what I actually work with.

The tool is called Productive. It is an agency management platform that connects project management, time tracking, budgets and invoicing in one place so the data updates automatically rather than sitting in separate tools. Most agency owners and ops leads use it to get a live view of margin and utilization without manual reporting.

Worth a 15-minute call if you want to see how it works?

`
- message at day 23.00, 3 variant(s):
  - variant 1 (536 chars, 90 words): `Hey {FIRST_NAME}, one more thought and then I will leave it with you.

Most {INDUSTRY} agencies in {LOCATION} that switch to Productive end up replacing Harvest or Toggl for time, Monday or Asana for projects and whatever spreadsheet was doing the budget reporting. The reason it sticks is that the data finally connects rather than sitting in separate tools that someone at {COMPANY} has to reconcile by hand.

If that sounds familiar I am happy to send over a short walkthrough instead of a call if that feels easier.

{MY_FIRST_NAME}`
  - variant 2 (455 chars, 77 words): `Hey {FIRST_NAME}, circling back one more time.

The agencies in {LOCATION} that get the most out of Productive are usually running exactly the kind of setup {COMPANY} is likely running right now. Multiple tools that work fine on their own but do not talk to each other, so a {POSITION} ends up doing the connecting manually.

Productive removes that entirely. Happy to show you a quick walkthrough if a call feels like too much right now.

{MY_FIRST_NAME}`
  - variant 3 (467 chars, 85 words): `Hey {FIRST_NAME}, wanted to try a different angle.

The question I get most from {POSITION}s before they see Productive is something like how long does it take you to answer whether we made money on that project? At most agencies it takes a day or two of pulling data together. In Productive the answer is on screen in real time.

If that gap sounds familiar at {COMPANY} it is worth seeing. I can send a walkthrough if a call does not fit right now.

{MY_FIRST_NAME}`
  - fallback (444 chars): `Hey, one more thought before I leave it with you.

Most agencies that switch to Productive end up replacing Harvest or Toggl for time, Monday or Asana for projects and whatever spreadsheet was doing the budget reporting. The reason it sticks is that the data finally connects rather than sitting in separate tools someone has to reconcile by hand.

Happy to send a short walkthrough if you want to see how it works without committing to a call.`
- message at day 28.00, 4 variant(s):
  - variant 1 (431 chars, 75 words): `Hey {FIRST_NAME}, last message from me on this.

If the timing is off or it is just not relevant to where {COMPANY} is right now that is completely fine. I would rather know than keep nudging you.

If things change and getting a cleaner view of profitability and utilisation ever becomes a priority, Productive has a free 14 day trial at productive.io and you can explore it without having to talk to anyone first.

{MY_FIRST_NAME}`
  - variant 2 (385 chars, 66 words): `Hey {FIRST_NAME}, I have sent a few messages without hearing back so I will leave it here.

No hard feelings at all, timing is everything with this kind of thing. If {COMPANY} ever gets to a point where the tool stack becomes a real headache or you want better visibility into project margins, Productive is worth a look. Free trial at productive.io, no call required.

{MY_FIRST_NAME}`
  - variant 3 (385 chars, 66 words): `Hey {FIRST_NAME}, I have sent a few messages without hearing back so I will leave it here.

No hard feelings at all, timing is everything with this kind of thing. If {COMPANY} ever gets to a point where the tool stack becomes a real headache or you want better visibility into project margins, Productive is worth a look. Free trial at productive.io, no call required.

{MY_FIRST_NAME}`
  - variant 4 (357 chars, 62 words): `Hey {FIRST_NAME}, wrapping up my end of this.

I know these messages land at all kinds of bad times so no offence taken. If the problem I have been describing ever becomes urgent at {COMPANY} you can start a free trial of Productive at productive.io without talking to anyone. Wanted to make sure you had that before I stopped reaching out.

{MY_FIRST_NAME}`
  - fallback (306 chars): `Hey, last message from me on this.

No hard feelings if the timing has not been right. If things ever change and you want a cleaner way to track project profitability and team utilization, Productive is worth a look. Free 14 day trial at productive.io and you do not need to speak to anyone to get started.`

### 388955 — PRODUCTIVE - MARKETING AGENCIES - USA 1ST  - CLEANED - ZVONIMIR V3

- ownership: **unknown** — not in the ledger and not on any operator-declared internal list; UNKNOWN is the state, not a gap
- provider status `PAUSED`; created `2026-04-08T15:04:25.536043Z`; started `2026-04-08T15:04:39.017885Z`
- seats (`campaignAccountIds`): 174892, 174748, 175455, 174742, 174332, 174822, 174803, 174797, 174810, 174845, 181262, 212356, 143105, 175552, 201978, 179527, 159259, 129531, 191848, 194061, 208253, 181658, 208242, 181653, 201959, 186618, 139699, 129082, 125775, 125748, 119588, 116988, 116973, 116968, 156360, 169600
- lead list `605355` (PRODUCTIVE - USA 1ST - ICP - FILTERED OUT OF 200K LEADS), list size `totalItemsCount` = 50563; campaign holds `progressStats.totalUsers` = 50563, finished 231
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **5880**, accepted **547** (9.30%)
  - messages sent **885**, message threads started **431**, replies **81** (18.79% of threads started)
  - unique leads contacted **5895**; profile views 10791, follows 7614, post likes 9214
  - provider's own tags: `autoTaggedInterested` **17**, `totalAutoTagged` **81**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 449 conversations joined, 12 operator-positive replies = **0.204 per 100 requests sent**
- reply classes in this campaign: `unknown` 61, `negative` 22, `positive` 9, `automated` 5, `not_relevant` 5, `question` 3, `not_now` 1, `objection` 1
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-04-17 .. 2026-09-04 (83 days)
- sequence node types present in the whole graph: CONNECTION_REQUEST, END, FOLLOW, LIKE_POST, MESSAGE, VIEW_PROFILE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   VIEW_PROFILE          wait 0H      day  0.00
  step 1   LIKE_POST             wait 3H      day  0.12
  step 2   FOLLOW                wait 3H      day  0.25
  step 3   CONNECTION_REQUEST    wait 3D      day  3.25
  step 4   MESSAGE               wait 3D      day  6.25
  step 5   LIKE_POST             wait 1D      day  7.25
  step 6   LIKE_POST             wait 4D      day 11.25
  step 7   MESSAGE               wait 1D      day 12.25
  step 8   VIEW_PROFILE          wait 1D      day 13.25
  step 9   VIEW_PROFILE          wait 1D      day 14.25
  step 10  LIKE_POST             wait 1D      day 15.25
  step 11  MESSAGE               wait 1D      day 16.25
  step 12  MESSAGE               wait 5D      day 21.25
  step 13  VIEW_PROFILE          wait 1D      day 22.25
  step 14  LIKE_POST             wait 1D      day 23.25
  step 15  MESSAGE               wait 1D      day 24.25
  step 16  END                   wait 1D      day 25.25
```

**Connection note:** 5 `CONNECTION_REQUEST` note slot(s), every one of them EMPTY — this campaign sends connection requests with no note.

**Message steps — our text, in full:**

- message at day 6.25, 3 variant(s):
  - variant 1 (607 chars, 105 words): `Hey {FIRST_NAME}, a colleague of mine probably reached out to you about Productive recently. I wanted to add my own note because {COMPANY} genuinely looks like a strong fit for what we do and I did not want it to get buried in a busy inbox.

I work with {INDUSTRY} agencies in {LOCATION} on the ops and profitability side. The short version is that Productive replaces the disconnected tool stack most agencies run on and gives a {POSITION} a real time view of project margins, utilization and forecasts in one place.

Worth a quick conversation to see if it maps to how {COMPANY} operates?

{MY_FIRST_NAME}`
  - variant 2 (429 chars, 74 words): `Hey {FIRST_NAME}, you may have already heard from someone on my team about Productive. I am reaching out separately because I look at the {INDUSTRY} space in {LOCATION} specifically and {COMPANY} keeps coming up as a business that would get a lot out of the platform.

Happy to give you a different perspective on it if the first message did not land at the right time. Sometimes it just takes the right framing.

{MY_FIRST_NAME}`
  - variant 3 (429 chars, 74 words): `Hey {FIRST_NAME}, one of my colleagues reached out to you about Productive recently. I am following up because I wanted to make this feel less like a blast and more like a real conversation.

I spend most of my time working with {POSITION}s at {INDUSTRY} agencies and the problems I hear consistently are the same ones Productive was built to solve. Thought it was worth one more shot before leaving it with you.

{MY_FIRST_NAME}`
  - fallback (453 chars): `Hey, a colleague of mine probably reached out recently about Productive. I wanted to follow up from my side because your agency looks like a strong fit for what we do, and I did not want it to get lost.

The short version is that Productive is an agency management platform that connects project management, time tracking, budgets, and invoicing so everything talks to each other. Happy to give you a fresh perspective on it if the timing is better now.`
- message at day 12.25, 3 variant(s):
  - variant 1 (392 chars, 66 words): `Hey {FIRST_NAME}, checking in to see if my last message landed.

Rather than send another pitch I wanted to ask a genuine question. When a project at {COMPANY} goes over budget or under delivers on margin, how long does it typically take before someone catches it?

The answer to that is usually what tells me whether Productive would actually change anything for you or not.

{MY_FIRST_NAME}`
  - variant 2 (328 chars, 52 words): `Hey {FIRST_NAME}, following up on my last note.

Quick question about {COMPANY}. How does your team currently know whether you are fully utilizing your people across projects? Not a trick question, I am asking because that visibility gap is exactly what most {INDUSTRY} agencies I work with are trying to close.

{MY_FIRST_NAME}`
  - variant 3 (297 chars, 52 words): `Hey {FIRST_NAME}, just circling back.

I will be straight with you. Between my colleague and I we have both reached out now and I think {COMPANY} is genuinely worth a conversation rather than just another follow up. What would make it worth 15 minutes of your time to take a look?

{MY_FIRST_NAME}`
  - fallback (247 chars): `Hey, just following up on my last message.

Rather than repeat the pitch I wanted to ask directly. What would need to be true about a tool for it to be worth 15 minutes of your time right now? Happy to tell you whether Productive fits that or not.`
- message at day 16.25, 3 variant(s):
  - variant 1 (544 chars, 93 words): `Hey {FIRST_NAME}, one more thought in case the timing is better now.

The thing most {POSITION}s at {INDUSTRY} agencies tell me after they see Productive is that they wish they had seen it before their last hire. The reason is that resourcing and growth decisions get made on utilization data and most agencies are working from numbers that are a month old and manually assembled.

Productive puts that in front of you in real time so the decisions at {COMPANY} are based on what is actually happening now.

Still worth a look?

{MY_FIRST_NAME}`
  - variant 2 (486 chars, 83 words): `Hey {FIRST_NAME}, trying a different angle this time.

Most {INDUSTRY} agencies in {LOCATION} that switch to Productive do it because of one specific moment. Someone asks how a project is tracking, the answer requires pulling from three different tools and an hour of work, and whoever is responsible decides there has to be a better way.

If that moment has not happened at {COMPANY} yet it probably will. Happy to show you what it looks like when it does not need to.

{MY_FIRST_NAME}`
  - variant 3 (282 chars, 51 words): `Hey {FIRST_NAME}, keeping this one short.

Productive has a 14 day free trial and no card required. If a call feels like too much of a commitment right now you can start at productive.io and see the platform on your own terms first.

Still here if you want to chat.

{MY_FIRST_NAME}`
  - fallback (440 chars): `Hey, trying a different angle this time.

The moment most agencies decide to switch to Productive is when someone asks a simple question about project profitability and the answer takes an hour to pull together from separate tools. If that has happened recently it is probably worth 15 minutes to see what it looks like when it does not.

Happy to set up a call or you can start a free trial at productive.io if you prefer to explore first.`
- message at day 21.25, 3 variant(s):
  - variant 1 (604 chars, 95 words): `Hey {FIRST_NAME}, sharing something specific in case it is useful.

{INDUSTRY} agencies in {LOCATION} that use Productive typically replace Harvest or Toggl for time tracking, Monday or Asana for project management and whatever spreadsheet was doing the budget reporting. The economics tend to work out well because they are paying for fewer tools and making better decisions with the data they were already capturing.

For a {POSITION} at {COMPANY} the main shift is that you stop being the person assembling the picture and start being the person who already has it.

Worth 15 minutes?

{MY_FIRST_NAME}`
  - variant 2 (566 chars, 99 words): `Hey {FIRST_NAME}, I realize I have sent a few messages now so I will make this one count.

The agencies that get the most out of Productive are the ones where a {POSITION} is spending real time each week on work that should happen automatically. Pulling utilization reports, reconciling budgets, chasing time logs, building invoices from scratch. Productive handles all of that so the focus shifts to what the data is telling you rather than how to get the data in the first place.

If any of that sounds like {COMPANY} right now it is worth a look.

{MY_FIRST_NAME}`
  - variant 3 (469 chars, 77 words): `Hey {FIRST_NAME}, last proper pitch from me before I wrap up.

Three things Productive does that most agency tools do not. Time tracked connects directly to budget burn so you see profit impact as work happens. Resource planning shows utilization across the whole team in real time. Invoicing pulls from actual project data so there is no manual assembly.

If {COMPANY} is doing any of those things manually right now that is the gap Productive closes.

{MY_FIRST_NAME}`
  - fallback (426 chars): `Hey, making this one specific.

Three things Productive does that most agency tools do not. Time tracked connects directly to budget burn so you see profit impact as work happens. Resource planning shows team utilization in real time. Invoicing pulls from actual project data so there is no manual assembly.

If your agency is doing any of those things manually right now that is the gap Productive closes. Worth 15 minutes?

`
- message at day 24.25, 3 variant(s):
  - variant 1 (402 chars, 72 words): `Hey {FIRST_NAME}, wrapping up from my end.

Between my colleague and I we have sent a handful of messages and I do not want to keep landing in your inbox if the timing is just not right for {COMPANY}. No hard feelings at all.

If it ever becomes relevant, Productive has a free trial at productive.io and you can explore it without talking to anyone first. Worth knowing that is there.

{MY_FIRST_NAME}`
  - variant 2 (297 chars, 51 words): `Hey {FIRST_NAME}, last one from me.

I get it, the timing might just not be right. If things change at {COMPANY} and getting a cleaner view of margins and utilization becomes a priority, feel free to reach out directly or start a free trial at productive.io.

Leaving it with you.

{MY_FIRST_NAME}`
  - variant 3 (350 chars, 62 words): `Hey {FIRST_NAME}, closing the loop on my end.

My colleague reached out, I followed up a few times and I think we have both made a reasonable case for why Productive could work well for {COMPANY}. At this point it is in your hands.

If the moment ever comes where the current setup stops working, productive.io is the place to start.

{MY_FIRST_NAME}`
  - fallback (305 chars): `Hey, last message from me on this.

My colleague and I have both reached out now and I do not want to keep taking up space in your inbox. If the timing is ever right, Productive has a free trial at productive.io and you do not need to speak to anyone to get started.

Thanks for bearing with the outreach.`

### 388957 — PRODUCTIVE - MARKETING AGENCIES - USA 2ND - CLEANED - ZVONIMIR

- ownership: **unknown** — not in the ledger and not on any operator-declared internal list; UNKNOWN is the state, not a gap
- provider status `PAUSED`; created `2026-04-08T15:06:37.014535Z`; started `2026-04-08T15:06:49.336861Z`
- seats (`campaignAccountIds`): 174892, 174748, 175455, 174742, 174332, 174810, 174822, 174803, 174797, 174845
- lead list `605359` (PRODUCTIVE - USA 2ND - ICP - FILTERED OUT OF 200K LEADS), list size `totalItemsCount` = 50469; campaign holds `progressStats.totalUsers` = 50469, finished 1436
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **0**, accepted **0** (n/a (denominator 0))
  - messages sent **0**, message threads started **0**, replies **0** (n/a (denominator 0) of threads started)
  - unique leads contacted **0**; profile views 8343, follows 3979, post likes 8607
  - provider's own tags: `autoTaggedInterested` **0**, `totalAutoTagged` **0**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 0 conversations joined, 0 operator-positive replies = **n/a (0 requests sent) per 100 requests sent**
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- sequence node types present in the whole graph: END, FOLLOW, LIKE_POST, VIEW_PROFILE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   VIEW_PROFILE          wait 0H      day  0.00
  step 1   FOLLOW                wait 10D     day 10.00
  step 2   LIKE_POST             wait 10D     day 20.00
  step 3   VIEW_PROFILE          wait 10D     day 30.00
  step 4   LIKE_POST             wait 10D     day 40.00
  step 5   LIKE_POST             wait 10D     day 50.00
  step 6   LIKE_POST             wait 10D     day 60.00
  step 7   VIEW_PROFILE          wait 10D     day 70.00
  step 8   END                   wait 1D      day 71.00
```

**Connection note:** this graph has no `CONNECTION_REQUEST` node, so no note is sent.


### 388958 — PRODUCTIVE - MARKETING AGENCIES - USA 2ND - CLEANED - ZVONIMIR

- ownership: **unknown** — not in the ledger and not on any operator-declared internal list; UNKNOWN is the state, not a gap
- provider status `PAUSED`; created `2026-04-08T15:07:08.554135Z`; started `2026-04-08T15:07:18.575664Z`
- seats (`campaignAccountIds`): 174892, 174748, 175455, 174742, 174332, 174822, 174803, 174797, 174845
- lead list `605359` (PRODUCTIVE - USA 2ND - ICP - FILTERED OUT OF 200K LEADS), list size `totalItemsCount` = 50469; campaign holds `progressStats.totalUsers` = 50469, finished 221
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **3913**, accepted **406** (10.38%)
  - messages sent **969**, message threads started **345**, replies **84** (24.35% of threads started)
  - unique leads contacted **3934**; profile views 890, follows 0, post likes 1581
  - provider's own tags: `autoTaggedInterested` **24**, `totalAutoTagged` **84**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 348 conversations joined, 20 operator-positive replies = **0.511 per 100 requests sent**
- reply classes in this campaign: `unknown` 80, `negative` 16, `positive` 16, `not_relevant` 7, `automated` 5, `question` 4, `unsubscribe` 3, `not_now` 3, `out_of_office` 1
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-04-08 .. 2026-09-15 (94 days)
- sequence node types present in the whole graph: CONNECTION_REQUEST, END, INMAIL, LIKE_POST, MESSAGE, VIEW_PROFILE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CONNECTION_REQUEST    wait 0H      day  0.00
  step 1   MESSAGE               wait 3D      day  3.00
  step 2   VIEW_PROFILE          wait 1D      day  4.00
  step 3   LIKE_POST             wait 1D      day  5.00
  step 4   MESSAGE               wait 1D      day  6.00
  step 5   LIKE_POST             wait 4D      day 10.00
  step 6   VIEW_PROFILE          wait 4D      day 14.00
  step 7   MESSAGE               wait 1D      day 15.00
  step 8   LIKE_POST             wait 7D      day 22.00
  step 9   MESSAGE               wait 1D      day 23.00
  step 10  VIEW_PROFILE          wait 4D      day 27.00
  step 11  MESSAGE               wait 1D      day 28.00
  step 12  VIEW_PROFILE          wait 1D      day 29.00
  step 13  LIKE_POST             wait 1D      day 30.00
  step 14  END                   wait 1D      day 31.00
```

**Connection note:** 1 `CONNECTION_REQUEST` note slot(s), every one of them EMPTY — this campaign sends connection requests with no note.

**Message steps — our text, in full:**

- message at day 3.00, 3 variant(s):
  - variant 1 (510 chars, 80 words): `Hi {FIRST_NAME}, appreciate the add.

I help {INDUSTRY} agencies in {LOCATION} replace the usual pile of disconnected tools with one platform that ties together projects, time tracking, budgets and invoicing. The idea being that a {POSITION} can actually see whether a project is profitable while it is still running rather than finding out after the invoice goes out.

Thought {COMPANY} might be worth a conversation at some point. No pressure on that though, good to be connected either way.

{MY_FIRST_NAME}`
  - variant 2 (374 chars, 60 words): `Hey {FIRST_NAME}, thanks for connecting.

I work with {INDUSTRY} agencies on the ops side, specifically helping teams get a real time view of project profitability and utilization without juggling five different tools to do it. Given what you are doing at {COMPANY} I thought it could be relevant at some point.

Happy to share more whenever it makes sense.

{MY_FIRST_NAME}`
  - variant 3 (376 chars, 65 words): `Hi {FIRST_NAME}, good to be connected.

I spend most of my time working with {INDUSTRY} agencies on the gap between time logged and money made. Most {POSITION}s I speak with know something is leaking but cannot pinpoint where until it is too late to fix it.

Thought {COMPANY} might find it useful to see how other teams are solving that. No rush on anything.

{MY_FIRST_NAME}`
  - fallback (322 chars): `Hi, appreciate the add.

I work with agencies on the ops and profitability side, specifically helping teams replace their disconnected tool stack with one platform that ties together projects, time tracking, budgets and invoicing.

Happy to share more if it is ever relevant to your setup. Good to be connected either way.`
- message at day 6.00, 3 variant(s):
  - variant 1 (310 chars, 54 words): `Hey {FIRST_NAME}, quick question for you.

What does {COMPANY} currently use to track project profitability in real time? Not after the work is done, I mean while a project is still live.

Asking because the answer tells me a lot about whether what I do would actually be useful to you or not.

{MY_FIRST_NAME}`
  - variant 2 (323 chars, 56 words): `Hey {FIRST_NAME}, wanted to ask you something directly.

How does {COMPANY} know if a project is going to hit its margin before it is finished? Is that something you can see at any point or does it only become clear after the fact?

Genuinely curious because the answer changes what I would share with you.

{MY_FIRST_NAME}`
  - variant 3 (276 chars, 49 words): `Hey {FIRST_NAME}, just a quick one.

When a project at {COMPANY} goes over budget who is the first person to find out and how do they find out?

Asking because that gap between when something goes wrong and when someone catches it is exactly what I help with.

{MY_FIRST_NAME}`
  - fallback (251 chars): `Hey, quick question.

How does your team currently track whether a project is going to hit its margin before it wraps up?

Not looking to pitch anything, I just find the answer changes a lot about whether what I do is even relevant. Genuinely curious.`
- message at day 15.00, 3 variant(s):
  - variant 1 (577 chars, 99 words): `Hey {FIRST_NAME}, wanted to share what I actually work with in case it is relevant.

The tool is called Productive. It is built for {INDUSTRY} agencies and brings project management, time tracking, budgets and invoicing into one place so the data connects automatically. Most {POSITION}s use it to get a clear picture of utilization and margin without pulling numbers from four different tools every time someone asks how a project is tracking.

{COMPANY} came to mind as a good fit. Would you be open to a 15 minute call to see how it maps to how you operate?

{MY_FIRST_NAME}`
  - variant 2 (467 chars, 75 words): `Hey {FIRST_NAME}, sharing this because I think it is actually relevant to {COMPANY}.

The platform is called Productive and it was built specifically for {INDUSTRY} businesses. It replaces the need to run separate tools for project management, time, budgets and invoicing by connecting all of it in one place. A {POSITION} can see live margin and utilization without anyone building a manual report.

Worth 15 minutes if you want to see it in action?

{MY_FIRST_NAME}`
  - variant 3 (475 chars, 76 words): `Hey {FIRST_NAME}, I should have mentioned this earlier.

The product I work with is Productive. It is an agency management platform that connects time tracking to budgets to invoicing so the financial picture updates automatically as work happens. Teams in {LOCATION} use it to replace Harvest, Asana and whatever spreadsheet is doing the reporting work right now.

Happy to walk you through how it works for a business like {COMPANY} if you have 15 minutes.

{MY_FIRST_NAME}`
  - fallback (442 chars): `Hey, wanted to share what I actually work with.

The tool is called Productive. It is an agency management platform that connects project management, time tracking, budgets and invoicing in one place so the data updates automatically rather than sitting in separate tools. Most agency owners and ops leads use it to get a live view of margin and utilization without manual reporting.

Worth a 15-minute call if you want to see how it works?

`
- message at day 23.00, 3 variant(s):
  - variant 1 (536 chars, 90 words): `Hey {FIRST_NAME}, one more thought and then I will leave it with you.

Most {INDUSTRY} agencies in {LOCATION} that switch to Productive end up replacing Harvest or Toggl for time, Monday or Asana for projects and whatever spreadsheet was doing the budget reporting. The reason it sticks is that the data finally connects rather than sitting in separate tools that someone at {COMPANY} has to reconcile by hand.

If that sounds familiar I am happy to send over a short walkthrough instead of a call if that feels easier.

{MY_FIRST_NAME}`
  - variant 2 (455 chars, 77 words): `Hey {FIRST_NAME}, circling back one more time.

The agencies in {LOCATION} that get the most out of Productive are usually running exactly the kind of setup {COMPANY} is likely running right now. Multiple tools that work fine on their own but do not talk to each other, so a {POSITION} ends up doing the connecting manually.

Productive removes that entirely. Happy to show you a quick walkthrough if a call feels like too much right now.

{MY_FIRST_NAME}`
  - variant 3 (467 chars, 85 words): `Hey {FIRST_NAME}, wanted to try a different angle.

The question I get most from {POSITION}s before they see Productive is something like how long does it take you to answer whether we made money on that project? At most agencies it takes a day or two of pulling data together. In Productive the answer is on screen in real time.

If that gap sounds familiar at {COMPANY} it is worth seeing. I can send a walkthrough if a call does not fit right now.

{MY_FIRST_NAME}`
  - fallback (444 chars): `Hey, one more thought before I leave it with you.

Most agencies that switch to Productive end up replacing Harvest or Toggl for time, Monday or Asana for projects and whatever spreadsheet was doing the budget reporting. The reason it sticks is that the data finally connects rather than sitting in separate tools someone has to reconcile by hand.

Happy to send a short walkthrough if you want to see how it works without committing to a call.`
- message at day 28.00, 4 variant(s):
  - variant 1 (431 chars, 75 words): `Hey {FIRST_NAME}, last message from me on this.

If the timing is off or it is just not relevant to where {COMPANY} is right now that is completely fine. I would rather know than keep nudging you.

If things change and getting a cleaner view of profitability and utilisation ever becomes a priority, Productive has a free 14 day trial at productive.io and you can explore it without having to talk to anyone first.

{MY_FIRST_NAME}`
  - variant 2 (385 chars, 66 words): `Hey {FIRST_NAME}, I have sent a few messages without hearing back so I will leave it here.

No hard feelings at all, timing is everything with this kind of thing. If {COMPANY} ever gets to a point where the tool stack becomes a real headache or you want better visibility into project margins, Productive is worth a look. Free trial at productive.io, no call required.

{MY_FIRST_NAME}`
  - variant 3 (385 chars, 66 words): `Hey {FIRST_NAME}, I have sent a few messages without hearing back so I will leave it here.

No hard feelings at all, timing is everything with this kind of thing. If {COMPANY} ever gets to a point where the tool stack becomes a real headache or you want better visibility into project margins, Productive is worth a look. Free trial at productive.io, no call required.

{MY_FIRST_NAME}`
  - variant 4 (357 chars, 62 words): `Hey {FIRST_NAME}, wrapping up my end of this.

I know these messages land at all kinds of bad times so no offence taken. If the problem I have been describing ever becomes urgent at {COMPANY} you can start a free trial of Productive at productive.io without talking to anyone. Wanted to make sure you had that before I stopped reaching out.

{MY_FIRST_NAME}`
  - fallback (306 chars): `Hey, last message from me on this.

No hard feelings if the timing has not been right. If things ever change and you want a cleaner way to track project profitability and team utilization, Productive is worth a look. Free 14 day trial at productive.io and you do not need to speak to anyone to get started.`

### 388960 — PRODUCTIVE - MARKETING AGENCIES - USA 2ND - CLEANED - ZVONIMIR V3

- ownership: **unknown** — not in the ledger and not on any operator-declared internal list; UNKNOWN is the state, not a gap
- provider status `PAUSED`; created `2026-04-08T15:07:35.808146Z`; started `2026-04-08T15:07:48.601941Z`
- seats (`campaignAccountIds`): 174892, 174748, 175455, 174742, 174332, 174822, 174803, 174797, 174810, 174845, 181262, 212356, 143105, 175552, 201978, 179527, 159259, 191848, 129531, 208253, 181658, 208242, 181653, 201959, 186618, 139699, 129082, 125775, 125748, 119588, 116988, 116973, 116968, 156360, 169600, 177751
- lead list `605355` (PRODUCTIVE - USA 1ST - ICP - FILTERED OUT OF 200K LEADS), list size `totalItemsCount` = 50563; campaign holds `progressStats.totalUsers` = 50563, finished 125
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **6002**, accepted **499** (8.31%)
  - messages sent **529**, message threads started **345**, replies **61** (17.68% of threads started)
  - unique leads contacted **5998**; profile views 11268, follows 8029, post likes 9101
  - provider's own tags: `autoTaggedInterested` **7**, `totalAutoTagged` **60**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 356 conversations joined, 5 operator-positive replies = **0.083 per 100 requests sent**
- reply classes in this campaign: `unknown` 52, `negative` 17, `automated` 5, `not_relevant` 5, `positive` 4, `unsubscribe` 1, `question` 1, `referral` 1
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-04-20 .. 2026-09-21 (80 days)
- sequence node types present in the whole graph: CONNECTION_REQUEST, END, FOLLOW, LIKE_POST, MESSAGE, VIEW_PROFILE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   VIEW_PROFILE          wait 0H      day  0.00
  step 1   LIKE_POST             wait 3H      day  0.12
  step 2   FOLLOW                wait 3H      day  0.25
  step 3   CONNECTION_REQUEST    wait 5D      day  5.25
  step 4   MESSAGE               wait 3D      day  8.25
  step 5   LIKE_POST             wait 1D      day  9.25
  step 6   LIKE_POST             wait 4D      day 13.25
  step 7   MESSAGE               wait 1D      day 14.25
  step 8   VIEW_PROFILE          wait 1D      day 15.25
  step 9   VIEW_PROFILE          wait 1D      day 16.25
  step 10  LIKE_POST             wait 1D      day 17.25
  step 11  MESSAGE               wait 1D      day 18.25
  step 12  MESSAGE               wait 5D      day 23.25
  step 13  VIEW_PROFILE          wait 1D      day 24.25
  step 14  LIKE_POST             wait 1D      day 25.25
  step 15  MESSAGE               wait 1D      day 26.25
  step 16  END                   wait 1D      day 27.25
```

**Connection note — our text, in full (9 variant(s)):**

1. (234 chars, 38 words) `hi {FIRST_NAME}, i'll be straight with you, i work with marketing agencies on getting projects and finances into one place, and i'd love to pitch you at some point. Connecting first felt more honest than ambushing you. {MY_FIRST_NAME}`
2. (220 chars, 39 words) `hey {FIRST_NAME}, no pretense here, this is a sales connect. i work with {INDUSTRY} agencies on their ops and finance stack and think {COMPANY} could be a fit. happy to make the case if you're open to it. {MY_FIRST_NAME}`
3. (210 chars, 31 words) `hi {FIRST_NAME}, saw you're {POSITION} at {COMPANY}. i help agencies tie resourcing, budgets and invoicing together, and yes, i'd like the chance to show you how. connecting first, pitch second. {MY_FIRST_NAME}`
4. (226 chars, 39 words) `hey {FIRST_NAME}, i'll own it, i'm reaching out to sell you something. it's a platform agencies use to see project margin in real time. if that's worth 15 minutes down the line, great. if not, no hard feelings. {MY_FIRST_NAME}`
5. (220 chars, 36 words) `hi {FIRST_NAME}, honest version: i work with agencies like {COMPANY} and i'd like to pitch you on getting your projects and finances into one view. connecting now so it's a conversation, not a cold blast. {MY_FIRST_NAME}`
6. (218 chars, 32 words) `hey {FIRST_NAME}, this is outreach, i won't pretend otherwise. i help {INDUSTRY} agencies fix the messy projects-plus-finances problem and i think you'd get value from a proper look. open to connecting? {MY_FIRST_NAME}`
7. (219 chars, 34 words) `hi {FIRST_NAME}, full transparency, i'd love to pitch {COMPANY} on a tool agencies use for margin and resourcing visibility. figured i'd connect properly first and let you decide if it's worth your time. {MY_FIRST_NAME}`
8. (204 chars, 37 words) `hey {FIRST_NAME}, i'm in sales and i'm not going to dress it up. i work with agencies on project profitability and i think it's relevant to what you do. happy to explain if you'll have me. {MY_FIRST_NAME}`
9. (209 chars, 34 words) `hi {FIRST_NAME}, straight up, i want to pitch you. i work with {POSITION}s at agencies on getting finances and project data into one place, and {COMPANY} looks like a fit. worth a conversation? {MY_FIRST_NAME}`

**Message steps — our text, in full:**

- message at day 8.25, 18 variant(s):
  - variant 1 (435 chars, 73 words): `right {FIRST_NAME}, the awkward intro worked, so here's the actual reason i'm here. 

most agencies i talk to run projects in one tool, time in another, and finances in a spreadsheet held together by hope. 

Productive pulls it all into one place so you see project margin while the work's still live, not after the invoice goes out. is the disconnected-tools thing a headache at {COMPANY}, or have you got it sorted? 

{MY_FIRST_NAME}`
  - variant 2 (410 chars, 65 words): `okay {FIRST_NAME}, pitch time, but a quick one. the pattern i see constantly: agencies only find out a project lost money once it's already done. 

Productive ties projects, time, budgets and invoicing together so profitability shows up in real time instead of as a nasty surprise. curious, is that visibility something {COMPANY} has today, or is it more a "find out at month-end" situation? 


{MY_FIRST_NAME}`
  - variant 3 (370 chars, 55 words): `thanks for accepting {FIRST_NAME}, now i'll earn the connection. 

the usual agency pain is utilization, you don't really know who's overloaded and who's idle until something breaks. 

Productive gives you that view live, alongside budgets and billing in one place. what's your current setup for tracking it at {COMPANY}, a tool, spreadsheets, or vibes?
 {MY_FIRST_NAME}`
  - variant 4 (358 chars, 54 words): `so here's what i actually do {FIRST_NAME}. agencies lose real money in the gaps between their tools, hours that never get billed, scope creep nobody catches, margin that quietly erodes. Productive closes those gaps by putting projects, resourcing and finances under one roof. which of those bites {COMPANY} most, billing, capacity, or margin? {MY_FIRST_NAME}`
  - variant 5 (345 chars, 59 words): `fair's fair {FIRST_NAME}, you accepted, so here's the honest pitch. if your projects, timesheets and invoicing all live in different places, someone at {COMPANY} is doing a lot of manual stitching just to see if a job made money. Productive makes that one connected view. is that manual work a real drain for you, or not so much? {MY_FIRST_NAME}`
  - variant 6 (356 chars, 54 words): `promised it wouldn't be "just circling back," so it won't be {FIRST_NAME}. straight version: 

Productive is built for {INDUSTRY} agencies that are tired of juggling four tools to answer one question, are we actually making money on this? 

projects, time, budgets, invoicing, all connected. what does {COMPANY} lean on for that right now? 
{MY_FIRST_NAME}`
  - variant 7 (375 chars, 58 words): `here's the actual hook {FIRST_NAME}. most agencies don't have a margin problem, they have a visibility problem, the data's just scattered across too many tools to see clearly. 
Productive consolidates it so profitability is obvious, live, per project. would seeing that in one place actually change how you run things at {COMPANY}, or are you already there? 

{MY_FIRST_NAME}`
  - variant 8 (375 chars, 58 words): `here's the actual hook {FIRST_NAME}. most agencies don't have a margin problem, they have a visibility problem, the data's just scattered across too many tools to see clearly. 
Productive consolidates it so profitability is obvious, live, per project. would seeing that in one place actually change how you run things at {COMPANY}, or are you already there? 

{MY_FIRST_NAME}`
  - variant 9 (375 chars, 58 words): `here's the actual hook {FIRST_NAME}. most agencies don't have a margin problem, they have a visibility problem, the data's just scattered across too many tools to see clearly. 
Productive consolidates it so profitability is obvious, live, per project. would seeing that in one place actually change how you run things at {COMPANY}, or are you already there? 

{MY_FIRST_NAME}`
  - variant 10 (375 chars, 58 words): `here's the actual hook {FIRST_NAME}. most agencies don't have a margin problem, they have a visibility problem, the data's just scattered across too many tools to see clearly. 
Productive consolidates it so profitability is obvious, live, per project. would seeing that in one place actually change how you run things at {COMPANY}, or are you already there? 

{MY_FIRST_NAME}`
  - variant 11 (375 chars, 58 words): `here's the actual hook {FIRST_NAME}. most agencies don't have a margin problem, they have a visibility problem, the data's just scattered across too many tools to see clearly. 
Productive consolidates it so profitability is obvious, live, per project. would seeing that in one place actually change how you run things at {COMPANY}, or are you already there? 

{MY_FIRST_NAME}`
  - variant 12 (375 chars, 58 words): `here's the actual hook {FIRST_NAME}. most agencies don't have a margin problem, they have a visibility problem, the data's just scattered across too many tools to see clearly. 
Productive consolidates it so profitability is obvious, live, per project. would seeing that in one place actually change how you run things at {COMPANY}, or are you already there? 

{MY_FIRST_NAME}`
  - variant 13 (375 chars, 58 words): `here's the actual hook {FIRST_NAME}. most agencies don't have a margin problem, they have a visibility problem, the data's just scattered across too many tools to see clearly. 
Productive consolidates it so profitability is obvious, live, per project. would seeing that in one place actually change how you run things at {COMPANY}, or are you already there? 

{MY_FIRST_NAME}`
  - variant 14 (381 chars, 54 words): `told you i'd eventually say something useful {FIRST_NAME}, so here it is. the agencies i work with kept losing time to manual reporting and billable hours slipping through cracks. 

Productive ties projects, resourcing and finances together so that stops happening. genuinely curious what your biggest time-sink is at {COMPANY}, reporting, billing, or resourcing?

 {MY_FIRST_NAME}`
  - variant 15 (381 chars, 54 words): `told you i'd eventually say something useful {FIRST_NAME}, so here it is. the agencies i work with kept losing time to manual reporting and billable hours slipping through cracks. 

Productive ties projects, resourcing and finances together so that stops happening. genuinely curious what your biggest time-sink is at {COMPANY}, reporting, billing, or resourcing?

 {MY_FIRST_NAME}`
  - variant 16 (381 chars, 54 words): `told you i'd eventually say something useful {FIRST_NAME}, so here it is. the agencies i work with kept losing time to manual reporting and billable hours slipping through cracks. 

Productive ties projects, resourcing and finances together so that stops happening. genuinely curious what your biggest time-sink is at {COMPANY}, reporting, billing, or resourcing?

 {MY_FIRST_NAME}`
  - variant 17 (381 chars, 54 words): `told you i'd eventually say something useful {FIRST_NAME}, so here it is. the agencies i work with kept losing time to manual reporting and billable hours slipping through cracks. 

Productive ties projects, resourcing and finances together so that stops happening. genuinely curious what your biggest time-sink is at {COMPANY}, reporting, billing, or resourcing?

 {MY_FIRST_NAME}`
  - variant 18 (363 chars, 56 words): `okay {FIRST_NAME}, cards on the table. Productive is one platform for agencies that runs projects, time tracking, budgets and invoicing together, so you get live profitability instead of a month-end guessing game. {COMPANY} looked like the kind of team it fits. before i assume anything though, what's the most annoying part of your current stack? {MY_FIRST_NAME}`
  - fallback (357 chars): `So... here's the actual hook. 

Most agencies don't have a margin problem; they have a visibility problem, the data's just scattered across too many tools to see clearly. 

Productive consolidates it so profitability is obvious, live, per project. would seeing that in one place actually change how you run things at your company, or are you already there? `
- message at day 14.25, 12 variant(s):
  - variant 1 (197 chars, 33 words): `hey {FIRST_NAME}, a week of silence, which is either "not interested" or "saw it, got distracted by actual work." totally fine if it's the first. if it's the second, i'm still here. {MY_FIRST_NAME}`
  - variant 2 (328 chars, 52 words): `Hey {FIRST_NAME}, following up on my last note.

Quick question about {COMPANY}. How does your team currently know whether you are fully utilizing your people across projects? Not a trick question, I am asking because that visibility gap is exactly what most {INDUSTRY} agencies I work with are trying to close.

{MY_FIRST_NAME}`
  - variant 3 (297 chars, 52 words): `Hey {FIRST_NAME}, just circling back.

I will be straight with you. Between my colleague and I we have both reached out now and I think {COMPANY} is genuinely worth a conversation rather than just another follow up. What would make it worth 15 minutes of your time to take a look?

{MY_FIRST_NAME}`
  - variant 4 (197 chars, 33 words): `hey {FIRST_NAME}, a week of silence, which is either "not interested" or "saw it, got distracted by actual work." totally fine if it's the first. if it's the second, i'm still here. {MY_FIRST_NAME}`
  - variant 5 (176 chars, 29 words): `hey {FIRST_NAME}, the polite move is to pretend i forgot i messaged you. i didn't. just checking this didn't vanish into the LinkedIn void. worth a quick reply? {MY_FIRST_NAME}`
  - variant 6 (224 chars, 34 words): `{FIRST_NAME}, one of three things happened: you're busy, you're not interested, or my message was boring. happy to fix the third one with a better question. how's {COMPANY} handling project margin these days? {MY_FIRST_NAME}`
  - variant 7 (180 chars, 31 words): `hey {FIRST_NAME}, no guilt-trip here, i know exactly how fast a message gets buried. just floating this back up before i let it go. one word reply works, even "no." {MY_FIRST_NAME}`
  - variant 8 (187 chars, 28 words): `{FIRST_NAME}, i'll take a hint eventually, just not yet. genuinely think Productive's worth 15 minutes for {COMPANY}, but if i'm wrong, tell me and i'll happily disappear. {MY_FIRST_NAME}`
  - variant 9 (196 chars, 32 words): `hey {FIRST_NAME}, day seven, the official point where a follow-up stops being keen and starts being clingy. so this is my one charming attempt before i back off. interested or nah? {MY_FIRST_NAME}`
  - variant 10 (184 chars, 33 words): `{FIRST_NAME}, circling back, and yes i hate that phrase too. truth is i think there's a real fit here for {COMPANY}. if there isn't, a quick "not for us" saves us both. {MY_FIRST_NAME}`
  - variant 11 (181 chars, 32 words): `hey {FIRST_NAME}, still here, still think your tool stack is quietly costing you money. but i also respect a busy inbox. want me to keep going or leave you in peace? {MY_FIRST_NAME}`
  - variant 12 (220 chars, 37 words): `{FIRST_NAME}, i promise this isn't an automated nudge, a bot wouldn't admit it's been a week. just a real person who thinks Productive could help {COMPANY} and didn't want to give up at the first silence. {MY_FIRST_NAME}`
  - fallback (247 chars): `Hey, just following up on my last message.

Rather than repeat the pitch I wanted to ask directly. What would need to be true about a tool for it to be worth 15 minutes of your time right now? Happy to tell you whether Productive fits that or not.`
- message at day 18.25, 3 variant(s):
  - variant 1 (544 chars, 93 words): `Hey {FIRST_NAME}, one more thought in case the timing is better now.

The thing most {POSITION}s at {INDUSTRY} agencies tell me after they see Productive is that they wish they had seen it before their last hire. The reason is that resourcing and growth decisions get made on utilization data and most agencies are working from numbers that are a month old and manually assembled.

Productive puts that in front of you in real time so the decisions at {COMPANY} are based on what is actually happening now.

Still worth a look?

{MY_FIRST_NAME}`
  - variant 2 (486 chars, 83 words): `Hey {FIRST_NAME}, trying a different angle this time.

Most {INDUSTRY} agencies in {LOCATION} that switch to Productive do it because of one specific moment. Someone asks how a project is tracking, the answer requires pulling from three different tools and an hour of work, and whoever is responsible decides there has to be a better way.

If that moment has not happened at {COMPANY} yet it probably will. Happy to show you what it looks like when it does not need to.

{MY_FIRST_NAME}`
  - variant 3 (282 chars, 51 words): `Hey {FIRST_NAME}, keeping this one short.

Productive has a 14 day free trial and no card required. If a call feels like too much of a commitment right now you can start at productive.io and see the platform on your own terms first.

Still here if you want to chat.

{MY_FIRST_NAME}`
  - fallback (440 chars): `Hey, trying a different angle this time.

The moment most agencies decide to switch to Productive is when someone asks a simple question about project profitability and the answer takes an hour to pull together from separate tools. If that has happened recently it is probably worth 15 minutes to see what it looks like when it does not.

Happy to set up a call or you can start a free trial at productive.io if you prefer to explore first.`
- message at day 23.25, 3 variant(s):
  - variant 1 (604 chars, 95 words): `Hey {FIRST_NAME}, sharing something specific in case it is useful.

{INDUSTRY} agencies in {LOCATION} that use Productive typically replace Harvest or Toggl for time tracking, Monday or Asana for project management and whatever spreadsheet was doing the budget reporting. The economics tend to work out well because they are paying for fewer tools and making better decisions with the data they were already capturing.

For a {POSITION} at {COMPANY} the main shift is that you stop being the person assembling the picture and start being the person who already has it.

Worth 15 minutes?

{MY_FIRST_NAME}`
  - variant 2 (566 chars, 99 words): `Hey {FIRST_NAME}, I realize I have sent a few messages now so I will make this one count.

The agencies that get the most out of Productive are the ones where a {POSITION} is spending real time each week on work that should happen automatically. Pulling utilization reports, reconciling budgets, chasing time logs, building invoices from scratch. Productive handles all of that so the focus shifts to what the data is telling you rather than how to get the data in the first place.

If any of that sounds like {COMPANY} right now it is worth a look.

{MY_FIRST_NAME}`
  - variant 3 (469 chars, 77 words): `Hey {FIRST_NAME}, last proper pitch from me before I wrap up.

Three things Productive does that most agency tools do not. Time tracked connects directly to budget burn so you see profit impact as work happens. Resource planning shows utilization across the whole team in real time. Invoicing pulls from actual project data so there is no manual assembly.

If {COMPANY} is doing any of those things manually right now that is the gap Productive closes.

{MY_FIRST_NAME}`
  - fallback (426 chars): `Hey, making this one specific.

Three things Productive does that most agency tools do not. Time tracked connects directly to budget burn so you see profit impact as work happens. Resource planning shows team utilization in real time. Invoicing pulls from actual project data so there is no manual assembly.

If your agency is doing any of those things manually right now that is the gap Productive closes. Worth 15 minutes?

`
- message at day 26.25, 3 variant(s):
  - variant 1 (402 chars, 72 words): `Hey {FIRST_NAME}, wrapping up from my end.

Between my colleague and I we have sent a handful of messages and I do not want to keep landing in your inbox if the timing is just not right for {COMPANY}. No hard feelings at all.

If it ever becomes relevant, Productive has a free trial at productive.io and you can explore it without talking to anyone first. Worth knowing that is there.

{MY_FIRST_NAME}`
  - variant 2 (297 chars, 51 words): `Hey {FIRST_NAME}, last one from me.

I get it, the timing might just not be right. If things change at {COMPANY} and getting a cleaner view of margins and utilization becomes a priority, feel free to reach out directly or start a free trial at productive.io.

Leaving it with you.

{MY_FIRST_NAME}`
  - variant 3 (350 chars, 62 words): `Hey {FIRST_NAME}, closing the loop on my end.

My colleague reached out, I followed up a few times and I think we have both made a reasonable case for why Productive could work well for {COMPANY}. At this point it is in your hands.

If the moment ever comes where the current setup stops working, productive.io is the place to start.

{MY_FIRST_NAME}`
  - fallback (305 chars): `Hey, last message from me on this.

My colleague and I have both reached out now and I do not want to keep taking up space in your inbox. If the timing is ever right, Productive has a free trial at productive.io and you do not need to speak to anyone to get started.

Thanks for bearing with the outreach.`

### 406850 — PRODUCTIVE - MARKETING AGENCIES - EU - CLEANED ZVONIIMR - AFTER EMAIL APPROACH INMAILS - 23/04

- ownership: **unknown** — not in the ledger and not on any operator-declared internal list; UNKNOWN is the state, not a gap
- provider status `PAUSED`; created `2026-04-23T21:04:35.423697Z`; started `2026-04-23T21:10:29.145678Z`
- seats (`campaignAccountIds`): 174892, 174748, 175455, 174742, 174332, 174822, 174845, 174803, 174797
- lead list `632277` (PRODUCTIVE - MARKETING AGENCIES - EU - SAFE TO SEND EMAIL - DOUBLE DOWN), list size `totalItemsCount` = 11128; campaign holds `progressStats.totalUsers` = 11128, finished 112
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **0**, accepted **0** (n/a (denominator 0))
  - messages sent **0**, message threads started **0**, replies **0** (n/a (denominator 0) of threads started)
  - InMail: started **2231**, replies **112** (5.02%). `inmailMessagesSent` is **0** here and on every campaign on this seat — the InMail volume lives in `totalInmailStarted`, so a reader asking `inmailMessagesSent` sees zero.
  - unique leads contacted **2231**; profile views 2662, follows 2590, post likes 2574
  - provider's own tags: `autoTaggedInterested` **10**, `totalAutoTagged` **112**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 2269 conversations joined, 4 operator-positive replies = **n/a (0 requests sent) per 100 requests sent**
- reply classes in this campaign: `unknown` 55, `negative` 53, `not_relevant` 6, `positive` 3, `objection` 3, `out_of_office` 3, `not_now` 2, `unsubscribe` 2, `automated` 2, `question` 1
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- sequence node types present in the whole graph: END, FOLLOW, INMAIL, LIKE_POST, VIEW_PROFILE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   VIEW_PROFILE          wait 0H      day  0.00
  step 1   FOLLOW                wait 1D      day  1.00
  step 2   LIKE_POST             wait 1D      day  2.00
  step 3   INMAIL                wait 1D      day  3.00
  step 4   LIKE_POST             wait 1D      day  4.00
  step 5   VIEW_PROFILE          wait 1D      day  5.00
  step 6   LIKE_POST             wait 1D      day  6.00
  step 7   VIEW_PROFILE          wait 1D      day  7.00
  step 8   END                   wait 1D      day  8.00
```

**Connection note:** this graph has no `CONNECTION_REQUEST` node, so no note is sent.


### 428674 — PRODUCTIVE - MARKETING AGENCIES - ALL LEADS - ZVONIMIR NEW APPRAOCH - 05/13 v2

- ownership: **unknown** — not in the ledger and not on any operator-declared internal list; UNKNOWN is the state, not a gap
- provider status `PAUSED`; created `2026-05-13T11:20:39.680299Z`; started `2026-05-13T11:21:06.085868Z`
- seats (`campaignAccountIds`): 174892, 174748, 175455, 174742, 174332, 174810, 174822, 174845, 174803, 174797
- lead list `632277` (PRODUCTIVE - MARKETING AGENCIES - EU - SAFE TO SEND EMAIL - DOUBLE DOWN), list size `totalItemsCount` = 11128; campaign holds `progressStats.totalUsers` = 11128, finished 669
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **4545**, accepted **985** (21.67%)
  - messages sent **1301**, message threads started **885**, replies **179** (20.23% of threads started)
  - unique leads contacted **4519**; profile views 740, follows 0, post likes 2061
  - provider's own tags: `autoTaggedInterested` **42**, `totalAutoTagged` **179**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 928 conversations joined, 12 operator-positive replies = **0.264 per 100 requests sent**
- reply classes in this campaign: `unknown` 193, `negative` 31, `not_relevant` 26, `automated` 10, `question` 9, `objection` 5, `out_of_office` 4, `positive` 3, `send_info` 2, `unsubscribe` 1, `not_now` 1
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-05-13 .. 2026-10-02 (90 days)
- sequence node types present in the whole graph: CONNECTION_REQUEST, END, LIKE_POST, MESSAGE, SEND_LEAD_TO_BISON, VIEW_PROFILE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CONNECTION_REQUEST    wait 0H      day  0.00
  step 1   MESSAGE               wait 3H      day  0.12
  step 2   VIEW_PROFILE          wait 5D      day  5.12
  step 3   LIKE_POST             wait 5D      day 10.12
  step 4   SEND_LEAD_TO_BISON    wait 1D      day 11.12
  step 5   MESSAGE               wait 0H      day 11.12
  step 6   LIKE_POST             wait 5D      day 16.12
  step 7   MESSAGE               wait 1D      day 17.12
  step 8   LIKE_POST             wait 1D      day 18.12
  step 9   END                   wait 1D      day 19.12
```

**Connection note:** 1 `CONNECTION_REQUEST` note slot(s), every one of them EMPTY — this campaign sends connection requests with no note.

**Message steps — our text, in full:**

- message at day 0.12, 20 variant(s):
  - variant 1 (149 chars, 21 words): `hey {FIRST_NAME}, how does {COMPANY} currently track project profitability, is it all spreadsheets or do you have something in place? {MY_FIRST_NAME}`
  - variant 2 (181 chars, 33 words): `{FIRST_NAME} quick one, do you guys have resource planning sorted out at {COMPANY} or is that still a bit of a mess? asking cause i work with few {INDUSTRY} agencies on exactly that`
  - variant 3 (173 chars, 27 words): `hey {FIRST_NAME}! saw you're {POSITION} at {COMPANY}, curious how you handle billing and invoicing across projects, is it all manual or do you have a system? {MY_FIRST_NAME}`
  - variant 4 (185 chars, 29 words): `{FIRST_NAME}, random question but how many tools is {COMPANY} using to manage projects, resources and finances? asking cause most {INDUSTRY} agencies we talk to are juggling way to many`
  - variant 5 (152 chars, 25 words): `hey {FIRST_NAME}, do you guys have visibility on which projects are actually profitable at {COMPANY} or is that something you figure out after the fact?`
  - variant 6 (182 chars, 27 words): `{FIRST_NAME} hi, is resource planning something {COMPANY} has figured out or still a work in progress? we work with {INDUSTRY} agencies on getting that under control, {MY_FIRST_NAME}`
  - variant 7 (167 chars, 27 words): `hey {FIRST_NAME}! as {POSITION} at {COMPANY} curious if you have a single place where projects, budgets and resourcing all live or if its spread across different tools`
  - variant 8 (168 chars, 24 words): `{FIRST_NAME}, how do you guys handle project budgets at {COMPANY}, got that sorted or still piecing it together across spreadsheets and different tools? {MY_FIRST_NAME}`
  - variant 9 (162 chars, 28 words): `hey {FIRST_NAME}, do you have a good handle on utilization across the team at {COMPANY} or is that one of those things thats always a bit unclear? {MY_FIRST_NAME}`
  - variant 10 (156 chars, 25 words): `{FIRST_NAME} quick question, how does {COMPANY} track whether projects are staying on budget, is that something you have sorted or more of a manual process?`
  - variant 11 (176 chars, 28 words): `hey {FIRST_NAME}! saw {COMPANY} and was curious, whats the biggest operational headache for you guys right now, is it resourcing, profitability or just to many tools to manage?`
  - variant 12 (160 chars, 25 words): `{FIRST_NAME}, is invoicing and billing something {COMPANY} has nailed down or still one of those things that takes way more time than it should? {MY_FIRST_NAME}`
  - variant 13 (130 chars, 22 words): `hey {FIRST_NAME}, how do you guys forecast revenue at {COMPANY}, got a solid process or still kinda winging it quarter to quarter?`
  - variant 14 (186 chars, 32 words): `{FIRST_NAME} hi! as {POSITION} at a {INDUSTRY} agency curious if you have clear visibility on team capacity at any given time or if thats always a bit of a guessing game, {MY_FIRST_NAME}`
  - variant 15 (151 chars, 25 words): `hey {FIRST_NAME}, do you guys have project management, resourcing and finances in one place at {COMPANY} or is it spread across like 4 different tools?`
  - variant 16 (151 chars, 28 words): `{FIRST_NAME}, quick one, how does {COMPANY} know if a project is going to hit budget before it's to late to do anything about it? got that figured out?`
  - variant 17 (202 chars, 31 words): `hey {FIRST_NAME}! {MY_FIRST_NAME} here, i work with {INDUSTRY} agencies on operational stuff. curious if {COMPANY} has a handle on project profitability in real time or its more of a retrospective thing`
  - variant 18 (158 chars, 24 words): `{FIRST_NAME} is time tracking something the team at {COMPANY} actually does consistently or is that one of those things thats always a battle? {MY_FIRST_NAME}`
  - variant 19 (174 chars, 30 words): `hey {FIRST_NAME}, saw you're {POSITION} at {COMPANY}. do you have one place where you can see project status, team capacity and finances together or is it all over the place?`
  - variant 20 (148 chars, 23 words): `{FIRST_NAME} hi, how are you guys managing agency ops at {COMPANY} right now, got a solid system or still stitching things together? {MY_FIRST_NAME}`
  - fallback (125 chars): `hey, do you guys have project management, resourcing and finances in one place or is it spread across like 4 different tools?`
- message at day 11.12, 14 variant(s):
  - variant 1 (186 chars, 30 words): `hey {FIRST_NAME}, just bumping this up, agencies like {COMPANY} usually tell us the biggest thing is not knowing project profitability until its too late. is that something you run into?`
  - variant 2 (170 chars, 28 words): `{FIRST_NAME} following up, i know its probably not top of mind but curious, how are you guys currently handling resource planning, got something or still figuring it out?`
  - variant 3 (226 chars, 35 words): `hey {FIRST_NAME}! didn't hear back, no worries. just wanted to add, most {INDUSTRY} agencies we work with were running projects, finances and resourcing across 3-4 tools before consolidating. is that the case at {COMPANY} too?`
  - variant 4 (183 chars, 30 words): `{FIRST_NAME}, just checking in. one thing that comes up a lot with {INDUSTRY} agencies is losing billable hours just cause time tracking is inconsistent. is that a thing at {COMPANY}?`
  - variant 5 (184 chars, 30 words): `hey {FIRST_NAME}, following up on my last message. not trying to be annoying, genuinely curious if operational visibility is something {COMPANY} has sorted or if its still a pain point`
  - variant 6 (212 chars, 32 words): `{FIRST_NAME} hi, just bumping this. agencies usually lose a surprising amount of revenue just from projects going over budget without anyone catching it early. does that ring a bell at {COMPANY}? 
{MY_FIRST_NAME}`
  - variant 7 (179 chars, 31 words): `hey {FIRST_NAME}! quick follow up, do you guys have a way to see team utilization and project finances in one place or is that something you're still working towards at {COMPANY}?`
  - variant 8 (233 chars, 40 words): `{FIRST_NAME}, i know you're probably busy but wanted to follow up. most {POSITION}s we talk to at {INDUSTRY} agencies say the hardest thing is getting a clear picture of whats profitable and whats not. is that fair for {COMPANY} too?`
  - variant 9 (191 chars, 32 words): `hey {FIRST_NAME}, just circling back. not asking for a demo or anything, just curious, is agency ops something that feels under control at {COMPANY} right now or more of an ongoing challenge?`
  - variant 10 (241 chars, 40 words): `{FIRST_NAME} following up, one thing worth mentioning, agencies that get resourcing and project finances in one place usually save a meaningful chunk of time on admin every week. curious if that kind of thing would matter to you at {COMPANY}`
  - variant 11 (174 chars, 30 words): `hey {FIRST_NAME}! bumping this up, is now just a bad time or is operational tooling not really a priority at {COMPANY} right now? either way just let me know, {MY_FIRST_NAME}`
  - variant 12 (222 chars, 37 words): `hey {FIRST_NAME}, circling back quickly. a lot of {INDUSTRY} agencies tell us they only realize a project went sideways after invoicing. does that happen at {COMPANY} or do you have visibility before it gets to that point?`
  - variant 13 (169 chars, 26 words): `{FIRST_NAME}, just checking in, is this landing with the wrong person? happy to connect with whoever handles ops or tooling at {COMPANY} if thats easier, {MY_FIRST_NAME}`
  - variant 14 (202 chars, 34 words): `{FIRST_NAME}, i'll keep this short. is operational visibility something {COMPANY} has a good handle on or is it one of those things that could always be better? worth a quick chat if so, {MY_FIRST_NAME}`
  - fallback (180 chars): `hey, i'll keep this short. is operational visibility something your company has a good handle on or is it one of those things that could always be better? worth a quick chat if so?`
- message at day 17.12, 19 variant(s):
  - variant 1 (37 chars, 5 words): `hey {FIRST_NAME}, still relevant? lmk`
  - variant 2 (37 chars, 5 words): `hey {FIRST_NAME}, still relevant? lmk`
  - variant 3 (122 chars, 20 words): `hey {FIRST_NAME}! is ops and project visibility something {COMPANY} has sorted or still a work in progress, lmk either way`
  - variant 4 (71 chars, 12 words): `{FIRST_NAME}, bad timing or just not relevant? either is fine, just lmk`
  - variant 5 (109 chars, 16 words): `hey {FIRST_NAME}, wdyt, is managing projects and finances in one place something {COMPANY} would find useful?`
  - variant 6 (81 chars, 12 words): `{FIRST_NAME} still open to connecting? lmk and ill keep it short, {MY_FIRST_NAME}`
  - variant 7 (90 chars, 17 words): `hey {FIRST_NAME}! last one from me, wdyt, worth 15 min or not really a priority right now?`
  - variant 8 (96 chars, 17 words): `hey {FIRST_NAME}, no worries if the timings off, just lmk and ill follow up whenever makes sense`
  - variant 9 (147 chars, 20 words): `{FIRST_NAME} wdyt, is operational visibility something {COMPANY} is actively trying to improve or pretty happy with how things are? {MY_FIRST_NAME}`
  - variant 10 (96 chars, 18 words): `hey {FIRST_NAME}! just lmk if this isnt relevant and ill get out of your inbox, no hard feelings`
  - variant 11 (90 chars, 18 words): `{FIRST_NAME}, one last bump. wdyt, is it a yes, a not now or a not for us? {MY_FIRST_NAME}`
  - variant 12 (108 chars, 14 words): `hey {FIRST_NAME}, is project profitability something {COMPANY} tracks well right now, genuinely curious, lmk`
  - variant 13 (86 chars, 17 words): `{FIRST_NAME} hi, wdyt, open to a quick look or not the right time? either works for me`
  - variant 14 (125 chars, 20 words): `hey {FIRST_NAME}! last message i promise. is agency ops a pain point at {COMPANY} or pretty much handled, lmk {MY_FIRST_NAME}`
  - variant 15 (96 chars, 15 words): `{FIRST_NAME}, still think there could be something here for {COMPANY}. wdyt, worth a quick call?`
  - variant 16 (109 chars, 24 words): `hey {FIRST_NAME}, just lmk if you want me to send over some info or if its better i reach out in a few months`
  - variant 17 (123 chars, 21 words): `{FIRST_NAME} last one from me. is this relevant at all for {COMPANY} right now, yes, no or maybe later, lmk {MY_FIRST_NAME}`
  - variant 18 (121 chars, 23 words): `hey {FIRST_NAME}! wdyt, is there a better person at {COMPANY} i should be talking to about this or are you the right one?`
  - variant 19 (140 chars, 23 words): `{FIRST_NAME}, i'll leave it here. if the timing ever feels right for a chat about how {COMPANY} manages agency ops just lmk, {MY_FIRST_NAME}`
  - fallback (60 chars): `one last bump. wdyt, is it a yes, a not now or a not for us?`

### 428676 — PRODUCTIVE - MARKETING AGENCIES - ALL LEADS - ZVONIMIR NEW APPRAOCH - 05/13 v4

- ownership: **unknown** — not in the ledger and not on any operator-declared internal list; UNKNOWN is the state, not a gap
- provider status `PAUSED`; created `2026-05-13T11:21:17.314201Z`; started `2026-05-13T11:21:55.775422Z`
- seats (`campaignAccountIds`): 174892, 174748, 175455, 174742, 174332, 174810, 174822, 174845, 174803, 174797, 181262, 212356, 143105, 175552, 201978, 179527, 129531, 191848, 208253, 181658, 208242, 181653, 201959, 186618, 125748, 119588, 125775, 129082, 139699, 116988, 116973, 116968, 156360, 169600, 177751
- lead list `632277` (PRODUCTIVE - MARKETING AGENCIES - EU - SAFE TO SEND EMAIL - DOUBLE DOWN), list size `totalItemsCount` = 11128; campaign holds `progressStats.totalUsers` = 11128, finished 0
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **4**, accepted **0** (0.00%)
  - messages sent **0**, message threads started **0**, replies **0** (n/a (denominator 0) of threads started)
  - unique leads contacted **4**; profile views 6205, follows 0, post likes 3828
  - provider's own tags: `autoTaggedInterested` **0**, `totalAutoTagged` **0**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 0 conversations joined, 0 operator-positive replies = **0.000 per 100 requests sent**
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-07-27 .. 2026-07-27 (1 days)
- sequence node types present in the whole graph: CONNECTION_REQUEST, END, LIKE_POST, MESSAGE, SEND_LEAD_TO_BISON, VIEW_PROFILE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   VIEW_PROFILE          wait 0H      day  0.00
  step 1   LIKE_POST             wait 10D     day 10.00
  step 2   LIKE_POST             wait 10D     day 20.00
  step 3   CONNECTION_REQUEST    wait 15D     day 35.00
  step 4   MESSAGE               wait 3H      day 35.12
  step 5   VIEW_PROFILE          wait 5D      day 40.12
  step 6   LIKE_POST             wait 5D      day 45.12
  step 7   SEND_LEAD_TO_BISON    wait 1D      day 46.12
  step 8   MESSAGE               wait 0H      day 46.12
  step 9   LIKE_POST             wait 5D      day 51.12
  step 10  MESSAGE               wait 1D      day 52.12
  step 11  LIKE_POST             wait 1D      day 53.12
  step 12  END                   wait 1D      day 54.12
```

**Connection note:** 1 `CONNECTION_REQUEST` note slot(s), every one of them EMPTY — this campaign sends connection requests with no note.

**Message steps — our text, in full:**

- message at day 35.12, 20 variant(s):
  - variant 1 (149 chars, 21 words): `hey {FIRST_NAME}, how does {COMPANY} currently track project profitability, is it all spreadsheets or do you have something in place? {MY_FIRST_NAME}`
  - variant 2 (181 chars, 33 words): `{FIRST_NAME} quick one, do you guys have resource planning sorted out at {COMPANY} or is that still a bit of a mess? asking cause i work with few {INDUSTRY} agencies on exactly that`
  - variant 3 (173 chars, 27 words): `hey {FIRST_NAME}! saw you're {POSITION} at {COMPANY}, curious how you handle billing and invoicing across projects, is it all manual or do you have a system? {MY_FIRST_NAME}`
  - variant 4 (185 chars, 29 words): `{FIRST_NAME}, random question but how many tools is {COMPANY} using to manage projects, resources and finances? asking cause most {INDUSTRY} agencies we talk to are juggling way to many`
  - variant 5 (152 chars, 25 words): `hey {FIRST_NAME}, do you guys have visibility on which projects are actually profitable at {COMPANY} or is that something you figure out after the fact?`
  - variant 6 (182 chars, 27 words): `{FIRST_NAME} hi, is resource planning something {COMPANY} has figured out or still a work in progress? we work with {INDUSTRY} agencies on getting that under control, {MY_FIRST_NAME}`
  - variant 7 (167 chars, 27 words): `hey {FIRST_NAME}! as {POSITION} at {COMPANY} curious if you have a single place where projects, budgets and resourcing all live or if its spread across different tools`
  - variant 8 (168 chars, 24 words): `{FIRST_NAME}, how do you guys handle project budgets at {COMPANY}, got that sorted or still piecing it together across spreadsheets and different tools? {MY_FIRST_NAME}`
  - variant 9 (162 chars, 28 words): `hey {FIRST_NAME}, do you have a good handle on utilization across the team at {COMPANY} or is that one of those things thats always a bit unclear? {MY_FIRST_NAME}`
  - variant 10 (156 chars, 25 words): `{FIRST_NAME} quick question, how does {COMPANY} track whether projects are staying on budget, is that something you have sorted or more of a manual process?`
  - variant 11 (176 chars, 28 words): `hey {FIRST_NAME}! saw {COMPANY} and was curious, whats the biggest operational headache for you guys right now, is it resourcing, profitability or just to many tools to manage?`
  - variant 12 (160 chars, 25 words): `{FIRST_NAME}, is invoicing and billing something {COMPANY} has nailed down or still one of those things that takes way more time than it should? {MY_FIRST_NAME}`
  - variant 13 (130 chars, 22 words): `hey {FIRST_NAME}, how do you guys forecast revenue at {COMPANY}, got a solid process or still kinda winging it quarter to quarter?`
  - variant 14 (186 chars, 32 words): `{FIRST_NAME} hi! as {POSITION} at a {INDUSTRY} agency curious if you have clear visibility on team capacity at any given time or if thats always a bit of a guessing game, {MY_FIRST_NAME}`
  - variant 15 (151 chars, 25 words): `hey {FIRST_NAME}, do you guys have project management, resourcing and finances in one place at {COMPANY} or is it spread across like 4 different tools?`
  - variant 16 (151 chars, 28 words): `{FIRST_NAME}, quick one, how does {COMPANY} know if a project is going to hit budget before it's to late to do anything about it? got that figured out?`
  - variant 17 (202 chars, 31 words): `hey {FIRST_NAME}! {MY_FIRST_NAME} here, i work with {INDUSTRY} agencies on operational stuff. curious if {COMPANY} has a handle on project profitability in real time or its more of a retrospective thing`
  - variant 18 (158 chars, 24 words): `{FIRST_NAME} is time tracking something the team at {COMPANY} actually does consistently or is that one of those things thats always a battle? {MY_FIRST_NAME}`
  - variant 19 (174 chars, 30 words): `hey {FIRST_NAME}, saw you're {POSITION} at {COMPANY}. do you have one place where you can see project status, team capacity and finances together or is it all over the place?`
  - variant 20 (148 chars, 23 words): `{FIRST_NAME} hi, how are you guys managing agency ops at {COMPANY} right now, got a solid system or still stitching things together? {MY_FIRST_NAME}`
  - fallback (125 chars): `hey, do you guys have project management, resourcing and finances in one place or is it spread across like 4 different tools?`
- message at day 46.12, 14 variant(s):
  - variant 1 (186 chars, 30 words): `hey {FIRST_NAME}, just bumping this up, agencies like {COMPANY} usually tell us the biggest thing is not knowing project profitability until its too late. is that something you run into?`
  - variant 2 (170 chars, 28 words): `{FIRST_NAME} following up, i know its probably not top of mind but curious, how are you guys currently handling resource planning, got something or still figuring it out?`
  - variant 3 (226 chars, 35 words): `hey {FIRST_NAME}! didn't hear back, no worries. just wanted to add, most {INDUSTRY} agencies we work with were running projects, finances and resourcing across 3-4 tools before consolidating. is that the case at {COMPANY} too?`
  - variant 4 (183 chars, 30 words): `{FIRST_NAME}, just checking in. one thing that comes up a lot with {INDUSTRY} agencies is losing billable hours just cause time tracking is inconsistent. is that a thing at {COMPANY}?`
  - variant 5 (184 chars, 30 words): `hey {FIRST_NAME}, following up on my last message. not trying to be annoying, genuinely curious if operational visibility is something {COMPANY} has sorted or if its still a pain point`
  - variant 6 (212 chars, 32 words): `{FIRST_NAME} hi, just bumping this. agencies usually lose a surprising amount of revenue just from projects going over budget without anyone catching it early. does that ring a bell at {COMPANY}? 
{MY_FIRST_NAME}`
  - variant 7 (179 chars, 31 words): `hey {FIRST_NAME}! quick follow up, do you guys have a way to see team utilization and project finances in one place or is that something you're still working towards at {COMPANY}?`
  - variant 8 (233 chars, 40 words): `{FIRST_NAME}, i know you're probably busy but wanted to follow up. most {POSITION}s we talk to at {INDUSTRY} agencies say the hardest thing is getting a clear picture of whats profitable and whats not. is that fair for {COMPANY} too?`
  - variant 9 (191 chars, 32 words): `hey {FIRST_NAME}, just circling back. not asking for a demo or anything, just curious, is agency ops something that feels under control at {COMPANY} right now or more of an ongoing challenge?`
  - variant 10 (241 chars, 40 words): `{FIRST_NAME} following up, one thing worth mentioning, agencies that get resourcing and project finances in one place usually save a meaningful chunk of time on admin every week. curious if that kind of thing would matter to you at {COMPANY}`
  - variant 11 (174 chars, 30 words): `hey {FIRST_NAME}! bumping this up, is now just a bad time or is operational tooling not really a priority at {COMPANY} right now? either way just let me know, {MY_FIRST_NAME}`
  - variant 12 (222 chars, 37 words): `hey {FIRST_NAME}, circling back quickly. a lot of {INDUSTRY} agencies tell us they only realize a project went sideways after invoicing. does that happen at {COMPANY} or do you have visibility before it gets to that point?`
  - variant 13 (169 chars, 26 words): `{FIRST_NAME}, just checking in, is this landing with the wrong person? happy to connect with whoever handles ops or tooling at {COMPANY} if thats easier, {MY_FIRST_NAME}`
  - variant 14 (202 chars, 34 words): `{FIRST_NAME}, i'll keep this short. is operational visibility something {COMPANY} has a good handle on or is it one of those things that could always be better? worth a quick chat if so, {MY_FIRST_NAME}`
  - fallback (180 chars): `hey, i'll keep this short. is operational visibility something your company has a good handle on or is it one of those things that could always be better? worth a quick chat if so?`
- message at day 52.12, 19 variant(s):
  - variant 1 (37 chars, 5 words): `hey {FIRST_NAME}, still relevant? lmk`
  - variant 2 (37 chars, 5 words): `hey {FIRST_NAME}, still relevant? lmk`
  - variant 3 (122 chars, 20 words): `hey {FIRST_NAME}! is ops and project visibility something {COMPANY} has sorted or still a work in progress, lmk either way`
  - variant 4 (71 chars, 12 words): `{FIRST_NAME}, bad timing or just not relevant? either is fine, just lmk`
  - variant 5 (109 chars, 16 words): `hey {FIRST_NAME}, wdyt, is managing projects and finances in one place something {COMPANY} would find useful?`
  - variant 6 (81 chars, 12 words): `{FIRST_NAME} still open to connecting? lmk and ill keep it short, {MY_FIRST_NAME}`
  - variant 7 (90 chars, 17 words): `hey {FIRST_NAME}! last one from me, wdyt, worth 15 min or not really a priority right now?`
  - variant 8 (96 chars, 17 words): `hey {FIRST_NAME}, no worries if the timings off, just lmk and ill follow up whenever makes sense`
  - variant 9 (147 chars, 20 words): `{FIRST_NAME} wdyt, is operational visibility something {COMPANY} is actively trying to improve or pretty happy with how things are? {MY_FIRST_NAME}`
  - variant 10 (96 chars, 18 words): `hey {FIRST_NAME}! just lmk if this isnt relevant and ill get out of your inbox, no hard feelings`
  - variant 11 (90 chars, 18 words): `{FIRST_NAME}, one last bump. wdyt, is it a yes, a not now or a not for us? {MY_FIRST_NAME}`
  - variant 12 (108 chars, 14 words): `hey {FIRST_NAME}, is project profitability something {COMPANY} tracks well right now, genuinely curious, lmk`
  - variant 13 (86 chars, 17 words): `{FIRST_NAME} hi, wdyt, open to a quick look or not the right time? either works for me`
  - variant 14 (125 chars, 20 words): `hey {FIRST_NAME}! last message i promise. is agency ops a pain point at {COMPANY} or pretty much handled, lmk {MY_FIRST_NAME}`
  - variant 15 (96 chars, 15 words): `{FIRST_NAME}, still think there could be something here for {COMPANY}. wdyt, worth a quick call?`
  - variant 16 (109 chars, 24 words): `hey {FIRST_NAME}, just lmk if you want me to send over some info or if its better i reach out in a few months`
  - variant 17 (123 chars, 21 words): `{FIRST_NAME} last one from me. is this relevant at all for {COMPANY} right now, yes, no or maybe later, lmk {MY_FIRST_NAME}`
  - variant 18 (121 chars, 23 words): `hey {FIRST_NAME}! wdyt, is there a better person at {COMPANY} i should be talking to about this or are you the right one?`
  - variant 19 (140 chars, 23 words): `{FIRST_NAME}, i'll leave it here. if the timing ever feels right for a chat about how {COMPANY} manages agency ops just lmk, {MY_FIRST_NAME}`
  - fallback (60 chars): `one last bump. wdyt, is it a yes, a not now or a not for us?`

### 429679 — OMEGA

- ownership: **unknown** — not in the ledger and not on any operator-declared internal list; UNKNOWN is the state, not a gap
- provider status `PAUSED`; created `2026-05-13T20:47:59.412256Z`; started `2026-05-13T20:48:19.465271Z`
- seats (`campaignAccountIds`): 174892, 174748, 175455, 174742, 174332, 174810, 174822, 174845, 174803, 174797, 208253, 208242, 129531, 181262, 212356, 143105, 116973, 116968, 156360, 169600, 177751, 116988, 116989, 119588, 125748, 125775, 129082, 139699, 186618, 201959, 181653, 181658, 194061, 191848, 179527, 201978, 175552, 159259
- lead list `668409` (PRODUCTIVE - OMEGA), list size `totalItemsCount` = 33710; campaign holds `progressStats.totalUsers` = 33710, finished 1035
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **8709**, accepted **1280** (14.70%)
  - messages sent **1911**, message threads started **1206**, replies **203** (16.83% of threads started)
  - unique leads contacted **8692**; profile views 1119, follows 0, post likes 5181
  - provider's own tags: `autoTaggedInterested` **31**, `totalAutoTagged` **203**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 1255 conversations joined, 13 operator-positive replies = **0.149 per 100 requests sent**
- reply classes in this campaign: `unknown` 187, `negative` 51, `automated` 16, `not_relevant` 15, `positive` 9, `objection` 6, `question` 4, `not_now` 4, `out_of_office` 3, `assistant_redirect` 2
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-05-14 .. 2026-09-15 (87 days)
- sequence node types present in the whole graph: CONNECTION_REQUEST, END, LIKE_POST, MESSAGE, SEND_LEAD_TO_BISON, VIEW_PROFILE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CONNECTION_REQUEST    wait 0H      day  0.00
  step 1   MESSAGE               wait 3H      day  0.12
  step 2   VIEW_PROFILE          wait 3D      day  3.12
  step 3   LIKE_POST             wait 2D      day  5.12
  step 4   SEND_LEAD_TO_BISON    wait 1D      day  6.12
  step 5   MESSAGE               wait 0H      day  6.12
  step 6   LIKE_POST             wait 5D      day 11.12
  step 7   MESSAGE               wait 1D      day 12.12
  step 8   LIKE_POST             wait 1D      day 13.12
  step 9   END                   wait 1D      day 14.12
```

**Connection note:** 1 `CONNECTION_REQUEST` note slot(s), every one of them EMPTY — this campaign sends connection requests with no note.

**Message steps — our text, in full:**

- message at day 0.12, 17 variant(s):
  - variant 1 (149 chars, 21 words): `hey {FIRST_NAME}, how does {COMPANY} currently track project profitability, is it all spreadsheets or do you have something in place? {MY_FIRST_NAME}`
  - variant 2 (181 chars, 33 words): `{FIRST_NAME} quick one, do you guys have resource planning sorted out at {COMPANY} or is that still a bit of a mess? asking cause i work with few {INDUSTRY} agencies on exactly that`
  - variant 3 (173 chars, 27 words): `hey {FIRST_NAME}! saw you're {POSITION} at {COMPANY}, curious how you handle billing and invoicing across projects, is it all manual or do you have a system? {MY_FIRST_NAME}`
  - variant 4 (429 chars, 68 words): `Hi {FIRST_NAME}, thanks for connecting. I'm a sales rep at Productive, where we help agencies run projects, resourcing and finances in one platform. 

If at {COMPANY} you're losing billable hours to manual timesheets, can't see project profitability in real time, or you're juggling separate tools for PM, time tracking and invoicing, we could be a real help. 

How are you handling that side of things right now? {MY_FIRST_NAME}`
  - variant 5 (364 chars, 59 words): `Hi {FIRST_NAME}, good to connect. Quick context, I'm a sales rep at Productive. 

How are you managing agency ops at {COMPANY} right now, solid system or still stitching things together? 

I ask because if you're stuck with gut feel forecasting, no live view of margin per project, or three to five disconnected tools, that's exactly what we fix. 

{MY_FIRST_NAME}`
  - variant 6 (276 chars, 44 words): `Hi {FIRST_NAME}, thanks for the add. I'm a sales rep at Productive. If at {COMPANY} you're battling lost billable hours, no real time profitability, and too many disconnected tools, we bring all of it into one platform. 

How's your current setup holding up? 

{MY_FIRST_NAME}`
  - variant 7 (401 chars, 69 words): `Hi {FIRST_NAME}, glad to be connected. I work in sales at Productive, helping agencies pull ops into one place. 

A lot of teams I speak to are stitching together separate tools, can't tell if a project is profitable until after invoicing, and lose hours to manual time tracking. 

If any of that sounds like {COMPANY}, I'd love to help. 

How are things running for you at the moment? {MY_FIRST_NAME}`
  - variant 8 (372 chars, 59 words): `Hi {FIRST_NAME}, thanks for connecting. I'm a sales rep at Productive. 

We help agency leaders who can't see margin while a project is still live, who lose billable time to manual timesheets, and who run resourcing across too many tools. If that's a fair picture of {COMPANY}, we could genuinely help. 

How are you tracking project profitability today? 

{MY_FIRST_NAME}`
  - variant 9 (328 chars, 52 words): `Hi {FIRST_NAME}, good to connect. I'm in sales at Productive. If at {COMPANY} you can't see team availability across projects in real time, you're forecasting on gut feel, and finance lives in a separate tool from delivery, that gap is exactly what we close. 

Curious how you're managing resourcing right now? 

{MY_FIRST_NAME}`
  - variant 10 (363 chars, 60 words): `Hi {FIRST_NAME}, thanks for the connection. I'm a sales rep at Productive. 

Most agencies we work with were running four or five tools for PM, time, budgets and invoicing, couldn't get a clean profitability number, and were losing billable hours in the gaps. 

We pull all of it into one platform. Is that close to how {COMPANY} operates today? 

{MY_FIRST_NAME}`
  - variant 11 (413 chars, 67 words): `Hi {FIRST_NAME}, appreciate the connect. I'm a sales rep at Productive and spend most of my time with agency ops people. 

The recurring pattern I hear is no live view of margin, billable hours slipping through manual timesheets, and resourcing scattered across separate tools. 

If that rings true for {COMPANY}, happy to share what's worked for similar teams. How are you set up at the moment? 

{MY_FIRST_NAME}`
  - variant 12 (262 chars, 42 words): `Hi {FIRST_NAME}, thanks for the add. Sales rep at Productive here. 

Disconnected tools, no real time profitability, billable hours going missing, if any of those are live issues at {COMPANY}, we can help. 

How are you managing it all right now? {MY_FIRST_NAME}`
  - variant 13 (559 chars, 89 words): `Hi {FIRST_NAME}, thanks for connecting.

I'm a sales rep at Productive, the platform that brings project management, resourcing, time tracking, budgets and invoicing into one place for agencies.

We mostly help agency and consultancy teams who lose billable hours to manual timesheets, can't see project profitability in real time, and are juggling four or five disconnected tools.

If any of that sounds like {COMPANY}, one brief call and we'll set your whole team up with a free premium trial.

How are you managing ops over there right now? {MY_FIRST_NAME}`
  - variant 14 (543 chars, 92 words): `Hi {FIRST_NAME}, good to connect.

Quick context, I'm a sales rep at Productive. We pull projects, resourcing and finances into a single platform built for agencies.

The teams we help usually have the same three headaches: gut feel forecasting, no live view of margin per project, and too many tools that don't talk to each other.

If that rings true for {COMPANY}, give me one short call and I'll get your whole team a free premium trial.

How are you handling all that today, solid system or still stitching things together? {MY_FIRST_NAME}`
  - variant 15 (526 chars, 86 words): `Hi {FIRST_NAME}, glad to be connected.

I work in sales at Productive and spend most of my time with agency ops people. We bring PM, time tracking, budgets and invoicing under one roof.

The pattern I keep hearing is billable hours slipping through manual timesheets, profitability you only see after the invoice goes out, and resourcing spread across separate tools.

If that's the picture at {COMPANY}, one brief call and your team gets a free premium trial, no strings.

How's your current setup holding up? {MY_FIRST_NAME}`
  - variant 16 (550 chars, 90 words): `Hi {FIRST_NAME}, thanks for the add.

I'm a sales rep at Productive, where we help agencies see project profitability while work is still live, not weeks after invoicing. Everything sits in one platform: projects, resourcing, time, budgets and billing.

Most leaders we speak to are stuck with no real time margin view, billable hours lost to manual tracking, and a stack of tools that don't connect.

If that's true for {COMPANY}, a quick call gets your whole team a free premium trial.

How are you tracking profitability right now? {MY_FIRST_NAME}`
  - variant 17 (522 chars, 87 words): `Hi {FIRST_NAME}, appreciate the connection.

I'm in sales at Productive. We replace the usual pile of agency tools with one platform that ties projects, resourcing, budgets and invoicing together.

Teams come to us when they're running four or five tools that don't sync, can't get a clean profitability number, and keep losing billable hours in the gaps.

If that sounds familiar at {COMPANY}, one short call and I'll set the whole team up on a free premium trial.

Is that close to how you operate today? {MY_FIRST_NAME}`
  - fallback (539 chars): `Hi, thanks for connecting.

I'm a sales rep at Productive, the platform that brings project management, resourcing, time tracking, budgets and invoicing into one place for agencies.

We mostly help teams who lose billable hours to manual timesheets, can't see project profitability in real time, and are juggling four or five disconnected tools.

If any of that sounds familiar, one brief call and we'll set your whole team up with a free premium trial.

How are you managing ops right now, solid system or still stitching things together?`
- message at day 6.12, 9 variant(s):
  - variant 1 (344 chars, 59 words): `Hi {FIRST_NAME}, just floating this back to the top of your inbox.

No worries if the timing's off, but if billable hours slipping away, no live profitability, or too many disconnected tools is a real thing at {COMPANY}, the offer still stands.

One brief call and your whole team gets a free premium trial.

Worth a quick chat? {MY_FIRST_NAME}`
  - variant 2 (326 chars, 58 words): `Hi {FIRST_NAME}, one quick question and I'll leave it there.

When someone at {COMPANY} needs to know if a project is actually profitable, how long does that take to pull together?

If the answer is longer than you'd like, that's exactly what we fix. One call and your team gets a free premium trial to see it. {MY_FIRST_NAME}`
  - variant 3 (350 chars, 59 words): `Hi {FIRST_NAME}, circling back with something concrete.

Hike One came to us with the same mess most agencies have, disconnected tools and no real time margin. They grew billable utilization 10% in their first year with us.

If {COMPANY} is anywhere near that, one brief call and your whole team gets a free premium trial. Open to it? {MY_FIRST_NAME}`
  - variant 4 (332 chars, 61 words): `Hi {FIRST_NAME}, want to make this easy.

The offer is a free premium trial for the entire {COMPANY} team, all I ask for first is one short call so I can set it up around how you actually work.

If lost billable hours, blurry profitability or tool sprawl are on your radar, it's worth the 20 minutes. When suits you? {MY_FIRST_NAME}`
  - variant 5 (341 chars, 59 words): `Hi {FIRST_NAME}, I don't want to keep nudging if it's not relevant.

Should I assume {COMPANY} has profitability, resourcing and billing well in hand, or is the disconnected tools thing still a quiet headache?

If it's the latter, one call gets your team a free premium trial. If not, no problem at all and I'll leave you be. {MY_FIRST_NAME}`
  - variant 6 (373 chars, 64 words): `Hi {FIRST_NAME}, following up with a different angle.

A lot of agency leads I talk to don't have a clean view of who's free across projects, so they overbook some people and lose billable time on others.

If {COMPANY} feels that, we put resourcing, projects and finances in one view. One brief call and your team gets a free premium trial. Worth exploring? {MY_FIRST_NAME}`
  - variant 7 (374 chars, 65 words): `Hi {FIRST_NAME}, quick thought to leave with you.

The expensive part of disconnected tools isn't the subscriptions, it's the billable hours that quietly leak out and the projects you find out were unprofitable too late to fix.

If that's a risk at {COMPANY}, one call and your team gets a free premium trial to see the whole picture in one place. Up for it? {MY_FIRST_NAME}`
  - variant 8 (233 chars, 39 words): `Hi {FIRST_NAME}, still happy to set {COMPANY} up with a free premium trial for the whole team after one short call.

Are lost billable hours, profitability blind spots, or too many tools live issues for you right now? {MY_FIRST_NAME}`
  - variant 9 (343 chars, 55 words): `Hi {FIRST_NAME}, last one from me so I'm not cluttering your inbox.

If the disconnected tools, hidden profitability and lost billable hours stuff ever becomes a priority at {COMPANY}, the door's open and the free team trial offer stands.

Just say the word and we'll grab 20 minutes. Otherwise, genuinely good to be connected. {MY_FIRST_NAME}`
  - fallback (429 chars): `Hi, just following up on my last message.

No worries if the timing's off, but if losing billable hours to manual timesheets, no real time view of project profitability, or juggling too many disconnected tools is a live issue for you, the offer still stands.

One brief call and we'll set your whole team up with a free premium trial.

Are any of those pain points hitting home right now? Happy to grab 20 minutes whenever suits.`
- message at day 12.12, 8 variant(s):
  - variant 1 (165 chars, 28 words): `Hey {FIRST_NAME}, still relevant?

Free premium trial for the {COMPANY} team is on the table, just need one quick call to set it up.

Lmk either way. {MY_FIRST_NAME}`
  - variant 2 (195 chars, 32 words): `Hey {FIRST_NAME}, quick one.

Is the projects, profitability and tools thing still worth solving at {COMPANY}, or have you got it covered?

Yes, no, or not now all work. Just lmk. {MY_FIRST_NAME}`
  - variant 3 (228 chars, 38 words): `Hey {FIRST_NAME}, still on your radar?

If ops and profitability isn't your area, totally fine, just point me to whoever owns it at {COMPANY} and I'll take it from there.

Free team trial offer stands either way. {MY_FIRST_NAME}`
  - variant 4 (189 chars, 33 words): `Hey {FIRST_NAME}, still relevant or just bad timing?

If now's not it, tell me when to circle back and I'll get out of your inbox.

The free team trial isn't going anywhere. {MY_FIRST_NAME}`
  - variant 5 (198 chars, 30 words): `Hey {FIRST_NAME}, still relevant?

Simple test: can you see right now whether your live projects at {COMPANY} are profitable?

If not, that's the call. Free team trial included. Lmk. {MY_FIRST_NAME}`
  - variant 6 (222 chars, 35 words): `Hey {FIRST_NAME}, still relevant?

One agency like yours grew billable utilization 10% in a year after ditching the disconnected tools.

Happy to show you how on a quick call, free team trial included. Lmk. {MY_FIRST_NAME}`
  - variant 7 (219 chars, 35 words): `Hey {FIRST_NAME}, chasing you gently here, promise this is friendly not pushy.

Still worth getting {COMPANY} that free team trial, or has the moment passed?

A one word reply saves us both the guessing. {MY_FIRST_NAME}`
  - variant 8 (238 chars, 41 words): `Hey {FIRST_NAME}, I'll take the quiet as a no for now, all good.

If the profitability, resourcing or tool sprawl stuff ever bites at {COMPANY}, the free team trial offer is here whenever.

Just say the word down the line. {MY_FIRST_NAME}`
  - fallback (250 chars): `Hey, still relevant?

Free premium trial for your whole team is on the table, just need one quick call to set it up.

If losing billable hours, no real time profitability, or too many disconnected tools is still a thing, worth a chat. Lmk either way.`

### 429680 — OMEGA 2

- ownership: **unknown** — not in the ledger and not on any operator-declared internal list; UNKNOWN is the state, not a gap
- provider status `PAUSED`; created `2026-05-13T20:48:32.151644Z`; started `2026-05-13T20:49:02.821147Z`
- seats (`campaignAccountIds`): 174892, 174748, 175455, 174742, 174332, 174810, 174822, 174845, 174803, 174797, 208253, 208242, 129531, 181262, 212356, 143105, 175552, 201978, 179527, 159259, 191848, 194061, 181658, 201969, 181653, 201959, 186618, 139699, 129082, 125775, 125748, 119588, 116989, 116988, 116973, 116968, 156360, 169600, 177751
- lead list `668409` (PRODUCTIVE - OMEGA), list size `totalItemsCount` = 33710; campaign holds `progressStats.totalUsers` = 33710, finished 159
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **5911**, accepted **754** (12.76%)
  - messages sent **647**, message threads started **574**, replies **55** (9.58% of threads started)
  - unique leads contacted **5868**; profile views 18912, follows 9484, post likes 12958
  - provider's own tags: `autoTaggedInterested` **11**, `totalAutoTagged` **55**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 597 conversations joined, 3 operator-positive replies = **0.051 per 100 requests sent**
- reply classes in this campaign: `unknown` 40, `negative` 18, `automated` 6, `question` 2, `positive` 1, `unsubscribe` 1
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-06-08 .. 2026-08-30 (55 days)
- sequence node types present in the whole graph: CONNECTION_REQUEST, END, FOLLOW, LIKE_POST, MESSAGE, SEND_LEAD_TO_BISON, VIEW_PROFILE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   VIEW_PROFILE          wait 0H      day  0.00
  step 1   LIKE_POST             wait 10D     day 10.00
  step 2   FOLLOW                wait 10D     day 20.00
  step 3   CONNECTION_REQUEST    wait 5D      day 25.00
  step 4   MESSAGE               wait 2D      day 27.00
  step 5   VIEW_PROFILE          wait 1D      day 28.00
  step 6   LIKE_POST             wait 1D      day 29.00
  step 7   SEND_LEAD_TO_BISON    wait 1D      day 30.00
  step 8   MESSAGE               wait 0H      day 30.00
  step 9   LIKE_POST             wait 5D      day 35.00
  step 10  MESSAGE               wait 1D      day 36.00
  step 11  LIKE_POST             wait 1D      day 37.00
  step 12  END                   wait 1D      day 38.00
```

**Connection note — our text, in full (15 variant(s)):**

1. (134 chars, 19 words) `Hi {FIRST_NAME}, we help {INDUSTRY} teams in {LOCATION} get real-time visibility into project profitability. Would be good to connect.`
2. (124 chars, 20 words) `Hi {FIRST_NAME}, work with a bunch of {INDUSTRY} teams who ditched the spreadsheet juggle for one tool. Figured I'd connect.`
3. (149 chars, 22 words) `Hi {FIRST_NAME}, curious how your team tracks project budgets and resourcing today. Most {INDUSTRY} teams stitch it across tools. Open to connecting?`
4. (138 chars, 21 words) `Hi {FIRST_NAME}, we've helped {INDUSTRY} teams cut manual reporting and grow billable utilization, one up 10% in a year. Worth connecting?`
5. (128 chars, 25 words) `Hi {FIRST_NAME}, bet I can solve every project and budget headache your team has on one call. If not, coffee's on me. Up for it?`
6. (128 chars, 25 words) `Hi {FIRST_NAME}, bet I can solve every project and budget headache your team has on one call. If not, coffee's on me. Up for it?`
7. (128 chars, 25 words) `Hi {FIRST_NAME}, bet I can solve every project and budget headache your team has on one call. If not, coffee's on me. Up for it?`
8. (128 chars, 25 words) `Hi {FIRST_NAME}, bet I can solve every project and budget headache your team has on one call. If not, coffee's on me. Up for it?`
9. (140 chars, 24 words) `Hi {FIRST_NAME}, give me one call and I'll tackle your biggest project, budgeting, and resourcing pains. If I can't, I'll send you a coffee.`
10. (140 chars, 24 words) `Hi {FIRST_NAME}, give me one call and I'll tackle your biggest project, budgeting, and resourcing pains. If I can't, I'll send you a coffee.`
11. (135 chars, 23 words) `Hi {FIRST_NAME}, where does your team lose the most time, timesheets, forecasting, or reporting? One call to fix it, or coffee's on me.`
12. (127 chars, 20 words) `Hi {FIRST_NAME}, help {INDUSTRY} teams run projects, time, and budgets in one place instead of five tools. Figured I'd connect.`
13. (132 chars, 26 words) `Hi {FIRST_NAME}, one call and I'll show how to kill the spreadsheet chaos for good. If I can't, I'll buy you a coffee. Worth a shot?`
14. (132 chars, 26 words) `Hi {FIRST_NAME}, one call and I'll show how to kill the spreadsheet chaos for good. If I can't, I'll buy you a coffee. Worth a shot?`
15. (130 chars, 21 words) `Hi {FIRST_NAME}, we get teams off spreadsheets and into one place for projects, budgets, and resourcing. Would be good to connect.`

**Message steps — our text, in full:**

- message at day 27.00, 13 variant(s):
  - variant 1 (166 chars, 29 words): `Hi {FIRST_NAME}, following up.

Saw {COMPANY} and thought it was a real fit.

Worth a quick look?

P.S. Hope your bracket is surviving the World Cup better than mine.`
  - variant 2 (185 chars, 32 words): `Hi {FIRST_NAME}, circling back.

I genuinely think {INDUSTRY} teams like yours benefit most from this.

Happy to show you why.

Let me know.

P.S. Who are you backing for the World Cup?`
  - variant 3 (199 chars, 34 words): `Hi {FIRST_NAME}, following up.

If timesheets, forecasting, or reporting eat your team's time, that's exactly what we fix.

I see a real fit here.

P.S. Catching any of the World Cup games this week?`
  - variant 4 (209 chars, 36 words): `Hi {FIRST_NAME}, no pitch.

Even if we never talk, happy to share how {INDUSTRY} teams cut reporting time.

I think you'd benefit.

Let me know.

P.S. Hope the World Cup isn't wrecking your sleep schedule too.`
  - variant 5 (210 chars, 36 words): `Hi {FIRST_NAME}, quick follow-up.

We helped a similar {INDUSTRY} team grow billable utilization 10% in a year.

The fit looks real.

Worth 15 min?

P.S. Any World Cup predictions, or are you staying out of it?`
  - variant 6 (178 chars, 33 words): `Hi {FIRST_NAME}, won't keep chasing.

I genuinely think {COMPANY} is a fit.

If I'm wrong, tell me and I'll back off.

Fair?

P.S. Hope your team is still alive in the World Cup.`
  - variant 7 (210 chars, 36 words): `Hi {FIRST_NAME}, following up.

Curious if project profitability visibility is even a priority right now.

Only reaching out because I see a fit.

P.S. Been a wild World Cup so far, any early standouts for you?`
  - variant 8 (158 chars, 28 words): `Hi {FIRST_NAME}, last nudge.

Saw {COMPANY} and thought it lined up well.

No rush, just let me know either way.

P.S. Enjoy the World Cup games this weekend.`
  - variant 9 (214 chars, 36 words): `Hi {FIRST_NAME}, circling back.

We get {INDUSTRY} teams off spreadsheets into one place for projects, time, and budgets.

The fit looks genuine.

Open to a chat?

P.S. Who's your pick to lift the World Cup trophy?`
  - variant 10 (125 chars, 24 words): `Hi {FIRST_NAME}, following up.

I think your team's a strong fit for what we do.

Happy to show you.

Let me know either way.`
  - variant 11 (125 chars, 24 words): `Hi {FIRST_NAME}, following up.

I think your team's a strong fit for what we do.

Happy to show you.

Let me know either way.`
  - variant 12 (125 chars, 24 words): `Hi {FIRST_NAME}, following up.

I think your team's a strong fit for what we do.

Happy to show you.

Let me know either way.`
  - variant 13 (125 chars, 24 words): `Hi {FIRST_NAME}, following up.

I think your team's a strong fit for what we do.

Happy to show you.

Let me know either way.`
  - fallback (112 chars): `Hi, following up.

I think your team's a strong fit for what we do.

Happy to show you.

Let me know either way.`
- message at day 30.00, 14 variant(s):
  - variant 1 (186 chars, 30 words): `hey {FIRST_NAME}, just bumping this up, agencies like {COMPANY} usually tell us the biggest thing is not knowing project profitability until its too late. is that something you run into?`
  - variant 2 (170 chars, 28 words): `{FIRST_NAME} following up, i know its probably not top of mind but curious, how are you guys currently handling resource planning, got something or still figuring it out?`
  - variant 3 (226 chars, 35 words): `hey {FIRST_NAME}! didn't hear back, no worries. just wanted to add, most {INDUSTRY} agencies we work with were running projects, finances and resourcing across 3-4 tools before consolidating. is that the case at {COMPANY} too?`
  - variant 4 (183 chars, 30 words): `{FIRST_NAME}, just checking in. one thing that comes up a lot with {INDUSTRY} agencies is losing billable hours just cause time tracking is inconsistent. is that a thing at {COMPANY}?`
  - variant 5 (184 chars, 30 words): `hey {FIRST_NAME}, following up on my last message. not trying to be annoying, genuinely curious if operational visibility is something {COMPANY} has sorted or if its still a pain point`
  - variant 6 (212 chars, 32 words): `{FIRST_NAME} hi, just bumping this. agencies usually lose a surprising amount of revenue just from projects going over budget without anyone catching it early. does that ring a bell at {COMPANY}? 
{MY_FIRST_NAME}`
  - variant 7 (179 chars, 31 words): `hey {FIRST_NAME}! quick follow up, do you guys have a way to see team utilization and project finances in one place or is that something you're still working towards at {COMPANY}?`
  - variant 8 (233 chars, 40 words): `{FIRST_NAME}, i know you're probably busy but wanted to follow up. most {POSITION}s we talk to at {INDUSTRY} agencies say the hardest thing is getting a clear picture of whats profitable and whats not. is that fair for {COMPANY} too?`
  - variant 9 (191 chars, 32 words): `hey {FIRST_NAME}, just circling back. not asking for a demo or anything, just curious, is agency ops something that feels under control at {COMPANY} right now or more of an ongoing challenge?`
  - variant 10 (241 chars, 40 words): `{FIRST_NAME} following up, one thing worth mentioning, agencies that get resourcing and project finances in one place usually save a meaningful chunk of time on admin every week. curious if that kind of thing would matter to you at {COMPANY}`
  - variant 11 (174 chars, 30 words): `hey {FIRST_NAME}! bumping this up, is now just a bad time or is operational tooling not really a priority at {COMPANY} right now? either way just let me know, {MY_FIRST_NAME}`
  - variant 12 (222 chars, 37 words): `hey {FIRST_NAME}, circling back quickly. a lot of {INDUSTRY} agencies tell us they only realize a project went sideways after invoicing. does that happen at {COMPANY} or do you have visibility before it gets to that point?`
  - variant 13 (169 chars, 26 words): `{FIRST_NAME}, just checking in, is this landing with the wrong person? happy to connect with whoever handles ops or tooling at {COMPANY} if thats easier, {MY_FIRST_NAME}`
  - variant 14 (202 chars, 34 words): `{FIRST_NAME}, i'll keep this short. is operational visibility something {COMPANY} has a good handle on or is it one of those things that could always be better? worth a quick chat if so, {MY_FIRST_NAME}`
  - fallback (180 chars): `hey, i'll keep this short. is operational visibility something your company has a good handle on or is it one of those things that could always be better? worth a quick chat if so?`
- message at day 36.00, 19 variant(s):
  - variant 1 (37 chars, 5 words): `hey {FIRST_NAME}, still relevant? lmk`
  - variant 2 (37 chars, 5 words): `hey {FIRST_NAME}, still relevant? lmk`
  - variant 3 (122 chars, 20 words): `hey {FIRST_NAME}! is ops and project visibility something {COMPANY} has sorted or still a work in progress, lmk either way`
  - variant 4 (71 chars, 12 words): `{FIRST_NAME}, bad timing or just not relevant? either is fine, just lmk`
  - variant 5 (109 chars, 16 words): `hey {FIRST_NAME}, wdyt, is managing projects and finances in one place something {COMPANY} would find useful?`
  - variant 6 (81 chars, 12 words): `{FIRST_NAME} still open to connecting? lmk and ill keep it short, {MY_FIRST_NAME}`
  - variant 7 (90 chars, 17 words): `hey {FIRST_NAME}! last one from me, wdyt, worth 15 min or not really a priority right now?`
  - variant 8 (96 chars, 17 words): `hey {FIRST_NAME}, no worries if the timings off, just lmk and ill follow up whenever makes sense`
  - variant 9 (147 chars, 20 words): `{FIRST_NAME} wdyt, is operational visibility something {COMPANY} is actively trying to improve or pretty happy with how things are? {MY_FIRST_NAME}`
  - variant 10 (96 chars, 18 words): `hey {FIRST_NAME}! just lmk if this isnt relevant and ill get out of your inbox, no hard feelings`
  - variant 11 (90 chars, 18 words): `{FIRST_NAME}, one last bump. wdyt, is it a yes, a not now or a not for us? {MY_FIRST_NAME}`
  - variant 12 (108 chars, 14 words): `hey {FIRST_NAME}, is project profitability something {COMPANY} tracks well right now, genuinely curious, lmk`
  - variant 13 (86 chars, 17 words): `{FIRST_NAME} hi, wdyt, open to a quick look or not the right time? either works for me`
  - variant 14 (125 chars, 20 words): `hey {FIRST_NAME}! last message i promise. is agency ops a pain point at {COMPANY} or pretty much handled, lmk {MY_FIRST_NAME}`
  - variant 15 (96 chars, 15 words): `{FIRST_NAME}, still think there could be something here for {COMPANY}. wdyt, worth a quick call?`
  - variant 16 (109 chars, 24 words): `hey {FIRST_NAME}, just lmk if you want me to send over some info or if its better i reach out in a few months`
  - variant 17 (123 chars, 21 words): `{FIRST_NAME} last one from me. is this relevant at all for {COMPANY} right now, yes, no or maybe later, lmk {MY_FIRST_NAME}`
  - variant 18 (121 chars, 23 words): `hey {FIRST_NAME}! wdyt, is there a better person at {COMPANY} i should be talking to about this or are you the right one?`
  - variant 19 (140 chars, 23 words): `{FIRST_NAME}, i'll leave it here. if the timing ever feels right for a chat about how {COMPANY} manages agency ops just lmk, {MY_FIRST_NAME}`
  - fallback (60 chars): `one last bump. wdyt, is it a yes, a not now or a not for us?`

### 467366 — OMEGA 3

- ownership: **unknown** — not in the ledger and not on any operator-declared internal list; UNKNOWN is the state, not a gap
- provider status `PAUSED`; created `2026-06-12T11:52:02.701025Z`; started `2026-06-12T11:53:53.893868Z`
- seats (`campaignAccountIds`): 174892, 174748, 175455, 174742, 174332, 174810, 174822, 174845, 174803, 174797, 208253, 208242, 129531, 181262, 212356, 143105, 175552, 201978, 179527, 159259, 191848, 194061, 181658, 201969, 116989, 119588, 125748, 125775, 129082, 139699, 186618, 201959, 181653, 116988, 116973, 116968, 156360, 169600, 177751
- lead list `668409` (PRODUCTIVE - OMEGA), list size `totalItemsCount` = 33710; campaign holds `progressStats.totalUsers` = 33710, finished 713
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **7988**, accepted **1091** (13.66%)
  - messages sent **1912**, message threads started **1048**, replies **151** (14.41% of threads started)
  - unique leads contacted **8065**; profile views 835, follows 0, post likes 4984
  - provider's own tags: `autoTaggedInterested` **57**, `totalAutoTagged` **151**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 1040 conversations joined, 23 operator-positive replies = **0.288 per 100 requests sent**
- reply classes in this campaign: `unknown` 138, `negative` 22, `positive` 15, `automated` 13, `question` 8, `objection` 5, `not_relevant` 5, `send_info` 2, `out_of_office` 1, `assistant_redirect` 1
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-06-12 .. 2026-09-11 (54 days)
- sequence node types present in the whole graph: CONNECTION_REQUEST, END, LIKE_POST, MESSAGE, SEND_LEAD_TO_BISON, VIEW_PROFILE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CONNECTION_REQUEST    wait 0H      day  0.00
  step 1   MESSAGE               wait 3D      day  3.00
  step 2   VIEW_PROFILE          wait 5D      day  8.00
  step 3   LIKE_POST             wait 5D      day 13.00
  step 4   SEND_LEAD_TO_BISON    wait 1D      day 14.00
  step 5   MESSAGE               wait 0H      day 14.00
  step 6   LIKE_POST             wait 5D      day 19.00
  step 7   MESSAGE               wait 1D      day 20.00
  step 8   LIKE_POST             wait 1D      day 21.00
  step 9   END                   wait 1D      day 22.00
```

**Connection note — our text, in full (1 variant(s)):**

1. (19 chars, 3 words) `Hey, let's connect!`

**Message steps — our text, in full:**

- message at day 3.00, 20 variant(s):
  - variant 1 (149 chars, 21 words): `hey {FIRST_NAME}, how does {COMPANY} currently track project profitability, is it all spreadsheets or do you have something in place? {MY_FIRST_NAME}`
  - variant 2 (181 chars, 33 words): `{FIRST_NAME} quick one, do you guys have resource planning sorted out at {COMPANY} or is that still a bit of a mess? asking cause i work with few {INDUSTRY} agencies on exactly that`
  - variant 3 (173 chars, 27 words): `hey {FIRST_NAME}! saw you're {POSITION} at {COMPANY}, curious how you handle billing and invoicing across projects, is it all manual or do you have a system? {MY_FIRST_NAME}`
  - variant 4 (185 chars, 29 words): `{FIRST_NAME}, random question but how many tools is {COMPANY} using to manage projects, resources and finances? asking cause most {INDUSTRY} agencies we talk to are juggling way to many`
  - variant 5 (152 chars, 25 words): `hey {FIRST_NAME}, do you guys have visibility on which projects are actually profitable at {COMPANY} or is that something you figure out after the fact?`
  - variant 6 (182 chars, 27 words): `{FIRST_NAME} hi, is resource planning something {COMPANY} has figured out or still a work in progress? we work with {INDUSTRY} agencies on getting that under control, {MY_FIRST_NAME}`
  - variant 7 (167 chars, 27 words): `hey {FIRST_NAME}! as {POSITION} at {COMPANY} curious if you have a single place where projects, budgets and resourcing all live or if its spread across different tools`
  - variant 8 (168 chars, 24 words): `{FIRST_NAME}, how do you guys handle project budgets at {COMPANY}, got that sorted or still piecing it together across spreadsheets and different tools? {MY_FIRST_NAME}`
  - variant 9 (162 chars, 28 words): `hey {FIRST_NAME}, do you have a good handle on utilization across the team at {COMPANY} or is that one of those things thats always a bit unclear? {MY_FIRST_NAME}`
  - variant 10 (156 chars, 25 words): `{FIRST_NAME} quick question, how does {COMPANY} track whether projects are staying on budget, is that something you have sorted or more of a manual process?`
  - variant 11 (176 chars, 28 words): `hey {FIRST_NAME}! saw {COMPANY} and was curious, whats the biggest operational headache for you guys right now, is it resourcing, profitability or just to many tools to manage?`
  - variant 12 (160 chars, 25 words): `{FIRST_NAME}, is invoicing and billing something {COMPANY} has nailed down or still one of those things that takes way more time than it should? {MY_FIRST_NAME}`
  - variant 13 (130 chars, 22 words): `hey {FIRST_NAME}, how do you guys forecast revenue at {COMPANY}, got a solid process or still kinda winging it quarter to quarter?`
  - variant 14 (186 chars, 32 words): `{FIRST_NAME} hi! as {POSITION} at a {INDUSTRY} agency curious if you have clear visibility on team capacity at any given time or if thats always a bit of a guessing game, {MY_FIRST_NAME}`
  - variant 15 (151 chars, 25 words): `hey {FIRST_NAME}, do you guys have project management, resourcing and finances in one place at {COMPANY} or is it spread across like 4 different tools?`
  - variant 16 (151 chars, 28 words): `{FIRST_NAME}, quick one, how does {COMPANY} know if a project is going to hit budget before it's to late to do anything about it? got that figured out?`
  - variant 17 (202 chars, 31 words): `hey {FIRST_NAME}! {MY_FIRST_NAME} here, i work with {INDUSTRY} agencies on operational stuff. curious if {COMPANY} has a handle on project profitability in real time or its more of a retrospective thing`
  - variant 18 (158 chars, 24 words): `{FIRST_NAME} is time tracking something the team at {COMPANY} actually does consistently or is that one of those things thats always a battle? {MY_FIRST_NAME}`
  - variant 19 (174 chars, 30 words): `hey {FIRST_NAME}, saw you're {POSITION} at {COMPANY}. do you have one place where you can see project status, team capacity and finances together or is it all over the place?`
  - variant 20 (148 chars, 23 words): `{FIRST_NAME} hi, how are you guys managing agency ops at {COMPANY} right now, got a solid system or still stitching things together? {MY_FIRST_NAME}`
  - fallback (125 chars): `hey, do you guys have project management, resourcing and finances in one place or is it spread across like 4 different tools?`
- message at day 14.00, 14 variant(s):
  - variant 1 (186 chars, 30 words): `hey {FIRST_NAME}, just bumping this up, agencies like {COMPANY} usually tell us the biggest thing is not knowing project profitability until its too late. is that something you run into?`
  - variant 2 (170 chars, 28 words): `{FIRST_NAME} following up, i know its probably not top of mind but curious, how are you guys currently handling resource planning, got something or still figuring it out?`
  - variant 3 (226 chars, 35 words): `hey {FIRST_NAME}! didn't hear back, no worries. just wanted to add, most {INDUSTRY} agencies we work with were running projects, finances and resourcing across 3-4 tools before consolidating. is that the case at {COMPANY} too?`
  - variant 4 (183 chars, 30 words): `{FIRST_NAME}, just checking in. one thing that comes up a lot with {INDUSTRY} agencies is losing billable hours just cause time tracking is inconsistent. is that a thing at {COMPANY}?`
  - variant 5 (184 chars, 30 words): `hey {FIRST_NAME}, following up on my last message. not trying to be annoying, genuinely curious if operational visibility is something {COMPANY} has sorted or if its still a pain point`
  - variant 6 (212 chars, 32 words): `{FIRST_NAME} hi, just bumping this. agencies usually lose a surprising amount of revenue just from projects going over budget without anyone catching it early. does that ring a bell at {COMPANY}? 
{MY_FIRST_NAME}`
  - variant 7 (179 chars, 31 words): `hey {FIRST_NAME}! quick follow up, do you guys have a way to see team utilization and project finances in one place or is that something you're still working towards at {COMPANY}?`
  - variant 8 (233 chars, 40 words): `{FIRST_NAME}, i know you're probably busy but wanted to follow up. most {POSITION}s we talk to at {INDUSTRY} agencies say the hardest thing is getting a clear picture of whats profitable and whats not. is that fair for {COMPANY} too?`
  - variant 9 (191 chars, 32 words): `hey {FIRST_NAME}, just circling back. not asking for a demo or anything, just curious, is agency ops something that feels under control at {COMPANY} right now or more of an ongoing challenge?`
  - variant 10 (241 chars, 40 words): `{FIRST_NAME} following up, one thing worth mentioning, agencies that get resourcing and project finances in one place usually save a meaningful chunk of time on admin every week. curious if that kind of thing would matter to you at {COMPANY}`
  - variant 11 (174 chars, 30 words): `hey {FIRST_NAME}! bumping this up, is now just a bad time or is operational tooling not really a priority at {COMPANY} right now? either way just let me know, {MY_FIRST_NAME}`
  - variant 12 (222 chars, 37 words): `hey {FIRST_NAME}, circling back quickly. a lot of {INDUSTRY} agencies tell us they only realize a project went sideways after invoicing. does that happen at {COMPANY} or do you have visibility before it gets to that point?`
  - variant 13 (169 chars, 26 words): `{FIRST_NAME}, just checking in, is this landing with the wrong person? happy to connect with whoever handles ops or tooling at {COMPANY} if thats easier, {MY_FIRST_NAME}`
  - variant 14 (202 chars, 34 words): `{FIRST_NAME}, i'll keep this short. is operational visibility something {COMPANY} has a good handle on or is it one of those things that could always be better? worth a quick chat if so, {MY_FIRST_NAME}`
  - fallback (180 chars): `hey, i'll keep this short. is operational visibility something your company has a good handle on or is it one of those things that could always be better? worth a quick chat if so?`
- message at day 20.00, 19 variant(s):
  - variant 1 (37 chars, 5 words): `hey {FIRST_NAME}, still relevant? lmk`
  - variant 2 (37 chars, 5 words): `hey {FIRST_NAME}, still relevant? lmk`
  - variant 3 (122 chars, 20 words): `hey {FIRST_NAME}! is ops and project visibility something {COMPANY} has sorted or still a work in progress, lmk either way`
  - variant 4 (71 chars, 12 words): `{FIRST_NAME}, bad timing or just not relevant? either is fine, just lmk`
  - variant 5 (109 chars, 16 words): `hey {FIRST_NAME}, wdyt, is managing projects and finances in one place something {COMPANY} would find useful?`
  - variant 6 (81 chars, 12 words): `{FIRST_NAME} still open to connecting? lmk and ill keep it short, {MY_FIRST_NAME}`
  - variant 7 (90 chars, 17 words): `hey {FIRST_NAME}! last one from me, wdyt, worth 15 min or not really a priority right now?`
  - variant 8 (96 chars, 17 words): `hey {FIRST_NAME}, no worries if the timings off, just lmk and ill follow up whenever makes sense`
  - variant 9 (147 chars, 20 words): `{FIRST_NAME} wdyt, is operational visibility something {COMPANY} is actively trying to improve or pretty happy with how things are? {MY_FIRST_NAME}`
  - variant 10 (96 chars, 18 words): `hey {FIRST_NAME}! just lmk if this isnt relevant and ill get out of your inbox, no hard feelings`
  - variant 11 (90 chars, 18 words): `{FIRST_NAME}, one last bump. wdyt, is it a yes, a not now or a not for us? {MY_FIRST_NAME}`
  - variant 12 (108 chars, 14 words): `hey {FIRST_NAME}, is project profitability something {COMPANY} tracks well right now, genuinely curious, lmk`
  - variant 13 (86 chars, 17 words): `{FIRST_NAME} hi, wdyt, open to a quick look or not the right time? either works for me`
  - variant 14 (125 chars, 20 words): `hey {FIRST_NAME}! last message i promise. is agency ops a pain point at {COMPANY} or pretty much handled, lmk {MY_FIRST_NAME}`
  - variant 15 (96 chars, 15 words): `{FIRST_NAME}, still think there could be something here for {COMPANY}. wdyt, worth a quick call?`
  - variant 16 (109 chars, 24 words): `hey {FIRST_NAME}, just lmk if you want me to send over some info or if its better i reach out in a few months`
  - variant 17 (123 chars, 21 words): `{FIRST_NAME} last one from me. is this relevant at all for {COMPANY} right now, yes, no or maybe later, lmk {MY_FIRST_NAME}`
  - variant 18 (121 chars, 23 words): `hey {FIRST_NAME}! wdyt, is there a better person at {COMPANY} i should be talking to about this or are you the right one?`
  - variant 19 (140 chars, 23 words): `{FIRST_NAME}, i'll leave it here. if the timing ever feels right for a chat about how {COMPANY} manages agency ops just lmk, {MY_FIRST_NAME}`
  - fallback (60 chars): `one last bump. wdyt, is it a yes, a not now or a not for us?`

### 467951 — inmail

- ownership: **unknown** — not in the ledger and not on any operator-declared internal list; UNKNOWN is the state, not a gap
- provider status `PAUSED`; created `2026-06-12T17:06:53.808587Z`; started `2026-06-12T17:13:08.509838Z`
- seats (`campaignAccountIds`): 174892, 174748, 175455, 174742, 174332, 174822, 174845, 174803, 208242, 174797
- lead list `727022` (inmails), list size `totalItemsCount` = 218; campaign holds `progressStats.totalUsers` = 218, finished 58
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **0**, accepted **0** (n/a (denominator 0))
  - messages sent **0**, message threads started **0**, replies **0** (n/a (denominator 0) of threads started)
  - InMail: started **217**, replies **31** (14.29%). `inmailMessagesSent` is **0** here and on every campaign on this seat — the InMail volume lives in `totalInmailStarted`, so a reader asking `inmailMessagesSent` sees zero.
  - unique leads contacted **217**; profile views 41, follows 28, post likes 28
  - provider's own tags: `autoTaggedInterested` **1**, `totalAutoTagged` **31**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 247 conversations joined, 5 operator-positive replies = **n/a (0 requests sent) per 100 requests sent**
- reply classes in this campaign: `unknown` 47, `negative` 28, `automated` 4, `positive` 4, `out_of_office` 2, `question` 1
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- sequence node types present in the whole graph: END, FOLLOW, INMAIL, LIKE_POST, VIEW_PROFILE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   INMAIL                wait 0H      day  0.00
  step 1   VIEW_PROFILE          wait 3H      day  0.12
  step 2   LIKE_POST             wait 3H      day  0.25
  step 3   FOLLOW                wait 3H      day  0.38
  step 4   END                   wait 1D      day  1.38
```

**Connection note:** this graph has no `CONNECTION_REQUEST` node, so no note is sent.


### 470010 — Warmup 1

- ownership: **unknown** — not in the ledger and not on any operator-declared internal list; UNKNOWN is the state, not a gap
- provider status `PAUSED`; created `2026-06-15T13:25:37.821647Z`; started `2026-06-15T13:37:12.276409Z`
- seats (`campaignAccountIds`): 181262, 212356, 143105, 175552, 201978
- lead list `730071` (Productive employees warmup), list size `totalItemsCount` = 178; campaign holds `progressStats.totalUsers` = 178, finished 0
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **136**, accepted **80** (58.82%)
  - messages sent **0**, message threads started **0**, replies **0** (n/a (denominator 0) of threads started)
  - unique leads contacted **136**; profile views 0, follows 0, post likes 232
  - provider's own tags: `autoTaggedInterested` **0**, `totalAutoTagged` **0**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 0 conversations joined, 0 operator-positive replies = **0.000 per 100 requests sent**
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-06-15 .. 2026-06-30 (14 days)
- sequence node types present in the whole graph: CONNECTION_REQUEST, END, LIKE_POST
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CONNECTION_REQUEST    wait 0H      day  0.00
  step 1   LIKE_POST             wait 10D     day 10.00
  step 2   LIKE_POST             wait 10D     day 20.00
  step 3   LIKE_POST             wait 10D     day 30.00
  step 4   LIKE_POST             wait 10D     day 40.00
  step 5   LIKE_POST             wait 10D     day 50.00
  step 6   LIKE_POST             wait 10D     day 60.00
  step 7   LIKE_POST             wait 10D     day 70.00
  step 8   LIKE_POST             wait 10D     day 80.00
  step 9   LIKE_POST             wait 10D     day 90.00
  step 10  LIKE_POST             wait 10D     day 100.00
  step 11  LIKE_POST             wait 10D     day 110.00
  step 12  LIKE_POST             wait 40D     day 150.00
  step 13  LIKE_POST             wait 40D     day 190.00
  step 14  END                   wait 1D      day 191.00
```

**Connection note:** 1 `CONNECTION_REQUEST` note slot(s), every one of them EMPTY — this campaign sends connection requests with no note.


### 470035 — Warmup 2

- ownership: **unknown** — not in the ledger and not on any operator-declared internal list; UNKNOWN is the state, not a gap
- provider status `PAUSED`; created `2026-06-15T13:35:20.325417Z`; started `2026-06-15T13:38:00.842012Z`
- seats (`campaignAccountIds`): 179527, 159259, 129531, 191848, 194061
- lead list `730071` (Productive employees warmup), list size `totalItemsCount` = 178; campaign holds `progressStats.totalUsers` = 178, finished 0
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **141**, accepted **79** (56.03%)
  - messages sent **0**, message threads started **0**, replies **0** (n/a (denominator 0) of threads started)
  - unique leads contacted **141**; profile views 0, follows 0, post likes 279
  - provider's own tags: `autoTaggedInterested` **0**, `totalAutoTagged` **0**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 0 conversations joined, 0 operator-positive replies = **0.000 per 100 requests sent**
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-06-15 .. 2026-07-02 (13 days)
- sequence node types present in the whole graph: CONNECTION_REQUEST, END, LIKE_POST
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CONNECTION_REQUEST    wait 0H      day  0.00
  step 1   LIKE_POST             wait 10D     day 10.00
  step 2   LIKE_POST             wait 10D     day 20.00
  step 3   LIKE_POST             wait 10D     day 30.00
  step 4   LIKE_POST             wait 10D     day 40.00
  step 5   LIKE_POST             wait 10D     day 50.00
  step 6   LIKE_POST             wait 10D     day 60.00
  step 7   LIKE_POST             wait 10D     day 70.00
  step 8   LIKE_POST             wait 10D     day 80.00
  step 9   LIKE_POST             wait 10D     day 90.00
  step 10  LIKE_POST             wait 10D     day 100.00
  step 11  LIKE_POST             wait 10D     day 110.00
  step 12  LIKE_POST             wait 40D     day 150.00
  step 13  LIKE_POST             wait 40D     day 190.00
  step 14  END                   wait 1D      day 191.00
```

**Connection note:** 1 `CONNECTION_REQUEST` note slot(s), every one of them EMPTY — this campaign sends connection requests with no note.


### 470037 — Warmup 3

- ownership: **unknown** — not in the ledger and not on any operator-declared internal list; UNKNOWN is the state, not a gap
- provider status `PAUSED`; created `2026-06-15T13:35:32.467997Z`; started `2026-06-15T13:39:27.078937Z`
- seats (`campaignAccountIds`): 208253, 181658, 174810, 208242, 181653, 201959
- lead list `730071` (Productive employees warmup), list size `totalItemsCount` = 178; campaign holds `progressStats.totalUsers` = 178, finished 1
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **134**, accepted **75** (55.97%)
  - messages sent **0**, message threads started **0**, replies **1** (n/a (denominator 0) of threads started)
  - unique leads contacted **134**; profile views 0, follows 0, post likes 221
  - provider's own tags: `autoTaggedInterested` **0**, `totalAutoTagged` **1**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 1 conversations joined, 0 operator-positive replies = **0.000 per 100 requests sent**
- reply classes in this campaign: `unknown` 2
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-06-16 .. 2026-07-15 (13 days)
- sequence node types present in the whole graph: CONNECTION_REQUEST, END, LIKE_POST
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CONNECTION_REQUEST    wait 0H      day  0.00
  step 1   LIKE_POST             wait 10D     day 10.00
  step 2   LIKE_POST             wait 10D     day 20.00
  step 3   LIKE_POST             wait 10D     day 30.00
  step 4   LIKE_POST             wait 10D     day 40.00
  step 5   LIKE_POST             wait 10D     day 50.00
  step 6   LIKE_POST             wait 10D     day 60.00
  step 7   LIKE_POST             wait 10D     day 70.00
  step 8   LIKE_POST             wait 10D     day 80.00
  step 9   LIKE_POST             wait 10D     day 90.00
  step 10  LIKE_POST             wait 10D     day 100.00
  step 11  LIKE_POST             wait 10D     day 110.00
  step 12  LIKE_POST             wait 40D     day 150.00
  step 13  LIKE_POST             wait 40D     day 190.00
  step 14  END                   wait 1D      day 191.00
```

**Connection note:** 1 `CONNECTION_REQUEST` note slot(s), every one of them EMPTY — this campaign sends connection requests with no note.


### 470038 — Warmup 4

- ownership: **unknown** — not in the ledger and not on any operator-declared internal list; UNKNOWN is the state, not a gap
- provider status `PAUSED`; created `2026-06-15T13:35:43.212444Z`; started `2026-06-15T13:40:50.747477Z`
- seats (`campaignAccountIds`): 186618, 139699, 129082, 125775, 125748
- lead list `730071` (Productive employees warmup), list size `totalItemsCount` = 178; campaign holds `progressStats.totalUsers` = 178, finished 0
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **157**, accepted **88** (56.05%)
  - messages sent **0**, message threads started **0**, replies **0** (n/a (denominator 0) of threads started)
  - unique leads contacted **157**; profile views 0, follows 0, post likes 308
  - provider's own tags: `autoTaggedInterested` **0**, `totalAutoTagged` **0**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 0 conversations joined, 0 operator-positive replies = **0.000 per 100 requests sent**
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-06-15 .. 2026-07-06 (8 days)
- sequence node types present in the whole graph: CONNECTION_REQUEST, END, LIKE_POST
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CONNECTION_REQUEST    wait 0H      day  0.00
  step 1   LIKE_POST             wait 10D     day 10.00
  step 2   LIKE_POST             wait 10D     day 20.00
  step 3   LIKE_POST             wait 10D     day 30.00
  step 4   LIKE_POST             wait 10D     day 40.00
  step 5   LIKE_POST             wait 10D     day 50.00
  step 6   LIKE_POST             wait 10D     day 60.00
  step 7   LIKE_POST             wait 10D     day 70.00
  step 8   LIKE_POST             wait 10D     day 80.00
  step 9   LIKE_POST             wait 10D     day 90.00
  step 10  LIKE_POST             wait 10D     day 100.00
  step 11  LIKE_POST             wait 10D     day 110.00
  step 12  LIKE_POST             wait 40D     day 150.00
  step 13  LIKE_POST             wait 40D     day 190.00
  step 14  END                   wait 1D      day 191.00
```

**Connection note:** 1 `CONNECTION_REQUEST` note slot(s), every one of them EMPTY — this campaign sends connection requests with no note.


### 470039 — Warmup 5

- ownership: **unknown** — not in the ledger and not on any operator-declared internal list; UNKNOWN is the state, not a gap
- provider status `PAUSED`; created `2026-06-15T13:35:56.080963Z`; started `2026-06-15T13:41:49.631165Z`
- seats (`campaignAccountIds`): 119588, 116989, 116988, 116973, 116968
- lead list `730071` (Productive employees warmup), list size `totalItemsCount` = 178; campaign holds `progressStats.totalUsers` = 178, finished 0
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **171**, accepted **102** (59.65%)
  - messages sent **0**, message threads started **0**, replies **0** (n/a (denominator 0) of threads started)
  - unique leads contacted **171**; profile views 0, follows 0, post likes 308
  - provider's own tags: `autoTaggedInterested` **0**, `totalAutoTagged` **0**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 0 conversations joined, 0 operator-positive replies = **0.000 per 100 requests sent**
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-06-15 .. 2026-07-17 (8 days)
- sequence node types present in the whole graph: CONNECTION_REQUEST, END, LIKE_POST
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CONNECTION_REQUEST    wait 0H      day  0.00
  step 1   LIKE_POST             wait 10D     day 10.00
  step 2   LIKE_POST             wait 10D     day 20.00
  step 3   LIKE_POST             wait 10D     day 30.00
  step 4   LIKE_POST             wait 10D     day 40.00
  step 5   LIKE_POST             wait 10D     day 50.00
  step 6   LIKE_POST             wait 10D     day 60.00
  step 7   LIKE_POST             wait 10D     day 70.00
  step 8   LIKE_POST             wait 10D     day 80.00
  step 9   LIKE_POST             wait 10D     day 90.00
  step 10  LIKE_POST             wait 10D     day 100.00
  step 11  LIKE_POST             wait 10D     day 110.00
  step 12  LIKE_POST             wait 40D     day 150.00
  step 13  LIKE_POST             wait 40D     day 190.00
  step 14  END                   wait 1D      day 191.00
```

**Connection note:** 1 `CONNECTION_REQUEST` note slot(s), every one of them EMPTY — this campaign sends connection requests with no note.


### 470040 — Warmup 6

- ownership: **unknown** — not in the ledger and not on any operator-declared internal list; UNKNOWN is the state, not a gap
- provider status `PAUSED`; created `2026-06-15T13:36:07.561664Z`; started `2026-06-15T13:42:28.12891Z`
- seats (`campaignAccountIds`): 156360, 169600, 177751
- lead list `730071` (Productive employees warmup), list size `totalItemsCount` = 178; campaign holds `progressStats.totalUsers` = 178, finished 0
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **93**, accepted **56** (60.22%)
  - messages sent **0**, message threads started **0**, replies **0** (n/a (denominator 0) of threads started)
  - unique leads contacted **93**; profile views 0, follows 0, post likes 93
  - provider's own tags: `autoTaggedInterested` **0**, `totalAutoTagged` **0**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 0 conversations joined, 0 operator-positive replies = **0.000 per 100 requests sent**
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-06-17 .. 2026-07-24 (15 days)
- sequence node types present in the whole graph: CONNECTION_REQUEST, END, LIKE_POST
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CONNECTION_REQUEST    wait 0H      day  0.00
  step 1   LIKE_POST             wait 10D     day 10.00
  step 2   LIKE_POST             wait 10D     day 20.00
  step 3   LIKE_POST             wait 10D     day 30.00
  step 4   LIKE_POST             wait 10D     day 40.00
  step 5   LIKE_POST             wait 10D     day 50.00
  step 6   LIKE_POST             wait 10D     day 60.00
  step 7   LIKE_POST             wait 10D     day 70.00
  step 8   LIKE_POST             wait 10D     day 80.00
  step 9   LIKE_POST             wait 10D     day 90.00
  step 10  LIKE_POST             wait 10D     day 100.00
  step 11  LIKE_POST             wait 10D     day 110.00
  step 12  LIKE_POST             wait 40D     day 150.00
  step 13  LIKE_POST             wait 40D     day 190.00
  step 14  END                   wait 1D      day 191.00
```

**Connection note:** 1 `CONNECTION_REQUEST` note slot(s), every one of them EMPTY — this campaign sends connection requests with no note.


### 473854 — OMEGA 3

- ownership: **unknown** — not in the ledger and not on any operator-declared internal list; UNKNOWN is the state, not a gap
- provider status `PAUSED`; created `2026-06-17T13:43:11.724284Z`; started `2026-06-17T13:44:48.82173Z`
- seats (`campaignAccountIds`): 129531, 181262, 212356, 143105, 116973, 116968, 156360, 169600, 177751, 116988, 119588, 125748, 125775, 129082, 139699, 186618, 201959, 181653, 181658, 194061, 191848, 179527, 201978, 175552, 159259
- lead list `668409` (PRODUCTIVE - OMEGA), list size `totalItemsCount` = 33710; campaign holds `progressStats.totalUsers` = 33710, finished 348
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **3808**, accepted **472** (12.39%)
  - messages sent **710**, message threads started **452**, replies **53** (11.73% of threads started)
  - unique leads contacted **3816**; profile views 7457, follows 0, post likes 1209
  - provider's own tags: `autoTaggedInterested` **7**, `totalAutoTagged` **53**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 457 conversations joined, 4 operator-positive replies = **0.105 per 100 requests sent**
- reply classes in this campaign: `unknown` 44, `negative` 12, `not_relevant` 4, `positive` 3, `automated` 2, `out_of_office` 2, `objection` 2, `question` 1
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-06-18 .. 2026-09-24 (49 days)
- sequence node types present in the whole graph: CONNECTION_REQUEST, END, LIKE_POST, MESSAGE, SEND_LEAD_TO_BISON, VIEW_PROFILE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   VIEW_PROFILE          wait 0H      day  0.00
  step 1   CONNECTION_REQUEST    wait 1D      day  1.00
  step 2   MESSAGE               wait 3H      day  1.12
  step 3   VIEW_PROFILE          wait 3D      day  4.12
  step 4   LIKE_POST             wait 2D      day  6.12
  step 5   SEND_LEAD_TO_BISON    wait 1D      day  7.12
  step 6   MESSAGE               wait 0H      day  7.12
  step 7   LIKE_POST             wait 5D      day 12.12
  step 8   MESSAGE               wait 1D      day 13.12
  step 9   LIKE_POST             wait 1D      day 14.12
  step 10  END                   wait 1D      day 15.12
```

**Connection note:** 1 `CONNECTION_REQUEST` note slot(s), every one of them EMPTY — this campaign sends connection requests with no note.

**Message steps — our text, in full:**

- message at day 1.12, 17 variant(s):
  - variant 1 (149 chars, 21 words): `hey {FIRST_NAME}, how does {COMPANY} currently track project profitability, is it all spreadsheets or do you have something in place? {MY_FIRST_NAME}`
  - variant 2 (181 chars, 33 words): `{FIRST_NAME} quick one, do you guys have resource planning sorted out at {COMPANY} or is that still a bit of a mess? asking cause i work with few {INDUSTRY} agencies on exactly that`
  - variant 3 (173 chars, 27 words): `hey {FIRST_NAME}! saw you're {POSITION} at {COMPANY}, curious how you handle billing and invoicing across projects, is it all manual or do you have a system? {MY_FIRST_NAME}`
  - variant 4 (429 chars, 68 words): `Hi {FIRST_NAME}, thanks for connecting. I'm a sales rep at Productive, where we help agencies run projects, resourcing and finances in one platform. 

If at {COMPANY} you're losing billable hours to manual timesheets, can't see project profitability in real time, or you're juggling separate tools for PM, time tracking and invoicing, we could be a real help. 

How are you handling that side of things right now? {MY_FIRST_NAME}`
  - variant 5 (364 chars, 59 words): `Hi {FIRST_NAME}, good to connect. Quick context, I'm a sales rep at Productive. 

How are you managing agency ops at {COMPANY} right now, solid system or still stitching things together? 

I ask because if you're stuck with gut feel forecasting, no live view of margin per project, or three to five disconnected tools, that's exactly what we fix. 

{MY_FIRST_NAME}`
  - variant 6 (276 chars, 44 words): `Hi {FIRST_NAME}, thanks for the add. I'm a sales rep at Productive. If at {COMPANY} you're battling lost billable hours, no real time profitability, and too many disconnected tools, we bring all of it into one platform. 

How's your current setup holding up? 

{MY_FIRST_NAME}`
  - variant 7 (401 chars, 69 words): `Hi {FIRST_NAME}, glad to be connected. I work in sales at Productive, helping agencies pull ops into one place. 

A lot of teams I speak to are stitching together separate tools, can't tell if a project is profitable until after invoicing, and lose hours to manual time tracking. 

If any of that sounds like {COMPANY}, I'd love to help. 

How are things running for you at the moment? {MY_FIRST_NAME}`
  - variant 8 (372 chars, 59 words): `Hi {FIRST_NAME}, thanks for connecting. I'm a sales rep at Productive. 

We help agency leaders who can't see margin while a project is still live, who lose billable time to manual timesheets, and who run resourcing across too many tools. If that's a fair picture of {COMPANY}, we could genuinely help. 

How are you tracking project profitability today? 

{MY_FIRST_NAME}`
  - variant 9 (328 chars, 52 words): `Hi {FIRST_NAME}, good to connect. I'm in sales at Productive. If at {COMPANY} you can't see team availability across projects in real time, you're forecasting on gut feel, and finance lives in a separate tool from delivery, that gap is exactly what we close. 

Curious how you're managing resourcing right now? 

{MY_FIRST_NAME}`
  - variant 10 (363 chars, 60 words): `Hi {FIRST_NAME}, thanks for the connection. I'm a sales rep at Productive. 

Most agencies we work with were running four or five tools for PM, time, budgets and invoicing, couldn't get a clean profitability number, and were losing billable hours in the gaps. 

We pull all of it into one platform. Is that close to how {COMPANY} operates today? 

{MY_FIRST_NAME}`
  - variant 11 (413 chars, 67 words): `Hi {FIRST_NAME}, appreciate the connect. I'm a sales rep at Productive and spend most of my time with agency ops people. 

The recurring pattern I hear is no live view of margin, billable hours slipping through manual timesheets, and resourcing scattered across separate tools. 

If that rings true for {COMPANY}, happy to share what's worked for similar teams. How are you set up at the moment? 

{MY_FIRST_NAME}`
  - variant 12 (262 chars, 42 words): `Hi {FIRST_NAME}, thanks for the add. Sales rep at Productive here. 

Disconnected tools, no real time profitability, billable hours going missing, if any of those are live issues at {COMPANY}, we can help. 

How are you managing it all right now? {MY_FIRST_NAME}`
  - variant 13 (559 chars, 89 words): `Hi {FIRST_NAME}, thanks for connecting.

I'm a sales rep at Productive, the platform that brings project management, resourcing, time tracking, budgets and invoicing into one place for agencies.

We mostly help agency and consultancy teams who lose billable hours to manual timesheets, can't see project profitability in real time, and are juggling four or five disconnected tools.

If any of that sounds like {COMPANY}, one brief call and we'll set your whole team up with a free premium trial.

How are you managing ops over there right now? {MY_FIRST_NAME}`
  - variant 14 (543 chars, 92 words): `Hi {FIRST_NAME}, good to connect.

Quick context, I'm a sales rep at Productive. We pull projects, resourcing and finances into a single platform built for agencies.

The teams we help usually have the same three headaches: gut feel forecasting, no live view of margin per project, and too many tools that don't talk to each other.

If that rings true for {COMPANY}, give me one short call and I'll get your whole team a free premium trial.

How are you handling all that today, solid system or still stitching things together? {MY_FIRST_NAME}`
  - variant 15 (526 chars, 86 words): `Hi {FIRST_NAME}, glad to be connected.

I work in sales at Productive and spend most of my time with agency ops people. We bring PM, time tracking, budgets and invoicing under one roof.

The pattern I keep hearing is billable hours slipping through manual timesheets, profitability you only see after the invoice goes out, and resourcing spread across separate tools.

If that's the picture at {COMPANY}, one brief call and your team gets a free premium trial, no strings.

How's your current setup holding up? {MY_FIRST_NAME}`
  - variant 16 (550 chars, 90 words): `Hi {FIRST_NAME}, thanks for the add.

I'm a sales rep at Productive, where we help agencies see project profitability while work is still live, not weeks after invoicing. Everything sits in one platform: projects, resourcing, time, budgets and billing.

Most leaders we speak to are stuck with no real time margin view, billable hours lost to manual tracking, and a stack of tools that don't connect.

If that's true for {COMPANY}, a quick call gets your whole team a free premium trial.

How are you tracking profitability right now? {MY_FIRST_NAME}`
  - variant 17 (522 chars, 87 words): `Hi {FIRST_NAME}, appreciate the connection.

I'm in sales at Productive. We replace the usual pile of agency tools with one platform that ties projects, resourcing, budgets and invoicing together.

Teams come to us when they're running four or five tools that don't sync, can't get a clean profitability number, and keep losing billable hours in the gaps.

If that sounds familiar at {COMPANY}, one short call and I'll set the whole team up on a free premium trial.

Is that close to how you operate today? {MY_FIRST_NAME}`
  - fallback (539 chars): `Hi, thanks for connecting.

I'm a sales rep at Productive, the platform that brings project management, resourcing, time tracking, budgets and invoicing into one place for agencies.

We mostly help teams who lose billable hours to manual timesheets, can't see project profitability in real time, and are juggling four or five disconnected tools.

If any of that sounds familiar, one brief call and we'll set your whole team up with a free premium trial.

How are you managing ops right now, solid system or still stitching things together?`
- message at day 7.12, 9 variant(s):
  - variant 1 (344 chars, 59 words): `Hi {FIRST_NAME}, just floating this back to the top of your inbox.

No worries if the timing's off, but if billable hours slipping away, no live profitability, or too many disconnected tools is a real thing at {COMPANY}, the offer still stands.

One brief call and your whole team gets a free premium trial.

Worth a quick chat? {MY_FIRST_NAME}`
  - variant 2 (326 chars, 58 words): `Hi {FIRST_NAME}, one quick question and I'll leave it there.

When someone at {COMPANY} needs to know if a project is actually profitable, how long does that take to pull together?

If the answer is longer than you'd like, that's exactly what we fix. One call and your team gets a free premium trial to see it. {MY_FIRST_NAME}`
  - variant 3 (350 chars, 59 words): `Hi {FIRST_NAME}, circling back with something concrete.

Hike One came to us with the same mess most agencies have, disconnected tools and no real time margin. They grew billable utilization 10% in their first year with us.

If {COMPANY} is anywhere near that, one brief call and your whole team gets a free premium trial. Open to it? {MY_FIRST_NAME}`
  - variant 4 (332 chars, 61 words): `Hi {FIRST_NAME}, want to make this easy.

The offer is a free premium trial for the entire {COMPANY} team, all I ask for first is one short call so I can set it up around how you actually work.

If lost billable hours, blurry profitability or tool sprawl are on your radar, it's worth the 20 minutes. When suits you? {MY_FIRST_NAME}`
  - variant 5 (341 chars, 59 words): `Hi {FIRST_NAME}, I don't want to keep nudging if it's not relevant.

Should I assume {COMPANY} has profitability, resourcing and billing well in hand, or is the disconnected tools thing still a quiet headache?

If it's the latter, one call gets your team a free premium trial. If not, no problem at all and I'll leave you be. {MY_FIRST_NAME}`
  - variant 6 (373 chars, 64 words): `Hi {FIRST_NAME}, following up with a different angle.

A lot of agency leads I talk to don't have a clean view of who's free across projects, so they overbook some people and lose billable time on others.

If {COMPANY} feels that, we put resourcing, projects and finances in one view. One brief call and your team gets a free premium trial. Worth exploring? {MY_FIRST_NAME}`
  - variant 7 (374 chars, 65 words): `Hi {FIRST_NAME}, quick thought to leave with you.

The expensive part of disconnected tools isn't the subscriptions, it's the billable hours that quietly leak out and the projects you find out were unprofitable too late to fix.

If that's a risk at {COMPANY}, one call and your team gets a free premium trial to see the whole picture in one place. Up for it? {MY_FIRST_NAME}`
  - variant 8 (233 chars, 39 words): `Hi {FIRST_NAME}, still happy to set {COMPANY} up with a free premium trial for the whole team after one short call.

Are lost billable hours, profitability blind spots, or too many tools live issues for you right now? {MY_FIRST_NAME}`
  - variant 9 (343 chars, 55 words): `Hi {FIRST_NAME}, last one from me so I'm not cluttering your inbox.

If the disconnected tools, hidden profitability and lost billable hours stuff ever becomes a priority at {COMPANY}, the door's open and the free team trial offer stands.

Just say the word and we'll grab 20 minutes. Otherwise, genuinely good to be connected. {MY_FIRST_NAME}`
  - fallback (429 chars): `Hi, just following up on my last message.

No worries if the timing's off, but if losing billable hours to manual timesheets, no real time view of project profitability, or juggling too many disconnected tools is a live issue for you, the offer still stands.

One brief call and we'll set your whole team up with a free premium trial.

Are any of those pain points hitting home right now? Happy to grab 20 minutes whenever suits.`
- message at day 13.12, 8 variant(s):
  - variant 1 (165 chars, 28 words): `Hey {FIRST_NAME}, still relevant?

Free premium trial for the {COMPANY} team is on the table, just need one quick call to set it up.

Lmk either way. {MY_FIRST_NAME}`
  - variant 2 (195 chars, 32 words): `Hey {FIRST_NAME}, quick one.

Is the projects, profitability and tools thing still worth solving at {COMPANY}, or have you got it covered?

Yes, no, or not now all work. Just lmk. {MY_FIRST_NAME}`
  - variant 3 (228 chars, 38 words): `Hey {FIRST_NAME}, still on your radar?

If ops and profitability isn't your area, totally fine, just point me to whoever owns it at {COMPANY} and I'll take it from there.

Free team trial offer stands either way. {MY_FIRST_NAME}`
  - variant 4 (189 chars, 33 words): `Hey {FIRST_NAME}, still relevant or just bad timing?

If now's not it, tell me when to circle back and I'll get out of your inbox.

The free team trial isn't going anywhere. {MY_FIRST_NAME}`
  - variant 5 (198 chars, 30 words): `Hey {FIRST_NAME}, still relevant?

Simple test: can you see right now whether your live projects at {COMPANY} are profitable?

If not, that's the call. Free team trial included. Lmk. {MY_FIRST_NAME}`
  - variant 6 (222 chars, 35 words): `Hey {FIRST_NAME}, still relevant?

One agency like yours grew billable utilization 10% in a year after ditching the disconnected tools.

Happy to show you how on a quick call, free team trial included. Lmk. {MY_FIRST_NAME}`
  - variant 7 (219 chars, 35 words): `Hey {FIRST_NAME}, chasing you gently here, promise this is friendly not pushy.

Still worth getting {COMPANY} that free team trial, or has the moment passed?

A one word reply saves us both the guessing. {MY_FIRST_NAME}`
  - variant 8 (238 chars, 41 words): `Hey {FIRST_NAME}, I'll take the quiet as a no for now, all good.

If the profitability, resourcing or tool sprawl stuff ever bites at {COMPANY}, the free team trial offer is here whenever.

Just say the word down the line. {MY_FIRST_NAME}`
  - fallback (250 chars): `Hey, still relevant?

Free premium trial for your whole team is on the table, just need one quick call to set it up.

If losing billable hours, no real time profitability, or too many disconnected tools is still a thing, worth a chat. Lmk either way.`

### 523896 — FIXED - PRODUCTIVE - MARKETING AGENCIES - AUSTRALIA - CLEANED - ZVONIMIR v2

- ownership: **unknown** — not in the ledger and not on any operator-declared internal list; UNKNOWN is the state, not a gap
- provider status `IN_PROGRESS`; created `2026-07-27T14:07:19.443555Z`; started `2026-07-28T15:59:12.424748Z`
- seats (`campaignAccountIds`): 174892, 174748, 175455, 174742, 174332, 174822, 174803, 174797, 174845, 208242
- lead list `605364` (PRODUCTIVE - AUSTRALIA - ICP - FILTERED OUT OF 200K LEADS), list size `totalItemsCount` = 5133; campaign holds `progressStats.totalUsers` = 5133, finished 24
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **465**, accepted **27** (5.81%)
  - messages sent **110**, message threads started **27**, replies **5** (18.52% of threads started)
  - unique leads contacted **465**; profile views 898, follows 0, post likes 0
  - provider's own tags: `autoTaggedInterested` **3**, `totalAutoTagged` **5**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 27 conversations joined, 3 operator-positive replies = **0.645 per 100 requests sent**
- reply classes in this campaign: `positive` 3, `negative` 1, `unknown` 1
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-07-28 .. 2026-10-02 (46 days)
- sequence node types present in the whole graph: CONNECTION_REQUEST, END, INMAIL, MESSAGE, VIEW_PROFILE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CONNECTION_REQUEST    wait 0H      day  0.00
  step 1   MESSAGE               wait 3D      day  3.00
  step 2   MESSAGE               wait 3D      day  6.00
  step 3   MESSAGE               wait 8D      day 14.00
  step 4   MESSAGE               wait 3D      day 17.00
  step 5   MESSAGE               wait 5D      day 22.00
  step 6   END                   wait 1D      day 23.00
```

**Connection note — our text, in full (3 variant(s)):**

1. (164 chars, 22 words) `Hi {FIRST_NAME}, came across {COMPANY} while exploring {INDUSTRY} businesses in {LOCATION}. Would love to connect and follow what you are building.

{MY_FIRST_NAME}`
2. (173 chars, 26 words) `Hi {FIRST_NAME}, saw {COMPANY} pop up while looking at {INDUSTRY} agencies in {LOCATION}. Looks like interesting work, would love to have you in my network.

{MY_FIRST_NAME}`
3. (173 chars, 23 words) `Hi {FIRST_NAME}, found {COMPANY} while browsing {INDUSTRY} businesses in {LOCATION}. Always good to connect with people doing interesting work in the space.

{MY_FIRST_NAME}`

**Message steps — our text, in full:**

- message at day 3.00, 3 variant(s):
  - variant 1 (510 chars, 80 words): `Hi {FIRST_NAME}, appreciate the add.

I help {INDUSTRY} agencies in {LOCATION} replace the usual pile of disconnected tools with one platform that ties together projects, time tracking, budgets and invoicing. The idea being that a {POSITION} can actually see whether a project is profitable while it is still running rather than finding out after the invoice goes out.

Thought {COMPANY} might be worth a conversation at some point. No pressure on that though, good to be connected either way.

{MY_FIRST_NAME}`
  - variant 2 (374 chars, 60 words): `Hey {FIRST_NAME}, thanks for connecting.

I work with {INDUSTRY} agencies on the ops side, specifically helping teams get a real time view of project profitability and utilization without juggling five different tools to do it. Given what you are doing at {COMPANY} I thought it could be relevant at some point.

Happy to share more whenever it makes sense.

{MY_FIRST_NAME}`
  - variant 3 (376 chars, 65 words): `Hi {FIRST_NAME}, good to be connected.

I spend most of my time working with {INDUSTRY} agencies on the gap between time logged and money made. Most {POSITION}s I speak with know something is leaking but cannot pinpoint where until it is too late to fix it.

Thought {COMPANY} might find it useful to see how other teams are solving that. No rush on anything.

{MY_FIRST_NAME}`
  - fallback (322 chars): `Hi, appreciate the add.

I work with agencies on the ops and profitability side, specifically helping teams replace their disconnected tool stack with one platform that ties together projects, time tracking, budgets and invoicing.

Happy to share more if it is ever relevant to your setup. Good to be connected either way.`
- message at day 6.00, 3 variant(s):
  - variant 1 (310 chars, 54 words): `Hey {FIRST_NAME}, quick question for you.

What does {COMPANY} currently use to track project profitability in real time? Not after the work is done, I mean while a project is still live.

Asking because the answer tells me a lot about whether what I do would actually be useful to you or not.

{MY_FIRST_NAME}`
  - variant 2 (323 chars, 56 words): `Hey {FIRST_NAME}, wanted to ask you something directly.

How does {COMPANY} know if a project is going to hit its margin before it is finished? Is that something you can see at any point or does it only become clear after the fact?

Genuinely curious because the answer changes what I would share with you.

{MY_FIRST_NAME}`
  - variant 3 (276 chars, 49 words): `Hey {FIRST_NAME}, just a quick one.

When a project at {COMPANY} goes over budget who is the first person to find out and how do they find out?

Asking because that gap between when something goes wrong and when someone catches it is exactly what I help with.

{MY_FIRST_NAME}`
  - fallback (251 chars): `Hey, quick question.

How does your team currently track whether a project is going to hit its margin before it wraps up?

Not looking to pitch anything, I just find the answer changes a lot about whether what I do is even relevant. Genuinely curious.`
- message at day 14.00, 3 variant(s):
  - variant 1 (577 chars, 99 words): `Hey {FIRST_NAME}, wanted to share what I actually work with in case it is relevant.

The tool is called Productive. It is built for {INDUSTRY} agencies and brings project management, time tracking, budgets and invoicing into one place so the data connects automatically. Most {POSITION}s use it to get a clear picture of utilization and margin without pulling numbers from four different tools every time someone asks how a project is tracking.

{COMPANY} came to mind as a good fit. Would you be open to a 15 minute call to see how it maps to how you operate?

{MY_FIRST_NAME}`
  - variant 2 (467 chars, 75 words): `Hey {FIRST_NAME}, sharing this because I think it is actually relevant to {COMPANY}.

The platform is called Productive and it was built specifically for {INDUSTRY} businesses. It replaces the need to run separate tools for project management, time, budgets and invoicing by connecting all of it in one place. A {POSITION} can see live margin and utilization without anyone building a manual report.

Worth 15 minutes if you want to see it in action?

{MY_FIRST_NAME}`
  - variant 3 (475 chars, 76 words): `Hey {FIRST_NAME}, I should have mentioned this earlier.

The product I work with is Productive. It is an agency management platform that connects time tracking to budgets to invoicing so the financial picture updates automatically as work happens. Teams in {LOCATION} use it to replace Harvest, Asana and whatever spreadsheet is doing the reporting work right now.

Happy to walk you through how it works for a business like {COMPANY} if you have 15 minutes.

{MY_FIRST_NAME}`
  - fallback (442 chars): `Hey, wanted to share what I actually work with.

The tool is called Productive. It is an agency management platform that connects project management, time tracking, budgets and invoicing in one place so the data updates automatically rather than sitting in separate tools. Most agency owners and ops leads use it to get a live view of margin and utilization without manual reporting.

Worth a 15-minute call if you want to see how it works?

`
- message at day 17.00, 3 variant(s):
  - variant 1 (536 chars, 90 words): `Hey {FIRST_NAME}, one more thought and then I will leave it with you.

Most {INDUSTRY} agencies in {LOCATION} that switch to Productive end up replacing Harvest or Toggl for time, Monday or Asana for projects and whatever spreadsheet was doing the budget reporting. The reason it sticks is that the data finally connects rather than sitting in separate tools that someone at {COMPANY} has to reconcile by hand.

If that sounds familiar I am happy to send over a short walkthrough instead of a call if that feels easier.

{MY_FIRST_NAME}`
  - variant 2 (455 chars, 77 words): `Hey {FIRST_NAME}, circling back one more time.

The agencies in {LOCATION} that get the most out of Productive are usually running exactly the kind of setup {COMPANY} is likely running right now. Multiple tools that work fine on their own but do not talk to each other, so a {POSITION} ends up doing the connecting manually.

Productive removes that entirely. Happy to show you a quick walkthrough if a call feels like too much right now.

{MY_FIRST_NAME}`
  - variant 3 (467 chars, 85 words): `Hey {FIRST_NAME}, wanted to try a different angle.

The question I get most from {POSITION}s before they see Productive is something like how long does it take you to answer whether we made money on that project? At most agencies it takes a day or two of pulling data together. In Productive the answer is on screen in real time.

If that gap sounds familiar at {COMPANY} it is worth seeing. I can send a walkthrough if a call does not fit right now.

{MY_FIRST_NAME}`
  - fallback (444 chars): `Hey, one more thought before I leave it with you.

Most agencies that switch to Productive end up replacing Harvest or Toggl for time, Monday or Asana for projects and whatever spreadsheet was doing the budget reporting. The reason it sticks is that the data finally connects rather than sitting in separate tools someone has to reconcile by hand.

Happy to send a short walkthrough if you want to see how it works without committing to a call.`
- message at day 22.00, 4 variant(s):
  - variant 1 (431 chars, 75 words): `Hey {FIRST_NAME}, last message from me on this.

If the timing is off or it is just not relevant to where {COMPANY} is right now that is completely fine. I would rather know than keep nudging you.

If things change and getting a cleaner view of profitability and utilisation ever becomes a priority, Productive has a free 14 day trial at productive.io and you can explore it without having to talk to anyone first.

{MY_FIRST_NAME}`
  - variant 2 (385 chars, 66 words): `Hey {FIRST_NAME}, I have sent a few messages without hearing back so I will leave it here.

No hard feelings at all, timing is everything with this kind of thing. If {COMPANY} ever gets to a point where the tool stack becomes a real headache or you want better visibility into project margins, Productive is worth a look. Free trial at productive.io, no call required.

{MY_FIRST_NAME}`
  - variant 3 (385 chars, 66 words): `Hey {FIRST_NAME}, I have sent a few messages without hearing back so I will leave it here.

No hard feelings at all, timing is everything with this kind of thing. If {COMPANY} ever gets to a point where the tool stack becomes a real headache or you want better visibility into project margins, Productive is worth a look. Free trial at productive.io, no call required.

{MY_FIRST_NAME}`
  - variant 4 (357 chars, 62 words): `Hey {FIRST_NAME}, wrapping up my end of this.

I know these messages land at all kinds of bad times so no offence taken. If the problem I have been describing ever becomes urgent at {COMPANY} you can start a free trial of Productive at productive.io without talking to anyone. Wanted to make sure you had that before I stopped reaching out.

{MY_FIRST_NAME}`
  - fallback (306 chars): `Hey, last message from me on this.

No hard feelings if the timing has not been right. If things ever change and you want a cleaner way to track project profitability and team utilization, Productive is worth a look. Free 14 day trial at productive.io and you do not need to speak to anyone to get started.`

### 523913 — FIXED - PRODUCTIVE - MARKETING AGENCIES - EUROPE - CLEANED - ZVONIMIR

- ownership: **unknown** — not in the ledger and not on any operator-declared internal list; UNKNOWN is the state, not a gap
- provider status `IN_PROGRESS`; created `2026-07-27T14:16:19.543595Z`; started `2026-07-28T15:58:07.499786Z`
- seats (`campaignAccountIds`): 174748, 175455, 174742, 174332, 174822, 174803, 174797, 174845, 208242, 174892
- lead list `605361` (PRODUCTIVE - EUROPE - ICP - FILTERED OUT OF 200K LEADS), list size `totalItemsCount` = 44157; campaign holds `progressStats.totalUsers` = 44157, finished 14
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **244**, accepted **21** (8.61%)
  - messages sent **61**, message threads started **19**, replies **2** (10.53% of threads started)
  - InMail: started **1**, replies **0** (0.00%). `inmailMessagesSent` is **0** here and on every campaign on this seat — the InMail volume lives in `totalInmailStarted`, so a reader asking `inmailMessagesSent` sees zero.
  - unique leads contacted **244**; profile views 462, follows 0, post likes 0
  - provider's own tags: `autoTaggedInterested` **0**, `totalAutoTagged` **2**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 19 conversations joined, 0 operator-positive replies = **0.000 per 100 requests sent**
- reply classes in this campaign: `unknown` 3
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-07-28 .. 2026-10-03 (44 days)
- sequence node types present in the whole graph: CONNECTION_REQUEST, END, INMAIL, MESSAGE, VIEW_PROFILE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CONNECTION_REQUEST    wait 0H      day  0.00
  step 1   MESSAGE               wait 3D      day  3.00
  step 2   MESSAGE               wait 3D      day  6.00
  step 3   MESSAGE               wait 9D      day 15.00
  step 4   MESSAGE               wait 7D      day 22.00
  step 5   MESSAGE               wait 3D      day 25.00
  step 6   END                   wait 1D      day 26.00
```

**Connection note:** 1 `CONNECTION_REQUEST` note slot(s), every one of them EMPTY — this campaign sends connection requests with no note.

**Message steps — our text, in full:**

- message at day 3.00, 1 variant(s):
  - variant 1 (510 chars, 80 words): `Hi {FIRST_NAME}, appreciate the add.

I help {INDUSTRY} agencies in {LOCATION} replace the usual pile of disconnected tools with one platform that ties together projects, time tracking, budgets and invoicing. The idea being that a {POSITION} can actually see whether a project is profitable while it is still running rather than finding out after the invoice goes out.

Thought {COMPANY} might be worth a conversation at some point. No pressure on that though, good to be connected either way.

{MY_FIRST_NAME}`
  - fallback (322 chars): `Hi, appreciate the add.

I work with agencies on the ops and profitability side, specifically helping teams replace their disconnected tool stack with one platform that ties together projects, time tracking, budgets and invoicing.

Happy to share more if it is ever relevant to your setup. Good to be connected either way.`
- message at day 6.00, 3 variant(s):
  - variant 1 (310 chars, 54 words): `Hey {FIRST_NAME}, quick question for you.

What does {COMPANY} currently use to track project profitability in real time? Not after the work is done, I mean while a project is still live.

Asking because the answer tells me a lot about whether what I do would actually be useful to you or not.

{MY_FIRST_NAME}`
  - variant 2 (323 chars, 56 words): `Hey {FIRST_NAME}, wanted to ask you something directly.

How does {COMPANY} know if a project is going to hit its margin before it is finished? Is that something you can see at any point or does it only become clear after the fact?

Genuinely curious because the answer changes what I would share with you.

{MY_FIRST_NAME}`
  - variant 3 (276 chars, 49 words): `Hey {FIRST_NAME}, just a quick one.

When a project at {COMPANY} goes over budget who is the first person to find out and how do they find out?

Asking because that gap between when something goes wrong and when someone catches it is exactly what I help with.

{MY_FIRST_NAME}`
  - fallback (251 chars): `Hey, quick question.

How does your team currently track whether a project is going to hit its margin before it wraps up?

Not looking to pitch anything, I just find the answer changes a lot about whether what I do is even relevant. Genuinely curious.`
- message at day 15.00, 3 variant(s):
  - variant 1 (577 chars, 99 words): `Hey {FIRST_NAME}, wanted to share what I actually work with in case it is relevant.

The tool is called Productive. It is built for {INDUSTRY} agencies and brings project management, time tracking, budgets and invoicing into one place so the data connects automatically. Most {POSITION}s use it to get a clear picture of utilization and margin without pulling numbers from four different tools every time someone asks how a project is tracking.

{COMPANY} came to mind as a good fit. Would you be open to a 15 minute call to see how it maps to how you operate?

{MY_FIRST_NAME}`
  - variant 2 (467 chars, 75 words): `Hey {FIRST_NAME}, sharing this because I think it is actually relevant to {COMPANY}.

The platform is called Productive and it was built specifically for {INDUSTRY} businesses. It replaces the need to run separate tools for project management, time, budgets and invoicing by connecting all of it in one place. A {POSITION} can see live margin and utilization without anyone building a manual report.

Worth 15 minutes if you want to see it in action?

{MY_FIRST_NAME}`
  - variant 3 (475 chars, 76 words): `Hey {FIRST_NAME}, I should have mentioned this earlier.

The product I work with is Productive. It is an agency management platform that connects time tracking to budgets to invoicing so the financial picture updates automatically as work happens. Teams in {LOCATION} use it to replace Harvest, Asana and whatever spreadsheet is doing the reporting work right now.

Happy to walk you through how it works for a business like {COMPANY} if you have 15 minutes.

{MY_FIRST_NAME}`
  - fallback (442 chars): `Hey, wanted to share what I actually work with.

The tool is called Productive. It is an agency management platform that connects project management, time tracking, budgets and invoicing in one place so the data updates automatically rather than sitting in separate tools. Most agency owners and ops leads use it to get a live view of margin and utilization without manual reporting.

Worth a 15-minute call if you want to see how it works?

`
- message at day 22.00, 3 variant(s):
  - variant 1 (536 chars, 90 words): `Hey {FIRST_NAME}, one more thought and then I will leave it with you.

Most {INDUSTRY} agencies in {LOCATION} that switch to Productive end up replacing Harvest or Toggl for time, Monday or Asana for projects and whatever spreadsheet was doing the budget reporting. The reason it sticks is that the data finally connects rather than sitting in separate tools that someone at {COMPANY} has to reconcile by hand.

If that sounds familiar I am happy to send over a short walkthrough instead of a call if that feels easier.

{MY_FIRST_NAME}`
  - variant 2 (455 chars, 77 words): `Hey {FIRST_NAME}, circling back one more time.

The agencies in {LOCATION} that get the most out of Productive are usually running exactly the kind of setup {COMPANY} is likely running right now. Multiple tools that work fine on their own but do not talk to each other, so a {POSITION} ends up doing the connecting manually.

Productive removes that entirely. Happy to show you a quick walkthrough if a call feels like too much right now.

{MY_FIRST_NAME}`
  - variant 3 (467 chars, 85 words): `Hey {FIRST_NAME}, wanted to try a different angle.

The question I get most from {POSITION}s before they see Productive is something like how long does it take you to answer whether we made money on that project? At most agencies it takes a day or two of pulling data together. In Productive the answer is on screen in real time.

If that gap sounds familiar at {COMPANY} it is worth seeing. I can send a walkthrough if a call does not fit right now.

{MY_FIRST_NAME}`
  - fallback (444 chars): `Hey, one more thought before I leave it with you.

Most agencies that switch to Productive end up replacing Harvest or Toggl for time, Monday or Asana for projects and whatever spreadsheet was doing the budget reporting. The reason it sticks is that the data finally connects rather than sitting in separate tools someone has to reconcile by hand.

Happy to send a short walkthrough if you want to see how it works without committing to a call.`
- message at day 25.00, 4 variant(s):
  - variant 1 (431 chars, 75 words): `Hey {FIRST_NAME}, last message from me on this.

If the timing is off or it is just not relevant to where {COMPANY} is right now that is completely fine. I would rather know than keep nudging you.

If things change and getting a cleaner view of profitability and utilisation ever becomes a priority, Productive has a free 14 day trial at productive.io and you can explore it without having to talk to anyone first.

{MY_FIRST_NAME}`
  - variant 2 (385 chars, 66 words): `Hey {FIRST_NAME}, I have sent a few messages without hearing back so I will leave it here.

No hard feelings at all, timing is everything with this kind of thing. If {COMPANY} ever gets to a point where the tool stack becomes a real headache or you want better visibility into project margins, Productive is worth a look. Free trial at productive.io, no call required.

{MY_FIRST_NAME}`
  - variant 3 (385 chars, 66 words): `Hey {FIRST_NAME}, I have sent a few messages without hearing back so I will leave it here.

No hard feelings at all, timing is everything with this kind of thing. If {COMPANY} ever gets to a point where the tool stack becomes a real headache or you want better visibility into project margins, Productive is worth a look. Free trial at productive.io, no call required.

{MY_FIRST_NAME}`
  - variant 4 (357 chars, 62 words): `Hey {FIRST_NAME}, wrapping up my end of this.

I know these messages land at all kinds of bad times so no offence taken. If the problem I have been describing ever becomes urgent at {COMPANY} you can start a free trial of Productive at productive.io without talking to anyone. Wanted to make sure you had that before I stopped reaching out.

{MY_FIRST_NAME}`
  - fallback (306 chars): `Hey, last message from me on this.

No hard feelings if the timing has not been right. If things ever change and you want a cleaner way to track project profitability and team utilization, Productive is worth a look. Free 14 day trial at productive.io and you do not need to speak to anyone to get started.`

### 523922 — FIXED - OMEGA 3

- ownership: **unknown** — not in the ledger and not on any operator-declared internal list; UNKNOWN is the state, not a gap
- provider status `IN_PROGRESS`; created `2026-07-27T14:20:12.436879Z`; started `2026-07-28T15:56:15.449852Z`
- seats (`campaignAccountIds`): 212356, 143105, 116973, 116968, 169600, 177751, 116988, 119588, 125748, 125775, 129082, 139699, 201959, 181653, 181658, 191848, 179527, 201978, 175552, 159259, 174892, 174748, 175455, 208253, 174742, 174332, 174810, 174822, 174845, 174803, 208242, 174797, 116989
- lead list `668409` (PRODUCTIVE - OMEGA), list size `totalItemsCount` = 33710; campaign holds `progressStats.totalUsers` = 33710, finished 1454
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **1951**, accepted **48** (2.46%)
  - messages sent **62**, message threads started **35**, replies **5** (14.29% of threads started)
  - unique leads contacted **1945**; profile views 4895, follows 0, post likes 0
  - provider's own tags: `autoTaggedInterested` **0**, `totalAutoTagged` **5**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 35 conversations joined, 1 operator-positive replies = **0.051 per 100 requests sent**
- reply classes in this campaign: `unknown` 4, `negative` 1, `not_relevant` 1, `positive` 1, `objection` 1
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-07-28 .. 2026-10-03 (59 days)
- sequence node types present in the whole graph: CONNECTION_REQUEST, END, MESSAGE, SEND_LEAD_TO_BISON, VIEW_PROFILE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CONNECTION_REQUEST    wait 1D      day  1.00
  step 1   MESSAGE               wait 3H      day  1.12
  step 2   SEND_LEAD_TO_BISON    wait 5D      day  6.12
  step 3   MESSAGE               wait 0H      day  6.12
  step 4   MESSAGE               wait 6D      day 12.12
  step 5   END                   wait 1D      day 13.12
```

**Connection note:** 1 `CONNECTION_REQUEST` note slot(s), every one of them EMPTY — this campaign sends connection requests with no note.

**Message steps — our text, in full:**

- message at day 1.12, 2 variant(s):
  - variant 1 (173 chars, 27 words): `hey {FIRST_NAME}! saw you're {POSITION} at {COMPANY}, curious how you handle billing and invoicing across projects, is it all manual or do you have a system? {MY_FIRST_NAME}`
  - variant 2 (413 chars, 67 words): `Hi {FIRST_NAME}, appreciate the connect. I'm a sales rep at Productive and spend most of my time with agency ops people. 

The recurring pattern I hear is no live view of margin, billable hours slipping through manual timesheets, and resourcing scattered across separate tools. 

If that rings true for {COMPANY}, happy to share what's worked for similar teams. How are you set up at the moment? 

{MY_FIRST_NAME}`
  - fallback (539 chars): `Hi, thanks for connecting.

I'm a sales rep at Productive, the platform that brings project management, resourcing, time tracking, budgets and invoicing into one place for agencies.

We mostly help teams who lose billable hours to manual timesheets, can't see project profitability in real time, and are juggling four or five disconnected tools.

If any of that sounds familiar, one brief call and we'll set your whole team up with a free premium trial.

How are you managing ops right now, solid system or still stitching things together?`
- message at day 6.12, 9 variant(s):
  - variant 1 (344 chars, 59 words): `Hi {FIRST_NAME}, just floating this back to the top of your inbox.

No worries if the timing's off, but if billable hours slipping away, no live profitability, or too many disconnected tools is a real thing at {COMPANY}, the offer still stands.

One brief call and your whole team gets a free premium trial.

Worth a quick chat? {MY_FIRST_NAME}`
  - variant 2 (326 chars, 58 words): `Hi {FIRST_NAME}, one quick question and I'll leave it there.

When someone at {COMPANY} needs to know if a project is actually profitable, how long does that take to pull together?

If the answer is longer than you'd like, that's exactly what we fix. One call and your team gets a free premium trial to see it. {MY_FIRST_NAME}`
  - variant 3 (350 chars, 59 words): `Hi {FIRST_NAME}, circling back with something concrete.

Hike One came to us with the same mess most agencies have, disconnected tools and no real time margin. They grew billable utilization 10% in their first year with us.

If {COMPANY} is anywhere near that, one brief call and your whole team gets a free premium trial. Open to it? {MY_FIRST_NAME}`
  - variant 4 (332 chars, 61 words): `Hi {FIRST_NAME}, want to make this easy.

The offer is a free premium trial for the entire {COMPANY} team, all I ask for first is one short call so I can set it up around how you actually work.

If lost billable hours, blurry profitability or tool sprawl are on your radar, it's worth the 20 minutes. When suits you? {MY_FIRST_NAME}`
  - variant 5 (341 chars, 59 words): `Hi {FIRST_NAME}, I don't want to keep nudging if it's not relevant.

Should I assume {COMPANY} has profitability, resourcing and billing well in hand, or is the disconnected tools thing still a quiet headache?

If it's the latter, one call gets your team a free premium trial. If not, no problem at all and I'll leave you be. {MY_FIRST_NAME}`
  - variant 6 (373 chars, 64 words): `Hi {FIRST_NAME}, following up with a different angle.

A lot of agency leads I talk to don't have a clean view of who's free across projects, so they overbook some people and lose billable time on others.

If {COMPANY} feels that, we put resourcing, projects and finances in one view. One brief call and your team gets a free premium trial. Worth exploring? {MY_FIRST_NAME}`
  - variant 7 (374 chars, 65 words): `Hi {FIRST_NAME}, quick thought to leave with you.

The expensive part of disconnected tools isn't the subscriptions, it's the billable hours that quietly leak out and the projects you find out were unprofitable too late to fix.

If that's a risk at {COMPANY}, one call and your team gets a free premium trial to see the whole picture in one place. Up for it? {MY_FIRST_NAME}`
  - variant 8 (233 chars, 39 words): `Hi {FIRST_NAME}, still happy to set {COMPANY} up with a free premium trial for the whole team after one short call.

Are lost billable hours, profitability blind spots, or too many tools live issues for you right now? {MY_FIRST_NAME}`
  - variant 9 (343 chars, 55 words): `Hi {FIRST_NAME}, last one from me so I'm not cluttering your inbox.

If the disconnected tools, hidden profitability and lost billable hours stuff ever becomes a priority at {COMPANY}, the door's open and the free team trial offer stands.

Just say the word and we'll grab 20 minutes. Otherwise, genuinely good to be connected. {MY_FIRST_NAME}`
  - fallback (429 chars): `Hi, just following up on my last message.

No worries if the timing's off, but if losing billable hours to manual timesheets, no real time view of project profitability, or juggling too many disconnected tools is a live issue for you, the offer still stands.

One brief call and we'll set your whole team up with a free premium trial.

Are any of those pain points hitting home right now? Happy to grab 20 minutes whenever suits.`
- message at day 12.12, 2 variant(s):
  - variant 1 (219 chars, 35 words): `Hey {FIRST_NAME}, chasing you gently here, promise this is friendly not pushy.

Still worth getting {COMPANY} that free team trial, or has the moment passed?

A one word reply saves us both the guessing. {MY_FIRST_NAME}`
  - variant 2 (238 chars, 41 words): `Hey {FIRST_NAME}, I'll take the quiet as a no for now, all good.

If the profitability, resourcing or tool sprawl stuff ever bites at {COMPANY}, the free team trial offer is here whenever.

Just say the word down the line. {MY_FIRST_NAME}`
  - fallback (250 chars): `Hey, still relevant?

Free premium trial for your whole team is on the table, just need one quick call to set it up.

If losing billable hours, no real time profitability, or too many disconnected tools is still a thing, worth a chat. Lmk either way.`

### 523932 — FIXED - OMEGA 3

- ownership: **unknown** — not in the ledger and not on any operator-declared internal list; UNKNOWN is the state, not a gap
- provider status `IN_PROGRESS`; created `2026-07-27T14:21:59.111558Z`; started `2026-07-28T15:54:40.288882Z`
- seats (`campaignAccountIds`): 174892, 174748, 175455, 174742, 174332, 174810, 174822, 174845, 174803, 174797, 208253, 208242, 212356, 143105, 175552, 201978, 179527, 159259, 191848, 181658, 116989, 119588, 125748, 125775, 129082, 139699, 201959, 181653, 116988, 116973, 116968, 169600, 177751
- lead list `668409` (PRODUCTIVE - OMEGA), list size `totalItemsCount` = 33710; campaign holds `progressStats.totalUsers` = 33710, finished 162
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **1129**, accepted **15** (1.33%)
  - messages sent **14**, message threads started **9**, replies **0** (0.00% of threads started)
  - unique leads contacted **1125**; profile views 1989, follows 0, post likes 0
  - provider's own tags: `autoTaggedInterested` **0**, `totalAutoTagged` **0**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 9 conversations joined, 0 operator-positive replies = **0.000 per 100 requests sent**
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-07-28 .. 2026-10-03 (56 days)
- sequence node types present in the whole graph: CONNECTION_REQUEST, END, MESSAGE, SEND_LEAD_TO_BISON, VIEW_PROFILE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CONNECTION_REQUEST    wait 0H      day  0.00
  step 1   MESSAGE               wait 3D      day  3.00
  step 2   SEND_LEAD_TO_BISON    wait 10D     day 13.00
  step 3   MESSAGE               wait 0H      day 13.00
  step 4   MESSAGE               wait 5D      day 18.00
  step 5   END                   wait 1D      day 19.00
```

**Connection note:** 1 `CONNECTION_REQUEST` note slot(s), every one of them EMPTY — this campaign sends connection requests with no note.

**Message steps — our text, in full:**

- message at day 3.00, 20 variant(s):
  - variant 1 (149 chars, 21 words): `hey {FIRST_NAME}, how does {COMPANY} currently track project profitability, is it all spreadsheets or do you have something in place? {MY_FIRST_NAME}`
  - variant 2 (181 chars, 33 words): `{FIRST_NAME} quick one, do you guys have resource planning sorted out at {COMPANY} or is that still a bit of a mess? asking cause i work with few {INDUSTRY} agencies on exactly that`
  - variant 3 (173 chars, 27 words): `hey {FIRST_NAME}! saw you're {POSITION} at {COMPANY}, curious how you handle billing and invoicing across projects, is it all manual or do you have a system? {MY_FIRST_NAME}`
  - variant 4 (185 chars, 29 words): `{FIRST_NAME}, random question but how many tools is {COMPANY} using to manage projects, resources and finances? asking cause most {INDUSTRY} agencies we talk to are juggling way to many`
  - variant 5 (152 chars, 25 words): `hey {FIRST_NAME}, do you guys have visibility on which projects are actually profitable at {COMPANY} or is that something you figure out after the fact?`
  - variant 6 (182 chars, 27 words): `{FIRST_NAME} hi, is resource planning something {COMPANY} has figured out or still a work in progress? we work with {INDUSTRY} agencies on getting that under control, {MY_FIRST_NAME}`
  - variant 7 (167 chars, 27 words): `hey {FIRST_NAME}! as {POSITION} at {COMPANY} curious if you have a single place where projects, budgets and resourcing all live or if its spread across different tools`
  - variant 8 (168 chars, 24 words): `{FIRST_NAME}, how do you guys handle project budgets at {COMPANY}, got that sorted or still piecing it together across spreadsheets and different tools? {MY_FIRST_NAME}`
  - variant 9 (162 chars, 28 words): `hey {FIRST_NAME}, do you have a good handle on utilization across the team at {COMPANY} or is that one of those things thats always a bit unclear? {MY_FIRST_NAME}`
  - variant 10 (156 chars, 25 words): `{FIRST_NAME} quick question, how does {COMPANY} track whether projects are staying on budget, is that something you have sorted or more of a manual process?`
  - variant 11 (176 chars, 28 words): `hey {FIRST_NAME}! saw {COMPANY} and was curious, whats the biggest operational headache for you guys right now, is it resourcing, profitability or just to many tools to manage?`
  - variant 12 (160 chars, 25 words): `{FIRST_NAME}, is invoicing and billing something {COMPANY} has nailed down or still one of those things that takes way more time than it should? {MY_FIRST_NAME}`
  - variant 13 (130 chars, 22 words): `hey {FIRST_NAME}, how do you guys forecast revenue at {COMPANY}, got a solid process or still kinda winging it quarter to quarter?`
  - variant 14 (186 chars, 32 words): `{FIRST_NAME} hi! as {POSITION} at a {INDUSTRY} agency curious if you have clear visibility on team capacity at any given time or if thats always a bit of a guessing game, {MY_FIRST_NAME}`
  - variant 15 (151 chars, 25 words): `hey {FIRST_NAME}, do you guys have project management, resourcing and finances in one place at {COMPANY} or is it spread across like 4 different tools?`
  - variant 16 (151 chars, 28 words): `{FIRST_NAME}, quick one, how does {COMPANY} know if a project is going to hit budget before it's to late to do anything about it? got that figured out?`
  - variant 17 (202 chars, 31 words): `hey {FIRST_NAME}! {MY_FIRST_NAME} here, i work with {INDUSTRY} agencies on operational stuff. curious if {COMPANY} has a handle on project profitability in real time or its more of a retrospective thing`
  - variant 18 (158 chars, 24 words): `{FIRST_NAME} is time tracking something the team at {COMPANY} actually does consistently or is that one of those things thats always a battle? {MY_FIRST_NAME}`
  - variant 19 (174 chars, 30 words): `hey {FIRST_NAME}, saw you're {POSITION} at {COMPANY}. do you have one place where you can see project status, team capacity and finances together or is it all over the place?`
  - variant 20 (148 chars, 23 words): `{FIRST_NAME} hi, how are you guys managing agency ops at {COMPANY} right now, got a solid system or still stitching things together? {MY_FIRST_NAME}`
  - fallback (125 chars): `hey, do you guys have project management, resourcing and finances in one place or is it spread across like 4 different tools?`
- message at day 13.00, 14 variant(s):
  - variant 1 (186 chars, 30 words): `hey {FIRST_NAME}, just bumping this up, agencies like {COMPANY} usually tell us the biggest thing is not knowing project profitability until its too late. is that something you run into?`
  - variant 2 (170 chars, 28 words): `{FIRST_NAME} following up, i know its probably not top of mind but curious, how are you guys currently handling resource planning, got something or still figuring it out?`
  - variant 3 (226 chars, 35 words): `hey {FIRST_NAME}! didn't hear back, no worries. just wanted to add, most {INDUSTRY} agencies we work with were running projects, finances and resourcing across 3-4 tools before consolidating. is that the case at {COMPANY} too?`
  - variant 4 (183 chars, 30 words): `{FIRST_NAME}, just checking in. one thing that comes up a lot with {INDUSTRY} agencies is losing billable hours just cause time tracking is inconsistent. is that a thing at {COMPANY}?`
  - variant 5 (184 chars, 30 words): `hey {FIRST_NAME}, following up on my last message. not trying to be annoying, genuinely curious if operational visibility is something {COMPANY} has sorted or if its still a pain point`
  - variant 6 (212 chars, 32 words): `{FIRST_NAME} hi, just bumping this. agencies usually lose a surprising amount of revenue just from projects going over budget without anyone catching it early. does that ring a bell at {COMPANY}? 
{MY_FIRST_NAME}`
  - variant 7 (179 chars, 31 words): `hey {FIRST_NAME}! quick follow up, do you guys have a way to see team utilization and project finances in one place or is that something you're still working towards at {COMPANY}?`
  - variant 8 (233 chars, 40 words): `{FIRST_NAME}, i know you're probably busy but wanted to follow up. most {POSITION}s we talk to at {INDUSTRY} agencies say the hardest thing is getting a clear picture of whats profitable and whats not. is that fair for {COMPANY} too?`
  - variant 9 (191 chars, 32 words): `hey {FIRST_NAME}, just circling back. not asking for a demo or anything, just curious, is agency ops something that feels under control at {COMPANY} right now or more of an ongoing challenge?`
  - variant 10 (241 chars, 40 words): `{FIRST_NAME} following up, one thing worth mentioning, agencies that get resourcing and project finances in one place usually save a meaningful chunk of time on admin every week. curious if that kind of thing would matter to you at {COMPANY}`
  - variant 11 (174 chars, 30 words): `hey {FIRST_NAME}! bumping this up, is now just a bad time or is operational tooling not really a priority at {COMPANY} right now? either way just let me know, {MY_FIRST_NAME}`
  - variant 12 (222 chars, 37 words): `hey {FIRST_NAME}, circling back quickly. a lot of {INDUSTRY} agencies tell us they only realize a project went sideways after invoicing. does that happen at {COMPANY} or do you have visibility before it gets to that point?`
  - variant 13 (169 chars, 26 words): `{FIRST_NAME}, just checking in, is this landing with the wrong person? happy to connect with whoever handles ops or tooling at {COMPANY} if thats easier, {MY_FIRST_NAME}`
  - variant 14 (202 chars, 34 words): `{FIRST_NAME}, i'll keep this short. is operational visibility something {COMPANY} has a good handle on or is it one of those things that could always be better? worth a quick chat if so, {MY_FIRST_NAME}`
  - fallback (180 chars): `hey, i'll keep this short. is operational visibility something your company has a good handle on or is it one of those things that could always be better? worth a quick chat if so?`
- message at day 18.00, 19 variant(s):
  - variant 1 (37 chars, 5 words): `hey {FIRST_NAME}, still relevant? lmk`
  - variant 2 (37 chars, 5 words): `hey {FIRST_NAME}, still relevant? lmk`
  - variant 3 (122 chars, 20 words): `hey {FIRST_NAME}! is ops and project visibility something {COMPANY} has sorted or still a work in progress, lmk either way`
  - variant 4 (71 chars, 12 words): `{FIRST_NAME}, bad timing or just not relevant? either is fine, just lmk`
  - variant 5 (109 chars, 16 words): `hey {FIRST_NAME}, wdyt, is managing projects and finances in one place something {COMPANY} would find useful?`
  - variant 6 (81 chars, 12 words): `{FIRST_NAME} still open to connecting? lmk and ill keep it short, {MY_FIRST_NAME}`
  - variant 7 (90 chars, 17 words): `hey {FIRST_NAME}! last one from me, wdyt, worth 15 min or not really a priority right now?`
  - variant 8 (96 chars, 17 words): `hey {FIRST_NAME}, no worries if the timings off, just lmk and ill follow up whenever makes sense`
  - variant 9 (147 chars, 20 words): `{FIRST_NAME} wdyt, is operational visibility something {COMPANY} is actively trying to improve or pretty happy with how things are? {MY_FIRST_NAME}`
  - variant 10 (96 chars, 18 words): `hey {FIRST_NAME}! just lmk if this isnt relevant and ill get out of your inbox, no hard feelings`
  - variant 11 (90 chars, 18 words): `{FIRST_NAME}, one last bump. wdyt, is it a yes, a not now or a not for us? {MY_FIRST_NAME}`
  - variant 12 (108 chars, 14 words): `hey {FIRST_NAME}, is project profitability something {COMPANY} tracks well right now, genuinely curious, lmk`
  - variant 13 (86 chars, 17 words): `{FIRST_NAME} hi, wdyt, open to a quick look or not the right time? either works for me`
  - variant 14 (125 chars, 20 words): `hey {FIRST_NAME}! last message i promise. is agency ops a pain point at {COMPANY} or pretty much handled, lmk {MY_FIRST_NAME}`
  - variant 15 (96 chars, 15 words): `{FIRST_NAME}, still think there could be something here for {COMPANY}. wdyt, worth a quick call?`
  - variant 16 (109 chars, 24 words): `hey {FIRST_NAME}, just lmk if you want me to send over some info or if its better i reach out in a few months`
  - variant 17 (123 chars, 21 words): `{FIRST_NAME} last one from me. is this relevant at all for {COMPANY} right now, yes, no or maybe later, lmk {MY_FIRST_NAME}`
  - variant 18 (121 chars, 23 words): `hey {FIRST_NAME}! wdyt, is there a better person at {COMPANY} i should be talking to about this or are you the right one?`
  - variant 19 (140 chars, 23 words): `{FIRST_NAME}, i'll leave it here. if the timing ever feels right for a chat about how {COMPANY} manages agency ops just lmk, {MY_FIRST_NAME}`
  - fallback (60 chars): `one last bump. wdyt, is it a yes, a not now or a not for us?`

### 523938 — FIXED - inmail 

- ownership: **unknown** — not in the ledger and not on any operator-declared internal list; UNKNOWN is the state, not a gap
- provider status `DRAFT`; created `2026-07-27T14:24:08.706335Z`; started `never`
- seats (`campaignAccountIds`): 174892, 174748, 175455, 174742, 174332, 174822, 174845, 174803, 208242, 174797
- lead list `727022` (inmails), list size `totalItemsCount` = 218; campaign holds `progressStats.totalUsers` = 0, finished 0
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **0**, accepted **0** (n/a (denominator 0))
  - messages sent **0**, message threads started **0**, replies **0** (n/a (denominator 0) of threads started)
  - unique leads contacted **0**; profile views 0, follows 0, post likes 0
  - provider's own tags: `autoTaggedInterested` **0**, `totalAutoTagged` **0**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 0 conversations joined, 0 operator-positive replies = **n/a (0 requests sent) per 100 requests sent**
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- sequence node types present in the whole graph: END, FOLLOW, INMAIL, VIEW_PROFILE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   INMAIL                wait 0H      day  0.00
  step 1   VIEW_PROFILE          wait 3H      day  0.12
  step 2   FOLLOW                wait 3H      day  0.25
  step 3   END                   wait 1D      day  1.25
```

**Connection note:** this graph has no `CONNECTION_REQUEST` node, so no note is sent.


### 523983 — FIXED - OMEGA 2

- ownership: **unknown** — not in the ledger and not on any operator-declared internal list; UNKNOWN is the state, not a gap
- provider status `IN_PROGRESS`; created `2026-07-27T14:44:00.913674Z`; started `2026-07-28T15:53:00.451622Z`
- seats (`campaignAccountIds`): 174892, 174748, 175455, 174742, 174332, 174810, 174822, 174845, 174803, 174797, 208253, 208242, 212356, 143105, 175552, 201978, 179527, 159259, 191848, 181658, 181653, 201959, 139699, 129082, 125775, 125748, 119588, 116989, 116988, 116973, 116968, 169600, 177751
- lead list `668409` (PRODUCTIVE - OMEGA), list size `totalItemsCount` = 33710; campaign holds `progressStats.totalUsers` = 33710, finished 1934
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **18053**, accepted **2096** (11.61%)
  - messages sent **3499**, message threads started **1997**, replies **310** (15.52% of threads started)
  - unique leads contacted **18118**; profile views 23270, follows 27154, post likes 0
  - provider's own tags: `autoTaggedInterested` **74**, `totalAutoTagged` **311**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 1994 conversations joined, 43 operator-positive replies = **0.238 per 100 requests sent**
- reply classes in this campaign: `unknown` 229, `negative` 93, `not_relevant` 30, `question` 22, `positive` 21, `automated` 14, `send_info` 5, `unsubscribe` 5, `not_now` 4, `out_of_office` 2, `objection` 2
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-08-02 .. 2026-10-03 (63 days)
- sequence node types present in the whole graph: CONNECTION_REQUEST, END, FOLLOW, MESSAGE, SEND_LEAD_TO_BISON, VIEW_PROFILE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   FOLLOW                wait 10D     day 10.00
  step 1   CONNECTION_REQUEST    wait 5D      day 15.00
  step 2   MESSAGE               wait 2D      day 17.00
  step 3   SEND_LEAD_TO_BISON    wait 3D      day 20.00
  step 4   MESSAGE               wait 0H      day 20.00
  step 5   MESSAGE               wait 6D      day 26.00
  step 6   END                   wait 1D      day 27.00
```

**Connection note:** 1 `CONNECTION_REQUEST` note slot(s), every one of them EMPTY — this campaign sends connection requests with no note.

**Message steps — our text, in full:**

- message at day 17.00, 6 variant(s):
  - variant 1 (147 chars, 24 words): `Hi {FIRST_NAME}, quick follow-up.

We helped a similar {INDUSTRY} team grow billable utilization 10% in a year.

The fit looks real.

Worth 15 min?`
  - variant 2 (124 chars, 22 words): `Hi {FIRST_NAME}, won't keep chasing.

I genuinely think {COMPANY} is a fit.

If I'm wrong, tell me and I'll back off.

Fair?`
  - variant 3 (145 chars, 23 words): `Hi {FIRST_NAME}, following up.

Curious if project profitability visibility is even a priority right now.

Only reaching out because I see a fit.`
  - variant 4 (162 chars, 26 words): `Hi {FIRST_NAME}, circling back.

We get {INDUSTRY} teams off spreadsheets into one place for projects, time, and budgets.

The fit looks genuine.

Open to a chat?`
  - variant 5 (125 chars, 24 words): `Hi {FIRST_NAME}, following up.

I think your team's a strong fit for what we do.

Happy to show you.

Let me know either way.`
  - variant 6 (125 chars, 24 words): `Hi {FIRST_NAME}, following up.

I think your team's a strong fit for what we do.

Happy to show you.

Let me know either way.`
  - fallback (112 chars): `Hi, following up.

I think your team's a strong fit for what we do.

Happy to show you.

Let me know either way.`
- message at day 20.00, 8 variant(s):
  - variant 1 (170 chars, 28 words): `{FIRST_NAME} following up, i know its probably not top of mind but curious, how are you guys currently handling resource planning, got something or still figuring it out?`
  - variant 2 (226 chars, 35 words): `hey {FIRST_NAME}! didn't hear back, no worries. just wanted to add, most {INDUSTRY} agencies we work with were running projects, finances and resourcing across 3-4 tools before consolidating. is that the case at {COMPANY} too?`
  - variant 3 (184 chars, 30 words): `hey {FIRST_NAME}, following up on my last message. not trying to be annoying, genuinely curious if operational visibility is something {COMPANY} has sorted or if its still a pain point`
  - variant 4 (212 chars, 32 words): `{FIRST_NAME} hi, just bumping this. agencies usually lose a surprising amount of revenue just from projects going over budget without anyone catching it early. does that ring a bell at {COMPANY}? 
{MY_FIRST_NAME}`
  - variant 5 (191 chars, 32 words): `hey {FIRST_NAME}, just circling back. not asking for a demo or anything, just curious, is agency ops something that feels under control at {COMPANY} right now or more of an ongoing challenge?`
  - variant 6 (174 chars, 30 words): `hey {FIRST_NAME}! bumping this up, is now just a bad time or is operational tooling not really a priority at {COMPANY} right now? either way just let me know, {MY_FIRST_NAME}`
  - variant 7 (169 chars, 26 words): `{FIRST_NAME}, just checking in, is this landing with the wrong person? happy to connect with whoever handles ops or tooling at {COMPANY} if thats easier, {MY_FIRST_NAME}`
  - variant 8 (202 chars, 34 words): `{FIRST_NAME}, i'll keep this short. is operational visibility something {COMPANY} has a good handle on or is it one of those things that could always be better? worth a quick chat if so, {MY_FIRST_NAME}`
  - fallback (180 chars): `hey, i'll keep this short. is operational visibility something your company has a good handle on or is it one of those things that could always be better? worth a quick chat if so?`
- message at day 26.00, 9 variant(s):
  - variant 1 (37 chars, 5 words): `hey {FIRST_NAME}, still relevant? lmk`
  - variant 2 (122 chars, 20 words): `hey {FIRST_NAME}! is ops and project visibility something {COMPANY} has sorted or still a work in progress, lmk either way`
  - variant 3 (71 chars, 12 words): `{FIRST_NAME}, bad timing or just not relevant? either is fine, just lmk`
  - variant 4 (81 chars, 12 words): `{FIRST_NAME} still open to connecting? lmk and ill keep it short, {MY_FIRST_NAME}`
  - variant 5 (96 chars, 18 words): `hey {FIRST_NAME}! just lmk if this isnt relevant and ill get out of your inbox, no hard feelings`
  - variant 6 (108 chars, 14 words): `hey {FIRST_NAME}, is project profitability something {COMPANY} tracks well right now, genuinely curious, lmk`
  - variant 7 (123 chars, 21 words): `{FIRST_NAME} last one from me. is this relevant at all for {COMPANY} right now, yes, no or maybe later, lmk {MY_FIRST_NAME}`
  - variant 8 (121 chars, 23 words): `hey {FIRST_NAME}! wdyt, is there a better person at {COMPANY} i should be talking to about this or are you the right one?`
  - variant 9 (140 chars, 23 words): `{FIRST_NAME}, i'll leave it here. if the timing ever feels right for a chat about how {COMPANY} manages agency ops just lmk, {MY_FIRST_NAME}`
  - fallback (60 chars): `one last bump. wdyt, is it a yes, a not now or a not for us?`

### 523987 — FIXED - OMEGA 

- ownership: **unknown** — not in the ledger and not on any operator-declared internal list; UNKNOWN is the state, not a gap
- provider status `IN_PROGRESS`; created `2026-07-27T14:45:44.308769Z`; started `2026-07-28T15:50:11.214514Z`
- seats (`campaignAccountIds`): 174892, 174748, 175455, 174742, 174332, 174810, 174822, 174845, 174803, 174797, 208253, 208242, 129531, 212356, 143105, 116973, 116968, 169600, 177751, 116988, 116989, 119588, 125748, 125775, 129082, 139699, 201959, 181653, 181658, 191848, 179527, 201978, 175552, 159259
- lead list `668409` (PRODUCTIVE - OMEGA), list size `totalItemsCount` = 33710; campaign holds `progressStats.totalUsers` = 33710, finished 759
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **1091**, accepted **20** (1.83%)
  - messages sent **16**, message threads started **10**, replies **0** (0.00% of threads started)
  - unique leads contacted **1091**; profile views 2577, follows 0, post likes 0
  - provider's own tags: `autoTaggedInterested` **0**, `totalAutoTagged` **0**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 10 conversations joined, 0 operator-positive replies = **0.000 per 100 requests sent**
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-07-28 .. 2026-10-03 (46 days)
- sequence node types present in the whole graph: CONNECTION_REQUEST, END, MESSAGE, SEND_LEAD_TO_BISON, VIEW_PROFILE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CONNECTION_REQUEST    wait 0H      day  0.00
  step 1   MESSAGE               wait 3H      day  0.12
  step 2   SEND_LEAD_TO_BISON    wait 6D      day  6.12
  step 3   MESSAGE               wait 0H      day  6.12
  step 4   MESSAGE               wait 6D      day 12.12
  step 5   END                   wait 1D      day 13.12
```

**Connection note:** 1 `CONNECTION_REQUEST` note slot(s), every one of them EMPTY — this campaign sends connection requests with no note.

**Message steps — our text, in full:**

- message at day 0.12, 17 variant(s):
  - variant 1 (149 chars, 21 words): `hey {FIRST_NAME}, how does {COMPANY} currently track project profitability, is it all spreadsheets or do you have something in place? {MY_FIRST_NAME}`
  - variant 2 (181 chars, 33 words): `{FIRST_NAME} quick one, do you guys have resource planning sorted out at {COMPANY} or is that still a bit of a mess? asking cause i work with few {INDUSTRY} agencies on exactly that`
  - variant 3 (173 chars, 27 words): `hey {FIRST_NAME}! saw you're {POSITION} at {COMPANY}, curious how you handle billing and invoicing across projects, is it all manual or do you have a system? {MY_FIRST_NAME}`
  - variant 4 (429 chars, 68 words): `Hi {FIRST_NAME}, thanks for connecting. I'm a sales rep at Productive, where we help agencies run projects, resourcing and finances in one platform. 

If at {COMPANY} you're losing billable hours to manual timesheets, can't see project profitability in real time, or you're juggling separate tools for PM, time tracking and invoicing, we could be a real help. 

How are you handling that side of things right now? {MY_FIRST_NAME}`
  - variant 5 (364 chars, 59 words): `Hi {FIRST_NAME}, good to connect. Quick context, I'm a sales rep at Productive. 

How are you managing agency ops at {COMPANY} right now, solid system or still stitching things together? 

I ask because if you're stuck with gut feel forecasting, no live view of margin per project, or three to five disconnected tools, that's exactly what we fix. 

{MY_FIRST_NAME}`
  - variant 6 (276 chars, 44 words): `Hi {FIRST_NAME}, thanks for the add. I'm a sales rep at Productive. If at {COMPANY} you're battling lost billable hours, no real time profitability, and too many disconnected tools, we bring all of it into one platform. 

How's your current setup holding up? 

{MY_FIRST_NAME}`
  - variant 7 (401 chars, 69 words): `Hi {FIRST_NAME}, glad to be connected. I work in sales at Productive, helping agencies pull ops into one place. 

A lot of teams I speak to are stitching together separate tools, can't tell if a project is profitable until after invoicing, and lose hours to manual time tracking. 

If any of that sounds like {COMPANY}, I'd love to help. 

How are things running for you at the moment? {MY_FIRST_NAME}`
  - variant 8 (372 chars, 59 words): `Hi {FIRST_NAME}, thanks for connecting. I'm a sales rep at Productive. 

We help agency leaders who can't see margin while a project is still live, who lose billable time to manual timesheets, and who run resourcing across too many tools. If that's a fair picture of {COMPANY}, we could genuinely help. 

How are you tracking project profitability today? 

{MY_FIRST_NAME}`
  - variant 9 (328 chars, 52 words): `Hi {FIRST_NAME}, good to connect. I'm in sales at Productive. If at {COMPANY} you can't see team availability across projects in real time, you're forecasting on gut feel, and finance lives in a separate tool from delivery, that gap is exactly what we close. 

Curious how you're managing resourcing right now? 

{MY_FIRST_NAME}`
  - variant 10 (363 chars, 60 words): `Hi {FIRST_NAME}, thanks for the connection. I'm a sales rep at Productive. 

Most agencies we work with were running four or five tools for PM, time, budgets and invoicing, couldn't get a clean profitability number, and were losing billable hours in the gaps. 

We pull all of it into one platform. Is that close to how {COMPANY} operates today? 

{MY_FIRST_NAME}`
  - variant 11 (413 chars, 67 words): `Hi {FIRST_NAME}, appreciate the connect. I'm a sales rep at Productive and spend most of my time with agency ops people. 

The recurring pattern I hear is no live view of margin, billable hours slipping through manual timesheets, and resourcing scattered across separate tools. 

If that rings true for {COMPANY}, happy to share what's worked for similar teams. How are you set up at the moment? 

{MY_FIRST_NAME}`
  - variant 12 (262 chars, 42 words): `Hi {FIRST_NAME}, thanks for the add. Sales rep at Productive here. 

Disconnected tools, no real time profitability, billable hours going missing, if any of those are live issues at {COMPANY}, we can help. 

How are you managing it all right now? {MY_FIRST_NAME}`
  - variant 13 (559 chars, 89 words): `Hi {FIRST_NAME}, thanks for connecting.

I'm a sales rep at Productive, the platform that brings project management, resourcing, time tracking, budgets and invoicing into one place for agencies.

We mostly help agency and consultancy teams who lose billable hours to manual timesheets, can't see project profitability in real time, and are juggling four or five disconnected tools.

If any of that sounds like {COMPANY}, one brief call and we'll set your whole team up with a free premium trial.

How are you managing ops over there right now? {MY_FIRST_NAME}`
  - variant 14 (543 chars, 92 words): `Hi {FIRST_NAME}, good to connect.

Quick context, I'm a sales rep at Productive. We pull projects, resourcing and finances into a single platform built for agencies.

The teams we help usually have the same three headaches: gut feel forecasting, no live view of margin per project, and too many tools that don't talk to each other.

If that rings true for {COMPANY}, give me one short call and I'll get your whole team a free premium trial.

How are you handling all that today, solid system or still stitching things together? {MY_FIRST_NAME}`
  - variant 15 (526 chars, 86 words): `Hi {FIRST_NAME}, glad to be connected.

I work in sales at Productive and spend most of my time with agency ops people. We bring PM, time tracking, budgets and invoicing under one roof.

The pattern I keep hearing is billable hours slipping through manual timesheets, profitability you only see after the invoice goes out, and resourcing spread across separate tools.

If that's the picture at {COMPANY}, one brief call and your team gets a free premium trial, no strings.

How's your current setup holding up? {MY_FIRST_NAME}`
  - variant 16 (550 chars, 90 words): `Hi {FIRST_NAME}, thanks for the add.

I'm a sales rep at Productive, where we help agencies see project profitability while work is still live, not weeks after invoicing. Everything sits in one platform: projects, resourcing, time, budgets and billing.

Most leaders we speak to are stuck with no real time margin view, billable hours lost to manual tracking, and a stack of tools that don't connect.

If that's true for {COMPANY}, a quick call gets your whole team a free premium trial.

How are you tracking profitability right now? {MY_FIRST_NAME}`
  - variant 17 (522 chars, 87 words): `Hi {FIRST_NAME}, appreciate the connection.

I'm in sales at Productive. We replace the usual pile of agency tools with one platform that ties projects, resourcing, budgets and invoicing together.

Teams come to us when they're running four or five tools that don't sync, can't get a clean profitability number, and keep losing billable hours in the gaps.

If that sounds familiar at {COMPANY}, one short call and I'll set the whole team up on a free premium trial.

Is that close to how you operate today? {MY_FIRST_NAME}`
  - fallback (539 chars): `Hi, thanks for connecting.

I'm a sales rep at Productive, the platform that brings project management, resourcing, time tracking, budgets and invoicing into one place for agencies.

We mostly help teams who lose billable hours to manual timesheets, can't see project profitability in real time, and are juggling four or five disconnected tools.

If any of that sounds familiar, one brief call and we'll set your whole team up with a free premium trial.

How are you managing ops right now, solid system or still stitching things together?`
- message at day 6.12, 9 variant(s):
  - variant 1 (344 chars, 59 words): `Hi {FIRST_NAME}, just floating this back to the top of your inbox.

No worries if the timing's off, but if billable hours slipping away, no live profitability, or too many disconnected tools is a real thing at {COMPANY}, the offer still stands.

One brief call and your whole team gets a free premium trial.

Worth a quick chat? {MY_FIRST_NAME}`
  - variant 2 (326 chars, 58 words): `Hi {FIRST_NAME}, one quick question and I'll leave it there.

When someone at {COMPANY} needs to know if a project is actually profitable, how long does that take to pull together?

If the answer is longer than you'd like, that's exactly what we fix. One call and your team gets a free premium trial to see it. {MY_FIRST_NAME}`
  - variant 3 (350 chars, 59 words): `Hi {FIRST_NAME}, circling back with something concrete.

Hike One came to us with the same mess most agencies have, disconnected tools and no real time margin. They grew billable utilization 10% in their first year with us.

If {COMPANY} is anywhere near that, one brief call and your whole team gets a free premium trial. Open to it? {MY_FIRST_NAME}`
  - variant 4 (332 chars, 61 words): `Hi {FIRST_NAME}, want to make this easy.

The offer is a free premium trial for the entire {COMPANY} team, all I ask for first is one short call so I can set it up around how you actually work.

If lost billable hours, blurry profitability or tool sprawl are on your radar, it's worth the 20 minutes. When suits you? {MY_FIRST_NAME}`
  - variant 5 (341 chars, 59 words): `Hi {FIRST_NAME}, I don't want to keep nudging if it's not relevant.

Should I assume {COMPANY} has profitability, resourcing and billing well in hand, or is the disconnected tools thing still a quiet headache?

If it's the latter, one call gets your team a free premium trial. If not, no problem at all and I'll leave you be. {MY_FIRST_NAME}`
  - variant 6 (373 chars, 64 words): `Hi {FIRST_NAME}, following up with a different angle.

A lot of agency leads I talk to don't have a clean view of who's free across projects, so they overbook some people and lose billable time on others.

If {COMPANY} feels that, we put resourcing, projects and finances in one view. One brief call and your team gets a free premium trial. Worth exploring? {MY_FIRST_NAME}`
  - variant 7 (374 chars, 65 words): `Hi {FIRST_NAME}, quick thought to leave with you.

The expensive part of disconnected tools isn't the subscriptions, it's the billable hours that quietly leak out and the projects you find out were unprofitable too late to fix.

If that's a risk at {COMPANY}, one call and your team gets a free premium trial to see the whole picture in one place. Up for it? {MY_FIRST_NAME}`
  - variant 8 (233 chars, 39 words): `Hi {FIRST_NAME}, still happy to set {COMPANY} up with a free premium trial for the whole team after one short call.

Are lost billable hours, profitability blind spots, or too many tools live issues for you right now? {MY_FIRST_NAME}`
  - variant 9 (343 chars, 55 words): `Hi {FIRST_NAME}, last one from me so I'm not cluttering your inbox.

If the disconnected tools, hidden profitability and lost billable hours stuff ever becomes a priority at {COMPANY}, the door's open and the free team trial offer stands.

Just say the word and we'll grab 20 minutes. Otherwise, genuinely good to be connected. {MY_FIRST_NAME}`
  - fallback (429 chars): `Hi, just following up on my last message.

No worries if the timing's off, but if losing billable hours to manual timesheets, no real time view of project profitability, or juggling too many disconnected tools is a live issue for you, the offer still stands.

One brief call and we'll set your whole team up with a free premium trial.

Are any of those pain points hitting home right now? Happy to grab 20 minutes whenever suits.`
- message at day 12.12, 8 variant(s):
  - variant 1 (165 chars, 28 words): `Hey {FIRST_NAME}, still relevant?

Free premium trial for the {COMPANY} team is on the table, just need one quick call to set it up.

Lmk either way. {MY_FIRST_NAME}`
  - variant 2 (195 chars, 32 words): `Hey {FIRST_NAME}, quick one.

Is the projects, profitability and tools thing still worth solving at {COMPANY}, or have you got it covered?

Yes, no, or not now all work. Just lmk. {MY_FIRST_NAME}`
  - variant 3 (228 chars, 38 words): `Hey {FIRST_NAME}, still on your radar?

If ops and profitability isn't your area, totally fine, just point me to whoever owns it at {COMPANY} and I'll take it from there.

Free team trial offer stands either way. {MY_FIRST_NAME}`
  - variant 4 (189 chars, 33 words): `Hey {FIRST_NAME}, still relevant or just bad timing?

If now's not it, tell me when to circle back and I'll get out of your inbox.

The free team trial isn't going anywhere. {MY_FIRST_NAME}`
  - variant 5 (198 chars, 30 words): `Hey {FIRST_NAME}, still relevant?

Simple test: can you see right now whether your live projects at {COMPANY} are profitable?

If not, that's the call. Free team trial included. Lmk. {MY_FIRST_NAME}`
  - variant 6 (222 chars, 35 words): `Hey {FIRST_NAME}, still relevant?

One agency like yours grew billable utilization 10% in a year after ditching the disconnected tools.

Happy to show you how on a quick call, free team trial included. Lmk. {MY_FIRST_NAME}`
  - variant 7 (219 chars, 35 words): `Hey {FIRST_NAME}, chasing you gently here, promise this is friendly not pushy.

Still worth getting {COMPANY} that free team trial, or has the moment passed?

A one word reply saves us both the guessing. {MY_FIRST_NAME}`
  - variant 8 (238 chars, 41 words): `Hey {FIRST_NAME}, I'll take the quiet as a no for now, all good.

If the profitability, resourcing or tool sprawl stuff ever bites at {COMPANY}, the free team trial offer is here whenever.

Just say the word down the line. {MY_FIRST_NAME}`
  - fallback (250 chars): `Hey, still relevant?

Free premium trial for your whole team is on the table, just need one quick call to set it up.

If losing billable hours, no real time profitability, or too many disconnected tools is still a thing, worth a chat. Lmk either way.`

### 523993 — FIXED - PRODUCTIVE - MARKETING AGENCIES - ALL LEADS - ZVONIMIR NEW APPRAOCH - 05/13 v4

- ownership: **unknown** — not in the ledger and not on any operator-declared internal list; UNKNOWN is the state, not a gap
- provider status `IN_PROGRESS`; created `2026-07-27T14:48:16.017591Z`; started `2026-07-28T15:49:01.751003Z`
- seats (`campaignAccountIds`): 174892, 174748, 175455, 174742, 174332, 174810, 174822, 174845, 174803, 174797, 212356, 143105, 175552, 201978, 179527, 191848, 208253, 181658, 208242, 181653, 201959, 125748, 119588, 125775, 129082, 139699, 116988, 116973, 116968, 169600, 177751, 159259, 116989
- lead list `632277` (PRODUCTIVE - MARKETING AGENCIES - EU - SAFE TO SEND EMAIL - DOUBLE DOWN), list size `totalItemsCount` = 11128; campaign holds `progressStats.totalUsers` = 11128, finished 25
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **473**, accepted **21** (4.44%)
  - messages sent **16**, message threads started **11**, replies **2** (18.18% of threads started)
  - unique leads contacted **473**; profile views 492, follows 0, post likes 0
  - provider's own tags: `autoTaggedInterested` **0**, `totalAutoTagged` **2**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 11 conversations joined, 0 operator-positive replies = **0.000 per 100 requests sent**
- reply classes in this campaign: `unknown` 2
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-07-28 .. 2026-10-03 (49 days)
- sequence node types present in the whole graph: CONNECTION_REQUEST, END, MESSAGE, SEND_LEAD_TO_BISON, VIEW_PROFILE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CONNECTION_REQUEST    wait 15D     day 15.00
  step 1   MESSAGE               wait 3H      day 15.12
  step 2   SEND_LEAD_TO_BISON    wait 11D     day 26.12
  step 3   MESSAGE               wait 0H      day 26.12
  step 4   MESSAGE               wait 6D      day 32.12
  step 5   END                   wait 1D      day 33.12
```

**Connection note:** 1 `CONNECTION_REQUEST` note slot(s), every one of them EMPTY — this campaign sends connection requests with no note.

**Message steps — our text, in full:**

- message at day 15.12, 20 variant(s):
  - variant 1 (149 chars, 21 words): `hey {FIRST_NAME}, how does {COMPANY} currently track project profitability, is it all spreadsheets or do you have something in place? {MY_FIRST_NAME}`
  - variant 2 (181 chars, 33 words): `{FIRST_NAME} quick one, do you guys have resource planning sorted out at {COMPANY} or is that still a bit of a mess? asking cause i work with few {INDUSTRY} agencies on exactly that`
  - variant 3 (173 chars, 27 words): `hey {FIRST_NAME}! saw you're {POSITION} at {COMPANY}, curious how you handle billing and invoicing across projects, is it all manual or do you have a system? {MY_FIRST_NAME}`
  - variant 4 (185 chars, 29 words): `{FIRST_NAME}, random question but how many tools is {COMPANY} using to manage projects, resources and finances? asking cause most {INDUSTRY} agencies we talk to are juggling way to many`
  - variant 5 (152 chars, 25 words): `hey {FIRST_NAME}, do you guys have visibility on which projects are actually profitable at {COMPANY} or is that something you figure out after the fact?`
  - variant 6 (182 chars, 27 words): `{FIRST_NAME} hi, is resource planning something {COMPANY} has figured out or still a work in progress? we work with {INDUSTRY} agencies on getting that under control, {MY_FIRST_NAME}`
  - variant 7 (167 chars, 27 words): `hey {FIRST_NAME}! as {POSITION} at {COMPANY} curious if you have a single place where projects, budgets and resourcing all live or if its spread across different tools`
  - variant 8 (168 chars, 24 words): `{FIRST_NAME}, how do you guys handle project budgets at {COMPANY}, got that sorted or still piecing it together across spreadsheets and different tools? {MY_FIRST_NAME}`
  - variant 9 (162 chars, 28 words): `hey {FIRST_NAME}, do you have a good handle on utilization across the team at {COMPANY} or is that one of those things thats always a bit unclear? {MY_FIRST_NAME}`
  - variant 10 (156 chars, 25 words): `{FIRST_NAME} quick question, how does {COMPANY} track whether projects are staying on budget, is that something you have sorted or more of a manual process?`
  - variant 11 (176 chars, 28 words): `hey {FIRST_NAME}! saw {COMPANY} and was curious, whats the biggest operational headache for you guys right now, is it resourcing, profitability or just to many tools to manage?`
  - variant 12 (160 chars, 25 words): `{FIRST_NAME}, is invoicing and billing something {COMPANY} has nailed down or still one of those things that takes way more time than it should? {MY_FIRST_NAME}`
  - variant 13 (130 chars, 22 words): `hey {FIRST_NAME}, how do you guys forecast revenue at {COMPANY}, got a solid process or still kinda winging it quarter to quarter?`
  - variant 14 (186 chars, 32 words): `{FIRST_NAME} hi! as {POSITION} at a {INDUSTRY} agency curious if you have clear visibility on team capacity at any given time or if thats always a bit of a guessing game, {MY_FIRST_NAME}`
  - variant 15 (151 chars, 25 words): `hey {FIRST_NAME}, do you guys have project management, resourcing and finances in one place at {COMPANY} or is it spread across like 4 different tools?`
  - variant 16 (151 chars, 28 words): `{FIRST_NAME}, quick one, how does {COMPANY} know if a project is going to hit budget before it's to late to do anything about it? got that figured out?`
  - variant 17 (202 chars, 31 words): `hey {FIRST_NAME}! {MY_FIRST_NAME} here, i work with {INDUSTRY} agencies on operational stuff. curious if {COMPANY} has a handle on project profitability in real time or its more of a retrospective thing`
  - variant 18 (158 chars, 24 words): `{FIRST_NAME} is time tracking something the team at {COMPANY} actually does consistently or is that one of those things thats always a battle? {MY_FIRST_NAME}`
  - variant 19 (174 chars, 30 words): `hey {FIRST_NAME}, saw you're {POSITION} at {COMPANY}. do you have one place where you can see project status, team capacity and finances together or is it all over the place?`
  - variant 20 (148 chars, 23 words): `{FIRST_NAME} hi, how are you guys managing agency ops at {COMPANY} right now, got a solid system or still stitching things together? {MY_FIRST_NAME}`
  - fallback (125 chars): `hey, do you guys have project management, resourcing and finances in one place or is it spread across like 4 different tools?`
- message at day 26.12, 14 variant(s):
  - variant 1 (186 chars, 30 words): `hey {FIRST_NAME}, just bumping this up, agencies like {COMPANY} usually tell us the biggest thing is not knowing project profitability until its too late. is that something you run into?`
  - variant 2 (170 chars, 28 words): `{FIRST_NAME} following up, i know its probably not top of mind but curious, how are you guys currently handling resource planning, got something or still figuring it out?`
  - variant 3 (226 chars, 35 words): `hey {FIRST_NAME}! didn't hear back, no worries. just wanted to add, most {INDUSTRY} agencies we work with were running projects, finances and resourcing across 3-4 tools before consolidating. is that the case at {COMPANY} too?`
  - variant 4 (183 chars, 30 words): `{FIRST_NAME}, just checking in. one thing that comes up a lot with {INDUSTRY} agencies is losing billable hours just cause time tracking is inconsistent. is that a thing at {COMPANY}?`
  - variant 5 (184 chars, 30 words): `hey {FIRST_NAME}, following up on my last message. not trying to be annoying, genuinely curious if operational visibility is something {COMPANY} has sorted or if its still a pain point`
  - variant 6 (212 chars, 32 words): `{FIRST_NAME} hi, just bumping this. agencies usually lose a surprising amount of revenue just from projects going over budget without anyone catching it early. does that ring a bell at {COMPANY}? 
{MY_FIRST_NAME}`
  - variant 7 (179 chars, 31 words): `hey {FIRST_NAME}! quick follow up, do you guys have a way to see team utilization and project finances in one place or is that something you're still working towards at {COMPANY}?`
  - variant 8 (233 chars, 40 words): `{FIRST_NAME}, i know you're probably busy but wanted to follow up. most {POSITION}s we talk to at {INDUSTRY} agencies say the hardest thing is getting a clear picture of whats profitable and whats not. is that fair for {COMPANY} too?`
  - variant 9 (191 chars, 32 words): `hey {FIRST_NAME}, just circling back. not asking for a demo or anything, just curious, is agency ops something that feels under control at {COMPANY} right now or more of an ongoing challenge?`
  - variant 10 (241 chars, 40 words): `{FIRST_NAME} following up, one thing worth mentioning, agencies that get resourcing and project finances in one place usually save a meaningful chunk of time on admin every week. curious if that kind of thing would matter to you at {COMPANY}`
  - variant 11 (174 chars, 30 words): `hey {FIRST_NAME}! bumping this up, is now just a bad time or is operational tooling not really a priority at {COMPANY} right now? either way just let me know, {MY_FIRST_NAME}`
  - variant 12 (222 chars, 37 words): `hey {FIRST_NAME}, circling back quickly. a lot of {INDUSTRY} agencies tell us they only realize a project went sideways after invoicing. does that happen at {COMPANY} or do you have visibility before it gets to that point?`
  - variant 13 (169 chars, 26 words): `{FIRST_NAME}, just checking in, is this landing with the wrong person? happy to connect with whoever handles ops or tooling at {COMPANY} if thats easier, {MY_FIRST_NAME}`
  - variant 14 (202 chars, 34 words): `{FIRST_NAME}, i'll keep this short. is operational visibility something {COMPANY} has a good handle on or is it one of those things that could always be better? worth a quick chat if so, {MY_FIRST_NAME}`
  - fallback (180 chars): `hey, i'll keep this short. is operational visibility something your company has a good handle on or is it one of those things that could always be better? worth a quick chat if so?`
- message at day 32.12, 19 variant(s):
  - variant 1 (37 chars, 5 words): `hey {FIRST_NAME}, still relevant? lmk`
  - variant 2 (37 chars, 5 words): `hey {FIRST_NAME}, still relevant? lmk`
  - variant 3 (122 chars, 20 words): `hey {FIRST_NAME}! is ops and project visibility something {COMPANY} has sorted or still a work in progress, lmk either way`
  - variant 4 (71 chars, 12 words): `{FIRST_NAME}, bad timing or just not relevant? either is fine, just lmk`
  - variant 5 (109 chars, 16 words): `hey {FIRST_NAME}, wdyt, is managing projects and finances in one place something {COMPANY} would find useful?`
  - variant 6 (81 chars, 12 words): `{FIRST_NAME} still open to connecting? lmk and ill keep it short, {MY_FIRST_NAME}`
  - variant 7 (90 chars, 17 words): `hey {FIRST_NAME}! last one from me, wdyt, worth 15 min or not really a priority right now?`
  - variant 8 (96 chars, 17 words): `hey {FIRST_NAME}, no worries if the timings off, just lmk and ill follow up whenever makes sense`
  - variant 9 (147 chars, 20 words): `{FIRST_NAME} wdyt, is operational visibility something {COMPANY} is actively trying to improve or pretty happy with how things are? {MY_FIRST_NAME}`
  - variant 10 (96 chars, 18 words): `hey {FIRST_NAME}! just lmk if this isnt relevant and ill get out of your inbox, no hard feelings`
  - variant 11 (90 chars, 18 words): `{FIRST_NAME}, one last bump. wdyt, is it a yes, a not now or a not for us? {MY_FIRST_NAME}`
  - variant 12 (108 chars, 14 words): `hey {FIRST_NAME}, is project profitability something {COMPANY} tracks well right now, genuinely curious, lmk`
  - variant 13 (86 chars, 17 words): `{FIRST_NAME} hi, wdyt, open to a quick look or not the right time? either works for me`
  - variant 14 (125 chars, 20 words): `hey {FIRST_NAME}! last message i promise. is agency ops a pain point at {COMPANY} or pretty much handled, lmk {MY_FIRST_NAME}`
  - variant 15 (96 chars, 15 words): `{FIRST_NAME}, still think there could be something here for {COMPANY}. wdyt, worth a quick call?`
  - variant 16 (109 chars, 24 words): `hey {FIRST_NAME}, just lmk if you want me to send over some info or if its better i reach out in a few months`
  - variant 17 (123 chars, 21 words): `{FIRST_NAME} last one from me. is this relevant at all for {COMPANY} right now, yes, no or maybe later, lmk {MY_FIRST_NAME}`
  - variant 18 (121 chars, 23 words): `hey {FIRST_NAME}! wdyt, is there a better person at {COMPANY} i should be talking to about this or are you the right one?`
  - variant 19 (140 chars, 23 words): `{FIRST_NAME}, i'll leave it here. if the timing ever feels right for a chat about how {COMPANY} manages agency ops just lmk, {MY_FIRST_NAME}`
  - fallback (60 chars): `one last bump. wdyt, is it a yes, a not now or a not for us?`

### 523997 — FIXED - PRODUCTIVE - MARKETING AGENCIES - ALL LEADS - ZVONIMIR NEW APPRAOCH - 05/13 v2

- ownership: **unknown** — not in the ledger and not on any operator-declared internal list; UNKNOWN is the state, not a gap
- provider status `IN_PROGRESS`; created `2026-07-27T14:50:03.622009Z`; started `2026-07-28T15:47:22.666553Z`
- seats (`campaignAccountIds`): 174892, 174748, 175455, 174742, 174332, 174810, 174822, 174845, 174803, 174797, 212356, 143105, 175552, 201978, 179527, 159259, 191848, 208253, 181658, 208242, 181653, 201959, 139699, 129082, 125775, 125748, 119588, 116989, 116988, 116973, 116968, 169600, 177751
- lead list `632277` (PRODUCTIVE - MARKETING AGENCIES - EU - SAFE TO SEND EMAIL - DOUBLE DOWN), list size `totalItemsCount` = 11128; campaign holds `progressStats.totalUsers` = 11128, finished 90
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **919**, accepted **62** (6.75%)
  - messages sent **83**, message threads started **52**, replies **6** (11.54% of threads started)
  - unique leads contacted **919**; profile views 1000, follows 0, post likes 0
  - provider's own tags: `autoTaggedInterested` **5**, `totalAutoTagged` **6**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 52 conversations joined, 1 operator-positive replies = **0.109 per 100 requests sent**
- reply classes in this campaign: `unknown` 5, `positive` 1, `negative` 1, `automated` 1
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-07-28 .. 2026-10-03 (54 days)
- sequence node types present in the whole graph: CONNECTION_REQUEST, END, MESSAGE, SEND_LEAD_TO_BISON, VIEW_PROFILE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CONNECTION_REQUEST    wait 0H      day  0.00
  step 1   MESSAGE               wait 3H      day  0.12
  step 2   SEND_LEAD_TO_BISON    wait 11D     day 11.12
  step 3   MESSAGE               wait 0H      day 11.12
  step 4   MESSAGE               wait 6D      day 17.12
  step 5   END                   wait 1D      day 18.12
```

**Connection note:** 1 `CONNECTION_REQUEST` note slot(s), every one of them EMPTY — this campaign sends connection requests with no note.

**Message steps — our text, in full:**

- message at day 0.12, 3 variant(s):
  - variant 1 (173 chars, 27 words): `hey {FIRST_NAME}! saw you're {POSITION} at {COMPANY}, curious how you handle billing and invoicing across projects, is it all manual or do you have a system? {MY_FIRST_NAME}`
  - variant 2 (152 chars, 25 words): `hey {FIRST_NAME}, do you guys have visibility on which projects are actually profitable at {COMPANY} or is that something you figure out after the fact?`
  - variant 3 (148 chars, 23 words): `{FIRST_NAME} hi, how are you guys managing agency ops at {COMPANY} right now, got a solid system or still stitching things together? {MY_FIRST_NAME}`
  - fallback (125 chars): `hey, do you guys have project management, resourcing and finances in one place or is it spread across like 4 different tools?`
- message at day 11.12, 14 variant(s):
  - variant 1 (186 chars, 30 words): `hey {FIRST_NAME}, just bumping this up, agencies like {COMPANY} usually tell us the biggest thing is not knowing project profitability until its too late. is that something you run into?`
  - variant 2 (170 chars, 28 words): `{FIRST_NAME} following up, i know its probably not top of mind but curious, how are you guys currently handling resource planning, got something or still figuring it out?`
  - variant 3 (226 chars, 35 words): `hey {FIRST_NAME}! didn't hear back, no worries. just wanted to add, most {INDUSTRY} agencies we work with were running projects, finances and resourcing across 3-4 tools before consolidating. is that the case at {COMPANY} too?`
  - variant 4 (183 chars, 30 words): `{FIRST_NAME}, just checking in. one thing that comes up a lot with {INDUSTRY} agencies is losing billable hours just cause time tracking is inconsistent. is that a thing at {COMPANY}?`
  - variant 5 (184 chars, 30 words): `hey {FIRST_NAME}, following up on my last message. not trying to be annoying, genuinely curious if operational visibility is something {COMPANY} has sorted or if its still a pain point`
  - variant 6 (212 chars, 32 words): `{FIRST_NAME} hi, just bumping this. agencies usually lose a surprising amount of revenue just from projects going over budget without anyone catching it early. does that ring a bell at {COMPANY}? 
{MY_FIRST_NAME}`
  - variant 7 (179 chars, 31 words): `hey {FIRST_NAME}! quick follow up, do you guys have a way to see team utilization and project finances in one place or is that something you're still working towards at {COMPANY}?`
  - variant 8 (233 chars, 40 words): `{FIRST_NAME}, i know you're probably busy but wanted to follow up. most {POSITION}s we talk to at {INDUSTRY} agencies say the hardest thing is getting a clear picture of whats profitable and whats not. is that fair for {COMPANY} too?`
  - variant 9 (191 chars, 32 words): `hey {FIRST_NAME}, just circling back. not asking for a demo or anything, just curious, is agency ops something that feels under control at {COMPANY} right now or more of an ongoing challenge?`
  - variant 10 (241 chars, 40 words): `{FIRST_NAME} following up, one thing worth mentioning, agencies that get resourcing and project finances in one place usually save a meaningful chunk of time on admin every week. curious if that kind of thing would matter to you at {COMPANY}`
  - variant 11 (174 chars, 30 words): `hey {FIRST_NAME}! bumping this up, is now just a bad time or is operational tooling not really a priority at {COMPANY} right now? either way just let me know, {MY_FIRST_NAME}`
  - variant 12 (222 chars, 37 words): `hey {FIRST_NAME}, circling back quickly. a lot of {INDUSTRY} agencies tell us they only realize a project went sideways after invoicing. does that happen at {COMPANY} or do you have visibility before it gets to that point?`
  - variant 13 (169 chars, 26 words): `{FIRST_NAME}, just checking in, is this landing with the wrong person? happy to connect with whoever handles ops or tooling at {COMPANY} if thats easier, {MY_FIRST_NAME}`
  - variant 14 (202 chars, 34 words): `{FIRST_NAME}, i'll keep this short. is operational visibility something {COMPANY} has a good handle on or is it one of those things that could always be better? worth a quick chat if so, {MY_FIRST_NAME}`
  - fallback (180 chars): `hey, i'll keep this short. is operational visibility something your company has a good handle on or is it one of those things that could always be better? worth a quick chat if so?`
- message at day 17.12, 8 variant(s):
  - variant 1 (37 chars, 5 words): `hey {FIRST_NAME}, still relevant? lmk`
  - variant 2 (37 chars, 5 words): `hey {FIRST_NAME}, still relevant? lmk`
  - variant 3 (71 chars, 12 words): `{FIRST_NAME}, bad timing or just not relevant? either is fine, just lmk`
  - variant 4 (81 chars, 12 words): `{FIRST_NAME} still open to connecting? lmk and ill keep it short, {MY_FIRST_NAME}`
  - variant 5 (96 chars, 18 words): `hey {FIRST_NAME}! just lmk if this isnt relevant and ill get out of your inbox, no hard feelings`
  - variant 6 (86 chars, 17 words): `{FIRST_NAME} hi, wdyt, open to a quick look or not the right time? either works for me`
  - variant 7 (96 chars, 15 words): `{FIRST_NAME}, still think there could be something here for {COMPANY}. wdyt, worth a quick call?`
  - variant 8 (109 chars, 24 words): `hey {FIRST_NAME}, just lmk if you want me to send over some info or if its better i reach out in a few months`
  - fallback (60 chars): `one last bump. wdyt, is it a yes, a not now or a not for us?`

### 524000 — FIXED - PRODUCTIVE - MARKETING AGENCIES INMAIL- EU - CLEANED ZVONIIMR - AFTER EMAIL APPROACH INMAILS - 23/04

- ownership: **unknown** — not in the ledger and not on any operator-declared internal list; UNKNOWN is the state, not a gap
- provider status `IN_PROGRESS`; created `2026-07-27T14:51:43.877609Z`; started `2026-07-28T15:45:18.133791Z`
- seats (`campaignAccountIds`): 174892, 174748, 175455, 174742, 174332, 174822, 174845, 174803, 174797, 208242
- lead list `632277` (PRODUCTIVE - MARKETING AGENCIES - EU - SAFE TO SEND EMAIL - DOUBLE DOWN), list size `totalItemsCount` = 11128; campaign holds `progressStats.totalUsers` = 11128, finished 2194
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **0**, accepted **0** (n/a (denominator 0))
  - messages sent **0**, message threads started **0**, replies **0** (n/a (denominator 0) of threads started)
  - InMail: started **2208**, replies **144** (6.52%). `inmailMessagesSent` is **0** here and on every campaign on this seat — the InMail volume lives in `totalInmailStarted`, so a reader asking `inmailMessagesSent` sees zero.
  - unique leads contacted **2208**; profile views 4162, follows 7138, post likes 0
  - provider's own tags: `autoTaggedInterested` **8**, `totalAutoTagged` **144**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 2184 conversations joined, 4 operator-positive replies = **n/a (0 requests sent) per 100 requests sent**
- reply classes in this campaign: `negative` 72, `unknown` 59, `not_relevant` 13, `automated` 7, `positive` 2, `question` 2, `referral` 2, `not_now` 1, `objection` 1, `out_of_office` 1
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- sequence node types present in the whole graph: END, FOLLOW, INMAIL, VIEW_PROFILE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   FOLLOW                wait 1D      day  1.00
  step 1   INMAIL                wait 1D      day  2.00
  step 2   VIEW_PROFILE          wait 2D      day  4.00
  step 3   VIEW_PROFILE          wait 2D      day  6.00
  step 4   END                   wait 1D      day  7.00
```

**Connection note:** this graph has no `CONNECTION_REQUEST` node, so no note is sent.


### 524002 — FIXED - PRODUCTIVE - MARKETING AGENCIES - USA 2ND - CLEANED - ZVONIMIR V3

- ownership: **unknown** — not in the ledger and not on any operator-declared internal list; UNKNOWN is the state, not a gap
- provider status `IN_PROGRESS`; created `2026-07-27T14:53:09.268684Z`; started `2026-07-28T15:43:48.191166Z`
- seats (`campaignAccountIds`): 174892, 174748, 175455, 174742, 174332, 174822, 174803, 174797, 174810, 174845, 212356, 143105, 175552, 201978, 179527, 159259, 191848, 208253, 181658, 208242, 181653, 201959, 139699, 129082, 125775, 125748, 119588, 116988, 116973, 116968, 169600, 177751, 116989
- lead list `605355` (PRODUCTIVE - USA 1ST - ICP - FILTERED OUT OF 200K LEADS), list size `totalItemsCount` = 50563; campaign holds `progressStats.totalUsers` = 50563, finished 1351
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **30207**, accepted **1862** (6.16%)
  - messages sent **4029**, message threads started **1663**, replies **217** (13.05% of threads started)
  - unique leads contacted **30355**; profile views 41124, follows 45488, post likes 0
  - provider's own tags: `autoTaggedInterested` **44**, `totalAutoTagged` **217**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 1667 conversations joined, 18 operator-positive replies = **0.060 per 100 requests sent**
- reply classes in this campaign: `unknown` 155, `negative` 46, `automated` 19, `not_relevant` 16, `positive` 11, `question` 7, `unsubscribe` 6, `not_now` 4, `referral` 2, `out_of_office` 1, `send_info` 1
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-08-02 .. 2026-10-03 (63 days)
- sequence node types present in the whole graph: CONNECTION_REQUEST, END, FOLLOW, MESSAGE, VIEW_PROFILE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   FOLLOW                wait 3H      day  0.12
  step 1   CONNECTION_REQUEST    wait 5D      day  5.12
  step 2   MESSAGE               wait 3D      day  8.12
  step 3   MESSAGE               wait 6D      day 14.12
  step 4   MESSAGE               wait 4D      day 18.12
  step 5   MESSAGE               wait 5D      day 23.12
  step 6   MESSAGE               wait 4D      day 27.12
  step 7   END                   wait 1D      day 28.12
```

**Connection note:** 1 `CONNECTION_REQUEST` note slot(s), every one of them EMPTY — this campaign sends connection requests with no note.

**Message steps — our text, in full:**

- message at day 8.12, 11 variant(s):
  - variant 1 (370 chars, 55 words): `thanks for accepting {FIRST_NAME}, now i'll earn the connection. 

the usual agency pain is utilization, you don't really know who's overloaded and who's idle until something breaks. 

Productive gives you that view live, alongside budgets and billing in one place. what's your current setup for tracking it at {COMPANY}, a tool, spreadsheets, or vibes?
 {MY_FIRST_NAME}`
  - variant 2 (345 chars, 59 words): `fair's fair {FIRST_NAME}, you accepted, so here's the honest pitch. if your projects, timesheets and invoicing all live in different places, someone at {COMPANY} is doing a lot of manual stitching just to see if a job made money. Productive makes that one connected view. is that manual work a real drain for you, or not so much? {MY_FIRST_NAME}`
  - variant 3 (375 chars, 58 words): `here's the actual hook {FIRST_NAME}. most agencies don't have a margin problem, they have a visibility problem, the data's just scattered across too many tools to see clearly. 
Productive consolidates it so profitability is obvious, live, per project. would seeing that in one place actually change how you run things at {COMPANY}, or are you already there? 

{MY_FIRST_NAME}`
  - variant 4 (375 chars, 58 words): `here's the actual hook {FIRST_NAME}. most agencies don't have a margin problem, they have a visibility problem, the data's just scattered across too many tools to see clearly. 
Productive consolidates it so profitability is obvious, live, per project. would seeing that in one place actually change how you run things at {COMPANY}, or are you already there? 

{MY_FIRST_NAME}`
  - variant 5 (375 chars, 58 words): `here's the actual hook {FIRST_NAME}. most agencies don't have a margin problem, they have a visibility problem, the data's just scattered across too many tools to see clearly. 
Productive consolidates it so profitability is obvious, live, per project. would seeing that in one place actually change how you run things at {COMPANY}, or are you already there? 

{MY_FIRST_NAME}`
  - variant 6 (375 chars, 58 words): `here's the actual hook {FIRST_NAME}. most agencies don't have a margin problem, they have a visibility problem, the data's just scattered across too many tools to see clearly. 
Productive consolidates it so profitability is obvious, live, per project. would seeing that in one place actually change how you run things at {COMPANY}, or are you already there? 

{MY_FIRST_NAME}`
  - variant 7 (375 chars, 58 words): `here's the actual hook {FIRST_NAME}. most agencies don't have a margin problem, they have a visibility problem, the data's just scattered across too many tools to see clearly. 
Productive consolidates it so profitability is obvious, live, per project. would seeing that in one place actually change how you run things at {COMPANY}, or are you already there? 

{MY_FIRST_NAME}`
  - variant 8 (381 chars, 54 words): `told you i'd eventually say something useful {FIRST_NAME}, so here it is. the agencies i work with kept losing time to manual reporting and billable hours slipping through cracks. 

Productive ties projects, resourcing and finances together so that stops happening. genuinely curious what your biggest time-sink is at {COMPANY}, reporting, billing, or resourcing?

 {MY_FIRST_NAME}`
  - variant 9 (381 chars, 54 words): `told you i'd eventually say something useful {FIRST_NAME}, so here it is. the agencies i work with kept losing time to manual reporting and billable hours slipping through cracks. 

Productive ties projects, resourcing and finances together so that stops happening. genuinely curious what your biggest time-sink is at {COMPANY}, reporting, billing, or resourcing?

 {MY_FIRST_NAME}`
  - variant 10 (381 chars, 54 words): `told you i'd eventually say something useful {FIRST_NAME}, so here it is. the agencies i work with kept losing time to manual reporting and billable hours slipping through cracks. 

Productive ties projects, resourcing and finances together so that stops happening. genuinely curious what your biggest time-sink is at {COMPANY}, reporting, billing, or resourcing?

 {MY_FIRST_NAME}`
  - variant 11 (363 chars, 56 words): `okay {FIRST_NAME}, cards on the table. Productive is one platform for agencies that runs projects, time tracking, budgets and invoicing together, so you get live profitability instead of a month-end guessing game. {COMPANY} looked like the kind of team it fits. before i assume anything though, what's the most annoying part of your current stack? {MY_FIRST_NAME}`
  - fallback (357 chars): `So... here's the actual hook. 

Most agencies don't have a margin problem; they have a visibility problem, the data's just scattered across too many tools to see clearly. 

Productive consolidates it so profitability is obvious, live, per project. would seeing that in one place actually change how you run things at your company, or are you already there? `
- message at day 14.12, 9 variant(s):
  - variant 1 (197 chars, 33 words): `hey {FIRST_NAME}, a week of silence, which is either "not interested" or "saw it, got distracted by actual work." totally fine if it's the first. if it's the second, i'm still here. {MY_FIRST_NAME}`
  - variant 2 (297 chars, 52 words): `Hey {FIRST_NAME}, just circling back.

I will be straight with you. Between my colleague and I we have both reached out now and I think {COMPANY} is genuinely worth a conversation rather than just another follow up. What would make it worth 15 minutes of your time to take a look?

{MY_FIRST_NAME}`
  - variant 3 (176 chars, 29 words): `hey {FIRST_NAME}, the polite move is to pretend i forgot i messaged you. i didn't. just checking this didn't vanish into the LinkedIn void. worth a quick reply? {MY_FIRST_NAME}`
  - variant 4 (224 chars, 34 words): `{FIRST_NAME}, one of three things happened: you're busy, you're not interested, or my message was boring. happy to fix the third one with a better question. how's {COMPANY} handling project margin these days? {MY_FIRST_NAME}`
  - variant 5 (180 chars, 31 words): `hey {FIRST_NAME}, no guilt-trip here, i know exactly how fast a message gets buried. just floating this back up before i let it go. one word reply works, even "no." {MY_FIRST_NAME}`
  - variant 6 (196 chars, 32 words): `hey {FIRST_NAME}, day seven, the official point where a follow-up stops being keen and starts being clingy. so this is my one charming attempt before i back off. interested or nah? {MY_FIRST_NAME}`
  - variant 7 (184 chars, 33 words): `{FIRST_NAME}, circling back, and yes i hate that phrase too. truth is i think there's a real fit here for {COMPANY}. if there isn't, a quick "not for us" saves us both. {MY_FIRST_NAME}`
  - variant 8 (181 chars, 32 words): `hey {FIRST_NAME}, still here, still think your tool stack is quietly costing you money. but i also respect a busy inbox. want me to keep going or leave you in peace? {MY_FIRST_NAME}`
  - variant 9 (220 chars, 37 words): `{FIRST_NAME}, i promise this isn't an automated nudge, a bot wouldn't admit it's been a week. just a real person who thinks Productive could help {COMPANY} and didn't want to give up at the first silence. {MY_FIRST_NAME}`
  - fallback (247 chars): `Hey, just following up on my last message.

Rather than repeat the pitch I wanted to ask directly. What would need to be true about a tool for it to be worth 15 minutes of your time right now? Happy to tell you whether Productive fits that or not.`
- message at day 18.12, 1 variant(s):
  - variant 1 (282 chars, 51 words): `Hey {FIRST_NAME}, keeping this one short.

Productive has a 14 day free trial and no card required. If a call feels like too much of a commitment right now you can start at productive.io and see the platform on your own terms first.

Still here if you want to chat.

{MY_FIRST_NAME}`
  - fallback (440 chars): `Hey, trying a different angle this time.

The moment most agencies decide to switch to Productive is when someone asks a simple question about project profitability and the answer takes an hour to pull together from separate tools. If that has happened recently it is probably worth 15 minutes to see what it looks like when it does not.

Happy to set up a call or you can start a free trial at productive.io if you prefer to explore first.`
- message at day 23.12, 2 variant(s):
  - variant 1 (566 chars, 99 words): `Hey {FIRST_NAME}, I realize I have sent a few messages now so I will make this one count.

The agencies that get the most out of Productive are the ones where a {POSITION} is spending real time each week on work that should happen automatically. Pulling utilization reports, reconciling budgets, chasing time logs, building invoices from scratch. Productive handles all of that so the focus shifts to what the data is telling you rather than how to get the data in the first place.

If any of that sounds like {COMPANY} right now it is worth a look.

{MY_FIRST_NAME}`
  - variant 2 (469 chars, 77 words): `Hey {FIRST_NAME}, last proper pitch from me before I wrap up.

Three things Productive does that most agency tools do not. Time tracked connects directly to budget burn so you see profit impact as work happens. Resource planning shows utilization across the whole team in real time. Invoicing pulls from actual project data so there is no manual assembly.

If {COMPANY} is doing any of those things manually right now that is the gap Productive closes.

{MY_FIRST_NAME}`
  - fallback (426 chars): `Hey, making this one specific.

Three things Productive does that most agency tools do not. Time tracked connects directly to budget burn so you see profit impact as work happens. Resource planning shows team utilization in real time. Invoicing pulls from actual project data so there is no manual assembly.

If your agency is doing any of those things manually right now that is the gap Productive closes. Worth 15 minutes?

`
- message at day 27.12, 3 variant(s):
  - variant 1 (402 chars, 72 words): `Hey {FIRST_NAME}, wrapping up from my end.

Between my colleague and I we have sent a handful of messages and I do not want to keep landing in your inbox if the timing is just not right for {COMPANY}. No hard feelings at all.

If it ever becomes relevant, Productive has a free trial at productive.io and you can explore it without talking to anyone first. Worth knowing that is there.

{MY_FIRST_NAME}`
  - variant 2 (297 chars, 51 words): `Hey {FIRST_NAME}, last one from me.

I get it, the timing might just not be right. If things change at {COMPANY} and getting a cleaner view of margins and utilization becomes a priority, feel free to reach out directly or start a free trial at productive.io.

Leaving it with you.

{MY_FIRST_NAME}`
  - variant 3 (350 chars, 62 words): `Hey {FIRST_NAME}, closing the loop on my end.

My colleague reached out, I followed up a few times and I think we have both made a reasonable case for why Productive could work well for {COMPANY}. At this point it is in your hands.

If the moment ever comes where the current setup stops working, productive.io is the place to start.

{MY_FIRST_NAME}`
  - fallback (305 chars): `Hey, last message from me on this.

My colleague and I have both reached out now and I do not want to keep taking up space in your inbox. If the timing is ever right, Productive has a free trial at productive.io and you do not need to speak to anyone to get started.

Thanks for bearing with the outreach.`

### 524013 — FIXED - PRODUCTIVE - MARKETING AGENCIES - USA 2ND - CLEANED - ZVONIMIR

- ownership: **unknown** — not in the ledger and not on any operator-declared internal list; UNKNOWN is the state, not a gap
- provider status `IN_PROGRESS`; created `2026-07-27T14:57:53.584625Z`; started `2026-07-28T15:42:16.042873Z`
- seats (`campaignAccountIds`): 174748, 175455, 174742, 174332, 174822, 174803, 174797, 174845, 208242, 174892
- lead list `605359` (PRODUCTIVE - USA 2ND - ICP - FILTERED OUT OF 200K LEADS), list size `totalItemsCount` = 50469; campaign holds `progressStats.totalUsers` = 50469, finished 25
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **446**, accepted **30** (6.73%)
  - messages sent **101**, message threads started **29**, replies **4** (13.79% of threads started)
  - unique leads contacted **446**; profile views 864, follows 0, post likes 0
  - provider's own tags: `autoTaggedInterested` **1**, `totalAutoTagged` **4**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 29 conversations joined, 0 operator-positive replies = **0.000 per 100 requests sent**
- reply classes in this campaign: `unknown` 3, `automated` 1, `not_relevant` 1
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-07-28 .. 2026-10-02 (57 days)
- sequence node types present in the whole graph: CONNECTION_REQUEST, END, INMAIL, MESSAGE, VIEW_PROFILE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CONNECTION_REQUEST    wait 0H      day  0.00
  step 1   MESSAGE               wait 3D      day  3.00
  step 2   MESSAGE               wait 3D      day  6.00
  step 3   MESSAGE               wait 9D      day 15.00
  step 4   MESSAGE               wait 8D      day 23.00
  step 5   MESSAGE               wait 5D      day 28.00
  step 6   END                   wait 1D      day 29.00
```

**Connection note:** 1 `CONNECTION_REQUEST` note slot(s), every one of them EMPTY — this campaign sends connection requests with no note.

**Message steps — our text, in full:**

- message at day 3.00, 3 variant(s):
  - variant 1 (494 chars, 80 words): `Hi {FIRST_NAME}, really appreciate the add.

I help marketing and advertisement agencies replace the usual pile of disconnected tools with one platform that ties together projects, time tracking, budgets and invoicing. The idea being that you can actually see whether a project is profitable while it is still running rather than finding out after the invoice goes out.

Thought your team might be worth a conversation at some point. No pressure on that though, good to be connected either way.`
  - variant 2 (296 chars, 49 words): `Hey {FIRST_NAME}, thanks for connecting.

I work with marketing agencies on the ops side, specifically helping teams get a real time view of project profitability and utilization without juggling five different tools to do it. I thought it could be relevant at some point.

Want me to share more?`
  - variant 3 (300 chars, 55 words): `Hi {FIRST_NAME}, good to be connected.

I work with marketing agencies on the gap between time logged and money made. The people I with know something is leaking but cannot pinpoint where until it is too late to fix it.

Thought your team might find it useful to see how other teams are solving that?`
  - fallback (322 chars): `Hi, appreciate the add.

I work with agencies on the ops and profitability side, specifically helping teams replace their disconnected tool stack with one platform that ties together projects, time tracking, budgets and invoicing.

Happy to share more if it is ever relevant to your setup. Good to be connected either way.`
- message at day 6.00, 3 variant(s):
  - variant 1 (220 chars, 43 words): `Hi, what do you currently use to track project profitability in real time? Not after the work is done, I mean while a project is still live.

Asking to figure out whether what I do would actually be useful to you or not.`
  - variant 2 (236 chars, 48 words): `How does your company know if a project is going to hit its margin before it is finished? Is that something you can see at any point or does it only become clear after the fact?

Genuinely curious to see if there's a fit with what I do.`
  - variant 3 (224 chars, 43 words): `Hey, when a project goes over budget who is the first person to find out and how do they find out?

Genuinely asking, since the answer usually tells me pretty quickly whether what I do would actually be useful to you or not.`
  - fallback (220 chars): `Hi, what do you currently use to track project profitability in real time? Not after the work is done, I mean while a project is still live.

Asking to figure out whether what I do would actually be useful to you or not.`
- message at day 15.00, 3 variant(s):
  - variant 1 (400 chars, 65 words): `Figured I should share a bit more about what I actually work with, {FIRST_NAME}.

It's called Productive. It brings project management, time tracking, budgets and invoicing into one place so the data connects automatically, no more pulling numbers from four different tools every time someone asks how a project's tracking or what the margin looks like.

Woukd you like to hear more if it's relevant?`
  - variant 2 (371 chars, 64 words): `Sharing this because I genuinely think it could be useful for your team, {FIRST_NAME}.

It's called Productive. It replaces the need to run separate tools for project management, time, budgets and invoicing by pulling all of it into one place, so you can see live margin and utilization without anyone having to build a manual report.

Would you want to see it in action?`
  - variant 3 (387 chars, 60 words): `I should have mentioned this earlier, {FIRST_NAME}.

The product I work with is Productive. It's an agency management platform that connects time tracking to budgets to invoicing, so the financial picture updates automatically as work happens. Most teams end up replacing Harvest, Asana or whatever spreadsheet is doing the reporting work right now.

Would you like to see a walkthrough?`
  - fallback (386 chars): `Figured I should share a bit more about what I actually work with.

It's called Productive. It brings project management, time tracking, budgets and invoicing into one place so the data connects automatically, no more pulling numbers from four different tools every time someone asks how a project's tracking or what the margin looks like.

Woukd you like to hear more if it's relevant?`
- message at day 23.00, 3 variant(s):
  - variant 1 (329 chars, 56 words): `Wanted to add that most agencies that switch to Productive end up replacing Harvest or Toggl for time, Monday or Asana for projects, and whatever spreadsheet was doing the budget reporting. The reason it sticks is that the data finally connects instead of sitting in separate tools someone has to reconcile by hand. Worth a look?`
  - variant 2 (275 chars, 47 words): `Just adding that most agencies that get the most out of Productive are running exactly the kind of setup you're probably running right now. Multiple tools that work fine on their own but don't talk to each other, so someone ends up doing the connecting manually.

Interested?`
  - variant 3 (299 chars, 57 words): `The question I get most before people see Productive is something like, how long does it take you to answer whether you made money on that project? At most agencies it takes a day or two of pulling data together. In Productive the answer's on screen in real time.

Does it make sense to take a look?`
  - fallback (327 chars): `Wanted to add that most agencies that switch to Productive end up replacing Harvest or Toggl for time, Monday or Asana for projects, and whatever spreadsheet was doing the budget reporting. The reason it sticks is that the data finally connects instead of sitting in separate tools someone has to reconcile by hand. Interested?`
- message at day 28.00, 4 variant(s):
  - variant 1 (169 chars, 33 words): `If the timing is off or just not relevant, I'd rather know than keep nudging you.

Productive has a free 14 day trial if that is something you'd want to check out first.`
  - variant 2 (227 chars, 43 words): `No hard feelings at all, timing is everything with this kind of thing. If the tool stack ever becomes a real headache or you want better visibility into project margins, there is a free trial if you'd want to take a look first.`
  - variant 3 (285 chars, 55 words): `Hey, no hard feelings at all, timing is everything with this kind of thing. If you ever gets to a point where the tool stack becomes a real headache or you want better visibility into project margins, Productive is worth a look.

There is a free trial if you want to take a look first.`
  - variant 4 (218 chars, 43 words): `I know these messages land at all kinds of bad times so no offence taken. If the problem I have been describing ever becomes urgent at your company you can start a free trial. Let me know and I'll send all the details.`
  - fallback (169 chars): `If the timing is off or just not relevant, I'd rather know than keep nudging you.

Productive has a free 14 day trial if that is something you'd want to check out first.`

### 524026 — FIXED - PRODUCTIVE - MARKETING AGENCIES RT - USA 1ST - CLEANED - ZVONIMIR V3

- ownership: **unknown** — not in the ledger and not on any operator-declared internal list; UNKNOWN is the state, not a gap
- provider status `DRAFT`; created `2026-07-27T15:03:47.897587Z`; started `never`
- seats (`campaignAccountIds`): 174892, 174748, 175455, 174742, 174332, 174822, 174803, 174797, 174810, 174845, 212356, 143105, 175552, 201978, 179527, 159259, 129531, 191848, 194061, 208253, 181658, 208242, 181653, 201959, 139699, 129082, 125775, 125748, 119588, 116988, 116973, 116968, 169600
- lead list `605355` (PRODUCTIVE - USA 1ST - ICP - FILTERED OUT OF 200K LEADS), list size `totalItemsCount` = 50563; campaign holds `progressStats.totalUsers` = 0, finished 0
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **0**, accepted **0** (n/a (denominator 0))
  - messages sent **0**, message threads started **0**, replies **0** (n/a (denominator 0) of threads started)
  - unique leads contacted **0**; profile views 0, follows 0, post likes 0
  - provider's own tags: `autoTaggedInterested` **0**, `totalAutoTagged` **0**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 0 conversations joined, 0 operator-positive replies = **n/a (0 requests sent) per 100 requests sent**
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- sequence node types present in the whole graph: CONNECTION_REQUEST, END, FOLLOW, MESSAGE, VIEW_PROFILE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   FOLLOW                wait 3H      day  0.12
  step 1   CONNECTION_REQUEST    wait 3D      day  3.12
  step 2   MESSAGE               wait 3D      day  6.12
  step 3   MESSAGE               wait 6D      day 12.12
  step 4   MESSAGE               wait 4D      day 16.12
  step 5   MESSAGE               wait 5D      day 21.12
  step 6   MESSAGE               wait 3D      day 24.12
  step 7   END                   wait 1D      day 25.12
```

**Connection note:** 5 `CONNECTION_REQUEST` note slot(s), every one of them EMPTY — this campaign sends connection requests with no note.

**Message steps — our text, in full:**

- message at day 6.12, 3 variant(s):
  - variant 1 (607 chars, 105 words): `Hey {FIRST_NAME}, a colleague of mine probably reached out to you about Productive recently. I wanted to add my own note because {COMPANY} genuinely looks like a strong fit for what we do and I did not want it to get buried in a busy inbox.

I work with {INDUSTRY} agencies in {LOCATION} on the ops and profitability side. The short version is that Productive replaces the disconnected tool stack most agencies run on and gives a {POSITION} a real time view of project margins, utilization and forecasts in one place.

Worth a quick conversation to see if it maps to how {COMPANY} operates?

{MY_FIRST_NAME}`
  - variant 2 (429 chars, 74 words): `Hey {FIRST_NAME}, you may have already heard from someone on my team about Productive. I am reaching out separately because I look at the {INDUSTRY} space in {LOCATION} specifically and {COMPANY} keeps coming up as a business that would get a lot out of the platform.

Happy to give you a different perspective on it if the first message did not land at the right time. Sometimes it just takes the right framing.

{MY_FIRST_NAME}`
  - variant 3 (429 chars, 74 words): `Hey {FIRST_NAME}, one of my colleagues reached out to you about Productive recently. I am following up because I wanted to make this feel less like a blast and more like a real conversation.

I spend most of my time working with {POSITION}s at {INDUSTRY} agencies and the problems I hear consistently are the same ones Productive was built to solve. Thought it was worth one more shot before leaving it with you.

{MY_FIRST_NAME}`
  - fallback (453 chars): `Hey, a colleague of mine probably reached out recently about Productive. I wanted to follow up from my side because your agency looks like a strong fit for what we do, and I did not want it to get lost.

The short version is that Productive is an agency management platform that connects project management, time tracking, budgets, and invoicing so everything talks to each other. Happy to give you a fresh perspective on it if the timing is better now.`
- message at day 12.12, 3 variant(s):
  - variant 1 (392 chars, 66 words): `Hey {FIRST_NAME}, checking in to see if my last message landed.

Rather than send another pitch I wanted to ask a genuine question. When a project at {COMPANY} goes over budget or under delivers on margin, how long does it typically take before someone catches it?

The answer to that is usually what tells me whether Productive would actually change anything for you or not.

{MY_FIRST_NAME}`
  - variant 2 (328 chars, 52 words): `Hey {FIRST_NAME}, following up on my last note.

Quick question about {COMPANY}. How does your team currently know whether you are fully utilizing your people across projects? Not a trick question, I am asking because that visibility gap is exactly what most {INDUSTRY} agencies I work with are trying to close.

{MY_FIRST_NAME}`
  - variant 3 (297 chars, 52 words): `Hey {FIRST_NAME}, just circling back.

I will be straight with you. Between my colleague and I we have both reached out now and I think {COMPANY} is genuinely worth a conversation rather than just another follow up. What would make it worth 15 minutes of your time to take a look?

{MY_FIRST_NAME}`
  - fallback (247 chars): `Hey, just following up on my last message.

Rather than repeat the pitch I wanted to ask directly. What would need to be true about a tool for it to be worth 15 minutes of your time right now? Happy to tell you whether Productive fits that or not.`
- message at day 16.12, 3 variant(s):
  - variant 1 (544 chars, 93 words): `Hey {FIRST_NAME}, one more thought in case the timing is better now.

The thing most {POSITION}s at {INDUSTRY} agencies tell me after they see Productive is that they wish they had seen it before their last hire. The reason is that resourcing and growth decisions get made on utilization data and most agencies are working from numbers that are a month old and manually assembled.

Productive puts that in front of you in real time so the decisions at {COMPANY} are based on what is actually happening now.

Still worth a look?

{MY_FIRST_NAME}`
  - variant 2 (486 chars, 83 words): `Hey {FIRST_NAME}, trying a different angle this time.

Most {INDUSTRY} agencies in {LOCATION} that switch to Productive do it because of one specific moment. Someone asks how a project is tracking, the answer requires pulling from three different tools and an hour of work, and whoever is responsible decides there has to be a better way.

If that moment has not happened at {COMPANY} yet it probably will. Happy to show you what it looks like when it does not need to.

{MY_FIRST_NAME}`
  - variant 3 (282 chars, 51 words): `Hey {FIRST_NAME}, keeping this one short.

Productive has a 14 day free trial and no card required. If a call feels like too much of a commitment right now you can start at productive.io and see the platform on your own terms first.

Still here if you want to chat.

{MY_FIRST_NAME}`
  - fallback (440 chars): `Hey, trying a different angle this time.

The moment most agencies decide to switch to Productive is when someone asks a simple question about project profitability and the answer takes an hour to pull together from separate tools. If that has happened recently it is probably worth 15 minutes to see what it looks like when it does not.

Happy to set up a call or you can start a free trial at productive.io if you prefer to explore first.`
- message at day 21.12, 3 variant(s):
  - variant 1 (604 chars, 95 words): `Hey {FIRST_NAME}, sharing something specific in case it is useful.

{INDUSTRY} agencies in {LOCATION} that use Productive typically replace Harvest or Toggl for time tracking, Monday or Asana for project management and whatever spreadsheet was doing the budget reporting. The economics tend to work out well because they are paying for fewer tools and making better decisions with the data they were already capturing.

For a {POSITION} at {COMPANY} the main shift is that you stop being the person assembling the picture and start being the person who already has it.

Worth 15 minutes?

{MY_FIRST_NAME}`
  - variant 2 (566 chars, 99 words): `Hey {FIRST_NAME}, I realize I have sent a few messages now so I will make this one count.

The agencies that get the most out of Productive are the ones where a {POSITION} is spending real time each week on work that should happen automatically. Pulling utilization reports, reconciling budgets, chasing time logs, building invoices from scratch. Productive handles all of that so the focus shifts to what the data is telling you rather than how to get the data in the first place.

If any of that sounds like {COMPANY} right now it is worth a look.

{MY_FIRST_NAME}`
  - variant 3 (469 chars, 77 words): `Hey {FIRST_NAME}, last proper pitch from me before I wrap up.

Three things Productive does that most agency tools do not. Time tracked connects directly to budget burn so you see profit impact as work happens. Resource planning shows utilization across the whole team in real time. Invoicing pulls from actual project data so there is no manual assembly.

If {COMPANY} is doing any of those things manually right now that is the gap Productive closes.

{MY_FIRST_NAME}`
  - fallback (426 chars): `Hey, making this one specific.

Three things Productive does that most agency tools do not. Time tracked connects directly to budget burn so you see profit impact as work happens. Resource planning shows team utilization in real time. Invoicing pulls from actual project data so there is no manual assembly.

If your agency is doing any of those things manually right now that is the gap Productive closes. Worth 15 minutes?

`
- message at day 24.12, 3 variant(s):
  - variant 1 (402 chars, 72 words): `Hey {FIRST_NAME}, wrapping up from my end.

Between my colleague and I we have sent a handful of messages and I do not want to keep landing in your inbox if the timing is just not right for {COMPANY}. No hard feelings at all.

If it ever becomes relevant, Productive has a free trial at productive.io and you can explore it without talking to anyone first. Worth knowing that is there.

{MY_FIRST_NAME}`
  - variant 2 (297 chars, 51 words): `Hey {FIRST_NAME}, last one from me.

I get it, the timing might just not be right. If things change at {COMPANY} and getting a cleaner view of margins and utilization becomes a priority, feel free to reach out directly or start a free trial at productive.io.

Leaving it with you.

{MY_FIRST_NAME}`
  - variant 3 (350 chars, 62 words): `Hey {FIRST_NAME}, closing the loop on my end.

My colleague reached out, I followed up a few times and I think we have both made a reasonable case for why Productive could work well for {COMPANY}. At this point it is in your hands.

If the moment ever comes where the current setup stops working, productive.io is the place to start.

{MY_FIRST_NAME}`
  - fallback (305 chars): `Hey, last message from me on this.

My colleague and I have both reached out now and I do not want to keep taking up space in your inbox. If the timing is ever right, Productive has a free trial at productive.io and you do not need to speak to anyone to get started.

Thanks for bearing with the outreach.`

### 562830 — PRODUCTIVE - BERNARDA CONNECTIONS - MARKETING AGENCIES - JELENA - AUGUST 21

- ownership: **unknown** — not in the ledger and not on any operator-declared internal list; UNKNOWN is the state, not a gap
- provider status `FINISHED`; created `2026-08-21T10:18:04.582216Z`; started `2026-08-24T09:39:07.120412Z`
- seats (`campaignAccountIds`): 174332
- lead list `876751` (Bernarda approved), list size `totalItemsCount` = 192; campaign holds `progressStats.totalUsers` = 192, finished 181
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **0**, accepted **0** (n/a (denominator 0))
  - messages sent **190**, message threads started **102**, replies **12** (11.76% of threads started)
  - unique leads contacted **102**; profile views 0, follows 0, post likes 0
  - provider's own tags: `autoTaggedInterested` **3**, `totalAutoTagged` **12**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 98 conversations joined, 1 operator-positive replies = **n/a (0 requests sent) per 100 requests sent**
- reply classes in this campaign: `unknown` 6, `negative` 3, `question` 1
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-08-24 .. 2026-09-16 (13 days)
- sequence node types present in the whole graph: CHECK_IS_CONNECTION, END, MESSAGE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CHECK_IS_CONNECTION   wait 0H      day  0.00
  step 1   MESSAGE               wait 0H      day  0.00
  step 2   MESSAGE               wait 5D      day  5.00
  step 3   MESSAGE               wait 5D      day 10.00
  step 4   END                   wait 1D      day 11.00
```

**Connection note:** this graph has no `CONNECTION_REQUEST` node, so no note is sent.

**Message steps — our text, in full:**

- message at day 0.00, 4 variant(s):
  - variant 1 (337 chars, 59 words): `Hi {FIRST_NAME}, we've been connected a while but never actually talked. I'll be direct about why I'm reaching out, I'm on the team at Productive, we help agencies get a live view of project profitability instead of finding out after the invoice's gone out. Think it's relevant for what you do at {COMPANY}. Worth 20 minutes to show you?`
  - variant 2 (327 chars, 55 words): `Hi {FIRST_NAME}, we've been connected a while but I don't think we've ever actually talked. 

I'm on the team at Productive, a platform agencies use to see project profitability live instead of finding out after the invoice's out. Think it's relevant for what you do at {COMPANY}. 

Happy to show you in 20 minutes. Interested?`
  - variant 3 (373 chars, 66 words): `Hey {FIRST_NAME}, we're connected but never got to talk. Reaching out because I think Productive could be relevant for you as a {POSITION}. The pitch: 20 minutes on how agencies get a live view of project profitability instead of finding out after the invoice's out. The deal: no deck, no follow up pressure either way, just a straight look at whether it fits. 

Up for it?`
  - variant 4 (351 chars, 61 words): `Hi {FIRST_NAME}, we've been connected but never actually chatted. I'll be direct about why I'm reaching out. Productive is a platform I think makes sense for {COMPANY}, and I'd love to show you what it does in 20 minutes. And because I know calendars are packed, there's no pitch deck involved, just a straight look at whether it's useful. Sound fair?`
  - fallback (315 chars): `Hi, we've been connected a while but never actually talked. 

I'll be direct about why I'm reaching out, I'm on the team at Productive, we help agencies get a live view of project profitability instead of finding out after the invoice's gone out. Think it's relevant for what you do. 

Worth 20 minutes to show you?`
- message at day 5.00, 3 variant(s):
  - variant 1 (306 chars, 50 words): `Here's the actual reason I think it's worth your time, {FIRST_NAME}. Some agencies are still stitching together budgets, resourcing, and time tracking across separate tools and only find out a project lost money once the invoice's gone out and Productive fixes that. Want to see if it applies to {COMPANY}?`
  - variant 2 (309 chars, 54 words): `{FIRST_NAME}, not sure my last message actually landed, so trying again. No pressure either way on the 20 minutes. The actual value is Productive connecting your project data to the financial side, so your team stops piecing it together after the fact and just sees it live. 

Would you like me to share more?`
  - variant 3 (272 chars, 43 words): `Hi {FIRST_NAME}, one thing I keep hearing from {POSITION} roles in your industry is that profitability visibility is the bottleneck, not because it's complicated, just because the tools haven't caught up. That's exactly what Productive is built for. 

Want to take a look?`
  - fallback (292 chars): `Here's the actual reason I think it's worth your time. Some agencies are still stitching together budgets, resourcing, and time tracking across separate tools and only find out a project lost money once the invoice's gone out and Productive fixes that. Want to see if it applies to your team?`
- message at day 10.00, 3 variant(s):
  - variant 1 (75 chars, 16 words): `Should I take this as a no for now, {FIRST_NAME}, or keep it on your radar?`
  - variant 2 (77 chars, 14 words): `Yes to 20 minutes at some point, {FIRST_NAME}, or should I stop reaching out?`
  - variant 3 (67 chars, 12 words): `Still worth 20 minutes, {FIRST_NAME}, or should I leave it for now?`
  - fallback (61 chars): `Should I take this as a no for now, or keep it on your radar?`

### 565187 — PRODUCTIVE - BOJAN R CONNECTIONS - MARKETING AGENCIES - JELENA - AUGUST 21

- ownership: **unknown** — not in the ledger and not on any operator-declared internal list; UNKNOWN is the state, not a gap
- provider status `FINISHED`; created `2026-08-24T09:21:12.789894Z`; started `2026-08-24T09:38:36.058895Z`
- seats (`campaignAccountIds`): 174742
- lead list `876757` (Bojan R approved), list size `totalItemsCount` = 273; campaign holds `progressStats.totalUsers` = 273, finished 268
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **0**, accepted **0** (n/a (denominator 0))
  - messages sent **318**, message threads started **161**, replies **13** (8.07% of threads started)
  - unique leads contacted **161**; profile views 0, follows 0, post likes 0
  - provider's own tags: `autoTaggedInterested` **1**, `totalAutoTagged` **13**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 162 conversations joined, 0 operator-positive replies = **n/a (0 requests sent) per 100 requests sent**
- reply classes in this campaign: `unknown` 6, `negative` 6, `unsubscribe` 1, `out_of_office` 1, `automated` 1
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-08-27 .. 2026-09-30 (14 days)
- sequence node types present in the whole graph: CHECK_IS_CONNECTION, END, MESSAGE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CHECK_IS_CONNECTION   wait 0H      day  0.00
  step 1   MESSAGE               wait 0H      day  0.00
  step 2   MESSAGE               wait 5D      day  5.00
  step 3   MESSAGE               wait 5D      day 10.00
  step 4   END                   wait 1D      day 11.00
```

**Connection note:** this graph has no `CONNECTION_REQUEST` node, so no note is sent.

**Message steps — our text, in full:**

- message at day 0.00, 4 variant(s):
  - variant 1 (337 chars, 59 words): `Hi {FIRST_NAME}, we've been connected a while but never actually talked. I'll be direct about why I'm reaching out, I'm on the team at Productive, we help agencies get a live view of project profitability instead of finding out after the invoice's gone out. Think it's relevant for what you do at {COMPANY}. Worth 20 minutes to show you?`
  - variant 2 (327 chars, 55 words): `Hi {FIRST_NAME}, we've been connected a while but I don't think we've ever actually talked. 

I'm on the team at Productive, a platform agencies use to see project profitability live instead of finding out after the invoice's out. Think it's relevant for what you do at {COMPANY}. 

Happy to show you in 20 minutes. Interested?`
  - variant 3 (373 chars, 66 words): `Hey {FIRST_NAME}, we're connected but never got to talk. Reaching out because I think Productive could be relevant for you as a {POSITION}. The pitch: 20 minutes on how agencies get a live view of project profitability instead of finding out after the invoice's out. The deal: no deck, no follow up pressure either way, just a straight look at whether it fits. 

Up for it?`
  - variant 4 (351 chars, 61 words): `Hi {FIRST_NAME}, we've been connected but never actually chatted. I'll be direct about why I'm reaching out. Productive is a platform I think makes sense for {COMPANY}, and I'd love to show you what it does in 20 minutes. And because I know calendars are packed, there's no pitch deck involved, just a straight look at whether it's useful. Sound fair?`
  - fallback (315 chars): `Hi, we've been connected a while but never actually talked. 

I'll be direct about why I'm reaching out, I'm on the team at Productive, we help agencies get a live view of project profitability instead of finding out after the invoice's gone out. Think it's relevant for what you do. 

Worth 20 minutes to show you?`
- message at day 5.00, 3 variant(s):
  - variant 1 (306 chars, 50 words): `Here's the actual reason I think it's worth your time, {FIRST_NAME}. Some agencies are still stitching together budgets, resourcing, and time tracking across separate tools and only find out a project lost money once the invoice's gone out and Productive fixes that. Want to see if it applies to {COMPANY}?`
  - variant 2 (309 chars, 54 words): `{FIRST_NAME}, not sure my last message actually landed, so trying again. No pressure either way on the 20 minutes. The actual value is Productive connecting your project data to the financial side, so your team stops piecing it together after the fact and just sees it live. 

Would you like me to share more?`
  - variant 3 (272 chars, 43 words): `Hi {FIRST_NAME}, one thing I keep hearing from {POSITION} roles in your industry is that profitability visibility is the bottleneck, not because it's complicated, just because the tools haven't caught up. That's exactly what Productive is built for. 

Want to take a look?`
  - fallback (292 chars): `Here's the actual reason I think it's worth your time. Some agencies are still stitching together budgets, resourcing, and time tracking across separate tools and only find out a project lost money once the invoice's gone out and Productive fixes that. Want to see if it applies to your team?`
- message at day 10.00, 3 variant(s):
  - variant 1 (75 chars, 16 words): `Should I take this as a no for now, {FIRST_NAME}, or keep it on your radar?`
  - variant 2 (77 chars, 14 words): `Yes to 20 minutes at some point, {FIRST_NAME}, or should I stop reaching out?`
  - variant 3 (67 chars, 12 words): `Still worth 20 minutes, {FIRST_NAME}, or should I leave it for now?`
  - fallback (61 chars): `Should I take this as a no for now, or keep it on your radar?`

### 565193 — PRODUCTIVE - BRUNO CONNECTIONS - MARKETING AGENCIES - JELENA - AUGUST 21

- ownership: **unknown** — not in the ledger and not on any operator-declared internal list; UNKNOWN is the state, not a gap
- provider status `FINISHED`; created `2026-08-24T09:23:35.808104Z`; started `2026-08-24T09:37:29.122099Z`
- seats (`campaignAccountIds`): 174892
- lead list `876768` (Bruno approved), list size `totalItemsCount` = 285; campaign holds `progressStats.totalUsers` = 285, finished 276
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **0**, accepted **0** (n/a (denominator 0))
  - messages sent **286**, message threads started **149**, replies **13** (8.72% of threads started)
  - unique leads contacted **149**; profile views 0, follows 0, post likes 0
  - provider's own tags: `autoTaggedInterested` **1**, `totalAutoTagged` **13**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 150 conversations joined, 1 operator-positive replies = **n/a (0 requests sent) per 100 requests sent**
- reply classes in this campaign: `unknown` 9, `negative` 4, `not_relevant` 3, `positive` 1, `automated` 1
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-08-25 .. 2026-09-08 (12 days)
- sequence node types present in the whole graph: CHECK_IS_CONNECTION, END, MESSAGE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CHECK_IS_CONNECTION   wait 0H      day  0.00
  step 1   MESSAGE               wait 0H      day  0.00
  step 2   MESSAGE               wait 5D      day  5.00
  step 3   MESSAGE               wait 5D      day 10.00
  step 4   END                   wait 1D      day 11.00
```

**Connection note:** this graph has no `CONNECTION_REQUEST` node, so no note is sent.

**Message steps — our text, in full:**

- message at day 0.00, 4 variant(s):
  - variant 1 (337 chars, 59 words): `Hi {FIRST_NAME}, we've been connected a while but never actually talked. I'll be direct about why I'm reaching out, I'm on the team at Productive, we help agencies get a live view of project profitability instead of finding out after the invoice's gone out. Think it's relevant for what you do at {COMPANY}. Worth 20 minutes to show you?`
  - variant 2 (327 chars, 55 words): `Hi {FIRST_NAME}, we've been connected a while but I don't think we've ever actually talked. 

I'm on the team at Productive, a platform agencies use to see project profitability live instead of finding out after the invoice's out. Think it's relevant for what you do at {COMPANY}. 

Happy to show you in 20 minutes. Interested?`
  - variant 3 (373 chars, 66 words): `Hey {FIRST_NAME}, we're connected but never got to talk. Reaching out because I think Productive could be relevant for you as a {POSITION}. The pitch: 20 minutes on how agencies get a live view of project profitability instead of finding out after the invoice's out. The deal: no deck, no follow up pressure either way, just a straight look at whether it fits. 

Up for it?`
  - variant 4 (351 chars, 61 words): `Hi {FIRST_NAME}, we've been connected but never actually chatted. I'll be direct about why I'm reaching out. Productive is a platform I think makes sense for {COMPANY}, and I'd love to show you what it does in 20 minutes. And because I know calendars are packed, there's no pitch deck involved, just a straight look at whether it's useful. Sound fair?`
  - fallback (315 chars): `Hi, we've been connected a while but never actually talked. 

I'll be direct about why I'm reaching out, I'm on the team at Productive, we help agencies get a live view of project profitability instead of finding out after the invoice's gone out. Think it's relevant for what you do. 

Worth 20 minutes to show you?`
- message at day 5.00, 3 variant(s):
  - variant 1 (306 chars, 50 words): `Here's the actual reason I think it's worth your time, {FIRST_NAME}. Some agencies are still stitching together budgets, resourcing, and time tracking across separate tools and only find out a project lost money once the invoice's gone out and Productive fixes that. Want to see if it applies to {COMPANY}?`
  - variant 2 (309 chars, 54 words): `{FIRST_NAME}, not sure my last message actually landed, so trying again. No pressure either way on the 20 minutes. The actual value is Productive connecting your project data to the financial side, so your team stops piecing it together after the fact and just sees it live. 

Would you like me to share more?`
  - variant 3 (272 chars, 43 words): `Hi {FIRST_NAME}, one thing I keep hearing from {POSITION} roles in your industry is that profitability visibility is the bottleneck, not because it's complicated, just because the tools haven't caught up. That's exactly what Productive is built for. 

Want to take a look?`
  - fallback (292 chars): `Here's the actual reason I think it's worth your time. Some agencies are still stitching together budgets, resourcing, and time tracking across separate tools and only find out a project lost money once the invoice's gone out and Productive fixes that. Want to see if it applies to your team?`
- message at day 10.00, 3 variant(s):
  - variant 1 (75 chars, 16 words): `Should I take this as a no for now, {FIRST_NAME}, or keep it on your radar?`
  - variant 2 (77 chars, 14 words): `Yes to 20 minutes at some point, {FIRST_NAME}, or should I stop reaching out?`
  - variant 3 (67 chars, 12 words): `Still worth 20 minutes, {FIRST_NAME}, or should I leave it for now?`
  - fallback (61 chars): `Should I take this as a no for now, or keep it on your radar?`

### 565195 — PRODUCTIVE - FRAN CONNECTIONS - MARKETING AGENCIES - JELENA - AUGUST 21

- ownership: **unknown** — not in the ledger and not on any operator-declared internal list; UNKNOWN is the state, not a gap
- provider status `FINISHED`; created `2026-08-24T09:24:27.768247Z`; started `2026-08-24T09:37:10.38978Z`
- seats (`campaignAccountIds`): 174797
- lead list `876790` (Fran approved), list size `totalItemsCount` = 185; campaign holds `progressStats.totalUsers` = 185, finished 184
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **0**, accepted **0** (n/a (denominator 0))
  - messages sent **167**, message threads started **89**, replies **10** (11.24% of threads started)
  - unique leads contacted **89**; profile views 0, follows 0, post likes 0
  - provider's own tags: `autoTaggedInterested` **1**, `totalAutoTagged` **10**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 89 conversations joined, 3 operator-positive replies = **n/a (0 requests sent) per 100 requests sent**
- reply classes in this campaign: `not_relevant` 4, `negative` 4, `unknown` 3, `positive` 2, `question` 1, `automated` 1
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-08-24 .. 2026-09-06 (11 days)
- sequence node types present in the whole graph: CHECK_IS_CONNECTION, END, MESSAGE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CHECK_IS_CONNECTION   wait 0H      day  0.00
  step 1   MESSAGE               wait 0H      day  0.00
  step 2   MESSAGE               wait 5D      day  5.00
  step 3   MESSAGE               wait 5D      day 10.00
  step 4   END                   wait 1D      day 11.00
```

**Connection note:** this graph has no `CONNECTION_REQUEST` node, so no note is sent.

**Message steps — our text, in full:**

- message at day 0.00, 4 variant(s):
  - variant 1 (337 chars, 59 words): `Hi {FIRST_NAME}, we've been connected a while but never actually talked. I'll be direct about why I'm reaching out, I'm on the team at Productive, we help agencies get a live view of project profitability instead of finding out after the invoice's gone out. Think it's relevant for what you do at {COMPANY}. Worth 20 minutes to show you?`
  - variant 2 (327 chars, 55 words): `Hi {FIRST_NAME}, we've been connected a while but I don't think we've ever actually talked. 

I'm on the team at Productive, a platform agencies use to see project profitability live instead of finding out after the invoice's out. Think it's relevant for what you do at {COMPANY}. 

Happy to show you in 20 minutes. Interested?`
  - variant 3 (373 chars, 66 words): `Hey {FIRST_NAME}, we're connected but never got to talk. Reaching out because I think Productive could be relevant for you as a {POSITION}. The pitch: 20 minutes on how agencies get a live view of project profitability instead of finding out after the invoice's out. The deal: no deck, no follow up pressure either way, just a straight look at whether it fits. 

Up for it?`
  - variant 4 (351 chars, 61 words): `Hi {FIRST_NAME}, we've been connected but never actually chatted. I'll be direct about why I'm reaching out. Productive is a platform I think makes sense for {COMPANY}, and I'd love to show you what it does in 20 minutes. And because I know calendars are packed, there's no pitch deck involved, just a straight look at whether it's useful. Sound fair?`
  - fallback (315 chars): `Hi, we've been connected a while but never actually talked. 

I'll be direct about why I'm reaching out, I'm on the team at Productive, we help agencies get a live view of project profitability instead of finding out after the invoice's gone out. Think it's relevant for what you do. 

Worth 20 minutes to show you?`
- message at day 5.00, 3 variant(s):
  - variant 1 (306 chars, 50 words): `Here's the actual reason I think it's worth your time, {FIRST_NAME}. Some agencies are still stitching together budgets, resourcing, and time tracking across separate tools and only find out a project lost money once the invoice's gone out and Productive fixes that. Want to see if it applies to {COMPANY}?`
  - variant 2 (309 chars, 54 words): `{FIRST_NAME}, not sure my last message actually landed, so trying again. No pressure either way on the 20 minutes. The actual value is Productive connecting your project data to the financial side, so your team stops piecing it together after the fact and just sees it live. 

Would you like me to share more?`
  - variant 3 (272 chars, 43 words): `Hi {FIRST_NAME}, one thing I keep hearing from {POSITION} roles in your industry is that profitability visibility is the bottleneck, not because it's complicated, just because the tools haven't caught up. That's exactly what Productive is built for. 

Want to take a look?`
  - fallback (292 chars): `Here's the actual reason I think it's worth your time. Some agencies are still stitching together budgets, resourcing, and time tracking across separate tools and only find out a project lost money once the invoice's gone out and Productive fixes that. Want to see if it applies to your team?`
- message at day 10.00, 3 variant(s):
  - variant 1 (75 chars, 16 words): `Should I take this as a no for now, {FIRST_NAME}, or keep it on your radar?`
  - variant 2 (77 chars, 14 words): `Yes to 20 minutes at some point, {FIRST_NAME}, or should I stop reaching out?`
  - variant 3 (67 chars, 12 words): `Still worth 20 minutes, {FIRST_NAME}, or should I leave it for now?`
  - fallback (61 chars): `Should I take this as a no for now, or keep it on your radar?`

### 565196 — PRODUCTIVE - JAKOV CONNECTIONS - MARKETING AGENCIES - JELENA - AUGUST 21

- ownership: **unknown** — not in the ledger and not on any operator-declared internal list; UNKNOWN is the state, not a gap
- provider status `FINISHED`; created `2026-08-24T09:25:18.710805Z`; started `2026-08-24T09:36:46.591776Z`
- seats (`campaignAccountIds`): 174803
- lead list `876802` (Jakov approoved), list size `totalItemsCount` = 180; campaign holds `progressStats.totalUsers` = 180, finished 175
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **0**, accepted **0** (n/a (denominator 0))
  - messages sent **168**, message threads started **86**, replies **5** (5.81% of threads started)
  - unique leads contacted **86**; profile views 0, follows 0, post likes 0
  - provider's own tags: `autoTaggedInterested` **0**, `totalAutoTagged` **6**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 87 conversations joined, 0 operator-positive replies = **n/a (0 requests sent) per 100 requests sent**
- reply classes in this campaign: `unknown` 5, `negative` 2
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-08-29 .. 2026-09-08 (7 days)
- sequence node types present in the whole graph: CHECK_IS_CONNECTION, END, MESSAGE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CHECK_IS_CONNECTION   wait 0H      day  0.00
  step 1   MESSAGE               wait 0H      day  0.00
  step 2   MESSAGE               wait 5D      day  5.00
  step 3   MESSAGE               wait 5D      day 10.00
  step 4   END                   wait 1D      day 11.00
```

**Connection note:** this graph has no `CONNECTION_REQUEST` node, so no note is sent.

**Message steps — our text, in full:**

- message at day 0.00, 4 variant(s):
  - variant 1 (337 chars, 59 words): `Hi {FIRST_NAME}, we've been connected a while but never actually talked. I'll be direct about why I'm reaching out, I'm on the team at Productive, we help agencies get a live view of project profitability instead of finding out after the invoice's gone out. Think it's relevant for what you do at {COMPANY}. Worth 20 minutes to show you?`
  - variant 2 (327 chars, 55 words): `Hi {FIRST_NAME}, we've been connected a while but I don't think we've ever actually talked. 

I'm on the team at Productive, a platform agencies use to see project profitability live instead of finding out after the invoice's out. Think it's relevant for what you do at {COMPANY}. 

Happy to show you in 20 minutes. Interested?`
  - variant 3 (373 chars, 66 words): `Hey {FIRST_NAME}, we're connected but never got to talk. Reaching out because I think Productive could be relevant for you as a {POSITION}. The pitch: 20 minutes on how agencies get a live view of project profitability instead of finding out after the invoice's out. The deal: no deck, no follow up pressure either way, just a straight look at whether it fits. 

Up for it?`
  - variant 4 (351 chars, 61 words): `Hi {FIRST_NAME}, we've been connected but never actually chatted. I'll be direct about why I'm reaching out. Productive is a platform I think makes sense for {COMPANY}, and I'd love to show you what it does in 20 minutes. And because I know calendars are packed, there's no pitch deck involved, just a straight look at whether it's useful. Sound fair?`
  - fallback (315 chars): `Hi, we've been connected a while but never actually talked. 

I'll be direct about why I'm reaching out, I'm on the team at Productive, we help agencies get a live view of project profitability instead of finding out after the invoice's gone out. Think it's relevant for what you do. 

Worth 20 minutes to show you?`
- message at day 5.00, 3 variant(s):
  - variant 1 (306 chars, 50 words): `Here's the actual reason I think it's worth your time, {FIRST_NAME}. Some agencies are still stitching together budgets, resourcing, and time tracking across separate tools and only find out a project lost money once the invoice's gone out and Productive fixes that. Want to see if it applies to {COMPANY}?`
  - variant 2 (309 chars, 54 words): `{FIRST_NAME}, not sure my last message actually landed, so trying again. No pressure either way on the 20 minutes. The actual value is Productive connecting your project data to the financial side, so your team stops piecing it together after the fact and just sees it live. 

Would you like me to share more?`
  - variant 3 (272 chars, 43 words): `Hi {FIRST_NAME}, one thing I keep hearing from {POSITION} roles in your industry is that profitability visibility is the bottleneck, not because it's complicated, just because the tools haven't caught up. That's exactly what Productive is built for. 

Want to take a look?`
  - fallback (292 chars): `Here's the actual reason I think it's worth your time. Some agencies are still stitching together budgets, resourcing, and time tracking across separate tools and only find out a project lost money once the invoice's gone out and Productive fixes that. Want to see if it applies to your team?`
- message at day 10.00, 3 variant(s):
  - variant 1 (75 chars, 16 words): `Should I take this as a no for now, {FIRST_NAME}, or keep it on your radar?`
  - variant 2 (77 chars, 14 words): `Yes to 20 minutes at some point, {FIRST_NAME}, or should I stop reaching out?`
  - variant 3 (67 chars, 12 words): `Still worth 20 minutes, {FIRST_NAME}, or should I leave it for now?`
  - fallback (61 chars): `Should I take this as a no for now, or keep it on your radar?`

### 565198 — PRODUCTIVE - KRESIMIR CONNECTIONS - MARKETING AGENCIES - JELENA - AUGUST 21

- ownership: **unknown** — not in the ledger and not on any operator-declared internal list; UNKNOWN is the state, not a gap
- provider status `FINISHED`; created `2026-08-24T09:26:52.926422Z`; started `2026-08-24T09:32:57.45068Z`
- seats (`campaignAccountIds`): 174748
- lead list `876807` (Kresimir approved), list size `totalItemsCount` = 275; campaign holds `progressStats.totalUsers` = 275, finished 268
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **0**, accepted **0** (n/a (denominator 0))
  - messages sent **272**, message threads started **140**, replies **5** (3.57% of threads started)
  - unique leads contacted **140**; profile views 0, follows 0, post likes 0
  - provider's own tags: `autoTaggedInterested` **0**, `totalAutoTagged` **5**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 146 conversations joined, 0 operator-positive replies = **n/a (0 requests sent) per 100 requests sent**
- reply classes in this campaign: `negative` 3, `unknown` 2, `not_relevant` 1
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-08-24 .. 2026-09-02 (7 days)
- sequence node types present in the whole graph: CHECK_IS_CONNECTION, END, MESSAGE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CHECK_IS_CONNECTION   wait 0H      day  0.00
  step 1   MESSAGE               wait 0H      day  0.00
  step 2   MESSAGE               wait 5D      day  5.00
  step 3   MESSAGE               wait 1D      day  6.00
  step 4   END                   wait 1D      day  7.00
```

**Connection note:** this graph has no `CONNECTION_REQUEST` node, so no note is sent.

**Message steps — our text, in full:**

- message at day 0.00, 4 variant(s):
  - variant 1 (337 chars, 59 words): `Hi {FIRST_NAME}, we've been connected a while but never actually talked. I'll be direct about why I'm reaching out, I'm on the team at Productive, we help agencies get a live view of project profitability instead of finding out after the invoice's gone out. Think it's relevant for what you do at {COMPANY}. Worth 20 minutes to show you?`
  - variant 2 (327 chars, 55 words): `Hi {FIRST_NAME}, we've been connected a while but I don't think we've ever actually talked. 

I'm on the team at Productive, a platform agencies use to see project profitability live instead of finding out after the invoice's out. Think it's relevant for what you do at {COMPANY}. 

Happy to show you in 20 minutes. Interested?`
  - variant 3 (373 chars, 66 words): `Hey {FIRST_NAME}, we're connected but never got to talk. Reaching out because I think Productive could be relevant for you as a {POSITION}. The pitch: 20 minutes on how agencies get a live view of project profitability instead of finding out after the invoice's out. The deal: no deck, no follow up pressure either way, just a straight look at whether it fits. 

Up for it?`
  - variant 4 (351 chars, 61 words): `Hi {FIRST_NAME}, we've been connected but never actually chatted. I'll be direct about why I'm reaching out. Productive is a platform I think makes sense for {COMPANY}, and I'd love to show you what it does in 20 minutes. And because I know calendars are packed, there's no pitch deck involved, just a straight look at whether it's useful. Sound fair?`
  - fallback (315 chars): `Hi, we've been connected a while but never actually talked. 

I'll be direct about why I'm reaching out, I'm on the team at Productive, we help agencies get a live view of project profitability instead of finding out after the invoice's gone out. Think it's relevant for what you do. 

Worth 20 minutes to show you?`
- message at day 5.00, 3 variant(s):
  - variant 1 (306 chars, 50 words): `Here's the actual reason I think it's worth your time, {FIRST_NAME}. Some agencies are still stitching together budgets, resourcing, and time tracking across separate tools and only find out a project lost money once the invoice's gone out and Productive fixes that. Want to see if it applies to {COMPANY}?`
  - variant 2 (309 chars, 54 words): `{FIRST_NAME}, not sure my last message actually landed, so trying again. No pressure either way on the 20 minutes. The actual value is Productive connecting your project data to the financial side, so your team stops piecing it together after the fact and just sees it live. 

Would you like me to share more?`
  - variant 3 (272 chars, 43 words): `Hi {FIRST_NAME}, one thing I keep hearing from {POSITION} roles in your industry is that profitability visibility is the bottleneck, not because it's complicated, just because the tools haven't caught up. That's exactly what Productive is built for. 

Want to take a look?`
  - fallback (292 chars): `Here's the actual reason I think it's worth your time. Some agencies are still stitching together budgets, resourcing, and time tracking across separate tools and only find out a project lost money once the invoice's gone out and Productive fixes that. Want to see if it applies to your team?`
- message at day 6.00, 3 variant(s):
  - variant 1 (75 chars, 16 words): `Should I take this as a no for now, {FIRST_NAME}, or keep it on your radar?`
  - variant 2 (77 chars, 14 words): `Yes to 20 minutes at some point, {FIRST_NAME}, or should I stop reaching out?`
  - variant 3 (67 chars, 12 words): `Still worth 20 minutes, {FIRST_NAME}, or should I leave it for now?`
  - fallback (61 chars): `Should I take this as a no for now, or keep it on your radar?`

### 565211 — PRODUCTIVE - LUKA CONNECTIONS - MARKETING AGENCIES - JELENA - AUGUST 21

- ownership: **unknown** — not in the ledger and not on any operator-declared internal list; UNKNOWN is the state, not a gap
- provider status `FINISHED`; created `2026-08-24T09:27:42.623962Z`; started `2026-08-24T09:31:56.85896Z`
- seats (`campaignAccountIds`): 175455
- lead list `876826` (Luka C approved), list size `totalItemsCount` = 278; campaign holds `progressStats.totalUsers` = 278, finished 273
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **0**, accepted **0** (n/a (denominator 0))
  - messages sent **293**, message threads started **151**, replies **14** (9.27% of threads started)
  - unique leads contacted **151**; profile views 0, follows 0, post likes 0
  - provider's own tags: `autoTaggedInterested` **1**, `totalAutoTagged` **14**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 155 conversations joined, 2 operator-positive replies = **n/a (0 requests sent) per 100 requests sent**
- reply classes in this campaign: `unknown` 9, `negative` 7, `positive` 2, `automated` 1, `not_now` 1
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-08-24 .. 2026-09-15 (11 days)
- sequence node types present in the whole graph: CHECK_IS_CONNECTION, END, MESSAGE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CHECK_IS_CONNECTION   wait 0H      day  0.00
  step 1   MESSAGE               wait 0H      day  0.00
  step 2   MESSAGE               wait 5D      day  5.00
  step 3   MESSAGE               wait 1D      day  6.00
  step 4   END                   wait 1D      day  7.00
```

**Connection note:** this graph has no `CONNECTION_REQUEST` node, so no note is sent.

**Message steps — our text, in full:**

- message at day 0.00, 4 variant(s):
  - variant 1 (337 chars, 59 words): `Hi {FIRST_NAME}, we've been connected a while but never actually talked. I'll be direct about why I'm reaching out, I'm on the team at Productive, we help agencies get a live view of project profitability instead of finding out after the invoice's gone out. Think it's relevant for what you do at {COMPANY}. Worth 20 minutes to show you?`
  - variant 2 (327 chars, 55 words): `Hi {FIRST_NAME}, we've been connected a while but I don't think we've ever actually talked. 

I'm on the team at Productive, a platform agencies use to see project profitability live instead of finding out after the invoice's out. Think it's relevant for what you do at {COMPANY}. 

Happy to show you in 20 minutes. Interested?`
  - variant 3 (373 chars, 66 words): `Hey {FIRST_NAME}, we're connected but never got to talk. Reaching out because I think Productive could be relevant for you as a {POSITION}. The pitch: 20 minutes on how agencies get a live view of project profitability instead of finding out after the invoice's out. The deal: no deck, no follow up pressure either way, just a straight look at whether it fits. 

Up for it?`
  - variant 4 (351 chars, 61 words): `Hi {FIRST_NAME}, we've been connected but never actually chatted. I'll be direct about why I'm reaching out. Productive is a platform I think makes sense for {COMPANY}, and I'd love to show you what it does in 20 minutes. And because I know calendars are packed, there's no pitch deck involved, just a straight look at whether it's useful. Sound fair?`
  - fallback (315 chars): `Hi, we've been connected a while but never actually talked. 

I'll be direct about why I'm reaching out, I'm on the team at Productive, we help agencies get a live view of project profitability instead of finding out after the invoice's gone out. Think it's relevant for what you do. 

Worth 20 minutes to show you?`
- message at day 5.00, 3 variant(s):
  - variant 1 (306 chars, 50 words): `Here's the actual reason I think it's worth your time, {FIRST_NAME}. Some agencies are still stitching together budgets, resourcing, and time tracking across separate tools and only find out a project lost money once the invoice's gone out and Productive fixes that. Want to see if it applies to {COMPANY}?`
  - variant 2 (309 chars, 54 words): `{FIRST_NAME}, not sure my last message actually landed, so trying again. No pressure either way on the 20 minutes. The actual value is Productive connecting your project data to the financial side, so your team stops piecing it together after the fact and just sees it live. 

Would you like me to share more?`
  - variant 3 (272 chars, 43 words): `Hi {FIRST_NAME}, one thing I keep hearing from {POSITION} roles in your industry is that profitability visibility is the bottleneck, not because it's complicated, just because the tools haven't caught up. That's exactly what Productive is built for. 

Want to take a look?`
  - fallback (292 chars): `Here's the actual reason I think it's worth your time. Some agencies are still stitching together budgets, resourcing, and time tracking across separate tools and only find out a project lost money once the invoice's gone out and Productive fixes that. Want to see if it applies to your team?`
- message at day 6.00, 3 variant(s):
  - variant 1 (75 chars, 16 words): `Should I take this as a no for now, {FIRST_NAME}, or keep it on your radar?`
  - variant 2 (77 chars, 14 words): `Yes to 20 minutes at some point, {FIRST_NAME}, or should I stop reaching out?`
  - variant 3 (67 chars, 12 words): `Still worth 20 minutes, {FIRST_NAME}, or should I leave it for now?`
  - fallback (61 chars): `Should I take this as a no for now, or keep it on your radar?`

### 565223 — PRODUCTIVE - MARKO CONNECTIONS - MARKETING AGENCIES - JELENA - AUGUST 21

- ownership: **unknown** — not in the ledger and not on any operator-declared internal list; UNKNOWN is the state, not a gap
- provider status `FINISHED`; created `2026-08-24T09:28:31.829827Z`; started `2026-08-24T09:30:25.771255Z`
- seats (`campaignAccountIds`): 174822
- lead list `876837` (Marko C approved), list size `totalItemsCount` = 256; campaign holds `progressStats.totalUsers` = 256, finished 250
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **0**, accepted **0** (n/a (denominator 0))
  - messages sent **245**, message threads started **127**, replies **15** (11.81% of threads started)
  - unique leads contacted **127**; profile views 0, follows 0, post likes 0
  - provider's own tags: `autoTaggedInterested` **1**, `totalAutoTagged` **15**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 127 conversations joined, 1 operator-positive replies = **n/a (0 requests sent) per 100 requests sent**
- reply classes in this campaign: `unknown` 10, `negative` 4, `automated` 2, `not_relevant` 2, `positive` 1, `unsubscribe` 1
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-08-25 .. 2026-09-11 (14 days)
- sequence node types present in the whole graph: CHECK_IS_CONNECTION, END, MESSAGE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CHECK_IS_CONNECTION   wait 0H      day  0.00
  step 1   MESSAGE               wait 0H      day  0.00
  step 2   MESSAGE               wait 5D      day  5.00
  step 3   MESSAGE               wait 5D      day 10.00
  step 4   END                   wait 1D      day 11.00
```

**Connection note:** this graph has no `CONNECTION_REQUEST` node, so no note is sent.

**Message steps — our text, in full:**

- message at day 0.00, 4 variant(s):
  - variant 1 (337 chars, 59 words): `Hi {FIRST_NAME}, we've been connected a while but never actually talked. I'll be direct about why I'm reaching out, I'm on the team at Productive, we help agencies get a live view of project profitability instead of finding out after the invoice's gone out. Think it's relevant for what you do at {COMPANY}. Worth 20 minutes to show you?`
  - variant 2 (327 chars, 55 words): `Hi {FIRST_NAME}, we've been connected a while but I don't think we've ever actually talked. 

I'm on the team at Productive, a platform agencies use to see project profitability live instead of finding out after the invoice's out. Think it's relevant for what you do at {COMPANY}. 

Happy to show you in 20 minutes. Interested?`
  - variant 3 (373 chars, 66 words): `Hey {FIRST_NAME}, we're connected but never got to talk. Reaching out because I think Productive could be relevant for you as a {POSITION}. The pitch: 20 minutes on how agencies get a live view of project profitability instead of finding out after the invoice's out. The deal: no deck, no follow up pressure either way, just a straight look at whether it fits. 

Up for it?`
  - variant 4 (351 chars, 61 words): `Hi {FIRST_NAME}, we've been connected but never actually chatted. I'll be direct about why I'm reaching out. Productive is a platform I think makes sense for {COMPANY}, and I'd love to show you what it does in 20 minutes. And because I know calendars are packed, there's no pitch deck involved, just a straight look at whether it's useful. Sound fair?`
  - fallback (315 chars): `Hi, we've been connected a while but never actually talked. 

I'll be direct about why I'm reaching out, I'm on the team at Productive, we help agencies get a live view of project profitability instead of finding out after the invoice's gone out. Think it's relevant for what you do. 

Worth 20 minutes to show you?`
- message at day 5.00, 3 variant(s):
  - variant 1 (306 chars, 50 words): `Here's the actual reason I think it's worth your time, {FIRST_NAME}. Some agencies are still stitching together budgets, resourcing, and time tracking across separate tools and only find out a project lost money once the invoice's gone out and Productive fixes that. Want to see if it applies to {COMPANY}?`
  - variant 2 (309 chars, 54 words): `{FIRST_NAME}, not sure my last message actually landed, so trying again. No pressure either way on the 20 minutes. The actual value is Productive connecting your project data to the financial side, so your team stops piecing it together after the fact and just sees it live. 

Would you like me to share more?`
  - variant 3 (272 chars, 43 words): `Hi {FIRST_NAME}, one thing I keep hearing from {POSITION} roles in your industry is that profitability visibility is the bottleneck, not because it's complicated, just because the tools haven't caught up. That's exactly what Productive is built for. 

Want to take a look?`
  - fallback (292 chars): `Here's the actual reason I think it's worth your time. Some agencies are still stitching together budgets, resourcing, and time tracking across separate tools and only find out a project lost money once the invoice's gone out and Productive fixes that. Want to see if it applies to your team?`
- message at day 10.00, 3 variant(s):
  - variant 1 (75 chars, 16 words): `Should I take this as a no for now, {FIRST_NAME}, or keep it on your radar?`
  - variant 2 (77 chars, 14 words): `Yes to 20 minutes at some point, {FIRST_NAME}, or should I stop reaching out?`
  - variant 3 (67 chars, 12 words): `Still worth 20 minutes, {FIRST_NAME}, or should I leave it for now?`
  - fallback (61 chars): `Should I take this as a no for now, or keep it on your radar?`

### 565765 — PRODUCTIVE - SOFTWARE DEVELOPMENT - JELENA - AUGUST 24

- ownership: **unknown** — not in the ledger and not on any operator-declared internal list; UNKNOWN is the state, not a gap
- provider status `IN_PROGRESS`; created `2026-08-24T13:40:00.697129Z`; started `2026-09-02T14:07:05.948471Z`
- seats (`campaignAccountIds`): 212356, 143105, 174892, 175552, 201978, 179527, 159259, 174748, 191848, 175455, 208253, 181658, 174742, 174332, 174810, 174822, 174845, 174803, 208242, 181653, 174797, 201959, 139699, 129082, 125775, 125748, 119588, 116989, 116988, 116973, 116968, 169600, 177751
- lead list `906686` (Software Development - EU - Firstliners, Batch 1), list size `totalItemsCount` = 1000; campaign holds `progressStats.totalUsers` = 1000, finished 151
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **952**, accepted **131** (13.76%)
  - messages sent **231**, message threads started **132**, replies **25** (18.94% of threads started)
  - unique leads contacted **951**; profile views 154, follows 1011, post likes 0
  - provider's own tags: `autoTaggedInterested` **4**, `totalAutoTagged` **25**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 132 conversations joined, 4 operator-positive replies = **0.420 per 100 requests sent**
- reply classes in this campaign: `unknown` 12, `negative` 11, `positive` 4, `automated` 3, `not_now` 1
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-09-02 .. 2026-10-02 (30 days)
- sequence node types present in the whole graph: CHECK_IS_CONNECTION, CONNECTION_REQUEST, END, FOLLOW, MESSAGE, SEND_LEAD_TO_BISON, VIEW_PROFILE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CHECK_IS_CONNECTION   wait 0H      day  0.00
  step 1   MESSAGE               wait 0H      day  0.00
  step 2   MESSAGE               wait 5D      day  5.00
  step 3   MESSAGE               wait 5D      day 10.00
  step 4   SEND_LEAD_TO_BISON    wait 3D      day 13.00
  step 5   END                   wait 0H      day 13.00
```

**Connection note:** 1 `CONNECTION_REQUEST` note slot(s), every one of them EMPTY — this campaign sends connection requests with no note.

**Message steps — our text, in full:**

- message at day 0.00, 3 variant(s):
  - variant 1 (283 chars, 46 words): `Hey {FIRST_NAME},

{Icebreaker}
 
We built Productive so budgets, time tracking and resourcing actually talk to each other, so you can see if a project's making money while it's still running, not just after it gets invoiced.
 
Can show you what that looks like if you're interested.`
  - variant 2 (233 chars, 39 words): `Hi {FIRST_NAME}, {Icebreaker}
 
It's a common one. Productive ties budgets, time and resourcing together so that question has a live answer instead of one you get after the invoice goes out. Can walk you through it if you're curious.`
  - variant 3 (233 chars, 34 words): `Hey {FIRST_NAME},
 
{Icebreaker}
 
That's basically why we built Productive, so budgets, time tracking and resourcing stop living in separate places and you can see project profitability while it's still happening. Happy to show you.`
  - fallback (256 chars): `Hey, we built Productive so budgets, time tracking and resourcing actually talk to each other, so you can see if a project's making money while it's still running, not just after it gets invoiced.
 
Can show you what that looks like if you're interested.

`
- message at day 5.00, 2 variant(s):
  - variant 1 (251 chars, 37 words): `{FIRST_NAME}, random one, but Infinum (software agency, 370+ people) uses Productive to plan resourcing across the whole team without losing sight of which projects are actually profitable.
 
Would something like this make sense for {COMPANY} as well?`
  - variant 2 (253 chars, 41 words): `{FIRST_NAME}, Akcelo (190 people, works with McDonald's and Netflix) uses Productive to stay on top of budgets and reporting across every project. PIABO runs basically the same setup across five offices in Europe. Could it be worth a look for {COMPANY}?`
  - fallback (237 chars): `Random one, but Infinum (software agency, 370+ people) uses Productive to plan resourcing across the whole team without losing sight of which projects are actually profitable.
 
Would something like this make sense for your team as well?`
- message at day 10.00, 4 variant(s):
  - variant 1 (83 chars, 17 words): `{FIRST_NAME}, worth a yes or no on this one so I know whether to stop reaching out?`
  - variant 2 (84 chars, 17 words): `{FIRST_NAME}, should I drop this or send you an overview if you want to take a look?`
  - variant 3 (51 chars, 9 words): `Worth a look, {FIRST_NAME}? I can send an overview.`
  - variant 4 (59 chars, 10 words): `Is this worth pursuing or should I stop here, {FIRST_NAME}?`
  - fallback (69 chars): `Worth a yes or no on this one so I know whether to stop reaching out?`

### 567677 — PRODUCTIVE - VLADIMIR H CONNECTIONS - MARKETING AGENCIES - JELENA - AUGUST 21

- ownership: **unknown** — not in the ledger and not on any operator-declared internal list; UNKNOWN is the state, not a gap
- provider status `FINISHED`; created `2026-08-25T12:03:35.860473Z`; started `2026-08-25T12:04:14.222203Z`
- seats (`campaignAccountIds`): 159259
- lead list `885884` (Vladimir H approved), list size `totalItemsCount` = 13; campaign holds `progressStats.totalUsers` = 13, finished 13
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **0**, accepted **0** (n/a (denominator 0))
  - messages sent **26**, message threads started **13**, replies **0** (0.00% of threads started)
  - unique leads contacted **13**; profile views 0, follows 0, post likes 0
  - provider's own tags: `autoTaggedInterested` **0**, `totalAutoTagged` **0**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 13 conversations joined, 0 operator-positive replies = **n/a (0 requests sent) per 100 requests sent**
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-08-30 .. 2026-09-04 (2 days)
- sequence node types present in the whole graph: CHECK_IS_CONNECTION, END, MESSAGE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CHECK_IS_CONNECTION   wait 0H      day  0.00
  step 1   MESSAGE               wait 0H      day  0.00
  step 2   MESSAGE               wait 5D      day  5.00
  step 3   MESSAGE               wait 5D      day 10.00
  step 4   END                   wait 1D      day 11.00
```

**Connection note:** this graph has no `CONNECTION_REQUEST` node, so no note is sent.

**Message steps — our text, in full:**

- message at day 0.00, 4 variant(s):
  - variant 1 (337 chars, 59 words): `Hi {FIRST_NAME}, we've been connected a while but never actually talked. I'll be direct about why I'm reaching out, I'm on the team at Productive, we help agencies get a live view of project profitability instead of finding out after the invoice's gone out. Think it's relevant for what you do at {COMPANY}. Worth 20 minutes to show you?`
  - variant 2 (327 chars, 55 words): `Hi {FIRST_NAME}, we've been connected a while but I don't think we've ever actually talked. 

I'm on the team at Productive, a platform agencies use to see project profitability live instead of finding out after the invoice's out. Think it's relevant for what you do at {COMPANY}. 

Happy to show you in 20 minutes. Interested?`
  - variant 3 (373 chars, 66 words): `Hey {FIRST_NAME}, we're connected but never got to talk. Reaching out because I think Productive could be relevant for you as a {POSITION}. The pitch: 20 minutes on how agencies get a live view of project profitability instead of finding out after the invoice's out. The deal: no deck, no follow up pressure either way, just a straight look at whether it fits. 

Up for it?`
  - variant 4 (351 chars, 61 words): `Hi {FIRST_NAME}, we've been connected but never actually chatted. I'll be direct about why I'm reaching out. Productive is a platform I think makes sense for {COMPANY}, and I'd love to show you what it does in 20 minutes. And because I know calendars are packed, there's no pitch deck involved, just a straight look at whether it's useful. Sound fair?`
  - fallback (315 chars): `Hi, we've been connected a while but never actually talked. 

I'll be direct about why I'm reaching out, I'm on the team at Productive, we help agencies get a live view of project profitability instead of finding out after the invoice's gone out. Think it's relevant for what you do. 

Worth 20 minutes to show you?`
- message at day 5.00, 3 variant(s):
  - variant 1 (306 chars, 50 words): `Here's the actual reason I think it's worth your time, {FIRST_NAME}. Some agencies are still stitching together budgets, resourcing, and time tracking across separate tools and only find out a project lost money once the invoice's gone out and Productive fixes that. Want to see if it applies to {COMPANY}?`
  - variant 2 (309 chars, 54 words): `{FIRST_NAME}, not sure my last message actually landed, so trying again. No pressure either way on the 20 minutes. The actual value is Productive connecting your project data to the financial side, so your team stops piecing it together after the fact and just sees it live. 

Would you like me to share more?`
  - variant 3 (272 chars, 43 words): `Hi {FIRST_NAME}, one thing I keep hearing from {POSITION} roles in your industry is that profitability visibility is the bottleneck, not because it's complicated, just because the tools haven't caught up. That's exactly what Productive is built for. 

Want to take a look?`
  - fallback (292 chars): `Here's the actual reason I think it's worth your time. Some agencies are still stitching together budgets, resourcing, and time tracking across separate tools and only find out a project lost money once the invoice's gone out and Productive fixes that. Want to see if it applies to your team?`
- message at day 10.00, 3 variant(s):
  - variant 1 (75 chars, 16 words): `Should I take this as a no for now, {FIRST_NAME}, or keep it on your radar?`
  - variant 2 (77 chars, 14 words): `Yes to 20 minutes at some point, {FIRST_NAME}, or should I stop reaching out?`
  - variant 3 (67 chars, 12 words): `Still worth 20 minutes, {FIRST_NAME}, or should I leave it for now?`
  - fallback (61 chars): `Should I take this as a no for now, or keep it on your radar?`

### 567681 — PRODUCTIVE - SNJEZANA M CONNECTIONS - MARKETING AGENCIES - JELENA - AUGUST 21

- ownership: **unknown** — not in the ledger and not on any operator-declared internal list; UNKNOWN is the state, not a gap
- provider status `FINISHED`; created `2026-08-25T12:05:02.308973Z`; started `2026-08-25T12:05:24.510581Z`
- seats (`campaignAccountIds`): 201959
- lead list `885894` (Snjezana M approved), list size `totalItemsCount` = 2; campaign holds `progressStats.totalUsers` = 2, finished 2
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **0**, accepted **0** (n/a (denominator 0))
  - messages sent **4**, message threads started **2**, replies **0** (0.00% of threads started)
  - unique leads contacted **2**; profile views 0, follows 0, post likes 0
  - provider's own tags: `autoTaggedInterested` **0**, `totalAutoTagged` **0**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 2 conversations joined, 0 operator-positive replies = **n/a (0 requests sent) per 100 requests sent**
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-08-30 .. 2026-09-04 (2 days)
- sequence node types present in the whole graph: CHECK_IS_CONNECTION, END, MESSAGE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CHECK_IS_CONNECTION   wait 0H      day  0.00
  step 1   MESSAGE               wait 0H      day  0.00
  step 2   MESSAGE               wait 5D      day  5.00
  step 3   MESSAGE               wait 5D      day 10.00
  step 4   END                   wait 1D      day 11.00
```

**Connection note:** this graph has no `CONNECTION_REQUEST` node, so no note is sent.

**Message steps — our text, in full:**

- message at day 0.00, 4 variant(s):
  - variant 1 (337 chars, 59 words): `Hi {FIRST_NAME}, we've been connected a while but never actually talked. I'll be direct about why I'm reaching out, I'm on the team at Productive, we help agencies get a live view of project profitability instead of finding out after the invoice's gone out. Think it's relevant for what you do at {COMPANY}. Worth 20 minutes to show you?`
  - variant 2 (327 chars, 55 words): `Hi {FIRST_NAME}, we've been connected a while but I don't think we've ever actually talked. 

I'm on the team at Productive, a platform agencies use to see project profitability live instead of finding out after the invoice's out. Think it's relevant for what you do at {COMPANY}. 

Happy to show you in 20 minutes. Interested?`
  - variant 3 (373 chars, 66 words): `Hey {FIRST_NAME}, we're connected but never got to talk. Reaching out because I think Productive could be relevant for you as a {POSITION}. The pitch: 20 minutes on how agencies get a live view of project profitability instead of finding out after the invoice's out. The deal: no deck, no follow up pressure either way, just a straight look at whether it fits. 

Up for it?`
  - variant 4 (351 chars, 61 words): `Hi {FIRST_NAME}, we've been connected but never actually chatted. I'll be direct about why I'm reaching out. Productive is a platform I think makes sense for {COMPANY}, and I'd love to show you what it does in 20 minutes. And because I know calendars are packed, there's no pitch deck involved, just a straight look at whether it's useful. Sound fair?`
  - fallback (315 chars): `Hi, we've been connected a while but never actually talked. 

I'll be direct about why I'm reaching out, I'm on the team at Productive, we help agencies get a live view of project profitability instead of finding out after the invoice's gone out. Think it's relevant for what you do. 

Worth 20 minutes to show you?`
- message at day 5.00, 3 variant(s):
  - variant 1 (306 chars, 50 words): `Here's the actual reason I think it's worth your time, {FIRST_NAME}. Some agencies are still stitching together budgets, resourcing, and time tracking across separate tools and only find out a project lost money once the invoice's gone out and Productive fixes that. Want to see if it applies to {COMPANY}?`
  - variant 2 (309 chars, 54 words): `{FIRST_NAME}, not sure my last message actually landed, so trying again. No pressure either way on the 20 minutes. The actual value is Productive connecting your project data to the financial side, so your team stops piecing it together after the fact and just sees it live. 

Would you like me to share more?`
  - variant 3 (272 chars, 43 words): `Hi {FIRST_NAME}, one thing I keep hearing from {POSITION} roles in your industry is that profitability visibility is the bottleneck, not because it's complicated, just because the tools haven't caught up. That's exactly what Productive is built for. 

Want to take a look?`
  - fallback (292 chars): `Here's the actual reason I think it's worth your time. Some agencies are still stitching together budgets, resourcing, and time tracking across separate tools and only find out a project lost money once the invoice's gone out and Productive fixes that. Want to see if it applies to your team?`
- message at day 10.00, 3 variant(s):
  - variant 1 (75 chars, 16 words): `Should I take this as a no for now, {FIRST_NAME}, or keep it on your radar?`
  - variant 2 (77 chars, 14 words): `Yes to 20 minutes at some point, {FIRST_NAME}, or should I stop reaching out?`
  - variant 3 (67 chars, 12 words): `Still worth 20 minutes, {FIRST_NAME}, or should I leave it for now?`
  - fallback (61 chars): `Should I take this as a no for now, or keep it on your radar?`

### 567683 — PRODUCTIVE - MINA R CONNECTIONS - MARKETING AGENCIES - JELENA - AUGUST 21

- ownership: **unknown** — not in the ledger and not on any operator-declared internal list; UNKNOWN is the state, not a gap
- provider status `FINISHED`; created `2026-08-25T12:05:46.30569Z`; started `2026-08-25T12:06:06.059218Z`
- seats (`campaignAccountIds`): 116968
- lead list `885896` (Mina r approved), list size `totalItemsCount` = 16; campaign holds `progressStats.totalUsers` = 16, finished 16
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **0**, accepted **0** (n/a (denominator 0))
  - messages sent **31**, message threads started **16**, replies **1** (6.25% of threads started)
  - unique leads contacted **16**; profile views 0, follows 0, post likes 0
  - provider's own tags: `autoTaggedInterested` **0**, `totalAutoTagged` **1**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 16 conversations joined, 0 operator-positive replies = **n/a (0 requests sent) per 100 requests sent**
- reply classes in this campaign: `unknown` 1
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-08-30 .. 2026-09-04 (3 days)
- sequence node types present in the whole graph: CHECK_IS_CONNECTION, END, MESSAGE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CHECK_IS_CONNECTION   wait 0H      day  0.00
  step 1   MESSAGE               wait 0H      day  0.00
  step 2   MESSAGE               wait 5D      day  5.00
  step 3   MESSAGE               wait 5D      day 10.00
  step 4   END                   wait 1D      day 11.00
```

**Connection note:** this graph has no `CONNECTION_REQUEST` node, so no note is sent.

**Message steps — our text, in full:**

- message at day 0.00, 4 variant(s):
  - variant 1 (337 chars, 59 words): `Hi {FIRST_NAME}, we've been connected a while but never actually talked. I'll be direct about why I'm reaching out, I'm on the team at Productive, we help agencies get a live view of project profitability instead of finding out after the invoice's gone out. Think it's relevant for what you do at {COMPANY}. Worth 20 minutes to show you?`
  - variant 2 (327 chars, 55 words): `Hi {FIRST_NAME}, we've been connected a while but I don't think we've ever actually talked. 

I'm on the team at Productive, a platform agencies use to see project profitability live instead of finding out after the invoice's out. Think it's relevant for what you do at {COMPANY}. 

Happy to show you in 20 minutes. Interested?`
  - variant 3 (373 chars, 66 words): `Hey {FIRST_NAME}, we're connected but never got to talk. Reaching out because I think Productive could be relevant for you as a {POSITION}. The pitch: 20 minutes on how agencies get a live view of project profitability instead of finding out after the invoice's out. The deal: no deck, no follow up pressure either way, just a straight look at whether it fits. 

Up for it?`
  - variant 4 (351 chars, 61 words): `Hi {FIRST_NAME}, we've been connected but never actually chatted. I'll be direct about why I'm reaching out. Productive is a platform I think makes sense for {COMPANY}, and I'd love to show you what it does in 20 minutes. And because I know calendars are packed, there's no pitch deck involved, just a straight look at whether it's useful. Sound fair?`
  - fallback (315 chars): `Hi, we've been connected a while but never actually talked. 

I'll be direct about why I'm reaching out, I'm on the team at Productive, we help agencies get a live view of project profitability instead of finding out after the invoice's gone out. Think it's relevant for what you do. 

Worth 20 minutes to show you?`
- message at day 5.00, 3 variant(s):
  - variant 1 (306 chars, 50 words): `Here's the actual reason I think it's worth your time, {FIRST_NAME}. Some agencies are still stitching together budgets, resourcing, and time tracking across separate tools and only find out a project lost money once the invoice's gone out and Productive fixes that. Want to see if it applies to {COMPANY}?`
  - variant 2 (309 chars, 54 words): `{FIRST_NAME}, not sure my last message actually landed, so trying again. No pressure either way on the 20 minutes. The actual value is Productive connecting your project data to the financial side, so your team stops piecing it together after the fact and just sees it live. 

Would you like me to share more?`
  - variant 3 (272 chars, 43 words): `Hi {FIRST_NAME}, one thing I keep hearing from {POSITION} roles in your industry is that profitability visibility is the bottleneck, not because it's complicated, just because the tools haven't caught up. That's exactly what Productive is built for. 

Want to take a look?`
  - fallback (292 chars): `Here's the actual reason I think it's worth your time. Some agencies are still stitching together budgets, resourcing, and time tracking across separate tools and only find out a project lost money once the invoice's gone out and Productive fixes that. Want to see if it applies to your team?`
- message at day 10.00, 3 variant(s):
  - variant 1 (75 chars, 16 words): `Should I take this as a no for now, {FIRST_NAME}, or keep it on your radar?`
  - variant 2 (77 chars, 14 words): `Yes to 20 minutes at some point, {FIRST_NAME}, or should I stop reaching out?`
  - variant 3 (67 chars, 12 words): `Still worth 20 minutes, {FIRST_NAME}, or should I leave it for now?`
  - fallback (61 chars): `Should I take this as a no for now, or keep it on your radar?`

### 567689 — PRODUCTIVE - MARTINA H CONNECTIONS - MARKETING AGENCIES - JELENA - AUGUST 21

- ownership: **unknown** — not in the ledger and not on any operator-declared internal list; UNKNOWN is the state, not a gap
- provider status `FINISHED`; created `2026-08-25T12:06:49.998994Z`; started `2026-08-25T12:07:29.4628Z`
- seats (`campaignAccountIds`): 191848
- lead list `885901` (Martina H approved), list size `totalItemsCount` = 28; campaign holds `progressStats.totalUsers` = 28, finished 26
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **0**, accepted **0** (n/a (denominator 0))
  - messages sent **48**, message threads started **27**, replies **3** (11.11% of threads started)
  - unique leads contacted **27**; profile views 0, follows 0, post likes 0
  - provider's own tags: `autoTaggedInterested` **1**, `totalAutoTagged` **3**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 27 conversations joined, 1 operator-positive replies = **n/a (0 requests sent) per 100 requests sent**
- reply classes in this campaign: `unknown` 3, `question` 1
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-08-25 .. 2026-09-04 (3 days)
- sequence node types present in the whole graph: CHECK_IS_CONNECTION, END, MESSAGE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CHECK_IS_CONNECTION   wait 0H      day  0.00
  step 1   MESSAGE               wait 0H      day  0.00
  step 2   MESSAGE               wait 5D      day  5.00
  step 3   MESSAGE               wait 5D      day 10.00
  step 4   END                   wait 1D      day 11.00
```

**Connection note:** this graph has no `CONNECTION_REQUEST` node, so no note is sent.

**Message steps — our text, in full:**

- message at day 0.00, 4 variant(s):
  - variant 1 (337 chars, 59 words): `Hi {FIRST_NAME}, we've been connected a while but never actually talked. I'll be direct about why I'm reaching out, I'm on the team at Productive, we help agencies get a live view of project profitability instead of finding out after the invoice's gone out. Think it's relevant for what you do at {COMPANY}. Worth 20 minutes to show you?`
  - variant 2 (327 chars, 55 words): `Hi {FIRST_NAME}, we've been connected a while but I don't think we've ever actually talked. 

I'm on the team at Productive, a platform agencies use to see project profitability live instead of finding out after the invoice's out. Think it's relevant for what you do at {COMPANY}. 

Happy to show you in 20 minutes. Interested?`
  - variant 3 (373 chars, 66 words): `Hey {FIRST_NAME}, we're connected but never got to talk. Reaching out because I think Productive could be relevant for you as a {POSITION}. The pitch: 20 minutes on how agencies get a live view of project profitability instead of finding out after the invoice's out. The deal: no deck, no follow up pressure either way, just a straight look at whether it fits. 

Up for it?`
  - variant 4 (351 chars, 61 words): `Hi {FIRST_NAME}, we've been connected but never actually chatted. I'll be direct about why I'm reaching out. Productive is a platform I think makes sense for {COMPANY}, and I'd love to show you what it does in 20 minutes. And because I know calendars are packed, there's no pitch deck involved, just a straight look at whether it's useful. Sound fair?`
  - fallback (315 chars): `Hi, we've been connected a while but never actually talked. 

I'll be direct about why I'm reaching out, I'm on the team at Productive, we help agencies get a live view of project profitability instead of finding out after the invoice's gone out. Think it's relevant for what you do. 

Worth 20 minutes to show you?`
- message at day 5.00, 3 variant(s):
  - variant 1 (306 chars, 50 words): `Here's the actual reason I think it's worth your time, {FIRST_NAME}. Some agencies are still stitching together budgets, resourcing, and time tracking across separate tools and only find out a project lost money once the invoice's gone out and Productive fixes that. Want to see if it applies to {COMPANY}?`
  - variant 2 (309 chars, 54 words): `{FIRST_NAME}, not sure my last message actually landed, so trying again. No pressure either way on the 20 minutes. The actual value is Productive connecting your project data to the financial side, so your team stops piecing it together after the fact and just sees it live. 

Would you like me to share more?`
  - variant 3 (272 chars, 43 words): `Hi {FIRST_NAME}, one thing I keep hearing from {POSITION} roles in your industry is that profitability visibility is the bottleneck, not because it's complicated, just because the tools haven't caught up. That's exactly what Productive is built for. 

Want to take a look?`
  - fallback (292 chars): `Here's the actual reason I think it's worth your time. Some agencies are still stitching together budgets, resourcing, and time tracking across separate tools and only find out a project lost money once the invoice's gone out and Productive fixes that. Want to see if it applies to your team?`
- message at day 10.00, 3 variant(s):
  - variant 1 (75 chars, 16 words): `Should I take this as a no for now, {FIRST_NAME}, or keep it on your radar?`
  - variant 2 (77 chars, 14 words): `Yes to 20 minutes at some point, {FIRST_NAME}, or should I stop reaching out?`
  - variant 3 (67 chars, 12 words): `Still worth 20 minutes, {FIRST_NAME}, or should I leave it for now?`
  - fallback (61 chars): `Should I take this as a no for now, or keep it on your radar?`

### 567693 — PRODUCTIVE - MILAN B CONNECTIONS - MARKETING AGENCIES - JELENA - AUGUST 21

- ownership: **unknown** — not in the ledger and not on any operator-declared internal list; UNKNOWN is the state, not a gap
- provider status `FINISHED`; created `2026-08-25T12:08:31.970486Z`; started `2026-08-25T12:09:10.776934Z`
- seats (`campaignAccountIds`): 179527
- lead list `885899` (Milan B approved), list size `totalItemsCount` = 7; campaign holds `progressStats.totalUsers` = 7, finished 7
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **0**, accepted **0** (n/a (denominator 0))
  - messages sent **14**, message threads started **7**, replies **0** (0.00% of threads started)
  - unique leads contacted **7**; profile views 0, follows 0, post likes 0
  - provider's own tags: `autoTaggedInterested` **0**, `totalAutoTagged` **0**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 7 conversations joined, 0 operator-positive replies = **n/a (0 requests sent) per 100 requests sent**
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-08-30 .. 2026-09-04 (2 days)
- sequence node types present in the whole graph: CHECK_IS_CONNECTION, END, MESSAGE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CHECK_IS_CONNECTION   wait 0H      day  0.00
  step 1   MESSAGE               wait 0H      day  0.00
  step 2   MESSAGE               wait 5D      day  5.00
  step 3   MESSAGE               wait 5D      day 10.00
  step 4   END                   wait 1D      day 11.00
```

**Connection note:** this graph has no `CONNECTION_REQUEST` node, so no note is sent.

**Message steps — our text, in full:**

- message at day 0.00, 4 variant(s):
  - variant 1 (337 chars, 59 words): `Hi {FIRST_NAME}, we've been connected a while but never actually talked. I'll be direct about why I'm reaching out, I'm on the team at Productive, we help agencies get a live view of project profitability instead of finding out after the invoice's gone out. Think it's relevant for what you do at {COMPANY}. Worth 20 minutes to show you?`
  - variant 2 (327 chars, 55 words): `Hi {FIRST_NAME}, we've been connected a while but I don't think we've ever actually talked. 

I'm on the team at Productive, a platform agencies use to see project profitability live instead of finding out after the invoice's out. Think it's relevant for what you do at {COMPANY}. 

Happy to show you in 20 minutes. Interested?`
  - variant 3 (373 chars, 66 words): `Hey {FIRST_NAME}, we're connected but never got to talk. Reaching out because I think Productive could be relevant for you as a {POSITION}. The pitch: 20 minutes on how agencies get a live view of project profitability instead of finding out after the invoice's out. The deal: no deck, no follow up pressure either way, just a straight look at whether it fits. 

Up for it?`
  - variant 4 (351 chars, 61 words): `Hi {FIRST_NAME}, we've been connected but never actually chatted. I'll be direct about why I'm reaching out. Productive is a platform I think makes sense for {COMPANY}, and I'd love to show you what it does in 20 minutes. And because I know calendars are packed, there's no pitch deck involved, just a straight look at whether it's useful. Sound fair?`
  - fallback (315 chars): `Hi, we've been connected a while but never actually talked. 

I'll be direct about why I'm reaching out, I'm on the team at Productive, we help agencies get a live view of project profitability instead of finding out after the invoice's gone out. Think it's relevant for what you do. 

Worth 20 minutes to show you?`
- message at day 5.00, 3 variant(s):
  - variant 1 (306 chars, 50 words): `Here's the actual reason I think it's worth your time, {FIRST_NAME}. Some agencies are still stitching together budgets, resourcing, and time tracking across separate tools and only find out a project lost money once the invoice's gone out and Productive fixes that. Want to see if it applies to {COMPANY}?`
  - variant 2 (309 chars, 54 words): `{FIRST_NAME}, not sure my last message actually landed, so trying again. No pressure either way on the 20 minutes. The actual value is Productive connecting your project data to the financial side, so your team stops piecing it together after the fact and just sees it live. 

Would you like me to share more?`
  - variant 3 (272 chars, 43 words): `Hi {FIRST_NAME}, one thing I keep hearing from {POSITION} roles in your industry is that profitability visibility is the bottleneck, not because it's complicated, just because the tools haven't caught up. That's exactly what Productive is built for. 

Want to take a look?`
  - fallback (292 chars): `Here's the actual reason I think it's worth your time. Some agencies are still stitching together budgets, resourcing, and time tracking across separate tools and only find out a project lost money once the invoice's gone out and Productive fixes that. Want to see if it applies to your team?`
- message at day 10.00, 3 variant(s):
  - variant 1 (75 chars, 16 words): `Should I take this as a no for now, {FIRST_NAME}, or keep it on your radar?`
  - variant 2 (77 chars, 14 words): `Yes to 20 minutes at some point, {FIRST_NAME}, or should I stop reaching out?`
  - variant 3 (67 chars, 12 words): `Still worth 20 minutes, {FIRST_NAME}, or should I leave it for now?`
  - fallback (61 chars): `Should I take this as a no for now, or keep it on your radar?`

### 567698 — PRODUCTIVE - MIHOVIL CONNECTIONS - MARKETING AGENCIES - JELENA - AUGUST 21

- ownership: **unknown** — not in the ledger and not on any operator-declared internal list; UNKNOWN is the state, not a gap
- provider status `FINISHED`; created `2026-08-25T12:09:42.950382Z`; started `2026-08-25T12:10:04.969383Z`
- seats (`campaignAccountIds`): 125775
- lead list `885900` (Mihovil approved), list size `totalItemsCount` = 13; campaign holds `progressStats.totalUsers` = 13, finished 13
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **0**, accepted **0** (n/a (denominator 0))
  - messages sent **21**, message threads started **12**, replies **2** (16.67% of threads started)
  - unique leads contacted **12**; profile views 0, follows 0, post likes 0
  - provider's own tags: `autoTaggedInterested` **1**, `totalAutoTagged` **2**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 12 conversations joined, 1 operator-positive replies = **n/a (0 requests sent) per 100 requests sent**
- reply classes in this campaign: `positive` 1, `unknown` 1
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-08-27 .. 2026-09-04 (4 days)
- sequence node types present in the whole graph: CHECK_IS_CONNECTION, END, MESSAGE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CHECK_IS_CONNECTION   wait 0H      day  0.00
  step 1   MESSAGE               wait 0H      day  0.00
  step 2   MESSAGE               wait 5D      day  5.00
  step 3   MESSAGE               wait 5D      day 10.00
  step 4   END                   wait 1D      day 11.00
```

**Connection note:** this graph has no `CONNECTION_REQUEST` node, so no note is sent.

**Message steps — our text, in full:**

- message at day 0.00, 4 variant(s):
  - variant 1 (337 chars, 59 words): `Hi {FIRST_NAME}, we've been connected a while but never actually talked. I'll be direct about why I'm reaching out, I'm on the team at Productive, we help agencies get a live view of project profitability instead of finding out after the invoice's gone out. Think it's relevant for what you do at {COMPANY}. Worth 20 minutes to show you?`
  - variant 2 (327 chars, 55 words): `Hi {FIRST_NAME}, we've been connected a while but I don't think we've ever actually talked. 

I'm on the team at Productive, a platform agencies use to see project profitability live instead of finding out after the invoice's out. Think it's relevant for what you do at {COMPANY}. 

Happy to show you in 20 minutes. Interested?`
  - variant 3 (373 chars, 66 words): `Hey {FIRST_NAME}, we're connected but never got to talk. Reaching out because I think Productive could be relevant for you as a {POSITION}. The pitch: 20 minutes on how agencies get a live view of project profitability instead of finding out after the invoice's out. The deal: no deck, no follow up pressure either way, just a straight look at whether it fits. 

Up for it?`
  - variant 4 (351 chars, 61 words): `Hi {FIRST_NAME}, we've been connected but never actually chatted. I'll be direct about why I'm reaching out. Productive is a platform I think makes sense for {COMPANY}, and I'd love to show you what it does in 20 minutes. And because I know calendars are packed, there's no pitch deck involved, just a straight look at whether it's useful. Sound fair?`
  - fallback (315 chars): `Hi, we've been connected a while but never actually talked. 

I'll be direct about why I'm reaching out, I'm on the team at Productive, we help agencies get a live view of project profitability instead of finding out after the invoice's gone out. Think it's relevant for what you do. 

Worth 20 minutes to show you?`
- message at day 5.00, 3 variant(s):
  - variant 1 (306 chars, 50 words): `Here's the actual reason I think it's worth your time, {FIRST_NAME}. Some agencies are still stitching together budgets, resourcing, and time tracking across separate tools and only find out a project lost money once the invoice's gone out and Productive fixes that. Want to see if it applies to {COMPANY}?`
  - variant 2 (309 chars, 54 words): `{FIRST_NAME}, not sure my last message actually landed, so trying again. No pressure either way on the 20 minutes. The actual value is Productive connecting your project data to the financial side, so your team stops piecing it together after the fact and just sees it live. 

Would you like me to share more?`
  - variant 3 (272 chars, 43 words): `Hi {FIRST_NAME}, one thing I keep hearing from {POSITION} roles in your industry is that profitability visibility is the bottleneck, not because it's complicated, just because the tools haven't caught up. That's exactly what Productive is built for. 

Want to take a look?`
  - fallback (292 chars): `Here's the actual reason I think it's worth your time. Some agencies are still stitching together budgets, resourcing, and time tracking across separate tools and only find out a project lost money once the invoice's gone out and Productive fixes that. Want to see if it applies to your team?`
- message at day 10.00, 3 variant(s):
  - variant 1 (75 chars, 16 words): `Should I take this as a no for now, {FIRST_NAME}, or keep it on your radar?`
  - variant 2 (77 chars, 14 words): `Yes to 20 minutes at some point, {FIRST_NAME}, or should I stop reaching out?`
  - variant 3 (67 chars, 12 words): `Still worth 20 minutes, {FIRST_NAME}, or should I leave it for now?`
  - fallback (61 chars): `Should I take this as a no for now, or keep it on your radar?`

### 567701 — PRODUCTIVE - MARKO D CONNECTIONS - MARKETING AGENCIES - JELENA - AUGUST 21

- ownership: **unknown** — not in the ledger and not on any operator-declared internal list; UNKNOWN is the state, not a gap
- provider status `FINISHED`; created `2026-08-25T12:10:27.592074Z`; started `2026-08-25T12:10:41.316348Z`
- seats (`campaignAccountIds`): 208253
- lead list `885903` (Marko D approved), list size `totalItemsCount` = 21; campaign holds `progressStats.totalUsers` = 21, finished 21
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **0**, accepted **0** (n/a (denominator 0))
  - messages sent **40**, message threads started **21**, replies **1** (4.76% of threads started)
  - unique leads contacted **21**; profile views 0, follows 0, post likes 0
  - provider's own tags: `autoTaggedInterested` **0**, `totalAutoTagged` **1**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 21 conversations joined, 0 operator-positive replies = **n/a (0 requests sent) per 100 requests sent**
- reply classes in this campaign: `negative` 1
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-08-25 .. 2026-09-04 (3 days)
- sequence node types present in the whole graph: CHECK_IS_CONNECTION, END, MESSAGE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CHECK_IS_CONNECTION   wait 0H      day  0.00
  step 1   MESSAGE               wait 0H      day  0.00
  step 2   MESSAGE               wait 5D      day  5.00
  step 3   MESSAGE               wait 5D      day 10.00
  step 4   END                   wait 1D      day 11.00
```

**Connection note:** this graph has no `CONNECTION_REQUEST` node, so no note is sent.

**Message steps — our text, in full:**

- message at day 0.00, 4 variant(s):
  - variant 1 (337 chars, 59 words): `Hi {FIRST_NAME}, we've been connected a while but never actually talked. I'll be direct about why I'm reaching out, I'm on the team at Productive, we help agencies get a live view of project profitability instead of finding out after the invoice's gone out. Think it's relevant for what you do at {COMPANY}. Worth 20 minutes to show you?`
  - variant 2 (327 chars, 55 words): `Hi {FIRST_NAME}, we've been connected a while but I don't think we've ever actually talked. 

I'm on the team at Productive, a platform agencies use to see project profitability live instead of finding out after the invoice's out. Think it's relevant for what you do at {COMPANY}. 

Happy to show you in 20 minutes. Interested?`
  - variant 3 (373 chars, 66 words): `Hey {FIRST_NAME}, we're connected but never got to talk. Reaching out because I think Productive could be relevant for you as a {POSITION}. The pitch: 20 minutes on how agencies get a live view of project profitability instead of finding out after the invoice's out. The deal: no deck, no follow up pressure either way, just a straight look at whether it fits. 

Up for it?`
  - variant 4 (351 chars, 61 words): `Hi {FIRST_NAME}, we've been connected but never actually chatted. I'll be direct about why I'm reaching out. Productive is a platform I think makes sense for {COMPANY}, and I'd love to show you what it does in 20 minutes. And because I know calendars are packed, there's no pitch deck involved, just a straight look at whether it's useful. Sound fair?`
  - fallback (315 chars): `Hi, we've been connected a while but never actually talked. 

I'll be direct about why I'm reaching out, I'm on the team at Productive, we help agencies get a live view of project profitability instead of finding out after the invoice's gone out. Think it's relevant for what you do. 

Worth 20 minutes to show you?`
- message at day 5.00, 3 variant(s):
  - variant 1 (306 chars, 50 words): `Here's the actual reason I think it's worth your time, {FIRST_NAME}. Some agencies are still stitching together budgets, resourcing, and time tracking across separate tools and only find out a project lost money once the invoice's gone out and Productive fixes that. Want to see if it applies to {COMPANY}?`
  - variant 2 (309 chars, 54 words): `{FIRST_NAME}, not sure my last message actually landed, so trying again. No pressure either way on the 20 minutes. The actual value is Productive connecting your project data to the financial side, so your team stops piecing it together after the fact and just sees it live. 

Would you like me to share more?`
  - variant 3 (272 chars, 43 words): `Hi {FIRST_NAME}, one thing I keep hearing from {POSITION} roles in your industry is that profitability visibility is the bottleneck, not because it's complicated, just because the tools haven't caught up. That's exactly what Productive is built for. 

Want to take a look?`
  - fallback (292 chars): `Here's the actual reason I think it's worth your time. Some agencies are still stitching together budgets, resourcing, and time tracking across separate tools and only find out a project lost money once the invoice's gone out and Productive fixes that. Want to see if it applies to your team?`
- message at day 10.00, 3 variant(s):
  - variant 1 (75 chars, 16 words): `Should I take this as a no for now, {FIRST_NAME}, or keep it on your radar?`
  - variant 2 (77 chars, 14 words): `Yes to 20 minutes at some point, {FIRST_NAME}, or should I stop reaching out?`
  - variant 3 (67 chars, 12 words): `Still worth 20 minutes, {FIRST_NAME}, or should I leave it for now?`
  - fallback (61 chars): `Should I take this as a no for now, or keep it on your radar?`

### 567703 — PRODUCTIVE - MARINA I CONNECTIONS - MARKETING AGENCIES - JELENA - AUGUST 21

- ownership: **unknown** — not in the ledger and not on any operator-declared internal list; UNKNOWN is the state, not a gap
- provider status `FINISHED`; created `2026-08-25T12:11:33.908453Z`; started `2026-08-25T12:11:54.521859Z`
- seats (`campaignAccountIds`): 175552
- lead list `885905` (Marina I approved), list size `totalItemsCount` = 19; campaign holds `progressStats.totalUsers` = 19, finished 19
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **0**, accepted **0** (n/a (denominator 0))
  - messages sent **38**, message threads started **19**, replies **0** (0.00% of threads started)
  - unique leads contacted **19**; profile views 0, follows 0, post likes 0
  - provider's own tags: `autoTaggedInterested` **0**, `totalAutoTagged` **0**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 19 conversations joined, 0 operator-positive replies = **n/a (0 requests sent) per 100 requests sent**
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-08-30 .. 2026-09-04 (2 days)
- sequence node types present in the whole graph: CHECK_IS_CONNECTION, END, MESSAGE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CHECK_IS_CONNECTION   wait 0H      day  0.00
  step 1   MESSAGE               wait 0H      day  0.00
  step 2   MESSAGE               wait 5D      day  5.00
  step 3   MESSAGE               wait 5D      day 10.00
  step 4   END                   wait 1D      day 11.00
```

**Connection note:** this graph has no `CONNECTION_REQUEST` node, so no note is sent.

**Message steps — our text, in full:**

- message at day 0.00, 4 variant(s):
  - variant 1 (337 chars, 59 words): `Hi {FIRST_NAME}, we've been connected a while but never actually talked. I'll be direct about why I'm reaching out, I'm on the team at Productive, we help agencies get a live view of project profitability instead of finding out after the invoice's gone out. Think it's relevant for what you do at {COMPANY}. Worth 20 minutes to show you?`
  - variant 2 (327 chars, 55 words): `Hi {FIRST_NAME}, we've been connected a while but I don't think we've ever actually talked. 

I'm on the team at Productive, a platform agencies use to see project profitability live instead of finding out after the invoice's out. Think it's relevant for what you do at {COMPANY}. 

Happy to show you in 20 minutes. Interested?`
  - variant 3 (373 chars, 66 words): `Hey {FIRST_NAME}, we're connected but never got to talk. Reaching out because I think Productive could be relevant for you as a {POSITION}. The pitch: 20 minutes on how agencies get a live view of project profitability instead of finding out after the invoice's out. The deal: no deck, no follow up pressure either way, just a straight look at whether it fits. 

Up for it?`
  - variant 4 (351 chars, 61 words): `Hi {FIRST_NAME}, we've been connected but never actually chatted. I'll be direct about why I'm reaching out. Productive is a platform I think makes sense for {COMPANY}, and I'd love to show you what it does in 20 minutes. And because I know calendars are packed, there's no pitch deck involved, just a straight look at whether it's useful. Sound fair?`
  - fallback (315 chars): `Hi, we've been connected a while but never actually talked. 

I'll be direct about why I'm reaching out, I'm on the team at Productive, we help agencies get a live view of project profitability instead of finding out after the invoice's gone out. Think it's relevant for what you do. 

Worth 20 minutes to show you?`
- message at day 5.00, 3 variant(s):
  - variant 1 (306 chars, 50 words): `Here's the actual reason I think it's worth your time, {FIRST_NAME}. Some agencies are still stitching together budgets, resourcing, and time tracking across separate tools and only find out a project lost money once the invoice's gone out and Productive fixes that. Want to see if it applies to {COMPANY}?`
  - variant 2 (309 chars, 54 words): `{FIRST_NAME}, not sure my last message actually landed, so trying again. No pressure either way on the 20 minutes. The actual value is Productive connecting your project data to the financial side, so your team stops piecing it together after the fact and just sees it live. 

Would you like me to share more?`
  - variant 3 (272 chars, 43 words): `Hi {FIRST_NAME}, one thing I keep hearing from {POSITION} roles in your industry is that profitability visibility is the bottleneck, not because it's complicated, just because the tools haven't caught up. That's exactly what Productive is built for. 

Want to take a look?`
  - fallback (292 chars): `Here's the actual reason I think it's worth your time. Some agencies are still stitching together budgets, resourcing, and time tracking across separate tools and only find out a project lost money once the invoice's gone out and Productive fixes that. Want to see if it applies to your team?`
- message at day 10.00, 3 variant(s):
  - variant 1 (75 chars, 16 words): `Should I take this as a no for now, {FIRST_NAME}, or keep it on your radar?`
  - variant 2 (77 chars, 14 words): `Yes to 20 minutes at some point, {FIRST_NAME}, or should I stop reaching out?`
  - variant 3 (67 chars, 12 words): `Still worth 20 minutes, {FIRST_NAME}, or should I leave it for now?`
  - fallback (61 chars): `Should I take this as a no for now, or keep it on your radar?`

### 567708 — PRODUCTIVE - LUKA N CONNECTIONS - MARKETING AGENCIES - JELENA - AUGUST 21

- ownership: **unknown** — not in the ledger and not on any operator-declared internal list; UNKNOWN is the state, not a gap
- provider status `FINISHED`; created `2026-08-25T12:12:21.779417Z`; started `2026-08-25T12:12:43.00804Z`
- seats (`campaignAccountIds`): 116973
- lead list `885908` (Luka N approved), list size `totalItemsCount` = 22; campaign holds `progressStats.totalUsers` = 22, finished 22
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **0**, accepted **0** (n/a (denominator 0))
  - messages sent **41**, message threads started **22**, replies **3** (13.64% of threads started)
  - unique leads contacted **22**; profile views 0, follows 0, post likes 0
  - provider's own tags: `autoTaggedInterested` **1**, `totalAutoTagged` **3**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 22 conversations joined, 1 operator-positive replies = **n/a (0 requests sent) per 100 requests sent**
- reply classes in this campaign: `negative` 2, `positive` 1
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-08-25 .. 2026-09-04 (4 days)
- sequence node types present in the whole graph: CHECK_IS_CONNECTION, END, MESSAGE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CHECK_IS_CONNECTION   wait 0H      day  0.00
  step 1   MESSAGE               wait 0H      day  0.00
  step 2   MESSAGE               wait 5D      day  5.00
  step 3   MESSAGE               wait 5D      day 10.00
  step 4   END                   wait 1D      day 11.00
```

**Connection note:** this graph has no `CONNECTION_REQUEST` node, so no note is sent.

**Message steps — our text, in full:**

- message at day 0.00, 4 variant(s):
  - variant 1 (337 chars, 59 words): `Hi {FIRST_NAME}, we've been connected a while but never actually talked. I'll be direct about why I'm reaching out, I'm on the team at Productive, we help agencies get a live view of project profitability instead of finding out after the invoice's gone out. Think it's relevant for what you do at {COMPANY}. Worth 20 minutes to show you?`
  - variant 2 (327 chars, 55 words): `Hi {FIRST_NAME}, we've been connected a while but I don't think we've ever actually talked. 

I'm on the team at Productive, a platform agencies use to see project profitability live instead of finding out after the invoice's out. Think it's relevant for what you do at {COMPANY}. 

Happy to show you in 20 minutes. Interested?`
  - variant 3 (373 chars, 66 words): `Hey {FIRST_NAME}, we're connected but never got to talk. Reaching out because I think Productive could be relevant for you as a {POSITION}. The pitch: 20 minutes on how agencies get a live view of project profitability instead of finding out after the invoice's out. The deal: no deck, no follow up pressure either way, just a straight look at whether it fits. 

Up for it?`
  - variant 4 (351 chars, 61 words): `Hi {FIRST_NAME}, we've been connected but never actually chatted. I'll be direct about why I'm reaching out. Productive is a platform I think makes sense for {COMPANY}, and I'd love to show you what it does in 20 minutes. And because I know calendars are packed, there's no pitch deck involved, just a straight look at whether it's useful. Sound fair?`
  - fallback (315 chars): `Hi, we've been connected a while but never actually talked. 

I'll be direct about why I'm reaching out, I'm on the team at Productive, we help agencies get a live view of project profitability instead of finding out after the invoice's gone out. Think it's relevant for what you do. 

Worth 20 minutes to show you?`
- message at day 5.00, 3 variant(s):
  - variant 1 (306 chars, 50 words): `Here's the actual reason I think it's worth your time, {FIRST_NAME}. Some agencies are still stitching together budgets, resourcing, and time tracking across separate tools and only find out a project lost money once the invoice's gone out and Productive fixes that. Want to see if it applies to {COMPANY}?`
  - variant 2 (309 chars, 54 words): `{FIRST_NAME}, not sure my last message actually landed, so trying again. No pressure either way on the 20 minutes. The actual value is Productive connecting your project data to the financial side, so your team stops piecing it together after the fact and just sees it live. 

Would you like me to share more?`
  - variant 3 (272 chars, 43 words): `Hi {FIRST_NAME}, one thing I keep hearing from {POSITION} roles in your industry is that profitability visibility is the bottleneck, not because it's complicated, just because the tools haven't caught up. That's exactly what Productive is built for. 

Want to take a look?`
  - fallback (292 chars): `Here's the actual reason I think it's worth your time. Some agencies are still stitching together budgets, resourcing, and time tracking across separate tools and only find out a project lost money once the invoice's gone out and Productive fixes that. Want to see if it applies to your team?`
- message at day 10.00, 3 variant(s):
  - variant 1 (75 chars, 16 words): `Should I take this as a no for now, {FIRST_NAME}, or keep it on your radar?`
  - variant 2 (77 chars, 14 words): `Yes to 20 minutes at some point, {FIRST_NAME}, or should I stop reaching out?`
  - variant 3 (67 chars, 12 words): `Still worth 20 minutes, {FIRST_NAME}, or should I leave it for now?`
  - fallback (61 chars): `Should I take this as a no for now, or keep it on your radar?`

### 567715 — PRODUCTIVE - LUCIJA BAKIC CONNECTIONS - MARKETING AGENCIES - JELENA - AUGUST 21

- ownership: **unknown** — not in the ledger and not on any operator-declared internal list; UNKNOWN is the state, not a gap
- provider status `FINISHED`; created `2026-08-25T12:13:56.516995Z`; started `2026-08-25T12:14:21.92417Z`
- seats (`campaignAccountIds`): 208242
- lead list `885914` (Lucija Bakic approved), list size `totalItemsCount` = 23; campaign holds `progressStats.totalUsers` = 23, finished 23
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **0**, accepted **0** (n/a (denominator 0))
  - messages sent **43**, message threads started **23**, replies **4** (17.39% of threads started)
  - unique leads contacted **23**; profile views 0, follows 0, post likes 0
  - provider's own tags: `autoTaggedInterested` **1**, `totalAutoTagged` **4**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 23 conversations joined, 0 operator-positive replies = **n/a (0 requests sent) per 100 requests sent**
- reply classes in this campaign: `unknown` 4, `negative` 1, `not_relevant` 1
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-08-25 .. 2026-09-04 (4 days)
- sequence node types present in the whole graph: CHECK_IS_CONNECTION, END, MESSAGE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CHECK_IS_CONNECTION   wait 0H      day  0.00
  step 1   MESSAGE               wait 0H      day  0.00
  step 2   MESSAGE               wait 5D      day  5.00
  step 3   MESSAGE               wait 5D      day 10.00
  step 4   END                   wait 1D      day 11.00
```

**Connection note:** this graph has no `CONNECTION_REQUEST` node, so no note is sent.

**Message steps — our text, in full:**

- message at day 0.00, 4 variant(s):
  - variant 1 (337 chars, 59 words): `Hi {FIRST_NAME}, we've been connected a while but never actually talked. I'll be direct about why I'm reaching out, I'm on the team at Productive, we help agencies get a live view of project profitability instead of finding out after the invoice's gone out. Think it's relevant for what you do at {COMPANY}. Worth 20 minutes to show you?`
  - variant 2 (327 chars, 55 words): `Hi {FIRST_NAME}, we've been connected a while but I don't think we've ever actually talked. 

I'm on the team at Productive, a platform agencies use to see project profitability live instead of finding out after the invoice's out. Think it's relevant for what you do at {COMPANY}. 

Happy to show you in 20 minutes. Interested?`
  - variant 3 (373 chars, 66 words): `Hey {FIRST_NAME}, we're connected but never got to talk. Reaching out because I think Productive could be relevant for you as a {POSITION}. The pitch: 20 minutes on how agencies get a live view of project profitability instead of finding out after the invoice's out. The deal: no deck, no follow up pressure either way, just a straight look at whether it fits. 

Up for it?`
  - variant 4 (351 chars, 61 words): `Hi {FIRST_NAME}, we've been connected but never actually chatted. I'll be direct about why I'm reaching out. Productive is a platform I think makes sense for {COMPANY}, and I'd love to show you what it does in 20 minutes. And because I know calendars are packed, there's no pitch deck involved, just a straight look at whether it's useful. Sound fair?`
  - fallback (315 chars): `Hi, we've been connected a while but never actually talked. 

I'll be direct about why I'm reaching out, I'm on the team at Productive, we help agencies get a live view of project profitability instead of finding out after the invoice's gone out. Think it's relevant for what you do. 

Worth 20 minutes to show you?`
- message at day 5.00, 3 variant(s):
  - variant 1 (306 chars, 50 words): `Here's the actual reason I think it's worth your time, {FIRST_NAME}. Some agencies are still stitching together budgets, resourcing, and time tracking across separate tools and only find out a project lost money once the invoice's gone out and Productive fixes that. Want to see if it applies to {COMPANY}?`
  - variant 2 (309 chars, 54 words): `{FIRST_NAME}, not sure my last message actually landed, so trying again. No pressure either way on the 20 minutes. The actual value is Productive connecting your project data to the financial side, so your team stops piecing it together after the fact and just sees it live. 

Would you like me to share more?`
  - variant 3 (272 chars, 43 words): `Hi {FIRST_NAME}, one thing I keep hearing from {POSITION} roles in your industry is that profitability visibility is the bottleneck, not because it's complicated, just because the tools haven't caught up. That's exactly what Productive is built for. 

Want to take a look?`
  - fallback (292 chars): `Here's the actual reason I think it's worth your time. Some agencies are still stitching together budgets, resourcing, and time tracking across separate tools and only find out a project lost money once the invoice's gone out and Productive fixes that. Want to see if it applies to your team?`
- message at day 10.00, 3 variant(s):
  - variant 1 (75 chars, 16 words): `Should I take this as a no for now, {FIRST_NAME}, or keep it on your radar?`
  - variant 2 (77 chars, 14 words): `Yes to 20 minutes at some point, {FIRST_NAME}, or should I stop reaching out?`
  - variant 3 (67 chars, 12 words): `Still worth 20 minutes, {FIRST_NAME}, or should I leave it for now?`
  - fallback (61 chars): `Should I take this as a no for now, or keep it on your radar?`

### 567721 — PRODUCTIVE - LUCIJA BILIC CONNECTIONS - MARKETING AGENCIES - JELENA - AUGUST 21

- ownership: **unknown** — not in the ledger and not on any operator-declared internal list; UNKNOWN is the state, not a gap
- provider status `FINISHED`; created `2026-08-25T12:15:04.679588Z`; started `2026-08-25T12:15:25.548665Z`
- seats (`campaignAccountIds`): 125748
- lead list `885917` (Lucija Bilic approved), list size `totalItemsCount` = 16; campaign holds `progressStats.totalUsers` = 16, finished 16
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **0**, accepted **0** (n/a (denominator 0))
  - messages sent **32**, message threads started **16**, replies **0** (0.00% of threads started)
  - unique leads contacted **16**; profile views 0, follows 0, post likes 0
  - provider's own tags: `autoTaggedInterested` **0**, `totalAutoTagged` **0**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 16 conversations joined, 0 operator-positive replies = **n/a (0 requests sent) per 100 requests sent**
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-08-30 .. 2026-09-04 (2 days)
- sequence node types present in the whole graph: CHECK_IS_CONNECTION, END, MESSAGE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CHECK_IS_CONNECTION   wait 0H      day  0.00
  step 1   MESSAGE               wait 0H      day  0.00
  step 2   MESSAGE               wait 5D      day  5.00
  step 3   MESSAGE               wait 5D      day 10.00
  step 4   END                   wait 1D      day 11.00
```

**Connection note:** this graph has no `CONNECTION_REQUEST` node, so no note is sent.

**Message steps — our text, in full:**

- message at day 0.00, 4 variant(s):
  - variant 1 (337 chars, 59 words): `Hi {FIRST_NAME}, we've been connected a while but never actually talked. I'll be direct about why I'm reaching out, I'm on the team at Productive, we help agencies get a live view of project profitability instead of finding out after the invoice's gone out. Think it's relevant for what you do at {COMPANY}. Worth 20 minutes to show you?`
  - variant 2 (327 chars, 55 words): `Hi {FIRST_NAME}, we've been connected a while but I don't think we've ever actually talked. 

I'm on the team at Productive, a platform agencies use to see project profitability live instead of finding out after the invoice's out. Think it's relevant for what you do at {COMPANY}. 

Happy to show you in 20 minutes. Interested?`
  - variant 3 (373 chars, 66 words): `Hey {FIRST_NAME}, we're connected but never got to talk. Reaching out because I think Productive could be relevant for you as a {POSITION}. The pitch: 20 minutes on how agencies get a live view of project profitability instead of finding out after the invoice's out. The deal: no deck, no follow up pressure either way, just a straight look at whether it fits. 

Up for it?`
  - variant 4 (351 chars, 61 words): `Hi {FIRST_NAME}, we've been connected but never actually chatted. I'll be direct about why I'm reaching out. Productive is a platform I think makes sense for {COMPANY}, and I'd love to show you what it does in 20 minutes. And because I know calendars are packed, there's no pitch deck involved, just a straight look at whether it's useful. Sound fair?`
  - fallback (315 chars): `Hi, we've been connected a while but never actually talked. 

I'll be direct about why I'm reaching out, I'm on the team at Productive, we help agencies get a live view of project profitability instead of finding out after the invoice's gone out. Think it's relevant for what you do. 

Worth 20 minutes to show you?`
- message at day 5.00, 3 variant(s):
  - variant 1 (306 chars, 50 words): `Here's the actual reason I think it's worth your time, {FIRST_NAME}. Some agencies are still stitching together budgets, resourcing, and time tracking across separate tools and only find out a project lost money once the invoice's gone out and Productive fixes that. Want to see if it applies to {COMPANY}?`
  - variant 2 (309 chars, 54 words): `{FIRST_NAME}, not sure my last message actually landed, so trying again. No pressure either way on the 20 minutes. The actual value is Productive connecting your project data to the financial side, so your team stops piecing it together after the fact and just sees it live. 

Would you like me to share more?`
  - variant 3 (272 chars, 43 words): `Hi {FIRST_NAME}, one thing I keep hearing from {POSITION} roles in your industry is that profitability visibility is the bottleneck, not because it's complicated, just because the tools haven't caught up. That's exactly what Productive is built for. 

Want to take a look?`
  - fallback (292 chars): `Here's the actual reason I think it's worth your time. Some agencies are still stitching together budgets, resourcing, and time tracking across separate tools and only find out a project lost money once the invoice's gone out and Productive fixes that. Want to see if it applies to your team?`
- message at day 10.00, 3 variant(s):
  - variant 1 (75 chars, 16 words): `Should I take this as a no for now, {FIRST_NAME}, or keep it on your radar?`
  - variant 2 (77 chars, 14 words): `Yes to 20 minutes at some point, {FIRST_NAME}, or should I stop reaching out?`
  - variant 3 (67 chars, 12 words): `Still worth 20 minutes, {FIRST_NAME}, or should I leave it for now?`
  - fallback (61 chars): `Should I take this as a no for now, or keep it on your radar?`

### 567727 — PRODUCTIVE - LAZAR L CONNECTIONS - MARKETING AGENCIES - JELENA - AUGUST 21

- ownership: **unknown** — not in the ledger and not on any operator-declared internal list; UNKNOWN is the state, not a gap
- provider status `FINISHED`; created `2026-08-25T12:16:06.357349Z`; started `2026-08-25T12:16:25.500495Z`
- seats (`campaignAccountIds`): 129082
- lead list `885922` (Lazar L approved), list size `totalItemsCount` = 11; campaign holds `progressStats.totalUsers` = 11, finished 11
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **0**, accepted **0** (n/a (denominator 0))
  - messages sent **22**, message threads started **11**, replies **0** (0.00% of threads started)
  - unique leads contacted **11**; profile views 0, follows 0, post likes 0
  - provider's own tags: `autoTaggedInterested` **0**, `totalAutoTagged` **0**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 11 conversations joined, 0 operator-positive replies = **n/a (0 requests sent) per 100 requests sent**
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-08-30 .. 2026-09-04 (2 days)
- sequence node types present in the whole graph: CHECK_IS_CONNECTION, END, MESSAGE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CHECK_IS_CONNECTION   wait 0H      day  0.00
  step 1   MESSAGE               wait 0H      day  0.00
  step 2   MESSAGE               wait 5D      day  5.00
  step 3   MESSAGE               wait 5D      day 10.00
  step 4   END                   wait 1D      day 11.00
```

**Connection note:** this graph has no `CONNECTION_REQUEST` node, so no note is sent.

**Message steps — our text, in full:**

- message at day 0.00, 4 variant(s):
  - variant 1 (337 chars, 59 words): `Hi {FIRST_NAME}, we've been connected a while but never actually talked. I'll be direct about why I'm reaching out, I'm on the team at Productive, we help agencies get a live view of project profitability instead of finding out after the invoice's gone out. Think it's relevant for what you do at {COMPANY}. Worth 20 minutes to show you?`
  - variant 2 (327 chars, 55 words): `Hi {FIRST_NAME}, we've been connected a while but I don't think we've ever actually talked. 

I'm on the team at Productive, a platform agencies use to see project profitability live instead of finding out after the invoice's out. Think it's relevant for what you do at {COMPANY}. 

Happy to show you in 20 minutes. Interested?`
  - variant 3 (373 chars, 66 words): `Hey {FIRST_NAME}, we're connected but never got to talk. Reaching out because I think Productive could be relevant for you as a {POSITION}. The pitch: 20 minutes on how agencies get a live view of project profitability instead of finding out after the invoice's out. The deal: no deck, no follow up pressure either way, just a straight look at whether it fits. 

Up for it?`
  - variant 4 (351 chars, 61 words): `Hi {FIRST_NAME}, we've been connected but never actually chatted. I'll be direct about why I'm reaching out. Productive is a platform I think makes sense for {COMPANY}, and I'd love to show you what it does in 20 minutes. And because I know calendars are packed, there's no pitch deck involved, just a straight look at whether it's useful. Sound fair?`
  - fallback (315 chars): `Hi, we've been connected a while but never actually talked. 

I'll be direct about why I'm reaching out, I'm on the team at Productive, we help agencies get a live view of project profitability instead of finding out after the invoice's gone out. Think it's relevant for what you do. 

Worth 20 minutes to show you?`
- message at day 5.00, 3 variant(s):
  - variant 1 (306 chars, 50 words): `Here's the actual reason I think it's worth your time, {FIRST_NAME}. Some agencies are still stitching together budgets, resourcing, and time tracking across separate tools and only find out a project lost money once the invoice's gone out and Productive fixes that. Want to see if it applies to {COMPANY}?`
  - variant 2 (309 chars, 54 words): `{FIRST_NAME}, not sure my last message actually landed, so trying again. No pressure either way on the 20 minutes. The actual value is Productive connecting your project data to the financial side, so your team stops piecing it together after the fact and just sees it live. 

Would you like me to share more?`
  - variant 3 (272 chars, 43 words): `Hi {FIRST_NAME}, one thing I keep hearing from {POSITION} roles in your industry is that profitability visibility is the bottleneck, not because it's complicated, just because the tools haven't caught up. That's exactly what Productive is built for. 

Want to take a look?`
  - fallback (292 chars): `Here's the actual reason I think it's worth your time. Some agencies are still stitching together budgets, resourcing, and time tracking across separate tools and only find out a project lost money once the invoice's gone out and Productive fixes that. Want to see if it applies to your team?`
- message at day 10.00, 3 variant(s):
  - variant 1 (75 chars, 16 words): `Should I take this as a no for now, {FIRST_NAME}, or keep it on your radar?`
  - variant 2 (77 chars, 14 words): `Yes to 20 minutes at some point, {FIRST_NAME}, or should I stop reaching out?`
  - variant 3 (67 chars, 12 words): `Still worth 20 minutes, {FIRST_NAME}, or should I leave it for now?`
  - fallback (61 chars): `Should I take this as a no for now, or keep it on your radar?`

### 567730 — PRODUCTIVE - KATARINA K CONNECTIONS - MARKETING AGENCIES - JELENA - AUGUST 21

- ownership: **unknown** — not in the ledger and not on any operator-declared internal list; UNKNOWN is the state, not a gap
- provider status `FINISHED`; created `2026-08-25T12:16:44.553396Z`; started `2026-08-25T12:17:04.132394Z`
- seats (`campaignAccountIds`): 116988
- lead list `885925` (Katarina K approved), list size `totalItemsCount` = 22; campaign holds `progressStats.totalUsers` = 22, finished 22
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **0**, accepted **0** (n/a (denominator 0))
  - messages sent **43**, message threads started **22**, replies **2** (9.09% of threads started)
  - unique leads contacted **22**; profile views 0, follows 0, post likes 0
  - provider's own tags: `autoTaggedInterested` **0**, `totalAutoTagged` **2**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 22 conversations joined, 0 operator-positive replies = **n/a (0 requests sent) per 100 requests sent**
- reply classes in this campaign: `automated` 2, `negative` 1
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-08-30 .. 2026-09-04 (2 days)
- sequence node types present in the whole graph: CHECK_IS_CONNECTION, END, MESSAGE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CHECK_IS_CONNECTION   wait 0H      day  0.00
  step 1   MESSAGE               wait 0H      day  0.00
  step 2   MESSAGE               wait 5D      day  5.00
  step 3   MESSAGE               wait 5D      day 10.00
  step 4   END                   wait 1D      day 11.00
```

**Connection note:** this graph has no `CONNECTION_REQUEST` node, so no note is sent.

**Message steps — our text, in full:**

- message at day 0.00, 4 variant(s):
  - variant 1 (337 chars, 59 words): `Hi {FIRST_NAME}, we've been connected a while but never actually talked. I'll be direct about why I'm reaching out, I'm on the team at Productive, we help agencies get a live view of project profitability instead of finding out after the invoice's gone out. Think it's relevant for what you do at {COMPANY}. Worth 20 minutes to show you?`
  - variant 2 (327 chars, 55 words): `Hi {FIRST_NAME}, we've been connected a while but I don't think we've ever actually talked. 

I'm on the team at Productive, a platform agencies use to see project profitability live instead of finding out after the invoice's out. Think it's relevant for what you do at {COMPANY}. 

Happy to show you in 20 minutes. Interested?`
  - variant 3 (373 chars, 66 words): `Hey {FIRST_NAME}, we're connected but never got to talk. Reaching out because I think Productive could be relevant for you as a {POSITION}. The pitch: 20 minutes on how agencies get a live view of project profitability instead of finding out after the invoice's out. The deal: no deck, no follow up pressure either way, just a straight look at whether it fits. 

Up for it?`
  - variant 4 (351 chars, 61 words): `Hi {FIRST_NAME}, we've been connected but never actually chatted. I'll be direct about why I'm reaching out. Productive is a platform I think makes sense for {COMPANY}, and I'd love to show you what it does in 20 minutes. And because I know calendars are packed, there's no pitch deck involved, just a straight look at whether it's useful. Sound fair?`
  - fallback (315 chars): `Hi, we've been connected a while but never actually talked. 

I'll be direct about why I'm reaching out, I'm on the team at Productive, we help agencies get a live view of project profitability instead of finding out after the invoice's gone out. Think it's relevant for what you do. 

Worth 20 minutes to show you?`
- message at day 5.00, 3 variant(s):
  - variant 1 (306 chars, 50 words): `Here's the actual reason I think it's worth your time, {FIRST_NAME}. Some agencies are still stitching together budgets, resourcing, and time tracking across separate tools and only find out a project lost money once the invoice's gone out and Productive fixes that. Want to see if it applies to {COMPANY}?`
  - variant 2 (309 chars, 54 words): `{FIRST_NAME}, not sure my last message actually landed, so trying again. No pressure either way on the 20 minutes. The actual value is Productive connecting your project data to the financial side, so your team stops piecing it together after the fact and just sees it live. 

Would you like me to share more?`
  - variant 3 (272 chars, 43 words): `Hi {FIRST_NAME}, one thing I keep hearing from {POSITION} roles in your industry is that profitability visibility is the bottleneck, not because it's complicated, just because the tools haven't caught up. That's exactly what Productive is built for. 

Want to take a look?`
  - fallback (292 chars): `Here's the actual reason I think it's worth your time. Some agencies are still stitching together budgets, resourcing, and time tracking across separate tools and only find out a project lost money once the invoice's gone out and Productive fixes that. Want to see if it applies to your team?`
- message at day 10.00, 3 variant(s):
  - variant 1 (75 chars, 16 words): `Should I take this as a no for now, {FIRST_NAME}, or keep it on your radar?`
  - variant 2 (77 chars, 14 words): `Yes to 20 minutes at some point, {FIRST_NAME}, or should I stop reaching out?`
  - variant 3 (67 chars, 12 words): `Still worth 20 minutes, {FIRST_NAME}, or should I leave it for now?`
  - fallback (61 chars): `Should I take this as a no for now, or keep it on your radar?`

### 567733 — PRODUCTIVE - JOVANA K CONNECTIONS - MARKETING AGENCIES - JELENA - AUGUST 21

- ownership: **unknown** — not in the ledger and not on any operator-declared internal list; UNKNOWN is the state, not a gap
- provider status `FINISHED`; created `2026-08-25T12:18:02.450347Z`; started `2026-08-25T12:18:14.454889Z`
- seats (`campaignAccountIds`): 116989
- lead list `885927` (Jovana K approved), list size `totalItemsCount` = 11; campaign holds `progressStats.totalUsers` = 11, finished 11
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **0**, accepted **0** (n/a (denominator 0))
  - messages sent **21**, message threads started **11**, replies **2** (18.18% of threads started)
  - unique leads contacted **11**; profile views 0, follows 0, post likes 0
  - provider's own tags: `autoTaggedInterested` **0**, `totalAutoTagged` **2**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 11 conversations joined, 0 operator-positive replies = **n/a (0 requests sent) per 100 requests sent**
- reply classes in this campaign: `negative` 2
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-08-30 .. 2026-09-10 (3 days)
- sequence node types present in the whole graph: CHECK_IS_CONNECTION, END, MESSAGE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CHECK_IS_CONNECTION   wait 0H      day  0.00
  step 1   MESSAGE               wait 0H      day  0.00
  step 2   MESSAGE               wait 5D      day  5.00
  step 3   MESSAGE               wait 5D      day 10.00
  step 4   END                   wait 1D      day 11.00
```

**Connection note:** this graph has no `CONNECTION_REQUEST` node, so no note is sent.

**Message steps — our text, in full:**

- message at day 0.00, 4 variant(s):
  - variant 1 (337 chars, 59 words): `Hi {FIRST_NAME}, we've been connected a while but never actually talked. I'll be direct about why I'm reaching out, I'm on the team at Productive, we help agencies get a live view of project profitability instead of finding out after the invoice's gone out. Think it's relevant for what you do at {COMPANY}. Worth 20 minutes to show you?`
  - variant 2 (327 chars, 55 words): `Hi {FIRST_NAME}, we've been connected a while but I don't think we've ever actually talked. 

I'm on the team at Productive, a platform agencies use to see project profitability live instead of finding out after the invoice's out. Think it's relevant for what you do at {COMPANY}. 

Happy to show you in 20 minutes. Interested?`
  - variant 3 (373 chars, 66 words): `Hey {FIRST_NAME}, we're connected but never got to talk. Reaching out because I think Productive could be relevant for you as a {POSITION}. The pitch: 20 minutes on how agencies get a live view of project profitability instead of finding out after the invoice's out. The deal: no deck, no follow up pressure either way, just a straight look at whether it fits. 

Up for it?`
  - variant 4 (351 chars, 61 words): `Hi {FIRST_NAME}, we've been connected but never actually chatted. I'll be direct about why I'm reaching out. Productive is a platform I think makes sense for {COMPANY}, and I'd love to show you what it does in 20 minutes. And because I know calendars are packed, there's no pitch deck involved, just a straight look at whether it's useful. Sound fair?`
  - fallback (315 chars): `Hi, we've been connected a while but never actually talked. 

I'll be direct about why I'm reaching out, I'm on the team at Productive, we help agencies get a live view of project profitability instead of finding out after the invoice's gone out. Think it's relevant for what you do. 

Worth 20 minutes to show you?`
- message at day 5.00, 3 variant(s):
  - variant 1 (306 chars, 50 words): `Here's the actual reason I think it's worth your time, {FIRST_NAME}. Some agencies are still stitching together budgets, resourcing, and time tracking across separate tools and only find out a project lost money once the invoice's gone out and Productive fixes that. Want to see if it applies to {COMPANY}?`
  - variant 2 (309 chars, 54 words): `{FIRST_NAME}, not sure my last message actually landed, so trying again. No pressure either way on the 20 minutes. The actual value is Productive connecting your project data to the financial side, so your team stops piecing it together after the fact and just sees it live. 

Would you like me to share more?`
  - variant 3 (272 chars, 43 words): `Hi {FIRST_NAME}, one thing I keep hearing from {POSITION} roles in your industry is that profitability visibility is the bottleneck, not because it's complicated, just because the tools haven't caught up. That's exactly what Productive is built for. 

Want to take a look?`
  - fallback (292 chars): `Here's the actual reason I think it's worth your time. Some agencies are still stitching together budgets, resourcing, and time tracking across separate tools and only find out a project lost money once the invoice's gone out and Productive fixes that. Want to see if it applies to your team?`
- message at day 10.00, 3 variant(s):
  - variant 1 (75 chars, 16 words): `Should I take this as a no for now, {FIRST_NAME}, or keep it on your radar?`
  - variant 2 (77 chars, 14 words): `Yes to 20 minutes at some point, {FIRST_NAME}, or should I stop reaching out?`
  - variant 3 (67 chars, 12 words): `Still worth 20 minutes, {FIRST_NAME}, or should I leave it for now?`
  - fallback (61 chars): `Should I take this as a no for now, or keep it on your radar?`

### 567736 — PRODUCTIVE - JELENA M CONNECTIONS - MARKETING AGENCIES - JELENA - AUGUST 21

- ownership: **unknown** — not in the ledger and not on any operator-declared internal list; UNKNOWN is the state, not a gap
- provider status `FINISHED`; created `2026-08-25T12:18:53.299576Z`; started `2026-08-25T12:19:10.6742Z`
- seats (`campaignAccountIds`): 177751
- lead list `885934` (Jelena M approved), list size `totalItemsCount` = 17; campaign holds `progressStats.totalUsers` = 17, finished 17
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **0**, accepted **0** (n/a (denominator 0))
  - messages sent **24**, message threads started **14**, replies **3** (21.43% of threads started)
  - unique leads contacted **14**; profile views 0, follows 0, post likes 0
  - provider's own tags: `autoTaggedInterested` **0**, `totalAutoTagged` **3**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 14 conversations joined, 0 operator-positive replies = **n/a (0 requests sent) per 100 requests sent**
- reply classes in this campaign: `unknown` 2, `negative` 1
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-08-25 .. 2026-09-04 (3 days)
- sequence node types present in the whole graph: CHECK_IS_CONNECTION, END, MESSAGE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CHECK_IS_CONNECTION   wait 0H      day  0.00
  step 1   MESSAGE               wait 0H      day  0.00
  step 2   MESSAGE               wait 5D      day  5.00
  step 3   MESSAGE               wait 5D      day 10.00
  step 4   END                   wait 1D      day 11.00
```

**Connection note:** this graph has no `CONNECTION_REQUEST` node, so no note is sent.

**Message steps — our text, in full:**

- message at day 0.00, 4 variant(s):
  - variant 1 (337 chars, 59 words): `Hi {FIRST_NAME}, we've been connected a while but never actually talked. I'll be direct about why I'm reaching out, I'm on the team at Productive, we help agencies get a live view of project profitability instead of finding out after the invoice's gone out. Think it's relevant for what you do at {COMPANY}. Worth 20 minutes to show you?`
  - variant 2 (327 chars, 55 words): `Hi {FIRST_NAME}, we've been connected a while but I don't think we've ever actually talked. 

I'm on the team at Productive, a platform agencies use to see project profitability live instead of finding out after the invoice's out. Think it's relevant for what you do at {COMPANY}. 

Happy to show you in 20 minutes. Interested?`
  - variant 3 (373 chars, 66 words): `Hey {FIRST_NAME}, we're connected but never got to talk. Reaching out because I think Productive could be relevant for you as a {POSITION}. The pitch: 20 minutes on how agencies get a live view of project profitability instead of finding out after the invoice's out. The deal: no deck, no follow up pressure either way, just a straight look at whether it fits. 

Up for it?`
  - variant 4 (351 chars, 61 words): `Hi {FIRST_NAME}, we've been connected but never actually chatted. I'll be direct about why I'm reaching out. Productive is a platform I think makes sense for {COMPANY}, and I'd love to show you what it does in 20 minutes. And because I know calendars are packed, there's no pitch deck involved, just a straight look at whether it's useful. Sound fair?`
  - fallback (315 chars): `Hi, we've been connected a while but never actually talked. 

I'll be direct about why I'm reaching out, I'm on the team at Productive, we help agencies get a live view of project profitability instead of finding out after the invoice's gone out. Think it's relevant for what you do. 

Worth 20 minutes to show you?`
- message at day 5.00, 3 variant(s):
  - variant 1 (306 chars, 50 words): `Here's the actual reason I think it's worth your time, {FIRST_NAME}. Some agencies are still stitching together budgets, resourcing, and time tracking across separate tools and only find out a project lost money once the invoice's gone out and Productive fixes that. Want to see if it applies to {COMPANY}?`
  - variant 2 (309 chars, 54 words): `{FIRST_NAME}, not sure my last message actually landed, so trying again. No pressure either way on the 20 minutes. The actual value is Productive connecting your project data to the financial side, so your team stops piecing it together after the fact and just sees it live. 

Would you like me to share more?`
  - variant 3 (272 chars, 43 words): `Hi {FIRST_NAME}, one thing I keep hearing from {POSITION} roles in your industry is that profitability visibility is the bottleneck, not because it's complicated, just because the tools haven't caught up. That's exactly what Productive is built for. 

Want to take a look?`
  - fallback (292 chars): `Here's the actual reason I think it's worth your time. Some agencies are still stitching together budgets, resourcing, and time tracking across separate tools and only find out a project lost money once the invoice's gone out and Productive fixes that. Want to see if it applies to your team?`
- message at day 10.00, 3 variant(s):
  - variant 1 (75 chars, 16 words): `Should I take this as a no for now, {FIRST_NAME}, or keep it on your radar?`
  - variant 2 (77 chars, 14 words): `Yes to 20 minutes at some point, {FIRST_NAME}, or should I stop reaching out?`
  - variant 3 (67 chars, 12 words): `Still worth 20 minutes, {FIRST_NAME}, or should I leave it for now?`
  - fallback (61 chars): `Should I take this as a no for now, or keep it on your radar?`

### 567738 — PRODUCTIVE - JELENA I CONNECTIONS - MARKETING AGENCIES - JELENA - AUGUST 21

- ownership: **unknown** — not in the ledger and not on any operator-declared internal list; UNKNOWN is the state, not a gap
- provider status `FINISHED`; created `2026-08-25T12:19:31.927658Z`; started `2026-08-25T12:19:51.485801Z`
- seats (`campaignAccountIds`): 139699
- lead list `885930` (Jelena I approved), list size `totalItemsCount` = 29; campaign holds `progressStats.totalUsers` = 29, finished 28
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **0**, accepted **0** (n/a (denominator 0))
  - messages sent **52**, message threads started **27**, replies **1** (3.70% of threads started)
  - unique leads contacted **27**; profile views 0, follows 0, post likes 0
  - provider's own tags: `autoTaggedInterested` **0**, `totalAutoTagged` **1**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 27 conversations joined, 0 operator-positive replies = **n/a (0 requests sent) per 100 requests sent**
- reply classes in this campaign: `unknown` 2, `negative` 1
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-08-25 .. 2026-09-04 (3 days)
- sequence node types present in the whole graph: CHECK_IS_CONNECTION, END, MESSAGE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CHECK_IS_CONNECTION   wait 0H      day  0.00
  step 1   MESSAGE               wait 0H      day  0.00
  step 2   MESSAGE               wait 5D      day  5.00
  step 3   MESSAGE               wait 5D      day 10.00
  step 4   END                   wait 1D      day 11.00
```

**Connection note:** this graph has no `CONNECTION_REQUEST` node, so no note is sent.

**Message steps — our text, in full:**

- message at day 0.00, 4 variant(s):
  - variant 1 (337 chars, 59 words): `Hi {FIRST_NAME}, we've been connected a while but never actually talked. I'll be direct about why I'm reaching out, I'm on the team at Productive, we help agencies get a live view of project profitability instead of finding out after the invoice's gone out. Think it's relevant for what you do at {COMPANY}. Worth 20 minutes to show you?`
  - variant 2 (327 chars, 55 words): `Hi {FIRST_NAME}, we've been connected a while but I don't think we've ever actually talked. 

I'm on the team at Productive, a platform agencies use to see project profitability live instead of finding out after the invoice's out. Think it's relevant for what you do at {COMPANY}. 

Happy to show you in 20 minutes. Interested?`
  - variant 3 (373 chars, 66 words): `Hey {FIRST_NAME}, we're connected but never got to talk. Reaching out because I think Productive could be relevant for you as a {POSITION}. The pitch: 20 minutes on how agencies get a live view of project profitability instead of finding out after the invoice's out. The deal: no deck, no follow up pressure either way, just a straight look at whether it fits. 

Up for it?`
  - variant 4 (351 chars, 61 words): `Hi {FIRST_NAME}, we've been connected but never actually chatted. I'll be direct about why I'm reaching out. Productive is a platform I think makes sense for {COMPANY}, and I'd love to show you what it does in 20 minutes. And because I know calendars are packed, there's no pitch deck involved, just a straight look at whether it's useful. Sound fair?`
  - fallback (315 chars): `Hi, we've been connected a while but never actually talked. 

I'll be direct about why I'm reaching out, I'm on the team at Productive, we help agencies get a live view of project profitability instead of finding out after the invoice's gone out. Think it's relevant for what you do. 

Worth 20 minutes to show you?`
- message at day 5.00, 3 variant(s):
  - variant 1 (306 chars, 50 words): `Here's the actual reason I think it's worth your time, {FIRST_NAME}. Some agencies are still stitching together budgets, resourcing, and time tracking across separate tools and only find out a project lost money once the invoice's gone out and Productive fixes that. Want to see if it applies to {COMPANY}?`
  - variant 2 (309 chars, 54 words): `{FIRST_NAME}, not sure my last message actually landed, so trying again. No pressure either way on the 20 minutes. The actual value is Productive connecting your project data to the financial side, so your team stops piecing it together after the fact and just sees it live. 

Would you like me to share more?`
  - variant 3 (272 chars, 43 words): `Hi {FIRST_NAME}, one thing I keep hearing from {POSITION} roles in your industry is that profitability visibility is the bottleneck, not because it's complicated, just because the tools haven't caught up. That's exactly what Productive is built for. 

Want to take a look?`
  - fallback (292 chars): `Here's the actual reason I think it's worth your time. Some agencies are still stitching together budgets, resourcing, and time tracking across separate tools and only find out a project lost money once the invoice's gone out and Productive fixes that. Want to see if it applies to your team?`
- message at day 10.00, 3 variant(s):
  - variant 1 (75 chars, 16 words): `Should I take this as a no for now, {FIRST_NAME}, or keep it on your radar?`
  - variant 2 (77 chars, 14 words): `Yes to 20 minutes at some point, {FIRST_NAME}, or should I stop reaching out?`
  - variant 3 (67 chars, 12 words): `Still worth 20 minutes, {FIRST_NAME}, or should I leave it for now?`
  - fallback (61 chars): `Should I take this as a no for now, or keep it on your radar?`

### 567743 — PRODUCTIVE - IVAN M CONNECTIONS - MARKETING AGENCIES - JELENA - AUGUST 21

- ownership: **unknown** — not in the ledger and not on any operator-declared internal list; UNKNOWN is the state, not a gap
- provider status `FINISHED`; created `2026-08-25T12:20:27.794401Z`; started `2026-08-25T12:20:50.24679Z`
- seats (`campaignAccountIds`): 174810
- lead list `885937` (Ivan M approved), list size `totalItemsCount` = 40; campaign holds `progressStats.totalUsers` = 40, finished 39
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **0**, accepted **0** (n/a (denominator 0))
  - messages sent **77**, message threads started **39**, replies **3** (7.69% of threads started)
  - unique leads contacted **39**; profile views 0, follows 0, post likes 0
  - provider's own tags: `autoTaggedInterested` **0**, `totalAutoTagged` **3**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 39 conversations joined, 0 operator-positive replies = **n/a (0 requests sent) per 100 requests sent**
- reply classes in this campaign: `negative` 2, `unknown` 1
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-08-30 .. 2026-09-21 (4 days)
- sequence node types present in the whole graph: CHECK_IS_CONNECTION, END, MESSAGE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CHECK_IS_CONNECTION   wait 0H      day  0.00
  step 1   MESSAGE               wait 0H      day  0.00
  step 2   MESSAGE               wait 5D      day  5.00
  step 3   MESSAGE               wait 5D      day 10.00
  step 4   END                   wait 1D      day 11.00
```

**Connection note:** this graph has no `CONNECTION_REQUEST` node, so no note is sent.

**Message steps — our text, in full:**

- message at day 0.00, 4 variant(s):
  - variant 1 (337 chars, 59 words): `Hi {FIRST_NAME}, we've been connected a while but never actually talked. I'll be direct about why I'm reaching out, I'm on the team at Productive, we help agencies get a live view of project profitability instead of finding out after the invoice's gone out. Think it's relevant for what you do at {COMPANY}. Worth 20 minutes to show you?`
  - variant 2 (327 chars, 55 words): `Hi {FIRST_NAME}, we've been connected a while but I don't think we've ever actually talked. 

I'm on the team at Productive, a platform agencies use to see project profitability live instead of finding out after the invoice's out. Think it's relevant for what you do at {COMPANY}. 

Happy to show you in 20 minutes. Interested?`
  - variant 3 (373 chars, 66 words): `Hey {FIRST_NAME}, we're connected but never got to talk. Reaching out because I think Productive could be relevant for you as a {POSITION}. The pitch: 20 minutes on how agencies get a live view of project profitability instead of finding out after the invoice's out. The deal: no deck, no follow up pressure either way, just a straight look at whether it fits. 

Up for it?`
  - variant 4 (351 chars, 61 words): `Hi {FIRST_NAME}, we've been connected but never actually chatted. I'll be direct about why I'm reaching out. Productive is a platform I think makes sense for {COMPANY}, and I'd love to show you what it does in 20 minutes. And because I know calendars are packed, there's no pitch deck involved, just a straight look at whether it's useful. Sound fair?`
  - fallback (315 chars): `Hi, we've been connected a while but never actually talked. 

I'll be direct about why I'm reaching out, I'm on the team at Productive, we help agencies get a live view of project profitability instead of finding out after the invoice's gone out. Think it's relevant for what you do. 

Worth 20 minutes to show you?`
- message at day 5.00, 3 variant(s):
  - variant 1 (306 chars, 50 words): `Here's the actual reason I think it's worth your time, {FIRST_NAME}. Some agencies are still stitching together budgets, resourcing, and time tracking across separate tools and only find out a project lost money once the invoice's gone out and Productive fixes that. Want to see if it applies to {COMPANY}?`
  - variant 2 (309 chars, 54 words): `{FIRST_NAME}, not sure my last message actually landed, so trying again. No pressure either way on the 20 minutes. The actual value is Productive connecting your project data to the financial side, so your team stops piecing it together after the fact and just sees it live. 

Would you like me to share more?`
  - variant 3 (272 chars, 43 words): `Hi {FIRST_NAME}, one thing I keep hearing from {POSITION} roles in your industry is that profitability visibility is the bottleneck, not because it's complicated, just because the tools haven't caught up. That's exactly what Productive is built for. 

Want to take a look?`
  - fallback (292 chars): `Here's the actual reason I think it's worth your time. Some agencies are still stitching together budgets, resourcing, and time tracking across separate tools and only find out a project lost money once the invoice's gone out and Productive fixes that. Want to see if it applies to your team?`
- message at day 10.00, 3 variant(s):
  - variant 1 (75 chars, 16 words): `Should I take this as a no for now, {FIRST_NAME}, or keep it on your radar?`
  - variant 2 (77 chars, 14 words): `Yes to 20 minutes at some point, {FIRST_NAME}, or should I stop reaching out?`
  - variant 3 (67 chars, 12 words): `Still worth 20 minutes, {FIRST_NAME}, or should I leave it for now?`
  - fallback (61 chars): `Should I take this as a no for now, or keep it on your radar?`

### 567745 — PRODUCTIVE - DOROTA P CONNECTIONS - MARKETING AGENCIES - JELENA - AUGUST 21

- ownership: **unknown** — not in the ledger and not on any operator-declared internal list; UNKNOWN is the state, not a gap
- provider status `FINISHED`; created `2026-08-25T12:21:32.50775Z`; started `2026-08-25T12:21:52.675043Z`
- seats (`campaignAccountIds`): 143105
- lead list `885945` (Dorota P approved), list size `totalItemsCount` = 15; campaign holds `progressStats.totalUsers` = 15, finished 15
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **0**, accepted **0** (n/a (denominator 0))
  - messages sent **30**, message threads started **15**, replies **0** (0.00% of threads started)
  - unique leads contacted **15**; profile views 0, follows 0, post likes 0
  - provider's own tags: `autoTaggedInterested` **0**, `totalAutoTagged` **0**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 15 conversations joined, 0 operator-positive replies = **n/a (0 requests sent) per 100 requests sent**
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-08-30 .. 2026-09-04 (2 days)
- sequence node types present in the whole graph: CHECK_IS_CONNECTION, END, MESSAGE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CHECK_IS_CONNECTION   wait 0H      day  0.00
  step 1   MESSAGE               wait 0H      day  0.00
  step 2   MESSAGE               wait 5D      day  5.00
  step 3   MESSAGE               wait 5D      day 10.00
  step 4   END                   wait 1D      day 11.00
```

**Connection note:** this graph has no `CONNECTION_REQUEST` node, so no note is sent.

**Message steps — our text, in full:**

- message at day 0.00, 4 variant(s):
  - variant 1 (337 chars, 59 words): `Hi {FIRST_NAME}, we've been connected a while but never actually talked. I'll be direct about why I'm reaching out, I'm on the team at Productive, we help agencies get a live view of project profitability instead of finding out after the invoice's gone out. Think it's relevant for what you do at {COMPANY}. Worth 20 minutes to show you?`
  - variant 2 (327 chars, 55 words): `Hi {FIRST_NAME}, we've been connected a while but I don't think we've ever actually talked. 

I'm on the team at Productive, a platform agencies use to see project profitability live instead of finding out after the invoice's out. Think it's relevant for what you do at {COMPANY}. 

Happy to show you in 20 minutes. Interested?`
  - variant 3 (373 chars, 66 words): `Hey {FIRST_NAME}, we're connected but never got to talk. Reaching out because I think Productive could be relevant for you as a {POSITION}. The pitch: 20 minutes on how agencies get a live view of project profitability instead of finding out after the invoice's out. The deal: no deck, no follow up pressure either way, just a straight look at whether it fits. 

Up for it?`
  - variant 4 (351 chars, 61 words): `Hi {FIRST_NAME}, we've been connected but never actually chatted. I'll be direct about why I'm reaching out. Productive is a platform I think makes sense for {COMPANY}, and I'd love to show you what it does in 20 minutes. And because I know calendars are packed, there's no pitch deck involved, just a straight look at whether it's useful. Sound fair?`
  - fallback (315 chars): `Hi, we've been connected a while but never actually talked. 

I'll be direct about why I'm reaching out, I'm on the team at Productive, we help agencies get a live view of project profitability instead of finding out after the invoice's gone out. Think it's relevant for what you do. 

Worth 20 minutes to show you?`
- message at day 5.00, 3 variant(s):
  - variant 1 (306 chars, 50 words): `Here's the actual reason I think it's worth your time, {FIRST_NAME}. Some agencies are still stitching together budgets, resourcing, and time tracking across separate tools and only find out a project lost money once the invoice's gone out and Productive fixes that. Want to see if it applies to {COMPANY}?`
  - variant 2 (309 chars, 54 words): `{FIRST_NAME}, not sure my last message actually landed, so trying again. No pressure either way on the 20 minutes. The actual value is Productive connecting your project data to the financial side, so your team stops piecing it together after the fact and just sees it live. 

Would you like me to share more?`
  - variant 3 (272 chars, 43 words): `Hi {FIRST_NAME}, one thing I keep hearing from {POSITION} roles in your industry is that profitability visibility is the bottleneck, not because it's complicated, just because the tools haven't caught up. That's exactly what Productive is built for. 

Want to take a look?`
  - fallback (292 chars): `Here's the actual reason I think it's worth your time. Some agencies are still stitching together budgets, resourcing, and time tracking across separate tools and only find out a project lost money once the invoice's gone out and Productive fixes that. Want to see if it applies to your team?`
- message at day 10.00, 3 variant(s):
  - variant 1 (75 chars, 16 words): `Should I take this as a no for now, {FIRST_NAME}, or keep it on your radar?`
  - variant 2 (77 chars, 14 words): `Yes to 20 minutes at some point, {FIRST_NAME}, or should I stop reaching out?`
  - variant 3 (67 chars, 12 words): `Still worth 20 minutes, {FIRST_NAME}, or should I leave it for now?`
  - fallback (61 chars): `Should I take this as a no for now, or keep it on your radar?`

### 567747 — PRODUCTIVE - DJORDJE J CONNECTIONS - MARKETING AGENCIES - JELENA - AUGUST 21

- ownership: **unknown** — not in the ledger and not on any operator-declared internal list; UNKNOWN is the state, not a gap
- provider status `FINISHED`; created `2026-08-25T12:22:14.391338Z`; started `2026-08-25T12:22:40.035444Z`
- seats (`campaignAccountIds`): 119588
- lead list `885948` (Djordje J approved), list size `totalItemsCount` = 24; campaign holds `progressStats.totalUsers` = 24, finished 23
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **0**, accepted **0** (n/a (denominator 0))
  - messages sent **46**, message threads started **23**, replies **1** (4.35% of threads started)
  - unique leads contacted **23**; profile views 0, follows 0, post likes 0
  - provider's own tags: `autoTaggedInterested` **0**, `totalAutoTagged` **1**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 23 conversations joined, 1 operator-positive replies = **n/a (0 requests sent) per 100 requests sent**
- reply classes in this campaign: `negative` 1, `positive` 1
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-08-30 .. 2026-09-09 (3 days)
- sequence node types present in the whole graph: CHECK_IS_CONNECTION, END, MESSAGE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CHECK_IS_CONNECTION   wait 0H      day  0.00
  step 1   MESSAGE               wait 0H      day  0.00
  step 2   MESSAGE               wait 5D      day  5.00
  step 3   MESSAGE               wait 5D      day 10.00
  step 4   END                   wait 1D      day 11.00
```

**Connection note:** this graph has no `CONNECTION_REQUEST` node, so no note is sent.

**Message steps — our text, in full:**

- message at day 0.00, 4 variant(s):
  - variant 1 (337 chars, 59 words): `Hi {FIRST_NAME}, we've been connected a while but never actually talked. I'll be direct about why I'm reaching out, I'm on the team at Productive, we help agencies get a live view of project profitability instead of finding out after the invoice's gone out. Think it's relevant for what you do at {COMPANY}. Worth 20 minutes to show you?`
  - variant 2 (327 chars, 55 words): `Hi {FIRST_NAME}, we've been connected a while but I don't think we've ever actually talked. 

I'm on the team at Productive, a platform agencies use to see project profitability live instead of finding out after the invoice's out. Think it's relevant for what you do at {COMPANY}. 

Happy to show you in 20 minutes. Interested?`
  - variant 3 (373 chars, 66 words): `Hey {FIRST_NAME}, we're connected but never got to talk. Reaching out because I think Productive could be relevant for you as a {POSITION}. The pitch: 20 minutes on how agencies get a live view of project profitability instead of finding out after the invoice's out. The deal: no deck, no follow up pressure either way, just a straight look at whether it fits. 

Up for it?`
  - variant 4 (351 chars, 61 words): `Hi {FIRST_NAME}, we've been connected but never actually chatted. I'll be direct about why I'm reaching out. Productive is a platform I think makes sense for {COMPANY}, and I'd love to show you what it does in 20 minutes. And because I know calendars are packed, there's no pitch deck involved, just a straight look at whether it's useful. Sound fair?`
  - fallback (315 chars): `Hi, we've been connected a while but never actually talked. 

I'll be direct about why I'm reaching out, I'm on the team at Productive, we help agencies get a live view of project profitability instead of finding out after the invoice's gone out. Think it's relevant for what you do. 

Worth 20 minutes to show you?`
- message at day 5.00, 3 variant(s):
  - variant 1 (306 chars, 50 words): `Here's the actual reason I think it's worth your time, {FIRST_NAME}. Some agencies are still stitching together budgets, resourcing, and time tracking across separate tools and only find out a project lost money once the invoice's gone out and Productive fixes that. Want to see if it applies to {COMPANY}?`
  - variant 2 (309 chars, 54 words): `{FIRST_NAME}, not sure my last message actually landed, so trying again. No pressure either way on the 20 minutes. The actual value is Productive connecting your project data to the financial side, so your team stops piecing it together after the fact and just sees it live. 

Would you like me to share more?`
  - variant 3 (272 chars, 43 words): `Hi {FIRST_NAME}, one thing I keep hearing from {POSITION} roles in your industry is that profitability visibility is the bottleneck, not because it's complicated, just because the tools haven't caught up. That's exactly what Productive is built for. 

Want to take a look?`
  - fallback (292 chars): `Here's the actual reason I think it's worth your time. Some agencies are still stitching together budgets, resourcing, and time tracking across separate tools and only find out a project lost money once the invoice's gone out and Productive fixes that. Want to see if it applies to your team?`
- message at day 10.00, 3 variant(s):
  - variant 1 (75 chars, 16 words): `Should I take this as a no for now, {FIRST_NAME}, or keep it on your radar?`
  - variant 2 (77 chars, 14 words): `Yes to 20 minutes at some point, {FIRST_NAME}, or should I stop reaching out?`
  - variant 3 (67 chars, 12 words): `Still worth 20 minutes, {FIRST_NAME}, or should I leave it for now?`
  - fallback (61 chars): `Should I take this as a no for now, or keep it on your radar?`

### 567750 — PRODUCTIVE - DEAN B CONNECTIONS - MARKETING AGENCIES - JELENA - AUGUST 21

- ownership: **unknown** — not in the ledger and not on any operator-declared internal list; UNKNOWN is the state, not a gap
- provider status `FINISHED`; created `2026-08-25T12:23:01.45936Z`; started `2026-08-25T12:23:18.86523Z`
- seats (`campaignAccountIds`): 212356
- lead list `885949` (Dean B approved), list size `totalItemsCount` = 14; campaign holds `progressStats.totalUsers` = 14, finished 14
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **0**, accepted **0** (n/a (denominator 0))
  - messages sent **25**, message threads started **14**, replies **2** (14.29% of threads started)
  - unique leads contacted **14**; profile views 0, follows 0, post likes 0
  - provider's own tags: `autoTaggedInterested` **0**, `totalAutoTagged` **2**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 14 conversations joined, 0 operator-positive replies = **n/a (0 requests sent) per 100 requests sent**
- reply classes in this campaign: `unknown` 2
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-08-25 .. 2026-09-05 (5 days)
- sequence node types present in the whole graph: CHECK_IS_CONNECTION, END, MESSAGE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CHECK_IS_CONNECTION   wait 0H      day  0.00
  step 1   MESSAGE               wait 0H      day  0.00
  step 2   MESSAGE               wait 5D      day  5.00
  step 3   MESSAGE               wait 5D      day 10.00
  step 4   END                   wait 1D      day 11.00
```

**Connection note:** this graph has no `CONNECTION_REQUEST` node, so no note is sent.

**Message steps — our text, in full:**

- message at day 0.00, 4 variant(s):
  - variant 1 (337 chars, 59 words): `Hi {FIRST_NAME}, we've been connected a while but never actually talked. I'll be direct about why I'm reaching out, I'm on the team at Productive, we help agencies get a live view of project profitability instead of finding out after the invoice's gone out. Think it's relevant for what you do at {COMPANY}. Worth 20 minutes to show you?`
  - variant 2 (327 chars, 55 words): `Hi {FIRST_NAME}, we've been connected a while but I don't think we've ever actually talked. 

I'm on the team at Productive, a platform agencies use to see project profitability live instead of finding out after the invoice's out. Think it's relevant for what you do at {COMPANY}. 

Happy to show you in 20 minutes. Interested?`
  - variant 3 (373 chars, 66 words): `Hey {FIRST_NAME}, we're connected but never got to talk. Reaching out because I think Productive could be relevant for you as a {POSITION}. The pitch: 20 minutes on how agencies get a live view of project profitability instead of finding out after the invoice's out. The deal: no deck, no follow up pressure either way, just a straight look at whether it fits. 

Up for it?`
  - variant 4 (351 chars, 61 words): `Hi {FIRST_NAME}, we've been connected but never actually chatted. I'll be direct about why I'm reaching out. Productive is a platform I think makes sense for {COMPANY}, and I'd love to show you what it does in 20 minutes. And because I know calendars are packed, there's no pitch deck involved, just a straight look at whether it's useful. Sound fair?`
  - fallback (315 chars): `Hi, we've been connected a while but never actually talked. 

I'll be direct about why I'm reaching out, I'm on the team at Productive, we help agencies get a live view of project profitability instead of finding out after the invoice's gone out. Think it's relevant for what you do. 

Worth 20 minutes to show you?`
- message at day 5.00, 3 variant(s):
  - variant 1 (306 chars, 50 words): `Here's the actual reason I think it's worth your time, {FIRST_NAME}. Some agencies are still stitching together budgets, resourcing, and time tracking across separate tools and only find out a project lost money once the invoice's gone out and Productive fixes that. Want to see if it applies to {COMPANY}?`
  - variant 2 (309 chars, 54 words): `{FIRST_NAME}, not sure my last message actually landed, so trying again. No pressure either way on the 20 minutes. The actual value is Productive connecting your project data to the financial side, so your team stops piecing it together after the fact and just sees it live. 

Would you like me to share more?`
  - variant 3 (272 chars, 43 words): `Hi {FIRST_NAME}, one thing I keep hearing from {POSITION} roles in your industry is that profitability visibility is the bottleneck, not because it's complicated, just because the tools haven't caught up. That's exactly what Productive is built for. 

Want to take a look?`
  - fallback (292 chars): `Here's the actual reason I think it's worth your time. Some agencies are still stitching together budgets, resourcing, and time tracking across separate tools and only find out a project lost money once the invoice's gone out and Productive fixes that. Want to see if it applies to your team?`
- message at day 10.00, 3 variant(s):
  - variant 1 (75 chars, 16 words): `Should I take this as a no for now, {FIRST_NAME}, or keep it on your radar?`
  - variant 2 (77 chars, 14 words): `Yes to 20 minutes at some point, {FIRST_NAME}, or should I stop reaching out?`
  - variant 3 (67 chars, 12 words): `Still worth 20 minutes, {FIRST_NAME}, or should I leave it for now?`
  - fallback (61 chars): `Should I take this as a no for now, or keep it on your radar?`

### 567752 — PRODUCTIVE - BOJAN S CONNECTIONS - MARKETING AGENCIES - JELENA - AUGUST 21

- ownership: **unknown** — not in the ledger and not on any operator-declared internal list; UNKNOWN is the state, not a gap
- provider status `FINISHED`; created `2026-08-25T12:23:36.491992Z`; started `2026-08-25T12:23:56.86565Z`
- seats (`campaignAccountIds`): 201978
- lead list `885950` (Bojan S approved), list size `totalItemsCount` = 25; campaign holds `progressStats.totalUsers` = 25, finished 24
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **0**, accepted **0** (n/a (denominator 0))
  - messages sent **47**, message threads started **25**, replies **2** (8.00% of threads started)
  - unique leads contacted **25**; profile views 0, follows 0, post likes 0
  - provider's own tags: `autoTaggedInterested` **0**, `totalAutoTagged` **2**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 25 conversations joined, 0 operator-positive replies = **n/a (0 requests sent) per 100 requests sent**
- reply classes in this campaign: `automated` 1, `negative` 1, `unknown` 1
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-08-25 .. 2026-09-24 (4 days)
- sequence node types present in the whole graph: CHECK_IS_CONNECTION, END, MESSAGE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CHECK_IS_CONNECTION   wait 0H      day  0.00
  step 1   MESSAGE               wait 0H      day  0.00
  step 2   MESSAGE               wait 5D      day  5.00
  step 3   MESSAGE               wait 5D      day 10.00
  step 4   END                   wait 1D      day 11.00
```

**Connection note:** this graph has no `CONNECTION_REQUEST` node, so no note is sent.

**Message steps — our text, in full:**

- message at day 0.00, 4 variant(s):
  - variant 1 (337 chars, 59 words): `Hi {FIRST_NAME}, we've been connected a while but never actually talked. I'll be direct about why I'm reaching out, I'm on the team at Productive, we help agencies get a live view of project profitability instead of finding out after the invoice's gone out. Think it's relevant for what you do at {COMPANY}. Worth 20 minutes to show you?`
  - variant 2 (327 chars, 55 words): `Hi {FIRST_NAME}, we've been connected a while but I don't think we've ever actually talked. 

I'm on the team at Productive, a platform agencies use to see project profitability live instead of finding out after the invoice's out. Think it's relevant for what you do at {COMPANY}. 

Happy to show you in 20 minutes. Interested?`
  - variant 3 (373 chars, 66 words): `Hey {FIRST_NAME}, we're connected but never got to talk. Reaching out because I think Productive could be relevant for you as a {POSITION}. The pitch: 20 minutes on how agencies get a live view of project profitability instead of finding out after the invoice's out. The deal: no deck, no follow up pressure either way, just a straight look at whether it fits. 

Up for it?`
  - variant 4 (351 chars, 61 words): `Hi {FIRST_NAME}, we've been connected but never actually chatted. I'll be direct about why I'm reaching out. Productive is a platform I think makes sense for {COMPANY}, and I'd love to show you what it does in 20 minutes. And because I know calendars are packed, there's no pitch deck involved, just a straight look at whether it's useful. Sound fair?`
  - fallback (315 chars): `Hi, we've been connected a while but never actually talked. 

I'll be direct about why I'm reaching out, I'm on the team at Productive, we help agencies get a live view of project profitability instead of finding out after the invoice's gone out. Think it's relevant for what you do. 

Worth 20 minutes to show you?`
- message at day 5.00, 3 variant(s):
  - variant 1 (306 chars, 50 words): `Here's the actual reason I think it's worth your time, {FIRST_NAME}. Some agencies are still stitching together budgets, resourcing, and time tracking across separate tools and only find out a project lost money once the invoice's gone out and Productive fixes that. Want to see if it applies to {COMPANY}?`
  - variant 2 (309 chars, 54 words): `{FIRST_NAME}, not sure my last message actually landed, so trying again. No pressure either way on the 20 minutes. The actual value is Productive connecting your project data to the financial side, so your team stops piecing it together after the fact and just sees it live. 

Would you like me to share more?`
  - variant 3 (272 chars, 43 words): `Hi {FIRST_NAME}, one thing I keep hearing from {POSITION} roles in your industry is that profitability visibility is the bottleneck, not because it's complicated, just because the tools haven't caught up. That's exactly what Productive is built for. 

Want to take a look?`
  - fallback (292 chars): `Here's the actual reason I think it's worth your time. Some agencies are still stitching together budgets, resourcing, and time tracking across separate tools and only find out a project lost money once the invoice's gone out and Productive fixes that. Want to see if it applies to your team?`
- message at day 10.00, 3 variant(s):
  - variant 1 (75 chars, 16 words): `Should I take this as a no for now, {FIRST_NAME}, or keep it on your radar?`
  - variant 2 (77 chars, 14 words): `Yes to 20 minutes at some point, {FIRST_NAME}, or should I stop reaching out?`
  - variant 3 (67 chars, 12 words): `Still worth 20 minutes, {FIRST_NAME}, or should I leave it for now?`
  - fallback (61 chars): `Should I take this as a no for now, or keep it on your radar?`

### 567754 — PRODUCTIVE - ANITA S CONNECTIONS - MARKETING AGENCIES - JELENA - AUGUST 21

- ownership: **unknown** — not in the ledger and not on any operator-declared internal list; UNKNOWN is the state, not a gap
- provider status `FINISHED`; created `2026-08-25T12:24:13.707972Z`; started `2026-08-25T12:24:36.274046Z`
- seats (`campaignAccountIds`): 169600
- lead list `885952` (Anita S approved), list size `totalItemsCount` = 26; campaign holds `progressStats.totalUsers` = 26, finished 26
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **0**, accepted **0** (n/a (denominator 0))
  - messages sent **50**, message threads started **26**, replies **1** (3.85% of threads started)
  - unique leads contacted **26**; profile views 0, follows 0, post likes 0
  - provider's own tags: `autoTaggedInterested` **0**, `totalAutoTagged` **1**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 26 conversations joined, 0 operator-positive replies = **n/a (0 requests sent) per 100 requests sent**
- reply classes in this campaign: `unknown` 1
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-08-25 .. 2026-09-05 (5 days)
- sequence node types present in the whole graph: CHECK_IS_CONNECTION, END, MESSAGE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CHECK_IS_CONNECTION   wait 0H      day  0.00
  step 1   MESSAGE               wait 0H      day  0.00
  step 2   MESSAGE               wait 5D      day  5.00
  step 3   MESSAGE               wait 5D      day 10.00
  step 4   END                   wait 1D      day 11.00
```

**Connection note:** this graph has no `CONNECTION_REQUEST` node, so no note is sent.

**Message steps — our text, in full:**

- message at day 0.00, 4 variant(s):
  - variant 1 (337 chars, 59 words): `Hi {FIRST_NAME}, we've been connected a while but never actually talked. I'll be direct about why I'm reaching out, I'm on the team at Productive, we help agencies get a live view of project profitability instead of finding out after the invoice's gone out. Think it's relevant for what you do at {COMPANY}. Worth 20 minutes to show you?`
  - variant 2 (327 chars, 55 words): `Hi {FIRST_NAME}, we've been connected a while but I don't think we've ever actually talked. 

I'm on the team at Productive, a platform agencies use to see project profitability live instead of finding out after the invoice's out. Think it's relevant for what you do at {COMPANY}. 

Happy to show you in 20 minutes. Interested?`
  - variant 3 (373 chars, 66 words): `Hey {FIRST_NAME}, we're connected but never got to talk. Reaching out because I think Productive could be relevant for you as a {POSITION}. The pitch: 20 minutes on how agencies get a live view of project profitability instead of finding out after the invoice's out. The deal: no deck, no follow up pressure either way, just a straight look at whether it fits. 

Up for it?`
  - variant 4 (351 chars, 61 words): `Hi {FIRST_NAME}, we've been connected but never actually chatted. I'll be direct about why I'm reaching out. Productive is a platform I think makes sense for {COMPANY}, and I'd love to show you what it does in 20 minutes. And because I know calendars are packed, there's no pitch deck involved, just a straight look at whether it's useful. Sound fair?`
  - fallback (315 chars): `Hi, we've been connected a while but never actually talked. 

I'll be direct about why I'm reaching out, I'm on the team at Productive, we help agencies get a live view of project profitability instead of finding out after the invoice's gone out. Think it's relevant for what you do. 

Worth 20 minutes to show you?`
- message at day 5.00, 3 variant(s):
  - variant 1 (306 chars, 50 words): `Here's the actual reason I think it's worth your time, {FIRST_NAME}. Some agencies are still stitching together budgets, resourcing, and time tracking across separate tools and only find out a project lost money once the invoice's gone out and Productive fixes that. Want to see if it applies to {COMPANY}?`
  - variant 2 (309 chars, 54 words): `{FIRST_NAME}, not sure my last message actually landed, so trying again. No pressure either way on the 20 minutes. The actual value is Productive connecting your project data to the financial side, so your team stops piecing it together after the fact and just sees it live. 

Would you like me to share more?`
  - variant 3 (272 chars, 43 words): `Hi {FIRST_NAME}, one thing I keep hearing from {POSITION} roles in your industry is that profitability visibility is the bottleneck, not because it's complicated, just because the tools haven't caught up. That's exactly what Productive is built for. 

Want to take a look?`
  - fallback (292 chars): `Here's the actual reason I think it's worth your time. Some agencies are still stitching together budgets, resourcing, and time tracking across separate tools and only find out a project lost money once the invoice's gone out and Productive fixes that. Want to see if it applies to your team?`
- message at day 10.00, 3 variant(s):
  - variant 1 (75 chars, 16 words): `Should I take this as a no for now, {FIRST_NAME}, or keep it on your radar?`
  - variant 2 (77 chars, 14 words): `Yes to 20 minutes at some point, {FIRST_NAME}, or should I stop reaching out?`
  - variant 3 (67 chars, 12 words): `Still worth 20 minutes, {FIRST_NAME}, or should I leave it for now?`
  - fallback (61 chars): `Should I take this as a no for now, or keep it on your radar?`

### 567758 — PRODUCTIVE - ANA L CONNECTIONS - MARKETING AGENCIES - JELENA - AUGUST 21

- ownership: **unknown** — not in the ledger and not on any operator-declared internal list; UNKNOWN is the state, not a gap
- provider status `FINISHED`; created `2026-08-25T12:24:56.356693Z`; started `2026-08-25T12:25:16.059817Z`
- seats (`campaignAccountIds`): 181658
- lead list `885955` (Ana L approved), list size `totalItemsCount` = 24; campaign holds `progressStats.totalUsers` = 24, finished 24
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **0**, accepted **0** (n/a (denominator 0))
  - messages sent **46**, message threads started **24**, replies **2** (8.33% of threads started)
  - unique leads contacted **24**; profile views 0, follows 0, post likes 0
  - provider's own tags: `autoTaggedInterested` **0**, `totalAutoTagged` **2**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 24 conversations joined, 0 operator-positive replies = **n/a (0 requests sent) per 100 requests sent**
- reply classes in this campaign: `unknown` 3, `negative` 1
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-08-25 .. 2026-09-05 (5 days)
- sequence node types present in the whole graph: CHECK_IS_CONNECTION, END, MESSAGE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CHECK_IS_CONNECTION   wait 0H      day  0.00
  step 1   MESSAGE               wait 0H      day  0.00
  step 2   MESSAGE               wait 5D      day  5.00
  step 3   MESSAGE               wait 5D      day 10.00
  step 4   END                   wait 1D      day 11.00
```

**Connection note:** this graph has no `CONNECTION_REQUEST` node, so no note is sent.

**Message steps — our text, in full:**

- message at day 0.00, 4 variant(s):
  - variant 1 (337 chars, 59 words): `Hi {FIRST_NAME}, we've been connected a while but never actually talked. I'll be direct about why I'm reaching out, I'm on the team at Productive, we help agencies get a live view of project profitability instead of finding out after the invoice's gone out. Think it's relevant for what you do at {COMPANY}. Worth 20 minutes to show you?`
  - variant 2 (327 chars, 55 words): `Hi {FIRST_NAME}, we've been connected a while but I don't think we've ever actually talked. 

I'm on the team at Productive, a platform agencies use to see project profitability live instead of finding out after the invoice's out. Think it's relevant for what you do at {COMPANY}. 

Happy to show you in 20 minutes. Interested?`
  - variant 3 (373 chars, 66 words): `Hey {FIRST_NAME}, we're connected but never got to talk. Reaching out because I think Productive could be relevant for you as a {POSITION}. The pitch: 20 minutes on how agencies get a live view of project profitability instead of finding out after the invoice's out. The deal: no deck, no follow up pressure either way, just a straight look at whether it fits. 

Up for it?`
  - variant 4 (351 chars, 61 words): `Hi {FIRST_NAME}, we've been connected but never actually chatted. I'll be direct about why I'm reaching out. Productive is a platform I think makes sense for {COMPANY}, and I'd love to show you what it does in 20 minutes. And because I know calendars are packed, there's no pitch deck involved, just a straight look at whether it's useful. Sound fair?`
  - fallback (315 chars): `Hi, we've been connected a while but never actually talked. 

I'll be direct about why I'm reaching out, I'm on the team at Productive, we help agencies get a live view of project profitability instead of finding out after the invoice's gone out. Think it's relevant for what you do. 

Worth 20 minutes to show you?`
- message at day 5.00, 3 variant(s):
  - variant 1 (306 chars, 50 words): `Here's the actual reason I think it's worth your time, {FIRST_NAME}. Some agencies are still stitching together budgets, resourcing, and time tracking across separate tools and only find out a project lost money once the invoice's gone out and Productive fixes that. Want to see if it applies to {COMPANY}?`
  - variant 2 (309 chars, 54 words): `{FIRST_NAME}, not sure my last message actually landed, so trying again. No pressure either way on the 20 minutes. The actual value is Productive connecting your project data to the financial side, so your team stops piecing it together after the fact and just sees it live. 

Would you like me to share more?`
  - variant 3 (272 chars, 43 words): `Hi {FIRST_NAME}, one thing I keep hearing from {POSITION} roles in your industry is that profitability visibility is the bottleneck, not because it's complicated, just because the tools haven't caught up. That's exactly what Productive is built for. 

Want to take a look?`
  - fallback (292 chars): `Here's the actual reason I think it's worth your time. Some agencies are still stitching together budgets, resourcing, and time tracking across separate tools and only find out a project lost money once the invoice's gone out and Productive fixes that. Want to see if it applies to your team?`
- message at day 10.00, 3 variant(s):
  - variant 1 (75 chars, 16 words): `Should I take this as a no for now, {FIRST_NAME}, or keep it on your radar?`
  - variant 2 (77 chars, 14 words): `Yes to 20 minutes at some point, {FIRST_NAME}, or should I stop reaching out?`
  - variant 3 (67 chars, 12 words): `Still worth 20 minutes, {FIRST_NAME}, or should I leave it for now?`
  - fallback (61 chars): `Should I take this as a no for now, or keep it on your radar?`

### 583490 — MAYBE - Heyreach - Jelena - September 3

- ownership: **unknown** — not in the ledger and not on any operator-declared internal list; UNKNOWN is the state, not a gap
- provider status `DRAFT`; created `2026-09-03T13:31:26.262442Z`; started `never`
- seats (`campaignAccountIds`): 174892, 174748, 175455, 174742, 174332, 174822, 174845, 174803, 208242, 174797
- lead list `902890` (Maybe CLEANED), list size `totalItemsCount` = 71; campaign holds `progressStats.totalUsers` = 0, finished 0
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **0**, accepted **0** (n/a (denominator 0))
  - messages sent **0**, message threads started **0**, replies **0** (n/a (denominator 0) of threads started)
  - unique leads contacted **0**; profile views 0, follows 0, post likes 0
  - provider's own tags: `autoTaggedInterested` **0**, `totalAutoTagged` **0**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 0 conversations joined, 0 operator-positive replies = **n/a (0 requests sent) per 100 requests sent**
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- sequence node types present in the whole graph: CHECK_IS_CONNECTION, CONNECTION_REQUEST, END, FOLLOW, INMAIL, MESSAGE, SEND_LEAD_TO_BISON, VIEW_PROFILE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CHECK_IS_CONNECTION   wait 0H      day  0.00
  step 1   MESSAGE               wait 0H      day  0.00
  step 2   MESSAGE               wait 5D      day  5.00
  step 3   SEND_LEAD_TO_BISON    wait 5D      day 10.00
  step 4   END                   wait 0H      day 10.00
```

**Connection note:** 1 `CONNECTION_REQUEST` note slot(s), every one of them EMPTY — this campaign sends connection requests with no note.

**Message steps — our text, in full:**

- message at day 0.00, 2 variant(s):
  - variant 1 (300 chars, 56 words): `hey {FIRST_NAME}, a colleague of mine reached out a while back about Productive, might not have been the right time. wanted to check back myself rather than just let it go quiet, is this still something worth a look for {COMPANY}? if not, no worries at all, just say so and I won't keep following up.`
  - variant 2 (238 chars, 45 words): `Hi {FIRST_NAME}, a colleague reached out to you a while ago about Productive. I wanted to check back in myself rather than let the thread go cold, is this relevant for {COMPANY}? Happy to leave it here if not, just let me know either way.`
  - fallback (287 chars): `hey, a colleague of mine reached out a while back about Productive, might not have been the right time. wanted to check back myself rather than just let it go quiet, is this still something worth a look for your team? if not, no worries at all, just say so and I won't keep following up.`
- message at day 5.00, 2 variant(s):
  - variant 1 (366 chars, 63 words): `figured I'd give a bit more context in case you can't remember what it was about. Productive brings project management, resourcing, time tracking and budgets into one place, so you can actually see if a project's profitable while it's still running instead of finding out after the invoice goes out. worth a quick look, or is this genuinely not a priority right now?`
  - variant 2 (289 chars, 49 words): `for context in case it's useful, Productive's basically a way to stop juggling separate tools for projects, time tracking and budgets, and see project profitability in real time instead of after the fact. if that's relevant for your company I'm happy to show you around. what do you think?`
  - fallback (366 chars): `figured I'd give a bit more context in case you can't remember what it was about. Productive brings project management, resourcing, time tracking and budgets into one place, so you can actually see if a project's profitable while it's still running instead of finding out after the invoice goes out. worth a quick look, or is this genuinely not a priority right now?`

### 583536 — INTERESTED - Heyreach - Jelena - September 3

- ownership: **unknown** — not in the ledger and not on any operator-declared internal list; UNKNOWN is the state, not a gap
- provider status `DRAFT`; created `2026-09-03T13:51:56.7108Z`; started `never`
- seats (`campaignAccountIds`): 174892, 174748, 175455, 174742, 174332, 174822, 174845, 174803, 208242, 174797
- lead list `902839` (Hot Leads CLEANED), list size `totalItemsCount` = 11; campaign holds `progressStats.totalUsers` = 0, finished 0
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **0**, accepted **0** (n/a (denominator 0))
  - messages sent **0**, message threads started **0**, replies **0** (n/a (denominator 0) of threads started)
  - unique leads contacted **0**; profile views 0, follows 0, post likes 0
  - provider's own tags: `autoTaggedInterested` **0**, `totalAutoTagged` **0**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 0 conversations joined, 0 operator-positive replies = **n/a (0 requests sent) per 100 requests sent**
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- sequence node types present in the whole graph: CHECK_IS_CONNECTION, CONNECTION_REQUEST, END, FOLLOW, INMAIL, MESSAGE, SEND_LEAD_TO_BISON, VIEW_PROFILE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CHECK_IS_CONNECTION   wait 0H      day  0.00
  step 1   MESSAGE               wait 0H      day  0.00
  step 2   MESSAGE               wait 5D      day  5.00
  step 3   SEND_LEAD_TO_BISON    wait 5D      day 10.00
  step 4   END                   wait 0H      day 10.00
```

**Connection note:** 1 `CONNECTION_REQUEST` note slot(s), every one of them EMPTY — this campaign sends connection requests with no note.

**Message steps — our text, in full:**

- message at day 0.00, 1 variant(s):
  - variant 1 (219 chars, 41 words): `Hi {FIRST_NAME}, a colleague of mine was talking with you a while back about Productive, and then it went quiet, which happens, no worries there. Wanted to pick it back up properly, do you have some time to take a look?`
  - fallback (206 chars): `Hi, a colleague of mine was talking with you a while back about Productive, and then it went quiet, which happens, no worries there. Wanted to pick it back up properly, do you have some time to take a look?`
- message at day 5.00, 2 variant(s):
  - variant 1 (188 chars, 43 words): `Would you like me to show you around, or would it be easier if I sent a few materials over first so you can take a look on your own time?

Or let me know if you'd like for me to stop here.`
  - variant 2 (289 chars, 49 words): `for context in case it's useful, Productive's basically a way to stop juggling separate tools for projects, time tracking and budgets, and see project profitability in real time instead of after the fact. if that's relevant for your company I'm happy to show you around. what do you think?`
  - fallback (188 chars): `Would you like me to show you around, or would it be easier if I sent a few materials over first so you can take a look on your own time?

Or let me know if you'd like for me to stop here.`

### 583549 — INTERESTED - Bison - Jelena - September 3

- ownership: **unknown** — not in the ledger and not on any operator-declared internal list; UNKNOWN is the state, not a gap
- provider status `DRAFT`; created `2026-09-03T14:04:17.531073Z`; started `never`
- seats (`campaignAccountIds`): 174892, 174748, 175455, 174742, 174332, 174822, 174845, 174803, 208242, 174797
- lead list `903006` (Interested Email CLEANED), list size `totalItemsCount` = 7; campaign holds `progressStats.totalUsers` = 0, finished 0
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **0**, accepted **0** (n/a (denominator 0))
  - messages sent **0**, message threads started **0**, replies **0** (n/a (denominator 0) of threads started)
  - unique leads contacted **0**; profile views 0, follows 0, post likes 0
  - provider's own tags: `autoTaggedInterested` **0**, `totalAutoTagged` **0**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 0 conversations joined, 0 operator-positive replies = **n/a (0 requests sent) per 100 requests sent**
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- sequence node types present in the whole graph: CHECK_IS_CONNECTION, CONNECTION_REQUEST, END, FOLLOW, INMAIL, MESSAGE, SEND_LEAD_TO_BISON, VIEW_PROFILE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CHECK_IS_CONNECTION   wait 0H      day  0.00
  step 1   MESSAGE               wait 0H      day  0.00
  step 2   MESSAGE               wait 5D      day  5.00
  step 3   SEND_LEAD_TO_BISON    wait 5D      day 10.00
  step 4   END                   wait 0H      day 10.00
```

**Connection note:** 1 `CONNECTION_REQUEST` note slot(s), every one of them EMPTY — this campaign sends connection requests with no note.

**Message steps — our text, in full:**

- message at day 0.00, 1 variant(s):
  - variant 1 (242 chars, 44 words): `Hi {FIRST_NAME}, a colleague of mine was in touch with you over email a while back about Productive, and then things went quiet, which happens, no worries there. Figured I'd try reaching you here instead, do you have some time to take a look?`
  - fallback (229 chars): `Hi, a colleague of mine was in touch with you over email a while back about Productive, and then things went quiet, which happens, no worries there. Figured I'd try reaching you here instead, do you have some time to take a look?`
- message at day 5.00, 2 variant(s):
  - variant 1 (188 chars, 43 words): `Would you like me to show you around, or would it be easier if I sent a few materials over first so you can take a look on your own time?

Or let me know if you'd like for me to stop here.`
  - variant 2 (289 chars, 49 words): `for context in case it's useful, Productive's basically a way to stop juggling separate tools for projects, time tracking and budgets, and see project profitability in real time instead of after the fact. if that's relevant for your company I'm happy to show you around. what do you think?`
  - fallback (188 chars): `Would you like me to show you around, or would it be easier if I sent a few materials over first so you can take a look on your own time?

Or let me know if you'd like for me to stop here.`

### 594057 — PRODUCTIVE - CANARY - 2026-09-09

- ownership: **unknown** — not in the ledger and not on any operator-declared internal list; UNKNOWN is the state, not a gap
- provider status `DRAFT`; created `2026-09-09T18:04:12.382209Z`; started `never`
- seats (`campaignAccountIds`): none
- lead list `0` (unnamed), list size `totalItemsCount` = None; campaign holds `progressStats.totalUsers` = None, finished None
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **0**, accepted **0** (n/a (denominator 0))
  - messages sent **0**, message threads started **0**, replies **0** (n/a (denominator 0) of threads started)
  - unique leads contacted **0**; profile views 0, follows 0, post likes 0
  - provider's own tags: `autoTaggedInterested` **0**, `totalAutoTagged` **0**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 0 conversations joined, 0 operator-positive replies = **n/a (0 requests sent) per 100 requests sent**
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- sequence: **could not be read** — `ProviderError: heyreach /campaign/GetCampaignSequence: unexpected response shape`

### 594060 — PRODUCTIVE - CANARY - 2026-09-09

- ownership: **unknown** — not in the ledger and not on any operator-declared internal list; UNKNOWN is the state, not a gap
- provider status `DRAFT`; created `2026-09-09T18:06:41.667176Z`; started `never`
- seats (`campaignAccountIds`): none
- lead list `0` (unnamed), list size `totalItemsCount` = None; campaign holds `progressStats.totalUsers` = None, finished None
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **0**, accepted **0** (n/a (denominator 0))
  - messages sent **0**, message threads started **0**, replies **0** (n/a (denominator 0) of threads started)
  - unique leads contacted **0**; profile views 0, follows 0, post likes 0
  - provider's own tags: `autoTaggedInterested` **0**, `totalAutoTagged` **0**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 0 conversations joined, 0 operator-positive replies = **n/a (0 requests sent) per 100 requests sent**
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- sequence: **could not be read** — `ProviderError: heyreach /campaign/GetCampaignSequence: unexpected response shape`

### 594061 — PRODUCTIVE - CANARY - 2026-09-09

- ownership: **resonate_os** — `heyreach_campaign_id` present in `work/campaigns.jsonl`
- provider status `PAUSED`; created `2026-09-09T18:06:46.630247Z`; started `2026-09-09T18:07:51.628018Z`
- seats (`campaignAccountIds`): 116968
- lead list `926076` (PRODUCTIVE - CANARY - 2026-09-09), list size `totalItemsCount` = 1; campaign holds `progressStats.totalUsers` = 1, finished 0
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **0**, accepted **0** (n/a (denominator 0))
  - messages sent **0**, message threads started **0**, replies **0** (n/a (denominator 0) of threads started)
  - unique leads contacted **0**; profile views 0, follows 0, post likes 0
  - provider's own tags: `autoTaggedInterested` **0**, `totalAutoTagged` **0**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 0 conversations joined, 0 operator-positive replies = **n/a (0 requests sent) per 100 requests sent**
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- sequence node types present in the whole graph: CONNECTION_REQUEST, END
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CONNECTION_REQUEST    wait 0H      day  0.00
  step 1   END                   wait 1D      day  1.00
```

**Connection note — our text, in full (1 variant(s)):**

1. (125 chars, 21 words) `hi Brooke, i work with Design Services teams on utilisation. curious how Nineyards handles it at your size. happy to connect.`


### 599020 — RESONATE - PRODUCTIVE LINKEDIN PRODUCTION V1

- ownership: **resonate_os** — `heyreach_campaign_id` present in `work/campaigns.jsonl`
- provider status `FINISHED`; created `2026-09-13T10:33:37.258848Z`; started `2026-09-15T19:38:29.894936Z`
- seats (`campaignAccountIds`): 174892
- lead list `933603` (RESONATE - PRODUCTIVE LINKEDIN PRODUCTION V1), list size `totalItemsCount` = 0; campaign holds `progressStats.totalUsers` = 0, finished 0
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **0**, accepted **0** (n/a (denominator 0))
  - messages sent **0**, message threads started **0**, replies **0** (n/a (denominator 0) of threads started)
  - unique leads contacted **0**; profile views 0, follows 0, post likes 0
  - provider's own tags: `autoTaggedInterested` **0**, `totalAutoTagged` **0**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 0 conversations joined, 0 operator-positive replies = **n/a (0 requests sent) per 100 requests sent**
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- sequence node types present in the whole graph: CHECK_IS_CONNECTION, CONNECTION_REQUEST, END, FOLLOW, MESSAGE, VIEW_PROFILE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CHECK_IS_CONNECTION   wait 0H      day  0.00
  step 1   MESSAGE               wait 3H      day  0.12
  step 2   MESSAGE               wait 3D      day  3.12
  step 3   VIEW_PROFILE          wait 2D      day  5.12
  step 4   MESSAGE               wait 5D      day 10.12
  step 5   MESSAGE               wait 7D      day 17.12
  step 6   END                   wait 3H      day 17.25
```

**Connection note — our text, in full (1 variant(s)):**

1. (17 chars, 1 words) `{connection_note}`

**Message steps — our text, in full:**

- message at day 0.12, 1 variant(s):
  - variant 1 (13 chars, 1 words): `{connected_1}`
  - fallback (99 chars): `how do you currently get visibility on whether a project is making money while it is still running?`
- message at day 3.12, 1 variant(s):
  - variant 1 (13 chars, 1 words): `{connected_2}`
  - fallback (115 chars): `most agencies i speak to find that out at the end of a project rather than during it. is that how it works for you?`
- message at day 10.12, 1 variant(s):
  - variant 1 (13 chars, 1 words): `{connected_3}`
  - fallback (94 chars): `we built productive so budgets, time tracking and resourcing talk to each other. worth a look?`
- message at day 17.12, 1 variant(s):
  - variant 1 (13 chars, 1 words): `{connected_4}`
  - fallback (83 chars): `happy to leave it here if the timing is wrong. is there someone else who owns this?`

### 604869 — RESONATE - PRODUCTIVE LINKEDIN CANARY - CONTROL

- ownership: **resonate_os** — `heyreach_campaign_id` present in `work/campaigns.jsonl`
- provider status `DRAFT`; created `2026-09-16T13:20:25.548645Z`; started `never`
- seats (`campaignAccountIds`): 174892
- lead list `940797` (RESONATE - STAGING PROBE - DO NOT USE), list size `totalItemsCount` = 1; campaign holds `progressStats.totalUsers` = 0, finished 0
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **0**, accepted **0** (n/a (denominator 0))
  - messages sent **0**, message threads started **0**, replies **0** (n/a (denominator 0) of threads started)
  - unique leads contacted **0**; profile views 0, follows 0, post likes 0
  - provider's own tags: `autoTaggedInterested` **0**, `totalAutoTagged` **0**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 0 conversations joined, 0 operator-positive replies = **n/a (0 requests sent) per 100 requests sent**
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- sequence node types present in the whole graph: CHECK_IS_CONNECTION, CONNECTION_REQUEST, END, FOLLOW, MESSAGE, VIEW_PROFILE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CHECK_IS_CONNECTION   wait 0H      day  0.00
  step 1   MESSAGE               wait 3H      day  0.12
  step 2   MESSAGE               wait 3D      day  3.12
  step 3   VIEW_PROFILE          wait 2D      day  5.12
  step 4   MESSAGE               wait 5D      day 10.12
  step 5   MESSAGE               wait 7D      day 17.12
  step 6   END                   wait 3H      day 17.25
```

**Connection note — our text, in full (1 variant(s)):**

1. (17 chars, 1 words) `{connection_note}`

**Message steps — our text, in full:**

- message at day 0.12, 1 variant(s):
  - variant 1 (13 chars, 1 words): `{connected_1}`
  - fallback (99 chars): `how do you currently get visibility on whether a project is making money while it is still running?`
- message at day 3.12, 1 variant(s):
  - variant 1 (13 chars, 1 words): `{connected_2}`
  - fallback (115 chars): `most agencies i speak to find that out at the end of a project rather than during it. is that how it works for you?`
- message at day 10.12, 1 variant(s):
  - variant 1 (13 chars, 1 words): `{connected_3}`
  - fallback (94 chars): `we built productive so budgets, time tracking and resourcing talk to each other. worth a look?`
- message at day 17.12, 1 variant(s):
  - variant 1 (13 chars, 1 words): `{connected_4}`
  - fallback (83 chars): `happy to leave it here if the timing is wrong. is there someone else who owns this?`

### 605487 — RESONATE - PRODUCTIVE LINKEDIN COHORT V1 - CONTROL

- ownership: **resonate_os** — `heyreach_campaign_id` present in `work/campaigns.jsonl`
- provider status `DRAFT`; created `2026-09-16T18:01:00.578803Z`; started `never`
- seats (`campaignAccountIds`): 174892
- lead list `943957` (RESONATE - PRODUCTIVE LINKEDIN COHORT 2026-09-16), list size `totalItemsCount` = 4; campaign holds `progressStats.totalUsers` = 0, finished 0
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **0**, accepted **0** (n/a (denominator 0))
  - messages sent **0**, message threads started **0**, replies **0** (n/a (denominator 0) of threads started)
  - unique leads contacted **0**; profile views 0, follows 0, post likes 0
  - provider's own tags: `autoTaggedInterested` **0**, `totalAutoTagged` **0**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 0 conversations joined, 0 operator-positive replies = **n/a (0 requests sent) per 100 requests sent**
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- sequence node types present in the whole graph: CHECK_IS_CONNECTION, CONNECTION_REQUEST, END, FOLLOW, MESSAGE, VIEW_PROFILE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CHECK_IS_CONNECTION   wait 0H      day  0.00
  step 1   MESSAGE               wait 3H      day  0.12
  step 2   MESSAGE               wait 3D      day  3.12
  step 3   VIEW_PROFILE          wait 2D      day  5.12
  step 4   MESSAGE               wait 5D      day 10.12
  step 5   MESSAGE               wait 7D      day 17.12
  step 6   END                   wait 3H      day 17.25
```

**Connection note — our text, in full (1 variant(s)):**

1. (17 chars, 1 words) `{connection_note}`

**Message steps — our text, in full:**

- message at day 0.12, 1 variant(s):
  - variant 1 (13 chars, 1 words): `{connected_1}`
  - fallback (99 chars): `how do you currently get visibility on whether a project is making money while it is still running?`
- message at day 3.12, 1 variant(s):
  - variant 1 (13 chars, 1 words): `{connected_2}`
  - fallback (115 chars): `most agencies i speak to find that out at the end of a project rather than during it. is that how it works for you?`
- message at day 10.12, 1 variant(s):
  - variant 1 (13 chars, 1 words): `{connected_3}`
  - fallback (94 chars): `we built productive so budgets, time tracking and resourcing talk to each other. worth a look?`
- message at day 17.12, 1 variant(s):
  - variant 1 (13 chars, 1 words): `{connected_4}`
  - fallback (83 chars): `happy to leave it here if the timing is wrong. is there someone else who owns this?`

### 605732 — RESONATE - PRODUCTIVE LINKEDIN COHORT V2 - CONTROL

- ownership: **resonate_os** — `heyreach_campaign_id` present in `work/campaigns.jsonl`
- provider status `PAUSED`; created `2026-09-16T19:57:32.64775Z`; started `2026-09-16T20:12:25.073226Z`
- seats (`campaignAccountIds`): 174892
- lead list `944355` (RESONATE - PRODUCTIVE LINKEDIN COHORT 2026-09-16 B), list size `totalItemsCount` = 3; campaign holds `progressStats.totalUsers` = 3, finished 0
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **3**, accepted **0** (0.00%)
  - messages sent **0**, message threads started **0**, replies **0** (n/a (denominator 0) of threads started)
  - unique leads contacted **3**; profile views 3, follows 3, post likes 0
  - provider's own tags: `autoTaggedInterested` **0**, `totalAutoTagged` **0**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 0 conversations joined, 0 operator-positive replies = **0.000 per 100 requests sent**
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-09-22 .. 2026-09-22 (1 days)
- sequence node types present in the whole graph: CHECK_IS_CONNECTION, CONNECTION_REQUEST, END, FOLLOW, MESSAGE, VIEW_PROFILE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CHECK_IS_CONNECTION   wait 0H      day  0.00
  step 1   MESSAGE               wait 3H      day  0.12
  step 2   MESSAGE               wait 3D      day  3.12
  step 3   VIEW_PROFILE          wait 2D      day  5.12
  step 4   MESSAGE               wait 5D      day 10.12
  step 5   MESSAGE               wait 7D      day 17.12
  step 6   END                   wait 3H      day 17.25
```

**Connection note — our text, in full (1 variant(s)):**

1. (17 chars, 1 words) `{connection_note}`

**Message steps — our text, in full:**

- message at day 0.12, 1 variant(s):
  - variant 1 (13 chars, 1 words): `{connected_1}`
  - fallback (99 chars): `how do you currently get visibility on whether a project is making money while it is still running?`
- message at day 3.12, 1 variant(s):
  - variant 1 (13 chars, 1 words): `{connected_2}`
  - fallback (115 chars): `most agencies i speak to find that out at the end of a project rather than during it. is that how it works for you?`
- message at day 10.12, 1 variant(s):
  - variant 1 (13 chars, 1 words): `{connected_3}`
  - fallback (94 chars): `we built productive so budgets, time tracking and resourcing talk to each other. worth a look?`
- message at day 17.12, 1 variant(s):
  - variant 1 (13 chars, 1 words): `{connected_4}`
  - fallback (83 chars): `happy to leave it here if the timing is wrong. is there someone else who owns this?`

### 613724 — RESONATE PRODUCTIVE LI B1 SEAT 116968

- ownership: **resonate_os** — `heyreach_campaign_id` present in `work/campaigns.jsonl`
- provider status `PAUSED`; created `2026-09-21T21:25:11.349106Z`; started `2026-09-22T09:10:21.299776Z`
- seats (`campaignAccountIds`): 116968
- lead list `956310` (RESONATE PRODUCTIVE LI B1 SEAT 116968), list size `totalItemsCount` = 5; campaign holds `progressStats.totalUsers` = 5, finished 0
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **5**, accepted **0** (0.00%)
  - messages sent **0**, message threads started **0**, replies **0** (n/a (denominator 0) of threads started)
  - unique leads contacted **5**; profile views 0, follows 5, post likes 0
  - provider's own tags: `autoTaggedInterested` **0**, `totalAutoTagged` **0**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 0 conversations joined, 0 operator-positive replies = **0.000 per 100 requests sent**
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-09-22 .. 2026-09-22 (1 days)
- sequence node types present in the whole graph: CHECK_IS_CONNECTION, CONNECTION_REQUEST, END, FOLLOW, MESSAGE, VIEW_PROFILE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CHECK_IS_CONNECTION   wait 0H      day  0.00
  step 1   MESSAGE               wait 0H      day  0.00
  step 2   MESSAGE               wait 5D      day  5.00
  step 3   MESSAGE               wait 5D      day 10.00
  step 4   END                   wait 3D      day 13.00
```

**Connection note:** 1 `CONNECTION_REQUEST` note slot(s), every one of them EMPTY — this campaign sends connection requests with no note.

**Message steps — our text, in full:**

- message at day 0.00, 3 variant(s):
  - variant 1 (283 chars, 46 words): `Hey {FIRST_NAME},

{Icebreaker}
 
We built Productive so budgets, time tracking and resourcing actually talk to each other, so you can see if a project's making money while it's still running, not just after it gets invoiced.
 
Can show you what that looks like if you're interested.`
  - variant 2 (233 chars, 39 words): `Hi {FIRST_NAME}, {Icebreaker}
 
It's a common one. Productive ties budgets, time and resourcing together so that question has a live answer instead of one you get after the invoice goes out. Can walk you through it if you're curious.`
  - variant 3 (233 chars, 34 words): `Hey {FIRST_NAME},
 
{Icebreaker}
 
That's basically why we built Productive, so budgets, time tracking and resourcing stop living in separate places and you can see project profitability while it's still happening. Happy to show you.`
  - fallback (256 chars): `Hey, we built Productive so budgets, time tracking and resourcing actually talk to each other, so you can see if a project's making money while it's still running, not just after it gets invoiced.
 
Can show you what that looks like if you're interested.

`
- message at day 5.00, 2 variant(s):
  - variant 1 (251 chars, 37 words): `{FIRST_NAME}, random one, but Infinum (software agency, 370+ people) uses Productive to plan resourcing across the whole team without losing sight of which projects are actually profitable.
 
Would something like this make sense for {COMPANY} as well?`
  - variant 2 (253 chars, 41 words): `{FIRST_NAME}, Akcelo (190 people, works with McDonald's and Netflix) uses Productive to stay on top of budgets and reporting across every project. PIABO runs basically the same setup across five offices in Europe. Could it be worth a look for {COMPANY}?`
  - fallback (237 chars): `Random one, but Infinum (software agency, 370+ people) uses Productive to plan resourcing across the whole team without losing sight of which projects are actually profitable.
 
Would something like this make sense for your team as well?`
- message at day 10.00, 4 variant(s):
  - variant 1 (83 chars, 17 words): `{FIRST_NAME}, worth a yes or no on this one so I know whether to stop reaching out?`
  - variant 2 (84 chars, 17 words): `{FIRST_NAME}, should I drop this or send you an overview if you want to take a look?`
  - variant 3 (51 chars, 9 words): `Worth a look, {FIRST_NAME}? I can send an overview.`
  - variant 4 (59 chars, 10 words): `Is this worth pursuing or should I stop here, {FIRST_NAME}?`
  - fallback (69 chars): `Worth a yes or no on this one so I know whether to stop reaching out?`

### 613725 — RESONATE PRODUCTIVE LI B1 SEAT 116973

- ownership: **resonate_os** — `heyreach_campaign_id` present in `work/campaigns.jsonl`
- provider status `PAUSED`; created `2026-09-21T21:25:14.1804Z`; started `2026-09-22T09:10:22.219001Z`
- seats (`campaignAccountIds`): 116973
- lead list `956311` (RESONATE PRODUCTIVE LI B1 SEAT 116973), list size `totalItemsCount` = 5; campaign holds `progressStats.totalUsers` = 5, finished 0
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **5**, accepted **0** (0.00%)
  - messages sent **0**, message threads started **0**, replies **0** (n/a (denominator 0) of threads started)
  - unique leads contacted **5**; profile views 0, follows 5, post likes 0
  - provider's own tags: `autoTaggedInterested` **0**, `totalAutoTagged` **0**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 0 conversations joined, 0 operator-positive replies = **0.000 per 100 requests sent**
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-09-22 .. 2026-09-22 (1 days)
- sequence node types present in the whole graph: CHECK_IS_CONNECTION, CONNECTION_REQUEST, END, FOLLOW, MESSAGE, VIEW_PROFILE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CHECK_IS_CONNECTION   wait 0H      day  0.00
  step 1   MESSAGE               wait 0H      day  0.00
  step 2   MESSAGE               wait 5D      day  5.00
  step 3   MESSAGE               wait 5D      day 10.00
  step 4   END                   wait 3D      day 13.00
```

**Connection note:** 1 `CONNECTION_REQUEST` note slot(s), every one of them EMPTY — this campaign sends connection requests with no note.

**Message steps — our text, in full:**

- message at day 0.00, 3 variant(s):
  - variant 1 (283 chars, 46 words): `Hey {FIRST_NAME},

{Icebreaker}
 
We built Productive so budgets, time tracking and resourcing actually talk to each other, so you can see if a project's making money while it's still running, not just after it gets invoiced.
 
Can show you what that looks like if you're interested.`
  - variant 2 (233 chars, 39 words): `Hi {FIRST_NAME}, {Icebreaker}
 
It's a common one. Productive ties budgets, time and resourcing together so that question has a live answer instead of one you get after the invoice goes out. Can walk you through it if you're curious.`
  - variant 3 (233 chars, 34 words): `Hey {FIRST_NAME},
 
{Icebreaker}
 
That's basically why we built Productive, so budgets, time tracking and resourcing stop living in separate places and you can see project profitability while it's still happening. Happy to show you.`
  - fallback (256 chars): `Hey, we built Productive so budgets, time tracking and resourcing actually talk to each other, so you can see if a project's making money while it's still running, not just after it gets invoiced.
 
Can show you what that looks like if you're interested.

`
- message at day 5.00, 2 variant(s):
  - variant 1 (251 chars, 37 words): `{FIRST_NAME}, random one, but Infinum (software agency, 370+ people) uses Productive to plan resourcing across the whole team without losing sight of which projects are actually profitable.
 
Would something like this make sense for {COMPANY} as well?`
  - variant 2 (253 chars, 41 words): `{FIRST_NAME}, Akcelo (190 people, works with McDonald's and Netflix) uses Productive to stay on top of budgets and reporting across every project. PIABO runs basically the same setup across five offices in Europe. Could it be worth a look for {COMPANY}?`
  - fallback (237 chars): `Random one, but Infinum (software agency, 370+ people) uses Productive to plan resourcing across the whole team without losing sight of which projects are actually profitable.
 
Would something like this make sense for your team as well?`
- message at day 10.00, 4 variant(s):
  - variant 1 (83 chars, 17 words): `{FIRST_NAME}, worth a yes or no on this one so I know whether to stop reaching out?`
  - variant 2 (84 chars, 17 words): `{FIRST_NAME}, should I drop this or send you an overview if you want to take a look?`
  - variant 3 (51 chars, 9 words): `Worth a look, {FIRST_NAME}? I can send an overview.`
  - variant 4 (59 chars, 10 words): `Is this worth pursuing or should I stop here, {FIRST_NAME}?`
  - fallback (69 chars): `Worth a yes or no on this one so I know whether to stop reaching out?`

### 613726 — RESONATE PRODUCTIVE LI B1 SEAT 116988

- ownership: **resonate_os** — `heyreach_campaign_id` present in `work/campaigns.jsonl`
- provider status `PAUSED`; created `2026-09-21T21:25:17.218589Z`; started `2026-09-22T09:10:23.799762Z`
- seats (`campaignAccountIds`): 116988
- lead list `956312` (RESONATE PRODUCTIVE LI B1 SEAT 116988), list size `totalItemsCount` = 5; campaign holds `progressStats.totalUsers` = 5, finished 0
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **5**, accepted **1** (20.00%)
  - messages sent **0**, message threads started **1**, replies **0** (0.00% of threads started)
  - unique leads contacted **5**; profile views 0, follows 5, post likes 0
  - provider's own tags: `autoTaggedInterested` **0**, `totalAutoTagged` **0**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 1 conversations joined, 0 operator-positive replies = **0.000 per 100 requests sent**
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-09-22 .. 2026-09-23 (2 days)
- sequence node types present in the whole graph: CHECK_IS_CONNECTION, CONNECTION_REQUEST, END, FOLLOW, MESSAGE, VIEW_PROFILE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CHECK_IS_CONNECTION   wait 0H      day  0.00
  step 1   MESSAGE               wait 0H      day  0.00
  step 2   MESSAGE               wait 5D      day  5.00
  step 3   MESSAGE               wait 5D      day 10.00
  step 4   END                   wait 3D      day 13.00
```

**Connection note:** 1 `CONNECTION_REQUEST` note slot(s), every one of them EMPTY — this campaign sends connection requests with no note.

**Message steps — our text, in full:**

- message at day 0.00, 3 variant(s):
  - variant 1 (283 chars, 46 words): `Hey {FIRST_NAME},

{Icebreaker}
 
We built Productive so budgets, time tracking and resourcing actually talk to each other, so you can see if a project's making money while it's still running, not just after it gets invoiced.
 
Can show you what that looks like if you're interested.`
  - variant 2 (233 chars, 39 words): `Hi {FIRST_NAME}, {Icebreaker}
 
It's a common one. Productive ties budgets, time and resourcing together so that question has a live answer instead of one you get after the invoice goes out. Can walk you through it if you're curious.`
  - variant 3 (233 chars, 34 words): `Hey {FIRST_NAME},
 
{Icebreaker}
 
That's basically why we built Productive, so budgets, time tracking and resourcing stop living in separate places and you can see project profitability while it's still happening. Happy to show you.`
  - fallback (256 chars): `Hey, we built Productive so budgets, time tracking and resourcing actually talk to each other, so you can see if a project's making money while it's still running, not just after it gets invoiced.
 
Can show you what that looks like if you're interested.

`
- message at day 5.00, 2 variant(s):
  - variant 1 (251 chars, 37 words): `{FIRST_NAME}, random one, but Infinum (software agency, 370+ people) uses Productive to plan resourcing across the whole team without losing sight of which projects are actually profitable.
 
Would something like this make sense for {COMPANY} as well?`
  - variant 2 (253 chars, 41 words): `{FIRST_NAME}, Akcelo (190 people, works with McDonald's and Netflix) uses Productive to stay on top of budgets and reporting across every project. PIABO runs basically the same setup across five offices in Europe. Could it be worth a look for {COMPANY}?`
  - fallback (237 chars): `Random one, but Infinum (software agency, 370+ people) uses Productive to plan resourcing across the whole team without losing sight of which projects are actually profitable.
 
Would something like this make sense for your team as well?`
- message at day 10.00, 4 variant(s):
  - variant 1 (83 chars, 17 words): `{FIRST_NAME}, worth a yes or no on this one so I know whether to stop reaching out?`
  - variant 2 (84 chars, 17 words): `{FIRST_NAME}, should I drop this or send you an overview if you want to take a look?`
  - variant 3 (51 chars, 9 words): `Worth a look, {FIRST_NAME}? I can send an overview.`
  - variant 4 (59 chars, 10 words): `Is this worth pursuing or should I stop here, {FIRST_NAME}?`
  - fallback (69 chars): `Worth a yes or no on this one so I know whether to stop reaching out?`

### 613727 — RESONATE PRODUCTIVE LI B1 SEAT 116989

- ownership: **resonate_os** — `heyreach_campaign_id` present in `work/campaigns.jsonl`
- provider status `PAUSED`; created `2026-09-21T21:25:21.915838Z`; started `2026-09-22T09:10:26.068019Z`
- seats (`campaignAccountIds`): 116989
- lead list `956313` (RESONATE PRODUCTIVE LI B1 SEAT 116989), list size `totalItemsCount` = 5; campaign holds `progressStats.totalUsers` = 5, finished 0
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **5**, accepted **1** (20.00%)
  - messages sent **1**, message threads started **1**, replies **0** (0.00% of threads started)
  - unique leads contacted **5**; profile views 0, follows 5, post likes 0
  - provider's own tags: `autoTaggedInterested` **0**, `totalAutoTagged` **0**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 1 conversations joined, 0 operator-positive replies = **0.000 per 100 requests sent**
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-09-22 .. 2026-09-28 (2 days)
- sequence node types present in the whole graph: CHECK_IS_CONNECTION, CONNECTION_REQUEST, END, FOLLOW, MESSAGE, VIEW_PROFILE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CHECK_IS_CONNECTION   wait 0H      day  0.00
  step 1   MESSAGE               wait 0H      day  0.00
  step 2   MESSAGE               wait 5D      day  5.00
  step 3   MESSAGE               wait 5D      day 10.00
  step 4   END                   wait 3D      day 13.00
```

**Connection note:** 1 `CONNECTION_REQUEST` note slot(s), every one of them EMPTY — this campaign sends connection requests with no note.

**Message steps — our text, in full:**

- message at day 0.00, 3 variant(s):
  - variant 1 (283 chars, 46 words): `Hey {FIRST_NAME},

{Icebreaker}
 
We built Productive so budgets, time tracking and resourcing actually talk to each other, so you can see if a project's making money while it's still running, not just after it gets invoiced.
 
Can show you what that looks like if you're interested.`
  - variant 2 (233 chars, 39 words): `Hi {FIRST_NAME}, {Icebreaker}
 
It's a common one. Productive ties budgets, time and resourcing together so that question has a live answer instead of one you get after the invoice goes out. Can walk you through it if you're curious.`
  - variant 3 (233 chars, 34 words): `Hey {FIRST_NAME},
 
{Icebreaker}
 
That's basically why we built Productive, so budgets, time tracking and resourcing stop living in separate places and you can see project profitability while it's still happening. Happy to show you.`
  - fallback (256 chars): `Hey, we built Productive so budgets, time tracking and resourcing actually talk to each other, so you can see if a project's making money while it's still running, not just after it gets invoiced.
 
Can show you what that looks like if you're interested.

`
- message at day 5.00, 2 variant(s):
  - variant 1 (251 chars, 37 words): `{FIRST_NAME}, random one, but Infinum (software agency, 370+ people) uses Productive to plan resourcing across the whole team without losing sight of which projects are actually profitable.
 
Would something like this make sense for {COMPANY} as well?`
  - variant 2 (253 chars, 41 words): `{FIRST_NAME}, Akcelo (190 people, works with McDonald's and Netflix) uses Productive to stay on top of budgets and reporting across every project. PIABO runs basically the same setup across five offices in Europe. Could it be worth a look for {COMPANY}?`
  - fallback (237 chars): `Random one, but Infinum (software agency, 370+ people) uses Productive to plan resourcing across the whole team without losing sight of which projects are actually profitable.
 
Would something like this make sense for your team as well?`
- message at day 10.00, 4 variant(s):
  - variant 1 (83 chars, 17 words): `{FIRST_NAME}, worth a yes or no on this one so I know whether to stop reaching out?`
  - variant 2 (84 chars, 17 words): `{FIRST_NAME}, should I drop this or send you an overview if you want to take a look?`
  - variant 3 (51 chars, 9 words): `Worth a look, {FIRST_NAME}? I can send an overview.`
  - variant 4 (59 chars, 10 words): `Is this worth pursuing or should I stop here, {FIRST_NAME}?`
  - fallback (69 chars): `Worth a yes or no on this one so I know whether to stop reaching out?`

### 613728 — RESONATE PRODUCTIVE LI B1 SEAT 119588

- ownership: **resonate_os** — `heyreach_campaign_id` present in `work/campaigns.jsonl`
- provider status `PAUSED`; created `2026-09-21T21:25:25.121066Z`; started `2026-09-22T09:10:27.14311Z`
- seats (`campaignAccountIds`): 119588
- lead list `956314` (RESONATE PRODUCTIVE LI B1 SEAT 119588), list size `totalItemsCount` = 5; campaign holds `progressStats.totalUsers` = 5, finished 0
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **5**, accepted **0** (0.00%)
  - messages sent **0**, message threads started **0**, replies **0** (n/a (denominator 0) of threads started)
  - unique leads contacted **5**; profile views 0, follows 5, post likes 0
  - provider's own tags: `autoTaggedInterested` **0**, `totalAutoTagged` **0**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 0 conversations joined, 0 operator-positive replies = **0.000 per 100 requests sent**
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-09-22 .. 2026-09-23 (2 days)
- sequence node types present in the whole graph: CHECK_IS_CONNECTION, CONNECTION_REQUEST, END, FOLLOW, MESSAGE, VIEW_PROFILE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CHECK_IS_CONNECTION   wait 0H      day  0.00
  step 1   MESSAGE               wait 0H      day  0.00
  step 2   MESSAGE               wait 5D      day  5.00
  step 3   MESSAGE               wait 5D      day 10.00
  step 4   END                   wait 3D      day 13.00
```

**Connection note:** 1 `CONNECTION_REQUEST` note slot(s), every one of them EMPTY — this campaign sends connection requests with no note.

**Message steps — our text, in full:**

- message at day 0.00, 3 variant(s):
  - variant 1 (283 chars, 46 words): `Hey {FIRST_NAME},

{Icebreaker}
 
We built Productive so budgets, time tracking and resourcing actually talk to each other, so you can see if a project's making money while it's still running, not just after it gets invoiced.
 
Can show you what that looks like if you're interested.`
  - variant 2 (233 chars, 39 words): `Hi {FIRST_NAME}, {Icebreaker}
 
It's a common one. Productive ties budgets, time and resourcing together so that question has a live answer instead of one you get after the invoice goes out. Can walk you through it if you're curious.`
  - variant 3 (233 chars, 34 words): `Hey {FIRST_NAME},
 
{Icebreaker}
 
That's basically why we built Productive, so budgets, time tracking and resourcing stop living in separate places and you can see project profitability while it's still happening. Happy to show you.`
  - fallback (256 chars): `Hey, we built Productive so budgets, time tracking and resourcing actually talk to each other, so you can see if a project's making money while it's still running, not just after it gets invoiced.
 
Can show you what that looks like if you're interested.

`
- message at day 5.00, 2 variant(s):
  - variant 1 (251 chars, 37 words): `{FIRST_NAME}, random one, but Infinum (software agency, 370+ people) uses Productive to plan resourcing across the whole team without losing sight of which projects are actually profitable.
 
Would something like this make sense for {COMPANY} as well?`
  - variant 2 (253 chars, 41 words): `{FIRST_NAME}, Akcelo (190 people, works with McDonald's and Netflix) uses Productive to stay on top of budgets and reporting across every project. PIABO runs basically the same setup across five offices in Europe. Could it be worth a look for {COMPANY}?`
  - fallback (237 chars): `Random one, but Infinum (software agency, 370+ people) uses Productive to plan resourcing across the whole team without losing sight of which projects are actually profitable.
 
Would something like this make sense for your team as well?`
- message at day 10.00, 4 variant(s):
  - variant 1 (83 chars, 17 words): `{FIRST_NAME}, worth a yes or no on this one so I know whether to stop reaching out?`
  - variant 2 (84 chars, 17 words): `{FIRST_NAME}, should I drop this or send you an overview if you want to take a look?`
  - variant 3 (51 chars, 9 words): `Worth a look, {FIRST_NAME}? I can send an overview.`
  - variant 4 (59 chars, 10 words): `Is this worth pursuing or should I stop here, {FIRST_NAME}?`
  - fallback (69 chars): `Worth a yes or no on this one so I know whether to stop reaching out?`

### 613729 — RESONATE PRODUCTIVE LI B1 SEAT 125748

- ownership: **resonate_os** — `heyreach_campaign_id` present in `work/campaigns.jsonl`
- provider status `PAUSED`; created `2026-09-21T21:25:27.84745Z`; started `2026-09-22T09:10:28.564708Z`
- seats (`campaignAccountIds`): 125748
- lead list `956315` (RESONATE PRODUCTIVE LI B1 SEAT 125748), list size `totalItemsCount` = 5; campaign holds `progressStats.totalUsers` = 5, finished 0
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **5**, accepted **1** (20.00%)
  - messages sent **0**, message threads started **1**, replies **0** (0.00% of threads started)
  - unique leads contacted **5**; profile views 0, follows 5, post likes 0
  - provider's own tags: `autoTaggedInterested` **0**, `totalAutoTagged` **0**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 1 conversations joined, 0 operator-positive replies = **0.000 per 100 requests sent**
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-09-22 .. 2026-09-23 (2 days)
- sequence node types present in the whole graph: CHECK_IS_CONNECTION, CONNECTION_REQUEST, END, FOLLOW, MESSAGE, VIEW_PROFILE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CHECK_IS_CONNECTION   wait 0H      day  0.00
  step 1   MESSAGE               wait 0H      day  0.00
  step 2   MESSAGE               wait 5D      day  5.00
  step 3   MESSAGE               wait 5D      day 10.00
  step 4   END                   wait 3D      day 13.00
```

**Connection note:** 1 `CONNECTION_REQUEST` note slot(s), every one of them EMPTY — this campaign sends connection requests with no note.

**Message steps — our text, in full:**

- message at day 0.00, 3 variant(s):
  - variant 1 (283 chars, 46 words): `Hey {FIRST_NAME},

{Icebreaker}
 
We built Productive so budgets, time tracking and resourcing actually talk to each other, so you can see if a project's making money while it's still running, not just after it gets invoiced.
 
Can show you what that looks like if you're interested.`
  - variant 2 (233 chars, 39 words): `Hi {FIRST_NAME}, {Icebreaker}
 
It's a common one. Productive ties budgets, time and resourcing together so that question has a live answer instead of one you get after the invoice goes out. Can walk you through it if you're curious.`
  - variant 3 (233 chars, 34 words): `Hey {FIRST_NAME},
 
{Icebreaker}
 
That's basically why we built Productive, so budgets, time tracking and resourcing stop living in separate places and you can see project profitability while it's still happening. Happy to show you.`
  - fallback (256 chars): `Hey, we built Productive so budgets, time tracking and resourcing actually talk to each other, so you can see if a project's making money while it's still running, not just after it gets invoiced.
 
Can show you what that looks like if you're interested.

`
- message at day 5.00, 2 variant(s):
  - variant 1 (251 chars, 37 words): `{FIRST_NAME}, random one, but Infinum (software agency, 370+ people) uses Productive to plan resourcing across the whole team without losing sight of which projects are actually profitable.
 
Would something like this make sense for {COMPANY} as well?`
  - variant 2 (253 chars, 41 words): `{FIRST_NAME}, Akcelo (190 people, works with McDonald's and Netflix) uses Productive to stay on top of budgets and reporting across every project. PIABO runs basically the same setup across five offices in Europe. Could it be worth a look for {COMPANY}?`
  - fallback (237 chars): `Random one, but Infinum (software agency, 370+ people) uses Productive to plan resourcing across the whole team without losing sight of which projects are actually profitable.
 
Would something like this make sense for your team as well?`
- message at day 10.00, 4 variant(s):
  - variant 1 (83 chars, 17 words): `{FIRST_NAME}, worth a yes or no on this one so I know whether to stop reaching out?`
  - variant 2 (84 chars, 17 words): `{FIRST_NAME}, should I drop this or send you an overview if you want to take a look?`
  - variant 3 (51 chars, 9 words): `Worth a look, {FIRST_NAME}? I can send an overview.`
  - variant 4 (59 chars, 10 words): `Is this worth pursuing or should I stop here, {FIRST_NAME}?`
  - fallback (69 chars): `Worth a yes or no on this one so I know whether to stop reaching out?`

### 613730 — RESONATE PRODUCTIVE LI B1 SEAT 125775

- ownership: **resonate_os** — `heyreach_campaign_id` present in `work/campaigns.jsonl`
- provider status `PAUSED`; created `2026-09-21T21:25:30.258166Z`; started `2026-09-22T09:10:29.708856Z`
- seats (`campaignAccountIds`): 125775
- lead list `956316` (RESONATE PRODUCTIVE LI B1 SEAT 125775), list size `totalItemsCount` = 5; campaign holds `progressStats.totalUsers` = 5, finished 0
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **5**, accepted **0** (0.00%)
  - messages sent **0**, message threads started **0**, replies **0** (n/a (denominator 0) of threads started)
  - unique leads contacted **5**; profile views 0, follows 5, post likes 0
  - provider's own tags: `autoTaggedInterested` **0**, `totalAutoTagged` **0**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 0 conversations joined, 0 operator-positive replies = **0.000 per 100 requests sent**
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-09-22 .. 2026-09-22 (1 days)
- sequence node types present in the whole graph: CHECK_IS_CONNECTION, CONNECTION_REQUEST, END, FOLLOW, MESSAGE, VIEW_PROFILE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CHECK_IS_CONNECTION   wait 0H      day  0.00
  step 1   MESSAGE               wait 0H      day  0.00
  step 2   MESSAGE               wait 5D      day  5.00
  step 3   MESSAGE               wait 5D      day 10.00
  step 4   END                   wait 3D      day 13.00
```

**Connection note:** 1 `CONNECTION_REQUEST` note slot(s), every one of them EMPTY — this campaign sends connection requests with no note.

**Message steps — our text, in full:**

- message at day 0.00, 3 variant(s):
  - variant 1 (283 chars, 46 words): `Hey {FIRST_NAME},

{Icebreaker}
 
We built Productive so budgets, time tracking and resourcing actually talk to each other, so you can see if a project's making money while it's still running, not just after it gets invoiced.
 
Can show you what that looks like if you're interested.`
  - variant 2 (233 chars, 39 words): `Hi {FIRST_NAME}, {Icebreaker}
 
It's a common one. Productive ties budgets, time and resourcing together so that question has a live answer instead of one you get after the invoice goes out. Can walk you through it if you're curious.`
  - variant 3 (233 chars, 34 words): `Hey {FIRST_NAME},
 
{Icebreaker}
 
That's basically why we built Productive, so budgets, time tracking and resourcing stop living in separate places and you can see project profitability while it's still happening. Happy to show you.`
  - fallback (256 chars): `Hey, we built Productive so budgets, time tracking and resourcing actually talk to each other, so you can see if a project's making money while it's still running, not just after it gets invoiced.
 
Can show you what that looks like if you're interested.

`
- message at day 5.00, 2 variant(s):
  - variant 1 (251 chars, 37 words): `{FIRST_NAME}, random one, but Infinum (software agency, 370+ people) uses Productive to plan resourcing across the whole team without losing sight of which projects are actually profitable.
 
Would something like this make sense for {COMPANY} as well?`
  - variant 2 (253 chars, 41 words): `{FIRST_NAME}, Akcelo (190 people, works with McDonald's and Netflix) uses Productive to stay on top of budgets and reporting across every project. PIABO runs basically the same setup across five offices in Europe. Could it be worth a look for {COMPANY}?`
  - fallback (237 chars): `Random one, but Infinum (software agency, 370+ people) uses Productive to plan resourcing across the whole team without losing sight of which projects are actually profitable.
 
Would something like this make sense for your team as well?`
- message at day 10.00, 4 variant(s):
  - variant 1 (83 chars, 17 words): `{FIRST_NAME}, worth a yes or no on this one so I know whether to stop reaching out?`
  - variant 2 (84 chars, 17 words): `{FIRST_NAME}, should I drop this or send you an overview if you want to take a look?`
  - variant 3 (51 chars, 9 words): `Worth a look, {FIRST_NAME}? I can send an overview.`
  - variant 4 (59 chars, 10 words): `Is this worth pursuing or should I stop here, {FIRST_NAME}?`
  - fallback (69 chars): `Worth a yes or no on this one so I know whether to stop reaching out?`

### 613731 — RESONATE PRODUCTIVE LI B1 SEAT 129082

- ownership: **resonate_os** — `heyreach_campaign_id` present in `work/campaigns.jsonl`
- provider status `PAUSED`; created `2026-09-21T21:25:32.876162Z`; started `2026-09-22T09:10:31.489883Z`
- seats (`campaignAccountIds`): 129082
- lead list `956317` (RESONATE PRODUCTIVE LI B1 SEAT 129082), list size `totalItemsCount` = 5; campaign holds `progressStats.totalUsers` = 5, finished 0
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **5**, accepted **1** (20.00%)
  - messages sent **0**, message threads started **1**, replies **0** (0.00% of threads started)
  - unique leads contacted **5**; profile views 0, follows 5, post likes 0
  - provider's own tags: `autoTaggedInterested` **0**, `totalAutoTagged` **0**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 1 conversations joined, 0 operator-positive replies = **0.000 per 100 requests sent**
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-09-22 .. 2026-09-22 (1 days)
- sequence node types present in the whole graph: CHECK_IS_CONNECTION, CONNECTION_REQUEST, END, FOLLOW, MESSAGE, VIEW_PROFILE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CHECK_IS_CONNECTION   wait 0H      day  0.00
  step 1   MESSAGE               wait 0H      day  0.00
  step 2   MESSAGE               wait 5D      day  5.00
  step 3   MESSAGE               wait 5D      day 10.00
  step 4   END                   wait 3D      day 13.00
```

**Connection note:** 1 `CONNECTION_REQUEST` note slot(s), every one of them EMPTY — this campaign sends connection requests with no note.

**Message steps — our text, in full:**

- message at day 0.00, 3 variant(s):
  - variant 1 (283 chars, 46 words): `Hey {FIRST_NAME},

{Icebreaker}
 
We built Productive so budgets, time tracking and resourcing actually talk to each other, so you can see if a project's making money while it's still running, not just after it gets invoiced.
 
Can show you what that looks like if you're interested.`
  - variant 2 (233 chars, 39 words): `Hi {FIRST_NAME}, {Icebreaker}
 
It's a common one. Productive ties budgets, time and resourcing together so that question has a live answer instead of one you get after the invoice goes out. Can walk you through it if you're curious.`
  - variant 3 (233 chars, 34 words): `Hey {FIRST_NAME},
 
{Icebreaker}
 
That's basically why we built Productive, so budgets, time tracking and resourcing stop living in separate places and you can see project profitability while it's still happening. Happy to show you.`
  - fallback (256 chars): `Hey, we built Productive so budgets, time tracking and resourcing actually talk to each other, so you can see if a project's making money while it's still running, not just after it gets invoiced.
 
Can show you what that looks like if you're interested.

`
- message at day 5.00, 2 variant(s):
  - variant 1 (251 chars, 37 words): `{FIRST_NAME}, random one, but Infinum (software agency, 370+ people) uses Productive to plan resourcing across the whole team without losing sight of which projects are actually profitable.
 
Would something like this make sense for {COMPANY} as well?`
  - variant 2 (253 chars, 41 words): `{FIRST_NAME}, Akcelo (190 people, works with McDonald's and Netflix) uses Productive to stay on top of budgets and reporting across every project. PIABO runs basically the same setup across five offices in Europe. Could it be worth a look for {COMPANY}?`
  - fallback (237 chars): `Random one, but Infinum (software agency, 370+ people) uses Productive to plan resourcing across the whole team without losing sight of which projects are actually profitable.
 
Would something like this make sense for your team as well?`
- message at day 10.00, 4 variant(s):
  - variant 1 (83 chars, 17 words): `{FIRST_NAME}, worth a yes or no on this one so I know whether to stop reaching out?`
  - variant 2 (84 chars, 17 words): `{FIRST_NAME}, should I drop this or send you an overview if you want to take a look?`
  - variant 3 (51 chars, 9 words): `Worth a look, {FIRST_NAME}? I can send an overview.`
  - variant 4 (59 chars, 10 words): `Is this worth pursuing or should I stop here, {FIRST_NAME}?`
  - fallback (69 chars): `Worth a yes or no on this one so I know whether to stop reaching out?`

### 613732 — RESONATE PRODUCTIVE LI B1 SEAT 139699

- ownership: **resonate_os** — `heyreach_campaign_id` present in `work/campaigns.jsonl`
- provider status `PAUSED`; created `2026-09-21T21:25:35.489221Z`; started `2026-09-22T09:10:32.754189Z`
- seats (`campaignAccountIds`): 139699
- lead list `956318` (RESONATE PRODUCTIVE LI B1 SEAT 139699), list size `totalItemsCount` = 5; campaign holds `progressStats.totalUsers` = 5, finished 0
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **5**, accepted **0** (0.00%)
  - messages sent **0**, message threads started **0**, replies **0** (n/a (denominator 0) of threads started)
  - unique leads contacted **5**; profile views 5, follows 5, post likes 0
  - provider's own tags: `autoTaggedInterested` **0**, `totalAutoTagged` **0**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 0 conversations joined, 0 operator-positive replies = **0.000 per 100 requests sent**
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-09-23 .. 2026-09-23 (1 days)
- sequence node types present in the whole graph: CHECK_IS_CONNECTION, CONNECTION_REQUEST, END, FOLLOW, MESSAGE, VIEW_PROFILE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CHECK_IS_CONNECTION   wait 0H      day  0.00
  step 1   MESSAGE               wait 0H      day  0.00
  step 2   MESSAGE               wait 5D      day  5.00
  step 3   MESSAGE               wait 5D      day 10.00
  step 4   END                   wait 3D      day 13.00
```

**Connection note:** 1 `CONNECTION_REQUEST` note slot(s), every one of them EMPTY — this campaign sends connection requests with no note.

**Message steps — our text, in full:**

- message at day 0.00, 3 variant(s):
  - variant 1 (283 chars, 46 words): `Hey {FIRST_NAME},

{Icebreaker}
 
We built Productive so budgets, time tracking and resourcing actually talk to each other, so you can see if a project's making money while it's still running, not just after it gets invoiced.
 
Can show you what that looks like if you're interested.`
  - variant 2 (233 chars, 39 words): `Hi {FIRST_NAME}, {Icebreaker}
 
It's a common one. Productive ties budgets, time and resourcing together so that question has a live answer instead of one you get after the invoice goes out. Can walk you through it if you're curious.`
  - variant 3 (233 chars, 34 words): `Hey {FIRST_NAME},
 
{Icebreaker}
 
That's basically why we built Productive, so budgets, time tracking and resourcing stop living in separate places and you can see project profitability while it's still happening. Happy to show you.`
  - fallback (256 chars): `Hey, we built Productive so budgets, time tracking and resourcing actually talk to each other, so you can see if a project's making money while it's still running, not just after it gets invoiced.
 
Can show you what that looks like if you're interested.

`
- message at day 5.00, 2 variant(s):
  - variant 1 (251 chars, 37 words): `{FIRST_NAME}, random one, but Infinum (software agency, 370+ people) uses Productive to plan resourcing across the whole team without losing sight of which projects are actually profitable.
 
Would something like this make sense for {COMPANY} as well?`
  - variant 2 (253 chars, 41 words): `{FIRST_NAME}, Akcelo (190 people, works with McDonald's and Netflix) uses Productive to stay on top of budgets and reporting across every project. PIABO runs basically the same setup across five offices in Europe. Could it be worth a look for {COMPANY}?`
  - fallback (237 chars): `Random one, but Infinum (software agency, 370+ people) uses Productive to plan resourcing across the whole team without losing sight of which projects are actually profitable.
 
Would something like this make sense for your team as well?`
- message at day 10.00, 4 variant(s):
  - variant 1 (83 chars, 17 words): `{FIRST_NAME}, worth a yes or no on this one so I know whether to stop reaching out?`
  - variant 2 (84 chars, 17 words): `{FIRST_NAME}, should I drop this or send you an overview if you want to take a look?`
  - variant 3 (51 chars, 9 words): `Worth a look, {FIRST_NAME}? I can send an overview.`
  - variant 4 (59 chars, 10 words): `Is this worth pursuing or should I stop here, {FIRST_NAME}?`
  - fallback (69 chars): `Worth a yes or no on this one so I know whether to stop reaching out?`

### 613733 — RESONATE PRODUCTIVE LI B1 SEAT 143105

- ownership: **resonate_os** — `heyreach_campaign_id` present in `work/campaigns.jsonl`
- provider status `PAUSED`; created `2026-09-21T21:25:38.557724Z`; started `2026-09-22T09:10:35.130403Z`
- seats (`campaignAccountIds`): 143105
- lead list `956319` (RESONATE PRODUCTIVE LI B1 SEAT 143105), list size `totalItemsCount` = 5; campaign holds `progressStats.totalUsers` = 5, finished 0
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **0**, accepted **0** (n/a (denominator 0))
  - messages sent **0**, message threads started **0**, replies **0** (n/a (denominator 0) of threads started)
  - unique leads contacted **0**; profile views 0, follows 5, post likes 0
  - provider's own tags: `autoTaggedInterested` **0**, `totalAutoTagged` **0**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 0 conversations joined, 0 operator-positive replies = **n/a (0 requests sent) per 100 requests sent**
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- sequence node types present in the whole graph: CHECK_IS_CONNECTION, CONNECTION_REQUEST, END, FOLLOW, MESSAGE, VIEW_PROFILE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CHECK_IS_CONNECTION   wait 0H      day  0.00
  step 1   MESSAGE               wait 0H      day  0.00
  step 2   MESSAGE               wait 5D      day  5.00
  step 3   MESSAGE               wait 5D      day 10.00
  step 4   END                   wait 3D      day 13.00
```

**Connection note:** 1 `CONNECTION_REQUEST` note slot(s), every one of them EMPTY — this campaign sends connection requests with no note.

**Message steps — our text, in full:**

- message at day 0.00, 3 variant(s):
  - variant 1 (283 chars, 46 words): `Hey {FIRST_NAME},

{Icebreaker}
 
We built Productive so budgets, time tracking and resourcing actually talk to each other, so you can see if a project's making money while it's still running, not just after it gets invoiced.
 
Can show you what that looks like if you're interested.`
  - variant 2 (233 chars, 39 words): `Hi {FIRST_NAME}, {Icebreaker}
 
It's a common one. Productive ties budgets, time and resourcing together so that question has a live answer instead of one you get after the invoice goes out. Can walk you through it if you're curious.`
  - variant 3 (233 chars, 34 words): `Hey {FIRST_NAME},
 
{Icebreaker}
 
That's basically why we built Productive, so budgets, time tracking and resourcing stop living in separate places and you can see project profitability while it's still happening. Happy to show you.`
  - fallback (256 chars): `Hey, we built Productive so budgets, time tracking and resourcing actually talk to each other, so you can see if a project's making money while it's still running, not just after it gets invoiced.
 
Can show you what that looks like if you're interested.

`
- message at day 5.00, 2 variant(s):
  - variant 1 (251 chars, 37 words): `{FIRST_NAME}, random one, but Infinum (software agency, 370+ people) uses Productive to plan resourcing across the whole team without losing sight of which projects are actually profitable.
 
Would something like this make sense for {COMPANY} as well?`
  - variant 2 (253 chars, 41 words): `{FIRST_NAME}, Akcelo (190 people, works with McDonald's and Netflix) uses Productive to stay on top of budgets and reporting across every project. PIABO runs basically the same setup across five offices in Europe. Could it be worth a look for {COMPANY}?`
  - fallback (237 chars): `Random one, but Infinum (software agency, 370+ people) uses Productive to plan resourcing across the whole team without losing sight of which projects are actually profitable.
 
Would something like this make sense for your team as well?`
- message at day 10.00, 4 variant(s):
  - variant 1 (83 chars, 17 words): `{FIRST_NAME}, worth a yes or no on this one so I know whether to stop reaching out?`
  - variant 2 (84 chars, 17 words): `{FIRST_NAME}, should I drop this or send you an overview if you want to take a look?`
  - variant 3 (51 chars, 9 words): `Worth a look, {FIRST_NAME}? I can send an overview.`
  - variant 4 (59 chars, 10 words): `Is this worth pursuing or should I stop here, {FIRST_NAME}?`
  - fallback (69 chars): `Worth a yes or no on this one so I know whether to stop reaching out?`

### 613734 — RESONATE PRODUCTIVE LI B1 SEAT 159259

- ownership: **resonate_os** — `heyreach_campaign_id` present in `work/campaigns.jsonl`
- provider status `PAUSED`; created `2026-09-21T21:25:41.184572Z`; started `2026-09-22T09:10:35.772093Z`
- seats (`campaignAccountIds`): 159259
- lead list `956320` (RESONATE PRODUCTIVE LI B1 SEAT 159259), list size `totalItemsCount` = 5; campaign holds `progressStats.totalUsers` = 5, finished 0
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **3**, accepted **1** (33.33%)
  - messages sent **1**, message threads started **1**, replies **0** (0.00% of threads started)
  - unique leads contacted **3**; profile views 0, follows 3, post likes 0
  - provider's own tags: `autoTaggedInterested` **0**, `totalAutoTagged` **0**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 1 conversations joined, 0 operator-positive replies = **0.000 per 100 requests sent**
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-09-22 .. 2026-09-28 (2 days)
- sequence node types present in the whole graph: CHECK_IS_CONNECTION, CONNECTION_REQUEST, END, FOLLOW, MESSAGE, VIEW_PROFILE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CHECK_IS_CONNECTION   wait 0H      day  0.00
  step 1   MESSAGE               wait 0H      day  0.00
  step 2   MESSAGE               wait 5D      day  5.00
  step 3   MESSAGE               wait 5D      day 10.00
  step 4   END                   wait 3D      day 13.00
```

**Connection note:** 1 `CONNECTION_REQUEST` note slot(s), every one of them EMPTY — this campaign sends connection requests with no note.

**Message steps — our text, in full:**

- message at day 0.00, 3 variant(s):
  - variant 1 (283 chars, 46 words): `Hey {FIRST_NAME},

{Icebreaker}
 
We built Productive so budgets, time tracking and resourcing actually talk to each other, so you can see if a project's making money while it's still running, not just after it gets invoiced.
 
Can show you what that looks like if you're interested.`
  - variant 2 (233 chars, 39 words): `Hi {FIRST_NAME}, {Icebreaker}
 
It's a common one. Productive ties budgets, time and resourcing together so that question has a live answer instead of one you get after the invoice goes out. Can walk you through it if you're curious.`
  - variant 3 (233 chars, 34 words): `Hey {FIRST_NAME},
 
{Icebreaker}
 
That's basically why we built Productive, so budgets, time tracking and resourcing stop living in separate places and you can see project profitability while it's still happening. Happy to show you.`
  - fallback (256 chars): `Hey, we built Productive so budgets, time tracking and resourcing actually talk to each other, so you can see if a project's making money while it's still running, not just after it gets invoiced.
 
Can show you what that looks like if you're interested.

`
- message at day 5.00, 2 variant(s):
  - variant 1 (251 chars, 37 words): `{FIRST_NAME}, random one, but Infinum (software agency, 370+ people) uses Productive to plan resourcing across the whole team without losing sight of which projects are actually profitable.
 
Would something like this make sense for {COMPANY} as well?`
  - variant 2 (253 chars, 41 words): `{FIRST_NAME}, Akcelo (190 people, works with McDonald's and Netflix) uses Productive to stay on top of budgets and reporting across every project. PIABO runs basically the same setup across five offices in Europe. Could it be worth a look for {COMPANY}?`
  - fallback (237 chars): `Random one, but Infinum (software agency, 370+ people) uses Productive to plan resourcing across the whole team without losing sight of which projects are actually profitable.
 
Would something like this make sense for your team as well?`
- message at day 10.00, 4 variant(s):
  - variant 1 (83 chars, 17 words): `{FIRST_NAME}, worth a yes or no on this one so I know whether to stop reaching out?`
  - variant 2 (84 chars, 17 words): `{FIRST_NAME}, should I drop this or send you an overview if you want to take a look?`
  - variant 3 (51 chars, 9 words): `Worth a look, {FIRST_NAME}? I can send an overview.`
  - variant 4 (59 chars, 10 words): `Is this worth pursuing or should I stop here, {FIRST_NAME}?`
  - fallback (69 chars): `Worth a yes or no on this one so I know whether to stop reaching out?`

### 613735 — RESONATE PRODUCTIVE LI B1 SEAT 169600

- ownership: **resonate_os** — `heyreach_campaign_id` present in `work/campaigns.jsonl`
- provider status `PAUSED`; created `2026-09-21T21:25:43.815174Z`; started `2026-09-22T09:10:36.3955Z`
- seats (`campaignAccountIds`): 169600
- lead list `956321` (RESONATE PRODUCTIVE LI B1 SEAT 169600), list size `totalItemsCount` = 5; campaign holds `progressStats.totalUsers` = 5, finished 0
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **5**, accepted **0** (0.00%)
  - messages sent **0**, message threads started **0**, replies **0** (n/a (denominator 0) of threads started)
  - unique leads contacted **5**; profile views 0, follows 5, post likes 0
  - provider's own tags: `autoTaggedInterested` **0**, `totalAutoTagged` **0**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 0 conversations joined, 0 operator-positive replies = **0.000 per 100 requests sent**
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-09-23 .. 2026-09-23 (1 days)
- sequence node types present in the whole graph: CHECK_IS_CONNECTION, CONNECTION_REQUEST, END, FOLLOW, MESSAGE, VIEW_PROFILE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CHECK_IS_CONNECTION   wait 0H      day  0.00
  step 1   MESSAGE               wait 0H      day  0.00
  step 2   MESSAGE               wait 5D      day  5.00
  step 3   MESSAGE               wait 5D      day 10.00
  step 4   END                   wait 3D      day 13.00
```

**Connection note:** 1 `CONNECTION_REQUEST` note slot(s), every one of them EMPTY — this campaign sends connection requests with no note.

**Message steps — our text, in full:**

- message at day 0.00, 3 variant(s):
  - variant 1 (283 chars, 46 words): `Hey {FIRST_NAME},

{Icebreaker}
 
We built Productive so budgets, time tracking and resourcing actually talk to each other, so you can see if a project's making money while it's still running, not just after it gets invoiced.
 
Can show you what that looks like if you're interested.`
  - variant 2 (233 chars, 39 words): `Hi {FIRST_NAME}, {Icebreaker}
 
It's a common one. Productive ties budgets, time and resourcing together so that question has a live answer instead of one you get after the invoice goes out. Can walk you through it if you're curious.`
  - variant 3 (233 chars, 34 words): `Hey {FIRST_NAME},
 
{Icebreaker}
 
That's basically why we built Productive, so budgets, time tracking and resourcing stop living in separate places and you can see project profitability while it's still happening. Happy to show you.`
  - fallback (256 chars): `Hey, we built Productive so budgets, time tracking and resourcing actually talk to each other, so you can see if a project's making money while it's still running, not just after it gets invoiced.
 
Can show you what that looks like if you're interested.

`
- message at day 5.00, 2 variant(s):
  - variant 1 (251 chars, 37 words): `{FIRST_NAME}, random one, but Infinum (software agency, 370+ people) uses Productive to plan resourcing across the whole team without losing sight of which projects are actually profitable.
 
Would something like this make sense for {COMPANY} as well?`
  - variant 2 (253 chars, 41 words): `{FIRST_NAME}, Akcelo (190 people, works with McDonald's and Netflix) uses Productive to stay on top of budgets and reporting across every project. PIABO runs basically the same setup across five offices in Europe. Could it be worth a look for {COMPANY}?`
  - fallback (237 chars): `Random one, but Infinum (software agency, 370+ people) uses Productive to plan resourcing across the whole team without losing sight of which projects are actually profitable.
 
Would something like this make sense for your team as well?`
- message at day 10.00, 4 variant(s):
  - variant 1 (83 chars, 17 words): `{FIRST_NAME}, worth a yes or no on this one so I know whether to stop reaching out?`
  - variant 2 (84 chars, 17 words): `{FIRST_NAME}, should I drop this or send you an overview if you want to take a look?`
  - variant 3 (51 chars, 9 words): `Worth a look, {FIRST_NAME}? I can send an overview.`
  - variant 4 (59 chars, 10 words): `Is this worth pursuing or should I stop here, {FIRST_NAME}?`
  - fallback (69 chars): `Worth a yes or no on this one so I know whether to stop reaching out?`

### 613736 — RESONATE PRODUCTIVE LI B1 SEAT 174332

- ownership: **resonate_os** — `heyreach_campaign_id` present in `work/campaigns.jsonl`
- provider status `PAUSED`; created `2026-09-21T21:25:46.644307Z`; started `2026-09-22T09:10:37.824732Z`
- seats (`campaignAccountIds`): 174332
- lead list `956322` (RESONATE PRODUCTIVE LI B1 SEAT 174332), list size `totalItemsCount` = 5; campaign holds `progressStats.totalUsers` = 5, finished 0
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **5**, accepted **1** (20.00%)
  - messages sent **0**, message threads started **0**, replies **0** (n/a (denominator 0) of threads started)
  - unique leads contacted **5**; profile views 0, follows 5, post likes 0
  - provider's own tags: `autoTaggedInterested` **0**, `totalAutoTagged` **0**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 0 conversations joined, 0 operator-positive replies = **0.000 per 100 requests sent**
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-09-22 .. 2026-09-23 (2 days)
- sequence node types present in the whole graph: CHECK_IS_CONNECTION, CONNECTION_REQUEST, END, FOLLOW, MESSAGE, VIEW_PROFILE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CHECK_IS_CONNECTION   wait 0H      day  0.00
  step 1   MESSAGE               wait 0H      day  0.00
  step 2   MESSAGE               wait 5D      day  5.00
  step 3   MESSAGE               wait 5D      day 10.00
  step 4   END                   wait 3D      day 13.00
```

**Connection note:** 1 `CONNECTION_REQUEST` note slot(s), every one of them EMPTY — this campaign sends connection requests with no note.

**Message steps — our text, in full:**

- message at day 0.00, 3 variant(s):
  - variant 1 (283 chars, 46 words): `Hey {FIRST_NAME},

{Icebreaker}
 
We built Productive so budgets, time tracking and resourcing actually talk to each other, so you can see if a project's making money while it's still running, not just after it gets invoiced.
 
Can show you what that looks like if you're interested.`
  - variant 2 (233 chars, 39 words): `Hi {FIRST_NAME}, {Icebreaker}
 
It's a common one. Productive ties budgets, time and resourcing together so that question has a live answer instead of one you get after the invoice goes out. Can walk you through it if you're curious.`
  - variant 3 (233 chars, 34 words): `Hey {FIRST_NAME},
 
{Icebreaker}
 
That's basically why we built Productive, so budgets, time tracking and resourcing stop living in separate places and you can see project profitability while it's still happening. Happy to show you.`
  - fallback (256 chars): `Hey, we built Productive so budgets, time tracking and resourcing actually talk to each other, so you can see if a project's making money while it's still running, not just after it gets invoiced.
 
Can show you what that looks like if you're interested.

`
- message at day 5.00, 2 variant(s):
  - variant 1 (251 chars, 37 words): `{FIRST_NAME}, random one, but Infinum (software agency, 370+ people) uses Productive to plan resourcing across the whole team without losing sight of which projects are actually profitable.
 
Would something like this make sense for {COMPANY} as well?`
  - variant 2 (253 chars, 41 words): `{FIRST_NAME}, Akcelo (190 people, works with McDonald's and Netflix) uses Productive to stay on top of budgets and reporting across every project. PIABO runs basically the same setup across five offices in Europe. Could it be worth a look for {COMPANY}?`
  - fallback (237 chars): `Random one, but Infinum (software agency, 370+ people) uses Productive to plan resourcing across the whole team without losing sight of which projects are actually profitable.
 
Would something like this make sense for your team as well?`
- message at day 10.00, 4 variant(s):
  - variant 1 (83 chars, 17 words): `{FIRST_NAME}, worth a yes or no on this one so I know whether to stop reaching out?`
  - variant 2 (84 chars, 17 words): `{FIRST_NAME}, should I drop this or send you an overview if you want to take a look?`
  - variant 3 (51 chars, 9 words): `Worth a look, {FIRST_NAME}? I can send an overview.`
  - variant 4 (59 chars, 10 words): `Is this worth pursuing or should I stop here, {FIRST_NAME}?`
  - fallback (69 chars): `Worth a yes or no on this one so I know whether to stop reaching out?`

### 613737 — RESONATE PRODUCTIVE LI B1 SEAT 174742

- ownership: **resonate_os** — `heyreach_campaign_id` present in `work/campaigns.jsonl`
- provider status `PAUSED`; created `2026-09-21T21:25:49.296475Z`; started `2026-09-22T09:10:39.664199Z`
- seats (`campaignAccountIds`): 174742
- lead list `956323` (RESONATE PRODUCTIVE LI B1 SEAT 174742), list size `totalItemsCount` = 5; campaign holds `progressStats.totalUsers` = 5, finished 0
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **3**, accepted **0** (0.00%)
  - messages sent **0**, message threads started **0**, replies **0** (n/a (denominator 0) of threads started)
  - unique leads contacted **3**; profile views 0, follows 3, post likes 0
  - provider's own tags: `autoTaggedInterested` **0**, `totalAutoTagged` **0**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 0 conversations joined, 0 operator-positive replies = **0.000 per 100 requests sent**
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-09-23 .. 2026-09-24 (2 days)
- sequence node types present in the whole graph: CHECK_IS_CONNECTION, CONNECTION_REQUEST, END, FOLLOW, MESSAGE, VIEW_PROFILE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CHECK_IS_CONNECTION   wait 0H      day  0.00
  step 1   MESSAGE               wait 0H      day  0.00
  step 2   MESSAGE               wait 5D      day  5.00
  step 3   MESSAGE               wait 5D      day 10.00
  step 4   END                   wait 3D      day 13.00
```

**Connection note:** 1 `CONNECTION_REQUEST` note slot(s), every one of them EMPTY — this campaign sends connection requests with no note.

**Message steps — our text, in full:**

- message at day 0.00, 3 variant(s):
  - variant 1 (283 chars, 46 words): `Hey {FIRST_NAME},

{Icebreaker}
 
We built Productive so budgets, time tracking and resourcing actually talk to each other, so you can see if a project's making money while it's still running, not just after it gets invoiced.
 
Can show you what that looks like if you're interested.`
  - variant 2 (233 chars, 39 words): `Hi {FIRST_NAME}, {Icebreaker}
 
It's a common one. Productive ties budgets, time and resourcing together so that question has a live answer instead of one you get after the invoice goes out. Can walk you through it if you're curious.`
  - variant 3 (233 chars, 34 words): `Hey {FIRST_NAME},
 
{Icebreaker}
 
That's basically why we built Productive, so budgets, time tracking and resourcing stop living in separate places and you can see project profitability while it's still happening. Happy to show you.`
  - fallback (256 chars): `Hey, we built Productive so budgets, time tracking and resourcing actually talk to each other, so you can see if a project's making money while it's still running, not just after it gets invoiced.
 
Can show you what that looks like if you're interested.

`
- message at day 5.00, 2 variant(s):
  - variant 1 (251 chars, 37 words): `{FIRST_NAME}, random one, but Infinum (software agency, 370+ people) uses Productive to plan resourcing across the whole team without losing sight of which projects are actually profitable.
 
Would something like this make sense for {COMPANY} as well?`
  - variant 2 (253 chars, 41 words): `{FIRST_NAME}, Akcelo (190 people, works with McDonald's and Netflix) uses Productive to stay on top of budgets and reporting across every project. PIABO runs basically the same setup across five offices in Europe. Could it be worth a look for {COMPANY}?`
  - fallback (237 chars): `Random one, but Infinum (software agency, 370+ people) uses Productive to plan resourcing across the whole team without losing sight of which projects are actually profitable.
 
Would something like this make sense for your team as well?`
- message at day 10.00, 4 variant(s):
  - variant 1 (83 chars, 17 words): `{FIRST_NAME}, worth a yes or no on this one so I know whether to stop reaching out?`
  - variant 2 (84 chars, 17 words): `{FIRST_NAME}, should I drop this or send you an overview if you want to take a look?`
  - variant 3 (51 chars, 9 words): `Worth a look, {FIRST_NAME}? I can send an overview.`
  - variant 4 (59 chars, 10 words): `Is this worth pursuing or should I stop here, {FIRST_NAME}?`
  - fallback (69 chars): `Worth a yes or no on this one so I know whether to stop reaching out?`

### 613738 — RESONATE PRODUCTIVE LI B1 SEAT 174748

- ownership: **resonate_os** — `heyreach_campaign_id` present in `work/campaigns.jsonl`
- provider status `PAUSED`; created `2026-09-21T21:25:51.819745Z`; started `2026-09-22T09:10:41.686101Z`
- seats (`campaignAccountIds`): 174748
- lead list `956324` (RESONATE PRODUCTIVE LI B1 SEAT 174748), list size `totalItemsCount` = 5; campaign holds `progressStats.totalUsers` = 5, finished 0
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **3**, accepted **0** (0.00%)
  - messages sent **1**, message threads started **1**, replies **0** (0.00% of threads started)
  - unique leads contacted **4**; profile views 0, follows 4, post likes 0
  - provider's own tags: `autoTaggedInterested` **0**, `totalAutoTagged` **0**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 1 conversations joined, 0 operator-positive replies = **0.000 per 100 requests sent**
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-09-24 .. 2026-09-28 (2 days)
- sequence node types present in the whole graph: CHECK_IS_CONNECTION, CONNECTION_REQUEST, END, FOLLOW, MESSAGE, VIEW_PROFILE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CHECK_IS_CONNECTION   wait 0H      day  0.00
  step 1   MESSAGE               wait 0H      day  0.00
  step 2   MESSAGE               wait 5D      day  5.00
  step 3   MESSAGE               wait 5D      day 10.00
  step 4   END                   wait 3D      day 13.00
```

**Connection note:** 1 `CONNECTION_REQUEST` note slot(s), every one of them EMPTY — this campaign sends connection requests with no note.

**Message steps — our text, in full:**

- message at day 0.00, 3 variant(s):
  - variant 1 (283 chars, 46 words): `Hey {FIRST_NAME},

{Icebreaker}
 
We built Productive so budgets, time tracking and resourcing actually talk to each other, so you can see if a project's making money while it's still running, not just after it gets invoiced.
 
Can show you what that looks like if you're interested.`
  - variant 2 (233 chars, 39 words): `Hi {FIRST_NAME}, {Icebreaker}
 
It's a common one. Productive ties budgets, time and resourcing together so that question has a live answer instead of one you get after the invoice goes out. Can walk you through it if you're curious.`
  - variant 3 (233 chars, 34 words): `Hey {FIRST_NAME},
 
{Icebreaker}
 
That's basically why we built Productive, so budgets, time tracking and resourcing stop living in separate places and you can see project profitability while it's still happening. Happy to show you.`
  - fallback (256 chars): `Hey, we built Productive so budgets, time tracking and resourcing actually talk to each other, so you can see if a project's making money while it's still running, not just after it gets invoiced.
 
Can show you what that looks like if you're interested.

`
- message at day 5.00, 2 variant(s):
  - variant 1 (251 chars, 37 words): `{FIRST_NAME}, random one, but Infinum (software agency, 370+ people) uses Productive to plan resourcing across the whole team without losing sight of which projects are actually profitable.
 
Would something like this make sense for {COMPANY} as well?`
  - variant 2 (253 chars, 41 words): `{FIRST_NAME}, Akcelo (190 people, works with McDonald's and Netflix) uses Productive to stay on top of budgets and reporting across every project. PIABO runs basically the same setup across five offices in Europe. Could it be worth a look for {COMPANY}?`
  - fallback (237 chars): `Random one, but Infinum (software agency, 370+ people) uses Productive to plan resourcing across the whole team without losing sight of which projects are actually profitable.
 
Would something like this make sense for your team as well?`
- message at day 10.00, 4 variant(s):
  - variant 1 (83 chars, 17 words): `{FIRST_NAME}, worth a yes or no on this one so I know whether to stop reaching out?`
  - variant 2 (84 chars, 17 words): `{FIRST_NAME}, should I drop this or send you an overview if you want to take a look?`
  - variant 3 (51 chars, 9 words): `Worth a look, {FIRST_NAME}? I can send an overview.`
  - variant 4 (59 chars, 10 words): `Is this worth pursuing or should I stop here, {FIRST_NAME}?`
  - fallback (69 chars): `Worth a yes or no on this one so I know whether to stop reaching out?`

### 613739 — RESONATE PRODUCTIVE LI B1 SEAT 174797

- ownership: **resonate_os** — `heyreach_campaign_id` present in `work/campaigns.jsonl`
- provider status `PAUSED`; created `2026-09-21T21:25:55.133001Z`; started `2026-09-22T09:10:43.505214Z`
- seats (`campaignAccountIds`): 174797
- lead list `956325` (RESONATE PRODUCTIVE LI B1 SEAT 174797), list size `totalItemsCount` = 5; campaign holds `progressStats.totalUsers` = 5, finished 0
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **4**, accepted **0** (0.00%)
  - messages sent **0**, message threads started **0**, replies **0** (n/a (denominator 0) of threads started)
  - unique leads contacted **4**; profile views 0, follows 4, post likes 0
  - provider's own tags: `autoTaggedInterested` **0**, `totalAutoTagged` **0**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 0 conversations joined, 0 operator-positive replies = **0.000 per 100 requests sent**
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-09-22 .. 2026-09-24 (3 days)
- sequence node types present in the whole graph: CHECK_IS_CONNECTION, CONNECTION_REQUEST, END, FOLLOW, MESSAGE, VIEW_PROFILE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CHECK_IS_CONNECTION   wait 0H      day  0.00
  step 1   MESSAGE               wait 0H      day  0.00
  step 2   MESSAGE               wait 5D      day  5.00
  step 3   MESSAGE               wait 5D      day 10.00
  step 4   END                   wait 3D      day 13.00
```

**Connection note:** 1 `CONNECTION_REQUEST` note slot(s), every one of them EMPTY — this campaign sends connection requests with no note.

**Message steps — our text, in full:**

- message at day 0.00, 3 variant(s):
  - variant 1 (283 chars, 46 words): `Hey {FIRST_NAME},

{Icebreaker}
 
We built Productive so budgets, time tracking and resourcing actually talk to each other, so you can see if a project's making money while it's still running, not just after it gets invoiced.
 
Can show you what that looks like if you're interested.`
  - variant 2 (233 chars, 39 words): `Hi {FIRST_NAME}, {Icebreaker}
 
It's a common one. Productive ties budgets, time and resourcing together so that question has a live answer instead of one you get after the invoice goes out. Can walk you through it if you're curious.`
  - variant 3 (233 chars, 34 words): `Hey {FIRST_NAME},
 
{Icebreaker}
 
That's basically why we built Productive, so budgets, time tracking and resourcing stop living in separate places and you can see project profitability while it's still happening. Happy to show you.`
  - fallback (256 chars): `Hey, we built Productive so budgets, time tracking and resourcing actually talk to each other, so you can see if a project's making money while it's still running, not just after it gets invoiced.
 
Can show you what that looks like if you're interested.

`
- message at day 5.00, 2 variant(s):
  - variant 1 (251 chars, 37 words): `{FIRST_NAME}, random one, but Infinum (software agency, 370+ people) uses Productive to plan resourcing across the whole team without losing sight of which projects are actually profitable.
 
Would something like this make sense for {COMPANY} as well?`
  - variant 2 (253 chars, 41 words): `{FIRST_NAME}, Akcelo (190 people, works with McDonald's and Netflix) uses Productive to stay on top of budgets and reporting across every project. PIABO runs basically the same setup across five offices in Europe. Could it be worth a look for {COMPANY}?`
  - fallback (237 chars): `Random one, but Infinum (software agency, 370+ people) uses Productive to plan resourcing across the whole team without losing sight of which projects are actually profitable.
 
Would something like this make sense for your team as well?`
- message at day 10.00, 4 variant(s):
  - variant 1 (83 chars, 17 words): `{FIRST_NAME}, worth a yes or no on this one so I know whether to stop reaching out?`
  - variant 2 (84 chars, 17 words): `{FIRST_NAME}, should I drop this or send you an overview if you want to take a look?`
  - variant 3 (51 chars, 9 words): `Worth a look, {FIRST_NAME}? I can send an overview.`
  - variant 4 (59 chars, 10 words): `Is this worth pursuing or should I stop here, {FIRST_NAME}?`
  - fallback (69 chars): `Worth a yes or no on this one so I know whether to stop reaching out?`

### 613740 — RESONATE PRODUCTIVE LI B1 SEAT 174803

- ownership: **resonate_os** — `heyreach_campaign_id` present in `work/campaigns.jsonl`
- provider status `PAUSED`; created `2026-09-21T21:25:58.868792Z`; started `2026-09-22T09:10:44.734229Z`
- seats (`campaignAccountIds`): 174803
- lead list `956326` (RESONATE PRODUCTIVE LI B1 SEAT 174803), list size `totalItemsCount` = 5; campaign holds `progressStats.totalUsers` = 5, finished 0
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **4**, accepted **1** (25.00%)
  - messages sent **0**, message threads started **0**, replies **0** (n/a (denominator 0) of threads started)
  - unique leads contacted **4**; profile views 0, follows 5, post likes 0
  - provider's own tags: `autoTaggedInterested` **0**, `totalAutoTagged` **0**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 0 conversations joined, 0 operator-positive replies = **0.000 per 100 requests sent**
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-09-24 .. 2026-09-24 (1 days)
- sequence node types present in the whole graph: CHECK_IS_CONNECTION, CONNECTION_REQUEST, END, FOLLOW, MESSAGE, VIEW_PROFILE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CHECK_IS_CONNECTION   wait 0H      day  0.00
  step 1   MESSAGE               wait 0H      day  0.00
  step 2   MESSAGE               wait 5D      day  5.00
  step 3   MESSAGE               wait 5D      day 10.00
  step 4   END                   wait 3D      day 13.00
```

**Connection note:** 1 `CONNECTION_REQUEST` note slot(s), every one of them EMPTY — this campaign sends connection requests with no note.

**Message steps — our text, in full:**

- message at day 0.00, 3 variant(s):
  - variant 1 (283 chars, 46 words): `Hey {FIRST_NAME},

{Icebreaker}
 
We built Productive so budgets, time tracking and resourcing actually talk to each other, so you can see if a project's making money while it's still running, not just after it gets invoiced.
 
Can show you what that looks like if you're interested.`
  - variant 2 (233 chars, 39 words): `Hi {FIRST_NAME}, {Icebreaker}
 
It's a common one. Productive ties budgets, time and resourcing together so that question has a live answer instead of one you get after the invoice goes out. Can walk you through it if you're curious.`
  - variant 3 (233 chars, 34 words): `Hey {FIRST_NAME},
 
{Icebreaker}
 
That's basically why we built Productive, so budgets, time tracking and resourcing stop living in separate places and you can see project profitability while it's still happening. Happy to show you.`
  - fallback (256 chars): `Hey, we built Productive so budgets, time tracking and resourcing actually talk to each other, so you can see if a project's making money while it's still running, not just after it gets invoiced.
 
Can show you what that looks like if you're interested.

`
- message at day 5.00, 2 variant(s):
  - variant 1 (251 chars, 37 words): `{FIRST_NAME}, random one, but Infinum (software agency, 370+ people) uses Productive to plan resourcing across the whole team without losing sight of which projects are actually profitable.
 
Would something like this make sense for {COMPANY} as well?`
  - variant 2 (253 chars, 41 words): `{FIRST_NAME}, Akcelo (190 people, works with McDonald's and Netflix) uses Productive to stay on top of budgets and reporting across every project. PIABO runs basically the same setup across five offices in Europe. Could it be worth a look for {COMPANY}?`
  - fallback (237 chars): `Random one, but Infinum (software agency, 370+ people) uses Productive to plan resourcing across the whole team without losing sight of which projects are actually profitable.
 
Would something like this make sense for your team as well?`
- message at day 10.00, 4 variant(s):
  - variant 1 (83 chars, 17 words): `{FIRST_NAME}, worth a yes or no on this one so I know whether to stop reaching out?`
  - variant 2 (84 chars, 17 words): `{FIRST_NAME}, should I drop this or send you an overview if you want to take a look?`
  - variant 3 (51 chars, 9 words): `Worth a look, {FIRST_NAME}? I can send an overview.`
  - variant 4 (59 chars, 10 words): `Is this worth pursuing or should I stop here, {FIRST_NAME}?`
  - fallback (69 chars): `Worth a yes or no on this one so I know whether to stop reaching out?`

### 613741 — RESONATE PRODUCTIVE LI B1 SEAT 174810

- ownership: **resonate_os** — `heyreach_campaign_id` present in `work/campaigns.jsonl`
- provider status `PAUSED`; created `2026-09-21T21:26:02.320718Z`; started `2026-09-22T09:10:46.113017Z`
- seats (`campaignAccountIds`): 174810
- lead list `956327` (RESONATE PRODUCTIVE LI B1 SEAT 174810), list size `totalItemsCount` = 5; campaign holds `progressStats.totalUsers` = 5, finished 0
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **5**, accepted **0** (0.00%)
  - messages sent **0**, message threads started **0**, replies **0** (n/a (denominator 0) of threads started)
  - unique leads contacted **5**; profile views 0, follows 5, post likes 0
  - provider's own tags: `autoTaggedInterested` **0**, `totalAutoTagged` **0**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 0 conversations joined, 0 operator-positive replies = **0.000 per 100 requests sent**
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-09-24 .. 2026-09-24 (1 days)
- sequence node types present in the whole graph: CHECK_IS_CONNECTION, CONNECTION_REQUEST, END, FOLLOW, MESSAGE, VIEW_PROFILE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CHECK_IS_CONNECTION   wait 0H      day  0.00
  step 1   MESSAGE               wait 0H      day  0.00
  step 2   MESSAGE               wait 5D      day  5.00
  step 3   MESSAGE               wait 5D      day 10.00
  step 4   END                   wait 3D      day 13.00
```

**Connection note:** 1 `CONNECTION_REQUEST` note slot(s), every one of them EMPTY — this campaign sends connection requests with no note.

**Message steps — our text, in full:**

- message at day 0.00, 3 variant(s):
  - variant 1 (283 chars, 46 words): `Hey {FIRST_NAME},

{Icebreaker}
 
We built Productive so budgets, time tracking and resourcing actually talk to each other, so you can see if a project's making money while it's still running, not just after it gets invoiced.
 
Can show you what that looks like if you're interested.`
  - variant 2 (233 chars, 39 words): `Hi {FIRST_NAME}, {Icebreaker}
 
It's a common one. Productive ties budgets, time and resourcing together so that question has a live answer instead of one you get after the invoice goes out. Can walk you through it if you're curious.`
  - variant 3 (233 chars, 34 words): `Hey {FIRST_NAME},
 
{Icebreaker}
 
That's basically why we built Productive, so budgets, time tracking and resourcing stop living in separate places and you can see project profitability while it's still happening. Happy to show you.`
  - fallback (256 chars): `Hey, we built Productive so budgets, time tracking and resourcing actually talk to each other, so you can see if a project's making money while it's still running, not just after it gets invoiced.
 
Can show you what that looks like if you're interested.

`
- message at day 5.00, 2 variant(s):
  - variant 1 (251 chars, 37 words): `{FIRST_NAME}, random one, but Infinum (software agency, 370+ people) uses Productive to plan resourcing across the whole team without losing sight of which projects are actually profitable.
 
Would something like this make sense for {COMPANY} as well?`
  - variant 2 (253 chars, 41 words): `{FIRST_NAME}, Akcelo (190 people, works with McDonald's and Netflix) uses Productive to stay on top of budgets and reporting across every project. PIABO runs basically the same setup across five offices in Europe. Could it be worth a look for {COMPANY}?`
  - fallback (237 chars): `Random one, but Infinum (software agency, 370+ people) uses Productive to plan resourcing across the whole team without losing sight of which projects are actually profitable.
 
Would something like this make sense for your team as well?`
- message at day 10.00, 4 variant(s):
  - variant 1 (83 chars, 17 words): `{FIRST_NAME}, worth a yes or no on this one so I know whether to stop reaching out?`
  - variant 2 (84 chars, 17 words): `{FIRST_NAME}, should I drop this or send you an overview if you want to take a look?`
  - variant 3 (51 chars, 9 words): `Worth a look, {FIRST_NAME}? I can send an overview.`
  - variant 4 (59 chars, 10 words): `Is this worth pursuing or should I stop here, {FIRST_NAME}?`
  - fallback (69 chars): `Worth a yes or no on this one so I know whether to stop reaching out?`

### 613742 — RESONATE PRODUCTIVE LI B1 SEAT 174822

- ownership: **resonate_os** — `heyreach_campaign_id` present in `work/campaigns.jsonl`
- provider status `PAUSED`; created `2026-09-21T21:26:05.333701Z`; started `2026-09-22T09:10:46.991842Z`
- seats (`campaignAccountIds`): 174822
- lead list `956328` (RESONATE PRODUCTIVE LI B1 SEAT 174822), list size `totalItemsCount` = 5; campaign holds `progressStats.totalUsers` = 5, finished 0
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **5**, accepted **0** (0.00%)
  - messages sent **0**, message threads started **0**, replies **0** (n/a (denominator 0) of threads started)
  - unique leads contacted **5**; profile views 0, follows 5, post likes 0
  - provider's own tags: `autoTaggedInterested` **0**, `totalAutoTagged` **0**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 1 conversations joined, 0 operator-positive replies = **0.000 per 100 requests sent**
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-09-23 .. 2026-09-23 (1 days)
- sequence node types present in the whole graph: CHECK_IS_CONNECTION, CONNECTION_REQUEST, END, FOLLOW, MESSAGE, VIEW_PROFILE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CHECK_IS_CONNECTION   wait 0H      day  0.00
  step 1   MESSAGE               wait 0H      day  0.00
  step 2   MESSAGE               wait 5D      day  5.00
  step 3   MESSAGE               wait 5D      day 10.00
  step 4   END                   wait 3D      day 13.00
```

**Connection note:** 1 `CONNECTION_REQUEST` note slot(s), every one of them EMPTY — this campaign sends connection requests with no note.

**Message steps — our text, in full:**

- message at day 0.00, 3 variant(s):
  - variant 1 (283 chars, 46 words): `Hey {FIRST_NAME},

{Icebreaker}
 
We built Productive so budgets, time tracking and resourcing actually talk to each other, so you can see if a project's making money while it's still running, not just after it gets invoiced.
 
Can show you what that looks like if you're interested.`
  - variant 2 (233 chars, 39 words): `Hi {FIRST_NAME}, {Icebreaker}
 
It's a common one. Productive ties budgets, time and resourcing together so that question has a live answer instead of one you get after the invoice goes out. Can walk you through it if you're curious.`
  - variant 3 (233 chars, 34 words): `Hey {FIRST_NAME},
 
{Icebreaker}
 
That's basically why we built Productive, so budgets, time tracking and resourcing stop living in separate places and you can see project profitability while it's still happening. Happy to show you.`
  - fallback (256 chars): `Hey, we built Productive so budgets, time tracking and resourcing actually talk to each other, so you can see if a project's making money while it's still running, not just after it gets invoiced.
 
Can show you what that looks like if you're interested.

`
- message at day 5.00, 2 variant(s):
  - variant 1 (251 chars, 37 words): `{FIRST_NAME}, random one, but Infinum (software agency, 370+ people) uses Productive to plan resourcing across the whole team without losing sight of which projects are actually profitable.
 
Would something like this make sense for {COMPANY} as well?`
  - variant 2 (253 chars, 41 words): `{FIRST_NAME}, Akcelo (190 people, works with McDonald's and Netflix) uses Productive to stay on top of budgets and reporting across every project. PIABO runs basically the same setup across five offices in Europe. Could it be worth a look for {COMPANY}?`
  - fallback (237 chars): `Random one, but Infinum (software agency, 370+ people) uses Productive to plan resourcing across the whole team without losing sight of which projects are actually profitable.
 
Would something like this make sense for your team as well?`
- message at day 10.00, 4 variant(s):
  - variant 1 (83 chars, 17 words): `{FIRST_NAME}, worth a yes or no on this one so I know whether to stop reaching out?`
  - variant 2 (84 chars, 17 words): `{FIRST_NAME}, should I drop this or send you an overview if you want to take a look?`
  - variant 3 (51 chars, 9 words): `Worth a look, {FIRST_NAME}? I can send an overview.`
  - variant 4 (59 chars, 10 words): `Is this worth pursuing or should I stop here, {FIRST_NAME}?`
  - fallback (69 chars): `Worth a yes or no on this one so I know whether to stop reaching out?`

### 613744 — RESONATE PRODUCTIVE LI B1 SEAT 174892

- ownership: **resonate_os** — `heyreach_campaign_id` present in `work/campaigns.jsonl`
- provider status `PAUSED`; created `2026-09-21T21:26:34.454581Z`; started `2026-09-22T09:10:48.227556Z`
- seats (`campaignAccountIds`): 174892
- lead list `956330` (RESONATE PRODUCTIVE LI B1 SEAT 174892), list size `totalItemsCount` = 4; campaign holds `progressStats.totalUsers` = 4, finished 0
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **4**, accepted **1** (25.00%)
  - messages sent **0**, message threads started **2**, replies **1** (50.00% of threads started)
  - unique leads contacted **5**; profile views 0, follows 4, post likes 0
  - provider's own tags: `autoTaggedInterested` **1**, `totalAutoTagged` **1**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 2 conversations joined, 1 operator-positive replies = **25.000 per 100 requests sent**
- reply classes in this campaign: `unknown` 4, `positive` 1
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-09-23 .. 2026-09-24 (2 days)
- sequence node types present in the whole graph: CHECK_IS_CONNECTION, CONNECTION_REQUEST, END, FOLLOW, MESSAGE, VIEW_PROFILE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CHECK_IS_CONNECTION   wait 0H      day  0.00
  step 1   MESSAGE               wait 0H      day  0.00
  step 2   MESSAGE               wait 5D      day  5.00
  step 3   MESSAGE               wait 5D      day 10.00
  step 4   END                   wait 3D      day 13.00
```

**Connection note:** 1 `CONNECTION_REQUEST` note slot(s), every one of them EMPTY — this campaign sends connection requests with no note.

**Message steps — our text, in full:**

- message at day 0.00, 3 variant(s):
  - variant 1 (283 chars, 46 words): `Hey {FIRST_NAME},

{Icebreaker}
 
We built Productive so budgets, time tracking and resourcing actually talk to each other, so you can see if a project's making money while it's still running, not just after it gets invoiced.
 
Can show you what that looks like if you're interested.`
  - variant 2 (233 chars, 39 words): `Hi {FIRST_NAME}, {Icebreaker}
 
It's a common one. Productive ties budgets, time and resourcing together so that question has a live answer instead of one you get after the invoice goes out. Can walk you through it if you're curious.`
  - variant 3 (233 chars, 34 words): `Hey {FIRST_NAME},
 
{Icebreaker}
 
That's basically why we built Productive, so budgets, time tracking and resourcing stop living in separate places and you can see project profitability while it's still happening. Happy to show you.`
  - fallback (256 chars): `Hey, we built Productive so budgets, time tracking and resourcing actually talk to each other, so you can see if a project's making money while it's still running, not just after it gets invoiced.
 
Can show you what that looks like if you're interested.

`
- message at day 5.00, 2 variant(s):
  - variant 1 (251 chars, 37 words): `{FIRST_NAME}, random one, but Infinum (software agency, 370+ people) uses Productive to plan resourcing across the whole team without losing sight of which projects are actually profitable.
 
Would something like this make sense for {COMPANY} as well?`
  - variant 2 (253 chars, 41 words): `{FIRST_NAME}, Akcelo (190 people, works with McDonald's and Netflix) uses Productive to stay on top of budgets and reporting across every project. PIABO runs basically the same setup across five offices in Europe. Could it be worth a look for {COMPANY}?`
  - fallback (237 chars): `Random one, but Infinum (software agency, 370+ people) uses Productive to plan resourcing across the whole team without losing sight of which projects are actually profitable.
 
Would something like this make sense for your team as well?`
- message at day 10.00, 4 variant(s):
  - variant 1 (83 chars, 17 words): `{FIRST_NAME}, worth a yes or no on this one so I know whether to stop reaching out?`
  - variant 2 (84 chars, 17 words): `{FIRST_NAME}, should I drop this or send you an overview if you want to take a look?`
  - variant 3 (51 chars, 9 words): `Worth a look, {FIRST_NAME}? I can send an overview.`
  - variant 4 (59 chars, 10 words): `Is this worth pursuing or should I stop here, {FIRST_NAME}?`
  - fallback (69 chars): `Worth a yes or no on this one so I know whether to stop reaching out?`

### 613746 — RESONATE PRODUCTIVE LI B1 SEAT 175455

- ownership: **resonate_os** — `heyreach_campaign_id` present in `work/campaigns.jsonl`
- provider status `PAUSED`; created `2026-09-21T21:26:48.106693Z`; started `2026-09-22T09:10:49.309718Z`
- seats (`campaignAccountIds`): 175455
- lead list `956331` (RESONATE PRODUCTIVE LI B1 SEAT 175455), list size `totalItemsCount` = 4; campaign holds `progressStats.totalUsers` = 4, finished 0
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **4**, accepted **0** (0.00%)
  - messages sent **0**, message threads started **0**, replies **0** (n/a (denominator 0) of threads started)
  - unique leads contacted **4**; profile views 0, follows 4, post likes 0
  - provider's own tags: `autoTaggedInterested` **0**, `totalAutoTagged` **0**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 0 conversations joined, 0 operator-positive replies = **0.000 per 100 requests sent**
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-09-22 .. 2026-09-23 (2 days)
- sequence node types present in the whole graph: CHECK_IS_CONNECTION, CONNECTION_REQUEST, END, FOLLOW, MESSAGE, VIEW_PROFILE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CHECK_IS_CONNECTION   wait 0H      day  0.00
  step 1   MESSAGE               wait 0H      day  0.00
  step 2   MESSAGE               wait 5D      day  5.00
  step 3   MESSAGE               wait 5D      day 10.00
  step 4   END                   wait 3D      day 13.00
```

**Connection note:** 1 `CONNECTION_REQUEST` note slot(s), every one of them EMPTY — this campaign sends connection requests with no note.

**Message steps — our text, in full:**

- message at day 0.00, 3 variant(s):
  - variant 1 (283 chars, 46 words): `Hey {FIRST_NAME},

{Icebreaker}
 
We built Productive so budgets, time tracking and resourcing actually talk to each other, so you can see if a project's making money while it's still running, not just after it gets invoiced.
 
Can show you what that looks like if you're interested.`
  - variant 2 (233 chars, 39 words): `Hi {FIRST_NAME}, {Icebreaker}
 
It's a common one. Productive ties budgets, time and resourcing together so that question has a live answer instead of one you get after the invoice goes out. Can walk you through it if you're curious.`
  - variant 3 (233 chars, 34 words): `Hey {FIRST_NAME},
 
{Icebreaker}
 
That's basically why we built Productive, so budgets, time tracking and resourcing stop living in separate places and you can see project profitability while it's still happening. Happy to show you.`
  - fallback (256 chars): `Hey, we built Productive so budgets, time tracking and resourcing actually talk to each other, so you can see if a project's making money while it's still running, not just after it gets invoiced.
 
Can show you what that looks like if you're interested.

`
- message at day 5.00, 2 variant(s):
  - variant 1 (251 chars, 37 words): `{FIRST_NAME}, random one, but Infinum (software agency, 370+ people) uses Productive to plan resourcing across the whole team without losing sight of which projects are actually profitable.
 
Would something like this make sense for {COMPANY} as well?`
  - variant 2 (253 chars, 41 words): `{FIRST_NAME}, Akcelo (190 people, works with McDonald's and Netflix) uses Productive to stay on top of budgets and reporting across every project. PIABO runs basically the same setup across five offices in Europe. Could it be worth a look for {COMPANY}?`
  - fallback (237 chars): `Random one, but Infinum (software agency, 370+ people) uses Productive to plan resourcing across the whole team without losing sight of which projects are actually profitable.
 
Would something like this make sense for your team as well?`
- message at day 10.00, 4 variant(s):
  - variant 1 (83 chars, 17 words): `{FIRST_NAME}, worth a yes or no on this one so I know whether to stop reaching out?`
  - variant 2 (84 chars, 17 words): `{FIRST_NAME}, should I drop this or send you an overview if you want to take a look?`
  - variant 3 (51 chars, 9 words): `Worth a look, {FIRST_NAME}? I can send an overview.`
  - variant 4 (59 chars, 10 words): `Is this worth pursuing or should I stop here, {FIRST_NAME}?`
  - fallback (69 chars): `Worth a yes or no on this one so I know whether to stop reaching out?`

### 613747 — RESONATE PRODUCTIVE LI B1 SEAT 175552

- ownership: **resonate_os** — `heyreach_campaign_id` present in `work/campaigns.jsonl`
- provider status `PAUSED`; created `2026-09-21T21:26:51.1031Z`; started `2026-09-22T09:10:50.264076Z`
- seats (`campaignAccountIds`): 175552
- lead list `956332` (RESONATE PRODUCTIVE LI B1 SEAT 175552), list size `totalItemsCount` = 4; campaign holds `progressStats.totalUsers` = 4, finished 0
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **4**, accepted **0** (0.00%)
  - messages sent **0**, message threads started **0**, replies **0** (n/a (denominator 0) of threads started)
  - unique leads contacted **4**; profile views 0, follows 4, post likes 0
  - provider's own tags: `autoTaggedInterested` **0**, `totalAutoTagged` **0**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 0 conversations joined, 0 operator-positive replies = **0.000 per 100 requests sent**
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-09-22 .. 2026-09-23 (2 days)
- sequence node types present in the whole graph: CHECK_IS_CONNECTION, CONNECTION_REQUEST, END, FOLLOW, MESSAGE, VIEW_PROFILE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CHECK_IS_CONNECTION   wait 0H      day  0.00
  step 1   MESSAGE               wait 0H      day  0.00
  step 2   MESSAGE               wait 5D      day  5.00
  step 3   MESSAGE               wait 5D      day 10.00
  step 4   END                   wait 3D      day 13.00
```

**Connection note:** 1 `CONNECTION_REQUEST` note slot(s), every one of them EMPTY — this campaign sends connection requests with no note.

**Message steps — our text, in full:**

- message at day 0.00, 3 variant(s):
  - variant 1 (283 chars, 46 words): `Hey {FIRST_NAME},

{Icebreaker}
 
We built Productive so budgets, time tracking and resourcing actually talk to each other, so you can see if a project's making money while it's still running, not just after it gets invoiced.
 
Can show you what that looks like if you're interested.`
  - variant 2 (233 chars, 39 words): `Hi {FIRST_NAME}, {Icebreaker}
 
It's a common one. Productive ties budgets, time and resourcing together so that question has a live answer instead of one you get after the invoice goes out. Can walk you through it if you're curious.`
  - variant 3 (233 chars, 34 words): `Hey {FIRST_NAME},
 
{Icebreaker}
 
That's basically why we built Productive, so budgets, time tracking and resourcing stop living in separate places and you can see project profitability while it's still happening. Happy to show you.`
  - fallback (256 chars): `Hey, we built Productive so budgets, time tracking and resourcing actually talk to each other, so you can see if a project's making money while it's still running, not just after it gets invoiced.
 
Can show you what that looks like if you're interested.

`
- message at day 5.00, 2 variant(s):
  - variant 1 (251 chars, 37 words): `{FIRST_NAME}, random one, but Infinum (software agency, 370+ people) uses Productive to plan resourcing across the whole team without losing sight of which projects are actually profitable.
 
Would something like this make sense for {COMPANY} as well?`
  - variant 2 (253 chars, 41 words): `{FIRST_NAME}, Akcelo (190 people, works with McDonald's and Netflix) uses Productive to stay on top of budgets and reporting across every project. PIABO runs basically the same setup across five offices in Europe. Could it be worth a look for {COMPANY}?`
  - fallback (237 chars): `Random one, but Infinum (software agency, 370+ people) uses Productive to plan resourcing across the whole team without losing sight of which projects are actually profitable.
 
Would something like this make sense for your team as well?`
- message at day 10.00, 4 variant(s):
  - variant 1 (83 chars, 17 words): `{FIRST_NAME}, worth a yes or no on this one so I know whether to stop reaching out?`
  - variant 2 (84 chars, 17 words): `{FIRST_NAME}, should I drop this or send you an overview if you want to take a look?`
  - variant 3 (51 chars, 9 words): `Worth a look, {FIRST_NAME}? I can send an overview.`
  - variant 4 (59 chars, 10 words): `Is this worth pursuing or should I stop here, {FIRST_NAME}?`
  - fallback (69 chars): `Worth a yes or no on this one so I know whether to stop reaching out?`

### 613748 — RESONATE PRODUCTIVE LI B1 SEAT 177751

- ownership: **resonate_os** — `heyreach_campaign_id` present in `work/campaigns.jsonl`
- provider status `PAUSED`; created `2026-09-21T21:26:54.146552Z`; started `2026-09-22T09:10:51.849924Z`
- seats (`campaignAccountIds`): 177751
- lead list `956333` (RESONATE PRODUCTIVE LI B1 SEAT 177751), list size `totalItemsCount` = 4; campaign holds `progressStats.totalUsers` = 4, finished 0
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **4**, accepted **0** (0.00%)
  - messages sent **0**, message threads started **0**, replies **0** (n/a (denominator 0) of threads started)
  - unique leads contacted **4**; profile views 0, follows 4, post likes 0
  - provider's own tags: `autoTaggedInterested` **0**, `totalAutoTagged` **0**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 0 conversations joined, 0 operator-positive replies = **0.000 per 100 requests sent**
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-09-22 .. 2026-09-22 (1 days)
- sequence node types present in the whole graph: CHECK_IS_CONNECTION, CONNECTION_REQUEST, END, FOLLOW, MESSAGE, VIEW_PROFILE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CHECK_IS_CONNECTION   wait 0H      day  0.00
  step 1   MESSAGE               wait 0H      day  0.00
  step 2   MESSAGE               wait 5D      day  5.00
  step 3   MESSAGE               wait 5D      day 10.00
  step 4   END                   wait 3D      day 13.00
```

**Connection note:** 1 `CONNECTION_REQUEST` note slot(s), every one of them EMPTY — this campaign sends connection requests with no note.

**Message steps — our text, in full:**

- message at day 0.00, 3 variant(s):
  - variant 1 (283 chars, 46 words): `Hey {FIRST_NAME},

{Icebreaker}
 
We built Productive so budgets, time tracking and resourcing actually talk to each other, so you can see if a project's making money while it's still running, not just after it gets invoiced.
 
Can show you what that looks like if you're interested.`
  - variant 2 (233 chars, 39 words): `Hi {FIRST_NAME}, {Icebreaker}
 
It's a common one. Productive ties budgets, time and resourcing together so that question has a live answer instead of one you get after the invoice goes out. Can walk you through it if you're curious.`
  - variant 3 (233 chars, 34 words): `Hey {FIRST_NAME},
 
{Icebreaker}
 
That's basically why we built Productive, so budgets, time tracking and resourcing stop living in separate places and you can see project profitability while it's still happening. Happy to show you.`
  - fallback (256 chars): `Hey, we built Productive so budgets, time tracking and resourcing actually talk to each other, so you can see if a project's making money while it's still running, not just after it gets invoiced.
 
Can show you what that looks like if you're interested.

`
- message at day 5.00, 2 variant(s):
  - variant 1 (251 chars, 37 words): `{FIRST_NAME}, random one, but Infinum (software agency, 370+ people) uses Productive to plan resourcing across the whole team without losing sight of which projects are actually profitable.
 
Would something like this make sense for {COMPANY} as well?`
  - variant 2 (253 chars, 41 words): `{FIRST_NAME}, Akcelo (190 people, works with McDonald's and Netflix) uses Productive to stay on top of budgets and reporting across every project. PIABO runs basically the same setup across five offices in Europe. Could it be worth a look for {COMPANY}?`
  - fallback (237 chars): `Random one, but Infinum (software agency, 370+ people) uses Productive to plan resourcing across the whole team without losing sight of which projects are actually profitable.
 
Would something like this make sense for your team as well?`
- message at day 10.00, 4 variant(s):
  - variant 1 (83 chars, 17 words): `{FIRST_NAME}, worth a yes or no on this one so I know whether to stop reaching out?`
  - variant 2 (84 chars, 17 words): `{FIRST_NAME}, should I drop this or send you an overview if you want to take a look?`
  - variant 3 (51 chars, 9 words): `Worth a look, {FIRST_NAME}? I can send an overview.`
  - variant 4 (59 chars, 10 words): `Is this worth pursuing or should I stop here, {FIRST_NAME}?`
  - fallback (69 chars): `Worth a yes or no on this one so I know whether to stop reaching out?`

### 613749 — RESONATE PRODUCTIVE LI B1 SEAT 179527

- ownership: **resonate_os** — `heyreach_campaign_id` present in `work/campaigns.jsonl`
- provider status `PAUSED`; created `2026-09-21T21:26:56.814199Z`; started `2026-09-22T09:10:53.15323Z`
- seats (`campaignAccountIds`): 179527
- lead list `956334` (RESONATE PRODUCTIVE LI B1 SEAT 179527), list size `totalItemsCount` = 4; campaign holds `progressStats.totalUsers` = 4, finished 0
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **0**, accepted **0** (n/a (denominator 0))
  - messages sent **0**, message threads started **0**, replies **0** (n/a (denominator 0) of threads started)
  - unique leads contacted **0**; profile views 0, follows 4, post likes 0
  - provider's own tags: `autoTaggedInterested` **0**, `totalAutoTagged` **0**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 0 conversations joined, 0 operator-positive replies = **n/a (0 requests sent) per 100 requests sent**
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- sequence node types present in the whole graph: CHECK_IS_CONNECTION, CONNECTION_REQUEST, END, FOLLOW, MESSAGE, VIEW_PROFILE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CHECK_IS_CONNECTION   wait 0H      day  0.00
  step 1   MESSAGE               wait 0H      day  0.00
  step 2   MESSAGE               wait 5D      day  5.00
  step 3   MESSAGE               wait 5D      day 10.00
  step 4   END                   wait 3D      day 13.00
```

**Connection note:** 1 `CONNECTION_REQUEST` note slot(s), every one of them EMPTY — this campaign sends connection requests with no note.

**Message steps — our text, in full:**

- message at day 0.00, 3 variant(s):
  - variant 1 (283 chars, 46 words): `Hey {FIRST_NAME},

{Icebreaker}
 
We built Productive so budgets, time tracking and resourcing actually talk to each other, so you can see if a project's making money while it's still running, not just after it gets invoiced.
 
Can show you what that looks like if you're interested.`
  - variant 2 (233 chars, 39 words): `Hi {FIRST_NAME}, {Icebreaker}
 
It's a common one. Productive ties budgets, time and resourcing together so that question has a live answer instead of one you get after the invoice goes out. Can walk you through it if you're curious.`
  - variant 3 (233 chars, 34 words): `Hey {FIRST_NAME},
 
{Icebreaker}
 
That's basically why we built Productive, so budgets, time tracking and resourcing stop living in separate places and you can see project profitability while it's still happening. Happy to show you.`
  - fallback (256 chars): `Hey, we built Productive so budgets, time tracking and resourcing actually talk to each other, so you can see if a project's making money while it's still running, not just after it gets invoiced.
 
Can show you what that looks like if you're interested.

`
- message at day 5.00, 2 variant(s):
  - variant 1 (251 chars, 37 words): `{FIRST_NAME}, random one, but Infinum (software agency, 370+ people) uses Productive to plan resourcing across the whole team without losing sight of which projects are actually profitable.
 
Would something like this make sense for {COMPANY} as well?`
  - variant 2 (253 chars, 41 words): `{FIRST_NAME}, Akcelo (190 people, works with McDonald's and Netflix) uses Productive to stay on top of budgets and reporting across every project. PIABO runs basically the same setup across five offices in Europe. Could it be worth a look for {COMPANY}?`
  - fallback (237 chars): `Random one, but Infinum (software agency, 370+ people) uses Productive to plan resourcing across the whole team without losing sight of which projects are actually profitable.
 
Would something like this make sense for your team as well?`
- message at day 10.00, 4 variant(s):
  - variant 1 (83 chars, 17 words): `{FIRST_NAME}, worth a yes or no on this one so I know whether to stop reaching out?`
  - variant 2 (84 chars, 17 words): `{FIRST_NAME}, should I drop this or send you an overview if you want to take a look?`
  - variant 3 (51 chars, 9 words): `Worth a look, {FIRST_NAME}? I can send an overview.`
  - variant 4 (59 chars, 10 words): `Is this worth pursuing or should I stop here, {FIRST_NAME}?`
  - fallback (69 chars): `Worth a yes or no on this one so I know whether to stop reaching out?`

### 613750 — RESONATE PRODUCTIVE LI B1 SEAT 181653

- ownership: **resonate_os** — `heyreach_campaign_id` present in `work/campaigns.jsonl`
- provider status `PAUSED`; created `2026-09-21T21:27:00.169626Z`; started `2026-09-22T09:10:54.207826Z`
- seats (`campaignAccountIds`): 181653
- lead list `956335` (RESONATE PRODUCTIVE LI B1 SEAT 181653), list size `totalItemsCount` = 4; campaign holds `progressStats.totalUsers` = 4, finished 0
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **4**, accepted **0** (0.00%)
  - messages sent **0**, message threads started **0**, replies **0** (n/a (denominator 0) of threads started)
  - unique leads contacted **4**; profile views 0, follows 4, post likes 0
  - provider's own tags: `autoTaggedInterested` **0**, `totalAutoTagged` **0**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 0 conversations joined, 0 operator-positive replies = **0.000 per 100 requests sent**
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-09-23 .. 2026-09-23 (1 days)
- sequence node types present in the whole graph: CHECK_IS_CONNECTION, CONNECTION_REQUEST, END, FOLLOW, MESSAGE, VIEW_PROFILE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CHECK_IS_CONNECTION   wait 0H      day  0.00
  step 1   MESSAGE               wait 0H      day  0.00
  step 2   MESSAGE               wait 5D      day  5.00
  step 3   MESSAGE               wait 5D      day 10.00
  step 4   END                   wait 3D      day 13.00
```

**Connection note:** 1 `CONNECTION_REQUEST` note slot(s), every one of them EMPTY — this campaign sends connection requests with no note.

**Message steps — our text, in full:**

- message at day 0.00, 3 variant(s):
  - variant 1 (283 chars, 46 words): `Hey {FIRST_NAME},

{Icebreaker}
 
We built Productive so budgets, time tracking and resourcing actually talk to each other, so you can see if a project's making money while it's still running, not just after it gets invoiced.
 
Can show you what that looks like if you're interested.`
  - variant 2 (233 chars, 39 words): `Hi {FIRST_NAME}, {Icebreaker}
 
It's a common one. Productive ties budgets, time and resourcing together so that question has a live answer instead of one you get after the invoice goes out. Can walk you through it if you're curious.`
  - variant 3 (233 chars, 34 words): `Hey {FIRST_NAME},
 
{Icebreaker}
 
That's basically why we built Productive, so budgets, time tracking and resourcing stop living in separate places and you can see project profitability while it's still happening. Happy to show you.`
  - fallback (256 chars): `Hey, we built Productive so budgets, time tracking and resourcing actually talk to each other, so you can see if a project's making money while it's still running, not just after it gets invoiced.
 
Can show you what that looks like if you're interested.

`
- message at day 5.00, 2 variant(s):
  - variant 1 (251 chars, 37 words): `{FIRST_NAME}, random one, but Infinum (software agency, 370+ people) uses Productive to plan resourcing across the whole team without losing sight of which projects are actually profitable.
 
Would something like this make sense for {COMPANY} as well?`
  - variant 2 (253 chars, 41 words): `{FIRST_NAME}, Akcelo (190 people, works with McDonald's and Netflix) uses Productive to stay on top of budgets and reporting across every project. PIABO runs basically the same setup across five offices in Europe. Could it be worth a look for {COMPANY}?`
  - fallback (237 chars): `Random one, but Infinum (software agency, 370+ people) uses Productive to plan resourcing across the whole team without losing sight of which projects are actually profitable.
 
Would something like this make sense for your team as well?`
- message at day 10.00, 4 variant(s):
  - variant 1 (83 chars, 17 words): `{FIRST_NAME}, worth a yes or no on this one so I know whether to stop reaching out?`
  - variant 2 (84 chars, 17 words): `{FIRST_NAME}, should I drop this or send you an overview if you want to take a look?`
  - variant 3 (51 chars, 9 words): `Worth a look, {FIRST_NAME}? I can send an overview.`
  - variant 4 (59 chars, 10 words): `Is this worth pursuing or should I stop here, {FIRST_NAME}?`
  - fallback (69 chars): `Worth a yes or no on this one so I know whether to stop reaching out?`

### 613751 — RESONATE PRODUCTIVE LI B1 SEAT 181658

- ownership: **resonate_os** — `heyreach_campaign_id` present in `work/campaigns.jsonl`
- provider status `PAUSED`; created `2026-09-21T21:27:03.160309Z`; started `2026-09-22T09:10:55.173205Z`
- seats (`campaignAccountIds`): 181658
- lead list `956336` (RESONATE PRODUCTIVE LI B1 SEAT 181658), list size `totalItemsCount` = 4; campaign holds `progressStats.totalUsers` = 4, finished 0
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **4**, accepted **1** (25.00%)
  - messages sent **0**, message threads started **0**, replies **0** (n/a (denominator 0) of threads started)
  - unique leads contacted **4**; profile views 0, follows 4, post likes 0
  - provider's own tags: `autoTaggedInterested` **0**, `totalAutoTagged` **0**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 0 conversations joined, 0 operator-positive replies = **0.000 per 100 requests sent**
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-09-22 .. 2026-09-22 (1 days)
- sequence node types present in the whole graph: CHECK_IS_CONNECTION, CONNECTION_REQUEST, END, FOLLOW, MESSAGE, VIEW_PROFILE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CHECK_IS_CONNECTION   wait 0H      day  0.00
  step 1   MESSAGE               wait 0H      day  0.00
  step 2   MESSAGE               wait 5D      day  5.00
  step 3   MESSAGE               wait 5D      day 10.00
  step 4   END                   wait 3D      day 13.00
```

**Connection note:** 1 `CONNECTION_REQUEST` note slot(s), every one of them EMPTY — this campaign sends connection requests with no note.

**Message steps — our text, in full:**

- message at day 0.00, 3 variant(s):
  - variant 1 (283 chars, 46 words): `Hey {FIRST_NAME},

{Icebreaker}
 
We built Productive so budgets, time tracking and resourcing actually talk to each other, so you can see if a project's making money while it's still running, not just after it gets invoiced.
 
Can show you what that looks like if you're interested.`
  - variant 2 (233 chars, 39 words): `Hi {FIRST_NAME}, {Icebreaker}
 
It's a common one. Productive ties budgets, time and resourcing together so that question has a live answer instead of one you get after the invoice goes out. Can walk you through it if you're curious.`
  - variant 3 (233 chars, 34 words): `Hey {FIRST_NAME},
 
{Icebreaker}
 
That's basically why we built Productive, so budgets, time tracking and resourcing stop living in separate places and you can see project profitability while it's still happening. Happy to show you.`
  - fallback (256 chars): `Hey, we built Productive so budgets, time tracking and resourcing actually talk to each other, so you can see if a project's making money while it's still running, not just after it gets invoiced.
 
Can show you what that looks like if you're interested.

`
- message at day 5.00, 2 variant(s):
  - variant 1 (251 chars, 37 words): `{FIRST_NAME}, random one, but Infinum (software agency, 370+ people) uses Productive to plan resourcing across the whole team without losing sight of which projects are actually profitable.
 
Would something like this make sense for {COMPANY} as well?`
  - variant 2 (253 chars, 41 words): `{FIRST_NAME}, Akcelo (190 people, works with McDonald's and Netflix) uses Productive to stay on top of budgets and reporting across every project. PIABO runs basically the same setup across five offices in Europe. Could it be worth a look for {COMPANY}?`
  - fallback (237 chars): `Random one, but Infinum (software agency, 370+ people) uses Productive to plan resourcing across the whole team without losing sight of which projects are actually profitable.
 
Would something like this make sense for your team as well?`
- message at day 10.00, 4 variant(s):
  - variant 1 (83 chars, 17 words): `{FIRST_NAME}, worth a yes or no on this one so I know whether to stop reaching out?`
  - variant 2 (84 chars, 17 words): `{FIRST_NAME}, should I drop this or send you an overview if you want to take a look?`
  - variant 3 (51 chars, 9 words): `Worth a look, {FIRST_NAME}? I can send an overview.`
  - variant 4 (59 chars, 10 words): `Is this worth pursuing or should I stop here, {FIRST_NAME}?`
  - fallback (69 chars): `Worth a yes or no on this one so I know whether to stop reaching out?`

### 613752 — RESONATE PRODUCTIVE LI B1 SEAT 191848

- ownership: **resonate_os** — `heyreach_campaign_id` present in `work/campaigns.jsonl`
- provider status `PAUSED`; created `2026-09-21T21:27:06.846844Z`; started `2026-09-22T09:10:56.73045Z`
- seats (`campaignAccountIds`): 191848
- lead list `956337` (RESONATE PRODUCTIVE LI B1 SEAT 191848), list size `totalItemsCount` = 4; campaign holds `progressStats.totalUsers` = 4, finished 0
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **4**, accepted **0** (0.00%)
  - messages sent **0**, message threads started **0**, replies **0** (n/a (denominator 0) of threads started)
  - unique leads contacted **4**; profile views 0, follows 4, post likes 0
  - provider's own tags: `autoTaggedInterested` **0**, `totalAutoTagged` **0**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 0 conversations joined, 0 operator-positive replies = **0.000 per 100 requests sent**
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-09-22 .. 2026-09-23 (2 days)
- sequence node types present in the whole graph: CHECK_IS_CONNECTION, CONNECTION_REQUEST, END, FOLLOW, MESSAGE, VIEW_PROFILE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CHECK_IS_CONNECTION   wait 0H      day  0.00
  step 1   MESSAGE               wait 0H      day  0.00
  step 2   MESSAGE               wait 5D      day  5.00
  step 3   MESSAGE               wait 5D      day 10.00
  step 4   END                   wait 3D      day 13.00
```

**Connection note:** 1 `CONNECTION_REQUEST` note slot(s), every one of them EMPTY — this campaign sends connection requests with no note.

**Message steps — our text, in full:**

- message at day 0.00, 3 variant(s):
  - variant 1 (283 chars, 46 words): `Hey {FIRST_NAME},

{Icebreaker}
 
We built Productive so budgets, time tracking and resourcing actually talk to each other, so you can see if a project's making money while it's still running, not just after it gets invoiced.
 
Can show you what that looks like if you're interested.`
  - variant 2 (233 chars, 39 words): `Hi {FIRST_NAME}, {Icebreaker}
 
It's a common one. Productive ties budgets, time and resourcing together so that question has a live answer instead of one you get after the invoice goes out. Can walk you through it if you're curious.`
  - variant 3 (233 chars, 34 words): `Hey {FIRST_NAME},
 
{Icebreaker}
 
That's basically why we built Productive, so budgets, time tracking and resourcing stop living in separate places and you can see project profitability while it's still happening. Happy to show you.`
  - fallback (256 chars): `Hey, we built Productive so budgets, time tracking and resourcing actually talk to each other, so you can see if a project's making money while it's still running, not just after it gets invoiced.
 
Can show you what that looks like if you're interested.

`
- message at day 5.00, 2 variant(s):
  - variant 1 (251 chars, 37 words): `{FIRST_NAME}, random one, but Infinum (software agency, 370+ people) uses Productive to plan resourcing across the whole team without losing sight of which projects are actually profitable.
 
Would something like this make sense for {COMPANY} as well?`
  - variant 2 (253 chars, 41 words): `{FIRST_NAME}, Akcelo (190 people, works with McDonald's and Netflix) uses Productive to stay on top of budgets and reporting across every project. PIABO runs basically the same setup across five offices in Europe. Could it be worth a look for {COMPANY}?`
  - fallback (237 chars): `Random one, but Infinum (software agency, 370+ people) uses Productive to plan resourcing across the whole team without losing sight of which projects are actually profitable.
 
Would something like this make sense for your team as well?`
- message at day 10.00, 4 variant(s):
  - variant 1 (83 chars, 17 words): `{FIRST_NAME}, worth a yes or no on this one so I know whether to stop reaching out?`
  - variant 2 (84 chars, 17 words): `{FIRST_NAME}, should I drop this or send you an overview if you want to take a look?`
  - variant 3 (51 chars, 9 words): `Worth a look, {FIRST_NAME}? I can send an overview.`
  - variant 4 (59 chars, 10 words): `Is this worth pursuing or should I stop here, {FIRST_NAME}?`
  - fallback (69 chars): `Worth a yes or no on this one so I know whether to stop reaching out?`

### 613753 — RESONATE PRODUCTIVE LI B1 SEAT 201959

- ownership: **resonate_os** — `heyreach_campaign_id` present in `work/campaigns.jsonl`
- provider status `PAUSED`; created `2026-09-21T21:27:09.713461Z`; started `2026-09-22T09:10:57.929754Z`
- seats (`campaignAccountIds`): 201959
- lead list `956338` (RESONATE PRODUCTIVE LI B1 SEAT 201959), list size `totalItemsCount` = 4; campaign holds `progressStats.totalUsers` = 4, finished 0
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **4**, accepted **0** (0.00%)
  - messages sent **0**, message threads started **0**, replies **0** (n/a (denominator 0) of threads started)
  - unique leads contacted **4**; profile views 0, follows 4, post likes 0
  - provider's own tags: `autoTaggedInterested` **0**, `totalAutoTagged` **0**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 0 conversations joined, 0 operator-positive replies = **0.000 per 100 requests sent**
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-09-24 .. 2026-09-24 (1 days)
- sequence node types present in the whole graph: CHECK_IS_CONNECTION, CONNECTION_REQUEST, END, FOLLOW, MESSAGE, VIEW_PROFILE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CHECK_IS_CONNECTION   wait 0H      day  0.00
  step 1   MESSAGE               wait 0H      day  0.00
  step 2   MESSAGE               wait 5D      day  5.00
  step 3   MESSAGE               wait 5D      day 10.00
  step 4   END                   wait 3D      day 13.00
```

**Connection note:** 1 `CONNECTION_REQUEST` note slot(s), every one of them EMPTY — this campaign sends connection requests with no note.

**Message steps — our text, in full:**

- message at day 0.00, 3 variant(s):
  - variant 1 (283 chars, 46 words): `Hey {FIRST_NAME},

{Icebreaker}
 
We built Productive so budgets, time tracking and resourcing actually talk to each other, so you can see if a project's making money while it's still running, not just after it gets invoiced.
 
Can show you what that looks like if you're interested.`
  - variant 2 (233 chars, 39 words): `Hi {FIRST_NAME}, {Icebreaker}
 
It's a common one. Productive ties budgets, time and resourcing together so that question has a live answer instead of one you get after the invoice goes out. Can walk you through it if you're curious.`
  - variant 3 (233 chars, 34 words): `Hey {FIRST_NAME},
 
{Icebreaker}
 
That's basically why we built Productive, so budgets, time tracking and resourcing stop living in separate places and you can see project profitability while it's still happening. Happy to show you.`
  - fallback (256 chars): `Hey, we built Productive so budgets, time tracking and resourcing actually talk to each other, so you can see if a project's making money while it's still running, not just after it gets invoiced.
 
Can show you what that looks like if you're interested.

`
- message at day 5.00, 2 variant(s):
  - variant 1 (251 chars, 37 words): `{FIRST_NAME}, random one, but Infinum (software agency, 370+ people) uses Productive to plan resourcing across the whole team without losing sight of which projects are actually profitable.
 
Would something like this make sense for {COMPANY} as well?`
  - variant 2 (253 chars, 41 words): `{FIRST_NAME}, Akcelo (190 people, works with McDonald's and Netflix) uses Productive to stay on top of budgets and reporting across every project. PIABO runs basically the same setup across five offices in Europe. Could it be worth a look for {COMPANY}?`
  - fallback (237 chars): `Random one, but Infinum (software agency, 370+ people) uses Productive to plan resourcing across the whole team without losing sight of which projects are actually profitable.
 
Would something like this make sense for your team as well?`
- message at day 10.00, 4 variant(s):
  - variant 1 (83 chars, 17 words): `{FIRST_NAME}, worth a yes or no on this one so I know whether to stop reaching out?`
  - variant 2 (84 chars, 17 words): `{FIRST_NAME}, should I drop this or send you an overview if you want to take a look?`
  - variant 3 (51 chars, 9 words): `Worth a look, {FIRST_NAME}? I can send an overview.`
  - variant 4 (59 chars, 10 words): `Is this worth pursuing or should I stop here, {FIRST_NAME}?`
  - fallback (69 chars): `Worth a yes or no on this one so I know whether to stop reaching out?`

### 613754 — RESONATE PRODUCTIVE LI B1 SEAT 201978

- ownership: **resonate_os** — `heyreach_campaign_id` present in `work/campaigns.jsonl`
- provider status `PAUSED`; created `2026-09-21T21:27:12.584643Z`; started `2026-09-22T09:10:59.072084Z`
- seats (`campaignAccountIds`): 201978
- lead list `956339` (RESONATE PRODUCTIVE LI B1 SEAT 201978), list size `totalItemsCount` = 4; campaign holds `progressStats.totalUsers` = 4, finished 0
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **4**, accepted **0** (0.00%)
  - messages sent **0**, message threads started **0**, replies **0** (n/a (denominator 0) of threads started)
  - unique leads contacted **4**; profile views 0, follows 4, post likes 0
  - provider's own tags: `autoTaggedInterested` **0**, `totalAutoTagged` **0**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 0 conversations joined, 0 operator-positive replies = **0.000 per 100 requests sent**
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-09-22 .. 2026-09-23 (2 days)
- sequence node types present in the whole graph: CHECK_IS_CONNECTION, CONNECTION_REQUEST, END, FOLLOW, MESSAGE, VIEW_PROFILE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CHECK_IS_CONNECTION   wait 0H      day  0.00
  step 1   MESSAGE               wait 0H      day  0.00
  step 2   MESSAGE               wait 5D      day  5.00
  step 3   MESSAGE               wait 5D      day 10.00
  step 4   END                   wait 3D      day 13.00
```

**Connection note:** 1 `CONNECTION_REQUEST` note slot(s), every one of them EMPTY — this campaign sends connection requests with no note.

**Message steps — our text, in full:**

- message at day 0.00, 3 variant(s):
  - variant 1 (283 chars, 46 words): `Hey {FIRST_NAME},

{Icebreaker}
 
We built Productive so budgets, time tracking and resourcing actually talk to each other, so you can see if a project's making money while it's still running, not just after it gets invoiced.
 
Can show you what that looks like if you're interested.`
  - variant 2 (233 chars, 39 words): `Hi {FIRST_NAME}, {Icebreaker}
 
It's a common one. Productive ties budgets, time and resourcing together so that question has a live answer instead of one you get after the invoice goes out. Can walk you through it if you're curious.`
  - variant 3 (233 chars, 34 words): `Hey {FIRST_NAME},
 
{Icebreaker}
 
That's basically why we built Productive, so budgets, time tracking and resourcing stop living in separate places and you can see project profitability while it's still happening. Happy to show you.`
  - fallback (256 chars): `Hey, we built Productive so budgets, time tracking and resourcing actually talk to each other, so you can see if a project's making money while it's still running, not just after it gets invoiced.
 
Can show you what that looks like if you're interested.

`
- message at day 5.00, 2 variant(s):
  - variant 1 (251 chars, 37 words): `{FIRST_NAME}, random one, but Infinum (software agency, 370+ people) uses Productive to plan resourcing across the whole team without losing sight of which projects are actually profitable.
 
Would something like this make sense for {COMPANY} as well?`
  - variant 2 (253 chars, 41 words): `{FIRST_NAME}, Akcelo (190 people, works with McDonald's and Netflix) uses Productive to stay on top of budgets and reporting across every project. PIABO runs basically the same setup across five offices in Europe. Could it be worth a look for {COMPANY}?`
  - fallback (237 chars): `Random one, but Infinum (software agency, 370+ people) uses Productive to plan resourcing across the whole team without losing sight of which projects are actually profitable.
 
Would something like this make sense for your team as well?`
- message at day 10.00, 4 variant(s):
  - variant 1 (83 chars, 17 words): `{FIRST_NAME}, worth a yes or no on this one so I know whether to stop reaching out?`
  - variant 2 (84 chars, 17 words): `{FIRST_NAME}, should I drop this or send you an overview if you want to take a look?`
  - variant 3 (51 chars, 9 words): `Worth a look, {FIRST_NAME}? I can send an overview.`
  - variant 4 (59 chars, 10 words): `Is this worth pursuing or should I stop here, {FIRST_NAME}?`
  - fallback (69 chars): `Worth a yes or no on this one so I know whether to stop reaching out?`

### 613755 — RESONATE PRODUCTIVE LI B1 SEAT 208242

- ownership: **resonate_os** — `heyreach_campaign_id` present in `work/campaigns.jsonl`
- provider status `PAUSED`; created `2026-09-21T21:27:16.19363Z`; started `2026-09-22T09:11:00.103092Z`
- seats (`campaignAccountIds`): 208242
- lead list `956340` (RESONATE PRODUCTIVE LI B1 SEAT 208242), list size `totalItemsCount` = 4; campaign holds `progressStats.totalUsers` = 4, finished 0
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **4**, accepted **0** (0.00%)
  - messages sent **0**, message threads started **0**, replies **0** (n/a (denominator 0) of threads started)
  - unique leads contacted **4**; profile views 0, follows 4, post likes 0
  - provider's own tags: `autoTaggedInterested` **0**, `totalAutoTagged` **0**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 0 conversations joined, 0 operator-positive replies = **0.000 per 100 requests sent**
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-09-22 .. 2026-09-22 (1 days)
- sequence node types present in the whole graph: CHECK_IS_CONNECTION, CONNECTION_REQUEST, END, FOLLOW, MESSAGE, VIEW_PROFILE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CHECK_IS_CONNECTION   wait 0H      day  0.00
  step 1   MESSAGE               wait 0H      day  0.00
  step 2   MESSAGE               wait 5D      day  5.00
  step 3   MESSAGE               wait 5D      day 10.00
  step 4   END                   wait 3D      day 13.00
```

**Connection note:** 1 `CONNECTION_REQUEST` note slot(s), every one of them EMPTY — this campaign sends connection requests with no note.

**Message steps — our text, in full:**

- message at day 0.00, 3 variant(s):
  - variant 1 (283 chars, 46 words): `Hey {FIRST_NAME},

{Icebreaker}
 
We built Productive so budgets, time tracking and resourcing actually talk to each other, so you can see if a project's making money while it's still running, not just after it gets invoiced.
 
Can show you what that looks like if you're interested.`
  - variant 2 (233 chars, 39 words): `Hi {FIRST_NAME}, {Icebreaker}
 
It's a common one. Productive ties budgets, time and resourcing together so that question has a live answer instead of one you get after the invoice goes out. Can walk you through it if you're curious.`
  - variant 3 (233 chars, 34 words): `Hey {FIRST_NAME},
 
{Icebreaker}
 
That's basically why we built Productive, so budgets, time tracking and resourcing stop living in separate places and you can see project profitability while it's still happening. Happy to show you.`
  - fallback (256 chars): `Hey, we built Productive so budgets, time tracking and resourcing actually talk to each other, so you can see if a project's making money while it's still running, not just after it gets invoiced.
 
Can show you what that looks like if you're interested.

`
- message at day 5.00, 2 variant(s):
  - variant 1 (251 chars, 37 words): `{FIRST_NAME}, random one, but Infinum (software agency, 370+ people) uses Productive to plan resourcing across the whole team without losing sight of which projects are actually profitable.
 
Would something like this make sense for {COMPANY} as well?`
  - variant 2 (253 chars, 41 words): `{FIRST_NAME}, Akcelo (190 people, works with McDonald's and Netflix) uses Productive to stay on top of budgets and reporting across every project. PIABO runs basically the same setup across five offices in Europe. Could it be worth a look for {COMPANY}?`
  - fallback (237 chars): `Random one, but Infinum (software agency, 370+ people) uses Productive to plan resourcing across the whole team without losing sight of which projects are actually profitable.
 
Would something like this make sense for your team as well?`
- message at day 10.00, 4 variant(s):
  - variant 1 (83 chars, 17 words): `{FIRST_NAME}, worth a yes or no on this one so I know whether to stop reaching out?`
  - variant 2 (84 chars, 17 words): `{FIRST_NAME}, should I drop this or send you an overview if you want to take a look?`
  - variant 3 (51 chars, 9 words): `Worth a look, {FIRST_NAME}? I can send an overview.`
  - variant 4 (59 chars, 10 words): `Is this worth pursuing or should I stop here, {FIRST_NAME}?`
  - fallback (69 chars): `Worth a yes or no on this one so I know whether to stop reaching out?`

### 613756 — RESONATE PRODUCTIVE LI B1 SEAT 208253

- ownership: **resonate_os** — `heyreach_campaign_id` present in `work/campaigns.jsonl`
- provider status `PAUSED`; created `2026-09-21T21:27:19.042957Z`; started `2026-09-22T09:11:01.739151Z`
- seats (`campaignAccountIds`): 208253
- lead list `956341` (RESONATE PRODUCTIVE LI B1 SEAT 208253), list size `totalItemsCount` = 4; campaign holds `progressStats.totalUsers` = 4, finished 0
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **4**, accepted **0** (0.00%)
  - messages sent **0**, message threads started **0**, replies **0** (n/a (denominator 0) of threads started)
  - unique leads contacted **4**; profile views 0, follows 4, post likes 0
  - provider's own tags: `autoTaggedInterested` **0**, `totalAutoTagged` **0**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 0 conversations joined, 0 operator-positive replies = **0.000 per 100 requests sent**
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-09-22 .. 2026-09-23 (2 days)
- sequence node types present in the whole graph: CHECK_IS_CONNECTION, CONNECTION_REQUEST, END, FOLLOW, MESSAGE, VIEW_PROFILE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CHECK_IS_CONNECTION   wait 0H      day  0.00
  step 1   MESSAGE               wait 0H      day  0.00
  step 2   MESSAGE               wait 5D      day  5.00
  step 3   MESSAGE               wait 5D      day 10.00
  step 4   END                   wait 3D      day 13.00
```

**Connection note:** 1 `CONNECTION_REQUEST` note slot(s), every one of them EMPTY — this campaign sends connection requests with no note.

**Message steps — our text, in full:**

- message at day 0.00, 3 variant(s):
  - variant 1 (283 chars, 46 words): `Hey {FIRST_NAME},

{Icebreaker}
 
We built Productive so budgets, time tracking and resourcing actually talk to each other, so you can see if a project's making money while it's still running, not just after it gets invoiced.
 
Can show you what that looks like if you're interested.`
  - variant 2 (233 chars, 39 words): `Hi {FIRST_NAME}, {Icebreaker}
 
It's a common one. Productive ties budgets, time and resourcing together so that question has a live answer instead of one you get after the invoice goes out. Can walk you through it if you're curious.`
  - variant 3 (233 chars, 34 words): `Hey {FIRST_NAME},
 
{Icebreaker}
 
That's basically why we built Productive, so budgets, time tracking and resourcing stop living in separate places and you can see project profitability while it's still happening. Happy to show you.`
  - fallback (256 chars): `Hey, we built Productive so budgets, time tracking and resourcing actually talk to each other, so you can see if a project's making money while it's still running, not just after it gets invoiced.
 
Can show you what that looks like if you're interested.

`
- message at day 5.00, 2 variant(s):
  - variant 1 (251 chars, 37 words): `{FIRST_NAME}, random one, but Infinum (software agency, 370+ people) uses Productive to plan resourcing across the whole team without losing sight of which projects are actually profitable.
 
Would something like this make sense for {COMPANY} as well?`
  - variant 2 (253 chars, 41 words): `{FIRST_NAME}, Akcelo (190 people, works with McDonald's and Netflix) uses Productive to stay on top of budgets and reporting across every project. PIABO runs basically the same setup across five offices in Europe. Could it be worth a look for {COMPANY}?`
  - fallback (237 chars): `Random one, but Infinum (software agency, 370+ people) uses Productive to plan resourcing across the whole team without losing sight of which projects are actually profitable.
 
Would something like this make sense for your team as well?`
- message at day 10.00, 4 variant(s):
  - variant 1 (83 chars, 17 words): `{FIRST_NAME}, worth a yes or no on this one so I know whether to stop reaching out?`
  - variant 2 (84 chars, 17 words): `{FIRST_NAME}, should I drop this or send you an overview if you want to take a look?`
  - variant 3 (51 chars, 9 words): `Worth a look, {FIRST_NAME}? I can send an overview.`
  - variant 4 (59 chars, 10 words): `Is this worth pursuing or should I stop here, {FIRST_NAME}?`
  - fallback (69 chars): `Worth a yes or no on this one so I know whether to stop reaching out?`

### 613757 — RESONATE PRODUCTIVE LI B1 SEAT 212356

- ownership: **resonate_os** — `heyreach_campaign_id` present in `work/campaigns.jsonl`
- provider status `PAUSED`; created `2026-09-21T21:27:21.847982Z`; started `2026-09-22T09:11:02.622908Z`
- seats (`campaignAccountIds`): 212356
- lead list `956342` (RESONATE PRODUCTIVE LI B1 SEAT 212356), list size `totalItemsCount` = 4; campaign holds `progressStats.totalUsers` = 4, finished 0
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **4**, accepted **0** (0.00%)
  - messages sent **0**, message threads started **0**, replies **0** (n/a (denominator 0) of threads started)
  - unique leads contacted **4**; profile views 0, follows 4, post likes 0
  - provider's own tags: `autoTaggedInterested` **0**, `totalAutoTagged` **0**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 0 conversations joined, 0 operator-positive replies = **0.000 per 100 requests sent**
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-09-22 .. 2026-09-22 (1 days)
- sequence node types present in the whole graph: CHECK_IS_CONNECTION, CONNECTION_REQUEST, END, FOLLOW, MESSAGE, VIEW_PROFILE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CHECK_IS_CONNECTION   wait 0H      day  0.00
  step 1   MESSAGE               wait 0H      day  0.00
  step 2   MESSAGE               wait 5D      day  5.00
  step 3   MESSAGE               wait 5D      day 10.00
  step 4   END                   wait 3D      day 13.00
```

**Connection note:** 1 `CONNECTION_REQUEST` note slot(s), every one of them EMPTY — this campaign sends connection requests with no note.

**Message steps — our text, in full:**

- message at day 0.00, 3 variant(s):
  - variant 1 (283 chars, 46 words): `Hey {FIRST_NAME},

{Icebreaker}
 
We built Productive so budgets, time tracking and resourcing actually talk to each other, so you can see if a project's making money while it's still running, not just after it gets invoiced.
 
Can show you what that looks like if you're interested.`
  - variant 2 (233 chars, 39 words): `Hi {FIRST_NAME}, {Icebreaker}
 
It's a common one. Productive ties budgets, time and resourcing together so that question has a live answer instead of one you get after the invoice goes out. Can walk you through it if you're curious.`
  - variant 3 (233 chars, 34 words): `Hey {FIRST_NAME},
 
{Icebreaker}
 
That's basically why we built Productive, so budgets, time tracking and resourcing stop living in separate places and you can see project profitability while it's still happening. Happy to show you.`
  - fallback (256 chars): `Hey, we built Productive so budgets, time tracking and resourcing actually talk to each other, so you can see if a project's making money while it's still running, not just after it gets invoiced.
 
Can show you what that looks like if you're interested.

`
- message at day 5.00, 2 variant(s):
  - variant 1 (251 chars, 37 words): `{FIRST_NAME}, random one, but Infinum (software agency, 370+ people) uses Productive to plan resourcing across the whole team without losing sight of which projects are actually profitable.
 
Would something like this make sense for {COMPANY} as well?`
  - variant 2 (253 chars, 41 words): `{FIRST_NAME}, Akcelo (190 people, works with McDonald's and Netflix) uses Productive to stay on top of budgets and reporting across every project. PIABO runs basically the same setup across five offices in Europe. Could it be worth a look for {COMPANY}?`
  - fallback (237 chars): `Random one, but Infinum (software agency, 370+ people) uses Productive to plan resourcing across the whole team without losing sight of which projects are actually profitable.
 
Would something like this make sense for your team as well?`
- message at day 10.00, 4 variant(s):
  - variant 1 (83 chars, 17 words): `{FIRST_NAME}, worth a yes or no on this one so I know whether to stop reaching out?`
  - variant 2 (84 chars, 17 words): `{FIRST_NAME}, should I drop this or send you an overview if you want to take a look?`
  - variant 3 (51 chars, 9 words): `Worth a look, {FIRST_NAME}? I can send an overview.`
  - variant 4 (59 chars, 10 words): `Is this worth pursuing or should I stop here, {FIRST_NAME}?`
  - fallback (69 chars): `Worth a yes or no on this one so I know whether to stop reaching out?`

### 613761 — RESONATE PRODUCTIVE LI B1 SEAT 174845

- ownership: **resonate_os** — `heyreach_campaign_id` present in `work/campaigns.jsonl`
- provider status `PAUSED`; created `2026-09-21T21:28:17.050874Z`; started `2026-09-22T09:11:03.63019Z`
- seats (`campaignAccountIds`): 174845
- lead list `956329` (RESONATE PRODUCTIVE LI B1 SEAT 174845), list size `totalItemsCount` = 4; campaign holds `progressStats.totalUsers` = 4, finished 1
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **4**, accepted **1** (25.00%)
  - messages sent **0**, message threads started **1**, replies **1** (100.00% of threads started)
  - unique leads contacted **4**; profile views 0, follows 4, post likes 0
  - provider's own tags: `autoTaggedInterested` **0**, `totalAutoTagged` **1**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 1 conversations joined, 0 operator-positive replies = **0.000 per 100 requests sent**
- reply classes in this campaign: `negative` 1
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- days on which the provider recorded activity: 2026-09-22 .. 2026-09-23 (2 days)
- sequence node types present in the whole graph: CHECK_IS_CONNECTION, CONNECTION_REQUEST, END, FOLLOW, MESSAGE, VIEW_PROFILE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CHECK_IS_CONNECTION   wait 0H      day  0.00
  step 1   MESSAGE               wait 0H      day  0.00
  step 2   MESSAGE               wait 5D      day  5.00
  step 3   MESSAGE               wait 5D      day 10.00
  step 4   END                   wait 3D      day 13.00
```

**Connection note:** 1 `CONNECTION_REQUEST` note slot(s), every one of them EMPTY — this campaign sends connection requests with no note.

**Message steps — our text, in full:**

- message at day 0.00, 3 variant(s):
  - variant 1 (283 chars, 46 words): `Hey {FIRST_NAME},

{Icebreaker}
 
We built Productive so budgets, time tracking and resourcing actually talk to each other, so you can see if a project's making money while it's still running, not just after it gets invoiced.
 
Can show you what that looks like if you're interested.`
  - variant 2 (233 chars, 39 words): `Hi {FIRST_NAME}, {Icebreaker}
 
It's a common one. Productive ties budgets, time and resourcing together so that question has a live answer instead of one you get after the invoice goes out. Can walk you through it if you're curious.`
  - variant 3 (233 chars, 34 words): `Hey {FIRST_NAME},
 
{Icebreaker}
 
That's basically why we built Productive, so budgets, time tracking and resourcing stop living in separate places and you can see project profitability while it's still happening. Happy to show you.`
  - fallback (256 chars): `Hey, we built Productive so budgets, time tracking and resourcing actually talk to each other, so you can see if a project's making money while it's still running, not just after it gets invoiced.
 
Can show you what that looks like if you're interested.

`
- message at day 5.00, 2 variant(s):
  - variant 1 (251 chars, 37 words): `{FIRST_NAME}, random one, but Infinum (software agency, 370+ people) uses Productive to plan resourcing across the whole team without losing sight of which projects are actually profitable.
 
Would something like this make sense for {COMPANY} as well?`
  - variant 2 (253 chars, 41 words): `{FIRST_NAME}, Akcelo (190 people, works with McDonald's and Netflix) uses Productive to stay on top of budgets and reporting across every project. PIABO runs basically the same setup across five offices in Europe. Could it be worth a look for {COMPANY}?`
  - fallback (237 chars): `Random one, but Infinum (software agency, 370+ people) uses Productive to plan resourcing across the whole team without losing sight of which projects are actually profitable.
 
Would something like this make sense for your team as well?`
- message at day 10.00, 4 variant(s):
  - variant 1 (83 chars, 17 words): `{FIRST_NAME}, worth a yes or no on this one so I know whether to stop reaching out?`
  - variant 2 (84 chars, 17 words): `{FIRST_NAME}, should I drop this or send you an overview if you want to take a look?`
  - variant 3 (51 chars, 9 words): `Worth a look, {FIRST_NAME}? I can send an overview.`
  - variant 4 (59 chars, 10 words): `Is this worth pursuing or should I stop here, {FIRST_NAME}?`
  - fallback (69 chars): `Worth a yes or no on this one so I know whether to stop reaching out?`

### 620829 — RESONATE STOP TEST

- ownership: **resonate_os** — `heyreach_campaign_id` present in `work/campaigns.jsonl`
- provider status `FINISHED`; created `2026-09-24T21:23:35.752001Z`; started `2026-09-24T21:23:52.240283Z`
- seats (`campaignAccountIds`): 174892
- lead list `967214` (zvonimir test), list size `totalItemsCount` = 1; campaign holds `progressStats.totalUsers` = 1, finished 0
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **0**, accepted **0** (n/a (denominator 0))
  - messages sent **0**, message threads started **1**, replies **0** (0.00% of threads started)
  - unique leads contacted **1**; profile views 0, follows 0, post likes 0
  - provider's own tags: `autoTaggedInterested` **0**, `totalAutoTagged` **0**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 1 conversations joined, 1 operator-positive replies = **n/a (0 requests sent) per 100 requests sent**
- reply classes in this campaign: `unknown` 4, `positive` 1
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- sequence node types present in the whole graph: CHECK_IS_CONNECTION, CONNECTION_REQUEST, END, FOLLOW, MESSAGE, VIEW_PROFILE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CHECK_IS_CONNECTION   wait 0H      day  0.00
  step 1   MESSAGE               wait 0H      day  0.00
  step 2   MESSAGE               wait 5D      day  5.00
  step 3   MESSAGE               wait 5D      day 10.00
  step 4   END                   wait 3D      day 13.00
```

**Connection note:** 1 `CONNECTION_REQUEST` note slot(s), every one of them EMPTY — this campaign sends connection requests with no note.

**Message steps — our text, in full:**

- message at day 0.00, 3 variant(s):
  - variant 1 (283 chars, 46 words): `Hey {FIRST_NAME},

{Icebreaker}
 
We built Productive so budgets, time tracking and resourcing actually talk to each other, so you can see if a project's making money while it's still running, not just after it gets invoiced.
 
Can show you what that looks like if you're interested.`
  - variant 2 (233 chars, 39 words): `Hi {FIRST_NAME}, {Icebreaker}
 
It's a common one. Productive ties budgets, time and resourcing together so that question has a live answer instead of one you get after the invoice goes out. Can walk you through it if you're curious.`
  - variant 3 (233 chars, 34 words): `Hey {FIRST_NAME},
 
{Icebreaker}
 
That's basically why we built Productive, so budgets, time tracking and resourcing stop living in separate places and you can see project profitability while it's still happening. Happy to show you.`
  - fallback (256 chars): `Hey, we built Productive so budgets, time tracking and resourcing actually talk to each other, so you can see if a project's making money while it's still running, not just after it gets invoiced.
 
Can show you what that looks like if you're interested.

`
- message at day 5.00, 2 variant(s):
  - variant 1 (251 chars, 37 words): `{FIRST_NAME}, random one, but Infinum (software agency, 370+ people) uses Productive to plan resourcing across the whole team without losing sight of which projects are actually profitable.
 
Would something like this make sense for {COMPANY} as well?`
  - variant 2 (253 chars, 41 words): `{FIRST_NAME}, Akcelo (190 people, works with McDonald's and Netflix) uses Productive to stay on top of budgets and reporting across every project. PIABO runs basically the same setup across five offices in Europe. Could it be worth a look for {COMPANY}?`
  - fallback (237 chars): `Random one, but Infinum (software agency, 370+ people) uses Productive to plan resourcing across the whole team without losing sight of which projects are actually profitable.
 
Would something like this make sense for your team as well?`
- message at day 10.00, 4 variant(s):
  - variant 1 (83 chars, 17 words): `{FIRST_NAME}, worth a yes or no on this one so I know whether to stop reaching out?`
  - variant 2 (84 chars, 17 words): `{FIRST_NAME}, should I drop this or send you an overview if you want to take a look?`
  - variant 3 (51 chars, 9 words): `Worth a look, {FIRST_NAME}? I can send an overview.`
  - variant 4 (59 chars, 10 words): `Is this worth pursuing or should I stop here, {FIRST_NAME}?`
  - fallback (69 chars): `Worth a yes or no on this one so I know whether to stop reaching out?`

### 621824 — RESONATE STOP TEST 2

- ownership: **resonate_os** — `heyreach_campaign_id` present in `work/campaigns.jsonl`
- provider status `FINISHED`; created `2026-09-25T12:11:20.51104Z`; started `2026-09-25T12:11:37.413482Z`
- seats (`campaignAccountIds`): 174892
- lead list `968810` (RESONATE STOP TEST 2 LIST), list size `totalItemsCount` = 1; campaign holds `progressStats.totalUsers` = 2, finished 0
- numbers, window **2026-04-01 .. 2026-10-04**, `/stats/GetOverallStats` with `startDate`/`endDate`:
  - connection requests sent **0**, accepted **0** (n/a (denominator 0))
  - messages sent **0**, message threads started **0**, replies **0** (n/a (denominator 0) of threads started)
  - unique leads contacted **0**; profile views 0, follows 0, post likes 0
  - provider's own tags: `autoTaggedInterested` **0**, `totalAutoTagged` **0**
- our classifier over the joined inbox (rules-4, **UNAUDITED**): 0 conversations joined, 0 operator-positive replies = **n/a (0 requests sent) per 100 requests sent**
- **meetings: NOT RECORDED.** No meeting count exists for this campaign in the provider or in this repository. See "Meetings" above for where it should be recorded.
- sequence node types present in the whole graph: CHECK_IS_CONNECTION, CONNECTION_REQUEST, END, FOLLOW, MESSAGE, VIEW_PROFILE
- the accepted / already-connected branch, in order, with the wait on each step and the cumulative day:

```
  step 0   CHECK_IS_CONNECTION   wait 0H      day  0.00
  step 1   MESSAGE               wait 0H      day  0.00
  step 2   MESSAGE               wait 5D      day  5.00
  step 3   MESSAGE               wait 5D      day 10.00
  step 4   END                   wait 3D      day 13.00
```

**Connection note:** 1 `CONNECTION_REQUEST` note slot(s), every one of them EMPTY — this campaign sends connection requests with no note.

**Message steps — our text, in full:**

- message at day 0.00, 3 variant(s):
  - variant 1 (283 chars, 46 words): `Hey {FIRST_NAME},

{Icebreaker}
 
We built Productive so budgets, time tracking and resourcing actually talk to each other, so you can see if a project's making money while it's still running, not just after it gets invoiced.
 
Can show you what that looks like if you're interested.`
  - variant 2 (233 chars, 39 words): `Hi {FIRST_NAME}, {Icebreaker}
 
It's a common one. Productive ties budgets, time and resourcing together so that question has a live answer instead of one you get after the invoice goes out. Can walk you through it if you're curious.`
  - variant 3 (233 chars, 34 words): `Hey {FIRST_NAME},
 
{Icebreaker}
 
That's basically why we built Productive, so budgets, time tracking and resourcing stop living in separate places and you can see project profitability while it's still happening. Happy to show you.`
  - fallback (256 chars): `Hey, we built Productive so budgets, time tracking and resourcing actually talk to each other, so you can see if a project's making money while it's still running, not just after it gets invoiced.
 
Can show you what that looks like if you're interested.

`
- message at day 5.00, 2 variant(s):
  - variant 1 (251 chars, 37 words): `{FIRST_NAME}, random one, but Infinum (software agency, 370+ people) uses Productive to plan resourcing across the whole team without losing sight of which projects are actually profitable.
 
Would something like this make sense for {COMPANY} as well?`
  - variant 2 (253 chars, 41 words): `{FIRST_NAME}, Akcelo (190 people, works with McDonald's and Netflix) uses Productive to stay on top of budgets and reporting across every project. PIABO runs basically the same setup across five offices in Europe. Could it be worth a look for {COMPANY}?`
  - fallback (237 chars): `Random one, but Infinum (software agency, 370+ people) uses Productive to plan resourcing across the whole team without losing sight of which projects are actually profitable.
 
Would something like this make sense for your team as well?`
- message at day 10.00, 4 variant(s):
  - variant 1 (83 chars, 17 words): `{FIRST_NAME}, worth a yes or no on this one so I know whether to stop reaching out?`
  - variant 2 (84 chars, 17 words): `{FIRST_NAME}, should I drop this or send you an overview if you want to take a look?`
  - variant 3 (51 chars, 9 words): `Worth a look, {FIRST_NAME}? I can send an overview.`
  - variant 4 (59 chars, 10 words): `Is this worth pursuing or should I stop here, {FIRST_NAME}?`
  - fallback (69 chars): `Worth a yes or no on this one so I know whether to stop reaching out?`


---

## 12. Synthesis — what I would take, what I would do better

Every line is a number with its `n`. Where a claim rests on a confound, the
confound is in the line.

### What I would take

1. **Send the first message on day 3 after the request, not day 8.** Top-5
   campaigns message at day 3.00 and reach 0.470 positives per 100 sent
   (74/15,737); 524002 messages at day 8.12 and reaches 0.060 (18/30,207).
2. **Write the first message at 100–299 characters.** 0.550% positives per
   touch on n=22,163 against 0.251% at 300–499 on n=23,495 — 2.2x, the cleanest
   paired comparison in the corpus.
3. **Put the whole bet on step 1 and 2.** 158 of 247 positives (64.0%) arrive
   there; step 6 produces 0.075% per touch on n=2,676, an 8.5x fall from step 1,
   while reply rate falls only 1.7x. Median touches before a positive = 1.
4. **Target founders and owners before ops.** 1.86% of 3,278 founder/owner
   conversations carry a positive against 1.10% of 5,185 ops/delivery — 1.69x —
   and the estate sent 1.58x more at ops.
5. **Space follow-ups 3–5 days, not 5–10.** 0.307% positives per touch on
   n=9,117 against 0.128% on n=19,518, a 2.4x difference; the estate's own
   default sits in the worse bucket.
6. **Keep a note, keep it short, keep it a statement, and do not name the
   company.** With a note 11.60% acceptance on n=23,874 against 10.52% on
   n=92,217. Statement-only 12.67% (n=11,961) against question 10.52%
   (n=11,913). Not naming `{COMPANY}` 13.27% (n=13,902) against naming it 9.27%
   (n=9,972). **Read with §6.4's caveat: strip 467366 and the note effect
   collapses to 10.56% on n=15,886, i.e. nothing.** What survives without
   467366 is only the negative: the 180+ char note underperforms no-note by
   2.2pp on n=6,002.
7. **The release sentence is in the best copy and absent from the worst.** "No
   pressure on that though, good to be connected either way" appears in the step
   1 of ranks 1, 2 and 4 (37,197 requests between them at 0.470 pos/100); the
   rank-14 text ends on "a tool, spreadsheets, or vibes?" at 0.060. Both ~370
   chars. `n` = 3 campaigns against 1, so this is an observation, not a learning.

### What I would do better

1. **Stop spending on the biggest campaign.** 524002 has taken **30,207 of the
   estate's 116,923 requests (25.8%)** and returned **18 of 247 positives
   (7.3%)** at 6.16% acceptance — the lowest of any campaign over 4,000
   requests. On the top-5's rate that spend would have returned ~142.
2. **Stop rotating variants as if more were better.** 524002 declares 11
   step-1 variants holding 4 distinct texts; 429680 rotates 15 notes and sits
   at 0.051 pos/100 on n=5,911. 1-variant campaigns: 13.65% acceptance on
   n=7,991. 5+-variant: 10.52% on n=11,913.
3. **Fix `campaign_stats`.** It sends `timeFrom`/`timeTo`, proven here to be
   discarded, and trims to four of 22 keys — so it cannot answer a windowed
   question and reports an InMail campaign as a campaign that did nothing. Both
   are one-line fixes and both are currently invisible.
4. **Do not trust `isInMail`.** `false` on 57,811 of 57,811 messages. Use
   `subject`, measured against `totalInmailStarted` to 4,648/4,657.
5. **Audit the reply classifier before any positive rate leaves this file.** 36
   of 247 (14.6%) are a connection pleasantry, 14 more are politeness, 83
   (33.6%) are six words or fewer, and HeyReach's own tagger says "not
   interested" on 49 (19.8%). A plausible floor is 197, i.e. 0.168 per 100 sent
   rather than 0.211. `meeting_intent` fired 0 times in 3,164 real replies,
   which means the class that matters most is not implemented in practice.
6. **Write the meeting event.** `events.MEETING_MARKED` exists,
   `outcomes._meeting` reads it, and `work/queue.jsonl` holds 0 of them in 1,584
   records. Until a caller appends it, the estate's most valuable channel cannot
   be ranked on the metric the operator says is the metric, and this file's
   ordering is a proxy for it.
7. **Close the attribution hole, or stop quoting inbox-level reply counts.**
   284 of 513 operator-positive replies (55.4%) and 9,638 of 22,045 leads
   (43.7%) join to no campaign on this seat. `correspondentProfile.autoTags`
   carries a `campaignId` and is the unused second join; that is the cheapest
   place to start.
9. **Know what our own sequences actually send.** `599020`, `604869`, `605487`
   and `605732` carry a merge variable at **every** step — `{connection_note}`,
   `{connected_1}` … `{connected_4}` — and a fallback behind each. The
   variables are 13 to 17 characters of variable name; the fallbacks are real
   words at **83, 94, 99 and 115 characters**. So the only copy guaranteed to
   reach a prospect from our own campaigns is the fallback set, and nothing in
   this estate has ever sent enough from them to measure it: 172 requests, 2
   positives. Those fallback lengths sit inside the 100–299 band that measures
   best (§6.2), which is the one encouraging thing this paragraph contains.

8. **Give our own campaigns something to measure.** The 40 Resonate OS
   campaigns have sent **172 requests in total** and hold **2 of 247**
   positives. Every learning on this page is read out of campaigns whose owner
   is `unknown`. That is a read-only learning asset by the standing rule, and it
   is also the only evidence this channel has.

### One defect in live copy, found by reading the sequences

**Campaign 524013** (`FIXED - PRODUCTIVE - MARKETING AGENCIES - USA 2ND -
CLEANED - ZVONIMIR`, `IN_PROGRESS`, 446 requests, 30 accepted, 101 messages
sent, 4 replies, **0** positives) carries a message variant whose sentence is
broken mid-edit. It is in the provider payload, so it is what a prospect
receives:

```
I work with marketing agencies on the gap between time logged and money made. The people I with know something is leaking but cannot pinpoint where until it is too late to fix it.
```

The intact version of that sentence, in campaigns 388939/388953/388958, reads
"Most `{POSITION}`s I speak with know something is leaking". The merge variable
was deleted and the verb with it. Nothing in this repository reads a HeyReach
message variant for grammar; `sequence_hazards` and `linkedin_only` read node
types, `connection_notes` reads the note, and `validate_sequence_for_write`
only guards a graph going the other way.

---

### The honest boundary

This is 121 campaigns' observational history, not an experiment. List, geo,
seat, period and copy move together in every comparison above except §6.1,
§6.2 and §6.3, which are computed per touch over 54,647 touches and are the
three I would act on first. The note comparison in §6.4 is dominated by one
campaign and says less than its table suggests. The positive rate is unaudited
and §8.1 says by how much.

---

## 13. PII scan, with its control

Run on this file as committed, by `work/task981/pii_scan.py`, which is
gitignored. **The forbidden-token list is built there from the live payloads
and is deliberately not reproduced here, and neither is the list of words the
scan flagged.** That is not tidiness: the first version of this section printed
the flagged words inside a fenced block, and the next run picked them up out of
its own report — the scan's restricted pass went from 2 hits to 33, 31 of them
its own output. A check that names what it forbids inside the file it protects
has happened three times in this repository and this is the fourth.

| | |
|---|---|
| scan list | 13,969 person-name tokens + 9,466 company names + 12,407 profile slugs = **35,842 forbidden tokens**, built from the 17,732 live conversations this walk joined to a campaign |
| allowlist | 1,057 words taken from OUR OWN sequence templates and OUR OWN campaign and list names, plus 23 of our own entity names (the product, the agency, the proof-point companies, the seat owners) |
| method | the document is tokenised once into unigrams and 2-to-6-grams and the token list is intersected against them; multi-word company names must match as a phrase |
| **positive control** | a real first name, a real surname, a real multi-word company name and a real profile slug were appended to a **copy** of the document before any verdict was printed. **4 of 4 were reported. CONTROL PASS.** The scanner does not issue a verdict at all if the control fails. |
| pass 1 — whole document | **38 hits at the time of writing: 23 person-name, 15 company, 0 profile slug.** Every one was inspected and every one is an ordinary English word or two-word phrase that is also somebody's name or company somewhere in a 23,435-token list drawn from 17,732 real conversations, and every one occurs in prose this session wrote from aggregates rather than in quoted material. **The count moves by a word or two every time this paragraph is edited**, because the paragraph is inside the document it describes — which is the self-reference the first draft fell into, and the reason the flagged words are not listed. |
| pass 2 — provider-derived regions only | the fenced blocks holding our template copy, the campaign heading lines and the lead-list lines — 10.3% of the file, 89,855 bytes. **2 hits, and 0 person names and 0 profile slugs.** Both hits are company names that collide with English: one with a column label this file's own cadence tables print on every step line, and one with a two-word phrase inside the broken message variant of campaign 524013 quoted in §12 — our own copy, matching a company nobody wrote about. |

**Why two passes.** At 23,435 name-and-company tokens a collision with ordinary
English is certain, so "0 hits over the whole document" is not an achievable
target and chasing it would mean weakening the list. Pass 2 restricts the scan
to the only regions that could carry a recipient — the material that came out
of a provider payload — and that is where the answer is zero names and zero
slugs.

The seat owners' own first names do appear in this file, inside our own campaign
and list names (`PRODUCTIVE - … CONNECTIONS - MARKETING AGENCIES - …`). They
are on the allowlist because they are ours, and they are on it by being read out
of the 121 campaign names rather than typed here. They are not recipients.

**What the scan cannot see, stated rather than glossed.** The token list is
built from the 17,732 conversations this walk joined to a campaign. It holds no
names from the 12,156 conversations that join to nothing, because this walk
fetched only hashes, seat ids and classifications for those. No text from them
reaches this file, so there is nothing for the scan to miss there — but the
list is not the whole inbox, and that is the boundary of the check.

**And the finding that changed this document.** The first draft of §8.2 printed
each positive reply with the correspondent's own `firstName`, `lastName`,
`companyName`, `location` and `position` substituted out — exact substitution
from the profile payload, not a guess at what a name looks like. The scan found
**86 hits** in that draft and three were real: a recipient signing a reply with
a name that is not on their profile, a reply naming a colleague who is not the
recipient, and a reply naming a company that is not the correspondent's
`companyName`. **An exact substitution of the fields we hold does not anonymise
a free-text reply**, and the scan is what established that rather than an
argument. The replies therefore live in `work/`, and §8.2 carries everything
about them except the recipient's own prose.
