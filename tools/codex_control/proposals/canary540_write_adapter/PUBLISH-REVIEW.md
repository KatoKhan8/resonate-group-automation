# Canary journal review publication

This branch publishes one reviewed local storage component and its exact pinned dependencies. It is based directly on the existing remote master commit; the development-control branch's separate local history and private/runtime artifacts are not included.

Run from repository root with Python3.14:

    python -B tools/codex_control/proposals/canary540_write_adapter/prove_persistent_owner.py --portable

Eight portable targeted methods use only owned synthetic files and isolated local child processes. They cover restart, same-ordinal concurrency, grant/material/root replacement, expiry and sticky pending state. The ninth source-bound guarded-caller integration method was verified locally in the development worktree and is explicitly excluded by --portable: it requires that separate pinned installed native tree and is not portable CI evidence. Default local nine-test behavior is retained.

Exact source bytes are preserved by narrowly scoped .gitattributes because dependency hashes include original line endings. Publish manifest records those six reviewed files. No provider module, runtime state, real grant, credential or production payload is included.

This is a review proposal, not native installation, authenticated grant issuance or launch permission. Current canary remains NO_GO. Provider authenticity/freshness, current approval, protected coverage and conditional native operation support remain open. Read PERSISTENT-OWNER-REVIEW.md for trusted-local-writer/TOCTOU/sticky-lock limitations.

The frozen adapter dependency contains 131 original CRCRLF line endings. Its exact ee95... bytes are retained for dependency verification, not reformatted. Whitespace lint is explicitly exempted only for that pinned dependency; the new owner/test sources remain checked.
