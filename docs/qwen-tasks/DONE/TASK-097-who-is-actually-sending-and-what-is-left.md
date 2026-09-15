# TASK-097 - which senders are actually busy, and what capacity is really free

## WHAT IS ALREADY MEASURED

`scripts/sender_capacity.py` -> `docs/state/SENDER-CAPACITY.json`, read from
the provider 2026-09-15:

    seats                             41
    healthy (isActive + authIsValid)  33
    active but auth INVALID            1   looks available, FAILS ON USE
    inactive                           7
    daily ceiling, healthy          1054 connection requests, 1143 messages
    healthy seats with NO active campaign   0

**That last line is the one that matters and it is why this task exists.**
Zero healthy seats are uncommitted. Every one is already attached to at least
one campaign - mostly the client's own pre-Resonate campaigns, 83 of them
going back to April. So "assign more senders to a cohort" is a question about
seats that are already working, not about picking up spares.

## THE QUESTION

**How much of that 1054/day ceiling is actually free?**

A ceiling summed over seats that are each already running eight campaigns is
not capacity. Establish, per healthy seat:

1. Which campaigns is it attached to, and what is the STATUS of each? A seat
   attached to six FINISHED and two PAUSED campaigns is effectively idle; a
   seat on an IN_PROGRESS campaign is not. 12 campaigns in the account are
   IN_PROGRESS.
2. What has it actually DONE recently? A configured limit is not throughput.
   Find whatever the provider exposes on real activity per seat, and say
   plainly if it exposes nothing - "the provider does not report this" is a
   finding, not a failure.
3. What is its remaining safe headroom today, and what is that number based
   on - a measurement, or an assumption?
4. Cooldowns: `connectionRequestCooldown`, `connectionNoteCooldown`,
   `inMailCooldown` and `searchCooldown` are on every seat. What do they mean
   for how fast a seat can actually be reused? A planner that ignores them
   will promise throughput the provider will not deliver.

## THEN ANSWER THE OPERATIONAL QUESTION

Given the healthy estate as it stands: **how fast could a 50-lead cohort move
through a connection-request-then-message cadence, and how many seats would it
need?** Show the arithmetic. If the answer is "one seat could do it in two
days", then the multi-sender question is not urgent and you should say so.

## HARD RULES

- **Never propose raising a per-seat limit.** Add senders or add days. A
  raised limit changes the risk taken with a client's real LinkedIn account
  and is not an engineering decision. The policy states this and this task may
  not soften it.
- **An `authIsValid: false` seat is not capacity** even though it reports
  `isActive: true`. It accepts an assignment and then fails, which is worse
  than being absent because leads queue behind it looking scheduled. There is
  exactly one such seat; find out whether it is recoverable or should be
  excluded from every plan.
- Reads only. Do not attach, detach, pause or modify any seat or campaign.
- A seat is a REAL PERSON. Hash names, emails and profile URLs. The existing
  output does this; do not regress it. Seat ids and numeric limits are fine.

## DELIVERABLE

`docs/SENDER-UTILISATION-2026-09-15.md` and an updated
`docs/state/SENDER-CAPACITY.json` carrying per-seat campaign attachment and
real headroom. Separate what you MEASURED from what you ASSUMED, and give the
cohort-throughput arithmetic explicitly so the assumption behind it can be
attacked.

## RESULT

- **STATUS:** DONE
- **COMMIT SHA:** ae5b75a
- **TESTS:** `tests.test_invariants` 80/80 pass; `tests.test_audit` 16/16 pass; no conflict markers in src/, tests/, scripts/
- **FILES CHANGED:**
  - `scripts/sender_utilisation.py` (new) — the analysis script, reads three HeyReach endpoints
  - `docs/SENDER-UTILISATION-2026-09-15.md` (new) — the report
  - `docs/state/SENDER-CAPACITY.json` (updated) — per-seat campaign attachment, all-time activity, cooldown state
- **FINDINGS:**
  1. **Zero idle seats.** All 33 healthy seats are on at least one IN_PROGRESS campaign. There is no free capacity that can be assigned without sharing with existing campaigns.
  2. **Two-tier estate:** 10 Sales Navigator seats (avg 39 campaigns each, 12 IN_PROGRESS) and 23 regular seats (avg 18 campaigns each, 8 IN_PROGRESS). Both fully committed.
  3. **The provider does NOT report per-day activity.** `/stats/GetOverallStats` returns all-time counters only. What a seat sent today is unknowable from the API. Headroom = ceiling, which is an UPPER BOUND.
  4. **Measured connection acceptance rate: 11.1%** (10,911 of 97,917). Varies by seat from 6.9% to 15.5%. The Sales Navigator seats have higher acceptance (12-15.5%) than regular seats (7-11%).
  5. **One AUTH_INVALID seat** (`42ee6311bdf4`, seat 129531): `isActive: true, authIsValid: false`, attached to 10 campaigns (1 IN_PROGRESS). Has historically sent 1,793 connections. Not recoverable from the API — requires LinkedIn re-auth. Should be excluded from all plans.
  6. **1 seat in cooldown** (`0b0fb227391b`, seat 143105): connection_request cooldown. Duration not exposed.
  7. **Cohort arithmetic:** One seat can move 50 leads through connect-then-message in 3-4 days. The multi-sender question is NOT URGENT for a 50-lead cohort. The constraint is approval and copy quality, not throughput.
  8. **The real question** is not 'can we fit a cohort' but 'can we add a cohort without disturbing the 12 IN_PROGRESS campaigns.' Since every seat is committed, the answer is: only by sharing seats with existing campaigns, or by waiting for campaigns to finish.
- **RISKS:**
  - All-time stats may overstate historical activity if seats were shared across workspace migrations
  - The 11.1% acceptance rate is an estate average; individual campaigns may differ significantly
  - Daily ceilings are assumed fully available; actual same-day usage is invisible
- **RECOMMENDED CLAUDE ACTION:** Review the report at `docs/SENDER-UTILISATION-2026-09-15.md`. The AUTH_INVALID seat needs a LinkedIn re-auth decision. The campaign-cleanup question (32 PAUSED, 31 FINISHED campaigns still attached to seats) is an operational hygiene issue that could free attachment slots even though it would not free daily capacity.
