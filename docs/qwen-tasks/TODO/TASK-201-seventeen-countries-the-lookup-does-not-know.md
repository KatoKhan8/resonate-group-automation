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
