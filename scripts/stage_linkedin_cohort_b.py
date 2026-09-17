#!/usr/bin/env python3
"""A second unbound list holding the THREE contacts both collision gates clear.

    py -3 scripts/stage_linkedin_cohort_b.py            # dry run
    py -3 scripts/stage_linkedin_cohort_b.py --live      # create + stage

WHY A SECOND LIST. List 943957 was staged from `account_policy` alone and holds
FOUR. At activation, `executionguard` gate 4 refused one of them: a profile the
account gate cleared carries FOUR prior LinkedIn messages from our own seat
208242, sent 2026-07-18, never replied to. The refusal is correct and is not
worked around - that contact is dropped, with the reason recorded.

AND WHY THE LIST CANNOT SIMPLY BE EDITED. HeyReach's `WRITE_ROUTES` has
`/list/CreateEmptyList` and `/list/AddLeadsToListV2` and NO removal route, and
943957 is now bound to campaign 605487 so `assert_list_safe` refuses further
adds to it anyway. A list whose membership is wrong can only be replaced.

THE COHORT IS THE ONE BOTH GATES ALLOW. `linkedin_ready_truth.verdicts()`
screens with the SAME call `executionguard` makes - the raw `linkedin` value,
the contact name, the client slug - so this cannot stage somebody the guard
will later refuse. Screening any other way returns `clear` on a touched
profile; measured three ways on 2026-09-16.

SEND EXPOSURE OF THIS SCRIPT IS ZERO. It creates an empty list and adds leads.
An unbound list reaches nobody.

A LIST IS PERMANENT. This vendor documents no list delete, so the name matters
and this runs once.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src import liststaging, providerwrites, store              # noqa: E402
from src.providers import heyreach, load_env                    # noqa: E402

from linkedin_ready_truth import h12, verdicts                  # noqa: E402

LIST_NAME = "RESONATE - PRODUCTIVE LINKEDIN COHORT 2026-09-16 B"


def cohort():
    """(rec, contact, url) for every contact both gates clear."""
    ready, held = verdicts()
    by_id = {rec["id"]: rec for rec in store.load()}
    out = []
    for row in ready:
        rec = by_id.get(row["rec"])
        contact = None
        for candidate in (rec.get("contacts") or []):
            if candidate.get("key") == row["key"]:
                contact = candidate
                break
        if rec is not None and contact is not None:
            out.append((rec, contact, row["url"]))
    return out, held


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--live", action="store_true",
                        help="create the list and stage; omit for a dry run")
    args = parser.parse_args(argv)

    load_env(os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "config", ".env"))

    ready, held = cohort()
    print("=== READY COHORT, BOTH COLLISION GATES, RECOMPUTED ===")
    for rec, contact, url in ready:
        print(f"  READY  profile={h12(url.lower())}")
    for row in held:
        print(f"  HELD   profile={row['hash']}  account={row['account']} "
              f"profile={row['profile']} msgs={row['messages']}")
    print(f"\n  LINKEDIN_READY_COHORT = {len(ready)}")
    if not ready:
        print("\nREFUSED: no approved contact passes both collision gates.")
        return 2

    if not args.live:
        print("\nDRY RUN: no list was created and nothing was staged.")
        return 0

    # 1. THE LIST. Empty, therefore inert.
    print("\n=== 1. CREATE THE UNBOUND LIST ===")
    created = {}

    def transport(payload):
        created.update(heyreach.create_list(payload["name"]) or {})
        return created

    try:
        providerwrites.perform(
            providerwrites.LINKEDIN_CREATE_LIST,
            provider_campaign_id=None, campaign=None, tenant="productive",
            payload={"name": LIST_NAME},
            transport=transport,
            readback=lambda: {"campaignIds": (heyreach.list_by_id(
                created.get("id")) or {}).get("campaignIds") or []},
            expected={"campaignIds": []}, by="operator")
    except Exception as exc:
        print(f"  REFUSED / FAILED: {type(exc).__name__}: {exc}")
        if created.get("id"):
            print(f"  A LIST WAS CREATED: {created['id']} - lists are "
                  f"permanent here. Reuse it rather than making another.")
        return 3
    list_id = created.get("id")
    print(f"  list id            : {list_id}")

    # 2. THE LEADS, one at a time. A refusal on one must not stop the rest.
    print("\n=== 2. STAGE THE COHORT ===")
    staged, refused = [], []
    for rec, contact, url in ready:
        parts = str(contact.get("name") or "").strip().split()
        row = {"linkedin_url": url,
               "first_name": parts[0] if parts else "",
               "last_name": " ".join(parts[1:]) if len(parts) > 1 else "",
               "company": str(rec.get("company") or "").strip(),
               "title": str(contact.get("title") or "").strip()}
        try:
            liststaging.stage_lead(
                list_id, row,
                lambda p, _row=row: heyreach.add_leads_to_list(
                    p["listId"], [_row]))
            staged.append(h12(url.lower()))
            print(f"  STAGED   {h12(url.lower())}")
        except Exception as exc:
            refused.append((h12(url.lower()), type(exc).__name__))
            print(f"  REFUSED  {h12(url.lower())}  {type(exc).__name__}: "
                  f"{str(exc)[:90]}")

    members, total = heyreach.list_leads(list_id)
    after = heyreach.list_by_id(list_id) or {}
    print("\n=== 3. PROVIDER TRUTH ===")
    print(f"  list {list_id}: campaignIds={after.get('campaignIds')} "
          f"leads={total}")
    for m in members:
        print("    member:", h12(str(liststaging.canonical_profile_url(
            m.get("profile_url")) or "").lower()))
    print(f"\n  staged  : {len(staged)}   refused : {len(refused)}")
    print("\nThe list is UNBOUND, so it reaches nobody.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
