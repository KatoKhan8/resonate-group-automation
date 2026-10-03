# TASK-531 — GLM Verdict: TASK-428

## Review metadata

| Field | Value |
|-------|-------|
| Task | TASK-428 |
| Branch | origin/qwen-worker-11-r9 |
| Branch HEAD SHA | c392a8ba4f07208cff6d89ac53c230aa64f4a7d5 |
| Verified SHA | c392a8ba4f07208cff6d89ac53c230aa64f4a7d5 (confirmed via `git rev-parse`) |
| Review worktree | .qwen/worktrees/task531-review (detached HEAD at c392a8ba4) |
| Reviewer | GLM (independent, via TASK-531) |
| Date | 2026-10-04 |

## Recommendation: **REWORK**

TASK-428's own implementation commit (`5791b9058`) was correct. A subsequent commit on the same branch — TASK-448 (`262c11f3a`) — removed `productive.io` from `FORBIDDEN_DOMAINS` entirely, destroying the narrow path-scoped allowance TASK-428 had built. At the branch HEAD, two of eight new tests FAIL, the "narrow allowance" is a universal exemption, and two of the task's six acceptance criteria are not met.

---

## Finding 1: The narrow allowance is dead code (CRITICAL)

**Severity:** Critical
**Category:** correctness / regression

### What TASK-428 built (commit 5791b9058)

TASK-428 correctly:
1. Renamed `config/clients/productive-offers.yaml` → `config/clients/productive/offers.yaml` (100% similarity, content unchanged — verified via `git diff`)
2. Updated `src/offers.py` `_offers_path()` to return the new path
3. Added `CLIENT_OWN_DOMAIN = "productive.io"` and `CLIENT_EVIDENCE_PATH = "config/clients/productive/"`
4. Added `_is_client_evidence_file(path)` helper
5. Added an inner check inside the `FORBIDDEN_DOMAINS` loop in `test_no_real_client_prospect_or_roster_domain`:
   ```python
   if domain == CLIENT_OWN_DOMAIN and _is_client_evidence_file(path):
       continue
   ```
6. Added 8 acceptance tests in `TestClientEvidenceAllowance`

This was correct. `productive.io` remained in `FORBIDDEN_DOMAINS`, and the inner check skipped it ONLY in the evidence path.

### What TASK-448 did (commit 262c11f3a)

TASK-448's commit message says: "productive.io was in FORBIDDEN_DOMAINS but it is the client's own public domain and the single approved CTA. Moved to CLIENT_OWN_DOMAINS allowlist."

The diff:
```diff
-    "nextoria.com", "cyber64.hr", "productive.io",
+    "nextoria.com", "cyber64.hr",
```

`productive.io` was removed from `FORBIDDEN_DOMAINS`. A new `CLIENT_OWN_DOMAINS` tuple was added for the email test. But the domain scan iterates `FORBIDDEN_DOMAINS`, so `productive.io` is never encountered, and TASK-428's inner check never fires.

### Evidence

```
$ python -c "from tests.test_fixture_hygiene import FORBIDDEN_DOMAINS, CLIENT_OWN_DOMAIN
... print('productive.io in FORBIDDEN_DOMAINS:', CLIENT_OWN_DOMAIN in FORBIDDEN_DOMAINS)"
productive.io in FORBIDDEN_DOMAINS: False
```

### Practical effect

`productive.io` is now allowed **everywhere** in the repository, not just in `config/clients/productive/`. The `_is_client_evidence_file` function, the `CLIENT_EVIDENCE_PATH` constant, and the inner check in the domain scan are all dead code. A file at `docs/anything.md` or `src/anything.py` could reference `productive.io` freely and the guard would not fire.

---

## Finding 2: Two of eight new tests FAIL (CRITICAL)

**Severity:** Critical
**Category:** correctness / test failure

### Test output (reproduced at c392a8ba4)

```
$ python -m unittest tests.test_fixture_hygiene.TestClientEvidenceAllowance -v

test_client_domain_in_evidence_path_is_allowed ... ok
test_client_domain_outside_evidence_path_is_refused ... FAIL
test_email_in_evidence_path_is_refused ... ok
test_mutation_widening_to_any_domain_in_path_fails ... ok
test_mutation_widening_to_client_domain_in_any_path_fails ... FAIL
test_personal_name_in_evidence_path_is_refused ... ok
test_phone_in_evidence_path_is_refused ... ok
test_prospect_domain_inside_evidence_path_is_refused ... ok

Ran 8 tests in 0.001s
FAILED (failures=2)
```

### Failure 1: `test_client_domain_outside_evidence_path_is_refused`

Asserts `assertTrue(_domain_would_be_flagged("productive.io", "config/clients/productive.yaml"))`. The helper returns `False` because `productive.io` is not in `FORBIDDEN_DOMAINS`, so the first line `if domain not in FORBIDDEN_DOMAINS: return False` short-circuits.

This is **Acceptance 2** from the task: "The same client domain OUTSIDE that path is still REFUSED." **Not met.**

### Failure 2: `test_mutation_widening_to_client_domain_in_any_path_fails`

Same root cause. Asserts `assertTrue(_domain_would_be_flagged("productive.io", "docs/some-historical-doc.md"))`. Returns `False` for the same reason.

This is **Acceptance 6b** from the task: "MUTATION: widen it to the client domain in any path, and a test must fail." **Not met.** The mutation has already happened (TASK-448 widened it universally) and the test cannot detect it.

---

## Finding 3: The result block claims are not accurate (MEDIUM)

**Severity:** Suggestion
**Category:** correctness / claims

The result block states:
- "TESTS: TestClientEvidenceAllowance (8 new tests): ALL PASS" — **False.** 6 pass, 2 fail.
- "test_fixture_hygiene domain test: 35 remaining hits outside the allowance scope" — The domain test passes (`test_no_real_client_prospect_or_roster_domain ... ok`), but only because `productive.io` is no longer in the forbidden set. The 35 hits are other domains in other files, which is correct, but the mechanism is not what the result block describes.

---

## Finding 4: Artifact exists and offers.load() works (VERIFIED)

**Severity:** N/A (positive finding)

- `config/clients/productive/offers.yaml` exists at the branch HEAD (renamed from `config/clients/productive-offers.yaml`, 100% content similarity)
- `src/offers.py` `_offers_path()` returns the correct new path
- `offers.load()` returns 8 offers; Offer A (`OFFER-A-ECONOMIC-BUYER`) and Offer B (`OFFER-B-OPERATIONS`) are `approval_status=approved`, `version=2` — unchanged
- Production callers exist: `src/campaignstrategy.py:69` and `src/generate_campaign.py:227,297` call `offers_mod.load()`
- `test_an_offer_cannot_be_invented`: 11/11 pass (the result block claimed 10/11 with a pre-existing failure, but `test_approval_status_is_not_defaulted_to_approved` now passes — TASK-448 fixed it)
- `test_a_dead_cta_link_is_refused`: 22/22 pass
- `test_a_case_study_claim_must_appear_on_the_page`: 19/19 pass

---

## Finding 5: Merging would not delete anything (VERIFIED)

`git diff master...origin/qwen-worker-11-r9 --diff-filter=D --name-only` returns empty. No files would be deleted.

The rename `config/clients/productive-offers.yaml` → `config/clients/productive/offers.yaml` is a pure rename (similarity index 100%).

---

## Finding 6: Scope drift (INFORMATIONAL)

The branch carries work from multiple tasks beyond TASK-428:
- TASK-448 (hygiene fixes, test corrections)
- TASK-437 (GLM verification of TASK-267)
- TASK-456 (GLM verdict for TASK-304)
- TASK-310 (training set)
- TASK-328 (review_hash threading)
- TASK-385 (pool status command)
- TASK-400 (generation entrypoint)

TASK-428's specific changes are limited to 3 files:
- `config/clients/productive-offers.yaml` → `config/clients/productive/offers.yaml` (rename)
- `src/offers.py` (4 lines: path update + docstring)
- `tests/test_fixture_hygiene.py` (+195 lines: constants, helper, 8 new tests, inner check)

The scope is clean. The defect is an interaction with TASK-448's changes on the same branch, not scope drift.

---

## Fix required

The fix is straightforward and must reconcile TASK-428 and TASK-448:

1. **Restore `productive.io` to `FORBIDDEN_DOMAINS`.** This re-enables the domain scan to encounter it.
2. **Keep TASK-428's inner check** (`if domain == CLIENT_OWN_DOMAIN and _is_client_evidence_file(path): continue`). This provides the narrow path-scoped allowance.
3. **Keep TASK-448's `CLIENT_OWN_DOMAINS` tuple and email test skip.** The email test is a separate check that correctly allows emails at the client's domain.
4. **Both mechanisms are needed:** `FORBIDDEN_DOMAINS` for the domain scan (with the path-scoped exception), and `CLIENT_OWN_DOMAINS` for the email scan (universal, because an email at the client's domain is the client's staff regardless of file path).

After the fix, all 8 `TestClientEvidenceAllowance` tests should pass, and the full `test_fixture_hygiene` suite should be green (25/25).

---

## Disposition summary

| # | Finding | Severity | Disposition |
|---|---------|----------|-------------|
| 1 | Narrow allowance is dead code (TASK-448 regression) | Critical | REWORK |
| 2 | Two of eight new tests FAIL | Critical | REWORK |
| 3 | Result block claims are inaccurate | Suggestion | REWORK |
| 4 | Artifact exists, offers.load() works, production callers verified | — | VERIFIED |
| 5 | Merging would not delete anything | — | VERIFIED |
| 6 | Scope drift: clean, but interacts destructively with TASK-448 | — | INFORMATIONAL |

## Recommendation

**REWORK.** The fix is a one-line restoration of `productive.io` to `FORBIDDEN_DOMAINS`, keeping both TASK-428's inner check and TASK-448's email-test allowance. After the fix, re-run `TestClientEvidenceAllowance` and confirm all 8 pass. The structural change (file rename, path update) is correct and should be preserved.
