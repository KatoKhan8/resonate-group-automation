---
title: "Per-lead sender attribution — the design that replaces the arity rule"
date: "2026-09-17"
status: "DESIGN ONLY. No gate changed, no provider write, no --live, no commit."
supersedes_rule: "src/executionguard.py:1079 — `if len(ids) != 1`"
builds_on:
  - "docs/HEYREACH-SENDER-CAPACITY-2026-09-17.md"
  - "docs/BISON-ATTRIBUTION-BOUNDARY-2026-09-15.md"
  - "docs/BISON-API-CAPABILITY-MAP-2026-09-14.md"
---

# Per-lead sender attribution

## What this document is

`src/executionguard.py:1058-1085` (`_sender_for`) refuses to authorize any
action on a campaign whose canonical row names more than one sender for the
channel:

```
src/executionguard.py:1079
    if len(ids) != 1:
        raise NotAuthorized(
            "sender",
            f"the canonical campaign names {len(ids)} {channel} senders; a "
            f"guarded action is attributed to exactly one")
```

The rule is right and this document does not weaken it. What it proposes is to
move the arity requirement **from the campaign to the action**: an action stays
attributed to exactly one human, but the one human is resolved *per lead* and
must be *proved* rather than *inferred from having no alternative*.

Everything below was established by reading the code and by READ-ONLY provider
calls made on 2026-09-17. No write route was called. HeyReach 605732 and
EmailBison 487 were read and not modified. Nothing under `src/` was edited.

---

# PART 1 — WHAT EXISTS ALREADY

## 1.1 `src/senderidentity.py` — the human, the account, the pairing

The module that introduced the distinction an account id cannot make
(`src/senderidentity.py:1-60`): *an inbox is not a person*.

| Thing | Constructor | What it holds |
|---|---|---|
| HumanSenderIdentity | `new_sender` **:148** | `sender_id`, `display_name`, `title`, `team`, `active`, `colleague_language` |
| EmailSenderAccount | `new_email_account` **:175** | `account_id`, **`sender_id` (the owner)**, `provider_account_id`, `email_address`, `daily_limit`, `health` |
| LinkedInSenderAccount | `new_linkedin_account` **:208** | same shape, `profile_url` instead of an address |
| SenderPairing | `new_pairing` **:237** | "Anna's email alongside Petar's LinkedIn" |

Reads are all workspace-scoped and there is deliberately **no unscoped
variant** (`_rows` **:140-143**). `require_sender` **:280** raises
`UnknownSender` / `CrossWorkspaceSender`. `by_provider_account` **:332** maps a
provider id back to a canonical account row. `pairing_for` **:372** is what
lets the LinkedIn side ask for the email side's human. `capacity` **:527**
sums `daily_limit` per channel and reports `complete: False` when any active
account has no known limit. `digest` **:623** fingerprints the roster.

**Where it falls back:** it does not. It raises or returns `None`. The
weakness is elsewhere — see 1.4 and Part 2.

**One trap that matters.** `roster()` **:468-495** matches accounts to people
with `a["sender_id"] == person["sender_id"]` and **never consults
attestations**. So even after an attestation backfill, the senders screen would
still classify every account as an `orphan_account` (**:497-502**). Any design
that makes attestation load-bearing must also make `roster()` resolve through
`senderownership.resolve_owner`.

## 1.2 `src/senderownership.py` — the attestation that bridges the gap

`senderinventory` rebuilds the roster from provider truth and sets
`sender_id=None` on every row on purpose, because neither provider knows who
owns an inbox (`src/senderinventory.py:13-19`, `:298`). `senderownership`
exists to record a human statement instead:

- `attest(workspace, channel, account_id, sender_id, by, at)` **:52-87** — the
  only write path. Refuses an unknown sender via `si.require_sender` **:68**,
  requires an actor **:66**, and replaces any prior attestation for that
  account rather than appending **:79-86**.
- `resolve_owner(account, rows)` **:106-132** — two paths in order: the
  account's own `sender_id`, then an attestation. Returns `None` when neither
  resolves, deliberately rather than a sentinel **:113-117**.
- `dry_run_report(workspace)` **:145-189** — what a backfill *would* write,
  splitting accounts into `resolved` and `needs_attestation`.

**Where it falls back:** `resolve_owner` returns `None`, and every caller
decides what `None` means. `assignment.resolve_reply_owner`
(`src/assignment.py:392-428`) renders it as `UNKNOWN` **:417-420**.

**A second trap.** `senderinventory.py:316` writes `account["attested"] =
allowed is not None`, where `allowed` is the operator's **seat allowlist**
(`build_linkedin` **:281-289**). All 32 productive `linkedin_account` rows on
disk carry `"attested": true`. That word there means *"an operator approved
using this seat"*, not *"an operator named the human who owns it"*, and
`resolve_owner` reads neither it nor anything populated. Two vocabularies, one
word, on the ownership path.

## 1.3 `src/assignment.py` — allocate once, then it is a fact

The module docstring states the design (`src/assignment.py:19-23`): assignment
"stops being a function and becomes a *fact*. It is computed once, written
onto the contact, and read from there forever after."

- `eligible_senders(workspace, channel, ...)` **:101-136** — humans who are
  active **:122** and own at least one active account on the channel whose
  health is not a refusal **:126**. Ownership is resolved by the account's own
  `sender_id` **:128** *or* by `so.resolve_owner` **:131**. `REFUSING_HEALTH`
  **:93** is `(paused, blocked)` only — `warming` and `unknown` are usable
  here.
- `allocate(workspace, contact_key, channel, ..., prefer_sender_id)`
  **:150-190** — raises `NoEligibleSender` **:160-163** on an empty pool;
  otherwise honours a pairing **:166-170** or picks deterministically by
  `_slot` **:70-77** (sha1 of the key, not Python's salted `hash`), then picks
  one of that human's accounts by a second hash **:139-147**. Stores nothing.
- `ensure(rec, contact, workspace, ...)` **:193-236** — idempotent: a channel
  with a stored assignment is skipped entirely **:213-214**, which is what
  makes stickiness real rather than intended. Email is allocated first so the
  LinkedIn side can be paired to it **:211-221**. Writes
  `contact["sender_assignment"]`, stamps `at`/`by` **:232-234** and
  `roster_digest` **:235**.
- `reassign(...)` **:239-284** — the only way a stored assignment changes.
  Requires a reason **:251-254**, keeps the old sender, appends to `history`
  **:279**, logs `sender_reassigned` **:281**.
- `is_stale` **:320-330** — "the pool changed since this was assigned" as a
  fact for a screen, explicitly *not* a trigger.

**Where it falls back — and this is the load-bearing one:**

```
src/assignment.py:222-230
        try:
            block[channel] = allocate(...)
        except NoEligibleSender as e:
            # Recorded, not raised. A contact with no LinkedIn sender is an
            # email-only contact ...
            block.setdefault("unavailable", {})[channel] = str(e)
            continue
```

`ensure` **swallows** `NoEligibleSender` and records it under `unavailable`.
The reasoning given is sound for a mixed-channel contact. The consequence,
today, is that **no contact in `productive` ever acquires an owner on either
channel and nothing raises.**

## 1.4 `heyreach.build_lead_pairs` — the per-lead seat already exists on the wire

```
src/providers/heyreach.py:47-56
        # Per row, not per push. A LinkedIn sender is assigned per contact and
        # sticks to them, so a single account id for the whole batch would
        # send every prospect from whichever profile the caller happened to
        # name ...
        "linkedInAccountId": _account_id_for(r, linkedin_account_id),
```

`_account_id_for(row, fallback)` **:92-107**:

```python
    candidate = row.get("provider_account_id")
    if candidate not in (None, ""):
        try:
            return int(candidate)
        except (TypeError, ValueError):
            pass
    return int(fallback or 0)
```

**Where it falls back:** to the caller's single `linkedin_account_id`, whenever
the row carries no `provider_account_id`. The row is built by
`push.heyreach_rows`, whose sender fields come from `push._sender_of`
(`src/push.py:188-208`), which reads `assignment.assigned(contact, channel)`
and returns `""` for every field when nothing is assigned **:201-207**. The
fallback id itself comes from `heyreachfactory._seat_for`
(`src/heyreachfactory.py:1039-1070`), which reads the canonical campaign's
`senders.linkedin[].provider_account_id` — i.e. the hardcoded `SEAT_ID =
174892` written by `scripts/create_linkedin_cohort_b_row.py:43`.

So the per-lead mechanism is fully built and is, today, never exercised: every
row is empty, every lead takes the fallback, and the fallback is one seat.

## 1.5 Where the guard stands now

`authorize` (`src/executionguard.py:342`) runs a fixed order (**:36-46**). The
sender block sits at **:601-644**:

- **:603** `sender_id = _sender_for(campaign, channel)` — the arity rule.
- **:630-638** the seat must be in this client's canonical roster (tenancy
  *and* ownership, per the comment at **:625-629**).
- **:640-641** the seat must be `active`.
- **:642-643** `seat.get("health") in (None, "ok")` — this is what refuses the
  three `warming` inboxes.
- **:644** `gates.append("sender")`.

`Authorization` already carries a single `sender_id` slot
(**:146-148**), and `actionledger.reserve` takes `sender_id=` as a first-class
field (`src/actionledger.py:242`, row written at **:283**), with
`count_on(..., sender_id=...)` **:127-156** enforcing a per-sender daily
ceiling. **The ledger is already per-sender.** Nothing about it assumes the
sender came from the campaign rather than from the lead.

---

# PART 2 — WHY IT DOES NOT WORK TODAY (verified, not assumed)

Verified 2026-09-17 against `work/senders.jsonl` (285 rows) and by running the
functions.

### 2.1 Every productive account row has `sender_id: null`

```
kind/workspace counts:
  email_account/productive     225      linkedin_account/productive    32
  sender/productive              7      pairing/productive              2

linkedin_account × (workspace, sender_id, active, health):
  ('productive', None, True, 'ok'): 32        <- all 32
email_account × (workspace, sender_id, active, health):
  ('productive', None, True, 'ok'):     222
  ('productive', None, True, 'warming'):  3   <- all 225
```

Seven human `sender` rows exist for `productive` (anna, mark, john, sarah,
petar, tom, sara_s) and **not one account points at any of them.**

### 2.2 There are ZERO `ownership_attestation` rows

```
[r for r in rows if r.get("kind") == "ownership_attestation"]  ->  []
```

Across the whole file, all workspaces. So `resolve_owner`
(`senderownership.py:121-132`) has neither path available for any productive
account.

### 2.3 `eligible_senders` returns `[]`, `allocate` raises, `ensure` swallows

Run with `SENDERS=work/senders.jsonl`:

```
productive  linkedin  eligible: []
productive  email     eligible: []
contactout  linkedin  eligible: [('ines', 1), ('liam', 1)]
contactout  email     eligible: [('liam', 2), ('mara', 3)]

allocate('productive', 'x@y.com', 'linkedin')
  -> NoEligibleSender: no active linkedin sender in productive owns an
     active linkedin account

ensure({}, {'key': 'x@y.com'}, 'productive')
  -> {"unavailable": {"email": "no active email sender in productive owns an
        active email account",
      "linkedin": "no active linkedin sender in productive owns an active
        linkedin account"},
      "at": "...", "by": "system", "roster_digest": "abf40771b7b3e74d"}
```

Confirmed exactly as the earlier audit stated. `contactout` works because its
fixture accounts were created with owners; `productive` — the only live
workspace — does not.

### 2.4 The consequence chain, end to end

1. No account has an owner → `eligible_senders` is `[]`.
2. → `allocate` raises `NoEligibleSender`.
3. → `ensure` records it under `unavailable` and continues (`assignment.py:225-230`).
4. → `contact["sender_assignment"][channel]` is never written.
5. → `push._sender_of` returns `provider_account_id: ""` (`push.py:206`).
6. → `heyreach._account_id_for` takes the fallback (`heyreach.py:105-107`).
7. → the fallback is `_seat_for`'s single canonical seat, `174892`.
8. → every prospect lands on one seat, so arity-1 is *incidentally* true, and
   `_sender_for` passes for a reason unrelated to attribution.

**Stickiness today works by accident of arity.** Attach a second seat and step
7 stops determining anything: HeyReach's own rotation picks, and
`configdiff._ids` (`src/configdiff.py:118-151`) compares the campaign's sender
*set*, never which lead sits on which seat — so the campaign reads as correctly
configured throughout.

### 2.5 Both live campaigns, as configured

| | canonical row | provider says |
|---|---|---|
| `productive-linkedin-cohort-v2` → HeyReach **605732** | `senders.linkedin = [{provider_account_id: 174892}]`, `org_unit: 118832`, `status: approved`, `provider_status_expected: IN_PROGRESS` | `status: IN_PROGRESS`, `campaignAccountIds: [174892]`, 3 leads |
| `productive-email-control-v3` → EmailBison **487** | `senders.email = [{2736, eb-2736}, {3941, eb-3941}]`, `bison_campaign_id: 487` | `status: paused`, `total_leads: 10`, `emails_sent: 0`, `campaign_senders: [2736, 3941]` |

605732 passes `_sender_for` (one id). **487 cannot**: `len(ids) == 2`, so it
refuses with *"the canonical campaign names 2 email senders"*. That is the
exact line blocking the email channel.

---

# PART 3 — WHAT THE PROVIDERS CAN ACTUALLY TELL US

## 3.1 HeyReach — per-lead sender is both WRITABLE and READABLE. CONFIRMED.

**Write.** `accountLeadPairs[].linkedInAccountId` is per lead, not per request
(`src/providers/heyreach.py:47-56`). `add_leads_to_campaign` **:2301-2320**
sends exactly what `build_lead_pairs` produces.

**Read.** `/campaign/GetLeadsFromCampaign` (`LEADS_ROUTE` **:2578**) returns
`linkedInSenderId` per lead, and `campaign_leads` **:2679-2706** already maps
it:

```
src/providers/heyreach.py:2696
                    "sender_id": row.get("linkedInSenderId"),
```

**Confirmed live, 2026-09-17, read-only, campaign 605732** — `totalCount: 3`:

| lead | profile | `linkedInSenderId` | state |
|---|---|---|---|
| 308670517 | /in/jamal-fraiser-5a10051a2 | **174892** | `request_pending` (InSequence / None / None) |
| 308670518 | /in/michelle-brianna-parsons | **174892** | `request_pending` |
| 308670519 | /in/audreyhancock | **174892** | `request_pending` |

`campaign_read(605732)` → `campaignAccountIds: [174892]`.

**Nothing outside the provider module reads that field.**
`configdiff.provider_heyreach` **:464-520** builds `sender_ids` from the
*campaign*, and `REQUIRED_HEYREACH` **:72-81** lists `sender_ids`, `lead_set`,
`lead_count` — but no per-lead owner. The evidence is on the wire and no gate
consumes it.

**Decisive fact, LinkedIn: per-lead sender is controllable on write and
provable on readback, with routes that already exist in this repository.**

## 3.2 EmailBison — per-lead sender is OBSERVABLE, NOT CONTROLLABLE, and NOT OBSERVABLE BEFORE ACTIVATION

Four things were checked, all read-only, workspace 10 (PRODUCTIVE) with the
credential binding asserted by `bison.require_workspace` (`bison.py:235-261`).

**(a) No write route can pin a lead's inbox.** `WRITE_ROUTES`
(`src/providers/bison.py:405-436`) contains exactly one sender verb:
`/campaigns/{campaign_id}/attach-sender-emails` — **campaign-level**
(`attach_senders` **:1111-1135**). The lead verbs are `/leads` (`build_leads`
**:262-306**) and `/leads/{lead_id}` (`update_lead` **:1163**); neither payload
has a sender field, and `LEAD_VARIABLES` **:322-328** carries `sender_id`,
`sender_account_id` and `provider_account_id` only as *custom variables* — the
code's own comment says so (**:288-301**): "Whether EmailBison round-trips
these particular fields has NOT been validated... **Nothing depends on it.**"

**(b) The lead row carries no sender.** `bison.lead(203809)` (a live 487 lead):

```
keys: company, created_at, custom_variables, email, first_name, id,
      last_name, lead_campaign_data, notes, overall_stats, status, tags,
      title, updated_at, uuid
lead_campaign_data: [{campaign_id: 485, status: "stopped", ...},
                     {campaign_id: 487, status: "sending_paused", emails_sent: 0, ...}]
```

No inbox, anywhere on the row.

**(c) The ONE route that names an inbox per lead is the scheduled-email
queue.** `/campaigns/{id}/scheduled-emails` (`scheduled_emails` **:1441-1466**)
returns rows carrying `sender_email: {id, name, email, daily_limit, status,
...}`. Confirmed live on campaign 352 (active), page 1:

```
KEYS: campaign, campaign_id, clicks, email_body, email_subject, id,
      interested, lead, opens, raw_message_id, replies, scheduled_date,
      scheduled_date_local, sender_email, sent_at, sequence_step_id,
      status, thread_reply, unique_opens, unique_replies
sender_email -> {"id": 3437, "name": "Bojan Rendulic",
                 "email": "rendulicbojan@gproductive.com", ...}
status       -> "scheduled"          (i.e. named BEFORE it is sent)
```

Per-lead stickiness across steps, sampled 8 pages / **83 distinct leads** of
campaign 352: **0 leads carried more than one distinct `sender_email.id`.** 22
distinct inboxes in use across the sample. So within one materialization of the
queue, EmailBison does bind a lead to an inbox and keeps it.

**(d) And the queue is EMPTY until the campaign has run.** Measured today:

| campaign | status | leads | `scheduled-emails` rows (`meta.total`) |
|---|---|---|---|
| **487** | paused, never started | 10 | **0** |
| 481 | paused, never started | 23 | **0** |
| 485 | draft | 10 | **0** |
| 451 | completed | 1 | 1 (`sent`, sender 3948 bernarda.vrbat@goproductive.online) |
| 352 | active | 21,318 | 95,724 (6,382 pages) |

**Decisive fact, email: EmailBison chooses the inbox itself, offers no route to
pin it, and discloses the choice only after the campaign has started
scheduling. For campaign 487, as it sits right now, there is no read route on
this provider that can say which inbox any of its ten leads will send from.**

## 3.3 The email finding that changes the 487 decision

`/sender-emails` (`sender_emails` **:121-194**, complete-inventory enforced,
225/225 returned with `meta.total: 225`) carries a **display name** per inbox.
Across the estate there are **12 distinct display names over 225 inboxes**
(`Kresimir Simicic` 66, `Bernarda Vrbat` 58, `Riley Parker` 17, `Morgan Ellis`
17, `Casey Wright` 17, `Ivan Mamic` 13, `Fran Vizintin` 12, `Tomislav Car` 11, …).

The two inboxes bound to campaign 487:

| inbox | display name | address | health (roster) |
|---|---|---|---|
| **2736** | **Bojan Rendulic** | bojan.rendulic@dontgoproductive.com | `ok` |
| **3941** | **Bernarda Vrbat** | bernarda.vrbat@goproductivelab.shop | `warming` |

**These are two different people.** Campaign 487 as configured would send its
ten prospects from two different humans, chosen by the provider, with no record
of which prospect heard from whom. That is a fact the pending operator decision
on 487 did not have. It is also, precisely, what `_sender_for`'s refusal is
currently preventing — the rule is doing its job.

The same field is the seed for ownership on email: a display name is strong
evidence for an operator attestation, and it is not itself one.

---

# PART 4 — THE DESIGN

## 4.1 How a prospect acquires an owner

Three layers, in order. Nothing in layer 2 or 3 may run before layer 1.

### Layer 1 — accounts acquire humans (once, by a person)

The roster rebuild must keep setting `sender_id=None`
(`senderinventory.py:13-19`); inventing an owner stays forbidden. Ownership
arrives through `senderownership.attest(workspace, channel, account_id,
sender_id, by)` **:52-87**, which already refuses an unknown human and already
requires a named actor.

What is new is a **proposal** step, so 257 attestations are not typed by hand:

```
python -m src.senderownership --workspace productive --propose
```

- **email**: propose `account.provider_state.display_name` → the matching
  `sender` row by display name. The name is on the provider row
  (`/sender-emails` `.name`); `senderinventory` does not currently store it, so
  it must be added to `PROVIDER_OWNED`-adjacent state. 225 inboxes collapse to
  12 names, so the operator confirms ~12 decisions, not 225.
- **linkedin**: propose `firstName`/`lastName` from `/li_account/GetAll` (both
  present — seat 174892 reads `Bruno Gudelj`, `brunogudelj@gmail.com`).
- Output is a table an operator approves or edits. **Approval writes the
  attestations; the proposal writes nothing.** `dry_run_report`
  (`senderownership.py:145-189`) is the existing shape for this.

Two repairs fall out and are part of this layer, not optional:

1. `senderidentity.roster()` **:468-495** must resolve owners through
   `senderownership.resolve_owner`, or every attested account still reports as
   an orphan.
2. `senderinventory.py:316`'s `account["attested"]` must be renamed
   (`seat_allowlisted`). One word must not mean two things on the ownership
   path.

### Layer 2 — a prospect acquires a human (once, at cadence build)

Unchanged in shape: `assignment.ensure` (`assignment.py:193-236`) at cadence
build, idempotent by the skip at **:213-214**, email first so the pairing can be
honoured **:211-221**, stored on the contact under `sender_assignment`, changed
only by `reassign` **:239-284**.

Two changes:

- **`ensure` stops swallowing on a channel the campaign will actually use.**
  The swallow at **:225-230** stays correct for a channel this campaign does
  not run — an email-only contact genuinely has no LinkedIn sender. It becomes
  a refusal when the caller names the channel as required:
  `ensure(..., require=(channel,))`. An unassigned prospect must not reach a
  payload builder silently. This is a *strengthening* of a fallback, not a
  relaxation of a gate.
- The stored row gains `capacity_digest` and `capacity_read_at` beside the
  existing `roster_digest` **:235**, so a later reader can say what picture the
  allocation was made against without ever recomputing it.

### Layer 3 — already-live prospects acquire the human who already touched them

Not by allocation. By copying the provider's record. See 4.6.

### Where it is recorded

`contact["sender_assignment"][channel]`, exactly the block
`assignment.allocate` already returns (`assignment.py:176-190`):
`sender_id`, `display_name`, `account_id`, `provider`, `provider_account_id`,
`address`, `workspace`, `channel`, `via`. Plus, new:

```
"owner_source":  "attestation" | "sender_id" | "provider_backfill"
"attested_by":   <actor>            # from the attestation row
"attested_at":   <iso>
```

`sender_assignment` already travels with the contact record, already has
`history` and `at`/`by`, and is already what `push._sender_of` reads
(`push.py:188-208`). No new store.

## 4.2 How stickiness is ENFORCED rather than hoped for

Today stickiness is hoped for in three places and enforced in none: `ensure`
skips an assigned channel (hope: that `ensure` is the only writer),
`_account_id_for` prefers the row's id (hope: that the row has one), and
`_sender_for` allows one seat (accident: that there is only one).

Four enforcement points, from the outside in.

**(1) The guard, gate `attribution` — the one that refuses.** Replaces the
`_sender_for` call at `executionguard.py:603` and sits in the same position,
before the cap, because `actionledger.count_on(..., sender_id=...)`
(`actionledger.py:127-156`) must count against the *resolved* sender. The
stickiness clause is predicate clause **(7)** in 4.3:

> every already-recorded action for this `(contact_key, channel)` names the
> same `sender_id`.

Read from two independent places and both must agree: the durable action ledger
rows for this contact, and `touch.confirmed_touches` (`src/touch.py`, the
function `reference_for` **:315** already consults). A prior touch by human A
plus a proposed action by human B raises `NotAuthorized("attribution", ...)`
with both names in the message. It cannot be bypassed by re-running allocation,
because **allocation never runs inside the guard** — the guard only reads what
is stored.

**(2) The write layer.** `revalidate` (`executionguard.py:909`) re-asserts, at
the moment of the write, that `authorization.sender_id` still equals
`assignment.assigned(contact, channel)["provider_account_id"]`. This closes the
window between minting and transport (already bounded to 60s by
`AUTHORIZATION_TTL_SECONDS` **:78**).

**(3) The payload builder stops falling back.**
`heyreach._account_id_for` **:92-107** currently returns the caller's id when
the row has none. Under this design a row with no `provider_account_id` is a
programming error, not a default:

```python
    candidate = row.get("provider_account_id")
    if candidate in (None, ""):
        raise ProviderError(
            "a lead with no assigned seat cannot be built into a lead pair: "
            "the fallback would send this prospect from whichever profile the "
            "caller happened to name")
```

The `fallback` argument is kept only for the sequence-probe callers at
**:1225** and **:1230**, which pass a synthetic row.

**(4) Reassignment stays the only door.** `assignment.reassign` **:239-284**
already requires a reason, keeps history and logs. Nothing else may write
`sender_assignment[channel]` once set — enforceable by a test that greps for
assignment to that key outside `assignment.py`, in the shape
`tests/test_nothing_writes_to_a_provider` already uses.

## 4.3 THE PREDICATE THAT REPLACES THE ARITY CHECK

`_sender_for(campaign, channel) -> one id` becomes
`_owner_for(campaign, channel, rec, contact, readback) -> one owner`.

```
ATTRIBUTED(campaign, channel, rec, contact, readback) holds iff ALL of:

  (1) OWNER RECORDED
      a = assignment.assigned(contact, channel)
      a is not None, and a["sender_id"], a["account_id"] and
      a["provider_account_id"] are all non-empty.

  (2) OWNER IS AN ACTIVE HUMAN IN THIS TENANT
      p = senderidentity.require_sender(campaign["client"], a["sender_id"])
      p["active"] is True.
      (require_sender raises CrossWorkspaceSender for another tenant's human.)

  (3) THE ACCOUNT IS THAT HUMAN'S, ATTESTABLY, AND FIT TO SEND
      acct = senderidentity.by_provider_account(
                 campaign["client"], channel, a["provider_account_id"])
      acct is not None
      and acct["active"] is True
      and acct["health"] in (None, "ok")
      and senderownership.resolve_owner(acct) == a["sender_id"]

  (4) THE CAMPAIGN ADMITS THAT ACCOUNT
      str(a["provider_account_id"]) in configdiff._ids(
          (campaign["senders"] or {})[channel])
      -- SET MEMBERSHIP. No constraint on |set|.

  (5) NO LEAD IN THIS CAMPAIGN IS UNATTRIBUTED
      for every contact c in the campaign's selected lead set on this channel:
          clauses (1),(2),(3),(4) hold for c.
      -- computed once per authorize() from the same rows the cap already
         loads; a campaign with one nameless lead authorises nothing.

  (6) THE PROVIDER AGREES, PER LEAD
      readback is fresh (executionguard.readback_is_fresh, TTL 900s),
      sealed and bound to this campaign/channel, AND
      readback.provider["lead_owner"] is a total map over the leads the
      provider holds, AND
      readback.provider["lead_owner"][lead_key(contact)]
          == str(a["provider_account_id"]), AND
      for every lead L the provider holds:
          readback.provider["lead_owner"][L] == our assignment for L
      -- UNVERIFIABLE anywhere in that map is a refusal, never a pass.

  (7) STICKY
      every prior recorded action for (contact["key"], channel) --
      actionledger rows and touch.confirmed_touches -- carries
      sender_id == a["sender_id"]. An empty history satisfies this.

The action is then attributed to exactly one human:
      Authorization.sender_id = a["provider_account_id"]
      Authorization.owner_id  = a["sender_id"]          (new slot)
```

### Why this is strictly stronger, not a relaxation

The old rule proved one thing: *the set of seats this campaign could possibly
have used has size 1, therefore this action is attributable.* Attribution by
elimination. It proved nothing about **which human**, nothing about whether the
seat belongs to that human, nothing about whether the provider agrees for this
lead, and nothing about the prospect's history.

The new predicate proves the old rule's conclusion and four more:

| Guarantee | old `len(ids) != 1` | new predicate |
|---|---|---|
| this action names exactly one seat | yes (by elimination) | yes — clause (1) names one, and it is what goes in `Authorization.sender_id` |
| that seat is in this tenant's roster, active and healthy | yes (guard :630-643) | yes — clause (3) |
| the seat belongs to a **named human** | **no** | yes — clauses (2),(3) |
| a person **vouched** for that ownership | **no** | yes — clause (3) via `resolve_owner`, which needs `sender_id` or an attestation row with `by` and `at` |
| the **provider** agrees for **this lead** | **no** — `configdiff._ids` compares the campaign's sender *set* | yes — clause (6) |
| **no other lead** in the campaign is nameless | **no** | yes — clause (5) |
| the prospect has never heard from anybody else | **no** | yes — clause (7) |

The arity requirement is not removed. It moves from *the campaign row* to *the
action*: one action, one `sender_id`, one `owner_id`. What is removed is the
inference that the campaign row's cardinality is a proxy for it — an inference
that is false the moment a lead set is heterogeneous, and true today only by
accident (Part 2.4).

**The honest consequence, stated plainly: campaign 605732 as configured right
now FAILS this predicate.** Clause (1) fails — its three contacts have no
`sender_assignment`; clause (3) fails — `li-174892` has `sender_id: null` and
no attestation. The new rule refuses what the old rule allowed. That is what
"strictly stronger" means here, and it is why Part 4.6 exists.

## 4.4 What a provider readback must prove before activation

### LinkedIn — provable, with routes that already exist

Add to `configdiff.provider_heyreach` (**:464-520**):

```python
    leads, total = heyreach.campaign_leads(campaign_id)      # already paged
    lead_owner = {}
    for row in leads:
        url = linkedin.canonical(row["profile_url"])
        if row.get("sender_id") in (None, ""):
            lead_owner[url] = UNVERIFIABLE      # never a pass
        else:
            lead_owner[url] = str(row["sender_id"])
```

and to `approved_heyreach`, the same map built from
`assignment.assigned(contact, "linkedin")["provider_account_id"]` per selected
contact. Then:

```python
REQUIRED_HEYREACH = (..., "lead_set", "lead_count", "lead_owner", ...)
SUBSET_FIELDS     = ("lead_set", "lead_count", "lead_owner")   # staging only
```

`lead_owner` joins `SUBSET_FIELDS` for the same reason `lead_set` is there
(`configdiff.py:915-926`): a staging readback authorises a write that *adds*
people, so containment is the right comparison; `_within` **:918** already
handles a mapping if extended to compare shared keys.

**Sequencing that makes this a pre-activation proof.** `providerwrites`
already refuses `heyreach.add_leads` unless a read taken at the moment of the
write proves the destination **cannot send** — only DRAFT proves it
(`src/providerwrites.py:150-171`). So the order is: add leads to a
non-sending campaign with per-lead seats → read `/campaign/GetLeadsFromCampaign`
→ prove `lead_owner` agrees for every lead → *then* activate. Per-lead
agreement is established before any prospect is reached. No new route, no new
permission.

**What it must prove, restated as the activation gate:** for every lead the
provider holds, `linkedInSenderId` is present, equals our stored assignment,
and resolves to an attested active human in this tenant; and the set of seats
appearing in `lead_owner.values()` is a subset of `campaignAccountIds` and of
the canonical row's sender set.

### Email — NOT provable before activation. Two phases, and the second is detection.

**Phase A, pre-activation (prevention, campaign-level):**

1. `bison.campaign_senders(id)` (**:1138-1153**, paged) equals the canonical
   row's `senders.email` set exactly.
2. Every inbox in that set resolves via `senderownership.resolve_owner` to an
   **attested, active** human in this tenant.
3. **`|{resolve_owner(i) for i in inboxes}| == 1`.** One *human*. Any number of
   that human's inboxes.
4. Each inbox is `active` and `health in (None, "ok")` — which is the existing
   check at `executionguard.py:642`, and is what excludes the three `warming`
   inboxes.

**Phase B, post-activation (detection, per-lead), bounded in time:**

Within one scheduling window of `resume_campaign`, read
`/campaigns/{id}/scheduled-emails` and assert, per row:
`sender_email.id ∈ {this campaign's attested inboxes}` and
`resolve_owner(sender_email.id) == the one attested human`.

On disagreement: `bison.pause_campaign` (**:1569**, in `WRITE_ROUTES` **:420**)
and `stop_lead` (**:906**, `/leads/stop-future-emails` **:423**) for the
affected leads. Both are stop verbs — "can only ever mean somebody receives
less" (**:417-418**).

Phase B is **not** the equal of the LinkedIn proof and must never be recorded
as one. It is stated as what it is: a detector with a blast radius of one
scheduling window. Phase A is what actually prevents the harm, and it does so
by making the provider's freedom to rotate *harmless* rather than by removing
it — every inbox it may rotate to is the same human.

## 4.5 Deterministic allocation for a NEW unassigned prospect — no LLM

Pure function of `(contact_key, channel, capacity snapshot)`. Same inputs, same
answer, on any machine, forever. It runs at **planning time**, never inside
`authorize` — the guard must not depend on a provider read.

### Step 1 — the candidate set

`assignment.eligible_senders(client, channel)` (**:101-136**) as written, once
attestations exist: active human **:122**, owning an active account
**:126** whose health is not `paused`/`blocked` **:93**, ownership resolved by
`sender_id` or attestation **:128-133**. Then intersect with the campaign's
declared sender set — a campaign may not allocate an account it does not name.

### Step 2 — real remaining capacity per account

Not `daily_limit`. `daily_limit` is a per-seat plan number and
`senderidentity.capacity` **:527** sums it into a figure that over-plans (the
2026-09-17 amendment to `HEYREACH-SENDER-CAPACITY` records a 26% over-plan from
exactly this).

**LinkedIn** — the vendor divides a seat's limit across the campaigns the seat
is active in. Marginal share if this campaign is added:

```
remaining(seat) = provider_state.connection_limit / (active_campaigns + 1)
                  - actionledger.count_on(today, channel="linkedin",
                                          sender_id=pid, workspace=client)
```

Both inputs are on the row already (`provider_state.connection_limit`,
`provider_state.active_campaigns`, refreshed by
`senderinventory.refresh_linkedin_state` **:437**). Measured live today across
the 32 rostered seats:

```
22 seats @ 8 active campaigns   connLimit 40 -> 4.4/day   (8 seats)
                                connLimit 15-25 -> 1.7-2.8/day
 9 seats @ 12 active campaigns  connLimit 40 -> 3.1/day
 1 seat  @ 13 (174892)          connLimit 40 -> 2.9/day
 1 seat  (139699)               connLimit 0  -> 0         <- MUST be excluded
Sum of marginal shares across all 32: ~99 connection requests/day.
```

Every seat with `activeCampaigns == 0` in the estate (156360, 170308, 181262,
186618, 194061, 201969, 210951) has `authIsValid: false` and `isActive: false`
and is **not** in the productive roster. **There is no idle healthy seat.** The
33 healthy seats are all carrying 8-13 campaigns. So spreading is not free
capacity appearing; it is the same total share drawn from many seats instead of
one — which is exactly the point, since the constraint being solved is
attribution, and the capacity gain (2.9 → ~99/day ceiling) is a side effect.

**Email**:

```
remaining(inbox) = provider_state.daily_limit
                   - actionledger.count_on(today, channel="email",
                                           sender_id=pid, workspace=client)
```

`daily_limit` here is the provider's own per-inbox figure from `/sender-emails`
and is not divided by campaigns — EmailBison's ceiling is per inbox per day.
`None` means unknown and an unknown-limit inbox contributes **zero** weight
(`senderidentity`'s rule at **:43-52**: an invented limit is worse than an
absent one).

### Step 3 — the deterministic weighted pick

```python
def allocate_weighted(client, contact_key, channel, candidates, snapshot):
    # candidates: [{"sender": person, "accounts": [...]}, ...]
    units = []                              # (sender_id, account_id) repeated
    for entry in sorted(candidates, key=lambda e: e["sender"]["sender_id"]):
        for acct in sorted(entry["accounts"], key=lambda a: a["account_id"]):
            w = int(max(0, math.floor(snapshot.remaining(acct))))
            units += [(entry["sender"]["sender_id"], acct["account_id"])] * w
    if not units:
        raise NoEligibleSender(
            f"no {channel} account in {client} has remaining capacity today")
    return units[_slot(f"{contact_key}:{channel}", len(units))]
```

- `_slot` is `assignment._slot` **:70-77** — sha1, not Python's salted `hash`,
  and shared with `senders._slot` on purpose so two allocators cannot disagree.
- Ordering is by id, so the unit array is identical everywhere.
- Weighting by whole units of remaining capacity makes the distribution
  proportional to what each account can actually carry, with no float
  comparison and no tie-break by clock.
- A pairing still wins: `prefer_sender_id` (**:151**, honoured at **:166-170**)
  is applied before the weighted pick, exactly as today.

### Step 4 — freeze it

The result is written by `ensure` and never recomputed (**:213-214**). The
capacity snapshot is fingerprinted onto the block (`capacity_digest`,
`capacity_read_at`) so `is_stale` **:320-330** can report "allocated against a
picture that has since changed" as a fact for a screen — never as a trigger.
Capacity changing is not a reason to move a prospect between humans.

## 4.6 Migration — what happens to prospects who are already live

**The rule: the provider's record wins, and it is COPIED, never recomputed. A
prospect who has already been in a campaign keeps the human who was on it. If
that human cannot be established, the campaign is refused — the prospect is not
moved.**

A new, narrow function, not `allocate`:

```python
def adopt_from_provider(rec, contact, workspace, channel, provider_account_id,
                        by, evidence):
    """Record the owner a prospect ALREADY has, from provider truth.

    Refuses when `sender_assignment[channel]` is already set - adoption is for
    a prospect the allocator never reached, and overwriting a stored
    assignment is `reassign`'s job and needs a reason.
    Refuses when the account resolves to no attested human - an unattributable
    live prospect is a refusal to report, not an owner to invent.
    `evidence` names the read it came from, e.g.
    "heyreach /campaign/GetLeadsFromCampaign 605732 @ 2026-09-17T09:06Z".
    """
```

`via: "adopted"`, `owner_source: "provider_backfill"`, and the evidence string
on the row.

### HeyReach 605732 — 3 leads on 174892

1. Attest `li-174892` to a human. `/li_account/GetAll` gives `Bruno Gudelj /
   brunogudelj@gmail.com` and the roster row gives
   `profile_url: linkedin.com/in/brunogudelj`. That is evidence, not an
   attestation; an operator says the word and `senderownership.attest` records
   who said it and when. **No `sender` row for Bruno exists in `productive`
   today** — the seven that exist are anna/mark/john/sarah/petar/tom/sara_s —
   so a `new_sender` row is created first.
2. `adopt_from_provider` for each of the three contacts, `provider_account_id`
   taken from `linkedInSenderId` on the live read (all three: `174892`).
3. Re-run the readback. `lead_owner` = `{3 urls: "174892"}` on both sides.
4. The new predicate now passes for 605732 **and nobody moved.** Clause (7) is
   satisfied trivially: the only human in their history is the one adopted.

Nothing about the campaign changes. Its `senders.linkedin` stays `[174892]`;
arity 1 is still permitted, it is simply no longer what does the proving.

### EmailBison 487 — 10 leads, 0 sent, 0 scheduled rows, two humans' inboxes

There is nothing to adopt. `scheduled-emails` returns **0 rows**, so the
provider has not chosen an inbox for any of the ten, and no prospect has
experienced anything (`emails_sent: 0`, `total_leads_contacted: 0`, every
lead's `lead_campaign_data` reads `sending_paused`). Adopting would mean
inventing.

Under Phase A (4.4) the campaign fails on clause 3: `{resolve_owner(2736),
resolve_owner(3941)}` is `{Bojan Rendulic, Bernarda Vrbat}` — two humans. The
operator's decision on 487 therefore has exactly two safe shapes:

- **(a)** Bind only inboxes belonging to one attested human, attest them, then
  activate. Bernarda Vrbat holds 58 inboxes in this estate, which is ample
  capacity under one name; 2736 (Bojan) and 3941 (Bernarda) cannot both stay.
  Note 3941 is `health: warming` and is refused by `executionguard.py:642`
  regardless — that check stays.
- **(b)** Leave it paused.

Both are decisions for a person. Neither is a code change and neither is in
this design's gift.

### The general rule for any other live prospect

| situation | what happens |
|---|---|
| provider names a seat, seat resolves to an attested human | `adopt_from_provider`; the prospect keeps that human |
| provider names a seat, seat has **no** attested owner | the campaign is **refused** at gate `attribution` until somebody attests it. The prospect is not reassigned. |
| provider names no seat (email, pre-activation) | there is nothing to adopt; the campaign must satisfy Phase A instead |
| our record and the provider disagree | **refuse, and report both.** Never silently adopt the provider's answer for a prospect we already told ourselves belonged to somebody else — that is the reassignment `reassign` exists to make answerable. |

## 4.7 Where EmailBison genuinely cannot support this, and the honest fallback

**Cannot be done.** Per-lead sender binding on EmailBison. There is no write
route (`WRITE_ROUTES`, `bison.py:405-436` — the only sender verb is
campaign-level `attach-sender-emails`), no field on the lead payload
(`build_leads` **:262-306**) and none on the lead row (verified on live lead
203809). The inbox is the provider's choice.

**Cannot be done before activation.** Reading which inbox a given lead will use.
The only route that carries it is the scheduled-email queue, and the queue does
not exist until the campaign runs — measured today: 487 → 0 rows, 481 → 0, 485
→ 0, against 352 (active) → 95,724 and 451 (completed) → 1.

**The honest fallback, and why it is not a weakening.**

> On email, a guarded campaign may bind **any number of inboxes** and must bind
> **exactly one attested human**. Per-lead attribution is satisfied by
> construction: whichever inbox the provider rotates to, the human the prospect
> hears from is the same one, and `resolve_owner` can name them from any reply
> (`assignment.resolve_reply_owner`, **:392-428**, already does this join).

Measured against the old rule this is stricter on the thing that matters and
looser only on the thing that does not:

| | old rule | email fallback |
|---|---|---|
| inboxes per campaign | **1** | many |
| **humans per campaign** | 1, unproven — nothing checked whose inbox it was | **1, attested, with an actor and a timestamp** |
| provider agreement | sender *set* only (`configdiff._ids`) | sender set pre-activation **+ per-lead queue assertion post-activation** |
| what a prospect experiences | one inbox, unknown human | one human, several of their inboxes |

Campaign 487 is the case in point: under the old rule it is refused for naming
two ids; under this fallback it is refused for naming **two people**, which is
the actual harm, and it would be *permitted* to name six of Bernarda Vrbat's
inboxes — more capacity, under a stronger guarantee.

What must be written down beside it, in `PRODUCT-GAPS.md`, without softening:
**on the email channel this system cannot prove which inbox a specific prospect
will hear from until after the campaign has started, and it can never choose.
The guarantee it offers is about the human, not the inbox.** That sentence is
the whole difference between the two channels and must not be allowed to blur.

---

# PART 5 — WHAT THIS DESIGN DOES NOT CLAIM

## 5.1 Named UNKNOWNs (each needs an experiment on a non-sending campaign)

1. **UNKNOWN — does HeyReach honour a per-lead `linkedInAccountId` that is not
   attached to the campaign?** `build_lead_pairs` has always sent the field but
   every value it has ever sent equalled the campaign's single seat. Untested
   with a heterogeneous pair set. Must be established on a DRAFT campaign,
   readback via `lead_owner`, before any multi-seat campaign is authorized.
2. **UNKNOWN — does HeyReach re-rotate a lead's seat after the add?** All three
   605732 leads read `request_pending` (`InSequence / None / None`), so no lead
   in this estate has yet been observed *after* its first action. The design
   assumes `linkedInSenderId` is stable once set and **must not** be shipped on
   that assumption: the readback is the authority and should be re-taken before
   each subsequent step, not only before activation.
3. **UNKNOWN — is EmailBison's per-lead inbox stable across a pause/resume?**
   Stability *within* one materialization is measured (83 leads on campaign 352,
   zero with more than one `sender_email.id`). Stability *across* a
   re-materialization is not, and Phase B's detector is what would catch it.
4. **UNKNOWN — EmailBison's per-inbox `daily_limit` is configured, not
   remaining.** No route exposes remaining-today. The ledger subtraction in 4.5
   counts only what *this system* sent; campaigns 352/328/327 send from the same
   estate outside this system's ledger, so the email weights are an upper bound.
   `li_readiness` (`senderinventory.py:267-269`) already refuses to promise a
   remaining figure, and this design must not either.
5. **UNKNOWN — whether the 12 EmailBison display names correspond to 12 real
   people who consent to being named.** A display name is evidence for an
   attestation, never a substitute for one.

## 5.2 What is deliberately not proposed

- **No gate is weakened.** `_sender_for`'s arity check is *replaced* by a
  predicate that implies it (4.3), not deleted. Until that predicate is
  implemented and its clause (6) readback exists, the arity check must stay
  exactly as it is — including for campaign 487.
- **The `warming` health refusal stays** (`executionguard.py:642`). The three
  free inboxes remain unusable. Warming is a deliverability state, not a
  permissions problem, and the answer to it is time.
- **`senderinventory` keeps setting `sender_id=None`.** Ownership never becomes
  derivable from provider truth.
- **The stoppability cap stays** (`executionguard.py:745-760`). Multi-sender
  attribution changes who sends; it does not give this system a LinkedIn pause
  verb, and `UNSTOPPABLE_CHANNEL_CAP = 1` is a statement about that.

## 5.3 Tests that must change, and how

Two tests assert the rule being replaced
(`tests/test_no_write_happens_without_every_gate.py`):

- **:624-628** `test_two_senders_are_refused_even_when_both_were_approved` —
  becomes `test_two_senders_are_refused_when_they_are_two_people`, and gains a
  sibling asserting that two seats attested to the **same** human, with a
  `lead_owner` readback that agrees per lead, **pass**.
- **:965-969** `test_a_seat_with_no_human_owner_still_passes` — **inverts.**
  Under the new predicate `sender_id: None` with no attestation is precisely
  what must refuse (clause 3). This is the single clearest measure of whether
  the change is a strengthening: the test whose name says an unowned seat
  passes has to stop being true.

The tests at **:970-989** (uninventoried seat, deactivated seat, unhealthy
seat, another client's seat) are unaffected — clause (3) preserves all four.

---

# PROVENANCE

All provider calls 2026-09-17, READ-ONLY. No write route was invoked. HeyReach
605732 and EmailBison 487 were read and not modified. Nothing under `src/` was
edited and nothing was committed.

**HeyReach**
- `POST /campaign/GetLeadsFromCampaign {campaignId: 605732}` → 3 leads,
  `linkedInSenderId: 174892` on all three
- `GET /campaign/GetById 605732` → `IN_PROGRESS`, `campaignAccountIds: [174892]`
- `POST /li_account/GetAll` → 41 seats, 33 healthy, seat 174892
  `activeCampaigns: 13`, `connectioRequestLimit: 40`

**EmailBison** (credential bound to workspace 10 `PRODUCTIVE`, asserted)
- `GET /campaigns/487` → `paused`, `total_leads: 10`, `emails_sent: 0`
- `GET /campaigns/487/sender-emails` → `[2736, 3941]`
- `GET /campaigns/{487,481,485}/scheduled-emails` → `meta.total: 0` on all three
- `GET /campaigns/451/scheduled-emails` → 1 row, `sent`, `sender_email.id: 3948`
- `GET /campaigns/352/scheduled-emails` pages 1-5, 50, 200, 500 → 83 distinct
  leads, 22 distinct inboxes, **0 leads with more than one sender**
- `GET /leads/203809` → no sender field on the row
- `GET /sender-emails` → 225/225 (`meta.total: 225`), 12 distinct display names
- `GET /campaigns` → 24 campaigns

**Local**
- `work/senders.jsonl` — 285 rows; 225+32 productive accounts, all
  `sender_id: null`; **0 `ownership_attestation` rows**
- `work/campaigns.jsonl` — 17 rows; `productive-linkedin-cohort-v2` → 605732,
  `productive-email-control-v3` → 487
- `src.assignment.eligible_senders('productive', ·)` → `[]` on both channels;
  `allocate` → `NoEligibleSender`; `ensure` → `unavailable` on both
