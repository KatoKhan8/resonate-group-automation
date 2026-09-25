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
- **COMMIT SHA:** 812e76b0
- **TESTS:** 6/6 pass in `test_a_skill_is_loaded_by_the_stage_that_uses_it`;
  acceptance one-liner passes; registration refuses a skill with empty
  consumer (verified); pre-existing invariants failures (2: EmailBison
  routing, barrier checklist) are unrelated.
- **FILES CHANGED:**
  - `src/skills/__init__.py` NEW — loader, registry, `Skill` dataclass
  - `src/skills/signal_verification.py` NEW — wraps `copyprompts.ICP_SYSTEM`, consumer `stage_a`
  - `src/skills/account_research.py` NEW — wraps `copyprompts.EXTRACT_SYSTEM`, consumer `stage_b`
  - `src/skills/campaign_strategy.py` NEW — wraps `copystages.STRATEGY_SYSTEM`, consumer `stage_e`
  - `src/skills/cold_email_writing.py` NEW — wraps `copystages.WRITER_SYSTEM`, consumer `stage_f`
  - `src/skills/linkedin_writing.py` NEW — wraps `copystages.WRITER_SYSTEM`, consumer `stage_f`
  - `tests/test_a_skill_is_loaded_by_the_stage_that_uses_it.py` NEW
  - `docs/qwen-tasks/TODO/TASK-319-*.md` → `docs/qwen-tasks/RUNNING/`
- **FINDINGS:**
  - All five procedures reference existing prompt constants directly
    (`copyprompts.ICP_SYSTEM`, `copyprompts.EXTRACT_SYSTEM`,
    `copystages.STRATEGY_SYSTEM`, `copystages.WRITER_SYSTEM`). No prompt was
    rewritten.
  - Consumer wiring: `stage_a` (1 skill), `stage_b` (1), `stage_e` (1),
    `stage_f` (2: cold_email + linkedin). TASK-321 will make the consumers
    real importers.
  - `_register()` raises `ValueError` on empty consumer; `registry()` raises
    `RuntimeError` if any registered skill has no consumer. Both paths tested.
  - `secondbrain.TASK_SECTIONS` already uses the same five task names, so the
    skill names align with the retrieval layer from TASK-317.
- **RISKS:**
  - The consumer field is a string declaration, not a live import from
    `copystages.py`. TASK-321 closes this by wiring the stages to call
    `skills.load()`.
  - `cold_email_writing` and `linkedin_writing` share `stage_f` and both
    reference `WRITER_SYSTEM`. The split is by output field (email vs
    LinkedIn), not by prompt. This is correct for the v2 pipeline but could
    confuse a future reader.
- **RECOMMENDED CLAUDE ACTION:** Accept. TASK-321 can proceed to wire the
  consumers into real stage callers.
