# The ambiguous holds, answered: 6 accounts of real inventory, 10 stay held

Measured 2026-09-18 against live EmailBison, per account, per stopped
membership. `src/stoppedcause.py`, run over every account whose only adverse
signal is the ambiguous-stop HOLD.

## What was asked

`docs/THE-ESTATE-IS-SATURATED-NOT-UNAPPROVED-2026-09-18.md` found that the
estate is saturated by the client's own outreach, and named one recoverable
pool: accounts held because

> a campaign at this account ended early (stopped) and the status does not say
> whether we stopped it, they unsubscribed, or something else

That is a conservative hold on an UNKNOWN. The question was whether the
UNKNOWN is answerable.

## The answer

**16 accounts carry that hold. 29 stopped memberships between them.**

    per membership          12  never_contacted
                            17  still_unknown

    per account              6  every stopped membership sent nothing,
                                and nothing else at the account is adverse
                            10  stays held

**`/api/events` could not have answered this.** It replays TEN DAYS and these
memberships are months old, so a resolver that depended on it would have
returned STILL UNKNOWN for nearly all of them. The cause that IS answerable
today is the membership's own `emails_sent` counter: **a stopped membership
that sent nothing cannot carry a prospect's refusal, because nobody at that
address was written to on that campaign.**

## Why 6 accounts is real inventory rather than a loophole

`collision.account_policy`'s own docstring draws the line:

> emailed before, all finished, nobody replied -> ALLOW. A campaign that ran
> its course months ago is history, not a live conflict.
> ...
> a `stopped` whose campaign has sent even one email is still a HOLD here

So prior sends do NOT block an account. All six candidates carry real history
- 5, 8, 21, 13, 13 and 5 emails at the account - and that history is
explicitly ALLOW territory: finished, unanswered, months old. **The only thing
holding them is the ambiguous `stopped` row, and for these six that row sent
nothing.**

The ten that stay held are the honest half. Their stopped memberships DID
send - between 2 and 31 emails at the account - and nothing in the available
evidence says why they stopped. Four of them carry four ambiguous memberships
each. The hold stays.

## The rule, and it is deliberately narrow

An account is a candidate only when **EVERY** stopped membership on it
resolves to `never_contacted` AND nothing else at the account is adverse - no
bounce, nobody in sequence, no unknown statuses.

One account makes the case for that conjunction on its own:
`cdcacc3cf0d8` has one `never_contacted` membership and one `still_unknown`,
and 31 emails at the account. Per-membership it is 50% explained. Per account
it is a question, and it stays held.

## What `never_contacted` does NOT mean

**It is not a clearance.** It is a fact about ONE membership: that row carried
no message. The account may have been emailed many times on other rows, and
five of the six candidates were.

**It does not mean the row is ours.** `collision.without_our_staging` already
removes our own proven-zero-send staging on four arms of positive evidence, so
a zero-send stopped row that survives that is the CLIENT's. Why a client stops
a lead before sending it anything is not recorded anywhere we can read -
reorganisation, a list change, a person removed. What can be said is the
narrow thing: **the prospect never heard from anybody, so the stop is not
their refusal.** That is the whole claim.

## A defect this found in itself

The first version of the counter helper returned `0` for `None`, `""`,
`"three"` and `{}` - so an UNREADABLE counter said "nobody was emailed", on
the exact branch deciding whether a stop could have been a refusal. Missing
evidence dressed as positive evidence. It returns `None` now and the caller
keeps the hold; a test asserts each unreadable shape refuses to become a zero.

## What this is NOT authority to do

Nothing here is wired into `collision.account_policy`, and it must not be
without an operator decision. Turning a resolution into a verdict **WIDENS who
may be contacted**, which is the one direction that needs a person. The
resolver reports; the gate is unchanged; every one of the 16 accounts is still
HOLD in production today.

What an operator is being offered is a bounded, checkable proposition: six
accounts whose only bar is a stopped row that provably sent nothing, each
listed with its membership outcomes and its account-level send total, so a
sample can be checked by hand before anything changes.

    465141272ed8   1 never_contacted    account sent 5
    5f3eec76776d   2 never_contacted    account sent 8
    f379f3fd6858   3 never_contacted    account sent 21
    71adcb61885a   1 never_contacted    account sent 13
    6b389ada1032   1 never_contacted    account sent 13
    8d5f4fa6c11b   1 never_contacted    account sent 5

Identifiers hashed; `work/` holds the domains and is gitignored.

## Reproducing

    py -3 -m unittest tests.test_stopped_cause_resolution

The live pass is not a committed script yet, deliberately: it reads the
provider per account and the numbers above are a moment, not a fixture. The
resolver is the durable part.
