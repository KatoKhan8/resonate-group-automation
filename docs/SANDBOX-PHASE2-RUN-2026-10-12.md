# Phase-2 sandbox: what was run, what it proves, and what it cannot

Measured 2026-10-12 on `task-sandbox-run-2026-10-12`, forked from
`task-sandbox-phase2-horizon` at `574863579`, with
`task-sandbox-fixture-2026-10-12` (`2ebc2188`) merged in for the fixture.

**`git diff --stat 574863579 -- src/` is EMPTY.** The whole branch adds eight
files and changes none: `scripts/sandbox_run.py`, `tests/test_sandbox_run.py`,
and the six the fixture merge brought. The production flow was DRIVEN, not
changed, and `tests/test_sandbox_run.py::TheProductionFlowIsUnchanged` asserts
it against the fork-point SHA rather than against a branch name.

---

## 0. The commands

    py -3 scripts/sandbox_run.py --mode one     --out <dir>
    py -3 scripts/sandbox_run.py --mode replies --out <dir>
    py -3 scripts/sandbox_run.py --mode full    --out <dir> --seed 1 --days 60
    py -3 scripts/sandbox_run.py --mode full    --out <dir> --seed 1 --days 60 \
        --checkpoint-every 30 --kill-after-day 29
    py -3 scripts/sandbox_run.py --mode full    --out <dir> --resume

    py -3 -m unittest tests.test_sandbox_phase1 tests.test_sandbox_run -v

`--out` is refused if it resolves inside `store.protected_directories()`.
`--companies N` truncates the fixture and exists for smoke runs only.

Artefacts per run, under `<dir>/sandbox/`: `days.jsonl` (one row per simulated
day), `months.jsonl` (per simulated month), `adapter-calls.jsonl` (every fake
provider call), `checkpoint.json`, `ledger.json` (the normalised event ledger)
and `report.json`. State lives under `<dir>/state/`, which is where
`store.use_directory` points every state file.

---

## 1. The clock, exactly

| | |
| --- | --- |
| start | `2026-10-12T06:00:00+00:00` — Europe/Zagreb **08:00, UTC+2 (CEST)** |
| end | `2026-12-10T06:00:00+00:00` — Europe/Zagreb **07:00, UTC+1 (CET)** |
| interval | exactly 24 hours, 59 advances, day indices 0-59 |
| zone carried | `Europe/Zagreb`, explicitly, never the host's |

The window matches the fixture's own declared window
(`docs/sandbox/FIXTURE.md`: 2026-10-12 to 2026-12-10).

A FIXED UTC interval is the point. Europe/Zagreb leaves summer time at
**2026-10-25 03:00 local (02:00 UTC+2 → 01:00 UTC+1)**, which falls between
day 12 (2026-10-24) and day 13 (2026-10-25). Because the interval is fixed in
UTC, the LOCAL hour of every day's work moves from 08:00 to 07:00 at that
point, and the run's own log shows it:

    day 12 2026-10-24 local 08:00 +2
    day 13 2026-10-25 local 07:00 +1

`SimClock.advance` returns `dst_change:+2->+1` on that step and the report
carries `dst_crossed: true`. The control is a 20-day window starting
2026-11-02, which crosses no transition and reports none — so `dst_crossed`
has been shown able to be False.

`Europe/Zagreb` is also the zone in Productive's own `sending_window`
(`config/clients/productive.yaml`: Mon-Fri 09:00-17:00), which is what makes
the question load-bearing rather than decorative.

---

## 2. The seams, in full

Three, all additive, all inert unless called, **none in `src/`**.

| # | what | where | why it is behaviour-neutral |
| --- | --- | --- | --- |
| 1 | the provider feeds | `bison.fetch_replies`, `bison.bound_workspace`, `heyreach.conversations`, `poller.IDENTIFY["emailbison"]` — replaced at the MODULE boundary | `poller.run` documents `fetch=` and `identify=` as its test seam (`src/poller.py:197`, `:322`, `:396`). `replywatch.poll_once` does NOT forward either, so the replacement is made on the module and the REAL `poll_once` is driven — exercising the cross-process lock, the status file, the checkpoint, the workspace pin and the health counter. Every call is logged. |
| 2 | the wire and the readbacks | `sandboxharness.seal_wire(allow=())`, `seal_readbacks()` | already in `src/` from the survey commit. Called before any work, with the positive control firing in both directions. |
| 3 | the clock | `sandboxclock.install` → `store.now` only, by module attribute | the queue-lock deadlines keep ticking in real time, which is deliberate: `sandboxclock.REAL_ELAPSED_EXEMPT` names them. |

Nothing else. In particular the sandbox does **not** fake a send: a step that
`eligibility.decide` answers `eligible` on is persisted by the real
`push.mark_pushed`, which writes the step, the log line and the `PUSH_MARKED`
event and contacts no provider. That is what the live path does once a
provider has accepted a payload.

`tests/test_sandbox_run.py::TheRunnerGoesThroughTheRealModules` proves the
authorities are on the path by replacing each with a raiser and requiring the
runner to blow up — not by searching the source for their names.

---

## 3. Isolation, and the proof it can fail

`_boot` refuses, in this order, before a record is read:

1. the production `work/` files it promises not to touch must EXIST — without
   this the assertion compares `None` to `None` and could never fail
2. `store.queue_path()` must be inside the sandbox directory
3. no `CAMPAIGNS` override may have survived `store.use_directory`
4. the wire must be sealed AND a deliberate call refused
5. the readbacks must be sealed AND a deliberate call refused
6. `store.now()` must equal the simulated instant

Each has a control that breaks it and proves the refusal. Two of those
controls were themselves defective on the first pass and would have **opened a
real socket to api.emailbison.com**, because un-sealing the wire leaves the
real transport in place; both now install a returning stand-in transport, and
nothing in the test file can reach a host.

`import unittest` at the top of `scripts/sandbox_run.py` is load-bearing:
`store.under_test()` reads `sys.modules` for it and
`store.refuse_production_write` — the barrier every writer into `work/` calls —
**returns silently when it is absent.** A plain script therefore runs with that
barrier switched off. Recorded as finding 6 below.

Production `work/queue.jsonl` and `work/campaigns.jsonl` md5 + `mtime_ns` +
size are captured per run and asserted unchanged at the end
(`sandboxharness.production_fingerprint` / `assert_production_unchanged`), with
controls for a changed byte, a vanished file and an absent production
directory.

---

## 4. Zero real calls, zero credits

| measurement | result |
| --- | --- |
| wire calls attempted | the deliberate control call, plus anything the flow tried |
| wire calls **allowed** | **0** — `seal_wire(allow=())` forwards nothing |
| adapter calls | every one logged to `adapter-calls.jsonl` with its simulated instant |
| `waterfall.spend(rec)["expected"]` summed over the estate | **0** |
| credit control | a single ledger row on a COPY makes it 3, so the zero is falsifiable |

Every domain is `.invalid` (RFC 6761, never delegable) and every address ends
`.invalid`. No `example.com`. The fixture lane asserts this from the AST of its
own generator; this runner re-asserts it on load and refuses a non-synthetic
domain.

---

## 5. The six run-order items

### (i) one contact, one simulated day

`--mode one`. The flow's order is not rearranged. On day 0 **nothing is due**,
because the first step of `productive_li_heavy_v1` is cadence day 1; that is
reported as the hold it is rather than skipped. After one advance:

    verification     policy primary deliverable, required_confirmations 2
                     sendable true, confirmation_count 2,
                     confirmed_by [deliverable, reoon]
    simulator        companies 1 accepted 1, contacts 1,
                     email_eligible 1, linkedin_eligible 1,
                     multichannel 1, held 0, mx_blocked 0,
                     estimated_credits 0
    approvals        10 of 10 steps approved, 0 refusals
    day 0 eligible   []                      (held:step_not_due)
    day 1 eligible   [em1, li1]
    day 1 pushed     [em1, li1]
    day 1 held       em2-em5 held:step_not_due,
                     li2-li5 held:awaiting_dependency
    fatigue          contact ok, account ok, both asked at the simulated instant
    wire             1 attempted, 0 allowed
    credits          0
    production       unchanged, asserted

### (ii) kill after a checkpoint, resume

A real `os._exit(97)` immediately after a checkpoint write — no `finally`, no
`atexit`, no buffer flush beyond what is already on disk — in a subprocess,
because a kill cannot be tested in the process doing the asserting.

8 companies, 24 days, checkpoint every 6, killed after day 11. The removal
cohort is scheduled on days 14-19, so the suppression is written by the
RESUMED process and then has to hold:

    kill returncode              97
    checkpoint                   day 11, 1,806 ledger rows
    resume returncode            0, resumed_from 11, 12 further days
    ledger before / after        1,806 / 1,814
    lost rows                    0
    duplicated rows              0
    gained rows                  8        (the resumed half did real work)
    unsubscribed after resume    2
    removal audit                scheduled 2, ingested 2, unsubscribed 2,
                                 refused_by_eligibility 2,
                                 pushes_after_removal 0, all_prevented TRUE

A second configuration (kill after day 17) gained **0** rows, which is an
honest negative: by then every step was pushed or blocked and the resumed half
proved durability without proving the resumed half works. Both are reported;
the first is the one that answers the question.

**The named pass criterion — an opt-out prevents every subsequent contact,
including after a resume — holds, and is audited four independent ways:** the
reply was ingested; `contact["unsubscribed"]` is set; `eligibility.
must_not_contact` refuses with `blocked:unsubscribed` AND
`blocked:company_paused`; and NO `push_marked` event for that contact is dated
after the reply. The control poisons a record so that the fourth fails, and
`all_prevented` goes False.

### (iii) 300 prospects x 60 days

100 companies x 3 contacts = 300 prospects, `fixture-seed-1.json`, 60 simulated
days. See `<dir>/sandbox/report.json` and the per-month table in section 7.

### (iv) twice with the same seed

10 companies, 20 days, run twice:

    seed 1 run A   ledger 3,721   signature f9900ab0ec1884a0fca1c732d651f78f   pushed 135
    seed 1 run B   ledger 3,721   signature f9900ab0ec1884a0fca1c732d651f78f   pushed 135
    seed 2 run C   ledger 3,952   signature a9967f0bf48ce0b9caafd2fa15e8807d   pushed 143

    A == B   normalised ledger TRUE,  final state signature TRUE
    A == C   normalised ledger FALSE, final state signature FALSE   (control)

The signature is an order-independent digest of what the run DECIDED — per
contact `unsubscribed`/`stopped`/`paused`, per record `paused`/`review`/`state`,
and per step `status`/`pushed_at` — deliberately not a digest of the queue
file, because `store.save` rewrites rows and a byte digest would report a
reordered-but-identical state as changed.

### (v) positive controls

See section 8. Seven deliberate mutations of the runner were additionally run,
each asserting the file changed before and was byte-identical after, with
`__pycache__` wiped both ways. All seven went RED.

### (vi) the existing tests still pass

    tests.test_sandbox_phase1                43 tests  OK
    tests.test_sandbox_fixture               76 tests  OK
    tests.test_sandbox_run                   79 tests  OK
    tests.test_eligibility tests.test_replies tests.test_replywatch
      tests.test_poller_highwater tests.test_cadence tests.test_cadence_replies
      tests.test_cadence_safety              270 tests, 1 failure
    tests.test_approve tests.test_channels tests.test_events tests.test_push
      tests.test_quality tests.test_replaysim tests.test_simulator
      tests.test_store tests.test_verification
                                             306 tests, 2 failures

**Three pre-existing failures, none of them this branch's**, proven by
measurement rather than argued: the whole branch diff against the fork point is
eight ADDED files, none under `src/` and none imported by the failing modules.

    tests.test_replies.TestTheClassifier.test_every_verdict_carries_its_evidence
      'rules-4+ca10b3cccdcb' != 'rules-4' - the classifier version now carries
      a rule digest and the test compares against the bare constant
    tests.test_replaysim.TestTheScenarios.test_each_one_classifies_as_documented
      linkedin_reply: got positive, expected neutral
    tests.test_replaysim.TestThePositiveChain.test_the_company_is_paused_afterwards

All three are classifier-related, which is consistent with the classifier work
being unsettled on other branches. `src/replies.py`, `src/replaysim.py`,
`src/accountpolicy.py`, `src/inbound.py`, `tests/test_replies.py` and
`tests/test_replaysim.py` are all byte-identical to the fork point.

`unittest discover` and `scripts/run_suite.py` were NOT run: at most one full
suite may run on this machine at a time and other lanes are active.

---

## 6. The four mandatory reply shapes

`--mode replies`. Each case is driven through the REAL ingestion entry point —
`replywatch.poll_once` with a PROVIDER-SHAPED row — on its own simulated day,
and the three things that must not be conflated are read independently.

**CLASSIFICATION BELOW IS UNVERIFIED.** A separate lane's classifier work was
refused by adversarial review and the ingestion fix is unreviewed. Nothing in
section 5 or 7 depends on any of it: the 60-day mechanical run's only inbound
reply shape is case (d), the settled one.

| case | classification | cadence stop | permanent opt-out | human review | verdict |
| --- | --- | --- | --- | --- | --- |
| (a) "Sounds great, Thursday works. You can unsubscribe from our mailing list at any time." | `unsubscribe` | yes | **YES** | **NO** | **FAIL** |
| (b) "How do we stop spam filters blocking your invoices?" | `question` | yes | no | yes | PASS |
| (c) "No further emails needed - just send the contract." | `unknown` | yes | no | yes | PASS |
| (d) "Please remove me from your list and do not contact me again." | `unsubscribe` | yes | yes | no | PASS |

### (a) is the expensive direction, and it fires

Measured: classified `unsubscribe` at **confidence 0.95** on `matched 1
unsubscribe phrase(s)`; `accountpolicy.effects` then plans `replier: suppress,
account: continue, review: False`. `_suppress_contact` writes
`contact["unsubscribed"] = True`, which its own docstring calls permanent and
says outranks every other contact state, and **nothing in the pipeline lifts
it**. A warm yes with a date in it became a permanent opt-out, silently, with
no person asked.

The control shows it is the FOOTER and not the warmth: "Sounds great, Thursday
works." alone classifies as something else and plans no suppression.

### (b) and (c) are the shape that should happen

Both end in `replier: hold, account: hold, review: True` —
`rec["review"]["open"]` is set by `accountpolicy._require_review`. The cadence
stops and a person has to look. For (c) the classifier returns `unknown` at
confidence 0.0 and the conservative fail-safe in `inbound.handle` pauses the
account; the buying signal is MISSED rather than misread, and a human sees it.
Per the operator's rule, an ambiguous case ending in human review is a PASS.

### the real ingestion entry point, three things asserted separately

`replaysim.simulate` was deliberately not used for this: it calls
`inbound.handle` directly with an event it built itself, so on its own it
proves none of the three.

| assertion | measured |
| --- | --- |
| the watcher actually calls ingestion | TRUE — 5 `bison.fetch_replies` calls, and `bison.bound_workspace` called, so the workspace pin ran |
| a verdict is persisted for an attributable reply | TRUE — a `REPLY_CLASSIFIED` event with a `classification` and an `outcome` is on the record in `work/` for all four cases |
| an unattributed reply is retained, not dropped | PARTLY — see below |

### the unattributed reply, measured

`src/inbound.py:429` is
`if applied["status"] != "applied": return outcome`, which returns BEFORE the
classify/store step whenever a reply cannot be attributed. Driven with a
provider-shaped row carrying no `record_id`, no `contact_key` and an address
matching no contact:

    ingestion saw it                              TRUE  (events_inspected 1)
    reported unmatched                            1
    durable UNMATCHED_REPLY notification rows     1     (destination "global")
    reply event persisted on any record           FALSE
    classification persisted                      FALSE

So the **arrival** is retained and visible to a person, and the reply's **text
and verdict are not in `work/` at all.** That is finding 5 below.

---

## 7. What the 60-day run measured

Per-month rows are in `<dir>/sandbox/months.jsonl` and the per-day rows in
`days.jsonl`. The report prints state growth per simulated month (events,
queue bytes, paused records, unsubscribed contacts), counters around day and
DST boundaries, repeat contact to the same person, copy repetition for the
same person, and resume accuracy.

Three counters deserve naming because a zero in them is a claim:

* **repeat contact, same person, same day, more than one push** — a
  legitimate non-zero when two channels are due on one cadence day, which
  `cadence.channel_conflicts` is the authority on.
* **repeat contact, same person, SAME STEP twice** — must be 0.
  `eligibility._already_pushed` and `push.already_pushed` are what keep it
  there, and the resume boundary is where it would break.
* **copy repetition, the same body twice to one person** — measured from the
  bodies actually pushed, not from the templates.

---

## 8. Positive controls, and what each detected

Every control below was RUN and is in `tests/test_sandbox_run.py`.

| control | what it detected |
| --- | --- |
| `seal_wire` with an allowed host + stubbed forward | `assert_wire_sealed` raises AssertionError instead of returning True — the seal's control can fail |
| `seal_wire` stubbed to a no-op | `_boot` refuses with "wire is NOT sealed" |
| `seal_readbacks` stubbed + `bison.campaign` stubbed benign | `_boot` refuses with "readbacks are NOT sealed" |
| `store.use_directory` stubbed to a no-op | `_boot` refuses: queue_path is not inside the sandbox |
| `use_directory` wrapped to restore `CAMPAIGNS` | `_boot` refuses: a surviving override would point campaign state at production |
| `sandboxclock.install` stubbed to a no-op | `_boot` refuses: the clock was not injected |
| `production_root` pointed at an empty directory | `_boot` refuses: the assertion would compare None to None |
| `bison.campaign` raising inside `_boot` | `_boot` left the INJECTED CLOCK installed. Fixed; a test now asserts the unwind |
| one byte appended to a fake production file | `assert_production_unchanged` raises `ProductionTouched` |
| a fake production file removed | same, "vanished" |
| one verification confirmation only | `is_sendable` False — `required_confirmations: 2` is real |
| verification evidence for a DIFFERENT address | `is_sendable` False — evidence is address-bound |
| `sendable: true` with no evidence | `is_sendable` False — the stored flag does nothing |
| a 20-day window starting 2026-11-02 | no `dst_change` crossing — `dst_crossed` can be False |
| install then undo the clock in one test | `store.now` moves both ways. The earlier one-sided version PASSED while a leaked clock was installed, because that clock's instant was the run's start date, which is also today |
| `evidence.recheck` at the run's END vs with no `today` | the answers differ by exactly the distance travelled. Anchored at the run's START it did NOT differ, because the start is today — this repository's "both sides of midnight" lesson |
| the clock scanner over all of `src/` | 36 entries, so the 0 for `SIMULATED_PATH_MODULES` is a measurement and not a broken scanner |
| a `contactout` confirmation added to a contact | the timeline/send-gate disagreement vanishes, identifying the POLICY as the cause rather than the address |
| the fixture with no installed copy | the timeline is `li1..li5` only — the email steps are ABSENT, so the fixture verbatim measures a LinkedIn-only estate |
| a real domain written into a COPY of the fixture | `load_fixture` refuses |
| a missing fixture path | `load_fixture` refuses rather than generating prospects |
| a spend row on a COPY of a record | `waterfall.spend` reports 3, so the 0 is falsifiable |
| `bound_workspace` answering id 99 against a pin of 10 | `poll_once` records unhealthy with `WrongWorkspace` — the real pin refuses |
| a dropped ledger row | `compare_ledgers` reports `no_lost_state` False |
| a duplicated ledger row | `compare_ledgers` reports `no_duplicated_events` False |
| a record whose state moved | the signature moves; and reversing the record order does NOT move it |
| `_axes` with an empty before-set | no stop is claimed — a vacuous pass is refused |
| a record pushed AFTER its removal reply | `removal_audit.all_prevented` False |
| a different seed | the two-run comparison fails, so equality is falsifiable |
| `rung3_economic_buyer` on em3 | 105 words against a ceiling of 90 — the word-contract test goes red |
| the hook no longer filled | every email step blocks `cold_no_hook` and the test goes red |
| `_boot`'s store check disabled | the refusal test goes red |
| `_boot`'s CAMPAIGNS check disabled | the refusal test goes red |
| `compare_ledgers` duplicate count hardcoded to 0 | the duplicate control goes red |
| the signature ignoring `unsubscribed` | the signature control goes red |

---

## 9. The defect list, with file and line

### 1. `cadence.status_for` asks the DEFAULT verification policy — `src/cadence.py:1354`

    if spec["channel"] == "email" and not lint.sendable(contact):
        return "blocked"

`lint.sendable` with **no policy** answers under
`verification.DEFAULT_POLICY`, where `primary` is `contactout`. Productive
moved primary to `deliverable` and dropped ContactOut from verification.
`eligibility._email_checks`, `approve.why_not`, `push` and `campaigns` all pass
`verification.policy_for(config)`, and the comments in the first two document
this exact defect as found and fixed one layer along —
`cadence.status_for` is the caller that still asks the default.

Measured, by calling both:

    lint.sendable(contact)                      -> False
    lint.sendable(contact, policy_for_record)   -> True
    DEFAULT_POLICY primary                      -> contactout
    client policy primary                       -> deliverable

**Consequence:** every email step on a Productive record reports
`status: "blocked"` in the timeline a reviewer reads and the approval graph
walks, while `eligibility.decide` answers `eligible` on the same step at the
same instant. Two answers to one question, and the one a person sees is the
wrong one. Control: adding a `contactout` confirmation makes both agree.

### 2. `quality.assess` re-ages evidence against the REAL wall clock — `src/quality.py:350` → `:216` → `src/evidence.py:106`

`assess` calls `_selected(rec, contact)` with no `today`, which reaches
`evidence.recheck(item, None)` and `datetime.date.today()`. **`assess` has no
`today` or `at` parameter at all**, so a caller cannot inject one —
`_selected` does, one layer down, which is what makes this a missing
parameter on the public function rather than a missing seam.

Measured, not grepped: `recheck` called twice on the same stored item returns
`age_days` differing by exactly the distance the simulation has travelled. In a
60-day run every personalisation band is computed against the wrong date.

### 3. `simulator.timeline_for` walks `cadence.STEPS` instead of the record's sequence — `src/simulator.py:63`

    for spec in cadence.STEPS:

`cadence.build` builds the client's sequence — for Productive,
`cadencelibrary.named("productive_li_heavy_v1")`, ten steps keyed
`li1,em1,...,li5,em5`. The preview then looks up `day1..day21` in it and finds
nothing, so **every row reads "this step is not part of the configured cadence
for this contact"** and the preview shows none of the ten real steps. Measured
in `--mode one`: `simulator_timeline_matches_cadence: false`, 7 rows, 7
`not_planned`.

### 4. `rec["cadence_steps"]` is inert on a RECORD — `src/cadence.py:132`

    steps = (campaign or {}).get(CADENCE_KEY)

`CADENCE_KEY` is a **campaign** key. A record carrying `cadence_steps` changes
nothing; with no campaign the sequence falls through to
`_named_sequence(config)` and then `cadencelibrary.named(config["cadence"])`.
This corrects the phase-2 survey, which records it as a record key. The
fixture writes it in good faith and it has no effect; the test asserts both
directions — inert on a record, decisive on a campaign.

### 5. An unattributed reply's text and verdict are not retained — `src/inbound.py:429`

    if applied["status"] != "applied":
        return outcome          # duplicate, unmatched or unknown

Returns before the classify/store step. Measured above: the arrival IS retained
as a durable `UNMATCHED_REPLY` notification and the cadence to every
correspondent IS held, but no reply event and no classification are persisted
on any record. A person can see that something arrived; nobody can read what it
said from `work/`.

### 6. `store.refuse_production_write` is inert in a plain script — `src/store.py:1093`, `:1082`

    def refuse_production_write(path):
        if not under_test():
            return

    def under_test():
        return "unittest" in sys.modules

The barrier every state writer into `work/` calls is switched OFF for any
process that does not import `unittest` — which is every production entry point
by design, and also every operator script. `scripts/sandbox_run.py` imports
`unittest` for exactly this reason and asserts `store.under_test()` in its
report. A script that forgot to would run with the barrier down.

### 7. A positive reply carrying an unsubscribe footer is permanently suppressed with no review

Section 6 case (a). Classification UNVERIFIED; the POLICY consequence
(`replier: suppress`, `review: False`) is measured from
`accountpolicy.effects`, which is not classifier-dependent.

### 8. Four shipped email templates break the shipped word contract

Rendered under both of Productive's persona families and counted with
`lint.countable_words` against `lint.STEP_WORD_CONTRACT` (ceilings of 90):

    persona_pain                 97 / 102
    rung3_economic_buyer        107 / 105
    angle_shift_champion        129 / 129
    angle_shift_economic_buyer  124 / 129

`eligibility.decide` answers `blocked:lint_failed, blocked:lint:
em1_body_98_words_over_contract_60_to_90` on any step rendering one. One
consequence lands in the sandbox: the contract-satisfying set is
persona-INDEPENDENT, because the economic-buyer variant of the day-8 rung is
105 words — so em3 renders `rung3_champion` for both families rather than the
persona-matched variant, and the runner says so rather than selecting copy the
real lint would block.

### 9. The fixture's `hook` is null on all 100 cold-lane records — `src/lint.py:756`

    if lane == "cold" and not rec.get("hook"): fails.add("cold_no_hook")

Not a fixture bug — `hook` is pipeline output — but a trap: a sandbox using the
fixture verbatim has every email step blocked and measures a LinkedIn-only
estate. `install_phase5_copy` fills it from the record's own company-level
evidence fact, and a control proves the blocked state is what you get without
it.

### 10. Nine of ten cadence steps need the writer's words to exist at all — `src/cadence.py:908`

`expand_step` returns `None` for a `generated` spec whose slot holds no `body`
(email) or `note` (linkedin), and `build` drops it unless the spec carries
`requires`. With the fixture as it ships the timeline is `li1..li5` and
`approve.why_not` says `empty note` for li2-li5.

**This is the one place the runner had to supply something the flow would
normally generate**, and the honest statement is that it is fixture data in the
same sense the synthetic verification evidence is: it stands in for an output
that needs a model, and the wire is sealed. It invents nothing — every sentence
is a shipped `cadence.TEMPLATES` entry rendered by `cadence.render` from
`cadence.template_vars`, plus `optout.append_opt_out`, written into
`rec["cadence"][contact_key][step_key]`, the exact slot the phase-5 writer
writes. Zero model calls.

### 11. `sandboxclock.SIMULATED_PATH_MODULES` is incomplete

`unpatched_business_clock_reads(only=SIMULATED_PATH_MODULES)` returns **0**.
The same scanner over all of `src/` returns **36**, which is the control. The
intersection with the modules this process actually imported, minus the named
set, is non-empty and includes `src/evidence.py:106` — which defect 2 proves is
not merely imported but executed on the simulated path. The named set is a
hand-kept list and this is what a hand-kept list does.

---

## 10. What this simulation CANNOT prove

Stated plainly, because a sandbox that is believed beyond its reach is worse
than none.

**Nothing about a real mailbox.** Whether a message is delivered, lands in a
spam folder, is greylisted, is rate-limited by the receiving gateway, trips a
reputation filter, or renders correctly in Outlook. Every address is `.invalid`
and nothing was sent. The verification verdicts are synthetic evidence supplied
in the shape a provider's answer takes; no provider ever looked at an address.
MX is `null` on every fixture contact, and `mx.allows_email` reads that as
"no MX check has been run for this contact" and **permits** the email path — so
the run proves nothing about gateway policy either.

**Nothing about real provider behaviour.** The fake feed is descending by
timestamp, pages by cursor and raises `ProviderError` on schedule, because that
is what `poller.poll_emailbison`'s own docstring records about the live feed.
It cannot prove EmailBison's actual pagination, its actual ordering, whether
its cursor still bounds pages to older rows, what its rate limits are, how it
behaves under partial failure, or that `custom_variables` survives a real
round trip. HeyReach's inbox ordering is UNDOCUMENTED and the fake assumes the
one measurement the repository has. A webhook shape was not exercised at all.
Nothing about provider-side scheduling: `docs/THE-SEND-DATE-IS-THE-MAILBOX`
says the day a cohort goes out is a property of the mailbox, and the sandbox
has no mailboxes.

**Nothing about the classifier.** Section 6's classifications are UNVERIFIED by
construction. What section 6 DOES establish is the policy consequence of a
classification once made, and the shape of the three axes — which is
independent of whether the classification itself is right.

**Nothing about real elapsed time.** `sandboxclock` deliberately does not fake
`time.monotonic` or `time.time`, so the queue-lock deadline, lock staleness and
the suite lock run in real time. A deadlock that only appears under a slow
provider, a lock held across a real minute, or a race between two real
processes is outside this run. One such race IS exercised for real: every poll
takes the cross-process advisory lock through `replywatch.poll_once`.

**Nothing about scale beyond 100 companies.** `cadence.build` is quadratic in
batch size without a caller-side `paused_set` (its own docstring: 25 million
checks at 5,000 domains), and this run passes one. 100 companies is not
evidence about 5,000.

**Nothing about a human.** Approvals are taken by a synthetic approver through
the real `approve.approve_step`, so the fingerprint, the sender fingerprint and
the staleness rules are exercised — but no person read a draft, and
`docs/MANUAL-REVIEW.md` is the list of things no assertion reaches.

**Nothing about the Slack path.** Notifications are PLANNED and written to the
sandbox's own `notifications.jsonl`; nothing was posted, and the wire would
have refused it.

**And one thing it cannot prove about itself:** that the copy
`install_phase5_copy` writes resembles what the real writer would produce. It
is the repository's own templates rendered by the repository's own renderer,
which makes the lint, the duplicate detector and the approval fingerprint real
measurements of THAT copy. It is not a measurement of generated copy.
