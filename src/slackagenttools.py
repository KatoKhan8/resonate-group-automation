#!/usr/bin/env python3
"""The bounded read-only tools the Slack agent may call before answering.

OPERATOR, 2026-09-21: "Bounded read-only tools the model may call before
answering (up to 5 per turn)."

## WHAT THE MODEL CHOOSES, AND WHAT IT DOES NOT

The model chooses a NAME from this registry and, at most, one string
argument. It does not choose a query, a table, a file or a verb. Every tool
is a Python function written here, every one of them reads, and the ones
that reach a provider reach it through `slackagentreadback`, whose import
contract forbids the write path.

So "call a tool" is the model picking one of thirteen buttons. A model that
picks the wrong button gets the wrong readback and says something unhelpful.
There is no button that changes anything.

## SCOPE IS CHECKED HERE, NOT AT THE PROMPT

`for_scope(scope)` returns only the tools that scope may call, and `run`
refuses a tool the scope does not carry even if it is asked for by name.
A client channel cannot call `who_does_what` or `credits`, and its
`lead_lookup` is pinned to its own workspace before the lookup happens - so
a prompt-injected "look up this lead at another client" reads that client's
store and finds nothing, because it never looks there.

## THE BUDGET

`MAX_CALLS_PER_TURN = 5`. Not a performance limit: an agent that can call
tools in a loop can be driven into one by a message, and a fixed budget
turns that from an outage into a worse answer.
"""
import json
import os
import time

from . import slackagentreadback as readback
from . import slackknowledge as knowledge
from . import slackscope

MAX_CALLS_PER_TURN = 5

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class ToolRefused(RuntimeError):
    """The tool does not exist, or this scope may not call it."""


# ------------------------------------------------------------ the tools

def workspace_summary(scope, argument=None):
    """Everything configured for one client: ICP, personas, angles, caps."""
    slug = _workspace_for(scope, argument)
    pack = knowledge.pack()
    entry = (pack.get("workspaces") or {}).get(slug)
    if not entry:
        return {"read_at": _now(),
                "_error": "no workspace %r in the knowledge pack" % slug}
    return entry


def campaign_detail(scope, argument=None):
    """One campaign as the PROVIDER states it: status, sent, queue rows."""
    campaign_id = str(argument or "").strip()
    if not campaign_id.isdigit():
        return {"read_at": _now(),
                "_error": "campaign_detail needs a numeric campaign id"}
    if not _campaign_is_visible(scope, campaign_id):
        return {"read_at": _now(),
                "_error": "campaign %s does not belong to this channel's "
                          "workspace" % campaign_id}
    return readback.campaign_by_id(campaign_id)


def cadence_detail(scope, argument=None):
    """The sequence: email steps and the LinkedIn graph, day by day."""
    slug = _workspace_for(scope, argument)
    entry = (knowledge.pack().get("workspaces") or {}).get(slug) or {}
    cadence = entry.get("cadence")
    if not cadence:
        return {"read_at": _now(),
                "_error": "no cadence is configured for %s" % slug}
    return dict(cadence, workspace=slug, read_at=_now())


def lead_lookup(scope, argument=None):
    """One contact's state. A CLIENT channel may name its own people.

    An internal channel gets counts and domains, never an address - the rule
    the status channel already enforces. A client channel is looking at its
    own data in its own channel, so the address is theirs to see.
    """
    needle = str(argument or "").strip().lower()
    if not needle:
        return {"read_at": _now(), "_error": "lead_lookup needs an address"}
    slug = _workspace_for(scope, None)
    found = _find_contacts(slug, needle, limit=5)
    if not found:
        return {"read_at": _now(), "matches": 0,
                "note": "nothing in %s's store matches that" % slug}
    if not scope.is_client:
        # A NAME IS AS IDENTIFYING AS AN ADDRESS. The first version stripped
        # only `contact`, which left "Jacob Faertz" in an internal answer -
        # and `notify._status_payload` refuses a person's name for the same
        # reason it refuses a mailbox.
        for row in found:
            row.pop("contact", None)
            row.pop("name", None)
    return {"read_at": _now(), "workspace": slug, "matches": len(found),
            "leads": found}


def account_lookup(scope, argument=None):
    """One account by domain: state, contacts, and whether it is approved."""
    domain = str(argument or "").strip().lower().lstrip("@")
    if not domain:
        return {"read_at": _now(), "_error": "account_lookup needs a domain"}
    slug = _workspace_for(scope, None)
    rows = _records(slug)
    hits = [r for r in rows if domain in str(r.get("domain") or "").lower()]
    if not hits:
        return {"read_at": _now(), "workspace": slug, "matches": 0,
                "note": "no account in %s's store matches %s" % (slug, domain)}
    out = []
    for record in hits[:5]:
        contacts = _contacts_of(record)
        out.append({
            "domain": record.get("domain"),
            "state": record.get("state"),
            "icp_verdict": (record.get("icp") or {}).get("verdict"),
            "contacts": len(contacts),
            "sendable_contacts": len([c for c in contacts
                                      if c.get("sendable")]),
            "contact_states": _count(c.get("state") or c.get("verdict")
                                     for c in contacts),
            "in_campaigns": campaigns_of_record(slug, record.get("id")),
        })
    return {"read_at": _now(), "workspace": slug, "matches": len(hits),
            "accounts": out}


def sender_summary(scope, argument=None):
    """How many sending accounts are working this client's campaigns.

    COUNTS AND PROVIDER IDS ONLY. The people behind the estate are real
    humans whose names live in a gitignored file, and a client is owed the
    answer to "how many senders are sending for us" without being owed the
    roster. The campaign rows carry `provider_account_id`, which is exactly
    that: a count of distinct sending accounts, no name and no address.
    """
    slug = _workspace_for(scope, argument)
    rows = _campaign_rows(slug)
    email, linkedin = set(), set()
    volume = {"email": 0, "linkedin": 0}
    live = 0
    for row in rows:
        senders = row.get("senders") or {}
        for entry in senders.get("email") or []:
            email.add(str(entry.get("provider_account_id")
                          or entry.get("account_id")))
        for entry in senders.get("linkedin") or []:
            linkedin.add(str(entry.get("provider_account_id")
                             or entry.get("account_id")))
        if (row.get("status") or "").lower() in ("approved", "launched",
                                                 "active"):
            live += 1
            for channel in ("email", "linkedin"):
                value = (row.get("daily_volume") or {}).get(channel)
                if isinstance(value, int):
                    volume[channel] += value
    out = {"read_at": _now(), "workspace": slug,
           "email_sending_accounts": len(email),
           "linkedin_sending_accounts": len(linkedin),
           "campaigns_they_serve": len(rows),
           "campaigns_approved_or_live": live,
           "combined_daily_volume": volume}
    if not email and not linkedin:
        out["note"] = ("no sending account is bound to any campaign for "
                       "this workspace yet")
    else:
        out["note"] = ("a sending account is bound to a campaign; bound is "
                       "not the same as sending, and sends_today is the "
                       "figure that says what actually went out")
    return out


#: A week, in seconds. The window "this week" means, and it is a rolling
#: seven days rather than a calendar week on purpose: a client asking on a
#: Monday means the last seven days, not the four hours since midnight.
WEEK_SECONDS = 7 * 24 * 3600


def activity_this_week(scope, argument=None):
    """What actually went out in the last seven days, per campaign.

    THE PROVIDER'S `emails_sent` IS A LIFETIME COUNTER, not a weekly one.
    Reporting it as "this week" would be the same class of error as reading
    `active` as a send, which is the error this project's register exists
    for. The weekly figure is counted from the QUEUE ROWS, each of which
    carries its own `sent_at`, and the lifetime counter is reported beside
    it so the two are never confused.
    """
    import datetime
    slug = _workspace_for(scope, argument)
    entry = (knowledge.pack().get("workspaces") or {}).get(slug) or {}
    ids = entry.get("provider_campaign_ids") or []
    cutoff = datetime.datetime.now(datetime.timezone.utc) - \
        datetime.timedelta(seconds=WEEK_SECONDS)

    rows, sent_week, lifetime, unreadable = [], 0, 0, 0
    for campaign_id in ids[:10]:
        detail = readback.campaign_by_id(campaign_id)
        if detail.get("_error"):
            unreadable += 1
            rows.append({"campaign_id": campaign_id,
                         "_error": detail["_error"]})
            continue
        week = _sent_since(campaign_id, cutoff)
        counter = detail.get("emails_sent")
        if isinstance(counter, int):
            lifetime += counter
        if isinstance(week, int):
            sent_week += week
        rows.append({"campaign_id": campaign_id,
                     "name": detail.get("name"),
                     "status": detail.get("status"),
                     "sent_last_7_days": week,
                     "sent_lifetime": counter,
                     "replied_lifetime": detail.get("replied"),
                     "bounced_lifetime": detail.get("bounced"),
                     "queue_rows": detail.get("queue_rows")})
    out = {"read_at": _now(), "workspace": slug,
           "campaigns_read": len(rows),
           "campaigns_unreadable": unreadable,
           "sent_last_7_days": sent_week,
           "sent_lifetime": lifetime,
           "campaigns": rows,
           "note": "sent_last_7_days is counted from queue rows carrying a "
                   "sent_at inside the window. sent_lifetime is the "
                   "provider's own counter and is NOT a weekly figure."}
    if unreadable:
        out["warning"] = ("%d campaign(s) could not be read, so this total "
                          "is a floor and not the whole picture" % unreadable)
    return out


def _sent_since(campaign_id, cutoff):
    """Queue rows sent since `cutoff`, or None if the queue cannot be read.

    None rather than 0. A queue that refused and a week with no sends are
    different answers, and returning 0 for both is how "nothing went out"
    gets reported for a campaign nobody could read.
    """
    import datetime
    try:
        from .providers import bison
        queue = bison.scheduled_emails(campaign_id) or []
    except Exception:                                           # noqa: BLE001
        return None
    count = 0
    for row in queue:
        stamp = row.get("sent_at")
        if not stamp:
            continue
        try:
            when = datetime.datetime.fromisoformat(
                str(stamp).replace("Z", "+00:00"))
        except ValueError:
            continue
        if when.tzinfo is None:
            when = when.replace(tzinfo=datetime.timezone.utc)
        if when >= cutoff:
            count += 1
    return count


def replies(scope, argument=None):
    """What has come back: the provider's counters and the reply feed.

    Two sources that answer different halves. The provider counts replies
    per campaign and knows nothing about what they said; the notification
    feed carries the classified ones and is the only place a positive reply
    is recorded. Both are reported, labelled, and an empty feed says it is
    empty rather than implying nobody replied.
    """
    slug = _workspace_for(scope, argument)
    entry = (knowledge.pack().get("workspaces") or {}).get(slug) or {}
    out = {"read_at": _now(), "workspace": slug}

    counted, unreadable = 0, 0
    for campaign_id in (entry.get("provider_campaign_ids") or [])[:10]:
        detail = readback.campaign_by_id(campaign_id)
        if detail.get("_error"):
            unreadable += 1
            continue
        if isinstance(detail.get("replied"), int):
            counted += detail["replied"]
    out["replies_counted_by_provider"] = counted
    if unreadable:
        out["campaigns_unreadable"] = unreadable

    try:
        from . import notify
        rows = notify.history(workspace=slug, limit=50)
    except Exception as exc:                                    # noqa: BLE001
        out["feed_error"] = type(exc).__name__
        return out

    kinds = {}
    recent = []
    for row in rows:
        kind = row.get("type") or "unknown"
        kinds[kind] = kinds.get(kind, 0) + 1
        if kind in ("positive_reply", "neutral_reply", "negative_reply"):
            recent.append({"at": row.get("at"), "type": kind,
                           "campaign": (row.get("ids") or {}).get("campaign")})
    out["reply_feed_by_kind"] = kinds
    out["classified_replies"] = recent[:10]
    if not rows:
        out["note"] = ("nothing is recorded in this workspace's "
                       "notification feed yet - that is an empty feed, not "
                       "a proven zero")
    return out


def batch_state(scope, argument=None):
    """Where the current batch stands: campaigns, accounts, enrolled.

    DELEGATES to `slackagentreadback.batch_state` when that module carries
    one. It does not on the commit this branch forked from, and the main
    session was adding it while this was written - so rather than copy it
    into a second place that can drift, this asks for the canonical one and
    falls back to reading the campaign store itself.
    """
    canonical = getattr(readback, "batch_state", None)
    state = canonical() if callable(canonical) else _batch_state_local(scope)
    if scope.is_client:
        state.pop("bound_to_provider", None)
    return state


def _batch_state_local(scope):
    """The fallback: the most recent batch, from the campaign store."""
    slug = _workspace_for(scope, None)
    entry = (knowledge.pack().get("workspaces") or {}).get(slug) or {}
    batches = entry.get("batch_history") or {}
    if not batches:
        return {"read_at": _now(), "workspace": slug,
                "note": "no batch is recorded for %s" % slug}
    latest = sorted(batches)[-1]
    row = dict(batches[latest])
    row.update({"read_at": _now(), "workspace": slug, "batch_id": latest,
                "note": "counts are ENROLLED, not sent. Ask sends_today for "
                        "what the provider has actually sent."})
    return row


def next_actions(scope, argument=None):
    """What happens next, and what it is waiting on.

    Reads `knowledge.current_state`, which follows the NEWEST handoff. An
    earlier version named the evening handoff and its section number
    directly; a night handoff landed the same day with different headings,
    and this tool went on reporting the superseded list as what was next.
    """
    if not scope.is_internal:
        return {"read_at": _now(),
                "note": "the next actions list is internal"}
    state = knowledge.pack().get("current_state") or knowledge.current_state()
    return {"read_at": _now(),
            "source": state.get("waiting_source") or state.get("source"),
            "headline": state.get("headline"),
            "waiting_on_operator": state.get("waiting_on_operator") or [],
            "problem_register": open_issues(),
            "campaigns_awaiting_decision": _awaiting_decision()}


def open_issues():
    """The problem register's rows. DELEGATES to the one reader.

    This used to parse the register itself, because `slackagentreadback.
    blocked` counted bullets and reported 47 where there are ten rows. That
    was the right call at the time and the wrong thing to keep: two readers
    of one file drift, and the operator asked for them folded into one.

    `blocked()` now counts rows, so this hands off to it and reshapes the
    answer for callers that expect this module's keys.
    """
    data = readback.blocked() or {}
    if data.get("_error"):
        return data
    return {"read_at": data.get("read_at"),
            "total": data.get("issue_rows"),
            "open": data.get("open_count"),
            "fixed": data.get("fixed_count"),
            "by_severity": data.get("by_severity"),
            "rows": data.get("open_items")}

def _awaiting_decision():
    try:
        from . import campaigns
        rows = campaigns.load()
    except Exception:                                           # noqa: BLE001
        return []
    return [{"campaign_id": str(r.get("campaign_id")),
             "status": (r.get("status") or "").lower(),
             "client": r.get("client")}
            for r in rows
            if (r.get("status") or "").lower() in (
                "review", "needs_approval", "awaiting_approval", "paused")]


def decisions_log(scope, argument=None):
    """The standing decisions with their dates, who made them, and why."""
    rows = knowledge.pack().get("policies") or []
    if not scope.is_internal:
        rows = slackscope.client_safe_policies(rows)
    return {"read_at": _now(), "decisions": rows}


def who_does_what(scope, argument=None):
    """Who works on this and what each is doing. INTERNAL ONLY."""
    return knowledge.pack().get("workers") or {}


def timeline(scope, argument=None):
    """When the project started, and the milestones since."""
    return knowledge.pack().get("timeline") or {}


def sends_today(scope, argument=None):
    """What actually went out, from the provider's own counters."""
    slug = _workspace_for(scope, None)
    entry = (knowledge.pack().get("workspaces") or {}).get(slug) or {}
    ids = entry.get("provider_campaign_ids") or []
    rows = []
    for campaign_id in ids[:8]:
        row = readback.campaign_by_id(campaign_id)
        if row.get("emails_sent") or row.get("queue_rows"):
            rows.append(row)
    return {"read_at": _now(), "workspace": slug,
            "campaigns_read": len(rows),
            "campaigns": rows,
            "note": "enrolled is not sent; emails_sent is the provider's "
                    "own counter and queue_sent_rows is the queue's"}


def held_by_reason(scope, argument=None):
    """Why leads are held, grouped by reason. Counts only.

    Same delegation as `batch_state`: the canonical `stages` readback if the
    module has one, otherwise the staging journals read here.
    """
    canonical = getattr(readback, "stages", None)
    stages = canonical() if callable(canonical) else _stages_local()
    out = {"read_at": stages.get("read_at")}
    copy = stages.get("s7_copy_leads") or {}
    verify = stages.get("s5_verification_leads") or {}
    if copy.get("held_by_reason"):
        out["copy_held_by_reason"] = copy["held_by_reason"]
    if verify.get("by_state"):
        out["verification_by_state"] = verify["by_state"]
    if not out.get("copy_held_by_reason") and not out.get(
            "verification_by_state"):
        out["note"] = "no staging journal is present to group"
    return out


def _stages_local():
    """The staging journals, keyed the way `readback.stages` keys them."""
    counts = knowledge._stage_counts()
    out = {"read_at": _now()}
    if counts.get("s7_copy"):
        out["s7_copy_leads"] = counts["s7_copy"]
    if counts.get("s5_verification"):
        out["s5_verification_leads"] = counts["s5_verification"]
    return out


def credits(scope, argument=None):
    """The credit position. INTERNAL ONLY - spend is Resonate's, not a
    client's."""
    return readback.credits()


def monitors(scope, argument=None):
    """Which watchers are beating, and how long ago. INTERNAL ONLY."""
    return readback.monitors()


# ----------------------------------------------------------- the registry

#: name -> (callable, one-line description, scopes that may call it)
_INTERNAL = (slackscope.INTERNAL,)
_INTERNAL_CLIENT = (slackscope.INTERNAL, slackscope.CLIENT)
# There is deliberately no ANY tuple. Every tool reads either Resonate's
# own state or a client's, and an unbound channel is entitled to neither -
# it gets the identity section of the pack and no readback at all.

REGISTRY = {
    "workspace_summary": (
        workspace_summary,
        "a client's ICP, personas, angles, cadence, sending window and caps",
        _INTERNAL_CLIENT, "workspace slug (optional in a client channel)"),
    "campaign_detail": (
        campaign_detail,
        "one campaign from the provider: status, emails sent, queue rows",
        _INTERNAL_CLIENT, "the campaign id"),
    "cadence_detail": (
        cadence_detail,
        "the sequence day by day: email steps and the LinkedIn graph",
        _INTERNAL_CLIENT, "workspace slug (optional in a client channel)"),
    "lead_lookup": (
        lead_lookup,
        "one contact's state by address",
        _INTERNAL_CLIENT, "an email address"),
    "account_lookup": (
        account_lookup,
        "one account's state by domain, with its contact counts",
        _INTERNAL_CLIENT, "a domain"),
    "sender_summary": (
        sender_summary,
        "how many sending accounts are working this client's campaigns",
        _INTERNAL_CLIENT, None),
    "activity_this_week": (
        activity_this_week,
        "what actually went out in the last seven days, per campaign",
        _INTERNAL_CLIENT, None),
    "replies": (
        replies,
        "what has come back: provider reply counts and the classified feed",
        _INTERNAL_CLIENT, None),
    "batch_state": (
        batch_state,
        "where the current batch stands: campaigns, accounts, enrolled",
        _INTERNAL_CLIENT, None),
    "next_actions": (
        next_actions,
        "what happens next and what it waits on",
        _INTERNAL, None),
    "decisions_log": (
        decisions_log,
        "the standing decisions, dated, with who made them and why",
        _INTERNAL_CLIENT, None),
    "who_does_what": (
        who_does_what,
        "who works on this and what each is doing right now",
        _INTERNAL, None),
    # INTERNAL AND CLIENT ONLY. The milestones name campaign ids, send
    # times and the size of the sender estate - Resonate's operational
    # detail, correct in a client's own channel and not in a room nobody
    # has identified. An unbound channel gets the identity section and no
    # tool at all, which is what makes its term list able to be empty.
    "timeline": (
        timeline,
        "when the project started and the milestones since",
        _INTERNAL_CLIENT, None),
    "sends_today": (
        sends_today,
        "what actually went out, from the provider's own counters",
        _INTERNAL_CLIENT, None),
    "held_by_reason": (
        held_by_reason,
        "why leads are held, grouped by reason",
        _INTERNAL_CLIENT, None),
    "credits": (
        credits,
        "the credit position",
        _INTERNAL, None),
    "monitors": (
        monitors,
        "which watchers are beating and how long ago",
        _INTERNAL, None),
}

TOOL_NAMES = tuple(sorted(REGISTRY))


def for_scope(scope):
    """The tools this scope may call, as `{name: description}`."""
    return {name: spec[1] for name, spec in sorted(REGISTRY.items())
            if scope.kind in spec[2]}


def catalogue(scope):
    """The tool list as the model is shown it. One line each."""
    lines = []
    for name, spec in sorted(REGISTRY.items()):
        if scope.kind not in spec[2]:
            continue
        argument = (" (argument: %s)" % spec[3]) if spec[3] else \
            " (no argument)"
        lines.append("  %s - %s%s" % (name, spec[1], argument))
    return "\n".join(lines)


def run(scope, name, argument=None):
    """One tool call. Refuses rather than widening a scope."""
    spec = REGISTRY.get(name)
    if spec is None:
        raise ToolRefused("no tool named %r" % (name,))
    function, _description, scopes, _argument_help = spec
    if scope.kind not in scopes:
        raise ToolRefused(
            "a %s channel may not call %r" % (scope.kind, name))
    try:
        return function(scope, argument)
    except Exception as exc:                                    # noqa: BLE001
        # THE MESSAGE, NOT JUST THE TYPE. A bare "sender_summary failed:
        # NameError" is what this returned when two tools called a helper
        # that did not exist in this module - and because the model is
        # handed the readback and asked for prose, what a person SAW was a
        # polite "I don't have a confirmed sender count in front of me".
        # A broken tool read as a cautious agent. The exception text is our
        # own code's, carries no credential, and is what makes the
        # difference between a fault and a hedge visible in one line.
        return {"read_at": _now(),
                "_error": "%s failed: %s: %s"
                          % (name, type(exc).__name__, str(exc)[:200])}


def run_all(scope, calls):
    """Up to `MAX_CALLS_PER_TURN` calls. Returns `[(name, arg, result)]`.

    Over-budget calls are DROPPED and recorded as dropped, not silently
    truncated: an answer assembled from three readbacks when five were
    asked for should be able to say so.
    """
    out = []
    for index, call in enumerate(calls or []):
        name = (call or {}).get("name")
        argument = (call or {}).get("argument")
        if index >= MAX_CALLS_PER_TURN:
            out.append((name, argument,
                        {"_error": "dropped: over the %d-call budget"
                                   % MAX_CALLS_PER_TURN}))
            continue
        try:
            out.append((name, argument, run(scope, name, argument)))
        except ToolRefused as exc:
            out.append((name, argument, {"_error": str(exc)}))
    return out


# ------------------------------------------------------------- rendering

def render(results):
    """Tool results as text for the prompt. Errors shown, never dropped."""
    lines = []
    for name, argument, result in results or []:
        head = "## %s" % name
        if argument:
            head += "(%s)" % argument
        lines.append(head)
        lines.append(json.dumps(result, default=str, indent=1)[:4000])
        lines.append("")
    return "\n".join(lines)


# -------------------------------------------------------------- internals

def _workspace_for(scope, argument):
    """Which workspace a tool call is about. A client channel: only its own.

    The argument is IGNORED in a client channel rather than validated
    against it. Validating would mean answering "no" to a question about
    another client, and "no" to that question confirms the other client
    exists.
    """
    if scope.is_client:
        return scope.workspace
    slug = str(argument or "").strip().lower()
    if slug:
        return slug
    return _default_workspace()


def _default_workspace():
    try:
        from . import workspaces
        rows = workspaces.workspaces()
    except Exception:                                           # noqa: BLE001
        return "productive"
    live = [w.get("slug") for w in rows
            if ((w.get("settings") or {}).get("policy") or {}).get(
                "sending.live") == "on"]
    return live[0] if live else (rows[0].get("slug") if rows
                                 else "productive")


def _campaign_is_visible(scope, campaign_id):
    if scope.is_internal:
        return True
    if not scope.is_client:
        return False
    entry = (knowledge.pack().get("workspaces") or {}).get(
        scope.workspace) or {}
    return str(campaign_id) in (entry.get("provider_campaign_ids") or [])


def _campaign_rows(slug):
    """This workspace's campaign rows, and no other's.

    A row with no client is EXCLUDED, for the same reason `_records`
    excludes an unattributed record: an unattributed row must never reach a
    client channel, and defaulting it into one is how it would.
    """
    try:
        from . import campaigns
        rows = campaigns.load()
    except Exception:                                           # noqa: BLE001
        return []
    return [r for r in rows
            if (r.get("client") or r.get("workspace")) == slug]


def _records(slug):
    """This workspace's records, and no other's.

    The filter is on the record's own client field. A record carrying no
    client is EXCLUDED rather than included - an unattributed row is
    exactly the thing the product goal says must never reach a client
    channel.
    """
    try:
        from . import store
        rows = store.load()
    except Exception:                                           # noqa: BLE001
        return []
    return [r for r in rows
            if (r.get("client") or r.get("workspace")) == slug]


def _contacts_of(record):
    """The contact dicts of a record, whichever shape it carries.

    The production queue stores a LIST; some fixtures and older rows store a
    dict keyed by address. Reading only one shape would make a real person
    look absent, and "no, they are not in a campaign" is exactly the answer
    that must not be given wrongly.
    """
    contacts = record.get("contacts")
    if isinstance(contacts, dict):
        return [c for c in contacts.values() if isinstance(c, dict)]
    return [c for c in (contacts or []) if isinstance(c, dict)]


def campaigns_of_record(slug, record_id):
    """Which of this client's campaigns hold a given record."""
    out = []
    for row in _campaign_rows(slug):
        if record_id in (row.get("record_ids") or []):
            out.append({"campaign_id": row.get("campaign_id"),
                        "name": row.get("name"),
                        "status": row.get("status"),
                        "provider_campaign_id": row.get("bison_campaign_id")})
    return out


def _find_contacts(slug, needle, limit=5):
    out = []
    for record in _records(slug):
        domain = str(record.get("domain") or "").lower()
        for contact in _contacts_of(record):
            address = str(contact.get("email") or "").lower()
            name = str(contact.get("name") or "").lower()
            if needle not in address and needle not in domain \
                    and needle not in name:
                continue
            out.append({
                "domain": record.get("domain"),
                "record_state": record.get("state"),
                "state": contact.get("state"),
                "sendable": contact.get("sendable"),
                "verification": (contact.get("verification") or {}).get(
                    "state") or contact.get("verdict"),
                "channel_states": contact.get("channels"),
                # THE ANSWER TO "is this person in a campaign". Membership is
                # a campaign-row fact, not a contact field, so it is looked
                # up rather than read off the contact - a contact carrying a
                # `bison_lead_id` was STAGED, which is not the same thing.
                "in_campaigns": campaigns_of_record(slug, record.get("id")),
                "contact": address,
                "name": contact.get("name"),
            })
            if len(out) >= limit:
                return out
    return out


def _count(values):
    out = {}
    for value in values:
        key = value or "unknown"
        out[key] = out.get(key, 0) + 1
    return out
