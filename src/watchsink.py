"""A durable sink for the background watchers, and a way to tell them apart
from the dead ones.

## The defect this exists for

On 2026-09-20 six monitors were alive - verified by PID, not by a log line
claiming they had been started - and every one of the five provider watchers
was writing its events to a closed pipe. `emit()` was `print(line, flush=True)`
and the shells that launched them had exited with the session that made them.
The processes polled the provider every three minutes and threw the answer
away.

That is worse than a stopped watcher. A stopped watcher is at least
discoverable: its PID is gone. A running watcher whose output is discarded
looks healthy from every angle a person checks, and the standing rule -
"a stopped watcher must not be interpreted as evidence that no replies
occurred" - does not catch it, because the watcher is not stopped.

487's ten openers are scheduled inside two days of this being found. The SEND
line for the first real batch this system has ever sent would have been
printed into nothing.

## Two kinds of file, because they answer two different questions

`watch-events/<watcher>.jsonl`  WHAT CHANGED. Append-only, one object per
event. Empty is a real answer - the watchers are built to say nothing while
the picture is unchanged - which is exactly why it cannot be the only file.

`heartbeat/<watcher>.json`  WHO IS STILL LOOKING. Rewritten every poll, so
silence in the event log can be read as "unchanged" rather than "died an hour
ago". **A heartbeat is not an event.** Putting the liveness signal in the
event log would mean a monitor that emits every three minutes forever and an
operator who stops reading it.

## ONE FILE PER WATCHER, AND THE MEASUREMENT THAT FORCED IT

The first version of this module had every watcher append to one shared
`watch-events.jsonl`, on the reasoning that a single `os.write` to a
descriptor opened `O_APPEND` is one call into the OS and so resolves the
offset and writes under one lock.

**That is true on POSIX and false on Windows, and the test measured it.** Six
writers x 40 lines should be 240 lines; the shared file held 193. Not torn -
LOST. The Windows CRT implements `O_APPEND` as a seek-to-end followed by a
write, which is two operations with a window between them, and a real atomic
append needs `FILE_APPEND_DATA` without `FILE_WRITE_DATA` at the Win32 layer,
which `os.open` does not offer.

So the sharing is removed rather than the race being fought. Each watcher
owns one events file and one heartbeat file, named for the watcher, and
`events()` merges them at read time. No lock is taken on the write path,
which matters more than tidiness: the alternative was `store.lock`, and a
`QueueLocked` on the one write that carries the first real SEND this system
has ever made would lose exactly the line the module was built to keep.

A watcher's identity is `(source, campaign)` - `bison:487` and `bison:489`
are two processes and must be two files. `emitter` and `beat` build it the
same way so the event log and the heartbeat agree on who is who.

This is worth carrying beyond this module: **anything in `work/` appended to
by more than one process at once on Windows is losing rows.**
"""
import json
import os
import re
import time

from . import store

_MAX_LINE = 8192


def events_dir():
    """Resolved per call, not at import, so tests can point it elsewhere."""
    return os.path.abspath(
        os.environ.get("WATCH_EVENTS")
        or os.path.join(os.path.dirname(store.queue_path()), "watch-events"))


def heartbeat_dir():
    return os.path.abspath(
        os.environ.get("WATCH_HEARTBEAT")
        or os.path.join(os.path.dirname(store.queue_path()), "heartbeat"))


_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")


def watcher(source, campaign=None):
    """The identity both files are named for.

    `bison:487` and `bison:489` are two PROCESSES watching two campaigns, and
    a name that collapsed them would put two writers back on one file - the
    defect this module's shape exists to remove.
    """
    name = str(source or "")
    if campaign is not None:
        name = "%s:%s" % (name, campaign)
    return name


def _slug(name):
    """A watcher identity as a filename. `bison:487` -> `bison-487`.

    Refuses empty rather than writing `.json`: a file nobody can attribute
    cannot answer the question it exists for.
    """
    slug = _UNSAFE.sub("-", str(name or "")).strip("-")
    if not slug:
        raise ValueError("a watcher must have a name")
    return slug


def heartbeat_path(source, campaign=None):
    return os.path.join(heartbeat_dir(),
                        _slug(watcher(source, campaign)) + ".json")


def events_path(source, campaign=None):
    return os.path.join(events_dir(),
                        _slug(watcher(source, campaign)) + ".jsonl")


def _now():
    return time.time()


def _stamp(at=None):
    at = _now() if at is None else at
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(at))


def record(source, line, campaign=None, at=None, kind=None):
    """Append one event. Returns the object written.

    `kind` defaults to the first word of the line, because every watcher
    already emits `SEND 487 ...` / `SCHEDULE-MOVED 487 ...` and re-stating it
    at the call site is a second place to keep in step. The full line is kept
    verbatim - it is what a person reads - and the parsed head is what a
    query filters on.
    """
    path = events_path(source, campaign)
    store.refuse_production_write(path)
    text = str(line)
    row = {
        "at": _stamp(at),
        "source": str(source),
        "watcher": watcher(source, campaign),
        "kind": (kind if kind is not None
                 else (text.split(" ", 1)[0] if text else "")),
        "line": text,
        # Carried so `contenders()` can prove after the fact that exactly one
        # process owns this file. The per-watcher split only removes the race
        # while the naming holds, and on 2026-09-20 it did not: two processes
        # watched 487, one with `--campaign 487` and one on the default.
        "pid": os.getpid(),
    }
    if campaign is not None:
        row["campaign"] = campaign
    payload = json.dumps(row, ensure_ascii=False) + "\n"
    if len(payload) > _MAX_LINE:
        # Truncate the LINE, never the envelope: a row that loses its `at` or
        # its `source` is unattributable, which is the one thing this file
        # must never be.
        keep = max(0, _MAX_LINE - (len(payload) - len(text)) - 3)
        row["line"] = text[:keep] + "..."
        row["truncated"] = True
        payload = json.dumps(row, ensure_ascii=False) + "\n"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    try:
        os.write(fd, payload.encode("utf-8"))
    finally:
        os.close(fd)
    return row


def beat(source, campaign=None, state=None, at=None, note=None):
    """Rewrite one watcher's heartbeat. Returns the object written.

    Called on EVERY poll including the ones that emit nothing, which is the
    whole point: the event log going quiet and the watcher dying look
    identical from the outside and this is what separates them.

    Also called on a failed poll, with `note`, so a watcher that is alive but
    cannot read the provider reports as alive-and-blind rather than as
    healthy. Those are different incidents.
    """
    path = heartbeat_path(source, campaign)
    store.refuse_production_write(path)
    row = {
        "source": str(source),
        "watcher": watcher(source, campaign),
        "at": _stamp(at),
        "epoch": int(_now() if at is None else at),
        "pid": os.getpid(),
    }
    if campaign is not None:
        row["campaign"] = campaign
    if state is not None:
        row["state"] = state
    if note is not None:
        row["note"] = note
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = "%s.%d.tmp" % (path, os.getpid())
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    os.replace(tmp, path)
    return row


def heartbeats():
    """Every watcher's last beat, newest first. Unreadable files are reported
    rather than skipped - a heartbeat that cannot be parsed is a fault in the
    monitor, and dropping it would restore exactly the silence this module
    exists to remove.
    """
    out = []
    directory = heartbeat_dir()
    if not os.path.isdir(directory):
        return out
    for name in sorted(os.listdir(directory)):
        if not name.endswith(".json"):
            continue
        full = os.path.join(directory, name)
        try:
            with open(full, encoding="utf-8") as f:
                row = json.load(f)
        except Exception as exc:
            out.append({"watcher": name[:-5], "source": name[:-5],
                        "at": None, "epoch": None,
                        "unreadable": "%s: %s" % (type(exc).__name__, exc)})
            continue
        row.setdefault("source", name[:-5])
        row.setdefault("watcher", row["source"])
        out.append(row)
    out.sort(key=lambda r: (r.get("epoch") is None, -(r.get("epoch") or 0)))
    return out


def stale(max_age_seconds, now=None):
    """The watchers that have not beaten inside `max_age_seconds`.

    An unreadable or undated heartbeat counts as STALE, not as fresh. The
    question being asked is "may I read silence as unchanged", and the only
    safe answer for a beat that cannot be read is no.
    """
    now = _now() if now is None else now
    out = []
    for row in heartbeats():
        epoch = row.get("epoch")
        if not isinstance(epoch, (int, float)):
            out.append(dict(row, age=None))
            continue
        age = now - epoch
        if age > max_age_seconds:
            out.append(dict(row, age=age))
    return out


def events(limit=None, source=None, campaign=None, kind=None, since=None,
           watcher_name=None):
    """Every watcher's events, MERGED and oldest first.

    The merge is the price of one file per writer, and it is paid at read
    time by the one reader rather than at write time by six processes.

    `since` is an ISO stamp compared as a string, which is exact for the
    `%Y-%m-%dT%H:%M:%SZ` this module writes and is the reason it writes that
    shape rather than a local-time one.
    """
    directory = events_dir()
    if not os.path.isdir(directory):
        return []
    out = []
    for name in sorted(os.listdir(directory)):
        if not name.endswith(".jsonl"):
            continue
        if watcher_name is not None and _slug(watcher_name) != name[:-6]:
            continue
        with open(os.path.join(directory, name), encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except Exception:
                    # A torn line is kept, marked. Dropping it would hide the
                    # evidence that a second writer had reached this file,
                    # which is the failure the per-watcher split prevents.
                    out.append({"at": None, "source": None,
                                "watcher": name[:-6], "kind": "TORN",
                                "line": line[:400], "torn": True})
                    continue
                row.setdefault("watcher", name[:-6])
                if source is not None and row.get("source") != source:
                    continue
                if campaign is not None and row.get("campaign") != campaign:
                    continue
                if kind is not None and row.get("kind") != kind:
                    continue
                if since is not None and str(row.get("at") or "") < since:
                    continue
                out.append(row)
    # A torn row has no `at` and must not sort to the front of a report an
    # operator reads as a timeline; it sorts last, where it reads as a fault.
    out.sort(key=lambda r: (r.get("at") is None, str(r.get("at") or "")))
    if limit is not None:
        out = out[-limit:]
    return out


def contenders(since=None):
    """Watchers whose file has been written by more than one process.

    The per-watcher split removes the shared-append race only while the NAMES
    stay distinct, and on the morning this module was written they did not:
    `bison_watch_loop.py --interval 300` defaults to campaign 487 and a
    second process ran `--campaign 487` explicitly. Two processes, one
    identity, one file - the exact arrangement that lost 47 of 240 rows.

    Reported rather than prevented, because a lock on the write path is the
    thing this module refused: the reading side can say which files are
    contended, and the fix is to stop running two of the same watcher.

    **PASS `since` OR THIS OVER-REPORTS.** The event files are durable across
    restarts, so a watcher that was STOPPED and REPLACED leaves its old pid
    behind and reads as contended for ever. Measured 2026-09-20: the fleet
    was restarted at 12:49Z onto new code and the unscoped call named both
    bison watchers, with `since="2026-09-20T12:50:00Z"` returning {}.

    A replaced watcher and a contended one are different facts and an
    operator must not read the first as the second, so the caller states the
    window it means. `since=None` answers "has this file EVER had two
    writers", which is a real question and rarely the one being asked.
    """
    seen = {}
    for row in events(since=since):
        pid = row.get("pid")
        if pid is None:
            continue
        seen.setdefault(row.get("watcher"), set()).add(pid)
    return {name: sorted(pids) for name, pids in sorted(seen.items())
            if len(pids) > 1}


def emitter(source, campaign=None, stream=True):
    """The one-line change a watch loop makes.

        emit = watchsink.emitter("bison", campaign=487)

    Keeps printing to stdout - a watcher run in a terminal by a person should
    still behave like one - and additionally records. The print is not the
    durable half and never was.
    """
    def emit(line):
        if stream:
            print(line, flush=True)
        try:
            record(source, line, campaign=campaign)
        except Exception as exc:
            # A sink failure must not kill a watcher. It must also not be
            # silent, so it goes to the stream that is already there.
            print("SINK-ERROR %s: %s" % (type(exc).__name__, exc), flush=True)
    return emit
