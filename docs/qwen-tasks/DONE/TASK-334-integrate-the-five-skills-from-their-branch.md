PRIORITY: P0
SIZE: M
DEPENDS:

# TASK-334 - integrate the five skills from their branch, by cherry-pick

**ABSORBED BY TASK-369, 2026-09-26.** The five skills are cherry-picked by
path inside TASK-369, which is the entrypoint that loads them - so one branch
owns `src/skills/*` and there is no second branch to reconcile. Do not dispatch
this task while TASK-369 is open. The contract below still governs: a skill
file nothing loads is not integrated.


TASK-319 is **complete on `origin/qwen-worker-4-r9`** and in DONE there. The
handoff says "WRITTEN, NOT STARTED" and is wrong - verified 2026-09-26, the
branch carries:

    src/skills/__init__.py
    src/skills/account_research.py
    src/skills/signal_verification.py
    src/skills/campaign_strategy.py
    src/skills/cold_email_writing.py
    src/skills/linkedin_writing.py
    tests/test_a_skill_is_loaded_by_the_stage_that_uses_it.py

**CHERRY-PICK, DO NOT MERGE.** Same rule as TASK-333.

## The rule that decides whether this is done

`docs/OPERATOR-DIRECTIVES-2026-09-26-PHASE1.md` section 6:

> A Markdown file describing best practice but never used by an agent is
> documentation, not an implemented skill.

and the spec: **a skill must be LOADED BY THE STAGE THAT USES IT.**

So the question this task must answer with evidence: **does anything call
`skills.load`?** The test file name claims a skill is loaded by the stage that
uses it - run it and read what it actually asserts. If it asserts only that the
loader works, say so plainly under FINDINGS. Do not wire the consumers here
(TASK-321 owns that), but do not report the skills as integrated if nothing
consumes them.

## Each skill must carry the spec's fields

purpose, inputs, required Second Brain sections, approved tools, procedure, good
examples, **bad examples**, validation criteria, output schema, failure handling,
escalation, tests. Check all twelve per skill and report any that are missing, by
skill name. Do not fabricate a missing field to make a check pass.

**Do not rewrite the prompts.** `src/copyprompts.py` and `src/copystages.py` are
Claude's; the skill wraps them.

## Acceptance

1. All seven files on your branch; report any deviation from the r9 versions.
2. Run it:

    py -3 -m unittest tests.test_a_skill_is_loaded_by_the_stage_that_uses_it -v

3. Report the registry and each skill's declared consumer:

    py -3 -c "import sys;sys.path.insert(0,'.');from src import skills;\
    r=skills.registry();\
    print(len(r),'skills');\
    [print(' ',k,'consumer=',getattr(v,'consumer',None)) for k,v in r.items()]"

   A skill whose consumer is None is DISCONNECTED - report it as such.
4. Exactly FIVE skills. Not ten. If the branch carries more, report it.
5. Full suite: wait for `work/suite_verdict.txt`, diff the failing-name SET.
6. Section 11 report with the REMOTE SHA verified.

## What this task may NOT do

- Do not merge the branch wholesale, do not add a sixth skill, do not rewrite the
  copy prompts, and do not mark a skill implemented because its file exists.
- Nothing sent, nothing activated.

## RESULT

**STATUS:** REVIEW

**ARTIFACT KIND:** finding (read-only audit; no code changes)

**FILES CHANGED:** None. This task audited files already on master (cherry-picked by TASK-369). No new files, no modifications.

**SCOPE DEVIATIONS:** None.

**ACCEPTANCE RESULTS:**

1. **All seven files on the branch:** VERIFIED. `git diff origin/qwen-worker-4-r9 -- src/skills/ tests/test_a_skill_is_loaded_by_the_stage_that_uses_it.py` is EMPTY — the local files match the r9 branch exactly. Files:
   - `src/skills/__init__.py`
   - `src/skills/account_research.py`
   - `src/skills/signal_verification.py`
   - `src/skills/campaign_strategy.py`
   - `src/skills/cold_email_writing.py`
   - `src/skills/linkedin_writing.py`
   - `tests/test_a_skill_is_loaded_by_the_stage_that_uses_it.py`

2. **Test run:** 6 tests, ALL PASS.
   ```
   test_consumer_names_a_real_stage ... ok
   test_every_skill_has_a_consumer ... ok
   test_load_returns_a_skill_with_all_required_fields ... ok
   test_load_unknown_skill_raises ... ok
   test_registry_has_exactly_five_skills ... ok
   test_two_skills_share_stage_f ... ok
   Ran 6 tests in 0.008s — OK
   ```

3. **Registry and consumer declarations:**
   ```
   5 skills
     signal_verification   consumer= stage_a
     account_research      consumer= stage_b
     campaign_strategy     consumer= stage_e
     cold_email_writing    consumer= stage_f
     linkedin_writing      consumer= stage_f
   ```
   All five skills declare a non-None consumer. No skill is DISCONNECTED at the registry level.

4. **Exactly five skills:** CONFIRMED. Not ten.

5. **Full suite:** `work/suite_verdict.txt` does not exist. The suite was not run (takes ~865 seconds). No failing-name SET comparison possible.

6. **Section 11 report:**
   - REMOTE SHA verified: `900f8708` (commit "TASK-319: five skills as executable SOPs, each wrapping an existing prompt" on `origin/qwen-worker-4-r9`)
   - `git diff origin/qwen-worker-4-r9 -- src/skills/ tests/test_a_skill_is_loaded_by_the_stage_that_uses_it.py` is empty — zero deviation.

**FINDINGS:**

**F1 — THE SKILLS ARE NOT INTEGRATED. The contract is not met.**

The task's acceptance criterion is: "does anything call `skills.load`?" The answer is **NO.**

`grep -rn "skills" src/` across the entire `src/` directory (excluding `src/skills/` itself) returns ZERO matches. Specifically:
- `src/generate_campaign.py` — no import of `skills`, no call to `skills.load()`
- `src/copystages.py` — no import of `skills`, no call to `skills.load()`
- `src/copyprompts.py` — no import of `skills`
- No other module in `src/` references the skills package

The stages that the skills declare as consumers (`stage_a`, `stage_b`, `stage_e`, `stage_f`) do NOT load them. The stages call `copyprompts` and `copystages` directly, exactly as they did before the skills existed.

**The test asserts the wrong thing.** `test_a_skill_is_loaded_by_the_stage_that_uses_it.py` asserts that every skill DECLARES a consumer — it checks `skill.consumer` is non-empty. It does NOT assert that the named consumer actually loads the skill. The test name says "a skill is loaded by the stage that uses it" but the test body says "a skill names a stage." These are different claims.

**F2 — Each skill carries all 12 spec fields.** Checked per skill:

| Skill | purpose | inputs | secondbrain_sections | approved_tools | procedure | examples_good | examples_bad | validation | output_schema | failure_handling | escalation | consumer |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| signal_verification | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| account_research | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| campaign_strategy | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| cold_email_writing | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| linkedin_writing | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

All twelve fields present in every skill. The `tests` field is satisfied by the separate test file. No missing fields.

**F3 — The skills are structurally sound but operationally inert.** The `Skill` dataclass is well-designed. The registry refuses skills without a consumer. The loader works. But the entire `src/skills/` package is a library with no callers — documentation-shaped code that nothing executes.

**SUMMARY:** The five skill files are on master, match the r9 branch exactly, all tests pass, every skill has all 12 fields and declares a consumer. **But nothing in the production pipeline loads them.** The TASK-319 contract — "a skill file nothing loads is not integrated" — is NOT met. The skills are cherry-picked, registered, and tested; they are NOT integrated. Wiring the consumers is the work that remains (and is explicitly out of scope for this task — TASK-321 owns it).

**RISKS:**
- The test name is misleading: it asserts declaration, not consumption. A future auditor reading the test name will conclude the skills are wired when they are not.
- The skills may drift from the prompts they wrap (`copyprompts.EXTRACT_SYSTEM`, `copystages.STRATEGY_SYSTEM`, `copystages.WRITER_SYSTEM`) without anyone noticing, since no stage reads them.

**RECOMMENDED CLAUDE ACTION:**
1. Accept the audit finding: the skills are present but not integrated.
2. The wiring of skills into stages belongs to TASK-321 (or its successor).
3. Consider renaming the test to `test_every_skill_declares_a_consumer` so the test name matches what it actually asserts.

## CLOSING NOTE, Claude, 2026-09-26 evening

This task's own header says "ABSORBED BY TASK-369... do not dispatch while
TASK-369 is open." TASK-369 finished and merged earlier tonight, and an
automated sweep dispatched this anyway - `claim_task.py`'s readiness check
has no concept of an "ABSORBED BY" header, only file location and DEPENDS.

The worker's finding (F1: nothing in `src/` calls `skills.load()`, the test
asserts declaration not consumption) independently confirms exactly what
TASK-375 found and fixed the same evening (commit `bcdfccf4`,
`docs/qwen-tasks/DONE/TASK-375-...md`): `generate_campaign.py` now loads
all five skills via `skills.load()` and passes `.procedure` to the model,
proven by 6 sentinel tests with a guard-failure check. F2 (all 12 spec
fields present per skill) is kept as independent confirmation, still true.
The suggestion to rename the misleading test
(`test_a_skill_is_loaded_by_the_stage_that_uses_it` asserts declaration,
not loading) is filed to `docs/BACKLOG.md` rather than acted on now - a
rename with no behaviour change, not urgent.

No code merged from this task - everything it asked for is already on
master via TASK-369 + TASK-375. Closed as superseded.
