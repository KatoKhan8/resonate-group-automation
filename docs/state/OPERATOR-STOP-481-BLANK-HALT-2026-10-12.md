# OPERATOR STOP: the 481 blank-content pause loop

**Decided by the operator (Zvonimir), 2026-10-12.** Deliberate stop, recorded
here because a provider-write loop that simply disappears from the ledger is
indistinguishable from a monitor that died.

**THE DETECTION IS RETAINED.** Nothing about which rows halt, or about the
predicate that finds them, is changed or weakened. What was stopped is the
REPETITION of the response.

---

## 1. What was stopped

`scripts/bison_watch_loop.py::_halt_on_blank_content` was issuing one
`providerwrites.perform(EMAIL_PAUSE, ...)` against EmailBison campaign **481**
every polling cycle - 180 seconds - and had been doing so since
2026-09-25T16:04:38Z.

It now responds **once per condition** instead of once per cycle. On a later
cycle carrying the same condition it still scans, still detects, and still
reports in the heartbeat; it does not issue a second provider write and does
not raise a second alert.

## 2. The measurement

`work/provider-writes.jsonl`, counted 2026-10-12:

    1410  bison.pause  campaign 481  outcome accepted  by bison_watch_loop
    first  2026-09-25T16:04:38Z   (pid 46016)
    last   2026-10-11T23:11:52Z   (pid 14156, alive at the time of writing)

    2026-10-11T22:23:32Z bison.pause 481 accepted by bison_watch_loop
    2026-10-11T22:26:33Z bison.pause 481 accepted by bison_watch_loop
    2026-10-11T22:29:34Z bison.pause 481 accepted by bison_watch_loop

Of 1417 `bison.pause` rows in the whole ledger, **1410 are this loop**.

`work/heartbeat/bison-481.json` at 2026-10-11T23:11:52Z, which is why the
pause changed nothing:

    campaign 481   status PAUSED   leads 23   queue_rows 10   emails_sent 0
    membership     {"stopped": 14, "sending_paused": 9}
    blanks.pending [ row 22364357, lead 203709, step 4730,
                     status sending_paused, faults [["subject","EMPTY"]] ]
    blanks.already []

481 was already paused. The halt's response was therefore a no-op against the
provider, the blank row stayed exactly where it was, and the next cycle found
the same row and paused the campaign again. Forever.

## 3. Two things the measurement falsified

**(a) `CLAUDE.md` says "provider writes from us remain 0".** That is false and
has been since 2026-09-25. This system has performed at least 1410 accepted
provider writes, all of them this loop. **CLAUDE.md was deliberately not
edited by this change** - correcting the operator's own standing document is
the operator's call - but the line is wrong and should be corrected there.

**(b) The CRITICAL was never raised for 481 at all.** `work/notifications.jsonl`
holds exactly **one** `campaign_blank_content` row for all time:

    id 6b017a290c97c465a8be   at 2026-09-23T20:18:58+00:00
    campaign 497   status FAILED   attempts 1
    last_error "AttributeError: 'str' object has no attribute 'get'"
    ids {}

The halt passed **no `ids`**, so `notify.notification_id` built the same
identifier for every blank-content finding there will ever be, and `plan` is
idempotent on that identifier. Every one of 481's 1410 firings collapsed onto
that one 497-shaped row and planned nothing. The alarm had fired 1410 times
into nothing, which is exactly how a real one gets masked. The ids now name
the campaign and the condition, so a different campaign and a different
condition each get their own row.

**That one row's delivery is still broken and is NOT fixed here.** It is
`failed` with `AttributeError: 'str' object has no attribute 'get'` raised by
the delivery loop, so no blank-content CRITICAL has ever reached Slack. That
is a defect in `scripts/notify_deliver_loop.py` / the payload it is handed,
it is outside this stop's scope, and it needs its own task.

## 4. Why the process was not simply killed

A kill would be undone at the next restart, and nothing about it would be
recorded as a decision.

* The Windows scheduled task **`ResonateMonitors`** restarts the monitor
  fleet.
* The watcher for 481 is **derived**, not configured: `src/supervisor.py`'s
  `campaign_monitors` / `_watch_campaign` (~line 165) gives a watcher to every
  campaign in the canonical registry that is not provably finished-and-empty,
  and `_watch_campaign` has **no operator-stop field**. A paused campaign with
  a non-terminal row is watched, correctly.
* Faking 481's status or its registry row to make the watcher retire would be
  a lie written into canonical state, which is worse than the loop.

So the stop is in the code path that writes, not in the process list and not
in the state the watcher reads.

## 5. What the halt now remembers, and where

`src/blankhalt.py`. One file per campaign: `work/blank-halt/bison-<id>.json`.

**The condition key is `<campaign>|<campaign status>|<fingerprint>`**, where
the fingerprint is a SHA-256 digest over, per offending pending row, its row
id, its step id, and its own sorted fault list.

**The campaign status is in the key deliberately.** The halt's response is to
PAUSE, so whether that response is still owed depends on the campaign's state
and not only on the rows: a blank row on a `paused` campaign is contained and
the pause is a no-op, while the same row on an `active` campaign is about to
be sent and the pause is a real action. A key without the status would have to
choose between re-pausing a contained campaign forever and staying silent
while an un-paused one sends the blank.

**The memory lives beside the MAIN checkout's `work/`**, resolved through
`git rev-parse --path-format=absolute --git-common-dir` by
`store.main_checkout_work()` - the same one path `src/suitelock.py` and
`src/store.py`'s write barrier use, and the one answer that is identical from
the main checkout and from every worktree. A **relative** answer from git is
REFUSED rather than resolved against the cwd, because `abspath` from a
worktree would resolve it into that worktree and give every tree its own
memory, which is the loop again. A per-tree memory would reset on every
restart from a different tree and defeat the whole point.

## 6. What makes the halt fire again

Any of these is a NEW condition and gets a provider write, an alert and a
`BLANK-CONTENT` line:

* **a new blank row appears** - a new row id changes the fingerprint;
* **an existing blank row gains a fault** - `subject/EMPTY` is not
  `subject/EMPTY + body/EMPTY`, and the second is a worse incident;
* **a blank row is fixed while another remains** - the set shrank;
* **the campaign is un-paused with the same row still there** - the status
  component of the key changes, and the row is no longer contained;
* **the halt's memory cannot be read** - a corrupt or missing file reads as
  "nothing recorded", never as "already handled";
* **the halt's memory cannot be written** - the failure is reported as
  `BLANK-HALT-MEMORY-UNWRITABLE` and the condition stays unrecorded, so the
  next cycle responds again;
* **the alert recorded nothing at all** - the pause and the alert are
  remembered separately, so an alert that landed nowhere is retried on the
  next cycle WITHOUT re-pausing.

There is **no flag, environment variable or configuration that disables this
control**, and the memory can only make the alarm quieter, never silent.

## 7. What a repeat cycle still does

* runs the full `emptyrender.scan` over every pending queue row;
* rewrites `work/heartbeat/bison-481.json` with the live state AND a note
  naming the condition, the rows, the faults, when it was first responded to
  and how many cycles it has been present;
* bumps `seen` and `last_seen_at` in its own memory file.

The event log keeps one line per condition on purpose. The signal "the blank
row is still there, right now" belongs in the file that is rewritten every
poll, not in the one that is appended to.

## 8. A MERGE IS NOT A DEPLOY

The monitor fleet imports its code at start and never reloads. **PID 14156 was
still running the old `_halt_on_blank_content` when this was written**, so it
will keep writing one pause every three minutes until that process is
restarted. Landing this change does not stop the loop by itself:

1. land the change on master;
2. restart the 481 watcher (or the fleet, via `ResonateMonitors`);
3. confirm from `work/provider-writes.jsonl` that no new `bison.pause 481` row
   appears after the restart stamp, and that
   `work/blank-halt/bison-481.json` exists with `seen` rising and `fired_at`
   standing still.

Step 3 is the only evidence that the stop took effect. A green test suite is
not that evidence.

## 9. Tests

`tests/test_the_blank_halt_fires_once_per_condition.py` - 28 tests, and the
fixture is campaign 481's own row as read out of the heartbeat above. Each
property has a control that proves the assertion can fail: the same two cycles
with the memory thrown away between them write TWICE, a new blank row fires
AGAIN, a clean campaign records nothing, and a stubbed relative answer from
git is refused while an absolute one is used.

Verified by mutation, each applied, measured and reverted:

* `pause_owed = True` (ignore the memory) - 6 tests fail, including
  "the same condition was written to the provider twice";
* `condition_key` without the fingerprint - 4 fail, including "a NEW blank row
  did not halt";
* `return True` after `BLANK-CONTENT-HALT-REFUSED` (suppress the alert when
  the pause refuses) - 2 fail, including "a refused pause swallowed the
  alert".

No provider calls and no network: `providerwrites.perform` is stubbed and the
store is redirected with `store.use_directory`.
