# TASK-0110 B7 pre-flight probe: fixture byte shape, config sender block
# (KEYS AND LINE NUMBERS ONLY - no config value is ever printed), and the
# clients.load env dependency check. Read-only.
import hashlib
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

FIX = os.path.join(ROOT, "tests", "fixtures", "sender-estate-2026-09-21.json")
raw = open(FIX, "rb").read()
print("fixture: %d bytes, sha256 %s" % (len(raw), hashlib.sha256(raw).hexdigest()[:16]))
print("fixture CRLF count:", raw.count(b"\r\n"))
doc = json.loads(raw.decode("utf-8"))
print("top-level keys:", sorted(doc.keys()))
rows = doc["rows"]
print("rows:", len(rows), "row0 keys:", list(rows[0].keys()))
i = raw.find(b'"rows"')
print("first 240 bytes at rows:", raw[i:i + 240].decode("utf-8"))
for px in ("px-75ee916b9999", "px-2f1dd920a186", "px-387dd1f77205"):
    print("%s occurrences: %d" % (px, raw.count(px.encode())))
print('"owner_px" fields:', raw.count(b'"owner_px"'), '"name_px" fields:', raw.count(b'"name_px"'))
print('serialized owner field shapes:',
      raw.count(b'"owner_px": "px-75ee916b9999"'),
      raw.count(b'"owner_px":"px-75ee916b9999"'))
for rid in (2910, 3425, 3426, 3430, 3435, 2742, 2782):
    row = next(r for r in rows if r["id"] == rid)
    print("row %d: name_px=%s owner_px=%s owner_present=%s" %
          (rid, row.get("name_px"), row.get("owner_px"), row.get("owner_present")))
print("pool ids (owner px-75ee916b9999):", [r["id"] for r in rows if r["owner_px"] == "px-75ee916b9999"])

CFG = os.path.join(ROOT, "config", "clients", "productive.yaml")
craw = open(CFG, "rb").read()
print("config: %d bytes, CRLF count %d, sha256 %s" %
      (len(craw), craw.count(b"\r\n"), hashlib.sha256(craw).hexdigest()[:16]))
for m in re.finditer(rb"(?m)^([ \t]*)(sender|name|mode|email|signature|title)[ \t]*:", craw):
    lineno = craw[:m.start()].count(b"\n") + 1
    print("config line %d: %s%s:" % (lineno, m.group(1).decode(), m.group(2).decode()))

src = open(os.path.join(ROOT, "src", "clients.py"), encoding="utf-8").read()
hits = [l.strip()[:110] for l in src.splitlines()
        if "environ" in l or ".env" in l or "def load" in l or "def sender_identity" in l]
print("clients.py load/env lines:")
for h in hits:
    print("  |", h)
