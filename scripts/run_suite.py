#!/usr/bin/env python3
"""Run the full test suite and report the real verdict.

This script exists because three earlier runs reported exit 0, and that was
the exit code of `tail` at the end of a pipeline, not of unittest. One
honest run exited 124 - killed at the watchdog.

This script:
1. Runs `python -m unittest discover` in a subprocess
2. Captures stdout+stderr to a log file (redirect, NOT pipe)
3. Reports the subprocess exit code directly - no pipe, no filter
4. Prints a structured verdict summary

Usage:
    python scripts/run_suite.py [--timeout SECONDS] [--offline]

--offline:  run through tests.offline (blocks non-loopback sockets)
--timeout:  watchdog in seconds (default 1800 = 30 min)
"""
import argparse
import os
import subprocess
import sys
import time


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PYTHON = sys.executable
LOG_FILE = os.path.join(PROJECT_ROOT, "scripts", "suite_run.log")
VERDICT_FILE = os.path.join(PROJECT_ROOT, "scripts", "suite_verdict.txt")


def run_suite(timeout, offline):
    if offline:
        cmd = [PYTHON, "-m", "tests.offline"]
    else:
        cmd = [PYTHON, "-m", "unittest", "discover", "-s", "tests", "-v"]

    print(f"Running: {' '.join(cmd)}")
    print(f"Timeout: {timeout}s")
    print(f"Log file: {LOG_FILE}")
    print(f"CWD: {PROJECT_ROOT}")
    print()

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

    wall = round(elapsed, 1)

    verdict_lines = []
    verdict_lines.append(f"exit_code={exit_code}")
    verdict_lines.append(f"wall_seconds={wall}")
    verdict_lines.append(f"timed_out={timed_out}")
    verdict_lines.append(f"log_file={LOG_FILE}")

    tail = _read_tail(LOG_FILE, 30)
    result_line = _find_result_line(tail)
    if result_line:
        verdict_lines.append(f"result_line={result_line}")

    failure_names = _find_failures(LOG_FILE)
    if failure_names:
        verdict_lines.append(f"failures={len(failure_names)}")
        for name in failure_names:
            verdict_lines.append(f"  {name}")

    verdict_text = "\n".join(verdict_lines) + "\n"
    with open(VERDICT_FILE, "w") as f:
        f.write(verdict_text)

    print("=" * 60)
    print("VERDICT")
    print("=" * 60)
    print(verdict_text)
    print(f"Full log: {LOG_FILE}")
    print(f"Verdict file: {VERDICT_FILE}")

    return exit_code


def _read_tail(path, n):
    with open(path, "r", errors="replace") as f:
        lines = f.readlines()
    return lines[-n:]


def _find_result_line(tail_lines):
    for line in reversed(tail_lines):
        stripped = line.strip()
        if stripped.startswith("Ran ") or stripped.startswith("OK") or stripped.startswith("FAILED"):
            return stripped
    return ""


def _find_failures(log_path):
    failures = []
    with open(log_path, "r", errors="replace") as f:
        content = f.read()

    in_failure_section = False
    for line in content.splitlines():
        if line.startswith("=" * 40):
            in_failure_section = True
            continue
        if line.startswith("-" * 70):
            in_failure_section = False
            continue
        if in_failure_section and line.startswith("FAIL: ") or line.startswith("ERROR: "):
            failures.append(line.strip())
    return failures


def main():
    parser = argparse.ArgumentParser(description="Run the full test suite")
    parser.add_argument("--timeout", type=int, default=1800,
                        help="Watchdog timeout in seconds (default 1800)")
    parser.add_argument("--offline", action="store_true",
                        help="Run through tests.offline harness")
    args = parser.parse_args()

    exit_code = run_suite(args.timeout, args.offline)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
