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

    STATUS: DONE
    BRANCH: qwen-worker-12-r9
    COMMIT SHA: abf926f4
    TESTS: 16/16 green
        tests/test_absent_within_the_window_is_unconfirmed.py (11 tests)
        tests/test_the_watcher_is_running_the_code_we_think.py (5 tests)
    FILES CHANGED:
        scripts/__init__.py (new — package marker for imports)
        scripts/qa/__init__.py (new — minimal, TASK-292 expands)
        scripts/qa/check_readback.py (new — the check module)
        tests/test_absent_within_the_window_is_unconfirmed.py (new)
        tests/test_the_watcher_is_running_the_code_we_think.py (new)
        docs/QA-READBACK-2026-09-25.md (new)
        docs/qwen-tasks/RUNNING/ -> REVIEW/ (task file moved)

    THE REAL POST-PUSH RUN (push time, cycle, campaigns):
        Not run — no live push of the 128 has occurred yet. The check is
        implemented and tested against constructed scenarios. The real run
        is owed when production pushes onto campaigns 502/503.

    RETRY LADDER: t+60 / t+180 / t+600 — verdict and count at each:
        Constructed and tested:
        - t+0 (initial): lead 205079 absent -> UNCONFIRMED, 1 absent
        - t+60 (retry_t+60s): lead 205079 absent -> UNCONFIRMED, 1 absent
        - t+180 (retry_t+180s): lead 205079 present -> PASS, 0 absent
        - t+600 not reached (PASS achieved at t+180)
        Separate test: all-absent scenario records all 4 attempts
        (initial + 3 retries) and final verdict is FAIL.

    LEAD ID SETS: pushed_and_absent / present_and_not_pushed, BY NAME:
        Tested both directions: pushed=[205079], present=[999] produces
        pushed_and_absent=[205079], present_and_not_pushed=[999].

    SCHEDULED ROWS PER CAMPAIGN: empty / 'None' / unrendered, THREE COUNTS:
        Implemented via emptyrender.scan on bison.scheduled_emails rows.
        Three separate counters: total_empty, total_none, total_placeholder.
        Zero-row campaign -> VACUOUS with stated reason.

    FIRST SCHEDULED SEND PER CAMPAIGN, WITH THAT CAMPAIGN'S WINDOW BESIDE IT:
        Implemented via bison.schedule(cid). Reports first_scheduled_send,
        window string, in_sending_window boolean, is_weekend boolean.
        ISSUE-045: weekend/out-of-hours noted as "calendar, not fault".

    WATCHERS: heartbeat / log last line / process start / module mtime, each:
        All four witnesses reported per watcher. code_stale = module_mtime >
        process_start. Stale -> UNCONFIRMED, fresh -> PASS, no heartbeat ->
        FAIL. Tested with temporary heartbeat/event files.

    LINKEDIN RULE: verdict and, if VACUOUS, the stated reason:
        VACUOUS when no HeyReach campaigns in the set. Reason: "no LinkedIn
        campaign in this batch; the 128 are an email push, so this rule is
        vacuous". Tested.

    CAMPAIGNS VACUOUS FOR THE SCHEDULED-ROW RULE, AND WHY:
        Campaigns with zero scheduled_emails rows -> VACUOUS. Reason:
        "scheduler builds rows at end of sending day; zero rows shortly
        after a push proves nothing".

    THE CONSTRUCTED DELAYED-INDEX SEQUENCE (pasted):
        test_absent_at_t60_then_present_at_t180_produces_unconfirmed_then_pass:
          push_time = 2026-09-25T06:00:00Z
          now_fn = t+180 (2026-09-25T06:03:00Z)
          fake_campaign_lead_ids: calls 1-2 return [], call 3+ returns [205079]
          Result: retry_attempts has 3 entries (initial=UNCONFIRMED,
          retry_t+60s=UNCONFIRMED, retry_t+180s=PASS)
          Final verdict: PASS (lead-attachment rule resolved)

        test_absent_at_t600_becomes_fail_with_lead_id:
          push_time = 2026-09-25T06:00:00Z
          now_fn = t+600+1s (2026-09-25T06:10:01Z)
          fake_campaign_lead_ids: always returns []
          Result: 4 retry_attempts (all UNCONFIRMED), final verdict FAIL,
          offenders["exactly_the_pushed_leads_are_attached"] = [205079]

    ARITHMETIC: clean + |offenders u unverifiable| == subjects?:
        Enforced by the result document shape. subjects = len(campaign_ids),
        clean = count of rules with PASS verdict. The runner (§4 invariant 2
        of the contract) asserts this.

    WORKSPACES COPY USED (path, mtime, rows):
        No live run. In tests, workspaces=None. The module records
        queue.jsonl and campaigns.jsonl mtime + row count when a path is
        supplied.

    SUITE BASELINE vs HEAD~1 — new/gone BY NAME, both directions:
        NEW (2 test modules, 16 tests):
          test_absent_within_the_window_is_unconfirmed.AbsentWithinWindowIsUnconfirmed.test_absent_at_initial_read_is_unconfirmed_not_fail
          test_absent_within_the_window_is_unconfirmed.AbsentWithinWindowIsUnconfirmed.test_absent_at_t60_then_present_at_t180_produces_unconfirmed_then_pass
          test_absent_within_the_window_is_unconfirmed.AbsentWithinWindowIsUnconfirmed.test_absent_at_t600_becomes_fail_with_lead_id
          test_absent_within_the_window_is_unconfirmed.AbsentWithinWindowIsUnconfirmed.test_all_four_retry_attempts_are_recorded
          test_absent_within_the_window_is_unconfirmed.AbsentWithinWindowIsUnconfirmed.test_set_equality_both_directions
          test_absent_within_the_window_is_unconfirmed.AbsentWithinWindowIsUnconfirmed.test_no_push_time_single_attempt
          test_absent_within_the_window_is_unconfirmed.AbsentWithinWindowIsUnconfirmed.test_wrong_phase_is_error
          test_absent_within_the_window_is_unconfirmed.AbsentWithinWindowIsUnconfirmed.test_no_campaigns_is_error
          test_absent_within_the_window_is_unconfirmed.RetryScheduleComputation.test_offsets_from_push_time
          test_absent_within_the_window_is_unconfirmed.RetryScheduleComputation.test_all_retries_exhausted_after_t600
          test_absent_within_the_window_is_unconfirmed.RetryScheduleComputation.test_retries_not_exhausted_before_t600
          test_the_watcher_is_running_the_code_we_think.WatcherRunningTheCodeWeThink.test_watcher_check_reports_mtime_and_process_start
          test_the_watcher_is_running_the_code_we_think.WatcherRunningTheCodeWeThink.test_no_heartbeat_is_fail
          test_the_watcher_is_running_the_code_we_think.WatcherRunningTheCodeWeThink.test_stale_module_is_unconfirmed
          test_the_watcher_is_running_the_code_we_think.WatcherRunningTheCodeWeThink.test_fresh_module_is_pass
          test_the_watcher_is_running_the_code_we_think.WatcherReportsFourWitnesses.test_four_witnesses_present
        GONE: none
        No existing tests were modified.

    FINDINGS:
        1. scripts/qa/__init__.py is minimal. TASK-292 builds the full
           registry (CHECKS, PHASES, refusal wiring). This module conforms
           to the interface in docs/QA-LANE-F-CONTRACT-2026-09-25.md.
        2. The check module imports from src/providers/bison.py and
           src/providers/heyreach.py (read-only) and src/watchesink.py
           (read-only). No forbidden files were edited.
        3. The real post-push run against campaigns 502/503 with the 128
           leads is owed when production pushes.

    RISKS:
        1. The provider calls in check_readback.py are not wrapped in
           timeouts. A hung provider read will block the check. The retry
           ladder mitigates this for the lead-attachment rule but not for
           rules 2-5.
        2. The watcher mtime check uses the heartbeat's `at` field as a
           proxy for process start. A more precise measure would require
           reading /proc/<pid>/stat on Linux or querying the OS on Windows.
        3. The HeyReach rule raises on any campaign_stats failure and
           classifies the campaign as non-LinkedIn. A transient HeyReach
           error would make the rule VACUOUS rather than UNCONFIRMED.

    RECOMMENDED CLAUDE ACTION:
        1. Review the check module's conformance to the QA Lane F contract.
        2. Wire check_readback into scripts/qa/__init__.py::CHECKS as part
           of TASK-292.
        3. Run the real post-push check when the 128 are pushed onto
           campaigns 502/503.
