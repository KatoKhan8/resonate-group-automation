#!/usr/bin/env python3
"""Measure the suite baseline AS A LIST OF NAMES, and diff two of them.

WHY THIS EXISTS. A baseline that is a COUNT cannot answer the only question
worth asking of it. `74 failures` and `74 failures` compare equal while a
different 74 tests fail, and that is not a hypothetical here: the 2026-09-23
host comparison found 17 host-only failures and 0 local-only ones behind two
counts that differed by exactly 17. A count says something changed. Only a
set of names says WHAT.

TWO RUNS, NOT ONE, and they answer different questions:

  full        one process, `python -m tests.offline`, everything discovered
              together. This is what a person runs, and what CI runs.

  standalone  each test module in its OWN process. A test that passes here
              and fails in `full` depends on something another module left
              behind; one that fails here and passes in `full` depends on
              something another module SET UP for it, which is worse because
              it will pass forever until somebody runs it alone.

The difference between the two is the order-dependence report. Equal sets
mean no failure depends on run order, and that claim is only as good as the
fact that both runs happened at the SAME commit.

USAGE

    py -3 scripts/suite_baseline.py --measure --out FILE.json
    py -3 scripts/suite_baseline.py --measure --full-log EXISTING.log \\
                                    --out FILE.json
    py -3 scripts/suite_baseline.py --diff OLD.json NEW.json

`--full-log` reuses a full run already on disk rather than running it again;
the standalone pass still runs. The commit recorded in the JSON is the
commit of the WORKING TREE at measure time, and the script refuses to write
a baseline from a dirty tree unless `--allow-dirty` is given - a baseline
measured against uncommitted work describes nothing anybody can return to.

NORMALISATION IS LOAD-BEARING. On 2026-09-23 the host's failing names were
passed through the host-value redactor and the local ones were not, so every
test whose NAME contains the app username appeared in BOTH "host-only" and
"local-only". It looked like a real divergence and it was a measurement
artifact. `--redact-map` applies the same substitutions to both sides of a
diff; without it, both sides must already be normalised the same way.
"""
import argparse
import collections
import datetime
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS_DIR = os.path.join(ROOT, "tests")

#: `FAIL: test_x (tests.mod.Class.test_x)` and the ERROR form. The name in
#: parentheses is the dotted path and is what is compared; the leading
#: method name is redundant and is not used. A subtest adds a trailing
#: ` [...]` which is stripped, because two subtests of one test are not two
#: failures for baseline purposes.
_LINE = re.compile(r"^(FAIL|ERROR):\s+\S+\s+\(([^)\s]+)")


def strip_prefix(name):
    """`tests.test_x.C.t` -> `test_x.C.t`.

    The 2026-09-22/23 baselines are written without the `tests.` prefix, so
    it is stripped HERE, once, rather than at each comparison. A diff whose
    two sides spell the same test differently reports every entry as both
    gone and new - the same shape of artifact as the redactor asymmetry the
    module docstring describes.
    """
    return name[6:] if name.startswith("tests.") else name


def parse_failures(text):
    """Every distinct failing test in a unittest log, as {kind, test}.

    Keyed by NAME: a test that errors in one run and fails in the next is
    the same entry, not two, so `kind` is carried for information and the
    name alone decides identity.
    """
    kinds = {}
    for line in text.splitlines():
        m = _LINE.match(line.strip())
        if m:
            kinds.setdefault(strip_prefix(m.group(2).split(" ")[0].strip()),
                             m.group(1))
    return kinds


def names_of(entries):
    """The name set of a baseline's `entries`, old shape or new.

    2026-09-22 and later write `{"kind": ..., "test": ...}`; a bare list of
    strings is also accepted so an older or hand-made file still diffs.
    """
    out = set()
    for e in entries or []:
        out.add(strip_prefix(e["test"] if isinstance(e, dict) else str(e)))
    return out


def test_modules():
    """Every test module name, discovered the same way unittest discovers."""
    loader = unittest.TestLoader()
    suite = loader.discover(TESTS_DIR, top_level_dir=ROOT)
    mods = set()

    def walk(s):
        if hasattr(s, "__iter__"):
            for child in s:
                walk(child)
        else:
            mod = type(s).__module__
            if mod and mod.startswith("tests."):
                mods.add(mod)

    walk(suite)
    return sorted(mods)


def _run(argv, log_path):
    """Run a command, redirect BOTH streams to a file, return (exit, text).

    Redirected, never piped: `scripts/run_suite.py` exists because three runs
    reported the exit code of `tail` at the end of a pipeline. No timeout
    wrapper - a watchdog that kills the suite reports a number that is not
    the suite's.
    """
    with io.open(log_path, "w", encoding="utf-8", errors="replace") as fh:
        proc = subprocess.run(argv, cwd=ROOT, stdout=fh,
                              stderr=subprocess.STDOUT)
    with io.open(log_path, encoding="utf-8", errors="replace") as fh:
        return proc.returncode, fh.read()


def _counts(text):
    """`Ran N tests`, and the failure/error tallies unittest prints."""
    ran = re.search(r"^Ran (\d+) tests?", text, re.M)
    fails = re.search(r"failures=(\d+)", text)
    errs = re.search(r"errors=(\d+)", text)
    return (int(ran.group(1)) if ran else None,
            int(fails.group(1)) if fails else 0,
            int(errs.group(1)) if errs else 0)


def _commit():
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                             cwd=ROOT, capture_output=True, text=True)
        return out.stdout.strip() or None
    except OSError:
        return None


def _dirty():
    out = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                         capture_output=True, text=True)
    return [l for l in out.stdout.splitlines() if l.strip()]


def measure(out_path, full_log=None, work_dir=None, allow_dirty=False):
    dirty = _dirty()
    if dirty and not allow_dirty:
        sys.stderr.write(
            "REFUSING: the working tree has %d uncommitted change(s). A "
            "baseline measured against uncommitted work describes a tree "
            "nobody can return to. Commit, or pass --allow-dirty.\n%s\n"
            % (len(dirty), "\n".join(dirty[:20])))
        return 2

    # NOT under `work/`. This branch may not write there, and a measurement
    # tool that scribbles into production state to measure it is its own
    # kind of defect. Default is a temp directory; `--work-dir` overrides.
    if work_dir:
        os.makedirs(work_dir, exist_ok=True)
    else:
        work_dir = tempfile.mkdtemp(prefix="suite-baseline-")
        sys.stderr.write("per-module logs: " + work_dir + "\n")
    commit = _commit()

    # ---- the full run -------------------------------------------------
    if full_log:
        with io.open(full_log, encoding="utf-8", errors="replace") as fh:
            full_text = fh.read()
        full_exit = None
        sys.stderr.write("full: reusing %s\n" % full_log)
    else:
        sys.stderr.write("full: running python -m tests.offline ...\n")
        full_exit, full_text = _run(
            [sys.executable, "-m", "tests.offline"],
            os.path.join(work_dir, "full.log"))

    full_kinds = parse_failures(full_text)
    full_names = set(full_kinds)
    ran, nfail, nerr = _counts(full_text)
    sys.stderr.write("full: %s tests, %d distinct failing names\n"
                     % (ran, len(full_names)))

    # ---- the standalone pass ------------------------------------------
    mods = test_modules()
    sys.stderr.write("standalone: %d modules\n" % len(mods))
    standalone = set()
    per_module = {}
    for i, mod in enumerate(mods, 1):
        _, text = _run([sys.executable, "-m", "unittest", mod],
                       os.path.join(work_dir, "mod-%s.log" % mod))
        names = set(parse_failures(text))
        if names:
            per_module[mod] = sorted(names)
        standalone |= names
        sys.stderr.write("  [%3d/%3d] %-62s %d\n"
                         % (i, len(mods), mod, len(names)))

    only_full = sorted(full_names - standalone)
    only_standalone = sorted(standalone - full_names)

    by_module = collections.Counter(
        n.rsplit(".", 2)[0] if n.count(".") >= 2 else n for n in full_names)

    doc = {
        "taken_at": datetime.date.today().isoformat(),
        "measured_at_commit": commit,
        "branch": subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"],
                                 cwd=ROOT, capture_output=True,
                                 text=True).stdout.strip() or None,
        "runner": "py -3 -m tests.offline",
        "platform": sys.platform,
        "python": sys.version.split()[0],
        "tests_run": ran,
        "failures": nfail,
        "errors": nerr,
        "full_exit": full_exit,
        "distinct_tests": len(full_names),
        "standalone_distinct": len(standalone),
        # A test failing ONLY in the full run needs something another module
        # left behind. One failing ONLY standalone was being propped up.
        "order_dependent": only_full,
        "fails_only_standalone": only_standalone,
        "by_module": dict(sorted(by_module.items())),
        "standalone_by_module": per_module,
        # Same shape as the 2026-09-22/23 baselines so the files diff
        # directly: name without the `tests.` prefix, kind alongside.
        "entries": [{"kind": full_kinds[n], "test": n}
                    for n in sorted(full_names)],
    }
    with io.open(out_path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(doc, fh, indent=2, sort_keys=False)
        fh.write("\n")
    sys.stderr.write(
        "\nwrote %s\n  %d distinct failing (full), %d (standalone)\n"
        "  order-dependent: %d   only-standalone: %d\n"
        % (out_path, len(full_names), len(standalone),
           len(only_full), len(only_standalone)))
    return 0


def _load(path):
    with io.open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _apply_redactions(names, mapping):
    out = set()
    for n in names:
        for src, dst in mapping.items():
            n = n.replace(src, dst)
        out.add(n)
    return out


def diff(old_path, new_path, redact_map=None):
    """Two baselines, by NAME. The counts are printed last, deliberately."""
    old, new = _load(old_path), _load(new_path)
    mapping = {}
    if redact_map:
        mapping = _load(redact_map)
    a = _apply_redactions(names_of(old.get("entries")), mapping)
    b = _apply_redactions(names_of(new.get("entries")), mapping)

    gone, arrived, both = sorted(a - b), sorted(b - a), sorted(a & b)
    print("OLD  %s  %s  %d distinct"
          % (old.get("taken_at"), old.get("measured_at_commit"), len(a)))
    print("NEW  %s  %s  %d distinct"
          % (new.get("taken_at"), new.get("measured_at_commit"), len(b)))
    if mapping:
        print("     both sides normalised through %d redaction(s)"
              % len(mapping))
    print()
    print("STILL FAILING   %d" % len(both))
    print("GONE            %d" % len(gone))
    for n in gone:
        print("    - %s" % n)
    print("NEW             %d" % len(arrived))
    for n in arrived:
        print("    + %s" % n)
    if len(a) == len(b) and (gone or arrived):
        print("\nNOTE: the counts are EQUAL and the sets are NOT. This is "
              "exactly what a count-only baseline cannot see.")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--measure", action="store_true")
    ap.add_argument("--out")
    ap.add_argument("--full-log", help="reuse an existing full-run log")
    ap.add_argument("--work-dir", help="where per-module logs are written")
    ap.add_argument("--allow-dirty", action="store_true")
    ap.add_argument("--diff", nargs=2, metavar=("OLD", "NEW"))
    ap.add_argument("--redact-map",
                    help="JSON {from: to} applied to BOTH sides of a diff")
    args = ap.parse_args()

    if args.diff:
        return diff(args.diff[0], args.diff[1], args.redact_map)
    if args.measure:
        if not args.out:
            ap.error("--measure needs --out")
        return measure(args.out, full_log=args.full_log,
                       work_dir=args.work_dir, allow_dirty=args.allow_dirty)
    ap.error("one of --measure or --diff")


if __name__ == "__main__":
    sys.exit(main())
