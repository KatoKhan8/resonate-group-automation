# TASK-049 - Re-attempt TASK-043's wiring, from the branch it is on

## DO NOT START OVER

TASK-043 is COMPLETE as a function and is on `qwen-worker-3` at `48f62d1`.
`quality.campaign_repetition` exists, its own tests pass, and it is the right
idea. Work from that branch.

What failed was the WIRING into `heyreachfactory`: it broke three existing
tests in `tests/test_the_sequence_belongs_to_nobody.py` and was backed out
rather than debugged, under context pressure, at the end of a long session.

## GOAL

`quality.campaign_repetition` is consumed on the HeyReach path, and
`tests/test_the_sequence_belongs_to_nobody.py` is green.

## WHY THOSE THREE TESTS ARE THE POINT, NOT THE OBSTACLE

`CLAUDE.md`: "A failing test is a question about the system, not an
obstacle. Ask which it is - fixture, assumption, disconnected consumer,
wrong canonical model, stale state, wrong identity, wrong tenancy, swallowed
exception, or a real bug - and fix the smallest root cause."

That file's name tells you what it protects: a HeyReach sequence is
CAMPAIGN-level and may say nothing true of only one contact. On 2026-09-14
campaign 599020 was found holding "hi jacob, ... at &Partner?" for a
canonical row naming fourteen records - one person's words, campaign-wide.
The sequence now carries merge variables instead, and those three tests are
what keep it that way.

So before you change any of them, answer in writing: does the wiring break
them because the wiring is wrong, or because the tests encode an assumption
the new check invalidates? Both are possible. Only one of them is fixed by
editing the test, and if it is that one, say precisely which assumption
changed and why it is safe.

## THE CONTEXT THE CHECK NOW RUNS IN

Since TASK-043 was written, the campaign-level sequence stopped carrying
literal copy. `heyreachfactory._plan` builds a graph of `{connection_note}`,
`{connected_1}`..`{connected_4}`, `{message_2}`..`{message_4}` and each
lead's own approved words travel in `customUserFields`.

That matters to you directly: a duplicate-detection check pointed at the
GRAPH now compares eight merge-field placeholders and will find nothing,
every time, forever. That is the "evaluator reporting INSUFFICIENT_DATA
because nothing writes the field it reads" defect this repository keeps
finding, and it would look exactly like success.

The per-lead copy is what has to be compared. `_plan` returns `contacts` and
`pushable`, each carrying a `custom_fields` dict. Confirm for yourself where
the real words are before wiring anything, and say in FINDINGS which
structure you compared.

## A REAL DUPLICATE TO TEST AGAINST

`ogpartner-dk` / `jacob-faertz`, 2026-09-14, straight out of `_plan`:

    connected_1  "how do you currently ensure profitability is visible in
                  your projects?"
    message_2    "how do you currently ensure profitability is visible in
                  your projects?"

Byte-identical, two roles, one lead. `COPY_MAPPING` maps `li2` to both
`connected_1` and `message_2`, so the two branches reuse one generated step.
A check that does not catch this is not finished.

## WHAT YOU MAY NOT DO

- No live provider call. HeyReach 599020 holds zero leads and must keep
  holding zero until Claude says otherwise.
- Do not touch `work/queue.jsonl` or `work/campaigns.jsonl`.
- Do not weaken a sequence-tenancy test to make a wiring pass.

## RESULT BLOCK

End this file with STATUS, COMMIT SHA, TESTS, FILES CHANGED, FINDINGS,
RISKS, RECOMMENDED CLAUDE ACTION.
