#!/usr/bin/env python3
"""B4b: the canary preflight as ONE command with a FIXED output shape.

    py -3 -B scripts/preflight_one_command.py --cohort <cohort.json>
    py -3 -B scripts/preflight_one_command.py --cohort <cohort.json> --no-addresses
    py -3 -B scripts/preflight_one_command.py --cohort <cohort.json> --channel linkedin

READ-ONLY. Makes NO provider call, NO network call, and writes nothing:
the fixed shape goes to stdout and the operator redirects it. Every
verdict is computed by `src/preflight.py`; this wrapper RE-RENDERS that
assessment and never re-decides anything. If its own rendering cannot be
reconciled with the instrument's states, it prints SHAPE FAULT and exits
with the instrument's EXIT_UNKNOWN (2) rather than reporting a table it
cannot vouch for.

THE FIXED SHAPE (three sections, denominators always):

    SECTION 1 - one block per rule of the channel path, in ask order:
                rule name; roll-up verdict over the cohort; the authority
                files it read with their states; one-line reason.
    SECTION 2 - one line per contact: roll-up verdict.
    SECTION 3 - summary: contacts assessed / N, rules asked / M, count
                per verdict at both levels, authorities, controls, exit.

THE ROLL-UP VOCABULARY, and the instrument states it is built from:

    rule level    REFUSED        an authority this rule needs is in a
                                 preflight.REFUSALS state (the instrument's
                                 own "could not look" declaration)
                  NOT CLEARED    the rule fired (EXCLUDED) on >=1 contact
                  UNKNOWN        no exclusion, >=1 UNKNOWN cell
                  CLEARED        asked on every contact, fired on none,
                                 and NOT ONE unknown cell
                  NOT CONSULTED  every cell not_applicable on this channel
    contact level CLEARED                 instrument row verdict PASS
                  NOT CLEARED (EXCLUDED)  instrument row verdict EXCLUDED
                  NOT CLEARED (UNKNOWN)   instrument row verdict UNKNOWN

Precedence follows the instrument's own ordering: a refusal outranks a
finding (REFUSALS force exit 2 even when an exclusion fired), an exclusion
outranks an unknown, and UNKNOWN NEVER RENDERS AS CLEARED - invariant 0.

EXIT CODES are the instrument's, unchanged: 0 every contact cleared,
1 an exclusion fired, 2 UNKNOWN / refusal / control failure / no contact /
shape fault. 2 outranks 1.

NOT THE INSTRUMENT: `scripts/batch_preflight.py` is the batch-1 push
preflight (collision checks, --batch/--apply) and cannot answer these
rules. The canary preflight instrument is `src/preflight.py` +
`scripts/canary_preflight.py`; this file is a rendering wrapper over them.
"""
import argparse
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from src import preflight                                       # noqa: E402

#: Roll-up labels. Rendering vocabulary only; every one is derived from
#: preflight's own states and none adds an answer the instrument did not give.
R_CLEARED = "CLEARED"
R_NOT_CLEARED = "NOT CLEARED"
R_UNKNOWN = "UNKNOWN"
R_REFUSED = "REFUSED"
R_NOT_CONSULTED = "NOT CONSULTED"

C_CLEARED = "CLEARED"
C_NOT_CLEARED_EXCLUDED = "NOT CLEARED (EXCLUDED)"
C_NOT_CLEARED_UNKNOWN = "NOT CLEARED (UNKNOWN)"

RULE_VERDICT_ORDER = (R_REFUSED, R_NOT_CLEARED, R_UNKNOWN, R_CLEARED,
                      R_NOT_CONSULTED)
CONTACT_VERDICTS = (C_CLEARED, C_NOT_CLEARED_EXCLUDED, C_NOT_CLEARED_UNKNOWN)

FAULT = "SHAPE FAULT"


def _one_line(text, limit=200):
    collapsed = " ".join(str(text or "").split())
    if len(collapsed) > limit:
        collapsed = collapsed[:limit - 3] + "..."
    return collapsed


def load_cohort(path):
    with open(path, encoding="utf-8") as handle:
        rows = json.load(handle)
    if not isinstance(rows, list):
        raise ValueError("%s does not hold a list of contacts" % (path,))
    return rows


def consulted_rules(channel):
    """The rules asked on this channel, in the instrument's own ask order."""
    return [r for r in preflight.RULES
            if r.get("channel") in ("both", channel)]


def rule_rollup(rule, rows, authorities):
    """One rule's roll-up verdict over every contact row.

    Pure function of the instrument's cells and authority states. Returns
    (verdict, counts, reason) where counts is a dict with keys pass, excl,
    unk, na, total. Raises ValueError on any count that does not reconcile -
    the caller turns that into a SHAPE FAULT, never into a guess.
    """
    cells = [row["cells"][rule["name"]] for row in rows]
    total = len(cells)
    n_pass = sum(1 for c in cells
                 if c["cell"] == preflight.PASS and not c.get("not_applicable"))
    n_na = sum(1 for c in cells
               if c["cell"] == preflight.PASS and c.get("not_applicable"))
    n_excl = sum(1 for c in cells if c["cell"] == preflight.EXCLUDED)
    n_unk = sum(1 for c in cells if c["cell"] == preflight.UNKNOWN)
    if n_pass + n_na + n_excl + n_unk != total:
        raise ValueError("rule %s: cell states do not sum to the cohort "
                         "(%d+%d+%d+%d != %d)"
                         % (rule["name"], n_pass, n_na, n_excl, n_unk, total))

    refused_auth = [n for n in rule["needs"]
                    if authorities.get(n, {}).get("state") in preflight.REFUSALS]
    counts = {"pass": n_pass, "excl": n_excl, "unk": n_unk, "na": n_na,
              "total": total}

    if total == 0:
        # AN EMPTY COHORT IS NOT A CHANNEL STATEMENT. Checked before the
        # all-n/a branch because 0 == 0 would otherwise render "no contact
        # was assessed" as NOT CONSULTED - and the instrument's own answer
        # for an empty cohort is UNKNOWN, exit 2, never a clean anything.
        verdict = R_UNKNOWN
        reason = "no contact was assessed, which is not a clean cohort"
    elif refused_auth:
        verdict = R_REFUSED
        reason = "the instrument could not determine %s" % ", ".join(
            refused_auth)
        for name in refused_auth:
            reason += ": %s" % _one_line(authorities[name].get("why"), 120)
    elif n_na == total:
        verdict = R_NOT_CONSULTED
        reason = "not consulted on this channel path"
    elif n_excl:
        verdict = R_NOT_CLEARED
        reason = next(c["why"] for c in cells
                      if c["cell"] == preflight.EXCLUDED)
    elif n_unk:
        verdict = R_UNKNOWN
        reason = next(c["why"] for c in cells
                      if c["cell"] == preflight.UNKNOWN)
    elif n_pass == total and total > 0:
        verdict = R_CLEARED
        reason = next(c["why"] for c in cells
                      if c["cell"] == preflight.PASS)
    else:
        # DEFENSIVE: every reachable world is matched above (an empty cohort
        # returns early; not_applicable is uniform per rule because it
        # follows the rule's channel). A mixed pass/n-a row reaching here is
        # a world this wrapper has not seen - rendered UNKNOWN, never
        # CLEARED, because an unrecognised state clears nobody.
        verdict = R_UNKNOWN
        reason = "cells do not match any known roll-up state; " \
                 "rendered UNKNOWN rather than guessed"
    return verdict, counts, reason


def contact_rollup(row, n_rules):
    """One contact's line. A rendering of the instrument's own row fields."""
    if row["cleared"] and row["verdict"] == preflight.PASS:
        verdict = C_CLEARED
    elif not row["cleared"] and row["verdict"] == preflight.EXCLUDED:
        verdict = C_NOT_CLEARED_EXCLUDED
    elif not row["cleared"] and row["verdict"] == preflight.UNKNOWN:
        verdict = C_NOT_CLEARED_UNKNOWN
    else:
        raise ValueError("contact %s: verdict %r and cleared=%r do not "
                         "reconcile" % (row.get("key"), row.get("verdict"),
                                        row.get("cleared")))
    unknown_on = len(row.get("unknown_on") or [])
    if unknown_on + len(row.get("excluded_by") or []) > n_rules:
        raise ValueError("contact %s: unknown_on + excluded_by exceeds the "
                         "rule count" % (row.get("key"),))
    return verdict, unknown_on


def render(assessment, prov, cohort_path, channel, addresses, out):
    """The fixed shape. Every count is computed here, at render time."""
    rows = assessment["rows"]
    authorities = assessment["authorities"]
    rules = consulted_rules(channel)
    n_contacts = len(rows)
    n_rules = len(rules)

    rule_rows = []
    for rule in rules:
        verdict, counts, reason = rule_rollup(rule, rows, authorities)
        rule_rows.append((rule, verdict, counts, reason))
    contact_rows = []
    for row in rows:
        verdict, unknown_on = contact_rollup(row, n_rules)
        contact_rows.append((row, verdict, unknown_on))

    # ---- guard the shape before printing any of it: the counts must close.
    rule_verdict_counts = {v: 0 for v in RULE_VERDICT_ORDER}
    for _, verdict, _, _ in rule_rows:
        rule_verdict_counts[verdict] += 1
    if sum(rule_verdict_counts.values()) != n_rules:
        raise ValueError("rule verdicts do not sum to the rule count")
    contact_verdict_counts = {v: 0 for v in CONTACT_VERDICTS}
    for _, verdict, _ in contact_rows:
        contact_verdict_counts[verdict] += 1
    if sum(contact_verdict_counts.values()) != n_contacts:
        raise ValueError("contact verdicts do not sum to the cohort size")
    if (contact_verdict_counts[C_CLEARED] != assessment["totals"]["cleared"]
            or contact_verdict_counts[C_NOT_CLEARED_EXCLUDED]
            != assessment["totals"]["excluded"]
            or contact_verdict_counts[C_NOT_CLEARED_UNKNOWN]
            != assessment["totals"]["not_cleared_because_unknown"]):
        raise ValueError("contact roll-up disagrees with the instrument's "
                         "own totals")

    bar = "=" * 72
    out(bar)
    out("CANARY-01 PREFLIGHT - ONE COMMAND, FIXED OUTPUT SHAPE (B4b)")
    out(bar)
    out("run at      : %s" % (assessment.get("at")
                              or "AT AN UNRECORDED TIME (producer missing)"))
    out("sha         : %s" % (prov.get("sha") or "UNKNOWN"))
    out("instrument  : %s (%s)"
        % ("CONFIRMED" if prov.get("confirmed") else "NOT CONFIRMED",
           prov.get("detail") or "no provenance was measured"))
    out("tree        : %s" % preflight.tree_root())
    out("channel     : %s" % channel)
    out("cohort      : %s (%d contact(s))" % (cohort_path, n_contacts))
    out("verdicts are src/preflight.py's; this wrapper re-renders and "
        "never re-decides. UNKNOWN never renders as CLEARED.")

    out("")
    out("SECTION 1 - RULE ROLL-UP: all %d/%d rules of the %s path, "
        "in ask order" % (n_rules, n_rules, channel))
    for rule, verdict, counts, reason in rule_rows:
        out("")
        out("  %s" % rule["name"])
        out("    verdict  : %-13s cells pass=%d excl=%d unk=%d n/a=%d "
            "of %d" % (verdict, counts["pass"], counts["excl"],
                       counts["unk"], counts["na"], counts["total"]))
        if rule["needs"]:
            for name in rule["needs"]:
                a = authorities.get(name, {})
                out("    authority: %-30s %-18s records=%-6s %s"
                    % (name, a.get("state", "UNDECLARED"),
                       "-" if a.get("records") is None else a["records"],
                       a.get("path")))
        else:
            out("    authority: none declared - provider read "
                "(needs_provider_read)")
        if rule.get("needs_record"):
            out("    record   : required (this contact's queue record)")
        out("    reason   : %s" % _one_line(reason))

    out("")
    out("SECTION 2 - CONTACT ROLL-UP: all %d/%d contacts, in cohort order "
        "- %s" % (n_contacts, n_contacts,
                  "addresses shown" if addresses else "addresses withheld"))
    for row, verdict, unknown_on in contact_rows:
        who = row["email"] if addresses else "(withheld)"
        out("  %-24s %-16s %-40s excluded_by=%s unknown_on=%d/%d"
            % (verdict, row["key"] or "?", who,
               ",".join(row["excluded_by"]) or "-", unknown_on, n_rules))

    out("")
    out("SECTION 3 - SUMMARY (denominators always)")
    totals = assessment["totals"]
    out("  contacts assessed            %d/%d" % (totals["contacts"],
                                                  n_contacts))
    out("  rules asked                  %d/%d  (RULES at this SHA: %d; "
        "channel %s)" % (n_rules, n_rules, len(preflight.RULES), channel))
    out("  contact verdicts             %s" % "  ".join(
        "%s %d/%d" % (v, contact_verdict_counts[v], n_contacts)
        for v in CONTACT_VERDICTS))
    out("  rule verdicts                %s" % "  ".join(
        "%s %d/%d" % (v, rule_verdict_counts[v], n_rules)
        for v in RULE_VERDICT_ORDER))
    populated = [n for n in preflight.AUTHORITY_NAMES
                 if authorities.get(n, {}).get("state") in preflight.ANSWERABLE]
    out("  authorities POPULATED        %d/%d%s"
        % (len(populated), len(preflight.AUTHORITY_NAMES),
           ("  refusals: " + ", ".join(assessment["authority_refusals"]))
           if assessment["authority_refusals"] else "  refusals: none"))
    controls = assessment["controls"]
    ok = sum(1 for c in controls if c.get("ok"))
    out("  controls OK                  %d/%d" % (ok, len(controls)))
    no_form = [r["name"] for r in rules
               if r.get("ask") is None and not r.get("needs_provider_read")]
    provider = [r["name"] for r in rules if r.get("needs_provider_read")]
    out("  rules with no evaluable form at this SHA: %d/%d; "
        "provider-read rules: %d/%d"
        % (len(no_form), n_rules, len(provider), n_rules))
    out("  exit %d  (0=every contact cleared, 1=an exclusion fired, "
        "2=UNKNOWN/refusal/control failure/no contact/shape fault)"
        % assessment["exit_code"])
    out("")
    out("  %s" % assessment["sentence"])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--cohort", required=True,
                    help="JSON list of contacts. Never in git.")
    ap.add_argument("--channel", default="email",
                    choices=("email", "linkedin"))
    ap.add_argument("--no-addresses", action="store_true",
                    help="withhold addresses from stdout")
    ap.add_argument("--sha", default=None,
                    help="default: derived from git HEAD and verified by "
                         "preflight.provenance to carry the instrument")
    args = ap.parse_args(argv)

    try:
        contacts = load_cohort(args.cohort)
        state = preflight.authorities()
        controls = preflight.controls()
        assessment = preflight.assess(contacts, state=state,
                                      channel=args.channel,
                                      control_rows=controls)
        prov = preflight.provenance(sha=args.sha)
        render(assessment, prov, os.path.abspath(args.cohort), args.channel,
               addresses=not args.no_addresses, out=print)
    except SystemExit:
        raise
    except Exception as exc:                                    # noqa: BLE001
        # FAIL CLOSED AND SAY SO. An uncaught traceback would exit 1, which
        # is this instrument's EXIT_EXCLUDED - a wrapper crash must never be
        # readable as a finding about a person.
        print("%s: the fixed shape could not be rendered: %s: %s"
              % (FAULT, type(exc).__name__, _one_line(exc, 300)))
        print("nothing was assessed by this run; UNKNOWN, exit %d"
              % preflight.EXIT_UNKNOWN)
        return preflight.EXIT_UNKNOWN
    return assessment["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
