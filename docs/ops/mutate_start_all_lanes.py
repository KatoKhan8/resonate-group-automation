"""Mutation proof for docs/ops/START-ALL-LANES.ps1.

The fixture is green, and green proves nothing on its own. Each mutation below
copies the launcher, the watcher, the modules and the harness into a throwaway
directory, applies ONE textual change to the launcher, runs the harness against
the mutated copy, and reports which legs went red.

    py -3 docs/ops/mutate_start_all_lanes.py
    py -3 docs/ops/mutate_start_all_lanes.py --baseline
    py -3 docs/ops/mutate_start_all_lanes.py --only N1

N1 is the point of the whole task: it restores the defect this launcher was
rewritten to remove - the totals line counting launch attempts instead of
evidence. If N1 does not turn a leg red, the rewrite bought nothing.

TWO MUTATIONS ARE DECLARED UNKILLABLE AND BOTH ARE REPORTED RESULTS, NOT PASSES.

N2 removes `$null = $proc.Handle`. Nothing goes red, and the reason is measured:
under Windows PowerShell 5.1 the exit code is blank after exit only in the
`-NoNewWindow` shape, which this launcher does not use.

    -NoNewWindow -PassThru, no handle   ->  ExitCode EMPTY
    -NoNewWindow -PassThru, handle      ->  ExitCode 7
    -PassThru (the launcher), no handle ->  ExitCode 2
    -PassThru (the launcher), handle    ->  ExitCode 2

N2 is also a correction of this author's own record. Leg C8 first went red
reading "exited 0" for a stub meant to exit 2, and the missing handle was blamed.
It was not the cause: the stub had collapsed into one line through PowerShell's
comma precedence, so its `exit 2` sat inside a comment. Two things were changed
at once and the wrong one got the credit - exactly the "confirm it failed for the
INTENDED reason" rule, broken, and then caught by this mutation surviving. The
line stays: it costs nothing and it guards the day somebody adds -NoNewWindow.

N3 makes an unreadable log read as empty. Nothing goes red, because the NEXT
guard catches the same input - the log had a pre-existing line, so the empty
string is shorter than the mark and the truncation check refuses it. The UNKNOWN
verdict is doubly protected. N3b removes both guards and leg C4 does go red,
which is what proves the pair.

Each run of the harness takes about 50 seconds, so the whole set is a few
minutes. Exit 0 when every mutation killed its named leg group.
"""

from __future__ import annotations

import argparse
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
LAUNCHER = os.path.join(HERE, "START-ALL-LANES.ps1")
TEST = os.path.join(HERE, "test_start_all_lanes.ps1")
COPY_ALSO = ["lane_watcher.ps1", "lane_treekill.ps1", "lane_refusal.ps1",
             "lane_orphan.ps1", "fake_lane_task.ps1"]

POWERSHELL = os.path.join(
    os.environ.get("SystemRoot", r"C:\Windows"),
    "System32", "WindowsPowerShell", "v1.0", "powershell.exe",
)

VERDICT = re.compile(r"^\s+(PASS|FAIL)\s+(C\d+(?:-C\d+)?)\b")
ALL_LEGS = ["C1", "C1-C3", "C2", "C3", "C4", "C4-C6", "C5", "C6", "C7", "C8", "C9"]

# (id, what it breaks, exact text, replacement, named red legs)
MUTATIONS = [
    (
        "N1",
        "THE ORIGINAL DEFECT: started = the number of launch attempts",
        '$started = @($results | Where-Object { $_.State -eq "STARTED" }).Count',
        "$started = $pending.Count",
        ["C1-C3", "C8", "C9"],
    ),
    (
        "N2",
        "the handle is not captured (UNKILLABLE - see the docstring)",
        "    $null = $proc.Handle",
        "    # handle not captured",
        [],
    ),
    (
        "N3",
        "an unreadable log is read as empty (UNKILLABLE - see the docstring)",
        "  return $null            # UNREADABLE, and the caller must not read it as empty",
        '  return ""',
        [],
    ),
    (
        "N3b",
        "the unreadable guard AND the truncation guard are both removed",
        "  if ($text.Length -lt $Mark) {",
        "  if ($false) {",
        ["C4"],
    ),
    (
        "N4",
        "the exit code is always 0, so a caller cannot tell the estate is down",
        "if ($refused -gt 0 -or $unknown -gt 0) { exit 1 }\nexit 0",
        "exit 0",
        ["C1-C3", "C4-C6"],
    ),
    (
        "N5",
        "a lane that says nothing within the bound is counted as started",
        '    Record $p.Lane "UNKNOWN" ("silent for " + $UpTimeoutSeconds + "s")',
        '    Record $p.Lane "STARTED" ("silent for " + $UpTimeoutSeconds + "s")',
        ["C7"],
    ),
]


def read(path: str) -> str:
    with io.open(path, encoding="utf-8", newline="") as fh:
        return fh.read()


def write(path: str, text: str) -> None:
    with io.open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)


def stage(work: str, mutation) -> str | None:
    shutil.copy2(TEST, os.path.join(work, "test_start_all_lanes.ps1"))
    for name in COPY_ALSO:
        shutil.copy2(os.path.join(HERE, name), os.path.join(work, name))
    text = read(LAUNCHER)
    if mutation is not None:
        mid, _why, old, new, _legs = mutation
        edits = [(old, new)]
        if mid == "N3b":
            # N3b is the PAIR: it only means anything with N3 applied too.
            n3 = [x for x in MUTATIONS if x[0] == "N3"][0]
            edits.append((n3[2], n3[3]))
        for o, n in edits:
            hits = text.count(o)
            if hits != 1:
                return "a target appears %d times, expected exactly 1" % hits
            text = text.replace(o, n)
    write(os.path.join(work, "START-ALL-LANES.ps1"), text)
    return None


def run_test(work: str) -> tuple[int, str]:
    cmd = [POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
           os.path.join(work, "test_start_all_lanes.ps1")]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    except subprocess.TimeoutExpired:
        return 124, "TIMEOUT - the harness did not finish"
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def legs_from(output: str) -> dict[str, str]:
    seen: dict[str, str] = {}
    for line in output.splitlines():
        m = VERDICT.match(line.rstrip())
        if not m:
            continue
        verdict, leg = m.group(1), m.group(2)
        if seen.get(leg) == "FAIL":
            continue
        seen[leg] = verdict
    return {leg: seen.get(leg, "NO-VERDICT") for leg in ALL_LEGS}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only")
    ap.add_argument("--baseline", action="store_true")
    ap.add_argument("--keep", action="store_true")
    args = ap.parse_args()

    for path in (LAUNCHER, TEST):
        if not os.path.exists(path):
            print("FATAL: missing %s" % path)
            return 2
    if not os.path.exists(POWERSHELL):
        print("FATAL: Windows PowerShell 5.1 not found at %s" % POWERSHELL)
        return 2

    root = tempfile.mkdtemp(prefix="qwen0210-mut-")
    failures: list[str] = []
    try:
        if args.baseline:
            work = os.path.join(root, "baseline")
            os.makedirs(work)
            err = stage(work, None)
            if err:
                print("BASELINE staging failed: %s" % err)
                return 2
            code, out = run_test(work)
            legs = legs_from(out)
            red = [k for k, v in legs.items() if v != "PASS"]
            print("BASELINE  exit=%d  red=%s" % (code, red or "none"))
            if red or code != 0:
                failures.append("the baseline is not green")
            print("")

        todo = MUTATIONS
        if args.only:
            todo = [m for m in MUTATIONS if m[0] == args.only]
            if not todo:
                print("no such mutation: %s" % args.only)
                return 2

        for mutation in todo:
            mid, why, _old, _new, named = mutation
            work = os.path.join(root, mid)
            os.makedirs(work)
            err = stage(work, mutation)
            if err:
                print("%-4s STAGING FAILED: %s" % (mid, err))
                failures.append("%s could not be staged" % mid)
                continue
            code, out = run_test(work)
            legs = legs_from(out)
            red = sorted([k for k, v in legs.items() if v != "PASS"])
            missed = [leg for leg in named if legs.get(leg, "NO-VERDICT") == "PASS"]
            extra = [leg for leg in red if leg not in named]
            if not named:
                # Declared unkillable: the requirement is that NOTHING goes red.
                # If something does, the docstring's reasoning is wrong, and that
                # is a finding too.
                ok = not red
                print("%-4s %-60s %s" % (mid, why,
                      "UNKILLABLE AS DECLARED" if ok else "RED: " + str(red)))
                if not ok:
                    failures.append("%s was declared unkillable but turned %s red" % (mid, red))
                continue
            ok = not missed
            print("%-4s %-60s %s" % (mid, why, "KILLED by " + ",".join(named) if ok
                                    else "SURVIVED (still green: %s)" % ",".join(missed)))
            if extra:
                print("       also red, which is information: %s" % ",".join(extra))
            if not ok:
                failures.append("%s survived: %s stayed green" % (mid, ",".join(missed)))
    finally:
        if args.keep:
            print("\nstaging kept at %s" % root)
        else:
            shutil.rmtree(root, ignore_errors=True)

    print("")
    if failures:
        print("FAILED:")
        for f in failures:
            print("  " + f)
        return 1
    print("every mutation killed its named leg group.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
