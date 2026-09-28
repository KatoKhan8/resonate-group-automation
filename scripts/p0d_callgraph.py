#!/usr/bin/env python3
"""P0-D read-only probe: does a real production entrypoint reach the generator?

READ-ONLY. Parses source with `ast`; imports nothing from `src`, calls no
provider, writes no state. Answers one question with a machine-derived answer
rather than a grep: from each candidate entrypoint, which generation functions
are REACHABLE through the call graph.

WHY AST AND NOT GREP. A grep for `generate.run` cannot see a caller inside
`src/generate.py` itself, because there the call is spelled `run(...)`. That is
the exact measurement error this probe exists to remove: `generate.main()`
calls `run(...)` and no qualified-name grep will ever show it.

Usage:
    py -3 scripts/p0d_callgraph.py                 # reachability report
    py -3 scripts/p0d_callgraph.py --callers-of src.generate:run
"""
import argparse
import ast
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Directories parsed. `tests` is included deliberately and then reported
# SEPARATELY, because a test caller is never a production caller (invariant 0).
SCAN = ("src", "scripts", "tools")
TEST_DIRS = ("tests",)


def _module_name(path):
    rel = os.path.relpath(path, ROOT).replace(os.sep, "/")
    if rel.endswith("/__init__.py"):
        rel = rel[: -len("/__init__.py")]
    elif rel.endswith(".py"):
        rel = rel[: -len(".py")]
    return rel.replace("/", ".")


def _py_files(dirs):
    out = []
    for d in dirs:
        base = os.path.join(ROOT, d)
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [x for x in dirnames
                           if x not in (".git", "__pycache__", ".venv")]
            for fn in filenames:
                if fn.endswith(".py"):
                    out.append(os.path.join(dirpath, fn))
    return sorted(out)


class ModuleIndex:
    """Per-module: the functions defined, and what each call site names."""

    def __init__(self, path):
        self.path = path
        self.module = _module_name(path)
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            self.src = fh.read()
        self.tree = ast.parse(self.src, filename=path)
        # alias -> target module. Both `from . import generate` and
        # `from src import generate` and `import src.generate as g`.
        self.aliases = {}
        # name defined at module level -> "module:qualname"
        self.defs = {}
        # "module:qualname" -> list of (callee_repr, lineno)
        self.calls = {}
        self._walk()

    # -- imports ------------------------------------------------------
    def _pkg(self, level):
        """Resolve a relative import's base package."""
        parts = self.module.split(".")
        if self.path.endswith("__init__.py"):
            base = parts
        else:
            base = parts[:-1]
        if level > 1:
            base = base[: len(base) - (level - 1)]
        return ".".join(base)

    def _collect_imports(self, node):
        if isinstance(node, ast.Import):
            for a in node.names:
                self.aliases[a.asname or a.name.split(".")[0]] = a.name
        elif isinstance(node, ast.ImportFrom):
            base = self._pkg(node.level) if node.level else (node.module or "")
            if node.level and node.module:
                base = base + "." + node.module
            for a in node.names:
                self.aliases[a.asname or a.name] = (
                    base + "." + a.name if base else a.name)

    # -- walk ---------------------------------------------------------
    def _walk(self):
        for node in ast.walk(self.tree):
            self._collect_imports(node)
        for node in self.tree.body:
            self._scan_def(node, prefix="")
        # module-level statements (an `if __name__` block lives here) are
        # attributed to a synthetic "<module>" scope, so `raise
        # SystemExit(main())` is not lost.
        self._scan_body(self.tree.body, f"{self.module}:<module>",
                        skip_defs=True)

    def _scan_def(self, node, prefix):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            qual = (prefix + "." + node.name) if prefix else node.name
            key = f"{self.module}:{qual}"
            self.defs[qual] = key
            self._scan_body(node.body, key, skip_defs=False)
            for sub in node.body:
                self._scan_def(sub, qual)
        elif isinstance(node, ast.ClassDef):
            qual = (prefix + "." + node.name) if prefix else node.name
            for sub in node.body:
                self._scan_def(sub, qual)
        elif isinstance(node, (ast.If, ast.Try, ast.With, ast.For,
                               ast.While)):
            for sub in ast.iter_child_nodes(node):
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef,
                                    ast.ClassDef)):
                    self._scan_def(sub, prefix)

    def _scan_body(self, body, key, skip_defs):
        bucket = self.calls.setdefault(key, [])
        for stmt in body:
            for node in ast.walk(stmt):
                if skip_defs and isinstance(
                        node, (ast.FunctionDef, ast.AsyncFunctionDef,
                               ast.ClassDef)):
                    continue
                if isinstance(node, ast.Call):
                    r = self._callee(node.func)
                    if r:
                        bucket.append((r, node.lineno))
                # function-local imports are real: `from . import generate`
                # inside a function body is how half this repo defers imports.
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    self._collect_imports(node)

    def _callee(self, func):
        if isinstance(func, ast.Name):
            return func.id
        if isinstance(func, ast.Attribute):
            parts = []
            cur = func
            while isinstance(cur, ast.Attribute):
                parts.append(cur.attr)
                cur = cur.value
            if isinstance(cur, ast.Name):
                parts.append(cur.id)
                return ".".join(reversed(parts))
        return None


def build(dirs):
    idx = {}
    for p in _py_files(dirs):
        try:
            m = ModuleIndex(p)
        except SyntaxError as e:
            print(f"  SKIP (syntax) {p}: {e}", file=sys.stderr)
            continue
        idx[m.module] = m
    return idx


def resolve(mi, callee, idx):
    """Map one call-site name to a "module:qualname", or None."""
    # same-module bare call: `run(...)` inside src.generate
    if "." not in callee:
        if callee in mi.defs:
            return mi.defs[callee]
        target = mi.aliases.get(callee)
        if target and target in idx:
            return None  # a module, not a function
        if target:
            mod, _, fn = target.rpartition(".")
            if mod in idx and fn in idx[mod].defs:
                return idx[mod].defs[fn]
        return None
    head, _, rest = callee.partition(".")
    target = mi.aliases.get(head)
    if target is None:
        return None
    # `generate.run` where alias generate -> src.generate
    if target in idx and rest in idx[target].defs:
        return idx[target].defs[rest]
    # `src.generate.run` style
    full = target + "." + rest
    mod, _, fn = full.rpartition(".")
    if mod in idx and fn in idx[mod].defs:
        return idx[mod].defs[fn]
    return None


def edges(idx):
    """caller "module:qual" -> set of callee "module:qual"."""
    out = {}
    for mi in idx.values():
        for key, calls in mi.calls.items():
            dst = out.setdefault(key, set())
            for callee, _line in calls:
                r = resolve(mi, callee, idx)
                if r:
                    dst.add(r)
    return out


def reverse(e):
    rev = {}
    for a, bs in e.items():
        for b in bs:
            rev.setdefault(b, set()).add(a)
    return rev


def reachable(e, start):
    seen, stack = set(), [start]
    while stack:
        cur = stack.pop()
        for nxt in e.get(cur, ()):
            if nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    return seen


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--callers-of", action="append", default=[],
                    help='e.g. "src.generate:run"')
    ap.add_argument("--from", dest="starts", action="append", default=[])
    ap.add_argument("--target", action="append", default=[],
                    help="chain link to test, as NAME=module:qual[,module:qual]")
    ap.add_argument("--include-tests", action="store_true")
    a = ap.parse_args(argv)

    dirs = list(SCAN) + (list(TEST_DIRS) if a.include_tests else [])
    idx = build(dirs)
    e = edges(idx)
    rev = reverse(e)
    print(f"modules parsed: {len(idx)}   call edges: "
          f"{sum(len(v) for v in e.values())}\n")

    for t in a.callers_of:
        print(f"== DIRECT CALLERS of {t} ==")
        cs = sorted(rev.get(t, ()))
        if not cs:
            print("  NONE")
        for c in cs:
            print(f"  {c}")
        print()

    # default: reachability of the generation surface from each entrypoint
    gen = [k for k in e if k.startswith("src.generate:")
           or k.startswith("src.generate_campaign:")]
    targets = ["src.generate:run", "src.generate:generate_record",
               "src.generate:_generate_via_campaign",
               "src.generate_campaign:generate",
               "src.generate:draft", "src.generate:plan"]
    starts = a.starts or [
        "src.web.app:main", "src.web:<module>", "src.web.app:<module>",
        "src.run:main", "src.run:run", "src.run:<module>",
        "src.generate:main", "src.generate:<module>",
        "src.orchestrator:main", "src.orchestrator:<module>",
        "src.supervisor:main", "src.jobs:<module>",
    ]
    print("== REACHABILITY: entrypoint -> generation surface ==")
    for s in starts:
        r = reachable(e, s)
        hits = [t for t in targets if t in r]
        label = "REACHES" if hits else "does NOT reach"
        print(f"  {s:38s} {label:15s} {', '.join(hits) if hits else '-'}")
    print()

    if a.target:
        links = []
        for spec in a.target:
            name, _, fns = spec.partition("=")
            links.append((name, [x for x in fns.split(",") if x]))
        print("== CHAIN LINKS: is each reachable from each entrypoint ==")
        hdr = "  " + "link".ljust(22) + "".join(
            s.split(":")[0].replace("src.", "").ljust(16) for s in starts)
        print(hdr)
        for name, fns in links:
            row = "  " + name.ljust(22)
            for s in starts:
                r = reachable(e, s)
                seen = [f for f in fns if f in r]
                # a target that is defined nowhere is ABSENT, not unreached
                known = [f for f in fns if f in e or f in rev]
                if not known:
                    row += "ABSENT".ljust(16)
                else:
                    row += ("YES" if seen else "no").ljust(16)
            print(row)
        print()
        print("  per-link detail (which of the named functions were reached):")
        for name, fns in links:
            for s in starts:
                r = reachable(e, s)
                seen = [f for f in fns if f in r]
                if seen:
                    print(f"    {name:22s} <- {s:26s} {', '.join(seen)}")
        print()
    print(f"(generation-surface functions indexed: {len(gen)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
