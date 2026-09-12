# What this product does not do

One index of every deliberate gap, so nobody discovers one in front of a
client. Each entry says what is missing, why, and where the detail lives.

Nothing here is a bug. A bug is behaviour that contradicts what the system
claims. Everything below is behaviour the system already declines to claim —
and the declining is the point. The failure mode this file exists to prevent
is a dashboard tile showing `0` for something nothing observes, which teaches
a reader to read an absence as a result.

---

## 1. Nothing sends

The largest gap, and the intended one for this build.

| Surface | State |
| --- | --- |
| Email (EmailBison) | payloads prepared, never posted |
| LinkedIn (HeyReach) | payloads prepared, never posted |
| Slack (outbound) | alerts recorded and routed, never posted |
| Slack (inbound) | `/slack/interactions` exists and verifies; no real click has reached it |
| Paid enrichment (ContactOut, Reoon, Deliverable) | callable, not called |

`--live` is explicit everywhere and unset everywhere. `/healthz` reports
`"live_sending": false`, and `tests/test_web_invariants.py` asserts that
string is in the source rather than trusting the runtime.

**What it would take:** `LIVE-VALIDATION-PLAN.md`, which is a controlled,
separately authorised test, not a flag flip.

The inbound row is new and is a different kind of gap from the others. The
endpoint a Slack app posts a button click to did not exist until now:
`src/interactions.py` verified, deduplicated and applied an interaction
from the day it was written, and no URL reached it, so every Approve /
Reject button in an approval notification pointed at nothing. A client
would have found that by pressing one.

The route exists now and is tested over real HTTP. What has *not* happened
is a request from Slack itself: `LIVE CONTRACT VALIDATION REQUIRED` for
the request shape, and a human still has to paste the URL into the Slack
app's interactivity setting and set `SLACK_SIGNING_SECRET`. Without that
secret the endpoint refuses everything, which is the correct direction to
fail but is indistinguishable from a wrong secret - so the first live
click is the only thing that proves it.

---

## 2. Two provider capabilities are planned but unvalidated

`cadencegraph.UNVALIDATED` names them, and `campaignqa` blocks approval of any
cadence that uses one:

- **React to a post** (`post_reaction`)
- **Withdraw connection request** (`withdraw_request`)

Both are shapes a real ABM cadence wants and neither has been exercised
against HeyReach. They exist as node types so a plan can express the
intention; the QA gate refuses to let that intention ship.

---

## 3. Reply policy: wired, but three outcomes need a person to name them

**No longer a gap in the engine.** `accountpolicy.apply_reply` is the only
thing that moves reply state and every entry point comes through it, so a
"not interested" from one person no longer stops three colleagues nobody has
written to. `ACCOUNT-OUTREACH.md` §10 is the table.

The classifier reaches the two outcomes that must never be missed:

| Text | Outcome | Effect |
| --- | --- | --- |
| "remove me from your list" | `unsubscribe` | that person, permanently |
| "do not contact anyone at this company" | `account_do_not_contact` | the whole account, permanently |

The broader rule is tested first, because reading "remove us" as "remove me"
leaves colleagues contactable after a company asked us to stop.

What still needs a person is the vocabulary in between. These four reach the
policy only when somebody classifies them by hand, from the Reply Center:

- `wrong_person`
- `left_company`
- `existing_client`

`referral` came off that list. A reply that hands somebody on is classified
and a `referral_mentioned` event records what was said and what could be
proved about it - see `src/referral.py`. What that is *not* is a
`REFERRAL_RECORDED` edge: the mention names nobody unless the reply carried
an address or a profile we already hold, and a name resolves to `unknown`
however obvious it looks. The edge stays a person's decision, which is the
next gap under it.

Each is a *narrowing* outcome — it stops one person rather than the account —
so an unclassified one falls to `unknown`, which holds the whole company and
asks for review. The failure mode of the gap is over-caution, which is the
right direction for it to fail in.

**What it would take:** rule sets in `replies.py` for each, and a confidence
threshold decision per rule. `wrong_person` and `left_company` already have
partial coverage under `not_relevant`, which maps to `not_icp` — close enough
to be tempting and not the same fact, so it is left alone rather than
guessed.

---

## 3b. Provider tags: modelled, queued, never written

`src/tagsync.py` holds the canonical desired tag state, the adapter
interface, the outbox with retry and status, and the preview. What it does
not hold is a validated way to write one.

| Provider | State |
| --- | --- |
| EmailBison | custom variables round-trip for `subject` and `body`. A tag endpoint is named in the adapter so it is reviewable; nothing has confirmed it exists. |
| HeyReach | confirmed live 2026-08-26: `customFields` returns empty on every conversation and `/lead/GetLead` exposes none. Tags need HeyReach's own tag or list API, whose shape nobody here has seen. |

`tagsync.send()` raises `TagSyncRefused`. There is no code path in this
build that mutates a provider, and a mutation asserts that.

Two consequences worth stating plainly:

- **Provider tags are always stale in this build.** The outbox records what
  *should* be true. Nothing has told anybody.
- **Reconciliation is architected, not implemented.** Comparing desired
  against actual is only useful once a tag can be written, and no
  reconciliation may ever change canonical truth.

**What it would take:** one validated endpoint per provider, then a worker
that drains `tagsync.pending()` and calls `record_attempt`. Both seams
exist. See `ENGAGEMENT-HYGIENE.md` §7 and `LIVE-VALIDATION-PLAN.md`.

---

## 3bb. A CSV of people at one company - FIXED

A record is a company and contacts live on it. The import used to hold
only the first half of that: rows 2..N at a seen domain were excluded as
"duplicate row in this file", and `commit` built each record from `domain`
and `company` alone - so the `email` and `linkedin` columns were parsed,
used for hygiene matching, and then **discarded**.

A five-person list at one company therefore imported as one company with
*zero* contacts, while the upload screen told the operator that other
columns were "carried through". Both halves were wrong and the screen was
wrong about them.

Now a row carrying strong identity - a normalised mailbox or a canonical
profile URL, exactly what `dedupe` treats as identity - becomes a contact
on that company. A name is never identity, so five unnamed rows at one
domain are still one company and four repeated rows. The preview counts
companies and people separately, and says which rows were colleagues
rather than duplicates.

No new lane was needed: this is the architecture the record model always
described.

---

## 3c. External signal sources

None. Engagement history is first-party: it comes from this system's own
event log. There is no job-posting feed, no funding feed, no technology
detection, no news monitoring.

That is a gap in *coverage*, not in correctness - a list is checked against
everything Resonate knows, and Resonate knows what it did.

---

## 3d. Copy experiments: the engine runs, the copy is written by hand

`src/variants.py` assigns, measures, evaluates and shifts traffic, and
`campaignqa` checks every variant. What it does not do is *write* the five
variants.

The demo cadence carries five styles per message step
(`src/web/demovariants.py`). A real campaign's variants are written by an
operator in the campaign builder. The seam for generating them exists -
`STYLES_FOR` names the hypothesis each variant represents, which is what a
generator would be given - but no generation is wired, and no paid model
is called anywhere in this build.

**The wire is connected.** `cadence.expand_step` resolves the assigned
variant and calls `variants.apply_to_step`, so a step carries a
`variant_id`, the confirmed touch carries it, and `results_from` has a
denominator. Before that, no step carried one, so every experiment
reported `INSUFFICIENT_DATA` for ever - indistinguishable from an
evaluator waiting for volume. `tests/test_variant_cadence_end_to_end.py`
walks the chain from campaign to attribution.

Variants live on the campaign's step spec, beside `template` and
`variant_if_accepted`, which is where a sequence already keeps the
question of which words a step uses. `src/cadencegraph.py` holds variants
on its nodes as well, but its node keys are its own (`d1`, `d3`), it
contains branch, wait and stop nodes with no linear equivalent, and it is
still never stored on a campaign - so resolving a running step's node out
of a graph needs a mapping that does not exist. That remains open.

Two refusals rather than guesses: a generated step may not carry variants,
because its copy was written for that contact and a variant would replace
it wholesale; and a sequence read with no campaign assigns nothing,
because an assignment that cannot name its experiment cannot be reported.

**What is still written by hand.** The five variants themselves. There is
no authoring screen and no generator: an operator writes them onto the
campaign's steps. That is the remaining half of this gap.

Two smaller limits worth naming:

- **The experiment unit is the contact.** Account-level cohorting - every
  decision maker at one company seeing one style - is modelled nowhere.
  For a five-person account receiving five different styles that is a real
  coherence risk, and the honest position is that it is not addressed yet.
- **Evaluation is on demand.** Nothing recalculates on a schedule and no
  traffic shift happens automatically: `shifted_allocation` computes the
  new shares and an operator applies them. That is deliberate for a build
  where nothing sends, and it is not the eventual design.

---

## 3e. Account intelligence: first-party only

`signals.py` and `priority.py` derive, decay, weight and explain. What they
have nothing to read is the outside world.

**Every account-level and person-level signal in this build is manual.**
There is no job feed, no funding feed, no technology detection, no news
monitoring and no scraping. Nothing in `signals.py` calls anything. The
demo's hiring surges and funding rounds are fictional entries written by
`src/web/demosignals.py`, marked "Entered by a person" on every screen.

What *is* real is the engagement half: replies, referrals, meetings and
confirmed touches are derived from the event log every time they are asked
for, and those are the signals a score mostly rests on today. The default
weights reflect that - signal strength is 0.20 rather than more, because
weighting it heavily would be weighting a number that is mostly zero.

Two further limits worth naming:

- **No score history.** `assess()` answers "what is Acme's priority now".
  It cannot answer "why was Acme 92 on 1 October", because nothing is
  snapshotted.
- **No scheduled recalculation.** Scores are computed on read, every read.
  A per-account cost of about 0.3ms is fine for a page and is still 9
  seconds for 30,000 accounts, so the reporting screens will need either a
  cached assessment or a narrowed default before an audience that size is
  usable. Nothing here is quadratic any more, which it was: `for_record`
  re-read the whole signals file per account, so 500 accounts against a
  5,000-signal file took 19 seconds and 2,000 took 96. `signals.index()`
  is read once and handed down, and a test counts the reads rather than
  the seconds so it cannot go flaky. The remaining cost is linear and
  measured.

**A signal can be entered and never taken back.** `signals.jsonl` is
append-only and there is no retraction path - no edit, no withdraw, no
"that was wrong". A mistyped or mistaken observation keeps scoring until
its half-life carries it under the stale line, and on a funding signal
that is six months. The audit log records who entered it, so the mistake
is attributable; it is just not reversible from any screen. The right fix
is a retraction *row* rather than a delete - the file is append-only on
purpose, and "we recorded this and then withdrew it" is a different fact
from "this was never recorded".

**What it would take:** one validated provider contract per source, and a
`provider` writer into `signals.jsonl`. The model, the decay, the storage,
the tenancy filter and the screens all already take a provider signal
without changing.

---

## 3f. Large audiences: measured, not assumed

`store.load()` parses the whole queue on every call and caches nothing.
That is fine once per screen and quadratic in a loop, and it was in a
loop three times. Measured on synthetic estates, 8 campaigns, 5 batches:

| | 1k | 5k | 30k |
| --- | --- | --- | --- |
| `store.load()` | 0.01s | 0.03s | 0.28s |
| `batch_list` before | 0.04s | 0.30s | 2.48s |
| `batch_list` after | 0.02s | 0.11s | **0.85s** |
| `campaign_rows` before | 0.09s | 0.59s | 9.86s |
| `campaign_rows` after | 0.03s | 0.06s | **0.31s** |

`campaign_rows` was the worst and for two reasons at once: a full parse
per campaign, *and* `id in record_ids` against a list, so the membership
test was itself linear. Six times the data made it 16.7 times slower.
Both are indexed now and the growth is linear.

**The suppression file, read once per contact.** `channels.evaluate`
loads it whenever it is not handed one - correct for a single contact,
once per contact across an estate. Seven call sites were inside
per-contact loops. `analytics_rows` was the worst: it loaded the set
correctly and then never passed it, so the variable sat there looking
like the fix.

| at 30,000 records | before | after |
| --- | --- | --- |
| contacts page | 7.47s | **0.60s** |
| analytics rows | 9.22s | **1.86s** |
| companies page | 0.47s | 0.44s |
| search | 0.34s | 0.33s |

Tests count reads rather than seconds, and assert the count does not grow
when records are added.

**What is still true at 30,000 records:**

- `search` is 0.38s - one parse plus a scan, and inherently a scan
  without a search index. Acceptable, and measured rather than assumed.
- `priority.assess` costs about 0.3ms per account. The 9-second estimate
  recorded here earlier was **wrong**: measured, the analytics path was
  dominated by the per-contact suppression read, not by scoring, and the
  whole path is 1.86s once that is fixed. The signal dashboard scores
  every account and caps its output at 200; it is 1.21s at 30,000.
  Scoring is not currently the bottleneck, and this entry previously said
  it was.
- **The two big list screens paginate; the rest do not.** `/companies`
  and `/contacts` take one window of 100 rows (`api.paginate`, capped at
  500, with `pages.pager` reporting the total beside it), so the largest
  screens no longer try to render 30,000 rows of HTML. This entry said
  "nothing paginates" twice until the release-candidate audit read the
  routing table; that was true when it was written and stopped being true
  in `3f63415`.
- What still returns everything is every screen that is not one of those
  two - segments, ICP review, senders, the audit log. None of them is a
  30,000-row screen today, and none of them is windowed either, so the
  next audience an order of magnitude larger meets them first.

**What would change the rest of it:** an assessment cache keyed by record
and its event count. Pagination is done where it was measured to matter
and undone everywhere else.

---

## 3g. Discovery has no source, and the delta has no CRM

`discovery.py` computes the difference correctly and there is nothing
connected to feed it. Every candidate in this build comes from a fixture
or a person, and says which - `SOURCES` names `provider` so an
integration has a shape to fill.

    LIVE DISCOVERY PROVIDER REQUIRED

The delta is checked against six things this system holds and one it does
not: the client's CRM. That gap is reported on every result rather than
left in a document, because a delta computed without a CRM is not a
smaller delta - it surfaces the client's own open opportunities as fresh
leads, which is the single most embarrassing thing this product could do.

    LIVE CRM CONNECTOR REQUIRED

Agency-wide DNC is a third absence and a different kind: it is
person-level, and a candidate is a domain with nobody attached yet. It
applies at `hygiene`, once contacts exist. `known()` names it, because
"we did not check" and "there was nothing to check" are different
sentences.

**Learning has no volume yet.** The demo estate has 11 contacted accounts
across 6 cohorts, so every cohort is `INSUFFICIENT_DATA` and the screen
says so. That is the honest answer at this size and the module is built
to give it rather than to find a winner in three accounts.

---

## 4. Figures nothing here can observe

`report.unavailable()` is the canonical list, and every client report prints it
as an appendix rather than as zeros:

| Figure | Why not |
| --- | --- |
| Meetings booked | needs a calendar or CRM integration, or somebody marking it |
| Opens | only if the sending platform reports them, and they are unreliable |
| Actual credits per record | ContactOut reports usage per account, not per call |
| Email + LinkedIn eligibility | runs after enrichment, which has not run |

The meetings section of a client report is a paragraph explaining that
"let's chat" is an intention, not a meeting. That paragraph is the feature.

---

## 5. One process, one writer

`work/queue.jsonl` and `work/campaigns.jsonl` are rewritten whole under an
advisory lock. Two workers cannot enrich two halves of a batch at once.

The trigger for changing this is specific: **when two processes need to write
at once.** Not sooner. `DATABASE-MIGRATION.md` holds the schema to build
against and the three properties that keep the migration cheap.

---

## 6. Sessions live in memory

`web.security.Sessions` holds them in one process's dictionary. A restart logs
everybody out.

That is the correct trade for an operations tool with no user database: the
alternative is persisting session material to disk, which is a new place for a
secret to live. It becomes wrong the moment there is a second process, which
is the same trigger as §5.

---

## 7. No inbound mail or message ingestion

Replies enter the system through `events.record`, which means somebody or
something has to put them there. There is no IMAP poller, no webhook receiver,
no provider callback endpoint.

The reply classifier, the account graph, the pause logic and the claim
resolver all read recorded reply events, so the integration point is small and
well defined — but it is an integration point, not an integration.

**What it would take:** a receiver that writes `REPLY_RECEIVED` with a
`provider_event_id`, which is already the idempotency key
`events.event_id` uses to refuse a duplicate.

---

## 8. Sender rotation is allocation, not scheduling

`assignment.allocate` decides *which* human and which inbox carries a contact,
and `fatigue` decides whether a touch is allowed *at all*. Neither decides
*when* within a day, and nothing here models an inbox's warmup curve over
weeks.

`senderidentity` records a daily capacity per account and the capacity screen
reports it, so the ceiling is visible. Spreading sends across a working day is
the sending platform's job in this design, and is unverified against a real
one.

---

## 9. Timezones are read, never guessed

`/timezones` reports what is known. A contact whose timezone cannot be derived
from recorded evidence has no timezone, and no send window is inferred for
them. `CLAUDE.md` states the rule: a guessed timezone is worse than a missing
one.

The gap is coverage, not correctness — most contacts have no timezone because
nothing has looked one up.

---

## 10. The client viewer is read-only

A `VIEWER` role can read reports and dashboards for its own workspace. There
is no client-side approval, no comment thread, no request queue. A client who
wants a change tells their operator.

---

## 11. Three modules still measure the default cadence

`cadence.build` takes the campaign a timeline is being built for, and
`steps_for` resolves both the campaign's own sequence and the contact's
assigned cadence arm from it. Everything that approves, sends, gates,
previews, plans, reports or QAs now passes it.

Three do not: `benchmark.measure`, `simulator.company_card` and
`demo_outreach`. Nothing in their call paths has a campaign - they measure
build cost, simulate a batch, and construct the demo estate - so they
build the seven-step constant.

**What this means in practice.** A benchmark reports the cost of the
constant rather than of a four-step campaign, and the simulator's company
card shows the constant's steps. Neither sends, approves or gates
anything. The demo estate's campaigns carry no sequence of their own, so
for them the constant *is* the right answer.

They are named here rather than given a `campaign=` parameter nobody
passes, because a parameter with no caller is a wire that looks connected
- which is the exact defect this sweep existed to remove.
`tests/test_campaign_cadence_sweep.py` lists the swept modules and fails if
one of them regresses.

---

## 12. There is no authentication, and the build now says so out loud

Signing in is picking an email address out of a list. The workspace
membership table decides what that person may do and it is checked on
every request; nothing at all decides whether they are that person.

For an operator on their own machine that is the design, not a hole - the
person at the keyboard is the person. It stops being the design the moment
the port is reachable by anybody else, which is why
`web.app.check_configuration` refuses `APP_MODE=production` outright and
refuses any non-loopback bind that is not serving the fictional estate.

**The refusal is not the fix.** It is the honest encoding of a missing
feature, the way `push.run(live=True)` raising is. What closes this is
`LIVE-VALIDATION-PLAN.md` §5.1: a real identity provider, and then
`security.sign_in_proves_identity()` returns True and both refusals lift
together. Until somebody makes that decision, the only thing this
repository can publish is the demonstration.

Two consequences worth stating rather than discovering:

- `SESSION_SECRET` is required in production and read by nothing. Sessions
  are in-process random tokens (§6), so it is a name reserved for the
  session store that does not exist yet.
- Secure cookies and HSTS are absent for the same reason TLS is: there is
  no deployment that terminates it. Adding a `Secure` flag now would sign
  the operator out of their own loopback.

---

## 13. The copy experiment screen has no campaign to read

`campaign["cadence_graph"]` is read by `campaignqa`, by the campaign
builder, by the plan-level QA and by the copy experiment screen. **It is
written by nothing.** That was already recorded as the one open instance
of this codebase's recurring defect; what the release-candidate audit
found is what the screen did about it.

It fell through to `web/demovariants.py`, whose exposure and outcome
totals are planted so that a demo can show five experiment states without
four thousand touch events in the estate. The evaluator reading them is
production code, which was the point - and because nothing writes
`cadence_graph`, the fallback fired for every real campaign, always. The
screen captioned the numbers as fictional and that caption was true. It
was still the wrong default: an operator asking what their campaign is
doing should be told nothing is configured, not shown somebody else's
numbers with a note underneath.

The fallback now takes `demo` from the process, so only `--demo` reaches
it, and a real workspace is told there is no cadence graph.

**What this does not affect.** The variant chain that matters does not go
through this screen: `cadence.expand_step` resolves the assigned variant,
`variants.apply_to_step` writes it into the payload, the confirmed event
records which variant was actually exposed, and attribution reads the
event. That path is covered by `test_variant_cadence_end_to_end.py` and is
unchanged.

---

## 14. The Railway config format has a deadline on it

`railway.json` works and was used for the deployment on 2026-09-02. The
CLI warns on every command that Config as Code is deprecated in favour of
Infrastructure as Code (`.railway/railway.ts`), and that **existing files
keep working until 2026-12-01**.

Recorded rather than migrated. Migrating today would trade a format that
is proven against a real build for one that is not, months before it is
needed, and `.railway/railway.ts` is TypeScript - a build step and a
dependency in a repository whose deployment advantage is having neither.
`railway config migrate` is the path when the date gets close.

What must not happen is discovering it in December. That is what this
entry is for.

---

## 15b. An out-of-office is read, and a person is told when they are back

`src/ooo.py` answers the two questions the reply category cannot carry:
whether a person or a mail system wrote it, and when they said they are
back. Both are recorded on the record as an `out_of_office_recorded`
event whenever `replies.apply` classifies an out-of-office, so the
reading is canonical history rather than something re-derived later from
a message that is gone.

`src/oooreturn.py` waits for the date. `python -m src.oooreturn` reports
who is back, who is not due yet, who was closed in the meantime, and who
never gave a readable date. Every re-check happens at the moment the date
comes due, not when the absence was recorded.

**It does not lift anything.** An out-of-office maps to `NOT_NOW`, whose
plan is `replier=stop`, so an autoresponder stops that contact exactly as
a refusal does. `oooreturn` is allowed to look past that one stop - the
deferral it is following up, identifiable because `not_now` is written for
`out_of_office` and nothing else - and past nothing else. It never clears
it. A scheduler that reopened a person because a date arrived would be the
only thing here able to do that automatically, on the strength of a regex
reading of an autoresponder. `DUE` is a verdict a human acts on.

`/replies/returns` surfaces the same three queues in the web app, under
Inbox: who is back, who did not give a readable date, and who is not due.
It is a screen with no buttons - rendering it lifts nothing, which has its
own test, because a view is the last place anybody would look for a write.

What is still missing is the step after the verdict: nothing turns a `DUE`
row into a drafted, approved message. A person reads the row and starts
the work the same way they would for any other account.

One related thing is deliberately unbuilt rather than half-built:

- **The category question.** `replies` puts `OUT_OF_OFFICE` above
  `POSITIVE` on purpose, so "yes, this is relevant - I'm away until the
  8th" is categorised as an out-of-office and raises no alert. `ooo.detect`
  now separates the facts underneath it (a human wrote this; here is the
  date), but whether a human absence carrying genuine interest should
  reclassify is a business decision about who gets woken, and it has not
  been made. See `tests/test_ooo.py::test_that_fixture_still_classifies_as_out_of_office_today`,
  which states the current behaviour rather than endorsing it.

  `NOT_NOW` now sits in the same place for the same reason: "sounds good,
  try me in Q1" is read as a date rather than as warmth, so it does not
  alert either. The two rankings are one decision - whether a message
  carrying warmth *and* a timing instruction should wake somebody - and
  they are recorded together here so they cannot be answered differently
  by accident.

  A different question, already settled: `NOT_NOW` is tested *after*
  `NEGATIVE`. "No thanks, maybe try us in Q1" is a refusal with a
  politeness on the end, and reading it as a future appointment would put
  a follow-up in front of somebody who said no.

A return date that could not be read is recorded as unknown with the
reason - `unknown:ambiguous_numeric_date`, `unknown:vague_period`,
`unknown:month_without_day`, `unknown:not_stated`. A numeric `08/09` is
never read: it is 8 September or 9 August depending on a locale nobody
recorded, and guessing moves somebody's return by a month.

---

## 15a. The timer exists; a day of it running does not

`src/poller.py` works and is now live-validated against EmailBison, and
`src/replywatch.py` now runs it on an interval from inside the web
process - supervised, locked against a second replica, and off unless
`REPLY_POLL_ENABLED` is set. `src/digestwatch.py` rides the same thread
for the daily summary. Both are correct against the clock and neither has
ever run for a day on the deployed service, which is the only thing that
proves a schedule: a timer that stops silently looks exactly like a quiet
week.

What is left of this gap is that validation, and one consequence of the
design being honest about it - with `REPLY_POLL_ENABLED` unset, which is
the default everywhere including production, replies are still ingested
exactly as often as somebody types the command.

Two live-only defects were found and fixed on 2026-09-02 while proving
this path, both of which the offline fixtures had hidden:

1. `fetch_replies` never sent `pagination_type=cursor`, so the cursor it
   read was always absent and the poller could not advance past its first
   15 rows.
2. The feed is newest-first and its cursor bounds the page to *older*
   rows, so the stored cursor walked backwards into history. A reply
   arriving after a checkpoint would never have been seen.

Both are fixed. The scheduling gap is not, and it is the remaining
blocker on reply-driven safety: the cadence-stopping guarantee in
`ACCOUNT-OUTREACH.md` is only as timely as the last manual poll.

---

## 15. Canonical state knows nothing about the outreach already running

**This is a P1, and it was found by looking rather than by reasoning.**

A live read of HeyReach on 2026-09-02 found 42 campaigns in progress for
this agency, 51 of the 76 named for Productive, across 39 distinct
LinkedIn sender accounts, with roughly **160,000 prospects currently
mid-sequence**. EmailBison holds 15 campaigns and is sending nothing.

Every pilot plan in this repository was written for a workspace with no
existing outbound. That assumption is false.

`ENGAGEMENT-HYGIENE.md` is the right design for this - a new list is
checked against canonical engagement state before anybody spends a credit
on it - and canonical engagement state has never been told about any of
those people. So the check would pass, and the prospect would experience
one company approaching them twice, from two senders, about two things.

**What would close it**, and none of it is built:

- an import of provider-side engagement into canonical state, or a
  pre-send check that asks the provider directly;
- a decision about precedence when both systems want the same person;
- the same question for EmailBison before its campaigns are unpaused.

**What must not happen meanwhile:** a Productive pilot that selects
contacts without knowing whether HeyReach is already talking to them.
`RELEASE-CANDIDATE.md` §9 says email-only and one sender for the first
run, which reduces the collision surface but does not remove it - the same
person can be in a LinkedIn sequence and reachable by email.

---

## 16. No reply is stored, only the fact of one

`events.apply` records that a reply arrived - when, on which channel, from
which provider - and never what it said. The excerpt that reaches a Slack
alert is built from the text as it passes through `replies.classify` and is
not written down anywhere.

So the conversation view on a contact is a thread of *what happened*, not
of what was written, and it says so on the screen rather than showing empty
quotes. An operator who wants the words opens the inbox the reply arrived
in.

Whether to close this is not an engineering decision. Storing a prospect's
message body in `work/queue.jsonl` is a data-protection question with a
retention period attached to it, and the person who answers it is not the
person writing the parser.

**What it costs meanwhile:** the classifier's verdict cannot be checked
against the text after the fact, so a misclassification is only visible if
somebody still has the original message.

---

## 17. A step that went out after a reply is reported, not prevented

`conversation.thread` flags a confirmed touch whose timestamp is later than
a reply from the same person, on either channel. That is a report about
something that already happened, and it is deliberately not a verdict: it
says a step went out after they answered and leaves the judgement to
whoever is reading.

The prevention is elsewhere and it is real - a reply pauses the whole
company in `events.apply` before anything is classified. What this flag
catches is the case that pause cannot: a sequence already running inside a
provider, which this build does not control. That is §15 seen from the
other end, and it will read zero until something is actually sending.

---

## 18. What a client's CSV can still be that this cannot read

The importer now sniffs the delimiter by trying each candidate and keeping
whichever produces a column that identifies the company, so a semicolon or
tab export - the default across most of Europe and from a good number of
CRMs - is read rather than refused. What is still missing:

- **XLSX is read, with two things it gets wrong.** An `.xlsx` is a zip of
  XML and both are standard library, so `src/web/xlsx.py` reads one and
  hands the rest of the import path the bytes a CSV would have arrived as.
  It reads the **first sheet only** - a workbook whose leads are on the
  second tab imports the first, and the preview names which sheet it read
  so that is noticeable. And a **date arrives as the serial number** Excel
  stores, because the cell format lives somewhere this does not read. No
  canonical column is a date, so the worst case is a provenance column
  carrying a number.
- **No operator override for column mapping, deliberately.** Two headers
  spelled the same are equally the field, and picking one is a coin flip
  over whose values are real - a question only the file can answer. The
  preview names the columns and says to delete or rename one. Two headers
  spelled *differently* for one field are the common case and are settled
  by rank, not refused.
- **Phone and mobile have no canonical column, deliberately.** Nothing in
  this build would read one - there is no phone channel and no dialer - so
  a canonical field would be state computed correctly and consumed by
  nobody, which is this codebase's own recurring defect added on purpose.
  A phone-first list still arrives as identity-less company rows, because
  a phone number is not an identity here. What changed is that the numbers
  are recoverable: `/export/contacts.csv` hands back every column an import
  kept, as `source:` columns, capped at twenty and saying so when it caps.

---

## 19. What the persona editor still leaves in the file

`/settings/personas` covers a persona's name, titles, per-company cap and
angles. Two things are still file-only:

- **`start_offset_days`**, which staggers one persona's track behind
  another's. It is a cadence decision rather than a targeting one, and the
  screen would have to explain the whole timeline to ask for it.
- **The band-to-persona mapping** in `PLAYBOOK.md` §5, which decides which
  persona family a company's size routes to.

And one degradation worth naming rather than hiding: a persona saved with no
angle still selects people, and their messages fall back to general wording
(`cadence.angle_words`) instead of the client's own phrasing. On the
`domains` lane the generator queues a `persona_angle` step for it, and this
build ships no model, so that step is never run. The screen says so on the
row; nothing fails, and the copy is worse.

---

---

## 20. Report sections that read fields nothing assembles

Every rate on every reporting surface was walked back to the code that
writes the field it counts. Five defects were found and fixed - the
verification tiles, the funnel's stored flag, the sender report's double
count, the bare pass rate and the meeting tile; see
`tests/test_reporting_honesty.py`. What is left is recorded here rather
than half-fixed.

**Five sections of the monthly and detailed templates read keys no code
produces.** `clientreport._linkedin`, `_pipeline`, `_accounts`, `_senders`
and `_trend` read `data["linkedin"]`, `["pipeline"]`, `["accounts"]`,
`["by_sender"]` and `["months"]`; `api.report_data` assembles none of them.
Four rates - LinkedIn acceptance, LinkedIn reply rate, per-sender reply
rate and month-over-month reply rate - therefore cannot be computed at all.
Each section now says it has nothing behind it rather than printing `n/a`,
but the wording still describes an empty *period* ("No LinkedIn activity
has been confirmed in this period") when the truth is an unassembled field.

**Everything downstream of a confirmed send is structurally zero.** Nothing
outside the demo estate writes `PUSH_MARKED` - `push.run(live=True)` raises
- so `emails_pushed`, `reached`, the funnel's "Confirmed sent" and every
rate whose denominator is one of those reads 0 or `0 of 0`. The prose says
so in three places; the tiles print `0`. That is the honest number for a
build that cannot send, and it will stop being confusing the moment one can.

**A period with no deliveries reads the same as no instrumentation.**
`report.for_client` returns `counts[EMAIL_DELIVERED] or None`, so a hundred
sends with zero confirmed deliveries and a period with no delivery webhook
both render `n/a` - under a note promising this reads `n/a` rather than 0.

**`observations` counts held as `contacts_found - reachable`** and explains
it as verification failure, disagreement or email security. That
subtraction also contains every contact with no address at all and every
LinkedIn-only contact, neither of which is any of the three reasons given.

**A persona and angle `positive_rate` is computed and rendered nowhere.**
`report.by_persona` and `by_angle` compute it; `clientreport`'s breakdown
table emits only the name and the contact count. It is `None` in any case,
being gated at thirty confirmed touches.

**The funnel chart draws a bar for zero.** `Canvas.bars` uses
`max(1.0, ...)` for the filled width, so a stage with a count of nothing
still shows a short bar.

**The credit cap does not reach Apify.** An actor run is billed in
compute units rather than credits, so `COSTS["apify-research"]` is zero and
`Budget.affordable(0)` is true at any cap. The run is recorded through
`spend()` now - it writes the `PROVIDER_CALL_PLANNED` event and the
waterfall step, so the spend audit can see it, which it could not before -
but nothing bounds compute-unit spend the way `--cap` bounds credits. What
bounds it is per record and upstream: a stated need from `research.why`,
the client's own `enabled`, `--live`, and `max_items_per_run`.
`tests/test_research_spend.py` asserts both halves, including that the cap
does not refuse one.

**A test reloads `src.providers` in process, and every later test has to
know.** `tests/test_audit.py` proves no module reads a credential at import
by reloading twenty-three modules, and a reload mints a fresh
`ProviderError` class. Any module or test holding the name from before the
reload stops matching what is raised after it - and because `src.providers`
sits eleventh in that list, the modules reloaded before it keep the old
class while the providers reloaded after it raise the new one, so which
half a file lands in depends on import order. `src/poller.py` resolves the
class at call time and says why; the fix for the suite as a whole is to run
that check in a subprocess, which is a change to a tracked,
mutation-anchored test rather than something to fold into an unrelated
diff.

**Two HeyReach readers have no production caller.**
`heyreach.is_from_correspondent` and `heyreach.unknown_directions` are
reached only from tests; the live path is `poller` to `inbound` to
`adapters.from_heyreach`, which calls `inbound_messages` alone. They are
correct and documented, and they are not wired to anything.

**HeyReach reply polling: closed 2026-09-07, and how.** The offset
checkpoint was replaced by a high-water mark on the message timestamp, and
the walk could not stop early because nothing documented the inbox
ordering - so a run read `MAX_PAGES x PAGE_SIZE` = 250 conversations of a
real 25,473, about one per cent, and the mark never advanced because a run
never drained anything. Reading the inbox settled it: `lastMessageAt` was
monotonically non-increasing across 200 conversations, four pages and
fifteen hours of live traffic, with no inversion. That licenses stopping
at the mark, the way `poll_emailbison` already does, so a run now reads
everything new since the last one.

The licence is checked rather than remembered. `_descending` tests the
page in hand before the stop fires, so a provider that reorders its inbox
stops satisfying it and the walk falls back to reading every page it can
afford - less coverage per run, and never a silently skipped reply. Both
directions are mutation-anchored.

**Two more collections are still coerced to empty.** `src/mapping.py`
`bison_campaigns` and `src/providers/apify.py` still do `rows if
isinstance(rows, list) else []`. Both are off the reply path, so an
envelope change reports a real campaign as MISSING rather than UNKNOWN
instead of losing a reply, but it is the same defect as the one fixed in
`bison.fetch_replies` and `heyreach`.

**An unmatched reply has no control at all.** The inbox says "nobody knows
who this is" and there is no route anywhere that matches a reply to a
contact - `app.py` has five reply routes and none of them does it. The
only action available is marking it handled, which does not answer the
question the row is asking. This is the orphaned-control defect one level
deeper: it needs a route, not a link.

**A vendor name is an unvalidated string, so two confirmations may be one
vendor.** `confirmations` keys on `entry["provider"]` verbatim, and
`result()` accepts anything. Evidence naming `contactout` and `Contactout`,
or `contactout` and `contactout-v2`, counts as two independent
confirmations and builds a payload. Not reachable from provider code today
- `verification.call` only ever emits three literals and `deliverable`
hardcodes its own name - so it needs hand-edited queue state or a future
adapter. The fix is to intersect `confirmations()` against a known-vendor
set.

**A client policy stricter than two confirmations is not enforced on the
push path.** `push.emailbison_rows` calls `verify_before_payload(item)`
with no config and `eligibility._email_checks` calls
`verification.resolve(contact)` with no policy, so both fall back to
`DEFAULT_POLICY`. A workspace that set `required_confirmations: 3` is
gated at 2. It cannot go *below* two - the same hardcoded default is what
makes a hand-edited `required_confirmations: 1` harmless - so this is a
stricter policy silently not applied rather than a weaker one silently
accepted.

**One person split across two contacts defeats the cross-channel stop.**
`enrich.merge_contacts` dedupes on a single raw marker, so a decision maker
returned by ContactOut with a profile and no address, and by AI Ark with an
address and no profile, becomes two contacts. `eligibility._replied` and
`_paused` are scoped to `contact["key"]`, and the only identity-based guard
reads `contact["duplicate_of"]` - which nothing in `src/` writes:
`dedupe.find` and `dedupe.mark` have no production caller. So a LinkedIn
unsubscribe leaves the same human's email sequence eligible. The narrow fix
is to make `_replied` match on `dedupe.keys_for` rather than on the key;
wiring `dedupe.mark` into enrichment is the larger correct one.

**A reply delivered late overwrites a newer verdict.**
`accountpolicy.classify_outcome` walks `rec["events"]` in insertion order
and keeps the last one it sees, without comparing `at`. A reply delivered
out of order but dated earlier wins, so a positive reply on file can be
replaced by an older refusal - and `cadence.pause_state`'s third source,
the documented safety net, then reports the account free to contact. The
fix is to select the greatest readable `at`, and to treat an entry with no
readable timestamp as unable to replace a dated one.

**The reply policy is read and never written.** Both production callers of
`apply_reply` pass no config - `events.apply_reply_policy` passes
`config=None` explicitly and `replies.apply` omits it - so the transition
is always written from the built-in defaults, while the read side does
honour the workspace config. A workspace that sets `reply.on_negative` to
`review`, which the settings screen offers, never gets a review opened. The
direction is fail-safe; a screen asserting a safety behaviour the engine
does not have is not.

**Fatigue is documented as blocking at QA time and gates nothing.** The
only `fatigue.BLOCK` consumer is `campaignqa.review`, whose sole caller is
the read-only approval screen. `campaigns.CHECKS` has no fatigue check and
neither has `eligibility.decide`, so the account-level limits - DMs active
at once, hours between opening two people, touches per company per week -
bind nowhere. The documented four-senders-in-two-days failure is not
prevented.

**Controls that exist for routes nobody can reach.** `POST
/senders/reassign` has no renderer anywhere, so a prospect assigned to the
wrong human cannot be moved; `senders_page` even accepts `csrf` and
`can_manage` and uses neither. Onboarding marks three sender steps required
and points at `/senders`, which has no create form and no route behind one,
so setup cannot be completed in the product. A member can be added and
never removed - `workspaces.remove` exists, is audited, and has no route.
`POST /strategy` accepts `supersedes` and no control renders it, so the
"superseded" counter and panel can never populate. Pause is offered on
every campaign regardless of status and resume runs the full launch
validation, so pausing a draft in a build with no provider keys is a
one-way door.

**Two smaller tenancy findings, both reproduced.** `/workspaces` renders
the full member roster with no permission, duplicating what `/users` gates
behind `USERS_MANAGE` - and `workspace_list` accepts a `can_manage` the
caller computes and the page never reads. `/reporting/senders` passes its
`dimension` through raw, unlike every other reporting route, so a viewer
can enumerate mailbox and LinkedIn account ids. And `/select-workspace`
changes session state on a GET with no CSRF token; membership is still
enforced, so it is a state-changing GET outside the fence rather than a
tenancy break.

**A templated issuer would reject every sign-in, and only a live read
showed it.** `oidc.verify` compares the `id_token`'s `iss` against
`document["issuer"]` for exact equality, which is right. Fetching
Microsoft's real multi-tenant document returns the issuer as the literal
template `https://login.microsoftonline.com/{tenantid}/v2.0`, while a real
token carries the tenant's GUID in that position - so the two can never be
equal and every Entra multi-tenant sign-in would be refused as "issued by
a different issuer". Google's document returns a literal issuer and is
unaffected, as is a single-tenant Entra endpoint. The loopback fake the
71 auth tests run against returns a literal issuer too, which is why no
offline test could find this. `PRODUCTION-AUTH.md` names Entra as one of
the two options a person may pick, so the choice matters. Not fixed by
relaxing the check - substituting the `tid` claim into the template is
provider-specific validation logic and a real piece of work; what is done
is that `discover` now refuses a templated issuer at configuration time,
with a message naming the problem, rather than letting it surface as a
confusing rejection at somebody's first sign-in.

**No real campaign can be given a cadence experiment.**
`orchestrator.set_cadence_experiment` is the only thing that attaches one,
and it has no caller anywhere outside the test suite - no CLI subcommand,
no route, nothing in `src/`. So `assign_cadence_arms` is a no-op for every
campaign that exists, and `cadenceexposure`, `cadencematurity`,
`cadencereplies`, `cadencereport`, `cadencesafety` and `cadencevalue` all
read a key nothing writes. The function's own docstring names this - "the
exposure accounting and the whole report were unreachable from a real
campaign. Which is the failure this repository keeps producing and the one
the cadence mission was written to measure" - and it is still true one
level up: the setter is reachable, and nothing reaches it. Wiring
`prepare` into campaign creation, which is done, closes the *assignment*
path; authoring an experiment is a feature and is not one to invent while
clearing defects.

**The stop button nobody can press.** `orchestrator.freeze` and
`unfreeze` have no caller anywhere in `src/` - no CLI subcommand, no
route, no page control - and their only callers are tests. The state they
write is read by three places that matter: `eligibility._campaign` checks
it *before anything else*, with a comment saying a freeze outranks
approval and staleness "because it is the stop button"; `campaigns.CHECKS`
refuses to launch a frozen campaign; and `audit` reports it. So it is a
guard the send path consults first and nothing reachable can set.
`RELEASE-CANDIDATE.md` describes it as available to any reviewer.

Not fixed here, deliberately. Pause is reachable, and as of 2026-09-07 it
blocks at the eligibility gate rather than only at launch validation, so
an operator does have a working stop. Adding a freeze route is new
surface, and a readiness pass is the wrong moment to invent one.
`killswitch.campaign_state` *was* fixed: it checked `paused` and not
`freeze`, so the screen an operator opens to ask whether a campaign would
send answered yes for a frozen one while the send path refused it.

**The test suite wrote into the real `work/` directory, and did for a
long time.** Fixed 2026-09-07. `tagsync.path()` derives from
`store.queue_path()` under a comment saying that path "is already
redirected by every test", and two classes in `test_demo_outreach.py` were
plain `unittest.TestCase`: they called `demo_outreach.gather()`, which
writes the provider tag outbox, with the store still pointing at the
working copy. Every full run appended to the real `work/tag-outbox.jsonl`,
which had reached 2.8MB over 6,410 rows. One of the two classes was called
`TestNoNetworkAndNoMutation`, and its
`test_nothing_is_written_to_the_queue` was reading the real queue to prove
nothing had been written to it.

Worth recording how it was found, because the obvious methods all missed
it. It does not reproduce per module - run `test_demo_outreach` alone and
the file is untouched, because whichever class runs first leaves the
environment redirected - and it is not an import-time write. Hashing all
eleven `work/` files across a full suite showed exactly one changed, which
bounded it; running all 205 modules in one process with the file hashed
between each named it. A first attempt that instrumented `tagsync.path()`
to log a stack trace broke 2,261 tests and produced no log, and was
reverted: diagnosing a test-hygiene defect is not worth editing production
source.

Nothing else was affected. The queue, campaigns, audit, workspaces,
signals, senders, notifications, checkpoints and report-drafts were all
byte-identical across the same run, so no canonical state was ever at
risk. `tests/test_invariants.py` now refuses a bare `unittest.TestCase`
that writes state without redirecting the store, which is the property
rather than the instance.

**The workspace kill switch enforces nothing.** `sending.live` is a real
policy key: settable on `/settings`, audited, rendered, and documented as
"the second lock". Its only reader is `killswitch.workspace_state`, and
`killswitch` has **no importer anywhere outside its own tests** -
`eligibility` never reads a workspace policy at all. So an operator who
sets it to `off` and believes the workspace is stopped is wrong. It is
harmless today only because `push.run(live=True)` refuses in code, which
outranks it; it becomes the most dangerous defect in the system the moment
that refusal is lifted. Wiring it means enforcing it in `eligibility`, and
that is not a small change: absence is `off` by design, so every workspace
and every fixture would have to be switched on explicitly. The setting's
own `why` text now says it enforces nothing.

**Neither is the per-sender disable.** `eligibility.decide` and
`push.verify_before_payload` contain no reference to sender, assignment or
health. The health filter added on 2026-09-07 applies at *allocation*, and
`assignment.ensure` skips a contact that already has a stored assignment
while `push._sender_of` reads that stored row without rechecking - so
pausing an inbox does not stop contacts already assigned to it.
`senderidentity.set_active` has no caller, there is no `set_health`
function at all, and `POST /senders/reassign` has no form.

**A record in two live campaigns has no campaign gate.**
`campaigns.by_record` maps it to `None` deliberately - guessing which
sequence it is in would put somebody in an arm nobody chose - and the
consequence is that `eligibility._campaign` receives `campaign=None` and
returns `None`, so pause, rejection, freeze and approval staleness all
stop applying and the record falls back to the default cadence. The
ambiguity is documented; this consequence is not.

**Nothing can write the agency DNC list.** `agencydnc.add` has no caller
in `src/`. The list is read at intake by `hygiene`, and is not consulted
at the send boundary at all.

**No route lifts an account or contact pause**, though `pages.py` tells
operators the control is on the company's screen. Recovery is
`python -m src.store patch` only.

**Verifier credits bypass the spend ledger.** `verification.verify` calls
`budget.charge` directly and never routes through `enrich.spend()`, which
is the only caller of `waterfall.record_step`. `enrich.COSTS` and
`CALL_STAGE` carry entries for `email-verifier`, `deliverable-verify` and
`reoon-verify` that nothing ever spends against, and `waterfall.audit`
reports `steps: 0` for a record that just spent two credits an address.
Against the rule that every paid call goes through `spend()`, this is the
"audit that reports clean because it watched nothing" case by name. For a
20-contact pilot that is roughly 40 unledgered credits.

**EmailBison workspace isolation cannot be asserted, and the hazard was
observed live (2026-09-07).** One credential sees 13 workspaces, and which
one it reads is *implicit in the credential's own context* rather than
anything Resonate states or can check.

Observed, not theorised. Early on 2026-09-07 `GET /campaigns` answered
with an empty list and `GET /sender-emails` gave a total of 51. Later the
same day, after an operator deleted a wrongly-named workspace, the same
two calls answered 20 campaigns - several named
`PRODUCTIVE - SOFTWARE DEVELOPMENT - ...` - and a total of 225. Nothing in
Resonate changed between the readings, and nothing in Resonate could have
told the difference.

Neither payload carries a workspace. A `/sender-emails` row has 24 fields
and none of them is a workspace, team or owner reference; a `/campaigns`
row has 24 fields and the same is true. So there is no way to answer
"does this inbox belong to PRODUCTIVE" from the response, and no way to
pin an expected workspace id and fail closed when it does not match.

The canonical workspace is **`PRODUCTIVE`, stable id 10** - note the API
spells it in capitals, so an exact-name match on "Productive" would miss
it, and a fuzzy one would have matched the wrong workspace that existed
until today. Deleting that workspace removed today's instance of the
problem and not the problem: the architecture is still unable to prove
which workspace it is reading, and the next similarly-named workspace
reintroduces it.

Until an endpoint exposes workspace ownership on the row, or the vendor
documents how a credential's workspace is selected, a provider-backed
EmailBison sender gate cannot be built honestly - it would assert an
isolation it cannot verify, which is the `sending.live` defect again.

**The sender inventory mismatch, explained and closed (2026-09-07).**
There was no mismatch between the providers and their APIs. Reading
HeyReach's `POST /li_account/GetAll` with correct pagination returned
**41 of 41** accounts and reproduces the operator's UI exactly:

|                  | in >=1 campaign | no campaign |
| ---------------- | --------------- | ----------- |
| `authIsValid`    | **33**          | 0           |
| not `authIsValid`| **1**           | 7           |

41 total, 33 connected and in campaign, 8 not connected, and "Available:
0" because every connected account is already in at least one campaign.
EmailBison's `GET /sender-emails` likewise returns `meta.total: 225`,
matching its UI.

So the smaller numbers Resonate reported were not a pagination bug, a
filter, a cache or an adapter defect. **Resonate never read either
provider.** There is no sender-enumeration call anywhere in `src/`, and
`work/senders.jsonl` is entirely locally authored - its 37 `productive`
rows are `demosenders.py` fixtures on the reserved domain
`productive.test`. Provider inventory 41 and 225; Resonate API-read
inventory nil.

One live finding fell out of the reconciliation: **account `129531` is
assigned to a campaign while its auth is invalid** - assigned and unable
to send, in the real Productive workspace today. That is the exact
fail-closed case a canonical sender model has to catch, and nothing in
this build would notice it.

The evidence a canonical model needs is all present on the HeyReach row -
`authIsValid`, `isActive`, `activeCampaigns`, and an `accountLimits`
object carrying connection-request, message, InMail, follow, post-like and
profile-view limits with their maxima, plus four cooldown fields. On the
EmailBison row: `status` (`Connected`), `type`, `daily_limit`,
`warmup_enabled`, `bounced_count`, `total_replied_count`,
`emails_sent_count`. None of it is read.

Note also that EmailBison exposes **16 workspaces** behind one key,
including both `PRODUCTIVE` and `ColdMessage - Productive`, so whether the
225 is Productive's or the estate's is still unestablished - and that is
precisely where cross-workspace sender leakage would come from.

**Sender inventory is never read from either provider.** Both endpoints
exist and were confirmed live on 2026-09-07: EmailBison
`GET /sender-emails` answers 200 with `meta.total: 225`, and HeyReach
`POST /li_account/GetAll` answers 200 with `totalCount: 41`. Neither is in
`src/`. `heyreach.READ_ROUTES` is `/campaign/GetAll` and
`/inbox/GetConversationsV2` only, and the module's note records
`/linkedinaccount/GetAll` answering 404 - which was the wrong route name,
not an absent capability. `bison.py` has no sender route at all. So
`work/senders.jsonl` is entirely locally authored, and the 37 rows it
holds for `productive` are `demosenders.py` fixtures on the reserved
domain `productive.test`. There is no reconciliation between what the
providers hold and what Resonate believes, and EmailBison has 16
workspaces behind one key, so the scoping of the 225 is unestablished.

**A contact-bearing import can never be qualified.** `campaignseg.assign`
grants a `segment_key` only to a company whose ICP verdict is
`QUALIFIED`, which needs `company_facts` - and `company_facts` cannot be
imported: `columns.CANONICAL` is eight fields, none of them a company
fact, and `store.new_record` hard-codes `{}`. The only writer is
`contactout.company_info`, and `enrich` reaches it only when
`usable_contacts(rec)` is empty, which is false for any row that arrived
with an address. So a list of known contacts imports, dedupes and screens
correctly, qualifies as `unknown`, gets no `segment_key`, and
`api.create_campaign` refuses it. A dry run on real contact data stops at
qualification.

**Enrichment spends person credits on companies with no ICP verdict.**
`CLAUDE.md`: "Company first. No paid person-level call before a company
reaches an explicit ICP verdict, and rejected, review and unknown all mean
zero person credits." Nothing enforced it. `enrich.py` imported neither
`icp` nor `dmplan`, and `enrich.run` selects on `state in ("queued",
"enriched")` alone - so a company explicitly marked `rejected` was planned
and charged for `decision-makers` (10 credits) exactly like a qualified
one, as was a company nobody had assessed. `dmplan.may_enrich` calls
itself "the single gate" and has no caller on any path that spends.

**Not fixed, and deliberately so.** The gate was built and measured: read
the verdict through `qualify.state_of`, refuse the two person-level calls
unless it is qualified or human-approved, leave company-level calls
ungated because they are what *produce* the verdict. It works - a rejected
company drops from 13 planned credits to 1, and a qualified one is
unchanged - and it is the order `PLAYBOOK.md` section 1 already documents:
"company facts -> qualify -> segment -> plan the spend -> STOP -> a human
approves -> person enrichment".

It also turns 40 tests red across six modules, because their fixtures
enrich without qualifying first - which is the violation, stated as a
fixture. The records come from shared JSON fixture files used by many more
tests than those six, so landing it means editing fixture data rather than
test code, and a half-landed spend guard is worse than a documented one.
It is specified, measured and reverted, and it is the first thing to do
next. The cost of leaving it is roughly 300,000 credits of person-level
calls on unassessed companies for a 30,000 domain universe; the cost of
rushing it is a corrupted fixture estate.

**And the forecast under-reported the bill by more than half.** `plan()`
lists no verification operations for a record that has no contacts yet -
which is every fresh import - so a 30,000 domain dry run forecast roughly
390,000 credits against a real exposure nearer 750,000, because
`enrich_record` verifies every contact it finds, at up to 3 credits each,
and `enrich.COSTS` prices `decision-makers` at a flat 10 while
`costsim.KNOWN_UNITS` prices it at 1 per profile. Three cost models
(`enrich.COSTS`, `costsim.KNOWN_UNITS`, `dmplan`) disagree and nothing
reconciles them.

**A cap hit condemns the tail of the batch with a false reason.** When
`Budget.charge` refuses, `enrich_record` still finishes and `outcome(rec)`
returns `("dropped", "no contact found at this domain")`. `dropped` is
terminal and outside `run()`'s default states, so those records are never
retried - marked with a reason that is not true, by a cap that was working
correctly.

**An interrupted Apify run bills for an actor nobody can reclaim.**
`research.run` held the run id in a local variable and never wrote it
down, and `wait_for` polls for as long as `POLL_ATTEMPTS` allows. A
process that died in there left an actor running and billing compute
units with its id held nowhere, an empty `rec["research"]`, and therefore
the same stated need next run - which started a second actor. Fixed by
recording the id on the record as soon as it exists. `COSTS` prices this
at zero because it is billed in compute units, so `--cap` could not have
bounded the duplication either.

**The free people-count guard was disabled by any other writer.**
`enrich` gated it on `not rec.get("company_facts")`, and the call writes
only `headcount_signal` - so `demo`, `companies` and `personas.apply_icp`
each suppressed it by writing some other key. `staffed` was then `None`,
`unstaffed` `False`, and a record with no contacts went straight to the
paid `decision-makers` on a domain that might be parked, which is exactly
what the free call exists to prevent. Now asks for the answer rather than
the dict.

**`gtm.supersede` is the one `work/` writer that can lose its file.** It
is a read-modify-write over the whole `gtm.jsonl` with a bare
`open(path, "w")` - no lock, no temp-and-rename. Every other writer
checked (`mx.save_cache`, `poller.save_checkpoint`,
`replywatch._write_status`, `observability._append`) does it correctly. A
crash there truncates the decision log and a concurrent `record()` append
is lost.

**Three more vocabularies that are declared and unreachable.**
`store.STATES` includes `"pushed"` and nothing in `src/` writes it, while
six guards read the record-level value - `lint.UNSHIPPABLE`,
`eligibility._record_state`, `enrich.TERMINAL`, `approve.REFUSED_STATES`,
`generate`, `personas`. `dmplan.STATES` declares `COMPANY_ENRICHED`,
`DM_PENDING` and `DM_COMPLETE`, and `qualify.state_of` - the only function
that computes a dmplan state - can return none of the three, while
`explorer.py` offers all nine as filter facets, so three filters match
nothing for ever and look like an empty segment. And `observations.py` is
460 lines deciding what a message may claim to have noticed, whose only
importer in the repository is a test.

**Two smaller ones worth the line.** `revival`'s `UNUSED_ANGLE` is a
static set difference rather than a change, so with a real multi-angle
config every account clears cooling and becomes `READY` on the calendar
alone and `NOTHING_NEW` is unreachable - it writes nothing and sends
nothing, but the queue it fills is "everything past ninety days", which is
not what the module intends. And `tasks._returns` wraps
`oooreturn.candidates` in a bare `except Exception: return`, which would
empty the returns queue silently.

**Nothing checks the age of an ICP verdict, a company fact, or a
verification.** `verdict["scored_at"]`, `verdict["scoring_version"]` and
`qualification["at"]` are stamped and read by nobody, so a verdict from
March carries full authority in September and a batch scored under an
older model mixes invisibly into every aggregate. `company_facts` carries
no timestamp at all. `verification.age_of` computes the numbers and says
in its own docstring that there is no freshness rule; its only consumers
are two display fields.

**The ICP gate is landed, and nothing can currently get through it.** The
gate itself is correct and tested: `enrich.spend` refuses `decision-makers`
and `aiark-people-search` unless `qualify.state_of` says qualified, so
rejected, review, unknown and not-yet-assessed all buy zero person credits.
What is missing is the other half. No client config carries an `icp` block -
not `demo.yaml`, not `productive.yaml` - so `icp.settings` falls back to
defaults, and the defaults want `min_dimensions_for_a_verdict` scored before
they will call anything either way. A well-formed agency with industry,
headcount, two offices, a founding year and a technology list scores 38 and
lands on `review`. The free `people-count` writes one field, and
`company-information-from-domain` a handful more, which is not enough. So on
today's configuration the honest end state of a run is every company held at
`review_required` with the person-level calls refused - which is the safe
direction, and is also not a working pipeline. This is a configuration gap,
not a code one: it needs a real ICP definition per client before a pilot can
enrich anybody.

**Two of the three verification vendors answer; a catch-all still cannot
clear.** This entry used to read "only one answers, so no address can ever
reach two confirmations", and the cause was a wrong path, not a missing
product. Measured on sixteen real contacts at three qualified Productive
accounts, `contactout` returned `error` nine times out of nine - HTTP 404,
"The route v1/email-verifier/verify could not be found", and four other
plausible paths answered the same. That path was the MCP *tool* name with a
verb bolted on, the same mistake section 5.1's route table was written to fix.
The REST route is `GET /v1/email/verify?email=`, confirmed live on 2026-09-07
on two real addresses - `accept_all` on a catch-all domain, `invalid` on a
dead mailbox - against the same key and the same `https://api.contactout.com/v1`
base the free `/stats` call already uses. There is no entitlement problem: the
account is prepaid and the verdict came back. `ROUTES["email-verifier"]` now
carries it, so `contactout` and `reoon` are two independent vendors and the
double-confirmation policy can be satisfied.

What remains is narrower and unchanged in kind. `deliverable` still returns
`error` on every call, because `require_contract` refuses until a human has
read one live response and set `DELIVERABLE_RESULT_SHAPE=confirmed`; the
refusal is classified as an error rather than a negative, so it costs nothing
and creates no disagreement. And `accept_all` is not in `CONFIRMING_STATUSES`,
so an address on a catch-all domain still reaches at most one confirmation and
stays at `held / insufficient_confirmations` - which is the correct answer, not
a defect. Arming Deliverable is now the only outstanding human action here, and
it buys catch-alls rather than the lane itself. Lowering
`required_confirmations` to 1 would still be the forbidden move.

**The thirty-thousand-credit floor is only real for a bare domain list.**
The scale forecast assumes one credit per domain for
`company-information-from-domain` before anybody is qualified. That is true of
the fifty-domain pilot file, which carried nothing but domains. It is not true
of a vendor TAM export: the 51,741-row file already in `work/` carries
headcount, industry, tags, product and services, locations and founding year -
most of what `icp.score` reads - and the model does not care which provider a
fact came from.

Measured, with no credits spent: 20,544 unique domains scored from that file
alone, and adding the free local read to the strongest twenty moved six of
them to `qualified`. One moved *down*, 41 to 17, because reading the site
showed it was not the business its tags implied - evidence arguing in both
directions, which is the model working rather than a scoring accident. Every
row in that export also carries a work email and a LinkedIn URL, and 41,566 of
them match a Productive persona.

So the cheapest qualified cohort available today costs nothing, and the
company-information call is a fallback for lists that arrive bare rather than
a floor under every upload. What an export cannot supply is verification: a
column named `Email_Business` is a vendor's claim, not two independent
confirmations, and nothing may shortcut that.

**Neither import path accepts an internationalised domain.** `ingest
.HOSTNAME` ends `[a-z]{2,63}`, so a punycode TLD fails on the digit in
`xn--p1ai` and a unicode IDN fails on the non-ASCII characters. Measured:
`munchen.de` with an umlaut, `xn--e1afmkfd.xn--p1ai` and `xn--r8jz45g
.xn--zckzah` are all refused, while `xn--mnchen-3ya.de` - punycode label,
ASCII TLD - is accepted. Nothing converts unicode to punycode anywhere in the
upload path. The two importers used to disagree about this, which was the
worse problem and is fixed; they now agree on refusing, which is the
conservative answer and not obviously the right one for a client selling into
Germany, Greece or Russia. It is one decision to make rather than two
behaviours to reconcile.

**A long batch overwrites anything that happened while it ran, including a
reply.** `enrich.run` does `store.load()`, spends minutes making provider
calls, then `store.save(recs)` - a whole-file write from a snapshot taken
before any of it. `generate`, `personas`, `mx`, `companies`, `inbound`, `run`
and, worst, `events.ingest` have the same shape. Demonstrated by running the
two paths against each other in a temp queue: a reply that landed mid-batch,
its account pause and its event were all present, and after the batch saved
they were gone. `eligibility._replied` then finds nothing and the person who
asked to be left alone is eligible again. `store.transaction()` exists and is
correct; most writers simply do not use it, and `tests/test_concurrency.py`
proves the primitive without ever asserting that callers reach for it.

The obvious repair is wrong: wrapping a live batch in `transaction()` would
hold the queue lock across every provider call for the length of the run.
What is needed is a re-read and merge at save time, or a per-record write -
which is a real change to the core write path and should not be made while
batches are in flight. Recorded here rather than attempted in a hurry. The
same mechanism loses the spend ledger, because `waterfall.record_step` writes
onto the in-memory record: a crash mid-batch discards the ledger for every
record whose credits were already spent, and the spend audit then reports
clean because it watched nothing.

**`out/emailbison.csv` is a second payload builder with weaker gates.**
`render.build` runs on every `python -m src.run` and `render.emailbison_rows`
gates on lint alone. It does not check replies or cross-channel stop, the
account pause, suppression, DNC, `already_pushed`, campaign freeze or
approval, the step due-day, duplicate identity, or the confirmation count -
all of which `push.verify_before_payload` does check. It emits every clean
step of every record of every client, each time it runs. Since a live send in
this build is a human uploading a file, that file is built by the weaker of
the two paths. It is header-only today, so nothing has escaped.

**The idempotency marker is never written on any wired path.**
`push.already_pushed` reads `stepstate.is_terminal` correctly, but the only
writer is `push.mark_pushed`, whose sole non-test caller is
`demo_outreach.py`. `push.run` never calls it, and nothing anywhere writes
`stepstate.PREPARED`, `CONFIRMED` or `FAILED`. `PREPARED` - a payload exists,
nothing has left - is precisely the write-ahead marker that makes a crash
between the provider write and the persist safe. And `push_id` is computed,
attached to the row, then dropped by both payload builders, so the
idempotency key never reaches the provider and provider-side dedupe of a
timed-out-but-succeeded call is impossible by construction.

**EmailBison accepts a workspace filter and ignores it.** Probed read-only:
`GET /sender-emails?workspace_id=10`, `?workspace_id=3` and
`?workspace_id=999` all answer 200 with the same 225 rows and the same total
as the unscoped call. A workspace that does not exist returns the whole
estate, indistinguishable from a correct answer. Combined with the fact that
no sender-email row carries a workspace, team, tenant or owner field, and
that `/workspaces/10/sender-emails` is 404, there is no read that can
establish which of the 225 inboxes belongs to which of the thirteen
workspaces - one of which is another client. The nearest signal is `tags`,
operator-typed free text that nothing validates; 153 of 225 mention
"Productive". This is documented in `src/providers/bison.py` beside
`headers()` so the next person to reach for the filter finds the probe result
first.

**The local sender roster names accounts that do not exist.** `work/senders
.jsonl` gives the productive workspace `provider_account_id` values
`bison-1 … bison-64` and HeyReach ids `4002-4005`. Live EmailBison sender ids
are integers around 3724-3948 and live HeyReach account ids run 116968-212356.
The overlap is not partial, it is zero, and four more roster rows carry no
provider id at all. So the chain is: a real healthy sender exists at the
provider, the assignment layer picks a sender from the roster, and the roster
names something that is not there. Both readiness counts look excellent - 33
of 41 HeyReach accounts auth-valid and active, 225 of 225 EmailBison inboxes
connected - and neither is reachable from this system. Repairing it means
mapping real provider ids to real senders by hand, because neither provider
will say who owns an inbox.

**One live LinkedIn account is running a campaign on broken auth.** HeyReach
id 129531: `activeCampaigns: 1`, `isActive: true`, `authIsValid: false`.
Whatever that campaign believes it is sending is not being delivered by that
account. Separately, id 139699 is auth-valid, active, in eight campaigns and
sitting at zero connection requests. Neither is visible to this system, which
reads sender health from a local field only the demo builder writes.

**Website evidence has no declared purpose, and the boundary holds by
accident.** Research rows - from Apify and now from the local reader - carry
no `evidence_id` and no `subject`, so `eligibility`, `personalization`,
`preview`, `qa` and `refresh` all filter them out silently: a scraped company
reports `company_research: never` for ever, and `qualify._inputs_fingerprint`
hashes every one of them as the empty string, so it can see that research
arrived but not that it changed. The tempting fix is to stamp an id. That
would be wrong on its own: an id makes the evidence citable in a message, and
`eligibility._evidence_aged_out` would then judge undated website copy
`unusable` and hold the send. The honest model is that a company's own
marketing page is *classification* evidence - good enough to decide what kind
of business this is, not good enough to quote back to a prospect as a dated
claim - and that distinction should be declared on the row rather than
emerging from a missing field. `evidence.make` cannot be used as-is: with no
`published_at` it returns `quality: unusable`, and calling `retrieved_at` a
publication date would be inventing freshness.

**The MX cache is loaded by the pipeline and never saved by it.**
`enrich` calls `mx.load_cache()` and then `mx.for_domain(..., save=False)`,
and no path in `enrich` calls `mx.save_cache()`. The only writers are the
standalone `python -m src.mx` and `apply_to_record(save=True)`. So the one
working per-domain TTL cache in the repository gets a per-process lifetime
during the run that would benefit from it most, and every DNS answer is
thrown away at exit.

**A second unlocked full-file rewrite, beside the known one.**
`gtm.supersede` is already recorded below. `signals.install` has the identical
shape - a bare `open(path, "w")` looping rows with no lock and no
temp-and-rename - so a crash there truncates `work/signals.jsonl` and a
concurrent `signals.record` append is lost. Its docstring says demo and tests
only, but nothing in the function enforces that.

**Six of the twelve ICP dimensions read website prose nobody fetches.**
Measured on fifty real Productive domains, after buying company facts for all
fifty: `agency_fit`, `employee_count`, `distributed_teams`, `geography` and
`service_not_product` score from structured firmographics, and the remaining
six - `resource_planning_need`, `profitability_need`, `utilization_need`,
`time_tracking_need`, `operational_complexity`, `delivery_complexity` - match
keyword *phrases* like "capacity planning", "billable" and "retainer" against
`segments.text_of`. ContactOut's `company-information-from-domain` returns
firmographics, not marketing copy, so those six never score. Five scored and
six or more missing puts `_confidence` in its `LOW` band by rule, and `LOW`
forces `REVIEW` in `_verdict` whatever the number is. The best account in the
batch - a UK communications agency, 424 staff, ten offices - scored 48,
clearing `tier_c` of 45, and still came out `review`. So the ceiling is not
the thresholds: it is that half the model reads a source the pipeline does not
collect for this client. `research`/Apify is what would collect it, it is
disabled for Productive, and `COSTS["apify-research"]` is zero because it
bills in compute units, so `--cap` cannot bound it either.

**A human accepting a `review` company still cannot unblock enrichment.**
`dmplan.may_enrich` implements the path - `review` plus a recorded acceptance
plus `dm_plan.allow_review_enrichment` - but the gate on the spending path
asks `qualify.state_of`, which returns `REVIEW_REQUIRED` for an accepted
review company just as for an unreviewed one. That is the conservative
reading of CLAUDE.md, which says review and unknown mean zero person credits
without qualifying the statement, so the gate stays shut and the policy escape
hatch is currently unreachable from the spend. Worth a decision rather than a
silent divergence: either the rule means what it says and `may_enrich`'s
clause is dead, or the clause is live and the gate needs to honour it.

**`dmplan.DM_APPROVED` is unreachable, so the approval layer is inert.**
`dmplan.ENRICHABLE = (DM_APPROVED,)` documents itself as "states from which
person enrichment may run at all" and its only reference anywhere is a test
asserting its literal value. `qualify.state_of` reads `dm_approved` and
`qualify.company` carries it forward, but nothing in `src/` ever writes it -
so the state can never be entered, and the `is_current(batch, companies)`
clause inside `may_enrich` can never be satisfied. That is why the spend gate
asks `qualify.state_of` rather than `may_enrich`: demanding the approval
would not have made person enrichment stricter, it would have ended it.
`may_enrich` itself still has no caller on any path that spends; its one
production caller renders the answer on a screen.

**A suppressed person still costs a model call and gets a draft written.**
`generate.plan` gates on `rec["state"]` and `lint.sendable(contact)`, and
`lint.sendable` delegates to `verification.is_sendable`, which answers a
question about verification evidence and nothing else. It reads none of
`rec["suppression"]`, `rec["paused"]`, `contact["unsubscribed"]`,
`contact["stopped"]` or the reply log, and `run.stage_generate` adds no gate.
After a company-wide do-not-contact is recorded, `generate.plan` still returns
a draft op for that contact. Nothing ships it - eligibility and
`push.verify_before_payload` both refuse - but the credits are spent and a
message body for a suppressed person is written and stored.

**Two dictionary keys are worth two vendor approvals.**
`verification.legacy_evidence` synthesises a ContactOut vote from
`contact["verdict"]` and a Reoon vote from `contact["reoon"]
["is_safe_to_send"]`, so a record carrying both is sendable with no provider
call behind it. It is narrow today because only `verification.apply` writes
those fields and stored evidence takes precedence, but a hand-edited or
externally-authored queue row clears the two-vendor invariant on its own.
Related, and from the same audit: `verification.confirmations()` counts a set
of provider *name strings* with no allowlist, so `contactout` plus
`contactout_v2` would count as two independent vendors; and there is no
spamtrap status anywhere - `result()` coerces any unrecognised status to
`unknown`, so a vendor reporting a spamtrap is recorded as having no opinion
and two other approvals still send.

**Neither sending provider has a sender enumeration path, and "ready" is
three local booleans.** There is no EmailBison inbox route in the codebase at
all, and HeyReach's account listing answers 404. The entire sender inventory
is `work/senders.jsonl`, whose only writers are the demo estate builders, and
whose rows carry no marker distinguishing them from real ones. Readiness is
decided by `assignment.eligible_senders` from `person["active"]`,
`account["active"]` and `health` - and `health` is written only by
`web/demosenders.py`, so in production every account sits at the constructor
default and the one health filter reads a field nothing fills in. Auth
validity, cooldowns, warmup and bounce history are not consulted. Separately,
`assignment.ensure` and `assignment.allocate` are called only from demo
builders, so outside the demo estate `push._sender_of` returns empty strings
and the payload degrades to a HeyReach account id of `0` rather than
refusing.

**Workspace ownership of an external campaign is assumed from the
credential.** No ownership field is read from any EmailBison or HeyReach
payload; `mapping.py` says so itself, treating visibility-to-the-key as the
isolation model. The keys are process-wide environment variables with no
per-workspace resolution, so every workspace shares one EmailBison tenant and
one HeyReach tenant. `push.py` and `campaigns.py` do not contain the word
workspace. `mapping.py` - the only module that could establish external
ownership - has no importer in `src/`, and the `campaign["mapping_checked"]`
it writes is read nowhere. Sending is refused globally by
`push.LiveSendNotEnabled`, so nothing can act on this today; but that refusal
is the only thing in the way, and it is not an ownership check.

**Out-of-office and not-now are distinct everywhere except where it counts.**
The classifier, the recorded event, `oooreturn`'s source field and the work
queue all keep them apart, and there is a test asserting that calling one the
other tells an operator something untrue. But `accountpolicy` maps both to
`NOT_NOW` and sends that to `reply.on_negative`, so an autoresponder ends
that contact's sequence exactly as a refusal does. Recovery is the
`oooreturn` work-queue row, which needs a person.

---

## 21. What the RBAC and observability audits found and this did not fix

An RBAC/secret-handling pass and an operator/client observability pass ran
over the whole product. Six findings were fixed and are in commit
`4546712`; twelve are recorded here instead, because each is either a
second correct answer to a question already answered elsewhere, or a
fragility with no reachable trigger today. **None of them lets anything
send.** Two things the audits flagged are deliberate and are named under
*What is not a gap* below rather than here: a viewer reading the report
editor, and a viewer generating a client PDF.

**1. Authorization lives on the route for eight service functions.**
`generate_report`, `regenerate_report`, `create_draft`, `edit_draft`,
`finalise_draft`, `announce_report` and `create_workspace` have no
`repo.require()` of their own. `render_draft` was the eighth until `4546712`
gave it one. Every current
caller gates them correctly, so nothing is reachable that should not be - but
fifteen other mutators ask at the service boundary and these ask at the door.
`create_workspace` also writes no audit entry for the creation itself.

**2. Two role tables decide the same question.** `src/roles.py` defines
`admin`/`reviewer`/`viewer` keyed on Slack user ids from client config and
drives the Slack approval path; `src/workspaces.py` defines five roles and
drives the console. Approving a campaign is authorised by whichever one the
request arrived through, and they can disagree. This is the parallel state
machine CLAUDE.md warns about, at the authorization layer.

**3. Five reads cross the workspace boundary before comparing.**
`reportdraft.get()` and `jobs.get()` load across all workspaces and then
compare against `repo.workspace`. They return `None` on a mismatch, so there
is no existence oracle and no mutation happens first - but they bypass
`Repo._guard`, which is the boundary every other read goes through.

**4. Two persisting egresses have no redaction seam.**
`observability.count()` truncates a `detail` string to 200 characters and
writes it to `work/observability.jsonl`; `app._refusal` writes
`reason=str(error)[:200]` into the workspace audit log. Neither passes
through `providers.redact`. Bounded today because the exceptions that reach
them carry no credential, and one caller away from not being.

**5. `outreachpage.redact` masks only a contact email** while rendering
outbound request bodies into a `<pre>`. The bodies carry no credential - keys
ride in headers - so this is a naming collision with `providers.redact`
rather than a leak, but a reader auditing "is this redacted" gets the wrong
answer from the name.

**6. `cadence.status_for` cannot say `held`.** It returns
`paused/blocked/waiting/skipped/unapproved/eligible`, so a contact awaiting
verification reads `blocked` where `eligibility` says
`HELD_VERIFICATION_UNKNOWN`. `stepstate`'s own docstring says the distinction
is the only information an operator can act on: "needs a better address" and
"needs one more call" are different jobs. Two screens answer differently
about one contact.

**7. Seven of `stepstate`'s fourteen states have no writer.** `planned`,
`pending`, `prepared`, `confirmed`, `failed`, `cancelled` and `held` are
never written by a live path, so `TRANSITIONS` is a legality table for a
machine that visits half its states.

**8. `touch.WORDS` is consumed on one of the two screens that render its
vocabulary.** `pages._state` renders the same values as
`str(value).replace("_", " ")`, so the account view prints `payload ready`
where the timeline prints "payload built, not sent" - the phrasing `WORDS`
exists to guarantee.

**9. `costsim.py` has no web importer** and `report_preview` has no route, so
the report editor's Preview button 404s.

**10. `accountpolicy.contact_state` assumes a dict.** It returns
`contact.get("suppressed")` directly, so a truthy non-dict - a bare `True`
from imported data - raises `AttributeError` in `api._engagement_of` and 500s
the contact outreach page. Nothing in `src/` writes that shape today; the
canonical writer records a dict.

**11. The `sending.live` workspace setting still enforces nothing**, and
`killswitch.py` still has no importer outside its own tests. Both are
recorded in full earlier in this file; re-confirmed by this audit, and
unchanged by it.

**12. Nothing refuses a contact with no sender assignment.**
`push._sender_of` returns empty strings for an unassigned contact and says in
its docstring that "the launch checklist is where it gets refused, not here".
It is not: `senders.check_mapping` reads `campaign["senders"]` - the
campaign's account configuration - and never looks at any contact's stored
assignment. There is no `BLOCKED_NO_SENDER` among eligibility's twenty-four
blocked and thirteen held reasons.

Downstream, `heyreach._account_id_for` falls back to `int(fallback or 0)`,
so an unassigned row resolves to LinkedIn account id 0 rather than failing
closed.

Nothing acts on either today - there is no send path, and `push.run(live=True)`
raises - so this is inert. It stops being inert the day a send path exists,
and it is not fixed here because assignment is currently written only by demo
code: making `_sender_of` raise, or making eligibility refuse an unassigned
contact, would refuse the entire pipeline rather than the unassigned case.
Whichever way that is closed is a design decision about when assignment
becomes mandatory, and it belongs with the send path rather than ahead of it.

---

## 22. What two red teams found on the Productive canary cohort

An independent data/safety pass and an independent copy/truth pass attacked the
cohort assembled for a one-person LinkedIn canary. Three copy blockers were
fixed in `fa58e88`. These are the rest, recorded because a canary is not safe
until they are answered, and because several are about guards that exist and
are not connected.

**1. A one-person canary is not expressible.** Approval is per-campaign
(`eligibility._campaign`), and `productive-pilot-canary` names two records with
no contact-level scope. Approving it releases 15 touches to 3 people at 2
accounts. There is no field that says "this approval covers this contact, this
step, once".

**2. `killswitch.py` and `pilotcaps.py` have no production importer.** Neither
is imported anywhere in `src/` outside its own tests. `killswitch.step_state`
calls `eligibility.decide`, not the reverse. So `sending.live`, the global and
workspace switches, and the pilot caps a canary exists to respect, enforce
nothing - while RELEASE-CANDIDATE.md and PRODUCTIVE-PILOT-PLAN.md describe them
as live. This is the same defect as `sending.live` in section 21 item 11,
confirmed again from the opposite direction.

**3. Account-level fatigue is not on the send path.** `eligibility._separation`
skips any entry whose contact key differs, so it is per-contact and never
per-account. `fatigue.account_check` is the only module holding an account view
(`max_active_contacts`, `max_touches_per_week`,
`min_hours_between_first_touches`) and `eligibility` does not import it.
Measured: both contacts at a 27-person agency receive a LinkedIn touch on day
8. `start_offset_days` is applied correctly; it staggers first touches and does
nothing about the second.

**4. The tier cap is computed and never enforced.** `persona_plan.max_contacts_to_enrich`
is 1 for both tier-C accounts and is read only by display and estimate code.
`enrich` extends `contacts` with no count limit. The only truncation uses a
different number from a different file - `cap_per_domain` in the client config -
and the looser of the two wins silently.

**5. `linkedin.canonical` normalises and never validates.** A bare token is
accepted as a vanity unconditionally, so `canonical("<script>")` returns a
plausible profile URL. Nothing cross-checks the slug against the person's name,
and the module says so as policy. In this dataset the provider's own name and
slug diverge often enough to matter: "Russell H" -> `russellharper1`,
"Connor D" -> `connordunaway`. For an email a wrong address bounces; a
connection request to the wrong profile does not.

**6. Re-keying has no migration and no detector.** `identity.assign_keys` is
the only writer of `contact["key"]` and touches `contacts` only, so every
`excluded` entry carries `key: null` and any event written under a previous key
is orphaned. Observed after a re-selection: 11 events on one record referencing
a key that resolves to nobody. `events.match_contact` falls through to
email/LinkedIn matching and reports `unmatched`, which is indistinguishable
from a stranger's event.

**7. The ledger is written before the call and can never be voided.**
`enrich.spend` charges the budget, writes the waterfall row, returns True, and
only then is the provider called. There is no refund or rollback anywhere. With
every provider call failing, a record still ends with credits charged, ledger
rows written, and `waterfall.audit` reporting no unjustified spend - an audit
that reports clean because it watched nothing. `actual_cost` is null on every
row ever written, so `waterfall.spend()["reported"]` is structurally always
None and expected-versus-actual cannot be reconciled.

**8. `src/validate.py` makes real paid calls with no ledger row.** Up to 10
credits for `decision-makers`, and `waterfall.record_step` appears nowhere in
the file. A genuine bypass of the rule that every paid call goes through
`spend()`.

**9. Reply detection is down** - *and this finding rested on contaminated
evidence. Corrected 2026-09-09.* `work/replywatch.json` reports HeyReach
unhealthy, "not configured: no credentials in the environment". Positive-reply
protection and the account HOLD-on-positive cannot fire while it stays that
way, which matters more the moment anything is actually sent.

The conclusion is still true - no poller has credentials, and
`work/checkpoints.json` has not moved since 2026-08-26 - but **the file cited
as evidence is part fixture.** It also holds `"digest"` and `"watcher"`
entries whose `last_error` values are `RuntimeError: no` and `RuntimeError:
still on fire`, written by `tests/test_replywatch.py:305` into the real
`work/` because the second barrier covered only the queue. A red team read
test fixtures as a production signal. The barrier now covers every writer
into `work/` (`store.refuse_production_write`, commit `a191a2a`), so the file
cannot be contaminated again - but the existing file has not been cleared,
and until it is, nothing in it should be quoted as evidence of anything.

**10. Two angle systems, and the one that runs ignores the evidence check.**
`qualification.messaging.recommended_angles` and `unsupported_hypotheses` are
computed per record; the angle actually used comes from
`personas.default_angle` via `contact["angle"]`. Both cohort records list the
angle in use under `unsupported_hypotheses`.

**11. `eligibility._linkedin_checks` calls neither lint nor `claims.verify`.**
Both live in `_email_checks`. `push.verify_before_payload` re-runs `decide()`,
which is a real pre-send recheck, but its extra hardening is gated on
`channel == EMAIL`. A note edited after the cadence was built is never
re-linted before the payload is made.

**12. Geography fails silently on US addresses.** Both US accounts resolve
`country: null`, `region: "Other"`, `timezone: null`,
`location_why: "no usable location evidence"` - while `company_facts.offices`
holds a full US street address. The parser works: the Irish record resolves
correctly. Cost is four ICP points each and no send-window localisation.

## 23. What the streaming architecture will not tolerate, and today does

`STREAMING-ARCHITECTURE.md` became a standing product principle on 2026-09-08:
a 30,000 domain TAM must produce campaign-ready accounts continuously, and the
account rather than the uploaded file is the unit of execution. Two things in
the current build are incompatible with it. Neither is a bug today - the batch
runner is correct at pilot scale - and both are recorded rather than fixed,
because fixing them is the next scale phase and not the canary critical path.

**23a. Progress is not durable per account.** `src/run.py:292` persists with a
single `store.save(recs)` after all four per-record stages have each walked the
whole target list, and `enrich.run` does the same at `src/enrich.py:723`,
saving once after its own loop. So a crash at record 9,000 of 30,000 loses
every stage mark from that pass. The evidence is not written either, which
means the paid calls behind it are re-spent on resume - the waterfall ledger
records what was bought, but the record that would let the next run skip it was
never saved. The cost of this scales exactly with TAM size, and the streaming
model's resume requirement ("a restart does not begin at domain 1") cannot hold
while it stands.

**23b. Selection is positional, so nothing can overtake.** `run()` takes
`targets[:limit]` in queue order. `limit` truncates a list; it does not
prioritise one. There is no priority band, so a strong ICP account uploaded at
row 28,000 cannot move ahead of a weak one at row 12 - which is the whole point
of optimising for time to first campaign-ready account rather than time to
finish the file.

What is *not* wrong here, and is worth stating because it decides how large the
eventual change is: the canonical per-account state already exists. Every
record carries `rec["stages"][name]["status"]`, `run.needs(rec, stage)` already
decides per record whether a stage applies, and `qualify.needs_work` already
re-runs a verdict when a fingerprint of the facts behind it changes. The
barrier is the stage-major loop, not the data model, so this is a scheduler
change rather than a rewrite.

## 24. Blitz is declared and nothing calls it

Phase 1 landed on 2026-09-08: `src/providers/blitz.py`, 62 tests, a cassette, a
cost table, a waterfall position at three stages, an ICP gate entry and a
health check in `python -m src.check`. **No call site exists.** Nothing in
`enrich_record` reaches Blitz, so today it changes no outcome for any record.

That is deliberate rather than unfinished - the field spellings come from the
OpenAPI specs and no response has ever been observed from this repository, so
wiring call sites now would be writing against a guess - but it is exactly the
shape this repository keeps mistaking for working software, and it is recorded
here so nobody reads "Blitz integrated" off a commit message. `LIVE-READINESS.md`
§5b classifies it as fixture-only.

Three things are owed before Phase 2, in order:

1. A live `GET /v2/account/key-info`. It is free, it costs no record, and it
   returns `allowed_apis` - the only authority on what this key may actually
   call. A green tick that does not say which endpoints are permitted is a tick
   for a key that may refuse the only call the batch needs.
2. One deliberate metered call to confirm the response shape, recorded the way
   `LIVE-VALIDATION-PLAN.md` asks. The HTTP verbs in `ROUTES` are inferred from
   the specs' shape; if one is wrong it is wrong in exactly one line.
3. The call sites, each of which must write the real cost
   (`fair_usage.records_used`) into the ledger via `waterfall.record_step`'s
   `actual_cost`, and must never retry. Blitz has no idempotency and no
   request-side identifier, so a retried timeout is a second billed call.
   `blitz.py` does not retry and a call site must not add one. A missing
   `fair_usage` block means unknown and must stay `None` - a metered call
   recorded as free is worse than one not recorded at all.

**24b. Two Blitz operations are deliberately unreachable.** `blitz-phone` and
`blitz-waterfall-icp-keyword` are in neither `enrich.COSTS` nor
`enrich.CALL_STAGE` nor `waterfall.STAGES`. The first means such a call would
cost 0 against the cap; the second means it cannot be recorded at all and
raises out of `spend()`. `waterfall-icp-keyword` asks "which companies exist",
a question no stage asks, and giving it a stage would need a ContactOut first
step that has no REST route in `contactout.py` today. `src/discovery.py` is the
module that would own it.

**24c. `src/preview.py::_provider_trail` has no `blitz` key.** It reads the
event log, so it costs nothing either way, but once a Blitz call is wired the
preview will report a provider trail with a hole in it.

## 25. The sequence gate is opt-in, and the Icebreaker mapping is not decided

`heyreach.refuse_unsupported_sequence` now refuses to build a payload for a
campaign whose configured copy uses a variable the push does not supply, and
`push.payloads` calls it. Two things about that are deliberately incomplete.

**25a. `payloads(heyreach_sequence=None)` checks nothing.** The gate is a
parameter rather than a fetch because `payloads` is pure and every test depends
on that, and because a just-in-time check has to read the sequence at push time
rather than trust a snapshot. `push.run()` therefore still owes the live fetch.
It is not wired today because `run(live=True)` raises before anything is sent,
so there is no path where the omission can reach a prospect - but the moment a
live push exists, passing no sequence must stop being legal. Until then
`python -m src.providers.heyreach --sequence <id>` answers the same question
read-only, and it is what to run before pointing a canary at a campaign.

**25b. Nothing maps our fields onto `{Icebreaker}`.** HeyReach campaign 565765
is the only campaign in the workspace whose copy uses a non-builtin variable.
`build_lead_pairs` can now carry any custom field from a row, so the mapping is
possible - but no code chooses it, and that is on purpose. The variable name is
a property of the client's existing campaign rather than of this data model,
and guessing that `{Icebreaker}` should be fed from our LinkedIn `note` is
exactly the kind of invention that puts the wrong opener in front of a real
person. Until somebody states the mapping, the gate refuses, which is the
correct default: a refusal costs a conversation, and a wrong guess costs a
prospect.

The consequence worth being explicit about: **campaign 565765 cannot be used
for the canary as things stand.** Either the mapping is stated, or the canary
points at one of the 31 single-sender `CHECK_IS_CONNECTION -> MESSAGE -> END`
campaigns, whose copy uses only `FIRST_NAME`, `COMPANY` and `POSITION` - all of
which `build_lead_pairs` already fills.

## 26. The brakes are reported, and enforced only by a caller that does not exist

`killswitch` had one importer, `workspaces`, and only to describe a setting.
`pilotcaps` had none at all. Both are now consumed - `push.run` carries
`sending` (every kill-switch layer and its verdict) and `caps` (what the batch
would consume against the pilot ceiling) - so neither is arithmetic nobody
reads. That is the defect closed. The gap is what remains.

**26a. Reporting is not enforcement, and the enforcing caller is the sender.**
`killswitch.require` and `pilotcaps.require` raise, and nothing calls either.
They cannot be called from `push.run`, and both wrong turns were tried:

* `killswitch.require` in a dry run refuses every step - correctly, since the
  global layer answers "this build cannot send" - and a preview that refuses
  itself prepares nothing for anyone to review.
* `pilotcaps.require` at preparation time is wrong twice. `day` is a cadence
  day rather than a calendar day, so a run's count is not the quantity
  `email_per_day` limits; and a prepared payload costs nothing until something
  sends it. Enforcing on a mis-mapped quantity is worse than not enforcing,
  because it produces a refusal people learn to route around.

So the true enforcement point is whatever eventually sends, counting real sends
against a real calendar day. Both `require` functions exist, are tested, and
default to off/refuse precisely so that the day somebody deletes the refusal in
`push`, the brakes are already there rather than being invented under time
pressure with a client waiting.

**26b. `sending.live` still stops nothing.** `workspaces.POLICY_KEYS` has said
so all along. It is a real setting with an audit entry whose only reader is
`killswitch.workspace_state`, and until a sender calls `killswitch.require`,
turning it off changes no behaviour. It is safe today only because the build
refuses to send in code, which is a guarantee about this build rather than
about the policy.

**26c. The pilot ceiling is breached by the fixture estate, on purpose.** A
`push.run` over `phase7.jsonl` prepares 28 email rows against a ceiling of 20.
That is now visible in `caps` rather than silent. It is not a bug in the
fixture: it is the condition the report exists to surface, and it would have
been invisible while nothing consulted the ceiling.

## What is *not* a gap

Worth naming, because each has been mistaken for one:

- **Two verifiers disagreeing holds an address.** That is the double
  verification rule working, not a verification failure.
- **A contact with no email but a LinkedIn profile.** Reachable on one
  channel is a normal state, reported as `linkedin_only`.
- **A refused claim on the outreach preview.** The claim resolver failing
  closed is the resolver working; `Claim diagnostics` shows what each refusal
  would need.
- **A campaign awaiting approval.** Nothing is push-eligible until a human
  says so, by design.
- **A viewer reading the report editor, and generating a client PDF.** Both
  look like role leaks and both are decisions with tests on them: the report
  is *for* the client-facing role, and reading a draft it cannot change
  costs nothing. `tests/test_client_reports.py` and
  `tests/test_report_editor.py` name them.

## 27. What the 2026-09-09 restart audit found

Three read-only audits after a machine restart, over the provider waterfall,
the canary send path and the Productive artefacts. The barrier defect that
prompted them is fixed in `a191a2a`; everything below is recorded, not fixed.
Ordered by what would bite first.

**27a. Paid negative verification evidence was overwritten by "unknown", and
it is still overwritten.** On `brightpath-com` the event log holds eight
`verification_result` events - `accept_all_uncleared` for `jonathan-gessert`
and `briley-brind-amour`, twice each - backed by seven `email_verification`
waterfall rows (contactout x2, deliverable x3, reoon x2) at 13:27 and 15:17 on
2026-09-08. At 15:49:26 a `verification_started`/`verification_result` pair
with `contact: null` and `state: "unknown"` landed, and the stored
`verification` block on both contacts now reads `state: "unknown"`, `cost: 0`,
`providers: []`, `evidence: []`.

This is missing evidence overwriting *negative* evidence, which is worse than
the rule against missing-as-positive usually covers: a recorded "not safe to
send" became "unknown", and unknown is the state that gets re-bought. The
13:27 -> 15:17 pair shows the re-buy already happened once.

`store.refuse_evidence_loss` would refuse this write today. It landed in
`59e8be2` at 2026-09-08 18:14:38Z, **two and a half hours after the loss at
15:49:26Z**, so this is damage that predates its guard rather than a hole in
it. The verdict is recoverable from the append-only event log without
spending anything. That repair is not attempted here: it is a write to real
client state, and the last time repairs like it were batched they produced
the three most serious findings of that round.

**27b. The waterfall's ordered table routes nothing.** `waterfall.STAGES`
holds the provider order per stage, including every Blitz position. Its
accessors - `providers_for`, `first_provider`, `contactout_is_first` - have no
caller outside `waterfall.py` itself. The order that actually executes is the
literal top-to-bottom position of the `if ... and spend(...)` statements in
`enrich.enrich_record` (`enrich.py:500, 518, 544, 568, 588`), and
`enrich.plan` restates the same order a second time by hand. `STAGES` can only
reject a tuple the hand-written code already chose; it cannot supply the next
provider. So "ContactOut first, Blitz second" is enforced by statement order
in one function, and the table that appears to define it is a post-hoc
validator.

**27c. The waterfall is not field-aware, so "ContactOut missed" cannot be
expressed.** Every gate tests `usable_contacts` (`enrich.py:140`), which is an
email-presence test. Nothing anywhere asks whether *LinkedIn* or *phone* is
the missing field. The stages `LINKEDIN_URL` and `PERSON_RESEARCH` have no
call mapped to them in `enrich.CALL_STAGE`, so no ledger row can carry them,
and the reason codes `CONTACTOUT_NO_COMPANY_LINKEDIN` and
`CONTACTOUT_NO_EMAIL_DOMAIN` are declared but emitted by nothing. The
consequence for the standing direction: a contact with an email but no
LinkedIn URL - exactly the case `blitz-domain-to-linkedin` exists for - is
indistinguishable from a fully enriched one. Field-aware routing is the
prerequisite for the Blitz rung, not a refinement of it.

**27d. `verification` bypasses `enrich.spend()`.** `verification.py:690` calls
the verifier directly, charges `budget` at `:670` and writes its own ledger
row at `:702`. It is the largest spender in the system at one to three credits
an address. Three consequences: the `PERSON_LEVEL` ICP gate is never consulted
for it, no `PROVIDER_CALL_PLANNED` event is emitted, and `record_step` runs
*after* the network call - so a `WaterfallViolation` there fires once the
money is gone, the reverse of `enrich.spend()`, where `require` is pre-flight.
CLAUDE.md says every paid call goes through `spend()`; this one does not.

**27e. `preview._provider_trail` reports the opposite of the truth after a
real run.** `used` is computed from `provider_call_completed` /
`contact_found` entries filtered on `entry.get("provider")`. In `src/`, only
`verification.py` writes `PROVIDER_CALL_STARTED`/`COMPLETED`; `enrich.spend()`
writes only `PLANNED`/`SKIPPED`/`ESTIMATED`, and `enrich.py:533, 579` write
`CONTACT_FOUND` with `source=`, not `provider=`. So those rows fail the filter
and are never seen: after a live enrichment the trail reports `aiark.used ==
False`, and the `why` string it surfaces is pulled from a
`PROVIDER_CALL_PLANNED` event - it prints the reason a provider **was** called
as the reason it was **not**. Only `demo.py` writes the events this function
expects, which is why it reads as working. It also has no `blitz` key, so a
Blitz event would be silently dropped rather than raising.

**27f. In `push.run`, the live refusal stands in front of every other guard,
not behind them.** `if live: raise LiveSendNotEnabled` is the first statement
of the function body (`push.py:442-446`). Record loading, `collect`,
`payloads`, `pilotcaps.check` and `killswitch.state` all come after it. So no
guard is consulted before the refusal, and the body has never executed with
`live` meaning anything. Whoever lifts the refusal does not inherit a stack of
checks that were already running in dry mode - they inherit a function whose
remaining body is unexercised for the case they just enabled, and whose cap
and kill-switch verdicts are computed *after* the point a sender would need
them.

**27g. The brakes are reported to nobody.** Extends 26. `push.run` returns
`caps` and `sending`, and its only caller in `src/` - `run.py:250-254` - reads
`result["counts"]` and `result["ready"]` and nothing else. So the reporting
form of both brakes is itself computed and discarded, not merely
unenforcing. Separately, `killswitch.state(workspace=recs[0].get("client"))`
(`push.py:483`) names the first record in the whole store rather than the
`client` the run was filtered by, so a `--client productive` run can report
another tenant's kill-switch state.

**27h. The sequence gate is armed by none of its callers, and the reachable
form is the optimistic one.** All four callers of `push.payloads` pass no
`heyreach_sequence` (`push.py:449`, `campaigns.py:768`, `web/api.py:2914`,
`demo_outreach.py:587`), so the gate at `push.py:300-303` never runs.
`heyreach.campaign_sequence` is reachable only from the manual CLI
`--sequence`. Worse, that CLI path calls `supplied_field_names()` with no
rows, which returns the maximal probe field set, while the enforcing path uses
the per-row intersection - so the command an operator would run before a
canary can answer "ok" for a cohort the enforcing path would refuse. And the
`BISON_HANDOFF` hazard, the one that matters for a LinkedIn-only canary
because it hands the prospect to an EmailBison campaign this system did not
write, is returned to `push.payloads` and discarded at `:301-303` without
being logged, stored or surfaced.

**27i. No real contact has a sender assignment, and nothing refuses that.**
Extends 21 item 12 with the measurement. The only writer of
`contact["sender_assignment"]` is `assignment.ensure`, whose only caller in
`src/` is `web/demosenders.py:195` - demo code. All three real contacts in
`work/queue.jsonl` have no `sender_assignment` key. So every real LinkedIn row
would resolve through `heyreach._account_id_for` to `linkedInAccountId: 0` and
be bucketed by `push.sender_summary` under the literal string `"unassigned"`,
which nothing refuses on. `senders.check_mapping` reads `campaign["senders"]`
and never looks at a contact.

**27j. A one-person canary is expressible but not enforceable.**
`approve.approve_record` approves every approvable step for *every* contact on
the record: it takes `step_keys` but no `contact_keys`, so
`approve record --id brightpath-com` would approve both Anthony and
Briley in one action. The per-person path exists only as the `approve step`
subcommand. Nothing counts touches: `killswitch` has six layers and none of
them is a per-touch counter, and the `pilotcaps` ceilings that define a cohort
- `companies: 20`, `contacts: 40` - are never placed in the plan dict
`push.py:468` builds, so `pilotcaps.check` reports them `unchecked` rather
than passed. What does hold today is per-step approval plus the mapping check:
approving the canary campaign right now releases **0** of its 21 candidate
touches, because no step has an approval fingerprint and both
`heyreach_campaign_id` and `bison_campaign_id` are null.

**27k. The operator-facing export is stale, and one batch artefact is simply
wrong.** The load-bearing check passes: `out/domains/*/people.csv` and
`people.json` name exactly the people the queue holds, across all 50 domains,
so the incident where an approval request would have named the wrong people
does **not** recur. But `out/summary.json` says `records: 100, queued: 100`
against an actual 50 records at 48 queued / 2 held, and `out/review.html`
renders zeros throughout. The `excluded` blocks are staler than the people
blocks - the export ran at 18:53:22 and the queue was written at 20:15:57 - so
`Rivers Colyer` appears three times in the artefact against once in the queue,
and `Rick Cheetham` twice against once. Artefact `excluded` entries carry no
`key`, so an excluded person cannot be joined back to the record by identity,
only by name string.

**27l. Two red-team findings are fixed, one is not reproducible, and two
stand.** Re-measured against the current queue. Fixed: no contact appears in
both `contacts` and `excluded` (0 of 50 records), and `Rivers Colyer` appears
once rather than twice. Not reproducible: the reported 11 orphaned events -
all 31 contact-referencing events resolve, 0 orphans. Still true:
brightpath carries 2 contacts against a tier-C cap of 1, because
`max_contacts_to_enrich` is read only by planning and reporting while
`personas.select_domains` caps by `cap_per_domain` alone; and `ninefields.test`
still has 0 contacts, where "Design Studio Manager" fails the client YAML's
persona titles even though it contains `routing.RESOURCE_MANAGEMENT_TITLES`'
"Studio Manager" - those routing lists rank, they never classify. A related
residue: 9 pairs of duplicate *people* survive in `excluded` under
hash-suffixed keys (`devon-adams` vs `devon-adams-46997d`), which no key-based
dedupe catches. And 32 of 63 events carry `contact: null`, including every
event for the two contacts an operator would actually approve - so those two
have no per-contact audit trail.

**27m. `tools/mutation_audit.py` has no state isolation, so mutating a
state-write guard destroys the estate that guard protects.** Demonstrated
today, by doing it. Six mutations were added to pin the new barrier - one per
call site plus the guard body - and all six were caught. But `run()` spawns
`python -m unittest` with the ambient environment, `QUEUE` unset, so every
state file resolves to the real `work/`. Each mutation removes the guard and
then runs the guard's own tests, whose entire job is to *attempt* the
dangerous write. With the guard gone the attempt succeeds:
`work/queue.jsonl` was left empty (`d41d8cd9...`, the md5 of a zero-byte
file), `report-drafts.jsonl` replaced with a single row, `replywatch.json`
and `checkpoints.json` overwritten, and `mx-cache.json` and a
`guard-probe.jsonl` created. All were restored byte-for-byte from a backup
taken before the run, and the queue re-verified by content - 50 records,
3 QUALIFIED / 9 REVIEW / 38 UNKNOWN, no `walk-` fixtures - rather than by
hash alone.

**The six mutations were removed rather than kept**, and the audit stands at
549. A harness-level fix does not work here: pointing `QUEUE` at a throwaway
directory would not help, because these tests deliberately *unset* `QUEUE` in
`setUp` to resolve the real `work/` - testing the real directory is what they
are for. So the rule is a constraint on what may be mutated, not a patch:
**no mutation may disable a guard whose test performs the action the guard
prevents, until the audit isolates state.** The guard is pinned instead by
`tests/test_tests_cannot_write_client_state.py`, whose five call-site tests
were each proven load-bearing by removing one guard at a time and restoring
`work/` from a snapshot after each - which is the only safe way to run that
attack, and is not something the audit tool does.

Worth checking before the next full audit: whether any of the existing 549
mutations disables a different guard whose tests reach real state. This one
was found by diffing `work/` against a snapshot, not by anything in the tool
reporting a problem - the audit printed `6/6 mutations caught` while the
estate was empty.

## 28. The prototype could send, and the claim that nothing could did not know

**FIXED in the same commit that records it, which is why this section is short
on remediation and long on how it survived.**

`prototype/bin/push.py --live` did a real `requests.post` to
`campaign/AddLeadsToCampaignV2` and to EmailBison's `campaigns/<id>/leads`. No
eligibility decision, no approval fingerprint, no killswitch, no pilot cap, no
account fatigue, no sequence check, no suppression, no MX screen, no
verification gate. It then rewrote `work/queue.jsonl` with its own
`json.dumps` loop rather than through `src/store.py`, so the tenancy
validation, the identity invariants and the evidence guard never saw the write
either - the same mechanism that destroyed the Productive estate once already.

It needed an API key in the environment and a flag.

**What makes this a process finding rather than a code finding.** Three
documents state, as the load-bearing sentence under which everything else is
safe, that no code path reaches a provider:

- `LIVE-READINESS.md` section 3 classifies both sending rows BLOCKING - "Not a
  flag: there is no code path to either provider".
- `RELEASE-CANDIDATE.md` rests "Live Productive pilot - NO-GO" on it.
- `RESUME-CHECKPOINT.md` blocker 5: "there is still no send path".

All three were derived by reading `src/`. `prototype/` was excluded from every
audit that established the claim, and nothing imports the file, so no import
graph found it and no test covered it. The one place it does appear is
`tests/test_fixture_hygiene.py`, which explicitly puts `prototype/` **out of
scope**. An exclusion written for one purpose - fixture naming - silently
became an exclusion for the safety audit.

`out/heyreach.csv` still holds three real prospects with real LinkedIn URLs,
staged and ready for it. The file was not theoretical; it was loaded.

**The fix.** `refuse_live()` on every path that would reach a provider or
rewrite the queue - four call sites, placed per-path rather than once at the
entry point because `push_heyreach` is also called directly by the `--to both`
branch. Dry run still works, which is the only thing the script was ever safe
for. `tests/test_the_prototype_cannot_send.py` loads the module and calls it,
including a test that plants `None` over `requests` in `sys.modules` to prove
the refusal lands before any transport is reached.

**One deliberate omission in the verification.** Every other guard added this
session was attacked by removing it and confirming the intended test went red.
This one was not, and must not be: with the refusal removed, the test calls
`push_heyreach(live=True)`, and the failure mode of that attack is the
irreversible send the guard exists to prevent. A guard whose attack is
indistinguishable from the incident cannot be tested that way. This is the
same class as 27m and the second instance in one session - **the repository
now has two guards whose natural adversarial test is itself the hazard**, and
that pattern deserves a general answer rather than a note each time.

**What to check next, and this is the actionable part.** `prototype/` was
never in scope for any audit. This file was found by chance, while tracing an
unrelated HeyReach question. Nothing here has established what else is under
`prototype/`, `tools/` or `batches/` that can reach a provider, spend a
credit or write client state. Until that sweep is done, "nothing can send"
remains a claim about `src/` and should be written that way wherever it
appears.

**The sweep, done.** `prototype/bin/` holds six scripts; three open a
transport. `push.py` was the send path and is now refused. `check.py` pings
five providers read-only, and one of those pings verifies
`test@example.com` through Reoon - a real verifier credit on a free-looking
health command. `verify.py` runs Reoon over addresses read straight out of
`work/queue.jsonl`, with its own `REOON_KEY`, no cap, no `spend()` and no
waterfall row: a paid call invisible to the spend audit, which is the exact
condition CLAUDE.md names. Neither can send, so the corrected claim - "nothing
in `src/` or `prototype/` can reach a prospect" - now holds. Neither was
disabled: they are manual tools somebody may deliberately run, and silently
breaking them is not this change's business. `tools/` holds only the mutation
audit; `batches/` holds one CSV.


## 29. What the field-aware waterfall closed, and what it exposed

### 29a. The declared order and the executed order were two things - FIXED

`waterfall.STAGES` held an ordered provider list per stage and
`providers_for` / `first_provider` / `contactout_is_first` had no caller
outside `waterfall.py` itself. The order that executed was the top-to-bottom
position of the `if ... and spend(...)` statements in `enrich.enrich_record`.
Two representations of one decision, and they disagreed: the table put AI Ark
ahead of Blitz for email discovery, so "Blitz second where ContactOut missed"
was false in the one place it was written down.

`src/fieldplan.py` routes from the table, so the table is now the order.
Reordered to ContactOut -> Blitz -> AI Ark on every stage that had both, and
`linkedin_url` gained the Blitz rung it never had.

### 29b. Twenty-five credits a run, on facts already on the record - FIXED

`enrich.already_bought` protects a record by asking whether a waterfall row
exists. Forty-seven of the fifty Productive records have no waterfall at all,
and twenty-five of those already carry the company facts
`company-information-from-domain` buys. Measured: 47 calls before the field
gate, 22 after.

`email_domain` is why the gate asks `filled_by` rather than "is any company
field unknown". ContactOut returns no mail domain under any spelling, so a
predicate over every company field found that one permanently UNKNOWN and
licensed the purchase on every run, for ever.

### 29c. Three defects only real data exposed - FIXED

None of the three appeared against fixtures; all three appeared on the first
run over `work/queue.jsonl`.

- `tried()` matched the ledger row's `stage`. `enrich.CALL_STAGE` files each
  call under exactly one stage while `decision-makers` answers four, so "has
  anyone been asked for this person's LinkedIn URL" answered no for ever and
  the fallback after it would have been bought against a question ContactOut
  had already answered. Matched on the call now.
- `next_step` returned None at the first fallback whose `requires_reason` the
  field could not supply. `company_information` holds three Blitz calls for
  three different fields, so that made the mail domain unroutable.
- `cost_of` charged one call once per person per field and reported the estate
  at 382 credits. One call answers a stage's question for everybody at the
  company. A forecast that over-reports is the number a cap gets sized
  against.

### 29d. Still open: the ledger cannot attribute a per-person call

`waterfall.entry` has no `contact` column, so a `blitz-email` row for person A
and one for person B are indistinguishable. Company-scoped attribution is
correct for `decision-makers`, which returns everybody in one response, and
wrong for the per-person Blitz calls - `blitz-email` is the first. `fieldplan.
tried()` says so in its docstring. Costless today because no per-person Blitz
call has a call site; it must be closed before one does, and
`waterfall.entry` is the single constructor, so it is a one-place change.

### 29e. Still open: four planners, and now five

`enrich.plan`, `verification.plan`, `refresh.staleness` and
`dmplan.for_company` all compute "what would we call next" and all four are
display-only. `fieldplan` is consumed by execution, and `enrich.plan` now asks
`fieldplan.company_info_is_owed` so the forecast and the run share one
predicate - but the other three still hold their own opinions. Not urgent and
not harmless: `verification.py` carries a comment about the production bug
caused when its forecast and its execution drifted.

### 29f. Still open: `phone` and `personal_email` are not modelled

`fieldplan` reports `phone` as UNSUPPORTED rather than missing, because no
contact field stores one and no channel dials one - an answer would have
nowhere to land. `blitz.phone` and `blitz-phone` therefore stay unreachable by
construction. `personal_email` is the same: the only references in `src/` are
in a test-data generator. Model the field before routing to it.


## 30. What one metered Blitz call bought

One authorised call, `POST /v2/enrichment/company`, one Blitz record. The free
`key-info` call ran first and earned its place twice over: `allowed_apis` is
the only authority on whether the key may call a route at all, and a 200 there
converts any later 404 from "this API key does not exist" - which `_refuse`
hard-codes - into proof of a wrong path.

**Three silent defects, none of which the 62 existing Blitz tests could have
caught**, because every one of them asserts against a dict written by the same
author as the code. All three are fixed.

- The request field is `company_linkedin_url`, not `linkedin_url`. Sending the
  wrong one returns 422 and bills nothing, so every call would have failed
  while the ledger showed no spend at all.
- The headcount is `employees_on_linkedin`. Not one of `employees`,
  `employee_count` or `headcount` is on the wire, so the trim read None where
  the server said 19. `size` is also there as a band (`"1-10"`) and is
  deliberately not read into `employees`: a band is not a count.
- The location is a nested `hq` object. `_text` would have stringified the
  whole dict into a trimmed field, which is a raw payload escaping under a
  different shape.

**Still unconfirmed, and now untrustworthy rather than merely unproven.** One
request field name was wrong, so the others are suspect: `domain-to-linkedin`
sends `{"domain": ...}`, `linkedin-to-domain` / `email` / `phone` send
`{"linkedin_url": ...}`, and none has been seen. **A Blitz call for real
client data is not yet safe**, which is the operative conclusion: the rung is
routable and its contract is one-eighth confirmed.

**The free way to finish it.** A deliberately empty request body returns 422
naming the field it expected, and bills nothing - that is how
`company_linkedin_url` was found. Six routes could have their request contract
confirmed for zero records that way. Not done here: it needs permission to
make provider calls beyond the one authorised.

**A display defect with a real consequence.** `blitz.check()` prints only the
first four entries of `allowed_apis`. On that truncated list the entitlement
appeared to exclude every enrichment route, and the conclusion drawn from it -
that Blitz could not serve its waterfall positions at all - was wrong. The
full response entitles all eight. A health line that truncates the
authoritative capability list invites exactly that error.

`records_remaining` was 30,000,000 before the call and 29,999,999 after, which
is both the receipt for one record and the reason one record is not a
decision.


## 31. What is now provable about a LinkedIn-only canary

`heyreach.linkedin_only` answers the question `sequence_hazards` could not.
The detector searches `json.dumps(sequence)` for `SEND_LEAD_TO_BISON`, so its
silence meant "that one string is absent", not "no email leaves this
campaign"; it never walked the graph, so it could not tell a complete graph
from one whose branches it never saw; and its verdict was discarded by its only
caller at `push.py:301`.

The predicate is an allowlist over the node types actually reached and fails
closed on an unfetched sequence, a typeless node, a branch holding an id rather
than a node, and any node type it cannot classify. It keeps two facts apart -
"this hands the lead off", naming the egress node, and "this uses a node I
cannot classify", which says explicitly that it is not proof of email. The
payload carries the verdict under `heyreach.sequence`, and an absent sequence
is stated rather than left empty: an unfetched sequence and a clean one must
not look the same to a reader.

**What it still cannot do, and this is the honest limit.** No recorded HeyReach
sequence exists anywhere in this repository - not for campaign 565765, not for
any of the 79. So the predicate has never been run against a real graph. Three
consequences:

- The allowlist holds seven node types. Four are named anywhere in this
  repository; the rest are inferred. A real campaign using a legitimate
  LinkedIn node absent from the list will be refused as unprovable, which is
  the safe direction and will look like a false alarm.
- `GetCampaignSequence` may or may not return the graph whole. The code
  asserts only that it is a dict. If HeyReach paginates branches or returns
  node references, `truncated` should catch it - but that is untested against
  the real thing.
- The claim that 31 campaigns are single-sender
  `CHECK_IS_CONNECTION -> MESSAGE -> END` names no ids and stores no
  sequences. It is unverifiable offline.

**The next action is a read, not a write.** `python -m src.mapping list
--provider heyreach` for the inventory, then `python -m src.providers.heyreach
--sequence <id>` per candidate, persisted under `work/`. Both are on the read
allowlists and mutate nothing. Until one real sequence is stored, "LinkedIn-
only" remains a predicate with no subject.


## 32. The client's own estate has already worked the entire pilot cohort

**This is the finding that changes what a canary is, and it is measured.**

`GET /leads?search=` over the Productive workspace, read-only, for all fifty
pilot accounts:

| verdict | accounts |
| --- | --- |
| **CLEAR** - no lead at the domain at all | **8** |
| touched - emails sent, nothing running now | 21 |
| **in_sequence** - somebody is being worked right now | **20** |
| unresolvable | 1 |

The two contacts selected for the one-person canary:

| contact | prior contact from the live estate |
| --- | --- |
| the BrightPath COO | **21 emails across three campaigns**, 0 opens, 0 replies |
| the Northbeam COO | **4 emails, a live campaign, `in_sequence`** |

`work/queue.jsonl` recorded zero confirmed touches for both, and it was correct
about what THIS system had done. The client's estate has been working the same
list since April: dozens of campaigns (a few active), hundreds of inboxes, a six-figure
lifetime send volume and a five-figure lead list. A colleague at the BrightPath account is
`bounced`, which is a deliverability fact about the domain that no verifier
credit would have told us.

`PRODUCTION-TRANSITION.md` predicted this and called it the single most likely
way a first pilot does visible damage. It is no longer a prediction.

**What it means for the canary.** All three qualified accounts are touched or
in-sequence, so a canary on any of them is a second sender arriving at a
company somebody else is already working - on either channel, because campaign
352 is a HeyReach-fed campaign and both selected people are in it. The eight
clear accounts have no discovered people. **So there is no safe canary
candidate today, and that is a data conclusion rather than a code blocker.**

The best candidate is the one clear account that is not `unknown`: it scores 38
at `review`, and the field-gap analysis measured that one ContactOut credit for
headcount and offices takes it to 51 and `qualified`. Person discovery on it
would be ten more.

### 32a. `src/collision.py` closes the gap, and the search is the hard part

The check is read-only and account-level as well as person-level, because
outreach here is account-based. Getting the query wrong fails **open**, and
three of the four obvious forms do:

    ?email=<addr>          ignored, returns the whole estate
    ?filter[email]=<addr>  ignored, returns the whole estate
    ?q=<term>              ignored, returns the whole estate
    ?search=<bare label>   exact
    ?search=<label.tld>    a five-figure row count - and the SAME a five-figure row count for an account with no
                           leads at all

So a check written as "search the address; nothing found means clear" would
have cleared every account on a broad match. The label is searched, the address
is matched locally, a neighbour whose name shares the prefix is dropped rather
than blamed on this account, and a response that looks broad rather than
filtered raises `CollisionUnknown`. **Unknown is never CLEAR** - that
distinction is the module's whole point, and the guard earned itself
immediately: it refused 7 accounts on the first sweep that a naive check would
have called clear.

### 32b. Still open: there is no HeyReach-side prior-contact check

`collision` reads EmailBison's lead list. The LinkedIn lane has no equivalent,
and it needs one: a live campaign is HeyReach-fed, so LinkedIn has been used on
these people too, and a LinkedIn canary would collide without anything
detecting it. `POST /inbox/GetConversationsV2` is already on the read
allowlist and is the likely source.

### 32c. Still open: nothing on the send path calls it

`collision` is a module and a CLI. `eligibility.decide` does not consult it,
and it should not until the send path exists - a pre-send check that runs hours
early is the planning-time read this project has already been warned about. The
right consumer is the JIT check immediately before an external mutation, and
that is where it must be wired.


## 33. What the provider inventories actually are

### 33a. 225 inboxes, and why the first read said 15

`meta.per_page` is 15 and `meta.last_page` was 15. Fifteen was the page size.
The read looked at `data` and never at the envelope, and there was no adapter
function to look at it for anyone, because the route had only ever been probed
by hand. `bison.sender_emails` now walks every page and raises
`PartialInventory` rather than returning a list shorter than `meta.total`.

Reconciled: **225 of 225 Connected**, 86 domains all Productive-branded, zero
Greenfield, `daily_limit` 15 on every inbox, 224 of 225 with warmup enabled,
a six-figure lifetime send volume and a sub-1% bounce rate.

Canonical: **202 READY, 23 DEGRADED** (20 on a lifetime bounce rate at or above
2%, 3 warming with nothing sent). **READY capacity 3,030/day.** Provider truth
is stored under `provider_state` and readiness is derived from it, so a screen
and a scheduler cannot disagree. `sender_id` is None on all 225: HeyReach and
EmailBison both know nothing about who owns an inbox, and 225 invented owners
would be worse than none.

### 33b. 41 seats, 33 auth-valid and active, 32 approved

First read of `/li_account/GetAll` from this repository - the route was on no
allowlist, and a comment saying sender accounts were unavailable had the wrong
route name rather than an absent capability.

`authIsValid AND isActive` is **33**, reconciling exactly with the operator's
attestation. One seat is excluded from the approved pool: it is the only one
carrying a `productive.test` address and is most likely a real employee's own
profile, so a canary from it would put a person's own LinkedIn at risk rather
than an agency seat. **32 approved: 29 READY, 3 DEGRADED** - one exhausted
against today's connection limit, two cooling down.

**Real limits, read for the first time.** `accountLimits` carries connection
request, message, InMail, follow, post-like and profile-view limits with their
maxima, plus four cooldown booleans. Every approved seat has a ceiling of 40
connection requests; **1,160/day across the ready pool, 970 remaining today.**
The provider's own key spelling is `connectioRequestLimit`, typo included, and
it is read under that name rather than a tidier one.

`accountLimits` answers what `PRODUCTION-TRANSITION.md` recorded as UNKNOWN in
both confirmed contracts. That entry was written before this route was found
and is now out of date rather than wrong.

### 33c. Still open: utilisation is not the same as a limit

`connectioRequestLimit` moves between reads and `connectioRequestMax` does not,
so the pair reads as remaining-today against a ceiling - but nothing confirms
that, and no consumed-today counter is named. Capacity here is a ceiling, not a
budget. `senders.DEFAULT_DAILY_LIMIT = 50` still silently assumes a limit for
an account that has none, which now matters more than it did: the real ceilings
are 15 and 40, both below it.

### 33d. Still open: `senders.jsonl` has real ids and no owners

The `linkedInAccountId: 0` fallback is no longer reachable through a fixture id
- the roster now carries real provider ids, 116968 to 212356 - but every row
has `sender_id: None`, so `push._sender_of` still returns empty strings and
`heyreach._account_id_for` still degrades to `0` rather than refusing. The
fixture half of PRODUCT-GAPS 27i is closed; the refusal half is not.


## 34. The credential's workspace moved mid-session, and three reads answered CLEAR

**The hazard this repository documented in prose happened live, and it was
caught by the guard it had already built - after that guard had been skipped.**

Timeline, all on 2026-09-09:

| | |
| --- | --- |
| 12:07 | `GET /api/users` reports workspace **10, PRODUCTIVE**. The 50-account prior-contact sweep runs: 8 clear, 21 touched, 20 in-sequence, 1 unresolvable. Binding verified before and after |
| later | Three prior-contact re-reads on `ninefields.test` answer **CLEAR**, `leads=0` |
| then | `GET /api/users` reports workspace **29, Bluewave**, and the whole estate reads `total: 0` leads |

Nothing changed on this side. The active workspace is chosen in the vendor's
UI, and `bison.py`'s own probe matrix already recorded that this credential had
answered for four different estates in two days.

**So those three CLEAR verdicts were read against another client's empty
estate.** The 12:07 sweep is the Productive truth and stands; the later re-read
is discarded. `ninefields.test` is `touched` - one lead, 9 emails sent, campaigns
328 and 352 - not clear.

### 34a. The guard existed, was optional, and was skipped - FIXED

`bison.require_workspace` was added earlier the same day and
`collision.leads_for_domain` took `expect_workspace=None`. Every call in the
sweep and every call afterwards omitted it, so the guard never ran. An optional
guard on a path whose failure mode is a false clear is a guard that gets
skipped, and it was - by the author of both, within an hour.

`expect_workspace` now has **no default**: `collision.leads_for_domain`,
`check_address` and `check_account` raise `CollisionUnknown` when it is absent,
before any wire call, and the CLI requires `--workspace`. Every answer carries
the workspace it was read against, because a verdict without its estate is
unreadable a day later. Seven tests pin it, including one asserting no provider
call is made on an unpinned read.

### 34b. What this says about every other provider read

`sender_emails` takes the same optional pin and `senderinventory` passes it from
`BISON_WORKSPACE_ID`, which is **unset**, so the 225-inbox inventory was also
read unpinned. It is trustworthy only because the binding was separately
verified as PRODUCTIVE immediately before and after that sweep, and because
`credential_bound_to` is stamped on the report - not because anything refused.

`BISON_WORKSPACE_ID=10` should be set in `config/.env`. It is deliberately not
defaulted to 10 in code, for the reason `replywatch.expected_workspace` gives -
a default asserts ownership the code cannot prove - but the operator can assert
it, and until they do every EmailBison read in this project is one vendor-UI
click away from answering for somebody else.

### 34c. Still open: a read cannot be made atomic with its binding check

`require_workspace` calls `/api/users`, then the read follows. Between the two
the binding can move. The window is small and the alternative does not exist -
there is no route that takes a workspace and no header that scopes one - so the
honest position is that this reduces the window rather than closing it, and
that a long sweep should re-assert the binding at the end and discard itself on
a change. The 225-inbox sweep did exactly that by hand; nothing enforces it.


## 35. The LinkedIn lane could collide and nothing was looking - CLOSED

`collision` asked EmailBison and only EmailBison. A live campaign is HeyReach-fed
and the client runs 33 seats holding 25,595 conversations, so a connection
request could have gone to somebody one of our own seats was already talking
to. The read route was on the allowlist the whole time; nothing called it.

**What it found on the first run, against real data.** Two of the three
qualified accounts' primary contacts are already in a LinkedIn conversation
with seat **208242 (Lucija Bakic)**, four messages each:

| contact | company | last message | replied |
| --- | --- | --- | --- |
| Austin Ball | Northbeam Inc. | 2026-07-18 | no |
| Anthony Andreatos | 321 Web Marketing | **2026-09-04** | no |

Anthony's is five days old. A LinkedIn canary aimed at him would have been a
second seat approaching a live conversation inside a week, and every check
this system had would have passed it.

### 35a. The filter's reach was measured rather than assumed

`POST /inbox/GetConversationsV2` takes a `filters` object. Every field of a
real conversation was probed as a `searchString`:

| term | answers |
| --- | --- |
| `firstName` | 2 |
| `lastName` | 1 |
| `companyName` | **0** |
| `profileUrl` | **0** |
| `linkedin_id` | **0** |
| message text | **0** |

It matches the correspondent's NAME and nothing else. An unrecognised filter
key is discarded in silence and the unfiltered 25,595 come back, so a typo in
a filter name would have read as "no prior contact" for everybody - the same
shape as the EmailBison `?search=` defect in section 32.

So the query is broad and the match is local: search the **first name**, then
compare the profile slug. The first name rather than the full name because the
search is literal on punctuation - the apostrophe form of one candidate's
surname answers 4 and the stripped form answers 0, so a full-name term is a
fragile negative. On the two live candidates the first name scanned 12 and 41
real conversations instead of 0.

### 35b. Still open: the company-level LinkedIn question cannot be asked

`searchString` does not match `companyName`, so "has anybody at this company
talked to one of our seats" is not expressible as a query. It needs all 25,595
conversations walked and compared locally - 256 read-only pages.
`collision.account_is_unanswerable` returns UNKNOWN rather than letting a
caller read a person-level CLEAR as a company-level one.

### 35c. Still open: nothing on the send path calls either check

Both checks are complete and neither is wired into a pre-send gate. That is
deliberate - it belongs at the JIT check immediately before an external
mutation, not at planning time hours earlier - but it means the checks are
operator-run today, and an operator can forget.


## 36. The first email a prospect could ever have received was fabricated

`persona_pain` - the day-5 email, and the **first renderable email step in the
cadence** - opens with `{line}`. `{line}` had two branches:

```
evidence[0] if evidence else f"you are running {phrase} at {company}"
```

`rec["evidence"]` is written only by `generate.persona_angle`, which needs a
model, and `src/llm.py` ships `NoModel` and `ScriptedModel` and nothing else.
**So the preferred branch has never fired on any record in this repository's
history, and the fallback was the only text that could ever have shipped.**

That text is a factual claim about how somebody runs their agency, assembled
out of OUR angle wording and THEIR company name:

> Dana, you are running utilisation at Ninefields

Nothing on the record supports it. Substituted per angle it also produced
plain nonsense - *"you are running who is booked on what next week at Acme"*.

**Why both guards passed it.** `claims.is_claim` examines a sentence only when
it carries a number, a month word or an event word. "Running" is none of
those, so the claim checker never read the one sentence that needed reading.
And `lint` has no rule about asserting, because until now nothing asserted.

Replaced with the shape the LinkedIn note already uses honestly - who we work
with, and an admission that we do not know - where every value is on the
record:

> Dana, I work with Design Services teams on utilisation, and I do not know
> how Ninefields handles it

### 36a. Still open: `claims` cannot see this class at all

The fix is one template's fallback. The hole that hid it is unchanged: an
asserting sentence carrying no number, month or event word is still never
examined. `test_the_opener_asserts_nothing` pins that as a recorded gap rather
than a passing guard, and a phrase list in a test is not a substitute for
`claims` understanding assertion.


## 37. `evidence` is on the record and `verification` is on the contact

Two fields named for the same idea, read by different code, and one of them is
never written. `rec["evidence"][contact_key]` is the LLM-generated licensed
observation used by `cadence.template_vars`. `contact["verification"]
["evidence"]` is the provider verification ledger used by
`verification.decide`. The first is empty on every record in `work/queue.jsonl`;
the second drives sendability. Section 36 exists because the empty one looked
like the populated one.


## 38. Eight read-only red teams attacked the build. What they found

Overnight on 2026-09-09, eight independent read-only agents attacked tenancy,
execution and duplication, personalisation, 30k scale, provider contracts, spend
control, campaign lifecycle and architecture gaps. Every finding below was
reproduced before being acted on, and several were in code written hours
earlier the same night.

The pattern worth naming first, because it recurred in six of the eight
reports: **a complete, tested, documented guard with no caller at the point of
use.** CLAUDE.md names this defect. It is the dominant one here, and it is not a
tidiness problem - each instance reads as a guarantee in the documentation and
is absent from the running system.

### 38a. FIXED - the cap that controlled spend was read by nobody

`routing.plan` computes `max_contacts_to_enrich` - 3 for tier A, 2 for B, 1 for
C, 0 for anything not qualified - and its docstring says it "is the number that
controls spend". Readers: a forecast, two screens, a report. Verification read
every address on the record instead, at up to three credits each.

`run.STAGES` is what made it expensive: enrich, then qualify, then personas.
`decision-makers` can return dozens of addressed profiles for one company;
verification paid for all of them; the selection that trims them to the cap ran
afterwards. **Measured at 30,000 domains: roughly 252,000 credits verifying
people the system had already decided never to write to.** On the three real
qualified records it halves the bill.

`enrich.verification_candidates` honours the cap, orders by the plan's own
`target_titles` so the addresses bought are the ones selection would choose, and
breaks ties on the contact key so a resumed run buys the same ones. A record
qualification has not seen is deliberately NOT capped.

### 38b. FIXED - the provider read-back was bound to nothing

`executionguard` took `readback` as a plain dict and read three fields, one of
them a timestamp the CALLER stamped. Nothing tied it to a campaign, a channel or
a provider id, so a diff computed for campaign A satisfied the gate for campaign
B; and nothing marked it used, so one dict authorised any number of actions.
That is precisely the defect `Authorization` exists to prevent, one level up, in
the module that argues a dict claiming the gates passed is not proof.

`configdiff.Readback` is sealed, stamps its own timestamp after the last
provider read, carries what it compared, and is single-use.

### 38c. FIXED - four more defects inside the new gate chain

| what | why it mattered |
| --- | --- |
| `killswitch.require` was handed a campaign ID STRING where it needs the row | `campaign_state` raised AttributeError on `.get`, `except Exception` reported that as policy, **the campaign layer never evaluated at all**, and the test asserting the gate fires was satisfied by the type error |
| `actionledger.reserve` permitted a key already `sent` | and because `state_of` reads the latest row, it **regressed the state to `attempted`**, destroying the durable record that a real person had been contacted |
| the pilot cap was counted outside the reservation lock | two workers each reading nine against a ceiling of ten both passed; the ledger ended the day at eleven |
| the ledger's tenant was EmailBison's numeric estate id | two clients in one estate would share a ceiling; one client in two estates would have its ceiling split with both halves passing |

The killswitch one is the exact failure CLAUDE.md warns about - a red test
passing for the wrong reason - and the test now rejects a Python type error
explicitly.

### 38d. FIXED - the email approved side ignored approval

`approved_heyreach` filters to approved steps and explains why at length.
`approved_bison`, twenty lines below, appended every renderable email step. A
campaign with day5 approved and day10 not produced an APPROVED_CONFIG containing
both - and if the provider held both, the gate whose entire purpose is "the
provider holds what was approved" reported **PASS** on two emails nobody blessed.

### 38e. FIXED - a lost update under the reply path

`store.transaction`'s own docstring says a bare `save()` "cannot protect a
read-modify-write against a second process". `inbound.ingest` was doing exactly
that: load, apply a reply, save. A concurrent pipeline run silently erased the
reply, its pause and its event - and `refuse_evidence_loss` does not catch it,
because it indexes verification evidence rather than events or pauses.

So a positive reply that paused an account was revertible by any concurrent run,
and every later gate would then read a record that looked contactable. `handle`
does Slack I/O between the two mutations, so holding the lock throughout would
trade this hazard for the one measured in 38k; instead
`store.save(expect_digest=...)` refuses a clobber rather than performing one.

### 38f. FIXED - the test suite was reading the operator's real credentials

`tests/base.py` promises "no key may reach a provider from the developer's own
environment". That held inside `ProviderTest` and nowhere else, and most modules
here are plain `unittest.TestCase`. **Measured: 1,289 reads of the real
`config/.env` in one full run.** Afterwards `os.environ` holds every real
credential, and because such a module's cleanup restores the real urllib
transport, the urlopen tripwire is disarmed at the same time.

`tests/__init__.py` now points env loading at a path that cannot exist and
clears every credential at package import. Two modules turned out to be
depending on the real key and now set their own placeholder. The failure mode is
a loud `MissingKey` rather than a quiet live call.

### 38g. FIXED - a campaign list was one page, on the launch-gating path

`mapping.bison_campaigns` read page one of a Laravel `{data, meta}` envelope
with `per_page` 15 - the same shape and the same page size that once turned a
225-inbox estate into fifteen. One real estate holds 25 campaigns, so any id
past the first fifteen answered MISSING; `validate` treats MISSING as blocking;
so the launch was correctly blocked with a **false diagnosis**, and the message
printed says "either the id is wrong or the key belongs to another workspace".
Somebody would hunt a typo that did not exist.

It also returned `[]` for a body of the wrong shape, where `bison.sender_emails`
refuses and `providers.mapping` raises. And it was the one EmailBison reader
that never asserted its tenancy.

### 38h. FIXED - fabricated evidence, the loaded half

Section 36 replaced the `{line}` fallback. The PREFERRED branch was worse.
`llm.traceable` accepted a claim if any stored fact appeared anywhere in it, and
the company name is a stored fact - so every one of these passed against a
record holding only an industry and a headcount:

    "<company> raised a Series B in March and opened a Vienna office."
    "<company> is hiring four delivery leads this quarter."
    "<company> lost its largest retainer last month."

`check_evidence` then wrote them to the record, where `template_vars` prints
`evidence[0]` verbatim as the day-5 opener AND `claims.support_text` reads them
as support. The model wrote the claim, certified it, and the certification was
what the claim checker consulted. A fact may now only account for a claim it
substantially covers, and every number in a claim must appear in some fact.

### 38i. FIXED - nothing checked that the greeting named the recipient

`render.emailbison_rows` writes `first_name` from the contact and `body` from
the step independently, and `claims` cannot see a salutation - no number, no
month, no event word. So `tests/fixtures/phase7.jsonl` held twelve
byte-identical drafts, **eleven addressed to somebody else**, all twelve linting
clean and all twelve reaching the push file - in the fixture that defines what a
shippable estate looks like. `phase4` and `phase2` had the same defect, and so
did the suite's own canonical GOOD draft.

`lint.check` gains `greets_the_wrong_person`, narrow by design: it fires only
when a body greets SOME name that is not the recipient's.

### 38j. FIXED - two templates claimed a message we had not sent

`comparable_proof` opened "one more note and then I will leave it" and
`comparable_proof_short` "following on from what I mentioned". `breakup` was
fixed for exactly this one screen below them. `due(day=21)` returns day3, day5,
day10 and day21 in ONE batch and 21 is `run.py`'s default, so day10 arriving as
a first touch is the default shape rather than an edge case.

### 38k. STILL OPEN - JSONL cannot be the substrate for 30,000 domains

Measured on a synthetic 30,000-record queue:

| records | file | load | save | transaction |
| --- | --- | --- | --- | --- |
| 500 | 8.4 MB | 0.07s | 0.14s | 0.12s |
| 10,000 | 168 MB | 2.71s | 4.60s | 4.30s |
| **30,000** | **505 MB** | **8.72s** | **14.64s** | **14.09s** |

`store.LOCK_TIMEOUT` is 10 seconds. **A single transaction at 30k exceeds the
lock timeout**, so a second worker gets `QueueLocked` before the first finishes.
Demonstrated with two processes.

Cost is quadratic in batch count, because every batch rewrites the whole file.
The planned shard sizes make it worse rather than better: 250-domain shards are
120 rewrites (852s, 61 GB of I/O); 25-person micro-batches are 1,200 rewrites
(2.4 hours, 606 GB); 10-lead micro-batches are 3,000 rewrites (5.9 hours,
1.5 TB). Memory is 1.5 GB resident at load and 3.0 GB peak at save, because
`save` parses the on-disk file a second time while the first copy is live.

**This is the boundary. A streaming controller built on whole-file JSONL would
be built on sand, and neither a longer lock timeout nor a smaller shard fixes
it - smaller shards are strictly worse.** No streaming controller was written
tonight for this reason; the design is recorded and the substrate has to change
first.

### 38l. STILL OPEN - no global, durable or cross-run credit cap

`enrich.Budget` lives in one process's memory and `cap` defaults to `None`.
`pilotcaps.CEILING` caps companies, contacts and sends - not credits.
`dm_plan.max_batch_credits` is parsed from client config and used only to
compute a display string; `dmplan.may_enrich` has zero callers. Two runs of
`--cap 100` spend 200, and a shard controller invoking `enrich.run(cap=X)` per
shard has an effective ceiling of 120X.

Forecast and enforcement also disagree in eleven named places, of which the
sharpest are: `costsim.DEFAULTS["found_per_company"]` 6.0 against
`enrich.ASSUMED_PROFILES` 5; `decision-makers` charged a flat 10 against
`costsim`'s ~8 per hit company; and the ContactOut **verifier** absent from
`costsim.known_costs` entirely, which is about 42,000 credits at 30k.
`scalesim` correctly calls `enrich.plan`; `costsim` is the reimplementation.

Measured against costsim's own assumptions, a 30,000-domain run is **260,832
credits forecast and 453,000 to 705,000 measured** - 1.7x to 2.7x.

### 38m. STILL OPEN - a provider failure is charged, ledgered, and read as an answer

`enrich.spend()` charges the budget and writes the waterfall ledger BEFORE the
provider call. A `ProviderError` is caught and logged with no refund and no
result marker. So four failed calls become 13 phantom credits and 13 credits of
false ledger - and the domain is dropped on a conclusion drawn from a rate limit.

Worse: `fieldplan.state_of` returns `MISSING_CONFIRMED` whenever `tried()` finds
a ledger row, and `tried()` cannot tell a 500 from an answer. After one all-500
run, `company_info_is_owed` is False and `already_bought` is True **forever**, so
the firmographics that produce the ICP verdict can never be bought for that
company. This is "missing evidence is never positive evidence" violated by
construction.

The right fix is to charge after the call, pass `actual_cost`, and give a failed
row a distinct result - which also closes 38n. Not attempted tonight: it touches
the single paid-call door and deserves its own change with its own validation.

### 38n. STILL OPEN - `actual_cost` has never been written

`waterfall.entry` accepts it and `waterfall.spend()` sums it into `reported`. No
caller in `src/` passes it, so `reported` is structurally `None` on every record
in the estate, and the ledger's ability to compare believed cost against billed
cost has never been exercised. `decision-makers` is charged a flat 10 and never
reconciled against `len(people)`, which is in hand at the call site. Blitz is the
only provider that reports true cost and Blitz has no caller.

### 38o. STILL OPEN - `stepstate`'s state machine has no enforcer

Only the flat predicate `is_terminal` is consumed. `TRANSITIONS`, `allowed`,
`check`, `apply` and `reconcile` have zero callers in `src/`. Thirteen of
fourteen states are never written by anything; the only persisted status any
production path writes is the bare literal `step["status"] = "pushed"`, which
does not go through `apply`, so no transition is ever validated and no history
entry is ever written. A table nothing enforces is worse than none, because it
reads as a guarantee.

### 38p. STILL OPEN - `RUNNING` is reachable by state mutation alone

`campaigns.set_status`'s `allow=` parameter makes any source status legal, and
six call sites pass the target itself. So `rejected -> approved` and
`anything -> running` are permitted, against the comment saying a campaign never
moves backwards into approval. Reachable from the web with the reviewer role:
`completed --pause--> paused --resume--> running`. Meanwhile `orchestrator.launch`
- the function whose docstring calls itself "the last door" - never sets
`RUNNING` at all. So the transition into the state `killswitch` requires for
sending and the provider write are on disjoint code paths, and the only path
into a LIVE canonical state is mutation. Harmless today only because
`providerwrites.SUPPORTED` is empty.

### 38q. STILL OPEN - the complete list of guards with no caller

Each is complete, tested and documented, and none is consulted at the point of
use:

| module or function | what it was written to do |
| --- | --- |
| `src/observations.py` (398 lines, 98 tests) | the licence layer that answers, BEFORE a word is written, what may be stated about a company or person and on what evidence |
| `src/mapping.py` | prove a provider campaign id exists and is OURS - `MISMATCH` means "belongs to something else, refuse loudly" |
| `src/stepstate.py` transitions | the step lifecycle, 14 states |
| `src/outreachclaims.py` on the send path | the authority on claims about US - `SAME_CONTACT_PRIOR_TOUCH` is exactly 38j's defect |
| `src/evidencerepair.py` | reconstruct verification evidence from the event log |
| `src/fieldplan.py` | 8 of 9 public functions; only `company_info_is_owed` is called, governing 1 credit of 13 |
| `src/blitz.py` entirely | two live-confirmed routes, 62 tests, five cost-table entries, three waterfall rungs, and `enrich.py` does not import it |
| `launch.state == "launched"` | read by three consumers, written by none, so the relaunch guard in the launch checklist can never fire |
| `orchestrator.complete` | no caller, so `CAMPAIGN_COMPLETED` is never emitted and no record is ever released from a finished campaign |
| `dmplan.may_enrich` | the per-batch credit ceiling |
| `refresh.py` | a whole staleness-driven re-buy plan |
| `contact["personalization"]` | written only by demo builders, so `eligibility._evidence_aged_out` - the only staleness gate on the send path - can never fire |
| `executionguard`, `providerwrites`, `configdiff` | nothing in `src/` imports them yet; they are reachable only from their own CLIs and tests |

### 38v. STILL OPEN - the provider has a variant model this system does not

Measured against live Productive EmailBison campaign 352 on 2026-09-12: 44
sequence-step rows, of which **five are the sequence** (`variant: false`,
`order` 1-5) and **thirty-nine are A/B variants** of those five (`variant:
true`, `variant_from_step` naming a base step's id, `order: null`). Campaign
418 is the same shape at 4 base steps and 6 variants.

`provider_bison` did `int(s.get("order") or 0)`, turning every variant's null
into 0, so it sorted all thirty-nine ahead of the sequence and reported
`actions` as thirty-nine indistinguishable `step0`s followed by step1-step5.
That is not a mismatch with the approved side - it is a fiction about the
provider, and it is the real reason `compare_bison` can never reach PASS,
underneath the `day1` versus `step1` naming that is usually blamed.

Now fixed to the extent it can be without guessing: the base sequence is
compared, the variants are counted per base step and reported under
`_variants_per_step`, which `diff` does not score.

WHAT IS STILL OPEN is the model. COPY-EXPERIMENTS.md describes five variants
per message step as a Resonate concept, assigned by this system and evaluated
by it. EmailBison implements its own variants natively, and the two have
never been reconciled: nothing in canonical state represents a provider-side
variant, so the diff has nothing to compare `_variants_per_step` against and
scoring it would be inventing a verdict. Deciding whether a Resonate variant
IS an EmailBison variant row, or whether this system should own all variation
and stage a single step, is a product decision.

Two further facts from the same read, both of which bear on it:

The provider holds TEMPLATED copy, not rendered copy. `email_subject` on 352
step 1 is `{me again, {FIRST_NAME}|following up from LinkedIn|trying email
this time}` - spintax plus merge fields - and `email_body` carries Liquid
(`{% assign %}`) as well. `approved_bison` builds rendered per-contact
subjects and bodies, so those two fields compare a rendered string against a
template and can never match. Whatever claim checking `lint` and `claims` do
on rendered copy is also checking something the provider never sees, because
the provider personalises at send time.

`provider_bison` refuses a campaign with more than 200 pages of leads, and
campaign 352 exceeds it. So for a real client campaign at scale the lead-set
half of the readback is structurally unavailable, and `lead_set` - which was
just made REQUIRED for email - will refuse rather than verify. That refusal is
correct behaviour and an unusable readback all the same.

### 38u. STILL OPEN - an `Authorization` proves shape, not provenance

`src/executionguard.py` said, in its own module docstring, that an
`Authorization` "cannot be constructed except by passing every gate" and "has
no public constructor path that skips them". `Authorization.__init__(**fields)`
is public and ungated, so that was false. Any caller in this repository can
build one with `gates=()`; `providerwrites.perform` accepts it on an
`isinstance` check, and from there only `revalidate` runs - eligibility and the
killswitch. Skipped: tenancy, campaign approval (so a swapped sender, list or
limit is invisible), the readback, person and account collision, fatigue, pilot
caps, stoppability, and the sender roster and health.

The compensating control is the ledger. `perform` requires the key to be in
`ATTEMPTED`, which takes a real `reserve` - which is also exactly what a
crashed attempt leaves behind, so it is a narrow one.

Not reachable from a prospect-facing write today: `providerwrites.SUPPORTED`
is empty and `killswitch.global_state()` reports sending off, so `authorize`
dies at the killswitch gate and `revalidate` refuses. It arms the day either
changes.

The fix is the one this repository already uses for
`store.save(allow_history_loss=...)`: an issuing token that only `authorize()`
holds, plus a test-only escape hatch that `tests/test_invariants.py` forbids
any `src/` module from reaching for. Eleven test sites construct an
`Authorization` directly, several of them deliberately forging one to prove
the write layer refuses it, so they move onto that hatch rather than losing
the ability to forge.

The docstring now says what is true instead. A false claim on a safety path is
worse than a named gap, because it is the reason nobody looks.

### 38s. FIXED - a batch erased what arrived while it was running

`run.run` loaded the whole queue once, walked 500 records across minutes of
provider I/O, and wrote that opening snapshot back at every `CHECKPOINT_EVERY`
records and again at the end. Reproduced 2026-09-12 in an isolated estate,
two processes, nothing crashing and no race to lose:

  * a record ingested mid-batch - carrying paid verification evidence, an
    unsubscribed contact and a reply event - was gone after the next
    checkpoint;
  * `store.drop(rid, "competitor - do not contact")` applied mid-batch came
    back as `state: queued` with `drop_reason: None`. **A do-not-contact
    record returned to the queue**;
  * three decision-makers bought mid-batch were erased.

Neither guard objected: `refuse_history_loss` and `refuse_evidence_loss` both
skip a record ABSENT from the new set, and the evidence index covers
verification answers, so a person-level purchase not yet verified was
unprotected.

The same shape on `campaigns.jsonl`, which has no history guard at all:
`interactions.decide` loads the file, runs `orchestrator.decide` and writes
its snapshot back, so a `freeze` written in between - the stop button
`eligibility` reads to block every step of a campaign - was lifted by a caller
that never knew it existed.

And `run.checkpoint()` was called from the stage loop with no handler, so any
refusal - `QueueLocked` after ten seconds of contention, `HistoryLost` from a
reply that landed - aborted the whole run and discarded every record's work,
including records that came before the refusal. Measured: a reply persisted
one second into a twelve-record batch left zero records enriched while the
durable spend ledger kept every charge.

`store.Snapshot` now carries what each row was when it was read, and the
write-back is a three-way merge: a row this caller never touched keeps
whatever is on disk, a row only this caller touched is written, and a row both
touched is merged field by field with the caller winning only the fields it
actually changed. A plain list still replaces the file, so a caller that built
its rows elsewhere is unaffected. The checkpoint catches those two refusals,
notes them in the report and lets the next one retry.

### 38t. STILL OPEN - one human in two records is two prospect-facing actions

`push.push_id` is `rec:contact:step:channel` and `actionledger.reserve` refuses
a repeat of a KEY, so the same person reachable through two queue records - the
account uploaded twice under two domains, or a parent and a subsidiary - is two
reservations and two touches. `collision` catches this by READING THE PROVIDER,
which is exactly what is unavailable in the timeout and crash cases this ledger
exists for. The ledger already computes the answer and does not consult it:
`contacts_reached` returns the contact after the first send.

What `reserve` needs is a canonical person identity rather than the
within-record contact key - `agencydnc.keys_for` and `identity.contact_key`
already derive one from the email and the LinkedIn URL - because a name slug
alone would make two different people called Dana Example block each other.
Asserted as an `expectedFailure` in
`tests/test_a_batch_does_not_erase_what_arrived_during_it.py`, so the day it is
closed the test announces itself.

### 38r. STILL OPEN - smaller, named

`claims.is_claim` still examines a sentence only when it carries a number, a
month or an event word, and additionally skips any sentence with no second-person
marker - so a fabricated claim phrased in the third person about the company by
name escapes entirely. Measured hole: 32 of 40 unsupported assertions ship.

`aiark._rows`, `apify.dataset_items` and (until tonight) `mapping.bison_campaigns`
return `[]` on a body of the wrong shape, where `providers.mapping` raises. Each
is on a decision path.

No retry, backoff or 429 handling exists in `providers.request`. The only retry
in the build, `poller.with_retry`, retries any `ProviderError` - including a 429
- three times on a fixed backoff with no `Retry-After` read.

`verification.verify(rec=None)` spends real credits and writes no ledger row.
One production caller passes a rec, so it is latent.

`validate.py` calls six paid providers through its own cost table with its own
`--max-credits` guard and writes no waterfall row at all - a real, bounded,
unledgered spend door.

A HeyReach lead-add is **unverifiable even in principle**: no confirmed route
reads a lead back by campaign, so `providerwrites`' mandatory read-back cannot be
satisfied for that operation. Establishing a read-back route is a prerequisite
to, not a part of, enabling it.

HeyReach exposes `organizationUnitId` on real campaign payloads and the only
consumer is `configdiff`. Nothing asserts it, so no HeyReach read can prove which
org unit answered - the hole EmailBison closed with `require_workspace` after its
credential answered for four estates in three days.



## 39. Why the 50-domain pilot produced zero campaign-ready, measured

Decision 3 of the HOLD_FOR_FIXES continuation asked for the quantitative
reason and a classification per hold. Read from the stored verdicts on
2026-09-10, not reasoned about.

**Every one of the 50 has `icp_confidence: low`, and that is the binding
constraint** - `_verdict` forces `review` for any LOW-confidence company
whatever it scored, so no record could become qualified regardless of fit.
Which branch of `_confidence` produced LOW, for each record:

| Records | Cause | Classification |
|---|---|---|
| 34 | `segment.vertical == UNKNOWN`, which returns LOW before anything else is considered | MISSING DATA |
| 14 | vertical known, but only 3-5 of 12 dimensions scored; `len(missing) >= 6` needs `scored >= 6` for MEDIUM | MISSING DATA |
| 2 | contradictory evidence demoted the band | EXPECTED - a human should see these |

Independently of confidence, **19 of 50 were rejected on headcount**: 23 of
the cohort are in the `1_9` band and the ICP charges -25 for "below the 10
needed to feel this problem". That is an **EXPECTED BUSINESS FILTER** and it
is correct. Productive sells utilisation tracking to Design Services teams;
a four-person shop does not have the problem the product solves. A cohort
of 50 domains drawn from an agency list is mostly very small agencies, and
a pipeline that qualified them would be the broken one.

So the headline number is not one failure. It is a correct business filter
removing roughly half the cohort, and missing data preventing a verdict on
the rest.

### The part that IS a defect: research cannot lift confidence

One record of the 50 got as far as research. It gained
nothing from it, for three separate reasons, and the first two are bugs:

1. **`confidence_components` reads fields the Apify path never writes.** It
   scores `source_quality` from `item["quality"]` and `recency` from
   `item["freshness_score"]`. The stored items do not have those keys at
   all - not null, absent - so both components scored 0.0 with the reason
   "0 usable piece(s) of evidence" and "nothing dated to judge recency by",
   about five pieces of evidence that were successfully retrieved.
   `evidence.make` populates both. `apify.evidence_from_items`
   (src/providers/apify.py:348) does not call it: it hand-builds a nine-key
   dict - `source_type, provider, source_url, actor, retrieved_at, field,
   title, fact` - and so emits no `quality`, no `freshness_score`, no
   `published_at`, no `relevance_score` and no `evidence_id`. Two producers
   of the same record shape, one of which the consumer was written against.

   This is the defect class named at the top of CLAUDE.md, in mirror image:
   not a field computed correctly that nothing reads, but a consumer reading
   a field nothing produces. Both look like a working system.

2. **`source_diversity` can never exceed 0 on the only research path this
   build has.** It counts `{provider} | {source_type}` distinctly, and the
   Apify path sets both to `"apify"`, so `distinct == 1` and the score is
   0.0 by construction. One provider not corroborating itself is correct;
   the consequence is that diversity is dead weight until a second research
   provider exists.

3. **The scraped content did not answer what the dimensions ask.** The five
   facts retrieved were the site's cookie policy, its privacy policy and
   its navigation menu. That is a **PROVIDER LIMITATION**, not a bug: a
   homepage scrape does not establish a delivery model or a utilisation
   problem, and no amount of scoring fixes evidence that is page furniture.

**Fixing 1 and 2 would not have changed this pilot's outcome**, and saying
otherwise would be the convenient reading. Only one of fifty records
reached research at all - the other 49 were held before it, by design,
because company-first means no research spend without an ICP verdict - and
that one record's evidence was boilerplate. The bugs are real and must be
fixed on their own merits. They are not the reason the pilot returned zero.

### What this does not license

Nothing here justifies lowering the headcount floor, widening the vertical
classifier's signal requirement, or letting LOW confidence qualify. The
cohort genuinely is mostly too small, and a verdict on absent evidence is
what `unknown` is for. The fix for 34 records that cannot be classified is
better company-level evidence before the verdict, not a verdict that needs
less evidence.


## 40. What the 50-domain pilot actually cost, per bucket, measured

Decision 2 required that a cost claim name its own evidence class, after I
claimed "zero credits spent" from ContactOut's `count` alone - which was not
sufficient evidence, because ContactOut meters three buckets independently
and `count` is only the email one.

### MEASURED_PROVIDER_ACTUAL - ContactOut

Read from `GET /stats` before and after, all three buckets:

| Bucket | Before | After | Delta | Quota |
|---|---|---|---|---|
| `count` (email) | 566 | 566 | **0** | 39,215 |
| `search_count` | 77 | 77 | **0** | 119,127 |
| `phone_count` | 462 | 462 | **0** | 4,370 |

Zero on every metered bucket, which agrees with the run's own invariants:
no person-level call, no verifier call, no contact enriched. This is a
measured actual, and it is the claim the earlier one should have been.

### UNKNOWN - Apify

Apify bills compute units, not credits, and `COSTS["apify-research"]` is 0,
which is why `--cap` could not bound it. Month-to-date usage reads
**$4.03** (`/users/me/usage/monthly`, `totalUsageCreditsUsdBeforeVolume-
Discount`, 2026-09-10).

**That is a month-to-date total, not this pilot's cost.** No pre-run Apify
snapshot was taken, so the delta attributable to the 50-domain run is
UNKNOWN and must not be reported as anything else. One actor run is known
to have happened during it; its share of the $4.03 is not established.

This reading is recorded here as the baseline for the next run, which is
what makes the next reconciliation possible.

### FREE_CONFIRMED

DNS/MX resolution is not a metered provider. The run-scoped MX cache change
is a latency fix, not a cost one, and was never claimed otherwise.

### The reconciliation gap this leaves

A cost reconciliation needs PRE-RUN SNAPSHOT -> RUN -> POST-RUN SNAPSHOT
per provider, and only ContactOut had a pre-run snapshot. Until the snapshot
is taken automatically at the start of a run and written to the ledger, every
Apify figure will be UNKNOWN by construction - which is honest but useless,
and the honesty is not a substitute for the measurement.


## 41. A reply nobody can match to a contact stops nothing at all

The authoritative rule is that a reply on either channel stops future cadence
for the same lead on BOTH channels. Traced end to end on 2026-09-10, that rule
holds: `accountpolicy.apply_reply` is the single writer of `contact["paused"]`,
`rec["paused"]` and `rec["review"]`; `eligibility._replied` and
`eligibility._paused` read it with NO channel filter; and both `push.py` and
`executionguard.authorize` sit on the only path to a provider write.
`tests/test_lifecycle_attacks.py` proves it in both directions.

**The gap is upstream of all of that: attribution.**

`events.match_record` is exact and fails closed - record id, then lowercased
email, then canonical LinkedIn URL, with `None` on any ambiguity. When it
returns `None`, `events.apply` reports `unmatched` and **writes nothing**.
`inbound.handle` then fires a Slack notification that is explicitly
best-effort and cannot raise, and returns.

So a reply this system cannot attribute produces a Slack message that is
permitted to fail silently, and outreach continues on both channels for
everyone at that account. Fail-closed for ATTRIBUTION; fail-open for STOPPING.
The cases are ordinary rather than exotic: a reply from a personal address, a
forwarded reply, a shared inbox not listed against any contact, an address two
clients' records both carry.

There is no durable queue, retry or blocking state for unmatched inbound. I
looked for one.

### What would close it, and why it is not done yet

The honest fix is not "match harder" - guessing an identity is worse than
admitting there is none. It is to make an unmatched reply hold the ACCOUNT it
plausibly came from: if the sender's email domain matches a record's domain,
somebody at that company replied, even if we cannot say who, and the
account-level HOLD semantics already exist for exactly that shape of fact.

That is a behaviour change with a real cost - it can hold an account on a
bounce from a shared domain, or on an out-of-office from an unrelated person -
so it wants its own design pass and its own attack tests rather than being
bolted on beside a cost fix. It is the highest-value item left on the reply
path.

### Two smaller findings on the same path

**FIXED 2026-09-10.** `events.match_contact` refused ambiguity for the
LinkedIn identifier and not for the email one, so two contacts sharing an
`info@` address meant a reply was attributed to whichever was listed first.
Now both identifiers collect candidates and any ambiguity returns `None`.

**OPEN, low.** `cadence.status_for` stamps the timeline's `step["status"]`
from the RECORD-level pause only. It never reads `contact["paused"]`,
`contact["stopped"]` or `contact["unsubscribed"]`, so a planning view can
label a replied contact's step `eligible`. Nothing ships - `push.
verify_before_payload` and the execution guard both re-check - but the plan a
human reads is wrong until the last gate, which is the kind of disagreement
that erodes trust in the screen.

**OPEN, unreached.** `adapters` trusts a HeyReach webhook payload's
`eventType` without calling `heyreach.direction()`, so our own outbound would
be readable as a prospect reply. The poller only produces conversation-shaped
pages and unsigned webhooks are deliberately not trusted as a transport, so
the path is unreached today - but it is the one place on the inbound path
where the direction allowlist is not applied.


## 42. Two ICP dimensions cannot be scored from a company's own website

**This section said five, and was wrong.** It was measured while the second
research pass was still running - eleven records researched, and the qualify
stage had not re-scored most of them. Generalising from that to "the ICP model
asks the wrong witness" was an overreach from partial data, and the corrected
numbers say something narrower and more useful.

Measured over the 50-domain Productive cohort on 2026-09-10, after research
had run for 15 records and every verdict had been recomputed:

| dimension | scored | before research ran |
|---|---|---|
| employee_count | 40/50 | 40 |
| agency_fit | 20/50 | 18 |
| service_not_product | 20/50 | 18 |
| geography | 17/50 | 17 |
| distributed_teams | 13/50 | 13 |
| delivery_complexity | 6/50 | 1 |
| project_delivery | 4/50 | 2 |
| resource_planning_need | 2/50 | **0** |
| profitability_need | 1/50 | **0** |
| operational_complexity | 1/50 | **0** |
| **utilization_need** | **0/50** | 0 |
| **time_tracking_need** | **0/50** | 0 |

Research works. Four of the six prose-driven dimensions started scoring the
moment it actually ran, and the per-record maximum went from 6 to 8 - enough
for HIGH confidence, which this file previously called unreachable and which
`digitalthirdcoast.com` now holds at 8 dimensions and a score of 73.

### The two that remain, and why they are different

    utilization_need     0/15 researched   "utilisation", "billable", "bench"
    time_tracking_need   0/15 researched   "timesheets", "logged hours"

These are the two dimensions that name the operational pain directly, and a
company's own marketing website does not advertise the problem a vendor wants
to sell it. It advertises services and clients. No agency writes "our
utilisation is a mess" on its homepage. The matcher is fine - over 13,200
words it finds "account manager", "studio", "retainer", "bookings" - it finds
nothing of these because there is nothing of these to find.

So the honest statement is not that the ICP model is unscoreable. It is that
**ten of twelve dimensions are scoreable from firmographics plus the company's
own words, and two are not scoreable from that source at all.** Their cost is
bounded: they count as `missing`, which nudges every company toward LOW, and
`_confidence` needs 6 of 12 for MEDIUM. Companies still reach MEDIUM and HIGH.

### What would close the last two, and what must not

**Not** lowering the threshold, and **not** widening the phrase lists until
something matches. Both manufacture confidence the evidence does not support.

  - **Job postings** are the strongest available signal and the cheapest. An
    agency hiring a Resource Manager, a Traffic Manager or a Studio Manager
    states the resourcing problem in public with a date on it. Nothing in this
    build reads them.
  - **Headcount trajectory** is a better proxy for resourcing pressure than any
    phrase: a studio that went from 20 to 45 people in a year has a scheduling
    problem whether or not it says so.
  - **Tech stack, but not the stack we currently get.** `company_facts.stack`
    is populated for 14 of the 50 and read by no ICP dimension at all - not one
    occurrence of "stack" in `icp.py` or `segments.py`. That IS a real
    disconnection, and it is worth less than it looks: the field holds WEB
    infrastructure - Google Analytics, Cloudflare, Yoast, Typekit - not
    business systems, so it cannot say whether a company runs Harvest or Float.

### The lesson underneath the correction

Both drafts of this section were written from real measurements. The first was
taken while the thing being measured was still changing, which is a way of
being precisely wrong. A number from a run that has not finished is not a
finding; it is a progress bar.

## 43. Two more places where one person's identifier lands on another

The referral promotion weld is fixed and regression-tested (§31 of the
current mission: every real finding gets a regression test). Looking for the
same SHAPE elsewhere - an identifier for person A written onto the record of
person B - found two more. Both were found by reading. The first was then
reproduced and fixed; the second is latent and is recorded rather than fixed.

### A shared name merged two people - FIXED 2026-09-11

`enrich.markers()` returns every handle a contact is known by - email,
LinkedIn **and name** - and `merge_contacts` indexes contacts by all three.
So a provider payload naming somebody with the same full name as an existing
contact is treated as that contact, and `FILLABLE = ("title", "linkedin",
"name")` then fills in the blanks.

The damaging case is an existing contact who has an address but no profile.
The incoming person shares the name, carries a different address and a
profile of their own. The address is correctly refused - the field is
already set - but the PROFILE is written, because that field is empty. The
contact now holds one person's mailbox and another person's LinkedIn, which
is exactly the referral bug in a different module, reached without anybody
replying to anything.

Two aggravating details:

  - `markers()` returns a SET, so which marker matches first is not defined.
    The same payload can merge on the name in one run and the address in the
    next, so the bug is not reliably reproducible from the input alone.
  - `referral.py` already states the rule this breaks, in its own module
    docstring: "An address or a canonical profile URL is identity. A name is
    not - two people share one and one person has three." Two modules, one
    question, two answers.

### What it actually did, reproduced

The damaging shape is not the one above. Both `merge_contacts` call sites run
only when `usable_contacts(rec)` is empty - no contact here has an address -
so the contact being merged into is somebody known by name and profile, and
it is the ADDRESS that gets welded on:

    on the record   Jan Novak, /in/jan-novak, no address
    provider says   Jan Novak, j.novak2@acme.test, /in/jan-novak-studio

    after merge     /in/jan-novak  +  j.novak2@acme.test
                    added: []   excluded: []

`usable_contacts` then returns that row, so verification buys a check on the
second person's address and a valid answer marks it sendable: the email goes
to one human and the connection request to another. The second person is not
added, not excluded, and no reason is recorded - a real decision maker
deleted with no trace. A contact added from a referral arrives as exactly
this shape, so the two paths chain.

### The fix, and what it deliberately still allows

Not dropping the name: the name index exists because a person known only by
name who later arrives with an address was being minted twice, and re-minting
destroys paid verification evidence. Three changes instead:

  - Two indexes rather than one, consulted in a stated order - address, then
    profile, then name. The old single index was iterated as a SET, so the
    winner was undefined and the same payload could merge on the name in one
    run and the address in the next.
  - A name-only match yields when the two records hold DIFFERENT values for a
    handle they both carry. It still stands when one side carries no strong
    handle at all: that is the case the name index exists for, and the guard
    removes matches contradicted by evidence, not matches with no evidence
    either way.
  - Handles are normalised before comparison, via `dedupe.normalise_email`
    and `linkedin.canonical`. This is not tidiness. Every one of the 25
    profiles in the estate is stored as a bare vanity slug and every provider
    returns a full URL, so a raw comparison would read one person as two and
    mint the duplicate that discards their verification. A mutation sweep
    caught that the first version of the tests never asserted it.

Not seen in live data: the 300-record estate has zero records with two
contacts sharing a name, which bounds the exposure and is not a reason it
could not happen. `tests/test_a_name_is_not_an_identity.py` holds the
reproduction; seven mutations, all caught.

### One thing left alone, upstream of the merge

`same_company` compares the incoming email's domain to the record's raw, so
`someone@acme.test.` - a valid FQDN form that `dedupe.normalise_email` treats
as the same mailbox - is excluded as a "company name collision". Excluding a
real person is the safe direction and this is not the weld, so it is recorded
here rather than changed in a diff about identity.

### A company name is an identity in one branch, and that is deliberate

Looked for the account-level version of the same question - can a fact or a
person belonging to company B land on company A - and `enrich.same_company`
is where it lives. Its first line says "Domain is the identity" and its
second branch then accepts a person carrying no address on a lowercase
company-NAME match, which is the trap the first line names.

Audited rather than assumed. Across all 300 records: 25 contacts, every one
on-domain, none admitted by the name branch, and the guard has excluded 40
people as "company name collision: not this domain". It works, and it has
never needed the weak branch.

NOT TIGHTENED, and the reason matters more than the finding. Both callers
search BY DOMAIN - `decision_makers(rec["domain"])` and
`people_search(companyDomain=...)` - so the payload is already scoped before
this function sees it, and the name branch is a second opinion on that
scoping rather than the only thing between two firms with one name. Removing
it would reject every profile-only person a domain-scoped search returns,
which is the population the LinkedIn lane runs on. Per the current mission's
rule on benchmark cheating, a rule change needs evidence that the rule was
wrong, and tightening for yield reasons is the same offence in the other
direction.

What changed is the claim, not the behaviour: the docstring now says which
branch decides and states the caller contract - a name match is licensed by
the caller's domain scoping, so a caller that searches any other way must
add its own domain check. Two tests pin both branches so the next reader
learns it from the tests rather than from an incident.

### A legacy `/pub/` URL collapsed distinct members - FIXED 2026-09-11

`linkedin.canonical()` accepts `/in/` and `/pub/` and keeps only the first
path segment. A legacy public URL is `/pub/jan-novak/1a/2b3/4c5`, where the
trailing triplet is what distinguishes two members who share a vanity
segment - so two different people both canonicalise to
`https://www.linkedin.com/in/jan-novak`, which may belong to a third.

That module is explicit that this is the expensive direction: "A near-miss
is an unmatched event, which is safe; a wrong match pauses somebody else's
campaign." Dropping the identifying segments turns near-misses into wrong
matches.

LATENT when found: `work/queue.jsonl` holds zero `/pub/` URLs, and the only
existing test of that prefix used a bare `/pub/jan-novak` with no trailing
segments. Fixed anyway, because identity is the wrong place to keep a
known-false equivalence, not because it had fired.

A `/pub/` URL carrying those segments now keeps them and is its own
identity; a bare `/pub/vanity` has nothing to disambiguate and keeps its
existing reading as the `/in/` form. Refusing the URL outright was the other
option and would have lost a real profile for no gain - unmatched is safe,
but so is matched-correctly. `key()` moved with it: it returned the text
after the last slash, which for a legacy URL is the final segment alone, so
two members one character apart shared a lookup key. Five mutations, all
caught, including one that kept only the first of the three segments - two
members can share the leading pair.
