"""TASK 0150 KEY-SHAPE — counts-only secret-pattern scan.

Scans the 14 backup originals + .codex/config.toml. Prints MATCH COUNTS only:
never a matched line, never a value, never content. Per file: 0, or
LIVE-KEY-SHAPE PRESENT (count N) with a per-pattern numeric breakdown.
"""
import json
import os
import re
import sys

WT = r"C:\Users\Zvonimir\Desktop\wt-glm-review-2026-10-14"
BACKUP = os.path.join(WT, ".codex", "0110", "backup")
CONFIG = os.path.join(WT, ".codex", "config.toml")
OUT_JSON = os.path.join(WT, ".codex", "0150", "keyshape_result.json")

# Named pattern set (credential SHAPES, matched per line, counted never shown):
PATTERNS = [
    ("P1 api[_-]?key assign", re.compile(r"(?i)api[_\-]?key\s*[:=]")),
    ("P2 token assign", re.compile(r"(?i)\btoken\b\s*[:=]")),
    ("P3 secret assign", re.compile(r"(?i)\bsecret\b\s*[:=]")),
    ("P4 password assign", re.compile(r"(?i)\bpassw(or)?d\b\s*[:=]")),
    ("P5 bearer string", re.compile(r"(?i)bearer\s+[A-Za-z0-9._+\-]{8,}")),
    ("P6 sk- key prefix", re.compile(r"sk[-_][A-Za-z0-9_\-]{12,}")),
    ("P7 40+ entropy run", re.compile(r"[A-Za-z0-9+/=_\-]{40,}")),
]
HEXONLY = re.compile(r"^[0-9a-fA-F]+$")


def scan(path):
    with open(path, "rb") as fh:
        text = fh.read().decode("utf-8", "replace")
    counts = {}
    for label, rx in PATTERNS:
        counts[label] = len(rx.findall(text))
    # P7 attribution split, counts only: hex-only runs look like digests/shas;
    # non-hex 40+ runs are the stronger live-key shape.
    runs = re.findall(r"[A-Za-z0-9+/=_\-]{40,}", text)
    hexish = sum(1 for r in runs if HEXONLY.match(r))
    counts["P7b of-which hex-only(digest-like)"] = hexish
    counts["P7c of-which non-hex(stronger shape)"] = len(runs) - hexish
    total = sum(counts[l] for l, _ in PATTERNS)
    return counts, total


def main():
    targets = sorted(
        os.path.join(BACKUP, f) for f in os.listdir(BACKUP)
        if f.endswith(".orig") and os.path.isfile(os.path.join(BACKUP, f)))
    if os.path.isfile(CONFIG):
        targets.append(CONFIG)
    else:
        print("CONFIG-ABSENT %s (named by the brief; not present in this worktree)" % CONFIG)
    rows = []
    for p in targets:
        counts, total = scan(p)
        rows.append({"file": os.path.basename(p), "path": p, "counts": counts,
                     "total": total})
    print()
    hdr = "%-42s %5s" % ("file", "total")
    print(hdr)
    present = 0
    for r in rows:
        if r["total"] == 0:
            line = "%-42s %5d" % (r["file"], 0)
        else:
            present += 1
            line = "%-42s LIVE-KEY-SHAPE PRESENT (count %d)" % (r["file"], r["total"])
        print(line)
    print()
    print("PER-PATTERN BREAKDOWN (counts only)")
    labels = [l for l, _ in PATTERNS] + ["P7b of-which hex-only(digest-like)",
                                         "P7c of-which non-hex(stronger shape)"]
    print("%-42s %s" % ("file", " ".join(l.split()[0] for l in labels)))
    for r in rows:
        print("%-42s %s" % (r["file"], " ".join(str(r["counts"].get(l, 0)) for l in labels)))
    print()
    print("FILES-SCANNED=%d  FILES-WITH->0=%d  FILES-WITH-0=%d" %
          (len(rows), present, len(rows) - present))
    with open(OUT_JSON, "w", encoding="utf-8", newline="\n") as fh:
        json.dump({"pattern_set": [l for l, _ in PATTERNS], "rows": rows,
                   "files_scanned": len(rows), "files_present": present}, fh, indent=1)
    print("wrote %s (%d B)" % (OUT_JSON, os.path.getsize(OUT_JSON)))


if __name__ == "__main__":
    sys.exit(main())
