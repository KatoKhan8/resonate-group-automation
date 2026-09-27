PRIORITY: P0
SIZE: L
DEPENDS: TASK-400, TASK-364, TASK-372

# TASK-425 — the one-account dry run, proved by a causal matrix

**This is the only milestone that matters after 400, 364 and 372 pass GLM
verification.** Operator, 2026-09-27. It does not start before all three PASS.
It ends with a STOP: the artifact goes to the operator and nobody proceeds to ten
accounts without their decision.

**ACCEPTANCE RESTATED AND FIXED BY THE OPERATOR — Zvonimir, 2026-09-27 evening.**
Recorded in full in `docs/OPERATING-MODE.md` under "TASK-425 ACCEPTANCE"; the four
criteria are the causal matrix (A original, B one fact changed, C persona switched,
D evidence removed — each stating EXPECTED change against OBSERVED diff, where an
unexpected change or no change is a BLOCK); the signature chain end to end with an
empty signature a BLOCK; offer sequencing as step objectives enforced by
`sequencegate` WITH a negative test; and a per-message audit artifact. Provider
writes = 0 throughout.

**These criteria are now frozen.** A change to any of them is one of the few things
that must stop this path and go back to the operator as a decision — per the
operator's execution rule of the same evening, a NEW decision that materially
changes safety, prospect-facing behaviour, licensed claims, provider state,
approval semantics or these acceptance criteria stops ONLY the affected path and is
asked in `#resonate-os`. Narrowing them to make the run pass is not a decision, it
is the failure this task exists to prevent.

## THE ACCOUNT

One safe Productive account, a **fixture built from real structure**, with two to
three decision makers. **No PII is committed.** Do not copy a real person's name,
email address or phone number into a committed file; build the fixture to match
the SHAPE of a real record, not its contents. The company may be a real public
domain; the people may not be real people.

The company is researched once and the research is reused across every run in the
matrix, so a difference between runs is caused by the variable under test and not
by a fresh crawl returning something different.

## THE PATH, THROUGH `src/generate.py`

account, Second Brain, verified facts, persona, the approved Offer A or B,
campaign strategy, the five skills, the email sequence and the LinkedIn sequence,
copylint, sequencegate, ONE canonical SequencePlan, the EmailBison projection, the
HeyReach projection, the approval projection, suppression, client-aware spend,
provider-ready. **Provider writes = 0.**

Offers A v2 and B v2 are APPROVED (Zvonimir, 2026-09-27), so the real path runs
without the dry-run stamp. Keep the stamped dry-run path working and covered:
approval can be withdrawn, and the stamp is what stops a pending-offer artifact
from reaching a provider.

## ACCEPTANCE 1 — THE CAUSAL TEST MATRIX

Four runs on the SAME account, everything else held constant. Each run states the
EXPECTED change BEFORE the run, then the OBSERVED diff. **An unexpected change is
a BLOCK, and so is no change where one was expected.**

    A   original                          the baseline artifact
    B   one fact or signal changed        angle AND copy must change
    C   persona economic buyer -> operations
                                          selected offer must change A -> B and
                                          the capabilities must change with it
    D   a key piece of evidence removed   the claim disappears, or the lead HOLDs

D is the one that catches a fabricating pipeline: if the claim survives the removal
of the evidence that licensed it, the grounding is decorative and this is a BLOCK
no matter how good the copy reads.

This matrix is the whole point. A slice that produces beautiful copy but where
changing an input changes nothing downstream means the intelligence layer is not
controlling generation, and that is a BLOCK.

## ACCEPTANCE 2 — THE SIGNATURE CHAIN, P0.5

Before any ten-account run, prove the chain end to end:

    mailbox owner -> sender_signature -> the rendered final message in the
    provider projection

**An empty signature is a BLOCK, not a warning.** This is a standing launch
blocker: 155 email steps render empty because no mailbox has a stored signature.
The proof required is the signature visible in the rendered message inside the
provider projection, not a populated field somewhere upstream.

## ACCEPTANCE 3 — THE AUDIT ARTIFACT

One artifact. **Per message** it shows, explicitly labelled:

    PRIMARY PROBLEM
    SELECTED OFFER
    WHY THIS OFFER
    SELECTED CORE CAPABILITIES
    AI CAPABILITY USED            yes / no
    IF YES, WHICH ONE
    IF YES, WHY IT WAS RELEVANT   to this problem and this angle
    SOURCE / PROVENANCE
    EXACT CLAIM LICENSED
    WHERE IT APPEARED IN COPY

Plus, for the run as a whole: the facts used each with its source, the campaign
strategy and its step objectives, the full email copy, the full LinkedIn copy,
copylint results, sequencegate results, the SequencePlan, both provider
projections, suppression, spend, and provider writes (which must read 0).

## THE MESSAGING RULE IS PART OF THE ACCEPTANCE

`messaging_rules` in `config/clients/productive-offers.yaml` is currently marked
`DATA_ONLY_NOT_YET_ENFORCED`. This task wires it and proves it:

- At most ONE AI capability per prospect-facing message. Assert it.
- AI is never the offer and never invents the problem. The audit artifact's
  "WHY IT WAS RELEVANT" line is the evidence, and a message whose AI capability
  cannot be justified against the selected problem fails.
- No AI capability is forced: a message with none is valid and must not be
  penalised.
- `sequencegate` reads `step_objectives` and refuses a sequence whose steps do not
  follow the offer's spine (A: margin visibility, quote versus burn, resource
  decisions, mechanism, reframe and close. B: project visibility, time,
  resourcing, mechanism, one operational view).
- Every claim traces to stored page text. `evidence.productive_ai` has page text
  and is quotable; all twelve customer stories have `page_text: null` and are NOT.
  No case study, customer name, figure or percentage appears anywhere.
- No dashes in any prospect-facing text.

## WHAT THIS TASK MAY NOT DO

- **Provider writes = 0.** No send, activate, resume, enrol, attach, or
  provider-changing test. The freeze stands and needs the operator's explicit
  APPROVED to lift.
- Do not proceed to ten accounts. Stop at one, post the artifact, wait.
- Do not approve or modify an offer.
- Do not loosen copylint, sequencegate, grounding, suppression or the offer gate
  to make a run pass. A refusal is a finding.
- No new features: no CRM, no Unipile, no new database, no dashboard, no
  unrelated backlog.

## HANDOFF

Post the artifact for the operator: what it knew, what it concluded, which offer
and why, which strategy, what it wrote and why, and the evidence behind it. Then
STOP. The operator decides on ten.
