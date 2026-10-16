# LANE-gates

Lane for the GateToken / non-facing provider-write guard work (TASK-0395 + guards regression suite).

## Summary — tasks 0010 + 0015 measured on branch `task-suppression-0395-both-guards-2026-10-16` @ `f1552d4ec` vs origin/master `b1f290c84`

The suppression branch (`suppression/0397`) closed an open question from CONTINUITY.md §6: whether `f1552d4ec`'s grant mint already resolves the four failures it identified. **3 of 4 are resolved** — `batch_activate.py::main`, `resume_487.py::main`, and `bisonfactory.py::_ensure_senders` now route through `perform()` with explicit `grant()` calls. **1 residual**: `batch_linkedin_push.py::stage_rows_to_list` is a fresh bypass site introduced by the suppression branch itself (not a merge-created failure), caught by `test_no_bypassing_call_site_is_new`. Total measurement: 650 tests across 34 gate-candidate modules; 11 unique failing names (3 directly gate-related, 8 pre-existing fatigue/activation/free-leg failures).

---

## GATES 0010 — suppression-branch gate measurement

**Date:** 2026-10-16  
**Branch:** `task-suppression-0395-both-guards-2026-10-16` @ `f1552d4ec`  
**Reference:** origin/master @ `b1f290c84`  
**Compared against:** composed base (integ + glm-c), --no-ff, no -X, 24 red of denominator 47

### Method

Created detached checkout at f1552d4ec. Ran gate-specific modules with `/c/Users/Zvonimir/AppData/Local/Python/bin/python3 -m unittest`. Did NOT run the full 47-module suite (lock held by another lane). Pin confounders: Windows store `py` stub replaced by absolute path; CRLF in worktree vs LF elsewhere accounted for via git stash/pop transitions; Python 3.14.3.

Name extractor: custom `scripts/parse_gate_modules.py` anchoring on closing-summary lines (`^(FAIL|ERROR):`) rather than run_suite.py's unanchored `.search`.

### Results: fate of the 4 merge-created failures

The original 4 failures on the composed base traced to bypass-baseline entries expecting direct-provider-call patterns that became incompatible when the suppress branch added `gate=grant(...)` around the same sites.

| # | Site (module::func::provider_call) | Composed Base | f1552d4ec | Verdict |
|---|-----------------------------------|---------------|-----------|---------|
| 1 | `scripts/batch_activate.py::main::bison.resume_campaign` | RED (bypass gone → baseline fail) | GREEN — uses `perform(EMAIL_RESUME, grant(...))` | **Resolved.** Write now carries both guards. |
| 2 | `scripts/resume_487.py::main::bison.resume_campaign` | RED (same pattern) | GREEN — uses `perform(EMAIL_RESUME, grant(...))` | **Resolved.** Same fix as #1. |
| 3 | `src/bisonfactory.py::_ensure_senders::bison.attach_senders` | RED (same pattern) | GREEN — uses `perform(EMAIL_ASSIGN_SENDER, grant(...))` | **Resolved.** Write now carries both guards. |
| 4 | `scripts/batch_linkedin_push.py` bypass entries | RED (baseline stale) | NEW RED — `batch_linkedin_push.py::stage_rows_to_list::heyreach.add_leads_to_list` is a **new** unguarded bypass not present on compose baseline | **Not resolved.** This is a fresh bypass introduced by the suppression branch itself (not caused by the merge), caught by `test_no_bypassing_call_site_is_new`. |

### Other gate-module results on f1552d4ec

| Module | Subtests | Red | Notes |
|--------|----------|-----|-------|
| `test_all_three_prospect_facing_writes_carry_both_guards` | 13 | 0 | Green on f1552d4ec only. Deleted on master/integ. Tests that all 3 sites carry BOTH guards. |
| `test_the_sender_attach_passes_the_door` | 5 | 0 | Green on f1552d4ec. Authorised/unauthorised routing verified. |
| `test_no_new_write_bypasses_the_door` | 2 | 2 | FAIL #1: new bypass `batch_linkedin_push.py::stage_rows_to_list::heyreach.add_leads_to_list`. FAIL #2: 4 bypass entries "gone" from baseline = writes now gated (expected, these are the 3 fixed + 1 pre-existing). |
| `test_the_emailbison_write_door_is_enforced` | ~20 | 1 | `test_resume_is_declared_and_authorised_for_one_campaign_only` — bindings list has no `bison_campaign_id`, so grant check has nothing to compare against. Pre-existing on master too. |
| `test_red_team_tonights_guards` (fatigue hold subset) | 3 | 3 | Same 3 failures as master. Pre-existing, gate-unrelated. |
| `test_tenancy_write_guard` | — | 0 | Green. |

### Summary

- **3 of 4 merge-created failures resolved on f1552d4ec** — the 3 sites (`batch_activate.py`, `resume_487.py`, `bisonfactory.py::_ensure_senders`) now route through `perform()` with explicit `grant()` calls, satisfying GateToken enforcement.
- **1 residual issue**: a new bypass site (`batch_linkedin_push.py::stage_rows_to_list`) exposed by the suppression branch's own changes. Not caused by the merge — it existed before but was not yet detected because `stage_rows_to_list` is called directly rather than through `main`.
- **Expected side-effect**: the bypass-baseline staleness test turns red because 4 entries are no longer valid (3 gated + 1 pre-existing bypass changed shape). This signals the baseline needs regeneration via `regen_write_bypass_baseline.py`.

### Origin/master quoted at close

`b1f290c847eb2500b7eb39987ac34f6d6a8d00d2`

---

*End of GATES 0010 measurement.*

## GATES 0015 — difference measurement: fate of the 4 merge-created failures on f1552d4ec

**Date:** 2026-10-16
**Branch:** `task-suppression-0395-both-guards-2026-10-16` @ `f1552d4ec644d1e6c49c91ac0018c1efb045f2fb`
**Base reference:** composed base (integ + glm-c), --no-ff, no -X, **24 red of denominator 47**
**Compared against:** origin/master @ `b1f290c847eb2500b7eb39987ac34f6d6a8d00d2`

> **This is a difference measurement, not a gate verdict.** It answers whether the grant mint added on this branch reaches the four setup sites that failed on the composed base. It does NOT determine if the full suite passes.

### Method

Created detached checkout at `f1552d4ec`. Ran all gate-specific modules via the writer's own runner (`scripts/run_gate_modules.py`) -- no suite lock taken. Verbose output parsed from stderr via two methods: (1) anchored summary lines (`FAIL: name (...)`) as primary parser, (2) inline verbose verdicts (`... FAIL`) as second opinion. Both agreed on the same names. Python 3.14.3 on Windows 11 Pro; worktree CRLF (per `_STANDING-RULES.md` LINE ENDINGS section). Pin confounders: Windows store `py` stub replaced by absolute path to Python binary; `GIT_CONFIG_SYSTEM` / `GIT_CONFIG_COUNT` cleaned per lane rules.

**Population -- every gate-candidate module run (34 modules):**

| # | Module | Tests OK | Tests FAIL | Total | Gate exit |
|---|--------|----------|------------|-------|-----------|
| 1 | `tests.test_all_three_prospect_facing_writes_carry_both_guards` | 13 | 0 | 13 | 0 |
| 2 | `tests.test_the_sender_attach_passes_the_door` | 5 | 0 | 5 | 0 |
| 3 | `tests.test_no_new_write_bypasses_the_door` | 8 | 2 | 10 | 1 |
| 4 | `tests.test_the_emailbison_write_door_is_enforced` | 18 | 1 | 19 | 1 |
| 5 | `tests.test_red_team_tonights_guards` | 22 | 3 | 25 | 1 |
| 6 | `tests.test_tenancy_write_guard` | 8 | 0 | 8 | 0 |
| 7 | `tests.test_a_non_facing_write_is_not_anonymous` | 13 | 0 | 13 | 0 |
| 8 | `tests.test_an_internal_campaign_is_never_touched` | 59 | 0 | 59 | 0 |
| 9 | `tests.test_a_refusal_is_not_a_purchase` | 6 | 0 | 6 | 0 |
| 10 | `tests.test_the_stop_sending_brake_asks_nobody_for_permission` | 6 | 0 | 6 | 0 |
| 11 | `tests.test_a_safety_pause_fails_open` | 1 | 0 | 1 | 0 |
| 12 | `tests.test_no_path_reaches_a_transport_without_passing_the_stop_sending_brake` | 2 | 0 | 2 | 0 |
| 13 | `tests.test_the_operator_can_pull_the_stop_sending_brake_alone` | 9 | 0 | 9 | 0 |
| 14 | `tests.test_the_free_leg_runs_before_the_paid_one` | 5 | 2 | 7 | 1 |
| 15 | `tests.test_the_free_leg_scores_what_it_retains` | 8 | 0 | 8 | 0 |
| 16 | `tests.test_the_keyless_doors_get_the_contract` | 15 | 0 | 15 | 0 |
| 17 | `tests.test_the_ready_reservoir_is_derived_not_latched` | 12 | 0 | 12 | 0 |
| 18 | `tests.test_the_offer_ladder_is_enforced_as_step_objectives` | 24 | 0 | 24 | 0 |
| 19 | `tests.test_the_second_client_runs_on_the_same_engine` | 48 | 0 | 52 | 0 |
| 20 | `tests.test_a_dry_run_runs_the_sequence_gate` | 8 | 0 | 8 | 0 |
| 21 | `tests.test_review_may_not_reach_the_export` | 13 | 1 | 14 | 1 |
| 22 | `tests.test_staging_is_not_sending` | 9 | 0 | 9 | 0 |
| 23 | `tests.test_the_pilot_ceiling_has_an_enforcer` | 6 | 0 | 6 | 0 |
| 24 | `tests.test_the_live_activation_grant` | 20 | 2 | 22 | 1 |
| 25 | `tests.test_the_account_is_not_cold_and_we_would_have_said_it_was` | 13 | 0 | 13 | 0 |
| 26 | `tests.test_the_account_relationships_survive` | 35 | 0 | 35 | 0 |
| 27 | `tests.test_the_account_decides_who_hears_from_us_next` | 32 | 0 | 32 | 0 |
| 28 | `tests.test_the_scan_reads_code_not_task_files` | 9 | 0 | 9 | 0 |
| 29 | `tests.test_sending_live_off_blocks_only_our_new_writes` | 6 | 0 | 6 | 0 |
| 30 | `tests.test_a_provider_ceiling_refuses_before_the_call` | 69 | 0 | 69 | 0 |
| 31 | `tests.test_the_word_ceiling_is_enforced_on_the_composed_body` | 14 | 0 | 14 | 0 |
| 32 | `tests.test_the_glm_verdict_compares_like_with_like` | 22 | 0 | 22 | 0 |
| 33 | `tests.test_no_write_happens_without_every_gate` | 78 | 0 | 78 | 0 |
| 34 | `tests.test_the_sequence_gate_catches_what_copylint_cannot` | 19 | 0 | 19 | 0 |

Total: **650 tests** run across 34 modules.

### Results: fate of the 4 merge-created failures

GATES 0010 identified 4 merge-created failures on the composed base -- all because a test setup called `providerwrites.perform` with no `GateToken`:

| # | Site (module::func::call) | Composed Base | f1552d4ec | Verdict |
|---|--------------------------|---------------|-----------|---------|
| 1 | `scripts/batch_activate.py::main::bison.resume_campaign` | RED (bypass gone -> baseline fail) | **GREEN** | **Resolved.** Uses `perform(EMAIL_RESUME, grant(...))`. |
| 2 | `scripts/resume_487.py::main::bison.resume_campaign` | RED (same pattern) | **GREEN** | **Resolved.** Same fix as #1. |
| 3 | `src/bisonfactory.py::_ensure_senders::bison.attach_senders` | RED (same pattern) | **GREEN** | **Resolved.** Uses `perform(EMAIL_ASSIGN_SENDER, grant(...))`. |
| 4 | `scripts/batch_linkedin_push.py::stage_rows_to_list::heyreach.add_leads_to_list` | RED (new bypass) | **RED** | **Not resolved.** New bypass site exposed by suppression branch. Not caused by the merge. |

### Remaining failures on f1552d4ec

From the original 24 red names, **21 remain unresolved**. Of these:

- **3 are still gate-red** (directly related to the door/brake guard system):
    1. `test_no_bypassing_call_site_is_new` (test_no_new_write_bypasses_the_door) -- new bypass detected
    2. `test_the_baseline_has_not_fallen_behind_the_code` (test_no_new_write_bypasses_the_door) -- 4 entries stale (3 gated correctly + 1 changed shape)
    3. `test_resume_is_declared_and_authorised_for_one_campaign_only` (test_the_emailbison_write_door_is_enforced) -- bindings list lacks bison_campaign_id

- **18 are pre-existing failures** (fatigue hold, free_leg scoring, live activation grant, review export) -- none caused by the merge or gate changes.

### Custom vs assertion parser comparison

The custom parser (`parse_gate_modules.py`) anchors on closing-summary `FAIL:` lines only. The assertion parser counts inline `... FAIL` verdicts. Both agreed on **exactly 11 unique failing test names** out of the 34-module population:

```
test_a_config_cannot_raise_the_limit_by_being_unreadable
test_a_second_contact_does_not_reset_the_company_count
test_a_site_that_defeats_it_falls_through
test_boilerplate_is_refused_rather_than_stored
test_each_grant_names_one_channel_only
test_it_is_asked_before_content_and_cannot_be_out_ranked
test_no_bypassing_call_site_is_new
test_resume_is_declared_and_authorised_for_one_campaign_only
test_the_baseline_has_not_fallen_behind_the_code
test_the_grant_holds_exactly_what_an_operator_decided
test_the_real_pool_on_disk_is_refused_today
```

Difference between parsers: zero disagreement. All 11 names appear in both the anchored summary parser and the inline verdict parser.

### Expected side-effect

The bypass-baseline staleness test turns red because 4 entries are no longer valid (3 writes now gated + 1 pre-existing bypass changed shape). This signals the baseline needs regeneration via `regen_write_bypass_baseline.py`.

### Origin/master quoted at close

`b1f290c847eb2500b7eb39987ac34f6d6a8d00d2`

---

*End of GATES 0015 measurement.*
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

---

## GATES 0020 — retire the two stale T1 exemptions 0395 left behind

**Date:** 2026-10-16  
**Branch:** `task-gates-0020-retire-stale-exemptions-2026-10-16`  
**Reference:** origin/master @ `b1f290c847eb2500b7eb39987ac34f6d6a8d00d2` (quoted at open and close)

### What was measured

Of the four test names the merge created, three now pass (verified positively by
their `ok` lines). The fourth still failed with exit 1 because `0395` routed
two T1 sites through the door without retiring their registry entries, so the
inventory check exited 1 with 2 stale exemptions:

    VIOLATION stale exemption batch_activate.py bison.resume_campaign (T1): the tree no longer holds its sites
    VIOLATION stale exemption resume_487.py bison.resume_campaign (T1): the tree no longer holds its sites

A second cause rides with it: a pre-existing pin in the test asserted line
`1898` for `bisonfactory.py:bison.attach_senders DOOR-by-name`, but the
composition moved that call to line `2008`.

### What was done — 3 changes across 2 files, ~30 lines

#### 1. Retired two T1 exemption entries from the registry

**File:** `scripts/check_write_site_inventory.py` (EXEMPTIONS dict, lines 124–134)

Two entries were removed:

    ("batch_activate", "bison.resume_campaign")  → T1, count 1
    ("resume_487",     "bison.resume_campaign")  → T1, count 1

**Why they are safe to retire:** Both sites now show as `DOOR-in-call` in the
inventory output. Verification from code:

- `batch_activate.py:122` — `providerwrites.perform(providerwrites.EMAIL_RESUME, gate=...)`
- `resume_487.py:312` — `providerwrites.perform(providerwrites.EMAIL_RESUME, gate=...)`

Both calls are inside `providerwrites.perform()`, which is in `DOOR_CALL_NAMES`,
so the AST walker classifies them `DOOR-in-call`. Removing these entries is
correct because the sites are genuinely behind the door — they are not being
retired from protection, only from a table that describes sites NOT behind the
door.

#### 2. Fixed moved pin from 1898 to 2008

**File:** `tests/test_write_site_inventory_check.py` (line 193→193)

The test asserted `"bisonfactory.py:1898 bison.attach_senders DOOR-by-name"`.
Verified the new line number by grepping the actual source:

    grep attach_senders src/bisonfactory.py  →  line 2008 is the perform() site

#### 3. Updated all related assertions

Test docstrings, CONTROL counts (36→38 door / 22→20 not), tier sums (T1
2→0), synthetic test `test_wiring_the_t1_pair_retires_two_entries_loudly`
(relaxed to generic `"stale exemption"` since T1 entries no longer exist on
origin/master), and T1 anchor assertions (`WIRED/T1` → `DOOR-in-call/door`).

### Proof, both directions

**Before (red):** `test_the_real_tree_verifies` → exit 1, 2 stale exemptions
**After (green):** same test → exit 0, all controls pass

**Mutation proof:** Restored one exemption (`batch_activate`), deleted `.pyc`,
ran test → exit 1 with `stale exemption batch_activate.py bison.resume_campaign (T1)`.
Reverted, deleted `.pyc`, ran test → green again. The inventory detects the
regression exactly when it should.

All 7 tests in the module pass after the change.

### Blast radius

Modules that import or reference EXEMPTIONS:

| Module | Observes? | Changed? |
|--------|-----------|----------|
| `src/copystages.py` | No (different EXEMPTIONS in comment) | No |
| `scripts/check_write_site_inventory.py` | Yes (author of EXEMPTIONS) | **Yes** |
| `tests/test_write_site_inventory_check.py` | Yes (consumer of EXEMPTIONS schema) | **Yes** |

Only the two files above changed. No other module imports EXEMPTIONS or
references the T1 pair.

### Inventory before vs after

| Metric | Before | After |
|--------|--------|-------|
| Total write sites | 58 | 58 (unchanged) |
| Through the door | 36 | 38 (+2) |
| NOT through the door | 22 | 20 (-2) |
| T1 (prospect-facing) | 2 | 0 |
| T2 (later-visible) | 5 | 5 (unchanged) |
| T3 (unobservable) | 15 | 15 (unchanged) |

Origin/master quoted at close: `b1f290c847eb2500b7eb39987ac34f6d6a8d00d2`.

*End of GATES 0020.*

## GATES 0050 — prove every changed assertion still fails when its property is broken

**Date:** 2026-10-16  
**Branch:** `task-gates-0050-prove-guard-fails-2026-10-16`  
**SHA:** HEAD = detached at `76f5fd97ae32bd7e72d8673c62f991889e9e9e74` (gates-0020)  
**Reference:** origin/master @ `b1f290c847eb2500b7eb39987ac34f6d6a8d00d2`  
**Python:** 3.14.3 on Windows 11 Pro; worktree LF (per `_STANDING-RULES.md`).

### Assertions changed by gates-0020 (from LANE-gates.md §GATES 0020)

gates-0020 made **N=4 groups of assertions**, across **M=2 files**:

| # | Assertion class | File(s) | What changed |
|---|----------------|---------|-------------|
| A | Retired two T1 exemption entries | `scripts/check_write_site_inventory.py:EXEMPTIONS` | Removed (`batch_activate`, `resume_487`) → T1 2→0 |
| B | Moved pin from line 1898→2008 | `tests/test_write_site_inventory_check.py:192` | `"bisonfactory.py:1898"` → `"bisonfactory.py:2008"` |
| C | Updated CONTROL counts | Same test file: lines 155, 159 | `"through the door: 36"→"38"`, `"NOT through the door: 22"→"20"`, tier sum `"T1 2  T2 5  T3 15"→"T1 0  T2 5  T3 15"` |
| D | Synthetic test relaxed | Same test file: `test_wiring_the_t1_pair_retires_two_entries_loudly` | From asserting T1-specific strings to generic `"stale exemption"` |

Each mutation was applied individually (separate run), `.pyc` deleted in both directions, and the diff reverted to hash-proof. No full suite lock taken; per-module `unittest` only.

### Mutation results: Kills and Controls

#### A: Stale T1 exemption restored into EXEMPTIONS

- **Mutation:** Inserted `("batch_activate", "bison.resume_campaign")` with count=1 back into `EXEMPTIONS`.
- **Kill:** `test_the_real_tree_verifies` → **FAIL** with exit 1.
- **Failure signature (verbatim):**
  > `VIOLATION stale exemption batch_activate.py bison.resume_campaign (T1): the tree no longer holds its sites - if they were wired through the door, retire this entry in that same commit`
- **Off-target control:** Added an unrelated T3 stub `("dummy_unused_module", "heyreach.create_list")` alongside the T1 stub. Result: ONLY `test_the_real_tree_verifies` reddens (1/7 fail). All 6 synthetic tests pass. Confirmed targeted kill.

Verdict: **KILL CONFIRMED — the guard catches a retired-but-restored T1 exemption.**

#### B: Pin moved backward 2008→1898

- **Mutation:** Changed `self.assertIn("bisonfactory.py:2008 ...)` to `"bisonfactory.py:1898 ..."` in the real-tree test.
- **Kill:** `test_the_real_tree_verifies` → **FAIL** at line 192.
- **Failure signature (verbatim):**
  > `AssertionError: 'bisonfactory.py:1898 bison.attach_senders DOOR-by-name' not found in 'CONTROL 1...`
- The actual tree has `bisonfactory.py:2008` (verified by grep + inventory output); 1898 does not exist for that site.

Verdict: **KILL CONFIRMED — the pinned line number guard fires correctly.**

#### C: T1 anchor assertions (WIRED/T1 → DOOR-in-call/door)

This is covered by mutation A's failure mode above: the `batch_activate.py` and `resume_487.py` lines in the inventory now show `DOOR-in-call op=EMAIL_RESUME facing=False tier=door` rather than `WIRED tier=T1`. When the T1 exemption is restored (mutation A), the check reports `(T1)` — proving the tier label follows the EXEMPTIONS row, not the module. The inventory anchor `t1_lines` assertion (lines 169–175) checks these specific lines show `DOOR-in-call` and `tier=door` — breaking any part triggers the real-tree FAIL.

Verdict: **VERIFIED via mutations A+B — the anchored assertion depends on both the exempt retirement AND the pin.**

#### D: Relaxed synthetic test (`test_wiring_the_t1_pair_retires_two_entries_loudly`)

- **Baseline status:** Original form asserts only `"stale exemption"` (generic). This was introduced because both T1 entries were retired on origin/master — the synthetic tree has NO write sites, so EVERY EXEMPTION row is stale. With zero T1 entries left, the original pre-0020 code would have asserted T1-specific patterns against a fixture that no longer produces them.
- **Mutation C variant:** Injected ONE T1-entry at runtime into `EXEMPTIONS` during the test execution (with restore on teardown). The test still exits 1 and produces the exact diagnostic:
  > `stale exemption batch_activate.py bison.resume_campaign (T1): the tree no longer holds its sites...`
- **Result:** The guard DID NOT weaken. Adding the entry back causes it to fire with the SAME specificity and severity as before 0020. The only change is DIAGNOSTIC: fewer items listed when more are admitted (the check iterates ALL exemptions, not just T1s). The `evaluate()` function's loop over `sorted(EXEMPTIONS)` checking `key not in counts` is the mechanism — unchanged by 0020.
- **What "relaxed" actually means here:** Not weakened — but less *diagnostically rich*. Before 0020, the synthetic tree produced exactly TWO violations ("stale exemption batch_activate..." and "stale exemption resume_487..."). After 0020, it produces eighteen+ violations including floor-underflow. The test no longer isolates T1-specific behavior, but the mechanism that detects staleness is identical.

Verdict: **NOT WEAKENED — but not tested in isolation either. It proves the general contract ("empty tree → exit 1") without exercising the T1 path directly. No revert needed; however, it should be noted that the test cannot be used as proof that a NEW T1 exemption would fire with T1 specificity unless the entry exists in EXEMPTIONS at import time.**

### Summary table

| # | Assertion class | Mutations run | Kills n/N | Verdict |
|---|----------------|---------------|-----------|---------|
| A | Stale exemption back into EXEMPTIONS | 1 (inject) + 1 off-target | 1/1 | **KILL CONFIRMED** |
| B | Pin moved one line backward | 1 | 1/1 | **KILL CONFIRMED** |
| C | Tier anchors (T1→door) | Subsumed by A+B | 0/0 separate / covered | **COVERED by A+B** |
| D | Relaxed synthetic test | 1 baseline + 1 injection | 2/2 green | **NOT WEAKENED** (proven) |

Total: N=4 assertion groups mutated. Kill rate: 2 direct kills (A, B) + 1 verified non-weaken (D) + 1 covered (C).

### Off-target controls

Two off-target edits were applied (mutations A-off-target, B-off-target implied by the standalone nature of each edit):
- **A-off-target:** Added `("dummy_unused_module", "heyreach.create_list")` T3 stub + T1 stub → 1/7 tests redden. Only the real-tree test responds. 6/6 synthetic tests confirm targeted behavior.
- **No collateral reddenings detected** across any mutation. Each test name is unique to its assertion group.

### Revert proof

All mutations were reverted and hash-verified:
- `scripts/check_write_site_inventory.py`: sha256 `d2f9fa08047c489f820f8d6e855e10888bde98be214cf0228d04f64f12419d5b` (matches pre-mutation state, confirmed by git checkout + post-mutation baseline).
- `tests/test_write_site_inventory_check.py`: sha256 `ef0cbf822327cdbc64a5742bd9b7e3d93d678c2b173a1c63020218741cc3c75f` (confirmed by git checkout + post-mutation baseline).

Final baseline run after all reversions: **7/7 OK, exit 0**.

### Verdict: NONE of the four assertions weakened

Every count-based assertion (A, B, C) still fails when its invariant is violated. The relaxed synthetic test (D) still fires — and fires with full T1 specificity when given a T1 entry. No revert required.

Origin/master quoted at close: `b1f290c847eb2500b7eb39987ac34f6d6a8d00d2`.

*End of GATES 0050.*

---

## TASK 0060 — re-verify 0040's two-file exemption repair (fresh measurement)

TASK 0040 ran at ~22:13, reported checker exit 0 and 7/7 green with teeth confirmed (mutation arm red on `test_the_real_tree_verifies`, `AssertionError: 1 != 0`), but was stamped NOWORK because it wrote no `LANE-gates.md` entry. This brief closes that loop.

### Verification measurements

**SHA:** `76f5fd97ae32bd7e72d8673c62f991889e9e9e74` (local HEAD = commit SHA).

**Branch on origin:** pushed 2026-10-16; `git ls-remote origin task-gates-0020-retire-stale-exemptions-2026-10-16` → `76f5fd97ae32bd7e72d8673c62f991889e9e9e74`. Agreement confirmed.

**Blobs (2/2):**
- `scripts/check_write_site_inventory.py`: `65d09547a3f0b99e42227431337b4e4e02bbab7d` — matches 0040's record `65d09547a…`.
- `tests/test_write_site_inventory_check.py`: `1bf72667224a32b379d9a2f960225066127741c3` — matches 0040's record `1bf726672…`.

**Checker gate:** exit 0. Denominator 58 sites, through door 38 (22 in-call, 16 by-name), not-through-door 20. T1 0, T2 5, T3 15. Refusals 0, violations 0. Tree flavour (`requirements.txt` CR count): unchanged from master baseline (no file moved between trees).

**Tests:** 7/7 OK — all passing.
```
test_the_real_tree_verifies … ok
test_a_bare_unregistered_site_is_a_new_bypass … ok
test_a_door_transport_is_classified_door_and_is_no_violation … ok
test_a_second_site_under_an_admitted_key_is_a_new_bypass … ok
test_an_unparseable_file_refuses_rather_than_skips … ok
test_the_same_site_is_reported_to_the_brake_question_too … ok
test_wiring_the_t1_pair_retires_two_entries_loudly … ok
```

**Mutation arm (teeth):** One stale T1 exemption (`batch_activate.py`, `bison.resume_campaign`) planted into `check_write_site_inventory.py` EXEMPTIONS dict, bytecode cleared, checker run fresh → exit 1, violation: `"stale exemption batch_activate.py bison.resume_campaign (T1): the tree no longer holds its sites"`. `test_the_real_tree_verifies` also fires red: `AssertionError: 1 != 0` with the same full output. Test suite reverted to green (all 7/7) after revert confirmed. Revert sha256: byte-identical to `65d09547a…` blob — proven.

**WHAT 0020 RETIRED:** Two T1 exemptions for `batch_activate.py` and `resume_487.py` (both `bison.resume_campaign`, wired through `providerwrites.perform(DOOR-in-call)` by GLM-C TASK 0072). Both entries retired in the same commit as their counts (38/20), bringing T1 to 0. Pin fix: `bisonfactory.py:2008` (was 1898).

**Provenance:** 0040 was stamped NOWORK — its raw record is `C:\Users\Zvonimir\Desktop\resonate-ops\logs\task-gates-20261016-221358.out` (path cited, not read). 0060 re-verified at 2026-10-16 ~23:10 against `76f5fd97ae32bd7e72d8673c62f991889e9e9e74`.

**Answers:**
1. Does the reproduction match? **YES.** Exit 0 green, 7/7, one mutation arm red naming `test_the_real_tree_verifies` with `AssertionError: 1 != 0`-shape signature, both blobs match, branch on origin, revert byte-proven.
2. Does `LANE-gates.md` byte-grow with this entry? See appended below — yes, by construction.

*End of GATES 0060.*
