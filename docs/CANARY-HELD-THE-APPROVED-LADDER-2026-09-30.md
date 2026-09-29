PRIORITY: THE CANARY IS HELD. THE RAMP HAS NOT STARTED.

# RACHELE IS HELD — HER APPROVED COPY BREAKS THE OFFER'S APPROVED LADDER

    measured at   master b946b59c, 2026-09-30 (overnight autonomous window)
    approved      hash fba63864ca640b9e, Rachele Crumpler / 2020 Companies

    PROVIDER WRITES        0
    PROSPECT-FACING SENDS  0
    CAMPAIGN ACTIVATIONS   0
    ENROLMENTS             0
    sending.live           off for productive, never turned on
    execution grant        never opened against a real campaign
    canary campaign        canonical row only, status HELD,
                           bison_campaign_id = None (never created)

Nothing was sent by this work.

---

## WHAT UNBLOCKED, AND WHAT IT REVEALED

Option (c) is done. The P.S. contract now sits on the approved step
(`_ps_is_intact`) instead of on set membership, so "deliberately no P.S." and
"a P.S. written and then lost" are finally different things. The approved
copy and the hash are untouched and no filler P.S. was invented.

Phase A's preflight then advanced past that blocker and stopped at the next
gate, which is the one this document is about.

    FAIL  step_objectives  em3  carries rung 1's own vocabulary
                                ('margin visibility') while rung 1's own step
                                em1 carries NONE of it, 100% against 0%
    FAIL  step_objectives  em4  carries rung 3's own vocabulary ('resource
                                decisions that move margin') while rung 3's
                                own step em3 carries NONE of it, 67% / 0%

**The gate is right and the copy is wrong.** The ladder it checks against is
`config/clients/productive-offers.yaml`, `step_objectives` 1 to 5, marked
`approved_by: Zvonimir, 2026-09-27`. Read against it, em3 restates rung 1
instead of advancing to resourcing, and em4 carries rung 3's argument on top
of its own. That is a real ordering defect in the approved artifact, exposed
by a corrected canonical contract — the one condition under which the
standing rule permits the approved copy to be regenerated.

## WHY IT WAS NEVER CAUGHT BEFORE

The sequence gate ran at STAGING and nowhere earlier, so it could refuse a
sequence but never ask for a better one. Its verdict was computed at
generation time and read by nothing — `generate_campaign` said so in its own
comment. That is now wired (b946b59c), and the writer is told.

## WHY REGENERATION DID NOT PRODUCE A CLEAN ARTIFACT

Regenerating left all eleven steps byte-identical, four times. Three causes,
each measured, all fixed and pushed:

1. **The planner never scheduled the steps.** `generate.plan` asks lint,
   claims and the quality gate whether a stored draft is finished work, and
   never asked `sequencegate` — so no op, so nothing to regenerate.
2. **The retry saw one reason.** It quoted the last rejection only, so the
   writer fixed the newest complaint and reintroduced an earlier one.
   Measured: `gpt-4.1-mini` refused for "would you be interested" on
   attempts 1, 3 and 5.
3. **Every attempt ran at temperature 0**, so the retries re-derived the
   first draft.

With all three fixed, the located feedback works — a dash is removed once the
writer is told which step holds it — and the failures now MOVE instead of
repeating. But **no draft clears roughly fifteen constraints across eleven
messages at once**, on either `openai/gpt-4.1-mini` or `openai/gpt-4.1`, at
ten attempts each. The last failures are a spaced hyphen, a service-list
P.S., an under-length body, and invented customer-outcome claims of exactly
the class TASK-914/921 hardened against.

**Her approved copy is intact.** A held contact stores nothing, so every run
left the record byte-identical — verified after each one.

## WHY THIS DID NOT SELF-REPAIR INTO A SEND

Three routes exist and the standing authorization forbids all three:

    a) relax the sequence gate       weakens the guard that found a real
                                     defect in approved copy
    b) hand-edit em3 and em4         patches prospect-facing copy outside
                                     the writer path, and the result would
                                     be words the operator never approved
    c) canary a different prospect   outside the Phase A grant, which names
                                     Rachele and hash fba63864ca640b9e

Phase A's authorization is bound to that hash. Any copy that fixes the ladder
is NEW copy with a NEW hash, and recording it as operator-approved would be
fabricating an approval. So Rachele is **HELD**, with the reason recorded —
the disposition the operator's own overnight instruction prescribes for an
individual prospect that cannot safely proceed.

## WHAT THE OPERATOR HAS TO DECIDE

One question, and it is not a routine one, which is why it was not decided
here:

**Does the 48-hour production authorization extend to prospect-facing copy
the operator has not personally read?** The ramp presumes yes — 50-company
batches cannot be hand-approved. Rachele presumes no, because her Phase A
grant names a specific hash. Those two cannot both hold, and which one
governs is an authorization question rather than an engineering one.

If YES, the canary proceeds on gate-certified copy as soon as the writer
produces a clean set, with the artifact posted as REVIEW_PENDING rather than
as approved. If NO, the canary needs a re-approved artifact and the ramp
needs a stated approval rule before its first batch.

## WHAT IS WORTH FIXING NEXT, WHOEVER PICKS THIS UP

The writer cannot currently satisfy the full constraint set for one contact.
That is not a Rachele problem — **it will hold every contact in every batch
of the ramp**, and it is the single thing most worth fixing before volume.
The architectural cause is visible: `_refuse_partial_regeneration` forbids
rewriting one step because the writer emits whole sets, so every attempt
discards the eight or nine messages that were already clean and re-rolls all
eleven. Joint satisfaction of ~15 constraints across 11 messages by repeated
whole-set sampling is the wrong shape for the problem. A step-scoped rewrite
that holds the clean siblings fixed is the obvious candidate and is a design
change, not an overnight one.

## COMMITS

    01b7caf6  Option (c): the P.S. authority moves to the approved step, and
              the campaign-scoped grant is wired to the campaign it authorizes
    b946b59c  The writer retry loop could not converge, and three measured
              reasons why

`01b7caf6` also carries two defects worth knowing about independently:

  - **TASK-566's grant could never be satisfied.** `bind_campaign` had zero
    production callers, so an unbound grant reached `_ensure_leads` with a
    real provider id and was refused by its own documented bootstrap. Phase A
    would have refused every lead however it was authorized.
  - **TASK-566 shipped a regression**: default-refuse landed without the
    estate suite being run to a verdict, and 14 modules were refused by a
    gate they are not about. Fixed, with the guard's teeth proved by
    mutation — neuter `require` and 19 of its 29 tests go red.
