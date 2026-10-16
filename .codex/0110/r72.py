# TASK-0110 L2557 (0072) re-derivation: swap pre-fix blobs in, run the two
# door tests, restore byte-exact from backup. 0079 protocol: pyc deleted
# before every leg. try/finally so the tree is restored even on failure.
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
# lane shells inherit broken GIT_CONFIG_* (memory: git-broken-in-shells);
# clear so every embedded git call works regardless of launcher.
for k in [k for k in os.environ if k.startswith("GIT_CONFIG")]:
    del os.environ[k]

TARGETS = {
    "scripts/batch_activate.py": "e1c3376934f89079fdaadd2a0547ba3f5fe42d9d",
    "scripts/resume_487.py": "932f439676d5e3b943f411ccfaae9a0c291e0a52",
}
TESTS = ("tests.test_a_resume_verb_from_batch_activate_must_pass_the_door",
         "tests.test_a_resume_verb_from_resume_487_must_pass_the_door")


def sha(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def kill_pycs():
    for rel in list(TARGETS) + ["src/providerwrites.py"]:
        d = os.path.join(os.path.dirname(os.path.join(ROOT, rel)), "__pycache__")
        if os.path.isdir(d):
            shutil.rmtree(d)
            print("  pyc dir removed: %s" % d)


def run_tests(tag):
    kill_pycs()
    out = os.path.join(HERE, "r72-%s.txt" % tag)
    with open(out, "wb") as fh:
        p = subprocess.run(
            [sys.executable, "-m", "unittest", "-v"] + list(TESTS),
            cwd=ROOT, stdout=fh, stderr=subprocess.STDOUT)
    print("  %s leg: exit=%d -> %s" % (tag, p.returncode, out))
    with open(out, encoding="utf-8", errors="replace") as fh:
        tail = [l for l in fh.read().splitlines() if l.strip()][-4:]
    for l in tail:
        print("    | %s" % l[:150])


orig_shas = {}
for rel in TARGETS:
    p = os.path.join(ROOT, rel)
    orig_shas[rel] = sha(p)
    shutil.copyfile(p, os.path.join(BAK, os.path.basename(rel) + ".orig"))
    print("backup %s sha256=%s" % (rel, orig_shas[rel][:16]))

try:
    for rel, blob in TARGETS.items():
        r = subprocess.run(["git", "cat-file", "blob", blob], cwd=ROOT,
                           capture_output=True)
        assert r.returncode == 0, r.stderr
        with open(os.path.join(ROOT, rel), "wb") as fh:
            fh.write(r.stdout)
        print("planted %s <- blob %s (%d B, sha256=%s)"
              % (rel, blob[:9], len(r.stdout),
                 hashlib.sha256(r.stdout).hexdigest()[:16]))
    run_tests("red")
finally:
    for rel in TARGETS:
        p = os.path.join(ROOT, rel)
        shutil.copyfile(os.path.join(BAK, os.path.basename(rel) + ".orig"), p)
        ok = sha(p) == orig_shas[rel]
        print("restored %s sha256 %s expected %s -> %s"
              % (rel, sha(p)[:16], orig_shas[rel][:16], "MATCH" if ok else "MISMATCH"))
    st = subprocess.run(["git", "status", "--porcelain", "scripts/"],
                        cwd=ROOT, capture_output=True, text=True)
    print("git status scripts/ -> %r" % st.stdout.strip())
run_tests("green")
