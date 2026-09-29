# GLM Verdict: TASK-428 — Client evidence path and hygiene allowance

## Review metadata

    reviewed task         TASK-428
    reviewed branch       origin/qwen-worker-11-r9
    reviewed HEAD SHA     c392a8ba4f07208cff6d89ac53c230aa64f4a7d5
    merge base            f69793008b003ef0945538520d494fe5e00a41bd
    review worktree       .qwen/worktrees/task531-review (detached at c392a8ba)
    review date           2026-09-29
    reviewer              TASK-531 (Qwen worker, independent verification)

## Scope

TASK-428 claims:
1. `config/clients/productive-offers.yaml` was renamed to `config/clients/productive/offers.yaml`
2. `src/offers.py` was updated to read from the new path
3. The fixture-hygiene guard got a NARROW allowance: `productive.io` in `config/clients/productive/` ONLY
4. The guard still refuses `productive.io` everywhere else
5. Eight acceptance tests cover both sides and both mutation directions
6. `offers.load()` returns 8 offers, Offers A and B approved at v2

## Finding 1 — File rename: VERIFIED

The file exists at `config/clients/productive/offers.yaml` on the branch. The old path `config/clients/productive-offers.yaml` is gone. `git diff --diff-filter=R` shows a 100% content-match rename.

## Finding 2 — Path wiring: VERIFIED, CONSUMED

`src/offers.py` `_offers_path()` now returns `config/clients/productive/offers.yaml`. The docstring was updated to match.

Production callers confirmed:
- `src/generate_campaign.py` line 21: `from . import ... offers as offers_mod`
- `src/generate_campaign.py` line 227: `all_offers = offers_mod.load()`
- `src/campaignstrategy.py` line 22: `from . import copystages, offers as offers_mod`

`offers.load()` validated in isolation: 8 offers returned, OFFER-A-ECONOMIC-BUYER and OFFER-B-OPERATIONS approved at v2 by Zvonimir. Matches the result block's claims exactly.

## Finding 3 — The allowance is NOT narrow. It is universal. CRITICAL DEFECT.

**The stated policy:** `productive.io` allowed in `config/clients/productive/` ONLY, refused everywhere else.

**The actual implementation:** `productive.io` was removed from `FORBIDDEN_DOMAINS` entirely by TASK-448 (commit `262c11f3`), which sits on top of TASK-428's commit (`5791b905`) on the same branch. A new `CLIENT_OWN_DOMAINS` tuple was added with a universal skip in both the domain test and the email test — no path check.

**Evidence:**

```
# TASK-428 commit (5791b905) added the path-based mechanism:
  CLIENT_OWN_DOMAIN = "productive.io"
  CLIENT_EVIDENCE_PATH = "config/clients/productive/"
  + if domain == CLIENT_OWN_DOMAIN and _is_client_evidence_file(path): continue

# TASK-448 commit (262c11f3) then removed productive.io from FORBIDDEN_DOMAINS:
- "nextoria.com", "cyber64.hr", "productive.io",
+ "nextoria.com", "cyber64.hr",

# And added a UNIVERSAL skip in the email test:
+ CLIENT_OWN_DOMAINS = ("productive.io",)
+ if low in CLIENT_OWN_DOMAINS: continue   # no path check
```

**Consequence:** `productive.io` is now allowed in EVERY file in the repository. The path-based skip from TASK-428 is dead code — `productive.io` is never iterated in the domain test because it is not in `FORBIDDEN_DOMAINS`. The email test skips it universally.

**Reproduction:**

```python
from tests.test_fixture_hygiene import FORBIDDEN_DOMAINS, CLIENT_OWN_DOMAIN
print(CLIENT_OWN_DOMAIN in FORBIDDEN_DOMAINS)  # False — the domain is unguarded
```

A file `docs/evil.md` containing `productive.io` would pass both the domain test and the email test. The stated policy is not enforced.

## Finding 4 — Two of TASK-428's own acceptance tests FAIL

Ran `python -m unittest tests.test_fixture_hygiene -v` in the isolated worktree:

    25 tests run, 2 FAILURES:

    FAIL: test_client_domain_outside_evidence_path_is_refused
      AssertionError: False is not true : productive.io outside
      config/clients/productive/ should still be refused

    FAIL: test_mutation_widening_to_client_domain_in_any_path_fails
      AssertionError: False is not true : productive.io outside
      config/clients/productive/ must be refused.

Both tests call `_domain_would_be_flagged(CLIENT_OWN_DOMAIN, outside_path)`, which checks `if domain not in FORBIDDEN_DOMAINS: return False`. Since `productive.io` is not in `FORBIDDEN_DOMAINS`, it returns `False` immediately. The tests correctly detect that the refusal is not enforced — and they fail because it is not.

The other 23 tests pass, including:
- `test_no_real_client_prospect_or_roster_domain`: passes because `productive.io` is never iterated
- `test_client_domain_in_evidence_path_is_allowed`: passes trivially (the domain is allowed everywhere)
- `test_prospect_domain_inside_evidence_path_is_refused`: passes because prospect domains ARE still in `FORBIDDEN_DOMAINS`

## Finding 5 — Other test results: VERIFIED

- `test_a_dead_cta_link_is_refused`: 22/22 PASS
- `test_a_case_study_claim_must_appear_on_the_page`: 19/19 PASS
- `test_an_offer_cannot_be_invented`: 11/11 PASS (the result block said 10/11 with a pre-existing failure; `test_approval_status_is_not_defaulted_to_approved` now passes because it checks that offers claiming `approved` have `approved_by` set, which A and B do)

## Finding 6 — Deletion risk: NONE

`git diff master...c392a8ba --diff-filter=D` returns empty. The branch deletes no files relative to the merge base. The offers file is a 100% content-match rename. Task file stage moves (TODO → REVIEW/DONE/RUNNING) are structural.

Master has added `messaging_rules()` to `src/offers.py` since the merge base. The branch does not touch that area. A merge would retain both.

## Finding 7 — Scope drift: PRESENT but structural

The branch carries work from TASK-310, TASK-328, TASK-385, TASK-437, TASK-448, and TASK-456 in addition to TASK-428. For TASK-428 specifically, the relevant files are:

- `config/clients/productive-offers.yaml` → `config/clients/productive/offers.yaml` (rename)
- `src/offers.py` (2-line path change)
- `tests/test_fixture_hygiene.py` (allowance constants + 8 acceptance tests)

The TASK-448 changes to `test_fixture_hygiene.py` (removing `productive.io` from `FORBIDDEN_DOMAINS`, adding `CLIENT_OWN_DOMAINS`) are what break TASK-428's stated policy. If TASK-428 were cherry-picked alone, its path-based mechanism would be correct — but TASK-448 on top of it undoes the restriction.

## Finding 8 — Stale docstring references (minor)

Two files still reference the old path `config/clients/productive-offers.yaml` in docstrings:
- `src/casestudies.py` line 3
- `tests/test_an_offer_cannot_be_invented.py` line 3

These are documentation only, not functional. The code uses `_offers_path()` which returns the correct new path.

## Disposition

| # | Finding | Severity | Evidence |
|---|---------|----------|----------|
| 1 | File rename verified | PASS | `git diff --diff-filter=R`, file exists at new path |
| 2 | Path wiring verified, consumed | PASS | `offers.load()` returns 8 offers, 2 approved at v2 |
| 3 | Allowance is universal, not path-scoped | **CRITICAL** | `productive.io` removed from `FORBIDDEN_DOMAINS` by TASK-448; path-based skip is dead code |
| 4 | Two acceptance tests FAIL | **CRITICAL** | `test_client_domain_outside_evidence_path_is_refused`, `test_mutation_widening_to_client_domain_in_any_path_fails` |
| 5 | Other tests pass | PASS | 22/22 CTA, 19/19 case study, 11/11 offer invention |
| 6 | No deletion risk | PASS | `git diff --diff-filter=D` empty |
| 7 | Scope drift | INFO | TASK-448 on top of TASK-428 undoes the path restriction |
| 8 | Stale docstrings | MINOR | Two docstring references to old path |

## Recommendation: REWORK

The structural change (file rename + path wiring) is correct and well-tested. The offers module works at the new path and has production callers.

The hygiene allowance is NOT what the task claims. TASK-448 removed `productive.io` from `FORBIDDEN_DOMAINS` entirely, making it universally allowed. The path-based restriction from TASK-428 is dead code. Two of TASK-428's own acceptance tests detect this and fail.

**To fix:**

1. **Restore `productive.io` to `FORBIDDEN_DOMAINS`.** The path-based skip in the domain test (`if domain == CLIENT_OWN_DOMAIN and _is_client_evidence_file(path): continue`) will then activate and provide the stated narrow allowance.
2. **Remove or narrow `CLIENT_OWN_DOMAINS`** in the email test. Either remove it (letting the domain test's path-based skip handle the allowance) or add the same path check to the email test.
3. **Re-run `test_fixture_hygiene`** and confirm all 25 tests pass, including the two that currently fail.
4. **Update stale docstrings** in `src/casestudies.py` and `tests/test_an_offer_cannot_be_invented.py`.

The fix is small. The architecture is right. The implementation was undermined by a subsequent commit on the same branch.
