# Production handoff — 2026-09-19. REPLACES the 09-18-B version.

Written for a session with ZERO conversation context. **Recompute before
acting on any number here.**

    py -3 scripts/production_status.py              the numbers, BOTH campaigns
    py -3 scripts/provider_truth.py                 rewrites docs/state/
    py -3 scripts/next_ready_cohort.py              READY / NEAR_MISS / blocked
    py -3 scripts/sender_pool_census.py             now also: when each mailbox is free
    py -3 scripts/bison_forward_book_census.py --report   who is booked when

## READ THE CLOCK FIRST. TODAY IS SATURDAY.

    2026-09-19 is a SATURDAY. 20th is Sunday. 21st is Monday.

    EmailBison 487   Mon-Fri Europe/Zagreb.   Rows sit on 2026-09-23.
    EmailBison 489   Mon-Fri America/New_York. Rows sit on 2026-09-24.
    HeyReach 605732  Mon-Fri 09:00-17:00 UTC.

**Nothing is due from any of the three today or tomorrow.** Every zero on
this page for the 19th and 20th is the calendar, not a fault. The previous
handoff's first instruction was to read the clock before reading a zero and
it is still the right one.

---

## 1. THE TWO FALSIFIERS FROM YESTERDAY BOTH RESOLVED

### 489 WAS planned, at window close, exactly as predicted

    489  updated_at  2026-09-18T21:03:56Z   window closes 21:00Z   +3m56s
         queue 0/0 -> 0/5

`docs/489-WAS-NOT-PLANNED-2026-09-18.md` set the cheap test: watch 21:00Z. It
has run and the inference held. Planning happens at or just after window
CLOSE. 487 was planned +2m48s after its own close on the 17th, and moved
again at 2026-09-18T16:03:54Z. Both stamps land at :03 past an hour, which
reads as an hourly planning tick - **OBSERVED. The rule selecting which
campaigns a tick plans is UNKNOWN and is not asserted.**

### The LinkedIn graph question did not need another day

`docs/THE-LINKEDIN-DELAY-IS-IN-THE-GRAPH-2026-09-19.md`. The measured path
for a not-connected lead:

    CHECK_IS_CONNECTION 0h -> VIEW_PROFILE +3h -> FOLLOW +3h
      -> CONNECTION_REQUEST +1 DAY            = 30h cumulative

Two actions and thirty hours, and the 1 DAY wait is in the approved graph.
`error_code` is null on all three leads and all read `InSequence`, so nothing
has failed. **Both readings of "1 DAY" converge on Monday 2026-09-21**, which
is a falsifier with a date: requests appear -> the graph explains everything;
Monday closes at 17:00Z with `connection: None` -> it no longer does.

---

## 2. THE FINDING THAT SHOULD CHANGE WHAT YOU DO NEXT

`docs/THE-SEND-DATE-IS-THE-MAILBOX-2026-09-19.md`.

> **UPDATED 2026-09-19T11:35Z: THE CENSUS COMPLETED AND THE RULE CHANGED.**
> Read `docs/THE-SCHEDULER-PLACES-THE-WHOLE-COHORT-2026-09-19.md`. The
> mailbox finding below STANDS. The rule does not: it is not "the first day
> with a free slot" but **the first sending day with room for the WHOLE
> COHORT**, which predicts BOTH campaigns exactly where the single-slot rule
> gets 489 wrong. 489's date is now PROVEN rather than inferred. Two further
> corrections there: the 23rd is exactly 15/15 rather than oversubscribed, and
> **client campaign 352 books 16 rows on a mailbox whose `daily_limit` is 15**,
> so `daily_limit` is not a hard provider cap and every capacity number in
> this system rests on it.

**The send date is not a property of the campaign. It is a property of the
mailbox.** From the complete forward-book walk, per campaign, per sender,
per day - sender 2736 carries 487, daily limit 15:

    sender 2736      Mon 09-21   Tue 09-22   Wed 09-23
      client 327        15           0           0
      client 328         0          15           0
      our    487         0           0          10
      -------------------------------------------------
                       15/15       15/15      10/15
                       FULL        FULL       first free day

Monday and Tuesday are booked solid by the client's own campaigns. 487's ten
openers went to the first day its mailbox had a single free slot. **PROVEN,
not inferred** - a complete walk of every scheduled row in every active
campaign, and the ten rows on the 23rd are 487's own.

489 is PROVEN too, by the completed walk - but by the whole-cohort rule, not
this one. Sender 3437 had 2 free slots on the 22nd and 1 on the 23rd and
489's five went to the 24th, the first day with room for all five.

**No campaign-side change moves these dates.** Not the window, not the
activation, not the approval, not the cap, not the sequence. This is
`THE-ESTATE-IS-SATURATED-NOT-UNAPPROVED` one layer down: that proved the
client's book blocks our cohort at the ACCOUNT gate, this proves it throttles
the cohorts that got through, at the MAILBOX. **Expansion is a sourcing
problem; latency is a sender problem.** It is systemic - every future cohort
on a shared mailbox queues behind the client the same way.

### The defect it exposed, and what was done about it

Nothing in sender selection read the forward book. `senderinventory.readiness()`
asks connected / warm / bounce / limit - all DELIVERABILITY, none LATENCY - so
the selector could not tell a mailbox free tomorrow from one booked for three
days. `bison_forward_book_census.py` computed the answer and only printed it.

`src/senderheadroom.py` is that logic made callable, on the asymmetry that
makes the census sound: a walk can only UNDERCOUNT, so a count reaching the
limit proves FULL on ANY walk, while ROOM must earn four gates - complete,
fresh within 24h, covering every active campaign, known limit. **REFUSED is
not ROOM** and `earliest_day` skips a refused day rather than falling through.
Wired into `sender_pool_census`, which had a HEADROOM stage measuring what a
mailbox sent TODAY rather than what it is committed to TOMORROW. 22 tests.

---

## 3. PRODUCTION TRUTH, read 2026-09-19T09:30-10:00Z

    487  active   10 leads  0 sent  0 replies  0 bounced  sender [2736]
         queue 0/10   all ten rows scheduled 2026-09-23, 08:41-14:32Z
    489  active    5 leads  0 sent  0 replies  0 bounced  sender [3437]
         queue 0/5    all five rows scheduled 2026-09-24, 13:05-16:44Z
    605732  IN_PROGRESS  3 leads  0 connections  0 messages  0 replies
         sender 174892, lastActionTime 2026-09-18 on all three

    REAL_EMAIL_SENDS     0   (canary 451 sent one on 2026-09-14; that stands)
    REAL_LINKEDIN_SENDS  0
    EMAIL_REPLIES 0   LINKEDIN_REPLIES 0

**Both campaigns' rows sit correctly inside their own windows.** Sender 3437
remains DEGRADED on lifetime bounce (2.11%, 38/1799) and was not swapped, for
the reasons in the 09-18 handoff. It is still the worst of the three; 2736
reads 0.68% and 3948 reads 0.31%.

### An independent corroboration worth keeping

1,500 events walked across 2026-09-17T15:18Z -> 2026-09-19T09:33Z: **zero
touch any of our campaigns.** Every event in the estate belongs to the
client's 327/328/352 (1,165 / 198 / 137). All 11+5 bounces and all 12
send-failures are theirs. Our campaigns really have sent nothing.

### Cohort, unchanged and correct

    EMAIL     ALREADY_LIVE 15   READY_NOW 0   NEAR_MISS 0   blocked 36
    LINKEDIN  ALREADY_LIVE  3   READY_NOW 0   NEAR_MISS 7   blocked 71

READY_NOW 0 at both ends is the right answer, not a stall. **Nothing is
convertible without either a human approval or new sourcing.**

---

## 4. 481 AND 485, RE-VERIFIED — AND ONE THING NOBODY HAD ASKED

    481  paused  23 rows  0 sent   14 stopped + 9 sending_paused  [2736, 2737]
    485  draft   10 rows  0 sent   10 stopped - already inert     [2736]

**481's nine `sending_paused` rows are EXACTLY 487's nine live leads** - not
nine of them, the same nine, confirmed lead by lead, with zero in neither
live campaign. That reproduces `THE-LOADED-GUN-IS-SMALLER-THAN-IT-LOOKED`
independently.

**The new fact: 481 also overlaps 489 on four leads, which nobody had looked
at. All four read `stopped` in 481**, so the newer cohort carries no exposure.
The nine are the whole of it.

`scripts/make_481_inert.py` converts them to `stopped` - the state 485 is
already in - rather than archiving, for which no route exists in
`WRITE_ROUTES`. Nothing is deleted. It matters because `sending_paused` is
RESUMABLE and `stopped` is not (the provider refuses re-attach with 422), so
it replaces a guard depending on our own `_NEVER_ACTIVATE` with one the
provider enforces.

It canaries the risk nobody has measured: `EMAIL_STOP_LEAD`'s evidence that
siblings stay untouched is a WITHIN-campaign result. Whether a stop in 481
touches the same lead's membership in LIVE 487 is unmeasured, and if the
provider models it per LEAD rather than per (lead, campaign) it would kill
the live cohort. So: one lead, then a full re-read of 487 and 489, refusing
to continue unless every row is unchanged.

**DRY RUN VERIFIED. THE `--live` RUN HAS NOT BEEN PERFORMED** - it was
blocked by the harness permission classifier. The nine rows are still
`sending_paused`. Run it when a human can approve the command.

---

## 5. WHAT AN OPERATOR STILL HAS TO DECIDE

1. **The seven LinkedIn contacts.** `work/approval/NEAR-MISS-PACKET-2026-09-17.md`
   (gitignored, real names, NEVER commit). A PERSON takes
   `approve.approve_step` - 84 approvals stamped `by: "claude"` were revoked
   for exactly that reason. **These seven are the entire remaining
   convertible inventory.**
2. **`scripts/make_481_inert.py --live`** (section 4).
3. **215 records await a human ICP verdict** (`scripts/funnel.py`).

---

## 6. WHAT IS RUNNING RIGHT NOW

Five monitors, all bare - **DO NOT WRAP A MONITOR IN `timeout`**, the 489
watcher was killed at exit 124 that way on the 18th:

    reply_watch_loop.py --interval 300                     healthy 09:51:01Z
    bison_watch_loop.py --interval 300
    bison_watch_loop.py --campaign 489 --interval 180
    heyreach_watch_loop.py --interval 300
    bison_mailbox_utilisation.py --interval 300 --samples 200 --quiet
    bison_watch_loop.py --campaign 487 --interval 180     armed 10:20Z

**THE CENSUS IS COMPLETE**, as of 2026-09-19T11:30Z: all five campaigns,
184,284 rows, every one `complete: true`. `senderheadroom` now answers FULL
and ROOM rather than REFUSED. Re-walk before trusting it for a NEW cohort -
the freshness gate refuses to prove ROOM from a walk over 24h old, and the
client's book demonstrably grows day to day.

The history, because it will happen again:
**THE FIRST RUN STOPPED ON NETWORK TIMEOUTS AND WAS RESUMED.** The first
run completed 327 (48,759 rows) and 489, then lost the connection on 328 and
never reached 352 or 487 - it saved progress and exited 0 rather than
crashing, which is TASK-231's timeout classification working. A resume over
328, 352 and 487 is running. **Re-run WITHOUT `--reset` to continue; `--reset`
discards the walk.**

**A FRESH FORWARD-BOOK CENSUS IS MID-WALK** and is the test for 489's
inferred cause. Started 2026-09-19T09:28Z over campaigns 327, 328, 352, 487
and 489 (489 was NOT in the 09-17 walk). It had reached ~34,500 of ~48,759
rows on campaign 327 alone; the full walk is ~183k rows over roughly six
hours. It is resumable - **re-run without `--reset` to continue** - and
`work/forward-book-census.2026-09-18.bak.json` holds the previous complete
walk if the new one is lost.

**Until it finishes, `senderheadroom` refuses every mailbox**, which is the
designed behaviour and was verified live against the in-flight file.

When it completes, the question it answers is: **was sender 3437 full on the
22nd and 23rd when 489 was planned?** Yes -> 489 is proven by the same rule
as 487. No -> the rule is wrong for 489 and that reopens.

---

## 7. TWO CORRECTIONS TO THE PREVIOUS HANDOFF

**Next-action 4 should not be done.** It says a cursor reader for
`/api/events` "turns a proven module into an answer" for the 33 ambiguous
holds. `docs/THE-THIRTY-THREE-ANSWERED-2026-09-18.md`, committed EIGHT HOURS
BEFORE that handoff, already answered them by a different route and says why
this one cannot work: the feed replays TEN DAYS and the memberships are
months old. Measured here: 600 events span under NINETEEN HOURS, so the
retention window holds ~7,600 events, essentially all client EMAIL_SENT.

`bison.fetch_events` / `walk_events` / `events_window` were built anyway and
kept, because they are right for recent memberships, reply and bounce
latency, and the webhook path that still has no captured delivery. **They are
not pointed at the 33.** 14 tests.

**The checkpoint in the prompt was stale.** A session had already run past
`b36fdc28`; master was at `5286e2cb` on arrival. Always verify.

---

## 8. THE NEAR-MISS THAT IS WORTH REMEMBERING

The LinkedIn graph walk first printed `delay=None` on all 24 nodes, and the
finding one keystroke away was "there are no delays before CONNECTION_REQUEST,
so three days is unexplained" - which would have sent somebody hunting a
provider fault that does not exist. The field is **`actionDelay` /
`actionDelayUnit`**. Four plausible names had been probed and a miss on all
four is indistinguishable from a real absence.

Third catch of this class in three days, and the same one the standing
corrections warn about for signatures. **A field that reads empty is a
question about the field name until the raw keys have been dumped.**

---

## 9. GIT

    START      5286e2cb   (NOT b36fdc28 - the prompt was a session stale)
    END        see `git rev-parse master`, verified equal to origin/master
    COMMITS    5

    qwen-worker-r9-preserved-2026-09-15   NEW. The local qwen-worker-r9 had
      diverged from its remote and carried unmerged TASK-119 work (provider
      ids normalised to strings at the boundary, which master's
      `bisonfactory._bind` still does not do). Pushed under a non-colliding
      name rather than rewriting remote history. UNREVIEWED, four days old,
      and `collision.py` already normalises defensively at its own read, so
      this is latent inconsistency rather than a live defect.

`py -3 -m unittest discover -s tests` still HANGS. Run named modules.

---

## 10. NEXT ACTIONS, in order

1. **Monday 09:00-17:00Z: watch HeyReach 605732.** The connection requests
   are predicted for the 21st and the falsifier is written (section 1).
2. **Finish the census** (re-run WITHOUT `--reset`), then
   `py -3 scripts/sender_pool_census.py` and settle 489's cause.
3. **`scripts/make_481_inert.py --live`** once a human can approve it.
4. **The seven LinkedIn approvals** - the only convertible inventory.
5. **Wednesday 2026-09-23 from 08:41Z: 487's ten openers are due, and the
   mailbox is contended.** Read
   `docs/THE-CLIENTS-BOOK-IS-GROWING-INTO-OUR-DAY-2026-09-19.md` first:
   client campaign 328 held ZERO rows on sender 2736 for the 23rd in the
   complete walk of the 17th and holds at least FIVE now, which with 487's
   own ten puts the mailbox at >=15 of 15 on the day it sends. What the
   scheduler does with an oversubscribed day is UNKNOWN. This is the first
   real batch send this system will have made. Watch it rather than assume
   it - the 487 watcher is armed for exactly this and emits
   `SCHEDULE-MOVED`.
6. **Thursday 2026-09-24 from 13:05Z: 489's five.**
7. Give `senderheadroom` a second caller - the cohort stager - so the NEXT
   cohort picks a mailbox by when it can send, not only by whether it is
   healthy.

## 11. SAFETY INVARIANTS — UNCHANGED, NOTHING WEAKENED

Double verification, exact sender identity, account and contact collision,
cross-channel reply suppression, email threading (step 1 owns the only
subject), provider WRITE -> READ BACK -> COMPARE, no fabricated claims,
`new_accounts_per_day: 5`, a bad record HELD or DROPPED with a reason while
unrelated records continue.

**Nothing was weakened today, and no prospect-facing state was mutated at
all.** Every provider call this session was a GET except one that was blocked
before it ran.
