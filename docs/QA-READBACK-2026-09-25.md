# QA Readback Check — `scripts/qa/check_readback.py`

**TASK-298. Lane F, post_push phase. 2026-09-25.**

The check that runs within one cycle of the push and answers: did exactly
the leads we pushed arrive, will every scheduled step actually have words
in it, when is the first one going out, and is anything watching?

---

## The five rules

| # | Rule | Subject | Verdict when clear |
|---|------|---------|--------------------|
| 1 | `exactly_the_pushed_leads_are_attached` | Set equality at the provider, diffed BOTH directions | PASS |
| 2 | `every_scheduled_step_has_subject_and_body` | RENDERED queue rows at the provider | PASS |
| 3 | `first_scheduled_send_recorded` | A timestamp, per campaign, read back | PASS or VACUOUS |
| 4 | `a_watcher_is_on_the_campaign` | Watcher registered AND running current code | PASS |
| 5 | `linkedin_leads_read_pending_or_insequence` | LinkedIn half, when there is one | PASS or VACUOUS |

---

## ISSUE-043: absent within the window is not absent

`bison.attach_leads` reads membership back 6 times over ~15s and raises
`ProviderError` when the lead is absent. **Measured 2026-09-24 late: the
campaign-membership index took ~30 seconds.** Attaching lead 205079 to 491
answered 200, raised "1 of 1 leads are not in campaign 491 after 6
readbacks over ~15s", and the lead was present on the next poll at t+30s
with the campaign count moved 332 → 333.

**The contract's answer:** absent within the window is UNCONFIRMED (exit 2),
and UNCONFIRMED at this phase is retried on a fixed schedule — t+60s,
t+180s, t+600s from the push, not a loop. Still absent at t+600s becomes
FAIL. Every attempt is recorded with its timestamp and its count, so the
report shows the index catching up rather than a single verdict.

### The retry ladder

```
t+0     initial readback           UNCONFIRMED  1 of 2 absent
t+60s   first retry                UNCONFIRMED  1 of 2 absent
t+180s  second retry               PASS         0 of 2 absent
t+600s  not run (ladder stopped)
```

The ladder stops at the first PASS. A lead absent at t+600 produces FAIL
with its id.

---

## The five rules in detail

### Rule 1: exactly_the_pushed_leads_are_attached

Set equality, BOTH directions. `count == count` is not set equality: the
campaign count moving 332 → 333 is consistent with the right lead arriving
and with a different one arriving. The check diffs the id sets and reports:

- `pushed_and_absent` — leads we pushed that the provider does not show
- `present_and_not_pushed` — leads the provider shows that we did not push

The second is the one nobody looks for and it is the one that means
somebody else's leads are in our campaign.

### Rule 2: every_scheduled_step_has_subject_and_body

Asked of the RENDERED rows at the provider, not on our templates. Three
separate fault counts:

- **empty** — `''`, whitespace, or HTML that renders to nothing (`<p></p>`)
- **literal 'None'** — the four-character string `None` or `null`
- **unrendered** — an unresolved merge field (`{BODY_1}`, `{{FIRST_NAME}}`)

A campaign with zero scheduled rows is **VACUOUS, not PASS** — the
scheduler builds the rows at the end of a sending day, so zero rows an hour
after a push is normal and proves nothing.

### Rule 3: first_scheduled_send_recorded

The line that stops "enrolled" being read as "sent". Enrolled is not sent,
scheduled is not sent, active is not sent, recovered is not sent. The
timestamp is read back per campaign and reported beside the campaign's
sending window.

A zero at a weekend or before a window opens is the calendar rather than a
fault — every EmailBison campaign is 09:00-17:00 Mon-Fri in its own
timezone (ISSUE-045). The window is reported beside the timestamp so the
two are read together.

### Rule 4: a_watcher_is_on_the_campaign

Two questions: is a watcher registered for this campaign id, and is that
watcher running the code we think? A merge is not a deploy: about fifteen
loops import at start and never reload, so the watcher module's **mtime is
checked against the process start time** before believing a watcher is
running what was just read.

Four witnesses per watcher, all reported:

1. **Heartbeat** — the watcher's last beat timestamp
2. **Log last line** — the last line of the watcher's event log
3. **Process start** — when the state file was written
4. **Module mtime** — when the source file was last modified

A watcher reported UP with no such pair is a watcher nobody checked.

### Rule 5: linkedin_leads_read_pending_or_insequence

When the batch has no LinkedIn half, this rule is **VACUOUS with a stated
reason, never PASS**. Today's 128 are an email push, so this rule will be
vacuous on the first real run, and that is the correct output.

---

## Exit codes

| Code | Verdict | post_push meaning |
|------|---------|-------------------|
| 0 | PASS | Every rule clear |
| 1 | FAIL | At least one rule offends |
| 2 | UNCONFIRMED / VACUOUS | Retried on the ladder, or the subject set is empty |
| 3 | ERROR | The check itself broke |

---

## What would make this a false pass

- **Reading "absent within the window" as FAILED.** ISSUE-043.
- **Reading "absent within the window" as PASSED.** UNCONFIRMED is a third answer.
- **Comparing counts instead of id sets.** 332 → 333 is consistent with the wrong lead arriving.
- **Never asking `present_and_not_pushed`.** One-directional diffs hide the case that matters.
- **Zero scheduled rows read as clean.** VACUOUS.
- **A watcher reported UP from its own heartbeat alone.** mtime against process start.
- **A LinkedIn rule that passes because the batch has no LinkedIn leads.** VACUOUS.
- **Reading `in_sequence`, `scheduled` or `active` as a send.**
- **A retry loop with no ceiling.** Three attempts on a fixed schedule.
- **Any provider write.** No re-attach, no re-push, no stop.

---

## Files

```
scripts/qa/check_readback.py          the check
tests/test_absent_within_the_window_is_unconfirmed.py
tests/test_the_watcher_is_running_the_code_we_think.py
docs/QA-READBACK-2026-09-25.md        this document
```

---

## The constructed delayed-index sequence

```
t+0     initial     UNCONFIRMED   pushed_and_absent: [102]   present_and_not_pushed: []
t+60s   retry 1     UNCONFIRMED   pushed_and_absent: [102]   present_and_not_pushed: []
t+180s  retry 2     PASS          pushed_and_absent: []      present_and_not_pushed: []
t+600s  not run     (ladder stopped at first PASS)
```

This is what ISSUE-043 looks like when the check is right: the index
catches up, the ladder records every step, and the final verdict is PASS
because the lead arrived within the window.
