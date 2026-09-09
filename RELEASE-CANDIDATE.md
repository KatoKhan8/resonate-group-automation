# Release candidate

What this build is, what it refuses to be, and the shortest honest path
from here to a first Productive pilot.

Three questions are asked and answered separately, because conflating them
is how a system gets deployed and then quietly switched on:

1. **Is it a coherent release locally?**
2. **Can the application be put online?**
3. **Can real outreach start?**

The answers are not the same. §Verdicts.

**§0 below is where this stands today. Everything from §1 onwards is a
record of 2026-09-02 against commit `1309079`, kept as written.** Two of
the issues it lists have since been closed, and reading them as open is
exactly the mistake a document with this title should not cause.

---

## 0. Where this stands now — 2026-09-07

| | |
| --- | --- |
| Commit | `1880d54` |
| Full suite | **5,495 tests, OK** |
| Offline harness | **5,495 tests, OK** — nothing reached off this machine |
| Mutation registry | **470** guards, each asserted to still match the code it removes (`tests/test_mutation_anchors.py`) |
| Runtime | CPython 3.14.3 locally; 3.14.6 on the deployed demonstration |
| Third-party dependencies | still none |

### What has changed since §1

**Production authentication exists.** It was §5's only open P1 and it is
closed: `PRODUCTION-AUTH.md` is the mechanism and
`tests/test_production_auth.py` is 71 tests of it, including an OIDC
provider that says yes to somebody this system still refuses. Read §5's
P1 row as historical.

**A cadence experiment screen exists** (`/campaigns/experiments`), which
was a P2.

**A workspace can be configured from the product.** Onboarding creates the
workspace and its client file; `/settings` now carries the market rule, the
geo lists and the out-of-market answer, and `/settings/personas` carries
who counts as a decision maker. The readiness checklist used to point at a
screen that could configure neither.

**One read path for a workspace's settings.** `clients.load` applies
workspace overrides, so a `--client` command line and the web layer read
the same rules. They did not before, and the one that mattered was
`verification.required_confirmations`: a workspace that had raised it to
three was verified at two from any terminal.

**The import preview screens every person** rather than the first at each
company, reads semicolon and tab exports, reports a row whose shape does
not match its header, and says how many addresses could be written to
today and what verifying the rest would cost.

**A referral can become a contact**, through a person, skipping no gate.

### The micro-pilot, by kind of blocker

Nothing below is a matter of opinion; each row names what would close it.

| kind | blocker | closes when |
| --- | --- | --- |
| **HUMAN** | The EmailBison key was exposed and has not been rotated | somebody rotates it — `HUMAN-ACTIONS-REQUIRED.md` §1 |
| **HUMAN** | Productive exclusivity is undecided while ~160,000 of their prospects are mid-sequence in HeyReach | a conversation, not a build — §5 there, and `PRODUCT-GAPS.md` §15 |
| **PROVIDER** | HeyReach reply reading has never returned a cursor from the real API | one authorised read |
| **PROVIDER** | Deliverable's response shape has never been seen | one authorised credit |
| **PROVIDER** | No Slack token, so every notification is fixture-proven only | a token and a channel |
| **CONFIGURATION** | Reply polling and the digest are off by default, including in production | `REPLY_POLL_ENABLED` and `DIGEST_SCHEDULE`, once somebody wants them |
| **CONFIGURATION** | A container filesystem is ephemeral; no volume has ever been mounted | point `QUEUE` at a mounted volume |
| **DATA** | Canonical state knows nothing about outreach already running in the providers | an import of provider-side engagement, or a pre-send check that asks the provider |
| **CODE** | Nothing can send. `push.run(live=True)` raises and there is no code path to either provider | deliberate, and it is the last thing that should change |

**The verdict has not moved.** Local release candidate: GO. Online
demonstration: GO. Live Productive pilot: **NO-GO**, and the reason is the
same one §7.3 gives — every provider is unvalidated on the wire, and the
DATA row above is the one that would let a prospect hear from the same
company twice.

What *has* moved is that none of the remaining blockers is a defect. They
are a credential, three provider reads, two switches, a volume, a
conversation, and a refusal that is there on purpose.

---

## 1. The build

| | |
| --- | --- |
| Commit | `1309079` (this document is committed on top of it) |
| Branch | `master` |
| Date | 2026-09-02, 01:30 CEDT |
| Runtime | CPython 3.14.3, and no other version has ever run this code |
| Third-party dependencies | none. Every import in `src/` is standard library, asserted by `tests/test_deployment_config.py` |
| Full suite | **4,774 tests, OK** (503s) |
| Offline harness | **4,774 tests, OK** (493s) — `socket.connect`, `getaddrinfo`, `gethostbyname`, `connect_ex` and `sendto` blocked; loopback permitted so the web tests can drive a real server |
| Mutation audit | **392/392 caught** |
| Adversarial passes tonight | 11 hand-run attacks, each failing the intended test for the intended reason; 6 of them now permanent in the audit |
| Mutation process active at commit time | no |
| Source restoration | verified: clean tree, staged file by file |

### What changed tonight

Four things, and none of them is a feature. `FINAL-SYSTEM-INTEGRITY-AUDIT.md`
is the full record.

1. **The production refusal that was documented and did not exist.**
   `config.verify()` had a docstring saying "called at startup" and no
   caller anywhere. `web.app.check_configuration` calls it now.
2. **A refusal to publish an unauthenticated console.** Signing in is
   picking an email out of a list. Production mode refuses to start; a
   non-loopback bind refuses unless the estate is fictional.
3. **A demo fallback removed from a production path.** The copy experiment
   screen showed planted totals for every real campaign, because nothing
   writes `cadence_graph`. It now says so instead.
4. **Deployment configuration that a platform can read** — and that is
   asserted against the application rather than read by a human.

---

## 2. Deployment architecture

The simplest thing compatible with the code, which is one process.

```
   app.resonategroup.co
          │
   ┌──────▼───────────────────┐
   │ platform TLS proxy       │
   └──────┬───────────────────┘
          │
   ┌──────▼───────────────────┐
   │ web  ×1                  │   python -m src.web
   │ ThreadingHTTPServer      │   http.server; never exposed directly
   └──────┬───────────────────┘
          │
   ┌──────▼───────────────────┐
   │ JSONL under a file lock  │   ephemeral without a volume
   └──────────────────────────┘
```

| component | required today | why |
| --- | --- | --- |
| web | **yes** | the only process this build has |
| database | no | state is JSONL. `DATABASE-MIGRATION.md` is the Postgres path and has not been executed |
| worker | no | jobs run in the request process and resume from a checkpoint |
| scheduler | no | nothing runs on a timer. "Weekly" describes intent in `discovery` and `refresh`, and both say so |
| Redis / queue | no | the job model is a cursor on a job row. A queue nobody needed is a service somebody has to operate |
| object storage | no | PDFs re-render from stored settings; no bytes are archived |
| persistent volume | **for the product, yes** | a container filesystem is ephemeral. Not needed for the demonstration |

### The web service

| | |
| --- | --- |
| Process | `python -m src.web --demo --host 0.0.0.0 --port $PORT` |
| Port | `$PORT`, injected by the platform. `WEB_PORT` is the fallback and `--port` wins |
| Health check | `GET /healthz` — unauthenticated, touches no provider, returns `{"ok", "demo", "live_sending", "sessions"}` |
| Replicas | **exactly 1.** State is single-writer by construction, and demo state is per process |
| Restart policy | on failure, 3 retries |
| Graceful shutdown | `SIGINT` closes the server; there is no in-flight work that outlives a request |
| Persistence | none in demo mode: a fresh throwaway directory per process, so a restart is a fresh demonstration |

**`--demo` is load-bearing.** §Verdicts explains why it is the only thing
this build may publish.

### Files that exist for the platform and nothing else

`requirements.txt` (empty of packages — a build identifies a Python
application by finding one), `.python-version` (`3.14`), `Procfile`,
`railway.json`. `tests/test_deployment_config.py` puts each start command
through `app.parser()` and `app.check_configuration` — the same parser and
the same refusal `main()` uses.

---

## 3. Configuration

Names only. `config/.env.example` carries all of them with a line each,
`src/config.py` classifies them, and `python -m src.config --mode
production` prints which are missing without printing a value.

**Required to deploy the demonstration: none.** An empty environment runs
it, which is the whole point of having a demo mode.

| group | names | when |
| --- | --- | --- |
| app | `APP_MODE` `WEB_HOST` `WEB_PORT` `WEB_QUIET` `WEB_DEBUG` | optional; `WEB_DEBUG` is demo-only |
| auth | `SESSION_SECRET` `AUTH_PROVIDER` `AUTH_CLIENT_ID` `AUTH_CLIENT_SECRET` `AUTH_ALLOWED_DOMAINS` | reserved. None is read by any code path, and setting them does not make production start |
| database | `DATABASE_URL` `DATABASE_POOL_SIZE` | reserved for the migration |
| state | `QUEUE` and fourteen siblings | `QUEUE` is the only one to set: everything else defaults to its directory |
| providers | `CONTACTOUT_TOKEN` `AIARK_KEY` `REOON_KEY` `DELIVERABLE_KEY` `DELIVERABLE_RESULT_SHAPE` `BISON_KEY` `BISON_BASE` `HEYREACH_KEY` `APIFY_TOKEN` `LLM_API_KEY` | only once live provider work is authorised |
| Slack | `SLACK_BOT_TOKEN` `SLACK_SIGNING_SECRET` `SLACK_OPS_CHANNEL` `SLACK_LIVE` | as above. A token alone never enables posting |

Two of those deserve a sentence each. `DELIVERABLE_RESULT_SHAPE=confirmed`
is the one variable that changes what the system believes about itself,
and it may only be set after a real Deliverable answer has been read.
`LLM_API_KEY` is reserved and unread: `src/llm.py` takes a model *object*,
no provider is wired in, and drafts in this build are written by a person.

---

## 4. What stops it

| | |
| --- | --- |
| Global | `push.run(live=True)` raises and `tagsync.send` refuses. Not flags — there is no code path to either provider |
| Workspace | `sending.live` absent means off. Absence is a decision here, and a test says so |
| Campaign | freeze (any reviewer) and pause. Freezing needs `PAUSE_CAMPAIGN`, lifting needs `RESUME_CAMPAIGN` |
| Account | held, paused or suppressed |
| Contact | suppressed, stopped, or replied |
| Step | re-decided at payload time from primary state |
| Reachability | `check_configuration` refuses production mode and any non-loopback bind that is not the fictional estate |

`src/killswitch.py` evaluates every layer and reports every verdict rather
than short-circuiting, so an operator who turns a campaign back on can see
the account is still held. **It has no setter.** The only way to make
`GLOBAL` permit sending is to change the code that refuses.

**Rollback.** The application is stateless in demo mode and rolls back by
redeploying the previous build; there is no artefact to reconcile and no
schema to reverse. For the product, migrations must be additive —
`DEPLOYMENT-PLAN.md` §10.

---

## 5. Known issues

Everything found tonight, classified. `FINAL-SYSTEM-INTEGRITY-AUDIT.md`
has the reasoning.

### P0 — open: none

Two were found and both are closed. Neither was closed by building
authentication; both are refusals that make the absence loud.

### P1 — open: one

| | |
| --- | --- |
| **No production authentication** | The pilot blocker. Signing in proves nothing about who somebody is. `LIVE-VALIDATION-PLAN.md` §5.1 |

Closed tonight: `AUTH_PROVIDER` satisfying a check without implementing a
mechanism; container state being silently ephemeral (now documented, with
the one env var that fixes it).

### P2 — open

| | |
| --- | --- |
| Sessions are in memory | A restart signs everybody out, and a second process cannot share them. `PRODUCT-GAPS.md` §6 |
| `cadence_graph` is read by four callers and written by none | The last open instance of this codebase's recurring defect. The copy experiment screen now says so rather than showing demo totals. `PRODUCT-GAPS.md` §13 |
| Only `/companies` and `/contacts` paginate | Measured where it mattered, undone everywhere else. `PRODUCT-GAPS.md` §3f |
| No cadence experiment screen | Every module has a CLI; none has a page |

### P3 — open

Twelve public functions with no reference anywhere - sixteen when this was
written. `events.pause_company`, which had a docstring claiming a caller it
does not have, is **closed**: deleted 2026-09-09, as the only one of the set
that was a trap rather than merely unused. The rest remain;
`cadencegraph.account_multichannel` importing a production template from
`web/democadence.py`; `api.system_status`/`provider_health` overlapping
`api.system_health`. All recorded, none fixed: they are not this audit's
change to make.

---

## 6. Live provider validation matrix

Nothing in this column has ever been exercised against a real counterpart.
A fixture is not a live-validated integration.

| provider | contract | wire | class |
| --- | --- | --- | --- |
| ContactOut | proven offline | never called | **B** live read validation required |
| AI Ark | proven offline | never called | **B** |
| Reoon | proven offline | never called | **B** |
| Deliverable | request proven; **response shape undocumented** | never called | **B**, and the top blocker. `verify()` refuses to spend a credit until one real answer is read |
| Apify | proven offline, SSRF-guarded | never called | **B** |
| EmailBison | read contract proven; payloads built and asserted | never posted | **C** live write validation required |
| HeyReach | same | never posted | **C** |
| Slack — posting | outbox recorded and routed | never posted | **C** |
| Slack — interactions | verified, deduplicated and applied over real HTTP in tests | no request from Slack has ever arrived | **C** |
| MX screening | hand-written DNS client, correct against recorded responses | never run against a live resolver | **B** |
| Email sending | — | — | **E** blocking: refused in code |
| LinkedIn sending | — | — | **E** blocking: refused in code |
| Provider tag sync | outbox correct | `tagsync.send` refuses unconditionally | **E** |

### Capability classes

**A — proven locally end to end.** CSV import and normalisation; identity
and deduplication; segmentation; hygiene and suppression; ICP
qualification (with review); cadence expansion, arms and exposure; copy
variants through to payload and attribution; claim licensing; campaign QA;
approval and fingerprinting; the eligibility gate; pre-send recheck;
reply normalisation, pause-before-classify and account policy; revival
verdicts; multi-tenancy and RBAC; the audit log; reporting and the client
PDF; the kill-switch layers.

**B — live read validation required.** Every provider read above.

**C — live write validation required.** EmailBison, HeyReach and Slack
writes.

**D — partial, not pilot blocking.** The copy experiment screen; the
cadence experiment screens that do not exist; discovery, which has no
source connected; the scheduler and reply poller, neither of which exists.

**E — blocking a first pilot.** Production authentication. Email sending.
LinkedIn sending. Provider tag sync.

---

## 7. Verdicts

### 0. The deployment proved on a fresh clone

Before the verdicts, the thing they rest on. The repository was cloned to
an empty directory - no `work/`, no `out/`, no environment, no setup step -
and the four states were exercised against the shipped configuration:

| what was run | result |
| --- | --- |
| the `Procfile` command verbatim, `--demo --host 0.0.0.0 --port 8799` | serves; `/healthz` answers `{"ok": true, "demo": true, "live_sending": false}` |
| the same command **without** `--demo` | **refused**: "refusing to bind 0.0.0.0 ... anything that can reach this port is a super admin" |
| `APP_MODE=production`, empty environment | **refused**, naming `SESSION_SECRET, AUTH_PROVIDER, DATABASE_URL` |
| `APP_MODE=production` with all three set | **still refused**, on the mechanism: "this build signs in by picking an email from a list" |
| loopback, no `--demo`, real state | serves, unchanged. The operator's own machine is the design |

### 0b. The demonstration is deployed

Done on 2026-09-02, from commit `a2c97f0`, following §8 below.

| | |
| --- | --- |
| URL | https://resonate-demo-production.up.railway.app |
| Railway project | `resonate-demo` · `19f19d96-6990-4f60-aed6-51a0d74f09e2` |
| What was uploaded | `git archive HEAD` — the committed tree only. No `.git`, no `work/`, no `out/`, 6.7 MB |
| Runtime the platform installed | **CPython 3.14.6**, resolved from `.python-version`, attestations verified. The pin held; nothing was silently downgraded |
| Dependencies installed | none. `pip install -r requirements.txt` had nothing to do, which is the claim in §1 surviving contact with a real build |
| Environment variables set | **none.** Only Railway's own `RAILWAY_*`. No `APP_MODE`, no `SESSION_SECRET`, no provider key, no `SLACK_LIVE` |

**Verified on the running instance, not locally:**

| check | result |
| --- | --- |
| `/healthz` over TLS | `{"ok": true, "demo": true, "live_sending": false}` |
| Chrome on every page | `Live sending **disabled**` · `DEMO` |
| Configuration component | `healthy · mode demo` |
| Operator screens | 43/43 answered 200 over HTTPS |
| Authorization, 5 roles | super admin 200 throughout; `/admin*` 404 for everyone else; viewer 403 on `/settings` and `/companies`, 200 on reporting |
| Unauthenticated deep link | `/companies` → 303 to `/login` |
| Providers | all eight `not set` / `unconfigured`. Nothing claims a provider is healthy, and Deliverable's live contract still reads `never` |
| Scheduler, reply poller | both reported `not running` |
| Redeploy and recovery | second deployment reached SUCCESS, previous one removed, health 200 throughout the swap |
| Restart semantics | `sessions` returned to 0 and the estate rebuilt — demo state is per process, exactly as `PRODUCT-GAPS.md` §6 classifies it |

**One caveat worth knowing before somebody reads the dashboard.** Railway
names its default environment `production` and injects
`RAILWAY_ENVIRONMENT=production`. That is Railway's word, not ours: this
application reads `APP_MODE`, which is unset, so it is in demo mode and
says so on every page. The two words meeting on one screen is the kind of
thing that gets misread at a glance.

**Not done, and deliberately.** §8 step 6, the `app.resonategroup.co`
record: that is a DNS change on the domain the agency's own marketing site
and email authentication live on, and it is not an action this session
takes.

### 1. Local release candidate — **GO**

The suite is green, the offline harness reaches nothing, every mutation is
caught, a fresh clone starts with no setup at all, all 47 navigation entries answer
correctly for all five roles across 235 requests, a client viewer holding a
valid CSRF token is refused every write behind a page they may read, all
four PDF templates render without leaking a planted credential,
and everything that cannot be proven locally is named rather than rounded
up.

### 2. Online deployment — **GO for the demonstration. NO-GO for the product.**

This is one verdict with two halves and it is the most important line in
this document.

**The demonstration may go online now.** `--demo` points every state file
at a throwaway directory and installs fictional companies on `.test`
domains before the process can read a real client file. Publishing it
leaks nothing that exists, proves the platform, the build, the health
check, the domain and the rollback, and gives the agency a URL to show a
prospect. §8 is the runbook and it should take under an hour.

**The product may not.** Signing in is picking an email out of a list, so
an instance holding Productive's real audience would be readable and
mutable by anyone who found the URL. That is deployment blocker 1 in
`PRODUCTION-READINESS.md` and it is now enforced rather than described:
the process refuses. Two things must happen before this half becomes GO,
and the first is a decision nobody has made yet.

- **An authentication decision, then an implementation.** Password,
  identity provider, or something else — `AUTH_PROVIDER` was reserved for
  a provider and the shape was never chosen. This is the one open question
  in this document that is not a task.
- **A persistent volume**, with `QUEUE` pointed at it, or the database
  migration. Without one, every record is lost on the next deploy.

### 3. Live Productive pilot — **NO-GO**

Expected, and correct. Nothing here can send: `push.run(live=True)` raises
and there is no code path to either provider. Beyond that, every provider
in §6 is unvalidated on the wire, no process polls for replies, and
Deliverable's response shape has never been read.

`LIVE-VALIDATION-PLAN.md` is the ordered sequence. `GO-LIVE-CHECKLIST.md`
Part D is the client's own sign-off. Each stage is a separate human
decision and none of them is made by this repository.

---

## 8. Tomorrow's runbook — the demonstration deployment

Written for somebody who is not deeply technical. Every step has an
expected result and a stop condition. **Nothing in this runbook sends
anything, spends a credit, touches a provider or exposes real data.**

**Steps 1-5 and 7 were carried out on 2026-09-02 and their results are in
§0b.** What is left is step 6, the DNS record, which is a human decision
about the agency's own domain. The runbook is kept in full because it is
also the procedure for the next environment.

### Before you start

- [ ] `git log --oneline -1` matches §1's commit
- [ ] `git status --short` shows only `AGENTS.md`
- [ ] `py -m unittest discover -s tests -q` is green

### Step 1 — create the service

**Do.** In Railway, New Project → Deploy from GitHub repo → this
repository, `master`.

**Expect.** The build detects Python from `requirements.txt`, installs
nothing, and finishes in seconds. `railway.json` supplies the start
command, the health check and one replica.

**Stop if.** The build cannot supply Python 3.14. Do not silently accept
another version: the suite has never run on one. Either pin the platform's
available version in `.python-version` *and re-run the full suite on it
first*, or use a Docker image that has 3.14.

### Step 2 — do not set any environment variables

**Do.** Nothing. Leave the service's variables empty.

**Expect.** This is correct and deliberate. Demo mode needs no
credentials, and a variable set now is a variable somebody later assumes
is doing something.

**Stop if.** You feel the need to set `APP_MODE=production`. It will
refuse to start, on purpose. §7.

### Step 3 — deploy and watch the health check

**Do.** Deploy. Watch the deploy log.

**Expect.** The log prints the banner: the URL, `Demo mode: enabled`,
`Live sending: disabled`, the throwaway store path, and the nine sign-in
addresses. The platform's health check hits `/healthz` and gets
`{"ok": true, "demo": true, "live_sending": false, "sessions": 0}`.

**Stop if.** The log says `refusing to bind` — the start command lost
`--demo`. Restore it from `railway.json`; do not remove the refusal.

### Step 4 — sign in and walk the estate

**Do.** Open the URL. Sign in as `root@resonate.test`. Then again in a
private window as `client@productive.test`.

**Expect.** As root: every workspace, the admin screens, System health. As
the client viewer: no `/admin` (404, not 403 — a refusal that confirms
existence is a disclosure), no `/settings` (403), and reporting scoped to
their own workspace. Every page carries **Live sending disabled** and
**DEMO** in the top bar.

**Stop if.** The client viewer can reach `/admin`. That is a tenancy
failure and it stops the deployment; report it, do not work around it.

### Step 5 — prove the demonstration is a demonstration

**Do.** Open System health (`/admin/health`) as root.

**Expect.** Scheduler and Reply poller both reported as not running.
Slack unconfigured. Every provider's live contract shown honestly, with
Deliverable marked unvalidated.

**Stop if.** Anything claims a provider is healthy. Nothing in this build
calls a provider, so health would be invented.

### Step 6 — the domain, and only the subdomain

**Do.** Add `app.resonategroup.co` in Railway, then one CNAME at the DNS
provider.

**Expect.** TLS issued by the platform. The marketing site at the apex is
untouched.

**Stop if.** You are about to edit the apex, the `www` record, or any MX
or TXT record. Do not. The agency's own email authentication lives there.

### Step 7 — prove rollback before you need it

**Do.** Redeploy the previous build from the platform's deploy history.

**Expect.** It comes back. There is no database and no artefact to
reconcile.

**Stop if.** It does not. A rollback discovered during an incident is not
a rollback.

### Then stop

That is the whole deployment available today. **Do not** set provider
credentials, set `SLACK_LIVE`, create a provider campaign, import a real
audience, or point this instance at real data. Everything past here is
`LIVE-VALIDATION-PLAN.md`, one stage at a time, each with its own
authorisation:

| stage | what | who decides |
| --- | --- | --- |
| 5.1 | production authentication — **the next real decision** | the agency |
| 1 | provider reachability, read-only and free | the agency |
| 2.1 | Deliverable's response shape, one credit, deliberately | the agency |
| 3 | Slack, read then write, throwaway channel first | the agency |
| 4 | EmailBison and HeyReach, one object at a time | the agency |
| — | lifting the refusal in `push.run` | a code change and a review |

---

## 9. The first Productive pilot — prepared, not authorised

Its purpose is to validate the system, not to optimise a funnel. Every
number below is deliberately small enough that a mistake is recoverable
and large enough to prove the path.

| | |
| --- | --- |
| Audience | 10–15 companies, 20–30 contacts. `PILOT-PLAN.md` |
| Selection | ICP `accept` only. `review` and `unknown` are real answers and spend nothing |
| Channels | **email only.** Adding LinkedIn doubles the provider surface on the first run |
| Senders | **one** human sender identity, one inbox. Multi-sender is built and reported; it is not what a first run should be proving |
| Cadence | **one arm.** No experiment. An arm the reply cannot be attributed to is worse than no arm |
| Copy | **one variant per step.** Five variants across thirty contacts cannot separate anything, and the evaluator will correctly refuse to say so |
| Drafts | written by a person. No model ships with this repository |
| Volume cap | the workspace's daily cap, set before approval, not after |
| Approval | a named human, after `campaignqa` passes. An edit invalidates it |
| Pre-send | eligibility re-derived at payload time from primary state |
| Monitoring | the operations Slack channel, and `/health` |
| Replies | handled by a person. **Nothing polls**, so nothing will notice a reply on its own — this is the single most important sentence in this section |
| Stop | freeze the campaign; any reviewer may |

**Success is not a reply rate.** It is: every contact who received
something was eligible at the moment it was built; every confirmed touch
matches a real provider event; every reply reached canonical state before
anybody was told; and the report's numerators and denominators are the
events, not the plan.

**Deliberately not in the first pilot:** four cadence arms, five copy
variants, multiple senders, LinkedIn, discovery, revival, and provider tag
sync. All exist. None of them is what a first live run should be risking.
