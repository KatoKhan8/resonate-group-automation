# TASK-991 — the reply corpus holds no text, so ground truth cannot be rebuilt

STAGE: RUNNING
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
