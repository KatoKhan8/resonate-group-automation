#!/usr/bin/env python3
"""Meetings booked, fed by hand, because nothing else can answer it.

OPERATOR, 2026-09-22: "build a human-fed ledger. In an internal channel or
thread, `@Resonate OS meeting booked <domain> <date>` (optionally
`with <role>`) records one row: workspace, domain, date, who recorded it,
source=manual. Internal users only. Counts appear in the digest, the weekly
plan and client answers; per-domain detail only internally or in that
client's channel. Add a second source later (Calendly/CRM) as a separate
tag; never merge sources silently."

`docs/SLACK-AGENT-QUESTION-CATALOGUE.md` puts it first on the build list:
**meetings booked is the single most-asked number the agent cannot produce.
It is the number the commercial relationship runs on.** 93 questions, and
no system anywhere holds it.

## SOURCES NEVER MERGE, AND THE SHAPE IS WHAT ENFORCES THAT

"Never merge sources silently" is not a rule somebody has to remember: the
count is per source and there is no function that returns a bare number.
`counts()` returns `{source: n}`, and the only total it will produce says
which sources it spans. When Calendly arrives it is a new key, a reader
sees two numbers, and nobody has to be told that one of them is new.

The alternative - a `total` that quietly grew when a second source was
wired - is precisely how "we booked 40 meetings" becomes unfalsifiable.

## IT RECORDS, IT DOES NOT ACT

This is a write, and it is the first one the agent makes on somebody's
instruction, so the limits are worth stating. It appends one row to a
journal under `work/`, which is the only place this agent writes. It
reaches no provider, changes no campaign, and sends nothing. The recogniser
is a REGEX, not the model: a Slack message cannot talk its way into a row
by being persuasive, only by being in the exact shape below.

## AND ONLY AN INTERNAL PERSON CAN FEED IT

Checked against `slackscope.internal_users()` - the person, not only the
room. A client channel cannot reach this at all, and a client's message in
an internal channel would not either. The number the contract is measured
by is not one the other party writes.

## THE WORKSPACE COMES FROM THE DOMAIN, OR THE ROW IS REFUSED

A meeting filed against the wrong client is a number in that client's own
answer that was never theirs. So the domain is resolved against the record
store and an unresolvable or ambiguous one is REFUSED, with the exact
phrase to type instead. Guessing here is worse than asking.

## A DUPLICATE IS REFUSED, NOT COUNTED TWICE

Two people recording the same meeting is the ordinary failure of any
hand-fed ledger, and this one feeds a commercial number. A row with the
same workspace, domain and date is refused and the existing row is named,
so the second person can see what the first one wrote.
"""
import json
import os
import re
import time

MANUAL = "manual"

RECORDED = "recorded"
WITHDRAWN = "withdrawn"

JOURNAL_NAME = "slack-meetings.jsonl"
JOURNAL_VAR = "SLACK_MEETINGS"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: The grammar, exactly as the operator wrote it. `meeting booked`, a
#: domain, a date, and optionally `with <role>` - and optionally
#: `for <workspace>`, which is not in the operator's grammar and exists
#: only because the refusal for an unresolvable domain has to offer
#: something to type. A recogniser that can only say no is a dead end.
_TRIGGER = re.compile(
    r"\bmeetings?\s+booked\b[\s:,-]*"
    r"(?P<domain>[a-z0-9][a-z0-9.-]*\.[a-z]{2,})"
    r"[\s:,-]*(?P<date>[0-9]{4}-[0-9]{2}-[0-9]{2}"
    r"|[0-9]{1,2}[./][0-9]{1,2}(?:[./][0-9]{2,4})?\.?"
    r"|today|tomorrow|danas|sutra)?"
    r"(?P<rest>.*)$",
    re.I | re.S)

_WITH = re.compile(r"\bwith\s+(?P<role>[^,.;\n]{2,60})", re.I)
_FOR = re.compile(r"\bfor\s+(?P<workspace>[a-z0-9][a-z0-9_-]{1,40})\b", re.I)

#: Words that mean the message is ASKING about meetings rather than
#: recording one. "how many meetings booked this week" must never write a
#: row, and it is the more common message by far.
_ASKING = re.compile(
    r"\b(?:how many|koliko|kolko|what|which|any|ima li|jel|je li|"
    r"\?|show|list|count)\b", re.I)


def _now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def path():
    override = (os.environ.get(JOURNAL_VAR) or "").strip()
    if override:
        return os.path.abspath(override)
    try:
        from . import store
        return os.path.join(os.path.dirname(store.queue_path()),
                            JOURNAL_NAME)
    except Exception:                                           # noqa: BLE001
        return os.path.join(ROOT, "work", JOURNAL_NAME)


def _append(row):
    from . import store
    target = path()
    store.refuse_production_write(target)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, default=str) + "\n")
    return row


def load():
    """Every meeting, latest state per id. Append-only underneath.

    Latest-per-id rather than every-line, so a correction verb can be added
    later without the count having to learn about it - the same shape
    `slackrequests` and `slackfollowup` use.
    """
    target = path()
    if not os.path.isfile(target):
        return []
    latest = {}
    with open(target, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if row.get("id"):
                latest[row["id"]] = row
    return sorted(latest.values(), key=lambda r: str(r.get("date")))


def recorded(workspace=None):
    rows = [r for r in load() if r.get("status") == RECORDED]
    if workspace:
        rows = [r for r in rows if r.get("workspace") == workspace]
    return rows


# ------------------------------------------------------------ the reading

def counts(workspace=None, since=None, until=None):
    """`{source: n}`, never a bare number.

    THE OPERATOR'S RULE IS THE RETURN TYPE. "Never merge sources silently"
    cannot be forgotten by a caller that has no single number to reach for,
    and the day Calendly is wired a reader sees a second key rather than a
    total that grew.
    """
    out = {}
    for row in recorded(workspace):
        if since and str(row.get("date") or "") < since:
            continue
        if until and str(row.get("date") or "") > until:
            continue
        source = row.get("source") or MANUAL
        out[source] = out.get(source, 0) + 1
    return out


def total_across(counted):
    """A single figure, and the sources it spans, together or not at all."""
    return {"meetings": sum(counted.values()),
            "sources": sorted(counted),
            "note": ("a total across %d source(s). Sources are counted "
                     "separately and this is their sum, not one system's "
                     "number." % len(counted)) if counted else
                    "no meeting is recorded for this period"}


def by_domain(workspace=None, since=None, until=None):
    """One row per meeting. NEVER client-facing except in that client's own
    channel - the caller decides that, and `slackagenttools` does."""
    out = []
    for row in recorded(workspace):
        if since and str(row.get("date") or "") < since:
            continue
        if until and str(row.get("date") or "") > until:
            continue
        out.append({"id": row.get("id"), "domain": row.get("domain"),
                    "date": row.get("date"), "with_role": row.get("with_role"),
                    "source": row.get("source"),
                    "recorded_by": row.get("recorded_by"),
                    "workspace": row.get("workspace")})
    return sorted(out, key=lambda r: (str(r["date"]), str(r["domain"])))


# ------------------------------------------------------------ the writing

class MeetingRefused(RuntimeError):
    """The row was not written, and the reason is on the exception."""


def existing(workspace, domain, date):
    for row in recorded(workspace):
        if (row.get("domain") == domain and row.get("date") == date):
            return row
    return None


def record(workspace, domain, date, recorded_by, with_role=None,
           source=MANUAL, original=""):
    """One row, or `MeetingRefused`. Writes nothing but the journal."""
    import secrets

    clash = existing(workspace, domain, date)
    if clash:
        raise MeetingRefused(
            "a meeting for %s on %s is already recorded as %s, by <@%s>. "
            "Nothing was added - two rows would be two meetings in the "
            "count." % (domain, date, clash.get("id"),
                        clash.get("recorded_by")))
    row = {"id": "mtg-%s" % secrets.token_hex(3),
           "status": RECORDED,
           "workspace": workspace,
           "domain": domain,
           "date": date,
           "with_role": (str(with_role).strip() or None) if with_role
                        else None,
           # THE TAG THE OPERATOR ASKED FOR. Every row carries where it
           # came from, so a second source is a second tag and never a
           # bigger number under the same one.
           "source": source,
           "recorded_by": recorded_by,
           "recorded_at": _now(),
           "original_message": str(original or "")[:400]}
    return _append(row)


# ------------------------------------------------------- the recogniser

def parse(text, slugs=None):
    """`{domain, date, with_role, workspace}` for a record instruction.

    `None` for anything else, INCLUDING a question about meetings. "how
    many meetings booked this week" is the more common message by a long
    way and it must never write a row, so an asking-shaped message is
    rejected before the grammar is even tried.

    `for <workspace>` IS ONLY A WORKSPACE WHEN IT NAMES ONE. "with the head
    of ops for EMEA" is a role that happens to contain the word, and an
    earlier version took `EMEA` as a workspace and the truncated phrase as
    the role. So the tail is matched against the workspaces that actually
    exist, and anything else stays part of what the person wrote.
    """
    body = str(text or "")
    stripped = _strip_mentions(body)
    if _ASKING.search(stripped):
        return None
    found = _TRIGGER.search(stripped)
    if not found:
        return None
    date = _as_date(found.group("date"))
    if not date:
        return None
    rest = found.group("rest") or ""
    known = _known_slugs() if slugs is None else {str(s).lower()
                                                  for s in slugs}
    workspace = None
    for candidate in _FOR.finditer(rest):
        if candidate.group("workspace").lower() in known:
            workspace = candidate.group("workspace").lower()
            rest = rest[:candidate.start()] + rest[candidate.end():]
            break
    role = _WITH.search(rest)
    return {"domain": found.group("domain").lower().strip("."),
            "date": date,
            "with_role": role.group("role").strip() if role else None,
            "workspace": workspace}


def _known_slugs():
    try:
        from . import workspaces
        return {str(w.get("slug") or "").lower()
                for w in workspaces.workspaces() if w.get("slug")}
    except Exception:                                           # noqa: BLE001
        # No workspace list means no `for <slug>` is recognised, which
        # leaves the domain as the only way a row is attributed. That is
        # the conservative direction: the fallback disappears, the refusal
        # stays.
        return set()


def _strip_mentions(text):
    return re.sub(r"<@[A-Z0-9]+>", " ", str(text or ""))


def _as_date(token, now=None):
    """ISO, or None. European order, and the caller echoes what it read.

    `03/04` is dd/mm here, because the people typing this write dates that
    way - and because a parser that guesses is only safe when the guess is
    said back. Every confirmation this module's caller posts names the ISO
    date it recorded, so a misread is visible in the same second rather
    than in a quarterly number.
    """
    import datetime
    text = str(token or "").strip().lower().rstrip(".")
    if not text:
        return None
    today = (now or datetime.date.today())
    if text in ("today", "danas"):
        return today.isoformat()
    if text in ("tomorrow", "sutra"):
        return (today + datetime.timedelta(days=1)).isoformat()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        try:
            return datetime.date.fromisoformat(text).isoformat()
        except ValueError:
            return None
    parts = re.split(r"[./]", text)
    if len(parts) not in (2, 3):
        return None
    try:
        day, month = int(parts[0]), int(parts[1])
        year = int(parts[2]) if len(parts) == 3 else today.year
    except ValueError:
        return None
    if year < 100:
        year += 2000
    try:
        return datetime.date(year, month, day).isoformat()
    except ValueError:
        return None


# ------------------------------------------------- which client it belongs to

def workspace_for_domain(domain):
    """`(slug, why)` - the workspace holding this domain, or `(None, why)`.

    Refuses on BOTH kinds of uncertainty, and they are different:

        unknown      no workspace has a record for that domain
        ambiguous    more than one does, and picking is a disclosure as
                     well as an error

    A meeting filed against the wrong client is a number in that client's
    own answer that was never theirs, and it is discovered - if ever - at
    the point somebody quotes it back. So neither case guesses.
    """
    needle = str(domain or "").lower().strip()
    if not needle:
        return None, "no domain was given"
    try:
        from . import store
        rows = store.load()
    except Exception as exc:                                    # noqa: BLE001
        return None, ("the record store could not be read (%s), so the "
                      "domain cannot be attributed to a client"
                      % type(exc).__name__)
    found = set()
    for record in rows:
        if str(record.get("domain") or "").lower().strip() != needle:
            continue
        slug = record.get("client") or record.get("workspace")
        if slug:
            found.add(slug)
    if len(found) == 1:
        return found.pop(), None
    if not found:
        return None, ("no client of ours has %s in their accounts, so I "
                      "cannot tell whose meeting this is" % needle)
    return None, ("%s appears under more than one client, so I will not "
                  "choose one" % needle)
