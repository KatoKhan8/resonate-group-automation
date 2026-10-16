#!/usr/bin/env python3
"""Fingerprint `src.suitefate`'s behaviour, then run its controls.

Run in a FRESH interpreter by `scripts/suitefate_mutations.py`, once per
mutation, so the mutated module is imported clean. It prints one JSON object
on a line beginning `@@@`: the behaviour fingerprint, and the exact test ids
that failed.

WHY THE FINGERPRINT EXISTS. `webapp/0140`'s M12 survived because the mutation
was a NO-OP - it rewrote an expression to something that evaluates
identically - and an empty kill-set then reads exactly like an unwatched
guard. The fingerprint tells those two apart, and it is only consulted for a
mutation that SURVIVED: a mutation some test failed on has changed behaviour
by definition and needs no probe to say so.

AND WHY IT IS AS WIDE AS THE CONTROLS. A narrow probe's "NO-OP" is worthless.
Two hand-picked instances reported six mutations NO-OP that the controls
plainly reach, including one that trusts an mtime a byte-identical copy
contradicts. This exercises every launch shape the controls do - both real
instances, the read and the unrecorded case, the clobbered clock, the late
landing proved by clock rather than arithmetic, a launch in a session gap, a
launch belonging to no lane, an unreadable process table, and a lock naming
no usable pid - and hashes the RENDERED PAGE for each, so a mutation that
changes only what a person sees still counts as a behaviour change.

Test ids come from `unittest`'s own result objects rather than from a parse
of its output: `-v` wraps long names and a wrapped name parses as absent,
which reads as a mutation that killed nothing.
"""

import datetime
import hashlib
import io
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from tests import test_a_suite_whose_launcher_never_learned as T  # noqa: E402
from src.web import api, pages                                    # noqa: E402

MODULE = "tests.test_a_suite_whose_launcher_never_learned"

#: Frozen so two runs of this probe are comparable. A fingerprint taken
#: against `datetime.now()` would differ between the baseline and every
#: mutation for reasons that have nothing to do with the mutation.
NOW = datetime.datetime(2026, 10, 16, 8, 30, 0)


def _case():
    """A bare TestCase carrying `Estate`'s fixture helpers.

    The helpers live on the test module so the probe and the controls build
    the SAME fixtures. A second fixture builder here would be a second
    representation of the estate's shape, and the two would drift.
    """
    case = type("ProbeCase", (unittest.TestCase, T.Estate), {
        "setUp": T.Estate.setUp, "runTest": lambda self: None})("runTest")
    case.setUp()
    return case


def _read(case, out="read it: filed at probe-verdict-x.txt", clobber=False):
    """The `suppression/0110` shape: a result that landed 81s before close."""
    tree = case.lane("suppression", os.path.join("C:\\", "t", "wt-supp"))
    case.session("suppression", "0110-x.md", "2026-10-15 21:51:36",
                 "2026-10-15 23:07:58", out=out)
    copies = ([(os.path.join("c", "copy.txt"),
                datetime.datetime(2026, 10, 16, 8, 5, 52))]
              if clobber else [])
    case.verdict("probe-verdict-x.txt", tree, "3454.5",
                 datetime.datetime(2026, 10, 15, 23, 6, 37),
                 failures=234, copies=copies)
    case.flush()
    return T.Probe(table={11111: (0, "python.exe")})


def _real_0234b(case):
    case.the_0234b_instance()
    case.flush()
    return T.Probe(table={9: (0, "python.exe")})


def _real_0220(case):
    case.the_0220_instance()
    case.flush()
    case.write_lock(pid=11111,
                    worktree=os.path.join("C:\\", "trees", "wt-other"))
    return T.Probe(table={11111: (0, "python.exe")})


def _late_by_the_clock(case):
    """A short run near the end of a long session: only an mtime settles it."""
    tree = case.lane("suppression", os.path.join("C:\\", "t", "wt-supp"))
    case.session("suppression", "0300-x.md", "2026-10-16 07:00:00",
                 "2026-10-16 07:30:00",
                 out="launched the branch suite under pid 90001")
    case.verdict("suite-verdict-pid90001.txt", tree, "600.0",
                 datetime.datetime(2026, 10, 16, 7, 35, 0))
    case.flush()
    return T.Probe(table={11111: (0, "python.exe")})


def _in_a_gap(case):
    """Five seconds after a DONE and before the next START: nobody's."""
    tree = case.lane("glm-c", os.path.join("C:\\", "t", "wt-glmc"))
    case.session("glm-c", "0060-x.md", "2026-10-15 03:24:48",
                 "2026-10-15 03:34:11")
    case.session("glm-c", "0070-x.md", "2026-10-15 03:44:56",
                 "2026-10-15 04:06:54")
    case.verdict("gap.txt", tree, "0.0",
                 datetime.datetime(2026, 10, 15, 3, 34, 16),
                 status="INCOMPLETE", failures=0)
    case.flush()
    return T.Probe(table={11111: (0, "python.exe")})


def _no_lane_at_all(case):
    """`log_file` in a Claude session's scratch tree: 15 of the 20 real ones."""
    case.lane("suppression")
    case.session("suppression", "0010-x.md", "2026-10-16 04:00:00",
                 "2026-10-16 04:10:00")
    case.verdict("ref.txt", os.path.join("C:\\", "Temp", "claude", "x"),
                 "2111.8", datetime.datetime(2026, 10, 3, 0, 41, 3))
    case.flush()
    return T.Probe(table={11111: (0, "python.exe")})


def _table_unreadable(case):
    case.the_0234b_instance()
    case.flush()
    return T.Probe(readable=False)


def _lock_pid_is_a_bool(case):
    case.the_0220_instance()
    case.flush()
    case.write_lock(pid=True)
    return T.Probe(table={11111: (0, "python.exe")})


def _gap_behind_a_stale_start(case):
    """A gap launch with a sixteen-hour-stale unclosed START behind it.

    The only shape in which the gap rule and the newest-first rule differ.
    Without it, replacing the gap's `return None` with `continue` is a true
    no-op and the gap rule cannot be shown to be watched.
    """
    tree = case.lane("pilotcaps")
    case.lines["pilotcaps"].append(
        "[2026-10-15 16:02:10] [pilotcaps] START 0130-certify-the-halt-fix.md")
    case.session("pilotcaps", "0234b-x.md", "2026-10-16 06:01:58",
                 "2026-10-16 06:20:08")
    case.session("pilotcaps", "0234c-x.md", "2026-10-16 06:20:13",
                 "2026-10-16 06:38:46")
    case.verdict("gap-after-0234b.txt", tree, "0.0",
                 datetime.datetime(2026, 10, 16, 6, 20, 10),
                 status="INCOMPLETE", failures=0)
    case.flush()
    return T.Probe(table={11111: (0, "python.exe")})


def _no_pid_anywhere(case):
    """A placeable launch whose pid nobody recorded: UNDETERMINED, not free."""
    tree = case.lane("suppression")
    case.session("suppression", "0110-no-pid.md", "2026-10-15 21:51:36",
                 "2026-10-15 23:07:58",
                 out="read it: filed at nopid-verdict.txt")
    case.verdict("nopid-verdict.txt", tree, "3454.5",
                 datetime.datetime(2026, 10, 15, 23, 6, 37), failures=234)
    case.flush()
    return T.Probe(table={11111: (0, "python.exe")})


SHAPES = [
    ("real_0234b", _real_0234b),
    ("real_0220", _real_0220),
    ("read", _read),
    ("unrecorded",
     lambda case: _read(case, out="Four briefs done, entries appended.")),
    ("clobbered", lambda case: _read(case, clobber=True)),
    ("late_by_clock", _late_by_the_clock),
    ("in_a_gap", _in_a_gap),
    ("no_lane", _no_lane_at_all),
    ("table_unreadable", _table_unreadable),
    ("lock_pid_bool", _lock_pid_is_a_bool),
    ("gap_behind_a_stale_start", _gap_behind_a_stale_start),
    ("no_pid_anywhere", _no_pid_anywhere),
]

#: The row fields the fingerprint carries. Every decision this module makes
#: about a launch, and nothing that moves on its own: no clock, no path, no
#: byte count.
FIELDS = ("lane", "source", "fate", "lock_disposition", "recorded",
          "attributed_by", "result_clock")


def fingerprint():
    """`[[str, ...], ...]` - every shape's decisions, plus a page hash each."""
    out = []
    for name, build in SHAPES:
        case = _case()
        try:
            system = build(case)
            data = case.read(system, now=NOW)
            out += sorted(
                [name] + [str(row[field]) for field in FIELDS]
                for row in data["rows"])
            out.append([name, "TOTALS", str(data["read"]),
                        str(data["unread"]), str(data["unknown"]),
                        str(data["decided"]),
                        str(round(data["unread_seconds"], 1)),
                        str(data["unread_lock_stranded"]),
                        str(data["unread_lock_released"])])
            # THE RENDERED PAGE, as a hash. Without this a mutation that
            # changes only what a person reads - a lane with nothing
            # readable painted like a lane with everything read - would be
            # reported NO-OP, which is exactly the defect the brief named.
            payload = api.lane_suite_fates(
                root=case.home, probe=system, table=system.table(),
                now=NOW, lock_path=case.lock)
            out.append([name, "HTML", hashlib.md5(
                pages.lane_suite_fates(payload).encode("utf-8")).hexdigest()])
        finally:
            case.doCleanups()
    return out


def main():
    try:
        rows = fingerprint()
    except Exception as exc:                      # noqa: BLE001
        # Reported as data rather than raised, so the harness can REFUSE
        # loudly. A probe that cannot run fails exactly like a clean bill of
        # health, and that cost twelve false NO-OPs once.
        rows = [["PROBE RAISED", type(exc).__name__, str(exc)]]
    result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(
        unittest.TestLoader().loadTestsFromName(MODULE))
    print("@@@" + json.dumps({
        "fingerprint": rows,
        "failed": sorted(test.id().split(".", 2)[-1]
                         for test, _why in result.failures + result.errors),
        "total": result.testsRun,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
