#!/usr/bin/env python3
"""Verify S7's render covers every variable the provider sequence will ask for.

Reads the client config's cadence and email_sequence, diffs the step keys as
sets in both directions, then walks every row of an s7-copy journal and
reports per-variable coverage: present, empty, literal 'None', and
unrendered placeholder.

Exits non-zero when any row would reach the provider with a gap.

    py -3 scripts/verify_s7_render.py --copy work/stage/s7-copy.jsonl
    py -3 scripts/verify_s7_render.py --copy work/stage/s7-copy.jsonl --client productive

NOT AUTHORIZED to change the cadence, the config, or the builder. Defects
found in those files are reported, not patched.
"""
import argparse
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import cadence as cadence_mod
from src import clients
from src import sequenceplan

PLACEHOLDER_RE = re.compile(r"\{[A-Za-z_][A-Za-z0-9_]*\}")
VARIABLE_REF_RE = re.compile(r"\{([A-Z_][A-Z0-9_]*)\}")


def load_config(client_name):
    """The client config, loaded through the same path the builder uses."""
    return clients.load(client_name)


def get_cadence_email_steps(config):
    """The cadence's email step keys, in cadence order."""
    steps = cadence_mod.steps_for(config=config)
    return [s for s in steps
            if isinstance(s, dict) and s.get("channel") == "email"
            and s.get("key")]


def get_sequence_step_keys(config):
    """The keys declared in email_sequence.steps, sorted by order."""
    es = (config.get("email_sequence") or {})
    block = es.get("steps") or {}
    if not isinstance(block, dict) or not block:
        return []
    return sorted(block, key=lambda k: (block[k] or {}).get("order", 0))


def diff_key_sets(cadence_keys, sequence_keys):
    """Both directions of the set diff, named.

    Returns ``(in_cadence_not_seq, in_seq_not_cadence)`` as sorted lists.
    A count is not a diff: {em1, em2, em3, em4} and {em1, em2, em4, em5}
    have the same length but differ in two positions.
    """
    c_set = set(cadence_keys)
    s_set = set(sequence_keys)
    return (sorted(c_set - s_set), sorted(s_set - c_set))


def extract_sequence_variables(config):
    """Every {VARIABLE} the email_sequence templates reference, as a set."""
    es = (config.get("email_sequence") or {})
    block = es.get("steps") or {}
    variables = set()
    for key, entry in block.items():
        if not isinstance(entry, dict):
            continue
        for field in ("subject", "body"):
            text = entry.get(field) or ""
            variables.update(VARIABLE_REF_RE.findall(text))
    return variables


def get_thread_reply_pattern(config):
    """The thread_reply_pattern from the config's email_sequence block."""
    es = (config.get("email_sequence") or {})
    pattern = es.get("thread_reply_pattern")
    if isinstance(pattern, (list, tuple)):
        return [bool(v) for v in pattern]
    return None


def get_sequence_waits(config):
    """The wait_in_days for each sequence step, in order."""
    es = (config.get("email_sequence") or {})
    block = es.get("steps") or {}
    if not isinstance(block, dict) or not block:
        return []
    ordered = sorted(block.items(),
                     key=lambda kv: (kv[1] or {}).get("order", 0))
    return [(k, (v or {}).get("wait_in_days")) for k, v in ordered]


def check_thread_pattern(pattern, n_email_steps):
    """Whether the pattern covers the cadence. ``(ok, message)``."""
    if pattern is None:
        return False, ("no thread_reply_pattern in email_sequence config; "
                       "the builder cannot determine which steps are thread "
                       "replies")
    if len(pattern) != n_email_steps:
        return False, (
            f"thread_reply_pattern has {len(pattern)} entries "
            f"({pattern}) but the cadence declares {n_email_steps} email "
            f"steps. A three-entry pattern is the pre-change value; the "
            f"cadence was lengthened and the pattern was not updated to "
            f"match. bisonfactory would refuse this silently")
    expected_first = False
    if pattern[0] != expected_first:
        return False, (f"thread_reply_pattern[0] is {pattern[0]}, should be "
                       f"False: the opener owns the subject")
    return True, f"thread_reply_pattern = {pattern} ({len(pattern)} entries, matches cadence)"


def check_journal_row(variables, expected_vars):
    """Check one rendered row. Returns a list of problems (empty = clean).

    Each problem is ``(variable, category)`` where category is one of
    ``'empty'``, ``'None_literal'``, ``'unrendered'``.
    """
    problems = []
    for var in sorted(expected_vars):
        lower = var.lower()
        value = variables.get(lower)
        if value is None:
            problems.append((var, "missing"))
        elif str(value).strip() == "":
            problems.append((var, "empty"))
        elif str(value).strip() == "None":
            problems.append((var, "None_literal"))
        elif PLACEHOLDER_RE.search(str(value)):
            problems.append((var, "unrendered"))
    return problems


def check_final_wait(config):
    """The final step's wait_in_days. ``(value, ok, message)``."""
    waits = get_sequence_waits(config)
    if not waits:
        return None, False, "no sequence steps declared"
    last_key, last_wait = waits[-1]
    if last_wait is None:
        return None, False, (f"{last_key} declares no wait_in_days; "
                             f"the builder refuses on this")
    wait_int = int(last_wait)
    if wait_int == 0:
        return wait_int, False, (
            f"{last_key} has wait_in_days=0. Campaign 485 was left at 0 "
            f"steps by exactly this: the provider rejected the sequence. "
            f"Set to 1")
    return wait_int, True, f"{last_key} wait_in_days={wait_int}"


def read_journal(path):
    """Read an s7-copy journal. Returns ``(rendered_rows, held_rows)``."""
    rendered, held = [], []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if row.get("state") == "rendered":
                rendered.append(row)
            else:
                held.append(row)
    return rendered, held


def verify(copy_path, client_name="productive"):
    """Run all checks. Returns ``(exit_code, report_lines)``."""
    lines = []
    fatal = []

    config = load_config(client_name)
    lines.append(f"Config loaded: {client_name}")
    lines.append(f"Journal: {copy_path}")
    lines.append("")

    email_steps = get_cadence_email_steps(config)
    cadence_keys = [s["key"] for s in email_steps]
    lines.append(f"Cadence email steps ({len(cadence_keys)}): {cadence_keys}")

    seq_keys = get_sequence_step_keys(config)
    lines.append(f"Sequence step keys  ({len(seq_keys)}): {seq_keys}")

    in_cadence_not_seq, in_seq_not_cadence = diff_key_sets(cadence_keys,
                                                           seq_keys)
    lines.append("")
    lines.append("--- set diff (both directions) ---")
    if in_cadence_not_seq:
        lines.append(f"  in cadence, NOT in sequence: {in_cadence_not_seq}")
        fatal.append(f"cadence declares {in_cadence_not_seq} but the "
                     f"sequence does not carry them")
    else:
        lines.append("  in cadence, NOT in sequence: (none)")
    if in_seq_not_cadence:
        lines.append(f"  in sequence, NOT in cadence: {in_seq_not_cadence}")
        fatal.append(f"sequence declares {in_seq_not_cadence} but the "
                     f"cadence does not carry them")
    else:
        lines.append("  in sequence, NOT in cadence: (none)")

    seq_vars = extract_sequence_variables(config)
    lines.append("")
    lines.append(f"Sequence template variables: {sorted(seq_vars)}")

    pattern = get_thread_reply_pattern(config)
    lines.append("")
    lines.append("--- threading invariant ---")
    tr_ok, tr_msg = check_thread_pattern(pattern, len(cadence_keys))
    lines.append(f"  {tr_msg}")
    if not tr_ok:
        fatal.append(tr_msg)

    lines.append("")
    lines.append("--- final step wait_in_days ---")
    wait_val, wait_ok, wait_msg = check_final_wait(config)
    lines.append(f"  {wait_msg}")
    if not wait_ok:
        fatal.append(wait_msg)

    lines.append("")
    lines.append("--- journal check ---")
    if not os.path.exists(copy_path):
        lines.append(f"  JOURNAL NOT FOUND: {copy_path}")
        lines.append("  Cannot verify per-variable coverage without the "
                     "rendered journal")
        fatal.append("journal not found")
        return (1 if fatal else 0), lines

    rendered, held = read_journal(copy_path)
    total = len(rendered) + len(held)
    lines.append(f"  Total rows: {total}")
    lines.append(f"  Rendered:   {len(rendered)}")
    lines.append(f"  Held:       {len(held)}")
    lines.append("")

    expected_vars = seq_vars
    counts = {v: {"present": 0, "empty": 0, "none_literal": 0,
                   "unrendered": 0, "missing": 0}
              for v in expected_vars}
    bad_rows = []

    for row in rendered:
        variables = row.get("variables") or {}
        problems = check_journal_row(variables, expected_vars)
        if problems:
            bad_rows.append((row.get("email", "?"), problems))
        for var in expected_vars:
            lower = var.lower()
            value = variables.get(lower)
            if value is None:
                counts[var]["missing"] += 1
            elif str(value).strip() == "":
                counts[var]["empty"] += 1
            elif str(value).strip() == "None":
                counts[var]["none_literal"] += 1
            elif PLACEHOLDER_RE.search(str(value)):
                counts[var]["unrendered"] += 1
            else:
                counts[var]["present"] += 1

    lines.append(f"  Per-variable table (over {len(rendered)} rendered rows):")
    lines.append(f"  {'variable'.ljust(14)} {'present':>8} {'empty':>8} "
                 f"{'None':>8} {'unrendered':>11} {'missing':>8}")
    for var in sorted(expected_vars):
        c = counts[var]
        lines.append(f"  {var.ljust(14)} {c['present']:>8} {c['empty']:>8} "
                     f"{c['none_literal']:>8} {c['unrendered']:>11} "
                     f"{c['missing']:>8}")

    if bad_rows:
        lines.append("")
        lines.append(f"  ROWS WITH PROBLEMS ({len(bad_rows)}):")
        for email, problems in bad_rows[:20]:
            detail = ", ".join(f"{v}={c}" for v, c in problems)
            lines.append(f"    {email}: {detail}")
        if len(bad_rows) > 20:
            lines.append(f"    ... and {len(bad_rows) - 20} more")
        fatal.append(f"{len(bad_rows)} row(s) would reach the provider "
                     f"with an empty or unrendered variable")
    else:
        if rendered:
            lines.append("")
            lines.append("  All rendered rows carry every variable clean.")

    if held:
        held_reasons = {}
        for row in held:
            reason = row.get("reason", "unknown")
            held_reasons[reason] = held_reasons.get(reason, 0) + 1
        lines.append("")
        lines.append(f"  Held rows by reason:")
        for reason, count in sorted(held_reasons.items(),
                                    key=lambda kv: -kv[1]):
            lines.append(f"    {reason[:68].ljust(68)} {count:>5}")

    lines.append("")
    if fatal:
        lines.append(f"FAILED ({len(fatal)} issue(s)):")
        for issue in fatal:
            lines.append(f"  - {issue}")
    else:
        lines.append("PASSED: all checks clean")

    return (1 if fatal else 0), lines


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--copy", required=True,
                        help="Path to the s7-copy.jsonl (or a copy of it)")
    parser.add_argument("--client", default="productive",
                        help="Client config name (default: productive)")
    args = parser.parse_args(argv)

    exit_code, report = verify(args.copy, args.client)
    for line in report:
        print(line)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
