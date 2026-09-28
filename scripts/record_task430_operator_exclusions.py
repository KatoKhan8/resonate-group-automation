#!/usr/bin/env python3
"""Record the TASK-430 permanent operator exclusions. Idempotent, reproducible.

OPERATOR DECISION "B", Zvonimir, 2026-09-28. The 32 companies across campaigns
491-500 that would not pass today's ICP gate are permanently excluded by
operator policy: they must not be enrolled regardless of future fact
refreshes.

This script exists so the register's contents are DERIVED and re-derivable
rather than hand-typed. It reads the identities from the audit artifact -
`work/TASK-430-icp-verdicts-2026-09-27.json`, gitignored because it names 665
real companies - and writes only the one-way account hashes plus the decision
metadata into `config/operator-exclusions.jsonl`, which is tracked.

It writes NOTHING to `work/`, touches no queue record, changes no verdict and
calls no provider.

  py -3 scripts/record_task430_operator_exclusions.py --dry-run
  py -3 scripts/record_task430_operator_exclusions.py --apply
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import operatorexclusion as oe  # noqa: E402

VERDICTS = os.path.join("work", "TASK-430-icp-verdicts-2026-09-27.json")

BY = "Zvonimir (operator)"
AT = "2026-09-28"
TASK = "TASK-430"
AUTHORITY = ("operator decision B, Zvonimir, 2026-09-28, recorded in "
             "docs/PERMANENT-OPERATOR-EXCLUSION-2026-09-28.md")
REASON = ("would not pass the ICP gate on the TASK-430 audit of campaigns "
          "491-500 and the operator ruled the account must never be enrolled "
          "again; the classifier verdict and the human review are unchanged "
          "and this exclusion does not depend on either")


def the_32(path):
    """The accounts the audit found not qualified: 7 rejected + 25 review."""
    companies = json.load(open(path, encoding="utf-8"))["companies"]
    return {domain: row for domain, row in companies.items()
            if row.get("icp_status") != "qualified"}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--verdicts", default=VERDICTS)
    p.add_argument("--apply", action="store_true",
                   help="append the rows; without it nothing is written")
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args(argv)

    accounts = the_32(a.verdicts)
    index = oe.resolve()
    already = [d for d in accounts if oe.account_key(d) in index]
    todo = [d for d in accounts if oe.account_key(d) not in index]

    print(f"  accounts in the audit, not qualified   {len(accounts)}")
    print(f"    of those, already in the register    {len(already)}")
    print(f"    to append                            {len(todo)}")
    by_status = {}
    for domain in accounts:
        status = accounts[domain].get("icp_status")
        by_status[status] = by_status.get(status, 0) + 1
    print(f"  classifier verdicts, UNCHANGED by this {by_status}")

    if not a.apply:
        print("  Nothing written. Pass --apply.")
        return 0

    written = 0
    for domain in sorted(todo):
        oe.exclude(domain, by=BY, reason=REASON, authority=AUTHORITY,
                   at=AT, origin=oe.OPERATOR_POLICY, task=TASK)
        written += 1
    print(f"  appended                               {written}")
    report = oe.audit()
    print(f"  register active                        {report['active']}")
    print(f"  active set fingerprint                 "
          f"{report['active_set_fingerprint']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
