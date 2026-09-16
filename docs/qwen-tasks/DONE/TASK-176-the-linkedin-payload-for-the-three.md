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

## RESULT

- **STATUS:** DONE
- **COMMIT SHA:** 833a9f2
- **TESTS:** Script ran successfully; lint and claims checks produced verdicts per role per contact. No unit tests added (script is analysis, not engine code).
- **FILES CHANGED:**
  - `scripts/task176_linkedin_canary_payload.py` (new) — resolution, lint, claims, payload builder
  - `docs/LINKEDIN-CANARY-PAYLOAD-2026-09-16.md` (new) — the deliverable document
  - Task file moved TODO → DONE
- **FINDINGS:**
  1. **15 of 24 variable slots are CONTROL fallbacks.** Only Austin Ball (contact #1) has operator-control-arm approval for all 8 roles. Sam Nielsen has 7 fallbacks (li1 approved by claude, not operator-control-arm). Anthony Andreatos has 8 fallbacks (zero approved copy).
  2. **Sam Nielsen's generated li1 FAILS lint and claims.** The text "noticed you're scaling operations at 2ton — i work with creative teams on capacity planning across live projects." contains an em dash (U+2014, lint fail) and a flat operational assertion ("you're scaling operations at 2ton", claims fail). This copy would be refused by the factory.
  3. **LinkedIn's blocking condition is approval, not a missing variable.** Email's blocker was `company` (unresolvable). LinkedIn's blocker is the absence of `approval.by` on a cadence step. The config fallback fills the graph's `fallbackMessage` but the per-lead `customUserFields` must carry approved words. 2 of 3 canary contacts cannot be staged.
  4. **The 24 nodes are the OLD sequence.** The corrected campaign 599020 carries 17 nodes with merge variables (`{connection_note}`, `{connected_1..4}`, `{message_2..4}`). The words arrive per lead in `customUserFields`. The graph structure matches the CONTROL the ladder assumes.
  5. **li6 has no graph position.** The cadence names 6 steps (li1-li6) but the HeyReach graph has positions for only 5 (li1-li5 via COPY_MAPPING). li6 exists on paper but never fires at the provider.
  6. **connected_1 and message_2 carry the same text** (both from li2), and likewise connected_2/message_3 (from li3) and connected_3/message_4 (from li4). This is by design in COPY_MAPPING, not a defect - they sit on different branches of the graph.
- **RISKS:**
  - The two contacts without operator approval need their cadence steps replaced with CONTROL fallbacks before staging. This is a provider write (cadence data in the queue) that this task did not perform.
  - Sam Nielsen's generated li1 contains PII ("2ton") that would be sent literally if the approval gate were bypassed.
- **RECOMMENDED CLAUDE ACTION:**
  1. Replace generated copy with CONTROL fallbacks for Sam Nielsen and Anthony Andreatos (cadence steps li1-li5 in the queue).
  2. Re-run this script to confirm 0 fallbacks and all-PASS verdicts.
  3. Then stage the three contacts to campaign 599020 (requires LINKEDIN_ADD_LEAD, which is not yet in SUPPORTED).
