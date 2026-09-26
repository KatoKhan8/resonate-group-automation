PRIORITY: P1
SIZE: M
DEPENDS:

# TASK-353 - docs and handoff hygiene

**Operator instruction, 2026-09-26:** docs and handoff hygiene.

This project's docs are operational instructions - an operator acts on them - so
a false statement is a defect, not a typo. Two were found on 2026-09-26 and are
already fixed; this task sweeps for the rest.

**Already fixed, do not redo:** `CLAUDE.md`'s headline (it named a 09-22 handoff
as current state and claimed both channels were sending), and the
`.gitignore` / QWEN.md worker-discipline rules.

**Already filed, do not duplicate:** TASK-336 (stale derived state in
`docs/state/`), TASK-337 (three undocumented credentials), TASK-343 (the preview's
invented LinkedIn days).

## What to sweep

Every load-bearing factual claim in the top-level `*.md` files and `docs/*.md`. A
claim is load-bearing if an operator would ACT differently depending on whether
it is true.

Known-suspect classes, from the 2026-09-26 findings:

1. **"DONE, artifact verified" claims.** The 09-26 handoff listed 13 such tasks;
   only 2 were in `DONE/`, and the artifacts for TASK-305, TASK-307 and TASK-313
   do not exist on master at all. **Check every such claim against
   `origin/master`, not against a branch.** Report each one that fails.
2. **Modules described as wired that have no caller.** `sequencegate`,
   `copystages` and `copyprompts` have ZERO real importers across `src/` and
   `scripts/`; `secondbrain` has one whose own caller count is zero. Any doc
   saying otherwise is false.
3. **Files named in plans that do not exist.** `docs/PHASE1-PLAN-2026-09-26.md`
   instructs work on `src/copypath.py` and `src/copyengine.py`. Neither is on
   master or any branch tree. Report every such reference.
4. **Acceptance snippets that would fail if run.** The plan's TASK-321 snippet
   asserts `'copystages' in src` over concatenated source text - it is a
   substring match that cannot prove wiring, and it already fails on master.
   **Run every documented command and report the ones that fail.**
5. **Superseded documents not marked as such.** Say which handoff is current and
   mark the rest superseded in their own first lines.

## Deliverable

    docs/DOC-TRUTH-SWEEP-2026-09-26.md   NEW

One row per false or unverifiable claim: the file, the quote, the contradicting
evidence, and the severity. **Fix only the unambiguous ones** - a stale date, a
path that does not exist, a superseded-document marker. Anything requiring a
judgement about what the truth IS goes under FINDINGS for the operator.

## Acceptance

1. Every documented command you ran, with its real exit status. A command that
   fails is a finding; do not fix it by editing the command to something that
   passes without checking what it was meant to prove.
2. Each "artifact verified" claim checked with `git cat-file -e origin/master:<path>`,
   with the result per claim.
3. The sweep file exists, is committed, and is verified on `origin/master`.
4. **Do not write a claim you have not checked.** This task's whole value is that
   its statements are verified; an unverified row in a truth sweep is worse than
   an absent one.

## What this task may NOT do

- Do not rewrite `CLAUDE.md`'s rules, `PLAYBOOK.md`, or any operator directive
  file. Correct a false FACT; never edit a rule. A rule you disagree with goes
  under FINDINGS.
- Do not delete a superseded document - mark it.
- Do not touch the posted, hashed review files.
- Nothing sent, nothing activated.

---

## RESULT

**STATUS:** REVIEW
**COMMIT:** 297cd5e6
**BRANCH:** qwen-worker-9-r68
**REMOTE:** https://github.com/KatoKuan8/resonate-group-automation/tree/qwen-worker-9-r68

**ARTIFACT KIND:** document (docs/DOC-TRUTH-SWEEP-2026-09-26.md) + 5 superseded
markers on existing docs.

### TESTS

No test suite run. This is a read-only doc sweep with targeted edits.
Verification commands and their exit statuses are recorded in the sweep
document under "COMMANDS RUN AND EXIT STATUSES".

### FILES CHANGED

    docs/DOC-TRUTH-SWEEP-2026-09-26.md     NEW — the sweep report
    docs/CLAUDE-HANDOFF.md                  MODIFIED — added SUPERSEDED marker
    docs/CONTEXT-RESET-2026-09-14.md        MODIFIED — added SUPERSEDED marker
    docs/CONTEXT-RESET-2026-09-14-B.md      MODIFIED — added SUPERSEDED marker
    docs/CONTEXT-RESET-2026-09-14-C.md      MODIFIED — added SUPERSEDED marker
    docs/CONTEXT-RESET-2026-09-15-D.md      MODIFIED — added SUPERSEDED marker

### FINDINGS

**CRITICAL:**
- 11 of 13 "DONE, artifact verified" claims in the 09-26 handoff are false.
  Only TASK-216 and TASK-317 are in DONE/. Artifacts for TASK-305 (no
  src/providers/groq.py), TASK-307 (no linkedin_url_from_email function),
  TASK-313 (no docs/AUDIT-2026-09-26.md), and TASK-279 (no scripts/pack_fetch.py)
  do not exist on master at all.

**HIGH:**
- PHASE1-PLAN TASK-321 instructs MODIFY on src/copypath.py and src/copyengine.py.
  Neither exists on origin/master (exit 128 for both).
- TASK-322 (in DONE/) claims "copystages/copypath is the consumer". copypath.py
  does not exist. copystages has zero callers.
- Two provider-answers files named in the handoff (apify-actor-limits.md,
  cheapverifier-rate-limits.md) are missing on master.

**MEDIUM:**
- PHASE1-PLAN TASK-321 acceptance snippet fails: AssertionError, exit 1.
  'copystages' does not appear in any src/*.py file content.

**LOW (fixed):**
- 4 context-reset docs and CLAUDE-HANDOFF.md lacked superseded markers. Now
  marked. Current state: CONTEXT-RESET-2026-09-15-E.md.

**Requires operator judgement (NOT fixed):**
- The handoff §8 list must be rewritten to reflect actual task states.
- PHASE1-PLAN must be updated to name real paths or the missing files must
  be recreated.
- TASK-322 DONE status may need to be re-opened.
- QWEN.md says CLAUDE-HANDOFF.md is "the current durable truth" but it is
  12 days stale. The reference should point to CONTEXT-RESET-2026-09-15-E.md.

### RISKS

- The superseded markers are additive and do not change any document's content.
  Low risk.
- The sweep document reports findings but does not fix them (except superseded
  markers). Operator must decide on the remaining items.

### RECOMMENDED CLAUDE ACTION

1. Correct the handoff §8 "DONE, artifact verified" list.
2. Update PHASE1-PLAN TASK-321 to name real file paths.
3. Decide on TASK-322: re-open or add corrective note.
4. Update QWEN.md to reference CONTEXT-RESET-2026-09-15-E.md as current state.
5. Recover or re-create the missing provider-answers files.
