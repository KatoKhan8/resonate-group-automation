# TASK-0180 RE-DISPATCH — the chain is real, its citations were typed, and the backfill is one flag away

Measured in `wt-suppression-2026-10-14` on branch
`task-suppression-bounce-RULE-2026-10-15` at **`81475191a`**, which was HEAD
when I was invoked. `origin/master` is **`b1f290c84`**, unchanged. No provider
call, no network call, no send, no activation, nothing prospect-facing, no cap
or gate change. **Nothing was wired.** `src/providers/*` was not opened; where a
line from it appears below it came from a repository-wide `grep` and that is
said at the point of use.

---

## 0. WHY THIS DOCUMENT EXISTS

`queue\suppression\RUNNING\0180-nine-hundred-sends-one-confirmed-touch.md` was
handed to me, and **TASK-0180 was already complete** — committed `ecebdca51` at
02:13 with a full lane entry, and its deliverable is
`docs/NINE-HUNDRED-SENDS-ONE-CONFIRMED-TOUCH-2026-10-16.md`, 413 lines. This is
the second time this lane has been handed a finished brief; `0170` was the
first, four hours ago.

Per `_STANDING-RULES.md` — *"before certifying another lane's work, re-measure
its gate yourself, at the moment you look"* — restating 0180 would have been
worthless and exiting would have been NOWORK. So this run **audits 0180's own
deliverable against the code**, at HEAD, the same way the 0170 re-dispatch did.

**The headline: 0180's analysis is substantially correct and I confirmed its
arithmetic exactly. Its central citation is wrong by two lines, its stated
reason for its largest finding cites an authority that does not say what it is
said to say, and it missed two defects — one of which is the only reachable
hazard in this whole chain.**

---

## 1. WHAT I CONFIRMED — re-measured at `81475191a`, not taken on trust

| 0180 claim | verdict at `81475191a` |
| --- | --- |
| `confirm_email_touches` **has** a production caller, via the watcher's bounce recorder | **CONFIRMED.** The chain is real and the refutation of the brief's premise stands |
| the cost table: 2,888 rows / 205 pages / 20 campaigns; our ten 1,495 rows / 105 pages; largest 665 | **CONFIRMED EXACTLY.** Recomputed from `docs/state/QUEUE-COUNTS-2026-10-15.json` with `OURS` loaded from `scripts/bounce_stop_7day.py` (= 487, 489, 491–498) and `PAGE_SIZE = 15`: 2,888 / 205 / 1,495 / 105 / 665, and hourly 2,520 / 4,920, 180s 98,400. Every figure reproduces |
| `max(1, ceil)` — an empty queue still costs one request, so 205 requests against 202 pages | **CONFIRMED.** Without the `max` the sum is 202; with it, 205 |
| the cooling rule reads provider confirmations or HOLDs | **CONFIRMED.** `src/suppression.py:114` `UNKNOWN_IS_NOT_A_PASS = True`; `:77` `HOLD_TOUCH_HISTORY_UNKNOWN` |
| the per-mailbox daily volume counts **attempts**, deliberately | **CONFIRMED.** `src/actionledger.py:144,178,220` default `states = (SENT, ATTEMPTED, UNRESOLVED)`; `:58` `BLOCKING = (ATTEMPTED, UNRESOLVED)` |
| `EVENT_FOR` maps `sent → PUSH_MARKED` | **CONFIRMED.** `src/leadobserve.py:400-404` |
| `scheduled_rows` passes no cap, so it takes `PAGE_CAP = 40` (600 rows) and cannot read 491 at 665 | **CONFIRMED.** `src/providers/bison.py:822-823` `PAGE_CAP = 40`, `PAGE_SIZE = 15` (grep, file not opened) |
| `--confirm` is dry unless `--live` and prints five counts | **CONFIRMED.** `src/leadobserve.py:805-828` |
| `EMAIL_DELIVERED` has no producer, so every delivery figure is structurally zero | **CONCLUSION CONFIRMED, REASONING CORRECTED — §2** |

So the useful half of 0180 holds, and I am not re-stating it. What follows is
only what it got wrong or did not ask.

---

## 2. DEFECT 1 — THE PROVENANCE WAS TYPED, NOT MEASURED. AGAIN.

0180's §0 refutes the brief's premise with a four-line call chain. That
refutation is the single most load-bearing claim in the document. **Two of its
four citations are wrong.**

    0180 said                              measured at 81475191a
    ----------------------------------------------------------------------
    bison_watch_loop.py line 643  on_queue  ->  641    WRONG by 2
    bison_watch_loop.py line 647  snapshot  ->  647    correct
    bison_watch_loop.py line 598  record_b  ->  598    correct
    leadobserve.py line 789       confirm_  ->  790    WRONG by 1

    (TASK-0210: written as `line N` rather than `path:N` deliberately. A
    wrong citation quoted AS WRONG must not be in citation syntax, or every
    run of `scripts/citecheck.py` re-reports the defect this table reports -
    a document containing a defect and a document naming one would be
    indistinguishable to the checker.)
                                              (789 is `rows = scheduled_rows`)

**And it is not drift, because the files did not move.** `git diff --stat
045babe5f HEAD -- scripts/bison_watch_loop.py src/leadobserve.py` is **empty** —
both files are byte-identical between 0180's stated SHA and mine. At
`045babe5f` itself, `git show 045babe5f:scripts/bison_watch_loop.py | sed -n
'639,648p'` puts `on_queue = _bounce_recorder(watched, emit)` on line **641**.
So the citation was wrong at its own stated SHA, when it was written.

The same two wrong numbers are in the commit message of `ecebdca51`, where they
are the body of the correction.

This is the **identical defect** the 0170 re-dispatch found and named four hours
earlier — *"the report's own provenance was typed, not measured"* — repeating in
the next task, in the next report, in that report's most important paragraph.
A line number is a measurement and this lane has now mis-typed one twice.

**The chain itself is real.** I read all four sites. `main()` builds
`on_queue = _bounce_recorder(watched, emit)` at 641 and passes it to
`snapshot(watched, on_queue=on_queue)` at 647; `_bounce_recorder.record` calls
`leadobserve.record_bounces(provider_id, queue=queue, live=True)` at 598; and
`record_bounces` returns `confirm_email_touches(..., event_for=policy,
rows=[row for row in rows if row["state"] == BOUNCED])` at 790. **0180's
correction of the brief's premise is right.** Only its coordinates were wrong.

---

## 3. DEFECT 2 — THE AUTHORITY CITED FOR FINDING 1 DOES NOT SPEAK TO THE CLAIM

0180's FINDING 1 says `EMAIL_DELIVERED` has no producer. **The conclusion is
correct.** How it got there is not.

It wrote that whether `bison.classify_reply_row` can return `"delivered"` is
*"in `src/providers/bison.py`, which this task may not read, so that one link is
UNVERIFIED-BY-BOUNDARY"*, and then: *"The adapter's own docstring is the
authority quoted above and it says no."*

Two things wrong with that:

1. **The docstring does not say that.** `src/adapters.py:172-178`
   (`emailbison_delivered`) says *"Nothing on the **confirmed surface** emits
   these: `/replies` carries replies, bounces and our own sends."* That is a
   statement about the **surface**, not about the classifier. It is cited as
   settling a question it never addresses.
2. **The classifier link was resolvable inside the boundary, and it resolves
   the other way.** A repository-wide grep for `"delivered"` — not a read of the
   file — returns `src/providers/bison.py:2080`
   `WEBHOOK_DELIVERED = ("delivered", "sent", "email_sent")` and `:2099`
   `return "delivered"`. So **the classifier can return `"delivered"`**, for a
   webhook row. I did not open the file to see which function those lines sit
   in, so "which classifier" stays UNKNOWN by boundary — but "it says no" is
   refuted by the constant's existence alone.

### The measured reason, which is better than the one 0180 gave

`src/adapters.py:109-141` `from_emailbison` **already handles a webhook batch**
— `rows = payload.get("events")` at :122, commented *"a webhook batch, same
fields"* — and routes `kind == "delivered"` to `events.EMAIL_DELIVERED` at
:134-135. The producer path is **code-complete**. It is fed in production:
`src/inbound.py:531` `adapter = adapters.ADAPTERS.get(provider)`, reached from
`scripts/reply_watch_loop.py` through `poller.run`.

So why is the figure still structurally zero? Because of what is missing, and
it is not a code path:

    grep -rn "def .*webhook|/webhook|route(\"/hook|hooks/" src/web/    ->  0 rows

**There is no HTTP route anywhere in `src/web/` that receives a provider
webhook.** The only two references to the word in `src/web/api.py` are
`:4330` and `:4333`, which *count* `webhook_rejected` events — a counter for a
door that does not exist. The live surface that IS polled, `/replies`, does not
carry delivery rows.

**Restated, measured:** `EMAIL_DELIVERED` has no producer not because the
adapter or the classifier refuses one, but because **the only payload shape that
yields one can only arrive by webhook, and this system has no webhook
endpoint**. Five consumers (`src/report.py:97,134`,
`src/outcomes.py:296,879`, `src/slackagentreadback.py:397`) read a field no
door can fill, and
`bouncepolicy.ACCEPTANCE_EVENTS` is half-dead exactly as 0180 said.

That matters for the proposal: 0180's §3 implies a vocabulary change is the way
in. It is not the only one. **A webhook receiver would make `delivered` real
with no change to the event vocabulary at all** — and it is the only design in
this chain that costs *zero* provider reads, because the provider calls us.
Whether the EmailBison instance can be configured to send one is a question for
`src/providers/*` and the provider's dashboard, both outside this task:
**UNKNOWN, and it is the single highest-value unknown in §2 of the brief.**

---

## 4. DEFECT 3, AND THE ONLY REACHABLE HAZARD IN THIS CHAIN

**The 918-touch backfill that 0180 §2b calls "a decision nobody has taken" is
reachable by one flag on a documented CLI, and nothing in the module refuses
it.** 0180 does not mention this, and its §4 recommends that exact command
minus the flag.

    py -3 -m src.leadobserve --provider emailbison --campaign <id> --confirm --live

`src/leadobserve.py:814` → `confirm_email_touches(a.campaign, live=a.live)`.
**No `rows=`, no `event_for=`.** That is the UNFILTERED form — the
`sent → PUSH_MARKED` half — and the function's own docstring at :655-658 states
the default plainly:

> The default is unchanged: no `rows` means read the queue and consider all of
> it. `record_bounces` below is the only narrowing this repository has decided
> on.

### Four measurements that make this a finding rather than a worry

1. **No gate exists in the module.**
   `grep -n "killswitch|workspace_state|sending.live|approval" src/leadobserve.py`
   returns **zero rows**. `live=True` reaches `events.record` inside
   `store.transaction()` at :726-745 with nothing in between.
2. **The narrowing 0180 praised as "structural" is not a property of this
   function.** It belongs to `record_bounces` (:790), which builds the list
   comprehension. Called directly, `confirm_email_touches` has no narrowing at
   all. 0180's §0 is precise about this; its §4 then recommends the CLI without
   carrying the distinction forward.
3. **The CLI help advertises it as routine.** `:805-807`: *"record a canonical
   confirmed touch for every lead the provider has reached. Dry unless
   --live"*. The prohibition lives in a docstring 130 lines further down, in a
   different function.
4. **There is no revert.** `ls scripts/ | grep -i revert` returns exactly
   `revert_bounce_suppression.py` — for bounces. Events are append-only, so a
   918-row `PUSH_MARKED` backfill has no scripted undo.

### Stated honestly, because overclaiming this would be the same sin

This is **not** a send, **not** a provider write, and **not** prospect-facing.
`events.PUSH_MARKED` is local, and its effect on `fatigue.contact_check` is to
**hold more people** — the safe direction, which is why nothing has noticed.

The hazard is precisely the one 0180 itself named and then left reachable: it
**silently changes who may be contacted**, at a scale of hundreds of contacts,
in one command, with no confirmation prompt, no cap, no approval, no killswitch
and no undo — and the command is one flag from the one this lane is
recommending the operator run during the canary. A tired operator who reads
`(DRY - pass --live to write)` as an instruction rather than a notice performs
the backfill.

---

## 5. DEFECT 4 — A FAILURE OF THE ONE PRODUCTION CALLER IS UNOBSERVABLE

0180 refuted *"nothing calls it"* and stopped there. It never asked whether the
caller's **failure** can be seen. It cannot.

`scripts/bison_watch_loop.py:596-602`, inside `_bounce_recorder.record`:

        try:
            out = leadobserve.record_bounces(provider_id, queue=queue,
                                             live=True)
        except Exception as exc:
            emit(f"BOUNCE-RECORD-FAILED {provider_id}: {type(exc).__name__}")
            return

Three measurements:

1. **Nothing reads the string.**
   `grep -rn "BOUNCE-RECORD-FAILED" --include=*.py .` returns the producer at
   `:601` and one copy in gitignored `work/suppression-measure/0110/`. **No
   consumer in `src/` or `scripts/`.** Nor is there any generic failure-line
   reader: the sink consumers (`watchsink`, `stopwatchdog`, `slackagentreadback`)
   contain no prefix scan for `BOUNCE*` or `FAILED` over sink lines.
2. **The heartbeat stays green.** The failure path `return`s without calling
   `watchsink.beat`. The loop's *read*-error path at `:656` does beat with
   `note=f"READ-ERROR {errors}x ..."` — deliberately, because *"alive-and-blind
   is a different incident from alive-and-nothing-changed and must not read as
   it."* The bounce recorder has no equivalent. The cycle's normal beat at
   `:663` fires regardless, so `src/supervisor.py`, which reads heartbeats
   through `watchsink`, calls the watcher healthy.
3. **The wrap is deliberate and correct.** The docstring says so: *"a recorder
   is not worth an outage ... must not stop the watcher watching, and must not
   blind the blank-content halt."* I am not proposing to remove it.

**So: a bounce recorder failing on every cycle is indistinguishable from one
with nothing to record, and the heartbeat is green through both.** That is the
exact reader-with-no-producer shape 0180 names in its own FINDING 1 and in
CLAUDE.md's standing warning, sitting in the chain 0180 cited to prove the
mechanism runs. **"It has a production caller" and "that caller is working" are
two claims, and only the first was measured.**

Whether it is failing right now is **UNKNOWN and not answerable here**: it
would need `work/watch-events/bison-<id>.jsonl` and `work/heartbeat/`, which
are production `work/` state this brief forbids me to read.

---

## 6. SMALLER CORRECTIONS

1. **The canary page count is 3, not 4.** 0180 wrote *"23 leads, ~1.9 rows/lead
   ≈ 46 rows ≈ 4 pages"*. The ratio derives from the same file: 2,888 rows /
   1,516 leads = **1.905**. 23 × 1.905 = **43.8 rows → 3 pages** at
   `PAGE_SIZE = 15`. 0180 rounded the ratio up to 1.9→46 and crossed the
   45-row page boundary. Honest statement: **3 pages, 4 if the cohort's
   sequence is longer than the estate average.** Nothing in either conclusion
   changes.
2. **0180's §4 command list is two commits stale.** It was written at
   `045babe5f`; the 0170 re-dispatch (`eb56a5a5d`) then added `--sha` to
   `scripts/canary_preflight.py` and `provenance` to `src/preflight.py`. The
   step-3 command still runs, but the report it produces now carries a
   provenance line that a reader of 0180's §4 will not expect.
3. **The 918-vs-912 reconciliation is sound and I add one datum.** 0180
   reasoned the two are the same quantity 17 days apart. Consistent with
   `docs/state/QUEUE-COUNTS-2026-10-15.json`, where all ten of ours are
   `status: paused` — so no send in either figure postdates 2026-09-28, exactly
   as 0180 argued. Still not re-derivable here; still UNKNOWN as to window.

---

## 7. THE BRIEF'S §4, ANSWERED AGAINST 0180'S ANSWER

0180 recommended: **build nothing, run the dry `--confirm`.** I agree with the
"run it" half and I now rank a different single piece first.

**My pick for the one piece worth building, if anything is: refuse the
unfiltered live form.** Not 0180's pick (make an unrecognised provider status a
loud refusal), because:

- It closes a **reachable** hazard (§4) rather than converting a silence into a
  finding. Both are worth doing; only one is one flag from an operator's hand
  during the canary.
- It is smaller: a refusal when `rows is None and live` in
  `confirm_email_touches`, plus an explicit opt-in flag the backfill decision
  would later use, plus a test. Confined to `src/leadobserve.py`.
- It changes **nothing** about who may be contacted, no cap, no gate on any
  send path — it only stops an undecided 918-row write from being taken by
  accident.
- It makes the record enforce what the record already says. §2b's prohibition is
  currently prose; this makes it code.

**It is NOT built here, and deliberately so.** The brief says *propose, do not
wire*, and *no cap or gate change* — and a refusal is a gate. It is written
down, costed, and left for a brief that authorises it.

### And the honest answer stands: for 23 contacts, run the command

0180 is right that 23 can be checked against the provider, and right that the
instrument exists and is dry by default. Its four-step command list is
correct as written (with correction 6.2). **One line to add to step 1**, from
§4 above: run it **without** `--live`, read the five counts, and understand
that adding `--live` is not "the same check, but recorded" — it is the
undecided backfill.

---

## 8. OPERATOR DECISIONS — ONE NEW, AND IT IS SMALL

Carried forward unchanged: the three from 0170 §7 (which cohort of the three
numbers; the 90-day question; `internal_campaign_membership` unimplemented).
0180 added none. I add one:

**NEW — is a webhook receiver worth asking EmailBison for?** (§3.) It is the
only design in this chain that makes `delivered` real at zero provider reads
and with no change to the event vocabulary, and it would retire a dead half of
`bouncepolicy.ACCEPTANCE_EVENTS`. The decision is the operator's because it
needs a provider-side configuration and an inbound HTTP endpoint, which is a
production-surface decision and not a local reversible one.
**Recommendation: ask, but not before the canary.** A 23-contact canary does
not need delivery events, and the provider read in §7 answers the canary's
question today.

---

## 9. STILL OPEN, CARRIED FORWARD

1. **The owed full-suite reference run.** Still owed, still not run, still not
   claimed. 0180 added one docs file and no code; this run adds one docs file
   and no code. **No `src/` or `tests/` file is touched by either**, so neither
   changes what the owed reference must measure — but per CLAUDE.md the
   shortcut for non-`src`-imported files is a *measurement*, not an argument,
   and I did not make it. I ran no suite and took no suite lock.
2. **Is the bounce recorder currently failing?** UNKNOWN (§5). Needs
   `work/watch-events/` and `work/heartbeat/`, forbidden here. **This is the
   first thing to check on the main checkout** and it is one `grep` of a sink
   file.
3. **Which function in `src/providers/bison.py` returns `"delivered"`**, and
   whether the live EmailBison instance can emit webhooks at all. UNKNOWN by
   boundary (§3).
4. **The window the 918 covers.** Still UNKNOWN. `scripts/bounce_stop_7day.py
   --days 365 --json` against the live workspace still settles it in one read.

---

## 10. STATED FOR THE RECORD

- **No code was changed.** This is a docs-only audit. Nothing wired, no provider
  call, no network call, no send, no gate or cap change, no `STOP-SENDING` file,
  no campaign touched.
- Every line number here was read at `81475191a` at the moment of writing, and
  where I claim a file did not move I show the empty `git diff --stat` (§2).
- `src/providers/*` was not opened. The two lines quoted from it came from a
  repository-wide grep and the resulting limit is stated as UNKNOWN (§3).
- Production `work/` state was not read; `config/.env` was not read.
- `origin/master` is **`b1f290c84`**, unchanged.
