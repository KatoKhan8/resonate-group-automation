# PLAYBOOK

The operating contract. What this engine will and will not do, in the order it
does it, written so a person who has not read the code can tell whether it is
behaving.

`BUILD-SPEC.md` is the design. This is the set of rules that outrank
convenience when the two disagree. Where a rule has a longer treatment
elsewhere, the link is given rather than the text repeated.

---

## 0. The one that outranks the rest

**Nothing in this build sends.** `push.run(live=True)` raises
`LiveSendNotEnabled`. No email, no LinkedIn message, no connection request, no
campaign launch, no Slack post, no mutation of an EmailBison or HeyReach
campaign. Every test runs offline against a cassette with the socket layer
blocked.

Turning that off is a deliberate, separate act with its own procedure:
`PILOT-PLAN.md`. It is not a flag anybody flips to see what happens.

This file is the rules. `OPERATOR-PLAYBOOK.md` is the sequence they govern -
create a workspace, qualify, enrich, verify, build, approve - and says which
of its eighteen steps work today and which are disabled.

`SLACK_LIVE` is the same kind of flag and has the same answer. Notifications
are routed, recorded, rendered and shown on screen; none is posted. The two
levels and the reasons they never mix are in `SLACK-NOTIFICATIONS.md`.

---

## 1. Company first, person second

The order is not a preference. Decision-maker enrichment is the first genuinely
expensive operation in the system, and running it before qualification means
paying to find people at companies that were never prospects.

    domains -> normalise -> dedupe -> suppress
            -> company facts -> qualify -> segment -> route personas
            -> plan the spend -> STOP
            -> a human approves
            -> person enrichment -> the ContactOut-first waterfall
            -> verification -> MX -> channel eligibility
            -> research -> drafting -> lint -> QA -> approval

The stop is the point. Everything before it is free and re-runnable; everything
after it costs money.

| Company outcome | Person credits |
|---|---|
| `qualified` | up to the tier cap |
| `review` | **0**, until a human decides |
| `rejected` | **0** |
| `unknown` | **0** — not knowing is not permission |

"Until a human decides" is now something a human can actually do.
`qualify.record_review` stores the decision and `/icp` is where it is made.
Two properties of it are not negotiable:

- **A review is of a verdict, not of a company.** It carries the inputs
  fingerprint the verdict came from, so it authorises nothing once the facts
  move — the same staleness rule the campaign and enrichment approvals use.
- **Accepting is weaker than rejecting.** A recorded `reject` blocks
  enrichment permanently, at any status, with no policy behind it. A recorded
  `accept` unlocks a company only where the client config opted in with
  `dm_plan.allow_review_enrichment`, and is otherwise recorded and inert. One
  reviewer with a browser does not get to widen what a client agreed to spend,
  and that flag is deliberately absent from the settings form for the same
  reason.

`dmplan.may_enrich()` is the single gate, and it refuses a rejected or review
company even when the batch approval is current.

Detail: `ICP-SEGMENTATION.md`.

---

## 2. Evidence discipline

**Missing information is never positive evidence.** A company with no employee
count does not get the benefit of the doubt on size. It gets a `missing` note,
its confidence drops, and the gap is listed in `missing_evidence`.

**Score and confidence answer different questions.** A low score on good
evidence is a *rejection*. A low score on no evidence is a *task*. They must
never share a bucket, because one is a decision and the other is work. A 90/100
built on two weak facts is not the same object as a 90/100 built on ten good
ones, and the engine is not allowed to pretend otherwise.

**Contradictions are surfaced, not resolved.** Where two stored facts cannot
both be true, the company keeps both, the confidence drops, and it can never be
reported as `high`. We usually cannot adjudicate; we can refuse to sound
certain.

**UNKNOWN is a real answer.** A company we cannot place is not "Other Agency".
Forcing a subvertical from one keyword is how a software agency receives copy
about creative retainers.

**Nothing specific is ever invented.** Every claim in a message must trace to
something on the record — `src/claims.py` enforces it. A dated fact with a URL
is evidence; a plausible sentence is not.

---

## 3. ContactOut first, and paid fallbacks need a reason

ContactOut is first at every stage where ContactOut can answer at all. Two
ContactOut calls in sequence are the primary path, not a fallback: what needs
justifying is *leaving* the provider we have already paid.

A step that leaves ContactOut must declare what has to be true to reach it, and
the reason must be one the stage names. Offering no reason, or an invented one,
is refused rather than logged.

    contactout_no_people          contactout_no_target_persona
    contactout_result_collision   contactout_rebrand_detected
    contactout_domain_unstaffed   contactout_incomplete
    contactout_missing_company_data   public_evidence_required
    contactout_no_company_linkedin    contactout_no_email_domain

The last two arrived with Blitz on 2026-09-08 and are not the same kind of
thing as each other. `contactout_no_company_linkedin` is a real miss:
ContactOut's `/domain/enrich` carries `li_vanity`, so it was asked and did not
answer. `contactout_no_email_domain` is a permanent gap: no ContactOut response
carries a mail domain under any spelling, so the question cannot be put to it
at all. Both must be stated before Blitz is paid, and the distinction matters
because a gap can never be closed by asking ContactOut again.

Every call is written to the record's waterfall ledger by the same closure that
charges for it, so the spend audit reads what actually happened rather than
what the policy hoped. `waterfall.audit(record)` names any step taken without
an accepted reason.

    python -m src.waterfall --describe
    python -m src.waterfall --record <id>

**Costs are real.** `people-count` is free; everything else burns credits. Cap
before you fan out, and cap against the *maximum* exposure, because that is the
number that can arrive on an invoice.

---

## 4. Apify is research, never sendability

Apify supplies public evidence and nothing else. It may improve ICP confidence,
vertical classification, company understanding and messaging evidence.

It may **never** make an address sendable. Verification is
`src/verification.py` and no other module decides it.

Scraped text is untrusted input that ends up near a model. It travels as
structured evidence with a URL, a date and a relevance score — never as prose.
A page saying "ignore previous instructions" arrives as a dated, attributed
fact scoring below the usable threshold: data with a score, not a line in a
prompt.

---

## 5. Persona routing

Searching the same titles everywhere is not merely ineffective. Each search is
a paid call, so a strategy that ignores size spends money looking for people
who do not exist.

Routing is chosen from the company's own band, vertical, business model and
tier. Five persona families: `founder`, `operations`, `finance`, `delivery`,
`resource_management`. Titles, band mapping and caps are all client
configuration, because Productive's ICP will change - and it can now change
from `/settings/personas` as well as in the file, because a change that has to
wait for somebody with filesystem access is a change that does not happen.
What a form may write is bounded: a persona needs at least one title, its cap
is between one and ten, and the whole set is refused rather than half applied.

Tier controls depth: A up to 3 contacts, B up to 2, C up to 1, review and
rejected 0. Configurable, and the caps bind before any fan-out.

---

## 6. Reachability is two verdicts, not one

| Situation | email | linkedin | mode |
|---|---|---|---|
| verified address, usable profile | yes | yes | multichannel |
| behind a high-protection gateway | no | yes | linkedin_only |
| no verified address, usable profile | no | yes | linkedin_only |
| verified address, no profile | yes | no | email_only |
| neither | no | no | **held**, never dropped |

**Nobody is dropped for losing one channel.** A contact blocked from email by
Proofpoint, Mimecast or Barracuda stays on the record and stays LinkedIn
eligible. Blocking suppresses the *channel*, not the person.

MX classification recognises gateways by label-boundary suffix match, never
substring. Mailbox hosts — Google, Microsoft, Zoho, Fastmail — are unblockable
even by category, because that is where most prospects keep their mail.

Every closed channel carries a stable code and a sentence a person can read.

---

## 7. Sendability

```
sendable = two independent providers confirmed it
       and verdict == "valid"
            or (verdict == "accept_all" and reoon.is_safe_to_send is True)
```

**One verifier is never enough.** `required_confirmations` is 2 by default and
counts *providers*, not calls: asking ContactOut twice is one confirmation,
because two answers from one source share whatever made the first wrong. A
catch-all is not a confirmation, an `unknown` is not an answer, and a provider
error is evidence of nothing.

MX screening runs before the first paid verifier call: a domain behind a
blocked gateway has its email channel closed whatever a verifier would say, so
buying that answer buys nothing.

Sendability is **recomputed from the evidence** on every ask. The stored state
is a cached opinion and it has no vote.

Detail, including the full agreement matrix: `VERIFICATION.md`.

Everything else is `held`, not dropped. Two providers disagreeing about an
address is a hold, not a resolution in our favour. DNS not answering is a hold,
never an assumption of safety.

**No email is generated for an unverified address.** **No draft ships without
passing `lint.py`.** **Never widen a lint rule to make a draft pass** —
regenerate the draft.

---

## 8. Local time

Timezone is a campaign field, not a display detail. An email that lands at
04:00 local is worse than one that never arrives.

- Stored as an IANA name (`Europe/Zagreb`), never a UTC offset. An offset is
  right for half the year, and the wrong half is the one nobody checks.
- Three fields travel together: `timezone`, `timezone_source`,
  `timezone_confidence`.
- Where a country spans zones and nothing narrows it, the timezone is `None`,
  scheduling is **held**, and the reason says so. **A guessed timezone is worse
  than a missing one**: a missing one stops the send, a guessed one sends
  confidently at the wrong hour.
- A step whose local date falls outside the configured sending days rolls
  forward and records that it rolled. Sending silently on the Saturday and
  silently dropping the step are both wrong.

    python -m src.schedule --demo

---

## 9. Approval gates

Two of them, and they are different.

**The DM plan.** Company analysis, then segmentation, then the cost plan, then
review, then approval — and only then is person enrichment eligible. The
approval carries a fingerprint of the qualification result it was given for, so
a stale plan is refused rather than allowed to approve something that changed
underneath it.

**The campaign.** Per-step human approval before anything is push-eligible.
Editing an approved draft moves its fingerprint and the approval no longer
applies; the record drops back from `approved` to `drafted` on its own. A
record-level `approved` state means "every sendable step here currently carries
a signature", and it is recomputed rather than latched.

A fingerprint the caller supplies is never trusted. The server recomputes and
compares. That is what makes "approve" mean "approve *this*".

---

## 9b. One conversation, not two channels

A prospect does not experience an email cadence and a LinkedIn cadence. They
experience seven messages from one company over three weeks, and the failure
they notice is the one no single-step check was looking for: the same sentence
in two places, an email arguing margin while the note argues capacity, or a
message arriving after they already replied.

`src/coherence.py` checks the sequence as a whole - duplicate argument across
channels, repeated opening, repeated call to action, contradictory angles, two
channels on one day, a step after the reply, a step on a closed channel. It
reports; `qa.py` is where a blocker becomes a verdict. Two copies of "may this
send" is the failure `eligibility.py` exists to prevent.

## 10. Replies stop everything

Any reply on either channel pauses **both** tracks for the **whole company**,
not just that person. Unsubscribes are honoured and stored.

Both providers return our own outgoing messages alongside real replies. Read
either naively and the engine pauses every company the moment it contacts them.
`src/adapters.py` allowlists what counts as inbound, and an unrecognised
classification is `unknown` — never `reply`.

Polling with durable cursors is the transport. Neither provider offers a
webhook we can verify, so an unsigned webhook is a hint to look now, never
evidence of anything.

---

## 11. No guessing, no silent drops

**Never delete a queue record.** Drop it with a reason. A rejected company
keeps its record, its score, its reasons and its evidence, so "why did we not
contact them?" is answerable a year later.

**No silent truncation.** A capped page says what it left out and where the
rest is. A preview showing the first two hundred of five thousand without
saying so reads as "this is all of it", which is a worse failure than being too
large.

**No invented metrics.** Planned, actual and unavailable never share a bucket.
`actual_credits` is `None` rather than `0`, because no provider in this stack
reports per-call spend, and a zero there reads as "we spent nothing".

**Provider modules return trimmed dicts, never raw payloads.**

---

## 12. Where the state lives

`work/queue.jsonl` holds record state; `work/campaigns.jsonl` holds campaign
state. Those two files are the only state, and both are touched through
`src/store.py` and nowhere else.

Record lifecycle: `queued -> enriched -> verified -> drafted -> approved ->
pushed`, with `dropped` and `held` as terminal branches.

Company qualification is a **substate** on the record
(`rec["qualification"]`), not a second top-level state machine — a company that
is `rejected` for ICP purposes is still a perfectly ordinary `enriched` record.
The vocabulary is in `dmplan.STATES`: `not_processed`, `company_enriched`,
`classified`, `review_required`, `qualified`, `rejected`,
`dm_enrichment_pending`, `dm_enrichment_approved`, `dm_enrichment_complete`.

Every stage is resumable. A batch that stops at company 2,731 restarts at
2,731, and a company whose inputs have not changed is skipped by fingerprint
rather than re-derived.

---

## 13. The documents

| Read this | For |
|---|---|
| `DEMO-OUTREACH.md` | one command, one page: what would actually go out |
| `VERIFICATION.md` | double verification: the matrix, the counting, the gate |
| `BUILD-SPEC.md` | the design, the data model, the traps found on real data |
| `ICP-SEGMENTATION.md` | qualification, scoring, segments, routing, DM planning |
| `PRE-PRODUCTION.md` | how to inspect a campaign before it runs |
| `PRODUCTION-READINESS.md` | what is ready, what is unproven, what does not exist |
| `PILOT-PLAN.md` | the first live send, when there is one |
| `WEB-READINESS.md` | the service boundary a UI would call |
| `REPORTING-READINESS.md` | what can be reported and what is external |
| `SCHEMA.md` | the record shape |
| `DATABASE-MIGRATION.md` | for when one writer stops being enough |
| `PERFORMANCE-READINESS.md` | measured behaviour at 5,000 domains |
