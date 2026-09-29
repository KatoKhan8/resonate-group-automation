# TASK-486 — Independent verification of TASK-339

**Reviewed branch:** `origin/qwen-worker-2-r63`
**Branch HEAD SHA:** `ae54f5182b82377a7916bf0ab32fbd2404c5f926`
**Verified at:** detached HEAD `ae54f518`
**Date:** 2026-09-29

---

## Summary

TASK-339 added deterministic semantic paraphrase detection to `src/sequencegate.py`.
The counter-example that lexical overlap missed ("margins thin on fixed scope" vs
"profit on flat fee projects squeezed") now fails via `semantic_overlap()`. 21 new
tests pass. 19 existing tests still pass. The implementation is correct in isolation.

**The module has zero production callers in `src/`.** This is the recurring defect:
a thing computed correctly that nothing downstream reads. TASK-339's own description
acknowledges this ("per TASK-321, `sequencegate.check` is not called in production
at all"). The improvement is real but DISCONNECTED.

**Recommendation: REWORK** — not because the code is wrong, but because the artifact
is unconsumed. The semantic check should be wired to a production caller before
merge, or merged with an explicit follow-up task for wiring.

---

## Findings

### F1 — Zero production callers (CRITICAL — DISCONNECTED)

`grep -rn "sequencegate" src/` returns only `sequencegate.py` itself. The only
imports are from test files:

```
tests/test_the_sequence_gate_catches_what_copylint_cannot.py:8:from src import copylint, sequencegate
tests/test_two_paraphrases_of_one_argument_do_not_pass.py:12:from src import sequencegate
```

No production module in `src/` imports or calls `sequencegate.check()`,
`sequencegate.semantic_overlap()`, or any other function from the module.

**Why this matters:** The task's own description states "per TASK-321,
`sequencegate.check` is not called in production at all." Adding a semantic
paraphrase check to a module nobody calls improves the module but does not
improve the system. QWEN.md is explicit: "Existence is not function... trace
the whole chain and prove every link is consumed. Zero production callers means
DISCONNECTED, which is a rework and not a merge."

**Evidence:** `git grep -n "sequencegate" ae54f518 -- src/ | grep -v sequencegate.py` returns empty.

### F2 — `_role_profile` is identical to `_concept_profile` (MEDIUM — misleading design)

The code describes "two independent thresholds" — concept overlap and role
overlap — that "both must be met." The docstring for `semantic_overlap()` says
"Both concept overlap and role overlap must be >= 0.6." The result block says
"Sharing concepts but with different roles (e.g. same words, different argument
structure) is not enough."

But `_role_profile()` is implemented as `return _concept_profile(text)`. The
two profiles are always identical. The "role overlap" check is a no-op that
provides zero additional filtering. The third failure mode described in the
comments ("sharing concepts but with different roles") is structurally impossible.

**Verified:**

```python
>>> _concept_profile("Your margins are thin on fixed scope work")
{'LOW', 'MARGIN', 'PROJECT_TYPE'}
>>> _role_profile("Your margins are thin on fixed scope work")
{'LOW', 'MARGIN', 'PROJECT_TYPE'}
>>> # Always identical
```

**Impact:** Does not affect correctness — the check still catches the
counter-example. But the code and comments describe a two-dimensional filter
that is actually one-dimensional. A future maintainer reading the comments
would believe the role check provides independent filtering when it does not.

### F3 — Stale warning contradicts the new check (LOW — misleading to callers)

After the semantic check was added, the unconditional warning at the end of
check #6 still fires:

```python
if len(order) > 1:
    warn("followup_adds_value", "sequence",
         "lexical overlap only: two steps arguing the same thing in "
         "different words pass this check. Semantic repetition is NOT "
         "verified here")
```

This warning is now false. The semantic check DOES verify semantic repetition.
A caller reading warnings would believe the check was not done when it was.

The existing test `test_the_paraphrase_blind_spot_is_reported_not_silent`
asserts this warning fires, so removing it would break that test. Both the
warning and the test should be updated together.

**Verified:** Running `check()` on a two-email sequence produces the warning
even when the semantic check actively catches the paraphrase.

### F4 — Regression set is a proxy, not the actual fifty (LOW — honest but incomplete)

The result block honestly states: "The fifty's actual 21 passed leads are in
`work/` (gitignored, Claude's worktree only). I constructed a diverse regression
set from the argument patterns in the existing tests and the concept groups."

The 10 "genuinely different" test pairs are constructed from argument patterns,
not from actual production sequences. This is acceptable given the constraint
(work/ is not available to workers), but the acceptance criterion 2 ("report how
many still pass") was not met against the actual baseline.

### F5 — Concept groups are hand-curated with no extension mechanism (INFO)

The 15 concept groups in `_SEMANTIC_GROUPS` cover the outreach domain but are
hand-curated. New argument patterns (e.g., "compliance risk," "security
exposure," "team morale") may require new groups. There is no test that fails
when a common outreach term is not covered by any group.

This is noted as a risk in the result block and is acceptable for now.

---

## What was verified

| Claim | Verdict | Evidence |
|-------|---------|----------|
| Counter-example now fails | **VERIFIED** | `semantic_overlap(A, B) = 1.0`, `check()` returns `passed=False` |
| Old code passed the counter-example | **VERIFIED** | Reverted to `bad85e04~1`: test fails with `AttributeError: semantic_overlap` |
| 21 new tests pass | **VERIFIED** | `py -3 -m unittest tests.test_two_paraphrases_of_one_argument_do_not_pass -v` → 21/21 OK |
| 19 existing tests still pass | **VERIFIED** | `py -3 -m unittest tests.test_the_sequence_gate_catches_what_copylint_cannot -v` → 19/19 OK |
| Semantic cannot rescue lexical failure | **VERIFIED** | `test_lexical_failure_stands_regardless_of_semantic` passes |
| Genuinely different arguments pass | **VERIFIED** for proxy set | 10 constructed pairs + 1 five-step sequence pass |
| Merging would delete files | **NOT A RISK** | Diff is purely additive in src/ and tests/ (+372/-20 lines; deletions are comment-only) |
| Scope drift | **NONE** | 4 files changed: task file TODO→REVIEW, sequencegate.py modified, new test file |

---

## What was NOT verified

| Claim | Reason |
|-------|--------|
| Actual 21 passed leads from the fifty still pass | `work/` is gitignored and not available in worker worktrees |
| Full suite passes | Not run; the result block says "running (background bg_df122f19)" with no verdict recorded |
| Production caller exists | Confirmed absent (F1) |

---

## Disposition

| Finding | Severity | Disposition |
|---------|----------|-------------|
| F1: Zero production callers | CRITICAL | DISCONNECTED — rework needed before merge |
| F2: role_profile == concept_profile | MEDIUM | Code quality — misleading but not incorrect |
| F3: Stale warning contradicts new check | LOW | Should be fixed together with F2 |
| F4: Proxy regression set | LOW | Accepted — honest limitation, not a defect |
| F5: Hand-curated concept groups | INFO | Accepted — noted risk, extensible |

---

## Recommendation

**REWORK** — with a narrow scope:

1. **Wire `sequencegate.check()` to a production caller**, or create a follow-up
   task for it. Merging an improvement to an unconsumed module does not improve
   the system. TASK-321 is the wiring task; if it exists, this branch should
   depend on it or include the wiring.

2. **Fix F2 and F3 together:** either make `_role_profile` actually distinct from
   `_concept_profile` (e.g., mapping words to syntactic roles rather than
   semantic groups), or remove the role overlap check and update the comments to
   describe the actual one-dimensional filter. Remove or conditionalize the stale
   warning, and update `test_the_paraphrase_blind_spot_is_reported_not_silent`
   accordingly.

The code itself is correct. The semantic check catches the counter-example, the
tests are well-structured, and the result block is honest about limitations. The
blocker is purely the absence of a production consumer.

---

## Reproducible commands

```bash
# Check out the exact SHA
git worktree add /tmp/task486-review ae54f5182b82377a7916bf0ab32fbd2404c5f926 --detach

# Run new tests
cd /tmp/task486-review
py -3 -m unittest tests.test_two_paraphrases_of_one_argument_do_not_pass -v

# Run existing tests
py -3 -m unittest tests.test_the_sequence_gate_catches_what_copylint_cannot -v

# Verify zero production callers
git grep -n "sequencegate" HEAD -- src/ | grep -v sequencegate.py

# Verify role_profile == concept_profile
py -3 -c "from src import sequencegate as sg; print(sg._concept_profile('margin thin') == sg._role_profile('margin thin'))"

# Seen-to-fail: revert to old code
git checkout bad85e04~1 -- src/sequencegate.py
py -3 -m unittest tests.test_two_paraphrases_of_one_argument_do_not_pass.ParaphraseDetection.test_the_exact_counter_example_from_the_comment_now_fails
# → FAILS with AttributeError: semantic_overlap
git checkout ae54f518 -- src/sequencegate.py

# Clean up
git worktree remove /tmp/task486-review --force
```
