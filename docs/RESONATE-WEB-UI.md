# Resonate OS web application

The feature branch retains the repository's server-rendered application and
shared CLI services. It does not introduce a parallel API, store, client-side
eligibility engine or sending path. Production runtime dependencies remain
Python standard library only.

## Product and design contract

Design source: [Resonate OS — Product Design](https://www.figma.com/design/DJawQ0JVsjKHBHcgkFhGsL/Resonate-OS-%E2%80%94-Product-Design).
Start with frame `24:3` (00 — START HERE); UX contract is frame `25:3`
(27 — UX States & Frontend Contract). The current numbered product frames
were inspected, excluding obsolete `ZZ` explorations. Figma's example counts,
charts and status labels are not application data.

The existing backend already supplies the requested surfaces. The shared
shell, tokens, controls, loading/error states and responsive styling apply
across them; their existing business actions remain server forms.

| Surface | Figma frame | Existing application route |
| --- | --- | --- |
| Operator dashboard | 20:3 | `/` |
| Upload and preflight | 20:127 | `/upload`, POST `/upload/commit` |
| Batch detail | 23:220 | `/batches/<batch>`, `/jobs` |
| ICP review | 21:3 | `/icp` |
| Companies and dossier | 21:86, 23:3 | `/companies`, `/companies/<id>` |
| Contacts and detail | 21:176, 23:114 | `/contacts`, `/contacts/<record>/<contact>` |
| Segments | 22:3 | `/segments` |
| Campaign builder | 20:234 | `/campaigns/new` |
| Campaign detail and QA | 23:320 | `/campaigns/<id>` |
| Outreach preview | 21:271 | `/outreach`, `/outreach/accounts`, `/outreach/cadence` |
| Approval queue | 21:394 | `/approvals`, `/approvals/plan` |
| Replies | 21:471 | `/replies`, `/replies/context/<record>/<contact>` |
| Client reporting and report detail | 20:349, 23:512 | `/reporting`, `/reporting/client`, `/reporting/editor` |
| PDF reports | 23:512 | existing client download and editor export routes |
| Scale simulator | 22:89 | `/simulator` |
| Timezone routing | 22:181 | `/timezones` |
| Workspace settings and users | 22:259, 23:429 | `/settings`, `/users`, `/workspaces` |
| Audit | 22:363 | `/audit` |
| Diagnostics | 22:440 | `/diagnostics`, `/health` |

Dark surfaces, mint navigation/actions, density, reusable tables and status
badges follow Figma. Muted text is brighter for contrast. Navigation preserves
the repository's role-filtered sections and additional supported workflows.
System fonts avoid external requests; Inter is not downloaded at runtime.

## Architecture and data

- `app.py` retains session resolution, route permissions, CSRF checks and
  native GET/POST routing. Authenticated HTML and other dynamic responses are
  `no-store`; only the three allowlisted static assets receive public caching.
- `api.py` continues to obtain verdicts from canonical services. New adapters
  search already scoped serialized company/contact rows **before pagination**,
  expose batch jobs and supply allowlisted runtime/audit information.
- `pages.py` renders the server's results. Company/contact filters survive
  empty results; pagination preserves escaped queries, filters and batch scope.
- `static/app.css` is the reusable responsive design system. The logo, CSS and
  JS are local, versioned by content digest. Strict CSP is unchanged. Native
  progress elements and CSS classes replace inline styles blocked by CSP.
- `static/app.js` progressively enhances filters, file selection, keyboard
  navigation and native form pending states. It neither calls a provider nor
  computes permissions, ICP verdicts, approval validity or channel eligibility.
- No application state is stored in the browser. Native navigation remains
  usable without JavaScript; a restored browser history page reloads before
  reusing a tenant's previous content.

## Truth and safety boundaries

The repository wins where the Figma annotations are older than the code:

- Production OIDC sign-in already exists. The UI reflects actual sign-in mode;
  demo sign-in is explicitly identified and is not identity verification.
- Optional `replywatch` reconciliation already exists. Its real health verdict
  is shown, including disabled, never-run, stale and failing states. Configuration
  is not presented as proof that a poll succeeded. No provider errors,
  checkpoints or foreign workspace names are included in the dashboard adapter.
- No automatic cadence sender has been added. `push.run(live=True)` remains
  refused. There is no live Send or Launch action.
- Paid browser jobs remain refused. Upload remains preview, then explicit
  commit, followed by the existing permitted processing stages.
- Held contacts, MX/security outcomes, verification consensus, suppression,
  ICP review, channel eligibility and company reply pauses are rendered from
  existing server verdicts. They are not relaxed to populate the UI.
- Campaign review still uses the exact server fingerprint; stale approval
  requests retain their existing refusal path.
- Batch details now verify membership in `repo.batches()` before rendering;
  foreign and missing batch IDs both receive 404.
- Client reporting retains its separate server-side redaction and access
  boundary. Operator cost, provider and runtime cards never enter the client
  dashboard or report merely to be hidden with CSS.

## UX states

| State | Behavior |
| --- | --- |
| Loading | Native form becomes busy, live region announces pending request, skeleton/progress appears; repeated submit is guarded |
| Empty | Backend-derived empty state keeps search and filters usable |
| Error | Escaped generic error, no exception details; failed GET can reload; failed POST does not claim that nothing changed |
| Permission denied | Server 403 and accessible alert; role-aware navigation and controls remain a convenience over enforcement |
| Stale approval | Existing current-fingerprint check refuses the mutation; UI shows the server refusal |
| Held contact | Existing held verdict and reasons, no override invented |
| Reply-paused company | Existing pause status and server-governed handling action |
| Production blocked | Persistent live-sending-disabled status and factual runtime health |

Loading enhancement never retries a write or claims success. If no new page
arrives, it tells the operator to check the current record before repeating an
action. PDF/download forms can leave the current document visible.

## Brand asset

`src/web/static/resonate-logo.png` is the unchanged logo image referenced by
the [Resonate Group website](https://www.resonategroup.co/), retrieved from its
[published Wix asset](https://static.wixstatic.com/media/e8370b_b4dab583973f49b289c8b93c99ee345f~mv2.png).
It is used to identify this Resonate application, not as a newly invented mark.
The build manifest records its SHA-256 digest alongside the other assets.

## Reproducible checks

The repository targets Python 3.14 (`.python-version`). Browser tools are
development-only; they do not become server dependencies.

```sh
python -m tests.offline
python -m compileall -q src tests
npm ci
npx playwright install chromium
npm run lint:web
npm run test:web
python -m src.web.build
git diff --check
```

Run suites sequentially, as required by `CLAUDE.md`. When a development
environment supplies a **loopback HTTP proxy**, unset `HTTP_PROXY`,
`HTTPS_PROXY`, `ALL_PROXY` and their lower-case equivalents for the offline
test process. Otherwise a request can reach the proxy through the harness's
loopback exception and stall instead of being refused. Do not use production
provider credentials or runtime state for tests.

`tests/browser/control-center.cjs` starts its own throwaway demo server with a
minimal environment, follows real detail links, checks desktop/mobile screens,
uploads and commits a fictional file, inspects pending/error states and verifies
viewer restrictions. It also checks CSP and no-JavaScript navigation.
Optional `PYTHON`, `PLAYWRIGHT_MODULE_PATH` and `BROWSER_EXECUTABLE_PATH` select
already-installed development tools. Screenshots go to ignored `out/browser`.

The production asset artifact is `out/web/{app.css,app.js,resonate-logo.png,manifest.json}`.
It is not a standalone SPA: deployment must include the existing Python
application, configuration and all static files. Existing production OIDC,
trusted-proxy/HTTPS, durable storage, backup, provider validation and release
gates remain applicable. A UI build does not certify live outreach readiness.
