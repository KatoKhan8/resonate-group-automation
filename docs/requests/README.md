# Change requests raised from Slack

One file per request, `<date>-<id>.md`, written by the Slack agent and
executed — if the operator approves it — by Claude Code through the existing
gates.

**Nothing here is written yet.** Ticket creation is Phase B. This directory
and this note exist now because they are part of the safety contract
described in `docs/SLACK-AGENT-PHASE-A.md`: the agent may write inside
`work/` and inside this directory, and nowhere else. Reserving the path with
its rules written down is how the rules get read before the first ticket is
written rather than after.

## What a ticket is, and what it is not

A ticket is a **record of a request**. It is not an instruction, it is not a
queue an executor drains, and creating one changes nothing about any
campaign, lead, provider or policy. The agent has no path to a write; that
is asserted by `tests/test_slack_agent_cannot_act.py` and it does not become
untrue because a file appeared in this folder.

## The shape

    # <id> — <one line saying what is being asked for>

    requester   Slack user id, and their resolved scope
    channel     channel id, and what it is bound to
    workspace   the client workspace, or `internal`
    raised_at   UTC
    status      awaiting_operator | approved | rejected | executed | failed

    ## The exact change

    Which lead, which campaign, which step, the proposed new text — in full,
    confirmed with the requester in thread BEFORE the ticket was written.

    ## What executing it would do

    The concrete operations, named. "Suppress the contact and stop the lead
    on both channels" — not "remove the lead".

    ## Decision

    Who decided, when, and what they said.

## The rules that outrank convenience

- **The exact intent is confirmed in the thread first.** Which lead, which
  campaign, which step, the proposed new text. A ticket built from a guess
  is a worse artefact than no ticket, because it looks like a record.
- **Only the operator approves**, by replying `approve <id>` from the Slack
  user id in policy. Nobody else's `approve <id>` is an approval, including
  in a client channel where somebody may reasonably believe it is theirs to
  authorise.
- **A lead removal is executed as suppression plus a stop on both channels**,
  after approval, through the existing guards. Never a direct provider write
  from the agent, and never a delete: this repository does not delete a queue
  record, it drops it with a reason.
- **Copy changes are drafted for review and never applied.** Changing
  approved live copy stays operator-gated, and an approval is fingerprinted —
  changing the words makes the existing approval stale rather than silently
  covering the new version.
- **Rejection is reported back in the original thread**, in the same words
  the operator used where they gave any. A request that quietly disappears
  teaches the requester to ask somebody else.
- **A ticket is never edited to change what was asked for.** Its status
  changes; its request does not. If the ask changed, that is a new ticket.
