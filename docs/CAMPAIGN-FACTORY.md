# The Campaign Factory

How a qualified, enriched, verified, eligible contact becomes a provider-staged
campaign, using the modules that already exist.

This document proposes **no new module and one new field**. That is the finding,
not modesty: every object a campaign factory appears to need is already in this
repository under a different name, and building a second one would be the
"parallel state machine for the same fact" CLAUDE.md names as how two
representations drift.

Read with `PLAYBOOK.md`, `ACCOUNT-OUTREACH.md`, `LIVE-READINESS.md` and
`RELEASE-CANDIDATE.md`. Nothing here relaxes any of them.

---

## 1. Reuse before inventing

| Object a factory seems to need | What already plays that role | New? |
|---|---|---|
| `CampaignIntent` | the `work/campaigns.jsonl` row built by `campaigns.new_campaign()` and edited only through `orchestrator.create / set_records / set_senders / set_daily_volume / map_external / set_cadence_experiment` | **No** |
| `CampaignMaterial` | `campaigns.material()` — every launch-sensitive fact assembled in one readable place, digested by `campaigns.fingerprint()` | **No** |
| `ProviderBinding` | fields on that same row: `heyreach_campaign_id`, `bison_campaign_id`, `heyreach_list_id`, `org_unit`, `workspace`, `provider_delays`, `provider_status_expected` — all already inside `material()` | **No** |
| `ProviderSnapshot` | `configdiff.provider_heyreach()` / `configdiff.provider_bison()`, read-only routes only | **No** |
| `ProviderDiff` | `configdiff.diff()` over the union of both sides, returned as a sealed, campaign-bound, single-use `configdiff.Readback` | **No** |
| `ActivationAuthorization` | `executionguard.Authorization` (typed, single-use, 60s TTL) plus the durable `actionledger.reserve()` row behind it | **No** |

A campaign-level activation token is not just redundant, it is **wrong grain**.
`executionguard.revalidate()` exists because a reply can land between the last
gate and the transport; a token minted once for a whole campaign would re-open
exactly that window for every contact after the first.

### The one genuinely new field

`campaign["readback"]` — the audit record of one execution of the diff:

```
{"channel": "linkedin", "provider_campaign_id": "…", "verdict": "PASS",
 "failures": [], "verified_at": "…", "by": "…", "fingerprint": "…"}
```

It earns its place because **READBACK_VERIFIED has no durable representation at
all today**. `configdiff.Readback` lives in RAM, is single-use, and expires in
fifteen minutes. A human is shown a verdict that leaves no trace, and
`RELEASE-CANDIDATE.md` cannot cite one. This is the same relationship
`actionledger` has to `authorize()`: the computation stays the authority, the
row is the evidence it ran.

It must be **inert**. `executionguard` keeps requiring a live sealed `Readback`
and must never read this field, or the fifteen-minute TTL becomes decorative.
Storing the `fingerprint` alongside makes a stale row self-identifying.

---

## 2. The factory's decisions, and who already owns each

The factory is a **function over canonical state**, not a service object. It
chooses nothing itself; it sequences modules that each own one decision.

| Decision | Owner today | Note |
|---|---|---|
| **Channel** | `channels.py` (two independent verdicts + a mode), narrowed per step by `eligibility.decide()` | "Sendable" is never one boolean |
| **Campaign grouping** | `campaignseg.py` merge ladder; the account is the unit per `ACCOUNT-OUTREACH.md`, via `account.py` / `accountpolicy.py` | Every company records which rung it stopped on |
| **Sender** | `assignment.py` (which *human* owns the prospect, stable across inbox changes) → `senders.assign()` (which account, within channel) → `senderidentity.accounts_for()` + `senderinventory` health, **re-checked inside `executionguard` gate 5** | `senders.py` alone is unstable when the account list changes; `assignment.py` is the fix |
| **Leads** | `icp` verdict (company first) → `routing.py` (who, and how many are worth paying for) → `verification` → `eligibility.decide()` → `campaign["record_ids"]` | No paid person-level call before an explicit ICP verdict |
| **Cadence** | `cadence.STEPS` / `cadence.steps_for(campaign)` / `cadencegraph.py` for branching; `cadencearms` when an experiment is set | Campaign-owned sequence changes the fingerprint transitively, via the expanded timeline |
| **Copy** | `generate.py` + `llm.py` → `variants.py` (five per step) → `lint.py` → `claims.py` → `approve.approve_step()` | The approval is bound to `approval.fingerprint(step)` over channel+subject+body+note |
| **Delays** | Two different quantities, deliberately: the cadence day (`cadence.STEPS`) is a position in a schedule; `campaign["provider_delays"]` is the provider node delay and is **declared, never derived** | `approved_heyreach` refuses a campaign that declares none |
| **Limits** | `campaign["daily_volume"]` → `pilotcaps.effective()` ceiling (which nothing can raise) → `senders.capacity()` → `fatigue.check()` per person and per company | The ledger, not a caller's plan dict, is what the cap counts |
| **Schedule** | `geo.send_window()` + `schedule.py` over `config["scheduling"]["windows"]` | **Carried to no provider and in no fingerprint — see §3 and §4** |
| **Provider** | Implied by channel: `linkedin → heyreach`, `email → bison`. The binding is the campaign row; the write door is `providerwrites.OPERATIONS` | There is no provider-selection decision to make, so no field for one |

### Where each gate sits

Staging and sending are different flows and only one of them can reach a person.

```
PLAN          campaignseg → routing → icp → verification → channels
                │
                ├─ tenancy .......... clients/workspaces scope every read
                ├─ suppression ...... eligibility.decide (SUPPRESSION_REASONS)
                ├─ DNC .............. agencydnc, via eligibility
                ├─ reply stop ....... eligibility BLOCKED_REPLIED / cadencereplies
                ├─ collision ........ collision.check_* against the CLIENT's estate
                ├─ fatigue .......... fatigue.check, person and company
                ├─ claims / lint .... claims.check + lint.check_step, per draft
                └─ budget ........... enrich.spend() waterfall ledger

APPROVE       campaigns.validate() → orchestrator.request_approval → decide
                └─ approval ......... campaign["approval"].fingerprint ==
                                      campaigns.fingerprint(material())

STAGE         providerwrites.perform(op, …)      NON-prospect-facing ops only
                └─ killswitch ....... killswitch.require, inside the write door
                   (create_list / create_campaign / set_sequence / assign_sender
                    / set_limits are all `prospect_facing=False`, which is what
                    lets configuration be built and proven with nobody at risk)
              _ensure_leads calls bison.create_lead / bison.attach_leads
              DIRECTLY, bypassing providerwrites.perform. Three checks close
              the gap: the collision check (collision.check_account +
              collision.account_policy) refuses leads whose account the
              client's estate says STOP or HOLD before any lead is created;
              the workspace killswitch (sending.live) is consulted before any
              lead is created; and the campaign's provider status is re-read
              immediately before attach_leads.

VERIFY        configdiff.compare_heyreach / compare_bison  → sealed Readback
                └─ provider readback  built from canonical state ONLY

ACT           executionguard.authorize(readback=…) → Authorization
              1 tenancy → 2 approval → 2b campaign_approval → 3 readback
              → 4 JIT (eligibility, suppression, lint, claims, fatigue,
                       collision RE-READ) → 5 cap + sender health
              → 5b stoppability → 6 ledger reservation → 7 killswitch
                └─ then executionguard.revalidate() against DISK
                └─ then providerwrites.perform(), the single sealed door
```

Two properties of that shape matter more than the list:

- **Nothing in STAGE can reach a prospect.** Every staging operation that
  goes through `providerwrites.perform` is declared `prospect_facing=False`
  in `providerwrites.OPERATIONS`. The factory therefore builds and proves a
  configuration with zero exposure. `_ensure_leads` does NOT go through
  `providerwrites.perform` - it calls `bison.create_lead` and
  `bison.attach_leads` directly - but three checks close the gap: the
  collision check refuses leads whose account the client's estate says STOP
  or HOLD (using `collision.check_account` + `collision.account_policy`, the
  same gates `executionguard` runs at send time); the workspace killswitch is
  consulted before any lead is created; and the campaign's provider status is
  re-read immediately before attach. The operations that need a full
  `Authorization` through `executionguard.authorize()` are `add_lead` and
  `activate` when they go through the write door; the factory's own lead
  path is gated by the collision check, the workspace killswitch and the
  provider status check instead.

  **WHY NOT A FULL AUTHORIZATION FOR STAGING.** `Authorization` is per-action
  with a 60-second TTL and a ledger reservation. Staging twenty leads is not
  twenty actions - it is one batch operation. A token minted for the batch
  re-opens the window `revalidate()` exists to close: the gap between the
  last gate and the transport, in which a reply can land and change the
  person. The collision check at staging time is the right scope: it answers
  "is this person already being emailed by the client" using the same verdict
  the send gate will re-check, without reserving ledger capacity or minting a
  token whose TTL outlives the batch.
- **The gates are not a convention.** They are the only way to obtain the thing
  the write layer requires. That is why the factory has no "call the guards"
  step: it cannot skip one.

---

## 3. Fingerprint coverage audit — `campaigns.material()` as it stands

Measured, not read off the source: each row below was verified by mutating the
field and comparing `campaigns.fingerprint()` before and after.

| Prospect-facing dimension | In `material()`? | How |
|---|---|---|
| Provider (which vendor) | **Yes**, implicitly | `bison_campaign_id` / `heyreach_campaign_id` presence names the provider; there is no separate choice to cover |
| Tenant / workspace | **Yes** | `workspace` (EmailBison estate), `org_unit` (HeyReach), `client` |
| Canonical leads | **Yes** | `record_ids` → per-record `contacts` (key, email, linkedin, sendable, persona, angle) |
| Sender(s) | **Yes** | `senders.email` / `senders.linkedin`, **including each account's `daily_limit`** |
| Channel | **Yes**, per step | `_step_material.channel`, and `approval.fingerprint` hashes the channel too |
| Sequence graph | **Yes**, transitively | steps come from `cadence.build(…, campaign=campaign)`, so a campaign-owned `cadence_steps` or a `cadence_experiment` arm moves the digest by changing the expanded timeline |
| Step types | **Yes** | each step contributes `step`, `channel`, `day` |
| Copy (body) | **Yes** | `approval.fingerprint(step)` over channel+subject+body+note |
| Connection note | **Yes** | same digest — `note` is one of its four fields |
| Subject | **Yes** | same digest |
| Delays — cadence | **Yes** | `day` per step |
| Delays — provider node | **Yes** | `provider_delays` |
| Limits — campaign volume | **Yes** | `daily_volume` |
| Expected provider status | **Yes** | `provider_status_expected` |
| Provider list binding | **Yes** | `heyreach_list_id` |
| Campaign cadence version | **Yes** | `cadence_version` |
| Client sending config | **Partly** | `sending_config()` covers `cadence`, `sender`, `tone`, `booking_link`, `linkedin_note_mode`, `verification` — and nothing else |
| **Schedule (send window, sending days, timezone)** | **NO** | `config["scheduling"]["windows"]` drives `geo.send_window()` and is not in `sending_config()`. The hour a prospect is written at is outside the approval entirely |
| **Client-level volume ceilings** | **NO** | `pilotcaps.configured()` reads `config["campaign"]["daily_volume"]`, `config["pilot"]`, `config["fatigue"]` — none of the three is in `sending_config()` |
| **Company/person fatigue limits** | **NO** | `config["fatigue"]`, as above — how often one company may hear from us can change after approval with no trace |
| **Campaign name** | **NO** | and `campaign_name` is REQUIRED by *both* provider diffs, so renaming after approval leaves the approval current and makes the read-back fail |
| Lanes / personas / geos | No | selection metadata; once `record_ids` is fixed these change nothing that is sent. Correctly out |
| Freeze / pause / status / launch | No | deliberately — `campaigns.freeze` documents why: a stop must not force re-approval |

**The finding is the schedule.** It is a field a human weighs, it is
prospect-facing in the most literal sense, it is absent from the fingerprint,
and (see §4) it is absent from the provider diff as well — so it is the one
dimension of this system with no approval and no verification at either end.

---

## 4. What the diff actually catches, and what it cannot

Proven executably in `tests/test_no_activation_without_an_exact_match.py`,
against the real `compare_heyreach` / `compare_bison` with a faked provider
payload. Each mutation asserts the exact set of failing fields, so no test can
pass because an earlier check happened to fire.

### Caught — LinkedIn (HeyReach)

`sender_ids` · extra sender · `lead_set` (who) · `lead_count` (how many) ·
`note` (one word, one capital, truncation, empty) · `delays` · `actions`
(an extra sequence node, while still provably LinkedIn-only) · `org_unit`
(tenant) · `list_id` · `campaign_id` · `status` (already activated) ·
`campaign_name` · `linkedin_only` · `bison_handoff`

### Caught — Email (EmailBison)

`sender_ids` · `lead_count` · `subjects` · `bodies` · `delays` ·
extra sequence step · `max_emails_per_day` · `max_new_leads_per_day` ·
`workspace` (tenant) · `status`

### NOT caught — lead with these first

| # | Mutation | Why it is invisible | Severity |
|---|---|---|---|
| 1 | An email campaign where **nobody approved any copy** | `approved_bison` runs `leads.add(address)` *before* it filters on approval, so every emailable contact is in the APPROVED lead set regardless. With no approved step the approved copy is empty, and a provider campaign holding those leads with no active sequence step **matches exactly and diffs PASS**. `approved_heyreach` refuses this by name; the email side has no equivalent | **Critical** — PASS in the wrong direction, and it is the exact defect `configdiff` was written to prevent |
| 2 | **Which person** is in an email campaign | `lead_set` is in `REQUIRED_HEYREACH` and **not** in `REQUIRED_BISON`. Swap one address for another and the report says `lead_set: mismatch` while the verdict never mentions it, because `lead_count` still agrees. This is the same correction the module already made once, on the other channel | **Critical** — the wrong person, silently |
| 3 | Anything on email, effectively | `approved_bison` names steps `day1…`; `provider_bison` names them `step1…`; `actions` is required. They can never be equal, so **`compare_bison` can never return PASS**. It fails closed, but the email half of this gate has never been exercised against a match and it masks every other email verdict | **High** — availability, and it hides #1 and #2 in practice |
| 4 | EmailBison **per-domain send cap** | `provider_bison` reads `daily_max_sends_per_receiving_domain` and files it as `_per_domain_cap`; `diff` skips every `_`-prefixed key. Fetched, carried, printed, scored by nothing — and the approved side has no opinion about it | **High** — decides how many people at one company hear from us in a day |
| 5 | HeyReach **per-campaign daily limit** | No read route exposes it; `provider_heyreach` returns `UNVERIFIABLE` and `REQUIRED_HEYREACH` omits it. Already documented in the module. The approved side *does* state one, from `daily_volume.linkedin` | **Medium** — structural, needs a vendor route |
| 6 | The **sending schedule** on either provider | No `schedule` / `sending_window` / `timezone` field on either side of either diff, and none in `material()` either. Both vendors carry a campaign sending window in their UI | **High** — no approval and no verification, at either end |
| 7 | `provider_status_expected` is **one scalar for two providers** | HeyReach spells it `PAUSED`, EmailBison `paused`. A dual-channel campaign cannot carry a value that satisfies both diffs | **Medium** — shape bug |
| 8 | `campaign["name"]` changed after approval | Outside `material()`, required by both diffs. The two halves of the gate then disagree about whether anything changed | **Low** — fails closed, but confusingly |

Findings 1–6 are executable in the test module as `expectedFailure`; 7 and 8
are demonstrable today and assert as passing tests.

---

## 5. The lifecycle, mapped onto fields that exist

| State | The field that proves it | Durable? |
|---|---|---|
| **PLANNED** | `campaign["status"]` ∈ `draft / preparing / ready_for_review`; `record_ids`, `senders`, `daily_volume` set through `orchestrator` | Yes — `work/campaigns.jsonl` |
| **APPROVED** | `status == approved` **and** `approval == {action: approve, by, at, fingerprint}` **and** `campaigns.approval_is_current()` re-derives the same digest | Yes |
| **PROVIDER_STAGED** | — nothing. `heyreach_campaign_id` / `bison_campaign_id` / `heyreach_list_id` prove a *binding was named*, not that leads and a sequence were written. Today they are set by hand via `orchestrator.map_external` because no create/set-sequence route is in `providerwrites.SUPPORTED` | **NO** |
| **READBACK_VERIFIED** | `configdiff.Readback` — sealed, campaign-bound, single-use, 15-minute TTL, **in memory only**. Nothing writes the verdict anywhere | **NO** — this is what §1's one new field is for |
| **ACTIVATION_AUTHORIZED** | Per *action*: `executionguard.Authorization` (60s TTL) backed by a durable `actionledger` reservation row carrying `campaign_id`, `sender_id`, `operation`, `fingerprint`, `cap_per_day`. Per *campaign*: nothing, and correctly so | Per action: yes. Per campaign: **NO**, by design |
| **LIVE** | `status == running`, `launch == {state: launched, at}`, `started_at` | Yes — but it is a **local claim**. Nothing sets it from provider truth, and `providerwrites.SUPPORTED == ()` means no activation has ever occurred |
| **OBSERVING** | `events` on the record + `touch.CONFIRMING_EVENTS` + `actionledger.settle()`. `push.mark_pushed` is the only writer and `push.run(live=True)` raises | **Partly** — being closed by `src/leadobserve.py`, which reads provider truth per lead and appends only on a real transition |
| **HOLD** | `campaign["freeze"]` (deliberately not a status, so unfreezing restores position without re-approval) **and** `status == paused` / `campaign["pause"]` **and** `killswitch` layers **and** `accountpolicy` account pause | Yes — four representations, each documented, each a different question |
| **STOP** | `killswitch.require()` refuses to **start**. There is no campaign-level stop: `heyreach.pause` and `bison.pause` are both unsupported, which is why `executionguard`'s stoppability gate caps an unstoppable channel at one contact | **NO** — STOP is refusal-to-start only, and the cap is the honest consequence |
| **RECONCILE** | `actionledger` `UNRESOLVED` rows (`unsettled()`, `is_unreservable()`) plus `providerwrites.UNKNOWN` / `DRIFTED` | Per action: yes. Per campaign: **NO** |

Five transitions with no durable representation: **PROVIDER_STAGED**,
**READBACK_VERIFIED**, campaign-level **ACTIVATION_AUTHORIZED** (intentional),
provider-observed **LIVE**, campaign-level **RECONCILE**.

---

## 6. Smallest next implementation step

Two lines of `src/configdiff.py`, in this order, because one is a safety bug and
the others are availability bugs:

1. **Move `leads.add(address)` inside the approval filter in
   `approved_bison`**, and refuse when the approved lead set is empty, the way
   `approved_heyreach` already does. Closes finding #1. A campaign nobody
   approved copy for stops certifying as "the provider holds what was
   approved".
2. **Add `"lead_set"` to `REQUIRED_BISON`.** Closes finding #2. Both sides
   already compute it; only the required tuple is missing the field.

Both are covered: `tests/test_no_activation_without_an_exact_match.py` carries
`test_an_email_campaign_with_no_approved_copy_should_not_pass` and
`test_who_is_in_an_email_campaign_should_block` as `expectedFailure`, so the
fix turns them green and an unexpected success fails the suite if anybody
reverts it.

Then, in descending value and each independently shippable:

3. Reconcile the `actions` naming so `compare_bison` can reach PASS (#3), and
   re-run this module — every email assertion tightens by one field.
4. Lift `_per_domain_cap` into the diffed, approved surface (#4) and add the
   matching field to `campaigns.material()`.
5. Put the schedule on both sides: `config["scheduling"]["windows"]` into
   `campaigns.sending_config()`, and the provider's campaign schedule into
   `approved_*` / `provider_*` (#6).
6. Make `provider_status_expected` per-channel (#7), and add `name` to
   `material()` (#8).
7. Only then the durable `campaign["readback"]` row from §1 — an audit record
   is worth writing once the thing it records is trustworthy.

Nothing above touches `SUPPORTED`. Activation stays BLOCKING by construction,
and a pause route that has never once succeeded stays unsupported, per
`LIVE-READINESS.md`.
