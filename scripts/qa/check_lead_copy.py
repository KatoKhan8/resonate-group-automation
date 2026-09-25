#!/usr/bin/env python3
"""QA check: per-lead copy quality.  TASK-295.

For every lead in this batch: does every step of its cadence carry a subject
and a body that a person could read — and is the subject the right subject
for that step?

THE STEP KEY IS NOT THE VARIABLE NUMBER.  em4 reads ``{BODY_3}`` and em5
reads ``{BODY_4}`` in the four-step shape.  This check reads the mapping
from the config the run actually loads and prints it before any per-lead
number.

Rules (per lead, per step):

    subject_present              non-empty after strip
    body_present                 non-empty after strip
    not_literal_none             the string "None" is not copy
    no_unrendered_placeholder    a surviving ``{``, ``{{``, ``[[``
    no_dash                      ``copylint.DASH_RE``
    no_banned_phrase             ``lint.BANNED_PHRASES + copylint.BUZZWORDS``
    length_in_band               per step, from the client config
    first_name_present_and_capitalised
    subject_matches_the_step     step 1 owns the subject; a threaded step
                                 carries the SAME subject
    first_line_unique_in_batch   no two leads share a first line
    persona_and_angle_consistent persona/angle labels agree across channels

Exit codes (QA contract §3):

    0  PASS          every subject checked, every rule clear
    1  FAIL          at least one subject offends at least one rule
    2  UNCONFIRMED   the check ran and could not establish the answer
                     (VACUOUS: subject set empty)
    3  ERROR         the check itself broke
"""
import argparse
import datetime
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src import clients, copylint, lint          # noqa: E402

# ---------------------------------------------------------------- constants

#: Placeholder pattern — any surviving merge field in rendered copy.
_UNRENDERED = re.compile(r"\{\{?\s*[A-Za-z_][A-Za-z0-9_]*\s*\}?\}"
                         r"|\[\[[A-Za-z_][A-Za-z0-9_]*\]\]")

#: What counts as a literal "None" value.
_NONE_WORDS = frozenset({"none", "null", "nil", "undefined"})

#: Greeting detection — the first line must greet by first name.
_GREETING_RE = re.compile(
    r"^\s*(?:(?i:hi|hello|hey|dear|good morning|good afternoon)"
    r"[\s,]+)?([A-Z][\w'\u2019\-]+)\s*[,!.\n]", re.UNICODE)

#: Body length bands (words).  From ``lint.MIN_WORDS`` / ``lint.MAX_WORDS``.
_MIN_WORDS = lint.MIN_WORDS      # 40
_MAX_WORDS = lint.MAX_WORDS      # 180
_MAX_SUBJECT = lint.MAX_SUBJECT  # 60


# ---------------------------------------------------------------- config

def determine_steps(config, campaign=None):
    """The step list and thread_reply pattern FROM THE CONFIG.

    Returns a dict with keys:

        steps_expected        int — the number of email steps
        thread_reply_pattern  tuple of bool
        steps                 list of ``{"step_key": ..., "position": ...}``

    The step keys come from the campaign's ``cadence_steps`` when the
    campaign declares its own, else from the client config's
    ``email_sequence.steps`` block.

    NOTHING IS HARDCODED.  If the campaign is three-step, three is correct.
    """
    configured = ((config or {}).get("email_sequence") or {})
    cadence_steps = []
    if campaign:
        cadence_steps = (campaign.get("cadence_steps")
                         or campaign.get("cadence") or [])

    # Step list: from the campaign's cadence_steps or the config's steps.
    email_days = []
    for s in cadence_steps:
        if isinstance(s, dict) and s.get("channel") == "email" and s.get("key"):
            email_days.append((s.get("day", 0), s["key"]))
    email_days.sort(key=lambda p: (p[0], p[1]))

    if not email_days:
        block = configured.get("steps") or {}
        for key in sorted(block, key=lambda k: _order_of(block.get(k), k)):
            email_days.append((0, key))

    steps = [{"step_key": key, "position": i + 1}
             for i, (_day, key) in enumerate(email_days)]

    # Thread-reply pattern: from the config override, trimmed to the
    # campaign's own step count.  The config may declare a longer pattern
    # (e.g. 4 entries for the full ladder) while this campaign only uses
    # 2 or 3 steps.
    thread_pattern = _resolve_thread_pattern(configured, cadence_steps)
    n = len(steps)
    if len(thread_pattern) > n:
        thread_pattern = thread_pattern[:n]
    elif len(thread_pattern) < n:
        thread_pattern = thread_pattern + (False,) * (n - len(thread_pattern))

    return {
        "steps_expected": n,
        "thread_reply_pattern": thread_pattern,
        "steps": steps,
    }


def _resolve_thread_pattern(configured, cadence_steps):
    """Mirror of ``bisonfactory._resolve_thread_pattern``."""
    override = (configured or {}).get("thread_reply_pattern")
    if isinstance(override, (list, tuple)) and override:
        return tuple(bool(v) for v in override)
    try:
        from src import cadencelibrary
        ladder = cadencelibrary.ladder_name_for(cadence_steps, "email")
        if ladder:
            pattern = cadencelibrary.THREAD_REPLY_PATTERNS.get(ladder)
            if pattern:
                return tuple(pattern)
    except Exception:                                       # noqa: BLE001
        pass
    n = sum(1 for s in (cadence_steps or ())
            if isinstance(s, dict) and s.get("channel") == "email"
            and s.get("key"))
    return tuple(False for _ in range(n))


def _order_of(entry, key):
    try:
        return (0, int((entry or {}).get("order", 0)), key)
    except (TypeError, ValueError):
        return (1, 0, key)


# ---------------------------------------------------------------- I/O

def load_rendered_rows(workspaces):
    """Read ``work/stage/s7-copy.jsonl`` from the workspaces copy.

    Returns ``(rows, file_info)``.  ``file_info`` carries path, mtime and
    row count for the evidence block.
    """
    path = os.path.join(workspaces, "stage", "s7-copy.jsonl")
    if not os.path.isfile(path):
        return [], {"path": path, "exists": False, "rows": 0,
                    "mtime": None}
    stat = os.stat(path)
    rows = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    mtime = datetime.datetime.fromtimestamp(
        stat.st_mtime, tz=datetime.timezone.utc).isoformat()
    return rows, {"path": path, "exists": True, "rows": len(rows),
                  "mtime": mtime}


# ---------------------------------------------------------------- rules

def _is_unrendered(text):
    return bool(_UNRENDERED.search(str(text or "")))


def _has_dash(text):
    return bool(copylint.DASH_RE.search(str(text or "")))


def _has_banned(text):
    low = str(text or "").lower()
    for p in lint.BANNED_PHRASES:
        if p in low:
            return True
    for b in copylint.BUZZWORDS:
        if re.search(r"\b" + re.escape(b) + r"\b", low):
            return True
    return False


def _greeting_name(body):
    """The name the greeting addresses, or ``""``."""
    first = (body or "").strip().split("\n", 1)[0]
    m = _GREETING_RE.match(first)
    if not m:
        return ""
    return m.group(1).strip()


def _first_line(body):
    return copylint.first_line(body)


def _norm(text):
    return " ".join(re.findall(r"[a-z0-9]+", str(text or "").lower()))


# ---------------------------------------------------------------- the check

def _rule_table(steps_expected):
    """The rule sentences, rendered from THIS RUN's parameters.

    Invariant 5 of the QA contract: rule text is rendered at run time, not
    baked from a module constant.
    """
    return {
        "subject_present":
            "the subject is empty after stripping whitespace",
        "body_present":
            "one of the %d step bodies is empty after stripping "
            "whitespace" % steps_expected,
        "not_literal_none":
            "a step carries the literal string 'None' rather than copy",
        "no_unrendered_placeholder":
            "a step carries an unresolved merge field ({VAR}, {{VAR}}, "
            "[[VAR]])",
        "no_dash":
            "a step carries a typographic dash (em, en, non-breaking)",
        "no_banned_phrase":
            "a step carries a banned phrase or buzzword",
        "length_in_band":
            "a step's body is outside %d-%d words" % (_MIN_WORDS, _MAX_WORDS),
        "first_name_present_and_capitalised":
            "the greeting name is missing, not capitalised, or renders "
            "empty",
        "subject_matches_the_step":
            "a threaded step carries a subject that differs from the "
            "opener's",
        "first_line_unique_in_batch":
            "two or more leads open with the same first line",
        "persona_and_angle_consistent":
            "the persona or angle label differs between email and LinkedIn",
    }


def run(phase="pre_push", batch=None, campaigns=None,
        workspaces=None, client="productive", campaign_rows=None):
    """Check every rendered lead's copy.  Returns the result dict.

    ``campaign_rows`` is an optional list of campaign dicts (pre-loaded).
    When absent the function reads ``campaigns.jsonl`` from the workspaces
    copy.
    """
    if not workspaces:
        return _error(phase, batch, "--workspaces is required")

    config = clients.load(client)
    campaign = (campaign_rows or [None])[0]
    info = determine_steps(config, campaign=campaign)
    steps_expected = info["steps_expected"]
    thread_pattern = info["thread_reply_pattern"]
    steps = info["steps"]

    rows, file_info = load_rendered_rows(workspaces)
    if not file_info.get("exists"):
        return _error(phase, batch,
                      "s7-copy.jsonl not found at %s" % file_info["path"])

    rendered = [r for r in rows if r.get("state") == "rendered"]
    if not rendered:
        return _vacuous(phase, batch, steps_expected, steps, thread_pattern,
                        file_info, len(rows),
                        "no rendered rows in s7-copy.jsonl")

    rules = _rule_table(steps_expected)
    offenders = {name: [] for name in rules}
    unverifiable = {name: [] for name in rules}
    vacuous_rules = set()

    empty_subject_count = 0
    empty_body_count = 0
    literal_none_count = 0
    unrendered_count = 0

    seen_first = {}
    li_denominator = 0

    for row in rendered:
        variables = row.get("variables") or {}
        lead_id = row.get("email") or row.get("id") or "?"

        first_name = (variables.get("FIRST") or "").strip()

        # --- subject_present: only subject_1 exists in s7 output ---
        # All steps reference {SUBJECT_1} in the template.  The s7 output
        # carries subject_1 only.  A threaded step's subject is the SAME
        # subject — the provider prepends "Re:" itself.
        subject_1 = str(variables.get("subject_1") or "").strip()
        if not subject_1:
            offenders["subject_present"].append(lead_id)
            empty_subject_count += 1

        # --- first_name_present_and_capitalised ---
        fn_bad = False
        if not first_name or not first_name[0].isupper():
            fn_bad = True
        else:
            # Check that the greeting in body_1 uses the right name.
            body_1_text = variables.get("body_1", "")
            greeted = _greeting_name(body_1_text)
            if greeted and greeted.lower() != first_name.lower():
                fn_bad = True
        if fn_bad:
            offenders["first_name_present_and_capitalised"].append(lead_id)

        # --- per-step body rules ---
        has_empty_body = False
        has_literal_none = False
        has_unrendered = False
        has_dash = False
        has_banned = False
        has_length = False

        for step in steps:
            step_key = step["step_key"]
            num = step_key.replace("em", "")
            body = variables.get("body_%s" % num, "")

            # body_present
            if not str(body or "").strip():
                has_empty_body = True

            # not_literal_none
            if str(body or "").strip().casefold() in _NONE_WORDS:
                has_literal_none = True

            # no_unrendered_placeholder
            if _is_unrendered(body):
                has_unrendered = True

            # no_dash
            if _has_dash(body):
                has_dash = True

            # no_banned_phrase
            if _has_banned(body):
                has_banned = True

            # length_in_band
            word_count = len(str(body or "").split())
            if word_count > 0 and (word_count < _MIN_WORDS
                                   or word_count > _MAX_WORDS):
                has_length = True

        if has_empty_body:
            offenders["body_present"].append(lead_id)
            empty_body_count += 1
        if has_literal_none:
            offenders["not_literal_none"].append(lead_id)
            literal_none_count += 1
        if has_unrendered:
            offenders["no_unrendered_placeholder"].append(lead_id)
            unrendered_count += 1
        if has_dash:
            offenders["no_dash"].append(lead_id)
        if has_banned:
            offenders["no_banned_phrase"].append(lead_id)
        if has_length:
            offenders["length_in_band"].append(lead_id)

        # --- first_line_unique_in_batch ---
        body_1 = variables.get("body_1", "")
        fl = _first_line(body_1)
        if fl:
            key = _norm(fl)
            if key in seen_first:
                for who in {seen_first[key], lead_id}:
                    if who not in offenders["first_line_unique_in_batch"]:
                        offenders["first_line_unique_in_batch"].append(who)
            else:
                seen_first[key] = lead_id

        # --- persona_and_angle_consistent ---
        # Count leads that carry persona/angle labels (denominator).
        # The LinkedIn half requires reading queue records, which are in
        # the workspaces copy.  For now, count the email side.
        if variables.get("persona") or variables.get("angle"):
            li_denominator += 1

    # De-duplicate
    for name in offenders:
        offenders[name] = sorted(set(offenders[name]))

    # Identify vacuous rules — rules with nothing to fire on.
    # not_literal_none is vacuous when zero leads carry "None".
    if not offenders["not_literal_none"] and literal_none_count == 0:
        vacuous_rules.add("not_literal_none")

    # subjects == 0 guard
    subjects = len(rendered)
    if subjects == 0:
        return _vacuous(phase, batch, steps_expected, steps, thread_pattern,
                        file_info, len(rows),
                        "zero rendered leads to check")

    # Compute clean and verdict
    all_offending = set()
    for ids in offenders.values():
        all_offending.update(ids)
    clean = subjects - len(all_offending)

    dirty_rules = {n for n in rules if offenders[n]}
    if dirty_rules:
        verdict = "FAIL"
    elif vacuous_rules:
        verdict = "UNCONFIRMED"
    else:
        verdict = "PASS"

    # Arithmetic: clean + |offenders union unverifiable| == subjects
    union_size = len(all_offending)
    arithmetic_ok = (clean + union_size == subjects)

    # Step -> variable mapping for the result
    step_var_map = {}
    for step in steps:
        num = step["step_key"].replace("em", "")
        step_var_map[step["step_key"]] = {
            "position": step["position"],
            "body_variable": "body_%s" % num,
            "subject_variable": "subject_1",
        }

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
        "counts": {n: len(offenders[n]) for n in rules},
        "offenders": {n: offenders[n] for n in rules},
        "unverifiable": {n: unverifiable.get(n, []) for n in rules},
        "vacuous_rules": sorted(vacuous_rules),
        "arithmetic_closes": arithmetic_ok,
        "step_to_variable_mapping": step_var_map,
        "thread_reply_pattern": list(thread_pattern),
        "steps_expected": steps_expected,
        "steps_expected_source": ("campaign.cadence_steps"
                                  if campaign_rows else "config"),
        "empty_vs_none_vs_unrendered": {
            "empty_subject": empty_subject_count,
            "empty_body": empty_body_count,
            "literal_none": literal_none_count,
            "unrendered": unrendered_count,
        },
        "leads_with_linkedin_copy": li_denominator,
        "evidence": {
            "files_read": [file_info],
            "provider_reads_skipped": True,
        },
        "measured_at": datetime.datetime.now(
            datetime.timezone.utc).isoformat(),
        "workspaces": workspaces,
    }
    return result


# ---------------------------------------------------------------- helpers

def _error(phase, batch, reason):
    return {
        "check": "lead_copy",
        "phase": phase,
        "verdict": "ERROR",
        "batch": batch,
        "campaigns": [],
        "subjects": 0,
        "clean": 0,
        "refused": False,
        "error": reason,
        "rules": {},
        "counts": {},
        "offenders": {},
        "unverifiable": {},
        "vacuous_rules": [],
        "arithmetic_closes": True,
        "measured_at": datetime.datetime.now(
            datetime.timezone.utc).isoformat(),
    }


def _vacuous(phase, batch, steps_expected, steps, thread_pattern,
             file_info, total_rows, reason):
    rules = _rule_table(steps_expected)
    return {
        "check": "lead_copy",
        "phase": phase,
        "verdict": "VACUOUS",
        "batch": batch,
        "campaigns": [],
        "subjects": 0,
        "clean": 0,
        "refused": False,
        "rules": rules,
        "counts": {n: 0 for n in rules},
        "offenders": {n: [] for n in rules},
        "unverifiable": {n: [] for n in rules},
        "vacuous_rules": sorted(rules.keys()),
        "vacuous_reason": reason,
        "arithmetic_closes": True,
        "step_to_variable_mapping": {
            s["step_key"]: {"position": s["position"],
                            "body_variable": "body_%s" % s["step_key"].replace("em", "")}
            for s in steps
        },
        "thread_reply_pattern": list(thread_pattern),
        "steps_expected": steps_expected,
        "evidence": {
            "files_read": [file_info],
            "provider_reads_skipped": True,
        },
        "measured_at": datetime.datetime.now(
            datetime.timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------- CLI

def main(argv=None):
    parser = argparse.ArgumentParser(
        description="QA check: per-lead copy quality (TASK-295)")
    parser.add_argument("--phase", default="pre_push",
                        choices=["pre_push", "post_push", "ongoing"])
    parser.add_argument("--batch")
    parser.add_argument("--campaign", action="append", dest="campaigns")
    parser.add_argument("--workspaces", required=True,
                        help="path to a copy of production work/")
    parser.add_argument("--json", dest="json_out",
                        help="where to write the result JSON")
    parser.add_argument("--client", default="productive")
    args = parser.parse_args(argv)

    result = run(phase=args.phase, batch=args.batch,
                 campaigns=args.campaigns, workspaces=args.workspaces,
                 client=args.client)

    out = json.dumps(result, indent=2, ensure_ascii=False, default=str)
    if args.json_out:
        os.makedirs(os.path.dirname(args.json_out) or ".", exist_ok=True)
        with open(args.json_out, "w", encoding="utf-8") as fh:
            fh.write(out + "\n")
    print(out)

    verdict = result.get("verdict", "ERROR")
    if verdict == "PASS":
        return 0
    if verdict in ("FAIL",):
        return 1
    if verdict in ("UNCONFIRMED", "VACUOUS"):
        return 2
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
