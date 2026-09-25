#!/usr/bin/env python3
"""Verify S7's render carries every variable the provider sequence needs.

    py -3 scripts/verify_s7_render.py --copy work/stage/s7-copy.jsonl
    py -3 scripts/verify_s7_render.py --copy work/stage/s7-copy.jsonl.bak

READS ONLY. Opens a named copy of the S7 journal, reads the client config,
builds the provider sequence through `bisonfactory._sequence_steps`, and
checks that every variable the sequence references is present, non-empty,
not the literal 'None', and carries no unrendered placeholder on every row.

TASK-283. Written 2026-09-25.

## WHAT THIS PROVES

1. The cadence's step keys and the provider sequence's variable keys agree,
   diffed as SETS in BOTH directions. One direction is how a half-applied
   change reads as complete.
2. Every row in the journal carries every variable the sequence needs.
3. Empty, the literal 'None', and unrendered `{` are THREE SEPARATE counts.
4. The threading invariant holds: `thread_reply_pattern` has the right
   length and the right values, read from the config at run time.
5. The final step's `wait_in_days` is 1, never 0.

## WHAT THIS DELIBERATELY DOES NOT PROVE

The approval gate's other conditions - verification, suppression, collision,
fatigue - are not exercised. They need `work/` state this script does not
read. A row counted good here is good ON ITS COPY.
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import bisonfactory, cadence, clients  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: Values that are "empty" to a human and not to `if value`. The morning
#: handoff warned about the literal `'None'`; 2026-09-24 measured the live
#: variables as EMPTY instead. Both are checked, because the blank gate
#: refuses both and checking only the one that bit last time is how the other
#: one gets through.
BLANKISH = {"", "none", "null", "nan", "n/a", "-"}

_PLACEHOLDER = re.compile(r"\{[A-Z_0-9]+\}")


def load_rows(path):
    """Read a JSONL journal into a list of dicts."""
    rows = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def rendered_rows(rows):
    """Rows whose state is 'rendered', keyed by lowercase email."""
    return {r["email"].lower(): r for r in rows if r.get("state") == "rendered"}


def cadence_keys(sequence):
    """The step keys the provider sequence carries, in order."""
    return tuple(s.get("step_key") for s in sequence if s.get("step_key"))


def variable_keys_from_sequence(sequence):
    """The variable names the sequence templates reference, as a set.

    Extracted from `{SUBJECT_N}` and `{BODY_N}` placeholders in each step's
    `email_subject` and `email_body`. Lowercased to match the journal's
    variable names.
    """
    names = set()
    for step in sequence:
        for field in (step.get("email_subject", ""), step.get("email_body", "")):
            for match in re.findall(r"\{([A-Z_0-9]+)\}", field or ""):
                names.add(match.lower())
    return names


def variable_keys_from_cadence(cadence_steps):
    """The variable names the cadence's email steps produce, as a set.

    The journal names variables by step key suffix: `em3` -> `body_3`.
    `subject_1` is the only subject variable (all follow-ups are thread
    replies carrying SUBJECT_1).
    """
    names = {"subject_1"}
    for step in cadence_steps:
        if step.get("channel") != "email":
            continue
        suffix = str(step["key"])[2:]
        names.add(f"body_{suffix}")
    return names


def diff_sets(cadence_vars, sequence_vars):
    """Both directions of the set diff, named.

    Returns (in_cadence_not_sequence, in_sequence_not_cadence).
    """
    return (sorted(cadence_vars - sequence_vars),
            sorted(sequence_vars - cadence_vars))


def classify_value(value):
    """Why this value is not sendable, or None if it is fine.

    Returns one of: 'empty', 'literal_none', 'unrendered', or None.
    Three separate faults, three separate causes.
    """
    if value is None:
        return "empty"
    raw = str(value).strip()
    if not raw:
        return "empty"
    if raw.lower() in BLANKISH:
        if raw.lower() == "none":
            return "literal_none"
        return "empty"
    if _PLACEHOLDER.search(raw):
        return "unrendered"
    return None


def check_rows(rows_by_email, sequence, cadence_steps):
    """Check every rendered row against every variable the sequence needs.

    Returns a dict of {variable_name: {fault_type: count}} plus a list of
    example emails per fault.
    """
    seq_vars = variable_keys_from_sequence(sequence)
    report = {}
    examples = {}

    for var in sorted(seq_vars):
        report[var] = {"present": 0, "empty": 0, "literal_none": 0,
                       "unrendered": 0}
        examples[var] = {}

    for email, row in rows_by_email.items():
        values = row.get("variables", {})
        for var in sorted(seq_vars):
            value = values.get(var)
            fault = classify_value(value)
            if fault is None:
                report[var]["present"] += 1
            else:
                report[var][fault] += 1
                examples[var].setdefault(fault, email)

    return report, examples


def check_threading(sequence, configured):
    """Assert the threading invariant from the config at run time.

    Returns (pattern, faults). `faults` is a list of strings describing
    what is wrong; empty means the invariant holds.
    """
    pattern = configured.get("thread_reply_pattern")
    faults = []

    if not isinstance(pattern, (list, tuple)):
        faults.append(
            "thread_reply_pattern is absent or not a list. "
            "The config must declare it explicitly.")
        return (), faults

    n_steps = len(sequence)
    n_pattern = len(pattern)

    if n_pattern != n_steps:
        faults.append(
            f"thread_reply_pattern has {n_pattern} entries but the sequence "
            f"has {n_steps} steps. The pattern must have one entry per step. "
            f"A three-entry pattern on a four-or-five-step sequence is the "
            f"pre-change value and means the threading was not updated when "
            f"the cadence lengthened.")
        return tuple(pattern), faults

    if n_pattern > 0 and pattern[0] is not False:
        faults.append(
            "thread_reply_pattern[0] is not false. The opener must not be "
            "a thread reply; only the opener owns a subject.")

    for i in range(1, n_pattern):
        if pattern[i] is not True:
            faults.append(
                f"thread_reply_pattern[{i}] is not true. Every follow-up "
                f"must be a thread reply carrying SUBJECT_1.")

    return tuple(pattern), faults


def check_final_wait(sequence):
    """The final step's wait_in_days must be 1, never 0.

    Campaign 485 was left at 0 steps by exactly that. Returns (wait, fault).
    """
    if not sequence:
        return None, "no sequence steps to check"
    last = sequence[-1]
    wait = last.get("wait_in_days")
    if wait is None:
        return None, f"step {last.get('step_key')!r} declares no wait_in_days"
    if int(wait) == 0:
        return int(wait), (
            f"the final step ({last.get('step_key')!r}) has wait_in_days=0. "
            f"Campaign 485 was left at 0 steps by exactly that. The final "
            f"step's wait is inert (nothing follows it) but the provider "
            f"refuses 0.")
    return int(wait), None


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__.split("\n")[0])
    parser.add_argument("--copy", required=True,
                        help="path to the S7 journal copy to verify")
    parser.add_argument("--client", default="productive",
                        help="client config name (default: productive)")
    args = parser.parse_args(argv)

    if not os.path.exists(args.copy):
        print(f"ERROR: {args.copy} does not exist", file=sys.stderr)
        return 2

    copy_mtime = os.path.getmtime(args.copy)
    rows = load_rows(args.copy)
    rendered = rendered_rows(rows)

    print(f"VERIFY S7 RENDER  (TASK-283)")
    print(f"=" * 60)
    print(f"Journal   {args.copy}")
    print(f"mtime     {copy_mtime}")
    print(f"Rows      {len(rows)} total, {len(rendered)} rendered")
    print()

    # --- Load config and build the sequence ---
    config = clients.load(args.client)
    email_seq = config.get("email_sequence", {})
    cadence_steps = cadence.steps_for(config=config)
    email_cadence = [s for s in cadence_steps if s.get("channel") == "email"]

    try:
        sequence = bisonfactory._sequence_steps(email_seq, cadence_steps)
    except Exception as exc:
        print(f"FATAL: bisonfactory._sequence_steps refused: {exc}",
              file=sys.stderr)
        return 2

    print(f"SEQUENCE  {len(sequence)} steps")
    for s in sequence:
        print(f"  {s.get('step_key'):>4}  pos {s['order']}  "
              f"thread_reply={s.get('thread_reply')}  "
              f"subject={s.get('email_subject')}  "
              f"wait={s.get('wait_in_days')}")
    print()

    # --- 1. Set diff: cadence vars vs sequence vars ---
    cadence_vars = variable_keys_from_cadence(cadence_steps)
    seq_vars = variable_keys_from_sequence(sequence)
    in_cadence, in_seq = diff_sets(cadence_vars, seq_vars)

    print(f"SET DIFF  cadence vars vs sequence vars (both directions)")
    print(f"  cadence vars:    {sorted(cadence_vars)}")
    print(f"  sequence vars:   {sorted(seq_vars)}")
    if in_cadence:
        print(f"  IN CADENCE NOT SEQUENCE: {in_cadence}")
    else:
        print(f"  IN CADENCE NOT SEQUENCE: (none)")
    if in_seq:
        print(f"  IN SEQUENCE NOT CADENCE: {in_seq}")
    else:
        print(f"  IN SEQUENCE NOT CADENCE: (none)")
    print()

    # --- 2. Threading invariant ---
    pattern, thread_faults = check_threading(sequence, email_seq)
    print(f"THREADING thread_reply_pattern as read at run time: {list(pattern)}")
    if thread_faults:
        for fault in thread_faults:
            print(f"  FAIL: {fault}")
    else:
        print(f"  PASS  {len(pattern)} entries, opener=false, "
              f"follow-ups=true")
    print()

    # --- 3. Final step wait ---
    wait, wait_fault = check_final_wait(sequence)
    print(f"FINAL WAIT  wait_in_days = {wait}")
    if wait_fault:
        print(f"  FAIL: {wait_fault}")
    else:
        print(f"  PASS")
    print()

    # --- 4. Per-variable table ---
    report, examples = check_rows(rendered, sequence, cadence_steps)
    print(f"PER-VARIABLE TABLE  over {len(rendered)} rendered rows")
    print(f"  {'variable':<14} {'present':>8} {'empty':>8} "
          f"{'None':>8} {'unrend':>8}")
    any_fault = False
    for var in sorted(report):
        r = report[var]
        faults = r["empty"] + r["literal_none"] + r["unrendered"]
        if faults:
            any_fault = True
        print(f"  {var:<14} {r['present']:>8} {r['empty']:>8} "
              f"{r['literal_none']:>8} {r['unrendered']:>8}")
    print()

    if any_fault:
        print(f"FAULT EXAMPLES")
        for var in sorted(examples):
            for fault_type, email in sorted(examples[var].items()):
                print(f"  {var} {fault_type}: e.g. {email}")
        print()

    # --- 5. Exit ---
    has_set_diff = bool(in_cadence or in_seq)
    has_thread_fault = bool(thread_faults)
    has_wait_fault = bool(wait_fault)

    if has_set_diff or has_thread_fault or has_wait_fault or any_fault:
        reasons = []
        if has_set_diff:
            reasons.append("set diff non-empty")
        if has_thread_fault:
            reasons.append("threading invariant violated")
        if has_wait_fault:
            reasons.append("final wait_in_days is 0")
        if any_fault:
            reasons.append("rows with empty/None/unrendered variables")
        print(f"FAIL  {', '.join(reasons)}")
        return 1

    print(f"PASS  all {len(rendered)} rows carry every variable, "
          f"threading holds, final wait is {wait}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
