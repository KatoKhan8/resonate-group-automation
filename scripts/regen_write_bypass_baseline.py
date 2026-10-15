#!/usr/bin/env python3
"""Regenerate `scripts/known_write_bypasses.json` from the analyzer.

    py -3 -B scripts/regen_write_bypass_baseline.py

WHY THIS EXISTS RATHER THAN A HAND-EDITED FILE. The baseline it writes is what
`tests/test_no_new_write_bypasses_the_door.py` compares against, and a baseline
somebody maintains by hand is the defect this whole line of work is about:
`sink_token_split.py` carried a list of fourteen script names and reported "0
token-free writes" while seven scripts with ungated provider writes sat outside
its own denominator. That is catalogue entry 7, and item 2 of the three shapes
in `resonate-ops/THE-CATALOGUE.md`.

So every entry here is derived by `scripts/write_path_denominator.py`, which
itself derives the set of mutating provider functions by closure over each
provider's own call graph rather than from a list.

RUN THIS ONLY WHEN A BYPASS IS DELIBERATELY ADDED OR REMOVED, and say which in
the commit message. Regenerating to make a red test green is how the baseline
stops meaning anything.
"""
import collections
import importlib.util
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASELINE = os.path.join(ROOT, "scripts", "known_write_bypasses.json")


def analyzer():
    path = os.path.join(ROOT, "scripts", "write_path_denominator.py")
    spec = importlib.util.spec_from_file_location("write_path_denominator", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["write_path_denominator"] = module
    spec.loader.exec_module(module)
    return module


def measure(root=ROOT):
    """{"file::function::call": occurrences} for every BYPASS, plus the totals.

    Keyed by enclosing function rather than by LINE NUMBER on purpose: a line
    moves whenever anything above it changes, and a baseline that churns on
    unrelated edits gets regenerated reflexively until it means nothing.
    """
    module = analyzer()
    writers = module.mutating_functions(root)
    rows = module.call_sites(root, writers)
    counts = collections.Counter(
        "%s::%s::%s" % (rel, where, call)
        for verdict, rel, _line, call, where in rows if verdict == "BYPASS")
    totals = collections.Counter(v for v, *_ in rows)
    return counts, totals, writers


def main():
    counts, totals, writers = measure()
    payload = {
        "_what": "Provider write call sites that do NOT pass "
                 "providerwrites.perform.",
        "_why": "Operator decision D, 2026-10-14. A test pins this set so a NEW "
                "ungated write fails the suite. Compared as a SET keyed by "
                "file::function::call with an occurrence count - never by a "
                "total, because a baseline is a named list and three finished "
                "suites once reported the same count for different sets.",
        "_generated_by": "py -3 -B scripts/regen_write_bypass_baseline.py",
        "_never_hand_edit": "Every entry is derived. A hand-kept denominator is "
                            "catalogue entry 7 and item 2 of the three shapes.",
        "total_bypassing_call_sites": sum(counts.values()),
        "sites": dict(sorted(counts.items())),
    }
    io.open(BASELINE, "w", encoding="utf-8").write(
        json.dumps(payload, indent=2) + "\n")
    print("write paths            : %d" % sum(totals.values()))
    print("pass through the door  : %d" % (totals["gated"]
                                           + totals["the door itself"]))
    print("BYPASS the door        : %d" % totals["BYPASS"])
    print("mutating functions     : %s" %
          ", ".join("%s=%d" % (k, len(v)) for k, v in sorted(writers.items())))
    print("baseline written       : %s" % BASELINE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
