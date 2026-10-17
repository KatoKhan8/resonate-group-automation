#!/usr/bin/env python3
"""Run the full test suite and report the real verdict.

This script exists because three earlier runs reported exit 0, and that was
the exit code of `tail` at the end of a pipeline, not of unittest. One
honest run exited 124 - killed at the watchdog.

This script:
1. Runs the suite in a subprocess
2. Captures stdout+stderr to a log file (redirect, NOT pipe)
3. Reports the subprocess exit code directly - no pipe, no filter
4. Prints a structured verdict summary with an explicit STATUS

## A timeout is INCOMPLETE. It is not a pass and it is not zero failures.

MEASURED 2026-10-01 on master 10a38310: `run_suite.py --timeout 20` wrote a
verdict file of four lines - exit_code, wall_seconds, timed_out, log_file -
and NO `failures=` line at all, because the old `_find_failures` read only the
`FAIL: name (dotted.path)` blocks unittest prints in its CLOSING summary. On a
watchdog kill that summary is never reached. Anything reading the verdict for
a failure count found no count, and no count reads as zero.

That is not hypothetical. The base suite on d98c83ce exited 124 at 2700s with
**227 failing tests in the log**, and `grep -cE '^(FAIL|ERROR): '` over that
log returned **0**. The verdict was blind exactly when it mattered.

Two changes follow from that, and `tests/
test_a_timed_out_suite_is_never_reported_as_a_pass.py` holds both:

* every verdict carries `status=` - PASS, FAIL or INCOMPLETE. A killed run is
  INCOMPLETE and can never read PASS, whatever its failure count happens to
  be.
* failures are parsed from the inline verbose `... FAIL` / `... ERROR` lines
  as well as the closing blocks, because the inline lines are the only
  evidence that survives a timeout. The two markers are deduplicated by the
  test's dotted name, so a finished run - which prints both - still counts one
  failing test once.

A partial count is also LABELLED partial (`failures_are_partial=True`). A
baseline comparison that silently diffs 1,129 reached results against a full
14,157-result baseline reports every test never reached as "fixed".

## A verdict names the tree it measured

MEASURED 2026-10-17 on b1f290c84: a verdict written by this script carried
eleven lines and not one of them said which tree those numbers came from.
`scripts/suite_verdict.txt` is written into the repository and outlives the
checkout that wrote it, so a file left by an earlier run sits in front of the
next reader as a finished run of whatever is checked out now - the same silent
substitution this module exists to prevent, committed by this module.

So every verdict now carries `tree_sha=`, `written_at=` and `mode=` ahead of
its status, and `read_verdict` is the reader that compares the sha a file
records against the tree in front of it. A different sha is STALE-MISMATCH; a
file with no sha field at all - every verdict written before this change - is
UNIDENTIFIED; and neither is ever MATCH. A reader that cannot tell which tree
it is holding has no verdict, and says so instead of guessing.

## The watchdog is 3600 seconds

Approved figure. The run that produced the 227-failure baseline was killed at
2700s with the suite nearly finished, so the old 1800s default guaranteed the
blind timeout case on every single run.

Usage:
    python scripts/run_suite.py [--timeout SECONDS] [--offline]

--offline:  run through tests.offline (blocks non-loopback sockets)
--timeout:  watchdog in seconds (default 3600)
"""
import argparse
import os
import re
import subprocess
import sys
import time


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PYTHON = sys.executable
LOG_FILE = os.path.join(PROJECT_ROOT, "scripts", "suite_run.log")
VERDICT_FILE = os.path.join(PROJECT_ROOT, "scripts", "suite_verdict.txt")

#: The one name for "git could not say which tree this is". A verdict that
#: cannot name its tree says so in this word rather than leaving the field
#: empty: an empty field is what a reader skips, and a field a reader skips is
#: how a stale verdict came to be read as a live one.
UNKNOWN = "UNKNOWN"

#: What `read_verdict` can say about a verdict file on disk. MATCH is the only
#: state that licenses reading one as a statement about the tree you are
#: standing in; every other state says this file is evidence about a different
#: tree, or about none.
MATCH = "MATCH"
STALE_MISMATCH = "STALE-MISMATCH"
UNIDENTIFIED = "UNIDENTIFIED"
MISSING = "MISSING"

#: Approved 2026-10-01. See the module docstring: 2700s killed a suite that
#: was nearly done, and a killed suite is the case this file exists to report
#: honestly rather than the case it should be provoking.
DEFAULT_TIMEOUT = 3600

#: The closing-summary form: `FAIL: test_x (tests.mod.Class.test_x)`. Printed
#: only once the run has finished, which is why it cannot be the only thing
#: read.
_SUMMARY = re.compile(r"^(FAIL|ERROR):\s+\S+\s+\(([^)\s]+)")

#: The inline verbose form. unittest prints `name (dotted.path)` and then the
#: verdict - but when the test has a docstring, the docstring goes between
#: them and the verdict lands on a LATER line. So the name and the verdict are
#: tracked separately rather than matched in one pattern.
_INLINE_NAME = re.compile(r"^(\S+)\s+\(([^)\s]+)\)")
_INLINE_VERDICT = re.compile(
    r"\.\.\.\s+(ok|FAIL|ERROR|skipped|expected failure|unexpected success)\b")

#: A run that printed this finished. Its absence means the process died -
#: watchdog, crash, or a segfault in a C extension - and the log describes
#: only the part that ran.
_RAN = re.compile(r"^Ran \d+ tests?", re.M)


def run_suite(timeout, offline):
    if offline:
        cmd = [PYTHON, "-m", "tests.offline", "-v"]
    else:
        cmd = [PYTHON, "-m", "unittest", "discover", "-s", "tests", "-v"]

    print(f"Running: {' '.join(cmd)}")
    print(f"Timeout: {timeout}s")
    print(f"Log file: {LOG_FILE}")
    print(f"CWD: {PROJECT_ROOT}")
    print()

    # The tree this run MEASURES, read before the suite starts. A suite runs
    # for 2100-2720s and the tree can move under it, so the identity recorded
    # is the one the tests were loaded from, not whatever is checked out by
    # the time the verdict is finally written.
    tree_sha = _tree_sha(PROJECT_ROOT)
    mode = "offline" if offline else "unittest"

    start = time.monotonic()
    timed_out = False

    with open(LOG_FILE, "w") as log:
        try:
            proc = subprocess.run(
                cmd,
                stdout=log,
                stderr=log,
                timeout=timeout,
                cwd=PROJECT_ROOT,
            )
            elapsed = time.monotonic() - start
            exit_code = proc.returncode
        except subprocess.TimeoutExpired:
            elapsed = time.monotonic() - start
            exit_code = 124
            timed_out = True
            log.write(f"\n\nTIMEOUT after {timeout}s\n")

    verdict_text = build_verdict(LOG_FILE, exit_code, elapsed, timed_out,
                                 tree_sha=tree_sha, mode=mode)
    with open(VERDICT_FILE, "w") as f:
        f.write(verdict_text)

    print("=" * 60)
    print("VERDICT")
    print("=" * 60)
    print(verdict_text)
    print(f"Full log: {LOG_FILE}")
    print(f"Verdict file: {VERDICT_FILE}")

    return exit_code


def classify(log_text, exit_code, timed_out, failures):
    """PASS, FAIL or INCOMPLETE - and INCOMPLETE wins over both.

    A run that did not finish has no verdict to give about the tests it never
    reached, so it gets the one label that says so. Note the order: a killed
    run with zero observed failures is still INCOMPLETE, never PASS.
    """
    if timed_out or not _RAN.search(log_text):
        return "INCOMPLETE"
    if exit_code == 0 and not failures:
        return "PASS"
    return "FAIL"


def build_verdict(log_path, exit_code, wall_seconds, timed_out,
                  tree_sha=None, mode=None, written_at=None):
    """The verdict text, as written to `suite_verdict.txt`.

    Separated from `run_suite` so it can be tested against a log on disk
    without running a suite to produce one.

    The identity fields come FIRST, ahead of the status, because a verdict
    nobody can attribute is not evidence and a reader that stops after the
    first line must still see which tree the numbers below belong to.

    `tree_sha` and `mode` are whatever the caller measured - `run_suite` reads
    both from the tree before the suite starts. Neither is ever left empty and
    neither is guessed: a caller that did not say which runner it used gets
    `unknown`, and a tree git cannot name gets `UNKNOWN`. Both are values
    `read_verdict` refuses to match.
    """
    with open(log_path, "r", errors="replace") as fh:
        log_text = fh.read()

    if tree_sha is None:
        tree_sha = _tree_sha()
    sha = (tree_sha or "").strip() or UNKNOWN
    runner = (mode or "").strip() or "unknown"

    failures = _parse_failures(log_text)
    status = classify(log_text, exit_code, timed_out, failures)
    partial = status == "INCOMPLETE"

    lines = [
        f"tree_sha={sha}",
        f"written_at={written_at or _utc_now()}",
        f"mode={runner}",
        f"status={status}",
        f"exit_code={exit_code}",
        f"wall_seconds={round(wall_seconds, 1)}",
        f"timed_out={timed_out}",
        f"log_file={log_path}",
        f"results_reached={_count_results(log_text)}",
        f"failures={len(failures)}",
        f"failures_are_partial={partial}",
    ]

    result_line = _find_result_line(log_text.splitlines()[-30:])
    if result_line:
        lines.append(f"result_line={result_line}")

    if partial:
        lines.append(
            "# INCOMPLETE: this run did not finish. The failure count above "
            "covers ONLY the tests it reached and is NOT comparable to a "
            "full baseline - every test never reached would read as fixed. "
            "Do not revert a merge on this; a timeout is not a regression.")

    for name in failures:
        lines.append(f"  {name}")

    return "\n".join(lines) + "\n"


def _tree_sha(root=None):
    """The commit this tree is standing on, or UNKNOWN.

    Bounded and never fatal, the same shape as `_current_branch`: a tree with
    no git answer gets the word that says so rather than an empty field, and
    never a guess. Read from the tree, never cached - a cached identity is a
    stale identity, which is the defect this whole change answers.
    """
    try:
        out = subprocess.run(
            ["git", "-C", root or PROJECT_ROOT, "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=60, check=False)
    except Exception:                                          # noqa: BLE001
        return UNKNOWN
    sha = (out.stdout or "").strip()
    return sha if re.fullmatch(r"[0-9a-fA-F]{7,64}", sha) else UNKNOWN


def _utc_now():
    """The verdict's own clock. UTC to the second, never local time."""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def read_verdict(verdict_path, tree_sha=None):
    """What a `suite_verdict.txt` on disk is evidence ABOUT.

    The file is written into `scripts/`, so it outlives the checkout that wrote
    it: a verdict from an earlier run then sits in front of a reader as though
    it described the tree that is checked out now, and "the suite is green"
    gets said about a tree nobody ran.

    So the question this answers is not what the file SAYS but which tree it is
    about. The comparison is between the sha the file records and the sha of
    the tree being asked about, and the non-MATCH answers are kept apart on
    purpose because they mean different things:

      MATCH            the file names this tree
      STALE-MISMATCH   the file names a DIFFERENT tree
      UNIDENTIFIED     the file carries no `tree_sha` line at all - the shape
                       every verdict written before this change has, which
                       identifies no tree and so cannot be read as one
      UNKNOWN          one side could not be read: the file says
                       `tree_sha=UNKNOWN`, or this tree has no sha to give
      MISSING          there is no verdict file

    Never raises on a damaged file: an unreadable verdict is UNKNOWN, which is
    not MATCH, and a reader that cannot tell what it is holding has to say so
    rather than guess. The parsed fields come back too, so a caller can still
    see the status the file claims - without being licensed to act on it.
    """
    asked = ((tree_sha if tree_sha is not None else _tree_sha())
             or "").strip()
    result = {"state": MISSING, "recorded_sha": None,
              "asked_sha": asked or None, "fields": {}}
    if not verdict_path or not os.path.exists(verdict_path):
        return result

    try:
        with open(verdict_path, "r", errors="replace") as fh:
            text = fh.read()
    except OSError:
        result["state"] = UNKNOWN
        return result

    fields = {}
    for line in text.splitlines():
        if "=" not in line or line[:1].isspace():
            continue
        key, _, value = line.partition("=")
        fields.setdefault(key.strip(), value.strip())
    result["fields"] = fields

    recorded = fields.get("tree_sha")
    result["recorded_sha"] = recorded or None
    if not recorded or recorded == UNKNOWN:
        result["state"] = UNIDENTIFIED if "tree_sha" not in fields else UNKNOWN
    elif not asked or asked == UNKNOWN:
        result["state"] = UNKNOWN
    elif recorded == asked:
        result["state"] = MATCH
    else:
        result["state"] = STALE_MISMATCH
    return result


def check_verdict(path=None, tree_sha=None):
    """The instrument: say what the verdict file on disk is evidence about.

    ONE instrument prints both answers, so a clean MATCH cannot come from a
    reader that is structurally unable to report the other one. MATCH exits 0;
    every other state exits 3, because a verdict that does not name THIS tree
    is not a verdict about this tree, and a stale one read as a live one is the
    whole reason this function exists.
    """
    target = path or VERDICT_FILE
    result = read_verdict(target, tree_sha=tree_sha)
    print(f"verdict_file={target}")
    print(f"state={result['state']}")
    print(f"recorded_sha={result['recorded_sha']}")
    print(f"asked_sha={result['asked_sha']}")
    return 0 if result["state"] == MATCH else 3


def _count_results(log_text):
    """How many tests actually reported a verdict, timeout or not."""
    n = 0
    pending = None
    for line in log_text.splitlines():
        head = _INLINE_NAME.match(line)
        if head:
            pending = head.group(2)
        if pending and _INLINE_VERDICT.search(line):
            n += 1
            pending = None
    return n


def _find_result_line(tail_lines):
    for line in reversed(tail_lines):
        stripped = line.strip()
        if (stripped.startswith("Ran ") or stripped.startswith("OK")
                or stripped.startswith("FAILED")):
            return stripped
    return ""


def _parse_failures(log_text):
    """Every distinct failing test in a log, as `KIND: dotted.path`, sorted.

    Reads BOTH markers and deduplicates by the dotted name. The closing blocks
    are authoritative about kind when present; the inline lines are what is
    left when the run was killed before it could print them.
    """
    kinds = {}

    # Pass 1: the closing summary, when there is one.
    for line in log_text.splitlines():
        m = _SUMMARY.match(line.strip())
        if m:
            kinds.setdefault(m.group(2).split(" ")[0].strip(), m.group(1))

    # Pass 2: the inline verbose lines. `setdefault` keeps pass 1's kind for
    # any test both passes saw, so a finished run counts each failure once.
    pending = None
    for line in log_text.splitlines():
        head = _INLINE_NAME.match(line)
        if head:
            pending = head.group(2)
        verdict = _INLINE_VERDICT.search(line)
        if verdict and pending:
            if verdict.group(1) in ("FAIL", "ERROR"):
                kinds.setdefault(pending, verdict.group(1))
            pending = None

    return [f"{kinds[name]}: {name}" for name in sorted(kinds)]


def _find_failures(log_path):
    """`_parse_failures` against a log on disk. Kept for existing callers."""
    with open(log_path, "r", errors="replace") as fh:
        return _parse_failures(fh.read())


def build_parser():
    parser = argparse.ArgumentParser(description="Run the full test suite")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT,
                        help=f"Watchdog in seconds (default {DEFAULT_TIMEOUT})")
    parser.add_argument("--offline", action="store_true",
                        help="Run through tests.offline harness")
    parser.add_argument("--lock-wait", type=float, default=None,
                        help="Seconds to wait for the machine-wide suite lock "
                             "before refusing. Defaults to "
                             "suitelock.DEFAULT_TIMEOUT, which is READ rather "
                             "than copied: this flag carried its own 4200.0 and "
                             "the two figures were then free to drift, which is "
                             "how the master reference came to be launched with "
                             "a timeout shorter than the queue ahead of it.")
    parser.add_argument("--no-lock", action="store_true",
                        help="Skip the machine-wide suite lock. ONLY for a run "
                             "that is not a full suite - a single module, say. "
                             "Two full suites at once make both untrustworthy: "
                             "this harness binds loopback and builds demo "
                             "estates, so a collision looks like a failure.")
    parser.add_argument("--check-verdict", action="store_true",
                        help="Read scripts/suite_verdict.txt, print which tree "
                             "it is evidence about, and exit. Runs no suite and "
                             "takes no lock. Exit 0 only on MATCH: a verdict "
                             "about some other tree is not a verdict about this "
                             "one, and says so with exit 3.")
    return parser


def _current_branch():
    """This tree's branch, for the lock's message. Never fatal."""
    try:
        out = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"],
                             capture_output=True, text=True, timeout=20,
                             check=False)
        return (out.stdout or "").strip() or None
    except Exception:                                          # noqa: BLE001
        return None


def main():
    """ONE full suite at a time on this machine, held by a lock.

    OPERATOR RULE, 2026-10-02. Six `tests.offline` workers ran concurrently from
    four separate launches that day. The suite takes 2100-2720s alone, so six in
    parallel made every one of them look stalled and cost 3h42 of waiting on a
    merge verdict that was only contending - and the results were not
    trustworthy either way, because this suite binds loopback and builds demo
    estates, so a port collision is indistinguishable from a real failure.

    A second run WAITS. It does not start in parallel and it does not steal the
    lock from a live holder. `--no-lock` exists for the one honest case - a
    single-module run that is not a full suite - and says so in its help.
    """
    args = build_parser().parse_args()
    if getattr(args, "check_verdict", False):
        return check_verdict()
    if getattr(args, "no_lock", False):
        return run_suite(args.timeout, args.offline)
    # Run as a script, so the repo root is not on sys.path. Measured: without
    # this the import raised ModuleNotFoundError, the lock was never taken, and
    # the serialisation this function documents did not happen - a guard that
    # exists and never runs. The convention matches scripts/glm_verify_branch.py.
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if root not in sys.path:
        sys.path.insert(0, root)
    from src import suitelock
    wait = (args.lock_wait if args.lock_wait is not None
            else suitelock.DEFAULT_TIMEOUT)
    suitelock.acquire(branch=_current_branch(), timeout=wait)
    try:
        return run_suite(args.timeout, args.offline)
    finally:
        suitelock.release()


if __name__ == "__main__":
    raise SystemExit(main())
