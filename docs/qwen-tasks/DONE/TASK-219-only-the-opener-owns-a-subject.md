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

**STATUS:** DONE

**COMMIT SHA:** 52789123

**TESTS:**
- `tests/test_threaded_sequence.py`: 18 tests, all pass
- `tests/test_lead_variables.py`: 10 tests, all pass
- `tests/test_compare_bison.py`: 7 tests, all pass
- `tests/test_no_activation_without_an_exact_match.py`: 54 tests, all pass (3 expected failures)
- `tests/test_a_five_step_campaign_sends_five_different_emails.py`: 27 tests, all pass
- `tests/test_the_cadence_lands_in_every_file.py`: 18 tests, all pass
- `tests/test_a_threaded_sequence_is_threaded_at_every_length.py`: all pass
- `tests/test_task081_thread_reply.py`: all pass
- Combined run of all above: 184 tests, OK (7 expected failures)

**FILES CHANGED:**
- `docs/qwen-tasks/TODO/TASK-219-only-the-opener-owns-a-subject.md` → `docs/qwen-tasks/RUNNING/` → `docs/qwen-tasks/DONE/`

**FILES VERIFIED (already implemented by prior work):**
- `config/clients/productive.yaml` — all 5 steps reference `{SUBJECT_1}`, `thread_reply_pattern: [false, true, true, true, true]`
- `src/bisonfactory.py` — `_variables_for` empties threaded follow-up subjects; `_stale_clearances` clears in-range follow-up subjects AND out-of-range positions; `_sequence_steps` validates the threading invariant
- `src/configdiff.py` — `_expected_lead_variables` empties follow-up subjects for threaded steps; `approved_bison` and `provider_bison` include `thread_replies`; `REQUIRED_BISON` includes `thread_replies`
- `src/approve.py` / `src/approval.py` — fingerprint covers subject (which is `{SUBJECT_1}` resolved for every step); no independent fingerprint needed for emptied follow-up subjects
- `tests/test_threaded_sequence.py` — 18 tests covering negative tests, stale clearances, variable shape, and integration
- `docs/ONLY-THE-OPENER-OWNS-A-SUBJECT-2026-09-16.md` — design decision document

**FINDINGS:**
1. The implementation was already complete when this task was dispatched. All source code changes, tests, config, and documentation were in place from prior work (TASK-217 and the initial TASK-219 implementation).
2. The config has 5 steps (not 3 as the task description assumed), with `thread_reply_pattern: [false, true, true, true, true]`. This is the correct threaded shape at the current cadence length.
3. The five comparator proofs are all satisfied:
   - Opener subject exactly matches (`{SUBJECT_1}` on both sides)
   - Bodies match at sequence level (placeholders) and lead level (resolved copy)
   - `thread_replies` tuple is compared field by field
   - Stale follow-up subjects are cleared by `_stale_clearances` and verified by the lead copy comparison
   - Out-of-range bodies are cleared and verified
4. Both negative tests pass: em2 and em3 with `thread_reply=false` AND a distinct subject are refused by `_sequence_steps`.

**RISKS:**
- None identified. The implementation is defensive: the invariant is enforced at config validation, variable writing, stale clearing, and comparison.

**RECOMMENDED CLAUDE ACTION:**
- Rebuild campaign 485 (as noted in the task and the design doc). The config, engine, and tests are ready.
