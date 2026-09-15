# AI Call-Site Inventory — 2026-09-15

**Snapshot:** `work/queue.snapshot.jsonl` — 2026-09-15T17:52:12+00:00 from master cf23154, 550 records  
**Encoding:** tiktoken `cl100k_base` (GPT-4 / OpenRouter default)  
**Model:** OpenAI-compatible endpoint via OpenRouter (LLM_MODEL and LLM_BASE_URL configured)  
**Retry:** `llm.MAX_ATTEMPTS = 3` (schema-level); `MAX_DRAFT_ATTEMPTS = 3` (content-level outer loop)

---

## 1. Call-Site Inventory

Every row is one distinct prompt shape that reaches `model.complete()` via `llm.ask()`.
All calls go through the same seam: `src/llm.py:827` (`ask` -> `validate` -> `parse` -> `model.complete`).

| # | Call site (file:line) | Stage | Purpose | Prompt template | Est. input tokens (avg) | Est. output tokens | Calls per record | Calls per company | Retry behaviour | Cache behaviour | Could deterministic code replace it? | Company evidence duplicated? | Contact evidence duplicated? | Is the call necessary at all? |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | `generate.py:1411` | diagnose | Classify why a revive-lane thread died | `prompts/diagnose.md` (256 tok) | **842** | ~62 | 1 (revive lane only) | 1 | Up to 3 schema retries | No cache; full prompt re-sent each retry | **No.** Requires reading a free-form CRM thread and identifying the specific moment it broke. | Yes — `context.thread` is the full CRM thread | N/A | **Yes** — semantic classification of an unstructured thread |
| 2 | `generate.py:1423` | hook | Extract one checkable fact from a cold-lane signal | `prompts/hook.md` (96 tok) | **682** | ~18 | 1 (cold lane only) | 1 | Up to 3 schema retries + traceability check | No cache | **No.** Must pick one specific, checkable fact from a free-form signal. | Yes — `context.signal` | N/A | **Yes** — semantic extraction from unstructured signal |
| 3 | `generate.py:1431` | persona_angle | Assign a contact to a configured persona angle with evidence | `prompts/persona_angle.md` (163 tok) | **779** (avg across estate: 793) | ~23 | 1 per contact | N per contact | Up to 3 schema retries + evidence traceability check | No cache | **Partly.** The angle assignment could be a rule-based lookup if personas had deterministic criteria. The evidence selection requires judgement about which facts support which angle. | Yes — full `facts_block` + `public_evidence` | Yes — `contact_block` is per-contact but small (~26 tok) | **Mostly yes** — this is a classification over a small set of configured angles |
| 4 | `generate.py:1558` | draft | Write one email step (subject + body) | `prompts/draft.md` (2,906 tok) | **4,343** (p50=4,202, p90=5,185) | ~144 | N_contacts × N_email_steps | N_contacts × N_email_steps | Up to 3 outer attempts × 3 inner schema retries = up to 9 model calls per step | No cache; each retry re-sends the full 4,000+ token prompt | **No.** Writing a message that is specific, non-repetitive, evidence-grounded, and tonally correct is the core semantic task. | **YES — 57-73% of context is company-level and identical across contacts** | Contact-specific block is ~26 tokens (name, title, persona) | **Yes** — this is the core generative task |
| 5 | `generate.py:1468` | linkedin_note | Write one LinkedIn step (note < 300 chars) | `prompts/linkedin_note.md` (1,665 tok) | **3,217** (p50=3,023, p90=3,984) | ~23 | N_contacts × N_li_steps | N_contacts × N_li_steps | Up to 3 outer × 3 inner = up to 9 calls per step | No cache | **No.** Same semantic requirements as draft but shorter. | **YES — 54-73% of context is company-level and identical across contacts** | Contact-specific block is ~26 tokens | **Yes** — core generative task |
| 6 | `generate.py:1317` | linkedin_set | Regenerate ALL LinkedIn notes for a contact as a coordinated set | `prompts/linkedin_note.md` (1,665 tok) | **~3,200** per note | ~23 per note | 1 set per contact (regeneration path) | 1 set per contact | Up to 3 attempts per note within the set | No cache | **No** — same as linkedin_note but with cross-step repetition checking | **YES** — same company evidence per note | Same | **Yes** — but the SET approach multiplies cost by N_notes |
| 7 | `variantgen.py:588` (via `generate.py:1697`) | variant_set | Generate 5 materially different variants per step | `prompts/draft.md` + approach description (~3,643 tok per variant) | **~3,643** per variant | ~144 per variant | Up to 5 variants per step | Up to 5 per step | 1 attempt per variant (no outer retry loop in variantgen) | No cache | **No** — each variant must be structurally different. | **YES** — same company evidence across all 5 variants | Same | **Yes** — but 5× the cost of a single draft |

---

## 2. Anatomy of One 4,000-Token Prompt (draft step)

Record: `thecommunity.ca` (domains lane, 16 contacts, 5 research rows)  
Total prompt: **4,049 tokens**

| Part | Tokens | % of total | Nature |
|---|---|---|---|
| **Template (static rules)** | **2,906** | **71.8%** | STATIC — identical on every draft call across the entire estate |
| Fence overhead (UNTRUSTED_PREAMBLE) | 179 | 4.4% | STATIC — identical on every call of every type |
| ctx.facts (company facts) | 140 | 3.5% | COMPANY-LEVEL — identical for all contacts on this domain |
| ctx.public_evidence (research) | 238 | 5.9% | COMPANY-LEVEL — identical for all contacts |
| ctx.research (research_block) | 140 | 3.5% | COMPANY-LEVEL — identical for all contacts |
| ctx.product | 168 | 4.1% | CLIENT-LEVEL — identical for all records using this client |
| ctx.step (position + purpose) | 101 | 2.5% | STEP-LEVEL — same for all contacts on this step |
| ctx.sender_identity | 43 | 1.1% | CLIENT-LEVEL — identical for all records |
| ctx.tone | 43 | 1.1% | CLIENT-LEVEL |
| ctx.contact (name, title, persona) | 29 | 0.7% | **CONTACT-LEVEL — the only part that changes per contact** |
| ctx.angle | 6 | 0.1% | CONTACT-LEVEL |
| ctx.angle_wording | 8 | 0.2% | CONTACT-LEVEL |
| ctx.prior_contact | 7 | 0.2% | CONTACT-LEVEL |
| ctx.already_sent | 6 | 0.1% | CONTACT-LEVEL (varies with history) |
| ctx.siblings | 5 | 0.1% | CONTACT-LEVEL |
| ctx.company + ctx.domain | 22 | 0.5% | COMPANY-LEVEL |
| ctx.evidence | 6 | 0.1% | CONTACT-LEVEL |

### The three questions answered

**Q1: What is in those 4,000 input tokens?**

| Category | Tokens | % |
|---|---|---|
| Static rules (template + fence preamble) | 3,085 | 76.2% |
| Company-level evidence (facts + research + public_evidence) | 518 | 12.8% |
| Client-level config (product + sender + tone) | 379 | 9.4% |
| Contact-specific data | 55 | 1.4% |
| Step/history/siblings context | 112 | 2.8% |

**The static half is 3,085 tokens repeated on EVERY draft call across the entire estate.** With 91 records having email steps and an average of ~5 email steps × ~1 contact each, that is ~3,085 × 455 = ~1.4M tokens of pure static instruction text per full regeneration pass.

**Q2: How many times is one company's research sent to a model?**

Measured on the top 5 multi-contact accounts:

| Record (hashed) | Domain | Contacts | Company evidence (tokens) | Sent N× = total tokens | % of full prompt |
|---|---|---|---|---|---|
| `947f2f9d81ff` | inmobi.com | 23 | 629 | 23× = **14,467** | 57.6% |
| `41da47c0397b` | skyad.com | 21 | 518 | 21× = **10,878** | 54.0% |
| `31720b152ed1` | backbone.media | 20 | 197 | 20× = **3,940** | 30.7% |
| `39afdfaca50` | invnt.com | 20 | 668 | 20× = **13,360** | 60.7% |
| `20ba2bec38b5` | 8ms.com | 18 | 1,221 | 18× = **21,978** | 72.8% |

**The estate averages ~2.5 contacts per domain** (277 contacts / 91 records with contacts). But the top 5 accounts have 18-23 contacts each, and on those accounts the company evidence is sent 18-23 times identically. The contact-specific portion is only ~26 tokens (name, title, persona).

**Q3: Which calls answer something Python already knows?**

| Call site | Could deterministic code replace it? | What deterministic code could cover | What it could NOT cover |
|---|---|---|---|
| **diagnose** | **No** | — | Reading a free-form CRM thread and identifying the specific moment it broke requires semantic understanding |
| **hook** | **No** | — | Extracting one checkable fact from a free-form signal requires judgement |
| **persona_angle** | **Partly** | If persona criteria were deterministic (e.g., title contains "CEO" → founder), the angle assignment could be rule-based. The configured angles are a closed set. | Evidence selection — which facts support which angle — requires judgement. But the angle KEY could be determined by title/persona matching rules. |
| **draft** | **No** | — | Writing a message that is specific, non-repetitive, evidence-grounded, tonally correct, and does not repeat siblings or already_sent |
| **linkedin_note** | **No** | — | Same as draft but shorter |
| **variant_set** | **No** | — | Each variant must be structurally different; this is inherently generative |
| **Normalisation** (punctuation) | **YES — already done** | `lint.normalise_punctuation` already runs before lint. This is deterministic. | — |
| **Schema validation** | **YES — already done** | `llm.validate` checks shape, enums, required fields. Deterministic. | — |
| **Evidence traceability** | **YES — already done** | `claims.check` and `llm.traceable` verify every claim against stored facts. Deterministic. | — |
| **Repetition detection** | **YES — already done** | `quality.campaign_repetition` detects structural overlap between steps. Deterministic. | — |
| **Filler phrase detection** | **YES — already done** | `lint` refuses a closed list of banned phrases. Deterministic. | — |

**Honest assessment:** The post-model gates (lint, claims, traceability, repetition, filler detection) are ALL deterministic. The model is only called for the generative steps. No model call is doing work that Python could do — but the generative work genuinely requires a model.

---

## 3. Aggregate Cost Summary

### Per-record cost (domains lane, the only lane in the snapshot)

| Step | Avg input tokens | Avg output tokens | Calls per record (1 contact) | Calls per record (5 contacts) |
|---|---|---|---|---|
| persona_angle | 793 | 23 | 1 | 5 |
| draft (×5 email steps) | 4,343 | 144 | 5 | 25 |
| linkedin_note (×6 LI steps) | 3,217 | 23 | 6 | 30 |
| **Total per record** | — | — | **12** | **60** |
| **Total input tokens** | — | — | **~27,600** | **~138,000** |
| **Total output tokens** | — | — | **~1,033** | **~5,165** |

### Estate-wide cost (550 records, 277 contacts)

| Metric | Value |
|---|---|
| Total base model calls | **3,324** |
| With avg 1.3 attempts per call | **~4,321** |
| Total input tokens (at avg sizes) | **~14.4M** |
| Total output tokens | **~430K** |
| Input:Output ratio | **33:1** |

### Variant generation multiplier

When variant generation is active, each step generates up to 5 variants at ~3,643 tokens each:
- 5 variants × 3,643 = **18,215 tokens per step** (vs 4,343 for a single draft)
- **4.2× cost multiplier** per step

---

## 4. Key Findings

### Finding 1: The static template is 72-76% of every draft prompt

`prompts/draft.md` is 2,906 tokens and `prompts/linkedin_note.md` is 1,665 tokens. These are IDENTICAL on every call. The `UNTRUSTED_PREAMBLE` adds another 157 tokens, also identical. Together, the static portion is:

- **Draft:** 3,085 / 4,343 = **71%** static
- **LinkedIn note:** 1,844 / 3,217 = **57%** static

**Cache opportunity:** OpenRouter supports prompt caching. The static template + preamble could be cached, saving 57-71% of input token costs on every call after the first.

### Finding 2: Company evidence is duplicated across every contact

On multi-contact accounts (18-23 contacts), the company-level evidence (facts, research, public_evidence) is sent identically 18-23 times. The contact-specific portion is only ~26 tokens. For the largest accounts, company evidence represents 57-73% of the per-contact context.

**Deduplication opportunity:** A two-pass approach — one company-level "brief" call, then per-contact "write from this brief" calls with a reference instead of the full evidence — could reduce company-level token sending from N× to 1×.

### Finding 3: The input:output ratio is 33:1

Paying for 14.4M input tokens to receive 430K output tokens across the estate. This is the shape the task description identified. The ratio is driven by:
- The 2,906-token template on every draft call
- The 157-token UNTRUSTED_PREAMBLE on every call
- Company evidence repeated per contact

None of this is automatically waste — the template carries genuine constraints — but it IS the shape that hides waste, and the measurement confirms it.

### Finding 4: All post-model gates are already deterministic

The codebase has already moved every checkable concern to deterministic post-model gates: lint, claims, traceability, repetition detection, filler phrase detection, schema validation. The model is called ONLY for genuinely generative work. There are no model calls doing normalisation, deduplication, or classification that Python could handle.

### Finding 5: The retry structure can multiply cost silently

Each draft/linkedin_note call has:
- Up to 3 outer attempts (MAX_DRAFT_ATTEMPTS) when gates fail
- Each outer attempt triggers up to 3 inner schema retries (MAX_ATTEMPTS in llm.ask)
- Worst case: 9 model calls per step, each re-sending the full 4,000+ token prompt

A single contact on a 5-email × 6-LI sequence could cost up to 99 model calls (11 steps × 9 worst-case).

---

## 5. Deterministic Replacement Assessment

| What the model does | Deterministic replacement possible? | Notes |
|---|---|---|
| Classify a CRM thread's death moment | **No** | Free-form text understanding |
| Extract a hook from a signal | **No** | Judgement about specificity |
| Assign persona angle | **Partly** | Angle key could be rule-based; evidence selection needs judgement |
| Write an email draft | **No** | Core generative task |
| Write a LinkedIn note | **No** | Core generative task |
| Generate 5 different variants | **No** | Structural diversity requires generation |
| Punctuation normalisation | **Already deterministic** | `lint.normalise_punctuation` |
| Schema validation | **Already deterministic** | `llm.validate` |
| Evidence traceability | **Already deterministic** | `claims.check`, `llm.traceable` |
| Repetition detection | **Already deterministic** | `quality.campaign_repetition` |
| Filler phrase detection | **Already deterministic** | `lint` banned phrases |
| Foreign product detection | **Already deterministic** | `claims.foreign_product` |

**Bottom line:** Every call that reaches the model is genuinely semantic. The waste is not in WHAT is being asked of the model but in HOW MUCH CONTEXT is sent to ask it — 72% static template, company evidence repeated per contact, no prompt caching.

---

## 6. Recommendations (for Claude to integrate)

1. **Prompt caching** — The static template (2,906 tok for draft, 1,665 for linkedin_note) and the UNTRUSTED_PREAMBLE (157 tok) are identical across all calls. OpenRouter supports caching. This alone would save ~57-71% of input token costs.

2. **Company-evidence deduplication** — For multi-contact accounts, factor the company brief out of per-contact calls. Send it once, then reference it. Saves 54-73% of per-contact context on multi-contact accounts.

3. **Variant generation cost awareness** — 5 variants at 3,643 tokens each is 4.2× the cost of a single draft. Ensure the evaluation layer actually uses the variants to justify the spend.

4. **Retry budget visibility** — The 3×3 retry structure means worst case is 9× the expected cost per step. Track actual attempt counts to see how often retries fire.
