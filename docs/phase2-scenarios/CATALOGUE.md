# Phase-2 scenario catalogue — 30 rows

Thirty scenarios for the 90-day simulation. One row here is one `SNN.yaml` in
this directory; `README.md` states the shape precisely enough to author one
from this table alone.

**Scope.** Rule 2's five ordered lead classes (S01-S08), the reply classes that
carry a consequence (S09-S18), DNC (S19-S21), recontact windows (S22-S25),
bounce (S26-S27), unsubscribe (S28) and the cross-channel stop (S29-S30).

**`rule2_step` is a LABEL, not a code verdict.** Measured on `e967271d`:
`BLOCKED_FOREVER`, `ON_HOLD`, `COLD_LEAD` and `stari` each return **zero** grep
hits across `src/`. Rows carry the answer rule 2 *requires* beside the verdicts
the authorities that exist actually give. The `unimpl` column marks the rows
where those cannot agree today — **eight of thirty** — and that count is a
deliverable of this catalogue, not a caveat on it.

Every row: domain on `.invalid`, `synthetic: true`, `provider_writes: 0`.
Day offsets are simulated days, 0-90.

---

## Rule 2 — the five ordered lead classes

| id | intent | setup | event | expected | covers | unimpl |
|---|---|---|---|---|---|---|
| S01 | A removal request blocks the lead forever and stops both channels | OS campaign 491, 1 send, last touch day 3 | day 5, email reply: "please remove me from your list. do not contact me again" | `replies_classify: unsubscribe`, `accountpolicy_outcome: unsubscribe`, `channels_email_allowed: false` / `unsubscribed`, `channels_linkedin_allowed: false`, `cross_channel_stop: true`, `eligibility_verdict: blocked` / `blocked:unsubscribed`, `rule2_step: BLOCKED_FOREVER` | lead_class, reply_class, dnc, cross_channel | |
| S02 | A plain negative reply is terminal, and no later step is offered | OS campaign 491, 2 sends, last touch day 6 | day 8, email reply: "not interested, we have no requirement" | `replies_classify: negative`, `accountpolicy_outcome: negative`, `eligibility_verdict: blocked` / `blocked:replied`, `channels_email_allowed: false`, `rule2_step: BLOCKED_FOREVER` | lead_class, reply_class | |
| S03 | A hard bounce blocks the ADDRESS forever and does not suppress the account | OS campaign 492, 1 send, two contacts on the record, one verified | day 4, bounce on contact A | `channels_email_allowed: false` / `bounced` for A, `channels_email_allowed: true` for B, `eligibility_reason: blocked:address_bounced` for A, `hygiene_verdict: invalid_contact` for A, `rule2_step: BLOCKED_FOREVER` for A only | lead_class, bounce | |
| S04 | A lead inside anyone's LIVE campaign is ON HOLD, not blocked and not cold | no OS campaign; lead holds a row in campaign 352, status `active`, owner `resonate_internal` | `kind: none` | `collision_decision: hold`, `hygiene_verdict: active_conversation` OR `previously_contacted`, `eligibility_verdict: held`, `rule2_step: ON_HOLD` | lead_class | yes |
| S05 | A paused campaign whose rows are NOT terminal holds its leads, and a pause is not a close | lead holds a `sending_paused` row in campaign 503, status `paused`, owner `resonate_os` | `kind: none` | `collision_decision: hold`, `eligibility_verdict: held`, `rule2_step: ON_HOLD`, and the row records that only the operator formally closing 503 may change this | lead_class, recontact | yes |
| S06 | A lead OUR code contacted, 95 days cold, is a STARI LEAD for revival — and the two authorities for "how cold" disagree | OS campaign 491, 1 provider-confirmed send, last touch day -95 | `kind: none`, assessed on day 0 | `collision_decision: allow`, `rule2_step: STARI_LEAD`, revival eligible under `revival.DEFAULTS.cooling_days` = **90**, and the row records that **CLAUDE.md rule 2 says 30**. Classification only: no revival send without the operator's approval. | lead_class, recontact | yes |
| S07 | Manual history does not make a lead ours, so a never-OS-contacted lead is COLD however much manual history exists | no OS campaign, no provider-confirmed OS send; 4 manual touches, last on day -40 | `kind: none` | `collision_decision: allow`, `rule2_step: COLD_LEAD`, full new sequence, `eligibility_verdict: eligible`, **subject to a configured gap that does not exist** — see S25 | lead_class | yes |
| S08 | Provider truth that cannot be read is UNKNOWN, and UNKNOWN is BLOCKED — never cold, never revival | lead on a domain whose provider walk REFUSES (pagination incomplete) | `kind: none` | `collision_decision: unknown` raising `CollisionUnknown`, `rule2_step: UNKNOWN`, treated as blocked, `provider_writes: 0` | lead_class | yes |

## Reply classes that carry a consequence

| id | intent | setup | event | expected | covers | unimpl |
|---|---|---|---|---|---|---|
| S09 | A positive reply goes to a HUMAN and is never answered automatically | OS campaign 491, 1 send | day 6, email reply: "this is interesting, can you send some times for a call next week" | `replies_classify: positive`, `replies_confidence_at_least: 75` (**not `meeting_intent`** — measured, no rule in `RULES` returns it, so it needs a model call), `accountpolicy_outcome: positive`, account HELD, a notification at the alerting level, zero drafts sent | reply_class, notify | |
| S10 | An account-level "do not contact us" suppresses the whole ACCOUNT, not one contact | OS campaign 491, 3 contacts, 2 sends | day 7, email reply from contact A: "do not contact anyone at this company again" | `replies_classify: account_do_not_contact`, `accountpolicy_outcome: account_do_not_contact`, `channels_email_allowed: false` for **all three** contacts, `hygiene_verdict: suppressed_account`, `rule2_step: BLOCKED_FOREVER` | reply_class, dnc | |
| S11 | An out-of-office STOPS the contact exactly as a refusal does, and the return date is read but changes nothing yet | OS campaign 491, 1 send day 2 | day 3, email reply, `automated: true`: "automatic reply: out of the office until the 18th", `return_day: 18` | `replies_classify: out_of_office`, `accountpolicy_outcome: not_now`, contact `stopped` with reason `not_now`, `oooreturn_verdict: not_yet` / `NOT_DUE` on day 3 | reply_class, recontact | |
| S12 | "Try me later" and an out-of-office are different sentences and the same question | OS campaign 492, 1 send | day 10, email reply: "we are mid budget cycle, come back to me in the new quarter", `return_day: 60` | `replies_classify: not_now`, `accountpolicy_outcome: not_now`, `oooreturn_verdict: not_yet` on day 10, `due` on day 60 | reply_class, recontact | |
| S13 | A referral ROUTES to a new person and does not block the account | OS campaign 491, 1 send | day 5, email reply: "wrong person, speak to our head of operations instead" | `replies_classify: referral`, `accountpolicy_outcome: referral`, `hygiene_verdict: referral` / `hygiene_action: route`, account NOT suppressed, the named person is not contacted without a verification pass | reply_class | |
| S14 | "Not relevant to us" is a refusal and is not softened into unknown | OS campaign 492, 1 send | day 4, email reply: "this is not relevant to what we do" | `replies_classify: not_relevant`, `accountpolicy_outcome: not_icp`, `eligibility_verdict: blocked`, `rule2_step: BLOCKED_FOREVER` | reply_class | |
| S15 | A question is a live conversation, so it reaches a person and stops the cadence | OS campaign 491, 2 sends | day 9, email reply: "how would this work with the tooling we already run" | `replies_classify: question`, account HELD not suppressed, later steps not offered, a notification fires, zero automated replies | reply_class, notify | |
| S16 | An objection is neither a refusal nor a buying signal | OS campaign 491, 1 send | day 6, email reply: "we tried something like this before and it did not work for us" | `replies_classify: objection`, routed to a person, account HELD, cadence stopped | reply_class | |
| S17 | An assistant answering for somebody else is machinery, not the prospect | OS campaign 491, 1 send | day 3, email reply, `automated: true`: "i look after the diary, please send anything for her through me" | `replies_classify: assistant_redirect`, `accountpolicy_outcome: not_now`, cadence stopped, NOT read as positive | reply_class | |
| S18 | A one-word refusal is a refusal — TASK-939's regression, held down | OS campaign 491, 1 send; the reply arrives with an ordinary signature block | day 4, email reply whose entire human content is the single word "Stop", followed by a signature | `replies_classify: unsubscribe`, `replies_confidence_at_least: 95`, **NOT** `positive`, `rule2_step: BLOCKED_FOREVER`. Before TASK-939 this returned `positive 0.75` — a person asking to be left alone, announced as a buying signal. | reply_class, dnc | |

## DNC

| id | intent | setup | event | expected | covers | unimpl |
|---|---|---|---|---|---|---|
| S19 | An agency-wide DNC fingerprint blocks before a single credit is spent | the contact's fingerprint is already in the agency DNC with reason `requested`; no campaign | `kind: send_attempt` on day 0 | `eligibility_verdict: blocked` / `blocked:agency_dnc`, `hygiene_verdict: agency_suppressed` / `suppress`, zero provider calls, zero credits, `rule2_step: BLOCKED_FOREVER` | dnc | |
| S20 | A permanent operator exclusion survives everything, including a fact refresh | the domain is in `config/operator-exclusions.jsonl`; the record is otherwise a clean ICP fit with `medium` research | `kind: send_attempt` on day 30, after a research refresh on day 29 | `eligibility_reason: blocked:operator_excluded`, `channels_email_reason: operator_excluded`, still blocked on day 90, and only an explicit `lift` with confirmation changes it | dnc | |
| S21 | The client's own "no" is a different authority from ours and blocks just as hard | the domain is client-suppressed for workspace `demo`; no reply, no DNC | `kind: send_attempt` on day 0 | `eligibility_reason: blocked:client_suppressed`, `hygiene_verdict: suppressed_account`, `rule2_step: BLOCKED_FOREVER` | dnc | |

## Recontact windows

| id | intent | setup | event | expected | covers | unimpl |
|---|---|---|---|---|---|---|
| S22 | Inside the cooling window a revival candidate is held, and the hold has a measurable duration | OS campaign 491, last provider-confirmed touch day -45 | `kind: none`, assessed on day 0 then day 44 | held on both days, `rule2_step: ON_HOLD`, and the weekly HOLD report shows the duration growing from 45 to 89 days. A hold that never clears is a defect and is only visible as a duration. | recontact | yes |
| S23 | When the window closes the lead is CLASSIFIED and still not sent to | OS campaign 491, last touch day -46 | `kind: clock_advance` to day 45 | the cooling window closes on the simulated day the arithmetic says (46 + 45 = 91 days > 90), so the row must assert **which** of the two windows was applied — 90 from `revival.DEFAULTS` or 30 from CLAUDE.md — and that the verdict is CLASSIFIED, never a send | recontact | yes |
| S24 | The return date arriving means LOOK AGAIN, and never lifts the stop | the S11 state: contact stopped with reason `not_now`, `return_day: 18` | `kind: clock_advance` to day 18 | `oooreturn_verdict: due` / `BACK` on day 18 and after, the contact's `stopped` block **still present and unchanged**, `channels_email_allowed: false` until a person lifts it | recontact | |
| S25 | The gap a COLD LEAD is "subject to" does not exist, and the simulation must say so rather than pass | S07's state: no OS contact, last manual touch day -40 | `kind: send_attempt` on day 0 | `rule2_step: COLD_LEAD` with **`rule2_step_unimplemented: true`**. CLAUDE.md rule 2 requires "a configured gap since the last manual or internal touch"; `gap_days`, `min_days_since`, `min_gap` and `recontact_days` appear nowhere in `src/` outside reporting buckets. The simulation must name the code that actually decided. | recontact, lead_class | yes |

## Bounce

| id | intent | setup | event | expected | covers | unimpl |
|---|---|---|---|---|---|---|
| S26 | A bounce is re-derived from the event log on every read, not stored as a flag | OS campaign 492, 1 send, bounce recorded on day 4 | `kind: clock_advance` to day 5 | `channels_email_allowed: false` / `bounced` on day 5 and on day 90; and the row records that there is **no persistent `bounced` flag** — `channels._bounced` recomputes it, and for a period a bounce was read by no gate at all, so a bounced address was exactly as sendable the day after as the day before | bounce | |
| S27 | A mailbox over its bounce tolerance is withdrawn, and the estate shrinks mid-simulation | sender 2736 with `bounced_count` / `emails_sent_count` above tolerance in the census | `kind: clock_advance` to day 30 | the mailbox is not selected, the day's send plan shrinks against the forward book rather than the cap, and the weekly send-plan artefact shows it. **Derived input:** estate bounce rate 0.009792 (1,965/200,674) with a per-mailbox max of 0.054795 — see `config/simulation-assumptions-2026-10.json`. | bounce, scheduler | |

## Unsubscribe and the cross-channel stop

| id | intent | setup | event | expected | covers | unimpl |
|---|---|---|---|---|---|---|
| S28 | An unsubscribe arriving on LinkedIn must stop EMAIL too | enrolled on both channels: OS campaign 491 and a HeyReach sequence | day 12, LinkedIn reply via `heyreach`: "please take me off your list" | `replies_classify: unsubscribe`, `channels_linkedin_allowed: false`, **`channels_email_allowed: false`**, `cross_channel_stop: true`. A stop that reaches only the channel it arrived on is the defect this row exists to catch. | unsubscribe, cross_channel | |
| S29 | A negative EMAIL reply must stop the LinkedIn sequence, and the write door for that is measurably shut | enrolled on both channels | day 10, email reply: "no thanks, not for us" | local state blocks both channels and `cross_channel_stop: true`. **MEASURED ON `e967271d`, correcting an earlier note: both stop verbs ARE supported** — `providerwrites.EMAIL_STOP_LEAD` ("bison.stop_lead") and `providerwrites.LINKEDIN_STOP_LEAD` ("heyreach.stop_lead") are both in `providerwrites.SUPPORTED`, so the write door is open on both channels and the row must assert `provider_writes: 0` comes from the simulation's seal, NOT from an unsupported verb. Prove the stop through `bisonfactory.stage` and `heyreachfactory.ensure_leads`, **never** through `scripts/batch_linkedin_push.py`, which references none of the gates. | cross_channel, dnc | |
| S30 | A reply stops the steps already scheduled for the SAME simulated day | OS campaign 491, steps due on days 14 and 21, reply arrives on day 14 before the step is pushed | day 14, email reply: "please stop emailing me" | the day-14 step is not pushed, the day-21 step is never offered, `eligibility_verdict: blocked` for both, and the day's send plan shows the step withdrawn rather than sent. A reply that stops only FUTURE steps leaves the one already in today's plan. | cross_channel, scheduler | |

---

## How often each class actually occurs

Measured on the 899-reply corpus at the current rule hash
`rules-4+ca10b3cccdcb`, joined 899 of 899 to the enrichment that carries
persona and step. Full provenance and the durability warning are in
`config/simulation-assumptions-2026-10.json`; the figures are here because a
scenario author should know which classes carry the volume.

| class | n of 899 | share | scenario |
|---|---|---|---|
| `unknown` | 278 | 30.9% | none — deliberately; see below |
| `negative` | 209 | 23.2% | S02 |
| `unsubscribe` | 191 | 21.2% | S01, S18, S28 |
| `out_of_office` | 128 | 14.2% | S11, S24 |
| `not_relevant` | 30 | 3.3% | S14 |
| `positive` | 20 | 2.2% | S09 |
| `referral` | 15 | 1.7% | S13 |
| `objection` | 7 | 0.8% | S16 |
| `question` | 6 | 0.7% | S15 |
| `not_now` | 5 | 0.6% | S12 |
| `assistant_redirect` | 3 | 0.3% | S17 |
| `automated` | 3 | 0.3% | — |
| `account_do_not_contact` | 2 | 0.2% | S10 |
| `send_info` | 1 | 0.1% | — |
| `meeting_intent` | 1 | 0.1% | — |
| `neutral`, `interested` | 0 | 0.0% | — |

**Three facts a scenario author should carry from this.**

`unknown` is the single largest class at 278 of 899 and **no scenario covers
it**. That is on purpose: its consequence is that not one of those 278 reaches
a human, which is TASK-941's subject rather than a scenario's. But it means a
90-day run will route roughly a third of its replies nowhere, and that is the
system's behaviour and not a fault in these thirty rows.

**`positive` is 20 of 899 — 2.2% of replies.** S09 is the only row that
exercises the path a meeting comes down, and the whole meeting count of a
simulated funnel rests on that one rate. Section 5 of the brief says the
simulation may not claim what ninety days would EARN; this is the number that
makes that true.

**The persona split is real.** `out_of_office` is 25.3% of a champion's
replies (90 of 356) against 6.2% of an economic buyer's (30 of 484), and
`unsubscribe` runs the other way at 25.6% against 15.2%. Rows that set
`persona: champion` and rows that set `persona: economic_buyer` are not
interchangeable, and the assumption table carries the full cross-tab.

Human replies land at a **median 1.64h** from the step's send, with a p90 of
88h and a 62-day maximum; autoresponders land at a median of **0.01h**. A
scenario's `on_day` should respect that: an `out_of_office` arriving the same
simulated day as the send is realistic, a `positive` arriving within the hour
is the tail rather than the middle.

---

## Coverage check

| area | rows |
|---|---|
| rule 2's five lead classes | S01-S08 (8) |
| reply classes with a consequence | S09-S18 (10) |
| DNC | S19-S21 (3) |
| recontact windows | S22-S25 (4) |
| bounce | S26-S27 (2) |
| unsubscribe | S28 (1) |
| cross-channel stop | S29-S30 (2) |
| **total** | **30** |

Reply classes exercised: `unsubscribe`, `negative`, `positive`,
`account_do_not_contact`, `out_of_office`, `not_now`, `referral`,
`not_relevant`, `question`, `objection`, `assistant_redirect` — **11 of the 17**
in `replies.CATEGORIES`.

The six not exercised, and the reason is measured rather than chosen. Of the 17
categories, only **13 are returnable by any rule in `RULES`**; the four that are
not are `neutral`, `interested`, `meeting_intent` and `unknown`. `unknown` is
the no-rule-matched default and `classify` does return it, but `neutral`,
`interested` and `meeting_intent` **require a model call**, so a rules-only
simulation cannot produce them at all and a scenario asserting one would be
asserting something about the model. `send_info` is rule-returnable but carries
no consequence these rows test. `unknown` is deliberately not a scenario: it is
the largest real class at 278 of 899, and its consequence — that not one of
those 278 reaches a human — is TASK-941's subject rather than a scenario's.
`automated` is covered through `assistant_redirect` and `out_of_office`, the two
automated categories that do carry a consequence. `wrong_person` and
`left_company` are `accountpolicy` outcomes rather than classifier categories
and arrive through S13's referral path.

**Eight rows carry `rule2_step_unimplemented: true`: S04, S05, S06, S07, S08,
S22, S23, S25** — the eight marked `yes` in the `unimpl` column above, and no
others. That is the single largest gap this catalogue surfaces: rule 2 is a
permanent operator rule, and eight of thirty scenarios cannot assert it against
any module because no module computes it.
