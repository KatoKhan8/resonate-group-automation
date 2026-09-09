#!/usr/bin/env python3
"""Reply reconciliation on a timer, so protection does not depend on memory.

## The gap this closes

`poller` works and is live-validated, but it is a command somebody types.
On the deployed service that meant replies were ingested exactly as often as
an operator remembered to run it, which makes the guarantee in
`ACCOUNT-OUTREACH.md` - a confirmed reply stops that lead on both channels -
only as timely as the last manual poll. A cadence step can fire in the gap.

## Why a thread and not a job framework

The deployment is one Railway service running one process (`numReplicas: 1`),
and the build has no third-party dependencies by construction. A scheduler
library, a second service or a queue would each be a new moving part with its
own failure modes for what is, at bottom, "call two read-only endpoints every
few minutes". So this is a supervised daemon thread in the process that is
already running, and the state it depends on is the same `work/` state
everything else uses.

It is nonetheless safe against a second process: every poll is taken under a
cross-process advisory lock, so two replicas, or a web process and an
operator's CLI, cannot poll the same provider at once. A poll that cannot get
the lock is skipped and recorded as skipped, never queued - the next tick is
minutes away and the checkpoint means nothing is lost by waiting.

## Per provider, not per workspace, and the reason

Provider credentials are process-global environment variables. There is no
per-workspace API key, so a per-workspace poll would be the same request
repeated N times against the same account. Workspace is not ignored - it is
recovered where it actually lives, on the record an event matched, and
reported per workspace in the status below.

## What it will not do

It reads. `poller.run` ingests, which pauses a record and may enqueue a
tag-sync intent; nothing on this path sends, drafts or replies, and `push`
and `tagsync.send` refuse by construction. It is off unless
`REPLY_POLL_ENABLED` is set, for the same reason `--live` is explicit on
every other read: a default that reaches a provider is still a default that
surprises somebody.

  python -m src.replywatch --once
  python -m src.replywatch --status
"""
import argparse
import datetime
import json
import os
import sys
import threading

from . import poller, providers, store

PROVIDERS = ("emailbison", "heyreach")

DEFAULT_INTERVAL = 300
MIN_INTERVAL = 60                 # a tighter loop is a provider complaint
DEFAULT_MAX_PAGES = 5

# Long enough that a slow provider is not mistaken for a stuck one, short
# enough that a tick never queues up behind the previous tick.
LOCK_WAIT = 1.0

CREDENTIALS = {"emailbison": ("BISON_KEY",), "heyreach": ("HEYREACH_KEY",)}


class NotConfigured(RuntimeError):
    """A provider was asked for without the credentials to reach it."""


def truthy(value):
    return str(value or "").strip().lower() in ("1", "true", "yes", "on")


def settings(env=None):
    """What the environment asks for. Bounded, never trusted blindly."""
    env = os.environ if env is None else env
    try:
        interval = int(str(env.get("REPLY_POLL_SECONDS") or DEFAULT_INTERVAL))
    except ValueError:
        interval = DEFAULT_INTERVAL
    named = [p.strip().lower()
             for p in str(env.get("REPLY_POLL_PROVIDERS") or "").split(",")
             if p.strip()]
    unknown = [p for p in named if p not in PROVIDERS]
    if unknown:
        raise NotConfigured("no poller for: " + ", ".join(sorted(unknown)))
    return {"enabled": truthy(env.get("REPLY_POLL_ENABLED")),
            "interval": max(MIN_INTERVAL, interval),
            "providers": tuple(named or PROVIDERS),
            "max_pages": DEFAULT_MAX_PAGES}


def expected_workspace(provider, env=None):
    """Which estate this deployment believes it is polling, or None.

    Only EmailBison has an answer to give. Its credential is bound to one of
    thirteen workspaces, the binding is changed in the vendor's UI rather than
    here, and it has moved four times in three days - so "which client's mail
    am I reading" is not answerable from configuration alone and must be
    checked against the provider on every run.

    Unset means unpinned, and unpinned is honest rather than safe: the run
    still scopes its checkpoint by whatever workspace it finds, so a mark can
    no longer leak between estates, but nothing refuses a poll of the wrong
    one. Set `BISON_WORKSPACE_ID` to make that a refusal. It is deliberately
    not defaulted to Productive's 10: a default would assert ownership this
    module cannot prove, and the failure it would cause is a refusal to read
    replies, on the path that stops outreach to someone who has answered.
    """
    if provider != "emailbison":
        return None
    # Deliberately does NOT load `config/.env`. `configured()` below does, and
    # for a credential that is right: a key is either readable or it is not.
    # A PIN is different - loading the file here would set BISON_WORKSPACE_ID
    # in `os.environ` for the whole process, and that flips this function's
    # answer from unpinned to pinned for every later caller, including tests
    # that have no pin and must not acquire one. A caller that wants the
    # operator's file read asks `providers.load_env()` itself; see
    # `senderinventory.run`.
    source = env if env is not None else os.environ
    return (source.get("BISON_WORKSPACE_ID") or "").strip() or None


def configured(provider, env=None):
    """Are this provider's credentials readable?

    `config/.env` is where this repository keeps them - `providers.key`
    says so in its own error message - and the only thing that reads that
    file is `providers.load_env`, called lazily from `key()` at the moment
    a credential is needed. Nothing loaded it at process startup, so this
    function asked `os.environ` a question the answer to which had not
    been fetched yet, and said no.

    The consequence was not a warning. `start()` refuses to poll when a
    chosen provider is unconfigured, `health()` then reports `off`, and
    `problems()` suppresses `off` outside production mode - so on any
    machine keeping its keys in `config/.env`, reply protection was
    silently not running, and nothing on any screen said so. Reply
    protection that is not running is not reply protection.

    Only when the caller has not injected an environment: an injected one
    is a test saying exactly what it wants asked.
    """
    if env is None:
        providers.load_env()
    env = os.environ if env is None else env
    names = CREDENTIALS.get(provider, ())
    return bool(names) and all(str(env.get(n) or "").strip() for n in names)


# ------------------------------------------------------------------- status

def status_path():
    return os.path.abspath(
        os.environ.get("REPLY_WATCH_STATUS")
        or os.path.join(os.path.dirname(store.queue_path()),
                        "replywatch.json"))


def load_status():
    path = status_path()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle) or {}
    except (OSError, ValueError):
        # Status is a report, never a decision. A corrupt file must not stop
        # polling; the next write replaces it.
        return {}


def _write_status(provider, fields):
    path = status_path()
    store.refuse_production_write(path)
    with store.lock(for_path=path):
        data = load_status()
        entry = data.setdefault(provider, {})
        entry.update(fields)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = f"{path}.{os.getpid()}.tmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(data, handle, indent=2, sort_keys=True)
        os.replace(tmp, path)
    return fields


def lock_file(provider):
    return os.path.join(os.path.dirname(store.queue_path()),
                        f"replywatch.{provider}")


def _workspaces_touched(outcomes):
    """Which workspace each applied event landed in.

    Recovered from the record the event matched rather than from the poll,
    because that is where the truth is. An unmatched event belongs to no
    workspace and is counted separately, never guessed into one.
    """
    ids = {(o.get("applied") or {}).get("record_id")
           for o in outcomes
           if (o.get("applied") or {}).get("status") == "applied"}
    ids.discard(None)
    if not ids:
        return {}
    counts = {}
    for rec in store.load():
        if rec.get("id") in ids:
            slug = rec.get("client") or "unassigned"
            counts[slug] = counts.get(slug, 0) + 1
    return counts


# ------------------------------------------------------------------ polling

def poll_once(provider, max_pages=DEFAULT_MAX_PAGES, live=True, env=None,
              now=None):
    """One provider, once. Never raises: a failure is a status, not a crash.

    Failure is isolated per provider on purpose. EmailBison being
    unreachable must not stop HeyReach from being polled, and must not move
    EmailBison's own checkpoint - a checkpoint advanced past rows that were
    never read is a reply nobody answers.
    """
    started = now or store.now()
    prior = load_status().get(provider) or {}
    fails = int(prior.get("consecutive_failures") or 0)

    if not configured(provider, env=env):
        return _write_status(provider, {
            "provider": provider, "last_started": started,
            "last_error": "not configured: no credentials in the environment",
            "consecutive_failures": fails + 1, "healthy": False})

    try:
        with store.lock(for_path=lock_file(provider), timeout=LOCK_WAIT):
            result = poller.run(provider, max_pages=max_pages, live=live,
                                expect=expected_workspace(provider, env=env))
    except store.QueueLocked:
        # Someone else is polling this provider right now. Skipping is the
        # correct answer: the work is not lost, it is already happening.
        return _write_status(provider, {
            "provider": provider, "last_started": started,
            "last_skipped": started, "skipped_reason": "already polling",
            "healthy": prior.get("healthy", True)})
    except Exception as exc:                                  # noqa: BLE001
        # Deliberately broad, and deliberately not silent: any failure to
        # reach a provider has to be visible rather than swallowed. The
        # checkpoint is untouched, so the next run re-reads.
        detail = f"{type(exc).__name__}: {exc}"[:300]
        _alert(provider, fails + 1, detail)
        return _write_status(provider, {
            "provider": provider, "last_started": started,
            "last_error": detail,
            "consecutive_failures": fails + 1, "healthy": False})

    outcomes = result.get("outcomes") or []
    return _write_status(provider, {
        "provider": provider,
        "last_started": started,
        "last_succeeded": store.now(),
        "checkpoint": result.get("cursor"),
        "pages": result.get("pages"),
        "events_inspected": result.get("events"),
        "new_replies_ingested": result.get("applied"),
        "duplicates_ignored": result.get("duplicates"),
        "ambiguous_identities": result.get("unmatched"),
        "workspaces": _workspaces_touched(outcomes),
        "last_error": None,
        "consecutive_failures": 0,
        "healthy": True})


# A provider blips. Alerting on the first failure would cry wolf, and
# alerting on every failure would send one message every interval for as
# long as the outage lasts. So: once, on the run that crosses the line.
ALERT_AFTER_FAILURES = 3


def _alert(provider, failures, detail):
    """Say once that reply protection has stopped, and only once.

    Emitted exactly on the crossing rather than on every failure. A
    provider that is down for a day would otherwise post an identical
    message every few minutes, and an operator who mutes that channel has
    muted the one alert that means somebody is still being written to
    after they answered.

    `notify.notify` cannot raise, which is why it is safe to call from the
    watcher thread. A notification that cannot be built must not stop the
    next poll from happening.
    """
    if failures != ALERT_AFTER_FAILURES:
        return None
    from . import notify
    return notify.notify(
        notify.REPLY_PROTECTION_FAILED,
        fields={"provider": provider,
                "consecutive_failures": failures,
                "detail": detail,
                "effect": "replies are not being ingested, so a cadence "
                          "step can go out to somebody who has already "
                          "answered",
                "action": "check the provider's credentials and reachability, "
                          "then `python -m src.replywatch --once`"},
        ids={"provider": provider})


def sweep(providers=None, max_pages=DEFAULT_MAX_PAGES, live=True, env=None):
    """Every provider, once. One provider's failure never stops another."""
    chosen = providers if providers is not None else settings(env)["providers"]
    return {p: poll_once(p, max_pages=max_pages, live=live, env=env)
            for p in chosen}


def healthy(status=None):
    """Is reply protection currently working? Unknown is not healthy."""
    status = load_status() if status is None else status
    if not status:
        return False
    return all(bool(entry.get("healthy")) and entry.get("last_succeeded")
               for entry in status.values())


# How many intervals may pass before a poller that once worked is treated
# as stale. Two would fire on a single slow sweep; three is a gap nobody
# should have to wonder about.
STALE_AFTER_INTERVALS = 3

OFF = "off"
NEVER_RUN = "never_run"
STALE = "stale"
FAILING = "failing"
WORKING = "working"

STATE_LABEL = {
    OFF: "Reply polling is off",
    NEVER_RUN: "Reply polling has never run",
    STALE: "Reply polling has not succeeded recently",
    FAILING: "Reply polling is failing",
    WORKING: "Reply polling is working",
}


def _age_seconds(stamp, now):
    try:
        then = datetime.datetime.fromisoformat(str(stamp))
        current = datetime.datetime.fromisoformat(str(now))
    except (TypeError, ValueError):
        return None
    if (then.tzinfo is None) != (current.tzinfo is None):
        # Naive and aware do not subtract. Refusing is better than
        # pretending one of them is UTC and reporting a confident number.
        return None
    return (current - then).total_seconds()


def health(now=None, env=None, status=None):
    """One verdict per provider, for somebody who has to answer

        "is reply protection currently working?"

    Silence is never health. A poller that has never run, or that ran an
    hour ago and has not succeeded since, is reported as a problem rather
    than left absent - the failure this exists to prevent is a dashboard
    that looks calm because nothing wrote a row.

    Deliberately says nothing about *which workspace* the events landed
    in. The status file records that, and this is rendered inside one
    tenant's pages, where another tenant's name has no business.
    """
    config = settings(env)
    status = load_status() if status is None else status
    now = now or store.now()
    interval = config["interval"]
    limit = interval * STALE_AFTER_INTERVALS

    rows = []
    for provider in config["providers"]:
        entry = status.get(provider) or {}
        age = _age_seconds(entry.get("last_succeeded"), now)
        failures = int(entry.get("consecutive_failures") or 0)

        if not config["enabled"]:
            state = OFF
        elif not entry.get("last_succeeded"):
            state = NEVER_RUN
        elif failures:
            state = FAILING
        elif age is not None and age > limit:
            state = STALE
        else:
            state = WORKING

        rows.append({
            "provider": provider,
            "state": state,
            "label": STATE_LABEL[state],
            "enabled": config["enabled"],
            "last_succeeded": entry.get("last_succeeded"),
            "seconds_since_success": int(age) if age is not None else None,
            "stale_after_seconds": limit,
            "consecutive_failures": failures,
            "last_error": entry.get("last_error"),
            "checkpoint": entry.get("checkpoint"),
            "interval": interval,
        })
    return rows


def problems(now=None, env=None, status=None, mode=None):
    """Only the rows an operator has to do something about.

    `off` is the interesting one, and it depends on where this is running.
    On a laptop or in the fictional estate, reply polling being off is the
    ordinary state and listing it as a failure would make "nothing is
    wrong" impossible to say. On the deployed service it means replies are
    not being ingested at all, which is the silent-health failure this
    whole verdict exists to prevent - so there, it is a row.
    """
    from . import config as app_config
    where = mode or app_config.mode()
    ignorable = {WORKING} if where == "production" else {WORKING, OFF}
    return [row for row in health(now=now, env=env, status=status)
            if row["state"] not in ignorable]


# --------------------------------------------------------------- the daemon

class Watcher:
    """A daemon thread that sweeps on an interval, and stops when asked.

    `polling` and `after` are separately switchable, because the two things
    this process owes an operator - reply protection and the digest - fail
    for different reasons and one being off must not silence the other. It
    is still one thread: a second timer running the same loop against the
    same clock would be a second thing to supervise for no gain.
    """

    def __init__(self, interval=DEFAULT_INTERVAL, providers=None,
                 max_pages=DEFAULT_MAX_PAGES, sweeper=None, polling=True,
                 after=()):
        self.interval = max(MIN_INTERVAL, int(interval))
        self.providers = tuple(providers or PROVIDERS)
        self.max_pages = max_pages
        self._sweep = sweeper or sweep
        self.polling = polling
        # (name, callable) so a failure can say which job failed rather
        # than "something in the watcher".
        self.after = tuple(after)
        self._stop = threading.Event()
        self._thread = None
        self.sweeps = 0

    def _tick(self):
        if self.polling:
            try:
                self._sweep(providers=self.providers,
                            max_pages=self.max_pages)
            except Exception as exc:                          # noqa: BLE001
                # sweep() already isolates per provider; this is the last
                # resort, and the loop has to outlive it. A watcher that
                # dies quietly is worse than one that never started.
                self._record_failure("watcher", exc)
        for name, job in self.after:
            # One job's failure must not stop the next one, and must not
            # stop polling. Same isolation, one level out.
            try:
                job()
            except Exception as exc:                          # noqa: BLE001
                self._record_failure(name, exc)

    def _record_failure(self, name, exc):
        try:
            _write_status(name, {
                "last_error": f"{type(exc).__name__}: {exc}"[:300],
                "healthy": False})
        except Exception:                                     # noqa: BLE001
            pass

    def _loop(self):
        while not self._stop.is_set():
            self._tick()
            self.sweeps += 1
            self._stop.wait(self.interval)

    def start(self):
        if self._thread is not None:
            return self
        self._thread = threading.Thread(target=self._loop, daemon=True,
                                        name="reply-watch")
        self._thread.start()
        return self

    def stop(self, timeout=5):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout)
            self._thread = None
        return self


def start(env=None, after=()):
    """Start the watcher if anything asked for it, else say why not.

    `after` is other work that wants the same interval - today that is the
    digest schedule. It is why this can return a running watcher while
    reply polling is off: the two jobs are independent, and a thread that
    refused to start because one of them was disabled would silently take
    the other with it.
    """
    config = settings(env)
    after = tuple(after)
    if not config["enabled"]:
        why = "reply polling is off (REPLY_POLL_ENABLED is not set)"
        if not after:
            return None, why
        watcher = Watcher(interval=config["interval"], polling=False,
                          after=after).start()
        return watcher, why
    missing = [p for p in config["providers"] if not configured(p, env=env)]
    if missing:
        # Fail loudly rather than looping against a provider we cannot reach.
        why = ("reply polling wants " + ", ".join(missing)
               + " but their credentials are not in the environment")
        if not after:
            return None, why
        watcher = Watcher(interval=config["interval"], polling=False,
                          after=after).start()
        return watcher, why
    watcher = Watcher(interval=config["interval"],
                      providers=config["providers"],
                      max_pages=config["max_pages"],
                      after=after).start()
    return watcher, (f"reply polling every {config['interval']}s: "
                     + ", ".join(config["providers"]))


# ---------------------------------------------------------------- the CLI

REPORTED = ("healthy", "last_started", "last_succeeded", "last_error",
            "consecutive_failures", "checkpoint", "pages", "events_inspected",
            "new_replies_ingested", "duplicates_ignored",
            "ambiguous_identities", "workspaces", "last_skipped",
            "skipped_reason")


def _print_status(out=print):
    status = load_status()
    if not status:
        out("no poll has ever run")
        return 1
    for provider in sorted(status):
        entry = status[provider]
        out(f"  {provider}")
        for key in REPORTED:
            if key in entry:
                out(f"    {key:22} {entry[key]}")
    out("")
    out(f"  reply protection healthy: {healthy(status)}")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m src.replywatch")
    parser.add_argument("--once", action="store_true",
                        help="sweep every provider once and exit")
    parser.add_argument("--status", action="store_true",
                        help="what the last sweep did. Reads nothing remote")
    parser.add_argument("--provider", action="append",
                        choices=sorted(PROVIDERS))
    parser.add_argument("--max-pages", type=int, default=DEFAULT_MAX_PAGES)
    args = parser.parse_args(argv)

    if args.status or not args.once:
        return _print_status()

    results = sweep(providers=tuple(args.provider) if args.provider else None,
                    max_pages=args.max_pages)
    for provider in sorted(results):
        entry = results[provider]
        state = "ok" if entry.get("healthy") else "FAILED"
        detail = entry.get("last_error") or (
            f"{entry.get('events_inspected')} inspected, "
            f"{entry.get('new_replies_ingested')} ingested")
        print(f"  {provider:12} {state:7} {detail}")
    print("\nPolling reads. Nothing was sent to anyone.")
    return 0 if healthy() else 1


if __name__ == "__main__":
    sys.exit(main())
