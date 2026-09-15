PRIORITY: P0
DEPENDS:

# TASK-148 - the email sequence, built to the contract rather than to taste

## THE CONTRACT COMES FIRST

`EMAILBISON-COPY-REQUIREMENTS.md` is standing and outranks anything you
conclude. It already settles what would otherwise be the interesting
questions:

    a sequence is ONE CONVERSATION
    same-thread follow-ups use the provider's thread_reply rather than a new
      subject on every step
    no name is ever hardcoded
    no greeting may render empty

**Do not re-litigate those.** Read it, then build to it.

The operator has added, for this campaign specifically:

    natural greeting - "Hey {{first_name}}" where appropriate
    a sender signature at the end
    real variables, verified against what the provider actually accepts
    not every step gets a new subject
    multiple meaningful variants for testing
    the validated fallback stays CONTROL; generated copy runs as CHALLENGER

## WHAT THIS TASK PRODUCES

A sequence SPECIFICATION, complete enough that Claude can write it to the
provider without making a single copy decision afterwards. Not a campaign -
Claude creates campaigns.

### 1. The step graph

How many steps, what each one is FOR, and the delay between them. Each step
must make a different argument. `PRODUCTION-SCALE-POLICY.md` and the operator
both name the shape:

    INTRO / CONTEXT -> PROBLEM -> PRODUCT / RELEVANCE -> FOLLOW-UP
      -> CLOSE / EASY OUT

Not the same question five times. Three human reads on the LinkedIn side all
returned DOES NOT BEAT FALLBACKS, and TASK-136 found the reason: every
sequence walked one six-beat arc while the fallbacks each had a different
shape. **Phrase-level variety cannot fix a sameness that lives in the shape.**
That finding is about LinkedIn and it is exactly as true here.

### 2. Which steps thread, and how

State, per step, whether it opens a thread or replies in one, and name the
FIELD that carries it. `docs/BISON-ATTRIBUTION-BOUNDARY-2026-09-15.md` and
`docs/BISON-API-ROUTE-EVIDENCE-2026-09-15.md` already establish the route
inventory - read them rather than re-probing.

A follow-up in the same thread does not get a new subject. Say what the
subject field must contain for a thread reply, verified rather than assumed.

### 3. Variables, verified

List every variable the sequence uses and prove the provider accepts it.
A variable that renders empty is a defect - `{{first_name}}` on a lead with no
first name produces "Hey ," which is worse than no greeting.

For each variable: where the value comes from in our record, what happens when
it is missing, and the fallback. **A greeting that can render empty fails the
standing contract.**

### 4. CONTROL and CHALLENGERS

CONTROL is the validated fallback copy. Find it - the client config carries
the LinkedIn fallbacks under `linkedin_sequence.fallbacks`; say what the email
equivalent is and whether it exists. If there is no validated email fallback,
that is a finding and CONTROL has to be defined before anything ships.

CHALLENGERS are variants that differ in ANGLE, TONE, STRUCTURE, HOOK and CTA -
not synonyms. TASK-141 established that EmailBison carries variant identity
durably: a scheduled email points at the VARIANT step's id, so a variant
experiment is readable afterwards. Design the arms so that finding is usable.

Say how many variants per step the provider supports, from the evidence
already recorded, and how a lead is assigned to one.

### 5. Senders

Multiple inboxes where capacity safely allows. State the allocation rule and
where the capacity number comes from. **Do not raise a configured limit to
make a number work** - the sender estate is never made to carry more by
raising a limit.

## WHAT YOU MAY NOT DO

- No provider writes. No campaign creation, no sequence write, no send.
- Do not weaken or widen a lint, claims or quality rule to let copy through.
- Do not write to `work/`.
- Do not run generation against the real queue.

## FILES ALLOWED

    docs/BISON-SEQUENCE-SPEC-2026-09-15.md   (new)
    scripts/task148_*.py
    the task file itself

## FILES FORBIDDEN

    src/    work/    config/

## DELIVERABLE

The step graph with each step's purpose and delay, the threading decision per
step with its field, the verified variable list with empty-render behaviour,
the CONTROL definition (or the finding that none exists), the challenger arms
with what actually differs between them, and the sender allocation rule.

## RESULT BLOCK

    STATUS: DONE
    COMMIT SHA: 6a8a9d1
    TESTS: No code changes. Specification document only.
    FILES CHANGED:
      docs/BISON-SEQUENCE-SPEC-2026-09-15.md — new, the full specification
    FINDINGS:
      1. NO EMAIL CONTROL EXISTS. The client config declares
         linkedin_sequence.fallbacks (the validated CONTROL for LinkedIn,
         survived three human reads) but has no email_sequence.fallbacks.
         Generated email copy has no validated baseline to beat. Until
         CONTROL is defined, a "winner" among challengers is uncontrolled.
         Three options: (a) operator writes email fallbacks, (b) LinkedIn
         fallbacks are adapted for email — they already make the same
         five-beat arc, (c) first generated campaign wrongly treated as
         CONTROL.
      2. The greeting is NOT a provider-side variable. EmailBison has no
         {FIRST_NAME} merge field. The entire body including greeting
         travels as {BODY_N}. A broken greeting goes straight to the
         prospect. The pre-write guard (_refuse_bad_greetings) is the
         only protection.
      3. The F,T,F,T,F threading pattern is a design choice, not
         evidence-backed. The estate has no control group for same-thread
         vs new-thread at any position.
      4. Same-thread follow-ups that got replies are LONGER (857 chars)
         than new-thread emails (571 chars). "Be short on follow-ups" is
         not supported by the reply data.
      5. The provider auto-prepends "Re:" on all 153 same-thread
         follow-ups. Do not write "Re:" in templates.
      6. 225 EmailBison inboxes exist, all Connected, currently idle.
         Email throughput is not the constraint — approval and copy
         quality are.
      7. employee_range coverage is 19% — exclude the record from any
         variant that uses it, do not fallback.
      8. Variable coverage must be measured on the production worktree
         where work/queue.jsonl exists. This worktree has no work/.
    RISKS:
      - Without email CONTROL, a "winner" among challengers has no
        baseline and the experiment is uncontrolled
      - The greeting is baked into body text with no provider-side
        safety net; the pre-write guard is the only protection
      - 225 inboxes with unprovable ownership
    RECOMMENDED CLAUDE ACTION:
      1. Define email CONTROL — adapt LinkedIn fallbacks or write new ones
      2. Measure variable coverage on production worktree
      3. Create the campaign (Claude creates campaigns, not Qwen)
      4. Stage, read back, promote within the established gates
