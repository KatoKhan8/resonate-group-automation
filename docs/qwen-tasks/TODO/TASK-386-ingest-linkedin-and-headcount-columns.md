PRIORITY: P1
SIZE: M
DEPENDS: TASK-347

# TASK-386 — ingest the client file's LinkedIn and headcount columns into records and packs

**Operator instruction, 2026-09-26/27 overnight standing order.**
`work/Productive/productive_ICP_safe_to_send (1).csv` (TASK-347's input)
carries a `Url` (LinkedIn) column per row. TASK-347 ingests the file into
records; this task's job is to confirm — and if missing, add — that the
LinkedIn URL and a headcount figure (band or number, from whatever source
the pipeline already has: the CSV itself, or an enrichment step already run)
actually land in the record and in the pack the copy/lint layer reads, not
just in an intermediate CSV-parsing step that discards them.

## Trace first, then build

1. Read `src/store.py`'s record schema (`new_record`, `validate`) — does it
   have a field for a LinkedIn URL and a headcount? If not, name the closest
   existing field (`linkedin`? `contact.linkedin`? a `sources` entry?) and
   say whether it is populated by TASK-347's ingest today.
2. Read `src/packfacts.py:pack_for()` — does the pack it builds for
   `copylint.check_batch` ever include a headcount or LinkedIn fact? Grep
   `headcount` and `linkedin` across `src/packfacts.py`, `src/research.py`,
   `src/enrich.py`.
3. **Do not assume a gap — measure it.** Run TASK-347's ingest on a small
   sample (10-20 rows) if it has landed, or read its output format if not,
   and report: for one real record, does `rec["research"]` or the record's
   own fields carry the LinkedIn URL and a headcount, end to end, after
   ingest?

## Build only what the trace shows missing

If the columns are read into the record but never reach `rec["research"]`
(the canonical store per TASK-376) or the pack, wire that path — the
smallest change that makes a headcount or LinkedIn fact traceable by
`copylint.untraceable`/`buzzwords_in`/case-study rules the same way any
other fact is. Do not invent a new storage location if `rec["research"]`
already fits.

## Acceptance

1. Name, with file:line, where each column is read today and where (if
   anywhere) it is dropped.
2. For one real ingested record: show the LinkedIn URL and headcount value
   present in the record/pack after your change, and show a rendered claim
   citing the headcount traces correctly through `copylint`.
3. Full suite: wait for `work/suite_verdict.txt`, diff the failing-name SET.

## What this task may NOT do

- Do not invent a headcount figure where the source data has none - report
  the record as lacking one, per this repo's rule that missing evidence is
  never positive evidence.
- No provider write, no send, no campaign action.
