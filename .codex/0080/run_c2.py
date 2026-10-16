# TASK-0080 -- CONTROL C2 (the paired one).  Replays TASK-0075's P3 shape
# LIVE in a throwaway worktree and feeds the measured facts to the
# classifier as synthetic Layer-1 records:
#
#   PRIME    import the pristine module in a fresh process -> a timestamp-
#            mode pyc compiled from pristine bytes; probe raises
#            UnpricedCall (the guard's own refusal).
#   PLANT    write a SAME-SIZE mutant (4 B `not ` -> 4 B `0 * `) at the
#            guard, then roll the file's mtime back NS-EXACT to the
#            pre-plant stamp -- the pyc header (int mtime, size) still
#            validates.
#   STALE    fresh-process import serves the PRE-PLANT bytecode while the
#            disk holds the plant: load_proof prints STALE BYTECODE and the
#            probe still raises UnpricedCall even though the mutant on disk
#            would proceed.  That is 0075 P3: a verdict the module under
#            test never produced.  The classifier must print AFFECTED.
#   REVERT   finally-restore: pristine bytes + pristine mtime, verified by
#            sha256 AND an import-level read (load_proof CLEAN, guard
#            refuses again).  Modelled as a record WITH a load-proof CLEAN
#            -> the classifier must print SAFE.
#
# Boundaries: the worktree lives on the Desktop beside the lane tree
# (never under logs\, never inside another lane), is created DETACHED at
# the lane's own HEAD (b67c61ab4, asserted), the plant is restored in a
# `finally` before the worktree is removed, and the worktree's removal is
# verified twice (path gone, absent from `git worktree list`).  No
# provider, gate, cap or master is touched; git runs env-clean per call.
# PASS = stale leg AFFECTED, reverted leg SAFE, raw replay facts all
# observed, restoration verified, worktree gone.
import hashlib
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from classify import classify_facts  # noqa: E402

LANE = os.path.dirname(os.path.dirname(HERE))       # the lane tree root
TOOLS = os.path.join(os.path.dirname(HERE), "0078")  # load_proof lives there
WT = r"C:\Users\Zvonimir\Desktop\wt-glm-0080-c2-2026-10-16"
PINNED_HEAD = "b67c61ab4"
SRC_REL = os.path.join("src", "spendledger.py")

NEEDLE = b"    if not priced and governed:"
MUTANT_LINE = b"    if 0 * priced and governed:"   # 4 B `not ` -> 4 B `0 * `


def clean_env():
    """Lane shells inherit broken GIT_CONFIG_* vars; strip them per call."""
    return {k: v for k, v in os.environ.items()
            if not k.startswith("GIT_CONFIG")}


def git(*args):
    r = subprocess.run(["git", "-C", LANE] + list(args),
                       capture_output=True, env=clean_env())
    out = r.stdout.decode("utf-8", errors="replace")
    err = r.stderr.decode("utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError("git %s -> %d\n%s" % (" ".join(args),
                                                 r.returncode, err))
    return out


def probe(label):
    r = subprocess.run(
        [sys.executable, os.path.join(HERE, "c2_probe.py"), WT, TOOLS, label],
        capture_output=True)
    line = r.stdout.decode("utf-8", errors="replace").strip()
    if r.returncode != 0 or not line:
        raise RuntimeError("probe %s died (%d): %s%s"
                           % (label, r.returncode, line,
                              r.stderr.decode("utf-8", errors="replace")))
    return json.loads(line.splitlines()[-1])


def sha256(data):
    return hashlib.sha256(data).hexdigest()


if os.path.exists(WT):
    print("ABORT: %s already exists (earlier C2 run left it); refusing "
          "to reuse a tree of unknown state." % WT)
    sys.exit(1)

head = git("rev-parse", "HEAD").strip()
assert head.startswith(PINNED_HEAD), \
    "lane HEAD moved to %s; C2 was pinned to %s -- re-pin deliberately" \
    % (head, PINNED_HEAD)
git("worktree", "add", "--detach", WT, head)

src = os.path.join(WT, SRC_REL)
result = {"pinned_head": head, "worktree": WT, "legs": {}, "pass": False}

pristine = open(src, "rb").read()
pristine_sha = sha256(pristine)
assert pristine.count(NEEDLE) == 1, "guard needle not unique in worktree copy"
st = os.stat(src)
stamp = (st.st_atime_ns, st.st_mtime_ns)

# PRIME: a fresh process imports pristine bytes and compiles the pyc.
p = probe("prime")
result["prime"] = p
assert p["load_proof"] == "CLEAN", "prime not CLEAN: %s" % p
assert p["probe_raised"].startswith("UnpricedCall"), \
    "pristine guard did not refuse: %s" % p["probe_raised"]

restored_ok = False
try:
    # PLANT: same-size write, then ns-exact mtime rollback.
    mutant = pristine.replace(NEEDLE, MUTANT_LINE)
    assert len(mutant) == len(pristine) and mutant != pristine
    with open(src, "wb") as fh:
        fh.write(mutant)
    os.utime(src, ns=stamp)
    on_disk = open(src, "rb").read()
    assert on_disk == mutant, "plant did not land on disk"

    # STALE LEG: the raw replay facts, then the synthetic record.
    s = probe("planted")
    result["legs"]["stale_raw"] = s
    raw_ok = (s["load_proof"] == "STALE BYTECODE"
              and s["probe_raised"].startswith("UnpricedCall"))
    rec_stale = {"line": None, "entry": "c2-replay", "excerpt":
                 "c2-replay of 0075 P3: disk planted, pyc header still "
                 "valid, import served pre-plant bytes",
                 "outcome": "survive",
                 "stale_marker": "c2-replay: load-proof STALE BYTECODE "
                 "over a planted disk (0075 P3 shape)"}
    v1, why1, _ = classify_facts(rec_stale)
    result["legs"]["stale"] = {"verdict": v1, "reason": why1,
                               "raw_replay_observed": raw_ok}
finally:
    # REVERT (always): pristine bytes + pristine stamp, then verify by
    # sha256 AND an import-level read of the module object.
    with open(src, "wb") as fh:
        fh.write(pristine)
    os.utime(src, ns=stamp)
    back_sha = sha256(open(src, "rb").read())
    r = probe("reverted")
    result["legs"]["revert_raw"] = r
    restored_ok = (back_sha == pristine_sha
                   and r["load_proof"] == "CLEAN"
                   and r["probe_raised"].startswith("UnpricedCall"))
    rec_safe = {"line": None, "entry": "c2-replay", "excerpt":
                "c2-replay revert leg: pristine bytes restored, mtime "
                "restored, load-proof CLEAN at import",
                "outcome": "survive", "loadproof_clear": True,
                "revert_claim": True}
    v2, why2, _ = classify_facts(rec_safe)
    result["legs"]["revert"] = {"verdict": v2, "reason": why2,
                                "sha256_equal": back_sha == pristine_sha,
                                "restoration_verified": restored_ok}

# Cleanup: throw the whole tree away and prove it is gone.
git("worktree", "remove", "--force", WT)
gone = not os.path.exists(WT) and WT not in git("worktree", "list",
                                                "--porcelain")
result["worktree_removed"] = gone

result["pass"] = (result["legs"]["stale"]["verdict"] == "AFFECTED"
                  and result["legs"]["revert"]["verdict"] == "SAFE"
                  and result["legs"]["stale"]["raw_replay_observed"]
                  and restored_ok and gone)
with open(os.path.join(HERE, "c2_result.json"), "w", encoding="utf-8") as fh:
    json.dump(result, fh, indent=1)

print("PRIME   load_proof=%s raised=%s" % (p["load_proof"],
                                           p["probe_raised"]))
print("PLANTED load_proof=%s raised=%s  <- 0075 P3 shape (forged verdict)"
      % (s["load_proof"], s["probe_raised"]))
print("  classifier -> %s (%s)" % (v1, why1[:70]))
print("REVERT  load_proof=%s raised=%s sha_equal=%s"
      % (r["load_proof"], r["probe_raised"], back_sha == pristine_sha))
print("  classifier -> %s (%s)" % (v2, why2[:70]))
print("worktree removed and verified gone: %s" % gone)
print("c2_result.json written; C2 %s"
      % ("PASS" if result["pass"] else "FAIL"))
sys.exit(0 if result["pass"] else 1)
