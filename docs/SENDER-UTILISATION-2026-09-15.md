# Sender Utilisation Report — 2026-09-15

TASK-144 deliverable. Three parts: per-seat committed-vs-busy picture, the
write route verdict, and a recommendation for the first campaign.

Machine-readable form: `docs/state/TASK144-SEAT-UTILISATION.json`, regenerate
with `py -3 scripts/task144_seat_utilisation.py`.

## CRITICAL CLARIFICATION: WHAT `activeCampaigns` MEANS

Cross-referencing `SENDER-CAPACITY.json` (from `POST /li_account/GetAll`) with
the per-seat campaign status breakdown in this report (from a live provider
read that mapped each seat to its campaigns and their statuses) reveals:

**`activeCampaigns` is the IN_PROGRESS campaign count, not the total.**

Evidence: SENDER-CAPACITY.json shows `activeCampaigns: 8` for every non-SN
healthy seat and `activeCampaigns: 12` for every SN healthy seat. The per-seat
breakdown below shows the same seats with exactly 8 IN_PROGRESS (non-SN) and
12 IN_PROGRESS (SN). The match is exact across all 33 seats.

Total campaigns per seat (including PAUSED, FINISHED, DRAFT) range from 13 to
43. Those additional campaigns are not counted in `activeCampaigns`.

**This means all 33 healthy seats ARE genuinely busy.** There is no hidden
headroom from seats attached to only-finished campaigns. Every healthy seat
is actively sending through 8-12 campaigns.

## Summary

| Metric | Value |
|--------|-------|
| Total seats | 41 |
| Healthy (isActive + authIsValid) | 33 |
| Auth invalid (active but broken) | 1 |
| Inactive | 7 |
| Healthy seats effectively idle (no IN_PROGRESS campaign) | 0 |
| Healthy seats on at least one IN_PROGRESS campaign | 33 |
| Daily connection request ceiling (all healthy) | 1054 |
| Daily message ceiling (all healthy) | 1143 |
| Daily connection request ceiling (seats on IN_PROGRESS) | 1054 |
| Daily message ceiling (seats on IN_PROGRESS) | 1143 |
| Daily connection request ceiling (idle seats) | 0 |
| Daily message ceiling (idle seats) | 0 |

## Campaign Status Distribution

| Status | Count |
|--------|-------|
| DRAFT | 8 |
| FINISHED | 31 |
| IN_PROGRESS | 12 |
| PAUSED | 32 |

## 1. Per-Seat Campaign Attachment

Each healthy seat's campaign attachment, classified by campaign status.
A seat is **effectively idle** if NONE of its campaigns are IN_PROGRESS.

| Seat (hash) | Campaigns | IN_PROGRESS | PAUSED | FINISHED | DRAFT/SCHED | Idle? | Conn Req Limit | Msg Limit |
|-------------|-----------|-------------|--------|----------|-------------|-------|----------------|-----------|
| `3b946d9bb7b6` | 19 | 8 | 9 | 1 | 1 |  | 40 | 40 |
| `ba47db254958` | 18 | 8 | 8 | 1 | 1 |  | 40 | 40 |
| `2f8cfc9a3cb6` | 18 | 8 | 8 | 1 | 1 |  | 40 | 40 |
| `1d6bf60eb479` | 13 | 8 | 4 | 1 | 0 |  | 40 | 40 |
| `392c37e7e961` | 18 | 8 | 8 | 1 | 1 |  | 40 | 40 |
| `f1bcbd4d80f2` | 18 | 8 | 8 | 1 | 1 |  | 40 | 40 |
| `1556fcf3feb2` | 18 | 8 | 8 | 1 | 1 |  | 40 | 40 |
| `17b1e1b53e37` | 18 | 8 | 8 | 1 | 1 |  | 40 | 40 |
| `b0af54d6bb50` | 18 | 8 | 8 | 1 | 1 |  | 0 | 40 |
| `0b0fb227391b` | 18 | 8 | 8 | 1 | 1 |  | 25 | 40 |
| `d198f343f114` | 17 | 8 | 7 | 1 | 1 |  | 25 | 25 |
| `359833076bff` | 18 | 8 | 8 | 1 | 1 |  | 23 | 24 |
| `d4b6a09b4718` | 42 | 12 | 24 | 1 | 5 |  | 40 | 40 |
| `12b2a139eafd` | 42 | 12 | 24 | 1 | 5 |  | 40 | 40 |
| `38b50288b045` | 42 | 12 | 24 | 1 | 5 |  | 40 | 40 |
| `502a93d71832` | 42 | 12 | 24 | 1 | 5 |  | 40 | 40 |
| `fca27f014c0e` | 42 | 12 | 24 | 1 | 5 |  | 40 | 40 |
| `b23f2ef3515d` | 27 | 8 | 17 | 1 | 1 |  | 40 | 40 |
| `644e8f47c2ea` | 42 | 12 | 24 | 1 | 5 |  | 40 | 40 |
| `1f6544b3858e` | 35 | 12 | 18 | 0 | 5 |  | 40 | 40 |
| `745eafbba979` | 43 | 12 | 24 | 1 | 6 |  | 40 | 40 |
| `5aa8d21d4e05` | 42 | 12 | 24 | 1 | 5 |  | 40 | 40 |
| `3e58112b464a` | 18 | 8 | 8 | 1 | 1 |  | 25 | 40 |
| `9f8a9d51be40` | 16 | 8 | 7 | 1 | 0 |  | 17 | 17 |
| `43328c3aeaff` | 18 | 8 | 8 | 1 | 1 |  | 19 | 18 |
| `84828bd8f352` | 17 | 8 | 8 | 0 | 1 |  | 22 | 22 |
| `7945bfbb9e9a` | 18 | 8 | 8 | 1 | 1 |  | 18 | 17 |
| `fe7419baf5c7` | 18 | 8 | 8 | 1 | 1 |  | 25 | 40 |
| `738779f2fe0c` | 18 | 8 | 8 | 1 | 1 |  | 15 | 5 |
| `acfd02760a66` | 18 | 8 | 8 | 1 | 1 |  | 25 | 40 |
| `fffe676369ee` | 26 | 12 | 8 | 1 | 5 |  | 40 | 40 |
| `b950e5cf18cf` | 17 | 8 | 7 | 1 | 1 |  | 40 | 40 |
| `f691fc2aa4bf` | 18 | 8 | 8 | 1 | 1 |  | 15 | 15 |

### Seats on ONLY finished campaigns (potentially reclaimable)

None. Every healthy seat with campaigns has at least one IN_PROGRESS or PAUSED.

## 2. Real Activity Per Seat

The provider exposes `/stats/GetOverallStats` which returns ALL-TIME counters per seat (connectionsSent, messagesSent, totalMessageReplies, uniqueLeadsContacted). **This is NOT today's activity** — it is cumulative since the seat was connected.

**The provider does NOT expose per-day or per-period activity breakdowns per seat.** What was sent TODAY cannot be determined from the API. This is a finding, not a failure — a planner must assume the full daily ceiling is available unless operational logs say otherwise.

| Seat (hash) | Connections | Accepted | Acceptance% | Messages | Replies | Reply% | Leads |
|-------------|-------------|----------|-------------|----------|---------|--------|-------|
| `3b946d9bb7b6` | 2805 | 302 | 10.8 | 430 | 32 | 12.3 | 2808 |
| `ba47db254958` | 2776 | 251 | 9.0 | 375 | 22 | 10.0 | 2778 |
| `2f8cfc9a3cb6` | 2796 | 305 | 10.9 | 404 | 40 | 15.7 | 2797 |
| `1d6bf60eb479` | 2079 | 192 | 9.2 | 202 | 23 | 16.0 | 2081 |
| `392c37e7e961` | 2808 | 227 | 8.1 | 329 | 21 | 10.0 | 2808 |
| `f1bcbd4d80f2` | 2797 | 284 | 10.2 | 398 | 22 | 9.2 | 2799 |
| `1556fcf3feb2` | 2808 | 218 | 7.8 | 312 | 24 | 13.7 | 2810 |
| `17b1e1b53e37` | 2806 | 195 | 6.9 | 250 | 22 | 13.3 | 2808 |
| `b0af54d6bb50` | 1241 | 154 | 12.4 | 240 | 18 | 11.6 | 1241 |
| `0b0fb227391b` | 1329 | 152 | 11.4 | 238 | 16 | 11.8 | 1329 |
| `d198f343f114` | 1440 | 139 | 9.7 | 199 | 15 | 12.0 | 1440 |
| `359833076bff` | 2586 | 251 | 9.7 | 371 | 24 | 10.7 | 2586 |
| `d4b6a09b4718` | 4657 | 680 | 14.6 | 1613 | 148 | 19.9 | 5068 |
| `12b2a139eafd` | 4723 | 734 | 15.5 | 1955 | 142 | 16.7 | 5140 |
| `38b50288b045` | 4735 | 596 | 12.6 | 1558 | 108 | 15.7 | 5110 |
| `502a93d71832` | 4729 | 595 | 12.6 | 1443 | 123 | 19.2 | 5131 |
| `fca27f014c0e` | 4649 | 450 | 9.7 | 1114 | 89 | 17.6 | 5028 |
| `b23f2ef3515d` | 3758 | 369 | 9.8 | 661 | 53 | 14.7 | 3725 |
| `644e8f47c2ea` | 4697 | 619 | 13.2 | 1511 | 122 | 17.9 | 5103 |
| `1f6544b3858e` | 4633 | 619 | 13.4 | 1360 | 91 | 15.7 | 5015 |
| `745eafbba979` | 4723 | 453 | 9.6 | 1263 | 87 | 15.2 | 5118 |
| `5aa8d21d4e05` | 4716 | 581 | 12.3 | 1524 | 100 | 14.6 | 5118 |
| `3e58112b464a` | 2750 | 280 | 10.2 | 374 | 31 | 13.1 | 2750 |
| `9f8a9d51be40` | 1971 | 231 | 11.7 | 332 | 39 | 20.2 | 1974 |
| `43328c3aeaff` | 1202 | 86 | 7.2 | 148 | 8 | 11.1 | 1202 |
| `84828bd8f352` | 1440 | 135 | 9.4 | 172 | 16 | 14.4 | 1440 |
| `7945bfbb9e9a` | 2035 | 236 | 11.6 | 325 | 40 | 19.5 | 2035 |
| `fe7419baf5c7` | 2717 | 398 | 14.6 | 609 | 59 | 16.7 | 2725 |
| `738779f2fe0c` | 1134 | 88 | 7.8 | 73 | 9 | 13.4 | 1134 |
| `acfd02760a66` | 2737 | 271 | 9.9 | 400 | 29 | 12.2 | 2746 |
| `fffe676369ee` | 2923 | 295 | 10.1 | 541 | 51 | 17.2 | 3167 |
| `b950e5cf18cf` | 3067 | 371 | 12.1 | 589 | 50 | 14.8 | 3068 |
| `f691fc2aa4bf` | 1650 | 154 | 9.3 | 220 | 19 | 14.1 | 1650 |

## 3. The Write Route Verdict - TASK-144 Part 2

### The route EXISTS. The OPERATIONS entry is stale.

`providerwrites.py:153` says of `LINKEDIN_ASSIGN_SENDER`:

> "no documented route. campaignAccountIds is readable on the campaign
> object, so a write would be verifiable; assignment was done by hand"

**This is no longer true.** The routes are documented, implemented, and on
the write allowlist:

| Route | On WRITE_ROUTES | Function | Readback |
|---|---|---|---|
| `/campaign/AddLinkedInAccountsToCampaign` | YES (heyreach.py:1302) | `add_senders()` at heyreach.py:1813 | `campaignAccountIds` after write |
| `/campaign/RemoveLinkedInAccountsFromCampaign` | YES (heyreach.py:1303) | `remove_senders()` at heyreach.py:1831 | `campaignAccountIds` after write |

Request shape:

    POST /campaign/AddLinkedInAccountsToCampaign
    Body: {"campaignId": <int>, "linkedInAccountIds": [<int>, ...]}

    POST /campaign/RemoveLinkedInAccountsFromCampaign
    Body: {"campaignId": <int>, "linkedInAccountIds": [<int>, ...]}

Both functions:
1. Read the campaign BEFORE the write (refuse if not in DRAFT/SCHEDULED/PAUSED)
2. POST the write
3. Read the campaign AFTER the write
4. Check `campaignAccountIds` - if any requested id is missing (add) or still
   present (remove), raise even though HTTP was 2xx

`/campaign/UpdateAccounts` is deliberately NOT on WRITE_ROUTES. It is a full
replace: any seat missing from the body is removed. On a PAUSED campaign,
leads belonging to a removed seat are stopped and cannot be resumed. The
additive and subtractive routes do the same job safely.

### What is NOT enabled

`LINKEDIN_ASSIGN_SENDER` is NOT in `providerwrites.SUPPORTED`. The
`SUPPORTED` tuple (line 309) contains:

    LINKEDIN_PAUSE, EMAIL_PAUSE, EMAIL_STOP_LEAD,
    EMAIL_CREATE_CAMPAIGN, EMAIL_SET_SEQUENCE,
    LINKEDIN_SET_SEQUENCE, LINKEDIN_ADD_LEAD

`LINKEDIN_ASSIGN_SENDER` is absent. The transport can do it; the permission
gate refuses it.

### Callers

`add_senders()` and `remove_senders()` have NO callers in `src/`. They are
defined, tested at the transport level, and wired into no workflow.

### The verdict

The write route exists at the transport layer and is fully implemented with
readback verification. It is not enabled at the permission layer. The
`providerwrites.OPERATIONS` entry saying "no documented route" is stale and
should be updated. Enabling requires Claude's decision - it is a
configuration change to `SUPPORTED`, not prospect-facing (attaching a seat
to a DRAFT campaign sends nothing), and the readback is already wired.

## 4. Remaining Safe Headroom

### What is MEASURED

- **Per-seat daily ceilings** (connectionRequestLimit, messageLimit): configured in the provider, read from `accountLimits` on each seat.
- **Cooldown state**: whether each seat is currently in cooldown for connection requests, connection notes, InMail, or search.
- **Campaign attachment**: which campaigns each seat is on and their statuses.

### What is ASSUMED

- **That the daily ceiling is available today.** The provider does not report how much has been sent today. A seat showing 40 connection requests/day may have already sent 30 of them. Without per-day activity data, headroom = ceiling, and that is an UPPER BOUND.
- **That a seat on a FINISHED campaign can be reused.** Detachment from the finished campaign is assumed to be possible but has not been tested.
- **That cooldowns are temporary.** A seat in `connectionRequestCooldown` will exit cooldown, but the duration is not exposed by the API.

## 5. Cooldown Analysis

**1 seats are currently in at least one cooldown.**

- `0b0fb227391b` (seat 143105): cooldown on: connection_request

A seat in cooldown CANNOT be reused immediately. The provider does not expose cooldown duration. A planner that ignores cooldowns will promise throughput the provider will not deliver.

## 6. The AUTH_INVALID Seat

- **Seat `42ee6311bdf4`** (id 129531): `isActive: true`, `authIsValid: false`. Attached to 10 campaigns (1 IN_PROGRESS).
  - All-time stats: 1793 connections, 240 messages, 21 replies, acceptance rate 11.9%

**This seat is NOT capacity.** It accepts assignments and fails. It is attached to campaigns, which means leads may be queued behind it. It should be excluded from every plan until auth is restored. Whether it is recoverable depends on the LinkedIn re-authentication flow — the provider does not expose a diagnostic beyond `authIsValid: false`.

## 7. Cohort Throughput Arithmetic - TASK-144 Part 3

### The question: how fast could a 50-lead cohort move through a connection-request-then-message cadence?

### Two-tier seat structure

The estate has two tiers:
- **10 Sales Navigator seats**: 398 total campaign attachments (avg 39 per seat). These are the heavy users, each on 12 IN_PROGRESS campaigns plus 18-24 PAUSED/FINISHED.
- **23 Regular seats**: 414 total campaign attachments (avg 18 per seat). Most are on 8 IN_PROGRESS campaigns plus 7-9 PAUSED.

Both tiers are fully committed. No seat in either tier is idle.

### Measured connection acceptance rate: 11.1%

Across the estate, 10911 of 97917 connection requests have been accepted. This is the actual rate to use for planning, not a guess.

#### Scenario A: Use ALL healthy seats (including those on IN_PROGRESS campaigns)

- Total healthy seats: 33
- Total daily connection request ceiling: 1054
- 50 leads, one connection request each: needs 50 connection requests
- **Day 1: all 50 connection requests can be sent** (1054 ceiling >> 50 needed)
- After connection acceptance (measured rate 11.1% = ~6 leads accept), message step fires
- Total daily message ceiling: 1143
- **Day 2-3: messages to accepted leads can be sent** (1143 ceiling >> 6 needed)
- **Total time: 2-3 days** (day 1 connect, day 2-3 message after acceptance)

#### Scenario B: Use only effectively idle seats

- Idle healthy seats: 0
- Idle daily connection request ceiling: 0
- Idle daily message ceiling: 0
- **There are no idle seats.** Every healthy seat is on at least one IN_PROGRESS campaign. To free capacity, campaigns would need to be completed, paused, or seats detached.

#### Scenario C: One seat could do it

A single seat with a 25-40 connection request daily limit:
- Day 1: send 25-40 connection requests (covers 50 leads in 2 days)
- Day 2: send remaining connection requests
- Day 3-4: messages to accepted leads
- **Total: 3-4 days from one seat**

### The answer

**One seat could move 50 leads through a connect-then-message cadence in 3-4 days.** The multi-sender question is therefore NOT URGENT for a 50-lead cohort. The constraint is not throughput — it is approval and copy quality, as TASK-096 already found.

The real question is not 'can we fit a cohort' but 'can we add a cohort without disturbing the 12 IN_PROGRESS campaigns already running.' Since every seat is already committed, the answer is: only by sharing seats with existing campaigns, or by waiting for campaigns to finish.

### The specific recommendation for campaign 599020

**ONE sender: seat 174892 (already attached).**

This seat is:
- HEALTHY (isActive + authIsValid both true)
- Sales Navigator (validates SN-dependent routes)
- 40 CR/day, 40 msg/day (highest tier)
- Not on cooldown at snapshot time
- Already has the campaign's sequence bound to it

The arithmetic:

    1 seat at 40 CR/day  ->  50 leads in 2 days  (1.25 working days)
    1 seat at 40 CR/day  ->  122 leads in 4 days (3 working days)

The cohort is smaller than one seat's daily ceiling times a small number of
days. Adding senders does not meaningfully reduce total elapsed time because
the cadence's own delays (1-3 days between steps) dominate.

**Why not multi-sender for the first campaign:**

1. **The cohort is smaller than one seat's capacity.** 50 leads at 40 CR/day
   is 1.25 days. Even 122 leads is only 3 days from one seat.
2. **The constraint was never throughput.** Campaign 599020 carried ONE sender
   and ZERO leads while 33 healthy seats sat at 1,054 CR/day. Approval and
   copy quality were the blockers.
3. **Every seat is already busy.** All 33 healthy seats carry 8-12 IN_PROGRESS
   campaigns. Adding a seat to 599020 adds load to a seat already serving
   the client's active campaigns.
4. **A canary should be simple.** One seat, one sequence, one set of replies
   to monitor. If something goes wrong, one seat to investigate.
5. **Identity spreading matters at volume, not at 50.** One seat sending 50
   connection requests over 2 days is indistinguishable from normal LinkedIn
   activity.

**If multi-sender IS wanted later**, the mechanism is ready:
1. Enable `LINKEDIN_ASSIGN_SENDER` in `providerwrites.SUPPORTED`
2. Update the stale OPERATIONS entry
3. Call `heyreach.add_senders(599020, [seat_ids])`
4. Assign leads to seats per row via `provider_account_id` before `build_lead_pairs`
5. Readback verifies `campaignAccountIds` after the write

### Assumptions behind this arithmetic

1. **Connection acceptance rate: 11.1% measured.** Used verbatim from the estate's all-time stats. Varies by seat from 6.9% to 15.5%.
2. **Daily ceilings are available.** The provider does not report today's usage, so we assume the full ceiling is free. This is an UPPER BOUND.
3. **Cooldowns are not blocking.** At measurement time, 1 seat(s) were in cooldown. This can change.
4. **Detachment from finished campaigns is possible.** Not tested.
5. **LinkedIn tolerates the provider's configured limits.** A configured limit of 40/day is what the provider allows, not what LinkedIn will tolerate indefinitely. The provider sets these conservatively.

## 8. What the Provider Does NOT Report

These are findings, not failures:

1. **Per-day activity per seat.** `/stats/GetOverallStats` returns all-time counters. There is no way to determine what a seat sent today.
2. **Cooldown duration.** A seat in cooldown reports `true` for the cooldown flag but does not say when it expires.
3. **Why auth is invalid.** `authIsValid: false` is a boolean. No diagnostic, no error message, no remediation hint.
4. **Per-campaign activity per seat.** Stats can be filtered by campaignIds AND accountIds together, but the cross-tabulation of 'this seat sent N messages in this campaign' requires N API calls.

---

*Originally generated 2026-09-15 06:56 UTC by `scripts/sender_utilisation.py`.
Updated for TASK-144 with write route verdict, corrected `activeCampaigns`
interpretation, and specific campaign recommendation. Read-only. No provider
mutations.*