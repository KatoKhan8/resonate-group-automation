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
