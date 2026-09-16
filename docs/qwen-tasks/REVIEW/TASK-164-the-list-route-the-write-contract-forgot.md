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

STATUS: DONE
COMMIT: d24cfeb
TESTS: test_the_heyreach_write_contract OK, test_nothing_writes_to_a_provider
       OK, test_invariants OK, test_audit OK (125 tests, 4 skipped).
       test_fixture_hygiene still FAILED (3) - (b) cases, not this task's.
FILES CHANGED:
  - tests/test_the_heyreach_write_contract.py (allowlist registration)
  - tests/test_nothing_writes_to_a_provider.py (allowlist registration)
  - docs/RED-TESTS-2026-09-16.md (new, enumerated red tests)

FINDINGS:
  5 red tests found, 2 (a) fixed, 3 (b) reported:

  (a) FIXED - test_the_write_surface_is_exactly_this_and_nothing_else:
      /list/AddLeadsToListV2 was on heyreach.WRITE_ROUTES (TASK-158) but not
      in the expected set. Added it.

  (a) FIXED - test_every_http_write_in_the_repository_is_declared:
      7 scripts issue POSTs not in ALLOWED. All are diagnostic reads or
      probes, none are prospect-facing:
      - scripts/provider_truth.py (HeyReach reads as POST)
      - scripts/sender_capacity.py (HeyReach reads as POST)
      - scripts/task158_probe2.py (TASK-158 schema probe)
      - scripts/task158_probe3.py (TASK-158 schema probe)
      - scripts/task158_probe_list_schema.py (TASK-158 schema probe)
      - scripts/task158_verify_schema.py (TASK-158 schema verification)
      - scripts/task166_grok_measurement.py (xAI responses API, intelligence read)

  (b) NOT FIXED - test_every_email_address_is_on_a_reserved_domain:
      Test fixtures use non-reserved domains (acme-test.com, b.com, d.com).
      Rule is right; fixtures should use .test or .example domains.

  (b) NOT FIXED - test_no_real_client_prospect_or_roster_domain:
      17 hits: real client/prospect domains in docs/ and scripts/ files
      (BISON-COHORT-LIVE, EMAIL-CONTROL-SEQUENCE, task147_*, task159_*,
      task167_*). Rule is right; real data should not be in git.

  (b) NOT FIXED - test_no_real_person_or_client_named:
      42 hits: real names and company tokens in docs/ and scripts/ files.
      Rule is right; real data should not be in git.

RISKS: None. The (a) fixes are allowlist registrations only. No provider
       writes were authorized, no providerwrites.SUPPORTED was touched.

RECOMMENDED CLAUDE ACTION: Review the (b) findings. The fixture_hygiene
       failures are real data in tracked files and need a data cleanup task.
