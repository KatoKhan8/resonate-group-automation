# The other two bounces, and the bounce gate prepared both ways

TASK 0110, suppression lane, 2026-10-15. Everything below was measured on
commit `9bd8648f5` in worktree `wt-suppression-2026-10-14`, which is a CRLF
tree. No provider call, no Apify call, no network call, no send. Nothing was
applied: both branches exist as patch files and as temporary trees under
`%TEMP%\rga-0110`, and neither touches this worktree, which is clean.

---

## 0. NO CANARY-01 CONTACT IS AMONG THE FIVE. NOT ONE, IN EITHER DIRECTION.

The task asked for a STOP at the top of the report if any of the five bounces
is in the CANARY-01 cohort. **It is not a STOP.** The clean answer, with the
same precision the dirty one would have had:

    the three suppressed   x  the 25 approval-sheet rows   EMPTY
    the three suppressed   x  the ten-company cohort       EMPTY
    the 25 rows            x  the whole 108-row agency DNC EMPTY
    the two NOT suppressed can only be leads of campaign 503,
    and no canary address or domain is in 503's 250 leads   EMPTY

Every one of those has a positive control that fires, because an intersection
that returns empty because the reader is broken looks exactly like a clean
estate. §1.4 gives the controls.

**The attach is not blocked by this lane.** Nothing else in this file changes
that answer.

---

## 1. THE FIVE, AND WHY TWO ARE NOT ON THE LIST

### 1.1 The population, re-measured rather than quoted

Read now from `work/heartbeat/bison-*.json` in the main checkout — the twenty
`scripts/bison_watch_loop.py` processes' own output, beats stamped
2026-10-15T20:14:49Z–20:17:21Z. No provider call was made; the watchers had
already paid for the reads.

    491  paused     bounced 1    sent 411   leads 333   queue 665
    492  paused     bounced 1    sent 245   leads 206   queue 409
    495  archived   bounced 1    sent  42   leads  60   queue 114
    503  paused     bounced 2    sent  25   leads 250   queue 500
    the other 16 watched: 0

    TOTAL             5          918       1,516

Identical to the figures 0090 took at 19:09Z yesterday evening, three hours
and twenty watcher restarts of beats later.

### 1.2 The three that ARE on the list, by fingerprint

The agency DNC in the main checkout's `work/` holds **108 rows**, sha256
`6c6485b1b0ca33d47c24dfc861337e78fd3e249298f0b7d8485599cb9c637d93`, unchanged
since 0100 wrote it — 100 `requested`, 6 `internal`, 2 `legal`. The three
0100 added, taken as the set difference against the reversal manifest's
`before.fingerprints` rather than retyped:

    0a5148a392afd2db74e2df98932dcb9b7e91cfe299f1027b8e03184cbda25228
    d13e93d56e314e02d1ad136183b326675b39586d50b6ea9e73f5dd58babd0a6c
    f38022b4e74b6e516baeba4d6704c94317978c31f2ace17b339a28a610e97871

**They are exactly the bounced population the snapshot can see, and that was
re-derived here rather than taken from 0070.** Scanning
`PROVIDER-SUPPRESSION-SNAPSHOT-FULL.json` for every email carrying a `bounced`
status and hashing each through `agencydnc.fingerprint("email", …)`:

    0a5148a392afd2db…   campaign 491   lead 204668   3 source files agree
    f38022b4e74b6e51…   campaign 492   lead 204472   3 source files agree
    d13e93d56e314e02…   campaign 495   lead 204562   3 source files agree

    set equality with the three applied:  TRUE

### 1.3 The two that are NOT: 503's, and why the manifest could not hold them

The other two are **campaign 503's**, at `2026-09-25T12:32:20Z` and
`2026-09-25T12:54:34Z`. They are not nameable from anything on this machine,
and the reason is not that 0070 asked the wrong question.

**They fell outside the SOURCE CORPUS, not outside the query.** 0070's manifest
came from the snapshot, whose five provider-side sources were all written
before campaign 503 existed:

    stage/pc-leads.jsonl                 written 2026-09-24T18:12:20Z
    stage/pc-sends.jsonl                 written 2026-09-24T18:12:21Z
    stage/pc-lead-sends.jsonl            written 2026-09-24T18:27:49Z
    stage/reengagement-inventory.jsonl   written 2026-09-23T21:05:31Z
    lead-observations.jsonl              written 2026-09-13T09:28:53Z

    campaign 503 attached                        2026-09-25T11:53:06Z
    503's first send                             2026-09-25T12:29:10Z
    503's two bounces                            2026-09-25T12:32:20Z, 12:54:34Z

The snapshot carries rows for 22 campaign ids and **zero** for 503, 504 or
505. A query over it could not have returned them under any phrasing. (Two of
the sources carry dates as late as 2026-09-30 in their coverage window; those
are `scheduled_date`s in the future, not later writes. The file mtimes above
are the authority for when the data was captured.)

**And the watchers, which DID see them, record a count and never an identity.**
`work/watch-events/bison-503.jsonl` is 71 lines; six mention a bounce and this
is all six carry:

    BOUNCE 503 bounced 0 -> 1
    MEMBERSHIP 503 per-lead status {in_sequence: 250} -> {in_sequence: 249, bounced: 1}
    BOUNCE 503 bounced 1 -> 2
    MEMBERSHIP 503 per-lead status {…, bounced: 1} -> {in_sequence: 248, bounced: 2}
    MEMBERSHIP 503 … -> {sending_paused: 248, bounced: 2}
    MEMBERSHIP 503 … -> {sending_paused: 164, stopped: 84, bounced: 2}

A counter and a histogram. No lead id, no row id, no address — by design: this
loop's state is written verbatim into a heartbeat file and
`emptyrender.scan` already forbids prospect identifiers there. **Naming the two
still needs one EmailBison read of 503's queue (500 rows, 34 pages), which this
task may not make.** That is unchanged from 0090 and is re-asserted here
rather than assumed.

### 1.4 The canary check, both directions, with its controls

**The canary set.** 25 rows parsed out of `canary/APPROVAL-SHEET-2026-10-15.md`
by its own `### Row N` headings and `- contact: … <address>` lines: 25 rows,
25 addresses, 25 distinct fingerprints, of which the ten of
`DECISION-canary-cohort-and-pool-2026-10-15.md` are rows 3, 4, 5, 7, 8, 9, 10,
13, 15 and 17.

**Against the three.** Intersection with the three applied fingerprints:
EMPTY, both directions. Intersection with the whole 108-row list: EMPTY.
*Control:* the same loop over a candidate set with one listed digest injected
returns exactly that one. The first version of this check called a
`lst.lookup()` that does not exist — `agencydnc.load()` returns a plain dict —
and returned "NONE" for everything. It was caught by the control and redone;
the number above is from the redone one.

**Against the two.** They cannot be fingerprinted, so the question was turned
into one that can be answered: **is any canary contact a member of campaign
503 at all?** 503's membership is known exactly, from four sources that agree:

    the file the push actually read
      .claude/worktrees/agent-ad212f18841597a60/work/copy-US-East.jsonl   250 rows
    work/503-linkedin.json          250 addresses, set-equal to the above
    work/503-pack-coverage.json     250 domains, domain-set-equal to the above
    the provider's own readback     "READBACK 503: provider total_leads=250 |
                                     of our 250: present=250 missing=0"
    today's heartbeat               leads=250

    canary addresses in 503:  EMPTY        canary domains in 503:  EMPTY
    503 leads already on the agency DNC:   0

*Control:* injecting one real 503 address into the canary set makes the same
test return exactly one hit.

**So whoever the two are, they are not CANARY-01 contacts** — not because
their identities were checked, but because the population they must come from
contains no canary contact. That is a stronger statement than a fingerprint
comparison could make here, and it is the only one available without a
provider read.

---

## 2. THE BOUNCE GATE, PREPARED BOTH WAYS. NEITHER APPLIED.

`leadobserve.confirm_email_touches` still has zero production callers. Both
branches give it one, in the loop that has already paid for the read, and they
differ in **one function**.

### 2.1 What both branches share

`src/leadobserve.py` — two optional parameters and one new function:

* `scheduled_rows(campaign_id, queue=None)` — trim rows somebody else already
  fetched, instead of fetching them again.
* `confirm_email_touches(…, rows=None)` — consider rows the caller narrowed.
* `record_bounces(campaign_id, queue=None, recs=None, live=False)` — filter to
  `state == BOUNCED` **before** the writer, then delegate.

`scripts/bison_watch_loop.py` — `snapshot(provider_id=None, on_queue=None)`
calls `on_queue(queue)` once, when the read succeeded, and `main()` passes a
recorder built from `_bounce_recorder(watched, emit)`.

Three properties, each deliberate:

1. **Zero additional provider calls.** The rows are the ones `snapshot` has
   already read at `bison.CAMPAIGN_QUEUE_PAGE_CAP = 400`. The precedent is in
   that file already — the blank-content scan runs there for the same reason.
2. **Bounce-only, structurally.** A `sent` row never reaches `events.record`,
   so the 918 `sent -> PUSH_MARKED` touches — and the silent change to
   `fatigue.contact_check` they would cause — cannot happen by accident.
3. **No prospect identifier leaves `snapshot`.** Everything the function
   returns is written verbatim into `work/heartbeat/bison-<id>.json`; the rows
   carry the address, our `record_id` and our `contact_key`. `on_queue` is how
   they reach a consumer without reaching the heartbeat.

### 2.2 HARD — a bounce suppresses

`live=True`. The event lands on the record, `channels._bounced` reads it, and
`eligibility.decide` refuses the address inside `_email_checks` before MX and
before verification — permanently, no decay, no threshold.

**It does not write to the agency DNC, and that is a decision, not an
omission.** That list is person-level on every channel, and `src/agencydnc.py`
says in its own docstring that a row there is "written deliberately by a super
admin, never derived". The three rows of 0100 were a human decision about
three named people. A mechanism may not write there. So HARD closes the
ADDRESS on the EMAIL channel; it does not close the person on LinkedIn, which
is also what 0070 argued for on the merits — a dead mailbox says nothing about
the same person's LinkedIn.

**What it does to volume, if the estate's rate holds.** Both rates measured
from `canary/sender-estate-export-2026-10-15b.csv`, 181 mailboxes:

    all 181 mailboxes            175,237 sent   1,771 bounces   1.0106%
    connected, real owner (128)  147,678 sent   1,237 bounces   0.8376%
    our own 20 campaigns             918 sent       5 bounces   0.545%

    daily caps in the same export:  2,715 total | 2,685 connected
                                    1,920 connected with a real owner

    people closed per week, five sending days:
      at 2,685/day (whole connected estate, 1.0116%)   136 /wk
      at 1,920/day (real-owner mailboxes only, 0.8376%)  80 /wk
      at CLAUDE.md's forward book, 1,470/day, 1.01%      74 /wk   (figure of
                                                                   2026-09-22)
      at today's actual rate                              0 /wk   (nothing of
                                                                   ours sends)
      over the whole of CANARY-01, ten openers           0.08 people

**The honest reading of those numbers:** the volume HARD costs is not 80-136
people of reach a week, because the mail to those addresses was bouncing
anyway. What it costs is only the TRANSIENT bounces — the addresses that would
have worked next week — and **what fraction that is is UNKNOWN and not
knowable from this provider.** EmailBison exposes no bounce code, class or
SMTP status on any surface this repository has measured; `hard_bounced` and
`soft_bounced` exist only in two of our own allowlists and have never been
observed. The authority that would settle it is a provider field that does not
exist.

### 2.3 SOFT — a bounce is surfaced and a person decides

`live=False`. Nothing reaches the record.

**What surfaces it, and where.** Two surfaces, because one of them is not
durable:

* `emit(...)` writes `BOUNCE-NEEDS-REVIEW <campaign> row=<id> step=<n> NOT
  APPLIED - a person decides` into
  `work/watch-events/bison-<id>.jsonl`, which survives the shell. Ids only, no
  address, no contact key.
* `notify.notify(EMAIL_BOUNCE_NEEDS_REVIEW, …)` routes **GLOBAL /
  ACTION_REQUIRED** — the ops room, not the client's. `CAMPAIGN_MILESTONE`,
  which the watcher's existing `milestone()` helper uses, routes to
  **WORKSPACE**, and a bounce is not a line a client's room should carry.
  `scripts/notify_deliver_loop.py` is the deliverer and was measured running
  as pid 38056 at 22:19 today, so this surface is live rather than theoretical.
  The notification's `ids` make it idempotent: a bounced row stays `bounced`
  for ever and the watcher re-reads it every 180s, so without them this is a
  Slack line every three minutes.

SOFT is therefore the LARGER change: three files instead of two, a new
notification kind and a new row in the routing table, plus a CLI flag for the
human's apply step (`--bounces --live`) that this patch does not yet add.

**What happens to someone whose bounce is never read: nothing happens, and
that is the failure mode.** The address stays `sendable=True`, verdict
`valid`. Every later step of the sequence is sent to it and bounces again.
`work/watch-events/` is not a queue anybody works, and an ACTION_REQUIRED
Slack line is read or it is not. Each unread bounce keeps degrading the
sending mailbox's bounce rate, which is a per-mailbox reputation figure shared
by every campaign that mailbox sends — 0070 already measured
`channels.email_verdict` answering SENDABLE for three addresses the provider
had rejected weeks earlier, which is exactly this failure with the review step
missing entirely.

**One structural argument the operator should have before choosing.** In this
codebase the canonical event for a bounce ALREADY MEANS blocked: `channels.
_bounced` is the only consumer of `EMAIL_BOUNCED` on the send path. SOFT
therefore cannot record the truth and defer the consequence — it has to invent
a second, weaker representation of the same fact and keep it somewhere the
canonical model does not look. That is the "parallel state machine for the
same fact" CLAUDE.md warns about, and it is the reason the SOFT patch is
bigger than the HARD one rather than smaller.

**Recommendation, unchanged from 0090: HARD.** The cost of a wrong HARD lands
on one prospect. The cost of a wrong SOFT lands on the sending reputation of
the whole estate, and it compounds. If the operator wants the SOFT safety net
anyway, the cheap version is HARD plus a weekly report of what it closed —
reversible by hand, with the canonical state still correct.

### 2.4 The three states, measured

Same SHA (`9bd8648f5`), same tree origin: every tree below is `git archive
HEAD` into `%TEMP%\rga-0110`, so they differ only by the patch. Failing names
are extracted with `run_suite._parse_failures`, never grepped.

The born-red module is 0090's `test_a_provider_bounce_reaches_the_record`, with
one change made identically in all trees: `run_the_scheduled_producers` now
also runs **one cycle of the real `bison_watch_loop.main()`**, stopped at its
first `time.sleep` by a `BaseException`. It names no function a patch might
add, so the test stays agnostic about which module records the bounce — which
is what that file's docstring promises.

    STATE                                      failing names in the module
    A  clean (15 tests)                        6
       the five 0090 measured, plus
       TheSameBounceIsNotRecordedTwice
    B  HARD                                    1   (the vocabulary case only,
                                                    red by design - it needs
                                                    the EMAIL_STATES widening)
    C1 HARD, live=True -> live=False           6   exactly state A's set
    C2 HARD, bounce-only filter removed        2   vocabulary + OnlyTheBounce
                                                   IsRecorded

    B' SOFT, same module                       6   exactly state A's set -
                                                   SOFT satisfies none of it,
                                                   and that is correct
    A' clean, the SOFT module (6 tests)        4
    B" SOFT, the SOFT module                   0   all green
    C3 SOFT, the review line removed           2   the two surfacing cases

**Two tests in this set exist only because a mutation ran and nothing
noticed**, which is the part of the method worth keeping:

* `OnlyTheBounceIsRecorded.test_a_sent_row_does_not_become_a_confirmed_touch`.
  Removing the bounce-only filter — the mutation that writes 918 confirmed
  touches — left the module at its unmutated name-set, because every other
  case asks only about `EMAIL_BOUNCED`. The property with the largest blast
  radius in either branch was the one with no test.
* `test_the_notification_is_planned`. The SOFT recorder's first
  `notify.notify` call passed keyword names the function does not take, raised
  `TypeError` on every bounce, was swallowed by the recorder's own `except`,
  and the file still passed on the emit line alone. A surfacing branch whose
  Slack half is dead is SOFT with one surface, and the durable one is a log
  nobody reads.

### 2.4a The blast radius, by name-set, same SHA and same tree origin

The observer set was enumerated by measurement rather than argued from the
kind of file: every module under `tests/` whose source names `leadobserve` or
`bison_watch_loop` — the two files HARD changes — and for SOFT additionally
every module naming `ROUTES`, `EVENT_TYPES` or `destination_for`, which is the
table SOFT adds a row to. Names via `run_suite._parse_failures`.

    HARD   15 modules, 327 tests
      clean   18 failing names
      hard    13 failing names
      only in clean   the 5 bounce names, which is the change
      only in hard    NONE

    SOFT   41 modules, 1,112 tests
      clean   35 failing names
      soft    35 failing names
      set difference, both directions   EMPTY

SOFT moving nothing is the correct result and not a null measurement: it adds
a routing row and surfaces a line, and it satisfies no part of the record
invariant, so the only names it may move are in its own new test file — where
it turns 4 red names green (§2.4, A' vs B").

**This is NOT a substitute for the full reference either branch owes.** The
operator's rule of 2026-10-02 admits no exception for a change under `src/` or
`tests/`, and both branches change both. What this bounds is the set a reader
would look at first; it is 1,112 tests of roughly 14,750.

**One caveat on these four runs, named rather than buried:** they overlapped
the full reference run this lane launched at 22:00:18Z, and
`tests.test_tenancy_penetration` in the SOFT set binds loopback. The clean and
patched runs were taken back to back under the same conditions, so a flake
would have to be asymmetric to survive a set comparison — but the SOFT result
is "nothing moved", which is exactly the shape a symmetric flake cannot
disturb and an asymmetric one could. Re-runnable in seconds with
`work/suppression-measure/0110/blast.py`.

### 2.5 "The producer cannot read 491 at all" — it is OUR CALL

Not the producer, not the provider.

* `bison.scheduled_emails(campaign_id, cap=None)` takes a cap and documents
  why: "`cap` RAISES THE PAGE LIMIT FOR A CALLER THAT GENUINELY NEEDS EVERY
  ROW, and it does not weaken anything."
* `scripts/bison_watch_loop.py` passes `cap=bison.CAMPAIGN_QUEUE_PAGE_CAP =
  400` and reads 491's 665-row queue every 180 seconds without difficulty —
  measured again today, `queue_rows: 665` in a beat stamped 20:16Z.
* `leadobserve.scheduled_rows` passes **no cap**, so `_paged` takes
  `PAGE_CAP = 40`, and this route serves 15 rows a page. 45 pages. It refuses.

So the provider can answer, the provider module can ask, and one call site does
not. **The shared patch makes it moot for the watcher path** — the rows come
in through `queue=`, already read at 400 — and `scheduled_rows`' own default
is left alone deliberately, because the refusal is the right behaviour for a
caller that has not sized its read.

**Who else is blind: one campaign of twenty, today.** The limit is 40 pages ×
15 rows = 600 rows, measured per campaign from today's beats:

    491   665 rows   45 pages   REFUSES
    503   500        34         reads     (100 rows of headroom)
    504   446        30         reads
    505   434        29         reads
    492   409        28         reads
    494   152   495  114   493   64   498  26   487  20   496  17
    489    15   497   13   481   10   451   1   501   1   506   1
    484     0   485    0   500    0

It is a property of SIZE, not of the campaign: anything crossing 601 rows goes
blind, and 503 is one good cohort away. The four operator-declared internal
campaigns (274, 327, 328, 352) have sent roughly 209,000 emails between them
and are certainly far past it — they are never read by this path and must
never be written to, so that is a statement about reach and not a gap to fix.

---

## 2.6 The two prepared branches

Built with git plumbing against a temporary index, so the working tree was
never checked out, never moved off its branch and never modified:

    task-suppression-bounce-HARD-2026-10-15   2c131cb20
      3 files, +238 / -7
    task-suppression-bounce-SOFT-2026-10-15   dc79a4b6c
      5 files, +399 / -7

Both are children of `9bd8648f5`. Neither is merged, neither is near master,
and neither is in any running process. The equivalent patch files are in
`work/suppression-measure/0110/`, and all four apply clean to a pristine
`git archive HEAD` (`patch -p1 --dry-run`, no fuzz).

---

## 3. THE REFERENCE THIS BRANCH OWED — TAKEN, AND IT IS 233 NAMES

The lock was **not** held by a live process: `work/suite.lock` still carried
`task-glm-b-2026-10-14` pid 77584 from 21:39:18, and that pid was measured
GONE twice, seven minutes apart, through `Get-CimInstance Win32_Process` with
a self-check, with no `run_suite` process anywhere among 537 and then 567
processes. `suitelock` took the stale lock over itself; nothing was unlinked
by hand and no live lane's lock was touched. The run took it at 22:00:18Z and
released it at 22:57; the next waiter (`integ/canary-nine-2026-10-15`) had it
five seconds later, so the FIFO queue worked.

    status=FAIL   exit_code=1   wall_seconds=3454.5   timed_out=False
    results_reached=14766        failures=234         partial=False

Against the 227-name reference measured on `acf078b72` — read out of that
run's RAW log with `run_suite._parse_failures`, **not** out of its summary
file, which parses to zero names — the diff is **+7 and -0**:

    +5  the born-red bounce names 0090 intended
    +1  test_a_provider_bounce_reaches_the_record.TheSendPathRefusesIt.
          test_without_a_bounce_the_refusal_is_the_other_one
    +1  test_fixture_hygiene.TestKnownSets.
          test_every_phone_number_is_a_reserved_fiction

**The hygiene name is my own artefact and it is positively attributed.** The
traceback is `FileNotFoundError` on
`docs/SUPPRESSION-THE-OTHER-TWO-AND-THE-BOUNCE-GATE-2026-10-15.md` — this
file. `tracked_files()` lists untracked-but-not-ignored files, I wrote the
draft into `docs/` while the run was in that module and moved it out two
minutes later, and the test listed it and then could not read it. Re-run alone
on the clean tree the module gives **5** names, the same 5 the reference
carries. It is not a property of `9bd8648f5`.

**The control name is real, and it is a test-isolation defect worth having
found.** `test_without_a_bounce_the_refusal_is_the_other_one` passes alone and
fails inside a full run with `'held:verification_unknown' != 'blocked:lint_
failed'`. Cause, proven rather than inferred: `lint.policy_for_record` caches
the verification policy per client in a **module-level dict** cleared only by
`lint.forget_policies()`, and this module runs after fifty-eight others,
several of which rewrite a client config. Seeding
`_POLICY_CACHE["productive"] = None` once, as a previous module would leave
it, reproduces all three failures and the exact message; with the one-line
`lint.forget_policies()` the branches' test patch adds to `setUp`, the same
poisoning leaves the control green and only the two genuinely red names
behind.

**So the reference for `9bd8648f5` is the 233 names** in
`work/suppression-measure/0110/REFERENCE-9bd8648f5-233-names.txt` — this run's
234 minus the artefact. A future run on this tree should reproduce exactly
that set. 232 was the expectation 0090 recorded; the 233rd is the isolation
defect above, which was always there and had never been run in a suite before
because the module did not exist until `617c2a1ac`.

---

## 4. WHAT THIS DOES NOT DO

* **Neither branch is applied.** `src/`, `scripts/` and `tests/` in this
  worktree are byte-identical to `9bd8648f5`; the patches live in
  `work/suppression-measure/0110/` (gitignored) and the trees under `%TEMP%`.
* **Neither branch takes effect until the twenty watchers are restarted.**
  They have been running since 2026-10-14/15 and hold the old code. A restart
  is an operational action on live monitors and is outside this task.
* **The vocabulary case stays red in both branches.** Widening
  `leadobserve.EMAIL_STATES`, or making an unrecognised bounce-shaped status a
  loud refusal instead of `waiting`, is 0090's STEP 4 and a separate change.
* **503's two bounces stay unnamed.** One EmailBison read of 503's queue
  answers it; this lane may not make it.
* **A full suite reference is still owed by each BRANCH.** §3's 233 names are
  the reference for `9bd8648f5`, which is what the branches are measured
  FROM. The operator's rule of 2026-10-02 means each branch owes its own run
  before it merges, because each changes `src/` and `tests/`.
