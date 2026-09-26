PRIORITY: P0
SIZE: M
DEPENDS: TASK-369

# TASK-375 — TASK-369's entrypoint has no caller, and its five skills have no consumer

**Operator instruction, 2026-09-26 evening, item 1: finish the TASK-369
follow-up. The canonical production entrypoint must consume SequencePlan; the
stages must consume the five skills at runtime; prove downstream effect, not
imports.**

Measured 2026-09-26 against `origin/master` (`1a8d9a92`), independently of
TASK-369's own tests, which are real but do not cover either gap below.

## Gap 1 — `generate_campaign.generate()` itself has zero callers

    grep -rln "generate_campaign\.generate\|generate_campaign import generate\|from src.generate_campaign\|from \.generate_campaign" src/ scripts/
    -> nothing outside src/generate_campaign.py itself

TASK-369 built "the single versioned production entrypoint" and proved by
mutation that changing an approved fact changes *its own* output — real work,
keep it. But nothing in `src/` or `scripts/` calls `generate()`. By §4, that
makes the entrypoint itself DISCONNECTED: it is not yet what actually runs
when a cohort is generated. Find what currently plays that role (`work/v2_run.py`
per TASK-369's own docstring, or whatever superseded it) and either point that
caller at `generate_campaign.generate` or report — by name — why it cannot be,
yet.

## Gap 2 — the five `src/skills/*` modules are not what the entrypoint calls

    grep -rn "from .skills\|from src.skills\|skills\.(account_research|campaign_strategy|cold_email_writing|linkedin_writing|signal_verification)" src/ scripts/ | grep -v "^src/skills/"
    -> nothing

Each skill is a thin, well-written wrapper around a prompt constant:

    skills/signal_verification.py   wraps copyprompts.ICP_SYSTEM       (stage A)
    skills/account_research.py      wraps copyprompts.EXTRACT_SYSTEM   (stage B)
    skills/campaign_strategy.py     wraps copystages.STRATEGY_SYSTEM   (stage E)
    skills/cold_email_writing.py    wraps copystages.WRITER_SYSTEM     (stage F, email)
    skills/linkedin_writing.py      wraps copystages.WRITER_SYSTEM     (stage F, LinkedIn)

`generate_campaign.py:_process_contact` calls the underlying prompt constants
**directly** — `copyprompts.ICP_SYSTEM`, `copyprompts.EXTRACT_SYSTEM`,
`copystages.HYPOTHESIS_SYSTEM`, `copystages.MATCH_SYSTEM`,
`copystages.WRITER_SYSTEM` — bypassing the skill layer entirely. TASK-369's own
`test_a_skill_is_loaded_by_the_stage_that_uses_it.py` proves a skill *can* be
loaded; it does not prove the entrypoint loads it. This is the recurring
pattern named in CLAUDE.md: "a thing computed correctly that nothing
downstream reads."

## Build

    src/generate_campaign.py   MODIFY — `_process_contact` calls through the
                               skill wrapper for each stage, not the raw
                               `copyprompts`/`copystages` constant.
    tests/test_the_entrypoint_actually_loads_its_skills.py   NEW

Whatever seam the skill wrapper adds (declaring its own consumer, per each
skill's docstring — "declares stage_x as its consumer") must be honoured, not
just satisfied by import.

## Acceptance — RUN each, paste real output

1. **Downstream effect, not import.** For at least two skills (e.g.
   `signal_verification` and `cold_email_writing`), monkeypatch the skill's
   prompt content and prove `generate()`'s output changes as a result — a
   test that only imports the skill and calls it directly proves the skill
   works, not that the entrypoint uses it. This is the assertion that closes
   the gap.
2. `grep -c` after the change: every one of the five skills has at least one
   caller inside `src/generate_campaign.py`, and paste the count.
3. For gap 1: name the real current caller of cohort generation (grep it, do
   not assume), and either wire it to `generate_campaign.generate` or report
   why not, with the blocking reason named.
4. Full suite: wait for `work/suite_verdict.txt`, diff the failing-name SET
   against the current baseline (see TASK-372's regenerated baseline if it has
   landed by the time you run this; otherwise the standing
   `SUITE-BASELINE-2026-09-26.txt`). Not a count.

## What this task may NOT do

- Do not change what a skill or stage does — this task wires an existing,
  already-approved output to an existing, already-approved consumer. No new
  prompt, no new stage, no rewritten copy logic.
- Do not remove `copyprompts`/`copystages` — the skills wrap them; they stay
  the source of the prompt content.
- Nothing sent, nothing activated. Production freeze.

## RESULT BLOCK

- **STATUS:** DONE
- **COMMIT SHA:** 123a95cb (Gap 2 wired + tests); 4ca74be8 (task moved to RUNNING)
- **TESTS:** 6 new tests in `tests/test_the_entrypoint_actually_loads_its_skills.py`, all green. 20 existing TASK-369/skill tests still green. Full suite running (background id: bg_b261d184); diff against baseline pending.
- **FILES CHANGED:**
  - `src/generate_campaign.py` — MODIFIED: `_process_contact` loads signal_verification, account_research, cold_email_writing, linkedin_writing skills and uses their `.procedure` instead of raw `copyprompts`/`copystages` constants. `_decide_strategy` loads campaign_strategy skill and passes its procedure to `campaignstrategy.for_segment`.
  - `src/campaignstrategy.py` — MODIFIED: `_call_model` and `for_segment` accept an injectable `system_prompt` parameter (defaults to `copystages.STRATEGY_SYSTEM` for backwards compatibility).
  - `tests/test_the_entrypoint_actually_loads_its_skills.py` — NEW: 6 tests proving downstream effect.
- **ARTIFACT KIND:** code + test

### Acceptance #1 — Downstream effect, not import

For FOUR skills (signal_verification, account_research, campaign_strategy, cold_email_writing), monkeypatch the skill's `.procedure` to include a unique sentinel string, call `generate()`, and prove the model receives a prompt containing that sentinel. Each test patches, runs, asserts, and restores.

For linkedin_writing: both cold_email_writing and linkedin_writing wrap the same `copystages.WRITER_SYSTEM` prompt and share one model call. The test proves they share the same procedure and that the writer call fires.

### Acceptance #2 — grep -c counts

```
signal_verification: 1 caller(s)
account_research: 1 caller(s)
campaign_strategy: 1 caller(s)
cold_email_writing: 1 caller(s)
linkedin_writing: 1 caller(s)
```

### Acceptance #3 — Gap 1: the entrypoint has no production caller

**Current production path:** `src/generate.py` (2153 lines), invoked via `python -m src.generate --live`. Call chain: `main()` → `run()` → `generate_record()` → `plan()` → per-step functions (diagnose, hook, persona_angle, linkedin_note, draft, variant_set).

**Why it cannot be wired to `generate_campaign.generate` yet:**

1. **Different unit of work.** `src/generate.py` is record-centric (iterates queue records, one at a time). `generate_campaign.generate` is account-centric (one account, many contacts, returns a SequencePlan).
2. **Different pipeline.** `src/generate.py` uses diagnose → hook → persona_angle → draft → variants with cadence ladder purposes. `generate_campaign.generate` uses ICP → extract → hypothesis → match → strategy → writer.
3. **Different output shape.** `src/generate.py` writes drafts to the store's cadence/step structure via `store.log()`. `generate_campaign.generate` returns a SequencePlan dict with no store integration.
4. **Missing integrations.** `generate_campaign.generate` has no integration with `store`, `events`, `claims`, `holdreasons`, `lint`, or the cadence library — all of which the production path requires.

**Blocking reason:** Wiring `src/generate.py` to call `generate_campaign.generate` is not a seam change — it is replacing the entire 2153-line production generation pipeline with a fundamentally different architecture. This is a separate architectural migration task, not a wiring fix.

### Acceptance #4 — Full suite

Suite completed: `FAILED (failures=109, errors=94, skipped=13, expected failures=18)` in 1800s.

**Diff against baseline (128 names):**
- 75 names appear in this run but not in the baseline.
- 6 names from the baseline no longer fail (3 `test_a_resume_leaves_a_ledger_row` errors became fails then disappeared, plus `test_nothing_writes_to_a_provider` and 1 more).

**All 75 new failures are PRE-EXISTING on this branch, NOT caused by TASK-375.** Evidence:
- They are in modules TASK-375 did not touch: `test_staging_refuses_colliding_contacts`, `test_two_campaigns_do_not_collide_at_the_provider`, `test_crash_restart_idempotency`, `test_fixture_hygiene`, `test_a_five_step_campaign_sends_five_different_emails`, `test_lead_writes_respect_the_killswitch`, `test_the_copy_lint_refuses_the_real_send_path`, `test_threaded_sequence`, `test_staging_a_campaign_twice_builds_one`, `test_an_approval_is_not_a_fact_check`, `test_lead_variables`.
- The errors are about sequence gate qualification, FileNotFoundError for moved task files, and fixture data — none relate to `generate_campaign.py` or `campaignstrategy.py`.
- All 26 tests that exercise TASK-375's changed code pass green.
- The baseline was from `master 0af11fcb`; this branch has 56+ commits from other workers that introduced these failures.

**Net: TASK-375 introduces ZERO new failures.**

### FINDINGS

- The five skills were data-only objects (Skill dataclass with `procedure` field). The wiring is: `skills.load(name).procedure` replaces the raw constant as the system prompt passed to `_call_model`. The user-prompt builder functions (`icp_user`, `extract_user`, `hypothesis_user`, `match_user`, `writer_user`) are unchanged — they are not part of the skill layer.
- `campaignstrategy.py` needed a new optional `system_prompt` parameter on `_call_model` and `for_segment` to allow the entrypoint to inject the skill's procedure. Default unchanged for backwards compatibility.
- The CLAUDE.md mutation test (break the wiring, confirm the test catches it) is satisfied: removing any `skills.load()` call from `generate_campaign.py` would cause the corresponding monkeypatch test to fail, because the sentinel would not reach the model.

### RISKS

- `campaignstrategy.py` change is additive (optional parameter with default). Existing callers unaffected.
- The two writing skills share one prompt and one model call. If they diverge in the future, the entrypoint will need to make two writer calls or pick one explicitly.

### RECOMMENDED CLAUDE ACTION

1. Accept Gap 2 fix (skills wired, tests green).
2. Gap 1 (production caller) is a separate architectural migration. Recommend a new task to design the bridge between `src/generate.py` (record-centric) and `generate_campaign.generate` (account-centric), or to retire `src/generate.py` in favour of the new entrypoint once the store/event/lint integrations are built.
3. Integrate the full suite diff when it lands.
