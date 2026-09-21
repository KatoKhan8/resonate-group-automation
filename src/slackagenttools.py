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
        for row in found:
            row.pop("contact", None)
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
        contacts = record.get("contacts") or []
        out.append({
            "domain": record.get("domain"),
            "state": record.get("state"),
            "icp_verdict": (record.get("icp") or {}).get("verdict"),
            "contacts": len(contacts),
            "contact_states": _count(c.get("state") for c in contacts),
        })
    return {"read_at": _now(), "workspace": slug, "matches": len(hits),
            "accounts": out}


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
    """What happens next, and what it is waiting on."""
    pack = knowledge.pack()
    text = knowledge._read(
        "docs/PRODUCTION-HANDOFF-2026-09-21-EVENING.md") or ""
    actions = []
    import re
    block = re.search(r"^## 11\. TOMORROW'S FIRST THREE ACTIONS"
                      r"([\s\S]*?)^## ", text, re.M)
    if block:
        for match in re.finditer(r"^\d+\.\s+(.+?)(?=^\d+\.|\Z)",
                                 block.group(1).strip(), re.M | re.S):
            actions.append(" ".join(match.group(1).split())[:400])
    if not scope.is_internal:
        return {"read_at": _now(),
                "note": "the next actions list is internal"}
    return {"read_at": _now(),
            "source": "docs/PRODUCTION-HANDOFF-2026-09-21-EVENING.md",
            "next_actions": actions,
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
        return {"read_at": _now(),
                "_error": "%s failed: %s" % (name, type(exc).__name__)}


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


def _find_contacts(slug, needle, limit=5):
    out = []
    for record in _records(slug):
        for key, contact in (record.get("contacts") or {}).items() \
                if isinstance(record.get("contacts"), dict) \
                else enumerate(record.get("contacts") or []):
            if not isinstance(contact, dict):
                continue
            address = str(contact.get("email") or "").lower()
            if needle not in address and needle not in str(
                    record.get("domain") or "").lower():
                continue
            row = {"domain": record.get("domain"),
                   "state": contact.get("state"),
                   "verification": (contact.get("verification") or {}).get(
                       "state"),
                   "channel_states": contact.get("channels"),
                   "contact": address}
            out.append(row)
            if len(out) >= limit:
                return out
    return out


def _count(values):
    out = {}
    for value in values:
        key = value or "unknown"
        out[key] = out.get(key, 0) + 1
    return out
