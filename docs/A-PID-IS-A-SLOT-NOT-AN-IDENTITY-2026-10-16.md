# A PID is a slot, not an identity — TASK-0399, 2026-10-16

> **READ §7 FIRST. THIS IS THE SECOND INDEPENDENT FIX FOR TASK-0399.** The
> first landed at 15:10 today on `task-suppression-0399-lock-identity-2026-10-16`
> at `c85724df0`, with its own report and 12 artefacts under
> `resonate-ops\TASK-0399\`. I did not know that when I started — I did not grep
> `LANE-suppression.md` for the task id first, and the standing rule says a brief
> can arrive already done and must be re-measured rather than redone. §7 is that
> re-measurement: where the two agree, where they differ, and which should land.
> **Only one of them may: the two use different field names** (`pid_created` vs
> `pid_started`) **and so cannot read each other's locks.**

**Measured in** `wt-suppression-2026-10-14`, a **CRLF** tree, on branch
`task-suppression-0300-differ-failclosed-2026-10-16`.
Open: `HEAD` `3a87a6479`, `origin/master` `b1f290c84`.
Close: `HEAD` `79e1878e8`, `origin/master` **still** `b1f290c84`.

`src/suitelock.py` was blob `12de2433e` at `HEAD`, local `master`,
`origin/master`, `b1f290c84` **and** the main checkout's own branch tip
`87fa57080` — all five the same bytes. So every line quoted below is also the
main checkout's line, and the fix applies to it unchanged.

---

## 1. What the lock records, and whether any of it is an identity

The writer is `acquire`, `src/suitelock.py:417-421` **in the pre-fix file**
(`:700-718` after the change). The readers are `read` (`:168`), `_alive`
(`:132`), `_takeable` (`:236`), `_live_tickets` (`:336`) and `release`
(`:482`).

| field | written at | recyclable / reusable / forgeable |
|---|---|---|
| `pid` | `:417` `os.getpid()` | **RECYCLABLE by the OS.** This is the defect. |
| `branch` | `:417` `_label(branch)` | Reusable and forgeable — free text, or a short SHA. Many runs share one. |
| `worktree` | `:418` `abspath(getcwd())` | Reusable — every run from a given tree writes the same string. |
| `queued_at` | `:419` `strftime` | Reusable. Naive local time, **second** resolution, no offset. |
| `started_at` | `:431` `strftime` at grant | Reusable, same shape. |
| `lock_path` | `:421` | Constant. |
| `damaged` | not written — injected by `read` on a parse failure (`:179`) | n/a |

**Not one of the seven is an identity.** Six repeat across runs and the seventh
is a number the kernel re-issues. The only reader that decides whether the file
gets deleted, `_takeable:246`, consults exactly one of them:

    if _alive(holder.get("pid")):
        return False

`_alive` is correct about the PID. The PID is not the holder. My own 0395
measurement is the proof: pid 79548 answered DEAD and then ALIVE four minutes
apart, because Windows briefly recycled that number onto a transient process of
my own shell.

**And the same defect sits on the destructive side, which nothing had named.**
`release:493` guarded on `holder.get("pid") != os.getpid()` and nothing else, so
once the OS handed a lock holder's number to this process, `release` would
delete a **live** suite's lock and return `True`.

### Could the existing fields be made to answer?

`started_at` happens to equal the live holder's creation second today, but that
is coincidence: `started_at` is stamped **at grant**, documented at `:401-416`,
so a run that queued for 39 minutes has a `started_at` 39 minutes after its
process began. It cannot serve as an identity. The stamp has to be recorded
explicitly.

## 2. What identity is actually obtainable — verified, not asserted

Process **creation time** paired with the PID is the usual answer on Windows. I
measured it rather than repeating it. `OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION)`
+ `GetProcessTimes`, four targets, all four branches reached deliberately:

| target | result |
|---|---|
| this process | OK, created `2026-10-16T14:44:15.140948Z` |
| **pid 99260 — another session's process** | OK, created `2026-10-16T14:39:43.055856Z` |
| `csrss.exe`, `wininit.exe` | `OpenProcess` fails **5, ACCESS_DENIED** |
| pid 999997, never existed | `OpenProcess` fails **87, INVALID_PARAMETER** |

The second row is the one the fix rests on, and it was the open question: **the
creation time of a process this reader does not own IS obtainable, to the
microsecond.** 99260 was the live suite holding the real machine lock at the
time, and its stamp matched that lock's own `started_at` of 16:39:43.

Two findings that change the design:

**ACCESS_DENIED is reachable, so "unobtainable" is a real state.** A protected
process's number is in use *and* unreadable. That is neither alive-as-holder nor
dead, and a bool cannot carry it.

**A reaped process with an open handle still opens and still reports a creation
time.** Measured: pid 67800, created `14:44:16.186564Z`, exited
`14:44:16.214101Z` — 28 ms later — and `OpenProcess` succeeded for it *after* it
was reaped, because a `Popen` object still held a handle. A reader that took
openability for liveness would call that corpse the holder for as long as the
handle lived. **The exit time has to be read, not just the open.** I would have
shipped this bug.

## 3. The fix

`holder_state(file_path, holder) -> (state, reason)` replaces the bool, with
three states. `_pid_identity(pid) -> (ALIVE|DEAD|UNKNOWN, token)` underneath it.

- `dead-pid` → **STALE**. A machine that lost power mid-suite still needs no human.
- `identity-unreadable` → **UNKNOWN → WAIT.** A state of its own precisely so a
  later refactor cannot fold it into either neighbour.
- `pid-recycled` → **STALE**, by either of two independent proofs.
- `damaged-within-grace` → **HELD**, unchanged (`DAMAGED_GRACE`, 2026-10-02).

**Two recycle proofs, because one of them does not work on the lock currently on
disk.** The exact check compares the recorded stamp — but only locks written by
the fixed code carry one. The ordering check retrofits onto the rest: *a process
cannot publish a file before it existed*, so a creation time later than the lock
file's own mtime proves the pid is not the holder, whatever the lock records.
Both numbers are absolute (a FILETIME and an `st_mtime`), which is why the
comparison is deliberately **not** against `queued_at` — parsing that naive
local string across a DST transition can be an hour out, and an hour out in the
wrong direction reads a live holder as recycled, which is fail-open.

`CLOCK_SLACK` is **60 s**, and the sizing is asymmetric on purpose. Too small
and a true holder is misread as recycled and its lock **deleted** — the
catastrophe. Too large and a recycle inside the window escapes *this* check
only, while the exact check still catches it with no tolerance at all. Measured
reference: the real holder was created **0.584 s before** its own lock's mtime;
the real recycle reissued a number roughly **80 minutes** after the lock was
written.

`release` now checks the stamp too, and an old-format lock of ours stays
releasable — otherwise the first run after this lands would leave a lock nothing
ever clears.

## 4. Controls

`scripts/suitelock_recycle_controls.py` imports the **pre-fix module** from blob
`12de2433e` via `git show` and prints both readers side by side. Not a
reconstruction — the bytes that are on master now.

| | current reader | fixed reader |
|---|---|---|
| **C1a** recorded stamp disagrees, pid live | `HELD (keep waiting)` | `STALE` — `pid-recycled (recorded ft:1343663`**`51`**`054967697, now ft:1343663`**`61`**`054967697)` |
| **C1b** old-format lock, pid appeared 61 s later | `HELD (keep waiting)` | `STALE` — `pid-recycled (created after the lock file was written)` |
| **C2** live holder that called `acquire` itself | `HELD` | `HELD` — `identity-matches`; `acquire` raises `SuiteBusy` |
| **C3** died at process start, lock age 0.0 s | `STALE` | `STALE` — `dead-pid` |
| **C4** pid is a protected system process | `HELD` | `UNKNOWN` — `identity-unreadable`; `acquire` raises `SuiteBusy` |
| **C5** live holder advertising a 150-minute hold | `HELD` | `HELD` — `identity-matches` |

**C1 is the task, and C1b is the real case.** No timestamp is manipulated in
C1b: the lock is written, 61 real seconds pass, and only then is the process
created — measured `+61.000 s` relative to the lock file. That is the sequence
the ghost followed.

**C3's reason is named, not aged.** The lock is 0.0 s old when it is called
stale, so no age threshold can be what fired, and the reason asserts literally
as `dead-pid`. The current reader also gets C3 right — as I said in 0395, that
ghost was always takeable. **The danger was never C3; it was C1 flipping C3's
answer** the moment the number got reissued.

**C4 is honest about what changed: the action, no; the reason, yes.** The old
reader also waited — because `_alive` turned "cannot read" into "alive", which
*happened* to be safe. It never fail-opened on UNKNOWN; it fail-opened on
**recycle**, reporting a lock nobody held as held and blocking every lane. What
C4 buys is that UNKNOWN is now a distinct, named state that cannot be quietly
collapsed into DEAD later.

**C5 pins the reader in both directions.** Stale at an age of zero (C3) and held
at an advertised 150 minutes (C5) together prove age is not the criterion either
way. The unmanipulated witness is the **real** machine lock, read-only: 20.2
minutes old, live holder, `HELD (pid-only-no-recorded-identity)`.

### Mutation proof — six mutations, six kills, no collateral

Applied to the **committed** bytes (an uncommitted fix dies in the restore),
`__pycache__` cleared before every run (.pyc invalidation is whole-second), and
restored by writing the backup bytes back, proven by sha256 `ddff549c…` each
time — not by `git status`, which calls 2482 of 2588 byte-divergent files clean.

| mutation | killed by |
|---|---|
| M1 UNKNOWN collapses into STALE (fail-open) | `test_an_unknown_holder_is_waited_on_and_never_taken` |
| M2 recorded-stamp comparison dropped | `test_a_recycled_pid_is_stale_not_held` |
| M3 ordering retrofit always answers no | `test_an_old_format_lock_whose_pid_appeared_later_is_stale` |
| M4 exit time ignored, corpse reads alive | `test_a_reaped_process_whose_handle_is_still_open_is_dead` |
| M5 lock stops recording a stamp | `test_the_lock_records_an_identity_and_not_only_a_pid` + its control |
| M6 `release` back to pid equality | `test_release_will_not_delete_a_lock_a_different_process_took` |

Each kill is by the test that **observes that guard** — not a test that reddens
for any edit to the file, which is how every mutation can look killed.

`py -3 -m unittest tests.test_one_full_suite_at_a_time -v` → **51 tests, OK.**
36 pre-existing, 15 new. **No full suite was started and the machine-wide lock
was never taken.**

## 5. What this does NOT cover

- **The lock on disk right now carries no stamp**, so only the weaker ordering
  check protects it. The exact check begins working with the first lock the
  fixed code writes.
- **POSIX is unmeasured.** `/proc/<pid>/stat` field 22 is implemented; this
  machine is Windows 11 and I did not run it. Where no stamp is obtainable the
  lock records `identity: "pid-only"` and the reader degrades to exactly the old
  behaviour — stated, not hidden.
- The `recorded and not token` UNKNOWN branch is fixture-covered (patched
  `_pid_identity`). The ACCESS_DENIED branch is covered with **no mock at all**,
  via pid 4.
- **Queue tickets still carry only a pid**, by construction — a ticket name has
  nowhere to put a stamp. A recycled waiter's pid can therefore hold its place
  in the FIFO. That costs fairness, never serialisation, and is filed rather
  than fixed (FOCUS RULE).
- `_takeable` keeps its name and signature, so every existing call site and test
  is unchanged.

## 6. Applying it to the main checkout — NOT DONE BY THIS LANE

This lane may not touch the main checkout, so the change sits on
`task-suppression-0300-differ-failclosed-2026-10-16` at `79e1878e8` and was not
applied there.

**It needs no push.** A worktree shares `.git` with the main checkout — that is
what `--git-common-dir` resolves — so the branch is already visible from it.

The change is not a few lines: `src/suitelock.py` is +392/-36. By function, in
the post-fix file:

- **replaced** `_alive` (pre-fix `:132-165`) with `_alive_tasklist` `:207`,
  `_pid_identity_windows` `:230`, `_pid_identity_posix` `:286`, `_pid_identity`
  `:324`, and a two-line `_alive` `:370`
- **replaced** `_takeable` (pre-fix `:236-254`) with `_created_after_the_lock`
  `:450`, `holder_state` `:475`, `_takeable` `:541`
- **added** constants `:86-155`
- **`acquire`**: payload `:708-718`, takeover and waiting messages `:740-749`,
  `SuiteBusy` `:755-762`
- **`release`**: stamp check `:801-811`

So a hand replaces the three files whole. The committed blob is **LF**, which
matches the main checkout.

Two things to check first, because the main checkout is **not** on `master` — it
is on `task-sandbox-phase2-horizon` at `87fa57080` — and a long-lived tree can
hold mutated source while `git status` calls it clean:

1. `git -C <main> status --porcelain -- src/suitelock.py` is empty, and
2. `git -C <main> rev-parse HEAD:src/suitelock.py` is still `12de2433e`.

Then, from the main checkout, one command:

```
git checkout task-suppression-0300-differ-failclosed-2026-10-16 -- src/suitelock.py tests/test_one_full_suite_at_a_time.py scripts/suitelock_recycle_controls.py
```

That stages the three files without moving the branch. It does not touch
`master` and it does not push.

## 7. The other TASK-0399 — re-measured

TASK-0399 was already done at **15:10** today, on
`task-suppression-0399-lock-identity-2026-10-16` at **`c85724df0`**
(`src/suitelock.py` +280/-24, plus
`tests/test_the_suite_lock_holder_is_a_process_not_a_number.py`, 483 lines).
`LANE-suppression.md:16524` carries its entry. A later session recorded at
`:17148` that it *"did not re-measure its content — that belongs to a 0399
session"*. This is that re-measurement, made by reading `c85724df0`'s bytes and
running both readers side by side, not by reading its report.

**I duplicated it because I did not grep the lane file for the task id before
starting.** The brief gave no hint, and the dispatcher never clears
`queue/<lane>/`, so RUNNING held a brief whose work already existed. The cost is
this session; the lesson is one grep.

### Where the two agree — independently

Both reach the same diagnosis and the same core instrument: pid + process
creation time, via `OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION)` and
`GetProcessTimes`; both use `87` for absent and `5` for unreadable; both add a
three-state verdict with a named reason (`HELD / STALE / UNIDENTIFIABLE` there,
`HELD / STALE / UNKNOWN` here); both refuse to take an unreadable identity; both
keep `DAMAGED_GRACE`; both implement `/proc` field 22 for POSIX; and **both
independently found the handle-outlives-the-process trap** — its comment reads
*"A HANDLE OUTLIVES ITS PROCESS, and `GetProcessTimes` still answers for a dead
one"*. Two sessions, same measurement. That is the finding corroborated.

### Three differences, measured

**1. `release` is unfixed in `c85724df0`** (`:714-731`). It still guards on
`holder.get("pid") != os.getpid()` and nothing else — so the identical recycle
defect remains on the **destructive** side, where a recycled number deletes a
live suite's lock and returns `True`. Mine checks the stamp (`:801-811`,
`test_release_will_not_delete_a_lock_a_different_process_took`, killed by M6).

**2. A token-less lock whose number was recycled onto a live process is
PERMANENTLY un-takeable there.** `c85724df0:335` returns `UNIDENTIFIABLE` when
`pid_created` is absent and the pid is alive. Every lock written before either
fix lands has no such field — **including the one on this machine right now**.

Its `_alive` check runs first, so the ordinary case (holder died, number not
reused) is still recovered. The gap is exactly the 0395 scenario: ghost lock,
number reissued to something live. There, `c85724df0` wedges the machine until a
human deletes the file — the one outcome the module's founding rule, *"a machine
that lost power mid-suite must not need a human to delete a file"*, exists to
prevent. My ordering check (`_created_after_the_lock`) recovers it automatically,
and **only on a proof**: a process cannot publish a file before it existed.

Where it cannot prove, mine answers `HELD` and `c85724df0` answers
`UNIDENTIFIABLE` — **different labels, identical action: not takeable.** So mine
is strictly more recoverable at equal safety. This was a deliberate choice there,
not an oversight, and it is the one difference an operator might reasonably
decide the other way.

**3. `c85724df0` reads liveness through `GetExitCodeProcess` and compares to
`STILL_ACTIVE` (259), which cannot distinguish "running" from "exited with
code 259".** Measured, both readers, same children:

| case | PRIOR `c85724df0` | MINE `79e1878e8` |
|---|---|---|
| child exited with code 0 | `GONE (exited with code 0)` | `DEAD` |
| child exited with code 1 | `GONE (exited with code 1)` | `DEAD` |
| **child exited with code 259** | **`ALIVE (STILL_ACTIVE)`** | `DEAD` |
| CONTROL: a genuinely live process | `ALIVE (STILL_ACTIVE)` | `ALIVE` |

A dead holder reading ALIVE wedges the lock permanently — with a stamp it reads
`HELD` forever, without one `UNIDENTIFIABLE` forever.

**Reachability is low and I am not inflating it.** `run_suite.py:135` returns
`proc.returncode` from the inner unittest process, which is 0 or 1, or 124 on the
watchdog timeout. Reaching 259 needs a `TerminateProcess` carrying that code or a
deliberate `sys.exit(259)`. But the exit FILETIME has **no** ambiguous value, so
there is no reason to carry the risk at all: `exit_ft != 0` means exited, full
stop.

### Recommendation — the operator's call, not mine

**Land `c85724df0` as the base and add my three deltas**, rather than landing
mine whole. It was first, it carries the report and 12 artefacts, its 483-line
test file is larger than my 280 lines, and its structure is sound. The three
additions are small and each has a test and a mutation kill:

1. the stamp check in `release`;
2. `_created_after_the_lock`, so a legacy ghost with a live recycled number is
   recovered without a human;
3. `exit_ft != 0` in place of `code == STILL_ACTIVE`.

**Whichever lands, only one may** — `pid_created` and `pid_started` are different
field names, so a lock written by one reads as token-less to the other, silently
degrading it to the weak check. That is a merge hazard, not a runtime one, and it
is the reason this must not be resolved by merging both branches.

Neither is applied. `origin/master` is `b1f290c84` at open and at close.
