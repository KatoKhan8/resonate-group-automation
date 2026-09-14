# EmailBison copy and sequence requirements

Standing requirement, set by the operator 2026-09-15. This governs EmailBison
generation, QA and learning. It sits under `PLAYBOOK.md` and does not
override any safety rule: suppression, DNC, approval, pre-send recheck,
volume caps and the no-live-action restriction all still outrank it.

## 1. A SEQUENCE IS ONE CONVERSATION, NOT FIVE COLD EMAILS

**The defect, in our own production data.** Probed 2026-09-15:

    campaign 481   RESONATE production, 5 steps
                   thread_reply = False on ALL FIVE

Every step is a brand-new cold email with its own subject. That is the thing
this document exists to stop.

**The provider supports the alternative and our estate already uses it.**
`thread_reply` is a real field on a parent sequence step - PROVIDER FACT,
read from the live API:

    campaign 352   5 parents   order 1..5 thread_reply = F, T, F, T, F
                   the estate's largest at 92,806 sent
    campaign 327   8 parents   only step 2 is a same-thread follow-up
    campaign 335   8 parents   only step 2 is a same-thread follow-up
    campaign 481   5 parents   none

So the alternating new/follow-up/new/follow-up/new shape the operator
described is not a guess - it is what the biggest campaign in the estate
does. That is a correlation with a structure, not yet with an outcome.
TASK-080 measures whether it actually performs.

**Note:** a step carries an `email_subject` even when `thread_reply` is True.
Thread behaviour is governed by the `thread_reply` flag, NOT by omitting the
subject. Do not infer a follow-up from a missing subject.

### The starting hypothesis, and it is a hypothesis

    EMAIL 1   new thread     who / why you / relevant problem / simple question
    EMAIL 2   SAME THREAD    short, adds one thought, does not repeat email 1
    EMAIL 3   evidence-led   different pain or angle; Productive where it fits
    EMAIL 4   new thread     fresh subject IF justified - proof, consequence,
                             insight, or stronger personalisation
    EMAIL 5   SAME THREAD    short close, low-friction, wrong-person redirect

**Five steps is the current production target, not a finding.** Do not
conclude five is optimal because it was requested. Historical and live
evidence decides whether a cohort should run 3, 4, 5 or 6.

**Do not generate a new subject for every step.** A follow-up preserves the
thread using the provider's own mechanism.

## 2. GREETING

Open naturally with the prospect's first name. Style only, not syntax:

    Hey <first name>,
    Hi <first name>,
    <first name> - quick question,

**Use the variable syntax EmailBison actually supports.** Do not copy a
placeholder from a document. Measured on this estate 2026-09-14: 3,295
single-brace occurrences and ZERO double-brace across 81 sequences, so
`{{first_name}}` would reach a prospect as literal text on this provider.
Confirm the syntax against the provider before generating, and
`bison.ensure_custom_variables` / `LEAD_VARIABLES` is where the names live.

**NEVER hardcode a person's name.** HeyReach campaign 599020 carried "hi
jacob" for a row naming fourteen people. `heyreachfactory` now refuses a
cohort name in the graph; EmailBison needs the same guarantee.

**A missing first name must degrade safely.** None of these may ever render:

    Hey ,        Hi undefined,      Hi null,

Either a fallback renders, or the record is excluded from that variant. A
blank greeting is not an acceptable third option.

## 3. SIGNATURE

End naturally, from the sender identity in campaign or provider
configuration. **Do not hallucinate a sender name, title, company, phone
number or anything else in a signature.** An invented sender is a claim about
us the record cannot support, and `claims.RELATIONSHIP` already refuses "as a
fellow founder" for the same reason.

The signature need not be verbose. For a very short same-thread follow-up,
whether a full signature helps at all is an EVIDENCE question - TASK-080
measures what the estate actually does.

## 4. VARIABLES ARE NOT DECORATION

Use the personalisation we actually hold: first name, company, role, industry,
company context, a verified trigger, a researched observation, a supported
pain hypothesis.

    BAD    "Hey {x}, I saw you work at {y}..." repeated across thousands
    GOOD   verified context connected to WHY this email is relevant to them

**Never invent missing information.** Every variable used must have one of:

    reliable data coverage
    a safe fallback
    a rule preventing that variant from being used for that record

That third option is the one people forget, and it is often the right one.

Coverage must be MEASURED before a variable ships, not assumed. This is the
same discipline as the ICP rule: missing evidence is never positive evidence.

## 5. VARIANTS

At least five materially different variants per important position, where
attribution is measurable - and on EmailBison it IS, because a variant is a
first-class sequence step with its own id (`docs/BISON-PROVIDER-TRUTH-2026-09-14.md`).

    NOT AN EXPERIMENT     A "Hey John" / B "Hi John" / C "Hello John"
    AN EXPERIMENT         conversational / direct-operational / pain-led /
                          insight-led / concise-low-friction

Also vary greeting style, personalisation depth, subject style, body length,
question vs statement, CTA, when Productive is introduced, same-thread vs
fresh-thread positioning, and cadence spacing.

## 6. QA BEFORE ANY PROMOTION

Render REPRESENTATIVE LEADS - plural - through the same code path that builds
the provider payload, and verify every line:

    [ ] first name resolves
    [ ] no hardcoded names anywhere in the sequence
    [ ] company resolves where used
    [ ] every other variable resolves
    [ ] fallbacks work on a record MISSING each variable
    [ ] sender and signature correct, nothing invented
    [ ] Productive described correctly, no invented capability
    [ ] no unsupported claim about prospect, sender or relationship
    [ ] follow-ups are actually follow-ups (thread_reply True where intended)
    [ ] new subjects occur ONLY where designed
    [ ] each step has a distinct purpose
    [ ] the sequence reads naturally from email 1 to the close
    [ ] variants are materially different

`scripts/render_preview.py` renders through `bisonfactory`, the same path
that builds the real payload. A preview through a second path proves nothing.

**Then read the campaign back from EmailBison after writing it.** The
provider state, not our local payload, is the final truth. A 2xx is not
evidence. `scripts/heyreach_readback.py` is the model to copy.

## 7. WHAT MUST NOT HAPPEN

- No hardcoded name reaching more than one lead.
- No blank, `undefined` or `null` greeting.
- No invented sender, signature, capability, metric or history.
- No five-steps-that-are-one-step-five-times.
- No widening a quality gate to make copy pass. Regenerate the copy.
- No promotion on a 2xx without a readback.
- No variant performance claim where attribution is not measurable.

## 8. THE ORDER THIS RUNS IN

    LEARN -> GENERATE -> QA -> DRY RUN -> LIVE -> READBACK -> MEASURE
          -> IMPROVE -> SCALE

Delegate the bulk to Qwen: historical cadence and follow-up analysis,
variable coverage, greeting and signature analysis, copy and variant
generation, rendering QA, batch preparation. Claude reviews, rejects weak
work and decides what is safe to promote.
