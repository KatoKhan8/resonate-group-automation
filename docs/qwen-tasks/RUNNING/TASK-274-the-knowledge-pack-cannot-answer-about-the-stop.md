# TASK-274 — the knowledge pack cannot answer about the cross-channel stop

SIZE: M
Operator instruction, 2026-09-23 night. Found by the agent itself, live, and
it is a finding rather than a fault.

## WHAT HAPPENED, MEASURED

Asked in `#resonate-os` at 20:47Z: *"explain in three sentences how the
cross-channel stop works"*.

    ANSWERED C0C3C6MDN9L:1790189207.896399 scope=internal via=model
      tools=['cadence_detail', 'decisions_log', 'workspace_summary']

`via=model`, not a refusal. **And the answer was right about its own limits**:
it said the knowledge pack carries no named "cross-channel stop", separated
what it could evidence from what it was inferring — *"I'm reasoning, not
reporting"* — named what would settle it, and offered a ticket.

It is correct. The stop lives in `src/inbound.py` and `src/leadstop.py`. The
pack indexes the cadence library, the decisions log and the workspace summary,
and **none of them describe a mechanism**. The agent reached for the three
tools it had and none of them could answer.

## THE DEFECT IS THE PACK, NOT THE ANSWER

Do not "fix" this by teaching the agent to bluff. The behaviour under test is
already right: an agent that says *I am reasoning, not reporting* when the
pack is silent is the behaviour to preserve. What is missing is the material.

So there are two deliverables and the second is the load-bearing one.

## WHAT TO BUILD

**1. A mechanism section in the knowledge pack.** The cross-channel stop, from
the sources rather than from this file: reply ingested → classified →
`inbound.summarise_stops` → `leadstop` per channel → provider stop confirmed,
with the refusal cases named (no lead, already stopped, REFUSED-with-reason).
Every claim traceable to a line in `src/inbound.py` or `src/leadstop.py`.
Cite `file:line`. **Do not paraphrase this task file — read the code.**

**2. A scope test per gap: the pack must be able to FAIL.** Today nothing
asserts the pack can answer a question it claims to cover. Add a test that,
for each catalogue entry, asserts the pack contains the material to answer it,
and fails when it does not. That test failing is how the next gap is found
before a human asks.

**3. The next ten catalogue gaps.** `docs/SLACK-AGENT-QUESTION-CATALOGUE.md`
holds the question catalogue. Walk it against the pack's actual contents and
report the ten highest-value questions the pack cannot answer, each with the
source that would answer it. **Rank by how likely the operator is to ask it**,
not by how easy it is to add. Write them up under FINDINGS; do not build all
ten.

## BOUNDARY

You may not edit `src/providers/*`, `scripts/*_watch_loop.py`, `config/.env`
or anything under `work/`. The agent's runtime loop is production's. If the
pack's builder lives behind one of those, write the boundary into FINDINGS,
commit what you have, push, and stop.

Reads only against any provider. No sends.

## DONE WHEN

The pack answers the cross-channel-stop question from cited code, a scope test
fails on a pack with the section removed, and ten ranked gaps are written up.
