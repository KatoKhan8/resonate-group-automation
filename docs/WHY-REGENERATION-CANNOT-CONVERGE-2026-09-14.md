# Why the regeneration cannot converge, and which task actually unblocks it

Measured on `<client-a86dfd>-com/ranjan-damodar`, the contact currently blocking the
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

---

## THE COUNTER-ARGUMENT, AND WHY IT IS REJECTED

TASK-061 reached the opposite conclusion and it deserves answering in full,
because it is a reasonable argument that happens to be wrong:

> "The shared words are SUBJECT words, not STRUCTURAL. Every message in this
> sequence is ABOUT capacity and utilisation because that is the
> conversation. The model is being asked to write four messages about
> capacity management without using the words 'capacity', 'projects' or
> 'utilisation' - which is the entire subject. The model is not paraphrasing
> the same idea four times."

**It is paraphrasing the same idea four times.** Here is the stored copy:

    li2  "how do you currently track utilisation and capacity across your
          live projects?"
    li3  "how are you currently managing capacity across your teams?"
    li4  "challenges in tracking utilisation and capacity across your
          projects?"
    li5  "any thoughts on improving utilisation and capacity across your
          live projects?"

Four questions. One question.

**And the ladder never asked for four messages about capacity.** What it
actually asks:

    li2  a first message, one operational angle, put as a question
    li3  a SECOND, DIFFERENT operational angle, naming the consequence
    li4  SAY WHAT THE PRODUCT IS - name it, say what it joins up
    li5  a concise final follow-up, no new argument
    li6  close the loop, an easy no

`li4`'s job is the product. `li6`'s job is an exit. Neither is a capacity
question. The model collapsed five different jobs into one subject, and the
gate noticed. That is the gate doing exactly what it exists for.

Widening `SUBJECT_VOCABULARY` would make the gate accept this. It would not
make the copy better; it would remove the only thing currently reporting that
the copy is bad. Measured: discounting the client's angle vocabulary takes
this contact from five collisions to zero, and the copy it then passes is the
four questions above.

**REJECTED. The vocabulary stays narrow.**

## WHAT TASK-061 GOT RIGHT, AND IT IS THE IMPORTANT HALF

Eighteen model calls - six steps, three attempts each - ALL FAILED, and
nothing was stored. Two full passes produced an identical blocker.

That is the real finding, and it is not about vocabulary. Each fresh
candidate is compared against the five stale notes that are still there, so a
new `li2` must differ from four messages about capacity at once. It cannot,
and the one it replaces stays. The loop cannot escape its own starting state.

The fix is TASK-068: regenerate the colliding set AS A SET, so no member of
the old set constrains the new one.
