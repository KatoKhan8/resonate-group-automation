# TASK-0079 driver -- stop the stale import instead of catching it.
#
#   phase 0  baseline asserts on src/spendledger.py and its pyc (fail-closed)
#   phase 1  canonical name enumeration without running the tests -- the
#            kill-set ruler
#   phase 2  S2 -- 0075's P3 rebuilt exactly (same file, same size-identical
#            edit, same ns-exact mtime rollback, both ns values quoted),
#            evaluated four ways: unremedied, R1, R2, R3; 2x4 table.  If the
#            unremedied column KILLS the plant the hazard did not reproduce
#            in this session: every verdict is INCONCLUSIVE and the driver
#            stops before the controls.
#   phase 3  C1 -- 0075's P1 (size-changing) under the chosen remedy (R1):
#            KILLED, kill-set == the one name
#   phase 4  C2 -- 0075's no-op plant under R1: SURVIVED, kill-set empty
#   phase 5  C3 -- one evaluation timed with and without R1, 3 reps each,
#            every timing printed
#   phase 6  C4 -- the verdict gate
#
# The remedies, each a one-line change to this lane's plant harness only:
#   R1  os.unlink the target's __pycache__ entry before the evaluation
#   R2  the evaluation subprocess runs with PYTHONDONTWRITEBYTECODE=1
#   R3  os.utime the planted source to a whole second that provably differs
#       from the pyc header's, before the evaluation
#
# This file never imports anything under src/ -- the import under test
# happens only inside fresh subprocesses (0075's discipline: an import
# between the plant write and the mtime set-back would recompile the pyc
# and destroy the P3 condition).  Every revert is verified by sha256 of the
# working file's own bytes; every mtime moved is restored; after every
# revert the pyc is re-primed from the restored original so the tree never
# rests on a pyc compiled from a mutant.
import hashlib
import json
import os
import re
import struct
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
SRC = os.path.join(ROOT, "src", "spendledger.py")
PYC = os.path.join(ROOT, "src", "__pycache__",
                   "spendledger.cpython-314.pyc")
LOGS = os.path.join(HERE, "logs")
ART = r"C:\Users\Zvonimir\Desktop\resonate-ops\TASK-0079"
TESTMOD = "tests.test_an_unknown_price_is_not_a_free_call"

# Constants at HEAD fee793625 (measured 2026-10-16, this session, phase 0
# asserts them before anything runs).
BASE_SHA = "a51a60bee5077fdd3b0deedbbbded71a90971f49b2be19ce30858224b2dad7db"
BASE_SIZE = 59007
BASE_MTIME_NS = 1792144718123314700
GUARD = b"    if not priced and governed:\n"
PLANT_P3 = b"    if 0 * priced and governed:\n"            # same size
PLANT_P1 = b"    if False and not priced and governed:\n"   # +10 bytes
PLANT_NOOP = (b"    if not priced and governed:"
              b"  # TASK-0075 no-op plant\n")               # +25 bytes
KILL_SUFFIX = ("TheLlmSeam.test_a_finite_ceiling_refuses_an_unpriced"
               "_call_before_the_provider")

PY = sys.executable
CANON = []


def sha(b):
    return hashlib.sha256(b).hexdigest()


def run(cmd, env=None):
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, env=env)
    return (p.stdout.decode("utf-8", "replace"),
            p.stderr.decode("utf-8", "replace"), p.returncode)


def pyc_header():
    with open(PYC, "rb") as fh:
        magic, flags, hmtime, hsize = struct.unpack("<IIII", fh.read(16))
    return magic, flags, hmtime, hsize


def pyc_sha():
    return sha(open(PYC, "rb").read())


def ensure_pristine():
    disk = open(SRC, "rb").read()
    st = os.stat(SRC)
    assert sha(disk) == BASE_SHA, "tree not pristine (sha) -- abort"
    assert disk.count(GUARD) == 1, "guard count != 1 -- abort"
    assert st.st_mtime_ns == BASE_MTIME_NS, \
        "baseline mtime moved (%d != %d) -- abort" % (st.st_mtime_ns,
                                                      BASE_MTIME_NS)
    return disk


def prime():
    """Recompile the pyc from the CURRENT disk bytes (overwrite, not
    deletion)."""
    _, err, rc = run([PY, "-m", "py_compile", SRC])
    assert rc == 0, "py_compile failed (rc=%d): %s" % (rc, err.strip()[:200])


def verify_primed(tag=""):
    magic, flags, hmtime, hsize = pyc_header()
    ok = (flags == 0 and hmtime == BASE_MTIME_NS // 1_000_000_000
          and hsize == BASE_SIZE)
    print("    primed%s: header flags=%d mtime=%d size=%d == baseline %s"
          % (tag, flags, hmtime, hsize, ok))
    assert ok, "pyc not primed to the baseline -- abort"


def restore(backup, atime_ns, mtime_ns):
    with open(SRC, "wb") as fh:
        fh.write(backup)
    os.utime(SRC, ns=(atime_ns, mtime_ns))
    got = sha(open(SRC, "rb").read())
    print("    restored sha256 %s (baseline %s, equal=%s)"
          % (got, BASE_SHA, got == BASE_SHA))
    st = os.stat(SRC)
    print("    restored mtime_ns=%d (expected %d, equal=%s)"
          % (st.st_mtime_ns, mtime_ns, st.st_mtime_ns == mtime_ns))
    return got == BASE_SHA and st.st_mtime_ns == mtime_ns


def proof_leg(label):
    out, err, _ = run([PY, os.path.join(HERE, "..", "0078",
                                        "proof_runner.py"), label])
    i = out.find("{")
    res = json.loads(out[i:]) if i >= 0 else {}
    print("    [proof %-14s] verdict=%-13s clean_by=%s"
          % (label, res.get("verdict"), res.get("clean_by")))
    return res


def suite_leg(tag, env_extra=None):
    """One evaluation: the 13-test module, fresh subprocess, -v, output
    teed to .codex/0079/logs/<tag>.out.  Returns verdict + kill-set +
    elapsed seconds."""
    out_path = os.path.join(LOGS, tag + ".out")
    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)
    t0 = time.perf_counter()
    with open(out_path, "wb") as out:
        proc = subprocess.run([PY, "-m", "unittest", TESTMOD, "-v"],
                              cwd=ROOT, stdout=out,
                              stderr=subprocess.STDOUT, env=env)
    elapsed = time.perf_counter() - t0
    text = open(out_path, "r", encoding="utf-8", errors="replace").read()
    ran = re.search(r"^Ran (\d+) tests?", text, re.M)
    fails = re.findall(r"^(FAIL|ERROR): (\S+) \(([^)]+)\)", text, re.M)
    red = sorted(set(full for _, _, full in fails))
    ok = bool(re.search(r"^OK", text, re.M))
    kill_set = sorted(set(red) & set(CANON))
    foreign = sorted(set(red) - set(CANON))
    ran_n = int(ran.group(1)) if ran else -1
    print("    [suite %-14s] Ran %d, %s, kill-set %s%s, %.2fs"
          % (tag, ran_n, "OK" if ok else "NOT-OK",
             kill_set if kill_set else "{}",
             (" +foreign %s" % foreign) if foreign else "", elapsed))
    return {"ok": ok, "ran": ran_n, "kill_set": kill_set,
            "foreign_red": foreign, "elapsed": elapsed,
            "exit": proc.returncode}


def arm_p3(backup, atime_ns0, mtime_ns0):
    """0075's P3: same file, same size-identical edit, same ns-exact mtime
    rollback.  Both ns values quoted.  Asserts the header would reuse the
    stale bytes (hazard armed).  The caller holds the backup and wraps this
    in the revert's try, so a failed assert cannot leave the file mutated."""
    assert sha(backup) == BASE_SHA
    assert backup.count(GUARD) == 1 and backup.count(PLANT_P3) == 0
    planted = backup.replace(GUARD, PLANT_P3)
    assert len(planted) == len(backup), "P3 edit is not size-identical"
    with open(SRC, "wb") as fh:
        fh.write(planted)
    os.utime(SRC, ns=(atime_ns0, mtime_ns0))
    got_m = os.stat(SRC).st_mtime_ns
    print("    P3 armed: `not ` -> `0 * ` (%d bytes, size-identical), "
          "set mtime_ns %d, read back mtime_ns %d, identical=%s"
          % (len(planted), mtime_ns0, got_m, got_m == mtime_ns0))
    assert got_m == mtime_ns0, "os.utime would not set the ns value -- stop"
    magic, flags, hmtime, hsize = pyc_header()
    reuse = hmtime == mtime_ns0 // 1_000_000_000 and hsize == BASE_SIZE
    print("    header would reuse stale bytes: %s (header mtime=%d size=%d "
          "vs file %d/%d)" % (reuse, hmtime, hsize,
                              mtime_ns0 // 1_000_000_000, BASE_SIZE))
    assert reuse, "pyc header does not match the planted file -- plant failed"


def apply_remedy(which):
    """Applied after the hazard is armed, before the evaluation."""
    if which == "unremedied":
        return "nothing -- the hazard runs as 0075 measured it"
    if which == "R1":
        magic, flags, hmtime, hsize = pyc_header()
        os.unlink(PYC)
        assert not os.path.exists(PYC)
        return ("unlinked src\\__pycache__\\spendledger.cpython-314.pyc "
                "(header was mtime=%d size=%d)" % (hmtime, hsize))
    if which == "R2":
        return "evaluation leg runs with PYTHONDONTWRITEBYTECODE=1"
    if which == "R3":
        magic, flags, hmtime, hsize = pyc_header()
        header_sec = hmtime
        t1 = int(time.time())
        while t1 <= header_sec:          # must PROVABLY differ, not assumed
            time.sleep(0.25)
            t1 = int(time.time())
        # 100-ns-aligned on purpose: this NTFS volume rounds an unaligned
        # ns value down (...6789 -> ...6700) and the read-back assert
        # refuses it.  Measured in the first run of this harness; see
        # run-0079-first-abort.log.
        t1_ns = t1 * 1_000_000_000 + 123_456_700
        os.utime(SRC, ns=(os.stat(SRC).st_atime_ns, t1_ns))
        got = os.stat(SRC).st_mtime_ns
        print("    R3: set mtime_ns %d, read back %d, identical=%s"
              % (t1_ns, got, got == t1_ns))
        assert got == t1_ns
        magic, flags, hmtime2, hsize2 = pyc_header()
        now_sec = os.stat(SRC).st_mtime_ns // 1_000_000_000
        differs = not (hmtime2 == now_sec and hsize2 == os.stat(SRC).st_size)
        print("    R3: whole second %d vs header mtime %d, provably "
              "different=%s" % (now_sec, hmtime2, differs))
        assert differs, "R3 failed to move off the header's second"
        return ("source mtime bumped to whole second %d (header %d)"
                % (now_sec, hmtime2))
    raise ValueError(which)


def column(which):
    """One column of the S2 table: pristine -> primed -> P3 armed ->
    remedy -> evaluation -> proof -> sha-verified revert -> re-prime."""
    print("-- column %s --" % which)
    ensure_pristine()
    prime()
    verify_primed(" (pre-plant)")
    backup = open(SRC, "rb").read()
    pre = os.stat(SRC)
    atime_ns0, mtime_ns0 = pre.st_atime_ns, pre.st_mtime_ns
    res = {"column": which}
    try:
        arm_p3(backup, atime_ns0, mtime_ns0)
        pyc_before = pyc_sha()
        desc = apply_remedy(which)
        print("    remedy: %s" % desc)
        env_extra = {"PYTHONDONTWRITEBYTECODE": "1"} if which == "R2" else None
        s = suite_leg("s2-" + which, env_extra=env_extra)
        res.update(s)
        pyc_after = pyc_sha() if os.path.exists(PYC) else "(absent)"
        print("    pyc sha across the evaluation: before %s.. after %s.."
              % (pyc_before[:12], pyc_after[:12]))
        res["pyc_unchanged"] = (pyc_before == pyc_after)
        p = proof_leg("s2-" + which)
        res["proof"] = p.get("verdict")
    finally:
        print("    revert:")
        ok = restore(backup, atime_ns0, mtime_ns0)
        assert ok, "revert failed -- file left mutated, stopping"
        prime()
        verify_primed(" (post-revert)")
    res["verdict"] = "SURVIVED" if res["ok"] else "KILLED"
    print("    COLUMN %s: %s, kill-set %s, proof %s"
          % (which, res["verdict"], res["kill_set"] or "{}",
             res["proof"]))
    return res


def plant_and_run(which, plant, tag, expect):
    """Shared leg for C1/C2: pristine -> primed -> plant (no mtime rollback;
    these plants are size-changing) -> remedy -> evaluation -> revert ->
    re-prime.  Returns the suite result."""
    ensure_pristine()
    prime()
    verify_primed(" (pre-plant)")
    backup = open(SRC, "rb").read()
    pre = os.stat(SRC)
    atime_ns0, mtime_ns0 = pre.st_atime_ns, pre.st_mtime_ns
    planted = backup.replace(GUARD, plant)
    delta = len(planted) - len(backup)
    assert delta == expect, "unexpected size delta %+d (want %+d)" % (delta,
                                                                      expect)
    with open(SRC, "wb") as fh:
        fh.write(planted)
    print("    planted %s (%+d bytes -> %d)" % (tag, delta, len(planted)))
    try:
        apply_remedy(which)
        s = suite_leg(tag)
    finally:
        print("    revert:")
        ok = restore(backup, atime_ns0, mtime_ns0)
        assert ok, "revert failed -- file left mutated, stopping"
        prime()
        verify_primed(" (post-revert)")
    s["verdict"] = "SURVIVED" if s["ok"] else "KILLED"
    return s


def phase0():
    print("== phase 0: baseline asserts ==")
    disk = open(SRC, "rb").read()
    st = os.stat(SRC)
    print("src sha256  %s (expected %s)" % (sha(disk), BASE_SHA))
    print("src size %d, CR=%d, mtime_ns=%d" % (len(disk), disk.count(b"\r"),
                                                st.st_mtime_ns))
    assert sha(disk) == BASE_SHA, "baseline sha moved -- abort"
    assert len(disk) == BASE_SIZE, "baseline size moved -- abort"
    assert disk.count(b"\r") == 0, "baseline file gained CR -- abort"
    assert disk.count(GUARD) == 1, "guard line count != 1 -- abort"
    assert st.st_mtime_ns == BASE_MTIME_NS, "baseline mtime moved -- abort"
    magic, flags, hmtime, hsize = pyc_header()
    print("pyc header flags=%d mtime=%d size=%d" % (flags, hmtime, hsize))
    assert flags == 0, "pyc not timestamp-mode -- precondition not met"
    assert hmtime == BASE_MTIME_NS // 1_000_000_000 and hsize == BASE_SIZE, \
        "as-found pyc is not the primed original -- precondition not met"


def phase1():
    print("== phase 1: canonical names, enumerated without a run ==")
    global CANON
    code = ("import json, unittest;"
            "s=unittest.TestLoader().loadTestsFromName('%s');"
            "ids=[]; stack=[s]\n"
            "while stack:\n"
            "    t=stack.pop()\n"
            "    (stack.extend(t) if hasattr(t,'_tests') else ids.append(t.id()))\n"
            "print(json.dumps(sorted(ids)))" % TESTMOD)
    out, err, rc = run([PY, "-c", code])
    CANON = json.loads(out.strip().splitlines()[-1])
    assert len(CANON) == 13, "expected 13 canonical names, got %d" % len(CANON)
    kills = [n for n in CANON if n.endswith(KILL_SUFFIX)]
    assert len(kills) == 1, "kill name not unique in the canon: %s" % kills
    print("13 canonical names; the kill name is unique:")
    print("    %s" % kills[0])
    return kills[0]


def phase2():
    print("== phase 2: S2 -- P3 rebuilt, evaluated four ways ==")
    rows = []
    for which in ("unremedied", "R1", "R2", "R3"):
        rows.append(column(which))
    print()
    print("S2 table (rows = survived/killed, columns = remedy):")
    print("  %-12s %-9s %-46s %s" % ("column", "verdict", "kill-set",
                                     "load-proof"))
    for r in rows:
        ks = (r["kill_set"][0].split(".")[-2] + "."
              + r["kill_set"][0].split(".")[-1]) if r["kill_set"] else "{}"
        print("  %-12s %-9s %-46s %s" % (r["column"], r["verdict"], ks,
                                         r["proof"]))
    unrem = rows[0]
    if unrem["verdict"] != "SURVIVED" or unrem["kill_set"]:
        print()
        print("HAZARD DID NOT REPRODUCE: the unremedied column killed the "
              "plant (%s, kill-set %s).  Every other column is "
              "uninterpretable and every verdict in this task is "
              "INCONCLUSIVE." % (unrem["verdict"], unrem["kill_set"]))
        return rows, False
    return rows, True


def phase3_c1(kill_name):
    print("== phase 3: C1 -- P1 (size-changing) under the chosen remedy R1 ==")
    s = plant_and_run("R1", PLANT_P1, "c1-p1-r1", 10)
    state1 = not s["ok"] and s["ran"] == 13
    state2 = s["kill_set"] == [kill_name]
    print("    C1 state 1 (plant KILLED, 13 ran):        %s" % ("shown"
                                                                if state1
                                                                else "FAILED"))
    print("    C1 state 2 (kill-set is exactly the one name): %s"
          % ("shown" if state2 else "FAILED: %s" % s["kill_set"]))
    return state1 and state2, s


def phase4_c2():
    print("== phase 4: C2 -- the no-op plant under R1 ==")
    s = plant_and_run("R1", PLANT_NOOP, "c2-noop-r1", 25)
    state1 = s["ok"] and s["ran"] == 13
    state2 = s["kill_set"] == []
    print("    C2 state 1 (no-op SURVIVED, 13 ran):     %s" % ("shown"
                                                               if state1
                                                               else "FAILED"))
    print("    C2 state 2 (kill-set empty):             %s"
          % ("shown" if state2 else "FAILED: %s" % s["kill_set"]))
    return state1 and state2, s


def phase5_c3():
    print("== phase 5: C3 -- one evaluation, timed with and without R1 ==")
    without = []
    for i in range(3):
        ensure_pristine()
        prime()
        verify_primed(" (c3-without-%d pre)" % i)
        s = suite_leg("c3-without-%d" % i)
        without.append(s["elapsed"])
    with_r1 = []
    for i in range(3):
        ensure_pristine()
        prime()
        verify_primed(" (c3-with-r1-%d pre)" % i)
        os.unlink(PYC)
        s = suite_leg("c3-with-r1-%d" % i)
        with_r1.append(s["elapsed"])
        prime()
        verify_primed(" (c3-with-r1-%d post)" % i)
    for i in range(3):
        print("    rep %d: without %.2fs | with R1 %.2fs"
              % (i + 1, without[i], with_r1[i]))
    mw = sorted(without)[1]
    mr = sorted(with_r1)[1]
    print("    medians: without %.2fs, with R1 %.2fs, delta %+.2fs per "
          "evaluation" % (mw, mr, mr - mw))
    state1 = len(without) == 3 and all(t > 0 for t in without)
    state2 = len(with_r1) == 3 and all(t > 0 for t in with_r1)
    print("    C3 state 1 (without-remedy timings printed): %s"
          % ("shown" if state1 else "FAILED"))
    print("    C3 state 2 (with-remedy timings printed):    %s"
          % ("shown" if state2 else "FAILED"))
    return state1 and state2, {"without": without, "with_r1": with_r1,
                               "median_without": mw, "median_with": mr}


class Tee:
    def __init__(self, path):
        self.fh = open(path, "wb")
        self.stdout = sys.stdout

    def write(self, data):
        if isinstance(data, str):
            data = data.encode("utf-8", "replace")
        self.stdout.buffer.write(data)
        self.fh.write(data)
        self.fh.flush()

    def flush(self):
        self.stdout.flush()
        self.fh.flush()


def main():
    os.makedirs(LOGS, exist_ok=True)
    os.makedirs(ART, exist_ok=True)
    sys.stdout = Tee(os.path.join(ART, "run-0079.log"))
    print("TASK-0079 driver -- %s, python %s, %s"
          % (ROOT, sys.version.split()[0],
             time.strftime("%Y-%m-%d %H:%M:%S")))
    phase0()
    kill_name = phase1()
    rows, reproduced = phase2()
    results = {"columns": rows}
    if not reproduced:
        with open(os.path.join(ART, "results-0079.json"), "w") as fh:
            json.dump(results, fh, indent=1)
        sys.exit(1)
    c1_ok, c1 = phase3_c1(kill_name)
    c2_ok, c2 = phase4_c2()
    c3_ok, c3 = phase5_c3()
    results["c1"] = c1
    results["c2"] = c2
    results["c3"] = c3
    results["kill_name"] = kill_name

    print("== phase 6: C4 -- the verdict gate ==")
    print("    S2 unremedied column SURVIVED:                %s" % reproduced)
    print("    C1 both states shown (kill + one name):       %s" % c1_ok)
    print("    C2 both states shown (survive + empty set):   %s" % c2_ok)
    print("    C3 both states shown (timings, both arms):    %s" % c3_ok)
    r1k = next(r for r in rows if r["column"] == "R1")
    r1_kills = (r1k["verdict"] == "KILLED" and r1k["kill_set"] == [kill_name])
    r2k = next(r for r in rows if r["column"] == "R2")
    r3k = next(r for r in rows if r["column"] == "R3")
    print("    R1 column KILLED with the one name:           %s" % r1_kills)
    print("    R2 column: %s, kill-set %s (analysis said R2 cannot defeat "
          "P3: -B stops writes, not header-valid reads)"
          % (r2k["verdict"], r2k["kill_set"] or "{}"))
    print("    R3 column: %s, kill-set %s"
          % (r3k["verdict"], r3k["kill_set"] or "{}"))
    if reproduced and c1_ok and c2_ok and c3_ok and r1_kills:
        print()
        print("VERDICT: R1 (unlink the target's __pycache__ entry before "
              "each evaluation) stops the stale import for this lane's "
              "harness -- the forged green becomes the kill it should have "
              "been, the no-op stays green, and the cost is the measured "
              "recompile delta above.  R3 equally kills; R2 does not.")
    else:
        print()
        print("C4 REFUSED TO PRINT A VERDICT -- a control that cannot fail "
              "proves nothing (failure family 5)")
        sys.exit(1)

    print()
    print("== final state ==")
    ensure_pristine()
    prime()
    verify_primed(" (final)")
    st = os.stat(SRC)
    print("src sha256 %s size %d mtime_ns %d" % (sha(open(SRC, "rb").read()),
                                                 st.st_size, st.st_mtime_ns))
    print("pyc sha256 %s" % pyc_sha())
    with open(os.path.join(ART, "results-0079.json"), "w") as fh:
        json.dump(results, fh, indent=1)
    print("results written to %s" % os.path.join(ART, "results-0079.json"))


if __name__ == "__main__":
    main()
