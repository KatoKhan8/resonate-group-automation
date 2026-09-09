# Seeing a campaign before it exists

One command, one page, five contacts, and an answer to the only question that
matters before sending is switched on: **what would go out, to whom, saying
what, and why?**

    py -m src.demo_outreach

That writes `out/demo-outreach.html` and prints a summary. It makes no network
call, spends no credit, runs no model, starts no Apify actor, and posts to
nothing. `would_send` is 0 and a test asserts it.

Open the file in a browser. It is written for somebody who has not read the
code.

## The five contacts, and why these five

Between them they cover every path a real batch takes.

| | Scenario | What it proves |
|---|---|---|
| **A** | Harborlight Studio — full multichannel | the happy path: both providers receive this contact, both payloads are shown |
| **B** | Ironbridge Consulting — LinkedIn only, MX | the address verified *and* the domain sits behind Proofpoint. Email closes, LinkedIn does not, the contact stays |
| **C** | Saltmarsh Design — LinkedIn only, no address | a catch-all that Reoon would not clear. Email closes for a completely different reason, and the contact still stays |
| **D** | Quarrystone Engineering — email only | no usable profile, so HeyReach never sees them. EmailBison still does |
| **E** | Wintergreen Partners — reply, then pause | a reply on day 5 stops every later step on **both** channels, and deletes nothing |

B, C and D are three different reasons for a lost channel and one identical
consequence. That is the invariant worth seeing on a page, because *held, not
dropped* is easy to say and easy to get wrong.

## What is real and what is fictional

This distinction is the whole value of the page, so it is worth being exact.

**Fictional — the inputs.** Five companies, five people, their addresses,
their LinkedIn URLs, their MX hostnames, their evidence and the two generated
emails. Every domain is `.test`. No real person or company appears anywhere,
and `tests/test_fixture_hygiene.py` keeps it that way.

**Real — everything done to them.** Every verdict on the page came out of the
production function that would decide it in a live run:

| On the page | Produced by |
|---|---|
| ICP score, tier, confidence, contradictions | `icp.score()` |
| vertical, band, region, timezone | `segments.classify()`, `geo` |
| persona and target titles | the client config's own persona block |
| MX provider and category | `mx.apply_to_record()` → `mx.classify()` |
| email / LinkedIn eligibility and mode | `channels.evaluate()` |
| sendability | `verification.is_sendable()` via `lint.sendable()` |
| the seven-step timeline and every status | `cadence.build()` |
| lint on both channels | `lint.check_step()` |
| per-step eligibility | `eligibility.decide()` |
| personalisation band and its five components | `quality.assess()` |
| duplicate email steps | `duplicates.for_contact()` |
| cross-channel coherence | `coherence.for_contact()` |
| campaign QA verdict | `qa.report()` |
| step approval and campaign approval | `approve.approve_record()`, `orchestrator.decide()` |
| **the EmailBison and HeyReach payloads** | `push.collect()` → `push.payloads()` |
| local send times | `schedule.for_batch()` |

The payload row is the one to be most careful about. The page does not draw a
payload that looks like what the sender would build — it calls the sender's own
`push.payloads()` and prints the dict. A test asserts that, because a payload
the demo shapes itself is a payload nobody has tested.

**The one substitution.** DNS. `demo_outreach._resolver` returns MX hostnames
from a table instead of asking a resolver, so `mx.classify()` does the real
work on real hostname shapes — `mx1.…pphosted.com` really is recognised as
Proofpoint by the production classifier. Only the lookup is replaced, and an
unknown domain raises rather than returning nothing, because "no answer" and
"no MX" are different facts.

## Why the demo approves its own campaign

A campaign nobody has approved has every step `held: campaign_not_approved`,
which renders an empty EmailBison payload and teaches the reader nothing. So a
fictional approver signs a fictional campaign, through `approve.approve_record`
and then `orchestrator.decide` with the fingerprint it was issued for — the
same call the Slack button makes. `demo.yaml` names `U0DEMOADMIN1` as its only
approver, so the permission check is exercised rather than bypassed, and a test
asserts an unpermitted actor is refused.

Order matters, and it is the documented one: **steps first, campaign last.**
`campaigns._step_material` puts each step's `approved` flag and each record's
`paused` flag into the campaign fingerprint, so anything that moves either has
to settle before the campaign is signed or the signature is stale the moment it
is given.

## How the demo maps to the Campaign Review screen

Each contact card is the screen, section for section. A web version would
render the same ten blocks from the same `gather()` return value — the page
takes no data the JSON does not carry.

| Card section | The question it answers | Service call |
|---|---|---|
| 1 Why this company | Would I target them? | `icp.score`, `segments.classify` |
| 2 Why this person | Is this the right person? | the persona plan |
| 3 Contact and verification | Can we reach them, and how do we know? | `channels.evaluate`, `mx`, `verification` |
| 4 Research and evidence | What do we actually know? | `rec["research"]` |
| 5 Personalisation strategy | Is this specific or is it filler? | `quality.assess` |
| 6 Full outreach | Would I send this? | `cadence.build` |
| 7 QA and coherence | Does it hold together across channels? | `coherence`, `duplicates`, `lint` |
| 8 EmailBison payload | What exactly will Bison receive? | `push.payloads` |
| 9 HeyReach payload | What exactly will HeyReach receive? | `push.payloads` |
| 10 Events and pause | Has anything happened since? | the record's event log |

`WEB-READINESS.md` carries the HTTP surface. Nothing new is needed for this
screen: `demo_outreach.gather()` is the shape a `GET /api/campaigns/{id}/review`
would return.

## Cross-channel coherence

`src/coherence.py` was added for this page and is a production module, not a
demo helper. It answers a question no existing module was asking: **do this
contact's email and LinkedIn steps read as one conversation?**

Three modules each checked part of it. `duplicates.py` compares emails to
emails and filters to `channel == "email"`, so a LinkedIn note making the
identical argument to day 1's email had never been compared to it.
`cadence.cross_channel_leaks()` catches a step that *names* the other channel,
which is one specific leak. `eligibility.decide()` judges one step with no view
of the sequence around it. The prospect experiences none of those — they
experience seven messages over three weeks.

Seven checks, each naming the two steps it is about:

- `duplicate_across_channels` — the same argument on two channels **(block)**
- `repeated_opening` — two steps opening with the same words *(review)*
- `repeated_cta` — the identical ask, word for word *(review)*
- `contradictory_angles` — one person approached on two angles *(review)*
- `two_channels_one_day` — BUILD-SPEC §7's rule, re-checked after expansion **(block)**
- `scheduled_after_reply` — a live step after the prospect answered **(block)**
- `ineligible_channel` — a live step on a channel that is closed **(block)**

It reports and never blocks: `qa.py` is where a blocker becomes a verdict. Two
copies of "may this send" is the failure `eligibility.py` exists to prevent.

## Bugs this page found in the real engine

Building it against the production path — rather than around it — surfaced
four. All four are fixed in the engine, not worked around in the demo.

**1. `cadence` read a stored flag where everything else recomputed.**
`status_for()` gated the email channel on `contact.get("sendable")`, the
projection SCHEMA.md warns about by name, while `channels`, `eligibility` and
the payload gate all asked `verification.is_sendable()`. A stale `True` reached
`push.collect()` and died on an assertion at payload-build time; a stale or
absent `False` silently blocked a contact that had cleared verification. The
second is what the demo hit. A test asserted the old behaviour, so it had been
green the whole time.

**2. EmailBison never received `contact_key` or `client`.**
`adapters.from_emailbison` has always read all three identifiers back off an
inbound reply, and `bison.build_leads` only ever wrote `record_id` — so two of
those branches could not fire, and a reply could name the company it came from
but never the person. EmailBison's custom variables are the mechanism the
client's own cadence already relies on, so this one genuinely round-trips.

**3. HeyReach never received them either.** Same shape.
`adapters._heyreach_event` reads `record_id` and `contact_key`;
`heyreach.build_lead_pairs` wrote only the note. Sending them does **not** make
them a correlation key — confirmed live on 2026-08-26, HeyReach returns
`customFields: []` on every conversation, so the canonical profile URL remains
what replies are matched on and `src/linkedin.py` remains load-bearing. What it
buys is smaller and still real: a person looking at a lead in HeyReach's own UI
can see which record it came from.

**4. The demo fixture's day 1 and day 15 emails were identical.** BUILD-SPEC §7
asks for "a different angle from day 1". `duplicates.py` had always caught it;
nothing had ever looked. The new demo writes two genuinely different openings
and a test asserts they do not overlap.

## What is simulated rather than production-real

Stated plainly so nobody mistakes the page for evidence it is not:

- **The reply.** A local event applied through `replaysim.simulate()`, which is
  the production rehearsal path. No provider was contacted and no provider
  state was read.
- **The two sent steps in scenario E.** Marked through `push.mark_pushed()`,
  which writes the same push id and event a real send would. Nothing left the
  process.
- **The generated copy.** Written into the fixture rather than produced by a
  model, because this command must not call one. Its *shape* follows the
  drafting prompt's contract in BUILD-SPEC §8, and it is linted by the real
  linter like any other draft.
- **DNS**, as described above.
- **The evidence.** Fictional facts on `.test` URLs, built through
  `evidence.make()` so the scoring, freshness and relevance are real.

## What is still unvalidated against live providers

Unchanged by this work, and repeated here because the page might otherwise
suggest more confidence than exists:

- **No send has ever happened.** `push.run(live=True)` raises
  `LiveSendNotEnabled`. The payloads are built and displayed; nothing posts.
- **Adding a HeyReach lead is a mutation and has never been performed.** The
  identity reasoning above is reasoning, not observation.
- **Provider rate limits** are respected as documented and have never been hit.
- **Reply volume at scale** has not been exercised against live pagination.
- **Deliverability** is outside this system entirely.

## What still blocks production sending

`PILOT-PLAN.md` is the procedure. In short: sender warmup confirmed
independently, a real EmailBison campaign created and mapped, twenty contacts,
email only, a QA report with no BLOCK, a current campaign approval, and
somebody watching. The QA verdict on this demo is deliberately **BLOCK** — it
contains a paused company and a contact whose address never cleared
verification, and a QA gate that passed that would be the bug.

## Commands

    py -m src.demo_outreach                  # write out/demo-outreach.html
    py -m src.demo_outreach --json           # the same data, unrendered
    py -m src.demo_outreach --reveal-emails  # unmasked (they are fictional)
    py -m src.coherence --record harborlight # cross-channel check, one record
