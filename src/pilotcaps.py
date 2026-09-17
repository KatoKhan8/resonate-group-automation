#!/usr/bin/env python3
"""Ceilings a configuration cannot raise, for the first controlled pilot.

## The mistake this exists to make impossible

A pilot is twenty companies and forty people. Every number that decides
how much goes out is configurable - `campaign.daily_volume`, the workspace
`sending.*` overrides, the fatigue limits - and every one of them is
configurable to a number far larger than a pilot.

So the failure is not exotic. It is somebody typing 2000 where they meant
20, in a field that accepts it, on a screen that has no idea a pilot is
happening. The system does exactly what it was told, and the first live
run is not a pilot any more.

## A ceiling is not a default

`fatigue` and `campaigns` already hold limits, and this does not replace
them: they are the client's judgement about what is decent, and they can
be tuned. This is a different kind of number - the most that may happen
while pilot mode is on, whatever anything else says.

Both apply, and the smaller one wins. `effective()` is `min(configured,
ceiling)` for every key, so a workspace configured for 500 emails a day
gets 20 while the pilot is on, and gets 500 the moment somebody turns
pilot mode off - which is a deliberate act with an audit entry rather
than an edit to a number in a form.

## Deliberately tiny, and deliberately awkward to raise

The defaults here are smaller than anybody would choose for a real
campaign. That is the point: a pilot that quietly grew is a pilot nobody
was watching, and the cost of a ceiling that is too low is a second run.

Raising one is a change to this file and a review, not a setting. There is
no environment variable, no workspace override, and no argument to
`effective()` that lifts a ceiling - the only parameter it takes is the
configuration being *constrained*.
"""
import argparse
import json

# What may happen at all, while the pilot is on. Nothing configurable
# raises these; `effective()` takes the smaller of this and whatever was
# configured.
CEILING = {
    "companies": 20,
    "contacts": 40,
    "email_per_day": 20,
    "linkedin_per_day": 10,
    "per_sender_per_day": 10,
    # RAISED 4 -> 8 on 2026-09-13, which is the change-and-review this file
    # asks for rather than a setting somebody turned up.
    #
    # The operator moved Productive to a LinkedIn-heavy cadence: eleven
    # touches per person over 21 days, five of them in the first week. Four a
    # week to a COMPANY was therefore incompatible with one fully-worked
    # contact, never mind the staggered second one the account plan calls for
    # - it would have blocked the primary on day 6 and admitted no secondary
    # at all.
    #
    # Eight is one fully-worked primary (five in week one) plus a second
    # stakeholder entering later at about three. It is not a number that
    # licenses a third track: `fatigue.account.max_active_contacts` is two,
    # and the providers enforce it independently - EmailBison 422s a lead
    # that is `in_sequence` elsewhere.
    "touches_per_account_per_week": 8,
    "new_accounts_per_day": 5,
}

KEYS = tuple(CEILING)

LABELS = {
    "companies": "Companies in the pilot",
    "contacts": "People in the pilot",
    "email_per_day": "Emails a day, across the whole pilot",
    "linkedin_per_day": "LinkedIn activities a day",
    "per_sender_per_day": "Messages a day from one human",
    "touches_per_account_per_week": "Touches to one company in a week",
    "new_accounts_per_day": "Companies opened for the first time in a day",
}

WHY = {
    "companies":
        "a pilot is small enough that one person can read every message "
        "that goes out",
    "contacts":
        "two people per company on average, which is what the cadence "
        "assumes",
    "email_per_day":
        "the whole pilot in a day is still reviewable by eye",
    "linkedin_per_day":
        "LinkedIn limits are lower and enforced by the platform rather "
        "than by us",
    "per_sender_per_day":
        "a new inbox sending twenty a day on its first week is how a "
        "domain gets a reputation problem",
    "touches_per_account_per_week":
        "four touches to one company in a week reads as pressure however "
        "many people they are spread across",
    "new_accounts_per_day":
        "opening every account at once means every reply arrives at once, "
        "and a pilot exists to be watched",
}

# Where each ceiling constrains an existing setting. Named so a reader can
# see the two numbers that meet, rather than wondering which one applied.
CONSTRAINS = {
    "email_per_day": "campaign.daily_volume.email",
    "linkedin_per_day": "campaign.daily_volume.linkedin",
    "touches_per_account_per_week": "fatigue.account.max_touches_per_week",
}


class PilotCapExceeded(RuntimeError):
    """A plan asked for more than the pilot allows. Refused, not trimmed.

    Trimming would be the friendly thing and the wrong one: somebody who
    asked for two hundred and got twenty has been told the system did what
    they asked, and it did not.
    """


class UnacknowledgedCap(RuntimeError):
    """`require` was asked about some ceilings and said nothing about the rest.

    NOT A BREACH. Nobody asked for too much; somebody asked a question this
    module could only half answer and took `True` for the whole answer.

    THE DEFECT THIS EXISTS TO MAKE IMPOSSIBLE, measured on 2026-09-17.
    `new_accounts_per_day` had been in `CEILING` since the file was written,
    with a label, a reason, and a number - and no caller anywhere in `src/`
    ever put it in a plan. `check` reported it in `unchecked`, honestly, and
    nothing read that list; `require` returned `True` regardless. So the
    ceiling existed, was documented, was displayed by `main()`, and refused
    nothing. A cap that is not checked must not be able to look like a cap
    that passed, and silence was the whole mechanism by which it did.
    """


def enabled(config=None):
    """Is pilot mode on? Off is not the default - on is.

    Inverted deliberately. Every other switch in this system defaults to
    the safe position by defaulting to off; here the safe position *is*
    on, so absence means the caps apply. A build where somebody forgot to
    configure anything is a build running under pilot limits, which is the
    only forgetting that costs nothing.
    """
    value = ((config or {}).get("pilot") or {}).get("enabled")
    if value is None:
        return True
    return str(value).strip().lower() not in ("off", "false", "no", "0")


def configured(config=None):
    """The numbers this client asked for, where they map onto a ceiling."""
    config = config or {}
    volume = ((config.get("campaign") or {}).get("daily_volume")
              or config.get("daily_volume") or {})
    fatigue_limits = (config.get("fatigue") or {})
    account = (fatigue_limits.get("account") or {})
    out = {}
    if volume.get("email") is not None:
        out["email_per_day"] = volume["email"]
    if volume.get("linkedin") is not None:
        out["linkedin_per_day"] = volume["linkedin"]
    if account.get("max_touches_per_week") is not None:
        out["touches_per_account_per_week"] = account["max_touches_per_week"]
    return out


def effective(config=None):
    """The number that actually applies to each key, and where it came from.

    `min(configured, ceiling)`. The only parameter is the configuration
    being constrained - there is nothing to pass that raises a ceiling,
    which is what makes this a ceiling rather than a default.
    """
    on = enabled(config)
    asked = configured(config)
    out = {}
    for key in KEYS:
        ceiling = CEILING[key]
        want = asked.get(key)
        if not on:
            value, source = (want if want is not None else ceiling,
                             "configured" if want is not None else "ceiling")
        elif want is None:
            value, source = ceiling, "ceiling"
        elif want <= ceiling:
            value, source = want, "configured"
        else:
            value, source = ceiling, "ceiling"
        out[key] = {
            "key": key,
            "label": LABELS[key],
            "limit": value,
            "ceiling": ceiling,
            "configured": want,
            "source": source,
            "constrains": CONSTRAINS.get(key),
            "why": WHY[key],
            "capped": on and want is not None and want > ceiling,
        }
    return out


def check(plan, config=None):
    """What in this plan exceeds the pilot, and by how much.

    `plan` is a dict of the same keys - companies, contacts, and so on.
    Keys it does not carry are not checked, and are reported as unchecked
    rather than passed: a plan that named nothing would otherwise come
    back clean.
    """
    limits = effective(config)
    breaches, checked = [], []
    for key, row in limits.items():
        if key not in (plan or {}):
            continue
        checked.append(key)
        asked = plan[key]
        if asked is not None and asked > row["limit"]:
            breaches.append({
                "key": key, "label": row["label"], "asked": asked,
                "limit": row["limit"], "source": row["source"],
                "over_by": asked - row["limit"], "why": row["why"]})
    return {
        "ok": not breaches,
        "pilot": enabled(config),
        "breaches": breaches,
        "checked": sorted(checked),
        "unchecked": sorted(set(KEYS) - set(checked)),
        "note": "a ceiling is refused rather than trimmed. Somebody who "
                "asked for two hundred and silently got twenty has been "
                "told the system did what they asked",
    }


def require(plan, config=None, *, not_checking=None):
    """Raise unless the plan fits AND the caller has named what it skipped.

    `not_checking` is the caller saying, in the code, which ceilings this call
    is not answering for - as an iterable of keys, or better as a dict of
    `{key: who does answer for it}` so the next reader is not left guessing.
    It must name EXACTLY the keys absent from `plan`: too few and a ceiling is
    passing on silence, too many and the call is claiming to skip something it
    just checked.

    WHY AN EXPLICIT LIST RATHER THAN A FLAG. `require(plan, ack=True)` would
    close today's hole and reopen it tomorrow: the next ceiling added to
    `CEILING` would be swept into the same blanket acknowledgement and nobody
    would ever be asked about it. An exact list is the only form that breaks
    at every call site the moment a ceiling is ADDED, which is the moment the
    decision "who enforces this" is actually being made - and it is the moment
    `new_accounts_per_day` went by unmade.

    WHY BREACHES ARE RAISED FIRST. A breach is a fact about the outside world
    and an unacknowledged cap is a fact about this call site. If both are true
    the breach is the one an operator needs, with its own message and its own
    type, so the coverage complaint waits its turn.

    Callers that are gates should let this propagate rather than catch it. It
    fails CLOSED by construction: in `executionguard` gate 5 every exception
    out of this function becomes `NotAuthorized("pilot_cap")`, so getting the
    acknowledgement wrong refuses the action instead of permitting it.
    """
    found = check(plan, config)
    if not found["ok"]:
        first = found["breaches"][0]
        raise PilotCapExceeded(
            f"{first['label']}: asked for {first['asked']}, the pilot "
            f"allows {first['limit']} ({first['why']})")

    if not_checking is None:
        acknowledged = set()
    elif isinstance(not_checking, str):
        acknowledged = {not_checking}
    else:
        # A dict gives its keys, which is what makes `{key: reason}` the
        # readable form without needing a second parameter for the reasons.
        acknowledged = set(not_checking)

    unknown = sorted(acknowledged - set(KEYS))
    if unknown:
        raise UnacknowledgedCap(
            f"{', '.join(unknown)}: not a pilot ceiling. An acknowledgement "
            f"naming a key that does not exist is how one stops matching the "
            f"ceilings it was written against")
    contradicted = sorted(acknowledged & set(found["checked"]))
    if contradicted:
        raise UnacknowledgedCap(
            f"{', '.join(contradicted)}: this call says it is not checking "
            f"them and the plan checks them. One of the two is wrong, and a "
            f"reader cannot tell which")
    silent = sorted(set(found["unchecked"]) - acknowledged)
    if silent:
        raise UnacknowledgedCap(
            "this plan is silent about " + ", ".join(silent) + " and so is "
            "the caller. Name them in `not_checking` with what does enforce "
            "them, or check them: " + "; ".join(
                f"{k} ({LABELS[k]}) - {WHY[k]}" for k in silent))
    return True


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m src.pilotcaps",
                                description=__doc__)
    p.add_argument("--client")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)

    config = {}
    if a.client:
        from . import clients

        config = clients.load(a.client)

    limits = effective(config)
    if a.json:
        print(json.dumps({"enabled": enabled(config), "limits": limits},
                         indent=2, default=str))
        return 0

    print("pilot mode: " + ("ON" if enabled(config) else "OFF"))
    for row in limits.values():
        mark = " (capped)" if row["capped"] else ""
        print(f"  {row['label']:<44} {row['limit']}{mark}")
        if row["capped"]:
            print(f"      configured {row['configured']}, ceiling "
                  f"{row['ceiling']}: {row['why']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
