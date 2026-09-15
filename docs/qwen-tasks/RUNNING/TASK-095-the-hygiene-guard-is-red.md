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

---

## FINDINGS - 2026-09-15

### Verdict per test

**Test 1: test_every_phone_number_is_a_reserved_fiction** - STALE TEST

The PHONE regex `\+\d[\d\s().-]{7,}\d` allowed `\s` which includes `\n`, so it
matched across line boundaries in a markdown table. The file
`docs/qwen-tasks/DONE/TASK-066-the-classifier-cannot-read-linkedin.md` has a
comparison table with delta values like `+93`, `+7`, `+67` (statistical
changes, not phone numbers). The regex matched `+93` then continued across
newlines into the next line's percentage `(18.3`, producing the false hit
`+93\n        (18.3`. Same for the other two.

**Fix:** Changed regex from `\+\d[\d\s().-]{7,}\d` to `\+\d[\d \t().-]{7,}\d`.
This allows horizontal whitespace (spaces, tabs) for formatted numbers like
`+44 20 7000 0000` but prevents cross-line matching. Test now passes.

**Test 2: test_every_email_address_is_on_a_reserved_domain** - STALE TEST

`tests/test_task062_failing_sibling_excluded.py` used a non-reserved domain in
test fixture data. The domain is commonly used as a fictitious example in
documentation but is a real resolvable domain and the guard correctly flags
it.

**Fix:** Changed test fixture to use a reserved domain (`.example` suffix).
Test now passes.

**Test 3: test_no_real_person_or_client_named** - REAL LEAK

Real prospect and person names appear in tracked files. This is not a stale
test - the guard is working as designed and catching data that should not be
in git.

**Escalation - operator decision required:**

Real names in the following tracked files (file paths and name classes only,
not the values themselves):

- `docs/CONTEXT-RESET-2026-09-14-C.md` - two prospect company names
- `docs/HEYREACH-599020-UPDATED-2026-09-14.md` - one prospect company name
- `docs/HEYREACH-PROVIDER-READBACK-2026-09-14.md` - one person name (appears
  twice, once as a LinkedIn URL path segment)
- `docs/WHY-REGENERATION-CANNOT-CONVERGE-2026-09-14.md` - one prospect
  company name
- `docs/qwen-tasks/DONE/TASK-061-drive-the-regeneration-to-a-passing-dry-run.md`
  - one prospect company name (appears multiple times)
- `docs/qwen-tasks/DONE/TASK-062-stale-copy-that-regeneration-never-replaces.md`
  - one prospect company name
- `docs/qwen-tasks/DONE/TASK-068-regenerate-a-colliding-set-as-a-set.md` -
  one prospect company name (appears multiple times)
- `scripts/task065_run_bcd.py` - six prospect company names in a RECORD_IDS
  list

These are historical documentation and a script that embeds record IDs. The
names were committed before the guard was enforced or before it caught them.
Redaction fixes the working tree but the names remain in git history. A
history rewrite is an operator decision.

**Recommendation:** Redact the working tree to silence the guard and prevent
future pushes from carrying these names. Document the history exposure for
operator decision. The script's RECORD_IDS list should be replaced with
opaque identifiers or removed if the script is no longer needed.

### Test execution

Ran the three failing tests plus their neighbours in
`tests.test_fixture_hygiene`:

    test_every_phone_number_is_a_reserved_fiction          PASS (after fix)
    test_every_email_address_is_on_a_reserved_domain       PASS (after fix)
    test_no_real_person_or_client_named                    FAIL (real leak)
    test_no_real_client_prospect_or_roster_domain          PASS
    test_no_live_account_figures                           PASS
    test_no_crm_narrative_about_a_real_account             PASS
    test_the_tracked_template_holds_only_reserved_domains  PASS
    test_the_real_roster_is_not_tracked                    PASS
    test_the_real_roster_is_ignored_...                    PASS
    test_no_env_file_is_tracked                            PASS
    test_no_runtime_state_directory_is_tracked             PASS

Exit code read from process: 1 (one failure remains - the real leak).

### Files changed

- `tests/test_fixture_hygiene.py` - PHONE regex tightened to exclude newlines
- `tests/test_task062_failing_sibling_excluded.py` - test fixture domain
  changed from acme.com to acme.example

### RESULT BLOCK

STATUS: PARTIAL - two stale tests fixed, one real leak escalated
COMMIT SHA: pending
TESTS: 10 pass, 1 fail (the real leak - test working as designed)
FILES CHANGED: tests/test_fixture_hygiene.py, tests/test_task062_failing_sibling_excluded.py
FINDINGS: See escalation above. Real prospect and person names in 8 tracked files.
RISKS: Redaction fixes working tree only; names remain in git history.
RECOMMENDED CLAUDE ACTION: Operator decision on history rewrite. Redact working tree to silence guard.
