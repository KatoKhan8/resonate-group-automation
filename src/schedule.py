#!/usr/bin/env python3
"""When each cadence step would land, in the prospect's own local time.

## Why this is a module and not a display detail

`geo.send_window()` already converts one local window on one date into UTC.
What was missing is the thing anybody actually wants to look at: a whole
cadence, for a whole batch, with the UTC instants each step would fire at. A
batch spanning London, New York, Zagreb and Sydney has no single "09:30" - it
has four, they are 15 hours apart, and two of them change by an hour on
different weekends.

Three rules the module is built around:

**A guessed timezone is worse than a missing one.** A missing timezone stops
the send and says so; a guessed one sends confidently at 04:00. Where
`geo.schedulable()` refuses, this returns a held step with the reason, never a
time.

**Offsets are computed, never stored.** Every instant goes through the IANA
zone on its own date, so the answer moves with daylight saving instead of
being right for half the year. `utc_offset_hours` is reported as a fact about
that date rather than a property of the company.

**A step outside the sending days moves forward, and says so.** Day 3 of a
cadence that starts on a Thursday is a Sunday. Silently sending on the Sunday
and silently dropping the step are both wrong; it rolls to Monday and the roll
is on the record.

Nothing here sends, and nothing here writes to the queue.

  python -m src.schedule --demo
  python -m src.schedule --record <id> --start 2026-09-01
"""
import argparse
import datetime
import json

from . import cadence, clients, geo, segments, store

# Where in the window a step is placed. A step fired at the very start of every
# window would put every prospect in the world at exactly 09:00 local, which is
# both the busiest minute of the inbox and an obvious machine signature.
# Spreading them across the window is one line here and invisible downstream.
DEFAULT_OFFSETS = {
    "email": 30,        # minutes past the window start
    "linkedin": 45,
}

HELD = "held"
SCHEDULED = "scheduled"
ROLLED = "rolled_forward"


def settings(config):
    """Per-channel placement inside the window, in minutes past its start."""
    block = ((config or {}).get("scheduling") or {}).get("offsets") or {}
    merged = dict(DEFAULT_OFFSETS)
    for channel in DEFAULT_OFFSETS:
        try:
            value = int(block[channel])
        except (KeyError, TypeError, ValueError):
            continue
        if value >= 0:
            merged[channel] = value
    return merged


def _window_minutes(spec):
    start = geo._parse_time(spec["start"])
    end = geo._parse_time(spec["end"])
    return (end.hour * 60 + end.minute) - (start.hour * 60 + start.minute)


def place(timezone, on, channel, config=None):
    """One step, on one local date, as a UTC instant.

    Returns the same shape whether or not it could be scheduled, so a caller
    never has to branch on presence to find out what happened.
    """
    base = {"channel": channel, "timezone": timezone,
            "requested_date": on.isoformat()}

    window = geo.send_window(timezone, on, config, channel=channel)
    if not window.get("ok"):
        return dict(base, status=HELD, why=window.get("reason"),
                    local_at=None, utc_at=None)

    days = geo.windows(config)["days"]
    rolled = 0
    while on.isoweekday() not in days:
        on += datetime.timedelta(days=1)
        rolled += 1
        if rolled > 7:                      # no configured sending day at all
            return dict(base, status=HELD, local_at=None, utc_at=None,
                        why="no sending day is configured")
        window = geo.send_window(timezone, on, config, channel=channel)
        if not window.get("ok"):
            return dict(base, status=HELD, why=window.get("reason"),
                        local_at=None, utc_at=None)

    spec = geo.windows(config)[channel]
    offset = settings(config)[channel]
    # Never past the end of the window: a client with a 30-minute window and a
    # 45-minute offset would otherwise send outside the hours it configured.
    offset = min(offset, max(0, _window_minutes(spec)))

    tz = geo.zone(timezone)
    local = (datetime.datetime.combine(on, geo._parse_time(spec["start"]),
                                       tzinfo=tz)
             + datetime.timedelta(minutes=offset))
    utc = local.astimezone(datetime.timezone.utc)

    return dict(
        base,
        status=ROLLED if rolled else SCHEDULED,
        date=on.isoformat(),
        local_at=local.isoformat(),
        utc_at=utc.isoformat(),
        # A fact about this instant, not about this company: the same company
        # has a different offset in January and July.
        utc_offset_hours=local.utcoffset().total_seconds() / 3600,
        is_dst=bool(local.dst()),
        window_local=f"{spec['start']}-{spec['end']}",
        why=(f"rolled forward {rolled} day(s) to the next sending day"
             if rolled else "inside the configured window"),
    )


def for_timezone(timezone, start, steps=None, config=None):
    """A whole cadence for one timezone, as UTC instants.

    `steps` defaults to the client's own cadence shape, so this reports what
    would actually be sent rather than an illustrative sequence.
    """
    steps = steps if steps is not None else cadence.STEPS
    out = []
    for spec in steps:
        on = start + datetime.timedelta(days=spec["day"] - 1)
        placed = place(timezone, on, spec["channel"], config)
        out.append(dict(placed, step=spec["key"], day=spec["day"]))
    return out


def for_company(segment, start, config=None, steps=None):
    """The cadence for one company, held in full if it cannot be scheduled.

    Held as a whole rather than per step: a company whose timezone is unknown
    has no schedulable step, and reporting six identical refusals reads as six
    problems rather than one.
    """
    schedulable, why = geo.schedulable(segment, config)
    timezone = segment.get("timezone")
    if not schedulable:
        return {"timezone": timezone, "schedulable": False, "why": why,
                "steps": [dict({"step": s["key"], "day": s["day"],
                                "channel": s["channel"], "status": HELD,
                                "why": why, "local_at": None, "utc_at": None})
                          for s in (steps if steps is not None
                                    else cadence.STEPS)]}
    return {"timezone": timezone, "schedulable": True,
            "why": why,
            "steps": for_timezone(timezone, start, steps, config)}


def for_batch(segments_, start, config=None, steps=None):
    """Every company in a batch, plus what the spread across zones actually is.

    The interesting number in a multi-timezone batch is not any one send time.
    It is the span: the same "09:30 local" is a fifteen-hour window in UTC
    across London, New York and Sydney, and that is the fact a person planning
    sender capacity needs.
    """
    rows, held = [], []
    for segment in segments_:
        plan = for_company(segment, start, config, steps)
        row = {"domain": segment.get("domain"),
               "timezone": plan["timezone"],
               "schedulable": plan["schedulable"],
               "why": plan["why"], "steps": plan["steps"]}
        (rows if plan["schedulable"] else held).append(row)

    firsts = [r["steps"][0]["utc_at"] for r in rows
              if r["steps"] and r["steps"][0].get("utc_at")]
    by_zone = {}
    for row in rows:
        by_zone.setdefault(row["timezone"], 0)
        by_zone[row["timezone"]] += 1

    span = None
    if firsts:
        moments = sorted(datetime.datetime.fromisoformat(f) for f in firsts)
        span = {
            "earliest_utc": moments[0].isoformat(),
            "latest_utc": moments[-1].isoformat(),
            "hours": round((moments[-1] - moments[0]).total_seconds() / 3600, 2),
        }

    return {
        "start": start.isoformat(),
        "companies": len(rows) + len(held),
        "schedulable": len(rows),
        "held": len(held),
        "timezones": dict(sorted(by_zone.items())),
        "first_step_utc_span": span,
        "rows": rows,
        "held_rows": held,
        # Stated rather than implied. Nothing in this module can send.
        "would_send": 0,
    }


def for_record(rec, start, config=None):
    """One queue record, classified and scheduled."""
    config = config or clients.load(rec.get("client"))
    segment = segments.classify(rec, config)
    segment = dict(segment, domain=rec.get("domain"))
    return for_company(segment, start, config)


# ------------------------------------------------------------------- the CLI

DEMO_ZONES = ("Europe/London", "America/New_York", "Europe/Zagreb",
              "Australia/Sydney")


def demo(start=None, config=None):
    """The four-city example, which is the fastest way to see DST behaviour."""
    start = start or datetime.date(2026, 9, 1)
    return for_batch([{"domain": f"{z.split('/')[-1].lower()}.test",
                       "timezone": z, "timezone_confidence": geo.HIGH}
                      for z in DEMO_ZONES], start, config)


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m src.schedule",
                                description=__doc__)
    p.add_argument("--demo", action="store_true",
                   help="four cities, one cadence, no queue needed")
    p.add_argument("--record", help="schedule one queue record")
    p.add_argument("--client", help="client config to use")
    p.add_argument("--start", help="local start date, YYYY-MM-DD")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    start = (datetime.date.fromisoformat(args.start) if args.start
             else datetime.date(2026, 9, 1))
    config = clients.load(args.client) if args.client else None

    if args.record:
        rec = store.get(args.record)
        if not rec:
            raise SystemExit(f"no such record: {args.record}")
        result = for_record(rec, start, config)
    else:
        result = demo(start, config)

    if args.json:
        print(json.dumps(result, indent=2))
        return result

    if args.record:
        print(f"{args.record}  {result['timezone']}  "
              f"{'schedulable' if result['schedulable'] else 'HELD'}")
        for step in result["steps"]:
            _print_step(step)
        return result

    print(f"start {result['start']}   companies {result['companies']}   "
          f"held {result['held']}   would send {result['would_send']}")
    if result["first_step_utc_span"]:
        span = result["first_step_utc_span"]
        print(f"day 1 spans {span['hours']}h of UTC: "
              f"{span['earliest_utc']} .. {span['latest_utc']}")
    for row in result["rows"]:
        print(f"\n  {row['timezone']}")
        for step in row["steps"]:
            _print_step(step, indent="    ")
    for row in result["held_rows"]:
        print(f"\n  {row['timezone'] or 'no timezone'}  HELD: {row['why']}")
    return result


def _print_step(step, indent="  "):
    if step.get("utc_at"):
        dst = " DST" if step.get("is_dst") else ""
        print(f"{indent}{step['step']:<6} {step['channel']:<9} "
              f"{step['local_at']}  ->  {step['utc_at']}"
              f"  (UTC{step['utc_offset_hours']:+g}{dst})")
    else:
        print(f"{indent}{step['step']:<6} {step['channel']:<9} "
              f"HELD: {step.get('why')}")


if __name__ == "__main__":
    main()
