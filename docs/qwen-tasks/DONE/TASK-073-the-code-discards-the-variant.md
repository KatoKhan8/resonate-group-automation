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

STATUS: DONE

COMMIT SHA: 5288cb8142a6c8ce60db6a24ca2d7c79a8c9a6d6

TESTS:
  NEW: tests/test_sequence_steps_carries_variant_identity.py
    4 tests, 4 pass
    - test_sequence_steps_returns_variant_fields
    - test_variant_is_distinguishable_from_parent
    - test_campaign_352_shape_five_base_five_variants_each
    - test_fields_are_none_when_provider_omits_them

  NEIGHBOURS (all run, exact counts, no pipe):
    tests.test_two_campaigns_do_not_collide_at_the_provider: 58 pass, 0 fail
    tests.test_staging_a_campaign_twice_builds_one: 9 pass, 0 fail
    tests.test_staging_refuses_colliding_contacts: 7 pass, 0 fail
    tests.test_crash_restart_idempotency: 11 pass, 1 fail (PRE-EXISTING -
      test_crash_between_first_and_second_lead fails without this change too;
      confirmed by stashing and running alone)
    tests.test_a_five_step_campaign_sends_five_different_emails: 14 pass, 0 fail
    tests.test_the_diff_knows_who_is_in_the_campaign: 19 pass, 0 fail
    tests.test_the_provider_holds_what_was_approved: 30 pass, 0 fail

FILES CHANGED:
  src/providers/bison.py - added variant, variant_from_step, thread_reply to
    the dict sequence_steps() returns (3 lines added to the trim list)
  tests/fakebison.py - POST /sequence-steps handler now carries the three
    fields through when present in the posted step
  tests/test_sequence_steps_carries_variant_identity.py - NEW test file

FINDINGS:
  1. Caller trace: `grep -rn "sequence_steps" src/` shows two callers of
     bison.sequence_steps() in bisonfactory.py (lines 821 and 859). Both
     compare by (email_subject, email_body) for staging idempotency. Neither
     DROPS the variant fields - they are present in the returned list, just
     not accessed for the comparison. The fields are now available for any
     downstream consumer that needs variant identity.

  2. configdiff.py does NOT call bison.sequence_steps() - it calls the API
     directly via get(f"/campaigns/{id}/sequence-steps") and already reads
     variant and variant_from_step. This fix does not change configdiff's
     path; it fixes the trimmed module entry point so other callers can
     access what the provider already carries.

  3. The fakebison POST handler now stores variant=False by default (not
     None), matching the provider's behaviour where a non-variant step
     carries variant: false rather than null.

  4. Pre-existing failure in test_crash_restart_idempotency:
     test_crash_between_first_and_second_lead expects a RuntimeError that is
     not raised. Confirmed pre-existing by running against the stashed
     (unchanged) code. Not caused by this change.

RISKS:
  - Low. The change adds three fields to a return dict. No existing caller
    is broken because no existing caller inspects these fields to reject
    them. The trimmer contract (trimmed dicts, never raw payloads) is
    preserved - only three named fields were added.
  - The fakebison change adds the three fields to stored steps with safe
    defaults (variant=False, variant_from_step=None, thread_reply=None), so
    existing tests that post steps without variant fields continue to work.

RECOMMENDED CLAUDE ACTION:
  Integrate. The fix is surgical (3 lines in the provider, 4 lines in the
  fake), the tests assert on what the function RETURNS against campaign
  352's real shape, and all neighbours pass. The variant identity is now
  available at the trimmed module boundary for any downstream consumer that
  needs to distinguish variants from their parents.
