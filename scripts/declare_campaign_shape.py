#!/usr/bin/env python3
"""Fill in a canonical campaign row's provider binding, FROM PROVIDER TRUTH.

WHY THIS EXISTS.

`configdiff.approved_heyreach` compares what the canonical row DECLARES
against what the provider HOLDS. Campaign 599020's row declared almost none of
it: no `org_unit`, no `heyreach_list_id`, no `provider_delays`, no
`provider_status_expected`, and - because the concept did not exist until the
first add-lead attempt exposed the need - no `provider_note` and no
`provider_actions`.

A row that declares nothing cannot match anything. Five required fields were
mismatching against a campaign that was, in fact, correctly configured.

WHY READING THE PROVIDER TO FILL THEM IN IS NOT CIRCULAR.

It would be, if this ran unattended. A differ whose approved side is copied
from the provider proves only that the provider agrees with itself, and
`configdiff`'s own rule is that nothing there may edit either side to make
them agree.

So this is a ONE-TIME OPERATOR ACT with three properties that keep it honest:

  - it PRINTS the provider's values and what the row currently says, and
    writes nothing without `--live`, so a person sees exactly what is being
    adopted before it is adopted;
  - it refuses to touch a campaign that is not DRAFT. A campaign that can send
    is one whose shape a person must state deliberately, not adopt;
  - it is recorded in the campaign's own log with who ran it and when, and it
    MOVES THE FINGERPRINT - `campaigns.material` carries all of these fields -
    so any approval that predates the declaration is invalidated by it rather
    than inherited through it.

After this runs once, the row is the statement and the provider is the check.
Drift in either direction fails the diff, which is the point.

    py -3 scripts/declare_campaign_shape.py --campaign productive-linkedin-production-v1
    py -3 scripts/declare_campaign_shape.py --campaign ... --live --by zb
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import campaigns, configdiff, store  # noqa: E402
from src.providers import heyreach  # noqa: E402


class DeclareRefused(RuntimeError):
    """The row cannot be completed, and the reason is on the exception."""


# What this may adopt from a provider read, and where each comes from.
# Deliberately explicit rather than a loop over the provider dict: a field
# nobody listed here is a field nobody decided to adopt.
ADOPTED = (
    ("org_unit", "org_unit"),
    ("heyreach_list_id", "list_id"),
    ("provider_status_expected", "status"),
    ("provider_note", "note"),
    ("provider_actions", "actions"),
    ("provider_delays", "delays"),
)


def main(argv=None):
    p = argparse.ArgumentParser(prog="declare_campaign_shape",
                                description=__doc__)
    p.add_argument("--campaign", required=True)
    p.add_argument("--by", default="operator")
    p.add_argument("--live", action="store_true")
    a = p.parse_args(argv)

    rows = campaigns.load()
    campaign = campaigns.require(str(a.campaign), rows)
    provider_id = campaign.get("heyreach_campaign_id")
    if not provider_id:
        raise DeclareRefused(
            f"campaign {a.campaign!r} names no heyreach_campaign_id, so there "
            f"is no provider shape to read")

    # DRAFT ONLY, and read at the moment of the write rather than trusted from
    # the row. The same predicate the add-lead gate uses.
    if not heyreach.campaign_cannot_send(provider_id):
        raise DeclareRefused(
            f"HeyReach campaign {provider_id} is not proven unable to send. "
            f"The shape of a campaign that can send is a thing a person "
            f"states deliberately, not one this script adopts")

    provider = configdiff.provider_heyreach(str(provider_id))
    print(f"campaign        {a.campaign}  ->  HeyReach {provider_id}")
    print(f"provider status {provider.get('status')}")
    print()

    changes = []
    for field, source in ADOPTED:
        value = provider.get(source)
        if isinstance(value, frozenset):
            value = sorted(value)
        elif isinstance(value, tuple):
            value = [list(v) if isinstance(v, (tuple, list)) else v
                     for v in value]
        if value in (None, "", [], configdiff.UNVERIFIABLE):
            print(f"  SKIP  {field:26} provider says {value!r}; nothing to "
                  f"adopt")
            continue
        current = campaign.get(field)
        mark = "same" if current == value else ("SET " if current in
                                                (None, "", []) else "CHANGE")
        print(f"  {mark:6} {field:26} {json.dumps(current)[:40]:42} "
              f"-> {json.dumps(value)[:60]}")
        if current != value:
            changes.append((field, value))

    if not changes:
        print("\nnothing to declare; the row already states the provider's "
              "shape")
        return 0

    before = campaigns.fingerprint(campaign)
    if not a.live:
        print(f"\nDRY RUN. {len(changes)} field(s) would be declared.")
        print(f"fingerprint would move from {before} - any approval taken "
              f"before the declaration would stop being current, which is "
              f"the intended consequence.")
        return 0

    for field, value in changes:
        campaign[field] = value
    campaign.setdefault("log", []).append({
        "at": store.now(), "by": a.by,
        "what": ("declared the provider-side shape from a readback of "
                 f"HeyReach {provider_id}: "
                 + ", ".join(f for f, _v in changes)),
    })
    after = campaigns.fingerprint(campaign)
    campaigns.save(rows)
    print(f"\ndeclared {len(changes)} field(s)")
    print(f"fingerprint {before} -> {after}")
    if before != after and campaign.get("approval"):
        print("the campaign's approval predates this declaration and is no "
              "longer current. Re-approve before launching.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
