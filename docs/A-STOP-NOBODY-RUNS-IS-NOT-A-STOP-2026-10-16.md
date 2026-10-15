# A stop nobody runs is not a stop — TASK-0160, 2026-10-16

Everything here was measured in `wt-suppression-2026-10-14` on branch
`task-suppression-bounce-RULE-2026-10-15` at **`495fb3206`**. The tree is a
CRLF-checkout lane tree; where that matters it is said. `origin/master` was
`b1f290c84` before this work and is `b1f290c84` after it. No provider call, no
network call, no send, no activation, nothing prospect-facing. No cap and no
gate was changed.

---

## 1. The claim, re-derived — and it stands, with one correction to its scope

TASK-0140 ended with the line that outlives its own repair:

> **Nobody runs it.** `bounce_stop_7day` and `hard_stop_check` appear in docs
> and in themselves — no service, timer, monitor or module invokes either.

Re-derived at `495fb3206` by grepping the whole tree — every `.py`, every
`.md`, every `.sh`, `.service` and `.timer`, `scripts/server/`,
`scripts/start_monitors.py`, `src/supervisor.py`'s table, the tmux and systemd
unit generators, `scripts/cold_start.py` and every `*_loop.py` and `*_watch*`
file — for `bounce_stop_7day`, `hard_stop_check` and `queue_wall_check`.

**Every hit is one of four things, and none of them is a caller:**

| what | where |
| --- | --- |
| the three scripts themselves | `scripts/bounce_stop_7day.py`, `scripts/hard_stop_check.py`, `scripts/queue_wall_check.py` |
| their own test modules, importing by path | `tests/test_the_bounce_stop_produces_a_verdict_for_every_mailbox.py`, `tests/test_four_more_campaigns_walk_into_the_same_wall.py`, `tests/test_the_largest_campaign_is_the_one_the_agent_cannot_read.py`, `tests/test_the_queue_cap_is_one_number.py` |
| prose — docstrings and comments | `src/providers/bison.py:828`, `src/slackagentreadback.py:52,58`, `src/queuewall.py:4`, `scripts/bison_watch_loop.py:133`, and 11 files under `docs/` |
| a stale suite log and `work/` scratch | `scripts/suite_run.log`, `work/suppression-measure/*` |

**Nothing invokes any of them. The claim stands.** There is no correction to
0140 on this point.

The one correction is to its *scope*: there were not two uninvoked checks but
**three**, and the third is newer than the finding.

    scripts/bounce_stop_7day.py    added 4965cd534  2026-09-22 13:28  →  24 days uninvoked
    scripts/hard_stop_check.py     added b53bd9704  2026-09-22 21:55  →  24 days uninvoked
    scripts/queue_wall_check.py    added e67cd90d3  2026-10-16 01:10  →  born uninvoked, ~9 hours

`scripts/hard_stop_check.py`'s own docstring already said why this matters, on
the day it was written:

> Written 2026-09-22 because a monitor was armed against a script of this name
> that did not exist. **It would have reported nothing, for ever, and silence
> from a hard-stop monitor is indistinguishable from safety.**

It then spent 24 days being the thing it was written to replace.

`docs/PRODUCTION-HANDOFF-2026-09-23-NIGHT.md:164` recorded it too —
"`hard_stop_check` has **no automated caller**" — on 2026-09-23. The finding
was written down, correctly, 23 days ago, and nothing came of it.

### A second declared-and-unused instrument, found on the way

`notify.STATUS_HARD_STOP` has been in `notify.ROUTES` as
`(STATUS, CRITICAL)` since 2026-09-21, with a comment calling it "the one
deliberate double route in this table". **Nothing in the repository raised
it.** Measured: the only other references are
`tests/test_status_channel_carries_no_prospect.py:62,65`, which assert its
route and its id and never produce one. A CRITICAL event type with zero
producers is the same shape as a repaired script with zero callers, one layer
further out. `scripts/stop_watchdog_loop.py` is now its first producer.

---

## 2. One runner, and the precedent it follows

**Precedent: `scripts/weekly_report_loop.py` + `src/weeklyreportwatch.py`,
registered in `src/supervisor.py`'s one monitor table.** Named because its own
docstring already describes this exact failure and its own table entry already
records this exact fix:

> `digest_loop.py` exists because `digestwatch` and `digest.announce` were both
> written, both tested, and **called by nothing** […] `slackfollowup.due()`
> shipped the same way. This is the third time, so the loop is written in the
> same commit as the module rather than after it.

and, in `supervisor.STATIC_MONITORS`:

> The Monday client report. Added 2026-09-24: the script had existed since
> 09-23 and was in no table, so nothing started it and `--status` could not
> report it missing — an absent row reads as a healthy estate.

That is this defect, verbatim, one occurrence earlier. So nothing new is
invented:

    src/stopwatchdog.py             the logic: check table, classifier, journal,
                                    gap rule, controls, assessment. Pure.
    scripts/stop_watchdog_loop.py   the process: clock, beat, printing, notify.
    src/supervisor.py               ONE new row in the ONE table.

By being one row in that table the runner inherits, with no new mechanism:
`start_monitors.py --live` starting it at logon and refusing a second copy on
two independent witnesses; `start_monitors.py --status` reporting it DOWN if it
dies; the supervisor restarting it with backoff; and
`scripts/server/generate_units.py` deriving the systemd unit from the same
table for the Linux migration.

### Two clocks, because they are not the same number

    --interval  300s   wake up and BEAT
    --every    3600s   minimum gap between full check passes

`start_monitors.STALE_SECONDS` is 1200. A process that only woke hourly would
read DOWN for forty minutes in every hour, and `--live` would then be free to
start a **second** watchdog beside the first — the two-Slack-clients failure
with a different monitor. Beating every 300s and checking every 3600s keeps
both true, and `test_the_beat_is_more_frequent_than_the_staleness_limit`
asserts the relation rather than the numbers.

### It is loud when it cannot run

The requirement was that a missing attempt be visible as a gap rather than as
silence. A heartbeat cannot do that: it is rewritten every poll, so it holds no
history and can never say that last Tuesday did not happen. So there are two
records, answering two questions:

    work/heartbeat/stop-watchdog.json   WHO IS STILL LOOKING   rewritten each tick
    work/stop-watchdog.jsonl            DID THE SCHEDULE HOLD  append-only, one
                                        row per PASS

`gaps()` names four states and none of them is a quiet zero:

    NEVER     no attempt has ever been recorded. The estate's state today.
    OPEN      the last attempt is older than the cadence allows — the
              scheduler is NOT firing now. The live one.
    MISSED    a hole between two recorded attempts. Historical.
    DAMAGED   a journal line that will not parse, so continuity either side
              of it cannot be proven.

A tick that runs no pass writes **no** journal row. Padding the record with
wake-ups would make a hole unfindable, which is the one thing it exists to
show.

### BLIND and UNDEFINED propagate, verbatim

0140's line for the estate as it stands is carried through the runner, into the
journal row, unchanged — asserted by `TheSentenceTravelsVerbatim`, which holds
the string as a literal and fails on a paraphrase:

> 7-DAY BOUNCE STOP: 0 PASS, 0 STOP, 0 BLIND - no mailbox sent for us in 7d
> across 10 campaigns read whole, so every rate is UNDEFINED and UNDEFINED is
> not a pass.

The overall verdict is the exit code and nothing else, because that is the one
vocabulary all three checks already share and documented for themselves:
`0 → PASS`, `1 → STOP`, `2 → BLIND`, **anything else → BLIND**. `3`, `-1` from
a killed child, `None` from a function that returned nothing, `"0"` as text and
a `bool` in an exit-code slot are all BLIND. The `bool` case is explicit:
`True == 1` in Python, so a success flag arriving where a code belongs would
otherwise read as a tripped STOP by arithmetic accident and `False` as a clean
PASS.

STOP wins the headline; the BLIND and GAP counts stay in the same sentence
whichever verdict won. `bounce_stop_7day._summary` learnt that one level down —
an unreadable campaign beside a stopped mailbox produced no blinded mailbox and
therefore no BLIND in its own line — and this is the same disappearance one
level up. The summary is never a tick:

    STOP WATCHDOG STOP: 1 STOP, 2 PASS, 0 BLIND of 3 check(s); 1 gap(s) in the
    record (NEVER); controls 3/3 held. DO NOT SEND until a human has read this.

---

## 3. Where a STOP surfaces — and the honest answer

**Measured, not asserted.** A planted STOP was driven through
`stop_watchdog_loop.announce` and the stored notification read back:

    type        status_hard_stop
    destination status          (notify.ROUTES, since 2026-09-21)
    severity    critical
    status      unconfigured
    channel     None

So a STOP today produces **a durable local row in `work/notifications.jsonl`
that reaches nobody.** `notify.plan` posts nothing by design;
`notify.deliver` asks `slack.post`, which refuses unless `SLACK_LIVE` is set,
and it is not set in this build. The loop says so on the line after it:

    NOTIFIED status_hard_stop status=unconfigured channel=None
          and that is NOT a message anybody received

**What it surfaces in that WILL be seen, in order of cost:**

1. **`SLACK_LIVE` set and `SLACK_STATUS_CHANNEL` naming `#resonate-os`.** This
   is the transport the product already has, `notify_deliver_loop` is already
   in the monitor table, and `#resonate-os` is the room the operator already
   reads — the operator moved status, milestones, CRITICAL, digests and
   approvals into it on 2026-09-27. Nothing needs to be built. **Recommended.**
2. **The daily digest.** `digest_loop` already posts a summary a person opens
   anyway; a STOP line in it is one more line in something already read.
3. **The exit code, read by whatever next gates a send.** Non-zero means do not
   send, and it is machine-readable without a channel at all.

If none of those is arranged, the record above is the whole story and a tripped
mailbox waits for somebody to go looking. **That is the operator's call, and it
is the one real gap this task cannot close from inside the repository.**

### A finding about the channel guard, found while avoiding it

`notify._status_payload` refuses a string shaped like an email address — and
**it does not look inside a list**: the check is `isinstance(value, str)`. A
payload forwarding the check rows would have carried every stopped mailbox's
address into the room the whole team reads, past a guard that was watching
strings. Worse, `notify.notify` cannot raise into its caller, so a refused
payload becomes a `FAILED` row and *silently stops being a notification* — the
caller has no way to know except by reading the status back.

Both are why the payload is built by hand from counts and check names, and why
there are two tests: one asserting no `@` appears anywhere in the serialised
payload even when the check summary it came from carries two addresses, and one
asserting the stored status is not `FAILED`. **`notify.py` was not changed** —
the finding is recorded here and the recommendation is one line in
`_status_payload` to walk lists and tuples.

---

## 4. The three controls, printed every pass

Three planted inputs with known answers, run on every pass, costing no provider
call and no network. If one disagrees the whole pass is BLIND — an instrument
that cannot be shown to fail is not evidence that nothing is wrong.

    CONTROL OK   an over-threshold mailbox produces STOP
                 planted: mailbox 999001, 4 bounced of 100 in-window = 4.00%
                 expected ['STOP', 1]   observed ['STOP', 1]
    CONTROL OK   an unreadable campaign produces BLIND and a non-zero exit
                 planted: campaign 491 raising PartialInventory at the cap
                 expected ['BLIND', 2]  observed ['BLIND', 2]
    CONTROL OK   a pass the scheduler never fired is a gap in the record
                 planted: three attempts on a 3600s cadence with four
                 missing, and separately an empty record
                 expected [['MISSED'], ['NEVER']]
                 observed [['MISSED'], ['NEVER']]

Controls 1 and 2 drive the **real** `scripts/bounce_stop_7day.py` through its
real exit-code path. That is what `rows_source` was added to `measure()` and
`run()` for: a seam, not a feature, defaulting to `bison.scheduled_emails`,
resolved at call time so an existing `mock.patch.object` still intercepts, and
with no production caller passing it. Control 3 drives the real `gaps()`, and
it is the one the other two cannot stand in for — without it the runner is the
B7 instrument again, clean because it never ran.

**The controls were proven able to fail**, twice, by breaking the instrument
rather than by arguing:

- `bounce_stop_7day.THRESHOLD` moved to 99.0 → control 1 observes `['CLEAR', 0]`
  and reports FAIL; the pass becomes BLIND.
- `stopwatchdog.gaps` stubbed to return `[]` → control 3 observes `[[], []]`
  and reports FAIL.

`CLEAR`, not `PASS`, in that first observation — the observed pair is the
bounce stop's **own** vocabulary carried through rather than translated, which
is also the proof that control 1 ran that script and not a stand-in.

---

## 5. The real queue wall is OVER today, and the runner says so

The one check that makes no provider call was run for real inside a full pass.
It is not clean:

    STOP  queue_wall_check   exit 1
          QUEUE WALL: QUEUE WALL REFUSES: 1 OVER (491); 4 AT-RISK on one more
          sequence step (492, 503, 504, 505) of 20 campaigns - a queue past a
          reader's cap is not read in part, it is not read at all.

That is 0150's finding, unchanged, now carried by something that asks it on a
schedule instead of waiting to be typed. **No cap was changed here** — 0150's
pagination change is still pending the operator's word and this task added no
second one.

---

## 6. The 24-day window, stated and left unnarrowed — the operator's read

0140 pinned the bounce stop as **blind since 2026-09-22**, 24 days to today,
with sends in that window UNKNOWN and bounded above by 918, and said narrowing
it needs a provider read this lane may not make. **It is left unnarrowed.**

**The exact read that would close it.** For each of the ten campaigns in
`bounce_stop_7day.OURS` (487, 489, 491–498), one fully paginated walk of
EmailBison's `scheduled_emails` at `cap=400`, keeping only rows whose `status`
is `sent` or `bounced` and whose `sent_at` falls on or after 2026-09-22, then
grouping by `sender_email.id`. That is exactly
`py -3 scripts/bounce_stop_7day.py --days 24 --json`, unmodified, against the
live workspace — the script is read-only, has zero `except` clauses that could
mask a refusal, and now returns a verdict for every mailbox or says BLIND by
name. **Cost:** one GET per page, no credits, no model spend, no write; 491 is
45 pages and the rest are small, so on the 2026-10-03 census the whole walk is
of the order of 100 requests and a couple of minutes, and the only real risk is
rate-limiting a workspace whose campaigns are all paused anyway. **What he
would learn:** the actual numerator and denominator per mailbox for the whole
blind window — whether any of the ten mailboxes was at or over 2% while nothing
was watching, or whether the window was genuinely quiet; and, from
`unattributed` and `unreadable`, whether a complete answer is even available or
the window stays bounded-above-by-918. A clean result retires the 918 bound; a
dirty one names the mailboxes that must not be used in the canary pool.

**It is his call, not this lane's,** and it does not block the runner: the
runner's first recorded pass will produce the same read as a by-product the
hour it is started.

---

## 7. What was changed, and how it was proven

    src/stopwatchdog.py             NEW   the logic
    scripts/stop_watchdog_loop.py   NEW   the process
    tests/test_a_stop_nobody_runs_is_not_a_stop.py  NEW  50 tests
    src/supervisor.py               +22   one row in the one table
    scripts/bounce_stop_7day.py     +14/-4  the `rows_source` seam
    tests/test_the_derived_table_is_the_incident_gates_15.py  +8   the ceiling
    tests/test_the_estate_comes_back_after_a_reboot.py        +4   the beat pin
    tests/test_invariants.py        +36/-3  barrier registration and ONE
                                            widened detector — see below

**Born red, three ways, each caught by a guard that already existed:**

1. `test_the_derived_set_is_exactly_the_15_plus_the_five_named_extras` failed
   with `Items in the second set but not the first: 'stop_watchdog'` the moment
   the monitor was added. That ceiling test exists so an unexplained watcher
   cannot appear; the entry was then named with its reason, as its own comment
   requires.
2. `test_the_real_table_resolves_to_the_files_the_loops_write` failed with
   `KeyError: 'stop_watchdog'`. That is the `46474c6c` guard: a declared beat
   that names a file nothing writes makes `cold_start --verify` poll forever
   and report the monitor down. Pinned to `stop-watchdog.json`, read from the
   loop's own `WATCHER` constant by AST.
3. With `src/stopwatchdog.py` and `scripts/stop_watchdog_loop.py` removed, the
   new test module does not import at all; with only the loop removed, 16 of
   its 50 names go red. Both captured. The restore is **hash-verified**:
   `src/stopwatchdog.py` md5 `24776fd92e87f91f9a642a298d87513d`,
   `scripts/stop_watchdog_loop.py` md5 `e4a8b1bdf43e2713595db59380ca3f9b`,
   identical before and after.

**Mutation-proven, four mutations, every one killed by exactly the intended
names and every revert hash-identical** —
`work/suppression-measure/0160/MUTATIONS.txt`:

| | the silent weakening | red names |
| --- | --- | --- |
| M1 | `classify`'s default answers PASS | 1, exactly as intended |
| M2 | an empty record answers "no gaps" | 6, exactly as intended |
| M3 | `assess` ignores a failed control | 2, exactly as intended |
| M4 | the gap tolerance becomes effectively infinite | 7, exactly as intended |

**M3 caught one of my own tests being wrong**, which is the reason the proof is
run rather than described. `test_a_broken_instrument_is_caught_by_its_own_control`
first passed `[]` for the check results, so `assess`'s `not results` guard
answered BLIND on its own and deleting `or bad_controls` from the verdict rule
left the test green — a different guard firing first, which is the trap
CLAUDE.md names explicitly. The test now passes a clean check and a continuous
record, so the failed control is the only thing that can make it BLIND, and M3
reddens both tests.

### The `SELF_WRITERS` detector had a blind spot, and it missed this module

`src/stopwatchdog.py` appends its journal with `os.open(..., O_APPEND)` and
`os.write` — the pattern `watchsink.record` uses — and has no
`open(..., "a", encoding=...)` and no `os.replace(`. So all three conditions in
`test_the_checklist_has_not_fallen_behind_the_code` answered False and **the
half of that pair which exists to keep the checklist honest reported nothing.**
`watchsink` was only ever caught by it because its *other* function, `beat`,
replaces a file; its appender has been invisible to that test since the day it
landed.

The detector was **widened** — a fourth way of appending is one more thing it
can see — and only then did it report `['reviewapproval', 'stopwatchdog']`.
`stopwatchdog` was then registered on the checklist and driven for real against
the real `work/` directory by
`test_every_self_writer_refuses_the_real_work_directory`, which is the
behavioural half and the one that actually matters.

**`reviewapproval` on that list is a PRE-EXISTING failure, not this task's**,
and it is left alone under the FOCUS RULE. It is filed as a task, not fixed
here.

### Test state, by name-set

| module | before (`495fb3206`) | after |
| --- | --- | --- |
| `tests/test_a_stop_nobody_runs_is_not_a_stop` | did not exist | 50 pass, 0 fail |
| `tests/test_invariants` | 3 fail | **the same 3**, and `test_the_checklist_has_not_fallen_behind_the_code`'s list is still exactly `['reviewapproval']` |
| `tests/test_the_derived_table_is_the_incident_gates_15` | 7 pass | 7 pass |
| `tests/test_the_estate_comes_back_after_a_reboot` | 30 pass | 30 pass |
| `tests/test_the_units_come_from_the_table` | pass | pass |
| `tests/test_supervisor`, `test_each_watcher_has_its_own_log`, `test_starting_a_monitor_records_witness_one`, `test_the_watcher_is_running_the_code_we_think`, `test_keepawake` | pass | pass |
| `tests/test_the_bounce_stop_produces_a_verdict_for_every_mailbox` + 3 siblings | 94 pass | 94 pass |
| `tests/test_nothing_writes_to_a_provider` | 1 fail | the same 1 (`runtime_approval_hash_probe.py`, `task425_one_account_dry_run.py` — neither mine) |
| `tests/test_fixture_hygiene` | 5 fail | the same 5, none naming a file this task created or changed |

**`test_the_checklist_has_not_fallen_behind_the_code` WAS ALREADY RED, so a
name-set merge gate cannot see this change to it.** The verification is
therefore on the assertion's *contents*, in both directions, and recorded
above: `['reviewapproval']` before, `['reviewapproval', 'stopwatchdog']` with
the detector widened and the module unregistered, `['reviewapproval']` again
once registered. A count would have shown nothing at any step.

### A line-endings fact this tree hides

`src/supervisor.py` on disk in this lane tree was **CRLF** while its index and
HEAD blob are **LF**, and `git status` called the file clean — the stat cache
was answering, not a content comparison. Touching it surfaced a 999-line
whole-file difference. It was written back as LF to match its own committed
blob, which makes the diff the +22 lines it actually is. Same for
`tests/test_the_derived_table_is_the_incident_gates_15.py`,
`tests/test_the_estate_comes_back_after_a_reboot.py` and
`tests/test_invariants.py`. **Every lane editing a long-lived tree should
expect this**: a file that `git status` calls clean may still differ from its
index, and the first edit is when you find out.

---

## 8. The one command that starts it — the operator's action, not this lane's

    py -3 scripts/start_monitors.py --live --only stop_watchdog
    py -3 scripts/start_monitors.py --status

The first pass makes real EmailBison reads — ten campaigns' queue rows, 491 at
45 pages — and that is the point: it is the read §6 describes, happening
hourly instead of never. Nothing was started by this task.

Two safe reads need no start and make no provider call:

    py -3 scripts/stop_watchdog_loop.py --controls-only   # the three controls
    py -3 scripts/stop_watchdog_loop.py --status          # read the record

`--status` today answers, correctly:

    attempts recorded: 0   cadence 3600s   tolerance 2x
    NO ATTEMPT HAS EVER BEEN RECORDED. Nothing has been checked.
    GAP NEVER    no attempt has ever been recorded, so nothing has been
                 checked. An empty record is not a clean one.
    exit 2
