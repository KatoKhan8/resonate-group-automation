# -*- coding: utf-8 -*-
"""TASK-0243 - the controls for rows 2 and 5 of `scripts/exit_nine.py`.

TASK-0239's reachability matrix found two rows of the canary exit table that
report MET while their own printed evidence is red:

* **row 2** read `"NOT ok" in <formatted label>` - a substring no branch of the
  label builder can produce - so a FAILING demonstration read as a pass and the
  row **could not print NOT MET for any state of its input**. Failure family 1,
  failing OPEN, in the row that tells an operator a removal request is honoured.
* **row 5** scored `MET if bypass == 0 else NOT_MET` while running and PRINTING
  31 pin tests, 8 of them red, that nothing in the verdict ever read. Failure
  family 4: the row's printed evidence is not its evidence.

This module is the control set for both repairs. It plants, measures, reverts,
and proves every revert by the working file's own sha256 - never by
`git status` or `git diff`, because `0237` measured 2,482 of 2,588 tracked
files byte-divergent from their blob while status read CLEAN.

The plant machinery is NOT reimplemented here: it is imported from
`scripts/exit_nine_reachability.py`, which is committed at 1edcd1321 and whose
`Plant` / `insert_statements` / `replace_once` already carry the three traps
that cost that task a cell (a literal `\\n` against a CRLF file, a plant that
lands nowhere, a revert argued from `git status`).

    py -3 -B scripts/exit_rows_two_and_five.py c1        the defect, UNREPAIRED
    py -3 -B scripts/exit_rows_two_and_five.py tokens    C5, the token set
    py -3 -B scripts/exit_rows_two_and_five.py row2      C2 + C3 + the UNKNOWN leg
    py -3 -B scripts/exit_rows_two_and_five.py row5      row 5, both verdicts
    py -3 -B scripts/exit_rows_two_and_five.py worlds    C6, the three worlds
    py -3 -B scripts/exit_rows_two_and_five.py mutate2-met      C4a (commit it)
    py -3 -B scripts/exit_rows_two_and_five.py mutate2-notmet   C4b (commit it)
    py -3 -B scripts/exit_rows_two_and_five.py mutate5-met      C4c (commit it)
    py -3 -B scripts/exit_rows_two_and_five.py mutate5-notmet   C4d (commit it)

Run from a THROWAWAY tree only. Every mutate-* mode must be COMMITTED in that
tree before it has any effect: `exit_nine` hashes itself against
`HEAD:scripts/exit_nine.py`, so an uncommitted mutation makes all nine UNKNOWN
and would redden every control at once instead of the ones under test - a
mutation that looks caught because a different guard fired first.
"""
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile

ROOT = os.getcwd()
EXIT_NINE = os.path.join("scripts", "exit_nine.py")
REACH = os.path.join("scripts", "exit_nine_reachability.py")
SCRATCH = os.environ.get(
    "EXIT_ROWS_SCRATCH",
    os.path.join(tempfile.gettempdir(), "exit-rows-two-and-five"))

DEMO_FILE = "tests/test_a_suppressed_address_cannot_reach_a_provider.py"
DEMO_TEST = "test_an_attributed_removal_request_writes_a_suppression_row"
DEMO_SECOND = "test_an_unattributable_removal_request_still_writes_a_held_row"

GATE_FILE = "tests/test_no_new_write_bypasses_the_door.py"
GATE_TEST = "test_no_bypassing_call_site_is_new"
PROPOSALS_FILE = "tests/test_the_eight_write_path_proposals_are_unapplied.py"
PROPOSALS_TEST = "test_p1_a_resume_does_not_restart_a_campaign_holding_a_suppressed_contact"
BASELINE = os.path.join("scripts", "known_write_bypasses.json")
REGEN = os.path.join("scripts", "regen_write_bypass_baseline.py")

PLANT_TAG = "TASK-0243 plant"
FAIL_STMT = 'self.fail("%s")' % PLANT_TAG
ERROR_STMT = 'raise RuntimeError("%s")' % PLANT_TAG
SKIP_STMT = 'self.skipTest("%s")' % PLANT_TAG


def _reach():
    """0239's committed plant machinery, loaded from THIS tree."""
    path = os.path.join(ROOT, REACH)
    if not os.path.exists(path):
        raise SystemExit("%s is absent - this harness borrows its plant and "
                         "revert machinery and will not reimplement it" % path)
    spec = importlib.util.spec_from_file_location("pc0243_reach", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


R = _reach()


# ------------------------------------------------------------------ cells

def cell(label, expect, got, extra=""):
    ok = got == expect
    print("    %-44s -> %-9s expected %-9s %s%s"
          % (label, got, expect, "OK" if ok else "MISMATCH",
             ("  " + extra) if extra else ""))
    return ok


def plant_cell(label, number, build, expect, env=None, show=True):
    """Apply a plant, evaluate ONE criterion, revert, prove the revert."""
    plant = R.Plant(label)
    verdict, denominator, condition = "(not run)", "", ""
    try:
        build(plant)
        got = R.row(number, env=env)
        verdict = got["verdict"]
        denominator = got["denominator"]
        condition = got["condition"]
    except SystemExit as refused:
        verdict = "(PLANT DID NOT LAND)"
        condition = str(refused)
    finally:
        proof = plant.revert()
    ok = cell(label, expect, verdict)
    if show:
        print("        denom  %s" % denominator)
    bad = [p for p in proof if not p[3]]
    if bad:
        print("        REVERT FAILED: %s" % ", ".join(p[0] for p in bad))
    return dict(label=label, number=number, expect=expect, verdict=verdict,
                ok=ok, denominator=denominator, condition=condition,
                reverts=len(proof), reverts_ok=not bad)


def noop(plant):
    return None


def fail_demo(plant):
    R.insert_statements(plant, [(DEMO_FILE, DEMO_TEST, FAIL_STMT, False)])


def error_demo(plant):
    R.insert_statements(plant, [(DEMO_FILE, DEMO_TEST, ERROR_STMT, False)])


def skip_demo(plant):
    R.insert_statements(plant, [(DEMO_FILE, DEMO_TEST, SKIP_STMT, False)])


def decorate(plant, rel, test, decorator):
    """Add a decorator to a test method, editing the bytes CURRENTLY on disk.

    0239's `replace_once` and `insert_statements` both edit the bytes the Plant
    SAVED. That is right for one edit per file and silently discards the FIRST
    of two, and it cost this task's C5 a token on the first run: the decorator
    landed, `insert_statements` then rewrote the file from the saved blob, and
    the row reported `(RAN, FAIL)` where `expected failure` was wanted. A plant
    clobbered by a plant reads exactly like a token the formatter cannot emit -
    which is the defect this whole task is about, one level up. So this edits
    the live bytes and leaves the ORIGINAL held, once, for the revert.
    """
    plant.hold(rel)
    path = os.path.join(ROOT, rel)
    with io.open(path, "rb") as handle:
        text = handle.read().decode("utf-8")
    crlf = "\r\n" in text
    flat = text.replace("\r\n", "\n")
    anchor = "    def %s(" % test
    if flat.count(anchor) != 1:
        raise SystemExit("decorate: %r occurs %d times in %s, need exactly 1"
                         % (anchor, flat.count(anchor), rel))
    out = flat.replace(anchor, "    %s\n%s" % (decorator, anchor), 1)
    if crlf:
        out = out.replace("\n", "\r\n")
    with io.open(path, "wb") as handle:
        handle.write(out.encode("utf-8"))
    if decorator not in R.read_bytes(rel).decode("utf-8"):
        raise SystemExit("decorate: %r is not in %s after the write"
                         % (decorator, rel))


def expected_failure_demo(plant):
    """@unittest.expectedFailure on a test planted to FAIL -> 'expected failure'.

    The statement plant goes FIRST and the decorator second, because only
    `decorate` reads the live bytes.
    """
    R.insert_statements(plant, [(DEMO_FILE, DEMO_TEST, FAIL_STMT, False)])
    decorate(plant, DEMO_FILE, DEMO_TEST, "@unittest.expectedFailure")


def unexpected_success_demo(plant):
    """@unittest.expectedFailure on a test that PASSES -> 'unexpected success'."""
    decorate(plant, DEMO_FILE, DEMO_TEST, "@unittest.expectedFailure")


def rename_demo(plant):
    R.replace_once(plant, DEMO_FILE, "def %s(" % DEMO_TEST,
                   "def renamed_%s(" % DEMO_TEST)


# ------------------------------------------------------------------ C1

def c1():
    """The defect, in the UNREPAIRED evaluator. Refuses on a repaired tree."""
    source = R.read_bytes(EXIT_NINE).decode("utf-8")
    if '"NOT ok" in s' not in source:
        raise SystemExit(
            "this tree's %s does not carry the `\"NOT ok\" in s` detector, so "
            "C1 cannot be reproduced here. C1 is a measurement of the "
            "UNREPAIRED evaluator and belongs at 1edcd1321 or earlier; "
            "running it against the repair would be a control that cannot "
            "fail." % EXIT_NINE)
    print("C1  the defect reproduces: self.fail() planted in %s" % DEMO_TEST)
    print("    detector in this tree: bad = [s for s in shown "
          'if "NOT ok" in s]')
    got = plant_cell("C1 unrepaired, demonstration FAILs", 2, fail_demo, "MET")
    print("    cond   %s" % got["condition"][:300])
    print()
    print("    C1 %s - the UNREPAIRED row printed %s with (RAN, FAIL) in its "
          "own denominator"
          % ("PASS" if got["ok"] and "(RAN, FAIL)" in got["denominator"]
             else "FAIL", got["verdict"]))
    return 0 if got["ok"] and "(RAN, FAIL)" in got["denominator"] else 1


# ------------------------------------------------------------------ C5

TOKEN_CELLS = [
    ("ok", noop, "MET"),
    ("FAIL", fail_demo, "NOT MET"),
    ("ERROR", error_demo, "NOT MET"),
    ("skipped", skip_demo, "UNKNOWN"),
    ("expected failure", expected_failure_demo, "UNKNOWN"),
    ("unexpected success", unexpected_success_demo, "UNKNOWN"),
]


def tokens():
    """C5 - every terminal token the label builder can emit, forced and seen.

    A token missed here is the next `"NOT ok"`: the whole defect was a branch
    of the detector keyed to a string the formatter never writes.

    On an UNREPAIRED tree the expected verdict is MET for every one of the six,
    and that is the point: the family-1 property is then measured over the
    COMPLETE input space of the detector rather than inferred from the one
    sample that happened to be planted.
    """
    unrepaired = '"NOT ok" in s' in R.read_bytes(EXIT_NINE).decode("utf-8")
    print("C5  the terminal-status token set, each one FORCED and observed")
    print("    this tree's detector is %s"
          % ("UNREPAIRED - every token must read MET, which IS the family-1 "
             "property" if unrepaired else "repaired"))
    results = []
    for token, build, expect in TOKEN_CELLS:
        got = plant_cell("token %r" % token, 2, build,
                         "MET" if unrepaired else expect)
        seen = token in got["denominator"] or (
            token == "ok" and "(RAN," not in got["denominator"])
        print("        token %-20r appears in the row's own denominator: %s"
              % (token, seen))
        got["token"], got["token_seen"] = token, seen
        results.append(got)
    print()
    missed = [g["token"] for g in results if not g["token_seen"]]
    bad = [g["label"] for g in results if not g["ok"]]
    print("C5 %s - %d of %d tokens observed, %d of %d verdicts as predicted"
          % ("PASS" if not missed and not bad else "FAIL",
             len(results) - len(missed), len(results),
             len(results) - len(bad), len(results)))
    for token in missed:
        print("   TOKEN NOT OBSERVED: %r" % token)
    for label in bad:
        print("   VERDICT MISMATCH: %s" % label)
    _dump("c5-tokens.json", results)
    return 0 if not missed and not bad else 1


# ------------------------------------------------------------------ row 2

def row2():
    """C2, C3 and the UNKNOWN leg of the repaired row 2."""
    print("row 2 - the three ways the repaired detector may score")
    results = [
        plant_cell("C3 no plant: all green, population established",
                   2, noop, "MET"),
        plant_cell("C2 demonstration FAILs", 2, fail_demo, "NOT MET"),
        plant_cell("C2b demonstration ERRORs", 2, error_demo, "NOT MET"),
        plant_cell("UNKNOWN: demonstration SKIPPED", 2, skip_demo, "UNKNOWN"),
        plant_cell("UNKNOWN: demonstration renamed away", 2, rename_demo,
                   "UNKNOWN"),
    ]
    named = [g for g in results if g["label"].startswith("C2 ")]
    print()
    print("    C2 names the failing test in its own output: %s"
          % (DEMO_TEST in (named[0]["denominator"] + named[0]["condition"])
             if named else "?"))
    bad = [g["label"] for g in results if not g["ok"]]
    print("row 2 %s - %d of %d cells as predicted"
          % ("PASS" if not bad else "FAIL", len(results) - len(bad),
             len(results)))
    for label in bad:
        print("   MISMATCH: %s" % label)
    _dump("row2.json", results)
    return 0 if not bad else 1


# ------------------------------------------------------------------ row 5

def _bypass_pairs():
    import importlib.util as util
    spec = util.spec_from_file_location(
        "pc0243_denominator",
        os.path.join(ROOT, "scripts", "write_path_denominator.py"))
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    writers = module.mutating_functions(ROOT)
    return sorted(set((rel, where)
                      for verdict, rel, line, call, where
                      in module.call_sites(ROOT, writers)
                      if verdict == "BYPASS"))


def door_all_bypasses(plant):
    R.insert_statements(plant, [(rel, where, R.DOOR_STMT, True)
                                for rel, where in _bypass_pairs()])


def regen_baseline(plant):
    """Run the remedy the drift test itself prints, holding the file's bytes."""
    plant.hold(BASELINE)
    proc = subprocess.run([sys.executable, "-B", REGEN], cwd=ROOT,
                          capture_output=True, text=True, timeout=1800)
    if proc.returncode != 0:
        raise SystemExit("%s exited %d: %s"
                         % (REGEN, proc.returncode,
                            (proc.stdout + proc.stderr)[-400:]))


def doored_and_fresh(plant):
    door_all_bypasses(plant)
    regen_baseline(plant)


def doored_fresh_gate_red(plant):
    doored_and_fresh(plant)
    R.insert_statements(plant, [(GATE_FILE, GATE_TEST, FAIL_STMT, False)])


def doored_fresh_proposal_red(plant):
    doored_and_fresh(plant)
    R.insert_statements(plant, [(PROPOSALS_FILE, PROPOSALS_TEST,
                                 FAIL_STMT, False)])


def row5():
    """Row 5 both ways, plus the two cells that prove WHICH reds it charges."""
    print("row 5 - both verdicts, and the charge/no-charge split")
    results = [
        plant_cell("NOT MET: tree as it stands, 26 BYPASS", 5, noop, "NOT MET"),
        plant_cell("MET: doors on all bypasses + fresh baseline", 5,
                   doored_and_fresh, "MET"),
        plant_cell("NOT MET: ...and the GATE pin planted red", 5,
                   doored_fresh_gate_red, "NOT MET"),
        plant_cell("MET: ...and a PROPOSALS pin planted red (not charged)", 5,
                   doored_fresh_proposal_red, "MET"),
    ]
    bad = [g["label"] for g in results if not g["ok"]]
    print()
    print("row 5 %s - %d of %d cells as predicted"
          % ("PASS" if not bad else "FAIL", len(results) - len(bad),
             len(results)))
    for label in bad:
        print("   MISMATCH: %s" % label)
    _dump("row5.json", results)
    return 0 if not bad else 1


# ------------------------------------------------------------------ C6

def _criterion_source(name):
    import ast
    source = R.read_bytes(EXIT_NINE).decode("utf-8")
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise SystemExit("no def %s in %s" % (name, EXIT_NINE))


def consults_its_tests(name, source_node=None):
    """STATIC axis: is a unittest result REACHABLE from the verdict expression?

    Not "does the function call unittest_names" - row 5 calls it, prints its
    answer, and scores it nowhere. The question is whether any name the verdict
    is computed FROM derives, transitively, from that call. Answered from the
    AST of the criterion function, so it is a property of the code and not of
    the sample that happened to run.
    """
    import ast
    node = source_node or _criterion_source(name)

    produced_by_tests = set()
    assigns = []

    def names_in(expr):
        return set(n.id for n in ast.walk(expr) if isinstance(n, ast.Name))

    def calls_unittest(expr):
        for call in ast.walk(expr):
            if isinstance(call, ast.Call):
                func = call.func
                if isinstance(func, ast.Name) and func.id == "unittest_names":
                    return True
        return False

    for sub in ast.walk(node):
        if isinstance(sub, (ast.Assign, ast.AnnAssign)):
            targets = sub.targets if isinstance(sub, ast.Assign) else [sub.target]
            lhs = set()
            for target in targets:
                lhs |= set(n.id for n in ast.walk(target)
                           if isinstance(n, ast.Name))
            rhs = sub.value
            if rhs is None:
                continue
            if calls_unittest(rhs):
                produced_by_tests |= lhs
            assigns.append((lhs, names_in(rhs)))
        elif isinstance(sub, ast.AugAssign):
            lhs = set(n.id for n in ast.walk(sub.target)
                      if isinstance(n, ast.Name))
            assigns.append((lhs, names_in(sub.value) | lhs))
        elif isinstance(sub, (ast.For, ast.comprehension)):
            target = getattr(sub, "target", None)
            iterator = getattr(sub, "iter", None)
            if target is not None and iterator is not None:
                lhs = set(n.id for n in ast.walk(target)
                          if isinstance(n, ast.Name))
                assigns.append((lhs, names_in(iterator)))

    #: Seed: every name the VERDICT is computed from. Both shapes this file
    #: uses - `verdict = <expr>` in a branch, and `verdict=<expr>` as the
    #: returned dict's keyword - because row 1 uses the first and row 5 the
    #: second, and a seed that reads only one of them would answer "not read"
    #: for the wrong reason.
    seed = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Assign):
            for target in sub.targets:
                if isinstance(target, ast.Name) and target.id == "verdict":
                    seed |= names_in(sub.value)
        if isinstance(sub, ast.Call):
            for keyword in sub.keywords:
                if keyword.arg == "verdict":
                    seed |= names_in(keyword.value)

    #: Transitive closure over the assignments, to a fixed point.
    reached = set(seed)
    changed = True
    while changed:
        changed = False
        for lhs, rhs in assigns:
            if lhs & reached and not rhs <= reached:
                reached |= rhs
                changed = True
    return bool(reached & produced_by_tests), sorted(seed), sorted(
        reached & produced_by_tests)


def worlds():
    """C6 - the three worlds of Part B item 6, each constructed as an input.

    A method that answers the same world for all three has not discriminated,
    and that is a reportable result rather than a reason to guess. Two axes:

      STATIC   is a unittest result reachable from the verdict expression?
      DYNAMIC  does the verdict MOVE when a test the row prints goes red?

      reads + moves      -> an honest reader (world 3 territory; whether the
                            red is on-criterion is then an attribution
                            question, answered by reading the test)
      reads + inert      -> world 1, family 1: it reads them and mis-parses
      prints + inert     -> world 2, family 4: its printed evidence is not
                            its evidence
    """
    print("C6  the three worlds, constructed and discriminated")
    print()
    probes = [
        #: (label, criterion, a plant that reddens a test the row PRINTS,
        #:  expected world)
        ("row 1 (control: an honest reader)", 1,
         lambda plant: R.insert_statements(
             plant, [(DEMO_FILE, DEMO_TEST, FAIL_STMT, False)]),
         "reads+moves"),
        ("row 2 as repaired", 2, fail_demo, "reads+moves"),
        ("row 5 as repaired", 5, doored_fresh_gate_red, "reads+moves"),
    ]
    results = []
    for label, number, build, expect in probes:
        static, seed, via = consults_its_tests("criterion_%d" % number)
        before = R.row(number)
        after = plant_cell("DYNAMIC %s" % label, number, build, "(either)",
                           show=False)
        moved = after["verdict"] != before["verdict"]
        world = ("reads+moves" if static and moved else
                 "reads+inert" if static else
                 "prints+inert")
        print("    %-38s static=%-5s via %-22s before=%-8s after=%-8s -> %s"
              % (label, static, ",".join(via) or "-", before["verdict"],
                 after["verdict"], world))
        results.append(dict(label=label, number=number, static=static,
                            via=via, seed=seed, before=before["verdict"],
                            after=after["verdict"], moved=moved, world=world,
                            expect=expect))
    print()
    distinct = sorted(set(r["world"] for r in results))
    print("    worlds reported: %s" % ", ".join(distinct))
    _dump("worlds.json", results)
    return 0


def statics():
    """The static axis alone, for all nine rows. Cheap, and it is the read
    that answers Part B item 6 without a plant."""
    print("the static axis for all nine rows: is a unittest result reachable "
          "from the verdict expression?")
    out = []
    for number in range(1, 10):
        static, seed, via = consults_its_tests("criterion_%d" % number)
        print("    criterion_%d  reads-its-tests=%-5s  verdict seeded by %-28s"
              "  via %s" % (number, static, ",".join(seed) or "-",
                            ",".join(via) or "-"))
        out.append(dict(number=number, static=static, seed=seed, via=via))
    _dump("statics.json", out)
    return 0


# ------------------------------------------------------------------ C4

def mutate(number, force):
    """C4 - make criterion N return `force` UNCONDITIONALLY, as its first
    statement, so the mutation is blind to every input the row has.

    Must be COMMITTED in the throwaway tree before it has any effect.
    """
    plant = R.Plant("C4 criterion_%d -> %s" % (number, force))
    anchor = "def criterion_%d():" % number
    R.replace_once(
        plant, EXIT_NINE, anchor,
        anchor + '\n    return dict(verdict=%s, authority=[], '
        'denominator="TASK-0243 C4 mutant", condition="TASK-0243 C4 mutant", '
        'detail=[])   # TASK-0243 C4' % force)
    print("mutated criterion_%d in %s: it now returns %s unconditionally"
          % (number, EXIT_NINE, force))
    print("new sha256 %s" % R.digest(R.read_bytes(EXIT_NINE)))
    print("COMMIT THIS before measuring - exit_nine hashes itself against HEAD")
    return 0


# ------------------------------------------------------------------ plumbing

def _dump(name, payload):
    if not os.path.isdir(SCRATCH):
        os.makedirs(SCRATCH)
    with io.open(os.path.join(SCRATCH, name), "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=1, default=str)


MODES = {
    "c1": c1,
    "tokens": tokens,
    "row2": row2,
    "row5": row5,
    "worlds": worlds,
    "statics": statics,
    "mutate2-met": lambda: mutate(2, "MET"),
    "mutate2-notmet": lambda: mutate(2, "NOT_MET"),
    "mutate5-met": lambda: mutate(5, "MET"),
    "mutate5-notmet": lambda: mutate(5, "NOT_MET"),
}


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "statics"
    print("tree %s" % ROOT)
    print("HEAD %s" % subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                     capture_output=True,
                                     text=True).stdout.strip())
    print("exit_nine sha256 %s" % R.digest(R.read_bytes(EXIT_NINE)))
    print("scratch %s" % SCRATCH)
    print()
    if mode not in MODES:
        print("unknown mode %r; one of %s" % (mode, ", ".join(sorted(MODES))))
        return 2
    return MODES[mode]()


if __name__ == "__main__":
    sys.exit(main())
