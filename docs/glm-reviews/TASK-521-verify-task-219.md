# TASK-521 — Independent GLM Verification of TASK-413

## Review metadata

| Field | Value |
|---|---|
| Target task | TASK-413 (HeyReach Seat Cap Check) |
| Target branch | `origin/qwen-worker-11-task314` |
| Branch HEAD SHA | `ddc0bc816fed25b327cbe070d0597ba03ae2b67e` |
| SHA verified by | `git rev-parse origin/qwen-worker-11-task314` → `ddc0bc816fed25b327cbe070d0597ba03ae2b67e` ✓ |
| Review worktree | `.qwen/worktrees/glm-task521` (detached HEAD at target SHA) |
| Review date | 2026-10-03 |
| Reviewer | GLM (independent, read-only) |

**The branch HEAD SHA has NOT moved.** `git rev-parse origin/qwen-worker-11-task314` returns `ddc0bc816fed25b327cbe070d0597ba03ae2b67e`, matching the task file exactly.

---

## Finding 1: Artifacts exist on this ref

**Disposition: CONFIRMED**

TASK-413-specific artifacts on `ddc0bc816`:

| File | Status | Verified by |
|---|---|---|
| `scripts/task413_seat_cap_check.py` | Present, 190 lines | `git log --diff-filter=A --all -- scripts/task413_seat_cap_check.py` |
| `scripts/task413_seat_cap_probe.py` | Present, 76 lines | Same |
| `docs/state/TASK-413-SEAT-CAP-CHECK.json` | Present, 708 lines | Same |
| `docs/qwen-tasks/REVIEW/TASK-413-heyreach-seat-cap-check.md` | Present, result block filled | Read in full |

The task file was moved from `TODO/` to `REVIEW/` on this branch. The TODO copy is deleted (confirmed by `--diff-filter=D`).

---

## Finding 2: The core connection-cap claim is correct

**Disposition: CONFIRMED**

The task asks: "Is any HeyReach seat over its own daily/weekly connection cap?" with acceptance threshold of 90%.

The JSON output (`docs/state/TASK-413-SEAT-CAP-CHECK.json`) reports 41 seats. I re-derived the percentages from `conn_actual / conn_cap * 100` for every seat where both values are non-null. **All percentages are internally consistent.** The highest connection usage is seat 212356 at 27.5% (11/40). No seat is at or over 90% of its connection cap.

The result block's table matches the JSON data for connection and message columns (spot-checked 5 seats).

**However** (see Finding 3): the result block's summary claim overstates this.

---

## Finding 3: Result block claims "NO SEAT IS AT OR OVER 90% OF ANY CAP" — this is FALSE for profile views

**Disposition: DEFECT — result block overclaim**

The script collects profile view data (`pv_cap`, `pv_actual`, `pv_pct`) for every healthy seat and writes it to the JSON. The JSON shows:

| seat_id | pv_actual | pv_cap | pv_pct |
|---|---|---|---|
| 116968 | 37 | 40 | 92.5% |
| 116973 | 36 | 40 | 90.0% |
| 116988 | 40 | 40 | **100.0%** |
| 116989 | 39 | 40 | 97.5% |
| 119588 | 38 | 40 | 95.0% |
| 125748 | 38 | 40 | 95.0% |
| 129082 | 37 | 40 | 92.5% |
| 201978 | 38 | 40 | 95.0% |
| 208253 | 37 | 40 | 92.5% |

**9 of 33 healthy seats are at or over 90% of their profile view cap. One seat (116988) is at 100%.**

The script's flagging logic (lines 150-178 of `scripts/task413_seat_cap_check.py`) only checks `conn_pct` and `msg_pct` against the threshold. Profile views are collected but never flagged. The JSON has `seats_flagged_connection` and `seats_flagged_message` fields but no `seats_flagged_pv`.

The result block then states: **"NO SEAT IS AT OR OVER 90% OF ANY CAP."** The emphasis on "ANY" makes this a claim about all metrics the script measured. It is false.

**Severity:** The task specification asks about "connection cap" specifically, so the core deliverable (connection cap check) is correct. But the result block's summary claim is broader than what was checked, and the profile view data the script itself collected contradicts it. A reader relying on the result block would conclude all caps are safe when profile views are not.

**Required fix:** Either:
1. Narrow the result block to "no seat is at or over 90% of its connection-request or message cap" and add a separate note about profile views, or
2. Add profile view flagging to the script's findings section and JSON summary.

---

## Finding 4: Existence is not function — production callers

**Disposition: NOT APPLICABLE (expected for this task kind)**

`grep -rn "task413_seat_cap" src/` returns no matches. The script has no production caller. This is expected: the task is a one-shot read-only provider audit, not a production module. The script's value is as a reusable manual check tool, which the result block correctly identifies ("The script `scripts/task413_seat_cap_check.py` is reusable for future checks").

This is not a DISCONNECTED defect because the task never claimed to build a production pipeline element.

---

## Finding 5: Test falsifiability

**Disposition: NOT APPLICABLE**

The result block states "TESTS: N/A — read-only provider audit, no code change to src/." This is honest. The task is a measurement, not a code change. There is nothing to falsify in the implementation sense.

The JSON data itself is not independently falsifiable from this worktree (I cannot call the HeyReach API). I verified internal consistency: all percentages match `actual/cap*100`, `seats_total` matches `len(seats)`, state counts match (33 HEALTHY + 1 AUTH_INVALID + 7 INACTIVE = 41). The data is self-consistent but I cannot prove it was produced by a live API call rather than constructed by hand.

---

## Finding 6: Merge safety — would merging delete anything?

**Disposition: SAFE for TASK-413 files; scope drift concern for the branch**

`git diff master...ddc0bc816 --diff-filter=D --name-only` shows three deleted files:

1. `docs/qwen-tasks/TODO/TASK-314-where-the-heyreach-steps-are-lost.md` — moved to `DONE/`
2. `docs/qwen-tasks/TODO/TASK-398-suppression-list-audit.md` — moved to `REVIEW/`
3. `docs/qwen-tasks/TODO/TASK-413-heyreach-seat-cap-check.md` — moved to `REVIEW/`

These are all task-file stage moves (TODO → REVIEW/DONE), which is normal workflow. No production source, test, or state file is deleted.

**However**, the branch carries 23 changed files across 6 tasks (TASK-296, TASK-314, TASK-364, TASK-398, TASK-410, TASK-413). The TASK-413-specific files are only 4 (script, probe, JSON, task file move). Merging the full branch would bring in all other tasks' work as well. Cherry-picking TASK-413 alone would require extracting:
- `scripts/task413_seat_cap_check.py` (new)
- `scripts/task413_seat_cap_probe.py` (new)
- `docs/state/TASK-413-SEAT-CAP-CHECK.json` (new)
- `docs/qwen-tasks/REVIEW/TASK-413-heyreach-seat-cap-check.md` (new)
- Deletion of `docs/qwen-tasks/TODO/TASK-413-heyreach-seat-cap-check.md`

These are cleanly separable with no dependencies on the other tasks' changes.

---

## Finding 7: Scope drift

**Disposition: SIGNIFICANT**

The branch `qwen-worker-11-task314` carries work for at least 6 tasks:

| Task | Files | Nature |
|---|---|---|
| TASK-296 | `scripts/qa/check_campaign_bison.py`, `scripts/qa/__init__.py`, `docs/QA-CAMPAIGN-BISON-2026-09-25.md`, task file move | EmailBison campaign QA |
| TASK-314 | `tests/test_no_cadence_step_is_silently_dropped.py`, `tests/test_step_counts_agree_while_the_keys_do_not.py`, task file move | Cadence step regression tests |
| TASK-364 | `src/sequenceplan.py` (new functions), `src/bisonfactory.py` (modified), `src/heyreachfactory.py` (modified), `tests/test_every_representation_derives_from_one_plan.py`, task file move | Canonical sequence plan |
| TASK-398 | `docs/qwen-tasks/REVIEW/TASK-398-suppression-list-audit.md`, task file move | Suppression list audit |
| TASK-410 | `docs/qwen-tasks/TODO/TASK-410-glm-verify-task-400-critical-path.md` | GLM verification task file |
| TASK-413 | `scripts/task413_seat_cap_check.py`, `scripts/task413_seat_cap_probe.py`, `docs/state/TASK-413-SEAT-CAP-CHECK.json`, task file move | **This review's target** |

Additionally, `docs/state/SENDER-CAPACITY.json` is modified (refreshed by the seat cap check) and `scripts/stage_work_to_host.sh` is added (unrelated infrastructure).

The TASK-413 portion is cleanly separable. The branch should not be merged as-is for TASK-413 alone.

---

## Summary of findings

| # | Finding | Disposition | Severity |
|---|---|---|---|
| 1 | Artifacts exist on the reviewed ref | CONFIRMED | — |
| 2 | Core connection-cap claim is correct | CONFIRMED | — |
| 3 | Result block claims "NO SEAT ≥ 90% OF ANY CAP" but 9 seats are ≥ 90% of profile view cap | DEFECT | Medium — overclaim in summary, core deliverable (connection cap) is correct |
| 4 | No production caller for the script | NOT APPLICABLE | — (expected for audit script) |
| 5 | Test falsifiability | NOT APPLICABLE | — (read-only audit, no code change) |
| 6 | Merge would not delete production content | SAFE | — |
| 7 | Branch carries significant scope drift from 5 other tasks | SCOPE DRIFT | Low for TASK-413 portion (cleanly separable) |

---

## Recommendation

**REWORK** — narrow, specific.

The TASK-413 core work is sound: the script is correct for connection and message caps, the JSON is internally consistent, and the artifact is reusable. The defect is the result block's overclaim: "NO SEAT IS AT OR OVER 90% OF ANY CAP" is false for profile views, which the script itself measured.

**Required before merge of the TASK-413 portion:**
1. Correct the result block to say "no seat is at or over 90% of its connection-request or message cap."
2. Add a finding noting that 9 seats are at or over 90% of their profile view cap (one at 100%), or explicitly state that profile views were collected but not assessed against the threshold.
3. Optionally: add `seats_flagged_profile_view` to the JSON summary and a profile-view flagging section to the script.

**Merge scope:** The TASK-413 files are cleanly separable from the rest of the branch. Cherry-pick only the 4 TASK-413 files plus the TODO deletion; do not merge the full branch for this task alone.

**Provider state:** No provider write was made. This review is read-only. 42 HeyReach API reads were made by the original script run (1 GetAll + 41 GetOverallStats), all free-tier reads. No campaign, seat, or cap was modified.
