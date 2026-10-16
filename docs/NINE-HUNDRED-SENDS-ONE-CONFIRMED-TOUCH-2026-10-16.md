# 918 sends against one confirmed touch — TASK-0180, 2026-10-16

Measured in `wt-suppression-2026-10-14` on branch
`task-suppression-bounce-RULE-2026-10-15` at **`045babe5f`**. `origin/master`
is **`b1f290c84`**, unchanged. No provider call, no network call, no send, no
activation, nothing prospect-facing, no cap or gate change. **Nothing was
wired** — §3 and §4 are proposals, as the brief requires. `src/providers/*`
was not read; where an answer needed it, that is said by filename.

---

## 0. THE PREMISE IS HALF WRONG, AND THE CORRECTION MATTERS

0130 recorded, and this brief repeats:

> `confirm_email_touches` still has no production caller.

**It has one.** Measured by reading the call chain at `045babe5f`:

    scripts/bison_watch_loop.py:643   on_queue = _bounce_recorder(watched, emit)
    scripts/bison_watch_loop.py:647   snapshot(watched, on_queue=on_queue)
    scripts/bison_watch_loop.py:598   leadobserve.record_bounces(provider_id,
                                          queue=queue, live=True)
    src/leadobserve.py:789            confirm_email_touches(..., live=live,
                                          event_for=policy,
                                          rows=[r for r in rows
                                                if r["state"] == BOUNCED])

So `confirm_email_touches` **runs in production, live, on every watcher
cycle** — with its rows narrowed to bounces before the writer is reached.
That narrowing is 0120's step 1, and it landed.

**What has no caller is the UNFILTERED form** — the `sent → PUSH_MARKED` half.
And it is not unwired by neglect: the filter is a list comprehension that runs
*before* `events.record` is reached, so the exclusion is structural rather
than a branch, and `record_bounces`' own docstring states the reason. The
distinction is worth keeping straight, because "nobody calls it" invites
somebody to wire it, and wiring it whole is the one thing the record says not
to do.

---

## 1. THE NUMBERS, AND WHAT EACH CONSUMER ACTUALLY READS

### 1a. 918 against 1 is NOT re-derivable in this tree, and the two recorded figures disagree

Both halves of the figure rest on production `work/` state, which this task
may not read, and which **does not exist in this worktree** — `work/` here
holds three small files and no `queue.jsonl`, no `heartbeat/`, no
`action-ledger.jsonl`.

The committed provider truth cannot stand in for it:
`docs/state/PROVIDER-CAMPAIGNS.json`, `generated_at 2026-09-30T20:40:42Z`,
carries 40 EmailBison campaign rows whose only numeric field is `lead_count`.
**It has no send counts at all.** Re-derived: the sum of sends across the ten
campaigns in `bounce_stop_7day.OURS` from that file is **0, because the field
is absent** — not because nothing was sent.

What the repository does record, with its sources, and the two do not agree:

| figure | where | window |
| --- | --- | --- |
| **918 sends** against **1** confirmed touch in 1,582 records | `src/leadobserve.py:762`, `docs/SUPPRESSION-WHAT-IT-TAKES-TO-RECORD-A-BOUNCE-2026-10-15.md:288`, re-stated in three later docs | "the twenty watched campaigns", measured 2026-10-15 from the watcher's heartbeats |
| **912 sends** against **1** recorded touch in 1,582 records | `CLAUDE.md:105`, `docs/PRODUCTION-HANDOFF-2026-09-28-NIGHT-MINIMUM-CLAUDE.md:140`, `docs/qwen-tasks/TODO/TASK-935`, `docs/SUPPRESSION-THE-BOUNCE-RULE-2026-10-15.md:123` ("~912") | "across our campaigns", measured 2026-09-28 |

**Both are provider-side send counts, taken 17 days apart, and neither is
dated inside its own sentence.** The gap of 6 is consistent with sending
having stopped: our campaigns were paused by hand on 2026-09-28, so a count
taken on 09-28 and one taken on 10-15 *should* be nearly equal, and 912 → 918
is nearly equal. **So the two figures are probably the same quantity at two
moments, not a contradiction** — but nothing in either sentence says so, and a
reader meeting them in two files has no way to tell that from a disagreement.

**The window the figure covers is itself UNKNOWN in both cases.** Neither
records a start date. The upper bound is the lifetime of the twenty campaigns;
the useful lower bound is that our ten were all paused on 2026-09-28, so no
send in either figure is newer than that.

**What would settle it:** `py -3 scripts/bounce_stop_7day.py --days 365 --json`
against the live workspace counts `sent` and `bounced` rows per mailbox with
the provider's own timestamps, so it produces both the number and its window
in one read. It is the same read TASK-0160 §6 asks for, at a wider `--days`.

**For this report the figure is quoted and not re-derived, and that is stated
rather than papered over.** The analysis below does not depend on whether the
number is 912 or 918; it depends on the ratio being three orders of magnitude,
which both figures agree on.

### 1b. The consumer audit: attempts, confirmations, or neither

This is the part that is fully answerable from code, and it is the useful half
of §1.

| consumer | what it reads | attempts / confirmations | verdict |
| --- | --- | --- | --- |
| **the cooling rule** — `suppression.decide` | `provider_touches` when the caller supplies it; otherwise it refuses | **provider confirmations, or HOLD** | **correct.** `UNKNOWN_IS_NOT_A_PASS` is True and absent touch history is `HOLD_TOUCH_HISTORY_UNKNOWN`. It reads `account.touches(confirmed_only=True)` only to populate a `detail` field, never to decide |
| **the bounce rate** — `scripts/bounce_stop_7day.py`, `scripts/hard_stop_check.py` | the provider's own queue rows, `status ∈ {sent, bounced}` | **provider confirmations** | **correct**, and the only two places in the estate where "sent" means a message left a mailbox |
| **the per-mailbox daily volume** — `executionguard` gate, `actionledger.count_on(sender_id=…)` | the action ledger, default states `(SENT, ATTEMPTED, UNRESOLVED)` | **attempts, deliberately** | **correct, and documented as such**: *"a cap that only counted confirmed sends would let an unresolved attempt buy another attempt, which is precisely the hazard."* Counting attempts is the fail-closed direction for a cap |
| **the sender headroom** — `src/senderheadroom.py` | the forward book: the provider's own `scheduled_date` rows | **neither — the provider's PLAN** | **correct, and the third category.** Its docstring already says the limit is enforced at sending and not at booking, that client campaign 352 books 16 rows on a limit of 15, and that an overbooked day sheds rows and *which* row sheds is UNKNOWN |
| **"was it delivered"** — `report.py:97`, `report.py:134`, `outcomes.py:296,879`, `slackagentreadback.py:397`, `bouncepolicy.ACCEPTANCE_EVENTS` | `events.EMAIL_DELIVERED` | **nothing** | **BROKEN BY ABSENCE — see 1c** |

### 1c. THE FINDINGS, WITH NAMES

**FINDING 1 — `delivered` has no producer, so every delivery figure in this
product is structurally zero.**

`src/adapters.py:172`, `emailbison_delivered`, says it in its own docstring:

> Delivery events, if this instance is ever wired to report them. **Nothing on
> the confirmed surface emits these**: `/replies` carries replies, bounces and
> our own sends. Kept so a webhook that does carry them has a home.

Five consumers read `events.EMAIL_DELIVERED`. None of them can ever see one on
this provider, and **a zero from them is indistinguishable from "nothing was
delivered"** — the exact shape of the evaluator that reported
`INSUFFICIENT_DATA` forever because nothing wrote the field it read.
`from_emailbison` has a `kind == "delivered"` branch fed by
`bison.classify_reply_row`; whether that classifier can ever return
`"delivered"` is in `src/providers/bison.py`, which this task may not read, so
that one link is **UNVERIFIED-BY-BOUNDARY**. The adapter's own docstring is
the authority quoted above and it says no.

**Consequence nobody has written down:** `bouncepolicy.ACCEPTANCE_EVENTS =
(EMAIL_DELIVERED, REPLY_RECEIVED)`, and its docstring says *"Not
`PUSH_MARKED`"* on purpose. So the soft-bounce counter's reset condition —
"this address has accepted mail since" — can only ever be satisfied by a
**reply**. Half of that gate is dead, and it fails in the safe direction
(soft bounces accumulate and close an address sooner), which is why nothing
has noticed.

**FINDING 2 — the forward-going writer records an ENROLMENT under the
vocabulary of a SEND.**

`providerwrites.py:2633` calls `_record_confirmed_touch(authorization)` for
every `facing` write that is ACCEPTED. It writes `events.PUSH_MARKED`.
`touch.CONFIRMING_EVENTS[PUSH_MARKED] = SENT`, and `touch.WORDS[SENT] =
"confirmed sent"`.

The facing EmailBison verb is `EMAIL_ADD_LEAD = "bison.add_lead"`, and the
table entry describes exactly what it does: create a lead, then
`POST /api/campaigns/{id}/leads/attach-leads`. **That is an attachment, not a
send.** CLAUDE.md states the rule in four words — *"Enrolled is not sent"* —
and `senderheadroom` exists because the day the message actually goes is a
property of the mailbox, decided later.

So an accepted attach writes an event the vocabulary reads as *confirmed
sent*. This is **deliberate and correct for fatigue**, and the call site says
why:

> A touch recorded for an action that did not happen costs one refusal. A
> missing touch costs a second message to a real person.

Over-counting touches makes `fatigue.contact_check` hold more people, which is
the safe direction. **It is not safe for anything that asks whether a message
went out**, and it is read by `touch.state_of`, `touch.WORDS`, `report`,
`outcomes` and `nextaction`. The defect is not the write; it is that
`touch.SENT` carries two facts — *we asked* and *it went* — with one word, and
the state vocabulary (`PLANNED, APPROVED, PAYLOAD_READY, SENT, DELIVERED,
REPLIED, POSITIVE_REPLY`) **has no word for "enrolled, not yet sent"**, which
is the state most of the estate is actually in.

**FINDING 3 — the same word, three meanings, in three layers.**

    actionledger.SENT     "provider confirmed, and a read-back agreed"
                          -> for bison.add_lead, confirms an ATTACH
    touch.SENT            "confirmed sent"
                          -> written on the same attach
    provider row status   `sent`
                          -> the only one that means a message left a mailbox,
                             and read by exactly two scripts

Three layers, one word, three referents. The two scripts that read the
provider's own field are the bounce stop and the hard-stop check, which is
also the pair TASK-0160 just put on a schedule — so the honest end of this
chain is now the only end that runs.

---

## 2. WHY NOTHING CALLS THE UNFILTERED FORM, AND WHAT A REAL LOOP WOULD COST

### 2a. What it would need to run

`confirm_email_touches(campaign_id, recs=None, live=False, rows=None,
event_for=None)` needs:

- **the provider read**: `scheduled_rows(campaign_id)`, which is
  `bison.scheduled_emails` with **no cap**, so it takes `bison.PAGE_CAP = 40`
  and refuses any queue past 600 rows. Campaign 491 is **665 rows / 45 pages**,
  so `confirm_email_touches` **cannot read 491 at all today**. That is
  0120's step 2, still unlanded: three lines to give `scheduled_rows` a `cap`.
- **the queue**: `store.load()`, to match a provider row to a record and
  contact through `match_scheduled`.
- **a cadence**: none of its own. It is a function, and the only question is
  whose cycle it rides.

### 2b. Why it was never wired — the record is NOT silent, and it is quoted

`src/leadobserve.py:757-767`, in `record_bounces`' own docstring:

> `EVENT_FOR` also maps `sent -> PUSH_MARKED`, and `PUSH_MARKED` is in
> `touch.CONFIRMING_EVENTS`, which `fatigue.contact_check` counts against
> `max_touches_total` and `max_touches_per_week`. Measured 2026-10-15: the
> twenty watched EmailBison campaigns carry 918 sends against ONE confirmed
> touch in 1,582 records. Wiring the whole of `confirm_email_touches` into a
> loop would therefore write 918 touches and **silently change who may be
> contacted — a decision nobody has taken, made by accident, under cover of
> "record bounces"**.

and `docs/SUPPRESSION-WHAT-IT-TAKES-TO-RECORD-A-BOUNCE-2026-10-15.md:292-306`
adds the blast radius: `contact.max_touches_total = 12`,
`contact.max_touches_per_week = 3`, consulted at `executionguard.py:630` and
`nextaction.py:558`, so *"hundreds of contacts would move from 'no confirmed
touch to this contact yet' to a real count overnight, and some would start
being held."* It fails safe — more holds, never fewer — and it is still a large
silent change to who may be contacted.

**So the record is explicit: it was not wired because wiring it whole is a
backfill of 918 touches disguised as a reconciliation, and a backfill is a
decision with its own evidence.** Nothing here is a guess.

### 2c. The cost, derived

From `docs/state/QUEUE-COUNTS-2026-10-15.json` through `queuewall.assess`,
`measured_at 2026-10-15T21:58:00Z`, `bison.PAGE_SIZE = 15`:

    all 20 watched campaigns   2,888 rows   202 pages   205 requests a pass
    our ten                    1,495 rows   105 pages   105 requests a pass
    the largest (491)            665 rows    45 pages

An empty queue still costs one request, which is why requests exceed pages.

| design | requests per day |
| --- | --- |
| a standalone loop, our ten, **hourly** | 105 × 24 = **2,520** |
| a standalone loop, all twenty, hourly | 205 × 24 = **4,920** |
| a standalone loop at the watcher's own 180s | 205 × 480 = **98,400** |
| **riding `bison_watch_loop`'s existing cycle** | **0 additional** — the rows are already in hand, which is exactly how `record_bounces` runs today |
| canary volume: 1 campaign, 23 leads, ~1.9 rows/lead ≈ 46 rows ≈ 4 pages, hourly | 4 × 24 = **96** |

**That table is the result, and it changes the design rather than the
schedule.** A standalone confirmation loop at estate scale is between
unreasonable and absurd — 98,400 requests a day to re-learn facts the watcher
already has in memory. At canary scale it is 96 requests a day and could not
matter less. And the middle column makes the choice for us: **there is no
reason to build a loop at all, because the one that would hold the rows is
already running.**

---

## 3. THE PROPOSAL — AND THE FAIL-CLOSED CASE IS THE WHOLE DESIGN

**Nothing below was wired. No provider call was made.**

### 3a. Where it would run

Inside `bison_watch_loop`'s existing `on_queue` hook, beside
`_bounce_recorder`, on the rows `snapshot()` already holds. Zero additional
provider reads. The pattern is proven: that is how the bounce half runs today.

Not a new loop, and not `src/supervisor.py`'s table. A second process reading
the same queues would pay 205 requests a pass to learn what the first already
knows, and two writers of one canonical fact is the drift this repository
keeps naming.

### 3b. What it would write — and the vocabulary comes first

**The vocabulary change is a precondition, not a follow-up.** Writing
`PUSH_MARKED` for a provider `sent` row is correct; the problem is that the
same event is already written for an *attach*, so the two become
indistinguishable the moment both exist. Today they cannot be told apart at
all, and a backfill would make that permanent across 918 rows.

The proposal is therefore, in order:

1. **Split the state.** Add a `touch` state between `PAYLOAD_READY` and
   `SENT` — `ENROLLED`, "attached to a campaign, not yet sent" — and map
   `PUSH_MARKED` to it. Introduce `events.EMAIL_SENT_CONFIRMED` for a
   provider `sent` row and map **that** to `touch.SENT`.
   - `touch.CONFIRMING_EVENTS` keeps `PUSH_MARKED`, so **fatigue behaviour
     does not change** — the conservative over-count that protects a real
     person stays exactly as it is.
   - `touch.WORDS` stops printing "confirmed sent" for an enrolment, and
     `report`, `outcomes` and `nextaction` gain a figure that means what its
     label says.
   - This is a `src/` change to the event vocabulary and owes a full suite
     reference. It is the largest piece and it is the one everything else
     depends on.
2. **Then** write `EMAIL_SENT_CONFIRMED` from the watcher's rows, narrowed to
   `state == SENT` the same way bounces are narrowed — a list comprehension
   before the writer, so the property is structural.
3. **Then** decide the backfill of the 918 separately, with
   `confirm_email_touches(live=False)` run first and its `recorded` count read
   as the measurement.

### 3c. What happens when a confirmation never arrives — the interesting case

This is the question the brief says is the design, and the answer has to be
stated for three distinct absences, because they are three different facts and
collapsing them is how a rate goes green on nothing.

| the state | what it means | what the proposal does |
| --- | --- | --- |
| **row still `scheduled`** | the mailbox has not reached this message yet | `confirm_email_touches` already answers `waiting` and writes nothing. A `waiting` row is **not** a send and **not** a failure. Keep |
| **row has a status this estate's `EMAIL_STATES` does not know** | the provider said something we have no word for | today this falls into `waiting` **silently**, which reads as "nothing happened". The proposal makes it a **loud refusal** — 0120's step 4 — because an unrecognised status on a send path is a finding, not a wait |
| **the row disappeared, or the campaign cannot be read** | the authority is gone | **the touch stays absent and the ABSENCE IS RECORDED.** Nothing is inferred from a missing row. This is the case a careless implementation turns into "sent", and the refusal contract is `senderheadroom`'s: a count that reaches the limit proves FULL on any walk; a count below it proves nothing unless the walk was complete. Applied here: **a `sent` row proves a send; the absence of a `sent` row proves nothing at all** |

**How a reader tells "not confirmed yet" from "confirmed not sent".** They are
different rows, not a missing row:

    ENROLLED, no EMAIL_SENT_CONFIRMED, row still `scheduled`
        -> "not confirmed yet". Expected, and dated: the row carries
           `scheduled_at`, so a reader can see it is three days overdue
    ENROLLED, EMAIL_BOUNCED                       -> confirmed NOT delivered
    ENROLLED, row `stopped`                       -> confirmed not sent, by a stop
    ENROLLED, campaign unreadable                 -> UNKNOWN, named, never either

And the fail-closed rule stated plainly, because the brief asks for it
explicitly: **an unconfirmed send is never counted as sent.** No rate, report,
denominator or cap in this proposal reads an enrolment as a send. Where a
figure cannot be computed because a confirmation has not arrived, the figure
is UNDEFINED and prints as UNDEFINED — the same word, and the same rule,
`bounce_stop_7day` already enforces: *UNDEFINED is not 0% and it is not a
pass.*

---

## 4. THE SMALLEST HONEST THING — AND IT IS NOT A BUILD

**For a 23-contact canary, nothing in §3 is worth building first, and the
reason is not that 23 is small. It is that the instrument already exists, is
already dry by default, and will answer the only question the canary actually
asks.**

`src/leadobserve.py` has a CLI, and `--confirm` without `--live` writes
nothing:

    py -3 -m src.leadobserve --provider emailbison --campaign <id> --confirm
    py -3 -m src.leadobserve --provider emailbison --campaign <id> --confirm --json

It prints `recorded / already / waiting / refused / unmatched` and appends
`(DRY - pass --live to write)`. For the canary's one campaign that is **four
provider page reads**, no write, no credit, and the four counts are exactly
"how many of my 23 went out, how many are still queued, how many could not be
placed".

### Checking 23 by hand, in commands

In order, from the main checkout, after the canary has been attached and has
had a sending window:

    # 1. what the provider says happened, per row. 4 pages, no write.
    py -3 -m src.leadobserve --provider emailbison --campaign <id> --confirm --json

    # 2. the same question as a per-mailbox bounce rate, with its own window
    #    and its own BLIND verdict. Now on a schedule - TASK-0160.
    py -3 scripts/bounce_stop_7day.py --days 7
    py -3 scripts/stop_watchdog_loop.py --status

    # 3. whether anybody should not have been contacted at all, per contact,
    #    per rule - TASK-0170. 14 of 22 rules answer on the main checkout.
    py -3 scripts/canary_preflight.py --cohort <cohort.json>

    # 4. the one thing none of the above can answer
    #    - see below -

Step 1 reads `recorded` as **"the provider says these went out and the record
does not know"**. For 23 contacts that number is checkable by eye against the
approval sheet's 23 rows. If it is 23, every message went. If it is 7, sixteen
did not, and `waiting` says whether they are queued or lost.

**What this tells the operator:** whether each of the 23 messages left a
mailbox, when, from which sender, and which of them bounced.

**What it does NOT tell him, and nothing in this product can:**

- **whether any of the 23 was DELIVERED.** `EMAIL_DELIVERED` has no producer
  (§1c finding 1). A non-bounced `sent` row is the best evidence this estate
  can produce, and it is evidence of *dispatch*, not of arrival.
- **whether a `sent` row is a real send or an attach.** For rows produced by
  the provider it is a real send. For anything our own writer recorded it is
  an attach (§1c finding 2), and until the state is split the two cannot be
  told apart in the local ledger. **Step 1 reads the provider and so is not
  affected** — which is precisely why it is the recommended check and the
  local ledger is not.
- **the window the 918 covers.** Still UNKNOWN (§1a).

### The one piece worth building before the canary, if anything is

If the operator wants one thing built rather than run, it is **not** the
confirmation loop and **not** the backfill. It is **step 4a of the vocabulary
split**: make an unrecognised provider status a **loud refusal** instead of a
silent `waiting`. Three reasons it is the right single piece: it is small, it
is confined to `leadobserve`, and it is the only change here that converts a
silence into a finding. Everything else in §3 either changes who may be
contacted or depends on a decision nobody has taken.

**But the recommendation is to build nothing and run step 1.** Twenty-three
contacts can be checked against the provider in four page reads, and a
confirmation loop built to serve 23 people would be the third instrument this
lane has had to prove nobody was running.

---

## 5. STATED FOR THE RECORD

- **No code was changed by this task.** The three findings in §1c and the
  proposal in §3 are written down and nothing is wired, which is what the
  brief asked for.
- **The 918 figure is quoted, not re-derived**, and the disagreement with
  CLAUDE.md's 912 is reported with both sources (§1a). Neither is re-derivable
  without production `work/` state or a provider read, both of which are
  outside this task.
- `origin/master` is `b1f290c84`, unchanged.
