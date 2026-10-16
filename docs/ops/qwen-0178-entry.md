
# TASK 0178 — QWEN — THE DISPATCHER NOW SAYS "THIS IS ALREADY RECORDED" AND STILL DISPATCHES. THE HEADING-ANCHORED RULE WAS REFUTED BY THE DATA BEFORE IT SHIPPED — 2026-10-16 13:4x–14:2x

Worktree `C:\Users\Zvonimir\qwc`, branch `task-qwen-0090-watcher-treekill-2026-10-15`.
Commit **`8f90d57aa`**, pushed; `HEAD` and `origin/<branch>` read back identical.
`origin/master` **`b1f290c84` at start and `b1f290c84` at close** — fetched and
re-read, not assumed. `scripts/run_suite.py` md5 `fee0e375a63d13e32a8ac0f28019982b`
at start and at close. No suite was run.

`LANE-qwen.md` before **7472** lines, after **7840** lines.

---

## 0. The standing rules were read, by absolute path

`C:\Users\Zvonimir\Desktop\resonate-ops\queue\_STANDING-RULES.md` opened and read
in full. Every path this entry names is absolute.

---

## 1. WHAT IT DOES: IT ANNOTATES. IT DOES NOT SKIP.

The brief offered a hard skip and a recommendation, and invited a refutation of
the recommendation. **I did not refute it. The annotation is right, and the
`0161` case is why.**

Before dispatching `queue\<lane>\NNNN-*.md`, the watcher asks whether
`LANE-<lane>.md` already carries an entry claiming TASK `NNNN`. On a hit it
**appends a note to the brief in `RUNNING` and dispatches normally**. Nothing is
gated, nothing is withheld, no brief is consumed unexecuted.

The asymmetry, stated as the rule's own justification:

| | cost when wrong | measured instance |
|---|---|---|
| wrong SKIP | **work lost silently** | `glm-c/0161` looked done, ran 3m44s, found `task-glm-c-0164-brake-ship` (`0355fe7b7`) with **no remote ref at all**, holding the only copy of TASK 0225's work |
| wrong DISPATCH | one dispatch | `glm/0073`'s third dispatch found a new defect; `glm-c/0220`'s TIMEOUT found nothing |

A rule that can only ever be wrong cheaply is allowed to be wrong. A rule that
can be wrong expensively is not, and no false-positive rate I could measure
would make a silent skip safe — because the `0161` loss is **not detectable
afterwards**. That is the whole argument, and it does not depend on my numbers.

**The premise of the brief, re-measured rather than quoted.** From
`C:\Users\Zvonimir\Desktop\resonate-ops\logs\watcher-glm-c.log`:

    line 445   [2026-10-16 09:16:52] [glm-c] START 0220-the-remaining-bypasses-tiered.md
    line 446   [2026-10-16 11:46:53] [glm-c] TIMEOUT after 150 minutes ... 96 process(es)
    line 457   [2026-10-16 11:47:00] [glm-c] DONE  0220-... -> TIMEOUT

150 minutes 8 seconds. `logs\task-glm-c-20261016-091652.out` is **559 bytes**.
The report was already at `LANE-glm-c.md:1948` and the re-measurement at `:2091`.
Premise CONFIRMED.

**And one correction to the brief's count.** It says three more briefs in that
lane are queued with entries present. It is **four**: `0163`, `0164`, `0230`,
`0240`. `0164`'s entry is at `LANE-glm-c.md:2726` and is marked PARTIAL.

### The mechanism, and why it is the brief itself

The watcher launches the task as
`cmd /c claude -p --permission-mode {MODE} < "{BRIEF}" > "{OUT}" 2>&1`.
**The brief on stdin is the entire channel into the session.** A sidecar file or
an environment variable is something the session would have to already know to
look for — which is precisely the reference-that-resolves-to-nothing failure the
standing rules' own `queue/_STANDING-RULES.md` path bug was. So the note is
appended to the **`RUNNING` copy**, after the queue original has been moved out.
Nothing in `queue\<lane>\` is touched, and the annotated copy is the one that
lands in `DONE` — so the archive records what the session actually read.

The note tells the session to pick one of **AUDIT / COMPLETE / REDO** and to say
which it chose, and it ends by saying that a match is a match on a line and not
proof the work was done.

### Three states, not two

`MATCH`, `NO_MATCH`, `UNKNOWN`. **UNKNOWN annotates nothing and dispatches**, and
it is produced by an unreadable lane file, a missing lane file, or a filename
that declares no `NNNN-` id. Absence of a readable answer is never evidence of
absence of an entry and never evidence of one. `glm-c`'s `0162c-` and `0162d-`
briefs are in the queue right now and both come back UNKNOWN, which is correct:
they are different briefs from `0162` and must not inherit its entry.

**Save sweeps are exempt in either design** and are never annotated, however
many times their number appears. `glm-c` ran `0161-save-sweep` twice on
2026-10-16 and the SECOND run is the one that found the branch with no remote ref.

### One deliberate divergence from the estate's module contract

`lane_treekill`, `lane_refusal` and `lane_orphan` all make the watcher **REFUSE
TO START** when missing, because in each case the fallback is the destructive
behaviour. `lane_taskentry` **degrades** instead: missing means no annotation,
which is exactly what every watcher in the estate does today. Turning a missing
optimisation into seven refusing watchers would be a worse failure than the one
it removes. The reasoning is in the code beside the block, including the
condition under which it would have to change.

---

## 2. MATCHING: THE FIRST RULE WAS REFUTED BY THE DATA, AND THAT IS THE FINDING

I wrote the heading-anchored rule first — markdown heading **and** a TASK-adjacent
number — ran it against the seven real lane files, and it was **wrong**.

**`glm-c` does not use headings.** `LANE-glm-c.md` records TASK 0040, 0050, 0070,
0080, 0090, 0100 and 0110 as plain dated paragraphs at column zero:

    LANE-glm-c.md:372   2026-10-15 — TASK 0040 — DEPENDENCY UNMET, STOPPED BEFORE GENERATING: ...
    LANE-glm-c.md:399   2026-10-15 — TASK 0080 — GATE UNMET, STOPPED BEFORE GENERATING: ...

A stop on an unmet gate **is** an entry — the standing rules say so in words. The
heading rule called every one of them NO ENTRY.

So the anchor moved from *is a heading* to **opens an entry**:

> A line counts iff **(1)** it starts — within three spaces, through an optional
> bullet, optional bold and an optional heading marker — with either the word
> `TASK` or an ISO date, **and (2)** somewhere in its first 120 characters the
> word `TASK` is followed, across at most three characters of space, dash,
> underscore, colon or hash, by one to four digits whose **numeric** value equals
> the id, with a word boundary after them.

Numeric comparison, so `TASK 0220`, `TASK 220` and `TASK-0220` are one answer.
The trailing word boundary is what stops `TASK 02200` matching 0220.

**Why rule (1) exists, in one line of real data.** `LANE-glm-c.md:370` reads

    NEXT: TASK 0040 (`queue/glm-c/0040-canary-approval-sheet.md`).

a forward pointer to work **not yet done** — the exact claim this must never
make. It opens with neither `TASK` nor a date, so the shape test refuses it.

### The population, and the five rules scored on it

Population: **228 distinct (lane, task) pairs**, every brief filename across
`queue/<lane>/`, `RUNNING/` and `DONE/` for all seven lanes, which is the exact
question the watcher asks, asked once per thing it could ask about. 8 archive
filenames parsed to no id and are reported separately.
Harness `docs/ops/measure_lane_taskentry.ps1`; raw rows in
`docs/ops/lane_taskentry_measurement.tsv`. **It calls the shipped function** —
a rate measured against a reimplementation is a rate about the reimplementation.

| rule | MATCH | NO_MATCH | |
|---|---|---|---|
| A number-only, anywhere in the file | 222 | 6 | useless, as `webapp/0200` said |
| B number in any heading | 200 | 28 | |
| H heading **and** TASK-adjacent | 193 | 35 | **the refuted first version** |
| D any line, TASK-adjacent | 207 | 21 | no position anchor |
| **C entry-opener and TASK-adjacent** | **202** | **26** | **shipped** |

`webapp/0200`'s "143 convictions for number-only across 7 lanes" is of the same
kind as A's 222 here on a larger population; I did not reproduce its exact
number and am not claiming it.

### THE RATES

    FALSE POSITIVES   1 / 39 hand-validated MATCH rows    =  2.6%
    FALSE NEGATIVES   3 / 26 NO_MATCH rows, FULL CENSUS   = 11.5%

**The one false positive** — `glm-c/0070`. Its only line in the lane file is
`:397  2026-10-15 — TASK 0070 STARTED`. A start marker is not a record of work.
I counted it against the rule. Note the damage: a session reads the note, the
note prints the matched line, the line says STARTED, and the session picks REDO.

**All three false negatives share one shape, and it is worth the operator's
attention more than the rate is:** the entry exists but is **filed under another
task's number**.

    glm/0063     0063's deliverable WAS 0060's entry, and it is filed as 0060
    glm-c/0110   LANE-glm-c.md:405 is headed TASK 0100 and says
                 "ENTRY WRITTEN BY THE 0110 RUN BECAUSE THE 0100 RUN ENDED
                  BEFORE WRITING IT"
    glm-b/0145   LANE-glm-b.md:1470 reads "glm-b/0145 SAVE SWEEP" - lane/NNNN,
                 no TASK keyword. Harmless in practice: sweeps are exempt.

No regex fixes the first two. A lane that lands another task's entry under that
other task's number is, correctly, not claiming its own — and the fail-closed
direction (dispatch) is the one it produces.

**What the anchor bought and cost, both measured.** Against H (heading-only), C
recovers 9 genuine `glm-c` entries that H missed — H's false-negative count on
this population is **12, not 3**. Against D (any line), C refuses 5 rows; I read
all five by hand and **four are D false positives**: a commit message quoted
inside another entry (`glm/0055`), another lane's task number (`qwen/0020`), a
backticked `TASK-0260` in prose (`webapp/0260`) and a filesystem path
`logs\TASK-0270\measure-0270.py:82` (`webapp/0270`). The fifth, `glm/0063`, D
gets right for the wrong reason.

### C3 — the sample sizes and how they were validated

**False negatives: a CENSUS, not a sample.** All **26** NO_MATCH rows read by
hand. A census beats a sample at this size, and this is the direction in which a
skip-based rule would have lost work. Every verdict names what was read; the
table is `docs/ops/lane_taskentry_handvalidation.tsv`. Three classes of true
negative, each repeatable:

    NEVER-RAN     13   no DONE record for that id, so no entry could exist
    RAN-FAILED     4   the only DONE record is exit1 / exit-1
    RAN-NO-ENTRY   6   exited 0 and the lane file SAYS SO IN WORDS -
                       LANE-glm.md:1263 "No lane entry exists for 0040";
                       LANE-glm-b.md:269 0040 at 709 bytes, :270 0050 at
                       2,112 bytes of plan prose;
                       LANE-qwen.md:1235 "no TASK-labelled entry exists for
                       either" (qwen 0010, 0020)
    FALSE NEGATIVE 3   the three above

**False positives: 39 rows in two parts.** Part 1 is **not a sample** — it is
**all 9** MATCH rows whose brief is PENDING IN THE QUEUE RIGHT NOW, i.e. the
exact annotations the next dispatches would emit. All 9 are true positives, and
they are the live cost of the defect:

    glm-c  0163 :2456   glm-c 0164 :2726   glm-c 0230 :2130   glm-c 0240 :2263
    qwen   0180 :5554   qwen  0190 :6256   qwen  0200 :6739
    qwen   0210 :7016   qwen  0220 :7254

Five of those nine are **in my own queue**, which confirms the brief's point
about `0190` and extends it to four more.

Part 2 is **30 of the remaining 193**, `random.seed(178)`, `random.sample`.
29 true positives, 1 false positive (`glm-c/0070`).

**65 of 228 pairs hand-validated — 29%.**

---

## 3. PROVEN ON A COPY. WHAT REMAINS UNOBSERVED ON THE LIVE WATCHERS.

`qwen/0171`'s constraint binds here and is honoured the same way.

**Proved on a copy** — `docs/ops/test_lane_taskentry.ps1`, **18 of 18 legs green**,
output committed at `docs/ops/lane_taskentry_test.out.txt`:

- `U1`–`U12` exercise the matcher directly. `U1` and `U2` read the **real**
  `LANE-glm-c.md` — a matcher measured only against fixtures written beside it is
  measured against its author's idea of the data.
- `U4` holds a file open with `FileShare.None` so the read genuinely throws, and
  asserts UNKNOWN. `U3`, `U5`, `U6` cover the other UNKNOWN routes.
- `U8` is the `NEXT: TASK 0040` forward pointer; `U9` is the `glm-c` dated
  paragraph. Those two legs are the refutation and the repair, frozen as tests.
- `E0`–`E5` run a **byte copy** of the patched `lane_watcher.ps1` in a scratch
  `$Ops` under `%TEMP%`, lane name `tetest` (refused if it is ever a real lane),
  dispatch stubbed to a script that copies the brief it was handed. The watcher
  logged `ALREADY RECORDED: TASK 0300 -> LANE-tetest.md:3`, the captured brief
  contains the note, `0310` was dispatched clean, `0320-save-sweep` was dispatched
  unannotated **despite having an entry**, all three reached the task, and the
  `DONE` archive carries the note.

**Unobserved on the live watchers, and it is more than the usual caveat.** The
four watchers running right now (`suppression` 90432, `pilotcaps` 92132, `qwen`
64160, `webapp` 92408; `glm`, `glm-b`, `glm-c` are STOPped) are executing
`C:\Users\Zvonimir\Desktop\resonate-ops\tools\lane_watcher.ps1`, which is the
**2026-10-15 22:20 build, 20,048 bytes, 413 lines**. The repository's copy is
**786 lines**. The deployed file **does not contain this change — and does not
contain TASK 0110's injection points, 0175's refusal handling or 0200's orphan
resolver either.** Nothing here is live and nothing here can be live without a
restart, which is the operator's.

**No live watcher was restarted, stopped, edited or signalled, and no other
lane's `RUNNING\` was touched.** Verified at close: four watchers up, the same
four, same pids.

### I reproduced TASK 0070's own mistake while cleaning up, and it is reportable

Clearing a stray scratch process, I selected by `CommandLine -match 'lane-te-'`.
**My own shell's command line contained that string**, so the filter matched the
measurement shell and killed it — exit 255 — which is exactly the failure the
standing rules record from TASK 0070 and warn against two lines above where I
was working. The stray was killed first, so nothing was left behind, and the
re-check used `$_.ProcessId -ne $PID`. Recording it because a rule that is only
obeyed when remembered is not yet a control.

### C1 and C2

**C1.** `MATCH` on `LANE-glm-c.md:2263`, TASK 0240, **asserted on the line number**
and not merely the state. `NO MATCH` on invented TASK 9987. Both printed.

**C2, paired mutants** — `docs/ops/mutate_lane_taskentry.py`, output at
`docs/ops/lane_taskentry_mutants.out.txt`:

    baseline        18 passed, 0 failed
    mutant ALL      always MATCH   killed 4:  E2, U10, U2, U8
    mutant NONE     always NO_MATCH killed 5: E1, E5, U1, U10, U9

Named, non-empty, different. They overlap only at `U10`, which asserts both
directions and should be killed by both. **Neither mutant touches the module in
place**: the original is opened read-only, the mutant is written to a new file
under `%TEMP%`, and the test is pointed at it with `-Module`. There is nothing to
revert, so nothing can fail to revert — **TASK 0176's finding applied
structurally rather than remembered**. The original's md5 is asserted identical
at start and close anyway.

**C4, and it was exercised rather than asserted.** `docs/ops/rates_lane_taskentry.py`
refuses to print a rate unless C1, C2 and C3 have each been observed in **both**
states, read from artifacts on disk. I ran three negative controls — each a copy
under `%TEMP%`, the repo file never written — and each refused independently:

    C1 unmet (test log absent)        -> UNVALIDATED, exit 1
    C2 unmet (mutant log absent)      -> UNVALIDATED, exit 1
    C3 unmet (the one FP marked TP)   -> UNVALIDATED, exit 1, "a direction with
                                         zero found errors has not been shown
                                         to be measurable"

It also refuses if the hand-validation table no longer matches the measurement's
NO_MATCH set — so the rates go stale loudly when the lane files move, rather than
being believed.

---

## 4. FOR THE OPERATOR — two things `0190` left, restated so they are not lost

**`required_approving_review_count` is 0 on the master ruleset.** Ruleset
`master-protected`, id 25125359, Active, `bypass_actors: []`, measured refusing a
push with GH013. It stops an accidental `git push` from a lane. It does **not**
stop a deliberate self-merged pull request: with the review count at zero, the
same account can open a PR and merge it without a second pair of eyes, and the
ruleset will permit it. Master is guarded against the accident and not against
the intent. **I did not change the ruleset**, and changing it is yours — the
decision is whether a lane-authored PR to master should require an approving
review, which would make the boundary match what the standing rules already say
in prose.

**`LEDGER.json` records `master_pushed: true` while local and origin master
diverge.** `origin/master` is `b1f290c84`; the main checkout's local `master` is
`5fc5784fc`, moved 00:13 on 2026-10-15 and unpushed. The ledger therefore asserts
the **absence of this estate's one known durability alarm** — the exact condition
`scripts/durable_state.py` exists to raise — and nothing reads it, so the
assertion has never been contradicted by anything. A field that is wrong and
unread is worse than a field that is missing, because the next reader will
believe it. **I did not delete `LEDGER.json` and did not touch it.** The decision
is yours: either something reads that field and the alarm becomes real, or the
field is removed so it cannot be believed.

---

## 5. Boundaries

No prospect-facing send, activation or canary run. No provider, Apify or Slack
call. One network operation: `git push` of my own lane branch, and `git fetch`
of `origin/master` to read it at close. No cap or gate change. **No push or merge
to master**; `origin/master` `b1f290c84` at start and at close. The main checkout
and every other lane's worktree were not entered. No git worktree or clone was
created anywhere, and nothing was created under
`C:\Users\Zvonimir\Desktop\resonate-ops\logs\`. No full suite; `run_suite.py`'s
md5 identical at start and close. No live watcher restarted, stopped or edited;
no other lane's `RUNNING\` cleared. `config\.env` and production `work\` state
were not read or changed. No key printed. No credential rotated.

**Everything written under `C:\Users\Zvonimir\Desktop\resonate-ops\` by this
task: this entry, appended to `LANE-qwen.md`. Nothing else.** The code, the
tests, the mutants, the measurement and every evidence file are in the
repository on the lane branch at `8f90d57aa`.

## 6. Files

    docs/ops/lane_taskentry.ps1               the matcher, the sweep rule, the note writer
    docs/ops/lane_watcher.ps1                 +102 lines: param, load, dispatch-time check
    docs/ops/test_lane_taskentry.ps1          18 legs, U1-U12 and E0-E5
    docs/ops/mutate_lane_taskentry.py         the paired mutants
    docs/ops/measure_lane_taskentry.ps1       five rules over the seven real lane files
    docs/ops/rates_lane_taskentry.py          the hand validation and the C4 gate
    docs/ops/lane_taskentry_measurement.tsv   228 rows, five verdicts each
    docs/ops/lane_taskentry_handvalidation.tsv 65 hand verdicts with reasons
    docs/ops/lane_taskentry_{test,mutants,rates}.out.txt   the three control runs

**NOT DEPLOYED. Adoption is a restart and the restart is the operator's.** The
deploy would become five files: `lane_watcher.ps1`, `lane_treekill.ps1`,
`lane_refusal.ps1`, `lane_orphan.ps1`, `lane_taskentry.ps1` — and the deployed
watcher is three tasks behind the repository's before this one is counted.
