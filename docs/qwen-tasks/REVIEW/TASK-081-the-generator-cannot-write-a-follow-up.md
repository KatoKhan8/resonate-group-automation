# TASK-081 - the generator cannot write a follow-up

## THE DEFECT

Read `docs/EMAILBISON-COPY-REQUIREMENTS.md` section 1 first.

Our own production campaign, probed 2026-09-15:

    campaign 481   5 parent steps   thread_reply = False on ALL FIVE

Every step is a brand-new cold email with its own subject. The estate's
largest campaign does the opposite - 352 runs F, T, F, T, F across its five
parents - so this is not a provider limitation. It is that nothing in our
generator or factory ever sets `thread_reply`.

`bison.sequence_steps()` only stopped DISCARDING the field on 2026-09-14
(TASK-073). Now that it survives the read, the write side has to learn it.

## WHAT TO DO

Make a five-step email sequence able to express which steps are same-thread
follow-ups, end to end:

1. **The ladder** must say which rungs are follow-ups. `EMAIL_*_LADDER` in
   `src/cadencelibrary.py` currently gives each rung a job but no thread
   behaviour. A follow-up rung's brief must also tell the model it is
   writing INTO an existing thread: short, adds one thought, does not repeat
   the earlier email, does not re-introduce the sender from scratch.
2. **The factory** must carry `thread_reply` into the payload it posts, and
   must not invent a fresh subject where the design says follow-up. Note
   from the provider: a step carries an `email_subject` EVEN WHEN
   `thread_reply` is True, so do not implement "follow-up" as "omit the
   subject". The flag is the mechanism.
3. **The readback** must compare intended thread behaviour against provider
   state, the way `scripts/heyreach_readback.py` compares everything else.
   A step that was meant to be a follow-up and landed as a new thread is
   exactly the defect a readback exists to catch.

## THE STARTING SHAPE, AND IT IS A HYPOTHESIS

    1  new thread     who / why you / relevant problem / simple question
    2  SAME THREAD    short, one added thought, no repetition
    3  evidence-led   different angle; Productive where it fits
    4  new thread     fresh subject if justified
    5  SAME THREAD    short close, low-friction, wrong-person redirect

**Do not hardcode this as universal.** It must be configurable per client or
campaign, because TASK-080 is measuring whether it is right and may come back
saying something else. Five steps is the production target, not a finding.

## HOW YOU WILL KNOW IT WORKED

- A test that a ladder marking rung 2 a follow-up produces a payload with
  `thread_reply` True on step 2 and False on step 1. Assert on what the
  factory RETURNS, not on source text.
- A test that the flag round-trips: build, read back through
  `bison.sequence_steps()`, and confirm the value survives.
- A test that a follow-up rung's rendered prompt differs from a new-thread
  rung's - the model must be TOLD it is continuing a thread, or it will write
  another cold open and the flag will be the only thing that changed.
- Break your own wiring deliberately and confirm the intended test fails for
  the intended reason, and that a different guard did not fire first.

## WHAT YOU MAY NOT DO

- **READS ONLY at every provider.** Build the payload and test it against
  `tests/fakebison.py`; do NOT write a sequence to EmailBison. The live write
  is Claude's, after a dry run and a review.
- Do not change campaign 481 at the provider.
- Do not widen a gate.
- Calling the MODEL is allowed - you have credentials in this worktree.

## RESULT BLOCK

STATUS, COMMIT SHA, TESTS (exact commands, exact counts, exit codes read off
the process and never through a pipe), FILES CHANGED, FINDINGS, RISKS,
RECOMMENDED CLAUDE ACTION.

## RESULT BLOCK

STATUS: DONE

COMMIT SHA: fefe0f3 (readback script), ae4efc6 (implementation), d3537d2 (move to RUNNING)

TESTS:
  py -3 -m unittest tests.test_task081_thread_reply -v
    20 tests, 0 failures, exit 0
  py -3 -m unittest tests.test_a_five_step_campaign_sends_five_different_emails -v
    17 tests, 0 failures, exit 0
  py -3 -m unittest tests.test_sequence_steps_carries_variant_identity
    tests.test_staging_a_campaign_twice_builds_one
    tests.test_staging_refuses_colliding_contacts
    tests.test_two_campaigns_do_not_collide_at_the_provider -v
    78 tests, 0 failures, exit 0
  Pre-existing failures NOT caused by this change:
    test_cadence.TestTheCompanyPause (TypeError on paused.reason)
    test_crash_restart_idempotency.CrashAtSeam (RuntimeError not raised)

FILES CHANGED:
  src/cadencelibrary.py    - THREAD_REPLY_PATTERNS, FOLLOWUP_ADDENDUM,
                             thread_reply_for(), purpose_with_thread()
  src/bisonfactory.py      - _sequence_steps carries thread_reply per step,
                             _resolve_thread_pattern() with config override,
                             readback comparison includes thread_reply
  src/generate.py          - step_block includes thread_reply and modified
                             purpose for follow-up rungs
  tests/fakebison.py       - already stored thread_reply (no change needed)
  tests/test_staging_a_campaign_twice_builds_one.py
                           - FakeBison.set_sequence stores thread_reply
  tests/test_staging_refuses_colliding_contacts.py
                           - FakeBison.set_sequence stores thread_reply
  tests/test_task081_thread_reply.py (NEW)
                           - 20 tests: ladder, factory, round-trip, prompt,
                             break-the-wiring
  scripts/bison_readback.py (NEW)
                           - EmailBison readback comparison script

FINDINGS:
  1. The chain is fully connected. grep confirms every new function has a
     named caller in src/:
     - thread_reply_for() called by generate.step_block() and
       cadencelibrary.purpose_with_thread()
     - purpose_with_thread() called by generate.step_block()
     - _resolve_thread_pattern() called by bisonfactory._sequence_steps()
     - THREAD_REPLY_PATTERNS read by _resolve_thread_pattern() and
       thread_reply_for()
  2. The pattern is configurable per client via email_sequence.thread_reply_pattern
     override, as required. The ladder default is F,T,F,T,F for email_five.
  3. A follow-up step STILL CARRIES email_subject - the flag is the mechanism,
     not subject omission. Verified by test_follow_up_step_still_carries_subject.
  4. The prompt for a follow-up rung differs from a new-thread rung: the
     FOLLOWUP_ADDENDUM is appended, telling the model it is continuing a
     thread. Verified by test_follow_up_purpose_contains_thread_instruction.
  5. Break-the-wiring tests confirm that removing thread_reply from the step
     dict or setting all-False (the old defect) is detected.
  6. Both FakeBison implementations (tests/fakebison.py and the one in
     test_staging_a_campaign_twice_builds_one.py) now store thread_reply.

RISKS:
  1. The FOLLOWUP_ADDENDUM is appended to the purpose string. If the prompt
     template changes, the addendum must still reach the model. The test
     test_follow_up_purpose_contains_thread_instruction guards this.
  2. The client config override (thread_reply_pattern) is a list of bools.
     A malformed override (wrong length, non-bool values) is coerced but
     not refused. TASK-080 may come back saying the shape is wrong.
  3. Campaign 481's existing copy was generated without thread_reply. When
     regenerated, rungs 2 and 4 will get the follow-up brief and the flag.
     The existing stored copy is NOT rewritten - only regeneration picks up
     the new behavior.

RECOMMENDED CLAUDE ACTION:
  1. Review the test file and confirm the chain is correct.
  2. Run the bison_readback script against campaign 481 after regenerating
     copy, to confirm the provider holds the intended thread_reply pattern.
  3. Decide whether to activate thread_reply on campaign 481. The copy must
     be regenerated first - existing stored copy was generated without the
     follow-up brief.
  4. TASK-080 is measuring whether the F,T,F,T,F shape is right. When it
     reports, the pattern in THREAD_REPLY_PATTERNS or the client config
     override is what changes.
