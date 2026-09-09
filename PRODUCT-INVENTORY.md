# Product Inventory

Every area of Resonate Outbound OS, what state it is in, and where it lives.

Kept as a living document. The point of it is the second column: an area with a
strong backend and no screen is not finished, and a screen with no backend
behind it is worse than not finished.

Statuses:

| Status | Means |
| --- | --- |
| **IMPLEMENTED** | Backend and UI both, tested |
| **PARTIAL** | Works, but a named piece is missing |
| **BACKEND ONLY** | Real capability, no way to reach it from the app |
| **UI ONLY** | A screen with nothing real behind it. Should never appear |
| **MISSING** | Does not exist |
| **DEMO ONLY** | Exists only in demo mode |
| **LIVE VALIDATION REQUIRED** | Built and tested offline; never exercised for real |

Two columns of status: where this mission found things, and where it left
them. A row that did not move is not a failure - most of this product was
already built - but a row that moved from BACKEND ONLY to IMPLEMENTED is
where the work went.

---

## Areas

| Area | Before | After | Where |
| --- | --- | --- | --- |
| Global dashboard | IMPLEMENTED | IMPLEMENTED | `/global`, `api.global_overview` |
| Workspaces directory | IMPLEMENTED | IMPLEMENTED | `/workspaces`, `api.workspace_list` |
| Workspace dashboard | IMPLEMENTED | IMPLEMENTED | `/`, `api.dashboard` — Slack panel added |
| Campaigns | IMPLEMENTED | IMPLEMENTED | `/campaigns`, `/campaigns/<id>` |
| Campaign builder | IMPLEMENTED | IMPLEMENTED | `/campaigns/new`, staged with per-stage validation |
| Campaign lifecycle | IMPLEMENTED | IMPLEMENTED | `src/campaigns.py`; canonical states, server-side transitions |
| Companies | IMPLEMENTED | IMPLEMENTED | `/companies`, `/companies/<id>` |
| Company dossier | IMPLEMENTED | IMPLEMENTED | `api.company_dossier`, progressive disclosure |
| Contacts | IMPLEMENTED | IMPLEMENTED | `/contacts`, `/contacts/<id>/<key>` |
| Contact dossier | IMPLEMENTED | IMPLEMENTED | `api.contact_view` |
| Segments | IMPLEMENTED | IMPLEMENTED | `/segments`, `api.segment_tree` |
| ICP explainability | IMPLEMENTED | IMPLEMENTED | `/icp`, criteria and evidence per verdict |
| Senders | IMPLEMENTED | IMPLEMENTED | `/senders`, five tabs |
| Sender pools | IMPLEMENTED | IMPLEMENTED | `api.sender_strategy` |
| Sender pairings | IMPLEMENTED | IMPLEMENTED | pairings tab |
| Sticky assignment | IMPLEMENTED | IMPLEMENTED | `src/assignment.py`; reason and history shown |
| Capacity planning | IMPLEMENTED | IMPLEMENTED | capacity tab; unknown limits stay unknown |
| Cadence | IMPLEMENTED | IMPLEMENTED | `/outreach`, per-step channel and sender |
| Outreach preview | IMPLEMENTED | IMPLEMENTED | `api.full_outreach`; states not collapsed |
| Cross-channel safety UI | IMPLEMENTED | IMPLEMENTED | `.xchan` allowed/refused with the reason |
| Approvals | IMPLEMENTED | IMPLEMENTED | `/approvals`; fingerprint and staleness visible |
| Replies | IMPLEMENTED | IMPLEMENTED | `/replies` |
| Notifications | IMPLEMENTED | IMPLEMENTED | `/notifications`, filters, history |
| Slack global settings | IMPLEMENTED | IMPLEMENTED | `/admin/slack` |
| Slack workspace settings | IMPLEMENTED | IMPLEMENTED | `/settings` policy keys |
| Advanced reporting | IMPLEMENTED | IMPLEMENTED | `/reporting`, 21 dimensions, denominators everywhere |
| Campaign comparison | IMPLEMENTED | IMPLEMENTED | `/compare`; small samples labelled |
| Sender analytics | IMPLEMENTED | IMPLEMENTED | `/reporting/senders` |
| **Client reports** | **MISSING** | **IMPLEMENTED** | `/reporting/client`, `src/clientreport.py` |
| **PDF generation** | **MISSING** | **IMPLEMENTED** | `src/pdf.py`, zero dependencies |
| **Report history** | **MISSING** | **IMPLEMENTED** | `src/reports.py`, audited |
| **Report section control** | **MISSING** | **IMPLEMENTED** | per template, with workspace defaults |
| Exports (CSV/JSON) | IMPLEMENTED | IMPLEMENTED | injection-guarded, permission-gated |
| Jobs | IMPLEMENTED | IMPLEMENTED | `/jobs`; resumable |
| Audit | IMPLEMENTED | IMPLEMENTED | `/audit`, scope widened only for super admin |
| Users | IMPLEMENTED | IMPLEMENTED | `/users`; escalation guarded |
| Roles | IMPLEMENTED | IMPLEMENTED | matrix read from `workspaces.py`, never retyped |
| Providers | PARTIAL | IMPLEMENTED | was a block inside `/admin`; now `/admin/health` |
| Admin console | IMPLEMENTED | IMPLEMENTED | `/admin` |
| **System health** | **BACKEND ONLY** | **IMPLEMENTED** | `/admin/health` |
| **Onboarding** | **MISSING** | **IMPLEMENTED** | `/onboarding` |
| **Config validation** | **MISSING** | **IMPLEMENTED** | `src/config.py`, fails closed in production |
| **Suppression** | **BACKEND ONLY** | **IMPLEMENTED** | `/suppression`, workspace-scoped, four reasons kept apart |
| **Global search** | **MISSING** | **IMPLEMENTED** | `/search`, bounded three ways |
| Demo mode | IMPLEMENTED | IMPLEMENTED | three workspaces, eight Slack scenarios |
| Diagnostics | IMPLEMENTED | IMPLEMENTED | `/diagnostics` |
| Timezones | IMPLEMENTED | IMPLEMENTED | `/timezones`; unknown stays unknown |
| Simulator | IMPLEMENTED | IMPLEMENTED | `/simulator`, 5,000 domains offline |

---

## What the account intelligence mission added

| Area | Before | After | Where |
| --- | --- | --- | --- |
| Signal model | MISSING | IMPLEMENTED | `src/signals.py`, 3 scopes, 28 types, evidence mandatory |
| Freshness and decay | MISSING | IMPLEMENTED | per-type half-life; removal requests never decay |
| Explainable priority | MISSING | IMPLEMENTED | `src/priority.py`, 5 components, each with its evidence |
| Signals dashboard | MISSING | IMPLEMENTED | `/signals`, tier filters, eligibility on every row |
| Why-this-account panel | MISSING | IMPLEMENTED | account screen; score, why-now, working shown |
| Manual signal entry | MISSING | IMPLEMENTED | `signals.record` permission, operator and above |
| Campaign context pack | MISSING | IMPLEMENTED | `src/contextpack.py`, on `/campaigns/<id>` |
| GTM decision memory | MISSING | IMPLEMENTED | `src/gtm.py`, `/strategy`; records intent, enforces nothing |
| Reason beside each setting | MISSING | IMPLEMENTED | settings screen; unexplained overrides listed |
| Delta discovery | MISSING | IMPLEMENTED | `src/discovery.py`; known companies never proposed as new |
| Client review roundtrip | MISSING | IMPLEMENTED | `src/clientreview.py`; canonical columns compared on return |
| Cohort performance learning | MISSING | IMPLEMENTED | `src/learning.py`, `/reporting/cohorts`; recommends, never acts |
| Live discovery provider | MISSING | **MISSING** | LIVE DISCOVERY PROVIDER REQUIRED |
| CRM connector for delta | MISSING | **MISSING** | LIVE CRM CONNECTOR REQUIRED |
| Credential sweep covers every screen | PARTIAL | **FIXED** | was 25 of 42 paths; now derived from NAV |
| Sidebar progressive disclosure | MISSING | IMPLEMENTED | 7 sections, one open; 40 links -> 9 on screen |
| Import discoverable | **UNREACHABLE** | **FIXED** | had no nav entry and no link anywhere |
| Dashboard quick actions | MISSING | IMPLEMENTED | role-filtered; import is primary |
| Company/contact separation at import | BROKEN | **FIXED** | `upload.py`; one domain, many people |
| Contacts written on commit | MISSING | IMPLEMENTED | `identity.assign_keys` on the record |
| Playbook library | MISSING | IMPLEMENTED | `src/playbooks.py`, 6 playbooks, recommends and never assigns |
| Playbook on the account screen | MISSING | IMPLEMENTED | conditions met, missed and never-asked all shown |
| Playbook in message generation | MISSING | **MISSING** | the recommendation reaches no prompt yet |
| Signal reporting dimensions | MISSING | IMPLEMENTED | `priority_tier`, `live_signal` (operator), `outreach_state` (client) |
| Decision review cadence | MISSING | **MISSING** | nothing asks whether an old judgement is still believed |
| Decisions scored against outcomes | MISSING | **MISSING** | needs reporting sliced by a decision's date range |
| External signal sources | MISSING | **MISSING** | deliberate; every account signal here is manual |
| Signal retraction | MISSING | **MISSING** | append-only, no withdraw path — see PRODUCT-GAPS.md |
| Score history | MISSING | **MISSING** | answers "now", cannot answer "why was it 92 in October" |

### What the pack is for

`/campaigns/<id>` says whether a campaign is in order. The outreach preview
says what would arrive. Neither says whether it should go out at all, and
the four answers that settle it - the segment, the priority, the angle the
evidence supports, and what a message may claim - live in four modules.

The pack assembles them and asserts nothing of its own. What it adds is
three refusals to blur: a supported angle is never merged with a plausible
one, a priority is never reported without the count of accounts that
cannot be worked, and the quoted evidence is never presented as something
a message may repeat.

---

## What the overnight observability and revival mission added

| Area | Before | After | Where |
| --- | --- | --- | --- |
| Operational health | MISSING | IMPLEMENTED | `/health`; failures already in canonical state, read together, with whether a retry is safe |
| Slack interactions endpoint | **MISSING** | IMPLEMENTED | `/slack/interactions`; `src/interactions.py` had no HTTP terminator, so every Approve button posted to a URL that did not exist |
| Evidence re-ageing | **MISSING** | IMPLEMENTED | `evidence.recheck`; freshness was frozen on the day a fact was found and every reader trusted it |
| Aged-out draft hold | MISSING | IMPLEMENTED | `eligibility.HELD_EVIDENCE_AGED_OUT`; approval is a fingerprint of the text, so it could not catch this |
| Weekly refresh selection | MISSING | IMPLEMENTED | `src/refresh.py`, `/refresh`; plans, never spends |
| Revival | MISSING | IMPLEMENTED | `src/revival.py`, `/revival`; a timer means re-evaluate, not send |
| Observation licensing | MISSING | IMPLEMENTED | `src/observations.py`; what may be said about them, and the four things that stay unspoken |
| Live readiness classification | MISSING | IMPLEMENTED | `LIVE-READINESS.md`; one strict class per capability |
| Scheduler | MISSING | PARTIAL | One supervised thread runs reply reconciliation and the daily digest, each switched separately and each off by default. Neither discovery nor refresh runs on a timer, and both still say so |
| Message-time context rebuild | PARTIAL | PARTIAL | Freshness is re-derived at payload time; cross-channel history is still not carried in `contextpack` |

## What Mission 4.1 added

| Area | Before | After | Where |
| --- | --- | --- | --- |
| Account touch graph | MISSING | IMPLEMENTED | `src/account.py` |
| Outreach claim resolver | MISSING | IMPLEMENTED | `src/outreachclaims.py`, 7 claim types |
| Contact and account fatigue | MISSING | IMPLEMENTED | `src/fatigue.py` |
| Branching cadence | MISSING | IMPLEMENTED | `src/cadencegraph.py`, 14 node types |
| Sender teams | MISSING | IMPLEMENTED | `src/senderteam.py` |
| Referral graph | MISSING | IMPLEMENTED | `events.REFERRAL_RECORDED` |
| Account outreach view | MISSING | IMPLEMENTED | `/outreach/account/<id>` |
| Account list | MISSING | IMPLEMENTED | `/outreach/accounts` |
| Cadence graph view | MISSING | IMPLEMENTED | `/outreach/cadence` |
| Report drafts and versions | MISSING | IMPLEMENTED | `src/reportdraft.py` |
| Report editor | MISSING | IMPLEMENTED | `/reporting/editor` |
| Monthly master report | MISSING | IMPLEMENTED | 20 sections |
| Contact outreach view rebuild | PARTIAL | **PARTIAL** | account view came first |
| Cadence graph in the builder | MISSING | **MISSING** | previewed and validated, not yet stored on a campaign |
| Fatigue in campaign QA | MISSING | **PARTIAL** | advisory, shown on the account screen; QA does not call it |

### The reporting engine

One engine, four templates, no per-client code:

    REPORT TEMPLATE + WORKSPACE DATA + REPORT DRAFT = CLIENT REPORT

`src/report.py` counts. `src/clientreport.py` lays out. `src/reportdraft.py`
holds the words. `src/pdf.py` writes the file.

A draft has narrative fields and **no metric fields**, so a manual edit cannot
change a number - not by convention, but because there is nowhere to put one.
Editing appends a version; a stored version is never rewritten.

## What earlier missions added

- Client reports, three templates, with the template as the permission
  boundary rather than a dropdown
- A PDF writer, hand-rolled to keep the zero-dependency property
- Report history and section control, workspace-scoped and audited
- Workspace onboarding checklist, answered from stored state
- System health and provider console, which never says "healthy" about
  something nothing has called
- Configuration validation that fails closed in production and stays silent
  in demo
- `DESIGN-SYSTEM.md`, and the controls the design system was missing
- Cross-tenant penetration tests with real forged identifiers
- Workspace-scoped suppression, keeping "paused because they replied" and
  "asked us to stop" as different facts
- Bounded global search across the workspaces a person is a member of
- `LIVE-VALIDATION-PLAN.md`, `DEPLOYMENT-PLAN.md`, `GO-LIVE-CHECKLIST.md`
- `PRODUCTION-READINESS.md` rewritten — it still claimed there was no web UI

---

## What remains, and why

### Worker, scheduler, reply poller — NOT READY

Not product gaps but infrastructure ones, and named in
`PRODUCTION-READINESS.md`. `/admin/health` reports all three as
live-validation-required rather than pretending they are running.

### Meeting tracking — MISSING, deliberately

Nothing observes a calendar. Every surface reports meetings as "not tracked"
with the reason. This is the one metric where a plausible-looking number would
do the most damage, so the product refuses to infer it from a positive reply's
wording.

---

## Rules this inventory enforces

**No orphaned backend.** An area with a real capability and no screen is
listed BACKEND ONLY and is a gap, not a subtlety. After this mission one row
is in that state: person-level research, whose absence is itself the honest
answer - `person_research.available` is false for every record, and nothing
is inferred from that.

**No decorative UI.** Nothing in the product is UI ONLY. Every control either
works or says why it is unavailable - a disabled Generate button on the client
reports screen carries the sentence "this role may read reports but not
generate them".

**No fake data outside demo.** Demo mode is obvious: a banner, a dot in the
header, and "DEMONSTRATION DATA" on the PDF cover. Outside it, empty means
empty and unknown means unknown.
