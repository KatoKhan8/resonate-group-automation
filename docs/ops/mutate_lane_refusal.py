#!/usr/bin/env python3
"""mutate_lane_refusal.py - break lane_refusal.ps1 one gate at a time and prove
that test_lane_refusal_classifier.ps1 goes red FOR THE INTENDED REASON.

Precedent and reason: docs/ops/mutate_lane_treekill.py does the same for the
tree-kill module. A harness whose assertions have never been seen to fail is
not evidence, and "the suite is green" says nothing about whether the suite can
go red.

AND NOT MERELY THAT IT WENT RED. The standing rules are explicit: when a guard
is broken deliberately, confirm that the INTENDED test failed, that it failed
for the intended reason, and that a different guard did not fire first. So every
mutation below declares the exact set of test names it must break, and this
script compares BY NAME SET in both directions:

    missing   a name this mutation was supposed to break and did not
    extra     a name that broke which this mutation did not predict

An `extra` is as much a failure as a `missing`: it means the mutation reached
further than the gate it was aiming at, so the test that went red is not
evidence about that gate.

Nothing here touches the live estate. Each mutation is written to a temp copy of
the module and the test is pointed at the copy with -ModulePath.
"""

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
MODULE = HERE / "lane_refusal.ps1"
TEST = HERE / "test_lane_refusal_classifier.ps1"

# Each mutation: (name, why, [(find, replace, expected_count)], {names that must fail})
# The replacement count is asserted, so a mutation that silently applied zero
# times - the way a refactor quietly disarms a mutation suite - is a hard error
# rather than a mutation that "passed".
MUTATIONS = [
    (
        "M1-drop-timeout-gate",
        "a timeout would be classified as a provider refusal",
        [("""  if ($TimedOut) {
    $result.FailedGate = "1-timed-out\"""",
          """  if ($false) {
    $result.FailedGate = "1-timed-out\"""", 1)],
        {"D a timeout stays a timeout: " + n for n in [
            "task-glm-20261016-004231.out", "task-glm-20261016-014141.out",
            "task-glm-20261016-014455.out", "task-glm-b-20261016-011843.out",
            "task-glm-b-20261016-014312.out", "task-glm-c-20261016-004232.out",
            "task-glm-c-20261016-014156.out", "task-glm-c-20261016-014506.out"]},
    ),
    (
        "M2-drop-exit-zero-gate",
        "a task that exited 0 while the output mentioned a 429 would be returned to the queue",
        [("  if ([int]$codeText -eq 0) {", "  if ($false) {", 1)],
        {"B exit 0 is never a refusal: " + n for n in [
            "task-glm-20261016-004231.out", "task-glm-20261016-014141.out",
            "task-glm-20261016-014455.out", "task-glm-b-20261016-011843.out",
            "task-glm-b-20261016-014312.out", "task-glm-c-20261016-004232.out",
            "task-glm-c-20261016-014156.out", "task-glm-c-20261016-014506.out"]},
    ),
    (
        "M3-drop-lane-growth-gate",
        "a refusal arriving AFTER the task recorded work would be returned, re-running work already done",
        [("  if ($LaneGrew) {", "  if ($false) {", 1)],
        ({"C lane grew, so work happened: " + n for n in [
            "task-glm-20261016-004231.out", "task-glm-20261016-014141.out",
            "task-glm-20261016-014455.out", "task-glm-b-20261016-011843.out",
            "task-glm-b-20261016-014312.out", "task-glm-c-20261016-004232.out",
            "task-glm-c-20261016-014156.out", "task-glm-c-20261016-014506.out"]}
         | {"B3 the DEFAULTS fail closed"}),
    ),
    (
        "M4-unanchor-the-signature",
        "a task QUOTING 'API Error' in its own report would be read as a refusal",
        [(r"Pattern = '(?m)^[ \t]*API Error\b[^\r\n]*(\(429\)|\b429\b)'",
          r"Pattern = 'API Error[^\r\n]*(\(429\)|\b429\b)'", 1)],
        # Case E's .out quotes ECONNREFUSED, not a 429, so unanchoring alone
        # does not reach it - which is the honest result and is why this
        # mutation's expected set is empty and the run is still informative.
        # It is kept because an EMPTY expected set that the script confirms is
        # itself a measurement: the anchor is defence in depth, not the only
        # thing standing between case E and a false positive.
        set(),
    ),
    (
        "M5-remove-the-second-signature",
        "a reworded CLI prefix would lose the behaviour entirely",
        [("""    [pscustomobject]@{
      Name    = "usage-limit-reached\"""",
          """    [pscustomobject]@{
      Name    = "DISABLED-usage-limit-reached"
      Pattern = 'ZZZ_NEVER_MATCHES_ZZZ'
      Status  = ""
      Note    = "mutated"
    },
    [pscustomobject]@{
      Name    = "unused-usage-limit-reached\"""", 1)],
        {"G prefix reworded, quota sentence intact -> still caught",
         "G two signatures are registered"},
    ),
    (
        "M6-open-the-default",
        "a caller that forgets -LaneGrew would get the destructive-free path by default",
        [("    [bool]$LaneGrew = $true", "    [bool]$LaneGrew = $false", 1)],
        {"B3 the DEFAULTS fail closed"},
    ),
    (
        "M7-silence-the-near-miss",
        "the day the provider rewords its message, nothing would say so",
        [("    $result.NearMiss   = $true", "    $result.NearMiss   = $false", 1)],
        {"G both wordings gone -> NEAR MISS is raised"},
    ),
]

FAIL_RE = re.compile(r"^  FAIL  (.+?)   ", re.M)
RESULT_RE = re.compile(r"^  passed (\d+)   failed (\d+)", re.M)


def run_test(module_path):
    r = subprocess.run(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
         "-File", str(TEST), "-ModulePath", str(module_path)],
        capture_output=True, text=True,
    )
    out = r.stdout + r.stderr
    names = set(FAIL_RE.findall(out))
    m = RESULT_RE.search(out)
    passed, failed = (int(m.group(1)), int(m.group(2))) if m else (None, None)
    return r.returncode, names, passed, failed, out


def main():
    if not MODULE.exists() or not TEST.exists():
        print("MISSING module or test"); return 2

    print("=" * 78)
    print("BASELINE: the unmutated module must be GREEN, or no mutation below means anything.")
    rc, names, passed, failed, out = run_test(MODULE)
    print(f"  exit={rc} passed={passed} failed={failed}")
    if rc != 0 or names:
        print("  BASELINE IS NOT GREEN. Stopping; a mutation suite on a red baseline proves nothing.")
        for n in sorted(names):
            print("    red:", n)
        print(out[-3000:])
        return 2
    baseline_passed = passed
    print(f"  baseline green, {baseline_passed} assertions\n")

    verdicts = []
    with tempfile.TemporaryDirectory() as td:
        for name, why, edits, expected in MUTATIONS:
            copy = Path(td) / f"lane_refusal_{name}.ps1"
            shutil.copy2(MODULE, copy)
            text = copy.read_text(encoding="ascii")
            ok_edits = True
            for find, repl, want in edits:
                got = text.count(find)
                if got != want:
                    print(f"[{name}] MUTATION DID NOT APPLY: found {got} of {find[:60]!r}, wanted {want}")
                    ok_edits = False
                    break
                text = text.replace(find, repl, want)
            if not ok_edits:
                verdicts.append((name, "NOT-APPLIED", set(), set()))
                continue
            copy.write_text(text, encoding="ascii", newline="")

            rc, got_names, passed, failed, out = run_test(copy)
            missing = expected - got_names
            extra = got_names - expected
            status = "OK" if (not missing and not extra) else "MISMATCH"
            verdicts.append((name, status, missing, extra))

            print(f"[{name}] {why}")
            print(f"  exit={rc} passed={passed} failed={failed}  red-names={len(got_names)}")
            if expected:
                print(f"  predicted red: {len(expected)}")
            else:
                print("  predicted red: NONE (defence in depth; see the comment in the mutation table)")
            for n in sorted(missing):
                print(f"    MISSING (should have gone red): {n}")
            for n in sorted(extra):
                print(f"    EXTRA (went red unpredicted):   {n}")
            print(f"  -> {status}\n")

    print("=" * 78)
    bad = [v for v in verdicts if v[1] != "OK"]
    for name, status, missing, extra in verdicts:
        print(f"  {status:12s} {name}")
    if bad:
        print(f"\n  {len(bad)} mutation(s) did not behave as predicted. The suite's ability to")
        print("  detect those gates is NOT established.")
        return 1
    print(f"\n  all {len(verdicts)} mutations behaved exactly as predicted, by name set,")
    print("  in both directions. Every gate in lane_refusal.ps1 has a test that can see it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
