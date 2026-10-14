#!/usr/bin/env python3
"""The dispositioned business-clock scanner. A MEASURING TOOL, not a seam.

    py -3 scripts/clockscan.py            # whole src/, grouped by disposition
    py -3 scripts/clockscan.py --named    # only SIMULATED_PATH_MODULES

WHY THIS IS IN `scripts/` AND NOT IN `src/sandboxclock.py`
==========================================================
It was written there first, and `tests/test_sandbox_run.py`
`test_src_is_identical_to_the_fork_point` refused it: this branch asserts
`git diff <fork> -- src/` is EMPTY, because the sandbox DRIVES the flow and
does not modify it. That assertion is correct and is not weakened here. A
scanner is a measurement, not a seam, and the branch already keeps its
measurement code in `scripts/` - `sandbox_run.clock_defects()` lives there
too. So this lives beside it and imports `src.sandboxclock` read-only.

WHY IT EXISTS AT ALL, MEASURED RATHER THAN ARGUED
=================================================
The 2026-10-13 sandbox run was HELD on C11, which reported ten
`on_path_but_unnamed` wall-clock reads. `sandboxclock`'s regex scanner cannot
answer the question it was being asked:

  * `_INJECTABLE_IDIOM` is `=\\s*\\w+\\s+or\\s+datetime\\.datetime\\.now\\(`.
    The repository writes the same injectable idiom FOUR ways and that
    pattern recognises ONE:

        x = now or datetime.datetime.now(tz)              MATCHES
        return (now or datetime.datetime.now(tz)).date()  missed, return form
        age = ((now or _utcnow()) - then)                  missed, helper form
        if today is None: today = date.today()             missed, guard form,
                                                           and it spans two
                                                           lines, which a line
                                                           scanner cannot see

  * `_CLOCK_RX["utcnow"]` is `utcnow\\(`, which matches the DEFINITION line
    `def _utcnow():`. One of the ten rows was a function signature.

So of those ten, one was not a read and six were injectable, and the report
could not tell them apart. A scanner that cannot see three of four spellings
cannot be used to certify that they are absent.

This one asks structurally: for every clock CALL, what encloses it, and does
that enclosure take a clock parameter a caller could pass?

THREE OF MY OWN DRAFTS WERE WRONG AND EACH WAS CAUGHT BY A CONTROL
==================================================================
Recorded because the pattern matters more than the fixes:

  1. `INJECTABLE_PARAMS` was written from memory as
     `("now","today","at","as_of")` - carrying `as_of`, which no site in
     `src/` uses, and OMITTING `on_date`, which three sites in
     `nightlysourcing` use. Three injectable reads were reported as unpatched
     defects. The list is now MEASURED off `src/`: `now` 7 sites, `today` 4,
     `on_date` 3, `at` 1.
  2. the helper test required the returned expression to BE a clock call, so
     `clientreport.today`, which is
     `return datetime.date.today().isoformat()`, was not recognised as a
     helper - the outer call is `.isoformat`. Any clock call anywhere inside
     the single returned expression now counts.
  3. a draft promoted every call to a local clock helper to `unpatched`,
     which swept in the four `store.now()` calls inside `store.py`. `store.now`
     is the PATCHED SEAM, so the instrument was reporting the fix as the
     defect. Seam calls are skipped; other helper calls are `INDIRECT`,
     counted once in the helper body; and `INJECTABLE` outranks `INDIRECT`,
     because whether a caller can inject is the fact that decides what
     evidence C11c needs.

WHAT A DISPOSITION DOES AND DOES NOT SETTLE
===========================================
`INJECTABLE` means the read sits behind a parameter a caller COULD pass. It
does NOT say any caller DOES. That is a question about execution and only an
executed control can answer it - `sandbox_run.evidence_clock_control` is the
shape: run the decision twice, once with the simulated clock and once
without, and require the answers to differ when the clock is not injected.
A row disposed `INJECTABLE` is therefore NOT disposed of for C11c until such
a control exists for it.
"""
import argparse
import ast
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.sandboxclock import (BUSINESS_CLOCK_SEAMS,          # noqa: E402
                              REAL_ELAPSED_EXEMPT,
                              SIMULATED_PATH_MODULES)

#: Parameter names that make a clock read injectable. MEASURED off `src/` on
#: 2026-10-13 by walking every function that carries the idiom, not guessed.
INJECTABLE_PARAMS = ("now", "today", "on_date", "at")

UNPATCHED = "unpatched"          # a real defect: reachable, not injectable
INJECTABLE = "injectable"        # behind a clock parameter; needs a CALLER test
HELPER_BODY = "helper_body"      # the body of a no-argument clock helper
MODULE_LEVEL = "module_level"    # evaluated at import; never injectable
EXEMPT = "exempt"                # named in REAL_ELAPSED_EXEMPT
INDIRECT = "indirect"            # a CALL to a local clock helper

DISPOSITIONS = (UNPATCHED, INJECTABLE, HELPER_BODY, MODULE_LEVEL, EXEMPT,
                INDIRECT)


def _exempt_index():
    lines, files = set(), set()
    for path, lineno, _kind, _why in REAL_ELAPSED_EXEMPT:
        name = os.path.basename(path)
        if lineno is None:
            files.add(name)
        else:
            lines.add((name, lineno))
    return lines, files


def clock_kind(node):
    """The clock-read kind this `ast.Call` is, or None."""
    func = node.func
    parts = []
    while isinstance(func, ast.Attribute):
        parts.append(func.attr)
        func = func.value
    if isinstance(func, ast.Name):
        parts.append(func.id)
    parts.reverse()
    if not parts:
        return None
    tail = parts[-1]
    if tail == "utcnow":
        return "utcnow"
    if tail == "now" and "datetime" in parts:
        return "datetime.now"
    if tail == "today" and ("date" in parts or "datetime" in parts):
        return "date.today"
    return None


class _Walker(ast.NodeVisitor):
    """Clock calls with their enclosing function and whether it is a helper."""

    def __init__(self):
        self.stack = []
        self.found = []
        self.helpers = {}

    def _visit_func(self, node):
        args = node.args
        names = [a.arg for a in list(args.posonlyargs) + list(args.args)
                 + list(args.kwonlyargs)]
        body = [s for s in node.body
                if not (isinstance(s, ast.Expr)
                        and isinstance(s.value, ast.Constant))]
        is_helper = (not names and len(body) == 1
                     and isinstance(body[0], ast.Return)
                     and body[0].value is not None
                     and any(isinstance(n, ast.Call)
                             and clock_kind(n) is not None
                             for n in ast.walk(body[0].value)))
        if is_helper:
            self.helpers[node.name] = node.lineno
        self.stack.append((node.name, names, is_helper))
        self.generic_visit(node)
        self.stack.pop()

    visit_FunctionDef = _visit_func
    visit_AsyncFunctionDef = _visit_func

    def visit_Call(self, node):
        helper = None
        kind = clock_kind(node)
        if kind is None:
            func = node.func
            name = func.id if isinstance(func, ast.Name) else None
            if name and name in self.helpers:
                kind, helper = "utcnow", name
        if kind is not None:
            if self.stack:
                fname, params, is_helper = self.stack[-1]
            else:
                fname, params, is_helper = None, [], False
            self.found.append((node.lineno, kind, fname, params, is_helper,
                               helper))
        self.generic_visit(node)


def clock_reads(root=None, only=None):
    """Every business-clock read under `root`, each with exactly ONE
    disposition. `only` narrows to a set of basenames.

    `time.time` and `time.monotonic` are NOT scanned: they are real elapsed
    time, and `REAL_ELAPSED_EXEMPT` names the ones that must stay real.
    """
    root = root or os.path.join(ROOT, "src")
    patched = {m.split(".")[-1] + ".py" for m, _a, _w in BUSINESS_CLOCK_SEAMS}
    exempt_lines, exempt_files = _exempt_index()
    out = []
    for folder, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for name in sorted(files):
            if not name.endswith(".py"):
                continue
            if only is not None and name not in only:
                continue
            path = os.path.join(folder, name)
            with open(path, encoding="utf-8", errors="replace") as handle:
                text = handle.read()
            try:
                tree = ast.parse(text)
            except SyntaxError:
                continue
            lines = text.splitlines()
            walker = _Walker()
            walker.visit(tree)
            seam_attrs = {a for m, a, _w in BUSINESS_CLOCK_SEAMS
                          if m.split(".")[-1] + ".py" == name}
            for (lineno, kind, fname, params, is_helper,
                 helper) in walker.found:
                if helper is not None and helper in seam_attrs:
                    continue                    # a call to the PATCHED SEAM
                if name in exempt_files or (name, lineno) in exempt_lines:
                    disposition = EXEMPT
                elif name in patched and kind == "datetime.now":
                    continue                    # the seam's own body
                elif fname is None:
                    disposition = MODULE_LEVEL
                elif is_helper:
                    disposition = HELPER_BODY
                elif any(p in INJECTABLE_PARAMS for p in params):
                    disposition = INJECTABLE    # outranks INDIRECT
                elif helper is not None:
                    disposition = INDIRECT
                else:
                    disposition = UNPATCHED
                src = lines[lineno - 1].strip() if lineno <= len(lines) else ""
                out.append({"file": path, "line": lineno, "kind": kind,
                            "source": src[:110], "function": fname,
                            "disposition": disposition})
    return out


def dispositions(rows):
    out = {}
    for row in rows:
        out[row["disposition"]] = out.get(row["disposition"], 0) + 1
    return out


def report_disagreement(only=None):
    """How the two instruments differ, in numbers. Evidence for C11's
    "the scanner was the defect" finding, and the reason the regex scanner is
    kept rather than deleted. It must NOT be used for a verdict."""
    from src import sandboxclock

    old = sandboxclock.unpatched_business_clock_reads(only=only)
    new = clock_reads(only=only)
    return {
        "regex_rows": len(old),
        "ast_rows": len(new),
        "ast_dispositions": dispositions(new),
        "regex_reports_a_def_line": any(r[3].startswith("def ") for r in old),
        "ast_reports_a_def_line": any(r["source"].startswith("def ")
                                      for r in new),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--named", action="store_true",
                        help="only SIMULATED_PATH_MODULES")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    only = SIMULATED_PATH_MODULES if args.named else None
    rows = clock_reads(only=only)
    if args.json:
        print(json.dumps({"rows": rows, "dispositions": dispositions(rows)},
                         indent=1, sort_keys=True))
        return 0
    print("scanned %s" % ("SIMULATED_PATH_MODULES" if args.named
                          else "the whole of src/"))
    print("rows: %d   dispositions: %s"
          % (len(rows), json.dumps(dispositions(rows), sort_keys=True)))
    for disposition in DISPOSITIONS:
        here = [r for r in rows if r["disposition"] == disposition]
        if not here:
            continue
        print("\n%s (%d)" % (disposition.upper(), len(here)))
        for row in here:
            print("   %-24s:%-5s %-13s fn=%-26s %s"
                  % (os.path.basename(row["file"]), row["line"], row["kind"],
                     row["function"], row["source"][:44]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
