# The next cohort is not waiting for copy. It is waiting for evidence.

2026-09-17. One live generation run, one record, and the result was worth it.

## The hypothesis

`scripts/verification_inventory.py` says 68 contacts are SENDABLE. Only 53 of
them carry any cadence. **Fifteen sendable contacts have no copy written at
all** - TASK-197's "fifteen records that never had copy written", confirmed
against live state.

Generating for them looked like the one lever available while P1 waits on an
operator signature: it costs no credits, needs no approval to run, and would
grow the approvable pool. So the account gate was checked first, which is the
lesson `docs/SEVENTEEN-AND-ONE-SIGNATURE-2026-09-17.md` records - nine
LinkedIn contacts were once queued for copy generation that would have
unblocked nobody, because they were account-blocked as well.

    15 records with a sendable contact and no cadence
     6 ALLOW      three with no prior contact at the account at all
     5 HOLD       ended early, or an address bounced
     4 STOP       mid-sequence, or somebody there has replied

Six genuinely clean, genuinely new accounts. That would take the operator's
approvable set from 17 to 23.

## What actually happened

`py -3 -m src.generate --client productive --live --id <one of the six>`

    GENERATED: 1 record(s), model=openai-compatible
      <record> state=held
        nothing to generate

The record came back **`held`, `hold_class: RETRYABLE`, `hold_reason:
generation:evidence_not_traceable`**. And the important detail is WHERE in the
run that happened: the hold is raised from an `llm.ModelError` handler
(`generate.py:1869-1876`). **The model was called. The words came back. They
were refused because a claim in them could not be traced to evidence this
record holds.** The spend happened and then the record was held.

## Why that is the finding rather than a setback

All six carry `evidence: 0`. They hold research rows - 0, 2, 4, 4, 4, 5 - but
research is not evidence, and the claims gate is not satisfied by prose
somebody fetched. The handoff's own scale measurement said it plainly and
nobody had connected it to this: **4 of 550 records carry any evidence at
all.**

So the pipeline's real shape for these people is not

    verified contact -> generate -> approve -> READY

but

    verified contact -> COMPANY EVIDENCE -> generate -> lint -> claims
                     -> approve -> READY

and the missing link is the one nobody is working on. A broad generation batch
across the six - or across the fifteen, or across the 66 review records -
would have spent a model call per step and then held every evidence-poor
record, with `state: held` written into canonical state as though the company
were the problem.

**One record's cost bought the reason not to spend fifty.**

## What this does NOT license

It does not license relaxing the claims gate. A message may only claim what
the event log supports, and a draft that asserts something about a company
nobody can trace is exactly what the gate is for. `ACCOUNT-OUTREACH.md` says
it and `approve` enforces it.

It does not license a broad evidence purchase either. TASK-199 priced Grok
evidence at about $0.20 a domain and TASK-183 measured $0.55 a verdict on the
review records; either is a real spend that has to be justified by conversion,
and today's conversion is limited by seventeen unsigned approvals rather than
by inventory.

## The order that follows from it

1. **The seventeen.** Still the only thing that converts anybody this week.
2. **Then evidence, measured on a handful** - not copy, and not verification.
   The six ALLOW records are the natural test: they are account-clean, their
   contacts are already verified, and evidence is the single gate between them
   and a draft. Price it on two before deciding on six.
3. The record held by this run is `RETRYABLE` and `holdreasons.
   can_return_to_queue` exists to release it once the condition is gone.
   Nothing was lost.
