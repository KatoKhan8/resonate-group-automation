# Slack agent — handoff, 2026-09-22 PM

**Merged to master** (production session took increments 1 and 2): Phases A
and B; channel binding with `#productive-resonate-outbound` live; client
mode; change-request tickets with the operator gate; `sending_domains`,
`sender_roster`, `slacklanguage`, the relay trigger; the question catalogue
and expectations docs. Master is `7ccc2cfc`.

**On the branch, not merged:** `slack-agent` @ `5ad2f7f7` — one commit, the
six client-channel fixes from the first live answer. New:
`src/slackclientview.py` (provider-confirmed enrolled, times in the
workspace's own zone, campaign names without our experiment design) and
`src/slackfollowup.py` (the one offer the agent can keep). Merge request:
`docs/MERGE-REQUEST-SLACK-AGENT-PHASE-C1.md`. It touches `src/store.py` and
`tests/test_invariants.py` — additive, to put the new writer behind the
production-write barrier.

**Open for the operator:** seat ownership (which HeyReach seats are
Resonate's — until decided, client channels give counts without names);
`hr-`/`li-` reconciliation (working via the bare-id join); a plaintext
password sitting in Slack history; and `slack_history.py --loop`, handed
over and not running.

**Two facts that contradict the handoffs:** batch 1 shows `emails_sent 0`
on all eight campaigns, and holds **393 leads, not 151** — two independent
provider witnesses agree.

**Next three:** merge `5ad2f7f7`; build `meetings_booked`, the most-asked
number nothing can produce; wire the promise scan — 53 commitments in ten
days and nothing tracks whether any was kept.
