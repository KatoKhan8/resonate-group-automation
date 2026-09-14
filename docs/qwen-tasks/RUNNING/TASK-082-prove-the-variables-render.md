# TASK-082 - prove the variables render, on real leads, including the broken ones

## WHY

`docs/EMAILBISON-COPY-REQUIREMENTS.md` sections 2, 3, 4 and 6. The operator's
requirement is blunt and correct: none of these may ever reach a prospect.

    Hey ,        Hi undefined,      Hi null,

And no hardcoded name may ever reach more than one lead. HeyReach campaign
599020 carried "hi jacob" for a row naming fourteen people. The LinkedIn side
now refuses that (`heyreachfactory._refuse_cohort_names_in_graph`, TASK-042).
**EmailBison has no equivalent guarantee.**

## WHAT TO DO

### 1. Establish the syntax from the provider, not from a document

Measured on this estate 2026-09-14: 3,295 single-brace occurrences and ZERO
double-brace across 81 sequences. So a double-brace placeholder would reach a
prospect as literal text here. Confirm the real syntax before anything else -
`bison.LEAD_VARIABLES`, `bison.custom_variables()` and
`bison.ensure_custom_variables()` are where this lives.

Report the exact syntax with the response behind it.

### 2. Measure COVERAGE before trusting any variable

For each variable we might use - first name, company, role/title, industry,
company context, trigger, researched observation - report across the real
queue:

    variable          records with a usable value    coverage %

**Missing evidence is never positive evidence.** A variable at 40% coverage
is not a variable, it is a 60% chance of an empty slot. For each one say
which of the three applies:

    reliable coverage      safe fallback      exclude the record

That third option is the one people forget and is often right.

### 3. Render on REPRESENTATIVE LEADS, plural, including the broken ones

Through `scripts/render_preview.py`, which goes through `bisonfactory` - the
same path that builds the real provider payload. A preview through a second
path proves nothing.

Render at least ten leads, and they must INCLUDE:

    a lead with no first name
    a lead with no company
    a lead with a one-character or unusual name
    a lead whose name is lowercase or ALL CAPS
    a lead with a non-ASCII name

Then show the rendered greeting and signature for each. **A screenshot of the
happy path is not this task.** The broken records are the point.

### 4. Write the guard, do not just report the gap

A test that fails if a rendered email can contain an empty, `undefined` or
`null` greeting, and a test that fails if a cohort member's literal name
appears in shared campaign-level copy. `tests/test_no_literal_name_in_campaign_graph.py`
is the LinkedIn model - read it, and note it includes a
`DeletingTheCallMakesTheTestFail` class proving the guard is not inert. Do
the same here.

## THE SIGNATURE RULE

Sender identity comes from configuration. **Do not hallucinate a name, title,
company or phone number.** `clients.sender_identity()` exists and
`prompts/draft.md` now has a sender section. Verify the signature renders
from config and degrades safely when config is thin - saying what the sender
DOES rather than inventing who they are.

## WHAT YOU MAY NOT DO

- **READS ONLY at every provider.** No campaign write, no lead write, no send.
- Do not commit prospect PII. Redact real emails, names and domains in
  anything that lands in `docs/` - describe the SHAPE of a failure, not the
  person it happened to.
- Do not widen a gate to make a render pass.
- Do not approve anything.

## OUTPUT

`docs/BISON-RENDER-QA-2026-09-15.md` - the syntax, the coverage table, the
ten rendered leads with their greetings and signatures, and the list of every
way a render can currently go wrong.

## RESULT BLOCK

STATUS, COMMIT SHA, TESTS (exact commands, exact counts, exit codes read off
the process and never through a pipe), FILES CHANGED, FINDINGS (the coverage
table and the rendered failures), RISKS, RECOMMENDED CLAUDE ACTION.
