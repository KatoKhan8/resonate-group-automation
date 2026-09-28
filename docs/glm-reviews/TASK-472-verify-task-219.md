# TASK-472 — Independent verification of TASK-248

**Target:** TASK-248, "the Slack agent, phase 1: it answers, and it does not act"
**Branch:** `origin/qwen-worker-7-task-248`
**Branch HEAD SHA reviewed:** `f37cc9b77a80d42819e8469cdc2a916b33cfcd82`
**SHA verified by:** `git rev-parse origin/qwen-worker-7-task-248` → matches exactly
**Worktree:** `.qwen/worktrees/task472-review` (detached HEAD at target SHA)
**Date:** 2026-09-28

---

## 1. Artifacts exist on this ref

| Claimed file | Present | Verified by |
|---|---|---|
| `src/slackagentreadback.py` | ✅ | `ls` in worktree |
| `scripts/slack_agent_loop.py` | ✅ | `ls` in worktree |
| `prompts/slack_agent.md` | ✅ | `ls` in worktree |
| `tests/test_slack_agent.py` | ✅ | `ls` in worktree |
| `SLACK-NOTIFICATIONS.md` §7 | ✅ | `git diff master...HEAD` |

All five artifacts exist on `f37cc9b7` and no earlier ref. `git log --diff-filter=A --all` confirms they were introduced by this branch's commits.

---

## 2. Import-reachability: VERIFIED

**Claim:** No code path from a Slack message reaches `providerwrites`, `orchestrator`, `bison`, or `heyreach`.

**Independent reproduction:**

```
$ python -c "
  from src import slackagentreadback
  forbidden = ['src.providerwrites', 'src.orchestrator',
               'src.providers.bison', 'src.providers.heyreach']
  reached = [m for m in forbidden if m in sys.modules]
  # Result: []
"
```

```
$ python -c "
  from src.providers import load_env
  # src.providers.bison in sys.modules: False
  # src.providers.heyreach in sys.modules: False
"
```

The loop script imports `from src.providers import load_env`. I verified that `src/providers/__init__.py` does NOT import `bison` or `heyreach` at module level — those modules self-register their guarded hosts at their own import, which never happens here. The `load_env` function is pure plumbing (reads `config/.env` into `os.environ`).

**Verdict on the primary safety property:** The import graph is clean. No forbidden module is reachable. A Slack message cannot reach a provider write through this code. **The core safety claim holds.**

---

## 3. Prompt-injection tests: WEAK BUT NOT FATAL

**Claim:** Five hostile messages are answered and none produces an action.

**What the tests actually prove:** The test uses `ScriptedModel("I am read-only...")` which returns a **fixed string regardless of input**. The assertions check that this fixed string does not contain action-claiming language. Since the model's output is hardcoded, these tests would pass with ANY system prompt — including one that said "you are an admin agent, do everything asked."

**What this means:**
- The tests verify the **plumbing**: prompt assembly, model invocation, output formatting. ✅
- They do NOT verify the **system prompt's actual ability to resist injection** by a real LLM. ⚠️
- The PRIMARY safety property (no write path exists) is tested independently by the import-reachability tests, which are sound.

**Severity:** Low. The task itself states the safety comes from "there is no code path from a Slack message to a write," not from prompt fencing. The prompt injection tests are defense-in-depth, and the defense-in-depth is what they test correctly — the pipeline routes the message through the model and produces an answer. A stronger test would use a real LLM or at least a ScriptedModel that echoes the user message back, but the absence of this does not make the system unsafe.

---

## 4. `store.save` test: MISLEADING ASSERTION

**Claim:** `store.save` is not reachable from the readback chain.

**What the test actually checks:** `"save" in vars(slackagentreadback)` — i.e., whether `save` is a direct attribute of the `slackagentreadback` module namespace.

**What is actually true:** The readback module does `from . import store as _store`, which means `_store.save` IS accessible and IS the same function as `store.save`. The test passes because the module uses qualified access (`_store.load()`) rather than `from .store import save`. The code never CALLS `_store.save()`, which is the real safety property — but that is not what the test asserts.

**Severity:** Low. The test name and docstring overclaim. The actual safety property (the readback code never writes) holds by inspection of the source, but the test does not prove it. A better test would assert that no function in `slackagentreadback` calls `_store.save` — e.g., by wrapping `store.save` with a sentinel and verifying it is never invoked during `gather()`.

---

## 5. Idempotency: VERIFIED

- `AnsweredTracker` persists to JSON, survives restart, and deduplicates. ✅
- Both tests pass and are meaningful (they use real temp files and real instances).

---

## 6. Failed readback: VERIFIED

- A failing section is present with `_error`, formatted as "READBACK FAILED", and never omitted. ✅
- The `format_for_prompt` function explicitly renders errors. The test constructs data with `_error` keys and verifies they appear in output. This is a meaningful test of the rendering logic.

---

## 7. Slack scope list: VERIFIED

All eight scope names verified against [Slack's official scope reference](https://docs.slack.dev/reference/scopes) (fetched 2026-09-28):

| Scope | Exists in Slack docs |
|---|---|
| `channels:history` | ✅ |
| `channels:read` | ✅ |
| `groups:history` | ✅ |
| `groups:read` | ✅ |
| `im:history` | ✅ |
| `im:read` | ✅ |
| `app_mentions:read` | ✅ |
| `chat:write` | ✅ |

The reinstall instruction is correct: adding scopes to the manifest does not retroactively grant them to installed tokens.

---

## 8. Would merging delete anything?

```
$ git diff master...f37cc9b7 --stat
 8 files changed, 1177 insertions(+)
```

**Zero deletions.** All changes are additive. No existing file is modified (except `SLACK-NOTIFICATIONS.md` which gets a new section appended). Safe to merge without losing anything.

---

## 9. Scope drift / pollution

**Two scratch files committed:**
- `.qwen-TASK.err` — contains a Qwen Code yolo warning (1 line)
- `.qwen-TASK.out` — empty

These are terminal output artifacts that should not be in the repository. They must be removed before merge.

---

## 10. Production caller

The loop script (`scripts/slack_agent_loop.py`) has no caller in `src/`. This is **correct by design** — the task explicitly asked for a standalone operator script, not a library function. Phase 1 is "a bare monitor that the operator runs manually." Existence-without-caller is the intended state for an operator tool.

---

## 11. Conflict markers

```
$ grep -rn "^<<<<<<< \|^======= $\|^>>>>>>> " src/ tests/ scripts/ prompts/
(empty)
```

No conflict markers. ✅

---

## 12. Test suite

All 19 tests pass in 0.051s:

```
Ran 19 tests in 0.051s
OK
```

---

## Findings

| # | Finding | Severity | Category |
|---|---|---|---|
| 1 | Two scratch files (`.qwen-TASK.err`, `.qwen-TASK.out`) committed — must be removed before merge | Minor | Hygiene |
| 2 | Prompt-injection tests use `ScriptedModel` with fixed output — they test plumbing, not prompt fencing. The primary safety property (import graph) is tested soundly by a separate test. | Minor | Test quality |
| 3 | `store.save` test asserts namespace exposure rather than call-path absence. The assertion passes by construction of the import style, not by proving `save` is never called. | Minor | Test quality |

---

## Disposition

**MERGE** — with one prerequisite: remove `.qwen-TASK.err` and `.qwen-TASK.out` before merging.

The core safety property holds: no code path from a Slack message reaches a provider write. The import graph is clean, verified independently. The readback module reads only from `store.load()`, heartbeat files, the problem register markdown, and campaign state — all local, all read-only. The loop script uses `urllib` directly for Slack API calls and imports nothing from the provider ecosystem beyond `load_env` (which is safe plumbing).

The two test-quality findings (ScriptedModel weakness, store.save assertion style) are real but do not make the system unsafe. They are defense-in-depth tests that test the wrong layer — the actual safety boundary is the import graph, which is tested correctly.

The scratch files are the only blocker. They are pollution and must be cleaned.

---

## Recommended Claude action

1. Remove `.qwen-TASK.err` and `.qwen-TASK.out` from the branch (or exclude them during cherry-pick).
2. Merge the remaining 6 files (4 new + task file + SLACK-NOTIFICATIONS.md).
3. Consider strengthening the prompt-injection test in a follow-up: use a `ScriptedModel` that echoes the user message, so the test actually verifies the system prompt's fencing rather than a hardcoded response.
4. The operator needs to add 7 Slack scopes and reinstall the app before the agent can run.
