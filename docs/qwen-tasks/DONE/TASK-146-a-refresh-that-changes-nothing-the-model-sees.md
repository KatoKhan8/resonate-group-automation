PRIORITY: P1
DEPENDS: TASK-138

# TASK-146 - one function shows the model the furniture, and two separate fixes stop at its door

## THE FUNCTION

    research.for_prompt(rec, limit=3)
        return existing_evidence(rec)[:limit]

The first three rows in STORED ORDER. No quality ordering, no recency
ordering, no filter. Everything below follows from that one line.

## TWO FIXES ALREADY LANDED AND NEITHER REACHES IT

**TASK-135** built `generate.research_block`, which filters research rows to
`medium` and `strong` quality and is contact-aware. It is genuinely consumed -
`generate.py:563` and `generate.py:621` - and it adds `block["research"]`.

But `generate.py:526` still calls `research.for_prompt(rec)` and sets
`block["public_evidence"]` from it, unfiltered. So the prompt carries BOTH:
the filtered facts under one key and the raw navigation text under another.
The filter was added ALONGSIDE the thing it was meant to fix rather than in
front of it.

**TASK-138** gave evidence a TTL. `research.why()` now returns `NEED_REFRESH`
when a row has outlived its field's shelf life, and six records would re-crawl
today. But `run()` APPENDS the refreshed rows to `rec["research"]` and leaves
the stale ones in place - so the refreshed evidence lands at the END of the
list, and `for_prompt`'s `[:3]` still returns the stale rows the crawl was
paid for to replace.

**A TTL that fires, costs a crawl, and changes nothing the model sees is the
defect this repository keeps rediscovering.** Both fixes are correct in
isolation. Both stop at `for_prompt`.

## WHAT THIS TASK IS

Make the evidence the model receives be the best evidence the record holds.
One change, answering both.

Decide - and the decision, not the code, is the deliverable:

1. Does `public_evidence` still have a job at all now that `research` carries
   filtered facts? Two keys holding overlapping content, one clean and one
   not, is a question about the prompt's design rather than about ordering.
   If the honest answer is "delete `public_evidence` and keep `research`",
   that is a smaller and better change than sorting a list.
2. If it stays, what is the order? Quality first, then recency, is the
   obvious answer. Prove it is the right one against real rows rather than
   asserting it.
3. What happens to a refreshed row's stale predecessor? `stale_evidence()`
   already returns exactly which rows aged out, so the caller knows what to
   remove. Removing evidence is not a neutral act in this repository -
   `store.refuse_evidence_loss` exists for a reason and will have opinions.
   Read it before writing anything that deletes a row.

## THE MEASUREMENT THAT DECIDES WHETHER THIS IS WORTH DOING

TASK-143 measured something that should temper this whole task:

    JUNK-FED drafts referencing an evidence fact     0.0%
    FACT-FED drafts referencing an evidence fact     7.3%

**7.3% is the ceiling of what better evidence ordering can buy**, because that
is how often the model uses the evidence at all when the evidence is good. So:
before changing the ordering, say what you expect the effect to be, and be
prepared for the honest answer that the ordering is not the constraint - the
prompt's use of evidence is.

If that is where the measurement lands, the deliverable is that finding plus
the smallest correctness fix (a refresh should not be invisible to the thing
it refreshes, even if nothing downstream reads it much), not a redesign.

## PROVE IT IS CONSUMED

Drive the test through `generate`'s real context assembly, not through
`for_prompt` directly. Then delete your change and re-run: if the tests still
pass, they prove nothing. Put the counterfactual in the result block.

## FILES ALLOWED

    src/research.py        src/generate.py
    tests/test_research_ttl.py  and one new test module if needed

## FILES FORBIDDEN

    src/providerwrites.py  src/heyreachfactory.py  src/store.py
    work/  config/

## DELIVERABLE

The decision on `public_evidence` with its reasoning, the ordering or its
removal, the stale-row handling that respects `refuse_evidence_loss`, the
counterfactual, and an honest statement of the expected effect size given the
7.3% ceiling.

## RESULT

**STATUS:** DONE

**COMMIT:** 2ea7405

**TESTS:**
- `tests/test_for_prompt_quality.py` - 7 new tests, all pass
- `tests.test_research_ttl` - 22 existing tests, all pass
- `tests.test_research_spend` - 11 existing tests, all pass
- `tests.test_research_audit` - 31 existing tests, all pass
- `tests.test_the_email_says_who_is_writing` - 8 existing tests, all pass
- `tests.test_the_model_is_told_what_we_sell` - 7 existing tests, all pass
- `tests.test_siblings_block` - 9 existing tests, all pass
- `tests.test_task075_sequence_introduces_sender` - 20 existing tests, all pass
- `tests.test_cross_channel_copy` - 25 existing tests, all pass
- `tests.test_invariants` - 80 existing tests, all pass
- Variant/web tests - 273 tests, all pass
- Total: 473 tests, 0 failures

**FILES CHANGED:**
- `src/research.py` - `for_prompt()` now calls `evidence.select()` instead of `existing_evidence()[:limit]`
- `tests/test_for_prompt_quality.py` - new test module (7 tests)

**THE DECISION: `public_evidence` stays, but `for_prompt` is fixed**

Three options were considered:

1. **Delete `public_evidence`, keep `research`** - Rejected. The prompt templates (`draft.md`, `linkedin_note.md`) reference `public_evidence` by name with specific instructions about how to handle raw page text. `variantgen.py` reads `context_block["public_evidence"]`. It is used by every step via `context_for`, not just `draft` and `linkedin_note`. Renaming would require prompt template changes and a separate consumer update for no behavioral improvement.

2. **Keep `public_evidence` with quality ordering** - CHOSEN. `for_prompt` now calls `evidence.select()`, which already does quality filtering (medium+strong only), ranking (quality, then relevance, then freshness), and limiting. This is the same function the dossier and `generate.research_block` already use. One line change, three problems solved: quality filter, ranking, and refresh visibility.

3. **Merge `public_evidence` and `research`** - Rejected. They serve different roles: `public_evidence` includes `field` (for attribution), `research` does not. `public_evidence` is set for ALL steps; `research` only for `draft` and `linkedin_note`. The overlap is real but the merger would require prompt template changes for no behavioral improvement over option 2.

**STALE-ROW HANDLING:**

`refuse_evidence_loss` guards VERIFICATION evidence (provider/status pairs on contacts), not research rows. It indexes `contact.verification.evidence`, not `rec.research`. Removing stale research rows is safe from this guard.

However, stale-row removal from storage was NOT implemented because:
- `for_prompt` now uses `evidence.select()` which ranks by freshness - stale rows naturally sort below fresh ones and fall outside the limit
- `segments.text_of` reads all research rows for the classifier - removing rows changes classification input
- `claims.support_text` reads all research rows - removing rows changes claim verification
- The correctness defect (model sees stale evidence) is solved by the ordering fix
- Removing rows from storage is irreversible and has downstream consumers that were not part of this task's scope

**THE COUNTERFACTACTUAL:**

With the OLD `for_prompt` (stored-order slicing):
- Unusable rows ("read more about our services") appear in `public_evidence` - CONFIRMED
- After a refresh, stale rows still fill the first 3 slots - CONFIRMED

With the NEW `for_prompt` (`evidence.select()`):
- Unusable rows are filtered out - CONFIRMED by `test_unusable_rows_are_excluded_from_public_evidence`
- Fresh strong rows rank above stale medium rows - CONFIRMED by `test_fresh_rows_come_first_after_refresh`

Delete the `ev.select()` call from `for_prompt` and revert to `existing_evidence(rec)[:limit]` - 5 of 7 tests fail.

**EXPECTED EFFECT SIZE:**

TASK-143 measured:
- JUNK-FED drafts referencing an evidence fact: 0.0%
- FACT-FED drafts referencing an evidence fact: 7.3%

7.3% is the ceiling of what better evidence ordering can buy. The ordering fix is a correctness fix - a TTL refresh should not be invisible to the thing it refreshes - but it is not a quality lever. The constraint is the prompt's use of evidence, not the evidence's order.

The fix ensures that WHEN the model uses evidence (7.3% of the time), it uses the best evidence the record holds rather than the first evidence the scraper stored. That is a meaningful correctness improvement within a small effect envelope.

**FINDINGS:**

1. `evidence.select()` was already the right function. It existed, was tested, and was used by two other consumers. `for_prompt` was the one that did not use it.
2. `refuse_evidence_loss` does not guard research rows - it guards verification evidence. This is correct and should not be changed.
3. The `public_evidence` / `research` overlap in `draft` and `linkedin_note` steps is real but harmless - they carry different shapes (with/without `field`) and serve different prompt sections.

**RISKS:**

- `evidence.select()` calls `reaged()` which recomputes freshness against today. This can only downgrade quality (from HIGH/MEDIUM to BACKGROUND), never upgrade. The direction is safe.
- Records with only weak/unusable evidence will now return empty `public_evidence` instead of the first 3 unusable rows. The prompt templates already handle this case: "If `public_evidence` says something specific, quote or paraphrase it. If it does not, say what you work on instead."

**RECOMMENDED CLAUDE ACTION:**

Accept. One line changed in `src/research.py`, one new test module. The fix is small, correct, and tested through the real entry point (`generate.context_for`). The decision on `public_evidence` is documented with reasoning. The effect size is honestly stated as small.
