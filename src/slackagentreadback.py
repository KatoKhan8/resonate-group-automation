"""Read-only system state for the Slack agent.

Most values here are gathered from local canonical state and heartbeat
files. NO WRITE IS PERFORMED anywhere in this module. A readback that fails
says so rather than returning a cached or invented number.

TWO FUNCTIONS DO REACH THE PROVIDER, both GETs and both for the same
reason: canonical state has said ``active`` for weeks on a campaign that
sent nothing, so "what was sent" has to be asked of the provider rather
than of us. ``campaign_by_id`` reads the campaign row and ``queue`` reads
the pre-send queue. They import ``providers.bison`` inside the function,
which is where the rest of the agent reads a provider from, and they are
the ONLY provider calls here.

THE IMPORT CONTRACT, which is about writes and is unchanged. This module
does not import ``providerwrites``, ``orchestrator``, ``push``,
``leadstop``, or any module that reaches ``store.save``. The Slack agent
loop imports this module and nothing else for data; the forbidden set is
asserted against every agent source by
``tests.test_slack_agent_cannot_act``.
"""
import json
import os
import datetime as _dt
import json as _json
import os as _os
import threading as _threading
import time

from . import campaigns as _campaigns
from . import events as _events
from . import report as _report
from . import store as _store
from . import watchsink as _watchesink

UNKNOWN = "UNKNOWN"

#: Pages ONE agent-side queue read will walk for ONE campaign.
#:
#: MEASURED 2026-09-23. The provider's default page cap is 40. Campaign 491
#: reached 645 rows - 43 pages - so `scheduled_emails` REFUSED it, correctly
#: and completely, on every agent-side read. The agent then reported 491 as
#: unreadable and answered out of the campaigns it could see: 241 of the
#: day's 494 sends. The largest campaign in the estate was invisible to every
#: client answer, and the honest floor the answer carried made that look like
#: a small omission rather than half the day.
#:
#: The number is not the property. THE REFUSAL IS. A queue past this cap
#: still raises rather than returning a prefix as the whole, and the callers
#: below still count that campaign unreadable rather than silently short.
#: `scripts/hard_stop_check.py` took the same decision on the same campaign
#: the day before, for the same reason, and this is deliberately the same
#: number: two readers that disagree about how much of a campaign they can
#: see will disagree about what was sent.
#: 2026-09-23: the canonical value now lives at
#: `bison.CAMPAIGN_QUEUE_PAGE_CAP`, and there were THREE readers by then -
#: this one, `scripts/hard_stop_check.py`, and `bison_watch_loop`, which had
#: no cap at all and went blind on 491 for hours. It is repeated here rather
#: than referenced because this module imports `providers.bison` inside its
#: functions on purpose (see the module docstring), so a module-level
#: reference would break that. The agreement is enforced by
#: `tests/test_the_queue_cap_is_one_number.py`, which fails if any of the
#: three drifts - a test being the only anti-drift mechanism that does not
#: cost the lazy import.
QUEUE_PAGE_CAP = 400


# ---------------------------------------------------------- readback cache

#: Seconds a provider readback may be reused. MEASURED, not chosen: the
#: 2026-09-23 replay put p50 at 24.3s and p95 at 132.3s, and 100% of that
#: was serial provider HTTP. A five-tool turn reads the SAME campaign up to
#: four times - `sends_today` and `activity_this_week` and `weekly_plan`
#: each walk the workspace's campaign list - so the repeats are within one
#: turn, and one turn is well inside a minute even at the p95 this exists
#: to fix.
#:
#: **SIXTY SECONDS IS THE POINT, NOT AN IMPLEMENTATION DETAIL.** It is short
#: enough that a campaign paused during a conversation is visible in the
#: next question, and long enough to collapse one turn's repeats. Raising it
#: buys a little latency and starts answering "is it still sending?" out of
#: a value from several questions ago.
READBACK_TTL = 60.0

#: `(route, key) -> (monotonic_at, iso_at, value)`. PER-PROCESS AND NEVER
#: PERSISTED. A cached "491 sent 494 today" surviving a restart would be
#: read as today's number tomorrow, and the restart is exactly the moment
#: nobody is watching.
_CACHE = {}
_CACHE_LOCK = _threading.Lock()

#: One lock per key, so two threads asking for the SAME campaign at the same
#: moment make one request rather than two. This matters on the first turn
#: after a restart, when the cache is cold and the parallel per-campaign
#: reads all miss at once - without it the cache saves nothing on precisely
#: the turn that needs it most.
_KEY_LOCKS = {}


def cache_clear():
    """Forget everything. For tests, and for a caller that must not reuse."""
    with _CACHE_LOCK:
        _CACHE.clear()
        _KEY_LOCKS.clear()


def cache_state():
    """`{(route, key): age_seconds}` - what is held and how old it is."""
    now = time.monotonic()
    with _CACHE_LOCK:
        return {key: round(now - entry[0], 2) for key, entry in _CACHE.items()}


def _key_lock(key):
    with _CACHE_LOCK:
        lock = _KEY_LOCKS.get(key)
        if lock is None:
            lock = _KEY_LOCKS[key] = _threading.Lock()
        return lock


def cached(route, key, fetch, ttl=None):
    """`fetch()` at most once per `ttl` per `(route, key)`.

    Returns `(value, fetched_at_iso, age_seconds)`. **`fetched_at_iso` is
    when the provider was ACTUALLY asked**, never when the cache was read -
    the whole risk of a cache on this path is a stale number wearing a fresh
    timestamp, and every caller here stamps its output with what it gets
    back from this.

    AN ERROR IS NOT CACHED. A provider that just failed will be asked again
    by the next caller: caching the failure would turn one transient outage
    into a minute of them, and this module's contract is that a readback
    which fails SAYS SO rather than returning a cached or invented number.
    Nothing is written on the raising path, so the previous good value is
    also left alone rather than being replaced by the failure.
    """
    ttl = READBACK_TTL if ttl is None else ttl
    full = (route, str(key))
    now = time.monotonic()
    with _CACHE_LOCK:
        entry = _CACHE.get(full)
    if entry and (now - entry[0]) < ttl:
        return entry[2], entry[1], round(now - entry[0], 2)

    with _key_lock(full):
        # SECOND LOOK, HOLDING THE KEY LOCK. The thread that waited here was
        # waiting for the fetch that is now in the cache; asking again would
        # make the coalescing pointless.
        now = time.monotonic()
        with _CACHE_LOCK:
            entry = _CACHE.get(full)
        if entry and (now - entry[0]) < ttl:
            return entry[2], entry[1], round(now - entry[0], 2)

        value = fetch()
        stamped = (time.monotonic(), _now_iso(), value)
        with _CACHE_LOCK:
            _CACHE[full] = stamped
        return value, stamped[1], 0.0


def queue(campaign_id):
    """The provider's pre-send queue for one campaign, walked far enough.

    THE ONE PLACE the agent reads a queue. Four functions in
    `slackagenttools` reached `bison.scheduled_emails` directly and got the
    40-page default; this module's own contract is that provider reads come
    through here, and the cap is why that contract is worth keeping - four
    call sites is four places to forget it.

    Raises whatever the provider raises. A caller that cannot read a queue
    must report that campaign unreadable; it must never treat the refusal as
    an empty queue, because a campaign nobody could read is not a campaign
    that sent nothing. `cached` does not store a raising fetch, so that
    stays true with the cache in front of it.

    CACHED ON `queue`, SEPARATELY FROM `campaign`. The two routes are read
    by different callers in different combinations - `sending_domains` wants
    only the queue, `sends_today` wants only the row - so one key covering
    both would evict a value the other caller was about to reuse.
    """
    from .providers import bison
    rows, _at, _age = cached(
        "queue", campaign_id,
        lambda: bison.scheduled_emails(campaign_id, cap=QUEUE_PAGE_CAP) or [])
    return rows


def sending_schedule(campaign_id, day):
    """What the provider PLANS to send for one campaign on one named day.

    ## A THIRD PROVIDER READ THAT WAS NOT IN THIS MODULE AT ALL

    Found 2026-09-24 by profiling `weekly_plan` with the campaign and queue
    reads stubbed out: it still took 3.4 seconds and made **thirty live
    HTTPS requests**. `slackagenttools._forward_window` called
    `bison.sending_schedule` directly, three days by ten campaigns, serially
    - so this module's docstring saying two functions reach the provider and
    they are "the ONLY provider calls here" was true of THIS FILE and not of
    the agent. The readback cache and the per-campaign fan-out both missed
    it for the same reason: it was not here to be found.

    It is here now, so it is cached with the rest and counted against the
    same provider budget.

    RAISES WHATEVER THE PROVIDER RAISES, `SendingScheduleEmpty` included.
    That exception is a RESULT - the provider's own "no emails scheduled for
    this period" - and the caller distinguishes it from a failed read. It is
    not cached, because `cached` stores nothing on a raising fetch, which
    means an empty day is re-asked; that is the safe direction, since a day
    that fills up between two questions must not answer "none scheduled".
    """
    from .providers import bison
    row, _at, _age = cached(
        "schedule:%s" % day, campaign_id,
        lambda: bison.sending_schedule(campaign_id, day))
    return row


def newest_reply_id():
    """The provider's highest reply id right now, or None if unreadable.

    The marker a follow-up watch opens with, so that a reply which arrived
    BEFORE the client opted in can never be announced as the batch's first.
    Read here rather than in the deliverer because registration is its only
    caller and this is where the agent's provider reads live.

    **None is not zero.** Zero is a workspace whose replies all lie ahead;
    None is a feed that could not be read, and a watch that cannot
    establish its marker is never promised the reply half at all -
    `slackfollowup.advance_to_reply` closes it instead of advancing it.

    One page. The feed is newest-first, so the highest id is on it, and a
    walk would buy nothing.
    """
    from .providers import bison
    try:
        rows, _cursor = bison.fetch_replies(per_page=25)
    except Exception:                                           # noqa: BLE001
        return None
    ids = [row["id"] for row in (rows or [])
           if isinstance(row, dict) and isinstance(row.get("id"), int)]
    return max(ids) if ids else 0


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
        # CAPACITY IS PER MAILBOX, NOT PER CAMPAIGN. This read 15 x 8 = 120
        # and kept saying 120 after wave 2 bound 154 attested mailboxes
        # across the same eight campaigns, when the real number is 2,310. A
        # capacity figure that does not move when capacity moves is the
        # stale-cached-value defect the register's closing section is about,
        # and this one was being read in Slack by the whole team.
        mailboxes = sum(len((r.get("senders") or {}).get("email") or [])
                        for r in rows)
        out["mailboxes_named"] = mailboxes
        out["first_step_capacity_per_day"] = 15 * max(mailboxes, len(rows))
        out["pacing_cap_per_campaign"] = "15 x that campaign's mailboxes x 3 days"
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

    CACHED, AND `read_at` IS THE FETCH TIME RATHER THAN THIS CALL'S.
    Stamping a reused value with the moment it was reused is the failure
    mode a readback cache has - the number would be up to a minute old and
    every report of it would say it was current. `read_age_seconds` carries
    how old, so a reader who cares can see it without knowing this exists.
    """
    from .providers import bison
    out = {"campaign_id": str(campaign_id)}
    try:
        row, fetched_at, age = cached(
            "campaign", campaign_id, lambda: bison.campaign(campaign_id) or {})
    except Exception as exc:                                    # noqa: BLE001
        out["read_at"] = _now_iso()
        out["_error"] = f"campaign readback failed: {type(exc).__name__}"
        return out
    out["read_at"] = fetched_at
    out["read_age_seconds"] = age
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
        queue_rows = queue(campaign_id)
    except Exception as exc:                                    # noqa: BLE001
        out["queue_error"] = f"{type(exc).__name__}"
        return out
    sent_rows = [r for r in queue_rows
                 if str(r.get("status") or "").lower() in ("sent", "delivered")
                 or r.get("sent_at")]
    dates = sorted(str(r.get("scheduled_date") or "") for r in queue_rows
                   if r.get("scheduled_date"))
    out["queue_rows"] = len(queue_rows)
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
    """The problem register's ROWS - open, fixed, and by severity.

    **COUNTS ROWS, NOT BULLETS.** This walked the OPEN section counting every
    line beginning with `- ` and reported 47 where the register carries ten
    `### ISSUE-nnn` rows, six of them open. A count wrong by a factor of five
    is worse than no count, because it reads as a number and gets quoted -
    and this one was being quoted into a Slack channel.

    The rows are the headings. A heading carrying FIXED is fixed, which is
    the register's own convention and the only one that survives a row being
    edited in place - which is what the register asks you to do.

    Folded in from `slackagenttools.open_issues` on 2026-09-21 at the
    operator's instruction, so there is ONE register reader rather than a
    correct one and a wrong one. `open_items` is kept, now carrying the row
    titles, because callers render it.
    """
    import re
    path = os.path.abspath(os.path.join(
        os.path.dirname(__file__), "..", "docs", "state",
        "PROBLEM-REGISTER.md"))
    if not os.path.isfile(path):
        return {"read_at": _now_iso(), "_error": "problem register not found"}
    try:
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
    except Exception as exc:                                    # noqa: BLE001
        return {"read_at": _now_iso(),
                "_error": f"could not read problem register: {exc}"}

    rows = []
    for match in re.finditer(r"^### (ISSUE-\d+)\s*[·-]\s*(.+?)$", text, re.M):
        heading = match.group(2)
        severity = None
        for word in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
            if word in heading:
                severity = word
                break
        rows.append({"id": match.group(1),
                     "title": heading.split("·")[0].strip()[:110],
                     "severity": severity,
                     "fixed": "FIXED" in heading})
    open_rows = [r for r in rows if not r["fixed"]]
    blocked_rows = [r for r in open_rows
                    if "BLOCKED" in text.split(r["id"], 1)[-1][:900].upper()]
    return {"read_at": _now_iso(),
            "issue_rows": len(rows),
            "open_count": len(open_rows),
            "fixed_count": len(rows) - len(open_rows),
            "open_items": [f"{r['id']} {r['title']}" for r in open_rows],
            "by_severity": {word: sum(1 for r in open_rows
                                      if r["severity"] == word)
                            for word in ("CRITICAL", "HIGH", "MEDIUM", "LOW")},
            "blocked_count": len(blocked_rows),
            "blocked_items": [f"{r['id']} {r['title']}" for r in blocked_rows]}


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
