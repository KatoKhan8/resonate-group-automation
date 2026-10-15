"""Mutation proof for docs/ops/lane_treekill.ps1.

A green test proves nothing on its own. CLAUDE.md: "when you break a guard
deliberately, confirm that the intended test failed, that it failed for the
intended reason, and that a different guard did not fire first."

For each mutation this script copies the module and its test into a throwaway
directory, applies ONE textual change, runs the test against the mutated copy,
and reports which legs went red. The run is green only when every mutation
turned its NAMED leg red.

    py -3 docs/ops/mutate_lane_treekill.py
    py -3 docs/ops/mutate_lane_treekill.py --only M2
    py -3 docs/ops/mutate_lane_treekill.py --baseline

Exit 0 when every mutation killed its named leg (and the baseline, if asked
for, was fully green). Exit 1 otherwise.

M2 is worth knowing about before you run it: removing the self-chain refusal
makes the test harness aim `taskkill /PID <itself> /T /F` at its own shell, so
the harness dies mid-run and produces no verdict at all. That IS the red - it
is the 2026-10-15 defect reproduced on purpose - and "no verdict" is scored as
a failure for every leg that never reported. Nothing outside the harness's own
process tree is in range: the harness runs as a child of this script, and /T
reaches downward only.
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
MODULE = os.path.join(HERE, "lane_treekill.ps1")
TEST = os.path.join(HERE, "test_lane_watcher_treekill.ps1")

POWERSHELL = os.path.join(
    os.environ.get("SystemRoot", r"C:\Windows"),
    "System32",
    "WindowsPowerShell",
    "v1.0",
    "powershell.exe",
)

ALL_LEGS = ["A", "B", "C1", "C2", "D1", "D2", "E", "F"]

# Each mutation: (id, what it breaks, the exact text to replace, its
# replacement, the legs that MUST go red). "Must go red" is the named leg; the
# report also prints any OTHER leg that went red, because a mutation taking
# down more than its own requirement is information, not a problem.
MUTATIONS = [
    (
        "M1",
        "taskkill loses /T, so it kills the wrapper and not the tree",
        "& taskkill.exe /PID $RootPid /T /F 2>&1",
        "& taskkill.exe /PID $RootPid /F 2>&1",
        ["B"],
    ),
    (
        "M2",
        "the self-chain refusal is removed from Get-LaneDescendants",
        "  if ($self.ContainsKey($RootPid)) { return $null }",
        "  if ($false) { return $null }",
        ["D1"],
    ),
    (
        "M3",
        "the -Accumulated union is removed, so a sampled orphan is never swept",
        "  if ($Accumulated) {",
        "  if ($false -and $Accumulated) {",
        ["C2"],
    ),
    (
        "M4",
        "the identity check is removed from the -Accumulated union, so a "
        "recycled pid is treated as the original process",
        "      if ($table.ContainsKey($rp) -and $table[$rp].Key -eq $k) {",
        "      if ($table.ContainsKey($rp)) {",
        ["E"],
    ),
    (
        "M5",
        "the creation-time validation is removed from the upward walk, so the "
        "chain climbs through a reused parent slot into a stranger's subtree",
        "    if ($parentCreated -gt $childCreated) { break }   # slot reused: not our parent",
        "    # mutated: the reused-slot check is gone",
        ["F"],
    ),
]

VERDICT = re.compile(r"^\[[^\]]+\]\s(PASS|FAIL)\s\s(\S+)$")


def read(path: str) -> str:
    with io.open(path, encoding="utf-8", newline="") as fh:
        return fh.read()


def write(path: str, text: str) -> None:
    with io.open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)


def run_test(work: str) -> tuple[int, str]:
    """Run the harness copy in `work` and return (exit code, output)."""
    proc = subprocess.run(
        [
            POWERSHELL,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            os.path.join(work, "test_lane_watcher_treekill.ps1"),
            "-WorkRoot",
            os.path.join(work, "fixtures"),
        ],
        capture_output=True,
        text=True,
        timeout=900,
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def legs_from(output: str) -> dict[str, str]:
    """Parse the final verdict block. A leg that never reported is NO-VERDICT,
    which is scored as red: a harness that died told us nothing."""
    seen: dict[str, str] = {}
    for line in output.splitlines():
        m = VERDICT.match(line.rstrip())
        if m and m.group(2) in ALL_LEGS:
            seen[m.group(2)] = m.group(1)
    return {leg: seen.get(leg, "NO-VERDICT") for leg in ALL_LEGS}


def stage(work: str, mutation: tuple | None) -> str | None:
    """Copy module+test into `work`, optionally mutating the module.
    Returns an error string, or None on success."""
    shutil.copy2(TEST, os.path.join(work, "test_lane_watcher_treekill.ps1"))
    text = read(MODULE)
    if mutation is not None:
        _mid, _why, old, new, _legs = mutation
        hits = text.count(old)
        if hits != 1:
            return "the mutation target appears %d times, expected exactly 1" % hits
        text = text.replace(old, new)
    write(os.path.join(work, "lane_treekill.ps1"), text)
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="run one mutation by id, e.g. M3")
    ap.add_argument("--baseline", action="store_true",
                    help="also run the unmutated module and require all legs green")
    ap.add_argument("--keep", action="store_true", help="keep the staging directories")
    args = ap.parse_args()

    for path in (MODULE, TEST):
        if not os.path.exists(path):
            print("FATAL: missing %s" % path)
            return 2
    if not os.path.exists(POWERSHELL):
        print("FATAL: Windows PowerShell 5.1 not found at %s" % POWERSHELL)
        return 2

    root = tempfile.mkdtemp(prefix="qwen0090-mut-")
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
            red = [leg for leg, verdict in legs.items() if verdict != "PASS"]
            print("BASELINE  exit=%d  %s" % (code, " ".join("%s=%s" % kv for kv in legs.items())))
            if red or code != 0:
                failures.append("BASELINE is not green: %s" % ", ".join(red) or "exit code")
                print("  the baseline must be green before a mutation means anything")
            print("")

        chosen = [m for m in MUTATIONS if not args.only or m[0] == args.only]
        if args.only and not chosen:
            print("FATAL: no mutation called %s" % args.only)
            return 2

        for mutation in chosen:
            mid, why, _old, _new, must_be_red = mutation
            work = os.path.join(root, mid)
            os.makedirs(work)
            print("%s  %s" % (mid, why))
            err = stage(work, mutation)
            if err:
                print("  STAGING FAILED: %s" % err)
                failures.append("%s could not be applied: %s" % (mid, err))
                print("")
                continue

            code, out = run_test(work)
            legs = legs_from(out)
            print("  exit=%d  %s" % (code, " ".join("%s=%s" % kv for kv in legs.items())))

            still_green = [leg for leg in must_be_red if legs[leg] == "PASS"]
            other_red = [leg for leg, verdict in legs.items()
                         if verdict != "PASS" and leg not in must_be_red]
            if still_green:
                print("  NOT PROVEN: %s stayed green under this mutation" % ",".join(still_green))
                failures.append("%s did not turn %s red" % (mid, ",".join(still_green)))
            else:
                print("  PROVEN: %s went red" % ",".join(must_be_red))
            if other_red:
                print("  also red (expected collateral, not a problem): %s" % ",".join(other_red))
            print("")
    finally:
        if not args.keep:
            shutil.rmtree(root, ignore_errors=True)
        else:
            print("staging kept at %s" % root)

    print("=" * 64)
    if failures:
        for f in failures:
            print("FAIL  %s" % f)
        print("RESULT: FAIL")
        return 1
    print("every mutation turned its named leg red")
    print("RESULT: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
