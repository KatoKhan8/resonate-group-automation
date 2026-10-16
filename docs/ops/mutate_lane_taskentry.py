#!/usr/bin/env python3
"""mutate_lane_taskentry.py - prove test_lane_taskentry.ps1 can fail.

A harness whose assertions have never been seen to fail is not evidence. This
runs the suite three times: once unmutated, then against two mutants that break
the matcher in OPPOSITE directions, and requires each mutant to kill a NAMED,
NON-EMPTY and DIFFERENT set of legs.

    ALL   Find-LaneTaskEntry always answers MATCH
    NONE  Find-LaneTaskEntry always answers NO_MATCH

A mutant that kills nothing is not a pass here, it is a reportable result about
the tests, and this script says so rather than exiting 0 quietly.

THE MODULE IS NEVER MUTATED IN PLACE, AND THAT IS DELIBERATE.

qwen TASK 0176 measured that a same-size revert inside one whole second can
leave a module mutant permanently, because the filesystem timestamp does not
move and `git checkout --` is the most exposed path. Both mutations here are
same-size-ish single-line edits on a file this script would otherwise have to
restore in under a second - exactly that shape. So the original is opened
read-only, the mutant is written to a NEW file under %TEMP%, and the test is
pointed at it with -Module. There is nothing to revert, so there is nothing
that can fail to revert. The original's md5 is asserted identical at the start
and at the close anyway, because an assertion that costs nothing and would have
caught 0176 is worth keeping.
"""
import hashlib
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
MODULE = os.path.join(HERE, "lane_taskentry.ps1")
TEST = os.path.join(HERE, "test_lane_taskentry.ps1")

VERDICT = ('  if ($res.Count -gt 0) { $res.State = "MATCH" } '
           'else { $res.State = "NO_MATCH" }')

MUTANTS = {
    "ALL": '  $res.State = "MATCH"\n'
           '  if ($res.Line -eq 0) { $res.Line = 1; $res.Count = 1; $res.Text = "(mutant: always matches)" }',
    "NONE": '  $res.State = "NO_MATCH"\n'
            '  $res.Line = 0; $res.Count = 0; $res.Text = ""',
}

LEG = re.compile(r"^\s{2}(PASS|FAIL)\s{2}(\S+)")


def md5(path):
    with open(path, "rb") as fh:
        return hashlib.md5(fh.read()).hexdigest()


def run(module):
    """Run the suite against `module`. Returns (passed, failed) name sets."""
    proc = subprocess.run(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
         "-File", TEST, "-Module", module],
        capture_output=True, text=True, timeout=900)
    passed, failed = set(), set()
    for line in (proc.stdout or "").splitlines():
        m = LEG.match(line)
        if not m:
            continue
        (passed if m.group(1) == "PASS" else failed).add(m.group(2))
    return passed, failed, proc.stdout or ""


def main():
    before = md5(MODULE)
    with open(MODULE, encoding="ascii") as fh:
        src = fh.read()
    if src.count(VERDICT) != 1:
        print("REFUSING: the verdict line this script mutates is not uniquely "
              "present in %s. It was probably edited. Re-read the module before "
              "trusting any mutation result." % MODULE)
        return 2

    print("=== baseline ===============================================")
    base_pass, base_fail, out = run(MODULE)
    print("  passed %d   failed %d" % (len(base_pass), len(base_fail)))
    if base_fail:
        print("  REFUSING to score mutants: the unmutated suite is not green.")
        print("  failing: " + ", ".join(sorted(base_fail)))
        print(out)
        return 1
    if not base_pass:
        print("  REFUSING: the baseline parsed ZERO legs. The reader is broken, "
              "and a mutant scored with a broken reader kills nothing for the "
              "wrong reason.")
        print(out)
        return 1

    killed = {}
    for name, replacement in MUTANTS.items():
        path = os.path.join(tempfile.gettempdir(), "lane_taskentry_MUTANT_%s.ps1" % name)
        with open(path, "w", encoding="ascii", newline="\n") as fh:
            fh.write(src.replace(VERDICT, replacement))
        print("")
        print("=== mutant %s ==============================================" % name)
        print("  " + path)
        mp, mf, mout = run(path)
        # A leg that was green and is now red. Legs that disappear entirely are
        # counted too: an aborted run kills nothing by silence otherwise.
        vanished = base_pass - mp - mf
        killed[name] = sorted(mf | vanished)
        print("  killed %d: %s" % (len(killed[name]), ", ".join(killed[name]) or "NOTHING"))
        if vanished:
            print("  (of which never ran: " + ", ".join(sorted(vanished)) + ")")
        os.remove(path)

    print("")
    print("=== verdict ================================================")
    ok = True
    for name in MUTANTS:
        if not killed[name]:
            print("  REPORTABLE: mutant %s killed NOTHING. The suite does not "
                  "constrain that direction of the rule." % name)
            ok = False
    if ok and set(killed["ALL"]) == set(killed["NONE"]):
        print("  REPORTABLE: both mutants killed the SAME set. The two "
              "directions are not separately constrained.")
        ok = False

    after = md5(MODULE)
    print("  module md5 before %s" % before)
    print("  module md5 after  %s  %s" % (after, "IDENTICAL" if before == after else "CHANGED - INVESTIGATE"))
    if before != after:
        ok = False

    if ok:
        print("  BOTH MUTANTS KILLED A NAMED, NON-EMPTY, DIFFERENT SET.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
