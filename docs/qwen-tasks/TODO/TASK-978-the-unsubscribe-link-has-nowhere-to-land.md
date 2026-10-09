SIZE: S
DEPENDS: none (narrower than and independent of TASK-271)

# TASK-978 — the unsubscribe link has nowhere to land

Written from the 2026-10-09 OSS survey (`docs/OSS-SURVEY-2026-10-09.md`,
§1). Listmonk (an unrelated, AGPL-3.0 project — nothing from it is copied)
has a working unsubscribe landing endpoint; this repo does not, and that
gap is real independent of Listmonk.

## The gap, traced

`executionguard.py:590-615` already refuses to authorize an email step
unless the body carries an unsubscribe link (`_has_unsubscribe_affordance`,
`executionguard.py:1163`) or a named provider setting
(`_named_unsubscribe_setting`, `:1175`). That only checks that outbound
copy *claims* an opt-out path exists. Confirm, before writing anything,
that nothing currently makes the claim true:

    grep -rn "/unsubscribe" src/            # zero hits as of this writing
    grep -rn "unsubscribe" src/web/*.py     # only display labels (pages.py)
                                             # and a read of an already-set
                                             # upload-file flag (api.py:5501)

If either grep now returns something that looks like a receiving route,
STOP and report it in FINDINGS rather than build a second one.

`src/agencydnc.py:134`, `add(kind, value, reason=REQUESTED, at=None,
file_path=None)`, is the existing, already-correct write primitive for a
suppression fact — sha256 fingerprints, closed reasons. This task does not
touch that function's contract, only calls it.

`docs/qwen-tasks/TODO/TASK-271-...md` writes the compliance document and
the outbound gate. It explicitly scopes out the receiving side ("does not
implement... the consent store"). This task does not depend on or block
TASK-271; it may land before, after, or independent of it.

## What to build

1. Find the real HTTP entrypoint this repo already uses to serve
   `src/web/pages.py` content (do not assume Flask, Django, or any
   particular framework — trace it, per CLAUDE.md's "find the real
   execution path"). Add one route, `/unsubscribe`, that:
   - accepts a signed token identifying `(client slug, contact key)` —
     reuse whatever signing primitive the codebase already has for a
     similar purpose if one exists; do not invent a new secret-handling
     scheme without finding one first.
   - on a valid token, calls `agencydnc.add("email", <value>,
     reason=agencydnc.REQUESTED, at=<now>)` exactly once (idempotent on
     repeat clicks — a second click must not double-write or error).
   - on an invalid or expired token, does **not** suppress anything and
     renders a generic "this link is no longer valid" page — never leak
     whether a token was well-formed but expired vs. garbage.
   - never reads or writes `work/*.jsonl` directly — go through
     `src/agencydnc.py` and `src/store.py` only, same as every other
     write path in this repo.
2. The token generator — whatever produces the per-send unsubscribe URL —
   is a separate, small function callable from wherever campaign copy is
   assembled. This task adds the function; it does NOT wire it into
   `providers/bison.py` or any live copy-generation path. That wiring is
   out of scope and belongs to whoever closes TASK-271's gate, once the
   document decides what the link's URL shape should be.
3. No new dependency. No code copied from Listmonk or any other surveyed
   project — the landing-endpoint *idea* is the only thing borrowed.

## ACCEPTANCE

Full offline suite (`scripts/run_suite.py`, under the suite lock, with
`-v`), zero new failures and zero new errors against the current master
baseline, diffed by test NAME both directions (new failing names absent
from the baseline, and no baseline-failing name silently disappearing
without being found passing in the log).

Required new tests:
- a valid token suppresses exactly once and is idempotent on a second
  click (no duplicate `agencydnc` entry, no error);
- an invalid token suppresses nothing;
- an expired token suppresses nothing and its error page does not reveal
  that the token was otherwise well-formed;
- the route never imports or touches `work/*.jsonl` directly (assert on
  the import graph / call graph, not on source text — see CLAUDE.md,
  "test behaviour, not the text of the source").

## FILES FORBIDDEN

    src/clientapproval.py    src/providers/*    config/    work/*.jsonl
