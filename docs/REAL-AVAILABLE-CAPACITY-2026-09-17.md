# 2,610 emails a day of idle capacity, and 487 cannot reach any of it

2026-09-17, measured over 6h44m of a live sending day by
`scripts/bison_mailbox_utilisation.py` and joined by
`scripts/email_sender_estate.py --json`. Reproducible; nothing here is
remembered.

## The table

    human            inbox  conn  cap/day  used  headroom  idle mb
    7cc85aecf642        66    59      885   129       756       41
    9e58861fb87e        58    50      750   155       595       30
    013d683eec7a        17    17      255     0       255       17
    083df9628156        17    17      255     0       255       17
    7798a10e783c        17    17      255     0       255       17
    2b4e867056bc        12    12      180    11       169       11
    35ecf4f32d2f        11    11      165    35       130        3
    a8d24efdbbaa        13    13      195   121        74        0
    6782bfbfb93f         5     5       75    10        65        1
    c62bbb200b21         6     6       90    51        39        0
    a7c559b981ac         2     2       30    21         9        0
    8d6a74cd9f15         1     1       15     7         8        0
    TOTAL                            3150   540      2610      137

Names are hashed - `sha256(name.lower())[:12]`, the same function the estate
script uses. `cap/day` counts CONNECTED inboxes only.

## The three numbers that matter

**1. The estate is 17% used.** 540 sends against 3,150/day of connected
capacity. **137 connected mailboxes sent nothing at all**, and not one mailbox
in the estate reached its limit - the busiest managed 12 of 15.

**2. Campaign 487's attested human is one of the most utilised in it.**
`c62bbb200b21` holds six inboxes, 90/day, 51 used, **zero idle mailboxes**.
487's sender 2736 is the second busiest inbox that human owns, at 11 of 15.
Of the six, only one has as many as ten slots free, and ten is exactly what
487's cohort needs on a single day.

That is the whole explanation for the six-day schedule. The provider queued
all ten of 487's leads for 2026-09-23 because it is booking a mailbox that is
already carrying three campaigns, one of which holds 21,318 leads. The
campaign is not stalled and the mailbox is not broken. It is at the back of a
queue.

**3. Three humans did not send one email today.** `013d683eec7a`,
`083df9628156` and `7798a10e783c` hold seventeen connected inboxes each - 51
mailboxes, **765 emails a day, entirely untouched.** Every one of them idle.

## So the constraint is not mailboxes. It is attested humans with free ones.

    what 487 needs          10 slots on one day
    what its human has      39/day of headroom spread over six busy inboxes
    what the estate has     2,610/day, 137 idle mailboxes
    what 487 may use        only inboxes belonging to ONE attested human,
                            because `executionguard` refuses any campaign
                            whose canonical row names more than one sender:
                            "a guarded action is attributed to exactly one"

The arity rule is right and this does not argue with it. A send that cannot be
attributed to one human is a send nobody can answer for, and
`docs/SENDER-ATTRIBUTION-DESIGN-2026-09-17.md` specifies the predicate that
would REPLACE it rather than relax it.

But the cost of not having that predicate is now a number rather than an
argument: **765 emails a day sitting idle behind three people this system
cannot name.** The roster's `productive` humans do not exist at the provider
(`docs/THE-ROSTER-NAMES-PEOPLE-WHO-DO-NOT-SEND-2026-09-17.md`), so
`eligible_senders` returns `[]` and every campaign falls back to a hardcoded
seat. That is what P4 buys, priced.

## Fifteen inboxes that are not capacity at all

Fifteen of the 225 read `status: Not connected`. Each has 328-371 lifetime
sends, so each used to work, and every one moved ZERO today. The roster gives
them `daily_limit: 15` regardless, so any nominal figure counts 225 mailboxes
of which only 210 can send.

    nominal    225 x 15 = 3,375/day
    connected  210 x 15 = 3,150/day

Reconnecting those fifteen returns 225/day to an estate that is already only
17% used - so it is worth less than it looks, and it is still worth more than
the three uncommitted mailboxes, which have never sent at all.

## What NOT to conclude

**Do not raise a limit.** `PRODUCTION-SCALE-POLICY.md`: a sender estate is
never made to carry more by raising a limit. Nothing here is limit-bound
anyway - the busiest inbox in the estate reached 12 of 15.

**Do not move 487's sender today.** The temptation is real: its human's least
busy inbox has exactly ten slots free. But 487 has a queue for the first time
ever, with all ten rows carrying fully rendered copy, and changing the sender
on the canonical row moves the fingerprint, requires re-approval, and re-rolls
the queue. Six days is a cheap price for the first provider-confirmed artefact
this campaign has produced, and the 23rd is itself a measurement: whether a
scheduled date on this provider holds.

**Do not read `headroom` as a forecast.** It is `cap/day` minus what moved
inside one measured window. A shorter window understates use and overstates
headroom, and this one began at 10:58Z on a day whose window opened at 07:00Z.
The three idle humans are the robust part of the finding: zero is zero however
the window is drawn.
