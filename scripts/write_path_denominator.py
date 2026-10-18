#!/usr/bin/env python3
"""How many provider write paths exist, and how many pass through the door.

READ-ONLY static `ast` analysis. Run with `py -3 -B <tree>` so it writes no
bytecode into a tree that may be holding a running suite.

WHY THIS EXISTS. `sink_token_split.py` counted `providerwrites.perform` CALL
SITES and asked whether each presented a token. A write that never reaches
`perform` is invisible to that question, and 26 of 58 do exactly that.

WHY THE MUTATING SET IS DERIVED, NOT LISTED. A hardcoded list is how
`sink_token_split.py:36` came to report on its own fourteen names. The write
functions here are found by closure over each provider's OWN call graph up from
its mutating helpers, so a new write verb is picked up without anyone
remembering to add it.

WHY "THE DOOR ITSELF" IS ALWAYS ZERO, and it is not a defect: `perform` never
calls a provider. The caller hands it a `transport=` callable, so the provider
call always lives at the call site.

THE CLASSIFIER'S OWN HISTORY, because it was wrong twice in the same direction
as the claim it was checking:
  * a lexical "inside the perform(...) call" test said 42 - it misses a
    transport defined as a named function just above the call;
  * following `transport=<name>` to a FunctionDef or Assign said 30 - it misses
    lambdas tuple-unpacked in a `for` statement (src/orchestrator.py:672).
The enclosing-function rule below says 26, and every `src/` hit was then read by
eye. A call site counts as gated when the mutating call and a `perform(...)` sit
in the SAME function. That over-credits a helper called only from a gated
function; `src/` results are hand-checked for exactly that reason.
"""
import ast
import collections
import io
import os
import sys

HELPERS = {"bison": ("_post", "_patch", "_put", "_delete"),
           "heyreach": ("_write", "_write_body")}


def _calls_within(path):
    tree = ast.parse(io.open(path, encoding="utf-8").read())
    out = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out[node.name] = {
                getattr(s.func, "id", None) or getattr(s.func, "attr", None)
                for s in ast.walk(node) if isinstance(s, ast.Call)}
    return out


def mutating_functions(root):
    """{provider: {public function names that reach a mutating helper}}."""
    found = {}
    for mod, seeds in HELPERS.items():
        graph = _calls_within(os.path.join(root, "src", "providers", mod + ".py"))
        reach, changed = set(seeds), True
        while changed:
            changed = False
            for fn, calls in graph.items():
                if fn not in reach and (calls & reach):
                    reach.add(fn)
                    changed = True
        found[mod] = {f for f in reach if not f.startswith("_") and f in graph}
    return found


def call_sites(root, writers):
    rows = []
    for base in ("src", "scripts"):
        for here, dirs, files in os.walk(os.path.join(root, base)):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for name in sorted(files):
                if not name.endswith(".py"):
                    continue
                path = os.path.join(here, name)
                rel = os.path.relpath(path, root).replace("\\", "/")
                try:
                    tree = ast.parse(io.open(path, encoding="utf-8",
                                             errors="replace").read())
                except SyntaxError:
                    continue
                owner = {}
                for top in tree.body:
                    if isinstance(top, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        for sub in ast.walk(top):
                            owner[id(sub)] = top

                def opens_the_door(node):
                    return any(
                        isinstance(s, ast.Call)
                        and (getattr(s.func, "attr", None) == "perform"
                             or getattr(s.func, "id", None) == "perform")
                        for s in ast.walk(node))

                for node in ast.walk(tree):
                    if not isinstance(node, ast.Call):
                        continue
                    fn = node.func
                    if not isinstance(fn, ast.Attribute):
                        continue
                    who = getattr(fn.value, "id", None)
                    if who not in writers or fn.attr not in writers[who]:
                        continue
                    enclosing = owner.get(id(node))
                    if rel == "src/providerwrites.py":
                        verdict = "the door itself"
                    elif enclosing is not None and opens_the_door(enclosing):
                        verdict = "gated"
                    elif enclosing is None and opens_the_door(tree):
                        verdict = "gated"
                    else:
                        verdict = "BYPASS"
                    rows.append((verdict, rel, node.lineno,
                                 "%s.%s" % (who, fn.attr),
                                 enclosing.name if enclosing else "<module>"))
    return rows


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    writers = mutating_functions(root)
    for mod in sorted(writers):
        print("%s: %d mutating public functions" % (mod, len(writers[mod])))
        print("   " + ", ".join(sorted(writers[mod])))
    rows = call_sites(root, writers)
    tally = collections.Counter(r[0] for r in rows)
    passes = tally["gated"] + tally["the door itself"]
    print()
    print("write paths            : %d" % len(rows))
    print("pass through the door  : %d" % passes)
    print("BYPASS the door        : %d" % tally["BYPASS"])
    print()
    for verdict, rel, line, call, where in sorted(rows):
        if verdict == "BYPASS":
            print("  BYPASS  %s:%d  %-32s in %s()" % (rel, line, call, where))
    return 0 if tally["BYPASS"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
