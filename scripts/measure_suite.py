#!/usr/bin/env python3
"""Measure per-module wall clock for the full test suite.

Discovers all tests, groups them by module, then runs each module's tests
as a unit while timing. Writes a JSON file with all results and prints
the slowest 30 to stdout.

One process, one import cycle. Per-module timing from grouped execution.

Exit code: the unittest exit code (0 = all green, 1 = failures, etc.)
"""
import json
import os
import sys
import time
import unittest


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS_DIR = os.path.join(PROJECT_ROOT, "tests")
OUTPUT_FILE = os.path.join(PROJECT_ROOT, "scripts", "module_timings.json")
DEFAULT_TOP_N = 30


def discover_grouped_by_module():
    """Discover all tests and group them by module name."""
    loader = unittest.TestLoader()
    suite = loader.discover(TESTS_DIR, top_level_dir=PROJECT_ROOT)

    modules = {}
    _group_by_module(suite, modules)
    return modules


def _group_by_module(suite, modules):
    if hasattr(suite, "__iter__"):
        for child in suite:
            _group_by_module(child, modules)
    else:
        mod = type(suite).__module__
        if mod:
            modules.setdefault(mod, []).append(suite)


def main():
    top_n = DEFAULT_TOP_N
    if "--top" in sys.argv:
        idx = sys.argv.index("--top")
        top_n = int(sys.argv[idx + 1])

    print("Discovering test modules...")
    modules = discover_grouped_by_module()
    module_names = sorted(modules.keys())
    print(f"Found {len(module_names)} modules with tests\n")

    results = []
    total_failures = 0
    total_errors = 0
    total_tests = 0
    total_skipped = 0

    runner = unittest.TextTestRunner(verbosity=0)

    for i, mod_name in enumerate(module_names, 1):
        tests = modules[mod_name]
        module_suite = unittest.TestSuite(tests)

        start = time.monotonic()
        inner = runner.run(module_suite)
        wall = round(time.monotonic() - start, 3)

        n_fail = len(inner.failures)
        n_err = len(inner.errors)
        n_skip = len(inner.skipped)
        fail_names = [str(t[0]) for t in inner.failures]
        err_names = [str(t[0]) for t in inner.errors]

        total_tests += inner.testsRun
        total_failures += n_fail
        total_errors += n_err
        total_skipped += n_skip

        status = "OK" if inner.wasSuccessful() else "FAIL"
        flag = ""
        if n_fail:
            flag += f" F={n_fail}"
        if n_err:
            flag += f" E={n_err}"

        print(f"[{i}/{len(module_names)}] {mod_name}: "
              f"{wall:.1f}s, {inner.testsRun} tests [{status}{flag}]",
              flush=True)

        results.append({
            "module": mod_name,
            "wall_seconds": wall,
            "tests_run": inner.testsRun,
            "failures": n_fail,
            "errors": n_err,
            "skipped": n_skip,
            "failure_names": fail_names,
            "error_names": err_names,
        })

    results.sort(key=lambda r: r["wall_seconds"], reverse=True)

    with open(OUTPUT_FILE, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nTimings written to {OUTPUT_FILE}")

    print(f"\n--- Slowest {min(top_n, len(results))} modules ---")
    for entry in results[:top_n]:
        flag = ""
        if entry["failures"] or entry["errors"]:
            flag = f" [F={entry['failures']} E={entry['errors']}]"
        print(f"  {entry['wall_seconds']:7.1f}s  {entry['module']}{flag}")

    overall_wall = sum(r["wall_seconds"] for r in results)
    print(f"\n--- Summary ---")
    print(f"Sum of per-module wall clocks: {overall_wall:.1f}s")
    print(f"Total tests: {total_tests}")
    print(f"Failures: {total_failures}")
    print(f"Errors: {total_errors}")
    print(f"Skipped: {total_skipped}")
    print(f"Modules: {len(results)}")

    failing = [r for r in results if r["failures"] or r["errors"]]
    if failing:
        print(f"\n--- Failing modules ({len(failing)}) ---")
        for r in failing:
            print(f"  {r['module']}: {r['failures']}F {r['errors']}E")
            for name in r["failure_names"]:
                print(f"    FAIL: {name}")
            for name in r["error_names"]:
                print(f"    ERROR: {name}")

    if total_failures == 0 and total_errors == 0:
        print(f"\nVERDICT: PASS (exit code would be 0)")
        return 0
    else:
        print(f"\nVERDICT: FAIL (exit code would be 1)")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
