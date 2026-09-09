#!/usr/bin/env python3
"""Out of office: whether it is one, and when they said they are back.

## Why this is separate from `replies`

`replies.classify` already answers "is this an out-of-office", and answers it
well: `OUT_OF_OFFICE` sits above `POSITIVE` in the precedence order precisely
so warmth cannot be read out of an autoresponder. That is a *category*
question and it stays there.

This module answers two different questions that a category cannot carry:

  1. Is this a machine or a person? An autoresponder and a human writing "I'm
     on holiday next week, but yes - let's talk" are the same category and
     completely different business events.
  2. When did they say they would be back?

Both are needed before anything can be scheduled, and neither belongs in a
list of regex categories.

## The date rule, which is the whole point

**A guessed return date is worse than no return date.** A missing one leaves
the account held and a person deciding; a wrong one schedules a follow-up
into somebody's leave, which is the exact discourtesy the OOO was telling us
about. So every reading here is deterministic and refuses on ambiguity:

  "back September 8"        -> resolved
  "back on the 15th"        -> resolved, next 15th
  "back Monday"             -> resolved, next Monday
  "returning 08/09"         -> UNKNOWN. 8 September or 9 August, and the
                               answer depends on a locale nobody recorded
  "back next week"          -> UNKNOWN. Which day?
  "on leave until January"  -> UNKNOWN. A month is not a date

`RETURN_DATE_UNKNOWN` is a real answer, not a failure to produce one, and it
is reported with the reason so an operator reads "they did not say" rather
than a blank field.

## Timezone

A return date is a calendar date in the writer's own frame. Nobody says "back
on the 8th, 09:00 UTC". So the date is taken exactly as written and never
shifted, and whether a timezone is known is recorded beside it rather than
being used to move the day. `geo.py` already refuses to guess a timezone and
this refuses to need one.

## What it does not do

It does not send, schedule, or resume anything. It reads a message and
returns what it can prove about it. Holding the cadence already happened in
`events.apply` when the reply arrived, before any of this ran.
"""
import datetime
import re

VERSION = "ooo-rules-1"

# ------------------------------------------------------------------ detection

AUTORESPONDER = "autoresponder"
HUMAN_ABSENCE = "human_absence"
NOT_ABSENCE = "not_absence"

# Phrases only a mail system writes. A person announcing their own holiday
# does not say "automatic reply".
MACHINE_MARKERS = (
    r"\bautomatic reply\b", r"\bauto[- ]?reply\b", r"\bautoreply\b",
    r"\bautomated (?:response|reply|message)\b",
    r"\bthis is an automated\b", r"\bout of office autoreply\b",
    r"\bdo not reply to this (?:email|message)\b",
)

# Absence, however it is phrased. A human and a machine both use these, which
# is exactly why they cannot decide the question on their own.
ABSENCE_MARKERS = (
    r"\bout of (?:the )?office\b", r"\bon (?:annual |parental |sick )?leave\b",
    r"\bon holiday\b", r"\bon vacation\b", r"\bmaternity leave\b",
    r"\bpaternity leave\b", r"\bi(?:'m| am) away\b", r"\bcurrently away\b",
    r"\bi(?:'m| am) (?:currently )?(?:out|off)\b", r"\baway from (?:my )?desk\b",
    r"\breturning on\b", r"\bback in the office\b",
    r"\blimited access to (?:my )?email\b", r"\bi(?:'m| am) travel"
    r"(?:ling|ing)\b", r"\bannual leave\b",
)


def normalise(text):
    return re.sub(r"\s+", " ", (text or "")).strip()


def _hits(text, patterns):
    found = []
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            found.append(match.group(0).strip().lower())
    return found


def detect(text, automated=None):
    """Is this an absence, and was it written by a machine or a person?

    `automated` is the provider's own flag where it has one - EmailBison
    puts `automated_reply` on every reply row. It is authoritative when
    present because the provider saw headers we never will, and `None`
    means the provider did not say, not that the answer is no.

    Absent that flag, a machine is claimed only on an unmistakable machine
    marker. Inferring "autoresponder" from "I'm on holiday" would silently
    demote a human being who happens to be away, and a human writing about
    their own absence is the case this module exists to keep visible.
    """
    body = normalise(text)
    machine = _hits(body, MACHINE_MARKERS)
    absence = _hits(body, ABSENCE_MARKERS)

    if automated is True:
        kind = AUTORESPONDER
        why = "the provider marked this an automated reply"
    elif machine:
        kind = AUTORESPONDER
        why = f"machine-only phrasing: {machine[0]}"
    elif absence:
        kind = HUMAN_ABSENCE
        why = ("absence stated, and nothing marks it automated"
               if automated is False else
               "absence stated; the provider did not say whether it is automated")
    else:
        kind = NOT_ABSENCE
        why = "no absence stated"

    return {
        "kind": kind,
        "is_absence": kind in (AUTORESPONDER, HUMAN_ABSENCE),
        # Whether the machine/human split rests on the provider or on us.
        "automated_source": ("provider" if automated is not None
                             else ("text" if machine else "unknown")),
        "evidence": (machine + absence)[:4],
        "reason": why,
        "detector": VERSION,
    }


# ------------------------------------------------------------- return dates

RESOLVED = "resolved"
UNKNOWN_NOT_STATED = "unknown:not_stated"
UNKNOWN_AMBIGUOUS_NUMERIC = "unknown:ambiguous_numeric_date"
UNKNOWN_VAGUE_PERIOD = "unknown:vague_period"
UNKNOWN_MONTH_WITHOUT_DAY = "unknown:month_without_day"

MONTHS = {
    "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3,
    "april": 4, "apr": 4, "may": 5, "june": 6, "jun": 6, "july": 7, "jul": 7,
    "august": 8, "aug": 8, "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10, "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}
MONTH_RE = "|".join(sorted(MONTHS, key=len, reverse=True))

WEEKDAYS = {"monday": 1, "tuesday": 2, "wednesday": 3, "thursday": 4,
            "friday": 5, "saturday": 6, "sunday": 7}
WEEKDAY_RE = "|".join(WEEKDAYS)

# The words that introduce a return. Without one of these a date in the body
# is just a date - "we shipped on 3 March" is not a return date.
# The same grammar answers a second question. "Try me in November" is not
# an absence - nobody is away - but it is a date somebody gave for when to
# come back, and reading it needs exactly the machinery below. The cue set
# is what differs, so it is a parameter rather than a copy of the parser.
NOT_NOW_CUE = (r"(?:try (?:me|us)|reach out|reach back|get back|come back|"
               r"circle back|check back|ping|contact me|touch base|follow up|"
               r"revisit|speak|talk|after|in|around|later in|early|"
               r"beginning of|start of|end of)")

RETURN_CUE = (r"(?:back|return(?:s|ing)?|returned|available again|available|"
              r"in the office|until|til|till|after|from|reach me|contact me|"
              r"respond|reply)")

# A stale autoresponder read late still names a real day. Rolling it into
# next year would schedule a follow-up twelve months out; keeping it says
# "they are already back", which is true and useful. Beyond this many days
# the reading is a next-year date instead.
STALE_TOLERANCE_DAYS = 31


def _received_date(received_at):
    """The day the message arrived, as a date. Never guessed."""
    if isinstance(received_at, datetime.datetime):
        return received_at.date()
    if isinstance(received_at, datetime.date):
        return received_at
    text = str(received_at or "").strip()
    if not text:
        return None
    try:
        return datetime.date.fromisoformat(text[:10])
    except ValueError:
        return None


def _choose_year(month, day, received):
    """This year's occurrence, or next year's, whichever they meant.

    Same-year unless that lands well in the past, which is how a December
    autoresponder saying "back January 5" resolves to the following year
    without a stale September one jumping twelve months.
    """
    for year in (received.year, received.year + 1):
        try:
            candidate = datetime.date(year, month, day)
        except ValueError:
            return None                      # 31 February and friends
        if candidate >= received - datetime.timedelta(
                days=STALE_TOLERANCE_DAYS):
            return candidate
    return None


def _unknown(status, reason, evidence=None):
    return {"return_date": None, "status": status, "reason": reason,
            "evidence": evidence or [], "parser": VERSION}


def _resolved(day, reason, evidence):
    return {"return_date": day.isoformat(), "status": RESOLVED,
            "reason": reason, "evidence": evidence, "parser": VERSION}


def return_date(text, received_at, timezone=None, cue=None):
    """When they said they are back, or why that is not knowable.

    `received_at` anchors every relative reading and is required: "back
    Monday" has no meaning without the day it was written. Without it the
    answer is unknown rather than today.

    `timezone` is recorded, never applied. A calendar date is what was
    written; shifting it by a zone would move somebody's return by a day in
    exchange for precision the message never had.
    """
    body = normalise(text)
    received = _received_date(received_at)
    result = _extract(body, received, cue=cue)
    result["timezone"] = timezone or None
    result["timezone_known"] = bool(timezone)
    return result


def _extract(body, received, cue=None):
    cue = cue or RETURN_CUE
    if not body:
        return _unknown(UNKNOWN_NOT_STATED, "empty message")
    if received is None:
        return _unknown(UNKNOWN_NOT_STATED,
                        "no received date to anchor the reading against")

    # Every reading below needs a cue. Without one, a date in the body is
    # just a date: "we launched on 3 March" resolved to a return on the
    # third of March, because the month-and-day pattern asked nothing about
    # what the sentence was for.
    #
    # It was contained only by this running on messages already classified
    # as an absence, which is a coincidence of the caller rather than a
    # guarantee - and the test that was supposed to cover it only exercised
    # the ordinal path, so it passed while this was wide open.
    # Guards the concrete readings only. "On leave for a couple of weeks"
    # names no cue and no date, and it is still worth saying that they gave
    # a period rather than that they said nothing - the reason is what an
    # operator reads. The ordinal and weekday patterns below carry the cue
    # in their own expressions already.
    has_cue = bool(re.search(rf"\b{cue}\b", body, re.I))

    # ---- explicit calendar dates, which need no anchor beyond the year
    iso = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", body) if has_cue else None
    if iso:
        try:
            day = datetime.date(*(int(g) for g in iso.groups()))
        except ValueError:
            return _unknown(UNKNOWN_AMBIGUOUS_NUMERIC,
                            "an ISO date that is not a real day",
                            [iso.group(0)])
        return _resolved(day, "an explicit ISO date", [iso.group(0)])

    # "8 September", "8th of September"
    day_month = re.search(
        rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+(?:of\s+)?({MONTH_RE})\b", body,
        re.I)
    # "September 8", "Sept 8th"
    month_day = re.search(
        rf"\b({MONTH_RE})\s+(\d{{1,2}})(?:st|nd|rd|th)?\b", body, re.I)
    for match, order in ((day_month, "dm"), (month_day, "md")):
        if not match or not has_cue:
            continue
        raw_day, raw_month = ((match.group(1), match.group(2)) if order == "dm"
                              else (match.group(2), match.group(1)))
        month = MONTHS[raw_month.lower()]
        day = _choose_year(month, int(raw_day), received)
        if day is None:
            return _unknown(UNKNOWN_AMBIGUOUS_NUMERIC,
                            "a named date that is not a real day",
                            [match.group(0)])
        return _resolved(day, "a named month and day", [match.group(0)])

    # ---- a numeric date is genuinely ambiguous and must not be read
    numeric = re.search(r"\b(\d{1,2})[/.-](\d{1,2})(?:[/.-]\d{2,4})?\b", body)
    if numeric and has_cue:
        return _unknown(
            UNKNOWN_AMBIGUOUS_NUMERIC,
            "a numeric date could be day-month or month-day, and no locale "
            "was recorded for this contact",
            [numeric.group(0)])

    # ---- "back on the 15th": a day of the month, next occurrence
    ordinal = re.search(
        rf"\b{cue}\b[^.!?]{{0,20}}?\bthe\s+(\d{{1,2}})(?:st|nd|rd|th)\b",
        body, re.I)
    if ordinal:
        return _next_day_of_month(int(ordinal.group(1)), received,
                                  ordinal.group(0).strip())

    # ---- "back Monday"
    weekday = re.search(
        rf"\b{cue}\b[^.!?]{{0,20}}?\b({WEEKDAY_RE})\b", body, re.I)
    if weekday:
        return _next_weekday(WEEKDAYS[weekday.group(1).lower()], received,
                             weekday.group(0).strip())

    # ---- everything below is a period, not a date
    vague = _hits(body, (
        r"\bnext week\b", r"\bthe week after\b", r"\bin (?:a|one) week\b",
        r"\b(?:a |the )?(?:couple|few) of weeks\b", r"\bin \d+ weeks?\b",
        r"\bin \d+ days?\b", r"\bfor (?:a|one) (?:week|fortnight)\b",
        r"\bshortly\b", r"\bsoon\b", r"\bfor the next \w+\b",
        r"\bthis week\b", r"\brest of the week\b",
    ))
    if vague:
        return _unknown(UNKNOWN_VAGUE_PERIOD,
                        f"a period rather than a date: {vague[0]}", vague)

    month_only = re.search(rf"\b(?:until|til|till|in|during)\s+({MONTH_RE})\b",
                           body, re.I)
    if month_only:
        return _unknown(UNKNOWN_MONTH_WITHOUT_DAY,
                        "a month with no day in it",
                        [month_only.group(0)])

    return _unknown(UNKNOWN_NOT_STATED, "no return date was stated")


def _next_day_of_month(day_number, received, evidence):
    if not 1 <= day_number <= 31:
        return _unknown(UNKNOWN_AMBIGUOUS_NUMERIC,
                        "not a day of any month", [evidence])
    year, month = received.year, received.month
    for _ in range(3):                        # this month, then the next two
        try:
            candidate = datetime.date(year, month, day_number)
        except ValueError:
            candidate = None
        if candidate is not None and candidate >= received:
            return _resolved(candidate, "the next occurrence of that day of "
                                        "the month", [evidence])
        month += 1
        if month > 12:
            month, year = 1, year + 1
    return _unknown(UNKNOWN_AMBIGUOUS_NUMERIC,
                    "no such day in the coming months", [evidence])


def _next_weekday(weekday_number, received, evidence):
    ahead = (weekday_number - received.isoweekday()) % 7
    # "back Monday" written on a Monday means the Monday coming, not today:
    # the message says they are away now.
    ahead = ahead or 7
    return _resolved(received + datetime.timedelta(days=ahead),
                     "the next occurrence of that weekday", [evidence])


# ------------------------------------------------------------------ together

def read(text, received_at, automated=None, timezone=None):
    """Detection and date in one answer, which is how callers want it.

    Returns the absence reading, the return date reading, and nothing
    derived from them. Deciding what to *do* about an out-of-office is
    account policy's job, and this deliberately stops short of it.
    """
    found = detect(text, automated=automated)
    dates = (return_date(text, received_at, timezone=timezone)
             if found["is_absence"] else
             _unknown(UNKNOWN_NOT_STATED, "not an absence"))
    if not found["is_absence"]:
        dates["timezone"] = timezone or None
        dates["timezone_known"] = bool(timezone)
    return {"absence": found, "return": dates}
