#!/usr/bin/env python3
"""TASK 0077 section 1 / control C3: enumerate consumers of the floor fields.

Two sweeps over a stated denominator, printed as file:line hits:

  FIELD sweep   - every literal read of `already_spent`, `already_spent_is`,
                  `unpriced_calls`, `expected_floor`, `unpriced_rows`.
  CALLER sweep  - every caller of the builders/formatters that produce or
                  format the spend summary, so a consumer that formats the
                  number without naming the field is still counted.

Denominator: *.py files under <root>/src, <root>/scripts and <root>/tests,
minus any `providers` directory (the operator's read prohibition - those are
classified by execution, as the TASK 0077 probe did for the Slack formatter).

Stated blind spots, not hidden ones:
  - only *.py: a .ps1, a notebook or a shell pipeline is invisible.
  - only src/, scripts/, tests/: any other top-level directory is invisible.
  - only literal spellings: `d["already_spent" + "_is"]` is invisible.
  - src/providers is not walked at all.

Exit prints a one-line count so an empty result cannot masquerade as a
scanned result (control C4's concern).
"""
import os
import sys

FIELDS = ("already_spent", "already_spent_is", "unpriced_calls",
          "expected_floor", "unpriced_rows")

CALLERS = ("spendledger.report(", "costs.report(", "costs.reconcile(",
           "_credit_estimate(", "slack_preview(", "reporting_preview(",
           "waterfall.spend(", "cost_estimate(", "campaign_approval_request(")


def walk(root):
    """(class, path) for every *.py under the walked tops, providers skipped."""
    found = []
    for label, top in (("src", "src"), ("scripts", "scripts"),
                       ("tests", "tests")):
        base = os.path.join(root, top)
        if not os.path.isdir(base):
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = sorted(d for d in dirnames if d != "providers")
            for name in sorted(filenames):
                if name.endswith(".py"):
                    found.append((label, os.path.join(dirpath, name)))
    return found


def hits_in(path):
    with open(path, "rb") as handle:
        text = handle.read().decode("utf-8", "replace")
    out = []
    for number, line in enumerate(text.splitlines(), 1):
        for needle in FIELDS:
            if needle in line:
                out.append((number, "FIELD", needle, line.strip()))
        for needle in CALLERS:
            if needle in line:
                out.append((number, "CALLER", needle, line.strip()))
    return out


def main(root):
    files = walk(root)
    total = 0
    for label, path in files:
        rows = hits_in(path)
        if not rows:
            continue
        print(f"[{label}] {os.path.relpath(path, root)}")
        for number, kind, needle, line in rows:
            shown = line if len(line) <= 100 else line[:97] + "..."
            print(f"    {number:>4} {kind:<6} {needle:<26} {shown}")
        total += len(rows)
    print(f"scanned {len(files)} *.py files under src/ scripts/ tests/ "
          f"(providers/ excluded); {total} hits.")
    if not files:
        print("NOTHING WAS SCANNED - an empty report from this tool means a "
              "wrong root, not an empty estate.")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ".")
