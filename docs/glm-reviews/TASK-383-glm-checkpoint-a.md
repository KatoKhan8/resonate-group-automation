# GLM CHECKPOINT A — TASK-383

**START_MASTER_SHA:** `53dc50c8ebe158102052206712e18f229bb48a7b`
**Date:** 2026-09-29
**Worker:** Qwen (qwen-worker-8-r9)
**Protocol:** `docs/GLM-REVIEW-PROTOCOL.md` — Checkpoint A: production generation entrypoint + canonical research store
**Mode:** Read-only. No provider write, no campaign action, no file modified except this report.

---

## Summary

Seven negative controls investigated. Five HOLD, one FAILS, one is PARTIALLY VERIFIABLE from a read-only pass. The production generation entrypoint is now wired end-to-end through `generate_campaign.generate()`, called from `src/generate.py` via `_generate_via_campaign()`. The closed-loop defect from prior checkpoints has been closed. The canonical research store (`rec["research"]`) is the sole authority, with `researchpack` demoted to an unused module. The Second Brain has a real consumer that reaches rendered messages. Cross-account research leakage is structurally prevented by exact-identity matching in `packfacts`.

---

## NC1: One version-controlled production entrypoint exists

**Disposition: FALSE POSITIVE (the claim "one entrypoint" is now TRUE, not aspirational)**

### Evidence

Two modules exist:

| Module | Exists | Version-controlled | Has caller |
|--------|--------|--------------------|------------|
| `src/generate.py` | Yes | Yes | `if __name__ == "__main__"` at line 2932; `main()` at line 2823 |
| `src/generate_campaign.py` | Yes | Yes | `src/generate.py:2070`, `2465`, `2533`, `2611` |

**The chain is:**

```
python -m src.generate --live
  → src/generate.py:main() [line 2823]
    → run() [line 2893+]
      → generate_record() [line 1853]
        → _generate_via_campaign() [line 1893]
          → generate_campaign.generate() [line 2611]
```

- `src/generate.py` is the CLI entrypoint (`python -m src.generate --live`).
- `src/generate_campaign.py` is the campaign pipeline, called at `src/generate.py:2611`: `plan = generate_campaign.generate(...)`.
- `_generate_via_campaign()` is defined at `src/generate.py:2521` and called at `src/generate.py:1893` inside `generate_record()`.

**Verdict:** There is ONE version-controlled production entrypoint (`src/generate.py`) that reaches the campaign pipeline (`src/generate_campaign.py`) through a real, traced call chain. "One entrypoint" is currently TRUE. `generate_campaign.py` is not a second entrypoint — it is a module called BY the entrypoint.

**Proof type:** Static/code. The call chain is traced through imports and function calls, not runtime-observed.

---

## NC2: The Second Brain has a real consumer

**Disposition: HOLDS**

### Evidence

The Second Brain reaches a rendered message through this chain:

1. **`secondbrain.for_task("campaign_strategy", slug)`** — `src/generate_campaign.py:460`
   - Reads from `config/clients/<client>.yaml` via `clients.load()`.
   - Returns section-keyed facts (profile, market, customers, messaging).

2. **`_load_admitted_facts(sb_identity, persona, offer)`** — `src/generate_campaign.py:443-490`
   - Filters to VERIFIED and CLIENT_SUPPLIED facts.
   - Restricts to the relevant persona's angles and the selected offer's capabilities.
   - Returns a flat list of admitted facts.

3. **`sb_facts` passed to `_process_contact()`** — `src/generate_campaign.py:278`

4. **`_format_br_context(sb_facts)`** — `src/generate_campaign.py:631`
   - Formats facts as `[source] text (source: ..., verified: ...)`.

5. **`copystages.hypothesis_user(company, domain, title, facts, br_context)`** — `src/generate_campaign.py:634`
   - `br_context` is included in the prompt as "Additional context from our own data:" — `src/copystages.py:143`.

6. **Model call** — `src/generate_campaign.py:632-635`: `_call_model(model, copystages.HYPOTHESIS_SYSTEM, ...)` 
   - The hypothesis output feeds into the writer (step F), which produces the email/LinkedIn copy.

**File:line that reads Second Brain facts in a path that reaches a rendered message:**
- `src/generate_campaign.py:460` — `secondbrain.for_task("campaign_strategy", slug)`
- `src/generate_campaign.py:631` — `_format_br_context(sb_facts)`
- `src/copystages.py:143` — `business_context` included in the hypothesis prompt

**Note:** `copystages.business_context_for()` at `src/copystages.py:124` is an alternative path that also calls `secondbrain.for_task()`, but it has NO caller anywhere in `src/`. It is dead code. The active path is through `_load_admitted_facts()`.

**Proof type:** Static/code. The data flow from config YAML → Second Brain facts → model prompt → rendered copy is fully traced.

---

## NC3: Canonical research has exactly one authority

**Disposition: HOLDS**

### Evidence

**`rec["research"]` is the one canonical store.**

Writers (modules that SET `rec["research"]`):
- `src/research.py:644,657` — the production crawl
- `src/companies.py:326-329` — `evidence.make()` entries
- `src/demo.py:182-185` — demo data
- `src/demo_outreach.py:417` — demo outreach
- `src/benchmark.py:53` — benchmark fixtures
- `src/synthetic.py:270-273` — synthetic data
- `src/web/demodata.py:479` — web demo data

Readers (modules that READ `rec["research"]`):
- `src/packfacts.py:228` — `pack_for()` reads `rec.get("research")` for identity-admitted facts
- `src/generate.py:2425-2465` — `_account_sources()` projects it into the campaign pipeline's `sources`
- `src/generate_campaign.py:912` — claims gate reads it
- `src/claims.py`, `src/dossier.py`, `src/eligibility.py`, `src/icp.py`, `src/preview.py`, `src/qa.py`, `src/quality.py`, `src/report.py`, `src/segments.py` — various consumers

**`researchpack` is demoted:**
- `src/researchpack/` exists as a module (init, pack, actors, cache, facts).
- **No module outside `researchpack/` imports it.** The only `import researchpack` is in `researchpack/__init__.py:6` (self-reference in docstring example).
- It is referenced in comments at `src/enrich.py:943`, `src/packfacts.py:10,16,127`, `src/spendledger.py:139,340` — all explanatory, none functional.
- It builds packs by buying Apify actor runs, but nothing in the generation path calls `researchpack.build()`.

**No second authority found.** Every code path that reads research for a rendered message reads it from `rec["research"]`, either directly (the old pipeline's `_account_sources`) or through `packfacts.pack_for()` (the claim licence path).

**Proof type:** Static/code. Exhaustive grep for imports and access patterns.

---

## NC4: Changing an approved fact changes the resulting artifact

**Disposition: UNVERIFIED from read-only pass (code tracing confirms the data flow, but end-to-end reproduction requires a live model call)**

### Evidence — data flow traced

**Path 1: `rec["research"]` → rendered artifact**

```
rec["research"]
  → _account_sources(rec) [src/generate.py:2425]
    → account["sources"]
      → _prepare_sources(account) [src/generate_campaign.py:523]
        → sources
          → copyprompts.icp_user(company, domain, sources) [src/generate_campaign.py:603]
          → copyprompts.extract_user(company, domain, sources) [src/generate_campaign.py:617]
            → model call → extracted facts → writer → rendered copy
```

Changing any entry in `rec["research"]` changes `sources`, which changes the ICP and extract prompts, which changes the model's output, which changes the rendered artifact.

**Path 2: Second Brain fact → rendered artifact**

```
config/clients/<client>.yaml
  → secondbrain.for_task() [src/generate_campaign.py:460]
    → _load_admitted_facts() [src/generate_campaign.py:443]
      → sb_facts
        → _format_br_context() [src/generate_campaign.py:631]
          → br_context
            → copystages.hypothesis_user(..., br_context) [src/generate_campaign.py:634]
              → model call → hypothesis → writer → rendered copy
```

Changing a Second Brain fact in the client YAML changes `sb_facts`, which changes `br_context`, which changes the hypothesis prompt, which changes the model's output, which changes the rendered artifact.

**Why this is UNVERIFIED rather than HOLDS:** The protocol requires reproducing this "end to end — change a Second Brain fact or a `rec["research"]` entry, regenerate, and show the artifact differs." A read-only pass cannot call the model. The data flow is fully traced and deterministic up to the model call; the model call is the non-deterministic step where the fact actually changes the text. A unit test with `ScriptedModel` could verify this, but the task says "a claim that a unit test does this is not the same as reproducing it against the real chain."

**What would be needed to verify:** Run `python -m src.generate --live --id <test-record>` with a modified `rec["research"]` entry or a modified client YAML fact, and diff the resulting artifact against the unmodified run.

---

## NC5: No critical generation logic depends on gitignored `work/`

**Disposition: HOLDS**

### Evidence

- `.gitignore:21` — `work/` is gitignored.
- `work/v2_run.py` does NOT exist in the filesystem. `glob("work/v2_run*")` returned no files.
- No module in `src/` imports from `work/` or references `work/v2_run`:
  - `src/generate_campaign.py:14` mentions `work/v2_run.py` in a COMMENT: "`work/v2_run.py` is the reference. This module promotes it." This is historical context, not a dependency.
  - `src/contamination.py:101` mentions `work/checkpoints.json` in a COMMENT.
  - No `import work`, `from work`, or `work.` reference exists in any production module.

**Verdict:** No current, in-scope module depends on gitignored `work/` for generation. The reference in `generate_campaign.py` is a comment acknowledging the historical predecessor.

**Proof type:** Static/code. Exhaustive grep and filesystem check.

---

## NC6: No closed wiring loop with zero external consumer

**Disposition: FALSE POSITIVE (the loop is no longer closed — it has an external consumer)**

### Evidence

The five skills and their consumers:

| Skill | `consumer` field | Actual caller |
|-------|-----------------|---------------|
| `signal_verification` | `stage_a` | `src/generate_campaign.py:601` — `skills.load("signal_verification")` |
| `account_research` | `stage_b` | `src/generate_campaign.py:614` — `skills.load("account_research")` |
| `campaign_strategy` | `stage_e` | `src/generate_campaign.py:516` — `skills.load("campaign_strategy")`, `skill.procedure` passed as `system_prompt` to `campaignstrategy.for_segment()` |
| `cold_email_writing` | `stage_f` | `src/generate_campaign.py:708` — `skills.load("cold_email_writing")` |
| `linkedin_writing` | `stage_f` | `src/generate_campaign.py:709` — `skills.load("linkedin_writing")` |

**The chain from external invocation to skill execution:**

```
python -m src.generate --live
  → main() [src/generate.py:2823]
    → run() → generate_record() [src/generate.py:1853]
      → _generate_via_campaign() [src/generate.py:2521]
        → generate_campaign.generate() [src/generate_campaign.py:116]
          → skills.load("campaign_strategy") [line 516]
          → skills.load("signal_verification") [line 601]
          → skills.load("account_research") [line 614]
          → skills.load("cold_email_writing") [line 708]
          → skills.load("linkedin_writing") [line 709]
```

**The loop is NOT closed.** `generate_campaign.generate()` is called from `_generate_via_campaign()` at `src/generate.py:2611`, which is called from `generate_record()` at `src/generate.py:1893`, which is called from `run()` which is called from `main()` which is invoked by `python -m src.generate --live`. All five skills are loaded through `skills.load()` and their `procedure` fields are used as system prompts for model calls.

**Proof type:** Static/code. Full call chain traced from CLI entry to skill execution.

---

## NC7: No cross-account research leakage in the reviewed path

**Disposition: HOLDS**

### Evidence

The path: `rec["research"]` → `packfacts.pack_for()` → `bisonfactory._copylint_batch()`

**`packfacts.identity_of()` — the identity gate:**
- `src/packfacts.py:107-136`
- Takes `(row, domain, record_id=None)`.
- **Three-tier verdict:** ADMITTED, REFUSED, UNVERIFIABLE.
- Checks:
  1. If `row["record_id"]` is stamped and does not match `record_id` → REFUSED.
  2. If the row has a site key (`companyWebsite`, `website`, `companyDomain`, `domain`) → checks `same_site(row[key], domain)`. Same site → ADMITTED. Different site → REFUSED.
  3. Falls back to `source_url` host. Same site → ADMITTED. Different site → UNVERIFIABLE (not REFUSED, because the host of a LinkedIn post is LinkedIn's, not the account's).
  4. If no domain is provided → REFUSED.

**`same_site()` — the identity test:**
- `src/packfacts.py:53-59`
- `host == domain or host.endswith("." + domain) or domain.endswith("." + host)`
- Exact host match or subdomain relationship. NOT a text filter, NOT a fuzzy match.

**`pack_for()` — the pack builder:**
- `src/packfacts.py:221-244`
- Iterates `rec.get("research")` — this is ONE record's research, already scoped to that record.
- For each row, calls `identity_of(row, domain, record_id=record_id)`.
- Only ADMITTED facts enter `pack["facts"]`.
- REFUSED and UNVERIFIABLE go into `unused`.

**`bisonfactory._copylint_batch()` — the consumer:**
- `src/bisonfactory.py:575` — `pack, _ = packfacts.pack_for(by_id.get(lead.get("record_id")))`
- Looks up the record by ID, then calls `pack_for` on THAT record.
- The pack is scoped to the lead's own record.

**The join is exact identity:**
- `pack_for(rec)` reads `rec["research"]` (that record's own research) and `rec["domain"]` (that record's own domain).
- `identity_of` checks each row's site against that domain by exact host match.
- A fact from account_Y cannot enter account_X's pack because:
  1. account_X's `rec["research"]` does not contain account_Y's rows (they are different records).
  2. Even if it did (e.g., from a shared crawl), `identity_of` would REFUSE any row whose site does not match account_X's domain.

**Historical context:** The module docstring records that 50 of 71 job rows from the research pilot belonged to a DIFFERENT company when joined by `companyName` (a text filter). `packfacts` was built specifically to close that defect by replacing text filter with exact identity.

**Proof type:** Static/code. The identity mechanism is read from the source.

---

## Additional findings

### A. `copystages.business_context_for()` is dead code

- Defined at `src/copystages.py:124`.
- Calls `secondbrain.for_task()` and formats the result.
- **No caller anywhere in `src/`.** The active Second Brain path is through `_load_admitted_facts()` in `generate_campaign.py`.
- **Disposition:** EXISTING TASK (cleanup candidate, not a defect).

### B. All five skills are loaded through `skills.load()` and their `procedure` is used

- `src/skills/campaign_strategy.py` defines `SKILL` with `consumer="stage_e"`.
- `src/generate_campaign.py:516` — `skill = skills.load("campaign_strategy")` and `skill.procedure` is passed as `system_prompt` to `campaignstrategy.for_segment()`.
- All five skills are loaded and consumed:
  - `signal_verification` → line 601
  - `account_research` → line 614
  - `campaign_strategy` → line 516
  - `cold_email_writing` → line 708
  - `linkedin_writing` → line 709
- **Disposition:** No issue. All five skills have real consumers that execute their `procedure` as the system prompt for model calls.

### C. `researchpack` module exists but has zero consumers

- `src/researchpack/` is a complete module (init, pack, actors, cache, facts).
- No import from outside the module.
- **Disposition:** ACCEPTED DEFERRED RISK. The module exists, is version-controlled, and could be accidentally imported. But currently it has no consumer and does not affect generation. The operator's decision to demote it (recorded in TASK-376) is respected.

---

## Disposition summary

| # | Negative control | Disposition | Confidence |
|---|-----------------|-------------|------------|
| 1 | One version-controlled production entrypoint | FALSE POSITIVE (it IS one entrypoint now) | HIGH |
| 2 | Second Brain has a real consumer | HOLDS | HIGH |
| 3 | Canonical research has exactly one authority | HOLDS | HIGH |
| 4 | Changing an approved fact changes the artifact | UNVERIFIED (read-only pass; data flow traced, reproduction requires live run) | MEDIUM |
| 5 | No critical generation logic depends on gitignored `work/` | HOLDS | HIGH |
| 6 | No closed wiring loop with zero external consumer | FALSE POSITIVE (loop is open; `generate.py` reaches `generate_campaign.py`) | HIGH |
| 7 | No cross-account research leakage | HOLDS | HIGH |

## Additional findings

| # | Finding | Disposition |
|---|---------|-------------|
| A | `copystages.business_context_for()` is dead code | EXISTING TASK (cleanup) |
| B | All five skills loaded and consumed through `skills.load()` | NO ISSUE |
| C | `researchpack` module has zero consumers | ACCEPTED DEFERRED RISK |

---

## Reproducible read-only commands

```bash
# NC1: Trace the entrypoint chain
grep -n "generate_campaign" src/generate.py | head -20
grep -n "_generate_via_campaign" src/generate.py

# NC2: Trace Second Brain consumption
grep -n "secondbrain\|sb_facts\|_format_br_context\|_load_admitted_facts" src/generate_campaign.py
grep -n "business_context" src/copystages.py

# NC3: Verify researchpack has no consumer
grep -rn "import researchpack\|from.*researchpack" src/ --include="*.py" | grep -v "researchpack/"

# NC5: Verify no work/ dependency
grep -rn "from work\|import work\|work/v2_run" src/ --include="*.py"

# NC6: Trace skill loading
grep -n "skills.load" src/generate_campaign.py

# NC7: Verify identity mechanism
grep -n "identity_of\|same_site\|ADMITTED\|REFUSED" src/packfacts.py
```

---

## Protocol compliance

- [x] Started from current `origin/master` (`53dc50c8`)
- [x] Read-only — no production file modified
- [x] Exact file:line evidence cited
- [x] Reproducible read-only commands provided
- [x] Static/code proof distinguished from runtime proof
- [x] Unsupported claims marked UNVERIFIED
- [x] Eight dispositions used
- [x] No merge, no provider state change, no implementation created
