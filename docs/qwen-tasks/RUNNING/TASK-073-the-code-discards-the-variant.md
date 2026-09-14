# TASK-073 - the provider carries the variant and the code throws it away

## THE DEFECT

TASK-069 established, and Claude re-probed and confirmed, that EmailBison
models a message variant as a first-class sequence step:

    campaign 352   44 sequence steps
                   39 carry variant=True
                   each carries variant_from_step naming its parent
                   44 of 44 ids are distinct

So variant identity survives a send and a readback. Five variants per
position is measurable AT THE PROVIDER, which is a much better answer than
the Resonate-owned experiment ledger that was designed as a fallback.

**And `bison.sequence_steps()` trims `variant`, `variant_from_step` and
`thread_reply` out of the row before anything downstream sees them.**

This is the repository's recurring defect in its purest form: a thing
computed correctly by the provider that nothing downstream can read. Not a
provider gap. A code gap, three field names wide.

## WHAT TO DO

Preserve those three fields through the trimmer. `CLAUDE.md` says provider
modules return trimmed dicts and never raw payloads, so this is a widening
of the trim list by three named fields - NOT a switch to returning the raw
payload. Keep the module's contract.

Then prove the fields are CONSUMED, because existence is not function:

1. A test that `sequence_steps()` returns them, asserting on what the
   function RETURNS against a realistic fixture - not on the text of the
   source.
2. Trace who reads the result. If a caller drops them one layer up, that is
   part of this defect and part of this fix.
3. A test that a variant step is DISTINGUISHABLE from its parent by what
   the function returns - id, variant flag and parent, together.

## THE FIXTURE MUST BE REAL IN SHAPE

Campaign 352's real shape, PII removed:

    {id: 4035, order: 1,    variant: False, variant_from_step: None}
    {id: 4036, order: None, variant: True,  variant_from_step: 4035}
    {id: 4037, order: 2,    variant: False, variant_from_step: None}
    {id: 4038, order: None, variant: True,  variant_from_step: 4037}
    {id: 4039, order: None, variant: True,  variant_from_step: 4037}

Note `order` is None on a variant and set on a parent. A variant is not a
position in the sequence; it is an alternative AT a position. Any code that
sorts steps by `order` will put every variant in one undefined heap, and
that is worth checking while you are in here.

## WHAT YOU MAY NOT DO

- **READS ONLY at every provider.** No campaign write, no sequence write.
- Do not build an experiment ledger. D came back verdict 1, so the provider
  already carries the identity and a second store of the same truth is
  exactly what `CLAUDE.md` refuses.
- Do not change any other field in the trim list.

## RESULT BLOCK

STATUS, COMMIT SHA, TESTS (run the NEIGHBOURS of what you changed, not only
your own new tests), FILES CHANGED, FINDINGS, RISKS, RECOMMENDED CLAUDE
ACTION.
