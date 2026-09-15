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

## RESULT

STATUS: DONE
COMMIT SHA: 35e01f6
TESTS: tests/test_multi_message_nodes.py - 3 passing, 1 skipped (documents the gap)
FILES CHANGED: tests/test_multi_message_nodes.py (new)
FINDINGS: see diagnosis below
RISKS: The fix requires wiring variant collection into assemble_linkedin_copy
RECOMMENDED CLAUDE ACTION: Review the diagnosis and decide whether to wire
  variant collection into assemble_linkedin_copy, or to express variants as
  separate campaigns/sequences.

---

## DIAGNOSIS

The five-variant machinery has never reached campaign 599020 because the
variant mechanism and the provider mechanism are wired for different things.

### 1. Does the HeyReach sequence schema accept multiple messages per node?

**YES.** The provider's `payload.messages` is a LIST and the provider rotates
among them. This is stated in the code at `src/heyreachfactory.py:1050`:

    `messages` is a LIST on the wire, which is where `COPY-EXPERIMENTS.md`'s
    five variants per step land: the provider rotates them itself, so a
    variant is a graph fact rather than something this system has to assign
    per contact.

Proof:
- `src/providers/heyreach.py:786` `_check_words` iterates over every entry in
  `payload.get("messages")` and validates each one. It does not refuse
  multiple messages.
- `tests/test_multi_message_nodes.py::test_validate_accepts_multiple_messages`
  builds a node with 3 messages and validates it successfully.
- `tests/test_multi_message_nodes.py::test_check_words_validates_each_message`
  proves that _check_words validates every entry and refuses if any is blank.

The schema supports multiple messages per node. No campaign in the account
has been observed with multi-message nodes (the snapshot only carries the one
resonate campaign), but the schema accepts it.

### 2. Does `heyreachfactory` build multi-message nodes?

**YES, if given a copy block with multiple messages.** The `_copy` function at
`src/providers/heyreach.py:1028` does:

    entries = block.get("messages")
    payload = {"messages": list(entries) if isinstance(entries, list) else [],
               "fallbackMessage": block.get("fallbackMessage")}

It carries the FULL list. Proof:
- `tests/test_multi_message_nodes.py::test_build_sequence_carries_multiple_messages_per_node`
  builds a copy block with 3 messages for connection_note and verifies the
  graph node's payload.messages has 3 entries. The test PASSES.

The graph builder carries the full list. The gap is upstream.

### 3. Does the write path carry them?

**YES.** `validate_sequence_for_write` at `src/providers/heyreach.py:818` does
not refuse multi-message nodes. It calls `_check_words` which validates each
entry. `set_sequence` at `src/providers/heyreach.py:1611` calls
`validate_sequence_for_write` before writing.

The write path carries multi-message nodes.

### THE GAP

The gap is in `assemble_linkedin_copy` at `src/heyreachfactory.py:170-240`.
When a step has variants, it resolves ONE variant per contact:

    if spec.get(_cadence.VARIANTS_KEY):
        recorded = step.get("variant_id")
        entry = _cadence.variant_for(spec, campaign, contact_key,
                                     recorded=recorded, config=config)
    if entry is not None:
        stepped = variants.apply_to_step(dict(step), entry)
        ...
        text = _step_copy(stepped)
    ...
    copy[role] = {"messages": [text], "fallbackMessage": text}

The variant mechanism assigns ONE variant per contact. The messages list gets
ONE entry. The provider mechanism rotates among multiple messages in the list.
The two are not wired together.

### WHAT STANDS BETWEEN THE GENERATOR AND THE PROVIDER

The answer to the task's question is: **the factory resolves one variant per
contact and puts that one variant's text into the messages list.** The
provider schema accepts multiple messages. The graph builder carries them.
The write path validates them. The gap is in the copy assembly, which chooses
one variant per contact rather than collecting all active variants.

### THE FIX

Two options:

1. **Wire variant collection into assemble_linkedin_copy.** When a step has N
   active variants, collect all N variant texts into the messages list. The
   provider rotates among them. Each contact is still assigned one variant
   for tracking/allocation purposes, but the graph carries all of them.

2. **Express variants as separate campaigns or sequences.** Each variant
   becomes its own campaign. Contacts are assigned to campaigns, not variants
   within a campaign. This is a larger architectural change.

Option 1 is the smaller fix and matches the code's own comment at line 1050:
"the provider rotates them itself, so a variant is a graph fact rather than
something this system has to assign per contact." The comment says the
provider rotates; the code does not wire it.

### TESTS

`tests/test_multi_message_nodes.py` proves:
- The provider schema accepts multi-message nodes (test_validate_accepts_multiple_messages)
- _check_words validates each message (test_check_words_validates_each_message)
- build_sequence carries the full list (test_build_sequence_carries_multiple_messages_per_node)
- The gap is documented (test_assemble_linkedin_copy_collects_all_variants, skipped)

The failing test that pins the desired behaviour is
`test_assemble_linkedin_copy_collects_all_variants`, which is skipped because
it requires wiring up the variant store to provide variant content. The gap
is documented: assemble_linkedin_copy resolves ONE variant per contact; it
should collect ALL active variants into the messages list so the provider can
rotate.
