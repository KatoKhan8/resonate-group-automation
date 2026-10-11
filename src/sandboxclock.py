"""An injected clock for the phase-2 horizon run.

WHY THIS EXISTS, AND WHY IT IS NOT A `freezegun` CALL
=====================================================
The phase-2 run simulates roughly 900 days. Every question it is meant to
answer is a question about TIME: does a 30-day hold release on day 31 and
never earlier, do per-day counters stay correct across a UTC midnight, does
a recipient-local sending window survive a daylight-saving change, does the
same account come round again after a re-engagement gap.

None of those can be answered by a run that reads the wall clock, and none of
them can be answered by a run that fakes time only in the test. The clock has
to reach the CODE UNDER TEST.

MEASURED 2026-10-12: there is no central clock seam in this repository.
`src/` holds **102 real-clock reads across 44 files** - 34 `time.time()`,
28 `datetime.now()`, 24 `time.monotonic()`, 12 `date.today()`, 4 `utcnow()`.

That sounds fatal and is not, because the reads fall into three classes and
only one of them matters:

1. BUSINESS TIME behind an injectable parameter. The repository's own idiom
   is `now = now or datetime.datetime.now(timezone.utc)` - `senderheadroom`
   at lines 189 and 337 is the pattern. A caller passing `now=` never reads
   the wall clock at all. This is the good design that was already here, and
   the horizon run uses it wherever it exists.

2. BUSINESS TIME with no parameter. `store.now()` (src/store.py:233) is the
   canonical one: one function, every stored timestamp. Patching that single
   function moves every `at`, `created_at` and `received_at` the run writes.

3. REAL elapsed time, which MUST NOT be faked. `store.py:268` and `:296` use
   `time.monotonic()` for the queue lock deadline and `:290` uses
   `time.time()` against a file mtime for lock staleness. Those are asking
   "how long have I actually been waiting", and a simulated answer would
   either spin forever or declare a live lock stale. `suitelock` is the same.
   Faking these would be a bug, not a feature.

So this module injects at classes 1 and 2 and deliberately leaves class 3
alone. `unpatched_business_clock_reads()` enumerates what is left over, so the
run can REPORT any class-1/2 read it could not reach as a defect with a file
and a line rather than quietly producing a wrong answer.

WHAT IT REFUSES TO DO
=====================
It does not advance by itself. Nothing in a simulation should be able to make
time pass as a side effect of being called, because then the order of two
unrelated reads changes the answer. `advance()` is the only way forward and
the runner calls it once per simulated day.

It is also TIMEZONE-AWARE ON PURPOSE, holding UTC and carrying the operator's
zone separately. A naive datetime cannot answer a daylight-saving question,
and "the machine's zone" is not an answer either: this is the sending machine
and its zone is Europe/Zagreb, but a recipient's window is the RECIPIENT's
zone and a seat's window is the SEAT's. Those are three different questions
and a single naive clock silently answers all of them the same way.
"""
import datetime
import os
import re
import zoneinfo

#: The operator's zone. This is the sending machine; confirmed Europe/Zagreb
#: on 2026-10-12. Carried explicitly rather than read from the host, because a
#: run whose answers depend on the host's TZ setting is not reproducible.
OPERATOR_ZONE = zoneinfo.ZoneInfo("Europe/Zagreb")

UTC = datetime.timezone.utc


class ClockNotInjected(RuntimeError):
    """Business time was read while the simulation held no clock.

    Raised rather than falling back to the wall clock. A silent fallback is
    how a 900-day simulation ends up with real 2026 timestamps in half its
    rows and no indication which half.
    """


class SimClock:
    """Simulated time, advanced only by an explicit call.

    `at` is the instant the simulation currently stands at, always tz-aware
    and always stored in UTC. `day_index` counts simulated days from the
    start, which is what the horizon's measurements are keyed on - a date is
    ambiguous across a DST boundary and an index never is.
    """

    def __init__(self, start, zone=OPERATOR_ZONE):
        if start.tzinfo is None:
            raise ValueError(
                "a naive start cannot answer a daylight-saving question; "
                "pass a tz-aware datetime")
        self.start = start.astimezone(UTC)
        self.at = self.start
        self.zone = zone
        self.day_index = 0
        self._advances = 0

    # ---------------------------------------------------------------- reading

    def now(self):
        """The current simulated instant, UTC, tz-aware."""
        return self.at

    def now_iso(self):
        """What `store.now()` would return, at simulated time."""
        return self.at.replace(microsecond=0).isoformat()

    def local(self, zone=None):
        """The same instant in a named zone. The DST question lives here."""
        return self.at.astimezone(zone or self.zone)

    def utc_offset_hours(self, zone=None):
        """The zone's offset right now, in hours. Changes across a DST step."""
        offset = self.local(zone).utcoffset()
        return offset.total_seconds() / 3600.0

    def is_dst(self, zone=None):
        return bool(self.local(zone).dst())

    # --------------------------------------------------------------- advancing

    def advance(self, days=0, hours=0, minutes=0):
        """Move forward. The ONLY way time passes in a simulation.

        Returns the list of events crossed, so the runner can assert on them
        rather than recomputing: a UTC day boundary and a DST transition are
        exactly the two things the horizon is asked about.
        """
        if days < 0 or hours < 0 or minutes < 0:
            raise ValueError("a simulation does not run backwards")
        before = self.at
        before_offset = self.utc_offset_hours()
        self.at = self.at + datetime.timedelta(
            days=days, hours=hours, minutes=minutes)
        self._advances += 1
        self.day_index = (self.at.date() - self.start.date()).days
        after_offset = self.utc_offset_hours()
        crossed = []
        if self.at.date() != before.date():
            crossed.append("utc_day_boundary")
        if after_offset != before_offset:
            crossed.append(
                "dst_change:%+g->%+g" % (before_offset, after_offset))
        return crossed

    def __repr__(self):
        return "<SimClock day=%d at=%s local=%s %+g>" % (
            self.day_index, self.at.isoformat(),
            self.local().isoformat(), self.utc_offset_hours())


# ------------------------------------------------------------------ injection

def dst_transitions(start, end, zone=OPERATOR_ZONE):
    """Every instant in [start, end) where `zone`'s UTC offset changes.

    Computed by walking, not from a table, because a table is a second
    representation of something the tz database already knows and the two
    drift. Hourly resolution: a transition is always on the hour.
    """
    out = []
    cur = start.astimezone(UTC).replace(minute=0, second=0, microsecond=0)
    end = end.astimezone(UTC)
    prev = cur.astimezone(zone).utcoffset()
    while cur < end:
        cur += datetime.timedelta(hours=1)
        off = cur.astimezone(zone).utcoffset()
        if off != prev:
            out.append((cur, prev.total_seconds() / 3600.0,
                        off.total_seconds() / 3600.0))
            prev = off
    return out


#: Business-time reads this module can reach, and how. Each entry is
#: (module path, attribute, what it is). Kept as data so the test can assert
#: the list is actually patched rather than trusting that `install` ran.
BUSINESS_CLOCK_SEAMS = (
    ("src.store", "now", "every stored timestamp"),
)

#: Real-elapsed-time reads that MUST NOT be simulated. Named so that a reader
#: can see the omission is deliberate and so a future patch cannot quietly
#: add them without this list disagreeing.
REAL_ELAPSED_EXEMPT = (
    ("src/store.py", 268, "time.monotonic", "queue lock deadline"),
    ("src/store.py", 290, "time.time", "queue lock staleness vs file mtime"),
    ("src/store.py", 296, "time.monotonic", "queue lock deadline"),
    ("src/suitelock.py", None, "time.monotonic/time.time", "suite lock"),
)


def install(clock):
    """Point the business-time seams at `clock`. Returns an undo callable.

    Patches by MODULE ATTRIBUTE rather than by rewriting `datetime`, because
    a global datetime patch also moves the lock deadlines in class 3 and
    those must keep ticking in real time.
    """
    import importlib

    undo = []
    for mod_name, attr, _what in BUSINESS_CLOCK_SEAMS:
        mod = importlib.import_module(mod_name)
        previous = getattr(mod, attr)
        setattr(mod, attr, clock.now_iso)
        undo.append((mod, attr, previous))

    def _undo():
        for mod, attr, previous in reversed(undo):
            setattr(mod, attr, previous)

    return _undo


_CLOCK_RX = {
    "datetime.now": re.compile(r"datetime\.datetime\.now\(|(?<!\w)datetime\.now\("),
    "date.today": re.compile(r"datetime\.date\.today\(|(?<!\w)date\.today\("),
    "utcnow": re.compile(r"utcnow\("),
}

#: A read on one of these lines is behind an injectable `now=` parameter, so
#: a caller that passes `now=` never reaches it. Recognised structurally by
#: the repository's own idiom rather than by a hand-kept list of line numbers.
_INJECTABLE_IDIOM = re.compile(r"=\s*\w+\s+or\s+datetime\.datetime\.now\(")


def unpatched_business_clock_reads(root=None, only=None):
    """Business-time reads the injected clock does NOT reach.

    Returns a list of (path, lineno, kind, source). Every entry is a defect
    candidate for the horizon report - a place where a 900-day simulation
    would get the real 2026 clock. `only` narrows to the modules actually on
    the simulated path, because a Slack helper's timestamp does not change a
    hold-release answer and reporting it as a defect would be noise.

    `time.time` and `time.monotonic` are NOT scanned: see class 3 above.
    """
    root = root or os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "src")
    patched = {m.split(".")[-1] + ".py" for m, _a, _w in BUSINESS_CLOCK_SEAMS}
    out = []
    for folder, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for name in files:
            if not name.endswith(".py"):
                continue
            if only is not None and name not in only:
                continue
            path = os.path.join(folder, name)
            with open(path, encoding="utf-8", errors="replace") as handle:
                for i, line in enumerate(handle, 1):
                    stripped = line.strip()
                    if stripped.startswith("#"):
                        continue
                    if _INJECTABLE_IDIOM.search(line):
                        continue
                    for kind, rx in _CLOCK_RX.items():
                        if rx.search(line):
                            if name in patched and kind == "datetime.now":
                                continue
                            out.append((path, i, kind, stripped[:110]))
    return out


#: The modules whose clock reads can change a horizon answer. Everything the
#: simulated path touches to decide WHEN something may happen or WHETHER a
#: hold has expired.
SIMULATED_PATH_MODULES = frozenset({
    "store.py", "schedule.py", "cadence.py", "touch.py", "fatigue.py",
    "reengagement.py", "revival.py", "eligibility.py", "collision.py",
    "optout.py", "agencydnc.py", "stepstate.py", "replies.py",
    "replywatch.py", "senderheadroom.py", "suppression.py", "dedupe.py",
})
