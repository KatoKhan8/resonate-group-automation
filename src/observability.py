#!/usr/bin/env python3
"""Counters for things that happen to no particular record.

A rejected webhook belongs to nobody. There is no record to append it to - that
is the whole point, since a forged payload naming a record must not be able to
write to that record's log just by naming it. So these land in a process-level
counter and, when it matters, a line in work/observability.jsonl.

What is counted is deliberately small and deliberately never the payload. A
rejection stores the reason and a short detail, never the body: storing the
body of a forged request means an attacker chooses what goes in your logs.
"""
import collections
import json
import os

from . import events, store

_counts = collections.Counter()
_recent = collections.deque(maxlen=200)

# How much of a detail string is kept. Enough to diagnose, not enough to be
# used as storage.
DETAIL_LIMIT = 200


def path():
    return os.path.abspath(os.environ.get("OBSERVABILITY")
                           or os.path.join(os.path.dirname(store.queue_path()),
                                           "observability.jsonl"))


def reset():
    _counts.clear()
    _recent.clear()


def count(name, persist=False, **fields):
    """Record one occurrence. Returns the entry, which is never a payload."""
    if name not in events.OBSERVED:
        raise events.UnknownEvent(f"unknown observability event: {name}")
    entry = {"type": name, "at": store.now()}
    for k, v in fields.items():
        if v in (None, "", [], {}):
            continue
        entry[k] = v[:DETAIL_LIMIT] if isinstance(v, str) else v
    _counts[name] += 1
    _recent.append(entry)
    if persist:
        _append(entry)
    return entry


def _append(entry):
    target = path()
    with store.lock(for_path=target):
        # Inside the write barrier - see the note in `spendledger.record`:
        # a self-built append beside the queue is a test's route into the
        # operator's real state.
        store.refuse_production_write(target)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def counts():
    return dict(_counts)


def recent(limit=20):
    return list(_recent)[-limit:]


def snapshot():
    """Everything a health page would show, with nothing sensitive in it."""
    return {"counts": counts(), "recent": recent(),
            "file": path() if os.path.exists(path()) else None}
