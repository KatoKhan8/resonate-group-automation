#!/usr/bin/env python3
"""Is the suite lock real, and if so how much longer? Reads. Writes nothing.

WHY THIS SCRIPT EXISTS AND NOT JUST THE FUNCTION. qwen TASK 0150 measured the
cost of having no such reader: the lock was held 82.4% of 2026-10-15 and 60.5%
of that by a process that no longer existed. That costs a lane calling
`suitelock.acquire()` nothing - the stale takeover self-heals in one poll - and
it costs exactly the lanes that were told to read `work/suite.lock` by hand and
decide. `webapp/0040` did that at ~23:52, wrote `SUITE: NOT OBTAINED`, and the
holder released at 23:55:33 with 38 minutes of its budget left.

`glm/0050` specified this script. TASK 0150 then measured that it existed on no
ref at all - `git log --all`, `git grep` - so every lane since has been reading
the raw file. A function with no caller is this repository's named recurring
defect; this is the caller.

    py -3 scripts/suite_lock_status.py
    py -3 scripts/suite_lock_status.py --json

Exit codes, so a shell can branch without parsing prose:

    0  FREE or STALE - a suite may start now (`acquire` would take it)
    1  HELD by a live holder - waiting is the only honest option
    2  UNKNOWN - the lock file could not be read, which is never FREE

NOTHING HERE TAKES, RELEASES, PRUNES OR REPAIRS ANYTHING. It is a read, and the
queue it counts is counted without deleting a single ticket.
"""
import argparse
import json
import os
import sys


def build_parser():
    parser = argparse.ArgumentParser(
        description="Report the suite lock's state, liveness and remaining "
                    "budget. Read-only.")
    parser.add_argument("--json", action="store_true",
                        help="The whole report as JSON, for a caller that "
                             "wants the numbers rather than the sentence.")
    parser.add_argument("--lock-path", default=None,
                        help="Which lock to read. Defaults to suitelock.path() "
                             "- the MAIN checkout's work/suite.lock, which is "
                             "the one path identical from every worktree.")
    return parser


#: FREE and STALE both mean "a suite may start now". UNKNOWN does not, and is
#: deliberately its own code: a lock that cannot be read is a refusal, and a
#: caller that treated it as 0 would be doing the thing this whole module
#: exists to prevent.
EXIT_BY_STATE = {"FREE": 0, "STALE": 0, "HELD": 1, "UNKNOWN": 2}


def main():
    args = build_parser().parse_args()
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if root not in sys.path:
        sys.path.insert(0, root)
    from src import suitelock

    report = suitelock.status(file_path=args.lock_path)

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True, default=str))
    else:
        rows = [
            ("lock", report["lock_path"]),
            ("state", report["state"]),
            ("holder pid", repr(report["pid"])),
            ("branch", repr(report["branch"])),
            ("worktree", repr(report["worktree"])),
            ("liveness", "%s   (%s)" % (report["liveness"],
                                        report["liveness_evidence"])),
            ("reader self-check", repr(report["reader_self_check"])),
            ("queued at", repr(report["queued_at"])),
            ("held since", repr(report["held_since"])),
            ("held for", "n/a" if report["holder"] is None
                         else ("UNKNOWN" if report["held_minutes"] is None
                               else "%.1f min" % report["held_minutes"])),
            ("its deadline", repr(report["lane_deadline"])),
            ("remaining", report["remaining"]),
            ("runs queued", str(report["queue_depth"])),
            ("acquire would", report["would_acquire"]),
        ]
        width = max(len(name) for name, _ in rows)
        print("suite lock status")
        for name, value in rows:
            print("  %-*s  %s" % (width, name, value))
        print()
        print(report["explain"])

    return EXIT_BY_STATE.get(report["state"], 2)


if __name__ == "__main__":
    raise SystemExit(main())
