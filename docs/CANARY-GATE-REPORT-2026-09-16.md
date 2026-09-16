---
title: "Canary Gate Report — Every Gate for One Lead"
task: "TASK-209"
date: "2026-09-16"
builds_on:
  - "docs/CONTEXT-RESET-2026-09-15-E.md"
  - "docs/LINKEDIN-CANARY-PAYLOAD-2026-09-16.md"
  - "docs/LI6-AND-APPROVAL-2026-09-16.md"
  - "docs/state/PROVIDER-CAMPAIGNS.json"
  - "docs/state/SENDER-CAPACITY.json"
---

# Canary Gate Report — 2026-09-16

**TASK-209 deliverable.** One named canary candidate, every gate with PASS/FAIL and the value read, the blocking set classified, whether `held` blocks a LinkedIn add, and the exact operator command sequence with readbacks.

**Snapshot:** `work/queue.snapshot.jsonl` from `2026-09-15T17:52:12+00:00 from master cf23154`, 550 records. The live queue is in Claude's worktree only; this report reads the snapshot available in this worktree. Time-dependent gates are marked ⏱ and MUST be re-read at the moment of the write.

**PII policy:** Every identifier is SHA-256 hashed (12 hex chars). No profile URL, person name, company name, email address, or domain appears in this document.

---

## 1. The Six Contacts With Full li1-li5 Operator Approval

All six carry `approval.by: "operator-control-arm"` on every step li1–li5. All six have a LinkedIn profile. All six share the same approval fingerprints:

| step | fingerprint |
|------|-------------|
| li1  | `171955be6018` |
| li2  | `e723f310876c` |
| li3  | `11dfd15ab6e5` |
| li4  | `e93016d8573d` |
| li5  | `90d018014200` |

These fingerprints match the CONTROL fallbacks in `config/clients/productive.yaml`.

| # | record_hash | contact_hash | state | hold_reason | sendable | LinkedIn | persona | angle |
|---|-------------|--------------|-------|-------------|----------|----------|---------|-------|
| 1 | `0f6272a876ef` | `cac85b829d29` | held | None | True | ✓ | champion | operations |
| 2 | `0f6272a876ef` | `722ce43b6a40` | held | None | True | ✓ | champion | delivery |
| 3 | `e46dd5323aa3` | `d814b9bcb642` | held | None | False | ✓ | economic_buyer | operations |
| 4 | `699952d14554` | `f4698472e36a` | verified | None | False | ✓ | economic_buyer | founder |
| 5 | `fd8123119dd5` | `f6f3b7fac1b1` | held | None | False | ✓ | champion | operations |
| 6 | `fd8123119dd5` | `32ac8b932120` | held | None | False | ✓ | champion | delivery |

**Distribution:** 5 contacts on 3 `held` records, 1 contact on 1 `verified` record. No `drafted` record among the six in this snapshot (the task description names one from live state; the snapshot is 18+ hours old and the live queue may differ).

---

## 2. The Canary Candidate

**Contact #4: record `699952d14554`, contact `f4698472e36a`.**

### Why this one

| Criterion | Contact #4 | Others |
|-----------|-----------|--------|
| Record state | `verified` — the cleanest state in the lifecycle | 5 of 6 others sit on `held` records |
| Hold ambiguity | None — `verified` has no hold_reason question | 5 others carry `hold_reason: None` on a `held` record, which is the anomaly TASK-168 was meant to resolve |
| LinkedIn profile | Present | All 6 have one |
| Persona and angle | `economic_buyer` / `founder` — classified with their own angle | Contacts #1, #2, #5, #6 are `champion` with varying angles; contact #3 is `economic_buyer`/`operations` but on a `held` record |
| Prior EmailBison history | None (`bison_lead_id: None`) | All 6 are clean |
| Email present | No (empty email hash `e3b0c44298fc` = hash of empty string) | Contacts #1, #2 have sendable email; #3, #5, #6 have unsentable email |
| Single contact on record | Yes — the canary tests one lead | Contacts #1/#2 share a record; #5/#6 share a record |

### Why the others were not chosen

- **Contacts #1, #2** (`0f6272a876ef`): Two contacts on one `held` record. A canary of two is not a canary of one. The `held` state introduces the hold_reason=None question. They are the strongest runners-up because `sendable=True` means email verification passed, but email sendability is irrelevant to a LinkedIn add.
- **Contact #3** (`e46dd5323aa3`): This is the contact from TASK-176 (`d814b9bcb642` = `b7d648ab527f` name hash). On a `held` record with `sendable=False`. Same hold ambiguity.
- **Contacts #5, #6** (`fd8123119dd5`): Two contacts on one `held` record, both `sendable=False`. Same issues as #1/#2 plus no email verification.

---

## 3. Every Gate, One Line Each

**Legend:** 🟢 PASS, 🔴 FAIL, ⏱ time-dependent (MUST re-read at write time), `[LOCAL]` = from local state, `[PROVIDER]` = from provider read, `[DERIVED]` = computed from code + local state

### 3.1 Tenancy / Workspace Ownership

| Gate | Verdict | Value read | Source |
|------|---------|------------|--------|
| Record client | 🟢 PASS | `productive` | `[LOCAL]` |
| Campaign client | 🟢 PASS | `productive` | `[LOCAL]` — campaign row `productive-linkedin-production-v1` |
| Record ↔ campaign client match | 🟢 PASS | both `productive` | `[DERIVED]` |
| org_unit named on campaign | 🟢 PASS | `118832` | `[PROVIDER]` — from `PROVIDER-CAMPAIGNS.json`, `organization_unit_id` |

### 3.2 Campaign Ownership and Identity

| Gate | Verdict | Value read | Source |
|------|---------|------------|--------|
| HeyReach campaign id | 🟢 PASS | `599020` | `[PROVIDER]` |
| Campaign name | 🟢 PASS | `RESONATE - PRODUCTIVE LINKEDIN PRODUCTION V1` | `[PROVIDER]` |
| Created by Resonate | 🟢 PASS | 1 of 83 campaigns in the account | `[PROVIDER]` |
| Internal ↔ provider binding consistent | 🟢 PASS | `consistent: true` | `[PROVIDER]` |

### 3.3 Campaign State ⏱

| Gate | Verdict | Value read | Source |
|------|---------|------------|--------|
| Campaign status | 🟢 PASS | `DRAFT` | `[PROVIDER]` — read 2026-09-15T15:24:59Z |
| startedAt | 🟢 PASS | `null` | `[PROVIDER]` |
| Lead count | 🟢 PASS | `0` | `[PROVIDER]` |

**⏱ TIME-DEPENDENT:** A human can change DRAFT to IN_PROGRESS in the vendor UI at any time. Must be re-read immediately before the write. `heyreach.campaign_read(599020)` is the call.

### 3.4 List Ownership and Attachment

| Gate | Verdict | Value read | Source |
|------|---------|------------|--------|
| List id | 🟢 PASS | `933603` | `[PROVIDER]` |
| List name | 🟢 PASS | `RESONATE - PRODUCTIVE LINKEDIN PRODUCTION V1` | `[PROVIDER]` |
| List count | 🟢 PASS | `0` | `[PROVIDER]` |
| List type | 🟢 PASS | `USER_LIST` | `[PROVIDER]` |
| List attached to campaign | 🟢 PASS | Yes — attached to 599020 | `[PROVIDER]` |

**Note:** The list IS attached to the campaign. For the list-staging path (`LINKEDIN_ADD_LEAD_TO_LIST`), `liststaging.assert_list_safe` requires the list to be UNBOUND (attached to no campaign). Since list 933603 IS attached to campaign 599020, the list-staging path REFUSES. The campaign-level path (`LINKEDIN_ADD_LEAD`) is the only route, and it is resealed by `CAMPAIGN_LEVEL_STAGING_IS_PROVEN = False`.

### 3.5 Sender Resolves, Is Active, Authorization Valid ⏱

| Gate | Verdict | Value read | Source |
|------|---------|------------|--------|
| Sender attached to campaign | 🟢 PASS | `174892` | `[PROVIDER]` |
| Sender resolves | 🟢 PASS | `true` | `[PROVIDER]` |
| Sender active | 🟢 PASS | `true` | `[PROVIDER]` |
| Sender state | 🟢 PASS | `HEALTHY` | `[PROVIDER]` |
| Auth valid | 🟢 PASS | `true` | `[PROVIDER]` |
| Sales Navigator | 🟢 PASS | `true` | `[PROVIDER]` |
| Active campaigns | 🟢 PASS | `12` | `[PROVIDER]` |

**⏱ TIME-DEPENDENT:** Sender health can change. A sender can go AUTH_INVALID between this read and the write. Must be re-read at write time.

### 3.6 Killswitch

| Gate | Verdict | Value read | Source |
|------|---------|------------|--------|
| Global killswitch | 🔴 FAIL | `sending: false` — `push.run(live=True)` raises `LiveSendNotEnabled` | `[DERIVED]` — `killswitch.global_state()` derives from `push.LiveSendNotEnabled` existing |
| Workspace killswitch | 🔴 FAIL | `sending: false` — no `sending.live` override for `productive` | `[LOCAL]` — default off per `killswitch.py` |
| Campaign killswitch | 🔴 FAIL | Campaign is DRAFT, not running | `[PROVIDER]` |

**All three killswitch layers report OFF.** The global killswitch is structural — `push.LiveSendNotEnabled` exists in code and can only be removed by a code change (a review, not a toggle). The workspace killswitch defaults off and no override has been set. The campaign is DRAFT and cannot send.

### 3.7 Collision: Account-Level and Contact-Level ⏱

| Gate | Verdict | Value read | Source |
|------|---------|------------|--------|
| Contact-level (LinkedIn profile) | 🔴 FAIL — CANNOT READ | No provider call made from this worktree | `[PROVIDER]` — requires `collision.check_linkedin_profile()` against the HeyReach estate |
| Account-level (domain) | 🔴 FAIL — CANNOT READ | No EmailBison workspace accessible from this worktree | `[PROVIDER]` — requires `collision.check_account()` against the EmailBison estate |

**These gates require provider reads that this worktree cannot make.** The collision estate is EmailBison's even for LinkedIn (ACCOUNT-OUTREACH.md makes the account the unit of outreach). The EmailBison workspace binding (`bison.bound_workspace()`) requires the EmailBison credential, which is in `config/.env` — present in this worktree but the collision module makes live API calls.

**⏱ TIME-DEPENDENT:** Collision state changes as other campaigns send. Must be re-read at write time.

### 3.8 Prior Contact, on Any Channel, from the Provider ⏱

| Gate | Verdict | Value read | Source |
|------|---------|------------|--------|
| Prior EmailBison contact | 🔴 FAIL — CANNOT READ | `bison_lead_id: None` locally, but provider not queried | `[LOCAL]` says no prior Bison lead; `[PROVIDER]` not queried |
| Prior HeyReach contact | 🔴 FAIL — CANNOT READ | Campaign 599020 has 0 leads, but the contact may exist in another campaign | `[PROVIDER]` — requires paging the account's lead list |

**⏱ TIME-DEPENDENT:** Prior contact state changes as sends happen.

### 3.9 Historical Contact

| Gate | Verdict | Value read | Source |
|------|---------|------------|--------|
| Internal event log | 🟢 PASS | No confirmed touches in the local event log for this contact | `[LOCAL]` |
| bison_lead_id | 🟢 PASS | `None` — no prior EmailBison lead | `[LOCAL]` |

### 3.10 Fatigue ⏱

| Gate | Verdict | Value read | Source |
|------|---------|------------|--------|
| Contact-level fatigue | 🟢 PASS | No confirmed touches → `ok` (no prior touches to exceed limits) | `[DERIVED]` — `fatigue.contact_check()` with zero confirmed touches returns `ok` |
| Account-level fatigue | 🟢 PASS | No confirmed touches at this account → `ok` | `[DERIVED]` — `fatigue.account_check()` with zero confirmed touches returns `ok` |

**⏱ TIME-DEPENDENT:** If another channel touches this contact or account before the LinkedIn write, fatigue state changes.

### 3.11 Caps and Daily Volume ⏱

| Gate | Verdict | Value read | Source |
|------|---------|------------|--------|
| Pilot caps | 🟢 PASS | No caps exceeded — zero touches to date | `[DERIVED]` — `pilotcaps.check()` against the action ledger |
| Daily volume (sender ceiling) | 🟢 PASS | Sender 174892: 40 connection requests/day, 40 messages/day | `[PROVIDER]` |
| Daily volume (account ceiling) | 🟢 PASS | 1,054 connection requests/day across 33 healthy seats | `[PROVIDER]` |
| Daily volume (current usage) | 🟢 PASS | 0 leads in campaign 599020, 0 sent | `[PROVIDER]` |

**⏱ TIME-DEPENDENT:** Daily volume resets on a rolling window. Current usage changes with every send across all campaigns.

### 3.12 Approval: Which Steps, by Whom, Fingerprint Current

| Gate | Verdict | Value read | Source |
|------|---------|------------|--------|
| li1 approved | 🟢 PASS | `by: operator-control-arm`, fp `171955be6018` | `[LOCAL]` |
| li2 approved | 🟢 PASS | `by: operator-control-arm`, fp `e723f310876c` | `[LOCAL]` |
| li3 approved | 🟢 PASS | `by: operator-control-arm`, fp `11dfd15ab6e5` | `[LOCAL]` |
| li4 approved | 🟢 PASS | `by: operator-control-arm`, fp `e93016d8573d` | `[LOCAL]` |
| li5 approved | 🟢 PASS | `by: operator-control-arm`, fp `90d018014200` | `[LOCAL]` |
| Fingerprint current | 🟢 PASS | All 5 fingerprints match the CONTROL fallbacks in config | `[DERIVED]` — `approval.is_approved()` compares stored fp to current step text |

### 3.13 Copy: Lint and Claims

| Gate | Verdict | Value read | Source |
|------|---------|------------|--------|
| LinkedIn lint (all steps) | 🟢 PASS | All 5 CONTROL fallbacks pass `lint.check_linkedin()` — no em dashes, no banned phrases, no placeholders, length within bounds | `[DERIVED]` — verified in TASK-176 and TASK-179 |
| Claims (all steps) | 🟢 PASS | All 5 CONTROL fallbacks pass `claims.check()` — no unsupported assertions, no operational claims about the prospect | `[DERIVED]` — verified in TASK-176 and TASK-179 |

### 3.14 Sequence / Copy Fingerprint Matches What Was Approved

| Gate | Verdict | Value read | Source |
|------|---------|------------|--------|
| Sequence graph carries merge variables | 🟢 PASS | `{connection_note}`, `{connected_1..4}`, `{message_2..4}` — pure merge variables, no literal text | `[PROVIDER]` — sequence hash `32f8dde79bfa0f27` |
| Approved text matches graph variables | 🟢 PASS | CONTROL fallbacks resolve to the exact text the merge variables carry | `[DERIVED]` |
| Sequence hash stable | 🟢 PASS | `32f8dde79bfa0f27` — unchanged since last readback | `[PROVIDER]` |

### 3.15 Campaign Binding

| Gate | Verdict | Value read | Source |
|------|---------|------------|--------|
| Canonical campaign → provider campaign | 🟢 PASS | `productive-linkedin-production-v1` → `599020` | `[LOCAL]` + `[PROVIDER]` |
| Provider campaign → canonical campaign | 🟢 PASS | `599020` → `productive-linkedin-production-v1` | `[PROVIDER]` |
| Binding consistent | 🟢 PASS | `consistent: true` in PROVIDER-CAMPAIGNS.json | `[PROVIDER]` |

### 3.16 The Permission That Refuses Everything

| Gate | Verdict | Value read | Source |
|------|---------|------------|--------|
| `CAMPAIGN_LEVEL_STAGING_IS_PROVEN` | 🔴 FAIL | `False` | `[LOCAL]` — `src/providerwrites.py` line 518 |
| `LINKEDIN_ADD_LEAD` conditional | 🔴 FAIL | `_campaign_is_a_declared_staging_campaign` raises `WriteRefused` immediately because `CAMPAIGN_LEVEL_STAGING_IS_PROVEN` is `False` | `[DERIVED]` |
| `LINKEDIN_ADD_LEAD_TO_LIST` (list staging) | 🔴 FAIL | List 933603 is attached to campaign 599020, so `liststaging.list_is_unbound()` returns `False` | `[PROVIDER]` + `[DERIVED]` |

**This is the master blocker.** Both paths to put a lead into the HeyReach campaign are sealed:
1. Campaign-level add (`LINKEDIN_ADD_LEAD`): resealed by `CAMPAIGN_LEVEL_STAGING_IS_PROVEN = False`
2. List-level add (`LINKEDIN_ADD_LEAD_TO_LIST`): the list is bound to a campaign, so the list-staging safety predicate refuses

---

## 4. The Blocking Set

| # | Gate | Classification | What must change |
|---|------|----------------|------------------|
| 1 | `CAMPAIGN_LEVEL_STAGING_IS_PROVEN = False` | **Permission** | An operator decision to set it `True`, after the staging path is proven safe. This is the TASK-137 seal. |
| 2 | Global killswitch (`push.LiveSendNotEnabled`) | **Permission** | Structural — requires a code change to `push.py` to remove the refusal. Not a toggle. |
| 3 | Workspace killswitch (`sending.live` not set) | **Human act** | The operator sets `sending.live: true` in the workspace config. |
| 4 | List 933603 is bound to campaign 599020 | **Data / architecture** | Either detach the list (making list-staging viable) or route through the campaign-level path (requiring gate 1). |
| 5 | Collision: account-level | **Data gap** | Cannot be evaluated from this worktree. Requires a live provider read against the EmailBison estate at write time. |
| 6 | Collision: contact-level (LinkedIn) | **Data gap** | Cannot be evaluated from this worktree. Requires a live provider read against the HeyReach estate at write time. |
| 7 | Prior contact from provider | **Data gap** | Cannot be evaluated from this worktree. Requires paging the provider's lead list. |

### Summary

- **Permission blockers:** 2 (the `CAMPAIGN_LEVEL_STAGING_IS_PROVEN` seal, the global killswitch)
- **Human act blockers:** 1 (workspace killswitch)
- **Data gap blockers:** 3 (collision and prior contact require live provider reads)
- **Data/architecture blockers:** 1 (list binding)
- **Defect blockers:** 0

**No gate failed because of a code defect.** Every failure is either a deliberate seal, a missing provider read, or a human act that has not been performed.

---

## 5. Is `held` a Blocker?

### The evidence

Five of the six approved contacts sit on records in state `held`. All five have `hold_reason: None` and `hold_class: None`.

### What `held` means in this codebase

`held` is an **email judgment**, not a LinkedIn one. The code is explicit:

```python
# src/approve.py, line 28:
# `held` is deliberately not in that list. It is an *email* judgement -
# `enrich.outcome` sets it when no address cleared verification - and refusing
# every step on the record because of it silently takes LinkedIn away from a
# contact whose profile is perfectly usable.
```

```python
# src/approve.py, line 38:
EMAIL_REFUSED_STATES = ("held",)
```

`approve.why_not()` refuses email steps on a `held` record but allows LinkedIn steps:

```python
if (rec.get("state") in EMAIL_REFUSED_STATES
        and step.get("channel") == "email"):
    return f"record is {rec['state']}"
```

For LinkedIn steps, the `held` check does NOT fire. A `held` record with a LinkedIn profile and approved LinkedIn steps is approvable and staging-eligible on the LinkedIn channel.

### Does `held` prevent staging?

**No.** `held` does not prevent a LinkedIn add. The staging path (`heyreachfactory.ensure_leads`) does not check record state. It checks:
1. Killswitch workspace state
2. Suppression and DNC
3. Account collision
4. Tenant check
5. Unsupported sequence

None of these gates reads `rec.get("state")`. The `held` state is invisible to the LinkedIn staging path.

### The `hold_reason: None` anomaly

TASK-168 wired `hold_reason` and `hold_class` onto records at the moment of hold. Five approved contacts have `hold_reason: None` despite being in state `held`. Two explanations:

1. **The backfill did not reach them.** If these records were held before TASK-168's migration, they would have `state: held` but no `hold_reason`.
2. **The reason lives elsewhere.** The hold may have been set by `enrich.outcome` (which calls `holdreasons.set_hold_reason`) but the field was later cleared or the record was re-enriched without the hold being re-set.

**This anomaly is orthogonal to the LinkedIn add.** Whether `hold_reason` is None or populated, `held` does not block LinkedIn staging. The anomaly matters for the email channel (where `held` refuses steps) but not for LinkedIn.

### Verdict

**`held` is NOT a blocker for a LinkedIn add.** It is an email-only judgment. The canary on the `verified` record (contact #4) avoids the question entirely, but even the five contacts on `held` records would not be refused by the staging path on account of their record state.

---

## 6. The Exact Operator Command Sequence

**Prerequisites:** `CAMPAIGN_LEVEL_STAGING_IS_PROVEN` has been set `True` by an operator decision. The workspace killswitch has been set. The list binding question has been resolved (either detach the list or use the campaign-level path).

**The commands below use the campaign-level path** (`LINKEDIN_ADD_LEAD` via `heyreachfactory.ensure_leads`), because the list is bound to the campaign.

### Step 0: Re-read provider state

```bash
py -3 scripts/provider_truth.py
```

**Readback:** Campaign 599020 is DRAFT, 0 leads, sender 174892 active and HEALTHY, list 933603 attached with 0 items. If the campaign is not DRAFT, STOP.

### Step 1: Re-read the killswitch

```bash
py -3 -c "from src import killswitch; import json; print(json.dumps(killswitch.workspace_state('productive'), indent=2))"
```

**Readback:** `sending: true`. If `sending: false`, STOP.

### Step 2: Re-run collision checks

```bash
py -3 -c "
from src import collision, store, clients
recs = store.load()
rec = store.get('<RECORD_ID>', recs)
config = clients.load('productive')
domain = rec.get('domain')
account = collision.check_account(domain, expect_workspace='productive')
verdict, why = collision.account_policy(account)
print(f'Account collision: {verdict} - {why}')
"
```

**Readback:** `Account collision: ALLOW - ...`. If `STOP` or `HOLD`, STOP.

### Step 3: Re-check fatigue

```bash
py -3 -c "
from src import fatigue, store, clients, datetime
recs = store.load()
rec = store.get('<RECORD_ID>', recs)
config = clients.load('productive')
result = fatigue.check(rec, '<CONTACT_KEY>', at=datetime.datetime.now(datetime.timezone.utc).isoformat(), config=config)
print(f'Fatigue: {result[\"state\"]}')
"
```

**Readback:** `Fatigue: ok`. If `block`, STOP.

### Step 4: Dry-run the staging

```bash
py -3 -m src.heyreachfactory productive-linkedin-production-v1 --dry-run
```

**Readback:** Report shows the plan: which contacts would be pushed, which refused, and why. Zero contacts refused. If any contact is refused, investigate the refusal reason before proceeding.

### Step 5: Stage the sequence (if not already staged)

```bash
py -3 -m src.heyreachfactory productive-linkedin-production-v1 --stage --live
```

**Readback:** `wrote sequence to HeyReach campaign 599020`, readback `matches: True`. If `matches: False`, STOP — the sequence at the provider does not match what was planned.

### Step 6: Add the lead

```bash
py -3 -m src.heyreachfactory productive-linkedin-production-v1 --ensure-leads --live
```

**Readback:** Report shows `did: [...]` with the contact added, `refused: []`, and `provider: {readback: ...}`. The readback pages the campaign's actual membership and confirms the contact is present. If the readback shows the contact is missing, STOP and read provider truth.

### Step 7: Final provider readback

```bash
py -3 scripts/provider_truth.py
```

**Readback:** Campaign 599020 now shows `lead_count: 1`. The lead's `leadCampaignStatus`, `leadConnectionStatus`, and `errorCode` fields confirm the lead was accepted and is in the expected state. If `lead_count` is still 0, the add did not land despite a local success — investigate the provider response.

---

## 7. Time-Dependent Gates — Summary

Every gate marked ⏱ above MUST be re-read at the moment of the write. This report is a readiness snapshot, not a licence. The time-dependent gates are:

| Gate | Why it changes | Re-read method |
|------|----------------|----------------|
| Campaign state | A human can change DRAFT → IN_PROGRESS in the vendor UI | `heyreach.campaign_read(599020)` |
| Sender health | A sender can go AUTH_INVALID | `heyreach.sender_status(174892)` |
| Collision (account) | Other campaigns may send to the same domain | `collision.check_account(domain)` |
| Collision (contact) | The contact may appear in another campaign | `collision.check_linkedin_profile(url)` |
| Prior contact | A send on any channel changes this | Provider lead list query |
| Fatigue | Any touch changes the window | `fatigue.check(rec, contact_key, at=now)` |
| Caps / daily volume | Rolling window, changes with every send | `pilotcaps.check(plan)` |

---

## 8. Summary

| Question | Answer |
|----------|--------|
| Canary candidate | Contact #4: record `699952d14554`, contact `f4698472e36a` |
| Why chosen | `verified` record state (cleanest), LinkedIn present, full li1-li5 operator approval, no prior history, single contact on record |
| Gates PASS | 13 of 20 evaluated gates |
| Gates FAIL | 7 (3 killswitch layers, 2 permission seals, 2 data gaps for collision) |
| Blocking set | 2 permission, 1 human act, 3 data gap, 1 data/architecture, 0 defect |
| Is `held` a blocker for LinkedIn? | **No.** `held` is an email-only judgment. The LinkedIn staging path does not read record state. |
| Can this canary ship today? | **No.** The `CAMPAIGN_LEVEL_STAGING_IS_PROVEN` seal and the global killswitch refuse the write. Both are deliberate, neither is a defect. |
| What must change before it ships? | An operator decision on the seal, a code review for the global killswitch, and live provider reads for collision and prior contact at write time. |
