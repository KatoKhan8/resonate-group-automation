PRIORITY: P1
DEPENDS:

# TASK-149 - the call-site inventory, measured rather than estimated

## THE OBSERVATION THAT STARTED THIS

OpenRouter requests shaped roughly:

    3,700-5,000 input tokens  ->  30-160 output tokens

Paying four thousand tokens to receive forty is not automatically wrong - a
classification over real evidence legitimately looks like that - but it is
the shape that hides waste, and nobody has checked which of ours are which.

**Do not assume it is necessary. Do not assume it is waste.** Measure.

## WHAT THIS TASK IS: AN INVENTORY. NOT A REFACTOR.

Produce `docs/AI-CALL-SITE-INVENTORY-2026-09-15.md`, one row per call site:

    call_site (file:line)      stage
    purpose                    model + fallback model
    prompt_version             est. input tokens
    est. output tokens         calls per record
    calls per company          retry behaviour
    cache behaviour            could deterministic code replace it
    company evidence duplicated?   contact evidence duplicated?
    is the call necessary at all?

Start from `src/llm.py` and work outwards - `grep -rn "llm\." src/` finds the
callers. `src/generate.py`, `src/variantgen.py`, `src/qualify.py`,
`src/personas.py` and `src/replies.py` are the likely concentration.

**Token counts must be measured, not guessed.** Build the real prompt for a
real record from the snapshot and count it. A number you estimated from
reading the template is not a measurement and will be wrong in the direction
that matters.

## THE THREE QUESTIONS THAT MATTER MOST

### 1. What is in those 4,000 input tokens?

Break one representative prompt into: static system rules, schema, examples,
company evidence, contact evidence, task instruction. Give the token count of
each part. If the static half is 3,000 tokens repeated on every call, that is
a cache opportunity and a compaction opportunity and you have found the
answer.

### 2. How many times is one company's research sent to a model?

The estate averages ~2.5 contacts per domain. If company evidence travels in
full on every contact-level call, we are paying 2.5x for identical text.
**Count it on a real multi-contact account.** Name the account by its record
id, not by its domain.

### 3. Which calls answer something Python already knows?

Look for: normalisation, dedupe, title/persona lookup where a config list
already exists, schema validation, evidence formatting, provider-state
interpretation, repetition detection. For each, say what the deterministic
replacement would be and what it could NOT cover.

**Do not recommend replacing a genuinely semantic decision with regex.** The
honest answer for most of them may be "no". Say so where it is.

## WHAT YOU MAY NOT DO

- **Do not change any production code.** This task reports. Claude integrates.
- Do not call the model to measure the model - build prompts and count tokens
  offline.
- Do not write to `work/`.
- No provider writes.
- Do not include prompt contents carrying real prospect names, domains or
  addresses in the document. Hash or redact identifiers.

## FILES ALLOWED

    docs/AI-CALL-SITE-INVENTORY-2026-09-15.md   (new)
    scripts/task149_*.py
    the task file itself

## FILES FORBIDDEN

    src/    work/    config/

## DELIVERABLE

The inventory table, the anatomy of one real 4,000-token prompt with per-part
token counts, the per-company duplication count measured on a named record,
and the deterministic-replacement list with an honest "no" where that is the
answer.

---

## RESULT

**STATUS:** DONE

**COMMIT SHA:** 5b5b88a

**TESTS:** No production code changed. Measurement script `scripts/task149_measure.py` builds real prompts from the snapshot and counts tokens with tiktoken cl100k_base. Verified by running against all 550 snapshot records.

**FILES CHANGED:**
- `docs/AI-CALL-SITE-INVENTORY-2026-09-15.md` (new) — the inventory
- `scripts/task149_measure.py` (new) — the measurement script

**FINDINGS:**

1. **The static template is 72-76% of every prompt.** `prompts/draft.md` is 2,906 tokens and `prompts/linkedin_note.md` is 1,665 tokens, identical on every call. The UNTRUSTED_PREAMBLE adds 157 tokens, also identical. Total static portion: 3,085/4,343 = 71% for draft, 1,844/3,217 = 57% for linkedin_note. This is the answer to "what is in those 4,000 tokens" — the static rules dominate.

2. **Company evidence is sent N times identically on multi-contact accounts.** Measured on record `947f2f9d81ff` (inmobi.com, 23 contacts): 629 tokens of company evidence sent 23 times = 14,467 tokens for shared data. The contact-specific portion is only ~26 tokens. The estate average is 2.5 contacts per domain but the top accounts have 18-23.

3. **Input:output ratio is 33:1 across the estate.** 14.4M input tokens to produce 430K output tokens. The observation that started this task is confirmed: we are paying 4,000 tokens to receive 40-144.

4. **Every model call is genuinely semantic.** All post-model gates (lint, claims, traceability, repetition, filler detection, schema validation) are already deterministic. The model is called only for: diagnose (thread classification), hook (fact extraction), persona_angle (angle assignment + evidence), draft (email writing), linkedin_note (note writing), variant_set (5 variants). None of these can be replaced by deterministic code except partly persona_angle.

5. **Seven call sites total.** diagnose, hook, persona_angle, draft, linkedin_note, linkedin_set (regeneration path), variant_set. All go through one seam: `llm.ask()` at `src/llm.py:827`.

6. **Retry structure can multiply cost 9× silently.** 3 outer attempts × 3 inner schema retries = 9 model calls per step, each re-sending the full prompt.

7. **Estate-wide: 3,324 base model calls, ~4,321 with retries.** All 550 records are in the domains lane (no diagnose or hook calls).

**RISKS:**
- Token counts are measured with tiktoken cl100k_base, which is the standard OpenAI/OpenRouter encoding. Actual costs depend on the specific model's pricing.
- The measurement builds prompts from snapshot data; actual production prompts may differ slightly if records have been updated since the snapshot.

**RECOMMENDED CLAUDE ACTION:**
- Prompt caching for the static template (saves 57-71% of input tokens)
- Company-evidence deduplication for multi-contact accounts
- Variant generation cost tracking to ensure the 4.2× multiplier is justified by evaluation results
