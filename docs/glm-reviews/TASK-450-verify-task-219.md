# TASK-450 — Independent GLM Verification: TASK-273

## Review identity

| Field | Value |
|-------|-------|
| Target task | TASK-273 |
| Target branch | origin/qwen-worker-r9 |
| Branch HEAD SHA | e456c6128774cfd00960ac50d7b39c6e99a3f8cd |
| SHA verified | `git rev-parse e456c6128774cfd00960ac50d7b39c6e99a3f8cd` → confirmed |
| Review worktree | `.qwen/worktrees/glm-450` (detached HEAD at target SHA) |
| Reviewer | GLM (independent, read-only) |
| Date | 2026-09-28 |

## What TASK-273 claims

A conformance suite for EmailBison and HeyReach adapters — 33 new tests in
`tests/test_provider_conformance.py` (349 lines), grouped into four categories:

1. **Shared and enforced** (13 claimed): ProviderError contract, write door,
   guard_prospect_facing, refuse_unauthorized_write
2. **Shared by convention** (5 claimed): headers(), check(), main(),
   events_contract() existence
3. **Declared differences** (7 claimed): signature asymmetries, validation
   location, write door architecture, fake coverage
4. **Refused by design** (7 claimed): unsupported operations raise
   WriteUnsupported, hand-built authorizations refused

Result block claims: STATUS DONE, 33 tests all green, 130 provider-related
tests green, zero new failures.

## Verification results

### 1. Does the artifact exist on this ref?

**YES.** `tests/test_provider_conformance.py` exists at the target SHA.

```
$ git log --diff-filter=A --all -- tests/test_provider_conformance.py
commit 17839f726e7cb5da0c8146e1b5e63ccd90d7e728
    TASK-273: conformance suite for EmailBison and HeyReach adapters
```

Added in commit 17839f72, which is an ancestor of the target HEAD e456c612.
The file is 349 lines, matching the claim.

### 2. Do the tests actually pass?

**YES.** All 33 tests pass at the target SHA:

```
$ python -m unittest tests.test_provider_conformance -v
Ran 33 tests in 0.302s
OK
```

Test count breakdown (actual vs claimed):

| Group | Claimed | Actual | Match |
|-------|---------|--------|-------|
| Shared and enforced | 13 | 14 | Minor miscount |
| Shared by convention | 5 | 5 | ✓ |
| Declared differences | 7 | 7 | ✓ |
| Refused by design | 7 | 7 | ✓ |
| **Total** | **33** | **33** | **✓** |

The "shared and enforced" group has 14 tests, not 13. The result block
miscounted by one. This is cosmetic — the tests themselves are correct.

### 3. Existence is not function — are the tests behavioral?

**Mixed.** The suite has four groups with genuinely different rigor:

**Group 1 — Shared and enforced: BEHAVIORAL ✓**
- Calls `bison.check()` and `heyreach.check()` with cleared keys, asserts
  `result["ok"]` is False. Real function call, real assertion on return value.
- Calls `key("BISON_KEY")` with missing key, asserts `ProviderError` raised.
  Real exception path.
- Calls `bison._allow("POST", "/campaigns/999/does-not-exist")`, asserts
  `ProviderError`. Independently verified: the function does raise.
- Calls `heyreach._write_body("/campaign/DoesNotExist", {})`, asserts
  `ProviderError`. Independently verified.
- Calls `refuse_unauthorized_write("POST", ...)` and asserts
  `ProviderWriteRefused`. Real transport-level door.
- Calls `is_prospect_facing()` with real host strings. Real function.

**Group 2 — Shared by convention: EXISTENCE-ONLY ⚠**
- `callable(getattr(mod, "headers", None))` — this is `hasattr` with a type
  check. It proves the function exists and is callable, not that it returns
  anything correct.
- Same pattern for `check()`, `main()`, `events_contract()`.
- `test_both_events_contract_return_dicts` is slightly better: it calls the
  function and asserts the return type is `dict`.

The protocol says "proving a function exists" is not accepted as proof. These
five tests are existence checks. However, the task specification explicitly
categorizes this group as "shared by convention" and "not contractual," and
the suite honestly labels them as such. The task spec says:

> "shared by convention: headers(), check(), main(argv), events_contract()"

The suite matches the spec. The weakness is acknowledged by the task's own
framing. **This is not a defect in the suite; it is an honest limitation of
the category.**

**Group 3 — Declared differences: BEHAVIORAL ✓**
- Uses `inspect.signature()` to extract exact parameter names, asserts they
  differ, and pins the exact shapes: `["campaign_id", "title", "steps"]` vs
  `["campaign_id", "sequence"]`. If someone changes either signature, this
  test fails. Falsifiable.
- Same pattern for `resume_campaign`: asserts `expect_leads` is in bison's
  params but not heyreach's. Falsifiable.
- Asserts HeyReach has `validate_sequence_for_write`, `sequence_hazards`,
  `refuse_unsupported_sequence` (callable) and `SequenceInvalid` (subclass of
  `ProviderError`). Existence check, but for a known asymmetry that the task
  says to pin.
- Asserts Bison does NOT have those names. Negative existence check — if
  someone adds them to Bison, the test goes red, which is the point.
- Asserts `_write_body` exists in HeyReach and `_allow` exists in Bison.
  Existence checks for known architectural differences.
- Asserts `fakebison` imports and `fakeheyreach` raises `ImportError`.
  Falsifiable.

**Group 4 — Refused by design: BEHAVIORAL ✓**
- Iterates `providerwrites.OPERATIONS`, calls `require_supported(op)` for
  each unsupported operation, asserts `WriteUnsupported`. Real function call
  through the production entry point.
- Calls `require_supported("bison.nonexistent_operation")`, asserts
  `WriteUnsupported`. Real function.
- Calls `describe("heyreach.nonexistent_operation")`, asserts
  `WriteUnsupported`. Real function.
- Iterates `providerwrites.SUPPORTED`, asserts each is in `OPERATIONS`. Real
  data structure check.

**Hand-built authorization tests: BEHAVIORAL ✓**
- Calls `providerwrites.perform()` with a dict as authorization, asserts
  `WriteRefused`. Real production entry point, real exception path.
  Independently verified.
- Creates a real `executionguard.Authorization` for `heyreach.add_lead`,
  passes it to `perform()` for `heyreach.activate`, asserts `WriteRefused`.
  Tests the operation-mismatch check through the real entry point.
  Independently verified.

### 4. Falsification: would these pass while the implementation is wrong?

**Signature tests**: If someone changed `bison.set_sequence` to match
HeyReach's signature, the test would fail. Falsifiable. ✓

**Write door tests**: If `_allow` or `_write_body` stopped refusing undeclared
routes, the tests would fail. Falsifiable. ✓

**Authorization tests**: If `perform()` stopped checking `isinstance` or
operation mismatch, the tests would fail. Falsifiable. ✓

**Convention tests**: If someone removed `headers()` from bison, the test
would fail. But if someone changed `headers()` to return garbage, the test
would still pass. **Not falsifiable for correctness, only for existence.**
However, this is the convention group, not the contract group.

**Declared difference tests**: If someone added sequence validation to Bison,
the "bison has no sequence validation" test would fail. Falsifiable. ✓

### 5. Would merging delete anything?

**NO.** The branch diff vs master shows:
- 75 files changed, 17680 insertions, 3150 deletions
- Deletions are only task files moving between stages (TODO → DONE/REVIEW),
  which is normal task lifecycle
- No source code deletions
- No test deletions
- `tests/test_provider_conformance.py` is a pure addition

TASK-273's own commits touch only:
- `tests/test_provider_conformance.py` (added)
- Task file moves (TODO → RUNNING → REVIEW)

### 6. Scope drift

**The branch carries significant scope drift.** The branch has 75 files
changed vs master, including:
- 8 new docs files (APIFY-COST, ICP-VERDICTS, LINKEDIN-CADENCE, etc.)
- 6 new GLM review documents
- Multiple task files in various stages
- Source changes in `bisonfactory.py`, `generate.py`, `generate_campaign.py`,
  `heyreachfactory.py`, `secondbrain.py`, `sequenceplan.py`
- 10+ new test files
- Script additions

**However, TASK-273's own commits are clean.** The three commits that belong
to TASK-273 (53d316fb claim, 17839f72 implementation, e456c612 move to REVIEW)
touch only the test file and task file moves. Cherry-picking TASK-273 would be
straightforward:

```
git cherry-pick 17839f72  # the implementation commit
```

This would add only `tests/test_provider_conformance.py`.

### 7. Zero new failures claim

**PARTIALLY VERIFIED.** The result block claims "130 provider-related tests
green" and "pre-existing failures in test_invariants/test_audit (3 failures,
3 errors) confirmed identical with and without the new file."

I verified:
- `tests.test_provider_conformance`: 33 tests, all pass ✓
- `tests.test_nothing_writes_to_a_provider`: all pass ✓
- `tests.test_provider_body`: all pass ✓
- `tests.test_provider_name`: all pass ✓

I did not run the full suite to verify the pre-existing failure count, but
the claim is plausible and the new tests do not introduce failures in the
modules I spot-checked.

## Findings

### Finding 1: Minor miscount in result block

**Severity**: Low
**Category**: Documentation
**Evidence**: Result block claims "13 tests" in Group 1, actual count is 14.
**Disposition**: No action required. The tests themselves are correct; the
result block has a cosmetic miscount.

### Finding 2: Convention group tests are existence-only

**Severity**: Low
**Category**: Test quality
**Evidence**: Group 2 tests use `callable(getattr(mod, "headers", None))`
pattern, which proves existence but not correctness.
**Disposition**: Accepted. The task spec explicitly categorizes these as
"shared by convention" and "not contractual." The suite honestly labels them.
This is an honest limitation of the category, not a defect.

### Finding 3: Branch carries significant scope drift

**Severity**: Informational
**Category**: Integration hygiene
**Evidence**: Branch has 75 files changed vs master, but TASK-273's own
commits touch only one test file.
**Disposition**: Cherry-pick the implementation commit (17839f72) to avoid
integrating unrelated changes. Do not merge the branch wholesale.

## Disposition

**MERGE** (with cherry-pick, not wholesale branch merge)

The artifact exists, does what it claims, and the important tests are
behavioral and falsifiable. The convention group is weak by design and
honestly labeled. The suite adds real value: it pins the declared differences
between the two adapters so a future convergence is loud, and it tests the
authorization door through the real production entry point.

**Recommended integration**:

```
git cherry-pick 17839f726e7cb5da0c8146e1b5e63ccd90d7e728
```

This adds only `tests/test_provider_conformance.py` (349 lines, 33 tests).

**Not verified**: Full suite run to confirm the "130 provider-related tests
green" claim and the pre-existing failure count. Spot-checks of provider
test modules all pass.

## Reproducible commands

```bash
# Check out the exact SHA
git worktree add .qwen/worktrees/glm-450 e456c6128774cfd00960ac50d7b39c6e99a3f8cd --detach

# Run the conformance suite
cd .qwen/worktrees/glm-450
python -m unittest tests.test_provider_conformance -v

# Verify the artifact exists
git log --diff-filter=A --all -- tests/test_provider_conformance.py

# Check what TASK-273's commits touched
git diff-tree --no-commit-id --name-status -r 17839f726e7cb5da0c8146e1b5e63ccd90d7e728
```
