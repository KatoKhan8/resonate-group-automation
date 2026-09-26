# FINDING: Infinum operator_summary "70" is not on the page

**TASK-365, 2026-09-26.**

The `operator_summary` for the Infinum case study in
`config/clients/productive-offers.yaml` states:

> digital agency, Zagreb, 420 people, resource planning for 350+, grew from
> 70 to 350

The stored page text (fetched from
`https://productive.io/customer-stories/resource-planning-for-350-people-using-productive/`)
states:

- "420 employees" (metadata)
- "370 people" (body text)
- "350+ people" (title and body)

**The figure "70" does NOT appear on the page as a standalone token.** It
appears only as part of "370" (the current headcount). The claim "grew from
70 to 350" cannot be traced to the stored page text.

## What this means

Per the operator's rule, copy may quote only what the page itself states.
The figure "70" from the `operator_summary` is therefore **not licensed for
quotation**. The lint correctly refuses a claim asserting "Infinum grew from
70 to 350 people" because "70" is not on the stored page.

## Operator decision needed

This is an operator decision, not a code fix. Two options:

1. **Correct the summary** to match what the page actually states (370
   people, not "grew from 70 to 350").
2. **Mark the summary as orientation-only** (which it already is by the
   task's rules) and accept that "70" is not quotable.

Either way, the lint behaviour is correct: it refuses the claim.
