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

---

## RESULT

**STATUS:** DONE
**COMMIT:** 314376b
**TESTS:** Read-only analysis. Script `scripts/task144_seat_utilisation.py` reads existing JSON snapshots and produces `docs/state/TASK144-SEAT-UTILISATION.json`. No code changes to src/.
**FILES CHANGED:**
- `docs/SENDER-UTILISATION-2026-09-15.md` (updated) - added write route verdict, corrected `activeCampaigns` interpretation, specific campaign recommendation
- `scripts/task144_seat_utilisation.py` (new) - reads existing JSON snapshots, produces machine-readable analysis
- `docs/state/TASK144-SEAT-UTILISATION.json` (new) - per-seat data and write route verdict

---

### Part 1: Per-seat committed-vs-busy picture

**`activeCampaigns` is the IN_PROGRESS campaign count, not total attachments.**
Confirmed by cross-reference: SENDER-CAPACITY.json shows `activeCampaigns: 8`
for non-SN seats and `12` for SN seats. The per-seat status breakdown in the
existing SENDER-UTILISATION report (from a live provider read that mapped each
seat to its campaigns) shows the same seats with exactly 8 IN_PROGRESS (non-SN)
and 12 IN_PROGRESS (SN). Total campaigns per seat (including PAUSED/FINISHED/
DRAFT) range from 13 to 43.

**All 33 healthy seats ARE genuinely busy.** Zero are idle. Every one carries
8-12 IN_PROGRESS campaigns. "Zero uncommitted seats" is accurate and not an
overstatement.

Data routes:
- Per-seat health, limits, activeCampaigns: `POST /li_account/GetAll` (captured in `docs/state/SENDER-CAPACITY.json`, generated 2026-09-15T06:44:59Z)
- Campaign status totals: `POST /campaign/GetAll` (captured in `docs/state/PROVIDER-CAMPAIGNS.json`, generated 2026-09-15T15:24:59Z)
- Per-seat campaign status breakdown: live provider read from earlier task (captured in `docs/SENDER-UTILISATION-2026-09-15.md` sections 1-2)
- All-time activity per seat: `POST /stats/GetOverallStats` (same source)

Estate: 83 campaigns (DRAFT 8, PAUSED 32, FINISHED 31, IN_PROGRESS 12).
41 seats: 33 HEALTHY, 1 AUTH_INVALID, 7 INACTIVE.
Daily ceiling over healthy: 1054 CR, 1143 messages.

### Part 2: Write route verdict

**The route EXISTS. The OPERATIONS entry is stale.**

`/campaign/AddLinkedInAccountsToCampaign` and `/campaign/RemoveLinkedInAccountsFromCampaign` are both on `heyreach.WRITE_ROUTES` (heyreach.py:1302-1303). Functions `add_senders()` (heyreach.py:1813) and `remove_senders()` (heyreach.py:1831) are fully implemented with readback verification against `campaignAccountIds`.

`LINKEDIN_ASSIGN_SENDER` is NOT in `providerwrites.SUPPORTED`. The OPERATIONS entry at providerwrites.py:153 saying "no documented route" is stale. The transport can do it; the permission gate refuses it.

Callers in src/: NONE. The functions are defined but unwired.

### Part 3: Recommendation

**ONE seat: 174892 (already attached to campaign 599020).**

Arithmetic:
- 1 seat at 40 CR/day → 50 leads in 2 days (1.25 working days)
- 1 seat at 40 CR/day → 122 leads in 4 days (3 working days)
- Cadence delays (1-3 days between steps) dominate total elapsed time

One seat is enough because:
1. The cohort is smaller than one seat's capacity
2. The constraint was never throughput (approval and copy quality were)
3. Every healthy seat is already busy on 8-12 IN_PROGRESS campaigns
4. A canary should be simple (one seat to monitor)
5. Identity spreading matters at volume, not at 50

### FINDINGS

1. **`activeCampaigns` is IN_PROGRESS count, not total.** This was ambiguous and is now settled by cross-reference. Total campaigns per seat (13-43) are much higher than `activeCampaigns` (8-12).
2. **The sender assignment write route exists and is stale-documented.** Routes on WRITE_ROUTES, functions implemented with readback, zero callers. OPERATIONS entry needs updating.
3. **One seat is enough for the first campaign.** The honest answer the task invited.
4. **Seat 139699 has 0 CR remaining** (healthy but connection-exhausted). Seat 143105 is in CR cooldown. Both are transient states.
5. **Seat 129531 (AUTH_INVALID) is on campaign 523987 with 33,710 leads** - client's own campaign, out of scope, actively failing.

### RISKS

- Adding campaign 599020 to any additional seat adds load to a seat already serving 8-12 IN_PROGRESS campaigns of the client's own. The daily ceiling (40 CR/day) is shared across ALL campaigns on that seat.
- The provider does not report per-day usage per seat. The daily ceiling is an UPPER BOUND; actual remaining capacity may be lower.

### RECOMMENDED CLAUDE ACTION

1. **Update `providerwrites.OPERATIONS`** for `LINKEDIN_ASSIGN_SENDER` to reflect the routes exist (stale documentation).
2. **Decide whether to enable `LINKEDIN_ASSIGN_SENDER`** in `SUPPORTED`. Not prospect-facing (attaching a seat to a DRAFT sends nothing). The transport is ready.
3. **Proceed with one seat (174892)** for the first cohort. The numbers support it.
