# QA Readback — post-push check, 2026-09-25

**TASK-298.** Lane F, the standing QA suite. The check that runs within one
cycle of the push and answers whether the push landed.

## What it answers

Within one cycle of the push:

1. Did exactly the leads we pushed arrive?
2. Will every scheduled step actually have words in it?
3. When is the first one going out?
4. Is anything watching?
5. Are the LinkedIn leads in the right state? (vacuous when there is no
   LinkedIn half)

## The thing that makes this hard — ISSUE-043

`bison.attach_leads` reads membership back 6 times over ~15s and raises
`ProviderError` when the lead is absent. **The campaign-membership index
took ~30 seconds** (measured 2026-09-24). A lead that answered 200, raised
"not in campaign 491 after 6 readbacks", and was present at t+30s with the
count moved 332 → 333.

**A post-push readback must not read "absent within the window" as FAILED.**
The failure direction is what matters: a caller that believes the raise will
re-attach, or will treat a good push as failed and re-push, and a re-push
against a lead that is now `in_sequence` cannot be attached anywhere at all.

## The contract

Absent within the window is **UNCONFIRMED** (exit 2), and UNCONFIRMED at
this phase is **retried on a fixed schedule — t+60s, t+180s, t+600s from
the push, not a loop.** Still absent at t+600s becomes FAIL. Every attempt
is recorded with its timestamp and its count, so the report shows the index
catching up rather than a single verdict.

## Five rules

### exactly_the_pushed_leads_are_attached

Set equality at the provider, diffed **BOTH directions**:
`pushed_and_absent` and `present_and_not_pushed` as named lists. The second
is the one nobody looks for and it is the one that means somebody else's
leads are in our campaign.

`count == count` is not set equality: the campaign count moving 332 → 333 is
consistent with the right lead arriving and with a different one arriving.

### every_scheduled_step_has_subject_and_body

On the **RENDERED queue rows at the provider**, not on our templates. Three
separate counts: empty, the literal `'None'`, and an unrendered `{`.

A campaign with zero scheduled rows is **VACUOUS**, not PASS — the scheduler
builds the rows at the end of a sending day, so zero rows an hour after a
push is normal and proves nothing.

### first_scheduled_send_recorded

A timestamp, per campaign, read back. **Enrolled is not sent, scheduled is
not sent, active is not sent, recovered is not sent.**

Every EmailBison campaign is 09:00-17:00 Mon-Fri in its own timezone
(ISSUE-045). A zero at a weekend or before a window opens is the calendar
rather than a fault. The window is reported beside the timestamp so the two
are read together.

### a_watcher_is_on_the_campaign

Two questions: is a watcher registered for this campaign id, and is that
watcher **running the code we think?** A merge is not a deploy — about
fifteen loops import at start and never reload. The watcher module's
**mtime is checked against the process start time** before believing a
watcher is running what was just read.

Four witnesses per watcher: heartbeat timestamp, log's last line, process
start time, module mtime. A watcher reported UP with no such pair is a
watcher nobody checked.

### linkedin_leads_read_pending_or_insequence

When the batch has no LinkedIn half, this rule is **VACUOUS with a stated
reason**, never PASS. Today's 128 are an email push, so this rule will be
vacuous on the first real run.

## Exit codes

    0   PASS         every rule clear
    1   FAIL         at least one rule offended
    2   UNCONFIRMED  could not establish the answer (retry ladder in
                     progress, or VACUOUS)
    3   ERROR        the check itself broke

## Usage

    py -3 scripts/qa/check_readback.py \
        --phase post_push \
        --batch batch-2-2026-09-25 \
        --campaign 502 --campaign 503 \
        --workspaces <path to a copy of production work/> \
        --pushed-leads 205079,205080 \
        --push-time 2026-09-25T06:00:00Z \
        --json work/qa/2026-09-25T06-00Z/readback.json

## Read surface

    EmailBison   bison.campaign_lead_ids(id)
                 bison.campaign_lead_count(id)
                 bison.membership(id, lead_ids)
                 bison.scheduled_emails(id, cap)
                 bison.sending_schedule(id, day) / bison.schedule(id)
                 bison.lead(id)

    HeyReach     heyreach.campaign_leads(id)
                 heyreach.lead_state(row)
                 heyreach.readback_membership(id, urls)
                 heyreach.campaign_stats(id)

    Render       emptyrender.scan / classify_row / summarise

    Watchers     watchsink.heartbeats / events_path (READ ONLY)

## Boundaries

- **READS ONLY at both providers.**
- Do not edit watcher scripts. Read their heartbeats, logs and process
  metadata; write nothing.
- Do not edit `src/bisonfactory.py`, `src/heyreachfactory.py`,
  `src/providers/*`, or `src/emptyrender.py`.
- Do not re-render and do not re-push.
- No prospect PII in any committed file.
- Production `work/` is not yours; `--workspaces` a named copy.

## What would make this a false pass

- Reading "absent within the window" as FAILED — ISSUE-043.
- Reading "absent within the window" as PASSED so the table goes green.
- Comparing counts instead of id sets.
- Never asking `present_and_not_pushed`.
- Zero scheduled rows read as clean.
- A watcher reported UP from its own heartbeat alone.
- A LinkedIn rule that passes because the batch has no LinkedIn leads.
- Reading `in_sequence`, `scheduled` or `active` as a send.
- A retry loop with no ceiling.
- Any provider write.

## Tests

    tests/test_absent_within_the_window_is_unconfirmed.py
        11 tests: the constructed delayed-index sequence, t+600 still
        absent -> FAIL, all four attempts recorded, set equality both
        directions, single attempt without push time, wrong phase -> ERROR.

    tests/test_the_watcher_is_running_the_code_we_think.py
        5 tests: mtime and process start both reported, stale module ->
        UNCONFIRMED, fresh module -> PASS, no heartbeat -> FAIL, four
        witnesses present.
