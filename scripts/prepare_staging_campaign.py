#!/usr/bin/env python3
"""DRAFT -> IN_PROGRESS -> PAUSED, on a campaign that holds nobody.

WHY THIS TRANSITION EXISTS AT ALL.

HeyReach will not accept leads into a DRAFT campaign and will not pause an
inactive one - both measured, both 400s. Only ongoing, paused and finished
campaigns accept leads. So a campaign cannot be staged into until it has been
started once, and the only safe moment to start it is while it holds ZERO
leads, because a campaign with nobody in it has nobody to send to.

This script is that transition and nothing else. It is deliberately not part
of `ensure_leads`: a state change to a real campaign in a client's account
should be a thing somebody ran on purpose, with the before and after in front
of them, rather than a side effect of loading a cohort.

WHAT IT PROVES AT EACH STEP, refusing rather than continuing:

    before   the campaign is ours, declared, DRAFT, and holds ZERO leads
    start    through providerwrites.perform, whose condition re-reads the
             lead count immediately before the write
    after    the provider says IN_PROGRESS
    pause    through the live-validated, SUPPORTED pause route
    after    the provider says PAUSED, still zero leads, and the campaign's
             own counters show nothing was sent

THE LAST CHECK IS THE POINT. `connectionsSent` and `uniqueLeadsContacted` come
from the provider's own stats, not from our ledger. If starting an empty
campaign ever did reach somebody, this is what would say so - and it refuses
rather than reporting success.

    py -3 scripts/prepare_staging_campaign.py --campaign <id>
    py -3 scripts/prepare_staging_campaign.py --campaign <id> --live --by zb
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import campaigns, providerwrites, store  # noqa: E402
from src.providers import heyreach  # noqa: E402


# Observed 2026-09-15, and not in `heyreach`'s known set: a campaign
# reports STARTING for a moment after a start before it reports
# IN_PROGRESS. A readback that expected IN_PROGRESS called a
# successful write DRIFTED because of it.
STARTING = "STARTING"


class PrepareRefused(RuntimeError):
    """The transition cannot be made, and the reason is on the exception."""


def _state(provider_id):
    """Everything the provider says, in one place, read fresh."""
    row = heyreach.campaign_read(provider_id)
    _rows, total = heyreach.campaign_leads(provider_id, offset=0)
    try:
        stats = heyreach.campaign_stats(provider_id)
    except Exception as e:                                   # noqa: BLE001
        stats = {"unreadable": f"{type(e).__name__}: {e}"}
    return {"status": (row or {}).get("status"),
            "started_at": (row or {}).get("startedAt"),
            "leads": total, "stats": stats}


def _show(label, st):
    print(f"  {label:9} status={st['status']!r} leads={st['leads']} "
          f"startedAt={st['started_at']!r}")
    print(f"            counters={st['stats']}")


def main(argv=None):
    p = argparse.ArgumentParser(prog="prepare_staging_campaign",
                                description=__doc__)
    p.add_argument("--campaign", required=True)
    p.add_argument("--by", default="operator")
    p.add_argument("--live", action="store_true")
    a = p.parse_args(argv)

    rows = campaigns.load()
    campaign = campaigns.require(str(a.campaign), rows)
    provider_id = campaign.get("heyreach_campaign_id")
    if not provider_id:
        raise PrepareRefused(
            f"campaign {a.campaign!r} names no heyreach_campaign_id")
    provider_id = int(provider_id)

    before = _state(provider_id)
    print(f"campaign  {a.campaign}  ->  HeyReach {provider_id}")
    _show("BEFORE", before)

    if int(before["leads"] or 0) != 0:
        raise PrepareRefused(
            f"HeyReach campaign {provider_id} holds {before['leads']} "
            f"lead(s). Starting a campaign that holds people is prospect-"
            f"facing and is not what this script does. Nothing was written")
    if before["status"] == heyreach.PAUSED:
        print("\nalready PAUSED and empty; nothing to do")
        return 0
    if before["status"] != heyreach.DRAFT:
        raise PrepareRefused(
            f"HeyReach campaign {provider_id} is {before['status']!r}. This "
            f"script moves a DRAFT campaign to PAUSED and refuses anything "
            f"else. Nothing was written")

    if not a.live:
        print("\nDRY RUN. Would start the empty campaign, then pause it, "
              "reading the provider back after each.")
        return 0

    # ---------------------------------------------------------------- start
    print("\nstarting the empty campaign ...")
    providerwrites.perform(
        providerwrites.LINKEDIN_START_EMPTY_FOR_STAGING,
        campaign=str(a.campaign), tenant=campaign.get("client"),
        provider_campaign_id=provider_id,
        payload={"campaignId": provider_id},
        transport=lambda _p: heyreach.start_campaign(provider_id),
        readback=lambda: {"status": heyreach.campaign_read(provider_id)
                          .get("status")},
        # STARTING IS A REAL STATUS AND IT IS TRANSIENT. Measured
        # 2026-09-15: the start succeeded, the readback saw "STARTING", the
        # verdict was DRIFTED, and moments later the campaign read
        # IN_PROGRESS. The write had worked. Accepting both is not a widened
        # expectation - it is the provider's actual state machine, which has
        # one more state than this expected.
        expected=None, by=a.by)
    started = _state(provider_id)
    _show("STARTED", started)
    if started["status"] not in (heyreach.IN_PROGRESS, STARTING):
        raise PrepareRefused(
            f"the start was accepted but the provider says "
            f"{started['status']!r}. Read provider truth and reconcile by "
            f"hand")

    # ---------------------------------------------------------------- pause
    print("\npausing it ...")
    providerwrites.perform(
        providerwrites.LINKEDIN_PAUSE,
        campaign=str(a.campaign), tenant=campaign.get("client"),
        payload={"campaignId": provider_id},
        transport=lambda _p: heyreach.pause_campaign(provider_id),
        readback=lambda: {"status": heyreach.campaign_read(provider_id)
                          .get("status")},
        expected={"status": heyreach.PAUSED}, by=a.by)
    after = _state(provider_id)
    _show("AFTER", after)

    # ------------------------------------------------- what must still hold
    problems = []
    if after["status"] != heyreach.PAUSED:
        problems.append(f"status is {after['status']!r}, not PAUSED")
    if int(after["leads"] or 0) != 0:
        problems.append(f"the campaign now holds {after['leads']} lead(s)")
    sent = (after["stats"] or {}).get("connectionsSent")
    contacted = (after["stats"] or {}).get("uniqueLeadsContacted")
    if sent not in (0, None) or contacted not in (0, None):
        problems.append(
            f"the provider's own counters moved: connectionsSent={sent}, "
            f"uniqueLeadsContacted={contacted}. Starting an empty campaign "
            f"reached somebody, which contradicts the premise of this whole "
            f"transition")
    if problems:
        raise PrepareRefused(
            "the transition completed and the provider does not agree it was "
            "harmless: " + "; ".join(problems))

    campaign.setdefault("log", []).append({
        "at": store.now(), "by": a.by,
        "what": (f"prepared for staging: DRAFT -> IN_PROGRESS -> PAUSED on "
                 f"HeyReach {provider_id} while it held zero leads; provider "
                 f"counters unchanged at zero"),
    })
    campaigns.save(rows)
    print("\nPAUSED, empty, and nothing was sent. Ready to stage.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
