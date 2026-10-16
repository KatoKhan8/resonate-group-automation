#!/usr/bin/env bash
# THE NEGATIVE CONTROL FOR `task_completeness_probe.py` - qwen TASK 0171.
#
# A completeness check that calls everything complete is this estate's sixth
# failure family, and B7 shipped exactly that. The positive control (0160 ->
# COMPLETE) only proves the probe can say yes. This proves it can say no, and it
# is built to be the HARDEST case rather than an easy one:
#
#   the RECORD leg is FABRICATED COMPLETE - a real commit whose subject names
#   the task, a report file, a lane-file heading, a watcher log carrying both
#   START and `DONE ... -> exit0`, and a non-empty task stdout. Every single
#   RECORD check passes.
#
#   the WORK leg is HALF-APPLIED - the module is there and the tests are there,
#   but the change is not finished.
#
# So the only thing that can produce the right answer is running the code. If
# the probe returns COMPLETE here, every RECORD check in it is decoration and
# its verdict on 0170 is worth nothing.
#
# Two variants, because a half-applied change fails in two different ways:
#
#   A  the module does not import
#   B  the module imports, a test fails
#
# Neither is COMPLETE, which is what `--control-must-not-pass` asserts - and
# that assertion, not the exact verdict, is what this control is for.
#
# MEASURED, AND IT CORRECTED ME. I expected A to come out UNKNOWN on the grounds
# that an import failure measures nothing. It comes out INCOMPLETE: unittest
# wraps an unimportable module in `unittest.loader._FailedTest` and reports it as
# `ERROR: tests.test_control_half_applied`, so there IS a `Ran 1 test` line and
# there IS a failing NAME. The probe's "no 'Ran' line -> UNKNOWN" branch is
# therefore NOT the one an import error takes, and the UNKNOWN branch is
# consequently unexercised by this control - a gap, named rather than papered
# over. The stricter verdict is the right answer anyway; the prediction about the
# mechanism was wrong and the outcome was not.
#
# SAFE BY CONSTRUCTION. Everything happens in a fresh local clone under $TMPDIR.
# No network (a local path, not a URL), no push, no remote, no suite lock, and
# the live tree is only ever READ. The clone is removed at the end unless KEEP=1.
set -u

REPO="${REPO:-C:/Users/Zvonimir/qwc}"
SCRATCH="$(mktemp -d "${TMPDIR:-/tmp}/probe-control-0171.XXXXXX")"
PROBE="$REPO/docs/ops/task_completeness_probe.py"
rc=0

cleanup() { if [ "${KEEP:-0}" != "1" ]; then rm -rf "$SCRATCH" 2>/dev/null; fi; }
trap cleanup EXIT

echo "scratch: $SCRATCH"
CLONE="$SCRATCH/clone"
git clone --quiet --no-hardlinks --single-branch \
    --branch "$(git -C "$REPO" rev-parse --abbrev-ref HEAD)" \
    "$REPO" "$CLONE" || { echo "clone failed"; exit 1; }
# A control must not inherit the thing it is testing. The live tree's
# uncommitted 0170 work is NOT in the clone (clone takes commits only), which is
# exactly what makes this a half-applied case rather than a copy of the real one.
git -C "$CLONE" remote remove origin
git -C "$CLONE" checkout --quiet -b control/half-applied-9999

run_variant() {
  local name="$1" expect="$2"
  echo
  echo "############ NEGATIVE CONTROL $name (expect $expect, must not be COMPLETE) ############"
  # --- the fabricated RECORD: every check in that leg is made to pass ---
  mkdir -p "$SCRATCH/ops/logs"
  printf '# LANE - control\n\n## TASK 9999 - the half-applied change - 2026-10-16\n\nLooks finished. Is not.\n' \
      > "$SCRATCH/ops/LANE-control.md"
  printf '[2026-10-16 03:00:00] [control] START 9999-half-applied.md\n[2026-10-16 03:30:00] [control] DONE  9999-half-applied.md -> exit0\n' \
      > "$SCRATCH/ops/logs/watcher-control.log"
  printf 'a task stdout with real-looking content in it\n' \
      > "$SCRATCH/ops/logs/task-control-9999.out"
  printf '# TASK 9999 REPORT\n\nAsserts the work landed. It did not.\n' \
      > "$CLONE/docs/ops/TASK-9999-REPORT.md"
  git -C "$CLONE" add -A >/dev/null
  git -C "$CLONE" -c user.name=control -c user.email=control@example.invalid \
      commit --quiet -m "TASK 9999: the half-applied change that claims to be done"

  py -3 "$PROBE" \
    --repo "$CLONE" \
    --lane-file "$SCRATCH/ops/LANE-control.md" \
    --watch-log "$SCRATCH/ops/logs/watcher-control.log" \
    --token "9999" --brief-name "9999-half-applied.md" \
    --report "docs/ops/TASK-9999-REPORT.md" \
    --out-file "$SCRATCH/ops/logs/task-control-9999.out" \
    --module tests.test_control_half_applied \
    --control-must-not-pass
  local got=$?
  if [ $got -ne 0 ]; then
    echo "!!! CONTROL $name FAILED: the probe was fooled."
    rc=1
  fi
}

# ---------------------------------------------------------------- variant A
# HALF-APPLIED, THE COMMON SHAPE: the test file references a helper the source
# half never got. This is literally what a run killed between two edits leaves
# behind - the test written, the function not. It must not import.
cat > "$CLONE/src/halfapplied.py" <<'PY'
"""Half of a change. The other half was never written."""
RESERVE_MINUTES = 10.0
PY
cat > "$CLONE/tests/test_control_half_applied.py" <<'PY'
import unittest
from src.halfapplied import RESERVE_MINUTES, decide   # `decide` was never written


class TheChangeLanded(unittest.TestCase):
    def test_it_decides(self):
        self.assertEqual(decide(legs=1), "RUN")
PY
run_variant "A (does not import)" "UNKNOWN"

# ---------------------------------------------------------------- variant B
# HALF-APPLIED, THE WORSE SHAPE: it imports, it runs, and it is wrong. Nothing
# about the file system can see this one - only executing it can.
cat > "$CLONE/src/halfapplied.py" <<'PY'
"""Imports cleanly. Returns the wrong answer."""
RESERVE_MINUTES = 10.0


def decide(legs=1):
    return "RUN"          # always, even with no minutes left: the guard is absent
PY
cat > "$CLONE/tests/test_control_half_applied.py" <<'PY'
import unittest
from src.halfapplied import decide


class TheChangeLanded(unittest.TestCase):
    def test_a_leg_that_fits_runs(self):
        self.assertEqual(decide(legs=1), "RUN")

    def test_a_leg_that_cannot_finish_is_refused(self):
        # The whole point of the feature, and the half that is missing.
        self.assertEqual(decide(legs=99), "REFUSE")
PY
run_variant "B (imports, test fails)" "INCOMPLETE"

echo
if [ $rc -eq 0 ]; then
  echo "BOTH NEGATIVE CONTROLS HELD: a fabricated-complete record over"
  echo "half-applied code did NOT read COMPLETE, in either failure shape."
else
  echo "A NEGATIVE CONTROL FAILED. The probe is blind; do not trust its verdicts."
fi
exit $rc
