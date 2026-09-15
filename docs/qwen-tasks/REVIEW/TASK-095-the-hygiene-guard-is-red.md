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

## VERDICTS (2026-09-15)

### Test 1: `test_every_phone_number_is_a_reserved_fiction` - STALE TEST

**Evidence:** The PHONE regex `\+\d[\d\s().-]{7,}\d` matches across newlines
because `\s` includes `\n`. The three "phone numbers" are actually markdown
table cells in `docs/qwen-tasks/DONE/TASK-066-the-classifier-cannot-read-linkedin.md`:

- Line 148: `+93` (count difference in a classification results table)
- Line 150: `+7` (count difference)
- Line 152: `+67` (count difference)

The regex matches `+93\n        (18.3` because `\s` allows the newline. These
are NOT phone numbers - they are statistics in a markdown table.

**Fix:** Changed regex from `\+\d[\d\s().-]{7,}\d` to `\+\d[\d ().-]{7,}\d`
(removed `\s`, kept literal space). This prevents cross-line matching while
still allowing legitimate phone number formats.

**Status:** FIXED. Test now passes.

---

### Test 2: `test_every_email_address_is_on_a_reserved_domain` - STALE TEST

**Evidence:** `tests/test_task062_failing_sibling_excluded.py` line 89 uses
a test email with a classic example domain that is NOT in the SAFE_SUFFIXES
list (which only includes RFC 2606/6761 reserved domains like `.example`,
`.test`, `example.com`, etc.).

This is a test fixture using a non-reserved example domain. The test itself
is correct in spirit - it needs a placeholder email - but the domain choice
trips the guard.

**Fix:** Changed the test email to use an RFC-reserved domain.

**Status:** FIXED. Test now passes.

---

### Test 3: `test_no_real_person_or_client_named` - REAL LEAK

**Evidence:** Multiple files contain forbidden names. One is a confirmed real
leak requiring escalation:

#### REAL LEAK (ESCALATE):

**File:** `docs/HEYREACH-PROVIDER-READBACK-2026-09-14.md`  
**Line:** 29  
**Class of data:** A real person's LinkedIn profile URL and their HeyReach seat
number. This is direct PII - a clickable link to a real individual's
professional profile, along with an internal identifier.

This is not a record ID or an abstract reference. It is a real person's
LinkedIn profile, committed to git history.

#### AMBIGUOUS CASES (operator decision required):

The following files contain record IDs that include forbidden company name
tokens:

1. **`scripts/task065_run_bcd.py`** - RECORD_IDS list contains six record
   identifiers derived from company domains (using `-com` instead of `.com`).
   
   These are internal record identifiers. The task description says "Those
   were redacted" about domains in this file, but the record IDs remain. They
   are not contact information, but they reveal which companies were prospects.

2. **Documentation files** - contain record IDs in analysis context:
   - `docs/CONTEXT-RESET-2026-09-14-C.md`
   - `docs/HEYREACH-599020-UPDATED-2026-09-14.md`
   - `docs/WHY-REGENERATION-CANNOT-CONVERGE-2026-09-14.md`
   - `docs/qwen-tasks/DONE/TASK-061-*.md`
   - `docs/qwen-tasks/DONE/TASK-062-*.md`
   - `docs/qwen-tasks/DONE/TASK-068-*.md`
   
   These are record IDs used in historical analysis documentation. Some
   include both a company identifier and a person's name.

**Question for operator:** Are record IDs (internal identifiers derived from
company domains) considered acceptable in documentation and scripts, or should
they be redacted/abstracted? The FORBIDDEN_NAMES list was designed to catch
names in generated copy, not necessarily record IDs. But the test is
mechanical and does not distinguish.

**Status:** NOT FIXED. The LinkedIn URL is a real leak and must not be
redacted quietly. The record ID cases require operator decision on whether
they are acceptable or should be abstracted.

---

## NEIGHBOUR TESTS

All other tests in `tests/test_fixture_hygiene.py` pass:

- `test_no_real_client_prospect_or_roster_domain` - PASS
- `test_no_live_account_figures` - PASS
- `test_no_crm_narrative_about_a_real_account` - PASS
- `test_the_tracked_template_holds_only_reserved_domains` - PASS
- `test_the_real_roster_is_not_tracked` - PASS
- `test_the_real_roster_is_ignored_so_it_cannot_be_added_by_accident` - PASS
- `test_no_env_file_is_tracked` - PASS
- `test_no_runtime_state_directory_is_tracked` - PASS

---

## RESULT BLOCK

**STATUS:** PARTIAL - two stale tests fixed, one real leak escalated

**COMMIT SHA:** bf70da8

**TESTS:** 
- `test_every_phone_number_is_a_reserved_fiction` - PASS (was FAIL)
- `test_every_email_address_is_on_a_reserved_domain` - PASS (was FAIL)
- `test_no_real_person_or_client_named` - FAIL (real leak, not fixed)
- All other hygiene tests - PASS

**FILES CHANGED:**
- `tests/test_fixture_hygiene.py` - Fixed PHONE regex to not match across newlines
- `tests/test_task062_failing_sibling_excluded.py` - Changed test email to use RFC-reserved domain

**FINDINGS:**
1. Phone regex was stale - matched markdown table statistics as phone numbers
2. Test fixture used non-reserved example domain
3. **REAL LEAK:** `docs/HEYREACH-PROVIDER-READBACK-2026-09-14.md` line 29
   contains a real LinkedIn profile URL and seat number. This is PII and must
   be escalated.
4. Record IDs in scripts and docs contain forbidden company name tokens but
   are internal identifiers, not contact information. Operator decision
   required on whether these are acceptable.

**RISKS:**
- The real LinkedIn URL is in git history. Redaction from HEAD does not erase
  it from history. A history rewrite is an operator decision.
- Record IDs may be considered acceptable as internal identifiers, or may need
  abstraction. This is a classification decision, not a technical one.

**RECOMMENDED CLAUDE ACTION:**
1. Review the real leak (LinkedIn URL) and decide on escalation/mitigation
2. Decide whether record IDs in scripts and docs are acceptable or should be
   abstracted
3. If record IDs are acceptable, update FORBIDDEN_NAMES or the test logic to
   exclude record ID patterns
4. If record IDs are not acceptable, redact them (but note this only fixes
   HEAD, not history)
5. Consider whether the LinkedIn URL requires notification to the affected
   individual (legal/privacy decision)
