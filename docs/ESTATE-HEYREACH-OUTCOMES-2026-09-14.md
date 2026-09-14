# HeyReach Touch-to-Reply Analysis - 2026-09-14

## WHAT THIS IS

Read-only analysis of 26113 conversations (of 26174 total in the inbox, 26174 fetched). Every outbound message is a touch. For each touch, we ask: did a reply follow, how long did it take, and what did the reply say?

## DATA QUALITY

- **Conversations analysed**: 26113 (of 26174 fetched, 26174 total)
- **Average touches per conversation**: 2.9
- **Total outbound touches**: 76315
- **Conversations with at least one reply**: 4007 (15.34%)
- **Conversations with multiple replies**: 927
- **Touches that immediately preceded a reply**: 5291 (6.93%)
- **Touches with unknown-direction messages in their conversation**: 0
- **Replies classified as unknown/unreadable**: 3869 of 5291 (73.1%)

The unreadable rate is the share of replies where the classifier could not match any rule. On LinkedIn, where messages are short and casual, this is expected to be high (the estate learning document measured 70% on LinkedIn against 35% on email).

## THREE BUCKETS, SEPARATED

Per the task instruction, every section below separates:
- **OBSERVATION**: what the rows say, with n
- **HYPOTHESIS**: what it might mean
- **PROVEN LEARNING**: what survives a sample-size objection

A difference with n<30 is an observation, never a learning. The evaluator refuses to call a winner from four replies against three; the same standard applies here.

## REPLY RATE BY MESSAGE POSITION

| position | n_touches | n_replied | reply_rate |
| --- | --- | --- | --- |
| 1 | 26114 | 1760 | 6.74 |
| 2 | 15411 | 1133 | 7.35 |
| 3 | 13002 | 933 | 7.18 |
| 4 | 8772 | 667 | 7.6 |
| 5 | 6245 | 407 | 6.52 |
| 6 | 3913 | 230 | 5.88 |
| 7 | 1821 | 67 | 3.68 |
| 8 | 650 | 48 | 7.38 |
| 9 | 242 | 15 | 6.2 |
| 10 | 53 | 11 | 20.75 |
| 11 | 33 | 7 | 21.21 |
| 12 | 21 | 4 | 19.05 |
| 13 | 14 | 3 | 21.43 |
| 14 | 6 | 2 | 33.33 |
| 15 | 5 | 2 | 40.0 |
| 16 | 3 | 1 | 33.33 |
| 17 | 1 | 0 | 0.0 |
| 18 | 1 | 0 | 0.0 |
| 19 | 1 | 0 | 0.0 |
| 20 | 1 | 0 | 0.0 |
| 21 | 1 | 0 | 0.0 |
| 22 | 1 | 0 | 0.0 |
| 23 | 1 | 0 | 0.0 |
| 24 | 1 | 1 | 100.0 |
| 25 | 1 | 0 | 0.0 |
| 26 | 1 | 0 | 0.0 |

**OBSERVATION**: Position 1: 6.74% (n=26114); Position 2: 7.35% (n=15411); Position 3: 7.18% (n=13002); Position 4: 7.6% (n=8772); Position 5: 6.52% (n=6245); Position 6: 5.88% (n=3913); Position 7: 3.68% (n=1821); Position 8: 7.38% (n=650); Position 9: 6.2% (n=242); Position 10: 20.75% (n=53); Position 11: 21.21% (n=33)

## REPLY RATE BY TOUCH COUNT REACHED

Each row is a conversation length: conversations with this many total outbound touches. The reply rate is the per-touch rate within those conversations (touches that immediately preceded a reply, divided by all touches). Conversations with more touches tend to be more engaged back-and-forths, so a higher per-touch reply rate is expected and does NOT mean later touches are more effective.

| total_outbound | n_touches | n_replied | reply_rate |
| --- | --- | --- | --- |
| 1 | 10703 | 512 | 4.78 |
| 2 | 4818 | 943 | 19.57 |
| 3 | 12690 | 1081 | 8.52 |
| 4 | 10108 | 984 | 9.73 |
| 5 | 11660 | 714 | 6.12 |
| 6 | 12552 | 461 | 3.67 |
| 7 | 8197 | 263 | 3.21 |
| 8 | 3264 | 110 | 3.37 |
| 9 | 1701 | 85 | 5.0 |
| 10 | 200 | 39 | 19.5 |
| 11 | 132 | 32 | 24.24 |
| 12 | 84 | 11 | 13.1 |
| 13 | 104 | 22 | 21.15 |
| 14 | 14 | 2 | 14.29 |
| 15 | 30 | 9 | 30.0 |
| 16 | 32 | 15 | 46.88 |
| 26 | 26 | 8 | 30.77 |

**OBSERVATION**: 1 touches: 4.78% (n=10703); 2 touches: 19.57% (n=4818); 3 touches: 8.52% (n=12690); 4 touches: 9.73% (n=10108); 5 touches: 6.12% (n=11660); 6 touches: 3.67% (n=12552); 7 touches: 3.21% (n=8197); 8 touches: 3.37% (n=3264); 9 touches: 5.0% (n=1701); 10 touches: 19.5% (n=200); 11 touches: 24.24% (n=132); 12 touches: 13.1% (n=84); 13 touches: 21.15% (n=104); 15 touches: 30.0% (n=30); 16 touches: 46.88% (n=32)

## REPLY RATE BY CHANNEL

| channel | n_touches | n_replied | reply_rate |
| --- | --- | --- | --- |
| linkedin_message | 76315 | 5291 | 6.93 |


## REPLY RATE BY TOUCH KIND

| touch_kind | n_touches | n_replied | reply_rate |
| --- | --- | --- | --- |
| breakup | 1159 | 82 | 7.08 |
| connection_request | 10975 | 882 | 8.04 |
| first_message | 15139 | 878 | 5.8 |
| followup | 49042 | 3449 | 7.03 |

**OBSERVATION**: breakup: 7.08% (n=1159); connection_request: 8.04% (n=10975); first_message: 5.8% (n=15139); followup: 7.03% (n=49042)

## ACCEPTANCE RATE BY CONNECTION-NOTE SHAPE

Connection acceptance is NOT directly readable from the conversation endpoint (`CONNECTION_STATUS_AVAILABLE = False` in `heyreach.py`). We infer it from conversation structure: if a prospect sent any message, the connection was accepted. If multiple outbound touches were sent but no reply came, the connection was likely accepted (LinkedIn does not allow follow-up messages to a non-connection).

**Connection outcome distribution** (across all touches):

- accepted: 14567 touches
- likely_accepted: 51562 touches
- unknown: 10186 touches

| length_band | n_touches | n_replied | reply_rate |
| --- | --- | --- | --- |
| long (300-600) | 10649 | 585 | 5.49 |
| medium (100-300) | 12164 | 975 | 8.02 |
| short (<100) | 717 | 42 | 5.86 |
| very_long (600+) | 2584 | 158 | 6.11 |


## REPLY RATE BY MESSAGE LENGTH BAND

| length_band | n_touches | n_replied | reply_rate |
| --- | --- | --- | --- |
| long (300-600) | 27422 | 1667 | 6.08 |
| medium (100-300) | 32878 | 2520 | 7.66 |
| short (<100) | 12839 | 892 | 6.95 |
| very_long (600+) | 3176 | 212 | 6.68 |

**OBSERVATION**: long (300-600): 6.08% (n=27422); medium (100-300): 7.66% (n=32878); short (<100): 6.95% (n=12839); very_long (600+): 6.68% (n=3176)

## REPLY RATE BY CTA TYPE

| cta_type | n_touches | n_replied | reply_rate |
| --- | --- | --- | --- |
| easy_out | 7497 | 481 | 6.42 |
| question | 40160 | 2962 | 7.38 |
| referral_ask | 961 | 46 | 4.79 |
| statement | 27697 | 1802 | 6.51 |

**OBSERVATION**: easy_out: 6.42% (n=7497); question: 7.38% (n=40160); referral_ask: 4.79% (n=961); statement: 6.51% (n=27697)

## REPLY RATE BY SUBJECT LINE PRESENCE

| has_subject | n_touches | n_replied | reply_rate |
| --- | --- | --- | --- |
| False | 67362 | 4800 | 7.13 |
| True | 8953 | 491 | 5.48 |


## CLASSIFICATION DISTRIBUTION (of replies)

Total replies: 5291

| category | count | pct |
| --- | --- | --- |
| unknown | 3894 | 73.6% |
| negative | 966 | 18.3% |
| positive | 178 | 3.4% |
| not_relevant | 97 | 1.8% |
| not_now | 79 | 1.5% |
| out_of_office | 36 | 0.7% |
| unsubscribe | 29 | 0.5% |
| referral | 12 | 0.2% |


## POSITIVE REPLY RATE (separately, never conflated)

- Touches: 76315
- Positive replies: 178
- Positive reply rate: 0.233%

This is the rate of positive replies per outbound touch, NOT per reply. It is a much smaller number than the reply rate and must never be conflated with it.

## REPLY DELAY DISTRIBUTION

- n: 5291
- Median: 6.1h
- Mean: 41.1h
- P25: 0.5h
- P75: 33.3h
- Min: 0.0h
- Max: 2256.1h

## REPLY RATE BY PROSPECT ROLE FAMILY

| role | n_touches | n_replied | reply_rate |
| --- | --- | --- | --- |
| consultant/advisor | 480 | 66 | 13.75 |
| finance/ops | 17103 | 1202 | 7.03 |
| founder/owner | 14715 | 968 | 6.58 |
| hr/people | 494 | 32 | 6.48 |
| manager | 17003 | 1161 | 6.83 |
| other | 10186 | 666 | 6.54 |
| sales/marketing | 4860 | 341 | 7.02 |
| tech/engineering | 676 | 50 | 7.4 |
| unknown | 31 | 1 | 3.23 |
| vp/director | 10767 | 804 | 7.47 |


## REPLY RATE BY COMPANY SIZE

| size | n_touches | n_replied | reply_rate |
| --- | --- | --- | --- |
| large | 144 | 18 | 12.5 |
| medium | 292 | 20 | 6.85 |
| small | 75876 | 5253 | 6.92 |
| unknown | 3 | 0 | 0.0 |


## HYPOTHESES

These are observations that might mean something, NOT proven learnings. Each needs a controlled experiment changing ONE variable at a time to confirm.

**H1. Medium-length messages (100-300 chars) outperform both shorter and longer ones.** 7.66% vs 6.95% (short) vs 6.08% (long). n is large in all three groups. Against: confounded with message type - connection requests are short, follow-ups are medium, and very long messages may be InMails or multi-paragraph pitches.

**H2. Questions get more replies than statements.** 7.38% vs 6.51%, both with large n. The gap is real but small (0.87 percentage points). Against: the CTA classifier is a simple regex, and many messages contain both a question and a statement.

**H3. Reply rate declines from position 5 onwards.** Position 1: 6.74% (n=26114), position 2: 7.35% (n=15411), position 3: 7.18% (n=13002), position 4: 7.60% (n=8772), position 5: 6.52% (n=6245), position 6: 5.88% (n=3913), position 7: 3.68% (n=1821). All have n>1000. Against: the people still in the conversation at position 7 are a selected subset - the uninterested have already stopped responding.

**H4. Messages without a subject line get more replies.** 7.13% vs 5.48% with subject. Both have large n. Against: subjects are used by specific campaigns and senders, so this may be a campaign effect rather than a subject effect.

**H5. Consultants/advisors reply at twice the rate of other roles.** 13.75% (n=480) vs 6-7% for most other roles. Against: n=480 is moderate, and consultants may be more responsive to outreach in general.

**NOT a hypothesis: anything about positions 10+.** Sample sizes drop below 100 and the numbers become unreliable.

## PROVEN LEARNINGS

With n>1000 in the major groups, a few things survive the sample-size objection:

1. **The overall per-touch reply rate is 6.93%, and the per-conversation rate is higher.** Of 26113 conversations, 4007 (15.34%) got at least one reply.
2. **73% of LinkedIn replies are unreadable to the rule-based classifier.** The classifier was built for email and does not transfer to short, casual LinkedIn messages. This is a measurement gap, not a finding.
3. **The positive reply rate is 0.233% per touch.** 178 positive replies from 76,315 touches. This is the real top of the funnel.
4. **Median reply time is 6.1 hours.** Most replies arrive within a day (P75 = 33.3h).
5. **No InMail messages were found in the estate.** Every message in 26,174 conversations had `isInMail: false`. The InMail capability exists in the sequence builder but is not used in any campaign that generated conversations.

## LIMITATIONS

1. **No campaign ID on conversations.** The HeyReach conversation endpoint does not expose which campaign a conversation belongs to. We cannot break down by campaign.
2. **Connection status not readable.** `CONNECTION_STATUS_AVAILABLE = False` in `heyreach.py`. We infer acceptance from the presence of an inbound message, which is necessary but not sufficient.
3. **Touch kind is inferred, not observed.** We classify connection requests by position and length, not by node type. This is approximate.
4. **64%+ of LinkedIn replies are unreadable.** The classifier was built for email and is much less effective on short, casual LinkedIn messages.
5. **No PII in this report.** Profile URLs are hashed, company names are included but could be identifying in combination with other fields.

## PROVENANCE

Read from `POST /inbox/GetConversationsV2`, paged by offset, 2026-09-14. 26174 conversations fetched of 26174 total. No write of any kind was made. Classification by `replies.classify(model=None)` (rules only, no model).
