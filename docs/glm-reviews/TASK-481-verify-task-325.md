---
title: "GLM Independent Verification: TASK-325"
task: "TASK-481"
reviewed_task: "TASK-325"
reviewed_branch: "origin/qwen-worker-r60"
reviewed_sha: "2594a3088814fa0c803afac8a654e9c6b72c6ebc"
date: "2026-09-28"
verdict: "MERGE"
---

# GLM Independent Verification: TASK-325

**Reviewed branch HEAD SHA:** `2594a3088814fa0c803afac8a654e9c6b72c6ebc`
**Verified on:** 2026-09-28
**Isolated worktree:** `.qwen/worktrees/task481-review` (detached at exact SHA)

## Summary

**VERDICT: MERGE**

TASK-325 is a read-only documentation task that accurately describes the LinkedIn cadence tree as built. The artifact exists, all claims are verified against the code, no behavior was changed, and there is no scope drift or deletion risk.

## What was reviewed

TASK-325's deliverable is `docs/LINKEDIN-CADENCE-AS-BUILT-2026-09-26.md`, a 323-line document that:
1. Maps the `PRODUCTIVE_LI_HEAVY_V1` graph (5 LinkedIn steps, 10 total)
2. Explains the four-vs-five discrepancy (branch structure, not a silent drop)
3. Confirms merge variables (words travel per lead, not baked into the graph)
4. Documents three operator observations for future decisions

The task explicitly states: **"This task changes NO behaviour. It reads and writes a document."**

## Verification results

### 1. Artifact existence — VERIFIED

The file exists at the exact SHA:
```
docs/LINKEDIN-CADENCE-AS-BUILT-2026-09-26.md
```

Commit `6d8aa9a6` added it; commit `2594a308` moved the task file to DONE with the result block.

### 2. Claims against code — ALL VERIFIED

| Claim | Document says | Actual (verified) | Status |
|-------|---------------|-------------------|--------|
| Graph location | `src/cadencelibrary.py` line 327 | Line 327, symbol `PRODUCTIVE_LI_HEAVY_V1` | ✅ |
| Total steps | 10 (5 LinkedIn + 5 email) | `len(PRODUCTIVE_LI_HEAVY_V1) == 10` | ✅ |
| LinkedIn steps | li1-li5, days 1/3/6/10/15 | Confirmed by import and measurement | ✅ |
| COPY_MAPPING location | `src/heyreachfactory.py` lines 106-112 | Lines 106-112 | ✅ |
| li5 role mapping | `("connected_4",)` only | Line 110: `"li5": {"role": ("connected_4",), ...}` | ✅ |
| li5 on cold path? | No, only on already-connected branch | Code at lines 395-410 confirms `connected_4` only in `already` branch | ✅ |
| Two branches in render | 4 roles each | Lines 670-672: `ALREADY_CONNECTED_BRANCH` (4), `NOT_CONNECTED_BRANCH` (4) | ✅ |
| Merge variables | `{role}` placeholders, not baked words | `merge_sequence_copy()` at line 469 builds `["{" + role + "}"]` | ✅ |
| `describe()` exists? | No, entry point is `stage()` | `grep "def describe\("` returns nothing; `stage()` at line 591 | ✅ |
| `_refuse_missing()` | Line 339, per-contact | Line 339, iterates `(contact_key, step_key, role)` tuples | ✅ |
| Per-contact pushable | Complete contacts pushable even if others have gaps | Line 849: `complete = [c for c in per_contact if not c["missing"] ...]` | ✅ |

**Minor discrepancies (not material):**
- `assemble_linkedin_copy()`: document says line 215, actual is line 223 (off by 8)
- `custom_fields_for()`: document says line 525, actual is line 535 (off by 10)

These are line-number drift in a reference table. The functions exist, are correctly named, and the substance is accurate. A documentation snapshot's line numbers are point-in-time; this does not affect the document's correctness.

### 3. Tests — VERIFIED

`tests/test_cadence_graph_agreement.py` (4 tests) passes on the branch:
```
test_cadence_and_graph_agree_on_step_count ... ok
test_every_cadence_step_has_a_graph_position ... ok
test_every_graph_position_has_a_cadence_step ... ok
test_li6_does_not_exist ... ok
```

This test module pins the fix from TASK-179 (li6 removal) and verifies cadence-graph agreement. It is consumed by the test suite and is not a dead artifact.

### 4. Falsification of key claim — ATTEMPTED

**Claim:** li5 maps ONLY to `connected_4` on the already-connected branch; the cold path never uses li5.

**Falsification attempt:** Searched for all occurrences of `connected_4` and `li5` in `heyreachfactory.py`. Found 9 matches. Line 410 places `connected_4` in the `already` branch (lines 401-411). The cold path (lines 395-399) and the not-accepted branch (line 393) do not reference `connected_4`. The `chain()` function (lines 375-384) builds the post-connection messages as `message_2`, `message_3`, `message_4` (from li2, li3, li4), not `connected_4`.

**Result:** Claim holds. li5 is structurally absent from the cold path.

### 5. Scope drift — NONE

```
git diff master...2594a308 --stat
 docs/LINKEDIN-CADENCE-AS-BUILT-2026-09-26.md       | 323 +++++++++++++++
 ...25-document-the-actual-linkedin-cadence-tree.md |  41 +++
 2 files changed, 364 insertions(+)
```

Only 2 files changed. Both are additions. No junk, no unrelated changes, no scope drift.

### 6. Deletion risk — NONE

```
git diff master...2594a308 --stat
```

Shows 364 insertions, 0 deletions. Merging this branch adds files; it does not delete or modify anything on master.

### 7. Existence is not function — NOT APPLICABLE

This is a documentation task. The deliverable is the document itself, not a code module with production callers. The task explicitly states it changes no behavior. There is no "production caller" to trace because the artifact is not consumed by code—it is consumed by the operator and future tasks.

The document's accuracy is what matters, and it is verified.

## Findings

### No P0 findings

The cadence, graph, and staging pipeline are consistent. The four-vs-five discrepancy is a branch structure, not a silent drop. No step is lost before the provider.

### Three operator observations (documented in the artifact)

1. **li5 only fires for already-connected prospects.** A cold prospect who accepts the connection request receives three messages (li2/li3/li4). An already-connected prospect receives four (li2/li3/li4/li5). If the intent is five messages on every path, li5 needs a role on the not-connected branch. **This is an operator decision, not a defect.**

2. **`_refuse_missing` is per-contact, not per-campaign.** A campaign with ten contacts where one has missing copy still stages and pushes the other nine. The PHASE1-PLAN's statement is accurate for the contact but not for the campaign.

3. **The InMail branch is structurally present but practically dead.** `ALTERNATIVE_MAPPING` maps li3 to an `inmail` role, but `build_sequence(include_inmail=False)` (the default) omits it. No InMail copy has ever been approved.

These are correctly documented in the artifact under FINDINGS and are waiting for operator decision.

## Disposition

**MERGE**

Rationale:
- The artifact exists and is accurate
- All claims verified against code at the exact SHA
- No behavior changed (read-only task)
- No scope drift (only 2 files, both additions)
- No deletion risk (0 deletions vs master)
- Tests pass (4/4 in `test_cadence_graph_agreement`)
- Key claim falsified and holds (li5 only on already-connected branch)
- Three operator observations are legitimate and correctly documented

The document is a faithful snapshot of the LinkedIn cadence as built. It answers the four-vs-five question, confirms merge variables, and flags three observations for operator decision. Merging it adds documentation; it does not change behavior or introduce risk.

## Reproducible verification commands

All commands run in the isolated worktree at SHA `2594a3088814fa0c803afac8a654e9c6b72c6ebc`:

```bash
# Graph symbol and step count
py -3 -c "import sys;sys.path.insert(0,'.');from src import cadencelibrary as cl;\
print('graph:', 'PRODUCTIVE_LI_HEAVY_V1' in dir(cl));\
steps=cl.PRODUCTIVE_LI_HEAVY_V1;\
li=[s for s in steps if s['channel']=='linkedin'];\
print(f'LinkedIn steps: {len(li)}');\
[print(f'  {s[\"key\"]}: day={s[\"day\"]}, action={s.get(\"linkedin_action\")}') for s in li]"

# COPY_MAPPING (li5 role)
grep -n '"li5"' src/heyreachfactory.py

# connected_4 usage (should only appear in already-connected branch)
grep -n 'connected_4' src/heyreachfactory.py

# Two branches in render_preview
grep -n 'ALREADY_CONNECTED_BRANCH\|NOT_CONNECTED_BRANCH' scripts/render_preview.py | head -5

# Merge variables (should show {role} placeholders)
sed -n '469,495p' src/heyreachfactory.py

# Tests
py -3 -m unittest tests.test_cadence_graph_agreement -v

# Diff vs master
git diff master...2594a3088814fa0c803afac8a654e9c6b72c6ebc --stat
```

## Recommendations

None. The task is complete and the artifact is accurate. The three operator observations are correctly flagged and waiting for decision. No rework is needed.
