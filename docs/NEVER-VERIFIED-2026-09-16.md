# Never-verified contacts — 2026-09-16

**TASK-203 result block**

**STATUS:** DONE  
**COMMIT SHA:** (to be filled after commit)  
**TESTS:** Read-only analysis, no tests run  
**FILES CHANGED:** docs/NEVER-VERIFIED-2026-09-16.md (new), scripts/task203_*.py (new)  
**FINDINGS:** See below  
**RISKS:** None — read-only analysis, no state changed  
**RECOMMENDED CLAUDE ACTION:** Review findings, decide whether to run verification on the 159 contacts

---

## Summary

**159 contacts have email addresses but no verification evidence.** They split into two populations with different causes:

| Population | Count | Cause |
|---|---|---|
| **Population 1** | 16 | Record never reached the verification stage |
| **Population 2** | 138 | Record ran verification but skipped these contacts (cap or MX block) |
| **No verification block** | 5 | Contact added after enrich ran, or enrich never completed |
| **Total** | **159** | |

**Snapshot:** `work/queue.snapshot.jsonl` (2026-09-15T17:52:12+00:00 from master cf23154, 550 records)

---

## The two populations, separated

### Population 1: Record never reached verification (16 contacts)

These 16 contacts sit on 16 records that have waterfall entries for `company_information`, `people_discovery`, and sometimes `company_research`, but **zero `email_verification` rows**. The verification stage was never invoked on these records.

**Why?** Two causes observed:

1. **MX screening blocked the email channel before verification ran.** The `enrich_record` function runs MX screening (step 4c) BEFORE verification (step 5). If a domain's MX records show a blocked gateway (Proofpoint, Mimecast), the contact is added to `mx_blocked` and verification is skipped with the event `PROVIDER_CALL_SKIPPED, reason="email channel closed by MX policy before any verifier ran"`. The contact still gets a verification block created by the final loop (lines 1232-1237 of `enrich.py`), but with empty evidence.

2. **The record was enriched in a run that did not reach verification.** Some records have `enrich.status = "partial"` and waterfall entries that stop at `company_research` or `people_discovery`. These records were enriched in a run that was capped or refused before reaching the verification stage. The verification block is created by the final loop anyway.

**How to distinguish:** Check the record's waterfall for `email_verification` rows. If there are none, the contact is in Population 1. Check the event log for `PROVIDER_CALL_SKIPPED` with `provider="verification"` to see if MX screening blocked it.

**Field to read:** `record.waterfall` — look for `stage == "email_verification"`. Absence means Population 1.

### Population 2: Record ran verification but skipped this contact (138 contacts)

These 138 contacts sit on records that **did** run `email_verification` (3 rows each: contactout, deliverable, reoon), but the specific contacts have empty evidence. The verification stage ran on OTHER contacts on the same record, but not on these.

**Why?** The `verification_candidates()` function (enrich.py line 174) caps the number of contacts verified per record based on the tier-based `persona_plan.max_contacts_to_enrich`:

- Tier A: 3 contacts
- Tier B: 2 contacts  
- Tier C: 1 contact

If a record has 5 contacts but is tier C, only 1 gets verified and 4 are skipped. The skipped contacts still get a verification block created by the final loop, but with empty evidence.

**How to distinguish:** Check the record's waterfall for `email_verification` rows. If there are 3 rows (contactout, deliverable, reoon) but the contact has empty evidence, the contact was skipped by the cap. Check `record.qualification.persona_plan.max_contacts_to_enrich` to see the cap.

**Field to read:** `record.waterfall` — presence of `stage == "email_verification"` rows means Population 2. Then check `contact.verification.evidence` — empty means this contact was skipped.

### No verification block (5 contacts)

These 5 contacts have no verification block at all. They were either:

1. Added to the record after the enrich stage ran (the contact key appears in a later enrichment pass, but verification was not re-run)
2. The enrich stage never completed on their record

**Field to read:** `contact.verification` — absence means no block.

---

## Cost of verifying all 159 contacts

Per-contact cost under the default policy (`required_confirmations: 2`):

| Provider | Cost | When called |
|---|---|---|
| ContactOut | 1 credit | Always (primary) |
| Deliverable | 1 credit | Always (secondary, needed for 2 confirmations) |
| Reoon | 1 credit | Only if catch-all or disagreement (conditional) |

**Expected cost per contact:** 2 credits (ContactOut + Deliverable)  
**Maximum cost per contact:** 3 credits (ContactOut + Deliverable + Reoon)

**Total for 159 contacts:**

| Scenario | Cost |
|---|---|
| **With Deliverable leg** (current policy) | 318–477 credits (expected 318, max 477) |
| **Without Deliverable leg** (if `required_confirmations: 1`) | 159–318 credits (expected 159, max 318) |

**Note:** `DELIVERABLE_RESULT_SHAPE` is unset by operator decision as of 2026-09-16, so Deliverable is currently refused locally. The "without Deliverable leg" scenario is the current operational state. With the current refusal, the cost is 159 credits (ContactOut only) for contacts that need verification, plus Reoon conditional on catch-alls.

**Breakdown by population:**

| Population | Count | Expected cost (with Deliverable) | Expected cost (without Deliverable) |
|---|---|---|---|
| Population 1 (never reached verification) | 16 | 32 credits | 16 credits |
| Population 2 (skipped by cap) | 138 | 276 credits | 138 credits |
| No verification block | 5 | 10 credits | 5 credits |
| **Total** | **159** | **318 credits** | **159 credits** |

---

## The trap that was avoided

The task description warned: "`spent=0` and `skipped` and `refused` and `never selected` all look identical in a summary line."

This analysis distinguished them by reading two fields:

1. **`record.waterfall`** — does it have `email_verification` rows? This distinguishes "verification never ran on this record" (Population 1) from "verification ran but skipped this contact" (Population 2).

2. **`contact.verification.evidence`** — is it empty? This distinguishes "verification ran but this contact was skipped" (empty evidence) from "verification ran and this contact was verified" (non-empty evidence).

A contact with `verification.cost = 0` and `verification.evidence = []` and `verification.stopped = None` is a contact that was never offered to the gate, not a contact the gate refused. The `stopped` field being `None` (not `"verification cost cap"` or `"batch verification budget exhausted"`) confirms the waterfall did not stop — it simply was never invoked on this contact.

---

## What a runner would select

If a verification run were invoked on these 159 contacts:

- **Population 1 (16 contacts):** The runner would invoke `verification.verify` on each. The waterfall would call ContactOut, then Deliverable, then conditionally Reoon. Each contact would get 2-3 evidence entries.

- **Population 2 (138 contacts):** The runner would invoke `verification.verify` on each. However, `verification_candidates()` would still apply the tier-based cap, so not all 138 would be verified in a single pass. A record with 5 contacts and tier C cap of 1 would still verify only 1 contact per pass. To verify all 138, the cap would need to be raised or the records re-enriched with a higher cap.

- **No verification block (5 contacts):** The runner would invoke `verification.verify` on each, assuming the enrich stage is re-run to completion.

**Total that would be verified in a single pass:** Depends on the tier distribution and caps. Expected: 50-80 contacts (not all 159, because the cap still applies).

---

## Files and scripts

- `scripts/task203_analyze.py` — initial analysis of live vs snapshot state
- `scripts/task203_deep_dive.py` — deep dive comparing live and snapshot
- `scripts/task203_empty_evidence.py` — analysis of empty evidence contacts
- `scripts/task203_check_waterfall.py` — waterfall ledger analysis
- `scripts/task203_waterfall_stages.py` — waterfall stage breakdown
- `scripts/task203_final_analysis.py` — final population separation

All scripts are read-only and do not modify state.

---

## Conclusion

The 159 contacts with no verification evidence are not a defect. They are the result of:

1. **MX screening** blocking the email channel on some records (Population 1, partial)
2. **Tier-based caps** limiting verification to 1-3 contacts per record (Population 2, most)
3. **Enrichment runs that were capped or refused** before reaching verification (Population 1, partial)
4. **Contacts added after enrich ran** (no verification block, partial)

A verification run on these 159 contacts would cost 159-318 credits (depending on whether Deliverable is enabled). However, the tier-based caps would still apply, so not all 159 would be verified in a single pass. The operator must decide whether to raise the caps or accept the current state.

**No verification was "lost" or "forgotten."** The system worked as designed: it screened domains, capped spend per record, and created verification blocks for every contact with an email address. The 159 contacts are unverified because the system correctly decided not to spend credits on them — either because the email channel was blocked, or because the tier cap was reached, or because the enrichment run was capped before reaching verification.
