# TASK-517 — GLM Independent Verification: TASK-409

**Reviewer:** TASK-517 on `qwen-worker-7-r9`
**Date:** 2026-09-29
**Target:** TASK-409 (GLM verification of TASK-294)
**Target branch:** `origin/qwen-worker-12-r9-sync`
**Branch HEAD SHA reviewed:** `3da4a246ee2536760d04dfc4d1d94b649160c2fa`
**Verified with:** `git rev-parse origin/qwen-worker-12-r9-sync` → `3da4a246ee2536760d04dfc4d1d94b649160c2fa` (matches)

---

## Verdict: REWORK — TASK-409's revised verdict is void

TASK-409's revised verdict on the target branch claims "SAFE TO MERGE" and asserts
that all three TASK-294 artifacts exist on `origin/qwen-worker-r9`. **They do not.**
The artifacts exist on a completely different branch. The original BLOCKED verdict
on master was correct for this branch.

---

## Finding 1: The artifacts do NOT exist on the target branch

**Severity: Critical — the verdict reviewed artifacts that are not on the branch.**

Established with multiple methods:

    git show 3da4a246:scripts/qa/check_lead_pack.py
    → fatal: path 'scripts/qa/check_lead_pack.py' does not exist in '3da4a246'

    git show 3da4a246:tests/test_a_pack_fact_must_belong_to_this_company.py
    → fatal: path does not exist

    git show 3da4a246:docs/QA-LEAD-PACK-2026-09-25.md
    → fatal: path does not exist

    git log --oneline 3da4a246 -- scripts/qa/check_lead_pack.py tests/test_a_pack_fact_must_belong_to_this_company.py docs/QA-LEAD-PACK-2026-09-25.md
    → (empty — zero history for these files on this branch)

    git diff master...3da4a246 --stat -- scripts/qa/ docs/QA-LEAD-PACK-2026-09-25.md
    → (no diff — the target branch contributes nothing for TASK-294)

**Disposition: CONFIRMED.** The target branch has zero TASK-294 artifacts.

---

## Finding 2: The artifacts do NOT exist where TASK-409 says they do

TASK-409's revised verdict states:

> "All three artifacts exist on `origin/qwen-worker-r9`"

Established:

    git show origin/qwen-worker-r9:scripts/qa/check_lead_pack.py
    → fatal: path does not exist

    git show origin/qwen-worker-r9:tests/test_a_pack_fact_must_belong_to_this_company.py
    → fatal: path does not exist

    git show origin/qwen-worker-r9:docs/QA-LEAD-PACK-2026-09-25.md
    → fatal: path does not exist

**Disposition: TASK-409's claim is FALSE.** The artifacts do not exist on
`origin/qwen-worker-r9`.

---

## Finding 3: The artifacts exist on a DIFFERENT branch

    git log --all --diff-filter=A -- scripts/qa/check_lead_pack.py
    → de44644e TASK-294: the per-lead research-pack QA check, with identity not presence

    git branch -a --contains de44644e
    → qwen-worker-r9-t391
    → remotes/origin/qwen-worker-r9-t391

    git merge-base --is-ancestor de44644e 3da4a246
    → NOT ANCESTOR

The artifacts exist on `qwen-worker-r9-t391` (commit `de44644e`), which is not
reachable from the target branch.

**Disposition: CONFIRMED.** The work exists but on a separate branch that the
target branch does not contain.

---

## Finding 4: TASK-409 cited orphaned commits

TASK-409's revised verdict cites commits `41d2a0ba`, `ace6085b`, `6f706daa`,
`3487aeee` as the implementation commits. These commits exist in the repo but:

    git branch -a --contains 41d2a0ba
    → (empty — not on ANY branch)

    git merge-base --is-ancestor 41d2a0ba 3da4a246
    → NOT ANCESTOR

    git merge-base --is-ancestor 41d2a0ba de44644e
    → NOT ANCESTOR (neither is ancestor of the other)

Commit `41d2a0ba` ("TASK-294: per-lead research-pack QA check and 32 tests") is an
orphan. It is a DIFFERENT implementation from the surviving `de44644e` (25 tests).
TASK-409 reviewed the orphaned version's metadata, not the surviving implementation.

**Disposition: CONFIRMED.** TASK-409's evidence chain points to commits that are
not on any branch and not on the target.

---

## Finding 5: The surviving implementation IS sound (on its own branch)

Despite being on the wrong branch for this verdict, the surviving artifact at
`de44644e` was independently verified:

### 5a. Tests pass: 25/25

    python -m unittest tests.test_a_pack_fact_must_belong_to_this_company -v
    → Ran 25 tests in 0.059s — OK

### 5b. Identity, not presence — CONFIRMED

The check imports `packfacts.identity_of` (line 56 of `check_lead_pack.py` on
`de44644e`) and uses `packfacts.pack_for` (line 214). `identity_of` returns three
separate verdicts: ADMITTED, REFUSED, UNVERIFIABLE. The check reports them
separately in `identity_totals` (line 300).

### 5c. The 50-of-71 shape is caught

Test `test_a_fact_from_a_different_domain_is_refused`:

    row = {"fact": "hiring 50 engineers",
           "source_url": "https://rival-corp.test/jobs",
           "companyWebsite": "https://rival-corp.test"}
    identity_of(row, "acme.test") → REFUSED

Test `test_a_lead_with_only_refused_facts_has_no_pack`:

    rec with research from other-corp.test → pack["facts"] == [], unused[REFUSED] == 1

### 5d. Falsification confirms wiring is real

Monkey-patching `packfacts.identity_of` to always return ADMITTED:

    Broken: pack_for(wrong_company_rec) → 1 admitted, 0 refused (WRONG)
    Real:   pack_for(wrong_company_rec) → 0 admitted, 1 refused (CORRECT)

The tests assert on behavior (identity verdicts), not on file existence or data
shape. Breaking the identity check changes test outcomes through the real code path.

### 5e. `packfacts.pack_for` has a real production caller

    src/bisonfactory.py:559: pack, _ = packfacts.pack_for(by_id.get(lead.get("record_id")))

The identity module is consumed in the send path. It is not disconnected.

### 5f. Test count discrepancy

TASK-409 claims "32 tests". The surviving artifact has 25. The orphaned `41d2a0ba`
has 32 (matching the claim). This confirms TASK-409 reviewed the orphaned version.

**Disposition: The work is real and sound, but it is on the wrong branch for this
verdict.**

---

## Finding 6: Merging the target branch would not delete source code

    git diff master...3da4a246 --diff-filter=D --name-only
    → docs/qwen-tasks/TODO/TASK-335-...
    → docs/qwen-tasks/TODO/TASK-405-...
    → docs/qwen-tasks/TODO/TASK-409-...
    → docs/qwen-tasks/TODO/TASK-415-...
    → docs/qwen-tasks/TODO/TASK-417-...
    → docs/qwen-tasks/TODO/TASK-418-...

All deletions are task files moved between stages (TODO → REVIEW/BLOCKED/DONE).
No source code, tests, or documentation would be deleted.

**Disposition: SAFE from a deletion perspective.**

---

## Finding 7: Scope — what the target branch actually carries

The target branch contributes 46 changed files vs master, including:

- TASK-245: nightly sourcing ends at candidates (scripts, tests, src changes)
- TASK-355: price cache tokens at their own rates (src/modelprices.py, test)
- TASK-272: explainable verdicts (tests, src changes)
- TASK-434: GLM verdict on TASK-245
- Various task file movements and new tasks (TASK-397, TASK-426, TASK-427)
- config changes (model-prices.yaml, clients/productive-offers.yaml)

TASK-294 is NOT among them.

---

## Summary of dispositions

| # | Finding | Disposition |
|---|---------|-------------|
| 1 | Artifacts not on target branch | CONFIRMED — voids the revised verdict |
| 2 | Artifacts not on `origin/qwen-worker-r9` | CONFIRMED — TASK-409's claim is false |
| 3 | Artifacts exist on `qwen-worker-r9-t391` | CONFIRMED — different branch |
| 4 | TASK-409 cited orphaned commits | CONFIRMED — not on any branch |
| 5 | Surviving implementation is sound | VERIFIED on its own branch (25/25 tests, identity not presence, falsifiable) |
| 6 | Merging would not delete source | CONFIRMED — only task file movements |
| 7 | Target branch carries other work | NOTED — TASK-245, TASK-355, TASK-272, etc. |

---

## Recommendation: REWORK

**TASK-409's revised verdict ("SAFE TO MERGE") is VOID.** It reviewed artifacts
that do not exist on the branch it was assigned to review, and cited commits that
are not on any branch.

**The original BLOCKED verdict on master was CORRECT** for this branch: the
TASK-294 artifacts were never on `qwen-worker-12-r9-sync` or `origin/qwen-worker-r9`.

**The work itself exists and is sound** on `qwen-worker-r9-t391` (commit `de44644e`):
25 tests pass, identity not presence, the 50-of-71 shape is caught, falsification
confirms the wiring is real, and `packfacts.pack_for` has a production caller in
`src/bisonfactory.py:559`.

**Claude action:**
1. Do NOT merge TASK-409's revised verdict — it is void.
2. The TASK-294 artifacts should be evaluated separately from `qwen-worker-r9-t391`
   if they are to be integrated.
3. The target branch `qwen-worker-12-r9-sync` carries other work (TASK-245, TASK-355,
   TASK-272) that may be cherry-picked independently.

---

## Protocol compliance

- [x] Reviewed exact HEAD SHA `3da4a246ee2536760d04dfc4d1d94b649160c2fa`, not branch name
- [x] Used isolated worktree (`.qwen/worktrees/task517-review`)
- [x] Falsified rather than confirmed (monkey-patched identity_of, verified test failure)
- [x] Checked for deletion risk (`--diff-filter=D`)
- [x] Cited file:line evidence
- [x] Marked unverified claims as UNVERIFIED
- [x] Read-only — zero provider calls, zero production mutations
- [x] Did not merge
