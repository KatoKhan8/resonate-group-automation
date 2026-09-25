PRIORITY: P0
SIZE: M
DEPENDS:

# TASK-314 — find exactly where the HeyReach steps are lost, and pin it

Operator directive, `docs/OPERATOR-DIRECTIVES-2026-09-25.md` section 4.

## The claim to test

A previous measurement found ONE LinkedIn step surfacing from a SIX-step
graph. `cadence.expand_step` drops a generated step whose copy was never
written, and under `productive_li_heavy_v1` li2..li6 are all `generated`.
`li1` survived only because it names the `linkedin_intro` template.

**Measured 2026-09-14 on `ogpartner-dk`: six notes stored on the record, one
step surfaced.** Confirm whether that is still true today.

## Trace the whole path, and say where the loss happens

    campaign config -> cadence graph -> LinkedIn message generation ->
    provider mapping -> HeyReach API payload -> provider response ->
    campaign preview

At each hop, count the steps in and the steps out. **The finding is the hop
where the count drops**, named by file and function.

Check connection request, follow-ups, ordering, delays, sender assignment,
personalisation variables, message bodies, provider step types, unsupported
operations, and preview consistency.

**A 200 from the provider does not prove the steps were configured.** Read the
campaign back and count what it holds.

## The regression test is the deliverable

A test that **fails when a configured step is silently omitted**. Not a test
that the graph has six entries; a test that six entries in produce six steps
out, and that a step with no copy is REFUSED rather than dropped.

Prove it fails: break it deliberately, show the failure, restore it.

## Rules

- **Do not modify any active HeyReach campaign.** Read only.
- Do not reduce the number of LinkedIn steps.
- Use the operator's own test campaign if a live read is needed; 620829 and
  613744 are ours. Never a client campaign.
- Report LIVE VALIDATION REQUIRED for anything you could not verify.

## Acceptance

    py -3 -m unittest tests.test_no_cadence_step_is_silently_dropped

plus: the hop where steps are lost, named by file and function, or evidence
that no loss occurs today. Commit, push, report the remote SHA and URL.
