"""TASK 0065 suite comparison - branch run vs reference run, by name-set.

Reference: full suite at 1ea8105bf (the parent of the fix commit b77cd4b20).
Branch:    full suite at b77cd4b20 (the fix tip).

Doctrine: a baseline is a NAMED LIST compared by SET, never by count; a GONE
name must be verified positively (found running and passing in the branch log
- unittest prints docstrings between the inline name and its outcome, so the
closing FAIL/ERROR blocks are the authority for what failed, and the inline
verbose lines are the authority for what ran and passed).
"""
import re
import sys

REF = sys.argv[1]
BR = sys.argv[2]
REFLOG = sys.argv[3]
BRLOG = sys.argv[4]


def names_from_verdict(path):
    out = []
    for line in open(path, encoding="utf-8", errors="replace"):
        m = re.match(r"\s*(FAIL|ERROR):\s+(\S+)\s*$", line)
        if m:
            out.append(m.group(2))
    return out


def passed_inline(logpath, name):
    """The name ran and PASSED in this log (inline verbose line 'name ... ok')."""
    tail = name.rsplit(".", 1)[-1]
    pat = re.compile(r"^\s*%s\s*\([^)]*\)[^\n]*\.\.\.\s*ok\b" % re.escape(tail), re.M)
    return bool(pat.search(open(logpath, encoding="utf-8", errors="replace").read()))


R = set(names_from_verdict(REF))
B = set(names_from_verdict(BR))
new, gone = B - R, R - B
print("reference names: %d   branch names: %d   BOTH: %d" % (len(R), len(B), len(R & B)))
print("NEW (branch has, reference has not): %d" % len(new))
for n in sorted(new):
    print("   NEW:", n)
print("GONE (reference has, branch has not): %d" % len(gone))
for n in sorted(gone):
    print("   GONE: %s   [verified passing in branch log: %s]"
          % (n, passed_inline(BRLOG, n)))
