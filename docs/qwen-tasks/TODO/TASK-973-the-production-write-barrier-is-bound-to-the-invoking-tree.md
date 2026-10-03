# TASK-973 — the production-write barrier protects the wrong `work/` when the suite runs from a worktree

Opened 2026-10-03 from the multi-part GLM review of
`task-guard-regressions-rebased` (part 2 of 5, FAIL). **GLM's headline
mechanism was REFUTED by measurement and a different, larger defect was found
underneath it.** Both halves are written down, because a refuted mechanism that
is quietly dropped is how the same claim comes back next week.

## What GLM said, and why it is wrong as stated

> "three setUp sites write the campaign ledger behind a one-path blacklist
> while CAMPAIGNS can aim the write at any other real ledger; exported
> CAMPAIGNS + the suite overwrites operator state"

The write it names is real — `tests/test_an_internal_campaign_is_never_touched.py:331`
deliberately corrupts the ledger to prove an unreadable authority yields
`unknown`:

    with open(store.campaigns_path(), "w", encoding="utf-8") as handle:
        handle.write("{this is not json\n")

But an exported `CAMPAIGNS` does **not** reach it. Measured, not reasoned: a
sentinel ledger was written to a temp path, `CAMPAIGNS` was exported at it, the
whole module was run (59 tests, exit 0), and the sentinel came back
**byte-identical**. The reason is `tests/base.py:705`, `ProviderTest.setUp` →
`store.use_directory(...)`, which points `QUEUE` into a tempdir and **pops
every entry of `STATE_OVERRIDES`, `CAMPAIGNS` among them**
(`src/store.py:203-205`). The inherited `setUp` runs before any test body, so
the export is gone by the time line 331 resolves its path.

**So the branch does not overwrite operator state, and that is not why it
fails.** It fails on what the second layer turned out to be.

## The defect, measured

`src/store.py:980` is the barrier every state write passes:

    if not under_test(): return
    target = os.path.abspath(path)
    if target == PRODUCTION_WORK or target.startswith(PRODUCTION_WORK + os.sep):
        raise ProductionStateUnderTest(...)

and `PRODUCTION_WORK = os.path.join(ROOT, "work")` — `ROOT` being **the tree
the code was imported from**. Measured from the gate worktree with `unittest`
imported, so the barrier is live:

    this worktree's work/   -> REFUSED
    MAIN checkout's work/   -> ALLOWED   <-- not behind the barrier
    MAIN campaigns.jsonl    -> ALLOWED   <-- not behind the barrier

**Every suite in this project's merge gate runs from a worktree.** So for every
run that has ever gated a merge, the barrier was pointed at a gitignored,
empty, per-tree `work/` — and the one file it exists to defend, the main
checkout's `work/campaigns.jsonl`, was outside it. The guard is not weak here;
it is aimed somewhere else, and its error message ("Isolate the store first")
could never have printed.

This is the identical trap CLAUDE.md already records for the suite lock, with
the fix already named there: **`ROOT` resolves per-tree, so anything that must
be machine-wide resolves through
`git rev-parse --path-format=absolute --git-common-dir`.** The lock learned it
on 2026-10-02 after six suites ran at once. The write barrier never did.

### Why nothing has been destroyed yet

    work/campaigns.jsonl   117,823 bytes
                           mtime 2026-09-30 19:22:26
                           69 rows parsed, 0 unparseable

Intact, through a night of seven suite runs and several commands that export
`CAMPAIGNS` at exactly that file — because `use_directory` clears the override
for every `ProviderTest`, which is the layer that actually held. **The estate
was defended by the layer nobody advertised as the barrier, while the barrier
watched an empty directory.** A test module that writes state without
`use_directory` is all it would take, and nothing refuses one.

## What to do

1. Resolve the protected directory through `--git-common-dir`, so the barrier
   covers the MAIN checkout's `work/` from every worktree, and refuse a
   relative answer from git rather than resolving it — `src/suitelock.py`
   already does exactly this and is the pattern to copy.
2. Keep the invoking tree's own `work/` refused as well. Both, not either.
3. Leave `use_directory` as it is. It is the layer that worked.

## Acceptance

```
python -c "import os,subprocess,sys,tempfile,unittest; sys.path.insert(0,'.'); from src import store; tc=unittest.TestCase(); assert store.under_test(), 'the barrier would be inert in this process'; c=subprocess.run(['git','rev-parse','--path-format=absolute','--git-common-dir'],capture_output=True,text=True,encoding='utf-8').stdout.strip(); assert c and os.path.isabs(c), 'git would not answer absolutely'; main=os.path.abspath(os.path.join(os.path.dirname(c),'work')); tc.assertRaises(store.ProductionStateUnderTest, store.refuse_production_write, os.path.join(main,'campaigns.jsonl')); tc.assertRaises(store.ProductionStateUnderTest, store.refuse_production_write, main); tc.assertRaises(store.ProductionStateUnderTest, store.refuse_production_write, store.PRODUCTION_WORK); store.refuse_production_write(os.path.join(tempfile.mkdtemp(prefix='barrier-'),'queue.jsonl')); print('OK the main checkout work/ and this tree work/ are both refused, an isolated tempdir is still allowed')"
```

```
python -c "import hashlib,os,sys,tempfile,unittest; sys.path.insert(0,'.'); from src import store; t=tempfile.mkdtemp(prefix='sentinel-'); store.PRODUCTION_WORK=t; led=os.path.join(t,'campaigns.jsonl'); open(led,'w',encoding='utf-8').write('{\"campaign_id\": \"sentinel\"}\n'); before=hashlib.md5(open(led,'rb').read()).hexdigest(); os.environ['CAMPAIGNS']=led; from src import campaigns; tc=unittest.TestCase(); tc.assertRaises(store.ProductionStateUnderTest, campaigns.save, [campaigns.new_campaign('x','productive','x',created_by='test')]); assert before==hashlib.md5(open(led,'rb').read()).hexdigest(), 'the file was mutated before the refusal - the guard runs too late'; print('OK the write path refuses and mutates nothing')"
```

```
python -m unittest tests.test_an_internal_campaign_is_never_touched -v
```

### NEGATIVE CONTROL

**Command 1 fails today**, from this worktree, on the first `assertRaises` —
that is the measurement above turned into an assertion. It cannot be satisfied
by making the guard paranoid: its third assertion keeps the invoking tree
refused, so the fix may not trade one directory for the other, and its last
line requires an isolated tempdir to stay WRITABLE, so a barrier that refuses
everything fails here in a second instead of reddening 231 modules forty
minutes later. It asserts nothing about a path it did not resolve from git, and
its first assertion is the control that the barrier is live at all in the
process doing the asking — `under_test()` reads `sys.modules`, so a command
that forgot to import `unittest` would pass while measuring a disabled guard.

Command 2 is the effect half, and because it attempts a REAL `campaigns.save()`
it is pointed at a sentinel in a tempdir rather than at the estate: it patches
the module's notion of the protected directory, which means that **if the fix
replaces that constant with a resolver, this command fails rather than passing
vacuously** — the right direction for a seam that moved, and it is said here so
the next reader updates the command instead of deleting it. Its second
assertion is the one that matters most: a refusal landing after `os.makedirs`
or after the temp file is in place is not a refusal, and the docstring at
`src/store.py:990` already promises it comes first.

Command 3 is the branch's own module, 59 tests, which must stay green — the
defect is in the barrier, not in the branch's guards.

## Files

`src/store.py` (`PRODUCTION_WORK`, `refuse_production_write`), with
`src/suitelock.py` as the pattern for resolving one machine-wide path.
`tests/base.py` is NOT in scope: `use_directory` is the layer that held.

## Not in scope

The deliberate corruption at line 331. It proves fail-closed on an unreadable
authority, which is invariant 0, and it belongs in the suite. What must change
is the barrier behind it.

---

# RESULT — branch `task-973-write-barrier`, 2026-10-03

Every command below was EXECUTED before being written down, from the neutral
worktree `wt-lane2` (A44: no provider token in the path), with master
`e967271d` as the base. The reference measurements were taken in a second
neutral worktree, `wt-lane2ref`, detached at the same `e967271d`.

## The defect, reproduced before the fix

    git-common-dir        C:/Users/Zvonimir/Desktop/resonate-group-automation/.git
    store.ROOT            ...\scratchpad\wt-lane2
    store.PRODUCTION_WORK ...\scratchpad\wt-lane2\work
    under_test()          True

    MAIN work/campaigns.jsonl    ALLOWED      <- the OS authority, unguarded
    MAIN work/                   ALLOWED
    this tree work/              REFUSED
    this tree work/queue.jsonl   REFUSED
    isolated tempdir             ALLOWED

Acceptance command 1 failed on its FIRST `assertRaises`, which is that table
turned into an assertion. Exactly as the task predicted.

## The fix

`src/store.py`. `PRODUCTION_WORK` is unchanged and still refused.
`main_checkout_work()` resolves the MAIN checkout's `work/` through
`git rev-parse --path-format=absolute --git-common-dir`, copying
`src/suitelock._git_common_dir` including its refusal of a RELATIVE answer
(`abspath` would resolve it against the caller's cwd - from a worktree, that
worktree - which is the per-tree barrier being fixed). `protected_directories()`
returns BOTH and is what `refuse_production_write` now reads, per call, so a
caller that patches `PRODUCTION_WORK` - acceptance command 2 does - still moves
the barrier. From the MAIN checkout the two resolve to the same directory and
are deduplicated, so the change is a no-op there and additive from a worktree.

### The cache, measured rather than assumed

    git rev-parse                        29.4 ms per call   (20 calls, 0.588 s)
    barrier before the fix                1.6 us per call   (2000 calls)
    barrier after the fix, warm cache     2.26 us per call  (5000 calls)
    barrier after the fix, cold           25.3 ms           (one git)
    barrier with the cache defeated      25.8 ms per call   (20 calls)

A factor of about eleven thousand, so resolving per write was not an option.
The cache is keyed on the CWD, because that is what git answers relative to.
**A FAILURE IS NEVER CACHED**: one ask from outside a repository would
otherwise switch the main-checkout half of the barrier off for the rest of the
process, silently and permanently. `use_directory` calls
`reset_main_work_cache()`, so no cached resolution outlives a redirect.

## Acceptance

    command 1   FAILED before the fix (first assertRaises), PASSES after
    command 2   passed before and after - it is the seam check, not the
                negative control, and it still passes because the fix kept
                `PRODUCTION_WORK` a module global read per call
    command 3   CANNOT BE RUN ON THIS BRANCH, and the task file is wrong about
                it being runnable here

**Command 3 contradicts the measurement.**
`tests/test_an_internal_campaign_is_never_touched` **does not exist on
master**: `ModuleNotFoundError: No module named
'tests.test_an_internal_campaign_is_never_touched'`. Measured across the
branches, it exists on `task-guard-regressions-rebased`,
`task-guard-regressions` and `task-internal-campaign-guard` and on 0 of
master. It was never the barrier's own module - it is the GLM review's
subject branch, which is where TASK-973 was written from. Whoever merges that
branch should re-run command 3 there; it cannot gate this one.

Substituted, and it is the better module anyway: `tests/test_tests_cannot_write_client_state`,
which is the barrier's own test file.

    python -m unittest tests.test_tests_cannot_write_client_state -v
    Ran 23 tests ... OK          (15 before this branch, 8 added)

## The mutation proofs

`__pycache__` wiped before each run, and `src/store.py` restored and
re-verified byte-identically afterwards (`git hash-object`
`f8bc166f989ca21623c98c12031d28a03a46fc1d` before and after).

**MUTATION A** - the main-checkout half deleted from `protected_directories`,
i.e. master's behaviour. Exactly 4 of the 23 red, each for its own reason:

    test_the_main_checkouts_work_directory_is_refused    ProductionStateUnderTest not raised
    test_the_cache_does_not_outlive_a_use_directory_redirect
                                                         ProductionStateUnderTest not raised
    test_both_directories_are_named_by_the_seam          '...\resonate-group-automation\work'
                                                         not found in ['...\wt-lane2\work']
    test_the_resolution_is_cached_rather_than_a_subprocess_per_write
                                                         0 != 1 : fifty writes cost 0 git resolutions

and the two controls stayed GREEN - `test_an_isolated_tempdir_is_still_writable`
and `test_the_invoking_trees_own_work_is_still_refused` - which is what says
the mutation was observed by the tests that should see it and by no others.

**MUTATION B was INEFFECTIVE AND IS RECORDED BECAUSE OF IT.** The first attempt
at a "refuse everything" barrier appended `os.path.abspath(os.sep)` to the
protected list and every test stayed green. Not because the control is weak:
on Windows `abspath(os.sep)` is `C:\`, and `target.startswith("C:\\" + os.sep)`
tests for a DOUBLE separator that no real path carries. A validator that
agreed with me. Named here so the next reader does not reach for it.

**MUTATION B2** - the temp directory added to the protected list, a genuinely
paranoid barrier. Six tests ERROR, three of them the isolated-directory
controls in this very file, and acceptance command 1's last line raises
`ProductionStateUnderTest` on `C:\...\Temp\barrier-...\queue.jsonl`. Under a
second, rather than reddening 231 modules forty minutes later - which is
exactly what the task said that control was for.

## Blast radius: zero new failing names

15 modules that touch `PRODUCTION_WORK`, `refuse_production_write` or
`use_directory`, run per module, name sets compared as SETS:

    reference (wt-lane2ref, e967271d)   4 failing names
    branch    (wt-lane2)                3 failing names
    NEW on the branch                   0
    gone                                1

The three that stand on both are pre-existing:
`test_emailbison_posts_only_to_routes_it_declares`,
`test_no_module_issues_an_http_post_outside_the_named_ones` and
`test_the_checklist_has_not_fallen_behind_the_code` (which fails on
`['reviewapproval']` identically in both trees).

**The one that went away is NOT a fix of mine, and chasing it found a real
defect in that test.** `tests.test_invariants.TestTheBarrierCoversEveryWriter.test_nothing_was_written_by_that`
calls `os.listdir(store.PRODUCTION_WORK)` with no guard that the directory
exists. Verified positively, the way a disappearing name has to be: it RUNS
AND PASSES in the full-module run on both trees. It only errored in the
reference's first run because that worktree had just been created and had no
`work/` yet. Reproduced deliberately on a third, untouched master worktree:

    FileNotFoundError: [WinError 3] ...\wt-lane2fresh\work
    (tests.test_invariants.TestTheBarrierCoversEveryWriter.test_nothing_was_written_by_that)

So on master, that invariant test ERRORS on any worktree whose `work/` has not
yet been created by something else - and every gate suite runs from a worktree.
It is a one-line fix (`os.makedirs(..., exist_ok=True)`, or listing defensively)
and it is deliberately NOT in this diff, which answers to TASK-973 only. It
needs its own task.

## What was not done

No full suite. One suite runs on this machine at a time and the main session
owns the lock, so this branch carries per-module name-set diffs and not a
231-name reference run. It needs one before it merges.

## Files changed

`src/store.py` (+123/-5), `tests/test_tests_cannot_write_client_state.py`
(+184), and this result block.
