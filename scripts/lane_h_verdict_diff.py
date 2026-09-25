"""Diff two suite verdicts BY NAME, because a baseline that is a count cannot
say which tests changed.

    py -3 scripts/lane_h_verdict_diff.py <baseline.txt> <current.txt>

This repository has learned twice that comparing 110 with 118 says nothing.
The names are what say whether a change caused a failure.
"""
import sys
import re
import collections

LINE = re.compile(r"^\s*(FAIL|ERROR):\s+(\S+)\s+\((\S+)\)")


def names(path):
    out = {}
    with open(path, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            hit = LINE.match(line)
            if hit:
                kind, _short, full = hit.groups()
                out[full] = kind
    return out


def module(full):
    return full.split(".")[0]


base_path, cur_path = sys.argv[1], sys.argv[2]
base, cur = names(base_path), names(cur_path)
print("baseline %-34s %4d distinct failing name(s)" % (base_path, len(base)))
print("current  %-34s %4d distinct failing name(s)" % (cur_path, len(cur)))

new = sorted(set(cur) - set(base))
gone = sorted(set(base) - set(cur))
both = sorted(set(base) & set(cur))
print("\n  in both          %4d" % len(both))
print("  NEW in current   %4d" % len(new))
print("  gone since base  %4d" % len(gone))

print("\nNEW failing names, by module:")
for mod, count in collections.Counter(module(n) for n in new).most_common():
    print("  %-62s %3d" % (mod, count))

print("\nGONE since baseline, by module:")
for mod, count in collections.Counter(module(n) for n in gone).most_common():
    print("  %-62s %3d" % (mod, count))

print("\nDoes any failing name belong to a module this lane touched?")
print("  this lane added only scripts/lane_h_*.py and one docs/ file.")
mine = [n for n in cur if "lane_h" in n.lower()]
print("  failing names mentioning lane_h: %d" % len(mine))
