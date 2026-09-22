# Merge request — `infra`, 2026-09-22: store design, test baseline, history runbook

**For the main session.** Branch `infra`, pushed to `origin/infra`. Worktree
`../resonate-infra`. Created off master `c75b4b60` this session; master has
since moved to `7ccc2cfc` under me, which is fine — nothing here conflicts
with it, and the two code changes are in files no other branch touches.

The GLM harness fix is a **separate** merge request:
`docs/MERGE-REQUEST-GLM-HARNESS-2026-09-22.md`. This one covers everything
else.

    006a8be8  GLM harness — separate MR
    e6847102  that MR
    a3ceb50d  git history runbook + scripts/history_pii_scan.py
    85867a9b  suite baseline, test_invariants fix, 7 bounded tasks
    87535888  this MR
    3402ddd9  TASK-251 src/sqlitestore.py + 26 tests (NOT WIRED)
    6303248f  TASK-251 -> DONE, result block and findings
    56177820  the storage prompt's five-day-stale measurement, corrected
    9e2bf63d  the same env leak in a second class; setUp becomes a mixin
    e9a704ac  baseline re-measured and the before/after diffed by name

## Overlap check, per the three-session rule

Checked `git log master..<branch>` for every branch, per file, before
starting:

    src/store.py          qwen-worker-2-task-243, qwen-worker-4-task-245
                          — both STATE_OVERRIDES additions, both already on
                          master. NOT TOUCHED by this branch anyway.
    src/queuejournal.py   qwen-worker-8-r28 (TASK-226, offset index for O(M)
                          replay). Adjacent to the SQLite design; NOT
                          superseded — see below. NOT TOUCHED here.
    scripts/glm_*.py      no overlap
    tests/test_invariants.py  no overlap

Nothing under `config/.env`, `src/providers/`, `scripts/*_watch_loop.py` or
`work/` was read-modified or written. `work/queue.jsonl` was read once,
read-only, for the measurement in section 1.

---

## 1. THE STORE — design and five tasks, nothing wired

`docs/STORE-SQLITE-DESIGN-2026-09-22.md`, and `TASK-251` … `TASK-255` in
`docs/qwen-tasks/TODO/`.

**Nothing is wired and no behaviour changed.** The tasks land in an order that
keeps the storage engine and the change to the only file holding real client
state as separate reviewable things — the shape `queuejournal.py` was
deliberately landed in, for the reason its own docstring gives.

### The measurement corrects two numbers you are planning against

Measured on the live queue today:

    records                 1,027
    total                  19.41 MB
    mean per record        19,819 bytes
    largest                162,117 bytes

- **The brief's "~31 KB per record" is high.** 31 KB is inside the range but
  the mean is 19.8 KB, so every projection in the design is the conservative
  version. **That same 31.8 KB figure was live inside
  `scripts/glm_review.py`'s `STORAGE_QUESTION`**, stated to GLM as "measured on
  the real estate today" since 2026-09-17, on 550 records. Every storage review
  run since then did its arithmetic on a record size wrong by 60%, and the
  model has no way to check a number it is handed. Corrected in `56177820`,
  with the tail stated as well as the mean — this is also where the brief's
  "~31 KB" came from, so it had already propagated out of the prompt and into
  a work instruction.)
- **`queuejournal.py`'s headline benchmark under-states production by
  22.7x.** Its table — 4,369.1 MB at 5,000 records, 1,000 checkpoints — works
  out to 874 bytes per record, matching its own "~900-byte record". Production
  is 19,819. Every byte and wall-clock figure in that table is low by that
  factor.

At the measured mean, one pass over 20,000 records writes **1.48 TB**, with an
O(N) read per checkpoint on top.

### Why this is feasible at all

`queue_path()` has 97 callers, which looked fatal. It is not: **36 of them
want `os.path.dirname(...)`**, and **no module under `src/` parses the queue
file itself.** The only direct readers are `scripts/profile_scale.py`,
`scripts/task191_funnel.py` and `store`'s own `queuejournal`. TASK-254 turns
that survey into a test so it stays true.

### TASK-226 is NOT superseded

The journal stays the default until SQLite is proven in shadow, so the offset
index on `qwen-worker-8-r28` is still worth having. Do not close it on the
strength of this design.

### Two decisions that are yours

1. **`digest()` changes meaning on the SQLite backend** — a revision counter,
   not a content hash. It refuses slightly more often (a change-and-change-back
   now refuses). That is the safe direction and the task asserts the stricter
   behaviour rather than shimming the old one. Flagging it because
   `expect_digest` is a concurrency guard.
2. **Shadow-mode divergence does NOT raise in production**, against this
   repository's default. Reasoning is in design §7 and task 253: JSONL is
   canonical throughout, the SQLite half is an observer with no vote, and a
   divergence that raises would take the trusted half down to protect the
   untrusted one. `SHADOW_STRICT=1` raises, and tests run with it on.

---

## 2. TEST DEBT — the baseline is a list now

`docs/state/SUITE-BASELINE-2026-09-22.md` and its `.json`.

**The diff asked for could not be done.** No name-level record of the 83 was
ever written — `docs/`, `docs/state/` and `../pool-logs` all searched; the
sweep logs are 71-byte dispatch records. A scalar can only be subtracted, and
subtraction hides an equal number of fixes and regressions. The suite also grew
427 tests between the two measurements, so those deltas never compared the same
suite.

So the artifact is the fix: every failure by fully-qualified name, regenerable,
diffable as a set.

    before     11,098 tests · 80 F · 36 E · 116 entries · 112 distinct
    after      11,109 tests · 75 F · 36 E · 111 entries · 111 distinct
    stable     110 of 115 reproduce identically when run alone
    fixed      -5, all test_invariants, all run-order

**Measured twice, not measured once and estimated.** The second full run
confirms the predicted -5 exactly, and the diff is a set difference rather
than a subtraction: exactly one distinct test gone (one method, five subTest
entries) and **nothing new**. 116 -> 111 could equally have been eleven fixes
and six regressions; the old count-only format could not have said which.

That diff then found a SECOND class with the same leak
(`TestValidationCannotSpendByAccident`), fixed after the run — so expect
**110** next measurement. The artifact earning its keep on first use.

### The 5 were the production-state barrier

`spendledger` and `observability` resolve their own path beside
`store.queue_path()`. With `QUEUE` left pointing at an earlier module's temp
directory they write there, the barrier correctly does not fire, and the test
fails with "ProductionStateUnderTest not raised" **while the barrier is in
perfect health**.

Reproduced rather than inferred: `QUEUE=<tmp>` → 4 failures, `SPEND_LEDGER=<tmp>`
→ exactly the `spendledger` subtest, clean env → 5/5.

Fixed by pinning the environment in `setUp` and restoring in `tearDown`, so the
class tests the real paths its docstring already claimed. **Verified not
vacuous:** with `refuse_production_write` stubbed to a no-op it produces 10
failures across all nine writers plus the dedicated barrier test.

Nothing retired, no assertion loosened, no guard widened.

### The number for the register

    2026-09-22   11,109 tests   111 entries   111 distinct

Measured, and expect 110 next run. It is **a floor to work down from, not an
achievement**: ~47 of the 111 are two known contract changes — TASK-256 (28)
and TASK-250 (~19, already written, never started) — both fixture work with a
stated rule, and neither hard.

### THE ONE THAT IS YOURS: the PII guard is red

`test_fixture_hygiene.TestNoRealDataAnywhereInGit`, 3 of 13. **REAL DEFECT,
not test debt.** ISSUE-006 closed at `cecd4223` on 09-20 reporting 13/13 with
the finding *"a red guard catches nothing"*. 132 commits later it is red
again, and every flagged file landed 09-21/22 — after that fix:

    docs/HEYREACH-CADENCES-2026-09-21.md
    docs/SLACK-AGENT-HANDOFF-2026-09-22.md
    docs/qwen-tasks/TODO/TASK-249-...
    scripts/batch1_build.py
    src/clientapproval.py
    tests/test_a_client_can_never_reach_another_client.py
    tests/test_client_approval_is_a_gate.py

None is mine; checked against every commit on this branch. **Not fixed here**
— they are your active files and redacting identifiers out of
`src/clientapproval.py` touches live client semantics.

It is red in plain sight, which is the argument for the baseline work: a guard
hidden among 112 failing tests is ISSUE-006's own mechanism one level up.

### And a latent defect the cluster was hiding

The 28-test threading cluster is a changed contract (TASK-219, `4c9d63d3`).
But the shipped ladder default

    THREAD_REPLY_PATTERNS["email_five"] = (False, True, False, True, False)

has steps 3 and 5 unthreaded, which TASK-219's invariant refuses whenever
follow-ups carry their own subjects. **The default configuration cannot build
a sequence.** Production is unaffected and I checked rather than assumed —
both real client configs override with all-threaded patterns, which is why
491-498 built against a six-day-old guard. A client added without that override
inherits the break. TASK-256, and it asks a question about the copy contract
that may be yours to answer.

---

## 3. GIT HISTORY — runbook, not a rewrite

`docs/GIT-HISTORY-REWRITE-RUNBOOK-2026-09-22.md` and
`scripts/history_pii_scan.py`. **Nothing has been run.**

### The cutoff in the brief does not work

Scanned every blob in the object database against the guard's three lists and
attributed to master's first-parent history:

    commits carrying an identifier (excl. guard file)   595 of 874
      before 2026-09-15                                 217
      on or after                                       378
    earliest                              2026-09-09  (first commit)
    latest                                2026-09-22  (today)
    distinct identifiers                       97

**A rewrite scoped to 09-15 leaves 217 commits behind** — full disruption,
data still there. It has to start at the root.

### Sequencing

The latest identifier is dated **today**, and the guard is red. **Fix the
guard first or the rewrite is stale the moment it finishes**, and you do not
get to run this twice cheaply.

### The decision the runbook cannot make for you

`tests/test_fixture_hygiene.py` holds all **117 values in clear and is in
every commit** — the largest single concentration in the repository. Redact it
and the guard has nothing to match; leave it and the rewrite is close to
pointless. Recommendation: move the lists to a gitignored sidecar first, the
way `config/suppress.local.txt` already works. That is a merge request with a
test, not a runbook step.

### Blast radius

10 worktrees, ~90 branches, 3 sessions, and **59 real commit SHAs cited across
tracked markdown** — the register names a commit in every FIXED row, and a
rewrite dangles all of them. Section 5.4 rewrites them from filter-repo's
commit map.

Neither `git-filter-repo` nor BFG is installed here (no Java). The runbook
says so and picks filter-repo.

---

## 4. LINKEDIN PER-SEAT LEDGER — TASK-257

The design point worth your attention: **our action ledger is a LOWER BOUND on
a seat's use**, because the client works the same seats on a workspace-wide key
and their actions are not in it. So the verdict vocabulary mirrors
`senderheadroom` — FULL / ROOM / REFUSED — with one difference that must not be
smoothed over:

    ours >= 40              FULL. A lower bound at the ceiling is still at it.
    seat exclusively ours   ROOM is computable.
    seat SHARED             REFUSED, permanently.

In `senderheadroom`, REFUSED means *not yet proven* and a better walk fixes it.
Here it is **permanent**: no walk of our own ledger can prove room on a seat
somebody else works, because the missing quantity is unobservable rather than
unwalked. The task says so in the module docstring, because a future session
will try to infer it from HeyReach campaign counters and a guessed denominator
is worse than a missing one.

`client` is the literal string `"UNKNOWN"` on a shared seat — never `None`,
never absent, never 0 — because an absent field reads as zero to the next
person who writes a sum.

It reads `actionledger.count_on` rather than adding a second counter, and it
never writes.

---

## 4b. ALSO ON THE BRANCH AFTER THIS MR WAS FIRST WRITTEN

**TASK-251 is BUILT, not just written** — `src/sqlitestore.py`, 26 tests,
`3402ddd9`, moved to DONE with a result block. `src/store.py` is untouched and
nothing imports it; both directions are asserted, so "not wired" is a property
rather than a claim. Attacked with three deliberate breaks (key-sorted reads,
upsert as delete-then-insert, `open_db` without the barrier), each caught by
its intended test.

It was built here rather than dispatched to the Qwen pool: those worktrees
were carrying other sessions' branches (task-244 … 249) and dispatching into
shared infrastructure was not mine to do without asking. **If you would rather
the pool ran 252-257, say so and I will queue them instead.**

Two findings from it are in the task's result block and worth reading before
the next one — `updated_at` is second-resolution and unusable as a test probe,
and my first no-circular-import test grepped the source and failed on the
module's own docstring, which is the exact failure CLAUDE.md warns about,
reproduced within the hour.

---

## 4c. QWEN POOL — DISPATCHED, REVIEWED, INTEGRATED

Operator asked for 252-257 queued to the pool. Dispatched on branches off
`infra` (252/255 depend on TASK-251, which is only here). **TASK-253 and
TASK-256 were deliberately NOT dispatched** — 253 depends on 252 and 256 on
258, and both touch the same files as their dependency. qwen-7 and qwen-8 are
held for them. `resonate-qwen-worker` was left alone; it is mid-TASK-250.

    TASK-251  (me)    INTEGRATED   sqlitestore, no caller
    TASK-252  qwen-2  INTEGRATED   one-shot migration + verifier
    TASK-253  qwen-7  INTEGRATED   QUEUE_BACKEND + shadow path
    TASK-254  qwen-3  INTEGRATED   the caller survey is an AST test
    TASK-255  qwen-4  INTEGRATED   20k load test at production record size
    TASK-256  qwen-8  INTEGRATED   the threading fixtures
    TASK-257  qwen-5  INTEGRATED   LinkedIn seat ledger
    TASK-258  qwen-6  INTEGRATED   the default ladder

**All eight DONE.** 300 tests across every suite this branch added or touched:
298 green, 2 failures — the known pre-existing `test_invariants` pair, which
is genuine test debt and predates this branch.

TASK-259 is written and NOT dispatched — see §4d.

### Every one was attacked before it was accepted

    TASK-254   3 synthetic violations (bare, dotted, nested in os.path.join)
               -> all caught; a COMMENT mentioning the pattern does not fire
    TASK-252   verifier stubbed to pass -> 1 failure; records reversed
               -> 2 failures; base file read instead of _current_records
               -> 1 failure
    TASK-257   swept ours=0..59 on a shared seat -> no ROOM, no numeric
               remaining, no client of 0, at any count

My first attack on TASK-252 was the flawed one: patching `_verify` in-process
caught nothing because those tests drive the script as a subprocess. Re-run
against the script file itself, it catches everything. Worth recording because
the same mistake would have passed a broken verifier.

### Three review fixes I made on integration

1. **`task191_funnel.py` called `store.use_directory()`** — documented "Demo
   mode and tests only", and it `makedirs` its target and CLEARS every
   `STATE_OVERRIDE`. The script's default target is the production `work/`
   directory and it is a read-only report. Now sets `QUEUE` alone. It is also
   the same helper behind the env leak that caused the five order-dependent
   failures fixed earlier today.

2. **The migration had an environment-named code path.** `migrate` read
   `_MIGRATE_CORRUPT_HOOK` and ran whatever file it named as a subprocess,
   unguarded, on the path that migrates the only file holding real client
   state. Not a privilege escalation — but this repo has a convention for
   test-only escape hatches (`allow_history_loss` is a keyword argument
   `test_invariants` forbids `src/` from passing) and an environment variable
   is not it. Now an `_after_insert` parameter, matching
   `sqlitestore._fail_after`. A test asserts no `os.environ` read and no
   run/Popen/exec/eval in the module.

3. **`seatledger` called `int()` on a seat id.** It raised on a non-numeric
   provider id — and in a module whose job is classifying FULL/ROOM/REFUSED,
   a traceback is not one of the three. Where it did not raise it collapsed
   distinct seats: `int(True)` is 1, `int("1_0")` is 10, `int("٧")` is 7.
   Two seats becoming one is one seat handed another's usage, and on the ROOM
   branch that is the confident wrong number the module exists to prevent.
   **None of it was covered**, because every fixture built ids with `int(s)`.
   Four tests added; verified by restoring `int()` — 1 error, 5 failures.

   This is the coercion class the GLM attribution review raised against
   `int(seat)` in `inbound` — the review that turned out to have been run with
   no code in the prompt. The finding was right anyway, and it has now turned
   up in a second module. **Worth checking `inbound` for it directly.**

### One design call I want to endorse rather than flag

`seatledger._is_exclusive` is ACCOUNT-WIDE, not per-seat, and that looks wrong
until you read its reasoning: we cannot enumerate the client's campaigns'
sender lists, so we cannot prove any INDIVIDUAL seat is absent from them.
Exclusivity is establishable for the whole account or not at all. In
production — 86 campaigns against our 4 — every seat comes back REFUSED, which
is exactly what ISSUE-010 says is true.

### A pool note that cost three workers

**`qwen.cmd` truncates a multi-line prompt.** Three of five workers replied
"the instruction is incomplete" and exited 0 having done nothing — the
README's "a worker that has done nothing" failure, from a cause it does not
name. Single-line prompts work. Worth adding to `docs/qwen-tasks/README.md`.

---

## 4d. THE TWO THINGS TO READ BEFORE PROMOTING ANYTHING

**1. SQLite is a very large win and NOT the finish line.** TASK-255 measured
all three arms at production record size:

    ARM              RECORDS  CHECKPOINTS  TIME_S  MB_WRITTEN  AMPLIFICATION
    jsonl              1,000          200    65.4     3,981.8       1108.1x
    jsonl+journal      1,000          200   123.9         3.6          1.0x
    sqlite             1,000          200    43.3         0.2          0.1x

O(changed) is demonstrated across three sizes, not asserted at one. But **all
three arms are O(N²) in wall clock** — 2x records, 4x time — because the read
per checkpoint is O(N) and there are N/5 of them. Projected at 20,000: jsonl
~7 hours, journal ~52 minutes, sqlite ~23 minutes. The design doc now carries
this, with a line asking that "SQLite fixes the storage problem" not be the
sentence that survives from it.

**2. TASK-259 is the gate, and it is not dispatched.** The reproduced-incident
tests — the ones encoding the 2026-09-12 batch that erased a reply, an
unsubscribe, a drop reason and three purchased decision-makers — structurally
cannot run against the sqlite backend, because they simulate a second writer
with `store._write()`, which is not on that path. So the three-way merge and
both loss guards are exercised **only on JSONL**. Do not promote
`QUEUE_BACKEND=sqlite` until that is closed.

### One more defect the regression caught, after every task was merged

`QUEUE_DB` — added by TASK-253 — was never registered in
`store.STATE_OVERRIDES`. `use_directory()` works by clearing that tuple, so a
stale `QUEUE_DB` pointing at the real `work/queue.db` would have **survived
isolation**: the queue moves to the temp directory, the database does not, and
a test writes the real SQLite store believing it is isolated. Fixed, and
verified by reproducing it. Found by `test_every_state_override_is_in_the_move
_together_set`, which is that invariant pair doing exactly its job.

---

## 4e. THE PROMOTION RULE, AND THE TWO TASKS IT GATES ON

**Operator, Zvonimir, 2026-09-22. Recorded in full as
`docs/STORE-SQLITE-DESIGN-2026-09-22.md` §11** — put there rather than only
here, because §11 is where somebody reaching for the flag will actually look.

    QUEUE_BACKEND=sqlite goes live ONLY when all four hold:
      1. TASK-259 green   both loss guards exercised on BOTH backends
      2. TASK-260 green   the checkpoint read is O(changed)
      3. 48 hours of shadow on the live queue with a ZERO diff
      4. the PRODUCTION SESSION flips it, in a window with no sends

    Until then, JSONL stays live.

Condition 3 has a trap written next to it. **An empty diff ledger is not the
same as a clean one** — zero rows because nothing ran looks identical to zero
rows because everything agreed, and this repository has shipped that exact
vacuous pass twice (F-003's `coverage()` passing against nothing, and
`leadstop.sweep` reporting clean because it never incremented its counter).
TASK-253's ledger records **writes observed** as well as divergences, so the
check is `writes_observed > 0 AND divergences == 0`, not "the file is empty".

§11 also records what promotion does **not** require, so nobody adds it later:
not a full-suite green (the baseline carries ~111 known failures, none about
storage), and not the jsonl 20k arm being performed (it writes ~1.59 TB and is
projected by design).

And it is reversible: `QUEUE_BACKEND=jsonl` restores the old path, because the
migration never deletes or modifies `queue.jsonl` and JSONL keeps being
written throughout shadow. That is the reason shadow comes first, and the
reason it is 48 hours rather than an afternoon.

### TASK-260 — dispatched, and it is a safety task wearing a performance hat

`docs/qwen-tasks/TODO/TASK-260-...md`. It leads with the hazard rather than
the optimisation, because the optimisation is easy:

**Both loss guards fail open on absence.** `refuse_evidence_loss` and
`refuse_history_loss` each `continue` past a record id missing from the new
set — correct today, because removal is a different rule with a different
guard. The moment the read narrows, every record outside the subset *is*
absent, so both guards skip it. Silently. **A narrowed read converts both into
no-ops for everything they did not read**, and these are the guards that exist
because a 2026-09-11 checkpoint erased a prospect's request to be removed and
left `eligibility` answering with an approval gate rather than a stop.

So the task forbids touching either guard, and requires the correctness to
come from the input being provably sufficient — the records the caller
touched, union the records changed on disk since its baseline — proven by a
200-round randomised property test that the narrowed input gives the identical
verdict to the full set, for the same ids. Plus a fail-closed fallback to the
full read whenever the cursor cannot be trusted.

It also tells the worker the thing that would otherwise cost it a day:
**`updated_at` cannot be the cursor.** Second-resolution from `store.now()`,
`CHECKPOINT_EVERY` is 5, so a cursor built on it would skip every change
landing in the same second. TASK-251 measured that. It specifies a real
per-row `rev` column fed from `meta.revision`.

---

## 4f. FINAL STATE — 251-260, PII guard green, and what is NOT met

**The PII guard is GREEN on this branch, 13/13**, which was the gate on
opening this merge request. Three failures, two causes:

- **One was mine.** TASK-260's tests used `a@test.com` in four places.
  `test.com` is a real, registered, resolvable domain — exactly what
  `test_every_email_address_is_on_a_reserved_domain` refuses, and its
  docstring is the argument: "an address on a domain that can resolve is an
  address somebody could actually be mailed at." No real identifier was
  involved. Moved to `.test`.
- **Two were inherited.** This branch forked at `c75b4b60`, when the guard was
  already red, and you fixed it in `9a77028e` after this session flagged it.
  **I merged master and took your redaction rather than writing a second,
  different one** — two placeholder choices for the same identifiers would
  conflict at merge time, and yours is the one master carries. Zero files were
  touched on both sides, so it was conflict-free by construction.

Merging master in also makes this branch reviewable: `git diff master..infra`
now shows what infra adds, rather than that plus the reversal of 30 commits of
your work.

### PROMOTION CONDITION 2 IS NOT MET, AND THE NUMBERS SAY SO

`docs/BENCHMARK-PASS-WALL-CLOCK-2026-09-22.md`. Run detached, no timeout
wrapper:

    size    backend   seconds   ratio
    1,000   sqlite      60.53   -
    5,000   sqlite   1,522.58   25.2x
    1,000   jsonl       88.36   -

**5² = 25; the measured ratio is 25.2.** Quadratic to two significant figures,
*with* TASK-260's incremental read in place. I stopped the 20,000 arm rather
than run it — ~6.8 hours at this shape, and it would add nothing the ratio has
not settled.

**The cause is not the storage backend.** `Snapshot` re-serialises every
record **twice per checkpoint** — `store.py:470` in `merge_onto`, `store.py:604`
in `_incremental_guard_input` — to re-derive which rows the caller edited. At
5,000 records that is ~198 GB of in-memory JSON to change 5,000 records, and it
happens on **every** arm. It retrospectively explains TASK-255: three backends
with wildly different I/O had identical shape because the quadratic was never
in the I/O. **TASK-261** owns it.

What SQLite has actually bought is **write volume** — 1.59 TB projected against
188 KB, four orders of magnitude of write endurance, and the reason
`queue.jsonl` will not survive 20k whatever else is true. It has not yet bought
wall clock. `QUEUE_BACKEND=sqlite` stays blocked, as recorded in §11.

### TASK-250: I tried it, it regressed, I reverted it

It was **claimed and stalled** on `qwen-worker-r57` — two commits, still in
`RUNNING/`, no result block. I merged it to preserve your work rather than
duplicate it, measured, and reverted:

    before   11,226 tests    82 distinct failures
    after    11,346 tests   123 distinct failures     +41

**The phase fixtures are shared, and neither the brief nor I knew it.**
`phase7.jsonl` alone is read by `test_approve`, `test_cadence`,
`test_double_verification` and `test_events`, so moving its evidence from
contactout to deliverable fixed `test_e2e` — the target — and broke 47 tests
across 8 modules with `'blocked' != 'eligible'`. That is why the work was
abandoned mid-flight.

Merging it was my call and my mistake; the set-difference diff caught it,
which is the third time today that artifact has paid for itself. `126dcfa1` is
preserved unmerged — the approach was right — and the diagnosis is written
into TASK-250 for attempt 2, including the instruction to enumerate every
consumer of a shared fixture *before* editing it.

**Baseline stands at 82.**

---

## 5. WHAT I DID NOT DO

- **Did not fix the PII guard** — §2, your files.
- **Did not root-cause the long tail**, ~54 entries across 28 modules. Several
  look like TASK-250's verification-role change, but "looks like" is not a
  classification and this register's first rule is a reproduction. Named in
  the JSON.
- **Did not dispatch any Qwen worker.** The tasks are written and queued; the
  store migration is five tasks of real work and I would rather you saw the
  design before eight workers started on it.
- **Did not run the rewrite, touch a worktree, or fetch/push anything but
  `infra`.**

---

## 6. SUGGESTED REGISTER ROWS

```
### ISSUE-015 · The PII guard is red again, 132 commits after it was fixed · HIGH

3 of 13 in `test_fixture_hygiene.TestNoRealDataAnywhereInGit`. ISSUE-006
closed at `cecd4223` reporting 13/13; every file now flagged landed 09-21/22,
after that fix. It is invisible because it is one of 112 failing tests - the
ISSUE-006 mechanism one level up, a guard hiding in a failing baseline rather
than in silence.
- **Evidence** `docs/state/SUITE-BASELINE-2026-09-22.md` §3.2
- **Status** OPEN. Files belong to the production session.

### ISSUE-016 · The default email ladder cannot build a sequence · MEDIUM

`THREAD_REPLY_PATTERNS["email_five"]` is (F,T,F,T,F); TASK-219's invariant
refuses an unthreaded follow-up carrying its own subject. The shipped default
is refused by the shipped guard. NOT affecting production: both client configs
override with all-threaded patterns, verified, which is why 491-498 built
against a six-day-old guard. A client added without the override inherits it.
- **Evidence** 28 suite failures; `config/clients/{productive,demo}.yaml`
- **Status** OPEN · TASK-256

### ISSUE-017 · The journal's benchmark was measured on 874-byte records · MEDIUM

`queuejournal.py`'s table works out to 874 bytes/record against a production
mean of 19,819 - low by 22.7x, and five days of capacity planning rest on it.
The register's own recurring shape, arriving in a benchmark.
- **Evidence** `docs/STORE-SQLITE-DESIGN-2026-09-22.md` §1
- **Status** OPEN · TASK-255 re-measures at production record size

### A RULE FOR THIS FILE: a baseline is a LIST, not a count.

"113 against 83" was unanswerable because the 83 had no members. Regenerate
`docs/state/SUITE-BASELINE-<date>.json` on every measurement and diff sets.
```
