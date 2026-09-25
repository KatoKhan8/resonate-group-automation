# COLLISION WALK REPORT — 2026-09-25

TASK-285. The collision walk batch 3 is sitting behind.

## STATUS: BLOCKED ON DATA, WIRING PROVEN

The live walk **cannot be run from this worktree**. The domain set
(`work/_s/supply.json`) and the staging files (`work/stage/s3-icp.jsonl`,
`work/stage/s5-verify.jsonl`, `work/mx-cache.json`) are gitignored and exist
only in Claude's worktree. This worktree's `work/` directory is empty.

What IS proven below:

1. The wiring from the walk output to `batch_eligibility` exists and works.
2. REFUSED domains are excluded from the cleared set.
3. A deleted walk file changes eligibility back to "not walked".
4. Every walk entry carries its walk date for staleness detection.
5. The walk script resumes correctly.

## 1. THE WIRING: walk output → batch_eligibility

The task's grep check (`grep -rn s6-collision-walk src/`) looks in `src/` and
finds nothing. **The consumer is in `scripts/`, not `src/`.**

```
$ grep -rn s6-collision-walk src/
(empty)

$ grep -rn s6-collision-walk scripts/
scripts/batch_eligibility.py:100:    PREFERS THE FRESH WALK. `s6-collision-walk.json` ...
scripts/batch_eligibility.py:118:    walk = os.path.join(STAGE, "s6-collision-walk.json")
scripts/s6_collision_walk.py:25:Progress is checkpointed to `work/stage/s6-collision-walk.json`
scripts/s6_collision_walk.py:56:                        "stage", "s6-collision-walk.json")
```

The chain is:

```
s6_collision_walk.py  WRITES  work/stage/s6-collision-walk.json
        ↓
batch_eligibility.py:collision_cleared()  READS  s6-collision-walk.json
        ↓                                   (falls back to batch1-candidates.json)
batch_eligibility.py:eligible()  CALLS  collision_cleared()
        ↓
if cleared is None:    → "collision not walked" (every domain refused)
if domain not in cleared: → "collision: account not cleared"
if domain in cleared:  → passes the collision gate
```

### Wiring proof (reproduced live)

```
No walk file:     collision_cleared() = None
                  → every domain refused as "collision not walked"

Walk file with:
  clearco.test:   policy=allow  → cleared
  refusedco.test: verdict=REFUSED → NOT cleared

With walk file:   collision_cleared() = {'clearco.test'}
                  → clearco passes, refusedco refused

Delete walk file: collision_cleared() = None
                  → back to "collision not walked"
```

**Deleting the read changes eligibility.** The walk is wired.

## 2. THE FOUR VERDICTS

The walk script and the report script both recognise four verdicts:

| Bucket     | Meaning                                    | Is supply? |
|------------|--------------------------------------------|------------|
| CLEAR      | Walked, no touch from us or the client     | Yes        |
| COLLIDES   | Walked, a touch found (STOP or HOLD)       | No         |
| REFUSED    | Provider's answer was not trustworthy       | No         |
| NOT_WALKED | Not asked yet                              | No         |

REFUSED and NOT_WALKED are different answers and neither is CLEAR. The test
suite (`tests/test_a_refused_domain_is_never_clear.py`) pins this:

- `test_refused_does_not_pass`: a REFUSED entry in the walk file is excluded
  from `collision_cleared()`.
- `test_hold_does_not_pass`: a HOLD entry is excluded.
- `test_stop_does_not_pass`: a STOP entry is excluded.
- `test_allow_passes`: only ALLOW entries pass through.
- `test_no_walk_file_returns_none`: no walk file → `None` → every domain
  refused as "collision not walked".

## 3. STALENESS

Every walk entry carries an `at` timestamp. The test suite pins that:

- `test_walk_entries_carry_their_date`: every entry has an `at` field.
- `test_stale_clearance_is_detectable`: entries from a prior cycle can be
  identified by comparing `at` against a cycle start date.

The staleness threshold is an operator decision, not hardcoded. The report
script (`scripts/collision_walk_report.py --staleness-days N`) flags clearances
older than N days.

## 4. RESUME PROOF

The walk script's main loop:

```python
todo = [d for d in targets() if d not in state["accounts"]]
```

Already-answered domains are excluded from the todo list. Re-running resumes
from where it left off and re-asks nothing. Checkpointing happens every
`--checkpoint` accounts (default 25).

## 5. WHY THE LIVE WALK CANNOT RUN HERE

| Requirement                  | Status in this worktree           |
|------------------------------|-----------------------------------|
| `work/_s/supply.json`        | MISSING (gitignored, Claude's)    |
| `work/stage/s3-icp.jsonl`    | MISSING (gitignored)              |
| `work/stage/s5-verify.jsonl` | MISSING (gitignored)              |
| `work/mx-cache.json`         | MISSING (gitignored)              |
| `work/stage/batch1-candidates.json` | MISSING (gitignored)       |
| `config/.env` credentials    | PRESENT (BISON_KEY, HEYREACH_KEY) |
| `src/collision.py`           | PRESENT and tested                |
| `scripts/s6_collision_walk.py` | PRESENT and functional          |

The script reads domains from `work/_s/supply.json` via its `targets()`
function. That file does not exist in this worktree. The QWEN.md standing
brief records that `work/` is gitignored and "does NOT travel with a branch".

## 6. DEFECT REPORTED: grep check looks in the wrong directory

The task says:

> `grep -rn s6-collision-walk src/` in the result block; if the only hit is
> the writer, the gate is still on batch 1's cache.

The consumer is `scripts/batch_eligibility.py:collision_cleared()`, not
anything in `src/`. The grep in `src/` returns empty not because the wiring is
absent but because the wiring lives in `scripts/`. The correct check is:

```
$ grep -rn s6-collision-walk scripts/
scripts/batch_eligibility.py:118:    walk = os.path.join(STAGE, "s6-collision-walk.json")
scripts/s6_collision_walk.py:25:     Progress is checkpointed to ...
scripts/s6_collision_walk.py:56:     ... "stage", "s6-collision-walk.json")
```

Two files: the writer and the reader. The gate is wired.

## 7. WHAT CLAUDE NEEDS TO DO

The live walk requires running from Claude's worktree where `work/` has data:

```bash
# In Claude's worktree:
py -3 scripts/s6_collision_walk.py --limit 200
py -3 scripts/collision_walk_report.py
```

The report script (`scripts/collision_walk_report.py`) is on this branch and
needs to be merged. It reads the walk output and produces the four-bucket
report with per-domain verdicts, staleness, and COLLIDES detail.

## FILES CHANGED

| File | Purpose |
|------|---------|
| `tests/test_a_refused_domain_is_never_clear.py` | 11 tests: REFUSED never CLEAR, staleness detectable, collision_cleared correct |
| `scripts/collision_walk_report.py` | Four-bucket report reader with staleness flagging |
| `docs/COLLISION-WALK-2026-09-25.md` | This report |

## TESTS

```
$ python -m unittest tests.test_a_refused_domain_is_never_clear -v
test_allow_passes ... ok
test_hold_does_not_pass ... ok
test_no_walk_file_returns_none ... ok
test_refused_does_not_pass ... ok
test_stop_does_not_pass ... ok
test_missing_verdict_is_not_a_defect ... ok
test_none_verdict_with_people_is_not_clear_via_allow ... ok
test_refused_is_never_allow ... ok
test_unknown_verdict_is_hold ... ok
test_stale_clearance_is_detectable ... ok
test_walk_entries_carry_their_date ... ok

Ran 11 tests in 0.019s - OK
```
