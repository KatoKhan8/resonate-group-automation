"""Mutation proof for docs/ops/lane_orphan.ps1 and its wiring in lane_watcher.ps1.

A green test proves nothing on its own. CLAUDE.md: "when you break a guard
deliberately, confirm that the intended test failed, that it failed for the
intended reason, and that a different guard did not fire first."

For each mutation this script copies the modules and the harness into a
throwaway directory, applies ONE textual change, runs the harness against the
mutated copy, and reports which legs went red. The run is green only when every
mutation turned its NAMED leg group red.

    py -3 docs/ops/mutate_lane_orphan.py
    py -3 docs/ops/mutate_lane_orphan.py --baseline
    py -3 docs/ops/mutate_lane_orphan.py --only M4
    py -3 docs/ops/mutate_lane_orphan.py --fast      # skip the Part B mutations

A leg group is RED if any check inside it failed OR if it never reported at all.
A harness that died told us nothing, and "nothing" is not a pass.

ONE MUTATION IS DECLARED UNKILLABLE AND IT IS A REPORTABLE RESULT, NOT A PASS.
M3 removes the empty-process-table guard and every leg stays green, because the
very next guard - "this table does not contain my own pid" - catches the same
input. The empty-table check is therefore SUBSUMED: it cannot be the guard that
fires. It is kept anyway, because its message names the actual condition and a
precise refusal is worth more than a byte, and M3b proves that removing BOTH
guards does go red. An unkillable mutation that is explained is information; an
unkillable mutation that is quietly dropped from the list is how a guard with no
red state survives, which is catalogue family 1.
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
ORPHAN = os.path.join(HERE, "lane_orphan.ps1")
WATCHER = os.path.join(HERE, "lane_watcher.ps1")
TEST = os.path.join(HERE, "test_lane_orphan.ps1")
COPY_ALSO = ["lane_treekill.ps1", "lane_refusal.ps1", "fake_lane_task.ps1"]

POWERSHELL = os.path.join(
    os.environ.get("SystemRoot", r"C:\Windows"),
    "System32", "WindowsPowerShell", "v1.0", "powershell.exe",
)

VERDICT = re.compile(r"^\s+(PASS|FAIL)\s+([AB]\d+)\b")

# (id, file, what it breaks, exact text, replacement, named red legs, needs Part B)
MUTATIONS = [
    (
        "M1", "orphan",
        "UNKNOWN is treated as dead, so an undecidable brief gets moved aside",
        '  if ($owner.Verdict -eq "UNKNOWN") {',
        "  if ($false) {",
        ["A2", "A6", "A7", "A9", "A11"], False,
    ),
    (
        "M2", "orphan",
        "the creation-time key is not compared, so a recycled pid reads ALIVE",
        "  if ($now.Key -eq $claim.Key) {",
        "  if ($true) {",
        ["A4"], False,
    ),
    (
        "M3", "orphan",
        "the empty-process-table guard is removed (SUBSUMED - see the docstring)",
        "  if ($null -eq $table -or $table.Count -eq 0) {",
        "  if ($false) {",
        [], False,
    ),
    (
        "M3b", "orphan",
        "the empty-table guard AND the self-pid guard are both removed",
        "  if (-not $table.ContainsKey($PID)) {",
        "  if ($false) {",
        ["A8", "A9"], False,
        # paired with M3's change, applied together below
    ),
    (
        "M4", "orphan",
        "the self-pid sanity check is removed, so an untrustworthy table is believed",
        "  if (-not $table.ContainsKey($PID)) {",
        "  if ($false) {",
        ["A9"], False,
    ),
    (
        "M5", "orphan",
        "the orphan is RE-QUEUED instead of moved aside",
        "  $donePath = Join-Path $Done $doneName",
        "  $donePath = Join-Path (Split-Path -Parent $Done) $brief.Name",
        ["A3"], False,
    ),
    (
        "M6", "orphan",
        "the moved file is not named for a human to review",
        '  $doneName = $stamp + "-ORPHANED-NEEDS-REVIEW-" + $brief.Name',
        '  $doneName = $stamp + "-" + $brief.Name',
        ["A3"], False,
    ),
    (
        "M7", "orphan",
        "the key is taken from Get-Process again - the four-tick bug, restored",
        "        $procKey  = $table[$PID].Key",
        "        $procKey  = Get-LaneProcKey -ProcPid $PID -Created (Get-Process -Id $PID).StartTime",
        ["A13"], False,
    ),
    (
        "M8", "orphan",
        "the sidecar is left behind when its brief is moved aside",
        "  Remove-LaneClaim -RunPath $runPath\n  $res.Action  = \"MOVED\"",
        "  $res.Action  = \"MOVED\"",
        ["A3"], False,
    ),
    (
        "M9", "orphan",
        "the parentheses come off the sidecar lines - the comma-precedence collapse",
        '    ("pid=" + $PID),',
        '    "pid=" + $PID,',
        ["A13"], False,
    ),
    (
        "M10", "orphan",
        "the move is skipped but the action still reports MOVED",
        "    Move-Item -LiteralPath $runPath -Destination $donePath -Force -ErrorAction Stop",
        "    $null = $donePath",
        ["A3"], False,
    ),
    (
        "M11", "watcher",
        "the startup resolver is never called, so the lane stalls as it did before",
        "  $orphan = Resolve-LaneOrphanedRunning -Running $Running -Done $Done -Lane $Lane `\n"
        "                                        -LogFn ${function:Log}",
        "  $orphan = [pscustomobject]@{ Action = \"NONE\"; Verdict = \"\"; Brief = \"\" }",
        ["B1"], True,
    ),
    (
        "M12", "watcher",
        "the claim sidecar is never written, so every brief is the legacy case",
        "  $claimed = Write-LaneClaim -RunPath $runPath -Lane $Lane -WatchLog $WatchLog",
        "  $claimed = [pscustomobject]@{ Ok = $true; Path = \"\"; Why = \"\" }",
        ["B2", "B3"], True,
    ),
]


def read(path: str) -> str:
    with io.open(path, encoding="utf-8", newline="") as fh:
        return fh.read()


def write(path: str, text: str) -> None:
    with io.open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)


def stage(work: str, mutation) -> str | None:
    """Copy everything into `work`, applying one mutation. Returns an error."""
    shutil.copy2(TEST, os.path.join(work, "test_lane_orphan.ps1"))
    for name in COPY_ALSO:
        shutil.copy2(os.path.join(HERE, name), os.path.join(work, name))
    texts = {"orphan": read(ORPHAN), "watcher": read(WATCHER)}
    if mutation is not None:
        mid, target, _why, old, new, _legs, _pb = mutation
        edits = [(target, old, new)]
        if mid == "M3b":
            # M3b is the PAIR: it only means anything with M3 applied too.
            m3 = [m for m in MUTATIONS if m[0] == "M3"][0]
            edits.append((m3[1], m3[3], m3[4]))
        for tgt, o, n in edits:
            hits = texts[tgt].count(o)
            if hits != 1:
                return "in %s the target appears %d times, expected exactly 1" % (tgt, hits)
            texts[tgt] = texts[tgt].replace(o, n)
    write(os.path.join(work, "lane_orphan.ps1"), texts["orphan"])
    write(os.path.join(work, "lane_watcher.ps1"), texts["watcher"])
    return None


def run_test(work: str, part_b: bool) -> tuple[int, str]:
    cmd = [POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
           os.path.join(work, "test_lane_orphan.ps1")]
    if not part_b:
        cmd.append("-SkipPartB")
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=1200)
    except subprocess.TimeoutExpired:
        return 124, "TIMEOUT"
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def legs_from(output: str, part_b: bool) -> dict[str, str]:
    """Collapse per-check results into leg groups. A group is PASS only if it
    reported at least once and never failed."""
    seen: dict[str, str] = {}
    for line in output.splitlines():
        m = VERDICT.match(line.rstrip())
        if not m:
            continue
        verdict, leg = m.group(1), m.group(2)
        if seen.get(leg) == "FAIL":
            continue
        seen[leg] = verdict
    expected = ["A%d" % i for i in range(1, 14)]
    if part_b:
        expected += ["B%d" % i for i in range(1, 7)]
    return {leg: seen.get(leg, "NO-VERDICT") for leg in expected}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only")
    ap.add_argument("--baseline", action="store_true")
    ap.add_argument("--fast", action="store_true", help="skip Part B mutations")
    ap.add_argument("--keep", action="store_true")
    args = ap.parse_args()

    for path in (ORPHAN, WATCHER, TEST):
        if not os.path.exists(path):
            print("FATAL: missing %s" % path)
            return 2
    if not os.path.exists(POWERSHELL):
        print("FATAL: Windows PowerShell 5.1 not found at %s" % POWERSHELL)
        return 2

    root = tempfile.mkdtemp(prefix="qwen0200-mut-")
    failures: list[str] = []
    try:
        if args.baseline:
            work = os.path.join(root, "baseline")
            os.makedirs(work)
            err = stage(work, None)
            if err:
                print("BASELINE staging failed: %s" % err)
                return 2
            code, out = run_test(work, part_b=not args.fast)
            legs = legs_from(out, part_b=not args.fast)
            red = [k for k, v in legs.items() if v != "PASS"]
            print("BASELINE  exit=%d  red=%s" % (code, red or "none"))
            if red or code != 0:
                failures.append("the baseline is not green")
                print("  a mutation means nothing until the baseline is green")
            print("")

        todo = MUTATIONS
        if args.only:
            todo = [m for m in MUTATIONS if m[0] == args.only]
            if not todo:
                print("no such mutation: %s" % args.only)
                return 2
        if args.fast:
            todo = [m for m in todo if not m[6]]

        for mutation in todo:
            mid, target, why, _old, _new, named, part_b = mutation
            work = os.path.join(root, mid)
            os.makedirs(work)
            err = stage(work, mutation)
            if err:
                print("%-5s STAGING FAILED: %s" % (mid, err))
                failures.append("%s could not be staged" % mid)
                continue
            code, out = run_test(work, part_b=part_b)
            legs = legs_from(out, part_b=part_b)
            red = sorted([k for k, v in legs.items() if v != "PASS"])
            missed = [leg for leg in named if legs.get(leg, "NO-VERDICT") == "PASS"]
            extra = [leg for leg in red if leg not in named]

            if not named:
                # Declared unkillable. The REQUIREMENT is that nothing goes red:
                # if something does, the docstring's reasoning is wrong and that
                # is a finding too.
                ok = not red
                print("%-5s %-62s %s" % (mid, why, "UNKILLABLE AS DECLARED" if ok else "RED: " + str(red)))
                if not ok:
                    failures.append("%s was declared unkillable but turned %s red" % (mid, red))
                continue

            ok = not missed
            print("%-5s %-62s %s" % (mid, why, "KILLED by " + ",".join(named) if ok
                                     else "SURVIVED (named legs still green: %s)" % ",".join(missed)))
            if extra:
                print("        also red, which is information and not a problem: %s" % ",".join(extra))
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
