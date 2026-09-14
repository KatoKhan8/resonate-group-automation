# Why the regeneration cannot converge, and which task actually unblocks it

Measured on `adcuratio-com/ranjan-damodar`, the contact currently blocking the
HeyReach dry run.

## THE COPY IS GENUINELY BAD - THE GATE IS RIGHT

    li1  "i'd love to connect and share insights on operations and project
          capacity."
    li2  "how do you currently track utilisation and capacity across your
          live projects?"
    li3  "how are you currently managing capacity across your teams?"
    li4  "have you seen any challenges in tracking utilisation and capacity
          across your projects?"
    li5  "just checking in to see if you had any thoughts on improving
          utilisation and capacity across your live projects?"
    li6  "any thoughts on our previous discussions. no pressure!"

Four askings of the same question. This is the ORIGINAL defect the operator
named on day one, reproduced with "utilisation and capacity" in place of
"profitability". And `li6` fabricates a relationship on a record whose
`prior_contact` is False.

**Nothing here argues for weakening the gate.** It argues the opposite: the
gate caught exactly what it exists to catch.

## AND THE SYSTEM ALREADY KNOWS

Every one of the six is correctly re-planned:

    li1  repeats another step (repetition_across_rungs)
    li2  repeats another step (angle_wording_leakage, ...)
    li3  repeats another step (angle_wording_leakage, ...)
    li4  repeats another step (angle_wording_leakage, ...)
    li5  repeats another step (angle_wording_leakage, ...)
    li6  makes an unsupported claim ('our previous discussions')

`claims.check` catches the fabricated relationship. The planner asks for all
six to be rewritten. The gates are correct and the diagnosis is correct.

## SO WHY DOES A REGENERATION PASS NOT FIX IT

Because **the old failing notes are still siblings.**

`generate._note_quality` builds its sibling set from the trial record, which
is the STORED steps with the candidate substituted in. So when li2 is
regenerated, it is compared against li1, li3, li4, li5 and li6 - all five of
which are the stale, repetitive copy that is being replaced.

A genuinely good new li2 still shares "capacity", "projects" and "across"
with four stale notes that say nothing else. It is refused. Nothing is
stored. **The stale note stays, and the next pass faces the same wall.**

This is why a completed regeneration pass left the blocker in place and only
moved it from one contact to the next: the contacts that converged were the
ones whose stale siblings happened not to collide.

## THE CONSEQUENCE FOR THE TASK ORDER

**TASK-062 is the unblocker for TASK-061, not a tidy-up beside it.**

TASK-062's deliverable is exactly the fix: a stored step that does not
currently pass the gates must not be treated as a valid sibling by anything
that compares siblings - `generate._note_quality`, `generate._quality_of`,
and `heyreachfactory._plan`'s `campaign_repetition`.

With that exclusion, a good new li2 is compared only against siblings that
are themselves acceptable, and the sequence can converge one step at a time.

TASK-061 should be expected to report NOT CONVERGED until TASK-062 lands.
That is not a failure of TASK-061; it is the finding.

## THE ROUTE NOT TAKEN, AND WHY

Discounting the client's own angle vocabulary clears all five collisions on
this contact - measured, 5 to 0. It was rejected.

`SUBJECT_VOCABULARY` is deliberately narrow and its own comment says why:
"Structural words like 'visibility', 'tracking', 'planning' are NOT
discounted because they can indicate actual paraphrasing when shared across
steps." The client's angle vocabulary contains `visibility` and `planning`.
Discounting all thirty angle words would make the check pass this copy - and
this copy is four askings of the same question.

A gate that passes it is not a better gate. It is the defect returning with
the alarm switched off.
