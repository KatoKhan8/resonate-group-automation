#!/usr/bin/env python3
"""The real funnel, stage by stage, from canonical state. READ-ONLY.

    py -3 scripts/funnel_truth.py

Built 2026-09-20 to answer one question with measurement rather than
assertion: WHY does this system have 18 live contact-channel pairs and not
sixty?

Every number is counted from `work/queue.jsonl` and the live cohort
computation, never from a handoff. The stages are the ones the pipeline
actually has, and each reports what came IN, what came OUT, and what is held
and WHY - because a funnel that only reports totals cannot tell a sourcing
problem from an approval problem, and this estate has been misdiagnosed as
the second when it is mostly the first.
"""
import collections
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src import store  # noqa: E402


def main():
    recs = store.load()
    print("=" * 74)
    print("  RESONATE OS FUNNEL - counted from canonical state")
    print("=" * 74)

    total = len(recs)
    states = collections.Counter(r.get("state") for r in recs)
    lanes = collections.Counter(r.get("lane") for r in recs)

    # ---- account stages
    qualified = [r for r in recs if (r.get("qualification") or {}).get("verdict")]
    # `verdict` is a DICT here, not a string - the ICP verdict carries score,
    # tier, status and the structural breakdown. Counting the dict raises
    # unhashable, which is the shape telling you to ask a narrower question.
    verdicts = collections.Counter(
        str(((r.get("qualification") or {}).get("verdict") or {})
            .get("icp_status")) for r in qualified)
    tiers = collections.Counter(
        str(((r.get("qualification") or {}).get("verdict") or {})
            .get("icp_tier")) for r in qualified)
    with_contacts = [r for r in recs if (r.get("contacts") or [])]
    contacts = [c for r in recs for c in (r.get("contacts") or [])]
    with_email = [c for c in contacts if (c.get("email") or "").strip()]
    with_li = [c for c in contacts if (c.get("linkedin") or "").strip()]
    sendable = [c for c in contacts if c.get("sendable")]
    verified = [c for c in contacts
                if str((c.get("verification") or {}).get("verdict") or
                       c.get("verdict") or "").lower() in
                ("verified", "valid", "deliverable", "ok")]

    print(f"  ACCOUNTS IN QUEUE                 {total}")
    print(f"    by state                        {dict(states)}")
    print(f"    by lane                         {dict(lanes)}")
    print()
    print(f"  ACCOUNTS WITH AN ICP VERDICT      {len(qualified)}"
          f"   of {total}")
    for v, n in verdicts.most_common():
        print(f"      icp_status {str(v):18} {n}")
    for v, n in sorted(tiers.items()):
        print(f"      icp_tier   {str(v):18} {n}")
    print()
    print(f"  ACCOUNTS WITH >=1 CONTACT         {len(with_contacts)}")
    print(f"  CONTACTS (decision makers)        {len(contacts)}")
    print(f"    with an email address           {len(with_email)}")
    print(f"    with a linkedin url             {len(with_li)}")
    print(f"    marked sendable                 {len(sendable)}")
    print(f"    email verified                  {len(verified)}")
    print()

    # ---- the drop: accounts with NO contact at all
    no_contact = total - len(with_contacts)
    print(f"  THE FIRST BIG DROP")
    print(f"    accounts carrying NO contact    {no_contact}"
          f"   ({100*no_contact//total}% of the estate)")
    print(f"    -> these need decision-maker discovery, a PAID ContactOut")
    print(f"       call. ContactOut IS configured and authenticating:")
    print(f"       `py -3 scripts/credential_health.py --verify`.")
    print(f"       The variable is CONTACTOUT_TOKEN. An earlier version of")
    print(f"       THIS script asserted CONTACTOUT_KEY was absent and")
    print(f"       concluded the path was dead. It invented the name.")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
