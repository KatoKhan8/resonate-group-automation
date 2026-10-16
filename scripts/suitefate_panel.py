#!/usr/bin/env python3
"""Count the suites whose launcher never learned the result. Read-only.

    LANE_OPS_DIR=C:\\Users\\Zvonimir\\Desktop\\resonate-ops \\
        py -3 scripts/suitefate_panel.py

Prints the same numbers `/admin/lanes` renders, in a terminal, so the count
can be taken and quoted without starting a web server - the convention
`scripts/depth_panel.py` and `scripts/rework_panel.py` already set for this
lane's panels.

IT WRITES NOTHING. No lock is cleared, no process is signalled, no brief is
moved, and no lane worktree is opened. The one machine-wide lock is READ, and
if it is stranded that is reported with its pid and mtime and left exactly
where it is: `suitelock.acquire` self-heals a stale lock on the next run, and
clearing one by hand is an operator action on a shared resource.
"""

import argparse
import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import lanes            # noqa: E402
from src import suitefate as sf  # noqa: E402
from src.web import api          # noqa: E402


def _clock(when):
    return when.strftime("%m-%d %H:%M:%S") if when else "UNKNOWN"


def main():
    parser = argparse.ArgumentParser(description="Suite results nobody read")
    parser.add_argument("--root", default=None,
                        help="the lane estate; defaults to $LANE_OPS_DIR")
    parser.add_argument("--rows", action="store_true",
                        help="print every launch, not only the per-lane roll-up")
    args = parser.parse_args()

    data = api.lane_suite_fates(root=args.root)
    if data.get("state") != lanes.PRESENT:
        print("estate state: %s - nothing has said where the lane estate is, "
              "so this is the ABSENCE of an answer and not a clean zero."
              % data.get("state"))
        print("set %s to the directory holding LANE-*.md, queue/ and logs/"
              % lanes.OPS_DIR)
        return 2

    print("read at %s   estate %s" % (data["at"].strftime("%Y-%m-%d %H:%M:%S"),
                                      data["root_name"]))
    print("process table read: %s   lock authority read: %s"
          % (data["table_read"], data["lock_readable"]))
    print("artefacts walked: %d%s"
          % (data["artefacts_walked"],
             "  (CAPPED - the walk hit its limit)" if data["artefacts_capped"]
             else ""))
    print()
    print("launches evidenced      %d" % data["total"])
    print("  result read           %d" % data["read"])
    print("  DIED UNREAD           %d" % data["unread"])
    print("  landed, no record     %d"
          % data["tally"].get(sf.FATE_LANDED_UNRECORDED, 0))
    print("  still open            %d" % data["tally"].get(sf.FATE_RUNNING, 0))
    print("  UNPLACEABLE           %d  (%s%% of all launches)"
          % (data["hole"], data["hole_share"]))
    print()
    print("MINUTES OF SUITE TIME WHOSE RESULT NOBODY READ: %.1f"
          % data["unread_minutes"])
    if data["unread_unmeasured"]:
        print("  plus %d launch(es) whose burn is UNMEASURABLE: a killed run "
              "writes no verdict, so its suite time is between zero and now. "
              "Counted as a launch, never folded in as a zero."
              % data["unread_unmeasured"])
    print()
    print("THE TWO AXES, COUNTED SEPARATELY - of the died-unread launches,")
    print("  %d left the lock STRANDED" % data["unread_lock_stranded"])
    print("  %d released the lock CLEANLY" % data["unread_lock_released"])
    print("  independence measured on this estate: %s"
          % ("YES - neither state can stand in for the other"
             if data["independent"] else
             "NO - only one of the two kinds is present, so this estate "
             "alone does not demonstrate it"))
    print()
    print("%-13s %9s %9s %7s %7s %7s %9s" % (
        "lane", "launches", "placeable", "read", "UNREAD", "no-rec",
        "unread min"))
    for row in data["lane_rows"]:
        print("%-13s %9d %9d %7d %7d %7d %9.1f%s" % (
            row["lane"] or "(no lane)", row["launches"], row["decided"],
            row["read"], row["unread"], row["unrecorded"],
            row["unread_seconds"] / 60.0,
            "  +%d unmeasured" % row["unread_unmeasured"]
            if row["unread_unmeasured"] else ""))

    if args.rows:
        print()
        for row in data["rows"]:
            print("--- %s %s pid=%s" % (row["source"],
                                        row["lane"] or "(no lane)",
                                        row["pid"]))
            print("    launcher : %s  (closed %s)"
                  % (row["launcher"] or "NONE IDENTIFIED",
                     _clock(row["launcher_done"])))
            print("    launch   : %s   [%s]" % (_clock(row["launch_at"]),
                                                row["launch_clock"]))
            print("    result   : %s   [%s]" % (_clock(row["result_at"]),
                                                row["result_clock"]))
            print("    FATE     : %s" % row["fate_label"])
            print("    LOCK     : %s" % row["lock_label"])
            print("    why      : %s" % row["why"])

    # The stranded lock, reported with everything a person needs and NOT
    # cleared. Printed last so it is the thing left on screen.
    stranded = [r for r in data["rows"]
                if r["lock_disposition"] == sf.LOCKD_STRANDED]
    for row in stranded:
        print()
        print("LOCK STRANDED AND LEFT ALONE: pid %s, taken %s, worktree %s"
              % (row["pid"], _clock(row["launch_at"]),
                 row.get("worktree") or "unknown"))
        print("  Not cleared by this script and not to be cleared by hand: "
              "`suitelock.acquire` takes over a stale lock on the next run "
              "and announces the dead pid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
