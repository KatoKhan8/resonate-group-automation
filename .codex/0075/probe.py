# TASK-0075 load probe. Run in a FRESH interpreter from the tree root:
#   py -3 .codex\0075\probe.py <tag>
# Imports src.spendledger the same way the test runner does, drives the exact
# guard (check() with priced=False under a finite budget), and reports whether
# the IMPORTED module raises UnpricedCall - the module-object read. Alongside
# it prints what is on DISK (guard line bytes + sha256) and the .pyc header, so
# one output block shows imported behaviour vs disk bytes vs cache header.
import hashlib
import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, "src", "spendledger.py")
PYC = os.path.join(ROOT, "src", "__pycache__", "spendledger.cpython-314.pyc")
TAG = sys.argv[1] if len(sys.argv) > 1 else "probe"

sys.path.insert(0, ROOT)
from src import spendledger  # noqa: E402  (import AFTER path setup, on purpose)

config = {"budget": {"total": 10_000_000}}
try:
    ok = spendledger.check(
        "task0075-probe", config, 0,
        rows=[], run_id="task0075-probe", day="2026-10-16",
        call="task0075-load-probe", priced=False)
    verdict = "NOT-RAISED (check returned %r)" % (ok,)
except spendledger.UnpricedCall as exc:
    verdict = "RAISED UnpricedCall: %s" % (str(exc).splitlines()[0][:90],)

disk = open(SRC, "rb").read()
guard_line = next(l for l in disk.split(b"\n") if b"priced and governed" in l)
with open(PYC, "rb") as fh:
    magic, flags, hmtime, hsize = struct.unpack("<IIII", fh.read(16))

print("[%s] imported-module-object read: %s" % (TAG, verdict))
print("[%s] disk guard line : %r" % (TAG, guard_line))
print("[%s] disk sha256     : %s" % (TAG, hashlib.sha256(disk).hexdigest()))
print("[%s] disk size       : %d" % (TAG, len(disk)))
st = os.stat(SRC)
print("[%s] disk mtime_ns   : %d (whole second %d)"
      % (TAG, st.st_mtime_ns, int(st.st_mtime)))
print("[%s] pyc header      : flags=%d mtime=%d size=%d  -> stale-bytes reused: %s"
      % (TAG, flags, hmtime, hsize,
         int(st.st_mtime) == hmtime and st.st_size == hsize))
