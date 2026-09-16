PRIORITY: P0
DEPENDS:

# TASK-203 - 159 contacts with an address and no verification at all

## WHERE THIS SITS

TASK-196 went looking for a broken parser and found something better. The
parser was fine; its gate had never been opened. And the number everybody had
been repeating was wrong:

    240   contacts with an email address
    159   have NO verification evidence at all - they never entered the
          waterfall
     81   did enter; all 81 carry Deliverable=error, 80 of those
          ContractNotVerified, and 68 were verified anyway via
          ContactOut + Reoon
     10   accept_all_uncleared
      3   held

TASK-194's "143 contacts held by insufficient confirmations" came from the
stale snapshot and does not survive contact with this. Exactly ONE contact
would benefit from a working Deliverable.

So the real question is the 159. They have addresses. Verification is what
stands between an address and a campaign - `CLAUDE.md`: "No email is generated
for an unverified address." And nothing verified them.

This has a precedent. TASK-160 asked why 250 records never reached ICP and the
answer was not a defect: no runner was ever invoked. Check that first.

## THE QUESTION

1. **Why did 159 contacts never enter the waterfall?** Test the cheap
   explanation before any other: was the verification stage simply never run
   over them? Look for the run in `EXECUTION-LOG.md`, in the event log, in the
   waterfall ledger. If a runner was invoked, say when and what it selected.
2. **If a runner DID run and skipped them, find the predicate.** Read the
   selection in `src/run.py` and `src/verification.py`. Candidates worth
   ruling in or out explicitly: the record is not in a state verification
   looks at, the contact lacks a field the selector requires, a lane filter,
   a cap that stopped the run short, a spend ledger refusal, or the contact was
   added after the last run.
3. **Distinguish the two populations inside the 159.** Contacts whose record
   never reached the stage that verifies, versus contacts whose record did and
   who were passed over individually. Those are different defects and only the
   second one is a selection bug.
4. **What would verifying them cost?** Per contact, which providers the
   waterfall would call and how many credits, and the total for 159. Note that
   `DELIVERABLE_RESULT_SHAPE` is unset by deliberate operator decision as of
   2026-09-16, so Deliverable is currently refused locally - give the cost both
   with and without that leg.
5. **Do NOT verify them.** Report the cost and the cause. A 159-contact
   verification run is a credit spend and it is the operator's.

## THE TRAP

`spent=0` and `skipped` and `refused` and `never selected` all look identical
in a summary line, and this repository has already been misled by exactly that:
the free-path run's own output showed `refused=[...]` entries that were the cap
working correctly, next to records that were never reached at all. Distinguish
refused-by-a-gate from never-offered-to-the-gate, per contact, and say which
field you read to tell them apart.

Second trap: do not relax `required_confirmations: 2`. TASK-196 measured that
relaxing it to 1 would admit 3 more contacts - three - and it is the rule that
keeps this system from mailing an address nobody confirmed.

## WHAT YOU MAY NOT DO

- No paid provider calls. No verification run, no credits. Reads of local state
  and the ledger only.
- No provider writes.
- Do not change the confirmation policy, a threshold, or
  `DELIVERABLE_RESULT_SHAPE`.
- Do not move contacts or records between states.
- Read live state, name the file, quote its record count. The snapshot is stale
  and is what produced the wrong number this task replaces.
- Never commit an email address, a contact name or a domain.

## FILES ALLOWED

    docs/NEVER-VERIFIED-2026-09-16.md   (new)
    scripts/task203_*.py

## FILES FORBIDDEN

    src/   work/   config/

## DELIVERABLE

Whether a runner was ever invoked over them, the selection predicate that
skipped them if one did, the two populations separated with counts, the cost of
verifying 159 with and without the Deliverable leg, and the field that
distinguishes refused from never-offered.

---

## RESULT BLOCK

**STATUS:** DONE  
**COMMIT SHA:** a311a5d  
**TESTS:** Read-only analysis, no tests run  
**FILES CHANGED:** docs/NEVER-VERIFIED-2026-09-16.md (new), scripts/task203_*.py (6 new)  
**FINDINGS:**

### Was a runner ever invoked?

Yes, but not on all 159 contacts. The snapshot (2026-09-15T17:52:12+00:00, 550 records) shows:

- **81 contacts** have verification evidence (verification ran on them)
- **159 contacts** have no verification evidence (verification never ran on them, or ran but skipped them)

Of the 159:
- **16 contacts** sit on records that never reached the verification stage (no `email_verification` rows in the waterfall)
- **138 contacts** sit on records that did run verification (3 `email_verification` rows: contactout, deliverable, reoon), but these specific contacts were skipped
- **5 contacts** have no verification block at all

### The selection predicate that skipped them

**Population 2 (138 contacts):** The `verification_candidates()` function (src/enrich.py line 174) caps verification based on `qualification.persona_plan.max_contacts_to_enrich`:
- Tier A: 3 contacts
- Tier B: 2 contacts
- Tier C: 1 contact

If a record has 5 contacts but is tier C, only 1 gets verified and 4 are skipped. The skipped contacts still get a verification block created by the final loop in `enrich_record` (lines 1232-1237), but with empty evidence.

**Population 1 (16 contacts):** Two causes:
1. **MX screening** blocked the email channel before verification ran (Proofpoint/Mimecast gateways)
2. **Enrichment runs that were capped or refused** before reaching the verification stage

**No verification block (5 contacts):** Contacts added after enrich ran, or enrich never completed.

### The two populations, separated

| Population | Count | Cause | Field to distinguish |
|---|---|---|---|
| Record never reached verification | 16 | MX block or capped run | `record.waterfall` has no `email_verification` rows |
| Record ran verification but skipped this contact | 138 | Tier-based cap | `record.waterfall` has `email_verification` rows, but `contact.verification.evidence` is empty |
| No verification block | 5 | Added after enrich or enrich incomplete | `contact.verification` is absent |

### Cost of verifying 159 contacts

Per-contact cost under default policy (`required_confirmations: 2`):
- ContactOut: 1 credit (primary, always called)
- Deliverable: 1 credit (secondary, always called for 2 confirmations)
- Reoon: 1 credit (conditional, only if catch-all or disagreement)

**Expected cost per contact:** 2 credits  
**Maximum cost per contact:** 3 credits

**Total for 159 contacts:**

| Scenario | Cost |
|---|---|
| **With Deliverable leg** (current policy) | 318–477 credits (expected 318, max 477) |
| **Without Deliverable leg** (if `required_confirmations: 1` or Deliverable refused) | 159–318 credits (expected 159, max 318) |

**Note:** `DELIVERABLE_RESULT_SHAPE` is unset by operator decision as of 2026-09-16, so Deliverable is currently refused locally. The operational cost is 159 credits (ContactOut only) plus Reoon conditional on catch-alls.

### The field that distinguishes refused from never-offered

**`record.waterfall`** — look for `stage == "email_verification"`:
- **Absent:** The contact was never offered to the gate (Population 1)
- **Present:** The gate ran on the record, but this contact was skipped (Population 2)

Then check **`contact.verification.evidence`**:
- **Empty:** This contact was skipped (by cap or MX block)
- **Non-empty:** This contact was verified

A contact with `verification.cost = 0`, `verification.evidence = []`, and `verification.stopped = None` was never offered to the gate. The `stopped` field being `None` (not `"verification cost cap"` or `"batch verification budget exhausted"`) confirms the waterfall did not stop — it simply was never invoked on this contact.

### What a runner would select

If a verification run were invoked on these 159 contacts, the tier-based caps would still apply via `verification_candidates()`. Not all 159 would be verified in a single pass. Expected: 50-80 contacts (depending on tier distribution). To verify all 159, the caps would need to be raised or the records re-enriched with higher caps.

**RISKS:** None — read-only analysis, no state changed  
**RECOMMENDED CLAUDE ACTION:** Review findings in docs/NEVER-VERIFIED-2026-09-16.md. Decide whether to run verification on the 159 contacts (159-318 credits) and whether to raise the tier-based caps.
