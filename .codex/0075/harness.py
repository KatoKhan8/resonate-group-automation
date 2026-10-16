# TASK-0075 mutation instrument. Stdlib only - this file itself never imports
# src.*, because an import between plant-write and mtime set-back would
# recompile the pyc from the mutant and destroy the P3 condition.
#
#   py -3 .codex\0075\harness.py status
#   py -3 .codex\0075\harness.py baseline
#   py -3 .codex\0075\harness.py plant P1|P2|P3|NOOP
#   py -3 .codex\0075\harness.py revert P1|P2|P3|NOOP
#
# Every phase prints a labeled block; the shell tees it to .codex/0075/.
import hashlib
import json
import os
import re
import struct
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, "src", "spendledger.py")
PYC = os.path.join(ROOT, "src", "__pycache__", "spendledger.cpython-314.pyc")
EVID = os.path.join(ROOT, ".codex", "0075")
TESTMOD = "tests.test_an_unknown_price_is_not_a_free_call"
PRE_PLANT_SHA = "91d21fb063743e0e660cac53273dc7e62bfe110ea85bc3593eec3d3dbab466b9"

# src/spendledger.py on disk in this tree is LF (measured CR=0, 58521 B).
GUARD = b"    if not priced and governed:\n"
PLANTS = {
    # P1: TASK 0073's M2 shape - deadens the guard, +10 bytes.
    "P1": b"    if False and not priced and governed:\n",
    # P2/P3: 'not ' (4 bytes) swapped for '0 * ' (4 bytes) - same byte length,
    # guard condition always falsy, guard deadened identically to P1.
    "P2": b"    if 0 * priced and governed:\n",
    "P3": b"    if 0 * priced and governed:\n",
    # no-op: comment appended, +25 bytes, semantics untouched (C1 leg 2).
    # (First attempt expected +26 - a miscount the size assert caught pre-write.)
    "NOOP": b"    if not priced and governed:  # TASK-0075 no-op plant\n",
}


def sha(b):
    return hashlib.sha256(b).hexdigest()


def fstat():
    st = os.stat(SRC)
    return st.st_size, st.st_mtime_ns, int(st.st_mtime)


def pyc_header():
    with open(PYC, "rb") as fh:
        magic, flags, hmtime, hsize = struct.unpack("<IIII", fh.read(16))
    return {"flags": flags, "mtime": hmtime, "size": hsize,
            "sha256": sha(open(PYC, "rb").read())}


def wait_fresh_second(avoid_header_mtime=None):
    """Sleep until (a) the wall clock is in a NEW whole second versus
    avoid_header_mtime, if given, and (b) the fractional part is early enough
    that a fast write cannot spill into the next second."""
    while True:
        t = time.time()
        if avoid_header_mtime is not None and int(t) <= avoid_header_mtime:
            time.sleep(0.05)
            continue
        if t % 1.0 > 0.35:
            time.sleep(0.05)
            continue
        return int(t)


def prime():
    """Recompile the pyc from the CURRENT disk bytes without deleting anything
    (deletion under __pycache__ is restricted in shared trees; overwrite is
    not deletion)."""
    subprocess.run([sys.executable, "-m", "py_compile", SRC], check=True,
                   cwd=ROOT)


def run_tests(tag):
    out_path = os.path.join(EVID, tag + ".out")
    with open(out_path, "wb") as out:
        proc = subprocess.run(
            [sys.executable, "-m", "unittest", TESTMOD, "-v"],
            cwd=ROOT, stdout=out, stderr=subprocess.STDOUT)
    text = open(out_path, "r", encoding="utf-8", errors="replace").read()
    ran = re.search(r"^Ran (\d+) tests?", text, re.M)
    fails = re.findall(r"^(FAIL|ERROR): (\S+) \(([^)]+)\)", text, re.M)
    red = sorted(set(full for _, _, full in fails))
    n_fail = len(re.findall(r"^FAIL:", text, re.M))
    n_err = len(re.findall(r"^ERROR:", text, re.M))
    m = re.search(r"^OK(?: \(skipped=(\d+)\))?", text, re.M)
    skipped = 0
    ok = bool(m)
    if not ok:
        m2 = re.search(
            r"^FAILED \(failures=(\d+)(?:, errors=(\d+))?"
            r"(?:, skipped=(\d+))?\)", text, re.M)
        if m2:
            n_fail, n_err, skipped = (int(m2.group(1) or 0),
                                      int(m2.group(2) or 0),
                                      int(m2.group(3) or 0))
        else:
            m3 = re.search(r"^FAILED \(skipped=(\d+)\)", text, re.M)
            if m3:
                skipped = int(m3.group(1))
    with open(os.path.join(EVID, "reference.json")) as fh:
        ref = json.load(fh)
    green = sorted(set(ref["canonical"]) - set(red))
    ran_n = int(ran.group(1)) if ran else -1
    accounted = len(green) + len(red) + skipped
    c3 = (ran_n == accounted and len(red) == n_fail + n_err)
    newly_red = sorted(set(red) - set(ref["red"]))
    newly_green = sorted(set(ref["red"]) - set(red))
    result = {
        "tag": tag, "exit": proc.returncode, "ran": ran_n, "ok": ok,
        "failures": n_fail, "errors": n_err, "skipped": skipped,
        "red": red, "green_count": len(green),
        "newly_red_vs_reference": newly_red,
        "newly_green_vs_reference": newly_green,
        "c3_accounted": accounted, "c3_ok": c3,
        "verdict": ("ACCOUNTED" if c3 else "UNKNOWN-C3-REFUSED"),
    }
    print(json.dumps(result, indent=1))
    return result


def do_status():
    b = open(SRC, "rb").read()
    size, mns, msec = fstat()
    print("file sha256 :", sha(b))
    print("file size   :", size, " CR:", b.count(b"\r"))
    print("file mtime_ns:", mns, "(whole second", msec, ")")
    print("guard count :", b.count(GUARD))
    print("pyc         :", json.dumps(pyc_header()))


def do_baseline():
    b = open(SRC, "rb").read()
    assert sha(b) == PRE_PLANT_SHA, "baseline refuses: tree not pristine"
    assert b.count(GUARD) == 1, "guard pattern count != 1"
    # canonical test names, enumerated WITHOUT running them
    code = ("import json, unittest;"
            "s=unittest.TestLoader().loadTestsFromName('%s');"
            "ids=[]; stack=[s]\n"
            "while stack:\n"
            "    t=stack.pop()\n"
            "    (stack.extend(t) if hasattr(t,'_tests') else ids.append(t.id()))\n"
            "print(json.dumps(sorted(ids)))" % TESTMOD)
    raw = subprocess.run([sys.executable, "-c", code], cwd=ROOT,
                         capture_output=True, text=True, check=True).stdout
    canonical = json.loads(raw.strip().splitlines()[-1])
    assert len(canonical) == 13, "expected 13 tests, enumerated %d" % len(canonical)
    prime()
    h = pyc_header()
    size, mns, msec = fstat()
    print("canonical names (%d):" % len(canonical))
    for n in canonical:
        print("   ", n)
    print("after py_compile: header mtime=%d size=%d | file second=%d size=%d"
          " | match=%s" % (h["mtime"], h["size"], msec, size,
                           h["mtime"] == msec and h["size"] == size))
    print("baseline pyc sha256:", h["sha256"])
    with open(os.path.join(EVID, "reference.json"), "w") as fh:
        json.dump({"canonical": canonical, "red": [], "ran": 13}, fh)
    print("--- baseline run ---")
    run_tests("baseline-run")
    print("--- baseline probe (fresh process, pristine tree) ---")
    subprocess.run([sys.executable, os.path.join(EVID, "probe.py"),
                    "baseline-probe"], cwd=ROOT)
    print("pyc sha after run:", pyc_header()["sha256"])


def do_plant(tag):
    plant = PLANTS[tag]
    b = open(SRC, "rb").read()
    assert sha(b) == PRE_PLANT_SHA, "plant %s refuses: tree not pristine" % tag
    assert b.count(GUARD) == 1, "guard pattern count != 1"
    size0, mns0, msec0 = fstat()
    with open(os.path.join(EVID, "backup-%s.py" % tag), "wb") as fh:
        fh.write(b)
    if tag in ("P2",):
        wait_fresh_second(avoid_header_mtime=pyc_header()["mtime"])
    if tag in ("P2", "NOOP", "P1"):
        wait_fresh_second()
    new = b.replace(GUARD, plant)
    assert new != b and new.count(plant) == 1
    assert len(new) == len(b) + (0 if tag in ("P2", "P3") else
                                 (10 if tag == "P1" else 25)), \
        "unexpected size delta for %s" % tag
    with open(SRC, "wb") as fh:
        fh.write(new)
    if tag == "P3":
        # set the mtime back EXACTLY to the pre-plant nanoseconds
        os.utime(SRC, ns=(os.stat(SRC).st_atime_ns, mns0))
    size1, mns1, msec1 = fstat()
    h = pyc_header()
    print("plant %s applied" % tag)
    print("  planted line: %r" % plant)
    print("  size  : %d -> %d (delta %+d, size-identical=%s)"
          % (size0, size1, size1 - size0, size1 == size0))
    print("  sha256: %s -> %s" % (PRE_PLANT_SHA[:16] + "...",
                                  sha(open(SRC, 'rb').read())))
    print("  mtime : set-back=%s  readback_ns=%d  readback_second=%d"
          % (("to %d ns (second %d)" % (mns0, msec0)) if tag == "P3"
             else "none", mns1, msec1))
    print("  pyc header: flags=%d mtime=%d size=%d | file second=%d size=%d"
          " | header-would-reuse-stale-bytes=%s"
          % (h["flags"], h["mtime"], h["size"], msec1, size1,
             h["mtime"] == msec1 and h["size"] == size1))
    if tag == "P3":
        print("  C4: set ns %d ; read back ns %d ; identical=%s ; "
              "shares whole second with pyc header=%s ; size matches=%s"
              % (mns0, mns1, mns0 == mns1,
                 h["mtime"] == msec1, h["size"] == size1))
    with open(os.path.join(EVID, "state-%s.json" % tag), "w") as fh:
        json.dump({"pristine_mtime_ns": mns0, "pristine_size": size0}, fh)


def do_revert(tag):
    with open(os.path.join(EVID, "backup-%s.py" % tag), "rb") as fh:
        b = fh.read()
    with open(os.path.join(EVID, "state-%s.json" % tag)) as fh:
        st = json.load(fh)
    with open(SRC, "wb") as fh:
        fh.write(b)
    os.utime(SRC, ns=(os.stat(SRC).st_atime_ns, st["pristine_mtime_ns"]))
    size, mns, msec = fstat()
    got = sha(open(SRC, "rb").read())
    print("revert %s: sha256=%s  pre-plant-hash=%s  EQUAL=%s"
          % (tag, got, PRE_PLANT_SHA, got == PRE_PLANT_SHA))
    print("  size=%d mtime_ns=%d (pristine %d) restored=%s"
          % (size, mns, st["pristine_mtime_ns"],
             mns == st["pristine_mtime_ns"]))
    assert got == PRE_PLANT_SHA, "REVERT FAILED for " + tag


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "status":
        do_status()
    elif cmd == "baseline":
        do_baseline()
    elif cmd == "plant":
        do_plant(sys.argv[2].upper())
    elif cmd == "revert":
        do_revert(sys.argv[2].upper())
    elif cmd == "run":
        run_tests(sys.argv[2])
    else:
        raise SystemExit("unknown command " + cmd)
