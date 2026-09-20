# Live readiness

One table, every capability, one classification each. It exists because
"is it ready" is not a question with one answer, and a summary that gives
one is the document somebody quotes in front of a client.

Strict on purpose. **A fixture is not a live-validated integration.** Code
that runs correctly against a recorded payload has proved that the code is
correct, not that the payload is what the provider sends.

---

## How to read a classification

| | what it means |
| --- | --- |
| **READY** | works, tested, and the only thing between it and a client is somebody deciding to use it |
| **READY WITH MANUAL REVIEW** | works, and a person has to look at the output before it goes anywhere. `MANUAL-REVIEW.md` says what they are looking for |
| **FIXTURE ONLY** | the code path runs end to end against recorded or synthetic input. No real counterpart has ever answered it |
| **NEEDS LIVE CONTRACT VALIDATION** | the integration is written and the wire has never been exercised. `LIVE-VALIDATION-PLAN.md` is the sequence for doing that safely |
| **BLOCKING** | this stops a pilot until it is resolved |
| **NOT REQUIRED FOR PILOT** | genuinely out of scope at 10–20 companies, and named so nobody discovers the absence mid-run |

Two of those are frequently confused and are kept apart deliberately.
FIXTURE ONLY means we have never seen the real thing. NEEDS LIVE CONTRACT
VALIDATION means we have written what we believe the real thing wants.
Neither is READY, and calling either one READY is the failure this file
exists to prevent.

---

## 1. Audience

| capability | class | why |
| --- | --- | --- |
| CSV import and normalisation | READY | `ingest`, `upload`. Real client CSVs; header aliases, same-domain contacts, the row-2..N collapse fixed in `fd5be18`, comma/semicolon/tab/pipe exports, and a row whose shape does not match its header reported rather than trimmed. Every person is screened against existing engagement, not only the first at each company. XLSX is read, with the two limits in `PRODUCT-GAPS.md`. The preview now has a second step: `/upload/commit` existed from the start and nothing rendered a form for it, so until `tests/test_import_commit.py` no lead could be imported through the product at all. |
| Identity and deduplication | READY | Strong identity only - normalised mailbox, canonical profile URL, provider lead id. A name is never identity |
| ICP qualification | READY WITH MANUAL REVIEW | The rules are the client's and the verdict is theirs to confirm. `review` and `unknown` are real answers and mean zero person credits |
| Company enrichment | NEEDS LIVE CONTRACT VALIDATION | `contactout.company-information-from-domain` costs a credit and was deliberately not called. ContactOut itself is now authenticated and answering - see Platform |
| Decision-maker discovery | NEEDS LIVE CONTRACT VALIDATION | `contactout.decision-makers` costs 10 credits by the estimator's own reckoning; not called |
| Email verification waterfall | NEEDS LIVE CONTRACT VALIDATION | Three providers, a confirmation rule, and no wire exercised. `VERIFICATION.md` |
| MX screening | NEEDS LIVE CONTRACT VALIDATION | A hand-written DNS client over UDP. Correct against recorded responses; never run against live resolvers here |
| Public research | NEEDS LIVE CONTRACT VALIDATION | `apify` authenticates and answers `GET /users/me`. An actor *run* costs money and was not made, so every evidence row in the estate is still synthetic |
| Segmentation | READY | `segments`, `campaignseg`. Pure functions over the record |
| Micro-segment split axes | READY | Reports how a cohort *could* be divided and refuses to split on its own |
| Discovery (delta) | FIXTURE ONLY | The subtraction is real and tested. Every candidate is a fixture: `LIVE DISCOVERY PROVIDER REQUIRED`, and there is no CRM connector |
| Client review roundtrip | READY | CSV out, CSV in, canonical columns compared. Silence is `never_returned`, not rejection |
| Refresh planning | READY | It plans and never spends. The calls it *plans* are the unvalidated ones above |

## 2. Copy

| capability | class | why |
| --- | --- | --- |
| Cadence expansion | READY | Seven steps across both channels, with dependencies and channel separation. `cadencegraph` offers 14 node kinds for longer multichannel sequences |
| Draft generation | BLOCKING by construction | Not "the integration is written and the wire has never been exercised", which is what the class above means. There is no integration: `src/llm.py` defines an interface and two offline stubs (`NoModel`, `ScriptedModel`), no HTTP client for any model provider exists anywhere in `src/`, `generate.main()` has no `--model` argument and `run()` defaults to `NoModel` - so the remedy this row used to state, `--live` on `src.generate`, is not executable. Same class as `push.run`: a code change and a review, not a credential |
| Lint | READY | Refuses; never widened to let a draft through |
| Claim checking | READY | `claims` refuses a finished draft that asserts what nothing supports |
| Observation licensing | READY | `observations`. What may be said about them, and the four things that stay unspoken |
| Outreach claim resolution | READY | `outreachclaims`. What may be said about us, against our own event log |
| Personalisation | READY WITH MANUAL REVIEW | Evidence-backed and re-aged at message time, and a person should still read the first campaign's drafts |
| Copy variants | READY | Five styles per channel, one variant per contact per step, deterministic assignment, Wilson lower bound before a winner is called. The *screen* is a different question - see below |
| Copy experiment screen | NOT REQUIRED FOR PILOT | It reads `campaign["cadence_graph"]`, which nothing writes, so for a real campaign it now says so rather than falling back to `demovariants`' planted totals. The variant chain itself - assignment, payload, confirmed exposure, attribution - does not go through this screen and is READY above |
| Campaign QA | READY | Blocks approval; reports how much it inspected |

## 3. Sending

| capability | class | why |
| --- | --- | --- |
| Eligibility gate | READY | Re-derived at payload time from primary state |
| Approval and orchestration | READY | Fingerprinted; an edit invalidates it |
| Payload construction | FIXTURE ONLY | EmailBison and HeyReach payloads are built and asserted against the documented shape. Neither has been posted |
| **Email sending** | **BLOCKING** | `push.run(live=True)` raises. Not a flag: there is no code path to either provider **in `src/`**. Corrected 2026-09-09: this row said "no code path" without that qualifier, and `prototype/bin/push.py --live` was one - a real POST to both providers with none of the guards, found only by chance. It is refused now, and `prototype/` has been swept, so the claim holds again as written. PRODUCT-GAPS 28 |
| **LinkedIn sending** | **BLOCKING** | Same |
| Provider campaign naming | READY | `providername` renders the string. Nothing creates a provider campaign, so the *mapping* is NEEDS LIVE CONTRACT VALIDATION |
| Provider tag sync | FIXTURE ONLY | The outbox records desired state correctly. `tagsync.send` refuses unconditionally: no tag endpoint has been validated |

`BLOCKING` here is the intended state of this build, not a defect. It
blocks a pilot that involves sending, and `LIVE-VALIDATION-PLAN.md` stage
4 is the sequence for lifting it one object at a time.

## 4. Inbound

| capability | class | why |
| --- | --- | --- |
| Reply ingestion (polling), EmailBison transport | LIVE-VALIDATED 2026-09-02 | `poller`. Polling rather than webhooks is a deliberate decision - neither provider offers a signature we can verify. A real cursor now comes back: 8 hops over `GET /api/replies`, 120 rows, pages disjoint, checkpoint persisted. This found a live-only bug - `fetch_replies` read `meta.next_cursor` without ever sending `pagination_type=cursor`, which the instance only populates in cursor mode, so the poller could never advance past its first 15 rows of 269,877. Fixed and covered by a test that asserts on the request we build, not on the fixture's answer. A second live-only defect followed from it: the feed is newest-first and its cursor bounds the page to *older* rows, so resuming from a stored cursor walked backwards into history and would never have seen a reply that arrived after the checkpoint. The checkpoint is now a high-water mark; two consecutive live runs behave correctly - 3 pages and 44 events, then 1 page and 0 |
| Reply ingestion, matching to our records | NEEDS LIVE CONTRACT VALIDATION | Every real reply on this instance belongs to a lead Productive created outside Resonate, so all 120 classified `unmatched` - correct, and fails closed, but it means the match-to-our-own-record path has still never run against real traffic |
| Reply normalisation | READY | Three payload shapes to one neutral event, idempotent on the provider's own id |
| Pause-before-classify | READY | The pause happens before classification and long before anyone is told. Nothing downstream can undo it |
| Reply classification | READY WITH MANUAL REVIEW | Conservative, and never resumes anything on its own |
| Account policy effects | READY | Per contact, per other decision maker, per account |
| Slack notification outbox | READY | Recorded, routed, two levels with no fallback between them |
| Slack posting | NEEDS LIVE CONTRACT VALIDATION | `SLACK_LIVE` is off and no message has been posted |
| Slack interactions endpoint | NEEDS LIVE CONTRACT VALIDATION | New. `/slack/interactions` verifies, deduplicates and applies over real HTTP in tests. No request from Slack has ever reached it, and a human must paste the URL into the app and set `SLACK_SIGNING_SECRET` |
| Revival | READY | Verdicts only. Nothing is sent, drafted or queued, and a READY account goes through every gate a first approach goes through |

## 4z. The autonomous execution layer, as of 2026-09-10

Built overnight, and every row here is deliberately classified below what the
code might suggest, because the distinction this document exists to make is
between a thing that works and a thing that has worked against a real
counterpart.

| capability | classification | what that means here |
| --- | --- | --- |
| provider configuration differ (`configdiff`) | **READ-ONLY VALIDATED** | run live against a real HeyReach campaign; caught a vendor placeholder note that every other check passed. The EmailBison half has never been run against a real campaign and one of its fields cannot pass (see below) |
| execution guard (`executionguard`) | **FIXTURE ONLY** | 50 tests, every gate proven to stop a provider call entirely. It has authorised exactly one action, in a dry run |
| action ledger (`actionledger`) | **FIXTURE ONLY** | reserve-before/settle-after, tenant-scoped caps enforced inside the reservation transaction. No row has ever been settled by a real write |
| guarded write layer (`providerwrites`) | **LIVE-VALIDATED, 14 VERBS ENABLED** | **CORRECTED 2026-09-20.** This row read "`SUPPORTED = ()`. Every operation refuses" and that has been false for days. Measured: 14 verbs, three of them prospect-facing - `heyreach.add_lead`, `bison.activate`, `heyreach.activate`. Enabling one is still a visible diff; the claim that none is enabled was the falsehood |
| approval fingerprint | **READY** | covers senders, provider binding, limits, lead set, tenant and angle; 13 tests, one per material field, plus one proving a volatile counter does NOT invalidate consent |
| persona spend cap | **READY** | `max_contacts_to_enrich` is now read by the code that spends. Halves verification on the real cohort |
| budget floor | **READY** | a live run with no `--cap` is refused at both CLIs |
| credential firewall in tests | **READY** | the suite read the operator's real `config/.env` 1,289 times per run and attempted 83 real provider calls, including to the client's live EmailBison instance. Now zero |
| reply provenance | **READY** | every reply event names the estate it was read from |
| streaming controller | **NOT BUILT** | deliberately. See PRODUCT-GAPS 38k: a 30,000-record queue is a 505 MB whole-file rewrite taking 14.6s against a 10s lock timeout, so a controller on this substrate would be built on sand |

**CORRECTED 2026-09-20. THIS SECTION ASSERTED A SAFETY PROPERTY THAT NO
LONGER HOLDS.** It read: "There is no route that adds a lead, and none that
activates a campaign... the write layer's allowlist is empty behind all of
them", and closed by calling the brakes "attached to a pedal that is not
connected to anything."

Every clause of that is now false, and this is the document CLAUDE.md names
as the one to read before promising anything. Measured against the providers:

    providerwrites.SUPPORTED          14 verbs, 3 prospect-facing
    heyreach.add_lead                 SUPPORTED
    bison.activate, heyreach.activate SUPPORTED
    EmailBison canary 451             ONE REAL EMAIL SENT, 2026-09-14
    HeyReach 605732                   IN_PROGRESS, 3 leads, senders attached
    EmailBison 487 / 489              10 and 5 leads enrolled, 0 sent

**This build can send, and has sent.** The pedal is connected. What is true
is narrower and worth stating precisely: no cohort has gone out yet, 487 is
paused awaiting an authorized resume, and 489 and 605732 are waiting on
provider schedules rather than on any gate of ours.

The gates are real and they are running in anger now, not on some future day
a route opens. `killswitch.require`, the approval fingerprint, the collision
check, the account gate and `providers.refuse_unauthorized_write` have each
refused a real action in the last week.

**Why this was allowed to drift:** the row and the paragraph were written
when they were true and nothing re-read them when `SUPPORTED` was populated
one verb at a time. A document asserting a safety property needs the same
treatment as a cached provider snapshot - it is only as good as its last
verification, and nothing here dated it. Buggie's audit of 2026-09-20 caught
it; the finding was rated CRITICAL and it was right.

---

## 5. Reporting

| capability | class | why |
| --- | --- | --- |
| Operational analytics | READY | Every rate carries its numerator and denominator |
| Client PDF report | READY | Hand-written PDF writer, no dependency, branded |
| Cohort learning | READY | And correctly reports `INSUFFICIENT_DATA` at this volume, which is the honest answer with 11 contacted accounts |
| Cost simulation | READY | Ranges, labelled as assumptions where the price is not known |
| Discovery funnel reporting | NOT REQUIRED FOR PILOT | Nothing has been discovered by a provider to report on |

## 5b. Provider wires, as of 2026-09-02

The first live reads this build has ever made. Read-only, no credits, no
writes. `PRODUCTION-TRANSITION.md` §1 is the detail and §2 is what they
revealed.

Re-run live on 2026-09-07 through `python -m src.check`, plus one free
reply page. Five ok, three skipped on purpose, none failed. Two things
changed since the 2026-09-02 evidence and both are recorded below rather
than quietly overwritten: EmailBison now answers **zero** campaigns where
it answered fifteen, and Slack appears in the sweep for the first time
because it was never in `check.PROVIDERS`.

| provider | authenticated | read contract | still required |
| --- | --- | --- | --- |
| ContactOut | **yes**, `GET /stats` | **`people-count` trim matches a real response.** **`email-verifier` READ-PROVEN 2026-09-07**: the route is `GET /v1/email/verify?email=`, not the `/email-verifier/verify` that 404ed nine times out of nine, and two real addresses answered `accept_all` and `invalid` - the verdict nests under `data.status`, which `unwrap` already handles | the paid trims: company info, decision-makers, people-search |
| AI Ark | **yes**, `tools/list` | 11 tools listed | every enrichment call costs credits |
| EmailBison | **yes**, re-confirmed 2026-09-07 | **`GET /campaigns` answered 200 with an empty list earlier on 2026-09-07, and 20 campaigns later the same day.** The first reading was recorded here as stale content and that was wrong: the credential's *workspace context* was pointing at a different workspace, and it moved when an operator deleted `ColdMessage - Productive`. Nothing about the transport changed. See `PRODUCT-GAPS.md` on workspace isolation - this is the hazard, observed rather than theorised. The account is not empty: one free `GET /replies` page returned 15 rows with a live next cursor, and `classify_reply_row` sorted them on real data into 9 bounces, 1 reply and **5 outgoing** - our own mail, correctly refused rather than read as a prospect reply, which is the guard that matters most on this endpoint. **`GET /replies` cursor-paginated, 120 real rows parsed.** `GET /leads` was traversed once by hand - 27,035 rows over 1,803 cursor pages - and no function in `src/` reads it, so the product cannot repeat that and nothing consumes it. `bison.leads_endpoint` is the *write* path for phase 7, not a reader. It is the path PRODUCT-GAPS' contact-history fix would need | a reply matching a record *we* created; every write |
| HeyReach | **yes**, `GET /auth/CheckApiKey` | **`POST /campaign/GetAll`, paging confirmed at limit=100. Inbox READ-PROVEN 2026-09-07** - the read `HUMAN-ACTIONS-REQUIRED.md` 2 asks for was authorised and run. `POST /inbox/GetConversationsV2` answered the documented `{items, totalCount}`; **totalCount 25,473**; all 25 conversations on the page carried a complete `messages` list, matching the module's claim; `sender` and `lastMessageSender` took **only** `ME` and `CORRESPONDENT`, so the allowlist that decides what counts as a prospect reply is correct against real traffic; and offsets 0 and 25 returned disjoint pages | the same read settled the coverage question: `lastMessageAt` was monotonically non-increasing across 200 conversations and four pages, so the walk may stop at the high-water mark and a run now reads everything new rather than 0.98 per cent of the inbox. Every write |
| Apify | **yes**, `GET /users/me` | account reachable | an actor run, which costs money |
| Slack | **no token configured** | none - and until 2026-09-07 it was not in `check.PROVIDERS` at all, so the sweep never touched it while this table counted eight providers. `check()` also returned SKIP unless `SLACK_LIVE` was set, which is the switch that arms *posting* - so proving a token required arming the send path. Both fixed; the free `auth.test` now runs on a token alone | a token, and a channel |
| DNS / MX | n/a, no credential | **PRODUCTION-PROVEN 2026-09-07.** `mx.for_domain` against real resolvers: Google Workspace and Microsoft 365 both detected by MX suffix, five MX records parsed for this agency's own domain, and `no_mx` kept distinct from a lookup that failed | nothing |
| OIDC discovery | n/a, public document | **READ-PROVEN 2026-09-07.** Google's and Microsoft's real documents fetched through the shipped `discover()`, both endpoints TLS-checked, an `http://` issuer refused. Reading Microsoft's found that a multi-tenant issuer is a template and would refuse every sign-in - see `PRODUCT-GAPS.md` | a real sign-in, which needs an OAuth client |
| **Blitz** | **no**, never called | **none - fixture only.** Declared 2026-09-08 with no call site. Every field spelling in `src/providers/blitz.py` comes from the OpenAPI specs and **no response has ever been observed from this repository**, so the trims are unproven and the HTTP verbs in `ROUTES` are inferred rather than confirmed. `tests/fixtures/cassettes/blitz.json` is hand-written from the capability matrix and is **not** evidence of anything | a live `GET /v2/account/key-info`, which is free and returns `allowed_apis` - the only authority on what the key may call. Then one deliberate metered call before any call site is wired |
| Reoon | key present, **not called** | none | one credit, deliberately (`--live-reoon`) |
| **Deliverable** | **cannot be tested without spending** | **none - response shape still unread** | **the top blocker.** `LIVE-VALIDATION-PLAN.md` §2.1 |
| Slack | no token configured | none | a token, a channel, and `SLACK_LIVE` |

**A fixture is not a live-validated integration.** Blitz is the newest
example and the clearest: it has a module, 62 tests, a cassette, a cost table,
a waterfall position and a health check, and it has never exchanged a byte with
the provider. Everything about it that could be wrong is still wrong.

**A live read is not a live write.** Everything in section 3 is still
BLOCKING by construction, and nothing above changes that.

## 6. Platform

| capability | class | why |
| --- | --- | --- |
| Multi-tenant web application | READY | Hard scoping through `Repo.for_user`; 404 rather than 403 on a cross-tenant read |
| Roles and permissions | READY | One table, checked before the handler runs |
| **Authentication** | NEEDS LIVE CONTRACT VALIDATION | OpenID Connect, authorization code with PKCE, standard library only. Every check - state, nonce, issuer, audience, expiry, `email_verified`, allowed domain - is proven end to end against an identity provider that answers, and eighteen mutations exist to stop one being removed. **No real provider has ever answered it**: the wire is exercised against a fake OpenID provider on loopback, which proves the code and not the counterpart. `PRODUCTION-AUTH.md` §5 is the OAuth client somebody has to create |
| Refusing to run unauthenticated | READY | `web.app.check_configuration`. Without a configured provider, production mode refuses and a non-loopback bind refuses unless the estate is fictional. With one, both lift together - they read one predicate rather than each carrying a copy of the fact |
| Publishing the demonstration | READY, **and done** | Deployed 2026-09-02 to https://resonate-demo-production.up.railway.app from `a2c97f0`, with no environment variables set. `--demo` points every state file at a throwaway directory and installs fictional companies before a real client file is reachable, so an exposed demo leaks nothing that exists. `RELEASE-CANDIDATE.md` §0b is what was verified on the running instance |
| Deployment configuration | READY | `Procfile`, `railway.json`, `requirements.txt`, `.python-version`, and `tests/test_deployment_config.py`, which puts each start command through the parser and refusal `main()` uses rather than reading it. Exercised on a real build: the platform resolved `.python-version` to CPython 3.14.6 and installed no packages |
| Persistent state in a container | NEEDS LIVE CONTRACT VALIDATION | A container filesystem is ephemeral. Point `QUEUE` at a mounted volume and every other state file follows it; no volume has ever been mounted from this build |
| Audit log | READY | Including the super-admin view |
| Batch processing | READY | Resumable per record; a failed job reports what it completed |
| Operational health | READY | Reads failures already in canonical state, says whether a retry is safe, and names the two areas it is not watching |
| Persistence | READY WITH MANUAL REVIEW | Append-only JSONL with a lock. Correct and measured to 30,000 records. `DATABASE-MIGRATION.md` is the Postgres path when that stops being true |
| Scheduler | NEEDS LIVE CONTRACT VALIDATION | Two jobs run on a timer and both are off unless asked for: `replywatch` reconciles replies and `digestwatch` delivers the daily summary, on one supervised thread in the web process. Correct against the clock and under a lock; never run for a day on the deployed service, which is the only thing that proves a schedule. "Weekly" in `discovery` and `refresh` still describes an intended cadence that nothing invokes, and both say so |
| Secrets handling | READY WITH MANUAL REVIEW | Environment only, never in state, and every screen the navigation offers is swept for planted canaries - the sweep is derived from `pages.NAV`, so a new screen joins it rather than being forgotten. A real secret store is a deployment decision |
| Backups | NOT REQUIRED FOR PILOT | Local files, and `DEPLOYMENT-PLAN.md` covers it for a hosted run |

---

## What this means for a pilot

Nothing in section 3 can send, by construction. A pilot at the size
`PILOT-PLAN.md` describes - 10–20 companies, 20–40 contacts - is
therefore a **preparation** pilot today: import, qualify, enrich,
segment, build, QA, approve, and inspect the payloads that would have
gone out.

**Verification does complete, and an earlier version of this paragraph
said it could not.** The correction matters, so here is the whole chain,
traced 2026-09-07.

`DEFAULT_POLICY` wants two independent confirmations and names
`deliverable` as the secondary, and `deliverable.verify` refuses every
call until somebody sets `DELIVERABLE_RESULT_SHAPE`. The wrong inference
from that - the one this file carried - is that an address therefore
stops at one confirmation. It does not, because of how the refusal is
classified: `verification.call` catches `ContractNotVerified` and records
`status: error`, and `decide` excludes an errored provider from `usable`
entirely. So the refusal is not a negative, does not create a
disagreement, and leaves the state at `held, 1 of 2` rather than at a
contradiction.

`verify` then walks `[primary, secondary, catch_all]` and asks
`needs("reoon", evidence, policy)`, which answers True whenever the count
is short of the requirement - not only on an unresolved catch-all. Reoon
runs, and `contactout: valid` plus `reoon: valid` is two independent
vendors on the same normalised address: `verified`, `sendable`,
`confirmed_by ['contactout', 'reoon']`. `push.verify_before_payload`
recomputes and agrees.

So the email lane is open, at **two real verifier credits per address** -
one ContactOut, one Reoon. Deliverable bills nothing, because it never
reaches the wire. Two consequences worth planning around: a batch cap
must be sized at **three** per contact rather than two, since the phantom
Deliverable charge is still reserved against it and a cap of two would
refuse the Reoon escalation part-way through a run; and a **catch-all
address still cannot pass**, because `accept_all` is not in
`CONFIRMING_STATUSES`, so clearing one leaves it at one confirmation.
Catch-all domains are unsendable until Deliverable is armed.

Setting `DELIVERABLE_RESULT_SHAPE` remains worth doing - it adds a third
vendor and unlocks catch-alls - but it is no longer what stands between
this build and a verified address.

To make it a sending pilot, in order:

1. Stage 1 and 2 of `LIVE-VALIDATION-PLAN.md`: read-only provider calls,
   then one credit deliberately.
2. Stage 3: Slack, read then write, including the interactions URL.
3. Stage 4: outbound providers, one object at a time, against a mailbox
   the agency owns.
4. Only then: lift the refusal in `push.run`, which is a code change and a
   review, not a flag.

Every one of those is a human decision. None of them is made by this
repository.
