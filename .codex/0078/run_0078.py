# TASK-0078 single-session driver.  Runs, in order:
#   phase 0  baseline asserts on src/spendledger.py and its pyc (fail-closed)
#   phase 1  C1 -- the load-proof says CLEAN twice (as-found pyc, freshly
#            py_compiled pyc), same session
#   phase 2  C2 -- 0075's P3 reconstructed exactly: same file, same
#            `not ` -> `0 * ` same-size edit, same ns-exact mtime rollback
#            (set and read back, both quoted).  Then: the suite still says
#            OK, 0075's probe still sees the pre-plant guard, and the
#            load-proof says STALE BYTECODE.  Revert verified by sha256 of
#            the working file's own bytes; both ns timestamps restored.
#   phase 3  section 3 -- the unnamed-kill-set census over the lane file's
#            own bytes (read-only)
#   phase 4  C3 -- the parser's negative control on a byte-copy of the lane
#            file: a planted named kill-set must NOT be listed, a planted
#            empty kill-set MUST be
#   phase 5  C4 -- refuse the verdict unless C1, C2 and C3 each showed both
#            of their states
#
# This file never imports anything under src/ -- the import under test
# happens only inside fresh proof_runner subprocesses, after the driver's
# last write to disk (0075's discipline: an import between the plant write
# and the mtime set-back would recompile the pyc and destroy the plant).
import hashlib
import json
import os
import re
import struct
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
SRC = os.path.join(ROOT, "src", "spendledger.py")
PYC = os.path.join(ROOT, "src", "__pycache__",
                   "spendledger.cpython-314.pyc")
LANE = r"C:\Users\Zvonimir\Desktop\resonate-ops\LANE-glm.md"
ART = r"C:\Users\Zvonimir\Desktop\resonate-ops\TASK-0078"
TESTMOD = "tests.test_an_unknown_price_is_not_a_free_call"

BASE_SHA = "a51a60bee5077fdd3b0deedbbbded71a90971f49b2be19ce30858224b2dad7db"
BASE_SIZE = 59007
BASE_MTIME_NS = 1792144718123314700
GUARD = b"    if not priced and governed:\n"
PLANT = b"    if 0 * priced and governed:\n"

PY = sys.executable


def sha(b):
    return hashlib.sha256(b).hexdigest()


def run(cmd):
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True)
    return (p.stdout.decode("utf-8", "replace"),
            p.stderr.decode("utf-8", "replace"), p.returncode)


def pyc_header():
    with open(PYC, "rb") as fh:
        magic, flags, hmtime, hsize = struct.unpack("<IIII", fh.read(16))
    return magic, flags, hmtime, hsize


def proof_leg(label):
    out, err, rc = run([PY, os.path.join(HERE, "proof_runner.py"), label])
    i = out.find("{")
    res = json.loads(out[i:]) if i >= 0 else {}
    print("[proof %-16s] verdict=%-13s clean_by=%s"
          % (label, res.get("verdict"), res.get("clean_by")))
    print("    pyc_body  %s" % res.get("pyc_body_sha256"))
    print("    fresh     %s  bytes_equal=%s structure_equal=%s"
          % (res.get("fresh_body_sha256"), res.get("marshal_bytes_equal"),
             res.get("structure_equal")))
    if err.strip():
        print("    stderr: %s" % err.strip().splitlines()[0])
    return res


def suite_leg(label):
    out, err, _ = run([PY, "-m", "unittest", TESTMOD])
    text = out + err
    ran = re.search(r"Ran (\d+) tests?", text)
    ok = re.search(r"^OK", text, re.M)
    print("[suite %-16s] Ran %s tests, %s"
          % (label, ran.group(1) if ran else "?",
             "OK" if ok else "NOT-OK"))
    return (ran is not None and int(ran.group(1)) == 13) and bool(ok)


def restore(backup, atime_ns, mtime_ns):
    with open(SRC, "wb") as fh:
        fh.write(backup)
    os.utime(SRC, ns=(atime_ns, mtime_ns))
    got = sha(open(SRC, "rb").read())
    print("    restored sha256 %s (baseline %s, equal=%s)"
          % (got, BASE_SHA, got == BASE_SHA))
    return got == BASE_SHA


def phase0():
    print("== phase 0: baseline asserts ==")
    disk = open(SRC, "rb").read()
    st = os.stat(SRC)
    print("src sha256  %s (expected %s)" % (sha(disk), BASE_SHA))
    print("src size %d, CR=%d, mtime_ns=%d, atime_ns=%d"
          % (len(disk), disk.count(b"\r"), st.st_mtime_ns, st.st_atime_ns))
    assert sha(disk) == BASE_SHA, "baseline sha moved -- abort"
    assert len(disk) == BASE_SIZE, "baseline size moved -- abort"
    assert disk.count(b"\r") == 0, "baseline file gained CR -- abort"
    assert disk.count(GUARD) == 1, "guard line count != 1 -- abort"
    assert st.st_mtime_ns == BASE_MTIME_NS, "baseline mtime moved -- abort"
    magic, flags, hmtime, hsize = pyc_header()
    print("pyc header flags=%d mtime=%d size=%d" % (flags, hmtime, hsize))
    assert flags == 0, "pyc not timestamp-mode -- C2 precondition not met"
    assert hmtime == BASE_MTIME_NS // 1_000_000_000 and hsize == BASE_SIZE, \
        "as-found pyc is not the primed original -- C2 precondition not met"
    print("as-found pyc IS the primed state (header == baseline mtime/size)")
    return disk


def phase1():
    print("== phase 1: C1 -- the proof can say CLEAN ==")
    a = proof_leg("c1-as-found")
    run([PY, "-m", "py_compile", SRC])
    b = proof_leg("c1-fresh-compile")
    magic, flags, hmtime, hsize = pyc_header()
    print("after py_compile: header flags=%d mtime=%d size=%d (still primed: %s)"
          % (flags, hmtime, hsize,
             hmtime == BASE_MTIME_NS // 1_000_000_000 and hsize == BASE_SIZE))
    return a.get("verdict"), b.get("verdict")


def phase2():
    print("== phase 2: C2 -- 0075's P3, reconstructed exactly ==")
    backup = open(SRC, "rb").read()
    assert sha(backup) == BASE_SHA
    assert backup.count(GUARD) == 1 and backup.count(PLANT) == 0
    pre = os.stat(SRC)                       # atime to restore, mtime to forge
    atime_ns0, mtime_ns0 = pre.st_atime_ns, pre.st_mtime_ns
    planted = backup.replace(GUARD, PLANT)
    assert len(planted) == len(backup)
    print("plant: `not ` -> `0 * ` (same %d bytes), planted sha256 %s"
          % (len(planted), sha(planted)))
    results = {}
    try:
        with open(SRC, "wb") as fh:
            fh.write(planted)
        os.utime(SRC, ns=(atime_ns0, mtime_ns0))
        got_m, got_a = os.stat(SRC).st_mtime_ns, os.stat(SRC).st_atime_ns
        print("C4 ns quoted -- set mtime_ns %d, read back mtime_ns %d, "
              "identical=%s" % (mtime_ns0, got_m, got_m == mtime_ns0))
        assert got_m == mtime_ns0, \
            "os.utime would not set the ns value -- REPORT AND STOP, " \
            "no whole-second substitute attempted"
        magic, flags, hmtime, hsize = pyc_header()
        reuse = hmtime == mtime_ns0 // 1_000_000_000 and hsize == BASE_SIZE
        print("header-would-reuse-stale-bytes: %s "
              "(header mtime=%d size=%d vs file %d/%d)"
              % (reuse, hmtime, hsize, mtime_ns0 // 1_000_000_000, BASE_SIZE))
        assert reuse, "pyc header does not match the planted file -- plant failed"

        results["suite_ok"] = suite_leg("c2-p3-plant")

        out, _, _ = run([PY, os.path.join(ROOT, ".codex", "0075", "probe.py"),
                         "0078-p3-recheck"])
        for line in out.splitlines():
            if line.startswith("[0078-p3-recheck]"):
                print("    %s" % line)
        probe_raised = "RAISED UnpricedCall" in out
        print("    probe imported-module read raised the guard: %s" % probe_raised)
        assert probe_raised, "probe did not see the pre-plant guard -- stop"

        stale = proof_leg("c2-p3-stale")
        results["stale_verdict"] = stale.get("verdict")
    finally:
        print("revert (verified by sha256 of the working file's own bytes):")
        ok = restore(backup, atime_ns0, mtime_ns0)
        assert ok, "revert sha mismatch -- file left mutated, stopping"
        st = os.stat(SRC)
        print("    restored mtime_ns=%d (expected %d) atime_ns=%d"
              % (st.st_mtime_ns, mtime_ns0, st.st_atime_ns))
        assert st.st_mtime_ns == mtime_ns0, "mtime not restored"
    results["post_revert_clean"] = proof_leg("post-revert").get("verdict")
    results["post_revert_suite_ok"] = suite_leg("post-revert")
    return results


def phase3():
    print("== phase 3: section 3 census over the lane file's own bytes ==")
    sys.path.insert(0, HERE)
    import parse_lane
    return parse_lane.report(LANE)


def phase4(orig_total):
    print("== phase 4: C3 -- the parser's negative control on a copy ==")
    raw = open(LANE, "rb").read()
    orig_lines = raw.decode("utf-8").count("\n")
    plant_a = (
        "## TASK-0078 C3 control A (planted): a kill-set that names its "
        "tests must NOT be listed\r\n"
        "- **Plant CONTROL-A** - guard deadened (`if False:` planted). "
        "Killed 2:\r\n"
        "  `test_the_named_control_kills_the_mutant`,\r\n"
        "  `test_the_second_named_control_kills_the_mutant`. Reverted "
        "byte-identical.\r\n\r\n"
        "## TASK-0078 C3 control B (planted): an empty kill-set MUST be "
        "listed\r\n"
        "- **Plant CONTROL-B** - comment-only no-op, semantics untouched. "
        "Run:\r\n"
        "  `Ran 13 tests`, OK, kill-set \u2205. **SURVIVED**.\r\n")
    copy_path = os.path.join(ART, "lane-copy-c3.md")
    with open(copy_path, "wb") as fh:
        fh.write(raw + plant_a.encode("utf-8"))
    print("wrote %s (%d bytes; original %d bytes, %d lines)"
          % (copy_path, os.path.getsize(copy_path), len(raw), orig_lines))

    sys.path.insert(0, HERE)
    import parse_lane
    c = parse_lane.census(copy_path)
    plants = [r for r in c["records"] if r["line"] > orig_lines]
    print("records found below the original file's last line: %d "
          "(copy total %d = original %d + %d)"
          % (len(plants), c["total"], orig_total,
             c["total"] - orig_total))
    for r in plants:
        print("  L%-5d %-7s %s" % (r["line"], r["verdict"], r["excerpt"]))
    a = next((r for r in plants if "CONTROL-A" in r["excerpt"]), None)
    b = next((r for r in plants if "CONTROL-B" in r["excerpt"]), None)
    named_ok = bool(a) and a["verdict"] == "NAMED"
    unnamed_ok = bool(b) and b["verdict"] == "UNNAMED"
    print("C3 state 1 (named kill-set NOT listed as unnamed): %s"
          % ("shown" if named_ok else "FAILED"))
    print("C3 state 2 (empty kill-set IS listed as unnamed):    %s"
          % ("shown" if unnamed_ok else "FAILED"))
    assert len(plants) == 2 and c["total"] == orig_total + 2, \
        "the plants changed the census beyond the two planted records"
    return named_ok, unnamed_ok


def main():
    print("TASK-0078 driver -- %s, python %s" % (ROOT, sys.version.split()[0]))
    phase0()
    v1a, v1b = phase1()
    r2 = phase2()
    c3 = phase3()
    named_ok, unnamed_ok = phase4(c3["total"])

    print("== phase 5: C4 -- the verdict gate ==")
    c1_ok = v1a == "CLEAN" and v1b == "CLEAN"
    c2_ok = (r2.get("stale_verdict") == "STALE BYTECODE"
             and r2.get("suite_ok") and r2.get("post_revert_clean") == "CLEAN"
             and r2.get("post_revert_suite_ok"))
    c3_ok = named_ok and unnamed_ok
    print("C1 both legs CLEAN:               %s" % c1_ok)
    print("C2 STALE + suite OK + revert CLEAN: %s" % c2_ok)
    print("C3 both states shown:             %s" % c3_ok)
    if c1_ok and c2_ok and c3_ok:
        print()
        print("VERDICT: the suite still says OK, and the load-proof says "
              "STALE BYTECODE -- verdict void")
    else:
        print("C4 REFUSED TO PRINT A VERDICT -- a control that cannot fail "
              "proves nothing (failure family 5)")
        sys.exit(1)


if __name__ == "__main__":
    main()
