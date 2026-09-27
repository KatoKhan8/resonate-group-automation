# Standing backlog template — for `scripts/refill_queue.py`

Read by the watchdog automatically when the ready queue drops below the
12-task floor (`docs/OPERATING-MODE.md` WORKER POLICY). Each entry below is
one reusable, always-legitimate-to-run kind of task — a fresh, state-of-the-
world check, not a one-off. The refill script cycles through these in
order, writing a new numbered task file from whichever template is next,
and never writes the same template twice in the same pass around the list.

Format per entry: a title line, then the body verbatim (a real task file
body — priority, acceptance checks, what it may not do). The script
substitutes only the task number.

---
### TEMPLATE: docs-hygiene-pass
PRIORITY: P3
SIZE: S
Docs hygiene: find what's now false in the standing docs (CLAUDE.md,
OPERATING-MODE.md, the most recent PRODUCTION-HANDOFF). For each specific,
checkable claim (a count, a SHA, a "the only X is Y" statement, a task's
stated status), verify against current master or a read-only provider
check. Report every claim found FALSE with the correction and its evidence.
Report only — Claude applies corrections, this task does not edit the
scoped files. Acceptance: a list of every checked claim, PASS or FALSE,
with evidence; do not touch the files yourself.
---
### TEMPLATE: suppression-list-audit
PRIORITY: P0
SIZE: M
Suppression list audit: name every store of a suppression fact today (DNC,
incident-suppressed recipients, channels.email_verdict, unsubscribes,
bounces) and whether it is one canonical list or several that could
disagree. Confirm every prospect-facing write path checks suppression
BEFORE writing, with file:line. Re-verify the 09-23 incident's 76
suppressed recipients are still suppressed by a fresh read, not memory.
READ-ONLY toward providers. Acceptance: one canonical source named or the
honest report that several exist; every write path confirmed pre-write;
the 76 reconfirmed by a fresh read.
---
### TEMPLATE: heyreach-seat-cap-check
PRIORITY: P1
SIZE: S
Is any HeyReach seat over its own daily/weekly connection cap? Read every
attested seat's configured cap against actual sends this period via a REAL
read-only provider read. Report any seat at or over 90% as a finding.
READ-ONLY. No campaign, seat or cap modification. Acceptance: a real
per-seat table (cap, actual, %); anything over 90% named explicitly.
---
### TEMPLATE: spend-report-wiring-check
PRIORITY: P1
SIZE: M
Does the spend report read what the ledger's client-attribution work now
writes? Trace every consumer of spendledger that reports a number to a
human; confirm each groups by the now-real client ids correctly, not still
folding everything into "unattributed". Acceptance: run the report against
a fixture with mixed client-attributed and unattributed rows; confirm the
client total is correct, not folded in.
---
### TEMPLATE: sender-inventory-drift-check
PRIORITY: P1
SIZE: S
Compare the attested sender/mailbox inventory (EmailBison sender_emails,
HeyReach seat roster) against whatever this repo's own internal record of
"our senders" claims, via a real read-only provider read. Report any
mailbox/seat present at the provider but not in our internal record, and
vice versa. READ-ONLY. Acceptance: a real diff, both directions, named by
id, not a count.
---
### TEMPLATE: research-store-freshness-check
PRIORITY: P2
SIZE: S
For a sample of records with `rec["research"]` populated, check how old the
research is (site-crawl timestamp if one exists) against when the record
was last touched. Report the honest distribution — is stale research
silently informing current copy? Acceptance: a real sample (20+ records),
ages reported, not estimated.
---
### TEMPLATE: campaign-cadence-drift-check
PRIORITY: P2
SIZE: M
For every ACTIVE campaign per the latest `docs/state/PROVIDER-CAMPAIGNS.json`,
confirm its actual send cadence (real provider timestamps between sends)
matches the canonical cadence library's declared days, not an assumption.
READ-ONLY. Acceptance: real per-campaign timing measured against the
canonical cadence, named drift if any.
---
### TEMPLATE: offer-config-consistency-check
PRIORITY: P1
SIZE: S
Read `config/clients/productive-offers.yaml` end to end and check for
internal contradictions the way TASK-382's GLM review found one (a "THE
ONLY allowed link" comment coexisting with a different link elsewhere in
the same file). Report every such contradiction found, file:line, quoting
both sides. Acceptance: a clean pass reports "none found" honestly; any
contradiction found is quoted exactly, both sides.
---
### TEMPLATE: notify-delivery-verification
PRIORITY: P1
SIZE: S
Trace whether a `src/notify.py` GLOBAL-destination notification (e.g.
`failed_job_needs_attention`, the kind `pool.sh`'s CRITICAL alert now
writes) is ever actually delivered to Slack by a live consumer, or whether
it only ever reaches the stored notification queue. Name the consumer if
one exists, with file:line, or report plainly that none was found running.
Acceptance: either a real delivered test notification traced end to end to
Slack, or an honest "no consumer found" with the queue location named.
---
