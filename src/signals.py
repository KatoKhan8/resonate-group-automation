#!/usr/bin/env python3
"""What is happening at an account, and how sure we are it still matters.

## Signals observe canonical state; they never replace it

The most trustworthy things we know about an account are already in the
event log: who replied, who referred whom, who booked a meeting, who asked
to be removed. Those are facts this system recorded about its own actions,
and a signal layer that stored a second copy of them would be a second
place that can disagree with the first.

So first-party signals are **derived**, not stored. `derive()` reads the
event log through `account` and `accountpolicy` and reports what it finds.
Nothing here writes engagement state, and nothing here can change what a
reply meant.

The corollary matters as much: a signal never grants eligibility. An
account can be the highest-priority account in the workspace and still be
suppressed, and the screen has to say both. `hygiene` and `eligibility`
remain the only authorities on whether anything may go out.

## Evidence is not optional

A signal without evidence is a rumour with a timestamp. Every signal
carries what was observed, where it came from, and when - and
`outreachclaims` remains the only thing that decides what a *message* may
say. A HIRING_SURGE signal is a reason to prioritise an account; it is not
a licence to write "I saw you're hiring" unless the evidence behind it
would survive being quoted back.

## Freshness is part of the reading, not a filter

A funding round from last quarter and a website change from last quarter
are not equally interesting, so decay is per type rather than universal.
`weight_at` returns the signal's current weight *and* the multiplier that
produced it, because a score that cannot show its own decay is a score
nobody can argue with.

## What is not here

No external providers. Nothing in this module calls anything, and there is
no scraper, no job feed, no funding feed. `SOURCES` names where a signal
may come from so that a future integration has a shape to fill, and
`PRODUCT-GAPS.md` says plainly that none of them exists yet.
"""
import datetime

from . import accountpolicy as ap

# --------------------------------------------------------- the taxonomy
#
# Three scopes, because the question "who does this tell us about" has
# three different answers and mixing them makes a score meaningless.

ACCOUNT = "account"
PERSON = "person"
ENGAGEMENT = "engagement"
SCOPES = (ACCOUNT, PERSON, ENGAGEMENT)

# Account-level: something changed at the company.
FUNDING = "funding"
HEADCOUNT_GROWTH = "headcount_growth"
HIRING_SURGE = "hiring_surge"
NEW_EXECUTIVE = "new_executive"
NEW_MARKET = "new_market"
NEW_OFFICE = "new_office"
TECH_ADOPTION = "tech_adoption"
TECH_REMOVAL = "tech_removal"
JOB_POSTING = "job_posting"
WEBSITE_CHANGE = "website_change"
COMPANY_NEWS = "company_news"
EXPANSION = "expansion"

# Person-level: something changed about somebody.
JOB_CHANGE = "job_change"
PROMOTION = "promotion"
NEW_ROLE = "new_role"
RELEVANT_CONTENT = "relevant_content"
RESPONSIBILITY_CHANGE = "responsibility_change"

# Engagement: what happened between us and them. These are *derived* from
# the canonical reply taxonomy rather than declared here - see
# `ENGAGEMENT_SIGNAL` below, which maps outcomes we already have names for
# rather than inventing second names for the same facts.
ENGAGED_REPLY = "reply"
ENGAGED_POSITIVE = "positive_reply"
ENGAGED_REFERRAL = "referral"
ENGAGED_MEETING = "meeting"
ENGAGED_NOT_NOW = "not_now"
ENGAGED_WRONG_PERSON = "wrong_person"
ENGAGED_LEFT_COMPANY = "left_company"
ENGAGED_EXISTING_CLIENT = "existing_client"
ENGAGED_UNSUBSCRIBE = "unsubscribe"
ENGAGED_ACCOUNT_DNC = "account_dnc"
ENGAGED_CONTACTED = "contacted"

SCOPE_OF = {
    FUNDING: ACCOUNT, HEADCOUNT_GROWTH: ACCOUNT, HIRING_SURGE: ACCOUNT,
    NEW_EXECUTIVE: ACCOUNT, NEW_MARKET: ACCOUNT, NEW_OFFICE: ACCOUNT,
    TECH_ADOPTION: ACCOUNT, TECH_REMOVAL: ACCOUNT, JOB_POSTING: ACCOUNT,
    WEBSITE_CHANGE: ACCOUNT, COMPANY_NEWS: ACCOUNT, EXPANSION: ACCOUNT,
    JOB_CHANGE: PERSON, PROMOTION: PERSON, NEW_ROLE: PERSON,
    RELEVANT_CONTENT: PERSON, RESPONSIBILITY_CHANGE: PERSON,
    ENGAGED_REPLY: ENGAGEMENT, ENGAGED_POSITIVE: ENGAGEMENT,
    ENGAGED_REFERRAL: ENGAGEMENT, ENGAGED_MEETING: ENGAGEMENT,
    ENGAGED_NOT_NOW: ENGAGEMENT, ENGAGED_WRONG_PERSON: ENGAGEMENT,
    ENGAGED_LEFT_COMPANY: ENGAGEMENT, ENGAGED_EXISTING_CLIENT: ENGAGEMENT,
    ENGAGED_UNSUBSCRIBE: ENGAGEMENT, ENGAGED_ACCOUNT_DNC: ENGAGEMENT,
    ENGAGED_CONTACTED: ENGAGEMENT,
}

TYPES = tuple(SCOPE_OF)

LABEL = {
    FUNDING: "Raised funding",
    HEADCOUNT_GROWTH: "Headcount growing",
    HIRING_SURGE: "Hiring surge",
    NEW_EXECUTIVE: "New executive",
    NEW_MARKET: "Entering a new market",
    NEW_OFFICE: "Opened an office",
    TECH_ADOPTION: "Adopted a technology",
    TECH_REMOVAL: "Dropped a technology",
    JOB_POSTING: "Relevant job posting",
    WEBSITE_CHANGE: "Website changed",
    COMPANY_NEWS: "In the news",
    EXPANSION: "Expanding",
    JOB_CHANGE: "Changed job",
    PROMOTION: "Promoted",
    NEW_ROLE: "New in role",
    RELEVANT_CONTENT: "Posted something relevant",
    RESPONSIBILITY_CHANGE: "Responsibilities changed",
    ENGAGED_REPLY: "Replied",
    ENGAGED_POSITIVE: "Replied positively",
    ENGAGED_REFERRAL: "Referred us on",
    ENGAGED_MEETING: "Meeting booked",
    ENGAGED_NOT_NOW: "Asked us to come back later",
    ENGAGED_WRONG_PERSON: "Not the right person",
    ENGAGED_LEFT_COMPANY: "Left the company",
    ENGAGED_EXISTING_CLIENT: "Already a client",
    ENGAGED_UNSUBSCRIBE: "Asked to be removed",
    ENGAGED_ACCOUNT_DNC: "Company asked us to stop",
    ENGAGED_CONTACTED: "Contacted",
}

# The canonical reply outcome each engagement signal is derived from. One
# direction only: the outcome is the fact, the signal is a reading of it.
ENGAGEMENT_SIGNAL = {
    ap.POSITIVE: ENGAGED_POSITIVE,
    ap.NEUTRAL: ENGAGED_REPLY,
    ap.NEGATIVE: ENGAGED_REPLY,
    ap.NOT_NOW: ENGAGED_NOT_NOW,
    ap.NOT_ICP: ENGAGED_REPLY,
    ap.REFERRAL: ENGAGED_REFERRAL,
    ap.WRONG_PERSON: ENGAGED_WRONG_PERSON,
    ap.LEFT_COMPANY: ENGAGED_LEFT_COMPANY,
    ap.EXISTING_CLIENT: ENGAGED_EXISTING_CLIENT,
    ap.UNSUBSCRIBE: ENGAGED_UNSUBSCRIBE,
    ap.ACCOUNT_DNC: ENGAGED_ACCOUNT_DNC,
}

# --------------------------------------------------------- where it came from

FIRST_PARTY = "first_party"      # our own event log; the most trustworthy
MANUAL = "manual"                # a person entered it, and is named
PROVIDER = "provider"            # an integration - none exists yet
SOURCES = (FIRST_PARTY, MANUAL, PROVIDER)

SOURCE_LABEL = {
    FIRST_PARTY: "Observed by Resonate",
    MANUAL: "Entered by a person",
    PROVIDER: "From a data provider",
}

HIGH = "high"
MEDIUM = "medium"
LOW = "low"
CONFIDENCE = (HIGH, MEDIUM, LOW)
CONFIDENCE_WEIGHT = {HIGH: 1.0, MEDIUM: 0.7, LOW: 0.4}

# ------------------------------------------------------------- decay
#
# Half-life in days, per type. Not a universal curve: a funding round is
# still interesting a quarter later and a website change is not, and one
# number for both would be a number nobody could defend.
#
# `None` means it does not decay - a removal request is as true in a year
# as it was on the day, and letting it fade would be the one kind of
# forgetting this system must never do.
HALF_LIFE = {
    FUNDING: 180,
    HEADCOUNT_GROWTH: 120,
    HIRING_SURGE: 60,
    NEW_EXECUTIVE: 120,
    NEW_MARKET: 180,
    NEW_OFFICE: 180,
    TECH_ADOPTION: 120,
    TECH_REMOVAL: 120,
    JOB_POSTING: 45,
    WEBSITE_CHANGE: 30,
    COMPANY_NEWS: 45,
    EXPANSION: 120,
    JOB_CHANGE: 90,
    PROMOTION: 90,
    NEW_ROLE: 90,
    RELEVANT_CONTENT: 21,
    RESPONSIBILITY_CHANGE: 90,
    ENGAGED_REPLY: 90,
    ENGAGED_POSITIVE: 120,
    ENGAGED_REFERRAL: 120,
    ENGAGED_MEETING: 180,
    ENGAGED_NOT_NOW: 120,
    ENGAGED_CONTACTED: 60,
    ENGAGED_WRONG_PERSON: None,
    ENGAGED_LEFT_COMPANY: None,
    ENGAGED_EXISTING_CLIENT: None,
    ENGAGED_UNSUBSCRIBE: None,
    ENGAGED_ACCOUNT_DNC: None,
}

# Below this a signal is stale: still recorded, still visible, no longer
# contributing weight. Kept rather than deleted, because "we knew this and
# it aged out" is a different statement from "we never knew it".
STALE_BELOW = 0.15

FRESH = "fresh"
AGEING = "ageing"
STALE = "stale"
PERMANENT = "permanent"


def half_life(signal_type, config=None):
    """Days for this type's weight to halve. None means it never does."""
    override = ((config or {}).get("signals") or {}).get("half_life") or {}
    if signal_type in override:
        return override[signal_type]
    return HALF_LIFE.get(signal_type, 90)


def _days_between(then, now):
    if not then:
        return None
    try:
        start = datetime.datetime.fromisoformat(str(then))
    except ValueError:
        return None
    if start.tzinfo is None:
        start = start.replace(tzinfo=datetime.timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=datetime.timezone.utc)
    return max(0.0, (now - start).total_seconds() / 86400.0)


def weight_at(signal, now=None, config=None):
    """This signal's current weight, and the arithmetic behind it.

    Returns the decayed weight, the multiplier that produced it, the age in
    days and a freshness word. All four, because a score that cannot show
    its own decay is a score nobody can argue with.
    """
    now = now or datetime.datetime.now(datetime.timezone.utc)
    base = CONFIDENCE_WEIGHT.get(signal.get("confidence"), 0.7)
    life = half_life(signal.get("type"), config)
    age = _days_between(signal.get("observed_at"), now)

    if life is None:
        return {"weight": base, "decay": 1.0, "age_days": age,
                "freshness": PERMANENT,
                "why": "this kind of signal does not age"}
    if age is None:
        # No date is not the same as fresh. An undated signal is treated as
        # having decayed once, so it counts for something and never for
        # everything.
        return {"weight": base * 0.5, "decay": 0.5, "age_days": None,
                "freshness": AGEING,
                "why": "no observation date, so it is treated as one "
                       "half-life old"}

    decay = 0.5 ** (age / float(life))
    freshness = (FRESH if decay >= 0.7
                 else AGEING if decay >= STALE_BELOW else STALE)
    return {"weight": base * decay, "decay": decay, "age_days": age,
            "freshness": freshness,
            "why": (f"observed {age:.0f} day(s) ago; this kind halves every "
                    f"{life} days")}


def is_stale(signal, now=None, config=None):
    return weight_at(signal, now, config)["freshness"] == STALE


# -------------------------------------------------------------- the record

def signal(workspace, signal_type, *, record_id=None, contact_key=None,
           evidence=None, source=FIRST_PARTY, source_ref=None,
           observed_at=None, occurred_at=None, confidence=MEDIUM,
           created_by=None, metadata=None):
    """One observation. Evidence is required, and that is the whole point.

    A signal without evidence is a rumour with a timestamp. `evidence` is
    what was actually seen - "7 open project-management roles", not
    "scaling rapidly" - because the first can be quoted back and the second
    cannot.
    """
    if signal_type not in SCOPE_OF:
        raise ValueError(f"unknown signal type: {signal_type!r}")
    if source not in SOURCES:
        raise ValueError(f"unknown source: {source!r}")
    if confidence not in CONFIDENCE:
        raise ValueError(f"unknown confidence: {confidence!r}")
    if not evidence:
        raise ValueError("a signal needs evidence: what was observed")
    return {
        "workspace": workspace,
        "type": signal_type,
        "scope": SCOPE_OF[signal_type],
        "record_id": record_id,
        "contact_key": contact_key,
        "evidence": str(evidence)[:400],
        "source": source,
        "source_ref": source_ref,
        "observed_at": observed_at,
        "occurred_at": occurred_at,
        "confidence": confidence,
        "created_by": created_by,
        "metadata": dict(metadata or {}),
    }


# ------------------------------------------------- derived, not stored
#
# The first-party signals are read out of the event log every time they are
# asked for. Storing them would create a second copy of facts the log
# already holds, and a second copy is a second thing that can be wrong.

def derive(rec, workspace=None, config=None, now=None):
    """Every first-party signal this record's own history supports.

    Reads `account` and `accountpolicy`; writes nothing, and cannot change
    what a reply meant. A signal here is a *reading* of a canonical fact,
    and where the two ever disagree the canonical fact is right.
    """
    from . import account, events as event_model

    workspace = workspace or rec.get("client")
    out = []

    for contact in account.contacts_of(rec):
        key = contact.get("key")
        name = contact.get("name") or key
        confirmed = [t for t in account.touches(rec, key)
                     if t.get("confirmed")]
        replies = account.replies(rec, key)

        if confirmed:
            last = confirmed[-1]
            out.append(signal(
                workspace, ENGAGED_CONTACTED, record_id=rec.get("id"),
                contact_key=key,
                evidence=(f"{len(confirmed)} confirmed touch(es) to {name}, "
                          f"most recently on "
                          f"{str(last.get('at') or '')[:10]}"),
                observed_at=last.get("at"), confidence=HIGH))

        if replies:
            outcome = ap.classify_outcome(rec, key)
            kind = ENGAGEMENT_SIGNAL.get(outcome, ENGAGED_REPLY)
            # A referral is emitted once, from its edge, which names both
            # ends. Emitting it again from the reply that produced it
            # counts one fact twice and inflates the account's strength.
            if kind == ENGAGED_REFERRAL:
                kind = None
        if replies and kind:
            out.append(signal(
                workspace, kind, record_id=rec.get("id"), contact_key=key,
                evidence=(f"{name} replied on "
                          f"{str(replies[-1].get('at') or '')[:10]}"
                          + (f", classified {ap.OUTCOME_LABEL.get(outcome, outcome).lower()}"
                             if outcome else "")),
                observed_at=replies[-1].get("at"), confidence=HIGH))

        for entry in rec.get("events") or []:
            if (entry.get("type") == event_model.MEETING_MARKED
                    and entry.get("contact") == key):
                out.append(signal(
                    workspace, ENGAGED_MEETING, record_id=rec.get("id"),
                    contact_key=key,
                    evidence=f"a meeting is recorded with {name}",
                    observed_at=entry.get("at"), confidence=HIGH))

    for edge in account.referrals(rec):
        out.append(signal(
            workspace, ENGAGED_REFERRAL, record_id=rec.get("id"),
            contact_key=edge.get("to_contact"),
            evidence=(f"{edge.get('from_name') or edge.get('from_contact')} "
                      f"referred us to "
                      f"{edge.get('to_name') or edge.get('to_contact')}"),
            observed_at=edge.get("at"), confidence=HIGH))

    return sorted(out, key=lambda s: str(s.get("observed_at") or ""))


def summarise(signals, now=None, config=None):
    """Signals with their current weight, freshest and heaviest first."""
    rows = []
    for entry in signals or []:
        weight = weight_at(entry, now, config)
        rows.append({**entry, **weight,
                     "label": LABEL.get(entry["type"], entry["type"]),
                     "source_label": SOURCE_LABEL.get(entry["source"],
                                                      entry["source"])})
    rows.sort(key=lambda r: (-r["weight"], str(r.get("observed_at") or "")))
    return rows


def strength(signals, now=None, config=None):
    """One number for how much is happening here, and the parts of it.

    Saturating rather than additive: ten stale job postings must not add up
    to a referral. The curve is `total / (total + 2)`, so the first strong
    signal moves the number a long way and the tenth weak one barely does.
    """
    rows = summarise(signals, now, config)
    contributing = [r for r in rows if r["freshness"] != STALE]
    total = sum(r["weight"] for r in contributing)
    return {
        "score": total / (total + 2.0) if total else 0.0,
        "raw": total,
        "contributing": contributing,
        "stale": [r for r in rows if r["freshness"] == STALE],
        "count": len(contributing),
    }


# ------------------------------------------------------------- storage
#
# Only signals that are *not* derivable live here: manual entries, and one
# day a provider's. First-party signals are read from the event log every
# time, so storing them would create a second copy of facts the log
# already holds.
#
# Append-only, like every other log in this system. A signal is an
# observation, and an observation that can be edited is not one.

import json
import os


def path():
    """Beside the queue, so it follows wherever state is redirected."""
    from . import store

    return os.path.abspath(
        os.environ.get("SIGNALS")
        or os.path.join(os.path.dirname(store.queue_path()), "signals.jsonl"))


def load(workspace=None, file_path=None):
    """Stored signals, newest last. Filtered to one workspace when asked.

    The filter is not an optimisation - it is the tenancy boundary. A
    caller that wants one workspace's signals must not be handed another's.
    """
    file_path = file_path or path()
    if not os.path.exists(file_path):
        return []
    out = []
    with open(file_path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue                # a corrupt line observes nothing
            if workspace and row.get("workspace") != workspace:
                continue
            out.append(row)
    return out


def enterable():
    """The signal types a person may enter by hand.

    Everything except engagement. That exclusion is `record()`'s refusal of
    first-party sources wearing a different hat: somebody typing "they
    replied" creates a second copy of a fact the event log already holds,
    and between two copies the handwritten one is the one that goes stale.
    Reply state moves through `accountpolicy.apply_reply` and nowhere else.
    """
    return tuple(t for t in TYPES if SCOPE_OF[t] != ENGAGEMENT)


def record(entry, file_path=None):
    """Append one signal. Returns it. Never rewrites an existing row."""
    if not entry.get("workspace"):
        raise ValueError("a signal must name its workspace")
    if entry.get("source") == FIRST_PARTY:
        # Those are derived. Storing one would put a second copy of an
        # event-log fact somewhere it can drift.
        raise ValueError("first-party signals are derived, not stored")
    if SCOPE_OF.get(entry.get("type")) == ENGAGEMENT:
        # The same rule by the other route: an engagement signal with
        # `source="manual"` would slip past the check above and land as a
        # handwritten duplicate of the event log. Guarded at the door
        # rather than in the screen that happens to call it today.
        raise ValueError("engagement signals are derived from the event "
                         "log, not stored")
    file_path = file_path or path()
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, sort_keys=True) + "\n")
    return entry


def for_record(record_id, workspace=None, file_path=None):
    """Stored signals about one account.

    Reads the file. Correct for one account, and quadratic across an
    estate - see `index` below, which is what a caller working through
    more than one should use.
    """
    return [s for s in load(workspace, file_path)
            if s.get("record_id") == record_id]


def index(workspace=None, file_path=None):
    """Stored signals grouped by record, read once.

    `for_record` re-reads the whole file on every call. That is invisible
    at demo scale and quadratic beyond it: 500 accounts against a
    5,000-signal file took 19 seconds, 2,000 accounts took 96, and the
    cost grows with both terms at once. Anything looping over accounts
    builds this first and hands it down.
    """
    grouped = {}
    for entry in load(workspace, file_path):
        grouped.setdefault(entry.get("record_id"), []).append(entry)
    return grouped


def install(entries, file_path=None):
    """Replace the file with these rows. Demo and tests only.

    Guarded, and it was the last state writer that was not. `store.write_jsonl`
    covers drafts, campaigns, senders and the tag outbox; `mx`, `poller` and
    `replywatch` ask for themselves; this opened the file directly and
    truncated it, so barrier 2 never saw it. Barrier 1 covered it - `SIGNALS`
    is in `STATE_OVERRIDES` - and barrier 1 is the one a test can forget.

    It is the worst possible writer to leave unguarded, because it REPLACES
    rather than appends: `work/signals.jsonl` holds fifty `walk-N` fixture
    rows today, and whatever it held before them was truncated away rather
    than merged around.
    """
    from . import store          # deferred, as everywhere else in this module
    file_path = file_path or path()
    store.refuse_production_write(file_path)
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as handle:
        for entry in entries:
            handle.write(json.dumps(entry, sort_keys=True) + "\n")
    return entries
