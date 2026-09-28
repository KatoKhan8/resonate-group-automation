PRIORITY: P1
SIZE: M
DEPENDS:

# TASK-423 — failure taxonomy of the fifty's 37 non-passing leads

**Operator instruction, 2026-09-27, Qwen lane B.** Read-only analysis plus fixes
to UPSTREAM CAUSES. **This task may not edit any critical-path file** that
TASK-400, TASK-364 or TASK-372 is working: `src/generate.py`,
`src/generate_campaign.py`, `src/bisonfactory.py`, `src/heyreachfactory.py`,
`src/sequenceplan.py`, or the suite baseline. If a fix you find belongs in one of
those, write it up as a finding and stop; do not edit it.

## THE QUESTION

Of the fifty leads, 13 were written and 37 did not pass. Nobody has a
per-lead reason. "37 failed" is not actionable; "19 failed at RESEARCH because
the crawler returned navigation furniture" is.

Assign **exactly one PRIMARY reason code and one stage** to each of the 37.
One primary, even where several things are wrong: the Pareto table is worthless
if every lead carries four reasons.

Stages, in pipeline order:

    INPUT           the row as it arrived: missing or malformed field, bad domain
    RESEARCH        nothing usable crawled or fetched, or unusable quality
    QUALIFICATION   ICP verdict rejected, review, or unknown
    STRATEGY        no offer selected, no angle, no step objectives
    GENERATION      the model produced nothing, or refused
    RENDER          produced but variables did not render
    COPYLINT        rendered but refused by copylint
    SEQUENCEGATE    passed copylint but refused by sequencegate

## DELIVERABLES

1. **A per-lead table**: lead identifier (use the record id or a hash, NEVER an
   email address or a person's name in a committed file), stage, primary reason
   code, one line of evidence for that classification.
2. **A Pareto table**: reason code by count, descending, with the cumulative
   percentage, so the largest upstream cause is unambiguous.
3. **A fix list**, ordered by how many leads each fix unblocks, naming the file
   and the upstream cause for each.

## THE 13 UNRENDERED VARIABLES ARE A PIPELINE DEFECT

The operator is explicit: `unrendered_variable` on 13 of the 31 written leads is
a defect in the pipeline, not a copy problem and not a lint problem. Find WHY the
variable had no value at render time: was it never collected, collected under a
different key, collected for a different contact, or overwritten. Report the
mechanism, not the symptom.

## THE RULE THAT OUTRANKS FINISHING

**Fix upstream causes. Never loosen a gate.** A lead that copylint refused is
evidence that generation produced something it should not have. Widening the lint
so it passes converts a caught defect into a shipped one. If you believe a gate
is genuinely wrong, that is a finding for Claude, not an edit.

## WHAT THIS TASK MAY NOT DO

- No send, activate, resume, enrol or attach. Provider writes zero.
- **Never commit a prospect email address, personal name or phone number.** The
  fifty are real people. Use record ids or hashes. `work/` stays gitignored and
  nothing is copied out of it into a committed file.
- No edits to the critical-path files listed above.
- Do not loosen copylint, sequencegate, qualification or suppression.

## ACCEPTANCE

The Pareto table accounts for all 37 leads with exactly one primary reason each,
the counts sum to 37, and each fix in the list names a file and an upstream cause.
A taxonomy where the largest bucket is "other" or "unknown" is not done.

---

## RESULT BLOCK

**STATUS:** REVIEW
**COMMIT SHA:** 433fcc76
**TESTS:** N/A — read-only analysis task, no code changes to test
**FILES CHANGED:**
- `docs/TASK-423-FAILURE-TAXONOMY.md` — the taxonomy document (NEW)
- `docs/qwen-tasks/REVIEW/TASK-423-failure-taxonomy-of-the-fifty.md` — moved from TODO

**ARTIFACT KIND:** document (analysis + findings)

**FINDINGS:**

1. The Pareto table accounts for all 37 leads: 13+13+4+3+2+2 = 37.
2. Two causes dominate: `not_an_agency` (13, 35.1%) and `unrendered_variable`
   (13, 35.1%), together 70.3% of all failures.
3. The `{firstName}` unrendered variable is a RENDER-stage defect: the Sonnet
   writer outputs `{firstName}` as a literal token in LinkedIn messages, and no
   post-generation substitution replaces it with the actual name. The name WAS
   available — it was in the writer prompt.
4. `fifty-data.json` is missing from all worktrees. Analysis was reconstructed
   from the posted HTML/XLSX review files and `sample50-built.json`.
5. The copylint expansion (TASK-378) to include LinkedIn messages was
   load-bearing — without it, 13 leads would ship with `{firstName}` visible.
6. No critical-path files were edited. No gates were loosened. No PII committed.

**RISKS:**
- The 8 "copylint-only" leads (passed sequencegate, refused by re-lint) are
  classified from TASK-342's numbers, not from direct measurement. The source
  data (`fifty-data.json`) is missing.
- 3 of the 6 sequencegate `channels_complement` failures also had unrendered
  variables and are classified at RENDER (earlier stage). Fixing the unrendered
  variable would expose the sequencegate failure underneath.

**RECOMMENDED CLAUDE ACTION:**
1. Fix the `{firstName}` substitution (Fix 1, 13 leads)
2. Integrate list pre-filtering (Fix 2, 13 leads)
3. Preserve pipeline output artifacts as durable state
