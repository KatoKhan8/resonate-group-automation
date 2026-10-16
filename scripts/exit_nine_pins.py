#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TASK-0246 - every pin in the exit-criteria machinery, resolved to a subject.

## The sentence this exists to close

`TASK-0243` repaired criterion 2 and, on the way, found that
`REMOVAL_DEMONSTRATION` pinned **`ARemovalRequestWritesARow`, a class that has
never existed on any ref in this repository**. It was invisible for one
reason: the matcher compared only the LEAF name and threw the dotted path
away, **so a pin that resolved to nothing behaved exactly like one that
resolved**.

That is not a weak check. It is a check with no subject. The exit table is the
sheet an operator reads before deciding it is safe to send twenty-three real
people a message, and `TASK-0239` already measured what an empty subject does
to it: a row printed `MET` with its own denominator reading `(RAN, FAIL)`.

So: **every pin in that table needs a subject that exists, and an unresolvable
pin is a loud UNKNOWN at evaluation time rather than a silent pass.**

## What a pin is

Any literal in the evaluator naming a test, class, method, module, file or
path that the evaluator expects to FIND. Three kinds, because three kinds have
three different authorities:

    dotted         `tests.<module>[.<Class>[.<method>]]` - resolved by parsing
                   the module's source, never by importing it, so a ref can be
                   resolved without checking it out and an import-time error
                   cannot be mistaken for a missing name.
    repo_path      a path relative to the repository root - resolved against a
                   ref's tree or against disk.
    external_path  an absolute path outside the repository (the ops folder,
                   the estate export, the approval sheet) - the filesystem is
                   its only authority, so a ref cannot answer it and the ref
                   column says so rather than guessing.

## Three verdicts and no fourth

    RESOLVES           the subject was found, by name, in the authority named.
    DOES NOT RESOLVE   the authority was read and the subject is not in it.
    UNKNOWN            the authority could not be read, or the source could not
                       be parsed. Never a pass - this estate's invariant 0.

A pin whose module cannot be PARSED is UNKNOWN, not DOES NOT RESOLVE: those
are different facts and collapsing them is how a blind reader reports a clean
bill of health.

## The denominator is a FLOOR, and the word is deliberate

`find_pins` reads string CONSTANTS out of the AST. A pin assembled at runtime
- `"tests.%s" % name`, a name read from JSON, a leaf joined to a module in a
loop - is not a constant and this finder cannot see it. `TASK-0239` had to
withdraw a "not a floor" claim once; this one is declared a floor from the
start, and `scripts/exit_pins_controls.py` C3 plants an invisible pin and
reports that it is missed.
"""
import argparse
import ast
import json
import os
import re
import subprocess
import sys

RESOLVES = "RESOLVES"
DOES_NOT_RESOLVE = "DOES NOT RESOLVE"
UNKNOWN = "UNKNOWN"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: A dotted pin always starts at the test package. Anchored at both ends, so a
#: prose mention inside a sentence is not mistaken for a pin.
DOTTED = re.compile(r"^tests\.[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*$")
#: A bare relative path literal, e.g. "scripts/write_path_denominator.py".
BARE_PATH = re.compile(r"^[\w.\-]+(?:/[\w.\-]+)+\.(?:py|json|csv|md|txt)$")
#: A bare test LEAF - a method name with no module and no class beside it.
#: This is the shape the broken matcher compared, and it is the weakest pin
#: there is: it can be resolved only to "some module defines this name".
BARE_LEAF = re.compile(r"^test_[a-z0-9][a-z0-9_]*$")
#: The root-relative names that `os.path.join(ROOT, ...)` is built from.
ROOT_NAMES = ("ROOT", "TREE", "tree")
#: Join bases that leave the repository.
EXTERNAL_NAMES = ("OPS", "base", "canary", "CANARY")


class Pin(object):
    """One pinned literal: what it says, where it is, what it should name."""

    def __init__(self, literal, kind, origin, line, context):
        self.literal = literal
        self.kind = kind
        self.origin = origin
        self.line = line
        self.context = context

    def __repr__(self):
        return "Pin(%r, %s, %s:%d)" % (self.literal, self.kind, self.origin,
                                       self.line)

    def key(self):
        return (self.kind, self.literal)

    def as_dict(self):
        return dict(literal=self.literal, kind=self.kind, origin=self.origin,
                    line=self.line, context=self.context)


# ------------------------------------------------------------------ the finder

def _const_str(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _binding_for(tree):
    """{line number: the name being assigned on it}, for the context column."""
    where = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for inner in ast.walk(node):
                where.setdefault(getattr(inner, "lineno", node.lineno),
                                 node.name + "()")
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            names = [t.id for t in node.targets if isinstance(t, ast.Name)]
            if names:
                for inner in ast.walk(node.value):
                    where[getattr(inner, "lineno", node.lineno)] = names[0]
    return where


def _argparse_defaults(tree):
    """{"--ops": "C:/..."} for every `add_argument` with a literal default.

    Needed because `obs2_nine` takes its ops folder from the command line and
    binds it as `base = os.path.abspath(args.ops)`. Without this the external
    pins beneath it fold to a RELATIVE fragment, which `os.path.exists` then
    resolves against the caller's cwd - a false DOES NOT RESOLVE, measured the
    first time this finder ran.
    """
    out = {}
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "add_argument"):
            continue
        flags = [_const_str(a) for a in node.args]
        default = None
        for word in node.keywords:
            if word.arg == "default":
                default = _const_str(word.value)
        if default is None:
            continue
        for flag in flags:
            if flag and flag.startswith("--"):
                out[flag.lstrip("-")] = default
    return out


def _fold(node, known, flags):
    """A string literal for `node`, or None. Deliberately shallow.

    Folds exactly the four shapes the evaluators use to name an authority -
    a literal, an env default, a join, and an abspath/expanduser - and folds
    NOTHING else. A fold that guessed would put an invented path in the
    authority column, which is worse than UNKNOWN.
    """
    text = _const_str(node)
    if text is not None:
        return text
    if isinstance(node, ast.Name):
        return known.get(node.id)
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) \
            and node.value.id == "args":
        return flags.get(node.attr)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        attr = node.func.attr
        if attr == "get" and len(node.args) == 2:          # os.environ.get
            return _fold(node.args[1], known, flags)
        if attr in ("abspath", "expanduser", "normpath", "realpath") \
                and len(node.args) == 1:
            return _fold(node.args[0], known, flags)
        if attr == "join" and node.args:
            parts = [_fold(a, known, flags) for a in node.args]
            if all(p is not None for p in parts):
                return "/".join(p.replace("\\", "/").rstrip("/") for p in parts)
    return None


def _known_names(tree, flags):
    """{name: folded string} for every assignment this finder can fold.

    Two passes over the WHOLE tree, not just module level, so a local like
    `canary = os.path.join(base, "canary")` inside `context()` is folded too.
    """
    known = {}
    for _ in range(3):                      # three passes: base -> canary -> leaf
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue
            value = _fold(node.value, known, flags)
            if value is None:
                continue
            for target in node.targets:
                if isinstance(target, ast.Name):
                    known.setdefault(target.id, value)
    return known


def _joins(tree, origin, where, known, flags):
    """Pins built by `os.path.join(<base>, "a", "b")`, as one path each.

    The base decides the KIND, and the kind decides the authority: a base that
    folds to the repository root (or to a runtime tree root) gives a path the
    ref can answer; anything else is outside the repository and only the
    filesystem can answer it. A base that folds to NOTHING still yields a pin -
    with its fragment and a kind of `external_path`, so the resolver reports
    UNKNOWN by path rather than the finder dropping it.
    """
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Attribute) and func.attr == "join"):
            continue
        if not node.args:
            continue
        base = node.args[0]
        parts = [_const_str(a) for a in node.args[1:]]
        if not parts or any(p is None for p in parts):
            continue
        base_name = None
        if isinstance(base, ast.Name):
            base_name = base.id
        elif isinstance(base, ast.Subscript):            # ctx["tree"]
            base_name = _const_str(base.slice)
        if base_name in ROOT_NAMES:
            found.append(Pin("/".join(parts), "repo_path", origin, node.lineno,
                             where.get(node.lineno, "-")))
            continue
        if base_name not in EXTERNAL_NAMES:
            continue
        head = known.get(base_name)
        literal = "/".join(parts) if head is None \
            else head.rstrip("/") + "/" + "/".join(parts)
        found.append(Pin(literal.replace("\\", "/"), "external_path", origin,
                         node.lineno, where.get(node.lineno, "-")))
    return found


def _pairs(tree, origin, where):
    """`("tests/x.py", "test_y")` - a path and a leaf, pinned side by side.

    `exit_nine_reachability.BRAKE_REDS` and `EMPTY_NOTE_TEST` are built this
    way, and the pair is strictly stronger than either half: the file names
    the authority and the leaf names the subject inside it, so the pair can be
    resolved properly where a bare leaf cannot.
    """
    found, consumed = [], set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Tuple, ast.List)):
            continue
        parts = [_const_str(e) for e in node.elts]
        if len(parts) != 2 or any(p is None for p in parts):
            continue
        path, leaf = parts
        if not (path.endswith(".py") and re.match(r"^[A-Za-z_]\w*$", leaf)):
            continue
        found.append(Pin("%s::%s" % (path, leaf), "file_symbol", origin,
                         node.lineno, where.get(node.lineno, "-")))
        #: both halves are now accounted for by the pair, which is the
        #: STRONGER pin. Recording them keeps the generic scan from also
        #: filing the leaf on its own and double-counting the denominator.
        for element, text in zip(node.elts, parts):
            consumed.add((element.lineno, text))
    return found, consumed


def find_pins(source, origin):
    """Every pin this finder can see in `source`. The result is a FLOOR."""
    tree = ast.parse(source)
    where = _binding_for(tree)
    flags = _argparse_defaults(tree)
    known = _known_names(tree, flags)
    found = list(_joins(tree, origin, where, known, flags))
    pairs, swallowed = _pairs(tree, origin, where)
    found.extend(pairs)
    for pin in found:
        pin.literal = pin.literal.replace("\\", "/")
    for pin in found:
        for part in re.split(r"[/:]+", pin.literal):
            swallowed.add((pin.line, part))
    for node in ast.walk(tree):
        text = _const_str(node)
        if text is None:
            continue
        if DOTTED.match(text):
            kind = "dotted"
        elif BARE_LEAF.match(text):
            kind = "leaf"
        elif BARE_PATH.match(text):
            kind = "repo_path"
        elif re.match(r"^[A-Za-z]:[\\/]", text) or text.startswith("\\\\"):
            kind = "external_path"
            text = text.replace("\\", "/")
        else:
            continue
        if (node.lineno, text) in swallowed:
            continue
        found.append(Pin(text, kind, origin, node.lineno,
                         where.get(node.lineno, "-")))
    #: de-duplicate by (kind, literal), keeping the first sighting.
    seen, out = {}, []
    for pin in sorted(found, key=lambda p: (p.line, p.literal)):
        if pin.key() in seen:
            continue
        seen[pin.key()] = pin
        out.append(pin)
    return out


# ------------------------------------------------------------------ the trees

class DiskTree(object):
    """The working tree as it is on disk, right now."""

    def __init__(self, root):
        self.root = root
        self.label = "disk"

    def read(self, rel):
        path = os.path.join(self.root, rel.replace("/", os.sep))
        if not os.path.isfile(path):
            return None
        with open(path, "rb") as handle:
            return handle.read()

    def exists(self, rel):
        return os.path.exists(os.path.join(self.root, rel.replace("/", os.sep)))

    def defines(self, name):
        """{rel path} for every module under tests/ defining `name`, or None
        if the search itself could not be made."""
        where = os.path.join(self.root, "tests")
        if not os.path.isdir(where):
            return None
        pattern = re.compile(r"^\s*(?:def|class)\s+%s\b" % re.escape(name),
                             re.M)
        hits = set()
        for entry in sorted(os.listdir(where)):
            if not entry.endswith(".py"):
                continue
            with open(os.path.join(where, entry), "rb") as handle:
                if pattern.search(handle.read().decode("utf-8", "replace")):
                    hits.add("tests/" + entry)
        return hits


class GitTree(object):
    """A committed ref, read without checking it out.

    `text=True` is NOT used anywhere here: `0237` measured `subprocess` with
    `text=True` decoding git output as cp1250 and producing mojibake that a
    control then passed against. Bytes in, decode once, explicitly. And every
    `GIT_CONFIG*` variable is stripped, because a lane shell inherits a broken
    set from the watcher and every git call then fails.
    """

    def __init__(self, ref, root=ROOT):
        self.ref = ref
        self.root = root
        #: The WHOLE ref. An abbreviated label collided on the first run -
        #: two branches both read `ref:task-pilot` and the two columns were
        #: indistinguishable, which is a table that cannot be checked.
        self.label = "ref:" + ref

    def _git(self, argv):
        env = dict(os.environ)
        for poisoned in [k for k in env if k.startswith("GIT_CONFIG")]:
            del env[poisoned]
        return subprocess.run(["git"] + argv, cwd=self.root, env=env,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def read(self, rel):
        proc = self._git(["show", "%s:%s" % (self.ref, rel)])
        if proc.returncode != 0:
            return None
        return proc.stdout

    def exists(self, rel):
        return self._git(
            ["cat-file", "-e", "%s:%s" % (self.ref, rel)]).returncode == 0

    def defines(self, name):
        proc = self._git(["grep", "-l", "-E",
                          r"^[[:space:]]*(def|class) %s\b" % re.escape(name),
                          self.ref, "--", "tests/"])
        #: git grep exits 1 for "no match" and >1 for a real failure. The two
        #: are different facts: no match is DOES NOT RESOLVE, a failure is
        #: UNKNOWN, and collapsing them is how a blind search reports clean.
        if proc.returncode > 1:
            return None
        return set(line.split(":", 1)[1]
                   for line in proc.stdout.decode("utf-8", "replace").split("\n")
                   if ":" in line)


class TheFilesystem(object):
    """The only authority an absolute path outside the repository has."""

    label = "filesystem"

    def read(self, rel):
        if not os.path.isfile(rel):
            return None
        with open(rel, "rb") as handle:
            return handle.read()

    def exists(self, rel):
        return os.path.exists(rel)


# --------------------------------------------------------------- the resolver

def _module_candidates(dotted):
    """`tests.a.b` -> (tests/a/b.py, []), (tests/a.py, [b]) - longest first."""
    parts = dotted.split(".")
    return [("/".join(parts[:stop]) + ".py", parts[stop:])
            for stop in range(len(parts), 1, -1)]


def resolve_dotted(tree, dotted):
    """(verdict, reason) for a `tests.module[.Class[.method]]` pin.

    By PARSING, never by importing. An import executes the module, so a
    collection error, a missing fixture or a side effect at import time would
    be reported as a missing name - a different fact wearing the same word.
    """
    source = rel = tail = None
    for candidate, remainder in _module_candidates(dotted):
        blob = tree.read(candidate)
        if blob is not None:
            source, rel, tail = blob, candidate, remainder
            break
    if source is None:
        return (DOES_NOT_RESOLVE,
                "no module file for %s in %s (tried %s)"
                % (dotted, tree.label,
                   ", ".join(c for c, _ in _module_candidates(dotted))))
    try:
        parsed = ast.parse(source.decode("utf-8", "replace"))
    except SyntaxError as broken:
        return (UNKNOWN, "%s in %s does not parse (%s) - an unreadable "
                         "authority is UNKNOWN, never a pass"
                         % (rel, tree.label, broken))
    if not tail:
        return RESOLVES, "module file %s" % rel
    scope, path = parsed.body, [rel]
    for name in tail:
        match = [n for n in scope
                 if isinstance(n, (ast.ClassDef, ast.FunctionDef,
                                   ast.AsyncFunctionDef)) and n.name == name]
        if not match:
            have = sorted(n.name for n in scope
                          if isinstance(n, (ast.ClassDef, ast.FunctionDef,
                                            ast.AsyncFunctionDef)))
            return (DOES_NOT_RESOLVE,
                    "%s has no class or def named %r in %s; it has %s"
                    % (" -> ".join(path), name, tree.label,
                       (", ".join(have[:8]) + (" ..." if len(have) > 8 else ""))
                       or "nothing"))
        path.append(name)
        scope = match[0].body
    return RESOLVES, " -> ".join(path)


def resolve_path(tree, rel):
    if tree.exists(rel):
        return RESOLVES, "%s in %s" % (rel, tree.label)
    return DOES_NOT_RESOLVE, "%s is absent from %s" % (rel, tree.label)


def _symbols(source):
    """Every class/def name defined anywhere in a module, at any depth."""
    try:
        parsed = ast.parse(source.decode("utf-8", "replace"))
    except SyntaxError:
        return None
    return set(n.name for n in ast.walk(parsed)
               if isinstance(n, (ast.ClassDef, ast.FunctionDef,
                                 ast.AsyncFunctionDef)))


def resolve_file_symbol(tree, literal):
    """`tests/x.py::test_y` - the file names the authority, the leaf the
    subject. Strictly stronger than a bare leaf, and resolvable."""
    rel, leaf = literal.split("::", 1)
    blob = tree.read(rel)
    if blob is None:
        return DOES_NOT_RESOLVE, "%s is absent from %s" % (rel, tree.label)
    names = _symbols(blob)
    if names is None:
        return (UNKNOWN, "%s in %s does not parse - an unreadable authority "
                         "is UNKNOWN, never a pass" % (rel, tree.label))
    if leaf in names:
        return RESOLVES, "%s defines %s" % (rel, leaf)
    return DOES_NOT_RESOLVE, "%s defines no %s" % (rel, leaf)


def resolve_leaf(tree, leaf):
    """A bare leaf with no module beside it.

    THIS IS THE WEAK FORM, and it is named weak on purpose: it is the exact
    comparison that let `ARemovalRequestWritesARow` pin nothing for a day. All
    it can establish is that SOME module under `tests/` defines the name - not
    that the module the evaluator will actually run defines it, and not that
    the class the evaluator names contains it. A leaf pin that RESOLVES here
    is still a pin worth replacing with a dotted one.
    """
    hits = tree.defines(leaf)
    if hits is None:
        return (UNKNOWN, "%s could not be searched for a def named %r"
                         % (tree.label, leaf))
    if hits:
        return (RESOLVES, "defined in %s%s (WEAK: a leaf names no module, so "
                          "this says only that the name exists somewhere)"
                % (", ".join(sorted(hits)[:3]),
                   " and %d more" % (len(hits) - 3) if len(hits) > 3 else ""))
    return DOES_NOT_RESOLVE, "no module under tests/ in %s defines %r" % (
        tree.label, leaf)


def resolve(pin, tree, filesystem=None):
    """(verdict, reason). An authority that cannot be consulted is UNKNOWN."""
    try:
        if pin.kind == "dotted":
            return resolve_dotted(tree, pin.literal)
        if pin.kind == "repo_path":
            return resolve_path(tree, pin.literal)
        if pin.kind == "file_symbol":
            return resolve_file_symbol(tree, pin.literal)
        if pin.kind == "leaf":
            return resolve_leaf(tree, pin.literal)
        if pin.kind == "external_path":
            if filesystem is None:
                return (UNKNOWN,
                        "%s is outside the repository, so a ref cannot answer "
                        "it; the filesystem is its only authority and it was "
                        "not consulted" % pin.literal)
            if not re.match(r"^([A-Za-z]:/|/|\\\\)", pin.literal):
                return (UNKNOWN,
                        "%r is a FRAGMENT: the base it hangs off does not fold "
                        "to a compile-time constant, so there is no absolute "
                        "path to test. Resolving it relative to the caller's "
                        "cwd would manufacture a verdict, and a fragment whose "
                        "authority cannot be named is UNKNOWN" % pin.literal)
            return resolve_path(filesystem, pin.literal)
    except OSError as blind:
        return UNKNOWN, "the authority could not be read: %s" % blind
    return UNKNOWN, "no resolver for kind %r" % pin.kind


# ------------------------------------- the evaluation-time gate (the repair)

class UnresolvablePin(Exception):
    """A pin with no subject. Raised AT EVALUATION TIME, so the criterion that
    reads it prints UNKNOWN instead of a verdict formed against nothing."""


def require_resolvable(dotted_pins, tree=None, what="this criterion"):
    """Refuse to score `what` unless every pin it reads names something.

    THIS IS THE REPAIR. Before it, `REMOVAL_DEMONSTRATION` named a class that
    has never existed and the row that read it printed MET for every state of
    the tree, because the matcher compared leaf names and the absent class was
    never consulted. A pin is now resolved against the tree the criterion is
    measuring, by parsing it, and an unresolvable pin stops the row.

    Fail closed in both directions: DOES NOT RESOLVE and UNKNOWN both raise.
    A pin whose module will not parse is not evidence that the pin is good.
    """
    tree = tree or DiskTree(ROOT)
    bad = []
    for dotted in dotted_pins:
        verdict, reason = resolve_dotted(tree, dotted)
        if verdict != RESOLVES:
            bad.append((dotted, verdict, reason))
    if bad:
        raise UnresolvablePin(
            "%s is pinned to %d name(s) that do not resolve in %s: %s. A pin "
            "that names nothing is not a weak check, it is a check with no "
            "subject - the row cannot be scored against it, and UNKNOWN never "
            "becomes a pass."
            % (what, len(bad), tree.label,
               "; ".join("%s [%s] %s" % (d, v, r) for d, v, r in bad)))
    #: IN THE ORDER GIVEN, never sorted. Callers hand the result straight to
    #: `unittest`, and this repository has measured inter-module interference
    #: more than once - a gate that silently reorders a run would change what
    #: it is gating.
    return list(dotted_pins)


# ------------------------------------------------------------------- the table

DEFAULT_SOURCES = ("scripts/exit_nine.py",
                   "scripts/exit_nine_reachability.py",
                   "scripts/obs2_nine.py")


def collect(sources, tree):
    """([(origin, [Pin])], [unreadable]) - a source that cannot be read or
    parsed is NAMED, never skipped silently, because a finder that read
    nothing reports the same clean table as one that found nothing."""
    out, blind = [], []
    for rel in sources:
        blob = tree.read(rel)
        if blob is None:
            blind.append("%s (absent from %s)" % (rel, tree.label))
            continue
        try:
            out.append((rel, find_pins(blob.decode("utf-8", "replace"), rel)))
        except SyntaxError as broken:
            blind.append("%s (does not parse: %s)" % (rel, broken))
    return out, blind


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--at", action="append", default=[],
                        help="a git ref to resolve against; repeatable. "
                             "'disk' means this working tree.")
    parser.add_argument("--source", action="append", default=[],
                        help="rel path of an evaluator to scan; repeatable")
    parser.add_argument("--source-ref",
                        help="read the --source files from this ref instead "
                             "of from disk")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--only-unresolved", action="store_true")
    args = parser.parse_args()

    refs = args.at or ["disk"]
    trees = [DiskTree(ROOT) if r == "disk" else GitTree(r) for r in refs]
    filesystem = TheFilesystem()

    source_tree = GitTree(args.source_ref) if args.source_ref else DiskTree(ROOT)
    groups, blind = collect(args.source or DEFAULT_SOURCES, source_tree)

    rows = []
    for origin, pins in groups:
        for pin in pins:
            got = pin.as_dict()
            got["verdicts"] = {}
            for tree in trees:
                verdict, reason = resolve(pin, tree, filesystem)
                got["verdicts"][tree.label] = dict(verdict=verdict,
                                                   reason=reason)
            rows.append(got)

    shown = rows
    if args.only_unresolved:
        shown = [r for r in rows
                 if any(v["verdict"] != RESOLVES for v in r["verdicts"].values())]

    if args.json:
        print(json.dumps(dict(sources=[o for o, _ in groups], unreadable=blind,
                              trees=[t.label for t in trees], pins=shown),
                         indent=2))
        return 2 if blind else 0

    print("=" * 108)
    print("EVERY PIN IN THE EXIT-CRITERIA MACHINERY, RESOLVED TO A SUBJECT")
    print("=" * 108)
    print("sources read   %s" % ", ".join(o for o, _ in groups))
    print("source of      %s" % source_tree.label)
    print("resolved at    %s" % ", ".join(t.label for t in trees))
    if blind:
        print("UNREADABLE     %s" % "; ".join(blind))
        print("               these contribute NO pins and the denominator "
              "below excludes them")
    print("denominator    %d pin(s), found by parsing the AST for string "
          "constants." % len(rows))
    print("               THIS IS A FLOOR - a pin assembled at runtime is not "
          "a constant and")
    print("               this finder cannot see it. See C3 in "
          "scripts/exit_pins_controls.py.")
    print()
    #: Column width from the LABELS, never a constant: two refs abbreviated
    #: to a fixed width collided on the first run and the two verdict columns
    #: became indistinguishable.
    wide = max([17] + [len(t.label) for t in trees])
    head = "%-4s %-11s %-14s %-58s" % ("#", "kind", "where", "literal")
    for tree in trees:
        head += " %-*s" % (wide, tree.label)
    print(head)
    print("-" * len(head))
    tally = {}
    for index, row in enumerate(shown, 1):
        literal = row["literal"]
        line = "%-4d %-11s %-14s %-58s" % (
            index, row["kind"].replace("_path", ""), row["context"][:14],
            literal if len(literal) <= 58 else ".." + literal[-56:])
        for tree in trees:
            verdict = row["verdicts"][tree.label]["verdict"]
            tally[(tree.label, verdict)] = tally.get((tree.label, verdict), 0) + 1
            line += " %-*s" % (wide, verdict)
        print(line)
    print("-" * len(head))
    for tree in trees:
        print("%-*s  RESOLVES %d   DOES NOT RESOLVE %d   UNKNOWN %d"
              % (wide, tree.label,
                 tally.get((tree.label, RESOLVES), 0),
                 tally.get((tree.label, DOES_NOT_RESOLVE), 0),
                 tally.get((tree.label, UNKNOWN), 0)))
    print()
    worst = 0
    for row in shown:
        for tree in trees:
            got = row["verdicts"][tree.label]
            if got["verdict"] != RESOLVES:
                worst = max(worst, 1 if got["verdict"] == DOES_NOT_RESOLVE else 2)
                print("  %-14s %-9s %s (%s:%d)"
                      % (tree.label[:14], row["kind"].replace("_path", ""),
                         row["literal"], row["origin"], row["line"]))
                print("      %s -> %s" % (got["verdict"], got["reason"]))
    return worst


if __name__ == "__main__":
    sys.exit(main())
