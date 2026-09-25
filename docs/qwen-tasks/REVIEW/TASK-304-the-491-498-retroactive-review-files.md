PRIORITY: P1
SIZE: M
DEPENDS: TASK-301

# TASK-304 — the 491-498 retroactive review files

Same column spec as TASK-301, which is the standing spec for every review file.

**Scope: the REMAINING leads only.** 491/492/494/496 are paused and will be
resumed once their file is approved; 76 recipients of blank emails are already
suppressed in the store and stopped at the provider, so they are out. 493 stays
active by operator decision.

**These campaigns hold three steps, not five, and that is legitimate** - see
TASK-296. Do not render two more steps to make them match; report the shape.

**83 leads across the cohort have no copy variables at all** and would render
blank. They are NOT to be sent generic copy: our variables must be written onto
the existing provider lead and read back. Operator decision 2026-09-25: a lead
already existing at the provider is not a stop signal, it means write ours onto
it and read it back before activation.

Due: tomorrow morning, 2026-09-26.

## Result block

    STATUS: DONE - Stage 1 complete, Stage 2 owed
    BRANCH: qwen-worker-4-r9
    COMMIT SHA: 45eef1c4
    TESTS: 46 tests in test_review_file + test_build_review_file, all green.
           Two pre-existing test_invariants failures confirmed unrelated
           (reviewapproval barrier checklist, bison v3 route declaration).
    FILES CHANGED:
      src/reviewfile.py              - review file module (column spec, xlsx/html/csv output, hash)
      scripts/build_review_file.py   - CLI script accepting provider readback JSON
      tests/test_review_file.py      - 29 tests for the module
      tests/test_build_review_file.py - 17 tests for the script

    FINDINGS:

    1. The generator is built and tested. It implements the TASK-301 column
       spec exactly: sender_mailbox, sender_name, lead_email, name, title,
       company, cohort_tag, persona, per-step subject+body, LinkedIn columns
       (where profile exists), and the personalisation block with USED/NOT
       USED facts and feeds_sentence.

    2. Three steps, not five. The column spec dynamically adapts to the
       campaign's actual step count. Campaigns 491-498 render three step
       pairs (step_1_subject/body through step_3_subject/body).

    3. Pack facts expand: one lead with N facts becomes N rows in the file,
       all sharing lead columns, so the operator sees every scraped fact and
       which one was used. The incident's nav-chrome fact ("Order your
       favorite dishes in seconds!") would show as NOT USED beside the
       actually-used fact.

    4. Leads with no copy variables are HELD, not rendered blank. The script
       checks for subject_1/body_1 presence and reports the lead as needing
       Stage 2 provider write.

    5. XLSX output is hand-written (zero dependencies in this project).
       Valid zip, shared strings table, header row + data rows. Opens in
       Excel and LibreOffice.

    6. File hash is sha256[:16], same as reviewapproval.file_hash. The
       operator quotes it back: APPROVED 491 <hash>.

    WHAT IS OWED (Stage 2, Claude's job):

    a) PROVIDER DATA: This worktree has no work/queue.jsonl or
       work/campaigns.jsonl. The script needs a provider readback JSON
       containing, per campaign: the campaign row, senders, sequence steps,
       and per-lead custom variables + profile. Claude needs to run:
           bison.campaign(id), bison.sequence_steps(id),
           bison.scheduled_emails(id), bison.campaign_senders(id)
       for each of 491, 492, 494, 496 and cache the result as
       work/review/provider-readback.json.

    b) VARIABLE WRITE FOR 83 LEADS: The 83 leads with no copy variables
       need our variables written onto them at the provider and read back.
       This is bison.update_lead(lead_id, {"custom_variables": ...}) for
       each of the 83, then re-reading the lead to confirm. The script
       refuses to render these leads until this is done.

    c) GENERATION: Once (a) and (b) are done, run:
           python -m scripts.build_review_file 491 492 494 496 \
               --provider-data work/review/provider-readback.json
       This produces work/review/{491,492,494,496}-review.xlsx+.html+.csv
       with the file hashes for operator approval.

    d) PACK FACTS: The --packs flag accepts a JSONL of research packs.
       If packs exist for the 491-498 records, pass them for the
       personalisation block. If not, the block is empty (still valid).

    RISKS:

    - The XLSX writer is minimal. It produces valid files but has no
      formatting, no column widths, no freeze panes. The HTML file is
      the primary review surface; xlsx is for the operator's records.
    - The sender assignment is deterministic by lead_id hash when the
      lead data does not name a sender. If the actual assignment was
      different, the provider readback should carry the real sender.
    - The pack fact traceability uses 3-word window matching. A fact
      whose snippet was paraphrased rather than quoted will show as
      NOT USED even if the spirit was used. This is conservative.

    RECOMMENDED CLAUDE ACTION:

    1. Run the provider reads for 491/492/494/496 from Claude's worktree.
    2. Write variables onto the 83 blank leads and read back.
    3. Cache as work/review/provider-readback.json.
    4. Run the script to generate the four review files.
    5. Post in #resonate-os with hashes for operator approval.
