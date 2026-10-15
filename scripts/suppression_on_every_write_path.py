#!/usr/bin/env python3
"""Does a suppression consult stand on every provider write path? TASK-0160.

READ-ONLY static `ast` analysis, offline, no provider call. Run as
`py -3 -B scripts/suppression_on_every_write_path.py <tree>` so it writes no
bytecode into a tree that may be holding a running suite.

WHY THIS EXISTS. CANARY-01 exit criterion 1 says a suppressed address cannot
reach the transport **by any path**. `tests/test_a_suppressed_address_cannot_
reach_a_provider.py` proves the consult is load-bearing on the paths it
exercises; it does not and cannot enumerate the paths it does not exercise.
`scripts/write_path_denominator.py` already derives that enumeration - 58
mutating provider call sites - so the "any path" half of criterion 1 is
answerable by asking the same denominator a different question.

WHAT COUNTS AS A CONSULT, and why it is not `perform`. The door does NOT run a
blanket suppression check. Measured on the suppression branch:

    src/executionguard.py:991 revalidate()  -> suppression.decide   SCOPE_SEND
        reached by `perform` only for a verb whose descriptor is facing=True
    src/providerwrites.py:1429 _resume_revalidates_suppression()
        CONDITIONAL[EMAIL_RESUME] only, because EMAIL_RESUME is facing=False
    src/bisonfactory.py:1998 _refuse_suppressed_leads()
        called from _ensure_leads(), so the lead writes carry a consult even
        though they bypass `perform`

So three buckets, not two, and a site that "passes the door" is not thereby
consulted - that depends on its verb's `facing` flag, which this analyzer
reports but does not resolve per call site.

THE RULE. A site is IN-FUNCTION consulted when the mutating call and a
`suppression.decide` / `suppression.require` call sit in the SAME function,
directly or through a same-module helper that function calls (transitively).
That is deliberately the same enclosing-function rule the denominator uses, so
the two numbers are commensurable, and it over-credits in the same direction -
a consult in the function is not proof it runs before the write on every branch.
Over-crediting is stated rather than hidden: a site this reports as consulted
may still not be, so the NO-CONSULT count is a FLOOR and never a ceiling.
"""
import ast
import collections
import importlib.util
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CONSULTS = ("decide", "require")


def _analyzer():
    spec = importlib.util.spec_from_file_location(
        "write_path_denominator_for_suppression",
        os.path.join(HERE, "write_path_denominator.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _consulting_functions(path):
    """Functions in one module that reach a suppression consult.

    Direct first, then closure down the module's own call graph, so a function
    calling a same-module helper that consults counts as consulting.
    """
    with io.open(path, encoding="utf-8", errors="replace") as fh:
        try:
            tree = ast.parse(fh.read())
        except SyntaxError:
            return set(), {}
    calls, direct = {}, set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        names = set()
        for sub in ast.walk(node):
            if not isinstance(sub, ast.Call):
                continue
            fn = sub.func
            if (isinstance(fn, ast.Attribute)
                    and fn.attr in CONSULTS
                    and getattr(fn.value, "id", None) in ("suppression",
                                                          "_suppression")):
                direct.add(node.name)
            names.add(getattr(fn, "id", None) or getattr(fn, "attr", None))
        calls[node.name] = names
    reach, changed = set(direct), True
    while changed:
        changed = False
        for fn, names in calls.items():
            if fn not in reach and (names & reach):
                reach.add(fn)
                changed = True
    return reach, direct


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    analyzer = _analyzer()
    writers = analyzer.mutating_functions(root)
    rows = analyzer.call_sites(root, writers)

    per_module = {}
    out = []
    for verdict, rel, line, call, where in rows:
        if rel not in per_module:
            per_module[rel] = _consulting_functions(os.path.join(root, *rel.split("/")))
        reach, direct = per_module[rel]
        if where in reach:
            consult = "CONSULT IN FUNCTION"
        elif verdict in ("gated", "the door itself"):
            consult = "via the door (facing= decides)"
        else:
            consult = "NO CONSULT"
        out.append((consult, verdict, rel, line, call, where))

    tally = collections.Counter(c for c, *_ in out)
    print("provider write paths                  : %d" % len(out))
    print("a suppression consult in the function : %d" % tally["CONSULT IN FUNCTION"])
    print("through the door, consult per verb    : %d"
          % tally["via the door (facing= decides)"])
    print("NO SUPPRESSION CONSULT ON THIS PATH   : %d  (a floor, not a ceiling)"
          % tally["NO CONSULT"])
    print()
    for consult, verdict, rel, line, call, where in sorted(out):
        if consult == "NO CONSULT":
            print("  NO CONSULT  [%s]  %s:%d  %s in %s()"
                  % (verdict, rel, line, call, where))
    return 0 if tally["NO CONSULT"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
