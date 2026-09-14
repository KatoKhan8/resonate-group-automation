# EmailBison Render QA - 2026-09-15

TASK-082. Proof that the variables render, on edge-case leads, including the
broken ones. Rendered through `scripts/render_preview.py email_edge_cases`
which goes through `bisonfactory._approved_copy` and
`bisonfactory._variables_for` - the SAME code path that builds the real
provider payload.

## 1. VARIABLE SYNTAX - CONFIRMED FROM THE PROVIDER

**Single-brace only.** Measured on this estate 2026-09-14: 3,295 single-brace
occurrences and ZERO double-brace across 81 sequences.

    {SUBJECT_1}    {BODY_1}     {SUBJECT_2}    {BODY_2}    ...
    {record_id}    {contact_key}    {client}

`bison.LEAD_VARIABLES` declares the names. `bison.ensure_custom_variables`
creates them on the workspace. The provider resolves them against per-lead
custom variables at send time.

**A double-brace placeholder would reach a prospect as literal text.**
`{{first_name}}` is NOT recognised by EmailBison. The provider does not error
on an unrecognised variable - it sends the literal text.

**The greeting is NOT a provider-side variable.** EmailBison does NOT have a
`{first_name}` merge variable. The greeting ("Hey John,") is part of the
generated body text that travels as `{BODY_N}`. The generator writes the
greeting into the body, and it travels as a custom variable. If the generator
produces "Hey ," or "Hi undefined," that goes straight to the provider and
out the door.

## 2. COVERAGE TABLE

**The work/ directory does not exist in this worktree.** Coverage cannot be
measured against the real queue here. This is a FINDING: the coverage
measurement must be done on the production worktree (Claude's) where
work/queue.jsonl exists.

The variables we might use and their expected coverage based on the record
structure:

| Variable | Expected Coverage | Classification |
|----------|------------------|----------------|
| first_name | High - required by bisonfactory._plan() | **reliable coverage** - the plan refuses contacts with no name |
| company | Medium - some records have domain-only company | **safe fallback** - the body text can omit company references |
| role/title | Medium - not all records carry it | **safe fallback** - use sparingly, never as the only personalisation |
| industry | Low - company_facts may be empty | **exclude the record** or use a generic fallback |
| company context | Low - requires company_facts | **exclude the record** if facts are missing |
| trigger | Very low - requires research | **exclude the record** - never invent |
| researched observation | Very low - requires research | **exclude the record** - never invent |

**Missing evidence is never positive evidence.** A variable at 40% coverage
is not a variable, it is a 60% chance of an empty slot.

## 3. RENDERED LEADS - EDGE CASES

12 leads rendered through the bisonfactory pipeline. Each shows the greeting
(first line of body), the signature (last lines), and any issues detected.

### Lead 1: Elena Vasquez (happy path)
- **Company:** Northbridge Consulting
- **First name:** 'Elena'
- **Greeting:** `Elena, I work with consulting teams on real-time project visibility...`
- **Signature:** Best, / Alex Chen / Founder, Resonate Group
- **Status:** OK

### Lead 2: (NO NAME) - empty name field
- **Company:** Ashford Digital
- **First name:** '' (empty)
- **Greeting:** `Hey , I work with agency teams on project visibility...`
- **Signature:** Best, / Alex Chen / Founder, Resonate Group
- **Status:** !!! EMPTY GREETING - greeting has no name after it
- **Note:** bisonfactory._plan() refuses this at staging time. The render
  preview shows what the body text looks like if it were to pass.

### Lead 3: Sam Okafor - no company
- **Company:** keystone-partners.example.com (domain string, not a name)
- **First name:** 'Sam'
- **Greeting:** `Sam, I work with operations teams on project visibility...`
- **Signature:** Best, / Alex Chen / Founder, Resonate Group
- **Status:** OK - greeting renders correctly without company reference

### Lead 4: X Li - one-character name
- **Company:** Bastion Digital
- **First name:** 'X'
- **Greeting:** `X, I work with digital agencies on project visibility...`
- **Signature:** Best, / Alex Chen / Founder, Resonate Group
- **Status:** OK - single-character name renders correctly

### Lead 5: jane doe - lowercase name
- **Company:** Meridian Logistics
- **First name:** 'jane'
- **Greeting:** `jane, I work with logistics teams on real-time visibility...`
- **Signature:** Best, / Alex Chen / Founder, Resonate Group
- **Status:** OK - preserves the case from the record (lowercase)

### Lead 6: JOHN SMITH - ALL CAPS name
- **Company:** Cascadia Design
- **First name:** 'JOHN'
- **Greeting:** `JOHN, I work with design studios on resourcing visibility...`
- **Signature:** Best, / Alex Chen / Founder, Resonate Group
- **Status:** OK - preserves the case from the record (ALL CAPS)

### Lead 7: Zoë Müller - non-ASCII name
- **Company:** Zürich Digital
- **First name:** 'Zoë'
- **Greeting:** `Zoë, I work with software teams on project visibility...`
- **Signature:** Best, / Alex Chen / Founder, Resonate Group
- **Status:** OK - Unicode renders correctly

### Lead 8: Maria Garcia - "Hi undefined," greeting
- **Company:** Pinnacle Partners
- **First name:** 'Maria'
- **Greeting:** `Hi undefined, I work with consulting teams on project visibility.`
- **Signature:** Best, / Alex Chen / Founder, Resonate Group
- **Status:** !!! LITERAL UNDEFINED - greeting contains 'undefined' instead of a name

### Lead 9: Chen Wei - "Hi null," greeting
- **Company:** Vertex Solutions
- **First name:** 'Chen'
- **Greeting:** `Hi null, I noticed Vertex Solutions and thought this might be relevant.`
- **Signature:** Best, / Alex Chen / Founder, Resonate Group
- **Status:** !!! LITERAL NULL - greeting contains 'null' instead of a name

### Lead 10: Rachel Okafor - planted name (hi-jacob class)
- **Company:** Keystone Partners
- **First name:** 'Rachel'
- **Greeting:** `Declan, I work with consulting teams on project visibility...`
- **Signature:** Best, / Alex Chen / Founder, Resonate Group
- **Status:** !!! PLANTED NAME - body contains name 'Declan' from another contact
- **Note:** This is the hi-jacob defect class for email. Rachel's body text
  names Declan, who is another contact in the same cohort. Every contact
  would receive copy addressing them as Declan.

### Lead 11: Declan Murphy - correct copy for the planted-name record
- **Company:** Keystone Partners
- **First name:** 'Declan'
- **Greeting:** `Declan, I work with consulting teams on project visibility...`
- **Signature:** Best, / Alex Chen / Founder, Resonate Group
- **Status:** OK - Declan's own copy correctly addresses him as Declan

### Lead 12: Priya Sharma - missing sender in signature
- **Company:** Summit Group
- **First name:** 'Priya'
- **Greeting:** `Priya, I work with technology teams on project visibility.`
- **Signature:** (no sender name - body ends without a signature block)
- **Status:** !!! SENDER MISSING - signature does not contain the configured sender name

## 4. EVERY WAY A RENDER CAN GO WRONG

### Greeting failures
1. **Empty greeting:** "Hey ," "Hi ," "Hello ," - the name is missing
2. **Literal undefined:** "Hi undefined," - JavaScript null representation
3. **Literal null:** "Hi null," - Java/JSON null representation
4. **Literal None:** "Hi None," - Python null representation
5. **Wrong name:** "Declan," in Rachel's email - the hi-jacob defect class

### Signature failures
6. **Missing sender:** no name, role or company in the signature
7. **Invented sender:** a name, title or company not in the config
8. **Invented capability:** "as a fellow founder" when the sender is not

### Variable failures
9. **Empty merge field:** {BODY_N} resolves to empty string - email with no body
10. **Double-brace syntax:** {{first_name}} reaches prospect as literal text
11. **Unresolved variable:** provider sends the literal "{VARIABLE_NAME}"

### Cohort failures
12. **Planted name:** one contact's copy contains another contact's name
13. **Hardcoded company:** copy names one company but goes to the whole cohort
14. **Duplicate text:** two steps render identically - prospect reads same sentence twice

## 5. THE GUARD

`bisonfactory._refuse_bad_greetings(plan)` checks three classes of defect:

1. Empty greeting: regex `^(Hey|Hi|Hello)\s*,` on the first line
2. Literal placeholder: "undefined", "null", "None" in the first line
3. Planted cohort name: word-boundary match of another contact's first name

**Wired into the production path.** Called by `_ensure_leads` on every
`stage()` invocation. Deleting the call makes the test fail - that is the
wiring proof. See `tests/test_emailbison_no_empty_greeting.py` and its
`DeletingTheCallMakesTheTestFail` class.

**16 tests, all passing.** Including:
- Empty greeting refuses (Hey, Hi, Hello)
- Literal placeholder refuses (undefined, null, None)
- Planted name refuses (hi-jacob class)
- Word boundary prevents false positives ("al" in "already")
- Single-char name excluded from cohort check
- Clean plan passes all checks
- Wiring proof: deleting the call lets bad input through

## 6. SIGNATURE

Sender identity comes from `clients.sender_identity(config)`. It reads the
`sender:` block in the client config:

    sender:
      name: Alex Chen
      role: Founder
      company: Resonate Group
      works_on: project profitability for agencies

**Do not hallucinate a sender name, title, company or phone number.** An
invented sender is a claim about us the record cannot support. If the config
has no sender block, the signature degrades: say what the sender does (from
the product block), never emit an empty slot, never invent a name.

## 7. WHAT MUST BE DONE ON THE PRODUCTION WORKTREE

1. **Measure coverage** against work/queue.jsonl. Report the actual
   percentages for first_name, company, role, industry, company_facts.
2. **Render real leads** through `scripts/render_preview.py email_edge_cases`
   on the production worktree where the real queue exists.
3. **Read back from the provider** after staging. The provider state, not
   the local payload, is the final truth.

## 8. FILES CHANGED

- `scripts/render_preview.py` - edge-case fixtures and rendering function
- `src/bisonfactory.py` - `_refuse_bad_greetings()` guard
- `tests/test_emailbison_no_empty_greeting.py` - 16 tests

## 9. RESULT BLOCK

    STATUS: DONE
    COMMIT SHA: 158a662
    TESTS: py -3 -m unittest tests.test_emailbison_no_empty_greeting -v
           16 tests, all pass, exit code 0
           py -3 -m unittest tests.test_the_emailbison_write_door_is_enforced -v
           19 tests, all pass, exit code 0
    FILES CHANGED:
      scripts/render_preview.py - edge-case fixtures and rendering
      src/bisonfactory.py - _refuse_bad_greetings() guard
      tests/test_emailbison_no_empty_greeting.py - 16 tests
      docs/BISON-RENDER-QA-2026-09-15.md - this document
    FINDINGS:
      - Variable syntax: single-brace only, confirmed from provider
      - Greeting is NOT a provider-side variable - it's baked into body text
      - work/ does not exist in this worktree - coverage cannot be measured
      - 12 edge-case leads rendered, 5 issues detected (empty greeting,
        undefined, null, planted name, missing sender)
      - Guard wired into _ensure_leads, called on every stage() invocation
      - 16 tests including DeletingTheCallMakesTheTestFail
    RISKS:
      - Coverage not measured against real queue (work/ absent here)
      - Generator could still produce bad greetings if the prompt is wrong
      - The guard checks the first line only - a broken greeting in the
        middle of the body would not be caught
    RECOMMENDED CLAUDE ACTION:
      1. Measure coverage on production worktree where work/ exists
      2. Render real leads through the edge-case fixture
      3. Read back from provider after staging
      4. Consider extending the guard to check the full body, not just
         the first line

---

## CLAUDE ADDITIONS - THE COVERAGE TABLE, AND WHAT THE PROVIDER REALLY OFFERS

TASK-082 could not measure coverage: `work/` is gitignored and its worktree
had no queue. Measured here against real production state, over the **92
contacts on not-dropped records** - the population a campaign can actually
draw from:

    variable          present  coverage   verdict
    first name             92      100%   reliable
    title/role             92      100%   reliable
    company                92      100%   reliable
    domain                 92      100%   reliable
    industry               92      100%   reliable
    headcount              92      100%   reliable
    persona                92      100%   reliable
    email                  87       94%   SAFE FALLBACK REQUIRED
    angle                  81       88%   SAFE FALLBACK REQUIRED
    specialties            68       73%   SAFE FALLBACK REQUIRED
    employee_range         18       19%   EXCLUDE THE RECORD

A first pass reported industry and headcount at 0% and was WRONG - it read
`sizing`, which is null on every record, where the data actually lives in
`company_facts.employees` and `company_facts.industry`. Anyone re-running
this should check the path before believing a zero. A 0% and a wrong lookup
look identical from the outside.

`employee_range` at 19% is the clearest case of the rule in
`EMAILBISON-COPY-REQUIREMENTS.md` section 4: it does not get a fallback, it
gets a rule excluding the record from any variant that uses it. Four out of
five leads have nothing to put there.

### THE PROVIDER FACT THAT CHANGES THE GREETING QUESTION

Read from the live API, `bison.custom_variables()`:

    body, body_1..body_6, client, contact_key, headline, industry, location,
    provider_account_id, record_id, sender_account_id, sender_id,
    subject, subject_1..subject_3

**There is no `first_name` and no `company` merge variable.** The whole email
body - greeting included - travels to the provider as `body_N`.

So the greeting cannot be delegated to EmailBison. There is no provider-side
substitution to get the syntax right for, and no provider-side fallback to
lean on. **"Hey ," is baked in at generation time and goes straight out the
door**, which is precisely why `bisonfactory._refuse_bad_greetings` has to
exist and has to run before the write rather than after it.

It also means the personalisation the operator asked for - industry, role,
company context - is not a matter of inserting a variable. It is a matter of
the generator being GIVEN those values and writing them into the body. The
coverage table above is what it may be given.

`headline`, `industry` and `location` DO exist as provider custom variables
and are the exception - those three can travel as fields.
