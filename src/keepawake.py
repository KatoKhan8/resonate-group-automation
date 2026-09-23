#!/usr/bin/env python3
"""Ask Windows not to idle-sleep while a monitor is alive. And say what that does NOT cover.

## Why this exists

On 2026-09-23 at 05:29:09 this machine restarted and every production loop
died. The cause was NOT sleep - it was a Windows Update restart initiated by
`MoUsoCoreWorker.exe` (System event 1074), five seconds after the last
heartbeat at 05:29:04. `docs/MACHINE-HARDENING-2026-09-23.md` has the
evidence.

**So read this first: a keep-awake request would not have prevented that
outage, and nothing in this module prevents a reboot.** A reboot is not a
sleep. `SetThreadExecutionState` has no opinion about the Update Orchestrator.
The defences that DO address the measured cause are the active-hours window,
the preview-update opt-out and `NoAutoRebootWithLoggedOnUsers`, all of which
live in the machine, not here.

This module closes a DIFFERENT hole, the one that was open but happened not
to fire: on 2026-09-23 the power scheme had `hard disk off` at 30 seconds,
`hybrid sleep` on, and idle sleep on battery at 45 minutes. Those are now 0,
but a power scheme is a machine setting that any Windows feature update, any
OEM utility, or any operator clicking through the Settings app can put back -
silently, with no event and no log line. A process that asserts its own
requirement does not depend on a setting staying where somebody left it.

## What it asks for, and what it deliberately does not

    ES_CONTINUOUS | ES_SYSTEM_REQUIRED

`ES_SYSTEM_REQUIRED` only. **No `ES_DISPLAY_REQUIRED`** - the screen is free
to blank, and holding a display request on a laptop that sits closed on a desk
is how a keep-awake turns into a burned panel and a hot room.

## The two ways this silently does nothing

**It is per-THREAD.** `ES_CONTINUOUS` sets a flag on the calling thread and
that flag dies with the thread. Acquire it on a worker that finishes and the
request evaporates with no error and no symptom until the machine sleeps
during the next unattended run. `acquire()` therefore records the thread it
was taken on and `holding()` refuses to claim the request is live from any
other thread. Take it on the process's main thread.

**A zero return is a failure.** `SetThreadExecutionState` returns the previous
state, and `0` means the call failed. Calling it and not reading the return is
how you get a keep-awake that reports success for ever - which is the shape of
three separate defects this project has already shipped. `acquire()` returns
False and `status()["error"]` says why.

## Modern Standby

This machine is S0 Low Power Idle. `ES_SYSTEM_REQUIRED` blocks IDLE
transitions; it does not override a lid-close or power-button entry into
connected standby. Under S0 the honest claim is "it will not drift to sleep on
its own", not "the OS cannot sleep".

## Non-Windows

`available()` is False, `acquire()` returns False, and nothing raises. A
POSIX box running the suite must not fail on a Windows power API, and a
no-op that pretends to have acquired something is worse than one that says it
did not.
"""
import ctypes
import platform
import threading

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
ES_DISPLAY_REQUIRED = 0x00000002          # named so it is visibly NOT used

KEEP_AWAKE = ES_CONTINUOUS | ES_SYSTEM_REQUIRED

_lock = threading.Lock()
_state = {"held": False, "thread": None, "previous": None, "error": None}


def available(system=None):
    """True only where `SetThreadExecutionState` exists."""
    name = system if system is not None else platform.system()
    return str(name).lower() == "windows"


def _kernel32():
    return ctypes.windll.kernel32                       # pragma: no cover


def _call(flags, api=None):
    """One call. Returns (ok, previous_state, error) and never raises.

    A power API is not worth crashing a supervisor over, and the caller has
    to be able to report a failure rather than inherit an exception on a
    path whose whole job is to keep other things running.
    """
    fn = api
    if fn is None:
        fn = getattr(_kernel32(), "SetThreadExecutionState", None)
    if fn is None:
        return False, None, "SetThreadExecutionState not present"
    try:
        previous = fn(ctypes.c_uint(flags))
    except Exception as exc:                            # noqa: BLE001
        return False, None, "%s: %s" % (type(exc).__name__, exc)
    if not previous:
        # Documented: the return is the PREVIOUS state, and 0 is failure.
        return False, 0, "SetThreadExecutionState returned 0"
    return True, int(previous), None


def acquire(api=None, system=None):
    """Take the system-required request on THIS thread. True if the OS agreed."""
    if not available(system):
        with _lock:
            _state.update(held=False, thread=None, previous=None,
                          error="not Windows")
        return False
    ok, previous, error = _call(KEEP_AWAKE, api=api)
    with _lock:
        _state.update(held=bool(ok),
                      thread=threading.get_ident() if ok else None,
                      previous=previous, error=error)
    return bool(ok)


def release(api=None, system=None):
    """Drop back to `ES_CONTINUOUS` alone, which clears the requirement."""
    if not available(system):
        with _lock:
            _state.update(held=False, thread=None)
        return False
    ok, _previous, error = _call(ES_CONTINUOUS, api=api)
    with _lock:
        _state.update(held=False, thread=None,
                      error=None if ok else error)
    return bool(ok)


def holding():
    """True only if the request is live AND we are the thread that took it.

    The second half is the point. See the module docstring: a request taken
    on a thread that has since exited is gone, and the only thing that can
    notice is a check that compares thread identity.
    """
    with _lock:
        if not _state["held"]:
            return False
        return _state["thread"] == threading.get_ident()


def status():
    """What to print in a `--status` line. Never raises, never lies."""
    with _lock:
        held = _state["held"]
        thread = _state["thread"]
        error = _state["error"]
    return {
        "available": available(),
        "held": bool(held),
        "same_thread": bool(held and thread == threading.get_ident()),
        "flags": "ES_CONTINUOUS|ES_SYSTEM_REQUIRED",
        "display_request": False,
        "error": error,
        # Stated on every status line so no reader of a green row concludes
        # the machine is protected from the thing that actually killed it.
        "covers": "idle sleep only - NOT a Windows Update restart",
    }


def reset_for_test():
    """Only the suite calls this. Module state is process-wide by design."""
    with _lock:
        _state.update(held=False, thread=None, previous=None, error=None)


class KeepAwake:
    """Context manager. `entered_ok` says whether the OS actually agreed.

        with KeepAwake() as awake:
            if not awake.entered_ok:
                emit("KEEP-AWAKE REFUSED " + str(awake.error))
            run_monitors()

    It does not raise when the request is refused: a supervisor that cannot
    take a power request should still supervise, loudly.
    """

    def __init__(self, api=None, system=None):
        self._api = api
        self._system = system
        self.entered_ok = False
        self.error = None

    def __enter__(self):
        self.entered_ok = acquire(api=self._api, system=self._system)
        self.error = status()["error"]
        return self

    def __exit__(self, *exc):
        release(api=self._api, system=self._system)
        return False
