# TASK-0140 -- stage 1: enumerate the 64 evidence-absent UNKNOWN rows from the
# CERTIFIED 0120 pipeline (extract/classify/widen imported UNCHANGED), gate on
# the certified tallies in table_result.json, and pull from each row's span +
# W1 evidence block ONLY the artefact references it carries (paths, git SHAs,
# lane-file line pointers).  No block prose is printed.  Read-only over the
# corpus; writes rows64.json for stage 2.
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CODEX = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(CODEX, "0090"))
sys.path.insert(0, os.path.join(CODEX, "0080"))
sys.path.insert(0, os.path.join(CODEX, "0120"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import extract_pilotcaps                 # noqa: E402  UNCHANGED
from classify import classify_records, tally   # noqa: E402  UNCHANGED
import run_0090                          # noqa: E402  UNCHANGED
import widen                             # noqa: E402  UNCHANGED

LANE_PILOTCAPS = run_0090.LANE_PILOTCAPS
CERT = json.load(open(os.path.join(CODEX, "0120", "table_result.json"),
                      encoding="utf-8"))
CERT_FLIPS = sorted(f["line"] for f in CERT["flips"])   # 10480 15382 16148

text = open(LANE_PILOTCAPS, "rb").read().decode("utf-8")
lines = [ln.rstrip("\r") for ln in text.split("\n")]
print("corpus %s  sha256 %s  %d B  %d lines" % (
    LANE_PILOTCAPS, hashlib.sha256(text.encode("utf-8")).hexdigest(),
    len(text.encode("utf-8")), len(lines)))

recs, unp = extract_pilotcaps.parse(text)
cls = classify_records(recs)
kept = [r for r in cls if r["line"] not in run_0090.EXCLUSIONS]
t = tally(kept)
wide = {w["line"]: w for w in widen.widen_corpus(kept, text)}

gate = []
gate.append(("kept 82", len(kept) == 82, len(kept)))
gate.append(("strict 14/67/1", t == CERT["strict"], t))
ou = {"SAFE": 0, "UNKNOWN": 0, "AFFECTED": 0}
for w in wide.values():
    if w["strict"] == "UNKNOWN":
        ou[w["wide"]] += 1
gate.append(("unknown67 widened 3/64/0", ou == CERT["unknown67"], ou))
flips = sorted(w["line"] for w in wide.values() if w["wide"] != w["strict"])
gate.append(("flips == certified 3", flips == CERT_FLIPS, flips))
drift = [g for g in gate if not g[1]]
for name, ok, val in gate:
    print("gate %-28s %s  %s" % (name, "PASS" if ok else "DRIFT", val))
if drift:
    print("DRIFT -- corpus moved since be6ed8b21's certification; rows are "
          "still anchored by line number (append-only file)")

rows64 = sorted(w["line"] for w in wide.values()
                if w["strict"] == "UNKNOWN" and w["wide"] == "UNKNOWN")
print("rows64 enumerated: %d (67 strict-UNKNOWN minus %d certified flips)"
      % (len(rows64), len(CERT_FLIPS)))

# ---- artefact-reference extraction over row span + W1 block ONLY ----------
ABS_PATH = re.compile(r'[A-Za-z]:\\[^\s`)\]\|,"\'{]+')     # C:\... windows abs
BACKTICK = re.compile(r'`([^`\n]{2,120})`')
LANE_REF = re.compile(r'\bLANE-[a-z]+\.md\b')
LINE_REF = re.compile(r'\bL(\d{2,6})\b')
HEX = re.compile(r'(?<![0-9a-f])[0-9a-f]{7,40}(?![0-9a-f])')
ARTEXT = re.compile(
    r'\.(?:py|json|md|out|txt|log|jsonl|csv|ps1)\b|[/\\]|^TASK-\d+', re.I)

def refs_of(s):
    refs = []
    for m in ABS_PATH.finditer(s):
        refs.append(("path", m.group(0).rstrip('.,;:')))
    for m in BACKTICK.finditer(s):
        tok = m.group(1).strip()
        if ARTEXT.search(tok) and not re.match(r'^[A-Za-z]:\\', tok):
            refs.append(("tick", tok))
        elif re.match(r'^[0-9a-f]{7,40}$', tok):
            refs.append(("sha", tok))
    for m in LANE_REF.finditer(s):
        refs.append(("lane", m.group(0)))
    for m in HEX.finditer(s.replace('`', ' ')):
        tok = m.group(0)
        if len(tok) in (7, 8, 10, 12, 40):
            refs.append(("sha?", tok))
    # dedupe, keep order
    seen, out = set(), []
    for kind, tok in refs:
        if (kind, tok) not in seen:
            seen.add((kind, tok))
            out.append((kind, tok))
    return out

def need_class(rec, w):
    """What evidence promotes this row, from outcome + widened reason."""
    r = w["reason_wide"]
    if rec["outcome"] == "kill":
        if "no name over row+block" in r:
            return "kill:needs-names+signature"
        if "no signature over row+block" in r:
            return "kill:needs-signature"
        if "W2a REFUSED" in r:
            return "kill:needs-count-match"
        if "W2b REFUSED" in r:
            return "kill:needs-killreason-count"
        return "kill:other"
    if rec["outcome"] == "survive":
        return "survive:needs-clearing-fact"
    return "stale-only:no-widened-path"

out_rows = []
by_need = {}
for ln in rows64:
    rec = next(r for r in kept if r["line"] == ln)
    w = wide[ln]
    span = lines[ln - 1:rec["end_line"]]
    block = [lines[n - 1] for n in w["block"]]
    refs = refs_of("\n".join(span) + "\n" + "\n".join(block))
    need = need_class(rec, w)
    by_need[need] = by_need.get(need, 0) + 1
    out_rows.append({"line": ln, "end_line": rec["end_line"],
                     "outcome": rec["outcome"], "need": need,
                     "reason_wide": w["reason_wide"],
                     "block": w["block"], "refs": refs})

with open(os.path.join(HERE, "rows64.json"), "w", encoding="utf-8") as fh:
    json.dump({"corpus_sha256": hashlib.sha256(
                   text.encode("utf-8")).hexdigest(),
               "lines": len(lines), "kept": len(kept), "strict": t,
               "unknown67_widened": ou, "rows": out_rows}, fh, indent=1)
print("\nneed classes (denominator %d):" % len(rows64))
for k in sorted(by_need):
    print("  %-32s %2d" % (k, by_need[k]))
noref = sum(1 for r in out_rows if not r["refs"])
print("rows with ZERO artefact refs: %d/%d" % (noref, len(out_rows)))
print("\nper-row refs (kind:token, truncated):")
for r in out_rows:
    rs = " ".join("%s:%s" % (k, (t[:58] + ".." if len(t) > 60 else t))
                  for k, t in r["refs"][:6])
    print("L%-6d %-28s %s" % (r["line"], r["need"], rs or "(none)"))
