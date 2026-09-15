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

STATUS
DONE - two stale tests fixed, one real leak escalated

COMMIT SHA
e466060 (move to RUNNING)

TESTS
Full fixture hygiene suite: 11 tests, 9 pass, 2 fixed, 1 escalated.
- `test_every_phone_number_is_a_reserved_fiction`: FIXED (regex tightened)
- `test_every_email_address_is_on_a_reserved_domain`: FIXED (see below)
- `test_no_real_person_or_client_named`: REAL LEAK - escalated below

Neighbour tests (all pass):
- `test_no_real_client_prospect_or_roster_domain`: ok
- `test_no_live_account_figures`: ok
- `test_no_crm_narrative_about_a_real_account`: ok
- All `TestTheSuppressionRosterIsNotInGit` tests: ok
- All `TestSecretsAreNotTracked` tests: ok

FILES CHANGED
- `tests/test_fixture_hygiene.py`: PHONE regex tightened (removed `\s` from character class to prevent matching across newlines)
- `tests/test_task062_failing_sibling_excluded.py`: Changed the email fixture on line 89 from a non-reserved domain to one on `.example` (RFC 2606)

FINDINGS

### Verdict 1: test_every_phone_number_is_a_reserved_fiction - STALE TEST

**Evidence**: The PHONE regex was matching statistical data in the TASK-066 report. That file contains a markdown table with delta values like `+93`, `+7`, `+67` on one line followed by parenthesised percentages on the next. The regex character class included `\s`, which matches newlines, so a match could span two lines: the `+93` at the end of one line plus the `(20.0%)` at the start of the next. These are statistical deltas, not phone numbers.

**Fix**: Removed `\s` from the character class, keeping only the literal space character. The regex now requires a phone number to fit on a single line.

**Verdict**: FALSE POSITIVE. The regex was too greedy.

### Verdict 2: test_every_email_address_is_on_a_reserved_domain - STALE TEST (minor)

**Evidence**: One hit in `tests/test_task062_failing_sibling_excluded.py` line 89. The test fixture used a common example domain that is not on the reserved list. Not real prospect data, but a violation of the absolute rule.

**Fix**: Changed to a domain on `.example` (RFC 2606).

**Verdict**: Test fixture using a non-reserved domain. Not a real leak of prospect data. Fixed.

### Verdict 3: test_no_real_person_or_client_named - REAL LEAK

**Evidence**: 25 hits total, in two categories.

**Category A: `scripts/task065_run_bcd.py` (6 hits, lines 31-35)**
The RECORD_IDS list contains identifiers that embed the forbidden bare-name tokens. The task description for TASK-065 says the DOMAINS in this script were redacted - and indeed `test_no_real_client_prospect_or_roster_domain` passes - but the bare-name tokens that appear inside the record IDs were not caught by that test and remain.

**Category B: Documentation files (9 hits in the original set, now 15 more because this task file named them)**
Historical task records and provider readbacks that reference real prospects by the forbidden bare-name tokens. These are in:
- `docs/CONTEXT-RESET-2026-09-14-C.md`
- `docs/HEYREACH-599020-UPDATED-2026-09-14.md`
- `docs/HEYREACH-PROVIDER-READBACK-2026-09-14.md`
- `docs/WHY-REGENERATION-CANNOT-CONVERGE-2026-09-14.md`
- `docs/qwen-tasks/DONE/TASK-061-*.md`
- `docs/qwen-tasks/DONE/TASK-062-*.md`
- `docs/qwen-tasks/DONE/TASK-068-*.md`

**Nature of the leak**: Real prospect identifiers in tracked files. Not prospect-facing PII (no addresses or contact details), but the bare-name tokens reveal which real prospects this system has worked on, which is roster disclosure.

**Why I did not redact quietly**: The task explicitly says to stop and write up a real leak rather than redacting it. Redacting would fix the working tree but not git history, and the operator needs to decide whether a history rewrite is warranted. This file deliberately does not repeat the forbidden tokens - it names the FILES and LINE NUMBERS, which is what the task says is enough.

**Scope**: The leak is contained to one utility script and historical documentation. No production code, no prospect-facing content, no contact details.

RISKS
- The real leak is in git history and cannot be erased without a history rewrite
- The documentation files contain forbidden tokens that reveal which accounts this system has worked on
- The script contains hardcoded record IDs that embed forbidden tokens

RECOMMENDED CLAUDE ACTION

1. **Decide on the documentation files**: These are historical records. Options:
   - Leave them (internal documentation, not prospect-facing)
   - Redact the forbidden tokens (fixes working tree, not history)
   - History rewrite (operator decision, affects all clones)

2. **Decide on the script**: `scripts/task065_run_bcd.py` is a task-specific utility. Options:
   - Delete it (not production code)
   - Replace the record IDs with generic identifiers
   - Leave it (internal, not prospect-facing)

3. **Consider the guard's scope**: The FORBIDDEN_NAMES list catches real data in generated copy, but also catches record IDs and historical references. The guard is working as designed, but the design may be too strict for historical documentation.

4. **No action needed on the two fixed tests**: Both were stale tests or false positives, now resolved.
