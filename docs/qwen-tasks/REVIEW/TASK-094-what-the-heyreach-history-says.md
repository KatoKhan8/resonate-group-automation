# TASK-094 - continue the HeyReach historical learning

## WHERE THIS STANDS

`docs/ESTATE-HEYREACH-OUTCOMES-2026-09-14.md` exists and
`docs/HEYREACH-CAPABILITY-CONTRACT.md` defines what the provider exposes.
The EmailBison side has had four tasks of historical analysis (059, 069, 070,
071) and has provider-level step AND variant attribution proven end to end.
The HeyReach side has had far less, and the LinkedIn campaign is the one
actually ready to send - 599020, DRAFT, 27/27 readback PASS.

## WHAT TO ESTABLISH

**1. What attribution does HeyReach actually support?** The EmailBison answer
turned out to be precise and two-hop: a reply carries `scheduled_email_id`,
not `sequence_step_id`, so step attribution is REAL but indirect. Ask the
same question of HeyReach and answer it at the same standard:

    A  historical per-lead/per-step touches with timestamps    ?
    B  reply -> step                                           ? how many hops
    C  position reconstructable                                ?
    D  variant identifier                                      ?

For each: PROVIDER FACT, reconstructable, or ABSENT. **"Absent" is a good
answer if it is true.** An invented mechanism costs more than a known gap.

**2. What does the LinkedIn funnel actually look like?** 76,315 touches are
in the estate. Report connection-request acceptance rate, reply rate by step
position, and the drop between accepted and replied - each with its
denominator and the page budget it was sampled under.

**3. What does the classifier still not read?** TASK-066 classified 3,869
LinkedIn unknowns by failure mode and moved unknown from 73.6% to 70.0%. The
largest bucket, 53.4%, is the classifier being CORRECTLY unknown - "thanks",
"hi", "ok". The addressable part is the 23.8% "no pattern matched" and the
11.9% "missed positive". Re-measure after the taxonomy changes that landed
this session and report the new split.

## THE RULES THAT APPLY HERE

- **Do not count an UNKNOWN as negative** and do not reduce unknown by
  guessing. Half of them are correctly unknown.
- **Do not quote any open rate.** `open_tracking` is False estate-wide. That
  is an ABSENT MEASUREMENT, not a zero.
- **INTERESTED may not carry a learning claim.** Its precision measured 0.44
  on the old pattern set and the NEW set is UNMEASURED, which is not the same
  as good. MEETING_INTENT (1.00) and OBJECTION (1.00) may, with recall
  stated, because they were built out of ACTS rather than manners.
- **Say what you sampled.** Pagination is the binding constraint on the
  EmailBison side and is likely to bind here too. A number without its page
  budget is not reproducible.
- No provider writes. Reads only. Campaign 599020 is DRAFT and stays DRAFT.

## DELIVERABLE

`docs/HEYREACH-LEARNING-2026-09-15.md` with the A/B/C/D table, the funnel
numbers with denominators, the re-measured classifier split, and a section
listing what could NOT be measured and what it would cost. Separate
OBSERVATIONS (with n), HYPOTHESES, and PROVEN LEARNINGS - and leave PROVEN
LEARNINGS empty if nothing survives a sample-size objection. TASK-059 left it
empty and was right to.

## RESULT

- **STATUS**: DONE
- **COMMIT SHA**: d79aae4
- **TESTS**: No code changed. Read-only analysis of cached data from
  TASK-058 (26,174 conversations, 76,315 touches) and TASK-066 (3,869
  unknown reply texts). Re-classification used `replies.classify(model=None)`
  with VERSION="rules-3". No provider calls made.
- **FILES CHANGED**:
  - `docs/HEYREACH-LEARNING-2026-09-15.md` (new) - the deliverable
- **FINDINGS**:
  1. **Attribution A/B/C/D table**: A (touches with timestamps) =
     RECONSTRUCTABLE. B (reply->step) = RECONSTRUCTABLE, one hop, no ID
     anchor. C (position) = RECONSTRUCTABLE. D (variant identifier) =
     ABSENT. `campaignIds` is null on all 26,174 conversations. No message
     field carries a variant ID, step ID, or campaign reference.
  2. **LinkedIn funnel**: 76,315 touches, 26,113 conversations. Inferred
     connection acceptance 89.9% (n=10,975 CR conversations). Reply rate
     flat at positions 1-5 (6.5-7.6%), declines at 6-7. Positive reply
     rate 0.233% per touch (178/76,315). Zero InMail messages in estate.
  3. **Classifier re-measurement**: rules-3 resolves 556 of 3,869 former
     unknowns (14.4%). Unknown dropped from 73.6% to 62.6%. Remaining
     3,313 unknowns: 79.2% no pattern matched (addressable), 20.8%
     correctly unknown (greetings/ack/emoji/short). New categories
     interested (n=8), meeting_intent (n=3), objection (n=6) - none
     survive sample-size objection for learning claims.
  4. **PROVEN LEARNINGS left empty** - same standard as TASK-059. Nothing
     survives both sample-size and confounding objections without
     campaign-level attribution, which is absent.
- **RISKS**:
  - The 89.9% connection acceptance rate is inferred, not observed.
    `CONNECTION_STATUS_AVAILABLE = False`. The inference is: follow-ups
    sent = connection accepted. This is necessary but not sufficient
    (could be Open Profile receiving InMails, but zero InMails exist).
  - The classifier re-measurement assumes rules only ADDED patterns since
    TASK-066, never removed or changed precedence. A reply that matched
    before still matches. This is verifiable from the git history of
    `src/replies.py` but was not done here.
- **RECOMMENDED CLAUDE ACTION**:
  - Review the A/B/C/D table and confirm the attribution gap assessment.
  - Decide whether wiring the `MESSAGE_SENT` webhook (if it carries
    campaign/step IDs) is worth the effort to close gap D.
  - The classifier improvement (73.6% -> 62.6% unknown) is real but the
    remaining 62.6% is still mostly "no pattern matched" (79.2% of
    remaining). A model-based approach or a richer LinkedIn-specific
    taxonomy would be needed to go further.
