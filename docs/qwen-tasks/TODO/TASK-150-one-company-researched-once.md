PRIORITY: P1
DEPENDS:

# TASK-150 - company evidence, sent once rather than once per person

## THE PRINCIPLE, WHICH IS ALREADY STANDING POLICY

`docs/NEXT-GENERATION-ARCHITECTURE-ROADMAP.md` ADR-3 states it: research
belongs to the ACCOUNT. A company's positioning does not differ per employee,
and at the estate's measured 2.5 contacts per domain, per-contact research
multiplies cost by 2.5 for identical output.

The roadmap says that about CRAWLING. This task is about the other half: how
many times that evidence is sent to a MODEL.

## THE QUESTION

When Resonate OS generates copy for three contacts at one company, how many
times does that company's research text travel to OpenRouter?

If the answer is three, the fix is a compact company-evidence reference built
once per company and reused - and the saving is immediate and large.

If the answer is one, say so and stop. **That is a real result and it ends
this task honestly.** Do not invent a refactor to justify the ticket.

## HOW TO MEASURE IT

Against `work/queue.snapshot.jsonl` - **quote the STAMP**.

1. Find a record with three or more contacts that has `research` rows. Name
   it by record id.
2. Build the real generation context for each contact through
   `generate.context_for` - the function production calls - without calling
   the model.
3. Count the tokens of the company-derived portion in each, and say how much
   of it is byte-identical across the three.

That last number is the answer. Identical text sent N times is the cost
multiplier, and it is measurable rather than arguable.

## IF THE DUPLICATION IS REAL, DESIGN THE FIX

Not implement - design, with the consumer named.

The shape the operator described:

    company/domain -> research once -> company facts, signals, ICP evidence,
    services, positioning, personas, angles, retrieved_at, source timestamps,
    evidence fingerprint -> reused across contacts

and contact-level generation consuming a compact relevant SUBSET plus that
contact's own evidence, rather than the whole company payload.

Two things the design must preserve, and they are not negotiable:

- **Provenance.** Every fact keeps its `source_url` and `retrieved_at`.
  `claims.py` reads `rec["research"]` directly and a compaction that breaks
  the link between a sentence and its source breaks the claims gate.
- **Freshness.** `research.ttl_for` gives short-lived fields 3 days and
  long-lived 30. A cached company object must not make stale evidence look
  current - `research.stale_evidence` already returns exactly which rows aged
  out.

## THE CEILING, SO THE EXPECTATION IS HONEST

TASK-143 measured that a draft references an evidence fact 7.3% of the time
when the evidence is good. So this is a COST change, not a quality change,
and the case for it is tokens rather than better copy. Say the expected
saving in tokens per company and be sceptical of any larger claim.

## WHAT YOU MAY NOT DO

- Do not change production code. Design and measure; Claude integrates.
- Do not call the model.
- Do not write to `work/`. No provider writes.
- Do not put real company names or domains in the document - use record ids.

## FILES ALLOWED

    docs/COMPANY-EVIDENCE-REUSE-2026-09-15.md   (new)
    scripts/task150_*.py
    the task file itself

## FILES FORBIDDEN

    src/    work/    config/

## DELIVERABLE

The duplication count on a named multi-contact record with the snapshot
stamp, the design with its named consumer if duplication is real, the
provenance and freshness argument, and the expected token saving per company.
