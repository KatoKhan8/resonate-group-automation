# Seventeen, and one signature stands between them and a campaign

2026-09-17, recomputed live from `scripts/next_ready_cohort.py` against the
gates in `executionguard.authorize`'s own order. Not from a snapshot.

    LINKEDIN   81 contacts    3 LIVE    12 NEAR_MISS    66 SAFETY_BLOCKED
    EMAIL      51 contacts   10 LIVE     5 NEAR_MISS    36 SAFETY_BLOCKED

**NEAR_MISS means every gate passes except approval.** Seventeen contacts, and
every one of them is held by a missing operator signature and by nothing else.
`work/approval/NEAR-MISS-PACKET-2026-09-17.md` (gitignored, real copy, real
names) holds all seventeen with their rendered steps and a lint and claims
verdict beside each one.

## The three tempting alternatives, and why each is worth zero today

Before asking a person for anything, the cheaper routes were measured rather
than assumed. All three are dead ends, and it is better to know that than to
spend a day on one.

**Generating the missing copy buys nothing.** Nine LinkedIn contacts stop at
the `copy` gate before approval is even reached. All nine are ALSO blocked at
the account gate - six because somebody at the account is mid-sequence or has
replied, one for an account whose campaign ended early. Generating their
`li4`/`li5` steps would move them from one refusal to another.

**Re-reading the account holds buys nothing.** Thirty-two contacts are held by
"a campaign at this account ended early (stopped) and the status does not say
whether we stopped it, they unsubscribed, or the provider stopped it on a
reply". The obvious hypothesis was that these are OUR OWN stopped staging -
campaign 485 sits `stopped` with zero sends on every lead it touched - and
that `collision.without_our_staging` was failing to remove it.

It is not. **Every one of the 32 carries real prior sends at the account: 2,
5, 8, 9, 13, 14, 15, 16, 24, 26, 30 and 31 emails. Not one reads zero.** Our
own staging sends nothing by construction, so none of these rows can be ours.
They are the client's genuine history and the HOLD is correct. Nothing to
recover, and the exclusion machinery is working exactly as designed.

**Waiting for the mid-sequence accounts buys nothing today.** Forty-six
contacts are stopped because somebody at their account is mid-sequence right
now - which includes the thirteen people we made live yesterday. That resolves
itself when those cadences end. It is a reason to come back, not a reason to
act.

## What the refusals actually are

    LINKEDIN 66 blocked          EMAIL 36 blocked
      33  account mid-sequence     14  account ended early (real history)
      18  account ended early      13  account mid-sequence
      11  account has replied       4  account has replied
       3  prior sends, finished     4  prior sends, finished
       1  an address bounced        1  an address bounced

Zero contacts are blocked by suppression. Zero by fatigue. Every refusal is an
account-level engagement fact that a person at that account created, and the
system is declining to write over it.

## What this means for the mission

P1 is "the largest SAFE live cohort". The honest answer today is **seventeen
more people**, and the constraint is neither capacity, nor providers, nor
copy, nor engineering. Both live campaigns are running below their sender
ceilings and neither channel is short of people.

**The constraint is one operator action that this system may not take on its
own behalf**, and that restriction is not an inconvenience to route around: 84
approvals stamped `by: "claude"` were revoked for exactly this reason, and on
a `generated: true` step a self-stamp never expires. The approval gate is the
only place where a human says "these exact words may go to this exact person",
and the fingerprint is what makes the statement mean anything.

## For whoever approves

The packet is a read, not a form. Approval is applied by the same path
`scripts/apply_control_approval.py` used for the current email ten: a written
authorisation naming the cohort, then `approve.approve_step` computing the
fingerprint over the copy that is actually there. `approval.by` is never
written by hand, because an approval that does not match the words is meant to
be detectable rather than trusted.

Seventeen contacts span roughly seventeen accounts, and
`new_accounts_per_day: 5` is enforced at gate 5 and inside the reservation
lock. So this converts over about four days, not in one afternoon - which is
an argument for starting it, not for batching it.
