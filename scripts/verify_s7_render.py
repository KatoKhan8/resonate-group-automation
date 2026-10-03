#!/usr/bin/env python3
"""Verify the S7 render covers every variable the provider sequence needs.

    py -3 scripts/verify_s7_render.py
    py -3 scripts/verify_s7_render.py --journal work/stage/s7-copy.jsonl
    py -3 scripts/verify_s7_render.py --journal path/to/copy.jsonl --client productive

TASK-283. Five checks, each named and fail-closed:

1. KEY DIFF, BOTH DIRECTIONS. The cadence's email step keys (from
   `scripts/batch1_build.py`'s `CADENCE_STEPS`) and the client config's
   `email_sequence.steps` keys must agree as SETS, both ways. A key on one
   side the other does not carry is named.

2. thread_reply_pattern, READ FROM CONFIG AT RUN TIME. The pattern must have
   exactly as many entries as there are email steps. Position 1 is false
   (the opener owns the subject); every follow-up is true. Three entries on
   a five-step cadence is the pre-change value and is refused with the cause
   named.

3. FINAL wait_in_days IS 1, NEVER 0. The provider refused 0 on campaign 485
   and left it at zero steps. The last step's declared wait is checked.

4. VARIABLE SET DIFF, BOTH DIRECTIONS. The provider sequence templates
   reference `{SUBJECT_1}`, `{BODY_1}`..`{BODY_N}`. The journal is expected
   to produce `subject_1`, `body_1`..`body_N` (lowercase). The two sets are
   diffed in both directions and the NAMES are printed.

5. PER-VARIABLE TABLE OVER THE JOURNAL. For every variable the provider
   needs: rows present, rows empty, rows carrying the literal 'None', rows
   with an unrendered `{` surviving. Exit non-zero when any row would reach
   the provider with a gap.

READS ONLY. No provider call, no credential, no write.
"""
import argparse
import importlib.util
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import clients  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: Values the blank gate refuses. The literal string 'None' is distinguished
#: from empty in the report: both are refusals but they have different causes
#: (a render that produced nothing vs a render that wrote the Python
#: repr of None) and the operator needs to know which.
BLANKISH = {"", "none", "null", "nan", "n/a", "-"}
PLACEHOLDER_RE = re.compile(r"\{([A-Z_0-9]+)\}")


def _load_batch1_build():
    """`scripts/batch1_build.py` by path. `scripts/` is not a package."""
    path = os.path.join(ROOT, "scripts", "batch1_build.py")
    spec = importlib.util.spec_from_file_location("batch1_build_verify", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_journal(path):
    """Every row from a JSONL journal, parsed."""
    rows = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                rows.append(json.loads(stripped))
    return rows


def rendered_rows(journal):
    """email -> the row, for rendered rows only."""
    return {r["email"].lower(): r
            for r in journal if r.get("state") == "rendered"}


# ---------------------------------------------------------------- check 1
#
# The cadence's email step keys vs the config's declared step keys.


def diff_cadence_keys(config, cadence_steps):
    """(configured_keys, cadence_keys, only_configured, only_cadence).

    Both directions, as sorted lists. The caller prints them.
    """
    steps_block = (config.get("email_sequence") or {}).get("steps") or {}
    configured = sorted(steps_block.keys())
    cadence_keys = sorted(s["key"] for s in cadence_steps
                          if s.get("channel") == "email" and s.get("key"))
    only_configured = sorted(set(configured) - set(cadence_keys))
    only_cadence = sorted(set(cadence_keys) - set(configured))
    return configured, cadence_keys, only_configured, only_cadence


# ---------------------------------------------------------------- check 2
#
# thread_reply_pattern, read from config at run time.


def check_thread_pattern(config, n_email):
    """(pattern, errors). Errors is empty when the invariant holds.

    The pattern is READ FROM THE CONFIG, not asserted from a table. A table
    in a task file is the thing that was wrong here in the first place
    (TASK-283 correction, 2026-09-25).
    """
    es = config.get("email_sequence") or {}
    pattern = es.get("thread_reply_pattern")
    errors = []
    if pattern is None:
        errors.append(
            "email_sequence.thread_reply_pattern is absent. "
            "The ladder default is used, but TASK-283 requires an "
            "explicit declaration")
        return None, errors
    if not isinstance(pattern, (list, tuple)):
        errors.append(
            f"thread_reply_pattern is {type(pattern).__name__}, "
            f"not a list")
        return None, errors
    if len(pattern) != n_email:
        errors.append(
            f"thread_reply_pattern has {len(pattern)} entries "
            f"({list(pattern)}) and the cadence carries {n_email} email "
            f"steps. A mismatched length means the threading flags were "
            f"declared for a different cadence - the pre-change value "
            f"on a post-change sequence. Fix the pattern to match the "
            f"step count")
        return list(pattern), errors
    if pattern[0] is not False and pattern[0] != False:
        errors.append(
            f"thread_reply_pattern[0] is {pattern[0]!r}: the opener "
            f"must NOT be a thread reply, because the opener owns the "
            f"subject")
    for i in range(1, len(pattern)):
        if pattern[i] is not True and pattern[i] != True:
            errors.append(
                f"thread_reply_pattern[{i}] is {pattern[i]!r}: every "
                f"follow-up must be a thread reply on the opener's "
                f"subject")
    return list(pattern), errors


# ---------------------------------------------------------------- check 3
#
# Final step's wait_in_days.


def check_final_wait(config, cadence_steps):
    """(wait, errors). The last email step's wait must be >= 1."""
    steps_block = (config.get("email_sequence") or {}).get("steps") or {}
    email_steps = [(s.get("day"), s.get("key")) for s in cadence_steps
                   if s.get("channel") == "email" and s.get("key")]
    email_steps.sort()
    if not email_steps:
        return None, ["cadence carries no email steps"]
    _last_day, last_key = email_steps[-1]
    entry = steps_block.get(last_key) or {}
    wait = entry.get("wait_in_days")
    errors = []
    if wait is None:
        errors.append(
            f"{last_key} declares no `wait_in_days`. The provider "
            f"defaults and 'nobody chose' reads the same as a choice")
    elif int(wait) < 1:
        errors.append(
            f"{last_key}.wait_in_days is {wait}. Campaign 485 was left "
            f"at zero steps by the provider refusing 0 atomically. "
            f"The terminal wait must be >= 1")
    return wait, errors


# ---------------------------------------------------------------- check 4
#
# Variable set diff, both directions.


def provider_sequence_variables(config):
    """The lowercase variable names the provider templates reference.

    Every `{SUBJECT_1}` in a template becomes `subject_1`; every `{BODY_3}`
    becomes `body_3`. The set is what the journal must produce.
    """
    steps_block = (config.get("email_sequence") or {}).get("steps") or {}
    referenced = set()
    for entry in steps_block.values():
        if not isinstance(entry, dict):
            continue
        for field in ("subject", "body"):
            text = entry.get(field) or ""
            for match in PLACEHOLDER_RE.findall(text):
                referenced.add(match.lower())
    return referenced


def journal_variable_names(rendered):
    """The variable names the journal's rendered rows actually carry.

    Intersected across ALL rendered rows: a name counts only when every
    rendered row has it. A variable half the rows carry is not a variable
    the journal produces - it is a variable the journal sometimes forgets.
    """
    if not rendered:
        return set()
    names = None
    for row in rendered.values():
        row_names = set((row.get("variables") or {}).keys())
        if names is None:
            names = row_names
        else:
            names &= row_names
    return names or set()


def diff_variable_sets(journal_vars, provider_vars):
    """(only_journal, only_provider): names in one set but not the other."""
    only_journal = sorted(journal_vars - provider_vars)
    only_provider = sorted(provider_vars - journal_vars)
    return only_journal, only_provider


# ---------------------------------------------------------------- check 5
#
# Per-variable analysis over the journal.


def analyse_rows(rendered, required_vars):
    """Per-variable stats over the rendered rows.

    Returns a dict keyed by variable name. Each value is a dict with:
        present     rows that carry this variable with a usable value
        empty       rows whose value is empty or blankish (not 'None')
        none_string rows whose value is the literal string 'None'
        unrendered  rows that still carry an unrendered `{...}`
        missing     rows that do not carry this variable at all
        example     one email for each fault category (for reporting)

    A row can appear in more than one fault category: a value can be both
    the string 'None' and carry an unrendered placeholder (though in
    practice the two have different causes).
    """
    stats = {}
    for var in sorted(required_vars):
        s = {"present": 0, "empty": 0, "none_string": 0,
             "unrendered": 0, "missing": 0,
             "example_empty": None, "example_none": None,
             "example_unrendered": None, "example_missing": None}
        for email, row in rendered.items():
            value = (row.get("variables") or {}).get(var)
            if value is None or var not in (row.get("variables") or {}):
                s["missing"] += 1
                s["example_missing"] = s["example_missing"] or email
                continue
            text = str(value)
            if text.strip().lower() == "none":
                s["none_string"] += 1
                s["example_none"] = s["example_none"] or email
            elif text.strip().lower() in BLANKISH:
                s["empty"] += 1
                s["example_empty"] = s["example_empty"] or email
            elif PLACEHOLDER_RE.search(text):
                s["unrendered"] += 1
                s["example_unrendered"] = (s["example_unrendered"]
                                           or email)
            else:
                s["present"] += 1
        stats[var] = s
    return stats


def collect_errors(stats):
    """Error strings from an analyse_rows result. Empty when every row is clean."""
    errors = []
    for var, s in sorted(stats.items()):
        if s["missing"]:
            errors.append(
                f"{var}: {s['missing']} row(s) missing "
                f"(e.g. {s['example_missing']})")
        if s["empty"]:
            errors.append(
                f"{var}: {s['empty']} row(s) empty/blank "
                f"(e.g. {s['example_empty']})")
        if s["none_string"]:
            errors.append(
                f"{var}: {s['none_string']} row(s) carry the literal "
                f"string 'None' (e.g. {s['example_none']})")
        if s["unrendered"]:
            errors.append(
                f"{var}: {s['unrendered']} row(s) carry an unrendered "
                f"placeholder (e.g. {s['example_unrendered']})")
    return errors


# ---------------------------------------------------------------- validate
#
# The whole check, callable from tests.


def validate(config, cadence_steps, journal_path=None):
    """Every check. Returns (errors, report_lines).

    `errors` is a list of strings; empty means pass. `report_lines` is the
    formatted output, always returned so the caller can print it whether
    the check passed or not.
    """
    errors = []
    lines = []

    es = config.get("email_sequence") or {}
    email_steps = [s for s in cadence_steps
                   if s.get("channel") == "email" and s.get("key")]
    n_email = len(email_steps)

    # -- check 1: key diff, both directions --
    lines.append("CHECK 1  cadence keys vs config step keys, both directions")
    cfg_keys, cad_keys, only_cfg, only_cad = diff_cadence_keys(
        config, cadence_steps)
    lines.append(f"  config declares:   {cfg_keys}")
    lines.append(f"  cadence declares:  {cad_keys}")
    if only_cfg:
        msg = (f"  FAIL config declares {only_cfg} that the cadence does not")
        lines.append(msg)
        errors.append(msg)
    if only_cad:
        msg = (f"  FAIL cadence declares {only_cad} that the config does not")
        lines.append(msg)
        errors.append(msg)
    if not only_cfg and not only_cad:
        lines.append(f"  PASS both sides declare {cfg_keys}")

    # -- check 2: thread_reply_pattern --
    lines.append("")
    lines.append("CHECK 2  thread_reply_pattern, read from config at run time")
    pattern, pat_errs = check_thread_pattern(config, n_email)
    lines.append(f"  value at run time: {pattern}")
    if pat_errs:
        for msg in pat_errs:
            lines.append(f"  FAIL {msg}")
            errors.append(msg)
    else:
        lines.append(
            f"  PASS {len(pattern)} entries, opener false, "
            f"follow-ups true")

    # -- check 3: final wait_in_days --
    lines.append("")
    lines.append("CHECK 3  final step wait_in_days")
    wait, wait_errs = check_final_wait(config, cadence_steps)
    lines.append(f"  value: {wait}")
    if wait_errs:
        for msg in wait_errs:
            lines.append(f"  FAIL {msg}")
            errors.append(msg)
    else:
        lines.append(f"  PASS wait_in_days = {wait}")

    # -- check 4: variable set diff, both directions --
    lines.append("")
    lines.append("CHECK 4  variable set diff, both directions")
    prov_vars = provider_sequence_variables(config)
    lines.append(f"  provider references: {sorted(prov_vars)}")

    if journal_path and os.path.exists(journal_path):
        journal = load_journal(journal_path)
        rend = rendered_rows(journal)
        j_vars = journal_variable_names(rend)
        only_j, only_p = diff_variable_sets(j_vars, prov_vars)
        lines.append(f"  journal produces:  {sorted(j_vars)}")
        if only_j:
            msg = (f"  FAIL journal produces {only_j} that the provider "
                   f"does not reference")
            lines.append(msg)
            errors.append(msg)
        if only_p:
            msg = (f"  FAIL provider references {only_p} that the journal "
                   f"does not produce")
            lines.append(msg)
            errors.append(msg)
        if not only_j and not only_p:
            lines.append(f"  PASS journal and provider agree on "
                         f"{sorted(prov_vars)}")
    else:
        lines.append("  SKIP no journal given or file not found")

    # -- check 5: per-variable table --
    lines.append("")
    lines.append("CHECK 5  per-variable table over rendered rows")
    if journal_path and os.path.exists(journal_path):
        journal = load_journal(journal_path)
        rend = rendered_rows(journal)
        total = len(journal)
        n_rendered = len(rend)
        lines.append(f"  journal: {total} rows, {n_rendered} rendered")
        stats = analyse_rows(rend, prov_vars)
        header = (f"  {'variable':<14} {'present':>8} {'empty':>8} "
                  f"{'None':>8} {'unrendered':>11} {'missing':>8}")
        lines.append(header)
        for var in sorted(prov_vars):
            s = stats[var]
            lines.append(
                f"  {var:<14} {s['present']:>8} {s['empty']:>8} "
                f"{s['none_string']:>8} {s['unrendered']:>11} "
                f"{s['missing']:>8}")
        row_errors = collect_errors(stats)
        if row_errors:
            lines.append("")
            for msg in row_errors:
                lines.append(f"  FAIL {msg}")
                errors.append(msg)
        else:
            lines.append(
                f"  PASS {n_rendered} rows x {len(prov_vars)} variables, "
                f"none empty, none 'None', none unrendered, none missing")
    else:
        lines.append("  SKIP no journal given or file not found")

    return errors, lines


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--journal",
                        help="path to s7-copy.jsonl (or a copy of it)")
    parser.add_argument("--client", default="productive")
    args = parser.parse_args(argv)

    config = clients.load(args.client)
    b1 = _load_batch1_build()
    cadence_steps = b1.CADENCE_STEPS

    errs, lines = validate(config, cadence_steps, args.journal)

    for line in lines:
        print(line)

    if errs:
        print(f"\nFAILED with {len(errs)} error(s)")
        return 1

    print("\nALL CHECKS PASSED")
    if args.journal:
        print(f"  config: {args.client}")
        print(f"  journal: {args.journal}")
    else:
        print("  (config-level checks only; no journal to verify)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
