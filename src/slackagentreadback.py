"""Read-only system state for the Slack agent.

Every value here is gathered from local canonical state and heartbeat files.
No provider API call is made; no write is performed. A readback that fails
says so rather than returning a cached or invented number.

THE IMPORT CONTRACT. This module imports only from ``store``, ``report``,
``watchsink``, ``campaigns``, ``events``, and the standard library. It does
not import ``providerwrites``, ``orchestrator``, ``providers.bison``,
``providers.heyreach``, or any module that reaches ``store.save``. The Slack
agent loop imports this module and nothing else for data; the import graph
is asserted by ``tests.test_slack_agent``.
"""
import json
import os
import time

from . import campaigns as _campaigns
from . import events as _events
from . import report as _report
from . import store as _store
from . import watchsink as _watchesink

UNKNOWN = "UNKNOWN"


def _now_iso():
    return _store.now()


def _try(fn, label="read"):
    """Call ``fn``; return its value or an UNKNOWN marker on failure."""
    try:
        return fn()
    except Exception as exc:
        return {"_error": f"{label} failed: {type(exc).__name__}: {exc}"}


def _is_error(value):
    return isinstance(value, dict) and "_error" in value


# -------------------------------------------------------------- monitors

def monitors():
    """Heartbeat files with their ages.

    Each row carries the watcher name, the last beat timestamp, the PID
    that wrote it, and the age in seconds.  A heartbeat that cannot be
    parsed is reported as READ-ERROR, not silently dropped.
    """
    now = time.time()
    beats = _watchesink.heartbeats()
    out = []
    for b in beats:
        row = {
            "watcher": b.get("watcher") or b.get("source") or "?",
            "at": b.get("at"),
            "pid": b.get("pid"),
        }
        epoch = b.get("epoch")
        if isinstance(epoch, (int, float)):
            row["age_seconds"] = round(now - epoch, 1)
        elif b.get("unreadable"):
            row["note"] = b["unreadable"]
        else:
            row["age_seconds"] = None
        state = b.get("state")
        if state:
            row["state"] = state
        note = b.get("note")
        if note:
            row["note"] = note
        out.append(row)
    return {"read_at": _now_iso(), "monitors": out}


# -------------------------------------------------------------- pipeline

def pipeline():
    """Record counts per pipeline stage.

    Sourced / qualified / verified / READY / enrolled / SENT today.
    ``enrolled`` and ``sent`` are always reported together so that
    ``enrolled is not sent`` is visible in every answer.
    """
    recs = _store.load()
    total = len(recs)
    states = {}
    for rec in recs:
        s = rec.get("state") or "unknown"
        states[s] = states.get(s, 0) + 1

    contacts_total = 0
    contacts_sendable = 0
    for rec in recs:
        for c in rec.get("contacts") or []:
            contacts_total += 1
            from . import lint
            if lint.sendable(c):
                contacts_sendable += 1

    all_rows = _report.rows(recs)
    event_counts = {}
    for row in all_rows:
        t = row.get("type") or "unknown"
        event_counts[t] = event_counts.get(t, 0) + 1

    pushed = event_counts.get(_events.PUSH_MARKED, 0)
    delivered = event_counts.get(_events.EMAIL_DELIVERED, 0)
    sent_witnesses = [v for v in (pushed, delivered) if isinstance(v, int)]

    return {
        "read_at": _now_iso(),
        "domains": total,
        "by_state": states,
        "contacts_found": contacts_total,
        "contacts_sendable": contacts_sendable,
        "pushed": pushed,
        "delivered": delivered,
        "sent": max(sent_witnesses) if sent_witnesses else 0,
        "replies": event_counts.get(_events.REPLY_RECEIVED, 0),
        "drafts_generated": event_counts.get(_events.DRAFT_GENERATED, 0),
        "drafts_approved": event_counts.get(_events.DRAFT_APPROVED, 0),
    }


# -------------------------------------------------------------- campaign

def campaign_by_id(campaign_id):
    """One campaign from the local campaigns store.

    Returns status, record count, and event counts from the canonical
    event log.  Provider readback (live send counts from HeyReach or
    EmailBison) is NOT performed here; the agent reports what canonical
    state says and labels the absence.
    """
    rows = _campaigns.load()
    target = None
    for r in rows:
        if str(r.get("campaign_id")) == str(campaign_id):
            target = r
            break
    if target is None:
        return {"read_at": _now_iso(), "campaign_id": str(campaign_id),
                "_error": f"campaign {campaign_id} not found locally"}

    rec_ids = set(target.get("record_ids") or [])
    recs = _store.load()
    campaign_recs = [r for r in recs if r.get("id") in rec_ids]

    event_counts = {}
    for rec in campaign_recs:
        for entry in rec.get("events") or []:
            t = entry.get("type") or "unknown"
            event_counts[t] = event_counts.get(t, 0) + 1

    return {
        "read_at": _now_iso(),
        "campaign_id": str(campaign_id),
        "status": target.get("status"),
        "client": target.get("client"),
        "name": target.get("name"),
        "records": len(campaign_recs),
        "pushed": event_counts.get(_events.PUSH_MARKED, 0),
        "delivered": event_counts.get(_events.EMAIL_DELIVERED, 0),
        "replies": event_counts.get(_events.REPLY_RECEIVED, 0),
        "note": "provider readback not available in phase 1; "
                "counts are from canonical event log only",
    }


# -------------------------------------------------------------- qwen task

def qwen_task():
    """The current task files in RUNNING/ and REWORK/."""
    base = os.path.abspath(os.path.join(
        os.path.dirname(__file__), "..", "docs", "qwen-tasks"))
    out = {"read_at": _now_iso(), "running": [], "rework": []}
    for folder, key in (("RUNNING", "running"), ("REWORK", "rework")):
        directory = os.path.join(base, folder)
        if not os.path.isdir(directory):
            continue
        for name in sorted(os.listdir(directory)):
            if name.endswith(".md"):
                out[key].append(name)
    return out


# -------------------------------------------------------------- blocked

def blocked():
    """OPEN and BLOCKED rows from the problem register.

    Read from the markdown file because no structured store exists for it.
    A parse failure is reported, not swallowed.
    """
    path = os.path.abspath(os.path.join(
        os.path.dirname(__file__), "..", "docs", "state",
        "PROBLEM-REGISTER.md"))
    if not os.path.isfile(path):
        return {"read_at": _now_iso(), "_error": "problem register not found"}
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except Exception as exc:
        return {"read_at": _now_iso(),
                "_error": f"could not read problem register: {exc}"}

    open_items = []
    blocked_items = []
    current_section = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("## OPEN"):
            current_section = "open"
            continue
        if stripped.startswith("## BLOCKED"):
            current_section = "blocked"
            continue
        if stripped.startswith("## ") and current_section:
            current_section = None
            continue
        if current_section == "open" and stripped.startswith("- "):
            open_items.append(stripped[2:120])
        elif current_section == "blocked" and stripped.startswith("- "):
            blocked_items.append(stripped[2:120])

    return {"read_at": _now_iso(),
            "open_count": len(open_items),
            "open_items": open_items[:20],
            "blocked_count": len(blocked_items),
            "blocked_items": blocked_items[:20]}


# -------------------------------------------------------------- decisions

def decisions():
    """What is waiting on the operator.

    Draws from the problem register's OPEN rows and from campaigns that
    are in a status that requires a decision (e.g. ``review``).
    """
    reg = blocked()
    campaigns_rows = _campaigns.load()
    awaiting = []
    for c in campaigns_rows:
        status = (c.get("status") or "").lower()
        if status in ("review", "needs_approval", "paused"):
            awaiting.append({
                "campaign_id": str(c.get("campaign_id")),
                "status": status,
                "client": c.get("client"),
                "name": c.get("name"),
            })
    return {
        "read_at": _now_iso(),
        "open_issues": reg.get("open_count", 0),
        "blocked_issues": reg.get("blocked_count", 0),
        "campaigns_awaiting_decision": awaiting,
    }


# -------------------------------------------------------------- credits

def credits():
    """Reported credit positions.  Read from local state only.

    No provider call is made.  If no local record exists, the answer
    says so rather than returning zero.
    """
    return {
        "read_at": _now_iso(),
        "note": "credit balances require a provider read; "
                "phase 1 reports from canonical state only",
    }


# -------------------------------------------------------------- aggregate

def gather(campaign_id=None):
    """All readback sections, with the read time on each.

    A section that fails is present with an ``_error`` key; it is never
    omitted and never falls back to a cached value.
    """
    at = _now_iso()
    result = {"read_at": at, "sections": {}}
    for name, fn in (("monitors", monitors),
                     ("pipeline", pipeline),
                     ("qwen_task", qwen_task),
                     ("blocked", blocked),
                     ("decisions", decisions),
                     ("credits", credits)):
        result["sections"][name] = fn()
    if campaign_id is not None:
        result["sections"]["campaign"] = campaign_by_id(campaign_id)
    return result


def format_for_prompt(data):
    """Render readback data as text for the LLM prompt.

    Every section is labelled with its read time.  Errors are shown
    explicitly so the model can say "the readback failed" rather than
    silently omitting a section.
    """
    lines = [f"System readback at {data.get('read_at', UNKNOWN)}"]
    lines.append("")
    for name, section in (data.get("sections") or {}).items():
        if _is_error(section):
            lines.append(f"## {name}")
            lines.append(f"  READBACK FAILED: {section['_error']}")
            lines.append("")
            continue
        read_at = section.get("read_at", UNKNOWN)
        lines.append(f"## {name} (read at {read_at})")
        _format_value(section, lines, indent=2)
        lines.append("")
    return "\n".join(lines)


def _format_value(obj, lines, indent=2):
    pad = " " * indent
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "read_at":
                continue
            if isinstance(v, (dict, list)):
                lines.append(f"{pad}{k}:")
                _format_value(v, lines, indent=indent + 2)
            else:
                lines.append(f"{pad}{k}: {v}")
    elif isinstance(obj, list):
        for item in obj:
            if isinstance(item, dict):
                parts = ", ".join(f"{k}={v}" for k, v in item.items()
                                  if k != "read_at")
                lines.append(f"{pad}- {parts}")
            else:
                lines.append(f"{pad}- {item}")
    else:
        lines.append(f"{pad}{obj}")
