# Why four leads stay blocked: nothing is broken

Four investigations, three fixed bugs along the way, and the answer is that
the system is working correctly. Written down because the wrong conclusion was
reached three times and the next reader will be tempted by all three.

---

## THE ANSWER

Regeneration **is** attempted on these steps. The model makes three attempts
per step. Every attempt fails a quality gate. The system correctly stores
nothing, and the old copy - which carries an em dash - survives because
nothing better could be produced.

From the record's own log:

    li2: no note passed the gates, nothing stored     attempts: 3
         rejected: "this repeats another LinkedIn step in the sequence"

    em1-em4: no draft passed lint, nothing stored     attempts: 3
         rejected: "hard_wrapped"
    em5: rejected: "unsupported claim"

Aggregated across the four blocked records:

    this repeats another step in the sequence              199
    this repeats another LinkedIn step in the sequence     178
    hard_wrapped                                           121
    unsupported claim                                       43
    the subject is 60 characters or more                    21
    domains_contact_no_angle                                20
    filler_phrase                                           16

**The `em_dash` failure is a SYMPTOM, not the cause.** The cause is that the
generator cannot produce copy for these four records that satisfies the
repetition and lint gates, so the pre-fix copy is never replaced - and that
pre-fix copy happens to contain an em dash.

## THE THREE WRONG ANSWERS, AND WHY EACH WAS PLAUSIBLE

**1. Approval blocks regeneration.** Mine. Three of the four steps are
approved, which made it look obvious. Wrong: `5bonsai/li2` is not approved and
is equally stuck.

**2. Gate ordering.** TASK-128. The ladder staleness check genuinely did sit
after lint, so a step failing lint never reached it - **a real bug, really
fixed**, and the impact report moved from 0 to 187. It did not move these
four.

**3. Set absorption.** TASK-129. `linkedin_set` consolidation genuinely did
drop the `ladder_stale` flag from the ops it replaced - **a real bug, really
fixed**, report moved 187 to 211. It did not move these four either.

Two real defects were found and fixed while chasing the wrong cause. That is
worth something, and it is also how four leads consumed four investigations.

## THE MISTAKE THAT COST THE MOST, AND IT WAS MINE

Diagnosing this, I called:

    generate.plan(rec, client='productive', regen_stale_ladder=True)   -> 0 stale ops
    generate.plan(rec, <config object>,     regen_stale_ladder=True)   -> 6 stale ops

`client` is a config object, not a name. Passing the string produced a
confident zero and sent me looking for a mechanism that was never broken. It
is the same shape as TASK-083's approval count reading 0 from a wrongly
reconstructed key, and the same shape as reading `sizing` instead of
`company_facts`. **A wrong argument and an absent feature look identical from
the outside.**

## WHAT WOULD ACTUALLY RECOVER THESE LEADS

Not a fix to the regeneration mechanism - it works. The generator has to be
able to write passing copy for these four records. The dominant blocker by a
wide margin is REPETITION: 377 of the ~440 rejections are one of the two
repetition checks.

That points at the records rather than the code. A record whose angle is
`None`, or whose facts are thin, gives the model little to vary between six
rungs, so every attempt repeats the last. `domains_contact_no_angle` appearing
20 times on four records supports that reading.

**Do not weaken the repetition check or the em dash rule to recover four
leads.** Both are correct and both are provably satisfiable: 497 regenerated
steps across the estate, zero em dashes, passing the same repetition gates.

## WHAT THIS MEANS FOR THE COHORT

The cohort is **47 of 51** and that is an honest number. The four are not a
mechanism failure to be fixed; they are four records the generator cannot
currently write well enough, which is exactly the outcome the gates exist to
produce. Recovering them is an enrichment question, not an engineering one.
