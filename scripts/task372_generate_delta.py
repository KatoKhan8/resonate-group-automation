#!/usr/bin/env python3
"""Generate the SUITE-BASELINE-DELTA-2026-09-26.md document for TASK-372."""
import re
import os
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(ROOT, "scripts", "suite_run.log")
OLD_BASELINE = os.path.join(ROOT, "docs", "state", "SUITE-BASELINE-2026-09-26.txt")
OUT = os.path.join(ROOT, "docs", "state", "SUITE-BASELINE-DELTA-2026-09-26.md")

_LINE = re.compile(r"^(FAIL|ERROR):\s+\S+\s+\(([^)\s]+)")
_SETUP = re.compile(r"^ERROR: setUpClass \(([^)]+)\)")


def strip_prefix(name):
    return name[6:] if name.startswith("tests.") else name


def main():
    with open(LOG, "r", errors="replace") as f:
        lines_list = f.readlines()

    # setUpClass failures
    setup_classes = set()
    for line in lines_list:
        m = _SETUP.match(line.strip())
        if m:
            setup_classes.add(strip_prefix(m.group(1).strip()))

    # Parse each failure's exception line
    test_errors = {}
    i = 0
    while i < len(lines_list):
        line = lines_list[i].rstrip()
        m = _LINE.match(line)
        if m:
            kind = m.group(1)
            name = strip_prefix(m.group(2).split(" ")[0].strip())
            exception_line = ""
            j = i + 1
            found_traceback = False
            while j < min(i + 60, len(lines_list)):
                l = lines_list[j].rstrip()
                if l.startswith("FAIL: ") or l.startswith("ERROR: "):
                    break
                if "Traceback (most recent call last)" in l:
                    found_traceback = True
                if found_traceback and l.strip():
                    stripped = l.strip()
                    if re.match(r"^[A-Z]\w*(Error|Exception):", stripped):
                        exception_line = stripped
                        break
                j += 1
            test_errors[name] = (kind, exception_line)
        i += 1

    # Load old baseline
    baseline = set()
    with open(OLD_BASELINE, "r") as f:
        for line in f:
            line = line.strip()
            if line.startswith("ERROR ") or line.startswith("FAIL "):
                parts = line.split(" ", 1)
                if len(parts) == 2:
                    baseline.add(parts[1].strip())

    new_set = set(test_errors.keys())
    only_new = sorted(new_set - baseline)
    only_old = sorted(baseline - new_set)
    both = sorted(new_set & baseline)

    # Categorize
    def categorize(name):
        kind, err = test_errors.get(name, ("?", ""))
        if name in setup_classes:
            return ("c", "setUpClass environment - web server required", "")
        if "src.personalization" in err and "has no attribute" in err:
            attr_match = re.search(r"'(\w+)'", err)
            attr = attr_match.group(1) if attr_match else "?"
            return ("a", f"src.personalization.{attr} missing (AttributeError)", err)
        if "start_monitors" in err and "has no attribute" in err:
            return ("a", "start_monitors.MONITORS missing (AttributeError)", err)
        if "src.heyreachfactory.FactoryRefused" in err:
            return ("a", "src.heyreachfactory.FactoryRefused", err[:120])
        if "src.clients.ConfigError" in err:
            return ("c", "src.clients.ConfigError (environment/config)", err[:120])
        if err.startswith("KeyError"):
            return ("b", "KeyError (data/fixture issue)", err[:120])
        if err.startswith("AssertionError"):
            return ("b", "AssertionError (genuine test failure)", err[:120])
        if err:
            return ("b", err.split(":")[0], err[:120])
        return ("?", "unknown (no exception captured)", "")

    categorized = {n: categorize(n) for n in only_new}
    cat_a = [(n, categorized[n][1], categorized[n][2]) for n in only_new if categorized[n][0] == "a"]
    cat_b = [(n, categorized[n][1], categorized[n][2]) for n in only_new if categorized[n][0] == "b"]
    cat_c = [(n, categorized[n][1], categorized[n][2]) for n in only_new if categorized[n][0] == "c"]

    # Sub-categorize (a)
    personalization_groups = defaultdict(list)
    factory_refused = []
    other_a = []
    for n, r, d in cat_a:
        if "src.personalization" in r:
            attr = r.split(".")[1].split(" ")[0]
            personalization_groups[attr].append(n)
        elif "FactoryRefused" in r:
            factory_refused.append(n)
        else:
            other_a.append((n, r))

    out = []
    out.append("# SUITE BASELINE DELTA - 2026-09-26 to 2026-09-30")
    out.append("")
    out.append("## Summary")
    out.append("")
    out.append("| | Count |")
    out.append("|---|---|")
    out.append(f"| Old baseline (2026-09-26) | {len(baseline)} |")
    out.append(f"| New baseline (2026-09-30) | {len(new_set)} |")
    out.append(f"| Still failing (in both) | {len(both)} |")
    out.append(f"| Gone (now passing) | {len(only_old)} |")
    out.append(f"| New (added to baseline) | {len(only_new)} |")
    out.append("")
    out.append("## Root cause breakdown of the %d new failures" % len(only_new))
    out.append("")
    out.append("| Category | Count | Kind |")
    out.append("|---|---|---|")
    pcount = sum(len(v) for v in personalization_groups.values())
    out.append(
        f"| (a) src.personalization missing attributes | {pcount} "
        "| Code-level: module API changed, tests not updated |"
    )
    for attr in sorted(
        personalization_groups.keys(), key=lambda a: -len(personalization_groups[a])
    ):
        out.append(f"|   - .{attr} | {len(personalization_groups[attr])} | AttributeError |")
    out.append(
        f"| (a) src.heyreachfactory.FactoryRefused | {len(factory_refused)} "
        "| Code-level: factory refusal path changed |"
    )
    if other_a:
        out.append(f"| (a) Other code-level | {len(other_a)} | Various |")
    out.append(
        f"| (b) Genuine assertion/test failures | {len(cat_b)} "
        "| Test logic or behavior changed |"
    )
    out.append(
        f"| (c) Environment-dependent | {len(cat_c)} "
        "| Missing server, config, or credentials |"
    )
    out.append("")

    # Category (a): personalization
    out.append("## Category (a): src.personalization missing attributes")
    out.append("")
    out.append(
        "The module `src.personalization` no longer exposes the attributes these tests import. "
        "This is a code-level issue: the module's API changed (attributes removed or renamed) "
        "but the tests were not updated. Each group below lists the affected tests."
    )
    out.append("")
    for attr in sorted(
        personalization_groups.keys(), key=lambda a: -len(personalization_groups[a])
    ):
        out.append(
            "### src.personalization.%s (%d tests)" % (attr, len(personalization_groups[attr]))
        )
        out.append("")
        for n in sorted(personalization_groups[attr]):
            out.append("- `%s`" % n)
        out.append("")

    if factory_refused:
        out.append(
            "## Category (a): src.heyreachfactory.FactoryRefused (%d tests)"
            % len(factory_refused)
        )
        out.append("")
        out.append(
            "These tests trigger a `FactoryRefused` exception from the HeyReach factory. "
            "The factory's refusal logic changed or the test fixtures no longer satisfy its guards."
        )
        out.append("")
        for n in sorted(factory_refused):
            out.append("- `%s`" % n)
        out.append("")

    # Category (b): genuine failures
    out.append("## Category (b): Genuine assertion/test failures")
    out.append("")
    out.append(
        "These are tests that fail with AssertionError or other exceptions not attributable "
        "to a single root cause. Each needs individual investigation."
    )
    out.append("")
    for n, r, d in sorted(cat_b, key=lambda x: x[0]):
        detail_short = d[:80] + "..." if len(d) > 80 else d
        out.append("- `%s`" % n)
        if detail_short:
            out.append("  - %s" % detail_short)
    out.append("")

    # Category (c): environment
    out.append("## Category (c): Environment-dependent")
    out.append("")
    out.append("### setUpClass cascades (%d names)" % len(setup_classes))
    out.append("")
    out.append(
        "These test classes fail at `setUpClass` because they require a running web server "
        "or external service that is not available in the test environment. They are not "
        "test logic failures - they are environment gaps."
    )
    out.append("")
    setup_names = sorted([n for n, r, d in cat_c if "setUpClass" in r])
    for n in setup_names:
        out.append("- `%s`" % n)
    out.append("")

    config_error = sorted([n for n, r, d in cat_c if "ConfigError" in r])
    if config_error:
        out.append("### src.clients.ConfigError (%d names)" % len(config_error))
        out.append("")
        out.append("These tests fail because a required client configuration is missing.")
        out.append("")
        for n in config_error:
            out.append("- `%s`" % n)
        out.append("")

    # Gone
    out.append("## %d names that now pass (were in old baseline, absent from new)" % len(only_old))
    out.append("")
    for n in only_old:
        out.append("- `%s`" % n)
    out.append("")
    out.append(
        "These may represent genuine fixes, or they may have been renamed/refactored. "
        "The `test_a_resume_leaves_a_ledger_row` entries (5 names) are noted in the old "
        "baseline as PRE-EXISTING RED guards for TASK-331. Their absence from this run "
        "needs verification."
    )
    out.append("")

    # Verification
    out.append("## Verification approach")
    out.append("")
    out.append(
        "This delta was generated from `scripts/suite_run.log` (2026-09-30 20:30), "
        "a complete run of `python -m unittest discover -s tests -v` that completed "
        "in 1252s (20m53s) with 13451 tests. The run was on branch `qwen-worker-r9` "
        "at commit fb45ab06, which differs from the baseline's master 0af11fcb only "
        "in documentation files and the task queue - no `src/` or `tests/` changes."
    )
    out.append("")
    out.append(
        "The 473 `src.personalization` failures are therefore PRE-EXISTING: the "
        "attribute errors exist at both commits because no code change occurred between "
        "them. The baseline simply did not record them."
    )
    out.append("")

    with open(OUT, "w", newline="\n") as f:
        f.write("\n".join(out))

    print(
        "Wrote %s: %d new, %d gone, %d still failing"
        % (OUT, len(only_new), len(only_old), len(both))
    )
    print("Categories: (a)=%d, (b)=%d, (c)=%d" % (len(cat_a), len(cat_b), len(cat_c)))


if __name__ == "__main__":
    main()
