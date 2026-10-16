# TASK-0078 -- the load-proof TASK-0075 proposed and left unwritten.
#
# Question it answers: did the module object an import just produced come
# from the bytes that are on disk NOW?  A timestamp-mode pyc (flags=0, this
# estate's only mode) is validated against (whole-second mtime, size), so a
# same-size plant written with the mtime rolled back ns-exact makes the
# import system serve pre-plant bytecode while the disk holds the plant --
# TASK-0075's P3.  This proof compares the CODE THE IMPORT WOULD RUN
# against a fresh compile of the disk bytes.
#
# Header read chosen, and why the other two were rejected:
#
#   CHOSEN (b, refined) -- unmarshal module.__cached__'s BODY and compare it
#     against marshal.dumps(compile(disk_bytes, co_filename-of-loaded)).
#     The body is the bytecode itself: it cannot be made to equal a fresh
#     compile of different bytes, whatever the header claims.  The pyc body
#     embeds co_filename, and 0075 measured that py_compile and an import
#     compile identical source to different pyc bytes differing by exactly
#     that -- so the fresh compile copies co_filename from the loaded code
#     and the comparison is about the code, not the path spelling.
#   REJECTED (a) -- the pyc header's (mtime, size) pair vs the source stat:
#     P3 forges exactly that pair by construction (same-size edit + ns-exact
#     mtime rollback).  0075's own proposed one-liner was this read, and it
#     says FRESH on the very plant it exists to catch.
#   REJECTED (c) -- a source sha256 read back through the loader: only
#     PEP-552 hash-based pycs carry a source hash, and nothing in this
#     estate produces them (measured flags=0).  There is no loader field
#     to read it from.
#
# Verdicts are fail-closed: pyc missing/unreadable/short, magic mismatch or
# flags != 0 means the provenance is unprovable, and that is UNKNOWN --
# never "clean".
#
# Equality is decided by marshal bytes first; if the bytes differ but the
# code objects are structurally identical (marshal ref-flag layout is an
# artefact of the dump walk, not of the code), the verdict is still CLEAN
# and both facts are printed.  Which branch fired is visible either way;
# C1 (clean file) and C2 (P3 plant) are the empirical validation of both.
import hashlib
import importlib.util
import marshal
import struct


def _sha(b):
    return hashlib.sha256(b).hexdigest()


def _code_struct(code):
    """Structural identity of a code object.  co_filename and line tables
    are excluded on purpose: the filename is matched from the loaded code
    before compiling, and positions are not semantics."""
    return (code.co_name, code.co_argcount, code.co_kwonlyargcount,
            code.co_nlocals, code.co_stacksize, code.co_flags,
            code.co_code, code.co_names, code.co_varnames,
            code.co_freevars, code.co_cellvars,
            tuple(_code_struct(c) if isinstance(c, type(code)) else c
                  for c in code.co_consts))


def load_proof(module):
    pyc = getattr(module, "__cached__", None)
    src = getattr(module, "__file__", None)
    if not pyc or not src:
        return {"verdict": "UNKNOWN", "why": "module has no __cached__/__file__"}
    try:
        raw = open(pyc, "rb").read()
    except OSError as exc:
        return {"verdict": "UNKNOWN", "why": "pyc unreadable: %s" % exc}
    if len(raw) < 16:
        return {"verdict": "UNKNOWN", "why": "pyc shorter than a header"}
    magic, flags = struct.unpack("<4sI", raw[:8])
    if magic != importlib.util.MAGIC_NUMBER:
        return {"verdict": "UNKNOWN", "why": "magic mismatch (other interpreter)"}
    if flags != 0:
        return {"verdict": "UNKNOWN",
                "why": "flags=%d, not timestamp-mode" % flags}
    loaded = marshal.loads(raw[16:])
    disk = open(src, "rb").read()
    fresh = compile(disk, loaded.co_filename, "exec")
    loaded_body, fresh_body = raw[16:], marshal.dumps(fresh)
    struct_equal = _code_struct(loaded) == _code_struct(fresh)
    out = {"verdict": None,
           "src": src, "pyc": pyc,
           "pyc_body_sha256": _sha(loaded_body),
           "fresh_body_sha256": _sha(fresh_body),
           "marshal_bytes_equal": loaded_body == fresh_body,
           "structure_equal": struct_equal,
           "clean_by": None}
    if loaded_body == fresh_body:
        out["verdict"], out["clean_by"] = "CLEAN", "marshal-bytes-equal"
    elif struct_equal:
        out["verdict"], out["clean_by"] = "CLEAN", "structure-equal"
    else:
        out["verdict"] = "STALE BYTECODE"
    return out
