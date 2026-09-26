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
