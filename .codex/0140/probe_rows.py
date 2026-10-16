# TASK-0140 -- bounded probe: for a handful of representative rows print the
# row span + W1 block (the ONLY prose pulled into context all run), the owning
# TASK entry header, and path-like tokens from the entry head.  Read-only.
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CODEX = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(CODEX, "0090"))
sys.path.insert(0, os.path.join(CODEX, "0120"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import run_0090                          # noqa: E402

text = open(run_0090.LANE_PILOTCAPS, "rb").read().decode("utf-8")
lines = [ln.rstrip("\r") for ln in text.split("\n")]
HDR = re.compile(r'^## .*TASK[ -]\d+', re.I)
ENTRY_HEAD = re.compile(r'^#{1,3} ')
TOK = re.compile(r'`[^`\n]{2,120}`|[A-Za-z]:\\[^\s`)\]|,"\']+|(?<![\w-])[\w.-]*'
                 r'(?:py|json|md|out|txt|log|jsonl)(?![\w-])', re.I)

def entry_of(ln):
    for k in range(ln - 1, -1, -1):
        if HDR.match(lines[k]):
            return k + 1, lines[k]
    return None, "(no TASK header)"

SAMPLES = [5478, 8283, 9505, 12061, 15661, 5926, 7645]
data = __import__("json").load(open(os.path.join(HERE, "rows64.json"),
                                    encoding="utf-8"))
rows = {r["line"]: r for r in data["rows"]}
for ln in SAMPLES:
    r = rows[ln]
    hdr_ln, hdr = entry_of(ln)
    print("=" * 78)
    print("L%d  need=%s  outcome=%s" % (ln, r["need"], r["outcome"]))
    print("reason_wide: %s" % r["reason_wide"][:160])
    print("entry header (L%d): %s" % (hdr_ln, hdr[:100]))
    span = lines[ln - 1:r["end_line"]]
    print("-- span (%d lines):" % len(span))
    for s in span[:4]:
        print("   |" + s[:150])
    print("-- block lines %s:" % (r["block"] or "(none)"))
    for n in r["block"][:6]:
        print("   |" + lines[n - 1][:150])
    # entry-head tokens: only path-shaped ones, first 12 lines of the entry
    toks = set()
    for k in range(hdr_ln - 1, min(hdr_ln - 1 + 14, ln - 1)):
        for m in TOK.finditer(lines[k]):
            t = m.group(0).strip('`')
            if re.search(r'[\\/]|^TASK-\d+', t) and len(t) < 100:
                toks.add(t)
    print("-- entry-head path tokens: %s" % ("; ".join(sorted(toks))[:400]
                                             or "(none)"))
