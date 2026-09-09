# Final system integrity audit

One night, one question: **what could make a first Productive pilot
unsafe, and which of those things can be closed locally.**

It is not a re-run of the test suite. The suite was green before this
audit started and stayed green through it, which is the point - every
finding below was invisible to 4,749 passing tests, because every one of
them is a thing that is *written down* rather than a thing that is
*wrong*. A document describing a guard, a variable an operator can set, a
function with a docstring saying when it is called: none of those is
exercised by a test of the system's behaviour, and all of them are read by
somebody who then believes something untrue.

---

## Method

Four passes, in this order, because each narrows the next.

**1. Recover the state rather than trust the brief.** `git log`, `git
status`, no live processes, then the claimed baseline re-run from scratch:
4,749 tests, OK, 793s. `tests.test_mutation_anchors` to prove every one of
the audit's mutations could still fire. The numbers in `MISSION-STATE.md`
were accurate.

**2. Ask what is computed and never read.** A fifteen-line AST script over
`src/`: 1,036 public module-level functions, 16 with zero references
anywhere in `src/`, `tests/` or `tools/`. Then the same question about
configuration: every `os.environ` lookup in `src/`, matched against
`src/config.py`'s declared list and against what any code path actually
consumes.

**3. Walk the deployment as an attacker would.** Not "does it start" but
"what does starting it expose". The application was cloned fresh and
started from the documented command with an empty environment, then swept
over HTTP: all 47 navigation entries as each of the five roles, a client
viewer POSTing to the write paths behind pages they may read, and the four
PDF templates generated with planted provider credentials in the
environment.

**4. Attack every guard that was added.** Eleven deliberate mutations,
each required to fail the intended test for the intended reason, each
followed by a restoration check. Six of them are now permanent entries in
`tools/mutation_audit.py`.

---

## Findings

Classified by what they could cause, not by how hard they were to fix.

### P0 — could cause unsafe send, isolation failure, or material harm

Both of these were latent: they cause nothing while the application runs
on loopback and sends nothing, which is every state it has ever been in.
They become P0 on the day somebody follows the deployment documentation.

#### P0-1. The documented production refusal did not exist

`src/config.py::verify()` carries the docstring *"Raise in production if
something required is missing. Called at startup."*

Nothing called it. Not `src/web/app.py::main()`, not `serve()`, not
anything. `PRODUCTION-READINESS.md` said `APP_MODE=production` "refuses to
start without `AUTH_PROVIDER`", `DEPLOYMENT-PLAN.md` §5 said "production
fails closed", and both described a guard that had never run.

The exposure this guarded is the real one. Signing in is a POST of an
email address: `/login` looks it up in the workspace table and issues a
session. There is no password, no identity provider, no second factor. The
membership table decides what that person may do and is checked on every
request - what nothing checks is whether they are that person. `/login`
renders the list to choose from, and the first entry is the super admin.

**Closed** by `web.app.check_configuration`, called from `serve()` so no
entry point can skip it.

#### P0-2. The documented start command published that console

`DEPLOYMENT-PLAN.md` §3: `python -m src.web --host 0.0.0.0 --port $PORT`.

Following that instruction puts an unauthenticated console that reads
every workspace, pauses campaigns, exports contacts and can spend provider
credits behind a public URL.

**Closed** by the same function: a non-loopback bind is refused unless the
process is serving the fictional estate. `""` is refused with the rest -
`ThreadingHTTPServer(("", port))` binds every interface, and it is 0.0.0.0
spelt in a way that looks like a default.

**Neither fix is authentication.** They are the honest encoding of its
absence, in the shape this repository already uses for `push.run(live=
True)`: refused in code, lifted by a decision and a review rather than by
a flag. One predicate, `security.sign_in_proves_identity()`, is the seam.
When a real provider is wired in it returns True and both refusals lift
together - which is why it is a function returning a constant rather than
two copies of the same fact.

### P1 — could materially break pilot behaviour or an operator decision

#### P1-1. `AUTH_PROVIDER` satisfied the check without implementing anything

Even with the environment check wired in, `AUTH_PROVIDER=okta` would have
passed it and changed nothing about the sign-in form. An operator clearing
a startup error would have produced a *worse* state than the error: a
running production process, and a belief that authentication was on.

**Closed.** Production mode refuses regardless of the environment.
`test_naming_an_auth_provider_is_not_implementing_one` asserts
`config.report()["blockers"] == []` and then asserts the refusal anyway.

#### P1-2. Container state is ephemeral and nothing said so

State is `work/*.jsonl`. A container filesystem is not persistent, so a
deployment without a mounted volume loses every record, campaign, approval
and reply on the next deploy - silently, because an empty store is a valid
store.

**Recorded, not code.** One lever exists and works: `QUEUE` points at the
volume and every other state file defaults to the queue's directory
(`store.STATE_OVERRIDES`, kept complete by `tests/test_invariants.py`).
`DEPLOYMENT-PLAN.md` §2b now says it, and it is a step in the runbook.

### P2 — degraded, and a pilot can operate safely

#### P2-1. A demo fallback on a production path

`api.campaign_experiments` fell through to `web/demovariants.py`'s planted
exposure and outcome totals whenever a campaign had no `cadence_graph`.
Nothing writes `cadence_graph`, so that was every real campaign, always.

The screen captioned the numbers as fictional, which is why this is P2 and
not P1. It was still the wrong default. **Closed**: the fallback takes
`demo` from the process, and a real workspace is told there is no cadence
graph rather than shown somebody else's numbers.

#### P2-2. `WEB_HOST` and `WEB_PORT` were configuration nobody read

Declared in `src/config.py`, reported by the settings screen, consumed by
no code path. The smallest possible instance of this repository's
signature defect, and the one most likely to waste an operator's evening.
**Closed**: `web.app.parser()` reads both, and the flags still win.

#### P2-3. No deployment artifacts existed

No `requirements.txt`, `pyproject.toml`, `Procfile` or runtime pin. A build
platform identifies a Python application by finding one of the first two;
with none present the build fails before it starts. **Closed**, and each
file is asserted against the application rather than read
(`tests/test_deployment_config.py`).

### P3 — polish and debt, recorded rather than fixed

- **`config/.env.example` told the reader to run `python -m src.check
  --config`.** No such flag. It is `python -m src.config`. Fixed, because
  it was one line and the file is the first thing a deploying operator
  reads.
- **Sixteen public functions have zero references anywhere.** Most are
  provider capabilities written ahead of use. One is worth naming:
  `events.pause_company` has a docstring saying "`accountpolicy` decides
  which, and calls this through its own `_hold_account`". It does not -
  `_hold_account` writes `rec["paused"]` itself. Two representations of
  one canonical transition, of which the live one is correct and tested.
  Left alone: deleting it is not this audit's change to make, and the
  docstring is the only thing that misleads.
  **Closed 2026-09-09.** Deleted. Re-running the sweep now finds twelve such
  functions rather than sixteen, and this was the only one that was a trap
  rather than merely unused: the two records differ, because `_hold_account`
  writes `outcome` beside `reason` and the dead one did not. A caller who
  believed the docstring would have produced a pause the audit cannot read.
  `tests/test_account_policy.py::OnePauseImplementation` pins that property
  rather than the absence of a function.
- **`cadencegraph.account_multichannel` imports a production template from
  `web/democadence.py`.** A real template living behind a `demo` prefix is
  a trap for the next reader.
- **`api.system_status` / `api.provider_health` are reachable only through
  `admin_overview`**, while `api.system_health` computes an overlapping
  answer for `/admin/health`. Two paths to one question.
- **The refusal audit writer swallows its own failure.**
  `web.app.Handler._refusal` records that a request was refused, inside a
  `try/except Exception: pass`. This was checked because it is exactly the
  shape the audit was hunting, and it is the opposite: the reasoning is at
  the site, in the docstring - "failing to log must never turn a refusal
  into a 500". That is right. What is left is small and real: if the write
  fails, nothing anywhere says so, and an operator reading the security
  log believes it is complete. One line to stderr would close it. Left
  alone tonight because the full battery was green and a deliberate,
  documented trade is not what a release-candidate freeze is for.

---

## What the audit checked and found nothing wrong with

Recorded because "we looked" is worth as much as "we fixed", and because
the next session should not spend the night here again.

| area | how it was checked | result |
| --- | --- | --- |
| Tenancy | `test_tenancy_penetration`, plus an AST sweep for `store.load()` inside service helpers | Every hit is a CLI `main()` or a super-admin route. `Repo.for_user` is the only path a handler has |
| Authorization by URL | All 47 navigation entries requested over HTTP as each of the five roles: 235 requests | No unexpected status. Super admin 200 throughout; `/admin*` is 404 rather than 403 for everyone else, because a refusal that confirms existence is a disclosure; the operator is refused `/users`, the reviewer `/upload` and `/campaigns/new`, the viewer everything but reporting and the overview |
| Whether reading a screen grants writing it | As a client viewer, holding a CSRF token taken from a page they may legitimately read, POSTed to `/reporting/editor/new`, `/save`, `/finalise`, `/export/analytics.csv`, `/export/contacts.csv` | 403, 403, 403, 404, 404. `PRODUCT-GAPS.md` §10's "the client viewer is read-only" is now a measurement rather than an assumption |
| Client PDFs | All four templates generated, with four planted provider credentials in the environment | Valid PDF-1.4, `%%EOF` present, 11-23KB, no canary in any byte |
| Stack traces to a browser | `WEB_DEBUG` read | Prints to the server's stdout only. The response is a generic 500 either way |
| Third-party dependencies | AST over every import in `src/` against `sys.stdlib_module_names` | None. The claim in `DEPLOYMENT-PLAN.md` §1 is true and is now a test |
| Fresh clone | Cloned, started with an empty environment, no `work/`, no `out/` | Starts and serves. No setup step at all |
| Health endpoint | `/healthz` over HTTP with no session | 200, `{"ok": true, "demo": true, "live_sending": false}` |
| Live-sending visibility | `pages.shell` | Every page carries "Live sending **disabled**" and DEMO/LOCAL in the chrome |
| Sending | `push.run(live=True)` | Raises. There is no code path to either provider, which is the intended state |
| Swallowed failures on safety paths | AST over every broad `except` in `src/`: 80 handlers, classified by what each does with the failure | 77 handle, re-raise, or return a classified value. Three swallow, and all three are deliberate: two are `_memory_mb`, which returns `None` rather than guessing at resident memory, and one is the refusal audit writer - see below |
| Full battery on the final tree | suite, offline harness, mutation audit, in isolation, in that order | 4,774 OK; 4,774 OK with the network blocked; 392/392 caught; tree clean afterwards |
| The deployment itself | fresh clone, empty environment, four start states | `RELEASE-CANDIDATE.md` §0 |

---

## One thing considered and deliberately not done

The bind refusal exempts demo mode on the strength of the caller's `demo`
flag, not on the strength of the data actually being fictional. A second
pass asked the obvious question: is that a guard on one path and not
another?

It was checked rather than argued about, and the answer is that the flag
is not standing alone.

- `main()` is the only entry point. When `--demo` is given it points every
  state file, the MX cache, the output directory and the client config
  directory at a fresh temporary directory *before* anything is installed
  - three lines above the `serve()` call that reads the same flag.
- `demodata.install()` refuses independently. It raises rather than
  writing if the queue already holds a non-demo record
  (`test_demo_refuses_to_run_over_real_records`), and it refuses to write
  into the repository's real `config/clients/`.

So the sequence a real deployment runs is guarded twice, by two modules,
for two different reasons. Adding a third check - "is the store somewhere
throwaway" - would not be a stronger fact than the two already there. It
would be a *different proxy* for the same fact, since a store pointed at
a real client's queue and started with `--demo` would satisfy it and be
caught by `install()` anyway.

`CLAUDE.md` is explicit that a second representation of one truth is how
two things drift. This is recorded rather than done, so the next reader
finds the reasoning instead of the gap.

---

## Exit criteria

The audit was allowed to end when all of these were true, and it ended
when they were:

- [x] Known P0s closed, or refused in code where closing them means
      building a feature nobody has decided the shape of
- [x] Pilot-blocking P1s closed or recorded with the exact next action
- [x] A regression test for every fix, asserting behaviour rather than
      source text
- [x] Every fix attacked: eleven mutations, each failing the intended test
      for the intended reason, each restored and verified
- [x] Six of them permanent in `tools/mutation_audit.py` (392 total)
- [x] Full battery green
- [x] Repository restored and clean, staged file by file
- [x] Everything remaining classified honestly rather than closed

`RELEASE-CANDIDATE.md` carries the numbers, the verdicts and the runbook.
