# Sender Utilisation Report — 2026-09-15

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

The provider exposes `/stats/GetOverallStats` which returns ALL-TIME counters per seat (connectionsSent, totalMessagesSent, totalMessageReplies, uniqueLeadsContacted). **This is NOT today's activity** — it is cumulative since the seat was connected.

**The provider does NOT expose per-day or per-period activity breakdowns per seat.** What was sent TODAY cannot be determined from the API. This is a finding, not a failure — a planner must assume the full daily ceiling is available unless operational logs say otherwise.

| Seat (hash) | All-Time Connections | All-Time Messages | All-Time Replies | Leads Contacted |
|-------------|---------------------|-------------------|------------------|-----------------|
| `3b946d9bb7b6` | 2805 | 0 | 32 | 2808 |
| `ba47db254958` | 2776 | 0 | 22 | 2778 |
| `2f8cfc9a3cb6` | 2796 | 0 | 40 | 2797 |
| `1d6bf60eb479` | 2079 | 0 | 23 | 2081 |
| `392c37e7e961` | 2808 | 0 | 21 | 2808 |
| `f1bcbd4d80f2` | 2797 | 0 | 22 | 2799 |
| `1556fcf3feb2` | 2808 | 0 | 24 | 2810 |
| `17b1e1b53e37` | 2806 | 0 | 22 | 2808 |
| `b0af54d6bb50` | 1241 | 0 | 18 | 1241 |
| `0b0fb227391b` | 1329 | 0 | 16 | 1329 |
| `d198f343f114` | 1440 | 0 | 15 | 1440 |
| `359833076bff` | 2586 | 0 | 24 | 2586 |
| `d4b6a09b4718` | 4657 | 0 | 148 | 5068 |
| `12b2a139eafd` | 4723 | 0 | 142 | 5140 |
| `38b50288b045` | 4735 | 0 | 108 | 5110 |
| `502a93d71832` | 4729 | 0 | 123 | 5131 |
| `fca27f014c0e` | 4649 | 0 | 89 | 5028 |
| `b23f2ef3515d` | 3758 | 0 | 53 | 3725 |
| `644e8f47c2ea` | 4697 | 0 | 122 | 5103 |
| `1f6544b3858e` | 4633 | 0 | 91 | 5015 |
| `745eafbba979` | 4723 | 0 | 87 | 5118 |
| `5aa8d21d4e05` | 4716 | 0 | 100 | 5118 |
| `3e58112b464a` | 2750 | 0 | 31 | 2750 |
| `9f8a9d51be40` | 1971 | 0 | 39 | 1974 |
| `43328c3aeaff` | 1202 | 0 | 8 | 1202 |
| `84828bd8f352` | 1440 | 0 | 16 | 1440 |
| `7945bfbb9e9a` | 2035 | 0 | 40 | 2035 |
| `fe7419baf5c7` | 2715 | 0 | 59 | 2723 |
| `738779f2fe0c` | 1132 | 0 | 9 | 1132 |
| `acfd02760a66` | 2737 | 0 | 29 | 2746 |
| `fffe676369ee` | 2923 | 0 | 51 | 3167 |
| `b950e5cf18cf` | 3067 | 0 | 50 | 3068 |
| `f691fc2aa4bf` | 1650 | 0 | 19 | 1650 |

## 3. Remaining Safe Headroom

### What is MEASURED

- **Per-seat daily ceilings** (connectionRequestLimit, messageLimit): configured in the provider, read from `accountLimits` on each seat.
- **Cooldown state**: whether each seat is currently in cooldown for connection requests, connection notes, InMail, or search.
- **Campaign attachment**: which campaigns each seat is on and their statuses.

### What is ASSUMED

- **That the daily ceiling is available today.** The provider does not report how much has been sent today. A seat showing 40 connection requests/day may have already sent 30 of them. Without per-day activity data, headroom = ceiling, and that is an UPPER BOUND.
- **That a seat on a FINISHED campaign can be reused.** Detachment from the finished campaign is assumed to be possible but has not been tested.
- **That cooldowns are temporary.** A seat in `connectionRequestCooldown` will exit cooldown, but the duration is not exposed by the API.

## 4. Cooldown Analysis

**1 seats are currently in at least one cooldown.**

- `0b0fb227391b` (seat 143105): cooldown on: connection_request

A seat in cooldown CANNOT be reused immediately. The provider does not expose cooldown duration. A planner that ignores cooldowns will promise throughput the provider will not deliver.

## 5. The AUTH_INVALID Seat

- **Seat `42ee6311bdf4`** (id 129531): `isActive: true`, `authIsValid: false`. Attached to 10 campaigns (1 IN_PROGRESS).
  - All-time stats: 1793 connections, 0 messages, 21 replies

**This seat is NOT capacity.** It accepts assignments and fails. It is attached to campaigns, which means leads may be queued behind it. It should be excluded from every plan until auth is restored. Whether it is recoverable depends on the LinkedIn re-authentication flow — the provider does not expose a diagnostic beyond `authIsValid: false`.

## 6. Cohort Throughput Arithmetic

### The question: how fast could a 50-lead cohort move through a connection-request-then-message cadence?

#### Scenario A: Use ALL healthy seats (including those on IN_PROGRESS campaigns)

- Total healthy seats: 33
- Total daily connection request ceiling: 1054
- 50 leads, one connection request each: needs 50 connection requests
- **Day 1: all 50 connection requests can be sent** (1054 ceiling >> 50 needed)
- After connection acceptance (assume 25% accept = ~13 leads), message step fires
- Total daily message ceiling: 1143
- **Day 2-3: messages to accepted leads can be sent** (1143 ceiling >> 13 needed)
- **Total time: 2-3 days** (day 1 connect, day 2-3 message after acceptance)

#### Scenario B: Use only effectively idle seats

- Idle healthy seats: 0
- Idle daily connection request ceiling: 0
- Idle daily message ceiling: 0
- **No idle connection request capacity available.**
- After acceptance (~25% = ~13 leads), messages needed: 13
- **No idle message capacity available.**

#### Scenario C: One seat could do it

A single seat with a 25-40 connection request daily limit:
- Day 1: send 25-40 connection requests (covers 50 leads in 2 days)
- Day 2: send remaining connection requests
- Day 3-4: messages to accepted leads
- **Total: 3-4 days from one seat**

### The answer

**One seat could move 50 leads through a connect-then-message cadence in 3-4 days.** The multi-sender question is therefore NOT URGENT for a 50-lead cohort. The constraint is not throughput — it is approval and copy quality, as TASK-096 already found.

However, if the cohort grows to 200+ leads or if speed matters (e.g., time-sensitive outreach), then the idle seat capacity becomes relevant. The 0 connection requests/day across idle seats could handle 200 leads in 1-2 days.

### Assumptions behind this arithmetic

1. **Connection acceptance rate: 25%.** This is a guess. The actual rate varies by industry, profile quality, and note personalisation. If it is 15%, fewer messages are needed; if 40%, more.
2. **Daily ceilings are available.** The provider does not report today's usage, so we assume the full ceiling is free. This is an UPPER BOUND.
3. **Cooldowns are not blocking.** At measurement time, 1 seats were in cooldown. This can change.
4. **Detachment from finished campaigns is possible.** Not tested.
5. **LinkedIn tolerates the provider's configured limits.** A configured limit of 40/day is what the provider allows, not what LinkedIn will tolerate indefinitely. The provider sets these conservatively.

## 7. What the Provider Does NOT Report

These are findings, not failures:

1. **Per-day activity per seat.** `/stats/GetOverallStats` returns all-time counters. There is no way to determine what a seat sent today.
2. **Cooldown duration.** A seat in cooldown reports `true` for the cooldown flag but does not say when it expires.
3. **Why auth is invalid.** `authIsValid: false` is a boolean. No diagnostic, no error message, no remediation hint.
4. **Per-campaign activity per seat.** Stats can be filtered by campaignIds AND accountIds together, but the cross-tabulation of 'this seat sent N messages in this campaign' requires N API calls.

---

*Generated 2026-09-15 06:53 UTC by `scripts/sender_utilisation.py`. Read-only. No provider mutations.*