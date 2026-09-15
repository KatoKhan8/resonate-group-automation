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

---

## DIAGNOSIS

### Question 1: Does the HeyReach sequence schema accept multiple messages per node?

**YES.** `payload.messages` is a list and every layer of the write/read path
handles it as one:

- `_copy()` at `heyreach.py:1045` builds `{"messages": list(entries)}` - it
  passes through whatever list it receives, no length constraint.
- `_check_words()` at `heyreach.py:786` iterates over ALL entries in the list
  and validates each one individually (type, non-empty, correct shape for
  MESSAGE vs INMAIL).
- `_fingerprint()` at `heyreach.py:1663` captures ALL texts in the list for
  readback comparison, so a multi-message write would be verified on every
  arm.
- The comment at `heyreach.py:1053-1057` states the design intent explicitly:
  *"messages is a LIST on the wire, which is where COPY-EXPERIMENTS.md's five
  variants per step land: the provider rotates them itself."*

**What was sampled:** The `provider_truth.py` script measured sequence shape
for the one Resonate campaign (599020) and found all 8 copy-carrying nodes
have exactly 1 message each. The other 82 campaigns in the account were
counted by status but their sequences were NOT individually examined for
messages-per-node. The 1,194 nodes measured on 2026-09-13 were counted by
type (227 MESSAGE, 15 INMAIL) but not by arm count. So it is NOT proven
whether any campaign in the entire account has ever carried a multi-message
node - but the schema accepts it and nothing in the readback path would
drop arms.

### Question 2: Does `heyreachfactory` build multi-message nodes?

**NO. This is the bottleneck.**

`assemble_linkedin_copy()` at `heyreachfactory.py:229` always builds:

    copy[role] = {"messages": [text], "fallbackMessage": text}

where `text` is a SINGLE resolved variant. The path:

1. `cadence.variant_for()` returns ONE variant per contact (deterministic
   hash assignment from `variants.resolve()`).
2. `variants.apply_to_step()` applies that one variant's words to the step.
3. `_step_copy()` extracts the single text.
4. The text goes into a single-element list.

The variants ARE generated (by `generate_variants` in `generate.py:1559`)
and stored on the step spec under the `variants` key. The factory DOES read
them. But it resolves ONE per contact and puts only that one in the messages
list. The five variants never become five messages on the node.

The design documents say the provider should rotate (the comment at
heyreach.py:1053, TASK-022's result block), but the implementation assigns
per-contact instead. Both mechanisms were in the design space; the code
chose per-contact assignment and then never also put all variants in the
list for provider-side rotation.

### Question 3: Does the write path carry them?

**YES, it would.** There is no validation that refuses a multi-message node:

- `validate_sequence_for_write()` at `heyreach.py:818` iterates over all
  entries via `_check_words()` and validates each.
- `set_sequence()` at `heyreach.py:1611` calls `validate_sequence_for_write`
  then writes via `/campaign/UpdateSequence`.
- `sequence_matches()` at `heyreach.py:1720` fingerprints ALL texts in the
  list for readback comparison.

The write path is ready. The factory never gives it more than one message
to write.

### ROOT CAUSE

The gap is in `heyreachfactory.assemble_linkedin_copy()`, lines 201-229.
When a step spec carries variants, the code resolves ONE variant per contact
(the correct thing for attribution) and writes that one variant's text into
a single-element `messages` list. What it should ALSO do is collect every
approved variant's text into the list so the provider can rotate them.

The two mechanisms are not mutually exclusive:
- Per-contact assignment: which variant THIS person got (for attribution).
- Provider rotation: all variants in the list (for the experiment).

The code does the first and stops there.

## RESULT

STATUS: done (diagnosis complete, failing test pins the fix)
COMMIT SHA: 146b4d7
TESTS: 3 new tests in tests/test_variant_reaches_provider_node.py.
  2 FAIL (the desired behaviour), 1 passes (baseline unchanged).
  63 related existing tests all pass (heyreachfactory, five_subject_variants,
  no_literal_name, no_branch_repeats).
FILES CHANGED:
  tests/test_variant_reaches_provider_node.py - new failing test file
FINDINGS:
  - The HeyReach schema accepts multiple messages per node. The write path
    validates, writes and reads back all of them. Nothing refuses.
  - The factory resolves one variant per contact and writes a single-element
    list. This is the ONLY bottleneck.
  - The comment at heyreach.py:1053 explicitly documents that variants should
    land in the messages list for provider rotation. The code does not do it.
  - provider_truth.py only examined Resonate campaigns' sequences in detail.
    The 82 other campaigns' arm counts are unknown.
  - The per-contact assignment (for attribution) and provider rotation (for
    the experiment) are complementary, not competing. The fix adds the
    rotation without removing the assignment.
RISKS:
  - The fix changes what goes on the wire. A campaign that currently sends
    one message per node will send N. The readback comparison in
    sequence_matches must verify all N survive the round-trip.
  - The fallbackMessage field is a single string, not a list. If the
    provider rotates messages, what is the fallback? This needs clarification
    before the fix ships to production.
RECOMMENDED CLAUDE ACTION:
  Fix assemble_linkedin_copy to collect all approved variants into the
  messages list when a step carries variants. Keep the per-contact
  variant_id recording for attribution. Verify the fix against the failing
  tests, then re-run provider_truth to confirm 599020's sequence accepts
  multi-message nodes (dry run first, no write without human approval).
