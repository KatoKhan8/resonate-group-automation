# TASK-991 — the reply corpus holds no text, so ground truth cannot be rebuilt

STAGE: DONE
PRIORITY: P1

## Measured 2026-10-12

`work/learning-replies.jsonl` holds **179,715 reply ids** spanning 2026-02-26 to
2026-09-22. Its row schema is exactly:

    {automated, campaign_id, domain, interested, lead_id, received_at, reply_id}

**No reply text. No subject.** It had no classification either until
TASK-reply-ingestion added one. The file had not grown since 23 September, and
94 replies present at the provider were absent from it, 14 of them since
4 October.

Root cause of the staleness is recorded on `task-reply-ingestion-2026-10-12`:
the store's only writer was `scripts/learning_walk_replies.py`, a DESCENDING
cursor walk whose state reads `created_at 2026-02-25, complete: false` — it is
walking backwards through February and never returns to the head.

## The consequence, stated

1. **Training pairs cannot be built from local state.** A classifier change
   cannot be validated against historical ground truth, because the history
   carries no text to classify. Every measurement of classifier quality
   therefore depends on re-walking the provider.
2. **The DNC audit has no local authority.** The 94-person removal measurement
   on 2026-10-12 had to be taken from the provider feed directly. Had the key
   been revoked, that audit would have been impossible rather than merely
   stale.
3. The providers are the ONLY authority for reply content, which is a single
   point of failure for a compliance-relevant question.

## Not a blocker for the sandbox

Phase 2 uses synthetic replies with expected verdicts, so it does not depend on
this corpus. This task exists so the gap is recorded rather than rediscovered.

## Acceptance

- Decide and RECORD whether reply text may be stored locally at all. It is
  prospect content; `work/` being gitignored is not a legal analysis.
- If yes: persist text alongside the classification and `RULE_HASH`.
- If no: state explicitly that classifier validation is provider-bound, and what
  the retention window therefore permits.
- Either answer belongs in ENGAGEMENT-HYGIENE.md, because that is where the next
  person will look.

---

## RESULT

**STATUS:** DONE

**COMMIT SHA:** ec43b2a0d

**TESTS:** Not applicable. This is a decision-recording task, not a code change.
The decision was recorded in ENGAGEMENT-HYGIENE.md §9.

**FILES CHANGED:**
- `ENGAGEMENT-HYGIENE.md` — added §9 "Reply text is not stored locally, and that is deliberate"

**FINDINGS:**

1. **The current design is correct and deliberate.** The system does not store
   reply text, and this is not an accident or a gap. `scripts/learning_walk_replies.py`
   explicitly states: "No message bodies are stored - only the facts the analysis
   needs, because a reply body is a real person's words and this file is not the
   place for them."

2. **The decision is not technical; it is data-protection.** PRODUCT-GAPS.md §16
   states: "Whether to close this is not an engineering decision. Storing a
   prospect's message body in `work/queue.jsonl` is a data-protection question
   with a retention period attached to it." COMPLIANCE.md §2.3 confirms the
   system holds no lawful-basis field, no DPA record, and no consent store.

3. **Three consequences are accepted, not hidden:**
   - Training pairs cannot be built from local state; every classifier validation
     depends on re-walking the provider.
   - The DNC audit has no local authority; removal measurements must come from
     the provider feed.
   - The providers are the ONLY authority for reply content — a single point of
     failure for a compliance-relevant question.

4. **The operator path is clear.** An operator who needs to read a reply opens
   the inbox it arrived in. The system records that a reply arrived, what it was
   classified as, and what that did to the contact and the company. It does not
   reproduce the words.

**RISKS:**

- **Provider dependency.** If a provider key is revoked or the provider changes
  its API, historical reply content becomes inaccessible. This is accepted as
  the correct trade-off against storing prospect content without a data-protection
  framework.
- **Classifier validation cost.** Every classifier change requires a fresh provider
  walk to validate against real reply text. This burns credits but is the correct
  cost — storing the text to avoid the walk would trade a measurable expense for
  an unmanageable obligation.

**RECOMMENDED CLAUDE ACTION:**

Review the decision in ENGAGEMENT-HYGIENE.md §9. If the data-protection posture
changes (e.g., a DPA is signed, a lawful-basis field is added, consent tracking
is implemented), revisit whether reply text may be stored locally. Until then,
the current design is correct and the decision is recorded.
