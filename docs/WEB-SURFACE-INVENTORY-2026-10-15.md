# THE WEB SURFACE, ENUMERATED — 2026-10-15

**TASK 0010, lane `webapp`.** Every HTTP route in `src/web/`, one row each,
read from the code.

    measured on   b1f290c847eb2500b7eb39987ac34f6d6a8d00d2   (= origin/master)
    worktree      Desktop\resonate-trees\wt-webapp-2026-10-15   branch task-webapp-2026-10-15
    line endings  LF — this is the only lane tree that is not CRLF
                  (_STANDING-RULES, 2026-10-15 21:10). Nothing in this document
                  is a suite name-set, so the difference does not apply to any
                  number below, but it is named because the rule says to.

**What this task did.** Read code. **No server was started and no listener was
opened** — zero listeners on 8765-8799 was the state glm-c measured at 19:16:47
and again at 19:54:42, and this task did not change it or re-measure it, because
nothing here depends on the answer. No file under `src/` was changed. No
provider, Apify, Slack or network call. No production `work/` read. The suite
lock was neither taken nor released and no suite was run — nothing under `src/`
or `tests/` changed.

**Method, copied from the three lane entries the brief names** —
`glm-c/0130`, `glm-b/0080`, `glm-c/0140`. Each of those took one documented
sentence, traced the real execution path hop by hop, asked whether the named
guard is on that path, and dated the falsehood by pickaxe. This document does
the same thing breadth-first: every route, and then the three derived lists.
Those three entries are also three of the rows below, and their verdicts are
cited rather than re-derived, except where this task re-read the code itself.

---

## 0. HOW THIS SURFACE IS ROUTED, AND WHY THE TABLE HAS TWO PERMISSION COLUMNS

`src/web/app.py` is a hand-rolled `BaseHTTPRequestHandler`. There is no router
and no decorator: `_route` (`app.py:483`) parses the path, then `_dispatch`
(`app.py:570`) walks a chain of `if path ==` / `if path.startswith` branches in
source order. Three consequences shape every row below.

**1. Reads are gated by a table; writes are not.** `READ_PERMISSIONS`
(`app.py:154-222`) maps a path prefix to one permission, and `_get` applies it
once at `app.py:705-710` — *before* the handler, which is the point:
"a refusal here cannot be skipped by a handler that forgot to ask". **`_post`
has no equivalent.** Every POST route carries its own
`security.require(...)` call, or delegates the check to the service layer. Two
POST routes take the second option: `/strategy` and `/signals`. Neither is a
hole — `api.record_decision` requires `workspace.manage` at `api.py:6694` and
`api.record_signal` requires `signals.record` at `api.py:7007` — but the
asymmetry is real and it is the shape the table's own comment warns about:
the handler that forgets is the failure mode, and on the POST side there is
nothing above the handler to catch it.

**2. `permission_for` was computed for every GET path, not inferred.** Run on
`b1f290c84`, every one of the 60 GET paths resolves to a permission except two:
`/workspaces` and `/select-workspace`. Both are handled at `app.py:674-686`,
*above* the permission check, and both are gated instead by
`repo_module.Repo.for_user(email, slug)` — membership, which is the stronger
check for what they do (picking which workspace a session points at). Nothing
else falls through.

**3. The two permission columns are different questions.** `glm-c/0140` found a
case where route and handler agree on the permission and *differ in
consequence*: `/campaigns/resume` gates `campaign.pause` at the route, re-checks
`campaign.pause` at `api.py:3212`, and then hands the orchestrator
`role=roles.ADMIN` hardcoded — so the one layer positioned to refuse a reviewer
is fed the one role it cannot refuse. The table therefore carries **route
permission**, **handler re-require**, and **role passed onward** as three
separate columns, because in this codebase they are three separate facts.

**Legend for the PROVIDER column — the column that matters.**

| code | meaning |
|---|---|
| `—` | cannot reach any provider or any network, on any branch |
| **`WRITE`** | **a provider write is reachable from this route.** Chain given in §2 |
| `NET-idp` | makes an outbound HTTPS call, to the OIDC identity provider only |
| `plan` | writes a local notification row. Nothing in `src/web/` delivers one |

Nothing in the `plan` class posts. `notify.notify` → `notify.plan` stores a row
and returns; `notify.deliver` — the only function that calls `slack.post` — has
exactly two callers in the repository, `digestwatch.py:250` (the background
digest thread `main()` starts) and `notify.retry`. **No route reaches either.**
`orchestrator.deliver` (`orchestrator.py:761`) likewise has two callers,
`positive_reply_notification` and `operational_alerts`, and no route reaches
those. A Slack post from a click is not possible on this build.

Writes are named by their canonical file. `work/` paths are
`store`-resolved and the names are from the modules, not guessed:
`queue.jsonl` (`store.py:37`), `campaigns.jsonl` (`store.py:68`),
`audit.jsonl` (`workspaces.py:972`), `workspaces.jsonl` (`workspaces.py:175`),
`jobs.jsonl` (`jobs.py:112`), `notifications.jsonl` (`notify.py:302`),
`report-drafts.jsonl` (`reportdraft.py:103`), `reports.jsonl`
(`reports.py:46`), `gtm.jsonl` (`gtm.py:173`), `signals.jsonl`
(`signals.py:454`), `senders.jsonl` (`senderidentity.py:124`),
`provider-writes.jsonl` (`providerwrites.py:2266-2272`).

---

## 1. THE INVENTORY

### 1a. Before a session exists

These five are above the session gate at `app.py:657-658`. The Slack route is
above it deliberately and is three lines from the routing table so an auditor
can see it.

| METHOD PATH | handler | route permission | handler re-require | role passed | reads → writes | provider | renders | safety claim |
|---|---|---|---|---|---|---|---|---|
| `GET /assets/app.css` | `app.py:572` | none | none | — | `assets.CSS` in memory → nothing | `—` | CSS | — |
| `GET /assets/app.js` | `app.py:575` | none | none | — | `assets.JS` in memory → nothing | `—` | JS | — |
| `GET /healthz` | `app.py:579` | none | none | — | session count → nothing | `—` | JSON | **`"live_sending": False`** — a hardcoded literal in the JSON body (`app.py:581`). See §3.1 |
| `POST /slack/interactions` | `app.py:604` → `_slack_interaction` `app.py:339` | **none — HMAC instead of session, and no CSRF** | `slack.verify` over the raw bytes, then `orchestrator.decide`'s own three authorisation doors | **none passed** — `decide` is called with no `role`, so it derives one from the *client config* via `roles.role_of` + `slack.may_approve` | `campaigns.jsonl` (unscoped `campaigns.load`), client config → `campaigns.jsonl`, record/campaign events | `—` | `text/plain`, one sentence | — |
| `GET/POST /login` | `app.py:619`, `_login` `app.py:1752` | none | `security.sign_in_mode()` decides which branch answers; OIDC mode 405s a POST | — | `workspaces.jsonl` → session, `audit.jsonl` on a proved sign-in | `—` | login page | **"Live sending is disabled in this build"** (`pages.py:466`). See §3.6 |
| `GET /auth/start` | `_auth_start` `app.py:1771` | none | 404 unless `AUTH_PROVIDER=oidc` | — | OIDC discovery document → in-memory `PendingSignIns` | **`NET-idp`** — `oidc.discover` → `urllib.request.urlopen` (`oidc.py:367`) | 303 to the provider | — |
| `GET /auth/callback` | `_auth_callback` `app.py:1788` | none | 404 unless OIDC; state claimed-and-consumed *first* | — | provider token endpoint, `workspaces.jsonl` → session, `audit.jsonl`, pending invitations consumed | **`NET-idp`** — `oidc.discover` + `oidc.exchange` | 303, or a one-sentence error page | — |
| `GET /logout` | `app.py:649` | none | none | — | — → session destroyed | `—` | 303 | — |

On `/slack/interactions`: this is the only route in the application that skips
both the session and CSRF, and it is the only route that reaches
`campaigns.load()` **unscoped by workspace**. It is not a hole — the HMAC over
the exact bytes is a stronger check than a cookie, `handle` verifies before it
parses one field, and a payload's `client` must match the campaign's — but it
means the Slack signing secret is a cross-tenant approval authority. Stated so
nobody has to rediscover it.

### 1b. A session, before a workspace

Handled at `app.py:674-705`, above the `READ_PERMISSIONS` check.

| METHOD PATH | handler | route permission | handler re-require | role passed | reads → writes | provider | renders | safety claim |
|---|---|---|---|---|---|---|---|---|
| `GET /select-workspace` | `app.py:674` | **none in the table** | `Repo.for_user(email, ?to)` — membership | — | `workspaces.jsonl` → **the session's workspace pointer** | `—` | 303 to `/` | — |
| `POST /select-workspace` | `app.py:1191` | none | `Repo.for_user(email, workspace)` | — | as above | `—` | 303 | — |
| `GET /workspaces` | `app.py:683` | **none in the table** | `api.workspace_list(email)` scopes by `workspaces_for` | — | `workspaces.jsonl`, per-workspace cards → nothing | `—` | workspace list | — |
| `GET /admin` | `app.py:688` | `_require_super_admin`, **404 not 403** | `api.admin_overview()` — the one genuinely unscoped function in `api.py`, by its own docstring | — | every record, every campaign, every job, every notification, the waterfall ledger → nothing | `—` | admin console | **"No provider call has been made. This build does not make one from any surface"** (`pages.py:4881`); **"this build makes no provider call"** (`api.py:4265`, rendered); `live_sending: False` and `campaign.launch: False` rows from `api.feature_flags()`. See §3.1 and §4.3 |
| `GET /admin/health` | `app.py:692` | `_require_super_admin` | none | — | env-var *presence* only, state-store sizes → nothing | `—` | system health | **`provider_states()` labels every provider `NOT_CALLED`**, docstring "Nothing in this build calls a provider" (`api.py:5443`). See §3.1 |
| `GET /admin/slack` | `app.py:696` | `_require_super_admin` | none | — | every workspace's Slack routing → nothing | `—` | Slack ops | — |

`GET /select-workspace` is a GET with a side effect: it writes the session's
workspace pointer, with no CSRF token. The effect is confined to the caller's
own session and the membership check is the same one the POST does, so this is
noted rather than filed as a defect.

### 1c. GET — reads

Route permission is from `READ_PERMISSIONS` and was **computed**, not read off
the table by eye. Where the handler column is blank, the service function
asks for no permission of its own and relies on the route table plus `Repo`
scoping — which is the designed shape (`workspaces.py` docstring: "a permission
is checked at the service boundary, never in a page"), and is why the route
table's completeness was measured rather than assumed.

| METHOD PATH | handler | route permission | handler re-require | reads → writes | provider | renders |
|---|---|---|---|---|---|---|
| `GET /` | `app.py:713` | `workspace.view` | — | `queue.jsonl`, `campaigns.jsonl`, `jobs.jsonl`, Slack routing → nothing | `—` | dashboard; a VIEWER gets the `simple` cut |
| `GET /batches` | `app.py:723` | `operations.view` | — | `queue.jsonl` → nothing | `—` | batch list |
| `GET /batches/<b>` | `app.py:726` | `operations.view` | — | `queue.jsonl`, preflight → nothing | `—` | batch detail |
| `GET /upload` | `app.py:732` | `batch.create` | — | — → nothing | `—` | upload form |
| `GET /companies` | `app.py:736` | `contacts.view` | — | `queue.jsonl` → nothing | `—` | paginated company list |
| `GET /companies/<id>` | `app.py:749` | `contacts.view` | — | `queue.jsonl` → nothing | `—` | dossier, or 404 |
| `GET /icp` | `app.py:757` | `contacts.view` | — | `queue.jsonl`, qualification → nothing | `—` | ICP queue |
| `GET /segments` | `app.py:765` | `contacts.view` | `contacts.view` ×3 (`api.py:995`, `1087`, `1188`) | `queue.jsonl` → nothing | `—` | segment explorer |
| `GET /contacts` | `app.py:771` | `contacts.view` | — | `queue.jsonl` → nothing | `—` | paginated contact list |
| `GET /contacts/<id>/<k>` | `app.py:780` | `contacts.view` | — | `queue.jsonl`, `campaigns.jsonl` → nothing | `—` | contact detail, or 404 |
| `GET /global` | `app.py:793` | `workspace.view` | — | one scoped `Repo` **per workspace the caller is a member of** → nothing | `—` | agency overview |
| `GET /global/reporting` | `app.py:798` | `reporting.view` | — | as above → nothing | `—` | cross-workspace comparison |
| `GET /reporting/senders` | `app.py:805` | `reporting.view` | — | `queue.jsonl`, `senders.jsonl` → nothing | `—` | sender report |
| `GET /senders` | `app.py:812` | `operations.view` | — | `senders.jsonl`, assignments → nothing | `—` | sender roster |
| `GET /jobs` | `app.py:820` | `operations.view` | — | `jobs.jsonl` → nothing | `—` | job list + the `RUNNABLE`/`UNRUNNABLE` tables |
| `GET /outreach` | `app.py:825` | `operations.view` | — | `queue.jsonl`, `campaigns.jsonl`, cadence → nothing | `—` | full outreach preview |
| `GET /campaigns/new` | `app.py:830` | `campaign.create` | — | `queue.jsonl`, `campaigns.jsonl`, suppression file → nothing | `—` | campaign builder. **"Creates a draft. Nothing is sent, no provider…"** (`pages.py:2770`) — true of `/campaigns/create` |
| `GET /campaigns` | `app.py:837` | `operations.view` | — | `campaigns.jsonl` → nothing | `—` | campaign list, with Pause/Resume buttons if the caller holds `campaign.pause` |
| `GET /campaigns/experiments` | `app.py:897` | `operations.view` | — | `queue.jsonl`, `campaigns.jsonl`, variants → nothing | `—` | copy experiments |
| `GET /campaigns/<id>` | `app.py:903` | `operations.view` | — | `campaigns.jsonl`, `queue.jsonl`, `push.payloads` → nothing | `—` | campaign detail + **provider request bodies as a preview**. `api.py:2878` "The exact request bodies the sender would post. Nothing is sent." — true: `push.payloads` builds, it does not post |
| `GET /discovery/review.csv` | `app.py:846` | `operations.view` | **`contacts.export`** (`api.py:6856`) | `queue.jsonl` → nothing | `—` | CSV attachment |
| `GET /tasks` | `app.py:852` | `operations.view` | `operations.view` (`api.py:1461`) | `queue.jsonl`, `jobs.jsonl`, `campaigns.jsonl` → nothing | `—` | work queue |
| `GET /revival` | `app.py:856` | `operations.view` | `operations.view` (`api.py:1332`) | `queue.jsonl` → nothing | `—` | revival view |
| `GET /replies/returns` | `app.py:860` | `operations.view` | `operations.view` (`api.py:1482`) | `queue.jsonl` → nothing | `—` | OOO returns |
| `GET /refresh` | `app.py:864` | `operations.view` | `operations.view` (`api.py:1317`) | `queue.jsonl` → nothing | `—` | refresh plan |
| `GET /health` | `app.py:868` | `operations.view` | `operations.view` (`api.py:1528`) | `jobs.jsonl`, `notifications.jsonl`, `tag-outbox.jsonl`, replywatch + digestwatch problems → nothing | `—` | operational health |
| `GET /audience` | `app.py:872` | `contacts.view` | `contacts.view` (`api.py:6894`) | `queue.jsonl` → nothing | `—` | audience overview |
| `GET /discovery` | `app.py:877` | `operations.view` | `operations.view` (`api.py:6813`) | `queue.jsonl`, discovery state → nothing | `—` | discovery view |
| `GET /reporting/cohorts` | `app.py:880` | `operations.view` | `operations.view` (`api.py:6781`) | `queue.jsonl` → nothing | `—` | cohort performance |
| `GET /strategy` | `app.py:887` | `operations.view` | `operations.view` (`api.py:6657`) | `gtm.jsonl`, `queue.jsonl` → nothing | `—` | strategy centre + the decision form |
| `GET /signals` | `app.py:892` | `contacts.view` | — | `signals.jsonl`, `queue.jsonl` → nothing | `—` | account intelligence |
| `GET /approvals/plan` | `app.py:913` | `approvals.review` | — | `campaigns.jsonl`, `queue.jsonl`, QA → nothing | `—` | plan review |
| `GET /approvals` | `app.py:919` | `approvals.review` | — | `campaigns.jsonl` → nothing | `—` | approval queue |
| `GET /replies` | `app.py:924` | `replies.view` | — | `queue.jsonl`, Slack previews → nothing | `—` | inbox |
| `GET /replies/policy` | `app.py:994` | `operations.view` | — | client config → nothing | `—` | reply policy |
| `GET /replies/context/<id>/<k>` | `app.py:997` | `replies.view` | — | `queue.jsonl` → nothing | `—` | one reply in context, or 404 |
| `GET /reporting` | `app.py:933` | `reporting.view` | — | `queue.jsonl`, waterfall ledgers → nothing | `—` | analytics. **"Nothing has been sent from this system, so there are no open rates, no bounce rates…"** on the client-facing cut (`pages.py:3653`). See §3.6 |
| `GET /search` | `app.py:946` | `workspace.view` | — | one scoped `Repo` per membership → nothing | `—` | search hits |
| `GET /suppression` | `app.py:951` | `contacts.view` | — | `queue.jsonl`, suppression file, `agency-dnc.jsonl` → nothing | `—` | suppression view |
| `GET /outreach/accounts` | `app.py:954` | `operations.view` | — | `queue.jsonl` → nothing | `—` | account list |
| `GET /outreach/cadence` | `app.py:959` | `operations.view` | — | `queue.jsonl`, `campaigns.jsonl`, cadence graph → nothing | `—` | cadence view |
| `GET /outreach/contact/<id>/<k>` | `app.py:965` | `operations.view` | — | `queue.jsonl`, `campaigns.jsonl` → nothing | `—` | contact outreach, or 404 |
| `GET /outreach/account/<id>` | `app.py:978` | `operations.view` | — | `queue.jsonl`, `signals.jsonl` → nothing | `—` | account view + the signal form |
| `GET /onboarding` | `app.py:991` | `workspace.view` | — | `queue.jsonl`, `senders.jsonl`, client config → nothing | `—` | setup checklist |
| `GET /reporting/editor` | `app.py:1007` | `reporting.view` | — | `report-drafts.jsonl`, `queue.jsonl` → nothing | `—` | report editor. **Carries a "Preview" link to `/reporting/editor/preview`, which is not a route** — see §5.1 |
| `GET /reporting/editor/export` | `app.py:1016` | `reporting.view` | **`reporting.export`** (`api.py:6060`) | `report-drafts.jsonl`, `queue.jsonl` → **`reports.jsonl` + `audit.jsonl`** | `—` | PDF attachment. **A GET that writes history** — and says so: "this writes history and audits it, so it is an export, not a read" |
| `GET /reporting/client` | `app.py:1034` | `reporting.view` | — | `reports.jsonl` → nothing | `—` | client reports |
| `GET /reporting/client/download` | `app.py:1039` | `reporting.view` | — | `reports.jsonl`, `queue.jsonl` → **`audit.jsonl`** (`report.downloaded`, or `report.failed`) | `—` | PDF, **re-rendered not stored**; 404 for another workspace's id |
| `GET /compare` | `app.py:1067` | `reporting.view` | — | `queue.jsonl` → nothing | `—` | comparison |
| `GET /settings/personas` | `app.py:1074` | `workspace.manage` | — | client config → nothing | `—` | personas |
| `GET /settings` | `app.py:1080` | `operations.view` | — | client config, `campaigns.jsonl` → nothing | `—` | settings, incl. the provider-mapping form if the caller holds `provider_settings.view` |
| `GET /users` | `app.py:1087` | `users.manage` | — | `workspaces.jsonl` → nothing | `—` | members |
| `GET /audit` | `app.py:1094` | `operations.view` | — | `audit.jsonl`, scoped to the workspace unless `?scope=all` **and** super admin → nothing | `—` | audit log. **Renders `provider_stopped: … → False` for a pause that did stop the provider** — `pages._audit_change` `pages.py:4686-4699`. See §3.3 |
| `GET /notifications` | `app.py:1109` | `operations.view` | — | `notifications.jsonl`, same `?scope=all` shape → nothing | `—` | notification history |
| `GET /export/contacts.csv` | `app.py:1131` | `contacts.export` | — | `queue.jsonl` → **`audit.jsonl` + 2 rows in `notifications.jsonl`** | `plan` | CSV attachment. **A GET that writes, and the audit row is written *before* the export runs** |
| `GET /export/analytics.csv` | `app.py:1140` | `reporting.export` | — | `queue.jsonl` → **`audit.jsonl` + 2 `notifications.jsonl`** | `plan` | CSV attachment |
| `GET /export/analytics.json` | `app.py:1155` | `reporting.export` | — | as above | `plan` | JSON |
| `GET /simulator` | `app.py:1168` | `operations.view` | — | nothing stored → nothing | `—` | simulator. **"Offline. No provider, model or network is touched"** (`pages.py:3691`) — **true**: `scalesim` over a synthetic set |
| `GET /timezones` | `app.py:1178` | `operations.view` | — | `queue.jsonl` → nothing | `—` | timezone preview |
| `GET /diagnostics` | `app.py:1181` | `operations.view` | — | env presence, `jobs.jsonl`, state sizes → nothing | `—` | diagnostics. **`row("Live sending", tag("DISABLED", "pass"))` and `row("EmailBison", tag("preview only", "pass"))` are hardcoded literals** (`pages.py:3840-3842`). See §3.1 |

### 1d. POST — writes

| METHOD PATH | handler | route permission | handler re-require | role passed | reads → writes | provider | renders |
|---|---|---|---|---|---|---|---|
| `POST /strategy` | `app.py:1201` | **none at the route** | `workspace.manage` (`api.py:6694`) | — | `gtm.jsonl` → `gtm.jsonl`, `audit.jsonl` | `—` | 303, or the form with an error |
| `POST /signals` | `app.py:1218` | **none at the route** | `signals.record` (`api.py:7007`) | — | `queue.jsonl` → `signals.jsonl`, `audit.jsonl` | `—` | 303, or 400/404 |
| `POST /upload` | `app.py:1254` | `batch.create` (explicit — and the comment says why: without it the handler was an oracle) | — | — | the CSV, `queue.jsonl`, hygiene index, agency DNC, client policy → **in-memory preview only** | `—` | preview, or 400 |
| `POST /upload/commit` | `app.py:1290` | `batch.create` | — | — | the stashed preview → **`queue.jsonl`**, `audit.jsonl` | `—` | 303 to the batch |
| `POST /workspaces/create` | `app.py:1307` | `_require_super_admin` | — | — | → `workspaces.jsonl`, a client config file, `audit.jsonl` | `—` | 303 |
| `POST /users/add` | `app.py:1326` | `users.manage` | — | — | `workspaces.jsonl` → `workspaces.jsonl`, `audit.jsonl`. Refuses `super_admin` by name | `—` | 303 |
| `POST /users/revoke` | `app.py:1348` | `users.manage` | — | — | → `workspaces.jsonl`, `audit.jsonl` | `—` | 303 |
| `POST /users/role` | `app.py:1358` | `users.manage` | — | — | → `workspaces.jsonl`, `audit.jsonl`. Refuses `super_admin` | `—` | 303, or 400 |
| **`POST /campaigns/pause`** | `app.py:1374` → `_campaign_run_state` `app.py:1624` | `campaign.pause` | `campaign.pause` (`api.py:3171`) | **`roles.ADMIN` hardcoded** (`api.py:3185`) — inert, because campaign-layer REVIEWER holds `PAUSE_CAMPAIGN` | `campaigns.jsonl`, `queue.jsonl` → `campaigns.jsonl`, `audit.jsonl`, **`provider-writes.jsonl`** | **`WRITE`** | 303, or 409/404 |
| **`POST /campaigns/resume`** | `app.py:1378` → `_campaign_run_state` `app.py:1624` | `campaign.pause` | `campaign.pause` (`api.py:3212`) | **`roles.ADMIN` hardcoded** (`api.py:3223`) — **NOT inert**: campaign-layer REVIEWER deliberately lacks `RESUME_CAMPAIGN` | as above | **`WRITE`** | 303, or 409/404 |
| `POST /replies/handle` | `app.py:1382` | `replies.manage` | `replies.manage` (`api.py:3242`) | — | `queue.jsonl` → `queue.jsonl`, `audit.jsonl` | `—` | 303, or 409/404 |
| `POST /senders/reassign` | `app.py:1398` | `workspace.manage` | `workspace.manage` (`api.py:621`) | — | `queue.jsonl`, `senders.jsonl` → `queue.jsonl`, `audit.jsonl` | `—` | 303, or 409/404. **No form anywhere posts to this** — see §5.2 |
| `POST /reporting/editor/new` | `app.py:1415` | `reporting.export` | — | — | `queue.jsonl` → `report-drafts.jsonl` | `—` | 303 |
| `POST /reporting/editor/save` | `app.py:1423` | `reporting.export` | — | — | → `report-drafts.jsonl` | `—` | 303, or 400/404 |
| `POST /reporting/editor/finalise` | `app.py:1452` | `reporting.export` | — | — | `report-drafts.jsonl` → `report-drafts.jsonl`, `audit.jsonl`. Toggles: a FINAL draft is reopened | `—` | 303, or 404 |
| `POST /reporting/client/generate` | `app.py:1469` | **`reporting.view`** — which a VIEWER holds | none in `api.generate_report` | — | `queue.jsonl`, client config → `reports.jsonl`, `audit.jsonl` | `—` | PDF, or the page with `status=500`. Template and sections resolved through an allowlist, not trusted |
| `POST /settings/policy` | `app.py:1490` | `workspace.manage` | `workspace.manage` (`api.py:3955`) | — | → **the workspace's policy overrides**, `audit.jsonl`. Refused **whole** on an un-overridable key, never half-applied | `—` | 303, or 400 |
| `POST /replies/referral/add` | `app.py:1504` | `batch.create` (not `replies.*` — the comment says this writes a person into an account) | `contacts.view` **and** `batch.create` (`api.py:6350-6351`) | — | `queue.jsonl` → `queue.jsonl`, `audit.jsonl` | `—` | 303, or 400/404 |
| `POST /settings/personas/save` | `app.py:1525` | `workspace.manage` | `workspace.manage` (`api.py:4020`) | — | → persona config, `audit.jsonl` | `—` | 303, or 400 |
| `POST /settings/personas/remove` | `app.py:1540` | `workspace.manage` | `workspace.manage` (`api.py:4039`) | — | → persona config, `audit.jsonl` | `—` | 303 |
| **`POST /settings/mapping`** | `app.py:1545` | `provider_settings.manage` | `provider_settings.manage` (`api.py:4064`) | **none** — and it does **not** go through `orchestrator.map_external`, so `roles.require(CHANGE_MAPPING)` never runs | `campaigns.jsonl` → **`campaigns.jsonl`: `bison_campaign_id` / `heyreach_campaign_id`**, `audit.jsonl` | `—` **directly, but see §2.3** | 303, or 404 |
| `POST /jobs/run` | `app.py:1556` | `batch.run` | `batch.run` (`api.py:766`) | — | `queue.jsonl`, `jobs.jsonl` → `queue.jsonl`, `jobs.jsonl`, `audit.jsonl` | `—` **and structurally so** | 303, or 400/404 |
| `POST /jobs/cancel` | `app.py:1572` | `batch.run` | `batch.run` (`api.py:836`) | — | `jobs.jsonl` → `jobs.jsonl`, `audit.jsonl` | `—` | 303, or 404 |
| `POST /campaigns/create` | `app.py:1583` | `campaign.create` | `campaign.create` (`api.py:2595`) | — | `queue.jsonl`, segments → **`campaigns.jsonl`**, `queue.jsonl` (cadence-arm assignment), `audit.jsonl` | `—` | 303 to the campaign, or 400 |
| `POST /icp/decide` | `app.py:1597` | `approvals.review` (not `contacts.view` — "this one can unlock spending") | `approvals.review` (`api.py:1841`) | — | `queue.jsonl` → `queue.jsonl`, `audit.jsonl` | `—` | 303, or 409/404 |
| `POST /approvals/campaign` | `app.py:1617` → `_approve_campaign` `app.py:1678` | `campaign.approve` | none at the repo layer | **`roles.REVIEWER`, deliberately the lowest engine role carrying approve/reject** — the comment names the alternative and refuses it | `campaigns.jsonl`, `queue.jsonl`, client config → `campaigns.jsonl`, `audit.jsonl`, `notifications.jsonl` | `plan` | 303, or 403/409/404. **"Local approval only. No provider is touched by this"** (`app.py:1679`) — **TRUE**, re-verified below |

**`/jobs/run` is structurally incapable of spending, and this was checked
rather than taken from the docstring.** Two gates in series at `api.py:766-777`:
`job_type in jobs.SPENDING_TYPES` (`= (ENRICH, VERIFY, RESEARCH, PERSONALIZE)`,
`jobs.py:79`) refuses, and then an **allowlist** — `RUNNABLE_JOBS` holds exactly
one entry, `ICP_CLASSIFY` (`api.py:684-688`), whose unit of work is
`qualify.company`. The allowlist is what makes `RENDER` safe, which matters,
because `RENDER` "generates copy, which is a paid LLM request" and is **not** in
`SPENDING_TYPES`. The first gate alone would have admitted it. Both exist; the
second is the one doing the work.

**`/approvals/campaign` passes `roles.REVIEWER`, and that is the one place on
this surface where the role handed onward is argued for rather than hardcoded
to ADMIN.** The comment at `app.py:1705-1713` says why: a workspace admin
approving a campaign needs `APPROVE_CAMPAIGN`, not `LAUNCH_CAMPAIGN`, and
handing `roles.ADMIN` here "would grant the launch permission this build exists
to withhold". The claim "No provider is touched by this" was re-traced for this
task: `orchestrator.request_approval` → `slack.campaign_approval_request`
(a payload *builder*) + `plan_notification` (stores a row) +
`notify.notify` (stores a row); `orchestrator.decide` → `roles.require`,
fingerprint compare, status change, events. **No provider call on any branch.**
The sentence is true. It is also, measured across this surface, the only
"no provider" sentence in `src/web/` that is.

---

## 2. DERIVED LIST 1 — ROUTES THAT CAN CAUSE A PROVIDER WRITE

**Two, by direct chain. A third is the enabler and is named because without it
the first two cannot reach anything.**

### 2.1 `POST /campaigns/pause` — reaches EmailBison and HeyReach

    POST /campaigns/pause                               app.py:1374
      security.require(session, CAMPAIGN_PAUSE)          app.py:1375
      _campaign_run_state(..., "pause")                  app.py:1631-1635
        api.pause_campaign                               api.py:3149
          repo.require(ws.CAMPAIGN_PAUSE)                api.py:3171
          orchestrator.pause(..., role=roles.ADMIN)      api.py:3184
            — NO `provider=` argument, so `provider=True` default applies
                                                         orchestrator.py:534-535
            roles.require(role, PAUSE_CAMPAIGN)          orchestrator.py:555
            _pause_at_provider                            orchestrator.py:565
              — skips a channel with no binding; needs
                `bison_campaign_id` / `heyreach_campaign_id`
              providerwrites.is_supported(EMAIL_PAUSE)   → True
              _perform_pause → providerwrites.perform    orchestrator.py:595-612
                require_supported                         providerwrites.py:2399
                require_conditional_permission            :2517   (no entry for a pause — no-op)
                require_resonate_os_campaign              :2528   ← the real gate
                transport(payload)                        :2572
                  bison.pause_campaign(provider_id)       orchestrator.py:604
                mandatory readback + _classify            :2585-2595

**Gates between the click and the vendor:** HTTP permission, repo permission,
engine role, verb allowlist, ownership default-refuse, mandatory read-back.
**No killswitch, no cap, no freeze gate anywhere in the chain** — `glm-b/0080`
measured that and this task re-read the same hops at `b1f290c84` and agrees.
`repo.require` is membership-permission only (`repo.py:146-158`), and the
killswitch gates *starts*, not stops.

### 2.2 `POST /campaigns/resume` — reaches EmailBison; HeyReach resume is sealed

    POST /campaigns/resume                               app.py:1378
      security.require(session, CAMPAIGN_PAUSE)           app.py:1379
      _campaign_run_state(..., "resume")                  app.py:1631-1635
        api.resume_campaign                               api.py:3205
          repo.require(ws.CAMPAIGN_PAUSE)                 api.py:3212
          orchestrator.resume(..., role=roles.ADMIN)      api.py:3223   ← hardcoded
            roles.require(role, RESUME_CAMPAIGN)          orchestrator.py:620
            campaigns.validate(..., ignore_status=True)   orchestrator.py:621
            _resume_at_providers                          orchestrator.py:648
              providerwrites.perform(EMAIL_RESUME, ...)   orchestrator.py:681
                — EMAIL_RESUME is ("email", facing=False), so `perform`
                  does NOT run executionguard.revalidate and therefore
                  never reaches killswitch.require
                                                          providerwrites.py:407-412, 2567-2568
                require_resonate_os_campaign               :2528
                transport → bison.resume_campaign(pid, expect_leads=n)
              LINKEDIN_RESUME remains sealed              orchestrator.py:655-657

Two findings already on the record and re-read here, not restated from the lane
file alone:

- **The hardcoded `roles.ADMIN` at `api.py:3223` is a real escalation, not an
  apparent one.** `CAMPAIGN_PAUSE` is granted to workspace `_REVIEWER`
  (`workspaces.py:116-118`), campaign-layer `roles.REVIEWER` deliberately lacks
  `RESUME_CAMPAIGN` (`roles.py:38-45`, "can stop a run, but cannot start one"),
  and the one layer positioned to refuse is handed ADMIN. The pause side
  hardcodes ADMIN too (`api.py:3185`) and is **inert**, because campaign-layer
  REVIEWER does hold `PAUSE_CAMPAIGN`. `glm-c/0140`'s born-red test proves the
  resume half empirically.
- **`campaigns.validate` is the only check on the resume path that is doing any
  real work**, and it works by fingerprint rather than by consulting any
  barrier. Confirmed for this inventory: `campaigns.material`
  (`campaigns.py:282-293`) includes `bison_campaign_id` and
  `heyreach_campaign_id`, so the approval fingerprint covers the provider
  mapping, and a mapping changed after approval makes
  `approval_is_current` False.

### 2.3 `POST /settings/mapping` — the enabler, and it is the one nobody has named

Neither pause nor resume can reach a provider unless the canonical campaign row
binds a provider campaign id. **`POST /settings/mapping` is the only route on
this surface that writes that field**, and it is also what the ownership gate
reads to decide whether a write is permitted at all.

`api.set_provider_mapping` (`api.py:4055`) assigns
`campaign["bison_campaign_id"] = (bison or "").strip()[:80] or None` and saves.
**There is no validation of the value beyond an 80-character truncation**: no
check against the operator's internal list, no check that the id exists, no
check that it is a number. It also does not go through
`orchestrator.map_external` (`orchestrator.py:192`), so
`roles.require(role, CHANGE_MAPPING)`, the `EXTERNAL_CAMPAIGN_MAPPED` event and
`_invalidate_if_needed` are all skipped; what it writes instead is a
`mapping_changed` log line, and only when an approval already exists.

Now the consequence. `providerwrites.classify_campaign`
(`providerwrites.py:2015-2039`) answers in this order:

    key not canonicalisable            → unknown      (refused)
    key in declared_internal[channel]  → resonate_internal  (refused)
    any ledger row binds key           → resonate_os        (PERMITTED)
    otherwise                          → unknown      (refused)

`_ledger_rows_binding` reads `work/campaigns.jsonl` and returns a hit for **any**
row whose `bison_campaign_id` equals the key. So a `provider_settings.manage`
holder — workspace admin and up — who writes a provider id into any campaign
row in their own workspace has, by that act, made that provider campaign
classify as `resonate_os`. A `campaign.pause` holder — workspace reviewer and
up — can then pause it at EmailBison.

**The four operator-declared campaigns are protected and this was checked.**
`config/internal-campaigns.txt` declares `bison 274`, `327`, `328`, `352`, the
list is read on every call and never cached, and it is consulted **before** the
ledger precisely because "on 2026-09-18 a canonical row re-bound to 327 — one of
these very campaigns — carried an authorization straight onto it"
(`providerwrites.py:1852-1857`). That fix holds against this route.

**418 is not protected.** `docs/state/PROVIDER-CAMPAIGNS.json` in this tree
(`generated_at: 2026-09-30T20:40:42+00:00`) lists campaign **418** in
`sending_now`, name `PRODUCTIVE - SOFTWARE DEVELOPMENT - NOT CONNECTED - JELENA
- AUGUST 24`, 24 leads. CLAUDE.md records 418 as still ACTIVE with ownership
UNKNOWN and not knowable from the provider. It appears on no line of
`config/internal-campaigns.txt`. So the sequence above — map a campaign row to
`418`, then pause — passes the ownership gate, by construction, because the
gate's positive evidence is a row this route writes.

What actually stands below it is **door A**:
`providers.refuse_unauthorized_write` (`src/providers/__init__.py:769`,
default-REFUSE at the socket unless `RESONATE_PROVIDER_WRITES=1`), cited from
`glm-c/0130`'s committed measurement — **no file under `src/providers/` was
opened by this task**, per standing rules. Door A is an environment variable the
operator sets. **It is procedure, not one of the three barriers CLAUDE.md
names**, and that is the whole shape of this finding: the last line of defence
on the console's only provider-write path is a variable, and the gate above it
can be satisfied from the console itself.

Not a theoretical chain, and not an exploit either: it needs two legitimate
permissions and an operator who has turned provider writes on. It is filed as
what it is — **an inventory finding about where the ownership gate's evidence
comes from**, with a recommendation in §7 and no code changed.

### 2.4 Routes that reach a network, but not a provider

`GET /auth/start` and `GET /auth/callback` make outbound HTTPS calls to the
OIDC identity provider (`oidc.py:360-367`). They are the only other routes that
open a socket. Reachable only when `AUTH_PROVIDER=oidc`; both 404 otherwise.

---

## 3. DERIVED LIST 2 — ROUTES WHOSE DOCUMENTED CLAIM IS FALSE

Dated by pickaxe, as the three lane entries were. **Every sentence in this
section was born in the root commit `628723472`, 2026-09-09 21:32:34 +0200, and
has never once been revised.** `git log -S` over `src/web/` and
`src/workspaces.py` returns that single commit for each of the nine strings
below. So in every case the falsifying event is a change *somewhere else*, or —
in two cases — no commit at all.

The three commits that did the falsifying:

    09cf9b7c8   2026-09-13 00:02:57 +0200   SUPPORTED gained EMAIL_PAUSE / LINKEDIN_PAUSE
    1f62182bc   2026-09-13 00:44:29 +0200   orchestrator.pause defaults to provider=True
    6ff9cc945   2026-09-24 16:53:55 +0200   _resume_at_providers + EMAIL_RESUME

`/campaigns/pause` has existed since the root commit too (pickaxe on
`campaigns/pause` over `src/web/`: `628723472` only). **So the route was wired
before the write existed, and the sentence describing it was never revisited
when the write arrived.** That is the generating mechanism for this whole
section, and it is one line in a changelog away from happening again.

### 3.1 "This build makes no provider call" — FALSE since 2026-09-13 00:44:29

Five sites, all of them rendered, not merely stored:

| site | text | reached from |
|---|---|---|
| `pages.py:4881` | "**No provider call has been made. This build does not make one from any surface.**" | `GET /admin` |
| `api.py:4240`, `api.py:4265` | "this build makes no provider call" — the second is a `note` **field rendered on the page** | `GET /admin` |
| `api.py:5443` | "Nothing in this build calls a provider, so claiming health would be inventing the one fact this screen exists to report" — and every provider's `state` is `NOT_CALLED` | `GET /admin/health` |
| `api.py:1677` | "no provider is called in this build" | `GET /health` |
| `pages.py:3840-3842`, `pages.py:4862-4864` | `row("Live sending", tag("DISABLED", "pass"))`, `row("EmailBison", tag("preview only", "pass"))` — **hardcoded literals with a `pass` class** | `GET /diagnostics`, `GET /admin` |

**And the condition on the strongest of them reads the wrong ledger.**
`pages.py:4881` renders that sentence when `data["providers"]["providers"]` is
empty. That list comes from `api.provider_health`, which walks
`waterfall.ledger(rec)` — a **per-record** list at `rec["waterfall"]`
(`waterfall.py:426`), written by `enrich.spend()` for paid enrichment calls.
A provider *write* leaves a row in a different file,
`work/provider-writes.jsonl` (`providerwrites.py:2266-2272`). **No module under
`src/web/` reads that file.** `grep -rn providerwrites src/web/` returns exactly
one hit, and it is inside a docstring saying `SUPPORTED` is empty.

So: the console can perform a provider write, the write is recorded in a ledger,
and the console has no surface that can show it happened — while the admin page
derives "no provider call from any surface" from a ledger that could never have
recorded one. This is the `suppression/0070` shape exactly, one layer up: a
correctly-computed conditional reading a field the relevant writer does not
write.

Also false in the same breath: `api.feature_flags()` reports
`live_sending: False` because "`push.run(live=True)` raises
LiveSendNotEnabled", and `paid_enrichment: False` because "no web surface runs
a spending job type". **The second is true** — §1d, measured. The first is a
true statement about `push.run` and an irrelevant one about this surface:
`pilotcaps/0050`'s census found 33 call sites, 32 in tests, one production
caller at `src/run.py:365` passing no `live` at all, and **nothing on the
pause or resume path calls `push.run`**. A reader of the diagnostics page sees
`Live sending DISABLED (pass)` and `EmailBison preview only (pass)` and
concludes no provider write can originate here. It can.

### 3.2 `src/web/api.py:3150-3169` — "`SUPPORTED` is empty" · `glm-b/0080`

`pause_campaign`'s docstring: "**IT DOES NOT REACH THE PROVIDER** … `SUPPORTED`
is empty, so `heyreach.pause` and `bison.pause` both refuse by name."
`glm-b/0080` printed `SUPPORTED` at `e2f2d5abd`: **16 verbs, both pauses
present**, `is_supported` True for both. Died `09cf9b7c8` / `1f62182bc`,
2026-09-13. Re-read at `b1f290c84` for this inventory and unchanged.

### 3.3 `src/web/api.py:3196` — the audit row that denies a provider stop · `glm-b/0080`

`after={"status": …, "provider_stopped": False}` with **False a literal**, and
the `reason` string saying "The provider was not asked to stop: no pause route
is supported". The truthful per-channel outcome exists at the moment of the
write — the `CAMPAIGN_PAUSED` event carries `provider_stop`
(`orchestrator.py:560-561`) — and `api.pause_campaign` never reads it.

**Worse than a stored-only lie, because it is rendered.** `pages._audit_change`
(`pages.py:4686-4699`) prints every `after` key as `key: before → after`, and
`GET /audit` (`app.py:1094`) renders it. A human reading the audit log to decide
whether outreach stopped is shown **`provider_stopped: → False`** for a pause
that did stop the provider. And `tests/test_a_pause_says_what_it_paused.py:73-86`
**pins** both the False and the false prose — it passes today only because its
fixture campaign has no provider binding, so no leg runs.

### 3.4 `src/web/app.py:1625-1629` — "Neither of these sends anything or starts sending" · `glm-c/0130`

The docstring of `_campaign_run_state`, the handler behind both buttons. Born
TRUE in `628723472`; killed by `6ff9cc945`, 2026-09-24 16:53:55. Its named
guard — `push.run(live=True)` raising "underneath" the resume — is real code on
no path. `glm-c/0130`'s verdict on each of CLAUDE.md's three barriers, on this
path: **B1 killswitch — DOES NOT HOLD** (`EMAIL_RESUME` is `facing=False`, so
`perform` never reaches `executionguard.revalidate`, the only route to
`killswitch.require`; `orchestrator.py` has never imported killswitch);
**B2 `sending.live` — DOES NOT HOLD** (true as a fact, but no layer of the chain
names a workspace, so no layer reads it — "a switch nothing reads is not a
barrier; it is weather"); **B3 approvals — holds for the legacy ten, by side
effect through a fingerprint mismatch, and not as a gate**.

### 3.5 `src/web/api.py:3223` — `role=roles.ADMIN` on a route granted to REVIEWER · `glm-c/0140`

Not a false *sentence* but a false *design claim*: `roles.py:38-45`'s own
comment says a reviewer "can stop a run, but cannot start one", and
`orchestrator.freeze`'s docstring says "Stopping is deliberately easier than
starting again". The web route pair breaks that: pause and resume are gated by
the **same** workspace permission, and the layer that would restore the
difference is handed ADMIN. Pickaxe: `role=roles.ADMIN` in `src/web/api.py` is a
single commit, `628723472`, 2026-09-09T21:32:34+02:00 — **this path has never
once consulted the actor**. The ingredients are day-one; the overlap became a
provider-write escalation at 2026-09-24 16:53:55.

### 3.6 "Nothing has been sent from this system" — FALSE, and falsified by the world rather than by a commit

Five sites. The first two are **hardcoded literals on surfaces a client sees**:

| site | reached from | shape |
|---|---|---|
| `pages.py:378` | **every page** — `pages.shell`'s safety badge | hardcoded: `<span>Live sending <b>disabled</b></span>` |
| `pages.py:466` | `GET /login` | hardcoded: "Live sending is disabled in this build" |
| `pages.py:892` | `GET /` (client-facing cut) | hardcoded: "Nothing has been sent from this system." |
| `pages.py:3653` | `GET /reporting` (client-facing cut) | hardcoded: "Nothing has been sent from this system, so there are no open rates, no bounce rates and no deliverability figures" |
| `pages.py:5068`, `api.py:2469`, `api.py:4502` | `GET /reporting` (operator cut), analytics qualifiers | hardcoded: "nothing has been sent from this build — so a reply here came from a rehearsal, not from a mailbox" |
| `pages.py:701` | `GET /` | **conditional** on a derived `reached` count — see below |

`pages.py:3653` and `pages.py:892` are rendered on the `simple=True` branch of
`pages.reporting` and `pages.dashboard` — **the client-facing cut, which a
workspace VIEWER sees**, and `REPORTING_VIEW` is held by every role including
VIEWER (`workspaces.py:114`). The sentence is contradicted by two authorities
that are in git and need no provider call:

- `docs/state/PROBLEM-REGISTER.md` **ISSUE-046 · CONFIRMED**: "503/504/505 sent
  **64 emails to real prospects** carrying a different agency's pitch, signed
  with the operator's name from Productive mailboxes."
- CLAUDE.md's incident paragraph: **77 emails** with an empty subject and a
  `<p></p>` body on 09-23, 76 recipients suppressed, **four of them replied to a
  blank email**.

So the sentence was false no later than **2026-09-23**, and no commit made it
so — the world did. That distinction matters for how it gets fixed: a sentence
falsified by a commit can be caught by a reviewer reading a diff; this one can
only be caught by a test that asserts the *behaviour* rather than the prose,
which is the invariant-choice rule all three lane entries applied.

**The exact send count is UNKNOWN from this tree and this task did not guess
one.** CLAUDE.md's prose says 912 provider-confirmed sends across our campaigns
and itself says "Do not trust a send count in prose here; derive it".
`docs/state/PROVIDER-CAMPAIGNS.json` at `generated_at:
2026-09-30T20:40:42+00:00` carries **no send field at all** — its 40 EmailBison
rows hold `bison_campaign_id`, `name`, `status`, `owner`, `lead_count` and
nothing else. The authority that would answer it is a live EmailBison read via
`scripts/provider_truth.py`, which this task may not make.

**And `pages.py:701` is the dangerous one, because it is honest-by-construction
and still renders the false branch.** It says "Nothing has been sent from this
system yet" only when the derived `reached` count is zero — reading confirmed
`push_marked` touch events. CLAUDE.md: "Across our campaigns the provider
confirms 912 sends against **one** recorded touch in 1,582 records." A
conditional reading a field with effectively no production writer produces the
same output as a hardcoded lie, and is harder to see.

### 3.7 `src/workspaces.py:137-138` — "Launch is nobody's by default"

"Launch is nobody's by default. It is granted deliberately, and in this build it
is refused at a lower level anyway: `push.run(live=True)` raises." Two
problems. **`CAMPAIGN_LAUNCH` is granted to `SUPER_ADMIN`**, because
`GRANTS[SUPER_ADMIN] = set(PERMISSIONS)` (`workspaces.py:140`) — so it is
somebody's, and the one role it belongs to is the one that crosses every
tenancy boundary. And the lower-level refusal it names is `push.run`, which
nothing on any web path calls. The permission is also read by nothing — §4.3.

### 3.8 `docs/state/PROVIDER-CAMPAIGNS.json`'s `owner` field — must not be reported

Not a route, but it is state the app would reach for. Each of the 40 EmailBison
rows carries `owner: "resonate" | "client_or_other"`, and
`owner_totals: {resonate: 20, client_or_other: 20}`. This is the exact field
CLAUDE.md withdrew on 2026-10-01: it came from
`provider_truth.owned_by_resonate`, "a BOOLEAN that wrote 'not provably ours'
down as the client's". The file in this tree still carries it, and still labels
**327, 328, 352 and 418** `client_or_other` — which is precisely the claim
CLAUDE.md says was WRONG. Anything reporting ownership must read
`providerwrites.classify_campaign`, which has three states and whose third is
`unknown`.

---

## 4. DERIVED LIST 3 — ROUTES AND PERMISSIONS NOBODY CAN REACH

Measured by searching every `.py` file under `src/` **except `src/web/app.py`**
(the routing table itself, which would match every path trivially) for each
path as a quoted string, then reading each hit to see whether it is a link, a
form action or something else.

### 4.1 A link to a route that does not exist

**`/reporting/editor/preview`.** `pages.py:6991` renders
`link("/reporting/editor/preview?draft=" + draft["id"], "Preview")` in the
report editor's **Export** panel, beside a working "Export PDF" link.
`grep -n "if path ==" src/web/app.py` has no `/reporting/editor/preview`
branch, so the request falls through `_get` to `app.py:1185` and the person
gets the **"Not found"** page with a 404. Born in `628723472` like everything
else here. Nobody has clicked it, which is itself the finding: nobody has
clicked Preview on the report editor since the root commit.

### 4.2 Wired routes with no link or form anywhere

| route | permission | what it does | why nobody reaches it |
|---|---|---|---|
| **`POST /senders/reassign`** | `workspace.manage` (both layers) | `api.reassign_sender` — "**the only way a stored assignment changes**" (`api.py:611`); writes `queue.jsonl` + `audit.jsonl`, refuses a cross-workspace or unknown sender | **No `<form>` in `src/web/pages.py` or anywhere else posts to it.** `GET /senders` renders the roster and the assignments table; neither carries a reassign control. The route, the service function, its three exception classes and its 409/404 branches are all live, and nothing can invoke them from a browser |
| `GET /export/contacts.csv` | `contacts.export` | contact-level CSV, including the `source:` columns an import did not recognise; writes an audit row and two notification rows | No link. `/export/analytics.csv` **is** linked (`pages.py:5039`); this one and the JSON twin are not. Reachable only by typing the URL |
| `GET /export/analytics.json` | `reporting.export` | the analytics payload as JSON | No link |

`/healthz`, `/slack/interactions` and `/auth/callback` also have no link, and
should not: the first is for an infrastructure probe, the second is where Slack
posts, the third is where the identity provider redirects. They are listed in
§1a and are not findings.

### 4.3 Permissions that are declared, granted, and read by nothing

    workspaces.CAMPAIGN_LAUNCH   "campaign.launch"   workspaces.py:71
    workspaces.CAMPAIGN_EDIT     "campaign.edit"     workspaces.py:69

Both are in `PERMISSIONS` (`workspaces.py:100`), both are in `GRANTS` —
`CAMPAIGN_EDIT` to `_OPERATOR` and up (`workspaces.py:121-122`), `CAMPAIGN_LAUNCH`
to `SUPER_ADMIN` only — and **neither is passed to `security.require`,
`security.may`, `repo.require` or `repo.may` anywhere in the repository.**
`grep -rn 'CAMPAIGN_LAUNCH\|ws.CAMPAIGN_EDIT\|workspaces.CAMPAIGN_EDIT' src/`
returns only the declaration, the tuple and the grant sets; every other hit in
`src/` is `events.CAMPAIGN_LAUNCH_READY` or
`eligibility.BLOCKED_CAMPAIGN_LAUNCHED`, different names.

So there is no route a `campaign.edit` holder can reach that a holder of the
other operator permissions cannot, and `campaign.launch` guards nothing — it is
a flag the admin page *reports* (`api.py:4400`: `{"flag": "campaign.launch",
"state": False, "why": "granted to no role below super admin, and refused below
that"}`) describing a check that does not exist. "Existence is not function",
in two lines.

### 4.4 Gated by a permission, reachable by the role above it

Not unreachable, but worth recording because the asymmetry is the kind that
looks like a bug later: `POST /reporting/client/generate` requires
**`reporting.view`**, which a workspace **VIEWER** holds — so the most
client-facing role can generate a PDF and write a row to `reports.jsonl`
— while `POST /reporting/editor/*` requires `reporting.export`, operator and
up. The generate path is presumably deliberate (the report is *for* the client)
and `api.generate_report` resolves the template and sections through allowlists
so a forged form field cannot put the provider table into a client's document.
Recorded, not filed.

---

## 5. WHAT THIS APP COULD TRUTHFULLY REPORT TODAY — one paragraph, not a design

**Report only what has exactly one canonical authority that some production
writer actually writes, and the honest set is smaller than the screens
suggest.** Truthful today, because each is derived from state the console
itself writes on every action: the **audit log** (`work/audit.jsonl` — who did
what, in which workspace, with before/after, written by `repo.audit` on every
mutation on this surface), **workspace membership and what each role carries**
(`work/workspaces.jsonl` plus `GRANTS`, read not retyped — the admin page
already does this correctly and says why), **job history** (`work/jobs.jsonl`,
with the `RUNNABLE`/`UNRUNNABLE` split, which is structurally true), **upload
and batch provenance** (`work/queue.jsonl`, and the refusal-whole-rather-than-
truncated behaviour means a row count means what it says), **verification
outcomes with both halves of every rate** (`pages.reporting` already prints
every numerator beside its denominator, which is the one discipline on this
surface that has never lapsed), **notification *planning*** (`work/notifications.jsonl`
— that a message was built and where it would go, never that it was delivered),
and **credential presence as presence** (`provider_states` returns a variable
name and a boolean and never a value). It must **not** report: **anything
about sending** — "nothing has been sent", open rates, deliverability, or a
reach count derived from `push_marked` touches, because the provider confirms
hundreds of sends against one recorded touch in 1,582 records and the local
authority is empty; **"no provider call has been made"** or any live-sending
badge, because the pause and resume routes do write to EmailBison and the
console reads the wrong ledger to find out; **`provider_stopped`** from the
pause audit row, because it is a hardcoded `False` rendered as a denial;
**campaign ownership from `PROVIDER-CAMPAIGNS.json`'s `owner` field**, which is
the two-state boolean CLAUDE.md withdrew — ownership has three states and the
third is `unknown`; **`campaign.launch` as a flag**, which describes a check
that does not exist; and **anything resembling "bounce protection: active"** —
`suppression/0070` measured the gate real, consulted on every send, and reading
`events.EMAIL_BOUNCED`, which only `leadobserve.confirm_email_touches` writes
and which has **zero production callers**, so `channels.email_verdict` returns
`(True, None)` — SENDABLE, no reason — for all three addresses EmailBison has
already bounced. The rule that falls out of every one of those, and the only
one worth carrying into a report design: **a report may render a safety state
only where the same measurement that proves the guard exists also proves
something writes the field it reads** — and where it cannot, it says UNKNOWN,
which never becomes PASS.

---

## 6. WHAT THIS TASK DID NOT MEASURE

Named so nobody reads a gap as a pass.

- **Whether the real, unpatched transport would admit any of these writes.**
  That is a property of `src/providers/*`, which standing rules forbid this lane
  to read. Door A is cited from `glm-c/0130`'s committed measurement and
  **no file under `src/providers/` was opened.** UNKNOWN by rule; the authority
  is `src/providers/__init__.py:769`.
- **Who actually holds which permission in production.** Memberships are runtime
  state in `work/workspaces.jsonl`, and production `work/` is prohibited
  reading. What *code* fixes is in §1 and §4; the population is UNKNOWN, and the
  authority is production `work/workspaces.jsonl` plus `work/audit.jsonl`.
- **The provider-confirmed send count.** §3.6. The authority is a live
  EmailBison read via `scripts/provider_truth.py`.
- **Whether any of this is live.** No server was started and no listener opened.
  The last independent measurement of the port range is `glm-c/0140`'s at
  2026-10-15 19:54:42 — zero listeners on 8765-8799 — and a measurement from
  another task is not a measurement taken now. **Treat the reachability column
  as "reachable the moment somebody runs `py -m src.web`", which is the honest
  reading and the one `glm-b/0080` and `glm-c/0130` both arrived at.**
- **No born-red test was written.** This task's deliverable is the map. Each of
  §3.1, §3.6, §4.1, §4.2 and §4.3 is a candidate for one, and §2.3 is the
  candidate with the highest value: *a campaign row bound to a provider id the
  operator never declared may not pass `require_resonate_os_campaign`*.

## 7. RECOMMENDATIONS — NOT APPLIED. `src/` was not touched.

1. **`api.set_provider_mapping` (`api.py:4055`)** — refuse a provider id the
   ownership gate would then bless on this route's own evidence. Smallest honest
   shape: call `providerwrites.classify_campaign(channel, value)` **before**
   writing, and refuse `resonate_internal` outright; for `unknown`, require the
   operator to have declared it, because "absence of a claim is not evidence
   that a campaign is ours" is already this system's rule and this is the one
   route that can manufacture the claim. Second, route the write through
   `orchestrator.map_external` so `roles.require(CHANGE_MAPPING)`,
   `EXTERNAL_CAMPAIGN_MAPPED` and `_invalidate_if_needed` run — three guards the
   current path skips for no stated reason.
2. **A surface that reads `work/provider-writes.jsonl`.** The console can cause a
   provider write and has no screen that can show one. Until that exists, every
   "no provider call" sentence on `/admin`, `/admin/health`, `/health` and
   `/diagnostics` is unfalsifiable from inside the product. One table on
   `/diagnostics` — verb, campaign, class, outcome, when, by whom — would make
   §3.1 self-correcting.
3. **The five hardcoded "nothing has been sent" literals** (`pages.py:378`,
   `466`, `892`, `3653`, `5068`) — two of them on client-facing cuts. Either
   derive them from an authority that something writes, or delete the sentence.
   A badge on every page saying `Live sending disabled`, which no code consults,
   is weather.
4. **`api.py:3196`** — compute `provider_stopped` from the `CAMPAIGN_PAUSED`
   event's `provider_stop` field, which exists at the moment of the write, and
   gate the vendor-UI sentence on no leg having run. `glm-b/0080` proved this
   shape green under mutation, including against the 2026-09-11 module whose
   unbound fixture legitimately still records `False`.
5. **`api.py:3223`** — `role=roles.role_of(repo.config(), by)`.
   `glm-c/0140` proved it green and spelled out the deliberate consequence:
   under `productive.yaml`, which has no `slack` block, the Resume button would
   refuse everyone until the operator names people. That is fail-closed and
   consistent with "resuming any of the three needs the operator's explicit
   `APPROVED`".
6. **`/reporting/editor/preview`** — add the route or remove the link. A 404
   behind a button on a report screen is the cheapest fix in this document.
7. **`CAMPAIGN_LAUNCH` and `CAMPAIGN_EDIT`** — either give them a consumer or
   delete them, and in either case stop reporting `campaign.launch` as a flag
   whose `why` describes a refusal that does not exist.
8. **`POST /senders/reassign`** — decide which it is. If sender reassignment is
   a capability, `GET /senders` needs the form; if it is not, the route and
   `api.reassign_sender` are dead weight carrying a `workspace.manage`
   permission.

Every one of these is the operator's call. Nothing in §7 was applied, no file
under `src/` was changed, and `origin/master` is untouched at `b1f290c84`.
