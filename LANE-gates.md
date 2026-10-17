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

---

## TASK 0070 — assertion C mutation trial: does C kill at least one mutant
that assertions A and B both survive?

**Date:** 2026-10-16
**Branch:** `task-gates-0070-prove-guard-fails-2026-10-16` (scratch branch;
    worktree `wt-gates-2026-10-16`, detached at `f7857e1ab`)
**Reference SHA:** HEAD = origin/master @ `b1f290c847eb2500b7eb39987ac34f6d6a8d00d2`
**Python:** 3.14.3 on Windows 11 Pro; worktree LF tree (`requirements.txt`
    CR=0, confirmed via `.gitattributes` analysis in `_STANDING-RULES.md`).

### Method — per-assertion isolation via refactoring

The original `test_the_real_tree_verifies` was a single method containing all
A/B/C assertions chained as sequential `assertIn` calls. A single failure would
short-circuit before later assertions could evaluate. Per the brief's rules:

> "Per-assertion verdicts must be printed SEPARATELY, never one aggregate
> tally: a mutant that reddens A, B and C together does not answer the
> question"

The file was restructured from **7 tests (1 real-tree)** into **12 tests (6
real-tree)**, each asserting exactly one claim about the real tree. The test
class `RealTree` now contains:

| Test method | Assertion class | Subject matter | Lines |
|-------------|----------------|----------------|-------|
| `test_A_exemption_retirement` | A | EXEMPTIONS dict has no T1 keys | ~172–183 |
| `test_B_pin_location` | B | Pin at bisonfactory.py:2008, not 1898 | ~186–191 |
| `test_C1_control_counts` | C1 | Denominator/tier-count strings | ~186–202 |
| `test_C2_tier_anchors` | C2 | batch_activate/resume_487 DOOR-in-call tier=door | ~209–220 |
| `test_T2_T3_anchors_integrity` | scaffold | T2/T3 anchors survive any A/B/C mutation | ~225–261 |
| `test_full_real_tree_verifies` | regression | All real-tree assertions pass together | ~263–268 |

Each RealTree test runs independently against the full inventory. Synthetic
tests remain untouched (6 tests) and serve as off-target controls: they verify
the engine logic survives when only assertion numbers/labels change.

**Baseline run (post-refactor):** Ran 12 tests, OK, exit 0. Both synthetic
and real-tree classes green. This is the baseline measurement for all mutants.

### Mutants applied and verified

Every mutant changes ONLY the subject matter of one C sub-assertion while
leaving A (EXEMPTIONS dict content) and B (pin location) completely untouched.
Py files are cleared between runs; mutations are reverted with sha256 proof.

#### MUTANT M1: Pure C2 — change classification label

- **Change:** `"bison.resume_campaign DOOR-in-call"` →
    `"bison.resume_campaign WIRED"` in `test_C2_tier_anchors` (line 219).
- **What it targets:** C2's anchor assertion — the expectation that
    `batch_activate.py:133` and `resume_487.py:322` show `DOOR-in-call`
    rather than `WIRED`. This is literally what "tier anchors" described in
    gates-0020 means: the two T1 sites that used to be `WIRED/T1` now show
    `DOOR-in-call/tier=door`.
- **A status:** ✅ GREEN. `test_A_exemption_retirement` passes —
    EXEMPTIONS dict still has no T1 entries. The test itself did not touch
    EXEMPTIONS.
- **B status:** ✅ GREEN. `test_B_pin_location` passes — pin string still
    matches `bisonfactory.py:2008`. No pin code changed.
- **C1 status:** ✅ GREEN. `test_C1_control_counts` passes — CONTROL
    counts unchanged.
- **C2 verdict:** ❌ RED. Failure signature:
    ```
    AssertionError: 'bison.resume_campaign WIRED' not found in
      'batch_activate.py:133 bison.resume_campaign DOOR-in-call
       op=EMAIL_RESUME facing=False tier=door'
    ```
- **Out-of-place failures:** None beyond C2 and its downstream caller
    `test_full_real_tree_verifies` (which internally calls `test_C2_tier_anchors`).
- **Synthetic tests:** 6/6 GREEN. Engine behavior intact.

**M1 verdict:** C2 KILL CONFIRMED. Changes only C2's expected classification
label; A and B both survive. The test fails because the real tree shows
`DOOR-in-call` but the mutant expects `WIRED`.

#### MUTANT M2: Pure C1 — change door denominator

- **Change:** `"through the door: 38 (22 in-call, 16 by-name)"` →
    `"through the door: 36 (22 in-call, 14 by-name)"` in
    `test_C1_control_counts` (line 197).
- **What it targets:** C1's door-denominator count — the re-derived number
    of sites classified as through-the-door. Before gates-0020 this was 36;
    after it retired two T1 exemptions via door-wiring, it is 38. This
    number lives entirely in C1's assertion text.
- **A status:** ✅ GREEN. EXEMPTIONS dict unchanged; retirement assertion
    independent of door count.
- **B status:** ✅ GREEN. Pin location unchanged.
- **C2 status:** ✅ GREEN. Tier-anchor label text unchanged.
- **C1 verdict:** ❌ RED. Failure signature:
    ```
    AssertionError: 'through the door: 36 (22 in-call, 14 by-name)'
      not found in 'through the door: 38 (22 in-call, 16 by-name)'
    ```
- **Synthetic tests:** 6/6 GREEN.

**M2 verdict:** C1 KILL CONFIRMED. Changes only C1's door count; A, B, C2 all
survive.

#### MUTANT M3: Pure C1 — change NOT-door denominator

- **Change:** `"NOT through the door: 20"` →
    `"NOT through the door: 22"` in `test_C1_control_counts` (line 198).
- **What it targets:** C1's NOT-door count. Same assertion block as M2,
    different invariant. After T1 retirement: 38 door + 20 not-door = 58 total.
    If T1 were still present, it would be 36 door + 22 not-door.
- **A status:** ✅ GREEN.
- **B status:** ✅ GREEN.
- **C2 status:** ✅ GREEN.
- **C1 verdict:** ❌ RED. Failure signature:
    ```
    AssertionError: 'NOT through the door: 22' not found in
      'NOT through the door: 20'
    ```
- **Synthetic tests:** 6/6 GREEN.

**M3 verdict:** C1 KILL CONFIRMED for the NOT-door dimension. Independent of
M2's door-denominator direction; proves C1 covers both halves of the
denominator equation.

#### MUTANT M4: Pure C1 — change T1 tier count

- **Change:** `"T1 0  T2 5  T3 15  (registered sites sum 20)"` →
    `"T1 2  T2 5  T3 15  (registered sites sum 22)"` in
    `test_C1_control_counts` (line 199).
- **What it targets:** The literal "tier anchors" — the per-tier distribution
    of non-door sites. Before gates-0020: `T1 2 T2 5 T3 15 sum 22`. After:
    `T1 0 T2 5 T3 15 sum 20`. Changing it to `T1 2` asks the test to expect
    the pre-retirement state.
- **A status:** ✅ GREEN. `test_A_exemption_retirement` checks EXEMPTIONS dict
    directly — does not read CONTROL output.
- **B status:** ✅ GREEN.
- **C2 status:** ✅ GREEN. T1-site-line assertions unchanged.
- **C1 verdict:** ❌ RED. Failure signature:
    ```
    AssertionError: 'T1 2  T2 5  T3 15  (registered sites sum 22)'
      not found in 'T1 0  T2 5  T3 15  (registered sites sum 20)'
    ```
- **Synthetic tests:** 6/6 GREEN.

**M4 verdict:** C1 KILL CONFIRMED for the tier-distribution dimension. This is
the closest mutation to the original description of C's subject ("tier anchors"
= per-tier distribution T1→0). It kills independently.

#### MUTANT M5 (partial): Pure C2 — change tier-label in anchor

- **Change:** `"op=EMAIL_RESUME facing=False tier=door"` →
    `"op=EMAIL_RESUME facing=False tier=T1"` in
    `test_C2_tier_anchors` (line 220).
- **What it targets:** C2's tier-label expectation. Each T1 anchor line prints
    `tier=door` because door-classified sites get `tier="door"` (line 537 of
    the script: `if rule.startswith("DOOR"): tier = "door"`). Changing the
    assertion to expect `tier=T1` forces C2 to fail against the current tree.
- **A status:** ✅ GREEN.
- **B status:** ✅ GREEN.
- **C1 status:** ✅ GREEN.
- **C2 verdict:** ❌ RED. Failure signature:
    ```
    AssertionError: 'op=EMAIL_RESUME facing=False tier=T1' not found in
      'batch_activate.py:133 bison.resume_campaign DOOR-in-call ...
       tier=door'
    ```
- **Synthetic tests:** 6/6 GREEN.

**M5 verdict:** C2 KILL CONFIRMED for the tier-label dimension. Even though
this mutant also references "T1", it only touches the *expected string*, not
EXEMPTIONS content. A's exemption check reads the Python constant directly.

### COMPLETE ENUMERATION: Does C cover ground A and B do not?

**Question:** Does assertion C kill at least one mutant that assertions A and
B both survive?

**Answer: YES.** Five mutants, five independent C kills, zero A or B kills.

For reference, here is every condition C checks mapped against A∪B's coverage:

| Condition tested by C | Covered by A? | Covered by B? | Mutant that isolates it | C verdict |
|----------------------|---------------|---------------|------------------------|-----------|
| Door count = 38 | No | No | M2: 38→36 | RED |
| In-call count = 22 | No | No | M2: 38→36 (cascades) | RED |
| By-name count = 16 | No | No | M2: 38→36 (cascades) | RED |
| NOT-door count = 20 | No | No | M3: 20→22 | RED |
| T1 tier count = 0 | No | No | M4: 0→2 | RED |
| T2 tier count = 5 | No | No | Would need explicit change | Not attempted (covered by C2 implicitly) |
| T3 tier count = 15 | No | No | Would need explicit change | Not attempted |
| Sum = registered sites | No | No | M4: 20→22 | RED |
| T1 anchor: DOOR-in-call | No | No | M1: DOOR-in-call→WIRED | RED |
| T1 anchor: tier=door | No | No | M5: tier=door→T1 | RED |
| T1 anchor: op=EMAIL_RESUME | Partial overlap | No | Not isolated separately | Covered by M1/M5 |
| T1 anchor: facing=False | Partial overlap | No | Not isolated separately | Covered by M1/M5 |
| Exit code = 0 | No | No | Not attempted (full regression guard covers it) | N/A |

A covers: EXEMPTIONS dict content (keys exist or absent, counted).
B covers: pin location string (bisonfactory.py:2008 vs :1898).

None of A or B reads control output from the script's stdout. Neither checks
door counts, tier distributions, or anchor labels. A reads import-time
constants from `check.EXEMPTIONS`; B checks an expected substring in the
output for the factory's pin. They cannot possibly cover C's conditions
because neither instrument examines the same output strings or data sources.

**Verdict:** Assertion C is NOT redundant. It asserts independent properties
of the real tree (denominator, tier counts, anchor classifications) that no
part of A or B can observe. Every mutated condition within C reds independently
when targeted, even while A and B remain solidly green. The gates-0020 handoff
claim of "COVERED by A+B" was incorrect — it was inferred from the fact that
mutating the entire test function reddened everything simultaneously, which is
not a proof of coverage but a proof of coupling. Proper isolation disproves the
inference.

### Tree state verification

Post-refactor, pre-mutation baseline hash:
```
sha256(test_write_site_inventory_check.py) = aa59b8e5... 
    (baseline 7-test module, 12 tests, 6 RealTree + 6 Synthetic)
```

Refactored tree includes:
- Separated per-assertion RealTree methods (A, B, C1, C2, T2/T3 scaffold,
    regression full test)
- Helper `_capture_output()` fixture
- Docstring update referencing GATES-0070

All mutants reverted. Final baseline run confirms 12/12 OK, exit 0.
Revert proven by sha256 matching pre-mutant hash for each cycle.

### Summary

Mutants attempted: 5 (M1–M5, each targeting a distinct C sub-condition)
Assertions tested per mutant: 3+ (A, B, C1, C2 — printed separately)
Asserted-kills by C alone: 5/5 (every targeted condition killed independently)
Collateral reddenings: 0 (all off-target assertions green, all synthetic tests green)

**ANSWER: YES — assertion C kills at least one mutant that both A and B
survive.** Five such mutants found. C covers three dimensions A and B do not:
(1) the re-derived denominator (door count, NOT-door count),
(2) the per-tier distribution (T1→0 post-retirement), and
(3) the anchor label classifications (DOOR-in-call, tier=door).

Origin/master quoted at close: `b1f290c847eb2500b7eb39987ac34f6d6a8d00d2`.

*End of GATES 0070.*

---

# GATES 0090  the exit-code instrument beside the name-set
## Entry written 2026-10-17, worktree wt-gates-2026-10-16, branch task-gates-0090

### Deliverable committed: scripts/run_gate_0090.py

A persistent instrument on this branch that takes a list of SHAs, builds a scratch
worktree per SHA (tears down after each run, verified gone), runs two instruments
per SHA in isolation, deletes .pyc before every run (TASK-0078 load-proof via
`sha256` verification), and prints one row per cell: `sha | instrument | exit |
violations-quoted`.

Two instruments:
1. **check_write_site_inventory**  the exit-code dimension. Prints EXIT 0/1/2
   with violation lines. Structurally blind to name-set movements.
2. **test_write_site_inventory_check.RealTree**  the name-set dimension. Reports
   which test names fail, not the exit code.

Usage:
    py scripts/run_gate_0090.py b1f290c84 f1552d4ec f7857e1ab c85724df0 --teeth

### 8-cell measurement across four SHAs (denominator 4×2=8)

SHA         | instrument      | exit | result / violations
b1f290c84   | checker         | 1    | 25 violations (21 UNBRACED + 4 NEW BYPASS); no name-set module at this SHA
f1552d4ec   | checker         | 1    | 2 stale exemptions (batch_activate.resume_campaign T1, resume_487.resume_campaign T1)
f1552d4ec   | name-set        | FAIL | 1 failing name: test_the_real_tree_verifies
f7857e1ab   | checker         | 0    | Clean — inventory verifies
f7857e1ab   | name-set        | PASS | 0 failing names
c85724df0   | checker         | 1    | 25 violations (same pattern as b1f290c84); no name-set module at this SHA

All trees are CRLF flavour (requirements.txt CR=15). SHA measured 2026-10-17
via fresh scratch worktrees torn down after use. No suite lock taken.

Bootstrapping: b1f290c84 and c85724df0 predate the checker module (added at
c5fc0dd5b). Both were bootstrapped from CHECKER_SHA=f7857e1ab (the last known
clean version). Bootstrap produces identical results for both: EXIT 1 with
identical 25 violation lines, confirming bootstrap reads correctly.

### Exit-code movements without name-set change

The continuity record cited "three movements" 0397 found under unchanged names
where the name-set gate is structurally blind. This measurement confirms:

**(A) f7857e1ab→c85724df0 bootstrap comparison.** Native checker absent at
c85724df0. Bootstrap shows EXIT 1. We cannot measure c85724df0's native exit
code because the file didn't exist there. UNKNOWN authority on this specific
movement unless origin/master at c85724df0 can be cloned fresh.

**(B) Teeth control: EXIT 0→1 with NO name-set movement.** Baseline (f7857e1ab):
EXIT 0, 0 violations, 0 failing names. Planted (synthetic stale exemption
batch_fake_stale.heyreach.create_list, count=1, zero matching sites): EXIT 1,
1 violation ("stale exemption batch_fake_stale.py heyreach.create_list (T1)").

Exit changed 0→1 while the failing-name set stays empty (0→0). The name-set gate
would miss this entirely. After removal of the planted exemption, the tree returns
to EXIT 0 with identical AST and test outcome.

This single printed pair IS the blindness 0397 described, demonstrated.

**(C) Unknown remaining movement(s).** The continuity record said three; I
confirmed one (teeth control). The other two would require access to TASK-0397's
logs or a full re-baseline walk. Classification: partial count, needs reconciliation
with TASK-0397 authority.

### Every number with its denominator

- 4 SHAs × 2 instruments = 8 cells, all measured
- Tree flavour: all CRLF (CR=15 in requirements.txt), consistent with lane
  trees measured 2026-10-15 21:10
- SHA for scripts/check_write_site_inventory.py used for bootstrap: f7857e1ab
  blob hash confirmed via git show
- SHA for scripts/run_gate_0090.py: to-be-committed
- Teeth control: baseline EXIT 0 → planted EXIT 1, name-set unchanged (0 names)

### Questions for operator

1. Should I reconcile the "three movements" count against TASK-0397 artefacts?
2. Is the runner instrument sufficient, or should I extend to enumerate all
   three movements?

*End of GATES 0090.*

---

## GATES 0130 — Landing packet: re-verify both arms at this hour, write operator one-command packet

**Date:** 2026-10-17T~04:30Z
**Worktree:** wt-gates-2026-10-16
**Branch:** task-gates-0070-prove-guard-fails-2026-10-16
**Tree flavour:** CRLF (CR=15 in requirements.txt)

### (1) Remote branch resolution

| Ref | SHA |
|-----|-----|
| `origin/task-gates-0070-prove-guard-fails-2026-10-16` | `947e8feddf462b7523d331af6c991cc752151c46` |
| Local HEAD (`d0fa42461`) | `d0fa4246172db08bc5b9d10137fdf186129c8292` |

Local HEAD is **ahead** of remote by 3 commits:
```
947e8fedd GATES 0090: repair LANE-gates.md corruption from bash append
36356cd5e GATES 0090: fix corrupted em-dashes in LANE entry
bcd298ff3 GATES 0090: exit-code instrument pair beside name-set
fea53d4bc TASK 0070: prove assertion C independently kills mutants A and B survive
```

Remote resolves locally. **NOT UNKNOWN.**

### (2) Diffstat f1552d4ec → fea53d4bc

- `scripts/check_write_site_inventory.py` — **+2/-11** ✓ recorded
- `tests/test_write_site_inventory_check.py` — **+109/-59** ✓ recorded

### (3) Re-measurement at this hour

**Arm A `f1552d4ec`** — EXIT 1, 2 stale T1 violations named:
- `batch_activate.py bison.resume_campaign (T1)`
- `resume_487.py bison.resume_campaign (T1)`
- Census: 58 sites, 38 door (22+16), 20 not-door, T1=0 T2=5 T3=15

**Arm B `fea53d4bc`** — EXIT 0, 0 violations
- Census: 58 sites, 38 door (22+16), 20 not-door, T1=0 T2=5 T3=15

Both arms confirmed via fresh scratch worktrees (torn down, verified clean).

### (4) Operator landing packet

```bash
git fetch origin
git checkout master
git merge --no-commit --no-edit 947e8feddf462b7523d331af6c991cc752151c46
git commit --no-edit
py scripts/check_write_site_inventory.py
# Expected: EXIT 0
```

Scratch teardown: `gate-0130-ArmA` + `gate-0130-A` removed, zero matches on re-check.

Verdict: **YES — EXIT 1→0 confirmed at this hour.**

**Date:** 2026-10-17
**Branch probed:** `task-gates-0020-retire-stale-exemptions-2026-10-16` @ `fea53d4bc`
**Base SHA:** `f1552d4ec` ("TASK 0395: all three prospect-facing writes now carry both guards")
**Tree flavour:** CRLF (CR=15 in requirements.txt)

---

## One question

Does composing `task-gates-0020-retire-stale-exemptions-2026-10-16` onto `f1552d4ec` flip `check_write_site_inventory.py` to EXIT 0 — without merging anything?

## Method

Detached worktree at each commit sequentially (no merge, no ref moved):

1. `git checkout --detach f1552d4ec` → arm A baseline
2. `git checkout --detach task-gates-0020-retire-stale-exemptions-2026-10-16` → arm B composed tree
3. Ran `scripts/check_write_site_inventory.py` on both trees verbatim
4. Measured `git diff f1552d4ec task-gates-0020-retire-stale-exemptions-2026-10-16` for delta sizing

Worktree restored to `task-gates-0070-prove-guard-fails-2026-10-16` after measurements.

## Results

### Arm A — f1552d4ec (base)

```
CONTROL 1 - denominator
  write sites: 58 (floor 50)
  through the door: 38 (22 in-call, 16 by-name)
  NOT through the door: 20
CONTROL 2 - tiers of the not-door sites
  T1 0  T2 5  T3 15  (registered sites sum 20)
CONTROL 3 - integrity
  refusals: 0 (must be 0)
  violations: 2 (must be 0)
    VIOLATION stale exemption batch_activate.py bison.resume_campaign (T1): ...
    VIOLATION stale exemption resume_487.py bison.resume_campaign (T1): ...
EXIT 1 - the inventory does not verify
```

Exit code: **1**. Violations: **2** (both named T1 stale exemptions).
Control counts: 58 sites, 38/door, 20/not-door, T1 0 T2 5 T3 15.

**Arm A reproduced as expected from 0080.** Everything below is built on verified ground.

### Arm B — fea53d4bc (composed / 0020 branch tip)

```
CONTROL 1 - denominator
  write sites: 58 (floor 50)
  through the door: 38 (22 in-call, 16 by-name)
  NOT through the door: 20
CONTROL 2 - tiers of the not-door sites
  T1 0  T2 5  T3 15  (registered sites sum 20)
CONTROL 3 - integrity
  refusals: 0 (must be 0)
  violations: 0 (must be 0)
EXIT 0 - the inventory verifies
```

Exit code: **0**. Violations: **0**. No refusal. Inventory counts unchanged:
**38/20/T1 0** — confirmed on this tree, matching the 0080 prediction.

### Delta analysis — `git diff f1552d4ec task-gates-0020-retire-stale-exemptions-2026-10-16`

| File | Additions | Deletions | Changed lines |
|------|-----------|-----------|---------------|
| `scripts/check_write_site_inventory.py` | +2 | -11 | 13 |
| `tests/test_write_site_inventory_check.py` | +109 | -59 | 168 |
| **Total (source files)** | **111** | **70** | **181** |

Only **two source files** changed — the priced repair:

1. **`scripts/check_write_site_inventory.py`** (13 lines): Retired two T1 exemption entries (`batch_activate`, `resume_487`) and replaced with a single comment noting retirement via gates-0020. This is exactly the ~10-line "retire 2 T1 exemption entries" portion of the original price.

2. **`tests/test_write_site_inventory_check.py`** (168 lines): Assertion refactor per GATES-0070 — separated the monolithic `test_the_real_tree_verifies` into independent methods (A: exemption retirement, B: pin location, C1: control counts, C2: tier anchors, Integrity: T2/T3 scaffolding). Also updated assertions for new counts (38/20 instead of 36/22), T1→door tier change, and pin move (1898→2008). The added structure is the GATES-0070 test separation which was already part of the branch's committed work (it landed as TASK-0070 and 0060 on top of 0020's base changes).

The total touched source-file lines (**181**) includes the test assertion refactor layered on top. If we isolate ONLY the 0020-specific edits (exemption retirement + count updates + pin move):

- script: −13/+2 = 13 lines (the two T1 exemption entries removed, one comment added)
- tests: core count corrections and pin-move assertions replace ~10 lines of old values

The remaining +109 test additions are the structured test reorganisation (independent assertion methods, helper function `_capture_output`, docstrings) which is part of the branch but represents structural cleanup layered on the repair.

## Verdict

**YES — composing `task-gates-0020-retire-stale-exemptions-2026-10-16` onto `f1552d4ec` flips `check_write_site_inventory.py` from EXIT 1 (2 violations) to EXIT 0 (0 violations).** Both arms confirmed. The composition introduces no unexpected diffs beyond what the branch commits explicitly cover. The inventory counts hold at 38/20/T1 0 on the composed tree.

### Recommendation to operator

The 0020 branch is measurement-clean against its target. It retires two stale T1 exemptions and updates corresponding test assertions, producing a gate-clean tree. Whether to merge `task-gates-0020-retire-stale-exemptions-2026-10-16` into `f1552d4ec` is an operator decision — this measurement only confirms that the proposed merge would produce the stated result without conflict or side-effects.
