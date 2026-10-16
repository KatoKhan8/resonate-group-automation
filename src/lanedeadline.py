"""How long has this lane got left, and does the next suite leg fit inside it?

WHY THIS EXISTS, MEASURED 2026-10-15 (qwen TASK 0150, and 0090 before it).
A lane task runs under a watcher that kills its whole process tree at a
deadline. The watcher computes that deadline (`docs/ops/lane_watcher.ps1`) and
until now told the child NOTHING, so a task could not tell a 15-minute
remainder from a 90-minute one. Two costs were measured the same night:

* `glm 0065` and `pilotcaps 0130` were killed at exactly 90:00 while doing real
  work, and their real processes carried on for 25 and 64 minutes afterwards
  with no watcher left to record a DONE line. Neither was hung.
* `webapp/0040` read the lock by hand, wrote `NOT OBTAINED` at ~23:52 against a
  holder that released at 23:55:33, and had 38 minutes left at that moment. Its
  arithmetic was invented on the spot, because nothing published either number.

So the watcher now exports `LANE_DEADLINE` into the child's environment and
this module is the only reader of it. The variable carries the DEADLINE as an
ISO-8601 instant, never a duration: a duration cannot survive a restart or a
task that began ten minutes ago, and would quietly lie about both.

WHAT IT DOES NOT DO. It gates nothing on its own. `decide()` returns a verdict
and the arithmetic behind it; a caller opts in (`scripts/run_suite.py --legs N`)
and a caller that does not opt in behaves exactly as it did before this module
existed. That is deliberate: `LANE_DEADLINE` is absent from every shell that is
not a lane child, and a module that refused on its absence by default would
have stopped the operator's own runs.

UNKNOWN IS NOT PERMISSION. An unset or unparseable deadline is `UNKNOWN`, and
`may_start` is False for `UNKNOWN` exactly as it is for `REFUSE`. The caller
cannot accidentally read "I could not tell" as "go ahead", which is invariant 0
applied to this one number.
"""
import datetime
import os

#: The environment variable the watcher sets. One name, one authority.
ENV_VAR = "LANE_DEADLINE"

#: WHERE THE SUITE FIGURES COME FROM, AND THEY ARE MEASURED RATHER THAN CHOSEN.
#:
#: A REFERENCE PAIR - the branch run and the master-reference run that every
#: merge gate needs - costs **78 to 91 minutes** of suite time. The ends of that
#: range are two independent measurements:
#:
#:   78 min   qwen TASK 0090: `glm 0065`'s two legs, 2267.7s + 2355.3s = 77.0 min
#:   91 min   qwen TASK 0150: a real leg is 2,233-3,456 s, so two long legs
#:
#: `LEG_MINUTES` is the upper end halved, so `leg_cost_minutes(2)` is exactly
#: the measured worst pair and nothing is rounded in the optimistic direction.
PAIR_MINUTES_MEASURED = (78.0, 91.0)
LEG_MINUTES = PAIR_MINUTES_MEASURED[1] / 2.0

#: The longest SINGLE leg ever measured here: 3,456.1 s, the complete run
#: `pilotcaps/0170` left behind on 2026-10-15 (294 names, not partial).
#:
#: It matters because it is LONGER than `LEG_MINUTES`. A one-leg estimate of
#: 45.5 minutes would have understated that run by twelve, so the cost of a
#: single leg is never quoted below the widest leg on record.
WIDEST_LEG_MINUTES = 57.6

#: What a lane needs AFTER the suite exits: read the verdict, diff by name both
#: directions, write the lane entry, commit.
#:
#: THIS FIGURE IS DECLARED, NOT MEASURED, AND SAYING SO IS THE POINT. Nothing on
#: this machine has ever timed the write-up separately from the work, so the
#: honest authority is UNKNOWN. Ten minutes is a floor chosen to be smaller than
#: any plausible real value, every verdict prints it as a named line, and
#: `--reserve-minutes` overrides it - so a reader who knows better can recompute
#: the decision instead of believing this constant.
RESERVE_MINUTES = 10.0


def leg_cost_minutes(legs=1, leg_minutes=LEG_MINUTES):
    """What `legs` suite legs cost, in minutes, conservatively.

    Never below `WIDEST_LEG_MINUTES` for a run of one or more legs, because the
    widest single leg on record is longer than the pair-derived average leg and
    an estimate that undercuts a measurement is not an estimate.
    """
    count = int(legs)
    if count <= 0:
        return 0.0
    return max(float(count) * float(leg_minutes), WIDEST_LEG_MINUTES)


def parse(text):
    """An ISO-8601 instant as an aware datetime, or None. Never raises.

    A value with no offset is read as LOCAL time and that is recorded in the
    verdict's `source`, because this machine is the only clock involved and
    refusing a naive stamp would make the feature unavailable to any writer that
    formats one.
    """
    if not text:
        return None
    value = str(text).strip()
    if not value:
        return None
    if value.endswith(("Z", "z")):
        value = value[:-1] + "+00:00"
    try:
        parsed = datetime.datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None
    if parsed.tzinfo is None:
        # Naive -> aware at the local offset. `astimezone` on a naive value
        # assumes it is local, which is the only reading available.
        parsed = parsed.astimezone()
    return parsed


def now():
    """Now, aware, at the local offset."""
    return datetime.datetime.now(datetime.timezone.utc).astimezone()


def deadline(env=None):
    """This lane's kill time as an aware datetime, or None when unknown."""
    source = os.environ if env is None else env
    return parse(source.get(ENV_VAR))


def remaining_minutes(env=None, at=None):
    """Minutes left before the watcher kills this lane, or None when UNKNOWN.

    Negative when the deadline has already passed, which is a real state: a
    task whose tree-kill has not landed yet is still running.
    """
    end = deadline(env)
    if end is None:
        return None
    return (end - (at or now())).total_seconds() / 60.0


def decide(legs=1, env=None, at=None, reserve_minutes=RESERVE_MINUTES,
           leg_minutes=LEG_MINUTES):
    """Does a run of `legs` suite legs fit in what is left? With its arithmetic.

    Returns a dict. `decision` is one of:

        RUN       there is room: minutes_left >= minutes_needed
        REFUSE    there is not
        UNKNOWN   the deadline could not be read at all

    `may_start` is False for REFUSE **and** for UNKNOWN. A caller reading only
    that field cannot turn "I could not tell" into permission.
    """
    source = os.environ if env is None else env
    raw = source.get(ENV_VAR)
    moment = at or now()
    end = parse(raw)
    cost = leg_cost_minutes(legs, leg_minutes=leg_minutes)
    reserve = float(reserve_minutes)
    needed = cost + reserve

    if raw is None or str(raw).strip() == "":
        why = "%s is not set in this environment" % ENV_VAR
        origin = "unset"
    elif end is None:
        why = "%s=%r is not an ISO-8601 instant" % (ENV_VAR, raw)
        origin = "unparseable"
    else:
        why = None
        origin = ENV_VAR

    verdict = {
        "decision": "UNKNOWN" if end is None else None,
        "may_start": False,
        "source": origin,
        "env_var": ENV_VAR,
        "raw": raw,
        "now": moment.isoformat(timespec="seconds"),
        "deadline": end.isoformat(timespec="seconds") if end else None,
        "minutes_left": None,
        "legs": int(legs),
        "minutes_per_leg": float(leg_minutes),
        "minutes_the_legs_cost": cost,
        "reserve_minutes": reserve,
        "minutes_needed": needed,
        "widest_leg_measured": WIDEST_LEG_MINUTES,
        "pair_measured": list(PAIR_MINUTES_MEASURED),
        "why": why,
    }

    if end is None:
        verdict["arithmetic"] = (
            "UNKNOWN: %s. A leg of this shape costs %.1f min and the reserve is "
            "%.1f, so %.1f min would be needed - but the remainder cannot be "
            "read, and UNKNOWN is not permission to start."
            % (why, cost, reserve, needed))
        return verdict

    left = (end - moment).total_seconds() / 60.0
    verdict["minutes_left"] = left
    fits = left >= needed
    verdict["decision"] = "RUN" if fits else "REFUSE"
    verdict["may_start"] = bool(fits)
    verdict["arithmetic"] = (
        "%s: %.1f min left (deadline %s, now %s) %s %.1f min needed "
        "= %d leg(s) x %.1f min (pair measured %.0f-%.0f, widest single leg "
        "%.1f) + %.1f min reserve (declared, not measured)."
        % (verdict["decision"], left, verdict["deadline"], verdict["now"],
           ">=" if fits else "<", needed, int(legs), float(leg_minutes),
           PAIR_MINUTES_MEASURED[0], PAIR_MINUTES_MEASURED[1],
           WIDEST_LEG_MINUTES, reserve))
    return verdict


def describe(verdict=None, legs=1, env=None):
    """The verdict as the block a lane pastes into its record.

    Every number that went into the decision is a named line, so a reader can
    redo the arithmetic rather than trust the word at the bottom.
    """
    verdict = verdict if verdict is not None else decide(legs=legs, env=env)
    left = verdict["minutes_left"]
    rows = [
        ("deadline", verdict["deadline"] or "UNKNOWN (%s)" % verdict["source"]),
        ("now", verdict["now"]),
        ("minutes left", "UNKNOWN" if left is None else "%.1f" % left),
        ("legs", str(verdict["legs"])),
        ("minutes the leg(s) cost", "%.1f" % verdict["minutes_the_legs_cost"]),
        ("reserve (declared)", "%.1f" % verdict["reserve_minutes"]),
        ("minutes needed", "%.1f" % verdict["minutes_needed"]),
        ("decision", verdict["decision"]),
    ]
    width = max(len(name) for name, _ in rows)
    lines = ["%s: %s" % (ENV_VAR, verdict["decision"])]
    lines += ["  %-*s  %s" % (width, name, value) for name, value in rows]
    lines.append("  " + verdict["arithmetic"])
    return "\n".join(lines)
