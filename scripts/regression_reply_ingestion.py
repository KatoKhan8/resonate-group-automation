#!/usr/bin/env python3
"""The reply-ingestion regression gate, as a command rather than as prose.

    py -3 scripts/regression_reply_ingestion.py                 # names only
    py -3 scripts/regression_reply_ingestion.py --baseline master
    py -3 scripts/regression_reply_ingestion.py --baseline <sha> --verbose

WHY THIS EXISTS. The reply-ingestion branch changed `src/inbound.py`,
`src/poller.py`, `src/adapters.py`, `src/replies.py`, `src/store.py`,
`src/replywatch.py` and `scripts/learning_walk_replies.py`, and reported "378
tests, no new failing names" in a commit message. A reviewer cannot re-run a
sentence. This runs the modules that actually cover that surface and compares
the failing-name SET against the same modules on another commit, so the next
reader gets the verdict rather than the claim.

IT IS NOT A FULL SUITE AND DOES NOT PRETEND TO BE. It takes no suite lock
(`src/suitelock.py` is for `scripts/run_suite.py`) and does not replace the
merge gate, which is a full run against a reference on the current master.
This is the targeted evidence for THIS change, runnable in about two minutes
instead of eighty.

A NAMED SET, NEVER A COUNT. Three full suites have each reported exactly 231
failing names here and one of them was a different 231. So this prints names
and exits non-zero only on a name that is failing HERE and passing at the
baseline.

A MODULE MISSING AT THE BASELINE IS REPORTED, NOT IGNORED. A new test file
has no baseline result, so every failure of it is new by construction, and
saying so is the difference between a gate and a rubber stamp.
"""
import argparse
import io
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

#: The modules that can observe this change, and what each one is here for.
#: Chosen by what imports or exercises the changed files, not by what sounded
#: related: `src/store.py`'s override set, the ingest path end to end, the
#: adapter's event shape, the classifier, and the watcher's status.
MODULES = (
    # store.STATE_OVERRIDES, reply_store_path, and the write barrier.
    "tests.test_invariants",
    "tests.test_store",
    # replies.classify and the verdict shape the store persists.
    "tests.test_replies",
    "tests.test_a_stored_verdict_names_the_rules_that_made_it",
    # inbound.ingest / inbound.handle, end to end, on every reply class.
    "tests.test_events",
    "tests.test_a_reply_and_its_stop_are_saved_together",
    "tests.test_a_reply_names_the_estate_it_came_from",
    "tests.test_a_reply_mark_is_bound_to_its_workspace",
    "tests.test_our_identifiers_survive_an_inbound_reply",
    "tests.test_a_reply_counts_even_when_the_counter_says_zero",
    "tests.test_a_provider_flag_is_not_a_positive_reply",
    "tests.test_a_stop_survives_a_concurrent_run",
    "tests.test_lifecycle_attacks",
    "tests.test_ooo",
    "tests.test_oooreturn",
    "tests.test_not_now",
    "tests.test_referral",
    # poller.run, its checkpoint, and replywatch's status.
    "tests.test_poller_highwater",
    "tests.test_reply_high_water",
    "tests.test_replywatch",
    "tests.test_scheduler_health",
    # The change's own tests.
    "tests.test_the_reply_store_is_not_inert",
)

#: `FAIL: test_x (tests.test_y.Class.test_x)` and the ERROR form. The dotted
#: identifier is captured rather than the bare method name, because two
#: modules can hold the same method name and a bare name would merge them.
RESULT = re.compile(r"^(?:FAIL|ERROR): \S+ \(([^)]+)\)", re.M)

TAIL = re.compile(r"^(?:Ran \d+ tests?.*|OK.*|FAILED.*)$", re.M)


def _run(cwd, modules, verbose=False):
    """`unittest` over `modules` in `cwd`. Returns (names, summary, output).

    `encoding="utf-8", errors="replace"` and NOT `text=True`: the default
    decodes with the console codepage - cp1250 on this machine - and one
    non-ASCII byte in a traceback then returns None for the whole capture,
    which reads exactly like a clean run.
    """
    present, absent = [], []
    for module in modules:
        relative = os.path.join(*module.split(".")) + ".py"
        (present if os.path.exists(os.path.join(cwd, relative))
         else absent).append(module)

    if not present:
        return set(), "no modules present", "", absent

    argv = [sys.executable, "-m", "unittest"] + list(present)
    if verbose:
        argv.append("-v")
    done = subprocess.run(argv, cwd=cwd, capture_output=True,
                          encoding="utf-8", errors="replace")
    output = (done.stdout or "") + (done.stderr or "")
    names = set(RESULT.findall(output))
    summary = " | ".join(TAIL.findall(output)) or "no summary line"

    # A run that produced neither a summary nor a failure name read nothing.
    # Saying "clean" about that is the failure this repository keeps finding.
    if "no summary line" in summary and not names:
        raise SystemExit(
            "the run in %s produced no unittest summary at all - refusing to "
            "read that as a clean result.\n%s" % (cwd, output[-4000:]))
    return names, summary, output, absent


def _export(ref, into):
    """A pristine tree at `ref`. `git archive`, so no worktree is created."""
    done = subprocess.run(["git", "archive", ref], cwd=ROOT,
                          capture_output=True)
    if done.returncode != 0:
        raise SystemExit("git archive %s failed: %s"
                         % (ref, (done.stderr or b"").decode("utf-8", "replace")))
    with tarfile.open(fileobj=io.BytesIO(done.stdout)) as tar:
        tar.extractall(into)
    return into


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--baseline", help="a git ref to compare against, "
                                           "normally `master`. Omit to just "
                                           "list what fails here")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--keep", action="store_true",
                        help="keep the baseline export for inspection")
    args = parser.parse_args(argv)

    print("HERE: %s" % ROOT)
    here, summary, output, absent = _run(ROOT, MODULES, args.verbose)
    print("  %s" % summary)
    if absent:
        print("  NOT PRESENT HERE: %s" % ", ".join(sorted(absent)))
    print("  %d failing name(s)" % len(here))
    for name in sorted(here):
        print("    %s" % name)

    if not args.baseline:
        print("\nNo --baseline given, so this is a listing and not a verdict. "
              "A failing name here may be pre-existing; pass --baseline master "
              "to find out which.")
        return 0

    temporary = tempfile.mkdtemp(prefix="reply-ingestion-baseline-")
    try:
        print("\nBASELINE %s -> %s" % (args.baseline, temporary))
        _export(args.baseline, temporary)
        there, summary, _out, missing = _run(temporary, MODULES, args.verbose)
        print("  %s" % summary)
        print("  %d failing name(s)" % len(there))
        if missing:
            print("  NOT PRESENT AT BASELINE (every failure of these is new "
                  "by construction): %s" % ", ".join(sorted(missing)))
    finally:
        if not args.keep:
            shutil.rmtree(temporary, ignore_errors=True)

    new = sorted(here - there)
    fixed = sorted(there - here)
    shared = sorted(here & there)

    print("\nPRE-EXISTING (failing on both): %d" % len(shared))
    for name in shared:
        print("    %s" % name)
    if fixed:
        print("\nNO LONGER FAILING: %d" % len(fixed))
        for name in fixed:
            print("    %s" % name)
    print("\nNEW FAILURES: %d" % len(new))
    for name in new:
        print("    %s" % name)

    if new:
        print("\nVERDICT: REGRESSION. The names above fail here and pass at "
              "%s." % args.baseline)
        return 1
    print("\nVERDICT: no new failing names against %s." % args.baseline)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
