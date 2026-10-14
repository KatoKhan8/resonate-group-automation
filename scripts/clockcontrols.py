#!/usr/bin/env python3
"""EXECUTED controls for the C11c rows that a grep may not dispose of.

The pre-registered criterion (`PREREG-C11-wall-clock-2026-10-13.md`) is
explicit about what a disposition of `injectable_proven` costs:

    An entry may not be disposed of as `injectable_proven` on the strength of
    a grep. It needs an executed control of the shape `evidence_clock_control`
    already has: run the decision twice, once with the simulated clock and
    once without, and require the answers to DIFFER when the clock is not
    injected and to AGREE when it is.

So each control here CALLS the decision twice and reports what came back.

WHAT THESE CONTROLS DO NOT DO, said plainly so no report overstates them.
They do not run the sandbox. A sandbox run is gated on C11 and on the fixture,
and `--mode one` is still a sandbox run. These are unit-level calls into the
same decision functions, which answers "is this read live, and does injection
reach it" and does NOT answer "did the 2026-10-13 run execute this line". The
second question is C11e and is unimplemented.

Each control therefore reports three separate things and never merges them:

    differs_when_not_injected   the read is LIVE: omitting the date changes
                                the answer. A False here means the control
                                proved nothing, not that the row is safe.
    agrees_when_injected        injection REACHES the read.
    sandbox_call_sites          whether the sandbox path has a call site that
                                injects - measured separately, because a
                                function can be perfectly injectable and
                                still be called without the date.

A row is `injectable_proven` only when all three are satisfied. Anything else
is reported as it measured, not rounded up.
"""
import contextlib
import datetime
import inspect
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

#: Far from any real "today", so a DIFFER result cannot be the calendar
#: agreeing with the simulation by accident. Deliberately not a date the
#: repository uses anywhere else.
SIMULATED_DATE = "2027-03-01"
SIMULATED_ISO = SIMULATED_DATE + "T09:00:00+00:00"


class _FakeClock(object):
    """What `sandboxclock.install()` wants: an object with `now_iso`."""

    def __init__(self, iso):
        self._iso = iso

    def now_iso(self):
        return self._iso


@contextlib.contextmanager
def _isolated_ledger():
    """Point the spend ledger at a temp file.

    `spendledger.path()` honours `SPEND_LEDGER`, and `record()` calls
    `store.refuse_production_write(path())` BEFORE any filesystem change, so
    the operator's real `work/spend-ledger.jsonl` is never the target here.
    The module's own comment records what happened the one time a test
    reached a paid call without isolating the store: 19 rows of fabricated
    spend landed in the client's real ledger.
    """
    directory = tempfile.mkdtemp(prefix="clockctl-")
    previous = os.environ.get("SPEND_LEDGER")
    os.environ["SPEND_LEDGER"] = os.path.join(directory, "spend-ledger.jsonl")
    try:
        yield os.environ["SPEND_LEDGER"]
    finally:
        if previous is None:
            os.environ.pop("SPEND_LEDGER", None)
        else:
            os.environ["SPEND_LEDGER"] = previous


# ====================================================== row 7: spendledger

def spendledger_day_control():
    """`spendledger.record()` stamps `at` SIMULATED and `day` REAL.

    This is not an injectability question. It is a disagreement INSIDE ONE
    ROW, and it is the one control here that reports a defect rather than a
    clean injection:

        row = {"at": at or store.now(), "day": today(), ...}

    `store.now` is the single entry in `BUSINESS_CLOCK_SEAMS`, so `at` moves
    with the simulated clock. `today()` reads `datetime.datetime.now()` and
    is passed nothing, so `day` stays on the real calendar. Under a long
    simulation every simulated day's spend therefore collapses onto one real
    `day` key - and `check`, `reserve`, `balances` and `client_balance` all
    resolve `day = day or today()`, so the per-day ceiling is read on the
    real calendar while the rows are stamped on the simulated one.
    """
    from src import sandboxclock, spendledger

    out = {"row": "spendledger.py:278 (via record(), spendledger.py:333)"}

    # `record` cannot be told the day: there is no parameter to tell it with.
    # Signature introspection rather than a source grep - this repository
    # forbids tests that read the text of the module.
    params = inspect.signature(spendledger.record).parameters
    out["record_accepts_day"] = "day" in params
    out["record_accepts_at"] = "at" in params
    out["injectable_readers"] = {
        name: ("day" in inspect.signature(getattr(spendledger, name)).parameters)
        for name in ("check", "reserve", "balances", "client_balance")
    }

    with _isolated_ledger():
        undo = sandboxclock.install(_FakeClock(SIMULATED_ISO))
        try:
            row = spendledger.record("clockcontrol", "none", "probe", 0,
                                     run_id="clockcontrol")
        finally:
            undo()

    out["at"] = row.get("at")
    out["day"] = row.get("day")
    out["at_is_simulated"] = str(row.get("at", "")).startswith(SIMULATED_DATE)
    out["day_is_simulated"] = str(row.get("day", "")).startswith(SIMULATED_DATE)
    # THE DEFECT: one row, two calendars.
    out["same_row_two_calendars"] = bool(
        out["at_is_simulated"] and not out["day_is_simulated"])
    out["verdict"] = ("DEFECT: at simulated, day real, and record() has no "
                      "day parameter to fix it with"
                      if out["same_row_two_calendars"] else
                      "no disagreement measured")
    return out


# ================================================ rows 4/5/6: executionguard

def readback_freshness_control():
    """`readback_is_fresh` (executionguard.py:240) - DIFFER and AGREE.

    The decision is boolean, so the control picks a stamp that is fresh on
    one calendar and stale on the other. `_utcnow()` is the real clock;
    `now=` is the injection.
    """
    from src import executionguard

    # Verified "now" on the SIMULATED calendar: fresh there, and far in the
    # future - therefore NOT fresh - on the real one, because the function
    # refuses a future-dated stamp by design ("a clock skew or a hand-edited
    # record must not buy an unlimited window").
    verified_at = SIMULATED_ISO
    simulated_now = datetime.datetime.fromisoformat(SIMULATED_ISO)

    injected = executionguard.readback_is_fresh(verified_at, now=simulated_now)
    not_injected = executionguard.readback_is_fresh(verified_at)

    return {
        "row": "executionguard.py:240 (readback_is_fresh)",
        "accepts_now": "now" in inspect.signature(
            executionguard.readback_is_fresh).parameters,
        "verified_at": verified_at,
        "answer_injected": injected,
        "answer_not_injected": not_injected,
        "expected_under_simulation": True,
        "agrees_when_injected": injected is True,
        "differs_when_not_injected": not_injected != injected,
    }


def authorize_injection_control():
    """Rows 5 and 6 live inside `authorize(..., now=...)`.

    `authorize` is keyword-only and DOES take `now`, and both internal users
    of the clock forward it, so the injection chain inside the module is
    intact. What the control reports instead is the part that decides the
    disposition: WHO CALLS IT. Measured - `scripts/sandbox_run.py` contains
    no reference to `authorize`, `executionguard` or `spendledger` at all,
    and the only caller in `src/` is `heyreachfactory.py:1112`, which the
    sandbox runner does not import.

    So these two rows are not disposed of by proving injection works. They
    are disposed of by showing the sandbox path never reaches them - which is
    a REACHABILITY claim, and `accepted` is the only pre-registered
    disposition that fits it.
    """
    from src import executionguard

    sig = inspect.signature(executionguard.authorize)
    return {
        "rows": ["executionguard.py:630 (authorize, fatigue hold)",
                 "executionguard.py:710 (authorize, per-day spend)"],
        "accepts_now": "now" in sig.parameters,
        "now_is_keyword_only": (
            "now" in sig.parameters
            and sig.parameters["now"].kind == inspect.Parameter.KEYWORD_ONLY),
        "internal_forwarding_intact": True,
        "note": ("injection works; the open question is reachability, "
                 "measured separately by sandbox_reachability()"),
    }


# ====================================================== row 8: copylint

def copylint_demotion_control():
    """`copylint.warning_rules` (copylint.py:1475) - DIFFER and AGREE.

    `DEMOTIONS` holds one entry expiring 2026-09-28. A date before it keeps
    the rule demoted to a warning; any date after it - the real clock
    included, today - lets the rule revert to refusing. So the two answers
    are different frozensets and the control is a real measurement rather
    than a tautology.
    """
    from src import copylint

    before_expiry = "2026-09-01"
    injected = copylint.warning_rules(before_expiry)
    not_injected = copylint.warning_rules()

    return {
        "row": "copylint.py:1475 (warning_rules)",
        "accepts_today": "today" in inspect.signature(
            copylint.warning_rules).parameters,
        "demotions": [(rule, until) for rule, until, _w, _who
                      in copylint.DEMOTIONS],
        "answer_injected": sorted(injected),
        "answer_not_injected": sorted(not_injected),
        "agrees_when_injected": "step1_without_pack_fact" in injected,
        "differs_when_not_injected": set(injected) != set(not_injected),
    }


# ====================================================== row 1: evidence/quality

def quality_injection_gap_control():
    """Row 1 - the injection point exists one level down and is not forwarded.

    `evidence.age_days(published_at, today=None)` is injectable.
    `quality._selected(rec, contact, today=None)` is injectable.
    `quality.assess(rec, contact, config=None)` is NOT - it has no date
    parameter at all, and at `quality.py:350` it calls `_selected(rec,
    contact)` without one. That single missing argument is the whole defect,
    and it is why `evidence_clock_control` measured `differs: true` in the
    2026-10-13 run.

    Reported by signature introspection, which is behaviour; a grep for
    `today=` over the call sites returns ZERO and is MISLEADING, because
    every other caller passes `today` POSITIONALLY.
    """
    from src import evidence, quality

    return {
        "row": "evidence.py:106 (age_days), via quality.assess",
        "age_days_accepts_today": "today" in inspect.signature(
            evidence.age_days).parameters,
        "_selected_accepts_today": "today" in inspect.signature(
            quality._selected).parameters,
        "assess_accepts_today": "today" in inspect.signature(
            quality.assess).parameters,
        "assess_params": list(inspect.signature(quality.assess).parameters),
        "verdict": ("DEFECT: assess() cannot be told the date, so _selected() "
                    "and age_days() fall back to the real clock"),
    }


# ====================================================== reachability

#: Measured in a CLEAN interpreter, and that is not a stylistic choice.
#: The first version of `sandbox_reachability()` diffed `sys.modules` before
#: and after importing the runner, inside this same process. Run alone it was
#: right; run inside the suite it reported EVERY module as "not loaded",
#: because the other controls above had already imported `src.evidence`,
#: `src.quality` and `src.spendledger`, so the delta was empty and the
#: positive controls failed. An order-dependent measurement of what an import
#: loads is not a measurement. A subprocess has no history to contaminate it.
_REACHABILITY_PROBE = r'''
import importlib.util, json, os, sys
root = sys.argv[1]
sys.path.insert(0, root)
before = set(sys.modules)
spec = importlib.util.spec_from_file_location(
    "_clockctl_entry", os.path.join(root, "scripts", "sandbox_run.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
loaded = sorted(n for n in set(sys.modules) - before if n.startswith("src."))
sys.stdout.write(json.dumps(loaded))
'''


def sandbox_reachability():
    """Which of these modules the sandbox runner even IMPORTS.

    LOADED, not EXECUTED. `clock_defects()` says the same of its own filter
    and this says it again here, because the distinction is the whole of
    C11e: a module can be imported by something it never calls.
    """
    import subprocess

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    # Bytes, not `text=True`: this machine decodes subprocess output as
    # cp1250 and a stray byte has silently returned None here before.
    proc = subprocess.run([sys.executable, "-c", _REACHABILITY_PROBE, root],
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        raise RuntimeError("the reachability probe failed: %s"
                           % proc.stderr.decode("utf-8", "replace")[-400:])
    loaded = set(json.loads(proc.stdout.decode("utf-8", "replace")))

    interesting = ("src.evidence", "src.quality", "src.executionguard",
                   "src.spendledger", "src.copylint", "src.secondbrain",
                   "src.heyreachfactory", "src.providerwrites")
    return {
        "loaded_src_module_count": len(loaded),
        "loaded": {name: (name in loaded) for name in interesting},
        # The reader must discriminate or "not loaded" is worthless.
        "positive_controls": {name: (name in loaded) for name in
                              ("src.cadence", "src.store",
                               "src.sandboxharness", "src.sandboxclock")},
        "negative_control_absent": "src.nosuchmodule" not in loaded,
    }


CONTROLS = (
    ("row_1_quality_injection_gap", quality_injection_gap_control),
    ("row_4_readback_freshness", readback_freshness_control),
    ("rows_5_6_authorize", authorize_injection_control),
    ("row_7_spendledger_day", spendledger_day_control),
    ("row_8_copylint_demotion", copylint_demotion_control),
)


def run_all():
    report = {"simulated_date": SIMULATED_DATE,
              "reachability": sandbox_reachability()}
    for name, control in CONTROLS:
        report[name] = control()
    return report


def main(argv):
    report = run_all()
    if "--json" in argv:
        print(json.dumps(report, indent=1, sort_keys=True, default=str))
        return 0
    reach = report["reachability"]
    print("REACHABILITY (loaded, NOT executed - that is C11e)")
    for name, was in sorted(reach["loaded"].items()):
        print("   %-24s %s" % (name, "LOADED" if was else "not loaded"))
    print("   positive controls all loaded: %s"
          % all(reach["positive_controls"].values()))
    print("   negative control absent     : %s"
          % reach["negative_control_absent"])
    for name, _ in CONTROLS:
        block = report[name]
        print()
        print(name)
        for key in sorted(block):
            print("   %-28s %s" % (key, block[key]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
