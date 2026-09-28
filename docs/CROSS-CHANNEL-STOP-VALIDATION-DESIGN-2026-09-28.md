# CROSS-CHANNEL STOP — LIVE VALIDATION DESIGN — 2026-09-28

**Operator decision 14, Zvonimir, 2026-09-28.** Launch blocker 4: *"Cross-channel
stop unproven at the provider — readback required, never inferred from logs or
mocks. Needs separate operator authorisation."*

**This is a DESIGN. Nothing in it was executed.** From this task:
**provider writes 0. provider reads 0 — the credentials are not set in this
environment, so provider state is UNKNOWN and is reported that way rather than
as clean.** No Slack post. No merge to master. No edit to `src/`.

**State of the capability, and it is said this way and no other way:**
**cross-channel stop is IMPLEMENTED / NEVER LIVE_VALIDATED, in BOTH
directions.** Two documents on master claim otherwise
(`docs/DECISIONS-2026-09-25-OPTION-A-AND-THE-FREE-CRAWL.md` §6, "the LinkedIn
halt is lifted", and `docs/STOP-MEASUREMENT-READY-2026-09-25.md` §5). §0.3
below shows why the operator's classification is the correct one and those two
are not, using the timestamps in those same documents.

## 0. DERIVE EVERY STATE CLAIM, AND THE LEDGER FOR THE ONES BELOW

    git fetch origin && git rev-parse master origin/master
    py -3 -c "from src import killswitch as k; print(k.workspace_state('productive'))"
    py -3 scripts/probe_cross_channel_stop.py --queue <production work/queue.jsonl>

Every claim in this document carries CLAIM / AUTHORITY / MEASURED AT / STATE.
A claim without an authority is not in here.

### 0.1 The ledger

    CLAIM        origin/master is 4b1fb0c6bfc7dac2a00a1b91b4fd5f867d30f606
    AUTHORITY    git rev-parse origin/master, this worktree
    MEASURED AT  2026-09-28, this session
    STATE        VERIFIED

    CLAIM        sending.live is off for `productive`
    AUTHORITY    killswitch.workspace_state('productive') run from the
                 PRODUCTION checkout -> {'sending': False,
                 'why': 'sending.live is off for productive'}
    MEASURED AT  2026-09-28, this session
    STATE        VERIFIED

    CLAIM        the same call run from a WORKTREE cannot read that authority
    AUTHORITY    killswitch.workspace_state('productive') in this worktree ->
                 {'sending': False, 'why': 'no such workspace: productive'}
    MEASURED AT  2026-09-28, this session
    STATE        VERIFIED — and it is a trap. The worktree has its own empty
                 `work/`, so the answer is a FAIL-CLOSED DEFAULT that prints
                 the same `sending: False` as the real one. Read the freeze
                 from the production checkout or the state is UNKNOWN.

    CLAIM        exactly ONE contact in the production queue is bound on both
                 providers, and it is the operator's own test identity
    AUTHORITY    scripts/probe_cross_channel_stop.py against the production
                 work/queue.jsonl — 1582 records, 1065 contacts:
                 BOTH 1 · email-only 804 · linkedin-only 0 · unbound 260
    MEASURED AT  2026-09-28, this session
    STATE        VERIFIED

    CLAIM        no prospect can be reached by a cross-channel stop today
    AUTHORITY    the same probe: the one both-bound contact is the record in
                 `testidentity.RECORD_IDS`, and 0 campaign rows carry both a
                 bison_campaign_id and a heyreach_campaign_id
    MEASURED AT  2026-09-28, this session
    STATE        VERIFIED

    CLAIM        both stop verbs are ENABLED in the write layer
    AUTHORITY    runtime read of providerwrites: EMAIL_STOP_LEAD
                 ('bison.stop_lead') in SUPPORTED True; LINKEDIN_STOP_LEAD
                 ('heyreach.stop_lead') in SUPPORTED True; both in REPEATABLE
    MEASURED AT  2026-09-28, this session
    STATE        VERIFIED

    CLAIM        no killswitch gates either stop
    AUTHORITY    `providerwrites` does not import `killswitch`; both stops are
                 declared `prospect_facing=False` by `describe()`, so the
                 `executionguard` branch — the only place
                 `killswitch.workspace_state` is consulted — never runs
    MEASURED AT  2026-09-28, this session
    STATE        VERIFIED

    CLAIM        the process that would execute a live stop holds code from
                 2026-09-25 and is stale on three modules of the stop's own path
    AUTHORITY    `scripts/reply_watch_loop.py --interval 300` PID 60108,
                 CreationDate 2026-09-25T12:36:34Z, against file mtimes in the
                 production checkout
    MEASURED AT  2026-09-28, this session
    STATE        VERIFIED — see §1.4 for the table

    CLAIM        the supervisor that is supposed to run that loop cannot start
    AUTHORITY    bytecode of `supervisor._run`: `LOAD_FAST_CHECK 3 (monitors)`
                 — `monitors = table if table is not None else monitors()`
                 makes `monitors` a local, so the `else` branch reads an
                 unbound local. Both production callers pass no table:
                 `scripts/supervise.py:35`, `scripts/cold_start.py:336`
    MEASURED AT  2026-09-28, this session
    STATE        VERIFIED

    CLAIM        current provider state of every object this design names
    AUTHORITY    none available — BISON_KEY and HEYREACH_KEY are unset in this
                 environment (checked against `config.VARIABLES`, never guessed)
    MEASURED AT  2026-09-28, this session
    STATE        UNKNOWN. Not clean, not zero, not ready. §3 makes reading it
                 the first gate of the run rather than an assumption.

### 0.2 The ladder

    DIRECTION                    ABSENT IMPL UNIT INTEG LIVE PROD
    LinkedIn reply -> email stop         yes  yes  part   no   no
    email reply -> LinkedIn stop         yes  yes  part   no   no

`IMPLEMENTED` — the chain exists and has a production entrypoint (§1).
`UNIT_TESTED` — `tests/test_a_reply_stops_the_other_channel.py`, ~1,200 lines,
both directions, duplicate webhooks, races, suppression propagation, audit
logging, and a class named `TheReadbackCannotLie` that asserts a constant
readback would pass while the real one does not. This is a good suite. It is
still not evidence about the provider (§2).
`INTEGRATION_TESTED — part` — the WRITE SCOPE is integration-tested at the
transport against real URL shapes
(`tests/test_the_reply_path_may_stop_and_nothing_else.py`, asserting
`inbound.STOP_ROUTES` permits `stop-future-emails` and `stopleadincampaign`
and refuses everything else). The PROVIDER STOP is not: every test mocks
`src.leadstop.bison` / `src.leadstop.heyreach`, i.e. at or above the adapter.
`LIVE_VALIDATED` — no. §0.3.

### 0.3 Why the two 09-25 documents are not a live validation, from their own timestamps

`docs/DECISIONS-2026-09-25-OPTION-A-AND-THE-FREE-CRAWL.md` §6 reports
LinkedIn->email at 7.7 minutes (2026-09-23) and email->LinkedIn at 4m02s
(2026-09-25), and lifts the LinkedIn halt on that basis. The same section says,
four paragraphs later:

> **And the audit was lying in both directions until 12:35Z.** The email
> read-back was `lambda: {"stopped": True}` against `expected={"stopped": True}`
> — a constant identical to the expectation, so it recorded ACCEPTED whatever
> the provider did. The LinkedIn read-back returned the raw campaigns LIST
> against a dict, so it recorded DRIFTED even when the stop worked.

The email->LinkedIn measurement it reports happened at **12:24:10Z and
12:24:11Z** — eleven minutes BEFORE the readbacks were fixed. The
LinkedIn->email measurement was two days earlier, on the same broken email
readback. So **neither figure was produced by a write layer that asked the
provider anything.** What survives in each case is a single independent status
read quoted in prose — `membership(491,[204967])` reading `stopped` on 09-23,
`621824 Pending -> Paused` on 09-25 — each against one lead, the operator's
own, with no negative control, no sibling, no pre-state assertion recorded as
evidence, and no named SHA.

That is why `IMPLEMENTED / NEVER LIVE_VALIDATED` is the accurate rung and the
halt-lift text is not. It is also the whole reason this design exists:
**a measurement taken by an audit that cannot fail is not a measurement.**

---

## 1. WHAT IS ACTUALLY IMPLEMENTED TODAY

Traced through the real consumer chain, per the repo's own rule: a module, a
passing unit test or `A imports B` is not wiring; zero production callers is
DISCONNECTED.

### 1.1 The chain, both directions, and it is ONE chain

Both directions converge on the same funnel and differ only in which provider
feed enters it and which provider is written to.

    INPUT          provider reply feed
                   email     GET  /replies                bison.fetch_replies
                   linkedin  POST /inbox/GetConversationsV2
                                                          heyreach.conversations
    NORMALISE      adapters.from_emailbison / from_heyreach   src/adapters.py
    CANONICAL      events.apply -> the record's own event log  src/events.py
    DECISION       inbound.handle                          src/inbound.py:365
                   - the stop is attempted BEFORE classification, deliberately:
                     a stop can only ever mean somebody receives less
    CONSUMER       inbound._stop_at_provider                src/inbound.py:186
                   - per channel, and "not attempted" is an outcome
                   - opens providers.allow_writes(only=STOP_ROUTES)
                     src/inbound.py:310
    EXECUTION      leadstop.stop_contact          (email)    src/leadstop.py:39
                   leadstop.stop_linkedin_contact (linkedin) src/leadstop.py:137
                   -> providerwrites.perform(EMAIL_STOP_LEAD / LINKEDIN_STOP_LEAD)
                   -> bison.stop_lead      POST /campaigns/{id}/leads/stop-future-emails
                      heyreach.stop_lead_in_campaign
                                            POST /campaign/StopLeadInCampaign
    CONFIRMED      email     bison.membership -> lead_campaign_data status in
                             STOPPED_STATES = ("stopped","replied","bounced",
                             "sequence_finished","unsubscribed")
                   linkedin  heyreach.campaigns_for_lead -> leadStatus NOT in
                             RUNNING_LEAD_STATUSES = ("Pending","InSequence",
                             "PendingOrExcludedToBeCalculated")
    REPORTING      events.PROVIDER_STOP_CONFIRMED on the record
                   inbound.summarise_stops -> the watcher's line + refusals
                   work/action-ledger.jsonl

### 1.2 PRODUCTION ENTRYPOINT

**The only programmatic caller of the funnel is `poller.run` -> `inbound.ingest`
(`src/poller.py:471`).** Everything else that reaches `inbound` is a manual CLI
(`python -m src.inbound apply`, `src/replaysim.py`) or a reporting call.
**No web route calls `inbound` at all** — `scripts/server/webhook_receiver.py`
is record-only by design.

`poller.run` has three possible drivers:

    1. src/web/app.py:2153   replywatch.start(after=after), inside the process
                             the Procfile and railway.json declare. Polls only
                             if REPLY_POLL_ENABLED is truthy in that process's
                             environment. That variable is set to a truthy
                             value in NO tracked file — config/.env.example
                             ships it empty, hosts/production.env.example omits
                             it. Whether it is set in the Railway dashboard is
                             UNKNOWN from this repository.
    2. scripts/reply_watch_loop.py  a real `while True:` loop that sets the
                             flag itself. Registered as the first entry of
                             supervisor.STATIC_MONITORS. THE SUPERVISOR CANNOT
                             START IT — §1.4.
    3. manual CLIs           python -m src.replywatch --once
                             python -m src.poller emailbison --live

**So the cross-channel stop is not DISCONNECTED — it has a real production
entrypoint and a real chain — but on this machine it is live only because a
human started driver 2 by hand on 2026-09-25 and it has not died since.** PID
60108 is that process.

### 1.3 The population the mechanism can act on: ONE, and it is the operator

Measured, not inferred (`scripts/probe_cross_channel_stop.py`, production queue):

    records                            1,582
    contacts                           1,065
    BOUND ON BOTH PROVIDERS                1   <- the entire population
    email binding only                   804
    linkedin binding only                  0
    no provider binding                  260
    campaign rows                         67   bison 20 · heyreach 40
    campaign rows carrying BOTH ids        0
    records in an email row              697
    records in a linkedin row              5
    records in BOTH                        1

The one is the record in `testidentity.RECORD_IDS`, client `productive`,
carrying `bison_lead_id` 205079, a `heyreach_lead_id` and a `linkedin` URL.
It sits in THREE campaign rows:

    productive-email-batch1-kresimir    bison 491      status approved
    productive-email-stoptest-501       bison 501      status draft
    productive-linkedin-stoptest-621824 heyreach 621824 status draft

**`leadstop._campaign_of(rec, rows, requires="bison_campaign_id")` returns the
FIRST row holding the record that carries the field.** For this record that is
the 491 row. So the email stop for the test identity resolves to **EmailBison
campaign 491** — a real campaign that has really sent — and not to the
purpose-built 501. That resolution is part of what is under test and §3 does
not override it with an explicit `campaign=`, because overriding it is exactly
the defect `leadstop.sweep` had to fix in itself.

### 1.4 THE FINDING THAT MATTERS MOST: A MERGE IS NOT A DEPLOY

`scripts/reply_watch_loop.py` PID 60108 started **2026-09-25T12:36:34Z**. It
imports its modules once and never reloads them. Against the production
checkout's mtimes:

    module                      mtime (UTC)              vs process start
    src/leadstop.py             2026-09-25T12:35:42Z     52s BEFORE  -> loaded
    src/inbound.py              2026-09-23T16:44:41Z     before      -> loaded
    src/providerwrites.py       2026-09-26T16:42:48Z     AFTER  -> STALE
    src/providers/bison.py      2026-09-28T00:51:27Z     AFTER  -> STALE
    src/providers/heyreach.py   2026-09-28T00:51:27Z     AFTER  -> STALE

The running loop holds the FIXED readbacks in `leadstop` (mtime is 52 seconds
before the process start — that is the `50ade3b0` fix, and it is the only
reason this process is worth anything). It does **not** hold master's write
layer or master's provider adapters. `git log` since the process start shows
`08af5146` changing `src/providerwrites.py` by **+72/-9** ("a resume now
re-reads the stops from disk and refuses by name") — on the module every stop
passes through.

**Consequence for this task: a validation run against PID 60108 as it stands
would produce a verdict about code that is on nobody's branch — 09-25's
`providerwrites` and provider adapters, with 09-28's `leadstop`. It would not
be a statement about `4b1fb0c6`.** This is the single reason the decision in §7
is shaped the way it is.

And the recovery path is broken too. `supervisor.STATIC_MONITORS`'s first entry
IS `reply_watch`, and the systemd unit exists — but `supervisor._run()` does

    monitors = table if table is not None else monitors()

which binds `monitors` as a function-local for the whole body, so the `else`
branch reads an unbound local. Proven at the bytecode, not from the comment
above it: `LOAD_FAST_CHECK 3 (monitors)`. Both production callers pass no
table (`scripts/supervise.py:35`, `scripts/cold_start.py:336`). **So if PID
60108 dies, nothing restarts it, and a cold start crash-loops.** Not mine to
fix — `src/` is off-limits on a design task — recorded here because it is an
abort condition for any run (§5, A6) and a P0 in its own right.

### 1.5 Three docstrings on this path are now false

`providerwrites.describe(LINKEDIN_STOP_LEAD)` returns a description ending
**"NOT in SUPPORTED: enabling is an operator decision and this task does not
have it"** — while the verb IS in `SUPPORTED`. The same sentence appears in
`providerwrites.REPEATABLE`'s comment and in `leadstop.stop_linkedin_contact`'s
docstring. `require_supported` reads the tuple, not the prose, so the verb is
live. **Nobody planning this run may reason from those sentences.**

### 1.6 The tripwire that is green because it reads an empty store

`tests/test_the_linkedin_stop_can_actually_address_somebody.py` carries
`TestTheCrossChannelPopulationIsEmpty.test_no_contact_is_bound_on_both_providers_yet`,
written so that the day a contact is bound on both providers it turns red and
says what now has to work. Demonstrated both ways this session:

    default QUEUE (worktree, empty work/)   ... ok
    QUEUE=<production work/queue.jsonl>     ... FAILED
        AssertionError: Lists differ:
        [(<the test record>, <the test contact key>)] != []

**The tripwire has already fired against the canonical store and is green in
the suite**, because the suite's store is empty. Its sibling in the same file,
`test_the_store_uses_linkedin_and_not_linkedin_url`, is in
`docs/state/SUITE-BASELINE-2026-09-26.txt` as a known failure for the same
reason, which is the proof that this file does not see production state when
the suite runs it. This is invariant 0 in one file: a guard measuring a fixture
and reporting on an estate.

---

## 2. WHY A MOCK OR A LOG CANNOT SETTLE IT

Not a principle — four specific things, each of which has already happened here.

**2.1 A mock cannot get the identifier wrong.** `heyreach.stop_lead_in_campaign`
needs `leadMemberId` = `linkedInUserProfile.linkedin_id`. Measured minutes
apart on one lead: `linkedInUserProfileId` (the `ACoAA...` value **HeyReach
support itself named**) returned **404**; the row's own `id` returned **404**;
`profile.linkedin_id` returned **200**. The 404 body says *"The lead is not
present in the campaign you are trying to modify"* — about a lead two read
routes report as present and `InSequence`. **A mock accepts whatever it is
handed and returns success for all three.** No amount of mocking distinguishes
them; one live call does.

**2.2 A mock cannot notice that the field never existed.** For its whole life
until 2026-09-24, `stop_linkedin_contact` built `profile_url` from
`contact["linkedin_url"]`. Across the live store: 1,014 contacts carry
`linkedin`, **zero** carry `linkedin_url`. So `profile_url` was always `""`
and the email->LinkedIn stop **could never have succeeded — not
intermittently: never.** The unit tests were green throughout, because they
construct their own contact dicts. The repo's own words for it: *wired,
unit-tested, sealed, and incapable.*

**2.3 A log entry is an assertion by the process that wrote it.** The audit
recorded `ACCEPTED` for every email stop because the readback was
`lambda: {"stopped": True}` against `expected={"stopped": True}` —
`_classify` comparing a literal to itself. Simultaneously the LinkedIn readback
returned the raw campaigns LIST against a dict `expected`, so `_classify` fell
to `observed == expected` and recorded `DRIFTED` for stops that genuinely
worked. **The same ledger was false-positive in one direction and
false-negative in the other, at the same time.** Any log line from before
2026-09-25T12:35Z is inadmissible, and that is every line the two "halt lifted"
figures rest on.

**2.4 The test harness can dissolve the guard it is testing.**
`providers.set_transport(fn)` replaces the wire wholesale and bypasses
`refuse_unauthorized_write` entirely. That is how the suite runs. So a green
suite is compatible with a transport that would have been refused in
production — which is precisely how the missing `allow_writes` scope survived:
`reply_watch_loop` set `REPLY_POLL_ENABLED` and no write scope, every stop it
attempted was refused by the interceptor, and the refusal was caught and
recorded as an error nobody read. A prospect replied "no thank you" on LinkedIn
at 11:12:33Z; the stop was refused at 11:19:35Z; she stayed `in_sequence` in
EmailBison 491 for **2h07m**.

**What a mock CAN prove, and does:** the decision logic, the classification
independence, the per-channel campaign resolution, duplicate suppression,
idempotency of the recorded event, that a refusal is reported as REFUSED, and
that a constant readback would pass where the real one does not. That work is
done and does not need redoing. **What it structurally cannot reach is the four
things above: route, identifier shape, provider semantics, and whether the
guard is armed on the real wire.** Only a provider readback reaches those.

---

## 3. THE SMALLEST SAFE LIVE VALIDATION, PER DIRECTION

Design principles, taken from the campaign-500 precedent in
`docs/PRODUCTION-HANDOFF-2026-09-28-MIDDAY.md` §2a — that write was chosen
because the campaign *could not touch a prospect even in principle*:

    P1  The only person addressable by either direction is the operator.
        Measured, not assumed: the both-bound population is 1 (§1.3).
    P2  ZERO send-shaped writes. The only two verbs used are the two stops,
        and a stop can only ever reduce what somebody receives.
    P3  The trigger is a message the OPERATOR sends. Nothing leaves this
        system during the run.
    P4  Every precondition is a provider READ, and an unreadable one aborts.
    P5  Production resolution is never overridden. No explicit `campaign=`,
        no hand-built URL, no `set_transport`, no
        `RESONATE_PROVIDER_WRITES=1` (it is a process-wide bypass of `only=`).
    P6  The stop runs on the thread that opened `allow_writes`.
        `_write_scopes` is a ContextVar and fails CLOSED into a thread — a
        threaded harness produces a refusal that looks like a missing grant.

### 3.0 What is NOT in scope, and why that keeps this to one decision

**Putting a lead into a running state is not part of this design.** On HeyReach
that means `LINKEDIN_ADD_LEAD` (in `SUPPORTED`, but CONDITIONAL — `perform`
refuses unless a live read proves the destination campaign is DRAFT) followed
by `LINKEDIN_ACTIVATE`, which goes through `executionguard` and therefore
through `killswitch.workspace_state('productive')`, **which refuses while
`sending.live` is off.** On EmailBison it means `EMAIL_ADD_LEAD`, which is
**not in `SUPPORTED` at all**, and `EMAIL_ACTIVATE`, refused for the same
reason.

So: **if the provider does not already hold the test identity in a running
status on the target channel, this validation cannot be set up without moving
the killswitch, and moving the killswitch for a validation is the one thing
three independent protections exist to prevent.** That case is an ABORT and a
separate decision, not a step of this one. §5, A2.

### 3.1 DIRECTION 1 — a reply on LINKEDIN must stop the EMAIL sequence

    TRIGGER        the operator sends a message in the existing LinkedIn
                   conversation on the owned seat. NO provider write from us.
                   NO send from us.
    PROVIDER OBJECTS READ
                   heyreach POST /inbox/GetConversationsV2   (the poller's own)
                   bison    GET  /leads/205079               pre-state
                   bison    GET  /campaigns/{resolved}/leads  sample, pre + post
                   bison    GET  /campaigns/{resolved}        status, unchanged?
    THE ONE WRITE  POST /campaigns/{resolved}/leads/stop-future-emails
                   body {"lead_ids": [205079]}
                   {resolved} is whatever `leadstop._campaign_of` chooses. On
                   today's store that is 491 (§1.3) and the run RECORDS it
                   rather than choosing it.
    READBACK       bison.lead(205079).lead_campaign_data status for {resolved}
                   must be in STOPPED_STATES, read by an independent probe and
                   not only by `perform`'s own readback.
    BUILT-IN BLAST CHECK
                   `bison.stop_lead` refuses an absent lead up front (the route
                   answers 200 and does nothing for a non-member), polls
                   `lead_campaign_data` up to 8 attempts / ~14.5s until the stop
                   lands, and RAISES if any other sampled member's status moved.
    PRE-ASSERTION  int(lead_ids[0]) in testidentity.LEAD_IDS, asserted on the
                   ID ALONE. An EmailBison event can arrive carrying the lead id
                   and nothing else, and `matches(205079)` was once False for
                   exactly that reason.

**Why this is the cheap direction:** the LinkedIn side needs no write and no
send at all — the operator types a message into a conversation that already
exists. Our entire exposure is one stop write naming one lead id that is the
operator's own.

### 3.2 DIRECTION 2 — a reply on EMAIL must stop the LINKEDIN sequence

    TRIGGER        the operator replies by email into an existing thread on the
                   test lead. NO send from us.
                   THE OPEN QUESTION, and it is UNKNOWN rather than assumed:
                   whether EmailBison's /replies feed exposes that reply with
                   `row["lead"]["custom_variables"]` populated, which is where
                   `adapters._custom` reads record_id / contact_key / client.
                   That field was read from the WRONG LEVEL until 2026-09-25,
                   so record_id was None for EVERY EmailBison reply ever
                   ingested. If the reply arrives unmatched, this direction
                   ends as UNKNOWN — see §5, A8 — and the fallback (a one-lead
                   send) is refused by §3.0 and comes back as its own decision.
    PROVIDER OBJECTS READ
                   bison    GET  /replies                   (the poller's own)
                   heyreach POST /campaign/GetLeadsFromCampaign  on 621824:
                            the ONLY route that yields `member_id`, plus the
                            pre-state leadStatus
                   heyreach POST /campaign/GetCampaignsForLead   independent
                            cross-check of the same pre-state, and the
                            post-stop confirmation
    THE ONE WRITE  POST /campaign/StopLeadInCampaign
                   body {"campaignId": 621824,
                         "leadMemberId": <member_id from GetLeadsFromCampaign>,
                         "leadUrl": <the contact's `linkedin`>}
                   leadMemberId MUST be profile.linkedin_id. NOT
                   linkedInUserProfileId, NOT the row's own id — both 404 with
                   a message that blames membership (§2.1).
    READBACK       campaigns_for_lead(profile_url) lists 621824 with leadStatus
                   NOT in RUNNING_LEAD_STATUSES — expect `Paused`, whose
                   provider-side message reads
                   "The workflow was paused manually. (API)".
    ASSERT THE READBACK'S OWN CEILING, or the verdict is void
                   `campaigns_for_lead` is a SINGLE page, `limit <= 100`, and
                   it DISCARDS `totalCount`. Both readbacks on this direction —
                   `heyreach.stop_lead_in_campaign`'s own and
                   `leadstop._linkedin_stop_took` — use it. If the profile is
                   in more than 100 campaigns the target falls off page one and
                   both conclude "not listed" -> refuse. So the run asserts
                   `totalCount <= 100` BEFORE believing any verdict from it.
    ASYMMETRY TO EXPECT
                   the LinkedIn stop is SYNCHRONOUS — one readback, no polling
                   loop — where the email stop polls for ~14.5s. If HeyReach's
                   stop is eventually consistent, this direction RAISES where
                   the email direction would have waited. That is a FALSE FAIL
                   and §5 A5 covers it.

### 3.3 The clock, and what it is measured from

The operator's standing condition is **reply -> stop inside 15 minutes**,
measured from the PROVIDER's own timestamp on the reply, never from when our
watcher noticed it. On 09-25 the watcher's own figure was 3m47s against a true
4m02s — flattering and wrong. Recorded fields per direction:

    t0  the provider's timestamp on the reply
    t1  the reply visible in the provider's feed        (provider visibility,
                                                         not ours — it was 4.4
                                                         of the 7.7 minutes)
    t2  ingested                                        events.REPLY_RECEIVED
    t3  the write issued
    t4  the independent readback confirms
    poll interval in force on the executing process     (300s on PID 60108)

---

## 4. WHAT COULD GO WRONG, AND WHAT IT WOULD COST

**4.1 The validation itself sends something to a real person.**
**With the §3 preconditions read back, this design can rule that out. Without
them, it cannot — and then the run must not start.**

Ruled out how: the run performs **zero send-shaped writes**. The only two verbs
it uses are `EMAIL_STOP_LEAD` and `LINKEDIN_STOP_LEAD`, both declared
`prospect_facing=False`, both of which can only reduce what somebody receives.
No lead is added (`EMAIL_ADD_LEAD` is not in `SUPPORTED`; `LINKEDIN_ADD_LEAD`
is CONDITIONAL on a DRAFT destination). No campaign is activated or resumed
(refused through `executionguard` by the killswitch while `sending.live` is
off). No sequence is written. Both triggers are messages the **operator**
sends. **Nothing can leave this system during the run.**

The residual, stated plainly: if the pre-run readback of the target provider
campaigns cannot be completed — credentials unauthenticated, a lead list that
will not paginate, `totalCount` above the single-page ceiling — then this
design **cannot rule out that a targeted campaign holds somebody other than the
operator**, and in that case the run is refused rather than reasoned about.
That is abort A1/A3.

**4.2 The stop is aimed at the wrong lead.** Cost: one real prospect
irreversibly stops receiving a sequence. The direction of harm is a reduction
rather than an unwanted send, which makes it survivable but not free — a real
lead is destroyed and there is no un-stop. Mitigation: a single-element
`lead_ids` asserted against `testidentity.LEAD_IDS` by the id alone;
`bison.stop_lead`'s own refusal for an absent lead; and its post-write sample
raising if any other member moved.

**4.3 The write lands on a campaign the operator did not expect.** The test
record sits in three rows and `_campaign_of` returns the first. Cost: the
evidence says 491 while the operator believes 501, and 491 is a campaign with
real history. Mitigation: the resolved campaign id is recorded as primary
evidence and the resolution is treated as under test (§3.1), never overridden.

**4.4 A PASS that means nothing because the executing process is not master.**
Cost: the most expensive failure mode this repository has — a `LIVE_VALIDATED`
stamp no SHA supports, which then licenses an 825-person enrolment. Already
true today: PID 60108 is three days and roughly forty merges behind on three
modules of the stop's own path (§1.4). This is what §7 is a decision about.

**4.5 A FALSE FAIL from an unreadable provider.**
`leadstop._linkedin_stop_took` catches **every** exception and returns `False`
— not-proven-stopped — which classifies as `DRIFTED` and raises
`WriteUnverified`. So a transient read failure is byte-for-byte
indistinguishable from a stop that did not work. Cost: a working safety
mechanism recorded as broken, and a `WriteUnverified` in the ledger that a
future session reads as an incident. Mitigation: A5 — an unreadable readback
is UNKNOWN, never FAIL.

**4.6 A repeat run reaches the provider again.** Both stops are in
`REPEATABLE`, so `staged_already` is not consulted and no `provider_staged` row
is written. Intended — a repeat can only mean somebody receives less — but it
means **the write layer gives this run no idempotency backstop.** Each re-run
is a real write. Cost: after the first successful run the target is settled, so
every subsequent run passes by construction (A2) and proves nothing.

**4.7 The reply-path process dies mid-run.** Nothing restarts it (§1.4) and the
run stalls looking like a stop that never fired. Cost: hours, and a FALSE FAIL
on the record. Mitigation: A6 records the PID and its start time, and the
watcher's liveness is asserted at t0 and again at t4.

---

## 5. THE ABORT CONDITIONS AND THE ROLLBACK, STATED BEFORE THE RUN

### 5.1 Abort — any one of these and the run does not start, or stops where it is

    A1  BISON_KEY or HEYREACH_KEY is not AUTHENTICATION_VERIFIED by
        scripts/credential_health.py --verify. A set variable is not an
        authenticated one, and a transport failure is not a bad key.
    A2  The pre-state readback shows the target already settled — a bison
        status in STOPPED_STATES, or a HeyReach leadStatus outside
        RUNNING_LEAD_STATUSES. The run would then PASS BY CONSTRUCTION:
        `stop_contact` returns `already: True` and writes nothing, and a
        sequence that was already finished looks identical to one that was
        stopped. This is the documented trap — campaign 613744 reads
        `Finished` for this identity and must never be the subject.
    A3  A target provider campaign holds any lead other than the test
        identity, or its lead list cannot be paginated completely, or
        `campaigns_for_lead` reports `totalCount > 100`.
        GetLeadsFromCampaign honours NO filters — a status filter is accepted
        and ignored and the unfiltered total is returned — so scoping is the
        caller's job and a partial read is not estate truth.
    A4  killswitch.workspace_state('productive'), read from the PRODUCTION
        checkout, does not return sending False with a reason naming
        productive. Read from a worktree it fail-closes to the same boolean
        with the reason "no such workspace" — that is UNKNOWN, not a match.
    A5  Any readback raises, or cannot be completed. The verdict is UNKNOWN,
        the run stops, and UNKNOWN is never written down as FAIL, PASS, zero,
        clean or safe.
    A6  The executing process is not the SHA the run intends to validate, or
        its PID changed between t0 and t4.
    A7  Any write is attempted to a route outside inbound.STOP_ROUTES. That is
        the interceptor doing its job and the run is over; the refusal is
        already appended to work/provider-write-refusals.jsonl.
    A8  The trigger reply arrives `unmatched` — record_id None. That is the
        `adapters._custom` defect class and the direction ends UNKNOWN. It is
        NOT escalated to a send (§3.0).

### 5.2 Rollback — and the honest part first

**There is no un-stop, and the design does not pretend there is one.**
`EMAIL_STOP_LEAD`'s own contract records that a stopped membership cannot be
restarted by re-attaching the same campaign (the provider answers 422), which
is deliberate: a stop must not be silently undoable by a routine re-stage. On
HeyReach the stop lands on `Paused` and `LINKEDIN_RESUME` is **not in
`SUPPORTED`**, so this system cannot undo that either.

So the rollback is not of the write. It is:

    R1  The sealed-run mutation (NC-3) is reverted and the source verified
        BYTE-IDENTICAL by hash before and after. Never "looks restored".
    R2  No local queue write is made by the probe. The stop's own
        PROVIDER_STOP_CONFIRMED event rides ingest's single save with
        `persist=False`, which is the production behaviour under test — a
        nested transaction there is ISSUE-001 and discards ingest's own work.
    R3  The executing process is left on a RECORDED SHA — either restored to
        what it was, or deliberately on master and written down. Never
        undocumented.
    R4  `docs/state/PROVIDER-CAMPAIGNS.json` is regenerated by
        scripts/provider_truth.py afterwards, because `inbound._owned()`
        REFUSES to drop an unattributable reply when that readback is more
        than 24h old, and a run that leaves it stale changes behaviour for
        every reply after it.

**Because the write cannot be rolled back, the entire safety argument rests on
target choice** — the campaign-500 reasoning: the only lead named is the
operator's own, so the irreversible act costs nothing.

---

## 6. THE NEGATIVE CONTROLS — what must FAIL

A validation that only shows the happy path proves almost nothing. Each control
below has a specific prior failure behind it.

    NC-1  PRE-STATE, both directions. The target must be measured in a
          RUNNING / resumable status within the recorded window before the
          trigger, by TWO independent routes on the LinkedIn side
          (GetLeadsFromCampaign and GetCampaignsForLead) and by the per-lead
          read on the email side. WITHOUT THIS THE RUN CANNOT DISTINGUISH A
          STOP FROM A SEQUENCE THAT HAD ALREADY FINISHED. Prior: 613744 reads
          Finished for this identity and a stop against it returns "already
          settled" — a pass by construction.

    NC-2  SIBLING SCOPE, email direction. A second member of the resolved
          campaign measured running before and still running after — proving
          the LEAD stopped, not the CAMPAIGN. `bison.stop_lead` already
          raises if any other sampled member moved; the sample is recorded as
          evidence rather than trusted silently. Prior: the verb's own
          measurement on 2026-09-13 is exactly this — one lead moved
          in_sequence -> stopped, the sibling untouched, the campaign's status
          unchanged.

    NC-2b CROSS-CAMPAIGN SCOPE, LinkedIn direction. If 621824 holds only the
          one lead, NC-2 is UNAVAILABLE there and this is the substitute: the
          same profile's leadStatus in a DIFFERENT HeyReach campaign must be
          unchanged, proving the stop was scoped to one campaign rather than
          to the person. `campaigns_for_lead` returns every campaign for the
          profile, so this control costs nothing — and `_linkedin_stop_took`
          is scoped to one campaign for precisely this reason.

    NC-3  THE SEALED RUN — the killed mutation, and the most important one.
          BEFORE the authorised run, execute the identical chain with the
          verb removed from `providerwrites.SUPPORTED` — one line, reverted
          and hash-verified afterwards — against the SAME running target, and
          prove all three:
              a) `perform` raises WriteUnsupported;
              b) the provider status is UNCHANGED on an independent readback;
              c) `inbound.summarise_stops` prints REFUSED, not "stopped".
          This is what proves it is OUR STOP that moved the lead and not
          something else, and it proves the readback can say NO. Confirm the
          INTENDED refusal fired for the INTENDED reason and that a different
          gate did not fire first.

    NC-4  THE UNSCOPED RUN. Run once with no `allow_writes` scope open and
          prove `ProviderWriteRefused` is raised at the transport BEFORE the
          socket opens, with a row appended to
          work/provider-write-refusals.jsonl. Prior, and it is the reason this
          control exists: `reply_watch_loop` opened no write scope, every stop
          it attempted was refused and caught as an error nobody read, and a
          prospect who said "no thank you" on LinkedIn stayed `in_sequence` in
          EmailBison 491 for 2h07m.

    NC-5  NO SAME-CHANNEL REPLY IN THE WINDOW. Prove no reply exists on the
          TARGET channel between t0 and t4. EmailBison marks a lead `replied`
          BY ITSELF when a reply arrives by email — four of five
          locally-stopped contacts read `replied` for that reason alone — and
          `replied` is in STOPPED_STATES, so a same-channel reply would hand
          this run a free pass. Cross-channel is structurally clean here
          (HeyReach cannot know about an email reply and EmailBison cannot know
          about a LinkedIn one), and this control is what turns that
          expectation into evidence.

    NC-6  THE CONSTANT-READBACK TEST, re-run against the exact SHA under
          validation and its result recorded:
              py -3 -m unittest tests.test_a_reply_stops_the_other_channel.TheReadbackCannotLie
          Four tests, including
          `test_a_constant_readback_would_pass_but_the_real_one_does_not`.
          This is the guard against the defect that voided both 09-25 figures.
          A test count is not a PASS; the named result is the evidence.

**A run missing NC-1 or NC-3 is not a validation and must not be reported as
one.**

---

## 7. THE OPERATOR AUTHORISATION BEING ASKED FOR

One decision. One only — a block with two decisions in it gets the first
answered and the second lost.

---

### 🔴 TREBAM TVOJU ODLUKU — cross-channel stop, živa validacija

**PROBLEM.** Launch blocker 4 traži čitanje sa providera. Mjerenja od 09-23 i
09-25 to nisu: oba su nastala dok je audit potvrđivao sam sebe — email
read-back je bio konstanta identična očekivanju, a LinkedIn read-back je
vraćao listu protiv dicta, i to je popravljeno u 12:35Z, **jedanaest minuta
nakon** mjerenja koje je diglo halt. Stanje je zato **IMPLEMENTED / NEVER
LIVE_VALIDATED, u oba smjera.**

Dobra vijest, izmjereno danas: validacija se može izvesti **bez ijednog
slanja** i s **dva pisanja ukupno** (po jedan stop u svakom smjeru). Jedini
kontakt u cijeloj bazi vezan na oba providera **si ti** — 1 od 1.065 — pa ni u
principu ne može dotaknuti prospekta. Tvoja poruka je okidač u oba smjera.
Killswitch ne blokira stop (oba glagola su `prospect_facing=False`), pa freeze
ostaje netaknut.

**Loša vijest, i ona je cijela odluka:** proces koji bi to izveo —
`reply_watch_loop`, PID 60108 — pokrenut je **2026-09-25T12:36:34Z** rukom i
od tada nije ponovno učitao module. Drži `providerwrites` i oba provider
adaptera iz 09-25; master ih je od tada mijenjao, jedan commit sam
`providerwrites` za +72/-9 — a to je modul kroz koji stop prolazi. Dodatno:
`supervisor._run()` puca na `UnboundLocalError` prije nego išta pokrene, pa
ako taj proces umre, **ništa ga ne vraća.**

**OPCIJA A — ODOBRI, uz restart na master.** Restartaj reply put s
`origin/master`, zapiši SHA, pa odradi oba smjera po ovom dizajnu: nula
slanja, dva pisanja, svih šest negativnih kontrola, prekid na svakom
nečitljivom autoritetu. **Cijena:** restart u istom trenutku podiže ~40 mergeva
na safety putu, i ta pisanja su nepovratna (stop se ne može odvrnuti) — ali
padaju isključivo na tvoj vlastiti lead.

**OPCIJA B — NE SADA.** Ostavi klasifikaciju IMPLEMENTED / NEVER
LIVE_VALIDATED, halt na cross-channel enrolment ostaje na snazi, i prvo se
poprave dvije stvari koje bi svaku buduću validaciju učinile besmislenom:
supervisor koji se ne može pokrenuti, i tripwire test koji je zelen samo zato
što čita prazan store (protiv prave baze je crven — provjereno danas).
Validacija ide onda kad se LinkedIn sloj otvori, što odluka 15 trenutno
odbija.

**PREPORUKA: A.**

**ZAŠTO.** Izloženost je izmjerena, ne procijenjena: jedan adresabilan čovjek
i on si ti, nula slanja, dva pisanja koja mogu samo smanjiti ono što netko
prima. Opcija B ne štedi ništa — ona premješta neprovjereni safety mehanizam u
trenutak kad se upisuje 825 ljudi, pod pritiskom, umjesto sada na miru. A dok
je neprovjeren, ništa ne upozorava: tripwire koji je za to napisan je zelen.
Jedini pravi trošak A je restart, i on se ionako mora dogoditi prije bilo
kakvog cutovera — bolje kontrolirano, s jednim mjerenjem odmah nakon njega.

**Odgovori "A" ili "B".**

---

### The same decision in English, for the record

**PROBLEM.** Launch blocker 4 requires a provider readback. The 09-23 and
09-25 measurements are not one: both were produced while the write layer's
readback confirmed itself, and the fix landed eleven minutes AFTER the
measurement that lifted the halt. State: **IMPLEMENTED / NEVER LIVE_VALIDATED,
both directions.**

Measured today: the validation can be done with **zero sends** and **two
provider writes total** — one stop per direction. The only contact bound on
both providers is the operator's own test identity (1 of 1,065), so no prospect
is addressable even in principle. The trigger in both directions is a message
the operator sends. The killswitch does not gate either stop, so the freeze is
untouched.

The complication, and it is the whole decision: the process that would execute
it, `reply_watch_loop` PID 60108, was hand-started at 2026-09-25T12:36:34Z and
has not reloaded a module since. It holds 09-25's `providerwrites` and both
provider adapters; master has changed `providerwrites` by +72/-9 since, on the
module every stop passes through. And `supervisor._run()` raises
`UnboundLocalError` before spawning anything, so if that process dies nothing
brings it back.

**OPTION A — AUTHORISE, with a restart onto master.** Restart the reply path
from `origin/master`, record the SHA, then run both directions as designed:
zero sends, two writes, all six negative controls, abort on any unreadable
authority. Cost: the restart makes ~40 merges live on the safety path at once,
and the two writes are irreversible — landing only on the operator's own lead.

**OPTION B — NOT NOW.** Keep the classification, keep the cross-channel
enrolment halt, and first fix the two things that would make any future run
meaningless: the supervisor that cannot start, and the tripwire test that is
green only because it reads an empty store. Validate when the LinkedIn layer
is reopened; decision 15 currently refuses it.

**RECOMMENDATION: A.** The exposure is measured rather than estimated — one
addressable person and it is the operator, zero sends, two writes that can only
reduce what somebody receives. B saves nothing: it moves an unproven safety
mechanism to the moment 825 people are being enrolled, under pressure, instead
of proving it now in calm. And while it is unproven nothing warns anybody — the
tripwire written for this is green. A's only real cost is the restart, which
has to happen before any cutover regardless; better done deliberately, with one
measurement taken immediately after it.

**Answer "A" or "B".**

---

## 8. WHAT THIS TASK DID, AND WHAT IT DELIBERATELY DID NOT

    provider writes            0
    provider reads             0 — BISON_KEY and HEYREACH_KEY are unset here,
                                 so provider state is UNKNOWN, not clean
    files edited in src/       0
    merges to master           0
    Slack posts                0
    local state files written  0 — the probe opens the queue read-only

Owned and delivered by this task:

    docs/CROSS-CHANNEL-STOP-VALIDATION-DESIGN-2026-09-28.md   this document
    scripts/probe_cross_channel_stop.py                       READ-ONLY probe

`scripts/probe_cross_channel_stop.py` REFUSES rather than answering when the
queue it is pointed at does not exist, because a worktree's own empty `work/`
would otherwise report a population of zero — a false negative that looks
exactly like the true one.

### Findings surfaced here that are NOT this task's to fix

    F1  supervisor._run() raises UnboundLocalError before spawning any
        monitor. Both production callers pass no table. The reply poll is the
        first entry of its own table, so nothing supervises or restarts it.
        P0 in its own right.
    F2  providerwrites.describe(LINKEDIN_STOP_LEAD) still says "NOT in
        SUPPORTED" about a verb that is in SUPPORTED. Same sentence in
        REPEATABLE's comment and in leadstop.stop_linkedin_contact's
        docstring. Three false statements on a safety path.
    F3  tests/test_the_linkedin_stop_can_actually_address_somebody.py's
        cross-channel-population tripwire is green in the suite and red
        against the canonical store. It has already fired and nobody has seen
        it.
    F4  heyreach.campaigns_for_lead reads one page of at most 100 and
        discards totalCount, and it is the sole readback for the LinkedIn
        stop in two places. A silent ceiling on a safety readback.
    F5  leadstop._linkedin_stop_took converts every read exception into
        "not stopped", so an unreadable provider is indistinguishable from a
        failed stop — UNKNOWN laundered into FAIL on a safety path.
    F6  docs/DECISIONS-2026-09-25-OPTION-A-AND-THE-FREE-CRAWL.md §6 lifts the
        LinkedIn halt on two figures its own next paragraph invalidates.
        Operator decision 14 supersedes it; the document still reads as
        current to a fresh session.
