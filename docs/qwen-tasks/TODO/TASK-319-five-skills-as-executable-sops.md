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
