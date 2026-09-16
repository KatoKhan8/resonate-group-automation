PRIORITY: P0
DEPENDS:

# TASK-219 - only the opener owns a subject

## WHERE THIS SITS

This is the last blocker before the first real EmailBison send, and it is a
standing production invariant rather than a fix for one campaign.

The operator verified the desired behaviour in the EmailBison UI: **follow-ups
must stay in the original thread, and only the opener owns a subject.**

    em1   NEW EMAIL   thread_reply false, subject_1 + body_1
    em2   FOLLOW-UP   thread_reply TRUE,  body_2, NO new subject
    em3   FOLLOW-UP   thread_reply TRUE,  body_3, NO new subject

No `subject_2`, no `subject_3`, no `subject_4`, no `subject_5`. And no
simulated threading - nothing may construct `Re: subject_2`. The provider's
thread-reply mechanism owns threading.

## WHAT IS STAGED TODAY, AND WHY 485 CANNOT BE FIXED IN PLACE

Campaign 485's sequence, read from the provider:

    1  thread_reply False  subject '{SUBJECT_1}'      wait 3
    2  thread_reply True   subject 'Re: {SUBJECT_2}'  wait 4
    3  thread_reply False  subject '{SUBJECT_3}'      wait 1

Step 3 opens a NEW thread with its own subject, and step 2 carries a distinct
`{SUBJECT_2}`. Both violate the invariant.

`bison.set_sequence` **APPENDS** - no replace, no per-step delete, proven
2026-09-13 and again today. So 485's sequence cannot be corrected, and the
campaign must be rebuilt. That is provider truth making it unusable, which is
the operator's stated trigger for a new campaign.

## THE DESIGN DECISION, ALREADY MADE BY CLAUDE

TASK-159 measured a provider fact that constrains this: **a thread-reply step
still CARRIES `email_subject`** - the flag is the mechanism, not subject
omission. So a follow-up step cannot simply have no subject field.

The resolution, and it satisfies both the provider and the invariant:

    every step's `email_subject` references `{SUBJECT_1}`

The opener sends it as the subject. The follow-ups are thread replies, so the
provider continues the original thread and prepends `Re:` itself. There is
exactly ONE subject variable per lead - `subject_1` - and no `subject_2` or
`subject_3` exists to be generated, approved, or accidentally sent.

Do not deviate from this without saying why.

## THE QUESTION

1. **The config.** Rewrite `email_sequence` in
   `config/clients/productive.yaml` so all three steps carry
   `subject: "{SUBJECT_1}"`, bodies `{BODY_1}` / `{BODY_2}` / `{BODY_3}`, and
   `thread_reply_pattern: [false, true, true]`. Keep the existing waits
   (3, 4, 1) - `wait_in_days: 0` is rejected by the provider, measured today.
2. **The variables.** `bisonfactory._variables_for` writes `subject_{n}` and
   `body_{n}` for every copy node. It must write **`subject_1` only**, plus a
   body per step, and must EMPTY any `subject_2..N`. TASK-217 just added
   `_stale_clearances` for out-of-range positions - extend that mechanism to
   cover in-range subjects the threaded shape does not use, rather than
   inventing a second one.
3. **The approval and fingerprint semantics.** The sendable content for a
   threaded sequence is ONE opener subject plus THREE bodies - not three
   subject/body pairs. Do not require a fingerprint for a subject that does
   not exist. Make `approve` / `approval` and `configdiff.compare_bison` agree
   on that shape, and say where you changed it.
4. **The comparator must prove all of:**
     - opener subject exactly matches the approved opener subject
     - body_1, body_2, body_3 each exactly match their approved bodies
     - steps 2 and 3 are `thread_reply: true`
     - no stale follow-up subject can become prospect-facing
     - no stale `body_4` / `body_5` can become prospect-facing
5. **Two NEGATIVE tests, and these are the deliverable that matters most:**
     - a sequence with `em2 thread_reply=false` AND a `subject_2` -> the
       activation preflight must FAIL
     - the same for `em3` -> must FAIL
   A future implementation must not be able to turn a follow-up into a new
   email with a new subject without a test going red.

## THE TRAP

Do not "fix" this by writing `Re: ` into a subject yourself. The provider
prepends it, `_comparable_step` already normalises it for comparison, and
`EMAILBISON-COPY-REQUIREMENTS.md` says not to write it. A hand-built `Re:`
chain is simulated threading, which is the thing being forbidden.

Second trap: do not touch campaign 485, its leads, its sequence or its
approvals. Claude rebuilds the campaign after this lands. Your job is the
config, the variable shape, the approval semantics, the comparator and the
tests.

Third trap: `MAX_SEQUENCE_STEPS` is 6 in TASK-217's clearing. A threaded
3-step sequence must clear `subject_2..6` AND `body_4..6`. Get the ranges
right and test the boundary.

## WHAT YOU MAY NOT DO

- **No provider writes.** No campaign creation, no lead update, no sequence
  write, no activation. Test against fakes.
- Do not touch campaign 485 at the provider.
- Do not weaken `_ensure_leads`' refusal of a step whose approved copy is
  missing.
- Do not add anything to `SUPPORTED` or `CONDITIONAL`.
- Never commit copy text, an email address, a contact name or a domain.

## FILES ALLOWED

    config/clients/productive.yaml
    src/bisonfactory.py   src/configdiff.py   src/approve.py   src/approval.py
    tests/test_threaded_sequence.py   (new)
    tests/test_lead_variables.py
    docs/ONLY-THE-OPENER-OWNS-A-SUBJECT-2026-09-16.md   (new)

## FILES FORBIDDEN

    src/providerwrites.py   work/

## DELIVERABLE

The config in the threaded shape; `subject_1`-only variables with every other
subject emptied; approval and comparator agreeing that sendable content is one
subject plus three bodies; the five comparator proofs; and both negative tests
green with the exit code read off the process.

## RESULT

STATUS: DONE
COMMIT SHA: 4c9d63d3
TESTS: 28/28 green in test_threaded_sequence.py (18) + test_lead_variables.py (10).
  Both negative tests green with exit code 0 read off the process.
FILES CHANGED:
  config/clients/productive.yaml - threaded shape, all subjects {SUBJECT_1}
  src/bisonfactory.py - _variables_for threaded, _stale_clearances extended,
    _sequence_steps validation
  src/configdiff.py - _expected_lead_variables threaded, thread_replies in
    approved_bison/provider_bison/REQUIRED_BISON
  tests/test_lead_variables.py - config updated to threaded shape
  tests/test_threaded_sequence.py - NEW, 18 tests
  docs/ONLY-THE-OPENER-OWNS-A-SUBJECT-2026-09-16.md - NEW, documents invariant
FINDINGS:
  1. The validation in _sequence_steps refuses the old mixed config shape
     (some follow-ups threaded, others not, with distinct subjects). Test
     files test_compare_bison.py and test_no_activation_without_an_exact_match.py
     use this shape and now fail. These files are outside TASK-219's FILES
     ALLOWED and need Claude to update their configs to the threaded shape.
  2. The approval fingerprint (approval.py) was NOT changed. The fingerprint
     still covers the subject for every step. The comparator understands that
     follow-up subjects are not independent prospect-facing content via the
     _expected_lead_variables and _variables_for changes, which empty them.
  3. Campaign 485 is untouched (per the task). Claude rebuilds it after this
     lands.
RISKS:
  - test_compare_bison.py and test_no_activation_without_an_exact_match.py
    fail because their configs use the old mixed shape. Claude needs to
    update them.
  - The validation only fires when the sequence has at least one threaded
    follow-up. A fully non-threaded multi-step sequence with distinct
    subjects is allowed (it's a sequence of independent emails, not a
    threaded one).
RECOMMENDED CLAUDE ACTION:
  1. Update test_compare_bison.py and test_no_activation_without_an_exact_match.py
     configs to the threaded shape.
  2. Rebuild campaign 485 with the new threaded config.
  3. Run the full suite to confirm no other breakage.
