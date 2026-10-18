# TASK-938 — COMPLIANCE.md must name the one-click-unsubscribe gap

SIZE: S

From the 2026-10-02 OSS survey (`docs/OSS-SURVEY-2026-10-02.md`, item 3).
Documentation only. No code change, no dependency, no provider call.

## WHAT IS TRUE TODAY, CHECKED AGAINST THE SHIPPED CODE NOT THE OLD TASK FILE

TASK-271 asked for a compliance document and a fail-loud gate for unsubscribe
presence. Both exist now: `COMPLIANCE.md` at repo root, and
`src/executionguard.py:589-608` (`_has_unsubscribe_affordance` at `:1163`,
`_named_unsubscribe_setting` at `:1175`). The gate is correctly built against
the rule it claims to enforce: a link or merge-field token matching
`unsubscribe|opt-out|manage preferences|...` in the rendered email body
(`_UNSUBSCRIBE_URL`, `:1154-1159`), or a named provider-level setting.

**That is a real affordance and a different thing from a `List-Unsubscribe`
header.** Since 2024, Gmail and Yahoo require senders above their bulk
thresholds to support one-click unsubscribe per RFC 8058 — a `List-Unsubscribe`
header **and** a `List-Unsubscribe-Post` header, both inside the DKIM
signature. A link in the email body satisfies neither header requirement,
however prominent it is. `executionguard.py:1241`'s own refusal message
already says as much in its wording ("no `List-Unsubscribe` header and no
generated body carries...") but `COMPLIANCE.md` itself does not currently say
this anywhere (confirmed: zero hits for "one-click", "RFC 8058",
"List-Unsubscribe-Post", "Gmail", or "Yahoo" in the file today).

**And it is not reachable from here regardless.** `src/providers/bison.py`'s
sequence-step payload (`:1598-1606`) is `{id, order, email_subject,
email_body, wait_in_days, active, variant, variant_from_step,
thread_reply}` — no `headers` field, so there is no way to set a real mail
header through this provider's sequence-step API even if the gate required
it. Separately, `executionguard.py:1214-1219` records EmailBison's own
native `can_unsubscribe` switch reads back `False` on 22 of 22 campaigns
with `unsubscribe_text` null.

## WHAT TO WRITE

Add a short, explicitly-labeled section to `COMPLIANCE.md` — "What this
system does not do" or similar, next to wherever it already separates
system-enforced from operator-obligated — stating plainly:

1. The unsubscribe-affordance gate satisfies this repository's own defined
   rule (a link or named setting), not Gmail/Yahoo's RFC 8058 one-click
   requirement (real `List-Unsubscribe` + `List-Unsubscribe-Post` headers).
2. This is not a gap this codebase can currently close: the provider's
   sequence-step API has no header field to write one through, cited at
   `bison.py:1598-1606`.
3. Closing it would require either a provider capability that does not
   exist today, or sending through a different channel than the sequence-step
   API — both are product decisions for the operator, not something this
   task proposes.

Do not soften this into "may not fully satisfy" or similar hedge language —
the house rule on a compliance document is that it is dangerous exactly in
proportion to how confidently it understates a gap. State the gap as what it
is.

## WHAT THIS MUST NOT DO

- Must not touch `src/executionguard.py`, `src/providers/*`, or any gate
  logic. The gate is correctly built against its own stated rule; this task
  is about `COMPLIANCE.md` saying what that rule is and is not.
- Must not imply a fix is in progress or scheduled. None is.

## ACCEPTANCE

Full offline suite, zero new failures and zero new errors against the
`master` baseline, diffed by test NAME both directions (this task should not
change suite behavior at all, since it edits only a `.md` file — the run is
to prove that, not to find anything).

## FILES FORBIDDEN

    src/clientapproval.py    src/providers/*    config/    work/*.jsonl
