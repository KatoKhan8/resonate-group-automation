PRIORITY: P0
SIZE: M
DEPENDS:

# TASK-334 - integrate the five skills from their branch, by cherry-pick

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
