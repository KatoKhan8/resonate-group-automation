# What it would take to make a bounce reach the record

TASK 0090, lane `suppression`, 2026-10-15. Branch `task-suppression-2026-10-14`.
Every number below was measured on `acf078b72` in the worktree
`wt-suppression-2026-10-14` (a CRLF tree), except where it says otherwise.

**NOTHING HERE IS WIRED AND NOTHING WAS APPLIED.** No provider, Apify or
network call was made. Not one byte was written to production `work/`. The
poller checkpoint was not moved. `src/leadobserve.py`, `src/channels.py` and
`src/eligibility.py` are untouched. This is the measurement that lets the
operator choose; it is not the fix.

---

## 0. THE HEADLINE: IT IS FIVE BOUNCES, NOT THREE

`0070` found three bounced addresses and said they were the instance rather
than the population. They are. **The estate's own local state already holds
two more, and no snapshot this lane carries can see them.**

Read from the watcher heartbeats under the main checkout's
`work/heartbeat/bison-*.json`, written by the twenty
`scripts/bison_watch_loop.py` processes that poll EmailBison every 180 seconds.
Timestamps are the watchers' own, 2026-10-15T19:09:31Z to 19:12:26Z. **No
provider call was made to obtain this — the watchers had already paid for the
reads.**

    campaign   status      bounced   emails_sent   leads   queue_rows
    491        paused            1           411     333          665
    492        paused            1           245     206          409
    495        archived          1            42      60          114
    503        paused            2            25     250          500
    all other 16 watched                0

    TOTAL                             5       918   1,516        2,888

And the per-event sink agrees, with the moment each one happened
(`work/watch-events/bison-*.jsonl`):

    2026-09-22T15:29:12Z   BOUNCE 491 bounced 0 -> 1
    2026-09-22T15:36:47Z   BOUNCE 492 bounced 0 -> 1
    2026-09-22T20:48:12Z   BOUNCE 495 bounced 0 -> 1
    2026-09-25T12:32:20Z   BOUNCE 503 bounced 0 -> 1
    2026-09-25T12:54:34Z   BOUNCE 503 bounced 1 -> 2

**503's two are invisible to every snapshot in this lane.** This lane's
`PROVIDER-SUPPRESSION-SNAPSHOT-FULL.json` holds exactly three bounced emails —
the 491/492/495 people, each witnessed by three stage files — because its
sources' coverage ends 2026-09-24/09-30 and 503 is not among them. Measured
again today against that file: 3 of 749 snapshot emails, 3 of 1,381 joined
local contacts, and the whole observed status vocabulary is `bounced`,
`in_sequence`, `replied`, `scheduled`, `sending_paused`, `sent`,
`sequence_finished`, `stopped`.

**And the counter is a COUNT, not an identity.** The watcher reads the
campaign's own `bounced` field. It says 503 bounced twice; it does not say to
whom. Naming those two people is **UNKNOWN**, and the authority is one
EmailBison read of 503's scheduled-email queue (500 rows, 34 pages), which this
task may not make.

Zero `email_bounced` events exist on any record. `0070` measured the three
nameable ones: 12 / 3 / 3 events each, every one of them `draft_approved`, and
`channels.email_verdict` answering `(True, None)` — SENDABLE, no reason.

---

## 1. WHAT `confirm_email_touches` ACTUALLY NEEDS

    leadobserve.confirm_email_touches(campaign_id, recs=None, live=False)
                                      src/leadobserve.py:579

**Reads.** One provider surface and one local file.

* `scheduled_rows(campaign_id)` (`:416`) → `bison.scheduled_emails(campaign_id)`
  (`src/providers/bison.py:1648`) → **`GET /api/campaigns/{id}/scheduled-emails`**,
  page-paginated. `per_page` is ignored by this route by measurement, so the
  page size is the provider's: **15 rows per page**, from the recorded
  measurement of 491 at 647 rows across 44 pages.
* `store.load()` — the whole production queue, 27,071,294 bytes.

**Writes, only with `live=True`.** One `store.transaction()` **per recorded
event** (`:653`), each a full load-and-save of that 27 MB file.

**Cost per run.** `ceil(rows / 15)` GETs per campaign, and nothing per lead —
the call is per campaign. Across the twenty watched campaigns, 2,888 queue rows
is **193 GETs** for one full sweep.

**AND IT CANNOT READ THE LARGEST CAMPAIGN TODAY.** `scheduled_rows` calls
`bison.scheduled_emails(campaign_id)` with **no `cap`**, so it takes the
default `PAGE_CAP = 40`. 491's queue is 665 rows = **45 pages**, so
`_paged` raises `PartialInventory` — correctly, and fatally for this caller.
`scripts/bison_watch_loop.py` passes `cap=bison.CAMPAIGN_QUEUE_PAGE_CAP`, which
is 400. So the function named as the bounce producer **refuses the one campaign
holding one of the five bounces**, while the loop beside it reads that same
queue every 180 seconds without difficulty. 503 (34 pages), 504 (30), 505 (29)
and 492 (28) are all under the cap today.

**AND IT IS NOT A BOUNCE PRODUCER.** `EVENT_FOR` (`:383`) maps three states:

    sent     -> events.PUSH_MARKED              a CONFIRMED TOUCH
    bounced  -> events.EMAIL_BOUNCED            the thing we want
    stopped  -> events.PROVIDER_STOP_CONFIRMED  REFUSED by construction, because
                                                it is not in events.KNOWN

Measured today on the test fixture: a queue row reading `sent` makes
`confirm_email_touches(..., live=True)` write **`push_marked`** and nothing
else. So wiring this function is not "record bounces" — see §5.

---

## 2. WHERE A CALLER WOULD HAVE TO SIT

| host | runs today | sees | extra provider cost | verdict |
|---|---|---|---|---|
| **`scripts/bison_watch_loop.py`** | **YES — 20 processes, one per campaign, every 180s. Measured live 2026-10-15 (PIDs 31956…25100)** | the 20 campaigns it is launched with, each at `cap=400` | **ZERO. It already calls `bison.scheduled_emails` and has the rows in hand** | the only candidate that costs nothing |
| `scripts/reply_watch_loop.py` → `poller.run` | **YES — every 300s, PID 29528, since 2026-09-20T12:23:34Z** | `GET /api/replies`, all campaigns | zero extra | **wrong surface — see §3** |
| `src/replywatch` daemon thread | only in the deployed Railway service, and its own docstring says that service is not what drives these campaigns | `/api/replies` | zero extra | same wrong surface |
| a new scheduled run / cron | nothing exists | whatever it is told | 193 GETs per sweep | a new moving part for a read already being paid for |
| the resume path | refuses — killswitch, `sending.live` false, 0 of 3,005 approvals valid | the campaign being resumed | — | **wrong time.** A bounce must be recorded while the campaigns are paused, not at the moment somebody tries to send again |

**THE COVERAGE TRAP, NAMED.** `bison_watch_loop` watches **20 of the estate's
40** campaigns. A producer hosted there records bounces for those twenty and
for nobody else, and a report that said "bounces are recorded" would be the
same defect one layer up — exactly what this task was written to avoid. It is
tolerable only if it is stated: the twenty watched are 451, 481, 484, 485, 487,
489, 491–498, 500, 501, 503, 504, 505, 506 — which is every campaign of ours
that has ever sent. The four internal campaigns (274, 327, 328, 352) and 418
are **not** watched, and under CLAUDE.md rule 1 their bounces belong in the
local suppression ledger too. That gap would remain open and must be written
down, not inferred.

**THE PRECEDENT IS IN THAT FILE ALREADY.** The blank-content scan runs inside
`bison_watch_loop`'s cycle, and its own comment says why: *"It runs HERE because
`snapshot` has already paid for the queue read, so the check costs no extra
provider call — which is what makes 'every cycle' affordable rather than
aspirational."* A bounce recorder is the same shape, on the same rows, in the
same loop.

---

## 3. THE OTHER PRODUCER, AND WHY IT DOES NOT CLOSE THE GAP

Both halves confirmed.

### Replies and lead status really are different surfaces

Three routes, three shapes, three readers, and no overlap:

| route | pagination | reader | bounce signal |
|---|---|---|---|
| `GET /api/replies` | cursor (`pagination_type=cursor`, `per_page` ≤ 100) | `adapters.from_emailbison` → `bison.classify_reply_row` | `type` ∈ (`bounced`, `bounce`) or `folder == "bounced"` |
| `GET /api/campaigns/{id}/scheduled-emails` | page | `leadobserve.scheduled_rows` | `status == "bounced"` |
| `GET /api/events` | cursor, **10-day retention** | `bisonevents.normalise` | `payload.event.type == "EMAIL_BOUNCED"` |

`bisonevents.normalise` also has **zero production callers** — `scripts/glm_review.py`
and tests only.

### Moving that checkpoint back would recover NOTHING for bounces

This is measured, not argued. **`scripts/reply_watch_loop.py` was live through
every one of the five bounces.** Its own sink
(`work/watch-events/replies.jsonl`, 45 lines, first 2026-09-20T12:23:34Z, last
2026-10-11T22:23:30Z) records **26 REPLY ingests, 3 POLL-ERRORs, 1
STOP-REFUSED, and not one bounce** — including:

    2026-09-22  15:15:36  15:21:04  15:26:28  16:03:59   around 491 at 15:29:12
                                                          and 492 at 15:36:47
    2026-09-22  20:50:52                                  around 495 at 20:48:12
    2026-09-25  12:24:12  13:25:08                        around 503's 12:32:20
                                                          and 12:54:34

The poller was reading `/api/replies` minutes either side of every bounce,
ingesting other events successfully the whole time, and `0070` measured zero
`EMAIL_BOUNCED` on the three records. **So `/api/replies` is not where this
estate's bounces appear, and rewinding a cursor over a feed that never carried
them recovers nothing.**

What rewinding *would* recover is replies, and only those older than the
current mark. The reply watcher has covered the estate continuously since
2026-09-20, which predates the first send from 491–498 (2026-09-22 13:02–14:13Z).
**So: nothing. The reset is not worth a provider call.**

**The checkpoint has also already moved since `0070` measured it.** Read
read-only from the main checkout's `work/checkpoints.json`
(sha256 `e7d6edd9ade13632fb395fb7…`, 424 bytes):

    emailbison          at 2026-08-26T19:01:25+00:00   an opaque base64 cursor — a legacy slot
    emailbison:ws10     at 2026-10-15T18:30:18+00:00   cursor 2026-10-15T18:30:10.000000Z
    heyreach            at 2026-10-15T19:10:53+00:00

`poll_emailbison` stores a **high-water mark, not a provider cursor**, and sets
it to the newest row actually seen — so it advances only on real rows and the
feed is alive and current. `0070`'s `2026-10-14T08:30:56` was a true reading of
a mark that moves every few minutes. Nothing is "past the backlog"; there is no
backlog.

### And one defect to know about before anybody wires the replies path for bounces

`adapters.from_emailbison` sets `email=row["from_email_address"]`. On a bounce
row that is the **bouncing MTA**, not the prospect. Attribution would then rest
entirely on `lead.custom_variables` — the nesting that was broken until
2026-09-25 and whose presence on a bounce row has never been observed. The
address fallback in `events.match_record` would match nothing, or the wrong
thing.

---

## 4. WHAT A BOUNCE LOOKS LIKE AT THE PROVIDER

From the code and the fixtures only. No probe was made.

**The queue surface — where our five actually are.**
`leadobserve.EMAIL_STATES` is `(scheduled, sent, bounced, stopped)`.
`_email_state` lowercases and trims, and folds **anything else** to
`email_state_unknown`, which carries no canonical event and is reported as
`waiting` — *"nothing has happened to anybody"*.

**The replies surface.** `BOUNCE_TYPES = ("bounced", "bounce")`,
`folder == "bounced"`, or webhook `event` ∈ `WEBHOOK_BOUNCE = ("bounced", "bounce")`.

**The events surface.** `EMAIL_BOUNCED`, 15 of 1,200 real events walked
2026-09-17 — and separately **`EMAIL_SEND_FAILED`, also 15**, which
`bisonevents.TYPE_TO_KIND` maps to `send_failed` and which maps to **no
canonical event at all**. `data.reply` is present only on `LEAD_REPLIED` and
`EMAIL_BOUNCED`.

### SOFT AND HARD ARE NOT DISTINGUISHABLE IN ANYTHING WE WOULD READ

**No surface in this repository carries a bounce code, class, SMTP status or
reason field in any shape that has been measured.** One word, `bounced`, on all
three routes.

`hard_bounced` and `soft_bounced` exist only in two of **our own** allowlists —
`src/suppression.py:409-410` (`PROVIDER_STOPPED`) and
`scripts/reengagement_provider_confirmed.py:109` (`BOUNCE_STATES`) — and the
2026-10-15 snapshot's entire observed status vocabulary contains neither. They
are words this repository decided were bounces, not words the provider has been
seen to use.

So the operator is choosing between two errors and should know which:

* **The gate will OVER-suppress.** One bounce, whatever caused it, closes that
  address permanently. A transient 4xx deferral from a full mailbox and a dead
  address are the same word, and `channels._bounced` has no decay and no
  threshold. This is the direction the gate is *designed* to fail in, and it is
  the safer one — the cost of writing again to a dead address lands on the whole
  sending domain, and the cost of this error lands on one prospect.
* **And the queue reader will UNDER-suppress** the day the provider changes the
  word. Three of the four words this estate itself declares to be a bounce —
  `bounce`, `hard_bounced`, `soft_bounced` — fold to `email_state_unknown` and
  come back as `waiting`. A vocabulary change would present as "nothing
  happened" and the address would stay sendable. This is the second red test.

---

## 5. THE BLAST RADIUS OF TURNING IT ON

### The bounce side is small, and two of it cannot be named

* **5 records at most. 3 nameable.** The three are `0070`'s fingerprints
  `d13e93d5…` (lead 204562, c495), `f38022b4…` (lead 204472, c492) and
  `0a5148a3…` (lead 204668, c491). All three read `ours=allow`, state
  `verified`, `0` overlap with the canary 25 and with the 90 applied today, in
  both directions. 503's two are a counter and are **UNKNOWN**.
* Against the snapshot: **3 of 1,381** joined contacts, **3 of 749** snapshot
  emails. No cohort that could ship today contains any of them.
* 491's bounce is unreachable by `confirm_email_touches` at its default cap
  (§1), so the function as written would deliver **2 of the 3 nameable**.

### What else reads `EMAIL_BOUNCED`, and what changes

| reader | effect of the event appearing |
|---|---|
| `channels._bounced` → `eligibility.BLOCKED_BOUNCED` | **the point.** That address stops being sendable |
| `nextaction._bounced_channels` | closes email for that identity; if it was the only open channel, `WAIT_NO_CHANNEL` |
| `account.bounces` | a projection gains rows; `nextaction` is its consumer |
| `cadencesafety` | `BOUNCED` is in **`CONTEXT`, deliberately not `HARM`** — no harm rate moves and there is no halt on it |
| `report.py` `bounced` / `outcomes` BOUNCED stage | 0 → 5. Two reports stop saying zero |
| `stoppedcause.BOUNCED` | reads the provider feeds, not `rec["events"]`. Unaffected |
| any cap or volume gate | **none.** `touch.CONFIRMING_EVENTS` excludes `EMAIL_BOUNCED` **by name**, so it adds no confirmed touch and moves no counter |

**No cohort builder and no cap changes behaviour as a side effect of the bounce
event itself.**

### THE REAL BLAST RADIUS IS NOT THE BOUNCE — IT IS THE 918 TOUCHES

Wiring `confirm_email_touches` **whole** also writes `events.PUSH_MARKED` for
every queue row reading `sent`. That is **918 sends** across the twenty watched
campaigns, against the **one** confirmed touch currently recorded in 1,582
records. Proven on the fixture rather than inferred: a `sent` row produced
`push_marked` and nothing else.

`PUSH_MARKED` **is** in `touch.CONFIRMING_EVENTS`, and
`fatigue.contact_check` counts confirmed touches against
`contact.max_touches_total = 12` and `contact.max_touches_per_week = 3`,
consulted by `src/executionguard.py:630` and `src/nextaction.py:558`. So
hundreds of contacts would move from *"no confirmed touch to this contact yet"*
to a real count overnight, and some would start being held.

It fails in the **safe** direction — more holds, never fewer. But it is a large
and silent change to who may be contacted, and **it is not what the operator
would be approving if he approved "record bounces".** Two further notes:
`eligibility._separation` reads `entry["day"]`, which this writer does not set,
so that gate sees nothing; and `providerwrites._record_confirmed_touch` is
already the forward-going writer of `PUSH_MARKED`, so this half is duplicative
for new sends and a **backfill** for old ones. A backfill is a decision with its
own evidence, not a side effect.

---

## THE PLAN, IN ORDER

**STEP 1 — THE SMALLEST HONEST FIRST STEP. A bounce-only recorder inside
`bison_watch_loop`'s existing cycle.**

On the rows `snapshot()` already holds, writing **only** `EMAIL_BOUNCED`, keyed
to the contact, never a touch and never a stop.

* **Cost: zero additional provider calls.** One `store.transaction()` per NEW
  bounce — 5 today, then approximately none per week while nothing is sending.
* **It sidesteps the 491 problem entirely**, because the loop reads that queue
  at `cap=400` rather than at `scheduled_rows`' 40.
* **What it breaks: nothing measured.** 5 records gain the event, 3–5 addresses
  stop being sendable, two reports move off zero, `nextaction` closes email for
  those identities. No cap, no cohort, no harm rate, no halt.
* **What it does not cover, and this must be written down rather than
  inferred:** the 20 campaigns outside the loop, including all four internal
  ones, whose bounces CLAUDE.md rule 1 also wants in the local ledger.
* The born-red test for it is already committed:
  `tests/test_a_provider_bounce_reaches_the_record.py`.

**STEP 2 — give `scheduled_rows` a `cap`,** so `confirm_email_touches` can read
491 at all. Three lines in `src/leadobserve.py`; a `src/` change, so it owes a
new full suite reference.

**STEP 3 — decide the touch backfill separately,** with the fatigue impact
measured first: how many contacts cross `max_touches_total` and
`max_touches_per_week` once 918 confirmed touches exist. That measurement needs
only the queue and the heartbeats, no provider call, and it should be a task of
its own.

**STEP 4 — the vocabulary.** Either add `bounce`, `hard_bounced` and
`soft_bounced` to `EMAIL_STATES`, or make an unrecognised bounce-shaped status a
**loud refusal** instead of `waiting`. Today it is silent, and silence on this
path reads as "nothing happened".

**STEP 5 — name 503's two bounced leads.** Needs one EmailBison read of 503's
queue. Operator's call; it is a read, not a write.

---

## THE ONE THING THE OPERATOR HAS TO DECIDE FIRST

> **May a single provider-reported bounce close that address permanently,
> knowing that EmailBison gives us no way to tell a hard bounce from a soft one
> — so one transient deferral would close a good address forever? YES, or NO
> with the number of bounces that should.**

Everything above waits on that one line, because it is the only question whose
answer changes the design rather than the schedule. Recommendation: **YES.** The
cost of the error lands on one prospect; the cost of the opposite error lands on
the sending reputation of the whole estate, and `0070` already showed that this
gate has been returning SENDABLE for addresses the provider has already
rejected.

## AND THE THREE ARE UNCHANGED

`0070`'s recommendation — add the three bounced addresses to the local agency
DNC with reason `bounced` — **stands exactly as written and is strengthened**:
the DNC is still the only barrier that does not depend on a feed nobody runs,
and the population is now 5 rather than 3 with two of them unnameable without a
provider read. Nothing here was applied to them.
