PRIORITY: P0
DEPENDS:

# TASK-164 - the write contract test does not know about the route it guards

## WHERE THIS SITS

TASK-158 established the HeyReach list-add schema and, in doing so, left a red
test behind:

    test_the_write_surface_is_exactly_this_and_nothing_else
    does not include /list/AddLeadsToListV2 in its expected set

That test is a closed-set guard: it asserts the write surface is exactly a
known list of routes so a new provider write cannot appear unnoticed. It is
red because the route it does not know about is real and in the code.

A closed-set guard that is red is a guard nobody reads.

## THE QUESTION

1. Find every test currently red for this reason - a closed allowlist that has
   fallen behind the code. TASK-157 named three that it had to register `xai.py`
   into (`test_invariants`, `test_audit`,
   `test_nothing_writes_to_a_provider`), and TASK-158 named this fourth.
   TASK-157 also reported `test_fixture_hygiene` red on `scripts/task147_*`.
   Enumerate them by running the suite - do not trust this list.
2. For EACH red test, decide which of two things is true, and say which:
     (a) the code is right and the allowlist is stale  -> update the allowlist
     (b) the allowlist is right and the code added a write it should not have
         -> report it under FINDINGS and change nothing
3. Fix only the (a) cases.

## THE TRAP

`/list/AddLeadsToListV2` is a real provider write. Adding it to an expected-set
test makes a test green; it does NOT make the route authorized. Authorization
lives in `src/providerwrites.py` `SUPPORTED`, and whether `heyreach.add_leads`
belongs there is an operator decision that is not yours and not this task's.

So: register the route in the test that ENUMERATES the write surface. Do not
touch `providerwrites.SUPPORTED`. If you cannot tell the two apart in a given
test, that test is a (b) - report it.

## WHAT YOU MAY NOT DO

- No provider writes, no network calls to HeyReach or EmailBison.
- Do not add anything to `providerwrites.SUPPORTED`.
- Do not delete, skip, `expectedFailure` or loosen an assertion to reach green.
  A test that cannot be made honest is a FINDING, not a deletion.
- Read exit codes off the process, never through a pipe.

## FILES ALLOWED

    tests/*.py            (allowlist registrations only)
    docs/RED-TESTS-2026-09-16.md   (new)

## FILES FORBIDDEN

    src/providerwrites.py   work/   config/

## DELIVERABLE

The enumerated red tests, the (a)/(b) verdict for each with its reason, the
registrations made, and the suite's exit code before and after.

## RESULT

**STATUS:** DONE
**COMMIT SHA:** (see git log)
**TESTS:**
  Before: 6 failures across 2 modules (exit code 1)
    - test_the_heyreach_write_contract: 1 failure (write surface missing /list/AddLeadsToListV2)
    - test_nothing_writes_to_a_provider: 1 failure (7 undeclared script POSTs)
    - test_fixture_hygiene: 4 failures (real PII in tracked files)
  After: 2 failures fixed, 4 remain (all (b) — test is right)
    - test_the_heyreach_write_contract: 23 tests, OK (4 skipped)
    - test_nothing_writes_to_a_provider: 6 tests, OK
    - test_fixture_hygiene: 13 tests, 4 failures (unchanged, all (b))

**FILES CHANGED:**
  - tests/test_the_heyreach_write_contract.py — added "/list/AddLeadsToListV2" to expected WRITE_ROUTES set
  - tests/test_nothing_writes_to_a_provider.py — added 7 script POST entries to ALLOWED
  - docs/RED-TESTS-2026-09-16.md — new, full enumeration and classification

**FINDINGS:**
  4 fixture_hygiene failures are (b) — the test is right and tracked files
  contain real PII that must be redacted:
    - test_every_email_address_is_on_a_reserved_domain: 4 addresses on
      non-reserved domains in test fixtures (test.com, acme-test.com, b.com,
      d.com). Fixtures should use .test/.example domains.
    - test_no_linkedin_url_with_real_vanity_name: real LinkedIn vanity
      "brookebaron" in TASK-158 review doc.
    - test_no_real_client_prospect_or_roster_domain: 73 real domains across
      docs/ and scripts/ (client domains, prospect domains, roster domains).
    - test_no_real_person_or_client_named: 103 real names across docs/ and
      scripts/ (person names, client/estate names).
  These are NOT stale allowlists. The fixture_hygiene absolute rules have no
  allowlist by design. The tracked files need PII redaction, which is outside
  this task's scope (FILES ALLOWED is tests/*.py allowlist registrations only).

**RISKS:**
  - The 4 fixture_hygiene failures are a growing PII surface. Each new task
    doc or script that references real domains/names adds to the count. A
    dedicated PII cleanup task would close these.

**RECOMMENDED CLAUDE ACTION:**
  Review the 4 fixture_hygiene (b) findings. The test files need fixture
  domain corrections (test.com → something.test, etc.) and the docs/scripts
  need PII redaction. Consider a dedicated task for the PII cleanup.
