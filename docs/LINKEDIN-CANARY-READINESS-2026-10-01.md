# LINKEDIN CANARY READINESS — 2026-10-01

Phase 1, ground-up, READ-ONLY. No candidate picked. No store write, no provider
write, no credential printed. GETs and the allowlisted read-POSTs in
`src/providers/heyreach.py` only. Repo at master `617f910e`.

**An email GO is not a LinkedIn GO.** Nothing here carries over from the email
track and nothing here grants one.

Person-level detail — names, profile URLs, emails — is in
`C:\Users\Zvonimir\Desktop\resonate-canary-log\linkedin-canary-2026-10-01.txt`
and nowhere in this repo. This file carries counts and company domains only.

## VERDICT: NOT READY. The sender cannot be attributed. STOP.

The operator's own condition — *"if you cannot establish whose account it is, or
it is not Productive/Ivan, STOP"* — is met as a STOP, by test, twice over.

---

## 1. WHICH LINKEDIN ACCOUNT WOULD SEND — STOP

**CLAIM** The seat a canary would send from cannot be attributed to a human by
this system, and the one campaign already named for the job is not on Ivan's seat.

**AUTHORITY** `heyreach.all_li_accounts()` (live), `docs/state/PROVIDER-CAMPAIGNS.json`,
`work/senders.jsonl`, `src/senderownership.one_attested_human`, `src/seatledger.daily`.

**MEASURED AT** 2026-10-01, live provider read.

**STATE**

- 41 seats, 33 active with valid auth. Exactly **one** is on the `productive.io`
  domain: **seat 174810, Ivan Mamić** — limits 40/day connection requests,
  40/day messages, no cooldown, `activeCampaigns: 8`.
- **The campaign literally named `RESONATE - PRODUCTIVE LINKEDIN CANARY - CONTROL`
  (604869) is attached to seat 174892, not 174810.** 174892 is a
  `gmail.com`-domain seat attested to a different human who is not at Productive.
  So the pre-built canary would send as somebody else.
- `senderownership.one_attested_human` **refuses every one of the 35 roster seats
  — 0 resolve.** Two distinct failures, both measured:
  - seat **174810 is not in the roster at all** (`NotOneHuman: ... are not in
    productive's roster`). There is no `linkedin_account` row for the only
    Productive-domain seat.
  - the other 32 fail `no attested owner` because the 33 LinkedIn
    `ownership_attestation` rows are keyed **`hr-<id>`** while the
    `linkedin_account` rows are keyed **`li-<id>`**. Intersection of the two key
    sets: **0 of 35**. The attestations exist and never join. Every
    `linkedin_account` row carries `sender_id: null`.
  The email side does join: `eb-2778` attestation ↔ `eb-2778` account row.
- **A seat is not a campaign, and it bites here.** `seatledger.daily("174810",
  today)` → `REFUSED / client_usage_unknown / remaining: UNKNOWN`. Permanent, not
  stale: `_is_exclusive` needs `campaigns_total == campaigns_created_by_resonate`,
  and the account is **121 total vs 40 ours**. No walk of our ledger can ever
  prove room on a shared seat.
- The 8 campaigns active on seat 174810 are, every one of them, campaigns we do
  not own (see item 6a).

**MISSING CHECK** Nothing binds a HeyReach seat to an attested human. The fix is
one key: make the attestation and the account row agree on the prefix, and add a
roster row for 174810. Until then no LinkedIn send is attributable.

## 2. IDENTITY CONSISTENCY — MISMATCH, same class as email

**CLAIM** LinkedIn has the same first-name-only mismatch as email, plus a
cross-channel spelling divergence.

**AUTHORITY** `clients.sender_identity`, `src/sendersignature.py`, live seat read,
`work/senders.jsonl`.

**MEASURED AT** 2026-10-01.

**STATE** `sender_identity.name` is **`"Ivan"`** and the composed signature is
`"Ivan\nProductive"`. The LinkedIn seat's provider display name is **"Ivan Mamić"**
(c-acute). The email mailbox is `i.mamic@withproductive-ai.com`, attested to
`"ivan"`, and the operator's measured From name is "Ivan Mamic" (**no diacritic**).

So: we render a bare first name on both channels; the LinkedIn profile shows the
surname with a diacritic and the mailbox shows it without. A connection request
carries no signature, so the LinkedIn exposure is narrower than email's — but the
two channels do not spell the same person the same way, and
`linkedin_note_mode: llm` means a model writes the self-introduction fresh each
time (`prompts/linkedin_note.md:31` requires it to say who is contacting).

**MISSING CHECK** No test asserts the rendered name matches the sending seat's
provider name on LinkedIn. `sendersignature` has a duplicate-signature guard and
no name-agreement guard.

## 3. THE 9 ACCEPTED CONNECTIONS — CONFIRMED, and nothing enforces them

**CLAIM** There are exactly 9 real accepted connections; 8 got no human reply; 1
replied negatively. No gate marks any of them as the operator's.

**AUTHORITY** `heyreach.campaign_leads` + `campaign_stats` across all 40
campaigns we own (live), joined to `work/queue.jsonl` by canonical profile URL;
`eligibility.decide`.

**MEASURED AT** 2026-10-01, live.

**STATE** Across our 40 campaigns: 133 `request_sent`, 9 `request_pending`,
**8 `accepted`**, **2 `replied`**, 4 `failed`, 2 `unknown`. Ten distinct profiles
are accepted-or-replied. Nine are in `work/queue.jsonl`; the tenth is the
operator's own test identity. **9 real people — matches the handoff's "nine
accepted connections, eight of whom got no human reply" exactly.**

Company domains (9, one person each — no names):
`sodaandlime.com`, `reboundb2b.com`, `digitalposition.com`, `vigorant.com`,
`datashake.fr`, `the-wants-social.com`, `lafayetteamerican.com`,
`sullivannyc.com`, `studionorth.com`.

Campaigns: one each on 613726, 613727, 613729, 613731, 613734, 613736, 613738,
613744, 613761 — all `RESONATE PRODUCTIVE LI B1 SEAT <id>`, all PAUSED.

Replies: **1 of 9** — `studionorth.com`, the negative reply. The other 8 have
`stopped: null`.

**Three findings the operator needs:**

1. **Nothing enforces "do not touch these 9."** Tested: all 8
   accepted-no-reply contacts return **`held`**, not `blocked` — `held:approval_stale`
   on email, `held:draft_not_approved` on LinkedIn. A hold is lifted by an
   approval. None of the 9 is in `config/operator-exclusions.jsonl`
   (`blocks_address` and `blocks_domain` both False) or in `agency-dnc`
   (`agencydnc.lookup` False). The exclusion lives only in the operator's
   instruction.
2. **The provider's own counter disagrees with its lead rows.** 613738 reports
   `connectionsAccepted: 0` while its lead row reads `accepted`. Do not use
   `campaign_stats` to count accepted connections; enumerate leads.
3. **The test-identity exclusion is blind.** `testidentity.LINKEDIN_SLUGS` holds
   the vanity slug only; HeyReach returned the obfuscated `ACoAA…` URN for that
   profile and `testidentity.matches()` returned **False**. The operator's own
   test reply would be counted as a real prospect reply in any report that
   filters this way.

## 4. THE INBOX — PRIOR FINDING CONFIRMED, and worse than stated

**CLAIM** The inbox is overwhelmingly not ours, a seat is not a campaign, and a
conversation object cannot be attributed to a campaign at all.

**AUTHORITY** `heyreach.conversations` with the measured filter allowlist, live.

**MEASURED AT** 2026-10-01.

**STATE**

| filter | conversations |
|---|---|
| none | **27,785** |
| our 40 campaign ids | **10** |
| seat 174810 (Ivan) alone | **360** |
| campaign 613741 (our B1 on seat 174810) | **0** |
| our 40 campaigns AND seat 174810 | **0** |
| 565765 (owner UNKNOWN, live) | 132 |
| 523987 `FIXED - OMEGA` (owner UNKNOWN, live) | 10 |

Ours is **10 of 27,785 — 0.04%.** Confirmed, and the count has grown (26,039 on
09-13 → 27,785 today). Seat 174810 carries 360 conversations and **none** belong
to our campaign on it: the clearest possible demonstration that a seat is not a
campaign.

**How a reply is attributed — and the hole.** A conversation object's only
attribution fields are `linkedInAccountId` and the nested `linkedInAccount`
object. **There is no `campaignId` on a conversation, at all.** Attribution is
possible only by re-querying with a `campaignIds` filter — the server honours it,
the payload does not record it. Downstream, `adapters._heyreach_event` attributes
by `customUserFields.contact_key`; a conversation with no such field lands with
`contact: None` and `eligibility._replied` can never match it.

**MISSING CHECK** Nothing reconciles "this conversation" to "this campaign" from
a stored payload. A reply-stop built on the inbox must carry the campaign id it
filtered by, because the row cannot be re-attributed later.

## 5. WHAT `li1` ACTUALLY IS — TWO CONTRADICTORY DEFINITIONS

**CLAIM** The checkpoint cannot yet state the exact action, because two live code
paths define `li1` differently and the one that built the real campaigns sends an
empty note.

**AUTHORITY** `config/clients/productive.yaml`, `src/cadencelibrary.py:349-387`,
`src/lint.py:516-626`, `config/linkedin/productive-standard.json`,
`scripts/batch_linkedin_push.py`.

**MEASURED AT** 2026-10-01, static.

**STATE**

- Canonical cadence `productive_li_heavy_v1`: **`li1`, day 1,
  `linkedin_action: connect`, template `linkedin_intro`, `generated: false`** —
  a connection request. `li2..li5` are messages requiring `connected`. (Five
  writer keys, not six; prose elsewhere still says li1..li6.)
- `config/clients/productive.yaml`'s `linkedin_sequence` block holds **no steps**
  — only `fallbacks`. The steps come from `cadence: productive_li_heavy_v1`.
  `linkedin_connection_note.mode: llm`.
- **Path A, the engine:** `li1` is a connection request **with a mandatory
  non-empty note**. `heyreach._copy("connection_note", …)` → `_check_words`,
  which raises `SequenceInvalid` on an empty note. Lint caps it at
  `NOTE_MAX_CHARS = 300` (LinkedIn's own limit) with a 40-char floor, applied via
  `is_connection_note(step)` → `step["requires"] not in {"connected",
  "connection_accepted"}`, true for `li1` alone.
- **Path B, what actually built the 33 B1 campaigns:**
  `scripts/batch_linkedin_push.py` posts `config/linkedin/productive-standard.json`
  verbatim. Its `CONNECTION_REQUEST` node carries `payload.messages: [""]` and
  `fallbackMessage: ""` — **zero characters, no note** — permitted by
  `_check_optional_note` under the 2026-09-22 operator decision. That script
  calls **no lint, no approval, no claims gate at all.**

**So the honest answer to "with or without a note?" is: both, depending on which
builder runs, and the builder that has actually run sends without one.** A
checkpoint cannot state the exact action until one path is chosen.

**MISSING CHECK** `_copy`/`_check_words` and `_check_optional_note` disagree about
the same empty note. Nothing asserts that the graph pushed to the provider is the
graph the cadence and lint describe.

## 6. THE GATES ON THE LINKEDIN SEND PATH

**CLAIM** `_linkedin_checks` runs 7 checks; the gravest problem is that the
production LinkedIn write paths never call it.

**AUTHORITY** `src/eligibility.py:882-923` (`_linkedin_checks`), `:792-878`
(`_email_checks`), `:775` (dispatch), `src/heyreachfactory.py:1225`,
`src/providerwrites.py:1469`.

**MEASURED AT** 2026-10-01, static.

**STATE — what it runs,** in order: `no_linkedin_profile` → `draft_not_approved`
(empty note) → `awaiting_dependency` → `lint.check_linkedin` →
`claims.verify` → `evidence_aged_out` → `approval_stale`.

**What it does not, and what is blind:**

- **a) `provider_truth.campaign_owner` is never consulted on any send path.**
  Zero matches for `campaign_owner` under `src/`; it lives only in
  `scripts/provider_truth.py`. The only `src/` reader of
  `PROVIDER-CAMPAIGNS.json` is `seatledger`, and it reads the seat keys, never
  `owner`. So "anyone in an owner-UNKNOWN campaign is NOT CLEAN" **has no
  enforcement point.** Worse, on the HeyReach half `provider_truth.main()` still
  calls the **boolean** `owned_by_resonate` (line 419); the three-state
  `campaign_owner` is wired to EmailBison only (line 380), and the persisted
  `docs/state/PROVIDER-CAMPAIGNS.json` still carries the old `client_or_other`
  vocabulary with no owner field on HeyReach entries at all.
  **Computed here, read-only, applying the same standard the operator set:
  of 121 HeyReach campaigns — 40 ours, 5 client, 76 UNKNOWN. ALL 12
  IN_PROGRESS campaigns are owner-UNKNOWN, and seat 174810 is attached to 8 of
  them, whose lead lists total 33,710 (`PRODUCTIVE - OMEGA`), 50,563, 11,128 and
  1,000 people.** By the operator's rule every one of those is NOT CLEAN, and
  nothing in the send path can see it.
- **b) `_claim_detail(unsupported)` is still duplicated** at `eligibility.py:910`.
  Not a wrong verdict — `_decide` takes `reasons[0]` — but `summarise()`
  double-counts every LinkedIn claim detail and `require()` repeats each twice.
  Email calls it once.
- **c) `domains_contact_no_angle` is now enforced on both**, but narrower on
  LinkedIn: email asks it over `send_scope(rec, contact)`, LinkedIn about this
  contact only (`lint.py:588-590` vs `499-501`). Documented, not blind.
- **d) `_operator_excluded` is blind to a LinkedIn-only person.** Both
  person-level questions sit behind `if "@" in email` (`eligibility.py:333-338`),
  and `operatorexclusion` has no profile-URL key — only `account_key(domain)` and
  `address_key(email)`. A contact with a profile and no email is tested against
  the record domain alone.
- **e) `_client_own_domain` cannot fire on LinkedIn** — derived solely from the
  contact's email (`:387-388`). A connection request to the client's own staff
  passes.
- **f) No verification / identity-confidence gate on LinkedIn.** Email runs
  `lint.sendable` + `verification.resolve`; LinkedIn runs nothing equivalent.
  `channels.IDENTITY_UNCERTAIN` is consulted by no gate on either channel.
- **g) No opt-out affordance is ever required of a LinkedIn note** —
  `executionguard.py:606` is `if channel == "email" and not staging:`.
- **h) `greets_the_wrong_person` is not checked on LinkedIn**, though
  `TEMPLATES["linkedin_intro"]` interpolates `{first_name}`.
- **i) LinkedIn is the fall-through default:**
  `checks = (_email_checks if channel == EMAIL else _linkedin_checks)`. Any
  channel value that is not exactly `"email"` — `None`, `"EMAIL"`, a step dict
  with no `channel` — is judged by the LinkedIn gates. Fail-closed, but it names
  the wrong channel and skips bounce/MX/verification entirely.
  `eligibility.for_record` passes no channel at all.
- **j) THE LARGEST ONE.** The only production LinkedIn write paths —
  `heyreachfactory.py:1225` and `providerwrites.py:1469` — call
  `eligibility.must_not_contact` and **never `eligibility.decide`**. On those
  paths the whole of `_linkedin_checks` (profile, lint, 300-char cap, claims,
  evidence age, approval) **is bypassed.** Only `executionguard.authorize`
  reaches it. Combined with item 5, the path that created live campaigns ran no
  content gate of any kind.

## 7. CROSS-CHANNEL STOP — HOLDS at `eligibility.decide`, in both directions

**CLAIM** A LinkedIn negative reply blocks email, an email unsubscribe blocks
LinkedIn, and the block reaches the whole company. Proven by test on synthetic
records *and* on the real production record.

**AUTHORITY** `eligibility.must_not_contact` / `eligibility.decide`, run against
synthetic records and against `work/queue.jsonl` read-only.

**MEASURED AT** 2026-10-01.

**STATE — exact verdicts**

LinkedIn negative reply → email:

    synthetic, LI negative      must_not_contact -> blocked:contact_stopped,
                                                    blocked:company_paused
    decide channel=email  em1   blocked  blocked:contact_stopped
    decide channel=linkedin li1  blocked  blocked:contact_stopped
    colleague, same company     blocked:company_paused

Email unsubscribe → LinkedIn (`li1`), four shapes, all blocked:

    contact.unsubscribed=True            blocked:unsubscribed
    contact.suppressed=True              blocked:unsubscribed
    rec.suppression.unsubscribed=True    blocked:account_suppressed
    contact.stopped(reason=unsubscribe)  blocked:contact_stopped

**Control — the test can fail.** A clean synthetic record fires nothing in
`must_not_contact` and `decide` returns `held: held:draft_not_approved`. Not
`blocked`. So the blocks above are the stop working, not a record that blocks
whatever you ask.

**The real record.** `studionorth.com` — the person who replied "no thank you" —
returns `blocked / blocked:contact_stopped` on **both** `em1` and `li1`, with
`must_not_contact` → `blocked:contact_stopped, blocked:company_paused`. A
synthetic colleague inserted onto that same record returns
`blocked:company_paused`. **She and her company are refused on both channels.
This is not a canary blocker.**

**But two things the operator should hear with it:**

1. **The DNC person and the "no thank you" incident are the same person.** The
   operator listed them as two separate exclusions. Measured: one person, one
   company, one incident — the LinkedIn negative reply of 2026-09-23T11:12:33Z
   that received another message seven minutes later. There is a **second,
   separate** "no thank you" and it is on **email**: `wearebond.com`, EmailBison
   event 1609410, classified negative, drafted for review, never sent. That
   domain is NOT CLEAN too, on both channels, by the same rule.
2. **The gate holds; the path is what failed in September.** The 2026-09-23
   incident happened on a write path that does not call `decide`, and the 15-minute
   automated stop test the push halt waits on **has still never run**
   (`scripts/batch_linkedin_push.py:359-364`). A gate that returns the right
   verdict when asked is not the same as a send path that asks it.

---

## WHAT WOULD SETTLE EACH OPEN ITEM

| # | Missing check | What settles it |
|---|---|---|
| 1 | No seat→human binding resolves | Reconcile the `hr-`/`li-` attestation keys; add a `linkedin_account` roster row for 174810; then `one_attested_human([174810])` must return one human |
| 1 | Seat 174810 is shared, permanently REFUSED | Only an exclusive seat, or an operator decision to accept an unknown denominator in writing |
| 2 | Rendered name vs seat name never compared | A test asserting `sender_identity.name` agrees with the sending seat's provider display name |
| 3 | The 9 are not enforced anywhere | Add all 9 profiles to a LinkedIn-capable exclusion store; `operatorexclusion` needs a profile-URL key first (item 6d) |
| 3 | Test identity blind to obfuscated URNs | Add the `ACoAA…` URN to `testidentity`, or match on provider profile id |
| 4 | Conversations carry no campaign id | Store the campaign id used as the filter alongside every ingested conversation |
| 5 | Two definitions of `li1` | Choose one builder. Until then the checkpoint cannot state the action being approved |
| 6a | `campaign_owner` unused on the send path, and HeyReach still boolean | Give the HeyReach half three-state owners, persist them, and make the LinkedIn gate refuse an owner-UNKNOWN campaign |
| 6j | LinkedIn writes bypass `_linkedin_checks` | Route `heyreachfactory` and `providerwrites` through `eligibility.decide`, then re-run this measurement |
| 7 | Reply-stop never exercised live | The 15-minute automated stop test the halt is waiting on |

**No candidate was selected. Nothing was written to any store. No provider write
of any kind was issued on either provider.**
