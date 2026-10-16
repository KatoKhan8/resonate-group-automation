#!/usr/bin/env py -3
"""Mutation proof for TASK 0170's two changes - written by qwen TASK 0171.

WHY THIS EXISTS AND WHY IT IS NOT 0170's OWN WORK. 0170's brief, section 3,
asked for tests "born-red, mutation-proven in three states with a hash-verified
revert for each of the two". The orphaned 0170 run wrote 53 tests and they pass,
but it left no evidence of any mutation cycle: the source files' mtimes are all
EARLIER than the test files', and no mutation cycle can run without touching the
source it mutates. So the tests were green and never proven. A test that has
never been seen to fail for the right reason is a test of nothing - which is this
repository's own recurring defect, an evaluator that reported INSUFFICIENT_DATA
forever because nothing wrote the field it read.

WHAT A PASS HERE MEANS, PRECISELY. For each mutation:

  1 the target string occurs EXACTLY ONCE in the file (else the mutation is
    ambiguous and proves nothing about which line was exercised)
  2 the file's md5 is recorded BEFORE
  3 the guard is broken
  4 the module still RUNS - a mutation that stops the module importing proves
    nothing about the guard, it only proves Python noticed
  5 the SPECIFICALLY NAMED test fails. Not "a test failed", and not a count:
    `CLAUDE.md` is explicit that when a guard is broken deliberately you confirm
    the intended test failed, that it failed for the intended reason, and that a
    different guard did not fire first. The expected name must be in the failing
    set.
  6 the file is restored and its md5 must EQUAL the one from step 2. A revert
    that is merely "probably fine" is how mutated source got committed here once.

A SURVIVING MUTANT IS A REPORTED RESULT, NEVER A SILENT ONE. If a guard can be
broken with every test still green, that is a hole in the tests and it is printed
as SURVIVED and exits non-zero.

SAFE: edits only the two source files, always restores them in a `finally`, runs
unittest directly so no suite lock is taken, and takes no network or provider
call.
"""

import hashlib
import os
import subprocess
import sys

# Three levels up: docs/ops/<this file> -> docs/ops -> docs -> the repo root.
# The first version stopped at `docs`, and the baseline check caught it at once:
# unittest could not load the test modules from there and reported the load
# error as a failing name, so the proof refused to run against a red baseline.
# That is the guard working, on its own author.
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LANE = os.path.join(REPO, "src", "lanedeadline.py")
LOCK = os.path.join(REPO, "src", "suitelock.py")

MOD_LANE = "tests.test_a_leg_that_cannot_finish_is_not_started"
MOD_LOCK = "tests.test_the_lock_says_whether_it_is_real"


#: Each entry is one broken guard and the ONE test name that must notice.
MUTATIONS = [
    # ---- feature 1: a leg that cannot finish is not started -------------
    dict(feature="LANE_DEADLINE", file=LANE, module=MOD_LANE,
         name="M1 the fit comparison is removed",
         find="    fits = left >= needed\n",
         repl="    fits = True  # MUTANT\n",
         expect="test_no_room_for_one_leg_is_REFUSE",
         why="With the comparison gone every leg 'fits', which is the exact "
             "defect the feature exists to prevent: a 58-minute leg started "
             "into a 20-minute remainder."),
    dict(feature="LANE_DEADLINE", file=LANE, module=MOD_LANE,
         name="M2 UNKNOWN is turned into permission",
         find='        "may_start": False,\n',
         repl='        "may_start": True,  # MUTANT\n',
         expect="test_unknown_never_grants_permission",
         why="The fail-closed rule itself. An unreadable deadline must never "
             "become a licence to start; UNKNOWN is not a measurement."),
    dict(feature="LANE_DEADLINE", file=LANE, module=MOD_LANE,
         name="M3 the write-up reserve is dropped from the arithmetic",
         find="    needed = cost + reserve\n",
         repl="    needed = cost  # MUTANT\n",
         expect="test_the_reserve_is_what_makes_a_tight_fit_a_refusal",
         why="Without the reserve a leg may finish exactly as the watcher kills "
             "the lane, which is the 2026-10-15 failure: the suite completed and "
             "the record was never written."),

    # ---- feature 2: the lock says whether it is real ---------------------
    dict(feature="suitelock.status", file=LOCK, module=MOD_LOCK,
         name="M4 a dead process is reported ALIVE",
         find='        if not text.strip():\n            return "UNKNOWN"\n        return "DEAD"\n',
         repl='        if not text.strip():\n            return "UNKNOWN"\n        return "ALIVE"  # MUTANT\n',
         expect="test_three_states_and_unknown_is_not_dead",
         why="The 659 minutes of dead-holder lock time are only visible because "
             "a dead pid reads DEAD. Report it ALIVE and STALE never appears."),
    dict(feature="suitelock.status", file=LOCK, module=MOD_LOCK,
         name="M5 a malformed lock is reported FREE",
         find='    if report["damaged"]:\n        report["state"] = "UNKNOWN"\n',
         repl='    if report["damaged"]:\n        report["state"] = "FREE"  # MUTANT\n',
         expect="test_bytes_that_are_not_json_are_UNKNOWN",
         why="Invariant 0: an unreadable authority means UNKNOWN, and UNKNOWN "
             "never becomes free, idle or safe. FREE here would start a second "
             "concurrent suite."),
    dict(feature="suitelock.status", file=LOCK, module=MOD_LOCK,
         name="M6 the reader's self-check is inverted",
         find='    if self_seen != "ALIVE":\n',
         repl='    if self_seen == "ALIVE":  # MUTANT\n',
         expect="test_a_live_holder_is_HELD_and_acquire_would_wait",
         why="The guard that stops a blind reader reporting on anyone else. "
             "Inverted, a working reader discards its own good answer."),
]

_PREFIXES = ("FAIL: ", "ERROR: ")


#: Built from `chr()` rather than written as escapes, deliberately. The first
#: attempt to add this function wrote the escapes through a shell heredoc and
#: they arrived as REAL newlines, which made the file a syntax error - the
#: pattern-vs-bytes confusion this function exists to fix, committed by the fix
#: itself. `chr()` has no escape layer to lose.
LF = chr(10)
CRLF = chr(13) + chr(10)


def _match_eol(text, fragment):
    """Rewrite an LF fragment to the line ending the FILE actually uses.

    MEASURED, AND IT COST THREE MUTATIONS. The first run reported "0
    occurrence(s)" for all three `suitelock.py` targets and skipped them. The
    patterns here are written with LF; this tree is CRLF - the standing rules
    record the five lane worktrees at CRLF and the main checkout at LF - so no
    multi-line pattern could ever match. A lane that normalised the FILE to make
    its pattern fit would be rewriting the thing under test, so the PATTERN is
    translated instead.
    """
    if CRLF in text and CRLF not in fragment:
        return fragment.replace(LF, CRLF)
    return fragment


def _purge_pyc(module_file):
    """Delete the cached bytecode for a file whose source just changed.

    THE BUG THIS EXISTS FOR, MEASURED 2026-10-16. The first run reverted every
    mutation with a MATCHING md5 and `git status` agreed the tree was clean -
    and the very next test run still failed 6 times, reporting
    `minutes_needed == 91.0` with the reserve missing, which is M3's mutant
    exactly. Python validates a `.pyc` against the source's mtime and SIZE, and
    M3's replacement `    needed = cost  # MUTANT` is the same 28 bytes as
    `    needed = cost + reserve` and was reverted inside the same second. Same
    size, same second: the cache looked valid and the MUTATED bytecode kept
    being imported out of a byte-perfect tree.

    So a hash-verified revert of the SOURCE is not a restored MODULE. This
    repository has committed mutated source once; this is the same failure one
    layer down, where `git status` cannot see it.
    """
    base = os.path.basename(module_file)[:-3]
    cache = os.path.join(os.path.dirname(module_file), "__pycache__")
    if not os.path.isdir(cache):
        return []
    gone = []
    for entry in os.listdir(cache):
        if entry.startswith(base + "."):
            try:
                os.remove(os.path.join(cache, entry))
                gone.append(entry)
            except OSError:
                pass
    return gone


def md5(path):
    with open(path, "rb") as fh:
        return hashlib.md5(fh.read()).hexdigest()


def failing_names(blob):
    out = set()
    for ln in blob.splitlines():
        ln = ln.strip()
        for pre in _PREFIXES:
            if ln.startswith(pre):
                out.add(ln[len(pre):].split(" ")[0].split(".")[-1])
    return out


def run_module(module):
    env = dict(os.environ)
    env.pop("LANE_DEADLINE", None)
    proc = subprocess.run([sys.executable, "-m", "unittest", module],
                          cwd=REPO, capture_output=True, text=True, env=env)
    blob = (proc.stderr or "") + "\n" + (proc.stdout or "")
    ran = any(l.startswith("Ran ") for l in blob.splitlines())
    return ran, failing_names(blob), blob


def main():
    print("MUTATION PROOF FOR TASK 0170 -- repo %s" % REPO)
    code, _ = subprocess.getstatusoutput("git -C %s rev-parse HEAD" % REPO)
    sha = subprocess.run(["git", "-C", REPO, "rev-parse", "HEAD"],
                         capture_output=True, text=True).stdout.strip()
    print("measured at SHA %s" % sha)

    print("\n=== STEP 0: the baseline must be GREEN, or nothing below means anything ===")
    base = {}
    for mod in (MOD_LANE, MOD_LOCK):
        ran, failing, _ = run_module(mod)
        base[mod] = failing
        print("  %-55s ran=%s failing=%d" % (mod, ran, len(failing)))
        if not ran or failing:
            print("  BASELINE NOT GREEN. Stopping: a mutation proof against a "
                  "red baseline cannot attribute a failure to the mutation.")
            return 1

    results = []
    for mut in MUTATIONS:
        path = mut["file"]
        print("\n=== %s  [%s] ===" % (mut["name"], mut["feature"]))
        print("    why: %s" % mut["why"])
        original = open(path, "rb").read()
        before = hashlib.md5(original).hexdigest()
        text = original.decode("utf-8")

        find = _match_eol(text, mut["find"])
        repl = _match_eol(text, mut["repl"])
        hits = text.count(find)
        if hits != 1:
            print("    TARGET NOT UNIQUE: %d occurrence(s). Mutation skipped - "
                  "an ambiguous target proves nothing." % hits)
            results.append((mut, "AMBIGUOUS"))
            continue

        try:
            with open(path, "wb") as fh:
                fh.write(text.replace(find, repl).encode("utf-8"))
            _purge_pyc(path)   # so the MUTANT is what runs, not a cached original
            ran, failing, blob = run_module(mut["module"])
            new = failing - base[mut["module"]]
            if not ran:
                verdict = "NOT_OBSERVED (module stopped running)"
            elif mut["expect"] in new:
                verdict = "KILLED"
            elif new:
                verdict = ("WRONG_GUARD (expected %s, got %s)"
                           % (mut["expect"], ", ".join(sorted(new)[:3])))
            else:
                verdict = "SURVIVED"
            print("    module ran      %s" % ran)
            print("    new failures    %d: %s"
                  % (len(new), ", ".join(sorted(new)[:6]) or "none"))
            print("    expected name   %s" % mut["expect"])
            print("    VERDICT         %s" % verdict)
        finally:
            # The revert is unconditional - that is what `finally` is for - but
            # the VERDICT on it is raised afterwards, because a `return` inside
            # a `finally` swallows any exception in flight and Python warns
            # about exactly that.
            with open(path, "wb") as fh:
                fh.write(original)
            purged = _purge_pyc(path)
            after = md5(path)
            reverted = after == before
            print("    md5 before      %s" % before)
            print("    md5 after revert %s  %s"
                  % (after, "MATCHES" if reverted else "!!! DOES NOT MATCH !!!"))
            print("    bytecode purged %s" % (", ".join(purged) or "nothing cached"))
        if not reverted:
            print("    THE REVERT DID NOT RESTORE THE FILE. Stop and fix by "
                  "hand before committing anything.")
            return 1
        results.append((mut, verdict))

    print("\n=== SUMMARY ===")
    bad = 0
    for mut, verdict in results:
        flag = "ok " if verdict == "KILLED" else "BAD"
        if verdict != "KILLED":
            bad += 1
        print("  %s %-48s %-22s %s"
              % (flag, mut["name"], mut["feature"], verdict))
    print("\n%d of %d mutations KILLED by the named test."
          % (len(results) - bad, len(results)))

    print("\n=== FINAL: the tree must be back to GREEN ===")
    for mod in (MOD_LANE, MOD_LOCK):
        ran, failing, _ = run_module(mod)
        print("  %-55s ran=%s failing=%d" % (mod, ran, len(failing)))
        if not ran or failing:
            print("  THE TREE DID NOT COME BACK GREEN.")
            return 1
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
