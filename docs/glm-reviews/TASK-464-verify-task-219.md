# GLM Independent Verdict: TASK-192

**TASK-464** — Independent verification of TASK-192

## Review coordinates

| Field | Value |
|---|---|
| Target task | TASK-192 (buy Grok evidence for 25 records) |
| Branch | `origin/qwen-worker-5-r59` |
| Branch HEAD SHA | `2b3584534d6c4b18a666b5ac2b2aef5b8271cded` |
| SHA verified with `git rev-parse` | **YES** — SHA matches task file specification |
| Review method | Isolated worktree at exact SHA, detached HEAD |
| Master reference | `origin/master` at time of review |
| Reviewer | GLM (Qwen-7 worktree, independent of authoring branch) |

**This verdict reviewed `2b3584534d6c4b18a666b5ac2b2aef5b8271cded` specifically. The branch has not moved since the task file named it.**

---

## Finding 1: Artifact exists and matches claims

**Disposition: VERIFIED**

The branch introduces four file changes beyond the task file:

| File | Status | Verified |
|---|---|---|
| `docs/BOUGHT-EVIDENCE-2026-09-16.md` | New, 109 lines | Content matches result block claims |
| `scripts/task183_buy_evidence.py` | 1-line change (snapshot path) | Change is correct and minimal |
| `scripts/task183_results.json` | Expanded (+844 lines) | 25 result records, consistent structure |
| `.qwen-257.err` | New (junk) | **Scope pollution — see Finding 6** |
| `.qwen-257.out` | New (junk) | **Scope pollution — see Finding 6** |

The report (`BOUGHT-EVIDENCE-2026-09-16.md`) exists, is substantive (700+ chars of analysis), and its numbers match the raw data in `task183_results.json`.

**Evidence:**
```
git show 2b358453:docs/BOUGHT-EVIDENCE-2026-09-16.md   # 109 lines, present
git show 2b358453:scripts/task183_results.json          # 25 results, valid JSON
```

---

## Finding 2: Result data is internally consistent

**Disposition: VERIFIED**

The `task183_results.json` data was independently parsed and cross-checked against the report claims:

| Claim in report | Actual from JSON | Match |
|---|---|---|
| 25 records processed | 25 results in JSON | ✓ |
| 0 qualified | Counter: 0 qualified | ✓ |
| 10 rejected | Counter: 10 rejected | ✓ |
| 5 still review | Counter: 5 review | ✓ |
| 10 unknown | Counter: 10 unknown | ✓ |
| 0 confidence off low | 0 non-low confidence | ✓ |
| $6.71 total spend | 6.7068 in JSON | ✓ (rounding) |
| $0.27 avg per record | 0.2683 computed | ✓ (rounding) |
| $0.67 per rejection | 0.6707 computed | ✓ (rounding) |
| All started from `review` | `old_statuses = {'review'}` | ✓ |
| 0 errors/parse failures | 0 errors in JSON | ✓ |
| ~5.5 facts per record avg | 139 total / 25 = 5.56 | ✓ |

**The movement numbers are not fabricated. They derive from the actual JSON data.**

**Evidence:**
```python
import json
d = json.load(open('scripts/task183_results.json'))
# Counter(new_status) = {'unknown': 10, 'rejected': 10, 'review': 5}
# total_cost_usd = 6.7068
# all old_status = 'review'
```

---

## Finding 3: The script uses real production entry points

**Disposition: VERIFIED with caveat**

The script calls:
- `qualify.company(rec, config, store_result=True)` — **real entry point**, defined at `src/qualify.py:95`. This is the production qualification function.
- `xai_adapter.respond(...)` — **real adapter**, defined at `src/providers/xai.py:125`. TASK-182 compliant.
- `ev.make(...)` — **real evidence constructor**, defined at `src/evidence.py:442`.
- `store.now()` — **real function**, defined at `src/store.py:223`.
- `xai_adapter.ticks_to_usd(...)` — **real function**, defined at `src/providers/xai.py:331`.
- `icp.QUALIFIED`, `icp.REJECTED`, `icp.REVIEW`, `icp.UNKNOWN` — **real constants**, defined at `src/icp.py:35-38`.

**Caveat:** The script itself (`scripts/task183_buy_evidence.py`) has **zero production callers**. `grep -rn "task183_buy_evidence" src/` returns nothing. This is **acceptable for this task type** — TASK-192 explicitly asked for a one-shot measurement script, not a production integration. The task file says "Buy evidence for 25 records and see if the wall move." It is a measurement, not a pipeline component. The "existence is not function" rule applies to production modules, not to measurement scripts whose entire purpose is to be run once and report.

**Evidence:**
```
grep -rn "task183_buy_evidence" src/ scripts/
# Only hits: the script's own docstring and argparse prog name
grep -n "def company" src/qualify.py
# 95:def company(rec, config=None, store_result=True):
```

---

## Finding 4: No PII leakage

**Disposition: VERIFIED**

All record identifiers, domains, and company names in `task183_results.json` are hashed:
- `record_id_hash`: 12-char hex (SHA-256 truncated)
- `domain_hash`: 12-char hex
- `company_hash`: 16-char hex

The report (`BOUGHT-EVIDENCE-2026-09-16.md`) contains no raw domains, company names, or prospect-identifying URLs. Third-party source domains are preserved as instructed.

**Evidence:**
```python
# Sample from results JSON:
# record_id_hash: "c74e7e1541ab"
# domain_hash: "e691c6dd0272"
# company_hash: "e691c6dd02726a76"
```

---

## Finding 5: Merging would not delete anything from master

**Disposition: VERIFIED**

`git diff master...2b358453 --stat` shows only additions and one rename:
- 2 new junk files (`.qwen-257.err`, `.qwen-257.out`)
- 1 new doc (`docs/BOUGHT-EVIDENCE-2026-09-16.md`)
- 1 task file rename (`TODO/TASK-192-*` → `DONE/TASK-192-*`)
- 1 script modification (1 line)
- 1 results JSON expansion

**No files from master are deleted.** The branch does not touch `src/` or `config/` at all (`git diff master...2b358453 --stat -- src/ config/` returns empty).

**Evidence:**
```
git diff master...2b3584534d6c4b18a666b5ac2b2aef5b8271cded --stat -- src/ config/
# (empty)
```

---

## Finding 6: Scope pollution — two junk files committed

**Disposition: DEFECT — minor, cherry-pickable**

The branch carries two files that are terminal output from an unrelated task (TASK-257):

- `.qwen-257.err` — contains a Qwen Code yolo-mode warning
- `.qwen-257.out` — contains a background agent completion message

These are scratch output files from a different worker session that were accidentally committed. They have no relevance to TASK-192.

**Impact:** These files would land in the repository root if the branch is merged as-is. They are harmless but constitute pollution.

**Remediation:** Cherry-pick only the four TASK-192 files, or ask the author to remove the two junk files. This is a 30-second fix and does not affect the measurement's validity.

**Evidence:**
```
git diff master...2b358453 -- .qwen-257.err .qwen-257.out
# Both files are new, containing terminal output from TASK-257
```

---

## Finding 7: Task file stage — DONE vs REVIEW

**Disposition: PROCESS OBSERVATION**

The task file was moved from `TODO/` to `DONE/`. Per QWEN.md queue rules: "Finished work goes to REVIEW, not DONE — Claude moves it to DONE after integrating." The worker instruction section says "Move the file to `DONE/`" which contradicts the queue rule. The branch followed the worker instruction.

**Impact:** None on the measurement. This is a process inconsistency in the standing instructions, not a defect in TASK-192's work.

---

## Finding 8: Snapshot dependency is not reproducible from the branch

**Disposition: NOTED, not a defect**

The script references `work/RETIRED-2026-09-17-queue.snapshot.jsonl` which is in `work/` (gitignored). The snapshot does not travel with the branch. Re-running the script requires the snapshot to be present in the worktree.

Per QWEN.md: "The snapshot (`work/queue.snapshot.jsonl`) is RETIRED as of 2026-09-16." The script was updated to point at the retired snapshot name, which is correct — it preserves the exact input state the measurement ran against.

**Impact:** The measurement cannot be independently re-run from the branch alone. The results JSON is the durable artifact. This is acceptable for a one-shot measurement.

---

## Finding 9: The "structural wall" claim is supported by the data

**Disposition: VERIFIED**

The report's central finding — that the criteria blocking qualification are operational-model questions web search cannot answer — is supported by the `new_missing` fields in the results:

- 15/15 non-rejected records list "no evidence of how client work is delivered"
- 13/15 list "no evidence for delivery complexity"
- 10/10 unknown records list "vertical could not be classified"

These are consistent across the data. The claim that "web search tells you what a company does, not how they deliver client work" is a reasonable interpretation supported by the fact that 139 facts were added and zero records qualified.

**Caveat:** This is an interpretation of the data, not a mechanically verifiable claim. A different ICP model with different criteria might qualify records with the same evidence. The finding is valid for the current ICP model.

---

## Summary of findings

| # | Finding | Disposition | Severity |
|---|---|---|---|
| 1 | Artifact exists and matches claims | VERIFIED | — |
| 2 | Result data is internally consistent | VERIFIED | — |
| 3 | Script uses real production entry points | VERIFIED (caveat: no production caller, acceptable for measurement) | — |
| 4 | No PII leakage | VERIFIED | — |
| 5 | Merging would not delete anything | VERIFIED | — |
| 6 | Two junk files committed | DEFECT | Minor — cherry-pickable |
| 7 | Task file in DONE not REVIEW | PROCESS OBSERVATION | None |
| 8 | Snapshot not reproducible from branch | NOTED | None |
| 9 | "Structural wall" claim supported by data | VERIFIED | — |

---

## Recommendation

**MERGE with cherry-pick** — exclude `.qwen-257.err` and `.qwen-257.out`.

The measurement is real, the data is consistent, the script uses real entry points, and the finding (buying web-search evidence produces rejections but zero qualifications) is valuable and well-supported. The two junk files are the only defect and are trivially excluded.

The task's central conclusion — that the estate is blocked by evidence *type* not evidence *quantity* — is a finding the data supports and that the project needs. It correctly stops a $60 spend that would buy nothing in the qualification direction.

**Specific cherry-pick set:**
- `docs/BOUGHT-EVIDENCE-2026-09-16.md` (new)
- `scripts/task183_buy_evidence.py` (1-line change)
- `scripts/task183_results.json` (expansion)
- `docs/qwen-tasks/TODO/TASK-192-*` → `DONE/TASK-192-*` (rename)

**Exclude:**
- `.qwen-257.err`
- `.qwen-257.out`
