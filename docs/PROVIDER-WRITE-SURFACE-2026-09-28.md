# Provider Write Surface — 2026-09-28

**TASK-564 audit. READ-ONLY. Zero writes performed.**

MEASURED AT: `eb017892d1cdb1fc836335c78785265386441092` (qwen-worker-3-r9)
CLAIM: qwen-worker-3-r9 / TASK-564
AUTHORITY: TASK-564 (operator, P0, 2026-09-28)
STATE: All Resonate campaigns paused. `sending.live` false. Freeze active.

---

## Summary

Two doors exist. `providerwrites.perform` is the first; the transport-level
`refuse_unauthorized_write` in `providers/__init__.py` is the second. They
protect different things and neither is sufficient alone.

**Door 1: `providerwrites.perform`** — 14 operations declared in `OPERATIONS`,
14 in `SUPPORTED`. Refuses by: unsupported operation, missing authorization,
wrong channel, wrong operation name, unspent token, failed conditional
predicate, duplicate staging, missing readback, failed readback. Writes the
action ledger on every exit (refused, unverified, failed, performed).

**Door 2: `refuse_unauthorized_write`** — sits in `_urllib_transport` before
the socket. Refuses any POST/PUT/PATCH/DELETE to a prospect-facing host unless
`RESONATE_PROVIDER_WRITES=1` or an `allow_writes()` scope is open. Host-based:
only EmailBison and HeyReach register as prospect-facing.

**The gap between them:** `bisonfactory` calls eight provider write functions
directly, bypassing `perform`. These calls are caught by Door 2 only if the
env var is absent and no scope is open. Door 1's authorization, conditional
permission, idempotency, ledger and readback requirements do NOT apply to them.

---

## Complete Write Primitive Table

### A. Operations routed through `providerwrites.perform` (Door 1)

| # | Operation | Entry point | Callers | Central enforcement | Operator auth | Canonical plan | Copy/claim gates | Suppression | Ledger effect | Scratch-callable | Production active |
|---|-----------|-------------|---------|--------------------|---------------|----------------|-----------------|-------------|---------------|-----------------|------------------|
| 1 | `heyreach.add_lead` | `heyreachfactory.ensure_leads` → `providerwrites.perform` | `heyreachfactory.ensure_leads` (called by `run.py`, `generate_campaign.py`) | YES — `perform` | YES — `Authorization` from `executionguard.authorize()` | YES — `SequencePlan` via `_mint_authorization` | `copy`, `approved_words` (via `_require_approved_words`), `sequencegate.check` (via `_refuse_sequence_gate`) | YES — `executionguard.authorize` runs suppression gate | Row on every exit (refused/unverified/performed) | YES — `import src; heyreachfactory.ensure_leads(live=True)` | YES — SUPPORTED, CONDITIONAL |
| 2 | `heyreach.set_sequence` | `heyreachfactory._write_sequence` → `providerwrites.perform` | `heyreachfactory.stage` | YES — `perform` | NO — not prospect-facing | YES — `plan["provider_sequence"]` | NO — staging, not facing | NO — staging | Row on every exit | YES | YES — SUPPORTED |
| 3 | `heyreach.pause` | `orchestrator._perform_pause` → `providerwrites.perform` | `orchestrator.pause` (Slack, supervisor, nightlysourcing) | YES — `perform` | NO — not prospect-facing | NO | NO | NO | Row on every exit | YES | YES — SUPPORTED |
| 4 | `heyreach.stop_lead` | `leadstop.stop_linkedin_contact` → `providerwrites.perform` | `leadstop.sweep`, `inbound._stop_at_provider` | YES — `perform` | NO — not prospect-facing | NO | NO | YES — inbound reply triggers | Row on every exit | YES | YES — SUPPORTED (enabled 2026-09-23) |
| 5 | `heyreach.start_empty_for_staging` | `heyreachfactory` internal | `heyreachfactory.stage` | YES — `perform` | NO — not prospect-facing | NO | NO | NO | Row on every exit | YES | YES — SUPPORTED |
| 6 | `heyreach.add_lead_to_list` | `liststaging.stage_lead` → `providerwrites.perform` | `liststaging.stage_lead` | YES — `perform` | NO — not prospect-facing | NO | NO | NO | Row on every exit | YES | YES — SUPPORTED (enabled 2026-09-16) |
| 7 | `heyreach.create_campaign` | `heyreachfactory` / `liststaging` path | Via `providerwrites.perform` | YES — `perform` | NO — not prospect-facing | NO | NO | NO | Row on every exit | YES | YES — SUPPORTED (enabled 2026-09-16) |
| 8 | `heyreach.create_list` | HeyReach factory | Via `providerwrites.perform` | YES — `perform` | NO — not prospect-facing | NO | NO | NO | Row on every exit | YES | YES — SUPPORTED (enabled 2026-09-16) |
| 9 | `heyreach.activate` | NOT WIRED to any caller | ZERO CALLERS | YES — `perform` | YES — `Authorization` required (prospect-facing) | YES | YES — `_require_approved_words` | YES | Row on every exit | YES — but no caller | YES — SUPPORTED (enabled 2026-09-16), CONDITIONAL on `_is_the_authorized_linkedin_canary` (campaign 604869 only) |
| 10 | `bison.create_campaign` | `bisonfactory._ensure_campaign` → `providerwrites.perform` | `bisonfactory.stage` | YES — `perform` | NO — not prospect-facing | NO | NO | NO | Row on every exit | YES | YES — SUPPORTED |
| 11 | `bison.set_sequence` | `bisonfactory._ensure_sequence` → `providerwrites.perform` | `bisonfactory.stage` | YES — `perform` | NO — not prospect-facing | YES — `plan["provider_sequence"]` | YES — `copylint`, `sequencegate.check` | NO — staging | Row on every exit | YES | YES — SUPPORTED |
| 12 | `bison.pause` | `orchestrator._perform_pause` → `providerwrites.perform` | `orchestrator.pause` | YES — `perform` | NO — not prospect-facing | NO | NO | NO | Row on every exit | YES | YES — SUPPORTED |
| 13 | `bison.stop_lead` | `leadstop.stop_contact` → `providerwrites.perform` | `leadstop.sweep`, `inbound._stop_at_provider` | YES — `perform` | NO — not prospect-facing | NO | NO | YES — inbound reply triggers | Row on every exit | YES | YES — SUPPORTED |
| 14 | `bison.resume` | `orchestrator._resume_at_providers` → `providerwrites.perform` | `orchestrator.resume` | YES — `perform` | NO — not prospect-facing (CONDITIONAL carries suppression re-check) | NO | NO | YES — `_resume_revalidates_suppression` CONDITIONAL | Row on every exit | YES | YES — SUPPORTED (enabled 2026-09-24) |
| 15 | `bison.assign_sender` | NOT WIRED to any caller in bisonfactory | ZERO CALLERS (bisonfactory uses `bison.attach_senders` directly — see Section B) | YES — `perform` | NO — not prospect-facing | NO | NO | NO | Row on every exit | YES — but no caller routes through perform | YES — SUPPORTED, CONDITIONAL on `_is_the_authorized_email_campaign` |
| 16 | `bison.activate` | NOT WIRED to any caller | ZERO CALLERS | YES — `perform` | YES — `Authorization` required (prospect-facing) | YES | YES | YES | Row on every exit | YES — but no caller | YES — SUPPORTED, CONDITIONAL on `_is_the_authorized_email_campaign` (campaign 485 only) |

### B. EmailBison writes BYPASSING `providerwrites.perform` (Door 2 only)

These calls go directly to `bison.*` transport functions. They are caught by
`refuse_unauthorized_write` at the socket level ONLY when
`RESONATE_PROVIDER_WRITES` is not set and no `allow_writes()` scope is open.
They do NOT get: authorization, conditional permission, idempotency check,
action ledger, mandatory readback, or `perform`'s eight refusal points.

| # | Primitive | bisonfactory function | bison transport | Call site (line) | Gates before the call | Suppression | Ledger | Scratch-callable | Production active |
|---|-----------|----------------------|-----------------|-------------------|----------------------|-------------|--------|-----------------|------------------|
| B1 | `bison.set_limits` | `_ensure_limits` | `bison.set_limits()` | bisonfactory.py:1514 | Daily volume required (refuses if absent) | NO | NO action ledger | YES — `bisonfactory.stage(live=True)` | YES — called from `bisonfactory.stage` |
| B2 | `bison.set_schedule` | `_ensure_schedule` | `bison.set_schedule()` | bisonfactory.py:1547 | Sending window required (refuses if absent); skipped if already matches | NO | NO action ledger | YES | YES — called from `bisonfactory.stage` |
| B3 | `bison.attach_senders` | `_ensure_senders` | `bison.attach_senders()` | bisonfactory.py:1578 | Senders from campaign config; readback (membership check) | NO | NO action ledger | YES | YES — called from `bisonfactory.stage` |
| B4 | `bison.ensure_custom_variables` | `_ensure_leads` | `bison.ensure_custom_variables()` | bisonfactory.py:2048 | Idempotent; creates variable names only | NO | NO action ledger | YES | YES — called from `_ensure_leads` |
| B5 | `bison.create_lead` | `_ensure_leads` | `bison.create_lead()` | bisonfactory.py:2111 | Collision check, killswitch workspace state, pre-attach status re-read | YES — `collision.check_account` + `_refuse_colliding_leads` | NO action ledger | YES | YES — called from `_ensure_leads` |
| B6 | `bison.update_lead` | `_ensure_leads` | `bison.update_lead()` | bisonfactory.py:2102, 2169 | Same as B5; stale variable reconciliation | YES — same collision/killswitch | NO action ledger | YES | YES — called from `_ensure_leads` |
| B7 | `bison.attach_leads` | `_ensure_leads` | `bison.attach_leads()` | bisonfactory.py:2206 | Pre-attach status re-read (refuses if campaign active); collision check; killswitch | YES — same collision/killswitch + pre-attach status | NO action ledger | YES | YES — called from `_ensure_leads` |
| B8 | `bison.pause_campaign` | `_ensure_stopped` | `bison.pause_campaign()` | bisonfactory.py:2412 | Status check: skips if already stopped; refuses if in FAILED state (records it); leaves RUNNING campaigns running by design | NO | NO action ledger | YES | YES — called from `_ensure_stopped` |

### C. HeyReach writes bypassing `providerwrites.perform`

**None identified.** Every HeyReach write in `heyreachfactory` routes through
`providerwrites.perform`. The `heyreach._write` / `heyreach._write_body`
transport functions are called only from within `heyreach.py`'s own write
functions, and every caller of those functions in `heyreachfactory` goes
through `perform`.

### D. Transport-level primitives (providers/bison.py, providers/heyreach.py)

These are the raw HTTP functions. They are the final transport layer and are
always called by one of the above.

**EmailBison (`bison.py`)** — all go through `_post`, `_patch`, `_put`, or
`_delete`, each of which calls `_allow(verb, path)` checking `WRITE_ROUTES`:

| Function | Route | WRITE_ROUTES member |
|----------|-------|---------------------|
| `create_campaign` | POST `/campaigns` | YES |
| `set_limits` | PATCH `/campaigns/{id}/update` | YES |
| `set_sequence` | POST `/campaigns/{id}/sequence-steps` | YES |
| `attach_leads` | POST `/campaigns/{id}/leads/attach-leads` | YES |
| `pause_campaign` | POST `/campaigns/{id}/pause` | YES |
| `resume_campaign` | POST `/campaigns/{id}/resume` | YES |
| `stop_lead` | POST `/campaigns/{id}/leads/stop-future-emails` | YES |
| `set_schedule` | POST `/campaigns/{id}/schedule` | YES |
| `attach_senders` | POST `/campaigns/{id}/attach-sender-emails` | YES |
| `create_lead` | POST `/leads` | YES |
| `update_lead` | PATCH `/leads/{id}` | YES |
| `ensure_custom_variables` | POST `/custom-variables` | YES |

**HeyReach (`heyreach.py`)** — all go through `_write` or `_write_body`, each
checking `WRITE_ROUTES`:

| Function | Route | WRITE_ROUTES member |
|----------|-------|---------------------|
| `pause_campaign` | POST `/campaign/Pause` | YES |
| `start_campaign` | POST `/campaign/StartCampaign` | YES |
| `resume_campaign` | POST `/campaign/Resume` | YES |
| `create_list` | POST `/list/CreateEmptyList` | YES |
| `create_campaign` | POST `/campaign/Create` | YES |
| `set_sequence` | POST `/campaign/UpdateSequence` | YES |
| `add_senders` | POST `/campaign/AddLinkedInAccountsToCampaign` | YES |
| `remove_senders` | POST `/campaign/RemoveLinkedInAccountsFromCampaign` | YES |
| `stop_lead_in_campaign` | POST `/campaign/StopLeadInCampaign` | YES |
| `add_leads_to_campaign` | POST `/campaign/AddLeadsToCampaignV2` | YES |
| (list add) | POST `/list/AddLeadsToListV2` | YES |

---

## Three Seeded Findings — Confirmed or Refuted

### Finding 1: `refuse_unauthorized_write` is ROOT-relative and protects nothing from a worktree

**PARTIALLY CONFIRMED, but the mechanism is different from what the finding states.**

`ROOT` is computed at `providers/__init__.py:17`:
```python
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
```

This resolves to the worktree's own root. `ROOT` is used for:
1. `ENV_FILE` — loading `config/.env` with real provider credentials
2. `_log_refusal` — the refusal log path (default: `work/provider-write-refusals.jsonl`)

The **enforcement decision** in `refuse_unauthorized_write` does NOT use ROOT.
It calls `writes_allowed(url)` which checks:
- `_write_scopes` ContextVar (set by `allow_writes()`)
- `RESONATE_PROVIDER_WRITES` env var

Neither is worktree-aware. A worktree with `RESONATE_PROVIDER_WRITES=1` set,
or code that opens an `allow_writes()` scope, can write to live providers.
The guard is process-level, not filesystem-level.

**The real risk:** QWEN.md confirms `config/.env` is present in ALL EIGHT
worktrees with real provider keys. The transport guard protects against
accidental writes (a chain of library calls the caller did not intend), NOT
against a determined in-process actor. This is stated and conceded in
`providers/__init__.py:345-352`: "It is NOT enforcement against a determined
in-process actor. Anything running in this process can call
`allow_writes('because I said so')`, set the env var, or monkeypatch
`writes_allowed`."

**Verdict:** The guard is real and caught the 487 incident. But it is a
process-level guard, not a worktree-level one. A worktree that sets the env
var or opens a scope has the same write authority as production. The finding
is correct in spirit — worktree execution is not structurally separated from
production writes — but the mechanism is env-var/ContextVar, not ROOT-relative
path resolution.

### Finding 2: An audit agent paused live campaign 487 by importing src and calling through

**CONFIRMED AS THE MOTIVATING INCIDENT FOR THE TRANSPORT GUARD.**

The `refuse_unauthorized_write` function's docstring and the `allow_writes`
class both reference this incident. The guard was added specifically because
an audit agent importing `src` and calling through `orchestrator.pause`
reached the transport and paused campaign 487.

The fix was two-layered:
1. **Door 2** (`refuse_unauthorized_write`): refuses at the socket unless the
   process opts in via env var or `allow_writes()`.
2. **Door 1** (`providerwrites.perform`): requires authorization, readback,
   ledger, etc.

**Is the route closed for every primitive, or only for pause?**

For primitives going through `perform`: YES, closed. `perform` refuses without
`SUPPORTED` membership, and prospect-facing operations refuse without a real
`Authorization` from `executionguard.authorize()`.

For the 8 bisonfactory direct calls (Section B): they bypass `perform` and
are caught ONLY by Door 2. If `RESONATE_PROVIDER_WRITES=1` is set (which it
is in production for legitimate staging), these calls are permitted without
the authorization, ledger, or readback that `perform` would require.

**Verdict:** The pause route is closed at both doors. But the 8 direct
bisonfactory calls are protected only at Door 2, and Door 2 is a process-level
opt-in, not a per-operation gate.

### Finding 3: `bisonfactory._refuse_sequence_gate` has no tenant guard; `offers.py` returns Productive's offers for every client

**CONFIRMED.**

`_refuse_sequence_gate` (bisonfactory.py:702) calls `sequencegate.check` with
the lead's sequence, qualification, facts, capability, offer, messaging_rules,
and batch_capabilities. It does NOT pass a tenant or client identifier, and
`sequencegate.check` does not filter by tenant.

`offers.for_campaign(campaign_id)` (offers.py:107) loads ALL offers from
`config/clients/productive-offers.yaml` and filters by `campaign_id` only.
There is no client/tenant filter. If multiple clients share the same
productive-offers.yaml (which is the current single-client deployment), this
is not a live incident but it is a structural gap: the offer library is
single-tenant by deployment, not by enforcement.

**Impact on the write surface:** The sequence gate checks copy quality, not
tenant ownership. A campaign for client A could theoretically use client B's
offers if both are in the same file. This is a copy/claim gate gap, not a
write authorization gap — it affects WHAT is written, not WHETHER something
is written.

**Verdict:** Confirmed as a structural gap. Not exploitable in the current
single-tenant deployment, but the enforcement is absent rather than satisfied.

---

## Rows Where a Mistake Would Reach a Real Person

Ranked by blast radius. These are the primitives where a bug, a misconfigured
gate, or a bypassed check could cause a prospect to receive a message they
should not.

### CRITICAL — prospect-facing, SUPPORTED, with callers

1. **`heyreach.add_lead`** (row A1) — The ONLY prospect-facing route with
   active callers and real writes. CONDITIONAL on
   `_campaign_is_a_declared_staging_campaign`, which is currently RESEALED
   (`CAMPAIGN_LEVEL_STAGING_IS_PROVEN = False`). The condition refuses every
   campaign, making this route inert in practice. If the seal were lifted
   without the condition working correctly, a lead added to a RUNNING campaign
   would receive messages immediately.

2. **`heyreach.activate`** (row A9) — SUPPORTED and CONDITIONAL on
   `_is_the_authorized_linkedin_canary` (campaign 604869 only). Has ZERO
   callers in the wired code. If a caller were added, it would start a
   campaign sending to real people. The condition limits it to one campaign.

3. **`bison.activate`** (row A16) — SUPPORTED and CONDITIONAL on
   `_is_the_authorized_email_campaign` (campaign 485 only). Has ZERO callers.
   Same shape as above — the condition limits it to one campaign.

4. **`bison.resume`** (row A14) — SUPPORTED, routed through `perform`, called
   by `orchestrator.resume`. Carries a CONDITIONAL suppression re-check
   (`_resume_revalidates_suppression`). A resume puts a paused campaign back
   into sending. The `expect_leads` guard in `bison.resume_campaign` refuses
   when the provider disagrees with the expected lead count.

### HIGH — bypass `perform`, reach the provider directly

5. **`bison.attach_leads`** (row B7) — Attaches leads to an EmailBison
   campaign. If the campaign is active, leads are acted on immediately.
   The pre-attach status re-read catches this, but the call bypasses `perform`'s
   authorization, ledger, and readback requirements.

6. **`bison.create_lead`** (row B5) — Creates a lead in EmailBison. Not
   prospect-facing on its own (the lead must be attached to a campaign
   afterwards), but it is the first step in the chain.

7. **`bison.update_lead`** (row B6) — Rewrites custom variables on an
   existing lead. If the variables carry wrong copy, the prospect receives
   incorrect content. The collision check and killswitch are the only gates.

### MEDIUM — staging, not directly prospect-facing

8. **`bison.set_sequence`** (row A11) — Writes copy onto an EmailBison
   campaign. Not prospect-facing if the campaign is stopped (and
   `_ensure_stopped` runs before `_ensure_sequence`). `bison.set_sequence`
   APPENDS rather than replacing, so a double-write builds a duplicate
   sequence.

9. **`heyreach.set_sequence`** (row A2) — Writes a sequence onto a HeyReach
   campaign. Replaces the whole graph (unlike EmailBison's append), so a
   double-write is safe. Not prospect-facing if the campaign holds nobody.

10. **`bison.set_limits`** (row B1), **`bison.set_schedule`** (row B2),
    **`bison.attach_senders`** (row B3) — Configuration primitives. Wrong
    values could cause a campaign to send at the wrong time, from the wrong
    inbox, or without a daily cap. All three are staging, not facing.

### LOW — stopping verbs, can only reduce exposure

11. **`heyreach.pause`** (row A3), **`bison.pause`** (row A12) — Can only
    stop a campaign. A mistake here means a campaign that should have been
    stopped continues sending.

12. **`heyreach.stop_lead`** (row A4), **`bison.stop_lead`** (row A13) —
    Can only stop one person. A mistake means one person continues receiving.

13. **`bison.pause_campaign`** (row B8) — Direct call, bypasses `perform`.
    Can only stop a campaign. The `_ensure_stopped` function deliberately
    leaves RUNNING campaigns running (re-staging reconciles material but does
    not stop a live campaign).

---

## `push.py` — the send path

`push.run(live=True)` raises `LiveSendNotEnabled`. The function is
preparation-only: it builds payloads, checks eligibility, reports caps. No
code in `push.py` reaches a provider transport. The `--live` flag prints
"REFUSED" and exits with code 2.

---

## `heyreachfactory._mint_authorization` — the Authorization construction path

`heyreachfactory._mint_authorization` (line 1056) calls
`executionguard.authorize()` to construct the Authorization object. It does
NOT construct the object directly. The docstring at line 1061 states:
"THE AUTHORIZATION COMES FROM executionguard.authorize(), NOT FROM
CONSTRUCTING THE OBJECT DIRECTLY. providerwrites.perform checks with
isinstance, so a hand-built object passes while having passed no gate."

This is the ONLY path in `heyreachfactory` that mints an Authorization, and
it goes through the canonical gate ladder. The `isinstance` check in
`perform` catches hand-built objects.

---

## Scratch script reachability

Every primitive in Sections A and B is reachable from a scratch script:
`import src; from src import bisonfactory, heyreachfactory, orchestrator, leadstop, liststaging`.

Door 2 (`refuse_unauthorized_write`) is the ONLY guard that applies when
`RESONATE_PROVIDER_WRITES` is not set and no `allow_writes()` scope is open.
Setting the env var or opening a scope removes this guard.

Door 1 (`perform`) applies only to operations in Section A. The 8 operations
in Section B bypass it entirely.

---

## GLM verification

GLM verifies this table against branch head
`eb017892d1cdb1fc836335c78785265386441092` (qwen-worker-3-r9).
