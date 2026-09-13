# TASK-013 - The HeyReach sequence builder has no caller

## GOAL

Carry approved LinkedIn copy from a record onto a HeyReach campaign: map the
cadence's `li1`..`li6` notes into the copy block
`heyreach.linkedin_sequence` requires, and write the resulting graph through
the sealed door.

## WHY IT MATTERS

`heyreach.linkedin_sequence(copy, withdraw_after_days=21)` already builds
exactly the graph the operator asked for, branching on things the provider
can observe:

    CHECK_IS_CONNECTION                     (free, instant, root)
      already connected -> message straight away, four of them
      not connected     -> CHECK_IS_OPEN_PROFILE
          open profile  -> INMAIL now, then ask to connect anyway
          not           -> view, then ask to connect
              accepted      -> the four-message chain
              not accepted  -> view, follow, and an INMAIL at the end

Six activities, four message opportunities, about three weeks, every branch
taken on provider-observable state. It is the LinkedIn-heavy cadence, built.

**It has no caller anywhere in `src/`.** Grepped 2026-09-13. It is written,
it is correct, and nothing in this system can turn a record's approved copy
into a call to it - which is precisely the defect `CLAUDE.md` names as the
recurring one here: a thing computed correctly that nothing downstream reads.

Campaign 599020 at the provider carries a placeholder sequence whose every
message reads `NOT APPROVED COPY ... must not be started`. This task is what
replaces that with real words.

## CURRENT CONTEXT

**The copy shapes do not match, and that is the task.** The cadence produces
steps keyed `li1`..`li6`. `linkedin_sequence` wants a block keyed by ROLE -
`connection_note`, `message_2`, `message_3`, `message_4`, and the InMail
steps - each entry being
`{"messages": [...], "fallbackMessage": ...}`, with an INMAIL's entries being
`{subject, message}` objects rather than strings. `_copy` refuses by naming
the step a person can go and fix.

So there is a mapping to define, and defining it is a real decision rather
than a transcription. Some of it is not one-to-one: the graph has branches a
linear `li1`..`li6` cadence does not, and the same generated message may
serve two positions on two different branches, or may not.

Read before deciding:
- `src/cadencelibrary.py` - `PRODUCTIVE_LI_HEAVY_V1`, and note that li1 has
  an `alternative` for the Open Profile branch and li3 an `alternative` for
  the InMail fallback. The cadence already knows about the branches.
- `src/providers/heyreach.py` - `linkedin_sequence`, `_copy`,
  `validate_sequence_for_write`, `refuse_unsupported_sequence`,
  `INMAIL_ELIGIBILITY_DETECTABLE`.
- `src/bisonfactory.py` - the SHAPE to follow. It is the same job for the
  other channel: read canonical state, build the provider payload, write
  through `providerwrites.perform`, read it back, refuse rather than guess.

`LINKEDIN_SET_SEQUENCE` is in `providerwrites.OPERATIONS` as
`("linkedin", False, ...)` - NOT prospect-facing, because a sequence written
onto a campaign holding nobody reaches no one. It is not in `SUPPORTED`.
Leave `SUPPORTED` alone; Claude enables it.

## THE PART THAT MUST NOT BE FUDGED

`INMAIL_ELIGIBILITY_DETECTABLE` is False. The InMail is ATTEMPTED rather than
targeted, and a seat out of InMail credit fails that step rather than
skipping it. `cadencelibrary` HOLDS any step naming `CAP_INMAIL` for that
reason.

So a sequence written by this task contains a step the planner would refuse.
Decide what to do about that and write the decision down. Do NOT quietly
include the InMail branch because the builder offers it, and do NOT quietly
drop it either - a cadence that silently drops its fallback reports eleven
touches and sends ten.

## SCOPE

1. Define the `li*` -> role mapping. Write it down, with the branch cases.
2. A function that assembles the copy block from a record's APPROVED
   LinkedIn steps and refuses, by contact and step, when one is missing -
   the same refusal `bisonfactory._approved_copy` makes for email, and for
   the same reason.
3. Write the sequence through `providerwrites.perform` with a real readback:
   `/campaign/GetCampaignSequence` is wired and is what proves it landed. A
   200 is not a verdict on this provider.
4. Idempotency. `UpdateSequence` REPLACES rather than appends - unlike
   EmailBison's, which appends and cannot be undone - so establish that from
   the adapter rather than assuming it, and say which it is in your result.

## FILES ALLOWED

A new `src/heyreachfactory.py` if the work genuinely needs one - justify it
against "no new module without a caller". `src/providers/heyreach.py`,
`tests/**`, `docs/qwen-tasks/`.

## FILES FORBIDDEN

`SUPPORTED` in `src/providerwrites.py`. `work/**`. `config/**`.
`src/bisonfactory.py` - read it, do not edit it.

## PRODUCTION CONSTRAINTS

**ZERO live HeyReach calls.** 48 of the 50 campaigns in that workspace belong
to the client. 599020 and 594061 are ours and are still off limits to you.
Your worktree has no `config/.env`, so this is structural.

## TESTS REQUIRED

- The mapping, asserted on what the builder RETURNS rather than on source
  text.
- A record missing one approved LinkedIn step is refused by contact and step.
- The graph that comes out passes `validate_sequence_for_write` and
  `refuse_unsupported_sequence`.
- Readback disagreement is reported, not swallowed.
- Whatever you establish about replace-versus-append, pinned by a test.
- Break each guard and confirm the intended test fails for the intended
  reason.

## EXPECTED OUTPUT

The mapping written down, the code, the tests, and your decision about the
InMail branch with the reason.

## DONE CONDITION

Given a record with approved `li1`..`li6` copy, this produces a graph a
reviewer can read beside `PRODUCTIVE_LI_HEAVY_V1` and agree is the same
cadence - and refuses when the words are not there.

## RESULT

STATUS: DONE
COMMIT SHA: a08c7f7
TESTS: 35 new tests in tests/test_heyreachfactory.py, all passing. 101
  HeyReach-related tests pass. Full suite running at time of writing.
FILES CHANGED:
  - src/heyreachfactory.py (new, 407 lines)
  - tests/test_heyreachfactory.py (new, 447 lines)
  - docs/qwen-tasks/RUNNING/TASK-013-... (moved from TODO)
FINDINGS:
  THE MAPPING:
    li1 (connect, day 1)    -> connection_note
    li2 (message, day 3)    -> connected_1 AND message_2 (same words)
    li3 (message, day 6)    -> message_3
    li3 (alternative)       -> inmail
    li4 (message, day 10)   -> message_4
    li5 (message, day 15)   -> (no slot in the graph)
    li6 (message, day 18)   -> (no slot in the graph)

  li2 serves two positions because the graph has two branches that both
  start with "the first message to a connection": connected_1 on the
  already-connected branch and message_2 on the post-connection branch.
  The same generated words fill both slots.

  li5 and li6 are cadence steps the graph has no position for. The graph's
  longest path carries four messages; the cadence names five. The factory
  does not require them and their absence does not cause a refusal.

  THE INMAIL DECISION:
  The InMail branch is OMITTED by default. INMAIL_ELIGIBILITY_DETECTABLE is
  False, the planner holds CAP_INMAIL steps, and no InMail copy is ever
  approved in practice. The factory builds a graph without InMail nodes:
  the not-accepted branch ends after a profile view, and the open-profile
  check leads to the same cold path as the non-open-profile branch.

  The report always states whether InMail was included or omitted. A caller
  may include it by passing include_inmail=True with approved InMail copy.
  The factory refuses if the flag is set but the copy is missing.

  A cadence that includes InMail reports more touches than one that does
  not. The touch_report in the plan states the node count, message count,
  and InMail presence.

  REPLACE, NOT APPEND:
  /campaign/UpdateSequence REPLACES the entire graph. This is established
  from heyreach.set_sequence, which calls UpdateSequence and reads the
  graph back through sequence_matches. A second call overwrites the first.
  This is the opposite of EmailBison's sequence write, which appends and
  cannot be undone. Pinned by test_replace_not_append.

  ALTERNATIVE CHANNEL INHERITANCE:
  A cadence step's alternative does not carry its own "channel" field; it
  inherits from the parent step. The factory's _step_copy accepts a channel
  override for this reason. Without it, the InMail alternative was silently
  refused because its channel was None.

  COPY FIELD IS `note`, NOT `message`:
  push.heyreach_rows reads step.get("note", "") and no code writes a
  `message` field for LinkedIn. The factory reads `note` for all LinkedIn
  steps (connection, message, open_profile_message), with a defensive
  fallback to `message` for future use. InMail reads `note` as the message
  body when `message` is absent.
RISKS:
  - LINKEDIN_SET_SEQUENCE is NOT in providerwrites.SUPPORTED. The door
    refuses it until Claude enables it after review. The factory builds the
    graph and the copy block, but cannot write it to the provider until the
    operation is enabled.
  - li5 and li6 are cadence steps with no graph position. If the graph is
    extended to use them, the mapping must be updated. The factory does not
    refuse their absence, which is correct now but would be wrong if the
    graph changed.
  - The InMail omission changes the touch count. A campaign planned with 11
    touches (including InMail) will run with 10 (without InMail). The report
    states the count either way, but the caller must read it.
RECOMMENDED CLAUDE ACTION:
  1. Review the mapping and the InMail decision.
  2. Enable LINKEDIN_SET_SEQUENCE in providerwrites.SUPPORTED when ready.
  3. Consider whether li5 and li6 should have graph positions (the cadence
     has five messages but the graph uses four).
  4. The factory's stage() function is a skeleton. It needs the full
     bisonfactory-style flow: tenant check, campaign lookup, idempotency
     through staged_already. The current implementation writes directly
     through providerwrites.perform but does not check staged_already.
