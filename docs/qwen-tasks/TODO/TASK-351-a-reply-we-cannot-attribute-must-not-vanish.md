PRIORITY: P1
SIZE: M
DEPENDS:

# TASK-351 - a reply we cannot attribute must not vanish

**Operator instruction, 2026-09-26:** contact-key guard clean-up.

`events.apply` returns `contact_key = None` whenever the reply address matches no
contact - an alias, a forward, somebody writing from their phone. This is common,
not exotic.

`src/accountpolicy.py` has already been bitten by it and **fixed for one branch
only.** Its own comment, around line 655:

> Every branch below was guarded by `replier is not None`, and `UNSUBSCRIBE`
> plans `replier=SUPPRESS, account=CONTINUE`, so an unattributable removal
> request wrote *nothing*: no suppression, no contact state, nothing in
> `hygiene`, nothing in the agency index.

Removal requests now widen to the account. **This task sweeps for the branches
that were not fixed.**

## Build

    src/accountpolicy.py    MODIFY - the remaining branches.
    src/events.py or wherever `apply` lives   READ.
    tests/test_an_unattributable_reply_is_never_dropped.py   NEW

For **every** outcome in the policy table, answer in your result block: with
`contact_key = None`, what does this branch write? If the answer is "nothing",
that is the defect.

## The rule that decides every case

**Uncertainty never narrows.** From the module's own four things that never move:

> An outcome nobody classified resolves to a review at *account* scope - the old
> blanket pause, plus a flag. So a broken classifier fails to the behaviour this
> system has always had, and every narrower effect requires a classification that
> earned it.

So an unattributable outcome **widens to the account or holds at account scope.**
It never silently applies to nobody. And:

- **Only a removal request suppresses.** `unsubscribe` and
  `account_do_not_contact` set `unsubscribed`; nothing else does. Do not widen
  suppression to other outcomes to make this tidy.
- **Nothing subtracts.** `apply_reply` writes only absent state. A replay may add
  a hold or a suppression and may never lift one.
- **The replier is never left to carry on** - but with no contact key there is no
  replier to stop, which is exactly why the effect must land at account scope.

## Acceptance - RUN each, paste real output

1. **Enumerate every outcome against `contact_key = None`** and print a table:
   outcome, what is written, scope. Any row writing nothing is a FAIL.

    py -3 -m unittest tests.test_an_unattributable_reply_is_never_dropped -v

2. One test per outcome, not one test for all of them. The bug was
   outcome-specific and a single aggregate assertion would have missed it.

3. **Each guard is seen to fail:** for at least three outcomes, break the
   widening, confirm the test fails and names the outcome, restore. Paste the
   runs, and confirm each mutation actually landed (`grep -c`) - a patch that
   silently no-ops produces a green run worth nothing.

4. **Suppression is not widened:** a test asserting a non-removal unattributable
   outcome does NOT set `unsubscribed`.

5. **Nothing subtracts:** replay an unattributable reply twice and assert no
   state was removed or altered, and no duplicate suppression written.

6. Full suite: wait for `work/suite_verdict.txt`, diff the failing-name SET
   against `docs/state/SUITE-BASELINE-2026-09-26.txt`.

## What this task may NOT do

- Do not narrow any existing effect. Do not make suppression easier to trigger.
- Do not change what `unsubscribe` and `account_do_not_contact` mean.
- No provider call. Nothing sent, nothing activated.
