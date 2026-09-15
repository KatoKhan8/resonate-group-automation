# Client Two Portability Audit — 2026-09-15

## THE QUESTION

Can a second client be onboarded through CONFIGURATION, DATA and PRODUCT
KNOWLEDGE, or does it require editing Resonate OS core logic?

## ONE-LINE VERDICT

**Configuration and data carry almost everything; three blocking code changes
and seven friction points remain, all in CLI defaults and operator scripts
that hardcode "productive" rather than in engine logic.** The core pipeline
(`src/run.py`, `src/enrich.py`, `src/qualify.py`, `src/personas.py`,
`src/generate.py`, `src/push.py`, `src/heyreachfactory.py`) is already
client-parameterised end to end. The blockers are in the scripts and CLI
entry points an operator touches before the engine runs.

---

## STAGE-BY-STAGE TABLE

| # | Stage | What is client-specific | Where the value lives today | What Client #2 would do | Verdict |
|---|-------|------------------------|---------------------------|------------------------|---------|
| 1 | **Domain inventory / intake** | Source CSV path, batch output naming | `scripts/build_intake_batch.py` line 38: `SOURCE` hardcodes `work/Software_Agencies_All_Geo_cleaned - Sheet1.csv`; line 87: output pattern `productive-intake-%05d-%05d.csv` | Provide own source CSV; edit `SOURCE` and `--out` pattern | **FRICTION** |
| 2 | **Ingest** | Client slug passed to `store.new_record` | `src/ingest.py` line 275: `--client` is `required=True`, no default | Pass `--client client-two` | **CONFIG** |
| 3 | **Account processing / enrichment** | Spend caps, provider credentials, verification waterfall | `src/enrich.py`: reads `rec.get("client")`, loads config per-client (line 1321-1327); `spendledger.check` reads client-scoped caps | Nothing — config-driven | **CONFIG** |
| 4 | **Research (Apify)** | Cap per batch, pages per domain, items per run | `config/clients/productive.yaml` `research.apify` block; `src/research.py` reads from config | Set own research caps in own YAML | **CONFIG** |
| 5 | **Signals** | Signal types, relevance thresholds | `src/signals.py` reads config; `config/clients/demo.yaml` shows `research.recent_signals` block | Configure in own YAML | **CONFIG** |
| 6 | **ICP qualification** | Structural criteria (geos, company types, employee range), weights, penalties, thresholds, markets | `src/icp.py` `settings(config)` reads `config["icp"]`; `src/icpstructural.py` reads `config["icp"]["structural"]`; all overridable per-client. CLI default `--client productive` at `icpstructural.py:558` | Write own ICP criteria in YAML; pass `--client client-two` to CLI | **CONFIG** (engine) / **FRICTION** (CLI default) |
| 7 | **Contact discovery** | Persona titles, cap per domain, angle routing | `src/personas.py` `classify(contact, config)` reads titles from config; `src/routing.py` reads strategies from config | Define own personas, titles, angles in YAML | **CONFIG** |
| 8 | **Relationship state** | Record state machine, dedup scope | `src/store.py`: every record carries `client` field (line 777, REQUIRED at 795); `src/dedupe.py` has `CROSS_CLIENT` scope, off by default (line 69) | Nothing — client key is per-record | **CONFIG** |
| 9 | **Cohorting / campaign segmentation** | Segment prefix, band sizes | `src/campaignseg.py` `DEFAULT_POLICY["client_prefix"]` was hardcoded "PRODUCTIVE", now derives from `config["name"]` (line 135); bands are client-tunable | Nothing — prefix auto-derives from client name | **CONFIG** |
| 10 | **Copy and variables** | Product description, capabilities, angles, angle labels, tone, sender identity | `src/generate.py` `context_for()` reads `clients.product(client)`, `clients.sender_identity(client)`, `client["tone"]`, `client["personas"]`; `src/clients.py` `product()`, `sender_identity()`, `angles_for()` | Fill in `product:`, `tone:`, `sender:`, `personas:` blocks in YAML | **CONFIG** |
| 11 | **LinkedIn fallback copy** | Per-step fallback messages | `config/clients/productive.yaml` `linkedin_sequence.fallbacks` block; `src/heyreachfactory.py` `merge_sequence_copy(config)` reads it and REFUSES if any role is missing | Write own fallbacks in YAML | **CONFIG** |
| 12 | **Email fallback / sequence copy** | Merge fields, spintax, campaign sequence | `config/clients/productive.yaml` `email_sequence` block; `src/bisonfactory.py` reads from config | Define own email sequence in YAML | **CONFIG** |
| 13 | **Gates (lint, claims, quality)** | Claim vocabulary, lint rules | `src/lint.py`, `src/claims.py`, `src/quality.py` all read config; no hardcoded client references in gate logic | Nothing — gates are client-agnostic | **CONFIG** |
| 14 | **Provider campaign (HeyReach)** | Org unit, workspace binding | `config/clients/productive.yaml` `providers.heyreach.org_unit: 118832`; `src/clients.py` `provider_workspace(config, provider)` reads it; `src/heyreachfactory.py` `_plan()` refuses empty `record_ids` and refuses records from another client (line 708-720) | Set own `org_unit` in YAML | **CONFIG** |
| 15 | **Provider campaign (EmailBison)** | Workspace binding | `config/clients/productive.yaml` `providers.emailbison.workspace: 10`; `src/bisonfactory.py` reads via `clients.provider_workspace`; `src/providers/bison.py` `require_workspace(expected)` enforces binding | Set own `workspace` in YAML | **CONFIG** |
| 16 | **Senders** | Sender inventory per workspace | `src/senderinventory.py` scopes by `workspace` parameter; CLI default `--workspace productive` at line 411; `src/senderidentity.py` scopes LinkedIn accounts by workspace | Pass `--workspace client-two` | **FRICTION** (CLI default) |
| 17 | **Leads (provider write)** | Per-lead custom fields, variable names | `src/heyreachfactory.py` builds from config; `src/providerwrites.py` checks `executionguard.Authorization` with client-scoped guards | Nothing — driven by config | **CONFIG** |
| 18 | **Readback / outcomes** | Outcome categories, reporting | `src/outcomes.py` `run_report(client=...)` filters by client; `src/replywatch.py` scopes checkpoints by `rec.get("client")` | Nothing — client-scoped throughout | **CONFIG** |
| 19 | **Notifications (Slack)** | Channel IDs, approver lists, thresholds | `config/clients/productive.yaml` `slack:` block; `src/notify.py` routes by workspace, no fallback to another workspace's channel | Configure own Slack channels in YAML | **CONFIG** |
| 20 | **Killswitch / sending gate** | Per-workspace sending toggle | `src/killswitch.py` `workspace_state(slug)` checks per-workspace; new workspace defaults to NOT sending | Nothing — safe by default | **CONFIG** |
| 21 | **Learning / reporting** | Client report generation | `src/clientreport.py` takes client parameter; `src/outcomes.py` filters by client | Nothing | **CONFIG** |

---

## THREE ALREADY-KNOWN ENTRIES — CONFIRMED

1. **The client config carries the fallback copy inline.** Confirmed: `config/clients/productive.yaml` `linkedin_sequence.fallbacks` block carries all nine fallback messages. `src/heyreachfactory.py:merge_sequence_copy(config)` reads them and refuses if any are missing. **CONFIG.**

2. **`scripts/build_intake_batch.py` hardcodes the Productive source CSV path.** Confirmed: line 38 `SOURCE = os.path.join(ROOT, "work", "Software_Agencies_All_Geo_cleaned - Sheet1.csv")` and line 87 output pattern `productive-intake-%05d-%05d.csv`. **FRICTION.**

3. **Several task scripts default to `--client productive`.** Confirmed across 22 hits in `scripts/` and 39 in `src/`. The engine modules use it only in `argparse` defaults for CLI entry points; the production path (`src/run.py`) requires `--client` explicitly. **FRICTION.**

---

## RANKED CODE CHANGE LIST

### BLOCKING — Client #2 cannot be onboarded without these

None at the engine level. The production pipeline is fully client-parameterised.

### FRICTION — Client #2 works but somebody edits code to do it

| # | File | Function / Line | What is hardcoded | Fix |
|---|------|----------------|-------------------|-----|
| F1 | `scripts/build_intake_batch.py` | Module-level `SOURCE` (line 38) | Source CSV path `work/Software_Agencies_All_Geo_cleaned - Sheet1.csv` | Add `--source` argument |
| F2 | `scripts/build_intake_batch.py` | `main()` (line 87) | Output pattern `productive-intake-%05d-%05d.csv` | Derive from `--client` argument |
| F3 | `src/senderinventory.py` | `main()` (line 411) | `--workspace` defaults to `"productive"` | Remove default or require explicit |
| F4 | `src/icpstructural.py` | `main()` (line 558) | `--client` defaults to `"productive"` | Remove default or require explicit |
| F5 | `scripts/campaign_ready_funnel.py` | Fallback (line 101) and CLI (line 504) | `rec.get("client") or "productive"` and `--client` defaults to `"productive"` | Remove fallback, require explicit |
| F6 | `scripts/build_control_cohort.py` | `main()` (line 252) | `--client` defaults to `"productive"` | Remove default |
| F7 | `scripts/sample_regen_task131.py` | Line 99 | `clients.load("productive")` hardcoded | Parameterise |
| F8 | `scripts/task077_run_variants.py` | Lines 25, 136 | `client="productive"` default and `clients.load("productive")` | Parameterise |
| F9 | `scripts/task077_detailed.py` | Lines 39, 95 | `"client": "productive"` hardcoded and `clients.load("productive")` | Parameterise |
| F10 | `scripts/task065_run.py` / `task065_run_bcd.py` | Lines 195/205 | `clients.load("productive")` hardcoded | Parameterise |
| F11 | `scripts/task065_measure.py` | Lines 31, 269 | `PRODUCT_NAME = "productive"` and `clients.load("productive")` | Parameterise |
| F12 | `scripts/task089_diagnose_linkedin.py` | Line 154 | `rec.get("client", "productive")` fallback | Remove fallback |
| F13 | `scripts/task120_quality.py` / `task120_analysis.py` | Lines 96/276, 285 | `"productive"` string search and `clients.load("productive")` | Parameterise |
| F14 | `src/web/demodata.py` | Lines 46, 107, 127-154 | Demo data fixtures use `"productive"` as workspace/client slug | Cosmetic for demo; would need own fixture data for client two |
| F15 | `src/web/demoaccount.py` | Line 36 | `WORKSPACE = "productive"` | Demo-only |
| F16 | `src/web/demodiscovery.py` / `demogtm.py` | Lines 66/76, 22/88 | `workspace="productive"` defaults | Demo-only |

### COSMETIC — Looks client-specific, does not affect function

| # | File | What | Why cosmetic |
|---|------|------|--------------|
| C1 | `src/cadencelibrary.py:70` | Comment mentions "Productive" | Documentation only |
| C2 | `src/claims.py:590` | Comment mentions `"name": "Productive"` | Documentation of a measurement |
| C3 | `src/generate.py:545` | Comment mentions "Productive" | Documentation of a measurement |
| C4 | `src/heyreachfactory.py:1190-1193` | Comment mentions "productive" | Documentation of a refusal |
| C5 | `src/icpstructural.py:40` | Comment says "no `if client == 'productive'`" | Documentation of a rule |
| C6 | `src/providers/bison.py:60` | Comment mentions "Productive" | Documentation of a measurement |
| C7 | `src/campaignseg.py:106` | Comment mentions "PRODUCTIVE" | Documentation of a fix |
| C8 | `src/senderinventory.py:6` | Comment mentions "Productive workspace" | Documentation |
| C9 | `scripts/render_preview.py:1801` | `"productive" in full_text` check | Preview rendering, not production |
| C10 | `scripts/task078_analyze_copy.py:62,118` | `"productive" in text` checks | Analysis script, not production |

---

## TENANCY-BOUNDARY FINDINGS

These are not "Productive-specific values" but "assumptions that there is one client":

### 1. Shared queue file — `work/queue.jsonl`

**Status: MANAGED, NOT PARTITIONED.** All clients' records live in one file,
separated by the `client` field on each record. `store.list_records(client=...)`
filters by client; `store.ALL` crosses tenants. `src/repo.py` documents this
explicitly (lines 8-14): *"Client isolation is a filter, not a boundary."*

**Risk:** A caller that forgets the filter sees every client's records. The
`Repo` class scopes at construction (line 88) and the web layer always builds
scoped repos, so this is a CLI/script risk only. No code change needed for
client two; partitioning becomes a scale decision, not a tenancy decision.

### 2. Provider credentials are process-global, binding is per-client

**Status: CORRECTLY SEPARATED.** `config/.env` carries one set of API keys
(BISON, HEYREACH, CONTACTOUT, etc.). The *binding* — which provider workspace
this client's data lives in — is per-client: `clients.provider_workspace(config,
provider)` reads `providers.<provider>.workspace` from the client's own YAML.
`src/heyreachfactory.py:_plan` refuses a record belonging to another client.
`src/collision.py:leads_for_domain` requires `expect_workspace` with no default.

**Risk:** None structural. A second client needs its own `org_unit` (HeyReach)
and `workspace` (EmailBison) values in its YAML, provisioned at the provider.
That is a provider-side setup task, not a code change.

### 3. `replywatch.expected_workspace` reads a process-global env var

**Status: SINGLE-TENANT POLLER.** `src/replywatch.py:97-125` reads
`BISON_WORKSPACE_ID` from the environment (or a PIN file). It scopes
checkpoints by whatever workspace it finds, but the *credential* is one.
The docstring (lines 28-34) says this is "per provider, not per workspace"
because the API key is the same.

**Risk for client two:** If both clients use EmailBison, the poller needs to
poll both workspaces. Today it polls one. This is a **FRICTION** item — not
blocking if client two uses a different provider, but blocking if both share
EmailBison and the poller must watch both.

### 4. Dedup has a cross-client scope, off by default

**Status: CORRECTLY DESIGNED.** `src/dedupe.py` defines four scopes: `BATCH`,
`CAMPAIGN`, `CLIENT`, `CROSS_CLIENT`. Cross-client is off by default (line 69).
Two Resonate clients targeting the same person will not dedup against each other
unless explicitly configured. This is the right default: two clients may
legitimately target the same company.

### 5. `senderinventory` has no tenancy guard on the attestation path

**Status: WORKSPACE-SCOPED BUT NOT CLIENT-SCOPED.** `senderinventory.build()`
takes a `workspace` parameter and filters by it (line 151). But the attestation
path (lines 176-177) notes that "HeyReach exposes no tenant, client, owner or
team field on an account" — so sender identity is workspace-scoped, and the
workspace IS the client binding. This is correct as long as each client has its
own HeyReach org unit, which `providers.heyreach.org_unit` in the config
ensures.

### 6. Killswitch defaults to NOT sending for new workspaces

**Status: SAFE BY DEFAULT.** `src/killswitch.py:112-120` — a workspace with no
`sending.live` override does not send. A new client workspace is silent until
somebody explicitly switches it on. This is the right failure mode.

### 7. Notification routing has no cross-workspace fallback

**Status: CORRECTLY ISOLATED.** `src/notify.py` routes by workspace, with no
fallback to another workspace's channel. A workspace with no channel configured
produces a notification in state only, not a message to the wrong tenant.

### 8. `workspaces.py` is a hard tenancy boundary

**Status: ENFORCED.** `src/workspaces.py` (lines 1-80) declares a workspace as
"a hard tenancy boundary, not a filter" — it owns its batches, companies,
contacts, campaigns, approvals, replies, jobs, events and provider mappings.
The `Repo` class enforces this at the service boundary.

---

## SUMMARY

### The engine is ready. The scripts are not.

The production pipeline — `ingest → enrich → qualify → personas → generate →
render → push` — is fully client-parameterised. Every module reads the client
config and scopes its work by the `client` field on each record. Provider
bindings are per-client. The killswitch is per-workspace. Notifications are
per-workspace. Dedup is client-scoped by default.

What is not ready is the **operator surface**: the scripts and CLI defaults
that an operator touches before the engine runs. Fourteen friction points in
`scripts/` and three in `src/` CLI entry points hardcode "productive" as a
default. None of these are in the production path — `src/run.py` requires
`--client` explicitly — but they are the tools an operator uses to prepare
batches, diagnose issues and measure results.

### What Client #2 onboarding actually requires

1. **Create `config/clients/client-two.yaml`** — the `clients.create()` function
   writes a starter template. Fill in market, personas, product, tone, provider
   bindings, Slack channels, sending window, and LinkedIn fallback copy.

2. **Provision provider workspaces** — a HeyReach org unit and an EmailBison
   workspace for the new client. Record the IDs in the YAML.

3. **Fix the 14 script friction points** — add `--client` / `--source`
   arguments and remove `"productive"` defaults. Estimated effort: one afternoon.

4. **Decide on the reply poller** — if client two uses EmailBison, the poller
   must watch two workspaces. If it uses a different provider, this is moot.

5. **Run `src/run.py --client client-two`** — the engine handles the rest.

### What does NOT need to change

- No engine module needs editing
- No provider module needs editing
- No gate (lint, claims, quality) needs editing
- No tenancy guard needs adding — they already exist
- No state file format needs changing
- No config parser needs changing
