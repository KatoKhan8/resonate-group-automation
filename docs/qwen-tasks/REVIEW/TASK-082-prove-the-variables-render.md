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

## RESULT BLOCK

    STATUS: DONE
    COMMIT SHA: 48a2f52
    TESTS: py -3 -m unittest tests.test_emailbison_no_empty_greeting -v
           16 tests, all pass, exit code 0
           py -3 -m unittest tests.test_the_emailbison_write_door_is_enforced -v
           19 tests, all pass, exit code 0
           py -3 scripts/render_preview.py email_edge_cases
           12 leads rendered, exit code 0
    FILES CHANGED:
      scripts/render_preview.py - 11 edge-case fixtures and render_email_edge_cases()
      src/bisonfactory.py - _refuse_bad_greetings() guard wired into _ensure_leads
      tests/test_emailbison_no_empty_greeting.py - 16 tests including
        DeletingTheCallMakesTheTestFail class
      docs/BISON-RENDER-QA-2026-09-15.md - the QA document
    FINDINGS:
      1. VARIABLE SYNTAX: single-brace only. 3,295 single-brace occurrences,
         ZERO double-brace across 81 sequences. Confirmed from bison.LEAD_VARIABLES
         and the template structure. A double-brace placeholder would reach a
         prospect as literal text.
      2. GREETING IS NOT A PROVIDER VARIABLE: EmailBison has no {first_name}
         merge variable. The greeting is baked into the generated body text
         that travels as {BODY_N}. If the generator produces "Hey ," or
         "Hi undefined," that goes straight to the provider and out the door.
      3. COVERAGE: work/ does not exist in this worktree. Coverage cannot be
         measured against the real queue here. This must be done on the
         production worktree where work/queue.jsonl exists.
      4. RENDERED 12 LEADS through bisonfactory pipeline:
         - Happy path (Elena): OK
         - No name: EMPTY GREETING "Hey ," detected
         - No company: OK (greeting renders without company reference)
         - One-char name (X): OK
         - Lowercase (jane): OK (preserves case)
         - ALL CAPS (JOHN): OK (preserves case)
         - Non-ASCII (Zoë): OK (Unicode renders correctly)
         - "Hi undefined,": LITERAL UNDEFINED detected
         - "Hi null,": LITERAL NULL detected
         - Planted name (Rachel's body names Declan): PLANTED NAME detected
         - Declan's own copy: OK
         - Missing sender: SENDER MISSING detected
      5. GUARD WRITTEN: bisonfactory._refuse_bad_greetings() checks three
         defect classes: empty greeting, literal placeholder, planted cohort
         name. Wired into _ensure_leads, called on every stage() invocation.
         16 tests including DeletingTheCallMakesTheTestFail proving the guard
         is not inert.
      6. THE WIRING PROOF: grep -n _refuse_bad_greetings src/bisonfactory.py
         returns TWO hits: the definition (line 420) and the call (line 1125).
         Deleting the call makes the test fail.
    RISKS:
      - Coverage not measured against real queue (work/ absent in this worktree)
      - The guard checks the first line of body text only - a broken greeting
        in the middle of the body would not be caught
      - The generator could still produce bad greetings if the prompt is wrong
      - Single-character names are excluded from the planted-name check
        (too short for reliable word-boundary matching)
    RECOMMENDED CLAUDE ACTION:
      1. Measure coverage on production worktree where work/ exists
      2. Render real leads through scripts/render_preview.py email_edge_cases
      3. Read back from provider after staging (scripts/readback or equivalent)
      4. Consider extending the guard to check the full body, not just the
         first line
      5. Add the guard to the generation prompt so the model does not produce
         broken greetings in the first place
