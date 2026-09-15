PRIORITY: P1
DEPENDS:

# TASK-144 - 33 healthy seats, ~1054 connection requests a day, and the first campaign uses one

## THE NUMBERS AS THEY STAND

Read from HeyReach 2026-09-15:

    seats in the estate               41
    healthy                           33
    active but authIsValid FALSE       1   (seat 129531, the client's own
                                            campaign 523987, out of scope)
    inactive                           7
    aggregate ceiling            ~1054 connection requests / day
    uncommitted healthy seats          0   <- read this one twice

    campaign 599020                    1 sender attached (174892)

**Zero healthy seats are uncommitted.** Every one is already attached to
something in the client's own estate. So "use multiple senders" is not a free
action here - it is a request to share a seat that is already carrying work,
and the standing policy is explicit that a sender estate is never made to
carry more by raising a limit.

## THE QUESTION THIS TASK ANSWERS

Given that, what is the CORRECT sender configuration for a Resonate OS
campaign, and what does the provider actually let us do about it?

Three parts, and the first two are reads:

### 1. What does a seat's committed capacity actually look like?

For each healthy seat, from provider reads only:

    which campaigns is it attached to
    what state are those campaigns in (a seat attached only to DRAFT or
      FINISHED campaigns is not, in any real sense, busy)
    what has it actually sent recently, if the provider exposes it
    what per-day limit is configured, per seat and per campaign, and where
      that limit is READ from - `docs/HEYREACH-CAPABILITY-CONTRACT.md` and
      `scripts/sender_capacity.py` already hold some of this. Start there.

The distinction that matters: **attached is not the same as busy.** If most of
the 33 are attached to campaigns that cannot send, the estate has far more
real headroom than "zero uncommitted" suggests, and that changes the answer.

### 2. Is there a write route for sender assignment at all?

`providerwrites.LINKEDIN_ASSIGN_SENDER` says "no documented route.
campaignAccountIds is readable on the campaign object, so a write would be
verifiable; assignment was done by hand."

Establish whether that is still true. Read the vendor documentation and the
route evidence already recorded in `docs/`. **You may not probe a write route
and you may not call one** - reads only, and a route's existence is
established by documentation plus what a READ shows, not by trying it.

If no route exists, say so plainly. "Assignment stays manual" is a finding,
and it means the answer to part 3 has to work within one sender or be handed
to a person.

### 3. What should the FIRST campaign be configured with, and why?

A recommendation with a number and a reason. Not "use more senders."

Consider, and say which applies:

    one seat is correct for a 3-50 lead cohort because the cohort is smaller
      than one seat's daily ceiling
    multiple seats are correct because a connection request per seat per day
      is the binding constraint and the cohort exceeds one seat's share
    multiple seats are correct for a reason that is NOT throughput - spreading
      identity, avoiding one account carrying a whole client's outreach

Work out what one seat's daily ceiling actually is and compare it to 50. If
one seat can carry the whole cohort comfortably, then adding senders to the
first campaign is complexity with no benefit and the honest recommendation is
one seat - say so.

## WHAT YOU MAY NOT DO

- **No provider writes of any kind.** No assignment, no limit change, no
  campaign mutation. Reads only, and that is a rule rather than a property
  now that you hold real keys.
- Do not raise any configured limit, or recommend raising one, to make a
  number work. The policy is explicit: a sender estate is never made to carry
  more by raising a limit.
- Do not write to `work/`.

## FILES ALLOWED

    docs/SENDER-UTILISATION-2026-09-15.md   (new)
    scripts/task144_*.py
    the task file itself

## FILES FORBIDDEN

    src/       work/       config/

## DELIVERABLE

The per-seat committed-vs-busy picture with the route each number came from,
the verdict on whether an assignment write route exists, and a recommendation
for the first campaign with the arithmetic behind it - including, if that is
where the numbers land, "one seat is enough".
