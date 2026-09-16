PRIORITY: P0
DEPENDS:

# TASK-176 - the LinkedIn canary payload, resolved for three contacts

## WHERE THIS SITS

TASK-167 did this for email and it is what made the Bison path concrete: all 17
contacts resolved, all 51 step-renderings through lint and claims, an exact
payload in a document. LinkedIn has no equivalent, and it is now the shorter
pole.

What exists:

    599020   RESONATE - PRODUCTIVE LINKEDIN PRODUCTION V1
             DRAFT, 0 leads, 24 nodes, 1 sender that resolves and is active,
             readback hash 32f8dde79bfa0f27, 27/27 PASS
    list     933603 attached to it, 0 leads
    ladder   TASK-155, rung 3 = three economic_buyer/operations contacts,
             named by record id in docs/COHORT-LADDER-2026-09-15.md
    copy     the LinkedIn CONTROL is the operator's hand-written fallback,
             which beat everything the model produced

**Every copy-bearing node in 599020 holds exactly ONE message.** The
five-variant machinery has never reached this campaign, so whatever is in those
24 nodes is what a prospect would see.

## THE QUESTION

1. **Read the three.** Take rung 3 from the cohort ladder by record id. For
   each, every variable the LinkedIn templates need, resolved or fallen back,
   named. Email's `company` was the only blocking variable; find LinkedIn's.
2. **Render every step for all three**, and run each rendering through lint and
   through the claims gate against that contact's own evidence. Report PASS or
   FAIL per step per contact, not a total.
3. **What is actually in the 24 nodes?** Read them from the provider. Which
   carry copy, which are delays, which are conditions. Does the node sequence
   match the CONTROL the ladder assumes, and does the copy in the nodes match
   the copy your rendering produces? If they differ, that difference is the
   finding - the campaign was staged before the ladder existed.
4. **The payload.** Per contact: `profileUrl`, `firstName`, `lastName` - the
   schema TASK-158 established, with the last two required - plus the record id
   and the step copy. As JSON, PII hashed, in the deliverable.

## THE TRAP

Signal is 100% null at 550 records and angle is 79% null (TASK-155), so copy
that says something specific about a prospect has nothing true to say it from.
Email's answer was 23 fallbacks across 17 contacts and every `line` variable
generic. Expect the same here, count them, and do not treat a well-reading
fallback as personalization.

Second trap: do not touch the 24 nodes. The readback hash `32f8dde79bfa0f27`
is what proves the campaign is what we last verified, and `heyreach.set_sequence`
being authorized makes changing them easy and the hash worthless. Read them.

## WHAT YOU MAY NOT DO

- **No provider writes.** No add to 933603 or 940797, no sequence write, no
  node edit, no start, no activate. Reads only.
- Do not regenerate or rewrite the CONTROL copy.
- Do not add to `SUPPORTED` or `CONDITIONAL`.
- Never commit a profile URL, a prospect name, a seat-holder name or a domain.
  Hash identifiers and say what you hashed.

## FILES ALLOWED

    docs/LINKEDIN-CANARY-PAYLOAD-2026-09-16.md   (new, PII hashed)
    scripts/task176_*.py

## FILES FORBIDDEN

    src/   work/   config/

## DELIVERABLE

The three contacts with per-variable resolution, per-step lint and claims
verdicts, the 24 nodes read from the provider and compared to the rendering,
the fallback count, and the exact payload.
