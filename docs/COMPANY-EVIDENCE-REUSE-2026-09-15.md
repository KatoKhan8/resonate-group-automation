# Company evidence reuse - measurement and design

**Date:** 2026-09-15
**Task:** TASK-150
**Snapshot:** `work/queue.snapshot.jsonl` — `2026-09-15T17:52:12+00:00 from master cf23154 550 records`

## The question

When Resonate OS generates copy for N contacts at one company, how many times
does that company's research text travel to OpenRouter?

## The answer

**N times. Every byte is identical.**

For every company-derived key in the context block — `company`, `domain`,
`facts`, `public_evidence`, `research` — the serialised value is
byte-identical across all contacts at the same record. There are zero
contact-specific variations in any company-derived field.

## Measurement

### Record `surface51-com` (3 contacts, 5 research rows)

| Key               | Chars/contact | Identical across all 3? |
|-------------------|:-------------:|:-----------------------:|
| `company`         | 15            | yes                     |
| `domain`          | 15            | yes                     |
| `facts`           | 531           | yes                     |
| `public_evidence` | 4             | yes                     |
| `research`        | 4             | yes                     |
| **Total**         | **561**       | **yes**                 |

- Unique company content (build once): **561 chars (~140 tokens)**
- Total sent across 3 contacts: **1,683 chars (~420 tokens)**
- Duplication factor: **3.0×**
- Waste: **1,122 chars (~280 tokens)**

Contact-specific content per contact: 86–144 chars. The company content
dominates each context by 4–6×.

### Record `directmail-com` (9 contacts, 4 research rows)

| Key               | Chars/contact | Identical across all 9? |
|-------------------|:-------------:|:-----------------------:|
| `company`         | 16            | yes                     |
| `domain`          | 16            | yes                     |
| `facts`           | 431           | yes                     |
| `public_evidence` | 2,783         | yes                     |
| `research`        | 2,019         | yes                     |
| **Total**         | **5,265**     | **yes**                 |

- Unique company content (build once): **5,265 chars (~1,316 tokens)**
- Total sent across 9 contacts: **47,385 chars (~11,846 tokens)**
- Duplication factor: **9.0×**
- Waste: **42,120 chars (~10,530 tokens)**

Contact-specific content per contact: 52–88 chars. The company content is
60–100× larger than the contact-specific portion.

### Duplication holds across all pipeline steps

For `surface51-com`, every step that includes company evidence sends the same
561 chars per contact, identically:

| Step              | Chars/contact | Identical? |
|-------------------|:-------------:|:----------:|
| `diagnose`        | 561           | yes        |
| `hook`            | 561           | yes        |
| `persona_angle`   | 561           | yes        |
| `linkedin_note`   | 561           | yes        |
| `draft`           | 561           | yes        |

The duplication is not a `draft`-only problem. Every step rebuilds the same
company block from scratch.

### Why it is always identical

`research_block` (line 145 of `src/generate.py`) is contact-aware in
principle: entries with a matching `contact_key` come first. But the docstring
states: "When no entry has a `contact_key` (the current state of all 695
rows), all are company-level and the contact match is a no-op."

`research.for_prompt` (line 499 of `src/research.py`) is not contact-aware at
all — it calls `evidence.select` on `rec["research"]` with no contact
parameter.

`facts_block` reads `rec["company_facts"]`, which is per-record, not
per-contact.

The result: every company-derived field in the context block is a pure
function of the record, independent of the contact.

### Estate-wide scope

Across the 14 multi-contact records with research (≥3 contacts each):

- **175 total contacts** across 14 records
- **28,594 chars** of unique company content (~7,148 tokens)
- **402,047 chars** sent with duplication (~100,511 tokens)
- **373,453 chars** of pure waste (~93,363 tokens)
- Average duplication factor: **14.1×**

The estate is small (91 records with contacts, 277 total contacts). As the
estate grows to hundreds of records with 5–20 contacts each, this waste
scales linearly with contact count.

## Design

### The shape

```
company_evidence(rec) -> {
    "company": str,
    "domain": str,
    "facts": {...},                          # from facts_block(rec)
    "public_evidence": [...],                # from research.for_prompt(rec)
    "research": [...],                       # from research_block(rec)
    "evidence_fingerprint": str,             # hash of source rows + retrieved_at
    "built_at": ISO-8601,
}
```

Built once per record per generation pass. Cached in a dict keyed by
`rec["id"]` for the duration of the pass.

### The consumer

`generate.context_for` is the consumer. It currently calls `facts_block(rec)`,
`research.for_prompt(rec)`, and `research_block(rec, contact)` independently
for every contact. The fix:

1. Add a module-level or pass-level cache in `generate.py`:
   `_company_cache: dict[str, dict]` keyed by `rec["id"]`.
2. Add a function `company_evidence(rec)` that checks the cache, builds the
   block on miss, and stores it.
3. `context_for` calls `company_evidence(rec)` once and merges the result
   into the block. The contact-specific fields (`contact`, `angle`,
   `angle_wording`, `product`, `sender_identity`, `evidence`, `tone`,
   `prior_contact`, `step`, `already_sent`, `siblings`) remain per-contact.

### Provenance

Every fact in `public_evidence` and `research` already carries `source_url`
and `retrieved_at`. The compaction preserves these fields verbatim — no
field is dropped, no transformation is applied to the fact text beyond the
existing `chars` truncation that already happens in `for_prompt` and
`research_block`.

`claims.py` line 447 reads `rec.get("research") or []` directly from the
record, not from the context block. The compaction does not alter
`rec["research"]` — it only changes how the context block is assembled. The
claims gate is unaffected.

### Freshness

`research.ttl_for` returns 3 days for short-lived fields (team, careers,
hiring, jobs, news, announcements, launches) and 30 days for everything else.
`research.stale_evidence` returns the rows that have outlived their TTL.

A cached company evidence object must not make stale evidence look current.
Two protections:

1. **Cache scope is a single generation pass.** The cache lives for the
   duration of one `generate.main()` invocation (or one batch), not across
   sessions. Evidence cannot age out during a pass that takes minutes.
2. **The evidence fingerprint is a hash of `(field, source_url, retrieved_at)`
   tuples.** If the record's research rows change between passes (a refresh
   replaced stale rows), the fingerprint changes and the cache misses. A
   stale cache is impossible because the cache does not outlive the pass
   that built it.

`research.stale_evidence` continues to operate on `rec["research"]` directly,
which is the source of truth. The cache is a read-only projection.

### Expected token saving

TASK-143 measured that a draft references an evidence fact 7.3% of the time.
This is a **cost change, not a quality change**. The model receives the same
facts in the same form; it receives them once instead of N times.

Per company, the saving is:

    (N - 1) × company_context_tokens

For the estate's current 14 multi-contact records:

- **~93,363 tokens** saved per generation pass
- This is the token cost of the company-derived context, not the full prompt
- Contact-specific content (name, title, persona, angle, evidence, history)
  is unaffected and continues to vary per contact

At OpenRouter's pricing for the current model, this is a direct credit
saving proportional to the contact multiplier. As the estate grows, the
saving scales with the number of multi-contact records and their contact
counts.

### What this does NOT change

- The claims gate (`claims.py`) still reads `rec["research"]` directly.
- The quality filter in `research_block` still applies.
- The TTL and staleness logic in `research.py` still applies.
- The contact-specific context (angle, evidence, history, step position) is
  unchanged.
- No provider is called differently. No record is mutated.

## Files referenced

- `src/generate.py` — `context_for` (line 511), `research_block` (line 145),
  `facts_block` (line 105)
- `src/research.py` — `for_prompt` (line 499), `ttl_for` (line 45),
  `stale_evidence` (line 78)
- `src/claims.py` — `rec.get("research")` (line 447)
- `src/evidence.py` — `select` (line 546)
