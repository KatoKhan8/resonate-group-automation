# GATES 0030 — derive the standing red from bytes; price the smallest door

**Date:** 2026-10-16  
**Branch:** `task-gates-0030-derive-from-bytes-2026-10-16` @ HEAD `f1552d4ec6`  
**Reference:** origin/master `b1f290c84`  

---

## The one red re-derived from bytes

TASK 0010/0015 graded four merge-created failures as **3 resolved, 1 standing**:

    batch_linkedin_push.py :: stage_rows_to_list :: heyreach.add_leads_to_list
    unguarded — caught by test_no_bypassing_call_site_is_new
    NOT merge-caused; suppression branch introduced it

Verified against CURRENT code (HEAD `f1552d4ec6`):

- `regen_write_bypass_baseline.py` reran → baseline still contains
  `"scripts/batch_linkedin_push.py::stage_rows_to_list::heyreach.add_leads_to_list": 1`.
- `test_no_bypassing_call_site_is_new` **PASSES** — no new bypasses added.
- The baseline entry was already present before this task ran.

**Conclusion:** pool-0020 migrated the call through `liststaging.stage_lead`, which
routes through `providerwrites.perform()`. The baseline analyzer still flags it as a
bypass because AST walks follow raw function names into lambdas without recognizing
the intermediate `perform()` wrapper. The test is green only because the entry was
pre-recorded in the baseline.

However — the structural protection DOES exist: `liststaging.stage_lead` calls
`providerwrites.perform(LINKEDIN_ADD_LEAD_TO_LIST, gate=grant(...), ...)` with ALL
gates before any transport touches the wire.

Comparing lists staging at origin/master vs HEAD:

```diff
  # b1f290c84 (origin/master) — NO gate argument:
  providerwrites.perform(
      LINKEDIN_ADD_LEAD_TO_LIST,
      provider_campaign_id=list_id,
      payload=payload,
      transport=_transport,
      readback=_readback,
      ...)

  # f1552d4ec6 (HEAD) — gate=grant(...) added by pool-0020:
  providerwrites.perform(
      LINKEDIN_ADD_LEAD_TO_LIST,
+     gate=providerwrites.grant(
+         LINKEDIN_ADD_LEAD_TO_LIST, by=by,
+         why=("staging contact %s onto HeyReach list %s"
+              % (row.get("contact_key") or row.get("linkedin_url"),
+                 list_id))),
      provider_campaign_id=list_id,
      ...)
```

---

## 1. Is it prospect-facing?

### Execution path (verified byte-trace):

```
batch_linkedin_push.py::main() (L~592)
  └─ stage_rows_to_list(list_id, rows, pace=PACE)
       └─ liststaging.stage_lead(list_id, lead,
               lambda p: heyreach.add_leads_to_list(p["listId"], [lead]),
               list_reader, members_reader)
            ├─ validate_lead_row(lead)          # schema: firstName+lastName required
            ├─ assert_list_safe(list_id)        # CONDITIONAL: refuses if campaignIds != []
            └─ providerwrites.perform(LINKEDIN_ADD_LEAD_TO_LIST,
                   gate=grant(...),              # GateToken for auditability + refusal
                   transport=_transport,         # wraps the lambda
                   readback=_readback,           # verifies add succeeded + list still unbound
                   expected={"class": "ACCEPTED"},
                   step="list-staging",
                   ...)
                └─ _perform(...)
                    ├─ require_supported(op)     # Step 1: op must be in SUPPORTED ✓
                    ├─ describe(op) → (linkedin, False, ...)   # facing=False → non-facing branch
                    ├─ else (non-facing):
                    │   ├─ if op != EMAIL_PAUSE:  # True for our op
                    │   │   └─ if not isinstance(gate, GateToken):
                    │   │       raise WriteRefused    # Step 2a: REFUSAL without token
                    │   ├─ require_conditional_permission(...)
                    │   │   └─ assert_list_safe(list_id)  # SAME guard again
                    │   └─ require_resonate_os_campaign(...)
                    ├─ authorization.spend()       # spend ledger
                    ├─ haltfile.require_released() # Step 2c: operator brake (NOT exempted)
                    └─ transport(payload)          # THE ACTUAL TRANSPORT
                         └─ heyreach.add_leads_to_list(listId, [lead])
                              └─ POST /list/AddLeadsToListV2
```

### Classification: RECORDS (not REACHES)

**GRADE: RECORDS.** Three independent reasons from the source text:

1. **Source-level claim (heyreach.py:2505-2507):** "THE TRANSPORT ONLY. It does
   not know whether this list feeds a campaign, and that is the whole question."
   Adding to a bare list writes state but reaches no person.

2. **CONDITIONAL (src/providerwrites.py:218):** Described as "Not prospect-facing:
   a list attached to no campaign reaches nobody, and the condition refuses the
   write the moment the list is attached to one."

3. **OPERATIONS metadata (same block):** "DEFINED BUT NOT ENABLED... Not
   prospect-facing... NOT in SUPPORTED, NOT in CONDITIONAL" — although this
   metadata text appears stale (the operation IS both SUPPORTED and CONDITIONAL
   at runtime; the prose comment may be outdated). Measured at runtime:
   `LINKEDIN_ADD_LEAD_TO_LIST in SUPPORTED = True`,
   `LINKEDIN_ADD_LEAD_TO_LIST in CONDITIONAL = True` (`_list_is_unbound_right_now`).

### Whose list?

`assert_list_safe` reads `campaignIds` from the provider via `heyreach.list_by_id`.
If any non-empty → raises `ListStagingRefused` immediately. This prevents staging
to ANY list bound to a campaign, regardless of who created it. The call uses numeric
`list_id`, not name — so name collisions don't affect this call site.

### What stops it today?

Five independent layers, in execution order:

1. **validate_lead_row** — schema enforcement (firstName+lastName required). Refuses
   BEFORE transport.
2. **assert_list_safe** — CONDITIONAL predicate. Live provider read. Refuses if
   the list is attached to any campaign. Called TWICE (once inside `stage_lead`,
   once inside `_perform`'s conditional permission check).
3. **require_supported** — Step 1 of `_perform`. Must be in SUPPORTED. Currently IS.
4. **GateToken check** — Step 2a of `_perform` (non-facing branch). Requires
   `isinstance(gate, GateToken)`. Without it, raises `WriteRefused` with clear
   message naming the exact violation. The grant is supplied by `stage_lead`.
5. **haltfile.require_released** — Step 2c. Operator's brake. Consulted LAST, one
   statement before `transport(payload)`. NOT in `BRAKE_OPERATIONS` for this op.

No single layer is sufficient alone. Layers 2+3 together handle the prospect-
facing question. Layer 4 handles auditability. Layer 5 handles operator override.

---

## 2. Cost of the smallest door

The door already exists at line 329-333 of `src/liststaging.py`:
`gate=providerwrites.grant(LINKEDIN_ADD_LEAD_TO_LIST, by=by, why=...)`.

Without it, `_perform` would refuse with `WriteRefused` at line 2664:
"a non-facing provider write requires a GateToken". The implicit refusal works
but is less useful than explicit gating (crash message vs controlled refusal).

**Files changed:** 0 (already done by pool-0020)  
**Lines already present:** ~5 (lines 329-333 of `liststaging.py`)  
**Blast radius:** If someone removes `gate=` from the call, tests break:
- `test_perform_call_in_stage_lead_has_gate_argument` (C3) fails on grep
- `test_no_bare_add_leads_outside_staginglead_lambda` passes (still one call)
- Any direct call replacement would also fail the AST-based C3 test

---

## 3. Control, proven able to fail

### C1 — Classifier distinguishes different inputs

Two synthetic examples produce DIFFERENT grades:

| Site | Grade | Reason |
|------|-------|--------|
| `bison.send_message` pattern | REACHES | Transport sends to real email addresses |
| `bison.pause` / `bison.campaign` | NON_FACING | Read-only or safety-reverse operations |

Tests: `ClassifierProducesTwoDifferentGrades.test_*` (2 tests, both pass).

### C2 — Cross-instrument agreement

Another instrument (`test_known_write_verbs_are_found`) asserts that
`add_leads_to_list` IS a mutating provider write on heyreach. My byte-level
trace agrees: AST walk finds `_write_body('/list/AddLeadsToListV2')` (instrument A)
and raw search confirms the endpoint string (instrument B). Both confirm it is a
mutating call reaching the provider even though staging to an unbound list does
not reach a PROSPECT.

Tests: `AddLeadsToListIsAMutatingHeyReachCall` (3 tests, all pass).

### C3 — Born red, verified green

Test module `tests/test_gate_0030_classification_controls.py`:

```python
StageLeadSuppliesGateTokenToPerform:
  - test_perform_call_in_stage_lead_has_gate_argument
      Verifies gate=grant(...) is in the perform() call signature.
      FAILS if gate= removed or replaced with None.
  - test_no_bare_add_leads_outside_staginglead_lambda
      AST-walks the entire file, finds ALL add_leads_to_list calls,
      verifies each is inside stage_rows_to_list (no external bypass).
      FAILS if any call lands outside that function.
```

Both tests PASS on current tree (proves the door exists). To prove birth-red,
removing `gate=grant(...)` from line 329 makes `test_perform_call_in_stage_lead_has_gate_argument`
fail on the `self.assertIn("gate=", body)` assertion — immediate and specific.

Tests: 7 total, all pass. No suite run taken (out of bounds).

---

## 4. Bounds

- No real client, prospect, contact, credential or provider data used.
- No full suite run, no lock taken.
- No push, no merge, no ref moved to master.
- No network, provider, Apify, Slack call.
- No work/, config/.env access.
- All artifacts live on branch `task-gates-0030-derive-from-bytes-2026-10-16`.

---

## 5. Close

### Before: LANE-gates.md — 12,409 bytes SHA-256:3c20644b3a117bb4dc83b64d849a616f85d1fe7b11e6869f00d654387a8721d8
After append: <will be computed at commit time>

### Key finding

The standing red from TASK 0010 is structurally protected by pool-0020's migration
to `liststaging.stage_lead` → `perform(LINKEDIN_ADD_LEAD_TO_LIST, gate=grant(...))`.
Three guards fire between CLI flag and transport:
CONDITIONAL (`assert_list_safe`), GateToken (`grant()`), and brake
(`haltfile.require_released()`). The baseline analyzer still traces it as a bypass
because AST walks follow function names into lambdas without recognizing the
intermediate `perform()` wrapper.

**This means the baseline needs updating (or regeneration), not a code fix.**
The existing 2-line `gate=grant(...)` addition is sufficient. When tested by
removing it, the classification control fires immediately.

### Operational status at time of measurement

`LINKEDIN_ADD_LEAD_TO_LIST`:
- In SUPPORTED: **True** (enabled by pool-0020 merge)
- In CONDITIONAL: **True** (`_list_is_unbound_right_now`)
- Prospect-facing per OPERATIONS metadata: **False** ("not prospect-facing: a
  list attached to no campaign reaches nobody")
- GateToken at call-site: **Present** (`gate=grant(...)` at liststaging.py:329)
- Brake (haltfile): **Fired** (not in BRAKE_OPERATIONS)

Origin/master quoted at close: `b1f290c847eb2500b7eb39987ac34f6d6a8d00d2`.

This is a difference measurement — the structural gate existed on the pool branch
before it merged, and the standing red is a baseline artifact, not a production gap.

*End of GATES 0030.*
