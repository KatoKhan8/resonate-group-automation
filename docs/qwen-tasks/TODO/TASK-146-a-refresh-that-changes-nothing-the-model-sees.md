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
