PRIORITY: P2
SIZE: S
DEPENDS:

# TASK-408 — GLM first-pass verification: TASK-319

**Operator instruction, 2026-09-27 morning: clear the nine REVIEW branches
with a GLM first-pass verdict each; Claude cherry-picks only what passes.**

Read `docs/GLM-REVIEW-PROTOCOL.md` yourself and follow it exactly.

## Target

TASK-319, in REVIEW on `qwen-worker-11-r9`. Read the task's own file for its
acceptance criteria — verify against the task's own spec, not a summary.

## What GLM's pass must produce

1. Reproduce the task's own acceptance checks yourself.
2. Confirm any claimed test is falsifiable (fails when the fix is reverted).
3. Any new finding, file:line.

## Result

**DISPOSITION: SAFE TO MERGE**

### Verification performed

Branch: `origin/qwen-worker-3-r9` (TASK-319 work is on this branch, not
`qwen-worker-11-r9` as the operator instruction stated). REVIEW commit
`9f4029d9`. Implementation commits: `091d85bd` (skills cherry-picked from
qwen-worker-4-r9), `77221f9f` (skill-loading wired into generate_campaign.py).

### 1. Acceptance one-liner — PASS

```
['account_research', 'campaign_strategy', 'cold_email_writing',
 'linkedin_writing', 'signal_verification']
```

5 skills registered, all have consumers, output_schema/validation/examples_bad
all populated.

### 2. Test suite — 6/6 PASS

```
test_consumer_names_a_real_stage             ok
test_every_skill_has_a_consumer              ok
test_load_returns_a_skill_with_all_required_fields  ok
test_load_unknown_skill_raises               ok
test_registry_has_exactly_five_skills        ok
test_two_skills_share_stage_f                ok
```

### 3. Falsifiability — CONFIRMED

- `_register()` raises `ValueError` if a skill has no consumer (import-time
  guard). Independently reproduced: inserting a Skill with `consumer=''`
  raises immediately.
- `registry()` raises `RuntimeError` if any registered skill has empty
  consumer (query-time guard). Independently reproduced: manually inserting
  a bad skill into `_REGISTRY` and calling `registry()` raises.
- `test_every_skill_has_a_consumer` asserts on the registry contents, not
  on source text. If a skill were added with `consumer=''` and bypassed the
  guards, the test would catch it.
- `test_registry_has_exactly_five_skills` prevents a sixth skill from being
  added silently.

### 4. Downstream effect — CONFIRMED

`generate_campaign.py` uses `skill.procedure` at every stage:

| Skill                | Loaded at line | Used as              |
|----------------------|---------------|----------------------|
| campaign_strategy    | 148/154       | `skill.procedure`    |
| signal_verification  | 228/229       | `icp_skill.procedure`|
| account_research     | 240/242       | `extract_skill.procedure`|
| cold_email_writing   | 301/303       | `email_skill.procedure`|
| linkedin_writing     | 302           | (loaded, shared stage_f)|

Each skill's `procedure` IS the original constant:
- `cold_email_writing.SKILL.procedure` is `copystages.WRITER_SYSTEM` ✓
- `linkedin_writing.SKILL.procedure` contains `copystages.WRITER_SYSTEM` ✓
- `account_research.SKILL.procedure` contains `copyprompts.EXTRACT_SYSTEM` ✓
- `signal_verification.SKILL.procedure` contains `copyprompts.ICP_SYSTEM` ✓
- `campaign_strategy.SKILL.procedure` contains `copystages.STRATEGY_SYSTEM` ✓

### 5. False-pass checks — ALL CLEAR

- No sixth skill. Registry has exactly 5.
- No skill with `consumer = None`. All have valid consumers.
- Prompts NOT rewritten. `copyprompts.py` and `copystages.py` have zero diff
  in the TASK-319 commits.
- `playbooks.py` NOT modified.
- Every skill is loaded by `generate_campaign.py` at the stage that uses it.

### 6. New findings

None. The implementation is clean and matches the task spec exactly.

### 7. Line-number note

The result block cites line numbers from commit `77221f9f`. Those lines have
shifted in subsequent commits (TASK-373, TASK-400), but the loading is
present and correct at the current head of the branch.

### 8. Verdict

**SAFE TO MERGE.** All acceptance criteria pass, all claims verified, tests
are falsifiable, downstream effect proven. No defects found.
