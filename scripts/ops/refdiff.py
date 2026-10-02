"""Name-set diff of one full-suite log against the frozen reference's log.

    python refdiff.py <reference.log> <branch.log> [label]

WHY NOT `suite_baseline.parse_failures`. That one matches only the CLOSING
summary form, `FAIL: name (dotted.path)`, which unittest prints when a run
finishes. A run killed at the watchdog never reaches it, and the 227-failure
base suite on `d98c83ce` is the proof: `grep -cE '^(FAIL|ERROR): '` over that
log returned 0. So extraction uses `run_suite._parse_failures`, which reads the
inline verbose verdicts as well and is the only thing that survives a timeout -
and normalisation uses `suite_baseline.strip_prefix`, so both sides spell a test
the same way. A diff whose sides spell names differently reports every entry as
both gone and new.

THE RULE THIS SERVES, operator 2026-10-02: a baseline is a NAMED LIST. Compare
by set of names, never by count - `231 == 231` can hold for a different 231. A
merge is refused on a NEW NAME, never on a count and never on a timeout.
"""
import importlib.util
import os
import sys


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def names(text, run_suite, baseline):
    """The set of failing test names in a log, normalised.

    `run_suite._parse_failures` returns a list of `"KIND: dotted.path"`; the
    name alone decides identity, because a test that ERRORs in one run and
    FAILs in the next is one entry, not two.
    """
    out = set()
    for entry in run_suite._parse_failures(text):
        _, _, dotted = entry.partition(": ")
        dotted = dotted.strip()
        if dotted:
            out.add(baseline.strip_prefix(dotted))
    return out


def read(path):
    with open(path, "r", errors="replace") as handle:
        return handle.read()


def parser_home(ref_log):
    """Where `run_suite.py` and `suite_baseline.py` live, or None.

    MEASURED 2026-10-02, when this tool was moved out of a session scratchpad
    into `resonate-ops` and stopped working: the old code derived the scripts
    directory from the REFERENCE LOG's location, which only held while that log
    lived inside a checkout. A reference log kept as a durable artefact does
    not, and the tool died on `FileNotFoundError` for `run_suite.py` - a
    durability move that silently broke the one reader every merge verdict
    rests on.

    Four candidates, in order, and the first that actually holds both files
    wins:
      1. `REFDIFF_SCRIPTS`, for an operator who knows better than all of this;
      2. this file's own repository, when it lives at `scripts/ops/refdiff.py`;
      3. the main checkout found through git, the one path identical from every
         worktree - the same escape the suite lock and `config/.env` use;
      4. the reference log's own directory, the old behaviour, kept so nothing
         that worked yesterday stops working today.
    """
    candidates = []
    override = os.environ.get("REFDIFF_SCRIPTS")
    if override:
        candidates.append(override)

    mine = os.path.dirname(os.path.abspath(__file__))
    candidates.append(os.path.dirname(mine))                 # scripts/ops -> scripts
    candidates.append(os.path.join(os.path.dirname(os.path.dirname(mine)),
                                   "scripts"))

    try:
        import subprocess
        out = subprocess.run(["git", "rev-parse", "--path-format=absolute",
                              "--git-common-dir"], capture_output=True,
                             text=True, encoding="utf-8", errors="replace",
                             timeout=60)
        value = (out.stdout or "").strip()
        if out.returncode == 0 and value and os.path.isabs(value):
            candidates.append(os.path.join(
                os.path.dirname(os.path.abspath(value)), "scripts"))
    except Exception:                                        # noqa: BLE001
        pass

    here = os.path.dirname(os.path.abspath(ref_log))
    candidates.append(here if os.path.basename(here) == "scripts"
                      else os.path.join(os.path.dirname(here), "scripts"))

    for candidate in candidates:
        if (candidate
                and os.path.isfile(os.path.join(candidate, "run_suite.py"))
                and os.path.isfile(os.path.join(candidate,
                                                "suite_baseline.py"))):
            return candidate
    return None


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    ref_log, branch_log = sys.argv[1], sys.argv[2]
    label = sys.argv[3] if len(sys.argv) > 3 else os.path.basename(branch_log)

    scripts = parser_home(ref_log)
    if not scripts:
        print("REFUSED: cannot find run_suite.py and suite_baseline.py. They "
              "are the only sound extractor - a hand-rolled grep over a full "
              "suite log returns 0 on a killed run and missed all five "
              "fixture-hygiene names once. Pass REFDIFF_SCRIPTS=<path to a "
              "checkout's scripts/> or run this from inside one.")
        return 4
    print(f"  parsers from: {scripts}")
    run_suite = _load(os.path.join(scripts, "run_suite.py"), "rs_ref")
    baseline = _load(os.path.join(scripts, "suite_baseline.py"), "sb_ref")

    ref_text, branch_text = read(ref_log), read(branch_log)
    ref_names = names(ref_text, run_suite, baseline)
    branch_names = names(branch_text, run_suite, baseline)

    # CONTROLS, printed every time, because a reader that cannot see the thing
    # makes its zeros worthless and these two zeros are the whole verdict.
    self_new = names(ref_text, run_suite, baseline) - ref_names
    planted = names(
        ref_text + "\ntest_planted (tests.test_control.C.test_planted)\n"
        "... FAIL\n", run_suite, baseline) - ref_names
    print(f"  control, reference against itself: {len(self_new)} new "
          f"(must be 0)")
    print(f"  control, one planted name:         {len(planted)} new "
          f"(must be 1) {sorted(planted)}")
    if len(self_new) or len(planted) != 1:
        print("  CONTROLS FAILED - this diff is not trustworthy")
        return 3

    finished = bool(run_suite._RAN.search(branch_text))
    ref_finished = bool(run_suite._RAN.search(ref_text))
    new = sorted(branch_names - ref_names)
    gone = sorted(ref_names - branch_names)

    print()
    print(f"  reference : {len(ref_names)} failing names, "
          f"{'finished' if ref_finished else 'INCOMPLETE'}")
    print(f"  {label:<10}: {len(branch_names)} failing names, "
          f"{'finished' if finished else 'INCOMPLETE'}")
    print(f"  NEW   (blocks the merge): {len(new)}")
    for n in new:
        print(f"    + {n}")
    print(f"  GONE  (fixed or unreached): {len(gone)}")
    for n in gone:
        print(f"    - {n}")
    if not finished or not ref_finished:
        print("  WARNING: one side did not finish. Every test it never reached "
              "reads as GONE, and NEW is still trustworthy only for the part "
              "that ran. A timeout is INCOMPLETE, not a pass.")
    print(f"  VERDICT: {'CLEAN - no new name' if not new else 'NEW NAMES - do not merge'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
