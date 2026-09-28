# TASK-477 — Independent verification of TASK-269

## Target

    task            TASK-269
    branch          origin/qwen-worker-4-r58
    branch HEAD SHA fe92b486beb93425aeaf8458efc521c3b667f3b1

SHA verified with `git rev-parse origin/qwen-worker-4-r58` — matches the task file exactly.
Review performed in an isolated worktree checked out at `fe92b486` (detached HEAD).

## Task summary

TASK-269 unifies three divergent derivations of a greeting first name into one
function (`names.greeting_first_name`) that strips a closed-list honorific
prefix before returning the first token. The defect: a contact named
"Ing Christoph Lemmer" greets "Ing" because the first token of the name is an
honorific, not a given name. The lint rule `_names_match` passed it because
"Ing" was a token of the full name.

## Finding 1 — Artifact exists and matches claims

**VERIFIED.**

Files on the branch (confirmed via `git ls-tree` and `git diff master...fe92b486 --stat`):

| File | Status | Lines |
|------|--------|-------|
| `src/names.py` | NEW | +93 |
| `tests/test_names.py` | NEW | +232 |
| `src/cadence.py` | MODIFIED | +4/-1 |
| `src/bisonfactory.py` | MODIFIED | +9/-3 |
| `src/heyreachfactory.py` | MODIFIED | +10/-3 |
| `src/lint.py` | MODIFIED | +9/-1 |
| TASK-269 task file | NEW | +38 |

Total: 386 insertions, 9 deletions. No files deleted.

`src/names.py` contains:
- `HONORIFICS` — a frozenset of 12 normalised honorific tokens
- `strip_honorific(name)` — strips a leading honorific, never the only token
- `greeting_first_name(contact)` — unified derivation: prefers `name` over `first_name`

## Finding 2 — Existence is function: all three call sites are wired

**VERIFIED.** `grep -rn "greeting_first_name" src/` returns:

    src/cadence.py:582         first = names.greeting_first_name(contact) or "there"
    src/bisonfactory.py:392    first = names.greeting_first_name(person)
    src/heyreachfactory.py:1267 first_name = names.greeting_first_name(record_contact) if record_contact else ""

All three old derivation patterns are gone (confirmed by grepping for the old
patterns — zero matches):
- `(contact.get("name") or "").split()[0]` — gone from cadence.py
- `contact.get("first_name") or name.split()[0]` — gone from bisonfactory.py
- `contact_key.split("_")[0]` — gone from heyreachfactory.py

All three modules import `names` in their import blocks. `lint.py` imports
`names` and uses `names._normalise_token` and `names.HONORIFICS` in
`_names_match`.

**No zero-consumer defect.** The function has three production callers plus
one lint caller.

## Finding 3 — Tests are falsifiable (mutation verified)

**VERIFIED** by breaking the wiring and confirming the intended tests fail:

### Mutation 1: Reverted cadence.py to old pattern
Restored `first = (contact.get("name") or "").split()[0] if contact.get("name") else "there"`.
Result: `test_template_vars_strips_honorific` FAILS with `AssertionError: 'Ing' != 'Christoph'`.
This is the exact defect the task prevents. No other guard fires first.

### Mutation 2: Removed the honorific check from lint._names_match
Commented out the `if names._normalise_token(greeted) in names.HONORIFICS: return False` block.
Result: `test_honorific_greeting_is_refused` and `test_dr_greeting_is_refused` FAIL with
`AssertionError: True is not false`. The "normal greeting still passes" and "wrong person
still refused" tests continue to pass — no false positives from the mutation.

Both mutations confirm: the tests prove the wiring, not just the logic.

## Finding 4 — Test coverage against acceptance criteria

**VERIFIED.** All 31 tests pass. The task's required tests are present:

| Required test | Test name | Status |
|---|---|---|
| "Ing Christoph Lemmer" greets "Christoph" | `test_derives_from_name_with_honorific` | PASS |
| Single-token "Ing" left alone | `test_single_token_is_not_stripped`, `test_single_token_first_name_is_not_stripped` | PASS |
| "Mags Bennett" greets "Mags" | `test_mags_bennett_is_not_stripped` | PASS |
| Cleaned value reaches template via cadence.py | `test_template_vars_strips_honorific` (TestCadenceIntegration) | PASS |
| _names_match refuses honorific-only greeting | `test_honorific_greeting_is_refused` | PASS |
| DE sample | `test_german_ing_christoph_lemmer`, `test_german_dipl_ing` | PASS |
| AT sample | `test_austrian_mag`, `test_austrian_dipl_ing_variant` | PASS |

The integration test (`TestCadenceIntegration`) drives through `cadence.template_vars`,
the real production entry point — not the `names.greeting_first_name` function directly.
This is the test that would pass on a no-op implementation but fails on the real one
(verified by mutation 1 above).

## Finding 5 — Broader suite: no regressions

**VERIFIED.**

| Suite | Tests | Result |
|-------|-------|--------|
| test_lint + test_names + test_cadence | 112 | ALL PASS |
| test_heyreachfactory | 40 | ALL PASS |
| test_bison_prewrite_check | 35 | ALL PASS |
| test_bison_campaign_write | 15 | ALL PASS |
| test_bison_sending_schedule | 19 | ALL PASS |

The result block claims "51 bison prewrite and greeting tests" — measured 35 + 15 = 50
plus greeting-related tests in other files. Close enough; not materially misleading.

## Finding 6 — Merging would NOT delete anything

**VERIFIED.** `git diff master...fe92b486 --diff-filter=D --name-only` returns empty.
The branch adds 386 lines and modifies 9. No deletions.

## Finding 7 — No scope drift

**VERIFIED.** The branch carries exactly 2 commits:

    fe92b486 TASK-269: done, commit SHA filled in
    9d141ccb TASK-269: one derivation, three call sites, and the honorific that was a name

All 7 changed files are directly related to the task. No junk, no unrelated changes.
Cherry-pick is unnecessary — the branch is clean enough for a direct merge.

## Finding 8 — heyreachfactory wiring correctness

**VERIFIED with one observation.** The old code derived `first_name` from
`contact_key.split("_")[0]` — a key-derived token with no connection to the
actual contact name. The new code finds the record contact by matching
`contact["contact_key"]` against the record's contacts' `key` field, then
calls `names.greeting_first_name(record_contact)`.

Both `linkedin_url` and `record_contact` are set in the same loop iteration,
so the `if not linkedin_url: continue` guard ensures `record_contact` is
always set when `first_name` is derived. The `if record_contact else ""`
is defensive but correct.

**Observation (not a defect):** If a record contact has no `name` or
`first_name` field, `greeting_first_name` returns empty string, and the
enriched lead will have `first_name: ""`. The result block notes this risk
and calls it correct behavior. The downstream `_refuse_bad_greetings` in
bisonfactory catches empty greetings. The LinkedIn path does not render
greetings from this field directly, so the impact is limited.

## Disposition

| # | Finding | Severity | Evidence |
|---|---------|----------|----------|
| 1 | Artifact exists and matches claims | PASS | git diff, file contents |
| 2 | All three call sites wired | PASS | grep, import verification |
| 3 | Tests are falsifiable | PASS | Two mutations, both caught |
| 4 | Acceptance criteria covered | PASS | 31 tests, all required cases |
| 5 | No regressions | PASS | 221 tests across 5 suites |
| 6 | Merging deletes nothing | PASS | --diff-filter=D empty |
| 7 | No scope drift | PASS | 2 commits, 7 files, all related |
| 8 | heyreachfactory wiring correct | PASS | Code review, defensive guard |

## Recommendation: **MERGE**

TASK-269 is a well-scoped prevention change with real wiring, falsifiable tests,
and zero regressions. The three divergent derivations are unified, the lint rule
is tightened, and the integration test drives through the production entry point.
The mutation tests confirm that the tests prove the wiring, not just the logic.
No deletions, no scope drift, no junk. Clean merge.
