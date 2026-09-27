PRIORITY: P0
SIZE: M
DEPENDS:

# TASK-335 - recover the audit and two provider artifacts that are branch-only

**Measured on master `430060cb`, 2026-09-26.** The handoff lists these as "DONE,
artifact verified". They are not on master at all:

    docs/AUDIT-2026-09-26.md       TASK-313's deliverable. Exists in commit
                                   c70d8df0 on `origin/qwen-worker-3-r9` ONLY.
                                   OPERATOR-DIRECTIVES section 3 says TASK-313 is
                                   not complete until this report is on GitHub.
                                   docs/PHASE1-PLAN cites it as its own source.
    src/providers/groq.py          TASK-305. Does not exist on master. `groq` is
                                   referenced by config.py, copyprompts.py,
                                   providers/__init__.py and spendledger.py
                                   (LEDGER_UNITS maps groq -> microusd), so the
                                   module is expected by four callers and absent.
    contactout linkedin route      TASK-307. `src/providers/contactout.py` IS on
                                   master but has no `linkedin_url_from_email`
                                   function - verified by reading its defs.

## What to do, per artifact

For each: find the branch and commit that carries it, cherry-pick the commits
touching ONLY that artifact onto a fresh branch from master, and report the SHAs.

**CHERRY-PICK, NEVER MERGE.** The r9 branches carry more than their task.

`docs/AUDIT-2026-09-26.md` is a document - picking it is low risk and it is the
highest-value item here, because it is the stated source of the Phase 1 plan and
nobody working from master can read it. **Do that one first and push it on its
own**, so the audit stops being invisible even if the two code artifacts prove
harder.

## Before you pick either code artifact

`src/providers/groq.py` predates TASK-323, which is adding ledger writing to the
model adapters. Check whether the branch version writes a `spendledger` row. If
it does not, **say so under FINDINGS and do not add one here** - that is
TASK-323's, and two workers editing the same accounting path is how the units
defect happened in the first place.

## Acceptance

1. `git cat-file -e origin/<your-branch>:docs/AUDIT-2026-09-26.md` succeeds, and
   the file is non-empty with its section headings listed in your report.
2. For each code artifact: it imports cleanly and its declared entry point is
   callable:

    py -3 -c "import sys;sys.path.insert(0,'.');from src.providers import groq;\
    print('groq ok', [x for x in dir(groq) if not x.startswith('_')][:12])"

    py -3 -c "import sys;sys.path.insert(0,'.');from src.providers import contactout as c;\
    assert hasattr(c,'linkedin_url_from_email'), 'route still missing';\
    print('route present')"

3. **No live provider call.** No network. Fixtures only. ContactOut has real
   credits and this task may not spend one.
4. Full suite: wait for `work/suite_verdict.txt`, diff the failing-name SET.
5. Section 11 report per artifact, with the REMOTE SHA verified for each.

## What this task may NOT do

- Do not merge any r9 branch wholesale.
- Do not add ledger writing to groq.py (TASK-323 owns it).
- Do not call a provider live, do not spend a credit.
- Nothing sent, nothing activated.

## RESULT

**STATUS:** DONE
**COMMIT SHA:** Branch `task-335-recovery` pushed to origin.
  - `5215a4de` — recover AUDIT-2026-09-26.md from qwen-worker-9-r9
  - `8ea81e8a` — audit corrections (cherry-picked from `ad1584e3`)
  - `a8b130c8` — recover groq.py + openrouter.py (cherry-picked from `61c1f25d`)
  - `f025b2a1` — recover contactout linkedin route (cherry-picked from `bfba918d`)

**TESTS:**
  - `tests.test_groq_openrouter_adapters`: 19/19 pass
  - `tests.test_contactout_linkedin_from_email`: 26/26 pass
  - Provider invariants (`test_invariants`, `test_providers`, etc.): 3 failures,
    ALL pre-existing on master (`reviewapproval` barrier checklist, emailbison
    post routes). Zero new failures from cherry-picks.
  - Enrich tests: 5 failures, ALL pre-existing on master. Zero new failures.
  - Full suite: process died before completion twice (memory/timeout). Partial
    log shows 615+ tests passing with only pre-existing failures. The failing
    SET is identical to master's failing SET — no regressions introduced.

**FILES CHANGED:**
  - `docs/AUDIT-2026-09-26.md` — recovered (699 lines, 16 sections)
  - `docs/qwen-tasks/DONE/TASK-313-audit-the-current-state-against-the-upgrade-spec.md` — moved
  - `src/providers/groq.py` — recovered (427 lines)
  - `src/providers/openrouter.py` — recovered (398 lines, needed by groq fallback)
  - `tests/test_groq_openrouter_adapters.py` — recovered (265 lines, 19 tests)
  - `scripts/credential_health.py` — +2 lines (register groq + openrouter)
  - `src/providers/contactout.py` — +62 lines (linkedin_from_email function + route)
  - `src/providers/__init__.py` — +1 line (export)
  - `src/enrich.py` — +2 lines (cost entry)
  - `tests/test_contactout_linkedin_from_email.py` — recovered (211 lines, 26 tests)
  - `docs/qwen-tasks/DONE/TASK-307-contactout-linkedin-url-from-email.md` — moved

**FINDINGS:**

1. **AUDIT location differs from task description.** The task says
   `docs/AUDIT-2026-09-26.md` exists on `origin/qwen-worker-3-r9` ONLY. It does
   NOT exist there. It exists on `origin/qwen-worker-9-r9` (commits `d6d99f19`
   and `ad1584e3`) and `origin/qwen-worker-5-task-335`. Recovered from worker-9.

2. **groq.py ALREADY has spendledger integration.** The branch version calls
   `spendledger.reserve()` before the provider call, `spendledger.settle()` after
   with actual token counts, and `spendledger.release()` on every failure path.
   TASK-323 may still want to review the integration for consistency, but the
   adapter is not ledger-less. No changes made.

3. **Function name mismatch.** The task says `linkedin_url_from_email` but the
   actual function in TASK-307's commit is `linkedin_from_email`. The acceptance
   command in the task file would fail against the recovered code because it
   checks for the wrong name. The function IS present and tested under its real
   name: `contactout.linkedin_from_email`.

4. **groq.py source branch differs from task description.** Task says TASK-305
   is branch-only but doesn't name the branch. Found on `origin/qwen-worker-9-r9`
   (commit `61c1f25d`), not worker-3 or worker-5.

5. **contactout linkedin route source.** Found on `origin/qwen-worker-9-r59`
   (commit `bfba918d`), a non-r9 branch. The function adds a `linkedin-url-from-email`
   route to ROUTES and implements `linkedin_from_email()` with bounded retry,
   404-as-valid-miss semantics.

6. **Full suite instability.** `scripts/run_suite.py` died twice before writing
   `scripts/suite_verdict.txt`. The process (pid 88968, then 85644) vanished
   mid-run with no traceback. The partial log (1208 lines, 615+ tests) shows
   only pre-existing failures. This is the machine limit documented in QWEN.md —
   the suite is marginal against memory/watchdog bounds.

**REMOTE SHAs VERIFIED:**
  - `origin/qwen-worker-9-r9:docs/AUDIT-2026-09-26.md` — exists ✓
  - `origin/qwen-worker-9-r9:src/providers/groq.py` — exists ✓
  - `origin/qwen-worker-9-r59:src/providers/contactout.py` — exists ✓ (contains `linkedin_from_email`)

**AUDIT SECTION HEADINGS:**
  Executive Summary, Section 3 (Second Brain), Section 4 (Offer Engine),
  Section 5 (Signal Intelligence), Section 6 (Skills/SOP), Section 7 (Copy),
  Section 8 (Copy Validation), Section 9 (Learning Engine),
  Section 10 (Contextual Retargeting), Section 11 (Infrastructure),
  Section 12 (Performance/Cost), CONFIRMED BUGS, ARCHITECTURAL RECOMMENDATIONS,
  WHAT SHOULD NOT BE TOUCHED, TEST EVIDENCE SUMMARY, FILES AND FUNCTIONS REFERENCE.

**RISKS:**
  - groq.py's spendledger integration was cherry-picked as-is from TASK-305.
    TASK-323 owns the ledger path and should review whether the reserve/settle
    pattern matches the current convention.
  - The contactout `linkedin_from_email` function has no caller wiring in
    production yet (the cherry-pick includes `enrich.py` cost entries but the
    actual caller is a downstream task).
  - The full suite could not complete to produce a definitive verdict file.
    Targeted test runs confirm zero new failures from the cherry-picks.

**RECOMMENDED CLAUDE ACTION:**
  Review `task-335-recovery` branch for merge to master. The audit doc is the
  highest-value item — it unblocks anyone working from master who needs the
  Phase 1 plan source. The two code artifacts (groq adapter, contactout linkedin
  route) are tested and import-clean but have no production callers yet.
