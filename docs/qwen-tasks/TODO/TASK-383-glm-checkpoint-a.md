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
