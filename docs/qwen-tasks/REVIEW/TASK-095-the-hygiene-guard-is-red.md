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

**STATUS:** DONE (two stale tests fixed, one real leak escalated)

**COMMIT SHA:** 46b7256

**TESTS:**
- `tests.test_fixture_hygiene` (11 tests): 10 pass, 1 fail (the real leak)
- `tests.test_task062_failing_sibling_excluded` (4 tests): all pass
- `tests.test_invariants` (80 tests): all pass
- Exit codes read directly from `py -3 -m unittest`, not through a pipe.

**FILES CHANGED:**
- `tests/test_fixture_hygiene.py` - PHONE regex: `\s` → ` \t` (fix false positive)
- `tests/test_task062_failing_sibling_excluded.py` - `acme.com` → `acme.example` (fix non-reserved domain in fixture)

---

### VERDICT PER TEST

#### 1. `test_every_phone_number_is_a_reserved_fiction` — STALE TEST (false positive)

**Root cause:** The PHONE regex `\+\d[\d\s().-]{7,}\d` uses `\s` which matches `\n`. Three "phone numbers" were actually markdown table fragments in `docs/qwen-tasks/DONE/TASK-066-the-classifier-cannot-read-linkedin.md` where a delta like `+93` at end-of-line was concatenated with a percentage `(18.3%)` on the next line:

```
      966       1,059         +93
        (18.3%)        (20.0%)
```

The regex matched `+93\n        (18.3` across the line boundary. Same pattern for `+67` and `+7`. None of these are phone numbers.

**Fix:** Changed `\s` to `[ \t]` in the PHONE regex character class. Phone numbers are single-line constructs; horizontal whitespace only. The ALLOWED_PHONES set entries all use horizontal whitespace and still match. This is not widening the guard - it is fixing a regex that matched things that are not phone numbers.

#### 2. `test_every_email_address_is_on_a_reserved_domain` — STALE TEST (fixture non-compliance)

**Root cause:** `tests/test_task062_failing_sibling_excluded.py` line 89 used a test fixture email on a real, resolvable domain (a well-known fictional company's actual .com). Not in SAFE_SUFFIXES (RFC 2606/6761 reserved). The guard correctly flagged it.

**Fix:** Changed the fixture to use the `.example` TLD, which is reserved by RFC 2606 and is in SAFE_SUFFIXES. The test's company name "Acme Corp" and person "Jane Doe" are fictional and do not trigger FORBIDDEN_NAMES. The test_task062 tests still pass (verified: 4/4 OK).

#### 3. `test_no_real_person_or_client_named` — REAL LEAK (escalated below)

15 hits across 8 tracked files. These are not false positives. The FORBIDDEN_NAMES list contains real prospect/client company names and a real person's LinkedIn identifier, and those names appear in committed files.

---

### ESCALATION: Real prospect/client names in tracked files

**Class of data:** Real prospect company name tokens, real prospect record IDs (domain-derived), and one real person's LinkedIn profile path.

**Files and line numbers (name tokens, not values):**

| File | Line(s) | Class |
|------|---------|-------|
| `docs/CONTEXT-RESET-2026-09-14-C.md` | 366, 477, 499 | prospect record ID + name token |
| `docs/HEYREACH-599020-UPDATED-2026-09-14.md` | 48 | prospect record ID |
| `docs/HEYREACH-PROVIDER-READBACK-2026-09-14.md` | 29 | **real person LinkedIn profile URL + seat number** |
| `docs/WHY-REGENERATION-CANNOT-CONVERGE-2026-09-14.md` | 3 | prospect record ID |
| `docs/qwen-tasks/DONE/TASK-061-*.md` | 10, 74, 94, 96, 99 | prospect record ID + name token |
| `docs/qwen-tasks/DONE/TASK-062-*.md` | 13, 14 | prospect name token |
| `docs/qwen-tasks/DONE/TASK-068-*.md` | 5, 61, 144, 183 | prospect record ID + name token |
| `scripts/task065_run_bcd.py` | 31-35 | 6 prospect name tokens in RECORD_IDS literal list |

**Most serious:** `docs/HEYREACH-PROVIDER-READBACK-2026-09-14.md:29` contains a real person's LinkedIn profile path and a HeyReach seat number. This is PII - a named individual's professional profile linked to a provider account identifier.

**Pattern:** The docs/ files are analysis reports from 2026-09-14 that reference real prospects by record ID (which embeds the domain name). The script has a hardcoded list of 15 record IDs containing real prospect domain names. The task description notes this script "had fifteen real prospect domains baked into a literal list" and that domains were redacted - but the record IDs still carry the name tokens.

**Not redacted quietly.** Redaction fixes the working tree only; git history retains every committed occurrence. A history rewrite is an operator decision. The operator needs to decide:
1. Whether these docs/ reports should be purged of real identifiers or retained as-is
2. Whether `scripts/task065_run_bcd.py` should have its RECORD_IDS replaced with opaque identifiers
3. Whether the git history warrants a rewrite (operator decision, not mine)

**FINDINGS:** Two of three red hygiene guards were false positives (regex bug + fixture non-compliance). Both fixed. The third is a real leak of prospect names and one person's LinkedIn profile across 8 tracked files committed between 2026-09-14 and present. The guard itself is sound - it caught what it was designed to catch.

**RISKS:** The 15 name occurrences are already in git history. Working-tree redaction mitigates future exposure but does not erase committed blobs. The HeyReach provider readback file also contains a seat number that may be a live account identifier.

**RECOMMENDED CLAUDE ACTION:**
1. Review the escalation and decide on redaction scope for the 8 files
2. Decide whether the git history needs a rewrite (this is an operator call)
3. The two stale-test fixes are safe to integrate immediately - they make the guard more precise, not less
