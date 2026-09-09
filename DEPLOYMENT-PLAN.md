# Deployment Plan

How Resonate Outbound OS gets hosted, when that is authorised. **Nothing here
has been executed.** No infrastructure exists, no DNS has been touched, no
service has been created.

Read `PRODUCTION-READINESS.md` first: it lists what is not ready. This document
assumes those blockers are cleared and describes the shape of the deployment,
not permission to make it.

---

## 1. What is being deployed

One Python application with **zero third-party dependencies**. No build step,
no bundler, no `node_modules`, no `requirements.txt`. That is unusual and it is
the deployment's biggest advantage: the build stage is copying files, and there
is no dependency tree to audit, pin or patch.

It is also the deployment's main constraint. `http.server` is not a production
web server. It must sit behind a reverse proxy that terminates TLS, and the
process must never be exposed directly.

---

## 2. Target architecture

```
                    ┌──────────────────────────────┐
   app.resonate     │  TLS / reverse proxy         │
   group.co  ─────► │  (platform-provided)         │
                    └──────────────┬───────────────┘
                                   │
                    ┌──────────────▼───────────────┐
                    │  web            1..n         │  request/response only
                    └──────────────┬───────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              │                    │                    │
     ┌────────▼────────┐  ┌────────▼────────┐  ┌────────▼────────┐
     │  PostgreSQL     │  │  worker  1..n   │  │  scheduler  1   │
     │  state          │  │  jobs           │  │  cadence, polls │
     └─────────────────┘  └─────────────────┘  └─────────────────┘
              │
     ┌────────▼────────┐
     │  object storage │  (only if reports are archived; see §6)
     └─────────────────┘
```

### Services

| Service | Count | What it does | Exists today |
| --- | --- | --- | --- |
| web | 1+ | Serves the app. Stateless once the database exists. | Yes |
| worker | 1+ | Runs enrichment, verification and research jobs. | **No** — jobs run in the web process |
| scheduler | exactly 1 | Advances cadence, polls providers for replies. | **No** |
| PostgreSQL | 1 | All state. | **No** — state is JSONL |
| Redis | 0 or 1 | Only if the queue needs it; see §4. | **No** |
| Object storage | 0 or 1 | Only if PDFs are archived; see §6. | **No** |

**The web service cannot be scaled past one instance until the database
migration is done.** Today's state is JSONL files guarded by a file lock. Two
web processes on a shared volume will corrupt it. This is not a tuning
concern - it is a correctness one, and it is the single hard gate on
horizontal scale.

---

## 3. Platform

Vendor-neutral by design; nothing in the repository requires a particular host.
Two reasonable paths:

### Railway or Render

Fits this application well. Both give a managed Postgres, a private network
between services, per-service environment variables, health checks and
rollback. Deploy from the repository; the build is "copy the files", so build
times are seconds.

Four files in the repository root exist for this and nothing else:

| file | why it is there |
| --- | --- |
| `requirements.txt` | empty of packages, and not redundant: a platform identifies a Python application by finding one. Without it the build does not know what it is building |
| `.python-version` | `3.14`, the only interpreter this repository has ever been run or tested on. A build that cannot supply it should fail loudly rather than silently pick another |
| `Procfile` | the start command |
| `railway.json` | the same start command, the health check path, and `numReplicas: 1` |

`tests/test_deployment_config.py` puts every one of those through the
parser and the startup refusal `main()` itself uses. A start command that
this build would refuse fails a test rather than a deploy.

- web: start `python -m src.web --demo --host 0.0.0.0 --port $PORT`
- worker: a separate service running the job runner
- scheduler: a cron-style service, or the platform's own scheduler
- database: the managed Postgres add-on

**`--demo` is in that command and is not a placeholder.** A non-loopback
bind is refused unless the estate is fictional - see §2b - so today the
only thing this repository can publish is the demonstration. Removing
`--demo` does not deploy the product; it fails to start.

### 2b. What may be published, and what may not

`web.app.check_configuration` reads one fact - does signing in prove who
somebody is - and refuses accordingly.

| state | what happens |
| --- | --- |
| `APP_MODE=production`, no `AUTH_PROVIDER` | refuses, naming every missing variable |
| `AUTH_PROVIDER` set to anything but `oidc` | refuses. A name is not an implementation, and falling back to demo here would be unauthenticated access reached by way of a variable set to turn authentication on |
| `AUTH_PROVIDER=oidc`, partly configured | refuses, naming which part |
| `APP_MODE=production`, no `QUEUE` | refuses. State would land on a disk that disappears - see §2c |
| any non-loopback bind, no provider, no `--demo` | refuses. Whoever reaches the port could select the super admin from a list |
| a non-loopback bind with `--demo` | **allowed.** Every state file is pointed at a throwaway directory and a fictional estate is installed before the process can read a real client file |
| **a non-loopback bind with a configured provider** | **allowed.** This is the product, and it is what the owner actions in `PRODUCTION-AUTH.md` §5 unlock |

So there are two deployments, and only one of them exists today:

**The demonstration.** Publishable now. Fictional data, no volume, no
database, no secrets, one replica. Useful for a client demo and as proof
that the platform, the build, the health check and the rollback all work.

**The product.** Not publishable yet. It needs an identity provider
(`PRODUCTION-AUTH.md` §5) and a persistent volume.

### 2c. Persistence: a volume, and not a database

The decision follows the code rather than the roadmap. **There is no SQL
backend in this build** - no driver, no schema, no query, nothing that
opens a connection. `DATABASE-MIGRATION.md` is a plan that has not been
executed. So a Postgres instance provisioned today would sit empty beside
the real state on disk, and the only thing it would change is the bill.

State is JSONL under an advisory lock, single-writer by construction.
The correct production shape is therefore **one service, one replica, one
mounted volume**:

| | |
| --- | --- |
| Volume mount | `/data` |
| `QUEUE` | `/data/work/queue.jsonl` |
| Everything else | follows automatically - campaigns, workspaces, jobs, senders, notifications, the audit log, the tag outbox, signals, discovery and the rest all default to the queue's directory |
| Replicas | **exactly 1.** Two writers on one volume corrupt it; that is `PRODUCT-GAPS.md` §5 and it is a correctness gate, not a tuning one |
| `DATABASE_URL` | **do not set, and do not provision one** |

`QUEUE` is `PRODUCTION_ONLY` in `src/config.py`, so **production refuses
to start without it.** That refusal is the point: a container filesystem
is ephemeral, and unset the queue lands somewhere that is deleted on the
next deploy - silently, because an empty store is a *valid* store and
nothing downstream can tell a fresh workspace from one whose records were
thrown away.

It was the other way round until the release audit: `DATABASE_URL`
blocked startup while nothing read it, and `QUEUE`, which decides whether
client data survives, was optional. `tests/test_persistent_volume.py`
puts a populated estate through a mounted directory and checks the bytes
landed there, that a stale override cannot quietly point one file
somewhere else, and that the state is still readable after the process is
replaced.

### A single VM

Also fine, and cheaper. systemd units for web, worker and scheduler; nginx or
Caddy in front for TLS; Postgres on the same box or managed. More operational
work, fewer moving parts.

Pick one. Do not build an abstraction over both.

---

## 4. The queue

The current job model is a cursor on a job row: `run_step` advances a slice and
records where it got to, so a crash resumes rather than restarts. That model
survives the move to Postgres unchanged, with `SELECT ... FOR UPDATE SKIP
LOCKED` doing what the file lock does now.

**Redis is not required.** Add it only if a measured need appears - genuinely
concurrent workers contending, or scheduled work that needs sub-minute
precision. A queue nobody needed is a service somebody has to operate.

---

## 5. Configuration and secrets

Every variable is named in `config/.env.example` and classified in
`src/config.py`. To read what a mode would demand, without starting
anything:

```
python -m src.config --mode production
```

Production **fails closed**, and until the release-candidate audit it only
said so. `config.verify()` had a docstring reading "called at startup" and
no caller anywhere; the process started in any mode with any environment.
`web.app.check_configuration` calls it now, before anything binds, so a
missing `SESSION_SECRET`, `AUTH_PROVIDER` or `DATABASE_URL` is a refusal
with a message naming what is absent.

Passing that check is not permission to run in production. §2b is the
second refusal and it is the one that matters: there is no production
authentication, so production mode does not start at all.

Secrets live in the platform's secret store, never in the repository and never
in an image layer. `config/.env` is gitignored; the deployment does not use it.

`SESSION_SECRET` must be stable across deploys. It is generated per process in
demo mode, which is why demo sessions do not survive a restart; a production
process that did that would sign everybody out on every deploy.

---

## 6. Report storage

Client reports are **re-rendered on download** from stored settings; no PDF
bytes are archived. That is deliberate - see `src/reports.py` - and it means
**object storage is not required**.

Add it only if a signed, immutable copy of what a client was sent becomes a
requirement. It would be a real change in meaning: today, a corrected figure
corrects the document, and an archive would preserve a number the system no
longer stands behind.

---

## 7. Domain

| Name | Points at | Change |
| --- | --- | --- |
| `resonategroup.co` | the existing marketing site | **none** |
| `www.resonategroup.co` | the existing marketing site | **none** |
| `app.resonategroup.co` | this application | one new record |

One record, on a subdomain. Do not touch the apex, the `www` record, or any
existing MX or TXT record: the marketing site and the agency's own email
authentication live there, and an outbound platform breaking its own company's
SPF would be a memorable way to start.

TLS is issued by the platform for the subdomain. HSTS on the subdomain only,
until somebody has decided about the apex.

---

## 8. Deploy sequence

Step 0 is the only one available today and it is worth having on its own:
**deploy the demonstration.** `RELEASE-CANDIDATE.md` is the ordered
runbook. It proves the build, the health check, the rollback and the
domain with nothing real at stake, and it is finished before authentication
exists. Steps 1 onwards all wait on `LIVE-VALIDATION-PLAN.md` §5.1.

1. Provision Postgres. Run the migration from `DATABASE-MIGRATION.md` against
   an empty database. Confirm the acceptance checks.
2. Deploy **web only**, one instance, with the worker and scheduler disabled.
   Confirm `/healthz`, sign in, read a dashboard.
3. Deploy the worker. Run one job. Confirm it is picked up outside the web
   process and that the web process no longer runs it.
4. Deploy the scheduler. Confirm it advances nothing it should not - cadence
   timing only, no sending.
5. Point `app.resonategroup.co` at the web service. Confirm TLS.
6. Work `LIVE-VALIDATION-PLAN.md` from stage 1. **Sending stays disabled
   throughout.**
7. `GO-LIVE-CHECKLIST.md` gates anything beyond that.

Steps 1-5 are a deployment. Step 6 is a separate authorisation. Step 7 is
another.

---

## 9. Health checks and monitoring

- **Liveness** — `GET /healthz`. Already implemented; returns process state
  and never touches a provider.
- **Readiness** — should additionally assert the database is reachable, once
  there is one.
- **What to alert on** — see `PRODUCTION-READINESS.md` §Monitoring. The
  short list: failed jobs, reply-poller lag, Slack delivery failures, report
  generation failures, approval age, queue depth.
- **What not to alert on** — anything derived from a provider being
  unconfigured. In a build where nothing sends, that is the expected state and
  paging on it trains people to ignore the pager.

---

## 10. Rollback

The application rolls back cleanly: it is stateless once the database exists,
and there is no build artefact to reconcile.

The database does not. Migrations must be additive - add a column, backfill,
switch reads, drop later - so that rolling the application back does not meet
a schema it cannot read. A destructive migration and a rollback are not
compatible, and the way that is discovered is during an incident.

Rollback procedure:

1. Redeploy the previous release of web, worker and scheduler.
2. Do **not** roll the database back. Additive migrations are forward-safe.
3. If a migration must be reversed, restore from backup and accept the data
   loss window knowingly - see `PRODUCTION-READINESS.md` §Backups.

---

## 11. Backups

- Postgres: managed automated backups, plus point-in-time recovery. Test a
  restore before go-live; an untested backup is a hope.
- Configuration: in the repository, except secrets.
- Secrets: in the platform's store, with a sealed offline copy held by two
  people.
- Reports: nothing to back up - they re-render.

---

## 12. What this plan does not authorise

- enabling live sending
- posting to a real client's Slack channel
- mutating an EmailBison or HeyReach campaign
- spending a provider credit
- touching the apex domain or any existing DNS record

Each of those has its own gate in `LIVE-VALIDATION-PLAN.md` and
`GO-LIVE-CHECKLIST.md`.
