# HeyReach sender capacity, read from the provider

Date: 2026-09-17
Method: READ-ONLY. `src.providers.heyreach` read routes only — `/li_account/GetAll`
(41 rows, `totalCount` 41), `/campaign/GetAll` (86 rows, `totalCount` 86),
`/campaign/GetLeadsFromCampaign` (campaign 605732, 3 rows). No write route was
called. Campaign 605732 and EmailBison 487 were not touched.

PII: real names and profile URLs are hashed `sha256(lower(normalised))[:12]`,
the convention `scripts/sender_capacity.py:56` uses. Seat ids, health flags and
numeric limits are not PII and are printed verbatim.

---

## Headline

| | |
|---|---|
| SENDERS_AVAILABLE | **41** |
| SENDERS_ELIGIBLE | **32** |
| BUSY | **32 of 32** — every eligible seat carries someone else's live campaigns |
| FREE (healthy, zero in-progress campaigns) | **0** |
| CAPACITY_PER_SENDER | **exposed** per seat per day; the per-campaign *share* is **UNKNOWN** |
| PROVIDER_CAMPAIGN_SENDER_LIMIT | **UNKNOWN** (not documented). Observed ≥39 in this workspace |
| MAX_SAFE_SENDERS | **1** — seat `174892` — under the code as it stands |

---

## 1. SENDERS_AVAILABLE — 41

`POST /li_account/GetAll` returns 41 rows and `totalCount: 41`.
`heyreach.all_li_accounts` (src/providers/heyreach.py:2799) refuses a short
read, so this is the whole estate and not a first page.

The row carries exactly 15 keys: `id`, `firstName`, `lastName`, `emailAddress`,
`profileUrl`, `isActive`, `authIsValid`, `activeCampaigns`, `accountLimits`,
`isValidNavigator`, `isValidRecruiter`, `connectionRequestCooldown`,
`connectionNoteCooldown`, `inMailCooldown`, `searchCooldown`.

**There is no workspace, tenant, client, owner or team field on a seat.** That
is the finding, not an omission in this report — `src/senderinventory.py:176`
already records it, and section 2 explains what stands in its place.

`activeCampaigns` was verified to be *the count of IN_PROGRESS campaigns whose
`campaignAccountIds` contains this seat* — it matches exactly on all 41 seats
when cross-checked against `/campaign/GetAll`.

### The estate

`attested` = present in `work/senders.jsonl` as a `linkedin_account` row for
workspace `productive`. `health` uses `senderinventory.li_health_of`
(src/senderinventory.py:203).

| seat id | identity(h) | profile(h) | isActive | authIsValid | health | attested | in-progress campaigns | connReq/max | msg | cooldowns |
|---|---|---|---|---|---|---|---|---|---|---|
| 116968 | bfb06aace99a | a7c17803d972 | true | true | ok | yes | 8 | 40/40 | 40 | - |
| 116973 | c4b8c5c7fd26 | c8bb2beebd3b | true | true | ok | yes | 8 | 40/40 | 40 | - |
| 116988 | fe49874b761b | f8ca073e54a9 | true | true | ok | yes | 8 | 40/40 | 40 | - |
| 116989 | c7ad25d068ff | b98bde43a424 | true | true | ok | yes | 8 | 40/40 | 40 | - |
| 119588 | de163884cd4e | 923aaa8d9b34 | true | true | ok | yes | 8 | 40/40 | 40 | - |
| 125748 | c2a7b14ccc3e | dca06af85989 | true | true | ok | yes | 8 | 40/40 | 40 | - |
| 125775 | 2501b1cbf143 | c3ec542234d9 | true | true | ok | yes | 8 | 40/40 | 40 | - |
| 129082 | 9cad4ad7c67d | 1412030b7ac2 | true | true | ok | yes | 8 | 40/40 | 40 | - |
| **129531** | 6f01b59d3bac | 27eb8bb3beeb | true | **false** | **blocked** | NO | 1 | 40/40 | 40 | - |
| 139699 | 5a2429140c70 | 20f4b9a63098 | true | true | ok | yes | 8 | **0**/40 | 40 | - |
| 143105 | 174130483158 | e5e90377181b | true | true | ok | yes | 8 | 25/40 | 40 | connectionRequest |
| **156360** | c96f28534cc7 | 32daa0fa6a00 | **false** | **false** | blocked | NO | 0 | 25/40 | 24 | - |
| 159259 | 0af5fa68e431 | f3ba842cdb15 | true | true | ok | yes | 8 | 25/40 | 25 | connectionRequest |
| 169600 | 6a9f3b2f7db3 | 35c56b922b70 | true | true | ok | yes | 8 | 23/40 | 24 | - |
| **170308** | d58637a655c2 | 6d40e2e555f3 | **false** | **false** | blocked | NO | 0 | 5/40 | 5 | - |
| 174332 | 9e58861fb87e | dee708fbfb15 | true | true | ok | yes | 12 | 40/40 | 40 | - |
| 174742 | c62bbb200b21 | 357045a29147 | true | true | ok | yes | 12 | 40/40 | 40 | - |
| 174748 | 7cc85aecf642 | fc3c5be1739f | true | true | ok | yes | 12 | 40/40 | 40 | - |
| 174797 | ddf3257c8492 | 9ababe615a5d | true | true | ok | yes | 12 | 40/40 | 40 | - |
| 174803 | 9e43475b3b85 | cc81d69b98e2 | true | true | ok | yes | 12 | 40/40 | 40 | - |
| **174810** | 5ed6be298e23 | 75bbdd609e0a | true | true | **ok** | **NO** | **8** | 40/40 | 40 | - |
| 174822 | 39f05f90f56f | 668be49d9e81 | true | true | ok | yes | 12 | 40/40 | 40 | - |
| 174845 | 5112055c28a6 | 624c27fb573f | true | true | ok | yes | 12 | 40/40 | 40 | - |
| **174892** | d7b929fb95a5 | c5544adddff7 | true | true | ok | yes | **13** | 40/40 | 40 | - |
| 175455 | 3b38ee19a1b8 | 61aa4784f4cc | true | true | ok | yes | 12 | 40/40 | 40 | - |
| 175552 | c564c46018e9 | ad3e38475e7e | true | true | ok | yes | 8 | 25/40 | 40 | - |
| 177751 | 1ba930be9311 | d2a2c026a5c2 | true | true | ok | yes | 8 | 17/40 | 17 | - |
| 179527 | 479a8940a199 | c8f11d7d2088 | true | true | ok | yes | 8 | 19/40 | 18 | - |
| **181262** | 69e86b7fc892 | 6fdc61c10c2d | **false** | **false** | blocked | NO | 0 | 15/40 | 5 | - |
| 181653 | b0dd0bf603c0 | ba8821432707 | true | true | ok | yes | 8 | 22/40 | 22 | connectionRequest |
| 181658 | 0e8779efd5c6 | 563caa06e833 | true | true | ok | yes | 8 | 18/40 | 17 | - |
| **186618** | 448ddbfe3679 | 496f55bde163 | **false** | **false** | blocked | NO | 0 | 10/40 | 10 | - |
| 191848 | 40d908e1069c | cf4d16c53b68 | true | true | ok | yes | 8 | 25/40 | 40 | - |
| **194061** | 0b43ce85083e | 9a4cd8ba2816 | **false** | **false** | blocked | NO | 0 | 5/40 | 5 | - |
| 201959 | 618ac60b96e3 | 18b3a6ea92fb | true | true | ok | yes | 8 | 15/40 | 5 | - |
| **201969** | dcd50dfaaaef | d223dc7ed534 | **false** | **false** | blocked | NO | 0 | 15/40 | 5 | - |
| 201978 | 4b3ec378bfb9 | bd699dd50ee0 | true | true | ok | yes | 8 | 25/40 | 40 | - |
| 208242 | 165a02b63af7 | d675fa12d9cc | true | true | ok | yes | 12 | 40/40 | 40 | - |
| 208253 | 388b46b896c4 | 3892979932d6 | true | true | ok | yes | 8 | 40/40 | 40 | - |
| **210951** | 3085e4e44e40 | 2ed05d7147c4 | **false** | **false** | blocked | NO | 0 | 40/40 | 40 | - |
| 212356 | 3248357a4d3e | c55aee7b64a1 | true | true | ok | yes | 8 | 15/40 | 15 | - |

---

## 2. SENDERS_ELIGIBLE — 32

Four criteria, applied in order. Each exclusion names the exact field.

| # | criterion | field tested | excluded | remaining |
|---|---|---|---|---|
| 0 | every seat the provider returns | — | — | 41 |
| 1 | the credential is alive | `authIsValid is not True` | **8**: 129531, 156360, 170308, 181262, 186618, 194061, 201969, 210951 | 33 |
| 2 | the seat is switched on | `isActive is not True` | 0 further (all 7 `isActive:false` seats are already out on criterion 1) | 33 |
| 3 | correct tenant | single `organizationUnitId` = `118832` across all 86 campaigns | 0 | 33 |
| 4 | ours — a human attested it | present in `work/senders.jsonl` as `linkedin_account` / workspace `productive` | **1**: `174810` | **32** |

**Criterion 1 in detail.** `129531` is the dangerous middle state
`scripts/sender_capacity.py:63` names: `isActive: true`, `authIsValid: false`,
and it is still attached to live campaign `523987`. It will accept an
assignment and deliver nothing. The other seven are off at both flags.

**Criterion 3 in detail.** Tenancy cannot be established from a seat row —
there is no tenant field. What *can* be established is that this API key sees
exactly one `organizationUnitId` (`118832`) across all 86 campaigns, so there
is no second tenant visible to segregate against. That is weaker than a
per-seat tenant check and should be read as "no evidence of a second tenant",
not as "tenant verified".

**Criterion 4 in detail — this is the load-bearing one.** Because the provider
exposes no owner, ownership *is* the operator attestation
(`src/senderinventory.py:176-182`, `build_linkedin(..., approved=)` at
src/senderinventory.py:234). Seat **174810** is healthy at the provider,
carries 8 live client campaigns, and is **absent from the canonical roster**.
Its `emailAddress` is on the client's own corporate domain while 37 of the
other 40 are `gmail.com` — consistent with a real client employee rather than
an agency-operated persona — but nothing in the repo records why it was left
out. It is excluded here on the stated rule (unattested ⇒ not ours to use),
not on the domain guess.

**A further exclusion for a cold cohort, stated separately because it is about
the action rather than the seat:** `139699` is healthy and attested but has
`connectioRequestLimit: 0`. It cannot open a connection-request cadence. If the
next campaign's entry action is a connection request, entry-capable eligible
seats are **31**, not 32.

---

## 3. BUSY vs FREE — every eligible seat is busy

**FREE = 0.** There is not one healthy seat in this workspace with zero
in-progress campaigns. The only seats at `activeCampaigns: 0` are the seven
dead ones.

Seat → in-progress campaign counts: 8 campaigns × 17 seats, 12 campaigns ×
9 seats, 13 campaigns × 1 seat (`174892`), 1 campaign × 1 seat (`129531`,
dead).

### What the busy seats are carrying

13 campaigns are `IN_PROGRESS`. **Exactly one is ours**; the other 12 are the
client's own estate and nothing here may disturb them.

| campaign | name | seats | ours? |
|---|---|---|---|
| **605732** | RESONATE - PRODUCTIVE LINKEDIN COHORT V2 - CONTROL | 1 — `174892` | **yes, LIVE** |
| 565765 | PRODUCTIVE - SOFTWARE DEVELOPMENT - JELENA - AUGUST 24 | 33 | client |
| 524013 | FIXED - PRODUCTIVE - MARKETING AGENCIES - USA 2ND | 10 | client |
| 524002 | FIXED - PRODUCTIVE - MARKETING AGENCIES - USA 2ND | 33 | client |
| 524000 | FIXED - PRODUCTIVE - MARKETING AGENCIES INMAIL - EU | 10 | client |
| 523997 | FIXED - PRODUCTIVE - MARKETING AGENCIES - ALL LEADS | 33 | client |
| 523993 | FIXED - PRODUCTIVE - MARKETING AGENCIES - ALL LEADS | 33 | client |
| 523987 | FIXED - OMEGA | 34 | client |
| 523983 | FIXED - OMEGA 2 | 33 | client |
| 523932 | FIXED - OMEGA 3 | 33 | client |
| 523922 | FIXED - OMEGA 3 | 33 | client |
| 523913 | FIXED - PRODUCTIVE - MARKETING AGENCIES - EUROPE | 10 | client |
| 523896 | FIXED - PRODUCTIVE - MARKETING AGENCIES - AUSTRALIA | 10 | client |

Every one of the 32 eligible seats appears in at least 8 of those client
campaigns. **There is no idle capacity to claim; there is only shared capacity
to dilute.** Section 4 is why that distinction decides the answer.

---

## 4. CAPACITY_PER_SENDER

**Per seat per day: EXPOSED.** `accountLimits` carries twelve numbers on every
one of the 41 rows — `connectioRequestLimit`/`connectioRequestMax` (the
provider's own misspelling, kept verbatim at src/senderinventory.py:172),
`messageLimit`/`Max`, `inMailLimit`/`Max`, `profileViewLimit`/`Max`,
`followLimit`/`Max`, `postLikeLimit`/`Max`.

**`connectioRequestLimit` is a configured setting, not a remaining-today
counter.** Measured: all 32 attested seats' `connection_limit` and
`message_limit` are **byte-identical** to the values `work/senders.jsonl`
recorded on 2026-09-13 — zero drift across 4 days and 32 seats. Over the same
window the cooldown flags *did* move (7 seats flagged on 09-13, 3 today), which
is what a genuinely volatile field looks like. This matters because
`src/senderinventory.py:228` reads the same field as `remaining` and its
refusal text says *"no connection requests left against today's limit"* — that
comment is a misreading of the field. The *number* it produces is still right;
the *reason* it gives an operator is wrong.

**Per campaign: UNKNOWN, and not derivable from any read route.** The vendor
documents that limits are per LinkedIn account and *shared*: "The limits are
shared between all campaigns that LinkedIn account is active in", divided
proportionally. No read route exposes the resulting per-campaign share, and it
is not stated here as a number.

The consequence is stated as arithmetic rather than as a measured value:
seat `174892` has `connectioRequestLimit: 40` and 13 in-progress campaigns, so
the share reaching live campaign 605732 is on the order of 40/13 ≈ 3 connection
requests a day. **Adding 605732's seat to a further campaign takes that to
40/14.** Any plan that reuses `174892` for the next cohort is a plan that slows
the campaign that is running right now.

Estate-wide ceiling over the 33 healthy seats — 1,054 connection requests/day,
1,143 messages/day (`docs/state/SENDER-CAPACITY.json`, 2026-09-15) — is what
the provider *allows*, summed. It is not throughput available to a new
campaign, because none of it is unshared.

---

## 5. PROVIDER_CAMPAIGN_SENDER_LIMIT — UNKNOWN

**Not documented.** The vendor's sender-rotation article states you may
"select unlimited LinkedIn senders" per campaign and names no maximum. No
number is available, so none is asserted here.

Two things that are known and are *not* this limit:

- **Observed maximum in this workspace: 39 seats on one campaign** (`467366`
  and `429680`, both PAUSED); 34 on a live one (`523987`). So the real cap,
  whatever it is, is ≥39. This is an observation, not a documented limit.
- **1–100 accounts per API request** — `_change_senders`
  (src/providers/heyreach.py:2144) enforces `1 <= len(seats) <= 100`. That is a
  batch size for `AddLinkedInAccountsToCampaign`, not a per-campaign ceiling;
  the route is additive and can be called repeatedly.

---

## 6. MAX_SAFE_SENDERS — 1, seat `174892`

Not because the estate is small. 32 eligible seats exist. **Because this
repository cannot currently authorize, attribute or keep sticky a campaign
with more than one.** Three blockers, each a specific line:

### Blocker A — the execution guard refuses a multi-seat campaign outright

```
src/executionguard.py:1015
    if len(ids) != 1:
        raise NotAuthorized(
            "sender",
            f"the canonical campaign names {len(ids)} {channel} senders; a "
            f"guarded action is attributed to exactly one")
```

`_sender_for` (src/executionguard.py:993) is on the authorize path. A canonical
campaign naming two seats raises `NotAuthorized` before anything is sent. This
fails closed — it cannot let a bad campaign through — but it means
MAX_SAFE_SENDERS is 1 *by construction* until it is deliberately changed.

### Blocker B — the sticky-assignment pool for LinkedIn is empty

The mechanism for stickiness exists and is correct in shape. The push payload
sets the seat **per lead, not per batch**:

```
src/providers/heyreach.py:55
    "linkedInAccountId": _account_id_for(r, linkedin_account_id),
```

with the comment at src/providers/heyreach.py:50-54 stating exactly the right
reason — "a LinkedIn sender is assigned per contact and sticks to them, so a
single account id for the whole batch would send every prospect from whichever
profile the caller happened to name".

`_account_id_for` (src/providers/heyreach.py:92-106) reads the row's
`provider_account_id` and **falls back to the caller's single
`linkedin_account_id` when the row has none**.

Measured today: that fallback is the only path in use.

- All 32 `linkedin_account` rows for workspace `productive` carry
  `sender_id: null`. `senderinventory.build_linkedin`
  (src/senderinventory.py:252) sets it null on purpose — the provider knows no
  owner.
- `work/senders.jsonl` contains **zero** `ownership_attestation` rows, so
  `senderownership.resolve_owner` (src/senderownership.py:106) returns None for
  every seat.
- Therefore `assignment.eligible_senders('productive', 'linkedin')`
  (src/assignment.py:101) returns `[]`. Executed against live state, confirmed:
  **0 eligible humans on LinkedIn, and 0 on email.**
- `assignment.allocate` (src/assignment.py:150) then raises `NoEligibleSender`,
  and `assignment.ensure` (src/assignment.py:225-231) *swallows* it into
  `block["unavailable"]["linkedin"]` rather than raising.

So no contact ever gets a stored LinkedIn `provider_account_id`, every row hits
the fallback, and the fallback is the hardcoded `SEAT_ID = 174892`
(scripts/activate_linkedin_cohort.py:59, and seven sibling scripts).

**With one seat this is invisible — every prospect lands on 174892 either way.
With two seats it becomes the bug the comment at heyreach.py:50 was written to
prevent**, because nothing would decide which prospect goes to which seat, and
nothing would record the decision to honour on a re-push, repair or settle.

Confirmation that the per-lead binding is real and readable back: all 3 leads
on campaign 605732 return `linkedInSenderId: 174892` from
`/campaign/GetLeadsFromCampaign`, bound at `creationTime` while
`leadCampaignStatus` is still `Pending`. `heyreach.campaign_leads`
(src/providers/heyreach.py:2696) already maps it to `sender_id`. **That field
is the readback a multi-seat stickiness check would be built on, and nothing
outside the provider module and two tests reads it today.**

### Blocker C — no seat can be attributed to a human

`HumanSenderIdentity` is separate from the provider account by design
(src/senderidentity.py:31-38). Today the separation is total: 7 humans exist in
workspace `productive` (`anna`, `john`, `mark`, `petar`, `sara_s`, `sarah`,
`tom`) and **none of them owns any of the 32 real LinkedIn seats**. The three
`linkedin_account` rows that *do* have a `sender_id` belong to the `contactout`
and `demo-client` fixture workspaces.

So when a prospect on any seat replies, `assignment.resolve_reply_owner`
(src/assignment.py:392) resolves to UNKNOWN. One seat makes that survivable —
there is only one profile it can be. N seats makes "which of our colleagues
does this person think they are talking to?" unanswerable N ways.

### Therefore

**MAX_SAFE_SENDERS = 1. Seat id: `174892`.**

And it is 174892 specifically for continuity, not merit: campaign 605732's 3
leads are already bound to it at the provider. Moving them is the exact
prohibited act.

### The conditional answer, if the blockers are cleared

Should Blockers A and B be deliberately fixed — the guard taught to accept a
sender *set*, and per-lead `provider_account_id` actually populated so
`_account_id_for` stops falling back — the defensible set for a **new** campaign
is **9 seats**:

`116968, 116973, 116988, 116989, 119588, 125748, 125775, 129082, 208253`

Derived, not chosen: of the 32 eligible seats, these are the ones that
simultaneously satisfy

1. attested in the canonical roster (criterion 4 above);
2. `isActive && authIsValid`;
3. `connectioRequestLimit == connectioRequestMax == 40` — the provider has
   applied no throttle, which excludes 139699 (0), 212356 and 201959 (15),
   177751 (17), 181658 (18), 179527 (19), 181653 (22), 169600 (23), and
   143105/159259/175552/191848/201978 (25);
4. no cooldown flag set *at this read* — excludes 143105, 159259, 181653;
5. the **lowest** in-progress campaign load in the clean set (8, against 12 for
   the 174332/174742/174748/174797/174803/174822/174845/175455/208242 group).
   Criterion 5 is the throughput criterion: a seat in 8 campaigns contributes
   ≈40/9 ≈ 4.4 requests/day to a ninth, where a seat in 12 contributes
   ≈40/13 ≈ 3.1.

`174892` is deliberately **excluded** from that set. Adding it to a second
campaign divides its 40/day across 14 campaigns instead of 13 and directly
slows live campaign 605732.

Criterion 4 is a point-in-time filter — cooldown flags moved on 4 of 7 seats
between 2026-09-13 and today — so the set must be re-derived at build time, not
copied from this document.

---

## 7. The repo's own inventory, checked against the provider

### `scripts/sender_capacity.py`

Reads `/li_account/GetAll` directly and classifies HEALTHY / AUTH_INVALID /
INACTIVE. Its last output (`docs/state/SENDER-CAPACITY.json`, 2026-09-15) says
41 seats / 33 healthy / 1 auth-invalid / 7 inactive and
`healthy_seats_with_no_active_campaign: 0`. **Re-measured today: identical.**
The script is correct as far as it goes.

Two gaps, neither of which it claims to cover:

- It has **no attestation check**, so its 33 healthy seats include `174810`,
  which is not in the canonical roster. Read as a capacity number, 33 is one
  seat too many.
- Its `unassigned` measure (`state == HEALTHY and not active_campaigns`) is
  the right question asked of the wrong provider. On HeyReach a seat is
  normally in 8–13 campaigns at once, so this metric is structurally pinned at
  0 and gives an operator no signal. The useful measure is the *share* a new
  campaign would get, which needs the campaign count, which this script already
  reads (`active_campaigns`) and does not use.

### `src/senderidentity.py` and `work/senders.jsonl`

Holds **32** `linkedin_account` rows for workspace `productive` (plus 3 fixture
rows in `contactout` / `demo-client`).

**Does the roster agree with the provider? Partially. One material
disagreement, one stale field, one misleading field.**

| | |
|---|---|
| in roster but **not** at the provider | **none** — no phantom seats |
| at the provider but **not** in the roster | **9**: `174810`, `129531`, `156360`, `170308`, `181262`, `186618`, `194061`, `201969`, `210951` |

Eight of those nine are dead at the provider and their absence is correct. **The
ninth is the finding: `174810` is healthy, credential-valid, attached to 8 live
client campaigns, and nobody vetted it.** A roster that disagrees with the
provider in *this* direction is fail-closed — `executionguard`
(src/executionguard.py:610) refuses any seat not in the canonical roster, so
174810 cannot be used by accident. But it means the true eligible population is
either 32 or 33 depending on a human decision nobody has recorded, and that
decision should be written down rather than left as a gap.

**Stale field:** `li-174892.provider_state.active_campaigns` = 12, read
2026-09-13. The provider says 13 today — campaign 605732 is the thirteenth. Any
capacity calculation off the stored roster under-counts 174892's load.

**Misleading field:** every `productive` row carries `daily_limit: 40`,
including `li-139699` whose real `connectioRequestLimit` is **0** and
`li-201959` whose real limit is **15**. This is not a bug in the write —
`senderinventory.build_linkedin` (src/senderinventory.py:257) deliberately
stores `CONNECTION_MAX` (`connectioRequestMax`, the plan ceiling) — but
`senderidentity.roster()` sums `daily_limit` into `known_daily_capacity`
(src/senderidentity.py:545), which therefore reports **1,280/day** for
32 seats where the provider's configured limits total **1,014**. 13 of 32 rows
are affected. **A planner reading `daily_limit` off the roster over-plans the
estate by 26%.** The true per-seat number is present on the same row, under
`provider_state.connection_limit`.

---

## Biggest single risk

**Using more than one seat today silently converts a per-lead binding into a
provider-side coin flip, and nothing in this repo would notice.**

Stickiness currently works by accident of arity. `_account_id_for` falls back to
one hardcoded `SEAT_ID` because the assignment pool is empty
(`eligible_senders` → `[]`, measured), so every prospect lands on 174892 and the
binding is trivially stable. Attach a second seat and the fallback no longer
determines anything: HeyReach's own rotation picks, the pick is recorded only at
the provider (`linkedInSenderId`, which nothing outside the provider module
reads), and any re-push, settle or repair that re-enters the add path can bind
the same prospect to a different human's LinkedIn profile. The prospect sees a
second stranger continuing the first stranger's conversation. There is no
alarm for this — `configdiff._ids` compares the campaign's *sender set*, not
which lead sits on which seat, so the campaign would read as correctly
configured throughout.

`executionguard.py:1015` is the only thing standing in front of it, and it is
standing there for an unrelated reason (attribution of a guarded action). It
should not be relaxed to gain sender capacity until per-lead assignment
actually populates.

---

## Provenance

- `POST /li_account/GetAll` — 41 rows, `totalCount` 41, 2026-09-17
- `POST /campaign/GetAll` — 86 rows, `totalCount` 86, 2026-09-17
- `POST /campaign/GetLeadsFromCampaign` `{campaignId: 605732}` — 3 rows, 2026-09-17
- `work/senders.jsonl` — 35 `linkedin_account` rows, 32 in workspace `productive`, written 2026-09-13
- `docs/state/SENDER-CAPACITY.json` — generated 2026-09-15
- Vendor: HeyReach help centre, "How to configure my Sending Limits?" and
  "Multiple LinkedIn senders on one campaign (Sender rotation)"

No provider write route was called. Campaign 605732 and EmailBison 487 were
read but not modified. No file under `src/` was edited.

---

## Amendment, 2026-09-17 — the two reporting defects above are fixed

This audit read the provider and changed nothing. A follow-up changed
`src/senderinventory.py` only, to make the repository report what the audit
measured. Still READ-ONLY against both providers: no write route was called,
campaign 605732 and EmailBison 487 were not touched, and no `--live` was run,
so `work/senders.jsonl` on disk is unchanged and still holds the stale values
described below.

### Which `accountLimits` member means what — established, not inferred

`POST /li_account/GetAll`, 41 seats, re-read 2026-09-17. The twelve numbers are
six `<action>Limit` / `<action>Max` pairs, and the pairing is not symmetric:

| | `connectioRequestLimit` | `connectioRequestMax` |
|---|---|---|
| distinct values over 41 seats | 0, 5, 10, 15, 17, 18, 19, 22, 23, 25, 40 | **40, and only 40** |
| on the 8 seats with a dead credential | varies (5 – 40) | 40 |
| `Limit > Max` anywhere | never | — |

The same shape holds for `messageLimit`/`messageLimitMax`,
`inMailLimit`/`inMailLimitMax`, `profileViewLimit`/`profileViewLimitMax`,
`followLimit`/`followLimitMax` and `postLikeLimit`/`postLikeLimitMax`: the
`...Limit` member varies per seat, the `...Max` member is 40 on every row.

A number identical on a seat carrying thirteen live campaigns and on a seat
whose credential is dead is a plan ceiling, not that seat's allowance. So:

- **`connectioRequestLimit` is the CONFIGURED daily limit.**
- **`connectioRequestMax` is the plan ceiling it may be configured up to.**
- **Neither is remaining-today, and no field anywhere is.** Fifteen keys on the
  seat row and twelve numbers in `accountLimits`; not one of the twenty-seven
  is a used-today or left-today count. Remaining today is **UNKNOWN** and is
  now reported as the word, never as a number.

### The corrected numbers

| | value | field it comes from |
|---|---|---|
| Configured connection capacity, 32 rostered seats | **1,014/day** | Σ `accountLimits.connectioRequestLimit` |
| Plan ceiling, same 32 seats | 1,280/day | Σ `accountLimits.connectioRequestMax` = 40 × 32 |
| Over-report the roster used to carry | **+26.2%** | the ceiling reported as the capacity |
| Remaining today | **UNKNOWN** | no such field exists |
| Rostered seats affected | 13 of 32 | `connectioRequestLimit != connectioRequestMax` |

Section 7's "1,280/day where the provider's configured limits total 1,014"
stands; `senderidentity.roster()` now reports 1,014 from rows built after the
fix. `docs/state/SENDER-CAPACITY.json`'s 1,054 was always correct —
`scripts/sender_capacity.py` read `connectioRequestLimit` all along; the
difference from 1,014 is seat `174810`, which that script counts and the
roster does not.

### What changed

- `senderinventory.build_linkedin` stores `connectioRequestLimit` as
  `daily_limit`. The ceiling is kept under `provider_state.connection_max`.
- `senderinventory.li_readiness` no longer tells an operator that a seat has
  "no connection requests left against today's limit". It says the configured
  limit is 0, which is what is true and does not imply waiting for midnight.
- The LinkedIn report separates `connection_capacity_per_day` (configured)
  from `connection_plan_ceiling_per_day` (the ceiling), and
  `connection_remaining_today` is the string `"unknown"` — a word rather than
  `None` so that `int(x or 0)` and `sum()` cannot turn it back into a zero.
- `senderinventory.reconcile_linkedin` reports the attestation gap and the
  drift between the stored roster and provider truth, and refreshes the
  provider-owned fields of seats already in the roster. Reachable as
  `python -m src.senderinventory --workspace productive --reconcile-linkedin`.

### Seat 174810 is still not in the roster, and now it is on the record

The gap is reported rather than closed. `reconcile_linkedin` lists all nine
provider seats the roster does not name with each one's eligibility in the
provider's own fields — the eight dead ones as not eligible, `174810` as
eligible at the provider and `usable: false` — and the live run against the
provider today returns `unrostered_but_eligible: ["174810"]`.

Nothing here attests it. Section 2's criterion 4 is unchanged: HeyReach has no
owner field, so attestation is an operator's decision about whose LinkedIn
profile speaks to a stranger, and the reconcile write-back adds no rows at all.
**That decision is still open and is now the only thing standing between "32
eligible" and "33".**

### Still stale on disk, and what closes it

`work/senders.jsonl` was written 2026-09-13 and no `--live` was run, so it
still holds `daily_limit: 40` on all 32 rows and
`li-174892.provider_state.active_campaigns: 12` against the provider's 13. The
dry reconcile reports all 14 drifted fields. An operator closes it with

    python -m src.senderinventory --workspace productive --reconcile-linkedin --live

which rewrites the provider-owned fields of the 32 rostered seats and adds
none. Until then, read capacity from the reconcile report rather than from the
stored roster.

### Not fixed

- `scripts/sender_capacity.py` still has no attestation check, so its
  "33 healthy" and its 1,054/day both include `174810`. Section 7 already
  records this; the fix above did not touch that script.
- `senderinventory` has a constant for `messageLimit` but none for
  `messageLimitMax`, so the message ceiling is not stored. Nothing reads it
  today.
