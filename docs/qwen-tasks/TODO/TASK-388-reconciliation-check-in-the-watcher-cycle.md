PRIORITY: P2
SIZE: M
DEPENDS: TASK-387

# TASK-388 — does the watcher's own cycle ever check itself against provider truth?

**Operator instruction, 2026-09-26/27 overnight standing order.**
`scripts/bison_watch_loop.py` reads campaign state every cycle
(`snapshot()`) and reacts to it (milestones, halts on blank content). Trace
whether the watcher ever RECONCILES what it believes (its own last-known
state, or what TASK-387's write-back records) against a fresh provider
read, and reports a mismatch — or whether it only ever reads forward, so a
drift between "what we think happened" and "what the provider says
happened" would go unnoticed indefinitely.

## Trace first

1. Read `scripts/bison_watch_loop.py`'s `main()` loop end to end. Does any
   cycle compare its OWN prior belief (the last snapshot it wrote, or a
   record's event log if TASK-387 has landed) against a fresh read, or does
   every cycle just overwrite the previous heartbeat file with no diff?
2. `docs/state/PROVIDER-CAMPAIGNS.json`'s `internal_vs_provider` block
   already does exactly this comparison at the CAMPAIGN level (claimed ids
   vs provider-confirmed ids) — is anything analogous run inside the
   watcher's own per-cycle loop, or only in the separate, manually-invoked
   `scripts/provider_truth.py`?
3. Name the honest answer: does a reconciliation check exist in the watch
   loop today, partially, or not at all.

## Build only if the trace shows a real gap

If nothing reconciles automatically, add ONE cheap check per cycle: compare
the watcher's own last-known counters (`emails_sent`, `replied`, `bounced`)
against what the SAME provider read returns this cycle, and if a number the
watcher's own logic assumed monotonic (sent count going backward, say) ever
moves the wrong direction, log it loudly — this is exactly the shape of bug
`docs/THE-MAILBOX-WAS-NEVER-THE-PROBLEM-2026-09-17.md`'s correction section
already warns about (an inference dressed as a measurement).

## Acceptance

1. Name whether a reconciliation check exists today, with file:line, or
   report its absence plainly.
2. If you build one: force a synthetic backward-moving counter in a test
   fixture and confirm the check fires; confirm it does NOT fire on a
   normal forward-moving read.
3. Full suite: wait for `work/suite_verdict.txt`, diff the failing-name SET.

## What this task may NOT do

- READ-ONLY toward providers throughout — this instruments the watcher's
  own read, it does not add a new provider call.
- Do not silence or auto-correct a detected drift - report it loudly, the
  same way `bison_watch_loop.py` already halts on blank content rather than
  fixing it silently.
- Nothing sent, nothing activated.
