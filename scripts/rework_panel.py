"""Print the re-dispatch panel for the real lane estate, and PROVE it read only.

TWO CONTROLS, because the obvious one is not sufficient on a live estate.

C-W, THE WRITE TRAP, and it is the one that proves the claim. Every mutating
entry point python can reach - `open` in a writing mode, `os.open` with a
writing flag, `os.remove`, `os.rename`, `os.replace`, `os.mkdir`,
`os.makedirs`, `os.rmdir`, `os.truncate`, `os.utime` - is wrapped for the
duration of the measurement and RAISES if its path is under the ops root.
It does not count, it refuses: a control that tallies violations after the
fact has already let the first one through.

C-F, THE BEFORE/AFTER WALK, which `0110` and `0130` used. On this estate it
cannot stand alone, and the first run of this script proved it: seven paths
moved between the two walks and every one of them was the `suppression`
lane's watcher closing `0290` and dispatching `0300` thirty seconds into my
run. So the walk ATTRIBUTES each difference. A change under
`logs/task-<lane>-*.out`, `logs/watcher-<lane>.log` or `queue/<lane>/` is
the dispatcher doing its own bookkeeping and is reported as CONCURRENT; a
change to ANY `LANE-*.md`, or to anything the attribution cannot explain, is
UNEXPLAINED and fails the run.

    py -3 scripts/rework_panel.py --root C:\\Users\\Zvonimir\\Desktop\\resonate-ops
"""
import argparse
import builtins
import datetime
import hashlib
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import lanerework as lr  # noqa: E402
from src import lanes  # noqa: E402

#: `logs\task-suppression-20261016-065400.out` and
#: `logs\watcher-suppression.log` - the dispatcher's own two files per lane.
_OUT = re.compile(r"^logs[\\/]task-[^\\/]+-\d{8}-\d{6}\.out$")
_WATCHER = re.compile(r"^logs[\\/]watcher-[^\\/]+\.(log|pid)$")
_QUEUE = re.compile(r"^queue[\\/]")

WRITE_MODES = set("wxa+")


class Wrote(AssertionError):
    """A write was attempted under the ops root. Raised, never tallied."""


class WriteTrap(object):
    """C-W. Wraps every mutating call python offers and refuses under `root`."""

    NAMES = ("remove", "unlink", "rename", "replace", "mkdir", "makedirs",
             "rmdir", "truncate", "utime", "chmod")

    def __init__(self, root):
        self.root = os.path.abspath(root)
        self.saved = {}
        self.calls = 0

    def _under(self, path):
        try:
            resolved = os.path.abspath(os.fspath(path))
        except TypeError:
            return False
        return (resolved == self.root
                or resolved.startswith(self.root + os.sep))

    def __enter__(self):
        trap = self

        real_open = builtins.open

        def guarded_open(file, mode="r", *args, **kwargs):
            trap.calls += 1
            if set(mode) & WRITE_MODES and trap._under(file):
                raise Wrote("open(%r, %r) under the ops root" % (file, mode))
            return real_open(file, mode, *args, **kwargs)

        self.saved["builtins.open"] = real_open
        builtins.open = guarded_open

        real_os_open = os.open
        writing = (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_APPEND
                   | os.O_TRUNC)

        def guarded_os_open(path, flags, *args, **kwargs):
            trap.calls += 1
            if flags & writing and trap._under(path):
                raise Wrote("os.open(%r, %#o) under the ops root"
                            % (path, flags))
            return real_os_open(path, flags, *args, **kwargs)

        self.saved["os.open"] = real_os_open
        os.open = guarded_os_open

        for name in self.NAMES:
            real = getattr(os, name, None)
            if real is None:
                continue
            self.saved["os." + name] = real
            setattr(os, name, self._guard(name, real))
        return self

    def _guard(self, name, real):
        trap = self

        def guarded(path, *args, **kwargs):
            trap.calls += 1
            if trap._under(path):
                raise Wrote("os.%s(%r) under the ops root" % (name, path))
            return real(path, *args, **kwargs)
        return guarded

    def __exit__(self, *exc):
        builtins.open = self.saved.pop("builtins.open")
        os.open = self.saved.pop("os.open")
        for key, real in self.saved.items():
            setattr(os, key.split(".", 1)[1], real)
        self.saved = {}
        return False


def walk(root):
    """`{relpath: (size, mtime_ns, sha256)}` for every authority this reads."""
    out = {}
    targets = [os.path.join(root, "queue"), os.path.join(root, "logs")]
    for name in sorted(os.listdir(root)):
        if name.startswith("LANE-") and name.endswith(".md"):
            targets.append(os.path.join(root, name))
    for target in targets:
        if os.path.isfile(target):
            out[os.path.relpath(target, root)] = _stat(target)
            continue
        for base, dirs, files in os.walk(target):
            dirs.sort()
            for name in sorted(files):
                path = os.path.join(base, name)
                out[os.path.relpath(path, root)] = _stat(path)
    return out


def _stat(path):
    try:
        info = os.stat(path)
        with open(path, "rb") as handle:
            digest = hashlib.sha256(handle.read()).hexdigest()
        return (info.st_size, info.st_mtime_ns, digest)
    except OSError as error:
        return ("UNREADABLE", str(error), None)


def attribute(key):
    """`CONCURRENT` for the dispatcher's own bookkeeping, else `UNEXPLAINED`.

    A `LANE-*.md` is deliberately NOT in the concurrent set even though a
    sibling lane legitimately appends to its own one while this runs. The
    lane files are the authority this panel reads and the file this task
    must prove it did not edit, so any movement in one is surfaced rather
    than excused - and the run says which lane's file moved, so a reader
    can tell a sibling's append from a defect here.
    """
    if _OUT.match(key) or _WATCHER.match(key) or _QUEUE.match(key):
        return "CONCURRENT"
    return "UNEXPLAINED"


def diff(before, after):
    """Every difference, both directions. A count alone would not name one."""
    out = []
    for key in sorted(set(before) | set(after)):
        if before.get(key) != after.get(key):
            out.append((key, before.get(key), after.get(key),
                        attribute(key)))
    return out


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=lanes.ops_root())
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--rows", action="store_true",
                        help="every START, not only the confirmed ones")
    parser.add_argument("--cwd", default=os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))),
        help="the repository git reads commits from")
    args = parser.parse_args(argv)
    if not args.root:
        print("no root: set %s or pass --root" % lanes.OPS_DIR)
        return 2

    trap = WriteTrap(args.root)
    with trap:
        before = walk(args.root)
        data = lr.rework(root=args.root, cwd=args.cwd)
        commits = lr.git_commits(_all_shas(data, args.root), cwd=args.cwd)
        after = walk(args.root)
    moved = diff(before, after)
    unexplained = [item for item in moved if item[3] == "UNEXPLAINED"]

    print("C-W WRITE TRAP HELD: %d guarded calls, 0 writes attempted under "
          "the ops root. The trap RAISES rather than counts, so this line "
          "existing is the proof." % trap.calls)
    print("C-F WALK: %d files fingerprinted by size, mtime_ns and sha256; "
          "%d moved, %d of them UNEXPLAINED."
          % (len(before), len(moved), len(unexplained)))
    for key, was, now, why in moved:
        print("   [%s] %s" % (why, key))
        if why == "UNEXPLAINED":
            print("        before %r\n        after  %r" % (was, now))
    if unexplained:
        print("READ-ONLY ASSERTION FAILED on %d unexplained path(s)."
              % len(unexplained))
        return 1
    print()

    if args.json:
        print(json.dumps(data, indent=2, default=str))
        return 0

    _print(data, args, commits)
    return 0


def _all_shas(data, root):
    shas = set()
    for lane in data["lanes"]:
        path = os.path.join(root, "LANE-%s.md" % lane["lane"])
        state, text = lr._read_text(path)
        if state != lanes.PRESENT:
            continue
        shas.update(lr._candidate_shas(lr.headings(text)))
    return shas


def _print(data, args, commits):
    print("ESTATE: %s   state=%s   local offset UTC%+g   measured %s"
          % (data["root_name"], data["state"], data["offset_hours"] or 0,
             datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    print()
    head = ("lane", "starts", "re-disp", "UNKNOWN", "first-run", "no-entry",
            "minutes", "unpriced")
    print("%-12s %7s %8s %8s %10s %9s %9s %9s" % head)
    print("-" * 80)
    for lane in data["lanes"]:
        if lane["state"] == lr.UNREADABLE:
            print("%-12s %7s %8s %8s %10s %9s %9s %9s   <- log=%s lane=%s"
                  % (lane["lane"], "UNK", "UNK", "UNK", "UNK", "UNK", "UNK",
                     "UNK", lane["log_state"], lane["lane_file_state"]))
            continue
        tally = lane["tally"]
        print("%-12s %7d %8d %8d %10d %9d %9.1f %9d"
              % (lane["lane"], lane["starts"], tally.get(lr.REWORK, 0),
                 sum(tally.get(name, 0) for name in lr.UNKNOWN_VERDICTS),
                 tally.get(lr.FRESH, 0), tally.get(lr.NO_ENTRY, 0),
                 lane["minutes"], lane["minutes_unknown"]))
    print("-" * 80)
    print("%-12s %7d %8d %8d %10s %9s %9.1f %9d"
          % ("ESTATE", data["starts"], data["rework"], data["unknown"],
             data["not_rework"], "", data["minutes"],
             data["minutes_unknown"]))
    print()
    print("DENOMINATORS: %d starts read across %d of %d lanes; %d lane(s) "
          "UNREADABLE and in no column above."
          % (data["starts"], data["lane_count"] - data["lanes_unknown"],
             data["lane_count"], data["lanes_unknown"]))
    print("  re-dispatched %d/%d = %.1f%% of starts read.  UNKNOWN %d/%d = "
          "%.1f%%.  not re-dispatched %d/%d = %.1f%%."
          % (data["rework"], data["starts"],
             100.0 * data["rework"] / data["starts"] if data["starts"] else 0,
             data["unknown"], data["starts"],
             100.0 * data["unknown"] / data["starts"] if data["starts"] else 0,
             data["not_rework"], data["starts"],
             100.0 * data["not_rework"] / data["starts"]
             if data["starts"] else 0))
    print("MINUTES is a FLOOR: %d confirmed re-dispatch(es) have no DONE "
          "line and contribute zero." % data["minutes_unknown"])
    print()

    print("CONFIRMED RE-DISPATCHES, each with the field that convicted it")
    print("-" * 80)
    by_rung = {}
    for lane in data["lanes"]:
        for row in lane["rows"]:
            if row["verdict"] != lr.REWORK:
                continue
            by_rung[row["field"]] = by_rung.get(row["field"], 0) + 1
            print("%-12s %-52s START %s" % (lane["lane"], row["brief"],
                                            row["at"]))
            print("%-12s   rung=%s" % ("", row["field"]))
            print("%-12s   value=%s  (entry at line %s)"
                  % ("", row["value"] if row["value"] is not None
                     else "NO CLOCK - the entry says so itself", row["entry"]))
            print("%-12s   %s" % ("", (row["detail"] or "")[:110]))
            print("%-12s   cost=%s min   done=%s"
                  % ("", ("%.1f" % row["minutes"]) if row["minutes"]
                     is not None else "UNKNOWN", row["done"] or "NONE"))
            if row["attribution"]:
                print("%-12s   attribution=%s" % ("", row["attribution"]))
            if row["rewritten"]:
                print("%-12s   ** BRIEF REWRITTEN after that entry - id "
                      "equality may not be task equality" % "")
            print()
    print("BY RUNG: " + ", ".join("%s=%d" % item
                                  for item in sorted(by_rung.items())))
    print()

    print("BLIND SPOTS, with sizes")
    print("-" * 80)
    for spot in lr.blind_spots(data):
        size = "UNKNOWN" if spot["size"] is None else str(spot["size"])
        print("  %-44s %s of %s" % (spot["name"], size, spot["denominator"]))
        print("      %s" % spot["note"])
    print()

    names = [lane["lane"] for lane in data["lanes"]]
    branch_lanes = lr.branch_lanes_for(
        [sha for sha, row in commits.items()
         if lr._HEAD_TASK.search(row["subject"])], names, cwd=args.cwd)
    landed = lr.commit_only(data, commits, known=names,
                            branch_lanes=branch_lanes)
    print("THE NO-ENTRY COHORT, PRICED AGAINST GIT - a separate authority, "
          "deliberately NOT in the headline")
    print("-" * 80)
    strong = [item for item in landed
              if item["attribution"] != lr.A_UNCONTRADICTED]
    print("  %d of %d no-entry STARTs have a commit naming their own TASK id "
          "dated BEFORE the dispatch; %d of those are POSITIVELY attributed "
          "to the lane, so the rest are candidates rather than findings."
          % (len(landed), sum(1 for lane in data["lanes"]
                              for row in lane["rows"]
                              if row["verdict"] == lr.NO_ENTRY),
             len(strong)))
    for item in landed:
        print("    %-12s %-46s START %s  [%s]"
              % (item["lane"], item["brief"], item["start"],
                 item["attribution"]))
        print("        %s  %s  %s" % (item["sha"], item["when"],
                                      item["subject"][:70]))
    print()

    both = lr.both_runs_recorded(data)
    print("BOTH RUNS RECORDED: %d confirmed re-dispatch(es) whose lane file "
          "holds an entry on each side of the START" % len(both))
    for item in both:
        print("  %-12s %s" % (item["lane"], item["brief"]))
        for place in item["placements"]:
            print("      line %-6s %-12s %-26s %s"
                  % (place["line"], place["position"], place["field"],
                     str(place["value"])))
    print()

    clash = lr.rung_clashes(data)
    print("RUNG CLASHES: %d entr(ies) where two rungs place the SAME entry "
          "differently" % len(clash))
    for item in clash[:12]:
        print("  %-12s line %-6s %s" % (item["lane"], item["line"],
                                        item["text"][:70]))
        for field, (position, value) in sorted(item["rungs"].items()):
            print("      %-26s %-12s %s" % (field, position, value))
    print()

    if args.rows:
        print("EVERY START")
        print("-" * 80)
        for lane in data["lanes"]:
            for row in lane["rows"]:
                print("%-12s %-52s %-10s %-28s entries=%d"
                      % (lane["lane"], row["brief"], row["verdict"],
                         row["field"], row["entries"]))


if __name__ == "__main__":
    raise SystemExit(main())
