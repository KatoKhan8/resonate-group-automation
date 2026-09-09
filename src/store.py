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
STATE_OVERRIDES = ("CAMPAIGNS", "JOBS", "WORKSPACES", "AUDIT", "SENDERS",
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
                   # The prospect-facing action ledger. Of everything in this
                   # tuple it is the one a test must never write into the real
                   # `work/`: a stray reservation there would count against a
                   # live pilot cap, and a stray `sent` row would make a real
                   # person look already-contacted.
                   "ACTION_LEDGER")


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
    """
    with lock(timeout):
        recs = load()
        yield recs
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


def load():
    return read_jsonl(queue_path())


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


def save(recs, timeout=None):
    """Atomic whole-file write, under the lock. A crash leaves the old queue."""
    with lock(timeout):
        refuse_evidence_loss(read_jsonl(queue_path()), recs)
        _write(recs)


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


def list_records(state=None, lane=None, client=None, recs=None):
    return [r for r in (recs if recs is not None else load())
            if (state is None or r.get("state") == state)
            and (lane is None or r.get("lane") == lane)
            and (client is None or r.get("client") == client)]


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
        rows = list_records(a.state, a.lane, a.client)
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
