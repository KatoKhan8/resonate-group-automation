# The bounce recorder can fail forever and nothing looks wrong — TASK-0220, 2026-10-16

Measured in `wt-suppression-2026-10-14` on branch
`task-suppression-bounce-RULE-2026-10-15`. `origin/master` is **`b1f290c84`**,
unchanged and re-fetched. No provider call, no network call, no send, no
activation, nothing prospect-facing, no cap or gate change. **No monitor loop
was changed** — this task may read one and may not edit one, and §5's repair is
written out and deliberately not applied. `confirm_email_touches` was never
called in any form.

Every `path:line` below was opened and read in this tree at the SHA this
document is committed at. `scripts/citecheck.py` (TASK-0210) reports this
file's citations: **22 citations, OK=11, REFUSED=11, UNVERIFIABLE=0,
MOVED=0, BROKEN=0, ERROR=0.** All eleven REFUSED are into
`scripts/bison_watch_loop.py`, which that checker's default boundary excludes
as a monitor loop — **this task's boundary permits reading it**, so all eleven
are verified here instead, by `test_the_cited_lines_are_the_lines`, and
`test_citecheck_refuses_only_lines_this_module_asserts` makes that coverage a
measurement rather than a promise. **Corrected on re-dispatch, 2026-10-16:
this paragraph said "the three", and the measured number is eleven — see §7.**

---

## 0. THE ANSWER, FIRST

`BOUNCE-RECORD-FAILED` has **one writer and zero readers**. A failure of the
only production caller of `leadobserve.record_bounces` changes nothing that
any production code reads, leaves the watcher reporting **UP**, and could
continue **indefinitely** — the window is **UNBOUNDED**, not long.

And the cost lands in the one direction that can reach a prospect: a bounce
that was never recorded makes the preflight's `bounce_history` cell read
**PASS**, not UNKNOWN. `channels._bounced` answers `False` for a missing
event, measured.

TASK-0180's defect 4 is **correct**, and this task found two things it did not
say:

1. **The READ-ERROR asymmetry it praised does not reach a verdict either.**
   `supervisor.witnesses()` reads a heartbeat's `epoch` and the pid and
   nothing else. The READ-ERROR note is real and no verdict consults it, so
   that path is equally invisible *to the system* and differs only in leaving
   a readable string behind.
2. **The obvious one-line repair does not work.** Beating with a note from
   inside the recorder is overwritten by the loop's own beat 0 lines later.
   Measured by planting it; see §5.

---

## 1. IS THE STRING READ — MEASURED, AND THE SEARCH IS CONTROLLED

Searched: this worktree (all files, `.git` and `__pycache__` excluded) and
`C:\Users\Zvonimir\Desktop\resonate-ops\`.

| hit | classification |
| --- | --- |
| `scripts/bison_watch_loop.py:601` | **WRITES IT.** `emit(f"BOUNCE-RECORD-FAILED {provider_id}: {type(exc).__name__}")` |
| `docs/NINE-HUNDRED-SENDS-ONE-CONFIRMED-TOUCH-REDISPATCH-2026-10-16.md:227,233` `BOUNCE-RECORD-FAILED` | mentions (this lane's own audit) |
| `work/suppression-measure/0110/hard.patch`, `.../make_patches.py` | mentions (this lane's gitignored scratch) |
| `scripts/__pycache__/bison_watch_loop.cpython-314.pyc` | a stale build artefact, not a reader |
| `resonate-ops/LANE-suppression.md` lines 6299, 6378 | mentions |
| `resonate-ops/logs/task-suppression-20261016-023121.out` line 13, `logs/watcher-suppression.log` line 653 | mentions (my own output) |
| `resonate-ops/queue/suppression/0220-the-failure-nobody-would-ever-see.md` lines 11, 29 | mentions (this brief) |

**READS IT: nothing.** Zero hits in `src/`, asserted by a test rather than
reported from a shell.

### The two candidate readers of the sink, opened rather than grepped

* **`watchsink.events()`** (`src/watchsink.py:261` `events`) is the only function that
  reads the event log. Its production callers: **none.** Every call is in
  `tests/test_a_watcher_that_prints_into_nothing_is_not_a_watcher.py`.
* **`scripts/qa/check_readback.py:623` `_read_log_last_line`** reads the
  **last line only** and the value lands at
  `scripts/qa/check_readback.py:592` `log_last_line` — a field in the
  returned row. The
  verdict beside it is computed at `:580`–`:584` from `latest_beat.get("at")`
  and `module_stale`, and **never from the line.** Two reasons it cannot see
  this failure anyway: it searches for nothing, and one later emission pushes
  the line off the end.

### And the beat note, since that is where §5's repair would land

* **`supervisor.witnesses()`** — `src/supervisor.py:695` `witnesses` to `:790` — reads
  `epoch` and the pid. The word `note` does not appear in it.
* `src/slackagentreadback.py:330` `heartbeats` builds watcher rows of
  `watcher / at / pid / age`. No note.
* `src/slackknowledge.py:429` `heartbeats` builds
  `watcher / pid / age_seconds / at`. No note.
* `scripts/cold_start.py:132` `"note": row.get` is the **only** production
  reader of a beat note, inside `cursors()`, a read-only report. It
  is a display, not a decision — nothing branches on it.

### C1 — the control that makes "zero readers" worth anything

A planted reader of the string, in a temporary fixture, must be found by the
same function that reports zero readers:

    test_the_planted_reader_is_found                            OK
    test_the_same_search_narrowed_to_src_does_not_find_it       OK  (C1 red when blinded)
    test_the_estate_search_finds_the_writer_and_no_reader       OK

The second is C1's proof-of-failure: narrow the search to `src/` and the
planted reader is not found, which is exactly what a broken search looks like.
Without one planted reader whose absence is a *measurement*, "no readers"
and "no search" are the same output — failure family 5, which this estate has
already shipped once.

**The search also found itself.** The first version counted this task's own
test file, which quotes the writer line in its docstring, as a second writer.
Excluded by name.

### NOT SEARCHED — reported, never counted as clean

| path | why |
| --- | --- |
| `C:\Users\Zvonimir\Desktop\resonate-group-automation` (main checkout) | boundary |
| `wt-glm-review-2026-10-14`, `wt-glm-b-2026-10-14`, `wt-glm-c-2026-10-14`, `wt-pilotcaps-2026-10-14`, `resonate-trees\wt-webapp-*` | another lane's worktree — boundary |
| `qwc` (separate clone) | boundary |
| production `work/` state, including every `watch-events/*.jsonl` and `heartbeat/*.json` | boundary |
| any dashboard or alert configuration outside these two trees | not visible from here |

**So whether the recorder is failing in production right now is UNKNOWN**, and
by construction this lane cannot find out: the evidence is in production
`work/`.

**A note on this document's own citations — REWRITTEN ON RE-DISPATCH, and the
first version of it was the defect.** `scripts/citecheck.py` reports two
non-`OK` states for this file and the first version of this paragraph named
only one of them, which is why §7 exists. Measured now, at the SHA this
correction is committed at:

    OK  11   MOVED 0   BROKEN 0   UNVERIFIABLE 0   REFUSED 11   ERROR 0

`REFUSED` is all eleven `scripts/bison_watch_loop.py` citations, because that
checker's default boundary excludes monitor loops and this task's does not.
A refusal is **not** a check, so every one of the eleven is asserted line by
line in `test_the_cited_lines_are_the_lines`, and
`test_citecheck_refuses_only_lines_this_module_asserts` fails if the checker
ever refuses a line this module does not assert — which is what stops
`REFUSED` from quietly meaning `unchecked` again.

`UNVERIFIABLE` was **ten**, and is now zero. Ten citations here carried no
backticked symbol adjacent to them, so the checker had nothing to test and
said so; its own docstring says a document may not be called verified while
that count is above zero. All ten line numbers were in fact **correct** — read
from the `HEAD` blob one by one on re-dispatch — so this was a defect in how
they were written, not in what they claimed. Each now names its symbol.

The four references to files in `resonate-ops/` are written **in prose, not in
`path:line` syntax**, because that tree is not in the repository and the
checker resolves against `HEAD` - a citation it cannot resolve reads BROKEN,
which would be a false finding about a correct reference. The checker has no
state for "outside the repository" and that is a gap worth one later task,
not a reason to write a citation it will mis-report.

---

## 2. HOW LONG A SILENT FAILURE COULD LAST — UNBOUNDED

### What triggers the recorder, and how often

    scripts/bison_watch_loop.py:641   on_queue = _bounce_recorder(watched, emit)
    scripts/bison_watch_loop.py:647   current = snapshot(watched, on_queue=on_queue)
    scripts/bison_watch_loop.py:189   on_queue(queue)
    scripts/bison_watch_loop.py:598   out = leadobserve.record_bounces(provider_id, queue=queue,
    scripts/bison_watch_loop.py:599                                    live=True)

Once per poll, inside `snapshot`, whenever the queue read succeeded. The loop's
own default is `--interval 300` (`:627`), and the supervisor launches it with
**180** — `src/supervisor.py:230` `bison_campaign_id` registers
`("bison", "bison_campaign_id", "scripts.bison_watch_loop", 180)` and `:238`
passes `["--campaign", campaign_id, "--interval", str(interval)]`. One watcher
per campaign carrying a `bison_campaign_id` in the ledger, and
`_watch_campaign` fails SAFE — an unrecognised status returns
`True, "unknown status %r"`, so a paused campaign is still watched.

**So: every 180 seconds, per watched campaign, with `live=True`.**

### What the health beat asserts, and what it does not

    scripts/bison_watch_loop.py:663   watchsink.beat("bison", campaign=watched, state=current)

Unconditional, every poll, **with no note**. `supervisor.witnesses()` then
reaches `UP` from two witnesses: a live pid from a post-boot state file, and a
beat no older than `STALE_BEAT_MULTIPLE` (2) × the interval. **Neither witness
has any connection to the recorder having succeeded.** A beat written after a
failed recorder is byte-indistinguishable from one written after a clean poll —
asserted in `test_the_beat_carries_no_note_and_still_supports_up`.

### What the READ-ERROR path does differently, quoted

    scripts/bison_watch_loop.py:654   # Beat anyway, with the reason. Alive-and-blind is a different
    scripts/bison_watch_loop.py:655   # incident from alive-and-nothing-changed and must not read as it.
    scripts/bison_watch_loop.py:656   watchsink.beat("bison", campaign=watched,
    scripts/bison_watch_loop.py:657                  note=f"READ-ERROR {errors}x {type(exc).__name__}")

Confirmed. It also emits at the 3rd and 12th consecutive failure only
(`:651`). **And the note reaches no verdict** — §1. So the asymmetry is real
in the file and absent from every decision: the READ-ERROR path is legible to
a human reading the heartbeat, and invisible to the supervisor, exactly like
the recorder.

### The window

**UNBOUNDED.** Not a long number — there is no mechanism whose period bounds
it:

* the failure repeats every 180s and each repetition is identical and silent;
* each one appends a line to `work/watch-events/bison-<id>.jsonl`, which has
  **zero production readers**;
* the beat is unchanged, so the supervisor says UP, and the Slack watcher rows
  carry no note;
* there is no counter, no state file, no exit code, no retry, no alert;
* nothing schedules or instructs the one detector that exists — a human
  grepping that log. The only document in the estate that names that grep is
  this lane's own `LANE-suppression.md`.

One mitigation, stated so the finding is not overstated: the provider keeps
the bounced rows, so a recorder that starts working again records them on its
next poll. The failure therefore **delays** recording rather than necessarily
losing it — and the preflight reads PASS throughout the delay, which is §3.

---

## 3. WHAT IT WOULD COST THE 23 — AND THE DIRECTION IS THE WRONG ONE

What the recorder writes: (`src/leadobserve.py:753` `record_bounces`) filters
the provider's rows to `state == BOUNCED` and calls `confirm_email_touches`
with `event_for=policy`, where `bouncepolicy.decide` chooses
`EMAIL_BOUNCED` or `EMAIL_BOUNCED_SOFT`. The product is a canonical **event on
the contact's queue record**.

What reads it:

| preflight rule | reads | direction if the event is missing |
| --- | --- | --- |
| `bounce_history` | `channels._bounced`, and `bouncepolicy.decide` for the hard/soft split | **PASS.** `channels._bounced` iterates `rec["events"]` for `type == EMAIL_BOUNCED`; with none it returns `False` |
| `mx_and_verification` | `channels.email_verdict`, which composes `_bounced` | **PASS** on this input, for the same reason |

Both declare `needs: ("queue",)` and `needs_record: True`, so both are among
the **14** rules a main-checkout run is expected to answer — `bounce_history`
is one of them by name.

**So the cell would read PASS where the truth is "this address bounced".** Not
UNKNOWN. A rule that fails closed on a missing input is a different situation
from one that passes, and this is the second: it is the only shape in this
chain that can put a message in front of a prospect at an address the provider
has already refused.

Measured, both halves, in
`test_the_bounce_gate_answers_false_when_the_event_is_absent`:
`_bounced` is `True` with the event planted and `False` with `{"events": []}`
and with `{}`.

The other two cells in the chain fail closed, and the contrast is the point:
with the queue authority absent or empty, TASK-0190's authority gate makes all
14 rules UNKNOWN before they are asked. **The dangerous case is the one where
the queue is perfectly readable and merely does not contain the bounce.** No
authority state can detect that; only the recorder working can.

---

## 4. CONTROLS — AND C3 REFUTED THE FIRST PROPOSAL

`tests/test_the_bounce_recorders_failure_is_unobservable.py`, 20 tests, 18
pass and 2 are deliberate skips (C2's assertions overridden under C3 so they
cannot silently re-run and report green).

**C2 — a planted failure is genuinely invisible.** `record_bounces` is made to
raise, the real `_bounce_recorder` runs, then the loop's own beat. Measured:

* the exception is swallowed and one `BOUNCE-RECORD-FAILED` line is emitted;
* the set of files that change is **exactly** the heartbeat and the
  append-only event log — nothing else appears anywhere in the fixture;
* the heartbeat carries **no note** and `witnesses()` says **UP**.

**The brief asked me to assert that "no file anywhere in the fixture changes",
and that is not quite true** — the event log does change, by one line. The
assertion is therefore the stronger true one: the only files that move are the
beat, whose content is indistinguishable from a healthy poll, and a log no
production reader consults. A control on that control ages the beat and
asserts `witness_heartbeat` False and `DOWN`, so the UP is about a fresh beat
and not about a check that is always UP.

**C3 — the same fixture made visible, and the proposal was wrong.** The first
proposal was *"on failure, beat with a note"*, inside the recorder. Planted in
the fixture, **the note was not there afterwards.** Why: the recorder runs
inside `snapshot` (`:189`) and the loop beats unconditionally at `:663`, and
`watchsink.beat` **rewrites** the heartbeat file through `os.replace`. The
READ-ERROR path escapes this only because it beats inside its `except` branch
and then `continue`s, skipping `:663`.

So the repair cannot live inside the recorder. With the note carried by the
loop's **own** beat, C3 holds: the beat gains the note, C2's assertion becomes
false, and the detector is proven able to detect.

**And then the half the brief did not ask for:** with the note present,
`witnesses()` still says **UP**. Nothing reads a note. The emission repair
makes the failure legible to a human who looks and does not make it visible to
the system.

---

## 5. THE REPAIR — WRITTEN, SCOPED, NOT WIRED

### Half one — EMISSION. Two lines, in the monitor loop, reversible.

**This is a change to what is emitted.** It does not change what the system
does on failure.

    # scripts/bison_watch_loop.py, inside `_bounce_recorder`, at the except
    # branch that currently only emits:
            except Exception as exc:
                emit(f"BOUNCE-RECORD-FAILED {provider_id}: {type(exc).__name__}")
    +           record.failed = f"BOUNCE-RECORD-FAILED {type(exc).__name__}"
                return
    +       record.failed = None          # cleared on every successful poll

    # and at the unconditional beat, `:663`:
    -   watchsink.beat("bison", campaign=watched, state=current)
    +   watchsink.beat("bison", campaign=watched, state=current,
    +                  note=getattr(on_queue, "failed", None))

`watchsink.beat` already takes `note=` and already omits the key when it is
`None`, so a healthy poll's beat is byte-identical to today's. **Proven to
work in a fixture** (C3) and proven insufficient alone by the same fixture.

### Half two — ONE READER, and it is not a monitor loop and not a gate

A note nothing reads is a note. The cheapest reader that already exists in the
operator's own path is the Slack watcher readback: `src/slackagentreadback.py`
builds `{"watcher", "at", "pid"}` per beat and drops the note. One key:

    -           "pid": b.get("pid"),
    +           "pid": b.get("pid"),
    +           "note": b.get("note"),

Still emission-side. It changes no verdict and refuses nothing.

### What I am NOT proposing tonight

Making the supervisor's verdict depend on the recorder — "alive but not
recording" reading as something other than UP — is a **gate**: it changes what
healthy means and what a human does about it. So is halting, retrying, or
refusing to send while the recorder is failing. Both are firmly the
operator's.

### RECOMMENDATION

**Do half one and half two together, as one change, and do not touch the
verdict.** Four lines across two files, no behaviour change, fully reversible,
and it converts an unbounded silence into a line the operator already looks at.
Half one alone is not worth shipping — C3 measured that it changes no verdict
and C1 measured that nothing reads a note — and that is precisely why it is
quoted here with its own limitation rather than as a fix.

If only one may land: **half two**, because it is outside the monitor loop and
immediately makes the READ-ERROR note — which exists today and is read by
nobody — visible for the first time.

---

## 6. WHAT WOULD CHANGE THIS DOCUMENT

* **A reader found anywhere not searched** (§1's table). The claim is "zero
  readers in the two trees I may read", not "zero readers".
* **`bison._paged` raising rather than truncating** would not affect this, but
  **a provider read that fails rather than raising** would: the recorder is
  only reached when `snapshot` got a queue at all.
* **Whether any watcher is running right now.** UNKNOWN by boundary. If none
  is, the recorder is not failing — it is not running, which is TASK-0160's
  finding about the stop, one layer along, and a worse version of the same
  thing.

---

## 7. THE RE-DISPATCH, 2026-10-16 — THIS DOCUMENT WAS NOT CITATION-CHECKED

The dispatcher handed `0220` to this lane a second time. The work of §0-§6 was
already committed at `e59b70258` and is re-verified below, so the re-run had to
earn its own finding. It did, and the finding is about **this document**.

`scripts/citecheck.py` was built by TASK-0210 for exactly this purpose and
improved again by its re-dispatch at `4dc332693`. Run against this file for the
first time, on `4dc33269327dc09c8d21428adf5d122c320d8f53` in
`wt-suppression-2026-10-14`:

    TOTALS  OK=1  MOVED=0  BROKEN=0  UNVERIFIABLE=10  REFUSED=11  ERROR=0

**One of twenty-two.** Three separate defects, all of them mine, none of them
caught by the first run because the first run never pointed the checker at its
own output.

**D1 — the preamble named the wrong number, and it was typed.** It said "the
three into `scripts/bison_watch_loop.py` come back `REFUSED`". Eleven do. The
same lane had already been caught three times in one night writing a number
from memory; this is the fourth, in the sentence that claims the citations are
measured. Corrected.

**D2 — ten citations named no symbol, so nothing could check them.** The
checker's own docstring says a bare `file:123` is "a claim nobody can test",
that printing it as OK "is how an instrument that checks nothing reports
clean", and that a document "may not be called verified while that count is
above zero." This document carried ten and described itself as verified. Each
of the ten was read out of the `HEAD` blob one line at a time on re-dispatch
and **every line number was correct** — so the claims were true and
unfalsifiable at the same time, which is the weaker of the two properties this
estate cares about. All ten now name their symbol; `UNVERIFIABLE` is **0**.

    src/watchsink.py:261                  events
    scripts/qa/check_readback.py:592      log_last_line
    src/supervisor.py:695                 witnesses
    src/supervisor.py:230                 bison_campaign_id
    src/slackagentreadback.py:330         heartbeats
    src/slackknowledge.py:429             heartbeats
    scripts/cold_start.py:132             "note": row.get
    src/leadobserve.py:753                record_bounces
    (and lines 227 and 233 of the sibling REDISPATCH document, written in
    prose rather than in path:line form below, because the ELIDED path this
    table first used does not exist at HEAD and read BROKEN - which the new
    test caught in this very section)

**D3 — and the REFUSALS were covered in part while the document said in
full.** §1 said the loop citations "are verified here by hand and by
`test_the_cited_lines_are_the_lines`". That test asserted **five** of the
eleven. Lines **189, 599, 654, 655, 656 and 657** were typed and never
measured — including both lines of the READ-ERROR comment that §2 quotes as the
asymmetry this whole document rests on. All six were read from the `HEAD` blob
and all six are correct, so again: true, and unchecked.

**D3 is the one that generalises, because `REFUSED` reads like a pass.** It is
printed beside `OK` in a totals line, it is not the checker's fault, and it
means *nobody looked*. So the fix is not another promise in prose:
`test_citecheck_refuses_only_lines_this_module_asserts` now requires the set of
lines the checker REFUSES and the set `LOOP_CITATIONS` asserts to be **equal**.
Cite a new line of the loop without asserting it and the module goes red.

### What is now measured, and the control under it

    OK  20   MOVED 0   BROKEN 0   UNVERIFIABLE 0   REFUSED 11   ERROR 0
    all 11 REFUSED lines asserted by LOOP_CITATIONS, by set equality
    tests/test_the_bounce_recorders_failure_is_unobservable.py   23 tests, OK, 2 skips

Twenty OK rather than eleven because this section cites nine more lines, and
they are checked on the same terms as the rest. **The assertion is on the four
states that mean UNCHECKED - UNVERIFIABLE, MOVED, BROKEN and ERROR, each at
zero by name - and not on a total**, because a total reddens when a correct
citation is added, which teaches an author to delete the assertion. It earned
that shape immediately: the first draft of this very section cited an ELIDED
path - `docs/NINE-HUNDRED-…-REDISPATCH-...` with the middle cut out, which is no
file at HEAD - and one bare line, and the new test went red on both before this
document was committed.

`test_the_control_on_the_citation_verdict` is the proof that those two
assertions can fail: a fixture document is written with three citations — one
correct, one bare, one whose symbol is on a different line — and the checker
must answer `OK`, `UNVERIFIABLE` and `MOVED` respectively, with the `MOVED` row
naming line **753**. If the correct one did not come back OK the instrument is
dead; if the other two came back OK it is blind. Both halves are asserted, so
neither failure mode can pass for the other.

### One small gap in the checker, found by using it and NOT fixed

`row` is in `citecheck.NOT_A_SYMBOL`, so `` `row.get("note")` `` could not be
used as the symbol for `scripts/cold_start.py:132` `"note": row.get` — the
first identifier of the rejected fragment is `row`, and a stop-word is not
evidence. The citation was rewritten to name `"note": row.get` instead, whose
first identifier is `note`. **Widening the
stop-list to make a citation pass is the "never widen a lint rule to make a
draft pass" shape**, so it was not widened; the citation was regenerated. Worth
one line in whoever owns `citecheck` next, not a change here.

### The two numbers the re-dispatch re-measured rather than assumed

* `tests/test_the_bounce_recorders_failure_is_unobservable.py` at
  `4dc33269327dc09c8d21428adf5d122c320d8f53`, **before** any edit: 20 tests,
  `OK`, 2 skips. The two skips are C3 deliberately overriding the two inherited
  C2 assertions whose inverse it asserts — they are not unexercised controls.
* `origin/master` re-fetched: **`b1f290c847eb2500b7eb39987ac34f6d6a8d00d2`**,
  unchanged.

**Nothing in §0-§6 changed.** The recorder's failure is still unobservable, the
window is still UNBOUNDED, the direction still lands on `PASS` rather than
`UNKNOWN`, and §5's repair is still written and still not wired. This section
corrects how this document proves itself, not what it found.
