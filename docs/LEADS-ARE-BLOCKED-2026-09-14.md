# Leads are blocked, and the gates are not the reason

2026-09-14, written after TASK-064's human read of the LinkedIn cadence.

## THE DECISION

    DO NOT ADD LEADS TO HEYREACH 599020.
    Not the three pushable contacts. Not a raised cohort. Not tonight.

This is not a permission question and it is not a gate failure. The campaign
is written and verified - 27 of 27 readback checks PASS. The three pushable
contacts pass every automated gate the repository has. **They fail a human
read on all six verdicts**, and a person reading them is the check that no
assertion could reach.

## WHAT A HUMAN READ FOUND THAT EVERY GATE MISSED

Across 12 generated messages for the 3 pushable contacts:

    Productive is named                          ZERO times
    the connection note says who is writing      never - no name, no company
    the sequence progresses                      no - four askings of the
                                                 profitability question
    a stranger learns what is being offered      no
    the hand-written fallbacks beat it           on every pushable record

The paradox worth keeping: the twelve NON-pushable contacts fall back to the
operator's hand-written lines, which DO name Productive. So the contacts that
pass the gates would send worse copy than the contacts that fail them.

## WHY THE GATES DID NOT CATCH IT

They were not asked to. Every gate here answers a local question - does this
message repeat a sibling, does it assert something unsupported, is the
subject the right length, does it name a real person. Each one is correct and
each one fired correctly.

**No gate asks whether the sequence, read end to end by a stranger, explains
what is being sold.** That question is not expressible as a per-message
assertion, which is precisely why `MANUAL-REVIEW.md` exists. This is the
first time that file has earned its place with a concrete save.

Do not respond to this by writing a gate that greps for the word
"Productive". A sequence can name the product and still be four askings of
the same question, and a gate that passes it would be the alarm switched off
again.

## THE ROOT CAUSE, AND WHY IT IS ALREADY HALF FIXED

The copy read by TASK-064 is STORED copy. It was generated before the
`product:` block in `config/clients/productive.yaml` reached the prompt.

Two other tasks measured the other half of this the same evening:

    TASK-039  the product block DOES now reach the rendered prompt.
              Proven against tests.test_the_model_is_told_what_we_sell.
    TASK-065  on FRESH generation the product rungs em3 and li4 name
              Productive 100% of the time; per-sequence 94-100%.

So the 42% and 29% figures in checkpoint C, and the ZERO in TASK-064,
all describe copy that predates the fix. **Regeneration is the remedy for
findings 2 and 7. It is not the remedy for findings 1 and 3.**

## WHAT REGENERATION WILL NOT FIX

    finding 1   the sequence does not progress - the ladder's six distinct
                jobs collapse into one discovery question
    finding 3   the connection note never identifies the sender

Neither is a stale-copy problem. Both are the ladder and the prompt asking
for the wrong thing, and both survive a regeneration that only fixes the
product name. TASK-075 is those two.

## THE ORDER, AND IT HAS NOT CHANGED - ONLY THE BAR HAS

    1  sequence written and verified at the provider        DONE, 27/27
    2  copy regenerated against the current ladder          TASK-072, running
    3  connection note and progression fixed                TASK-075, queued
    4  A HUMAN READ OF THE REGENERATED COPY PASSES          the new gate
    5  only then, leads

**`pushable: N of 15` is no longer the promotion criterion.** It was the
criterion this morning and TASK-064 retired it. A contact is promotable when
it passes the gates AND a person has read its sequence end to end and would
send it. Raising `pushable` while step 4 fails just produces more copy nobody
should send.

## THE CLAIMS THAT MUST NOT SURVIVE REGENERATION

Found in the read, each on a specific record:

    portsidemarketing-com   "as a fellow founder" - an assertion about the
                            SENDER that may be false. Note the direction:
                            the unsupported-claim gate watches claims about
                            the PROSPECT, and this one is about us.
    ethoscreate-com         "our previous discussions" on a record whose
                            prior_contact is False. Correctly flagged.
    savagebrands-com        "i admire how savage brands drives profitability
                            and growth" - an assertion about the recipient
                            with no stored evidence behind it.

The first is the more interesting one, and it is the fourth phrase this rule
has turned out to be short of. Checkpoint C predicted there would be a
fourth. There was.
