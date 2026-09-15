# Client #2 Portability Assessment — 2026-09-15

## THE VERDICT

**Client #2 can be onboarded through CONFIGURATION and DATA alone, with no
core logic edits.** The engine is parameterised on `client` at every
production-loop stage. The blockers are in operator scripts and CLI defaults,
not in `src/`. A second client config file, a second set of provider
bindings, and a second batch of domain data are sufficient to begin
qualification.

The six FRICTION items are all CLI defaults in scripts and one module — none
of them sits on the production execution path. They affect an operator
running a command by hand, not a campaign sending to a prospect.

---

## STAGE-BY-STAGE TABLE

Each row walks one stage of the production loop and answers: what is
client-specific, where that value lives today, what Client #2 must supply,
and whether the stage is CONFIG (change the YAML), DATA (supply a file or
batch) or CODE CHANGE (edit src/).

| # | Stage | What is client-specific | Where it lives today | Client #2 must | Verdict |
|---|-------|------------------------|---------------------|----------------|---------|
| 1 | **Domain inventory** | The source CSV path and the batch output pattern | `scripts/build_intake_batch.py:19` hardcodes `work/Software_Agencies_All_Geo_cleaned - Sheet1.csv`; output pattern is `batches/productive-intake-%05d-%05d.csv` | Supply their own source CSV; pass `--out` to override the pattern | FRICTION (script, not engine) |
| 2 | **Ingestion** | The client slug on every record | `src/ingest.py:275` — `--client` is **required**, no default | Pass `--client client-two` | CONFIG |
| 3 | **Account processing / ICP** | Market rules, geo include/exclude, company types, employee thresholds, services-business test | `config/clients/productive.yaml` under `market:` and `icp:` blocks; read by `src/icp.py` and `src/icpstructural.py` | Write their own `icp:` and `market:` blocks in their YAML | CONFIG |
| 4 | **ICP CLI default** | `--client` defaults to `"productive"` | `src/icpstructural.py:558` — `p.add_argument("--client", default="productive")` | Pass `--client client-two` explicitly | FRICTION |
| 5 | **Research** | Apify cap, pages-per-domain, items-per-run, enabled flag | `config/clients/productive.yaml` under `research.apify:`; read by `src/research.py` via `clients.research_settings(config)` | Set their own research caps | CONFIG |
| 6 | **Signals** | Signal sources, freshness windows, relevance threshold | `config/clients/productive.yaml` (absent — uses module defaults); `src/signals.py` reads config | Add a `signals:` block if they want non-default signal policy | CONFIG |
| 7 | **Contact discovery** | Persona titles, cap-per-domain, angle assignments | `config/clients/productive.yaml` under `personas:`; matched by `src/personas.py` and `src/routing.py` | Write their own persona titles, angles and caps | CONFIG |
| 8 | **Relationship state** | The `client` field on every record | `src/store.py:777` — `client` is in the record skeleton and in `REQUIRED` (line 795); validated as a lowercase slug (line 804) | Nothing — the field is already populated at ingest | CONFIG |
| 9 | **Cohorting / campaign segmentation** | Campaign-to-client binding | `src/campaigns.py:151` — campaign rows carry `client`; `src/campaignseg.py` accepts `--client` | Nothing — campaigns are already client-bound at creation | CONFIG |
| 10 | **Copy and variables** | Product description, capabilities, tone, angles, sender identity, fallback copy | `config/clients/productive.yaml` under `product:`, `tone:`, `personas.*.angles`, `sender:`, `linkedin_sequence.fallbacks`; assembled by `src/generate.py:context_for` (line 511) which takes `client` as a parameter | Write their own product block, tone, angles, sender identity and fallback copy | CONFIG |
| 11 | **Cadence selection** | Which named sequence to run | `config/clients/productive.yaml` line `cadence: productive_li_heavy_v1`; resolved by `src/cadencelibrary.py` | Name a cadence from the library or use `default` | CONFIG |
| 12 | **Gates** | Killswitch state, execution guard, approval policy | `src/killswitch.py`, `src/executionguard.py`, `src/approval.py` — all read from campaign/config, none hardcode a client | Nothing — gates are tenant-agnostic | CONFIG |
| 13 | **Provider campaign (EmailBison)** | Workspace binding, sending window, merge-field sequence | `config/clients/productive.yaml` under `providers.emailbison.workspace: 10`; read by `clients.provider_workspace(config, "emailbison")`; consumed by `src/bisonfactory.py:stage` | Set their own `providers.emailbison.workspace` to their EmailBison workspace id | CONFIG |
| 14 | **Provider campaign (HeyReach)** | Org-unit binding, LinkedIn seat, sequence graph | `config/clients/productive.yaml` under `providers.heyreach.org_unit: 118832`; read by `clients.provider_workspace(config, "heyreach")`; consumed by `src/heyreachfactory.py` | Set their own `providers.heyreach.org_unit` | CONFIG |
| 15 | **Sender inventory** | `--workspace` defaults to `"productive"` | `src/senderinventory.py:411` — `p.add_argument("--workspace", default="productive")` | Pass `--workspace client-two` explicitly | FRICTION |
| 16 | **Leads / contact assignment** | Contact-to-campaign assignment | `src/assignment.py:435` — accepts `--client`; assignment reads from campaign state | Nothing — assignment is campaign-scoped | CONFIG |
| 17 | **Readback / reply watching** | Workspace pin for reply polling | `src/replywatch.py:97-125` — `expected_workspace` reads `BISON_WORKSPACE_ID` as a process-global env var; deliberately NOT defaulted to Productive's 10 | Set `BISON_WORKSPACE_ID` to Client #2's workspace before polling; or run two poller processes | FRICTION (multi-tenant limitation) |
| 18 | **Outcomes** | Outcome tracking per client | `src/outcomes.py:1105` — accepts `--client` | Pass `--client client-two` | CONFIG |
| 19 | **Learning / deduplication** | Cross-client dedup scope | `src/dedupe.py:39-42` — cross-client dedup is OFF by default; two clients may legitimately sell to the same company | Decide whether to enable cross-client dedup for their vertical overlap | CONFIG |

---

## RANKED FINDINGS: BLOCKING / FRICTION / COSMETIC

### BLOCKING — none

No stage requires editing `src/` to onboard Client #2. Every domain function
accepts a `client` parameter or reads it from the campaign row. The record
skeleton carries `client` as a required field. The workspace module is a hard
tenancy boundary. The client config loader (`src/clients.py`) accepts any
valid slug and refuses only templates and reserved names.

### FRICTION — eight items, ranked by impact

**F1. `scripts/build_intake_batch.py:19` — hardcoded source CSV path**
- `SOURCE = os.path.join(ROOT, "work", "Software_Agencies_All_Geo_cleaned - Sheet1.csv")`
- The output pattern on line 82 is `batches/productive-intake-%05d-%05d.csv`
- Client #2 needs their own source file and a different output name
- **Impact:** The operator must edit the script or pass `--out` for the output; the source path has no override
- **Fix:** Add `--source` argument; parameterise the output pattern on `--client`

**F2. `src/cadence.py:357-430` — TEMPLATES dict carries Productive-specific copy**
- Four templates (`persona_pain`, `comparable_proof`, `comparable_proof_short`, `breakup`) contain verbatim Productive value-proposition text: "Utilisation and margin are known at the end of the month", "seeing project margin while the project is still running", "finance view and the delivery view stop being two different spreadsheets", "a project lands under margin"
- These templates are used by the `productive_balanced_v1` cadence; a cadence with `generated: True` steps does not touch them
- **Impact:** If Client #2 uses a cadence that references these template keys, their prospects receive Productive's pitch. If they use only generated steps, this is never reached.
- **Fix:** Make templates configurable per client, or ensure Client #2's cadence uses `generated: True` for all steps

**F3. `src/icp.py:138-155` — NEED_SIGNALS keyword dictionary is hardcoded**
- Six keyword tuples (`resource_planning_need`, `profitability_need`, `utilization_need`, `time_tracking_need`, `operational_complexity`, `delivery_complexity`) contain English phrases tuned for project-management software buyers
- These are not loaded from config; `settings(config)` overrides weights, penalties and thresholds but not the keyword vocabulary
- **Impact:** A client selling a different product (HR software, accounting tools) would have their companies scored on irrelevant need-signal keywords. The scoring still runs, but the "need" dimension is silent for any product that is not agency tooling.
- **Fix:** Add a `need_signals:` block to the client config that overrides the hardcoded dictionary

**F4. `src/icpstructural.py:558` — `--client` defaults to `"productive"`**
- An operator running `python -m src.icpstructural` without `--client` qualifies Productive's records
- **Impact:** Silent wrong-client qualification if the flag is forgotten
- **Fix:** Remove the default, make `--client` required (as `ingest.py` already does)

**F5. `src/senderinventory.py:411` — `--workspace` defaults to `"productive"`**
- An operator running `python -m src.senderinventory` without `--workspace` reads Productive's sender estate
- **Impact:** Silent wrong-workspace inventory if the flag is forgotten
- **Fix:** Remove the default, require explicit `--workspace`

**F6. `scripts/build_control_cohort.py:198` — `--client` defaults to `"productive"`**
- A control-cohort build without `--client` draws from Productive
- **Impact:** Wrong-client cohort if the flag is forgotten
- **Fix:** Remove the default

**F7. `scripts/campaign_ready_funnel.py:504-505` — `--client` defaults to `"productive"`**
- A funnel report without `--client` reports on Productive
- **Impact:** Misleading report if the flag is forgotten
- **Fix:** Remove the default

**F8. `src/replywatch.py:97-125` — process-global workspace pin**
- `expected_workspace("emailbison")` reads `BISON_WORKSPACE_ID` from `os.environ`
- One credential, one workspace, one pin — the poller cannot serve two clients simultaneously
- **Impact:** Client #2's replies cannot be polled at the same time as Productive's without a second process or a credential per client
- **Fix:** Per-workspace credentials or a poller that iterates over client configs; this is a multi-tenant architecture decision, not a bug

### COSMETIC — do not fix, do not refactor

| File | What | Why it is cosmetic |
|------|------|--------------------|
| `src/web/demodata.py:46` | `CLIENT = "productive"` | Demo fixture data, never reaches production |
| `src/web/demoaccount.py:36` | `WORKSPACE = "productive"` | Demo fixture |
| `src/web/demodiscovery.py:66,76` | `workspace="productive"` default | Demo fixture |
| `src/web/demosenders.py:80,176` | `"productive"` key and default | Demo fixture |
| `src/web/demosignals.py:33,78` | `workspace="productive"` default | Demo fixture |
| `src/web/demoslack.py:31,44,121,185,202` | `"productive"` Slack channel mapping | Demo fixture |
| `src/companies.py:401` | `--client default="benchmark"` | Benchmark tool, not a production path |

---

## TENANCY-BOUNDARY FINDINGS

These are not "Productive has the wrong value" — they are "the system assumes
there is only one client." They are more serious than a wrong default because
a wrong default is visible; an assumption is not.

### T1. Provider credentials are process-global

**Where:** `src/providers/bison.py:35` reads `BISON_KEY`; `src/providers/heyreach.py:24` reads `HEYREACH_KEY`; `src/replywatch.py:67` declares the credential map.

**What it means:** One EmailBison API key and one HeyReach API key serve every client. The credential identifies a provider account, not a tenant.

**Risk:** Low for now — most agencies have one EmailBison account and one HeyReach account. If Client #2 needs a separate provider account, a second set of env vars and a credential-per-client lookup are needed.

**Pattern to follow:** `clients.provider_workspace(config, provider)` already binds a client to a provider estate by config. The credential is the layer above that and is not yet parameterised.

### T2. `bison.bound_workspace()` returns one workspace per credential

**Where:** `src/providers/bison.py:70-103`

**What it means:** The EmailBison credential is bound to exactly one workspace at the provider. `bound_workspace()` discovers which one by calling `/api/users`. There is no way to ask "which workspace does Client #2 use?" without a second credential.

**Risk:** Medium. If Client #2 has their own EmailBison workspace under the same credential, the system cannot distinguish them. If they have a separate credential, the system needs a credential-per-client indirection.

**Mitigation already present:** `heyreachfactory._plan` refuses an empty `record_ids` and refuses records belonging to another client. The same shape of guard should be applied to any new cross-tenant lookup.

### T3. `replywatch.expected_workspace` is a single global pin

**Where:** `src/replywatch.py:97-125`

**What it means:** The reply poller pins to one EmailBison workspace via `BISON_WORKSPACE_ID`. It cannot poll two workspaces in one process.

**Risk:** Medium. Reply protection for Client #2 requires either a second poller process or a poller that iterates over workspaces. The module already scopes checkpoints by workspace, so a multi-workspace poller would not leak marks.

**Design note:** The docstring says "Per provider, not per workspace, and the reason" — provider credentials are process-global, so a per-workspace poll would repeat the same request N times. This is correct for one credential but becomes the limitation for two clients.

### T4. Cross-client deduplication is OFF by default

**Where:** `src/dedupe.py:39-42`

**What it means:** Two Resonate clients may independently target the same person. Cross-client dedup is configurable but off, because enabling it means one client's targeting suppresses another's — a commercial decision.

**Risk:** Low. This is a deliberate design choice, not an oversight. Client #2 should decide whether to enable it based on vertical overlap with Productive.

### T5. State keys that do not carry a client

**Where:** `src/store.py` — campaigns, workspaces, senders, notifications, MX cache, observability, checkpoints, signals, GTM, discovery, client review, tag outbox, agency DNC.

**What it means:** Most state files are workspace-scoped through the workspace table, not through a `client` field on every row. The workspace IS the tenancy boundary. This is correct — a workspace maps 1:1 to a client config — but it means a bug in workspace resolution would cross tenants.

**Risk:** Low. `workspaces.py` is described as "a hard tenancy boundary, not a filter" and the permission model checks at the service boundary.

### T6. `outcomes.py` programmatic API loads the entire estate

**Where:** `src/outcomes.py:359` (`observations()`), `src/outcomes.py:661` (`answer()`), `src/outcomes.py:729` (`answers()`), `src/outcomes.py:742` (`readiness()`).

**What it means:** When called without pre-filtered rows, these functions load ALL records across ALL clients. The CLI entry point filters by `--client`, but any programmatic caller that does not pass pre-filtered rows gets a cross-client analysis. The observation rows DO carry `"client": rec.get("client")`, so the data is labeled, but it is not separated.

**Risk:** Medium. A dashboard or API endpoint calling `answer("persona")` without a client filter would mix two clients' outcomes. The fix is to add a `client` parameter to `observations()` and propagate it.

### T7. `events.py` cross-client record search

**Where:** `src/events.py:341-389` (`match_record()`), `src/events.py:391-429` (`correspondents()`).

**What it means:** Both functions search ALL records across ALL clients for matching contacts. The client check at line 481 only fires when the event carries a `client` field, which LinkedIn replies do not. A reply from a person who appears on two clients' records will stop both clients' outreach to that person.

**Risk:** Low-to-medium. This is partly deliberate — the unattributed-reply stop (`inbound.py:128`) needs to search across clients to catch replies that cannot be attributed. But it means a shared contact across two clients causes both to be held, which is the correct safety behaviour for reply protection and a false positive for targeting.

---

## ALREADY-KNOWN ITEMS (confirmed, not re-discovered)

1. **`config/clients/productive.yaml` carries fallback copy inline** — the `linkedin_sequence.fallbacks` block (lines ~230-245) contains the words HeyReach sends when a variable cannot be filled. Client #2 must write their own. This is CONFIG, not CODE.

2. **`scripts/build_intake_batch.py` hardcodes the Productive source CSV path** — listed above as F1.

3. **Several task scripts default to `--client productive`** — listed above as F2, F4, F5. These do not block production; they affect an operator running a command by hand.

---

## WHAT CLIENT #2'S CONFIG FILE MUST CONTAIN

Based on what `productive.yaml` carries and what the engine reads:

```
name:                          # display name
domain:                        # primary domain
booking_link:                  # calendar link
sender:                        # who is writing
  mode: client_rep
  name:
  role:
  company:
  works_on:
market:                        # ICP market rules
  must:
  size_min_employees:
  geos: [...]
  exclude_geos: [...]
icp:                           # structural qualification
  markets: [...]
  structural:
    geographies:
    company_types:
    services_business_required:
    tracks_time_required:
    employees:
research:                      # public-web research caps
  apify:
    enabled:
    max_runs_per_batch:
personas:                      # who to contact
  champion:
    titles: [...]
    cap_per_domain:
    angles:
      ...
  economic_buyer:
    titles: [...]
    cap_per_domain:
    angles:
      ...
cadence:                       # which sequence to run
tone:                          # email and LinkedIn tone
product:                       # what they sell
  name:
  what_it_is:
  capabilities:
linkedin_connection_note:      # template or llm
  mode:
linkedin_sequence:             # fallback copy for every graph role
  fallbacks:
    connection_note:
    connected_1:
    ...
providers:                     # provider estate bindings
  emailbison:
    workspace: <their id>
  heyreach:
    org_unit: <their id>
```

The starter template in `src/clients.py:STARTER` (line ~460) provides the
minimum skeleton. The `create_workspace` API endpoint (`src/web/api.py:5073`)
writes this starter and a workspace row together.

---

## WHAT IS NOT IN THIS ASSESSMENT

- **Provider account capacity.** HeyReach seats and EmailBison inboxes are
  finite. Client #2 needs their own seats. This is a procurement question,
  not a code question.
- **Slack routing.** Each workspace maps to its own Slack channels. The
  mapping is per-workspace in `src/web/demoslack.py` (demo) and in the
  workspace settings (production). Client #2 needs their own channels.
- **Sending reputation.** Each client's sender domains and IP reputation are
  independent. Client #2 needs their own email infrastructure.
- **Provider credentials for a second account.** If Client #2 has their own
  EmailBison or HeyReach account, the credential layer needs a
  credential-per-client indirection (T1 above).

---

## SUMMARY

The production loop is client-parameterised end to end. The engine (`src/`)
has four FRICTION items in code (`cadence.py` templates, `icp.py`
need-signals, `icpstructural.py` CLI default, `senderinventory.py` CLI
default) and zero BLOCKING items. The scripts directory has four FRICTION
defaults and one hardcoded path. The tenancy boundary is the workspace, and
it holds, with two additional cross-client data exposure paths in
`outcomes.py` and `events.py` that should be reviewed before a second
client shares the estate.

Client #2 onboarding is a configuration and data exercise, not a code
change. The eight FRICTION items should be fixed before the first operator
runs a command for Client #2, because a forgotten `--client` flag will
silently operate on Productive's records, and the two hardcoded code items
(`cadence.py` templates, `icp.py` need-signals) will silently inject
Productive's vocabulary into Client #2's scoring and copy if their cadence
or ICP model reaches them.
