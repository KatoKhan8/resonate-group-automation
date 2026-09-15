PRIORITY: P0
DEPENDS: 

# TASK-130 - read the REGENERATED cohort as a human, against the fallbacks

## WHY THIS IS THE GATE

TASK-098 returned **DOES NOT BEAT FALLBACKS** and that verdict still stands in
the handoff - but it was taken on copy generated 2026-09-13, before the ladder
fixes. **That copy has since been replaced.** 497 of ~716 steps now carry the
current ladder, and the cohort's numbers moved:

    measure            pre-fix estate    regenerated
    Productive named        25%              93%
    "I noticed" openers     20%               0%
    sender identified       23%              40%
    "just checking in"      27 estate-wide    0 in regenerated steps

    economic_buyer cohort passing lint:  26  ->  47 of 51

**Nobody has read the new copy.** Every verdict on record describes copy that
no longer exists. The lead block is still correct, and it is now resting on a
measurement of something else.

## THE QUESTION, UNCHANGED FROM TASK-098

Not "is this acceptable". It is:

    DOES THIS COPY BEAT THE HAND-WRITTEN FALLBACKS?

The fallbacks beat all 165 generated emails and all 15 connection notes when
TASK-063 and TASK-064 last compared them. That is the bar.

## WHAT TO READ

The 47 passing contacts in the economic_buyer cohort - specifically their
REGENERATED steps (`ladder_fingerprint` present). Read whole sequences, not
individual messages: a sequence can hold six clean messages and still ask one
question six times.

Check each of the failures the earlier reads found, and say whether it is
still true:

    Productive named, and with enough context to mean something
    the sender says who is writing, at rung 1
    six rungs doing six DIFFERENT jobs, not one question six ways
    an easy out at the last rung
    no "i noticed" opener, no "just checking in"
    greeting renders - no "Hey ,", no "Hi undefined,", no cohort name
    a signature that says who it is from

`ogpartner-dk/jacob-faertz` was the reference sequence when the ladder ran
correctly. TASK-110 found only 11 of 60 sequences matched that shape; re-count
it on the regenerated set.

## WHAT NOT TO DO

- **Do not approve anything.** Approval is a human act and it is not yours.
  This task produces a verdict, not a promotion.
- **Do not edit copy to make it pass.** Report what is there.
- Do not read the stale steps and report them as the new copy. Filter on
  `ladder_fingerprint` being present, and say how many you read.
- Do not conclude "acceptable because it passes the gates". That is exactly
  the condition that produced the lead block in the first place.
- Hash every identifier in the report. Do NOT quote a real prospect reply.

## DELIVERABLE

`docs/HUMAN-READ-REGENERATED-2026-09-15.md`: a verdict of BEATS FALLBACKS /
DOES NOT BEAT FALLBACKS, per sequence, with the reasoning, and a count of how
many of the 47 you would send as they stand.

**A clear NO is a complete and valuable result.** It would mean the ladder
fixes moved the measurable things and not the readable ones, which is worth
knowing before anybody spends a lead on it.
