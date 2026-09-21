# Production handoff - 2026-09-21T09:30Z

Written for a session with no conversation context. **Supersedes
`PRODUCTION-HANDOFF-2026-09-19.md` and every checkpoint before it.**
Every number here was read from the providers or from git today.

    master / origin      6cc71928   identical, verified
    working tree         clean
    SAFE_TO_CLEAR        TRUE

**READ THE CLOCK.** Monday. 487 is Mon-Fri 07:00-15:00Z (Europe/Zagreb
09:00-17:00); 489 is Mon-Fri 13:00-21:00Z (America/New_York 09:00-17:00).

---

## 1. WHAT HAPPENED TODAY, AND IT IS THE HEADLINE

**487 WAS RESUMED AND RECOVERED.** At 09:06:07Z the authorized write ran,
at the operator's instruction, and all ten leads moved
`sending_paused -> in_sequence`. That is the grant's ONLY definition of
success. `docs/487-IS-RECOVERED-2026-09-21.md` is the full record.

**489 RE-PLANNED ITSELF THREE DAYS EARLIER, WITH NO WRITE FROM US.**
`first_scheduled` moved `2026-09-24T13:27Z -> 2026-09-21T13:34Z`, with
entirely new row ids. The Sunday analysis proposed a pause/resume to force
this and correctly refused to perform it; EmailBison's scheduler runs at the
end of every sending day and did it unprompted.
`docs/489-COULD-GO-THREE-DAYS-EARLIER-2026-09-20.md`.

**STILL ZERO PROVIDER-CONFIRMED SENDS ON EITHER CHANNEL.** Recovered is not
sent, scheduled is not sent, and active is not sent.

---

## 2. PROVIDER TRUTH, read 09:25-09:30Z

### EmailBison - our campaigns

    487  active   10 leads   SENT 0   replies 0  bounces 0  unsubs 0
         membership {'in_sequence': 10}      sender [2736]  Europe/Zagreb
         SCHEDULED ROWS: 0        <- the resume cleared them, see §3
         provider sending-schedule: today EMPTY, tomorrow EMPTY, +2 EMPTY

    489  active    5 leads   SENT 0   replies 0  bounces 0  unsubs 0
         membership {'in_sequence': 5}       sender [3437]  America/New_York
         scheduled rows: 8        first send 2026-09-21T13:34Z
         provider sending-schedule: today 3 emails, tomorrow 2, +2 EMPTY

    481  paused   23 leads   SENT 0
         membership {'stopped': 14, 'sending_paused': 9}
         NOT a destination. `scripts/make_481_inert.py --live` is still
         unperformed and still authorized-but-unrun.

**No newer Resonate EmailBison campaigns exist.** The non-terminal set is
487, 489, 481 (ours) and 327, 328, 352 (the client's).

### HeyReach

    605732  IN_PROGRESS   3 leads
            connectionsSent 0   accepted 0   replies 0   uniqueLeadsContacted 0
            all three leads: leadCampaignStatus InSequence,
            connection None, message None, error_code None
            lastActionTime: 2026-09-18  (ALL THREE, unmoved)

    605487  DRAFT     0 leads      604869  DRAFT     0 leads
    599020  FINISHED  0 leads

**OPEN FALSIFIER, AND IT IS LIVE TODAY.** The graph spends 3h + 3h + 1 DAY
before `CONNECTION_REQUEST`, and `docs/THE-LINKEDIN-DELAY-IS-IN-THE-GRAPH-2026-09-19.md`
says the test can only run on a weekday. It is Monday and `lastActionTime` is
still Friday's on all three leads. That is not yet a stall - 605732's own
sending window may not have opened - but **if lastActionTime is still
2026-09-18 by end of Monday, the campaign is stalled and that is a new
finding.** Check with `heyreach.campaign_leads(605732)`.

### Suppression and sender health

    reply watcher     0 errors on either provider, heartbeat fresh
    replies received  0 on any Resonate campaign, ever
    suppression       nothing to suppress yet

    EmailBison estate  225 inboxes, 210 connected, 207 healthy
    2736 (487)         ROOM, 15 free today, FULL Tue and Wed
    3437 (489)         ROOM today and tomorrow
    HeyReach seats     41 total, 34 active, 33 valid auth, 0 unallocated

---

## 3. THE ONE OPEN PRODUCTION QUESTION

**487 is recovered and has an EMPTY QUEUE.** Rows went 10 -> 0 on resume and
had not rebuilt as of 09:25Z, nineteen minutes later. The provider reports
nothing scheduled for today, tomorrow or the day after.

This is expected rather than alarming - EmailBison re-plans on resume and at
the end of every sending day, and 489's own rebuild appeared at 22:01Z rather
than instantly. **The falsifier, in order of what it means:**

    rows reappear, first send inside today's window
        -> the resume is complete and 487 sends today
    rows reappear on a LATER day
        -> the mailbox rule applies. 2736 is FULL Tue and Wed, so a rebuild
           that misses today lands Thursday at best
    NO rows by 15:00Z (today's window close)
        -> the resume produced a LIVE campaign with an empty queue. That is
           a NEW fault, not the old one, and it has never been seen here

**DO NOT RESUME 487 AGAIN IN ANY OF THOSE CASES.** Condition 5 of the grant
is ONCE, the campaign is already `active`, and the grant is spent.

Check with:

    py -3 -c "import sys;sys.path.insert(0,'.');from src.providers import bison,load_env;load_env();print(len(bison.scheduled_emails(487)))"

---

## 4. AUTHORIZATION - what is and is not permitted

    SPENT    the 487 resume. Performed 09:06Z, succeeded, ONCE. Do not repeat.
    HELD     `scripts/make_481_inert.py --live` - authorized, never run
    FORBIDDEN resuming or pause/resuming 489. Named twice in the standing
             grant under what is NOT authorized. It re-planned itself anyway.
    FORBIDDEN any second resume of 487
    FORBIDDEN attesting a human to a mailbox to gain capacity
    SEALED   `LINKEDIN_STOP_LEAD` is on WRITE_ROUTES and NOT in SUPPORTED.
             The mechanism exists; enabling it is a decision nobody has made.

`providerwrites.SUPPORTED` holds 14 verbs. Verified unchanged today.

**No unresolved provider writes.** The action ledger holds 18 distinct keys -
14 `unresolved`, 4 `attempted`, all activate verbs. None permits a
re-attempt: three independent refusals block it, attacked and confirmed by
Buggie. `scripts/reconcile_ledger.py` (dry run by default) now settles the
attempted ones from provider truth and leaves the 14 for a person.

---

## 5. WORKFORCE

    CLAUDE   this session
    PYTHON   RUNNING  5 monitors, pids 86848 / 89712 / 10388 / 32056 / 84868,
                      all heartbeating inside 90s
    QWEN     IDLE     qwen-code v0.23.3. 0 claims, 0 ready. Eight worktrees,
                      all clean, all branches PUSHED.
    GLM      IDLE     glm-5.3 via ZAI_API_KEY. Last task: the ISSUE-001
                      review, integrated.
    GROK     IDLE     grok-4.6 via XAI_API_KEY. Its scheduling research was
                      recovered and used today rather than re-run.

**The monitors do not survive a restart and neither does the session
monitor.** Five bare python processes plus a session-scoped watch on 487 and
489. If the machine reboots, restart them bare - **never wrap a monitor in
`timeout`**, that killed the 489 watcher at exit 124 on the 18th.

### Unreviewed worker output

    TASK-219  qwen-worker-r51, REVIEW, pushed. "approval fingerprint excludes
              subject for threaded steps". NOT reviewed. Read it first.

### Six branches carry code master does not have

    TASK-067 067 qwen-worker-7      TASK-213 qwen-worker-4-r45
    TASK-214 qwen-worker-r45        TASK-225 qwen-worker-7-r28 (ratelimit)
    TASK-230 task-230-prefetch      TASK-231 qwen-worker-8-r28 (large, 2012+)

**Check each against master before merging.** See §8.

---

## 6. ENGINEERING INTEGRATED TODAY

| What | Commit |
| --- | --- |
| Write guard refused every HeyReach READ; the live watcher survived only on a pre-guard module in memory | `28f4766e` |
| Census walked a hardcoded 3 campaigns while 6 can book; senderheadroom REFUSED every mailbox | `d321c2ef` |
| `active_campaign_ids=()` made coverage pass vacuously | `c9ddf35d` |
| senderheadroom counted weekdays from 0 while the repo is ISO | `5ff914d1` |
| LIVE-READINESS claimed `SUPPORTED = ()` while 14 verbs were live | `03d9da3f` |
| PII guard red since ~09-18: seat-holder identifiers and five real prospects in a tracked script | `cecd4223` |
| GLM was sending NO SOURCE for two runs; output filename hardcoded to 09-17 | `d5ae9836` |
| TASK-237 reconciler, plus a guard: an UNRESOLVED key is never settled FAILED | `ac6f7996` |
| TASK-235 LinkedIn stop verb, seal intact | `abfc844a` |
| TASK-236 provider `sending-schedule` reader, silent-zero removed | `47afa019` |
| ISSUE-001 fixed across both call sites | `0379958d` |
| 487 preflight contradicted its own checklist once the window opened | `6ed1f0ee` |
| The unintegrated scan compared task files, not code | `6cc71928` |

---

## 7. CONCLUSIONS THAT MUST NOT BE RE-DERIVED

Each of these cost real time this session or last.

- **The 215 in ICP_REVIEW have failed nothing.** Zero criteria at `fail`,
  zero contacts, all still `queued`, 184 with no company evidence at all.
  Re-qualifying the whole estate yields **ONE** extra lead, measured. It is
  an ENRICHMENT task and it does not belong on an operator's list.
- **Sender capacity is not the constraint.** 2,025 free slots, and
  `HUMAN_IDENTITY_ATTESTED = 0` across all 257 accounts, so
  `SAFE_FOR_PRODUCTIVE = 0`. A campaign may name exactly ONE sender anyway
  (`executionguard._sender_for`). `scripts/attestation_packet.py` ranks the
  candidates; one genuine attestation is the unlock and it is an operator act.
- **The census per-human table groups by DISPLAY NAME.** Twelve strings are
  not twelve known owners. `resolve_owner` returning None for all 257 is the
  module working.
- **`/api/events` cannot answer the 33 ambiguous holds.** It replays ten days
  and the memberships are months old. The answerable signal is the
  membership's own `emails_sent`, which master's `stoppedcause.py` uses.
- **REFUSED IS NOT ROOM.** A non-covering forward-book walk cannot prove a
  mailbox free. Do not pass the walked campaign list as the active list -
  that makes `coverage()` pass vacuously and it produced a wrong answer here.
- **ContactOut company-info moved ZERO verdicts over 50 records** (09-16).
  Do not scale it without a new measurement.
- **Credential names come from `config.VARIABLES`.** `CONTACTOUT_KEY` does
  not exist. `ZAI_API_KEY` and `XAI_API_KEY` are NOT in the registry, so
  `credential_health.py` structurally cannot report on the model workers.

---

## 8. THE TRAP THAT ALMOST CAUSED A REGRESSION TODAY

`task173_scan.py --unintegrated` compared each task FILE'S STAGE and never
looked at the code, so **six of twelve reported tasks were already
integrated**. TASK-229's three files are byte-identical to master's by blob
hash - merging would have deleted 12,487 lines. TASK-232 was worse: its
branch carries an older `stoppedcause.py` and merging would have deleted the
`NEVER_CONTACTED` classification that actually answers the question.

Fixed in `6cc71928`: the scan now compares blob hashes and prints
**"ALREADY INTEGRATED ... DO NOT MERGE these - the branch is older than
master."** Still: check each branch against master before merging it.

---

## 9. RESUMING AFTER /clear

    cd C:\Users\Zvonimir\Desktop\resonate-group-automation
    git log --oneline -1                       # expect 6cc71928 or later
    py -3 scripts/provider_truth.py            # HeyReach, writes state
    cat work/heartbeat/*.json                  # are the monitors alive
    py -3 scripts/claim_task.py --status       # workers
    py -3 scripts/task173_scan.py --unintegrated
    py -3 scripts/credential_health.py --verify

Then read, in order: this file,
`docs/state/PROBLEM-REGISTER.md`, `docs/487-IS-RECOVERED-2026-09-21.md`.

**Priorities:** P0 a provider-confirmed send on either channel - the two
live questions are 487's queue rebuild (§3) and 489's 13:34Z window.
P1 the HeyReach Monday falsifier (§2). P2 larger READY cohorts, which is an
enrichment problem. P3 the six unmerged branches, TASK-225's rate limiter
first. P4 Slack, which is an operator action and blocks all alerting.

**Buggie**, when it is run again: read-only on an ISOLATED WORKTREE, never
`--fix`, never against files another worker is editing, and never where it
can reach a provider. Its last run paused live campaign 487 by accident,
which is what `providers.refuse_unauthorized_write` now exists to stop.
`work/BUGGIE-FINDINGS-2026-09-20.md` holds its findings; the top five are
triaged in the problem register.

---

## 10. BLOCKERS, with their exact causes

    487 has no queued rows        the resume cleared them; the scheduler has
                                  not rebuilt. Wait, do not re-resume. §3
    no alerting reaches anybody   SLACK_BOT_TOKEN / SLACK_OPS_CHANNEL /
                                  SLACK_LIVE all unset. The adapter works and
                                  207 notifications are recorded and
                                  undelivered. Channels already exist -
                                  #resonate-notifications is C0C34GCAR27.
                                  SET 2026-09-21, smoke test SENT.
    0 eligible senders            attestation, an operator act. §7
    READY cohort is 0 on both     enrichment, not approval or capacity. §7
    89 stale branches             they hide ready work from the dispatcher
    Qwen idle                     the backlog empties fast; 0 ready now
