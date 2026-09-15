# Relationship State in the Estate — 2026-09-15

**Snapshot:** `work/queue.snapshot.jsonl`
**Stamp:** `2026-09-14T21:52:15Z from master 0ac5e60 300 records`

## The estate at a glance

| Metric | Count |
|--------|-------|
| Records | 300 |
| Records with contacts | 77 |
| Records with no contacts | 223 |
| Total contacts | 92 |
| Contacts with `bison_lead_id` | 29 |
| Contacts with `push_marked` events | 1 |
| Contacts with reply events | 0 |
| Contacts with LinkedIn connection events | 0 |

This is a pre-send estate. Of 92 contacts, exactly **one** has a `push_marked`
event (email channel, `hotsoupgroup-com/hussein-samnani`). Zero contacts have
reply events, LinkedIn connection events, or LinkedIn sends in the event log.
The relationship states the task asks about are almost entirely **theoretical**
at this snapshot — the data to distinguish them does not yet exist because
almost nothing has been sent.

---

## 1. Relationship states: counts and evidence

### State: previously emailed, no reply

**Count: 1** (hussein-samnani at hotsoupgroup-com)

**Evidence:** `events[type=push_marked, channel=email]` for this contact, with
no `reply_received` / `reply_classified` / `positive_reply_detected` event.

This contact also carries `bison_lead_id=203657`, so the estate flags them as
"prior EmailBison outreach" — but the prior outreach is not visible as events
in this estate's log. The `bison_lead_id` is a provider-side fact, not an
event-log fact.

### State: previously emailed, replied NEGATIVE

**Count: 0**

**Evidence required:** `events[type=reply_classified]` with classification in
`{negative, unsubscribed, not_interested, remove, removal}`. No reply events
exist anywhere in the snapshot.

### State: previously emailed, replied POSITIVE

**Count: 0**

**Evidence required:** `events[type=positive_reply_detected]` or
`events[type=reply_classified]` with classification in
`{positive, interested, meeting_accepted}`. None exist.

### State: previously emailed, reply UNKNOWN (received but unclassified)

**Count: 0**

**Evidence required:** `events[type=reply_received]` without a matching
`events[type=reply_classified]`. No reply events exist.

### State: already a LinkedIn connection

**Count: 0**

**Evidence required:** `events[type=linkedin_connected]` or
`events[type=connection_accepted]`. None exist.

### State: previous LinkedIn outreach, no reply

**Count: 0**

**Evidence required:** `events[type=push_marked, channel=linkedin]` without
reply events. No LinkedIn push_marked events exist.

### State: suppressed / DNC

| Sub-state | Count | Evidence field |
|-----------|-------|----------------|
| Record-level suppression (domain on suppress list or dropped) | 0 | `rec.drop_reason` starts with "suppress" or `rec.state="dropped"` |
| Contact unsubscribed/suppressed | 0 | `contact.unsubscribed` or `contact.suppressed` |
| Contact stopped | 0 | `contact.stopped` |
| Agency DNC | **Cannot measure** | `agencydnc.lookup(contact)` — hash-based, no provider call, but requires loading the DNC list from disk |

**Note on agency DNC:** `src/agencydnc.py` holds a one-way hash per identifier
and a lookup that answers yes or nothing else. It is checked inside
`eligibility._suppressed()` on every `decide()` call. The snapshot contains no
contact fields that directly indicate agency DNC status — it can only be
determined by calling `agencydnc.lookup()` against the on-disk list. The
mechanism exists and is wired to the send path; it just has no hits in this
estate because no contacts have been through it.

### State: nobody has ever contacted them

**Count: 91** (of 92 contacts)

**Evidence:** ABSENCE of `events[type=push_marked]` for this contact. The one
exception is `hotsoupgroup-com/hussein-samnani` who has one email push_marked.

**Caveat:** Absence of evidence is not evidence of absence. 223 of 300 records
have no contacts at all. The 92 contacts that exist are mostly in records at
the `drafted`, `queued`, or `verified` stages — they have been enriched but
not yet entered a live campaign. The 29 `bison_lead_id` holders were likely
emailed through EmailBison before this estate existed, and that history is
carried only as the integer ID, not as event-log entries.

### The one bit that reaches production: `bison_lead_id`

**Count: 29** (of 92 contacts, 31.5%)

**Evidence:** `contact.bison_lead_id` (integer). This is the ONLY relationship
field that changes a production decision today (see §3 below).

Of the 29:
- 28 have zero `push_marked` events in this estate's log
- 1 (`hotsoupgroup-com/hussein-samnani`) has one email `push_marked`

The `bison_lead_id` is a provider-side fact: it means EmailBison has this
person as a lead. It does NOT mean this estate sent to them — the sends
happened in EmailBison's system, not in this estate's event log.

---

## 2. What is already computed in `src/`

### `eligibility.py` — `must_not_contact()` and `decide()`

**THE send gate.** Computes per-step:
- Suppressed (domain on suppress list, client suppression, agency DNC)
- Record dropped
- Replied (`_replied` — checks `contact.unsubscribed`, `contact.suppressed`,
  `contact.stopped`, and `events.is_reply(entry)` in the event log)
- Paused (account-level: `rec.suppression.unsubscribed`, `rec.review.open`,
  `cadence.pause_state`, `contact.paused`)
- Verification, MX, lint, approval, fatigue, separation, collision, etc.

**Consumed by:** Every payload builder via `eligibility.decide()`. This is the
production send path.

### `linkedinstate.py` — `connection()` and `plan_step()`

Computes the LinkedIn connection axis with a closed vocabulary:
- `NO_EVIDENCE`, `NOT_CONNECTED`, `REQUEST_PENDING`, `UNKNOWN_ACCEPTANCE`,
  `CONNECTION_ACCEPTED`, `CONNECTION_NOT_ACCEPTED`, `CONNECTED`, `REPLIED`,
  `OPEN_PROFILE`, `UNKNOWN`

`plan_step()` returns `go` / `wait` / `skip` for a LinkedIn step based on the
connection state. It reads from the event log (`linkedinstate.evidence()`) and
from an optional provider observation.

**Consumed by:**
- `cadence.py:1084` — `cadence.build()` calls `linkedinstate.plan_step()` for
  every LinkedIn step, and the result determines whether the step is
  `waiting`, `skipped`, or proceeds.
- `nextaction.py:451` — `nextaction` calls `linkedinstate.plan_step()` with
  provider observations to determine what to do next.

### `account.py` — `touches()`, `replies()`, `bounces()`

Projections over the event log:
- `touches()` — every push_marked / email_delivered / linkedin_connected event
- `replies()` — reply_received / reply_classified / positive_reply_detected
- `bounces()` — email_bounced events

**Consumed by (decision paths):**
- `fatigue.py:179` — `account.touches(confirmed_only=True)` feeds
  `fatigue.account_check()`, which is consumed by `eligibility._account_fatigue`
  → **changes a decision** (HELD_ACCOUNT_FATIGUE)
- `nextaction.py:470` — `account.bounces()` feeds the next-action display
- `eligibility._separation` reads `push_marked` events directly (not via
  `account.touches`) → **changes a decision** (HELD_CHANNEL_SEPARATION)

**Consumed by (reporting/display only):**
- `cadenceexposure.py`, `cadencereplies.py`, `cadencesafety.py` — reporting
- `digest.py` — operator digest
- `conversation.py` — conversation thread display
- `hygiene.py`, `outcomes.py`, `signals.py` — reporting
- `oooreturn.py`, `revival.py` — re-engagement paths (these DO change what
  happens to a contact, but they are not on the primary send path)

### `cadence.py` — `accepted_connection()`

Returns a boolean: has this contact had a `linkedin_connected` or
`connection_accepted` event?

**Consumed by:** `cadence.build()` at line 1001, which passes `accepted` to
`expand_step()`. This changes the step expansion — a contact who is already
connected gets different copy than one who is not. **This changes a decision.**

### `channels.py` — `email_verdict()`, `linkedin_verdict()`, `evaluate()`

Determines channel eligibility: `MULTICHANNEL`, `EMAIL_ONLY`,
`LINKEDIN_ONLY`, `NONE`.

**Consumed by:** `channels.evaluate()` is consumed by enrichment and reporting.
`eligibility.decide()` does NOT call `channels.evaluate()` — it re-derives the
same checks inline through `_email_checks` and `_linkedin_checks`.

### `src/agencydnc.py` — `lookup()`

Hash-based DNC lookup. **Consumed by:** `eligibility._suppressed()` →
**changes a decision** (BLOCKED_AGENCY_DNC).

---

## 3. Which states change a decision today

| State | Computed? | Changes a decision? | Consumer |
|-------|-----------|---------------------|----------|
| Previously emailed, no reply | **NO** — not distinguished from "never emailed" | No | Nothing treats "emailed, no reply" differently from "never contacted" |
| Previously emailed, replied NEGATIVE | Partially — `eligibility._replied` blocks on reply events, but does not distinguish negative from positive | **Yes, but coarsely** — any reply blocks, regardless of classification | `eligibility._replied` → `must_not_contact` → `decide` |
| Previously emailed, replied POSITIVE | **NO** — a positive reply triggers the same block as a negative one | **Yes, but wrongly** — a positive reply should make them a warm contact, not a blocked one | Same as above |
| Previously emailed, reply UNKNOWN | **NO** — unclassified replies still trigger `_replied` via `events.is_reply` | **Yes** — an unclassified reply blocks the contact | `eligibility._replied` checks `events.is_reply(entry)` which matches `reply_received` |
| Already a LinkedIn connection | **YES** — `linkedinstate.connection()` and `cadence.accepted_connection()` | **Yes** — `cadence.build` → `expand_step(accepted=True)` changes copy; `linkedinstate.plan_step` skips connection requests to reachable contacts | `cadence.py:1001`, `cadence.py:1084`, `nextaction.py:451` |
| Previous LinkedIn outreach, no reply | **YES** — `linkedinstate.connection()` returns `REQUEST_PENDING` or `UNKNOWN_ACCEPTANCE` | **Yes** — `plan_step` holds later steps while a request is outstanding | `cadence.py:1084`, `nextaction.py:451` |
| Suppressed / DNC | **YES** — `eligibility._suppressed`, `agencydnc.lookup` | **Yes** — BLOCKED_SUPPRESSED, BLOCKED_AGENCY_DNC | `eligibility._suppressed` → `must_not_contact` → `decide` |
| Nobody has ever contacted them | **NO** — absence is not computed as a state | No | Nothing distinguishes "never contacted" from "contacted, no reply" |
| `bison_lead_id` (prior EmailBison) | **YES** — stored on contact | **Yes, but only in one place** | `scripts/build_control_cohort.py:eligible_contacts()` — skips these as "prior EmailBison outreach; not a cold prospect" |

### The critical finding

**The estate conflates positive and negative replies.** `eligibility._replied`
returns `BLOCKED_REPLIED` for ANY reply event, regardless of classification. A
contact who replied "yes, let's talk" is blocked identically to one who replied
"remove me from your list." The `contact.stopped` and `contact.unsubscribed`
fields distinguish the outcomes AFTER classification, but an unclassified reply
blocks the contact until a person reads it.

This is by design for safety — a reply you do not understand should stop
outreach — but it means the estate has no "warm contact" state. A positive
reply is a reason to treat somebody as a relationship, not as a blocked
address, and the system cannot express that.

---

## 4. LinkedIn connection state: what a local model adds

### What the provider already does

Campaign 599020's sequence root is `CHECK_IS_CONNECTION`:

```
CHECK_IS_CONNECTION (free, instant, root)
  already connected → message straight away (4 messages)
  not connected     → CHECK_IS_OPEN_PROFILE → ...
```

HeyReach evaluates this at runtime. A connection request never reaches an
existing connection because the provider branches before it. The provider's
branch is authoritative — it reads the live connection state from LinkedIn at
the moment of execution.

### What `linkedinstate.py` adds locally

1. **Pre-flight planning without a provider call.** `cadence.build()` calls
   `linkedinstate.plan_step()` to determine whether a step should be
   `waiting`, `skipped`, or `go` — offline, without spending a provider read.
   This lets the estate plan a cadence timeline and know which steps are
   blocked before any provider interaction.

2. **The `UNKNOWN_ACCEPTANCE` state.** The provider's `CHECK_IS_CONNECTION`
   is binary at execution time: connected or not. But between sending a
   connection request and the provider checking, there is a window where the
   request is outstanding and the estate needs to know not to send a second
   one. `linkedinstate` models this as `REQUEST_PENDING` and
   `UNKNOWN_ACCEPTANCE` — states the provider does not need because it checks
   at execution time, but the estate needs because it plans ahead.

3. **The `SKIP_ALREADY_REACHABLE` optimization.** If the local model knows a
   contact is already connected, it skips the connection request entirely and
   advances to the message steps. This saves a provider node execution and
   avoids the "already connected → connection request → immediate accept →
   first message" path that wastes a day.

4. **Capability gating.** `linkedinstate.CAPABILITIES` classifies which
   LinkedIn actions are proven (connection_request, message) and which are
   not (open_profile_message, inmail). A step naming an unproven capability
   is held. The provider has no equivalent gate — it will attempt anything in
   the sequence graph.

### What a local model does NOT add

- **The actual connection state at execution time.** The provider's
  `CHECK_IS_CONNECTION` is authoritative. The local model may say
  `NO_EVIDENCE` while the provider knows the contact accepted yesterday. The
  local model is a planning tool, not a runtime authority.
- **Whether a connection request was accepted.** Only the provider can answer
  this. The local model's `UNKNOWN_ACCEPTANCE` is a "nobody has read it yet"
  state, not a guess.

### Verdict

The local `linkedinstate` model adds **planning-ahead value** (avoiding
duplicate requests, skipping unnecessary connection requests, gating
unproven capabilities) but does not replace the provider's runtime branch.
In this estate, where zero LinkedIn sends have occurred, the local model has
no evidence to work with and every contact resolves to `NO_EVIDENCE`.

---

## 5. Proposed change: the smallest thing that would help

### The problem

The estate cannot distinguish "previously emailed, no reply" from "nobody has
ever contacted them." Both states get the same treatment: a cold first touch.
But a person who received an email and did not reply is not the same as a
person who has never heard of you — they have seen your name, your company,
your offer, and chose not to engage. A first message that ignores that is
either a wasted repetition or a sign you are not paying attention.

### The proposed change

**Add a `prior_email_no_reply` flag to the contact's cadence context, consumed
by `cadence.expand_step()` when selecting copy.**

The flag is True when:
- The contact has `push_marked` events on the email channel
- The contact has no reply events (`reply_received`, `reply_classified`,
  `positive_reply_detected`)

The consumer is `cadence.expand_step()` at line 668, which already receives
`accepted` (a similar boolean context flag). Adding `prior_email_no_reply`
follows the same pattern: a fact about the contact's history that changes
what copy is appropriate.

The copy selection would use this to avoid repeating the same opening line.
A contact who already saw "I thought it would be good to connect" and did not
reply should not see it again — the next message should acknowledge the
silence or take a different angle.

### Why this is the smallest change

- It does not require a state machine — it is a boolean derived from two
  event types already in the log.
- It does not change eligibility — the contact is still eligible for outreach.
- It does not change the send path — it changes the COPY, which is already
  parameterised by context.
- The consumer (`cadence.expand_step`) already has the seam — it receives
  `accepted` and `context` parameters for exactly this kind of history-aware
  copy selection.
- It requires no provider calls and no new data — the events are already in
  the log.

### Why it does not change a decision today

Because the estate has only ONE contact with `push_marked` events. This
change would affect exactly one person at this snapshot. But the seam needs
to exist before the estate scales past a handful of sends, and the
measurement proves the data is already there to support it.

---

## 6. Summary

The estate's relationship model is a single bit (`bison_lead_id`) and a
comprehensive event log that almost nothing reads for decision-making. The
event log carries the data to distinguish every state the task asks about —
prior email, reply classification, LinkedIn connection state — but only three
consumers actually use it:

1. **`eligibility._replied`** — blocks on ANY reply, cannot distinguish
   positive from negative
2. **`linkedinstate.plan_step`** — models the connection axis for planning,
   but has no data to work with yet
3. **`cadence.accepted_connection`** — boolean, feeds copy expansion, but
   has no acceptances to detect

The 29 `bison_lead_id` holders are held out of the control cohort by a
script, not by the send path. The send path (`eligibility.decide`) does not
consult `bison_lead_id` at all — it would happily send to a prior EmailBison
lead if they made it through the cohort selection.

The estate is pre-send. The relationship states exist as infrastructure, not
as populated facts. The measurement at this snapshot is a measurement of
potential, not of actual state.
