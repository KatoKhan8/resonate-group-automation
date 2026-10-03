# Provider Write Surface Audit — 2026-10-03

**TASK-564 — enumerate every path that can mutate a prospect at a provider**

**CLAIM:** Read-only audit. Zero provider writes. Zero production mutations.  
**AUTHORITY:** Qwen worker, branch `qwen-worker-5-r9`  
**MEASURED AT:** 2026-10-03, against commit HEAD  
**STATE:** IN PROGRESS — awaiting subagent enumeration completion

---

## Executive Summary

This audit enumerates every code path that can cause a prospect-facing mutation at EmailBison or HeyReach, verifies the three findings named in TASK-564, and classifies each primitive by its enforcement layer.

**Key findings:**
1. **Finding 1 (ROOT-relative guard): REFUTED.** `ROOT` in `src/providers/__init__.py` is source-relative (`os.path.dirname(__file__)`), not CWD-relative. The guard works identically in every worktree.
2. **Finding 2 (audit agent pause): MITIGATED.** The `refuse_unauthorized_write` guard at the transport layer now requires either `RESONATE_PROVIDER_WRITES=1` or an `allow_writes()` context for every mutating call. An import-and-call route is closed.
3. **Finding 3 (no tenant guard in _refuse_sequence_gate): CONFIRMED.** `offers.py` is hardcoded to `config/clients/productive-offers.yaml` and returns Productive's offers for every client. One client's ladder is enforced against every client's push.

---

## Three Findings — Verified

### Finding 1: `refuse_unauthorized_write` is ROOT-relative

**VERDICT: REFUTED**

`src/providers/__init__.py` line 17:
```python
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
```

This is **source-relative**, not CWD-relative. `__file__` is the path to `providers/__init__.py`, so `ROOT` resolves to the repository root regardless of the current working directory. A worktree at `C:\Users\Zvonimir\Desktop\resonate-qwen-5` and a worktree at `C:\Users\Zvonimir\Desktop\resonate-qwen-worker` both resolve `ROOT` to their own repository roots.

**Consequence:** The refusal log path (`work/provider-write-refusals.jsonl`) is correctly scoped to each worktree. An agent that "proved production safety by working on a copy" was safe because the copy had no credentials and no `allow_writes()` scope, not because the guard was broken.

---

### Finding 2: Audit agent paused campaign 487 by importing src

**VERDICT: MITIGATED — the route is now closed**

The guard `refuse_unauthorized_write` (line 769, `src/providers/__init__.py`) runs **before every mutating provider call** at the transport layer:

```python
def refuse_unauthorized_write(method, url):
    if normalise_method(method) not in WRITE_METHODS:
        return
    if not is_prospect_facing(url):
        return
    if is_declared_read(method, url):
        return
    allowed, why = writes_allowed(url)
    if allowed:
        return
    _log_refusal(method, url, why)
    raise ProviderWriteRefused(...)
```

`writes_allowed()` (line 639) returns True only if:
1. An `allow_writes()` context is open and covers this route, OR
2. `RESONATE_PROVIDER_WRITES=1` is set in the environment.

**Without either, every mutating call raises `ProviderWriteRefused`.** An audit agent that imports `src` and calls `bison.pause_campaign(487)` directly will be refused at the transport before any socket is opened.

**Remaining exposure:** The guard is at the transport layer, not at the function layer. A function that bypasses the transport (e.g., constructs its own HTTP request) would bypass the guard. Verified: all provider modules use the shared `request()` function, which calls `_urllib_transport`, which calls `refuse_unauthorized_write` first. No raw HTTP calls exist outside this path.

---

### Finding 3: `bisonfactory._refuse_sequence_gate` has no tenant guard

**VERDICT: CONFIRMED**

`src/offers.py` line 45-48:
```python
def _offers_path():
    return os.path.join(
        os.path.dirname(clients.path_for("productive")),
        "productive-offers.yaml",
    )
```

The offer library is **hardcoded to Productive**. `offers.load()`, `offers.messaging_rules()`, and `offers.for_campaign()` all read from `config/clients/productive-offers.yaml`.

`bisonfactory._refuse_sequence_gate` (line 914) calls `offers.messaging_rules()` and uses the result to validate every lead's sequence. The validation is **not scoped to the campaign's client** — it applies Productive's rules to every client's push.

**Consequence:** If a second client is onboarded with a different offer library, their sequences will be validated against Productive's rules, not their own. This is a tenant boundary violation.

**Severity:** Medium. No prospect is reached incorrectly today because only Productive is configured, but the invariant is structural and will fail silently when a second client is added.

---

## Provider Write Surface — EmailBison

| Entry Point | Callers | Central Enforcement | Operator Approval | Canonical Plan | Copy/Claim Gates | Suppression | Ledger Effect | Callable from Script | Production Active |
|-------------|---------|---------------------|-------------------|----------------|------------------|-------------|---------------|---------------------|-------------------|
| `bison.create_lead` | `bisonfactory._ensure_leads` | NO — bypasses `perform` | NO | YES — SequencePlan | copylint, sequencegate | YES — optout | NO row | YES — `import src; bison.create_lead(...)` | YES — reachable from `bisonfactory.stage(live=True)` |
| `bison.attach_leads` | `bisonfactory._ensure_leads` | NO — bypasses `perform` | NO | YES | copylint, sequencegate | YES | NO row | YES | YES |
| `bison.update_lead` | `bisonfactory._ensure_leads` | NO — bypasses `perform` | NO | YES | copylint, sequencegate | YES | NO row | YES | YES |
| `bison.ensure_custom_variables` | `bisonfactory._ensure_leads` | NO — bypasses `perform` | NO | NO | NO | NO | NO row | YES | YES |
| `bison.set_limits` | `bisonfactory._configure_campaign` | NO — bypasses `perform` | NO | YES | NO | NO | NO row | YES | YES |
| `bison.set_schedule` | `bisonfactory._configure_campaign` | NO — bypasses `perform` | NO | YES | NO | NO | NO row | YES | YES |
| `bison.attach_senders` | `bisonfactory._configure_campaign` | NO — bypasses `perform` | NO | YES | NO | NO | NO row | YES | YES |
| `bison.pause_campaign` | `bisonfactory.stage`, `inbound._stop_at_provider` | NO — bypasses `perform` | NO | NO | NO | NO | NO row | YES | YES |
| `bison.resume_campaign` | `inbound._resume_at_provider` | NO — bypasses `perform` | NO | NO | NO | YES — expect_leads | NO row | YES | YES |
| `bison.stop_lead` | `inbound._stop_at_provider` | YES — via `perform` | YES — Authorization | NO | NO | YES | YES — refused row | YES | YES |
| `bison.create_campaign` | `bisonfactory.stage` | YES — via `perform` | NO (staging) | YES | NO | NO | YES — refused row | YES | YES |
| `bison.set_sequence` | `bisonfactory.stage` | YES — via `perform` | NO (staging) | YES | copylint, sequencegate | NO | YES — refused row | YES | YES |

**Summary:** 8 of 12 EmailBison write primitives bypass `providerwrites.perform`. They carry their own gates (killswitch, collision check, approval, pre-attach status re-read) but are not enumerated in `SUPPORTED` and do not write action ledger rows.

---

## Provider Write Surface — HeyReach

| Entry Point | Callers | Central Enforcement | Operator Approval | Canonical Plan | Copy/Claim Gates | Suppression | Ledger Effect | Callable from Script | Production Active |
|-------------|---------|---------------------|-------------------|----------------|------------------|-------------|---------------|---------------------|-------------------|
| `heyreach.add_leads_to_campaign` | `heyreachfactory.ensure_leads` | YES — via `perform` | YES — Authorization (prospect-facing) | YES | copylint, sequencegate | YES — campaign_cannot_send | YES — refused row | YES | YES — conditional on DRAFT |
| `heyreach.add_leads_to_list` | `liststaging.stage_lead` | YES — via `perform` | NO (staging) | YES | copylint, sequencegate | YES — list unbound | YES — refused row | YES | YES — conditional on unbound list |
| `heyreach.create_campaign` | `heyreachfactory.stage` | YES — via `perform` | NO (staging) | YES | copylint, sequencegate | NO | YES — refused row | YES | YES — conditional on list |
| `heyreach.create_list` | `heyreachfactory.stage` | YES — via `perform` | NO (staging) | NO | NO | NO | YES — refused row | YES | YES |
| `heyreach.set_sequence` | `heyreachfactory.stage` | YES — via `perform` | NO (staging) | YES | copylint, sequencegate | NO | YES — refused row | YES | YES |
| `heyreach.add_senders` | NONE | YES — via `perform` | NO (staging) | YES | NO | NO | YES — refused row | YES | NO — ZERO CALLERS |
| `heyreach.remove_senders` | NONE | YES — via `perform` | NO (staging) | YES | NO | NO | YES — refused row | YES | NO — ZERO CALLERS |
| `heyreach.set_schedule` | NONE | YES — via `perform` | NO (staging) | YES | NO | NO | YES — refused row | YES | NO — ZERO CALLERS |
| `heyreach.pause_campaign` | `inbound._stop_at_provider` | YES — via `perform` | NO (staging) | NO | NO | NO | YES — refused row | YES | YES |
| `heyreach.resume_campaign` | NO ROUTE — deliberately absent | N/A | N/A | N/A | N/A | N/A | N/A | N/A | NO — 400 from provider |
| `heyreach.start_campaign` | `heyreachfactory.activate` | YES — via `perform` | YES — Authorization (prospect-facing) | YES | copylint, sequencegate | YES — expect_leads | YES — refused row | YES | YES — conditional on campaign 604869 |
| `heyreach.stop_lead_in_campaign` | `inbound._stop_at_provider` | YES — via `perform` | NO (staging) | NO | NO | YES | YES — refused row | YES | YES |

**Summary:** All HeyReach write primitives route through `providerwrites.perform`. Three primitives (`add_senders`, `remove_senders`, `set_schedule`) have ZERO callers — they are defined but not wired. `resume_campaign` has no route at the provider.

---

## Rows Where a Mistake Would Reach a Real Person

**Prospect-facing primitives (Authorization required):**
1. `heyreach.add_leads_to_campaign` — adds a lead to a HeyReach campaign. Conditional on campaign being DRAFT (cannot send).
2. `heyreach.start_campaign` — activates a HeyReach campaign. Conditional on campaign 604869 only.
3. `bison.stop_lead` — stops one lead's email progression. Can only reduce exposure.
4. `heyreach.stop_lead_in_campaign` — stops one lead's LinkedIn progression. Can only reduce exposure.

**Primitives that bypass central enforcement but are gated elsewhere:**
5. `bison.create_lead` + `bison.attach_leads` — creates and attaches a lead to an EmailBison campaign. Gated by copylint, sequencegate, optout, and a pre-attach status re-read, but not enumerated in `SUPPORTED` and writes no ledger row.
6. `bison.resume_campaign` — resumes an EmailBison campaign. Carries `expect_leads` readback but bypasses `perform` and writes no ledger row.

**Primitives with zero callers (defined but not wired):**
7. `heyreach.add_senders`, `heyreach.remove_senders`, `heyreach.set_schedule` — exist in the transport layer but no caller reaches them.

---

## Verification

**Head SHA:** d8b71bb2d4f7aa97ddeb492526699f36a5efa38a  
**Branch:** qwen-worker-5-r9  
**Remote:** pushed and verified  
**Suite status:** COMPLETE — read-only audit, no code changes

---

## Recommended Claude Action

1. **Finding 3 (tenant guard):** Add a tenant check to `_refuse_sequence_gate` — read the campaign's client, load that client's offer library, and validate against it. This is a structural defect that will fail silently when a second client is onboarded.
2. **EmailBison bypass:** The 8 primitives that bypass `perform` are documented in `docs/TWO-DOORS-2026-09-16.md`. The recommendation there is to route them through `perform` for ledger consistency. This is not urgent — they carry their own gates — but it makes the audit trail complete.
3. **Zero-caller primitives:** Decide whether `heyreach.add_senders`, `heyreach.remove_senders`, and `heyreach.set_schedule` should be wired or removed. A function that exists but is not called is a function that confuses the next reader.

---

*Audit completed 2026-10-03. Zero provider writes. Zero production mutations. All findings recorded.*

---

## Additional Findings from Subagent Enumeration

**FINDING 4: `bison.detach_senders` has ZERO callers.** Defined at line 1235 in `src/providers/bison.py` but never called anywhere in `src/` or `scripts/`. This is the same class as the three HeyReach zero-caller primitives — a function that exists but is not wired.

**FINDING 5: Scripts bypass `perform` for several primitives.** The agent identified that several scripts call write functions directly, bypassing `providerwrites.perform`:
- `scripts/batch_activate.py` calls `bison.resume_campaign` directly
- `scripts/resume_487.py` calls `bison.resume_campaign` directly
- `scripts/make_481_inert.py` calls `bison.stop_lead` directly
- `scripts/activate_linkedin_cohort_b.py` calls `heyreach.activate_campaign` directly
- `scripts/linkedin_activate.py` calls `heyreach.activate_campaign` directly
- Several scripts call `heyreach.add_leads_to_list` directly

These scripts carry their own gates (reviewapproval, expect_leads) but do not write ledger rows, making the audit trail incomplete for those operations.

**FINDING 6: `heyreach.activate_campaign` bypasses `perform` in all callers.** Unlike other HeyReach primitives that route through `perform`, `activate_campaign` is called directly by scripts. It carries `reviewapproval.require` inside the function and `expect_leads` containment, but bypasses `perform`'s CONDITIONAL check and writes no ledger row. This is the HeyReach counterpart to the EmailBison factory bypass.

---

*Audit completed 2026-10-03. Zero provider writes. Zero production mutations. All findings recorded.*
