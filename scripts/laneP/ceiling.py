#!/usr/bin/env python3
"""LANE P: the CEILING - how many people in this store could be enrolled on
LinkedIn today if the five-axis cohort rule were relaxed to nothing?

The cohorted plan is small. Before anyone concludes that the cohort rule is
what makes it small, this measures the other bound: every candidate that
passed all four provider gates, capped by the client's own
`fatigue.account.max_active_contacts`, and ruled on by
`collision.account_policy` per account.

If the ceiling is also small, the constraint is SUPPLY and no loosening of
the cohort rule reaches the target. That is the question this answers, and
it costs one provider read per distinct account rather than per person.

READ ONLY.
"""
import collections
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import boot  # noqa: E402
import plan as planner  # noqa: E402

from src import collision  # noqa: E402

rows = []
for name in ("verified_all.json", "verified_top3.json"):
    path = os.path.join(boot.OUT, name)
    if os.path.exists(path):
        rows += json.load(open(path, encoding="utf-8"))["rows"]

seen, passed = set(), []
for row in rows:
    key = (row["record_id"], row["contact_key"])
    if key in seen or row.get("verdict") != "linkedin_only":
        continue
    seen.add(key)
    passed.append(row)

by_account = collections.defaultdict(list)
for row in passed:
    by_account[str(row.get("domain") or row.get("company") or "").lower()
               ].append(row)

verdicts, ceiling, detail = collections.Counter(), 0, []
for account, people in sorted(by_account.items(),
                              key=lambda kv: -len(kv[1])):
    if not account:
        verdicts["no_domain"] += 1
        continue
    try:
        answer = collision.check_account(
            account, expect_workspace=os.environ.get("BISON_WORKSPACE_ID"))
        decision, why = collision.account_policy(answer)
    except Exception as exc:  # noqa: BLE001
        decision, why = collision.HOLD, f"{type(exc).__name__}: {exc}"
    verdicts[decision] += 1
    allowed = min(len(people), planner.ACCOUNT_CAP) \
        if decision == collision.ALLOW else 0
    ceiling += allowed
    detail.append({"people_passing_the_four_gates": len(people),
                   "account_decision": decision,
                   "enrollable_after_the_cap": allowed,
                   "why": why[:110]})

summary = {
    "candidates_that_passed_all_four_gates": len(passed),
    "distinct_accounts": len(by_account),
    "account_cap": planner.ACCOUNT_CAP,
    "account_verdicts": verdicts.most_common(),
    "CEILING_enrollable_today_ignoring_cohort_shape": ceiling,
    "accounts": detail,
    "people_by_account_verdict": {
        verdict: sum(a["people_passing_the_four_gates"] for a in detail
                     if a["account_decision"] == verdict)
        for verdict in sorted({a["account_decision"] for a in detail})},
}
with open(os.path.join(boot.OUT, "CEILING.json"), "w", encoding="utf-8") as f:
    json.dump(summary, f, indent=1)
print(json.dumps({k: v for k, v in summary.items() if k != "accounts"},
                 indent=1))
