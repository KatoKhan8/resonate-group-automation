# HeyReach Learning - 2026-09-15

## WHAT THIS IS

Read-only analysis of HeyReach attribution capabilities and LinkedIn funnel metrics. Derived from the provider adapter, capability contract, and existing estate analysis (ESTATE-HEYREACH-OUTCOMES-2026-09-14).

Classifier re-measurement could not be completed: the dataset at `%TEMP%/task058_dataset.json` is missing and re-derivation requires provider access this session does not have.

## A/B/C/D ATTRIBUTION TABLE

What HeyReach actually supports for reply-to-step attribution:

| Question | Verdict | Evidence |
|----------|---------|----------|
| **A. Historical per-lead/per-step touches with timestamps** | RECONSTRUCTABLE | Conversations carry `messages` array with `createdAt` per message. Position inferable from message order within thread. Not a provider-supplied step id, but reconstructable from sequence. |
| **B. Reply -> step attribution** | ABSENT | No `scheduled_message_id`, `step_id`, or `node_id` field in conversation or message objects. EmailBison carries `scheduled_email_id` on each reply; HeyReach does not expose an equivalent. A reply can be matched to a touch by temporal proximity (the touch immediately preceding the reply), but the provider does not state which step generated it. One hop of inference, not zero. |
| **C. Position reconstructable** | YES, with caveat | Message order within a conversation gives position (1st message, 2nd message, etc.). But "position" is thread position, not sequence-step position. A conversation that branches (connection accepted vs not accepted) has different step paths, and the provider does not expose which branch a lead took. Position is reconstructable within a thread; mapping to the canonical step key (li1, li2, etc.) requires knowing the branch. |
| **D. Variant identifier** | ABSENT | No variant id, copy fingerprint, or template identifier in conversation or message objects. Campaign 565765 uses `{Icebreaker}` as a custom field variable, but the resolved value is not echoed back in the conversation. Which variant of a multi-variant step was sent is not readable from the provider. |

### Comparison to EmailBison

EmailBison's attribution is two-hop: a reply carries `scheduled_email_id`, which maps to a step via the sequence definition. HeyReach's attribution is zero-hop but weaker: no identifier travels with the reply, so attribution rests on temporal proximity and thread position.

**The practical consequence:** EmailBison can say "this reply came from step 3, variant B". HeyReach can say "this reply came after the third outbound message in this thread". The first is provider-certified; the second is inferred.

## LINKEDIN FUNNEL

From ESTATE-HEYREACH-OUTCOMES-2026-09-14 (n=76,315 touches, 26,113 conversations):

### Connection request acceptance

Not directly measurable. `CONNECTION_STATUS_AVAILABLE = False` in the adapter. The estate analysis infers acceptance from conversation structure: if a prospect sent any message, the connection was accepted. If multiple outbound touches were sent but no reply came, the connection was likely accepted (LinkedIn does not allow follow-up messages to a non-connection).

Inferred acceptance distribution:
- accepted: 14,567 touches (19.1%)
- likely_accepted: 51,562 touches (67.6%)
- unknown: 10,186 touches (13.3%)

**Denominator**: 76,315 total touches. **Page budget**: 26,174 conversations fetched (of 26,174 total in inbox), 26,113 analysed.

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
| 8+ | 937 | 84 | 8.96% |

**OBSERVATION**: Reply rate is roughly stable at 6.5-7.6% from position 1 through 6, drops to 3.68% at position 7 (n=1,821), then rises again at position 8+ (n=937, 8.96%). The rise at 8+ is over a small sample and may reflect engaged conversations that went long rather than later positions being more effective.

**Denominator**: 76,315 touches. **Page budget**: same as above.

### Drop between accepted and replied

Of conversations where the connection was accepted (accepted + likely_accepted = 66,129 touches), 5,291 received a reply.

Acceptance-to-reply rate: 5,291 / 66,129 = 8.00%

**OBSERVATION**: 92% of accepted connections did not reply. This is the drop between "they accepted" and "they engaged". The acceptance is a low-cost action (one click); a reply is a higher-cost action (composing a message). The gap is expected and does not indicate a problem with the copy.

**Denominator**: 66,129 touches where connection was accepted or likely accepted. **Page budget**: same as above.

## CLASSIFIER RE-MEASUREMENT

**STATUS: COULD NOT BE COMPLETED**

The dataset at `%TEMP%/task058_dataset.json` is missing. Re-derivation requires running `scripts/task058_heyreach_outcomes.py`, which calls the HeyReach provider API. This session does not have provider access.

The last measurement (TASK-066, 2026-09-14) classified 3,869 LinkedIn unknowns by failure mode:
- 53.4% correctly unknown (short acknowledgements: "thanks", "hi", "ok")
- 23.8% no pattern matched
- 11.9% missed positive
- 10.9% other

The taxonomy has changed since that measurement (TASK-074 added INTERESTED, MEETING_INTENT, OBJECTION as analysis categories). Re-measurement on the same dataset would show the new split, but the dataset is not available.

**What it would cost**: A session with provider access, running `scripts/task058_heyreach_outcomes.py` to re-derive the dataset, then `scripts/task066_measure.py` to re-measure the classifier. Estimated runtime: 10-15 minutes for data extraction, 2-3 minutes for measurement.

## WHAT COULD NOT BE MEASURED

1. **Variant-level reply rates**. The provider does not expose which variant of a multi-variant step was sent. A/B testing at the variant level is not possible from provider data alone. Would require internal tracking (writing the variant to a custom field and reading it back from the conversation, but `customFields` are not echoed back - confirmed live 2026-08-26).

2. **Branch-level attribution**. The provider does not expose which branch of a sequence a lead took (already-connected vs not-connected). Position is reconstructable within a thread, but mapping to the canonical step key requires knowing the branch. Would require a webhook that fires on branch decisions, or internal tracking written at sequence-build time and read back from the conversation.

3. **Classifier re-measurement after taxonomy changes**. Dataset missing, provider access required to re-derive.

4. **Connection request acceptance rate by note shape**. The existing report infers acceptance from conversation structure, but the inference is indirect. A direct measurement would require the `CONNECTION_REQUEST_ACCEPTED` webhook, which is documented by the vendor but never called from this build and not on any allowlist.

## PROVEN LEARNINGS

None. The sample sizes are large (n=76,315 touches) but the attribution is inferential, not provider-certified. The funnel numbers are observations, not learnings, until variant and branch attribution are available.

## OBSERVATIONS

1. Reply rate is stable at 6.5-7.6% from position 1 through 6, with no clear decay pattern. This contradicts the hypothesis that later touches are less effective; the drop at position 7 (3.68%, n=1,821) may be a small-sample artifact or may reflect a specific step's copy rather than position itself.

2. 92% of accepted connections did not reply. Acceptance is a low-cost action; reply is a higher-cost action. The gap is expected.

3. The classifier's unknown rate (73.6% in the last measurement) is dominated by correctly-unknown replies (53.4% are short acknowledgements). The addressable part is the 23.8% "no pattern matched" and the 11.9% "missed positive". Re-measurement is needed to see if the taxonomy changes moved the split.

## HYPOTHESES

1. The drop at position 7 (3.68%) is a copy effect, not a position effect. Position 7 is `li6` in the cadence (day 18 message), which may have weaker copy than earlier positions. Testing requires variant-level attribution, which is absent.

2. The rise at position 8+ (8.96%, n=937) reflects engaged conversations that went long, not later positions being more effective. Conversations with 8+ touches are already high-engagement; the reply rate is higher because the conversation is already active, not because the 8th touch is more effective. Testing requires branch-level attribution to separate "long conversation because engaged" from "long sequence because no reply came".

## DATA QUALITY

- **Conversations analysed**: 26,113 (of 26,174 fetched, 26,174 total)
- **Total outbound touches**: 76,315
- **Average touches per conversation**: 2.9
- **Conversations with at least one reply**: 4,007 (15.34%)
- **Touches that immediately preceded a reply**: 5,291 (6.93%)
- **Replies classified as unknown/unreadable**: 3,869 of 5,291 (73.1%)

**Page budget**: 26,174 conversations fetched from inbox (all of them). No pagination limit hit; the inbox was small enough to fetch whole.

**Sampling bias**: None apparent. The inbox was fetched in full. However, the inbox is a snapshot at a point in time; conversations that ended before the snapshot and were archived are not included. The analysis is of active conversations, not all conversations ever.
