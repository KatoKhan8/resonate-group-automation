# TASK-1004 - a positive reply reaches a human

**WRITTEN AFTER THE CODE, AND SAYING SO.** Every command below was executed
before it was written down, on branch
`task-1004-positive-replies-reach-a-human` off master `7e8eee41`, in the
worktree
`.../0d28ed9d-f87b-4840-9b68-ad4a06088bec/scratchpad/wt-laneP0`. Nothing here
is a plan; it is a record of what was measured, in the order it was measured.

The worktree name carries no provider token, because A44's path-substring
allowlist switches a send guard off when one appears in the path and that fix
is not on master.

## WHY THIS BLOCKED PHASE 0

Three independent faults, each of which ends with a human not being told
something they were the only possible actor on. Without all three, a positive
reply on the canary would be classified, would pause the account correctly,
and would reach nobody.

---

## 1. `question`, `meeting_intent` and `interested` reached no human

### Before, measured

`src/accountpolicy.py` mapped all three to `UNKNOWN`:

    interested       class=interested     outcome=unknown   replier=hold account=hold review=True
    meeting_intent   class=meeting_intent outcome=unknown   replier=hold account=hold review=True
    question         class=question       outcome=unknown   replier=hold account=hold review=True

The state movement was right - the account held, a review was opened - and
nothing else happened at all. `inbound.handle` notifies on
`replies.is_positive(verdict)` and `replies.apply` announces on the same
predicate, so the only reply that ever raised anything was `POSITIVE`.
Driven through the real `inbound.handle`, `notify.load()` came back empty for
all three and `accountpolicy.classify_outcome` read back `unknown` - which is
this module's own word for "we could not read this", about three replies it
had read perfectly well.

That mapping was deliberate (TASK-074) and the reason it gave is still
correct: a finer class must not widen what automation may do. What it also
did, and nobody intended, was make the reply unreportable and unroutable.

### After

A new canonical outcome, `accountpolicy.NEEDS_A_PERSON`, with a new policy
`reply.on_needs_a_person` whose default is `REVIEW` at `ACCOUNT` scope -
which is byte-for-byte what `UNKNOWN` already resolved to through `resolve`'s
no-policy branch. **The permission did not change. The reachability did.**

`src/replies.apply` raises `notify.REPLY_NEEDS_A_PERSON` for that outcome,
after `accountpolicy.apply_reply` has already moved the state, in the same
position and for the same reason as the positive-reply announcement:
`notify.notify` cannot raise into a caller, so a notification failure cannot
unwind a pause. The event routes `(GLOBAL, ACTION_REQUIRED)` - the operator's
own feed, not a client's channel - and the payload carries `reply_text`, the
prospect's extracted words, bounded at 4000 characters rather than excerpted,
because the person reading it has to answer it.

`inbound.handle` surfaces it on its return value. Without that line the row
existed in the notification log and in nothing the poller reports from.

`objection` and `send_info` deliberately stay on `UNKNOWN`. "Too expensive"
is a stated barrier rather than a question aimed at us, and "send me the deck"
is a request the reply engine already routes. A gate that notifies on
everything is as useless as one that notifies on nothing.

### Which path was measured for the 15-minute claim

**The live `inbound` path, and it is synchronous.** Three answers exist for
this question and this is the one measured; each link was executed, not read,
because a previous measurement on this machine proved 15 minutes for a module
the script never called.

    replywatch.Watcher._tick                every REPLY_POLL_SECONDS
      -> replywatch.poll_once               MEASURED: calls poller.run
      -> poller.run(live=True)              MEASURED: calls inbound.ingest
      -> inbound.ingest -> inbound.handle   MEASURED: adapter -> handle
      -> replies.apply -> notify.plan       INSIDE the call

* `test_the_watcher_tick_reaches_the_poller` patches `poller.run` with a
  recorder and calls `replywatch.poll_once("emailbison", env={"BISON_KEY": ...})`.
  The recorder fires once. The provider is never reached.
* `test_the_poller_reaches_inbound_handle` patches `poller.POLLERS` with a
  fake page in **EmailBison's own payload shape** - so
  `adapters.from_emailbison` really runs - patches `identity_of`, wraps
  `inbound.handle`, and calls `poller.run("emailbison", live=True)`. The wrapper
  sees exactly one event.
* `test_the_notification_exists_when_the_call_returns` measures the wall clock
  across `inbound.handle` and asserts the notification row exists when the call
  returns.
* `test_the_poller_cycle_is_inside_fifteen_minutes` asserts
  `replywatch.settings({})["interval"] <= 900`; `DEFAULT_INTERVAL` is 300.

So the end-to-end latency is **the poller's cycle plus the handling**, with no
timer, queue or deferred job in between: bounded at 300s by default and
configurable up to the 900s limit the test pins. **Not** the sweep and **not**
a push script - neither was measured and neither is claimed.

---

## 2. `channels.email_verdict` returned ALLOWED for a STOPPED contact

### Before, measured

A contact stopped by a NEGATIVE reply through the real `inbound.handle` path:

    eligibility.must_not_contact(...)[4]  ->  'blocked:contact_stopped'
    channels.email_verdict(...)           ->  (True, None)
    channels.evaluate(...)["mode"]        ->  'multichannel'

Two authorities, one person, one process, opposite answers. `channels` never
read `contact["stopped"]` at all. That mattered because `eligibility.decide`
is not the only caller: `channels.apply_to_record`, `summarise`, `evaluate`,
`allows` and `of` are what the preview, the channel report and the campaign
segmenter read, and every one of them showed somebody who had answered and
been stopped as fully reachable.

`linkedin_verdict` had the same gap.

### After

`channels.STOPPED = "contact_stopped"`, in `REASONS` and in `HUMAN`, asked by
**both** verdicts from the one field - `contact["stopped"]`, the same field
`eligibility._replied` reads, through one reader (`_stopped`) rather than a
second derivation. A stop is a fact about the person, not about a channel, so
a stop recorded from an email reply closes LinkedIn too. That is the whole of
"cross-channel".

It is asked before the address and verification checks, on the same reasoning
the MX comment already gives: the honest reason for refusing somebody who has
answered is that they answered, not that their address was never re-verified.

Not a flavour of `UNSUBSCRIBED`: a stop ends a sequence and an operator can
reopen it, an unsubscribe cannot be reopened, and one code for both loses
which is which.

---

## 3. A referral became BLOCKED FOREVER

### Before, measured

    "I am not the right person for this - please talk to Sarah Novak,
     sarah.novak@acme.test, she owns delivery operations."

    classification = not_relevant (0.80)   REFERRAL ranks BELOW NOT_RELEVANT in RULES
    outcome        = not_icp
    policy         = reply.on_negative (CONTINUE, CONTACT)
    replier        = STOP   ->  contact["stopped"]
    eligibility    = blocked:contact_stopped   = BLOCKED FOREVER, CLAUDE.md rule 2

And the plain form, `"Please talk to Sarah Novak, sarah.novak@acme.test"`,
classified `referral` and reached `reply.on_referral`, whose default was also
`STOP`. **Both** roads ended with the referrer permanently blocked.

The name was not lost - `replies.apply` has recorded `REFERRAL_MENTIONED` on
the evidence since TASK-066, and it carries the names, addresses and profiles.
Nothing alerted on it. This repository's own recurring defect: a thing
computed correctly that nothing downstream reads. The 899-reply corpus holds
15 of these and the LinkedIn corpus more.

### After

Two changes, and the mutation tests below show they are independently
load-bearing.

**`reply.on_referral` default is `HOLD`**, per the operator: *"referral =
HOLD, with a notification carrying the name of the person referred to."* The
referrer's own cadence still ends - `_TRANSITION` never lets a replier
CONTINUE - but it ends as `blocked:contact_paused`, which an operator lifts,
rather than `blocked:contact_stopped`, which nothing does.

**A recorded referral mention re-reads the policy outcome, for exactly one
category.** `replies.HANDED_ON = (NOT_RELEVANT,)`. `referral.read` is pure, so
it is now asked *before* the `REPLY_CLASSIFIED` event is written - the event
records the corrected outcome, so `classify_outcome` and every consumer see
`referral` rather than `not_icp`. Event ordering is unchanged; the same answer
is reused by the recorder below it, so the reading cannot be made twice and
differ.

Everything else is deliberately absent and the module says why:

| category | why it is not in `HANDED_ON` |
| --- | --- |
| `negative` | "Not interested - talk to Sarah" is a refusal that names somebody. It stays a refusal. |
| `unsubscribe`, `account_do_not_contact` | excluded one level up, where the referral is not read at all. A queue item naming a colleague inside a company-wide removal is the worst thing this could emit. |
| `not_now` | a date, not a hand-off. The deferral is the fact. |
| `referral` | needs no re-reading; it already resolves to `REFERRAL`. |

Fail-closed by construction: an unlisted category keeps the reading it had, so
a new class cannot accidentally soften a stop.

`notify.REFERRAL_RECEIVED` carries `referred_to` (the names), the addresses
and profiles, `referral.read`'s own resolution label, and the reply text. The
identifiers travel rather than a count of them, for the reason the
`REFERRAL_MENTIONED` event already gives: without the address the decision is
unmakeable.

---

## THE ACCEPTANCE COMMANDS

    cd <worktree>
    find . -name __pycache__ -type d -not -path "./.git/*" -exec rm -rf {} +
    py -3 -m unittest tests.test_a_positive_reply_reaches_a_human
    #  Ran 31 tests ... OK

`scripts/run_suite.py` was NOT run. One full suite runs on this machine at a
time and the main session holds the lock for the merge queue.

### The controls, and why they are the point

A gate that notifies on everything is as useless as one that notifies on
nothing, so every part carries a negative that a blanket fix would break:

* `test_an_ordinary_negative_reply_raises_no_operator_notification` - a
  decline raises **nothing** on the operator's feed.
* `test_an_out_of_office_raises_no_operator_notification`.
* `test_a_negative_reply_still_stops_the_person_who_sent_it`.
* `test_a_clean_contact_is_allowed_before_anything_stops_them` - the positive
  control for part 2. Without it a blanket `return False, STOPPED` passes.
* `test_a_colleague_who_never_replied_is_still_allowed` - a stop on one
  person is not a stop on the account.
* `test_a_not_relevant_reply_naming_nobody_still_stops` - the referral
  re-reading only fires when somebody was actually named.
* `test_a_decline_naming_a_colleague_is_still_a_decline`.
* `test_a_removal_request_naming_a_colleague_still_suppresses` - the single
  worst thing this change could have produced.

### Nothing was sent and nothing was written to a provider

`notify.plan` stores a row and posts nothing. Delivery is asserted through a
**recording transport**: `providers.slack.post` is patched with a recorder and
`notify.deliver` is called, so the assertion is on the bytes the transport was
handed. No `SLACK_LIVE`, no provider write, no Slack post.

The fixture pins `NOTIFICATIONS` and `OPERATOR_EXCLUDED`'s register path
explicitly. `operatorexclusion.path()` does **not** move with
`store.use_directory`, and `channels._operator_excluded` asks it on every
verdict, so an unpinned run would read the real register - the setUp asserts
both pins took before any test runs.

---

## THE MUTATIONS

Each was applied by a script that **asserts the substitution happened** (a
heredoc that no-ops while the suite reports OK has cost this repository a day),
`__pycache__` was wiped before every run so an equal-length mutation could not
serve a stale `.pyc`, and the restore was verified with `git status`.

| # | mutation | reddened | reason, and that no other guard fired first |
| --- | --- | --- | --- |
| 1 | `CLASSIFIER_OUTCOME`: all three back to `UNKNOWN` | 8 FAIL + 4 ERROR | `test_none_of_the_three_reads_back_as_unknown` x3 with `'unknown' == 'unknown'`; `test_each_of_the_three_raises_an_operator_notification` x3 with `0 != 1`; `test_the_notification_exists_when_the_call_returns` with `0 != 1`. Every control stayed GREEN. |
| 2 | `channels.email_verdict` stops asking `_stopped` | 3 FAIL | `test_email_verdict_blocks_a_stopped_contact` - *"said ALLOWED for somebody who has been stopped"*; `test_channels_and_eligibility_agree`; mode became `email_only`, **not** `multichannel`, which proves only the email check was removed and that `linkedin_verdict` is a separate guard rather than the one that was firing. The positive control stayed GREEN. |
| 3a | `reply.on_referral` default back to `STOP` | 4 FAIL | both referral phrasings `'stop' != 'hold'`, plus `blocked:contact_stopped` back in `must_not_contact`. |
| 3b | `HANDED_ON = ()` | 2 FAIL | **only** the `not_relevant` phrasing; the plain `referral` phrasing stayed GREEN. The two halves of part 3 are independently load-bearing. |
| 4 | `inbound.handle` stops surfacing the notification | 3 FAIL | `None != '<id>'` - *"inbound.handle did not return the notification it raised"*. The notification row still existed; only the consumer link broke, which is the exact shape of defect this repository keeps finding. |
| 5 | `referral_received` drops `referred_to` | 2 FAIL | `'Sarah Novak' not found in ''`. The notification still fired; it just said nothing useful. |

Mutation 1 was restored from a file copy after `git checkout --` over
uncommitted work destroyed the lane's edits once. Everything after it was
committed first, so `git checkout --` was the safe restore.

---

## THE REGRESSION DIFF

Per-module failing-**NAME-SET** diff against
`resonate-ops/logs/reference-228-master-7e8eee41.log`, the reference measured
on this branch's own base commit. Names are extracted with
`run_suite._parse_failures` and `suite_baseline.strip_prefix`, **never** by
grepping, by `scratchpad/namediff.py`.

**Positive control**: the reader must find `test_e2e`'s known failures in the
reference. It reports `control test_e2e: 11 names`, which is the count
CLAUDE.md records for that module, so a diff reading "clean" is reading
something.

Candidate modules were chosen by the **symbols that moved** rather than by the
files that moved - `CLASSIFIER_OUTCOME`, `OUTCOME_POLICY`, `POLICIES`,
`on_referral`, `apply_reply`, `classify_outcome`, `contact_state`,
`email_verdict`, `linkedin_verdict`, `channels.evaluate/allows/of/summarise`,
`replies.apply`, `inbound.handle/ingest`, `notify.plan/ROUTES/EVENT_TYPES`,
`referral.read`, and the state consumers `tagsync`, `stoppedcause`, `hygiene`,
`signals`, `priority`, `reengagement`, `oooreturn`, `learning`,
`cadenceexposure`, `eligibility`, `leadstop`, `nextaction`, `cadence` - which
is 408 of the 700 test modules.

**RESULT: see the lane report.** 64 of the 408 bind loopback and were run
separately, because a concurrent suite makes a port collision
indistinguishable from a real failure.

**THIS IS NOT A MERGE GATE.** The operator's rule is explicit and has no
exception for `src/` or `tests/`: a change under either **always** gets a new
full-suite reference. This diff is the regression tool available while the
lock is held, and the branch still needs its own full run plus a GLM verdict
before it may land.

---

## WHAT WAS DECLINED, AND WHY

* **`scripts/run_suite.py` was not run.** The main session owns the machine
  lock for the merge queue.
* **Nothing was merged or pushed to master.** The work is on
  `task-1004-positive-replies-reach-a-human` only.
* **No provider write and no Slack post.** Every notification is planned;
  delivery is asserted through a recording transport.
* **`objection` and `send_info` were left on `UNKNOWN`.** The brief named
  three categories. Promoting a fourth is a separate decision with its own
  evidence, and widening the alert is the one change that would make the
  operator's feed unreadable.
* **`RULES` was not reordered.** Making `REFERRAL` outrank `NOT_RELEVANT`
  would have fixed part 3 at the classifier, and it would also have moved
  every `not_relevant` reply in the corpus whose text happens to carry a
  hand-off cue. `NOT_RELEVANT`'s measured precision is a thing this repository
  paid for. The policy layer was the smaller change and it is the layer the
  operator's rule is about.
* **`WRONG_PERSON`, `LEFT_COMPANY` and `EXISTING_CLIENT` were left alone.**
  They carry no classifier word and are written straight onto the event by
  `revival` and by a person in the UI; nothing measured says they are
  unreachable.
