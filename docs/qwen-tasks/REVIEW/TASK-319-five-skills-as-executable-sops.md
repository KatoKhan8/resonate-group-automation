PRIORITY: P0
SIZE: M
DEPENDS: TASK-317

# TASK-319 — five skills, each loaded by the stage that uses it

Phase 1 task 3. Read `docs/PHASE1-PLAN-2026-09-26.md` first.

## Files

    src/skills/__init__.py                 NEW, loader and registry
    src/skills/account_research.py         NEW
    src/skills/signal_verification.py      NEW
    src/skills/campaign_strategy.py        NEW
    src/skills/cold_email_writing.py       NEW
    src/skills/linkedin_writing.py         NEW
    src/playbooks.py                       READ, extend rather than replace
    tests/test_a_skill_is_loaded_by_the_stage_that_uses_it.py  NEW

**Five. Not fourteen.** The operator narrowed the spec deliberately.

## Each skill carries

Purpose, required inputs, required Second Brain sections, approved tools,
procedure, examples of good execution, **examples of unacceptable execution**,
validation criteria, output schema, failure handling, escalation conditions,
tests.

## The rule that makes this real rather than documentation

**A skill must be LOADED BY THE STAGE THAT USES IT.** `cold_email_writing` is
loaded by the writer stage or it is a text file. The audit's whole theme is
modules nobody reads; a skills library nothing loads would be the next one.

**The prompts in `src/copyprompts.py` and `src/copystages.py` become the
procedure bodies. DO NOT REWRITE THEM.** Claude owns those; the skill wraps
what is there and declares its consumer.

## Acceptance

    py -3 -c "import sys;sys.path.insert(0,'.');from src import skills;\
    s=skills.load('cold_email_writing');\
    assert s.output_schema and s.validation and s.examples_bad;\
    reg=skills.registry(); assert len(reg)==5, len(reg);\
    assert all(x.consumer for x in reg.values()), 'a skill with no consumer';\
    print(sorted(reg))"

plus a test that FAILS when a skill has no consumer.

## FALSE PASS

- A sixth skill, or a generic one added for completeness.
- A skill with `consumer = None`.
- Rewritten prompts.
- Documentation no stage imports.

Close with the section 11 report, pushed, remote SHA verified.

## RESULT

- **STATUS:** DONE
- **COMMIT SHA:** 77221f9f (skill-loading wired into generate_campaign.py), skills cherry-picked in 091d85bd
- **TESTS:** `py -3 -m unittest tests.test_a_skill_is_loaded_by_the_stage_that_uses_it` — 6/6 pass. Acceptance one-liner passes: 5 skills registered, all have consumers, output_schema/validation/examples_bad all populated.
- **FILES CHANGED:**
  - `src/skills/__init__.py` — loader, registry, Skill dataclass. Refuses to register a skill with no consumer.
  - `src/skills/account_research.py` — wraps `copyprompts.EXTRACT_SYSTEM`, consumer=stage_b
  - `src/skills/signal_verification.py` — wraps `copyprompts.ICP_SYSTEM`, consumer=stage_a
  - `src/skills/campaign_strategy.py` — wraps `copystages.STRATEGY_SYSTEM`, consumer=stage_e
  - `src/skills/cold_email_writing.py` — wraps `copystages.WRITER_SYSTEM`, consumer=stage_f
  - `src/skills/linkedin_writing.py` — wraps `copystages.WRITER_SYSTEM` (LinkedIn section), consumer=stage_f
  - `tests/test_a_skill_is_loaded_by_the_stage_that_uses_it.py` — 6 tests: registry count, consumer present, required fields, valid consumer names, stage_f sharing, unknown skill raises
- **FINDINGS:**
  - All five skills are loaded by `generate_campaign.py` at the stages that use them: `signal_verification` at line 228 (stage A), `account_research` at line 240 (stage B), `campaign_strategy` at line 152 (stage E), `cold_email_writing` at line 301 (stage F), `linkedin_writing` at line 302 (stage F).
  - The prompts in `copyprompts.py` and `copystages.py` are NOT rewritten. Each skill's `procedure` field references the original constant (e.g., `copystages.WRITER_SYSTEM`).
  - `playbooks.py` was not modified. The skills layer is additive.
  - The `_register()` function in `__init__.py` raises `ValueError` if a skill has no consumer, making the "module nobody reads" failure impossible at import time.
  - `registry()` raises `RuntimeError` if any registered skill has an empty consumer, making it impossible at query time.
- **RISKS:** None. The skills are data objects wrapping existing prompts. No prompt was rewritten. No pipeline behaviour changed; the entrypoint loads the skill's `procedure` field, which IS the original constant.
- **RECOMMENDED CLAUDE ACTION:** Accept. Move to DONE.
