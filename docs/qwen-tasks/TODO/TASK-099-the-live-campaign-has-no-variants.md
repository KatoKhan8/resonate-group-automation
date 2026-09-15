PRIORITY: P0
DEPENDS: 

# TASK-099 - the live campaign holds one message per node

## THE FACT, READ FROM THE PROVIDER

`docs/state/PROVIDER-CAMPAIGNS.json`, 2026-09-15:

    nodes carrying copy        8   (7 MESSAGE + 1 CONNECTION_REQUEST)
    messages per node          1   on every single one

The five-variant machinery TASK-084 and TASK-087 have been repairing **has
never reached campaign 599020.** Whatever the generator can produce now, the
provider holds one arm per step.

## THE QUESTION

What exactly stands between the generator's variant output and a HeyReach
sequence node carrying more than one message?

Answer in this order and report WHICH it is:

1. **Does the HeyReach sequence schema even accept multiple messages per
   node?** `payload.messages` is a LIST, which suggests yes. Prove it from the
   provider's own shape or from an existing campaign in the estate that has
   more than one - 83 campaigns are available to look at. If NO campaign in
   the entire account has a multi-message node, that is a strong finding and
   possibly the answer.
2. **Does `heyreachfactory` build multi-message nodes?** Trace the path from
   `variantgen` output to the payload. Existence is not function: find where a
   variant list would have to become `payload.messages` and prove whether
   anything does it.
3. **Does the write path carry them?** `heyreach.set_sequence` IS in
   `providerwrites.SUPPORTED`. Does the validation in
   `validate_sequence_for_write` accept or refuse a multi-message node?

## WHAT NOT TO DO

- **Do not write to the provider.** This task ends at a diagnosis and a test.
  The rewrite of 599020's sequence is Claude's and needs the human read first.
- Do not "fix" it by generating five copies of one message. TASK-087 measured
  that and the diversity check correctly refuses it.

## DELIVERABLE

The diagnosis with evidence, plus a FAILING test that pins the desired
behaviour (a node built from N variants carries N messages) so the fix is
verifiable. If the provider cannot carry variants per node at all, say so -
that would mean variants must be expressed as separate campaigns or separate
sequences, which is an architectural finding worth more than any code.

## RULES THAT APPLY TO THIS TASK

- Reads only at both providers. No POST/PATCH/PUT/DELETE, no sends, no
  campaign creation or activation, no adding leads.
- **A zero and a wrong lookup are indistinguishable from the outside.** If you
  measure zero of something, prove you read the right field first. Industry
  and headcount were reported at 0% three separate times by a reader looking
  at `sizing`, which is null everywhere, instead of `company_facts`.
- Say what you SAMPLED. `per_page` is accepted and IGNORED on every EmailBison
  route - you get 15 rows whatever you ask for - and offset pagination is
  refused past ~500 pages. A number without its page budget is not
  reproducible.
- Never use `meta.total` as a sent count. Campaign 274 reports 30,411
  scheduled rows and zero of its first 100 pages are sent. Count rows WHERE
  `sent_at` IS PRESENT.
- **Do not quote 8.49%** - unreproduced. **Do not quote any open rate** -
  `open_tracking` is False estate-wide, which is an ABSENT MEASUREMENT and not
  a zero. **Do not count an UNKNOWN as negative** - 53.4% of unknowns are
  correctly unknown.
- INTERESTED may NOT carry a learning claim: 0.44 precision on the old pattern
  set, and the new set is UNMEASURED, which is not the same as good.
  MEETING_INTENT (1.00) and OBJECTION (1.00) may, with recall stated.
- Never weaken, widen or disable a gate, a lint rule or a sender limit to make
  something pass or to gain volume. Fix what produced the bad output.
- Read every test exit code OFF THE PROCESS, never through a pipe.
- No unhashed PII in any tracked file or commit message - no real names,
  domains, emails, profile URLs or reply text. A seat holder is a real person
  too; Claude leaked one yesterday and the guard caught it.
- Separate OBSERVATIONS (with n), HYPOTHESES, and PROVEN LEARNINGS. Leave
  PROVEN LEARNINGS empty if nothing survives a sample-size objection. TASK-059
  left it empty and was right to.
