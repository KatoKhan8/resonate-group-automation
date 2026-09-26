PRIORITY: P2
SIZE: S
DEPENDS:

# TASK-342 - the review spreadsheet lost the messages

Found while verifying the fifty against the ten on 2026-09-26.

The ten's workbook had two sheets:

    "ten leads"      22 columns: ICP verdict + evidence, facts with sources,
                     HYPOTHESIS (not a fact), hypothesis rests on, signal
                     strength, capability chosen, why that capability, what
                     changes for them, sequence strategy (objective per step),
                     copylint, sequence gate, held / error reason, OLD v1 copy
    "every message"  12 columns: channel, step, day, thread, new-thread-or-reply,
                     subject, objective, BODY (AS SENT), P.S., signature block,
                     chars

The fifty's workbook has "Summary" plus "Leads" (25 columns), and **carries no
message body at all - only character counts** (`em1 chars` ... `em5 chars`,
`LI connect`, `LI msg1..3`). It also drops facts-with-sources, the hypothesis,
signal strength, why-that-capability, what-changes, and the per-step objectives,
and collapses copylint and sequencegate into one `Gate` column.

Nothing is lost overall - the `.html` carries the bodies - but **the spreadsheet
stopped being the instrument an operator can read the copy in**, and the gate
detail that matters most (15 copylint refusals, 10 sequencegate failures, and
WHICH rule fired) is not in it.

## What to do

Restore the ten's information content in the fifty's generator, at the fifty's
scale.

1. Find the generator. It is the script that produced
   `503-FIFTY-v2-2026-09-25.xlsx`. **It lives in `work/`, which is gitignored, so
   it is not in git** - locating it is part of the task. Report its path, and
   report under FINDINGS that the generator of a posted operator artifact is not
   version-controlled, which is a durable-state violation in its own right.
2. Add a second sheet carrying every message verbatim: channel, step, day,
   thread, new-thread-or-reply, subject, objective, body as sent, P.S., signature
   block, chars.
3. Split `Gate` into `copylint` and `sequence gate`, each carrying **which rule
   fired**, not just pass/fail.
4. Restore facts-with-sources, the hypothesis and what it rests on, and
   why-that-capability.

## Acceptance

1. Regenerate into a NEW file. **Do not overwrite
   `work/review/503-FIFTY-v2-2026-09-25.xlsx` or its `.html`** - both are posted
   to `#resonate-os` and hashed (`0c493ab9c3d9d136` / `775cd55287b8f29a`). An
   approved artifact is immutable.
2. Assert the new workbook's dimensions and that body text is present:

    py -3 -c "import zipfile,re;z=zipfile.ZipFile('<your new file>');\
    s=[n for n in z.namelist() if re.match(r'xl/worksheets/sheet\d+.xml',n)];\
    print('sheets',len(s));\
    [print(n, re.search(r'<dimension ref=\"([^\"]+)\"',z.read(n).decode('utf8',errors='replace')).group(1)) for n in sorted(s)]"

   and assert at least one cell holds more than 200 characters - proving a body
   landed, not a count.
3. Report the per-rule gate breakdown it now shows, and check it against the
   verified truth: 31 written, 16 copylint clean, 15 refused (13
   `unrendered_variable`), 21 sequencegate passed, 10 failed, **13 passing both**.
   If your numbers differ, that is a finding - report it, do not adjust to match.

## What this task may NOT do

- Do not overwrite or modify the posted, hashed files.
- Do not regenerate the COPY. This task changes the report, not the messages - no
  model call.
- Nothing sent, nothing activated.
