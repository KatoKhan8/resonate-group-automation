# Fresh-process leg of the TASK-0078 load-proof.  The import MUST happen in
# a process started after whatever the driver last did to disk, so the
# module object reflects the import system's decision right now.  This file
# itself never writes anything.
#
#   py -3 .codex\0078\proof_runner.py <label>     (cwd = worktree root)
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import load_proof            # noqa: E402  (path set above)
import src.spendledger as m  # noqa: E402  (the import under test)

result = load_proof.load_proof(m)
result["label"] = sys.argv[1] if len(sys.argv) > 1 else ""
result["python"] = sys.version.split()[0]
print(json.dumps(result, indent=1))
