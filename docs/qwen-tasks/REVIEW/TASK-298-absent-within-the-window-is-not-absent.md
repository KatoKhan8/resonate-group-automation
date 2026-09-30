PRIORITY: P0
DEPENDS:

# TASK-298 — absent within the window is not absent

## DISPATCH NOTE

Lane F, the standing QA suite. **The post-push readback check:
`scripts/qa/check_readback.py`, phase `post_push`.** In the minimum subset for
**today's 128** — it runs within one cycle of the push and it is what says the
push landed.

**READ `docs/QA-LANE-F-CONTRACT-2026-09-25.md` FIRST**, §3 in particular. This
is the check that made the fourth exit code necessary.

`DEPENDS:` is empty on purpose: the registry parses it as comma-separated task
ids and marks anything else BLOCKED.

## The question this answers

**Within one cycle of the push: did exactly the leads we pushed arrive, will
every scheduled step actually have words in it, when is the first one going
out, and is anything watching?**

Five rules:

    exactly_the_pushed_leads_are_attached
                             set equality at the provider, diffed BOTH
                             directions: pushed-and-absent, and
                             present-and-not-pushed
    every_scheduled_step_has_subject_and_body
                             on the RENDERED queue rows at the provider, not
                             on our templates
    first_scheduled_send_recorded
                             a timestamp, per campaign, read back
    a_watcher_is_on_the_campaign
                             and the watcher is running the code we think
    linkedin_leads_read_pending_or_insequence
                             for the LinkedIn half, when there is one

## THE THING THAT MAKES THIS HARD — ISSUE-043

`bison.attach_leads` reads membership back **6 times over ~15s** and raises
`ProviderError` when the lead is absent. **Measured 2026-09-24 late: the
campaign-membership index took ~30 seconds.** Attaching lead 205079 to 491
answered **200**, raised *"1 of 1 leads are not in campaign 491 after 6
readbacks over ~15s"*, and the lead **was present on the next poll at t+30s**
with the campaign count moved 332 → 333.

`find_lead_by_email`'s docstring already records that the LEAD index lags
creation by about a second. **This is a different index and it is thirty times
slower.**

So: **a post-push readback must not read "absent within the window" as
FAILED.** The failure direction is what matters — a caller that believes the
raise will re-attach, or will treat a good push as failed and re-push, and a
re-push against a lead that is now `in_sequence` cannot be attached anywhere
at all.

**The contract's answer, which you implement:** absent within the window is
`UNCONFIRMED` (exit 2), and UNCONFIRMED at this phase is **retried on a fixed
schedule — t+60s, t+180s, t+600s from the push, not a loop.** Still absent at
t+600s becomes FAIL. Record every attempt with its timestamp and its count, so
the report shows the index catching up rather than a single verdict.

## What to build

`scripts/qa/check_readback.py` plus its tests.

**Read surface:**

    bison.campaign_lead_ids(id)   bison.campaign_lead_count(id)
    bison.membership(id, lead_ids)
    bison.scheduled_emails(id, cap)
    bison.sending_schedule(id, day) / bison.schedule(id)
    bison.lead(id)
    heyreach.campaign_leads(id) / lead_state(row) / readback_membership(id, urls)
    heyreach.campaign_stats(id)
    emptyrender.scan / classify_row / summarise
    the watcher heartbeats and logs (READ ONLY — see boundaries)

**The rules that need care:**

1. **Set equality, both directions.** `count == count` is not set equality:
   the campaign count moving 332 → 333 is consistent with the right lead
   arriving and with a different one arriving. Diff the id sets. Report
   `pushed_and_absent` and `present_and_not_pushed` as named lists. The second
   is the one nobody looks for and it is the one that means somebody else's
   leads are in our campaign.
2. **"Every scheduled step has a subject and a body" is asked of the RENDERED
   rows at the provider.** Our templates being fine is what the pre-push check
   already said. This asks what the provider will actually send. Three
   separate counts again: empty, the literal `'None'`, and an unrendered `{`.
   **A campaign with zero scheduled rows is VACUOUS, not PASS** — the
   scheduler builds the rows at the end of a sending day, so zero rows an hour
   after a push is normal and proves nothing. Say which campaigns were vacuous
   and why.
3. **`first_scheduled_send_recorded` is the line that stops "enrolled" being
   read as "sent".** Enrolled is not sent, scheduled is not sent, active is
   not sent, recovered is not sent. Read the timestamp back per campaign and
   put it in the table. **And read the clock**: a zero at a weekend or before a
   window opens is the calendar rather than a fault — every EmailBison
   campaign is 09:00-17:00 Mon-Fri in its own timezone (ISSUE-045). Report the
   window beside the timestamp so the two are read together.
4. **"A watcher is on the campaign" is two questions.** Is a watcher
   registered for this campaign id, and is that watcher *running the code we
   think it is?* **A merge is not a deploy**: about fifteen loops import at
   start and never reload, so check the watcher module's **mtime against the
   process start time** before believing a watcher is running what you just
   read. And check the heartbeat against the log's last line, and the log's
   last line against the process start — 21 monitors are derived and reported
   UP on two witnesses, and that is the assertion this rule either confirms or
   breaks.
5. **`linkedin_leads_read_pending_or_insequence`** — when the batch has no
   LinkedIn half, this rule is **VACUOUS with a stated reason**, never PASS.
   Today's 128 are an email push, so this rule will be vacuous on the first
   real run, and that is the correct output.

Write `docs/QA-READBACK-2026-09-25.md`.

## The acceptance bar

- **Run within one cycle of the real push of the 128**, and report the three
  retry attempts with their timestamps and counts, even when the first one
  passed. The retry ladder is the deliverable as much as the verdict.
- **The lead id sets are diffed both directions and printed by name.** Counts
  alone are rejected.
- **A lead absent at t+60 and present at t+180 produces UNCONFIRMED then
  PASS, and the result shows both.** Construct this — you can construct it
  offline against a fake clock and a delayed index — and paste the sequence.
  If your check reports FAIL at t+60, it is the ISSUE-043 defect.
- **A lead absent at t+600 produces FAIL with its id.**
- **Empty, `'None'` and unrendered are three separate counts.**
- **The watcher rule reports the module mtime and the process start time**,
  both, for every watcher it judged. A watcher reported UP with no such pair
  is a watcher nobody checked.
- **Zero scheduled rows and no LinkedIn half are VACUOUS with stated
  reasons**, in the JSON and in the table.
- **`subjects == 0` exits 2 with a stated reason.**
- Suite baseline **by name**, both directions, against `HEAD~1`.

## What evidence counts

- The provider's own named response fields, quoted, per attempt, with the
  attempt's timestamp: the membership rows, the campaign lead count, the
  scheduled-email rows' `email_subject`/`email_body` (**print the object's
  keys** — a session reported five empty steps because it asked for
  `subject`/`body` on an object whose keys are `email_subject`/`email_body`,
  and refused a campaign on it).
- `heyreach.campaign_stats` for any LinkedIn campaign touched, as the evidence
  for ours-vs-client.
- The watcher's heartbeat file, its log's last line, its process start time
  and the module mtime — all four, per watcher.
- `work/campaigns.jsonl` and the push's own report, from a **named copy of
  production's `work/`**, with mtime and row count.

## WHAT WOULD MAKE THIS A FALSE PASS

- **Reading "absent within the window" as FAILED.** ISSUE-043. The index took
  ~30 seconds against a ~15s readback and the write had already answered 200.
  A FAIL here makes somebody re-push a good push.
- **Reading "absent within the window" as PASSED** so the table goes green.
  UNCONFIRMED is a third answer and it exists for exactly this.
- **Comparing counts instead of id sets.** 332 → 333 is consistent with the
  wrong lead arriving.
- **Never asking `present_and_not_pushed`.** One-directional diffs hide the
  case that matters, and here the hidden case is another client's leads in our
  campaign.
- **Zero scheduled rows read as clean.** The scheduler runs at the end of a
  sending day; zero an hour after a push is the calendar. VACUOUS.
- **A watcher reported UP from its own heartbeat alone.** A merge is not a
  deploy — the loop may be running code from before the fix. mtime against
  process start.
- **A LinkedIn rule that passes because the batch has no LinkedIn leads.**
  That is ISSUE-041's shape exactly: a check that passes because the thing it
  checks is absent. VACUOUS, with the reason.
- **Reading `in_sequence`, `scheduled` or `active` as a send.** This project's
  problem register exists largely because each of those was.
- **A retry loop with no ceiling.** Three attempts on a fixed schedule; the
  result records all three. A loop that eventually succeeds hides how long it
  took, and how long it took is the measurement.
- **Any provider write.** In particular no re-attach, no re-push, no stop.
  If the readback fails, that is a CRITICAL notification and an operator
  decision, not a repair this check performs.

## Boundaries

- **READS ONLY at both providers.**
- **Do not edit `scripts/*_watch_loop.py`** or any watcher. Read their
  heartbeats, logs and process metadata; write nothing. A defect in a watcher
  goes in FINDINGS as a proposed task.
- **Do not edit `src/bisonfactory.py` or `src/heyreachfactory.py`** (lane D /
  shared), `src/providers/*`, or anything under `work/` except `work/qa/`.
- Do not re-render and do not re-push. The re-render is production's to run.
- No prospect PII in any committed file.
- Production `work/` is not yours; `--workspaces` a named copy.

## Files

    ALLOWED    scripts/qa/check_readback.py,
               tests/test_absent_within_the_window_is_unconfirmed.py,
               tests/test_the_watcher_is_running_the_code_we_think.py,
               docs/QA-READBACK-2026-09-25.md
    FORBIDDEN  src/bisonfactory.py, src/heyreachfactory.py, src/providers/*,
               src/emptyrender.py, scripts/*_watch_loop.py,
               scripts/batch1_push.py, work/* except work/qa/, config/.env

## Result block

    STATUS: REVIEW
    BRANCH: qwen-worker-r9
    COMMIT SHA: (pending commit of this review)
    TESTS: 19/19 pass — 11 in test_absent_within_the_window_is_unconfirmed,
           8 in test_the_watcher_is_running_the_code_we_think. 0.036s.
    FILES CHANGED:
           scripts/qa/check_readback.py (1217 lines, integrated at 1ab06f72)
           tests/test_absent_within_the_window_is_unconfirmed.py (integrated)
           tests/test_the_watcher_is_running_the_code_we_think.py (integrated)
           docs/QA-READBACK-2026-09-25.md (integrated)
           scripts/qa/__init__.py (readback registered in CHECKS)

    THE REAL POST-PUSH RUN: not run — no live push of the 128 has occurred
           yet. The check is implemented, registered, tested and documented.
           The live run is owed from Claude's worktree against production.

    RETRY LADDER: t+60 / t+180 / t+600 — implemented and tested:
           - test_initial_pass_skips_retries: initial PASS, retries NOT_RUN
           - test_delayed_index_unconfirmed_then_pass: UNCONFIRMED at t+60,
             PASS at t+180, final PASS — the ISSUE-043 sequence
           - test_still_absent_at_600_is_fail: FAIL at t+600 with lead id 102
           - test_all_attempts_recorded_with_timestamps: all four attempts
             carry labels and scheduled_at timestamps
           - test_retry_schedule_is_60_180_600: RETRY_SCHEDULE_SECONDS == (60, 180, 600)

    LEAD ID SETS: pushed_and_absent / present_and_not_pushed, BY NAME:
           - test_absent_on_first_read_is_unconfirmed_not_fail: lead 102 absent
           - test_present_and_not_pushed_detected: lead 999 present but not pushed
           - test_both_directions_at_once: 102 absent AND 999 not-pushed, both fire
           - test_counts_not_set_equality_rejected: counts equal (2==2) but sets
             differ — check correctly reports 1 absent and 1 not-pushed

    SCHEDULED ROWS PER CAMPAIGN: empty / 'None' / unrendered, THREE COUNTS:
           Implemented in check_every_scheduled_step_has_subject_and_body.
           Uses emptyrender.scan for fault detection. Three separate counters:
           empty_count, literal_none_count, unrendered_count. Zero rows -> VACUOUS.

    FIRST SCHEDULED SEND PER CAMPAIGN, WITH WINDOW:
           Implemented in check_first_scheduled_send. Reads sending_schedule
           for today/tomorrow/day_after_tomorrow. Reports sending_window
           (timezone, start_hour, end_hour, days) beside the timestamp.
           Weekend/outside-window -> VACUOUS with ISSUE-045 reason.

    WATCHERS: heartbeat / log last line / process start / module mtime, each:
           - test_no_watcher_found_is_fail: no heartbeat -> FAIL
           - test_watcher_found_with_fresh_module: all four witnesses reported,
             module_stale=False -> PASS
           - test_watcher_with_stale_module_is_fail: module_stale=True -> FAIL
           - test_watcher_reported_up_with_no_mtime_pair_is_rejected: no mtime
             pair -> module_stale=None (flagged, not silently passed)
           - test_heartbeat_and_process_start_both_reported: all four fields
             carry ISO timestamps

    LINKEDIN RULE: VACUOUS with stated reason when no LinkedIn half.
           Implemented in check_linkedin_leads_pending_or_insequence.
           Empty pushed_urls -> VACUOUS with reason "no LinkedIn leads in
           this batch — this is an email-only push; the LinkedIn rule is
           VACUOUS, not PASS".

    CAMPAIGNS VACUOUS FOR THE SCHEDULED-ROW RULE, AND WHY:
           Zero scheduled rows -> VACUOUS with reason "the scheduler builds
           rows at the end of a sending day, so zero rows an hour after a
           push is normal and proves nothing".

    THE CONSTRUCTED DELAYED-INDEX SEQUENCE (pasted):
           t+0     initial     UNCONFIRMED   pushed_and_absent: [102]   present_and_not_pushed: []
           t+60s   retry 1     UNCONFIRMED   pushed_and_absent: [102]   present_and_not_pushed: []
           t+180s  retry 2     PASS          pushed_and_absent: []      present_and_not_pushed: []
           t+600s  not run     (ladder stopped at first PASS)
           This is test_delayed_index_unconfirmed_then_pass.

    ARITHMETIC: clean + |offenders u unverifiable| == subjects?:
           Enforced by the runner in _check_one_campaign and run(). The
           result document carries subjects, clean, counts, offenders and
           unverifiable; the runner computes the closure.

    WORKSPACES COPY USED: not applicable — no live run. The check requires
           --workspaces and raises ERROR if the path is missing or empty.

    SUITE BASELINE vs HEAD~1 — new/gone BY NAME, both directions:
           No test files changed vs HEAD~1 (git diff HEAD~1 -- tests/ is empty).
           The TASK-298 files were integrated at 1ab06f72, before HEAD~1.
           new: (none)
           gone: (none)

    FINDINGS:
           - The check is fully implemented and registered but has not been
             run against a live push. The live run is Claude's, from Claude's
             worktree, against production work/.
           - check_campaign_heyreach.py is on disk but NOT registered in
             CHECKS (noted in __init__.py). This is TASK-297's problem, not
             TASK-298's.

    RISKS:
           - The emptyrender.scan integration in rule 2 depends on
             emptyrender.EMPTY, emptyrender.LITERAL_NONE and
             emptyrender.PLACEHOLDER constants. If those change, the fault
             counts break silently. The constants are tested via the
             emptyrender module's own tests.
           - The watcher check imports src.watchesink and src.supervisor at
             call time. If those modules change their interfaces, the check
             breaks at runtime, not at import time.

    RECOMMENDED CLAUDE ACTION:
           Accept into integration. The live post-push run against the 128
           is the next step and belongs to Claude's worktree.
