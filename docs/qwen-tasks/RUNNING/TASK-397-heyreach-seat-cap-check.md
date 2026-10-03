PRIORITY: P1
SIZE: S
DEPENDS:

# TASK-397 — is any HeyReach seat over its own daily/weekly connection cap?

Per the earlier finding pattern (`heyreachfactory` roster reporting
`daily_limit` incorrectly in one direction already found and fixed once):
read every attested HeyReach seat's configured cap (`connectioRequestMax` or
whatever field is authoritative today) against what the seat has actually
sent this period, using a REAL provider read (read-only, no write), and
report any seat over or near its cap.

## Trace first

1. Name the authoritative cap field and where it is read today
   (`heyreachfactory.py`, `providers/heyreach.py`).
2. Name the authoritative "sent this period" counter — provider-reported,
   not inferred from our own queue.
3. Cross-reference all attested seats; report each seat's cap vs actual,
   flagging any at or over 90% as a finding, not silently.

## Acceptance

1. Real provider read (read-only), full per-seat table: cap, actual, %.
2. Any seat over 90%: named explicitly as a finding.
3. Full suite: wait for `work/suite_verdict.txt`, diff the failing-name SET.

## What this task may NOT do

- READ-ONLY. No campaign, seat or cap modification.
- Nothing sent, nothing activated.
