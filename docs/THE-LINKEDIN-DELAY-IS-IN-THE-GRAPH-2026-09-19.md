# How long this graph spends before a connection request, measured

Read 2026-09-19T09:35Z on campaign 605732.

Yesterday's handoff left an open question and set a date for it: the falsifier
did not fire on the 18th because `lastActionTime` moved on all three leads, and
it said that **if the 19th showed movement again with connection still `None`,
the useful question becomes "how many VIEW_PROFILE days does this graph spend
before CONNECTION_REQUEST, and is that what was approved".**

That question did not need another day of waiting. It is a property of the
sequence, and the sequence is readable.

## First, the clock

    today               Saturday 2026-09-19
    campaign window     09:00-17:00 UTC Mon-Fri
    lastActionTime      all three leads, 2026-09-18 (10:33 / 13:56 / 14:02Z)

**Nothing moved today and nothing should have.** The falsifier as written -
`leadConnectionStatus: None` AND `lastActionTime` unmoved - is technically
satisfied this morning, and firing it would be wrong. A weekend is not a stall.
The test it was built for can only run on Monday.

## Per-lead provider truth, with the fields that would show a failure

    provider_lead_id  campaign     connection  message  error_code  last action
    308670517         InSequence   None        None     null        09-18T13:56Z
    308670518         InSequence   None        None     null        09-18T14:02Z
    308670519         InSequence   None        None     null        09-18T10:33Z

**`error_code` is null on all three and every lead reads `InSequence`.**
Nothing has failed. The leads are progressing; the graph is spending delays.

## The measured graph, on the branch these three are actually on

`CHECK_IS_CONNECTION` is the root and it forks. All three read
`leadConnectionStatus: None`, so all three take the **unconditional** branch -
the not-connected path:

    CHECK_IS_CONNECTION    actionDelay 0 HOUR      cumulative   0h
      -> VIEW_PROFILE      actionDelay 3 HOUR      cumulative   3h
        -> FOLLOW          actionDelay 3 HOUR      cumulative   6h
          -> CONNECTION_REQUEST  actionDelay 1 DAY cumulative  30h

**Two actions and thirty hours stand between enrolment and the first connection
request.** Not three days of profile views. The `1 DAY` delay in front of
CONNECTION_REQUEST is the single largest component and it is deliberate - it
is in the approved graph.

So the answer to the handoff's question is: **the graph spends 3 hours and 3
hours, then waits a day.** The VIEW_PROFILE-heavy stretches - 2 DAY, 3 DAY and
5 DAY nodes - are all on branches that come AFTER the connection request or on
the already-connected fork. None of them is in front of it.

## I nearly recorded the opposite, from a field-name miss

The first walk of this graph printed `delay=None` on all 24 nodes and I was one
step from writing down "there are no delays in front of CONNECTION_REQUEST,
so three days is unexplained" - a finding that would have been confidently
wrong and would have sent somebody to look for a provider fault.

The field is **`actionDelay` / `actionDelayUnit`**. I had probed `delay`,
`delayInHours`, `waitTime` and `delayValue`, none of which exist on this
payload, and a miss on all four is indistinguishable from a genuine absence.

This is the third time this class of error has been caught in this repository
in three days, and it is the same one CORRECTION #3 warns about for signatures.
**A field that reads empty is a question about the field name until the raw
keys have been dumped.** The keys here, in full, are: `nodeType`,
`actionDelay`, `actionDelayUnit`, `payload`, `conditionalNode`,
`unconditionalNode`.

## The prediction, so Monday is a test rather than another look

The three leads last acted on 2026-09-18 between 10:33Z and 14:02Z. On the
graph above those actions are the FOLLOW at cumulative 6h, which puts the
CONNECTION_REQUEST one day later.

    if `1 DAY` is wall-clock     due 2026-09-19 10:33-14:02Z, but that is a
                                 Saturday and outside the window, so the first
                                 opportunity is Monday 2026-09-21 09:00Z
    if `1 DAY` is working-time   due later on Monday 2026-09-21, same day

**Both readings converge on Monday 2026-09-21.** That is a real falsifier with
a date:

- Connection requests appear on the 21st -> the graph explanation is complete,
  the campaign is healthy, and nothing was ever wrong.
- Monday closes at 17:00Z with `leadConnectionStatus: None` on all three and
  `error_code` still null -> the graph no longer explains it, and the question
  becomes why a provider that moves `lastActionTime` daily will not execute
  the next node.

Either way the wait now has an end and a meaning.

## What this does not say

It does not say the campaign is fine. Three leads, five days enrolled, zero
connection requests and zero messages is still thin, and thirty hours of graph
delay does not by itself account for the 17th and the 18th both passing with
`connection: None`. It says the shape of the graph is known, measured, and
approved, and that Monday distinguishes the two remaining explanations.

## Numbers, as read

    HEYREACH_STATUS               IN_PROGRESS
    ENROLLED                      3
    CONNECTION_REQUESTS_SENT      0
    MESSAGES_SENT                 0
    REPLIES                       0
    SENDERS                       [174892]
    ERRORS                        none - error_code null on all three
    NEXT_ACTION                   CONNECTION_REQUEST, predicted 2026-09-21
    WITHDRAW_AFTER                21 days, from the request node's payload
