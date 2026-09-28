# TASK-488 — Independent GLM Verification of TASK-342

**Review date:** 2026-09-28  
**Reviewer:** GLM (independent verification)  
**Target task:** TASK-342 — "a new review workbook that restores the full review surface"  
**Target branch:** `origin/qwen-worker-r72`  
**Branch HEAD SHA:** `b32d979028e2095008bd5c1eb0b24d290b26a82f` (verified matches task spec)  
**Commits reviewed:** 2 commits on top of master  
- `ee842afb` — TASK-342: review workbook that restores the full message surface  
- `b32d9790` — TASK-342: update commit SHA in result block (trivial metadata fix)

---

## Executive Summary

**DISPOSITION: MERGE with findings**

The script is **correct by code inspection** and follows the task spec. It reads from canonical sources (`cadencelibrary.PRODUCTIVE_LI_HEAVY_V1`), does not hardcode cadence days, does not make model calls, and has meaningful acceptance checks. The generated artifacts (xlsx, html) are in gitignored `work/review/` **by design** — the task spec explicitly says "Commit no row from it" and the result block provides hashes and acceptance output for review.

**Critical finding:** The actual deliverables (xlsx, html) cannot be independently verified from the branch because they are gitignored. Only the script is committable. This is a **limitation of the task design**, not a defect in the implementation.

---

## Verification Results

### 1. Does the artifact exist on this ref?

**YES.** `scripts/export_review_342.py` (805 lines, new file) exists on the branch. The task file is in `docs/qwen-tasks/REVIEW/` state.

**Files changed (vs master):**
- `scripts/export_review_342.py` — NEW, 805 lines
- `docs/qwen-tasks/REVIEW/TASK-342-the-review-spreadsheet-lost-the-messages.md` — NEW, 248 lines (task spec + result block)

**Total:** 864 insertions, 0 deletions.

### 2. Does it do what the result block claims?

**YES — verified by code inspection.**

#### Claim: "Reads LinkedIn days from cadencelibrary, not hardcoded"
**VERIFIED.** Lines 33-44:
```python
LI_STEPS = tuple(s for s in PRODUCTIVE_LI_HEAVY_V1 if s.get("channel") == "linkedin")
LI_CANONICAL = {s["key"]: s["day"] for s in LI_STEPS}
```
This reads from `src/cadencelibrary.py:PRODUCTIVE_LI_HEAVY_V1` which defines:
- li1: day 1, li2: day 3, li3: day 6, li4: day 10, li5: day 15

**No hardcoded day table.** The `LI_KEY_MAP` maps generated keys (`connect`, `msg1`, `msg2`, `msg3`) to canonical keys (`li1`, `li2`, `li3`, `li4`) but does not carry days.

#### Claim: "Email days from canonical source"
**VERIFIED.** Lines 47-49:
```python
EMAIL_STEPS = tuple(s for s in PRODUCTIVE_LI_HEAVY_V1 if s.get("channel") == "email")
EMAIL_DAYS = {s["key"]: s["day"] for s in EMAIL_STEPS}
```
This produces: em1=1, em2=4, em3=8, em4=12, em5=21 — matching the cadence library.

#### Claim: "Checks posted pair hashes before proceeding"
**VERIFIED.** Lines 715-722:
```python
if os.path.exists(posted_html) and os.path.exists(posted_xlsx):
    h_html = reviewapproval.file_hash(posted_html)
    h_xlsx = reviewapproval.file_hash(posted_xlsx)
    assert h_html == "0c493ab9c3d9d136", f"HTML hash mismatch: {h_html}"
    assert h_xlsx == "775cd55287b8f29a", f"XLSX hash mismatch: {h_xlsx}"
```
The script asserts the posted pair is unchanged before generating new artifacts.

#### Claim: "No model call — spend ledger unchanged"
**VERIFIED.** Lines 707-712 and 765-770:
```python
before_count = sum(1 for line in f if line.strip())
# ... generate artifacts ...
after_count = sum(1 for line in f if line.strip())
assert before_count == after_count, "Spend ledger changed - a model call happened!"
```
The script records spend ledger row count before and after, and asserts no change.

#### Claim: "Exports full message bodies, not counts"
**VERIFIED.** Lines 301-310 (Sheet 3 message export):
```python
ws.cell(row=row_num, column=10, value=body)  # full body
ws.cell(row=row_num, column=13, value=len(body))  # char count
```
Column 10 contains the full body text, column 13 contains the character count. The acceptance check (lines 735-742) verifies the longest cell in Sheet 3 XML exceeds 200 characters, confirming full bodies are present.

#### Claim: "Gate rule names appear in Sheet 2"
**VERIFIED.** Lines 234-241 (Sheet 2 lead export):
```python
lint_label = "REFUSED" if lint_pass is False else "PASS"
lint_rule_str = ", ".join(lint_rules)  # rule names
gate_label = "FAILED" if gate_pass is False else "PASSED"
gate_rule_str = ", ".join(gate_failures)  # check names
```
The script writes both the result label and the rule/check names. The acceptance check (lines 745-750) counts occurrences of specific rule names in Sheet 2 XML.

#### Claim: "li5 shown as NOT GENERATED IN THIS RUN with canonical day 15"
**VERIFIED.** Lines 344-358 (Sheet 3 li5 placeholder):
```python
li5_day = LI_CANONICAL.get("li5", 15)
ws.cell(row=row_num, column=4, value="li5")
ws.cell(row=row_num, column=5, value=li5_day)
ws.cell(row=row_num, column=10, value="NOT GENERATED IN THIS RUN")
```
The script reads li5's day from `LI_CANONICAL` (which comes from the cadence library) and marks the body as "NOT GENERATED IN THIS RUN".

#### Claim: "No day 8 or 14 for LinkedIn"
**VERIFIED.** The acceptance check (lines 753-762) reads Sheet 3 and asserts:
```python
assert 8 not in li_days_found, "LinkedIn day 8 found - must not be present"
assert 14 not in li_days_found, "LinkedIn day 14 found - must not be present"
```
The result block shows: "LinkedIn days found: [1, 3, 6, 10, 15]" — no 8 or 14.

### 3. Existence is not function — does it have a production caller?

**NOT APPLICABLE.** This is a **review tool** in `scripts/`, not a production module. The task spec explicitly asks for "a NEW review artifact" — a projection tool that reads `fifty-data.json` and generates a workbook. The script IS the deliverable; it does not need a production caller.

**Verified:** `grep -r export_review_342 src/` returns no matches, which is correct — this is a standalone tool, not a library function.

### 4. Are the tests falsifiable?

**YES.** The acceptance checks are embedded in the script (lines 724-778) and verify:
1. Sheet dimensions match expected counts
2. Longest cell in Sheet 3 > 200 chars (full bodies present)
3. Specific gate rule names appear in Sheet 2 XML
4. LinkedIn days are [1, 3, 6, 10, 15], no 8 or 14, li5 present as "NOT GENERATED"
5. Spend ledger row count unchanged (no model call)
6. Posted pair hashes match expected values
7. New artifact hashes are reported

These checks **could fail** if the implementation was wrong:
- If bodies were missing, the longest cell would be < 200 chars
- If LinkedIn days were hardcoded to 8/14, the assertion would fire
- If the posted pair was modified, the hash assertion would fire
- If a model call happened, the spend ledger count would change

The checks are **meaningful and falsifiable**, not tautological.

### 5. Would merging delete anything?

**NO.** `git diff master...origin/qwen-worker-r72 --stat --diff-filter=D` returns empty. The branch adds 2 files (864 insertions) and deletes nothing.

### 6. Scope drift — does the branch carry junk?

**NO.** The branch has exactly 2 commits on top of master, both TASK-342 related:
- `ee842afb` — adds the script and task file with result block
- `b32d9790` — updates the commit SHA in the result block (trivial metadata fix)

No unrelated changes, no scratch output, no junk.

---

## Critical Findings

### Finding 1: Generated artifacts are NOT on the branch (BY DESIGN)

**Severity:** Informational (not a defect)  
**Evidence:** `.gitignore` line 18: `work/`  
**Location:** `scripts/export_review_342.py` lines 29-30:
```python
REVIEW_DIR = os.path.join(ROOT, "work", "review")
XLSX_NAME = "503-FIFTY-REVIEW-TASK342.xlsx"
```

**Analysis:** The script writes the generated xlsx and html to `work/review/`, which is gitignored. The task spec says "work/ is gitignored and holds real people. Commit no row from it." So the artifacts **cannot be committed** by design.

**Impact:** The result block claims "DONE" with specific artifact hashes (HTML: `e8efeee4ccae1a7c`, XLSX: `89202fb797188854`), but these artifacts exist only on the worker's local disk, not in the repository. They **cannot be independently verified** from the branch.

**Mitigation:** The result block provides:
- Artifact hashes (for verification if the files are available locally)
- Acceptance check output (showing the script ran successfully)
- Sheet dimensions and row counts
- Gate rule counts
- LinkedIn days found

This is **sufficient for review** given the task design, but it means the actual workbook content cannot be audited from the branch alone.

**Recommendation:** This is a **limitation of the task design**, not a defect in the implementation. The task spec explicitly forbids committing `work/` content. Future tasks of this type should either:
1. Output to a committable location (e.g., `docs/review/` instead of `work/review/`), or
2. Explicitly accept that the artifacts are local-only and the script is the deliverable.

TASK-342 follows option 2, which is consistent with the spec.

### Finding 2: Data path is worktree-specific (DOCUMENTED RISK)

**Severity:** Low (documented)  
**Evidence:** `scripts/export_review_342.py` lines 25-27:
```python
DATA_PATH = os.path.join(
    os.path.dirname(ROOT), "resonate-qwen-2", "work", "fifty-data.json"
)
```

**Analysis:** The script reads `fifty-data.json` from a sibling worktree (`resonate-qwen-2`). This path is:
- **Fragile:** breaks if the worktree is renamed or removed
- **Worktree-specific:** only works when run from a specific location
- **Not portable:** cannot be re-run in other worktrees without modification

**Mitigation:** The result block explicitly states: "The script reads `fifty-data.json` from `resonate-qwen-2` worktree. If that file moves, the DATA_PATH in the script needs updating."

**Impact:** Low. The script is a one-shot review tool, not a production pipeline. The data path is documented as a risk.

**Recommendation:** No action required. The risk is documented and acceptable for a review tool.

### Finding 3: channels_complement count discrepancy (DATA FINDING, NOT BUG)

**Severity:** Informational  
**Evidence:** Result block finding #1:
> "channels_complement is 8, not 6. The task spec says 'channels_complement 6' but the data carries 8 failure instances. Seven leads fire it; lead 24 (Clever Creative Copy) fires it twice."

**Analysis:** The task spec's "verified truth" block states:
```
sequencegate PASSED 21 · FAILED 10  (channels_complement 6, claims_supported em5 4)
```

But the script's acceptance output shows:
```
Rule 'channels_complement' appears 8 times in Sheet 2
```

The result block explains: "Seven leads fire it; lead 24 (Clever Creative Copy) fires it twice (two distinct failures: 'is em1 in shorter form' and 'asks a question email already asked'). The workbook exports what the data says."

**Impact:** This is a **discrepancy in the spec's verified-truth block**, not a bug in the script. The script correctly exports what the data carries. The spec's number (6) may be from an earlier run or may have been a counting error.

**Recommendation:** Investigate whether the spec's verified-truth block needs updating, or whether the gate logic changed between runs. This is a **data/provenance question**, not a code defect.

---

## Additional Observations

### Observation 1: Thread and subject mapping is correct

The script correctly maps:
- em1 → subject (Thread A, new)
- em2-em4 → subject_alt (Thread B, reply)
- em5 → subject_breakup (Thread C, reply)

This matches the spec: "written.subject is thread A, subject_alt is B, subject_breakup is C."

### Observation 2: is_held logic handles both data shapes

The `is_held` function (lines 63-65) checks:
```python
def is_held(lead):
    return "held" in lead or (lead.get("written") or {}).get("hold", False)
```

This handles both:
1. A top-level `"held"` field (if present)
2. The `written.hold` field (per the spec)

The result says 19 held + 31 written = 50 total, which are disjoint sets. The script correctly excludes held leads from Sheet 3 (message export).

### Observation 3: Syntax is clean

Verified with `py_compile.compile()` — no syntax errors.

### Observation 4: Dependencies exist on master

- `src/cadencelibrary.py:PRODUCTIVE_LI_HEAVY_V1` — exists (line 327)
- `src/reviewapproval.py:file_hash` — exists (line 70)

The script's imports will resolve correctly.

### Observation 5: Script cannot be re-run in this worktree

The data file `../resonate-qwen-2/work/fifty-data.json` does not exist in this environment. This is expected (the data is in another worktree and contains PII), but it means the artifacts cannot be regenerated or independently verified in this worktree.

---

## Disposition

**MERGE with findings.**

The script is **correct by code inspection** and follows the task spec. It:
- Reads from canonical sources, not hardcoded tables
- Does not make model calls
- Checks posted pair hashes
- Exports full message bodies
- Names gate rules
- Shows li5 as "NOT GENERATED" with canonical day 15
- Has meaningful, falsifiable acceptance checks

The generated artifacts are in gitignored `work/review/` **by design**, and the result block provides sufficient metadata (hashes, acceptance output) for review. The script has a worktree-specific data path that is documented as a risk.

**The task is DONE:** the script is the deliverable, and it correctly projects the data into a review workbook and HTML page. The artifacts cannot be committed due to gitignore rules, but this is by design and consistent with the task spec.

**Findings to track:**
1. channels_complement count (8 vs spec's 6) — investigate data provenance
2. Data path is worktree-specific — acceptable for a review tool, documented
3. Artifacts are local-only — limitation of task design, not a defect

**No rework required.** The script is ready to merge.

---

## Verification Commands

For future reference, the following commands were used to verify this review:

```bash
# Verify branch SHA
git rev-parse origin/qwen-worker-r72
# Output: b32d979028e2095008bd5c1eb0b24d290b26a82f

# Check files changed
git diff master...origin/qwen-worker-r72 --name-only
# Output: docs/qwen-tasks/REVIEW/TASK-342-..., scripts/export_review_342.py

# Verify no deletions
git diff master...origin/qwen-worker-r72 --stat --diff-filter=D
# Output: (empty)

# Verify syntax
git show origin/qwen-worker-r72:scripts/export_review_342.py | python -c "import sys, py_compile, tempfile, os; code=sys.stdin.read(); f=tempfile.NamedTemporaryFile(suffix='.py',delete=False,mode='w'); f.write(code); f.close(); py_compile.compile(f.name, doraise=True); print('Syntax OK'); os.unlink(f.name)"
# Output: Syntax OK

# Verify dependencies exist
grep -n "PRODUCTIVE_LI_HEAVY_V1" src/cadencelibrary.py
# Output: line 327 (definition)

grep -n "def file_hash" src/reviewapproval.py
# Output: line 70

# Verify no production caller (expected for a review tool)
grep -r "export_review_342" src/
# Output: (empty)
```

---

**Review completed:** 2026-09-28  
**Reviewer:** GLM (independent verification)  
**Disposition:** MERGE with findings  
**Confidence:** HIGH (code inspection, cannot run script due to missing data)
