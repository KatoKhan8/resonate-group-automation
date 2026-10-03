# Operator decisions, with the date and the reason

Every decision Zvonimir has made that governs what this system does, newest
first. A decision is recorded here when it is made. A decision that is later
superseded is **marked superseded in place and kept**, because the most
expensive thing in this repository has been acting on a rule that had already
been withdrawn.

The standing RULES derived from these live in `CLAUDE.md` and
`docs/OPERATING-MODE.md`. This file is the decision itself: what was decided,
when, and why.

---

## 2026-10-03, evening

**`needs_a_person` maps to `reply` in `ENGAGEMENT_SIGNAL`, never
`positive_reply`.** Reason: it would inflate the metric just made primary, on a
classifier measured at 38.5% precision on `positive` in email. The lane that
implemented it added a second reason worth keeping - **not `meeting` either**,
because `ENGAGED_MEETING` is labelled "Meeting booked" and has exactly ONE
writer, an `events.MEETING_MARKED` entry, while `needs_a_person` collapses
three classifier categories (`question`, `meeting_intent`, `interested`). One
outcome carrying three readings may only assert their coarsest shared truth,
and asserting a booked meeting from "can you handle multi-currency invoicing?"
is a claim the event log does not support.
**And `test_signals` would NOT have caught a wrong mapping**: with
`needs_a_person -> positive_reply` it reports 95 tests OK. The decision is
pinned in the lane's own module with `not positive_reply` and `not meeting` as
named assertions.

**The third channel, decided: an enum of `call` and `whatsapp`, with events
`touch_attempted` / `touch_completed` / `reply`, recorded BY HAND, and counted
as a Resonate OS touch ONLY if they are in the ledger.** That last clause is
the attribution rule restated for a channel a person operates: a manual call is
not OS contact unless the ledger positively records it, which keeps the
five-step lead classification intact - absence of a record stays a refusal and
never becomes a revival lead. TASK-1001 carries the measurement that made this
necessary: `channels.MODES` knew two channels and no module under `src/` knew
`phone`, `call` or `whatsapp`.

**USD per credit for Deliverable and Reoon: tomorrow.** Batch 3 of verification
(483 contacts, up to 1,311 credits) stays unrun until it is priced, because a
cap that cannot be evaluated is not a cap.


**The 15-to-60 reply range is ABOLISHED. em2 and em4 are 45-90, from
`WORD_CONTRACT`, and the test changes with them.** One authority. Reason: the
copy lane deleted the duplicate CONSTANTS this morning but kept the band,
because the night's instruction named only em1 — and CLAUDE.md's TASK-943 line
had said the range was abolished, which is wider. The operator has now closed
that gap in the wider direction: `test_the_band_itself_is_unchanged` is the one
line to change, and it changes.

**Gold set, two rulings that move the defensible count:**
- **a price or what-is-it question COUNTS as positive**;
- **interest with a later date COUNTS as positive, flagged `later` and
  carrying the date.**
Both came from the 32-row sample in `resonate-ops/copy-review/`, where the
measured precision was 10 of 26 defensible (38.5%), or 12 of 26 (46.2%) with
deferred interest. These two rulings take it to the upper figure and give the
`later` cases a flag rather than a judgement.

**The unpruned rejection ledger gets its own branch, BEFORE phase 2 and NOT
before the canary.** Measured: the reason list fed to writer retry 9 is
byte-identical to retry 1 — ten items, nine from attempt 0 — so the model is
told nine times to remove a phrase it removed on the first retry while the one
live complaint is buried. Nine model calls per refused draft. It is a spend and
a generation defect, and it is not on the canary's path.

**The queue is fixed and the order is not to be re-derived**: master suite →
P0 (TASK-1004) → guard. When P0 and the guard are on master: **phase 0 on
savagebrands — five generated emails, the copy-review file, the Slack output —
and GENERATION DOES NOT WAIT for the operator's approval. Approval is for
sending only.** Then phase 1.

---

## 2026-10-03

**The em1 contract is (90, 120, 140).** Reason: measured against the operator's
own 17 em1 exemplars — excluding the signature block, 16 of the 17 span
**114–133 with median exactly 120**, so the band and the target are their real
copy rather than a guess. This retires A21, the collision with `WORD_CONTRACT`'s
em1 ceiling of 90, which intersected the new band at exactly one legal value.
`n = 17` bodies, measured with `lint.countable_words`, 2026-10-03.

**`client_approved: true` is backfilled on `OFFER-A-ECONOMIC-BUYER` and
`OFFER-B-OPERATIONS`**, approver Zvonimir, date 2026-10-03. Reason: the field is
new and only `OFFER-GIVE-001` carried it, so a gate keyed on
`client_approved is True` would have held **all nine offers**, including the two
live spines in `messaging_rules`. Absence must not be allowed to decide a gate
by omission. `n = 9` offers read with `offers.load()`.

**TASK-967 proceeds: the prior-contact dossier is wired into the copy path, with
a per-contact cache, and no provider id means UNKNOWN.** Reason: the first-touch
licence is currently decided by a boolean derived from a local event log that
carries one confirmed touch across 1,582 records.

**943 merges once the four keyless doors have tests.** Reason: `approve`,
`eligibility`, `executionguard` and `campaigns` call `lint.check` with no step
key, and the only test that drove that path was deleted. Measured 2026-10-03:
each of the four doors could be switched off with the pre-existing 53 tests
**completely green**.

**The guard branch is fixed and then gated**: TASK-973 through `--git-common-dir`,
TASK-974 by deleting the stale attestation. Reason: its GLM FAIL rested on a
refuted mechanism, a gate defect, and one real stale file.

**The provider stop stays BEFORE classification. The operator's own earlier
instruction — "unknown calls nothing but raises a notification" — FALLS.**
Reason: the stop is a safety REDUCTION; attempting it before classification can
only mean somebody receives less, and implementing the instruction would send
MORE to a person who replied and whose reply we could not classify. The
notification half is genuinely missing and stays open (A8 / TASK-941).

**Today's success measure: how many canary-minimal-path branches are on master
by evening, and whether phase 0 ran. Everything else is secondary. If the
minimal set is not merged by 18:00, parallel work stops and every resource goes
to that queue.**

**Verification is a pipeline step, not a manual act.** Verification calls to
Reoon or Bison verify are **allowed and are not a provider write**, because they
never touch a prospect. Every call goes into the spend ledger with its price.
**`catch_all` is HOLD** until the operator decides otherwise. Reason, measured
2026-10-03: of 1,381 contacts, 709 are sendable and **zero reach ALLOW** — 485
are `verification_not_sendable` and 599 of the sendable are
`held:approval_stale`. Verification was the first gate savagebrands failed
(`held:verification_unknown`, provider `status: unverified`).

**Phase 2 expands to 300 synthetic accounts, 900 DMs, eight cohorts
proportionally, and a clock running day 0 to day 120.** All 30 catalogue
scenarios fire during the run, each at least three times on different accounts
and different days, each with a verdict set in advance. A scenario that does not
match, or that is more than 15 minutes late, is a TASK; "the rule does not
exist" is a TASK with a proposal and goes to the operator. Cost cap **80 USD**,
copy generation on a stratified sample of 90 DMs with the rest templated,
attributed to the task. The report carries one line verbatim: *"ovo kaže što
sustav radi 120 dana, ne što bi zaradio; svaki odgovor je iz stope, ne iz
tržišta."*

**The copy engine learns from the prior campaigns, and nothing enters the
exemplars until the operator has read it.** EmailBison: all 20 OS campaigns'
`sequence_steps` and all 899 readable replies. HeyReach: **all 121 campaigns on
the seat** — 40 ours, 5 the client's, 76 of unknown owner — learning from all of
them while **marking ownership by the authority and never changing it**.
Numbers come from the stats endpoint with `startDate`/`endDate`, never
`timeFrom`/`timeTo`, which is proven to ignore the window and return lifetime.
Replies that cannot be joined to a campaign stay `unknown campaign` and are
never attributed on a guess.

**The second brain is permanent**: `docs/second-brain/` with `linkedin.md`,
`email.md`, `scenarios.md`, `defects.md` and `decisions.md`; every line carries
source, date and `n`; updated at each finding, never retroactively; the writer
reads only approved exemplars from it, never the syntheses, until the operator
approves. The weekly handover carries a "what is new in the second brain"
section.

**Qwen is re-enabled, with a new pattern**: the first line of every brief is
"write REPORT.md now, empty, then fill it in"; one deliverable per task; Claude
commits the result. Suitable work: the 30 scenario YAML files, the 16
anonymised em1 exemplars from the `.eml` files, handover tables, the
`client_approved` backfill, clearing stale attestations. `qwen3.8-max` at night,
`3.7-plus` by day. It must not touch `src/`, `tests/`, `work/` or
`config/.env`. **If it returns nothing again, it is switched off and that is
recorded.**

**GLM runs multi-part on every branch before a merge, and on every Qwen commit
before it is taken over.** The test-step budget is set by measurement, not a
round number. Spend is attributed to the task. **A NEEDS_CLAUDE caused by the
tooling is fixed in the tool and never bypassed.**

**Up to four parallel Opus lanes, and at most one full suite at any moment.**
Lanes waiting for the suite queue and start nothing that binds loopback.
**Worktree names stay neutral** — no `glm`, `test` or other allowlist token —
until A44 is on master.

---

## 2026-10-02

**The writer contract is the only authority for a body's word count** (TASK-943).
The 15-to-60 thread-reply range is abolished. Reason: two authorities for one
number intersected to exactly ONE legal length for em2, which is an equality and
not a threshold.

**Attribution and suppression are two separate questions.** Attribution reads
the OS authority only. Suppression reads every known provider touch whoever made
it. The figures are config, not constants.

**Every merge is gated against a reference on the current master, and one run
can serve as both** — but the emptiness of `git diff master <branch>` is proven
every time, never assumed. Reason: a reference bound to something that can move
is not a reference.

**Every merge goes through GLM first, and NEEDS_CLAUDE or UNKNOWN does not
pass.** A FAIL does not pass either.

**At most one full suite runs on this machine at a time.** Reason: six
concurrent `tests.offline` workers made every run look stalled, cost 3h42 of
waiting on a merge verdict that was only contending, and no result from any of
them was trustworthy.

**Model spend is attributed to a client or a task, never left unattributed.**

**The step-objectives ladder is a ladder of ROLES, not of words** (TASK-964):
em1 the offer, em2 a smaller tangible piece of the same offer, em3 proof with a
named client and a number, em4 an easy-answer question with an explicit exit,
em5 a breakup in a new thread. Four refusals follow.

**A give-first offer is recorded as data with `client_approved: false`** — the
writer may generate with it in sandbox and copy-review, but eligibility holds it
until the client confirms. Generation is allowed; sending is held.

**`#resonate-os-output` has standing permission, no per-post approval**: every
generated copy in full with per-step word counts, every classified reply with
its text and verdict, DNC changes, and the campaign plan when one exists.
Engineering status stays in `#resonate-os` and only with the operator's
approval.

**Qwen's 100%-utilisation order is REVOKED.** Idle workers are fine; the
critical path is Claude subagents. (Superseded in part on 2026-10-03, which
re-enables Qwen for file-shaped work under a new pattern.)

---

## 2026-10-03, evening — five rulings

Given in response to lane 3's three questions and lane 4's measurements. Each
is recorded with the reason the operator gave, not a paraphrase of the effect.

**1. "A question about the offer" SPLITS, and the split is the ruling.**
*Broad* — any question about the offer — reaches a human as
`needs_a_person`. *Narrow* — price, how it works, a demo — **counts toward
the metric**. This settles the limb that lane 3 measured at 10 against 7 and
rejects both single answers: routing everything to a person and counting
everything as positive are each wrong in a different direction.

**2. An objection citing a past failure is the `objection` class, routes to
`needs_a_person`, and is NOT `negative`.** "We tried this before and it did
not work" is a conversation that has started, not a refusal. Note the
consequence the operator accepted: `objection` resolves to UNKNOWN today, so
this ruling is only real once `objection` carries a policy of its own.

**3. An EA redirect HOLDS the cadence for that person AND raises a referral
to the person named — the same treatment as `wrong_person`.** Lane 3
recommended this as the only option where the hold cannot become invisible.
Volume measured at 3 in 899.

**4. The output channel is its own destination.** `SLACK_OUTPUT_CHANNEL` in
config, `notify.output_channel()`, and phase 0 posts there explicitly.
**Never a fallback to the ops channel for the output stream** — the reason
being the 2026-09-27 incident that retired `#resonate-notifications`, and
that a room receiving both alerts and generated copy is a room that gets
muted. `#resonate-os-output` is `C0C6DES2L7L`.

**5. The LinkedIn char constants are REPLACED by the measured contract.**
`NOTE_MIN_CHARS`, `MESSAGE_MIN_CHARS` and `MESSAGE_MAX_CHARS` give way to one
authority in the same shape as the email word contract: li2 100-299 with a
target of 125, li1 with **no floor while it is UNKNOWN** and a measured
ceiling of 179. The operator accepted lane 4's refutations: a 40-character
note floor would refuse the best-accepting note in the estate, and a 1900
ceiling has never bound anything.

**And the em1 ruling that re-ordered the night:** `task-copy-exemplars`
merges BEFORE phase 0. Generating under master's `(60, 75, 90)` would
"return the old shape, which is exactly what we rejected yesterday." It costs
one suite and is worth it.

---

## 2026-10-03, late evening — HeyReach, and the cost rules

### Costs

**Verification credits are AUTHORISED WITHOUT A PRICE.** Reoon and Deliverable
do not count against any cap and do not block. Authorised by the operator,
Zvonimir, on 2026-10-03. GO item F1 is amended to say exactly that, naming
who authorised it and when, rather than refusing a run because
`USD_PER_UNIT['credits'] is None` — which was true, and was the operator's own
open decision 1, and is now answered by authorisation rather than by a price.

**The only hard cap is OpenRouter: 50 USD for the night**, `BudgetExceeded`
fail-closed, shared across the email and LinkedIn lanes, with the running
total written into the handover every 90 minutes. **At 40 USD generation
stops**, the draft is filled with whatever is finished, and the number of
missing accounts is recorded.

**Apify is spent as research needs it, but every call lands in the ledger with
a price.**

### HeyReach — three rulings

**1. OWNERSHIP: a fourth class, `resonate_manual`.** Every campaign on the
Productive workspace that the OS did not create is `resonate_manual` — **not
`unknown`, not `client`**. The ownership classifier gains that class.
- Attribution: a `resonate_manual` campaign is **not an OS touch**.
- Suppression: **membership without a reply does not block. A reply blocks.
  An active sequence on any campaign is HOLD until it ends.**
- `our_heyreach_campaign_ids` remains the authority for what is OS.

This retires the reading in which an unrecognised campaign made its members
untouchable: the question is no longer "is this campaign ours" but "is there
a reply, and is there an active sequence".

**2. SEATS: all ~30 Productive profiles are available.** Every seat the OS
uses must carry a roster row `li-<seat>` joined to an `hr-` attestation of a
named person — **the li/hr join is fixed and is 32/32, and those rows get
written**. A seat without attestation is **NO-GO for that seat, not for the
batch**. The LinkedIn sender need NOT be the same person as the email sender
to the same account, but **must** be the seat's owner, and the note and
message are signed with the profile owner's name.

**3. ALLOCATION AND CAP, from provider measurement.** Measure each seat's
spend TODAY at the provider — connection requests, messages, cooldown, manual
campaigns `IN_PROGRESS` — and distribute the 20 candidates to the seats with
the most free headroom. **At most 5 requests per seat per day in the pilot**,
never above HeyReach policy of 30, and never above the provider's actual
measured headroom. **A seat in cooldown, or with `authIsValid` false, drops
out.**

The morning checkpoint carries a table: seat, owner, today's spend, assigned
candidates, note.

### Personalisation is a condition, not an option

Every account — email and LinkedIn alike — must carry **at least two research
rows with `source_url` and `retrieved_at` before generation**, or it is HELD
`research_required` and does not enter the campaign. Canonical research
(webfetch, honest UA, robots.txt) comes first; **Apify only as a fallback
through `research.py`, fail-closed on robots, never `src/providers/apify.py`
directly**. Sources in priority order: the agency's own site, the company's
LinkedIn, public news. The fact carried in em1 must be **fresh within twelve
months** and verifiable, and the claims gate stays.

**The second brain supplies STRUCTURE, never FACTS.** Exemplars, the role
ladder, the contract and what precedes a positive reply reach the writer
through `WRITER_SYSTEM`. Facts about a prospect come only from research rows —
never from the second brain, never from the model.

**If research finds nothing usable for an account, that account drops out and
the count falls. The threshold is not lowered.**

### Two GOs, and what tonight may not do

**EMAIL GO and LINKEDIN GO are separate written approvals**, each naming the
exact recipient, sender and campaign; the LinkedIn GO also lists the seats.
Neither implies the other. Tonight may reach a DRAFT and a checkpoint on both
channels and may go no further. **The only stop conditions overnight are the
cap, the account ceiling, and a red item on the GO checklist**; everything
else is recorded and the work continues.

---

## Earlier

The 2026-09-15 autonomous production grant, the 2026-09-26 production freeze,
the 2026-09-27 licence decision on `CLIENT_SUPPLIED` versus `CLIENT_APPROVED`,
the 2026-09-28 pause of 487/489/493 with its recorded reason, the 2026-10-01
declaration of 274/327/328/352 as internal and the five-step lead
classification, and the 2026-09-24 decision that **there is no unsubscribe link
in any campaign — the opt-out mechanism is the REPLY** all live in
`CLAUDE.md` and `docs/OPERATING-MODE.md`, which remain the authority on the
rules they produced. They are named here so this file is not read as the
complete list.
