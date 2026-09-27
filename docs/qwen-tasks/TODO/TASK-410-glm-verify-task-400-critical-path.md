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

---

## CORRECTION BY CLAUDE, 2026-09-27 — VERIFY THE BRANCH, NOT MASTER

**The first run of this task produced a void verdict.** At 12:13 it reported
"TASK-400 still in TODO/, not yet in REVIEW - verification deferred per task
instruction". That was wrong: TASK-400 had been implemented and moved to REVIEW on
`qwen-worker-4-r9` at 09:38, in commit `34e25fdb`. The verdict was reached by
looking at **master**, where the task file still sat in TODO because nothing had
been merged. Do not repeat that.

**Where the work lives.** A task's implementation lives on a WORKER BRANCH until
Claude integrates it. Master showing a task in TODO tells you only that it has not
been merged. It tells you nothing about whether the work exists.

**How to find it.** Do not infer from master. Ask git:

    git for-each-ref --format='%(refname:short)' refs/heads refs/remotes/origin \
      | while read r; do
          git ls-tree -r --name-only "$r" -- docs/qwen-tasks \
            | grep 'TASK-400-' | sed "s|^|$r |"
        done

Then read the code on the branch whose copy is in REVIEW, and **name the head SHA
you verified in your verdict**. A verdict that does not name a SHA cannot be
checked and will be treated as NEEDS_EVIDENCE.

**TASK-400 has since been BLOCKED TWICE by Claude**, and the second rework is in
flight. So when you run:

1. Find the branch holding TASK-400 in RUNNING or REVIEW right now.
2. Verify against that branch's head SHA.
3. If the task is still RUNNING and incomplete, return NEEDS_EVIDENCE naming the
   SHA and what was missing. Do not return PASS or BLOCK on unfinished work, and
   do not report "not started" when a branch says otherwise.

**What counts as proof**, per the operator: not that a module exists, not that an
import exists, not that unit tests pass, not that a function is callable by hand.
Proof is that `src/generate.py` runs, the component executes on real input, the
output flows downstream, and **changing the input changes the downstream output**.

**What to check specifically**, the three defects the second BLOCK named:

- Is there any `isinstance(model, llm.ScriptedModel)` branch left in
  `_generate_via_campaign`? Its presence is a BLOCK regardless of its comment.
- Does `clients.ConfigError` still return instead of raising? That is a BLOCK.
- Does the EmailBison attach and activation path refuse a stamped artifact, at the
  real call site, the way `heyreachfactory.ensure_leads:1268` and
  `providers/heyreach.activate_campaign:1738` do? Absence is a BLOCK.
- Do all three mutation tests fail when their fallback is reintroduced? If any
  mutation leaves the suite green, that is a BLOCK on the tests themselves.
