PRIORITY: P1
DEPENDS:

# TASK-139 - the relationship states we can actually prove, and what each one forbids

## THE PROBLEM IS NOT THAT HISTORY IS MISSING

It is that history exists and only ONE bit of it reaches a production decision.
`build_control_cohort.py` holds out contacts carrying a `bison_lead_id` - 29 of
277 - and that is the entire relationship model in the live path. Everything
else the estate knows about a person is inert.

That single bit conflates cases that must be treated differently:

    previously emailed, no reply
    previously emailed, replied NEGATIVE
    previously emailed, replied POSITIVE
    previously emailed, reply UNKNOWN
    already a LinkedIn connection
    previous LinkedIn outreach, no reply
    suppressed / DNC
    nobody has ever contacted them

A previous POSITIVE reply is not a reason to hold somebody out of outreach -
it is a reason to treat them as a warm relationship rather than send them a
connection request. Holding all of them out equally is as wrong as sending to
all of them equally.

## WHAT THIS TASK IS - MEASUREMENT FIRST, AND IT MAY BE ALL OF IT

Read the snapshot, not the queue:

    work/queue.snapshot.jsonl     read-only copy of production
    work/queue.snapshot.STAMP     when, and from which commit

**Quote the stamp in your result block.** A measurement against a snapshot is
a measurement at a moment and the moment is part of the answer. Never write to
either file.

Answer, with counts:

1. For each state above, how many contacts in the estate are in it, and WHAT
   FIELD PROVES IT. A state you cannot evidence is not a state - report it as
   unknown and say what would be needed.
2. Which of those states are already computed somewhere in `src/`, by name.
   `engagement`, `touch`, `events`, `replies`, `linkedinstate` and
   `eligibility` all hold something adjacent. Name the function and say what
   reads its answer.
3. **THE ONE THAT MATTERS: which of them changes a decision today?** For each
   state, trace whether any production path - channel choice, cohort
   membership, connection request vs message, copy, cadence - reads it. A
   state computed correctly that nothing consumes is the recurring defect in
   this repository and finding one is a result, not a failure.
4. LinkedIn connection state specifically. The 599020 sequence root is
   `CHECK_IS_CONNECTION`, so the PROVIDER branches at runtime and a connection
   request never reaches an existing connection. Given that, state precisely
   what a local connection-state model would add that the provider's own
   branch does not. It may be little. Say so if so.

## WHAT YOU MAY NOT DO

- No provider calls. You hold real keys and the rule is READS ONLY at every
  provider; this task needs none at all.
- Do not write to `work/`.
- Do not change `eligibility.must_not_contact`. Suppression and DNC semantics
  are not this task's to move.

## IF THE MEASUREMENT LEAVES TIME

Propose - in the task file, as a design, with the consumer named - the
smallest change that would make ONE additional state change ONE real decision.
Smallest, with a named consumer. Not a state machine.

## FILES ALLOWED

    docs/RELATIONSHIP-STATE-2026-09-15.md   (new, your findings)
    scripts/task139_*.py                    (measurement scripts)
    the task file itself

## FILES FORBIDDEN

    src/  (anything - this task REPORTS; Claude changes the live path)
    work/ (anything)

## DELIVERABLE

The counts with their evidence fields, the consumed/not-consumed verdict per
state traced to a named caller, the snapshot stamp, and the one proposed
change with its consumer.
