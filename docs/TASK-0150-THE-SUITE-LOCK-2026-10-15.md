# TASK 0150 — HOW MUCH LANE TIME IS LOST WAITING FOR THE SUITE LOCK?

qwen lane, measured in `C:\Users\Zvonimir\qwc` at **`6b516b0e4`**, tree clean
before and after. Standing rules read first at their absolute path,
`C:\Users\Zvonimir\Desktop\resonate-ops\queue\_STANDING-RULES.md`.
Prerequisites closed: `0110` `9f02ce7f9`, `0120` `09e8e3ada`, `0130` `6b516b0e4`,
`0140` recorded at `LANE-qwen.md:3953`.

**Nothing in this task took, released, moved, deleted or wrote a lock.** The
lock file was read three times (23:43, 23:49:11, 00:00:22), the last two with a
self-checked `Get-CimInstance Win32_Process`. No watcher was restarted or
edited. No push or merge to master. No provider, Apify, Slack or network call.
`config/.env` not opened. No suite was run.

**Read-only reads of other lanes' worktrees, declared by path**, because the
only records of a lock wait live in them and the standing rules permit reading
what they forbid acting on. Nothing was written and no git command was run in
any of them:

    wt-glm-c-2026-10-14\work\suite_0100_candidate.out
    wt-cand-21dae6a70\work\suite_0100_reference.out
    wt-suppression-2026-10-14\work\suppression-measure\*.out|.log
    wt-glm-b-2026-10-14\scripts\suite_verdict.txt
    wt-glm-review-2026-10-14\scripts\suite_verdict.txt
    wt-suppression-2026-10-14\scripts\suite_verdict.txt
    resonate-trees\wt-integ-nine-2026-10-15\scripts\suite_verdict.txt

---

## THE ANSWER, IN ONE LINE

**Waiting is 4.87% of the day's lane time and is not the bottleneck.
70.4% of all the time the lock was held bought nothing at all, and 9 of 18
suite runs today produced a verdict somebody could actually use.**

    working time, 92 paired watcher sessions          2,163.4 min
    waiting INSIDE suitelock.acquire()  (FLOOR)         105.3 min   4.87%
    lock held by a DEAD holder                          659.3 min  30.48%
    lock held by a run nobody read                      104.4 min   4.83%
    lock held by a run later declared unusable             3.8 min   0.18%
                                                     ----------
    lock time that bought nothing                       767.6 min  35.48%
                                                                 (70.4% of held)

Against `0090`'s 72-pair window (median 16.9 min, mean 19.1 min, ~1,375 lane-min)
the wait is **7.66%**. Either way it is single digits, and the brief's own test —
"waiting time as a percentage of working time is the number that decides whether
this is worth fixing" — says **the lock queue is not worth fixing. What holds the
lock is.**

---

## 1. TOTAL LANE-MINUTES SPENT WAITING — 105.3, AND IT IS A FLOOR

**There is no wait log on this machine.** `suitelock.acquire` prints its waiting
and queue-position lines to the caller's stdout and writes nothing durable; the
lock payload is overwritten by the next holder. So a wait is only measurable
where a `queued_at`/`started_at` **pair** survived in a lane file or a captured
stdout. Ten did.

    holder   lane          queued    granted   wait_min   authority
    74780    pilotcaps     01:57:16  01:57:16      0.00   branch-run-launcher.out
    61372    suppression   02:24:06  03:34:16     70.17   LANE-glm.md:966
    76868    glm-b         03:08:04  03:17:47      9.72   TASK-0060/baseline_console.txt
    79120    glm-c         04:04:54  04:06:55      2.02   LANE-glm.md:931
    83452    glm-c         10:48:55  10:48:56      0.02   suite_0100_reference.out
    83600    glm-c         14:24:15  14:24:16      0.02   LANE-pilotcaps.md:3203
    57972    glm           15:11:04  15:11:06      0.03   LANE-pilotcaps.md:3921
    68836    pilotcaps     16:15:01  16:36:43     21.70   LANE-glm.md:1709
    77584    glm-b         21:39:17  21:39:18      0.02   LANE-suppression.md:3369
    83472    pilotcaps     22:56:18  22:57:57      1.65   the live lock file

    per lane:  suppression 70.17   pilotcaps 23.35   glm-b 9.73
               glm-c 2.05          glm 0.03
    TOTAL (FLOOR)  105.33 min = 1.76 h

**Two waits are 87% of the total and both ended on a dead holder or a clean
hand-over, not on congestion.** Eight of the ten waits were under ten minutes;
five were under two seconds.

Five more waits are recorded without a `queued_at` and are **not summed**:
`31936` (≤26m12s), `74556` (≤3m51s), `84496` (UNKNOWN), `83540` (UNKNOWN),
pilotcaps' X2 (UNKNOWN, granted ≤1s after X1 released).

**One correction to a lane's own figure.** `LANE-pilotcaps.md:4827` says its leg
"WAITED 27 minutes". Its own payload, three lines below, says
`16:15:01 → 16:36:43` = **21m42s**. The narrative number is the one that is
wrong; the measurement in the same entry is right.

### The cost that is not waiting: forgone gates

Five sessions wanted a full reference, could not have one, and said so. They
were **not idle** — all five did other work — so these minutes are not "lost
lane time". The right unit is **five merge gates not obtained**:

    webapp/0030    21:07-21:48   declined; glm-b held
    glm-b/0110     21:39-21:51   launched anyway, session died under it, NOWORK
    webapp/0030b   22:09-22:38   declined; suppression held
    pilotcaps/0160 21:40-22:14   "owes a full suite reference and does not have one"
    webapp/0040    23:04-23:52   declined; integ-nine held. THIRD CONSECUTIVE.

**webapp/0040 missed a free lock by three minutes.** It wrote `NOT OBTAINED` at
~23:52 on a holder that released at **23:55:33**, with 38 minutes still left
before its kill. One number it could not see — "how much longer is the holder
likely to run?" — cost it the gate.

---

## 2. HOW OFTEN THE LOCK IS HELD, AND FOR HOW LONG

**It is held 82.4% of the span, and 60.5% of that by a process that is not
running.** Full interval table with per-row authorities in
`docs/ops/suite_lock_timeline.py`; the arithmetic balances (union + free = span
= 1,323.1 min).

    LIVE_READ     331.5 min   30.4%   completed AND read by its own session
    LIVE_VOID       3.8 min    0.4%   completed, then declared unusable
    LIVE_ORPHAN   104.4 min    9.6%   completed, read by nobody
    DEAD          659.3 min   60.5%   holder not in the process table
    ---
    HELD        1,090.5 min   82.4% of 01:57:16 - 00:00:22
    FREE          232.6 min

Shape of the day: **17 acquisitions on the machine lock, not twenty short ones
and not one long one.** A real leg is 37–58 minutes (2,233s–3,456s measured).
Five acquisitions ran for **zero seconds** — the `0xC0000142` death where the
suite subprocess dies with the session that launched it.

The single longest hold is **402 minutes (6h42m) by dead pid 79120**,
04:06:55 → 10:48:56. Nothing was running on the machine for most of it.

### What a dead lock actually costs, stated honestly

A dead holder costs **nothing** to a lane that calls `acquire()`: the stale
takeover self-heals inside one poll, which is what six of today's runs did. It
costs only the lane that **reads the lock file and decides by hand** — and that
is precisely what webapp and suppression did, correctly, under a brief that told
them not to wait. So the 659 minutes is a **misinformation** cost, not idle
time, and it is paid exactly when a lane treats the lock file as a statement
about the machine. Invariant 0: the lock file is the authority on *who claimed
it*, never on *whether anything is running*.

### The lock failed its one job for 8.7 minutes

`83452` (glm-c's candidate, 10:48:57→11:28:01) was declared **dead while alive**
at 10:52:46, and `84496` then took the lock at 11:22:34 — so **two full suites
ran concurrently for 5.5 minutes**, plus 8.7 minutes of overlap in total across
the day. Root cause already filed by `glm/0050`: `src/suitelock.py:156`,
`return str(pid) in (out.stdout or "")` — a `tasklist` that runs and prints
nothing reads as a confident DEAD.

**And that is why `LIVE_VOID` reads as only 3.8 minutes and is the most
misleading row in the table.** 83452's run consumed **39.1 minutes of machine
capacity** and produced a complete 385-name verdict that both `glm-c` and
`pilotcaps` then declared void for contention. Lock minutes understate that loss
by an order of magnitude.

### Two runs produced results nobody will ever read

- **`83600`**, 14:24:16→15:11:06, glm-c's 0110 reference: 46.8 minutes of lock,
  **no verdict was ever written** (`wt-cand\scripts\suite_verdict.txt` is still
  the 10:52:46 zero-second file) and `LANE-glm-c.md:437`'s promised continuation
  never appeared. Its own fallback clause therefore fires: NOT OBTAINED.
- **`83472`**, 22:57:57→**23:55:33**, pilotcaps/0170's reference: **57m36s of
  lock, and it COMPLETED.** The session that launched it was `DONE` at
  22:58:54 — 57 seconds after it took the lock — so
  `LANE-pilotcaps.md:6113`'s promised §7a will never be written.

**RESCUED HERE, AT ZERO COST, because reading it is free and it is the only
complete LF-tree reference taken today:**

    C:\Users\Zvonimir\Desktop\resonate-trees\wt-integ-nine-2026-10-15\scripts\suite_verdict.txt
    status=FAIL   exit_code=1   wall_seconds=3456.1   timed_out=False
    results_reached=14928   failures=294   failures_are_partial=False
    result_line=FAILED (failures=202, errors=90, skipped=18, expected failures=25)

Branch and SHA are **cited, not re-measured**: `LANE-pilotcaps.md:6118-6122`
records the tree at `integ/canary-nine-2026-10-15` / `cc112ae60`, LF, CR=0, and
the run was launched at 22:56:18 — after `cc112ae60` (22:53). I did not run git
in that worktree, so the SHA at the moment of the run is **cited** and would be
settled by one `git -C <tree> rev-parse HEAD` from a session permitted to touch
it.

---

## 3. HOW MANY TASKS GENUINELY NEED THE FULL SUITE

Measured over **every commit on every ref this clone holds, dated 2026-10-15**
— 71 commits — against the operator's 2026-10-02 rule: *"A change under `src/`
or under `tests/` ALWAYS gets a new reference, with no exception."*

    commits today                                      71
    touch src/ or tests/   -> FULL, no exception       41   57.7%
    touch neither          -> bounded alternative      30   42.3%

So **42% of today's commits are eligible for the bounded alternative and did not
need the lock** — eligible, not exempt: the operator's rule bounds the shortcut
to files no module under `src/` imports, and still demands a per-change
measurement naming the tests that could observe the delta. The rule already
covers them; nothing new is needed. Of the 41 that do need a reference:

    code files touched (src/ + tests/)
      1 file   26 commits        <= 2 files:  33 of 41  (80.5%)
      2 files   7 commits
      3 files   2 commits
      4 files   3 commits
      5 files   1 commit
      6+        2 commits

**The changes are narrow. The modules are not.** Twelve distinct `src/` files
changed today; here is how many of the 691 test modules name each:

    src/web/app.py         618      src/lint.py            127
    src/config.py          335      src/web/pages.py        70
    src/cadence.py         236      src/bisonfactory.py     62
    src/web/api.py         165      src/providerwrites.py   53
    src/notify.py           30      src/sequencegate.py     20
    src/lanes.py             8      src/leadobserve.py       7

**A module-scoped reference is therefore unsound for most `src/` changes and the
measurement says so, not an opinion.** Touching `src/web/app.py` and scoping the
reference to the modules that name it IS the full suite.

**The one real opening: 26 of the 41 (63%) changed NO file under `src/`.** They
added or edited test files only. What can observe a tests-only delta is the
changed modules themselves plus the modules that **read the tests tree**, of
which there are **20** — 2.9% of 691:

    tests/__init__.py, tests/base.py,
    test_a_credential_is_checked_by_its_real_name, test_audit, test_campaign_audit,
    test_compliance_gate, test_deployment_config, test_invariants,
    test_a_watcher_that_prints_into_nothing_is_not_a_watcher,
    test_no_test_leaves_the_environment_changed, test_nothing_writes_to_a_provider,
    test_persistent_volume, test_preproduction, test_qwen_cli_model,
    test_research_audit, test_run, test_supervisor, test_variant_wiring,
    test_the_readback_cache_cannot_lie_about_its_age, test_web_invariants

**That list is a grep and the operator's own rule forbids exactly that:
"Not an argument from the kind of file — a measurement."** So it is a candidate,
not a finding. §6 says what one suite would cost to settle it permanently.

---

## 4. WHAT A LANE DOES TODAY WHEN IT CANNOT GET THE LOCK

Four behaviours in one night, from four lanes, under the same standing rules.

**(a) READ, COMPUTE, DECLINE — `webapp`, three times.** Read the lock, measured
the holder's liveness, computed `one leg (35-45 min) + a pair (~80 min)` against
the time left before its watcher's kill, started nothing, and wrote
`SUITE: NOT OBTAINED` with the exact recipe and `UNDONE AND NOT RE-QUEUED`.

**(b) QUEUE FIFO AND WAIT — `pilotcaps`, 16:15:01→16:36:43.** Wrote a ticket,
waited 21m42s, was granted on a clean hand-over, ran both legs, got a zero-new-
name pair. `pilotcaps/0170` did the same at 22:56:18 for 1m39s.

**(c) LAUNCH ANYWAY AND DIE — `glm-b/0110`, 21:39:18.** Launched a leg with ~12
minutes of session left. The session ended, the suite child died with it
(`scripts/suite_run.log` stops growing at 21:51:08; `DONE → NOWORK` at
21:51:09), the lane entry never grew, and the lock sat on a dead pid for a
further **9m10s** while webapp was reading it.

**(d) DETACH AND WALK AWAY — `glm-c/0110` 14:24, `pilotcaps/0170` 22:56.**
Launched under `nohup` so the run survives the session, then ended the session.
The machine works; the record does not. 104.4 minutes of lock, two complete-or-
abandoned runs, zero entries.

### Which is correct

**(b) when the time fits, (a) when it does not. (c) and (d) are both wrong, and
(d) is the more dangerous because it looks responsible.**

The decision is arithmetic, not judgement:

    wait_estimate + leg_time (+ second_leg)  <=  time_left_before_kill - write_time
        -> (b) queue and wait
    otherwise
        -> (a) decline, record NOT OBTAINED, name the recipe

### Do the standing rules say so clearly enough? NO — and here is the gap

What the rules **do** cover: (c) and (d) are already forbidden. *"Do not end a
run while anything it depends on is still running"* and *"Never write 'I will
continue when re-invoked'"* were added at 14:16 today. `pilotcaps/0170` wrote
*"§7a below is appended when the run ends"* at ~23:00 — the forbidden sentence
in different words, **nine hours after the rule landed**. The rule is not
unclear; it is not being read as covering a `nohup`.

**Recommend one sentence in the standing rules:** *a background job that
outlives the session is the same defect as "I will continue when re-invoked",
whichever tool detaches it. If it cannot finish inside the run, do not start
it.*

What the rules **do not** cover, and this is the real gap:

1. **Nothing says whether to wait or to decline.** Three lanes chose
   differently on the same night and all three were defensible. The arithmetic
   above is webapp's invention, not a rule.
2. **A lane cannot see its own deadline.** The watcher computes
   `$deadline = (Get-Date).AddMinutes($TaskTimeoutMinutes)` at
   `lane_watcher.ps1:299` and tells the child nothing. webapp reconstructed its
   kill time by reading the watcher's own log file. Every lane that does not do
   that archaeology is deciding blind.
3. **Nothing tells a lane the lock has a readable status.** `acquire` prints
   `queued at position N of M` — but only *after* you have committed to waiting.
   `glm/0050` specified `suitelock.status()` behind
   `scripts/suite_lock_status.py`; **it exists on no ref** (checked by
   `git log --all` and `git grep` across today's commits). webapp's
   `src/lanes.py` (`4650a302e`, unmerged) is a lane board and does **not** read
   the lock.

### AND THE FACT THAT MAKES (a) UNAVOIDABLE TODAY

**All five running watchers are capped at 90 minutes, and the 150-minute raise
written this evening to fix exactly this is in effect in no process.**

    lane_watcher.ps1  mtime 22:20:25   line 88: [int]$TaskTimeoutMinutes = 150
    lane_watcher.ps1.2026-10-15.bak    line 53: [int]$TaskTimeoutMinutes = 90

    five live watchers, all created 10/15/2026 21:07:08, none passing
    -TaskTimeoutMinutes, all logging  "watcher up. ... timeout=90m"
      glm-b 79568   suppression 45176   pilotcaps 78160   qwen 66028   webapp 31148

`docs/ops/WATCHER-SWAP-2026-10-15.md:104` — this lane's own `0090` — already
says it: *"nothing starts behaving differently until a watcher is restarted."*
The file was swapped at 22:20:25. No watcher was restarted. So the cap is 90,
and **a reference pair costs 78–91 minutes of suite time alone**, which cannot
fit in 90 under any lock policy. webapp's three refusals were correct arithmetic
against a constraint that a restart removes.

**This is the largest recoverable number in the task and it is not about the
lock.** Not applied: this brief forbids restarting a watcher, and it is the
operator's call.

---

## 5. WHAT IS ACTUALLY LOST — RANKED

    1  five watchers pinned at 90 min      a reference pair cannot fit. Ever.
    2  nine suite runs of eighteen         produced nothing usable or nothing read
    3  659 min of lock on a dead pid       misinforms every lane that reads it
    4  8.7 min of genuine concurrency      voided a 39-min 385-name reference
    5  105 min of real queue waiting       4.87% of the day. The smallest item.

---

## 6. PROPOSALS — EVALUATED, NOT APPLIED, EACH WITH ITS CORRECTNESS COST

**P1. Restart the five watchers so the 150-minute cap takes effect.**
*Recovers:* the difference between a cap that cannot hold a reference pair and
one that can — items 1 and, consequentially, most of 2.
*Correctness cost:* **ZERO.** It changes no gate, no threshold and no verdict;
`0090` measured zero genuine hangs in 72 records and both 90-minute hits as
productive work. The cost is operational, not epistemic: up to 90 minutes per
lane waiting for the current task to end, and `WATCHER-SWAP-2026-10-15.md`
§"step 2" already carries the exact `STOP-<lane>` / restart / readback recipe
(`timeout=150m` is the readback line).
**The smallest change that recovers the most lane time. Recommend first.**

**P2. The watcher tells the lane its deadline.** One line beside the
`GIT_CONFIG_SYSTEM` line it already sets: export `LANE_DEADLINE` (ISO) into the
child's environment.
*Recovers:* turns "wait or decline" from archaeology into arithmetic, for every
lane, permanently. Would have let webapp/0040 see it had 38 minutes left.
*Correctness cost:* **ZERO.** It adds information and removes none; no gate
reads it. The only risk is a lane *trusting* it after the watcher is restarted
with a different cap — so it must be the deadline, not the duration.
**Recommend second. It is one line and it is the difference between (a) and (b)
being a decision and being a guess.**

**P3. `_alive` must return three states, and UNKNOWN must not mean DEAD.**
`src/suitelock.py:156`. Already specified by `glm/0050` with a born-red test.
*Recovers:* item 4 — the concurrency that voids references.
*Correctness cost:* **this one cuts both ways and must not be shipped alone.**
Today the bug makes the lock too *permissive*. Fix it so an unreadable process
table reads ALIVE and a genuinely dead holder becomes *harder* to displace — the
402-minute dead hold gets a grace period added to it. The module already has the
right primitive (`DAMAGED_GRACE`, unreadable ≠ dead, 30s) and the right
philosophy; what is missing is applying it to the process table instead of the
lock file. **Ship P3 only together with P4, or the 4-minute win buys a longer
dead hold.**

**P4. Displace a holder on evidence of progress, not on a pid read.** The
payload already names the `worktree`; `scripts/suite_run.log` in that worktree
is append-only and grows continuously during a run. "Is this holder working?" is
then a file mtime — the same class of evidence as a CPU-time read, and it does
not depend on `tasklist` at all.
*Correctness cost:* **a real one, and the threshold is UNKNOWN.** A suite that
genuinely stalls longer than the threshold would be displaced mid-run, which is
the 2026-10-02 incident again. The longest gap between writes to
`suite_run.log` during a healthy run **has never been measured**, and picking a
number without it is exactly what this project forbids. *Authority that would
settle it:* one `-v` run with the log's mtime sampled every 5s; the artefact is
one file and it can ride along on the next reference anybody takes.
**Recommend measuring the gap before proposing a threshold. Do not guess it.**

**P5. A shared reference per SHA, that several lanes read instead of each
re-running.** The brief's candidate, and the one I came closest to recommending
and will not.
*Recovers:* nine complete references were taken today, at several distinct
lineages, with more than one lane needing one on or near `b1f290c84`. **How
many were genuinely duplicates is UNKNOWN** — settling it needs each run's SHA,
and four of the nine never had one recorded anywhere I could read. Plausibly
1–3 legs a day; stated as plausible, not measured.
*Correctness cost:* **a name-set is not a function of the SHA, and this project
has already measured it twice.** `qwen/0060`'s D4 found **13 names that flip
between a CRLF and an LF tree at the same SHA**. `glm-c`'s 385-vs-228
decomposition found the extra names clustering in
`test_the_deploy_can_be_rolled_back` (17), `test_the_backup_restores` (15),
`test_the_units_come_from_the_table` (14), `test_the_sessions_come_back_after_a_reboot`
(9), `test_the_secrets_checklist_never_prints_a_value` (8) and
`test_one_full_suite_at_a_time` (7) — **machine- and environment-shaped, not
commit-shaped.** A cache keyed on the SHA alone would hand one lane another
lane's environment and report a regression as a flake, or worse, a flake as
clean. The key must be (SHA, EOL regime, invocation, *and* a fingerprint of
what those environment-shaped modules read) and **the last component is not
currently measurable.**
**Recommend building the manifest as a RECORD, not a cache: it makes an existing
reference findable, and it REFUSES — not warns — on any key mismatch, because
absence of a matching key is a refusal and never a pass. Reuse only where every
key component matches exactly. That is strictly weaker than the brief's
candidate and it is the strongest version that is safe.**

**P6. A tests-only reference, scoped to the ~20 modules that read the tests
tree.** 63% of the code-touching commits today changed no `src/` file.
*Correctness cost:* **it is a new exception to a rule the operator wrote with
"no exception" in it, so it is his to grant and not mine to take** — and the
20-module list above is a grep, which is the method his own rule rejects.
**Recommend he does not grant it until one experiment is run, because it costs
one suite and settles it permanently:** add a no-op test file to a clean tree,
take a full reference with `-v`, diff by name both directions against the same
tree without it, and publish the set of modules that moved. If that set is
inside the 20, the exception is measured rather than argued. If it is not, the
candidate dies on evidence. **Either outcome is worth one suite.**

**P7. A queue position a lane can see before it decides to wait.**
`suitelock.status()` behind `scripts/suite_lock_status.py`, exactly as
`glm/0050` specified it: the holder payload; the liveness verdict **with its
evidence class** (ALIVE / DEAD-verified / UNKNOWN-not-takeable, never a bare
boolean); what `acquire` *would* do now, performing no writes; and a
self-checked sweep for suite processes not matching the holder pid.
*Recovers:* item 3 — it replaces the hand-rolled `Get-CimInstance` incantation
four lanes each wrote tonight, and it is what webapp/0040 needed at 23:52.
*Correctness cost:* **ZERO, strictly.** It writes nothing, deletes nothing and
changes no takeover logic, so UNKNOWN still never becomes a pass. **The only
proposal here with no downside at all. Recommend alongside P2.**

**NOT proposed: a module-scoped reference for `src/` changes.** §3 measures why
— 618, 335, 236, 165 and 127 test modules name the five most-changed `src/`
files, so the scope *is* the suite. A cheaper reference that misses an
interference is worse than waiting, and that rule applies to this lane's own
proposal.

**ALSO FILED, NOT PROPOSED HERE: the lock is per-CLONE, not machine-wide.**
`qwen/0060` measured it (`LANE-qwen.md:2024-2041`): this lane runs in a second
clone, so its suite takes `qwc\work\suite.lock` and serialises against nothing.
Its 18:18:16→18:55:39 run today is absent from §2's timeline for that reason.
One-line fix, already filed, and it makes the machine-wide rule true rather than
aspirational.

---

## 7. AGAINST MYSELF, AND WHAT IS UNKNOWN

- **The wait total is a FLOOR and the method cannot be improved from here.**
  There is no wait log. I recovered ten pairs from prose and captured stdout;
  there were 17 acquisitions. Five more waits are bounded or UNKNOWN and are
  excluded from the sum rather than estimated. If the true figure is double, the
  conclusion does not move: 9.7% is still not the bottleneck.
- **`LIVE_VOID` = 3.8 minutes is the most misleading number in this report,**
  and I nearly published it without the paragraph that corrects it. The run it
  describes consumed 39.1 minutes of machine capacity. Lock minutes are not
  machine minutes and I have said so where it matters.
- **I classified `84496`'s 12:00:35→14:24:16 interval as DEAD from a read taken
  at ~12:20.** The transition instant is therefore bounded, not measured: the
  holder was dead by 12:20 and the interval starts at its run's end. 20 minutes
  of the 143.7 are an inference.
- **`?(X2)`'s holder pid is UNKNOWN.** Its window is measured from the verdict;
  its identity is inferred from the one-second gap after X1 released.
- **`glm/0050`'s inference that "74780's verdict never advanced past Oct 14
  20:29" read the wrong tree.** 74780 ran in a CLONE
  (`resonate-ops\pilotcaps-ci-2026-10-15\clone`), not in `wt-pilotcaps`, and its
  run completed at 02:45:45 with `failures_are_partial=False`. The takeover at
  03:34 was still legitimate — by then the holder was 31936 — but the stated
  reason was not. Named rather than inherited.
- **The 90-vs-150 finding is measured directly** (five `CreationDate`s at
  21:07:08, the file's mtime at 22:20:25, both defaults read from the two files)
  and does not rest on any commit.
- **The threshold P4 needs is UNKNOWN** and I have refused to invent it.

---

## 8. ARTEFACTS

    qwc\docs\TASK-0150-THE-SUITE-LOCK-2026-10-15.md   this report
    qwc\docs\ops\suite_lock_timeline.py               §2, every row with its authority
    qwc\docs\ops\measure_suite_lock.py                §1's working time; the run census
    qwc\docs\ops\who_needs_a_full_suite.py            §3, offline, reads git only
    resonate-ops\qwen-0150-2026-10-15\timeline.log
    resonate-ops\qwen-0150-2026-10-15\sessions-and-runs.log
    resonate-ops\qwen-0150-2026-10-15\needs-full-suite.log
    resonate-ops\qwen-0150-2026-10-15\raw-lock-mentions.txt

All three scripts are read-only, offline, take no lock and run in under a
second. They are committed so the next session re-derives the numbers rather
than believing this document.
