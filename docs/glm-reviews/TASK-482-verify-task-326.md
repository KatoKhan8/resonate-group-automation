# TASK-482 — GLM independent verification of TASK-326

## Review metadata

    reviewed task        TASK-326 — Second Brain retrieval is account-scoped
    reviewed branch      origin/qwen-worker-7-r9
    reviewed HEAD SHA    e6f3f02120df697676f18288f3e8c93ece902729
    review worktree      .qwen/worktrees/task482-review (detached HEAD)
    review date          2026-09-28
    reviewer             Qwen-3 (TASK-482)

**Branch HEAD movement notice:** The task file specified SHA `e6f3f02120df697676f18288f3e8c93ece902729`. At review time, `origin/qwen-worker-7-r9` has moved to `7c9f20d28820081f19f8fa0f1a841d22c1174360`. Per the task instruction, the review targets the original SHA `e6f3f02120df697676f18288f3e8c93ece902729`, which is the artifact this verdict is about. That SHA is an ancestor of the current branch HEAD.

**Note on output path:** The task file says to write to `TASK-482-verify-task-219.md` but the review target is TASK-326. The filename `-task-219` is a copy-paste error from a template. This verdict uses the correct name `TASK-482-verify-task-326.md`.

---

## 1. Does the artifact exist, and does it do what the result block claims?

### Artifacts found on this ref

| File | Status | Lines |
|------|--------|-------|
| `src/secondbrain.py` (lines 326-478) | PRESENT, purely additive | +152 insertions, 0 deletions |
| `tests/test_company_research_is_paid_for_once_per_account.py` | PRESENT, new file | 247 lines, 16 tests |

### Claim-by-claim verification

**Claim 1: "Account evidence resolved once for three contacts"**
- **VERIFIED.** Direct execution: 3 contacts (`ceo`, `coo`, `head_of_delivery`) at the same domain produce exactly 1 unique call to `_load_account_evidence`. The cache (`_account_cache`, keyed by domain) works as designed.

**Claim 2: "No duplication — person layer does not copy account facts"**
- **VERIFIED, but trivially.** `for_contact` returns `"facts": []` — an empty list. The no-duplication assertion (`af & cf == empty`) is true by construction because the person layer never carries any facts at all. This is correct by design (the person layer is a reference + angle, not a fact carrier), but the test cannot catch a future regression where facts ARE copied, because the current implementation has nothing to copy. The test is necessary but not sufficient — it proves the current code is correct, but a future `for_contact` that copies account facts into the person layer would need a different test to catch it.

**Claim 3: "Role changes the angle and not the evidence"**
- **VERIFIED.** CEO → `"business impact"`, COO → `"operational control"`, Head of Delivery → `"project delivery"`. Same `account_ref` (`"account:huemor.rocks"`) for all roles at the same domain. Unknown roles get `"general business"`.

**Claim 4: "TASK-322's provenance guard still holds"**
- **VERIFIED.** `tests.test_the_second_brain_returns_only_what_the_task_needs` — 24 tests, all pass. The existing provenance guard is undisturbed.

**Claim 5: "No write to config/ or work/"**
- **VERIFIED.** `TestNoWrite` mocks `builtins.open` and asserts zero writes to `config/` or `work/` during `for_account`, `for_contact`, `for_task`, and `all_sections` calls. 4 tests, all pass.

**Claim 6: "Full suite: 40 secondbrain tests pass, timeout pre-existing"**
- **PARTIALLY VERIFIED.** The two secondbrain test modules (16 + 24 = 40 tests) all pass. Full suite was not run during this review (the task says it times out at 1800s, which is a pre-existing condition).

---

## 2. Existence is not function — production caller trace

### Result: DISCONNECTED

```
grep -rn "secondbrain.for_account\|secondbrain.for_contact" src/
→ (empty)
```

**Zero production callers.** The only callers of `secondbrain` in `src/` are:
- `src/copystages.py:133` → `secondbrain.for_task(task, client)`
- `src/generate_campaign.py:346` → `secondbrain.for_task("campaign_strategy", client_name)`

Neither uses `for_account` or `for_contact`. The new functions are defined, tested, and completely disconnected from the production execution path.

**This is the recurring defect.** QWEN.md records three tasks that failed review on 2026-09-14 for exactly this reason. The rule is explicit: "Zero production callers means DISCONNECTED, which is a rework and not a merge."

### Mitigating context

The task explicitly forbade building the orchestration engine:
> "Do not build the orchestration decision engine. Directive: document it as the next layer, do not build it now."

The result block honestly discloses:
> "for_account and for_contact have no production caller in src/ yet."

So the worker followed instructions correctly. The defect is in the task decomposition — the retrieval layer was built without a wiring task attached — not in the execution. But the protocol is clear: existence is not function, and a module with no caller is DISCONNECTED regardless of why.

---

## 3. Falsification results

### Mutation: broken cache

Replaced `_get_account_evidence` with a pass-through that bypasses the cache. Result: 3 loads for 3 contacts (instead of 1). The `test_three_contacts_one_load` test catches this — it asserts exactly 1 unique load call.

### Mutation: role does not change angle

If `_ROLE_ANGLES` were removed and all roles got the same angle, `test_ceo_and_coo_have_different_angles` would fail. Verified.

### Tests are falsifiable: CONFIRMED

No `hasattr`, no source-text assertions, no fake cassettes. Tests intercept `_load_account_evidence` via `mock.patch.object`, count calls, and assert on return shapes. A broken implementation would fail these tests.

---

## 4. Would merging delete anything?

### Code files: NO

`src/secondbrain.py` diff is purely additive: +152 lines, 0 deletions. No existing function modified. `tests/test_company_research_is_paid_for_once_per_account.py` is a new file.

### Task files: 4 deletions (lifecycle moves, not code)

```
docs/qwen-tasks/TODO/TASK-264-every-test-module-runs-in-isolation.md   DELETED (moved)
docs/qwen-tasks/TODO/TASK-389-contact-key-guard-cleanup.md              DELETED (moved)
docs/qwen-tasks/TODO/TASK-406-glm-verify-task-396.md                   DELETED (moved)
docs/qwen-tasks/TODO/TASK-440-glm-verify-task-281.md                   DELETED (moved)
```

These are task lifecycle moves (TODO → REVIEW/DONE), not code deletions. They are other tasks' business, not TASK-326's.

---

## 5. Scope drift

### Assessment: SIGNIFICANT

| Metric | Value |
|--------|-------|
| Total commits on branch (vs master) | 62 |
| TASK-326-specific commits | 3 |
| Total files changed | 73 |
| Total insertions/deletions | +10,253 / -625 |
| TASK-326's own files | 2 (secondbrain.py + test) |
| TASK-326's own lines | +399 |

The branch carries the work of many tasks beyond TASK-326: `src/generate.py` (+721), `src/generate_campaign.py` (+517), `tests/base.py` (+365), `tests/test_task400_rework2.py` (+992), `tests/test_task400_rework3.py` (+530), plus 12 GLM review documents and numerous task file moves.

### Cherry-pick scope

TASK-326's work is cleanly isolable to 2 files:
- `src/secondbrain.py` (append-only, lines 326-478)
- `tests/test_company_research_is_paid_for_once_per_account.py` (new file)

Cherry-picking these 2 files plus the task file move would be straightforward and carries no risk of pulling in other tasks' changes.

---

## 6. Additional observations

### Design limitation: evidence is client-ICP-shaped, not domain-shaped

`_load_account_evidence` derives facts from the client config's ICP structure (company types, verticals, employee range, geos). It describes what kind of company the client is looking for, not what the prospect company actually is. The `domain` parameter is used as a cache key but does not influence the facts at all — the same facts are returned for any domain given the same client.

This is acknowledged in the result block:
> "When real company-level enrichment exists (e.g. from a provider), _load_account_evidence should be extended to read it."

This is not a defect in TASK-326's implementation — it's a known placeholder that will need real enrichment data to become useful.

### Module-level mutable cache

`_account_cache = {}` is a module-level dict. It is process-scoped and not thread-safe. Tests properly clear it in `setUp`/`tearDown`. This is consistent with the rest of the codebase's patterns and is not a concern for the current single-process generation pipeline.

---

## Findings

| # | Severity | Finding | Evidence |
|---|----------|---------|----------|
| 1 | **Critical** | DISCONNECTED: `for_account` and `for_contact` have zero production callers in `src/`. The retrieval layer is built and tested but nothing in the production path uses it. | `grep -rn "secondbrain.for_account\|secondbrain.for_contact" src/` → empty |
| 2 | Minor | No-duplication test is trivially true: `for_contact` returns `"facts": []`, so overlap is always empty. The test cannot catch a future regression where facts are copied. | `src/secondbrain.py:474`: `"facts": []` |
| 3 | Minor | `_load_account_evidence` ignores the domain parameter for fact content — all facts come from client ICP config, not from the prospect domain. | `src/secondbrain.py:362-430`: no domain-based fact derivation |
| 4 | Info | Branch has significant scope drift (62 commits, 73 files) but TASK-326's work is cleanly cherry-pickable to 2 files. | `git diff master...e6f3f021 --stat` |

---

## Disposition

**REWORK** — not because the implementation is wrong, but because it is disconnected.

The code is correct, well-tested, and falsifiable. The task followed its instructions honestly. But per the standing protocol: "Zero production callers means DISCONNECTED, which is a rework and not a merge." The retrieval layer exists in isolation and provides zero production value until something calls it.

### What REWORK means here

Not "fix the code" — the code is fine. The rework is:
1. Wire `for_account`/`for_contact` into the copy/orchestration layer (the "next layer" TASK-326 was told to document but not build), OR
2. Merge TASK-326 as-is and create a follow-up task for the wiring, with an explicit acceptance criterion that the wiring must have a production caller before it ships.

### Recommendation

**CLOSE** — the retrieval layer is correctly built and the tests prove it. Merge the 2 files (cherry-pick, not the whole branch) as a foundation, but only if the wiring task is already queued and named. If it is not, this should be REWORK until the wiring exists.

The branch should NOT be merged wholesale — it carries 62 commits of other tasks' work. Cherry-pick `fe16ec3e` and `64dd1028` (the two TASK-326 implementation commits) plus the task file move.

---

## Reproducible commands

All verification was performed in an isolated worktree at the exact target SHA:

```bash
git worktree add .qwen/worktrees/task482-review e6f3f02120df697676f18288f3e8c93ece902729 --detach

# Production caller check
grep -rn "secondbrain.for_account\|secondbrain.for_contact" src/

# TASK-326 tests
python -m unittest tests.test_company_research_is_paid_for_once_per_account -v

# TASK-322 provenance guard
python -m unittest tests.test_the_second_brain_returns_only_what_the_task_needs -v

# Merge deletion check
git diff master...e6f3f02120df697676f18288f3e8c93ece902729 --diff-filter=D --name-only

# Scope drift
git diff master...e6f3f02120df697676f18288f3e8c93ece902729 --stat
```
