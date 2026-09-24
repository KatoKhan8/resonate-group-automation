# Production handoff — 2026-09-24 morning

For a session with no conversation context. **Supersedes
`docs/PRODUCTION-HANDOFF-2026-09-23-NIGHT.md`.**

Master is at `522495b3` and **pushed**. The night handoff's §1 is superseded
in one important way: its account of the blank emails was wrong about the
cause, and §1 below replaces it.

**NOTHING HAS PUSHED TO A CAMPAIGN SINCE THE INCIDENT.** The operator's gate
held: supply resumes only after the incident gate, and the gate is now done.

---

## 1. THE 76 BLANK EMAILS — ROOT CAUSE, AND IT IS NOT WHAT THE NIGHT HANDOFF SAID

`docs/INCIDENT-2026-09-23-BLANK-EMAILS.md` is the full write-up.
`ISSUE-025` in the register is the row.

**73 of the 76 went to leads our factory never created.** Every scheduled row
in 487–498 was attributed by asking whether its lead carries `record_id` and
`contact_key`, the two variables `bisonfactory` always writes:

    FOREIGN  sent/blank 73   stopped/blank 101   sent/ok 1
    factory  sent/blank  3   sent/ok      581    scheduled/ok 543

**The mechanism, confirmed in code and against the provider.**
`bison.create_lead` answers *"email has already been taken"* when the address
is **in the client's own estate**, not only when we lost a race with
ourselves. The branch called `find_lead_by_email`, got THEIR months-old lead —
carrying `headline` and `location` and none of our copy — recorded its id as
ours, and attached it **without ever writing our variables**. Our steps are
pure merge templates (`{SUBJECT_1}`, `<p>{BODY_1}</p>`), so the provider
rendered against nothing and sent `<p></p>`.

    foreign leads in 491-498                                   91
    recorded in OUR store as `bison_lead_id` on OUR contacts    90
    `sequence_finished` members of the client's campaign 352     85
    members of the client's 327 / 328                      55 / 23
    created_at 2026-04-08 / 2026-04-23                     55 / 23
    control: factory leads in 327/328/352             0 and 1 of 120

**We attached them. Nobody else did.** The action ledger cannot say so — it
records no bison lead attachment at all, so its silence was never evidence.

**REFUTED: the revive lane did not do this.** Two independent grounds — the
lane has no attach path (`reengagement_inventory.py` is read-only,
`revival.py` makes no provider calls), and **0 of the 91** appear in its
1,415-row inventory. All eight campaigns are `lanes=['domains']`, created
fresh at 19:18Z on 09-21, not from a list. It is a lane crossing by a
different route.

**The three that were ours are the half that survives fixing the first.**
Leads 141278, 190068 and 140657 carry correct copy TODAY and still sent blank:
all three were patched at 13:58, up to 54 minutes AFTER the empty row had been
queued and sent. **The render is a snapshot. Patching a lead does not rebuild
an existing queue row**, so a guard that reads the lead sees perfect copy and
the prospect still got nothing.

### Containment, measured

85 of 91 already stopped. The 2 still `in_sequence` were stopped and read back
`stopped`. The 4 `replied` hold **0 sendable rows each**, verified per lead.

**THE PROVIDER WILL NOT MOVE A `replied` LEAD TO `stopped`** —
`stop-future-emails` returns it as `replied` and leaves it there. Do not read
a `replied` row as unprotected, and do not retry the stop expecting it to
change.

---

## 2. THE GATE IS DONE — `5c9fb515`, `7bb23d6d`

One predicate, `src/emptyrender.py`, used by both controls, so they cannot
drift. Four shapes, each from the incident: `EMPTY` (`''`, `<p></p>`,
`&nbsp;`), `LITERAL_NONE`, `PLACEHOLDER` (`{BODY_1}` surviving into a rendered
row), `SUBJECT_RE_ONLY` (a bare `Re:` — the empty case wearing the thread's
clothes).

    (a) push guard    `bisonfactory._refuse_blank_render` reads the PROVIDER's
                      rendered queue. Zero rows read is recorded as
                      `blank_render_verified: False`, NEVER as a pass. An
                      unreadable queue refuses outright.
    (b) watcher check `scripts/bison_watch_loop` scans every scheduled row of
                      every active campaign every cycle, on rows `snapshot`
                      already paid for, regardless of whose lead it is. Runs
                      BEFORE the first-cycle early return.
    (c) fixture       `tests/test_a_blank_email_can_never_be_sent_again.py`,
                      24 tests on real shapes off step 4769 and lead 167865.
    structural        `_refuse_unvariabled_leads` — never attach a lead whose
                      copy is not already on it, read back from the provider.
                      An invariant over `ids`, not a patch to one branch.

**CONTROL (b)'s FIRST EXERCISE HALTED NOTHING, and that is why it now works.**
The pause was refused — *"no RESONATE_PROVIDER_WRITES and no allow_writes()
scope"*, `work/provider-write-refusals.jsonl` 20:18:58Z. A watcher is a reader
and holds no write scope, so the control was an alert dressed as a halt. It
now opens `allow_writes(only=PAUSE_ROUTES)` — narrow in time AND in power — and
a test asserts the same scope does **not** reach attach-leads.

**THE FAKES NOW RENDER.** `tests/fakebison.RendersTheQueue` substitutes each
lead's variables into the step template and substitutes NOTHING where one is
absent. A `scheduled_emails` stub returning `[]` would have kept all 782 tests
green while modelling away the entire incident.

Verified live: 491's running watcher carries `blanks: {pending 0, already 92}`
in its heartbeat. Across all ten campaigns: **0 pending, 177 already** — and
177 is exactly the 174 foreign + 3 factory blanks attributed independently.

**Watchers for 496, 497 and 498 are up.** `supervisor.MONITORS` had been
missing **491–498 entirely**, not just the three. Both tables now read 15.

---

## 3. THE REBOOT DRILL — DEFERRED, DELIBERATELY, AND NOT ATTEMPTED

**Do not run it until §3.1 and §3.2 are done.** Operator instruction was: if
any monitor does not come back UP with two witnesses within ten minutes, stop
and report, and do not fix live at midnight.

`cold_start --verify` run at 22:50 against the HEALTHY estate:

    0 of 15 monitors have two witnesses.
    gave up after 64s; still not up: <all 15>

…while the table it prints directly underneath shows all 15 beating, most
within 60 seconds, and `start_monitors --status` independently reports 15 UP.
**The instrument is broken before any reboot.** Rebooting to discover that is
not a drill.

### 3.1 The monitor-name → heartbeat-file mapping

    supervisor.MONITORS      heartbeat file on disk
    reply_watch              replies
    notify_deliver           notify-deliver
    bison_watch_491          bison-491
    heyreach_watch           heyreach-605732
    slack_agent              slack-agent

Only `digest` matches. **Adopt infra `46474c6c` or later**, which the night
handoff already named as the fix. It was not adopted before the witness was
tested, and it should have been.

### 3.2 Witness 1 needs a supervisor state file that does not exist

Loops are started by `scripts/start_monitors.py`, not `scripts/supervise.py`,
so nothing writes the state file `cold_start` reads for its live-process
witness. **Even a correct name mapping leaves witness 1 unsatisfiable on this
deployment.** Whether the supervisor actually runs is an open decision, and
the drill depends on the answer.

Also surfaced: `bison_mailbox_utilisation` is in `supervisor.MONITORS`, has no
heartbeat file and is not running; `slack-followup` is running and is **not**
in `supervisor.MONITORS`.

**Plan: adopt `46474c6c+`, reconcile the two tables onto one naming scheme,
decide the supervisor question, then drill — in the no-send window, not at
midnight.** About an hour.

---

## 4. THE REMOVE-LEAD VERB — APPROVED, NOT BUILT

**OPERATOR DECISION 2026-09-24**, on ISSUE-025: add a **narrow
remove-lead-from-campaign write verb** — route-scoped, reason recorded, and
**refused for any lead that is ours** — so foreign leads can be DETACHED from
491–498 rather than only stopped. **Not urgent; after the drafts.**

Today there is no such route on `bison.WRITE_ROUTES`, which is why the 91
foreign leads are stopped and still attached. Stopping was enough for safety —
0 sendable rows anywhere — and detaching is the hygiene half.

The verb belongs beside `stop_lead` and inherits `PAUSE_ROUTES`' shape: a
route fragment, never a whole URL.

---

## 5. THE 76 DRAFTS — WRITTEN, POSTED, NOTHING SENT

**Posted to `#resonate-os` (C0C3C6MDN9L), grouped by sender, Paul Bradley
first**, 2026-09-24:
<https://resonategroup-hq.slack.com/archives/C0C3C6MDN9L/p1790235029725279>

    sender   recipients
    A            42
    B            21
    C             7
    D             5
    unattributed  1

One file per sender under `work/apology-drafts-2026-09-23/`, named for that
sender. **The names are not repeated here**: the hygiene guard forbids real
seat-holder identifiers in tracked files, and a handoff is a tracked file.
Read the directory for who is who.

All 76 have approved step-1 copy, so every draft is apology + the real first
email. **Under `work/` because they carry prospect names and addresses**, and
`work/` is gitignored — the hygiene guard forbids them in a tracked file.

**NOTHING HAS BEEN SENT AND THE SYSTEM WILL NOT SEND ANY OF IT.** Each is for
a person to edit and send by hand from the mailbox named above it.

**The operator's named-first recipient is lead 167877** — campaign 497, blank
sent 2026-09-23 13:15:38Z, sender D, and one of the four who replied to a
blank. The four repliers are first in every file and marked: they are owed an
answer, not just an apology. The other three are leads 142778 (491), 204548
and 142663 (492).

A SENDER OWNS MANY MAILBOXES. **53 mailboxes carried these 76 emails across
five people**, and the local part is not the person: one sender's mailboxes
are spelled `<first>.<last>@`, `<last>@`, `<first>@`, `<first>.<initial>@` and
one live misspelling of the surname. Grouping on the first token put one
person's apologies in three files. `_PEOPLE` in the generator maps mailbox to
person; group by person.

---

## 6. THE WORKFORCE

**Qwen: 8 dispatched, 7 expected still running** on `qwen-worker-*-r58`
branches. TASK-266, 267, 268, 269, 271, 272, 273 and TASK-274. Check
`work/../pool-logs/*.r58.log` and `py -3 scripts/claim_task.py --status`
before assuming any are alive — this machine has lost workers without warning.

**TASK-270 self-blocked on TASK-247** and was right to: `lane_for` is not in
`src/` and the task forbids inlining a third copy. TASK-247 is in TODO and is
**not `ready`** (unmet deps). Unblocking 270 means doing 247 first.

**TASK-274 is new** — the agent's knowledge pack carries no cross-channel
stop. It found this itself, live, said *"I'm reasoning, not reporting"* rather
than bluffing, and was correct. The pack is the defect; the answer was the
behaviour to keep.

**`scripts/pool_dispatch.sh` is new**: dispatch NAMED tasks to named workers.
`pool.sh` has only `next_ready`, which is right for a queue and wrong for an
instruction. It refuses a task master does not carry — measured, after a
worker spent 29 seconds correctly proving an uncommitted task file did not
exist.

**GLM: three reviews queued and now unblocked**, the gate code having landed —
(1) the empty-body push guard and watcher check: any path by which an empty or
placeholder step still reaches the provider; (2) the account-level reply stop;
(3) the research-pack renderer. Scorecard: findings raised vs accepted.

**Grok: three answered**, `docs/GROK-PROVIDER-RESEARCH-2026-09-23-NIGHT.md`.
The load-bearing finding: EmailBison's variable-injection timing,
empty-variable behaviour and any pre-send render readback are all **NOT
DOCUMENTED** by the vendor. Control (a) cannot rest on a documented guarantee
and must read the queue back — which it does.

---

## 7. STILL NOT STARTED

Operator decisions 3, 4 and 5 (personalisation bar; account-level reply stop;
account targeting and multi-contact plan) — 4 is next in the stated order, then
3 and 5 together in the next batch. The research pack and copy lint. Roles from
Slack membership. The provider event write-back to the ledger, which blocks
account status and Phase D item 4. Client-two preparation (runbook, per-
workspace provider credentials, synthetic dry run, readiness report). rules-4.
The `'None'` writer — factory leads carry the literal string in
`body_4..6`/`subject_2..6` and **nothing found has been shown to write it**;
it is one step of cadence growth from sending the word "None" to a prospect,
and the gate refuses it, but the source is unknown.

---

## 8. THE PATTERN, AGAIN

**A guard that reports clean on an empty read.** Control (a) can legitimately
find no queue to look at, and calling that a pass would have made it ceremony
for ever. It records `blank_render_verified: False` instead.

**A control that cannot act.** Control (b) alerted and halted nothing, because
a watcher holds no write scope. It looked exactly like a working halt.

**A fixture that models the bug away.** `scheduled_emails` returning `[]` keeps
782 tests green and proves nothing. The fakes render now.

**A merge that discards the work it was merging.** `git checkout --ours` takes
the WHOLE FILE, not the conflicting hunk; the first attempt at the agent merge
silently dropped 111 lines of `working_on` that had merged cleanly. Four tests
caught it. Resolve hunk by hunk.

And the one that cost the incident: **every guard we had inspected the leads we
stage, and the leads that sent blank were in that set as an address only.**
There is exactly one object that answers "what will this person receive", and
it is the provider's rendered queue row.
