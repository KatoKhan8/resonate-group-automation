PRIORITY: P0
SIZE: M
DEPENDS: TASK-560

# TASK-904 — every email carries an opt-out line, or it BLOCKS

**Canary requirement, operator, Zvonimir 2026-09-28.** Part of the one real
review artifact. **Serialised after TASK-560: it touches the same rendering
path. Do not start until 553 has landed.**

## The state

**Nothing generates or checks an opt-out line today.** Separately, the
provider's own footer is **unreadable**: `unsubscribe_text` is `None`, the
stored sequence bodies contain no unsubscribe string, and the footer is
injected at send time — so no API read shows it. Campaign 500 proved the flag
flips; **the text stayed UNKNOWN, and UNKNOWN is never a PASS.**

The operator's standing fallback (decision 10) is **our own explicit,
readable opt-out — never an unseen provider footer**. This task implements the
readable half for the slice.

## What to build

1. **Every rendered email carries an opt-out line**, present in the body a
   person receives AND in the EmailBison projection.
2. **Its absence BLOCKS.** A rendered email with no opt-out line is refused,
   naming the step. It must never silently ship without one.
3. **NO SECOND LINK.** The single-CTA rule stands: the only URL permitted
   anywhere in prospect-facing copy is `https://productive.io/get-started/`.
   So the opt-out is a **reply-based instruction, not a link** — implement it
   as plain text such as *"If this isn't relevant, reply STOP and I'll close
   the file."* **Treat the exact wording as provisional**: it is operator
   content and they will confirm or change it at artifact review. Put the
   string in ONE place so a wording change is one edit.
4. **It must not double up with a provider footer.** If the provider ever
   injects its own, the check must detect the duplicate and BLOCK rather than
   send two.

## Acceptance
1. All five emails of the Brand IQ slice carry the line, in the rendered body
   and in the projection.
2. **NEGATIVE CONTROL:** an email with the line removed is REFUSED, naming the
   step.
3. **NEGATIVE CONTROL:** a body already containing an opt-out line is refused
   as a duplicate, not silently double-signed.
4. **NEGATIVE CONTROL:** an opt-out implemented as a URL is refused by the
   single-link rule — prove the link rule still bites.
5. The line does not trip `copylint`, the figure gate, or the claim gates.
6. Mutation: disable the presence check; control 2 must go red for that reason.

## Files
The rendering path shared with TASK-560 (`src/bisonfactory.py`,
`src/render.py`, `src/sequenceplan.py`) plus the lint/gate module that enforces
presence, plus your own tests. **Do NOT touch `src/generate.py`** (TASK-901),
**`src/claims.py`** (TASK-902) or **`src/copystages.py`** (TASK-903).

## RULES THAT OUTRANK FINISHING

- **NEVER WIDEN A GATE TO MAKE A DRAFT PASS.** Fix what a gate CONSULTS, never
  what it PERMITS.
- **EVERY new check needs a NEGATIVE control and a NEAR-MISS control.** Two
  defects this week shipped with only positive controls.
- **MUTATION CHECK IS MANDATORY.** Break your fix, prove the intended test goes
  red for the intended reason, confirm no other guard fired first, restore and
  verify **byte-identical by sha256**. These files are **CRLF**: a
  `\n`-anchored regex matches zero times and your mutation silently no-ops.
- **Derive a suite verdict from a `Ran N tests` line in the output, NEVER from
  `$?`.** A killed run reported `exit=127` after writing 922 KB of real output.
  No `Ran` line = **absent** measurement, not a failure. Sweep `%TEMP%` for
  `rga-*` first: ~95k leftovers broke every run for an hour.
- **PROVIDER WRITES = 0.** `sending.live` false, freeze active, nothing sent.
- Production `work/` is READ-ONLY; verify `queue.jsonl` and `campaigns.jsonl`
  unchanged **by sha256 from a fresh process**, never by mtime.
- Write suite logs **outside** the repository — one inside the tree became part
  of `test_fixture_hygiene`'s corpus and nearly committed real prospect domains.
- Baseline `docs/state/SUITE-BASELINE-2026-09-26.txt`, compared **AS SETS**.
  Known stale on master (TASK-549).
- Commit and push to your own branch and **verify the remote with
  `git rev-parse` AFTER your last commit** — a stale verification is how a
  branch gets reported pushed while it is not. Do NOT merge. Do NOT post to
  Slack. Report **CLAIM / AUTHORITY / MEASURED AT / STATE** and your head SHA.
