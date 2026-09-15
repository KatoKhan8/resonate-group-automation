# TASK-093 - the fifth arm exists in code and has never been generated

## THE FACT

`variantgen.APPROACHES` defines FIVE approaches. Every measurement this
repository has ever taken of variant output shows FOUR:

    concise_direct    generated
    conversational    generated
    problem_led       generated
    observation_led   NEVER SEEN IN ANY MEASURED OUTPUT
    value_led         generated

`observation_led` is withheld unless the record carries a LICENSED
OBSERVATION, and `approaches_available` filters it out rather than letting
the model invent one. That design is correct and must not be weakened - a
model asked for an observation-led message with no observation WILL fabricate
one, and fabrication is exactly what `claims.check` exists to refuse.

**But nobody has ever confirmed the fifth arm generates even when the
evidence IS there.** The operator's requirement is a minimum of five
genuinely different variants WHERE SUPPORTED. This task establishes where it
is supported and whether it works there.

## THE THREE QUESTIONS

**1. How many records can support it?** Count, across the 300 real records in
`work/queue.jsonl`, how many hold a licensed observation of the kind
`approaches_available` requires. Report the number and the licence condition
it is testing. If the answer is ZERO, then the fifth arm is unreachable on
the current estate and THAT is the finding - say it plainly and say what a
record would need to carry.

**2. Does it generate on a record that supports it?** If any record
qualifies, run variant generation on it against the real model and show the
five arms. If none qualifies, construct the licence from evidence that is
genuinely present on a real record - do NOT invent an observation to make the
path run. If you cannot reach it without inventing evidence, say so.

**3. Is the fifth arm structurally different from the other four, or is it a
sixth way to ask the same question?** Report opening type, CTA type, tone,
length and product-introduction point, and the `diversity_collisions` verdict
for the five-arm set. TASK-089 is fixing the four-arm LinkedIn collapse; if
the fifth arm collides too, the same cause probably explains both.

## WHAT NOT TO DO

- **Do not remove or loosen the observation licence** to make five arms
  appear. Five arms where one is fabricated is worse than four honest ones.
  This is the single most tempting wrong move in this task.
- **Do not count "five approaches defined" as "five variants produced."**
  The whole point of TASK-084 was that 622 lines with 453 lines of green
  tests had never generated anything.
- Do not weaken the claims gate. If `observation_led` output is REFUSED by
  `claims.check`, that refusal is a finding and the underlying defect is the
  prompt, not the gate.

## DELIVERABLE

A count of licence-carrying records with the condition stated, the five-arm
output if reachable, the structural table, and a clear verdict on whether
"minimum five genuinely different variants" is currently achievable on this
estate or is blocked on evidence the records do not carry.
