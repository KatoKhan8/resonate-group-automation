#!/usr/bin/env python3
"""The per-contact, per-rule preflight for a cohort. READ-ONLY.

    py -3 scripts/canary_preflight.py --cohort work/.../cohort.json
    py -3 scripts/canary_preflight.py --cohort <file> --markdown > report.md
    py -3 scripts/canary_preflight.py --controls-only
    py -3 scripts/canary_preflight.py --authorities

Makes NO provider call, NO network call, and writes nothing but its own
stdout. Every rule that needs a provider read is reported UNKNOWN by
declaration rather than asked.

## THE COHORT FILE IS AN ARGUMENT AND IT IS NEVER IN GIT

It holds real people's addresses. It lives in `resonate-ops/` or under
gitignored `work/`, and the path is passed in, so this script carries no
cohort of its own and a `grep` of the repository for a prospect finds
nothing. The expected shape is a list of objects:

    [{"key": "...", "name": "...", "company": "...",
      "email": "...", "domain": "..."}]

`record` is optional and, when present, is this contact's queue record. It is
absent here by construction: the queue is production state this task's
boundaries forbid reading, so every rule that needs it reports UNKNOWN and
names the file.

## EXIT CODES

    0   every contact cleared: every rule asked, every rule passed
    1   at least one contact EXCLUDED by a rule that fired
    2   at least one contact NOT CLEARED because a rule could not be asked,
        or the controls did not hold, or no contact was assessed

2 outranks 1: a table whose instrument could not see does not support either
answer. Same rule as `bounce_stop_7day`'s BLIND outranking its STOP, and
`queue_wall_check`'s CANNOT-ASSESS outranking its WALL.
"""
import argparse
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from src import preflight                                       # noqa: E402

CELL_MARK = {preflight.PASS: "pass", preflight.EXCLUDED: "EXCL",
             preflight.UNKNOWN: "unk?"}


def load_cohort(path):
    with open(path, encoding="utf-8") as handle:
        rows = json.load(handle)
    if not isinstance(rows, list):
        raise ValueError("%s does not hold a list of contacts" % (path,))
    return rows


def print_authorities(state, out=print):
    out("")
    out("AUTHORITIES - each rule's input, by path, state checked before the "
        "rule is asked")
    for name in preflight.AUTHORITY_NAMES:
        row = state[name]
        out("  %-30s %-10s %s" % (name, row["state"], row.get("path")))
        if row["state"] != preflight.PRESENT:
            out("      %s" % row["why"])
            out("      WHICH MEANS: %s" % row["absent_means"])


def print_controls(rows, out=print):
    for row in rows:
        out("  CONTROL %-4s %s" % ("OK" if row["ok"] else "FAIL",
                                   row["control"]))
        if not row["ok"]:
            out("           planted  %s" % row["planted"])
            out("           expected %r" % (row["expected"],))
            out("           observed %r" % (row["observed"],))


def print_gaps(out=print):
    """Rules declared somewhere authoritative with nothing asking them.

    Printed with the table rather than filed away, because a rule nobody
    asks is indistinguishable from a rule that passed - which is this whole
    task's shape, one level out from the cells.
    """
    out("")
    out("RULES EXPECTED AND NOT FOUND ON ANY SEND PATH")
    for row in preflight.RULES_EXPECTED_BUT_NOT_FOUND:
        out("  %s" % row["name"])
        out("      declared in : %s" % row["declared_in"])
        out("      what exists : %s" % row["what_exists"])
        out("      what is NOT : %s" % row["what_is_missing"])
        out("      would need  : %s" % row["would_need"])


def print_table(assessment, out=print, addresses=True):
    """One row per contact, one column per rule.

    Printed as a column list rather than a wide grid: twenty-two rules do not
    fit a terminal, and a table that wraps is a table nobody reads.
    """
    out("")
    out("THE RULES, in the order they are asked")
    for rule in preflight.RULES:
        out("  %-30s %-9s %s" % (rule["name"], rule["channel"],
                                 rule["decides"]))
    out("")
    out("ONE ROW PER CONTACT - %s" % ("addresses shown" if addresses
                                      else "addresses withheld"))
    for row in assessment["rows"]:
        who = row["email"] if addresses else (row["key"] or "?")
        out("")
        out("  %-9s %-28s %s" % (row["verdict"], row["key"] or "?", who))
        out("            %s" % (row["company"] or "?"))
        for name in preflight.RULE_NAMES:
            cell = row["cells"][name]
            if cell["cell"] == preflight.PASS and cell.get("not_applicable"):
                continue
            out("      %-4s %-28s %s" % (CELL_MARK[cell["cell"]], name,
                                         cell["why"][:150]))


def print_totals(assessment, out=print):
    totals = assessment["totals"]
    out("")
    out("  TOTALS")
    out("    contacts assessed                 %d" % totals["contacts"])
    out("    cleared                           %d" % totals["cleared"])
    out("    excluded                          %d" % totals["excluded"])
    # THE THIRD IS THE ONE THAT MATTERS, and it is printed last and labelled,
    # because it is the number most likely to read zero because the
    # instrument could not see.
    out("    NOT CLEARED because UNKNOWN       %d  <-- the one that matters"
        % totals["not_cleared_because_unknown"])
    out("")
    out("  %s" % assessment["sentence"])
    out("  exit %d" % assessment["exit_code"])


def markdown(assessment, sha="UNKNOWN", cohort_path=None):
    """The report body. The table is per contact, with the rules as columns.

    Addresses ARE in this output: it is written to `resonate-ops/`, which is
    where the cohort already lives, and a preflight a person cannot tie to a
    named contact is not a preflight.
    """
    totals = assessment["totals"]
    lines = [
        "# CANARY-01 preflight - one row per contact, one column per rule",
        "",
        "**%s**" % assessment["sentence"],
        "",
        "Measured %s on SHA `%s`, channel `%s`. Read-only: no provider call, "
        "no network call, nothing written but this file."
        % (assessment.get("at", "see the lane entry"), sha,
           assessment["channel"]),
        "",
        "    contacts assessed             %d" % totals["contacts"],
        "    cleared                       %d" % totals["cleared"],
        "    excluded                      %d" % totals["excluded"],
        "    NOT CLEARED because UNKNOWN   %d   <- the one that matters"
        % totals["not_cleared_because_unknown"],
        "",
        "Cohort read from `%s`." % (cohort_path or "an argument"),
        "",
        "## The controls, every run",
        "",
    ]
    for row in assessment["controls"]:
        lines.append("- **%s** - %s. planted: %s; expected `%r`; observed "
                     "`%r`." % ("OK" if row["ok"] else "FAIL",
                                row["control"], row["planted"],
                                row["expected"], row["observed"]))
    lines += ["", "## The authorities, state checked BEFORE the rule", "",
              "| authority | state | path | what an absence means |",
              "|---|---|---|---|"]
    for name in preflight.AUTHORITY_NAMES:
        row = assessment["authorities"][name]
        lines.append("| `%s` | **%s** | `%s` | %s |"
                     % (name, row["state"], row.get("path"),
                        row["absent_means"] if row["state"]
                        != preflight.PRESENT else "-"))
    lines += ["", "## Rules expected and NOT found on any send path", "",
              "A rule nobody asks is indistinguishable from a rule that "
              "passed. These are declared somewhere this project treats as "
              "authority and have no implementation that could exclude a "
              "contact.", ""]
    for row in preflight.RULES_EXPECTED_BUT_NOT_FOUND:
        lines += ["### `%s`" % row["name"], "",
                  "- **declared in:** %s" % row["declared_in"],
                  "- **what exists:** %s" % row["what_exists"],
                  "- **what is missing:** %s" % row["what_is_missing"],
                  "- **what would answer it:** %s" % row["would_need"], ""]
    lines += ["", "## The rules", "",
              "| rule | channel | what decides it |", "|---|---|---|"]
    for rule in preflight.RULES:
        lines.append("| `%s` | %s | `%s` |"
                     % (rule["name"], rule["channel"], rule["decides"]))
    lines += ["", "## One row per contact", ""]
    for row in assessment["rows"]:
        lines += [
            "### %s - %s (%s)" % (row["verdict"], row["name"] or row["key"],
                                  row["company"] or "?"),
            "",
            "`%s` at `%s`, key `%s`." % (row["email"], row["domain"],
                                         row["key"]),
            "",
        ]
        if row["excluded_by"]:
            lines.append("**EXCLUDED by:** %s"
                         % ", ".join("`%s`" % n for n in row["excluded_by"]))
            lines.append("")
        lines += ["| rule | cell | why |", "|---|---|---|"]
        for name in preflight.RULE_NAMES:
            cell = row["cells"][name]
            if cell["cell"] == preflight.PASS and cell.get("not_applicable"):
                continue
            lines.append("| `%s` | **%s** | %s |"
                         % (name, cell["cell"], cell["why"]))
        lines.append("")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--cohort", default=None,
                    help="JSON list of contacts. Never in git.")
    ap.add_argument("--channel", default="email", choices=("email", "linkedin"))
    ap.add_argument("--controls-only", action="store_true")
    ap.add_argument("--authorities", action="store_true")
    ap.add_argument("--markdown", action="store_true")
    ap.add_argument("--no-addresses", action="store_true",
                    help="withhold addresses from stdout")
    ap.add_argument("--sha", default="UNKNOWN")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    if args.controls_only:
        rows = preflight.controls()
        print_controls(rows)
        return 0 if all(r["ok"] for r in rows) else preflight.EXIT_UNKNOWN

    state = preflight.authorities()
    if args.authorities:
        print_authorities(state)
        bad = [n for n in preflight.AUTHORITY_NAMES
               if state[n]["state"] != preflight.PRESENT]
        print("")
        print("  %d of %d authorities PRESENT; %s"
              % (len(preflight.AUTHORITY_NAMES) - len(bad),
                 len(preflight.AUTHORITY_NAMES),
                 ("not present: " + ", ".join(bad)) if bad else "all present"))
        return 0 if not bad else preflight.EXIT_UNKNOWN

    if not args.cohort:
        ap.error("--cohort is required (or use --controls-only / "
                 "--authorities)")
    contacts = load_cohort(args.cohort)
    controls = preflight.controls()
    assessment = preflight.assess(contacts, state=state,
                                  channel=args.channel,
                                  control_rows=controls)

    if args.json:
        print(json.dumps(assessment, indent=1, default=str))
        return assessment["exit_code"]
    if args.markdown:
        print(markdown(assessment, sha=args.sha, cohort_path=args.cohort))
        return assessment["exit_code"]

    print_controls(controls)
    print_authorities(state)
    print_gaps()
    print_table(assessment, addresses=not args.no_addresses)
    print_totals(assessment)
    return assessment["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
