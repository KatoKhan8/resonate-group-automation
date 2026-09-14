# TASK-056 - Five contacts the gates refuse, and nothing regenerates them

## THE FINDING, MEASURED

`heyreachfactory._plan` on `productive-linkedin-production-v1`, 2026-09-14:

    contacts   15
    pushable   10
    blocked     5

Every one of the five is blocked by a CLAIM, and the claims are real:

    caleb-crail      connected_4   'profitability' asserted about them,
                                   nothing stored supports it
    christine-xoinis connected_4   'our previous discussions' - a
                                   relationship that does not exist
    janie-karas      connected_4   'utilisation' asserted about them
    rik-de-veirman   connected_3, connection_note, message_4
                                   'profitability' asserted about them
    tina-frost       connected_4   'resourcing' asserted about them

The gates are right. The copy is wrong. **And nothing regenerates it.**

## THE ACTUAL DEFECT, WHICH IS NOT THE COPY

`generate.plan` decides a LinkedIn note needs writing like this:

    note = stored.get(spec["key"]) or {}
    if note.get("generated") and note.get("note"):
        continue

A note that EXISTS is a note that is done. So a stored note asserting
something the record cannot support is counted as work already finished, and
the planner says there is nothing to do - forever.

The email path does NOT have this defect and the fix is already written
there. `generate.plan` re-plans an email draft when `lint.classify` says
`failed`, and the comment above it says exactly why:

    "A DRAFT THAT DOES NOT PASS IS NOT A DRAFT. This asked only whether a
     body EXISTED, so a stored draft that fails lint was counted as work
     already done - and nothing else regenerates one."

That was written for email on 2026-09-13. The LinkedIn branch twenty lines
above it still asks only whether a note exists.

## GOAL

A stored LinkedIn note that fails the gates is re-planned and regenerated,
exactly as a failing email draft is.

## WHAT TO BE CAREFUL ABOUT

1. **Use the same gates the storer uses.** `generate.linkedin_note` now runs
   `lint.check_step`, `claims.check`, `claims.foreign_product` and the
   quality gate. The planner must ask the same questions, or it will re-plan
   notes that would pass and skip notes that would fail.

2. **Do not regenerate for a reason no rewrite can fix.** The email side
   already draws this line: `lint.classify` separates a failure about the
   DRAFT from one about the RECIPIENT, and `recipient_not_sendable` is a
   HELD code because no rewrite fixes a fact about an address.
   `LINKEDIN_HELD_CODES` holds `profile_missing` for the same reason. A note
   for a contact with no LinkedIn profile must not be regenerated three
   times.

3. **Three attempts, then stop.** `MAX_DRAFT_ATTEMPTS` already bounds one
   generation. What this must not create is a run that re-plans the same
   note every pass forever, spending three model calls each time. Establish
   what happens on the SECOND run over a record whose note cannot be fixed,
   and say so in FINDINGS.

## PROVE IT

Behavioural, through `generate.plan`:

  - a stored note that passes everything is NOT re-planned
  - a stored note asserting an unsupported claim IS re-planned
  - a stored note for a contact with no profile is NOT re-planned
  - the reason reaches the op's `why`, so an operator reading the plan can
    see which note is being rewritten and what for

Then break the wiring deliberately and confirm the intended test fails for
the intended reason.

## THEN MEASURE IT

With the fix in, run `heyreachfactory._plan` again and report the new
pushable count. It does not have to reach 15 - a note that cannot be made
true should stay blocked - but the five named above are all ordinary
regenerable copy and should move.

Regeneration needs live model calls. Copy `work/queue.jsonl` to a scratch
path and point `QUEUE` at the copy. Report the call count.

## WHAT YOU MAY NOT DO

- Do not weaken `claims`, `lint` or the quality gate to raise the number.
  The five are blocked because the copy asserts things about strangers that
  nothing supports, and that is the gate working.
- Do not touch `work/queue.jsonl` or `work/campaigns.jsonl`.
- No live provider call, no campaign mutation.

## RESULT BLOCK

End this file with STATUS, COMMIT SHA, TESTS, FILES CHANGED, FINDINGS,
RISKS, RECOMMENDED CLAUDE ACTION.
