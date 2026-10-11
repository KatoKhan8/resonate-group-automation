"""What the blank-content halt has already responded to. ONE FILE PER WATCHER.

## The defect this exists for, MEASURED 2026-10-11/12

`scripts/bison_watch_loop.py` watches EmailBison campaign 481 every 180s. 481
holds ONE scheduled row with an empty subject - row 22364357, lead 203709, step
4730, status `sending_paused` - and `_halt_on_blank_content` correctly finds it
every single cycle. The halt's response is to pause the campaign. **481 was
already paused**, so the pause changed nothing, the blank row stayed, and the
next cycle found the same row and paused it again.

`work/provider-writes.jsonl`, counted 2026-10-12: **1410 rows of
`bison.pause` 481, every one `accepted`, by `bison_watch_loop`, from
2026-09-25T16:04:38Z to 2026-10-11T23:11:52Z** - one every three minutes for
sixteen days. Three consecutive examples:

    2026-10-11T22:23:32Z bison.pause 481 accepted by bison_watch_loop
    2026-10-11T22:26:33Z bison.pause 481 accepted by bison_watch_loop
    2026-10-11T22:29:34Z bison.pause 481 accepted by bison_watch_loop

That is a real provider write loop, and it is also an alarm firing forever into
nothing: the CRITICAL that means "a campaign is about to send an empty email"
had been raised 1410 times for one row, which is the same as not raising it.

**The detection was right every time.** What was missing was a memory of
having already responded, so the fix is here rather than in the predicate.

## WHY THE STATE IS NOT IN THIS TREE'S `work/`

`work/` is gitignored and every worktree has its own, so `store.PRODUCTION_WORK`
resolves against the tree the module was imported from. A memory kept there
would be empty in every worktree and would reset the moment the fleet was
restarted from somewhere else - which would restore the exact loop above while
looking fixed. `src/suitelock.py` learned this on 2026-10-02 after six suites
ran at once, and `src/store.py` learned it again on 2026-10-03: anything that
must be machine-wide resolves through
`git rev-parse --path-format=absolute --git-common-dir`, the one path identical
from the main checkout and from every worktree.

So this module asks `store.main_checkout_work()`, which is that resolution,
cached, and which REFUSES a relative answer from git rather than resolving it
against the caller's cwd - from a worktree, that worktree.

## WHY ONE FILE PER CAMPAIGN

`src/watchsink.py` measured it: six writers x 40 lines into one file under
`work/` on Windows produced 193 lines, not 240. Not torn - LOST, because the
Windows CRT implements `O_APPEND` as a seek-then-write. Nine of these watchers
run at once, one process per campaign, so nine processes sharing one memory file
is exactly that race. Each watcher owns `blank-halt/bison-<id>.json` and no two
processes write the same path. The write is also a temp-file-and-replace, so a
reader never sees half a record.

## FAILING LOUD IS FAILING SAFE HERE

Every read failure is reported as "nothing recorded", and every write failure is
reported to the caller rather than raised. Both make the halt fire AGAIN next
cycle, which is the direction that cannot hide a blank email. A memory that
could suppress the control by being unreadable would be worse than no memory:
this module may make the alarm quieter, and it may never make it silent.
"""
import hashlib
import json
import os
import time

from . import store

#: The directory the per-campaign memories live in, under `work/`.
DIRNAME = "blank-halt"


def directory(dir_path=None):
    """Where the memories live. The MAIN checkout's `work/blank-halt`.

    `dir_path` is for tests and for an operator inspecting a copy - it is an
    argument rather than an environment variable on purpose: an env override is
    ambient state that a service launcher can set by accident, and a memory
    silently pointed at a per-tree directory is the defect this module exists
    for. The production path takes no arguments at all.

    Falls back to THIS tree's `work/` when git cannot answer, the way
    `suitelock.path` does, and the caller records that it did - see
    `tree_local` below. A per-tree memory is still once-per-condition for as
    long as the process lives, which is better than the loop; it is recorded
    so nobody reads it as the durable thing.
    """
    if dir_path:
        return os.path.abspath(dir_path)
    main = store.main_checkout_work()
    if main:
        return os.path.join(main, DIRNAME)
    return os.path.join(store.PRODUCTION_WORK, DIRNAME)


def is_tree_local(dir_path=None):
    """True when `directory` had to fall back to this tree's own `work/`."""
    return not dir_path and not store.main_checkout_work()


def path(campaign, dir_path=None):
    """One file per watched campaign. `bison-481.json`.

    The name is the watcher's identity, the same way `watchsink` names its
    files, because the writer is the same process and the reason is the same:
    two processes on one file under `work/` lose rows on Windows.
    """
    name = str(campaign or "").strip()
    if not name:
        raise ValueError("a blank-halt memory must name a campaign")
    return os.path.join(directory(dir_path), "bison-%s.json" % (name,))


def _stamp(at=None):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ",
                         time.gmtime(time.time() if at is None else at))


def describe(pending):
    """The offending rows, as the three facts that identify them.

    Returns `(rows, steps, reasons)`, each sorted, each a list of strings.
    NO LEAD IDENTIFIER and no copy: a row id and a step id are provider
    bookkeeping, a lead id is a person, and this file is read by whoever is
    debugging the monitor.
    """
    rows, steps, reasons = set(), set(), set()
    for entry in pending or []:
        rows.add(str(entry.get("row")))
        if entry.get("step"):
            steps.add(str(entry.get("step")))
        for fault in entry.get("faults") or []:
            field, reason = (list(fault) + [None, None])[:2]
            reasons.add("%s/%s" % (field, reason))
    return sorted(rows), sorted(steps), sorted(reasons)


def fingerprint(pending):
    """A digest of WHICH rows are wrong and HOW, per row.

    Row id + step id + that row's own fault list, so:

    * the same rows with the same faults fingerprint the same, however many
      cycles apart, and however the provider orders its queue page;
    * a NEW blank row changes it - a new row id;
    * a row that gains a fault changes it - `subject/EMPTY` is not
      `subject/EMPTY+body/EMPTY`, and the second is a worse incident;
    * a row that is FIXED changes it, because the set it belonged to shrinks.

    Per row rather than three flat sets, so two rows swapping which fault they
    carry is a different fingerprint rather than the same union.
    """
    parts = []
    for entry in pending or []:
        faults = sorted("%s/%s" % tuple((list(f) + [None, None])[:2])
                        for f in entry.get("faults") or [])
        parts.append("%s:%s:%s" % (entry.get("row"), entry.get("step"),
                                   "+".join(faults)))
    blob = "|".join(sorted(parts))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def condition_key(campaign, status, pending):
    """The identity of one blank-content condition. THE CAMPAIGN STATUS IS IN IT.

    `<campaign>|<status>|<fingerprint>`.

    WHY THE STATUS BELONGS IN THE KEY. The halt's response is to PAUSE the
    campaign, so whether the response is still needed depends on the campaign's
    state and not only on the rows. 481 was `paused` with a blank row pending:
    the pause is a no-op, the condition is contained, and the control has
    nothing left to do but say so once. The same row on an `active` campaign is
    a different thing entirely - nothing is containing it, and the pause is a
    real action that must be taken. A key without the status cannot tell those
    apart, so it would have to choose between re-pausing a contained campaign
    forever (what 481 did) and staying silent while an un-paused campaign sends
    the blank (the expensive direction).

    So an un-pause with the same row still there IS a new condition and the
    halt fires on it.

    WHAT IS DELIBERATELY *NOT* IN THE KEY: the row's own `status`. 481's row
    reads `sending_paused` because the CAMPAIGN is paused, and
    `emptyrender.SETTLED_STATUSES` already decides which rows can still send.
    A per-row status in the key would re-fire on every provider relabelling of
    a row nobody fixed.

    AND NOT A TIMESTAMP, and not a counter. Either would make every cycle a new
    condition, which is the loop this exists to stop wearing a hash.
    """
    state = str(status or "").strip().lower() or "unknown"
    return "%s|%s|%s" % (campaign, state, fingerprint(pending))


def load(campaign, dir_path=None):
    """What was recorded for this campaign, or `{}`.

    An ABSENT, unreadable or corrupt file all answer the same way - nothing is
    recorded - because the only safe reading of "I cannot tell whether I have
    already responded" is that I have not. That answer costs one duplicate
    provider write; the other answer costs a blank email.
    """
    try:
        with open(path(campaign, dir_path), encoding="utf-8") as handle:
            row = json.load(handle)
    except Exception:                                          # noqa: BLE001
        return {}
    return row if isinstance(row, dict) else {}


def responded(campaign, key, dir_path=None):
    """Has this exact condition already been responded to? `(bool, row)`.

    Compares against the LAST condition recorded, not against a history of
    every condition ever seen. That is what makes "the campaign was un-paused
    and the row is still there" fire again: the recorded condition no longer
    matches the observed one, and a condition that has been superseded is not
    evidence about the one in front of you.

    The bool says the KEY matches. WHICH HALVES OF THE RESPONSE ALREADY
    HAPPENED is in the row - `pause_attempted` and `alerted` - and the caller
    reads them separately on purpose: an alert that did not land must be
    retried, and retrying it must not re-pause the campaign.
    """
    row = load(campaign, dir_path)
    return bool(row) and row.get("condition") == key, row


def record(campaign, key, dir_path=None, **details):
    """Write the memory. Returns `(row, error)`; NEVER raises on a write fault.

    Two shapes, decided by whether `key` is the condition already recorded:

    * a NEW condition - the row is replaced, `fired_at` and `first_seen_at` are
      now, `seen` restarts at 1;
    * the SAME condition - `last_seen_at` and `seen` move, and whatever
      `details` the caller has newly LEARNED are merged over the row. A repeat
      cycle with no details is the "still detecting" record: evidence that the
      control looked and found the fault, written without a provider write and
      without an alert. A repeat that carries `alerted=True` is an alert that
      failed on the first pass and landed on this one - which is why the two
      halves of the response are recorded separately and not as one flag.

    `error` is a string when the write did not land. The caller reports it and
    carries on: a halt that died because it could not write its own bookkeeping
    would be a control removed by its own idempotency.
    """
    now = _stamp()
    previous = load(campaign, dir_path)
    if previous.get("condition") == key:
        row = dict(previous)
        row.update(details)
        row["last_seen_at"] = now
        row["seen"] = int(previous.get("seen") or 0) + 1
    else:
        row = dict(details)
        row["campaign"] = str(campaign)
        row["condition"] = key
        row["fired_at"] = now
        row["first_seen_at"] = now
        row["last_seen_at"] = now
        row["seen"] = 1
        if is_tree_local(dir_path):
            # NAMED, because a memory in a worktree's own `work/` is not the
            # durable thing this module promises and must not be read as it.
            row["tree_local"] = True
    row["pid"] = os.getpid()
    target = path(campaign, dir_path)
    try:
        # The second barrier, before any filesystem mutation including the
        # directory - `store.refuse_production_write` is why a test that forgets
        # to pass `dir_path` fails loudly instead of writing the operator's real
        # monitor state. Both `work/` directories are protected, and the
        # production path for this file is inside one of them by design.
        store.refuse_production_write(target)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        tmp = "%s.%d.tmp" % (target, os.getpid())
        with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        os.replace(tmp, target)
    except Exception as exc:                                   # noqa: BLE001
        return row, "%s: %s" % (type(exc).__name__, str(exc)[:200])
    return row, None
