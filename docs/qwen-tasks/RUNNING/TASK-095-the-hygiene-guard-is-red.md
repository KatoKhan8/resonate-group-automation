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

## RESULT

**STATUS:** DONE - two stale tests fixed, one real leak escalated

**COMMIT SHA:** (pending - stale test fixes committed, real leak NOT redacted)

**TESTS:**
- `test_every_phone_number_is_a_reserved_fiction` - **STALE TEST, FIXED**
- `test_every_email_address_is_on_a_reserved_domain` - **STALE TEST, FIXED**
- `test_no_real_person_or_client_named` - **REAL LEAK, ESCALATED BELOW**

**FILES CHANGED:**
- `tests/test_fixture_hygiene.py` - tightened PHONE regex to avoid matching statistical data
- `tests/test_task062_failing_sibling_excluded.py` - changed acme.com to example.com

**FINDINGS:**

### Test 1: test_every_phone_number_is_a_reserved_fiction - STALE TEST

**Verdict:** STALE TEST

**Evidence:** The PHONE regex `\+\d[\d\s().-]{7,}\d` was matching statistical percentages and decimal numbers in markdown reports:
- `docs/qwen-tasks/DONE/TASK-066-*.md` lines with `+67`, `+7`, `+93` followed by percentages like `(1.8`, `(3.4`, `(18.3`
- `FLIGHT-REPORT-2026-09-10.md` with `+0.664858` (a correlation coefficient)

These are NOT phone numbers. The regex was too greedy and matched across newlines and decimal points.

**Fix:** Tightened regex to `\+[1-9]\d{0,2}[\d \t().-]{5,17}\d`:
- Requires country code to start with 1-9 (not 0, which eliminates `+0.664858`)
- Uses `[ \t]` not `\s` so it cannot span newlines (eliminates the markdown table matches)
- Still matches all five ALLOWED_PHONES entries

**Test result after fix:** PASS

---

### Test 2: test_every_email_address_is_on_a_reserved_domain - STALE TEST

**Verdict:** STALE TEST

**Evidence:** One hit at `tests/test_task062_failing_sibling_excluded.py` with a non-reserved test domain. The test file uses a test email address with a classic test domain that is NOT in SAFE_SUFFIXES.

**Fix:** Changed the test email to use `example.com` (which IS in SAFE_SUFFIXES).

**Test result after fix:** PASS

---

### Test 3: test_no_real_person_or_client_named - REAL LEAK

**Verdict:** **REAL LEAK - DO NOT REDACT QUIETLY**

**Evidence:** 15 hits across 8 tracked files, all from 2026-09-14 or earlier. These are real prospect record IDs, real prospect names, and a real LinkedIn profile URL.

**Files and line numbers (values NOT shown - operator must inspect):**

1. **docs/CONTEXT-RESET-2026-09-14-C.md** - lines 366, 477, 499
   - Class: prospect record IDs and names in operator documentation

2. **docs/HEYREACH-599020-UPDATED-2026-09-14.md** - line 48
   - Class: prospect record ID and name in provider readback

3. **docs/HEYREACH-PROVIDER-READBACK-2026-09-14.md** - line 29
   - Class: **real LinkedIn profile URL and seat number** in provider readback

4. **docs/WHY-REGENERATION-CANNOT-CONVERGE-2026-09-14.md** - line 3
   - Class: prospect record ID and name in analysis document

5. **docs/qwen-tasks/DONE/TASK-061-drive-the-regeneration-to-a-passing-dry-run.md** - lines 10, 74, 96, 99
   - Class: prospect record IDs and names in completed task file

6. **docs/qwen-tasks/DONE/TASK-062-stale-copy-that-regeneration-never-replaces.md** - lines 13, 14
   - Class: prospect record IDs in completed task file

7. **docs/qwen-tasks/DONE/TASK-068-regenerate-a-colliding-set-as-a-set.md** - lines 5, 61, 144, 183
   - Class: prospect record IDs and names in completed task file, plus live generation commands

8. **scripts/task065_run_bcd.py** - lines 31-35
   - Class: **list of 15 real prospect record IDs** in a RECORD_IDS literal

**What class of data:**
- Prospect record IDs (format: `domain-com` or `domain-com/contact-name`)
- Prospect contact names
- One real LinkedIn profile URL
- One real HeyReach seat number

**Why this matters:**
QWEN.md says `scripts/task065_run_bcd.py` "had fifteen real prospect domains baked into a literal list. Those were redacted." **They were not fully redacted.** The record IDs are still present at lines 31-35. The other seven docs/ files are operator documentation from 2026-09-14 that were committed with real prospect data still in them.

**What I did NOT do:**
- I did NOT redact these values. The task says "if any of the three is a real leak, STOP and write it up rather than redacting quietly - the operator needs to know what escaped and where."
- I did NOT put the actual values in this task file or the commit message.
- I did NOT attempt a git history rewrite. That is an operator decision.

**What the operator must decide:**
1. Whether to redact the working tree (mitigates, does not erase from git history)
2. Whether a git history rewrite is warranted (operator decision, not mine)
3. How the real data entered tracked files on 2026-09-14 despite the guard

**RISKS:**
- The redaction of `scripts/task065_run_bcd.py` mentioned in QWEN.md was incomplete
- Real prospect data has been in git history since 2026-09-14 or earlier
- A red working tree fix does not erase committed history

**RECOMMENDED CLAUDE ACTION:**
1. Inspect the 8 files at the line numbers above
2. Decide on redaction vs. history rewrite
3. Investigate how the data entered tracked files despite the guard (the guard was red on 2026-09-14, which is indistinguishable from absent)
4. Consider whether the operator who committed these files on 2026-09-14 was working with a red test suite and did not notice
