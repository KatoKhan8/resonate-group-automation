"""One place that runs the standing stops on a schedule and records every try.

## THE DEFECT THIS EXISTS FOR, MEASURED TWICE

TASK-0140 repaired `scripts/bounce_stop_7day.py` into a real instrument -
PASS / STOP / BLIND, `>=` at the boundary, a narrow catch, three exit codes,
28 tests through four states - and then said the thing that outlives the
repair:

    Nobody runs it.

Re-derived for TASK-0160 at `495fb3206`: a `grep` across the whole tree for
`bounce_stop_7day`, `hard_stop_check` and `queue_wall_check` finds docs, the
three scripts themselves, their own test modules, and **no service, timer,
monitor, loop, unit or module that invokes any of them**. The bounce stop and
the hard-stop check were both added on 2026-09-22 and have been uninvoked for
24 days. `scripts/queue_wall_check.py` was added at 01:10 today and was born
the same way.

A repaired script nothing calls is the same no-op it was yesterday with better
tests. `scripts/weekly_report_loop.py`'s own docstring names this as the third
time it happened in this repository; this is the fourth and fifth.

## WHAT THIS MODULE IS, AND WHAT THE LOOP IS

This module is the logic: the table of checks, the classifier, the attempt
journal, the gap rule, the three controls, and the assessment that puts them
together. `scripts/stop_watchdog_loop.py` is the process, registered in
`src/supervisor.py`'s one monitor table beside every other loop.

The split follows `weekly_report_loop.py` / `src/weeklyreportwatch.py`: the
decision is a pure function of its inputs so it can be driven through every
state without a process and without a provider, and the loop adds only the
clock, the beat and the printing.

## THE VERDICT IS THE EXIT CODE, BECAUSE ALL THREE ALREADY AGREE ON IT

The three checks have three different vocabularies - CLEAR / NO-DATA / STOP /
BLIND, tripped / undefined / blind, OK / WALL / CANNOT-ASSESS - and inventing
a fourth to map them into would be a second representation of a truth each
script already states. What they share, documented in each one's own
docstring, is the exit code:

    0   nothing is over a line, and the read was complete      -> PASS
    1   something is AT OR OVER a line                         -> STOP
    2   something could not be measured                        -> BLIND

So `classify` reads the exit code and nothing else, and each check's own
sentence is carried through **verbatim** rather than summarised. An exit code
outside those three is BLIND, not PASS: a check that answered in a code this
module does not know has not been understood, and an unread answer is not a
clean one.

## A STOP MUST NOT HIDE A BLIND, AND NEITHER MAY HIDE A GAP

Three things can go wrong and they are three different incidents:

    STOP    a stop tripped. Someone has to act.
    BLIND   a stop could not be measured. Nobody may be cleared.
    GAP     the schedule itself did not fire. Nothing was even asked.

The overall verdict is STOP when anything stopped, BLIND when anything was
blind or the record has a gap, and PASS only when every check answered 0, the
record is continuous and all three controls held. The summary names all three
counts in one sentence whichever wins, because the failure this whole task is
about is a number disappearing into a greener one.

## AN EMPTY RECORD IS A GAP, NOT A CLEAN SHEET

`gaps()` answers NEVER on an empty journal, OPEN when the last attempt is
older than the schedule allows, MISSED for a hole between two attempts, and
DAMAGED for a journal line that will not parse. A silently stopped scheduler
is how this hole opened in the first place, so the absence of attempts is an
observation with a name rather than a quiet zero.

## THE CONTROLS RUN EVERY PASS

`controls()` plants three inputs whose answers are known and checks the
instrument gives them. They make no provider call and cost nothing. If one
fails the whole pass is BLIND - an instrument that cannot be shown to fail is
not evidence that nothing is wrong, which is the B7 instrument this project
has already been bitten by.
"""
import datetime
import importlib.util
import json
import os
import time

from . import store

# ------------------------------------------------------------- the verdicts

PASS = "PASS"
STOP = "STOP"
BLIND = "BLIND"

#: The three answers and the only three. Named so a rewrite that quietly
#: drops BLIND goes red in the test file rather than going silent in
#: production - `bounce_stop_7day.VERDICTS` exists for the same reason.
VERDICTS = (PASS, STOP, BLIND)

EXIT_PASS, EXIT_STOP, EXIT_BLIND = 0, 1, 2

#: verdict -> the code this runner exits with. STOP and BLIND are both
#: non-zero and they are NOT the same number, for the reason
#: `bounce_stop_7day` separates them: a reader keyed on the status must be
#: able to tell a tripped stop from a check that never managed to run.
EXIT = {PASS: EXIT_PASS, STOP: EXIT_STOP, BLIND: EXIT_BLIND}


def classify(exit_code):
    """0 -> PASS, 1 -> STOP, 2 -> BLIND, anything else -> BLIND.

    FAIL CLOSED ON THE DEFAULT. A check that exits 3, or `None`, or -1 from a
    killed child, has not been understood by this runner, and the one thing
    an unread answer must never become is a pass.

    THE TYPE IS CHECKED BEFORE THE VALUE, and `bool` is excluded explicitly.
    `True == 1` in Python, so a boolean arriving in an exit-code slot - the
    shape of a caller that returned a success flag where a code belongs -
    would otherwise be read as a tripped STOP by arithmetic accident, and
    `False` as a clean PASS. A type confusion is not an answer; it is BLIND.
    """
    if isinstance(exit_code, bool) or not isinstance(exit_code, int):
        return BLIND
    if exit_code == EXIT_PASS:
        return PASS
    if exit_code == EXIT_STOP:
        return STOP
    if exit_code == EXIT_BLIND:
        return BLIND
    return BLIND


# ---------------------------------------------------------- the check table
#
# DATA, NOT CODE, and in ONE place - `src/supervisor.py`'s monitor table makes
# the same choice for the same reason, and its comment records what two
# tables cost when they drifted.
#
# `script` is a repository-relative path and `entry` the function inside it.
# The scripts are loaded by path rather than imported as modules because
# `scripts/` is not a package and because nothing under `src/` may depend on
# the shape of `scripts/`: the path and the function name are declarations in
# this table, checked by `test_every_declared_check_resolves`.
#
# `reads` says what the check asks, so an operator reading a journal row knows
# which provider traffic a pass costs.

CHECKS = (
    {
        "name": "bounce_stop_7day",
        "script": os.path.join("scripts", "bounce_stop_7day.py"),
        "entry": "run",
        "about": "bounce >= 2% on any mailbox over 7 days, from our own sends",
        "reads": "the per-message queue rows of the ten campaigns we own",
        "added": "2026-09-22",
    },
    {
        "name": "hard_stop_check",
        "script": os.path.join("scripts", "hard_stop_check.py"),
        "entry": "check",
        "about": "the deliverability hard stops: bounce, spam, unsubscribe",
        "reads": "the same queue rows plus each campaign's own record",
        "added": "2026-09-22",
    },
    {
        "name": "queue_wall_check",
        "script": os.path.join("scripts", "queue_wall_check.py"),
        "entry": "main",
        "about": "which campaigns are past a queue reader's page cap",
        "reads": "a dated counts file on disk; no provider call",
        "added": "2026-10-16",
    },
)


def root():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def load(check):
    """The check's script, loaded as a module from its declared path.

    Loaded fresh per call. These scripts hold no state between runs and a
    stale module held across a merge is the defect CLAUDE.md records for
    `bison_watch_loop`, which survived a breaking change only because it had
    the old module in memory.
    """
    path = os.path.join(root(), check["script"])
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    spec = importlib.util.spec_from_file_location(
        "_stopwatchdog_%s" % check["name"], path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ----------------------------------------------------------- one check's run
#
# Each adapter returns `(exit_code, summary)` and the summary is the check's
# OWN sentence wherever it has one. `bounce_stop_7day` builds its own, so it
# is quoted and never rewritten: 0140's line today is
#
#   0 PASS, 0 STOP, 0 BLIND - no mailbox sent for us in 7d across 10
#   campaigns read whole, so every rate is UNDEFINED and UNDEFINED is not a
#   pass.
#
# and summarising that into a green tick is exactly the loss this runner must
# not cause.


def _adapt_bounce_stop_7day(module, **kw):
    result = module.run(**kw)
    return result["exit_code"], result["summary"], result


def _adapt_hard_stop_check(module, **kw):
    """`check()` returns numbers and prints its sentences from `main()`.

    So the sentence here is COMPOSED from its own figures rather than quoted,
    and it says so. Its exit rule is its own: `main` returns 1 on BLIND, and
    a tripped stop or a spam complaint exits 1 through `--quiet`. Both are
    honoured, with BLIND distinguished as 2 because this runner's reader
    needs the distinction that script's two codes cannot express.
    """
    result = module.check(**kw)
    tripped, blind = result["tripped"], result["blind"]
    if tripped or result["spam"]:
        code = EXIT_STOP
    elif blind:
        code = EXIT_BLIND
    elif not result["mailboxes"]:
        # Read whole and nothing to measure. NOT a pass about any mailbox -
        # the same UNDEFINED-is-not-zero rule the bounce stop states - but
        # not a blind read either, so it is reported as the no-data it is.
        code = EXIT_PASS
    else:
        code = EXIT_PASS
    summary = (
        "HARD STOPS (composed from hard_stop_check.check, which has no "
        "summary of its own): %d mailbox(es) tripped, %d spam complaint(s), "
        "%d unsubscribed, %d mailbox(es) with sends in the window, %d "
        "under the %d-send denominator and therefore UNDEFINED, %d "
        "campaign(s) BLIND and NOT proven clean%s."
        % (len(tripped), result["spam"], result["unsubscribed"],
           result["mailboxes"], len(result["undefined"]),
           module.MIN_DENOMINATOR, len(blind),
           (" - " + ", ".join(str(c) for c in blind)) if blind else ""))
    return code, summary, {k: v for k, v in result.items() if k != "tripped"}


def _adapt_queue_wall_check(module, **kw):
    """Driven through `main(argv)`, which is where its exit rule lives.

    `main` prints; the loop captures nothing and the sentence is rebuilt from
    `queuewall.assess` so the journal row carries words rather than a bare
    code. Both come from the same call, so they cannot disagree.
    """
    import io
    import contextlib

    argv = list(kw.pop("argv", []) or [])
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        code = module.main(argv)
    text = buffer.getvalue().strip().splitlines()
    tail = [line.strip() for line in text if line.strip()]
    summary = tail[-2] if len(tail) >= 2 else (tail[-1] if tail else "")
    return code, "QUEUE WALL: %s" % (summary or "no line printed"), {
        "printed_lines": len(tail)}


ADAPTERS = {
    "bounce_stop_7day": _adapt_bounce_stop_7day,
    "hard_stop_check": _adapt_hard_stop_check,
    "queue_wall_check": _adapt_queue_wall_check,
}


def run_check(check, **kw):
    """One check, as a row. NEVER raises, and a raise is BLIND and never PASS.

    THE CATCH IS BROAD HERE AND NARROW INSIDE THE CHECKS, which is the
    opposite of `bounce_stop_7day`'s rule and deliberately so. In there a bare
    catch would turn a bug in our own row handling into a BLIND and hide it.
    Out here the runner is the thing that must survive: one check raising must
    not stop the other two being asked, and the alternative - the scheduler
    dying on a `KeyError` - is the silent stop this whole module exists for.

    What makes it safe is the direction. The exception class and message are
    recorded in the row, the verdict is BLIND, and BLIND clears nobody. A bug
    is therefore loud and non-zero rather than invisible and green.
    """
    row = {"name": check["name"], "about": check["about"]}
    started = time.time()
    try:
        module = load(check)
        adapter = ADAPTERS[check["name"]]
        code, summary, detail = adapter(module, **kw)
    except Exception as exc:                                    # noqa: BLE001
        row.update({
            "verdict": BLIND,
            "exit_code": EXIT_BLIND,
            "summary": ("%s could not run at all: %s: %s"
                        % (check["name"], type(exc).__name__,
                           str(exc)[:300])),
            "error": type(exc).__name__,
            "seconds": round(time.time() - started, 3),
        })
        return row
    row.update({
        "verdict": classify(code),
        "exit_code": code,
        "summary": summary,
        "seconds": round(time.time() - started, 3),
    })
    if isinstance(detail, dict):
        row["detail"] = {k: detail[k] for k in sorted(detail)
                         if k in ("verdict", "roster_complete", "unattributed",
                                  "unreadable", "spam", "unsubscribed",
                                  "mailboxes", "blind", "printed_lines")}
    return row


def run_checks(checks=None, per_check=None):
    """Every check in the table, in order. `per_check` is `{name: kwargs}`."""
    per_check = per_check or {}
    return [run_check(check, **per_check.get(check["name"], {}))
            for check in (CHECKS if checks is None else checks)]


# ------------------------------------------------------------- the journal
#
# ONE ROW PER ATTEMPT, appended beside the queue, so a missing attempt is
# visible as a hole rather than as silence. This is the half of the
# requirement a heartbeat cannot meet: a heartbeat says the process is alive
# and is rewritten every poll, so it carries no history and cannot show that
# last Tuesday never happened.
#
# `store.refuse_production_write` is asked before anything touches the
# filesystem, which is why this module is on `test_invariants`'
# `SELF_WRITERS` checklist.

JOURNAL_NAME = "stop-watchdog.jsonl"


def journal_path():
    """Resolved per call from `store.queue_path()`, never cached.

    Per call so `store.use_directory()` moves it with the rest of the state,
    and from the queue's own directory rather than an environment variable of
    its own: an override this module resolved itself would be a state path
    outside `store.STATE_OVERRIDES`, which is the drift
    `test_every_state_override_is_in_the_move_together_set` exists to catch.
    """
    return os.path.join(os.path.dirname(store.queue_path()), JOURNAL_NAME)


def record_attempt(row, path=None):
    """Append one attempt. Returns the row as written.

    APPEND, not replace. The record's value is entirely in its continuity -
    a rewritten file would answer "what happened last time" and never "did
    the schedule hold", and the second question is this task's.
    """
    target = path or journal_path()
    store.refuse_production_write(target)
    payload = json.dumps(row, ensure_ascii=False, default=str) + "\n"
    os.makedirs(os.path.dirname(target), exist_ok=True)
    handle = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    try:
        os.write(handle, payload.encode("utf-8"))
    finally:
        os.close(handle)
    return row


def attempts(path=None):
    """Every recorded attempt, oldest first. A bad line is REPORTED.

    An unparseable line comes back as `{"epoch": None, "unreadable": ...}`
    rather than being dropped, because a damaged record is a fault in the
    instrument and dropping it would restore the silence this file removes.
    `gaps()` turns such a row into a DAMAGED gap.
    """
    target = path or journal_path()
    if not os.path.exists(target):
        return []
    out = []
    with open(target, encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except ValueError as exc:
                out.append({"epoch": None, "line": number,
                            "unreadable": "%s: %s" % (type(exc).__name__, exc)})
                continue
            if not isinstance(row, dict):
                out.append({"epoch": None, "line": number,
                            "unreadable": "not an object"})
                continue
            if not isinstance(row.get("epoch"), (int, float)):
                row = dict(row, epoch=None,
                           unreadable="no numeric epoch on line %d" % number)
            out.append(row)
    return sorted(out, key=lambda r: (r.get("epoch") is None,
                                      r.get("epoch") or 0))


# ------------------------------------------------------------------- gaps

#: How many scheduled passes may be missed before the record has a gap.
#:
#: TWO, not one. A single missed pass is a slow provider read or a machine
#: that was asleep for a minute; two in a row is the scheduler. Set here
#: rather than inside the rule so the number is one thing a test can move.
GAP_FACTOR = 2.0

NEVER, OPEN, MISSED, DAMAGED = "NEVER", "OPEN", "MISSED", "DAMAGED"


def gaps(rows, every, now=None, factor=GAP_FACTOR):
    """Where the schedule did not hold. A list, empty only when it did.

    FOUR KINDS, because they are four different facts:

        NEVER     no attempt has ever been recorded. Not "nothing to report".
        OPEN      the last attempt is older than the schedule allows, so the
                  scheduler is not firing NOW. This is the live one.
        MISSED    a hole between two recorded attempts. Historical.
        DAMAGED   a journal line that will not parse, so the continuity
                  either side of it cannot be proven.

    `every` is the pass cadence in seconds. A tolerance of `factor` passes is
    allowed before a hole is called a gap - see `GAP_FACTOR`.
    """
    now = time.time() if now is None else now
    every = float(every)
    if every <= 0:
        raise ValueError("a cadence of %r seconds cannot be assessed" % every)
    tolerance = every * factor
    out = []
    dated = []
    for row in rows or []:
        if row.get("epoch") is None:
            out.append({"kind": DAMAGED, "line": row.get("line"),
                        "why": "a recorded attempt cannot be read: %s"
                               % (row.get("unreadable") or "no epoch")})
            continue
        dated.append(row)
    dated.sort(key=lambda r: r["epoch"])
    if not dated:
        out.append({
            "kind": NEVER, "seconds": None, "missed": None,
            "why": "no attempt has ever been recorded, so nothing has been "
                   "checked. An empty record is not a clean one."})
        return out
    for before, after in zip(dated, dated[1:]):
        delta = after["epoch"] - before["epoch"]
        if delta > tolerance:
            out.append({
                "kind": MISSED, "seconds": round(delta, 1),
                "missed": int(delta // every) - 1,
                "from": before.get("at"), "to": after.get("at"),
                "why": "%.0fs between two attempts on a %.0fs cadence - "
                       "about %d pass(es) never ran"
                       % (delta, every, max(1, int(delta // every) - 1))})
    since = now - dated[-1]["epoch"]
    if since > tolerance:
        out.append({
            "kind": OPEN, "seconds": round(since, 1),
            "missed": int(since // every),
            "from": dated[-1].get("at"), "to": None,
            "why": "the last attempt was %.0fs ago on a %.0fs cadence - the "
                   "schedule is NOT firing now"
                   % (since, every)})
    return out


# --------------------------------------------------------------- controls
#
# Three, run every pass, each with its expected answer written down beside
# it. They exist because of this repository's own B7 instrument: a check that
# has never been seen to fail is not evidence that nothing is wrong.
#
# NO PROVIDER CALL AND NO NETWORK. Controls 1 and 2 drive the REAL
# `bounce_stop_7day.run` over a planted row source, which is why that
# function grew a `rows_source` seam; control 3 drives the real `gaps`.


def _planted_rows(mailbox, sent, bounced, stamp):
    rows = [{"id": 1 + i, "status": "bounced", "sent_at": stamp,
             "sender_email": {"id": mailbox}} for i in range(bounced)]
    rows += [{"id": 1000 + i, "status": "sent", "sent_at": stamp,
              "sender_email": {"id": mailbox}} for i in range(sent)]
    return rows


def controls(now=None):
    """The three controls, as rows. `ok` is False the moment one disagrees.

    Each row carries what was planted, what the instrument was expected to
    answer and what it did answer, so a failing control names the difference
    rather than only asserting one.
    """
    from src.providers import bison

    when = (datetime.datetime.now(datetime.timezone.utc) if now is None
            else now)
    stamp = when.strftime("%Y-%m-%dT%H:%M:%SZ")
    out = []

    bounce = load(CHECKS[0])

    # 1. A PLANTED OVER-THRESHOLD MAILBOX PRODUCES STOP.
    planted = {487: _planted_rows(999001, sent=96, bounced=4, stamp=stamp)}
    try:
        result = bounce.run(days=7, campaigns=(487,),
                            rows_source=lambda cid, cap=None: planted[cid])
        observed = (result["verdict"], result["exit_code"])
    except Exception as exc:                                    # noqa: BLE001
        observed = ("RAISED", "%s: %s" % (type(exc).__name__, exc))
    out.append({
        "control": "an over-threshold mailbox produces STOP",
        "planted": "mailbox 999001, 4 bounced of 100 in-window = 4.00%",
        "expected": [STOP, EXIT_STOP],
        "observed": list(observed),
        "ok": observed == (STOP, EXIT_STOP)})

    # 2. A PLANTED UNREADABLE CAMPAIGN PRODUCES BLIND AND A NON-ZERO EXIT.
    def _refuse(cid, cap=None):
        raise bison.PartialInventory(
            "planted control: %s pages to walk and this read stops at %s"
            % (45, cap))

    try:
        result = bounce.run(days=7, campaigns=(491,), rows_source=_refuse)
        observed = (result["verdict"], result["exit_code"])
    except Exception as exc:                                    # noqa: BLE001
        observed = ("RAISED", "%s: %s" % (type(exc).__name__, exc))
    out.append({
        "control": "an unreadable campaign produces BLIND and a non-zero exit",
        "planted": "campaign 491 raising PartialInventory at the page cap",
        "expected": [BLIND, EXIT_BLIND],
        "observed": list(observed),
        "ok": observed == (BLIND, EXIT_BLIND) and observed[1] != 0})

    # 3. A PASS THE SCHEDULER NEVER FIRED IS VISIBLE AS A GAP.
    #
    # The one control the other two cannot stand in for, and the reason this
    # task exists: without it the runner is clean because it never ran.
    every = 3600
    base = 1_760_000_000
    planted_rows = [{"epoch": base, "at": "planted-1"},
                    {"epoch": base + every, "at": "planted-2"},
                    # four cadences of nothing
                    {"epoch": base + every * 5, "at": "planted-3"}]
    found = gaps(planted_rows, every=every, now=base + every * 5)
    kinds = [g["kind"] for g in found]
    empty = [g["kind"] for g in gaps([], every=every, now=base)]
    out.append({
        "control": "a pass the scheduler never fired is a gap in the record",
        "planted": "three attempts on a 3600s cadence with four missing, "
                   "and separately an empty record",
        "expected": [[MISSED], [NEVER]],
        "observed": [kinds, empty],
        "ok": kinds == [MISSED] and empty == [NEVER]
              and found[0]["missed"] == 3})

    for row in out:
        row["ok"] = bool(row["ok"])
    return out


# ------------------------------------------------------------- the assessment


def assess(results, journal_rows, every, now=None, control_rows=None):
    """One verdict over the checks, the record and the controls.

    ORDER, and every step of it is the same rule: the thing that cannot be
    shown to be safe is not safe.

        any check STOP                     -> STOP
        any check BLIND, any gap, or a
        control that did not hold           -> BLIND
        no check ran at all                 -> BLIND
        otherwise                           -> PASS

    A STOP wins the headline and the BLIND and GAP counts are still in the
    sentence. `bounce_stop_7day._summary` learnt that one level down: an
    unreadable campaign beside a stopped mailbox produced no blinded mailbox
    and therefore no BLIND in its own line, which is this same disappearance.
    """
    results = list(results or [])
    control_rows = list(control_rows or [])
    found = gaps(journal_rows, every=every, now=now)
    counts = {verdict: sum(1 for r in results if r.get("verdict") == verdict)
              for verdict in VERDICTS}
    bad_controls = [c for c in control_rows if not c.get("ok")]

    if counts[STOP]:
        verdict = STOP
    elif counts[BLIND] or found or bad_controls or not results:
        verdict = BLIND
    else:
        verdict = PASS

    reasons = []
    if counts[STOP]:
        reasons.append("%d check(s) STOPPED" % counts[STOP])
    if counts[BLIND]:
        reasons.append("%d check(s) BLIND" % counts[BLIND])
    if found:
        reasons.append("%d gap(s) in the record (%s)"
                       % (len(found),
                          ", ".join(sorted({g["kind"] for g in found}))))
    if bad_controls:
        reasons.append("%d of %d control(s) DID NOT HOLD, so this pass proves "
                       "nothing" % (len(bad_controls), len(control_rows)))
    if not results:
        reasons.append("no check ran at all")

    out = {
        "verdict": verdict,
        "exit_code": EXIT[verdict],
        "checks": results,
        "counts": counts,
        "gaps": found,
        "controls": control_rows,
        "controls_ok": not bad_controls,
        "every": every,
        "why": "; ".join(reasons) or "every check answered 0, the record is "
                                     "continuous and all controls held",
    }
    out["summary"] = summary_line(out)
    return out


def summary_line(assessment):
    """The one sentence an operator reads. All three counts, always.

    Never a tick. The words STOP, BLIND and GAP appear with their numbers
    whichever verdict won, because this runner's whole purpose is that a
    number does not disappear into a greener one.
    """
    counts = assessment["counts"]
    total = len(assessment["checks"])
    gap_kinds = ", ".join(sorted({g["kind"] for g in assessment["gaps"]}))
    controls_held = sum(1 for c in assessment["controls"] if c.get("ok"))
    tail = ("DO NOT SEND until a human has read this."
            if assessment["verdict"] != PASS else
            "Nothing is over a line and nothing is unmeasured.")
    return (
        "STOP WATCHDOG %s: %d STOP, %d PASS, %d BLIND of %d check(s); "
        "%d gap(s) in the record%s; controls %d/%d held. %s"
        % (assessment["verdict"], counts[STOP], counts[PASS], counts[BLIND],
           total, len(assessment["gaps"]),
           (" (%s)" % gap_kinds) if gap_kinds else "",
           controls_held, len(assessment["controls"]), tail))
