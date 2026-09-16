#!/usr/bin/env python3
"""Fresh unbound list + the 4 collision-clear approved LinkedIn contacts.

    py -3 scripts/stage_linkedin_ready_cohort.py            # dry run
    py -3 scripts/stage_linkedin_ready_cohort.py --live      # create + stage

AUTHORIZED 2026-09-16: "APPROVED - enable heyreach.create_list", on top of the
standing grant to scale to "the largest cohort that ALREADY satisfies all
existing Resonate OS production gates".

WHY A NEW LIST. List 940797 is now bound to campaign 604869 - the bind is
`linkedInUserListId` at creation and there is no detach route - so
`assert_list_safe` correctly refuses adding anything more to it. And the one
contact staged there is HELD by `account_collision`: nine emails to that
account across two campaigns, one `stopped` for a reason the provider does not
record. That hold is correct and is not being worked around; those contacts
are simply not in this cohort.

THE COHORT IS THE ONE THE GATES ALLOW, not a number chosen here. Every
approved LinkedIn contact is re-checked against `collision.account_policy` at
run time, and only accounts whose verdict is neither hold nor stop are staged.
Measured when this was written: 4 contacts across 3 accounts.

SEND EXPOSURE OF THIS SCRIPT IS ZERO. It creates an empty list and adds leads
to it. An unbound list reaches nobody; the campaign that would give it an
audience is a separate authorized write, and activation is a separate gate
again.

A LIST IS PERMANENT. `create_list`'s docstring: this vendor documents no
delete for a list, so the name matters and this runs once.
"""
import argparse
import hashlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import collision, liststaging, providerwrites, store     # noqa: E402
from src.providers import heyreach                                # noqa: E402

LIST_NAME = "RESONATE - PRODUCTIVE LINKEDIN COHORT 2026-09-16"
REQUIRED_APPROVER = "operator-control-arm"
REQUIRED_STEPS = ("li1", "li2", "li3", "li4", "li5")
WORKSPACE = 10


def h12(value):
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:12]


def ready_cohort():
    """Approved contacts whose ACCOUNT passes collision. Re-read every run."""
    by_account, out, holds = {}, [], []
    for rec in store.load():
        cadence = rec.get("cadence") or {}
        for contact in rec.get("contacts") or []:
            steps = cadence.get(contact.get("key")) or {}
            approved = all(
                ((steps.get(s) or {}).get("approval") or {}).get("by")
                == REQUIRED_APPROVER for s in REQUIRED_STEPS)
            url = liststaging.canonical_profile_url(contact.get("linkedin"))
            if approved and url:
                by_account.setdefault(rec.get("domain"), []).append(
                    (rec, contact, url))
    for domain, entries in by_account.items():
        try:
            account = collision.check_account(domain, expect_workspace=WORKSPACE)
            verdict, why = collision.account_policy(account)
        except Exception as exc:
            holds.append((h12(domain), f"unreadable: {type(exc).__name__}"))
            continue
        if verdict in ("hold", "stop"):
            holds.append((h12(domain), f"{verdict}: {why[:60]}"))
            continue
        out.extend(entries)
    return out, holds


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--live", action="store_true",
                        help="create the list and stage; omit for a dry run")
    args = parser.parse_args(argv)

    cohort, holds = ready_cohort()
    print("=== READY COHORT, RECOMPUTED FROM THE GATES ===")
    for rec, contact, url in cohort:
        print(f"  READY  rec={h12(rec['id'])} contact={h12(contact.get('key'))} "
              f"profile={h12(url.lower())}")
    for account, why in holds:
        print(f"  HELD   acct={account}  {why}")
    print(f"\n  HEYREACH_READY_COHORT = {len(cohort)}")
    if not cohort:
        print("\nREFUSED: no approved contact passes account collision.")
        return 2

    if not args.live:
        print("\nDRY RUN: no list was created and nothing was staged.")
        print("Re-run with --live.")
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
                  f"permanent on this provider. Reuse it rather than making "
                  f"another.")
        return 3
    list_id = created.get("id")
    print(f"  list id            : {list_id}")
    print(f"  campaignIds        : "
          f"{(heyreach.list_by_id(list_id) or {}).get('campaignIds')}")

    # 2. THE LEADS, one at a time, through the staging path. A refusal on one
    #    must not stop the rest - the operator's instruction, and the reason
    #    this loops rather than batching.
    print("\n=== 2. STAGE THE COHORT ===")
    staged, refused = [], []
    for rec, contact, url in cohort:
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
            refused.append((h12(url.lower()), f"{type(exc).__name__}"))
            print(f"  REFUSED  {h12(url.lower())}  {type(exc).__name__}: "
                  f"{str(exc)[:90]}")

    members, total = heyreach.list_leads(list_id)
    after = heyreach.list_by_id(list_id) or {}
    print(f"\n=== 3. PROVIDER TRUTH ===")
    print(f"  list {list_id}: campaignIds={after.get('campaignIds')} "
          f"leads={total}")
    for m in members:
        print("    member:", h12(str(liststaging.canonical_profile_url(
            m.get("profile_url")) or "").lower()))
    print(f"\n  staged  : {len(staged)}")
    print(f"  refused : {len(refused)}")
    print("\nThe list is UNBOUND, so it reaches nobody. Binding it to a "
          "campaign is the next authorized write.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
