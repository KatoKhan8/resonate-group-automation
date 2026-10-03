# GLM Checkpoint A — Independent Review

**START_MASTER_SHA**: `2bf7b8a57` (Merge task-guard-regressions-rebased)
**Review date**: 2026-10-03
**Reviewer**: GLM (independent, read-only)
**Worktree**: `../resonate-glm-checkpoint-a` (isolated, detached HEAD)
**Protocol**: `docs/GLM-REVIEW-PROTOCOL.md`

## Scope

Checkpoint A per `docs/qwen-tasks/RUNNING/TASK-383-glm-checkpoint-a.md`:
production generation entrypoint + canonical research store, after TASK-375
(entrypoint loads its five skills) and TASK-376 (researchpack vs packfacts
resolved).

Seven negative controls. Falsification over confirmation.

---

## Control 1 — One version-controlled production entrypoint exists

**Attempted falsification**: Show that `generate_campaign.py` has no production
caller, or that two competing entrypoints exist.

**Evidence**:

- `src/generate.py:3211` — `if __name__ == "__main__": raise SystemExit(main())`
  is the CLI entrypoint (`python -m src.generate --live`).
- `src/generate.py:2944` — `run()` is the real production function.
- `src/generate.py:1988` — `run()` calls `_generate_via_campaign(rec, model, client, ...)` for every writer op.
- `src/generate.py:2888` — `_generate_via_campaign` calls `generate_campaign.generate(...)`.
- `src/generate_campaign.py:1` — module docstring: "The single versioned production entrypoint for campaign generation."
- `src/generate.py:2802-2808` — comment: "TASK-400. The real entrypoint. `generate_campaign.generate()` is the single versioned production path."

**Full chain, traced**:

```
python -m src.generate --live
  → main()                                          [generate.py:3209]
  → run(model, live=True, ...)                      [generate.py:2944]
  → _generate_via_campaign(rec, model, client, ...) [generate.py:1988]
  → generate_campaign.generate(...)                 [generate.py:2888]
```

**Verdict**: CONTROL FAILS TO FALSIFY. There IS one version-controlled
production entrypoint now. `generate_campaign.generate()` is the single
versioned path, and `generate.py` reaches it through `_generate_via_campaign`.
TASK-375's finding ("no production caller") was the old state; TASK-400 closed
it. Both modules are version-controlled and the chain is complete from CLI to
writer.

**Disposition**: **SUPERSEDED** — the defect TASK-383 names has been fixed by
TASK-400. "One entrypoint" is currently true, not aspirational.

---

## Control 2 — The Second Brain has a real consumer

**Attempted falsification**: Show that Second Brain facts are loaded but never
reach a rendered message.

**Evidence**:

- `src/generate_campaign.py:602` — `secondbrain.for_task("campaign_strategy", slug)` in `_load_admitted_facts`.
- `src/generate_campaign.py:814` — `br_context = _format_br_context(sb_facts)` formats facts for the hypothesis prompt.
- `src/generate_campaign.py:816-818` — `copystages.hypothesis_user(company, domain, title, facts, br_context)` passes the formatted facts to the hypothesis model call.
- `src/generate_campaign.py:595-596` — comment: "CLIENT_SUPPLIED knowledge informs strategy and hypothesis but NEVER becomes a prospect-facing assertion."
- `src/copystages.py:124` — `business_context_for(task, client)` is defined but has **ZERO callers** in `src/`. It is dead code.
- `src/generate_campaign.py:1523` — A second `_format_br_context` exists locally in `generate_campaign.py` and IS the one the production path uses.

**Trace to rendered message**:

```
secondbrain.for_task("campaign_strategy", slug)
  → _load_admitted_facts() filters to VERIFIED + CLIENT_SUPPLIED
  → _format_br_context(sb_facts) formats as text
  → copystages.hypothesis_user(..., br_context) builds prompt
  → model call produces hypothesis
  → hypothesis feeds writer (via plan_data / context)
  → writer produces email/LinkedIn copy
```

The Second Brain reaches the **hypothesis stage** (an intermediate model call),
and the hypothesis influences the writer. But the Second Brain facts themselves
are explicitly marked "NEVER prospect-facing" (line 596). The writer's
prospect-facing `facts` argument comes from account research extraction
(`extract_skill` at line 797), not from Second Brain.

**Dead code found**: `copystages.business_context_for()` at `src/copystages.py:124` has zero callers. It duplicates the function that `generate_campaign._format_br_context` actually performs.

**Verdict**: PARTIALLY HOLDS. The Second Brain has a real consumer in the
hypothesis stage and influences strategy, but:
1. Its facts never directly appear in prospect-facing copy (by design).
2. `copystages.business_context_for()` is dead code.
3. The influence is indirect: fact → hypothesis → writer → copy.

**Disposition**: **EXISTING TASK** (dead code in `copystages.business_context_for`)
+ the control partially holds for the production path.

---

## Control 3 — Canonical research has exactly one authority

**Attempted falsification**: Find any code path that reads research from
somewhere other than `rec["research"]` and lets it reach a rendered message.

**Evidence**:

Writers of `rec["research"]` (all write a LIST):
- `src/research.py` — production crawl
- `src/companies.py:326-329`
- `src/demo.py:182-185`
- `src/demo_outreach.py:417`
- `src/benchmark.py:53`
- `src/synthetic.py:270-273`
- `src/web/demodata.py:479`

Readers of `rec["research"]`:
- `src/packfacts.py:232` — `pack_for(rec)` iterates `rec.get("research") or []`
- `src/generate.py:2692` — `_account_sources(rec)` reads the list
- `src/claims.py`, `src/dossier.py`, `src/eligibility.py`, `src/icp.py`,
  `src/preview.py`, `src/qa.py`, `src/qualify.py`, `src/quality.py`,
  `src/report.py`, `src/segments.py`, `src/personalization.py`, `src/llm.py`,
  `src/funnel.py`, `src/simulator.py`, `src/web/api.py`

`researchpack` status:
- `src/researchpack/__init__.py` — module exists, docstrings show usage examples
- **ZERO imports** from production code. Searched `import researchpack`,
  `from .researchpack`, `from src.researchpack` — only self-references in
  docstrings.
- `researchpack.build()` and `researchpack.pack()` are never called from
  production.

`src/generate.py:2695-2718` — `_account_sources` documents that `rec["research"]`
is a LIST by count: "394 carry a populated list, 23 an empty list, 1,165 none,
and NOT ONE a dict."

**Verdict**: CONTROL FAILS TO FALSIFY. `rec["research"]` is the one canonical
store. `researchpack` is demoted — it exists as a module but has no production
caller. Every writer produces a list, every reader consumes a list.

**Disposition**: **HOLDS**.

---

## Control 4 — Changing an approved fact changes the resulting artifact

**Attempted falsification**: Show that changing a Second Brain fact does NOT
change the output.

**Evidence**:

- `tests/test_changing_an_approved_fact_changes_the_output.py` — test exists,
  539 lines, drives through `generate_campaign.generate()`.
- Test mocks `secondbrain.for_task` and `offers.load`, calls `generate()` twice
  with different facts, asserts hypothesis and email body differ.
- Test also verifies reversibility: change fact A→B→A, assert output returns.
- Test also verifies negative: change an INFERRED (unapproved) fact, assert
  output does NOT change.

**Limitation**: This is a unit test with mocked Second Brain, not a reproduction
against the real chain with real model calls. The task says "A claim that a unit
test does this is not the same as reproducing it against the real chain."

**Static chain analysis**:
```
secondbrain.for_task() → _load_admitted_facts() → sb_facts
  → _format_br_context(sb_facts) → br_context
  → copystages.hypothesis_user(..., br_context) → prompt
  → model.complete() → hypothesis
  → writer uses hypothesis → rendered copy
```

The chain is wired. A changed fact produces a different `br_context` string,
which produces a different prompt, which (deterministically or not) produces a
different hypothesis, which influences the writer.

**Verdict**: UNVERIFIABLE from a read-only pass. The test exists and drives
through the real entrypoint. Static analysis shows the chain is wired. But I
cannot run the test to confirm it passes, and a test with a mocked model
(`_FactAwareModel`) is not the same as a real model call.

**Disposition**: **UNVERIFIED** — read-only pass cannot confirm runtime
behaviour. Static proof of wiring is present; runtime confirmation is owed.

---

## Control 5 — No critical generation logic depends on gitignored `work/`

**Attempted falsification**: Find production code that opens files from `work/`
at runtime.

**Evidence**:

- Searched `open(.*work/` and `Path(.*work/` in `src/` — **ZERO matches**.
- `src/generate_campaign.py:14` — "`work/v2_run.py` is the reference" — this is
  a comment, not a runtime dependency.
- `src/generate_campaign.py:668` — "Sources come from the account dict, not from
  hardcoded work/ paths." — explicit statement that `work/` is not used.
- `src/operatorexclusion.py:89-96` — guard/test that states the rule: "Business
  logic never depends on gitignored work/".
- All 101 matches for `work/` in `src/` are in comments/docstrings explaining
  the architecture, not in executable code.

**Verdict**: CONTROL FAILS TO FALSIFY. No production code in `src/` opens files
from `work/` at runtime. The `work/v2_run.py` reference is historical context.

**Disposition**: **HOLDS**.

---

## Control 6 — No closed wiring loop with zero external consumer

**Attempted falsification**: Show that the five skills are wired into
`generate_campaign.py` but that module itself has no external caller.

**Evidence**:

Five skills loaded by `generate_campaign.py`:
1. `campaign_strategy` — line 659: `skills.load("campaign_strategy")`
2. `signal_verification` — line 784: `skills.load("signal_verification")`
3. `account_research` — line 797: `skills.load("account_research")`
4. `cold_email_writing` — line 938: `skills.load("cold_email_writing")`
5. `linkedin_writing` — line 939: `skills.load("linkedin_writing")`

External caller of `generate_campaign.generate()`:
- `src/generate.py:2888` — `_generate_via_campaign` calls `generate_campaign.generate(...)`.
- `src/generate.py:1988` — `run()` calls `_generate_via_campaign(...)`.
- `src/generate.py:3209` — `main()` calls `run()`.
- `src/generate.py:3211` — `if __name__ == "__main__": raise SystemExit(main())`.

The chain is complete:
```
CLI → main() → run() → _generate_via_campaign() → generate_campaign.generate()
  → skills.load("campaign_strategy") → campaignstrategy.for_segment()
  → skills.load("signal_verification") → ICP check
  → skills.load("account_research") → fact extraction
  → skills.load("cold_email_writing") → email writer
  → skills.load("linkedin_writing") → LinkedIn writer
```

**Verdict**: CONTROL FAILS TO FALSIFY. The loop is NOT closed. The five skills
have a real internal caller (`generate_campaign.py`), and that module has a
real external caller (`generate.py` → `run()` → CLI). Something reaches it.

**Disposition**: **SUPERSEDED** — TASK-400 closed the gap TASK-375 identified.
The skills are no longer a closed loop.

---

## Control 7 — No cross-account research leakage in the reviewed path

**Attempted falsification**: Show that the join between record and research pack
is a text filter rather than exact identity.

**Evidence**:

`src/bisonfactory.py:594` — `_copylint_batch`:
```python
by_id = {record.get("id"): record for record in recs or []}
```

`src/bisonfactory.py:605`:
```python
pack, _ = packfacts.pack_for(by_id.get(lead.get("record_id")))
```

This is an EXACT IDENTITY join by `record_id`, not a text filter.

`src/packfacts.py:131-142` — `identity_of(row, domain, record_id)`:
```python
if record_id is not None and stamped is not None \
        and str(stamped) != str(record_id):
    return REFUSED
for key in SITE_KEYS:
    if str(row.get(key) or "").strip():
        return ADMITTED if same_site(row[key], domain) else REFUSED
```

The test is:
1. `record_id` match (exact string comparison).
2. Domain/site identity via `same_site()` (exact host comparison, not substring).

Same pattern in `_gate_facts` (line 730) and sequence gate (line 1054).

`src/packfacts.py:21-28` — module docstring documents the 50-of-71 defect:
"50 of the 71 job rows the research pilot returned belonged to a DIFFERENT
company, because `companyName` is a text filter and not an identity match."
The fix was `identity_of()`, which is now the gate.

**Verdict**: CONTROL FAILS TO FALSIFY. The join is exact identity (record_id +
domain), not a text filter. The 50-of-71 defect is documented and the fix is
in place.

**Disposition**: **HOLDS**.

---

## Summary of dispositions

| # | Control | Disposition | Confidence |
|---|---------|-------------|------------|
| 1 | One entrypoint | **SUPERSEDED** — TASK-400 fixed it | HIGH |
| 2 | Second Brain consumer | **PARTIALLY HOLDS** — reaches hypothesis, not copy; dead code in `copystages.business_context_for` | HIGH |
| 3 | One research authority | **HOLDS** — `rec["research"]` is canonical, `researchpack` has no caller | HIGH |
| 4 | Fact change → artifact change | **UNVERIFIED** — test exists, chain is wired, but read-only pass cannot confirm runtime | MEDIUM |
| 5 | No `work/` dependency | **HOLDS** — zero runtime `open()`/`Path()` on `work/` | HIGH |
| 6 | No closed loop | **SUPERSEDED** — TASK-400 closed the gap | HIGH |
| 7 | No cross-account leakage | **HOLDS** — exact identity join, not text filter | HIGH |

## New findings

1. **Dead code**: `copystages.business_context_for()` at `src/copystages.py:124`
   has zero callers. It is a duplicate of `generate_campaign._format_br_context`
   and should be removed or wired.

2. **Dual `_format_br_context`**: Two functions with the same name exist —
   `copystages._format_br_context` (line 109, private) and
   `generate_campaign._format_br_context` (line 1523, private). The production
   path uses the latter. The former is only reached through the dead
   `business_context_for`.

## What this review could not verify

- **Runtime behaviour of Control 4**: Changing a fact and observing the artifact
  differ requires running the test suite or a live generation pass. Static
  analysis shows the chain is wired, but a mocked model (`_FactAwareModel`) is
  not a real model. Runtime confirmation is owed.

## END_MASTER_SHA check

**END_MASTER_SHA**: `2bf7b8a57` — same as START. No master movement detected.
