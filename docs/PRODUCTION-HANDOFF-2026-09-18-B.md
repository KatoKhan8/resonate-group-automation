# Production handoff — 2026-09-18 (morning). REPLACES the overnight version.

Written for a session with ZERO conversation context. **Recompute before
acting on any number here.**

    py -3 scripts/production_status.py              the numbers, BOTH campaigns
    py -3 scripts/next_ready_cohort.py              READY / NEAR_MISS / blocked
    py -3 scripts/build_ready_reservoir.py          depth and ranked blockers
    py -3 scripts/bison_forward_book_census.py --report    who is booked when

> **UPDATE 2026-09-18T15:51Z - THE 489 FALSIFIER FIRED. NO EMAIL SENT TODAY.**
> Its window opened at 13:00Z and three hours later `scheduled_emails` is 0
> and `updated_at` has not moved since activation. The campaign, the sender
> and the schedule are all correct and sender 3437 has sent nine emails today
> for other campaigns. Read `docs/489-WAS-NOT-PLANNED-2026-09-18.md` before
> anything else: the likely cause is that planning happens at window CLOSE,
> and the America/New_York window I chose closes at 21:00Z. Expected first
> send is Monday 2026-09-21, and the test is to watch 21:00Z tonight.

**UNKNOWN IS NEVER 0. LIVE IS NOT SENT. ACTIVE IS NOT SENT. SCHEDULED IS NOT
SENT.** And see section 1b: **one real email HAS been sent from this estate**,
by canary 451 on 2026-09-14. "Nothing has ever sent" is false and was in the
permission table until today.

## READ THE CLOCK BEFORE READING A ZERO

Written **2026-09-18T07:15Z**. Three different windows are in play and none of
them is Zagreb-only any more:

    EmailBison 487   09:00-17:00 Europe/Zagreb Mon-Fri.   Queued for the 23rd
                     regardless, so nothing is due from it today.
    EmailBison 489   09:00-17:00 America/New_York Mon-Fri = 13:00-21:00Z.
                     NEW TODAY. Opens ~6h after this was written. This is the
                     campaign that could send first.
    HeyReach 605732  vendor default 09:00-17:00 UTC Mon-Fri. Opens ~2h after
                     this was written.

So "it is the 18th and nothing has sent" is not a fault at the time of
writing. **The first thing to check on waking is the clock, then 489.**

---

## 1. PRODUCTION TRUTH, read 2026-09-18T07:10Z

### EmailBison — there are now TWO live campaigns

    487  active   10 leads  0 sent  senders [2736]  queue 0/10
         first scheduled 2026-09-23T07:12Z    UNCHANGED, and untouched today
    489  active    5 leads  0 sent  senders [3437]  queue 0/0
         first scheduled: none queued yet

**489 is new and is the whole of today's production work.** Five approved US
contacts, sender 3437, 5/day cap, a US business-hours window. Full account:
`docs/THE-US-COHORT-IS-LIVE-2026-09-18.md`.

**READ THIS BEFORE YOU READ A BOUNCE.** Sender 3437's lifetime bounce rate is
**2.13%** - 38 on 1,784 sends - and `senderinventory.readiness()` calls it
`('degraded', 'lifetime bounce rate 2.1% is at or above 2%')`. I chose it on
`health_of()`, which checks connected and warming and does NOT look at the
bounce rate, and found this after the campaign was live. It was not swapped:
DEGRADED is a warning rather than a refusal, the rate is lifetime over 678
leads contacted, the exposure is five addresses, and all five cleared two
independent verifiers. 2736 reads 0.63% and the canary's 3948 reads 0.31%, so
3437 is the worst of the three. If one of the five bounces, start here.

`scripts/production_status.py` reported only 487 until this morning, which
meant a reader checking `EMAILBISON_SENT = 0` was reading the quiet campaign
rather than the live one. It now prints a labelled line per campaign.

### HeyReach

    605732  IN_PROGRESS  3 leads  0 connection requests  0 messages  0 replies
            sender 174892
            lastActionTime UNMOVED since 2026-09-17 on all three

**THE FALSIFIER IS DUE AND IS NOW OVERDUE ONCE MORE.** The standing
explanation for why nothing has sent is a graph one. The previous handoff set
the test: if a full window passes with all three still at
`leadConnectionStatus: None` and `lastActionTime` unmoved since the 17th, the
explanation is wrong and it should be investigated rather than extended.
Today's UTC window had not opened when this was written. **Check it.**

### Cohort

    EMAIL     ALREADY_LIVE 15   READY_NOW 0   NEAR_MISS 0   blocked 36
    LINKEDIN  ALREADY_LIVE  3   READY_NOW 0   NEAR_MISS 7   blocked 71

LIVE moved **13 -> 18** today. READY_NOW is 0 at both ends and that is the
correct answer, not a stall: everybody who could move today moved.

---

## 1b. THE PIPELINE HAS ALREADY REACHED A REAL PROSPECT, ONCE

Found 2026-09-18 and it corrects a claim that was in this repository's own
permission table: "nothing has been sent by this system yet - confirmed
touches are zero".

**Campaign 451 sent one real email on 2026-09-14.** Provider truth:

    451   status completed   total_leads 1   emails_sent 1   replied 0
          lead 203657        membership `sequence_finished`, emails_sent 1
          scheduled row      status `sent`
                             scheduled 2026-09-14T16:24:00Z
                             sent_at   2026-09-14T16:24:20Z   (20s late)
          sender 3948        bernarda.vrbat@goproductive.online
          subject            the CONTROL opener

So the end-to-end path - stage, sequence, sender, schedule, activate, send -
is PROVEN against a real person, and the canary-before-batch principle was
honoured rather than skipped: **one on the 14th, five on 489, ten on 487.**

**451's window was 09:00-17:00 America/New_York, which is 489's window
exactly.** That makes it the best available precedent for what 489 should do,
and it carries a warning as well as a reassurance:

- Its scheduled row first appeared on the 13th carrying 13:19Z - nineteen
  minutes after that window opened - and then **MOVED OVERNIGHT** to 16:24Z on
  the 14th, where it fired.
- **So a row appearing today is not a send today.** A `scheduled_emails` row
  is a lookahead, and this one moved once before it meant anything.

### Two diagnostics, so the waiting is not spent chasing the wrong thing

**`schedule.status: "Not Started"` MEANS NOTHING. Do not chase it.** All three
campaigns read it, including 451 - the one that actually sent:

    489  active     schedule.status 'Not Started'   America/New_York
    487  active     schedule.status 'Not Started'   Europe/Zagreb
    451  completed  schedule.status 'Not Started'   America/New_York  <- SENT

**`updated_at` is the diagnostic that does mean something.** Sibling campaigns
352 and 328 move theirs every few minutes while the provider works them.

    489  updated_at 2026-09-18T05:35:58Z   = the moment it was activated,
                                             unmoved since
    487  updated_at 2026-09-17T15:02:48Z   = our last write

So the provider has NOT touched 489 since activation, which is consistent with
the scheduler planning when the window opens rather than when a campaign is
started. **If `updated_at` moves and `queue` stays 0/0, that is the provider
looking at this campaign and declining to plan it - a much more interesting
fact than silence, and worth investigating immediately.**

The falsifiable expectation for 489, written down so the waiting is a test
rather than a hope: **rows should appear shortly after 13:00Z**, because that
is when its window opens and 451's appeared 19 minutes into its own. If
21:00Z passes with `queue 0/0`, the provider has not planned this campaign at
all - which is a different and much more specific fact than "it has not sent",
and is the point at which to investigate rather than wait.

---

## 2. THE FINDING THAT SHOULD CHANGE WHAT YOU DO NEXT

`docs/THE-ESTATE-IS-SATURATED-NOT-UNAPPROVED-2026-09-18.md`.

**Approval is not the bottleneck. The client's own outreach is.**

Every contact in the estate, cross-tabulated by first gate AND by whether it
also carries a safety refusal:

- **Not one** of the 36 blocked EMAIL contacts is held by approval alone.
  Every one also carries an account STOP or HOLD or a collision. Approving
  them converts nobody.
- **Seven** LinkedIn contacts are clean but for approval. They are the seven
  in the regenerated near-miss packet and they are the entire remaining
  convertible inventory.

Why the accounts are stopped:

    65  stop  somebody at this account is mid-sequence right now
    33  hold  a campaign there ended early and the status does not say
              whether we stopped it, they unsubscribed, or something else
    15  stop  somebody there has already replied or been marked interested
     2  hold  an address there bounced

The 65 are the finding: campaigns 327, 328 and 352 hold 183,239 scheduled
rows between them and the account gate is correctly refusing to put a second
conversation in front of a company already mid-sequence with its own vendor.

**So "expand the cohort" is a SOURCING problem.** More verification, more
copy and more approvals at these accounts change nothing, because the account
gate refuses after all of it and refusing is right.

---

## 3. WHAT AN OPERATOR CAN DECIDE, and nothing else moves without one

1. **The seven LinkedIn contacts.** Packet regenerated at
   `work/approval/NEAR-MISS-PACKET-2026-09-17.md` (gitignored, real names,
   NEVER commit). `approve.approve_step` is the action and a PERSON takes it -
   84 approvals stamped `by: "claude"` were revoked for exactly that reason,
   and `approval.is_accountable_approver` now refuses a bare token.
2. **Campaign 481's nine `sending_paused` leads.**
   `docs/THE-LOADED-GUN-IS-SMALLER-THAN-IT-LOOKED-2026-09-18.md` corrects the
   previous handoff: 485 is already 10 of 10 STOPPED and inert, and 481's real
   exposure is nine rows belonging to 487. The recommendation is a
   campaign-scoped `EMAIL_STOP_LEAD` - already SUPPORTED, already
   unconditional, no new permission - NOT archiving, for which no route exists
   in `WRITE_ROUTES` at all and which could break the collision proof that
   currently excludes those leads from their own accounts' history.
3. **215 records await a human ICP verdict** (`scripts/funnel.py`). No amount
   of engineering substitutes for it.

---

## 4. WHAT WAS DONE TODAY

**Production.** Campaign 489 created, staged, readback-verified and activated
under the operator's 2026-09-18 authorization. Five contacts approved against
a packet proven byte-identical to the one the operator read. Sender 3437 -
the same human 487 sends as, warm with 1,784 sends - chosen over three
inboxes with an empty forward book that are empty because they have NEVER
SENT AN EMAIL, which the system's own vocabulary calls DEGRADED.

**Permissions, narrowly.** `EMAIL_ACTIVATE` widened by exactly one canonical
row across the two independent tables that must both agree
(`providerwrites._AUTHORIZED_EMAIL_CAMPAIGNS` and
`executionguard.LIVE_ACTIVATION_GRANTS`), plus `_NEVER_ACTIVATE` refusing 481
and 485 whatever row names them.

**A GLM review of that permission, the same day, found four ways in. All four
reproduced, all four fixed**, the most serious being that the unpinned
provider slot let a re-bound canonical row carry the grant onto one of the
CLIENT's own live campaigns. Both entries are now pinned and the row must
agree with the pin rather than supply it.

**Performance, measured rather than modelled.** ContactOut `people-count` at
K=1/4/8/12: **7.98x at K=8, zero 429s at every level, p95 IMPROVED**, and the
knee at K=12 is ours rather than the provider's.
`docs/PERF-CONCURRENCY-MEASURED-2026-09-18.md`. That call is now prefetched
concurrently in `enrich.run` with the waterfall ledger proven byte-identical
to a serial run, and the HTTP timeout now aborts the socket, which is the
prerequisite for wiring the paid routes.

**Landed unwired**: `src/ratelimit.py` (with an OBSERVED classification the
measurement earned), `src/reservoir.py`, `src/stoppedcause.py`,
`geo.propose_cohort_window`.

---

## 5. THREE THINGS I GOT WRONG TODAY, so nobody re-derives them

**I named the wrong cause for gap 44 and briefed a worker on it.** I claimed
a killswitch refusal leaves a ledger reservation behind. It does not -
`actionledger.reserve` runs after the killswitch, and the session's own record
proves it: run A refused five at the killswitch and run B then authorized all
five, which gate 6 would have refused as an unsettled retry had run A left
anything. The real defect is that **an authorization minted and never used
leaves a reservation nothing settles**, which the all-or-nothing activation
shape makes routine. TASK-228 was rejected to REWORK for this reason; its
reserve-late analysis is worth reading anyway.

**A worker silenced a real test and I nearly took it.** TASK-230 made
`test_every_provider_call_is_logged_on_the_record` pass by adding
`prefetch=False`, reasoning that the test's subject was the log shape. The
prefetch MAKES A PROVIDER CALL; the test's subject is exactly that. Fixed
with an `on_applied` callback and break-proofed.

**A worker's classification would have made timeouts invisible.** TASK-231's
`HttpTimeout(TimeoutError)` did not inherit `ProviderError`, and 27 `except
ProviderError` sites catch that. A timeout would have gone from a recorded
failure to an uncaught exception ending the pass. It inherits both now; the
worker's test asserting otherwise was INVERTED rather than deleted.

The pattern in all three: **a plausible-sounding rationale attached to a
change that removed a guard.** Check what a change stops refusing.

---

## 6. GIT

    START      b36fdc28
    END        see `git rev-parse master`, verified equal to origin/master
    COMMITS    24 at the time of writing

    BRANCH                                      STATE
    qwen-worker-6-r40    TASK-232 integrated (stoppedcause), pushed
    qwen-worker-7-r28    TASK-225 integrated (ratelimit), pushed
    qwen-worker-8-r28    TASK-231 integrated (timeout), pushed; ALSO carries
                         TASK-226's journal index, NOT reviewed, NOT integrated
    bounded-gather-2026-09-18          TASK-229 integrated (reservoir), pushed
    bison-webhook-ingest-2026-09-17    TASK-230 integrated (prefetch), pushed
    geo-iso-resolution-2026-09-17      TASK-227 integrated (geo window), pushed
    staged-paused-activation-order     TASK-228 REJECTED, pushed, do not merge

**`py -3 -m unittest discover -s tests` still HANGS.** Run named modules.

---

## 7. MONITORS — SESSION-SCOPED, RE-ARM THEM

    py -3 -u scripts/reply_watch_loop.py --interval 300
    py -3 -u scripts/bison_watch_loop.py --interval 300
    py -3 -u scripts/bison_watch_loop.py --campaign 489 --interval 180
    py -3 -u scripts/heyreach_watch_loop.py --interval 300
    py -3 -u scripts/bison_mailbox_utilisation.py --interval 300 --samples 200 --quiet

The bison watcher takes `--campaign` now, because there are two. Reply
protection was healthy and moving every cycle all morning.

**DO NOT WRAP A MONITOR IN `timeout`.** The 489 watcher was armed as
`timeout 36000 py -3 -u ...` and was killed with exit 124 after about two
hours, having emitted only its startup line. The four monitors that have
survived across sessions carry no such wrapper. Arm them exactly as written
above, bare.

That mattered for one reason worth keeping: the watcher is the thing that
would have caught 489's first QUEUED row, and it died silently in the sense
that mattered - the process was gone while the campaign it was watching was
still live. Re-armed and confirmed running. **Check that the process list
actually holds all five before trusting any silence**, because a monitor that
is not running and a monitor with nothing to report look identical from the
outside, which is the whole reason `work/replywatch.json` exists.

---

## 8. NEXT ACTIONS, in order

1. **Check 489 after 13:00Z.** The watcher emits `QUEUED` when the provider
   first plans it - campaign 451's row appeared 19 minutes after its window
   opened and then MOVED overnight before firing, so a row is a lookahead and
   not a receipt. If 21:00Z passes with `queue 0/0`, the provider has not
   planned this campaign at all, which is a different and more specific fact
   than "it has not sent".
2. **Check HeyReach after 09:00Z.** The falsifier is due.
3. **The operator decisions in section 3.**
4. **Answer the 33.** `src/stoppedcause.py` is correct and has never seen a
   real event - there is no `bison.fetch_events()`. A paginated cursor reader
   for `/api/events`, modelled on `fetch_replies`, turns a proven module into
   an answer.
5. **Wire a paid route into `gather`** now that the timeout aborts. It needs
   `ratelimit`'s idempotency contract: a retried POST is a second write, and
   an aborted socket proves we stopped waiting, NOT that the server stopped
   working.
6. **Do not turn `QUEUE_JOURNAL` on.** TASK-226 reports the index makes the
   journal faster than the whole-file path; it is unreviewed and the flag
   stays off until GLM has been over the crash and interleaving contract.

---

## 9. SAFETY INVARIANTS — UNCHANGED, AND TWO STRENGTHENED

Double verification, exact sender identity, account and contact collision,
cross-channel reply suppression, email threading (step 1 owns the only
subject), provider WRITE -> READ BACK -> COMPARE, no fabricated claims,
`new_accounts_per_day: 5`, a bad record HELD or DROPPED with a reason while
unrelated records continue.

**Nothing was weakened today.** Strengthened: the activation grant is pinned
to provider ids and refuses a re-bound row, and `bison_readback` stopped
reporting FAIL on the provider's own `Re:` - a compare that cries wolf on a
correct campaign teaches an operator to ignore the verdict.
