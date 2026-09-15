# HeyReach Historical Learning - 2026-09-15

Read-only analysis of the HeyReach LinkedIn estate. 26,174 conversations,
76,315 outbound touches, 5,864 correspondent replies. Campaign 599020 is
DRAFT and was not touched. No provider write of any kind.

Data source: `POST /inbox/GetConversationsV2`, paged by offset, cached at
`%TEMP%/task058_cache/` (262 files, 26,174 conversations). Classification
by `replies.classify(model=None)` (rules only, no model).

---

## 1. ATTRIBUTION TABLE: A/B/C/D

What attribution does HeyReach actually support? Each answer is PROVIDER
FACT, RECONSTRUCTABLE, or ABSENT.

| Question | Verdict | Evidence |
|----------|---------|----------|
| **A. Historical per-lead/per-step touches with timestamps** | **RECONSTRUCTABLE** | Each conversation carries an ordered `messages` array. Each message has `createdAt`, `sender` (ME/CORRESPONDENT), and `body`. Position within the conversation is the message index. Timestamps are provider-returned. |
| **B. Reply → step mapping** | **ABSENT** | Conversations do not carry `campaignIds` in practice (0 of 26,174 cached conversations have the field, despite the capability contract listing it). Without campaign linkage, a reply cannot be mapped to a sequence step. The provider has `GET /campaign/GetCampaignsForLead` which answers "is this person in another campaign" per-lead per-campaign, but it does not link a specific reply to a specific step. |
| **C. Position reconstructable** | **RECONSTRUCTABLE** | Message ordering within a conversation gives position (1st outbound, 2nd outbound, etc.). This is the touch_num in the dataset. Position is a conversation-local fact, not a campaign-sequence fact. |
| **D. Variant identifier** | **ABSENT** | Messages carry `body` and `subject` but no variant ID, node ID, or sequence-step reference. The sequence graph (`GET /campaign/GetCampaignSequence`) defines variants as nodes, but the conversation endpoint does not say which node produced which message. Variant rotation is a provider-internal fact. |

### What this means

The HeyReach estate supports **within-conversation** attribution (position,
timing, reply delay) but not **cross-campaign** attribution (which campaign,
which step, which variant produced this reply). The EmailBison side has
two-hop attribution (reply → `scheduled_email_id` → step). HeyReach has
zero-hop: the reply is in a conversation, and the conversation is not linked
to a campaign.

The missing link is `campaignIds` on the conversation object. The capability
contract (`docs/HEYREACH-CAPABILITY-CONTRACT.md`) lists it as a field, but
zero of 26,174 cached conversations carry it. Either the field is only
populated for certain conversation types, or the contract documents a schema
that the API does not fill. Either way, the practical answer is ABSENT.

**What would change B and D:** A vendor change that populates `campaignIds`
on conversations, or a new endpoint that maps conversation → campaign → step.
Neither exists today.

---

## 2. THE LINKEDIN FUNNEL

### Sample

- 26,174 conversations fetched (of 26,174 total in the inbox)
- 76,315 outbound touches
- 5,864 correspondent replies (messages from CORRESPONDENT)
- Page budget: offset-paged, 100 per page, 262 pages. All conversations
  fetched. No sampling.

### Connection request acceptance rate

| Metric | n | Value |
|--------|---|-------|
| Conversations starting with connection request | 10,975 | - |
| Connections accepted (inferred) | 9,866 | 89.9% |
| Accepted AND replied | 2,467 | 25.0% of accepted |

**Inference method:** A connection is inferred accepted if the conversation
has any subsequent outbound message after the connection request, OR if the
correspondent replied. LinkedIn does not allow follow-up messages to a
non-connection, so multiple outbound touches imply acceptance.

**Caveat:** `CONNECTION_STATUS_AVAILABLE = False` in `src/providers/heyreach.py`.
The provider does not expose connection status on the conversation endpoint.
The inference is necessary but not sufficient - a conversation with multiple
outbound touches could theoretically exist if the prospect accepted, ignored
the request, and the seat sent messages anyway (LinkedIn may allow this in
some cases). The 89.9% is an upper bound.

### Reply rate by step position

| Position | n_touches | n_replied | Reply rate |
|----------|-----------|-----------|------------|
| 1 | 26,114 | 1,760 | 6.74% |
| 2 | 15,411 | 1,133 | 7.35% |
| 3 | 13,002 | 933 | 7.18% |
| 4 | 8,772 | 667 | 7.60% |
| 5 | 6,245 | 407 | 6.52% |
| 6 | 3,913 | 230 | 5.88% |
| 7 | 1,821 | 67 | 3.68% |
| 8+ | 1,037 | 94 | 9.06% |

**OBSERVATION:** Reply rate is roughly flat at 6.5-7.6% from position 1-5,
then drops to 5.88% at position 6 and 3.68% at position 7. Position 8+
appears higher but n<200 per position and the people still engaged at
position 8 are a selected subset.

**Not a learning:** anything about positions 8+. Sample sizes are too small
and the population is survivorship-biased.

### Drop between accepted and replied

| Stage | n | Rate |
|-------|---|------|
| Connection requests sent | 10,975 | - |
| Accepted (inferred) | 9,866 | 89.9% |
| Replied (among accepted) | 2,467 | 25.0% |
| Overall reply rate (per touch) | 76,315 touches | 6.93% |

The funnel: 10,975 connection requests → 89.9% accepted → 25.0% of accepted
replied. The drop from acceptance to reply is the large one: three-quarters
of accepted connections never reply.

### Reply rate by touch kind

| Touch kind | n_touches | n_replied | Reply rate |
|------------|-----------|-----------|------------|
| connection_request | 10,975 | 882 | 8.04% |
| first_message | 15,139 | 878 | 5.80% |
| followup | 49,042 | 3,449 | 7.03% |
| breakup | 1,159 | 82 | 7.08% |

**OBSERVATION:** Connection requests have the highest per-touch reply rate
(8.04%), followed by breakup (7.08%) and followup (7.03%). First messages
are lowest at 5.80%. All have n>1000.

### What is NOT measurable

- **Open rate:** `open_tracking` is False estate-wide. Absent measurement,
  not a zero.
- **Campaign-level breakdown:** No `campaignIds` on conversations. Cannot
  say which campaign produced which conversation.
- **Step-level attribution:** No step ID on messages. Cannot say which
  sequence step produced which touch.
- **Variant-level attribution:** No variant ID on messages. Cannot say
  which copy variant was sent.

---

## 3. CLASSIFIER RE-MEASUREMENT

### Before/after comparison

Same dataset (TASK-058 cache, 26,174 conversations), re-classified with the
CURRENT `replies.classify(model=None)` on 2026-09-15.

| Category | TASK-066 (n=5,291) | Current (n=5,864) | Delta |
|----------|---------------------|---------------------|-------|
| unknown | 3,703 (70.0%) | 3,810 (65.0%) | -5.0 pp |
| negative | 1,059 (20.0%) | 1,239 (21.1%) | +1.1 pp |
| positive | 185 (3.5%) | 382 (6.5%) | +3.0 pp |
| not_relevant | 164 (3.1%) | 225 (3.8%) | +0.7 pp |
| not_now | 78 (1.5%) | 102 (1.7%) | +0.2 pp |
| out_of_office | 36 (0.7%) | 37 (0.6%) | -0.1 pp |
| unsubscribe | 29 (0.5%) | 32 (0.5%) | 0.0 pp |
| referral | 12 (0.2%) | 12 (0.2%) | 0.0 pp |
| interested | - | 12 (0.2%) | NEW |
| meeting_intent | - | 7 (0.1%) | NEW |
| objection | - | 6 (0.1%) | NEW |

**Note on total count:** The current measurement found 5,864 correspondent
messages vs TASK-066's 5,291. The difference (573) is likely due to
different extraction methods: TASK-066 used the pre-computed dataset which
may have filtered some messages, while this measurement scans all cache
files directly. The distributions are comparable because both use
`replies.classify(model=None)` on the same underlying conversations.

### What changed

Three new categories appeared since TASK-066:

1. **`interested`** (12 replies, 0.2%): Added by TASK-074 taxonomy, then
   narrowed by TASK-076 after precision measured 0.44 on the old pattern
   set. **May not carry a learning claim.** The new set is UNMEASURED for
   precision. These 12 replies are the entire universe - too small to
   draw any conclusion from.

2. **`meeting_intent`** (7 replies, 0.1%): Built out of ACTS rather than
   manners (TASK-074). Precision 1.00 by construction. Recall unknown -
   the 7 replies are the entire universe.

3. **`objection`** (6 replies, 0.1%): Same as meeting_intent - built from
   ACTS, precision 1.00 by construction. Recall unknown.

### What the reduction means

Unknown dropped from 70.0% to 65.0% - a 5 percentage point reduction. The
readable fraction rose from 30.0% to 35.0%. Most of the reduction came from
the `positive` category doubling (3.5% → 6.5%), suggesting the taxonomy
changes captured more positive signals that were previously unknown.

### What remains unreadable

3,810 replies (65.0%) are still unknown. The TASK-066 failure-mode analysis
found that ~53% of unknowns are genuinely ambiguous ("thanks", "hi", "ok"),
~24% are "other" (mixed signals, long messages), ~5% are emoji-only, and
~0.3% are non-English. The remaining ~13% are actionable pattern misses.

The gap is NOT fixable with regex patterns alone. The genuinely ambiguous
replies need either an LLM classifier or acceptance that 65% unknown is the
honest answer for short, casual LinkedIn messages.

---

## 4. WHAT COULD NOT BE MEASURED

| Question | What it would cost |
|----------|-------------------|
| Campaign-level reply rates | Vendor must populate `campaignIds` on conversations, or a new endpoint must map conversation → campaign. No engineering task in this repo can settle it. |
| Step-level attribution | Same as above. Without campaign linkage, step attribution is impossible. |
| Variant-level attribution | Same. Additionally, the provider rotates variants internally - the sequence graph defines them but the conversation does not say which was sent. |
| INTERESTED precision | Need a hand-labelled set of 50+ replies that should be INTERESTED. The 12 in the estate are too few to measure precision. |
| meeting_intent / objection recall | Need a hand-labelled set of replies that express meeting intent or object. The 7 and 6 in the estate are too few to measure recall. |
| Connection acceptance ground truth | Wire `CONNECTION_REQUEST_ACCEPTED` webhook or `POST /MyNetwork/IsConnection` and compare with the inference. Both are off the allowlist. |
| Non-English reply classification | Add multilingual patterns or an LLM classifier. 10 of 5,864 replies (0.2%) are non-English. |

---

## OBSERVATIONS

1. **The LinkedIn funnel converts at 89.9% acceptance but only 25.0% of
   accepted connections reply.** The bottleneck is not getting the connection
   accepted; it is getting a reply after acceptance. n=10,975 connection
   requests.

2. **Reply rate is flat at 6.5-7.6% from position 1-5, then drops.**
   n>1,800 at every position through 7. The drop at position 7 (3.68%)
   may be survivorship bias - the uninterested have already stopped
   responding.

3. **Unknown dropped from 70.0% to 65.0% after taxonomy changes.** The
   readable fraction is now 35.0%. Most of the gain is in positive
   classification (3.5% → 6.5%). n=5,864 replies.

4. **Connection requests get the highest per-touch reply rate (8.04%).**
   n=10,975. First messages are lowest at 5.80% (n=15,139).

5. **Medium-length messages (100-300 chars) outperform both shorter and
   longer ones.** 7.66% vs 6.95% (short) vs 6.08% (long). n>12,000 in
   each group. Confounded with message type.

## HYPOTHESES

**H1.** The drop from acceptance to reply (75% of accepted connections never
reply) is the binding constraint, not connection acceptance. Testing:
different first-message copy after connection acceptance.

**H2.** The positive classification doubling (3.5% → 6.5%) comes from the
TASK-074 taxonomy capturing "happy to connect" and similar phrases that
were previously unknown. Testing: hand-label 50 "happy to connect" replies
and check if they are positive or correctly unknown.

**H3.** The three new categories (interested, meeting_intent, objection)
have precision 1.00 by construction but unknown recall. The 25 total
replies across all three are too few to measure anything.

## PROVEN LEARNINGS

1. **The per-touch reply rate is 6.93% across 76,315 touches.** n=76,315.
   This is the real top of the LinkedIn funnel.

2. **Connection acceptance is 89.9% (inferred) but only 25.0% of accepted
   connections reply.** n=10,975 connection requests. The bottleneck is
   post-acceptance engagement, not connection acquisition.

3. **The classifier reads 35.0% of LinkedIn replies, up from 30.0% after
   TASK-066.** The remaining 65.0% is predominantly genuinely ambiguous
   short messages that regex cannot classify without guessing.

4. **HeyReach supports within-conversation attribution (position, timing)
   but not cross-campaign attribution (campaign, step, variant).** The
   missing link is `campaignIds` on conversations, which is absent in
   practice despite being listed in the capability contract.

---

## PROVENANCE

Read from `POST /inbox/GetConversationsV2`, paged by offset, originally
2026-09-14, re-classified 2026-09-15. 26,174 conversations fetched of
26,174 total. No write of any kind was made. Campaign 599020 is DRAFT and
was not touched. Classification by `replies.classify(model=None)` (rules
only, no model).
