# Autonomous run checkpoint - 2026-09-20, 20:30 UTC

Written at the end of a long Sunday session, for a Monday morning reader.
Every number recomputed today; nothing carried forward on trust.

**READ THE CLOCK FIRST.** Sunday. Both email campaigns are Mon-Fri. **Zero
sends today is the calendar, not a fault**, and no amount of engineering
changes that.

    master HEAD / origin   ac6f7996   identical, verified
    commits this session   19
    SAFE_TO_CLEAR          TRUE

---

## THE ONE THING THAT MATTERS ON MONDAY

    py -3 scripts/resume_487.py --live      MONDAY 2026-09-21, from 07:00Z

`docs/OPERATOR-AUTHORIZATION-2026-09-20-RESUME-487.md` is the standing grant.
The operator's own decision was **"You run it Monday morning"** - nothing is
scheduled, no cron exists, and **if nobody types it, the recovery does not
happen.**

Preflight re-run 2026-09-20T19:11Z. Every condition MET except the window:

    window      LATER   opens 2026-09-21T07:00Z
    truth       PASS    'paused', 10 leads, senders [2736]
    membership  PASS    {'sending_paused': 10}
    copy        PASS    10 of 10 rows carry the approved text

Success is `in_sequence` on all TEN. `active` with leads still
`sending_paused` is the SAME FAULT. Condition 5 is ONCE - do not retry.

**Monday is now provably 487's only day.** With a covering census, sender
2736 reads ROOM 15 free on Monday and FULL on both Tuesday and Wednesday.

---

## PRODUCTION TRUTH, 20:26Z

    EmailBison 487   paused   10 leads  0 sent   sending_paused x10
    EmailBison 489   active    5 leads  0 sent   first scheduled 09-24T13:27Z
    HeyReach 605732  IN_PROGRESS  3 leads  0 connection requests, 0 messages
    replies watcher  0 errors on either provider

    PROVIDER_CONFIRMED_SENDS   0 on both channels
    EMAIL_LIVE 15 - LINKEDIN_LIVE 3 - EMAIL_READY 0 - LINKEDIN_READY 0

**HeyReach is not stalled.** The graph spends 3h + 3h + 1 DAY before
`CONNECTION_REQUEST`; all three leads read `InSequence` with `error_code`
null; the 19th and 20th were the weekend on a Mon-Fri campaign. The falsifier
can only run Monday.

**489 may fix itself.** EmailBison's scheduler runs *"every time the campaign
is resumed, AND at the end of every sending day"* - DOCUMENTED, with a source
URL. So 489 re-plans on its own at the end of Monday's sending day. Its
Thursday slot is FULL (15/15, including its own 5) while Monday has 12 free
and Tuesday 15. **Free falsifier: re-read `first_scheduled` Tuesday morning.**
Moved earlier means self-correcting and no write was ever needed. Unchanged
means a plan is sticky once made, and the question becomes real.
`docs/489-COULD-GO-THREE-DAYS-EARLIER-2026-09-20.md`.

---

## WHAT AN OPERATOR MUST DECIDE

1. **Monday 07:00Z, run the 487 resume.** Nothing else produces a send.
2. **Slack: set `SLACK_BOT_TOKEN`, `SLACK_OPS_CHANNEL`, `SLACK_LIVE`.**
   The channels ALREADY EXIST - do not create any. `#resonate-notifs`
   (C0AQB4KB9TM) for global ops; `#productive-resonate-outbound`
   (C0ADUMGQX8S) and `#replies-productive` (C0BFUF4JRK9) per workspace.
   207 of 216 notifications have been recorded and delivered to nobody.
3. **One sender attestation.** `py -3 scripts/attestation_packet.py` prints
   the candidates; 207 of 257 qualify with proven Monday room. It unblocks
   nothing today - it lets the ALLOCATOR propose a mailbox for a future
   cohort, which it currently cannot do at all.

---

## WORKFORCE - verified by process, not by assignment

    CLAUDE   RUNNING   this session
    PYTHON   RUNNING   5 monitors, all heartbeating inside 90s
    QWEN     RUNNING   qwen-code v0.23.3, 2 claims live (TASK-235, TASK-237)
    GLM      COMPLETED glm-5.3, reviewed ISSUE-001, findings integrated
    GROK     IDLE      grok-4.6 verified live; its existing research was
                       RECOVERED AND USED rather than re-run

**All eight worker branches are pushed and durable** - checked explicitly,
because they were NOT. `git log @{u}..HEAD` with no upstream prints nothing,
which I misread as "0 unpushed" while four finished branches sat local-only.
That is the exact failure CLAUDE.md records from 2026-09-15. Verify with
`git log master..HEAD`, never with `@{u}`.

**One dispatch failed silently and is worth knowing about.** Round r51 logged
three tasks `DONE exit=0` within 45 seconds. They had not run - I dispatched
before committing the briefs, so the workers correctly reported the files
missing. The pool's exit code said success. **Read the worker log, not the
exit code.**

---

## INTEGRATED TODAY

| Fix | Commit | Production |
| --- | --- | --- |
| The write guard refused every HeyReach READ; the live 605732 watcher survived only because it predates the guard by 3h and held the old module in memory | `28f4766e` | **VERIFIED** - provider_truth ran live |
| The forward-book census walked a hardcoded 3 campaigns while 6 can book, so senderheadroom REFUSED every mailbox and capacity planning had no input at all | `d321c2ef` | **VERIFIED** - derived set matches the provider |
| `active_campaign_ids=()` made coverage pass vacuously - the trap that produced a wrong ROOM reading earlier the same session | `c9ddf35d` | no caller yet |
| senderheadroom counted weekdays from 0 while the repo is ISO, so `geo.windows()` days read Mon-Fri as Tue-**Saturday** | `5ff914d1` | no caller yet |
| LIVE-READINESS claimed `SUPPORTED = ()` and "nothing sends" while 14 verbs were live and a real email had gone out | `03d9da3f` | n/a |
| The PII guard had been RED since ~09-18 - two seat-holders' identifiers and **five real prospects hardcoded** in the script that builds 489's cohort | `cecd4223` | **13/13 green** |
| GLM was sending NO SOURCE CODE for two runs, and wrote every review to a filename hardcoded to `2026-09-17` | `d5ae9836` | verified by re-run |
| TASK-237: the reconciler settles activate keys from provider truth | `ac6f7996` | dry run on real ledger |

**TASK-237 needed one guard added in review.** Its loop walks `unsettled()` -
ATTEMPTED *and* UNRESOLVED - and applied one rule to both. Settling an
UNRESOLVED key FAILED would make it reservable again and re-open the
duplicate-send path Buggie confirmed closed. Reachable: 13 of our 18 keys are
UNRESOLVED. Positive evidence still settles; absence never does.

---

## THE REGISTER, AND THE PATTERN UNDER IT

`docs/state/PROBLEM-REGISTER.md` is canonical. 9 open, 5 refuted-and-kept.
Two rules it enforces on itself: **code written is not FIXED, and FIXED is
not PRODUCTION_VERIFIED.**

Six of today's defects are one shape: **a value that was true when written,
cached somewhere with no way to notice it had gone stale** - a campaign list,
a credential name, a weekday constant, a safety claim, a review filename, a
scheduler plan. The answer is not vigilance. It is the `senderheadroom`
model: carry the date and the source, and REFUSE rather than answer when you
cannot prove you are current.

---

## RECOVERY FOR THE NEXT SESSION

1. Read this file, then `docs/state/PROBLEM-REGISTER.md`.
2. `py -3 scripts/resume_487.py --preflight` - safe at any hour, refuses
   outside the window and prints when it opens.
3. `py -3 scripts/provider_truth.py` and the heartbeats in `work/heartbeat/`.
4. `py -3 scripts/claim_task.py --status` for the workers; check
   `git log master..HEAD` in each `../resonate-qwen-*` worktree.
5. **Do not re-run the census with `--reset`.** It now derives its campaign
   set from the provider; a plain re-run resumes.

**Background processes do not survive a restart.** Five monitors and the Qwen
pool are running now; none is supervised. If the machine reboots, restart the
monitors bare - **never wrap a monitor in `timeout`**, that killed the 489
watcher at exit 124 on the 18th.

### Still open, highest value first

- **ISSUE-001** reply ingestion discards the REPLY_RECEIVED event. Mechanism
  confirmed, consequence narrower than claimed, **has never fired** (it needs
  a reply that triggers a successful provider stop; zero replies so far).
  Check the `sweep` caller before moving the write in-memory.
- **ISSUE-002** a DNC cannot stop a running HeyReach sequence - TASK-235 is
  in flight on `qwen-worker-2-r52` and had no tests at last look.
- **TASK-236** provider `sending-schedule` endpoint into the watchers -
  finished on `qwen-worker-3-r52`, not yet reviewed.
- **9 more finished-but-unintegrated worker results**; 89 stale branches are
  hiding ready work from the dispatcher.
