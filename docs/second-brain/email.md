# Second brain: email

**What this file is.** What the estate's email outreach actually did, measured
against the replies it earned. Every line carries its source, its date and its
`n`. Nothing is in here that was not computed from data read on the date shown.
Where a number could not be derived it says UNKNOWN and says what would derive
it — because missing evidence is never positive evidence.

**Written 2026-10-03, TASK-980, from EmailBison provider GETs (read-only, no
write) plus the reply census described below.** Companion files:
`linkedin.md` (the LinkedIn/HeyReach half), `scenarios.md`, `defects.md`,
`decisions.md`.

**The ordering metric is POSITIVE REPLIES PER 100 SENT**, not reply rate.
Reply rate is kept because it is measurable and it moves, but it ranks the
wrong thing: of the 899 classified replies, 201 are `unsubscribe` and 197 are
`negative` against 19 `positive` (n=899, 2026-10-01 classification). A campaign
can lead on reply rate and be last on the metric that pays.

**Nothing in this file is an exemplar for the writer until the operator has
read it.** Nothing here has been written into `prompts/exemplars/` and nothing
has been wired into `WRITER_SYSTEM`.

**PII.** Our own texts are ours and appear in full. Recipient names, companies,
email addresses, phone numbers and domains do not appear at all; our step copy
is quoted in its stored template form, which carries merge tokens rather than
anyone's data. Real recipient data stays in `work/` and in session scratchpads,
both gitignored.

---

## 1. How these numbers were made, and what each denominator is

Three different denominators appear below and they are not interchangeable.

**Sends per step — EXACT, derived.** The provider exposes no per-step send
statistic. `sequence_step_id` is accepted and then silently ignored on
`/campaigns/{id}/scheduled-emails` (the filtered total came back identical,
46,710, and the rows returned carried step ids that were not the one asked
for — measured 2026-10-03). `per_page` is pinned at 15 whatever is sent, and
offset pagination hard-caps at page 1000 — page 1000 returns HTTP 200 and page
1001 returns HTTP 422, while `last_page` claims 1814. So a filtered total is
impossible, a random-page frame is truncated to the earliest 15,000 rows, and a
full walk of the send ledger would be about 14,700 pages.

What is exposed is `lead_campaign_data[].emails_sent`, per lead **per
campaign**. An EmailBison sequence is sequential, so a lead with
`emails_sent = m` received steps 1..m, and therefore

    sends at step k  =  #{leads in that campaign whose emails_sent >= k}

All four campaigns' lead lists were walked to exhaustion by cursor on
2026-10-03: 10,049 / 10,008 / 10,915 / 21,689 leads read against declared
totals of 10,049 / 10,008 / 10,915 / 21,689, every walk `exhausted: true`,
52,661 leads in 3,512 pages. Counters only were stored — no address, name,
company or custom variable.

**The positive control on that derivation**, because a derived report is only
as good as its last verification:

| campaign | Σ per-lead `emails_sent` | provider campaign `emails_sent` | ratio | leads with ≥1 send | provider `total_leads_contacted` |
|---|---|---|---|---|---|
| 274 | 27,363 | 28,331 | 0.966 | 4,815 | 4,994 |
| 327 | 47,105 | 47,795 | 0.986 | 7,878 | 8,013 |
| 328 | 38,501 | 38,641 | 0.996 | 7,723 | 7,772 |
| 352 | 94,004 | 94,423 | 0.996 | 20,661 | 20,842 |

Four independent reconciliations between 0.966 and 0.996, in the same
direction (the campaign counter is the larger, consistent with its counting
sends the per-lead field has since stopped carrying). 274's 27,363 also sits
between its two provider figures — `emails_sent` 28,331 and queue `sent`
27,205. The derivation stands.

**Replies per campaign — EXACT.** `lead_campaign_data[].replies`, summed over
the same exhaustive walk: 70 / 522 / 753 / 549, total **1,894**, against
provider campaign `replied` of 73 / 532 / 762 / 558 (total 1,925) — within 2%
on every campaign.

**Replies per step and per class — a 47.5% SAMPLE, not a census.** This is the
single most important caveat in the file and it was not known before today.
The 899-row corpus is the `Tracked Reply` rows from
`/campaigns/{id}/replies`, walked to its own declared exhaustion on 2026-10-01
(273 + 638 + 712 + 1,564 = 3,187 raw rows = 1,882 `Bounced` + 899
`Tracked Reply` + 406 `Outgoing Email`). But that endpoint's declared total
is **not** the reply ledger. Per campaign:

| campaign | Tracked Reply rows readable | replies actually recorded | coverage |
|---|---|---|---|
| 274 | 73 | 70 | 104.3% |
| 327 | 160 | 522 | 30.7% |
| 328 | 216 | 753 | 28.7% |
| 352 | 450 | 549 | 82.0% |
| **all** | **899** | **1,894** | **47.5%** |

274 is complete. 327 and 328 are under a third. So **every per-step and
per-class rate below is a FLOOR**, understated by a factor that differs per
campaign, and a zero in a 28.7%-covered campaign is not a measured zero. The
endpoint behaves like an inbox view rather than a ledger. What would close the
gap: either a provider route that lists replies by campaign without the inbox
filter, or the per-scheduled-email `replies` counter walked across the send
ledger (about 14,700 pages at the pinned `per_page` of 15).

**Step attribution was verified, not assumed.** 374 of 352's 450 replies and 35
of 274's 73 land on A/B *variant* steps rather than on the ordered parent, so
the step order has to be resolved through `variant_from_step`. Resolving it
independently and comparing against the corpus's stored `step_order`: **888
agree, 0 disagree, 11 unresolvable** (step ids deleted from the campaign since).
Those 11 are reported as "no step resolved" and are never silently dropped into
a step.

**Rendered word counts — a 7,200-row sample with a stated frame.** The stored
templates carry Liquid conditionals, so a template's word count is not what
anybody received: campaign 327's em1 template is 281 words and renders at a
median of 136. Rendered lengths were measured from 120 random pages per
campaign of `status=sent` (1,800 rows each, 7,200 total, 2026-10-03). Because
offset pagination caps at page 1000, that frame is the earliest 15,000 sent
rows of each campaign — fine for "how long is this step when it renders",
not a frame for a rate, and no rate below uses it.

**`confidence` on a classified reply is a per-class CONSTANT and carries no
information.** Measured across all 899: every `positive` is exactly 0.75, every
`negative` exactly 0.80, every `unsubscribe` exactly 0.95, every `unknown`
exactly 0.0 — 15 classes, 7 distinct values, zero within-class variation. It is
a label restating the class, not a measurement of certainty. A reply cannot be
triaged by it, and the 0.75 on a bad call is not a low-confidence outlier; it
is what every positive gets.

**The opt-out is the reply, confirmed three independent ways** (operator
decision 2026-09-24, and these are the measurements of it): `can_unsubscribe`
is `false` on all four campaigns; `unsubscribed` is 0 on all four; and **0 of
95 steps in the inventory contain any opt-out wording** (searched for
unsubscribe / opt out / stop hearing / remove you / reply STOP). So an
`unsubscribe` classification is a person typing a removal request into a reply,
and it belongs in the reply-rate numerator. It is counted as a reply
everywhere below, and never as a positive.

---

## 2. The estate, as two populations

**The 20 Resonate OS campaigns** — campaigns our code created. Read live from
the provider 2026-10-03, all 40 EmailBison campaigns paginated (declared 40,
read 40), the 20 identified as the 17 whose name begins `RESONATE` plus
503/504/505:

    451, 481, 484, 485, 487, 489, 491, 492, 493, 494,
    495, 496, 497, 498, 500, 501, 503, 504, 505, 506

    emails_sent total ........ 918
    replied total ............  27
    total_leads_contacted ....  763
    campaigns with any send ... 14 of 20
    largest ... 491 (411 sent, 11 replied), 492 (245 sent, 11 replied)

**918 sends and 27 replies is the entire measured history of copy this system
wrote.** It is not enough to rank anything by. It is also not clean: CLAUDE.md
records that 77 of those sends carried an empty subject and a `<p></p>` body,
and 64 from 503/504/505 carried a different agency's pitch signed with the
operator's name. Four of the 27 replies are replies to a blank email. A
reply-per-send figure computed over this population would be measuring two
incidents, so none is quoted here as a performance number.

**The 4 internal campaigns** — 274, 327, 328, 352, declared internal by the
operator 2026-10-01, run by hand for the same end client, never written to, and
a read-only learning asset. **206,973 derived sends and 1,894 recorded
replies.** This is where every number in sections 3 to 7 comes from.

That asymmetry is the finding that frames the rest: the learning signal is
225× larger on the campaigns our code did not write (206,973 sends vs 918).

---

## 3. Campaign 274 — "April 8th", 8 steps, archived

    created 2026-04-08, status archived, 9,734 leads, 4,994 contacted
    derived sends 27,363 | replies 70 (exact) | reply rate 0.2558% (70/27,363)
    per contacted lead 1.433% (69/4,815)
    census coverage 104.3% (73 readable of 70 recorded) - complete
    POSITIVES 0 of 73 classified | positives per 100 sent 0.0000 (0/27,363)

| step | sends | replies | reply rate (floor) | pos | pos/100 | unsub | neg | ooo | unknown | rendered words (median) | thread | wait |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| em1 | 4,815 | 26 | 0.5400% | 0 | 0.0000 | 11 | 5 | 0 | 10 | 117 (n=147) | no | 2d |
| em2 | 4,309 | 18 | 0.4177% | 0 | 0.0000 | 11 | 5 | 0 | 1 | 236 (n=241)* | yes | 3d |
| em3 | 3,975 | 5 | 0.1258% | 0 | 0.0000 | 2 | 2 | 0 | 0 | 129 (n=215) | no | 2d |
| em4 | 3,394 | 10 | 0.2946% | 0 | 0.0000 | 1 | 5 | 0 | 2 | 277 (n=140)* | yes | 5d |
| em5 | 3,094 | 2 | 0.0646% | 0 | 0.0000 | 0 | 1 | 0 | 1 | 127 (n=206) | no | 3d |
| em6 | 2,872 | 1 | 0.0348% | 0 | 0.0000 | 0 | 0 | 0 | 1 | 130 (n=298) | no | 3d |
| em7 | 2,601 | 3 | 0.1153% | 0 | 0.0000 | 2 | 0 | 0 | 1 | 146 (n=296) | no | 4d |
| em8 | 2,303 | 5 | 0.2171% | 0 | 0.0000 | 3 | 1 | 0 | 1 | 97 (n=257) | no | 1d |
| no step | — | 3 | — | — | — | — | — | — | — | — | — | — |

\* a `thread_reply` step's rendered body includes the quoted previous email, so
its word count is not comparable with a fresh-subject step's. 274 em2's own
text is roughly 236 − 117 ≈ 119 words.

Note 0 `out_of_office` across all 73 — the only campaign of the four with none,
and it is the only archived one, so its replies were collected over a closed
window rather than a live one.

The copy is in `work/` form only for this campaign's variants (27 of its 35
steps are variants); the 8 ordered steps are long-form, 97 to 277 rendered
words, 2–5 day waits, with the "P.S." present in 100% of sampled renders of
all 8 steps (n=1,800).

---

## 4. Campaign 327 — "April 22nd new approach", USA, 8 steps, ACTIVE

    created 2026-04-23, status active, 9,676 leads, 8,013 contacted
    derived sends 47,105 | replies 522 (exact) | reply rate 1.1082% (522/47,105)
    per contacted lead 6.448% (508/7,878)
    census coverage 30.7% (160 readable of 522 recorded) - FLOOR
    POSITIVES 2 of 160 classified | positives per 100 sent 0.0042 (2/47,105)

| step | sends | replies | reply rate (floor) | pos | pos/100 | unsub | neg | ooo | unknown | rendered words | thread | wait |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| em1 | 7,878 | 30 | 0.3808% | 0 | 0.0000 | 11 | 9 | 1 | 8 | 136 (n=159) | no | 2d |
| em2 | 7,162 | 24 | 0.3351% | 1 | 0.0140 | 8 | 8 | 1 | 6 | 240 (n=199)* | yes | 4d |
| em3 | 6,512 | 17 | 0.2611% | 0 | 0.0000 | 4 | 1 | 5 | 6 | 141 (n=233) | no | 2d |
| em4 | 5,896 | 23 | 0.3901% | 0 | 0.0000 | 6 | 3 | 11 | 3 | 104 (n=240) | no | 3d |
| em5 | 5,460 | 14 | 0.2564% | 0 | 0.0000 | 2 | 0 | 8 | 3 | 142 (n=231) | no | 3d |
| em6 | 5,056 | 12 | 0.2373% | 0 | 0.0000 | 5 | 1 | 4 | 2 | 139 (n=248) | no | 3d |
| em7 | 4,727 | 30 | 0.6347% | 1 | 0.0212 | 7 | 3 | 4 | 11 | 108 (n=245) | no | 3d |
| em8 | 4,414 | 6 | 0.1359% | 0 | 0.0000 | 4 | 1 | 1 | 0 | 104 (n=245) | no | 1d |
| no step | — | 4 | — | — | — | — | — | — | — | — | — | — |

**Our copy, em1** (template as stored; 281 template words, 136 rendered median,
n=159; `{...|...}` is spintax and `{%  %}` is Liquid):

> SUBJECT: `{how {COMPANY} tracks margin today|the ops stack at {COMPANY}|project profitability at {COMPANY}}`
>
> ```
> {% assign title = '{TITLE}' | downcase | strip %}{% assign loc = '{LOCATION}' | strip | default: 'your market' %}
> {Hi|Hey|Hi there} {FIRST_NAME},
>
> {% if title contains "founder" or title contains "owner" or title contains "ceo" %}Building {COMPANY} from the ground up means you've probably duct-taped together the ops layer as you went -- project tool here, time tracking there, budgets in a spreadsheet, invoices somewhere else.{% elsif title contains "coo" or title contains "operations" %}
>
> Running operations at {COMPANY} usually means you're the one who actually sees how many tools it takes to answer one question: are we profitable on this?{% elsif title contains "cfo" or title contains "finance" %}The financial layer at most agencies is the last thing to get cleaned up -- time logs that don't connect to budgets, invoices that lag the work by weeks, forecasts built in spreadsheets nobody trusts.{% else %}Most {TITLE}s I talk to are running 3 to 5 tools just to answer one question: are we actually making money on this project?{% endif %}
>
> Productive fixes that.
>
> One platform for projects, time tracking, budgets, resource planning, and invoicing, all connected so the numbers update in real time.
>
> Agencies in {{ loc }} use it to get from "I think we're doing okay" to "here's our margin by client, right now."
>
> No demo call needed.
>
> If you just want to see it with your own hands, just reply {yes|"yes"|yes please} and I'll set up a free trial for you and your team, same day.
>
> {SENDER_FIRST_NAME}
>
> P.S. Pulled up your profile before writing this, made me think the reporting and financial visibility side would land most for you. Happy to be wrong on that.
> ```

**Our copy, em7** — the step that earned one of 327's two positives, and the
shortest of its eight at 108 rendered words (n=245). Full text of all eight
steps is in the measurement bundle; em7's distinguishing features are in §6.

Campaign 327's whole sequence shares one CTA shape: **"reply yes" in 100% of
sampled renders of all 8 steps (n=1,800)** and an explicit "no demo call
needed" / "no call" promise in em1–em4 (100% of their renders). It never asks
for a call. Its two positives came from em2 and em7.

---

## 5. Campaign 328 — "April 22nd new approach", EU, 8 steps, ACTIVE

    created 2026-04-23, status active, 10,285 leads, 7,772 contacted
    derived sends 38,501 | replies 753 (exact) | reply rate 1.9558% (753/38,501)
    per contacted lead 9.478% (732/7,723)   <- HIGHEST OF THE FOUR
    census coverage 28.7% (216 readable of 753 recorded) - FLOOR, the thinnest
    POSITIVES 0 of 216 classified | positives per 100 sent 0.0000 (0/38,501)

| step | sends | replies | reply rate (floor) | pos | pos/100 | unsub | neg | ooo | unknown | rendered words | thread | wait |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| em1 | 7,723 | 47 | 0.6086% | 0 | 0.0000 | 8 | 3 | 10 | 24 | 145 (n=223) | no | 2d |
| em2 | 6,501 | 44 | 0.6768% | 0 | 0.0000 | 7 | 12 | 5 | 16 | 263 (n=234)* | yes | 3d |
| em3 | 5,633 | 18 | 0.3195% | 0 | 0.0000 | 4 | 4 | 4 | 6 | 142 (n=281) | no | 4d |
| em4 | 4,765 | 46 | 0.9654% | 0 | 0.0000 | 5 | 4 | 27 | 6 | 105 (n=296) | no | 3d |
| em5 | 3,991 | 9 | 0.2255% | 0 | 0.0000 | 0 | 0 | 6 | 2 | 141 (n=242) | no | 3d |
| em6 | 3,565 | 6 | 0.1683% | 0 | 0.0000 | 2 | 0 | 2 | 2 | 136 (n=188) | no | 3d |
| em7 | 3,278 | 25 | 0.7627% | 0 | 0.0000 | 3 | 4 | 6 | 10 | 108 (n=164) | no | 3d |
| em8 | 3,045 | 20 | 0.6568% | 0 | 0.0000 | 1 | 1 | 14 | 4 | 102 (n=172) | no | 1d |
| no step | — | 1 | — | — | — | — | — | — | — | — | — | — |

328 is 327's copy pointed at the EU — the two sequences are the same eight
emails with the same CTA shape (reply-yes in 100% of renders, n=1,800).
**It is the best campaign in the estate on reply rate and it produced zero
positives.** Both halves of that sentence need their caveat: 9.478% of
contacted leads replied (732/7,723), and the 0 positives is 0 observed in a
216-row window covering 28.7% of its 753 replies. 0 of 216 bounds the positive
share of its replies at roughly 1.4% at 95%, which over 753 replies is **up to
about 10 unobserved positives**. So 328's positive count is not zero; it is
**UNKNOWN, bounded above by ~10**. What would resolve it: classifying the other
537 replies, which needs the reply-readability gap in §1 closed first.

The other thing 328 shows: `out_of_office` is 72 of its 216 (33.3%), the
highest share of the four, and em4 alone is 27 of 46 replies (58.7%). An EU
sequence running through European holiday windows spends a large part of its
reply volume on auto-responders.

---

## 6. Campaign 352 — "HeyReach Connection Campaign", 5 steps, ACTIVE

    created 2026-05-13, status active, 21,676 leads, 20,842 contacted
    derived sends 94,004 | replies 549 (exact) | reply rate 0.5840% (549/94,004)
    per contacted lead 2.352% (486/20,661)
    census coverage 82.0% (450 readable of 549 recorded)
    POSITIVES 24 of 450 classified | positives per 100 sent 0.0255 (24/94,004)
                                                            <- BEST OF THE FOUR
    audited positives (my read, §8): 9 | 0.0096 per 100 sent (9/94,004)

| step | sends | replies | reply rate (floor) | pos | pos/100 | unsub | neg | ooo | unknown | rendered words | thread | wait |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| em1 | 20,661 | 184 | 0.8906% | 14 | 0.0678 | 24 | 55 | 8 | 71 | 95 (n=146) | no | 3d |
| em2 | 19,039 | 121 | 0.6355% | 6 | 0.0315 | 23 | 38 | 4 | 39 | 147 (n=126)* | yes | 4d |
| em3 | 18,499 | 61 | 0.3297% | 2 | 0.0108 | 18 | 8 | 5 | 23 | 79 (n=350) | no | 3d |
| em4 | 18,053 | 52 | 0.2880% | 1 | 0.0055 | 15 | 16 | 1 | 17 | 127 (n=489)* | yes | 3d |
| em5 | 17,752 | 29 | 0.1634% | 1 | 0.0056 | 9 | 4 | 1 | 13 | 49 (n=689) | no | 1d |
| no step | — | 3 | — | — | — | — | — | — | — | — | — | — |

**This is the campaign the estate actually learned something from: 24 of the
estate's 26 classifier-positives (92.3%) and 9 of my 10 audited positives, on
45.4% of its sends (94,004 of 206,973).** Two things make it different from
327/328 and the data cannot separate them:

1. **Its email explicitly follows a LinkedIn touch.** The campaign is named
   "HeyReach Connection Campaign" and every one of its five steps references
   the prior channel in text — "reached out on LinkedIn too but figured email
   might be easier", "tried you on LinkedIn as well but email felt like the
   safer bet", "LinkedIn didn't reach you, so". It is the email arm of a
   coordinated two-channel sequence.
2. **It is far shorter.** Own-text rendered medians of 95 / 79 / 49 words for
   its fresh-subject steps (em1/em3/em5, n=146/350/689) against 102–145 for
   327/328's and 97–277 for 274's.

**Both differences point the same way and this corpus cannot tell them apart.**
A test that would: run 352's short question-led copy at accounts with no prior
LinkedIn touch, and 327's long copy behind a LinkedIn touch, and compare. That
experiment does not exist in this data.

**Our copy, em1 — the single best-performing email in the estate by positives
per 100 sent (0.0678, 14 positives / 20,661 sends; audited 6, 0.0290):**

> SUBJECT: `{me again, {FIRST_NAME}|following up from LinkedIn|trying email this time}`
>
> ```
> Hey {FIRST_NAME},
>
> saw your profile and noticed you're {TITLE} at {COMPANY}, reached out on LinkedIn too but figured email might be easier.
>
> quick question, how are you guys currently managing projects, resourcing and finances, is it all in one place or spread across a bunch of different tools?
>
> most {INDUSTRY} agencies we talk to are juggling 3-4 tools and losing visibility on project profitability because of it.
>
> worth a quick chat?
>
> {SENDER_FIRST_NAME}
> ```

**Our copy, em2 (0.0315, 6 positives / 19,039 sends) — a same-thread reply:**

> SUBJECT: `Re: {me again, {FIRST_NAME}|following up from LinkedIn|trying email this time}`
>
> ```
> Hey {FIRST_NAME},
>
> just bumping this up in case it got buried.
>
> not asking for a big commitment, just curious if managing project profitability and resourcing is something {COMPANY} has figured out or still a bit of a pain point.
>
> worth a quick reply either way.
>
> {SENDER_FIRST_NAME}
> ```

**Our copy, em3 (0.0108, 2 / 18,499):**

> SUBJECT: `what we see with {INDUSTRY} agencies`
>
> ```
> Hey {FIRST_NAME},
>
> wanted to share something quick since i work with a bunch of {INDUSTRY} agencies.
>
> the ones that struggle most with profitability usually have the same setup, project management in one tool, finances in another, resourcing in a spreadsheet. by the time something goes wrong its already too late to fix it.
>
> the ones that have it sorted have everything in one place and can see in real time whether a project is on track before it hits invoicing.
>
> curious which camp {COMPANY} is in right now.
>
> {SENDER_FIRST_NAME}
> ```

**Our copy, em4 (0.0055, 1 / 18,053) — same-thread reply, 35 template words,
the shortest step in the estate:**

> SUBJECT: `Re: what we see with {INDUSTRY} agencies`
>
> ```
> {FIRST_NAME},
>
> just bumping this. wdyt, is the way {COMPANY} manages project ops and profitability something thats working well or room to improve?
>
> lmk either way, happy to set something up or leave it here.
>
> {SENDER_FIRST_NAME}
> ```

**Our copy, em5 (0.0056, 1 / 17,752) — the close:**

> SUBJECT: `{last one from me|closing the file on {COMPANY}|signing off, {FIRST_NAME}}`
>
> ```
> Hey {FIRST_NAME},
>
> last one from me, i promise.
>
> i've reached out a few times now and totally get it if the timings off or its just not relevant for {COMPANY} right now.
>
> if things change and you ever want to look at how other {INDUSTRY} agencies are managing projects, resourcing and finances in one place, just reply to this email and ill pick it up.
>
> {SENDER_FIRST_NAME}
> ```

### 6a. The variant arms, and why no arm is a winner

352 runs 39 variant arms behind its 5 ordered steps (44 steps total). Its 450
readable replies land on variants 374 times against 73 on the parents. The 26
positives spread across **17 distinct arms, with a maximum of 4 on any one
arm** (step 4192, a variant of em1).

**Per-arm reply and positive RATES are UNKNOWN**, and deliberately not
estimated here: the lead walk yields sends per step *order*, not per arm, and
there is no per-arm denominator without the 14,700-page send-ledger walk from
§1. Four positives against an unknown denominator is not a rate, and
COPY-EXPERIMENTS.md's rule — no winner called from four replies against three —
applies exactly. What the arms are good for is reading what the positive-earning
text looked like, and the arms agree with the parents: short, lower-case, one
question about the prospect's own operation, LinkedIn named.

Two arm-level observations that are measurements rather than rankings:

- Arms 4194 and 4195 carry **byte-identical bodies and different subjects**, so
  the "variant" axis there is subject-only.
- Arm 4196's stored subject begins with the literal string `Subject: ` —
  **1 of 95 steps in the inventory** — so recipients received a subject line
  reading "Subject: me again, <name>". That arm still earned 1 positive.

---

## 7. What the numbers say, ranked by the metric that counts

**Campaigns, ranked by positives per 100 sent** (classifier unaudited; the
right-hand column is my own audit from §8, which the operator's review
supersedes):

| rank | campaign | sends | positives (classifier) | per 100 sent | positives (audited) | per 100 sent | reply rate (exact) | census coverage |
|---|---|---|---|---|---|---|---|---|
| 1 | 352 | 94,004 | 24 | **0.0255** | 9 | 0.0096 | 0.5840% | 82.0% |
| 2 | 327 | 47,105 | 2 | 0.0042 | 1 | 0.0021 | 1.1082% | 30.7% |
| 3= | 274 | 27,363 | 0 | 0.0000 | 0 | 0.0000 | 0.2558% | 104.3% |
| 3= | 328 | 38,501 | 0 | 0.0000 | 0 | 0.0000 | **1.9558%** | 28.7% |
| | all | 206,973 | 26 | 0.0126 | 10 | 0.0048 | 0.9151% | 47.5% |

**The ranking inverts the reply-rate ranking at both ends.** 328 is first on
reply rate (1.9558%) and last on positives; 352 is third on reply rate
(0.5840%) and first on positives by 6×. Measured, n as shown. The caveat that
keeps 328's zero honest is in §5: it is 0 observed in 28.7% coverage, bounded
above at about 10.

**Step cells, ranked by positives per 100 sent** — 29 ordered step-emails with
exact denominators. 7 have at least one positive; 22 have none.

Top 5:

| rank | cell | sends | replies | reply rate | positives | per 100 sent | own-text words | questions in body | prospect merge vars | thread |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 352 em1 | 20,661 | 184 | 0.8906% | 14 | **0.0678** | 95 | 2 | 3 | no |
| 2 | 352 em2 | 19,039 | 121 | 0.6355% | 6 | 0.0315 | 52 | 0 | 1 | yes |
| 3 | 327 em7 | 4,727 | 30 | 0.6347% | 1 | 0.0212 | 108 | 1 | 2 | no |
| 4 | 327 em2 | 7,162 | 24 | 0.3351% | 1 | 0.0140 | 104 | 0 | 4 | yes |
| 5 | 352 em3 | 18,499 | 61 | 0.3297% | 2 | 0.0108 | 79 | 0 | 2 | no |

"Own-text words" is the rendered median with the quoted opener subtracted on
`thread_reply` steps, since the provider stores the quote inside the body.

Bottom 5. 22 of 29 cells are tied at zero positives, so "bottom" is not an
ordering — these are the five zero cells with the largest `n`, where the zero
carries the most information:

| cell | sends | replies | reply rate | positives | own-text words | questions | vars | thread |
|---|---|---|---|---|---|---|---|---|
| 327 em1 | 7,878 | 30 | 0.3808% | 0 | 136 | 2 | 3 | no |
| 328 em1 | 7,723 | 47 | 0.6086% | 0 | 145 | 2 | 3 | no |
| 327 em3 | 6,512 | 17 | 0.2611% | 0 | 141 | 0 | 2 | no |
| 328 em2 | 6,501 | 44 | 0.6768% | 0 | 118 | 0 | 4 | yes |
| 327 em4 | 5,896 | 23 | 0.3901% | 0 | 104 | 0 | 2 | no |

What separates the two lists, with `n`:

- **Length, and it is the cleanest signal in the file.** Across all 29 cells,
  the 7 that earned at least one positive have own-text lengths of
  32, 49, 52, 79, 95, 104, 108 words — **median 79** (n=7). The 22 that earned
  none run 97 to 160 words — **median 129.5** (n=22). The two distributions
  barely overlap: 5 of the 7 earning cells are shorter than every one of the
  22 that earned nothing. Confounded with campaign, since 5 of the 7 are 352's.
- **The prior channel is named.** 5 of the 5 top cells' campaigns name LinkedIn
  in the body (352: all 5 steps; 327 em7 and em2 do not, and are ranks 3 and 4
  with 1 positive each on the smallest denominators in the table). Counting at
  campaign level: the one campaign that names a prior LinkedIn touch holds 24
  of 26 positives (92.3%) on 45.4% of sends.
- **The CTA.** 327 and 328 use "reply yes, I'll set up a free trial" with an
  explicit "no demo call needed" in **100% of 1,800 sampled renders** and
  produced 2 positives in 85,606 sends (0.0023 per 100). 352 never says "reply
  yes" and asks for a short call or demo in 24.7% of em1 renders (n=146) and
  23.0% of em2 (n=126); it produced 24 in 94,004 (0.0255 per 100). **Asking for
  the call outperformed promising not to need one by 11× on this metric.**
  That is the most counter-intuitive measurement in the file and it rests on 26
  positives, so it is a direction, not a settled number.
- **Questions.** The question-mark count per body across all 95 steps is
  0 in 34, 1 in 49, 2 in 6, 3 in 1, 4 in 1, 5 in 2, 6 in 2. The best cell
  (352 em1) has 2; rank 2 has 0. **No monotone relationship is measurable**
  from 26 positives spread over 7 cells, and none is claimed. What is visible
  is narrower: the top cell's question is about the prospect's own operation
  ("how are you guys currently managing projects, resourcing and finances"),
  while the bottom cells' questions are rhetorical and about the market
  ("are we actually making money on this project?"). That is a reading of 2
  texts, not a measurement.
- **Stating a fact about the prospect's company.** Operationalised as the count
  of distinct prospect-derived merge fields in the body — `{COMPANY}`,
  `{TITLE}`, `{INDUSTRY}`, `{LOCATION}` — because a token substituted from the
  prospect's own record is the only mechanically checkable version of "this
  email says something about *your* company". Top-5 cells carry 3, 1, 2, 4, 2
  (median 2); bottom-5 carry 3, 3, 2, 4, 2 (median 3). **No relationship is
  measurable and none is claimed** — the richer-personalised sequences are the
  ones that earned nothing. This proxy does not distinguish "you are a
  {TITLE} at {COMPANY}", which is a fact about their business card, from a
  fact about how their business runs, and the second is what the top cell's
  question actually goes after. Measuring the second needs a judgement the
  merge-field count cannot make.

### 7a. A measured defect that costs positives

**8.89% of sent emails rendered a merge variable empty** — 73 of 821 sent rows
with stored bodies (74 of the 821 are campaign 352's; 56 of the 73 hits are
352's). Detected as a dangling `at ,` / `at .` / `for  ` where a company token
should have substituted. Among the 32 preceding messages behind the flagged
replies in §8, **5 of 32 (15.6%)** carried one, including sends that went out
reading "saw your profile and noticed you're Project Manager at ." and
"noticed you're Assistant Operations Manager at ,".

One of those five replies was, in full: *"I noticed you could use a copy editor
for your outgoing emails. I am available for freelance work."* The classifier
scored that reply `positive` at 0.75.

The fix is a pre-send assertion that no merge token resolved empty, which is a
copy-path change and belongs to the lane that owns `src/copylint.py`. Not made
here.

Also measured on the live inventory: **98 non-breaking spaces (U+00A0)** across
the 95 steps' subjects and bodies, and **0 of 95 bodies with unbalanced
spintax braces**. The NBSPs are a paste artefact from a rich editor; they break
naive word-splitting and nothing else observed.

---

## 8. The classifier-positive corpus, and the audit that says do not trust the rate

**Every positive rate in this file is labelled `classifier unaudited`, and this
section is why.** The operator's instruction was to collect up to 100
classifier-positive replies with their text for review. **Email holds 26, and
there is no padding it to 100.** Corpora searched: the 899-row classified reply
set (all four internal campaigns, 2026-10-01 classification) and the 3,187 raw
reply rows behind it. The Resonate OS campaigns hold 27 replies in total,
unclassified, and 4 of those are replies to a blank email.

**Counted as positive** (operator's definition — explicit interest, a request
to talk, or a question about the offer): `positive` 19 + `question` 6 +
`meeting_intent` 1 = **26**.

**Counted separately and never positive**: `referral` 5, `send_info` 1 = **6**.

I read all 32 against the operator's definition. **My audit: 10 of 26 are
defensible positives, 2 more are explicit interest that is explicitly
deferred, and 14 are not positives at all — a precision of 38.5% (10/26), or
46.2% (12/26) if deferred interest counts.** The 14 break down as **6 plain
negatives** ("We are not currently interested", "no interested from our
company", "This isn't something we're interested in at this time", "We already
have the systems we need... So we won't be interested moving forward", "I don't
think it's worth retraining our entire team", "Sounds good! I'll keep that in
mind if it ever comes up"), **3 inbound pitches *to us*** (one selling
marketing services, one offering freelance copy editing, one proposing we
become their review subject), **2 "send me information" replies** which the
operator's rule excludes by name, **1 existing customer** sending product
feature requests, **1 reply that merely answers our question** with no
interest, and **1** scored `question` whose text is *"What are you even
pitching here? This is one of the weaker cold-mails I've gotten in a while"*.

**Grouped by why, because the grouping is the fix signal** — 18 wrong rows
across both buckets: 7 plain negatives, 4 inbound pitches to us, 2 send-info,
2 out-of-office read as a referral, 1 existing customer, 1 bare answer, 1
objection. **Not one of the 18 is a threshold problem**, which matters because
`confidence` carries no information to set a threshold against: raising the bar
on `positive` would not fix a single row. The fix is categories and ordering —
a class for inbound pitches, a class for existing customers, `out_of_office`
and `unsubscribe` decided before `referral` and `question`, and negation
handled before any positive match. The full sample with every reply's text is
at `resonate-ops/copy-review/POSITIVE-SAMPLE-2026-10-03.md`, outside git.

The `referral` bucket is worse in kind: **2 of its 5 rows are plain
out-of-office auto-replies** that happen to name a covering colleague, which
the classifier read as a referral. A third is an existing customer saying so.

**Consequences, stated plainly.** The headline 0.0126 positives per 100 sent
rests on a bucket that is 54% wrong by my reading. The audited figure is
0.0048 per 100 sent (10/206,973). The ranking in §7 survives the audit — 352
still leads, 9 audited positives to 327's 1 — because the errors are spread
across campaigns rather than concentrated. **The ranking is more trustworthy
than the rate.** And `confidence` cannot be used to filter: every one of the 26
is exactly 0.75.

### 8a. Positive rows, shaped to assemble across channels

The per-row corpus is `positive-rows` in the measurement bundle, one row per
reply, with these fields so it can be concatenated with the LinkedIn lane's
half: `bucket`, `classification`, `confidence`, `channel` (constant `email`),
`provider` (constant `emailbison`), `campaign_id`, `step_order`,
`sequence_step_id`, `date_received`, `sent_at`, `persona`, `title`, `geo`,
`emails_received_in_this_campaign`, `our_subject`, `our_body` (ours, in full,
fetched per row from the provider by `scheduled_email_id` — 32 of 32 retrieved),
and the reply text. **The rows are NOT in this file**: a reply's text is the
recipient's words and carries their name, company, direct phone number and
signature block, so the corpus lives in the gitignored scratchpad and in
`work/`, and `docs/second-brain/positive-replies.md` should be assembled from
there with the recipient side anonymised. Our side needs no anonymising and
should be carried in full.

**Where in the sequence a positive arrives**, by exact step (classifier
bucket, n=26):

| step | positives | sends | per 100 sent | share of positives |
|---|---|---|---|---|
| em1 | 14 | 41,077 | 0.0341 | 53.8% |
| em2 | 7 | 37,011 | 0.0189 | 26.9% |
| em3 | 2 | 34,619 | 0.0058 | 7.7% |
| em4 | 1 | 32,108 | 0.0031 | 3.8% |
| em5 | 1 | 30,297 | 0.0033 | 3.8% |
| em6 | 0 | 11,493 | 0.0000 | 0.0% |
| em7 | 1 | 10,606 | 0.0094 | 3.8% |
| em8 | 0 | 9,762 | 0.0000 | 0.0% |

**80.8% of positives arrive at em1 or em2 (21 of 26), on 37.7% of the sends.**
Steps 3 through 8 carry 62.3% of the sends (128,885 of 206,973) and 19.2% of
the positives (5 of 26). Reply rate pooled across campaigns falls the same way:
0.6987% at em1 (287/41,077) to 0.1653% at em6 (19/11,493), with a partial
recovery at em7 (0.5469%, 58/10,606) driven by 327 and 328's em7.

**The honest reading of that is not "cut the sequence at em2."** The later
steps' replies are disproportionately `unsubscribe` and `out_of_office`, and
the whole table is a floor at 47.5% coverage. What it does support: the
marginal positive from steps 6–8 is 1 in 31,861 sends (1/31,861 = 0.0031 per
100), against 21 in 78,088 for steps 1–2 (0.0269 per 100) — **an 8.6×
difference in yield per send**, measured, n=26 positives.

**Persona.** Across all 899, the split is 484 `economic_buyer`, 356 `champion`,
59 `not_a_persona`, and it is not noise: `out_of_office` runs at 25.3% of a
champion's replies against 6.2% of an economic buyer's, and `unsubscribe` the
other way, 25.6% against 15.2% (previously measured 2026-10-01, carried
forward here, not recomputed). Among the 26 positives the split is 14
`champion`, 8 `economic_buyer`, 4 `not_a_persona` — 53.8% champion against
champions' 39.6% share of all 899 replies. **That difference is not
measurable at n=26** (10.3 champions expected, 14 observed) and no persona
advantage is claimed. Recorded geography of the 26: 7 United States, 5 Canada,
2 Austria, 1 United Kingdom, 2 other, 6 absent.

---

## 9. Farseer — what is in the data, and precisely what is not

The operator's standing account is that Farseer produced **35 meetings in 14
countries** and is the only engagement where channels were coordinated per
account. Here is what this lane could and could not verify, from EmailBison,
`docs/`, `work/` and git history on 2026-10-03.

**There is no Farseer campaign on EmailBison.** All 40 campaigns were read and
paginated (declared total 40, read 40) and none carries the name in any
casing. The estate under this credential is entirely the one end client's
campaigns plus the 20 Resonate OS ones. So **this lane's half of the Farseer
join is empty, and that is the finding, not a gap in the reading.**

**The engagement ran on LinkedIn, voice, WhatsApp and the phone.** From
`work/slack-history/` (165 messages naming the client across 11 channels,
2026-02-21 to 2026-07-28; `work/` is gitignored and stays so): the campaigns
are discussed in terms of "connections and messages" and HeyReach; there is a
LinkedIn voice-message programme with its generator prompt written down; a
WhatsApp-feature nudge with its message written down; cold calling with a hire
being interviewed for it; and an ABM gifting track with physical merch and a
designed card. The LinkedIn lane owns that half and holds the per-campaign
cadence.

**Meetings, as actually recorded.** Monthly invoice posts in Slack, which are
the only tallies that exist:

| month (post date) | billable meetings | composition as recorded |
|---|---|---|
| Feb 2026 (2026-03-02) | 11 | 2 ABM + 9 cold |
| Mar 2026 (2026-03-31) | 14 | 13 cold − 2 no-show = 11; 4 ABM − 1 no-show = 3; 1 disqualified |
| Apr 2026 (2026-05-04) | 11 | 11 cold − 2 no-show = 9; 2 ABM |
| May 2026 (2026-06-02) | 10 | 14 cold − 2 no-show − 3 disqualified = 9; 2 ABM − 1 no-show = 1 |
| Jun 2026 (2026-06-29) | 10 | 9 cold + 1 ABM |
| **Feb–Jun total** | **56** | |

**So "35 meetings" is not a number this data produces.** 56 were invoiced over
five months; no artefact I read states 35. The string "35" does not co-occur
with the client's name in any of the 165 Slack messages, and neither does
"countr" or "zemlj" in any casing. **"14 countries" is not recorded anywhere**:
country is not a field on any invoice post, and the only geographic information
is implicit in recipient company names, which I will not convert into a country
count because inferring one would be exactly the plausible reconstruction the
operator ruled out. 35 may be a subset — one channel, one quarter, held rather
than billable, or cold-only excluding ABM — but which one is not in the data
and I am not guessing.

**What is NOT recorded anywhere, and where it should live.** This is the part
that matters for the cross-channel join:

1. **Per-meeting channel and step attribution.** Not recorded. The invoice
   posts name the lead and their company and split cold from ABM; they never
   say which channel or which touch produced the meeting. Slack says the
   booking data was entered into **HubSpot** ("u HubSpot upisati info za booked
   meetings", 2026-03-11), which is not a system this repository reads and not
   one I have a credential for. **It should be recorded on the canonical touch
   ledger as the confirmed-event source of the meeting**, so that a meeting has
   a provider, a campaign, a step and a timestamp like any other confirmed
   event. Today it has a name and a price.
2. **Touches before the first positive.** Not derivable. It needs (1) plus the
   per-account touch history across LinkedIn, voice, WhatsApp and phone in one
   ordered sequence. The LinkedIn half exists in HeyReach; the voice, WhatsApp
   and call touches are **recorded only as Slack prose and in no ledger at
   all**, so the ordered per-account cadence cannot be reconstructed for any
   account. This is the single biggest hole in the Farseer record.
3. **The per-channel cadence with days.** Not recorded as a cadence. Day
   offsets exist for EmailBison steps (`wait_in_days`) and for HeyReach
   sequences, but no artefact states the intended cross-channel order or the
   day offsets between channels for this engagement.
4. **The positive reply behind each meeting.** Not recorded. The replies that
   led to the 56 meetings are in LinkedIn inboxes and in a WhatsApp account;
   nothing in `work/` or `docs/` holds them.
5. **Countries.** Never a field. If per-account geography matters to the
   operator's account of this engagement, it has to come from the account
   record at enrolment time, and no artefact carries it for these leads.

**One piece of the Farseer method is recorded in full and is ours, so it is
quoted here** — the voice-message generator prompt, from Slack 2026-02-25. It
is the clearest written statement of the angle that engagement ran on, and it
contradicts the long-form email approach in §4 and §5 on every axis:

> You are a sales outreach assistant for Farseer, a financial forecasting and
> planning platform. Based on the full LinkedIn conversation below, write a
> short voice message script that: sounds natural and conversational; is under
> 30 seconds when spoken; references something specific the prospect said;
> focuses on one clear pain point; briefly positions Farseer as a potential
> improvement, not a replacement pitch; includes a soft, low pressure call to
> action; ends with a question. Tone guidelines: direct and human; not salesy;
> no buzzwords; no long sentences; slightly informal; add one small grammar
> imperfection; max one emoji if used. Objective: create a light nudge to see
> if this is worth exploring, without pushing for a hard meeting.

And the operating instruction that went with it, same channel, 2026-02-25:

> Before you reply on HeyReach, navigate the conversation — add the company
> link and ask the agent to comment on pain points. People want to talk about
> themselves and to know that we can solve the problem — they do not want to be
> pitch-slapped with a 20 minute call straight away.

That instruction is the opposite of what 327 and 328 do (a 136–145 word opener
that pitches the platform and promises no call) and close to what 352 em1 does
(95 words, one question about their operation). It is prose, not a
measurement — but it is prose from the engagement with the best recorded
outcome in the business, and it predicted the only thing §7 measured.

**The client's own name.** This client's web domain is on the paying-customer
roster in `config/suppress.local.txt` and in `FORBIDDEN_DOMAINS` in
`tests/test_fixture_hygiene.py`, which scans every tracked `.md` — so the
domain is deliberately not written anywhere in this file, and neither is any
lead name, lead company or per-lead figure from the invoice posts. The bare
product name is used because the operator asked for this section by that name
and because the repository already names clients in `docs/`. But
`scripts/slack_question_catalogue.py` lists the bare token among the client
identities it replaces with a role, on the stated ground that a client's
identity becomes client-internal the moment it sits in a shared document
beside what they asked for. **That convention and this section disagree, and
the operator should settle it**: if the stricter reading wins, retitle this
section to a role label and add the bare token to `FORBIDDEN_NAMES` so the
guard enforces it rather than leaving it to each writer's judgement.

The first run of this file's own PII scan flagged this very paragraph, because
the earlier wording spelled the domain out while explaining that the domain was
forbidden. That is the third time in this project that a check reintroduced
what it existed to exclude, and the reason the scan is run with a positive
control before every commit.

---

## 10. The new copy, measured against the best old email

**The new-rules regeneration does not exist yet for either account.** Checked
on 2026-10-03: `origin/task-copy-exemplars` carries exactly one copy fixture,
`tests/fixtures/converged-copy-anonymised-2026-10-02.json`, and nothing on any
branch carries a savagebrands artefact. So **the new-rules half of this
comparison is PENDING and is not invented here.** What follows compares the one
committed generated sequence — bigfish, anonymised, generated 2026-10-02 under
the OLD rules, third attempt, `lint_failures_total: 0`, `research_rows: 0` —
against 352 em1, the best old email by positives per 100 sent.

| | 352 em1 (best old, measured) | bigfish em1 (generated, unsent) |
|---|---|---|
| positives per 100 sent | **0.0678** (14/20,661) | **no sends, no data** |
| reply rate | 0.8906% (184/20,661) | no sends, no data |
| own-text words | 95 median (n=146) | 61 |
| questions in body | 2 | 2 |
| prospect merge fields | 3 (`TITLE`, `COMPANY`, `INDUSTRY`) | company name + country + vertical, rendered inline |
| names the prior channel | yes, in every step | no |
| CTA | "worth a quick chat?" | "Are you currently able to see all your projects and their delivery status in one place?" |
| asks for a call | em1 no, em5 yes (a demo with an AE) | em5 yes |
| sequence length | 5 steps, waits 3/4/3/3/1 days | 5 steps |
| step-2 form | same-thread reply (`thread_reply` true) | same subject as em1, reply-shaped |

**Where the new copy is better.**

- **It is shorter at every step**: 61 / 41 / 53 / 46 / 41 words against 352's
  95 / 52 / 79 / 32 / 49. Length is the one axis where the measured signal in
  §7 is consistent and in the new copy's favour — the 7 step cells that earned
  a positive have a median own-text length of 79 words (n=7) against 129.5 for
  the 22 that did not (n=22), and all five new steps sit inside the earning
  range rather than the barren one.
- **It states a fact about the prospect's company in em1** — "<company> is a
  UK-based digital marketing agency" — rather than asserting a fact about the
  market and merging the prospect's title into it. Whether that earns replies
  is **UNKNOWN**: §7 found no measurable relationship for the merge-field proxy,
  and this is the thing that proxy cannot see, so the comparison is a
  difference in kind with no rate attached.
- **It ends every step with a question about the prospect's own operation**,
  which is the narrow feature the best-performing old email shares and the
  22 zero cells do not. Again a reading of texts, not a measured rate.
- **It carries no spintax and no Liquid conditionals**, so it cannot render an
  empty merge token the way 8.89% of sent mail did (73/821, §7a) — the defect
  class is designed out rather than guarded against.

**Where the new copy is worse.**

- **It never names the prior channel.** That is the feature most strongly
  associated with positives in this corpus: the one campaign that names a prior
  LinkedIn touch holds 24 of 26 positives (92.3%) on 45.4% of sends. If
  bigfish's accounts are being worked on LinkedIn too, dropping the reference
  discards the estate's single largest measured signal. If they are not, then
  the comparison does not apply and the best old email is not a valid target —
  and which of those is true is a targeting question this lane cannot answer.
- **Its em2 reuses em1's subject rather than threading.** 352 em2 is a true
  `thread_reply` and is the second-best cell in the estate (0.0315, 6/19,039);
  EMAILBISON-COPY-REQUIREMENTS.md already requires same-thread follow-ups.
  A same subject is not the same thing as a thread reply, and the provider
  field that makes it one is `thread_reply`.
- **Three of its five steps end with a yes/no question** ("Does having a
  forward-looking view... sound useful for your team?", "Is your team's time
  tracking integrated with project budgets today?"). A closed question invites
  a one-word answer, and the estate's own experience of inviting a one-word
  answer is 327/328's "reply yes" CTA: 100% of 1,800 sampled renders, 2
  positives in 85,606 sends, 0.0023 per 100 — **11× worse than 352's open
  question plus call ask**. That is the measurement most directly against the
  new copy's shape, n=26 positives.
- **em4 contains no merge field and no question about the prospect at all** —
  it is three sentences of generic product rationale. Its nearest old analogue
  by that description is 274's middle steps, which produced 0 positives in
  27,363 sends.
- **em5 asks for "a quick walkthrough with a Productive AE" and offers a
  premium trial.** 352 em5, the measured best close, asks for nothing and
  leaves the door open ("just reply to this email and ill pick it up"),
  earning 1 positive in 17,752. The new em5 is the *only* step that asks for
  a meeting, which inverts the old sequence's shape (ask early, release late).

**What this comparison cannot say.** bigfish's copy has never been sent. It has
zero sends, zero replies and zero positives, so **every row above that is about
outcomes is UNKNOWN for it**, and no estimate is offered. The only honest
statement of the gap: the new copy is better on the one axis the estate
measured a signal for (length), worse on the one axis the estate measured its
largest signal for (naming the prior channel), and unresolved on the rest.

---

## 11. What I would change, with the number beside it

Each of these is a direction with its `n`, not a settled rule. 26 positives is
a small number and §8 says 14 of them are misreadings.

1. **Fix the classifier before anybody optimises against the positive rate.**
   Precision 38.5% (10/26) by my read; 2 of 5 `referral` rows are
   out-of-office auto-replies; `confidence` is a per-class constant with zero
   within-class variation across all 899 and cannot filter anything. Until this
   is fixed, rank by the ordering (which survived the audit) and not by the
   rate (which did not).
2. **Close the reply-readability gap.** 899 of 1,894 replies are readable
   (47.5%), and 328's zero-positive result is 0 observed in 28.7% coverage with
   an upper bound near 10. Every per-step number in this file is a floor
   because of it.
3. **Name the prior channel when there is one.** 24 of 26 positives (92.3%)
   came from the one campaign that does, on 45.4% of sends. Confounded with
   length in this corpus and the confound is stated — but it is the largest
   association measured.
4. **Length is an OPEN QUESTION, not a recommendation, and this is the one
   number here that disagrees with the contract.** Cells that earned a
   positive: 32–108 own-text words, median 79 (n=7). Cells that did not:
   97–160, median 129.5 (n=22). The em1 contract set on 2026-10-03 is **90–140,
   target 120**, drawn from the operator's own 17 exemplars (114–133, median
   120.5, n=17 — reported by the lane that set it, not measured here).
   **Neither number is adjusted.** Different senders, different lists,
   different mailboxes; and the earning-cell figure is confounded with naming a
   prior LinkedIn touch, so in this corpus a short email and a
   channel-coordinated email are the same email. The exemplar range is what a
   human wrote and the operator endorsed; the 79-word median is what replies
   actually came back to. **The experiment that separates them**: 352's short
   question-led opener to accounts with no prior LinkedIn touch, against a
   120-word exemplar-shaped opener behind a LinkedIn touch, same mailboxes,
   same window, comparable lists. Until that runs, neither licenses changing
   the other.
5. **Ask for the short call in the opener instead of promising not to need
   one.** 352's call-ask opener: 0.0255 per 100 sent (24/94,004). 327+328's
   "reply yes, no demo call needed", present in 100% of 1,800 sampled renders:
   0.0023 per 100 sent (2/85,606). 11×, n=26.
6. **Spend the sequence budget on steps 1–2.** 21 of 26 positives (80.8%)
   arrive there on 37.7% of sends; steps 6–8 yield 1 positive in 31,861 sends.
   8.6× difference in positives per send.
7. **Assert that no merge token rendered empty, before send.** 8.89% of sent
   mail had one (73/821); 15.6% of the sends behind flagged replies did (5/32).
8. **Record the meeting, not just the invoice.** The business's best-performing
   engagement has 56 invoiced meetings over five months and **zero** of them
   joined to a channel, a campaign, a step or a reply (§9). That is why the
   cross-channel question cannot be answered today, and it is a ledger problem
   rather than a copy problem.
