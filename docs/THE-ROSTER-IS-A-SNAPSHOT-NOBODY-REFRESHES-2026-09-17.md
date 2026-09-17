# The sender roster is a snapshot nobody refreshes, on both channels

2026-09-17. Found while pricing P3 capacity; it is a safety finding, not a
reporting one.

## What the roster is for

`senderinventory` reads the provider and writes a `health` word onto every
account. `assignment.usable_health` then reads that STORED word when deciding
who may send: `REFUSING_HEALTH = (paused, blocked)`, and `health_of` maps any
non-connected provider status to `blocked`. **The mapping is correct.** An
inbox the provider calls `Not connected` becomes `blocked` and can never be
allocated.

The defect is that nothing re-runs the read.

## Email: eight days stale, fifteen inboxes wrong

Every one of the 225 productive `email_account` rows carried
`provider_state.read_at: 2026-09-09`. Measured against the provider on
2026-09-17:

    Connected -> Not connected      15 accounts
    rows canonical state still called `active: true, health: "ok"`   15

So fifteen inboxes that cannot send read as healthy capacity for eight days,
and `readiness()` called them READY. They are also, not coincidentally, the
same fifteen that moved ZERO over a 6h44m sampling window while 73 others sent
531 emails.

**This is harmless today only by accident.** No productive account has an
owner, so `eligible_senders` returns `[]` and nothing is allocated to
anything. It stops being harmless the moment attestation lands - which is the
whole of P4 - because the first thing a working allocator would do is hand
prospects to fifteen dead inboxes that look perfect on paper.

**Rebuilt.** `py -3 -m src.senderinventory --workspace productive --live`,
after a backup:

    accounts            225
    replaced            225
    health              ok 207, warming 3, blocked 15
    readiness           ready 186, degraded 24, not_ready 15
    ready capacity      2,790/day  (not 3,375, and not 3,150)

The rebuild is scoped - `replace` keeps everything that is not this
workspace's email accounts - and all 11 humans, 3 pairings, 35 LinkedIn
accounts and the outreach team survived untouched. The 13 owned accounts are
in the `contactout` and `demo-client` workspaces and were not in scope.

**24 accounts are DEGRADED on lifetime bounce rate** at or above 2%, which is
a separate thing nobody had counted and which no capacity figure subtracts.

## LinkedIn: four days stale, fourteen accounts drifted

`--reconcile-linkedin`, read-only:

    seats at provider             41
    seats in roster               32
    unrostered seats               9   (1 of them eligible: 174810)
    drifted accounts              14
    connection capacity/day    1,014   against a plan ceiling of 1,280

The drift is the same shape and one row is worse than stale. `li-139699`
stores `daily_limit: 40` and the provider now reports **0** - a seat that
cannot send one connection request, described by canonical state as the
estate's joint-largest. Another reads 25 against a stored 40.

**Not rebuilt, deliberately.** `build_linkedin` drops any seat not in the
operator's approved allowlist, so running it with an empty list would delete
all 32 rows and `executionguard` refuses any seat the roster does not name.
That is a fail-closed design working exactly as intended and it is not
something to route around at 20:00 with no operator present. The reconcile
report is the honest half and it is what this records.

## What changed so it is noticed next time

`production_status.py` - the first thing a fresh session runs - now prints:

    roster_read_at           the OLDEST provider read across both channels
    roster_blocked_inboxes   how many the roster itself calls unusable

UNKNOWN when the roster cannot be read or carries no timestamp, because "the
roster is fresh" is not the safe reading of silence.

That is a report, not a guard. **The guard is still missing**, and it belongs
with the attestation work rather than ahead of it: an allocator that reads a
health word should refuse a roster older than some bound, and choosing that
bound is a decision about how often the provider is asked, not a detail. Named
here so it is chosen rather than defaulted.

## The pattern this is the third instance of

    `production_status` reported 15/day for a shared mailbox     corrected
    the HeyReach roster stored `connectioRequestMax` as a limit  corrected
    the roster's health words were eight days old                corrected

Each time, a stored value was read as a current one. `CLAUDE.md` already names
the rule - prefer canonical state to a second representation of it - and the
subtler failure is this: canonical state that is a CACHE of provider truth is
a second representation, and it drifts in exactly the direction that makes the
estate look healthier than it is.
