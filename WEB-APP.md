# The Outbound Control Center

The web application that makes the engine usable in a browser. It renders,
routes and refuses. It does not decide anything.

This document is the one to read before changing `src/web/`. `WEB-READINESS.md`
is the older analysis of what a UI would need; this is what was built, and why
it was built that way. `SLACK-NOTIFICATIONS.md` covers `/admin/slack`,
`/notifications` and the dashboard's Slack panel, and is the one to read before
touching any of them.

**Live sending is disabled in this build.** No screen sends an email, opens a
LinkedIn conversation, creates a provider campaign, posts to Slack or spends a
credit. Provider payloads are generated and displayed; nothing submits them.

---

## 1. Architecture

### The stack, and why it is not a framework

`http.server` and server-rendered HTML, with no third-party application runtime.
The dark Resonate OS shell uses local CSS, JavaScript and the Resonate logo.
`python -m src.web.build` exports the exact production assets and SHA-256
manifest; Node/Playwright are optional development tools for browser checks.
See [the web UI implementation contract](docs/RESONATE-WEB-UI.md).

That is not minimalism for its own sake. The repository has **zero third-party
dependencies** - there is no `requirements.txt`, no `pyproject.toml`, and
`src/clients.py` hand-parses the subset of YAML the client files actually use
rather than importing PyYAML. Adding a framework to serve twenty read-mostly
screens would have made this the first repository in the project's history that
cannot be run by unzipping it and typing `py`. The property is worth more than
the convenience.

What that costs: no automatic request validation, no ORM, no template engine.
What replaces each is named below.

### The four layers

```
src/web/app.py        routing, sessions, permissions, refusals
src/web/api.py        the service layer: arguments in, plain data out
src/web/pages.py      HTML. Rendering only.
src/web/assets.py     loads and content-hashes an explicit static asset allowlist
src/web/static/       shared dark design system, progressive enhancement, logo
src/web/build.py      dependency-free production asset export and manifest
```

Underneath, and shared with the CLI:

```
src/repo.py           the persistence seam. Scoped at construction.
src/workspaces.py     tenants, users, roles, permissions, the audit log
src/jobs.py           resumable work over a batch, with a cursor and a budget
src/web/upload.py     CSV parsing and the guards on the way in
src/web/demodata.py   a fictional estate, built by the real engine
```

### The screens

```
/                       dashboard, or the client-facing cut of it
/batches, /batches/<id> what a batch holds, and its preflight
/jobs                   batch processing: one slice per request
/icp                    the ICP review queue and the human decision
/companies, /companies/<id>   the list, and the full dossier
/segments               region -> vertical -> band
/contacts, /contacts/<id>/<key>   DM, verification, MX, channels, evidence
/campaigns              every campaign, with pause and resume
/campaigns/new          the campaign builder
/campaigns/<id>         review: cadence, lint, QA, provider payloads
/outreach               the full outreach preview, one campaign at a time
/approvals              the approval queue, fingerprinted
/replies                what came back, and marking one handled
/reporting, /compare    advanced reporting and segment comparison
/simulator              the 5,000-domain rehearsal
/timezones              local-time routing
/workspaces, /settings, /users, /audit, /diagnostics
/admin                  the super admin console. Every workspace.
/export/*.csv, *.json   permission-gated export
```

### The rule the whole thing is built around

**Every verdict on every screen came from the same function the CLI calls.**

`api.py` calls `icp.score`, `segments.classify`, `verification.decide`,
`verification.resolve`, `channels.evaluate`, `mx.stored_decision`,
`lint.check_step`, `qa.report`, `cadence.build`, `push.payloads`,
`report.funnel_for` and `scalesim.qualify_scale`. It arranges what they return
into something a template can loop over. It does not compute any of it.

A UI that re-derives "is this sendable" has invented a second answer to a
question with one right answer, and the second one is the one nobody tests.
`tests/test_web_invariants.py` walks the source and fails if `pages.py` imports
an engine module or calls a decision function, and fails if `api.py` stops
calling any of the functions above.

### No business logic in the frontend

`pages.py` imports exactly two things: `assets` (for the cache-busting version
strings) and `security` (for `esc`, `attr` and `safe_url`). It cannot reach the
store, the queue, the campaign file or any engine module. The JavaScript is
about 40 lines and does three things: toggle a disclosure, filter rows already
on the page, and submit a select on change. Nothing it does changes an answer.

---

## 2. Tenancy: a workspace is a boundary, not a filter

`WEB-READINESS.md` names the gap this closes: *"client isolation is a filter,
not a boundary."*

A filter is something a caller applies, and therefore something a caller can
forget. What `src/repo.py` provides instead is an object that has **no unscoped
call on it**:

```python
repo = Repo.for_user(email, workspace_slug)   # raises NotAMember if they are not
repo.records()          # only this workspace's
repo.record(record_id)  # raises CrossClientAccess if it is somebody else's
repo.save_records(rows) # refuses to write a row it does not own
```

There is no `Repo.records(client=...)` for a handler to get wrong. The one
unscoped constructor is `repo.admin_repo()`, named so a reader auditing "what
can cross a boundary" has one place to look and one thing to grep for.

### 404, not 403

Reaching for another workspace's record answers **404**. "That exists but is
not yours" confirms an id, and an id in this system carries a company. A forged
id and a real one belonging to somebody else are indistinguishable from
outside. The same applies to `/admin`: a workspace user should not learn that a
super-admin console exists here.

### Roles and permissions

Five roles, twenty-one permissions, defined in `src/workspaces.py`. The roles form
a strict ladder - viewer ⊂ reviewer ⊂ operator ⊂ workspace admin ⊂ super admin
- so the model can be reasoned about by rank rather than case by case, and a
test asserts the containment.

| Role | What it is for |
|---|---|
| `viewer` | **client-facing.** Outcomes only: dashboard, reporting, compare. |
| `reviewer` | reads contacts and campaigns, approves, pauses. Cannot upload or export. |
| `operator` | runs the machine: batches, campaigns, exports, replies. |
| `workspace_admin` | the above, plus who else may, plus the provider mapping. |
| `super_admin` | every workspace. An account-level fact, not a workspace role. |

`campaign.launch` is granted to nobody below super admin, and is refused at a
lower level anyway: `push.run(live=True)` raises in this build.

`signals.record` is the newest of the twenty-one, and it is separate from
`contacts.view` on purpose: reading the estate and changing what it is
worked in are different powers. A reviewer sees an account's signals and
cannot add one, because a signal moves an account up somebody's list.

#### The permission table is a read-side table

`permission_for(path)` runs before the handler on GET, and only on GET. A
write route therefore carries its own check - `security.require(...)`, or an
`api` call that asks `repo.require(...)` itself - and an invariant test walks
every branch of `_post` and fails on any that reaches neither.

That test exists because one route did not. `POST /upload` had no check
while `GET /upload` required `batch.create`, and parsing a CSV reads this
workspace's records to answer "have we seen these before". A viewer -
the client-facing role, denied `contacts.view` - could post a list of
domains and read back how many were suppressed, already present, or
previously engaged, without committing anything. The counts were the
disclosure. `/select-workspace` is the one deliberate exemption: it is
guarded by membership rather than by permission, because picking a
workspace is what a member does before any permission in it means
anything.

### The role is never in the session

`Sessions.create` stores an **email and a workspace, and nothing else**. The
membership is resolved from storage on every single request.

A role cached in a session is a role that keeps working after somebody removed
it. A role in a cookie is a role the browser can edit. A revoked role has to
stop working *now*, not at the user's next sign-in, and
`tests/test_web_security.py::Permissions::test_7_a_revoked_role_stops_working_immediately`
demotes a live session mid-test and asserts the next request is refused.

### The permission table

`app.READ_PERMISSIONS` maps every read surface to the permission it needs, and
`_get` checks it **before** dispatching. Not inside each handler - a handler
that forgets to ask is exactly the failure mode. `tests/test_web_invariants.py`
enumerates the routes in `app.py` and fails if one has no entry.

The navigation hides links a role cannot use. That is a courtesy, not the
control: a menu full of 403s is a bad tool, and a menu that is the *only* check
is a vulnerability. Both exist, and a test asserts they agree.

### The client-facing cut

A `viewer` is somebody's client, not somebody's colleague. Their dashboard and
reporting page drop the vendor names, the credit exposure, the job queue, the
MX gateway breakdown and the provider operations table - not by hiding them
with CSS, but by rendering a different page with none of it in the markup. The
breakdown dimensions are narrowed on the server too, so a hand-typed
`?dimension=mx_provider` does not reach the supplier list either.

---

## 3. Local development

Requirements: Python 3.11 or newer. Nothing else.

```bash
py -m src.web --demo            # a throwaway estate on http://127.0.0.1:8765
py -m src.web --port 9000       # against the real work/ directory
```

Useful environment variables:

| Variable | Effect |
|---|---|
| `QUEUE` | the queue file. Everything else defaults beside it. |
| `CLIENTS_DIR` | where client configs are read from. Demo mode points it at a temp dir. |
| `WEB_DEBUG` | print a traceback on a 500 instead of swallowing it |
| `WEB_QUIET` | stop logging every request |

`store.use_directory(path)` points the queue, campaigns, jobs, workspaces and
audit files at one directory in a single call. The file *names* live in
`store.py` and nowhere else; `tests/test_invariants.py` fails any other module
that spells one out.

Running the tests:

```bash
py -m unittest discover -s tests -t . -q     # everything
py -m tests.offline                          # the same, with the network unavailable
py -m unittest tests.test_web_acceptance -q  # the security acceptance list, read as tests
py -m unittest tests.test_web_security -q    # the working security suite
py tools/mutation_audit.py                   # break each guard, check a test notices
```

`tests/offline.py` blocks every route off the machine - `connect`,
`create_connection`, `getaddrinfo`, `gethostbyname` - and **permits loopback**,
because the web tests drive a real server on an ephemeral port and that traffic
never leaves the host. It did not always: refusing loopback meant every web
test errored under the harness that exists to prove nothing reaches out, so 194
tests passed in the normal run and were absent from the run that makes the
claim. `is_loopback` parses the address rather than matching a prefix, so
`127.0.0.1.attacker.test` is a hostname and is refused;
`tests/test_offline_harness.py` asserts both directions.

---

## 4. Demo mode

```bash
py -m src.web --demo
```

Demo mode is **not a mock of the application**. It is the application, given
records that were built rather than bought. Every verdict on every demo screen
came out of `icp.score`, `verification.decide`, `mx.classify`,
`channels.evaluate`, `cadence.build`, `qa.report` and `push.payloads`. What is
fictional is the input. A demo that fakes its outputs proves nothing about the
engine; this one exercises it.

Three workspaces, populated differently on purpose - one workspace cannot
demonstrate that a workspace is a boundary:

| Workspace | Companies | Campaigns | State |
|---|---|---|---|
| Productive | 32 | 3 | one approved, one reply planted, one batch qualified with **no campaign yet** |
| ContactOut | 16 | 2 | nothing approved: a full review queue |
| Demo Client | 8 | 1 | early, small |

Productive's fourth batch (`nl-ecommerce`) is built by the same generator as
the other three and then has its campaign row dropped. That is the state
between "qualified" and "there is a campaign", and without a batch sitting in
it the campaign builder has nothing to build. Two Productive companies also
carry a deliberately sparse profile - no industry, no specialties, no employee
count - so they reach `unknown` by having nothing to score rather than by
scoring badly, and the ICP review queue is not empty in the workspace an
operator lands in.

Nine sign-ins, one per role, printed at startup. `ops@contactout.test` is
deliberately in **two** workspaces with **different** roles - operator in one,
reviewer in the other - because a permission model that resolves a role once
per session rather than once per workspace gets that person wrong.

Everything is on `.test` domains and nobody in it is real.
`tests/test_demo_mode.py` and `tests/test_fixture_hygiene.py` keep it that way,
and demo mode **refuses** to write its client configs into `config/clients/` or
to install over a queue holding non-demo records.

Determinism: built from an index, never from a clock or a random seed, so
company 41 is the same company on every machine and a screenshot taken tonight
matches one taken tomorrow.

---

## 4e. Senders: the human, the inbox, and the difference

An inbox is not a person. A LinkedIn profile is not a person. And the person
behind the email is very often not the person behind the LinkedIn message. A
real client looks like this:

    Anna    anna01@ ... anna06@       Mark    mark01@ ... mark05@
    John    john01@ ... john04@       Sarah   sarah01@ ... sarah04@

    Petar LinkedIn   Sarah LinkedIn   Tom LinkedIn   John LinkedIn

`src/senders.py` models the *accounts* - which inbox a step goes out of, and
whether it is over its allowance - and models them well. What it had no concept
of is the human, and without that concept there is no way to answer the
question the product now has to answer: **"my colleague Anna emailed you" - is
that true?** `bison-7` and `hr-3` are two strings; whether they are one person,
two colleagues or two strangers is not recoverable from them.

| Object | What it is |
|---|---|
| `HumanSenderIdentity` | a person. Anna. |
| `EmailSenderAccount` | an inbox, owned by one human |
| `LinkedInSenderAccount` | a profile, owned by one human |
| `SenderPairing` | Anna's email alongside Petar's LinkedIn |

All four live in `src/senderidentity.py`, in `work/senders.jsonl`, and every
one is reachable only through a function that takes a workspace. Resolution by
the *provider's* own account id is scoped too: that is somebody else's
namespace with no cross-tenant uniqueness guarantee, so a global lookup would
be a way to walk from a HeyReach id into another client's roster.

### Capacity is nullable, and that is the point

`daily_limit` is `None` when nobody has told us, and every screen renders that
as UNKNOWN. The senders page shows `520 a day from 13 of 15 accounts` rather
than a total, because a guessed sending limit looks like a control and is not
one: it will be believed, planned against, and wrong.

**Known conflict.** `senders.DEFAULT_DAILY_LIMIT` is 50 - an account configured
on a campaign with no explicit limit is treated as allowing fifty a day. The
new model refuses to do that. The two are deliberately not reconciled:
`senders.py` is the allocator the launch checklist and the push path already
depend on, and changing what it assumes would change which steps are refused,
in a build where nothing sends and the change could not be observed end to end.
The stricter behaviour is in the new model and the planning screens read the
new model.

### Assignment is a stored fact, not a function

`senders.assign` hashes the contact key over the eligible accounts.
Deterministic for a fixed list - and the list is not fixed. Add an inbox,
disable one, let one hit its cap, and the modulus moves and a prospect changes
inbox mid-thread. Survivable at the account level. At the level of a *human
whose name is in the copy*, it is not.

So `src/assignment.py` computes the first allocation from the hash, writes it
onto the contact, and reads it from there forever after. A changed roster is
*reported* (`assignment.is_stale`) and never acted on: that is a reason for a
person to look, not for the software to move a prospect between humans behind
their back. `reassign` is the only thing that changes one, it requires a
reason, and it appends to `history` rather than overwriting.

---

## 4f. Cross-channel memory: what "confirmed" means

`src/touch.py` answers one question and refuses to answer it optimistically:
*is there trustworthy evidence that a named human touched this contact on this
channel, before now?*

A touch is **confirmed** by one of exactly three events:

    push_marked          we handed it to the provider and marked it sent
    email_delivered      the provider said it was delivered
    linkedin_connected   the provider said the connection was accepted

and by nothing weaker. Not an eligible step, not a linted draft, not an
approved draft, not a blocked or held or failed one, and **not
`push_prepared`**. That last exclusion is the one that matters: `push_prepared`
fires when a payload is built, and in this build every payload is built and
none is sent - so treating it as evidence would have the system claim it had
contacted every prospect it ever planned to.

A confirmed touch also has to say **who**. The sender is recorded on the event
at the moment it is sent, and never looked up afterwards, because an assignment
can be changed by a human and reading the current one would let a reassignment
silently rewrite history. A touch with no `sender_id` is confirmed-but-
unattributed: it happened, and it may not be referenced by name.

### The four copy modes

| Mode | When | What it may say |
|---|---|---|
| same-sender continuity | one human on both channels | "I sent you a note over email as well" |
| team handoff | two humans, workspace opted in | "My colleague Anna reached out over email earlier" |
| — | two humans, no permission | **a standalone message** |
| — | nothing confirmed | **a standalone message** |

There is deliberately no "somebody reached out" mode. A prospect who cannot
place the name is still being asked to believe something about a relationship
we were not authorised to describe, and a vague version of an unauthorised
claim is still the claim.

Colleague language is **opt-in per workspace**
(`sender_policy.colleague_language`), because two people being active senders
in one client's workspace is not by itself evidence a prospect would recognise
them as colleagues. A sender may also opt out individually, and the narrower
refusal wins.

### The guard changed from a ban to a licence

`cadence.cross_channel_leaks` used to flag *any* mention of the other channel.
It now flags any **unlicensed** mention - which is stricter, not looser. It
still catches every mention with no evidence behind it, and it additionally
catches a licensed step whose copy names somebody other than the person the
evidence names, which is the failure that puts a prospect in front of a
colleague who never wrote to them.

A reference is made **once**. Five emails each opening "my colleague Petar
reached out on LinkedIn" is not five times as personal.

---

## 5. The three decision screens

### `/icp` - the human decision the playbook reserves for one

PLAYBOOK section 1 is a table: `qualified` gets person credits up to the tier
cap, and `review`, `rejected` and `unknown` get zero - the middle two "until a
human decides". There was no way to record that a human had.
`dmplan.may_enrich` said so out loud, in a string about a field that did not
exist, which made `dm_plan.allow_review_enrichment` unsatisfiable config.

`qualify.record_review` is that field. Two properties matter:

**A review is of a verdict, not of a company.** It carries the inputs
fingerprint the verdict was derived from, so it stops authorising anything the
moment the company facts move - the same staleness rule the campaign approval
and the enrichment approval already use. The form carries the fingerprint back
and the server compares, so "accept" means "accept *this*" and a verdict that
changed after the page rendered is refused with a 409.

**Accepting is weaker than rejecting.** A recorded `reject` blocks enrichment
permanently, at any status, with no policy behind it, because refusing to spend
is never the dangerous direction. A recorded `accept` unlocks a company only
where the client's own config opted in with `dm_plan.allow_review_enrichment`,
and is otherwise recorded and inert. One reviewer clicking a button must not
widen what a client agreed to spend, and the page says which of the two it is
about to do before it is clicked.

The queue prints `missing_evidence` beside the score, because a low score on
good evidence is a rejection and a low score on *no* evidence is a task -
PLAYBOOK section 2 - and a screen that renders them identically teaches people
to read them identically.

### `/campaigns/new` - the builder that cannot choose the population

A campaign is a segment plus a name. Who is in it, which persona, which angle,
which channel strategy and what it would cost were all decided upstream by
`campaignseg.assign`, `routing.plan`, `strategy` and `channels.evaluate`. The
builder shows what those decided and lets a person say yes.

There is deliberately **no field that changes the population**.
`campaignseg.why_together` is already the answer to "why are these two in the
same campaign", and a builder that let an operator hand-pick would be a second
answer to a question that has one. The grouping explanation on the page is that
function's return value, not a sentence written in the template.

Creating one produces a `draft`: no provider campaign, no approval, no
fingerprint, `launch: not_launched`. A company already in a campaign is left out
rather than duplicated - `check_no_duplicate_pushes` would catch it later, but
later means the copy was already written twice.

### `/outreach` - what would actually arrive

`/campaigns/<id>` answers "is this campaign in order". `/outreach` answers the
question somebody asks before approving: what would arrive, at whom, on which
day, and what would not.

Steps that will not run are rendered **in place** with their reason, and the
reason's wording is `channels.explain`'s rather than a paraphrase. A timeline
that quietly drops its blocked steps shows a campaign that is not the campaign.

Contact cards are capped at 40 and the page says what it left out. The totals
above cover everybody either way. A preview that silently shows the first forty
and calls it the campaign is worse than one that shows forty and admits it.

---

## 6. Batch processing, and the four steps it will not run

`/jobs` is where `jobs.run_step` is called from. One slice of 100 records per
request, a cursor that survives the request, and a progress number instead of a
timeout.

The interesting half is the refusal. PLAYBOOK section 1 splits the pipeline at
the STOP - free and re-runnable before it, money after it - and this screen runs
the free half only. `enrich`, `verify`, `research` and `personalize` are refused
by a **table that names each one and says what it would spend**, not by a button
that is not drawn. `render` is refused too: generating copy is a paid model
call. The reasons are on the page rather than behind a disabled control, because
"there is no button" and "that would spend money" are not the same thing for an
operator to be reading.

Records are written before the job is, so a job that says "done" over records
that were never saved is the one lie the ordering cannot tell. The segment pass
runs only when the batch finishes, because which rung a company lands on depends
on how many others share its key: it is not a per-record decision and cannot be
made one slice at a time.

---

## 7. Workspace policy: overrides, not a rewritten file

A workspace's rules live in its client config - a hand-written YAML file with
comments, read by `src/clients.py`, whose own docstring says a misparsed geo is
a live customer getting cold sequenced. A web form is not allowed to rewrite
one.

So the file stays the baseline and what a workspace admin changes is an
**override**, stored beside the workspace in a file this system already owns.
`clients.load()` merges the two, which is what makes the CLI and the web layer
read the same rules - if they differ for one client then one of them is wrong
and nobody can tell which. It used to be `Repo.config()` that merged, and only
`Repo.config()`, so every `--client` command line read the file alone and a
workspace that had raised its confirmation count was verified at two from a
terminal.

The overridable keys are in `workspaces.POLICY_KEYS`. They now include the
market rule, the geo lists and the persona set, so a new workspace can state
who it sells to and who counts as a decision maker without anybody opening a
file - which is what the readiness checklist has always told people to do on
that screen. Every one of them narrows or bounds: the market rule excludes,
the geo lists exclude, and a persona's `cap_per_domain` limits how many people
at one company it may put into a sequence. Three things are deliberately
not overridable:

| Not overridable | Why |
|---|---|
| `verification.required_confirmations` below 2 | double verification is a property of this build, not a setting |
| `email_security.mx_filter.enabled` | turning the filter off is how a Proofpoint tenant gets cold emailed |
| `dm_plan.allow_review_enrichment` | `/icp` says in words that widening it is a config change, not a click |

A key outside the list is **refused**, not ignored. A value outside its range is
**refused**, not clamped - somebody told the system did what they asked when it
did not has learned something false. And one bad value saves none of the others,
because a half-applied policy is a workspace running under rules nobody chose.

---

## 8. The 5,000-domain workflow

The operator path, screen by screen. Every step is reversible up to approval,
and nothing after approval is enabled in this build.

```
LOGIN → WORKSPACE → UPLOAD CSV → NORMALIZE → ICP → ICP REVIEW → SEGMENT
  → CAMPAIGN BUILDER → PRE-DM PLAN
  → COST PLAN → APPROVE ENRICHMENT → DM DISCOVERY → EMAIL/LINKEDIN DATA
  → MX SCREENING → DOUBLE VERIFICATION → CHANNEL ELIGIBILITY → RESEARCH
  → PERSONALIZATION → CADENCE → CAMPAIGN QA → HUMAN REVIEW → APPROVAL
  → PROVIDER PAYLOAD PREVIEW → READY FOR LAUNCH ∎
```

Every one of those has a screen, and the screen calls the engine function the
CLI calls. Nothing in the table below is a stage the web layer invented:

| Stage | Screen | The function behind it |
|---|---|---|
| upload, normalise, dedupe, suppress | `/upload` | `upload.parse`, `ingest.norm_domain`, `dedupe` |
| ICP qualification | `/jobs`, `/batches/<id>` | `icp.score` via `qualify.company` |
| ICP review | `/icp` | `qualify.record_review`, `dmplan.may_enrich` |
| segmentation | `/segments`, `/campaigns/new` | `segments.classify`, `campaignseg.assign` |
| timezone / geography | `/timezones` | `geo.schedulable`, `schedule` |
| enrichment planning | `/batches/<id>` preflight | `dmplan.for_batch` |
| ContactOut-first waterfall | `/contacts/<id>/<key>` | `waterfall.ledger`, `enrich.spend` |
| DM selection | `/contacts` | `routing.plan` |
| double verification | `/contacts/<id>/<key>` | `verification.decide`, `verification.resolve` |
| MX / security filtering | `/contacts`, `/` | `mx.stored_decision`, `mx.allows_email` |
| channel eligibility | `/contacts` | `channels.evaluate` |
| research / personalisation | `/companies/<id>` | `evidence`, `quality.assess` |
| campaign generation | `/campaigns/new` | `campaigns.new_campaign` |
| QA | `/campaigns/<id>`, `/outreach` | `qa.report` |
| human approval | `/approvals` | `orchestrator.decide`, fingerprinted |
| provider payload | `/outreach`, `/campaigns/<id>` | `push.payloads`, `delivered: false` |

The three stages between the enrichment plan and the double verification -
`APPROVE ENRICHMENT`, `DM DISCOVERY`, `EMAIL/LINKEDIN DATA` - are the ones that
spend. They are represented and planned on every screen above, and they are the
four job types `/jobs` refuses to run. In this build the demo estate carries
records that have already been through them; a real batch would stop at the
plan and wait for a CLI run with an explicit budget.

At 5,000 domains the numbers this path is built for: 50 slices of 100 per job,
one cursor, one lock, one process. `/simulator` runs `scalesim.qualify_scale`
over a synthetic 5,000 and reports what the qualification stage would produce
and cost without touching a provider.

### Why there is a job model

5,000 domains is not one request. `src/jobs.py` walks a batch in slices of 100
and checkpoints a cursor after each one, so:

- **A crash loses one record, not a batch.** The cursor advances after the work
  returns, so the item in flight when a process dies is retried. Redoing one is
  the honest cost of not skipping one - and skipping one silently is far worse,
  because nothing looks wrong afterwards.
- **The cursor is matched by identity, not index.** A batch that grew between
  slices would shift every index, and a resume that trusted an index would
  either redo work or skip it.
- **The queue wins when they disagree.** A cursor naming a record that is gone
  starts the walk over. The cursor exists to avoid redoing work, not to decide
  whether work is needed.
- **One bad record is recorded and skipped; twenty in twenty aborts.** Twenty
  failures in twenty records is not a bad record, it is a bad run - a wrong
  config, a dead provider, a mis-parsed file - and continuing through 5,000 of
  them is how a mistake becomes an invoice.
- **A step that can spend refuses without a budget, and stops at it.**
  `ENRICH`, `VERIFY`, `RESEARCH` and `PERSONALIZE` raise if `run_step` is
  called with no budget, and stop when the units are used up. Raising the
  budget continues from the cursor rather than starting over. `CLAUDE.md`:
  *costs are real; cap before you fan out.*

A web request never runs a job to completion. It calls `run_step` and returns,
so the browser gets a progress number rather than a timeout.

### Upload

`src/web/upload.py` parses, reports and writes nothing. A commit is a separate
request. It counts `uploaded`, `unique`, `duplicates`, `existing`, `suppressed`
and `invalid` separately, because "1,000 rows, 600 usable" is four different
facts and an operator needs to know which one bit.

Two guards on the way in:

- **A cell that would execute as a formula is dropped with a stated reason.**
  `src/export.py` prefixes a dangerous cell on the way *out*; that protects the
  file this system writes and does nothing about one landing in the queue. The
  row is refused, not the file - the same trade the job model makes, because
  rejecting 5,000 domains over one poisoned cell is the worse outcome. The
  check reads the **unstripped** value: stripping first removes exactly the
  leading tab that makes the trick work.
- **A value that is not shaped like a hostname is refused.**
  `ingest.norm_domain` normalises but does not validate - it turns
  `cmd|'/c calc'!A1` into `cmd|'` and hands it back - so `upload.py` enforces a
  hostname pattern before anything is stored. *(The CLI ingest path still has
  this laxness. See "Known gaps" below.)*

---

## 9. Campaign review, approval and replies

### Review

`/campaigns/<id>` shows the full cadence per contact, every lint result, the QA
report, the cross-channel timeline and the exact provider payloads that *would*
be submitted. `push.payloads` builds them; nothing sends them. Every payload
carries `delivered: False` and the reason it was not.

### Approval

Approval is local and fingerprinted. The form carries a fingerprint of the
campaign; the server recomputes it and compares. That is what makes "approve"
mean "approve *this*" - a stale approval is refused with a 409, not applied to
a campaign that changed after the page was rendered.

`orchestrator.decide` is the same call the Slack button makes. While fixing the
web path, one real production gap surfaced and was fixed: `decide` called
`slack.require_approver` *before* the role check, so a client with no Slack
block configured could never have a campaign approved at all - by anyone,
through any path. The role check now runs first, and Slack membership is a
second door rather than the only one.

### Pause and resume

A campaign can be paused from **reviewer** upward and launched by **nobody at
all**. The asymmetry is the design: the person who can see something is wrong
should be able to stop it without going to find somebody more senior, and nobody
should be able to start it from a browser. A test asserts no screen anywhere
renders a launch control.

Resuming is not the inverse of pausing. `orchestrator.resume` re-runs the full
validation and refuses with the blockers when it does not pass, so a pause is
not undone by forgetting about it.

### Replies

Any reply pauses **both** channels for the **whole company**, not just the
contact who replied. `/replies` shows what arrived, what it was classified as,
and what the Slack notification *would* say. Nothing is posted.

Marking a reply **handled** records that a person read it, and that is all it
does. The pause is lifted by looking at the company, on the company's own
screen. There is no control on the replies screen that lifts it, and the page
says so, because a checkbox that did would turn a safety property into a piece
of admin.

### Provider mapping

`/settings` shows which EmailBison and HeyReach campaign this workspace maps
to, or states plainly that none has been created. A role carrying
`provider_settings.manage` can change it, and what that records is a
**pointer**: it creates nothing at either provider and changes nothing there,
because creating a provider campaign is a mutation this build does not perform.
Changing a mapping after approval is logged on the campaign, because the
campaign somebody approved would now be submitted somewhere else. Secrets are never shown -
`credential_status()` reports presence by name, gated on
`provider_settings.view`, and a test plants a canary into every credential
variable and greps every rendered byte of every screen for it.

---

## 10. Security

| Property | How |
|---|---|
| Tenancy | scoped `Repo`, no unscoped call, 404 on a foreign id |
| Permission | one table, checked before the handler runs |
| Session | email + workspace only; the role is resolved per request |
| CSRF | every mutation, `hmac.compare_digest` |
| XSS | one `esc()` on every interpolation; a script tag in a company name renders inert |
| URL injection | `safe_url` renders a non-http(s) scheme as text |
| Client verdicts | `sendable`, `approved`, `eligible`, `verified` and friends are **refused**, not ignored |
| Secrets | never rendered; presence only, and only for `provider_settings.view` |
| CSV injection | guarded on the way in and on the way out, through one writer |
| Headers | `nosniff`, `DENY`, `no-referrer`, and a CSP with `default-src 'none'` |
| Cookie | `HttpOnly`, `SameSite=Strict`, 8-hour idle expiry |
| Audit | who, what, which workspace, before → after. No payloads, no credentials. |
| Refusals | every 403 and every cross-tenant 404 writes one audit entry |
| Senders | workspace-scoped, including resolution by a provider's own id |
| Cross-channel | a reference needs a confirmed touch *and* a named sender |
| Directory | the users page lists members only; no cross-tenant address book |

A request carrying `sendable=true` is **refused**, not sanitised. A caller who
sent it and got a 200 has learned something false about this system.

### Refusals are written down

A refusal that leaves no trace is a refusal nobody can review. Somebody walking
record ids looking for one that answers 200 is invisible if the only evidence is
a status code the attacker also has, so every refusal path in `_route` writes
one audit entry: who, when, which workspace, which path, which class of refusal.

**Not the query string, not the form, not the id that was reached for.** An
attacker who can choose what goes into your log has been handed a second tool.
The path is enough to see the pattern. Logging that fails swallows its own
error, because the refusal is the point and is not worth losing over the record
of it.

`/admin` groups them by kind and by actor.

### What authentication is, and is not

There is no password. Sign-in is by email from a known list, and the page says
so. Inventing password storage would create a new place for a secret to live
and would not make anything safer while the server binds to loopback.

What *does* exist is authorisation: which workspaces this person may enter and
what their role there carries, resolved on the server on every request. Before
this is exposed beyond localhost it needs a real identity provider - see
"Deployment readiness".

---

## 11. Deployment readiness

**Not deployed, and not ready to be, without the four items below.** Everything
else works.

1. **Authentication.** Sign-in is by email with no credential. This must be an
   SSO / OIDC integration before the app leaves localhost. The seam is one
   function: `app._login` produces a session from a verified email.
2. **TLS and a real server.** `ThreadingHTTPServer` is fine for one operator on
   loopback. Behind a reverse proxy with TLS termination, `Secure` must be
   added to the session cookie.
3. **Two processes writing at once.** The file store takes a lock and is
   correct for one process. `DATABASE-MIGRATION.md` is explicit that files stop
   being enough *when two processes need to write at once* - which is the day a
   worker process is added, not before.
4. **Live sending.** Disabled at four levels: no route, no permission below
   super admin, `push.run(live=True)` raises, and every screen says so.
   Enabling it is a deliberate act that should have its own review.

### Database migration

Deliberately not done tonight. Files are still enough, and doing an
irreversible migration without the constraint that motivates it is how a
schema gets chosen badly. What *was* done is the preparation: every query lives
behind a method on `Repo` named the way the query would be, so a `SqlRepo` can
be written and joined without a single caller changing. `records(state=, lane=,
batch=)` is a `WHERE`. `save_records` is an `UPDATE` that already refuses rows
outside the tenant, which is what row-level security would enforce for free.

### Worker migration

`jobs.run_step` is already the unit a worker would consume: it takes a job, a
list and a callable, does one slice, checkpoints and returns. Moving to a
worker process means changing who calls it, not what it does. The cursor,
budget and failure-rate logic move unchanged, because none of it assumes it is
running inside a request.

---

## 12. Known gaps

Written down rather than left to be discovered.

- **`ingest.norm_domain` does not validate.** The web upload enforces a
  hostname shape; the CLI path does not. Fixing it in `ingest` would change
  what an existing pipeline accepts, which is a wider change than tonight's
  scope. Worth doing deliberately.
- **No password, no SSO.** See above.
- **Sessions are in memory.** A restart signs everybody out. That is the right
  trade for one process with no user database - the alternative is persisting
  session material to disk, which is a new place for a secret to live.
- **A workspace admin can add any existing account to their workspace.** They
  have to know the address - there is no directory to browse - but there is no
  invitation-and-acceptance step. Fine for an internal tool with nine accounts;
  revisit alongside SSO.
- **`/audit` is readable by an operator.** Scoped to their own workspace and
  carrying no secrets, so this is a deliberate call rather than an oversight:
  an operator debugging their own workspace should not need an admin.
  `?scope=all` widens it to every workspace, and the super-admin check - not
  the parameter - is what decides whether that happens.
- **Job execution is synchronous within a slice.** Fine at 5,000 records;
  revisit alongside the worker migration.
- **`/jobs` runs one job type.** ICP classification, which is the free half of
  the pipeline. The four that spend are refused by a table rather than absent,
  and `render` with them. When paid enrichment is enabled the runnable set is
  where that decision gets made, and it should be made deliberately rather than
  by adding an entry.
- **Provider mapping records a pointer.** Creating the EmailBison and HeyReach
  campaigns it points at is still a mutation nothing here performs.
- **A workspace policy override applies to the CLI too.** That is deliberate -
  two readers of one client's rules disagreeing is worse - but it means a
  change made in a browser changes what a terminal command does. The audit
  entry is how that stays visible.
- **A refusal writes an audit entry, and nothing rate-limits that.** Fine on
  loopback with nine accounts. Before this is exposed further, a caller who can
  make requests can make the audit file grow, and the answer is a rate limit
  rather than dropping the record.
- **Cross-channel reference decisions are not in the audit log.** They are
  recorded on the step and shown in the preview with the reason, which is
  where QA reads them. Auditing every one would be 5,000 contacts times seven
  steps of entries per build, and a log nobody can read is a log nobody reads.
  The *reassignment* of a sender is audited, because that is the rare,
  deliberate act somebody asks about later.
- **`senders.py` and `senderidentity.py` disagree about an unknown capacity.**
  See "Known conflict" above. Deliberate, documented, and worth revisiting when
  live sending is enabled.
- **The security-event feed has no retention policy.** `work/audit.jsonl`
  grows and nothing rotates it. It is a file of identifiers and status words,
  not payloads, so it grows slowly - but "slowly" is not "never".
