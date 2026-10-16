# -*- coding: utf-8 -*-
"""TASK-0239 - the row-by-row reachability matrix for scripts/exit_nine.py.

For each of the nine CANARY-01 exit criteria, two cells: CAN THIS ROW PRINT MET
and CAN THIS ROW PRINT NOT MET. Each cell is answered by a PLANT that forces
the state, never by reading the code and arguing. A row that cannot print one
of the two is not an instrument for its criterion and is named as such.

Run from a THROWAWAY tree only. Every plant is reverted by writing the saved
bytes back and proven reverted by the working file's own sha256 - never by
`git status` or `git diff`, because pilotcaps/0234c measured a plain
`git checkout --` converting CRLF to LF and leaving the tree reading clean.

    py -3 -B scripts/exit_nine_reachability.py controls   C1, C2, C3 only
    py -3 -B scripts/exit_nine_reachability.py matrix     all eighteen cells
    py -3 -B scripts/exit_nine_reachability.py extra      the isolating cells
    py -3 -B scripts/exit_nine_reachability.py mutate-met C4, in a throwaway

TASK-0239. Its measured output is
`resonate-ops/EXIT-NINE-REACHABILITY-MATRIX-2026-10-16.md`.
"""
import ast
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile

ROOT = os.getcwd()
EXIT_NINE = os.path.join("scripts", "exit_nine.py")
#: OUTSIDE the tree, always. An earlier harness in this estate resolved its
#: output path relative to its own file, was then run from inside a checkout,
#: and had its stray json charged to the change by test_fixture_hygiene. The
#: scratch authorities criteria 6 and 8 are pointed at live here, so they must
#: not be inside the tree under measurement either.
SCRATCH = os.environ.get(
    "EXIT_NINE_REACH_SCRATCH",
    os.path.join(tempfile.gettempdir(), "exit-nine-reachability"))
PLANT_TAG = "TASK-0239 plant"


# ------------------------------------------------------------------ bytes

def read_bytes(rel):
    with io.open(os.path.join(ROOT, rel), "rb") as handle:
        return handle.read()


def write_bytes(rel, blob):
    with io.open(os.path.join(ROOT, rel), "wb") as handle:
        handle.write(blob)


def digest(blob):
    return hashlib.sha256(blob).hexdigest()


class Plant(object):
    """A set of file edits, reverted and PROVEN reverted by sha256."""

    def __init__(self, label):
        self.label = label
        self.saved = {}

    def hold(self, rel):
        if rel not in self.saved:
            self.saved[rel] = read_bytes(rel)
        return self.saved[rel]

    def revert(self):
        proof = []
        for rel, blob in sorted(self.saved.items()):
            write_bytes(rel, blob)
            back = read_bytes(rel)
            proof.append((rel, digest(blob), digest(back),
                          digest(blob) == digest(back)))
        return proof


# ------------------------------------------------------------------ editing

def _plain_test(node):
    """A test method with no expectedFailure / skip decorator on it."""
    if not node.name.startswith("test_"):
        return False
    for dec in node.decorator_list:
        text = ast.dump(dec)
        if "expectedFailure" in text or "skip" in text:
            return False
    return True


def _insert_points(source, name, toplevel):
    """(line_index, col) for the first real statement of each matching def.

    `name=None` means "the first undecorated test_* method in the file" - used
    where the cell only needs SOME test in a module to go red.
    """
    tree = ast.parse(source)
    pool = (tree.body if toplevel else list(ast.walk(tree)))
    defs = [n for n in pool
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    if name is None:
        candidates = [n for n in defs if _plain_test(n)][:1]
    else:
        candidates = [n for n in defs if n.name == name]
    points = []
    for node in candidates:
        first = node.body[0]
        is_doc = (isinstance(first, ast.Expr)
                  and isinstance(first.value, ast.Constant)
                  and isinstance(first.value.value, str))
        if is_doc and len(node.body) > 1:
            line = node.body[1].lineno
            col = node.body[1].col_offset
        elif is_doc:
            line = first.end_lineno + 1
            col = first.col_offset
        else:
            line = first.lineno
            col = first.col_offset
        points.append((line - 1, col))
    return points


def insert_statements(plant, edits):
    """edits: [(rel, funcname, statement, toplevel)]. Bottom-up per file."""
    grouped = {}
    for rel, func, stmt, toplevel in edits:
        grouped.setdefault(rel, []).append((func, stmt, toplevel))
    touched = []
    for rel, items in sorted(grouped.items()):
        blob = plant.hold(rel)
        text = blob.decode("utf-8")
        newline = "\r\n" if "\r\n" in text else "\n"
        lines = text.replace("\r\n", "\n").split("\n")
        points = []
        for func, stmt, toplevel in items:
            found = _insert_points("\n".join(lines), func, toplevel)
            if not found:
                raise SystemExit("plant %s: no def %r in %s - a plant that "
                                 "silently lands nowhere is the defect this "
                                 "harness exists to find"
                                 % (plant.label, func, rel))
            for index, col in found:
                points.append((index, col, stmt))
        for index, col, stmt in sorted(points, reverse=True):
            lines.insert(index, " " * col + stmt)
        out = newline.join(lines).encode("utf-8")
        write_bytes(rel, out)
        touched.append((rel, len(points)))
    return touched


def replace_once(plant, rel, old, new):
    """Line-ending-agnostic single replacement.

    The first version of this matched a literal "\\n" against a CRLF config and
    found 0 occurrences - a plant that lands nowhere, which is the shape this
    harness exists to catch, caught in the harness itself.
    """
    blob = plant.hold(rel)
    text = blob.decode("utf-8")
    crlf = "\r\n" in text
    flat = text.replace("\r\n", "\n")
    if flat.count(old) != 1:
        raise SystemExit("plant %s: %r occurs %d times in %s, need exactly 1"
                         % (plant.label, old[:40], flat.count(old), rel))
    out = flat.replace(old, new, 1)
    if crlf:
        out = out.replace("\n", "\r\n")
    write_bytes(rel, out.encode("utf-8"))


# ------------------------------------------------------------------ running

def row(number, env=None):
    """Evaluate one criterion and return its row dict."""
    environ = dict(os.environ)
    if env:
        environ.update(env)
    proc = subprocess.run(
        [sys.executable, "-B", EXIT_NINE, "--only", str(number), "--json"],
        cwd=ROOT, capture_output=True, text=True, env=environ, timeout=1800)
    try:
        payload = json.loads(proc.stdout)
    except ValueError:
        return dict(number=number, verdict="(UNPARSEABLE)",
                    denominator=proc.stdout[-400:] + proc.stderr[-400:],
                    condition="exit %d" % proc.returncode)
    return payload["rows"][0]


# ------------------------------------------------------------------ the sites

def write_sites():
    """[(rel, enclosing_function, door_verdict)] for every provider write."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "pc0239_denominator", os.path.join(ROOT, "scripts",
                                           "write_path_denominator.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    writers = module.mutating_functions(ROOT)
    return [(rel, where, verdict)
            for verdict, rel, line, call, where in module.call_sites(ROOT, writers)]


def consult_report():
    proc = subprocess.run(
        [sys.executable, "-B",
         os.path.join("scripts", "suppression_on_every_write_path.py"), "."],
        cwd=ROOT, capture_output=True, text=True, timeout=1800)
    return proc.returncode, proc.stdout


def no_consult_functions():
    """[(rel, where)] for the paths the instrument reports as unconsulted."""
    _, out = consult_report()
    found = []
    for line in out.splitlines():
        if not line.strip().startswith("NO CONSULT"):
            continue
        tail = line.split("]", 1)[1].strip()
        where = tail.rsplit(" in ", 1)[1].rstrip("()")
        rel = tail.split(":", 1)[0]
        found.append((rel, where))
    return found


CONSULT_STMT = 'if False: suppression.decide("%s")' % PLANT_TAG
DOOR_STMT = 'if False: perform("%s")' % PLANT_TAG


def consult_edits(pairs):
    return [(rel, where, CONSULT_STMT, True)
            for rel, where in sorted(set(pairs))]


# ------------------------------------------------------------------ scratch

def scratch(name, text):
    if not os.path.isdir(SCRATCH):
        os.makedirs(SCRATCH)
    path = os.path.join(SCRATCH, name)
    with io.open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    return path


def estate_csv(name, connected_all, bounces):
    head = "Email,Status,Emails Sent,Bounces,Opens\n"
    rows = []
    for index in range(3):
        status = "Connected"
        if not connected_all and index == 1:
            status = "Disconnected"
        rows.append("m%d@example.test,%s,1000,%d,0\n"
                    % (index, status, bounces if index == 0 else 0))
    return scratch(name, head + "".join(rows))


# ------------------------------------------------------------------ cells

def cell(label, expect, verdict, extra=""):
    ok = verdict == expect
    print("    %-34s -> %-9s  expected %-9s  %s %s"
          % (label, verdict, expect, "OK" if ok else "MISMATCH", extra))
    return ok


def controls():
    """C1, C2 and C3. Returns a dict of control -> (pass/fail, detail)."""
    out = {}

    print("C1  the wired row against the tree as it stands")
    got = row(1)
    c1 = (got["verdict"] == "NOT MET"
          and "21 of 58" in got["denominator"])
    print("    verdict %s" % got["verdict"])
    print("    denom   %s" % got["denominator"])
    print("    C1 %s" % ("PASS" if c1 else "FAIL"))
    out["C1"] = (c1, got["verdict"], got["denominator"])

    print("C2  a suppression consult planted on every one of the 58 paths")
    sites = write_sites()
    pairs = sorted(set((rel, where) for rel, where, _ in sites))
    plant = Plant("C2 all 58")
    try:
        touched = insert_statements(plant, consult_edits(pairs))
        code, report = consult_report()
        line = [l for l in report.splitlines() if "NO SUPPRESSION" in l]
        print("    planted into %d functions across %d files, %d sites"
              % (sum(n for _, n in touched), len(touched), len(sites)))
        print("    instrument exit %d  |  %s" % (code, line[0] if line else "?"))
        got = row(1)
        c2 = got["verdict"] == "MET"
        print("    verdict %s" % got["verdict"])
        print("    denom   %s" % got["denominator"])
        print("    C2 %s" % ("PASS" if c2 else "FAIL"))
        out["C2"] = (c2, got["verdict"], got["denominator"])
    finally:
        proof = plant.revert()
        print("    revert: %d file(s), sha256 identical: %s"
              % (len(proof), all(p[3] for p in proof)))
        out["C2_revert"] = proof

    print("C3  a consult planted on exactly ONE unconsulted path")
    unconsulted = no_consult_functions()
    one = sorted(set(unconsulted))[0]
    plant = Plant("C3 one path")
    try:
        insert_statements(plant, consult_edits([one]))
        code, report = consult_report()
        line = [l for l in report.splitlines() if "NO SUPPRESSION" in l]
        got = row(1)
        moved = "20 of 58" in got["denominator"]
        c3 = moved and got["verdict"] == "NOT MET"
        print("    planted at %s:%s()" % one)
        print("    instrument exit %d  |  %s" % (code, line[0] if line else "?"))
        print("    verdict %s" % got["verdict"])
        print("    denom   %s" % got["denominator"])
        print("    C3 %s" % ("PASS" if c3 else "FAIL"))
        out["C3"] = (c3, got["verdict"], got["denominator"])
    finally:
        proof = plant.revert()
        print("    revert: %d file(s), sha256 identical: %s"
              % (len(proof), all(p[3] for p in proof)))
        out["C3_revert"] = proof
    return out


SIGNED_NOTE = ("Hi {FIRST_NAME}, saw Productive would fit how you run "
               "delivery - worth a look?")

EMDASH_TEST = "test_an_em_dash_is_normalised_rather_than_spending_an_attempt"

BRAKE_REDS = [
    ("tests/test_the_stop_sending_brake_fails_closed_when_it_cannot_be_read.py",
     "test_an_unreadable_brake_refuses_the_transport"),
    ("tests/test_the_stop_sending_brake_refuses_the_transport_immediately.py",
     "test_no_file_and_the_transport_is_reached"),
    ("tests/test_the_stop_sending_brake_refuses_the_transport_immediately.py",
     "test_the_file_present_refuses_and_the_transport_is_unreached"),
    ("tests/test_the_stop_sending_brake_refuses_the_transport_immediately.py",
     "test_the_refusal_is_ledgered_as_refused_not_failed"),
    ("tests/test_the_stop_sending_brake_refuses_the_transport_immediately.py",
     "test_the_brake_pulled_after_the_last_gate_still_refuses"),
]

FAIL_STMT = 'self.fail("%s")' % PLANT_TAG
SKIP_STMT = 'self.skipTest("%s")' % PLANT_TAG

NOTE_BLOCK_OLD = ('"messages": [\n      ""\n     ],\n'
                  '     "fallbackMessage": "",')
LI_CONFIG = "config/linkedin/productive-standard.json"


def note_block_new(text):
    return ('"messages": [\n      "%s"\n     ],\n'
            '     "fallbackMessage": "%s",' % (text, text))


def plant_cell(label, number, build, expect, env=None):
    """Apply a plant, evaluate one row, revert, prove the revert."""
    plant = Plant(label)
    verdict, denominator, condition = "(not run)", "", ""
    try:
        build(plant)
        got = row(number, env=env)
        verdict = got["verdict"]
        denominator = got["denominator"]
        condition = got["condition"]
    except SystemExit as refused:
        #: A plant that cannot land is recorded LOUDLY as its own cell rather
        #: than aborting the other seventeen - but it is never recorded as a
        #: verdict, because "the plant did not land" and "the row answered" are
        #: different facts and collapsing them is failure family 6.
        verdict = "(PLANT DID NOT LAND)"
        condition = str(refused)
    finally:
        proof = plant.revert()
    ok = cell(label, expect, verdict)
    return dict(label=label, number=number, expect=expect, verdict=verdict,
                ok=ok, denominator=denominator, condition=condition,
                revert=[(p[0], p[1], p[3]) for p in proof])


def matrix():
    results = []
    noop = lambda plant: None

    print("criterion 1 - a suppressed address cannot reach the transport by any path")
    results.append(plant_cell("1 NOT MET: tree as it stands", 1, noop, "NOT MET"))
    sites = write_sites()
    all_pairs = sorted(set((rel, where) for rel, where, _ in sites))
    results.append(plant_cell(
        "1 MET: consult on all 58 paths", 1,
        lambda plant: insert_statements(plant, consult_edits(all_pairs)), "MET"))

    print("criterion 2 - a removal request writes a suppression row, demonstrated")
    results.append(plant_cell("2 MET: tree as it stands", 2, noop, "MET"))
    results.append(plant_cell(
        "2 NOT MET: demonstration FAILs", 2,
        lambda plant: insert_statements(plant, [(
            "tests/test_a_suppressed_address_cannot_reach_a_provider.py",
            "test_an_attributed_removal_request_writes_a_suppression_row",
            FAIL_STMT, False)]), "NOT MET"))

    print("criterion 3 - li1 renders a real connection note; RED if empty")
    results.append(plant_cell("3 NOT MET: tree as it stands", 3, noop, "NOT MET"))
    results.append(plant_cell(
        "3 MET: a REAL note at the node", 3,
        lambda plant: replace_once(plant, LI_CONFIG, NOTE_BLOCK_OLD,
                                   note_block_new(SIGNED_NOTE)), "MET"))

    def placeholder_plant(plant):
        replace_once(plant, LI_CONFIG, NOTE_BLOCK_OLD,
                     note_block_new("{connection_note}"))
        insert_statements(plant, [("tests/test_linkedin_note.py",
                                   EMDASH_TEST, SKIP_STMT, False)])

    results.append(plant_cell(
        "3 MET: the PLACEHOLDER token", 3, placeholder_plant, "MET"))

    print("criterion 4 - every template passes the ceiling and the floor")
    results.append(plant_cell("4 MET: tree as it stands", 4, noop, "MET"))
    results.append(plant_cell(
        "4 NOT MET: one template test FAILs", 4,
        lambda plant: insert_statements(plant, [(
            "tests/test_no_template_escapes_the_word_contract.py",
            None, FAIL_STMT, False)]), "NOT MET"))

    print("criterion 5 - zero write paths bypass the gate")
    results.append(plant_cell("5 NOT MET: tree as it stands", 5, noop, "NOT MET"))
    bypass_pairs = sorted(set((rel, where) for rel, where, verdict in sites
                              if verdict == "BYPASS"))
    results.append(plant_cell(
        "5 MET: a door on all 26 bypasses", 5,
        lambda plant: insert_statements(
            plant, [(rel, where, DOOR_STMT, True)
                    for rel, where in bypass_pairs]), "MET"))

    print("criterion 6 - mailbox health from the estate export")
    results.append(plant_cell("6 UNKNOWN: tree as it stands", 6, noop, "UNKNOWN"))
    healthy = estate_csv("pc0239-estate-healthy.csv", True, 5)
    sick = estate_csv("pc0239-estate-disconnected.csv", False, 5)
    results.append(plant_cell("6 MET: all Connected, 0.17%", 6, noop, "MET",
                              env=dict(EXIT_NINE_ESTATE=healthy)))
    results.append(plant_cell("6 NOT MET: one Disconnected", 6, noop, "NOT MET",
                              env=dict(EXIT_NINE_ESTATE=sick)))

    print("criterion 7 - one owner across the attached pool")
    results.append(plant_cell("7 UNKNOWN: tests GREEN", 7, noop, "UNKNOWN"))
    results.append(plant_cell(
        "7 NOT MET: a signing test FAILs", 7,
        lambda plant: insert_statements(plant, [(
            "tests/test_the_provider_does_the_signing.py",
            None, FAIL_STMT, False)]), "NOT MET"))

    print("criterion 8 - the review file is approved by the owner")
    results.append(plant_cell("8 MET: tree as it stands", 8, noop, "MET"))
    sheet = scratch("pc0239-sheet.md", "a sheet nobody approved\n")
    wrong = scratch("pc0239-decision-wrong.md",
                    "pinned sha256 " + "0" * 64 + "\n")
    with io.open(sheet, "rb") as handle:
        sheet_digest = hashlib.sha256(handle.read()).hexdigest()
    right = scratch("pc0239-decision-right.md",
                    "pinned sha256 %s\n" % sheet_digest)
    results.append(plant_cell("8 MET: scratch sheet, pinned", 8, noop, "MET",
                              env=dict(EXIT_NINE_SHEET=sheet,
                                       EXIT_NINE_DECISION=right)))
    results.append(plant_cell("8 NOT MET: digest does not match", 8, noop,
                              "NOT MET",
                              env=dict(EXIT_NINE_SHEET=sheet,
                                       EXIT_NINE_DECISION=wrong)))

    print("criterion 9 - a kill switch the operator can operate alone")
    results.append(plant_cell("9 NOT MET: tree as it stands", 9, noop, "NOT MET"))
    results.append(plant_cell(
        "9 MET: the five reds skipped", 9,
        lambda plant: insert_statements(
            plant, [(rel, name, SKIP_STMT, False) for rel, name in BRAKE_REDS]),
        "MET"))

    print()
    print("=" * 78)
    for got in results:
        print("%-38s %-9s expect %-9s %s"
              % (got["label"], got["verdict"], got["expect"],
                 "OK" if got["ok"] else "MISMATCH"))
    bad = [g["label"] for g in results if not g["ok"]]
    print("cells agreeing with prediction: %d of %d"
          % (len(results) - len(bad), len(results)))
    for label in bad:
        print("  MISMATCH: %s" % label)
    reverts = [(r["label"], rel, ok)
               for r in results for rel, _, ok in r["revert"]]
    print("revert proofs: %d file-writes, all sha256-identical: %s"
          % (len(reverts), all(ok for _, _, ok in reverts)))
    for label, rel, ok in reverts:
        if not ok:
            print("  REVERT FAILED: %s %s" % (label, rel))
    with io.open(os.path.join(SCRATCH, "pc0239-matrix.json"), "w",
                 encoding="utf-8") as handle:
        json.dump(results, handle, indent=1)
    return 0 if not bad else 1


EMPTY_NOTE_TEST = ("tests/test_the_empty_connection_note_is_an_operator_decision.py",
                   "test_the_note_is_empty_because_the_operator_decided_it")

DEMO_TEST = "test_an_attributed_removal_request_writes_a_suppression_row"
DEMO_FILE = "tests/test_a_suppressed_address_cannot_reach_a_provider.py"


def extra():
    """The cells that isolate WHY two rows refused to move, from run 2.

    Run 2 left three mismatches. Two of them are the finding; the third is the
    reproduction of 0235's plant. These cells separate "the row cannot print
    that verdict" from "the plant did not force the state".
    """
    results = []

    print("criterion 2 - is NOT MET unreachable, or was the test not red?")
    print("  run 2 already showed the demonstration FAILing and the row MET,")
    print("  with the status recorded as '(RAN, FAIL)'. This cell asks whether")
    print("  the row can leave MET AT ALL, by making the demonstration vanish.")
    results.append(plant_cell(
        "2 UNKNOWN: demonstration renamed", 2,
        lambda plant: replace_once(plant, DEMO_FILE,
                                   "def %s(" % DEMO_TEST,
                                   "def renamed_%s(" % DEMO_TEST), "UNKNOWN"))

    print("criterion 3 - MET with BOTH observers of the contradiction suspended")
    print("  run 2 showed occurrences 0 -> 2 and a NEW red:")
    print("  test_the_note_is_empty_because_the_operator_decided_it. The row")
    print("  needs occurrences > 0 AND zero reds, and that test needs the note")
    print("  EMPTY, so the two halves contradict. This cell measures what it")
    print("  takes to reach MET: suspending the criterion's own observer.")

    def both_suspended(plant):
        replace_once(plant, LI_CONFIG, NOTE_BLOCK_OLD,
                     note_block_new("{connection_note}"))
        insert_statements(plant, [
            ("tests/test_linkedin_note.py", EMDASH_TEST, SKIP_STMT, False),
            (EMPTY_NOTE_TEST[0], EMPTY_NOTE_TEST[1], SKIP_STMT, False)])

    results.append(plant_cell(
        "3 MET: both observers suspended", 3, both_suspended, "MET"))

    print()
    bad = [g["label"] for g in results if not g["ok"]]
    for got in results:
        print("%-38s %-9s expect %-9s %s"
              % (got["label"], got["verdict"], got["expect"],
                 "OK" if got["ok"] else "MISMATCH"))
        print("    denom %s" % got["denominator"])
        print("    cond  %s" % got["condition"][:400])
    reverts = [ok for r in results for _, _, ok in r["revert"]]
    print("revert proofs: %d file-writes, all sha256-identical: %s"
          % (len(reverts), all(reverts)))
    with io.open(os.path.join(SCRATCH, "pc0239-extra.json"), "w",
                 encoding="utf-8") as handle:
        json.dump(results, handle, indent=1)
    return 0 if not bad else 1


def mutate(force):
    """C4 - make the evaluator REPORT `force` for every row, permanently.

    The mutation sits where the row is recorded, not inside one criterion, so
    it is literally "report X for every row" and is blind to which check ran.
    It must be COMMITTED in the throwaway tree before it has any effect: the
    instrument hashes itself against HEAD and an uncommitted edit makes all
    nine UNKNOWN, which would spoil the pairing by reddening every control at
    once instead of the ones under test.
    """
    plant = Plant("C4 force %s" % force)
    replace_once(plant, EXIT_NINE, "        rows.append(got)",
                 '        got["verdict"] = %s   # TASK-0239 C4 mutation\n'
                 "        rows.append(got)" % force)
    print("mutated %s: every row now reports %s" % (EXIT_NINE, force))
    print("new sha256 %s" % digest(read_bytes(EXIT_NINE)))
    return 0


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "controls"
    print("tree %s" % ROOT)
    print("HEAD %s" % subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                     capture_output=True,
                                     text=True).stdout.strip())
    print("exit_nine sha256 %s" % digest(read_bytes(EXIT_NINE)))
    print()
    if mode == "controls":
        got = controls()
        names = [k for k in ("C1", "C2", "C3")]
        print()
        print("CONTROL SUMMARY  " + "  ".join(
            "%s=%s" % (n, "PASS" if got[n][0] else "FAIL") for n in names))
        return 0 if all(got[n][0] for n in names) else 1
    if mode == "matrix":
        return matrix()
    if mode == "extra":
        return extra()
    if mode == "mutate-met":
        return mutate("MET")
    if mode == "mutate-notmet":
        return mutate("NOT_MET")
    print("unknown mode %r" % mode)
    return 2


if __name__ == "__main__":
    sys.exit(main())
