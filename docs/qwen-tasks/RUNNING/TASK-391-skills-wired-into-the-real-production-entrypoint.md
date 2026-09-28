PRIORITY: P1
SIZE: M
DEPENDS:

# TASK-391 — skills consumed at runtime by the REAL production entrypoint

TASK-375 wired all five skills into `generate_campaign.py` — but TASK-375
and TASK-379 (GLM) both independently confirmed `generate_campaign.generate()`
has zero production callers. The actual production path is `src/generate.py`
(record-centric, `python -m src.generate --live`, its own
diagnose/hook/persona_angle/draft pipeline). **The skills are wired into a
pipeline nothing runs, not the pipeline that runs.**

## Trace first

1. Read `src/generate.py`'s stage functions (`diagnose`, `hook`,
   `persona_angle`, `draft`, and whatever else calls a model). Which raw
   prompt constants do they use, and do any already resemble one of the five
   skills' procedures?
2. Do NOT assume the five skills map cleanly onto `generate.py`'s stages —
   `generate_campaign.py`'s pipeline (ICP → extract → hypothesis → match →
   strategy → writer) may not be `generate.py`'s pipeline. Name the mismatch
   if there is one, honestly, rather than forcing a skill onto a stage it
   was not written for.

## Build only what the trace supports

Wire whichever skills genuinely correspond to a `generate.py` stage, the
same way TASK-375 did: `skills.load(name).procedure` replaces the raw
constant, proven by a sentinel-injection test showing the patched procedure
reaches the model through `generate.py`'s real call path — not a direct
call to the skill.

## Acceptance

1. Name, with file:line, each `generate.py` stage and whether a skill now
   feeds it, or why not (no corresponding skill exists).
2. Sentinel test per wired skill: patch procedure, run `generate.py`'s real
   entrypoint, prove the model saw the patch. Guard-failure: revert, confirm
   the test fails for the right reason, restore.
3. Full suite: wait for `work/suite_verdict.txt`, diff the failing-name SET.

## What this task may NOT do

- Do not change generate.py's stage logic or prompts, only which system
  prompt source each stage reads from.
- Nothing sent, nothing activated. Production freeze - generate.py --live
  is the real send path; this task runs it in dry/test mode only.
