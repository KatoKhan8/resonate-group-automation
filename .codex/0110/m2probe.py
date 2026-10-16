# M2 diagnostic: why did the accent not reach the parsed sender.name?
# Prints ONLY structural facts - never the value.
import hashlib
import os
import re
import sys
import unicodedata

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CFG = os.path.join(ROOT, "config", "clients", "productive.yaml")
raw = open(CFG, "rb").read()
print("config sha256 still:", hashlib.sha256(raw).hexdigest()[:16], "(expect 4ec1e1696efbcdfe)")

ms = re.search(rb"(?m)^sender:[^\n]*\n", raw)
mn = re.search(rb"(?m)^[A-Za-z_][A-Za-z0-9_]*:[^\n]*\n", raw[ms.end():])
block = raw[ms.end():ms.end() + (mn.start() if mn else len(raw))]
cands = list(re.finditer(rb"(?m)^([ \t]+)name:[ \t]*[^\n]*\n", block))
print("sender block spans chars %d..%d; indented name: lines in block: %d"
      % (ms.start(), ms.end() + (mn.start() if mn else 0), len(cands)))
for c in cands:
    lb = c.group(0)
    lineno = raw[:c.start()].count(b"\n") + 1
    core = lb.rstrip(b"\r\n")
    m = re.match(rb"^([ \t]+name:[ \t]*)([^\r\n]*?)([ \t]#[^\r\n]*)?$", core)
    pre, val, com = m.group(1), m.group(2), m.group(3)
    print("line %d: indent=%d value_bytes=%d quoted=%s trailing_comment=%s crlf=%s"
          % (lineno, len(pre) - len(pre.lstrip(b" ")), len(val),
             val[:1] in (b'"', b"'") and val[-1:] == val[:1] and len(val) >= 2,
             com is not None, lb.endswith(b"\r\n")))

import yaml
cfg = yaml.safe_load(raw.decode("utf-8"))
sender = cfg.get("sender")
print("sender keys:", sorted(sender.keys()) if isinstance(sender, dict) else type(sender).__name__)
name = (sender or {}).get("name") or ""
SALT = "resonate-pii-salt-2026-09-16"


def px_of(n):
    return "px-" + hashlib.sha256(
        (SALT + unicodedata.normalize("NFC", n or "")).encode()).hexdigest()[:12]


print("px_of(original name) == CONFIG_PX_TODAY:", px_of(name) == "px-fc7d1255b8a3",
      "(local model:", px_of(name)[:6] + "...)")
