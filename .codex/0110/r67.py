# TASK-0110 0067 group (L1925/L1929/L1933) re-derivation at HEAD 8dc1ed55f.
# Control leg (unmutated), then three plant->run->restore cycles, each with
# byte-exact backup/restore (sha256) and the 0079 pyc protocol.
import hashlib
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HERE = os.path.join(ROOT, ".codex", "0110")
BAK = os.path.join(HERE, "backup")
os.makedirs(BAK, exist_ok=True)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
for k in [k for k in os.environ if k.startswith("GIT_CONFIG")]:
    del os.environ[k]

TEST = "tests.test_the_word_ceiling_is_enforced_on_the_composed_body"

# (tag, file, unique-search, replacement) -- all single-occurrence, verified
# by the assert in plant().
PLANTS = [
    ("L1925", "src/sequencegate.py",
     "        if words > ceiling:\n",
     "        if False and words > ceiling:  # 0110 re-plant L1925\n"),
    ("L1929", "src/bisonfactory.py",
     "\n    _refuse_composed_ceiling(campaign, plan, recs, report)\n",
     "\n    pass  # 0110 re-plant L1929: stage() call unwired\n"),
    ("L1933", "src/bisonfactory.py",
     "        composed = _composed_bodies(lead, copy_entries, held)\n"
     "        result = sequencegate.check_composed_length(composed)\n",
     "        composed = _composed_bodies(lead, copy_entries, held)\n"
     "        bare = dict(zip(composed,\n"
     "                        [e.get(\"body\") or \"\" for e in copy_entries]))\n"
     "        result = sequencegate.check_composed_length(bare)\n"),
]


def sha(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def kill_pycs():
    for d in (os.path.join(ROOT, "src", "__pycache__"),
              os.path.join(ROOT, "scripts", "__pycache__"),
              os.path.join(ROOT, "tests", "__pycache__")):
        if os.path.isdir(d):
            shutil.rmtree(d)


def run_tests(tag):
    kill_pycs()
    out = os.path.join(HERE, "r67-%s.txt" % tag)
    with open(out, "wb") as fh:
        p = subprocess.run([sys.executable, "-m", "unittest", "-v", TEST],
                           cwd=ROOT, stdout=fh, stderr=subprocess.STDOUT)
    print("  %s: exit=%d -> r67-%s.txt" % (tag, p.returncode, tag))
    with open(out, encoding="utf-8", errors="replace") as fh:
        lines = fh.read().splitlines()
    for l in lines[-3:]:
        if l.strip():
            print("    | %s" % l[:160])
    fails = [l for l in lines if " (tests." in l and l.startswith(("FAIL:", "ERROR:", "UNEXPECTED"))]
    return fails


def plant(tag, rel, search, repl):
    p = os.path.join(ROOT, rel)
    orig = sha(p)
    shutil.copyfile(p, os.path.join(BAK, os.path.basename(rel) + "." + tag + ".orig"))
    with open(p, "rb") as fh:
        raw = fh.read()
    n = raw.count(search.encode("utf-8"))
    assert n == 1, "%s: search found %d times in %s (need exactly 1)" % (tag, n, rel)
    with open(p, "wb") as fh:
        fh.write(raw.replace(search.encode("utf-8"), repl.encode("utf-8")))
    print("planted %s in %s (orig sha256=%s -> %s)"
          % (tag, rel, orig[:16], sha(p)[:16]))
    return orig


def restore(tag, rel, orig_sha):
    p = os.path.join(ROOT, rel)
    shutil.copyfile(os.path.join(BAK, os.path.basename(rel) + "." + tag + ".orig"), p)
    ok = sha(p) == orig_sha
    print("restored %s sha256 %s expected %s -> %s"
          % (tag, sha(p)[:16], orig_sha[:16], "MATCH" if ok else "MISMATCH"))
    assert ok


print("=== control leg (unmutated) ===")
run_tests("control")

for tag, rel, search, repl in PLANTS:
    print("=== %s ===" % tag)
    orig = plant(tag, rel, search, repl)
    try:
        fails = run_tests(tag.lower() + "-red")
        for f in fails:
            print("    RED %s" % f[:160])
    finally:
        restore(tag, rel, orig)
    run_tests(tag.lower() + "-green")

st = subprocess.run(["git", "status", "--porcelain", "src/"],
                    cwd=ROOT, capture_output=True, text=True)
print("git status src/ -> %r" % st.stdout.strip())
