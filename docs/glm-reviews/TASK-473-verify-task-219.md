# TASK-473 — GLM Independent Verification of TASK-249

## Review metadata

| Field | Value |
|-------|-------|
| Target task | TASK-249 |
| Target branch | origin/qwen-worker-8-r61 |
| Branch HEAD SHA | 8e6ee5edcb1ccc970a3dfa1b86be599a9822bb29 |
| SHA verified with | `git rev-parse origin/qwen-worker-8-r61` → matches |
| Review worktree | `.qwen/worktrees/task473-review` (detached at exact SHA) |
| Review date | 2026-09-28 |
| Reviewer | GLM (independent, read-only) |

## What TASK-249 claims

Seven new read-only Slack agent tools for account/lead queries with DM-only lead privacy:

1. `account_campaign_status` — is domain in a campaign
2. `lead_status_dm` — status of email/LinkedIn URL, DM-only, never echoes identifier
3. `domain_hold_reason` — why domain held (S5/S7 journals, ICP, MX)
4. `domain_send_history` — provider-confirmed sends only
5. `campaign_sending_schedule` — today/tomorrow/day_after
6. `replies_today` — notify store filtered to today
7. `credits_today` — spend ledger filtered to today, internal only

Result block claims: 22 new tests, all green. 279 existing tests unchanged. Import-graph test passes.

## Verification results

### 1. Do the artifacts exist on this ref?

**YES — verified.**

| File | Lines added | Verified |
|------|-------------|----------|
| `src/slackagenttools.py` | +436 | Functions at lines 2963-3340, REGISTRY entries at lines 3577-3601 |
| `src/slackconversation.py` | +19 | KEYWORD_PLAN entries at lines 499-517 |
| `tests/test_slack_agent_task249.py` | +372 | 22 test methods across 7 test classes |

`git log --diff-filter=A --all -- tests/test_slack_agent_task249.py` confirms the file was added in commit `c01b4bf3` on this branch.

### 2. Existence is not function — are there production callers?

**YES — fully wired. NOT DISCONNECTED.**

The production caller chain:

```
slackconversation.respond()
  → plan() (line 620+)
    → keyword_plan() (line 636, 645, 659) — no-model fallback
    → model plan — model picks from catalogue()
  → tools.run_all(scope, calls) (line 1586)
    → tools.run(scope, name, argument) (line 3625+)
      → REGISTRY[name] → (function, desc, scopes, help)
      → scope check → function(scope, argument)
```

- `keyword_plan()` consumes KEYWORD_PLAN entries: 7 new routes at lines 499-517
- `catalogue()` reads REGISTRY: 7 new entries at lines 3577-3601
- `run()` dispatches from REGISTRY: verified at line 3625
- `run_all()` is called at line 1586 in `respond()`

Every new tool has at least two independent consumers (keyword routing and REGISTRY dispatch). The model-driven path reaches them through `catalogue()` → model picks name → `run()` looks up REGISTRY.

### 3. Falsification of privacy claims

**Privacy rule is STRUCTURAL and VERIFIED.**

Mutation test performed: called `lead_status_dm` with a channel scope (`source="channel: internal"`):
- `_is_dm(scope)` → `False`
- Result: `{"refused": True, "reason": "Lead lookups are direct messages only..."}`
- Email address NOT in result output

The privacy implementation has three layers:
1. **Channel refusal**: `_is_dm(scope)` checks `scope.source.startswith("dm:")`. If False, returns refusal without any data lookup. The refusal string (`LEAD_LOOKUP_DM_ONLY`) is a constant that does not contain the identifier.
2. **Field scrubbing in DM**: Reuses `notify.STATUS_FORBIDDEN_FIELDS` (14 field name patterns), `notify.STATUS_ADDRESS_FIELDS` (6 exact field names), and `notify._EMAIL_SHAPE` (regex for email-shaped values). Plus explicit "name" stripping.
3. **Not-found safety**: Even the "not found" answer says "nothing in this workspace matches that query" — no identifier echoed.

If `_is_dm` check were removed: `test_refuses_in_channel_without_echoing_email` would fail (result.get("refused") would be falsy).
If field scrubbing were removed: `test_answers_in_dm_without_address` would fail (email would appear in output).
If keyword routes were removed: all 7 `KeywordRouting` tests would fail.

### 4. Are the tests falsifiable?

**YES — they test behavior, not existence.**

| Test class | What it tests | Falsifiable by |
|------------|---------------|----------------|
| `LeadLookupInChannelRefuses` | Refusal flag + no identifier in output | Removing `_is_dm` check or adding identifier to refusal |
| `LeadLookupInDMAnswers` | Answer + no address/name in output | Removing field scrubbing |
| `AccountAnswerCarriesDomain` | Domain present, contacts as counts only, no emails | Adding contact details to output |
| `CampaignSendingSchedule` | Structure (3 day keys), error on invalid id | Removing FORWARD_DAYS handling |
| `KeywordRouting` (7 tests) | keyword_plan() routes to correct tool names | Removing KEYWORD_PLAN entries |
| `ToolRegistry` (3 tests) | REGISTRY membership + scope restrictions | Removing REGISTRY entries or widening scopes |
| `IsDMHelper` (3 tests) | _is_dm() distinguishes DMs from channels | Changing the source check logic |

None of these are `hasattr`, source-text, or shape-only assertions. They call actual functions with real scope objects and check behavioral outputs.

### 5. Would merging delete anything?

**NO — zero deletions.**

```
git diff master...8e6ee5ed --stat:
 src/slackagenttools.py       | 436 ++++++
 src/slackconversation.py     |  19 ++
 tests/test_slack_agent_task249.py | 372 ++++++
 5 files changed, 948 insertions(+)
```

(The other 2 files are the task file moving TODO → DONE.)

### 6. Scope drift

**NONE — clean.** Only the 3 named source/test files changed. No unrelated modifications.

### 7. Import-graph test (no write path)

**PASSES — 10/10 tests green.**

`tests.test_slack_agent_cannot_act` confirms:
- No agent source imports a write module
- The conversation module reaches no write module
- The tools module reaches no write module
- The loop reaches no write module
- Every Bison attribute the agent touches is a read
- Only the loop posts to Slack (not the agent logic)

### 8. Full Slack agent test suite

**176 tests, 0 failures.** (22 new + 154 existing Slack agent tests.)

Note: The result block claims "279 existing Slack agent tests unchanged." I measured 154 existing under `test_slack_agent*` discovery pattern. The discrepancy is likely due to different test discovery patterns or counting method. The important fact is: zero regressions.

## Findings

### Finding 1: Weak behavioral tests for `replies_today` and `credits_today`

**Severity: LOW** | **Confidence: HIGH**

These two tools have no dedicated behavioral tests. They are tested only through:
- Keyword routing (keyword_plan routes to the right tool name)
- Registry membership (they exist in REGISTRY with correct scopes)

There is no test that calls `replies_today(scope)` or `credits_today(scope)` and verifies the output structure or filtering logic. If the `datetime.date.today()` filtering were broken, no test would catch it.

**Evidence**: grep for `replies_today` and `credits_today` in the test file shows only KeywordRouting and ToolRegistry references.

### Finding 2: `campaign_sending_schedule` test is structural only

**Severity: LOW** | **Confidence: HIGH**

`test_result_has_three_days` checks that the result has the three day keys, but the provider call fails in tests (no live provider). The test verifies error handling structure, not the happy path. The test comment acknowledges this: "This will try to hit the provider, which will fail in tests."

**Evidence**: `tests/test_slack_agent_task249.py` lines 195-207.

### Finding 3: Test count discrepancy

**Severity: INFORMATIONAL** | **Confidence: HIGH**

Result block claims "279 existing Slack agent tests unchanged, all green." Independent measurement found 154 existing tests under `test_slack_agent*` discovery pattern (176 total - 22 new). The claim may include tests from other discovery patterns or may be an overcount. No regression was observed regardless.

## Disposition

### MERGE

**Reason**: The work is clean, well-scoped, and properly wired. The privacy rule is structural (not prompt-based), reuses existing notify module guards, and is verified by behavioral tests that would fail if the privacy logic were removed. All 7 tools have production callers through both the keyword routing and model-driven paths. The import-graph test confirms no write path was introduced. Zero deletions, zero scope drift.

The two low-severity findings (weak tests for `replies_today`/`credits_today`, structural-only test for `campaign_sending_schedule`) are not blockers — they are coverage gaps that could be addressed in a follow-up but do not indicate broken functionality.

### Verification commands (reproducible)

```bash
# Check out the exact SHA
git worktree add .qwen/worktrees/verify 8e6ee5edcb1ccc970a3dfa1b86be599a9822bb29 --detach

# Run the TASK-249 tests
cd .qwen/worktrees/verify
python -m unittest tests.test_slack_agent_task249 -v

# Run the import-graph test
python -m unittest tests.test_slack_agent_cannot_act -v

# Run all Slack agent tests
python -m unittest discover -s tests -p "test_slack_agent*" -v

# Verify the diff
git diff master...8e6ee5edcb1ccc970a3dfa1b86be599a9822bb29 --stat
```
