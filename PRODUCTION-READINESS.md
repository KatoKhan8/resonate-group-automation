# Production Readiness

An honest inventory before anything reaches a real person.

Four statuses, used strictly:

| Status | Means |
| --- | --- |
| **READY** | Built, tested, and the test would fail if it broke |
| **LIVE VALIDATION REQUIRED** | Built and tested offline. Never exercised against the real thing |
| **NOT READY** | Does not exist, or exists in a form production cannot use |
| **OPTIONAL** | Would be good. Nothing is blocked on it |

**A mock test passing is not READY** for anything that talks to the outside
world. Where the only evidence is a recorded contract, the status is LIVE
VALIDATION REQUIRED, however green the suite is.

**The sender is off.** `push.run(live=True)` raises `LiveSendNotEnabled`.
`slack.post` raises `SlackPostingNotEnabled` unless `SLACK_LIVE` is set.
Every test runs with the socket layer blocked. Turning either off is gated by
`GO-LIVE-CHECKLIST.md`.

Related: `LIVE-VALIDATION-PLAN.md` (what to prove, in what order),
`DEPLOYMENT-PLAN.md` (how it gets hosted), `DATABASE-MIGRATION.md` (the
storage change), `PILOT-PLAN.md` (the first real campaign).

---

## 1. The two lists that matter

Deployment readiness and live-sending readiness are different questions, and
conflating them is how a system gets deployed and then quietly switched on.

### Blockers before deployment

Nothing may be hosted until every one of these is cleared.

1. ~~**Production authentication.**~~ **Implemented.** OpenID Connect,
   authorization code with PKCE, no third-party dependency, in
   `src/web/oidc.py` and `PRODUCTION-AUTH.md`. Demo sign-in still exists
   and is unreachable whenever `AUTH_PROVIDER` is set.

   What remains is not code: an OAuth client has to be created in Google
   Workspace or Entra, and no real provider has ever answered this client.
   `PRODUCTION-AUTH.md` §5 says exactly what to create and what to return.
   Until then the classification is NEEDS LIVE CONTRACT VALIDATION rather
   than READY, for the same reason every other integration in
   `LIVE-READINESS.md` is: a fake provider on loopback proves the code, not
   the counterpart.

   The original entry said `APP_MODE=production` refused to start without
   `AUTH_PROVIDER`. It did not - nothing called `config.verify()` - and
   `AUTH_PROVIDER` was a name that satisfied a check without implementing a
   mechanism. `web.app.check_configuration` now runs the environment check
   and then asks whether the mechanism exists, and `AUTH_PROVIDER=oidc`
   with the four settings behind it is what makes the answer yes. See
   `DEPLOYMENT-PLAN.md` §2b.
2. **Production database.** State is JSONL guarded by a file lock. It is
   single-writer by construction, so the web service cannot run more than one
   instance. `DATABASE-MIGRATION.md` is the plan; it has not been executed.
3. ~~**`SESSION_SECRET` handling.**~~ **Withdrawn as a blocker, and the
   reason is worth keeping.** It was required in production and read by
   nothing: sessions are opaque tokens held in this process, so there was
   no cookie to sign. A required variable that nothing consumes is the one
   an operator sets to clear an error, and clearing it changes nothing.

   What is real, and is `PRODUCT-GAPS.md` §6 rather than a
   deployment blocker: **a restart signs everybody out**, and two processes
   cannot share a session. That is the same trigger as the database
   migration, not a separate one. The variable stays named for the session
   store a second process would need.
4. **A reverse proxy terminating TLS.** `http.server` must never be exposed
   directly.
5. **A verified backup restore.** Not a configured backup - a restore that
   somebody performed and checked.
6. **Monitoring and alerting** for the list in §8.

### Blockers before live sending

Everything above, plus:

7. **Deliverable's wire contract validated** against a live answer, including
   a known-bad address. Until then the verification waterfall's final step is
   written against an assumption. See `LIVE-VALIDATION-PLAN.md` §2.1.
8. **A worker process.** Jobs currently run inside the request process; a
   long enrichment run blocks a web worker.
9. **A scheduler.** Nothing advances cadence timing. Sending without one means
   a person triggering every step.
10. **A reply poller running.** Inbound events are applied when handed to
    `src/inbound.py`. No process fetches them, so nothing would notice a reply.
11. **Slack channel isolation proven live**, with throwaway channels, before
    any real client channel is mapped.
12. **Provider identifier round-trips confirmed** on EmailBison and HeyReach.
    If our identifiers do not survive, replies cannot be attributed.
13. **Every gate in `GO-LIVE-CHECKLIST.md` Part D signed** — the client's
    agreement, the sending domains, and that every sender persona is a real
    consenting person.
14. **An unsubscribe mechanism.** Unsubscribes are honoured from replies and
    stored; there is no hosted link, and some jurisdictions require one.

---

## 2. Application

| Area | Status | Evidence |
| --- | --- | --- |
| Append-only state, atomic writes | READY | `tests/test_store.py`, crash/resume in `tests/test_resilience.py` |
| One authority on `sendable` | READY | `src/verification.py`, recomputed from evidence on every ask |
| Mandatory double verification | READY | two independent providers required; `VERIFICATION.md` |
| MX screening before paid verification | READY | a blocked gateway costs no verifier credit |
| MX / gateway filtering | READY | `tests/test_mx.py`; Google and Microsoft never blocked |
| Centralised eligibility | READY | `src/eligibility.py`, 33 stable reason codes |
| Identity and cross-client dedup | READY | strong identifiers only; names never merge |
| Cadence state machine | READY | a sent step cannot return to sendable |
| Campaign fingerprint / approval binding | READY | changing launch-sensitive state invalidates approval |
| Pre-send QA with hard blockers | READY | a blocker is never averaged away by a good score |
| Idempotency on every expensive act | READY | `push_id`, `provider_event_id`, `evidence_id`, interaction id |
| Cost caps before fan-out | READY | credits capped before any paid call |
| 5,000-domain throughput | READY | full offline pipeline well inside budget, linear |
| Per-channel eligibility | READY | `src/channels.py`; a lost channel never drops a contact |
| ContactOut-first waterfall | READY | a fallback without an accepted reason is refused |
| Personalisation quality bands | READY | five components, a written rule, no opaque score |
| Sender identity and sticky assignment | READY | `src/senderidentity.py`, `src/assignment.py` |
| Cross-channel confirmed-touch gate | READY | `src/touch.py`; a planned step can never be referenced as sent |
| Slack routing, two levels, no fallback | READY | `SLACK-NOTIFICATIONS.md`, `tests/test_notify*.py` |
| Client reports and PDF generation | READY | `src/pdf.py`, `src/clientreport.py`, `tests/test_client_reports.py` |
| Web application | READY | 50+ routes, permission table checked before every handler |
| Workspace tenancy | READY | `tests/test_tenancy_penetration.py`; forged ids per object kind |
| RBAC | READY | 5 roles, 21 permissions; read table swept against every handler, and an invariant walks every POST branch |
| Audit trail | READY | `src/audit.py`; says what it cannot answer |

---

## 3. Data and storage

| Area | Status | Note |
| --- | --- | --- |
| JSONL state with advisory locking | READY *for one process* | correct and tested; single-writer by construction |
| Multi-process writes | NOT READY | the hard gate on horizontal scale. `DATABASE-MIGRATION.md` |
| PostgreSQL | NOT READY | planned, not executed |
| Backups | NOT READY | no production database exists to back up |
| Report storage | READY | nothing to store: PDFs re-render from stored settings |
| Data retention policy | NOT READY | see §9 |
| PII deletion workflow | NOT READY | records are dropped with a reason, never deleted. A real erasure request has no procedure |

---

## 4. Authentication and authorisation

| Area | Status | Note |
| --- | --- | --- |
| RBAC model | READY | role resolved per request, never stored in the session |
| Workspace tenancy | READY | `Repo.for_user`; a slug in a URL reaches a membership check and no further |
| 404-not-403 on cross-tenant reads | READY | a refusal that confirms existence is a disclosure |
| Privilege escalation guards | READY | a workspace admin cannot grant themselves super-admin |
| Session handling | READY *for one process* | in-memory opaque tokens; `HttpOnly` and `SameSite=Strict` always, `Secure` once a provider is configured. A restart signs everybody out |
| Production authentication | LIVE VALIDATION REQUIRED | OIDC implemented and proven against a fake provider; no real one has answered. `PRODUCTION-AUTH.md` |
| Refusing to run without it | READY | `web.app.check_configuration`: production mode and any non-loopback bind refuse unless the estate is fictional. Six mutations in the audit |
| Secure cookies / HSTS | NOT READY | needs TLS, which needs a deployment. Deliberately not added ahead of one: a `Secure` cookie on a plain-HTTP loopback signs the operator out of their own machine, and the deployment that needs it is the same deployment that needs authentication |
| CSRF | READY | token per session, checked on every write |
| Rate limiting | NOT READY | see §10 |

---

## 5. Providers

| Provider | Offline contract | Live contract | Status |
| --- | --- | --- | --- |
| ContactOut | READY | historically exercised | LIVE VALIDATION REQUIRED |
| AI Ark | READY | historically exercised | LIVE VALIDATION REQUIRED |
| Reoon | READY | documented, matches cassette | LIVE VALIDATION REQUIRED |
| **Deliverable** | READY | **never** | **NOT READY** — see below |
| EmailBison | READY (reads) | reads only | LIVE VALIDATION REQUIRED |
| HeyReach | READY (reads) | reads only | LIVE VALIDATION REQUIRED |
| Apify | READY | not run in this build | LIVE VALIDATION REQUIRED |
| Slack | READY | never posted | LIVE VALIDATION REQUIRED |

**Deliverable is the one that is NOT READY rather than merely unvalidated.**
Its transport is documented and is already the adapter's default. Its
*response* is not: no field names, no status values, read from nothing.
`verify()` refuses to spend a credit until one real answer has been read and
the normaliser checked against it. The failure mode if that check is skipped is
the worst one available - an invalid address classified valid, and a contact
that should have been held becoming sendable.

`/admin/health` reports this per provider, and never uses the word "healthy"
for something nothing has called.

### Specific unknowns

| Area | The unknown |
| --- | --- |
| EmailBison sending | The send path has never been called |
| HeyReach lead identity round-trip | `customUserFields` do not round-trip through any readable endpoint. Our identifiers are sent regardless; whether they come back is unobserved |
| Provider rate limits | Documented limits are respected. What happens *at* the limit is unknown |
| Reply volume at scale | Polling handles the pages it was shown. A thousand replies a day against live pagination has not been simulated |
| Deliverability | Outside this system entirely. Warmup, domain reputation and content |
| Verifier disagreement rate | The matrix says what happens. Nobody knows how often that row fires on real data |

---

## 6. Operations

| Area | Status | Note |
| --- | --- | --- |
| Jobs with resumable cursors | READY | survives a crash; resumes rather than restarts |
| Worker process | NOT READY | jobs run in the request process |
| Scheduler | NOT READY | nothing advances cadence timing |
| Reply poller running | NOT READY | the transport exists; no process runs it |
| Health endpoint | READY | `/healthz`, touches no provider |
| System health console | READY | `/admin/health` |
| Configuration validation | READY | `python -m src.config`; production fails closed |
| Structured observability | READY *locally* | `src/observability.py`; counters, no secrets |
| Log aggregation | NOT READY | needs a deployment |

---

## 7. Security

Reviewed deliberately. Findings and non-findings both.

| Area | Status | Evidence |
| --- | --- | --- |
| Credentials never in source, tests, fixtures, docs or state | READY | `tests/test_secrets.py`, `tests/test_minimization.py` |
| Credential values never rendered | READY | planted-canary sweep across every screen every role can reach |
| Credential *names* still reported | READY | presence by name is a feature; the sweep is value-based so it does not punish it |
| CSV injection | READY | `src/export.py` guards every cell; a test asserts no second writer exists |
| HTML injection | READY | every interpolation escapes; a `<script>` company name renders inert |
| Cross-tenant reads | READY | forged real ids per object kind, `tests/test_tenancy_penetration.py` |
| Cross-tenant writes | READY | pause, ICP decision, approval, reassign, policy — all asserted unchanged |
| Slack signature and replay | READY *offline* | HMAC, freshness window, constant-time compare, interaction dedup |
| Slack signature, live | LIVE VALIDATION REQUIRED | Slack's real signing has never been received |
| SSRF in research | READY | Apify isolation, bounded fetches |
| Network egress in tests | READY | `tests/offline.py`; loopback only |
| Security headers, CSP | NOT READY | needs TLS and a deployment |
| Rate limiting | NOT READY | §10 |
| Dependency vulnerabilities | READY | there are no dependencies |

---

## 8. Monitoring

Nothing is wired up; a deployment needs all of it. Alert on:

| Signal | Why |
| --- | --- |
| Reply poller stopped | somebody answered and nobody was told |
| Failed jobs | work that did not happen |
| Provider failing repeatedly | credits burning on retries, or a silent stall |
| Slack delivery failing | the operations feed is the thing that reports other failures |
| Report generation failing | a client is expecting a document |
| Approval age | a campaign waiting on a person who did not see it |
| Queue depth | work arriving faster than it is done |
| Sender capacity exhausted | outreach silently not going out |

Do **not** alert on a provider being unconfigured. In a build where nothing
sends that is the expected state, and paging on it trains people to ignore the
pager.

---

## 9. Data protection

| Area | Status | Note |
| --- | --- | --- |
| Data minimisation | READY | adapters return trimmed dicts; no raw payload is stored |
| Audit immutability | READY | append-only; no UI workflow rewrites a historic event |
| Retention policy | NOT READY | nothing expires. Contacts, research, reports and audit grow without bound |
| Export on request | PARTIAL | contacts and analytics export; no per-subject export |
| Erasure on request | NOT READY | records are dropped with a reason, never deleted |

No compliance claim is made. These are the mechanics; whether they satisfy a
particular regime is a question for somebody qualified to answer it.

---

## 10. Rate limiting

NOT READY, and worth naming per endpoint:

| Endpoint | Risk |
| --- | --- |
| `/login` | credential stuffing once real auth exists |
| `/reporting/client/generate` | a PDF is CPU work; a loop is a denial of service |
| `/export/*` | large exports |
| Slack interaction callback | replay is handled; volume is not |
| Anything triggering a provider | the expensive one |

Application-level limits are the right layer for the last two; the platform's
proxy can handle the rest.

---

## 11. What does not exist

Named rather than implied, so nobody finds them in week three.

- **No sending.** Deliberate.
- **No webhooks.** Neither provider offers a verifiable one, so polling with
  durable cursors is the transport. A provider limitation, not a gap.
- **No meeting tracking.** Nothing observes a calendar. `meetings` is `None`
  until a human marks one, and no report infers it from a positive reply.
- **No hosted unsubscribe page.** Unsubscribes are honoured from replies and
  stored; there is no link.
- **No automated warmup or sender reputation monitoring.** Senders are assigned
  and capped; their reputation is not watched.
- **No person-level web research runs.** The architecture records an absence
  honestly, and `person_research.available` is false for every record today.
- **No screen-reader audit.** Semantics, contrast and focus states are built
  to; nobody has tested with a screen reader.
- **No automated accessibility check in CI.**

---

## 12. Summary

| | |
| --- | --- |
| **READY** | The engine, the safety rules, the web application, tenancy, RBAC, reporting, PDFs, Slack routing |
| **LIVE VALIDATION REQUIRED** | Every provider, Slack posting, Slack callbacks |
| **NOT READY** | Production auth, database, worker, scheduler, reply poller, backups, monitoring, rate limiting, retention, erasure, Deliverable's contract |
| **OPTIONAL** | Redis, object storage, log aggregation |

The engine is in good shape. What is missing is almost entirely the
infrastructure around it and the one provider contract nobody has read - and
both are named rather than assumed.
