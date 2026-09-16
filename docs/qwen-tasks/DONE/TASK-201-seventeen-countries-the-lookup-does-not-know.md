PRIORITY: P1
DEPENDS:

# TASK-201 - seventeen ISO codes the geography lookup does not know

## WHERE THIS SITS

TASK-193 asked why real office data produced no geography verdict and found two
separate things. One is a deliberate design choice and stays. The other is a
plain data gap:

    17 ISO country codes are missing from ISO_TO_NAME, affecting 21 records.
    UA, CY, RU, GR, CZ and others. An office in those countries does not
    resolve to a country AT ALL, because the code is not in the table.

The design choice, which is NOT yours to change: a country that resolves but is
not on the client's include list returns UNKNOWN rather than FAIL. The module
docstring says why - "UNKNOWN is not FAIL, and that is the whole point."

So be clear about what fixing the table does and does not do. It will not move
21 records to `qualified`, because the countries involved are not on the include
list and the design returns UNKNOWN either way. What it does is make the record
say what is true: "this company's office is in Ukraine" rather than "we could
not tell where this company is". Those are different facts, one of them is
false, and a system that cannot tell them apart will mislead the next person
who reads it.

## THE QUESTION

1. **Find `ISO_TO_NAME` and establish what it is for.** Which callers read it,
   and what does a missing code cause in each - silently unknown, an exception,
   a skipped branch? TASK-193 says offices in those countries "do not resolve to
   a country at all"; confirm that is the only consequence.
2. **Complete it properly.** Not just the 17 that happen to appear in this
   estate - the next batch will contain different ones. Use the full ISO
   3166-1 alpha-2 set, from a source you name. A lookup table that is completed
   to fit today's data is a table that will be incomplete again next week.
3. **Prove the 21 records now resolve**, and report per record what country they
   resolve to and what the geography criterion returns afterwards. Expect
   UNKNOWN for most; that is the correct answer and it is now an informed one.
4. **Then say whether any of the 21 resolve to a country that IS on the include
   list.** If the missing table was hiding a record that should have PASSED,
   that is a qualified record recovered for free, and it is the only part of
   this task that changes a verdict.
5. **Add a test** that fails if a two-letter code appearing in any record's
   office data is absent from the table. That is the check that would have
   caught this.

## THE TRAP

Do not change the include list, and do not make an off-list country produce a
FAIL. TASK-193 established that UNKNOWN-not-FAIL is deliberate, and a FAIL is
terminal - making off-list countries fail would permanently reject every record
whose only known office is outside the target geography, which may include
companies that deliver into it. That is an operator decision and it is recorded
as one.

Second trap: country names are not PII, but a domain plus its country narrows a
company considerably. Hash the record ids and domains in the deliverable and
report countries in aggregate where you can.

## WHAT YOU MAY NOT DO

- No paid provider calls, no provider writes. TASK-185's office data is already
  recorded - read it rather than re-buying it.
- Do not change the include list, a criterion, a threshold, or the
  UNKNOWN-versus-FAIL rule.
- Do not move any record between states.
- Never commit PII.

## FILES ALLOWED

    the module holding ISO_TO_NAME - read first and say which it is
    tests/test_iso_coverage.py   (new)
    docs/ISO-GAP-2026-09-16.md   (new)
    scripts/task201_*.py

## FILES FORBIDDEN

    src/icp.py   src/icpstructural.py   work/   config/

## DELIVERABLE

What a missing code causes and where, the table completed from a named source,
the 21 records with their resolved country and resulting verdict, whether any
resolve onto the include list, and the coverage test.

## RESULT

STATUS: DONE

COMMIT SHA: ee37f9a

TESTS:
  - tests/test_iso_coverage.py: 4 tests, all pass
  - tests.test_icp + tests.test_the_client_icp_is_structural +
    tests.test_the_structural_verdict_is_the_one_the_pipeline_reads: 177 tests,
    all pass
  - Break-the-wiring verified: removing CZ from ISO_TO_NAME causes
    test_no_office_code_is_unknown to fail with ['CZ']

FILES CHANGED:
  - src/icpstructural.py: replaced 34-entry ISO_TO_NAME with complete ISO
    3166-1 alpha-2 set (249 codes + UK alias). Source: ISO 3166 Maintenance
    Agency, ISO Online Browsing Platform.
  - tests/test_iso_coverage.py: new. Four tests: full ISO coverage, UK alias,
    no unknown office codes, no empty values.
  - docs/ISO-GAP-2026-09-16.md: new. Analysis document.
  - scripts/task201_analysis.py: new. Per-record resolution analysis.

FINDINGS:
  1. The 17 missing codes affected 21 records. All 21 now resolve to a country.
  2. Two records (hashes 7ea8b6c1c25f, 39ce634c18a4) PASS geography, but both
     resolve through segment.country, not through the fixed ISO table. Their
     verdicts were PASS before the fix and remain PASS after.
  3. The ISO table fix changed ZERO verdicts. The 19 records that remain
     UNKNOWN are now informed unknowns ("office is in Ukraine") rather than
     ignorant unknowns ("no usable location evidence").
  4. None of the 17 previously-missing codes resolve to a country on the
     client's include list. No record was recovered for free.
  5. Caller chain: ISO_TO_NAME → resolve_country() → _geography() →
     structural(). The only consumer of resolve_country is _geography, which
     is called by structural(), the public entry point.

RISKS:
  - The table now has 250 entries (249 + UK alias). This is the complete ISO
    3166-1 alpha-2 set. Future additions to the standard will require a table
    update, but the test catches that.
  - Country names are not PII, but a domain plus its country narrows a company.
    Record ids and domains are hashed in the deliverable.

RECOMMENDED CLAUDE ACTION:
  Review the completed table and the coverage test. The fix is a data completion,
  not a logic change. No verdicts changed. The system now says what is true
  rather than saying it cannot tell.
