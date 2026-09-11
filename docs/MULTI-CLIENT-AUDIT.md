# Multi-client audit — Resonate OS against PRODUCT-GOAL.md

Audit only. Nothing here was changed; this document records what is true on
2026-09-11 so that in-flight work can be steered rather than restarted.
`PRODUCT-GOAL.md` is the standard being audited against and is not
re-litigated here.

Scope note: read-only. No provider call, no git mutation, no `work/*.jsonl`
write, no source change.

---

## 1. The goal is LOCKED

`PRODUCT-GOAL.md` exists, is unambiguous, and states the hierarchy, the
non-negotiable invariant, the eight contamination classes and the acceptance
test. This audit uses it verbatim.

One modelling question is genuinely open and is **not** a re-litigation of the
goal, because the goal's own hierarchy implies an answer the code refuses:

> `RESONATE -> CLIENT -> CLIENT WORKSPACE` is one-to-many in the goal.
> `workspaces.ensure` raises `ClientTaken` when a second workspace claims one
> client (`src/workspaces.py:1013-1019`), and `clients.overrides_for` raises
> for the same shape (`src/clients.py:181-186`).

The reason given is precise and correct: records, campaigns and jobs are scoped
by `repo.client`; the audit log, senders, notifications, reports and drafts are
scoped by `repo.workspace`. **Two scope keys, one hierarchy level, held equal
by a guard rather than by structure.** Until one of the two is derived from the
other, "CLIENT" and "CLIENT WORKSPACE" are the same object with two names.

---

## 2. Architecture compatibility: 42%

27 subsystems, scored READY 1.0 / PARTIAL 0.5 / NOT CLIENT-AWARE 0.25 /
PRODUCTIVE-SPECIFIC 0.25 / UNSAFE 0 / NOT IMPLEMENTED 0.

| Bucket | n | Weight | Points |
|---|---|---|---|
| READY | 3 | 1.00 | 3.00 |
| PARTIAL | 15 | 0.50 | 7.50 |
| PRODUCTIVE-SPECIFIC | 1 | 0.25 | 0.25 |
| NOT CLIENT-AWARE | 2 | 0.25 | 0.50 |
| UNSAFE FOR MULTI-CLIENT | 5 | 0.00 | 0.00 |
| NOT IMPLEMENTED | 1 | 0.00 | 0.00 |
| **Total** | **27** | | **11.25** |

11.25 / 27 = **41.7%, reported as 42%**.

The number is low for a specific and encouraging reason: the *data model* is
almost entirely client-aware (every record carries `client`, every campaign
carries `client`, every sender row carries `workspace`, every ledger row
carries a tenant), and the *access path* is not. Tenancy is enforced in one
layer — `src/repo.py` — and the web layer is the only consumer behind it. Every
CLI and every batch stage reaches `store.load()` directly. 61 of 92 CLI
entry points in `src/` take no `--client` at all.

---

## 3. Classification

### READY

| Subsystem | Evidence | Why |
|---|---|---|
| action ledger | `src/actionledger.py:130-137`, `:193-219`, `:250-267` | The tenant key is defined as the client slug, is keyword-required, is enforced inside the write lock, and the provider estate is recorded separately as evidence and explicitly "never used as the tenant key". |
| spend ledger | `src/spendledger.py:85`, `:139`, `:146-149` | `check()` refuses an unscoped spend outright: "a spend check needs a client; an unscoped budget is one client paying for another's run". |
| provider writes | `src/providerwrites.py:280-305`, `:162` | Cannot be invoked for a prospect-facing operation without an `executionguard.Authorization`, which carries `workspace` (client slug) and `provider_workspace` separately. `SUPPORTED = ()`, so no prospect-facing write exists today at all. |

Honourable mentions outside the 27: `killswitch` refuses on an unnamed
workspace at every layer (`src/killswitch.py:112-128`); `senderidentity` has no
unscoped read by construction (`src/senderidentity.py:140-143`, `:105`);
`agencydnc` is the model for "deliberately global by policy" — hashed, closed
vocabulary, leaks nothing between tenants (`src/agencydnc.py:2-45`, `:84`);
`repo.save_campaign` now refuses a campaign claiming another client's records
(`src/repo.py:340-345`).

### PARTIAL

| Subsystem | Evidence | Why |
|---|---|---|
| configuration | `src/clients.py:192`; `src/config.py:51`; `src/configdiff.py:432` | Per-client YAML is required and slug-validated, but `config.py` has no tenant concept — every provider credential is one global env var — and `provider_bison`'s workspace pin is optional. |
| queue / state | `src/store.py:585`, `:665`; `src/repo.py:11-14` | `client` is a required record field but only an optional filter argument. `repo.py`'s own docstring names this gap. `validate()` checks the key is present, never that it holds a client (`tests/test_workspace_isolation_attacks.py:572`). |
| qualification | `src/qualify.py:248`, `:256`, `:264`, `:283` | `client=None` waives the filter and qualifies every tenant; `campaignseg.assign` then decides segment rungs across the mixed result set, so one client's cohort size moves another's assignment. |
| personas | `src/personas.py:312`, `:387`, `:425` | Per-row `clients.load(rec.get("client"))` is correct and fails closed on a missing config, but `run()` takes no client and rewrites the whole queue. |
| research | `src/research.py:333`; `src/providers/apify.py:200`; `src/webfetch.py:221` | No entry point takes a client, but the per-row fallback fails closed (scraping off by default). Blemish: an unkeyed module-level `_cache={}`. |
| identity | `src/senderidentity.py:140-143`; `src/duplicates.py:250`; `src/dedupe.py:190-209` | `senderidentity` is exemplary; `duplicates` falls back to `recs[0]`'s client; `dedupe`'s weak name-match branch omits the client check its strong branch performs at `:178-181`. |
| suppression | `src/agencydnc.py:2-45`; `src/hygiene.py:221`; `src/ingest.py:31`, `:109` | Agency DNC is deliberate and privacy-engineered. `config/suppress.txt` is a flat global domain list with **no client key**, so one client's customer is suppressed for every tenant, and nothing explains that as policy. |
| collision | `src/collision.py:105`, `:133`, `:316`, `:326` | Every entry point requires a workspace and fails closed — but `expect_workspace` means an EmailBison numeric estate on the email path and a Resonate client slug on the LinkedIn path. Two identity spaces, one parameter name. |
| fatigue | `src/fatigue.py:88`, `:261` | Record-local and leak-free by construction; nothing forces the caller to supply the right client's config, and `config=None` silently substitutes module defaults. |
| claims | `src/claims.py:295`; `src/outreachclaims.py:217`, `:221` | Evidence is record-local and fails closed. `workspace` is optional and used only to look up a display name, never to verify the named sender belongs to this client's roster. |
| approval | `src/approve.py:96`, `:221-224`, `:230` | Writes derive the client from the record. `pending()` defaults to the whole multi-tenant queue and its entries carry no client field; it also reads the unscoped `campaigns.by_record`. |
| campaigns | `src/campaigns.py:126-154`, `:319-344` | `new_campaign` carries `client` — and **no provider-workspace binding of any kind** (no `org_unit`, no bison workspace). `by_record` is unscoped and maps an ambiguous record to `None`. |
| EmailBison adapter | `src/providers/bison.py:228-252`, `:242-243` | `bound_workspace()` genuinely proves the credential's binding and `require_workspace` refuses a mismatch. `require_workspace(None)` returns `None` — unpinned passes. |
| sender inventory | `src/senderidentity.py:140-143`; `src/senderinventory.py:370-386`, `:411`; `src/senderteam.py:113` | Scoped accessors with no unscoped variant, undermined by a hard-coded `--workspace default="productive"` on the command that *replaces* inventory, an unpinned provider read, and `team_for`'s first-row fallback. |
| reporting | `src/reports.py:66`, `:116`; `src/web/api.py:3391`; `src/funnel.py:266-273`, `:287-289` | Durable report rows are workspace-keyed and the web path is repo-scoped. `funnel.measure` has no client parameter and folds an all-tenant `actionledger` count into a per-cohort funnel. |

### PRODUCTIVE-SPECIFIC

| Subsystem | Evidence | Why |
|---|---|---|
| ICP | `src/icp.py:2`, `:56-58`, `:201`; `src/segments.py:28`, `:222` | The dimension set and vertical taxonomy are client #1's market by construction — `segments.py:222` says so: "without it this taxonomy is Productive's market and no one else's". An extension point exists (`segments.settings`, honoured at `icp.py:221`, tested in `tests/test_custom_verticals.py`) but `score(rec, config=None)` runs on the defaults when no config is passed, and the starter template ships no market at all (`src/clients.py:233-245`). |

Also structurally Productive-shaped and worth naming even though they are not
in the 27: `src/strategy.py:24-152` (the pain vocabulary, with no config path
to replace it — `settings()` at `:109` exposes only `max_angles` and
`include_unsupported`) and `src/playbooks.py:103-190` (six plays keyed on those
pains; `recommend(..., config=None)` accepts a config and never consults it for
the library).

### NOT CLIENT-AWARE

| Subsystem | Evidence | Why |
|---|---|---|
| HeyReach adapter | `src/providers/heyreach.py:37`, `:106`; `src/campaigns.py:126-154` | There is no `bound_workspace` equivalent: HeyReach cannot say which estate a key reads. `customFields` come back empty on every conversation, so `record_id`/`contact_key`/`client` are written and never read back. `org_unit` — the only LinkedIn tenancy pin `executionguard` accepts — is **never written by any production path**; only tests set it. And `_account_id_for` falls back to account id `0` two lines below a docstring saying guessing one "would send a prospect from a profile nobody chose". |
| observation | `src/leadobserve.py:57`, `:99-121`, `:125` | Provider truth about leads is written to one shared file keyed by provider campaign id and lead id, with **no client column at all**, so an observation cannot be attributed or filtered per tenant after the fact. |

### UNSAFE FOR MULTI-CLIENT

| Subsystem | Evidence | Why |
|---|---|---|
| orchestrator | `src/run.py:305`, `:310-313`; `src/orchestrator.py:45-62`, `:86-91` | `run(--client X)` passes the client to `ingest.run` **only**; the stages then walk `store.load()` with no client filter. One `--cap`, one `--limit`, one credit `Budget` for every tenant in the queue. Separately, `orchestrator.create` and `set_records` write campaign membership through `campaigns.save` directly, bypassing `repo.save_campaign`. |
| enrichment | `src/enrich.py:1019`, `:1027-1032`, `:1072-1074` | `run()` takes no client, reads the whole estate, shares one in-memory credit `Budget` across tenants, and sets the run-wide Apify scrape ceiling from **whichever record is processed first**. A tenant declaring `max_runs_per_batch: 0` inherits whoever sorted ahead of it. |
| verification | `src/mx.py:754-757`, `:769`, `:782-790` | `python -m src.mx run --client <slug> --live` loads that client's config and then applies it in an **unfiltered** estate-wide loop, persisting the result with `store.save(recs)`. One client's MX and email-security policy decides every other tenant's contacts. `verification.py` itself is a clean policy library with conservative defaults. |
| executionguard | `src/executionguard.py:206-227`, `:402-405` | It is the right shape — a token nothing can forge, six gates in a fixed order — and it has one hole and one fail-open. It **never compares `rec["client"]` to `campaign["client"]`**: the `record` gate checks truthiness only. And the email tenancy gate is `bison.require_workspace(workspace)`, which returns `None` for `workspace=None` — so an unpinned call passes tenancy and the gate is appended anyway. |
| reply handling | `src/events.py:423`; `src/replywatch.py:97-112`; `src/poller.py:391`, `:441` | The tenancy assertion is `if event.get("client") and ...` — skipped entirely when the event carries no client, which `events.py:341-343` itself calls "the ordinary shape of a LinkedIn reply". Polling is unpinned unless `BISON_WORKSPACE_ID` is set, and that key is absent from `config/.env.example`. HeyReach has no identity read at all (`IDENTIFY = {"emailbison": bison.bound_workspace}`). |

### NOT IMPLEMENTED

| Subsystem | Evidence | Why |
|---|---|---|
| stream controller | `src/run.py:291-313`; `STREAMING-ARCHITECTURE.md` | No scheduler module exists. `run()` is the stage-major, positional-slice loop that document explicitly rejects, and there is no fair-scheduling dimension between clients — which is item 5 of the goal's own scale ordering. |

---

## 4. Top 10 multi-client gaps, ranked by prospect-facing risk

Ranking note: `providerwrites.SUPPORTED = ()` and `push.run(live=True)` raises
`LiveSendNotEnabled`, so **nothing reaches a prospect from this build today**.
The ranking is therefore by what would reach a prospect the day sending is
enabled, not by what is reaching one now.

1. **`executionguard.authorize` never compares the record's client to the
   campaign's.** `src/executionguard.py:206-211`. The last gate before a
   prospect-facing write cannot tell whose record it is authorising. Every
   other gate — approval, readback, collision, fatigue, cap, ledger — is
   evaluated against the *campaign's* client.
2. **A campaign's provider binding is a CLI argument, not canonical state.**
   `src/campaigns.py:126-154` (no binding field), `src/executionguard.py:649`
   (`--workspace` required on the command line). Nothing in canonical state
   says which provider estate this client may use, so nothing can refuse the
   wrong one; the operator supplies it at the moment of the write.
3. **The reply path applies an untenanted event to whatever record matches.**
   `src/events.py:423` plus an unpinned poll (`src/replywatch.py:97-112`). A
   reply read from the wrong estate pauses the wrong client's account, fires a
   positive-reply alert and enters an append-only log that cannot be retracted.
4. **`orchestrator.create` / `set_records` bypass the ownership check.**
   `src/orchestrator.py:45-62`, `:86-91` vs `src/repo.py:340-345`. The guard
   that refuses a campaign claiming another client's records exists and is
   tested; the CLI path does not go through it.
5. **One record in two campaigns detaches every campaign-level stop.**
   `src/campaigns.py:342-343` maps the ambiguous record to `None`;
   `src/eligibility.py:399-400` returns immediately on `None`, so freeze,
   pause, rejection and approval-staleness all stop applying.
6. **`src/run.py` processes every tenant's queue in one pass.** `:310-313`.
   `--client` reaches ingest only. This is the blast radius for credits, model
   spend and generated copy.
7. **`src/mx.py:783` applies one named client's policy to the whole estate and
   saves it.** Email-security and MX screening is a prospect-facing decision;
   this writes another tenant's verdict from the wrong policy.
8. **`senderinventory --workspace` defaults to client #1.**
   `src/senderinventory.py:411`, with an unpinned provider read at `:370-386`.
   One invocation rewrites the sender roster of whichever estate the credential
   is bound to, under the slug `productive`.
9. **Client suppression is a global file with no client key.**
   `src/ingest.py:31`, `:109-122`. This is goal contamination bullet 2 — "one
   client's suppression suppressing another's" — in the plainest form. Agency
   DNC is correctly global; a client's own customer list is not.
10. **Provider account id `0` is substituted when none is chosen.**
    `src/providers/heyreach.py:106`, `src/push.py:343`, `src/web/api.py:2918`.
    A postable-looking payload with a sender nobody selected, and the approval
    preview never shows the account that would actually send.

---

## 5. Productive hard-coding

| Category | Count | Verdict |
|---|---|---|
| TEST FIXTURE | 1,122 lines / ~175 files | Correct. Leave alone. |
| VALID CLIENT CONFIG | 905 lines / 14 files | Correct. Leave alone — `PRODUCT-GOAL.md` says so explicitly. |
| DOCUMENTATION | 216 lines / ~50 files | Correct, and mostly prose explaining why something is *not* coupled. |
| LEGACY | 3 items | Dead, not dangerous. |
| **HARD-CODED ARCHITECTURAL COUPLING** | **13 firm, 2 borderline** | The only structural problem. |

### The coupling, item by item

Literal client identity as a default:

1. `src/senderinventory.py:411` — `p.add_argument("--workspace", default="productive")`.
   The only line of executable non-demo code in `src/` containing the string.
   `--live` with no `--workspace` replaces client #1's provider inventory from
   whatever credential is loaded.

Implicit default client identity — "first record in the store wins". These
contain no literal, but in this estate `recs[0]` is a client-#1 record, so the
engine defaults to client #1's configuration for everyone else's rows:

2. `src/push.py:461` — pilot volume ceiling from `recs[0]`'s client.
3. `src/push.py:514` — kill-switch verdict evaluated against `recs[0]`'s client.
4. `src/report.py:426` — no client parameter exists; whole report rendered from `recs[0]`'s config.
5. `src/revival.py:367-369` — one signal index, built from `recs[0]`'s client, assesses every record.
6. `src/quality.py:428` — quality thresholds from `recs[0]`'s client.
7. `src/duplicates.py:250` — duplicate policy from `recs[0]`'s client.
8. `src/enrich.py:1072-1074` — the run-wide Apify scrape ceiling from the first record processed.

Default provider account substituted when none is chosen:

9. `src/providers/heyreach.py:106` — `int(fallback or 0)`.
10. `src/push.py:343` — `linkedin_account_id or 0`.
11. `src/web/api.py:2918` — `linkedin_account_id=0` hard-coded into the approval preview.

Client #1's product vocabulary compiled into engine modules:

12. `src/strategy.py:38-152` — `PAINS`, `PAIN_WORDS`, `SUPPORTED_BY`,
    `PERSONA_PAINS`, `VERTICAL_ANGLES`, and the fallback at `:152` that hands
    any unrecognised vertical client #1's three core pains as its messaging
    brief. `settings()` at `:109` offers no way to replace them. Flows to
    `qualify.py:100` → `contextpack.py:255` → generation.
13. `src/playbooks.py:103-190` — six plays keyed on those pains; `recommend()`
    at `:302` takes a `config` and never consults it for the library.

Borderline (extension point exists, defaults are client #1's):

14. `src/icp.py:61` — twelve fixed dimensions; weights and thresholds are
    overridable, unknown keys ignored at `:155`, so a client can zero a
    dimension but cannot declare one.
15. `src/segments.py:47`, `:68` — default taxonomy is client #1's market;
    mitigated by `segmentation.verticals` (`:216-241`, tested).

### Counter-evidence worth preserving

The repository is unusually disciplined here and several places refuse to
default on purpose. Do not "simplify" these: `src/replywatch.py:109-111`
("deliberately not defaulted to Productive's 10: a default would assert
ownership this module cannot prove"); `src/providers/bison.py:228-240` (no
workspace parameter exists on any function in the module, by design);
`src/collision.py:105` (`expect_workspace=REQUIRED`, after a real incident);
`src/notify.py:280-290` (two matches returns `None` rather than picking one);
`src/workspaces.py:476-490` (no default Slack channel and no inference from the
workspace name).

---

## 6. The canonical client abstraction

**One already exists. Do not build a second.**

`src/repo.py` is it. A `Repo` is scoped at construction and cannot be widened;
`Repo.for_client` is the CLI constructor, `Repo.for_user` is the only one a
request path may use, `admin_repo()` is the single named escape hatch and the
web layer has a test asserting no handler calls it. `CrossClientAccess` is
raised rather than returning `None`, because "the difference between 'does not
exist' and 'is not yours' is the difference between a bug and a breach"
(`src/repo.py:57-63`). `src/workspaces.py` supplies membership, five roles,
granular permissions and an audit log that names a super-admin crossing.

The canonical answer to "which Resonate client does this record or action
belong to?" is **the `client` slug on the row, reachable only through a
`Repo`.** That answer is right. What is wrong is its reach.

Strengthen it in four moves, smallest first:

1. **Make `client` non-null, not merely present.** `src/store.py:588-592`
   checks the key exists. `client: None` passes `store.append` and creates a
   row no tenant owns and no tenant can repair — characterised already in
   `tests/test_workspace_isolation_attacks.py:572`. One line in `validate()`.

2. **Give `Repo` the two methods the batch path needs, and use them.**
   `records()` and `save_records()` exist. What the pipeline reaches for is
   `store.load()`. The change is not a refactor of every module — the domain
   functions are correctly pure over a list — it is that `run.py`,
   `enrich.run`, `mx.main`, `qualify.run`, `personas.run` and `approve.pending`
   take their record list from a `Repo` instead of from `store`. Their
   per-record `clients.load(rec.get("client"))` lookups can then stay exactly
   as they are.

3. **Collapse `client` and `workspace` to one key, or derive one from the
   other.** Today `ClientTaken` (`src/workspaces.py:1013-1019`) holds them
   equal by refusal. Either make the workspace slug the canonical identity and
   the client file a property of it, or keep the client canonical and make
   workspace a display grouping. Two keys guarded into agreement is the shape
   that drifts.

4. **Per-client suppression.** Split `config/suppress.txt` into an agency-level
   list and a per-client one, keeping `agencydnc` exactly as it is. This is the
   one place where the goal's contamination list and the current file layout
   disagree outright.

---

## 7. The canonical provider binding

**One does not exist, and this is the largest structural gap.**

Three facts:

- Provider credentials are process-global environment variables. One
  `BISON_KEY`, one `HEYREACH_KEY`, one `APIFY_TOKEN`, one `CONTACTOUT_TOKEN`,
  one Slack bot, one LLM key for the whole deployment
  (`src/config.py:51-170`, `src/providers/__init__.py:73-79`). `key(name)`
  takes no client.
- The canonical campaign row carries no binding at all
  (`src/campaigns.py:126-154`). `org_unit` is read by `configdiff` and
  `executionguard` and written by nothing outside tests.
- The word "workspace" names two different things. `executionguard.py:412-423`
  says it outright: "`workspace` here is EmailBison's numeric estate id …
  Everywhere else in this system the tenant is the client slug". The same
  ambiguity is inside one parameter in `collision.py`: `expect_workspace` is a
  provider estate id on the email path (`:133`) and a Resonate client slug on
  the LinkedIn path (`:316`).

The mechanism to prove "which provider workspace may this client use?" should
be **one binding row per (client, provider), held in canonical state, proved
against the provider at use time, and fail-closed when absent.** Two patterns
already in the repository show both halves of how:

- `src/providers/bison.py:228-252` — `bound_workspace()` asks the provider what
  it is bound to and `require_workspace` refuses a mismatch before the first
  page is read. That is the proof half. It needs the expected value to come
  from the binding row rather than from `--workspace`, and
  `require_workspace(None)` must stop returning `None`.
- `src/collision.py:304-323` — `our_linkedin_seats(workspace)` derives the
  tenant boundary from **the answer** rather than the query, against canonical
  per-client inventory, and raises `CollisionUnknown` when the roster is empty
  rather than reading an unscoped inbox as "no prior contact". That is the
  pattern for HeyReach, which has no identity read of its own.

Naming discipline is part of the fix, not cosmetic: `client` for the Resonate
tenant, `provider_workspace` for the vendor estate, everywhere.
`actionledger.py:130-137` and `:245-248` already keep them apart correctly and
is the reference.

---

## 8. Known cross-client defects, and what should have made them impossible

| # | Defect | What the architecture should have made structurally impossible |
|---|---|---|
| 1 | `orchestrator.create` / `set_records` bypass `repo.save_campaign`'s ownership check (`src/orchestrator.py:45-62`, `:86-91`) | Campaign membership should be writable through exactly one path. `repo.save_campaign` already refuses a campaign claiming a foreign or non-existent record (`src/repo.py:340-345`, tested at `tests/test_workspace_isolation_attacks.py:348`). A second writer to the same canonical state is the defect; the check is not. |
| 2 | `executionguard.authorize` never compares `rec["client"]` to `campaign["client"]` (`src/executionguard.py:206-211`) | A prospect-facing action should be un-constructible without one tenant identity that every input agrees on. The record, the campaign, the sender seat and the provider estate should all have to name the same client before an `Authorization` exists — the gate already proves the sender belongs to the campaign's client (`:377-381`); the record is the one input it never asks about. |
| 3 | A reply polled under one estate can be applied to another tenant's record, because HeyReach `customFields` is empty and `events.apply`'s tenancy check is skipped by its own guard (`src/events.py:423`, `src/providers/heyreach.py:37`) | An event should carry its tenant or be refused. The guard is `if event.get("client") and ...` — it disables itself for exactly the events that cannot name a client. Where the provider cannot round-trip an identifier, the tenant must be derived from proved provider-side inventory (the `our_linkedin_seats` pattern) and the event refused when it cannot be, rather than matched against the whole queue. |
| 4 | One record in two campaigns makes `campaigns.by_record` answer `None`, detaching freeze, pause, rejection and approval (`src/campaigns.py:342-343`, `src/eligibility.py:399-400`) | Campaign membership should be an exclusive, canonical fact a record can answer about itself, not an index rebuilt by scanning campaigns. And `None` from an ambiguity must never resolve to "no campaign constraints" — the ambiguity is the reason to stop, so it should return a refusal the eligibility path reports, not an absence it skips. |

---

## 9. The multi-client acceptance test

**Status: specified, not implemented.** No test in `tests/` runs the execution
pipeline over two clients.

### What exists to build on

- **`tests/test_workspace_isolation_attacks.py:82-135` (`Estate`)** — the
  closest base by far. Two synthetic clients in a throwaway directory,
  `store.use_directory` moving all 22 state files together, `CLIENTS_DIR`
  moving the client configs, two workspaces, three users including a super
  admin, one record and one campaign each, two sender rosters that
  deliberately share a `provider_account_id`, and two `Repo.for_user` handles.
  Its first assertion is that nothing is touching the real `work/`.
- **`tests/campaignbase.py` (`CampaignTest`)** — the single-client pipeline
  fixture: verified contacts built from real evidence, two distinct step
  bodies, approval, cadence, campaign file. This is the half `Estate` lacks.
- **`tests/base.py` (`ProviderTest`)** — the network tripwire, the cassette
  player, credential clearing, and `FIXTURE_WORKSPACE = {"id": 99}`, chosen
  fictional on purpose so a fixture exercises the identity read without
  naming a real estate.
- **`src/web/demodata.py:106-121`** — already builds a three-workspace estate
  with separate client configs, campaigns, users and memberships. Proof the
  data model supports it.
- **`tests/test_new_client_from_zero.py`** — onboards a client with no source
  change and names each platform limitation rather than working around it.
- **`tests/test_cadence_tenancy.py:62-99`** — the structural half worth
  copying: asserts by import graph that a module reads no state of its own.

### The test to write

`tests/test_two_clients_through_one_engine.py`. Client A configured as client
#1 is; Client B synthetic, with a deliberately *different* ICP (non-agency
vertical), different domains, different personas and angles, its own sender
pool, its own suppression entries, its own budget, its own campaign intent, and
its own provider binding. Both walked through the same engine: ingest →
qualify → research → enrich → verify → personalize → campaign → gates →
authorize → observe → reply → report.

Twelve assertions, one per goal contamination class plus resilience:

1. No contact of B appears in any payload, draft or campaign of A.
2. No evidence gathered for B licenses a claim in A's copy (`claims.check`).
3. No sender of B is selected for A (`senderidentity` already raises).
4. Neither client's campaign lists the other's record ids.
5. A provider read taken under B's binding cannot satisfy A's gate.
6. B's suppression entries do not suppress A's prospects; agency DNC
   suppresses both, and that is asserted as *deliberate*.
7. A collision answer computed against B's estate does not answer for A.
8. A reply arriving with no client, matching a contact both clients hold, is
   refused for both — and one arriving under B's estate never reaches A.
9. Every credit charged during the run is attributable to exactly one client
   in the spend ledger, and A's cap is not consumed by B's records.
10. An approval granted in A does not authorise a step in B.
11. Every action-ledger reservation names one client, and B's cap does not
    move A's.
12. Pausing B (workspace kill switch off, campaign frozen, budget exhausted)
    leaves A's safe work proceeding, and a raised exception on a B record does
    not abandon A's already-paid enrichment.

### What prevents it being written today

Five things, in order:

1. **No per-client provider binding.** Assertion 5 has nothing to bind. There
   is one credential set and no canonical row saying which estate a client may
   use. This is the blocker, not a detail.
2. **The pipeline is not client-scoped.** `run.py:310` loads every tenant, so
   assertions 1, 9 and 12 would be measuring the bug rather than the
   behaviour — and `enrich.py:1072` would give B client A's scrape ceiling.
3. **Suppression has no client dimension.** Assertion 6 cannot be expressed
   against `config/suppress.txt` at all.
4. **No LinkedIn tenancy pin is settable.** `org_unit` has no writer outside
   tests, so a HeyReach-side binding for B cannot be configured through any
   operator path.
5. **`campaigns.by_record` is unscoped.** Assertion 4's negative case — B
   detaching A's records — is reachable through `orchestrator.create`.

Assertions 3, 10 and 11 could be written today and would pass.

---

## 10. The next single best architectural action

**Make the client the thing an `Authorization` is constructed from, rather than
a field on one of its inputs.**

Concretely, in `src/executionguard.py`, as a gate-0 before the existing tenancy
gate: resolve one tenant identity and require every input to agree with it —
`rec["client"]`, `campaign["client"]`, the sender seat's workspace, and the
provider estate named by the client's binding. Refuse when any is absent;
`bison.require_workspace(None)` must stop being a pass.

Why this one, over nine other true things in this document:

- It is the smallest change that closes defect 2 outright and makes defects 1
  and 4 unable to reach a prospect even while they remain open.
- It forces the provider binding to become canonical state, because the gate
  will have nowhere to read the expected estate from. That is section 7's fix
  arriving as a consequence of a safety requirement rather than as a refactor.
- It is surgical. `executionguard` is already the single chokepoint by design,
  `providerwrites` already refuses anything that is not a genuine
  `Authorization`, and `SUPPORTED = ()` means the change can be made and
  proved with no live exposure at all.
- It matches the goal's closing instruction: when two designs are otherwise
  equal, choose the one that makes a cross-client operation impossible rather
  than the one that detects it.

Everything else in section 4 is then a spend, correctness or reporting bug
rather than a prospect-facing one — which is the right order to fix them in.
