#!/usr/bin/env python3
"""How often one person, and one company, may hear from us.

## The problem multi-sender outreach creates

While a contact had one email sender and one LinkedIn sender, pacing was a
property of the cadence: the steps were days apart because the template said
so. Account-based outreach breaks that. Anna emails Monday, Petar connects
Monday, Sarah messages Tuesday, Mark emails Tuesday - each sequence is
perfectly reasonable on its own, and together they are four strangers from one
agency arriving in two days.

Nobody planned that. It is what happens when four independently-correct plans
share a recipient, and it is invisible to anything that looks at one cadence
at a time.

So spacing is coordinated *across* senders and channels, at two levels: the
person, and the company.

## Configured, never invented

Every limit here comes from workspace or campaign configuration. This module
has defaults so the system is not unbounded out of the box, but they are
stated as defaults rather than presented as best practice - "three touches a
week" is not a fact about outreach, it is a number somebody chose, and the
person choosing it should be the client's operator rather than this file.

`DEFAULTS` is the fallback and `limits()` says which values came from
configuration and which did not, so a screen can show the difference.

## Advisory at plan time, blocking at QA time

`check()` returns a verdict; it does not mutate anything. The cadence builder
uses it to warn, and campaign QA uses it to block. That split is deliberate:
somebody drafting a campaign should be able to see "this is too dense" while
still holding a half-built plan, and nothing should be able to launch through
it.
"""
import datetime

from . import account, store

# Sensible-but-arbitrary starting points. Every one of them is overridable,
# and `limits()` reports whether the value in force was configured or fell
# back to here.
DEFAULTS = {
    # One person.
    "contact.min_hours_between_touches": 24,
    "contact.max_touches_per_week": 3,
    "contact.max_touches_total": 12,
    # One company, across every decision maker.
    "account.max_active_contacts": 3,
    "account.min_hours_between_first_touches": 24,
    "account.max_touches_per_week": 8,
}

KEYS = tuple(DEFAULTS)

LABELS = {
    "contact.min_hours_between_touches":
        "Minimum hours between two touches to one person",
    "contact.max_touches_per_week":
        "Maximum touches to one person in a rolling week",
    "contact.max_touches_total":
        "Maximum touches to one person in a whole sequence",
    "account.max_active_contacts":
        "Maximum decision makers being worked at once",
    "account.min_hours_between_first_touches":
        "Minimum hours between opening two different people",
    "account.max_touches_per_week":
        "Maximum touches to one company in a rolling week",
}

OK = "ok"
WARN = "warn"
BLOCK = "block"


def _at(config, dotted):
    node = config or {}
    for part in dotted.split("."):
        if not isinstance(node, dict):
            return None
        node = node.get(part)
    return node


def limits(config=None):
    """The limits in force, and where each came from.

    A screen that shows "max 3 per week" without saying whether anybody chose
    3 invites an operator to treat a default as a decision.
    """
    out = {}
    for key, fallback in DEFAULTS.items():
        value = _at(config or {}, "fatigue." + key)
        if value is None:
            value = _at(config or {}, key)
        configured = value is not None
        try:
            value = int(value) if configured else fallback
        except (TypeError, ValueError):
            value, configured = fallback, False
        out[key] = {"key": key, "label": LABELS[key], "value": value,
                    "configured": configured, "default": fallback}
    return out


def _hours_between(first, second):
    """Hours between two ISO timestamps, or None if either is unusable."""
    for value in (first, second):
        if not value:
            return None
    try:
        a = datetime.datetime.fromisoformat(str(first))
        b = datetime.datetime.fromisoformat(str(second))
    except ValueError:
        return None
    if a.tzinfo is None or b.tzinfo is None:
        a = a.replace(tzinfo=None)
        b = b.replace(tzinfo=None)
    return abs((b - a).total_seconds()) / 3600.0


def _within_week(touches, of):
    """Touches within seven days before `of`. Unusable timestamps are kept.

    Dropping a touch whose timestamp will not parse would make the count
    smaller, which is the wrong direction for a safety limit: an unreadable
    date should not create room for another message.
    """
    if not of:
        return list(touches)
    kept = []
    for item in touches:
        gap = _hours_between(item.get("at"), of)
        if gap is None or gap <= 24 * 7:
            kept.append(item)
    return kept


# The week is measured from the PROPOSED action, never from the last one.
#
# `_within_week(confirmed, at or last["at"])` anchored the window to the most
# recent historical touch whenever no `at` was supplied - and `_hours_between`
# returns an ABSOLUTE difference, so the window was seven days either side of
# that anchor rather than a trailing week. Three touches a year ago stayed
# "3 touches in the last week" for ever, and the count never decayed.
#
# Measured on 2026-09-11: three touches, all over a year old, answered
# `block {recent: 3}` with no `at` and `ok {recent: 0}` with `at` = now.
#
# So an absent `at` means now, not "whenever we last acted". This does let
# some long-dormant records through that were blocked before - which is the
# rule doing what it always claimed to do, not a cap being loosened.
def _window_origin(at, touches):
    return at or store.now()


def contact_check(rec, contact_key, at=None, config=None):
    """Whether one more touch to this person is within policy.

    `at` is when the proposed touch would happen; without it the check is
    against the most recent confirmed touch, which is what a planner wants
    when it has not chosen a time yet.
    """
    rules = limits(config)
    confirmed = account.touches(rec, contact_key, confirmed_only=True)
    findings = []

    if not confirmed:
        return _verdict(OK, "no confirmed touch to this contact yet", rules,
                        findings, touches=0)

    last = confirmed[-1]
    gap = _hours_between(last.get("at"), at or last.get("at"))
    minimum = rules["contact.min_hours_between_touches"]["value"]
    if at and gap is not None and gap < minimum:
        findings.append((BLOCK,
                         f"only {gap:.0f}h since the last touch; the limit is "
                         f"{minimum}h"))

    recent = _within_week(confirmed, _window_origin(at, confirmed))
    weekly = rules["contact.max_touches_per_week"]["value"]
    if len(recent) >= weekly:
        findings.append((BLOCK,
                         f"{len(recent)} touches in the last week already; "
                         f"the limit is {weekly}"))
    elif len(recent) == weekly - 1:
        findings.append((WARN,
                         f"{len(recent)} touches in the last week; one more "
                         f"reaches the limit of {weekly}"))

    total = rules["contact.max_touches_total"]["value"]
    if len(confirmed) >= total:
        findings.append((BLOCK,
                         f"{len(confirmed)} touches in total; the limit is "
                         f"{total}"))

    senders = {t.get("sender_id") for t in recent if t.get("sender_id")}
    if len(senders) > 2:
        findings.append((WARN,
                         f"{len(senders)} different people have written to "
                         f"this contact in the last week"))

    return _verdict(_worst(findings), None, rules, findings,
                    touches=len(confirmed), recent=len(recent),
                    senders=sorted(s for s in senders if s))


def account_check(rec, at=None, config=None, contact_key=None):
    """Whether the company as a whole is being worked within policy."""
    rules = limits(config)
    graph = account.graph(rec)
    findings = []

    active = [c for c in graph["contacts"]
              if c["confirmed_touches"] and c["state"] in
              (account.ACTIVE, account.ENGAGED, account.STOPPED)]
    maximum = rules["account.max_active_contacts"]["value"]
    would_be = len(active)
    if contact_key and contact_key not in {c["key"] for c in active}:
        would_be += 1
    if would_be > maximum:
        findings.append((BLOCK,
                         f"{would_be} decision makers would be active at this "
                         f"company; the limit is {maximum}"))
    elif would_be == maximum:
        findings.append((WARN,
                         f"{would_be} decision makers active, which is the "
                         f"configured limit"))

    confirmed = graph["confirmed_touches"]
    recent = _within_week(confirmed, _window_origin(at, confirmed))
    weekly = rules["account.max_touches_per_week"]["value"]
    if len(recent) >= weekly:
        findings.append((BLOCK,
                         f"{len(recent)} touches at this company in the last "
                         f"week; the limit is {weekly}"))

    # Two people opened within a few hours of each other reads as a blast
    # even when each sequence is individually paced.
    firsts = sorted((c["confirmed_touches"][0]["at"]
                     for c in graph["contacts"] if c["confirmed_touches"]),
                    key=lambda value: str(value or ""))
    spacing = rules["account.min_hours_between_first_touches"]["value"]
    for earlier, later in zip(firsts, firsts[1:]):
        gap = _hours_between(earlier, later)
        if gap is not None and gap < spacing:
            findings.append((WARN,
                             f"two people at this company were first "
                             f"contacted {gap:.0f}h apart; the guidance is "
                             f"{spacing}h"))
            break

    return _verdict(_worst(findings), None, rules, findings,
                    active=len(active), touches=len(confirmed),
                    recent=len(recent))


def check(rec, contact_key, at=None, config=None):
    """Both levels at once. The call a planner or QA makes."""
    contact = contact_check(rec, contact_key, at, config)
    company = account_check(rec, at, config, contact_key)
    findings = contact["findings"] + company["findings"]
    return {
        "state": _worst([(f["level"], f["why"]) for f in findings]),
        "contact": contact,
        "account": company,
        "findings": findings,
        "limits": limits(config),
    }


def _worst(findings):
    levels = [level for level, _ in findings] if findings and \
        isinstance(findings[0], tuple) else []
    if BLOCK in levels:
        return BLOCK
    if WARN in levels:
        return WARN
    return OK


def _verdict(state, why, rules, findings, **counts):
    return {
        "state": state,
        "why": why,
        "limits": rules,
        "findings": [{"level": level, "why": text} for level, text in findings],
        "counts": counts,
    }
