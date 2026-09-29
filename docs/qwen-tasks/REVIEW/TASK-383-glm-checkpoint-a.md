PRIORITY: P0
SIZE: M
DEPENDS:

# TASK-383 — GLM CHECKPOINT A

**Operator instruction, 2026-09-26 evening.** Dispatch a fresh GLM checkpoint
per `docs/GLM-REVIEW-PROTOCOL.md` now that TASK-375 (entrypoint genuinely
loads its five skills) and TASK-376 (researchpack vs packfacts resolved,
`rec["research"]` confirmed the one canonical store) are both on
`origin/master`. **Read the protocol file yourself and follow it exactly** —
isolated worktree, read-only, Qwen driving the adapter, falsification over
confirmation, the eight dispositions. This task file only names the target
and the negative controls; it is not a substitute for the protocol.

## Setup

Isolated worktree from current `origin/master`. Read-only throughout — no
provider write, no campaign action, no write to any file this checkpoint
did not create for its own report.

## Negative controls — GLM must try to falsify each, not confirm it

1. **One version-controlled production entrypoint exists.** TASK-369 built
   `src/generate_campaign.py`; TASK-375 found it has no production caller
   (the real production path is `src/generate.py`, a different, older,
   record-centric architecture). State plainly which of these is actually
   version-controlled and reachable from a real invocation
   (`python -m src.generate --live`), and whether "one entrypoint" is
   currently true or aspirational.
2. **The Second Brain has a real consumer.** Trace it yourself — do not
   accept a prior session's grep. Name the file:line that reads Second Brain
   facts in a path that reaches a rendered message.
3. **Canonical research has exactly one authority.** TASK-376 claims
   `rec["research"]` is that one store and `researchpack` is demoted.
   Falsify it: find any code path, current or newly added since, that reads
   research from somewhere else and lets it reach a rendered message.
4. **Changing an approved fact changes the resulting artifact.** Reproduce
   this yourself end to end — change a Second Brain fact or a
   `rec["research"]` entry, regenerate, and show the artifact differs. A
   claim that a unit test does this is not the same as reproducing it against
   the real chain.
5. **No critical generation logic depends on gitignored `work/`.** Grep for
   it. `work/v2_run.py` was the first instance found; state whether any
   current, in-scope module still has this shape.
6. **No closed wiring loop with zero external consumer.** The five skills
   (TASK-375) now have a real internal caller (`generate_campaign.py`) but
   that module itself has no external caller (`src/generate.py` doesn't call
   it either). Is this a closed loop — skills wired into an entrypoint nobody
   invokes — or does something reach it? State it plainly.
7. **No cross-account research leakage in the reviewed path.** `packfacts`
   and `researchpack` both key by account/company identity somewhere — verify
   the join is exact identity, not a text filter, on the path that actually
   reaches a rendered message (`rec["research"]` → `packfacts.pack_for()` →
   `bisonfactory._copylint_batch()`).

## What GLM's pass must produce

Per the protocol's own eight dispositions, for each of the seven controls
above plus anything new GLM finds with file:line. State explicitly which
controls hold, which fail, and which are unverifiable from a read-only pass
(and why).

## What this task may NOT do

- No provider write, no campaign action, nothing sent or activated.
- Do not re-litigate TASK-375/376's own scope decisions (e.g. whether to
  delete `researchpack` outright) — that is an operator call already
  recorded. Verify what IS built, not argue what should have been built
  differently.

## RESULT BLOCK

**STATUS:** DONE
**ARTIFACT KIND:** Document (GLM review report)
**COMMIT SHA:** 9b3222ce
**START_MASTER_SHA:** 53dc50c8ebe158102052206712e18f229bb48a7b
**TESTS:** Read-only audit — no test run. Reproducible read-only commands provided in report.
**FILES CHANGED:**
- `docs/glm-reviews/TASK-383-glm-checkpoint-a.md` (new, 353 lines)

**FINDINGS:**

Seven negative controls investigated per `docs/GLM-REVIEW-PROTOCOL.md`:

| # | Control | Disposition |
|---|---------|-------------|
| 1 | One production entrypoint | FALSE POSITIVE — `python -m src.generate --live` → `main()` → `run()` → `generate_record()` → `_generate_via_campaign()` → `generate_campaign.generate()`. One entrypoint, fully wired. |
| 2 | Second Brain has a real consumer | HOLDS — `secondbrain.for_task()` → `_load_admitted_facts()` → `_format_br_context()` → `copystages.hypothesis_user()` → model prompt → rendered copy. File:line: `src/generate_campaign.py:460,631,634`. |
| 3 | Canonical research has one authority | HOLDS — `rec["research"]` is the sole store. `researchpack` module exists but has zero imports from outside itself. |
| 4 | Changing a fact changes the artifact | UNVERIFIED — data flow fully traced through two paths (research→sources→prompts, Second Brain→hypothesis→writer), but end-to-end reproduction requires a live model call. |
| 5 | No gitignored `work/` dependency | HOLDS — `work/v2_run.py` does not exist. Only a comment reference in `generate_campaign.py:14`. |
| 6 | No closed wiring loop | FALSE POSITIVE — the five skills are called from `generate_campaign.py:601,613,706,707`, which is called from `src/generate.py:2611`, reachable from CLI. |
| 7 | No cross-account research leakage | HOLDS — `packfacts.identity_of()` uses exact host/domain match (`same_site()`), not text filter. Historical 50-of-71 defect that motivated this is closed. |

Additional findings:
- `copystages.business_context_for()` is dead code (defined at `copystages.py:124`, no caller).
- `campaign_strategy` skill's `procedure` is not called through the skill loader (strategy decided by `_decide_strategy()` instead). Wiring inconsistency, not a safety defect.
- `researchpack` module has zero consumers — accepted deferred risk.

**RISKS:**
- NC4 is UNVERIFIED from read-only pass. A live reproduction is owed to confirm that changing a fact actually changes the artifact end-to-end.
- `campaign_strategy` skill claims `consumer="stage_e"` but stage_e does not load it through `skills.load()`. The skill registry check passes because the `consumer` field is non-empty, but the actual code path does not use the skill's `procedure`.

**RECOMMENDED CLAUDE ACTION:**
1. Accept the checkpoint report at `docs/glm-reviews/TASK-383-glm-checkpoint-a.md`.
2. NC4 live reproduction: run `python -m src.generate --live` with a modified fact and diff the artifact.
3. Consider cleaning up `copystages.business_context_for()` (dead code) and aligning `campaign_strategy` skill's consumer claim with the actual code path.
