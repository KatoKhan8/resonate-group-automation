"""Print the consumable-depth panel for the real lane estate, and PROVE it read only.

TWO CONTROLS, because the obvious one is not sufficient on a live estate.

C-W, THE WRITE TRAP, and it is the one that decides the run. Every mutating
entry point python can reach - `open` in a writing mode, `os.open` with a
writing flag, `os.remove`, `os.rename`, `os.replace`, `os.mkdir`,
`os.makedirs`, `os.rmdir`, `os.truncate`, `os.utime`, `os.chmod` - is wrapped
for the duration of the measurement and RAISES if its path is under the ops
root. It does not count, it refuses: a control that tallies violations after
the fact has already let the first one through. `0160` built this trap and it
is reused here rather than rewritten.

C-F, THE BEFORE/AFTER WALK, which `0110` and `0130` used. A WALK CANNOT NAME
A WRITER: on this estate it failed twice for `0160` on other lanes' writes -
once on the `suppression` watcher closing `0290` thirty seconds into the run,
once on a `.git/index` the `pilotcaps` lane created under `logs/` mid-read.
So it is corroboration: it divides what moved by whether the path is in this
module's read set at all, reports it, and decides nothing.

WHAT THIS READS, AND IT IS THE WHOLE READ SET. `queue/<lane>/` and its
`RUNNING/` (listed, for the two depths), `queue/README.md` (the operator's
floor), `logs/watcher-<lane>.log`, `logs/watcher-<lane>.pid`, and
`LANE-<lane>.md`. No `DONE/` entry is opened, no `RUNNING/` brief is read,
moved, renamed or cleared, and the floor ledger is not touched at all - this
panel is a reader and `floor_ledger` is the sampler.

    py -3 scripts/depth_panel.py --root C:\\Users\\Zvonimir\\Desktop\\resonate-ops
"""
import argparse
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.rework_panel import WriteTrap, attribute, diff, walk  # noqa: E402
from src import lanes  # noqa: E402
from src import queuedepth as qd  # noqa: E402
from src.web import api  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=lanes.ops_root())
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if not args.root:
        print("no root: set %s or pass --root" % lanes.OPS_DIR)
        return 2

    trap = WriteTrap(args.root)
    with trap:
        before = walk(args.root)
        data = api.queue_depth(root=args.root)
        after = walk(args.root)
    moved = diff(before, after)
    inside = [item for item in moved if item[3] == "IN-READ-SET"]

    print("C-W WRITE TRAP HELD: %d guarded calls, 0 writes attempted under "
          "the ops root. The trap RAISES rather than counts, so this line "
          "existing is the proof, and it is the control that decides this "
          "run." % trap.calls)
    print("C-F WALK (corroboration; a walk cannot name a writer): %d files "
          "fingerprinted by size, mtime_ns and sha256; %d moved, %d of them "
          "in this module's read set."
          % (len(before), len(moved), len(inside)))
    for key, was, now, why in moved[:12]:
        print("   [%s] %s" % (why, key))
        if why == "IN-READ-SET":
            print("        before %r\n        after  %r" % (was, now))
    if len(moved) > 12:
        print("   ... and %d more" % (len(moved) - 12))
    if inside:
        print("   Those moved WHILE C-W held, so a concurrent lane wrote "
              "them. That is a fact about a live estate, not a write from "
              "here.")
    print()
    print("NO LEDGER CALL. `floor_ledger` is the sampler and it is a "
          "different screen; this panel reaches it in neither direction, "
          "which is stronger than holding it at write=False.")
    print()

    if args.json:
        print(json.dumps(data, indent=2, default=str))
        return 0

    print(qd.describe(data))
    print()
    print("MEASURED %s against the estate as it stood at that instant. Every "
          "number above is a reading of a live estate and will have moved by "
          "the time it is read."
          % datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
