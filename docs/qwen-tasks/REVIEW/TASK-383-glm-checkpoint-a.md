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

---

## RESULT

**STATUS**: DONE
**COMMIT SHA**: (pending — review artifact committed on qwen-worker-2-r9)
**TESTS**: Read-only review; no test run. Static analysis only.
**FILES CHANGED**:
- `docs/glm-reviews/checkpoint-a-2bf7b8a57.md` (created — review artifact)
- `docs/qwen-tasks/RUNNING/TASK-383-glm-checkpoint-a.md` (RESULT block added)

**ARTIFACT TYPE**: Document (independent review report).

**FINDINGS**:

Seven negative controls reviewed. START_MASTER_SHA = END_MASTER_SHA =
`2bf7b8a57`. No master movement.

| # | Control | Disposition |
|---|---------|-------------|
| 1 | One entrypoint | SUPERSEDED — TASK-400 wired `generate.py` → `_generate_via_campaign()` → `generate_campaign.generate()`. Chain is complete from CLI to writer. |
| 2 | Second Brain consumer | PARTIALLY HOLDS — `generate_campaign.py:602,814,817` reads facts into hypothesis. Facts are internal-only by design. `copystages.business_context_for()` is DEAD CODE (zero callers). |
| 3 | One research authority | HOLDS — `rec["research"]` is canonical. `researchpack` has zero production imports. |
| 4 | Fact change → artifact change | UNVERIFIED from read-only pass. Test exists (`test_changing_an_approved_fact_changes_the_output.py`), chain is statically wired, but runtime confirmation requires execution. |
| 5 | No `work/` dependency | HOLDS — zero `open()`/`Path()` calls on `work/` in `src/`. All references are comments. |
| 6 | No closed loop | SUPERSEDED — TASK-400 closed the gap. Skills → `generate_campaign` → `generate.py` → CLI. |
| 7 | No cross-account leakage | HOLDS — `bisonfactory.py:594,605` joins by exact `record_id`. `packfacts.identity_of()` checks record_id + domain, not text. |

**New findings**:
1. `copystages.business_context_for()` at `src/copystages.py:124` is dead code — zero callers.
2. Dual `_format_br_context`: `copystages.py:109` (private, unused) and `generate_campaign.py:1523` (private, production path uses this one).

**RISKS**:
- Control 4 is UNVERIFIED from read-only. The test uses `_FactAwareModel` (mocked), not a real model. Runtime confirmation is owed.
- Dead code in `copystages.business_context_for` is low risk but should be cleaned up.

**RECOMMENDED CLAUDE ACTION**:
1. Review the artifact at `docs/glm-reviews/checkpoint-a-2bf7b8a57.md`.
2. Decide disposition for dead code (`copystages.business_context_for`).
3. Run `test_changing_an_approved_fact_changes_the_output` to confirm Control 4 at runtime.
4. No P0 findings. Controls 1 and 6 are SUPERSEDED by TASK-400. Controls 3, 5, 7 HOLD. Control 2 partially holds with dead code noted.
