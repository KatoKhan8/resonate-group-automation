"""TASK 0064 Q3 - attribute the 406 failing names of the 11:22-12:00 run.

Inputs (all sanctioned, no other lane's worktree):
  - this worktree's scripts/suite_verdict.txt  (the 406 run, log mtime 12:00:32)
  - resonate-ops/ref-2bf7b8a57/scripts/suite_verdict.txt (master reference, 10-14 23:46)
  - this worktree's scripts/suite_run.log      (tracebacks of the 406 run)
  - git ls-tree / diff at 2bf7b8a57, 93162471d, 1ea8105bf

Everything printed is derived from the name lists, never from a scalar.
"""
import os
import re
import subprocess
from collections import Counter

ROOT = r"C:\Users\Zvonimir\Desktop\wt-glm-review-2026-10-14"
REF_VERDICT = r"C:\Users\Zvonimir\Desktop\resonate-ops\ref-2bf7b8a57\scripts\suite_verdict.txt"
ENV = {k: v for k, v in os.environ.items() if not k.startswith("GIT_CONFIG")}


def git(*a):
    r = subprocess.run(["git", *a], cwd=ROOT, env=ENV, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit("git failed (%s): %s" % (" ".join(a), r.stderr.strip()))
    return r.stdout


def names_from_verdict(path):
    out = []
    for line in open(path, encoding="utf-8", errors="replace"):
        m = re.match(r"\s*(FAIL|ERROR):\s+(\S+)\s*$", line)
        if m:
            out.append(m.group(2))
    return out


review = names_from_verdict(os.path.join(ROOT, "scripts", "suite_verdict.txt"))
master = names_from_verdict(REF_VERDICT)
R, M = set(review), set(master)
print("review-run names: %d read, %d unique" % (len(review), len(R)))
print("master-ref names: %d read, %d unique" % (len(master), len(M)))

new, gone, both = R - M, M - R, R & M
print("NEW (review-master): %d   GONE (master-review): %d   BOTH: %d"
      % (len(new), len(gone), len(both)))
for g in sorted(gone):
    print("  GONE:", g)


def mods(sha):
    s = set()
    for p in git("ls-tree", "-r", "--name-only", sha, "tests/").splitlines():
        b = os.path.basename(p)
        if p.startswith("tests/") and b.endswith(".py"):
            s.add(b[:-3])
    return s


m_ref, m_det, m_br = mods("2bf7b8a57"), mods("1ea8105bf"), mods("93162471d")
newfile_names = {n for n in R if n.split(".")[0] in (m_det - m_ref)}
impossible_at_det = {n for n in R if n.split(".")[0] not in m_det}
print("406-names inside modules ABSENT at 2bf7b8a57 (new files since master ref): %d" % len(newfile_names))
for n in sorted(newfile_names):
    print("   new-file name:", n)
print("406-names inside modules ABSENT at 1ea8105bf (must be 0): %d" % len(impossible_at_det))
for n in sorted(impossible_at_det):
    print("   IMPOSSIBLE:", n)

# which failing modules differ in content between the branch and the detached tree
diff_mods = set()
for p in git("diff", "--name-only", "93162471d", "1ea8105bf", "--", "tests/").splitlines():
    b = os.path.basename(p)
    if b.endswith(".py"):
        diff_mods.add(b[:-3])
overlap = {n for n in R if n.split(".")[0] in diff_mods}
print("406-names inside modules whose CONTENT differs 93162471d vs 1ea8105bf: %d" % len(overlap))
for n in sorted(overlap):
    print("   differs-between-trees:", n)

# traceback classes, read out of this run's own log
log = open(os.path.join(ROOT, "scripts", "suite_run.log"),
           encoding="utf-8", errors="replace").read()
pat = re.compile(r"={10,}\s*\n(?:FAIL|ERROR):\s+([^\s(]+)\s+\(([^)]+)\)\s*\n(.*?)"
                 r"(?=\n={10,}|\nRan \d+ tests?|\Z)", re.S)
cls_of = {}
for meth, cls, body in pat.findall(log):
    if cls.startswith("tests."):
        cls = cls[len("tests."):]
    key = cls + "." + meth
    if "3221225794" in body or "0xC0000142" in body:
        cls_of[key] = "A_dll_init_failed"
    elif re.search(r"in ''|line: ''|could not answer|FileNotFoundError|The system cannot find the file", body):
        cls_of[key] = "B_empty_subprocess_output"
    else:
        cls_of[key] = "C_other"


def klass(name):
    return cls_of.get(name, "not_recovered")


print("classes over ALL %d names: %s" % (len(R), dict(Counter(klass(n) for n in sorted(R)))))
print("classes over the %d NEW: %s" % (len(new), dict(Counter(klass(n) for n in sorted(new)))))
for n in sorted(n for n in new if klass(n) == "C_other"):
    print("   class-C NEW:", n)
for n in sorted(n for n in new if klass(n) == "not_recovered"):
    print("   not-recovered NEW:", n)

born_red = ("test_a_safety_pause_fails_open.TheHaltPausesWithoutAGateToken."
            "test_the_pause_is_performed_with_no_gatetoken_presented")
print("born-red halt name in 406: %s ; in NEW-vs-master: %s ; class: %s"
      % (born_red in R, born_red in new, klass(born_red)))

supp = ("test_fixture_hygiene.TestTheSuppressionRosterIsNotInGit."
        "test_the_real_roster_is_ignored_so_it_cannot_be_added_by_accident")
print("suppression-roster name in 406: %s ; class: %s" % (supp in R, klass(supp)))
