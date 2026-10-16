#!/usr/bin/env python3
"""Detect a LIVE stale `.pyc`: one CPython will accept as valid whose bytecode
does not match a fresh compile of the source it claims to be.

Written for TASK 0176 (qwen), 2026-10-16. Read-only: it opens files, writes
nothing, deletes nothing, and never imports the code it inspects.

WHY THIS EXISTS
---------------
A timestamp-mode `.pyc` (the default) records exactly two facts about its
source: `int(st_mtime)` truncated to 32 bits, and `st_size`. CPython reuses the
cached bytecode whenever both still match. So a mutation of the SAME byte
length, reverted inside the SAME whole second, leaves both facts intact and the
mutant's bytecode keeps being imported - permanently, because the source's mtime
never moves again. The source is hash-identical, `git status` is clean, and the
module that executes is the mutant.

    py -3 docs/qwen-tasks/stale_pyc_scan.py <tree> [<tree> ...]

Exit status: 0 if every accepted pyc matches its source, 1 if any is stale,
2 if a pyc could not be read at all (UNKNOWN, which is not PASS).

TWO EARLIER VERSIONS OF THIS WERE WRONG, both with false positives. Kept here
because the next person will reach for the same two shortcuts:

  v1 compiled the source's RAW BYTES. The import system decodes first (BOM,
     encoding cookie, universal newlines). In a CRLF tree every file with a
     multi-line string literal looked stale, because the fresh compile kept
     `\r\n` inside docstrings and the cached one did not. Fixed by using
     `importlib.util.decode_source`, which is what the import system uses.

  v2 compared `marshal.dumps()` of the two code objects. Marshal's
     reference-sharing flags depend on object IDENTITY, not value, so two
     semantically identical code objects serialise to different bytes. It
     reported 4 of 122 stale in `qwc`; a recursive field walk found ZERO
     differences in all four. All four were false.

v3 compares the recursive code-object fields. A difference there is a real
difference in what would execute.
"""

import importlib.util
import marshal
import pathlib
import struct
import sys
import types

#: Every field of a code object that a semantic change to the source can move.
#: `co_consts` and the nested code objects are walked separately, below.
FIELDS = (
    "co_name", "co_qualname", "co_argcount", "co_posonlyargcount",
    "co_kwonlyargcount", "co_nlocals", "co_stacksize", "co_flags",
    "co_firstlineno", "co_code", "co_names", "co_varnames", "co_freevars",
    "co_cellvars", "co_linetable", "co_exceptiontable",
)


def differences(cached, fresh, path="<module>", out=None):
    """Names of every field where the cached code object differs from a fresh
    compile. Empty list means the cache is faithful."""
    out = [] if out is None else out
    for field in FIELDS:
        if getattr(cached, field, None) != getattr(fresh, field, None):
            out.append("%s::%s" % (path, field))
    cached_code = [k for k in cached.co_consts if isinstance(k, types.CodeType)]
    fresh_code = [k for k in fresh.co_consts if isinstance(k, types.CodeType)]
    cached_rest = [k for k in cached.co_consts if not isinstance(k, types.CodeType)]
    fresh_rest = [k for k in fresh.co_consts if not isinstance(k, types.CodeType)]
    if cached_rest != fresh_rest:
        out.append("%s::co_consts" % path)
    if [k.co_name for k in cached_code] != [k.co_name for k in fresh_code]:
        out.append("%s::nested" % path)
    for a, b in zip(cached_code, fresh_code):
        differences(a, b, path + "/" + a.co_name, out)
    return out


def scan(root):
    """Returns (seen, accepted, stale_list, unreadable_list) for one tree."""
    root = pathlib.Path(root).resolve()
    seen = accepted = 0
    stale, unreadable = [], []
    for pyc in sorted(root.rglob("__pycache__/*.pyc")):
        if ".git" in pyc.parts:
            continue
        seen += 1
        parts = pyc.name.split(".")
        # A pyc for another interpreter cannot be served to this one.
        if len(parts) < 3 or parts[1] != sys.implementation.cache_tag:
            continue
        src = pyc.parent.parent / (parts[0] + ".py")
        if not src.exists():
            continue
        try:
            raw = pyc.read_bytes()
            magic, flags, field1, field2 = struct.unpack("<4sIII", raw[:16])
        except Exception as exc:
            unreadable.append((pyc, "%s: %s" % (type(exc).__name__, exc)))
            continue
        if magic != importlib.util.MAGIC_NUMBER:
            continue
        if flags & 1:
            # Hash-based (PEP 552). CPython verifies it by content itself.
            continue
        stat = src.stat()
        would_accept = (field1 == (int(stat.st_mtime) & 0xFFFFFFFF)
                        and field2 == (stat.st_size & 0xFFFFFFFF))
        if not would_accept:
            continue        # CPython will recompile it; it cannot go stale
        accepted += 1
        try:
            cached = marshal.loads(raw[16:])
            text = importlib.util.decode_source(src.read_bytes())
            fresh = compile(text, cached.co_filename, "exec", dont_inherit=True)
        except Exception as exc:
            unreadable.append((pyc, "%s: %s" % (type(exc).__name__, exc)))
            continue
        diff = differences(cached, fresh)
        if diff:
            stale.append((pyc, diff))
    return root, seen, accepted, stale, unreadable


def main(argv):
    trees = argv[1:] or ["."]
    worst = 0
    for tree in trees:
        root, seen, accepted, stale, unreadable = scan(tree)
        print(root)
        print("  pyc files seen            %d" % seen)
        print("  ACCEPTED as valid         %d" % accepted)
        print("  SEMANTICALLY STALE        %d" % len(stale))
        for pyc, diff in stale:
            print("    STALE %s" % pyc)
            for name in diff[:8]:
                print("          %s" % name)
        if unreadable:
            print("  UNREADABLE (UNKNOWN, not PASS)  %d" % len(unreadable))
            for pyc, why in unreadable:
                print("    %s  %s" % (pyc, why))
        if stale:
            worst = max(worst, 1)
        if unreadable:
            worst = max(worst, 2)
    return worst


if __name__ == "__main__":
    sys.exit(main(sys.argv))
