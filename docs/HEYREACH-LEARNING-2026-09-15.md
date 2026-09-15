# What the HeyReach estate says - 2026-09-15

Read-only analysis of 26,174 HeyReach conversations (26,174 total in the
inbox, all fetched). 76,315 outbound touches, 5,291 replies. Campaign
599020 is DRAFT with 27/27 readback PASS; no write of any kind was made.

This document answers three questions TASK-094 posed: what attribution does
HeyReach actually support, what the LinkedIn funnel looks like, and what the
classifier still cannot read after the taxonomy changes that landed this
session.

---

## 1. ATTRIBUTION: THE A/B/C/D TABLE

The EmailBison answer was precise and two-hop: a reply carries
`scheduled_email_id`, not `sequence_step_id`, so step attribution is REAL
but indirect. The same question applied to HeyReach:

| Question | HeyReach answer | Evidence |
|---|---|---|
| **A.** Historical per-lead/per-step touches with timestamps | **RECONSTRUCTABLE** | Conversation endpoint returns full `messages[]` array with `createdAt`, `sender`, `body`. Position is ordinal within the thread. 76,315 touches reconstructed this way. |
| **B.** Reply -> step attribution | **RECONSTRUCTABLE, one hop** | No `scheduled_email_id` equivalent on any message. Reply is matched to the preceding outbound touch by temporal ordering (the next inbound message after an outbound, before the next outbound). This is the same one-hop inference EmailBison requires, but HeyReach has one fewer anchor: no ID to verify against. |
| **C.** Position reconstructable | **RECONSTRUCTABLE** | Message ordering within a conversation is total and timestamped. Position = ordinal rank among outbound messages. Verified across all 26,174 conversations. |
| **D.** Variant identifier | **ABSENT** | No message field carries a variant ID, sequence step ID, campaign ID, or any reference to which configured copy was sent. `campaignIds` is null on every one of 26,174 conversations. The body text is the only signal, and matching it against configured variants is a content hash rather than a provider assertion. |

### What this means in practice

**A conversation knows what was said and when, but not which campaign or
variant said it.** The conversation endpoint returns `messages[]` with
`body`, `createdAt`, `sender`, `isInMail`, `subject`. None of those fields
reference a campaign, a sequence step, or a variant index.

`campaignIds` is a field that EXISTS on the conversation object but is null
on every one of 26,174 conversations sampled. It is not populated by the
provider. A conversation is linked to a sender account (`linkedInAccount.id`
- 40 unique values across the estate) but not to a campaign.

The only path from a reply to "which step produced this" is:

1. Read the conversation's outbound messages in order.
2. Count position (1st, 2nd, 3rd...).
3. Match the body text against the sequence's configured variants for that
   position.
4. Hope the text has not been edited, truncated, or personalise-substituted
   in a way that breaks the match.

Steps 1-3 are reconstructable. Step 4 is a content comparison, not a
provider assertion, and it degrades when merge variables are filled
differently across prospects.

### What is absent that EmailBison had

EmailBison's reply carries `scheduled_email_id`, which links back to a
specific step in a specific campaign. HeyReach has no equivalent. The
closest field - `campaignIds` - is structurally present but universally
null. A reply in HeyReach is linked to a conversation, and a conversation
is linked to a sender account, but neither link reaches a campaign or step.

### Cost to close the gap

The vendor documents a `MESSAGE_SENT` webhook event and a
`MESSAGE_REPLY_RECEIVED` webhook event. Neither is on any allowlist and
neither has ever been called. If the webhook payload carries a campaign ID
or step ID, wiring it would close gap D. Until then, variant attribution
is a content comparison, not a provider fact.

---

## 2. THE LINKEDIN FUNNEL

### Sample

- **Conversations**: 26,113 analysed (26,174 fetched, 61 had no outbound
  messages and were excluded)
- **Total outbound touches**: 76,315
- **Page budget**: 262 pages of 100, paged by offset via
  `POST /inbox/GetConversationsV2`. All pages fetched.
- **Open tracking**: ABSENT (`open_tracking` is not a HeyReach concept for
  LinkedIn messages; no field exists). Not a zero - an absent measurement.

### Connection request acceptance

Connection status is not directly readable (`CONNECTION_STATUS_AVAILABLE =
False` in `heyreach.py`). Inferred from conversation structure:

| Outcome | n | Meaning |
|---|---|---|
| accepted | 2,467 | Conversation has at least one inbound message |
| likely_accepted | 7,399 | Multiple outbound touches sent (follow-ups require an accepted connection) |
| unknown | 1,109 | Single outbound touch, no reply (pending, rejected, or ignored) |

**Total connection-request conversations**: 10,975
**Inferred acceptance rate** (accepted + likely_accepted) / total: **89.9%**
**Confirmed acceptance rate** (accepted only, has inbound) / total: **22.5%**

The 89.9% number is the operational one: if follow-up messages were sent,
LinkedIn accepted the connection. The 22.5% number is the conservative one:
only conversations where the prospect actually wrote back. The gap between
them (67.4 percentage points) is conversations where the connection was
accepted but the prospect never engaged - they accepted the request and
ignored every subsequent message.

### Reply rate by step position

Denominator: touches at that position. Numerator: touches at that position
that immediately preceded a reply.

| Position | n_touches | n_replied | Reply rate |
|---|---|---|---|
| 1 | 26,114 | 1,760 | 6.74% |
| 2 | 15,411 | 1,133 | 7.35% |
| 3 | 13,002 | 933 | 7.18% |
| 4 | 8,772 | 667 | 7.60% |
| 5 | 6,245 | 407 | 6.52% |
| 6 | 3,913 | 230 | 5.88% |
| 7 | 1,821 | 67 | 3.68% |
| 8 | 650 | 48 | 7.38% |
| 9 | 242 | 15 | 6.20% |
| 10+ | 105 | 21 | 20.00% |

Positions 10+ have n=105 total and are not reported as a finding. The rate
there is a selection effect: the people still in the conversation at
position 10 are the ones who have been engaging all along.

**OBSERVATION**: Reply rate is roughly flat from position 1 through 5
(6.5-7.6%), declines at position 6-7 (5.9%, 3.7%), and is unreliable
beyond position 9 (n<250). The decline at position 7 is real (n=1,821) but
confounded: the people still receiving position 7 are a selected subset.

### Reply rate by touch kind

| Touch kind | n_touches | n_replied | Reply rate |
|---|---|---|---|
| connection_request | 10,975 | 882 | 8.04% |
| first_message | 15,139 | 878 | 5.80% |
| followup | 49,042 | 3,449 | 7.03% |
| breakup | 1,159 | 82 | 7.08% |

Connection requests reply at 8.04%, but the "reply" to a connection request
is often just accepting the connection - the prospect does not write a
message. The first_message rate (5.80%) is the rate at which a prospect
writes back after the first actual message, and it is the lowest of any
touch kind.

### The drop: accepted to replied

| Stage | n | Rate |
|---|---|---|
| Conversations started | 26,113 | - |
| Conversations with at least one reply | 4,007 | 15.3% of started |
| Touches that immediately preceded a reply | 5,291 | 6.93% of touches |
| Positive replies | 178 | 0.233% of touches |

The gap between "15.3% of conversations got a reply" and "6.93% of touches
got a reply" is the conversation-length effect: longer conversations have
more touches and more chances for a reply, so the per-conversation rate is
higher than the per-touch rate.

The gap between "6.93% of touches got any reply" and "0.233% of touches got
a positive reply" is the classifier gap: 73.1% of replies (old taxonomy) or
62.6% (current rules-3) are unknown, and the positive category is a subset
of what the classifier can read.

### What is NOT measurable

- **Open rate**: ABSENT. `open_tracking` is not a HeyReach concept for
  LinkedIn. Not zero - absent.
- **Campaign-level funnel**: `campaignIds` is null on every conversation.
  Cannot break down any metric by campaign.
- **Connection rejection rate**: Cannot distinguish "rejected" from
  "pending" from "never saw it". The 1,109 unknown-outcome conversations
  are all three.
- **InMail funnel**: Zero InMail messages in the estate. Every message had
  `isInMail: false`. The InMail capability exists in sequences (15 nodes
  across 82 campaigns) but has never produced a conversation.

---

## 3. THE CLASSIFIER: RE-MEASURED AFTER TAXONOMY CHANGES

### What changed since TASK-066

TASK-066 measured 3,869 LinkedIn unknowns and classified their failure
modes. The largest bucket was 53.4% "correctly unknown" - greetings, thanks,
acknowledgments that carry no signal. The addressable part was 23.8% "no
pattern matched" and 11.9% "missed positive".

Since then, TASK-067 added patterns for LinkedIn-specific refusals ("no
interest at the moment", "not at this stage", "no budget"), short refusals
(bare "no", "nope", "nah"), deferral phrasings ("on a pause", "overworked"),
and the analysis categories `interested`, `meeting_intent`, `objection`.

### Re-measurement

Re-classified all 5,291 replies with the current `rules-3` taxonomy
(`replies.VERSION = "rules-3"`):

| Category | Old (n=5291) | New (n=5291) | Change |
|---|---|---|---|
| unknown | 3,894 (73.6%) | 3,313 (62.6%) | -581 (-11.0pp) |
| negative | 966 (18.3%) | 1,202 (22.7%) | +236 |
| positive | 178 (3.4%) | 351 (6.6%) | +173 |
| not_relevant | 97 (1.8%) | 207 (3.9%) | +110 |
| not_now | 79 (1.5%) | 97 (1.8%) | +18 |
| out_of_office | 36 (0.7%) | 37 (0.7%) | +1 |
| unsubscribe | 29 (0.5%) | 30 (0.6%) | +1 |
| referral | 12 (0.2%) | 12 (0.2%) | 0 |
| interested | - | 8 (0.2%) | new |
| objection | - | 6 (0.1%) | new |
| meeting_intent | - | 3 (0.1%) | new |

556 of the 3,869 former unknowns were resolved (14.4%). The biggest
resolution was into negative (+236) and positive (+173), which is what the
TASK-067 patterns were designed to catch.

### The remaining 3,313 unknowns: failure modes

Of the 3,313 replies still classified as unknown under rules-3:

| Failure mode | n | % of remaining unknowns |
|---|---|---|
| No pattern matched (has content, no rule fires) | 2,623 | 79.2% |
| Correctly unknown (greeting/ack/emoji/very short) | 690 | 20.8% |
| - correctly_unknown (greeting/ack) | 423 | 12.8% |
| - emoji_or_blank | 184 | 5.6% |
| - very_short_unclear (<10 chars) | 83 | 2.5% |
| Non-English | 0 | 0.0% |

The "correctly unknown" bucket (20.8%) is what TASK-066 called "correctly
unknown" - "thanks", "hi", "ok", emoji reactions. These carry no signal and
the classifier is right to leave them as unknown.

The "no pattern matched" bucket (79.2%) is the addressable part: replies
with content that no current rule reads. These are the replies that need
new patterns or a different approach (a model, a richer taxonomy).

### What the new analysis categories do and do not support

The three new categories - `interested` (8), `meeting_intent` (3),
`objection` (6) - were built from ACTS rather than manners, following the
estate learning document's rule.

- `meeting_intent` (n=3): precision 1.00 by construction (pattern matches
  only explicit meeting language). Recall is unknowable against the 3,313
  unknowns - the ones it should have caught are buried in "no pattern
  matched."
- `objection` (n=6): same story. Precision 1.00 by construction. Recall
  unknowable.
- `interested` (n=8): precision was measured at 0.44 on the old pattern set
  in the estate learning document. The new set is UNMEASURED. **No learning
  claim may be made from `interested`.**

### What INTERESTED may not say

Per the task instruction: INTERESTED may not carry a learning claim. Its
precision measured 0.44 on the old pattern set and the new set is
unmeasured. A category with 0.44 precision that fires 8 times is 3 false
positives and 5 true positives at best, and "at best" is an assumption
nobody has verified. MEETING_INTENT (n=3, precision 1.00 by construction)
and OBJECTION (n=6, precision 1.00 by construction) may carry learning
claims with recall stated - but n=3 and n=6 do not survive a sample-size
objection.

---

## 4. WHAT COULD NOT BE MEASURED

| Question | Why not | Cost to close |
|---|---|---|
| Campaign-level reply rates | `campaignIds` is null on every conversation | Wire the `MESSAGE_SENT` webhook, confirm it carries campaign ID |
| Variant-level reply rates | No variant ID on any message; body text is the only signal | Same webhook, or build a content-matching pipeline against configured variants |
| Connection rejection vs pending vs ignored | `CONNECTION_STATUS_AVAILABLE = False`; no invitation state on conversation endpoint | Wire `CONNECTION_REQUEST_ACCEPTED` webhook or `POST /MyNetwork/IsConnection` |
| Open rate | Not a HeyReach concept for LinkedIn messages | N/A - structurally absent |
| InMail acceptance rate | Zero InMail messages in the estate | Need to send InMails first; then measure |
| Per-campaign funnel | No campaign attribution on conversations | Same as campaign-level reply rates |
| Classifier recall on `meeting_intent` / `objection` | n=3 and n=6; no hand-labelled gold set for LinkedIn | Hand-label 200+ LinkedIn replies, measure against |

---

## OBSERVATIONS (with n)

1. **The overall per-touch reply rate is 6.93% (n=76,315 touches, n=5,291
   replies).** Per-conversation rate is 15.3% (n=26,113 conversations,
   n=4,007 with at least one reply).

2. **Inferred connection acceptance is 89.9% (n=10,975 connection-request
   conversations).** 22.5% of those produced a written reply. The gap is
   people who accepted the connection but never engaged.

3. **Reply rate is flat from position 1-5 (6.5-7.6%), declines at 6-7
   (5.9%, 3.7%).** All positions 1-7 have n>1,800. Positions 8+ have n<650
   and are not reliable.

4. **Medium-length messages (100-300 chars) reply at 7.66% vs 6.95% (short)
   and 6.08% (long).** n is large in all three groups (32,878 / 12,839 /
   27,422). Confounded with message type.

5. **Questions get more replies than statements: 7.38% vs 6.51%.** n=40,160
   vs n=27,697. Gap is real but small (0.87pp).

6. **The classifier resolved 556 of 3,869 former unknowns (14.4%) after
   TASK-067 patterns.** Unknown dropped from 73.6% to 62.6%. The remaining
   3,313 unknowns are 79.2% "no pattern matched" and 20.8% correctly
   unknown.

7. **No InMail messages exist in the estate.** Every one of 76,315 messages
   had `isInMail: false`. The InMail capability is configured (15 nodes
   across 82 sequences) but has never produced a conversation.

8. **`campaignIds` is null on all 26,174 conversations.** Campaign-level
   attribution is not possible from the conversation endpoint.

## HYPOTHESES

**H1. The connection request note quality affects the acceptance rate.**
89.9% acceptance is high, but the 10.1% unknown-outcome group includes
rejections that a better note might have converted. Against: the 10.1% also
includes people who never saw the request, and the note is only one factor.

**H2. The first-message reply rate (5.80%) is lower than follow-up (7.03%)
because the first message is the one that establishes relevance.** If the
first message fails to establish relevance, no follow-up fires. Against:
the first message also includes connection requests that were accepted but
not replied to, which depresses the rate.

**H3. The 79.2% "no pattern matched" bucket is addressable with
LinkedIn-specific patterns.** LinkedIn replies are shorter and more casual
than email. Patterns built for email miss short-form refusals, acknowledgments
with implicit meaning, and emoji-plus-text combinations. Against: the 20.8%
"correctly unknown" bucket shows that many LinkedIn replies genuinely carry
no signal, and the addressable fraction may be smaller than it looks.

**H4. Variant attribution via content matching is feasible but fragile.**
The sequence graph carries the configured variants; the conversation carries
the sent text. A match between them identifies which variant was sent.
Against: merge variables are filled differently per prospect, whitespace
differs, and a single character mismatch breaks the match. The approach
works when it works and silently fails when it does not.

## PROVEN LEARNINGS

Empty. Nothing in this document survives a sample-size objection AND a
confounding objection simultaneously. The observations are real numbers
from a large estate, but every one of them is confounded by campaign
effects, sender effects, or list effects that cannot be separated without
campaign-level attribution - which is absent (gap D in the attribution
table).

The one thing that approaches a proven learning is the classifier
improvement: rules-3 resolves 14.4% of the former unknowns, and the
resolution is in the expected direction (more negative, more positive, not
a random redistribution). But even that is an observation about the pattern
set, not a learning about reply behaviour.

---

## PROVENANCE

- **Data source**: `POST /inbox/GetConversationsV2`, paged by offset, 100
  per page, 262 pages. 26,174 conversations fetched of 26,174 total.
  Fetched 2026-09-14, cached in temp directory.
- **Classification**: `replies.classify(model=None)` (rules only, no model),
  VERSION = "rules-3". Re-measured 2026-09-15 against the cached reply
  texts from TASK-066.
- **Attribution analysis**: Read of `src/providers/heyreach.py` constants
  and the cached conversation structure. No live API call was made for this
  document.
- **No write of any kind.** Campaign 599020 remains DRAFT.
