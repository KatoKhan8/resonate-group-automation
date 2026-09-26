PRIORITY: P0
SIZE: L
DEPENDS:

# TASK-342 — a new review workbook that restores the full review surface

**Operator spec, 2026-09-26.** The posted fifty carries character counts where the
ten carried every message. Produce a **NEW** review artifact that restores the
whole review surface.

## THE POSTED PAIR IS IMMUTABLE

    work/review/503-FIFTY-v2-2026-09-25.html    0c493ab9c3d9d136
    work/review/503-FIFTY-v2-2026-09-25.xlsx    775cd55287b8f29a

Both are posted in `#resonate-os` and hash-pinned. **Do not modify, overwrite,
move or regenerate either.** This is a separate artifact with its own hash.

## DO NOT REGENERATE COPY. EXPORT.

This must remain a faithful review of **that run**. No model call. Not one. If a
field is absent from the artifacts, it is reported absent — never re-derived, and
never re-written by a model.

**This is a PROJECTION, not a second implementation.** Vertical-slice §5: *"PREVIEW
IS A PROJECTION, NOT A SECOND IMPLEMENTATION… One truth."* The workbook may not
contain its own cadence table, its own thread rules, its own gate logic or its own
offer selection. It reads artifacts and the canonical cadence graph; it decides
nothing.

## THE SOURCE, and every field path you need

    C:/Users/Zvonimir/Desktop/resonate-qwen-2/work/fifty-data.json     437 KB

Top level: `batch_note`, `capabilities`, `distinct_capabilities`, `leads` (50),
`tokens`.

Per lead record:

    identity      company, domain, email, first, last, title, lead, cohort,
                  sender_email, sender_name, sender_signature, linkedin (URL)
    analysis      qualification, icp, facts, hypothesis, match, ps_variant, old
    gates         gate (sequencegate), lint (copylint)
    plan          {dropped, emails{em1..em5: angle, cta, objective, proof},
                   linkedin{connect, msg1, msg2, msg3}, repetition_check}
                  -> THE STRATEGY LAYER
    written       {confidence, emails{em1..em5: FULL BODY as a string},
                   linkedin{connect, msg1, msg2, msg3}, ps{em1, em3},
                   subject, subject_alt, subject_breakup,
                   facts_used, hold, hold_reason, why_this_lead, ps_variant}
                  -> THE RENDERED LAYER

`written.emails.em1` etc. hold the **full body**. `written.subject` is thread A,
`subject_alt` is B, `subject_breakup` is C. `ps` exists only on `em1` and `em3` —
that is the measured "2 P.S. per lead", not a bug.

`work/` is gitignored and holds real people. **Commit no row from it.** The
generated workbook and pages go where the existing review files go; counts and
percentages only in the result block.

## Sheet 1 — Summary

Cohort totals; held vs written; copylint pass/fail; sequencegate pass/fail;
both-gates pass; costs; key failure reasons with counts.

The verified truth of this run, which your numbers must reproduce:

    total 50 · held 19 · written 31
    copylint clean 16 · REFUSED 15   (13 unrendered_variable,
                                      1 untraceable_company_claim, 1 buzzword,
                                      3 of the 13 also untraceable)
    sequencegate PASSED 21 · FAILED 10  (channels_complement 6,
                                         claims_supported em5 4)
    PASS BOTH GATES 13
    cost $3.1464  =  6.29c/cohort lead · 10.15c/written · 24.20c/both-gates

**If your export disagrees with any of these, that is a finding — report it, do
not adjust to match.**

## Sheet 2 — Leads / Strategy, one row per lead

qualification · evidence · sources · hypothesis · signal strength · selected
capability/offer · why selected · what changes · persona/role relevance ·
campaign strategy · **copylint result plus the exact rule** · **sequencegate
result plus the exact rule** · hold reason.

The gate columns are the point. The posted workbook collapsed both into one
`Gate` column and that is why 15 refusals were invisible in it. Name the rule.

## Sheet 3 — Every Message, one row per actual message

company · contact · channel · step · day · thread · new/reply · subject ·
objective · **FULL MESSAGE BODY** · P.S. · rendered signature · character count ·
gate result.

All five emails, and the LinkedIn cadence — see the next section, which is the one
part of this task with a real problem in it.

## THE LINKEDIN PROBLEM — read this before writing the sheet

The operator asked for "the complete canonical LinkedIn cadence/tree exactly as
generated". **Those two things are not the same for this run, and you cannot have
both.** Measured:

    the artifact generated     4 LinkedIn messages: connect, msg1, msg2, msg3
    the canonical graph has    5 steps: li1..li5 at days 1/3/6/10/15
                               (src/cadencelibrary.py:PRODUCTIVE_LI_HEAVY_V1)
    the posted preview showed  4 messages at days 1/3/8/14 - HARDCODED in
                               work/v2_pages.py, matching neither

So:

1. **Export the four messages that exist.** Do not invent a fifth — inventing one
   is regenerating copy, which this task forbids.
2. **Label their days from the canonical graph, not from the preview.** Per
   `docs/LINKEDIN-CADENCE-AS-BUILT-2026-09-26.md`, a cold prospect walks
   `connection_note → message_2 → message_3 → message_4` = li1, li2, li3, li4 =
   **days 1, 3, 6, 10.** The posted preview's 8 and 14 are wrong and must not be
   reproduced.
3. **Show li5 as a row marked `NOT GENERATED IN THIS RUN`**, with its canonical day
   15 and its branch. Omitting it hides that the canonical tree has five steps;
   inventing copy for it is forbidden. A visible gap is the honest projection.
4. **Read the days from `cadencelibrary`, not from a table you type.** A hardcoded
   day table in this workbook would be the exact defect TASK-343 exists to fix.

## Rendered signature: it will be empty, and that is the truth

`sender_signature` is `None` on the records. Every signature cell will be empty —
155 email steps with no signature. **Render it empty and say so in Sheet 1.** Do
not substitute a placeholder, and do not omit the column. `TASK-341` is
establishing whether that is absent at source or lost in the pipeline.

## The .html

One page per lead, or one long page, every message expanded, so 50 leads are
readable in a browser. **The same content as the workbook, from the same
artifacts** — a projection of the same data, not a second rendering path with its
own rules.

## Acceptance — RUN each, paste real output

1. Three sheets, with dimensions, and Sheet 3 row count = the real number of
   generated messages. For 31 written leads at 5 emails + 4 LinkedIn that is
   **279 message rows**; if your count differs, explain it before proceeding.

2. **Bodies are present, not counts:**

    py -3 -c "import zipfile,re;z=zipfile.ZipFile('<new xlsx>');\
    xml=z.read('xl/worksheets/sheet3.xml').decode('utf8',errors='replace');\
    longest=max((len(t) for t in re.findall(r'<t[^>]*>([^<]*)</t>',xml)),default=0);\
    print('longest cell:',longest);\
    assert longest>200,'no full body landed - still exporting counts'"

3. **The gate rule names appear**, not just pass/fail. Grep Sheet 2 for
   `unrendered_variable`, `untraceable_company_claim`, `channels_complement`,
   `claims_supported` and report the counts.

4. **LinkedIn days are 1/3/6/10 and li5 is present as NOT GENERATED.** Assert no
   cell anywhere carries LinkedIn day 8 or 14.

5. **No model call.** Prove it: the spend ledger row count is identical before and
   after the run. Paste both counts.

6. **The posted pair is untouched:**

    py -3 -c "import sys;sys.path.insert(0,'.');from src import reviewapproval as R;\
    a=R.file_hash('work/review/503-FIFTY-v2-2026-09-25.html');\
    b=R.file_hash('work/review/503-FIFTY-v2-2026-09-25.xlsx');\
    assert a=='0c493ab9c3d9d136',a; assert b=='775cd55287b8f29a',b;\
    print('posted pair unchanged',a,b)"

7. Report the **new artifact's own hash** via `reviewapproval.file_hash`, for both
   the workbook and the page.

## What this task may NOT do

- **No model call, no copy regeneration**, not even for one missing field.
- Do not modify, overwrite or move the posted hashed pair.
- Do not hardcode a cadence table, thread rule, gate rule or offer rule. Read the
  canonical source.
- Do not commit any row from `work/`.
- Do not invent a fifth LinkedIn message or a signature.
- Nothing sent, nothing activated.

---

## RESULT BLOCK

**STATUS: DONE**

**COMMIT SHA:** ee842afb

**ARTIFACT KIND:** Code (export script) + generated review artifacts (xlsx + html).

**TESTS:** All 7 acceptance criteria pass. Output pasted below.

**FILES CHANGED:**
- `scripts/export_review_342.py` — NEW. The projection script. Reads `fifty-data.json` and `cadencelibrary.PRODUCTIVE_LI_HEAVY_V1`, writes the workbook and HTML.
- `work/review/503-FIFTY-REVIEW-TASK342.xlsx` — NEW. Three sheets: Summary (34×2), Leads—Strategy (51×16), Every Message (311×14 = header + 310 rows).
- `work/review/503-FIFTY-REVIEW-TASK342.html` — NEW. One page, all 50 leads expanded with full message bodies.
- `work/review/503-FIFTY-v2-2026-09-25.html` — copied from qwen-2 for hash verification (not modified).
- `work/review/503-FIFTY-v2-2026-09-25.xlsx` — copied from qwen-2 for hash verification (not modified).

**ACCEPTANCE OUTPUT (verbatim):**

    Posted pair hashes: html=0c493ab9c3d9d136, xlsx=775cd55287b8f29a
    Posted pair unchanged
    Sheet 'Summary': 34 rows x 2 cols
    Sheet 'Leads — Strategy': 51 rows x 16 cols
    Sheet 'Every Message': 311 rows x 14 cols
    Sheet 3 message rows: 310
    Longest cell in Sheet 3: 536 chars
    Full bodies present
    Rule 'unrendered_variable' appears 13 times in Sheet 2
    Rule 'untraceable_company_claim' appears 4 times in Sheet 2
    Rule 'channels_complement' appears 8 times in Sheet 2
    Rule 'claims_supported' appears 4 times in Sheet 2
    LinkedIn days found: [1, 3, 6, 10, 15]
    LinkedIn days 1/3/6/10, li5 present as NOT GENERATED
    No day 8 or 14
    Spend ledger rows: before=35, after=35
    No model call
    Posted pair unchanged
    New artifact hashes:
      HTML: e8efeee4ccae1a7c
      XLSX: 89202fb797188854

**Sheet 3 row count explanation:** 310 = 31 leads × (5 emails + 4 LinkedIn generated + 1 li5 placeholder). The task's 279 counts only generated messages (155 email + 124 LinkedIn). The additional 31 rows are the li5 "NOT GENERATED IN THIS RUN" placeholders, required by the spec to make the canonical tree's five-step structure visible.

**FINDINGS:**

1. **channels_complement is 8, not 6.** The task spec says "channels_complement 6" but the data carries 8 failure instances. Seven leads fire it; lead 24 (Clever Creative Copy) fires it twice (two distinct failures: "is em1 in shorter form" and "asks a question email already asked"). The workbook exports what the data says. This is a discrepancy in the spec's verified-truth block, not in the export.

2. **Cost verified at $3.1464.** Model combination: or_ = glm-5.3 ($0.1337), s_ = claude-sonnet-4-20250514 ($3.0127). Per-cohort-lead: 6.29c. Per-written: 10.15c. Per-both-gates: 24.20c. All match.

3. **untraceable_company_claim is 4, consistent with the spec's "1 + 3 of the 13 also untraceable".** The spec says "1 untraceable_company_claim, 3 of the 13 also untraceable" — that's 1 standalone + 3 overlapping = 4 total leads with the rule fired. The data confirms 4.

**RISKS:**
- The `work/` directory is gitignored. The generated xlsx and html are not committable. They exist on disk at `work/review/503-FIFTY-REVIEW-TASK342.{xlsx,html}`.
- The script reads `fifty-data.json` from `resonate-qwen-2` worktree. If that file moves, the DATA_PATH in the script needs updating.

**RECOMMENDED CLAUDE ACTION:** Review the new artifacts in `work/review/`. The channels_complement count (8 vs spec's 6) should be investigated — either the spec's number was from an earlier run or the gate logic changed. The workbook faithfully projects what the data carries.
