# Merge request — the store and the provider must agree about who replied

Branch `reply-reconciliation-2026-09-24`, off master `5b1b2db3`. One commit.
**Not merged, not pushed.** No provider write was exercised, no event was
written into `work/`, and the live numbers below are all from a read-only
run.

Three files, all mine, staged by name:

    src/replyreconcile.py                                        new
    tests/test_a_replier_the_provider_still_calls_in_sequence.py new
    scripts/bison_watch_loop.py                                  +94 -5

`src/providers/apify.py` and `src/researchpack/` were being edited in this
same checkout by another agent while this was written. Neither was touched
and neither was staged.

---

## 1. WHAT IT IS FOR, MEASURED

Five leads carried `reply_received` AND `reply_classified` in the store —
three of them also `contact_stopped` or `company_paused` — and were still
`in_sequence` at EmailBison in campaigns 491 and 492, both ACTIVE. They were
stopped by hand. **23 of the 28 flagged records were correctly stopped**, so
this is not an ingestion failure: ISSUE-001 is fixed and the link below it
had nothing watching it.

`leadstop.sweep` can stop everybody who must not be contacted and `inbound`
stops a replier as the reply lands. Neither runs on a timer, and **neither
ever asks the provider whether it agrees.** A stop that silently did not
happen was indistinguishable from a stop that did.

---

## 2. THE READ-ONLY RUN, 2026-09-24, ALL TEN ACTIVE CAMPAIGNS

Provider statuses read live. 481, 487, 489, 491, 492, 493, 494, 496, 497,
498 are the ten ACTIVE; 495 is archived and 451/484/485 are not live.

**703 provider memberships in total: 568 `in_sequence`, 112 `stopped`,
21 `replied`, 2 `bounced`.**

| campaign | forward disagreements | of store-says-stop | reverse missing | of provider replied+bounced |
|---|---:|---:|---:|---:|
| 481 | 0 | 0 | 0 | 0 |
| 487 | 0 | 0 | 0 | 0 |
| 489 | 0 | 0 | 0 | 0 |
| **491** | **0** | 7 | **3** | 10 |
| **492** | **0** | 10 | **2** | 12 |
| 493 | 0 | 0 | 0 | 0 |
| 494 | 0 | 0 | 0 | 0 |
| 496 | 0 | 0 | 0 | 0 |
| 497 | 0 | 1 | 0 | 1 |
| 498 | 0 | 0 | 0 | 0 |
| **total** | **0** | **18** | **5** | **23** |

**FORWARD: 0 right now.** All 18 contacts the store says must hear nothing
further read a settled status at the provider. That is the expected answer
and it is a measurement of tonight's hand repair, not of the check being
weak — the five were stopped by hand hours before this ran. The check
therefore agrees with the repair, which is the strongest thing it could say
today and is not evidence it would catch a new one. The tests are what
carries that claim.

**REVERSE: 5.** Three in 491, two in 492. The provider records 21 replies
and 2 bounces across the ten; our store holds the event for 18 of those 23
and is missing 5 — two replies and a bounce in 491, a reply and a bounce in
492. **Every one of the 23 binds to a record we staged** — `unmatched` is 0,
so none of these is the client's own lead.

18 + 5 = 23 exactly, which is the arithmetic both directions have to satisfy
and is the reason to believe the two halves are looking at the same set.

Reproduce, read-only:

    py -3 -m src.replyreconcile --campaign 491 --campaign 492

---

## 3. WHAT IT DOES

`src/replyreconcile.check(campaign_id, membership=..., live=...)`.

**FORWARD.** For every contact our store says must hear nothing further —
`eligibility.must_not_contact` filtered by
`executionguard.SUPPRESSION_REASONS`, the same canonical pair `leadstop.sweep`
asks, plus a bounce that pair cannot express — assert the provider does not
still have them sendable. If it does, stop them through
`leadstop.stop_contact`, which is the existing door: it re-reads the
provider's `lead_campaign_data` for that exact lead, treats an already-stopped
membership as a success with no write, enforces tenancy, goes through
`providerwrites.perform` with `EMAIL_STOP_LEAD`, and records
`PROVIDER_STOP_CONFIRMED` where the rest of that person's history is.

**SENDABLE IS THE COMPLEMENT OF `bison.STOPPED_STATES`, not a list of its
own.** `in_sequence`, `sending_paused`, `never_contacted` and *any status
this system has never seen* all count as sendable. `sending_paused` is the
campaign's pause borrowed by the membership and reverses on one click;
`queued_for_sending` appeared in this estate on 2026-09-24. An unrecognised
status is not evidence of safety.

**REVERSE.** For every provider lead reading `replied` or `bounced` with no
corresponding event on the bound contact, write `REPLY_RECEIVED` or
`EMAIL_BOUNCED` into the store. One transaction for the whole cycle.
Idempotent on `provider_event_id`
(`emailbison:membership:<campaign>:<lead>:<status>`), so polling every five
minutes for a week appends one row.

The written event carries **no body, no address and no verdict** — a
membership status proves a reply happened and nothing else. `source` is
`provider_membership_reconcile`, so a later reader can tell it from an
ingested reply that carries words, and nothing classifies it.

**Provider `unsubscribed` is deliberately NOT written back.** The status
exists; the brief named replied and bounced; half-implementing the third
would hide the gap. It is listed in §7.

---

## 4. THE WRITE SCOPE — the part to review hardest

A watcher is a reader and holds no write scope. That is deliberate and it is
why the first blank-content halt alerted and halted nothing:
`work/provider-write-refusals.jsonl` at 2026-09-23T20:18:58Z, "no
RESONATE_PROVIDER_WRITES and no allow_writes() scope". **The guard was right
and the control was ceremony.**

`_halt_on_blank_content` fixed that with `allow_writes(only=PAUSE_ROUTES)`.
This is the same shape one verb further down:

    STOP_ROUTES = ("stop-future-emails",)

and the scope is opened **per lead**, inside `_stop_one`, around one provider
call — narrower in time than the halt's, which wraps the whole pause.

Narrow in power, and asserted so:

| route | in scope |
|---|---|
| `/campaigns/{id}/leads/stop-future-emails` | **yes** |
| `/campaigns/{id}/leads/attach-leads` | no |
| `/campaigns/{id}/resume` | no |
| `/campaigns/{id}/pause` | no |
| `/campaigns` (create) | no |
| `/campaigns/{id}/sequence-steps` | no |

Pause is out too, and not because pausing is dangerous: this function's job
is to stop ONE PERSON, and a scope that could also pause is a scope one
refactor from halting an estate.

**The tests that pin it**, in
`tests/test_a_replier_the_provider_still_calls_in_sequence.py`, class
`TheScopeIsNarrowInTimeAndInPower`:

    test_the_stop_route_is_authorised
    test_the_scope_does_not_reach_attach_leads
    test_the_scope_reaches_no_verb_that_can_send_more
    test_the_scope_is_closed_before_and_after
    test_the_scope_names_a_route_fragment_not_a_whole_url

The first three read `providers.writes_allowed(url)` **from inside the
transport**, in the one call the scope exists for — the same technique
`test_the_halt_actually_pauses_and_carries_a_write_scope` uses.

**Attacked, not merely green.** Replacing `only=STOP_ROUTES` with
`only=None` fails `test_the_scope_does_not_reach_attach_leads` ("the stop's
scope reached attach-leads") and `test_the_scope_reaches_no_verb_that_can_
send_more` ("the stop's scope reached resume"), and nothing else. Narrowing
`provider_is_sendable` to `in_sequence` alone fails
`test_sending_paused_is_still_sendable` and
`test_a_status_nobody_has_seen_counts_as_sendable`. Dropping the `live`
guard on the write-back fails `test_the_dry_run_writes_nothing`. Each failed
for its own reason and no other guard fired first.

---

## 5. WHAT IS SAID, AND WHERE

**Per cycle, counts, INFO.** `notify.STATUS_CHECKPOINT` routes
`(STATUS, INFO)` — the daily operations feed — and `notify._status_payload`
refuses a field whose name or value looks like a person, so a careless field
fails loudly rather than reaching the channel with the widest audience in the
product.

The notification id is built from the campaign, the UTC day **and the counts
themselves**. A cycle whose picture is unchanged lands on the same id and
writes nothing; a cycle whose picture moved posts a new line. Every cycle is
reported — an unchanged one by the line already there. Ten campaigns at a
300s interval would otherwise be ~2,880 identical lines a day, and a feed
nobody reads is a feed the CRITICAL is lost in.

**CRITICAL when a replier is found sendable.**
`notify.REPLY_PROTECTION_FAILED` routes `(GLOBAL, CRITICAL)`. It is the
existing verb for "somebody replied and may still receive the next step",
already raised by `replywatch` when polling dies and by `reply_watch_loop`
when a stop is refused. A new name would split one incident across two
alerts.

It is raised on **discovery** and carries `stopped_by_reconciliation:
yes|NO`, rather than being conditional on the stop failing. The
blank-content halt settled that argument: a repair that succeeds must not
swallow the finding, because the finding is that a replier was sendable at
all. A forward disagreement whose reason is a bounce or a stop raises the
INFO line and no CRITICAL.

---

## 6. THE WATCHER CHANGE

`scripts/bison_watch_loop.py`, +94 −5.

- `_membership_states(provider_id)` split into `_membership_rows(provider_id)`
  (the walk) and `_membership_states(rows)` (the count). **The walk is paid
  for once.** Two reads of one campaign in one cycle would be two readers
  that can disagree about who is in sequence — the defect
  `CAMPAIGN_QUEUE_PAGE_CAP`'s comment names about the queue, arriving on the
  membership. So the reconciliation costs **no extra provider call**.
- `snapshot()` carries `membership_rows` beside `membership`. It is compared
  for movement by nothing.
- `watchsink.beat` is given the state **without** `membership_rows`: the
  heartbeat is a picture a human reads, and `membership` already carries the
  counts.
- `_reconcile_replies(provider_id, state, emit)` runs every cycle, **before
  the first-cycle early return**, for the same reason the blank-content halt
  does: "a replier is still in sequence" is a standing fact, not a
  transition, and a watcher restarted at 21:31 must not wait an interval.
- It is wrapped. Reconciliation is not worth an outage: the log and the
  heartbeat are the record of last resort and must not depend on the store
  being loadable or the notification layer being up.
- New emitted lines: `RECONCILE-FORWARD`, `RECONCILE-STOPPED`,
  `RECONCILE-STOP-REFUSED`, `RECONCILE-REVERSE`,
  `RECONCILE-WRITEBACK-FAILED`, `RECONCILE-UNREADABLE`, `RECONCILE-FAILED`.
  Lead ids, statuses and counts; never a person.

**A MERGE IS NOT A DEPLOY.** The ~15 watcher loops import at start and never
reload, so merging this changes nothing until those processes are restarted.
The five reverse write-backs in §2 land on the first cycle after that
restart, not on the merge. Check the process start time against the file
mtime before believing the check is running.

---

## 7. WHAT IT DOES NOT DO

- **No LinkedIn.** `heyreach.stop_lead_in_campaign` is wired and
  `leadstop.stop_linkedin_contact` is its door, but its own docstring still
  says NEVER LIVE-VALIDATED. A reconciliation loop is not the place to find
  that out.
- **No provider `unsubscribed` write-back** — §3.
- **Nothing is ever un-stopped.** There is no path here that makes anybody
  more contactable: not a resume, not an enrol, not an event that clears a
  suppression.
- **An unreadable membership reconciles nothing.** It refuses and says so
  (`RECONCILE-UNREADABLE`). `{}` would have reported every replier as
  correctly stopped — a false clean on the safety path, which is the
  substitution this watcher exists to catch at the provider. Pinned by
  `test_a_refused_membership_read_reconciles_nothing`.
- **A campaign with no local row refuses** rather than guessing which
  records belong to it.

---

## 8. TESTS

`tests/test_a_replier_the_provider_still_calls_in_sequence.py` — **38 tests,
all passing**, in six classes:

| class | what it pins |
|---|---|
| `AReplierTheProviderStillHasInSequence` | forward detection, the dry run, the live stop, `sending_paused` and unknown statuses, bounce as a reason |
| `TheScopeIsNarrowInTimeAndInPower` | the write scope — §4 |
| `TheProviderKnowsSomethingTheStoreDoesNot` | reverse write-back, idempotency, no words, unmatched leads counted not invented |
| `AnUnreadableMembershipIsNotACleanOne` | refusal rather than a false clean |
| `WhatIsSaidAboutIt` | the CRITICAL, the INFO line, dedupe, nothing naming a person |
| `TheWatcherCarriesTheCheck` | the loop calls it on the roster it already read; one walk, two answers |

Every provider status in the fixtures is a word read off the live estate on
2026-09-24.

### Suite

**THERE IS NO FULL-SUITE NUMBER HERE, and that is a statement rather than an
omission.** A `unittest discover` was started and killed by its own
20-minute timeout before it reached its summary: zero `Ran N tests` lines and
zero `FAIL:` blocks in the log. The progress ticker in that log shows dots and
`F`s, and counting them would be the mistake
`MERGE-REQUEST-2026-09-24-LATENCY.md` §0a already records — unittest prints
those blocks only at the END of a run, so a live log cannot be read for a
verdict. It was not re-run: this checkout is shared with an agent editing
`src/researchpack/`, and two concurrent suites here bind the same loopback
ports and build the same demo estates, which manufactures failures for
whoever is running the other one.

So the claim rests on the targeted runs below, and a full run belongs to
whoever merges this, in a quiet checkout.

Targeted, green: `test_a_blank_email_can_never_be_sent_again`,
`test_the_queue_cap_is_one_number`,
`test_a_campaign_we_did_not_stop_is_critical`,
`test_a_watcher_that_prints_into_nothing_is_not_a_watcher`,
`test_fixture_hygiene` (17/17), `test_invariants`,
`test_one_person_can_be_stopped_without_stopping_the_rest`,
`test_the_reply_path_may_stop_and_nothing_else`,
`test_the_stop_line_says_what_happened`,
`test_a_linkedin_reply_stops_email_inside_fifteen_minutes`,
`test_the_linkedin_stop_can_actually_address_somebody`,
`test_a_reply_reaches_the_provider_not_just_the_record`,
`test_a_reply_and_its_stop_are_saved_together`,
`test_a_stop_beats_an_authorization`, `test_notify`.

**One guard caught this branch and was right.**
`test_invariants::test_only_store_names_a_state_file_in_code` failed on an
argparse help string that named `campaigns.jsonl`. Reworded, not exempted.

**Two failures in the neighbourhood are NOT this branch's:**

- `test_task235_dnc_cannot_stop_linkedin::test_enabling_it_moved_nothing_else`
  asserts `len(providerwrites.SUPPORTED) == 15` and it is 16 on master
  `5b1b2db3`. `src/providerwrites.py` is untouched here (`git diff --stat`
  empty).
- `test_nothing_writes_to_a_provider::test_every_http_write_in_the_repository_is_declared`
  names `src/researchpack/pack.py`, which the other agent is editing in this
  checkout. Not mine, not staged.
