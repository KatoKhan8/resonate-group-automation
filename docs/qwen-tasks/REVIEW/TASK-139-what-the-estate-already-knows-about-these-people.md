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

## RESULT

**STATUS:** DONE

**SNAPSHOT STAMP:** `2026-09-14T21:52:15Z from master 0ac5e60 300 records`

**COMMIT SHA:** 66cfc75

**TESTS:** Measurement script at `scripts/task139_measure_relationship_states.py`.
No unit tests — this task reports, it does not change src/.

**FILES CHANGED:**
- `docs/RELATIONSHIP-STATE-2026-09-15.md` (new) — full findings document
- `scripts/task139_measure_relationship_states.py` (new) — measurement script

**FINDINGS:**

The estate is pre-send. 300 records, 92 contacts, 1 push_marked event total.

| Relationship state | Count | Evidence | Changes a decision? |
|---|---|---|---|
| Previously emailed, no reply | 1 | push_marked(email) + no reply event | NO |
| Previously emailed, replied NEGATIVE | 0 | reply_classified=negative* | NO (none exist) |
| Previously emailed, replied POSITIVE | 0 | positive_reply_detected | NO — blocked same as negative |
| Previously emailed, reply UNKNOWN | 0 | reply_received without classification | YES — blocks via _replied |
| Already a LinkedIn connection | 0 | linkedin_connected/connection_accepted | YES — cadence.accepted_connection → expand_step |
| Previous LinkedIn outreach, no reply | 0 | push_marked(linkedIn) + no reply | YES — linkedinstate.plan_step holds |
| Suppressed / DNC | 0 | domain suppress list, contact flags | YES — eligibility._suppressed |
| Nobody has ever contacted them | 91 | absence of push_marked | NO — not computed as a state |
| bison_lead_id (prior EmailBison) | 29 | contact.bison_lead_id | YES — build_control_cohort only |

**Critical findings:**

1. **bison_lead_id is the ONLY relationship bit reaching production.** It is
   consumed by `scripts/build_control_cohort.py:eligible_contacts()` which
   skips these contacts. But `eligibility.decide()` does NOT consult it — the
   send path would happily send to a prior EmailBison lead.

2. **The estate conflates positive and negative replies.** `eligibility._replied`
   blocks on ANY reply event. A positive reply ("yes, let's talk") triggers
   the same BLOCKED_REPLIED as "remove me." The contact.stopped and
   contact.unsubscribed fields distinguish outcomes AFTER classification, but
   an unclassified reply blocks until a person reads it.

3. **The event log carries all the data; almost nothing reads it for decisions.**
   The infrastructure exists (linkedinstate, account.touches, account.replies)
   but with zero sends the states are empty.

4. **LinkedIn connection state: local model adds planning value, not runtime
   authority.** `linkedinstate.plan_step` avoids duplicate requests and gates
   unproven capabilities offline. The provider's CHECK_IS_CONNECTION is
   authoritative at execution time. The local model has no data to work with
   in this estate.

**Proposed change:** Add `prior_email_no_reply` boolean to `cadence.expand_step()`
context, following the same pattern as the existing `accepted` parameter.
Consumer: `cadence.expand_step()` at line 668. This would let copy selection
acknowledge that a contact already saw an email and did not reply, rather than
treating them as a cold prospect. Affects 1 contact at this snapshot.

**RISKS:**
- The measurement is against a snapshot from 2026-09-14. State may have changed.
- Agency DNC status cannot be measured without loading the on-disk list.
- 223 of 300 records have no contacts — the estate is very early stage.

**RECOMMENDED CLAUDE ACTION:**
1. Consider whether `eligibility.decide()` should consult `bison_lead_id` on
   the send path, not just at cohort selection time.
2. Consider whether `eligibility._replied` should distinguish reply
   classifications — a positive reply is a relationship, not a block.
3. The `prior_email_no_reply` proposal is safe to implement when the estate
   has more sends; the seam in `cadence.expand_step` already exists.
