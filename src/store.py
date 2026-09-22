#!/usr/bin/env python3
"""The only read/write path to work/queue.jsonl.

Nothing else in the repo opens the queue file. Records are never deleted:
drop() marks a record and leaves the line in place so a batch stays auditable
and re-runnable.

CLI:
  python -m src.store list [--state S] [--lane L] [--client C]
  python -m src.store get <id> [--field contacts]
  python -m src.store patch <id> --json '{"state":"enriched"}' [--note "..."]
  python -m src.store drop <id> --reason "..."
  python -m src.store stats
"""
import argparse
import collections
import contextlib
import datetime
import json
import os
import re
import sys
import time
from collections import Counter

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

LANES = ("revive", "cold", "domains")
STATES = ("queued", "enriched", "verified", "drafted", "approved", "pushed",
          "dropped", "held")


def queue_path():
    """Resolved per call, not at import, so tests can point QUEUE elsewhere."""
    return os.path.abspath(os.environ.get("QUEUE")
                           or os.path.join(ROOT, "work", "queue.jsonl"))


def backend():
    """Which storage backend is active. Resolved per call, not at import.

    Three modes:
      jsonl    DEFAULT. Exactly today's behaviour. SQLite untouched.
      shadow   JSONL canonical. Both written. Reads come from JSONL, the same
               read is taken from SQLite and diffed.
      sqlite   SQLite canonical. JSONL untouched.
    """
    mode = (os.environ.get("QUEUE_BACKEND") or "jsonl").strip().lower()
    if mode not in ("jsonl", "shadow", "sqlite"):
        raise ValueError(f"unknown QUEUE_BACKEND: {mode!r}")
    return mode


def db_path():
    """The SQLite database path. Resolved per call, not at import."""
    return os.path.abspath(os.environ.get("QUEUE_DB")
                           or os.path.join(os.path.dirname(queue_path()), "queue.db"))


def campaigns_path():
    """Campaign-level state. A campaign is not a record, so it does not live in
    the queue: forcing it in would mean a row that fails every record
    invariant. Same directory, same lock discipline, same atomic write.
    """
    return os.path.abspath(os.environ.get("CAMPAIGNS")
                           or os.path.join(os.path.dirname(queue_path()),
                                           "campaigns.jsonl"))


# Every environment override that names a state file, in one tuple.
#
# Each state module resolves its own override - `jobs.py` reads JOBS,
# `notify.py` reads NOTIFICATIONS - because each owns its own file's shape.
# What must not be spread out is the *set*: a module added to the system and
# forgotten here keeps pointing at the real `work/` directory while every
# other file moves to a temp one, and a test that writes into the developer's
# queue is the kind of thing discovered by losing a batch.
#
# `tests/test_invariants.py` walks `src/` for `os.environ.get("...")` state
# lookups and fails if one is missing from this tuple.
STATE_OVERRIDES = (
                   # The SQLite record store. Added 2026-09-22 with TASK-253,
                   # and `test_every_state_override_is_in_the_move_together_set`
                   # caught its absence within the hour - which is the half of
                   # that pair doing exactly what it is for.
                   #
                   # It defaults beside `queue_path()`, so it already moves
                   # when QUEUE moves. The hazard is the other direction: a
                   # stale `QUEUE_DB` pointing at the real `work/queue.db`
                   # would SURVIVE `use_directory()`, because that function
                   # works by clearing this tuple. The queue would move to the
                   # temp directory and the database would not, which is the
                   # failure this comment's own paragraph above describes.
                   "QUEUE_DB",
                   "CAMPAIGNS", "JOBS", "WORKSPACES", "AUDIT", "SENDERS",
                   "NOTIFICATIONS", "REPORTS", "REPORT_DRAFTS",
                   # Not row state, but written beside the queue and just as
                   # able to be left pointing at a real directory by a stale
                   # override: the MX cache, the observability counters and
                   # the poller's checkpoints.
                   "MX_CACHE", "OBSERVABILITY", "CHECKPOINTS",
                   # The reply watcher's health, written beside the
                   # checkpoints it reports on and for the same reason.
                   "REPLY_WATCH_STATUS",
                   # The provider tag outbox and the agency-wide
                   # do-not-contact index. Neither is row state either, and
                   # both are exactly the kind of file a test would
                   # otherwise write into the real `work/` - which is how
                   # this pair was found.
                   "TAG_OUTBOX", "AGENCY_DNC", "SIGNALS", "GTM",
                   "DISCOVERY", "CLIENT_REVIEW",
                   # The persisted crawl cache. Not row state, but written
                   # beside the queue and able to be left pointing at the
                   # real directory by a stale override.
                   "CRAWL_CACHE",
                   # The Slack agent's three: its knowledge-pack cache, its
                   # per-thread conversation memory and its change-request
                   # journal. Added 2026-09-22 with Phase B, after
                   # `test_the_checklist_has_not_fallen_behind_the_code`
                   # caught all three writing beside the queue without
                   # asking the barrier.
                   "KNOWLEDGE_PACK", "SLACK_THREADS", "SLACK_REQUESTS",
                   # The client follow-up watches.
                   "SLACK_FOLLOWUPS",
                   # The prospect-facing action ledger. Of everything in this
                   # tuple it is the one a test must never write into the real
                   # `work/`: a stray reservation there would count against a
                   # live pilot cap, and a stray `sent` row would make a real
                   # person look already-contacted.
                   "ACTION_LEDGER",
                   # The durable spend ledger, for the same reason one line
                   # up: a stray row there consumes a real client's budget
                   # ceiling, and a missing one lets a run spend twice. This
                   # was omitted when the ledger was added and
                   # `test_invariants` caught it the same night.
                   "SPEND_LEDGER",
                   # What the PROVIDER did to a staged lead, as distinct from
                   # what this system did. A stray row here would claim a real
                   # prospect had been contacted, so it moves with the rest.
                   "LEAD_OBSERVATIONS",
                   # The background watchers' durable output and their
                   # liveness beats. Not row state, but the file an operator
                   # reads to answer "has it sent yet" - a test appending a
                   # fixture SEND line there would be a fabricated send.
                   "WATCH_EVENTS", "WATCH_HEARTBEAT",
                   # The client-approval store. Not row state, but it decides
                   # whether an account may be spent on at all, and a test
                   # fixture that wrote the REAL file could approve a domain
                   # the client never cleared. Found by TASK-245's worker,
                   # whose own addition to this tuple made the invariant test
                   # report mine as missing - which is the test doing exactly
                   # what its docstring says it is for.
                   "CLIENT_APPROVAL",
                   # The nightly sourcing candidate list. Not queue state,
                   # but written beside the queue and must move with it in
                   # tests or a fixture would append to the real list.
                   "CANDIDATES")

def use_directory(path):
    """Point every state file at one directory. Demo mode and tests only.

    The file *names* stay in this module, which is the only one allowed to
    know them - `tests/test_invariants.py` fails any other module that spells
    one out, because a second place that knows the layout is a second place
    that can disagree with it. Everything except the queue already defaults to
    the queue's directory, so clearing the specific overrides is what makes
    the whole set move together.
    """
    os.makedirs(path, exist_ok=True)
    os.environ["QUEUE"] = os.path.join(path, "queue.jsonl")
    for override in STATE_OVERRIDES:
        os.environ.pop(override, None)
    return queue_path()


def out_dir():
    """Where generated output goes. One definition, so every writer agrees."""
    return os.path.abspath(os.environ.get("OUT") or os.path.join(ROOT, "out"))


def now():
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()


class QueueLocked(RuntimeError):
    """Another process holds the queue. Nothing was written."""


class ShadowDivergence(RuntimeError):
    """Shadow mode detected a divergence between JSONL and SQLite.

    Raised only when SHADOW_STRICT=1. Without it, divergences are written to
    the ledger and the write succeeds - shadow exists to find out whether the
    backend is trustworthy, on the live queue, before anything depends on it.
    """


LOCK_TIMEOUT = float(os.environ.get("QUEUE_LOCK_TIMEOUT", "10"))
LOCK_STALE_AFTER = 300          # seconds; a lock older than this is abandoned


def lock_path(path=None):
    return (path or queue_path()) + ".lock"


@contextlib.contextmanager
def lock(timeout=None, poll=0.05, for_path=None):
    """Cross-process advisory lock, held for the shortest possible window.

    An exclusive create is the one primitive that behaves the same on Windows
    and POSIX. A lock left behind by a killed process is reclaimed after
    LOCK_STALE_AFTER, so a crash cannot wedge the CLI for ever.
    """
    timeout = LOCK_TIMEOUT if timeout is None else timeout
    path = lock_path(for_path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    deadline = time.monotonic() + timeout
    handle = None
    while True:
        try:
            handle = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            try:
                age = time.time() - os.path.getmtime(path)
                if age > LOCK_STALE_AFTER:
                    os.unlink(path)          # abandoned by a dead process
                    continue
            except OSError:
                pass                          # it vanished; try again
            if time.monotonic() >= deadline:
                raise QueueLocked(
                    f"another process has held {os.path.basename(path)} for more "
                    f"than {timeout}s. Nothing was written.")
            time.sleep(poll)
    try:
        os.write(handle, str(os.getpid()).encode())
        os.close(handle)
        handle = None
        yield path
    finally:
        if handle is not None:
            os.close(handle)
        try:
            os.unlink(path)
        except OSError:
            pass


@contextlib.contextmanager
def transaction(timeout=None):
    """Read, change, write, with the lock held across all three.

    Use this for anything that loads the queue, changes it and saves it back.
    A bare save() takes the lock too, but only for the write itself, which
    cannot protect a read-modify-write against a second process.

    THE GUARDS RUN HERE TOO, and they did not. This called `_write` directly,
    so `refuse_evidence_loss` and `refuse_history_loss` - which `save` runs on
    every write - were absent from the path `qualify`, `approve`,
    `repo.save_records`, `run.stage_push` and `providerwrites` all take. The
    guard whose own docstring says it "moves to the boundary every writer
    already crosses" was missing from one of those boundaries.

    Holding the lock is supposed to make a stale write impossible here, which
    is exactly why the check belongs: if the lock is ever wrong - and it has
    been - this is the difference between a refused write and an erased reply.
    """
    with lock(timeout):
        recs = load()
        yield recs
        on_disk = _current_records()
        refuse_evidence_loss(on_disk, recs)
        refuse_history_loss(on_disk, recs)
        mode = backend()
        if mode == "sqlite":
            _write_sqlite(recs)
        elif mode == "shadow":
            _write(recs)
            _write_sqlite_shadow(recs, on_disk)
        else:
            _write(recs)


@contextlib.contextmanager
def file_transaction(path, timeout=None):
    """Read, change, write one jsonl file with its own lock held throughout."""
    with lock(timeout, for_path=path):
        rows = read_jsonl(path)
        yield rows
        write_jsonl(path, rows)


def read_jsonl(path):
    """One row per line. A missing file is an empty list, not an error."""
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def write_jsonl(path, rows):
    """Atomic whole-file write. Callers hold the lock.

    Guarded like the queue: this is the writer behind campaigns, drafts,
    senders, signals and the tag outbox, so a test reaching it reaches real
    client state just as surely.
    """
    refuse_production_write(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    os.replace(tmp, path)


MISSING = object()


def _frozen(value):
    """A comparable, hashable form of one field's value."""
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


class _TrackingRoot:
    """Mixin: marks the root record dirty on any mutation.

    The root is the top-level TrackingDict for this record. Every nested
    TrackingDict and TrackingList holds a reference to it, so a mutation at
    any depth - ``rec["contacts"].append(person)``,
    ``rec["cadence"]["day1"]["body"] = "..."`` - propagates to the same
    dirty set.
    """
    __slots__ = ()

    def _mark(self):
        self._root._dirty.add(self._key)


class _TrackingDict(_TrackingRoot, dict):
    """A dict subclass that marks its root record dirty on mutation.

    Replaces every nested dict and list with a tracking wrapper at
    construction time, so mutations at any depth propagate. The underlying
    dict data IS the record data: ``json.dumps`` reads it directly through
    the C encoder's dict-subclass path, and the output is identical to a
    plain dict because the wrappers subclass dict/list and compare equal.

    THE TRAP THIS PREVENTS: callers do not replace rows, they mutate them
    in place. A tracker that catches only ``__setitem__`` on the top-level
    dict silently stops detecting ``rec["contacts"].append(person)`` and
    ``rec["cadence"]["day1"]["body"] = "..."`` - the edits that carry
    contacts, events and cadence.
    """
    __slots__ = ("_root", "_key", "_dirty")

    def __init__(self, data=None, _root=None, _key=None):
        if isinstance(data, _TrackingDict):
            dict.__init__(self, data)
            self._root = _root or data._root
            self._key = _key if _key is not None else data._key
            return
        dict.__init__(self)
        self._root = self if _root is None else _root
        self._key = _key
        if data:
            for k, v in data.items():
                if isinstance(v, dict) and not isinstance(v, _TrackingDict):
                    v = _TrackingDict(v, _root=self._root, _key=self._key)
                    dict.__setitem__(self, k, v)
                elif isinstance(v, list) and not isinstance(v, _TrackingList):
                    v = _TrackingList(v, _root=self._root, _key=self._key)
                    dict.__setitem__(self, k, v)
                else:
                    dict.__setitem__(self, k, v)

    def _wrap_value(self, value):
        if isinstance(value, dict) and not isinstance(value, _TrackingDict):
            return _TrackingDict(value, _root=self._root, _key=self._key)
        if isinstance(value, list) and not isinstance(value, _TrackingList):
            return _TrackingList(value, _root=self._root, _key=self._key)
        return value

    def __setitem__(self, key, value):
        self._mark()
        dict.__setitem__(self, key, self._wrap_value(value))

    def __delitem__(self, key):
        self._mark()
        dict.__delitem__(self, key)

    def clear(self):
        self._mark()
        dict.clear(self)

    def pop(self, *args):
        self._mark()
        return dict.pop(self, *args)

    def popitem(self):
        self._mark()
        return dict.popitem(self)

    def setdefault(self, key, default=None):
        if key not in self:
            self._mark()
            wrapped = self._wrap_value(default)
            dict.__setitem__(self, key, wrapped)
            return wrapped
        return self[key]

    def update(self, *args, **kwargs):
        self._mark()
        if args:
            other = dict(args[0])
            for k, v in other.items():
                dict.__setitem__(self, k, self._wrap_value(v))
        for k, v in kwargs.items():
            dict.__setitem__(self, k, self._wrap_value(v))

    def __ior__(self, other):
        self._mark()
        for k, v in other.items():
            dict.__setitem__(self, k, self._wrap_value(v))
        return self


class _TrackingList(_TrackingRoot, list):
    """A list subclass that marks its root record dirty on mutation.

    Replaces every nested dict and list with a tracking wrapper at
    construction time, so mutations at any depth propagate.
    """
    __slots__ = ("_root", "_key")

    def __init__(self, data=None, _root=None, _key=None):
        if isinstance(data, _TrackingList):
            list.__init__(self, data)
            self._root = _root or data._root
            self._key = _key if _key is not None else data._key
            return
        list.__init__(self)
        self._root = self if _root is None else _root
        self._key = _key
        if data:
            for i, item in enumerate(data):
                if isinstance(item, dict) and not isinstance(item, _TrackingDict):
                    list.append(self, _TrackingDict(item, _root=self._root,
                                                    _key=self._key))
                elif isinstance(item, list) and not isinstance(item, _TrackingList):
                    list.append(self, _TrackingList(item, _root=self._root,
                                                    _key=self._key))
                else:
                    list.append(self, item)

    def _wrap_value(self, value):
        if isinstance(value, dict) and not isinstance(value, _TrackingDict):
            return _TrackingDict(value, _root=self._root, _key=self._key)
        if isinstance(value, list) and not isinstance(value, _TrackingList):
            return _TrackingList(value, _root=self._root, _key=self._key)
        return value

    def __setitem__(self, index, value):
        self._mark()
        list.__setitem__(self, index, self._wrap_value(value))

    def __delitem__(self, index):
        self._mark()
        list.__delitem__(self, index)

    def append(self, value):
        self._mark()
        list.append(self, self._wrap_value(value))

    def extend(self, values):
        self._mark()
        for v in values:
            list.append(self, self._wrap_value(v))

    def insert(self, index, value):
        self._mark()
        list.insert(self, index, self._wrap_value(value))

    def pop(self, *args):
        self._mark()
        return list.pop(self, *args)

    def remove(self, value):
        self._mark()
        list.remove(self, value)

    def reverse(self):
        self._mark()
        list.reverse(self)

    def sort(self, *args, **kwargs):
        self._mark()
        list.sort(self, *args, **kwargs)

    def __iadd__(self, other):
        self._mark()
        for v in other:
            list.append(self, self._wrap_value(v))
        return self


class Snapshot(list):
    """The queue as one reader found it, remembering what each row then was.

    WHY A WRITER HAS TO KNOW WHAT IT CHANGED. `save` replaces the whole file,
    so writing a snapshot back deletes everything that arrived while the
    caller held it and reverts everything that changed underneath it. Merging
    by id alone does not fix that: it keeps the new rows and still reverts the
    changed ones, because nothing distinguishes "this caller edited the row"
    from "this caller is holding a stale copy of a row somebody else edited".

    The baseline is what distinguishes them, and the reader is the only one
    who can record it. It is kept as the row's JSON text, which is what a
    digest would have been built from anyway and, unlike a digest, can still
    answer WHICH field moved.

    Three outcomes, and none of them is a guess:

      the caller never touched the row  -> whatever is on disk now is newer
                                           and is kept whole.
      the caller touched it and nobody
      else did                          -> the caller's row is written.
      both touched it                   -> field by field: a field the caller
                                           changed is the caller's, every
                                           other field is whatever is on disk.
                                           A field both changed is the
                                           caller's, and on the queue the
                                           history and evidence guards still
                                           run over the result.

    That last case is why this is a three-way merge rather than a choice
    between two rows. `interactions.decide` loads the campaign file, runs
    `orchestrator.decide` and writes its snapshot back; a `freeze` written in
    between - the stop button `eligibility` reads to block every step of a
    campaign - lived in a field that caller never looked at, and a whole-row
    write lifted it. The approval it did write is a different field, and both
    can be true.

    A plain `list` keeps the old whole-file semantics, deliberately: a caller
    that built its rows from somewhere other than `load` has no baseline to
    reason from, and inventing one would be a guess. `list` operations that
    return a new object - `+`, slicing, a comprehension - produce a plain list
    and so fall back, which is the safe direction.

    `key` because the campaign file is the same file-shaped state with the
    same hazard and a different id field, and `campaigns.save` erasing a
    freeze is the same bug as a checkpoint erasing a drop.
    """

    def __init__(self, rows, key="id"):
        self.key = key
        self._serialised = None
        self._dirty = set()
        self._by_id = {}
        self._keyless_count = 0
        wrapped = []
        for row in rows:
            if isinstance(row, dict) and not isinstance(row, _TrackingDict):
                if key not in row:
                    self._keyless_count += 1
                    wrapped.append(row)
                    continue
                td = _TrackingDict(row, _key=row[key])
                # The root TrackingDict carries _dirty so nested wrappers
                # can reach it via self._root._dirty. It IS the Snapshot's
                # dirty set - same object, not a copy.
                td._dirty = self._dirty
                wrapped.append(td)
                self._by_id[row[key]] = td
            else:
                if not (isinstance(row, dict) and key in row):
                    self._keyless_count += 1
                wrapped.append(row)
        super().__init__(wrapped)
        self.rebase()

    def append(self, row):
        if isinstance(row, dict) and self.key not in row:
            self._keyless_count += 1
        elif not isinstance(row, dict):
            self._keyless_count += 1
        if isinstance(row, dict) and not isinstance(row, _TrackingDict) \
                and self.key in row:
            td = _TrackingDict(row, _key=row[self.key])
            td._dirty = self._dirty
            self._by_id[row[self.key]] = td
            # AN APPENDED ROW IS DIRTY BY DEFINITION, AND SAYING SO IS NOT
            # OPTIONAL NOW THAT `merge_onto` READS `_dirty` RATHER THAN
            # RE-DERIVING IT.
            #
            # Before this task the edit set was recomputed by serialising
            # every row and comparing to the baseline, and a row with NO
            # baseline fell out of that comparison as changed for free. With
            # an explicit dirty set it does not: the row is wrapped, indexed
            # and appended, and then never written, because nothing put its
            # id in `_dirty`.
            #
            # `test_a_stop_survives_a_concurrent_run.test_adding_a_record_
            # passes` caught it - a record added to the snapshot simply did
            # not reach the disk. That is silent record loss, which is the
            # exact failure class `Snapshot` exists to prevent, arriving
            # through the optimisation meant to make it cheaper.
            self._dirty.add(row[self.key])
            list.append(self, td)
        else:
            list.append(self, row)

    def __iter__(self):
        for i in range(len(self)):
            yield list.__getitem__(self, i)

    def rebase(self):
        """The baseline becomes what these rows are now. Called after a write.

        A BATCH CHECKPOINTS MANY TIMES AND THE BASELINE HAS TO MOVE WITH IT.
        Without this the baseline stays at the opening read for the whole run,
        so every checkpoint re-asserts every field the caller has EVER
        touched, not the ones it has touched since the last one. Reproduced:
        the caller writes `state: enriched` at one checkpoint, another process
        then runs `drop(rid, "competitor - do not contact")`, and at the next
        checkpoint the caller wins `state` again on the strength of an edit it
        already persisted - landing the row as `state: enriched` with
        `drop_reason` still set. `validate` returns no problems, `run.TERMINAL`
        stops excluding it, and the record is worked again. That is the drop
        reversion this class exists to prevent, re-entering through the field
        the enrich stage always writes, with a window of the whole batch
        instead of one interval.

        So after a successful write the caller's rows ARE the baseline: they
        are what it just put on disk for every field it owns.

        `merge_onto` has just serialised every one of these rows to decide
        which had changed, and nothing mutates them between there and here, so
        it hands the result over rather than making this do it again. Two full
        serialisations of the queue per save was 18-28% of the cost of one,
        and `save` is 98% of the wall time of a resumed run. Measured on a
        5,000-record estate: 0.99s to 0.67s.
        """
        handed_over, self._serialised = self._serialised, None
        if handed_over is not None:
            # TASK-261: handover contains only dirty rows' serialised forms.
            # Update the baseline for those rows; clean rows' entries are
            # already correct (nothing changed since the last rebase).
            self.baseline.update(handed_over)
            self._dirty.clear()
            return
        self.baseline = {row[self.key]: _frozen(row) for row in self
                         if isinstance(row, dict) and self.key in row}
        self._dirty.clear()

    def _base_row(self, rec):
        """The row as it was read, or None if this caller introduced it."""
        known = self.baseline.get(rec.get(self.key))
        return None if known is None else json.loads(known)

    def unchanged(self, rec):
        """Is this row still exactly as it was read?

        A fast path, not a fourth rule: `_merge_row` reaches the same answer
        for an untouched row, because no field of it differs from the
        baseline and the merge then yields the disk row unchanged. It is here
        because a checkpoint every five records over a long batch walks the
        whole file each time, and most of the file is untouched.
        """
        rid = rec.get(self.key)
        if rid not in self._dirty:
            return self.baseline.get(rid) is not None
        known = self.baseline.get(rid)
        return known is not None and known == _frozen(rec)

    def _merge_row(self, rec, on_disk_row):
        """One row, three ways: what it was, what we made it, what it is now."""
        base = self._base_row(rec)
        if base is None or on_disk_row is None:
            return rec                       # nothing to merge against
        if _frozen(on_disk_row) == self.baseline.get(rec.get(self.key)):
            return rec                       # nobody else touched it
        merged = dict(on_disk_row)
        for field in set(rec) | set(base):
            before = base.get(field, MISSING)
            mine = rec.get(field, MISSING)
            if mine is before or mine == before:
                continue                     # we left this field alone
            if mine is MISSING:
                merged.pop(field, None)      # we removed it on purpose
            else:
                merged[field] = mine
        return merged

    def merge_onto(self, on_disk):
        """The rows to write: what is on disk, with this caller's edits applied.

        Order follows the disk, because that is the order every other reader
        sees and a checkpoint has no business reshuffling the file. Rows this
        caller added - present here with no baseline - go on the end, which is
        where an append would have put them.
        """
        # A ROW WITH NO KEY CANNOT BE MERGED, SO IT IS REFUSED RATHER THAN
        # SKIPPED. Counted at construction time, not here, to avoid an O(N)
        # walk on every checkpoint.
        if self._keyless_count:
            raise ValueError(
                f"{self._keyless_count} row(s) carry no {self.key!r} and "
                f"cannot be merged onto what is on disk. Nothing was written.")
        # TASK-261: only serialise dirty rows, not every row. The dirty set
        # tracks which records were mutated in place (including nested
        # mutations to contacts, events, cadence, log). Using _by_id makes
        # this O(|dirty|) rather than O(N), which is the whole point.
        frozen_dirty = {}
        edits = {}
        for rid in self._dirty:
            row = self._by_id.get(rid)
            if row is not None:
                frozen_dirty[rid] = _frozen(row)
                edits[rid] = row
        self._serialised = frozen_dirty
        out = []
        for row in on_disk:
            if not (isinstance(row, dict) and self.key in row):
                out.append(row)
                continue
            mine = edits.pop(row[self.key], None)
            out.append(row if mine is None else self._merge_row(mine, row))
        return out + list(edits.values())


def journalling():
    """Is the delta checkpoint path on? OFF unless QUEUE_JOURNAL says so.

    Default off because this changes how the only file holding real client
    state is written. On, `save` appends the rows it actually changed instead
    of rewriting every record, and `load` replays those deltas over the base.
    Every guard runs exactly as before - the read, the digest check, the
    three-way merge, `refuse_evidence_loss` and `refuse_history_loss` are all
    unchanged and still see the FULL merged set. Only the write narrows.

    So this halves the work rather than fixing it: 4.4 GB of writes at 5,000
    records becomes a few megabytes, while the O(N) READ per checkpoint
    stays. That read needs an index to fix and an index is a bigger change
    than this one. Writes are the expensive half and the only half that costs
    write endurance.
    """
    return (os.environ.get("QUEUE_JOURNAL") or "").strip().lower() in (
        "1", "true", "yes", "on")


def _current_records():
    """The queue as it actually is: the base file with any deltas replayed.

    One definition, used by both `load` and `save`, because a reader and a
    writer disagreeing about what is on disk is the whole hazard.

    Routes based on backend():
      jsonl    reads from queue.jsonl (with journal replay if enabled)
      shadow   reads from queue.jsonl (canonical)
      sqlite   reads from the SQLite database
    """
    mode = backend()
    if mode == "sqlite":
        from . import sqlitestore
        import sqlite3
        path = db_path()
        if not os.path.exists(path):
            return []
        conn = sqlite3.connect(path)
        try:
            return sqlitestore.read_all(conn)
        finally:
            conn.close()
    # jsonl and shadow both read from JSONL
    rows = read_jsonl(queue_path())
    if journalling():
        from . import queuejournal
        rows, _applied, _torn = queuejournal.replay(rows, queue_path())
    return rows


def load():
    """The queue, with any journalled deltas replayed over the base file."""
    recs = Snapshot(_current_records())
    mode = backend()
    if mode == "sqlite":
        from . import sqlitestore
        import sqlite3
        path = db_path()
        if os.path.exists(path):
            conn = sqlite3.connect(path)
            try:
                recs._baseline_rev = sqlitestore.revision(conn)
            finally:
                conn.close()
    return recs


def _incremental_guard_input(snapshot, full_read_fn):
    """For sqlite backend: return (guard_old, on_disk_for_merge, path, rows).

    TASK-260. If the snapshot has a valid baseline and the backend is sqlite,
    use the rev cursor to read only the records the guards need: caller-touched
    records plus records that changed on disk since the baseline.

    The key insight: we do NOT need a full read. The caller-touched records
    are in the Snapshot (in memory). The disk-changed records come from
    read_changed_since. The merge and guards only need these records.

    Falls back to full read if:
    - Not a Snapshot (no baseline)
    - Backend is not sqlite
    - Cursor is missing/stale/backwards

    Returns (guard_old, on_disk_for_merge, path, rows_read). `guard_new`
    is NOT returned: it is the MERGED result and only `save` has that.
    """
    mode = backend()
    if mode != "sqlite":
        on_disk = full_read_fn()
        return on_disk, on_disk, "full", len(on_disk)

    if not isinstance(snapshot, Snapshot) or not hasattr(snapshot, "baseline"):
        on_disk = full_read_fn()
        return on_disk, on_disk, "full", len(on_disk)

    from . import sqlitestore
    import sqlite3
    path = db_path()
    if not os.path.exists(path):
        on_disk = full_read_fn()
        return on_disk, on_disk, "full", len(on_disk)

    conn = sqlite3.connect(path)
    try:
        current_rev = sqlitestore.revision(conn)
        baseline_rev = getattr(snapshot, "_baseline_rev", None)

        if baseline_rev is None or baseline_rev > current_rev or baseline_rev < 0:
            on_disk = full_read_fn()
            return on_disk, on_disk, "full", len(on_disk)

        changed = sqlitestore.read_changed_since(conn, baseline_rev)
        changed_by_id = {r.get("id"): r for r in changed}

        caller_touched = {}
        for rid in snapshot._dirty:
            rec = snapshot._by_id.get(rid)
            if rec is not None:
                caller_touched[rid] = rec

        needed_ids = set(caller_touched) | set(changed_by_id)
        if not needed_ids:
            return [], [], "incremental", 0

        guard_old = []
        for rid in needed_ids:
            old_rec = changed_by_id.get(rid)
            if old_rec is None:
                for r in snapshot:
                    if isinstance(r, dict) and r.get("id") == rid:
                        old_rec = json.loads(snapshot.baseline.get(rid, "null"))
                        break
            if old_rec is not None:
                guard_old.append(old_rec)

        # NO `guard_new` IS BUILT HERE, deliberately. This loop used to set it
        # from `caller_touched[rid]` - the caller's RAW row - and that is the
        # stale pre-merge copy. For a record BOTH the caller and a second
        # writer touched, the merge keeps the second writer's field (the
        # caller did not change it) while the raw row does not have it, so
        # `refuse_history_loss` read a stop as lifted and raised on a write
        # the merge was about to make safe. Two tests in
        # `test_a_stop_survives_a_concurrent_run` caught it.
        #
        # The merged result IS the narrowed set - `merge_onto` appends only
        # rows the caller actually edited - so `save` passes `recs` straight
        # to the guards on this path exactly as it does on the whole-file one.
        on_disk_narrowed = guard_old
        return guard_old, on_disk_narrowed, "incremental", len(changed)
    finally:
        conn.close()


# ------------------------------------------------- the second barrier
#
# A test that forgets to isolate the store used to write into the real
# `work/` directory. `tests/base.py::ProviderTest` did exactly that, and
# `store.save` replaces the whole file rather than appending, so a fixture
# estate silently overwrote a client's. The comment on STATE_OVERRIDES above
# had already named the risk - "a test that writes into the developer's queue
# is the kind of thing discovered by losing a batch" - and it was.
#
# Fixing the base class removes the one known way in. This removes the class.
# The isolation a test sets up is the first barrier; this is the second, and
# it does not depend on any test remembering anything.

PRODUCTION_WORK = os.path.join(ROOT, "work")


class ProductionStateUnderTest(RuntimeError):
    """A test tried to write the real client state directory.

    Raised rather than redirected: silently writing somewhere else would make
    the test pass while testing a different file, which is its own defect. The
    fix is for the test to isolate the store - `store.use_directory(tmp)` -
    not for the store to guess where the test meant.
    """


def under_test():
    """Is this process a test run?

    `unittest` in sys.modules rather than an environment marker a harness has
    to remember to set: the failure being prevented is a forgotten setup step,
    so the detection may not have a setup step of its own. The production
    entry points - `python -m src.web`, `python -m src.run` - never import it.
    """
    return "unittest" in sys.modules


def refuse_production_write(path):
    """Called before every state write, by every writer into `work/`.

    Public because `work/` holds twenty-odd state files and only one of them
    is the queue. `write_jsonl` covers everything routed through this module;
    `mx`, `poller` and `replywatch` build their own temp-file-and-replace and
    so have to ask for themselves. A writer that does not call this is outside
    the barrier, which is how a test wrote fixtures into the real
    `replywatch.json` and sixteen draft rows into the real
    `report-drafts.jsonl` while the queue sat safely behind the guard.

    Called before `os.makedirs`, not after: the refusal must land before any
    filesystem mutation, including creating the directory.
    """
    if not under_test():
        return
    target = os.path.abspath(path)
    if target == PRODUCTION_WORK or target.startswith(PRODUCTION_WORK + os.sep):
        raise ProductionStateUnderTest(
            "a test tried to write real client state at %s. Isolate the "
            "store first: store.use_directory(tempfile.mkdtemp()). See "
            "tests/base.py, which does this for every ProviderTest." % target)


def _write(recs):
    """The atomic write itself. Callers hold the lock."""
    path = queue_path()
    refuse_production_write(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        for r in recs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    os.replace(tmp, path)


def _write_delta(on_disk, recs):
    """Append only the rows that differ from what is on disk. Caller locked.

    `recs` is the fully merged result, so the comparison is exact: a row whose
    serialised form matches the disk row is not written at all, and a row the
    disk has never seen is written whole.

    COMPACTION HAPPENS HERE, under the same lock, and the ORDER MATTERS - base
    first, then drop the journal. Reversed, a crash between the two loses every
    delta since the last base, silently. `queuejournal.compact` owns that
    ordering; this just decides when.
    """
    from . import queuejournal
    path = queue_path()
    # THE BARRIER COVERS THE SIDECAR TOO. `_write` asks it and this path does
    # not go through `_write`, so without this a test that forgot to isolate
    # the store would write `queue.jsonl.journal` into the real `work/`
    # directory - the exact failure `refuse_production_write` exists to stop,
    # arriving through a file that did not exist when it was written.
    refuse_production_write(path)
    # BOOTSTRAP. With no base file there is nothing to append a delta ONTO,
    # and writing one would leave `queue.jsonl` absent while the state lived
    # entirely in a sidecar - which every other reader of this repo, and
    # every backup of it, would read as an empty estate.
    if not os.path.exists(path):
        _write(recs)
        return
    by_id = {r.get("id"): r for r in on_disk
             if isinstance(r, dict) and "id" in r}
    changed = [r for r in recs
               if isinstance(r, dict) and "id" in r
               and _frozen(r) != (_frozen(by_id[r["id"]])
                                  if r["id"] in by_id else None)]
    if changed:
        queuejournal.append(path, changed, digest(path), at=now(), locked=True)
    if queuejournal.should_compact(path):
        queuejournal.compact(path, _write, locked=True)


# ------------------------------------------------- the shadow ledger
#
# Shadow mode writes to both JSONL and SQLite, reads from JSONL, and diffs
# the SQLite read against the JSONL read. Divergences are written to a ledger
# file, not raised - unless SHADOW_STRICT=1 is set.
#
# The ledger records WRITES OBSERVED as well as divergences, so a promotion
# check that sees zero of both refuses rather than passing vacuously.

def _shadow_ledger_path():
    """Where the shadow diff ledger lives."""
    return os.path.join(os.path.dirname(queue_path()), "store-shadow-diff.jsonl")


def _shadow_log(entry):
    """Append one entry to the shadow diff ledger."""
    path = _shadow_ledger_path()
    refuse_production_write(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _shadow_diff_and_log(jsonl_recs, sqlite_recs):
    """Compare JSONL and SQLite record sets, log divergences.

    Returns a list of divergence entries. Does NOT raise unless SHADOW_STRICT=1.

    Only flags records that exist in BOTH stores with different values. A record
    present in JSONL but missing from SQLite is not a divergence - it's expected
    on first write or after a migration. A record in SQLite but not in JSONL
    would be a divergence (SQLite has something JSONL doesn't), but that's
    unlikely in practice since JSONL is canonical.
    """
    divergences = []
    jsonl_by_id = {r["id"]: r for r in jsonl_recs if isinstance(r, dict) and "id" in r}
    sqlite_by_id = {r["id"]: r for r in sqlite_recs if isinstance(r, dict) and "id" in r}

    # Only compare records that exist in BOTH stores
    for rid in set(jsonl_by_id) & set(sqlite_by_id):
        j_rec = jsonl_by_id[rid]
        s_rec = sqlite_by_id[rid]
        # Compare field by field
        for field in set(j_rec) | set(s_rec):
            j_val = _frozen(j_rec.get(field))
            s_val = _frozen(s_rec.get(field))
            if j_val != s_val:
                divergences.append({
                    "type": "divergence",
                    "at": now(),
                    "id": rid,
                    "field": field,
                    "jsonl": j_rec.get(field),
                    "sqlite": s_rec.get(field)
                })

    # Log divergences
    for div in divergences:
        _shadow_log(div)

    # Log the write itself
    _shadow_log({"type": "write", "at": now()})

    # Raise if SHADOW_STRICT=1
    if divergences and (os.environ.get("SHADOW_STRICT") or "").strip() in ("1", "true", "yes", "on"):
        raise ShadowDivergence(
            f"shadow mode detected {len(divergences)} divergence(s) between "
            f"JSONL and SQLite. First: {divergences[0]['id']}.{divergences[0]['field']}")

    return divergences


def check_promotion_readiness(ledger_path=None):
    """Check whether the shadow ledger is clean enough to promote to sqlite.

    Returns a dict with:
      ready: bool
      writes: int
      divergences: int
      reason: str (if not ready)

    Refuses if the ledger has zero rows AND zero observed writes - an empty
    ledger because nothing ran is the vacuous pass.
    """
    path = ledger_path or _shadow_ledger_path()
    if not os.path.exists(path):
        return {"ready": False, "writes": 0, "divergences": 0,
                "reason": "no writes observed: the ledger does not exist"}

    entries = read_jsonl(path)
    writes = sum(1 for e in entries if e.get("type") == "write")
    divergences = sum(1 for e in entries if e.get("type") == "divergence")

    if writes == 0:
        return {"ready": False, "writes": 0, "divergences": divergences,
                "reason": "no writes observed: the ledger is empty or carries only divergences"}
    if divergences > 0:
        return {"ready": False, "writes": writes, "divergences": divergences,
                "reason": f"{divergences} divergence(s) detected"}
    return {"ready": True, "writes": writes, "divergences": 0, "reason": ""}


class EvidenceLost(RuntimeError):
    """A write would have deleted paid verification evidence.

    Raised rather than repaired: the writer is holding a contact list that has
    already lost the rows, and guessing which ones to put back is how a
    fabricated provider answer gets into the record.
    """


def _evidence_index(recs):
    """Every stored provider answer, per record.

    Contacts and excluded together: an exclusion moves somebody out of the
    selection, it does not un-buy what was spent on them.

    Counted per (address, provider, status), and deliberately not keyed on
    `at`. The timestamp is provenance, not identity, and keying on it made the
    guard fire on writes that lost nothing: `verification.result` stamps
    `store.now()`, so rebuilding the same answer a second later produced a
    different key and the original read as deleted. That is a false positive on
    a safety guard, which is worse than it sounds - it appears intermittently,
    it blocks a legitimate write, and the quickest way to make it stop is to
    weaken the guard.

    A count rather than a set, so the strictness that mattered survives: two
    answers from one provider collapsing into one is still a loss, even though
    both share a key.
    """
    from . import verification

    out = {}
    for rec in recs or []:
        for contact in ((rec.get("contacts") or [])
                        + (rec.get("excluded") or [])):
            for entry in (contact.get("verification") or {}).get("evidence") or []:
                out.setdefault(rec.get("id"), collections.Counter())[
                    (verification.normalise_address(entry.get("email")),
                     entry.get("provider"), entry.get("status"))] += 1
    return out


def refuse_evidence_loss(old_recs, new_recs):
    """Refuse a write that drops a provider answer somebody paid for.

    `verification.apply` already keeps evidence append-only, but it can only
    defend the field. It never sees a contact dict being replaced wholesale -
    which is what happened when a discovery run re-minted three people and the
    evidence-bearing dicts went with them. This is the layer that catches
    that, because every writer goes through `store`.

    A record absent from the new set is deliberately not flagged. Removing a
    record is governed by "never delete a queue record, drop it with a
    reason", which is a different rule with a different guard.
    """
    before, after = _evidence_index(old_recs), _evidence_index(new_recs)
    present = {r.get("id") for r in new_recs or []}
    lost = {}
    for rid, rows in before.items():
        if rid not in present:
            continue
        kept = after.get(rid, collections.Counter())
        gone = sorted(k for k, n in rows.items() if n > kept.get(k, 0))
        if gone:
            lost[rid] = gone
    if lost:
        raise EvidenceLost(
            "this write would delete paid verification evidence: "
            + "; ".join(
                "%s: %s" % (rid, ", ".join(
                    "%s %s %s" % (address, provider, status)
                    for address, provider, status in rows))
                for rid, rows in sorted(lost.items())))
    return True


# Every field that says this person must not be contacted. Written by
# `accountpolicy` when a reply is honoured, and cleared by nothing in this
# repository - which is what lets the guard below be strict.
CONTACT_STOPS = ("paused", "stopped", "unsubscribed", "suppressed")


def _history_index(recs):
    """Per record: WHICH events it holds, and which stops are set.

    A COUNT WAS NOT ENOUGH, and the gap was the ordinary case rather than an
    exotic one. The rule below fires only when the new snapshot holds FEWER
    events - but a stale worker is a worker doing work, and it appends events
    of its own (`draft_generated`, `verification_result`, `push_prepared`) to
    the copy it loaded. One append against one lost reply is a tie, and a tie
    passed. Reproduced on 2026-09-11: a confirmed touch and a reply were both
    erased by a snapshot with an equal event count, after which
    `push.already_pushed` answered False and the sequence continued.

    So events are identified, not counted. `events.record` already mints a
    stable `id` for every event and refuses to append a duplicate, so the ids
    are the natural identity - on the real queue, 5,194 events carry one and
    none is duplicated. Events without an id are still counted, so a record
    written before ids existed keeps the protection it had.
    """
    index = {}
    for rec in recs or []:
        stops = set()
        if rec.get("paused"):
            stops.add("account paused")
        if rec.get("suppression"):
            stops.add("account suppressed")
        for contact in ((rec.get("contacts") or [])
                        + (rec.get("excluded") or [])):
            for flag in CONTACT_STOPS:
                if contact.get(flag):
                    stops.add(f"{contact.get('key')} {flag}")
        named, unnamed = set(), 0
        for entry in rec.get("events") or []:
            if isinstance(entry, dict) and entry.get("id"):
                named.add(entry["id"])
            else:
                unnamed += 1
        index[rec.get("id")] = (named, unnamed, stops)
    return index


class HistoryLost(RuntimeError):
    """This write would forget a reply, or lift a stop nobody lifted."""


def refuse_history_loss(old_recs, new_recs):
    """Refuse a write that drops an event or clears a do-not-contact flag.

    THE DEFECT THIS CLOSES WAS ALREADY WRITTEN DOWN, in `save`'s own docstring,
    and the remedy it prescribed was caller-side: pass `expect_digest`. One
    caller does. The three that hold a whole-queue snapshot across minutes of
    provider I/O - `run.checkpoint`, `run`'s final save and `enrich.run` - do
    not, and they are exactly the callers the docstring warns about.

    Reproduced on 2026-09-11 with nothing crashing. A prospect replied "please
    remove us from your list"; the reply was persisted correctly and
    `eligibility.decide` answered `blocked:contact_paused`. A concurrent run
    then checkpointed the snapshot it had loaded before the reply, and the
    events and the pause were gone. `eligibility` answered
    `held:draft_not_approved` - an approval gate, not a stop - so approving
    that copy would have sent the next step to somebody who asked to be
    removed. `refuse_evidence_loss` had nothing to object to, because the
    verification evidence was present in both copies.

    So the guard moves to the boundary every writer already crosses, rather
    than resting on a discipline that demonstrably was not followed. It also
    covers the next caller, which is the part a call-site fix cannot do.

    Strict, with no opt-out, because nothing in this repository clears any of
    these: `accountpolicy` sets them and `resume_campaign` lifts a CAMPAIGN
    pause in the campaign file instead. If a deliberate lift is ever wanted, it
    should have to argue with this function rather than slip past it.
    """
    before, after = _history_index(old_recs), _history_index(new_recs)
    lost = {}
    for rid, (named_before, unnamed_before, stops_before) in before.items():
        if rid not in after:
            continue                      # removal is a different rule
        named_after, unnamed_after, stops_after = after[rid]
        why = []
        dropped = named_before - named_after
        if dropped:
            why.append(f"{len(dropped)} event(s) dropped: "
                       + ", ".join(sorted(dropped)[:3]))
        if unnamed_after < unnamed_before:
            why.append(f"{unnamed_before - unnamed_after} unidentified "
                       f"event(s) dropped")
        gone = sorted(stops_before - stops_after)
        if gone:
            why.append("stop lifted: " + ", ".join(gone))
        if why:
            lost[rid] = why
    if lost:
        raise HistoryLost(
            "this write would forget what happened or lift a stop nobody "
            "lifted: "
            + "; ".join(f"{rid}: {', '.join(why)}"
                        for rid, why in sorted(lost.items()))
            + ". Reload and re-apply rather than writing a stale snapshot "
              "back over it.")
    return True


class QueueChanged(RuntimeError):
    """The queue moved under a read-modify-write. Nothing was written.

    Raised rather than clobbering. `transaction()` is the right answer for
    anything that can hold the lock throughout; this exists for the callers
    that cannot, because they do network I/O between reading and writing.
    """


def digest(path=None):
    """A cheap fingerprint of the queue as it is on disk right now.

    Routes based on backend():
      jsonl/shadow  content hash of the queue file (plus journal if enabled)
      sqlite        the revision counter from meta.revision

    On SQLite, hashing the file's bytes is wrong: WAL, page reuse and vacuum
    all change bytes without changing state, and a checkpoint can change state
    without changing the main file at all. The revision counter is STRICTER
    than a content hash: a record changed and changed back now REFUSES where
    a content hash passed. That is the safe direction - `expect_digest` exists
    to refuse a read-modify-write that raced, and the caller is already told
    to reload and re-apply.
    """
    mode = backend()
    if mode == "sqlite":
        from . import sqlitestore
        import sqlite3
        db = path or db_path()
        if not os.path.exists(db):
            return "absent"
        conn = sqlite3.connect(db)
        try:
            return str(sqlitestore.revision(conn))
        finally:
            conn.close()

    # jsonl and shadow both use content hash
    import hashlib
    path = path or queue_path()
    if not os.path.exists(path):
        return "absent"
    digestor = hashlib.sha256()
    with open(path, "rb") as handle:
        digestor.update(handle.read())
    # THE JOURNAL IS PART OF "AS IT IS ON DISK RIGHT NOW".
    #
    # With journalling on, a checkpoint deliberately leaves the base file
    # untouched, so a digest of the base alone would be IDENTICAL before and
    # after somebody else's write. `expect_digest` exists to catch exactly
    # that write, and hashing only the base would have turned the
    # optimistic-concurrency refusal into a no-op that still looked present.
    if journalling():
        from . import queuejournal
        sidecar = queuejournal.path_for(path)
        if os.path.exists(sidecar):
            with open(sidecar, "rb") as handle:
                digestor.update(handle.read())
    return digestor.hexdigest()[:32]


def _write_sqlite(recs):
    """Write records to the SQLite database. Caller holds the lock.

    Used by sqlite backend mode. The database is opened, records are written,
    and the connection is closed.
    """
    from . import sqlitestore
    import sqlite3
    path = db_path()
    refuse_production_write(path)
    for sidecar in (path + "-wal", path + "-shm"):
        refuse_production_write(sidecar)
    conn = sqlitestore.open_db(path)
    try:
        sqlitestore.write_changed(conn, recs)
    finally:
        conn.close()


def _write_sqlite_shadow(recs, on_disk):
    """Write records to SQLite in shadow mode, then diff and log.

    Shadow mode: JSONL is canonical. The SQLite write is an observer. Before
    writing, we read from SQLite and diff against what we're about to write
    to JSONL. Divergences are logged, not raised (unless SHADOW_STRICT=1).
    Then we write to SQLite.
    """
    from . import sqlitestore
    import sqlite3
    path = db_path()
    refuse_production_write(path)
    for sidecar in (path + "-wal", path + "-shm"):
        refuse_production_write(sidecar)
    conn = sqlitestore.open_db(path)
    try:
        # Read from SQLite BEFORE writing, to detect divergences
        sqlite_recs = sqlitestore.read_all(conn)
        # Compare what's in SQLite against what we're about to write to JSONL
        _shadow_diff_and_log(recs, sqlite_recs)
        # Now write to SQLite
        sqlitestore.write_changed(conn, recs)
    finally:
        conn.close()


def save(recs, timeout=None, expect_digest=None, allow_history_loss=False):
    """Atomic whole-file write, under the lock. A crash leaves the old queue.

    `expect_digest` MAKES THIS SAFE FOR A READ-MODIFY-WRITE, and without it
    this function is not.

    The lock is held only for the write. `transaction()`'s docstring already
    says why that is not enough - it "cannot protect a read-modify-write against
    a second process" - and the most important caller in the system was doing
    exactly that: `inbound.ingest` loads the queue, applies a reply, and saves.
    A pipeline run loading and saving across the same window silently erased the
    reply, its pause and its event, and `refuse_evidence_loss` does not catch it
    because it indexes verification evidence rather than events or pauses. A
    positive reply that paused an account was revertible by any concurrent run,
    and every later gate would then read a record that looked contactable.

    So a caller that cannot hold the lock throughout passes the digest it read,
    and a change since then is a refusal rather than a clobber. Callers that can
    hold the lock should use `transaction()` instead and not need this.

    AND WHEN `recs` CAME FROM `load`, THE WRITE IS MERGED RATHER THAN TOTAL.
    `expect_digest` is opt-in and the batch runner never passed it, so a run
    that walks 500 records across minutes of provider I/O wrote its opening
    snapshot back at every checkpoint. Reproduced on 2026-09-12 in an isolated
    estate, two processes, nothing crashing: a record ingested mid-batch was
    gone after the next checkpoint along with its reply and its unsubscribe, a
    `drop(rid, "competitor - do not contact")` came back as `state: queued`
    with `drop_reason: None`, and three decision-makers bought mid-batch were
    erased. Neither guard objected - both skip records absent from the new
    set, and `refuse_evidence_loss` indexes verification evidence, so a
    purchase not yet verified is unprotected.

    Refusing instead would be the wrong trade for this caller: a checkpoint
    that raises costs the whole run, which is the loss `CHECKPOINT_EVERY` was
    chosen to bound. So `Snapshot` carries what each row was when it was read,
    and the merge is exact rather than heuristic:

      absent from `recs`   -> kept. It arrived after this caller read, or this
                              caller no longer holds it. Removal is a
                              different rule with a different guard.
      unchanged since read -> the disk row is kept. This caller did not touch
                              it, so a change to it is somebody else's and
                              newer.
      changed by us alone  -> written.
      changed by both      -> merged field by field, this caller winning only
                              the fields it actually changed. See `Snapshot`.

    What that leaves is two writers editing the SAME FIELD of the same record,
    where the last write wins. That is the case the guards below exist for and
    the case `expect_digest` exists for; it is not made worse here, and it is
    a far narrower window than the whole file.
    """
    with lock(timeout):
        # `on_disk` MUST BE THE CURRENT STATE, NOT THE BASE FILE.
        #
        # Everything below depends on it: the digest check, the three-way
        # merge, and both loss guards. With journalling on, the base file is
        # deliberately NOT rewritten, so reading it alone would hand all four
        # of them a stale picture - and a guard comparing against stale state
        # is not a guard. `test_on_still_refuses_to_drop_paid_evidence`
        # caught exactly that: EvidenceLost stopped being raised, silently,
        # because the evidence it was protecting lived in the journal.
        #
        # TASK-260: on sqlite backend with a valid Snapshot baseline, the
        # merge AND the guards run on a narrowed input (caller-touched ∪
        # disk-changed). Records outside this set have old == new, so the
        # merge and guards are vacuous for them.
        snapshot = recs if isinstance(recs, Snapshot) else None
        mode = backend()
        if mode == "sqlite" and snapshot is not None:
            guard_old, on_disk, _path, _rows = \
                _incremental_guard_input(snapshot, _current_records)
        else:
            on_disk = _current_records()
            guard_old = on_disk
        if expect_digest is not None and digest() != expect_digest:
            raise QueueChanged(
                "the queue changed while this work was in progress, so writing "
                "it back would discard whatever changed. Nothing was written; "
                "reload and re-apply.")
        if snapshot is not None:
            recs = snapshot.merge_onto(on_disk)
        # THE GUARDS SEE THE MERGED RESULT, NEVER THE CALLER'S SNAPSHOT.
        #
        # TASK-260 set `guard_new = list(snapshot)` here, which is the stale
        # pre-merge copy. That is a FALSE POSITIVE FACTORY on the safety path:
        # a concurrent run sets a stop, the caller's snapshot predates it, and
        # `refuse_history_loss` sees the stop present in `on_disk` and absent
        # in the snapshot - so it raises `HistoryLost` on a write that the
        # merge was about to make perfectly safe. Six tests in
        # `test_a_stop_survives_a_concurrent_run` and `test_approve` caught it.
        #
        # `_evidence_index`'s docstring already names why this is worse than
        # it sounds: "a false positive on a safety guard ... appears
        # intermittently, it blocks a legitimate write, and the quickest way to
        # make it stop is to weaken the guard."
        #
        # The merged result is what is about to be written, so it is the only
        # thing worth asking the guards about. The sqlite branch above is
        # different only in that it narrows BOTH sides consistently.
        guard_new = recs
        refuse_evidence_loss(guard_old, guard_new)
        # `allow_history_loss` IS FOR TEST CLEANUP AND NOTHING ELSE. A test
        # that adds an event to a shared estate has to take it back out again,
        # and that is a legitimate rewrite of history by a caller who knows it
        # is doing so. Nothing in `src/` may pass it, and
        # `tests/test_invariants.py` fails the build if anything does - an
        # escape hatch nobody is allowed to reach for in production is a
        # different thing from a guard with a hole in it.
        if not allow_history_loss:
            refuse_history_loss(guard_old, guard_new)
        # THE ONLY THING THE BACKEND CHANGES IS WHICH BYTES GET WRITTEN.
        # Everything above this line - the read, the digest check, the
        # three-way merge, and both loss guards - has already run over the
        # FULL merged set, exactly as it does on the whole-file path.
        if mode == "sqlite":
            _write_sqlite(recs)
        elif mode == "shadow":
            # JSONL is canonical. Write to JSONL first, then SQLite, then diff.
            if journalling():
                _write_delta(on_disk, recs)
            else:
                _write(recs)
            _write_sqlite_shadow(recs, on_disk)
        else:
            # jsonl
            if journalling():
                _write_delta(on_disk, recs)
            else:
                _write(recs)
        # Only after the write, and only if it happened: a refused checkpoint
        # must leave the caller still holding unpersisted edits, or the next
        # one would treat them as already on disk and stop re-asserting them.
        if snapshot is not None:
            snapshot.rebase()
            if mode == "sqlite":
                from . import sqlitestore
                import sqlite3
                path = db_path()
                if os.path.exists(path):
                    conn = sqlite3.connect(path)
                    try:
                        snapshot._baseline_rev = sqlitestore.revision(conn)
                    finally:
                        conn.close()


def new_record(id, lane, client, company, domain, context="", signal=""):
    """The record skeleton. Field shape lives here and nowhere else."""
    if lane not in LANES:
        raise ValueError(f"unknown lane: {lane}")
    return {
        "id": id,
        "lane": lane,
        "client": client,
        "company": company,
        "domain": domain,
        "context": context,
        "signal": signal,
        "state": "queued",
        "drop_reason": None,
        "company_facts": {},
        "contacts": [],
        "excluded": [],
        "diagnosis": None,
        "hook": None,
        "sizing": None,
        "cadence": {},
        "log": [],
    }


REQUIRED = ("id", "lane", "client", "company", "domain", "state", "drop_reason", "log")


def validate(rec):
    """Return a list of problems. Empty list means the record is well formed."""
    problems = []
    for key in REQUIRED:
        if key not in rec:
            problems.append(f"missing field: {key}")
    client = rec.get("client")
    if not client or not isinstance(client, str) \
            or not re.match(r"^[a-z0-9][a-z0-9_-]{0,63}$", client):
        problems.append(
            f"client must be a non-empty lowercase slug, got {client!r}")
    if rec.get("lane") not in LANES:
        problems.append(f"unknown lane: {rec.get('lane')}")
    if rec.get("state") not in STATES:
        problems.append(f"unknown state: {rec.get('state')}")
    if rec.get("state") == "dropped" and not rec.get("drop_reason"):
        problems.append("dropped record with no drop_reason")
    problems.extend(_identity_problems(rec))
    return problems


def _identity_problems(rec):
    """Every contact has one key, and every event names a contact that exists.

    A key is an identity, not a membership: `assign_keys` used to run only over
    the *selection*, so an excluded contact lost its key and every event
    written under it pointed at nobody. Reporting then dropped those events
    from persona and angle breakdowns, `audit.why_contacted` answered "no
    evidence stored" for a person who had cost credits, and the reply block in
    `eligibility` - which matches on the same key - would have stopped
    recognising somebody who had asked us to stop.

    Contacts and excluded are checked together for that reason: an exclusion
    moves a person out of the selection and does not make them a different
    person.
    """
    problems = []
    everyone = (rec.get("contacts") or []) + (rec.get("excluded") or [])
    holders = {}
    for contact in everyone:
        key = contact.get("key")
        if not key:
            problems.append(
                "contact with no key: %s" % (contact.get("name") or "unnamed"))
            continue
        holders.setdefault(key, []).append(contact)
    for key, held in sorted(holders.items()):
        if len(held) > 1:
            problems.append("contact key held by %d contacts: %s"
                            % (len(held), key))
    for entry in rec.get("events") or []:
        named = entry.get("contact")
        if named and named not in holders:
            problems.append("event %s names no contact: %s"
                            % (entry.get("type") or entry.get("id") or "?", named))
    return problems


def log(rec, step, note, **extra):
    """Append an audit entry. `extra` carries structured provenance, such as the
    evidence behind an angle or how many attempts a step took."""
    entry = {"step": step, "at": now(), "note": note}
    entry.update({k: v for k, v in extra.items() if v not in (None, "", [], {})})
    rec.setdefault("log", []).append(entry)


def deep_merge(base, patch):
    for k, v in patch.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            deep_merge(base[k], v)
        else:
            base[k] = v
    return base


def get(rid, recs=None):
    for r in (recs if recs is not None else load()):
        if r.get("id") == rid:
            return r
    return None


ALL = object()


def list_records(state=None, lane=None, client=MISSING, recs=None):
    """Filter the queue. `client` is explicit and never implicit.

    A caller that wants every tenant's records passes `client=ALL`. A caller
    that names a client gets that client's rows. An empty string, a string
    that is not a valid slug, or a string that does not name a known client
    refuses rather than returning silence: "nothing" and "not a tenant" are
    different answers, and conflating them is the bug this fixes.

    `client` has no default. Omitting it is a TypeError, not a silent return
    of the whole estate. The CLI passes `ALL` explicitly; a request path
    passes a slug.
    """
    if client is MISSING:
        raise TypeError(
            "list_records requires an explicit client argument. "
            "Pass client=store.ALL for every tenant, or a client slug.")
    if client is not ALL:
        if not client or not isinstance(client, str):
            raise ValueError(
                f"client must be a non-empty string or store.ALL, got {client!r}")
        if not re.match(r"^[a-z0-9][a-z0-9_-]{0,63}$", client):
            raise ValueError(
                f"not a valid client slug: {client!r}")
        from . import repo as _repo
        if client not in _repo.known_clients():
            raise ValueError(f"unknown client: {client!r}")
    return [r for r in (recs if recs is not None else load())
            if (state is None or r.get("state") == state)
            and (lane is None or r.get("lane") == lane)
            and (client is ALL or r.get("client") == client)]


def append(records, note="ingested"):
    """Add new records. Refuses to collide with an id already in the queue.

    Read, check and write happen under one lock, so two processes ingesting at
    once cannot both decide an id is free.
    """
    with lock():
        recs = load()
        known = {r["id"] for r in recs}
        for r in records:
            if r["id"] in known:
                raise ValueError(f"duplicate id: {r['id']}")
            problems = validate(r)
            if problems:
                raise ValueError(f"{r['id']}: {'; '.join(problems)}")
            if not r.get("log"):
                log(r, r["state"], note)
            known.add(r["id"])
            recs.append(r)
        mode = backend()
        if mode == "sqlite":
            _write_sqlite(recs)
        elif mode == "shadow":
            _write(recs)
            _write_sqlite_shadow(recs, None)
        else:
            _write(recs)
    return len(records)


def patch(rid, changes, note=""):
    """Read, change and write under one lock: no lost update."""
    with lock():
        recs = load()
        rec = get(rid, recs)
        if rec is None:
            raise KeyError(f"no record {rid}")
        before = rec.get("state")
        # What was already wrong with this record, before we touched it.
        #
        # A patch refuses to make things worse; it does not refuse to touch a
        # record that is already broken. Those are different rules, and
        # conflating them means a legacy record whose contacts predate keys
        # cannot be dropped - the one operation you most want available on a
        # record you have lost confidence in.
        was = set(validate(rec))
        deep_merge(rec, changes)
        problems = [p for p in validate(rec) if p not in was]
        if problems:
            raise ValueError(f"{rid}: {'; '.join(problems)}")
        log(rec, rec.get("state", before), note or f"patched {','.join(changes)}")
        mode = backend()
        if mode == "sqlite":
            _write_sqlite(recs)
        elif mode == "shadow":
            _write(recs)
            _write_sqlite_shadow(recs, None)
        else:
            _write(recs)
    return rec


def drop(rid, reason):
    if not reason:
        raise ValueError("a drop needs a reason")
    return patch(rid, {"state": "dropped", "drop_reason": reason}, note=reason)


def stats(recs=None):
    recs = recs if recs is not None else load()
    return {
        "records": len(recs),
        "states": dict(Counter(r.get("state") for r in recs)),
        "lanes": dict(Counter(r.get("lane") for r in recs)),
    }


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m src.store")
    sub = p.add_subparsers(dest="cmd", required=True)

    pl = sub.add_parser("list")
    pl.add_argument("--state")
    pl.add_argument("--lane")
    pl.add_argument("--client")
    pl.add_argument("--fields", default="id,lane,client,company,domain,state")

    pg = sub.add_parser("get")
    pg.add_argument("id")
    pg.add_argument("--field")

    pp = sub.add_parser("patch")
    pp.add_argument("id")
    pp.add_argument("--json", required=True)
    pp.add_argument("--note", default="")

    pd = sub.add_parser("drop")
    pd.add_argument("id")
    pd.add_argument("--reason", required=True)

    sub.add_parser("stats")
    a = p.parse_args(argv)

    if a.cmd == "list":
        fields = a.fields.split(",")
        rows = list_records(a.state, a.lane, a.client or ALL)
        widths = [max(len(f), max((len(str(r.get(f, ""))) for r in rows), default=0))
                  for f in fields]
        print("  ".join(f.ljust(widths[i]) for i, f in enumerate(fields)))
        for r in rows:
            print("  ".join(str(r.get(f, "")).ljust(widths[i]) for i, f in enumerate(fields)))
        return 0

    if a.cmd == "get":
        rec = get(a.id)
        if rec is None:
            sys.exit(f"no record {a.id}")
        print(json.dumps(rec.get(a.field) if a.field else rec, indent=2, ensure_ascii=False))
        return 0

    if a.cmd == "patch":
        rec = patch(a.id, json.loads(a.json), a.note)
        print(f"{a.id}: state {rec['state']}")
        return 0

    if a.cmd == "drop":
        drop(a.id, a.reason)
        print(f"{a.id}: dropped ({a.reason})")
        return 0

    s = stats()
    print(f"records: {s['records']}")
    for k, v in s["states"].items():
        print(f"  {k:<10} {v}")
    print("lanes: " + ", ".join(f"{k}={v}" for k, v in s["lanes"].items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
