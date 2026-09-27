PRIORITY: P0
SIZE: M
DEPENDS:

# TASK-410 — GLM first-pass verification: TASK-400 (src/generate.py becomes the real caller)

**Operator instruction, 2026-09-27: this is the critical path. Verify it as
soon as TASK-400 reaches REVIEW — do not wait for a status check to notice.**

Read `docs/GLM-REVIEW-PROTOCOL.md` yourself and follow it exactly (isolated
worktree, read-only, falsification over confirmation, eight dispositions).

## Target

TASK-400 (`docs/qwen-tasks/TODO/TASK-400-generate-py-becomes-the-real-caller.md`
for its full spec) — the fix for GLM Checkpoint A's three failing controls
(no single production entrypoint, Second Brain has no production consumer,
the five skills form a closed wiring loop). If TASK-400 is not yet in
REVIEW when you start, check its RUNNING/claim status and report that
instead of inventing a verdict.

## What GLM's pass must produce — reproduce all seven, don't trust the report

1. **One entrypoint.** Is `generate_campaign.py` now genuinely called from
   `src/generate.py`'s real path (or has `generate.py`'s body been replaced
   by it)? Grep it yourself; do not accept the worker's own grep.
2. **Second Brain has a real consumer**, reached through the path that
   `python -m src.generate --live` (or its test-mode equivalent) actually
   runs — reproduce the mutation test (change a verified fact, confirm the
   output changes) through THAT path, not `generate_campaign.generate()`
   called in isolation.
3. **Canonical research authority unchanged** (`rec["research"]`, still one
   store) — confirm no second store was introduced.
4. **Changing an approved fact changes the resulting artifact**, through
   the real entrypoint.
5. **No critical logic depends on gitignored `work/`** — re-verify, this is
   a large change.
6. **No closed wiring loop** — do the five skills now have an external
   consumer (a real send path), not just `generate_campaign.py`?
7. **No cross-account research leakage** — `packfacts.identity_of()`'s
   exact-identity join unweakened.

Also confirm: copylint, sequencegate and the Offer Engine's `NotApproved`
gate still run on whatever path results — this task connects a pipeline, it
must not have removed a safety gate to do it. And confirm TASK-364's known
BLOCKED state (see `docs/qwen-tasks/TODO/TASK-364-*` REWORK note) was not
quietly worked around instead of fixed — if TASK-400 routes through
`bisonfactory`/`heyreachfactory` unchanged, TASK-364's own gap (those
factories still build parallel payloads, not from `sequenceplan`) is a
SEPARATE, still-open problem this task does not have to fix, but must not
paper over either.

## Result

Use the protocol's own format and eight dispositions. State plainly: SAFE
TO MERGE or BLOCKED, with the exact reproduction for each control.
