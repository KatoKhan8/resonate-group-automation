# -*- coding: utf-8 -*-
"""TASK-0247 - the plant-composition defect in the shared plant machinery.

`scripts/exit_nine_reachability.py` is this estate's shared plant machinery:
`Plant`, `insert_statements` and `replace_once`, imported by every harness that
forces a state by editing bytes. Both editors rewrite the WHOLE file, and both
sourced their text from `Plant.hold`, which answers with the bytes of the FIRST
plant to touch the file for the whole life of the Plant. So a second edit to the
same file under the same Plant silently discarded the first - last write wins,
and nothing said so. A plant that did not land reads exactly like a plant that
landed and was survived, which is failure family 5.

Found by pilotcaps/0243 (its C5 read `(RAN, FAIL)` where `expected failure` was
wanted), worked around locally there with `decorate`, and repaired in the shared
machinery by TASK-0247: `Plant.live` saves the original once and answers with
the bytes NOW on disk, and both editors source from it.

    py -3 -B scripts/plant_composition_controls.py test      C1 - the born-red test
    py -3 -B scripts/plant_composition_controls.py mutate    C2 - paired mutants
    py -3 -B scripts/plant_composition_controls.py c3        C3 - the finder can miss
    py -3 -B scripts/plant_composition_controls.py resolve   the measured path sets
    py -3 -B scripts/plant_composition_controls.py ab        the no-behaviour-change A/B
    py -3 -B scripts/plant_composition_controls.py census    the blast-radius table
    py -3 -B scripts/plant_composition_controls.py all       all four, in order

`test` honours PC0247_MACHINERY, an absolute path to the machinery to load, so
the same test module can be pointed at the unrepaired bytes (where it must go
red) and at the repaired bytes (where it must go green). Everything is written
to a scratch dir OUTSIDE every checkout; no tracked file is ever edited by this
harness, which is a stronger statement than a proven revert.
"""
import ast
import hashlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.getcwd()
MACHINERY_REL = os.path.join("scripts", "exit_nine_reachability.py")
#: OUTSIDE the tree under measurement, always - an earlier harness in this
#: estate had its stray json charged to the change by test_fixture_hygiene.
SCRATCH = os.environ.get(
    "PC0247_SCRATCH", os.path.join(tempfile.gettempdir(), "pc0247"))

#: The editors that REWRITE THE WHOLE FILE from a text they chose. On the
#: unrepaired bytes these source from `hold`, so each one clobbers every
#: earlier edit to the same file under the same Plant.
CLOBBERING_EDITORS = ("insert_statements", "replace_once")
#: 0243's local workaround reads the LIVE bytes, so it does not clobber - which
#: is why the order in `expected_failure_demo` is load-bearing and documented.
LIVE_EDITORS = ("decorate",)
EDITORS = CLOBBERING_EDITORS + LIVE_EDITORS


def sha256_file(path):
    with io.open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def receipt_path(name):
    return os.path.join(SCRATCH, "receipt-%s.json" % name)


def write_receipt(name, payload):
    if not os.path.isdir(SCRATCH):
        os.makedirs(SCRATCH)
    with io.open(receipt_path(name), "w", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, indent=2, sort_keys=True))


def read_receipt(name):
    try:
        with io.open(receipt_path(name), encoding="utf-8") as handle:
            return json.loads(handle.read())
    except (IOError, OSError, ValueError):
        return None


# ===================================================== C1, the born-red test

TARGET = (
    "import unittest\n"
    "\n"
    "\n"
    "class ADemo(unittest.TestCase):\n"
    "    def test_x(self):\n"
    '        """A docstring, because the real corpus has them."""\n'
    "        self.assertTrue(True)\n"
)

PLANT_A = "raise AssertionError('PLANT_A')"
PLANT_B = "self.extra = 'PLANT_B'"
OLD_CLASS = "class ADemo("
NEW_CLASS = "class ARenamedDemo("
OLD_DEF = "def test_x("
NEW_DEF = "def renamed_test_x("


def load_machinery():
    """The machinery under test, from PC0247_MACHINERY or this tree."""
    path = os.environ.get("PC0247_MACHINERY",
                          os.path.join(ROOT, MACHINERY_REL))
    tag = hashlib.sha256(path.encode("utf-8")).hexdigest()[:12]
    spec = importlib.util.spec_from_file_location("pc0247_mach_%s" % tag, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return path, module


class APlantComposes(unittest.TestCase):
    """Two plants on one file, under one Plant, both land - or it refuses.

    Born RED against the machinery as pilotcaps/0239 committed it: three of
    these five fail there, and the two that pass are the controls that prove
    the harness is watching something.
    """

    REL = "mod.py"

    def setUp(self):
        self.path, self.R = load_machinery()
        self.dirpath = os.path.join(SCRATCH, "c1-%s" % self.id().split(".")[-1])
        if os.path.isdir(self.dirpath):
            shutil.rmtree(self.dirpath)
        os.makedirs(self.dirpath)
        self.R.ROOT = self.dirpath
        self.target = os.path.join(self.dirpath, self.REL)
        with io.open(self.target, "wb") as handle:
            handle.write(TARGET.replace("\n", "\r\n").encode("utf-8"))
        self.original = sha256_file(self.target)
        self.plant = self.R.Plant("0247 " + self.id().split(".")[-1])

    def tearDown(self):
        #: Reverted but NOT asserted here. The revert contract is asserted by
        #: its own two tests, so a mutant that breaks the revert and a mutant
        #: that breaks the composition get different kill sets.
        try:
            self.plant.revert()
        except Exception:
            pass

    def body(self):
        with io.open(self.target, "rb") as handle:
            return handle.read().decode("utf-8")

    def test_two_statement_plants_on_one_file_both_land(self):
        self.R.insert_statements(self.plant,
                                 [(self.REL, "test_x", PLANT_A, False)])
        self.R.insert_statements(self.plant,
                                 [(self.REL, "test_x", PLANT_B, False)])
        text = self.body()
        self.assertIn(PLANT_A, text,
                      "the FIRST plant was discarded by the second")
        self.assertIn(PLANT_B, text, "the SECOND plant did not land")

    def test_a_statement_plant_survives_a_later_replacement(self):
        self.R.insert_statements(self.plant,
                                 [(self.REL, "test_x", PLANT_A, False)])
        self.R.replace_once(self.plant, self.REL, OLD_CLASS, NEW_CLASS)
        text = self.body()
        self.assertIn(PLANT_A, text,
                      "the statement plant was discarded by replace_once")
        self.assertIn(NEW_CLASS, text, "the replacement did not land")

    def test_an_unsatisfiable_composition_refuses_rather_than_losing_a_plant(self):
        """Rename the def, then plant into the old name.

        There is no file in which both have landed, so the only correct
        answers are a refusal. The defect answered with neither: it wrote the
        statement plant into a file where the rename had vanished.
        """
        self.R.replace_once(self.plant, self.REL, OLD_DEF, NEW_DEF)
        try:
            self.R.insert_statements(self.plant,
                                     [(self.REL, "test_x", PLANT_A, False)])
        except SystemExit as refused:
            self.assertIn("test_x", str(refused))
            return
        text = self.body()
        self.fail("no refusal, and the file now has rename=%s plant=%s - a "
                  "plant clobbered by a plant reads exactly like a plant that "
                  "landed and was survived"
                  % (NEW_DEF in text, PLANT_A in text))

    def test_a_single_plant_still_lands_and_reverts(self):
        """The control. Unchanged by the repair, and it holds the revert."""
        self.R.insert_statements(self.plant,
                                 [(self.REL, "test_x", PLANT_A, False)])
        self.assertIn(PLANT_A, self.body())
        proof = self.plant.revert()
        self.assertTrue(proof, "revert proved nothing - it held no file")
        self.assertTrue(all(p[3] for p in proof))
        self.assertEqual(self.original, sha256_file(self.target))

    def test_hold_still_answers_with_the_original_bytes(self):
        """The control. `hold`'s own contract must not move."""
        first = self.plant.hold(self.REL)
        self.R.insert_statements(self.plant,
                                 [(self.REL, "test_x", PLANT_A, False)])
        self.assertEqual(first, self.plant.hold(self.REL),
                         "hold stopped answering with the ORIGINAL bytes")
        self.assertEqual(hashlib.sha256(first).hexdigest(), self.original)


BORN_RED = ("test_two_statement_plants_on_one_file_both_land",
            "test_a_statement_plant_survives_a_later_replacement",
            "test_an_unsatisfiable_composition_refuses_rather_than_losing_a_plant")
CONTROLS = ("test_a_single_plant_still_lands_and_reverts",
            "test_hold_still_answers_with_the_original_bytes")


def run_testcase(machinery=None, scratch_tag="run"):
    """Run APlantComposes in a CHILD process and return (headline, failed set).

    A child, because the machinery is loaded by path and `-B` keeps the
    mutants' bytes out of any __pycache__ - and because the headline wanted is
    unittest's own, printed verbatim rather than reconstructed.
    """
    env = dict(os.environ)
    if machinery:
        env["PC0247_MACHINERY"] = machinery
    env["PC0247_SCRATCH"] = os.path.join(SCRATCH, scratch_tag)
    proc = subprocess.run(
        [sys.executable, "-B", os.path.abspath(__file__), "_unittest"],
        cwd=ROOT, capture_output=True, env=env, timeout=600)
    out = proc.stdout.decode("utf-8", "replace")
    err = proc.stderr.decode("utf-8", "replace")
    text = out + err
    failed = set()
    for line in text.splitlines():
        line = line.strip()
        for prefix in ("FAIL: ", "ERROR: "):
            if line.startswith(prefix):
                failed.add(line[len(prefix):].split(" ")[0])
    headline = ""
    for line in text.splitlines():
        if line.startswith("OK") or line.startswith("FAILED"):
            headline = line.rstrip()
    return headline, failed, text


def control_one():
    """C1 - the same test module against the unrepaired and repaired bytes."""
    print("C1  the born-red test, both states")
    tracked = os.path.join(ROOT, MACHINERY_REL)
    repaired = sha256_file(tracked)
    print("    repaired machinery   %s" % MACHINERY_REL)
    print("    repaired sha256      %s" % repaired)

    old = unrepaired_copy()
    print("    unrepaired copy      %s" % old)
    print("    unrepaired sha256    %s" % sha256_file(old))

    red_head, red_failed, _ = run_testcase(old, "c1-before")
    print("    BEFORE headline      %s" % red_head)
    print("    BEFORE failing       %s" % ", ".join(sorted(red_failed)))
    green_head, green_failed, _ = run_testcase(None, "c1-after")
    print("    AFTER  headline      %s" % green_head)
    print("    AFTER  failing       %s"
          % (", ".join(sorted(green_failed)) or "(none)"))

    born_red_ok = set(red_failed) == set(BORN_RED)
    green_ok = not green_failed
    print("    born-red set is exactly the three named: %s" % born_red_ok)
    print("    the two controls pass on BOTH:            %s"
          % (not (set(CONTROLS) & set(red_failed))))
    print("    C1 %s" % ("PASS" if born_red_ok and green_ok else "FAIL"))
    write_receipt("c1", dict(
        before_headline=red_head, before_failing=sorted(red_failed),
        after_headline=green_head, after_failing=sorted(green_failed),
        both_states=bool(red_head) and bool(green_head),
        passed=bool(born_red_ok and green_ok),
        repaired_sha256=repaired, unrepaired_sha256=sha256_file(old)))
    return born_red_ok and green_ok


# ============================================ the unrepaired bytes, for C1/C2

#: The two edit sources, each anchored over MORE THAN ITS OWN LINE. The
#: four-space form is a SUBSTRING of the eight-space form, so a one-line
#: anchor matches both sites and a "half" mutant silently becomes the whole
#: one - measured, first run of C2, which reported FAIL and said why.
INSERT_SRC = ('        blob = plant.live(rel)\n'
              '        text = blob.decode("utf-8")\n'
              '        newline')
INSERT_OLD = INSERT_SRC.replace("plant.live", "plant.hold")
REPLACE_SRC = ('    blob = plant.live(rel)\n'
               '    text = blob.decode("utf-8")\n'
               '    crlf')
REPLACE_OLD = REPLACE_SRC.replace("plant.live", "plant.hold")

UNREPAIR = ((INSERT_SRC, INSERT_OLD), (REPLACE_SRC, REPLACE_OLD))


def _variant(name, edits, require):
    """A COPY of the tracked machinery in SCRATCH with `edits` applied.

    The tracked file is never written. Unique filename per variant, because
    pyc invalidation is whole-second and two same-size mutations written in
    one second import the previous bytes (pilotcaps/0075).
    """
    if not os.path.isdir(SCRATCH):
        os.makedirs(SCRATCH)
    src = os.path.join(ROOT, MACHINERY_REL)
    with io.open(src, "rb") as handle:
        blob = handle.read()
    text = blob.decode("utf-8")
    crlf = "\r\n" in text
    flat = text.replace("\r\n", "\n")
    for old, new in edits:
        if flat.count(old) != require.get(old, 1):
            raise SystemExit(
                "variant %s: anchor %r occurs %d times, need %d - a plant "
                "that lands nowhere reads as a verdict the row cannot print"
                % (name, old[:48], flat.count(old), require.get(old, 1)))
        flat = flat.replace(old, new)
    out = flat.replace("\n", "\r\n") if crlf else flat
    path = os.path.join(SCRATCH, "machinery-%s-%s.py"
                        % (name, hashlib.sha256(out.encode("utf-8"))
                           .hexdigest()[:10]))
    with io.open(path, "wb") as handle:
        handle.write(out.encode("utf-8"))
    ast.parse(out)
    return path


def unrepaired_copy():
    return _variant("unrepaired", UNREPAIR, {})


# ================================================== C2, the paired mutants

LIVE_BODY = """        self.hold(rel)
        return read_bytes(rel)"""

MUTANTS = (
    ("drop",
     "live answers with the SAVED bytes again - the defect restored",
     ((LIVE_BODY, "        return self.hold(rel)"),), {}),
    ("norevert",
     "live composes correctly but no longer HOLDS the original",
     ((LIVE_BODY, "        return read_bytes(rel)"),), {}),
    ("half",
     "only insert_statements reads live; replace_once sources from hold",
     ((REPLACE_SRC, REPLACE_OLD),), {}),
)


def control_two():
    """C2 - paired mutation of the repaired machinery."""
    print("C2  paired mutants of the repaired machinery")
    tracked = os.path.join(ROOT, MACHINERY_REL)
    before = sha256_file(tracked)
    print("    tracked sha256 at entry  %s" % before)

    ref_head, ref_failed, _ = run_testcase(None, "c2-ref")
    print("    reference (repaired)     %s   failing=%s"
          % (ref_head, ", ".join(sorted(ref_failed)) or "(none)"))

    rows = []
    for name, why, edits, require in MUTANTS:
        path = _variant(name, edits, require)
        head, failed, _ = run_testcase(path, "c2-%s" % name)
        kills = sorted(set(failed) - set(ref_failed))
        rows.append((name, why, head, kills, os.path.basename(path)))
        print("    mutant %-9s %s" % (name, why))
        print("        %s" % head)
        print("        kills %s" % (", ".join(kills) or "(NOTHING)"))

    after = sha256_file(tracked)
    print("    tracked sha256 at exit   %s   IDENTICAL: %s"
          % (after, after == before))

    sets = [frozenset(r[3]) for r in rows]
    nonempty = all(s for s in sets)
    distinct = len(set(sets)) == len(sets)
    ok = (not ref_failed) and nonempty and distinct and after == before
    print("    every kill set non-empty: %s" % nonempty)
    print("    all kill sets different:  %s" % distinct)
    print("    C2 %s" % ("PASS" if ok else "FAIL"))
    write_receipt("c2", dict(
        reference_headline=ref_head,
        reference_failing=sorted(ref_failed),
        mutants=[dict(name=n, why=w, headline=h, kills=k, copy=c)
                 for n, w, h, k, c in rows],
        both_states=bool(ref_head) and all(r[2] for r in rows),
        nonempty=nonempty, distinct=distinct,
        tracked_sha256_before=before, tracked_sha256_after=after,
        passed=bool(ok)))
    return ok


# ======================================== the caller / composition enumerator

def _const_table(tree):
    """Module-level name -> python value, for str and tuple-of-str only."""
    table = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not isinstance(target, ast.Name):
                continue
            try:
                table[target.id] = ast.literal_eval(node.value)
            except (ValueError, SyntaxError, TypeError):
                pass
    return table


def _rel(node, table):
    """The repo-relative path an argument denotes, or None if undecidable."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name):
        value = table.get(node.id)
        return value if isinstance(value, str) else None
    if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name):
        value = table.get(node.value.id)
        index = getattr(node.slice, "value", None)
        if isinstance(value, tuple) and isinstance(index, int):
            element = value[index] if index < len(value) else None
            return element if isinstance(element, str) else None
    return None


def _call_name(call):
    func = call.func
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return None


#: A non-literal edit list whose SOURCE names one of these is built from a
#: set of paths that `resolve` measures by running the instrument that
#: produces it. Statically the list is undecidable; the receipt makes it a
#: measurement rather than an argument.
GENERATORS = (("_bypass_pairs", "bypass_rels"),
              ("bypass_pairs", "bypass_rels"),
              ("consult_edits", "all_site_rels"))


def _generator_tag(node):
    try:
        text = ast.unparse(node)
    except Exception:
        return None
    for needle, tag in GENERATORS:
        if needle in text:
            return tag
    return None


def _targets(call, name, table):
    """[(rel-or-None, note)] the call edits. `note` carries a generator tag
    of the form `@<tag>` where `resolve` can supply the real path set."""
    args = call.args
    if name == "insert_statements":
        if len(args) < 2 or not isinstance(args[1], ast.List):
            tag = _generator_tag(args[1]) if len(args) > 1 else None
            return [(None, "insert_statements(non-literal edit list)"
                     + ("@" + tag if tag else ""))]
        out = []
        for element in args[1].elts:
            if isinstance(element, ast.Tuple) and element.elts:
                out.append((_rel(element.elts[0], table), "edit tuple"))
            else:
                out.append((None, "non-tuple edit"))
        return out or [(None, "empty edit list")]
    if len(args) < 2:
        return [(None, "%s(<2 args)" % name)]
    return [(_rel(args[1], table), "arg1")]


def _plant_functions(tree):
    """name -> FunctionDef, for every def whose FIRST parameter is a plant."""
    out = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = [a.arg for a in node.args.args]
            if args and args[0] == "plant":
                out[node.name] = node
    return out


def _plant_lambdas(tree):
    """[(label, Lambda)] for every `lambda plant: ...` cell.

    0239's matrix passes ELEVEN of its eighteen cells as lambdas. A finder
    that only walks `def`s does not see them at all, which is the dangerous
    direction of a miss: an invisible scope and a scope with nothing to
    compose print the same clean table.
    """
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Lambda):
            args = [a.arg for a in node.args.args]
            if args and args[0] == "plant":
                out.append(("<lambda line %d>" % node.lineno, node))
    return out


def _editor_calls(node, table, plantfns, seen, depth=0):
    """[(order, editor, rel, note)] for one plant scope, following helpers."""
    found = []
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        name = _call_name(child)
        if name in EDITORS:
            for rel, note in _targets(child, name, table):
                found.append((child.lineno, name, rel, note))
        elif name in plantfns and name not in seen and depth < 4:
            inner = plantfns[name]
            found.extend((child.lineno, e, r, n + " via %s()" % name)
                         for _, e, r, n in _editor_calls(
                             inner, table, plantfns, seen | {name}, depth + 1))
    return sorted(found)


def _expand(calls, resolved):
    """Substitute a measured path set for a tagged non-literal edit list.

    `resolved` is `resolve`'s receipt. Without it a tagged target stays None
    and the scope stays UNKNOWN - the gate is that a measurement, not an
    argument, is what moves a row off UNKNOWN.
    """
    out, used = [], []
    for line, editor, rel, note in calls:
        #: The tag ends at the first space: a target reached through a helper
        #: carries " via <fn>()" after it, and splitting on "@" alone made
        #: every tagged target through a helper unresolvable - three rows
        #: stayed UNKNOWN with the measurement sitting in the receipt.
        tag = (note.split("@", 1)[1].split(" ")[0]
               if rel is None and "@" in note else None)
        paths = (resolved or {}).get(tag) if tag else None
        if paths is None:
            out.append((line, editor, rel, note))
            continue
        used.append(tag)
        for path in paths:
            out.append((line, editor, path, note))
    return sorted(out), sorted(set(used))


def _classify(calls):
    """(verdict, reason). AFFECTED only where a CLOBBERING editor follows
    another edit to the SAME file under the same Plant.

    The order matters and is checked FIRST: a scope with one editor call has
    nothing to compose, whether or not its target is decidable, so it is
    UNAFFECTED and not UNKNOWN. Getting that backwards made four single-call
    scopes read UNKNOWN on this harness's first run.
    """
    if len(calls) < 2:
        return "UNAFFECTED", "a single editor call - nothing to compose"
    if any(rel is None for _, _, rel, _ in calls):
        return "UNKNOWN", ("a target path is not statically decidable and no "
                           "measurement supplied it: %s"
                           % ", ".join(sorted(set(
                               n for _, _, r, n in calls if r is None))))
    losses = []
    for index, (line, editor, rel, _) in enumerate(calls):
        if editor not in CLOBBERING_EDITORS:
            continue
        earlier = [c for c in calls[:index] if c[2] == rel]
        if earlier:
            losses.append("%s at line %d clobbers %s at line %d on %s"
                          % (editor, line, earlier[-1][1], earlier[-1][0], rel))
    if losses:
        return "AFFECTED", "; ".join(losses)
    files = sorted(set(rel for _, _, rel, _ in calls))
    return "UNAFFECTED", ("%d editor call(s) over %d distinct file(s), no "
                          "clobbering order: %s"
                          % (len(calls), len(files), ", ".join(files)))


def _row(origin, scope, calls, resolved):
    expanded, used = _expand(calls, resolved)
    verdict, reason = _classify(expanded)
    if used:
        reason += " [paths for %s supplied by the `resolve` receipt]" % (
            ", ".join(used))
    return dict(origin=origin, scope=scope, calls=len(calls),
                verdict=verdict, reason=reason,
                detail=["%s:%d %s" % (e, l, r) for l, e, r, _ in expanded])


def _plant_builds(node):
    """[(lineno, varname-or-None)] for every `Plant(...)` built in a scope."""
    out = []
    for child in ast.walk(node):
        if isinstance(child, ast.Assign) and isinstance(child.value, ast.Call) \
                and _call_name(child.value) == "Plant":
            names = [t.id for t in child.targets if isinstance(t, ast.Name)]
            out.append((child.lineno, names[0] if len(names) == 1 else None))
        elif isinstance(child, ast.Call) and _call_name(child) == "Plant":
            if not any(line == child.lineno for line, _ in out):
                out.append((child.lineno, None))
    return sorted(out)


def composed_sites(source, origin, resolved=None):
    """[row] for one caller source - one row per PLANT SCOPE."""
    tree = ast.parse(source)
    table = _const_table(tree)
    plantfns = _plant_functions(tree)
    rows = []
    for name in sorted(plantfns):
        calls = _editor_calls(plantfns[name], table, plantfns, {name})
        if calls:
            rows.append(_row(origin, name, calls, resolved))
    for label, node in _plant_lambdas(tree):
        calls = _editor_calls(node, table, plantfns, set())
        if calls:
            rows.append(_row(origin, label, calls, resolved))
    #: Scopes that BUILD a Plant themselves rather than receiving one. Several
    #: build MORE THAN ONE in sequence (`plant = Plant("C2 ...")` then
    #: `plant = Plant("C3 ...")`), and attributing all their edits to one
    #: Plant invents a composition that does not exist. Split by the nearest
    #: PRECEDING construction of the same variable; refuse (UNKNOWN) if the
    #: constructions are not simple single-name assignments.
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name in plantfns:
            continue
        builds = _plant_builds(node)
        if not builds:
            continue
        calls = _editor_calls(node, table, plantfns, {node.name})
        if not calls:
            continue
        if len(builds) == 1:
            rows.append(_row(origin, node.name, calls, resolved))
            continue
        if any(name is None for _, name in builds):
            rows.append(dict(
                origin=origin, scope=node.name, calls=len(calls),
                verdict="UNKNOWN",
                reason="%d Plant objects in one scope and at least one is not "
                       "a simple assignment, so which edit belongs to which "
                       "is not decidable statically" % len(builds),
                detail=["%s:%d %s" % (e, l, r) for l, e, r, _ in calls]))
            continue
        for index, (line, name) in enumerate(builds):
            end = builds[index + 1][0] if index + 1 < len(builds) else 10 ** 9
            mine = [c for c in calls if line < c[0] < end]
            if not mine:
                continue
            rows.append(_row(origin, "%s/Plant@%d(%s)"
                             % (node.name, line, name), mine, resolved))
    return rows


# ================================================= C3, the finder can miss

SEEN_SHAPE = '''

def _c3_seen_shape(plant):
    R.insert_statements(plant, [("tests/c3_seen.py", "test_a", "pass", False)])
    R.insert_statements(plant, [("tests/c3_seen.py", "test_a", "pass", False)])
'''

MISSED_INDIRECT = '''

def _c3_missed_step(plant, which):
    R.insert_statements(plant, [("tests/c3_missed.py", "test_a", which, False)])


def _c3_missed_shape(plant):
    for which in ("one", "two"):
        _c3_missed_step(plant, which)
'''

MISSED_GETATTR = '''

def _c3_missed_getattr(plant):
    getattr(R, "insert_" + "statements")(
        plant, [("tests/c3_getattr.py", "test_a", "one", False)])
    getattr(R, "insert_" + "statements")(
        plant, [("tests/c3_getattr.py", "test_a", "two", False)])
'''


def control_three():
    """C3 - plant callers the finder does, and does not, look for."""
    print("C3  the caller/composition finder, shown able to MISS")
    corpus_rel = os.path.join("scripts", "exit_rows_two_and_five.py")
    path = os.path.join(ROOT, corpus_rel)
    before = sha256_file(path)
    with io.open(path, encoding="utf-8") as handle:
        base = handle.read()

    def count(source, tag):
        rows = composed_sites(source, tag)
        affected = [r for r in rows if r["verdict"] == "AFFECTED"]
        return len(rows), len(affected), [r["scope"] for r in affected]

    base_rows, base_aff, base_names = count(base, "base")
    print("    base                      scopes=%d affected=%d %s"
          % (base_rows, base_aff, base_names))

    rows = []
    for name, plant, expect in (
            ("seen: two literal calls, one scope", SEEN_SHAPE, True),
            ("missed: two calls via a helper", MISSED_INDIRECT, False),
            ("missed: getattr-assembled name", MISSED_GETATTR, False)):
        n_rows, n_aff, names = count(base + plant, name)
        found = n_aff > base_aff
        rows.append(dict(shape=name, scopes=n_rows, affected=n_aff,
                         affected_names=names, found=found, expected=expect))
        print("    %-34s scopes=%d affected=%d  FOUND: %s"
              % (name, n_rows, n_aff, "YES" if found else "NO"))

    after = sha256_file(path)
    print("    corpus sha256 identical:  %s  (every plant was a COPY in memory)"
          % (after == before))
    seen = [r for r in rows if r["found"]]
    missed = [r for r in rows if not r["found"]]
    both = bool(seen) and bool(missed)
    print("    the finder found %d shape(s) and MISSED %d" % (len(seen),
                                                              len(missed)))
    print("    so the denominator is a FLOOR: %s" % (True if missed else False))
    print("    C3 %s" % ("PASS" if both and after == before else "FAIL"))
    write_receipt("c3", dict(shapes=rows, both_states=both,
                             floor=bool(missed),
                             corpus_sha256_before=before,
                             corpus_sha256_after=after,
                             passed=bool(both and after == before)))
    return both and after == before


# ====================================================== the blast radius

CALLER_SOURCES = (os.path.join("scripts", "exit_nine_reachability.py"),
                  os.path.join("scripts", "exit_rows_two_and_five.py"),
                  os.path.join("scripts", "exit_nine_pins.py"),
                  os.path.join("scripts", "exit_pins_controls.py"))


def git(args):
    proc = subprocess.run(["git"] + args, cwd=ROOT, capture_output=True,
                          env=dict(os.environ, GIT_CONFIG_COUNT="0"))
    return proc.returncode, proc.stdout.decode("utf-8", "replace")


# ================================ the A/B: no behaviour change for one touch

def control_ab():
    """Every REAL single-touch plant, applied twice, byte-compared.

    The repair's whole claim to being surgical is that for the FIRST edit to
    a file `live` and `hold` answer identically, so no existing single-plant
    caller moves. That is a claim about bytes, so it is measured on the real
    corpus rather than argued from the diff: the two big plants 0239 and 0243
    actually run (a consult on all 58 write-path sites, 30 files; a door on
    all 26 bypasses, 10 files) are applied under the UNREPAIRED and the
    REPAIRED machinery in turn, and every touched file is hashed.

    WRITES TRACKED FILES, so it refuses unless PC0247_ALLOW_TREE_WRITES=1.
    Run it in a throwaway tree only.
    """
    print("AB  no behaviour change for a single-touch plant, on real bytes")
    if os.environ.get("PC0247_ALLOW_TREE_WRITES") != "1":
        print("    REFUSED. This mode plants into TRACKED files to compare "
              "bytes. Set PC0247_ALLOW_TREE_WRITES=1 and run it in a "
              "throwaway tree. A refusal is the fail-closed answer; it is "
              "not a pass.")
        return False

    repaired = os.environ.get("PC0247_REPAIRED",
                              os.path.join(ROOT, MACHINERY_REL))
    unrepaired = os.environ.get("PC0247_UNREPAIRED",
                                os.path.join(ROOT, MACHINERY_REL))
    print("    unrepaired %s  %s" % (sha256_file(unrepaired)[:16], unrepaired))
    print("    repaired   %s  %s" % (sha256_file(repaired)[:16], repaired))

    def load(path, tag):
        spec = importlib.util.spec_from_file_location("pc0247_ab_%s" % tag,
                                                      path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.ROOT = ROOT
        return module

    def once(path, tag, build):
        R = load(path, tag)
        plant = R.Plant("0247 AB %s %s" % (tag, build))
        edits = PLANTS[build](R)
        R.insert_statements(plant, edits)
        touched = sorted(set(rel for rel, _, _, _ in edits))
        digests = dict((rel, sha256_file(os.path.join(ROOT, rel)))
                       for rel in touched)
        proof = plant.revert()
        return digests, all(p[3] for p in proof), len(proof)

    ok = True
    for build in sorted(PLANTS):
        a, a_rev, a_n = once(unrepaired, "old_%s" % build, build)
        b, b_rev, b_n = once(repaired, "new_%s" % build, build)
        same = a == b
        differing = sorted(k for k in a if a.get(k) != b.get(k))
        print("    %-18s files=%-3d reverted(old/new)=%s/%s  "
              "BYTE-IDENTICAL: %s"
              % (build, len(a), a_rev, b_rev, same))
        if differing:
            print("        DIFFERING: %s" % ", ".join(differing))
        ok = ok and same and a_rev and b_rev and a_n == b_n
    print("    AB %s" % ("PASS" if ok else "FAIL"))
    write_receipt("ab", dict(passed=bool(ok), both_states=True))
    return ok


def _consult_all(R):
    pairs = sorted(set((rel, where) for rel, where, _ in R.write_sites()))
    return R.consult_edits(pairs)


def _door_bypasses(R):
    sites = R.write_sites()
    pairs = sorted(set((rel, where) for rel, where, verdict in sites
                       if verdict == "BYPASS"))
    return [(rel, where, R.DOOR_STMT, True) for rel, where in pairs]


PLANTS = {"consult_all_58": _consult_all,
          "door_26_bypasses": _door_bypasses}


DENOMINATOR = os.path.join("scripts", "write_path_denominator.py")


def resolve():
    """Measure the path sets the non-literal edit lists are built from.

    Runs `write_path_denominator` - the same instrument the callers run - and
    records WHICH FILES the 26 BYPASS sites and all 58 write-path sites live
    in. That is what decides whether a later literal plant into a tests/ file
    can clobber an earlier one, and it is a measurement rather than a reading
    of the code.
    """
    print("RESOLVE  the path sets behind the non-literal edit lists")
    path = os.path.join(ROOT, DENOMINATOR)
    print("    instrument        %s" % DENOMINATOR)
    print("    instrument sha256 %s" % sha256_file(path))
    spec = importlib.util.spec_from_file_location("pc0247_den", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    writers = module.mutating_functions(ROOT)
    sites = list(module.call_sites(ROOT, writers))
    norm = lambda rel: rel.replace(os.sep, "/")
    all_rels = sorted(set(norm(rel) for _, rel, _, _, _ in sites))
    bypass_rels = sorted(set(norm(rel) for verdict, rel, _, _, _ in sites
                             if verdict == "BYPASS"))
    print("    write-path sites  %d  (BYPASS %d)"
          % (len(sites), sum(1 for v, _, _, _, _ in sites if v == "BYPASS")))
    print("    all_site_rels     %d files" % len(all_rels))
    print("    bypass_rels       %d files" % len(bypass_rels))
    for rel in bypass_rels:
        print("        %s" % rel)
    under_tests = [r for r in all_rels if r.startswith("tests/")]
    print("    any site under tests/ : %s"
          % (", ".join(under_tests) or "NONE - so a later literal plant into "
                                       "a tests/ file cannot clobber one of "
                                       "these"))
    write_receipt("resolve", dict(all_site_rels=all_rels,
                                  bypass_rels=bypass_rels,
                                  sites=len(sites),
                                  under_tests=under_tests,
                                  instrument=DENOMINATOR,
                                  instrument_sha256=sha256_file(path),
                                  both_states=True, passed=True))
    return True


_REFS_CACHE = []


def refs_with_callers():
    """[(branch, [caller rel])] for every local branch carrying one.

    Memoised, and ONE `ls-tree` per ref rather than one `cat-file -e` per
    (ref, path): the unmemoised four-calls-per-ref form issued ~3,600 git
    subprocesses over this repository's 300-odd branches and did not finish
    inside two minutes.
    """
    if _REFS_CACHE:
        return _REFS_CACHE[0]
    code, out = git(["for-each-ref", "--format=%(refname:short)", "refs/heads"])
    wanted = set(rel.replace(os.sep, "/") for rel in CALLER_SOURCES)
    found = []
    for name in out.split():
        code, listing = git(["ls-tree", "--name-only", "%s:scripts" % name])
        if code != 0:
            continue
        have = set("scripts/" + line.strip() for line in listing.splitlines())
        rels = sorted(wanted & have)
        if rels:
            found.append((name, rels))
    _REFS_CACHE.append(found)
    return found


def census():
    """C4-gated. The blast-radius table over every ref carrying the machinery."""
    gate = {}
    for name in ("c1", "c2", "c3"):
        data = read_receipt(name) or {}
        gate[name] = bool(data.get("both_states"))
    print("C4  self-check before the table is printed")
    for name in ("c1", "c2", "c3"):
        print("    %s printed both of its states: %s" % (name.upper(),
                                                         gate[name]))
    if not all(gate.values()):
        print("    REFUSED. The blast-radius table is NOT printed: %s did not "
              "print both states. UNAFFECTED is the dangerous wrong answer "
              "here, so an unwitnessed table is worse than none."
              % ", ".join(n.upper() for n in sorted(gate) if not gate[n]))
        return False
    print("    C4 PASS - printing the table")
    print("")

    resolved = read_receipt("resolve")
    if resolved:
        print("    path sets from the `resolve` receipt, measured by %s @ %s"
              % (resolved["instrument"], resolved["instrument_sha256"][:16]))
    else:
        print("    NO `resolve` receipt - every non-literal edit list stays "
              "UNKNOWN, which is the fail-closed answer, not a missing one.")
    print("")

    rows = []
    for ref, rels in refs_with_callers():
        for rel in rels:
            code, source = git(["show", "%s:%s" % (ref, rel.replace(os.sep,
                                                                    "/"))])
            if code != 0:
                rows.append(dict(origin=ref, source=rel, scope="-", calls=0,
                                 verdict="UNKNOWN",
                                 reason="git could not read it", detail=[]))
                continue
            if "insert_statements" not in source \
                    and "replace_once" not in source:
                rows.append(dict(origin=ref, source=rel, scope="(not a "
                                 "caller)", calls=0, verdict="UNAFFECTED",
                                 reason="names the machinery as a corpus PATH "
                                        "only; imports no editor from it",
                                 detail=[]))
                continue
            code, blob = git(["rev-parse", "%s:%s"
                              % (ref, rel.replace(os.sep, "/"))])
            found = composed_sites(source, ref, resolved)
            for row in found:
                row["source"] = rel
                row["blob"] = blob.strip()[:12]
            rows.extend(found)


    print("THE BLAST-RADIUS TABLE")
    print("one row per PLANT SCOPE - the unit a single Plant object covers")
    print("")
    for ref, _ in refs_with_callers():
        mine = [r for r in rows if r["origin"] == ref]
        if not mine:
            continue
        print("  %s" % ref)
        for source in sorted(set(r["source"] for r in mine)):
            blobs = sorted(set(r.get("blob") or "-"
                               for r in mine if r["source"] == source))
            print("    %s   blob %s" % (source, ", ".join(blobs)))
            for row in [r for r in mine if r["source"] == source]:
                print("      %-34s %-5s %s" % (row["scope"], row["calls"],
                                               row["verdict"]))
    print("")
    tally = {}
    for row in rows:
        tally[row["verdict"]] = tally.get(row["verdict"], 0) + 1
    composed = [r for r in rows if r["calls"] >= 2]
    #: Three denominators, because they answer three different questions and
    #: this estate has corrected four hand-kept ones in two days. The big one
    #: counts the same bytes once per branch; the distinct ones do not.
    distinct_scopes = sorted(set((r["source"], r["scope"]) for r in composed))
    distinct_blobs = sorted(set((r["source"], r.get("blob"))
                                for r in rows if r.get("blob")))
    print("plant scopes found, counted once per ref          %d" % len(rows))
    print("COMPOSED plants (>=2 editor calls on one Plant)   %d" % len(composed))
    print("  ... of which DISTINCT (source, scope) pairs     %d"
          % len(distinct_scopes))
    print("  ... over DISTINCT (source, blob) pairs          %d"
          % len(distinct_blobs))
    for verdict in sorted(tally):
        print("  %-11s %d" % (verdict, tally[verdict]))
    if tally.get("AFFECTED", 0) == 0 and tally.get("UNKNOWN", 0) == 0:
        print("")
        print("  EVERY ROW READS UNAFFECTED, WHICH IS THE DANGEROUS ANSWER "
              "HERE. It is only worth anything beside C3, which planted a "
              "clobbering composition into THIS corpus and watched this same "
              "finder print AFFECTED for it. Without that, an all-UNAFFECTED "
              "table and a finder that reads nothing are the same table.")
    print("")
    print("EVERY COMPOSED PLANT, with the reason:")
    for row in composed:
        print("  %s :: %s :: %s" % (row["origin"], row["source"],
                                    row["scope"]))
        print("      %-11s %s" % (row["verdict"], row["reason"]))
        for line in row["detail"]:
            print("          %s" % line)
    print("")
    print("THE DENOMINATOR IS A FLOOR. C3 measured this finder missing two "
          "caller shapes it does not look for (an editor reached through a "
          "helper inside a loop, and an editor named by getattr), and this "
          "census reads committed git refs only - an uncommitted harness in "
          "another lane's worktree is outside it by boundary, not by "
          "measurement.")
    write_receipt("census", dict(rows=rows, composed=len(composed),
                                 tally=tally, floor=True,
                                 resolve_used=bool(resolved)))
    return True


# ============================================================== entry point

def main(argv):
    mode = argv[1] if len(argv) > 1 else "all"
    if mode == "_unittest":
        unittest.main(argv=[argv[0], "-v", "APlantComposes"], exit=True)
        return 0
    if not os.path.isdir(SCRATCH):
        os.makedirs(SCRATCH)
    tracked = os.path.join(ROOT, MACHINERY_REL)
    opening = sha256_file(tracked)
    print("TASK-0247  plant-composition controls")
    print("ROOT     %s" % ROOT)
    print("SCRATCH  %s" % SCRATCH)
    print("machinery sha256 at open  %s" % opening)
    print("")
    ok = True
    if mode in ("test", "all"):
        ok = control_one() and ok
        print("")
    if mode in ("mutate", "all"):
        ok = control_two() and ok
        print("")
    if mode in ("c3", "all"):
        ok = control_three() and ok
        print("")
    if mode == "ab":
        ok = control_ab() and ok
        print("")
    if mode in ("resolve", "all"):
        ok = resolve() and ok
        print("")
    if mode in ("census", "all"):
        ok = census() and ok
        print("")
    closing = sha256_file(tracked)
    print("machinery sha256 at close %s  IDENTICAL: %s"
          % (closing, closing == opening))
    return 0 if (ok and closing == opening) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
