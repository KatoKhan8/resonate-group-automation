# TASK-524 — GLM independent verification of TASK-417

**Reviewed branch**: `origin/qwen-worker-12-r9-sync`
**Branch HEAD SHA**: `3da4a246ee2536760d04dfc4d1d94b649160c2fa`
**Verified with**: `git rev-parse origin/qwen-worker-12-r9-sync` → `3da4a246e` (matches)
**Isolated worktree**: `.qwen/worktrees/task524-review` (detached at SHA)
**Review date**: 2026-10-03

---

## 1. Artifact existence

**VERIFIED.** The artifact is `docs/qwen-tasks/DONE/TASK-417-campaign-cadence-drift-check.md`.
It exists on the branch at the reviewed SHA. It was added in commit `c658897cc`
("TASK-417: campaign cadence drift check — cold-branch expansion found") and
moved to DONE in `d35406c28`.

TASK-417 is a **read-only audit**. It changed no source code, no tests, and no
configuration. Its only file changes are its own task file (TODO → DONE) and the
result block within it. This is consistent with the task's acceptance criteria:
"READ-ONLY. Acceptance: real per-campaign timing measured against the canonical
cadence, named drift if any."

## 2. Finding correctness — independently re-derived

### 2a. Campaign inventory

TASK-417 claims 34 IN_PROGRESS HeyReach campaigns in three groups. Independent
query of `docs/state/PROVIDER-CAMPAIGNS.json` on the branch:

| Hash | Claimed count | Measured count | Match |
|------|--------------|----------------|-------|
| `2f7bb33ee7f6ce5a` | 32 | 32 | ✓ |
| `a3d4ce61b9ca79a9` | 1 | 1 | ✓ |
| `32f8dde79bfa0f27` | 1 | 1 | ✓ |

Node counts (20, 20, 24) and MESSAGE node counts (6, 6, 7) also match.

### 2b. Canonical cadence delays

`li_message_delays_from_cadence()` returns `(3, 4, 5)`. Independent execution
on the worktree confirmed:

```
li_message_delays_from_cadence(): (3, 4, 5)
```

Derived from `PRODUCTIVE_LI_HEAVY_V1` in `src/cadencelibrary.py`:
- li2 day 3, li3 day 6, li4 day 10, li5 day 15
- d1 = 6-3 = 3, d2 = 10-6 = 4, d3 = 15-10 = 5 ✓

### 2c. Cold-branch drift

TASK-417 claims the cold branch delivers a 7-day gap where the canonical
cadence declares 3 days (+4d drift), and a 5-day gap where 4 days is declared
(+1d drift).

Independent code trace of `chain()` at `src/providers/heyreach.py:1261-1267`:

```python
def chain(copy_block):
    return _node("MESSAGE", 3, "HOUR", _copy("message_2", copy_block),
            nxt=_node("VIEW_PROFILE", d1, "DAY",
                 nxt=_node("MESSAGE", d2, "DAY", _copy("message_3", copy_block),
                      nxt=_node("MESSAGE", d3, "DAY",
                                _copy("message_4", copy_block),
                                nxt=end()))))
```

- message_2 → VIEW_PROFILE(d1=3d) → message_3(d2=4d): gap = 3+4 = **7d**
  (canonical li2→li3 = 3d, drift = **+4d**) ✓
- message_3 → message_4(d3=5d): gap = **5d**
  (canonical li3→li4 = 4d, drift = **+1d**) ✓

### 2d. Already-connected branch — no drift

TASK-417 claims the already-connected branch compensates via `max(d2-2, 1)`.

Independent code trace at `src/providers/heyreach.py:1298-1306`:

```python
already = _node("MESSAGE", 3, "HOUR", _copy("connected_1", copy),
           nxt=_node("MESSAGE", d1, "DAY", _copy("connected_2", copy),
                nxt=_node("VIEW_PROFILE", 2, "DAY",
                     nxt=_node("MESSAGE", max(d2 - 2, 1), "DAY",
                               _copy("connected_3", copy),
                          nxt=_node("MESSAGE", d3, "DAY",
                                    _copy("connected_4", copy),
                                    nxt=end())))))
```

- connected_1 → connected_2: d1 = **3d** (canonical 3d, drift = 0) ✓
- connected_2 → connected_3: 2d + max(4-2,1) = 2+2 = **4d** (canonical 4d, drift = 0) ✓
- connected_3 → connected_4: d3 = **5d** (canonical 5d, drift = 0) ✓

### 2e. V2 CONTROL

TASK-417 claims V2 CONTROL (campaign 605732, hash `32f8dde79bfa0f27`) is
intentionally different, not drift. The PROVIDER-CAMPAIGNS.json confirms this
campaign is named "RESONATE - PRODUCTIVE LINKEDIN COHORT V2 - CONTROL", has
24 nodes and 7 MESSAGE nodes (vs 20 nodes / 6 MESSAGE for B1 batch), and
started 2026-09-16 (six days before B1 batch). Different structure, different
start date, explicitly labeled CONTROL. **Classification as intentional
experiment is reasonable.**

### 2f. EmailBison

TASK-417 claims EmailBison cadence is unverifiable from available data. The
`PROVIDER-CAMPAIGNS.json` EmailBison section carries id, name, status, owner,
lead_count — no sequence or delay data. **Claim verified.**

## 3. Existence is function — production caller chain

`linkedin_sequence()` is consumed:

```
src/heyreachfactory.py:599:  sequence = heyreach.linkedin_sequence(
src/heyreachfactory.py:600:      copy, withdraw_after_days=withdraw_after_days,
src/heyreachfactory.py:601:      message_delays=_li_message_delays())
```

`build_sequence()` in `heyreachfactory.py` is the production graph builder.
The cold-branch drift is in pre-existing code on master (last modified by
TASK-400, commit `fb5aefaf7`). This branch did NOT introduce the defect; it
found it.

The same `chain()` structure is duplicated in `_build_sequence_no_inmail()` at
`heyreachfactory.py:401-411`, carrying the same drift into the no-InMail path.
TASK-417 did not note this second occurrence.

## 4. Test falsifiability

**No test covers cold-branch inter-message delays.** Searched for
`test.*cold.*branch`, `test.*cadence.*delay`, `test.*linkedin.*timing`,
`test.*message_2.*message_3`, `test.*linkedin.*gap` — zero matches for
cadence timing assertions.

The finding is a read-only audit, so the absence of a test is expected — the
task was to measure, not to guard. However, the underlying drift is unguarded:
no test would catch it if the drift were to change or worsen.

## 5. Merge deletion check

`git diff master...origin/qwen-worker-12-r9-sync --diff-filter=D --name-only`
shows only TODO task files being deleted (moved to DONE/REVIEW/BLOCKED):

- `TASK-335-recover-the-audit-and-the-two-provider-artifacts-from-branches.md`
- `TASK-405-glm-verify-task-394.md`
- `TASK-409-glm-verify-task-294.md`
- `TASK-415-sender-inventory-drift-check.md`
- `TASK-417-campaign-cadence-drift-check.md`
- `TASK-418-offer-config-consistency-check.md`

**No source code, tests, or configuration files are deleted.** These are all
task queue movements. Safe.

## 6. Scope drift

TASK-417's own commits (`c658897cc`, `d35406c28`) touch only the task file.
The branch carries work from many other tasks (TASK-245, TASK-355, TASK-434,
TASK-272, TASK-311, TASK-424, TASK-405, TASK-409, TASK-335, TASK-427,
TASK-426, TASK-364, TASK-415, TASK-397, TASK-418). TASK-417 itself is clean
and self-contained. Cherry-picking its two commits is straightforward.

## 7. One thing TASK-417 missed

The `_build_sequence_no_inmail()` function in `heyreachfactory.py` (lines
388-430) contains an identical `chain()` with the same additive delay
structure. The cold-branch expansion affects both graph builders (with-InMail
and without-InMail), not just `linkedin_sequence()`. TASK-417's finding is
correct for the code it examined but understates the blast radius by not
naming the second occurrence.

---

## Findings

| # | Finding | Severity | Evidence |
|---|---------|----------|----------|
| F1 | Cold-branch expansion is real and independently confirmed | Verified | `heyreach.py:1261-1267`, re-derived (3,4,5) → cold gaps (7,5) vs canonical (3,4) |
| F2 | Already-connected branch correctly compensates | Verified | `heyreach.py:1298-1306`, `max(d2-2,1)` produces gap=4d matching canonical |
| F3 | Campaign inventory (34 IN_PROGRESS, three hash groups) is exact | Verified | `PROVIDER-CAMPAIGNS.json` independent query |
| F4 | EmailBison cadence is unverifiable from available data | Verified | Provider JSON carries no sequence/delay fields |
| F5 | V2 CONTROL is intentionally different | Verified | Named CONTROL, different structure (24 nodes, 7 MESSAGE), earlier start |
| F6 | `_build_sequence_no_inmail()` has the same cold-branch drift | Not in TASK-417 | `heyreachfactory.py:401-411`, identical `chain()` structure |
| F7 | No test guards against cold-branch timing drift | Not in TASK-417 | Searched all test files, zero cadence-timing assertions |

## Disposition

**MERGE.** TASK-417 is a clean, correct, read-only audit. Its finding
(COLD-BRANCH EXPANSION) is mathematically verified against the actual code.
The campaign inventory is exact. The task touched only its own file. The
branch deletes no source code. The finding is actionable and the recommended
Claude action (decide whether the expansion is intentional or a defect) is the
right next step.

One gap: TASK-417 did not notice the same drift in `_build_sequence_no_inmail()`.
This does not invalidate the finding — it understates the scope. Claude should
address both graph builders when deciding the fix.
