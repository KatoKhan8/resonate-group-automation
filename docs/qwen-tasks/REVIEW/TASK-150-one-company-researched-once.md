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

## RESULT

- **STATUS:** DONE
- **COMMIT SHA:** 69729df
- **SNAPSHOT:** `2026-09-15T17:52:12+00:00 from master cf23154 550 records`
- **TESTS:** Measurement script `scripts/task150_measure.py` runs against the
  snapshot and confirms byte-identity across all contacts for all
  company-derived keys at every pipeline step.
- **FILES CHANGED:**
  - `docs/COMPANY-EVIDENCE-REUSE-2026-09-15.md` (new — deliverable)
  - `scripts/task150_measure.py` (new — measurement script)
  - This task file (moved TODO → RUNNING → REVIEW)
- **FINDINGS:**
  - **The answer is N.** Company evidence is sent once per contact, and every
    byte is identical across contacts. This holds for all five pipeline steps
    (diagnose, hook, persona_angle, linkedin_note, draft).
  - Record `surface51-com` (3 contacts): 561 chars/contact, 100% identical,
    3.0× duplication.
  - Record `directmail-com` (9 contacts): 5,265 chars/contact, 100%
    identical, 9.0× duplication.
  - Estate-wide (14 multi-contact records, 175 contacts): ~93,363 tokens of
    pure duplication per generation pass.
  - Root cause: `research.for_prompt` is not contact-aware, `research_block`
    is contact-aware in principle but all 695 rows have no `contact_key`, and
    `facts_block` reads per-record data. Every company-derived field is a
    pure function of the record.
  - The design names `generate.context_for` as the consumer, with a
    pass-scoped `company_evidence(rec)` cache. Provenance is preserved
    (claims.py reads `rec["research"]` directly, unaffected). Freshness is
    preserved (cache lives only for one generation pass; `stale_evidence`
    and `ttl_for` operate on the record, not the cache).
- **RISKS:**
  - The saving is real but modest at current estate size (~93K tokens/pass).
    It scales linearly with contact count, so it grows as the estate grows.
  - TASK-143's 7.3% evidence reference rate means this is purely a cost
    change, not a quality change. No claim of better copy should be made.
- **RECOMMENDED CLAUDE ACTION:**
  - Review the design in `docs/COMPANY-EVIDENCE-REUSE-2026-09-15.md`.
  - Integrate the `company_evidence(rec)` cache into `generate.context_for`
    in `src/generate.py`. The change is local: one new function, one call
    site change in `context_for`, no changes to `research.py`, `claims.py`,
    or `evidence.py`.
