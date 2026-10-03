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
