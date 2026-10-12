#!/usr/bin/env python3
"""PLANNER-ONLY. What `keyword_plan` would read for the catalogue's questions.

    py -3 scripts/slack_planner_scorecard.py
    py -3 scripts/slack_planner_scorecard.py --out scorecard.json

## THIS IS NOT A REPLAY AND IT DOES NOT MEASURE THE AGENT'S ANSWERS

It calls `slackconversation.keyword_plan` and nothing else. No model, no
provider, no Slack, no network, and it never opens `work/`. What it scores
is the NO-MODEL FALLBACK's tool choice. The live loop runs with a model
configured, so a number from here says nothing about what a real answer
would have read, and nothing at all about what it would have said.

## WHY IT EXISTS: `--catalogue` CANNOT SCORE A TOOL AT ALL

Measured 2026-10-12 on e8da7edf0. `scripts/slack_agent_replay.py --catalogue
--no-model` scored the `tool` column **n/a on all 27 questions**, because
`catalogue_questions` emits `channel: None`, `slackscope.resolve` correctly
refuses to guess a binding, and an UNBOUND channel is given no tool at all -
every row came back `planned: "no tool is available in this scope"` with
`tools: []`. The column was honest and empty.

## AND THE CATALOGUE CANNOT SUPPLY THE MISSING SCOPE

Checked before writing this, because adding the scope to the catalogue would
have been the better fix. `docs/SLACK-AGENT-QUESTION-CATALOGUE.md` does not
record one PER QUESTION: section 2's "Who asks" column is per INTENT and is
prose - "internal >> client", "mixed", "client-heavy" - and section 3's
phrasings carry no asker marker. The miner's `channel_role` does classify a
room, but it runs over `work/slack-history` and its per-message output was
deliberately never committed. **So the real scope of a catalogue question is
not recoverable, and this does not invent one.**

What it does instead is report the planner under EACH CANDIDATE SCOPE and
label them, which is a different and weaker claim than knowing: "in an
internal channel the planner would read X" is measurable; "this question was
asked in an internal channel" is not known and is not asserted.

## THE THREE THINGS THIS KEEPS APART, AND WHY

    expectations       `slack_agent_replay.EXPECTED_TOOLS` - hand-written
                       from the question's meaning, deliberately NOT derived
                       from `KEYWORD_PLAN`, which is the thing being scored
    available tools    `slackagenttools.for_scope(scope)` - the REGISTRY is
                       the only authority on what a scope may call
    the plan           `slackconversation.keyword_plan(question, scope)`

**Scope is an input here, never computed from the expectations.** If the
table decided which tools were available, the measure would move whenever
somebody edited the table, and a scorecard that grades its own answer key
measures nothing. The separation is asserted directly in
`tests/test_the_planner_scorecard_is_not_its_own_answer_key.py`.

## `n/a` HAS THREE REASONS AND NONE OF THEM IS A PASS

    no_expectation          the question names nothing extractable
    unavailable_in_scope    every acceptable read is barred to this scope,
                            so the planner cannot be blamed for not calling
                            one - `monitors` is internal-only, and a monitor
                            question in a client channel is unscoreable, not
                            failed
    planner_chose_nothing   the plan was empty

Each is reported with its reason and counted apart from pass and fail. The
percentage is taken over SCORED rows only and the scored count is printed
beside it, because 50% of 18 and 50% of 27 are different claims.
"""
import argparse
import collections
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import importlib.util                                            # noqa: E402

from src import slackagenttools as agenttools                    # noqa: E402
from src import slackconversation as conversation                # noqa: E402
from src import slackscope                                       # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PASS, FAIL, NA = "pass", "fail", "n/a"

#: The workspace a hypothetical client scope names. It does NOT affect the
#: measurement - `keyword_plan` reads `scope.kind` and nothing else - and
#: `test_the_slug_does_not_change_the_plan` proves that rather than
#: asserting it. A client Scope must name one, so this names an obvious
#: placeholder instead of borrowing a real client's slug into a report.
PLACEHOLDER_SLUG = "scorecard-placeholder"


def harness():
    """`slack_agent_replay`, loaded by path because `scripts/` is not a
    package. Only `expected_tools_for` and `catalogue_questions` are used -
    nothing here runs a replay."""
    spec = importlib.util.spec_from_file_location(
        "slack_agent_replay",
        os.path.join(ROOT, "scripts", "slack_agent_replay.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def candidate_scopes():
    """The scopes a question COULD have been asked in, each labelled.

    UNBOUND is included deliberately and is expected to score nothing: it
    is the scope the replay actually resolved, and showing it empty beside
    the other two is the evidence for why this script exists.
    """
    return (
        slackscope.Scope(slackscope.INTERNAL, source="scorecard candidate"),
        slackscope.Scope(slackscope.CLIENT, workspace=PLACEHOLDER_SLUG,
                         source="scorecard candidate"),
        slackscope.Scope(slackscope.UNBOUND, source="scorecard candidate"),
    )


def per_expectation(question, expected_rows):
    """Each expectation this question matched, with ITS OWN reads.

    ## WHY THE UNION IS NOT ENOUGH FOR A BREAKDOWN

    `expected_tools_for` returns the union, which is the right rule for the
    row's verdict - see the replay harness on UNION, NOT EVERY ROW. But a
    per-expectation table built from a union verdict LIES. Measured
    2026-10-12: three catalogue rows match more than one expectation and
    all three passed, so crediting the row's pass to every expectation it
    matched reported `lead pass=1` when that row was answered by
    `sends_today` on its CAMPAIGN expectation and by nothing on its lead
    one. The lead gap looked one third smaller than it is.

    The predicate here is the same `re.search(asked, low, re.I)` that
    `expected_tools_for` uses, and
    `test_the_per_expectation_walk_agrees_with_the_union` asserts the two
    find the same names on every catalogue question, so this cannot drift
    away from it silently.
    """
    low = str(question or "").lower()
    return [(name, tuple(allowed)) for name, asked, allowed in expected_rows
            if re.search(asked, low, re.I)]


def score_one(question, scope, expected_tools_for, expected_rows=None):
    """One question under one scope. Returns a row, never raises.

    `expected_tools_for` is passed IN rather than imported here so a test
    can substitute it and prove the available-tool set does not move with
    it. See the module docstring. `expected_rows` is the table itself and
    is used ONLY for the per-expectation breakdown, never for the verdict.
    """
    about, acceptable = expected_tools_for(question)
    # THE REGISTRY IS THE AUTHORITY ON WHAT THIS SCOPE MAY CALL. Not the
    # expectation table, and not this file.
    available = set(agenttools.for_scope(scope))
    planned = [call["name"]
               for call in conversation.keyword_plan(question, scope)]
    row = {"question": question, "scope": scope.kind, "about": about,
           "acceptable": list(acceptable),
           "available_in_scope": len(available),
           "planned": planned, "mark": None, "reason": None}

    if not acceptable:
        row["mark"], row["reason"] = NA, "no_expectation"
    elif not (set(acceptable) & available):
        row["mark"], row["reason"] = NA, "unavailable_in_scope"
    elif not planned:
        row["mark"], row["reason"] = NA, "planner_chose_nothing"
    elif set(planned) & set(acceptable):
        row["mark"] = PASS
    else:
        row["mark"] = FAIL
        row["missed"] = sorted(set(acceptable) & available)

    # THE PER-EXPECTATION VERDICT, each judged against its OWN reads only.
    # This is for the breakdown and never for `mark` above.
    if expected_rows is not None:
        detail = {}
        for name, allowed in per_expectation(question, expected_rows):
            mine = set(allowed) & available
            if not mine:
                detail[name] = NA
            elif not planned:
                detail[name] = NA
            else:
                detail[name] = PASS if set(planned) & mine else FAIL
        row["by_expectation"] = detail
    return row


def build(root=None):
    """Every catalogue question under every candidate scope."""
    root = root or ROOT
    h = harness()
    questions = [r["text"] for r in h.catalogue_questions(root)]
    rows = []
    for scope in candidate_scopes():
        for question in questions:
            rows.append(score_one(question, scope, h.expected_tools_for,
                                  expected_rows=h.EXPECTED_TOOLS))
    return questions, rows


def _ascii(text):
    """The console here is cp1250 and a Croatian character in a `print`
    kills the script. The full text is kept in `--out`."""
    return str(text).encode("ascii", "replace").decode("ascii")


def report(questions, rows, out=None):
    print("PLANNER-ONLY SCORECARD - `keyword_plan`, no model, no provider")
    print("This does NOT measure the agent's real answers. See the module "
          "docstring.")
    print()
    print("catalogue questions parsed: %d" % len(questions))
    print()

    for kind in (slackscope.INTERNAL, slackscope.CLIENT, slackscope.UNBOUND):
        mine = [r for r in rows if r["scope"] == kind]
        if not mine:
            continue
        tally = collections.Counter(r["mark"] for r in mine)
        reasons = collections.Counter(r["reason"] for r in mine if r["reason"])
        scored = tally[PASS] + tally[FAIL]
        avail = mine[0]["available_in_scope"]
        print("=== SCOPE %s  (tools available in this scope: %d) ==="
              % (kind.upper(), avail))
        print("  questions            : %d" % len(mine))
        print("  SCORED               : %d" % scored)
        print("  pass                 : %d" % tally[PASS])
        print("  fail                 : %d" % tally[FAIL])
        print("  n/a                  : %d" % tally[NA])
        for reason, count in sorted(reasons.items()):
            print("      %-22s %d" % (reason, count))
        if scored:
            print("  pass rate among SCORED: %.0f%% (%d of %d)"
                  % (100.0 * tally[PASS] / scored, tally[PASS], scored))
        else:
            print("  pass rate among SCORED: NOT MEASURABLE - nothing scored")
        print()

    print("=== BY EXPECTED TOOL (internal scope) ===")
    internal = [r for r in rows if r["scope"] == slackscope.INTERNAL]
    print("Each expectation is judged against ITS OWN reads, so a row that")
    print("matched two expectations is not credited to both. See "
          "`per_expectation`.")
    by = {}
    for row in internal:
        for name, verdict in sorted((row.get("by_expectation") or {}).items()):
            slot = by.setdefault(name, collections.Counter())
            slot[verdict] += 1
    if not by:
        print("  nothing matched any expectation row")
    for name in sorted(by):
        total = sum(by[name].values())
        print("  %-10s rows=%-3d pass=%-3d fail=%-3d n/a=%-3d"
              % (name, total, by[name][PASS], by[name][FAIL], by[name][NA]))
    multi = [r for r in internal if len(r["about"]) > 1]
    print("  (%d of %d internal rows matched more than one expectation)"
          % (len(multi), len(internal)))
    print()

    print("=== THE CASES THE BRIEF ASKS ABOUT, internal scope ===")
    for want in ("meeting", "lead", "report", "monitor"):
        hits = [r for r in internal if want in r["about"]]
        if not hits:
            print("  %-8s NOT IN THE CATALOGUE - this corpus does not "
                  "measure it" % want)
            continue
        print("  %s: %d question(s)" % (want, len(hits)))
        for row in hits:
            verdict = (row.get("by_expectation") or {}).get(want, "?")
            print("    [%s for `%s`; row overall %s] %s"
                  % (verdict, want, row["mark"],
                     _ascii(row["question"])[:48]))
            print("         chose    : %s" % ",".join(row["planned"]))
            print("         about    : %s" % ",".join(row["about"]))
            print("         any of (this expectation only): %s"
                  % ",".join(dict(per_expectation(
                      row["question"], harness().EXPECTED_TOOLS)).get(
                          want, ()))[:70])
    print()

    print("=== EVERY ROW WHERE THE PLANNER CHOSE `monitors` ===")
    hits = [r for r in internal if "monitors" in r["planned"]]
    if not hits:
        words = [w for ws, names in conversation.KEYWORD_PLAN
                 for w in ws if "monitors" in names]
        print("  0 rows. The planner routes %s to `monitors`, and NO "
              "catalogue" % (words,))
        print("  phrasing contains any of them - so the `running` -> "
              "`monitors` defect")
        print("  that the 2026-09-23 audit found in the LIVE log is NOT "
              "measured by")
        print("  this corpus. It is not absent from the system; it is "
              "absent from here.")
    for row in hits:
        print("    [%s] %s -> %s" % (row["mark"], _ascii(row["question"])[:50],
                                     ",".join(row["planned"])))

    if out:
        with open(out, "w", encoding="utf-8") as handle:
            json.dump({"questions": questions, "rows": rows}, handle,
                      indent=1, ensure_ascii=False)
        print()
        print("wrote %s" % out)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Planner-only tool scorecard. No model, no provider, "
                    "no network, no work/ read.")
    parser.add_argument("--out", default=None,
                        help="write every scored row as JSON here")
    args = parser.parse_args(argv)
    questions, rows = build()
    report(questions, rows, out=args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
