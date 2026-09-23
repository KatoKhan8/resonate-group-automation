PRIORITY: P1
DEPENDS:

# TASK-258 — the shipped default ladders satisfy the threading invariant

**THE DECISION IS MADE. Do not re-open it.** Operator, Zvonimir, 2026-09-22:
*fix the default `email_five` ladder so it satisfies the threading invariant —
step 1 subject only, steps 2+ `thread_reply=true` — with a test that every
shipped default cadence builds a valid sequence; a new client must not inherit
the break.*

TASK-256 asked which of the ladder or the invariant was wrong and said to stop
rather than guess. That question is now answered: **the ladder is wrong, the
invariant stands.** This task changes the ladder. Nothing here weakens
`bisonfactory._sequence_steps`.

## The defect

    cadencelibrary.THREAD_REPLY_PATTERNS = {
        "email_five":  (False, True, False, True, False),
        "email_eight": (False, True, False, True, False, True, False, True),
    }

TASK-219's invariant (`4c9d63d3`, 2026-09-16) refuses a follow-up that is not
a thread reply and carries a subject different from the opener's. Steps 3 and
5 of `email_five` — and 3, 5, 7 of `email_eight` — are exactly that shape, so
**the shipped default cannot build a sequence whose follow-ups carry their own
subjects.** It is the system's own default configuration, refused by the
system's own guard.

### It has been worked around three times instead of fixed

This is the part that makes it worth a task rather than a one-line change.
Every caller that works today does so by *overriding* the default:

    config/clients/productive.yaml   thread_reply_pattern: [False, True, True]
    config/clients/demo.yaml         thread_reply_pattern: [False, True, True, True, True]
    tests/test_a_five_step_campaign_sends_five_different_emails.py
                                     thread_reply_pattern: [False, True, True, True, True]

and that last one says so in its own comment: *"the ladder's own default for
this cadence is (False, True, False, True, False), which would put steps 3 and
5 back in the shape the invariant forbids."* The break was known, named in a
comment, and routed around rather than repaired — which is why **a new client
added without an override inherits it**, and the first symptom is a campaign
that will not build.

## Do

1. **The patterns.** Opener false, every follow-up true:

        "email_five":  (False, True, True, True, True)
        "email_eight": (False, True, True, True, True, True, True, True)

2. **`tests/test_task081_thread_reply.py` asserts the OLD defaults** at lines
   ~40-48 — `assertEqual(pattern, (False, True, False, True, False))` and five
   per-ordinal assertions. Those are asserting the defect, not a contract.
   Update them to the new pattern and keep what they were really testing:
   that `thread_reply_for` reads the ladder, returns `None` past its end, and
   returns `None` for an unknown ladder. **Do not delete those tests.**

3. **THE TEST THE OPERATOR ASKED FOR, and it is the point of this task:**
   every shipped default cadence builds a valid sequence with NO client
   override. Drive it through the real path, not by re-checking the tuple:

   - for each entry in `cadencelibrary.SEQUENCES` (`productive_li_heavy_v1`,
     `productive_balanced_v1`, `productive_email_eight_v1`), build a sequence
     config whose every step carries its OWN distinct subject — the shape that
     trips the invariant — pass **no** `thread_reply_pattern`, and assert
     `bisonfactory._sequence_steps` accepts it.
   - assert the same for every key in `THREAD_REPLY_PATTERNS` directly, so a
     ladder added later without a sequence is still covered.

   Distinct subjects per step matter: with identical subjects the invariant is
   satisfied trivially and the test passes on a broken ladder. **A fixture
   that reuses the opener's subject everywhere proves nothing here.**

4. **A new client must not inherit the break.** A test that a client config
   with an `email_sequence` and **no** `thread_reply_pattern` key builds a
   valid sequence. That is the regression the operator named, and it is not
   covered today because both shipped clients override.

## Verify by breaking it

Restore one pattern to its alternating form and confirm the new tests go red —
and that they go red for the invariant's reason, not because a fixture fell
over. A test that passes on both the old and new patterns has tested nothing,
and that is easy to write here.

## Watch for

- **`purpose_with_thread` / `FOLLOWUP_ADDENDUM`.** Steps 3 and 5 become
  follow-ups, so they now receive the same-thread addendum telling the model
  it is continuing a conversation and must not re-introduce the sender. That
  is correct and intended — it is what those steps now are — but it changes
  generated copy, so check `tests/test_the_model_is_told_what_we_sell.py` and
  `tests/test_eight_step_cadence.py` and update any assertion that depended on
  step 3 being a cold open. **Do not remove the addendum to keep a test
  green.**
- **`config/clients/*.yaml` are NOT to be edited.** Their overrides become
  redundant once the default is right, but they are operator decisions about
  live copy and removing them is not this task. Leave them.
- **`src/bisonfactory.py` is NOT to be edited.** The invariant stands.
- Do not touch `src/providers/`, `config/.env`, `scripts/*_watch_loop.py` or
  `work/`.

## Relationship to TASK-256

TASK-256 fixes the ~28 stale test FIXTURES in `test_bison_campaign_write`,
`test_render_preview` and `test_task081_thread_reply`. **It depends on this
task and must not run beside it** — both touch `test_task081_thread_reply.py`
and both touch the threading shape. Land this one first; TASK-256 then has a
correct default to build fixtures against, and some of its 28 may already be
green.

## RESULT

- **STATUS:** DONE
- **COMMIT SHA:** 348980ce
- **TESTS:**
  - `tests.test_task081_thread_reply`: 26/26 pass (was 20, added 6 new)
  - `tests.test_eight_step_cadence`: 27/27 pass (updated 1 assertion for em5 addendum)
  - `tests.test_the_model_is_told_what_we_sell`: 15/15 pass (no changes needed)
  - `tests.test_a_five_step_campaign_sends_five_different_emails`: 24/24 pass
  - Total: 92/92 pass across all directly affected modules
  - Pre-existing failures in `test_bison_campaign_write` (11 errors) and
    `test_render_preview` (4 failures) confirmed NOT caused by this change
    (verified by stashing changes and re-running). These are TASK-256's domain.
- **FILES CHANGED:**
  - `src/cadencelibrary.py` — THREAD_REPLY_PATTERNS fixed: email_five
    (F,T,T,T,T), email_eight (F,T,T,T,T,T,T,T)
  - `tests/test_task081_thread_reply.py` — updated 5 assertions to new pattern;
    added ShippedDefaultsBuildValidSequences (4 tests) and
    NewClientNoOverride (2 tests)
  - `tests/test_eight_step_cadence.py` — em5 assertion updated to prefix-match
    (addendum now appended since em5 is a follow-up)
  - Task file moved TODO → RUNNING → DONE
- **FINDINGS:**
  - The `productive_email_eight_v1` sequence cannot be built through
    `_sequence_steps` because it has 8 email steps and `MAX_SEQUENCE_STEPS`
    is 6. This is a pre-existing provider limit, not a threading issue.
    The email_eight pattern is still asserted directly in
    `test_every_ladder_pattern_satisfies_invariant`.
  - Verified by breaking: restoring the old alternating pattern causes 4 of 6
    new tests to go red, all for the invariant's reason ("step N is not a
    thread reply but carries a distinct subject"). The tests discriminate.
  - `grep -rn "THREAD_REPLY_PATTERNS" src/` shows the constant is consumed by
    `_resolve_thread_pattern` in `bisonfactory.py` and `thread_reply_for` in
    `cadencelibrary.py` — both real production paths.
- **RISKS:**
  - Steps 3, 4, 5 of email_five (and 3-8 of email_eight) now receive the
    FOLLOWUP_ADDENDUM in their prompts, telling the model it is continuing
    a thread. This changes generated copy for those rungs. The addendum is
    correct — those steps ARE follow-ups now — but regeneration will produce
    different text.
  - Client config overrides (`config/clients/productive.yaml`,
    `config/clients/demo.yaml`) become redundant but are deliberately NOT
    removed (operator decisions about live copy, not this task's scope).
- **RECOMMENDED CLAUDE ACTION:**
  - Review and integrate.
  - TASK-256 can now proceed: it has a correct default to build fixtures
    against. Some of its 28 stale fixtures may already be green.
  - Consider regenerating copy for campaigns using email_five/email_eight
    ladders, since steps 3+ now carry the follow-up addendum.
