# HeyReach Historical Attribution and Funnel — 2026-09-15

Read-only analysis. No provider writes. No campaign mutations. Campaign 599020
remains DRAFT. `config/.env` confirmed present (14 variables, HEYREACH_KEY
among them) — values not read.

**Sample:** 26,174 conversations fetched from `POST /inbox/GetConversationsV2`,
paged by offset at limit=100, 262 pages. 76,315 outbound touches. 5,271
touch-attributed replies (20 fewer than the original TASK-058 count of 5,291,
due to timestamp reconstruction from cache; the difference is <0.4% and does
not affect any percentage below by more than 0.1pp).

---

## 1. ATTRIBUTION TABLE (A/B/C/D)

The EmailBison side has provider-level step AND variant attribution proven end
to end (a reply carries `scheduled_email_id`, which maps to a step, which maps
to a variant). The HeyReach side is asked at the same standard.

| Question | Verdict | Evidence |
|----------|---------|----------|
| **A: Historical per-lead/per-step touches with timestamps** | **RECONSTRUCTABLE** | The conversation endpoint returns all messages in a thread with `createdAt` timestamps and `sender` (ME/CORRESPONDENT). Position is ordinal within the conversation (touch 1, 2, 3…), not a provider step ID. The TASK-058 script reconstructs this by sorting messages by time and numbering outbound ones. No step ID exists on the message object. |
| **B: Reply → step attribution** | **ABSENT (one-hop)** | A reply is attributed to the touch that immediately preceded it by time ordering. There is no `sequence_step_id`, no `nodeId`, no campaign-step reference on any message. The EmailBison side is two-hop (reply → `scheduled_email_id` → step); HeyReach is one-hop (reply → preceding outbound message by timestamp). The hop is shorter but the attribution is coarser: it says "this reply followed this message" without saying which graph node produced it. |
| **C: Position reconstructable** | **RECONSTRUCTABLE** | Position = ordinal count of outbound messages before this one in the same conversation. The dataset records `touch_num` (1-indexed position) and `total_outbound` (conversation length). This is what the reply-by-position table uses. It is NOT a graph-node position — two different graph paths can produce the same ordinal. |
| **D: Variant identifier** | **ABSENT** | Messages carry no variant ID. The HeyReach graph carries `messages: [text1, text2, ...]` as a list, and the provider rotates them itself — "the provider rotates them itself, so a variant is a graph fact rather than something this system has to assign per contact" (`src/providers/heyreach.py`). There is no way to read back WHICH variant a specific prospect received. The sequence graph defines the variants; the conversation does not record which one was sent. |

### What each verdict means for learning

- **A (reconstructable):** We know what we sent and when, at message granularity.
  We do NOT know which graph node produced it. A MESSAGE node at position 3 on
  the cold path and position 2 on the already-connected path are both "touch 2"
  in the conversation but different graph steps with different intended purposes.

- **B (one-hop, no step ID):** The reply is attributed to the preceding outbound
  message. This is sufficient for "did this message get a reply?" but NOT for
  "which step in the sequence produced this reply?" — a question the EmailBison
  side CAN answer. The gap is structural: HeyReach does not expose it.

- **C (reconstructable with caveat):** Position is ordinal, not structural. A
  prospect who was already connected receives their first message at ordinal
  position 1, same as a cold prospect's connection note. The graph paths are
  different; the ordinal says nothing about which path was taken.

- **D (absent):** No variant tracking is possible from the conversation data.
  The provider rotates variants internally and does not record which one was
  delivered. COPY-EXPERIMENTS.md's five-variant-per-step design CANNOT be
  evaluated from historical data on HeyReach. It would need a prospective
  experiment with externally tracked assignment.

### Confirmed from the data

- `campaignIds` on conversations: **None on all 26,174 conversations.** The key
  exists in the API contract but is never populated in the inbox endpoint.
  A conversation cannot be attributed to a campaign from the inbox alone.
  `/campaign/GetCampaignsForLead` CAN answer this per-lead, but was not called
  for the 26,174 conversations in this dataset.

- `customFields` on correspondentProfile: **empty on all sampled conversations.**
  Confirmed live on 2026-08-26: "HeyReach returns `customFields: []` on every
  conversation." The `record_id`, `contact_key`, `sender_id` we send in
  `customUserFields` do not come back. Profile URL matching remains the only
  correlation key.

---

## 2. LINKEDIN FUNNEL

### 2a. Connection request acceptance rate

| Outcome | Conversations | % of conn-req convs |
|---------|--------------|---------------------|
| Accepted (prospect sent at least one message) | 2,470 | 22.5% |
| Likely accepted (multiple outbound, no inbound) | 7,399 | 67.4% |
| Unknown (single outbound, no inbound) | 1,106 | 10.1% |
| **Total conversations starting with connection request** | **10,975** | **100%** |

**Denominator:** 10,975 conversations whose first outbound message was <200
chars (classified as connection_request by the TASK-058 touch_kind heuristic).

**Caveat:** "Accepted" is inferred from the presence of any inbound message.
"Likely accepted" is inferred from multiple outbound messages (LinkedIn does not
allow follow-up messages to a non-connection, unless they are InMails to Open
Profile members — and `isInMail` is false for every message in this estate).
"Unknown" includes pending requests, rejected requests, and prospects who
simply never engaged. `CONNECTION_STATUS_AVAILABLE = False` for this endpoint.

The acceptance rate is between 22.5% (confirmed replies only) and 89.9%
(including inferred acceptances). The true rate is somewhere in that range; the
estate cannot narrow it without wiring `/MyNetwork/IsConnection` or a
`CONNECTION_REQUEST_ACCEPTED` webhook, neither of which is on any allowlist.

### 2b. Reply rate by step position

From the TASK-058 dataset, positions 1-9 have n>200 each:

| Position | n_touches | n_replied | Reply rate |
|----------|-----------|-----------|------------|
| 1 | 26,114 | 1,760 | 6.74% |
| 2 | 15,411 | 1,133 | 7.35% |
| 3 | 13,002 | 933 | 7.18% |
| 4 | 8,772 | 667 | 7.60% |
| 5 | 6,245 | 407 | 6.52% |
| 6 | 3,913 | 230 | 5.88% |
| 7 | 1,821 | 67 | 3.68% |
| 8 | 650 | 48 | 7.38% |
| 9 | 242 | 15 | 6.20% |

Positions 10+ have n<100 and are not reported.

**Denominator:** All outbound touches at that ordinal position across 26,113
conversations. Position 1 includes both connection requests (10,975) and first
messages (15,139).

### 2c. Reply rate by touch kind

| Touch kind | n_touches | n_replied | Reply rate |
|------------|-----------|-----------|------------|
| Connection request | 10,975 | 882 | 8.04% |
| First message | 15,139 | 878 | 5.80% |
| Follow-up | 49,042 | 3,449 | 7.03% |
| Breakup | 1,159 | 82 | 7.08% |
| **Total** | **76,315** | **5,291** | **6.93%** |

### 2d. Drop between accepted connection and replied

| Metric | Value |
|--------|-------|
| Conversations with connection request where connection was accepted or likely accepted | 9,869 |
| Of those, conversations that got at least one reply | 2,467 |
| Drop (accepted but never replied) | 7,402 |
| **Reply rate among accepted connections** | **25.0%** |

**Denominator:** 9,869 conversations where the connection was accepted or
likely accepted (excludes 1,106 with unknown status).

### 2e. Page budget

All numbers above are from the FULL inbox: 26,174 conversations fetched across
262 pages at limit=100. This is a complete enumeration, not a sample. The
binding constraint was API time, not pagination — the dataset represents every
conversation in the inbox at the time of fetch (2026-09-14).

---

## 3. CLASSIFIER RE-MEASUREMENT

### 3a. What changed since TASK-066

TASK-066 (commit 561fbbe) added 12 new patterns across 4 categories and moved
unknown from 73.6% to 70.0%. Since then, TASK-067 added LinkedIn-specific
short-reply patterns (anchored `^sure[.?!]*$`, `^show me[.?!]*$`, etc.) and
broadened CTA classification. TASK-076 removed the bare `interesting|intriguing`
patterns from INTERESTED after measuring precision 0.44.

The classifier VERSION is `rules-3`.

### 3b. Re-measured distribution

Re-classified all 5,271 touch-attributed replies from the cached dataset using
the current `replies.classify(model=None)`:

| Category | TASK-058 original | After TASK-066 | Current (re-measured) |
|----------|-------------------|----------------|----------------------|
| unknown | 3,894 (73.6%) | 3,703 (70.0%) | 3,316 (62.9%) |
| negative | 966 (18.3%) | 1,059 (20.0%) | 1,200 (22.8%) |
| positive | 178 (3.4%) | 185 (3.5%) | 349 (6.6%) |
| not_relevant | 97 (1.8%) | 164 (3.1%) | 214 (4.1%) |
| not_now | 79 (1.5%) | 78 (1.5%) | 96 (1.8%) |
| out_of_office | 36 (0.7%) | 36 (0.7%) | 37 (0.7%) |
| unsubscribe | 29 (0.5%) | 29 (0.5%) | 30 (0.6%) |
| referral | 12 (0.2%) | 12 (0.2%) | 12 (0.2%) |
| interested | — | — | 8 (0.2%) |
| meeting_intent | — | — | 3 (0.1%) |
| objection | — | — | 6 (0.1%) |

**Readable coverage: 26.4% → 30.0% → 37.1%.** Unknown reduced from 73.6% to
62.9% across three tasks.

### 3c. Failure-mode split (addressable parts of unknown)

The TASK-066 failure-mode analysis of 3,869 unknowns found:

| Failure mode | Count | % of unknowns | Addressable? |
|--------------|-------|---------------|--------------|
| Genuinely ambiguous (correctly unknown) | 2,067 | 53.4% | No — these ARE unknown |
| No pattern matched | 920 | 23.8% | Partially — TASK-067 addressed some |
| Missed positive | 461 | 11.9% | Partially — TASK-067 added anchored affirmatives |
| Empty/non-human (emoji only) | 184 | 4.8% | No — genuinely ambiguous |
| Missed negative | 98 | 2.5% | Partially |
| Missed not_relevant | 89 | 2.3% | Partially |
| Missed referral | 35 | 0.9% | Low priority |
| Non-English | 10 | 0.3% | Out of scope |
| Missed not_now | 5 | 0.1% | Low priority |

The current re-measurement shows the addressable parts WERE partially addressed:
unknown dropped by another 387 (from 3,703 to 3,316), with corresponding
increases in negative (+141), positive (+164), and not_relevant (+50).

### 3d. What the taxonomy adds (TASK-074/076)

Three analysis categories sub-classify what production rules leave as UNKNOWN:

| Category | Count | Precision (TASK-076) | May carry learning claim? |
|----------|-------|---------------------|--------------------------|
| interested | 8 | 0.44 (UNMEASURED on new set) | **NO** — precision unmeasured after pattern removal |
| meeting_intent | 3 | 1.00 | Yes, with recall stated |
| objection | 6 | 1.00 | Yes, with recall stated |

Numbers are too small (8, 3, 6) to support any statistical claim. The
taxonomy's value is structural: it defines the categories that a future
measurement with volume can evaluate.

---

## 4. WHAT COULD NOT BE MEASURED

| Question | What it would cost |
|----------|-------------------|
| **Which campaign did this conversation come from?** | Call `/campaign/GetCampaignsForLead` for each of 26,174 conversations' leads. The route is on the allowlist and was confirmed live 2026-09-13. It would add ~261 pages of API calls at limit=100. |
| **True connection acceptance rate** | Wire `CONNECTION_REQUEST_ACCEPTED` webhook or `POST /MyNetwork/IsConnection`. Neither is on any allowlist. The vendor documents both; neither has ever been called from this repository. |
| **Which graph node produced this message?** | HeyReach does not expose this on any endpoint. The message object has 9 keys; none reference a step or node. This would require a vendor change. |
| **Which variant was delivered to this prospect?** | Same: the provider rotates variants internally and does not record which was sent. No endpoint exposes this. Would require a vendor change or a prospective experiment with external assignment tracking. |
| **INTERESTED precision on the new pattern set** | TASK-076 measured 0.44 on the OLD patterns. The bare adjective patterns were removed. The new set (8 matches) is too small to re-measure precision meaningfully. Needs ~200+ taxonomy matches before a verdict is reliable. |
| **Per-campaign reply rates on LinkedIn** | Blocked by the campaignIds absence. Requires the `/campaign/GetCampaignsForLead` call above. |
| **Reply rate by graph path (cold vs already-connected)** | Cannot be determined from conversation data alone. The two paths produce the same ordinal positions. Would require per-lead campaign status from `/campaign/GetLeadsFromCampaign` (leadConnectionStatus). |

---

## 5. OBSERVATIONS (with n)

**O1.** The per-touch reply rate is 6.93% across 76,315 touches (n=76,315).
The per-conversation reply rate is 15.34% (4,007 of 26,113 conversations got at
least one reply).

**O2.** Connection requests reply at 8.04% (n=10,975), first messages at 5.80%
(n=15,139), follow-ups at 7.03% (n=49,042). Connection requests have the
highest per-touch reply rate of any touch kind.

**O3.** 62.9% of LinkedIn replies are classified as unknown (n=5,271). This is
down from 73.6% at baseline, but still means the classifier cannot read almost
two-thirds of what prospects say on this channel.

**O4.** Medium-length messages (100-300 chars) reply at 7.66% (n=32,878) vs
6.95% for short (<100, n=12,839) and 6.08% for long (300-600, n=27,422).

**O5.** Questions get 7.38% (n=40,160) vs statements at 6.51% (n=27,697). The
gap is 0.87pp.

**O6.** Reply rate declines from position 5 onwards: position 4 is 7.60%
(n=8,772), position 5 is 6.52% (n=6,245), position 6 is 5.88% (n=3,913),
position 7 is 3.68% (n=1,821). All have n>1,000.

**O7.** 75% of connection-request conversations either got accepted (22.5%) or
are likely accepted (67.4%), but only 25.0% of accepted connections ever replied
(n=9,869 accepted, 2,467 replied). The drop between acceptance and reply is
74.9%.

**O8.** The positive reply rate is 0.66% per touch (349 positive from 5,271
replies, from 76,315 touches). This is the real top of the funnel for
qualification.

**O9.** No InMail messages were found in the estate. Every message in 26,174
conversations had `isInMail: false`.

---

## 6. HYPOTHESES

**H1.** Medium-length messages (100-300 chars) outperform both shorter and
longer ones. 7.66% vs 6.95% vs 6.08%, all with large n. Against: confounded
with message type — connection requests are short, follow-ups are medium, and
very long messages may be multi-paragraph pitches.

**H2.** Questions get more replies than statements. 7.38% vs 6.51%, both with
large n. Against: the CTA classifier is a simple regex, and many messages
contain both a question and a statement.

**H3.** Reply rate declines from position 5 onwards. Against: the people still
in the conversation at position 7 are a selected subset — the uninterested have
already stopped responding. Survivorship bias.

**H4.** The 75% drop between connection acceptance and reply (O7) means the
connection note opens the door but the first message after acceptance is where
engagement is won or lost. Against: "accepted but never replied" includes people
who accepted and simply never engaged further — they are warm connections, not
failed messages.

**NOT a hypothesis:** anything about positions 10+ (n<100), anything about
INTERESTED (precision 0.44 unmeasured on new set), or anything about open rates
(open_tracking is False estate-wide).

---

## 7. PROVEN LEARNINGS

1. **The per-touch reply rate is 6.93% and the per-conversation rate is
   15.34%.** (n=76,315 touches, n=26,113 conversations.) This is the LinkedIn
   baseline against which any experiment must be compared.

2. **62.9% of LinkedIn replies are unreadable to the rule-based classifier.**
   Down from 73.6% at baseline, but still the dominant category. The classifier
   was built for email and does not transfer fully to short, casual LinkedIn
   messages. This is a measurement gap, not a finding.

3. **The positive reply rate is 0.46% per touch** (349 positive from 76,315
   touches). This is the real top of the funnel for qualification.

4. **No campaign attribution exists on conversations.** `campaignIds` is None
   on all 26,174 conversations. Per-campaign analysis requires an additional
   API call per lead.

5. **No variant tracking exists.** The provider rotates message variants
   internally and does not record which was delivered. COPY-EXPERIMENTS.md's
   five-variant design cannot be evaluated retrospectively on HeyReach.

6. **Connection acceptance is inferable but imprecise.** The range is 22.5%-89.9%
   depending on whether "likely accepted" is counted. The true rate requires a
   vendor endpoint this repository does not call.

---

## PROVENANCE

Re-measured 2026-09-15 from the TASK-058 cache (`%TEMP%/task058_cache/`, 262
pages, 26,174 conversations) using `replies.classify(model=None)` at VERSION
`rules-3`. No provider call was made. No campaign state was mutated. The 20-reply
difference from the original 5,291 count is a timestamp-reconstruction artifact
and does not affect any percentage by more than 0.1pp.
