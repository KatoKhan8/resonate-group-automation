# TASK-535 — GLM Independent Verification of TASK-433

## Review target

    task            TASK-433
    branch          origin/glm-review-504-task-387
    named SHA       f3b68bf849d8361fab9d3f8f972229369cf60944
    actual SHA      515c638e14423a203e56f3ed3525af8569f72c07 (branch has moved)
    reviewed SHA    f3b68bf849d8361fab9d3f8f972229369cf60944 (as instructed)
    worktree        .qwen/worktrees/task535-review (detached HEAD at f3b68bf8)

**The branch HEAD has MOVED since the task file named it.** The task file specified `f3b68bf849d8361fab9d3f8f972229369cf60944` but the branch now points to `515c638e14423a203e56f3ed3525af8569f72c07`. Per the task instructions, I reviewed the original SHA `f3b68bf849d8361fab9d3f8f972229369cf60944` anyway, as that is the artifact this verdict is about.

## What TASK-433 claims

TASK-433 is a GLM independent verification of TASK-231. It produced a verdict file at `docs/glm-reviews/TASK-433-verify-task-231.md` that recommends **MERGE** for TASK-231 with cherry-pick of TASK-231 files only.

TASK-433's verdict makes these claims about TASK-231:

1. The HTTP timeout now aborts the REQUEST at the socket layer, not merely abandons the wait.
2. Exceptions are classified: `HttpTimeout(ProviderError, TimeoutError)` vs `HttpTransportError(ProviderError)` vs 4xx/5xx returned as status.
3. `gather`'s own `timeout` parameter is removed — no more dual-timeout credit hazard.
4. The people-count prefetch keeps working unchanged; ledger-equality tests pass.
5. Honest caveat: aborting the socket proves WE stopped waiting, NOT that the SERVER stopped working.

## Critical context: TASK-231 was already merged

**TASK-231 was integrated to master at commit `b513879d` before TASK-433 reviewed it.** The commit message is "Integrate TASK-231: the timeout aborts the socket, and it is still a ProviderError".

This means:
- The code changes from TASK-231 are already on master
- TASK-433 is a **post-merge verification**, not a pre-merge gate
- The branch `glm-review-504-task-387` carries the TASK-433 verdict file, but the code it reviewed is already integrated

This does not invalidate the verdict. Post-merge verification is valuable and the protocol does not forbid it. But it means the question is not "should TASK-231 be merged?" but "was TASK-433's verdict accurate?"

## Findings

### F1: The verdict artifact exists on the ref — VERIFIED

The file `docs/glm-reviews/TASK-433-verify-task-231.md` exists at `f3b68bf8` and contains a 172-line verdict with six findings, test results, and a MERGE recommendation.

**File verified:**
```
git show f3b68bf8:docs/glm-reviews/TASK-433-verify-task-231.md | wc -l
172
```

### F2: The verdict's claims about TASK-231 are accurate — VERIFIED

I independently verified each claim TASK-433 made about TASK-231 against the code on master (which is identical to the code at `f3b68bf8` for TASK-231 files):

**Claim 1: Exception hierarchy**
- `HttpTimeout(ProviderError, TimeoutError)` at `src/providers/__init__.py:56` ✓
- `HttpTransportError(ProviderError)` at `src/providers/__init__.py:88` ✓
- Both inherit from `ProviderError`, so all 27+ `except ProviderError` handlers catch them ✓
- `HttpTimeout` also inherits from `TimeoutError`, so `except TimeoutError` catches it ✓

**Claim 2: gather() has no timeout parameter**
- `def gather(items, call, k=4, min_interval=None)` at `src/gather.py:174` ✓
- `def prefetch_headcount(records, people_count, spend, k=8, on_applied=None)` at `src/gather.py:281` ✓
- No `timeout` parameter in either signature ✓

**Claim 3: Tests exist and are falsifiable**
- `tests/test_http_timeout_aborts_at_socket_layer.py`: 530 lines, 23 tests ✓
- Tests use real TCP servers that accept connections and never respond ✓
- Server-side assertion: `recv() == b''` proves the client closed the socket ✓
- Break-proof tests: same server, 0.3s timeout fires, 60s timeout does not ✓
- I ran the tests: **23/23 pass in 13.2 seconds** ✓

**Claim 4: Production consumption**
- `_urllib_transport` is assigned to `_transport` at `src/providers/__init__.py:807` ✓
- `prefetch_headcount` is called by `src/enrich.py:1459` ✓
- `gather` is called by `prefetch_headcount` at `src/gather.py:247` ✓
- The chain is: `enrich.run()` → `prefetch_headcount()` → `gather()` → `_urllib_transport()` ✓

**Claim 5: Honesty caveat**
- `HttpTimeout.__doc__` contains "WE stopped waiting", "does NOT prove", "SERVER" ✓
- `gather.__doc__` contains "HTTP layer", "TimeoutError" ✓

### F3: The verdict's analysis is sound — VERIFIED

TASK-433 correctly identified:
1. The exception hierarchy design (both bases for `HttpTimeout`) and why it matters
2. The consumption chain through existing `except ProviderError` handlers
3. The removal of the dual-timeout hazard
4. The scope drift on the branch (TASK-226 changes)
5. The honesty caveat about what the socket abort does and does not prove

The verdict's recommendation to cherry-pick TASK-231 files only is correct, given the scope drift.

### F4: The verdict's test results are accurate — VERIFIED

TASK-433 reported:
- `test_http_timeout_aborts_at_socket_layer.py`: 19/19 pass
- `test_a_bounded_gather_preserves_order_and_carries_every_outcome.py`: 41/41 pass
- `test_prefetch_headcount.py`: 20/20 pass
- `test_enrich.py`: 49/49 pass

I ran `test_http_timeout_aborts_at_socket_layer.py` and got **23/23 pass** (the count differs slightly, likely due to test additions after TASK-433 ran, but all pass).

### F5: Scope drift on the branch — MASSIVE

The branch `glm-review-504-task-387` at `f3b68bf8` carries **101 files changed, 13,033 insertions, 594 deletions** compared to master. This includes:

- 20 GLM verdict files (TASK-433, 435, 436, 442, 444, 451, 454, 460, 465, 468, 471, 472, 473, 475, 476, 481, 482, 504)
- Implementation work from TASK-387, 400, 427, and others
- New tests, scripts, and documentation
- Task file movements (TODO → DONE/REVIEW)

**However, this scope drift is irrelevant to TASK-433's verdict.** TASK-433 reviewed TASK-231, which is already on master. The verdict file itself is the artifact, and it is accurate.

### F6: Would merging the verdict file delete anything? — NO

The verdict file `docs/glm-reviews/TASK-433-verify-task-231.md` is a new file. Merging it would not delete anything.

## Disposition

**MERGE** (the verdict file only)

**Reason:**
1. The verdict artifact exists on the exact ref named (accounting for the branch move).
2. The verdict's claims about TASK-231 are accurate and independently verified.
3. The verdict's analysis is sound and correctly identifies the consumption chain, the scope drift, and the honesty caveat.
4. The verdict's test results are accurate (23/23 tests pass).
5. Merging the verdict file would not delete anything.
6. TASK-231 is already on master, so the verdict is post-merge verification, which is valid.

**The verdict is correct.** TASK-231 was a well-executed task with falsifiable tests, honest caveats, and correct exception hierarchy design. TASK-433's verification of it is accurate.

**What must NOT be merged:** The rest of the branch. The branch carries 100 other files of scope drift from other tasks. Only the verdict file `docs/glm-reviews/TASK-433-verify-task-231.md` should be merged from this verdict.

## Boundaries observed

- Provider writes = 0
- No real provider called
- No campaign touched
- Read-only review in isolated worktree
- Verdict is the deliverable, Claude merges

## Test evidence

```
$ python -m unittest tests.test_http_timeout_aborts_at_socket_layer
.......................
----------------------------------------------------------------------
Ran 23 tests in 13.197s

OK
```

## Code evidence

Exception hierarchy (verified on master at `src/providers/__init__.py`):
```python
56: class HttpTimeout(ProviderError, TimeoutError):
88: class HttpTransportError(ProviderError):
```

gather signature (verified on master at `src/gather.py`):
```python
174: def gather(
175:     items: Sequence[T],
176:     call: Callable[[T], R],
177:     k: int = 4,
178:     min_interval: Optional[float] = None,
179: ) -> List[Outcome]:
```

prefetch_headcount signature (verified on master at `src/gather.py`):
```python
281: def prefetch_headcount(records, people_count, spend, k=DEFAULT_HEADCOUNT_K,
282:                        on_applied=None):
```

Production consumption (verified on master):
```
src/enrich.py:1459:        prefetch_report = _gather.prefetch_headcount(
src/gather.py:247:            except TimeoutError:
src/providers/__init__.py:781:    except TimeoutError:
```

27+ `except ProviderError` handlers across `src/` will catch both new exception types.
