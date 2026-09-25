#!/usr/bin/env python3
"""LANE P bootstrap: this worktree has no config/.env and no work/ of its own.

Credentials are loaded from the PRODUCTION checkout's config/.env by path -
no value is ever written here. Outputs go to this worktree's own (gitignored)
work/laneP/.
"""
import os
import sys

WORKTREE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

# A WORKTREE HAS ITS OWN EMPTY `work/` AND NO `config/.env`.
# A cohort built from an empty store is the classic worktree false pass: it
# reports zero candidates and reads as a clean estate. So the store and the
# credentials come from the PRODUCTION checkout by path. Neither is written,
# and no credential VALUE is ever recorded here.
#
#   RESONATE_PROD_ROOT  the production checkout (default: this checkout)
#   LANEP_OUT           where this lane writes (default: <root>/work/laneP)
PROD = os.path.abspath(os.environ.get("RESONATE_PROD_ROOT") or WORKTREE)
ENV = os.path.join(PROD, "config", ".env")
OUT = os.path.abspath(os.environ.get("LANEP_OUT")
                      or os.path.join(WORKTREE, "work", "laneP"))

sys.path.insert(0, WORKTREE)

from src import providers  # noqa: E402

providers.load_env(ENV)
os.makedirs(OUT, exist_ok=True)

# Every LANE P probe counts its own provider requests and refuses to write.
CALLS = {"n": 0, "by": {}}


def readonly(module, label):
    """Wrap a provider module's `request` so a write is impossible."""
    original = module.request

    def counted(method, url, headers=None, body=None, **kw):
        if str(method).upper() != "GET":
            raise SystemExit(
                f"LANE P is reads-only: refusing {method} on {label}")
        CALLS["n"] += 1
        CALLS["by"][label] = CALLS["by"].get(label, 0) + 1
        return original(method, url, headers, body, **kw)

    module.request = counted
    return counted
