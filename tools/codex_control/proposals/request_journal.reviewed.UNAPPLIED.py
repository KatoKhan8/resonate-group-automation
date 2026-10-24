# request_journal.UNAPPLIED.py
import json, os, re
import pathlib

SCHEMA = "request-journal/1"
MAXF, MAXR, MAXL = 1 << 20, 4096, 4096
_ID = re.compile(r"[A-Za-z0-9_.-]{1,64}")
_OUT = ("ok", "error", "unknown", "interrupted")


def _isint(v):
    return type(v) is int


def _okid(v):
    return type(v) is str and _ID.fullmatch(v) is not None


def R(status, reason, total=None, cap=None, aid=None, permit=False):
    rem = cap - total if (total is not None and cap is not None) else None
    return {"status": status, "reason": reason, "total_consumed": total,
            "remaining": rem, "attempt_id": aid, "dispatch_permitted": permit,
            "producer_authenticated": False, "send_allowed": False,
            "coverage_proven": False}


def _check(path, bid, bc, cap, **ids):
    if not (_okid(bid) and _isint(bc) and _isint(cap)
            and 0 <= bc <= cap and 1 <= cap <= 1000000):
        return None, R("REFUSED", "INVALID_BASELINE")
    ok = True
    if type(path) is str:
        ok = "\0" not in path and os.path.isabs(path)
        p = path
    elif type(path) in (pathlib.PosixPath, pathlib.WindowsPath):
        ok = path.is_absolute() and "\0" not in str(path)
        p = str(path)
    else:
        ok = False
    for k, v in ids.items():
        ok = ok and ((v in _OUT) if k == "outcome" and type(v) is str else
                     (_okid(v) if k != "outcome" else False))
    if not ok or not os.path.basename(p):
        return None, R("REFUSED", "INVALID_INPUT")
    return p, None


def _pairs(pairs):
    d = {}
    for k, v in pairs:
        if k in d:
            raise ValueError("dup")
        d[k] = v
    return d


def _bad(_):
    raise ValueError("nonfinite")


def _parse(data, bid, bc, cap):
    if len(data) > MAXF:
        return "BOUND"
    if not data.endswith(b"\n"):
        return "CORRUPT"
    lines = data.split(b"\n")[:-1]
    if len(lines) > MAXR or any(len(x) > MAXL for x in lines):
        return "BOUND"
    res, fin = {}, set()
    for i, ln in enumerate(lines):
        try:
            o = json.loads(ln.decode("utf-8"), object_pairs_hook=_pairs,
                           parse_constant=_bad)
        except (ValueError, UnicodeError, TypeError, RecursionError):
            return "CORRUPT"
        if type(o) is not dict:
            return "CORRUPT"
        if i == 0:
            if set(o) != {"schema", "baseline_id", "baseline_count", "hard_cap"} \
                    or o["schema"] != SCHEMA or not _okid(o["baseline_id"]) \
                    or not _isint(o["baseline_count"]) or not _isint(o["hard_cap"]):
                return "CORRUPT"
            if (o["baseline_id"], o["baseline_count"], o["hard_cap"]) != (bid, bc, cap):
                return "MISMATCH"
            continue
        t = o.get("t")
        if t == "r" and set(o) == {"t", "n", "attempt_id", "scope_id"}:
            if not (_isint(o["n"]) and o["n"] == len(res) + 1 and _okid(o["attempt_id"])
                    and _okid(o["scope_id"]) and o["attempt_id"] not in res):
                return "CORRUPT"
            res[o["attempt_id"]] = o["scope_id"]
        elif t == "f" and set(o) == {"t", "attempt_id", "outcome"}:
            a = o["attempt_id"]
            if not (type(a) is str and a in res and a not in fin
                    and type(o["outcome"]) is str and o["outcome"] in _OUT):
                return "CORRUPT"
            fin.add(a)
        else:
            return "CORRUPT"
    if not lines or bc + len(res) > cap:
        return "CORRUPT"
    return bc + len(res), res, fin


def _line(o):
    return (json.dumps(o, separators=(",", ":"), allow_nan=False) + "\n").encode("ascii")


def _write(f, b):
    f.write(b)
    f.flush()
    os.fsync(f.fileno())


def _body(p, bid, bc, cap, mode, aid, extra):
    if mode == "init":
        try:
            fd = os.open(p, os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0), 0o600)
        except FileExistsError:
            pass
        else:
            with os.fdopen(fd, "wb") as f:
                _write(f, _line({"schema": SCHEMA, "baseline_id": bid,
                                 "baseline_count": bc, "hard_cap": cap}))
            return R("OK", "INITIALIZED", bc, cap)
    try:
        with open(p, "rb") as f:
            data = f.read(MAXF + 1)
    except FileNotFoundError:
        return R("REFUSED", "MISSING")
    st = _parse(data, bid, bc, cap)
    if type(st) is str:
        return R("REFUSED", st)
    total, res, fin = st
    if mode in ("init", "inspect"):
        return R("OK", "UNRESOLVED_PRESENT" if len(res) > len(fin) else "OK", total, cap)
    if mode == "reserve":
        if aid in res:
            return R("REFUSED", "ATTEMPT_REUSED", total, cap)
        if len(res) > len(fin):
            return R("REFUSED", "UNRESOLVED", total, cap)
        if total >= cap:
            return R("REFUSED", "CAP_EXHAUSTED", total, cap)
        rec = _line({"t": "r", "n": len(res) + 1, "attempt_id": aid, "scope_id": extra})
        ok = "RESERVED"
        total += 1
    else:
        if aid not in res:
            return R("REFUSED", "UNKNOWN_ATTEMPT", total, cap)
        if aid in fin:
            return R("REFUSED", "ALREADY_FINISHED", total, cap)
        rec = _line({"t": "f", "attempt_id": aid, "outcome": extra})
        ok = "FINISHED"
    if len(data) + len(rec) > MAXF or len(data.split(b"\n")) > MAXR:
        return R("REFUSED", "BOUND", st[0], cap)
    try:
        with open(p, "ab") as f:
            _write(f, rec)
    except (OSError, ValueError):
        return R("UNKNOWN", "IO_ERROR")
    return R(ok, "OK", total, cap, aid, ok == "RESERVED")


def _op(p, bid, bc, cap, mode, aid=None, extra=None):
    try:
        if not os.path.isdir(os.path.dirname(p)):
            return R("REFUSED", "PARENT_MISSING")
    except (OSError, ValueError):
        return R("UNKNOWN", "IO_ERROR")
    try:
        fd = os.open(p + ".lock", os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        return R("LOCKED", "LOCKED")
    except OSError:
        return R("UNKNOWN", "IO_ERROR")
    try:
        return _body(p, bid, bc, cap, mode, aid, extra)
    except (OSError, ValueError, TypeError, UnicodeError):
        return R("UNKNOWN", "IO_ERROR")
    finally:
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            os.unlink(p + ".lock")
        except OSError:
            pass


def initialize(path, *, baseline_id, baseline_count, hard_cap):
    p, e = _check(path, baseline_id, baseline_count, hard_cap)
    return e or _op(p, baseline_id, baseline_count, hard_cap, "init")


def inspect(path, *, baseline_id, baseline_count, hard_cap):
    p, e = _check(path, baseline_id, baseline_count, hard_cap)
    return e or _op(p, baseline_id, baseline_count, hard_cap, "inspect")


def reserve(path, *, baseline_id, baseline_count, hard_cap, attempt_id, scope_id):
    p, e = _check(path, baseline_id, baseline_count, hard_cap,
                  attempt_id=attempt_id, scope_id=scope_id)
    return e or _op(p, baseline_id, baseline_count, hard_cap, "reserve", attempt_id, scope_id)


def finish(path, *, baseline_id, baseline_count, hard_cap, attempt_id, outcome):
    p, e = _check(path, baseline_id, baseline_count, hard_cap,
                  attempt_id=attempt_id, outcome=outcome)
    return e or _op(p, baseline_id, baseline_count, hard_cap, "finish", attempt_id, outcome)
