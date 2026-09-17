# Comparative review of open-source GTM engines

2026-09-17T18:37:03.128682+00:00. Grok with web_search, 55 sources.

**A README IS A CLAIM, NOT AN IMPLEMENTATION.** The prompt demanded a file path per architectural claim and NOT FOUND where the code could not be located. Nothing here is adopted because another repository has it: this estate's production evidence and existing invariants remain authoritative, and every candidate pattern still has to earn its place against them.

---

I'll inspect the actual GitHub code for each repo, starting with opengtm, and only report what the files implement.
The first search missed several repos. I’ll open the GitHub URLs directly and hunt for the missing names.
I have the repo overviews. Next I’ll walk the source trees and open implementation files, not READMEs.
OpenGTM’s tree fetch failed; I’ll pull its directory listing and search the code for the claimed features.
The OpenGTM tree is large. I’ll search the repo for waterfall, cache, spend, RLS, and related files.
I’ll open the service directories and the implementation files that should hold waterfall, cache, spend, and RLS.
I’ll read the core implementation files next: waterfall/enrichment, cache, tenancy, signals, CLI/MCP.
Next I’ll read WaterfallEnricher, cache, spend/RLS, signals, CLI/MCP, and count providers vs sources.
Code-only review. READMEs ignored except as claims to check.

---

## 1. `debpalash/OpenGTM` (deepest)

**1. Pattern.** Clay-style **workbook cell engine**: each column is a typed transform (waterfall / AI / HTTP / research / output) over tenant-scoped rows, with workers claiming jobs.

**2. Evidence.** `apps/api/services/workbook/enrichment.py`, `apps/api/services/workbook/providers.py`, `apps/api/worker.py`, `apps/api/core/tenancy.py`.

**3. Feature map**

| Feature | Code |
|---|---|
| Cross-row evidence caching | `apps/api/services/leadgen/enrichment/cache.py` (identity key + TTL). Used by `WaterfallEnricher` in `.../enrichment/provider.py`. **Workbook hot path does not call it** (`enrichment.py` walks providers and `break`s on first value). |
| Cost-ordered provider waterfall | `apps/api/services/workbook/planner.py` `order_chain()` (yield/cost + cooldown + budget). Workbook uses it. |
| Cost/yield ledger | `apps/api/services/workbook/planner_models.py` `ProviderStat`; `planner.record_attempt()`. |
| Confidence early-exit | `WaterfallEnricher.EARLY_EXIT_CONFIDENCE = 0.85` in `provider.py`. **Workbook path: first success, not confidence.** |
| Checkpointed/resumable connector runs | `apps/api/services/workbook/ambitionbox_import.py` (`cursor.next_page`, `seen_record_ids`, resume). |
| Buying-signal baseline+diff | `apps/api/services/poller/account_group.py` (`bootstrapped` suppress, `pricing_fingerprint` hash-diff, `partnership_job_ids`). Also hiring-band scan in `.../signals/monitor.py`. |
| Per-lead **multichannel** state machine | Email-only: `apps/api/services/outreach/sequence.py`. LinkedIn track **NOT FOUND**. |
| Sender/capacity allocation | In-process SMTP hour cap in `.../outreach/sender.py`. No multi-sender pool. |
| Spend ceilings | `Workbook.budget_max_usd` / `budget_spent_usd` in `enrichment.py` + `database.py` migration. |
| Evidence freshness/TTL | `cache.py` `TTL_DAYS` (email 30d … founded 365d). |
| Multi-tenancy / RLS | `apps/api/core/tenancy.py` + `apps/api/database.py` `set_config('app.workspace_id')`; migrations `e5f6a7b8c9d0_workbooks_rls.py`, `c42d0273d9bd_pg_tenancy_...`. SQLite path is per-workspace file, not RLS. |
| Stable CLI/MCP | CLI: `apps/api/cli.py`. MCP: `apps/mcp/server.py` + `apps/api/services/mcp/`. |

**Documented claims — code vs README**

| Claim | Verdict |
|---|---|
| ~90 sourcing sources | **Count matches, kind does not.** `source_registry.py` has **92 `"name"` entries** — DuckDuckGo `site:` query templates, not 90 scrapers. |
| ~35 enrichment providers | **Roughly true.** ~35 Python files under `.../enrichment/providers/` plus YAML manifests (`.../declarative/manifests/email/leadmagic.yaml`). Registry in `workbook/providers.py`. |
| Cost-ordered waterfalls | **True on workbook path** (`planner.order_chain`). Defaults in `DEFAULT_WATERFALLS` are still free-then-paid lists. |
| Cross-row caching | **Implemented, split.** Real in `WaterfallEnricher`; **not** on `enrich_cell`. |
| Confidence early-exit | **Same split.** |
| Checkpoint/resume | **True for connector imports**, not for generic enrichment cells. |
| Buying signals | **True**, including first-run suppress + page fingerprint. |
| Cost/yield ledger | **True** (`provider_stats`). |
| Spend ceilings | **True** (workbook USD cap). |
| Multi-tenancy/RLS | **True on Postgres**; SQLite is workspace files. |

**4. Better than a system that already has 2-vendor verify, approval fingerprints, reservation ledger, collision gating, write-readback.** Workbook DAG (formulas, HTTP, research, output columns). Learned yield/cost reorder + workbook spend cap. Tenant RLS + scoped MCP. Connector page cursors. Account-group signal fingerprint diffs. ~90 DDG source *queries* as cheap discovery.

**5. Worse / missing.** No reservation-before-call (ledger is post-hoc `ProviderStat`). No account collision gating. No LinkedIn execution. Cache is process-wide SQLite, not RLS-scoped. Workbook waterfall is first-hit, not confidence. “90 sources” are search templates. AGPL-3.0. Huge surface.

---

## 2. `clawnify/OpenProspector`

**1. Pattern.** **BYO-key contact waterfall**: first *verified* hit wins; identity cache; append-only attempt ledger; callback pause/resume.

**2. Evidence.** `src/server/providers/index.ts` (`runWaterfall`, `DEFAULT_ORDER`, `cacheKey`), `src/server/enrich.ts`, `src/server/cache.ts`, `src/server/schema.sql`.

**3. Feature map**

| Feature | Code |
|---|---|
| Cross-row caching | `src/server/cache.ts` `d1Cache` + `schema.sql` `enrichment_cache`; key `field\|name\|domain`. Also `companies` store. |
| Cost-ordered waterfall | **Hardcoded cheapest-first** `DEFAULT_ORDER` in `providers/index.ts`; user reorder via `waterfall_config`. Not a learned planner. |
| Cost/yield ledger | `enrichment_attempts` + `recordAttempts()` / `providerStats()`. **After** the call, not reserve-before-call. |
| Confidence early-exit | **First verified wins** (unverified held as fallback). No numeric confidence threshold. |
| Checkpoint/resume | `pending_enrichments` + `resumeLead()` / `expireOverdue()` in `enrich.ts`. Waterfall pause, not connector pagination. |
| Buying-signal baseline+diff | **Yes.** `signal_checks.baseline`, `signal_observations.fingerprint`, `visible=0` on baseline (`monitor-routes.ts`). Dedup in `signals.ts`. |
| Per-lead multichannel SM | **NOT FOUND** (no send). |
| Sender/capacity | **NOT FOUND**. |
| Spend ceilings | `credits_spent` is a **sum**, not a hard stop. **NOT FOUND**. |
| Evidence TTL | `CACHE_MAX_AGE_DAYS = 90` in `providers/index.ts`. |
| Multi-tenancy/RLS | **NOT FOUND** (single SQLite/D1). |
| CLI/MCP | **OpenAPI** on Hono (`src/server/index.ts`). No MCP server in-repo. |

**4. Better.** Tightest open implementation of identity cache + verified-win waterfall + callback vendors + hidden first-run signal baseline. Company cache so Stripe is bought once.

**5. Worse.** Weaker than your reservation ledger. No collision gating, no send, no tenancy, no spend ceiling. Relies on Clawnify agents API for sourcing/monitors.

---

## 3. `Abhipaddy8/outreach-agent`

**1. Pattern.** **Prompt-orchestrated Claude Code agent.** State = markdown files. No runtime.

**2. Evidence.** `CLAUDE.md`, `.ai-guide/missions.md`, `AERCHITECT.md`, `MEMORY.md`, `skills/*.md`, `.mcp.json`. Recursive tree: **no `.py`/`.ts` engine**.

**3. Feature map** — all **NOT FOUND** as code. Prompt stand-ins:

- “Resume” = checkboxes in `.ai-guide/missions.md` (agent-honored).
- “State machine” = `AERCHITECT.md` log.
- MCP = **third-party** servers in `.mcp.json` (Gmail, Tavily, Apollo, Apify, Instantly). Not a product control surface.
- Verify = Instantly via Composio, instructed in `CLAUDE.md`.
- Signals = `skills/signal-monitor.md` (prompt).

**4. Better.** Nothing you don’t already enforce in software. Maybe copy/research prompt packs.

**5. Worse.** No invariants. Keys in markdown. No ledger, cache, tenancy, limits, fingerprints. Session-quality only.

---

## 4. `moaljumaa/linki`

**1. Pattern.** **Dual-track per-lead sequencer** (LinkedIn ∥ email) driven by a Playwright runner + SQLite.

**2. Evidence.** `lib/linkedin/runner.ts` (`run_profile_tracks`, `trAdvance`/`trWait`/`trSkip`), `lib/db.ts` (`workflow_steps.track`, daily limits), `lib/linkedin/{connect,message,visit,session}.ts`, `lib/email/sender.ts`.

**3. Feature map**

| Feature | Code |
|---|---|
| Cross-row caching | **NOT FOUND** (Sales Nav filter cache only). |
| Cost-ordered waterfall | **NOT FOUND**. Enrich = Apollo (`lib/apollo.ts`) + Sales Nav scrape. |
| Cost/yield ledger | LLM `cost_usd` table in `db.ts`; not a provider waterfall ledger. |
| Confidence early-exit | **NOT FOUND**. |
| Checkpoint/resume | Import batches `list_imports.scheduled_for` / `start_page`. Sequence resume via `current_step` + `next_step_at`. |
| Buying-signal baseline+diff | **NOT FOUND**. |
| Per-lead multichannel SM | **Yes.** `run_profile_tracks` states `pending\|in_progress\|completed\|failed\|skipped`, parallel `linkedin`/`email` tracks. |
| Sender/capacity allocation | **Yes, per account.** `daily_connection_limit`, `daily_message_limit`, `daily_inmail_limit`, `daily_email_limit` + email ramp-up (`effectiveEmailLimit`). Not a global allocator across campaigns. |
| Spend ceilings | **NOT FOUND** (action counts, not USD). |
| Evidence TTL | **NOT FOUND**. |
| Multi-tenancy/RLS | **NOT FOUND** (single-user SQLite + password). |
| CLI/MCP | OAuth tables in `db.ts` for “hosted MCP”; **`pages/api/mcp` NOT FOUND**. OSS control surface is Next API routes. |

**4. Better.** Real LinkedIn+email step machine, working-hours, daily caps, session pinning. Your stack is stronger on data/verify/ledger; this is stronger on **channel execution state**.

**5. Worse.** LinkedIn ToS/fingerprint automation. No waterfall, no identity cache, no RLS, no reservation ledger, no collision gating. Sustainable-use license, not MIT.

---

## 5. `LaGrowthMachine/gtm-system`

**1. Pattern.** **Claude skill pack + installer that points at a hosted SaaS MCP.** Not an outbound engine.

**2. Evidence.** `skills/**/SKILL.md` (e.g. `skills/get-qualified-meetings/multichannel-campaign-builder/SKILL.md`), `install.sh` (`MCP_URL=https://mcp.lagrowthmachine.com`). Some skill scripts (`skills/catch-opportunities/objection-analyzer/scripts/analyze.py`) — local analytics, not send/enrich.

**3. Feature map** — engine features **NOT FOUND**. MCP is **remote LGM**, not in this repo (`LaGrowthMachine/lgm-mcp` is a separate product wrapper). No cache, waterfall, ledger, RLS, spend cap, state machine.

**4. Better.** Campaign-copy playbooks and reply-triage prompts if you already use Claude + LGM.

**5. Worse.** Execution lives in LGM. No data plane to steal. “Secure my channels” folder is empty (“Coming soon”).

---

## Table

| repo | pattern | verdict | why | cost |
|---|---|---|---|---|
| **opengtm** | Workbook cell engine + tenant workers | **ADAPT** | Steal planner (`order_chain`), workbook spend cap, Postgres RLS+MCP, connector cursors, account-group fingerprint diffs. Do **not** take DDG-as-90-sources or first-hit workbook waterfall; cache/confidence live on a **different** path than the workbook. Your reservation ledger + collision gating stay strictly better. | **High** — large Python/TS monorepo, AGPL-3.0, dual SQLite/PG |
| **OpenProspector** | Verified-win BYO waterfall | **ADAPT** | Best open code for identity cache, first-verified-wins, callback resume, hidden-baseline monitors, per-attempt credit log. **Do not replace** your reserve-before-call ledger with their append-after-call `enrichment_attempts`. | **Med** — focused TS, MIT, ~19 vendor adapters |
| **outreach-agent** | Markdown agent OS | **REJECT** | No executable invariants. Prompt files cannot beat fingerprints/ledger/gating. | **Low** to read; **negative** if used as runtime |
| **linki** | Dual-track LinkedIn+email SM | **ADAPT** (execution) / **REJECT** (data plane) | Steal `run_profile_tracks` + per-account daily caps/ramp. Reject Playwright LinkedIn as a core dependency if you already have provider write+readback. | **High ops** — sessions, ToS, fingerprints; source-available license |
| **gtm-system** | Skill pack → LGM MCP | **DEFER** | Useful only as copy/ICP prompts. No engine. MCP is SaaS lock-in. | **Low** (markdown) unless you adopt LGM |

**If you implement one thing from this set:** OpenProspector’s `runWaterfall` + `d1Cache` + baseline-hidden monitors — **beside**, not instead of, reservation-before-call. **If you implement one thing from OpenGTM:** `planner.order_chain` + `budget_max_usd` on the workbook/enrich path you already own.

## Sources searched

- https://github.com/quanyuchen2000/OPENTM
- https://github.com/openSUSE/opengm
- https://gitlab.com/ir2-lab/opentrim/-/tree/main
- https://github.com/vivan1211/opengp/blob/main/README.md
- https://github.com/orgs/openthread/repositories
- https://github.com/quanyuchen2000/OPENTM
- https://github.com/Robinlovelace/open-gat
- https://github.com/openSUSE/opengm
- https://github.com/sindresorhus/opn
- https://github.com/Gforcex/OpenGraphic/blob/master/README.md?plain=1
- https://github.com/PyCQA/prospector
- https://iopscience.iop.org/article/10.3847/1538-4365/abef67
- https://github.com/SAP/project-kb/blob/main/prospector/README.md
- https://prospector.landscape.io/en/master/usage.html
- https://github.com/landscapeio/prospector/blob/master/docs/supported_tools.rst
- https://github.com/Abhipaddy8/outreach-agent
- https://github.com/Abhipaddy8/outreach-agent
- https://github.com/codeharsh27/outreach-agent
- https://github.com/cporter202/agentic-ai-starters/tree/main/starters/outreach-agent
- https://github.com/ComposioHQ/outreach-agent
- https://github.com/moaljumaa/linki
- https://github.com/moaljumaa/linki/releases
- https://raw.githubusercontent.com/moaljumaa/linki/main/pages/inbox.tsx
- https://github.com/Xbobo5530/linki
- https://github.com/team-gritty/linki
- https://pipeline.zoominfo.com/sales/gtm-system
- https://github.com/shyftai/GTMOS
- https://www.lovesdata.com/blog/google-tag-gateway/
- https://github.com/sem-technology/gtm-copilot
- https://github.com/shawnla90/gtm-coding-agent
- https://github.com/buildingopen/opengtm
- https://github.com/debpalash/Opal
- https://www.linkedin.com/pulse/launching-opengtm-ben-salzman-9o2fc
- https://opengtm.com/
- https://www.opengtm.org/
- https://github.com/quanyuchen2000/OPENTM
- https://github.com/opengm/opengm/blob/master/README.md
- https://github.com/openSUSE/opengm
- https://gitlab.com/ir2-lab/opentrim/-/tree/main
- https://doc.oplist.org.cn/guide/installation/manual

---

## CLAUDE VERDICT, 2026-09-17 — four ADAPT, one REJECT, the rest DEFER

The review did what was asked: it read implementation files and it caught the
kind of discrepancy a README review never does. **OpenGTM's "~90 sourcing
sources" are 92 DuckDuckGo `site:` query templates in `source_registry.py`,
not 90 scrapers** - the count matches and the kind does not. And its
cross-row cache and confidence early-exit are real in `WaterfallEnricher` and
**not called on the workbook hot path**, which `break`s on the first value.
That is this repository's own recurring defect - a thing computed correctly
that nothing downstream reads - found in somebody else's codebase, and it is
the reason to read code rather than claims.

### What we already do better, and should not trade away

- **Reservation before the call.** OpenGTM's ledger is post-hoc
  (`planner.record_attempt`, `ProviderStat`). `actionledger.reserve` is
  written BEFORE the provider call, which is what makes a post-timeout retry
  impossible without reconciling. Nothing in the reviewed set has it.
- **Account-level collision gating.** NOT FOUND in any of them. Ours is the
  gate that stops a second person at an account somebody is already in
  sequence with.
- **Two-vendor verification and approval fingerprints.** Not present anywhere
  reviewed.
- **LinkedIn execution.** Only `linki` attempts multichannel; OpenGTM's
  sequence engine is email-only.

### ADAPT — four, in order of what they would buy us

1. **Evidence TTL by FIELD, not by record.** `cache.py`: email 30 days,
   founded 365. Our evidence problem is live - generation holds records for
   `evidence_not_traceable` and 4 of 550 records carry any evidence - and a
   field-typed TTL is the difference between re-buying a company's founding
   year and re-buying a deliverable address.
2. **Cost/yield ledger that REORDERS the waterfall.** `planner.order_chain()`
   ranks on measured yield/cost with cooldown and budget.
   `PROVIDER-ROUTING-POLICY.md` fixes our order by policy, deliberately and
   for a product reason - so this is ADAPT as *evidence for changing the
   policy*, never as an automatic reorder that would quietly demote
   ContactOut.
3. **A spend ceiling in money, not in calls.** `Workbook.budget_max_usd` /
   `budget_spent_usd`. `enrich.spend()` writes a ledger and caps calls; it
   does not cap dollars. Tonight's numbers - $0.196 a domain for Grok
   evidence, $1.40 a documentation question - are exactly what a USD ceiling
   is for.
4. **Connector cursors.** `ambitionbox_import.py` carries `cursor.next_page`
   and `seen_record_ids` and resumes. Our runs re-walk.

### DEFER

The MCP/CLI control surface (`apps/mcp/server.py`, `apps/api/cli.py`). It is
the right shape eventually and the wrong thing to build while the constraint
is seventeen unsigned approvals. Our equivalent already half-exists as
`production_status.py`, `verification_inventory.py`, `email_sender_estate.py`,
`sender_pool_census.py` - a control surface would be a thin stable wrapper
over those, not new capability.

### REJECT

The workbook cell engine as an architecture. It is a good product and a
different one: a general typed-transform DAG over rows, where this system is
a narrow pipeline with safety gates at named points. Adopting the DAG would
put every gate in the position of a column somebody could reorder.

**Nothing here is adopted because another repository has it.** Each of the
four ADAPT items is a task to be measured against our own production
evidence, and the existing invariants stay authoritative.
