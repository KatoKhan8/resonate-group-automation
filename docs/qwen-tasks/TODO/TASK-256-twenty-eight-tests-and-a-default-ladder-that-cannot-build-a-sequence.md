PRIORITY: P1
DEPENDS:

# TASK-256 — 28 tests against the threading invariant, and the default ladder that contradicts it

Measured 2026-09-22, `docs/state/SUITE-BASELINE-2026-09-22.md` section 3.1.
**The largest single cluster in the suite baseline: 28 of 111.**

## The failure

All 28 raise the same refusal:

    bisonfactory.FactoryRefused: step 3 is not a thread reply but carries a
    distinct subject ('{SUBJECT_3}' vs opener '{SUBJECT_1}')

    test_bison_campaign_write   11
    test_render_preview         11
    test_task081_thread_reply    6

The guard arrived with **TASK-219 at `4c9d63d3`, 2026-09-16** — "only the
opener owns a subject" — a deliberate tightening of the standing
EMAILBISON-COPY-REQUIREMENTS contract, which CLAUDE.md carries: *a sequence is
one conversation, same-thread follow-ups use the provider's thread_reply
rather than a new subject every step*.

**Changed contract. UPDATE THE FIXTURES, NEVER THE GUARD.** This is the same
rule TASK-250 states for the verification roles, for the same reason: a test
that goes green by weakening a standing copy contract is worth less than the
failure. Do not add an escape hatch, do not make the invariant conditional,
and do not skip the tests.

## The part that is NOT fixture debt — fix this first

The invariant says: if any follow-up is threaded, every follow-up must either
be threaded or reuse the opener's subject. The shipped ladder default is

    cadencelibrary.THREAD_REPLY_PATTERNS["email_five"]
        = (False, True, False, True, False)

Steps 3 and 5 are **not** threaded. So **the default five-rung ladder cannot
build a sequence whose follow-ups carry their own subjects** — the system's
own default configuration is refused by the system's own invariant.

Production is not affected today, and this was checked rather than assumed:
both real client configs override the pattern with all-threaded follow-ups.

    config/clients/productive.yaml   thread_reply_pattern: [False, True, True]
    config/clients/demo.yaml         thread_reply_pattern: [False, True, True, True, True]

which is why 491-498 built and activated on 09-21/22 against a guard already
six days old. **A client added without that override inherits the broken
default**, and the first symptom is a campaign that cannot be built.

So: decide which is right, the ladder or the invariant, and make them agree.
`email_eight` has the same alternating shape and the same problem. This is a
question about the copy contract, so if the answer is not obvious from
EMAILBISON-COPY-REQUIREMENTS, write the finding and stop rather than picking
one — the two candidate fixes have opposite meanings:

    the pattern is wrong  -> follow-ups should all thread; change the ladder
    the pattern is right  -> an unthreaded follow-up must reuse the opener's
                             subject; the ladder is fine and the DEFAULT COPY
                             is what has to change

## Then the fixtures

Per test, the same two shapes TASK-250 uses:

- the test is **about threading** → give it a shape that satisfies the
  invariant and keep what it was asserting. `test_task081_thread_reply` is
  this; it exists to prove thread_reply survives a round trip, and it can do
  that on a compliant sequence.
- the test merely needs **a sequence** → smallest possible change, one line,
  no ceremony.

## Falsifiable requirements

1. All 28 green, with the guard unchanged. `git diff src/bisonfactory.py`
   must be empty for the invariant block at lines ~288-308.
2. A test that the LADDER DEFAULT itself satisfies the invariant — the gap
   above, closed as a property rather than as 28 individual fixes. Build a
   sequence from each entry in `THREAD_REPLY_PATTERNS` with distinct
   per-step subjects and assert `_sequence_steps` accepts it, or assert the
   documented reason it should not.
3. A test that a client with NO `thread_reply_pattern` override can build a
   five-step sequence. That is the latent defect, and nothing currently
   covers it because both real clients override.
4. Attack it: restore one fixture to its pre-fix shape and confirm the
   invariant still refuses. A cluster this size is exactly where a guard gets
   quietly loosened to clear a number.

## Do not

- Do not weaken, gate or make optional the invariant in
  `src/bisonfactory._sequence_steps`.
- Do not edit `config/clients/*.yaml` to make tests pass. Those are operator
  decisions about live copy.
- Do not touch `src/providers/` — the production session owns it.
