"""Lane R boot: point every store read at the PRODUCTION checkout.

A worktree carries its own `work/`, and this one's is EMPTY. A client probe
resolved against an empty store answers "unbound" and a population count
answers zero - both of which read as a measurement. So the store root is an
absolute path into the production checkout, taken from `RESONATE_PROD_ROOT`
when it is set and falling back to the checkout this worktree hangs off.

Reads only. Nothing in lane R writes to the production tree.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WORKTREE = os.path.dirname(os.path.dirname(HERE))


def prod_root():
    """Absolute path to the PRODUCTION checkout that owns the live `work/`."""
    env = os.environ.get("RESONATE_PROD_ROOT")
    if env:
        return os.path.abspath(env)
    # .../<prod>/.claude/worktrees/<agent>  ->  <prod>
    parts = WORKTREE.replace("\\", "/").split("/")
    if len(parts) >= 3 and parts[-3] == ".claude" and parts[-2] == "worktrees":
        return os.path.abspath("/".join(parts[:-3]))
    raise RuntimeError(
        "lane R: cannot locate the production checkout from %r. Set "
        "RESONATE_PROD_ROOT." % WORKTREE)


PROD = prod_root()
WORK = os.path.join(PROD, "work")
QUEUE = os.path.join(WORK, "queue.jsonl")
CAMPAIGNS = os.path.join(WORK, "campaigns.jsonl")

for _p in (QUEUE, CAMPAIGNS):
    if not os.path.exists(_p):
        raise RuntimeError(
            "lane R: %s does not exist. A missing store is not an empty "
            "store and must not be counted as one." % _p)

# The repository's own modules come from THIS worktree, at the sha under test.
if WORKTREE not in sys.path:
    sys.path.insert(0, WORKTREE)
_SRC = os.path.join(WORKTREE, "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)
