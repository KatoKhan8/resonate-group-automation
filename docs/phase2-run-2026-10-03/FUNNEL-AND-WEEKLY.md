# Phase 2 - 120 simulated days, seventeen weeks plus a total

> ovo kaže što sustav radi 120 dana, ne što bi zaradio; svaki odgovor je iz stope, ne iz tržišta

Seed 20261003. Population digest `1dafc3837a532e9e`, rerun proven identical by digest. 300 accounts, 900 DMs, cohorts [38, 38, 38, 38, 37, 37, 37, 37].

Days 0-118 are the seventeen weeks below. **Days 119 and 120 are a two-day tail** - 121 days is 17 weeks and 2 days - and they are folded into week 17 rather than shown as an eighteenth week of two days.

## 1. Funnel, by week

| week | days | entered | sent | bounced | replies | positives | DNC |
|---|---|---|---|---|---|---|---|
| 1 | 0-6 | 300 | 300 | 2 | 7 | 0 | 3 |
| 2 | 7-13 | 300 | 300 | 3 | 12 | 0 | 3 |
| 3 | 14-20 | 300 | 300 | 1 | 6 | 0 | 2 |
| 4 | 21-27 | 300 | 300 | 2 | 1 | 0 | 0 |
| 5 | 28-34 | 300 | 300 | 2 | 5 | 0 | 1 |
| 6 | 35-41 | 300 | 300 | 1 | 1 | 0 | 1 |
| 7 | 42-48 | 300 | 300 | 1 | 5 | 0 | 0 |
| 8 | 49-55 | 300 | 300 | 2 | 8 | 1 | 1 |
| 9 | 56-62 | 300 | 269 | 5 | 7 | 0 | 2 |
| 10 | 63-69 | 300 | 258 | 1 | 5 | 0 | 2 |
| 11 | 70-76 | 300 | 167 | 1 | 5 | 0 | 0 |
| 12 | 77-83 | 300 | 22 | 0 | 0 | 0 | 0 |
| 13 | 84-90 | 300 | 0 | 0 | 0 | 0 | 0 |
| 14 | 91-97 | 300 | 0 | 0 | 0 | 0 | 0 |
| 15 | 98-104 | 300 | 0 | 0 | 0 | 0 | 0 |
| 16 | 105-111 | 300 | 0 | 0 | 0 | 0 | 0 |
| 17 | 112-118 | 300 | 0 | 0 | 0 | 0 | 0 |
| **total** | 0-120 | 300 | 3116 | 21 | 62 | 1 | 15 |

**THE ESTATE RUNS DRY, and that is the headline finding of a 120-day run rather than a defect in it.** Weeks 13 to 17 send NOTHING. A fixed population of 900 DMs on a five-step sequence with three-day spacing is exhausted in about 84 simulated days; after that every contact has either taken all five steps, bounced, replied or been stopped, and there is no new supply. CLAUDE.md already records the same thing about the real estate - "Expansion is a sourcing problem, and latency is a sender problem" - and this is that sentence with a date on it: a 120-day plan needs roughly 37 new DMs a day from day 84 onward, or a third of the window is idle.

The send plan below shows the other half of it: the mailbox estate was never the constraint. The forward book offered room every sending day and the population ran out first.

### Reply classes over the whole run

| class | n | share of replies |
|---|---|---|
| `negative` | 17 | 0.2742 |
| `unsubscribe` | 15 | 0.2419 |
| `out_of_office` | 12 | 0.1935 |
| `unknown` | 11 | 0.1774 |
| `not_relevant` | 4 | 0.0645 |
| `referral` | 2 | 0.0323 |
| `positive` | 1 | 0.0161 |

**Positives: 1 of 62 replies (0.0161), CLASSIFIER UNAUDITED.**

The operator's metric from 2026-10-03 is the positive reply - explicit interest or a request for more. Every positive rate in this report carries the label **classifier unaudited** until the operator reviews 100 classifier-positive replies, and the reason is on the record: a reply whose entire human content was the word "Stop" was classified `positive 0.75`. The input rate is thin - 20 positives in the 899-reply corpus - and this report does not smooth it.

## 2. Send plan per sender, against the cap

| week | sending days | mailboxes asked | slots free | cap |
|---|---|---|---|---|
| 1 | 5 | 200 | 3000 | 3000 |
| 2 | 5 | 200 | 3000 | 3000 |
| 3 | 5 | 200 | 3000 | 3000 |
| 4 | 5 | 200 | 3000 | 3000 |
| 5 | 5 | 200 | 3000 | 3000 |
| 6 | 5 | 200 | 3000 | 3000 |
| 7 | 5 | 200 | 3000 | 3000 |
| 8 | 5 | 200 | 3000 | 3000 |
| 9 | 5 | 200 | 3000 | 3000 |
| 10 | 5 | 200 | 3000 | 3000 |
| 11 | 5 | 200 | 3000 | 3000 |
| 12 | 5 | 200 | 3000 | 3000 |
| 13 | 5 | 200 | 3000 | 3000 |
| 14 | 5 | 200 | 3000 | 3000 |
| 15 | 5 | 200 | 3000 | 3000 |
| 16 | 5 | 200 | 3000 | 3000 |
| 17 | 7 | 280 | 4200 | 4200 |

The forward book is RE-WALKED EVERY SIMULATED DAY and stamped at the simulated now. Measured reason: `senderheadroom`'s freshness gate is the LAST gate and `STALE_AFTER_HOURS` is 24, so a run that walked the book once would get ROOM on day 0 and REFUSED on days 1-120 - silently, because a mailbox with no provable room is an answer and not an error.

## 3. Everybody in HOLD, with the reason and the duration

| week | holds open | longest held (days) | reasons |
|---|---|---|---|
| 1 | 2 | 0 | negative x6, not_now x5 |
| 2 | 12 | 0 | not_now x25, negative x22, referral x6 |
| 3 | 17 | 0 | negative x56, not_now x41, referral x14, not_icp x2 |
| 4 | 18 | 0 | negative x63, not_now x42, referral x14, not_icp x7 |
| 5 | 22 | 0 | negative x66, not_now x53, referral x14, not_icp x7 |
| 6 | 24 | 0 | not_now x76, negative x70, referral x14, not_icp x7 |
| 7 | 35 | 0 | not_now x89, negative x74, not_icp x36, referral x14 |
| 8 | 41 | 0 | not_now x108, negative x89, not_icp x69, referral x14 |
| 9 | 44 | 0 | not_now x116, negative x98, not_icp x70, referral x14 |
| 10 | 47 | 0 | negative x122, not_now x119, not_icp x70, referral x14 |
| 11 | 50 | 0 | negative x138, not_now x122, not_icp x70, referral x14 |
| 12 | 53 | 0 | not_now x141, negative x140, not_icp x70, referral x14 |
| 13 | 53 | 0 | not_now x147, negative x140, not_icp x70, referral x14 |
| 14 | 53 | 0 | not_now x147, negative x140, not_icp x70, referral x14 |
| 15 | 56 | 0 | negative x152, not_now x147, not_icp x70, referral x14 |
| 16 | 56 | 0 | negative x161, not_now x147, not_icp x70, referral x14 |
| 17 | 56 | 0 | negative x207, not_now x189, not_icp x90, referral x18 |

Longest single hold at the end of the run: **0 days**, reason `negative`. A hold that never clears is a defect and it is only visible as a duration.

## 4. Every notification that WOULD have fired

From the real notification layer: `replies.apply` returns the notification it planned, and **`notify.deliver` is never called**. Nothing was posted.

No notification was planned during the run.

## 5. The weekly Slack digest

Rendered to a file per week under `digests/`, not posted. Seventeen files.

