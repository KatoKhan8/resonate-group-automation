PRIORITY: P0
SIZE: S
DEPENDS:

# TASK-380 — GLM first-pass verification: TASK-346, the model spend ceiling

**Operator instruction, 2026-09-26 evening.** Independent GLM verification of
work Claude already merged, per `docs/GLM-REVIEW-PROTOCOL.md` — read it
yourself and follow its procedure, isolated-worktree rule, falsification
discipline and eight dispositions exactly. This file only names the target.

## Target

TASK-346, "model spend belongs to the client" — merged to `origin/master` at
`2fdb5568`. Files: `src/llm.py`, `src/providers/glm.py`,
`tests/test_model_spend_counts_against_the_client.py` (22 tests, claimed
green by the worker).

**Known open finding, not yours to re-discover — verify it independently
instead:** TASK-373 (docs/qwen-tasks/TODO/TASK-373-thread-the-client-into-
the-spend-gate.md) states that TASK-346 landed the ceiling MECHANISM
correctly, but that nothing calls `complete()` with a real `client`/`config` -
every call site Claude found (`src/campaignstrategy.py:114`,
`src/slackconversation.py:623,1623,1662`, `src/llm.py:1085`, several scripts)
passes neither, so every reservation lands on `"unattributed"`. **Falsify
this yourself**: grep every call site, confirm or refute that the mechanism
is reachable with a real client identity from any current production path.

## What GLM's pass must produce

1. Reproduce the ceiling-refusal claim: a second `complete()` call under an
   exceeded ceiling actually raises `BudgetExceeded` naming "PROVIDER
   CEILING" - run it, don't read the test and accept it.
2. State plainly whether TASK-373's "nothing supplies a real client" finding
   is CONFIRMED CURRENT, with the exact call sites you checked.
3. Check the narrowed `except Exception` and the named row for an unknown
   provider (TASK-346's own claimed fixes) - reproduce both directly.
4. Any NEW finding with file:line.

## Result

Use the protocol's own result format and dispositions - do not invent a new
vocabulary here.
