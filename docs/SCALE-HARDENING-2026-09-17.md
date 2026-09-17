# Scale Hardening — Phase One: Measurement and Design

**Date:** 2026-09-17
**Scope:** analysis only. No file under `src/` or `scripts/` was modified, no provider
call was made, nothing was run with `--live`, nothing was committed.
**Live channels untouched:** HeyReach 605732, EmailBison 487.

**Architectural goal being tested:** *"LLMs are NOT the normal production pipeline.
Resonate OS itself must process normal records."*

Every claim below cites `file:line` from code read on 2026-09-17. Where a number is
an estimate derived from measured inputs it says so. Where I could not establish
something it says UNKNOWN. No real prospect name, email or domain appears here.

---

## 0. The headline, before the detail

The operator's premise — that LLMs are doing normal production work and an agent must
shepherd each cohort — **is not what the code says.** Measured across `src/`:

```
src/bisonfactory.py      0 model references
src/heyreachfactory.py   0
src/providerwrites.py    0
src/collision.py         0
src/executionguard.py    0
src/verification.py      0
src/campaigns.py         0
src/assignment.py        0
src/fatigue.py           0
src/eligibility.py       0
```

Only **two** production modules import `llm` at all: `src/generate.py:26` and
`src/run.py:26`. Every model call in the repository funnels through one function,
`llm.ask` (`src/llm.py:819`), and there is exactly one `model.complete()` call site in
`src/` — `src/llm.py:827`. No bypass exists.

**Every item on the operator's priority list is already deterministic.** Normalization,
dedupe, company/contact matching, ICP, decision-maker titles, verification routing,
collision/history, campaign allocation, caps/fatigue, provider writes, readbacks,
reconciliation and READY/HOLD/DROP contain zero model calls, by design and with the
design stated in the docstrings (§1.4).

So the LLM is not the scale problem. The scale problem is three other things:

1. **The durable store is one whole-estate JSONL file, rewritten every five records**
   (`src/store.py:690`, `src/run.py:114`), and real records are **7.6× heavier** than
   the synthetic ones the 30k benchmark used. This is the bottleneck (§5).
2. **Evidence is keyed by record, not by company** (`src/evidence.py:431`), so the same
   company researched under a second record starts from zero. There is no cross-cohort
   reuse of anything paid for.
3. **The deterministic-first ladder that already exists is not observed end-to-end.**
   `waterfall.counters()` (`src/waterfall.py:556`) has **no production caller**;
   `CONTACTOUT_CACHE_HITS` has **no producer**; the free crawler produced **zero rows**
   on the whole estate while 394 records bought their research (`src/research.py:386`).

---

# DELIVERABLE 1 — THE LLM INVENTORY

## 1.1 The seam

| thing | location |
|---|---|
| The only entry point | `llm.ask(model, step, prompt, rec=None, extra_check=None, attempts=3)` — `src/llm.py:819` |
| The only `.complete()` in `src/` | `src/llm.py:827` |
| Prompt bodies | `prompts/` — exactly five files, one per `SCHEMAS` key (`src/llm.py:487`) |
| Prompt assembly | `generate.render_prompt` — `src/generate.py:723` (contract first, record fenced as untrusted via `llm.fence`, `src/llm.py:69`) |
| Retry | `MAX_ATTEMPTS = 3` (`src/llm.py:26`) inner, `MAX_DRAFT_ATTEMPTS = 3` (`src/generate.py:38`) outer — worst case 9 calls per step |
| Adapters | `NoModel` `:145` (default), `ScriptedModel` `:156` (tests), `OpenAICompatibleModel` `:173`, `QwenCliModel` `:350`; selection `from_env()` `:462` |
| Per-step call counter | `generate.model_calls` — `src/generate.py:86`, `count_model_call` `:159`. **In-memory, cleared per process.** |

`extra_check` (`src/llm.py:819`) has no caller anywhere — dead parameter.

## 1.2 The inventory, ranked by calls per domain

`N` = contacts kept per domain (measured estate average **2.5**, per
`docs/AI-CALL-SITE-INVENTORY-2026-09-15.md`; Productive config caps at 3).
`E` = generated email steps, `L` = LinkedIn steps. The module constant
`cadence.STEPS` (`src/cadence.py:42`) gives E=2, L=2; the live Productive sequence
measured E≈5, L≈6.

| Rank | Call site | Step | Question asked | Input | Output shape | Calls / domain | **Verdict** |
|---|---|---|---|---|---|---|---|
| **1** | `src/variantgen.py:588`, reached via `src/generate.py:1771` | `draft` or `linkedin_note` (chosen `variantgen.py:531`) | "Write this step again in one of five named styles so the five are materially different" | `generate.context_for(...)` flattened by `variant_prompt` (`variantgen.py:269`) + approach brief + rung purpose + optional licensed observation | same schema as the underlying step | `N × (E+L) × ≤5` → **up to ~137** | **LLM_REQUIRED**, with a deterministic pre-gate missing (§1.3a) |
| **2** | `src/generate.py:1632` (`draft`) | `draft` | "Write subject + body for this rung; first touch if `prior_contact` is false, a reply if true" | contact block, `angle`, `angle_wording`, `product`, `sender_identity`, `evidence[contact_key]`, `research`, `tone`, `step`, `already_sent`, `siblings`, plus `diagnosis`/`hook`/`sizing` (`generate.py:650-719`) | `{subject, body}` (`src/llm.py:492`) | `N × E` base = **12.5**, ≤ `×9` on retries | **LLM_REQUIRED** |
| **3** | `src/generate.py:1542` (`linkedin_note`) | `linkedin_note` | "Write one LinkedIn note for this rung, saying who is writing and one thing nothing earlier said" | as above, LinkedIn context | `{note}`, ≤300 chars, must not mention email (`src/llm.py:565`, `MAX_NOTE` `:499`) | `N × L` = **15** | **LLM_REQUIRED** |
| **4** | `src/generate.py:1391` (`_regenerate_linkedin_set`) | `linkedin_note` | Same, but regenerating the **whole** LinkedIn set so no two notes paraphrase each other | as above + in-memory siblings | `{note}` | `N × L` when triggered | **LLM_REQUIRED for the offending step; CACHEABLE for the rest** (§1.3d) |
| **5** | `src/generate.py:1505` (`persona_angle`) | `persona_angle` | "Which configured angle key fits this contact, and what evidence justifies it?" | company block, `contact_block`, `client["angles"]` (`generate.py:609`) | `{angle, evidence[]}`; `check_evidence` traceability gate (`src/llm.py:804`, called `:829`) | `≤ N`, **only when `personas.default_angle` returned None** | **DETERMINISTIC (angle) + CACHEABLE (evidence)** — §1.3b |
| **6** | `src/generate.py:1497` (`hook`) | `hook` | "One specific checkable fact about this company that would not be true of fifty others" | company block + `rec["signal"]` (`generate.py:607`) | `{hook}`; `check_hook` (`src/llm.py:769`) + `GENERIC_HOOKS` refusal (`:36`) | **≤1**, cold lane only → **0 for Productive (domains lane)** | **LLM_REQUIRED** |
| **7** | `src/generate.py:1485` (`diagnose`) | `diagnose` | "Order this CRM thread, name the day and sentence the deal died on, and which of four failure modes" | company block + `rec["context"]` as `thread` (`generate.py:605`) | `{died_on, died_because, failure_mode ∈ 4-enum, last_position?, what_changed?}`; "went cold" rejected (`src/llm.py:32`, `:530`) | **≤1**, revive lane only → **0 for Productive** | **LLM_REQUIRED** |
| **8** | `src/replies.py:851`, inside `classify` `:824` | (free-form callable) | "Classify this reply into one of the nine categories" | extracted prospect text only (`extract_prospect_text`) | `{classification ∈ CATEGORIES, confidence, reason, evidence[], classifier}` | **0 — no caller passes a model** | **DETERMINISTIC (already)** — §1.3c |
| **9** | `src/providers/xai.py:105` (`respond`) — Grok | n/a | "Research this domain; return facts with verifiable source URLs" | domain | JSON facts + `sources[]` | **0 — unwired** | **PROVIDER, then CACHEABLE** — §1.3e |

**Counts by verdict (9 seams):**

| verdict | count | which |
|---|---|---|
| **LLM_REQUIRED** | **6** | variant_set, draft, linkedin_note, linkedin_set, hook, diagnose |
| **DETERMINISTIC** | **2** | persona_angle (angle half — already wired deterministic-first), replies classifier (already rules-only) |
| **PROVIDER / CACHEABLE** | **1** | Grok company research (unwired; ContactOut + free crawl answer first) |

Running **today, for a Productive domains-lane record**: ranks 1–5 only. Ranks 6–7 are
lane-gated to zero, ranks 8–9 are not wired.

## 1.3 What would replace the non-LLM_REQUIRED work, concretely

**(a) variant_set — the gate is on the wrong side of the call.**
`variantgen._generate_one` (`src/variantgen.py:585`) calls the model *first*
(`:588`), then runs `claims.check` and `claims.foreign_product` and discards the
result if either fails (`:611-622`). `approaches_available` (`variantgen.py:220`)
already computes which approaches are licensed — `observation_led` is refused unless
`observations.resolve` licenses a real cited observation (`variantgen.py:242`,
`src/observations.py:197`). **Replacement:** extend that pre-call availability check to
ask the same question `claims.check` will ask — "does this record hold a supported
claim for this approach at all?" — using `llm.fact_strings(rec)` (`src/llm.py:585`)
and `evidence.select` (`src/evidence.py:546`). Every approach that cannot pass the
gate is skipped *before* the call rather than after. This is the single largest
saving in the inventory because it sits on the largest multiplier.

**(b) persona_angle — half of it is already deterministic; wire the other half.**
`personas.default_angle(config, persona, family)` (`src/personas.py:127`) matches an
angle key to the routing family a title belongs to, from the client's own config
(`config/clients/productive.yaml:190`, `:216`), and it already runs in the personas
stage: `contact["angle"] = default_angle(...)` at `src/personas.py:251-253`.
`generate.plan` then emits a `persona_angle` op only `if rec.get("lane") == "domains"
and not c.get("angle")` (`src/generate.py:878`). So the model is already the *residual*
path — it fires only when a persona defines several angles and no family matched.
What still forces the call is the **evidence** half: `rec["evidence"][contact_key]` is
written only by the model (`src/generate.py:1509`). **Replacement:** populate it from
`evidence.select(rec["research"], limit=3)` (`src/evidence.py:546`), which already
scores freshness, relevance and quality deterministically and returns exactly the
citable rows `claims.check` will later demand. Then the residual call disappears for
every contact whose persona has one angle or a matching family.

**(c) replies classification — leave it as it is, and say so.**
`classify` (`src/replies.py:824`) runs `classify_rules` (`:803`), then
`classify_taxonomy` (`:553`), and only then a model — and **no caller in `src/` or
`scripts/` ever passes one.** The chain is `inbound.handle(model=None)`
(`src/inbound.py:100`, `:188`) → `replies.apply(model=...)` (`:893`) → `classify`.
The seam is correct and the default is correct. No change.

**(d) linkedin_set — narrow the trigger, not the mechanism.**
The set regeneration is triggered by `quality.campaign_repetition`, a deterministic
detector (`src/generate.py:1346`), and then rewrites **every** LinkedIn note for the
contact (`src/generate.py:1384` loop over `li_specs`). **Replacement:** regenerate only
the steps the detector named, and keep the rest — they are already stored, already
linted, and in 146 live cases already carry a human approval fingerprint
(`src/approval.py:10`). This is also a correctness win: `store_step`
(`src/generate.py:750`) exists because a prior wholesale replacement silently deleted
72 of 169 approval records.

**(e) Grok — it is a declared stage with no executor, and that ordering is right.**
`waterfall.STAGES[COMPANY_INFO]` declares `{"provider": "xai", "call":
"xai-research", "is_fallback": True, "requires_reason":
enrich.CONTACTOUT_MISSING_COMPANY_DATA}` (`src/waterfall.py:124-131`), with a cost
entry (`src/enrich.py:43`) and a counter (`src/waterfall.py:600`). **Nothing calls
it** — the only importers are `scripts/task182_compare.py:20` and
`scripts/task183_buy_evidence.py:26`. Before it is ever wired, the two layers above
it must actually run: ContactOut `company-information-from-domain` (which does) and
the **free** webfetch crawl (which does not — §3.4). Its answer is a durable company
fact and belongs in the evidence store, not in a per-record prompt.

## 1.4 The operator's candidate list, assessed honestly

| candidate | already deterministic? | where | needs a model? |
|---|---|---|---|
| **Normalization** | Yes | `ingest.norm_domain` `src/ingest.py:48`, `ingest.slug` `:81`, `dedupe.normalise_domain` `src/dedupe.py:257`, `dedupe.normalise_email` `:85`, `identity.contact_key` `src/identity.py:74` (transliterates before slugging), `lint.normalise_punctuation` | **No.** But see the defect in §3.5: there are **two** domain normalisers and ingest calls neither of the canonical one. |
| **Dedupe** | Yes | `dedupe.find` `src/dedupe.py:155`, `keys_for` `:113`, `identity_of` `:129` | **No.** Strong identity only (email / canonical LinkedIn / namespaced provider id); a name match is review-only and never merges. |
| **Company/contact matching** | Yes | `dedupe.same_company` `src/dedupe.py:265`, `company_collisions` `:276`, `enrich.same_company` `src/enrich.py:331`, `enrich.disagree` `:475`, `enrich.identifies_nobody` `:517` | **No.** |
| **ICP rules over structured fields** | Yes, twice over | `icpstructural.structural` `src/icpstructural.py:591` (5 structural criteria, PASS / FAIL / UNKNOWN, UNKNOWN ≠ FAIL); `icp.score` `src/icp.py:208` (12 weighted dimensions, `SCORING_VERSION` `:113`) | **No.** `src/icp.py:4`: *"Not a model's yes or no."* Six of twelve dimensions read prose, and when no prose exists `research.icp_prose_missing` (`src/research.py:150`) names it and requests a **crawl**, not a model. |
| **Decision-maker title rules** | Yes | `personas.py` ranking + `clients.cap_for` `src/personas.py:245`, `roles.py`, `dmplan.py` | **No.** Zero model references in any of the three. |
| **Verification routing** | Yes | `src/verification.py` — "the one authority"; ladder stored evidence → ContactOut → Deliverable → Reoon, encoded in `waterfall.STAGES[EMAIL_VERIFICATION]` `src/waterfall.py:245` | **No.** |
| **Collision / history** | Yes | `src/collision.py` (64 KB, 0 model refs), `src/store.refuse_history_loss` `:609`, `src/store.refuse_evidence_loss` `:525`, `src/actionledger.py` | **No.** |
| **Campaign allocation** | Yes | `campaignseg.assign` `src/campaignseg.py` (segment key built at full specificity, merged upward along an explicit ladder, each company records the rung and why) | **No.** |
| **Caps / fatigue** | Yes | `src/fatigue.py` (person-level and company-level spacing across senders/channels), `src/pilotcaps.py` (ceilings a config cannot raise) | **No.** |
| **Provider writes** | Yes | `src/providerwrites.py` `perform` + `SUPPORTED`; note its own docstring `:4-15` says it is **not** the complete write surface — `bisonfactory` calls eight provider write functions directly (see `docs/TWO-DOORS-2026-09-16.md`) | **No.** The gap is a permission gap, not a reasoning gap. |
| **Provider readbacks** | Yes | `src/executionguard.py` (`READBACK_TTL_SECONDS = 15*60` `:64`, `readback_is_fresh` `:201`), `src/leadobserve.py` | **No.** |
| **Reconciliation** | Yes | `src/costs.py` `reconcile()` `:234`, verdict vocabulary `:43-69` (`RECONCILED`, `FREE_CONFIRMED`, `COST_UNRECONCILED`, `ESTIMATED_ONLY`, `UNPRICED`, `PENDING_SETTLEMENT`) | **No.** |
| **READY / HOLD / DROP** | Yes | `src/eligibility.py` (`ELIGIBLE`/`HELD`/`BLOCKED`/`SKIPPED` `:42-46`, ~35 `blocked:*` + ~10 `held:*` codes `:49-92`), `src/holdreasons.py` (5 classes) | **No.** |

**The one honest "needs a model" on this list is none of them.** The nearest thing to
a grey area is ICP's six prose dimensions — and the code already resolves that
correctly by demanding *evidence*, not inference: `research.why` returns
`NEED_ICP_EVIDENCE` only for a company whose verdict is still `review`/`unknown`
(`src/research.py:222-227`), and a rejected company is never re-scraped because
"a rejected company is a decision, not a gap" (`src/research.py:218`).

---

# DELIVERABLE 2 — THE LLM_REQUIRED GATE

## 2.1 The gate already exists in three pieces. It needs one name and one record.

The repository has independently grown the four rungs the operator asked for. They are
not composed, they are not named, and only two of them write anything an auditor can
read afterwards.

| rung | existing implementation | writes an audit row? |
|---|---|---|
| **1. Can deterministic code answer?** | `generate.plan` (`src/generate.py:804`) emits an op only for what is missing and is consumed; `personas.default_angle` (`src/personas.py:127`); `replies.classify_rules` (`src/replies.py:803`); `icpstructural.structural` (`src/icpstructural.py:591`) | **No** — `plan` returns ops; nothing records "we did not need a model here" |
| **2. Can ContactOut answer?** | `waterfall.may_fall_back` / `require` (`src/waterfall.py:355`, `:384`) — closed allowlist of reasons per step; `waterfall.contactout_is_first` (`:322`) | **Yes** — `waterfall.record_step` (`:414`) |
| **3. Does cached evidence answer?** | `enrich.already_bought(rec, call)` (`src/enrich.py:737`) reads the waterfall ledger; `research.existing_evidence` / `stale_evidence` (`src/research.py:179`, `:104`); `qualify.needs_work` + `_inputs_fingerprint` (`src/qualify.py:60`, `:75`); `research.crawl_cache_get` (`src/research.py:41`) | **Partly** — `already_bought` is silent; `qualify` stores the fingerprint |
| **4. Can free deterministic research answer?** | `research._from_the_site_itself` (`src/research.py:249`) → `webfetch.research` (`src/webfetch.py:359`), free HTTP, robots-respecting, same-domain | **Weakly** — `events.PROVIDER_CALL_SKIPPED` only |
| **5. Only then, a model** | `llm.ask` (`src/llm.py:819`) | **No** — attempts land on `store.log`, nothing else |

There is already a *precedent* for exactly the shape wanted: `enrich.spend()` refuses
a person-level call when `research.why(rec)` returns a reason, and writes the refusal
as an event (`src/enrich.py:878-890`). That is rung 4 gating rung 2, with an audit row.
The gate below is that pattern generalised and applied one layer up.

## 2.2 Where it belongs

**`src/generate.py`, between `plan()` and `generate_record()`.**

`generate.plan` (`src/generate.py:804`) already decides *what this record needs from a
model, and why* — its docstring says so: *"No call without a reason."*
`generate.generate_record` (`src/generate.py:1804`) then dispatches every op to a model
without asking again. The gate is one function that every op passes through between
those two lines:

```
plan(rec, client, campaign)  ->  [op, op, op]
                                   |
                                   v
                          answerable(rec, op, client)     <-- THE GATE
                                   |
                  +----------------+----------------+
                  |                                 |
          resolved deterministically            escalate
          (write the answer + the row)      (write the row, call llm.ask)
                                   |
                                   v
                          generate_record dispatch
```

Not in `llm.ask`. `llm.ask` is the *transport* — it receives a rendered prompt string
and cannot see the record, the op, or what a deterministic path would have answered.
Putting policy there would mean re-deriving the record from the prompt.

A second, smaller instance of the same gate belongs in
`variantgen.approaches_available` (`src/variantgen.py:220`), which is already the
per-approach admission test — it is the only place that can refuse a variant before
the call (§1.3a).

## 2.3 What the gate reads

Everything it needs is already on the record or one call away. Nothing new is fetched.

| rung | reads | authority |
|---|---|---|
| 1 deterministic | `contact["angle"]`, `contact["persona"]`, `contact["family"]`; `personas.default_angle(config, persona, family)`; `rec["cadence"][key][step]` for an already-generated, already-approved step; `rec["diagnosis"]`, `rec["hook"]` | `src/personas.py:127`, `src/generate.py:804` |
| 2 ContactOut | `rec["waterfall"]` via `enrich.already_bought(rec, call)`; `waterfall.may_fall_back(stage, provider, reason, call)`; `rec["company_facts"]` | `src/enrich.py:737`, `src/waterfall.py:355` |
| 3 cached evidence | `rec["research"]` via `research.existing_evidence` and `research.stale_evidence` (TTL by field: 3 days short-lived, 30 otherwise — `src/research.py:63-73`); `evidence.recheck` re-ages a stored row against today (`src/evidence.py:477`); `qualify._inputs_fingerprint` for "did the inputs move?" (`src/qualify.py:75`) | `src/research.py:104`, `src/evidence.py:477` |
| 4 free research | `research.why(rec, verdict=...)` — returns None when structured evidence suffices, else a named reason from `NEED_HOOK_EVIDENCE`/`NEED_ANGLE_EVIDENCE`/`NEED_REBRAND_EVIDENCE`/`NEED_ICP_EVIDENCE`/`NEED_REFRESH` (`src/research.py:22-26`, `:183`) | `src/research.py:183` |
| 5 model | `llm.fact_strings(rec)` to confirm the record can even *support* a traceable claim before paying to be told it cannot (`src/llm.py:585`) | `src/llm.py:585` |

## 2.4 What it records, so the choice is auditable

One row per record per op, appended to the record. **Reuse the existing ledger shape
rather than inventing a second one** — `waterfall.entry` (`src/waterfall.py:393`)
already carries `stage / provider / call / cost_unit / reason / expected_cost /
actual_cost / result / next_reason / at`, and `waterfall.audit(rec)`
(`src/waterfall.py:453`) already reads it and reports every step taken without an
accepted reason. The reasoning gate is a stage in the same ledger:

```
{ "stage":         "reasoning",
  "provider":      "deterministic" | "contactout" | "cache" | "webfetch" | "model",
  "call":          "persona_angle" | "draft" | "linkedin_note" | "variant_set" | ...,
  "reason":        the rung that answered, or the named reason the rung could not,
  "resolved_by":   the rung index that answered (1..5),
  "refused_rungs": [{ "rung": 1, "why": "personas.default_angle returned None" },
                    { "rung": 3, "why": "research rows stale: field=team age=6d ttl=3d" }],
  "expected_cost": 0 for rungs 1-4,
  "at":            store.now() }
```

Three properties this buys, none of which exist today:

- **`waterfall.audit(rec)` starts reporting model escalations** alongside provider
  escalations, from the same code, with no second audit tool.
- **`DETERMINISTIC_RESOLUTION_RATE` becomes derivable** — it is
  `count(resolved_by == 1) / count(rows)`, read off the ledger rather than counted in
  memory (§4).
- **A refusal is as visible as a call.** Today "the model was not needed" leaves no
  trace at all; `generate.plan` simply does not emit an op, and nothing downstream can
  tell that apart from "nobody looked".

Extend `waterfall.STAGES` (`src/waterfall.py:111`) with a `reasoning` stage whose
provider order is `deterministic → contactout → cache → webfetch → model`, each later
rung `is_fallback: True` with `requires_reason`. Then `waterfall.may_fall_back`
(`:355`) enforces the order **by construction**, exactly as it already enforces
ContactOut-first for provider calls, and a model call with no stated reason raises
`WaterfallViolation` (`:310`) instead of quietly costing money.

## 2.5 The smallest version that is still worth shipping

Three changes, no rewrite:

1. Add the `reasoning` stage to `waterfall.STAGES` and a
   `waterfall.record_reasoning(rec, call, resolved_by, refused)` helper beside
   `record_step` (`src/waterfall.py:414`).
2. Call it from `generate.plan` (`src/generate.py:804`) for every op it emits **and for
   every op it declines to emit**. `plan` already computes both.
3. Move `claims.check` from after the variant call (`src/variantgen.py:611`) to a
   pre-call predicate inside `approaches_available` (`src/variantgen.py:220`).

---

# DELIVERABLE 3 — THE EVIDENCE STORE

## 3.1 Reuse, do not rebuild: what is already here

**Ninety percent of the fact object already exists.** `evidence.make(...)`
(`src/evidence.py:442`) returns exactly the row shape the operator specified:

| operator's field | existing field | line |
|---|---|---|
| source | `source_url`, `source_type`, `provider` | `src/evidence.py:455-457` |
| timestamp | `published_at` (the claim's own date) **and** `retrieved_at` (when we fetched it) | `:458-459` |
| value | `fact` (whitespace-normalised text; *"never a raw page"*) | `:454` |
| confidence | `confidence` (passed through) plus derived `relevance_score`, `quality` ∈ strong/medium/weak/unusable | `:462`, `:466-468` |
| raw evidence reference | `evidence_id` — stable sha1, *"the same fact discovered twice keeps one id"* | `:431-439` |
| expiry / freshness | `age_days`, `freshness_score`, `freshness_bucket`; **re-derived, never stored stale** by `recheck()` | `:463-465`, `:477` |

Also already built and worth reusing verbatim:

| asset | location | why |
|---|---|---|
| **The field-typed TTL** | `research.ttl_for(field)` — `src/research.py:71`; `SHORT_LIVED_FIELDS` (team, careers, hiring, jobs, news, announcements, launches) = **3 days**, everything else = **30 days**; `age_of` reads `retrieved_at` because `age_days` is NULL on every row in the estate (`src/research.py:78-86`) | Freshness is already per fact type, not global |
| **The staleness query** | `research.stale_evidence(rec)` — `src/research.py:104` — returns the *rows*, so a caller can say which one aged out | Feeds `NEED_REFRESH` |
| **The re-ager** | `evidence.recheck(item, today)` — `src/evidence.py:477` — re-derives age/freshness/quality against today, and deliberately does **not** re-derive relevance | Stops a March draft calling a March fact "fresh" in September |
| **The durable-cache template** | `mx.load_cache` / `save_cache` / `_fresh` — `src/mx.py:451`, `:462`, `:473`; `work/mx-cache.json`, keyed by normalised domain, `cache_days` default 7 (`src/mx.py:229`), **never caches a `DNS_FAILURE`** (`src/mx.py:608`) | The only durable, domain-keyed, TTL'd, atomically-written cache in the repo. It already honours `store.lock`, atomic replace and `store.refuse_production_write`. Copy this file's shape. |
| **The state-file registry** | `store.STATE_OVERRIDES` — `src/store.py:60`, enforced by `tests/test_invariants.py` | A new store registers here, or it is invisible to the test suite |
| **The write guards** | `store.refuse_evidence_loss` `:525`, `store.refuse_history_loss` `:609`, `store.digest` + `expect_digest` `:676`/`:690`, `store.Snapshot` three-way merge `:246` | Paid evidence is already protected from being clobbered by a stale writer |
| **The change-detection key nobody reads** | `webfetch._page` emits `content_hash` = sha256[:16] of the page text (`src/webfetch.py:345`) — **no reader exists** | Free "did this page change?" for refresh decisions |
| **The recompute-avoidance fingerprint** | `qualify._inputs_fingerprint` — `src/qualify.py:75`: sha256[:16] of `{company, domain, hook, company_facts, sorted(research evidence_ids)}` | Already makes a 5,000-company batch resumable at company 2,731 |

## 3.2 The one thing that must change: the key

```python
# src/evidence.py:431
def evidence_id(record_id, source_url, fact, contact_key=None):
    material = "|".join(str(p or "") for p in
                        (record_id, contact_key, source_url, (fact or "")[:200]))
    return "ev_" + hashlib.sha1(material.encode("utf-8")).hexdigest()[:12]
```

**`record_id` is in the hash.** A record id is a slug of the company name, unique per
queue row and allocated at ingest with `-2`/`-3` collision suffixes
(`src/ingest.py:81`, `:187`). Consequences, all of them structural:

- The same company arriving in a second cohort gets a new `record_id`, therefore new
  `evidence_id`s, therefore **zero reuse of anything already paid for**.
- The same company for a second client cannot share a fact even where sharing is
  legitimate (a published careers page is not client-specific).
- Evidence lives inside `rec["research"]`, so it can only be found by loading the
  whole 17.5 MB queue and scanning it.

**The change:** key the store by `dedupe.normalise_domain(domain)`
(`src/dedupe.py:257` — lowercase, strip, `rstrip(".")`, strip one of
`www./mail./smtp./mx./email./go./info.`). That is already the canonical company key —
`dedupe.same_company` (`src/dedupe.py:265`) is defined as identical registrable domain
after exactly that normalisation, and it deliberately does **not** merge `.com` with
`.co.uk` because those are frequently separate legal entities with separate buyers.

`record_id` and `contact_key` stay on the row as **back-references**, not as key
material. A person-subject fact keys on `(domain, contact_identity)` where
`contact_identity` is `dedupe.identity_of(rec, contact)` (`src/dedupe.py:129`) — a
normalised email, a canonical LinkedIn URL or a namespaced provider id, never a name.

## 3.3 The store

`work/company-facts.jsonl`, registered in `store.STATE_OVERRIDES` (`src/store.py:60`),
written through `store.write_jsonl` under `store.file_transaction`
(`src/store.py:222`, `:206`), production-write-guarded (`src/store.py:448`).

```
key:     normalise_domain(domain)                      # dedupe.py:257
         + fact_type                                   # the five below
         + subject_ref                                 # None | contact_identity

row:     { domain, fact_type, subject_ref,
           value,                                      # typed per fact_type
           source: { provider, source_type, source_url },
           published_at, retrieved_at,
           confidence, quality,                        # evidence.py vocabulary
           evidence_ref,                               # evidence_id of the backing row
           content_hash,                               # webfetch.py:345, for refresh
           ttl_days, expires_at,                       # derived, per §3.5
           first_seen_at, last_confirmed_at,
           record_ids: [ ... ] }                       # back-references, append-only
```

`rec["research"]` stays exactly as it is. The store is a **projection keyed by domain**
that `research.run` writes alongside the record and that `enrich`, `qualify`,
`research.why` and the reasoning gate read *before* deciding to spend. Nothing moves;
one index is added. This matters because `store.refuse_evidence_loss`
(`src/store.py:525`) already protects the record copy, and a migration that relocated
evidence would fight that guard.

## 3.4 The five fact types that eliminate the most repeated work

Ranked by how many distinct consumers re-derive them today and by what each one unblocks.

### 1. `company_identity` — TTL 180 days

`name`, normalised `domain`, `email_domain`, company LinkedIn URL (`li_vanity`),
rebrand pointer.

**Why first:** it is the addressing key for every other provider. Blitz is addressed by
company LinkedIn URL, not by domain — `waterfall.STAGES[COMPANY_INFO]` has a whole
step, `blitz-domain-to-linkedin`, that exists only because ContactOut's
`/domain/enrich` sometimes returns without one (`src/waterfall.py:136-143`). And
`blitz-linkedin-to-domain` exists because *no* ContactOut response carries a mail
domain under any spelling — `src/waterfall.py:144-150` calls this "a gap, not a miss".
Both are permanent facts about the company that are re-bought per record today.
Consumers: `enrich` (Blitz addressing), `dedupe.company_collisions` (rebrand signal,
`src/dedupe.py:276`), `research.why` (`NEED_REBRAND_EVIDENCE`, `src/research.py:26`),
`mx` (the mail domain is what MX is resolved for).

### 2. `firmographics` — TTL 90 days

`employees` + band + witness, `headcount_signal`, `revenue`, `founded`, `industry`,
`offices`/country, `stack`.

**Why:** this is the entire input to the deterministic ICP. `icpstructural`
resolves geography (`:372`), company type (`:398`), services business (`:430`) and
employees (`:449`) from these fields alone, and `icp.score` weighs twelve dimensions
over the same block (`src/icp.py:208`). Measured on the live estate: `headcount_signal`
is present on 550/550 records, `employees` on 261, `industry` on 259, `revenue` on 198
— so **roughly half of every cohort is re-asking ContactOut a question the estate has
already answered for some other record.** `qualify._inputs_fingerprint`
(`src/qualify.py:75`) already hashes exactly this block, so the invalidation logic is
written.

### 3. `segment_and_type` — TTL 180 days, invalidated by prose change not by clock

`segments.classify` output plus **the matched phrases that produced it**.

**Why:** `segments.py:3` — *"deterministic keyword matching... the same company must
land in the same segment every time, a reviewer has to be able to see why, and a
segment that shifts between runs makes every campaign comparison meaningless."*
Consumers: `icpstructural._company_type` / `_services_business`
(`src/icpstructural.py:398`, `:430`), `icp` dimension scoring,
`campaignseg.key_for` (the campaign allocator's segment key), `personas` routing
family, `variantgen.style_for`. Six consumers, one derivation, recomputed every time.
Storing the *matched phrases* alongside the verdict is what makes it auditable and what
lets a config change invalidate it precisely instead of wholesale.

### 4. `site_prose_evidence` — TTL by field: 3 days short-lived, 30 days otherwise

The crawled page facts: `field`, `fact`, `source_url`, `retrieved_at`, `content_hash`.

**Why this is the biggest single lever:** six of twelve ICP dimensions — resource
planning, profitability, utilisation, time tracking, operational complexity, delivery
complexity — match phrases against prose and score zero without it, which forces
`_confidence` into its LOW band, which forces `review` however high the number
(`src/research.py:150-164`). And the copy layer cannot write a traceable claim without
it: `claims.check` refuses anything not in `llm.fact_strings(rec)` (`src/llm.py:585`).

**Measured, and this is the finding that matters:**
`src/research.py:386` — *"Measured 2026-09-16 across all 550 records: 1056 contactout
waterfall rows, 298 apify, 221 blitz, and ZERO webfetch. 394 records have research and
every one of them BOUGHT it."* The free leg was gated behind the paid plan
(`plan()` returns `planned: False` both for "not needed" and for "Apify is off"), fixed
at `src/research.py:398-403`, and the estate has not been re-run since. The TTL logic
for this type is already written (`research.ttl_for`, `src/research.py:71`); what is
missing is that the crawl is not cached beyond one pass — `_crawl_cache`
(`src/research.py:38`) is a module global cleared at the start of every
`enrich.run()` (`src/enrich.py:1348`).

### 5. `people_roster` — TTL 90 days; verification verdict 30 days; **miss reasons never expire**

Per decision-maker: contact identity, title, seniority, LinkedIn URL, work email,
verification verdict + evidence; **plus the ContactOut outcome for the domain**, whether
that is people or a named miss.

**Why the miss half matters as much as the hit half:** `enrich`'s whole fallback
allowlist is built from named misses — `CONTACTOUT_NO_PEOPLE`,
`CONTACTOUT_NO_TARGET_PERSONA`, `CONTACTOUT_RESULT_COLLISION`,
`CONTACTOUT_REBRAND_DETECTED`, `DOMAIN_UNSTAFFED`, `CONTACTOUT_NO_COMPANY_LINKEDIN`,
`CONTACTOUT_NO_EMAIL_DOMAIN` (`src/enrich.py:60-79`). A confirmed miss is a **durable
capability fact about the provider**, not a transient failure — `waterfall.is_transient`
(`src/waterfall.py:84`) already separates the two and refuses a fallback licensed by a
transient. Storing it per domain means the second cohort does not re-pay to rediscover
that ContactOut has nothing. `decision-makers` is the most expensive call in the table:
`COSTS["decision-makers"] = ASSUMED_PROFILES * 2 = 10` credits (`src/enrich.py:36`,
`:41`). Verification evidence is already keyed on `(normalised_address, provider,
status)` and deliberately not on `at` (`src/store.py:493-524`), which is the right
shape for a shared store.

## 3.5 How freshness is decided, per type

| fact type | TTL | invalidated early by | rationale |
|---|---|---|---|
| `company_identity` | 180 d | `mail_domain_differs` from `dedupe.company_collisions` (`src/dedupe.py:276`) | A rebrand is an event, not a clock tick |
| `firmographics` | 90 d | `qualify._inputs_fingerprint` change (`src/qualify.py:75`); any new ContactOut company record | Headcount moves quarterly at most |
| `segment_and_type` | 180 d | new `site_prose_evidence` for the domain; a change to the client's `segments` vocabulary | It is a pure function of prose + config; time alone does not move it |
| `site_prose_evidence` | `research.ttl_for(field)` — **3 d** for team/careers/hiring/jobs/news/announcements/launches, **30 d** otherwise (`src/research.py:63-73`) | `content_hash` change (`src/webfetch.py:345`) | Already the right rule; already written |
| `people_roster` | 90 d roster, **30 d** verification verdict, **never** for a named ContactOut miss | any contact-level stop/unsubscribe/suppression; `collision` finding | A confirmed miss is a capability fact; an address verdict decays; a stop is immediate |

Two rules carried over from code that already learned them the hard way:
**never cache a transient failure** (`mx.py:608` does not cache `DNS_FAILURE`;
`waterfall.may_fall_back` `:355` refuses a transient as a fallback reason), and
**re-derive freshness on read, never trust the stored score** (`evidence.recheck`,
`src/evidence.py:477`).

## 3.6 One defect the store would expose, worth fixing first

There are **two** domain normalisers and ingest calls neither.
`dedupe.normalise_domain` (`src/dedupe.py:257`) strips host prefixes;
`mx.normalise_host` (`src/mx.py:299`) is a separate implementation for MX keys;
`SCHEMA.md:16` claims the stored `domain` is *"normalised: lowercase, no scheme, no
www, no path"* but `src/ingest.py` uses its own `norm_domain` (`:48`) which does not
call `dedupe.normalise_domain`. A store keyed on the domain will make any disagreement
between them immediately visible as two entries for one company. **Fix the key before
building the store, not after.**

---

# DELIVERABLE 4 — MEASUREMENT PLAN, ~5,000 REAL PRODUCTIVE DOMAINS

**Not run.** This specifies how each number would be obtained and what is missing.

## 4.1 What `enrich.spend()` does and does not capture

`spend(call, why, provider="contactout", reason_code=None)` is a **closure inside
`enrich_record`** at `src/enrich.py:865`. It is the single door every provider call
passes through — a call that reaches a provider without passing here would not be
charged either, so there is nowhere else for one to hide (`src/enrich.py:938-944`).

**It writes to four sinks:**

| sink | line | durable? | payload |
|---|---|---|---|
| `budget.charge(...)` | `src/enrich.py:895` | No — in-memory, dies with the process | credits only |
| `spendledger.record(client, provider, call, cost)` | `:933` | Yes → `work/spend-ledger.jsonl` (1,320 rows today). **Only when `live`** (`:920`) | `at, day, client, provider, call, expected_cost, run_id` |
| `done.append({...})` | `:934` | No — returned as the run report | `call, why, cost, provider, reason_code` |
| `waterfall.record_step(...)` | `:946` | **Yes** → `rec["waterfall"]` in the queue. Runs in **both dry and live** | `stage, provider, call, cost_unit, reason, expected_cost, actual_cost, result, next_reason, at` (`src/waterfall.py:393`) |

Plus events on the record: `PROVIDER_CALL_PLANNED` (`:892`, carries `estimated_cost`),
`PROVIDER_CALL_SKIPPED` (`:875`, `:888`, `:897`, `:929`), `PROVIDER_CREDIT_ESTIMATED`
(`:937`). `PROVIDER_CREDIT_SPENT` exists (`src/events.py:184`) and is **never emitted**.

**What it does NOT capture — every one of these is a gap in the benchmark:**

| missing | evidence |
|---|---|
| **Tokens** | No token field on any path through `spend()` |
| **Wall clock** | No timer in `spend()` or `enrich_record`. Timing exists only per *stage per run* (`src/run.py:414`) |
| **LLM cost of any kind** | `spend()` is provider-enrichment only. `src/campaigns.py:763` literally stores `"llm_cost": "unknown"` |
| **Actual cost** | `actual_cost` is a real field and is **always `None`** from this path (`src/waterfall.py:405`, `src/enrich.py:946-949`) |
| **Cache hits** | No concept |
| **Currency** | Only a free-text `cost_unit` string (`src/waterfall.py:297`), never converted. `xai-research` is priced at `2_000_000_000` **ticks** (`src/enrich.py:43`) in the same integer column as 1-credit calls |
| **Record id on the row** | The row is nested inside the record; identity is positional. `waterfall.audit` adds `record_id` only to its output (`src/waterfall.py:471`) |
| **Whether the call succeeded** | `spend()` returns *before* the call happens; `result` is never written back |

## 4.2 Metric by metric

| metric | how to measure | status |
|---|---|---|
| **TOTAL_DOMAINS** | `funnel.counts(recs)["input_domains"]` (`src/funnel.py:191`) filtered to the cohort by `rec["batch"]["id"]` (`src/ingest.py:180`); `funnel.cohort_of` (`src/funnel.py:424`) already does the filtering | ✅ **instrumented** |
| **DETERMINISTIC_RESOLUTION_RATE** | `count(reasoning rows where resolved_by == 1) / count(reasoning rows)` — off the ledger the §2.4 gate writes | ❌ **needs the gate.** Today "no model was needed" leaves no trace: `generate.plan` simply does not emit an op |
| **CONTACTOUT_RESOLUTION_RATE** | `waterfall.counters(records)` → `CONTACTOUT_CALLS` vs `CONTACTOUT_CONFIRMED_MISSES` + `OTHER_PROVIDER_ESCALATIONS` (`src/waterfall.py:609-618`); derivable per stage via `waterfall.ledger(rec)` | ⚠️ **computable but never computed.** `waterfall.counters()` has **no production caller** — repo-wide, the only callers are `tests/test_contactout_fallback_semantics.py:256-292`. Needs a caller, not new code |
| **CACHE_HIT_RATE** | Requires the §3 store plus a hit counter at the read | ❌ **structurally unmeasurable today.** `waterfall.counters(records, cache_hits=0)` (`src/waterfall.py:556`) emits `CONTACTOUT_CACHE_HITS` from a parameter whose comment (`:551-554`) says it is tracked in `src/providers/contactout.py` — `grep -c cache src/providers/contactout.py` returns **0**. There is no ContactOut cache at all. The only real cache-hit rate in the repo is for DNS, in simulation (`src/scalesim.py:262`) |
| **RESEARCH_REQUIRED_RATE** | `count(research.why(rec) is not None) / TOTAL_DOMAINS`, computed as a dry pass — `why()` is free and pure (`src/research.py:183`). Split by the five named reasons (`src/research.py:22-26`) | ✅ **derivable now**, no new counters. Needs a script that iterates and tallies |
| **Free-crawl vs paid-crawl split** | `waterfall.ledger` rows where `call == "webfetch-crawl"` vs `"apify-research"` | ✅ instrumented. **Baseline: 0 webfetch rows / 298 apify rows across 550 records** (`src/research.py:386`) — the free leg has never run at scale |
| **SLM_REQUIRED_RATE** | `count(reasoning rows where resolved_by == 5) / count(reasoning rows)`, split by op | ❌ needs the gate. `generate.model_calls` (`src/generate.py:86`) counts per step but is **in-memory, per-process, never persisted** — only `scripts/task197_generate.py:311` reads it |
| **STRONG_MODEL_ESCALATION_RATE** | Needs a model tier on the call. `llm.from_env()` (`src/llm.py:462`) picks one model for the whole run; there is no tier concept | ❌ **not expressible today.** Requires a tier field on the reasoning row and a router. `GROK_ESCALATIONS` (`src/waterfall.py:600`) is the closest existing counter and can only fire on rows nothing currently writes |
| **ICP pass / fail / uncertain** | `icp.summarise(results)` → `status` dict over `qualified/review/rejected/unknown`, plus `tier`, `confidence`, `needs_manual_review` (`src/icp.py:863-879`); `icpstructural.summarise` → `verdicts`, `fail_reasons`, `eligible` (`src/icpstructural.py:623`); `qualify.summarise` wraps both (`src/qualify.py:377`) | ✅ **fully instrumented**, in three reconciling vocabularies |
| **Contacts per domain** | `funnel.counts["people_found"] / ["qualified"]` (`src/funnel.py:199-201`) | ✅ instrumented. Estate baseline ≈ **2.5** |
| **Verified contacts per domain** | `funnel.counts["emails_2_of_2_verified"]` — two independent confirmations, `contact.verification.confirmation_count` (`src/funnel.py:204`) | ✅ instrumented |
| **Campaign-ready per domain** | `funnel.counts["campaign_ready"]` → `funnel._campaign_ready` (`:220`), which asks `eligibility.decide` rather than reading a flag | ✅ instrumented. `scripts/campaign_ready_funnel.py:389` gives the same split by blocker |
| **SECONDS_PER_DOMAIN** | `run.report["seconds"]["per_record"]` (`src/run.py:444-446`) | ⚠️ **partial.** It is `sum(stage_times) / len(targets)` — an average over the run, not a per-record measurement, and it cannot separate a slow domain from a slow stage. A per-record timer around `enrich_record` / `generate_record` is a two-line addition |
| **COST_PER_DOMAIN — ContactOut** | `waterfall.spend(rec)["by_provider"]["contactout"]["expected"]` (`src/waterfall.py:430`) | ⚠️ **expected only.** `actual_cost` is always `None`. `costs.reconcile()` (`src/costs.py:234`) can close the gap against ContactOut's own counters (`AUTHORITATIVE`, `src/costs.py:86`) but must be run and is never called in the pipeline |
| **COST_PER_DOMAIN — crawl** | webfetch is free (`COSTS["webfetch-crawl"] = 0`, `src/enrich.py:42`). Apify is **UNPRICED** — `COSTS["apify-research"] = 0` because it bills compute units, stated explicitly at `src/enrich.py:110-114` and `src/waterfall.py:304`. `research.RunBudget` (`src/research.py:118`) caps *starts*, not cost | ⚠️ **starts countable, money not.** `costs.AUTHORITATIVE["apify"] = "usd"` (`src/costs.py:86`) means the number is retrievable from Apify, out of band |
| **COST_PER_DOMAIN — LLM** | Nothing. `spend()` never sees a model call | ❌ **missing.** But the data exists and is thrown away: `OpenAICompatibleModel.complete` appends `{model, seconds, chars, prompt_tokens, completion_tokens, total_tokens, cost}` to `self.calls` (`src/llm.py:304-312`) — **and `self.calls` has zero readers in `src/`** |
| **COST_PER_DOMAIN — provider (send)** | `work/spend-ledger.jsonl` via `spendledger.report()` → `expected_total`, `by_provider`, `by_day` (`src/spendledger.py:191`). Live-only (`src/enrich.py:920`) | ⚠️ expected credits only; no currency |
| **TOKENS_PER_DOMAIN by model** | `prompt_tokens` / `completion_tokens` / `total_tokens` are captured per call at `src/llm.py:205`, `:304`. xAI captures more — `prompt/completion/total/cached/reasoning tokens` + `cost_in_usd_ticks` (`src/providers/xai.py:275-308`) | ❌ **never persisted.** And **`QwenCliModel` captures no tokens and no cost at all** (`src/llm.py:454-458` records only `model`, `seconds`, `chars`) — so on the Qwen lane this metric is **unobtainable**, not merely unwired |

## 4.3 The instrument that is already written and not plugged in

`scripts/task151_ai_spend_writer.py` is a **complete, dead** AI spend ledger.
`record_call()` (`:108-171`) writes exactly the missing row:

```
at, day, client, stage, task, record_id (hashed), model, provider, prompt_version,
input_tokens, output_tokens, cached_tokens, latency, retry_count,
estimated_cost, cost_source, price_table_version, success, cache_hit
```

to `work/ai-spend-ledger.jsonl` (`:93`). Its own docstring says *"Claude wires it into
`llm.ask`; this script does not"* (`:8`). **Nothing imports it.** The design that
justified it is `docs/AI-SPEND-LEDGER-2026-09-15.md`, which correctly argues it should
sit *beside* `spendledger.py` rather than inside it, because credits and currency are
different units and merging them would corrupt both.

Wiring it into `llm.ask` (`src/llm.py:819`) — which already has `step`, `attempt`,
`errors`, and can read `model.calls[-1]` after `complete()` returns — closes
SLM_REQUIRED_RATE, TOKENS_PER_DOMAIN, LLM COST_PER_DOMAIN and the LLM half of
SECONDS_PER_DOMAIN in one change. Move it to `src/aispendledger.py` and register it in
`store.STATE_OVERRIDES` (`src/store.py:60`).

## 4.4 Benchmark harness cautions

1. **Use the real cohort, not `src/companies.py`.** That module builds a deterministic
   synthetic 5,000-company universe (`src/companies.py:374`) — it is the control, not
   the subject. Its records are ~4.2 KB; real ones are ~31.8 KB (§5).
2. **Re-measure the two quadratics before trusting `docs/SCALE-MEASUREMENT-30K.md`.**
   That document reports `dedupe.find` and `campaignseg.assign` as *"quadratic or
   worse"* (growth 49.7× and 64.1×). Both were fixed on 2026-09-14 by commit
   `115d405e` ("Integrate TASK-041: two quadratics and a per-lead transaction") —
   `dedupe.find` now uses a `found_pairs` set (`src/dedupe.py:163`) and
   `campaignseg.assign` hoists `settings()` out of the loop and builds `eligible_ids`
   once. **The document has not been re-run since the fix.** Re-run
   `benchmarks/scale_30k.py` before quoting it.
3. **Separate dry from live.** `waterfall.record_step` runs in **both** dry and live
   passes (`src/enrich.py:946`), but `spendledger.record` runs only when `live`
   (`:920`). A dry benchmark therefore produces a complete waterfall ledger and an
   empty spend ledger — which is correct, and will look like a bug if unstated.
4. **`src/benchmark.py` already counts `llm_calls_would_be`** (`:79`, computed at
   `:100` as `len(selected) × len(cadence.generated_keys(...))`). It is the right
   dry-run predictor for SLM_REQUIRED_RATE's denominator and is offline by
   construction (`src/benchmark.py:11`: *"Nothing here calls a network"*).

---

# 5. THE BIGGEST ARCHITECTURAL BOTTLENECK

**The whole estate is one JSONL file, it is rewritten in full every five records, and
real records are 7.6× heavier than the synthetic ones every benchmark has used.**

Measured today:

```
work/queue.jsonl        17,484,788 bytes / 550 records = 31.8 KB per record
synthetic benchmark      4.2 KB per record  (docs/SCALE-MEASUREMENT-30K.md)
                         --> real records are 7.6x heavier
```

- `store.load()` (`src/store.py:407`) reads the entire file into a `Snapshot`.
- `store.save()` (`src/store.py:690`) writes the entire file, atomically, and on the
  way through runs `refuse_evidence_loss` (`:525`) and `refuse_history_loss` (`:609`),
  each of which builds a full index of every record and every contact.
- `run.checkpoint()` calls `store.save(recs)` every **`CHECKPOINT_EVERY = 5`** records
  (`src/run.py:114`, `:395-402`).

At 5,000 real domains that is a **~159 MB file**, held entirely in memory, and
**~1,000 full-file writes per per-record stage** — of which there are four (`enrich`,
`qualify`, `personas`, `generate`; `src/run.py:38`). Scaling the measured
`store.save` at 5,000 synthetic records (0.524 s) by the 7.6× size factor gives
**~4 s per checkpoint, ~66 minutes of pure checkpoint I/O per stage** — an estimate
from measured inputs, not a measurement, and it excludes the two index-building
guards. Peak RSS at 5,000 synthetic records was 278.8 MB; at 7.6× the payload it will
not fit the profile the benchmark assumed.

This is why the agent-per-cohort pattern persists. It is not that the reasoning needs
a human — §1 shows the reasoning is already deterministic. It is that **a 5,000-domain
run cannot be left alone**: it is slow enough to be interrupted, it holds a lock
(`src/store.py:134`, `LOCK_STALE_AFTER = 300`), and an interrupted whole-file write
leaves the `.tmp` artefacts already sitting in `work/` (`queue.jsonl.32172.tmp`,
`action-ledger.jsonl.39192.tmp`) with nothing to reap them.

**Second-order, and inseparable from it:** because evidence lives *inside* the record
and is keyed by `record_id` (`src/evidence.py:431`), the file is the store — there is
no way to ask "what do we already know about this domain?" without loading all 159 MB.
The evidence store in §3 is therefore not only a cost saving; it is what makes the
queue small enough to stop being the bottleneck.

**Smallest changes that move this, in order:**

1. **Raise `CHECKPOINT_EVERY` and make it size-aware** (`src/run.py:114`) — one
   constant, and the comment at `:388` already frames it as a loss/cost trade.
2. **Split the evidence projection out of the record** into `work/company-facts.jsonl`
   keyed by `dedupe.normalise_domain` (§3). This is what removes the bulk from the
   queue; `rec["research"]` stays as the record's own copy.
3. **Give `store.save` an incremental path** for the common case where a checkpoint
   touched fewer than *k* records. `store.Snapshot` (`src/store.py:246`) already
   remembers each row as it was read and merges field-by-field, so the diff is already
   computed — only the write is wholesale.
4. **Re-run `benchmarks/scale_30k.py` at the real 31.8 KB record size** before any of
   the above, so the fix is measured rather than argued.

---

## 6. Summary of recommended changes (none implemented)

| # | change | file | why |
|---|---|---|---|
| 1 | Add a `reasoning` stage to `waterfall.STAGES` + `record_reasoning`, called from `generate.plan` for ops emitted **and** declined | `src/waterfall.py:111`, `src/generate.py:804` | Makes the deterministic-first choice auditable and enforceable by the existing `may_fall_back` machinery |
| 2 | Move `claims.check` from after the variant call to a predicate in `approaches_available` | `src/variantgen.py:220`, `:611` | Largest single reduction in model calls; sits on the biggest multiplier |
| 3 | Populate `rec["evidence"][key]` from `evidence.select` so `persona_angle` is not needed when `personas.default_angle` answered | `src/generate.py:1509`, `src/evidence.py:546` | Removes the residual per-contact call |
| 4 | Wire `scripts/task151_ai_spend_writer.record_call` into `llm.ask`; move to `src/aispendledger.py`; register in `STATE_OVERRIDES` | `src/llm.py:819`, `src/store.py:60` | Closes four of the twelve unmeasurable benchmark metrics with code that is already written |
| 5 | Add a caller for `waterfall.counters()` in the run report | `src/waterfall.py:556`, `src/run.py:440` | Seven policy counters exist and nothing computes them |
| 6 | `work/company-facts.jsonl` keyed by `dedupe.normalise_domain`, five fact types, `mx.py` as the template | new, `src/dedupe.py:257`, `src/mx.py:451` | Cross-cohort reuse; shrinks the queue |
| 7 | Fix the domain-normalisation split before building #6 | `src/ingest.py:48` vs `src/dedupe.py:257` | Two normalisers means two entries for one company |
| 8 | Narrow `_regenerate_linkedin_set` to the steps `campaign_repetition` named | `src/generate.py:1384` | Fewer calls, and stops discarding approved steps |
| 9 | Re-run `benchmarks/scale_30k.py` at real record size; re-measure the two fixed quadratics | `benchmarks/scale_30k.py` | The only scale document in the repo predates both the fix and the real payload size |

## 7. UNKNOWN

- Whether `work/queue.snapshot.jsonl` / `queue.snapshot.STAMP` are written by anything
  in `src/` — no writer found; likely a `scripts/` or manual backup.
- The true `E` and `L` (generated email and LinkedIn step counts) for the current
  Productive live sequence. `cadence.STEPS` (`src/cadence.py:42`) gives 2 and 2; a
  campaign may carry its own sequence under `CADENCE_KEY` (`src/cadence.py:63`);
  `docs/AI-CALL-SITE-INVENTORY-2026-09-15.md` measured ≈5 and ≈6. The per-domain call
  counts in §1.2 use the measured figures and scale linearly with whichever is real.
- Whether `research.crawl_cache` survives a process boundary in any deployment
  configuration — it is a module global (`src/research.py:38`) and does not, in the
  configurations read.
- What fraction of the 5,000 real Productive domains already appear in the 550-record
  estate. This determines the day-one CACHE_HIT_RATE and cannot be established without
  reading the cohort CSV, which was out of scope here.
