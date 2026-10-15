"""TASK 0064 Q3 part 2 - traceback classes with the corrected unittest key.

Python 3.11+ unittest writes headers as:
    FAIL: test_x (tests.test_y.Class.test_x)
so the parenthesized field is the FULL dotted name. Classify every failing
name of the 406 run by reading its traceback body out of suite_run.log,
then intersect with the NEW-vs-master set (recomputed here from the two
sanctioned verdict files).
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


R = set(names_from_verdict(os.path.join(ROOT, "scripts", "suite_verdict.txt")))
M = set(names_from_verdict(REF_VERDICT))
new = R - M
print("406 set: %d ; master set: %d ; NEW: %d" % (len(R), len(M), len(new)))

log = open(os.path.join(ROOT, "scripts", "suite_run.log"),
           encoding="utf-8", errors="replace").read()

# header: kind: method (full.dotted.name)
pat = re.compile(r"={10,}\s*\n(?:FAIL|ERROR):\s+\S+\s+\(([^)]+)\)\s*\n(.*?)"
                 r"(?=\n={10,}|\nRan \d+ tests?|\Z)", re.S)
cls_of = {}
body_of = {}
for full, body in pat.findall(log):
    if full.startswith("tests."):
        full = full[len("tests."):]
    if "." in full:  # module.Class.method
        cls_of[full] = ("A_dll_init_failed"
                        if ("3221225794" in body or "0xC0000142" in body)
                        else ("B_empty_subprocess_output"
                              if re.search(r"in ''|line: ''|could not answer|FileNotFoundError"
                                           r"|The system cannot find the file", body)
                              else "C_other"))
        body_of[full] = body

print("traceback headers recovered: %d distinct names" % len(cls_of))
missing = R - set(cls_of)
print("406 names with NO recovered traceback: %d" % len(missing))
for n in sorted(missing):
    print("   missing:", n)


def klass(name):
    return cls_of.get(name, "not_recovered")


print("classes over ALL %d: %s" % (len(R), dict(Counter(klass(n) for n in sorted(R)))))
print("classes over NEW %d: %s" % (len(new), dict(Counter(klass(n) for n in sorted(new)))))
print("classes over BOTH (shared with master) %d: %s"
      % (len(R & M), dict(Counter(klass(n) for n in sorted(R & M)))))
for n in sorted(n for n in new if klass(n) == "C_other"):
    print("   class-C NEW:", n)

born_red = ("test_a_safety_pause_fails_open.TheHaltPausesWithoutAGateToken."
            "test_the_pause_is_performed_with_no_gatetoken_presented")
print("born-red: in406=%s class=%s" % (born_red in R, klass(born_red)))
print("born-red body excerpt:")
for line in body_of.get(born_red, "").splitlines()[:12]:
    print("   |", line)

supp = ("test_fixture_hygiene.TestTheSuppressionRosterIsNotInGit."
        "test_the_real_roster_is_ignored_so_it_cannot_be_added_by_accident")
print("suppression-roster: in406=%s class=%s" % (supp in R, klass(supp)))
for line in body_of.get(supp, "").splitlines()[:8]:
    print("   |", line)

# last lineage question: NEW names sitting in a test module whose CONTENT
# differs between the master ref and the detached tree
diff_mods = set()
for p in git("diff", "--name-only", "2bf7b8a57", "1ea8105bf", "--", "tests/").splitlines():
    b = os.path.basename(p)
    if b.endswith(".py"):
        diff_mods.add(b[:-3])
cand = {n for n in new if n.split(".")[0] in diff_mods}
print("NEW names inside a test module whose content differs 2bf7b8a57->1ea8105bf: %d" % len(cand))
for n in sorted(cand):
    print("   module-changed NEW:", n)
