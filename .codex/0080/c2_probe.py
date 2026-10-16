# TASK-0080 -- C2 probe.  Runs in a FRESH process with the throwaway
# worktree's tree root first on sys.path, so pyc reuse is CPython's own
# decision, not simulated.  Two reads per run:
#   load_proof   0078's instrument: does the imported module object's pyc
#                body equal a fresh compile of the disk bytes?
#   probe_raised 0075's behavioural read of src.spendledger.check(): an
#                unpriced governed call raises UnpricedCall on the
#                original guard and proceeds silently on the mutant
#                (`0 * priced` is always 0).
# argv: tree_root tools_dir label; prints one JSON line.
import json
import sys

tree, tools_dir, label = sys.argv[1], sys.argv[2], sys.argv[3]
sys.path.insert(0, tools_dir)   # 0078's load_proof, read-only
sys.path.insert(0, tree)        # the worktree's src package, FIRST

import src.spendledger as m    # noqa: E402
from load_proof import load_proof  # noqa: E402

proof = load_proof(m)
raised = None
try:
    m.check("task0080-c2-probe", {"budget": {"total": 10_000_000}}, 0,
            rows=[], run_id="task0080-c2-probe", day="2026-10-16",
            call="task0080-c2-load-probe", priced=False)
except Exception as exc:      # the refusal IS the datum, never an error
    raised = "%s: %s" % (type(exc).__name__, str(exc)[:70])
print(json.dumps({
    "label": label, "module": m.__file__,
    "load_proof": proof["verdict"], "clean_by": proof.get("clean_by"),
    "pyc_body_sha256": proof.get("pyc_body_sha256"),
    "probe_raised": raised}))
