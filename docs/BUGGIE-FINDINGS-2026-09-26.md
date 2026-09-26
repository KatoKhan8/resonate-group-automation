# BUGGIE FINDINGS — 2026-09-26, master `0af11fcb`

Run under the operator's standing order: Buggie runs continuously against a fresh
clone, master after every merge and every worker branch before merge, findings
filed as Qwen tasks with severity, **never fixed by Buggie itself.**

**Containment, verified before the run:** clone at a temp path holding no
`config/.env`, no `work/`, no `queue.jsonl`. The four CSVs present are synthetic
fixtures on `.test` domains with zero email addresses. No network call, no model
call, no provider call, no edit.

**Crew:** 5 specialists — security, backend, data, docs, performance. Not
staffed: frontend, ux, accessibility, product-manager (no bootable UI without
the `.env` containment forbids, so those lenses are graded **I**, not passed);
code-reviewer (scope is master, not a diff).

**Verification:** every CRITICAL below was re-verified by hand in the main
checkout before being written down. Two agent claims were **corrected** in that
pass and are recorded as corrected, not as found.

---

## COUNT

    CRITICAL   5
    HIGH       9
    MEDIUM     6
    LOW        2
    total     22

    corrected during verification   2
    refuted by the finder itself    1   (context bloat — contextpack is NOT
                                        passed whole into prompts; the finder
                                        checked and dropped its own hypothesis)

---

## THE FIVE CRITICALS

### C1 — The approval hash is recorded and never checked. `TASK-328`
**`src/providers/bison.py:1439`, `:1886`, `src/providers/heyreach.py:1691`**

All three production call sites call `reviewapproval.require(campaign_id)` with
**no `review_hash`**. `require(campaign, review_hash=None)` compares the hash
only when one is given, so the mismatch branch is unreachable in production.

`reviewapproval`'s own docstring says the hash is "what makes the approval about
a particular file rather than about the campaign in general … An approval that
survived a re-render would approve words nobody read."

**Consequence:** approval is campaign-level and permanent. Once a campaign
carries any approval row, a later resume, activation or lead top-up passes the
gate with whatever copy is current — including copy regenerated after approval.
This is the 09-25 incident's failure mode at the gate built to prevent it.

Verified by hand: `grep -rn "reviewapproval.require(" src/` returns exactly
those three lines, none with a second argument.

### C2 — `secondbrain` cites a source it did not read, for any client. `TASK-322` (fix ran, awaiting verification)
**`src/secondbrain.py:_fact` and the ~19 call sites in `_profile/_market/_customers/_messaging`**

`source` is a hardcoded literal `"config/clients/productive.yaml …"` at every
call site, never built from the `client` argument. `for_task('cold_email_writing',
'acme')` cites Productive's config as the origin of Acme's facts.

Compounded by: `_fact(text, source, date=None, verified=True)` stamps
`verified=True` and `date=TODAY` unconditionally, and no caller ever passes
otherwise — so any assertion on `verified` or `date` passes by construction.
That is the guard-that-cannot-fail the handoff already confessed to.

Directives §7: *"Never fabricate provenance to satisfy a schema or validator …
A missing source is preferable to a fake source."* This is the violation, in
code, on master.

### C3 — Model spend never reaches the ledger, so no model ceiling can fire. `TASK-323` (fix ran, awaiting verification)
**`src/generate.py` (six `llm.ask` sites), `src/llm.py`, `src/providers/glm.py`, `src/providers/xai.py`**

`generate.py` does not import `spendledger` at all. Every draft, hook, diagnose,
persona-angle and LinkedIn-note call is priced onto `rec['model_calls']` and
never written as a ledger row. `llm.py` says so outright: *"The adapters already
measure this and the measurement is thrown away."* `glm.py` and `xai.py` contain
no `spendledger` reference either.

`LEDGER_UNITS` already maps `anthropic`/`groq`/`openrouter` → `microusd`,
implying rows were expected. None are written.

**Consequence:** `budget.total`, `budget.per_day` and every per-provider model
ceiling read rows nobody writes. They are controls that cannot trigger. This is
the operator's exact symptom — a night that spent ~$3.88 shows zero rows.

### C4 — CLAUDE.md, read first every session, is four days stale and describes a different production reality. `TASK-329`
**`CLAUDE.md:2`**

It names the **2026-09-22** handoff as "the current state", asserts "BOTH
CHANNELS ARE SENDING", and lists 491-498 as ACTIVE with 151 leads and 243
scheduled rows. Master carries a **2026-09-26** handoff whose provider table
shows 493 as the *only* active campaign, 491/492/494/496/503/504/505 paused, 495
archived, 497/498 completed — plus campaigns 503-505 that CLAUDE.md never
mentions, and two prospect-facing incidents (77 blank emails, 64 wrong-agency
emails) that postdate it.

**Consequence:** the file whose whole job is to orient a fresh session
misdirects it about what is sending. Graded CRITICAL because it is the first
thing read and it is wrong about live sending state.

### C5 — The handoff reports branch-only work as verified on master. `TASK-329`
**`docs/PRODUCTION-HANDOFF-2026-09-26-MORNING.md` §8**

It lists 13 tasks as "DONE, artifact verified". Measured: of those, only
**TASK-216** and **TASK-317** are in `DONE/`. The artifacts for **305** (no
`src/providers/groq.py` on master), **307** (no `linkedin_url_from_email` in
`contactout.py`) and **313** (no `docs/AUDIT-2026-09-26.md`) **do not exist on
master at all** — 313's report lives only on `qwen-worker-3-r9`.

Independently corroborated by `docs/state/TASK-REGISTRY.json`, which records
305/307/313 as `QUEUED / TODO / NOT_SUBMITTED`.

**Consequence:** directly contradicts directives §2 and §11 — a local or
branch commit is not a completed task. The next session builds on code that is
not there, or skips dispatching work believing it finished. This is what caused
the wasted dispatches this session.

---

## HIGH

**H1 — The entire v2 copy engine has zero callers. `TASK-324` (fix ran, awaiting verification)**
Every stage prompt and builder in `src/copystages.py` (HYPOTHESIS/MATCH/STRATEGY/WRITER)
and `src/copyprompts.py` (ICP/EXTRACT/COHORT/lead_user) is unimported by any
module, test or script. No lead is ever run through hypothesis → match →
strategy → write. Whatever produced the ten and the fifty is `work/v2_run.py`,
which is gitignored and therefore not in git at all.

**H2 — `sequencegate.check` has zero non-test callers, and `bisonfactory` never calls it.**
`bisonfactory`'s import line lists `campaigns, clients, copylint, packfacts,
providerwrites, store` — no `sequencegate`. A campaign can be staged and pushed
after per-message copylint with the sequence-level checks never run.

**H3 — `copylint`'s anti-fabrication REFUSE rule passes on lexical coincidence. `TASK-330`**
`_traces(value, supported)` reduces to `token in supported` — it checks only
whether the specific's exact string appears *anywhere* in the pack, never
whether it supports the claim being made. A pack containing "raised $50M in
2019" lets the fabricated sentence "grew revenue by $50M last quarter" pass as
traceable. This is precisely directives §9: *"A message sharing the word
'marketing' with a research pack is not evidence that the message is grounded."*

**H4 — `sequencegate` cannot catch a paraphrase.** Lexical overlap
`|wa ∩ wb| / min(|wa|,|wb|)` scores two paraphrases of one argument at 0.125
against a 0.45 threshold. Disclosed as a warning rather than hidden, but the
gate cannot fulfil its stated purpose — and per H2 it is not called anyway.

**H5 — A resume skips suppression revalidation. `TASK-331`**
`providerwrites.OPERATIONS[EMAIL_RESUME]` is `facing=False`, while the comment
three lines below calls resuming "the verb that puts a paused sequence back in
front of people - a sending action". `_perform` branches on that flag, so a
resume takes the non-facing path: no `executionguard` Authorization, no per-op
ledger reservation, and **no `revalidate()` re-check of unsubscribe/suppression
state** immediately before a paused sequence restarts. 76 suppressed recipients
exist from the 09-23 incident.
*Corrected from the finder's report:* resume is **not** ungated —
`reviewapproval.require` and `expect_leads` both apply inside the transport, and
EMAIL_RESUME **is** in `SUPPORTED` (added 2026-09-24, deliberately, so resumes
would stop bypassing the action ledger). The gap is the missing suppression
revalidation, not a total absence of gating.

**H6 — `ANTHROPIC_API_KEY`, `GROQ_API_KEY`, `OPENROUTER_API_KEY` are load-bearing and undocumented.**
All three are in `config.VARIABLES` and in `providers.model_key()`'s table; none
appears in `config/.env.example`. The per-provider model ceilings the handoff
calls "VERIFIED ON MASTER" depend on them.

**H7 — TASK-321's documented acceptance check is a string match that cannot prove wiring.**
The prose promises a test that "walks the import graph and fails if any module
… has no non-caller". The snippet given asserts `'copystages' in src` over
concatenated source text — which would pass the moment the word appears in a
comment. It also **already fails** on master, because the string appears in no
`src/*.py`.

**H8 — Stage E (strategy) is segment-invariant but coded per lead.**
6 model calls per lead across the six stages; at 50 leads in one segment, 49 of
50 stage-E calls are redundant. This is the plan's own TASK-320 argument,
confirmed in the code.

**H9 — No adapter requests prompt caching, and none exposes a batch entry point.**
`glm.complete` sends `{model, messages, max_tokens, temperature, stream}`;
`xai.respond` sends `{model, input, max_output_tokens, temperature, tools}`.
Zero matches for `cache_control`/`prompt_cache`/`ephemeral` anywhere against an
LLM call, and zero for `batch`. The static preamble measures ~1,439 words
against a ~60-word per-lead turn — roughly 24× more fixed text retransmitted and
paid for on every call. There is **no `src/providers/anthropic.py` at all**,
though Sonnet is what is being billed.

---

## MEDIUM

**M1** `spendledger.report()` / `main()` sum `expected_cost` across every row
regardless of unit (apify cents + credits + microusd) and print one "expected
total" with no warning — the exact defect the module's own comments say already
happened once. `client_balance()` *does* guard for mixed units; `report()` has no
equivalent. `TASK-332`

**M2** `researchpack/pack.py:run_actor` documents "THE COST HERE IS INTEGER
CENTS" and then calls `spendledger.reserve` **without** `unit="cents"`, so every
Apify row is written with no unit and no `usd_estimate`, despite the unit being
fully known at write time. `TASK-332`

**M3** `enrich.COSTS['xai-research'] = 2_000_000_000` (xAI ticks) sits in a dict
whose other values are single-digit credits, and `enrich`'s `spend()` calls
`record(...)` with no `unit=`. Dormant — no live call site — but it will ledger
two billion "credits" the moment one is added. `TASK-332`

**M4** A second, never-wired AI-spend ledger exists
(`scripts/task151_ai_spend_writer.py`, `work/ai-spend-ledger.jsonl`) with its own
schema, not registered in `store.STATE_OVERRIDES` and writing via a bare
`open()` with no `refuse_production_write` guard. If wired as its docstring
anticipates, a test run would append fabricated rows to a real client's file.

**M5** `copylint.WARNING_RULES` demotes `step1_without_pack_fact` from refuse to
warn under a directive "explicitly time-boxed to 2026-09-28", with **no date
check and no automatic reversion.** It will keep warning instead of refusing past
its own deadline until a human edits the frozenset.

**M6** Every derived state file in `docs/state/` is stale:
`TASK-REGISTRY.json` at `master_head da6860fb` (HEAD is later) and recording
TASK-317 as QUEUED/TODO while the file sits in `DONE/`; `LEDGER.json` and
`QUEUE-MANIFEST.json` from 09-20; `READY-RESERVOIR.json` from 09-18;
`PROVIDER-CAMPAIGNS.json` from 09-23. CLAUDE.md's own rule: *"a drifted ledger is
worse than none, because it is believed."* `PROBLEM-REGISTER.md` is also missing
both of the newest confirmed defects.

---

## LOW

**L1** `secondbrain.index_html`'s docstring claims it writes
`work/review/secondbrain-<client>.html`; the function only returns a string and
nothing opens a file. The unused `import os` is the residue.

**L2** `secondbrain.for_task` accepts `**scope` and never reads it, so a
caller's declared narrowing is silently discarded. (Also covered by TASK-322.)

---

## WHAT WAS NOT TESTED

- **No live run of anything.** No boot, no model call, no provider call, no
  network. Static analysis plus offline measurement only. Every CRITICAL is
  traced through the call graph, not executed.
- **Frontend, UX, accessibility and product-manager lenses: graded `I`.** Nobody
  was staffed, because booting the web app needs the `.env` that containment
  forbids. An unexamined dimension has no grade.
- Whether the $3.88 night reproduces zero ledger rows live — inferred from the
  absence of any writer in the call chain, not observed.
- Whether declared per-provider ceilings exist in a real client config —
  `config/clients/*.yaml` is absent from the clone by design, so "a ceiling that
  cannot fire" is established as "no writer exists", not against a declared
  value.
- The full bodies of `account.py`, `accountpolicy.py`, `heyreachfactory.py`, and
  `bisonfactory.py` past its staging head.
- `src/executionguard.py` was read only through its references.
