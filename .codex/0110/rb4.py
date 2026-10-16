# TASK-0110 B4 group (L56a, L56b) re-derivation at HEAD 8dc1ed55f.
# The surviving artifact is docs/REVIEW-GLM-2026-10-14-QUEUE.md section B4
# (committed 04c0bbb37, present at HEAD), which quotes both signatures.
# This re-plant checks the reader's test: run the recorded mutations at HEAD
# and compare against the doc's quoted text.
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

TEST = "tests.test_no_template_escapes_the_word_contract"
REL = "src/cadence.py"

# L56a: orphan in the register -> coverage guard red naming it, exactly the
# doc's 'b4_planted_uncovered'. Note shape: the only red is the coverage walk.
ORPHAN_SEARCH = 'TEMPLATES = {\n    "linkedin_intro": {\n'
ORPHAN_REPL = ('TEMPLATES = {\n'
               '    "b4_planted_uncovered": '
               '{"note": "planted uncovered template"},\n'
               '    "linkedin_intro": {\n')

# L56b: angle_shift_champion's body temporarily under the em4 ceiling ->
# the expectedFailure self-destructs (doc: 'the ledger cannot outlive the
# defect it names').
FLIP_SEARCH = (
    '        "body": "{first_name}, the thing I find most often at agencies the "\n'
    '                "size of {company} is that the answer already exists. Somebody "\n'
    '                "assembles it.\\n\\n"\n'
    '                "Usually that is one person pulling hours out of one system, "\n'
    '                "budgets out of another and the plan out of a third, so that "\n'
    '                "the end of week conversation has numbers in it. It works. It "\n'
    '                "is also the most expensive hour of the week, because it is "\n'
    '                "the hour that cannot be spent on the thing the numbers are "\n'
    '                "about.\\n\\n"\n'
    '                "What I would want to know in your position is not whether the "\n'
    '                "number can be produced, but how long producing it takes and "\n'
    '                "how far behind it is by the time it lands.\\n\\n"\n'
    '                "How long does that take at {company} at the moment?"},\n')
FLIP_REPL = ('        "body": "planted rewrite under the ceiling for '
             '{company}."},\n')


def sha(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def kill_pycs():
    for d in (os.path.join(ROOT, "src", "__pycache__"),
              os.path.join(ROOT, "scripts", "__pycache__"),
              os.path.join(ROOT, "tests", "__pycache__")):
        if os.path.isdir(d):
            shutil.rmtree(d)


def run_tests(tag, grep):
    kill_pycs()
    out = os.path.join(HERE, "rb4-%s.txt" % tag)
    with open(out, "wb") as fh:
        p = subprocess.run([sys.executable, "-m", "unittest", TEST],
                           cwd=ROOT, stdout=fh, stderr=subprocess.STDOUT)
    with open(out, encoding="utf-8", errors="replace") as fh:
        lines = fh.read().splitlines()
    print("  %s: exit=%d" % (tag, p.returncode))
    for l in lines:
        for g in grep:
            if g in l:
                print("    | %s" % l[:170])
                break
    for l in lines[-2:]:
        if l.strip():
            print("    | %s" % l[:170])
    return lines


def cycle(tag, search, repl, grep):
    p = os.path.join(ROOT, REL)
    orig = sha(p)
    shutil.copyfile(p, os.path.join(BAK, "cadence.py." + tag + ".orig"))
    with open(p, "rb") as fh:
        raw = fh.read()
    n = raw.count(search.encode("utf-8"))
    assert n == 1, "%s: search found %d times (need 1)" % (tag, n)
    with open(p, "wb") as fh:
        fh.write(raw.replace(search.encode("utf-8"), repl.encode("utf-8")))
    print("planted %s (cadence.py %s -> %s)"
          % (tag, orig[:16], sha(p)[:16]))
    try:
        run_tests(tag.lower() + "-red", grep)
    finally:
        shutil.copyfile(os.path.join(BAK, "cadence.py." + tag + ".orig"), p)
        ok = sha(p) == orig
        print("restored %s -> %s" % (tag, "MATCH" if ok else "MISMATCH"))
        assert ok
    run_tests(tag.lower() + "-green", [])


print("=== control (unmutated; doc says 8 tests, OK expected failures=3) ===")
run_tests("control", ["OK", "FAILED"])
print("=== L56a: orphan template ===")
cycle("L56a", ORPHAN_SEARCH, ORPHAN_REPL,
      ["b4_planted_uncovered", "NOTHING covers"])
print("=== L56b: ledger flip ===")
cycle("L56b", FLIP_SEARCH, FLIP_REPL,
      ["UNEXPECTED SUCCESS", "unexpected successes"])

st = subprocess.run(["git", "status", "--porcelain", "src/"],
                    cwd=ROOT, capture_output=True, text=True)
print("git status src/ -> %r" % st.stdout.strip())
