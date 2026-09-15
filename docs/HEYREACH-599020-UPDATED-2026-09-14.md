# HeyReach 599020 is updated. Provider readback proves it.

    WRITE -> READ BACK -> COMPARE -> PASS

All four happened. The readback below was run as a separate process after the
write, and its exit code was read from the process rather than through a pipe.

    py -3 scripts/heyreach_readback.py productive-linkedin-production-v1 --expect
    REAL EXIT CODE = 0
    27 passed, 0 failed
    VERDICT: PASS
    sequence_matches: MATCH

Full output: `docs/evidence-heyreach-readback-2026-09-14.txt`.

## WHAT CHANGED AT THE PROVIDER

    BEFORE                          AFTER
    nodes              24           17
    merge variables     0            8
    'jacob'        PRESENT       absent
    '&Partner'     PRESENT       absent
    repeated msg on a path  YES    none

The campaign previously carried ONE contact's personalised words at campaign
level - "hi jacob, as a founder..." - for a canonical row naming fourteen
records. Thirteen other people would have received a note addressed to Jacob.
It also sent the identical message twice on the already-connected branch,
three days apart, which only a path walk could see.

Both are gone, confirmed by reading the provider back.

## WHAT IS UNCHANGED, AND DELIBERATELY

    status      DRAFT
    leads       0
    schedule    not set
    senders     one seat, 174892

**Nothing has been sent and nobody has been added.** `LINKEDIN_ADD_LEAD` is
still not in `providerwrites.SUPPORTED`, and `Resume` and `StartCampaign` are
still absent from `heyreach.WRITE_ROUTES`. The sequence write was the only
door that was open, and it is the one that was used.

## HOW THE BLOCKER WAS ACTUALLY CLEARED

Not by weakening a gate. The dry run refused for hours on
`<client-a86dfd>-com/ranjan-damodar`, whose six LinkedIn notes asked the same
question four times in different words.

`generate.plan` regenerated ONE note at a time, so each candidate was compared
against the five stale notes still saying the same thing - it had to differ
from all of them at once or be discarded. Two full passes and 18 model calls
stored nothing.

TASK-068 regenerates a mutually-colliding set AS A SET, transactionally:
build the whole replacement, gate it together, commit only if every member
passes, keep the originals on failure. The copy that resulted has five
different jobs instead of one question repeated.

A shortcut was measured and REJECTED: discounting the client's own angle
vocabulary takes that contact from five collisions to zero, and the copy it
then passes is the four identical questions. See
`docs/WHY-REGENERATION-CANNOT-CONVERGE-2026-09-14.md`.

## WHAT IS STILL WRONG, STATED PLAINLY

**`pushable` is 3 of 15 contacts.** It was 10 before the gates tightened. The
sequence write does not depend on it - the graph carries merge fields - but
the LEAD ADD does, and three is a thin cohort. The other twelve are blocked by
unsupported claims or copy that still fails a gate.

**The product is still not reliably named.** Estate baseline: `li4` names
Productive in 42% of stored notes, `em3` in 29%. TASK-065 is measuring it
properly, per sequence rather than per step.

Neither blocks the sequence being correct at the provider. Both block a
sensible lead cohort.

## THE NEXT DECISION, AND IT IS SEPARATE

Adding a lead is not a continuation of this. It requires enabling
`LINKEDIN_ADD_LEAD`, and it should not happen at `pushable: 3` when the same
regeneration work would raise it. Order remains: sequence first, leads second,
and leads only when the cohort is worth sending to.
