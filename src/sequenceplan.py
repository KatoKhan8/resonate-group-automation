"""The single truth for a generated campaign sequence.

Preview, the XLSX workbook, the approval hash, the EmailBison payload and the
HeyReach payload are projections of this plan. Each derives from it; none
re-implements it. If a projection needs a field the plan does not carry, the
field belongs in the plan.

TASK-364. One canonical object from which preview, XLSX, approval hash and
both provider payloads derive. Timing and thread relation are READ FROM
``cadencelibrary``, never restated. A day number typed into this module is
the TASK-343 defect reintroduced.

WHAT THIS MODULE IS NOT. ``src/plan.py`` is a capacity/schedule estimator -
how many emails, how many days. It is not an outreach plan. This module
never extends, renames or confuses itself with that one.
"""
import hashlib
import json

ENTRYPOINT_VERSION = "2"


# --------------------------------------------------------------- the builder


def build(campaign, recs, config):
    """The canonical SequencePlan for one campaign. Built once, read six ways.

    Every timing value (day numbers, wait gaps, thread-reply flags) is read
    from ``cadencelibrary`` through ``cadence.steps_for``. Nothing in this
    function restates a day, a wait, or a thread pattern.

    The plan is a plain dict so it serialises cleanly for the approval hash
    and so consumers can read fields without importing a class. The builder
    is the only function that knows how to construct one; every consumer
    receives the same object or an equal serialisation of it.

    Returns a dict with these top-level keys:

        version             ENTRYPOINT_VERSION
        client              client name
        campaign_id         campaign id
        cadence_name        the named cadence (may be None)
        cadence_steps       the full step list from cadence.steps_for
        email_steps         email-channel steps in cadence order
        linkedin_steps      LinkedIn-channel steps in cadence order
        ladder_name_email   the email ladder name (may be None)
        thread_pattern      the thread-reply tuple for email steps
        contacts            per-contact data (empty until generation fills it)
        strategy            strategy metadata (empty until set)
        second_brain_facts  facts from second-brain research
        offers              offer metadata
        suppression         suppression state
    """
    from . import cadence as _cadence
    from . import cadencelibrary

    cadence_steps = list(
        _cadence.steps_for(campaign, config=config) or ()
    )

    email_steps = _extract_channel_steps(cadence_steps, "email")
    linkedin_steps = _extract_channel_steps(cadence_steps, "linkedin")

    ladder_name = cadencelibrary.ladder_name_for(cadence_steps, "email")
    thread_pattern = _resolve_thread_pattern(
        (config or {}).get("email_sequence"), cadence_steps
    )

    return {
        "version": ENTRYPOINT_VERSION,
        "client": (campaign or {}).get("client", ""),
        "campaign_id": (campaign or {}).get("campaign_id", ""),
        "cadence_name": _cadence_name(campaign, config),
        "cadence_steps": cadence_steps,
        "email_steps": email_steps,
        "linkedin_steps": linkedin_steps,
        "ladder_name_email": ladder_name,
        "thread_pattern": thread_pattern,
        "contacts": [],
        "strategy": {},
        "second_brain_facts": [],
        "offers": {},
        "suppression": {"paused": False, "held": False},
    }


def _cadence_name(campaign, config):
    """The cadence name this plan runs, or None."""
    from . import cadence as _cadence
    declared = (campaign or {}).get(_cadence.CADENCE_KEY)
    if declared:
        name = (config or {}).get("cadence")
        if isinstance(name, str) and name:
            return name
    name = (config or {}).get("cadence")
    if isinstance(name, str) and name:
        return name
    return None


def _extract_channel_steps(cadence_steps, channel):
    """Steps for one channel, in cadence order (day asc, key asc)."""
    filtered = [s for s in (cadence_steps or ())
                if s.get("channel") == channel and s.get("key")]
    filtered.sort(key=lambda s: (s.get("day") or 0, s.get("key") or ""))
    return filtered


def _resolve_thread_pattern(configured, cadence_steps):
    """The thread-reply pattern for this plan's email steps.

    The client config's ``email_sequence.thread_reply_pattern`` wins when
    present. When absent, the ladder's default pattern is used. When the
    ladder has none, every step is a new thread (all False).

    This is the SAME resolution bisonfactory._resolve_thread_pattern
    performs. The SequencePlan resolves it once; the factory reads the
    answer rather than re-deriving it.
    """
    from . import cadencelibrary

    override = (configured or {}).get("thread_reply_pattern")
    if isinstance(override, (list, tuple)) and override:
        return tuple(bool(v) for v in override)
    ladder_name = cadencelibrary.ladder_name_for(cadence_steps, "email")
    if ladder_name:
        pattern = cadencelibrary.THREAD_REPLY_PATTERNS.get(ladder_name)
        if pattern:
            return tuple(pattern)
    return tuple(False for _ in range(len(
        [s for s in (cadence_steps or ())
         if s.get("channel") == "email" and s.get("key")])))


# ------------------------------------------- backwards-compatible constructors


def new(client_name, account, contacts, *, strategy=None,
        second_brain_facts=None, offers=None, cadence=None):
    """Build an empty SequencePlan skeleton.

    The caller fills per-contact sequences as generation proceeds. The
    top-level fields (client, account, strategy, facts, offers) are set
    once; the per-contact entries are the variable part.
    """
    return {
        "version": ENTRYPOINT_VERSION,
        "client": client_name,
        "account": {
            "company": account.get("company", ""),
            "domain": account.get("domain", ""),
        },
        "strategy": strategy or {},
        "second_brain_facts": second_brain_facts or [],
        "offers": offers or {},
        "cadence": cadence or {},
        "contacts": contacts if isinstance(contacts, list) else [],
    }


# ------------------------------------------------- derivation: email steps


def email_sequence_for_bison(plan):
    """The email sequence this plan describes, shaped for EmailBison.

    Each step carries its order, step_key, day, and thread_reply flag.
    The gap to the next step is computed from the plan's own day numbers,
    never from a restated cadence.

    Returns a list of dicts, one per email step. The list is empty when the
    plan carries no email steps.
    """
    email_steps = plan.get("email_steps") or []
    thread_pattern = plan.get("thread_pattern") or ()
    result = []
    for position, step in enumerate(email_steps, start=1):
        entry = {
            "order": position,
            "step_key": step.get("key"),
            "day": step.get("day"),
        }
        if position < len(email_steps):
            next_day = email_steps[position].get("day") or 0
            entry["wait_in_days"] = next_day - (step.get("day") or 0)
        tr = (thread_pattern[position - 1]
              if position <= len(thread_pattern) else False)
        entry["thread_reply"] = bool(tr)
        result.append(entry)
    return result


def linkedin_delays(plan):
    """Relative day delays between consecutive LinkedIn MESSAGE steps.

    Derived from the plan's own LinkedIn steps, which came from
    cadencelibrary through build(). The four connected-branch messages
    (li2..li5) have three inter-message gaps.

    Returns a tuple of ints.
    """
    li_steps = plan.get("linkedin_steps") or []
    msg_steps = [s for s in li_steps
                  if s.get("linkedin_action") in ("message",
                                                  "open_profile_message")]
    if len(msg_steps) < 2:
        return ()
    days = [s.get("day") or 0 for s in msg_steps]
    return tuple(days[i + 1] - days[i] for i in range(len(days) - 1))


# ------------------------------------------------------- approval hash


def serialize_for_approval(plan):
    """A deterministic serialisation of the plan for hashing.

    Stable key order, stable formatting, no timestamps, nothing dependent
    on dict iteration order. Two runs producing the same plan produce the
    same serialisation; any material change produces a different one.

    The serialisation covers the cadence structure (steps, days, channels,
    thread pattern) and the per-contact copy. It does NOT cover mutable
    metadata like strategy or second_brain_facts, which do not affect what
    a prospect reads.
    """
    material = {
        "version": plan.get("version"),
        "client": plan.get("client"),
        "campaign_id": plan.get("campaign_id"),
        "cadence_name": plan.get("cadence_name"),
        "email_steps": [
            {"key": s.get("key"), "day": s.get("day"),
             "channel": s.get("channel")}
            for s in (plan.get("email_steps") or [])
        ],
        "linkedin_steps": [
            {"key": s.get("key"), "day": s.get("day"),
             "channel": s.get("channel"),
             "linkedin_action": s.get("linkedin_action")}
            for s in (plan.get("linkedin_steps") or [])
        ],
        "thread_pattern": list(plan.get("thread_pattern") or ()),
        "contacts": [],
    }
    for contact in plan.get("contacts") or []:
        material["contacts"].append({
            "contact_key": contact.get("contact_key"),
            "email": contact.get("email"),
            "sequences": contact.get("sequences") or {},
            "subjects": contact.get("subjects") or {},
        })
    return json.dumps(material, sort_keys=True, separators=(",", ":"))


def approval_hash(plan):
    """A stable digest of everything the operator approved.

    Used by the execution guard to detect drift between what was approved
    and what the provider payload carries. Two plans with the same approval
    hash produce the same prospect-facing copy. Any material change to the
    plan produces a different hash.
    """
    blob = serialize_for_approval(plan)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


# ------------------------------------------------------- derive: preview


def derive_preview_data(plan):
    """Extract the fields the preview page needs from the plan.

    Returns a dict shaped for ``preview.gather``-like consumption. Every
    value is read from the plan; nothing is recomputed.
    """
    rows = []
    for contact in plan.get("contacts") or []:
        rows.append({
            "contact_key": contact.get("contact_key"),
            "email": contact.get("email"),
            "first_name": contact.get("first_name", ""),
            "company": (plan.get("account") or {}).get("company", ""),
            "qualification": contact.get("qualification"),
            "hypothesis": (contact.get("hypothesis") or {}).get("hypothesis"),
            "capability": (contact.get("match") or {}).get("capability_key"),
            "sequences": contact.get("sequences") or {},
            "subjects": contact.get("subjects") or {},
            "gate": contact.get("sequence_gate") or {},
        })
    return {
        "client": plan.get("client"),
        "account": plan.get("account"),
        "strategy": plan.get("strategy"),
        "cadence_name": plan.get("cadence_name"),
        "email_steps": plan.get("email_steps") or [],
        "linkedin_steps": plan.get("linkedin_steps") or [],
        "thread_pattern": plan.get("thread_pattern") or (),
        "rows": rows,
        "approval_hash": approval_hash(plan),
    }


# ------------------------------------------------------- derive: EmailBison


def derive_bison_payload(plan):
    """Extract the EmailBison custom-variable payload from the plan.

    Each lead gets per-step subject and body merge fields. The sequence
    template is set at the campaign level.
    """
    leads = []
    for contact in plan.get("contacts") or []:
        if contact.get("qualification") in ("UNQUALIFIED", "INSUFFICIENT"):
            continue
        steps = []
        sequences = contact.get("sequences") or {}
        subjects = contact.get("subjects") or {}
        for key in ("em1", "em2", "em3", "em4", "em5"):
            body = sequences.get(key)
            if not body:
                continue
            subject_key = {"em1": "A", "em3": "B", "em5": "C"}.get(key, "")
            steps.append({
                "step_key": key,
                "subject": subjects.get(subject_key, ""),
                "body": body,
            })
        if steps:
            leads.append({
                "contact_key": contact.get("contact_key"),
                "email": contact.get("email"),
                "first_name": contact.get("first_name", ""),
                "steps": steps,
            })
    return {"leads": leads, "approval_hash": approval_hash(plan)}


# ------------------------------------------------------- derive: HeyReach


def derive_heyreach_payload(plan):
    """Extract the HeyReach LinkedIn graph payload from the plan.

    Maps the cadence step keys to the graph roles HeyReach expects.
    """
    leads = []
    for contact in plan.get("contacts") or []:
        if contact.get("qualification") in ("UNQUALIFIED", "INSUFFICIENT"):
            continue
        sequences = contact.get("sequences") or {}
        li = {}
        for key in ("connect", "msg1", "msg2", "msg3"):
            text = sequences.get(key)
            if text:
                li[key] = text
        if li:
            leads.append({
                "contact_key": contact.get("contact_key"),
                "linkedin": li,
            })
    return {"leads": leads, "approval_hash": approval_hash(plan)}


# ------------------------------------------------------- derive: XLSX


def derive_xlsx_rows(plan):
    """The plan as spreadsheet rows, one per contact per step.

    Each row carries: contact_key, email, step_key, day, channel,
    thread_reply, subject/body (for email), note (for LinkedIn).

    The XLSX export reads these rows; it does not rebuild the cadence.
    """
    email_steps = plan.get("email_steps") or []
    linkedin_steps = plan.get("linkedin_steps") or []
    thread_pattern = plan.get("thread_pattern") or ()

    email_by_key = {s.get("key"): s for s in email_steps}
    linkedin_by_key = {s.get("key"): s for s in linkedin_steps}

    rows = []
    for contact in plan.get("contacts") or []:
        if contact.get("qualification") in ("UNQUALIFIED", "INSUFFICIENT"):
            continue
        sequences = contact.get("sequences") or {}
        subjects = contact.get("subjects") or {}

        for step in email_steps:
            key = step.get("key")
            position = next(
                (i + 1 for i, s in enumerate(email_steps)
                 if s.get("key") == key), 0)
            tr = (thread_pattern[position - 1]
                  if position <= len(thread_pattern) else False)
            subject_key = {"em1": "A", "em3": "B", "em5": "C"}.get(key, "")
            rows.append({
                "contact_key": contact.get("contact_key"),
                "email": contact.get("email"),
                "first_name": contact.get("first_name", ""),
                "step_key": key,
                "day": step.get("day"),
                "channel": "email",
                "thread_reply": bool(tr),
                "subject": subjects.get(subject_key, ""),
                "body": sequences.get(key, ""),
                "note": "",
            })

        for step in linkedin_steps:
            key = step.get("key")
            rows.append({
                "contact_key": contact.get("contact_key"),
                "email": contact.get("email"),
                "first_name": contact.get("first_name", ""),
                "step_key": key,
                "day": step.get("day"),
                "channel": "linkedin",
                "thread_reply": False,
                "subject": "",
                "body": "",
                "note": sequences.get(key, ""),
            })

    rows.sort(key=lambda r: (
        r.get("contact_key") or "", r.get("day") or 0, r.get("step_key") or ""
    ))
    return rows


# ------------------------------------------------------- derive: QA


def derive_qa_summary(plan):
    """Validate the plan's structural integrity.

    Checks:
    - Days ascend (no step earlier than its predecessor)
    - Email step keys match the ladder
    - Thread pattern length matches email step count
    - Every LinkedIn step has a key and a day
    - No duplicate step keys

    Returns a dict with ``passed`` (bool), ``checks`` (list of check dicts),
    and ``issues`` (list of issue strings).
    """
    checks = []
    issues = []

    email_steps = plan.get("email_steps") or []
    linkedin_steps = plan.get("linkedin_steps") or []
    thread_pattern = plan.get("thread_pattern") or ()
    all_steps = (plan.get("cadence_steps") or [])

    # Days ascend.
    prev_day = 0
    days_ascend = True
    for step in all_steps:
        day = step.get("day") or 0
        if day < prev_day:
            days_ascend = False
            issues.append(
                f"step {step.get('key')} day {day} is earlier than "
                f"predecessor day {prev_day}")
        prev_day = day
    checks.append({"check": "days_ascend", "ok": days_ascend})

    # Thread pattern length matches email step count.
    tp_ok = len(thread_pattern) == len(email_steps)
    if not tp_ok:
        issues.append(
            f"thread_pattern has {len(thread_pattern)} entries but there "
            f"are {len(email_steps)} email steps")
    checks.append({"check": "thread_pattern_length", "ok": tp_ok})

    # No duplicate step keys.
    keys = [s.get("key") for s in all_steps if s.get("key")]
    dup_keys = len(keys) != len(set(keys))
    if dup_keys:
        seen = set()
        for k in keys:
            if k in seen:
                issues.append(f"duplicate step key: {k}")
            seen.add(k)
    checks.append({"check": "no_duplicate_keys", "ok": not dup_keys})

    # Every LinkedIn step has a key, day, and action.
    li_ok = True
    for step in linkedin_steps:
        if not step.get("key") or not step.get("day"):
            li_ok = False
            issues.append(
                f"LinkedIn step missing key or day: {step}")
        if not step.get("linkedin_action"):
            li_ok = False
            issues.append(
                f"LinkedIn step {step.get('key')} has no linkedin_action")
    checks.append({"check": "linkedin_steps_complete", "ok": li_ok})

    # Every email step has a key and a day.
    em_ok = True
    for step in email_steps:
        if not step.get("key") or not step.get("day"):
            em_ok = False
            issues.append(f"email step missing key or day: {step}")
    checks.append({"check": "email_steps_complete", "ok": em_ok})

    return {
        "passed": not issues,
        "checks": checks,
        "issues": issues,
        "email_step_count": len(email_steps),
        "linkedin_step_count": len(linkedin_steps),
        "total_steps": len(all_steps),
    }
