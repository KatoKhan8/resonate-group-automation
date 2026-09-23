# Production handoff — 2026-09-23 afternoon

For a session with no conversation context. **Supersedes
`docs/PRODUCTION-HANDOFF-2026-09-23-OVERNIGHT.md`.**

---

## 1. THE THING TO READ FIRST: THE CROSS-CHANNEL STOP HAD NEVER RUN

`ACCOUNT-OUTREACH.md` guarantees a confirmed reply stops that lead on BOTH
channels. **That guarantee had never once executed.**

`reply_watch_loop.py` opts into no provider write scope — it sets
`REPLY_POLL_ENABLED=1` and nothing else — so every stop
`inbound._stop_at_provider` attempted was refused by the guard added after the
487 incident, caught, and returned as a dict nobody read. From
`work/provider-write-refusals.jsonl`:

    2026-09-23T11:19:35Z POST .../campaigns/491/leads/stop-future-emails
    argv: ['reply_watch_loop.py', '--interval', '300']

Megan Ward replied **"no thank you"** on LinkedIn at 11:12:33Z and stayed
`in_sequence` in EmailBison 491 for **2h07m**. I stopped her by hand at 14:0xZ
(`in_sequence` → `stopped`, readback confirmed).

**IT HID BEHIND A COINCIDENCE, AND THIS IS THE PART WORTH REMEMBERING.**
EmailBison marks a lead `replied` *by itself* when the reply arrives BY EMAIL.
Four of the five locally-stopped contacts read `replied` at the provider for
that reason alone. The cross-channel case — a LinkedIn reply stopping an
EMAIL sequence — is the only one that depends on our call, and it was the
broken one. Every dashboard looked right.

Detection and classification were never the problem: 7m02s from reply to stop
attempt, inside the 15-minute gate.

### The fix, and why it is not the obvious one

`ed26fb9b`. `providers.allow_writes` now takes `only=` — a tuple of route
fragments — and `writes_allowed` takes the URL. `inbound.STOP_ROUTES` is two
routes and nothing else:

    outside any scope        stop False   enrol False   pause False
    inside the reply scope   stop TRUE    enrol False   pause False
                             "a scope is open but does not cover this route"

**`RESONATE_PROVIDER_WRITES=1` on the loop was the wrong fix** and is worth
refusing again: it would have fixed the stop and handed the same process
authority to enrol, pause, resume and create — giving back exactly what the
487 guard cost. A process holds only what its job needs.

Two details that earn their lines: a scope that is open but does not cover the
route reports *differently* from no scope at all (different investigations),
and `only=()` raises at construction, because a filter computed to empty is a
bug and not an authorise-all. 14 tests.

---

## 2. THIS MORNING: THE MACHINE, AND WHY IT WAS DARK FOR FOUR HOURS

**Cause, measured.** System event 1074 at **05:29:09**: `MoUsoCoreWorker.exe`
restarted the machine to install **KB5124010 — an optional *Preview* update**.
The last production heartbeat was 05:29:04. Five seconds.

Ruled out rather than assumed: no event 41, 6008 or 1076 in seven days; on
mains throughout (`Ac=1` at 05:25, 05:30:55, 05:33:09); the only Kernel-Power
125 rows are ACPI thermal-zone *enumeration at boot*. Active hours were
09:00–01:00, so 05:29 was a window Windows had been **told** it could use —
which was precisely the unattended overnight run.

**The reboot cost four minutes. The outage cost four hours**, because nothing
started the loops at boot.

`docs/MACHINE-HARDENING-2026-09-23.md` has every before/after. Applied and
independently read back: `NoAutoRebootWithLoggedOnUsers=1`, `AUOptions=3`,
`AUPowerManagement=0`, `HiberbootEnabled=0`, wake timers AC=0 DC=0, active
hours **20:00–14:00**, preview opt-in off, updates paused to 2026-09-30.

**Still open:** auto-logon. ARSO is being enabled by the operator; `netplwiz`
declined. **ARSO is designed for restarts Windows initiates**, and this
build's wording is "after an update", so a manual `shutdown /r` tonight may
land at the lock screen *without that proving ARSO is off*. Two questions, in
order: did the machine sign itself in (ARSO), and once signed in did the
monitors return (`start_monitors`). The second owns the four-hour gap and can
be tested right now by logging out and back in.

`ResonateMonitors` **does not exist** — `schtasks` was refused unelevated and
the elevated script does not register it. What fires at logon is
`%APPDATA%\...\Startup\resonate-monitors.cmd`. Do not add the task as well
without removing the .cmd.

---

## 3. MONITORS — 11 UP, AND THE TWO-WITNESS RULE

    replies           9656    notify-deliver  31008    digest        15664
    bison-487        23772    bison-489       33848    bison-491     34380
    bison-492        34244    bison-494       34640    bison-495     22824
    heyreach-605732  30924    slack-agent     19580

`scripts/start_monitors.py --status | --live | --restart <name>`.

**Liveness takes TWO witnesses and either alone is proof of life:** a
heartbeat newer than 20 minutes, OR a python process whose command line runs
that script (and that `--campaign N`, where there is one).

They are separate because **they fail apart, and I wrote the bug that proved
it.** `slack_agent_loop` writes its heartbeat when it handles a Slack
envelope, not on a timer. Measured today: pid alive, socket reconnected, log
healthy, heartbeat 21.5 minutes old, `--status` saying DOWN. Had the logon
autostart fired in that state it would have started **a second agent on the
same Socket Mode app**, both answering the same message. `slack-agent`
currently reads `UP ... process` with a 67-minute beat, and that is correct.

`--live` skips anything UP, which is right after a crash and **wrong after a
merge** — the loops import once and never reload. `--restart` is the deploy.
The check is process start time against module mtime, not the merge commit.

---

## 4. THE REPLY ENGINE — DRAFT ONLY, AND IT FOUND MORE THAN IT BUILT

`src/replyengine.py`, `scripts/reply_engine_draft.py`. `83a30652`.

**`SENDING_ENABLED = False`.** A module constant, not an env var: an env var
is unset by a restart, and flipping this must be an edit plus a deploy. The
operator's own precondition is recorded beside it — *Productive must confirm
in writing that system-written replies may go out under their senders' names*
— because no code can check that and the flag stands in for it.

**`compose()` raises `NoRegister`.** `prompts/reply_handling.md` does not
exist. The engine answers *what should happen to this reply* completely and
*what to say* not at all.

### Class counts, 28 real drafts across 09-22 and 09-23

    out_of_office        20        never                  22
    negative              3        review                  6
    not_relevant          2
    unknown               1        would have been sent:   0
    automated             1        replies composed:       0
    assistant_redirect    1

`unknown` was **9 before the class-layer work and is 1 after**.

### What the first run found, which mattered more than the drafts

A **German out-of-office classified as `referral` at 0.8** off its
emergency-contact line. Under the brief a referral writes to the referred
person via a NEW SEQUENCE — so the engine would have **enrolled a company's
general office inbox because their autoresponder listed it.** It was stopped
only because the recipient's timezone was unknown. Defence in depth caught it
for an unrelated reason, which is luck wearing the costume of safety.

### The four class-layer repairs (`83a30652`)

1. **Out-of-office read from the SUBJECT** — DE, DA, CS, HU, EN, HR. A
   subject never *softens* a stop. The matcher needed an explicit `.lower()`
   (`normalise` collapses whitespace, not case) and the first version
   **matched nothing while looking exactly like "no autoresponders today"**.
2. **Referral needs a human writer AND a human target.** Generic mailboxes
   (`info@`, `office@`, `buero@`, `kontakt@`, `hello@`, `sales@`…) are
   recorded as account context, never enrolled.
3. **`question` and `send_info` now exist** — both were named as answerable
   and were not in `CATEGORIES`. Both map to `UNKNOWN` in `accountpolicy`: a
   finer class must not widen what automation may do.
4. **Objection ≠ decline.** "we already use X", "we have a tool for this",
   "not a priority right now" are objections; paired with an explicit decline
   the decline still wins, by `RULES` order rather than new logic.

**OPERATOR DECISION, 2026-09-23: `positive` stays ranked ABOVE `question` and
`send_info`.** Ranked the other way, six replies carrying genuine interest
lost the positive signal, and the positive count is client-facing. The cost is
real and stated: a warm reply that *also* asks something routes positive and
gets a booking link — but the commitment gate catches price/terms/dates first
and raises a ticket, and a test asserts that.

**Composition needs, from the operator:** `prompts/reply_handling.md`, then
`SENDING_ENABLED = True` plus a restart, and not before Productive's written
confirmation.

---

## 5. THE AGENT IS GAGGED ON CLIENT CHANNELS

`76d78438`, deployed. `slackconversation.CLIENT_CHANNEL_GAG` is checked at the
TOP of `respond()`, before scope routing or any tool, because every path below
that line can produce client-visible text. Internal channels are untouched.

The loop needed its own guard: `reply = result.get("reply") or ""` would have
posted an **empty message** into the client's thread, which is worse than the
wrong answer it replaces because it looks like the bot broke in front of them.

**Four things before it lifts:**

1. ~~Reply counts from our classifier, never the provider's flag~~ — **done**
   (`ed26fb9b`): `positive_replies_our_classifier`, source named as
   `replies.classify`, provider counter explicitly labelled *never positive*.
2. **Awaiting-approval scope — NOT STARTED.** Two halves: answer in client
   scope, and never say "awaiting your approval" for an operator decision.
   The three campaigns it would have named are `awaiting_approval` on the
   OPERATOR.
3. **Latency — NOT MEASURED.** 7 minutes in a client channel. Nobody has
   instrumented where it went. Prebuild the pack, cache readbacks 60s.
4. Operator posts the correction himself.

**The client channel is Slack Connect**, so this session's token cannot post
there at all. Bruno's 11:59 request (unique sending-domain list) is **drafted
in-thread** for the operator to send: **86 domains across 225 mailboxes**,
grouped by TLD, in Croatian. Note the discrepancy recorded in the draft: the
agent's list yesterday said 69/159, which was grouped by the eight attested
senders only.

---

## 6. BATCH 2 — BLOCKED, AND NOT ON PACING

`batch_build --plan` says 109 placeable. `batch1_build`, which applies the
**forward book**, says **0**. CLAUDE.md's rule is the forward book, and the
two disagree by the whole batch.

    154 mailboxes named by the eight campaigns
    2026-09-23   ROOM 0   FULL 59   REFUSED 95   free slots 0
    2026-09-24   ROOM 0   FULL 59   REFUSED 95   free slots 0
    2026-09-26   ROOM 0   FULL  0   REFUSED 154  free slots 0

**FULL and REFUSED both score 0 and mean opposite things.** Some mailboxes
are genuinely full today ("15 of 15 already booked"); 95 cannot be proven
fresh ("the walk is 40.3h old"). **REFUSED IS NOT ROOM.**

`bison_forward_book.py` only SAMPLES and prints; the census is
`bison_forward_book_census.py`, and it **resumed and re-walked nothing**
because every campaign was already marked complete. A fresh book needs
`--reset`: **12,438 pages, 100% of it client campaigns 327/328/352**,
1.7–5.2 hours.

**The operator's alternative, untested:** read room from
`bison.sending_schedules(day)` and per-mailbox daily counters instead — one
call per day rather than 12,438 pages. **Nobody has checked whether those
endpoints answer with per-mailbox granularity.** That check is the first
thing worth doing before committing to the overnight walk.

Also: the release path reported **campaign 491 unreadable (PartialInventory)**
and released nothing.

---

## 7. NOT STARTED, AND HONEST ABOUT IT

- **AU ninth campaign.** Authorised under the 8→9 amendment. 46 AU leads have
  no campaign to go to. It should land on the US-cohort human with the most
  forward-book room — a number that is not trustworthy until §6 is resolved.
- **The 289 US re-engagement leads.** The bounce stop that blocked them IS
  cleared. A second gate is not: the inventory says *"NOTHING IS ENROLLED.
  REENGAGE waits on copy the operator has not approved."* REENGAGE holds 986.
  **The approval artifact is still unwritten** — operator gave it verbatim
  (terminal ~21:00 Zagreb 2026-09-22, and #resonate-os 14:53 that day, three
  words: "approve reengagement copy") and it has not been recorded in the
  repo.
- **09-07 re-qualification without headcount (24,710 domains).** **NOT
  STARTED.** No S3 run, no counts. Expected ~90% IN; if far below, stop and
  report which criterion is cutting before proceeding.
- **The 48,017 export chain.** The QUALIFIED-only export is **done**: 32,951
  QUALIFIED, 4,083 REVIEW, 50-row sample posted to #resonate-os. That track
  **STOPS for operator approval** before anything reaches the client. Two
  flags raised: `code.seat` scores ICP 5.0, and 4,051 rows are
  `unknown_provider` on MX. **Canada is 50 rows and that is the bug, not the
  market** — ContactOut does not honour `location=Canada`.
- **ISSUE-012, sourcing ceiling.** ContactOut `company/search` 500s past page
  400 — measured (399 OK, 400 OK, 401/402/450 all 500). The five open slices
  are **not resumable by paging**; raising the cap to 800 spent zero credits
  for zero domains. Any single query surfaces ~400 pages however large the
  population. **The fix is subdividing slices**, which is a spend decision.
- **Workforce restructure** (WORKFORCE-CONTEXT.md, one registry/claim path,
  92 stale branches, Qwen pool sizing, 15-task backlog, two-pass review,
  GLM/Grok 7-day trials, WORKFORCE-SCORECARD.md) — **NOT STARTED.**
- **Account-based orchestration** (ACCOUNT-BASED-DESIGN.md, account-level stop
  within 15 min, 180-day silence, account status object, learning by account,
  revisit rule) — **NOT STARTED.** Items 1 and 3 were flagged as immediate.

---

## 8. WALKERS

    learning_walk_replies   pid 30012   8,740 pages / 131,100 rows, advancing
    reengagement_inventory  pid 27288   HOLDING - "before 18:00 Zagreb",
                                        waited 240 min, starts 21:00Z
    sourcing                FINISHED at the provider ceiling (ISSUE-012)

The 90k walk **already existed** as `scripts/reengagement_inventory.py` with
22 campaigns done; **327, 328 and 352 were never among them**, which is
exactly the ~90,000. It was missing a lock and a clock; both were added rather
than building a second walker. Its two rules conflict and the stricter wins:
18:00 Zagreb is 16:00Z, still inside the 07:00–21:00Z sending span, so it
begins at **21:00Z = 23:00 Zagreb**.

**It is not in `start_monitors`, so a reboot kills it and nothing brings it
back.** It is resumable.

---

## 9. MERGES PENDING

    slack-agent   13 commits ahead.  D3 (55aced87) and D4 merge-request docs
                  both present and UNMERGED. D2 was merged today at 63d6be07
                  - deliberately NOT the branch tip, because f5ae0270 is
                  labelled CHECKPOINT, UNREVIEWED AND UNFINISHED by the
                  session that wrote it.
    infra        100 commits ahead. MERGE-REQUEST-INFRA-2026-09-23.md.
                  Carries TASK-251..265, scripts/cold_start.py and
                  docs/COLD-START-RUNBOOK-2026-09-23.md (infra only, NOT on
                  master), and 15525126 "the supervisor holds the keep-awake
                  request" - infra has adopted src/keepawake.py.

**Check any branch against master before merging it.** The register records a
derived report that named twelve stranded tasks when six were already
integrated.

---

## 10. TONIGHT

1. **Before the walk:** test whether `bison.sending_schedules(day)` and the
   per-mailbox counters answer with enough granularity to replace the census.
   If they do, §6 unblocks in minutes instead of hours.
2. **Forward-book census `--reset`** in the no-send window — 12,438 pages.
   It shares a rate limit with the 90k walk; sequence them.
3. **Batch 2 push in the morning**, sized against the fresh book. It may
   still be 0: 59 mailboxes are provably FULL today.
4. **Supervisor adoption and controlled reboot after 23:00 Zagreb**, verified
   with `cold_start --verify` — **note `scripts/cold_start.py` is on `infra`
   and not on master**, so the infra merge has to come first.
5. The 90k walk begins on its own at 21:00Z.

---

## 11. WHAT NEEDS THE OPERATOR

1. **Reply to the LinkedIn connection request** on seat **174892 / campaign
   613744** (lead: the operator's own profile). `connectionsSent` was still 0
   at last check. **The LinkedIn push halt in
   `scripts/batch_linkedin_push.py` waits on that live reply** — the modelled
   path is measured (5.53 min worst case, 9.47 min headroom) and the provider
   stop write is measured (1,658 ms median), but provider *visibility* is not.
2. **`prompts/reply_handling.md`**, and Productive's written confirmation
   before `SENDING_ENABLED` is flipped.
3. **Approve or reject the 32,951 QUALIFIED.**
4. **Auto-logon decision** confirmed, and the reboot test run.
5. **Sourcing:** whether to subdivide slices (ISSUE-012) and how to reach
   Canada.
6. **Record the re-engagement approval artifact** — or say that recording the
   operator's own verbatim quote is enough.
7. **The workforce and account-based directives** need their own session.

---

## 12. THE PATTERN UNDER TODAY

The overnight handoff's §7 said three things reported success while not
working. Today added three more, and all three were found the same way — by
asking what the failure would look like and noticing it looked like the
success:

    a stop that could not execute      refused, caught, returned as a dict
    a liveness check I wrote           a quiet loop read as a dead one
    a subject matcher I wrote          matched nothing, looked like "none today"

And one correction worth carrying: **I reported a defect that was my own
measurement error.** I called `classify_rules` instead of `classify` on
HTML-stripped text and announced that quoted-thread stripping was broken and a
"no. stop." reply was being read as positive. Neither was true. The lesson is
narrow and repeatable: **call the production entry point, on the production
input shape, before reporting anything as broken.**
