# M3b/M5/L186 pre-flight: trailingcontent.py disk flavour + occurrence
# counts for EOL-aware searches. Read-only.
import hashlib
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TC = os.path.join(ROOT, "src", "trailingcontent.py")
raw = open(TC, "rb").read()
print("trailingcontent.py: %d bytes, sha256 %s, CRLF=%d, bare-LF=%d"
      % (len(raw), hashlib.sha256(raw).hexdigest()[:16],
         raw.count(b"\r\n"), raw.count(b"\n") - raw.count(b"\r\n")))
eol = b"\r\n" if raw.count(b"\r\n") else b"\n"
print("detected eol:", eol)

m3b_s = b'        result = f"{result}\\n\\n{sig}"'
m5_s = eol.join([b'    result = (body or "").rstrip()',
                 b'    result = append_cta(result, cta_link)',
                 b''])
l186_s = eol.join([b'    if sig and result:',
                   b'        result = f"{result}\\n\\n{sig}"',
                   b'    elif sig:',
                   b'        result = sig',
                   b''])
for tag, s in (("m3b(single-line, no terminator)", m3b_s),
               ("m5(two-line, eol-joined)", m5_s),
               ("l186(four-line, eol-joined)", l186_s)):
    print("%s: count=%d" % (tag, raw.count(s)))
