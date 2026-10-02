# TASK-960 — the spend ledger resolves per worktree, for every caller

## Why

Model spend must be attributed to a client or a task — operator, 2026-10-02.
Measured the same evening, from both sides in the same minute:

    main checkout                    39 glm rows
    the verification worktree         2 glm rows   (its own calls, 30,688 micro-USD)

`spendledger.path()` returns
`os.path.join(os.path.dirname(store.queue_path()), "spend-ledger.jsonl")`, and
`store.queue_path()` resolves against the CALLING TREE's root. `work/` is
gitignored, so every `git worktree add` tree has its own — which means anything
that spends money from a worktree bills a file that is deleted with the tree and
is invisible to the production spend audit. An audit that reports clean because
it watched an empty file is worse than none; CLAUDE.md says so about this exact
ledger.

## The scope, swept rather than sampled

GLM named two stranded rows. A sweep of every `work/spend-ledger.jsonl` on the
machine found **37 glm rows, 482,732 micro-USD, across six ledgers** — against
41 rows in the production one. The control that the reader is not blind: the
same reader found those 41.

      5 rows    82,826 uUSD   wt-qwen-940        TASK-903 / 940 / 942 / 946
      2 rows    30,688 uUSD   glm-940            TASK-940
      5 rows    34,820 uUSD   wt-li              unattributed
      4 rows    77,916 uUSD   wt-steps           unattributed
     17 rows   220,618 uUSD   wt-gen             unattributed
      4 rows    35,864 uUSD   resonate-qwen-worker   _model

The first line is the one that matters beyond the money: **the four GLM verdicts
this queue is being gated on were billed into a worktree ledger** that the
production audit cannot see and that temp cleanup will eventually delete.

All six were COPIED — not moved, not migrated — to
`work/stranded-spend-2026-10-02/` in the main checkout, which is gitignored
production storage rather than temp, with an `INDEX.json` whose totals were read
back from the copies (37 rows claimed, 37 read back). The originals are
untouched, so this task's migration still finds them where they were.

This is the third appearance of one trap. The suite lock escaped it
(`--path-format=absolute --git-common-dir`), `config/.env` escaped it the same
way, and `scripts/glm_verify_branch.py` escaped it for ITSELF on
`task-940-glm-verifier` at `905a61c2` by exporting `SPEND_LEDGER`. **Every other
caller is still in it**, and a per-script escape is a workaround, not the fix:
the next tool that spends from a worktree will be invisible again, and nobody
will know until an audit is needed.

How it was found is worth keeping: it made an acceptance command unfailable. A
fresh acceptance worktree has no ledger, so `0 rows, 0 clients` satisfied
`assert isinstance(by, dict)` — no ledger CONTENT could break it, including the
retired-tenant blindness (A10) the check was written to guard.

## What to decide, with the repository's own precedent

`work/` holds production state and is deliberately per-tree for the QUEUE: a
worktree must not write records into production. **Spend is not queue state.**
It is money already gone, and there is exactly one of it. So the ledger belongs
beside the MAIN checkout's `work/`, resolved the way the lock resolves — and a
RELATIVE answer from git is refused rather than resolved, because `abspath`
would put it back inside the calling tree.

The reserved/alerts paths derive from `path()` already and must keep deriving,
not grow their own copy.

## Acceptance

Run every command **from a worktree**, because the main checkout passes them
trivially and would prove nothing.

```
python -c "import sys,os; sys.path.insert(0,'.'); from src import spendledger; p=spendledger.path(); here=os.path.abspath('.')+os.sep; assert not p.startswith(here), 'the ledger is inside the calling tree: '+p; assert os.path.isfile(p), 'resolved outside the tree but to nothing: '+p; print('OK one ledger:',p)"
```

```
python -c "import sys,os; sys.path.insert(0,'.'); from src import spendledger; a=spendledger.alerts_path(); p=spendledger.path(); assert os.path.dirname(a)==os.path.dirname(p), 'alerts drifted from the ledger: '+a+' vs '+p; print('OK alerts derive from the ledger')"
```

```
python -c "import sys,os; sys.path.insert(0,'.'); os.environ['SPEND_LEDGER']=os.path.join(os.path.abspath('.'),'chosen.jsonl'); from src import spendledger; assert spendledger.path().endswith('chosen.jsonl'), spendledger.path(); print('OK an explicit override still wins')"
```

### NEGATIVE CONTROL

Command 1 fails TODAY from any worktree with `the ledger is inside the calling
tree`, and that is the defect itself. Its second assertion is the control on the
first: a path that escapes the tree but points at nothing is not an escape, and
without it a fix that returned a plausible path nobody writes to would pass.
Command 3 is the control on the fix's direction — the documented
`SPEND_LEDGER` override must keep working, or this task breaks somebody's
deliberate redirection while fixing the default.

## Files

`src/spendledger.py`. `src/store.py` only if the resolution belongs there for
other callers too — decide by measurement of who else needs it, not by
symmetry. The one-place-two-callers resolution already written in
`scripts/glm_verify_branch.py` (`main_checkout_root`) is the shape; do not grow
a third copy of it.

## The migration, which is NOT done and needs the operator

Appending 37 rows to the canonical money ledger is a mutation of the spend
record, and a wrong one double-counts the audit it is meant to repair. It gets
what the 220-approval revocation got: a script with `--dry-run`, a marker field
naming the file each row came from so a second run cannot double-count, and a
readback from the file rather than from memory. The operator's word first.

Until then the rows are quarantined, the totals are above, and the production
audit is understated by 482,732 micro-USD — recorded here so the number is not
rediscovered.

## Not in scope

Moving `work/queue.jsonl` or `work/campaigns.jsonl`. They are production record
state and stay per-tree on purpose.
