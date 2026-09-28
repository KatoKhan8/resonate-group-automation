# TASK-456 — Independent verification of TASK-304

## Review coordinates

    Reviewed branch     origin/qwen-worker-4-task304-review-file
    Branch HEAD SHA     1a82ed63b6e4b1f48559bbdd4838a2900399fef4
    Verified            2026-09-28
    Review worktree     .qwen/worktrees/glm-task456 (detached at 1a82ed63, since removed)
    Reviewer            Qwen (TASK-456)

The branch HEAD SHA was verified with `git rev-parse` before any review work
began. It matches the SHA named in the task file.

---

## Finding 1 — Artifact existence

**VERIFIED.** Four new files exist on the exact ref:

| File | Lines | Status |
|---|---|---|
| `src/reviewfile.py` | 501 | Added |
| `scripts/build_review_file.py` | 325 | Added |
| `tests/test_review_file.py` | 376 | Added |
| `tests/test_build_review_file.py` | 295 | Added |

The task file moved from `docs/qwen-tasks/TODO/` (deleted, 23 lines) to
`docs/qwen-tasks/REVIEW/` (added, 113 lines with result block). This is the
correct lifecycle transition.

No pre-existing files were modified or deleted.

---

## Finding 2 — The artifact does what the result block claims

**VERIFIED, with one caveat on scope.**

Claims checked:

1. **Column spec matches TASK-301** — VERIFIED. `BASE_COLUMNS` carries
   sender_mailbox, sender_name, lead_email, name, title, company, cohort_tag,
   persona. `step_columns(n)` produces subject+body pairs dynamically.
   `PACK_COLUMNS` carries the personalisation block. `LINKEDIN_COLUMNS` are
   conditional. Tests `test_base_columns_present`, `test_step_columns_for_three_steps`,
   `test_pack_columns_always_present`, `test_linkedin_columns_added_when_flagged`
   all assert on the actual column lists.

2. **Three steps, not five** — VERIFIED. `step_columns(3)` produces exactly 6
   columns (3 subjects + 3 bodies). `test_three_steps_not_five` asserts
   `step_4_subject` and `step_5_body` are absent.

3. **Pack facts expand** — VERIFIED. `expand_pack_rows()` produces N rows for
   N facts, with lead columns repeated. `test_multiple_facts_expand` asserts
   3 facts → 3 rows with correct USED/NOT USED labels and lead data on
   expanded rows.

4. **Held leads, not blank** — VERIFIED. `build_from_provider_data()` checks
   `subject_1`/`body_1` presence and appends to `held[]` instead of rendering.
   `test_build_held_leads_without_copy` asserts rendered_count=0, held_count=2.

5. **XLSX is valid** — VERIFIED. `to_xlsx()` produces a valid zip with
   `[Content_Types].xml`, `xl/workbook.xml`, `xl/worksheets/sheet1.xml`,
   `xl/sharedStrings.xml`. `test_valid_zip` and `test_contains_expected_parts`
   assert on the zip structure.

6. **Hash is sha256[:16]** — VERIFIED. `compute_hash()` delegates to
   `reviewapproval.file_hash()`, which is documented as "sha256, hex, first 16
   characters". `test_hash_is_16_chars` asserts length 16.

**Caveat:** The result block claims "DONE - Stage 1 complete, Stage 2 owed".
Stage 2 (provider data collection, variable write for 83 leads, actual
generation for campaigns 491-498) is explicitly listed as Claude's job. This
is honest and the scope is clear.

---

## Finding 3 — Production callers (the "existence is not function" check)

**PARTIALLY DISCONNECTED, but the hash chain IS wired.**

The call graph:

```
scripts/build_review_file.py
  └── from src import reviewfile        (line 83)
        └── reviewfile.build()          (line 248)
        └── reviewfile.write()          (line 302)

src/reviewfile.py
  └── from . import reviewapproval      (line 40)
        └── reviewapproval.file_hash()  (line 439, in compute_hash)

src/providers/bison.py
  └── reviewapproval.require()          (lines 1439, 1886)

src/providers/heyreach.py
  └── reviewapproval.require()          (line 1691)
```

**What IS connected:** The hash that `reviewfile.compute_hash()` produces is
the same hash that `reviewapproval.require()` checks before allowing a
provider write. The operator approves by hash (`APPROVED 491 <hash>`), and
the provider modules refuse to activate without that approval. The hash chain
from generator → approval → provider gate is intact.

**What is NOT connected:** `scripts/build_review_file.py` is a CLI tool. No
module in `src/` calls it programmatically. It is invoked manually with
`python -m scripts.build_review_file <ids> --provider-data <path>`. This is
by design for a review file (the operator reviews it manually), but it means
there is no automated pipeline step that generates the file.

**Assessment:** This is not the "computed correctly but nothing downstream
reads it" defect from the recurring defect pattern. The generator's output
(the hash) IS read by the production gate. The generator itself is a CLI
tool, not a pipeline component. The task explicitly acknowledges the missing
integration as "Stage 2 owed".

**Risk:** If Stage 2 is never done, the generator exists but is never used
for its intended purpose (producing review files for campaigns 491-498).
This is a workflow gap, not a code defect.

---

## Finding 4 — Test falsifiability

**VERIFIED.** Mutation test performed:

- **Mutation:** Changed `has_copy = (variables.get("subject_1") or variables.get("body_1"))`
  to `has_copy = True` in `build_from_provider_data()`, removing the
  held-lead guard.
- **Result:** Two tests failed immediately:
  - `test_build_held_leads_without_copy`: expected rendered_count=0, got 2
  - `test_build_mixed_held_and_rendered`: expected rendered_count=2, got 4
- **Conclusion:** The tests correctly detect the removal of the
  safety-critical guard that prevents blank sends. They fail for the intended
  reason (leads that should be held are rendered instead).

Additional falsifiability checks:

- Tests assert on column lists, not source text.
- Tests assert on XLSX zip structure, not hasattr.
- Tests assert on hash length and determinism, not token presence.
- Tests assert on held/rendered counts, not function existence.
- The CLI test (`test_main_with_provider_data`) drives through `main()` with
  a real provider data JSON and verifies output files exist.

**Not accepted as proof (but not what the tests do):** None of the tests use
hasattr, source-text assertions, or fake cassettes. All assert on behavior.

---

## Finding 5 — Merge safety

**SAFE.** `git diff master...1a82ed63 --name-status`:

```
A  docs/qwen-tasks/REVIEW/TASK-304-the-491-498-retroactive-review-files.md
D  docs/qwen-tasks/TODO/TASK-304-the-491-498-retroactive-review-files.md
A  scripts/build_review_file.py
A  src/reviewfile.py
A  tests/test_build_review_file.py
A  tests/test_review_file.py
```

- No existing `src/` files modified or deleted.
- No existing `scripts/` files modified or deleted.
- No existing `tests/` files modified or deleted.
- Task file moved TODO → REVIEW (correct lifecycle).
- Total: 4 new files added, 1 task file moved. 1610 insertions, 23 deletions.

Merging would NOT delete any existing code.

---

## Finding 6 — Scope drift

**CLEAN.** The branch carries only TASK-304 work. The commits are:

```
1a82ed63 TASK-304 to REVIEW: review file generator done, Stage 2 owed
45eef1c4 TASK-304: review file generator for campaigns 491-498
99193b5b Move TASK-304 to RUNNING
```

Three commits, all TASK-304. No unrelated changes. No junk. Cherry-pick
would be straightforward if needed (but merge is clean).

---

## Finding 7 — Dependency on reviewapproval

**VERIFIED.** `src/reviewfile.py` imports `reviewapproval` (line 40) and
delegates `compute_hash()` to `reviewapproval.file_hash()`. The
`reviewapproval` module exists on the branch and is consumed by production
code:

- `src/providers/bison.py:1439` — `reviewapproval.require(campaign_id)`
- `src/providers/bison.py:1886` — `reviewapproval.require(campaign_id)`
- `src/providers/heyreach.py:1691` — `reviewapproval.require(campaign_id)`

The dependency is legitimate and the hash function is shared between the
generator and the approval gate.

---

## Disposition

**MERGE.**

The generator is well-built, well-tested, and implements the TASK-301 column
spec correctly. The hash chain is connected to the production approval gate
through `reviewapproval`. The tests are falsifiable (mutation test confirmed).
The branch is clean and merge-safe.

The generator has no programmatic caller in `src/` because it is a CLI tool
by design. The task explicitly acknowledges the remaining integration work
(Stage 2: provider data, variable write, generation) as Claude's job. This
is a workflow gap, not a code defect.

**Conditions:**

1. Stage 2 must be tracked and done. The generator is useless without the
   provider data and variable write for the 83 blank leads.
2. The operator must be told the generator exists and how to invoke it once
   Stage 2 is done.

**What would change my verdict:**

- If the tests were not falsifiable (e.g., asserted on source text or
  hasattr), I would recommend REWORK.
- If the hash chain were not connected to `reviewapproval.require()`, I
  would recommend REWORK (the generator would be truly disconnected).
- If the task had claimed "DONE, artifact verified" without acknowledging
  Stage 2, I would recommend REWORK (dishonest result block).

None of these apply. The task is honest, the code is correct, the tests are
real, and the hash chain is wired.

---

## Reproducible commands

```bash
# Verify the SHA
git rev-parse origin/qwen-worker-4-task304-review-file

# Run the tests
git worktree add .qwen/worktrees/glm-task456 1a82ed63 --detach
cd .qwen/worktrees/glm-task456
python -m unittest tests.test_review_file tests.test_build_review_file -v

# Check for production callers
git grep -n "reviewfile" 1a82ed63 -- src/ scripts/ | grep -v test_
git grep -n "reviewapproval.require" 1a82ed63 -- src/

# Check merge safety
git diff master...1a82ed63 --name-status
```
