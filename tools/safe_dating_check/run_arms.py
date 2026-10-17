"""webapp/0380 - the three arms. Deterministic: no clocks, no cwd in output.

Arm (a)  the known real pair, read-only against the estate worktree
Arm (b)  synthetic clause-inside-needle coupling, BOTH directions
Arm (c)  synthetic merge commit whose two parents differ in occurrence count

The synthetic repo is rebuilt from scratch each run with FIXED author and
committer identity and FIXED dates, so its commit SHAs are byte-stable and two
full runs of this script are byte-identical.
"""

import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from safe_dating import (  # noqa: E402
    BLOBS_COUNTED,
    classify_commit,
    date_needle,
    describe_blob,
    git,
    log_s,
)


def _resolve_estate(argv):
    """Resolve the estate worktree this instrument READS.  webapp/0420.

    0400 persisted this as a hardcoded absolute path, and recorded the
    consequence as a finding: when that one worktree goes away, arm (a) and the
    whole of step 6 stop working.  Resolution order now:

      1. an explicit `--estate <path>` argument, which always wins;
      2. otherwise the nearest ancestor of THIS FILE that is a git work tree -
         the zero-config answer when the instrument is checked out at
         tools/safe_dating_check/ inside the estate it reads;
      3. otherwise REFUSE, loudly, naming the argument and the directory walked.

    A path that is not a git work tree is a refusal too.  There is no fallback
    to the cwd: an instrument that dates commits must never guess which
    repository it is dating.
    """
    path = None
    if "--estate" in argv:
        i = argv.index("--estate")
        if i + 1 >= len(argv):
            raise SystemExit("REFUSED: --estate needs a path argument.")
        path = argv[i + 1]
    else:
        probe = HERE
        while True:
            if os.path.exists(os.path.join(probe, ".git")):
                path = probe
                break
            parent = os.path.dirname(probe)
            if parent == probe:
                break
            probe = parent
    if path is None:
        raise SystemExit(
            "REFUSED: cannot resolve the estate worktree.  No ancestor of\n"
            "  %s\n"
            "contains a .git, so this instrument is not checked out inside the\n"
            "repository it reads.  Pass it explicitly:\n"
            "  py -3 -B %s --estate <path-to-estate-worktree>"
            % (HERE, os.path.basename(os.path.abspath(__file__))))
    path = os.path.abspath(path)
    if not os.path.isdir(path) or not os.path.exists(os.path.join(path, ".git")):
        raise SystemExit(
            "REFUSED: %r is not a git work tree - no .git there, so no commit\n"
            "in it can be read.  Arm (a) and step 6 read REAL history from the\n"
            "estate; they do not invent one, and they do not silently fall back\n"
            "to the current directory." % path)
    return path


ESTATE = _resolve_estate(sys.argv[1:])
CONTESTED = "src/contested.py"

# 0360's settled cells, dispatcher-carried in the 0380 brief.
AROSE_AT = "608e46ea599526668ce0fe83782a90047b06c6af"
WRITTEN_AT = "3a623688973cbcc61ec53d235f3da14b32c72ae7"
COUPLING_OFFSET = 32
TIMELINE = [
    "3a623688973cbcc61ec53d235f3da14b32c72ae7",
    "608e46ea599526668ce0fe83782a90047b06c6af",
    "1476361fb2b44238a071680f9f80168f99dfa8f7",
    "f55fc043a6f6e73231bc123638628f6d0f077ca1",
    "d1fa9a29b03881c237a076120f3437481928b238",
]

BARE = b"diverged on 2026"
DISAMBIGUATED = b'"defect": r"diverged on 2026"'

FIXTURE = os.path.join(HERE, "fixture-repo")

ENV = dict(os.environ)
for key in list(ENV):
    if key.startswith("GIT_CONFIG"):
        del ENV[key]
ENV.update({
    "GIT_AUTHOR_NAME": "Fixture",
    "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
    "GIT_COMMITTER_NAME": "Fixture",
    "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
    "GIT_AUTHOR_DATE": "2020-01-01T00:00:00+0000",
    "GIT_COMMITTER_DATE": "2020-01-01T00:00:00+0000",
})


def rule(title):
    print()
    print("#" * 78)
    print("# %s" % title)
    print("#" * 78)
    print()


def fx(args, check=True):
    proc = subprocess.run(
        ["git", "-C", FIXTURE] + args,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=ENV,
    )
    out = proc.stdout.decode("utf-8", "replace")
    if check and proc.returncode != 0:
        raise RuntimeError("fixture git %s failed rc=%d: %s" % (args, proc.returncode, out))
    return out.strip()


def write_fixture_file(name, text):
    """LF only, written as bytes, so the fixture blobs are flavour-stable."""
    with open(os.path.join(FIXTURE, name), "wb") as fh:
        fh.write(text.replace("\r\n", "\n").encode("utf-8"))


def commit(msg):
    fx(["add", "-A"])
    fx(["commit", "-q", "-m", msg])
    return fx(["rev-parse", "HEAD"])


def _force_writable(func, path, exc):
    """git writes loose objects read-only; rmtree needs them writable on Windows."""
    os.chmod(path, 0o700)
    func(path)


def build_fixture():
    if os.path.isdir(FIXTURE):
        shutil.rmtree(FIXTURE, onexc=_force_writable)
    os.makedirs(FIXTURE)
    fx(["init", "-q", "-b", "main"])
    # Identity through env, never a repo config write, and autocrlf off so the
    # fixture blobs are LF whatever the machine's installer set.
    fx(["config", "core.autocrlf", "false"])
    shas = {}

    # ---- direction (i): the longer string PRE-EXISTS the clause ------------
    # b_i.py at B1 carries the bare needle inside a longer `now` string only.
    write_fixture_file("b_i.py", (
        'ENTRY = {\n'
        '    "now": "`master` is a different ref and diverged on 2026-10-15",\n'
        '}\n'
    ))
    shas["B1"] = commit("B1: the longer `now` string only, no clause yet")

    # B2 adds the clause, whose own text contains the bare needle.
    write_fixture_file("b_i.py", (
        'ENTRY = {\n'
        '    "now": "`master` is a different ref and diverged on 2026-10-15",\n'
        '    "defect": r"diverged on 2026",\n'
        '}\n'
    ))
    shas["B2"] = commit("B2: the clause arrives, coupled to B1's `now`")

    # ---- direction (ii): the clause arrives with NO pre-existing longer ----
    write_fixture_file("b_ii.py", 'ENTRY = {\n    "figure": "local_master",\n}\n')
    shas["Y0"] = commit("Y0: b_ii without the clause or any longer string")
    write_fixture_file("b_ii.py", (
        'ENTRY = {\n'
        '    "figure": "local_master",\n'
        '    "defect": r"diverged on 2026",\n'
        '}\n'
    ))
    shas["Y"] = commit("Y: the clause arrives uncoupled")

    # ---- arm (c): a merge whose two parents differ in occurrence count -----
    write_fixture_file("c.py", 'CFG = {\n    "k": 1,\n}\n')
    shas["M0"] = commit("M0: merge base, no needle")
    fx(["branch", "side", shas["M0"]])
    # Main side touches a DIFFERENT file, so the merge is clean and the only
    # thing that differs between M's two parents is c.py's occurrence count.
    write_fixture_file("other.py", 'NOTE = "main side, nothing to do with c.py"\n')
    shas["T1"] = commit("T1: main side, unrelated file, c.py count stays 0")
    fx(["checkout", "-q", "side"])
    write_fixture_file("c.py", (
        'CFG = {\n'
        '    "k": 1,\n'
        '    "defect": r"merge edge needle",\n'
        '}\n'
    ))
    shas["S1"] = commit("S1: branch side introduces the needle")
    fx(["checkout", "-q", "main"])
    fx(["merge", "-q", "--no-ff", "-m", "M: merge side into main", "side"])
    shas["M"] = fx(["rev-parse", "HEAD"])
    return shas


# =========================================================================
def arm_a():
    rule("ARM (a) - THE KNOWN REAL PAIR, read-only against the estate repo")
    print("estate repo : %s" % ESTATE)
    print("path        : %s" % CONTESTED)
    print("HEAD        : %s" % git(ESTATE, ["rev-parse", "HEAD"])[0].decode().strip())
    print("origin/master: %s" % git(ESTATE, ["rev-parse", "origin/master"])[0].decode().strip())
    print()

    print("--- a.1 NAIVE REPRODUCTION (the other-answer control) --------------")
    print("The old instrument's answer: the OLDEST hit of `git log -S<bare needle>`.")
    hits = log_s(ESTATE, BARE, CONTESTED)
    print("bare needle        : %r" % BARE)
    print("hits (oldest first): %s" % " ".join(hits))
    naive = hits[0] if hits else None
    print("NAIVE-OLDEST-HIT   : %s" % naive)
    print("0360's WRITTEN-AT  : %s" % WRITTEN_AT)
    print("CONTROL a.1        : %s" % (
        "REPRODUCED - the naive walk does return the wrong commit"
        if naive == WRITTEN_AT else
        "DISAGREEMENT WITH 0360'S RECORD - STOP"))
    print()

    print("--- a.2 THE SAFE INSTRUMENT ON THE SAME BARE NEEDLE ---------------")
    res_bare = date_needle(ESTATE, CONTESTED, BARE, ref="HEAD")

    print("--- a.3 THE SAFE INSTRUMENT ON THE DISAMBIGUATED NEEDLE -----------")
    res_dis = date_needle(ESTATE, CONTESTED, DISAMBIGUATED, ref="HEAD")

    print("--- a.4 THE REQUIRED CELL: count of the DISAMBIGUATED needle at the")
    print("        written-at commit must be 0 --------------------------------")
    n_written, _ = describe_blob(ESTATE, WRITTEN_AT, CONTESTED, DISAMBIGUATED,
                                 "written-at blob")
    print()
    return res_bare, res_dis, naive, n_written


def arm_b(shas):
    rule("ARM (b) - SYNTHETIC FIXTURE, BOTH DIRECTIONS")
    print("fixture repo: <artefact-dir>/fixture-repo")
    for k in ("B1", "B2", "Y0", "Y"):
        print("  %-3s %s" % (k, shas[k]))
    print()

    print("--- b(i) the longer string PRE-EXISTS the clause -------------------")
    print("expected: naive oldest-hit = B1 (WRONG for the clause);")
    print("          safe = refuse on the bare needle, B2 on the disambiguated.")
    print()
    hits_i = log_s(FIXTURE, BARE, "b_i.py")
    naive_i = hits_i[0] if hits_i else None
    print("naive-oldest-hit (bare needle) : %s  (B1=%s)" % (naive_i, shas["B1"]))
    print("naive verdict                  : %s"
          % ("WRONG - dates the clause to B1, where it does not exist"
             if naive_i == shas["B1"] else "UNEXPECTED"))
    print()
    bi_bare = date_needle(FIXTURE, "b_i.py", BARE, ref="main")
    bi_dis = date_needle(FIXTURE, "b_i.py", DISAMBIGUATED, ref="main")

    print("--- b(ii) the clause arrives UNCOUPLED ----------------------------")
    print("expected: naive right (Y), safe still right (Y).")
    print()
    hits_ii = log_s(FIXTURE, BARE, "b_ii.py")
    naive_ii = hits_ii[0] if hits_ii else None
    print("naive-oldest-hit (bare needle) : %s  (Y=%s)" % (naive_ii, shas["Y"]))
    print("naive verdict                  : %s"
          % ("RIGHT" if naive_ii == shas["Y"] else "UNEXPECTED"))
    print()
    bii_bare = date_needle(FIXTURE, "b_ii.py", BARE, ref="main")
    return bi_bare, bi_dis, bii_bare, naive_i, naive_ii


def arm_c(shas):
    rule("ARM (c) - MERGE-COMMIT EDGE")
    needle = b'"defect": r"merge edge needle"'
    for k in ("M0", "T1", "S1", "M"):
        print("  %-3s %s" % (k, shas[k]))
    print()
    print("M's parents differ: T1 count 0, S1 count 1.")
    print()
    res = date_needle(FIXTURE, "c.py", needle, ref="main")
    print("--- c.2 the merge commit classified DIRECTLY ----------------------")
    print("(`git log -S` applies history simplification; whether M appears in")
    print(" the walk above or not, the rule's verdict on M is printed here.)")
    print()
    v_merge = classify_commit(FIXTURE, "c.py", needle, shas["M"])
    print("--- c.3 the branch-side commit classified DIRECTLY ---------------")
    v_side = classify_commit(FIXTURE, "c.py", needle, shas["S1"])
    print("MERGE IN THE -S WALK : %s" % ("YES" if shas["M"] in res["hits"] else "NO"))
    print("RULE AT M            : %s" % v_merge)
    print("RULE AT S1           : %s" % v_side)
    return res, v_merge, v_side


def main():
    rule("webapp/0380 - COUPLING-SAFE DATING INSTRUMENT, THREE ARMS")
    print("RULE: a -S hit at C is the INTRODUCTION only if count(C's blob) >= 1")
    print("      AND count == 0 in EVERY parent of C.  A root commit with")
    print("      count >= 1 and no parents is CONFIRMED-INTRODUCTION by")
    print("      definition.  Counting is literal non-overlapping BYTE counting")
    print("      on raw blob bytes; each blob's CR count is printed so its")
    print("      LF/CRLF flavour is on the record.")
    print()
    print("PRECHECK (added by this task, and the reason is in arm (a)): a needle")
    print("      that occurs more than once in the blob you are dating FROM is")
    print("      satisfied by two different pieces of text, so no dating of")
    print("      either is trustworthy.  AMBIGUOUS-NEEDLE -> REFUSE.")

    shas = build_fixture()

    res_bare, res_dis, naive_a, n_written = arm_a()
    bi_bare, bi_dis, bii_bare, naive_i, naive_ii = arm_b(shas)
    res_c, v_merge, v_side = arm_c(shas)

    rule("CONTROLS AND KNOWN-ANSWER CELLS")
    checks = []

    checks.append((
        "a.1 naive oldest-hit == 0360's WRITTEN-AT 3a6236889",
        naive_a == WRITTEN_AT, naive_a))
    checks.append((
        "a.2 bare needle is caught as AMBIGUOUS-NEEDLE (not answered wrongly)",
        res_bare["precheck"] == "AMBIGUOUS-NEEDLE", res_bare["precheck"]))
    checks.append((
        "a.2 bare needle: 608e46ea5 reads MOVED-COUNT-ONLY (1 -> 2)",
        AROSE_AT not in res_bare["confirmed"], res_bare["confirmed"]))
    checks.append((
        "a.3 disambiguated needle CONFIRMED-INTRODUCTION == AROSE-AT 608e46ea5",
        res_dis["confirmed"] == [AROSE_AT], res_dis["confirmed"]))
    checks.append((
        "a.3 disambiguated needle is UNIQUE-AT-REF at HEAD",
        res_dis["precheck"] == "UNIQUE-AT-REF", res_dis["precheck"]))
    checks.append((
        "a.4 disambiguated needle count at WRITTEN-AT 3a6236889 is 0",
        n_written == 0, n_written))

    # coupling offset 32, recomputed from the blob rather than retyped
    data = git(ESTATE, ["cat-file", "blob",
                        git(ESTATE, ["rev-parse", "%s:%s" % (AROSE_AT, CONTESTED)])[0]
                        .decode().strip()])[0]
    now_line = [ln for ln in data.split(b"\n")
                if b'"now": "`master` is a different ref' in ln][0]
    now_val = now_line.split(b'"now": "', 1)[1].rsplit(b'"', 1)[0]
    offset = now_val.index(BARE)
    checks.append((
        "step5 coupling offset of the bare needle inside entry #2's `now`",
        offset == COUPLING_OFFSET, offset))
    print("  entry #2 `now` value : %r" % now_val)
    print("  bare needle offset   : %d  (0360's cell: %d)" % (offset, COUPLING_OFFSET))

    # timeline of 5 commits, each measured live
    print()
    print("  TIMELINE of src/contested.py, oldest first, measured live:")
    out = git(ESTATE, ["log", "--format=%H", "--", CONTESTED])[0].decode().split()
    live_timeline = list(reversed(out))
    for c in live_timeline:
        print("    %s" % c)
    checks.append((
        "step5 timeline is 0360's 5 commits in that order",
        live_timeline == TIMELINE, len(live_timeline)))

    checks.append((
        "b(i) naive oldest-hit is the PRE-EXISTING commit B1 (the defect)",
        naive_i == shas["B1"], naive_i))
    checks.append((
        "b(i) safe: bare needle caught AMBIGUOUS-NEEDLE",
        bi_bare["precheck"] == "AMBIGUOUS-NEEDLE", bi_bare["precheck"]))
    checks.append((
        "b(i) safe: disambiguated needle CONFIRMED-INTRODUCTION == B2",
        bi_dis["confirmed"] == [shas["B2"]], bi_dis["confirmed"]))
    checks.append((
        "b(ii) naive right: oldest-hit == Y",
        naive_ii == shas["Y"], naive_ii))
    checks.append((
        "b(ii) safe still right: CONFIRMED-INTRODUCTION == Y, UNIQUE-AT-REF",
        bii_bare["confirmed"] == [shas["Y"]]
        and bii_bare["precheck"] == "UNIQUE-AT-REF",
        (bii_bare["confirmed"], bii_bare["precheck"])))
    checks.append((
        "c merge reads MOVED-COUNT-ONLY",
        v_merge == "MOVED-COUNT-ONLY", v_merge))
    checks.append((
        "c branch-side S1 reads CONFIRMED-INTRODUCTION",
        v_side == "CONFIRMED-INTRODUCTION", v_side))
    checks.append((
        "c the -S walk's own CONFIRMED-INTRODUCTIONS are exactly [S1]",
        res_c["confirmed"] == [shas["S1"]], res_c["confirmed"]))

    print()
    passed = 0
    for name, ok, got in checks:
        print("  [%s] %-70s got=%r" % ("PASS" if ok else "FAIL", name, got))
        passed += 1 if ok else 0
    print()
    print("  CONTROLS: %d/%d PASS" % (passed, len(checks)))
    print("  DENOMINATORS: arms 3/3; "
          "hits walked: a.bare=%d a.dis=%d b(i).bare=%d b(i).dis=%d b(ii)=%d c=%d; "
          "blobs the needle was counted in: %d (counter incremented inside "
          "describe_blob, not composed)" % (
              len(res_bare["hits"]), len(res_dis["hits"]), len(bi_bare["hits"]),
              len(bi_dis["hits"]), len(bii_bare["hits"]), len(res_c["hits"]),
              BLOBS_COUNTED[0]))
    print()
    print("  VERDICT: %s" % (
        "SAFE-CHECK-BUILT" if passed == len(checks) else "FIX-INCOMPLETE"))


if __name__ == "__main__":
    main()
