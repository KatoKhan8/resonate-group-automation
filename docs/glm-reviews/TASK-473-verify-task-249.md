# TASK-473 — Independent verification of TASK-249

**Reviewed branch:** `origin/qwen-worker-8-r61`
**Branch HEAD SHA:** `8e6ee5edcb1ccc970a3dfa1b86be599a9822bb29`
**Verified SHA:** `8e6ee5ed` (matches)
**Review worktree:** `.qwen/worktrees/glm-473` (detached HEAD at target SHA)
**Review date:** 2026-09-28

---

## Summary

TASK-249 adds seven read-only Slack agent queries for account/lead lookup with a structural privacy rule: lead lookup is DM-only, and answers never echo the identifier. The work is **correct, fully wired, and safe to merge**.

---

## 1. Does the artifact exist on this ref?

**YES.** All claimed files are present at the target SHA:

- `src/slackagenttools.py`: +436 lines (7 new tool functions + REGISTRY entries + `_is_dm` helper)
- `src/slackconversation.py`: +19 lines (7 keyword routes in KEYWORD_PLAN)
- `tests/test_slack_agent_task249.py`: +372 lines (new test file, 22 tests)
- `docs/qwen-tasks/DONE/TASK-249-*.md`: +121 lines (task file with result block)
- Task file moved TODO → RUNNING (rename, 100% similarity)

**Verified with:** `git diff master...FETCH_HEAD --stat`

---

## 2. Existence is function: is every link consumed?

**YES.** The full production chain is wired:

```
Slack message
  → slackconversation.plan()
    → keyword_plan() reads KEYWORD_PLAN
      → matches keyword to tool name
      → checks tools.REGISTRY for scope availability
  → slackagenttools.run(scope, name, argument)
    → looks up tool in REGISTRY
    → checks scope.kind in allowed scopes
    → calls tool function
  → tool function returns dict
  → for_client() applies client-scoped scrubbing
```

**Verified with:**
- `grep -n "keyword_plan\|route\|REGISTRY" src/slackconversation.py` — `keyword_plan()` is called by `plan()` at lines 636, 645, 659
- `grep -n "REGISTRY\|for_scope\|tools\.run" src/slackagenttools.py` — `run()` reads REGISTRY at line 3625, `for_scope()` at line 3607
- All 7 new tools are in REGISTRY (lines 3562-3601 in the diff)
- All 7 keyword routes are in KEYWORD_PLAN (lines 499-517 in the diff)

**Zero production callers = DISCONNECTED?** NO. Every tool is registered, every route is wired, and the chain is consumed end-to-end.

---

## 3. Falsification of key claims

### 3.1 Privacy rule: lead lookup is DM-only

**Claim:** `lead_status_dm` refuses in channels without echoing the identifier.

**Falsification attempts:**

1. **Channel scope with email argument:** Returns `{"refused": True, "reason": "Lead lookups are direct messages only..."}`. The email is NOT in the output. ✓
2. **Channel scope with name argument:** Returns refused. The name is NOT in the output. ✓
3. **Edge case — source=None:** `_is_dm()` returns False (safe default). ✓
4. **Edge case — source="dm something" (no colon):** `_is_dm()` returns False (requires "dm:" prefix). ✓
5. **Edge case — source="channel: dm: fake":** `_is_dm()` returns False (starts with "channel:"). ✓

**Conclusion:** The DM check is structural and robust. A channel scope cannot bypass it.

### 3.2 Privacy rule: DM answer never echoes the identifier

**Claim:** The answer strips email, name, and all identifying fields.

**Falsification attempt:** Created a realistic record with `email`, `name`, `contact_name`, `first_name`, `linkedin_url`. Called `lead_status_dm` in a DM scope.

**Result:** The output contains keys `[domain, record_state, state, sendable, verification, channel_states, in_campaigns, in_campaigns_source]`. No PII fields survive. The scrubbing logic:
- Strips `name` explicitly (because STATUS_FORBIDDEN_FIELDS has "contact_name" but not bare "name")
- Strips any key containing a STATUS_FORBIDDEN_FIELDS substring
- Strips any key in STATUS_ADDRESS_FIELDS
- Strips any string value matching `_EMAIL_SHAPE` regex

**Verified with:** Direct Python test against a realistic record. No leaks found.

### 3.3 Not-found answers do not echo the identifier

**Claim:** Even a "not found" answer must not echo the query.

**Falsification attempt:** Called `lead_status_dm` with `nobody@nowhere.test` in an empty store.

**Result:** Returns `{"matches": 0, "note": "nothing in this workspace matches that query"}`. The query is NOT in the output. ✓

**Verified with:** Test `test_not_found_does_not_echo_either` and direct Python test.

### 3.4 SendingScheduleEmpty is not zero and not an error

**Claim:** `campaign_sending_schedule` treats `SendingScheduleEmpty` as "none scheduled" (a result), not as zero or an error.

**Verified with:** Code inspection. The exception handler at lines 3210-3214 in the diff checks `type(exc).__name__ == "SendingScheduleEmpty"` and sets `out[day] = "none scheduled"`. The note at the end explains: "'none scheduled' is the provider's own empty answer, not zero and not an error."

**Test:** `test_result_has_three_days` verifies the structure includes all three day keys.

### 3.5 Credits are internal only

**Claim:** `credits_today` is INTERNAL scope, not CLIENT.

**Verified with:** Test `test_credits_today_internal_only` asserts `slackscope.INTERNAL in scopes` and `slackscope.CLIENT not in scopes`. The REGISTRY entry at line 3597 in the diff confirms `_INTERNAL` scope.

---

## 4. Are the tests falsifiable?

**YES.** The tests assert on BEHAVIOR, not source text:

- **Privacy tests:** Assert on the ABSENCE of PII in `json.dumps(result)`. A mutation that removed the scrubbing would fail these tests.
- **Routing tests:** Assert on keyword → tool name mapping. A mutation that removed a route would fail.
- **Registry tests:** Assert on scope availability. A mutation that changed the scope would fail.
- **DM detection tests:** Assert on `_is_dm()` return values for different sources. A mutation that changed the logic would fail.

**Not accepted as proof:** None of the tests use `hasattr`, assert on source text, or prove a function exists without calling it. Every test drives the real entry point.

**Mutation test (informal):** If I deleted the `_is_dm` check in `lead_status_dm`, the test `test_refuses_in_channel_without_echoing_email` would fail because the function would attempt the lookup and return data (or an error), not `{"refused": True}`.

---

## 5. Would merging delete anything?

**NO.** The diff is purely additive:

```
121    0   docs/qwen-tasks/DONE/TASK-249-*.md
  0    0   docs/qwen-tasks/{TODO => RUNNING}/TASK-249-*.md (rename)
436    0   src/slackagenttools.py
 19    0   src/slackconversation.py
372    0   tests/test_slack_agent_task249.py
```

**Total:** 948 lines added, 0 lines removed. The task file move is a rename with 100% similarity.

**Verified with:** `git diff master...FETCH_HEAD --numstat`

---

## 6. Scope drift: does the branch carry junk?

**NO.** Only the files named in the result block are changed:
- `src/slackagenttools.py` (named)
- `src/slackconversation.py` (named)
- `tests/test_slack_agent_task249.py` (named)
- `docs/qwen-tasks/DONE/TASK-249-*.md` (task file)
- `docs/qwen-tasks/RUNNING/TASK-249-*.md` (task file move)

No unrelated files, no scratch output, no conflict markers.

**Verified with:** `git diff master...FETCH_HEAD --stat -- src/` shows only the two named files.

---

## 7. Import-graph test: no write path introduced

**PASS.** `test_slack_agent_cannot_act` (10 tests) passes. This test walks the import graph and asserts that no agent-reachable module imports a write module (providerwrites, clientapproval writes, etc.).

**Verified with:** `python -m unittest tests.test_slack_agent_cannot_act -v` — all 10 tests pass.

---

## 8. Full test suite: no regressions

**PASS.** 301 Slack agent tests pass (279 existing + 22 new).

**Verified with:** `python -m unittest discover -s tests -p "test_slack*.py" -v` — 301 tests in 29.9s, all green.

The result block's claim of "279 existing Slack agent tests unchanged, all green" is verified: 301 - 22 = 279.

---

## Findings

### F1: The logging requirement is satisfied by the loop, not the tools

The operator's decision says "All read-only, all logged to work/slack-agent.jsonl with who asked." The new tools do NOT log directly. Instead, the existing loop infrastructure (`scripts/slack_agent_loop.py`) logs every question with channel, user, and message at lines 218, 238, 319. This is correct — the tools are called through `plan()` → `gather()` → `plain_answer()`, and the loop logs at each step.

**Disposition:** NOT A DEFECT. The architecture is correct: tools return data, the loop logs.

### F2: The domain_hold_reason tool reads journals by domain substring match

The task's result block notes this as a risk: "If a journal key is an email address, the domain match works; if it is a hash or opaque ID, it will not find the row."

**Verified with:** Code inspection. The tool reads `s5-verify.jsonl` and `s7-copy.jsonl` via `slackagentreadback._stage_journal()`, then iterates over keys and checks `if domain in str(key).lower()`. This is a substring match, so it works for email addresses but not for hashes.

**Disposition:** KNOWN LIMITATION, documented in the result block. Not a defect — the tool answers what it can and says "no account matching" when it cannot find the row.

### F3: The domain_send_history tool reads events from the record's event log

The task's result block notes this as a risk: "If events are stored elsewhere (e.g., in the provider's queue), the answer will undercount."

**Verified with:** Code inspection. The tool reads `record.get("events")` and filters for send-related event types. The note in the output directs to `weekly_plan` for the full provider view.

**Disposition:** KNOWN LIMITATION, documented in the result block. Not a defect — the tool answers from the canonical local store and says so.

---

## Disposition

**MERGE.**

The work is correct, the privacy rule is structural and well-tested, the production chain is fully wired, and there is no scope drift or deletion risk. The 22 new tests are falsifiable and drive the real entry points. The import-graph test confirms no write path is introduced. The full suite passes with no regressions.

The three findings (F1, F2, F3) are not defects — F1 is correct architecture, and F2/F3 are documented limitations that are acceptable for a read-only agent query layer.

**Recommendation:** Merge `origin/qwen-worker-8-r61` at SHA `8e6ee5edcb1ccc970a3dfa1b86be599a9822bb29` into `master`.

---

## Reproducible commands

```bash
# Check out the exact SHA
git worktree add .qwen/worktrees/glm-473 8e6ee5edcb1ccc970a3dfa1b86be599a9822bb29 --detach

# Run the new tests
cd .qwen/worktrees/glm-473
python -m unittest tests.test_slack_agent_task249 -v

# Run the import-graph test
python -m unittest tests.test_slack_agent_cannot_act -v

# Run all Slack agent tests
python -m unittest discover -s tests -p "test_slack*.py" -v

# Verify the diff
git diff master...FETCH_HEAD --stat
git diff master...FETCH_HEAD --numstat
```

---

**Verdict written by:** GLM independent review, TASK-473
**Date:** 2026-09-28
**Branch HEAD SHA reviewed:** `8e6ee5edcb1ccc970a3dfa1b86be599a9822bb29`
