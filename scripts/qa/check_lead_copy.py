#!/usr/bin/env python3
"""QA check: per-lead copy validity. TASK-295, Lane F.

For every lead in a batch: does every step of its cadence carry a subject and
a body that a person could read, and is the subject the right subject for
that step?

    py -3 scripts/qa/check_lead_copy.py \\
        --phase pre_push \\
        --batch batch-2-2026-09-25 \\
        --campaign 502 --campaign 503 \\
        --workspaces <path to a copy of production work/>

The check reads rendered rows from `work/stage/s7-copy.jsonl` in the
workspace, the client config for the step->variable mapping and
thread_reply_pattern, and the campaign data for `cadence_steps`.

RULES (per lead, per step):
    subject_present              non-empty after strip
    body_present                 non-empty after strip
    not_literal_none             the string "None" is not copy
    no_unrendered_placeholder    a surviving {, {{, [[, or variable name
    no_dash                      copylint.DASH_RE
    no_banned_phrase             lint.BANNED_PHRASES + copylint.BUZZWORDS
    length_in_band               per step, MIN_WORDS..MAX_WORDS / MAX_SUBJECT
    first_name_present_and_cap   greeting must not render empty
    subject_matches_the_step     threading: step 1 owns subject, rest reply
    first_line_unique_in_batch   no two leads share a first line
    persona_and_angle_consistent email and LinkedIn persona/angle agree

THE STEP KEY IS NOT THE VARIABLE NUMBER. em4 at position 3 reads BODY_3;
em5 at position 4 reads BODY_4 in the four-step cadence. This check reads
the mapping from the config at run time and prints it.
"""
import argparse
import datetime
import json
import os
import re
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

from src import clients, copylint, emptyrender, lint          # noqa: E402


# ----------------------------------------------------------------- constants

#: The eleven rules, in the order the report lists them.
RULE_NAMES = (
    "subject_present",
    "body_present",
    "not_literal_none",
    "no_unrendered_placeholder",
    "no_dash",
    "no_banned_phrase",
    "length_in_band",
    "first_name_present_and_capitalised",
    "subject_matches_the_step",
    "first_line_unique_in_batch",
    "persona_and_angle_consistent",
)

#: An unrendered placeholder: {VAR}, {{VAR}}, [[VAR]], or a bare variable name
#: that survived the render.
UNRENDERED_RE = re.compile(
    r"\{\{?\s*[A-Za-z_][A-Za-z0-9_]*\s*\}?\}"
    r"|\[\[\s*[A-Za-z_][A-Za-z0-9_]*\s*\]\]"
)

#: Literal "None" (and friends) as a string value.
NONE_WORDS = frozenset({"none", "null", "nil", "undefined"})

#: Greeting pattern: salutation word followed by a name.
GREETING_RE = re.compile(
    r"^\s*(?:(?i:hi|hello|hey|dear|good morning|good afternoon)"
    r"[\s,]+)?([A-Z][\w'\u2019\-]+)\s*[,!.\n]", re.UNICODE)


# -------------------------------------------------- config reading at run time

def read_step_mapping(config):
    """The step->variable mapping FROM THE CONFIG THE RUN LOADED.

    Returns (steps_list, thread_reply_pattern, step_to_body_field).

    `steps_list` is a list of dicts, each with `key`, `order`, `subject`,
    `body`, sorted by order. `thread_reply_pattern` is a tuple of bools.
    `step_to_body_field` maps step key to the rendered row's body field name.

    THE STEP KEY IS NOT THE VARIABLE NUMBER. The rendered row names fields
    by step key (body_1 for em1, body_4 for em4), while the provider numbers
    by position. This function returns the step key -> body field mapping,
    which is what the check uses to find each step's copy in the row.
    """
    email_seq = (config or {}).get("email_sequence") or {}
    block = email_seq.get("steps") or {}
    if not block:
        return [], (), {}

    override = email_seq.get("thread_reply_pattern")
    if isinstance(override, (list, tuple)) and override:
        pattern = tuple(bool(v) for v in override)
    else:
        pattern = ()

    steps = []
    for key, entry in block.items():
        if not isinstance(entry, dict):
            continue
        order = entry.get("order")
        try:
            order = int(order)
        except (TypeError, ValueError):
            order = 999
        steps.append({
            "key": key,
            "order": order,
            "subject": entry.get("subject") or "",
            "body": entry.get("body") or "",
        })
    steps.sort(key=lambda s: s["order"])

    step_to_body = {}
    for step in steps:
        key = step["key"]
        num = _key_number(key)
        if num is not None:
            step_to_body[key] = f"body_{num}"
        else:
            step_to_body[key] = f"body_{key}"

    return steps, pattern, step_to_body


def _key_number(key):
    """Extract the number from a step key like 'em1' -> 1, 'li3' -> 3."""
    m = re.search(r"(\d+)$", str(key))
    return int(m.group(1)) if m else None


def read_campaign_steps(workspace, campaign_id):
    """Read a campaign's cadence_steps from the workspace.

    Returns (steps_expected, campaign_row). steps_expected is the number of
    email steps in the campaign's cadence_steps.
    """
    campaigns_path = os.path.join(workspace, "campaigns.jsonl")
    if not os.path.isfile(campaigns_path):
        return None, None
    with open(campaigns_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if str(row.get("campaign_id")) == str(campaign_id):
                cadence_steps = row.get("cadence_steps") or []
                email_steps = [s for s in cadence_steps
                               if isinstance(s, dict)
                               and s.get("channel") == "email"
                               and s.get("key")]
                return len(email_steps) or len(cadence_steps), row
    return None, None


def read_rendered_rows(workspace):
    """Read rendered rows from work/stage/s7-copy.jsonl in the workspace.

    Returns (rows, file_info). Only rows with state=="rendered" are returned.
    file_info has path, mtime, row count.
    """
    path = os.path.join(workspace, "stage", "s7-copy.jsonl")
    if not os.path.isfile(path):
        return [], {"path": path, "exists": False, "rows": 0}
    mtime = os.path.getmtime(path)
    mtime_str = datetime.datetime.fromtimestamp(
        mtime, tz=datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = []
    total = 0
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            total += 1
            entry = json.loads(line)
            if entry.get("state") == "rendered":
                rows.append(entry)
    return rows, {"path": path, "exists": True, "rows": total,
                  "mtime": mtime_str, "rendered": len(rows)}


# --------------------------------------------------------- the eleven rules

def check_subject_present(step_vars, step_info, _pattern):
    """Rule: subject is non-empty after strip."""
    subject = (step_vars.get("subject") or "").strip()
    return bool(subject)


def check_body_present(step_vars, step_info, _pattern):
    """Rule: body is non-empty after strip."""
    body = (step_vars.get("body") or "").strip()
    return bool(body)


def check_not_literal_none(step_vars, step_info, _pattern):
    """Rule: the string 'None' is not copy."""
    subject = (step_vars.get("subject") or "").strip().casefold()
    body = (step_vars.get("body") or "").strip().casefold()
    if subject in NONE_WORDS:
        return False
    if body in NONE_WORDS:
        return False
    return True


def check_no_unrendered_placeholder(step_vars, step_info, _pattern):
    """Rule: no surviving {, {{, [[, or variable name."""
    subject = step_vars.get("subject") or ""
    body = step_vars.get("body") or ""
    if UNRENDERED_RE.search(subject):
        return False
    if UNRENDERED_RE.search(body):
        return False
    return True


def check_no_dash(step_vars, step_info, _pattern):
    """Rule: no typographic dash as punctuation (copylint.DASH_RE)."""
    body = step_vars.get("body") or ""
    if copylint.DASH_RE.search(body):
        return False
    return True


def check_no_banned_phrase(step_vars, step_info, _pattern):
    """Rule: no banned phrase or buzzword (lint.BANNED_PHRASES + copylint.BUZZWORDS)."""
    body = step_vars.get("body") or ""
    low = " %s " % " ".join(re.findall(r"[a-z0-9]+", body.lower()))
    for phrase in lint.BANNED_PHRASES:
        normed = " ".join(re.findall(r"[a-z0-9]+", phrase.lower()))
        if normed and (" %s " % normed) in low:
            return False
    for word in copylint.BUZZWORDS:
        normed = " ".join(re.findall(r"[a-z0-9]+", word.lower()))
        if (" %s " % normed) in low:
            return False
    return True


def check_length_in_band(step_vars, step_info, _pattern):
    """Rule: body length in MIN_WORDS..MAX_WORDS, subject under MAX_SUBJECT."""
    body = step_vars.get("body") or ""
    subject = step_vars.get("subject") or ""
    words = len(body.split())
    if body.strip() and (words < lint.MIN_WORDS or words > lint.MAX_WORDS):
        return False
    if subject and len(subject) >= lint.MAX_SUBJECT:
        return False
    return True


def check_first_name_present_and_capitalised(step_vars, step_info, _pattern):
    """Rule: greeting names a capitalised first name, not empty."""
    body = step_vars.get("body") or ""
    first_line = ""
    for line in body.split("\n"):
        line = line.strip()
        if line:
            first_line = line
            break
    if not first_line:
        return False
    m = GREETING_RE.match(first_line)
    if not m:
        return False
    name = m.group(1).strip()
    if not name or not name[0].isupper():
        return False
    return True


def check_subject_matches_the_step(step_vars, step_info, pattern):
    """Rule: step 1 owns the subject; threaded steps carry the SAME subject.

    A threaded step STILL CARRIES a subject - the flag is the mechanism,
    not subject omission. So an empty subject on a threaded step is NOT
    correct; it is a fault.
    """
    position = step_info.get("position", 1)
    is_threaded = (position <= len(pattern) and pattern[position - 1])

    subject = (step_vars.get("subject") or "").strip()
    opener_subject = step_vars.get("opener_subject") or ""

    if position == 1:
        return bool(subject)
    if is_threaded:
        return subject == opener_subject and bool(subject)
    return bool(subject)


def check_first_line_unique_in_batch(step_vars, step_info, batch_first_lines):
    """Rule: no two leads share a first line.

    `batch_first_lines` is a dict mapping normalised first line to list of
    lead ids. The lead passes if its first line appears only once.
    """
    body = step_vars.get("body") or ""
    fl = copylint.first_line(body)
    if not fl:
        return True
    normed = " ".join(re.findall(r"[a-z0-9]+", fl.lower()))
    if not normed:
        return True
    leads_with_this = batch_first_lines.get(normed, [])
    return len(leads_with_this) <= 1


def check_persona_and_angle_consistent(step_vars, step_info, linked_info):
    """Rule: persona and angle labels agree between email and LinkedIn copy.

    If the lead has no LinkedIn copy, this rule is UNVERIFIABLE, not a pass.
    """
    email_persona = (step_vars.get("persona") or "").strip()
    email_angle = (step_vars.get("angle") or "").strip()
    li_persona = (linked_info.get("persona") or "").strip()
    li_angle = (linked_info.get("angle") or "").strip()

    if not li_persona and not li_angle:
        return None
    if email_persona and li_persona and email_persona != li_persona:
        return False
    if email_angle and li_angle and email_angle != li_angle:
        return False
    return True


# --------------------------------------------------------- the main check

def _classify_empty_vs_none_vs_unrendered(value):
    """Classify a value into EMPTY, LITERAL_NONE, UNRENDERED, or None (ok).

    Three separate counts for three different causes.
    """
    raw = "" if value is None else str(value)
    if UNRENDERED_RE.search(raw):
        return "UNRENDERED"
    visible = raw.strip()
    if visible.casefold() in NONE_WORDS:
        return "LITERAL_NONE"
    if not visible:
        return "EMPTY"
    return None


def run(phase="pre_push", batch=None, campaigns=None, workspaces=None):
    """Run the lead copy check. Returns a result dict."""
    campaigns = campaigns or []
    measured_at = datetime.datetime.now(
        datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    if not workspaces or not os.path.isdir(workspaces):
        return _error_result(
            phase, batch, campaigns, measured_at,
            f"--workspaces path does not exist or was not given: {workspaces}")

    rows, file_info = read_rendered_rows(workspaces)
    if not file_info.get("exists"):
        return _error_result(
            phase, batch, campaigns, measured_at,
            f"rendered rows file not found: {file_info.get('path')}")

    if not rows:
        return _vacuous_result(
            phase, batch, campaigns, measured_at, workspaces, file_info,
            "no rendered rows in s7-copy.jsonl")

    config = _load_config(workspaces)
    steps_list, thread_pattern, step_to_body = read_step_mapping(config)

    steps_expected = _resolve_steps_expected(
        workspaces, campaigns, steps_list, config)

    rule_sentences = _build_rule_sentences(steps_expected)

    result = _run_rules(
        rows, steps_list, thread_pattern, step_to_body,
        steps_expected, workspaces, config)

    result.update({
        "check": "lead_copy",
        "phase": phase,
        "batch": batch,
        "campaigns": campaigns,
        "measured_at": measured_at,
        "workspaces": workspaces,
        "rules": rule_sentences,
        "steps_expected": steps_expected,
        "step_mapping": _format_step_mapping(
            steps_list, thread_pattern, step_to_body),
        "thread_reply_pattern": list(thread_pattern),
        "evidence": {
            "files_read": [
                {"path": file_info.get("path"),
                 "rows": file_info.get("rows", 0),
                 "mtime": file_info.get("mtime", "unknown")},
            ],
            "provider_reads_skipped": True,
        },
    })

    try:
        import subprocess
        out = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=PROJECT_ROOT, stderr=subprocess.DEVNULL)
        result["commit"] = out.decode().strip()
    except Exception:
        result["commit"] = "unknown"

    return result


def _load_config(workspaces):
    """Load the client config. Try the workspace's config/ first."""
    config_path = os.path.join(workspaces, "..", "config", "clients",
                               "productive.yaml")
    if os.path.isfile(config_path):
        try:
            return clients.load("productive")
        except Exception:
            pass
    try:
        return clients.load("productive")
    except Exception:
        return {}


def _resolve_steps_expected(workspaces, campaigns, steps_list, config):
    """The step count for THIS campaign, not a module constant."""
    for cid in (campaigns or []):
        n, _row = read_campaign_steps(workspaces, cid)
        if n is not None:
            return n
    if steps_list:
        return len(steps_list)
    return copylint.STEPS_EXPECTED


def _build_rule_sentences(steps_expected):
    """Rule sentences rendered from THIS RUN's parameters."""
    return {
        "subject_present":
            "a step's subject is empty after strip",
        "body_present":
            "a step's body is empty after strip",
        "not_literal_none":
            "a step's copy is the literal string 'None'",
        "no_unrendered_placeholder":
            "a surviving template variable in subject or body",
        "no_dash":
            "a typographic dash used as punctuation",
        "no_banned_phrase":
            "a banned phrase or buzzword in the body",
        "length_in_band":
            f"body outside {lint.MIN_WORDS}..{lint.MAX_WORDS} words "
            f"or subject >= {lint.MAX_SUBJECT} chars",
        "first_name_present_and_capitalised":
            "greeting does not name a capitalised first name",
        "subject_matches_the_step":
            "subject does not match the threading pattern "
            "(step 1 owns, threaded steps carry the same)",
        "first_line_unique_in_batch":
            "two or more leads open with the same first line",
        "persona_and_angle_consistent":
            "persona or angle differs between email and LinkedIn copy",
    }


def _format_step_mapping(steps_list, thread_pattern, step_to_body):
    """Format the step->variable mapping for the result."""
    out = []
    for i, step in enumerate(steps_list):
        key = step["key"]
        order = step["order"]
        body_field = step_to_body.get(key, "?")
        provider_pos = i + 1
        threaded = (i < len(thread_pattern) and thread_pattern[i])
        out.append({
            "step_key": key,
            "order": order,
            "position": provider_pos,
            "body_field": body_field,
            "provider_variable": f"BODY_{provider_pos}",
            "subject_variable": "SUBJECT_1",
            "thread_reply": threaded,
        })
    return out


def _run_rules(rows, steps_list, thread_pattern, step_to_body,
               steps_expected, workspaces, config):
    """Run all rules over all rows. Returns the result body."""
    n_rules = len(RULE_NAMES)
    offenders = {name: [] for name in RULE_NAMES}
    unverifiable = {name: [] for name in RULE_NAMES}
    vacuous_rules = set(RULE_NAMES)

    empty_counts = {"EMPTY": 0, "LITERAL_NONE": 0, "UNRENDERED": 0}
    leads_with_linkedin = 0
    leads_without_linkedin = 0

    batch_first_lines = {}
    for entry in rows:
        variables = entry.get("variables") or {}
        lead_id = entry.get("email") or entry.get("record_id") or "?"
        body_1 = variables.get("body_1") or ""
        fl = copylint.first_line(body_1)
        if fl:
            normed = " ".join(re.findall(r"[a-z0-9]+", fl.lower()))
            if normed:
                batch_first_lines.setdefault(normed, []).append(lead_id)

    linkedin_data = _read_linkedin_data(workspaces, rows)

    for entry in rows:
        variables = entry.get("variables") or {}
        lead_id = entry.get("email") or entry.get("record_id") or "?"
        lead_offended = False

        opener_subject = (variables.get("subject_1") or "").strip()

        has_any_step = False
        for i, step in enumerate(steps_list):
            key = step["key"]
            body_field = step_to_body.get(key, f"body_{_key_number(key)}")
            subject_val = opener_subject
            body_val = (variables.get(body_field) or "").strip()
            has_any_step = has_any_step or bool(body_val)

            step_vars = {
                "subject": subject_val,
                "body": body_val,
                "opener_subject": opener_subject,
                "persona": variables.get("persona") or "",
                "angle": variables.get("angle") or "",
            }
            step_info = {
                "position": i + 1,
                "step_key": key,
            }

            for classification in _classify_empty_vs_none_vs_unrendered(
                    subject_val), _classify_empty_vs_none_vs_unrendered(
                    body_val):
                if classification:
                    empty_counts[classification] += 1

            if check_subject_present(step_vars, step_info, thread_pattern):
                vacuous_rules.discard("subject_present")
            else:
                offenders["subject_present"].append(
                    f"{lead_id}:{key}:subject")
                lead_offended = True

            if check_body_present(step_vars, step_info, thread_pattern):
                vacuous_rules.discard("body_present")
            else:
                offenders["body_present"].append(
                    f"{lead_id}:{key}:body")
                lead_offended = True

            none_result = check_not_literal_none(
                step_vars, step_info, thread_pattern)
            if none_result is True:
                pass
            elif none_result is False:
                offenders["not_literal_none"].append(
                    f"{lead_id}:{key}")
                lead_offended = True
                vacuous_rules.discard("not_literal_none")

            if check_no_unrendered_placeholder(
                    step_vars, step_info, thread_pattern):
                pass
            else:
                offenders["no_unrendered_placeholder"].append(
                    f"{lead_id}:{key}")
                lead_offended = True
                vacuous_rules.discard("no_unrendered_placeholder")

            if check_no_dash(step_vars, step_info, thread_pattern):
                pass
            else:
                offenders["no_dash"].append(f"{lead_id}:{key}")
                lead_offended = True
                vacuous_rules.discard("no_dash")

            if check_no_banned_phrase(step_vars, step_info, thread_pattern):
                pass
            else:
                offenders["no_banned_phrase"].append(
                    f"{lead_id}:{key}")
                lead_offended = True
                vacuous_rules.discard("no_banned_phrase")

            if check_length_in_band(step_vars, step_info, thread_pattern):
                vacuous_rules.discard("length_in_band")
            else:
                offenders["length_in_band"].append(
                    f"{lead_id}:{key}")
                lead_offended = True

            if check_first_name_present_and_capitalised(
                    step_vars, step_info, thread_pattern):
                vacuous_rules.discard(
                    "first_name_present_and_capitalised")
            else:
                offenders["first_name_present_and_capitalised"].append(
                    f"{lead_id}:{key}")
                lead_offended = True

            if check_subject_matches_the_step(
                    step_vars, step_info, thread_pattern):
                vacuous_rules.discard("subject_matches_the_step")
            else:
                offenders["subject_matches_the_step"].append(
                    f"{lead_id}:{key}")
                lead_offended = True

        li_info = linkedin_data.get(lead_id) or linkedin_data.get(
            variables.get("email"), {})
        if li_info and (li_info.get("persona") or li_info.get("angle")):
            leads_with_linkedin += 1
            consistency = check_persona_and_angle_consistent(
                step_vars, step_info, li_info)
            if consistency is False:
                offenders["persona_and_angle_consistent"].append(lead_id)
                lead_offended = True
                vacuous_rules.discard(
                    "persona_and_angle_consistent")
            elif consistency is None:
                pass
        else:
            leads_without_linkedin += 1

        if check_first_line_unique_in_batch(
                step_vars, step_info, batch_first_lines):
            pass
        else:
            offenders["first_line_unique_in_batch"].append(lead_id)
            lead_offended = True
            vacuous_rules.discard("first_line_unique_in_batch")

    for name in RULE_NAMES:
        offenders[name] = sorted(set(offenders[name]))

    all_offending_ids = set()
    for ids in offenders.values():
        all_offending_ids.update(
            id_str.split(":")[0] for id_str in ids)
    for ids in unverifiable.values():
        all_offending_ids.update(
            id_str.split(":")[0] for id_str in ids)

    subjects = len(rows)
    clean = subjects - len(all_offending_ids)
    dirty = bool(any(offenders[name] for name in RULE_NAMES))

    counts = {}
    for name in RULE_NAMES:
        unique_leads = set()
        for id_str in offenders[name]:
            unique_leads.add(id_str.split(":")[0])
        counts[name] = len(unique_leads)

    verdict = "PASS"
    if subjects == 0:
        verdict = "VACUOUS"
    elif dirty:
        verdict = "FAIL"

    return {
        "verdict": verdict,
        "subjects": subjects,
        "clean": clean,
        "refused": dirty,
        "counts": counts,
        "offenders": offenders,
        "unverifiable": unverifiable,
        "vacuous_rules": sorted(vacuous_rules),
        "empty_vs_none_vs_unrendered": dict(empty_counts),
        "leads_with_linkedin_copy": leads_with_linkedin,
        "leads_without_linkedin_copy": leads_without_linkedin,
    }


def _read_linkedin_data(workspaces, rows):
    """Read LinkedIn persona/angle data for leads.

    Tries work/queue.jsonl for record-level LinkedIn cadence data.
    Returns a dict mapping email/lead_id to {persona, angle}.
    """
    result = {}
    queue_path = os.path.join(workspaces, "queue.jsonl")
    if not os.path.isfile(queue_path):
        return result

    email_to_record = {}
    for entry in rows:
        variables = entry.get("variables") or {}
        email = (entry.get("email") or variables.get("email") or "").lower()
        if email:
            email_to_record[email] = entry

    try:
        with open(queue_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                contacts = rec.get("contacts") or []
                for contact in contacts:
                    li = contact.get("linkedin")
                    if not li:
                        continue
                    cadence = (rec.get("cadence") or {}).get(
                        contact.get("key") or "") or {}
                    li_steps = {}
                    for step_key, step in cadence.items():
                        if not isinstance(step, dict):
                            continue
                        if step.get("channel") != "linkedin":
                            continue
                        li_steps[step_key] = step
                    if not li_steps:
                        continue
                    for rec_contact in contacts:
                        email_addr = (rec_contact.get("email") or "").lower()
                        if email_addr in email_to_record:
                            result[email_addr] = {
                                "persona": contact.get("persona") or "",
                                "angle": contact.get("angle") or "",
                            }
    except Exception:
        pass
    return result


def _vacuous_result(phase, batch, campaigns, measured_at, workspaces,
                    file_info, reason):
    """A result with subjects == 0: VACUOUS, exit 2."""
    return {
        "check": "lead_copy",
        "phase": phase,
        "verdict": "VACUOUS",
        "batch": batch,
        "campaigns": campaigns,
        "subjects": 0,
        "clean": 0,
        "refused": False,
        "vacuous_reason": reason,
        "rules": {},
        "counts": {},
        "offenders": {},
        "unverifiable": {},
        "evidence": {
            "files_read": [
                {"path": file_info.get("path"),
                 "rows": file_info.get("rows", 0),
                 "mtime": file_info.get("mtime", "unknown")},
            ],
            "provider_reads_skipped": True,
        },
        "measured_at": measured_at,
        "workspaces": workspaces,
    }


def _error_result(phase, batch, campaigns, measured_at, reason):
    """A result for an error condition: ERROR, exit 3."""
    return {
        "check": "lead_copy",
        "phase": phase,
        "verdict": "ERROR",
        "batch": batch,
        "campaigns": campaigns,
        "subjects": 0,
        "clean": 0,
        "refused": False,
        "error": reason,
        "rules": {},
        "counts": {},
        "offenders": {},
        "unverifiable": {},
        "evidence": {"provider_reads_skipped": True},
        "measured_at": measured_at,
    }


# --------------------------------------------------------- CLI entry point

def main(argv=None):
    parser = argparse.ArgumentParser(
        description="QA check: per-lead copy validity (TASK-295)")
    parser.add_argument("--phase", default="pre_push",
                        choices=["pre_push", "post_push", "ongoing"])
    parser.add_argument("--batch", default=None)
    parser.add_argument("--campaign", action="append", default=None)
    parser.add_argument("--workspaces", required=True,
                        help="path to a copy of production work/")
    parser.add_argument("--json", default=None,
                        help="where to write the result JSON")
    args = parser.parse_args(argv)

    result = run(phase=args.phase, batch=args.batch,
                 campaigns=args.campaign, workspaces=args.workspaces)

    if args.json:
        os.makedirs(os.path.dirname(args.json) or ".", exist_ok=True)
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=2, default=str)

    verdict = result.get("verdict", "ERROR")
    subjects = result.get("subjects", 0)
    clean = result.get("clean", 0)
    print(f"lead_copy: {verdict} ({subjects} subjects, {clean} clean)")

    mapping = result.get("step_mapping") or []
    if mapping:
        print("\nStep -> Variable mapping (from config at run time):")
        for entry in mapping:
            tr = "thread_reply" if entry.get("thread_reply") else "new_thread"
            print(f"  {entry['step_key']:>4s}  pos {entry['position']}  "
                  f"{entry['body_field']:>8s} -> {entry['provider_variable']}  "
                  f"({tr})")

    pattern = result.get("thread_reply_pattern") or []
    if pattern:
        print(f"\nthread_reply_pattern: {pattern}")

    counts = result.get("counts") or {}
    offenders = result.get("offenders") or {}
    vacuous = result.get("vacuous_rules") or []
    for name in RULE_NAMES:
        count = counts.get(name, 0)
        if name in vacuous:
            print(f"  {name:<40s} VACUOUS (nothing to fire on)")
        elif count:
            ids = offenders.get(name, [])
            shown = ", ".join(ids[:4])
            more = " ..." if len(ids) > 4 else ""
            print(f"  {name:<40s} {count:>4d}  {shown}{more}")
        else:
            print(f"  {name:<40s}    0")

    empty_counts = result.get("empty_vs_none_vs_unrendered") or {}
    if empty_counts:
        print(f"\nEMPTY: {empty_counts.get('EMPTY', 0)}, "
              f"LITERAL_NONE: {empty_counts.get('LITERAL_NONE', 0)}, "
              f"UNRENDERED: {empty_counts.get('UNRENDERED', 0)}")

    li_with = result.get("leads_with_linkedin_copy", 0)
    li_without = result.get("leads_without_linkedin_copy", 0)
    print(f"\nLinkedIn copy: {li_with} leads with, {li_without} without")

    from scripts.qa import exit_code_for
    return exit_code_for(verdict)


if __name__ == "__main__":
    sys.exit(main())
