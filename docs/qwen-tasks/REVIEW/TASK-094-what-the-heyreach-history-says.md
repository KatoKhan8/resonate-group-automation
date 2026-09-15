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
