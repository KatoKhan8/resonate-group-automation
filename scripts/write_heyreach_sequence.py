#!/usr/bin/env python3
"""Write one campaign's corrected LinkedIn sequence to HeyReach, and read it back.

THIS SCRIPT EXISTS TO BE NARROW. Every live provider write in this repository
goes through `providerwrites.perform`, which is the door; this is a
single-purpose caller of one verb - `LINKEDIN_SET_SEQUENCE` - so the operator
can grant permission to exactly this and to nothing else.

WHAT IT CAN DO

  Replace the sequence on the HeyReach campaign named by a canonical campaign
  id, then read the sequence back and report whether the provider agrees.

WHAT IT CANNOT DO, AND NOT BY CONVENTION

  It cannot add a lead: `LINKEDIN_ADD_LEAD` is not in
  `providerwrites.SUPPORTED` and this script does not name it.
  It cannot start a campaign: `Resume` and `StartCampaign` are absent from
  `heyreach.WRITE_ROUTES` and asserted absent by the seals.
  It cannot send anything to anybody. A sequence written onto a campaign that
  holds nobody reaches nobody.

WHY THAT MATTERS HERE. Campaign 599020 currently holds one real contact's
personalised words - "hi jacob, ... at &Partner?" - at CAMPAIGN level, for a
canonical row naming fourteen records. Replacing it with merge fields is a
strict reduction in risk, and it is the step that must happen BEFORE any lead
is added, not after.

  python scripts/write_heyreach_sequence.py <campaign-id>          dry run
  python scripts/write_heyreach_sequence.py <campaign-id> --live   writes
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import heyreachfactory                            # noqa: E402
from src.providers import heyreach                         # noqa: E402

SINGLE_BRACE = re.compile(r"(?<!\{)\{([A-Za-z_][A-Za-z0-9_]*)\}(?!\})")
DOUBLE_BRACE = re.compile(r"\{\{([A-Za-z_][A-Za-z0-9_]*)\}\}")


def describe(sequence):
    """What a person needs to see before believing a sequence is safe."""
    raw = json.dumps(sequence)
    nodes = heyreach.walk_sequence(sequence)[0]
    kinds = {}
    for node in nodes:
        kind = node.get("nodeType")
        kinds[kind] = kinds.get(kind, 0) + 1
    return {
        "nodes": len(nodes),
        "node_types": kinds,
        "merge_variables": sorted(set(SINGLE_BRACE.findall(raw))),
        # A double brace would reach a prospect as literal text. Measured
        # across 81 campaign sequences in this workspace: 3,295 single-brace
        # occurrences and ZERO double.
        "double_brace_variables": sorted(set(DOUBLE_BRACE.findall(raw))),
    }


def main(argv=None):
    p = argparse.ArgumentParser(prog="write_heyreach_sequence")
    p.add_argument("campaign", help="the CANONICAL campaign id")
    p.add_argument("--live", action="store_true",
                   help="actually write. Dry run is the default")
    args = p.parse_args(argv)

    report = heyreachfactory.stage(args.campaign, live=args.live,
                                   by="write_heyreach_sequence")
    plan = report["plan"]
    print(json.dumps({
        "campaign": report["campaign"],
        "client": report["client"],
        "live": report["live"],
        "did": report["did"],
        "sequence": describe(plan["sequence"]),
        "contacts": len(plan.get("contacts") or []),
        "pushable": len(plan.get("pushable") or []),
        "unsupported_claims": len(plan.get("unsupported") or []),
        "touch_report": plan.get("touch_report"),
        "provider": report.get("provider"),
    }, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
