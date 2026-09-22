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
