PRIORITY: P1
SIZE: M
DEPENDS:

# TASK-348 - the ingest drops headcount and products

**Operator instruction, 2026-09-26:** ingest the LinkedIn, headcount and products
columns.

**The LinkedIn column is TASK-311's** (`docs/qwen-tasks/TODO/TASK-311-the-ingest-drops-the-linkedin-column.md`),
which is written and unmerged. **Do not duplicate it.** Read it first, follow its
shape, and if it is already merged when you start, extend rather than rewrite.

This task is headcount and products.

## Why they matter

`copylint`'s `untraceable_company_claim` REFUSES a specific - a number, a date, a
proper noun - that does not trace to the pack. Headcount and product names are
exactly the specifics a personalised opener wants, and a writer that cannot see
them either omits them or invents them. 4 of the fifty's 31 written leads were
refused on `untraceable_company_claim`.

## The input columns

    work/Productive/productive_ICP_safe_to_send (1).csv
        Headline, Industry, Company            (products / positioning live here)

    work/Software_Agencies_All_Geo_cleaned - Sheet1.csv
        Seniority, Department, MX_Records, Email_Provider, ... (headcount-adjacent)

**Read the real headers before writing a mapping.** Do not assume a column name;
the two files disagree about nearly every field, and a guessed header is how a
100%-populated column came to be dropped in the first place.

## Build

    src/ingest.py     MODIFY. Carry the columns through.
    src/packfacts.py or the pack builder   READ, then MODIFY so a fact can carry them.
    tests/test_the_ingest_keeps_headcount_and_products.py   NEW

**A fact must carry its source.** Directives §2: value, source, source reference,
observed date, verification status. A headcount from a CSV the client supplied is
`verified` only to the extent the client's file is - say so in the source, do not
stamp it as verified research. **Never fabricate provenance to satisfy a schema**
(directives §7); `UNKNOWN / UNVERIFIED` is preferable to a fake source.

## Acceptance - RUN each, paste real output

1. The columns survive ingest, measured on real rows:

    py -3 -c "import sys;sys.path.insert(0,'.');from src import ingest;\
    rows=list(ingest.read_rows('batches/productive-intake-00000-00250.csv'));\
    got=[r for r in rows if r.get('headcount') or r.get('products')];\
    print('%d of %d rows carry headcount or products'%(len(got),len(rows)))"

   Name the real field keys you chose. **Report the populated PERCENTAGE** - a
   column carried but empty is not ingested, and "the ingest drops a column that
   is 100% populated" is TASK-311's entire title.

2. A pack built from such a row exposes them as facts WITH a source.

3. **The guard is seen to fail:** a test that fails if the columns are dropped
   again. Break the mapping, confirm it fails, restore, confirm green. Paste both.

4. No fabricated provenance: a test asserting a fact built from a client CSV
   names that CSV as its source and is not marked as verified research.

5. Full suite: wait for `work/suite_verdict.txt`, diff the failing-name SET
   against `docs/state/SUITE-BASELINE-2026-09-26.txt`.

## What this task may NOT do

- Do not duplicate TASK-311. Do not commit any row from `work/` - counts and
  percentages only.
- Do not generate copy. Nothing sent, nothing activated.
