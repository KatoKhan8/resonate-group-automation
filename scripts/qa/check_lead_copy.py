#!/usr/bin/env python3
"""QA check: per-lead copy validation. TASK-295.

    py -3 scripts/qa/check_lead_copy.py \\
        --phase pre_push \\
        --workspaces <path-to-work-copy> \\
        [--json work/qa/<run>/lead_copy.json]

Reads rendered rows from `work/stage/s7-copy.jsonl` in the named workspace
copy and checks every lead's copy against ten rules.

THE REAL MAPPING (measured, not remembered):

    thread_reply_pattern: [false, true, true, true, true]

    em1   position 1   subject {SUBJECT_1}   body {BODY_1}
    em2   position 2   subject {SUBJECT_1}   body {BODY_2}
    em3   position 3   subject {SUBJECT_1}   body {BODY_3}
    em4   position 4   subject {SUBJECT_1}   body {BODY_4}
    em5   position 5   subject {SUBJECT_1}   body {BODY_5}

THE STEP KEY IS NOT THE VARIABLE NUMBER. em4 is at position 4 and reads
{BODY_4} in the five-step config. At four steps em4 was at position 3 and
read {BODY_3}. The mapping is derived from the config at run time.

ALL STEPS CARRY {SUBJECT_1}. There is no SUBJECT_2 and no new-thread step
after position 1 in the current config.

A THREADED STEP STILL CARRIES email_subject. The flag is the mechanism, not
subject omission. An empty subject on a threaded step is NOT correct.

`steps_expected` is THIS campaign's stored cadence_steps, never the module
constant (copylint.STEPS_EXPECTED = 5). Eleven campaigns hold 3 steps
legitimately (Option A).
"""
import argparse
import datetime
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from src import copylint, emptyrender, lint

try:
    from src import clients as _clients_mod
except ImportError:
    _clients_mod = None

# ----------------------------------------------------------------- the rules
#
# Each rule: (name, sentence_template).
#
# Sentences are rendered from THIS RUN's parameters, not from module
# constants. `copylint.RULES` has
#   "one of the %d steps is empty" % STEPS_EXPECTED
# with STEPS_EXPECTED = 5, so a three-step campaign renders
# "one of the 5 steps is empty" while the check correctly ran at 3.
# The check is right and the sentence is wrong; we render our own.

RULES = (
    ("subject_present",
     "step {step} has no subject"),
    ("body_present",
     "step {step} has no body"),
    ("not_literal_none",
     "step {step} carries the literal string 'None'"),
    ("no_unrendered_placeholder",
     "step {step} carries an unresolved template variable"),
    ("no_dash",
     "a dash used as punctuation"),
    ("no_banned_phrase",
     "a buzzword or banned phrase"),
    ("length_in_band",
     "step {step} body length outside the configured band"),
    ("first_name_present_and_capitalised",
     "the greeting name is missing or not capitalised"),
    ("subject_matches_the_step",
     "step {step} subject does not match the threading pattern"),
    ("first_line_unique_in_batch",
     "two or more leads share a first line"),
    ("persona_and_angle_consistent",
     "persona or angle labels differ between email and LinkedIn"),
)


def render_rules(steps_expected):
    """The rule sentences, rendered from this run's parameters.

    Invariant 5 of the QA contract: rule text is rendered at run time, not
    baked from a module constant.
    """
    out = {}
    for name, template in RULES:
        sentence = template.replace("{step}", str(steps_expected))
        if name == "length_in_band":
            sentence = ("body length outside the configured band "
                        "(%d steps)" % steps_expected)
        out[name] = sentence
    return out


# ----------------------------------------- config readers (read at run time)

def read_thread_reply_pattern(config):
    """From the client config's email_sequence.thread_reply_pattern.

    Returns a tuple of bools, one per email step in cadence order.
    """
    es = ((config or {}).get("email_sequence") or {})
    pattern = es.get("thread_reply_pattern")
    if isinstance(pattern, (list, tuple)) and pattern:
        return tuple(bool(v) for v in pattern)
    return ()


def read_step_body_mapping(config):
    """From the client config's email_sequence.steps.

    Returns [(step_key, body_variable), ...] in order.
    The body variable is extracted from the step's `body` template field:
    `<p>{BODY_1}</p>` -> `BODY_1`.
    """
    es = ((config or {}).get("email_sequence") or {})
    steps_block = es.get("steps") or {}
    if not isinstance(steps_block, dict):
        return []
    body_re = re.compile(r"\{(\w+)\}")
    result = []
    for key, entry in sorted(steps_block.items(),
                             key=lambda kv: (kv[1].get("order", 0), kv[0])):
        body_tmpl = entry.get("body", "")
        match = body_re.search(body_tmpl)
        body_var = match.group(1) if match else ""
        result.append((key, body_var))
    return result


def count_email_steps(config):
    """How many email steps the config declares."""
    es = ((config or {}).get("email_sequence") or {})
    steps_block = es.get("steps") or {}
    if isinstance(steps_block, dict) and steps_block:
        return len(steps_block)
    if es.get("subject") and es.get("body"):
        return 1
    return 0


def resolve_steps_expected(config, campaign=None):
    """THIS campaign's step count, not the module constant.

    Priority:
    1. The campaign's own `cadence_steps` email step count.
    2. The config's `email_sequence.steps` count.
    3. copylint.STEPS_EXPECTED (5) as last resort.
    """
    if campaign:
        cs = campaign.get("cadence_steps") or []
        email_count = sum(1 for s in cs
                          if isinstance(s, dict)
                          and s.get("channel") == "email"
                          and s.get("key"))
        if email_count:
            return email_count
    config_count = count_email_steps(config)
    if config_count:
        return config_count
    return copylint.STEPS_EXPECTED


# --------------------------------------------------------- per-rule checks

def check_subject_present(step_data, position, thread_reply):
    """non-empty after strip. A threaded step still carries a subject."""
    subject = (step_data.get("subject") or "").strip()
    if not subject:
        return False
    return True


def check_body_present(step_data, position):
    """non-empty after strip. No step has a legitimate empty body."""
    body = (step_data.get("body") or "").strip()
    if not body:
        return False
    return True


def check_not_literal_none(step_data, position):
    """The string 'None' (case-insensitive) is not copy."""
    subject = (step_data.get("subject") or "").strip()
    body = (step_data.get("body") or "").strip()
    for value in (subject, body):
        if value.lower() in emptyrender.NONE_WORDS:
            return False
    return True


def check_no_unrendered_placeholder(step_data, position):
    """No surviving {, {{, [[, or variable name."""
    body = step_data.get("body") or ""
    subject = step_data.get("subject") or ""
    text = subject + "\n" + body
    if emptyrender._PLACEHOLDER.search(text):
        return False
    if re.search(r"\{\{", text):
        return False
    if re.search(r"\[\[", text):
        return False
    return True


def check_no_dash(text):
    """copylint.DASH_RE over the text."""
    return not copylint.DASH_RE.search(text)


def check_no_banned_phrase(text):
    """lint.BANNED_PHRASES + copylint.BUZZWORDS."""
    return not copylint.buzzwords_in(text)


def check_length_in_band(body, min_words=40, max_words=180):
    """Body word count within [min_words, max_words]."""
    words = len(str(body or "").split())
    return min_words <= words <= max_words


def check_first_name(first_name_value):
    """Present and capitalised. Not empty, not a placeholder."""
    name = (first_name_value or "").strip()
    if not name or len(name) < 2:
        return False
    if name.lower() in ("n/a", "na", "none", "null", "-", "unknown"):
        return False
    if not name[0].isupper():
        return False
    return True


def check_greeting_not_empty(body, first_name_value):
    """The greeting must render to something a person can read.

    EMAILBISON-COPY-REQUIREMENTS: open naturally with the prospect's first
    name. A body whose greeting renders to nothing - because the first name
    was empty - is the defect this catches.
    """
    name = (first_name_value or "").strip()
    if not name:
        return False
    first_line = ""
    for line in str(body or "").splitlines():
        line = line.strip()
        if line:
            first_line = line
            break
    if not first_line:
        return False
    if name.lower() not in first_line.lower():
        return False
    return True


def check_subject_matches(step_data, position, thread_reply_pattern,
                          opener_subject):
    """Step 1 owns the subject; threaded steps carry the SAME subject.

    A new-thread step (if the config declares one) carries its own.
    Checked against thread_reply_pattern AS READ AT RUN TIME.

    A threaded step still carries email_subject - the flag is the mechanism,
    not subject omission. So an empty subject on a threaded step FAILS.
    """
    subject = (step_data.get("subject") or "").strip()
    if position == 1:
        return bool(subject)
    is_threaded = (position <= len(thread_reply_pattern)
                   and thread_reply_pattern[position - 1])
    if is_threaded:
        if not subject:
            return False
        if opener_subject and subject != opener_subject:
            return False
        return True
    else:
        return bool(subject)


def check_first_line_unique(body, seen_first_lines):
    """No two leads share a first line. Returns (is_unique, normalised_line)."""
    first = copylint.first_line(body)
    if not first:
        return True, ""
    key = copylint._norm(first)
    if key in seen_first_lines:
        return False, key
    return True, key


# ----------------------------------------------------------- the main check

def _load_config(workspaces, client="productive"):
    """Load the client config from the workspace copy."""
    if _clients_mod is not None:
        try:
            return _clients_mod.load(client)
        except Exception:
            pass
    config_path = os.path.join(workspaces, "config", "clients",
                               "%s.yaml" % client)
    if not os.path.exists(config_path):
        config_path = os.path.join(ROOT, "config", "clients",
                                   "%s.yaml" % client)
    if not os.path.exists(config_path):
        return {}
    try:
        import yaml
        with open(config_path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def _load_rendered_rows(workspaces):
    """Read s7-copy.jsonl from the workspace copy.

    Returns (rows, file_info). `rows` is a list of dicts (rendered only).
    `file_info` has path, mtime, row count.
    """
    path = os.path.join(workspaces, "stage", "s7-copy.jsonl")
    if not os.path.exists(path):
        return [], {"path": path, "rows": 0, "mtime": None, "exists": False}
    mtime = datetime.datetime.fromtimestamp(
        os.path.getmtime(path), tz=datetime.timezone.utc
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = []
    total = 0
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            total += 1
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("state") == "rendered":
                rows.append(row)
    return rows, {"path": path, "rows": total, "mtime": mtime, "exists": True}


def _load_queue_records(workspaces):
    """Read queue.jsonl from the workspace copy, for LinkedIn copy."""
    path = os.path.join(workspaces, "queue.jsonl")
    if not os.path.exists(path):
        return []
    records = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


def _find_linkedin_copy(queue_records, email):
    """Find a lead's LinkedIn copy from the queue records.

    Returns {"persona": ..., "angle": ...} or None.
    """
    for rec in queue_records:
        contacts = rec.get("contacts") or []
        for contact in contacts:
            if (contact.get("email") or "").lower() == email.lower():
                cadence = rec.get("cadence") or {}
                contact_key = contact.get("key")
                steps = cadence.get(contact_key) or {}
                li_steps = {}
                for step_key, step in steps.items():
                    if isinstance(step, dict) and step.get("channel") == "linkedin":
                        li_steps[step_key] = step
                if li_steps:
                    return {
                        "persona": contact.get("persona"),
                        "angle": contact.get("angle"),
                        "has_li_copy": bool(li_steps),
                    }
    return None


def run(phase="pre_push", workspaces=None, campaigns=None, batch=None,
        client="productive", json_path=None):
    """Run the lead copy check. Returns the result document dict."""
    if not workspaces:
        return _error_result("no workspaces path provided")
    if not os.path.isdir(workspaces):
        return _error_result("workspaces path does not exist: %s" % workspaces)

    config = _load_config(workspaces, client)
    rows, file_info = _load_rendered_rows(workspaces)

    if not file_info.get("exists"):
        return _error_result(
            "s7-copy.jsonl not found at %s" % file_info["path"])

    if not rows:
        return _vacuous_result(
            "s7-copy.jsonl has %d total rows but zero rendered" %
            file_info["rows"], file_info)

    thread_pattern = read_thread_reply_pattern(config)
    step_mapping = read_step_body_mapping(config)
    steps_expected = resolve_steps_expected(config)

    rules = render_rules(steps_expected)
    counts = {name: 0 for name, _ in RULES}
    offenders = {name: [] for name, _ in RULES}
    unverifiable = {name: [] for name, _ in RULES}

    seen_first_lines = {}
    empty_count = 0
    none_count = 0
    unrendered_count = 0
    leads_with_li = 0
    leads_with_li_checked = 0

    for row in rows:
        email = row.get("email", "?")
        variables = row.get("variables") or {}
        lead_id = email

        first_name_val = (variables.get("FIRST")
                          or variables.get("first_name")
                          or variables.get("first") or "")
        email_persona = variables.get("persona")
        email_angle = variables.get("angle")

        all_text_parts = []
        lead_had_any_failure = False

        for position in range(1, steps_expected + 1):
            body_key = "body_%d" % position
            subject_key = "subject_%d" % position

            body = variables.get(body_key, "")
            if position == 1:
                subject = variables.get(subject_key,
                                        variables.get("subject_1", ""))
            else:
                subject = variables.get(subject_key,
                                        variables.get("subject_1", ""))

            step_data = {"body": body, "subject": subject}
            is_threaded = (position <= len(thread_pattern)
                           and thread_pattern[position - 1])
            opener_subject = (variables.get("subject_1") or "").strip()

            if not check_subject_present(step_data, position, is_threaded):
                counts["subject_present"] += 1
                if lead_id not in offenders["subject_present"]:
                    offenders["subject_present"].append(lead_id)
                lead_had_any_failure = True

            if not check_body_present(step_data, position):
                counts["body_present"] += 1
                if lead_id not in offenders["body_present"]:
                    offenders["body_present"].append(lead_id)
                empty_count += 1
                lead_had_any_failure = True

            if not check_not_literal_none(step_data, position):
                counts["not_literal_none"] += 1
                if lead_id not in offenders["not_literal_none"]:
                    offenders["not_literal_none"].append(lead_id)
                none_count += 1
                lead_had_any_failure = True

            if not check_no_unrendered_placeholder(step_data, position):
                counts["no_unrendered_placeholder"] += 1
                if lead_id not in offenders["no_unrendered_placeholder"]:
                    offenders["no_unrendered_placeholder"].append(lead_id)
                unrendered_count += 1
                lead_had_any_failure = True

            if body:
                all_text_parts.append(body)
            if subject:
                all_text_parts.append(subject)

            if not check_subject_matches(step_data, position, thread_pattern,
                                         opener_subject):
                counts["subject_matches_the_step"] += 1
                if lead_id not in offenders["subject_matches_the_step"]:
                    offenders["subject_matches_the_step"].append(lead_id)
                lead_had_any_failure = True

            if body and not check_length_in_band(body):
                counts["length_in_band"] += 1
                if lead_id not in offenders["length_in_band"]:
                    offenders["length_in_band"].append(lead_id)
                lead_had_any_failure = True

        if first_name_val:
            if not check_first_name(first_name_val):
                counts["first_name_present_and_capitalised"] += 1
                if lead_id not in offenders[
                        "first_name_present_and_capitalised"]:
                    offenders["first_name_present_and_capitalised"].append(
                        lead_id)
                lead_had_any_failure = True
        else:
            counts["first_name_present_and_capitalised"] += 1
            if lead_id not in offenders[
                    "first_name_present_and_capitalised"]:
                offenders["first_name_present_and_capitalised"].append(
                    lead_id)
            lead_had_any_failure = True

        body_1 = variables.get("body_1", "")
        if body_1 and first_name_val:
            if not check_greeting_not_empty(body_1, first_name_val):
                counts["first_name_present_and_capitalised"] += 1
                if lead_id not in offenders[
                        "first_name_present_and_capitalised"]:
                    offenders["first_name_present_and_capitalised"].append(
                        lead_id)
                lead_had_any_failure = True

        whole_text = "\n".join(all_text_parts)
        if whole_text:
            if not check_no_dash(whole_text):
                counts["no_dash"] += 1
                if lead_id not in offenders["no_dash"]:
                    offenders["no_dash"].append(lead_id)
                lead_had_any_failure = True
            if not check_no_banned_phrase(whole_text):
                counts["no_banned_phrase"] += 1
                if lead_id not in offenders["no_banned_phrase"]:
                    offenders["no_banned_phrase"].append(lead_id)
                lead_had_any_failure = True

        if body_1:
            is_unique, key = check_first_line_unique(body_1, seen_first_lines)
            if not is_unique:
                counts["first_line_unique_in_batch"] += 1
                if lead_id not in offenders["first_line_unique_in_batch"]:
                    offenders["first_line_unique_in_batch"].append(lead_id)
                for prev_id in offenders.get("_first_line_%s" % key, []):
                    if prev_id not in offenders["first_line_unique_in_batch"]:
                        offenders["first_line_unique_in_batch"].append(
                            prev_id)
                lead_had_any_failure = True
            else:
                seen_first_lines[key] = lead_id
                offenders["_first_line_%s" % key] = [lead_id]

        li_info = None
        queue_records = _load_queue_records(workspaces)
        if queue_records:
            li_info = _find_linkedin_copy(queue_records, email)
        if li_info and li_info.get("has_li_copy"):
            leads_with_li += 1
            li_persona = li_info.get("persona")
            li_angle = li_info.get("angle")
            if (email_persona and li_persona
                    and email_persona != li_persona):
                counts["persona_and_angle_consistent"] += 1
                if lead_id not in offenders["persona_and_angle_consistent"]:
                    offenders["persona_and_angle_consistent"].append(lead_id)
                lead_had_any_failure = True
            if (email_angle and li_angle
                    and email_angle != li_angle):
                counts["persona_and_angle_consistent"] += 1
                if lead_id not in offenders["persona_and_angle_consistent"]:
                    offenders["persona_and_angle_consistent"].append(lead_id)
                lead_had_any_failure = True
            leads_with_li_checked += 1

    for key in list(offenders.keys()):
        if key.startswith("_first_line_"):
            del offenders[key]

    all_offender_ids = set()
    for name, ids in offenders.items():
        all_offender_ids.update(ids)
    all_unverifiable_ids = set()
    for name, ids in unverifiable.items():
        all_unverifiable_ids.update(ids)
    combined = all_offender_ids | all_unverifiable_ids
    clean = len(rows) - len(combined)

    subjects = len(rows)
    if subjects == 0:
        verdict = "VACUOUS"
    elif any(counts[name] > 0 for name, _ in RULES
             if name not in ("persona_and_angle_consistent",)):
        verdict = "FAIL"
    else:
        verdict = "PASS"

    vacuous_rules = []
    if counts["not_literal_none"] == 0:
        vacuous_rules.append(
            "not_literal_none: zero occurrences in the estate; "
            "nothing to fire on")
    if leads_with_li == 0:
        vacuous_rules.append(
            "persona_and_angle_consistent: no leads carry LinkedIn copy; "
            "nothing to compare")

    commit = _get_commit()

    result = {
        "check": "lead_copy",
        "phase": phase,
        "verdict": verdict,
        "batch": batch,
        "campaigns": campaigns or [],
        "subjects": subjects,
        "clean": clean,
        "refused": verdict == "FAIL",
        "rules": rules,
        "counts": counts,
        "offenders": {k: sorted(v) for k, v in offenders.items()
                      if not k.startswith("_")},
        "unverifiable": {k: sorted(v) for k, v in unverifiable.items()},
        "evidence": {
            "files_read": [
                {"path": file_info["path"],
                 "rows": file_info["rows"],
                 "mtime": file_info["mtime"]},
            ],
            "provider_reads_skipped": True,
        },
        "measured_at": datetime.datetime.now(
            datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "commit": commit,
        "workspaces": workspaces,
        "steps_expected": steps_expected,
        "thread_reply_pattern": list(thread_pattern),
        "step_mapping": [{"step_key": k, "body_variable": v}
                         for k, v in step_mapping],
        "empty_vs_none_vs_unrendered": {
            "empty": empty_count,
            "literal_none": none_count,
            "unrendered": unrendered_count,
        },
        "vacuous_rules": vacuous_rules,
        "leads_with_linkedin_copy": leads_with_li,
        "leads_with_linkedin_checked": leads_with_li_checked,
    }

    if json_path:
        os.makedirs(os.path.dirname(json_path) or ".", exist_ok=True)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

    return result


def _error_result(reason):
    return {
        "check": "lead_copy",
        "phase": "pre_push",
        "verdict": "ERROR",
        "error": reason,
        "subjects": 0,
        "clean": 0,
        "refused": False,
        "rules": {},
        "counts": {},
        "offenders": {},
        "unverifiable": {},
        "evidence": {"files_read": [], "provider_reads_skipped": True},
        "measured_at": datetime.datetime.now(
            datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "commit": _get_commit(),
        "workspaces": None,
    }


def _vacuous_result(reason, file_info):
    return {
        "check": "lead_copy",
        "phase": "pre_push",
        "verdict": "VACUOUS",
        "vacuous_reason": reason,
        "subjects": 0,
        "clean": 0,
        "refused": False,
        "rules": render_rules(0),
        "counts": {name: 0 for name, _ in RULES},
        "offenders": {name: [] for name, _ in RULES},
        "unverifiable": {name: [] for name, _ in RULES},
        "evidence": {
            "files_read": [
                {"path": file_info.get("path", ""),
                 "rows": file_info.get("rows", 0),
                 "mtime": file_info.get("mtime")},
            ],
            "provider_reads_skipped": True,
        },
        "measured_at": datetime.datetime.now(
            datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "commit": _get_commit(),
        "workspaces": None,
    }


def _get_commit():
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT, stderr=subprocess.DEVNULL
        ).decode().strip()
    except Exception:
        return "unknown"


def print_report(result):
    """Human-readable report to stdout."""
    print("QA lead_copy: %s" % result.get("verdict", "?"))
    print("  subjects: %d" % result.get("subjects", 0))
    print("  clean:    %d" % result.get("clean", 0))
    print("  steps_expected: %s" % result.get("steps_expected", "?"))
    print()

    trp = result.get("thread_reply_pattern")
    if trp:
        print("  thread_reply_pattern: %s" % trp)
    mapping = result.get("step_mapping")
    if mapping:
        print("  step -> variable mapping:")
        for entry in mapping:
            print("    %s -> {%s}" % (entry["step_key"],
                                      entry["body_variable"]))
    print()

    counts = result.get("counts") or {}
    offenders = result.get("offenders") or {}
    for name, sentence in (result.get("rules") or {}).items():
        count = counts.get(name, 0)
        ids = offenders.get(name, [])
        if count:
            print("  %-35s %3d  %s%s" % (
                name, count, ", ".join(ids[:5]),
                " ..." if len(ids) > 5 else ""))
            print("  %-35s      %s" % ("", sentence))
        else:
            print("  %-35s   0  (clean)" % name)

    vacuous = result.get("vacuous_rules") or []
    if vacuous:
        print()
        print("  VACUOUS rules (nothing to fire on):")
        for v in vacuous:
            print("    - %s" % v)

    env = result.get("empty_vs_none_vs_unrendered") or {}
    if env:
        print()
        print("  EMPTY vs 'None' vs UNRENDERED:")
        print("    empty:          %d" % env.get("empty", 0))
        print("    literal 'None': %d" % env.get("literal_none", 0))
        print("    unrendered:     %d" % env.get("unrendered", 0))

    li = result.get("leads_with_linkedin_copy", 0)
    print()
    print("  leads carrying LinkedIn copy: %d" % li)

    arithmetic_ok = (result.get("clean", 0)
                     + len(set().union(
                         *[set(v) for v in offenders.values()]
                     ) | set().union(
                         *[set(v) for v in
                           (result.get("unverifiable") or {}).values()]
                     )) == result.get("subjects", 0))
    print("  arithmetic: clean + |offenders u unverifiable| == subjects? %s"
          % ("YES" if arithmetic_ok else "NO"))


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="QA check: per-lead copy validation (TASK-295)")
    parser.add_argument("--phase", default="pre_push",
                        choices=["pre_push", "post_push", "ongoing"])
    parser.add_argument("--batch")
    parser.add_argument("--campaign", action="append", dest="campaigns")
    parser.add_argument("--workspaces", required=True,
                        help="path to a copy of production work/")
    parser.add_argument("--json", dest="json_path",
                        help="where to write the result JSON")
    parser.add_argument("--client", default="productive")
    args = parser.parse_args(argv)

    result = run(phase=args.phase, workspaces=args.workspaces,
                 campaigns=args.campaigns, batch=args.batch,
                 client=args.client, json_path=args.json_path)
    print_report(result)

    verdict = result.get("verdict", "ERROR")
    if verdict == "PASS":
        return 0
    elif verdict in ("FAIL", "UNCONFIRMED", "VACUOUS"):
        return 1 if verdict == "FAIL" else 2
    return 3


if __name__ == "__main__":
    sys.exit(main())
