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
