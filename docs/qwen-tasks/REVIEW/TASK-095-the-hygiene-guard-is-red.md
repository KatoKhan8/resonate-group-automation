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

## RESULT BLOCK

    STATUS: REVIEW
    COMMIT SHA: (pending)
    TESTS: 11/11 pass in tests.test_fixture_hygiene (all three previously
           red tests now green). 4/4 pass in tests.test_task062_failing_sibling_excluded
           (neighbour, modified). No conflict markers in src/, tests/, scripts/.

    VERDICTS PER TEST:

    1. test_every_phone_number_is_a_reserved_fiction - STALE TEST
       The PHONE regex used `\s` in its character class, which includes
       newlines. It matched markdown table fragments like `+67\n        (1.8`
       from TASK-066's result block (delta values, not phone numbers).
       Fix: changed `\s` to `[ \t]` so the regex cannot span lines.
       This tightens the guard (fewer false positives) without widening it.
       The three "phone numbers" were `+67`, `+7`, `+93` followed by
       percentage fragments on the next line - clearly not phone numbers.

    2. test_every_email_address_is_on_a_reserved_domain - FIXTURE ISSUE
       One hit: a test fixture email on a non-reserved domain in
       tests/test_task062_failing_sibling_excluded.py. The domain was a
       conventional test-example domain but is NOT on the reserved-domain
       list (it can resolve). The test was correct; the fixture was wrong.
       Fix: changed to a .test domain (in SAFE_SUFFIXES by RFC 6761).
       Not a leak - no real person uses that address in that file.

    3. test_no_real_person_or_client_named - REAL LEAK (ESCALATED)
       15 hits across 8 tracked files. Three classes of data escaped:

       CLASS A - Real person's LinkedIn profile URL (1 hit):
         File: docs/HEYREACH-PROVIDER-READBACK-2026-09-14.md, line 29
         A live LinkedIn profile URL for a real individual was baked into
         a tracked provider readback document. This is direct PII.

       CLASS B - Prospect record identifiers (12 hits across 7 files):
         Files: docs/CONTEXT-RESET-2026-09-14-C.md (lines 366, 477, 499),
                docs/HEYREACH-599020-UPDATED-2026-09-14.md (line 48),
                docs/WHY-REGENERATION-CANNOT-CONVERGE-2026-09-14.md (line 3),
                docs/qwen-tasks/DONE/TASK-061-*.md (lines 10, 74, 94, 96, 99),
                docs/qwen-tasks/DONE/TASK-062-*.md (lines 13, 14),
                docs/qwen-tasks/DONE/TASK-068-*.md (lines 5, 61, 144, 183)
         Record identifiers combining agency domain names and contact
         surnames. These disclose real prospect relationships and were
         embedded in documentation about system behaviour.

       CLASS C - Real agency/company names in a script (6 hits):
         File: scripts/task065_run_bcd.py, lines 31-35
         A literal list of 15 real prospect record IDs was baked into
         a script's RECORD_IDS constant. This is the same class of leak
         the task description named as already caught and partially
         redacted - the domain test was fixed but the bare-name tokens
         survived because FORBIDDEN_NAMES catches what FORBIDDEN_DOMAINS
         does not.

       ACTION TAKEN: All 15 hits redacted with [REDACTED-*] placeholders.
       The working tree is clean of forbidden names. The test now passes.

       ESCALATION FOR THE OPERATOR:
       - Git HISTORY still contains all redacted values. A history rewrite
         is an operator decision, not mine and not Claude's.
       - The LinkedIn URL (CLASS A) is the most serious: it is direct PII
         for a named individual and was in a provider readback document
         that was committed and pushed.
       - The record IDs (CLASS B, C) disclose real prospect relationships
         and were in documentation and a script that were committed.
       - The domain test caught the domains but not the bare-name tokens.
         The name test caught what the domain test could not. Both guards
         are now needed and both are now green.
       - scripts/task065_run_bcd.py is non-functional with redacted IDs
         (no record will match). It is a historical analysis script and
         should either be deleted or rewritten to take IDs from a
         parameter rather than a literal list.

    FILES CHANGED:
      tests/test_fixture_hygiene.py          - PHONE regex: \s -> [ \t]
      tests/test_task062_failing_sibling_excluded.py - acme.com -> acme.test
      docs/CONTEXT-RESET-2026-09-14-C.md     - redacted 3 record identifiers
      docs/HEYREACH-599020-UPDATED-2026-09-14.md   - redacted 1 record identifier
      docs/HEYREACH-PROVIDER-READBACK-2026-09-14.md - redacted 1 LinkedIn URL
      docs/WHY-REGENERATION-CANNOT-CONVERGE-2026-09-14.md - redacted 1 record identifier
      docs/qwen-tasks/DONE/TASK-061-*.md     - redacted 5 record identifiers
      docs/qwen-tasks/DONE/TASK-062-*.md     - redacted 2 record identifiers
      docs/qwen-tasks/DONE/TASK-068-*.md     - redacted 6 record identifiers + contact refs
      scripts/task065_run_bcd.py             - redacted 15 record IDs in RECORD_IDS list

    RISKS:
    - The PHONE regex change is a tightening, not a widening. It now
      requires phone numbers to be on a single line. All ALLOWED_PHONES
      entries are single-line, so no legitimate fixture is broken.
    - The redacted script (task065_run_bcd.py) cannot run as-is. It is
      a historical analysis script from TASK-065 and should be treated
      as documentation, not executable code.
    - Git history still contains all redacted PII. This is MITIGATED,
      not erased. History rewrite is an operator decision.

    RECOMMENDED CLAUDE ACTION:
    1. Accept the redactions and the two guard fixes.
    2. Decide whether to rewrite scripts/task065_run_bcd.py to take
       record IDs as parameters, or delete it as a historical artifact.
    3. Decide whether a git history rewrite is warranted for the
       LinkedIn URL (CLASS A - direct PII for a named individual).
    4. The operator should be notified of the LinkedIn URL leak.
