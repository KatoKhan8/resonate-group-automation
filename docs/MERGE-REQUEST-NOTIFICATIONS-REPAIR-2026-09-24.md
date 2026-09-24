# Merge request: #resonate-notifications, repaired

**Branch:** `notifications-repair`
**Base:** `68312d2f`
**NOT MERGED.** The foreground session is mid-push tonight. This is committed
on its own branch and is waiting for review.

---

## 0. THE NUMBER

| | posts to `#resonate-notifications` in 72 hours |
| --- | --- |
| before | **102** |
| after | **4** |

Measured, not modelled: 102 is the count of `unmatched_reply_needs_review`
rows with `status: sent` in `work/notifications.jsonl` between
2026-09-21T18:26Z and 2026-09-24T18:26Z. 4 is those same 102 events replayed
through the new path by `scripts/notifications_replay.py`, which posts
nothing and writes its notifications to a temporary directory.

**Two of the four name a real unmatched reply on HeyReach campaign 613744,
which is ours.** They were in the channel the whole time, in the same font as
the hundred that were the client's.

The before-count is a ROLLING 72 hours and it is still climbing, because this
is not merged and the watchers are still running the old path: 102 at
18:26Z, 103 at 18:35Z. The after-count was 4 on both runs.

---

## 1. WHAT WAS ACTUALLY WRONG

Every one of the 102 posts carried the same five fields:

    provider: heyreach
    Status: unmatched
    Why: no record for this event
    Held: 0
    Action: a person decides; nothing is auto-attributed

No campaign, no lead, no event type, no timestamp. Nothing to act on, and
nothing to dismiss either - which is worse than a wrong alert, because a
wrong alert at least gets read once.

Three faults produced it, and they are independent:

### 1.1 Nothing asked whose campaign it was

Both provider credentials are workspace-wide and the client runs their own
outreach in the same two accounts. Walked once, 2026-09-21T18:17Z to
2026-09-24T17:44Z, `bison.fetch_events`, 4,190 events:

    client campaigns          2,948    327, 328, 352, 418
    our campaigns             1,179    489, 491-498
    estate-level, no campaign    63    blacklist and mailbox events

After midnight on 2026-09-24: 841 events, **808 of them the client's**. The
brief said 194 and none of ours; the fuller walk says 841 and 19 of ours, and
all 19 are `EMAIL_SENT` / `LEAD_FIRST_CONTACTED` rather than anything
unmatched. The direction of the claim holds and the count did not, which is
this project's own recurring shape - a number quoted from a stage that had
not asked the next stage's question.

### 1.2 The one attribution that existed compared the wrong namespace

**This is the serious one, and it is a latent silent data loss rather than a
noise problem.**

`inbound._positively_not_ours` tested an event's `external_campaign_id`
against `owned_campaigns`, a set built from the **HeyReach** block of
`docs/state/PROVIDER-CAMPAIGNS.json`. An EmailBison event carries an
**EmailBison** campaign id. Our own campaign 491 is not in
`{594061, 599020, 604869, 605487, 605732, 613724…}`, so:

> every unattributable EmailBison reply on a campaign WE RUN read as
> "positively not ours" and was dropped, with no notification and no record.

It has never fired. Not because of a guard, but because `_owned()` has been
refusing since the ownership readback went stale - 32 hours at the time of
writing, against a 24-hour limit - and a refusal makes the whole predicate
return False. **A timer has been holding off a silent loss of our own
replies.** Run `scripts/provider_truth.py` on the old code and it starts.

### 1.3 Seat attribution stopped answering the question

TASK-238 dropped a HeyReach event on a seat we do not operate. It was
measured when we ran **1 of 41** seats. `PROVIDER-CAMPAIGNS.json` now says
**33 of 41**, because the B1 campaigns were put on the CLIENT'S OWN seats -
and the client's campaigns still run on those seats.

Sampled live, 2026-09-24, 50 conversations from `GetConversationsV2`: the
seats carrying them are 174797, 208242, 116973, 175455, 175552, 174845,
174742, 143105, 191848, 181658. **Ten of ten are seats we operate.** Resolved
by lead, every one of those conversations belongs to a campaign of the
client's and to none of ours.

So a seat can still prove an event is NOT ours and can no longer prove that
it is. **A seat is not a campaign.**

---

## 2. THE FIVE PARTS

### 2.1 Attribution first - `src/unmatched.py`

    campaign id present, in OUR registry for that provider   -> OURS
    campaign id present, in none of our campaigns            -> THEIRS
    no campaign id, lookup refused, lookup empty             -> UNATTRIBUTED

`OURS` and `UNATTRIBUTED` reach the channel. `THEIRS` reaches the ledger and
nothing else. The registry is **per provider** and cannot repeat 1.2:
`bison_campaign_id` and `heyreach_campaign_id` are read out of
`work/campaigns.jsonl` into two separate maps that are never merged.

Our own campaign state is the source, not a provider readback that expires -
a campaign row is written when we create the campaign, so it is there before
the first send. `PROVIDER-CAMPAIGNS.json` is unioned in as a FLOOR at any
age, because a stale readback can only have MISSED a campaign of ours, never
invented one; adding it can only move an event from THEIRS to OURS.

**HeyReach campaign attribution exists and TASK-238 concluded it did not.**
That task measured `POST /inbox/GetConversationsV2`, which carries no
campaign, and wrote "there is NO documented endpoint… do not go looking for
one". `POST /campaign/GetCampaignsForLead` is already in
`src/providers/heyreach.py` and answers the question the other way round: it
returns every campaign a LEAD is in, with names and the lead's status in
each. Measured on live conversations: 5 to 18 campaigns per lead.

### 2.2 Every posted alert names its object - `notify.MUST_NAME`

A table, per event type, of the fields without which the alert says nothing.
Checked in `plan()` on the payload **after the scrub**, because the scrub is
what can remove the field that named the object. An alert that names nothing
is stored `SUPPRESSED` with the missing field names in `why` - visible in
`/notifications`, not deleted.

The precedent is `d6a719c2`, and it is the same rule from the other side:
every external-stop CRITICAL named campaign 487 while carrying 491's figures,
because the call site passed a module constant instead of `watched`. One is
actively dismissed; the other is scrolled past. Both are alerts that do not
name their object.

`tests/test_an_alert_names_its_object.py::EveryPostedAlertNamesItsObject`
is the required test. It asserts the shape of the 102 posts VERBATIM is
refused, that every digest the new path can build passes the gate, and - the
mutation - that removing one required field from a real digest payload makes
that payload unpostable.

The STATUS feed is out of scope, by construction rather than by exception:
`_status_payload` refuses ids, names and addresses because that channel has
the widest human audience in the product. Requiring it to name an object
would require it to break its own contract.

### 2.3 Aggregate - one digest an hour

`unmatched.flush()` resolves every CLOSED hour and raises at most one
`unmatched_events_digest` for it, carrying counts per campaign and per
provider, up to 20 individual events, and the one action a person can take.

Idempotent on the hour, the way `digestwatch` is idempotent on its period:
the notification id is built from `{"hour": "2026-09-24T17"}`, so twelve
polls inside one hour produce one row. The CURRENT hour is never digested -
posting a partial hour would take the id, and the rest of that hour could
then never be posted.

**A digest with zero rows of ours is not posted at all**, decided in
`summarise()` and nowhere else so a mutation to it fails a test. The count of
client events suppressed rides along in the payload, so the suppression is
visible rather than merely quiet.

### 2.4 Severity and routing - three behaviours

    CRITICAL         PIN_AND_POST    posts immediately, and pins
    ACTION_REQUIRED  POST_NOW        posts immediately
    INFO             DAILY_THREAD    replies under the day's first ops post

The existing `ROUTES` table and the `GLOBAL`/`CRITICAL`/`ACTION_REQUIRED`/
`INFO` constants are untouched. `POSTING` is a second, smaller table mapping
severity to behaviour - a severity is a judgement about the event, a tier is
what the channel does with it, and they were previously the same word.

**`WARNING` maps to `POST_NOW`, and that is the one line worth arguing
about.** Three behaviours means the existing fourth severity must land on
one of them, and the only other candidate is the daily thread - which would
move `campaign_held`, `campaign_qa_failed`, `campaign_paused`,
`sender_capacity_warning`, both infrastructure warnings,
`verification_degraded`, `mx_security_anomaly` and
`provider_credit_warning` into a thread nobody opens. Quieting nine real
guards is not a repair.

The daily thread is **ops only**. A positive reply is `WORKSPACE` and `INFO`,
and burying the one message a client's channel exists for under a thread
would be this change committing the fault it was written to fix.

The thread parent is DERIVED - the day's first sent GLOBAL INFO row with a
`slack_ts` - rather than stored, for the reason `digestwatch` derives
delivery rather than storing it. `deliver()` now persists `slack_ts`,
`thread_ts`, `tier` and `pinned` on the row.

`slack.pin` never raises and never turns a delivered CRITICAL into a FAILED
row. The message is already in the channel by then; a workspace without
`pins:write` would otherwise cause a retry to post it twice.

### 2.5 The three-day walk

Below, §3.

---

## 3. THE SUMMARY - 2026-09-21T18:26Z to 2026-09-24T18:26Z

102 unmatched events, walked once with the new attribution.

| | count |
| --- | --- |
| **the client's own** | **98** |
| **ours** | **2** |
| **ours-or-unknown, unresolved** | **2** |

### 3.1 The client's, by campaign

    heyreach   388952    32
    heyreach   388947    25
    heyreach   388957    21
    heyreach   429679     7
    heyreach   565765     1
    emailbison    327     7
    emailbison    328     5

Every EmailBison unmatched event in the window was on a client campaign.
**None was ours.**

### 3.2 Ours - the whole list

Both are the same lead, two messages, on **HeyReach campaign 613744
(`RESONATE PRODUCTIVE LI B1 SEAT 174892`)**:

    2026-09-23T12:41:05Z  heyreach:2-ZjM5…XzEwMA==:2026-09-23T12:34:28.579Z
    2026-09-23T14:24:54Z  heyreach:2-ZjM5…XzEwMA==:2026-09-23T14:16:24.575Z

`GetCampaignsForLead` places the lead in exactly one campaign, and it is
ours. These are real unmatched replies on a campaign we run, which is the
alert the channel exists for, and they were indistinguishable from the other
hundred.

**613744 is one of the 33 B1 campaigns.** It is in
`PROVIDER-CAMPAIGNS.json` and it is NOT in `work/campaigns.jsonl` - the
script that created those 33 never wrote a campaign row. The readback union
in §2.1 is what makes this event OURS rather than THEIRS, and without it the
one alert worth having in three days would have been filed as the client's.
**That gap should be closed by writing the 33 campaign rows, not by relying
on the union** - see §5.

### 3.3 Unresolved - 2 events, 1 lead

    2026-09-24T14:24:39Z  heyreach:2-M2Zm…XzEwMA==  lookup 404
    2026-09-24T15:19:50Z  heyreach:2-M2Zm…XzEwMA==  lookup 404

`GetCampaignsForLead` answers **404** for this lead. Its profile URL is
percent-encoded, because the handle contains non-ASCII characters. See §5.

Kept, digested and named, exactly as the fail-closed rule requires: the
lookup did not answer, so nothing was concluded.

### 3.4 And the whole path run for real, once

`py -3 -m src.replywatch --once` in the worktree, against the live providers,
with `NOTIFICATIONS` and the ledger pointed at the worktree's own `work/` -
so the production delivery loop, which reads a different file, could not see
what it planned. It polled both providers, ingested 0 replies, attempted 0
stops, and wrote its own ledger from what the poller actually saw:

    95 unmatched events   ->   86 theirs, 6 OURS, 2 unattributed, 1 in the
                               open hour
    6 digests planned, 0 posted

That window reaches further back than the 102 notification rows do, and it
found **six unmatched replies on our own EmailBison campaigns 491, 492 and
495** that never produced a notification at all - the checkpoint had moved
past them before the watchers were last restarted. They are named, with the
campaign and the lead domain, in the six digests.

`GetCampaignsForLead` is registered as a declared READ, so it is not refused
by `providers.refuse_unauthorized_write` and does not need a write scope.
Confirmed rather than assumed: `is_declared_read` answers True for it, and
`work/provider-write-refusals.jsonl` recorded nothing from this run.

---

## 4. FILES

    src/unmatched.py                  NEW. Registry, attribution, ledger,
                                      hourly digest. 1 new module, 1 new
                                      state file.
    src/notify.py                     UNMATCHED_DIGEST + route; POSTING and
                                      posting_for; MUST_NAME, names_its_object
                                      and the gate in plan(); thread_parent_ts;
                                      deliver() tier behaviour.
    src/providers/slack.py            pin(), which never raises.
    src/inbound.py                    the unmatched branch records instead of
                                      posting; the namespace bug removed from
                                      _positively_not_ours.
    src/replywatch.py                 sweep() flushes the digest after the poll.
    src/store.py                      UNMATCHED_LEDGER in STATE_OVERRIDES.
    scripts/notifications_replay.py   NEW. The dry replay. Posts nothing.
    tests/test_an_alert_names_its_object.py  NEW, 47 tests.
    tests/test_task238_attribution.py       the nine criteria, at their new
                                      address. None removed.
    tests/test_notify_wiring.py       the unmatched class asserts the ledger.

State: `work/unmatched-ledger.jsonl`, gitignored with everything else under
`work/`.

### 4.1 The ingest path gained no I/O

`unmatched.record()` writes what the event already carries and makes no
provider call. Attribution and the digest happen in `unmatched.flush()`, on
the reply watcher's own thread after the poll - so a lookup that hangs cannot
sit between a reply arriving and the cadence to that person stopping.
`inbound.handle` keeps the shape it had.

---

## 5. WHAT THE FIVE PARTS DID NOT ANTICIPATE

1. **The namespace bug (§1.2).** A silent drop of our own EmailBison replies,
   armed and waiting on a `provider_truth.py` run. This is the finding that
   most deserves a second reader.

2. **`GetCampaignsForLead` 404s on percent-encoded profile URLs.** A lead
   whose LinkedIn handle contains non-ASCII characters can never be
   attributed. It fails in the safe direction - the event is kept and
   digested - but it is a permanent unattributable class, not a transient
   error, and it is 2 of the 4 posts in the after-count. Worth a separate
   look at whether the id form (`linkedinId`) answers where the URL does not.

3. **The 33 B1 campaigns are not in `work/campaigns.jsonl`.** They exist only
   in the provider readback. Canonical campaign state does not name campaigns
   we are running, which is why §2.1 has to union a file that expires. The
   union makes today correct; the gap is still there.

4. **`bison.fetch_events` carries 11 event types, not 8.** Six are not in
   `bisonevents.TYPE_TO_KIND` and normalise to `unknown`:
   `BLACKLISTED_DOMAIN_ADDED` (38 in 72h), `EMAIL_ACCOUNT_ADDED` (11),
   `EMAIL_ACCOUNT_REMOVED` (11), `MANUAL_EMAIL_SENT` (5),
   `EMAIL_ACCOUNT_DISCONNECTED` (2), `BLACKLISTED_EMAIL_ADDED` (1).
   **`EMAIL_ACCOUNT_DISCONNECTED` is a sender mailbox that stopped working
   and nothing alerts on it.** Out of scope here; it belongs in
   PRODUCT-GAPS.md or a task of its own.

5. **63 events in 72 hours carry no campaign and no lead at all** - they are
   estate-level (blacklist entries, mailbox add/remove/disconnect). They are
   not unmatched replies and must not be filed as unattributable ones. They
   never reach this path today because they come from `/events` and the reply
   watcher reads `/replies`; naming it here so a future wiring of `/events`
   into ingest does not discover it the hard way.

6. **The ownership readback has been stale for 32 hours and nothing said so
   in the channel.** The staleness is what produced 84 of the 102 posts, by
   making the seat predicate refuse. A guard refusing is correct; expressing
   the refusal as eighty-four identical ACTION_REQUIRED posts instead of one
   saying "attribution is refusing, run `scripts/provider_truth.py`" is not.
   This change removes the eighty-four. **It does not add the one**, and it
   should: a distinct WARNING when `_owned()` refuses, once per stale period.

---

## 6. WHAT THIS DOES NOT DO

- **It deletes nothing in Slack.** The 102 posts stay.
- **It posted nothing while it was built or tested.** The replay points
  `NOTIFICATIONS` and `UNMATCHED_LEDGER` at a temporary directory before
  `src.notify` is imported, and `notify.deliver` is never called. All
  development happened in a git worktree, so the running loops - which import
  at start and never reload - were never reading a half-edited module.
- **It weakens no guard.** The seat drop is unchanged. Every fail-closed case
  in TASK-238 - a lookup that raises, a lookup that answers about nobody, an
  event with no campaign field - is still KEPT, and each has a test that
  fails if it stops being. The only new drop is `THEIRS`, which needs a
  campaign id that positively belongs to a campaign in no registry of ours,
  and which is written to the ledger with the reason.
- **It does not resolve the 98.** They are the client's traffic in a shared
  workspace. The correct outcome for them is a row in a file, not a message.

---

## 7. TEST RUN

    tests/test_an_alert_names_its_object.py        47 tests, green
    tests/test_task238_attribution.py              26 tests, green
    tests/test_notify*.py                          green
    tests/test_inbox.py                            green
    tests/test_ownership_readback_staleness.py     green
    tests/test_fixture_hygiene.py                  green
    tests/test_invariants.py                       green

Six mutations were applied and each was caught by the intended test and by
no other:

    remove the naming gate from plan()        -> the-102-posts test fails
    merge the two provider registries         -> the namespace test fails
    post a digest with zero rows              -> four aggregation tests fail
    digest the current hour                   -> the partial-hour test fails
    map WARNING to the daily thread           -> the demotion test fails
    return the whole address, not the domain  -> the no-mailbox test fails
    let an empty registry decide THEIRS       -> three drop tests fail

### 7.1 The whole suite, and what the difference is

`unittest discover` on this branch: **12,568 tests, 92 failures, 10 errors.**
That is a large pre-existing baseline plus this repository's known cross-test
contamination, and it is not useful on its own - so the 44 modules that
contained a failure were re-run in isolation on this branch and on the
production tree, and the two lists diffed:

    only on master   test_secrets::test_every_state_override_is_in_the_example
    only on branch   test_the_prototype_cannot_send::…refuses_before_it_imports…
                     test_review_may_not_reach_the_export::…refused_today
    everything else  identical, 84 failures on both

The one on master is FIXED here - see below. **Both of the two on this branch
are worktree artefacts, and each was proved to be one by supplying the file
it was missing**: the first wants `prototype/` built (`run build.py first`),
the second reads the REAL `work/candidates.jsonl` by design. With
production's copies of both in place, all 20 tests pass. This is
`docs/` folklore already: a worktree has its own empty `work/`.

`tests/test_replies.py::test_every_verdict_carries_its_evidence` fails on
this branch and identically on the production tree. It is `1481a747`'s
`RULE_HASH` and has nothing to do with this change.

### 7.2 A guard this change found red, and turned back on

`tests/test_secrets.py::test_every_state_override_is_in_the_example` asserts
that every name in `store.STATE_OVERRIDES` is documented in
`config/.env.example`. It has been red, so the next omission would have gone
unnoticed behind the existing ones. **Five were missing** and none of them
was this change's:

    QUEUE_DB  PROVIDER_WRITES_LEDGER  SLACK_FOLLOWUPS
    SUPERVISOR_LOCKS  SUPERVISOR_STATE

They are named now, in one commented block, alongside this change's own
`UNMATCHED_LEDGER`. That test is green again. The other failure in that file,
`test_no_tracked_file_contains_a_credential_shaped_assignment`
(`scripts/server/webhook_receiver.py`), is pre-existing and untouched.
