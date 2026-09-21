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
import time

from . import account as _account
from . import campaigns as _campaigns
from . import clientapproval as _clientapproval
from . import events as _events
from . import notify as _notify
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


# --------------------------------------------------------- account by domain

def _find_record_by_domain(domain):
    """Find the queue record whose domain matches, or None."""
    key = _clientapproval.account_of(domain)
    if not key:
        return None
    for rec in _store.load():
        rec_domain = _clientapproval.account_of(rec.get("domain") or "")
        if rec_domain == key:
            return rec
    return None


def _find_record_by_email(address):
    """Find the queue record that carries this contact email, or None."""
    target = (address or "").strip().lower()
    if not target:
        return None
    for rec in _store.load():
        for contact in rec.get("contacts") or []:
            if (contact.get("email") or "").strip().lower() == target:
                return rec
    return None


def _find_record_by_linkedin(url):
    """Find the queue record whose contact matches this LinkedIn URL."""
    target = (url or "").strip().lower().rstrip("/")
    if not target:
        return None
    for rec in _store.load():
        for contact in rec.get("contacts") or []:
            prof = (contact.get("linkedin_url") or "").strip().lower().rstrip("/")
            if prof and prof == target:
                return rec
    return None


def _account_facts(rec):
    """The facts about one account, with no person-level detail.

    Returns domain, state, client-approval state, campaign membership,
    last touch, reply/bounce/unsubscribe counts.  No contact name and
    no email address.
    """
    domain = rec.get("domain") or ""
    approval = _clientapproval.state_of(domain)
    approval_state = (approval or {}).get("state", "unknown")

    touches = _account.touches(rec, confirmed_only=True)
    last_touch_at = touches[-1]["at"] if touches else None

    reply_events = _events.of(rec, _events.REPLY_RECEIVED)
    bounce_events = _events.of(rec, _events.EMAIL_BOUNCED)
    sent_events = _events.of(rec, _events.PUSH_MARKED)

    campaign_ids = []
    for entry in rec.get("events") or []:
        cid = entry.get("campaign_id")
        if cid and str(cid) not in campaign_ids:
            campaign_ids.append(str(cid))

    return {
        "read_at": _now_iso(),
        "domain": domain,
        "state": rec.get("state"),
        "client_approval": approval_state,
        "campaign_ids": campaign_ids,
        "last_touch_at": last_touch_at,
        "replies": len(reply_events),
        "bounces": len(bounce_events),
        "emails_sent": len(sent_events),
        "contacts_count": len(rec.get("contacts") or []),
    }


def account_by_domain(domain):
    """One account by domain.  No person-level detail.

    Returns the domain, client-approval state, campaign membership, step,
    last touch, reply/bounce/unsubscribe flags.  Domains only.
    """
    rec = _find_record_by_domain(domain)
    if rec is None:
        return {"read_at": _now_iso(), "_error": f"no record for {domain!r}"}
    return _account_facts(rec)


# ----------------------------------------------------------- lead lookup

def lead_by_identifier(identifier):
    """One lead by email or LinkedIn URL.

    Returns the same fields as ``account_by_domain`` but for the person's
    record.  The identifier is NOT echoed back - the caller must not see
    it in the answer.
    """
    identifier = (identifier or "").strip()
    if not identifier:
        return {"read_at": _now_iso(), "_error": "no identifier supplied"}

    if "@" in identifier:
        rec = _find_record_by_email(identifier)
    else:
        rec = _find_record_by_linkedin(identifier)

    if rec is None:
        return {"read_at": _now_iso(), "_error": "not found"}
    return _account_facts(rec)


# ----------------------------------------------------------- why held

def why_held(domain):
    """Why is this domain held?  Read the reasons already written down.

    Reads the record state, the verdict's ICP status, MX events, the
    drop/hold reason, and the client-approval state.  Does not re-derive.
    """
    rec = _find_record_by_domain(domain)
    if rec is None:
        return {"read_at": _now_iso(), "_error": f"no record for {domain!r}"}

    verdict = rec.get("verdict") or {}
    mx_events = _events.of(rec, *_events.MX_EVENTS)
    mx_decision = "no MX events"
    for ev in mx_events:
        if ev.get("type") == _events.EMAIL_CHANNEL_BLOCKED_MX:
            mx_decision = "blocked by MX"
        elif ev.get("type") == _events.MX_LOOKUP_COMPLETED:
            mx_decision = "MX OK"
        elif ev.get("type") == _events.MX_LOOKUP_FAILED:
            mx_decision = "MX lookup failed"

    approval = _clientapproval.state_of(domain)

    return {
        "read_at": _now_iso(),
        "domain": rec.get("domain"),
        "state": rec.get("state"),
        "drop_reason": rec.get("drop_reason"),
        "hold_reason": rec.get("hold_reason"),
        "icp_status": verdict.get("icp_status"),
        "icp_confidence": verdict.get("icp_confidence"),
        "mx_decision": mx_decision,
        "client_approval": (approval or {}).get("state", "unknown"),
    }


# --------------------------------------------------------- what was sent

def what_sent_to(domain):
    """What did we send to this domain?  Events and provider rows.

    SENT means a provider-confirmed send, never ``scheduled``.
    """
    rec = _find_record_by_domain(domain)
    if rec is None:
        return {"read_at": _now_iso(), "_error": f"no record for {domain!r}"}

    sent = []
    for entry in _events.of(rec, _events.PUSH_MARKED, _events.EMAIL_DELIVERED):
        sent.append({
            "type": entry.get("type"),
            "contact": entry.get("contact"),
            "channel": entry.get("channel"),
            "at": entry.get("at"),
            "day": entry.get("day"),
            "step": entry.get("step"),
        })

    bounced = []
    for entry in _events.of(rec, _events.EMAIL_BOUNCED):
        bounced.append({
            "contact": entry.get("contact"),
            "at": entry.get("at"),
        })

    return {
        "read_at": _now_iso(),
        "domain": rec.get("domain"),
        "sent": sent,
        "bounced": bounced,
    }


# --------------------------------------------------------- send schedule

def when_sends_next(campaign_id):
    """What does the provider say it will send on the next three days?

    Reads ``bison.sending_schedule`` for today, tomorrow and the day after.
    ``SendingScheduleEmpty`` is the provider saying NOTHING IS PLANNED -
    it is not zero and not an error.
    """
    from .providers import bison
    out = {"read_at": _now_iso(), "campaign_id": str(campaign_id),
           "days": {}}
    for day in ("today", "tomorrow", "day_after_tomorrow"):
        try:
            result = bison.sending_schedule(campaign_id, day)
            out["days"][day] = {"emails_being_sent": result.get("emails_being_sent")}
        except bison.SendingScheduleEmpty:
            out["days"][day] = {"emails_being_sent": 0, "empty": True}
        except Exception as exc:                                  # noqa: BLE001
            out["days"][day] = {"_error": f"{type(exc).__name__}"}
    return out


# --------------------------------------------------------- replies today

def replies_today():
    """How many reply events were recorded today across all records."""
    today = _dt.date.today().isoformat()
    count = 0
    for rec in _store.load():
        for entry in _events.of(rec, _events.REPLY_RECEIVED):
            at = str(entry.get("at") or "")
            if at.startswith(today):
                count += 1
    watch = _try(lambda: _watchesink.heartbeats(), "reply-watch")
    return {"read_at": _now_iso(), "replies_today": count,
            "watch_status": "available" if not _is_error(watch) else "unavailable"}


# --------------------------------------------------------- credits today

def credits_spent_today():
    """Credits spent today.  Reported, never gated."""
    today = _dt.date.today().isoformat()
    spend_path = os.path.abspath(
        os.environ.get("SPEND_LEDGER")
        or os.path.join(os.path.dirname(_store.queue_path()),
                        "spend-ledger.jsonl"))
    if not os.path.exists(spend_path):
        return {"read_at": _now_iso(), "spent_today": 0,
                "note": "no spend ledger found"}
    total = 0
    try:
        with open(spend_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                at = str(row.get("at") or "")
                if at.startswith(today):
                    total += row.get("credits", 0) or 0
    except OSError:
        return {"read_at": _now_iso(), "_error": "could not read spend ledger"}
    return {"read_at": _now_iso(), "spent_today": total}


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
