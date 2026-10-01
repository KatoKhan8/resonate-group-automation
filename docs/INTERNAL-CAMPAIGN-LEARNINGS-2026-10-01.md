# What the four internal Productive campaigns actually taught us

EmailBison campaigns **274, 327, 328, 352**. Read-only measurement, 2026-10-01. Freeze ON, `sending.live=false`. No provider write of any kind was issued; every call in this document is a GET.

These four are **internal Resonate campaigns run manually for Productive**. They are not the client's and they are not Resonate OS. Confirmed locally: `work/campaigns.jsonl` carries `bison_campaign_id` for 451, 481, 484, 485, 487, 489, 491-498, 500, 501, 503-506 and for **none** of 274, 327, 328, 352. Everybody in them is already contacted, so **none of these leads is clean for the canary**. What follows is the learning asset.

Reply classification throughout is `src/replies.classify`, rule identity `rules-4+63ac5f605770`. Where it is wrong, that is reported as a finding rather than smoothed over.

## 1. Denominators first - what was readable and what was not

The reply feed is `GET /api/replies`, cursor-paginated, filtered with `campaign_id`. The instance ignores `per_page` and serves 15 rows a page. Four folder values are accepted (`inbox`, `bounced`, `sent`, `spam`) and they sum exactly to `all`, so the folder set is exhaustive and the walk below is complete for what the provider stores.

| campaign | feed total declared | rows read | pages | walk exhausted | inbox (reply) | bounced | sent (our own mail) |
|---|---|---|---|---|---|---|---|
| 274 | 273 | 273 | 19 | yes | 73 | 180 | 20 |
| 327 | 638 | 638 | 43 | yes | 160 | 430 | 48 |
| 328 | 712 | 712 | 48 | yes | 216 | 432 | 64 |
| 352 | 1564 | 1564 | 105 | yes | 450 | 840 | 274 |

`sent` rows are **our own outbound mail** carried in the same feed (`type: Outgoing Email`, `folder: Sent`). They are dropped by `bison.classify_reply_row` and are never counted as replies. Ingesting them would pause every company the moment we contacted it.

### The gap I could not close

The campaign row's own `replied` counter and the number of readable inbox rows agree on the archived campaign and disagree on all three live ones:

| campaign | status | `replied` (campaign row) | `unique_replies` | inbox rows readable | reply events with no readable row |
|---|---|---|---|---|---|
| 274 | archived | 73 | 72 | 73 | 0 |
| 327 | active | 532 | 518 | 160 | 372 |
| 328 | active | 762 | 742 | 216 | 546 |
| 352 | active | 558 | 495 | 450 | 108 |

Authority for both columns: `GET /api/campaigns/{id}` and `GET /api/campaigns/{id}/replies?folder=inbox` (`meta.total`), read 2026-10-01. **I could not establish why they differ.** The totals are identical on `GET /api/campaigns/{id}/replies` and on `GET /api/replies?campaign_id={id}`, so this is not a lossy filter and not a truncated walk - the rows are not there to read. A plausible reading is that the counter is append-only while the inbox has been cleaned by hand, which would fit campaigns the team works manually, but **nothing I read proves it** and it is recorded here as UNKNOWN, not as an explanation.

So every reply-content finding below rests on 899 readable inbox rows out of 1925 reply events the provider claims.

### The HeyReach trap, addressed

Campaign **352 is named `HeyReach Connection Campaign` and is an EmailBison email campaign**, not a HeyReach LinkedIn campaign. No HeyReach inbox was read for this work and no reply was called ours because it was in an inbox: every row came from EmailBison's own per-campaign reply route, and each row's `campaign_id` was re-checked against the requested id on ingest (0 mismatches across all four walks). The ~27k-conversation HeyReach inbox is untouched by this measurement.

### created_at, addressed

Campaigns were addressed by numeric provider id throughout. `created_at` is populated on all four rows here, and was used only to date the campaigns, never to order them.

## 2. Per-campaign reply rates

| campaign | status | leads | leads contacted | emails sent | `replied` | reply/send | reply/contacted | readable inbox rows | readable/send | bounced | bounce rate | `interested` flag |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 274 | archived | 9734 | 4994 | 28331 | 73 | 0.26% | 1.46% | 73 | 0.26% | 180 | 0.64% | 0 |
| 327 | active | 9676 | 8013 | 47768 | 532 | 1.11% | 6.64% | 160 | 0.33% | 430 | 0.90% | 4 |
| 328 | active | 10285 | 7772 | 38533 | 762 | 1.98% | 9.80% | 216 | 0.56% | 432 | 1.12% | 3 |
| 352 | active | 21676 | 20829 | 94287 | 558 | 0.59% | 2.68% | 450 | 0.48% | 839 | 0.89% | 19 |

Authority: `GET /api/campaigns/{id}` for every column but `readable inbox rows`, which is the walk above. `unsubscribed` is **0 on all four** - these campaigns carry `can_unsubscribe: false` and no unsubscribe link, so every opt-out arrives as a reply somebody has to read. `opened`/`unique_opens` are 0 on all four because `open_tracking: false`; open rate is **not measurable** here and no inference from it is offered.

### The send census, from the queue rather than the counter

`GET /api/campaigns/{id}/scheduled-emails` accepts a `status` filter, and the five accepted values sum to the queue total, so this census is exhaustive. It is a second, independent reading of "how many messages went out" and it does **not** agree with the campaign row's `emails_sent`:

| campaign | membership route total | `total_leads` on campaign row | queue rows | queue `sent` | `emails_sent` on campaign row | counter minus queue | queue `stopped` | queue `bounced` | queue `scheduled` |
|---|---|---|---|---|---|---|---|---|---|
| 274 | 10049 | 9734 | 30411 | 27205 | 28331 | 1126 | 3077 | 129 | 0 |
| 327 | 10008 | 9676 | 49739 | 46683 | 47768 | 1085 | 2310 | 340 | 406 |
| 328 | 10915 | 10285 | 42868 | 37710 | 38533 | 823 | 2848 | 361 | 1948 |
| 352 | 21676 | 21676 | 97115 | 93025 | 94287 | 1262 | 2991 | 691 | 406 |

Three things in that table matter.

1. **The membership route and the campaign counter disagree on how many leads each campaign holds** (274: 10,049 vs 9,734). Neither is obviously right and I did not establish which.
2. **The queue `sent` count is consistently ~1,000 below the campaign's `emails_sent`.** Same unexplained direction as the reply gap in section 1.
3. **327, 328 and 352 still hold `scheduled` rows** - 406, 1,948 and 406 respectively, read 2026-10-01. These campaigns are not finished; they will send again. 274 holds 0 and is archived. That is a fact an operator should see beside the word "manual".

## 3. What the sequences actually say, mapped to this repo's taxonomies

The angle names are `src/copyprompts.ANGLES`; the pain names are `src/strategy` constants. The mapping was made by **reading each canonical step's stored body** via `GET /api/campaigns/{id}/sequence-steps`, and it is printed in full so it can be checked rather than trusted. `signoff` and `permission_check` are not product angles and are named as such instead of being forced into the closed list.

| campaign | step | angle (copyprompts.ANGLES) | pain (strategy) |
|---|---|---|---|
| 274 | 1 | `tools_fragmented` | `tool_sprawl` |
| 274 | 2 | `tools_fragmented` | `tool_sprawl` |
| 274 | 3 | `margin_visible_late` | `project_margin` |
| 274 | 4 | `margin_visible_late` | `budget_control` |
| 274 | 5 | `utilisation_unknown` | `utilization` |
| 274 | 6 | `tools_fragmented` | `tool_sprawl` |
| 274 | 7 | `margin_visible_late` | `profitability_reporting` |
| 274 | 8 | `signoff` | `-` |
| 327 | 1 | `tools_fragmented` | `tool_sprawl` |
| 327 | 2 | `tools_fragmented` | `tool_sprawl` |
| 327 | 3 | `margin_visible_late` | `project_margin` |
| 327 | 4 | `utilisation_unknown` | `resource_planning` |
| 327 | 5 | `utilisation_unknown` | `utilization` |
| 327 | 6 | `manual_reporting` | `tool_sprawl` |
| 327 | 7 | `permission_check` | `-` |
| 327 | 8 | `signoff` | `-` |
| 328 | 1 | `tools_fragmented` | `tool_sprawl` |
| 328 | 2 | `tools_fragmented` | `tool_sprawl` |
| 328 | 3 | `margin_visible_late` | `project_margin` |
| 328 | 4 | `utilisation_unknown` | `resource_planning` |
| 328 | 5 | `utilisation_unknown` | `utilization` |
| 328 | 6 | `manual_reporting` | `tool_sprawl` |
| 328 | 7 | `permission_check` | `-` |
| 328 | 8 | `signoff` | `-` |
| 352 | 1 | `tools_fragmented` | `tool_sprawl` |
| 352 | 2 | `tools_fragmented` | `tool_sprawl` |
| 352 | 3 | `margin_visible_late` | `profitability_reporting` |
| 352 | 4 | `margin_visible_late` | `profitability_reporting` |
| 352 | 5 | `signoff` | `-` |

Structural notes read from the step rows:

- 274 holds **35 step rows / 8 canonical steps** (27 A/B variants), 327 and 328 hold **8 steps and no variants at all**, 352 holds **44 step rows / 5 canonical steps** (39 variants).
- 327 and 328 hold the same copy; they are a **USA / EU geography split of one sequence**, which is the one clean geography comparison in this set.
- Every step in 327/328 branches on `{TITLE}` with Liquid (`title contains "founder"` / `"coo"` / `"financ"`), so persona targeting here is **done inside one message**, not by separate persona campaigns. 352 does not branch on title at all.
- 352 is the multichannel follow-on: step 1 opens with `following up from LinkedIn`, and it is the only sequence that merges `{INDUSTRY}` into the copy.

## 4. Replies by class

| class (src/replies) | 274 | 327 | 328 | 352 |
|---|---|---|---|---|
| `account_do_not_contact` | 0 | 0 | 0 | 2 |
| `assistant_redirect` | 0 | 1 | 1 | 1 |
| `automated` | 0 | 0 | 1 | 2 |
| `meeting_intent` | 0 | 0 | 0 | 2 |
| `negative` | 21 | 27 | 32 | 125 |
| `not_now` | 1 | 2 | 0 | 2 |
| `not_relevant` | 2 | 3 | 9 | 16 |
| `objection` | 0 | 1 | 1 | 5 |
| `out_of_office` | 0 | 35 | 74 | 19 |
| `positive` | 1 | 2 | 0 | 18 |
| `question` | 0 | 0 | 0 | 6 |
| `referral` | 0 | 2 | 6 | 9 |
| `send_info` | 1 | 0 | 0 | 0 |
| `unknown` | 24 | 50 | 71 | 179 |
| `unsubscribe` | 23 | 37 | 21 | 64 |
| **total classified** | 73 | 160 | 216 | 450 |


### The operator's own positive marking, beside the classifier's

EmailBison carries an `interested` flag a human sets in its UI. It is better authority for POSITIVE than any classifier verdict here, and the two do not agree:

| campaign | `interested` on campaign row | inbox rows flagged `interested` | classifier `positive` | classifier `interested`/`meeting_intent` | classifier `question`/`send_info` |
|---|---|---|---|---|---|
| 274 | 0 | 0 | 1 | 0 | 1 |
| 327 | 4 | 4 | 2 | 0 | 0 |
| 328 | 3 | 3 | 0 | 0 | 0 |
| 352 | 19 | 16 | 18 | 2 | 6 |

Where the campaign counter exceeds the flagged rows that are readable, the difference is the same unreadable-row gap as section 1. **The honest statement about positives in this corpus is that there are very few of them, and that the ones the classifier names are not reliable** - see section 12.

## 5. Per step: replies, and the positive/negative split

The step is established per reply by `GET /api/scheduled-emails/{id}` on the row's `scheduled_email_id`, which returns `sequence_step_id`; variants are folded onto their parent step through `variant_from_step`. `step = null` means the reply's scheduled email could not be resolved.

**The per-step SEND denominator is not available on this API and is not estimated.** `GET /api/campaigns/{id}/scheduled-emails` accepts `status` but silently ignores `sequence_step_id`, `step_id` and `sequence_step` (all three return the unfiltered total, measured), there is no per-step statistics route (`/sequence-steps/{id}`, `/campaigns/{id}/sequence-steps-stats`, `/campaigns/{id}/statistics`, `/campaigns/{id}/analytics` are all 404), and the queue is 15 rows a page against 97,115 rows on 352 alone. So the columns below are reply COUNTS and shares, never per-step reply rates.

**Campaign 274**

| step | angle | replies | share of replies | positive | negative | other | bounces |
|---|---|---|---|---|---|---|---|
| 1 | `tools_fragmented` | 26 | 35.62% | 1 | 12 | 13 | 98 |
| 2 | `tools_fragmented` | 18 | 24.66% | 0 | 15 | 3 | 7 |
| 3 | `margin_visible_late` | 5 | 6.85% | 0 | 4 | 1 | 23 |
| 4 | `margin_visible_late` | 10 | 13.70% | 0 | 7 | 3 | 4 |
| 5 | `utilisation_unknown` | 2 | 2.74% | 0 | 1 | 1 | 11 |
| 6 | `tools_fragmented` | 1 | 1.37% | 0 | 0 | 1 | 4 |
| 7 | `margin_visible_late` | 3 | 4.11% | 0 | 1 | 2 | 5 |
| 8 | `signoff` | 5 | 6.85% | 0 | 4 | 1 | 5 |
| None | `-` | 3 | 4.11% | 0 | 2 | 1 | 23 |

**Campaign 327**

| step | angle | replies | share of replies | positive | negative | other | bounces |
|---|---|---|---|---|---|---|---|
| 1 | `tools_fragmented` | 30 | 18.75% | 0 | 19 | 11 | 274 |
| 2 | `tools_fragmented` | 24 | 15.00% | 1 | 14 | 9 | 44 |
| 3 | `margin_visible_late` | 17 | 10.62% | 0 | 4 | 13 | 27 |
| 4 | `utilisation_unknown` | 23 | 14.38% | 0 | 8 | 15 | 22 |
| 5 | `utilisation_unknown` | 14 | 8.75% | 1 | 2 | 11 | 12 |
| 6 | `manual_reporting` | 12 | 7.50% | 0 | 5 | 7 | 20 |
| 7 | `permission_check` | 30 | 18.75% | 0 | 11 | 19 | 12 |
| 8 | `signoff` | 6 | 3.75% | 0 | 3 | 3 | 14 |
| None | `-` | 4 | 2.50% | 0 | 2 | 2 | 5 |

**Campaign 328**

| step | angle | replies | share of replies | positive | negative | other | bounces |
|---|---|---|---|---|---|---|---|
| 1 | `tools_fragmented` | 47 | 21.76% | 0 | 11 | 36 | 268 |
| 2 | `tools_fragmented` | 44 | 20.37% | 0 | 20 | 24 | 41 |
| 3 | `margin_visible_late` | 18 | 8.33% | 0 | 8 | 10 | 46 |
| 4 | `utilisation_unknown` | 46 | 21.30% | 0 | 11 | 35 | 22 |
| 5 | `utilisation_unknown` | 9 | 4.17% | 0 | 1 | 8 | 9 |
| 6 | `manual_reporting` | 6 | 2.78% | 0 | 2 | 4 | 14 |
| 7 | `permission_check` | 25 | 11.57% | 0 | 8 | 17 | 14 |
| 8 | `signoff` | 20 | 9.26% | 0 | 2 | 18 | 7 |
| None | `-` | 1 | 0.46% | 0 | 0 | 1 | 11 |

**Campaign 352**

| step | angle | replies | share of replies | positive | negative | other | bounces |
|---|---|---|---|---|---|---|---|
| 1 | `tools_fragmented` | 184 | 40.89% | 11 | 80 | 93 | 590 |
| 2 | `tools_fragmented` | 121 | 26.89% | 6 | 64 | 51 | 92 |
| 3 | `margin_visible_late` | 61 | 13.56% | 1 | 27 | 33 | 68 |
| 4 | `margin_visible_late` | 52 | 11.56% | 2 | 28 | 22 | 34 |
| 5 | `signoff` | 29 | 6.44% | 0 | 11 | 18 | 41 |
| None | `-` | 3 | 0.67% | 0 | 2 | 1 | 15 |


### Subject lines, as stored templates

The **template** is printed, never the rendered subject: a rendered one carries `{COMPANY}` and `{FIRST_NAME}` resolved to a real company and a real person, which is exactly the data this document must not hold. Spintax braces are the provider's own.

| campaign | step | stored subject template | replies | positive | negative |
|---|---|---|---|---|---|
| 274 | 1 | `{how many tools is\|what's running\|what holds together} {COMPANY}'s operations?` | 26 | 1 | 12 |
| 274 | 2 | `Re: {how many tools is\|what's running\|what holds together} {COMPANY}'s operations?` | 18 | 0 | 15 |
| 274 | 3 | `the project {COMPANY} thought was fine` | 5 | 0 | 4 |
| 274 | 4 | `Re: the project {COMPANY} thought was fine` | 10 | 0 | 7 |
| 274 | 5 | `{FIRST_NAME}, what's {COMPANY}'s utilization rate right now?` | 2 | 0 | 1 |
| 274 | 6 | `what does {COMPANY}'s current stack look like?` | 1 | 0 | 0 |
| 274 | 7 | `what staying put is costing {COMPANY}` | 3 | 0 | 1 |
| 274 | 8 | `{closing the loop\|last one from me}, {FIRST_NAME}` | 5 | 0 | 4 |
| 327 | 1 | `{how {COMPANY} tracks margin today\|the ops stack at {COMPANY}\|project profitability at {…` | 30 | 0 | 19 |
| 327 | 2 | `Re: {how {COMPANY} tracks margin today\|the ops stack at {COMPANY}\|project profitability …` | 24 | 1 | 14 |
| 327 | 3 | `{the 8% margin problem\|when you find out too late\|every agency hits this at some point}` | 17 | 0 | 4 |
| 327 | 4 | `{where the margin actually gets lost\|it starts at allocation, not invoicing\|resourcing a…` | 23 | 0 | 8 |
| 327 | 5 | `{what agencies like {COMPANY} actually find when they look\|the number most agencies don'…` | 14 | 1 | 2 |
| 327 | 6 | `{the cost of the current setup\|what the spreadsheet workaround is actually costing {COMP…` | 12 | 0 | 5 |
| 327 | 7 | `{wrong person at {COMPANY}?\|quick question before I stop reaching out\|should I be talkin…` | 30 | 0 | 11 |
| 327 | 8 | `{closing the loop on {COMPANY}\|last note from me\|leaving the door open}` | 6 | 0 | 3 |
| 328 | 1 | `{how {COMPANY} tracks margin today\|the ops stack at {COMPANY}\|project profitability at {…` | 47 | 0 | 11 |
| 328 | 2 | `Re: {how {COMPANY} tracks margin today\|the ops stack at {COMPANY}\|project profitability …` | 44 | 0 | 20 |
| 328 | 3 | `{the 8% margin problem\|when you find out too late\|every agency hits this at some point}` | 18 | 0 | 8 |
| 328 | 4 | `{where the margin actually gets lost\|it starts at allocation, not invoicing\|resourcing a…` | 46 | 0 | 11 |
| 328 | 5 | `{what agencies like {COMPANY} actually find when they look\|the number most agencies don'…` | 9 | 0 | 1 |
| 328 | 6 | `{the cost of the current setup\|what the spreadsheet workaround is actually costing {COMP…` | 6 | 0 | 2 |
| 328 | 7 | `{wrong person at {COMPANY}?\|quick question before I stop reaching out\|should I be talkin…` | 25 | 0 | 8 |
| 328 | 8 | `{closing the loop on {COMPANY}\|last note from me\|leaving the door open}` | 20 | 0 | 2 |
| 352 | 1 | `{me again, {FIRST_NAME}\|following up from LinkedIn\|trying email this time}` | 184 | 11 | 80 |
| 352 | 2 | `Re: {me again, {FIRST_NAME}\|following up from LinkedIn\|trying email this time}` | 121 | 6 | 64 |
| 352 | 3 | `what we see with {INDUSTRY} agencies` | 61 | 1 | 27 |
| 352 | 4 | `Re: what we see with {INDUSTRY} agencies` | 52 | 2 | 28 |
| 352 | 5 | `{last one from me\|closing the file on {COMPANY}\|signing off, {FIRST_NAME}}` | 29 | 0 | 11 |


## 6. When replies arrive

Day offset is `date_received` on the reply minus `sent_at` on the scheduled email it answers - both provider fields, no local clock involved. Hour is the UTC hour of `date_received`.

| days after send | replies | share | cumulative |
|---|---|---|---|
| 0 | 748 | 84.23% | 84.23% |
| 1 | 27 | 3.04% | 87.27% |
| 2 | 22 | 2.48% | 89.75% |
| 3 | 20 | 2.25% | 92.00% |
| 4 | 11 | 1.24% | 93.24% |
| 5 | 8 | 0.90% | 94.14% |
| 6 | 11 | 1.24% | 95.38% |
| 7 | 7 | 0.79% | 96.17% |
| 8 | 1 | 0.11% | 96.28% |
| 9 | 4 | 0.45% | 96.73% |
| 10 | 5 | 0.56% | 97.30% |
| 11 | 4 | 0.45% | 97.75% |
| 12 | 1 | 0.11% | 97.86% |
| 13 | 1 | 0.11% | 97.97% |
| 14 | 1 | 0.11% | 98.09% |
| 15 | 1 | 0.11% | 98.20% |
| 18 | 1 | 0.11% | 98.31% |
| 19 | 2 | 0.23% | 98.54% |
| 20 | 4 | 0.45% | 98.99% |
| 23 | 2 | 0.23% | 99.21% |
| 27 | 1 | 0.11% | 99.32% |
| 28 | 1 | 0.11% | 99.44% |
| 39 | 1 | 0.11% | 99.55% |
| 54 | 1 | 0.11% | 99.66% |
| 55 | 1 | 0.11% | 99.77% |
| 60 | 1 | 0.11% | 99.89% |
| 62 | 1 | 0.11% | 100.00% |

| hour (UTC) | replies | share |
|---|---|---|
| 0 | 7 | 0.79% |
| 1 | 3 | 0.34% |
| 2 | 11 | 1.24% |
| 3 | 2 | 0.23% |
| 4 | 3 | 0.34% |
| 5 | 7 | 0.79% |
| 6 | 24 | 2.70% |
| 7 | 46 | 5.18% |
| 8 | 49 | 5.52% |
| 9 | 47 | 5.29% |
| 10 | 41 | 4.62% |
| 11 | 48 | 5.41% |
| 12 | 67 | 7.55% |
| 13 | 82 | 9.23% |
| 14 | 90 | 10.14% |
| 15 | 51 | 5.74% |
| 16 | 56 | 6.31% |
| 17 | 44 | 4.95% |
| 18 | 53 | 5.97% |
| 19 | 37 | 4.17% |
| 20 | 54 | 6.08% |
| 21 | 29 | 3.27% |
| 22 | 20 | 2.25% |
| 23 | 17 | 1.91% |


## 7. Who replied - persona and routing family

Persona is `personas.classify` against `config/clients/productive.yaml`; the routing family is `personas.family_of` under the `operations_led` strategy. Titles come from the provider's own lead row. `not_a_persona` / `unmatched` means the title matches nothing this client configured - it is a measurement of our own persona list, not of the person.

| routing family | replies | positive | negative | other | negative share |
|---|---|---|---|---|---|
| `founder` | 353 | 6 | 155 | 192 | 43.91% |
| `delivery` | 261 | 10 | 85 | 166 | 32.57% |
| `operations` | 181 | 3 | 91 | 87 | 50.28% |
| `unmatched` | 104 | 4 | 58 | 42 | 55.77% |

| persona | replies | positive | negative | other | negative share |
|---|---|---|---|---|---|
| `economic_buyer` | 484 | 8 | 229 | 247 | 47.31% |
| `champion` | 356 | 12 | 133 | 211 | 37.36% |
| `not_a_persona` | 59 | 3 | 27 | 29 | 45.76% |


## 8. Geography

Two different things are reported and they must not be conflated.

**Campaign-level geography** is the one real split: 274 and 327 are named `USA`, 328 is named `eu`, and 327/328 carry identical copy. That is the clean comparison:

| campaign | geography (campaign name) | emails sent | `replied` | reply/send | bounce rate | readable inbox rows | out_of_office | unsubscribe | negative-family |
|---|---|---|---|---|---|---|---|---|---|
| 327 | USA | 47768 | 532 | 1.11% | 0.90% | 160 | 35 | 37 | 68 |
| 328 | EU | 38533 | 762 | 1.98% | 1.12% | 216 | 74 | 21 | 63 |

**Replier geography, from the provider's own lead record.** Every lead carries a `location` custom variable (`GET /api/leads/{id}` -> `custom_variables`), and it is a real place string, not a proxy. It is folded onto the geo names this repo already uses (`personas.GEO_CODES`); a location matching none of them stays `other` rather than being guessed into a region.

| geo (personas.GEO_CODES) | replies | positive | negative | other | negative share |
|---|---|---|---|---|---|
| `united states` | 310 | 7 | 159 | 144 | 51.29% |
| `absent` | 187 | 7 | 68 | 112 | 36.36% |
| `united kingdom` | 108 | 1 | 45 | 62 | 41.67% |
| `other` | 70 | 2 | 35 | 33 | 50.00% |
| `poland` | 29 | 1 | 9 | 19 | 31.03% |
| `germany` | 28 | 0 | 4 | 24 | 14.29% |
| `canada` | 27 | 4 | 6 | 17 | 22.22% |
| `switzerland` | 19 | 0 | 7 | 12 | 36.84% |
| `sweden` | 19 | 0 | 13 | 6 | 68.42% |
| `netherlands` | 16 | 0 | 11 | 5 | 68.75% |
| `austria` | 16 | 0 | 5 | 11 | 31.25% |
| `denmark` | 12 | 0 | 3 | 9 | 25.00% |
| `not_fetched` | 11 | 0 | 6 | 5 | 54.55% |
| `norway` | 10 | 0 | 2 | 8 | 20.00% |
| `belgium` | 10 | 0 | 4 | 6 | 40.00% |
| `ireland` | 9 | 1 | 2 | 6 | 22.22% |
| `france` | 9 | 0 | 5 | 4 | 55.56% |
| `finland` | 8 | 0 | 4 | 4 | 50.00% |
| `australia` | 1 | 0 | 1 | 0 | 100.00% |


**ccTLD of the replier's address** is reported below as a *weaker* signal. It is the literal top-level domain of the address that replied, nothing more: a `.com` says nothing about where the company is, so this table may be used to spot ccTLD concentration and must not be read as a location measurement.

| ccTLD | replies | positive | negative | other |
|---|---|---|---|---|
| .com | 566 | 15 | 267 | 284 |
| .uk | 31 | 0 | 14 | 17 |
| .de | 27 | 0 | 4 | 23 |
| .co | 21 | 1 | 15 | 5 |
| .cz | 21 | 2 | 7 | 12 |
| .pl | 20 | 0 | 4 | 16 |
| .io | 16 | 0 | 3 | 13 |
| .net | 14 | 0 | 6 | 8 |
| .ch | 14 | 0 | 2 | 12 |
| .nl | 13 | 0 | 8 | 5 |
| .se | 11 | 0 | 5 | 6 |
| .media | 10 | 1 | 2 | 7 |
| .fi | 10 | 0 | 6 | 4 |
| .be | 9 | 0 | 2 | 7 |
| .ca | 8 | 1 | 4 | 3 |
| .agency | 7 | 0 | 3 | 4 |
| .lt | 7 | 0 | 3 | 4 |
| .ie | 6 | 1 | 1 | 4 |


## 9. Vertical - not measurable, and the reason is a bug

**No vertical can be attached to any reply in this set, and that is a finding rather than a limitation.**

For 274, 327 and 328 the vertical is simply not recorded: the lead rows carry `first_name`, `last_name`, `email`, `title`, `company`, `status` and `custom_variables` holding only `headline` and `location`. The campaign names say `MARKETING AGENCY` and nothing finer. Segmenting these replies by `src/segments` vertical would need the companies re-segmented locally.

Campaign 352 **does** merge `{INDUSTRY}` into its copy - and on every rendered email that uses it, the field resolved to **nothing**. Counted on the 1,092 rendered 352 queue rows read through `GET /api/scheduled-emails/{id}`:

| template | rendered with an industry | rendered EMPTY |
|---|---|---|
| subject `what we see with {INDUSTRY} agencies` | 0 | 88 |
| body `most {INDUSTRY} agencies we talk to` | 0 | 183 |
| body `a bunch of {INDUSTRY} agencies` | 0 | 37 |
| body `how other {INDUSTRY} agencies are managing` | 0 | 14 |

So **88 subject lines went out reading `what we see with agencies`**, and not one rendered email in this campaign carried a real industry. The lead rows explain it: EmailBison substitutes a lead's custom variables, the leads here carry only `headline` and `location`, and there is no `industry` variable for it to find. The provider substitutes empty and sends.

**`src/emptyrender` does not catch this, and it is the module whose job it is.** Its four shapes are `EMPTY`, `LITERAL_NONE`, `PLACEHOLDER` and `SUBJECT_RE_ONLY`; a subject reading `what we see with agencies` is none of them - it is a full sentence with a hole in the middle. Run against the real string, `emptyrender.classify_subject` returns `None`, i.e. clean, with and without `thread_reply`. **That is a fifth shape the module needs: a merge field that rendered to nothing inside otherwise-present copy.** It is detectable the same way everything else there is - compare the rendered row against its own stored template and refuse a token that collapsed to empty.

## 10. Angle performance, as replies rather than rates

| angle | replies | positive | negative | other | negative share |
|---|---|---|---|---|---|
| `tools_fragmented` | 495 | 19 | 235 | 241 | 47.47% |
| `margin_visible_late` | 166 | 3 | 79 | 84 | 47.59% |
| `utilisation_unknown` | 94 | 1 | 23 | 70 | 24.47% |
| `signoff` | 60 | 0 | 20 | 40 | 33.33% |
| `permission_check` | 55 | 0 | 19 | 36 | 34.55% |
| `manual_reporting` | 18 | 0 | 7 | 11 | 38.89% |
| `unmapped` | 11 | 0 | 6 | 5 | 54.55% |

Read this as *which angle produced the conversation*, not *which angle converts*: without a per-step send denominator a step that was sent to more people will show more replies for that reason alone.

## 10b. How many emails a replier had already received, and the overlap between these four campaigns

`GET /api/leads/{id}` returns `lead_campaign_data`, one entry per campaign that lead sits in, each with its own `emails_sent` and `status`. So two things that are usually guesses are read facts here.

**Emails received in the campaign before the reply** - the real measure of how deep into a sequence a reply comes from, independent of which scheduled email the provider attached it to:

| emails this lead received | repliers | share | cumulative | positive | negative | other |
|---|---|---|---|---|---|---|
| 1 | 267 | 30.07% | 30.07% | 11 | 117 | 139 |
| 2 | 214 | 24.10% | 54.17% | 7 | 116 | 91 |
| 3 | 97 | 10.92% | 65.09% | 0 | 42 | 55 |
| 4 | 143 | 16.10% | 81.19% | 4 | 55 | 84 |
| 5 | 59 | 6.64% | 87.84% | 1 | 17 | 41 |
| 6 | 18 | 2.03% | 89.86% | 0 | 6 | 12 |
| 7 | 59 | 6.64% | 96.51% | 0 | 21 | 38 |
| 8 | 31 | 3.49% | 100.00% | 0 | 9 | 22 |

**Overlap.** How many of the OTHER three campaigns had already sent to the same person:

| also worked by N of the other three | repliers | share |
|---|---|---|
| 0 | 206 | 22.91% |
| 1 | 481 | 53.50% |
| 2 | 206 | 22.91% |
| 3 | 6 | 0.67% |

Per campaign, which of the other three had also sent to that campaign's repliers:

| repliers of \ also sent by | 274 | 327 | 328 | 352 |
|---|---|---|---|---|
| 274 | 0 | 62 | 0 | 49 |
| 327 | 76 | 0 | 0 | 136 |
| 328 | 0 | 0 | 0 | 163 |
| 352 | 61 | 105 | 139 | 0 |

And the lead's own status in the campaign it replied to (`lead_campaign_data.status`):

| lead status | repliers |
|---|---|
| `replied` | 888 |
| `None` | 11 |


## 11. Deliverability and the sending estate

Bounce substring hits across the bounce rows read (one row can hit more than one bucket; these are substrings of the bounce body, not an SMTP code taxonomy):

| bounce substring | hits |
|---|---|
| address_not_found | 919 |
| does_not_exist | 452 |
| relay_denied | 308 |
| spam_rejected | 241 |
| blocked_policy | 111 |
| mailbox_full | 35 |
| user_unknown | 23 |

**107 distinct sending domains of ours** received these 899 replies - every one a lookalike of the client's name (`productive`, `productiveai`, `productive-ai`, `productiveaibet`, plus `www`-prefixed and `.shop` / `.online` / `.org` variants). No single domain carries more than 28 of the replies. That is a deliberate spray across a large lookalike estate, and it is worth stating plainly beside the bounce numbers: a `spam_rejected` or `blocked_policy` bounce on one of these is a reputation signal about a domain built to look like the client's. The top 20 by replies received:

| our sending domain | replies received | positive | negative | other |
|---|---|---|---|---|
| gproductive.com | 28 | 2 | 8 | 18 |
| useproductiveaibet.com | 27 | 0 | 10 | 17 |
| wwwmyproductiveai.com | 27 | 0 | 6 | 21 |
| go-productive.com | 24 | 0 | 7 | 17 |
| withproductiveaibet.com | 24 | 0 | 11 | 13 |
| getproductiveai.com | 24 | 2 | 12 | 10 |
| theproductiveaibet.com | 22 | 1 | 5 | 16 |
| myproductiveaibet.com | 21 | 0 | 6 | 15 |
| heyproductive-ai.com | 18 | 0 | 5 | 13 |
| gohealthyproductive.com | 18 | 1 | 6 | 11 |
| goproductivebook.com | 18 | 1 | 3 | 14 |
| useproductiveai.com | 17 | 0 | 3 | 14 |
| wwwheyproductiveai.com | 17 | 0 | 8 | 9 |
| getproductiveaibet.org | 17 | 0 | 8 | 9 |
| withproductive-ai.com | 16 | 0 | 4 | 12 |
| theproductiveaiblog.com | 16 | 1 | 8 | 7 |
| wwwtheproductiveai.com | 16 | 0 | 6 | 10 |
| goproductive.shop | 16 | 0 | 8 | 8 |
| theproductiveai.online | 15 | 0 | 4 | 11 |
| goproductivetraining.com | 13 | 0 | 6 | 7 |


## 12. Defects in our own reading, found by doing this

These are not campaign findings, they are code findings, and they change what the suppression ledger would have contained.

**12.0 The classifier disagrees with the human on nearly every reply a human called interested.** EmailBison's `interested` flag is set by a person in its UI. Across the readable inbox rows, here is what `replies.classify` said about the rows a human had flagged:

| classifier verdict on a human-flagged `interested` reply | rows | share |
|---|---|---|
| `unknown` | 13 | 56.52% |
| `positive` | 5 | 21.74% |
| `unsubscribe` | 2 | 8.70% |
| `negative` | 2 | 8.70% |
| `referral` | 1 | 4.35% |

Of 23 human-flagged rows the classifier called **5 `positive`**. It called **4 of them a refusal or a removal request** - rows that, merged into a suppression ledger unreviewed, would suppress somebody the team had marked as a lead. Every one is in the per-person list flagged `human_interested_but_classified_negative: true`, and two of the four are `unsubscribe` at **0.95**, from two different mechanisms, both worth fixing:

- One reply says, in the prospect's own words, *"If you want to set up a phone call to chat, we can certainly do that."* The evidence phrase the classifier fired on is `unsubscribe`, and it comes from **the replier's own corporate email footer** 1,450 characters further down - a legally required opt-out line on THEIR outbound mail. `extract_prospect_text` reported `method: no_quote`, `had_quote: False`, so the footer and the quoted original were both handed to the classifier as the prospect's sentence. A meeting acceptance became a removal request at 0.95 confidence.
- The other fired on `remove me` inside the sentence *"...even if it is just to ask people to remove me from their CRM/distribution lists"* - the prospect describing their own habit, not asking us for anything. The quote stripping worked here (`method: top_post`); the pattern simply cannot see that the request is not addressed to us.

**12.1 `UNSUBSCRIBE_PATTERNS` says "me" and never "us".** `\bremove me\b` and `\b(?:remove|delete) me from (?:your|this|the) (?:list|database|mailing)\b` both require the first person singular. A reply reading `Please remove us from your mailing list` matches neither. Measured on one reply in campaign 274 which `classify` returned as **`positive` at 0.75** because the same sentence contains the word `interested`. A removal request was classified as a buying signal.

**12.2 `extract_prospect_text` is blind to the Outlook header-block quote.** `_find_quote_start` knows `-----Original Message-----`, `On ... wrote:` and `>`-prefixed lines, and nothing else. A reply whose quoted original begins with a bare `From:` / `Sent:` / `To:` / `Subject:` block is handed to the classifier **whole**, so our own step copy is classified as the prospect's sentiment - the exact failure that function exists to prevent. **44 of the readable inbox rows are in this shape.** One of them, in campaign 327, is a reply whose entire content is the single word `Stop`: `classify` returned `positive` at 0.75 on the evidence phrase `that would be useful`, which is **our sentence, not theirs**.

**12.3 The bare-`stop` pattern cannot fire through a signature.** `r"^stop[\s.!]*$"` is anchored to the whole message on purpose, which is right, but it means a one-word `Stop` followed by a signature block or an unstripped quote never matches. Combined with 12.2 this is how a stop becomes a positive.

**12.4 A merge field rendered empty into 88 live subject lines and nothing caught it.** Section 9 has the measurement; the gap is that `emptyrender`'s four shapes all describe copy that is empty or a bare placeholder, and none describes a present sentence with a hole in it.

Across all four campaigns **49 readable replies contain a literal removal token in the prospect's own words while `classify` returned something other than `unsubscribe` or `account_do_not_contact`.** Every one of them is in the per-person list handed to the operator, flagged `review_required: true`, with the classifier's own verdict beside the token so the disagreement is visible rather than resolved silently.

## 13. Actions

### For copy

1. **Front-load. 481 of 888 repliers answered on the first or second email (54.17%), and 775 of the 888 replies whose send could be dated arrived on the day of the send or the day after (87.27%).** The sequences are 5 and 8 steps long and the back half is buying very little. Shorten on that evidence, and read silence as an answer much sooner than the current 1-5 day waits imply.
2. **Keep the fragmented-stack opener.** Both sequence families open on it (`tools_fragmented`) and that is where the reply volume is concentrated. The margin and utilisation angles sit mid-sequence and arrive into a conversation that already exists; do not promote one of them to step 1 on the strength of this data, because the per-step send denominator is unreadable and a step sent to more people shows more replies for that reason alone.
3. **The `permission_check` step - 327/328 step 7, `wrong person at {COMPANY}? / should I be talking to someone else?` - is the only step that asks a question a busy person can answer in four words.** Move that move forward instead of spending it as a give-up step.
4. **Drop the `signoff` step or give it something to answer.** The last step in all four sequences is a withdrawal note, and it collects negatives and removals.
5. **Fix `{INDUSTRY}` before any sequence merges a vertical again, and add the fifth shape to `emptyrender`.** 88 subject lines went out reading `what we see with agencies`. A campaign that personalises on a field the lead rows do not carry is worse than one that does not personalise.
6. **Fix the reply classifier before anything automated reads this corpus.** Section 12: a one-word `Stop` came back `positive`, a meeting acceptance came back `unsubscribe` at 0.95, and `remove us` matches no pattern at all.

### For targeting

1. **693 of 899 repliers had already been emailed by at least one of the other three campaigns (77.09%), and `lead_campaign_data` names campaigns beyond these four - 262, 263, 264, 265, 266, 329, 330, 331 and 334 - working the same people.** The overlap matrix in section 10b shows the shape: 274 and 327 share repliers heavily (both USA), 352 overlaps all three, and 328 is disjoint from the two USA campaigns because it is the EU list. So this is not four audiences; it is two lists worked repeatedly, plus a multichannel campaign laid over both. Before any new cohort is sourced, dedupe against the whole workspace rather than per campaign.
2. **Compare 327 and 328 on bounce rate, not reply rate.** They carry identical copy, so the difference is list quality: EU bounces harder (1.12% against 0.90%). That points at where the EU addresses came from.
3. **Bounces are a first-contact problem, not a reputation problem.** The per-step bounce columns in section 5 put the large majority of every campaign's bounces on step 1. That is verification before send, not sender warm-up.
4. **Write the vertical onto the lead at push time.** Nothing in the provider carries one, so no reply in this corpus can be segmented by `src/segments` vertical. That is a gap in what we send, not in what the provider stores.
5. **Reconcile the persona list against the titles that actually replied.** Section 7 is dominated by titles `config/clients/productive.yaml` matches to nothing. Either the configured list is too narrow for the people who answer this copy, or these campaigns were never persona-targeted - and the 327/328 copy branches on `{TITLE}` inside one message, which suggests the second.
6. **Every lead in these four campaigns is contacted and none is canary-eligible.** 274 contacted 4994 of its 9734 leads; the other three are still sending. The clean-list question has to be answered somewhere else.
7. **Geography is readable per replier and should be used.** The lead `location` variable gives a real place for most repliers (section 8). Poland and Canada both appear in volume and both ARE on this client's configured `market.geos`, so nothing here is out of policy - but the distribution is worth comparing against where the client wants to grow.

## 14. What I could not measure

- **Per-step send denominators, therefore per-step reply RATES.** No per-step filter and no per-step statistics route exist; the queue is 97,115 rows on 352 at 15 rows a page.
- **Open rate.** `open_tracking: false` on all four; `opened` and `unique_opens` are 0 and mean nothing.
- **Why `replied` exceeds the readable inbox rows** on 327, 328 and 352 (section 1).
- **The vertical of any replying company.** Not recorded on the lead for 274, 327 or 328, and empty on every rendered email in 352 (section 9).
- **Geography for the 187 repliers whose lead carries no `location`** (`absent` in section 8) and the 11 whose lead row was not fetched. Everything else in that table is the provider's own place string; the ccTLD table beside it is a proxy and is labelled as one.
- **Reply sentiment for the 1026 reply events with no readable row.** They are counted in the denominator and are absent from every content finding.
- **Whether a given reply was answered by a human on our side.** The feed carries our outbound mail but reply-to-reply threading was not reconstructed.
- **A/B variant performance.** 274 and 352 hold 27 and 39 variant rows; variants were folded onto their parent step because per-variant send counts are unavailable for the same reason as per-step ones.
- **Why the membership route and `total_leads` disagree**, and why the queue's `sent` count sits ~1,000 below `emails_sent` on every campaign.
- **Whether the empty `{INDUSTRY}` render hurt anything.** It is measurable that it happened in 88 subject lines; whether those performed worse is not, because the per-step send denominator is missing.
- **The full overlap picture.** Overlap is measured only among the people who REPLIED, because `lead_campaign_data` was read for those 694 leads only. Walking all 52,724 memberships at 15 rows a page was not attempted. The campaigns named beyond these four (262-266, 329-331, 334) are therefore a floor, not a census.
- **Reply sentiment of the 2,350 bounce rows beyond their substring buckets.** Bounce bodies were bucketed by substring, not parsed to SMTP codes.

## 15. The negative / DNC list handed over, in counts only

The list itself is personal data and lives in the operator's scratchpad. Its shape and size are not personal data and belong here.

It is keyed to what this repo's suppression state actually stores, read from the code rather than invented:

- `work/agency-dnc.jsonl`, written by `agencydnc.add` - `{"fingerprint", "reason", "at"}`, where `fingerprint` is `sha256("email:<normalised>")` and `reason` is one of `requested | legal | complaint | internal`.
- `config/operator-exclusions.jsonl`, written by `operatorexclusion.exclude_address` - `{"op", "account", "origin", "by", "reason", "authority", "at", "task"}`, where `account` is `sha256("address:<normalised>")` and `origin` is one of `classifier | human_review | compliance | operator_policy`.

| measure | value |
|---|---|
| reply rows that are negative or carry a removal token | 432 |
|   of which from campaign 274 | 53 |
|   of which from campaign 327 | 79 |
|   of which from campaign 328 | 66 |
|   of which from campaign 352 | 234 |
| distinct people (one row per person) | 352 |
|   in more than one of these campaigns | 60 |
| removal requests - `suppress_scope: contact` or `account` | 162 |
|   of those, account-wide (`account_do_not_contact`) | 2 |
| not a removal - sequence stop only (`suppress_scope: none_yet`) | 190 |
| `reason: requested` (agencydnc vocabulary) | 162 |
| `reason: internal` (agencydnc vocabulary) | 190 |
| **`review_required: true` - DO NOT MERGE BLIND** | 45 |
|   of those, a human had marked the reply `interested` | 4 |
| rows with a usable `fingerprint` | 352 |
| rows with at least one `sender_email_id` to join on | 290 |
| strongest classification `negative` | 167 |
| strongest classification `unsubscribe` | 123 |
| strongest classification `unknown` | 30 |
| strongest classification `not_relevant` | 25 |
| strongest classification `objection` | 5 |
| strongest classification `account_do_not_contact` | 2 |

**Two things about this list the operator has to decide, not me.**

1. `agencydnc`'s own docstring says a reply must NOT put anybody on the agency list - *"Only a request made to the agency does, and it is written deliberately by a super admin, never derived."* Every row here is derived from a reply. So the `requested` rows are candidates for that file and the `internal` ones are not; `accountpolicy` is the module that already draws this line - `REMOVAL_REQUESTS = (UNSUBSCRIBE, ACCOUNT_DNC)` suppress, while `NEGATIVE`, `NOT_NOW` and `NOT_ICP` only stop that person's sequence. The rows are tagged `suppress_scope` accordingly: `contact`, `account`, or `none_yet`.
2. The `review_required` rows must not be merged blind. They are the rows where the classifier and the evidence disagree - a literal removal token the classifier did not call a removal, or a reply a human had marked `interested` that the classifier called a refusal. Both verdicts travel with the row.

---

Per-person negative and DNC rows, with the provider ids needed to join and the keys `work/agency-dnc.jsonl` and `config/operator-exclusions.jsonl` actually use, were written to the operator's scratchpad and are deliberately **not** in this repository: they are personal data. This document contains counts, rates, step numbers, angle and persona names, ccTLDs and our own sending domains, and no prospect identity.
