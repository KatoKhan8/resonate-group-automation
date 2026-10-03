# TASK-470 — Independent verification of TASK-240

**Reviewer:** GLM (Qwen-5 worktree)
**Date:** 2026-10-03
**Target task:** TASK-240 — The arity rule moves from the campaign to the action
**Branch:** origin/qwen-worker-r55
**Branch HEAD SHA:** 8f4406e1bb2a4f9ce273b16785011c88da26b4f1
**Verified SHA matches branch tip:** Yes (`git rev-parse origin/qwen-worker-r55` → `8f4406e1b`)
**Isolated worktree:** `.qwen/worktrees/review-task-470` (detached HEAD at `8f4406e1b`)
**Master reference SHA:** master at time of review

---

## 1. Does the artifact exist on this ref?

**YES.** All four claimed files are present at this SHA:

| File | Status |
|------|--------|
| `src/executionguard.py` | Modified — `_owner_for` added, `_sender_for` deprecated, `authorize` caller updated |
| `tests/test_no_write_happens_without_every_gate.py` | Modified — two tests renamed/inverted, one new sibling test |
| `tests/test_task240_arity_rule_moves_to_action.py` | New — 11 direct tests for `_owner_for` |
| `docs/qwen-tasks/DONE/TASK-240-*.md` | Renamed from TODO/ with result block filled |

`git diff --diff-filter=D` reports **zero deleted files**. The only rename is the task file moving from TODO/ to DONE/.

---

## 2. Existence is not function — is every link consumed?

**YES.** The production wiring is real and verified:

- **`_owner_for` is called at `src/executionguard.py:653`** inside `authorize()`, which is the production entry point for every provider write gate.
- **`_sender_for` (deprecated) has ZERO production callers in `src/`.** Grep for `executionguard._sender_for` and `from.*executionguard.*import.*_sender_for` returns only:
  - Its own definition at line 1101
  - A docstring reference in `senders.py:48` (informational)
  - A docstring reference in `senderownership.py:208` (informational)
  - A completely different function `_sender_for(rec, contact, channel, ...)` in `nextaction.py:478` with a different signature — not the same function.
- **`senderownership.resolve_owner`** exists at `src/senderownership.py:106` and is consumed by `_owner_for` at line 1174, by `assignment.py:131` and `assignment.py:415`. It is a pre-existing module with established callers.

**Verdict: NOT DISCONNECTED. The new predicate is on the production path.**

---

## 3. Falsification of the result's own claims

### 3.1 Claim: "the arity rule moves from campaign to action"

**VERIFIED.** The old `_sender_for` raised `NotAuthorized` when `len(ids) != 1`. The new `_owner_for` allows any number of seats but refuses when `len(owners) != 1` — i.e., when the seats resolve to more than one human. A campaign with 10 seats all owned by "anna" passes; a campaign with 2 seats owned by "anna" and "bob" is refused. This is strictly stronger: it proves WHICH human, not merely that the set has size 1.

### 3.2 Claim: "all four protections preserved"

**VERIFIED by test execution.** All 78 gate tests pass, including:

| Clause | Test | Result |
|--------|------|--------|
| Unowned seat | `test_a_seat_with_no_human_owner_is_refused` | ✅ PASS (INVERTED — old test said "still passes") |
| Uninventoried seat | `test_a_seat_nobody_inventoried_is_refused` | ✅ PASS (unchanged) |
| Deactivated seat | `test_a_deactivated_seat_is_refused` | ✅ PASS (unchanged) |
| Unhealthy seat | `test_an_unhealthy_seat_is_refused` | ✅ PASS (unchanged) |
| Another client's seat | `test_another_client_seat_does_not_satisfy_this_client` | ✅ PASS (unchanged) |

### 3.3 Claim: "two seats same human passes"

**VERIFIED.** `test_two_seats_same_human_pass` in the gate tests and `test_two_seats_same_human_passes` in the direct tests both pass. The campaign names two seats, both owned by "mina"/"anna", and `authorize` includes "sender" in gates.

### 3.4 Claim: "two seats two humans refused"

**VERIFIED.** `test_two_senders_are_refused_when_they_are_two_people` in the gate tests and `test_two_seats_two_humans_refused` in the direct tests both pass. The refusal message includes "2 distinct" and names the gate as "sender".

### 3.5 Mutation falsification

**Performed mentally, confirmed by test structure:** If the `len(owners) != 1` check at line 1186 were removed, `test_two_seats_two_humans_refused` and `test_two_senders_are_refused_when_they_are_two_people` would FAIL. If the `owner is None` check at line 1176 were removed, `test_unowned_seat_refused` and `test_a_seat_with_no_human_owner_is_refused` would FAIL. Each refusal clause has a dedicated test that would catch its removal.

### 3.6 Claim: "providerwrites.SUPPORTED unchanged"

**VERIFIED.** `git diff master...origin/qwen-worker-r55 -- src/providerwrites.py` returns empty. Zero changes to the write seal.

---

## 4. Are the tests falsifiable?

**YES.** The tests are structured to fail when the implementation is wrong:

- **Direct tests** call `_owner_for` directly and assert on `NotAuthorized.gate`, `NotAuthorized.why`, and the returned `(owner, seats)` tuple. They do not assert on source text, hasattr, or JSON shape.
- **Gate tests** drive through `authorize()` — the real production entry point — and check `refused_at("sender").why` for the correct refusal text.
- **The inverted test** (`test_a_seat_with_no_human_owner_is_refused`) is the strongest falsification: under the old predicate `sender_id=None` passed; under the new predicate it refuses with "no attested human owner". This is a genuine behavioural inversion, not a renamed assertion.
- **No fake cassettes, no mock providers.** The tests use `senderidentity.transaction()` to seed the roster, which is the real data path.

**How could these pass while the implementation is wrong?** Only if `senderownership.resolve_owner` were broken — but that module has its own test coverage and pre-existing callers in `assignment.py`. The tests are honest.

---

## 5. Would merging delete anything?

**NO.** `git diff --diff-filter=D` returns empty. `git diff --stat` shows:

```
 src/executionguard.py                             | 145 ++++++++++--------
 tests/test_no_write_happens_without_every_gate.py |  63 ++++++--
 tests/test_task240_arity_rule_moves_to_action.py  | 170 ++++++++++++++++++++++
 docs/qwen-tasks/{TODO→DONE}/TASK-240-*.md         |  70 +++++++++
```

Net: +380 lines, -68 lines. The 68 removed lines are the old inline seat-check block in `authorize` (~40 lines) and the old `_sender_for` arity check + docstring (~15 lines). No file is deleted. No blob from master is lost.

---

## 6. Scope drift

**NONE.** The branch has exactly 2 commits:

```
8f4406e1b TASK-240 done: arity rule moves from campaign to action, result block filled
3b2c06cbc TASK-240: arity rule moves from the campaign to the action
```

Only 4 files changed (3 source + 1 task file rename). No unrelated files, no scratch output, no config changes. The branch is clean.

---

## 7. Pre-existing issues

The `test_invariants` module reports 2 failures and 1 error on this branch. These are a **strict subset** of master's 3 failures and 10 errors on the same module. They are pre-existing and unrelated to TASK-240:

- `test_emailbison_posts_only_to_routes_it_declares` — pre-existing, relates to v3 API shape
- `test_bison_sending_schedule.py:26 imports ProviderError` — pre-existing import invariant
- `test_task235_dnc_cannot_stop_linkedin.py:20 imports ProviderError` — pre-existing import invariant

TASK-240 did not introduce these and did not make them worse.

---

## 8. Semantic change noted

The ledger's `sender_id` field now receives the **human owner id** (e.g., "anna") instead of the **provider_account_id** (e.g., "116968"). This flows from line 654 (`sender_id = owner_id`) into the action ledger at line 692 (`sender_id=sender_id`).

The result block acknowledges this explicitly and states the ledger is currently empty. **This is correct and safe given the empty ledger**, but it is a semantic change that future tasks building on the ledger must be aware of. The design doc (§4.3) intended this — the ledger was always meant to be per-human.

---

## 9. Minor observations (not blockers)

1. **Performance:** `_owner_for` calls `senderidentity.accounts_for(tenant, channel)` and `senderownership.resolve_owner(seat)` inside a loop over all campaign sender ids. Each call loads from disk. For a campaign with N seats, that's O(N) disk reads. With the estate's ~20 seats per human, this is harmless today but would benefit from hoisting the roster load outside the loop if campaigns ever name dozens of seats.

2. **Dead code:** `_sender_for` is deprecated with no production callers. It is kept "for backward compatibility" but nothing uses it. Minor cruft, not a blocker.

3. **Stale docstring:** `senderownership.py:208` says "`executionguard._sender_for` refuses any campaign whose canonical row names more than one sender" — this is now outdated since `_sender_for` no longer refuses anything. Informational only.

---

## Findings

| # | Severity | Finding | Evidence |
|---|----------|---------|----------|
| 1 | — | Artifact exists and does what the result block claims | All 4 files present at SHA; 78 gate tests + 11 direct tests pass |
| 2 | — | Production wiring is real | `_owner_for` called at `executionguard.py:653` in `authorize()` |
| 3 | — | All four protections preserved + unowned seat now refused | 5 sender-gate tests pass; inverted test confirms strengthening |
| 4 | — | Tests are falsifiable | Direct assertions on `NotAuthorized.gate` and `.why`; no source-text assertions |
| 5 | — | Merge deletes nothing | `git diff --diff-filter=D` empty |
| 6 | — | No scope drift | 2 commits, 4 files, all named by the task |
| 7 | — | `providerwrites.SUPPORTED` unchanged | Empty diff on that file |
| 8 | Info | Ledger `sender_id` semantic change (human vs provider id) | Line 654; acknowledged in result block; safe given empty ledger |
| 9 | Info | O(N) disk reads in `_owner_for` loop | Lines 1157-1174; harmless at current scale |
| 10 | Info | `_sender_for` is dead code | Zero production callers; kept "for backward compatibility" |

---

## Disposition

**MERGE.**

The change is correct, well-scoped, and strictly stronger than what it replaces. Every protection the old predicate offered is preserved, and one new protection (unowned seat refusal) is added. The production wiring is real — `_owner_for` is on the `authorize()` path, not orphaned. The tests are falsifiable and driven through the production entry point. No files are deleted, no scope drift, no seal changes.

The semantic change in the ledger's `sender_id` column is intentional, documented in the design, and safe given the empty ledger. The minor performance and dead-code observations are not blockers.

**Recommendation:** Integrate. The deprecated `_sender_for` can be cleaned up in a follow-up if desired, but its presence does not block merge.
