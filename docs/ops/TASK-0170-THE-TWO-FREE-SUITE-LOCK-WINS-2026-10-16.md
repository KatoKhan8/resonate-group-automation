# TASK 0170 — the two suite-lock changes with zero correctness cost

**Written by qwen TASK 0171 on 2026-10-16, not by 0170.** 0170 built both
features and was cut off before it committed, proved or recorded any of them.
This is the report its brief asked for, filled in by the task sent to find out
whether it had finished. The code is 0170's; the proof in section 3 and the
paragraph in section 4 are 0171's, because they did not exist.

It is worth being precise about "orphan", because the estate's records currently
say something stronger than the evidence supports: 0170's watcher and 0170's task
appear to have **stopped together at ~01:13**, not to have come apart with the
task surviving. See section 3 of
`TASK-0171-DID-AN-ORPHAN-FINISH-0170-2026-10-16.md`.

Measured at `119d545965cf689757c5242495f123a2df0188c1`, branch
`task-qwen-0090-watcher-treekill-2026-10-15`, derived rather than typed. That
SHA is reachable from `4bdb3a213` (0160's commit), and the committed blobs — not
just the working tree — contain `LANE_DEADLINE` in `lane_watcher.ps1`,
`def status(` in `suitelock.py`, `--legs` in `run_suite.py` and `def decide(` in
`lanedeadline.py`. `origin/master` is `b1f290c84`, untouched.

## 1. `LANE_DEADLINE` in the child environment — BUILT

The watcher computes the kill time **before** `Start-Process` and exports it as
`$env:LANE_DEADLINE`, an ISO-8601 instant with local offset, then clears it when
the task ends. `src/lanedeadline.py` parses it and `decide()` answers whether a
run of *n* suite legs fits in the remainder, naming the arithmetic. `run_suite.py
--legs N` refuses a leg that cannot finish, **before taking the lock** and
**again after the queue wait**, because the wait spends the minutes the leg
needs.

Three design choices are load-bearing and all three are 0170's:

- **The instant, never the duration.** A duration is already wrong by the time
  the child reads it. The test `test_a_duration_is_not_an_instant` pins this.
- **Opt-in.** Without `--legs`, nothing about `run_suite.py` changes. A
  default-on check would refuse the operator's own runs, where `LANE_DEADLINE`
  is absent. `test_without_the_flag_nothing_changes_at_all` is the control.
- **UNKNOWN is not permission.** `may_start` is `False` for `REFUSE` *and* for
  `UNKNOWN`, so a caller reading only that field cannot turn "I could not tell"
  into a licence to start.

The figures come from measurement and are named in every verdict: a pair costs
78–91 minutes (`glm 0065`), the widest single leg on record is 57.6 minutes
(`pilotcaps/0170`). The 10-minute write-up reserve is **declared, not measured** —
the write-up has never been timed separately — which is why it is a flag and why
every verdict prints it. That honesty is 0170's and it is worth keeping.

## 2. `suitelock.status()` — BUILT

Answers *is this lock real, and how much longer*, rather than returning the
file's contents: `FREE` / `HELD` / `STALE` / `UNKNOWN`, with liveness as an
evidence class (`ALIVE` / `DEAD` / `UNKNOWN`), the holder's remaining budget, and
`would_acquire` taken from `_takeable` — the function `acquire` itself calls, so
there is no second decision path to drift. It writes nothing.

Two things it deliberately does **not** do, both correct:

- It does not make `_alive` three-valued. That is qwen/0150's D6 and it has a
  real correctness cost: today's bug makes the lock too *permissive*, and fixing
  that alone makes a genuinely dead holder harder to displace, so the
  402-minute dead hold of 2026-10-15 would get *longer*. It needs the
  progress-evidence rule and a threshold nobody has measured.
- It does not repair `read()` for a lock file holding valid JSON that is not an
  object (`[]`, `"x"`, `3`). `status()` reports those UNKNOWN and says in the
  explain string that `acquire` would raise `AttributeError` on one. **This is
  an open defect, filed here rather than fixed**, because repairing it would
  change what `acquire` does and this change is specified to cost nothing in
  correctness.

## 3. The proof — DONE BY 0171, AND IT WAS ABSENT

0170's brief asked for tests "born-red, mutation-proven in three states with a
hash-verified revert for each of the two". The 53 tests exist and pass. **No
mutation cycle had ever been run against them.** The evidence is the file
mtimes: both source files were last written *before* both test files
(`lanedeadline.py` 01:04:20, `suitelock.py` 01:07:25, the tests 01:11:55 and
01:13:01), and no mutation cycle can run without touching the source it mutates.

Green is not proven. `docs/ops/mutation_proof_0170.py` now does it — six
mutations, three per feature, each required to be killed **by a specifically
named test** rather than by "a test failed":

| mutation | guard broken | named test that caught it | verdict |
|---|---|---|---|
| M1 | `fits = left >= needed` → `True` | `test_no_room_for_one_leg_is_REFUSE` | KILLED |
| M2 | `may_start` defaults `True` | `test_unknown_never_grants_permission` | KILLED |
| M3 | reserve dropped from `needed` | `test_the_reserve_is_what_makes_a_tight_fit_a_refusal` | KILLED |
| M4 | a dead pid reports `ALIVE` | `test_three_states_and_unknown_is_not_dead` | KILLED |
| M5 | a malformed lock reports `FREE` | `test_bytes_that_are_not_json_are_UNKNOWN` | KILLED |
| M6 | the reader's self-check inverted | `test_a_live_holder_is_HELD_and_acquire_would_wait` | KILLED |

**6 of 6 killed**, every revert md5-verified identical, baseline green before and
after. Log: `docs/ops/TASK-0170-MUTATION-PROOF-2026-10-16.txt`.

### The proof found a defect in itself, and it is the more useful finding

The first run reverted all three `lanedeadline.py` mutations with **matching
md5s**, and `git status` called the tree clean — and the very next test run
still failed six times with `minutes_needed == 91.0`, the reserve missing. That
is M3's mutant, running out of a byte-perfect tree.

Python validates a `.pyc` against the source's **mtime and size**. M3's
replacement `    needed = cost  # MUTANT` is the same 28 bytes as
`    needed = cost + reserve`, and the revert landed inside the same second.
Same size, same second: the cache looked valid and the **mutated bytecode kept
being imported**.

**A hash-verified revert of the source is not a restored module.** This
repository has committed mutated source once; this is the same failure one layer
down, where `git status` cannot see it. The harness now purges
`__pycache__` for the mutated file both after writing the mutant and after
reverting it. Anyone running mutation cycles here should do the same — and a
same-length mutation is the specific shape that triggers it, which is exactly
what a careful, aligned-comment mutation tends to produce.

## 4. Given 4.87%, what did these two actually buy?

**Honestly: very little, and 0150 already said so.** qwen/0150 measured lock
*waiting* at 4.87% of the day and named these two as the only proposals with
strictly zero correctness cost — not as the valuable ones. They are not the win
and were never claimed to be.

`status()` buys **nothing at all** for a lane that calls `acquire()`: the stale
takeover self-heals in one poll, so the 659 minutes of dead-holder lock time cost
that lane zero. Its entire value is to the lanes told to read the file and decide
by hand, and the measured cost there is one wrong decision — `webapp/0040` wrote
`NOT OBTAINED` at ~23:52 against a holder that released at 23:55:33, with 38
minutes of its own budget left. One lane-decision recovered. Real, small, and a
*misinformation* fix rather than a throughput one.

`LANE_DEADLINE` is worth more, but **not** as time saved: it saves no suite
minutes whatever. It converts a kill mid-sentence into a refusal up front, so a
lane that cannot fit spends 0 minutes instead of 58 and then writes its record.
And the larger part of that problem was already fixed by something else — the
timeout raise from 90 to 150 minutes (`566081c6e`, 0090 step 2). 0150's own
conclusion stands: the largest recoverable number was never about the lock.

**The sharpest thing to say is that 0170 would not have saved itself.** The task
that built the deadline feature was lost to a failure the deadline feature does
not address: it stopped at 01:13:04 with **75 minutes still on its 90-minute
clock**. It did not run out of time. `LANE_DEADLINE` answers "can I finish?", and
0170's answer would have been a confident yes, correctly, right up to the moment
it vanished. The gap that actually cost this estate 0170's record is upstream of
every one of the seven proposals in 0150 — see
`TASK-0171-DID-AN-ORPHAN-FINISH-0170-2026-10-16.md`.

## What is still not done

- **The PowerShell end-to-end test has never been observed to run.**
  `docs/ops/test_lane_deadline_in_child_env.ps1` (271 lines) is the only artefact
  that proves `LANE_DEADLINE` actually *arrives* in a real child's environment,
  as opposed to being exported by code that reads correctly. 0171 did not run it:
  it starts a watcher, and 0171's brief forbids starting any watcher. Python
  covers parsing and deciding; **the inheritance link is argued, not measured.**
  Whoever may start a scratch watcher should run it — it is self-contained in
  `%TEMP%`, never invokes `claude`, and takes no lock.
- The `read()` defect in section 2, filed deliberately.
- No full suite has been run against these changes. Five modules touch the
  changed code and all five are green: 53 + 72 = **125 tests, 0 failures**. That
  is not a merge gate and is not offered as one.
