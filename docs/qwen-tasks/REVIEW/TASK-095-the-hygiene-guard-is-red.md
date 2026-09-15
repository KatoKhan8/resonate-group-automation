# TASK-095 - the fixture-hygiene guard is red, and it is the PII guard

## THE THREE RED TESTS

Split out of TASK-088 because they guard something different from the rest.

    tests.test_fixture_hygiene
      TestKnownSets.test_every_phone_number_is_a_reserved_fiction      FAIL
      TestNoRealDataAnywhereInGit.test_every_email_address_is_on_a_reserved_domain
      TestNoRealDataAnywhereInGit.test_no_real_person_or_client_named  FAIL

All three were red in the FIRST full-suite run, so none was caused by the
2026-09-14/15 work. They are pre-existing, verified present at `a519954`.

## WHY THIS ONE MATTERS MORE THAN ITS COUNT SUGGESTS

This is the guard that stops real prospect data entering tracked files. It
has already caught a real leak this estate produced: four documents and
`scripts/task065_run_bcd.py`, which had fifteen real prospect domains baked
into a literal list. Those were redacted and
`test_no_real_client_prospect_or_roster_domain` passes now.

**A red hygiene guard is indistinguishable from an absent one.** While these
three fail, nobody can tell a new leak from the standing noise - which is
precisely how the last one survived.

## WHAT TO DETERMINE, PER TEST

For each of the three, answer the question this repository got right on the
tenancy tests and had to be forced to ask:

**Is this a STALE TEST, or a REAL LEAK?**

TASK-086 found three tenancy failures that looked like leaks and were stale
tests - production had got STRICTER and nobody updated them. The fix there
was ZERO production changes. But the same session found a REAL safety
regression hiding in the same red set. Both answers are live. Check, do not
assume, and **if any of the three is a real leak, STOP and write it up rather
than redacting quietly** - the operator needs to know what escaped and where.

Note the distinction that cost two wrong probes last time: a guard that
reports by RETURN VALUE and a guard that is ABSENT look identical from the
outside if you only watch for exceptions.

## WHAT NOT TO DO

- **Do not widen the guard** to make it pass. A reserved-domain list that
  admits a real domain is not a guard. This is the same move as widening a
  quality gate, which has been measured and rejected twice.
- **Do not put the real value in the task file, the commit message or the
  report** while proving a leak exists. Name the FILE and the LINE and say
  what CLASS of data it is. That is enough to act on.
- Remember that redaction fixes the working tree only. Anything already
  committed remains in git HISTORY, so a real leak is MITIGATED, not erased,
  and a history rewrite is an operator decision - not yours and not Claude's.
- Two module names that DO NOT EXIST and keep getting written into tasks:
  `tests/test_accountpolicy.py` (it is `test_account_policy.py`) and
  `tests/test_inbound_classification.py`. Check a name before using it.

## DELIVERABLE

A verdict per test - STALE TEST or REAL LEAK - with the evidence for each,
the fix for the stale ones, and a written escalation for any real one. Run
the neighbours, not just the three. Read every exit code off the process,
never through a pipe - a pipe reports the filter's status.

## RESULT

**STATUS:** DONE - two stale tests fixed, one real leak escalated

**COMMIT SHA:** ad78c25

**TESTS:**
- `tests.test_fixture_hygiene` - 10/11 PASS, 1 FAIL (the real leak)
- `tests.test_task062_failing_sibling_excluded` - 4/4 PASS (neighbour, verified after fixture change)

**VERDICTS PER TEST:**

### 1. test_every_phone_number_is_a_reserved_fiction - STALE TEST

**Evidence:** The PHONE regex `\+\d[\d\s().-]{7,}\d` matched statistical
deltas in a markdown table, not phone numbers. The table in
`docs/qwen-tasks/DONE/TASK-066-the-classifier-cannot-read-linkedin.md` has
lines like `+93` (a count delta) followed by `(18.3%)` on the next line. The
`\s` in the character class matches newlines, so the regex combined `+93`
with `(18.3` across lines into a false "phone number."

**Fix:** Changed `[\d\s().-]` to `[\d \t().-]` in the PHONE regex. Phone
numbers do not span multiple lines; horizontal whitespace only.

**File changed:** `tests/test_fixture_hygiene.py` line 108

### 2. test_every_email_address_is_on_a_reserved_domain - STALE TEST

**Evidence:** `tests/test_task062_failing_sibling_excluded.py` used
`jane@acme.com` as a test fixture. `acme.com` is not in SAFE_SUFFIXES and is
a real domain. The test fixture should use a reserved domain.

**Fix:** Changed `jane@acme.com` to `jane@acme.example` in the test fixture.

**File changed:** `tests/test_task062_failing_sibling_excluded.py` line 88

### 3. test_no_real_person_or_client_named - REAL LEAK

**Class of data:** Forbidden names (prospect/client names and person names)
from FORBIDDEN_NAMES in `tests/test_fixture_hygiene.py`.

**Files and lines (24 hits across 10 files):**

Documentation files (18 hits):
- `docs/CONTEXT-RESET-2026-09-14-C.md` lines 366, 477, 499
- `docs/HEYREACH-599020-UPDATED-2026-09-14.md` line 48
- `docs/HEYREACH-PROVIDER-READBACK-2026-09-14.md` line 29 (2 hits)
- `docs/WHY-REGENERATION-CANNOT-CONVERGE-2026-09-14.md` line 3
- `docs/qwen-tasks/DONE/TASK-061-drive-the-regeneration-to-a-passing-dry-run.md` lines 10, 74, 94, 96, 99
- `docs/qwen-tasks/DONE/TASK-062-stale-copy-that-regeneration-never-replaces.md` lines 13, 14
- `docs/qwen-tasks/DONE/TASK-068-regenerate-a-colliding-set-as-a-set.md` lines 5, 61, 144, 183

Script file (6 hits):
- `scripts/task065_run_bcd.py` lines 31, 32, 33 (2 hits), 34, 35

**Escalation:** This is a real leak. Forbidden names appear in tracked
documentation and a tracked script. The documentation files are historical
context and task records; the script has record IDs that embed client/prospect
names as identifiers. Redaction is an operator decision - git history retains
the values even if HEAD is cleaned. The operator must decide whether to
redact, whether to rewrite history, and whether the script's record IDs need
structural change rather than string replacement.

**FILES CHANGED:**
- `tests/test_fixture_hygiene.py` - PHONE regex fix (stale test)
- `tests/test_task062_failing_sibling_excluded.py` - fixture domain fix (stale test)

**FINDINGS:**
- Two of three red tests were stale tests (regex false positive, test fixture
  using non-reserved domain). Both fixed.
- One is a real leak: forbidden names in 10 tracked files. Not redacted
  quietly per task instructions. Operator escalation required.
- The guard itself is sound - it correctly identified the leak. No widening
  applied.

**RISKS:**
- The real leak remains in git history even if redacted from HEAD. History
  rewrite is an operator decision.
- The script `scripts/task065_run_bcd.py` has record IDs that embed names;
  structural change may be needed rather than string replacement.

**RECOMMENDED CLAUDE ACTION:**
- Review the escalation and decide on redaction scope.
- Decide whether git history rewrite is warranted.
- Decide whether `scripts/task065_run_bcd.py` needs structural change to
  remove name-bearing record IDs.
- After redaction (if approved), re-run `tests.test_fixture_hygiene` to
  confirm all 11 tests pass.
