# Relationship State Measurement — 2026-09-15

**TASK-139 findings.** Snapshot stamp: `2026-09-14T21:52:15Z from master 0ac5e60 300 records`.

## The estate at this moment

300 records, 92 active contacts (on non-dropped records), 921 excluded contacts.

The estate is in a pre-send state. Almost nothing has reached a prospect yet.

## 1. State counts with evidence fields

### State: `bison_lead_id` present (prior EmailBison outreach)

- **Count:** 29 of 92 contacts (31.5%)
- **Evidence field:** `contact["bison_lead_id"]` — an integer EmailBison lead ID
- **What it proves:** This person was previously in EmailBison outreach. They are not a cold prospect.
- **Examples:** ogpartner-dk/jacob-faertz (203715), 16kagency-com/izabelle-a (135163), hotsoupgroup-com/hussein-samnani (203657)

### State: previously emailed, no reply

- **Count:** 0 contacts with confirmed email touches
- **Evidence field:** `events[]` with `type` in (`push_marked`, `email_delivered`) and `contact` matching
- **Finding:** Only 1 contact in the entire estate has a `push_marked` event: `hotsoupgroup-com/hussein-samnani`. Zero `email_delivered` events exist anywhere.

### State: previously emailed, replied (any classification)

- **Count:** 0 contacts
- **Evidence field:** `events[]` with `type = "reply_received"` and `contact` matching
- **Finding:** Zero `reply_received` events exist in the entire estate. No reply has been classified because no reply has arrived.

### State: already a LinkedIn connection

- **Count:** 0 contacts
- **Evidence field:** `events[]` with `type` in (`linkedin_connected`, `connection_accepted`) and `contact` matching
- **Finding:** Zero connection acceptance events exist.

### State: previous LinkedIn outreach, no reply

- **Count:** 0 contacts with confirmed LinkedIn touches
- **Evidence field:** `events[]` with `type = "push_marked"` for LinkedIn channel
- **Finding:** 740 `linkedin_note` entries exist in the `log` array (human-readable), but these are NOT structured events in the `events` array. The `log` array carries `step: "linkedin_note"` entries with no `contact` key — they are record-level notes, not contact-keyed confirmed touches. Zero `push_marked` events for LinkedIn exist.

### State: suppressed / DNC

- **Count:** 0 contacts at contact level
- **Evidence fields:**
  - `contact["suppressed"]` — dict with `since`, `reason`, `why`
  - `contact["unsubscribed"]` — boolean
  - `contact["stopped"]` — boolean
  - `rec["suppression"]["unsubscribed"]` — account-level suppression
  - `rec["drop_reason"]` starting with "suppress"
- **Finding:** None of these fields are set on any contact or record in the snapshot.

### State: nobody has ever contacted them (true cold)

- **Count:** 91 of 92 contacts (98.9%)
- **Evidence:** No `push_marked`, `email_delivered`, or `linkedin_connected` events for this contact
- **The one exception:** `hotsoupgroup-com/hussein-samnani` has a single `push_marked` event

### State: reply classification (positive / negative / neutral / unknown)

- **Count:** 0 across all categories
- **Evidence field:** `events[]` with `type = "reply_classified"` or reply classification in `accountpolicy` outcome
- **Finding:** The classification machinery (`replies.classify`, `accountpolicy.apply_reply`, `CLASSIFIER_OUTCOME`) is fully built and wired. It has never fired on this estate.

## 2. What is computed somewhere in `src/`

| State | Module | Function | What it reads |
|-------|--------|----------|---------------|
| Suppressed / DNC | `eligibility.py` | `_suppressed()`, `must_not_contact()` | domain suppress list, `drop_reason`, `agencydnc.lookup()`, `contact["suppressed"]`, `contact["unsubscribed"]` |
| Contact stopped | `eligibility.py` | `_replied()` | `contact["stopped"]`, `contact["unsubscribed"]`, `contact["suppressed"]`, reply events |
| Reply received | `eligibility.py` | `_replied()` | `events[]` with `events.is_reply(entry)` and matching contact key |
| Reply classification | `replies.py` | `classify()` | Reply text → POSITIVE, NEGATIVE, NEUTRAL, UNKNOWN, UNSUBSCRIBE, etc. |
| Reply policy application | `accountpolicy.py` | `apply_reply()` | Classification → outcome (STOP, HOLD, CONTINUE, REVIEW) |
| LinkedIn connection state | `linkedinstate.py` | `connection()` | `events[]` acceptance/reply/request events + provider observation dict |
| LinkedIn plan step | `linkedinstate.py` | `plan_step()` | `connection()` result + sequence spec → GO/WAIT/SKIP |
| Confirmed touch | `account.py` | `has_confirmed_touch()` | `events[]` with type in (`push_marked`, `email_delivered`, `linkedin_connected`) |
| Touch state per step | `touch.py` | Step state resolution | PLANNED, APPROVED, SENT, DELIVERED, REPLIED, etc. |
| Outreach claims | `outreachclaims.py` | `resolve()` | `has_confirmed_touch()` → what a message may say about prior outreach |
| Prior EmailBison outreach | `scripts/build_control_cohort.py` | `eligible_contacts()` | `contact["bison_lead_id"]` |

## 3. What changes a decision today — consumer trace

### CONSUMED — changes a decision

| State | Computed by | Consumed by | What it decides |
|-------|-------------|-------------|-----------------|
| Suppressed / DNC | `eligibility._suppressed()` | `eligibility.decide()` → `heyreachfactory._plan()`, `push.py`, `executionguard.authorize()` | Whether ANY step goes out. Most final gate. |
| Contact stopped / unsubscribed | `eligibility._replied()` | `eligibility.decide()` → same consumers | Whether this person's sequence continues |
| Reply received (blocking) | `eligibility._replied()` | Same as above | Stops the sequence for this contact |
| LinkedIn connection state | `linkedinstate.connection()` | `linkedinstate.plan_step()` → `cadence.timeline()`, `nextaction.decide()` | Whether a LinkedIn step is GO, WAIT or SKIP; which branch of the sequence runs |
| Confirmed touch | `account.has_confirmed_touch()` | `outreachclaims.resolve()` → `lint.py`, `cadence._context_for()`, `campaignqa.py` | What a message may CLAIM about prior outreach ("my colleague Anna emailed you") |
| Prior EmailBison outreach | `contact["bison_lead_id"]` | `scripts/build_control_cohort.py` `eligible_contacts()` | Whether a contact enters the CONTROL arm cohort. **This is a script, not a production send path.** |

### COMPUTED BUT NOT CONSUMED in any live decision

| State | Computed by | Not consumed because |
|-------|-------------|---------------------|
| Reply classification (positive/negative/neutral) | `replies.classify()` | Has never fired — zero replies in the estate. The machinery is wired: `replies.apply()` → `accountpolicy.apply_reply()` → contact state transition. But it has had no input. |
| Touch state per step (PLANNED/SENT/DELIVERED/REPLIED) | `touch.py` | Consumed by `outreachclaims` for CLAIM checking, but NOT by channel choice, cohort membership, or sequence branching. A step being DELIVERED does not change what happens next — only `eligibility.must_not_contact` does. |
| `cadence.accepted_connection()` | `cadence.py:838` | Called only internally at line 1001 in `timeline()`, passed to `expand_step()` as the `accepted` flag. Used for copy expansion (choosing connected vs cold wording), NOT for branching the sequence. The sequence branch is `linkedinstate.plan_step`'s job. |

### THE RECURRING DEFECT CONFIRMED

The task statement predicted: "a state computed correctly that nothing consumes is the recurring defect in this repository."

At this snapshot, the defect is **latent** rather than active: the estate has almost no relationship state to misread. But the architecture already shows the pattern:

1. `touch.py` computes DELIVERED/REPLIED/POSITIVE_REPLY per step
2. `outreachclaims.py` reads confirmed touches to gate claims
3. Nothing reads the reply CLASSIFICATION to change channel choice, copy selection, or cadence speed
4. `build_control_cohort.py` reads `bison_lead_id` as a boolean hold-out, but this is a script, not the live send path

When replies DO arrive, the classification will flow through `accountpolicy.apply_reply()` and change contact state (stopped, suppressed, held). That IS consumed by `eligibility.must_not_contact()`. So the reply→stop path is wired. What is NOT wired is reply→different-treatment (warm vs cold), which is what the task asks about.

## 4. LinkedIn connection state specifically

### What the provider does today

Campaign 599020's sequence root is `CHECK_IS_CONNECTION` (free, instant):

```
CHECK_IS_CONNECTION (root)
  already connected → MESSAGE chain (connected_1..4)
  not connected     → CHECK_IS_OPEN_PROFILE
    open profile    → INMAIL, then CONNECTION_REQUEST
    not open        → VIEW → FOLLOW → CONNECTION_REQUEST
      accepted      → MESSAGE chain
      not accepted  → VIEW → INMAIL → END
```

The provider branches at RUNTIME based on its own observation of the LinkedIn relationship. A connection request never reaches an existing connection because `CHECK_IS_CONNECTION` routes them to the message chain instead.

### What a local connection-state model would add

`linkedinstate.connection()` already computes this state from events + provider observations. `linkedinstate.plan_step()` already uses it to decide GO/WAIT/SKIP per step. Both are consumed by `cadence.timeline()` and `nextaction.decide()`.

What the local model adds that the provider's branch does NOT:

1. **Pre-staging validation.** `heyreachfactory._plan()` can refuse a contact whose connection state is known-unfavourable BEFORE building the payload, rather than discovering it at the provider. This saves a provider call.
2. **Copy selection.** The local model knows whether to prepare "connected" copy vs "cold" copy before staging, so the campaign payload carries the right words rather than relying on merge fields at runtime.
3. **Screen display.** `nextaction.decide()` reports WAIT with a specific reason ("connection_request_outstanding", "acceptance_unread") rather than a generic "waiting for provider".

What the local model does NOT add:

- **Runtime safety.** The provider's `CHECK_IS_CONNECTION` is the actual gate. If the local model disagrees with the provider, the provider wins. The local model is a planning aid, not a safety gate.
- **New states.** The provider observes the same facts: connected, pending, not accepted. The local model adds `UNKNOWN_ACCEPTANCE` (a window expired with nobody reading) which the provider cannot express, but this is a planning state, not a send decision.

**Verdict:** The local model adds planning-time knowledge and better error reporting. It does not add runtime safety the provider lacks. The provider's branch is the load-bearing gate; the local model is the map that helps plan the route to it.

## 5. Proposed change — the smallest one that makes a state change a decision

### The state: `bison_lead_id` as a warm relationship marker

Today: `build_control_cohort.py` holds out `bison_lead_id` contacts from the CONTROL arm because they are "not cold prospects." This is a script, not the live path.

### The change: `heyreachfactory._plan()` reads `bison_lead_id` and selects the "already connected" branch

**Consumer:** `heyreachfactory._plan()` at the point where it builds the sequence for a contact.

**What changes:** A contact with `bison_lead_id` gets the `already` branch (message chain, no connection request) rather than the `cold` branch (view → follow → connect). The provider's `CHECK_IS_CONNECTION` would reach the same outcome at runtime, but:

1. The campaign payload would carry the right copy from the start
2. The staging gate would refuse a contact with `bison_lead_id` carrying cold copy
3. The screen would show "warm: prior EmailBison outreach" rather than "cold"

**Why this is the smallest change:**

- It reuses the existing `already` branch that `CHECK_IS_CONNECTION` already routes to
- It does not add a new state machine — it reads one existing field and selects one existing branch
- It has a named consumer: `heyreachfactory._plan()`
- It does not touch `eligibility.must_not_contact` or any suppression logic

**Why it matters:**

A contact with `bison_lead_id` receiving a connection request is the exact failure the task describes: "previously emailed, no reply" treated identically to "nobody has ever contacted them." The fix is not to hold them out — it is to route them to the warm branch.

## 6. Summary table

| # | State | Count | Evidence field | Computed in src/? | Consumed by a live decision? |
|---|-------|-------|----------------|-------------------|------------------------------|
| 1 | Prior EmailBison outreach (`bison_lead_id`) | 29/92 | `contact["bison_lead_id"]` | Yes — `build_control_cohort.eligible_contacts()` | **No** — only a script, not the live send path |
| 2 | Previously emailed, no reply | 0/92 | `events[]` type `push_marked`/`email_delivered` | Yes — `account.has_confirmed_touch()` | Indirectly — `outreachclaims` gates claims, not channel |
| 3 | Previously emailed, replied NEGATIVE | 0/92 | `events[]` type `reply_received` + classification | Yes — `replies.classify()` + `accountpolicy.apply_reply()` | Yes — `eligibility._replied()` blocks on `stopped`/`suppressed` |
| 4 | Previously emailed, replied POSITIVE | 0/92 | Same | Same | **No** — positive reply triggers alert, but does not change channel/copy |
| 5 | Previously emailed, reply UNKNOWN | 0/92 | Same | Same | Yes — held for review, sequence paused |
| 6 | Already a LinkedIn connection | 0/92 | `events[]` type `linkedin_connected`/`connection_accepted` | Yes — `linkedinstate.connection()` | **Yes** — `linkedinstate.plan_step()` selects branch |
| 7 | Previous LinkedIn outreach, no reply | 0/92 | `events[]` type `push_marked` for LinkedIn | Partially — `touch.py` tracks step state | No — step state does not change channel |
| 8 | Suppressed / DNC | 0/92 | `contact["suppressed"]`, `contact["unsubscribed"]`, domain list | Yes — `eligibility._suppressed()` | **Yes** — `eligibility.must_not_contact()` blocks everything |
| 9 | Nobody has ever contacted them | 91/92 | Absence of all touch events | N/A (default) | N/A |

**The critical finding:** At this snapshot, 91 of 92 contacts are in state 9 (true cold). The relationship model is inert because there are no relationships yet. The machinery is built and wired; it has had no input.

**The architectural finding:** When relationships DO exist, the only state that changes a live send decision is suppression/DNC (blocks everything) and LinkedIn connection state (selects branch). Reply classification changes contact state (stopped/suppressed) which IS consumed. But reply classification does NOT change channel choice, copy selection, or cadence speed — a positive reply and a negative reply both stop the sequence, just differently.

**The `bison_lead_id` finding:** This is the one bit of relationship state that reaches a decision, and it is a script decision, not a live send decision. The live send path treats all 92 contacts identically (modulo eligibility gates). A contact with prior EmailBison outreach and a contact who has never been contacted both receive the same cold sequence.
