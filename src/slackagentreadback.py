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
import datetime as _dt
import json as _json
import os as _os
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
        if not isinstance(epoch, (int, float)) and b.get("at"):
            # NOT EVERY WATCHER WRITES `epoch`. notify-deliver writes `at`
            # only, and reading a missing epoch as "no heartbeat" reported a
            # healthy monitor as dead in the first live answer this agent
            # gave. A missing field is a missing field, not a silent monitor.
            try:
                stamp = str(b["at"]).replace("Z", "+00:00")
                epoch = _dt.datetime.fromisoformat(stamp).timestamp()
            except Exception:                                   # noqa: BLE001
                epoch = None
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


# -------------------------------------------------------------- stages

_STAGE_DIR = _os.path.join(
    _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
    "work", "stage")


def _stage_journal(name):
    """Latest row per key from a staging journal, or None if it is absent."""
    path = _os.path.join(_STAGE_DIR, name)
    if not _os.path.exists(path):
        return None
    latest = {}
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                row = _json.loads(line)
            except ValueError:
                continue
            key = row.get("email") or row.get("domain") or len(latest)
            latest[key] = row
    return latest


def stages():
    """The 24k track, stage by stage, from the journals the stages wrote.

    OPERATOR, 2026-09-21: "how many leads are being processed" must answer
    from these, never from campaign queue rows.

    **THREE WORDS THAT ARE NOT SYNONYMS**, and every answer built from this
    has to keep them apart:

        queue rows   PROVIDER rows - one per message the provider intends
                     to send. Campaign 352 has 96,045 of them.
        leads        PEOPLE. One per contact.
        READY        leads that cleared EVERY gate: client approval, ICP,
                     MX, two independent verifications, collision, and copy.

    A number that mixes them is worse than no number, because it will be
    quoted back later as though it meant something.
    """
    out = {"read_at": _now_iso()}

    icp = _stage_journal("s3-icp.jsonl")
    if icp is not None:
        verdicts = {}
        for row in icp.values():
            verdicts[row.get("verdict") or "unknown"] = verdicts.get(
                row.get("verdict") or "unknown", 0) + 1
        out["s3_icp_domains"] = {"total": len(icp), "by_verdict": verdicts}

    verify = _stage_journal("s5-verify.jsonl")
    if verify is not None:
        states = {}
        for row in verify.values():
            states[row.get("state") or "unknown"] = states.get(
                row.get("state") or "unknown", 0) + 1
        out["s5_verification_leads"] = {"decided": len(verify),
                                        "by_state": states}

    copy = _stage_journal("s7-copy.jsonl")
    if copy is not None:
        states = {}
        reasons = {}
        for row in copy.values():
            state = row.get("state") or "unknown"
            states[state] = states.get(state, 0) + 1
            if state == "held":
                reason = str(row.get("reason") or "").split(":")[0]
                reasons[reason] = reasons.get(reason, 0) + 1
        out["s7_copy_leads"] = {"by_state": states, "held_by_reason": reasons}

    ready = _os.path.join(_STAGE_DIR, "ready.json")
    if _os.path.exists(ready):
        try:
            with open(ready, encoding="utf-8") as handle:
                rows = _json.load(handle)
            out["ready_leads"] = len(rows)
            out["ready_accounts"] = len({str(e).split("@")[-1].lower()
                                         for e in rows})
        except Exception as exc:                                # noqa: BLE001
            out["ready_leads"] = f"READ-ERROR {type(exc).__name__}"

    try:
        from . import clientapproval as _ca
        out["client_approval_accounts"] = _ca.counts("productive")
    except Exception as exc:                                    # noqa: BLE001
        out["client_approval_accounts"] = f"READ-ERROR {type(exc).__name__}"
    return out


def batch_state():
    """Where batch 1 stands: staged, stats posted, veto, pushed, enrolled."""
    out = {"read_at": _now_iso()}
    try:
        from . import campaigns as _campaigns, store as _store
        rows = [r for r in _campaigns.load()
                if r.get("batch_id") == "batch-1-2026-09-21"]
        recs = {r.get("id"): r for r in _store.load()}
        out["campaigns"] = len(rows)
        out["accounts"] = sum(len(r.get("record_ids") or []) for r in rows)
        out["leads_enrolled_locally"] = sum(
            len((recs.get(rid) or {}).get("contacts") or [])
            for r in rows for rid in r.get("record_ids") or [])
        out["bound_to_provider"] = [r.get("bison_campaign_id") for r in rows
                                    if r.get("bison_campaign_id")]
        out["first_step_capacity_per_day"] = 15 * len(rows)
        out["pacing_cap_per_campaign"] = 45
    except Exception as exc:                                    # noqa: BLE001
        out["_error"] = f"{type(exc).__name__}"
    try:
        report = _os.path.join(_os.path.dirname(_STAGE_DIR),
                               "batch1-push-report.json")
        if _os.path.exists(report):
            with open(report, encoding="utf-8") as handle:
                out["push_report"] = _json.load(handle)
        else:
            out["pushed"] = False
    except Exception as exc:                                    # noqa: BLE001
        out["push_report"] = f"READ-ERROR {type(exc).__name__}"
    return out


# -------------------------------------------------------------- campaign

def campaign_by_id(campaign_id):
    """One campaign AS THE PROVIDER STATES IT. Read-only.

    OPERATOR, 2026-09-21: the agent answers from "read-only provider
    readbacks (campaign status, sent counts, queue rows, HeyReach leads)".

    The first version of this read the local campaigns store and labelled the
    absence of provider truth. That is the wrong answer to "what was sent
    today": canonical state has said `active` for weeks on a campaign that
    sent nothing, and this whole project's register exists because `active`,
    `in_sequence` and `scheduled` were each read as a send at some point.
    The counter and the queue row are the two witnesses, so both are read.

    READ VERBS ONLY - `campaign` and `scheduled_emails` are GETs. A write
    from this path is refused at the transport by `providerwrites`, which is
    not imported here and whose guard every mutating verb must pass.
    """
    from .providers import bison
    out = {"read_at": _now_iso(), "campaign_id": str(campaign_id)}
    try:
        row = bison.campaign(campaign_id) or {}
    except Exception as exc:                                    # noqa: BLE001
        out["_error"] = f"campaign readback failed: {type(exc).__name__}"
        return out
    out.update({
        "status": row.get("status"),
        "name": row.get("name"),
        "emails_sent": row.get("emails_sent"),
        "replied": row.get("replied"),
        "bounced": row.get("bounced"),
        "unsubscribed": row.get("unsubscribed"),
        "leads": row.get("total_leads"),
        "updated_at": row.get("updated_at"),
    })
    try:
        queue = bison.scheduled_emails(campaign_id) or []
    except Exception as exc:                                    # noqa: BLE001
        out["queue_error"] = f"{type(exc).__name__}"
        return out
    sent_rows = [r for r in queue
                 if str(r.get("status") or "").lower() in ("sent", "delivered")
                 or r.get("sent_at")]
    dates = sorted(str(r.get("scheduled_date") or "") for r in queue
                   if r.get("scheduled_date"))
    out["queue_rows"] = len(queue)
    out["queue_sent_rows"] = len(sent_rows)
    out["first_scheduled"] = dates[0] if dates else None
    return out


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
