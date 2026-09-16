#!/usr/bin/env python3
"""TASK-175: enumerate every list the HeyReach account can see.

Read-only against the provider. Answers:
  1. Every list: id, name, lead count, created date, attachment state
  2. How attachment is discovered (endpoint and field)
  3. Whether a list can be attached to >1 campaign, and vice versa
  4. Recommendation for the canary's staging list
  5. The binding step: which provider operation performs it

Probes /list/GetAll (paged), /list/GetById (per list), and
/campaign/GetById (per attached campaign). Also pages /campaign/GetAll
to cross-reference which campaigns hold lists and to identify Resonate's
campaign (599020).
"""
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.providers.heyreach import (
    BASE, headers, lists, list_by_id, campaign_read, campaigns,
    campaign_by_id, MAX_PAGE, LIST_FIELDS, CAMPAIGN_FIELDS,
)
from src.providers import request, ok

RESONATE_CAMPAIGN_ID = 599020
RESONATE_LIST_IDS = (933603, 940797)


def ts_to_iso(ts):
    """Convert a millisecond timestamp to ISO format, or return as-is."""
    if not ts:
        return None
    try:
        return datetime.fromtimestamp(int(ts) / 1000, tz=timezone.utc).isoformat()
    except (TypeError, ValueError, OSError):
        return str(ts)


def page_all_lists():
    """Every list the account can see, paged."""
    all_items = []
    offset = 0
    total = None
    for page_num in range(20):
        items, count = lists(offset=offset, limit=MAX_PAGE)
        if count is not None:
            total = count
        all_items.extend(items)
        offset += len(items)
        if not items or (total is not None and offset >= int(total)):
            break
    return all_items, total


def page_all_campaigns():
    """Every campaign the account can see, paged. Bounded at 10 pages."""
    all_items = []
    offset = 0
    total = None
    for page_num in range(10):
        items, count = campaigns(offset=offset, limit=MAX_PAGE)
        if count is not None:
            total = count
        all_items.extend(items)
        offset += len(items)
        if not items or (total is not None and offset >= int(total)):
            break
    return all_items, total


def main():
    stamp = datetime.now(timezone.utc).isoformat()
    print("=" * 72)
    print(f"TASK-175: List estate enumeration — {stamp}")
    print("=" * 72)

    # ---- Part 1: enumerate all lists
    print("\n### PART 1: All lists visible to the account ###\n")
    all_lists, list_total = page_all_lists()
    print(f"Total lists reported by provider: {list_total}")
    print(f"Lists fetched: {len(all_lists)}")
    print()

    list_details = []
    for lst in all_lists:
        list_id = lst.get("id")
        name = lst.get("name")
        list_type = lst.get("listType")
        item_count = lst.get("totalItemsCount")
        campaign_ids = lst.get("campaignIds") or []
        creation_time = ts_to_iso(lst.get("creationTime"))

        detail = {
            "id": list_id,
            "name": name,
            "listType": list_type,
            "totalItemsCount": item_count,
            "campaignIds": campaign_ids,
            "creationTime": creation_time,
            "is_bound": len(campaign_ids) > 0,
            "bound_campaigns": [],
        }

        # For each attached campaign, read its status
        for cid in campaign_ids:
            try:
                camp = campaign_read(cid)
                detail["bound_campaigns"].append({
                    "campaignId": cid,
                    "campaignName": camp.get("name"),
                    "campaignStatus": camp.get("status"),
                    "campaignListId": camp.get("linkedInUserListId"),
                    "campaignListName": camp.get("linkedInUserListName"),
                })
            except Exception as e:
                detail["bound_campaigns"].append({
                    "campaignId": cid,
                    "error": f"{type(e).__name__}: {e}",
                })

        list_details.append(detail)

        bound_str = (f"BOUND to {len(campaign_ids)} campaign(s): "
                     f"{campaign_ids}" if campaign_ids else "UNBOUND")
        owner = "RESONATE" if list_id in RESONATE_LIST_IDS else "CLIENT"
        print(f"  List {list_id}: {name!r}")
        print(f"    type={list_type}, leads={item_count}, "
              f"created={creation_time}")
        print(f"    {bound_str}  [{owner}]")
        for bc in detail["bound_campaigns"]:
            if "error" in bc:
                print(f"      campaign {bc['campaignId']}: {bc['error']}")
            else:
                print(f"      campaign {bc['campaignId']}: "
                      f"{bc['campaignName']!r} status={bc['campaignStatus']}")
        print()

    # ---- Part 2: campaign cross-reference
    print("\n### PART 2: Campaign cross-reference ###\n")
    all_camps, camp_total = page_all_campaigns()
    print(f"Total campaigns reported by provider: {camp_total}")
    print(f"Campaigns fetched: {len(all_camps)}")
    print()

    # Find campaigns that reference a list
    campaigns_with_lists = []
    for c in all_camps:
        list_id = c.get("linkedInUserListId")
        if list_id:
            campaigns_with_lists.append({
                "campaignId": c.get("id"),
                "campaignName": c.get("name"),
                "status": c.get("status"),
                "linkedInUserListId": list_id,
                "linkedInUserListName": c.get("linkedInUserListName"),
                "is_resonate": str(c.get("id")) == str(RESONATE_CAMPAIGN_ID),
            })

    print(f"Campaigns holding a list: {len(campaigns_with_lists)}")
    for cw in campaigns_with_lists:
        tag = " ** RESONATE **" if cw["is_resonate"] else ""
        print(f"  Campaign {cw['campaignId']}: {cw['campaignName']!r} "
              f"status={cw['status']} list={cw['linkedInUserListId']} "
              f"({cw['linkedInUserListName']!r}){tag}")
    print()

    # ---- Part 3: Resonate campaign detail
    print("\n### PART 3: Resonate campaign 599020 detail ###\n")
    try:
        rc = campaign_read(RESONATE_CAMPAIGN_ID)
        print(f"  Campaign {RESONATE_CAMPAIGN_ID}:")
        for k, v in sorted(rc.items()):
            print(f"    {k} = {v!r}")
    except Exception as e:
        print(f"  FAILED to read campaign {RESONATE_CAMPAIGN_ID}: {e}")
    print()

    # ---- Part 4: Known list detail via GetById
    print("\n### PART 4: Known list detail via /list/GetById ###\n")
    for lid in RESONATE_LIST_IDS:
        try:
            detail = list_by_id(lid)
            print(f"  List {lid} (GetById):")
            for k, v in sorted(detail.items()):
                print(f"    {k} = {v!r}")
        except Exception as e:
            print(f"  List {lid}: FAILED - {e}")
        print()

    # ---- Part 5: Raw JSON dump for analysis
    print("\n### PART 5: Raw list data (JSON) ###\n")
    print(json.dumps(list_details, indent=2, ensure_ascii=False, default=str))

    print("\n" + "=" * 72)
    print(f"DONE at {datetime.now(timezone.utc).isoformat()}")
    print("=" * 72)


if __name__ == "__main__":
    main()
