"""Name-set AND finding-set diff of one full-suite log against the frozen
reference's log.

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

WHY A FINDING LEG WAS ADDED, 2026-10-15, TASK-0150. `webapp/0030` measured the
hole in the rule above: a branch added a real person's surname to a tracked
file, `test_no_real_person_or_client_named` FAILED on both sides - 24 entries
at master, 25 on the branch - and the failing-NAME set was identical, so this
tool reported CLEAN. A pre-existing failure masked a new violation of the same
rule. The test fired; the gate read the wrong field. A test whose failure is a
LIST (hits, rows, violations) must have that list diffed, both directions, or
the 25th entry of an already-failing rule is invisible. The finding set lives
inside the closing block's `AssertionError:` text, which a finished run always
prints; a killed run never does, which is why this leg REFUSES rather than
guesses when either side did not finish - and why the name leg, which does
survive a kill, keeps its old verdict with its INCOMPLETE warning rather than
being silenced.
"""
import importlib.util
import os
import re
import sys
from collections import Counter


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


#: A closing block's separator. unittest prints `=` x70 before the head and
#: `-` x70 after it; `run_suite` owns the head pattern (`_SUMMARY`), so this
#: file owns only the part it adds.
_BLOCK_SEP = re.compile(r"^={20,}\s*$")
_TAIL = re.compile(r"^(Ran \d+ tests?|OK\b|FAILED\b)")

#: unittest scaffolding whose digits move with list LENGTH, not content. The
#: entry lines carry no such markers, so normalising them away costs no signal:
#: the entries themselves are the diff.
_SCAFFOLD_DIGITS = (
    (re.compile(r"\[\d+ chars\]"), "[N chars]"),
    (re.compile(r"Diff is \d+ characters long"),
     "Diff is N characters long"),
    (re.compile(r"First list contains \d+ additional elements?"),
     "First list contains N additional elements"),
    (re.compile(r"First differing item \d+:"), "First differing item N:"),
    (re.compile(r"First extra element \d+:"), "First extra element N:"),
)

#: An absolute Windows path inside a payload. The prefix names the TREE, which
#: differs between the reference checkout and a worktree; findings themselves
#: are repo-relative (`docs/x.md: name`) and carry no drive letter, so this
#: touches only noise.
_ABS_PREFIX = re.compile(r"[A-Za-z]:\\(?:[^'\"\s:\\]+\\?)*")


def _normalise_line(line):
    line = _ABS_PREFIX.sub(r"<tree>\\", line)
    for pattern, replacement in _SCAFFOLD_DIGITS:
        line = pattern.sub(replacement, line)
    return line


def payloads(text, run_suite, baseline):
    """stripped name -> AssertionError payload, from CLOSING blocks only.

    Keys use `suite_baseline.strip_prefix` so they line up with `names()`.

    The payload is everything from the `AssertionError:` line to the end of
    the block. For a test that fails on a collected list (`assertEqual(hits,
    [], msg)`), unittest prints its list-diff scaffolding AND, after the msg
    separator, the full joined list - so a finished log already carries every
    finding set and nothing has to be re-measured.
    """
    out = {}
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        if _BLOCK_SEP.match(lines[i]) and i + 1 < len(lines):
            head = run_suite._SUMMARY.match(lines[i + 1])
            if head:
                dotted = baseline.strip_prefix(head.group(2))
                body, j, started = [], i + 2, False
                while j < len(lines):
                    if _BLOCK_SEP.match(lines[j]) or _TAIL.match(lines[j]):
                        break
                    if lines[j].startswith("AssertionError:") or started:
                        started = True
                        body.append(lines[j])
                    j += 1
                out[dotted] = "\n".join(body)
                i = j
                continue
        i += 1
    return out


def finding_lines(payload):
    """The payload as a multiset of normalised, nonempty lines."""
    counter = Counter()
    for line in payload.splitlines():
        line = _normalise_line(line).strip()
        if line:
            counter[line] += 1
    return counter


def compare_findings(ref_payloads, branch_payloads, both):
    """Per-test finding diffs for tests failing on both sides.

    `both` is the set of stripped names failing on BOTH sides - the only set
    where a name-set diff has nothing to say, which is the whole reason this
    leg exists. A test failing on one side only is the name leg's business.

    Returns (per_test, unknown): `per_test` maps name to `(new Counter, gone
    Counter)` where either is nonempty; `unknown` lists both-sides failures
    whose payload is missing on one side - a finished run always prints a
    closing block, so a missing one means the log cannot answer, and "a
    parser that returns nothing on both sides is not 'no change'".
    """
    per_test, unknown = {}, []
    for name in sorted(both):
        if name not in ref_payloads or name not in branch_payloads:
            unknown.append(name)
            continue
        ref_lines = finding_lines(ref_payloads[name])
        branch_lines = finding_lines(branch_payloads[name])
        new = branch_lines - ref_lines
        gone = ref_lines - branch_lines
        if new or gone:
            per_test[name] = (new, gone)
    return per_test, unknown


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


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) < 2:
        print(__doc__)
        return 2
    ref_log, branch_log = argv[0], argv[1]
    label = argv[2] if len(argv) > 2 else os.path.basename(branch_log)

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

    # The finding leg's own control: plant one extra finding line inside the
    # reference's own payloaded failing test and require exactly that line back.
    ref_payloads = payloads(ref_text, run_suite, baseline)
    branch_payloads = payloads(branch_text, run_suite, baseline)
    payloaded_ref = [d for d, p in ref_payloads.items() if p.strip()]
    finding_control = "n/a (reference has no failing test with a payload)"
    if payloaded_ref:
        probe = dict(ref_payloads)
        victim = payloaded_ref[0]
        probe[victim] = probe[victim] + "\nplanted finding: control"
        per_test, _ = compare_findings(ref_payloads, probe, ref_names)
        got = [line for new, _ in per_test.values() for line in new]
        ok = (set(per_test) == {victim}
              and sorted(got) == ["planted finding: control"])
        finding_control = f"{'PASS' if ok else 'FAIL'} " \
                          f"({victim}, one planted line -> {len(got)} new)"
        if not ok:
            finding_control += " MUST BE exactly 1: planted finding: control"
    print(f"  control, one planted finding:      {finding_control}")

    if len(self_new) or len(planted) != 1 or not finding_control.startswith(
            ("PASS", "n/a")):
        print("  CONTROLS FAILED - this diff is not trustworthy")
        return 3

    finished = bool(run_suite._RAN.search(branch_text))
    ref_finished = bool(run_suite._RAN.search(ref_text))
    new = sorted(branch_names - ref_names)
    gone = sorted(ref_names - branch_names)

    print()
    print(f"  reference : {len(ref_names)} failing names, "
          f"{'finished' if ref_finished else 'INCOMPLETE'}, "
          f"{len(payloaded_ref)} with a payload")
    print(f"  {label:<10}: {len(branch_names)} failing names, "
          f"{'finished' if finished else 'INCOMPLETE'}, "
          f"{len([d for d, p in branch_payloads.items() if p.strip()])} "
          f"with a payload")
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

    # ---- the finding leg -------------------------------------------------
    verdict, blocks = "CLEAN - no new name", bool(new)
    if not finished or not ref_finished:
        print("  FINDINGS: NOT COMPARED - a run that did not finish never "
              "prints the closing blocks that carry them. Rerun; do not read "
              "this as 'no new finding'.")
    elif not payloaded_ref:
        print("  FINDINGS: the reference's failing tests carry no payloads - "
              "nothing to compare beyond the names above.")
    else:
        both = ref_names & branch_names
        per_test, unknown = compare_findings(ref_payloads, branch_payloads,
                                             both)
        for dotted in unknown:
            short = baseline.strip_prefix(dotted)
            side = "reference" if dotted in ref_payloads else label
            print(f"  FINDINGS UNKNOWN: {short} - closing block missing on "
                  f"the {side} side. A finished run always prints one; this "
                  "blocks the merge rather than guessing.")
        if per_test:
            print("  FINDINGS inside tests failing on both sides "
                  "(blocks the merge):")
            for dotted, (f_new, f_gone) in per_test.items():
                print(f"    {baseline.strip_prefix(dotted)}: "
                      f"+{sum(f_new.values())} -{sum(f_gone.values())}")
                for line in sorted(f_new):
                    print(f"      + {line}")
                for line in sorted(f_gone):
                    print(f"      - {line}")
        else:
            print("  FINDINGS: identical inside every test failing on both "
                  "sides, both directions.")
        if per_test or unknown:
            verdict, blocks = "NEW FINDINGS - do not merge", True
    if blocks and new:
        verdict = "NEW NAMES - do not merge"
    print(f"  VERDICT: {verdict}")
    return 1 if blocks else 0


if __name__ == "__main__":
    raise SystemExit(main())
