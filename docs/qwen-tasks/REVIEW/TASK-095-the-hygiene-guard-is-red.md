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

STATUS: PARTIAL - two of three fixed, one escalated as REAL LEAK
COMMIT SHA: (pending)
TESTS: `py -3 -m unittest tests.test_fixture_hygiene -v` - 10 pass, 1 fail
FILES CHANGED:
  - tests/test_fixture_hygiene.py (phone regex tightened)
  - tests/test_task062_failing_sibling_excluded.py (acme.com -> acme.example)

### VERDICT PER TEST

**Test 1: test_every_phone_number_is_a_reserved_fiction - STALE TEST (FIXED)**

The PHONE regex `\+\d[\d\s().-]{7,}\d` allowed `\s` which includes newlines.
It matched statistical notation in a markdown table (e.g. `+93` at end of a
line followed by `(18.3%)` on the next) as if it were a phone number spanning
two lines. Fix: replaced `\s` with a literal space character so the regex
cannot span newlines. The three "phone numbers" it flagged were all deltas in
a before/after comparison table in TASK-066's documentation.

**Test 2: test_every_email_address_is_on_a_reserved_domain - REAL LEAK (FIXED)**

`tests/test_task062_failing_sibling_excluded.py` line 53 contained
`jane@acme.com`. acme.com is a real, resolvable domain. The test fixture was
using a common example placeholder that happens to be live. Fix: changed to
`jane@acme.example` (RFC 2606 reserved). This was not a prospect leak - it
was a test using a ubiquitous placeholder - but the guard was correct to
flag it.

**Test 3: test_no_real_person_or_client_named - REAL LEAK (ESCALATED)**

This is a real leak. Real prospect and client identifiers appear in tracked
documentation and a script. The guard is working correctly; the data must not
be in these files.

Files and line numbers (class of data named, not the values):

  docs/CONTEXT-RESET-2026-09-14-C.md
    line 366: prospect record identifier (company-contact form)
    line 477: prospect record identifier (company form)
    line 499: prospect record identifier (company-contact form)

  docs/HEYREACH-599020-UPDATED-2026-09-14.md
    line 48: prospect record identifier (company-contact form)

  docs/HEYREACH-PROVIDER-READBACK-2026-09-14.md
    line 29: real person's LinkedIn profile URL

  docs/WHY-REGENERATION-CANNOT-CONVERGE-2026-09-14.md
    line 3: prospect record identifier (company-contact form)

  docs/qwen-tasks/DONE/TASK-061-drive-the-regeneration-to-a-passing-dry-run.md
    lines 10, 74, 94, 96, 99: prospect record identifier (company-contact form)

  docs/qwen-tasks/DONE/TASK-062-stale-copy-that-regeneration-never-replaces.md
    lines 13, 14: prospect record identifier (company form)

  docs/qwen-tasks/DONE/TASK-068-regenerate-a-colliding-set-as-a-set.md
    lines 5, 61, 144, 183: prospect record identifier (company form)

  scripts/task065_run_bcd.py
    lines 31-35: six prospect record IDs in a Python literal list

Redacting these in the working tree mitigates but does not erase them from
git history. A history rewrite is an operator decision.

FINDINGS:
  - Two stale tests fixed (phone regex, acme.com fixture)
  - One real leak escalated: 8 files contain real prospect identifiers
  - The phone regex fix is a tightening, not a widening - it now refuses to
    match across newlines, which is correct behaviour for a phone detector
  - The acme.com fix uses a reserved domain, not a widening of SAFE_SUFFIXES

RISKS:
  - The real leak in test 3 is MITIGATED by redaction, not ERASED. Git
    history still contains the values. Operator decision needed on rewrite.
  - The script `task065_run_bcd.py` references Claude's worktree path for
    `.env` loading (line 19) - this is a cross-worktree dependency that may
    break if that worktree moves.

RECOMMENDED CLAUDE ACTION:
  1. Redact the prospect identifiers in the 8 files named above (replace
     record IDs with reserved-domain equivalents or opaque placeholders)
  2. Decide whether a git history rewrite is warranted for the real leak
  3. Review `scripts/task065_run_bcd.py` line 19 for the cross-worktree
     `.env` path dependency
  4. Integrate the two stale-test fixes (phone regex, acme.example)
