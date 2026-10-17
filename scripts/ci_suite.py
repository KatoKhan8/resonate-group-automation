#!/usr/bin/env python3
"""The offline-runnable suite, sharded, and gated against a NAMED baseline.

    py -3 scripts/ci_suite.py run-shard --index 0 --of 8 --log shard-0.log
    py -3 scripts/ci_suite.py gate --logs logs/ --baseline .github/suite-baseline.txt
    py -3 scripts/ci_suite.py regen-baseline --logs logs/ --out .github/suite-baseline.txt

Written for `.github/workflows/suite.yml`. Everything here also runs by hand,
which is deliberate: a gate the operator cannot reproduce locally is a gate
nobody can argue with.

## Why this exists rather than `run_suite.py`

`run_suite.py` answers "did the whole suite finish and how many failed" on this
machine, and it holds `work/suite.lock` so one lane runs it and the others wait.
That lock is the throughput ceiling. A CI runner has its own machine, so there
is nothing to serialise and no lock to take; what it needs instead is to run a
SLICE of the suite and to be judged by NAME against a recorded baseline.

`run_suite.py` is not modified. Other lanes' references are measured with its
parser and changing it would move their baselines underneath them.

## The naming trap, and why shards load modules as TOP-LEVEL names

`tests/offline.py` runs `loader.discover("tests")` with no `top_level_dir`, so
`tests/` becomes the top level, its modules import as `test_e2e` rather than
`tests.test_e2e`, and every name in every baseline this repository has measured
is spelled that way. A shard that loaded `tests.test_e2e` would produce names
that differ from the baseline in every single character before the first dot -
a 100% false "new failure" set and a 100% false "gone" set. So `run-shard` puts
`tests/` on `sys.path` and loads bare module names, exactly as discovery does.

## The parser, and the 166 results the repository's own one loses

MEASURED 2026-10-15 against the branch reference at `4d2d19b9b`
(`scripts/suite_run.log`, 14887 tests). `run_suite._parse_failures` and
`_count_results` anchor a verdict on a literal `...` followed by whitespace.
unittest does not always put it there:

    test_x (test_e2e.TestEnrichmentOutcomes.test_x) ... <path>:195:
      ResourceWarning: unclosed file ...
    FAIL

When a test emits a warning, the warning text takes the rest of the name line
and the verdict word is printed ALONE on a later line. The repository's parser
never matches that `FAIL`, so the test reads as never having reported:
`results_reached=14721` against `Ran 14887`, and 242 failing names against the
263 the closing summary supports. Reading the bare form as well brings the
parsed total to exactly 14887.

Three further things that measurement settled, each of which had to be right
before any name set here could be trusted:

* A NAME SET IS NOT AN EVENT COUNT. `subTest` reports one event per sub-case
  under one test name. That is the whole of `failures=171` against 167 failing
  names, and of `skipped=33` against 32 skipped names. Neither is a fault.
* A `setUpClass` that raises produces NO inline line for any test in the class.
  It appears only as `ERROR: setUpClass (mod.Class)` in the closing summary, and
  `Ran N` does not count the tests it killed. Those are read separately and
  counted as failures, because a whole class silently not running is the worst
  outcome this gate can have.
* A verdict regex must be ANCHORED AT END OF LINE. Without that anchor the
  ordinary program output `FAIL  (1 fields checked)`, printed by
  `test_the_estate_comes_back_after_a_reboot`, is read as that test's verdict.

## What the gate decides

A failing name present in the run and absent from the baseline FAILS the gate.
Everything else is reported and does not. In particular a name that STOPPED
failing is reported, never silently accepted, and is looked up positively in
the log: `passed`, `skipped`, `absent` or `unknown`. CLAUDE.md's rule - absence
proves nothing. `absent` means the test did not run, so its disappearance from
the failing set is not a fix and may be a whole class that vanished.
"""
import argparse
import collections
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS = os.path.join(ROOT, "tests")

VERDICTS = ("ok", "FAIL", "ERROR", "skipped", "expected failure",
            "unexpected success")
_WORD = "|".join(re.escape(v) for v in VERDICTS)

#: `<method> (<dotted>)`. The method name must equal the last component of the
#: dotted path; that is what separates a test-name line from interleaved program
#: output that happens to read `word (something)`.
_NAME = re.compile(r"^(\S+)\s+\(([^)\s]+)\)(.*)$")

#: Nothing after a verdict, or - after a skip - the quoted reason. Anchored at
#: end of line; see the module docstring for the line that breaks without it.
_TAIL = r"(\s+(?:'[^']*'|\"[^\"]*\"))?\s*$"
_AFTER_DOTS = re.compile(r"\.\.\.\s*(" + _WORD + r")" + _TAIL)
_BARE = re.compile(r"^(" + _WORD + r")" + _TAIL)

#: The only place a fixture failure appears. No inline line exists for the tests
#: it killed.
_CLASS_LEVEL = re.compile(
    r"^(FAIL|ERROR):\s+(setUpClass|setUpModule|tearDownClass)\s+\(([^)\s]+)\)",
    re.M)

_RAN = re.compile(r"^Ran (\d+) tests?", re.M)

#: Files the suite itself creates under `work/` while running. MEASURED, not
#: assumed: these are what appeared in a clone that started with no `work/` at
#: all. The workflow requires that nothing ELSE shows up, which is a measurement
#: of "never writes to work/" rather than a claim about it.
#:
#: THE FIRST VERSION OF THIS SET HELD FOUR NAMES AND THE MEASUREMENT SHOWED SIX,
#: so `check-work` would have returned 1 on every single run - a permanent red
#: step, on two files the suite writes every time. Both clone runs of
#: 2026-10-15 (X1-plain, X2-offline, logged in
#: `resonate-ops/pilotcaps-ci-2026-10-15/X*-work-created.txt`) produced exactly
#: these six and no others. A SEVENTH name appearing is meant to fail: a new
#: `w-*.out` is a worker capture nobody has looked at, and this list is widened
#: by measuring a run, never to clear a red step.
EPHEMERAL_WORK = frozenset({
    "dispatch-interpreter.json",
    "provider-write-refusals.jsonl",
    "reports",
    "sourcing-page.json",
    # Worker stdout captures, `w-<worker>.out`. Named individually rather than
    # matched by glob, so a worker nobody expected is a failure and not a pass.
    "w-bison_watch_493.out",
    "w-digest.out",
})


# --------------------------------------------------------------------------
# parsing
# --------------------------------------------------------------------------

def _reason(tail):
    """The quoted reason after a skip, unquoted, or ""."""
    tail = (tail or "").strip()
    if len(tail) >= 2 and tail[0] == tail[-1] and tail[0] in "'\"":
        return tail[1:-1]
    return tail


def parse_log(text):
    """{dotted name: {"verdict", "reason"}} for every test that reported."""
    out = {}
    pending = None

    def record(name, verdict, tail):
        if name not in out:
            out[name] = {"verdict": verdict, "reason": _reason(tail)}

    for line in text.splitlines():
        head = _NAME.match(line)
        if head and head.group(1) == head.group(2).split(".")[-1]:
            pending = head.group(2)
            found = _AFTER_DOTS.search(head.group(3))
            if found:
                record(pending, found.group(1), found.group(2))
                pending = None
            continue
        if not pending:
            continue
        found = _AFTER_DOTS.search(line)
        if found:
            record(pending, found.group(1), found.group(2))
            pending = None
            continue
        bare = _BARE.match(line.strip())
        if bare:
            record(pending, bare.group(1), bare.group(2))
            pending = None
    return out


def class_level(text):
    """{dotted class: KIND} for fixtures that failed and took a class down."""
    return {m.group(3): m.group(1) for m in _CLASS_LEVEL.finditer(text)}


def read_logs(paths):
    """Every log merged into one outcome map, plus the per-log ran-counts.

    Shards are disjoint by construction - each module belongs to exactly one -
    so a name appearing twice means two shards ran it and the merge says so
    rather than quietly keeping one.
    """
    outcomes, fixtures, ran, overlaps = {}, {}, {}, []
    for path in paths:
        with open(path, "r", errors="replace", encoding="utf-8") as fh:
            text = fh.read()
        parsed = parse_log(text)
        for name, info in parsed.items():
            if name in outcomes:
                overlaps.append(name)
            outcomes[name] = info
        fixtures.update(class_level(text))
        found = _RAN.search(text)
        ran[os.path.basename(path)] = int(found.group(1)) if found else None
    return outcomes, fixtures, ran, sorted(set(overlaps))


def failing_names(outcomes, fixtures):
    return {n for n, i in outcomes.items()
            if i["verdict"] in ("FAIL", "ERROR")} | set(fixtures)


def outcome_of(outcomes, name):
    """What `name` did, for a positive lookup of a disappeared failure."""
    info = outcomes.get(name)
    if info is None:
        return "absent"
    return {"ok": "passed", "skipped": "skipped", "FAIL": "failed",
            "ERROR": "failed", "expected failure": "expected-failure",
            "unexpected success": "unexpected-success"}.get(
                info["verdict"], "unknown")


# --------------------------------------------------------------------------
# sharding
# --------------------------------------------------------------------------

def all_modules():
    """Every test module, as discovery names it: bare, sorted, no `.py`."""
    return sorted(n[:-3] for n in os.listdir(TESTS)
                  if n.startswith("test") and n.endswith(".py"))


def shard_of(modules, index, of):
    """Contiguous block `index` of `of`. BY MODULE, never splitting one.

    Contiguous rather than round-robin so the order modules run in stays as
    close as it can to the order a single discovery run uses. Cross-module
    leakage is what `tests/envisolation.py` exists for, and a shard that
    reorders modules relative to the baseline would be measuring a different
    thing from the baseline it is compared against.
    """
    if not 0 <= index < of:
        raise SystemExit(f"shard {index} is not in range 0..{of - 1}")
    size, extra = divmod(len(modules), of)
    start = index * size + min(index, extra)
    stop = start + size + (1 if index < extra else 0)
    return modules[start:stop]


def run_shard(args):
    """One shard, offline, with the project's own isolation harness."""
    modules = shard_of(all_modules(), args.index, args.of)
    if not modules:
        print(f"shard {args.index}/{args.of} is empty", flush=True)
        return 0

    # The repo root for `import tests.offline`; `tests/` for the bare module
    # names discovery produces. BOTH, and in this order - see the naming trap
    # in the module docstring.
    for path in (ROOT, TESTS):
        if path not in sys.path:
            sys.path.insert(0, path)

    import unittest

    from tests import envisolation, offline

    blocked = offline.block()
    print(f"shard {args.index}/{args.of}: {len(modules)} modules")
    print("network blocked:", ", ".join(sorted(blocked)))

    loader = unittest.TestLoader()
    suite = envisolation.wrap_discovered(loader.loadTestsFromNames(modules))

    with open(args.log, "w", encoding="utf-8", errors="replace") as log:
        runner = unittest.TextTestRunner(stream=log, verbosity=2)
        result = runner.run(suite)

    print(f"shard {args.index}/{args.of}: ran {result.testsRun}, "
          f"{len(result.failures)} failure(s), {len(result.errors)} error(s), "
          f"{len(result.skipped)} skipped")
    # Deliberately 0 unless the shard could not RUN. A failing test is the
    # gate's business, and a shard that exits non-zero on an expected baseline
    # failure would make every job red and teach everyone to ignore the colour.
    return 0 if result.testsRun else 1


# --------------------------------------------------------------------------
# baseline
# --------------------------------------------------------------------------

#: The word a baseline's provenance block names itself with, and the two lines
#: `regen_baseline` writes when it carries a block forward instead of
#: discarding it. A reader that sees INHERITED must not call the block measured.
PROVENANCE = "PROVENANCE"
CARRIED = "# PROVENANCE CARRIED FORWARD, NOT RE-MEASURED BY THIS RUN."
INHERITED = "#   inherited  true  (this run re-measured the NAMES only)"


def read_baseline(path):
    """The baseline's names. Comments and blanks ignored, order irrelevant."""
    if not os.path.exists(path):
        return None
    names = set()
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line and not line.startswith("#"):
                names.add(line)
    return names


def read_provenance_block(path):
    """The provenance block of an existing baseline, verbatim: from the line
    that names it to the end of the comment run, or None when there is none.

    `read_baseline` skips every `#` line, so nothing downstream ever read these
    bytes - which is exactly why a writer could drop them and nothing noticed.
    """
    if not os.path.exists(path):
        return None
    block = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if block:
                if not line.startswith("#"):
                    break
                block.append(line)
            elif PROVENANCE in line.upper():
                block.append(line)
    return block or None


def regen_baseline(args):
    outcomes, fixtures, ran, overlaps = read_logs(args.logs)
    names = sorted(failing_names(outcomes, fixtures))
    block = read_provenance_block(args.out)
    with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("# Failing test NAMES. One per line. Compared as a SET, in\n"
                 "# both directions, never by count - see scripts/ci_suite.py.\n"
                 "#\n"
                 f"# names: {len(names)}\n"
                 f"# reported: {len(outcomes)}\n"
                 f"# logs: {len(args.logs)}\n"
                 "#\n"
                 "# REGENERATE DELIBERATELY, NEVER TO MAKE A RED CHECK GREEN.\n"
                 "# Every name added here is a test this repository has stopped\n"
                 "# asserting anything with.\n"
                 "#\n")
        # NOT DROPPED. This run re-measures the NAMES and nothing else: the SHA,
        # the machine, the command and the runner counts describe whichever run
        # produced the PREVIOUS file. They are carried forward and LABELLED
        # rather than erased, because a block nobody read is how the counts
        # above drifted away from the provenance that explains them - and
        # because `scripts/check_baseline_provenance.py` reads this label and
        # refuses to call an inherited block VALID.
        if block:
            fh.write(CARRIED + "\n")
            fh.write(INHERITED + "\n")
            for line in block:
                if line.startswith(CARRIED) or line.startswith("#   inherited"):
                    continue
                fh.write(line + "\n")
        else:
            fh.write("# NO MEASUREMENT BLOCK. The previous file carried none, and\n"
                     "# this run cannot write one: it re-measures the NAMES and\n"
                     "# knows nothing else about the run that produced them.\n")
        for name in names:
            fh.write(name + "\n")
    print(f"wrote {args.out}: {len(names)} names from {len(outcomes)} results")
    if overlaps:
        print(f"WARNING: {len(overlaps)} name(s) reported by more than one log")
    return 0


# --------------------------------------------------------------------------
# the gate
# --------------------------------------------------------------------------

def gate(args):
    baseline = read_baseline(args.baseline)
    outcomes, fixtures, ran, overlaps = read_logs(args.logs)
    failing = failing_names(outcomes, fixtures)

    if baseline is None:
        print(f"NO BASELINE at {args.baseline}")
        print(f"this run has {len(failing)} failing name(s) of "
              f"{len(outcomes)} reported")
        _summary(args, None, failing, outcomes, fixtures, ran, overlaps,
                 set(), set())
        return 0 if args.mode == "report" else 1

    new = failing - baseline
    gone = baseline - failing
    both = failing & baseline

    print(f"reported {len(outcomes)} results across {len(args.logs)} log(s)")
    print(f"failing now: {len(failing)}   baseline: {len(baseline)}")
    print(f"NEW:  {len(new)}")
    print(f"GONE: {len(gone)}")
    print(f"BOTH: {len(both)}")
    for name in sorted(new):
        print(f"  NEW  {name}")
    for name in sorted(gone):
        print(f"  GONE {name}  [now: {outcome_of(outcomes, name)}]")

    _summary(args, baseline, failing, outcomes, fixtures, ran, overlaps,
             new, gone)

    if args.mode == "report":
        print("mode=report: the diff above does not fail the job")
        return 0
    if new:
        print(f"FAIL: {len(new)} failing test(s) outside the baseline")
        return 1
    print("PASS: no failing test outside the baseline")
    return 0


def _vanished(outcomes, gone):
    """Of the names that stopped failing, the ones that did not run at all."""
    return sorted(n for n in gone if outcome_of(outcomes, n) == "absent")


def _summary(args, baseline, failing, outcomes, fixtures, ran, overlaps,
             new, gone):
    """The three name sets, into the job summary when there is one."""
    path = args.summary or os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    counts = collections.Counter(i["verdict"] for i in outcomes.values())
    lines = ["# Offline suite", ""]
    lines.append(f"- reported: **{len(outcomes)}** results from "
                 f"{len(args.logs)} shard log(s)")
    lines.append("- " + ", ".join(f"{v}: {counts.get(v, 0)}"
                                  for v in VERDICTS))
    lines.append(f"- failing names: **{len(failing)}**"
                 + (f" against a baseline of {len(baseline)}"
                    if baseline is not None else " (no baseline)"))
    lines.append(f"- mode: `{args.mode}`")
    lines.append("")

    if baseline is None:
        lines.append("> No baseline file. Nothing was gated. Regenerate with")
        lines.append("> `ci_suite.py regen-baseline` and commit it "
                     "deliberately.")
    else:
        lines.append(f"## NEW — failing, not in the baseline ({len(new)})")
        lines.append("")
        if new:
            lines.append("These fail the job." if args.mode == "enforce"
                         else "These would fail the job in `enforce` mode.")
            lines += [f"- `{n}`" for n in sorted(new)]
        else:
            lines.append("None.")
        lines.append("")
        lines.append(f"## GONE — in the baseline, not failing now "
                     f"({len(gone)})")
        lines.append("")
        if gone:
            lines.append("Verified positively: a name is only a fix if the log "
                         "shows it running. `absent` means it did not run.")
            lines.append("")
            lines.append("| test | now |")
            lines.append("| --- | --- |")
            lines += [f"| `{n}` | {outcome_of(outcomes, n)} |"
                      for n in sorted(gone)]
        else:
            lines.append("None.")
        lines.append("")
        lines.append(f"## BOTH — still failing, as recorded "
                     f"({len(failing & baseline)})")
        lines.append("")
        lines.append(f"{len(failing & baseline)} name(s). Not listed; they are "
                     f"the baseline file.")
    lines.append("")

    vanished = _vanished(outcomes, gone)
    if vanished:
        lines.append(f"## {len(vanished)} test(s) DID NOT RUN")
        lines.append("")
        lines.append("A vanished test looks exactly like a passing one. These "
                     "were in the baseline and produced no verdict at all.")
        lines += [f"- `{n}`" for n in vanished]
        lines.append("")

    if fixtures:
        lines.append(f"## {len(fixtures)} class-level fixture failure(s)")
        lines.append("")
        lines.append("A `setUpClass` that raises takes every test in the class "
                     "with it and `Ran N` does not count them.")
        lines += [f"- `{k}` ({v})" for k, v in sorted(fixtures.items())]
        lines.append("")

    if overlaps:
        lines.append(f"## {len(overlaps)} name(s) reported by two shards")
        lines.append("")
        lines.append("Shards are disjoint by module, so this means the shard "
                     "plan is wrong.")
        lines += [f"- `{n}`" for n in overlaps]
        lines.append("")

    lines.append("## Shards")
    lines.append("")
    lines.append("| log | ran |")
    lines.append("| --- | --- |")
    for log, count in sorted(ran.items()):
        lines.append(f"| {log} | {'(no `Ran` line)' if count is None else count} |")

    with open(path, "a", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


def _parser_acts_on(line):
    """True when `parse_log`/`class_level`/`_RAN` would consume this line.

    The redaction below is only safe because this is the complete list. Drop a
    line the parser WOULD have acted on and the damage is not a missing name -
    it is a MISATTRIBUTED one, because `parse_log` carries a `pending` name
    forward and would hand the next bare verdict to the wrong test.
    """
    head = _NAME.match(line)
    if head and head.group(1) == head.group(2).split(".")[-1]:
        return True
    if _AFTER_DOTS.search(line):
        return True
    if _BARE.match(line.strip()):
        return True
    if _CLASS_LEVEL.match(line):
        return True
    if _RAN.match(line):
        return True
    stripped = line.strip()
    return stripped.startswith("FAILED (") or stripped.startswith("OK")


def redact_log(args):
    """Keep only the lines the gate parses. Everything else is dropped.

    WHY THIS EXISTS, and it is not hypothetical. A workflow artifact on a
    PUBLIC repository is a public download, and a verbose unittest log carries
    assertion messages - which quote whatever the asserted value was. The
    gate needs none of that: it needs test names, verdicts, skip reasons,
    class-level fixture failures and the `Ran N` line.

    Measured 2026-10-15 and the reason this is not optional: FIVE tests in
    `test_fixture_hygiene.TestNoRealDataAnywhereInGit` are RED and sit inside
    the committed baseline - the very tests that assert no real email domain,
    no real person or client name and no real LinkedIn vanity URL is anywhere
    in git. While they are red the repository's own PII-in-git guard is not
    holding, so a full log must be treated as capable of carrying real
    identifiers and must not be published.

    The redaction is verified rather than trusted: `--verify` reparses both
    files and refuses unless the outcome map, the fixture map and the
    `Ran N` count are IDENTICAL.
    """
    with open(args.log, "r", errors="replace", encoding="utf-8") as fh:
        full = fh.read()
    kept = [line for line in full.splitlines() if _parser_acts_on(line)]
    out = "\n".join(kept) + "\n"
    with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(out)
    print(f"{args.log}: {len(full.splitlines())} lines, {len(full)} bytes")
    print(f"{args.out}: {len(kept)} lines, {len(out)} bytes "
          f"({100.0 * len(out) / max(len(full), 1):.1f}% kept)")

    if not args.verify:
        return 0
    before, after = parse_log(full), parse_log(out)
    checks = [
        ("names parsed", len(before), len(after)),
        ("outcome maps identical", True, before == after),
        ("fixture maps identical", True,
         class_level(full) == class_level(out)),
    ]
    ran_before = _RAN.search(full)
    ran_after = _RAN.search(out)
    checks.append(("Ran N preserved",
                   ran_before.group(1) if ran_before else None,
                   ran_after.group(1) if ran_after else None))
    bad = []
    for label, want, got in checks:
        ok = want == got
        print(f"  [{'OK' if ok else 'BAD'}] {label}: want {want}, got {got}")
        if not ok:
            bad.append(label)
    if bad:
        print(f"REDACTION CHANGED THE PARSE: {bad}")
        return 1
    print("the redacted log parses to exactly the same verdicts")
    return 0


def check_work(args):
    """Nothing unexpected under `work/`. A measurement, not a promise.

    The suite DOES write there - measured in a clone that started with no
    `work/` at all - so "never writes to work/" would be false if asserted
    flatly. What is asserted is the narrow, checkable thing: only the files the
    suite is known to create appear, and none of them is ever published.
    """
    work = os.path.join(ROOT, "work")
    if not os.path.isdir(work):
        print("work/ absent")
        return 0
    found = sorted(os.listdir(work))
    unexpected = [n for n in found if n not in EPHEMERAL_WORK]
    print(f"work/ holds {len(found)} entry(ies): {found}")
    # Every path, recursively, printed whatever the verdict. The pass/fail is
    # judged on top-level names, but a directory in that set (`reports`) could
    # hide anything underneath it, and a log that only ever showed four names
    # would make that invisible. Printing is not judging - it is how a person
    # reading the artifact can see what the runner actually wrote.
    for root, _dirs, files in os.walk(work):
        for name in sorted(files):
            rel = os.path.relpath(os.path.join(root, name), work)
            print(f"  work/{rel.replace(os.sep, '/')}")
    if unexpected:
        print(f"UNEXPECTED under work/: {unexpected}")
        print("Known-ephemeral: " + ", ".join(sorted(EPHEMERAL_WORK)))
        return 1
    print("all known-ephemeral")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run-shard", help="run one shard offline")
    run.add_argument("--index", type=int, required=True)
    run.add_argument("--of", type=int, required=True)
    run.add_argument("--log", required=True)
    run.set_defaults(func=run_shard)

    plan = sub.add_parser("plan", help="print the shard plan and exit")
    plan.add_argument("--of", type=int, required=True)
    plan.set_defaults(func=_plan)

    g = sub.add_parser("gate", help="diff a run against the baseline")
    g.add_argument("--logs", nargs="+", required=True)
    g.add_argument("--baseline",
                   default=os.path.join(ROOT, ".github", "suite-baseline.txt"))
    g.add_argument("--mode", choices=("report", "enforce"), default="enforce")
    g.add_argument("--summary", default=None)
    g.set_defaults(func=gate)

    r = sub.add_parser("regen-baseline", help="rewrite the baseline file")
    r.add_argument("--logs", nargs="+", required=True)
    r.add_argument("--out",
                   default=os.path.join(ROOT, ".github", "suite-baseline.txt"))
    r.set_defaults(func=regen_baseline)

    d = sub.add_parser("redact-log",
                       help="strip everything the gate does not parse")
    d.add_argument("--log", required=True)
    d.add_argument("--out", required=True)
    d.add_argument("--verify", action="store_true",
                   help="refuse unless the redacted log parses identically")
    d.set_defaults(func=redact_log)

    w = sub.add_parser("check-work", help="only known files under work/")
    w.set_defaults(func=check_work)

    args = parser.parse_args(argv)
    return args.func(args)


def _plan(args):
    modules = all_modules()
    print(f"{len(modules)} modules into {args.of} shard(s)")
    for index in range(args.of):
        mine = shard_of(modules, index, args.of)
        print(f"  shard {index}: {len(mine)} modules "
              f"[{mine[0] if mine else '-'} .. {mine[-1] if mine else '-'}]")
    print(json.dumps(list(range(args.of))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
