#!/usr/bin/env python3
"""TASK-147 supplementary: account collision for the 13 never-emailed
bison_lead_id contacts. These are effectively cold and need the same
account check as the cold cohort.
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.providers import bison  # noqa: E402
from src import collision  # noqa: E402

# The 13 never-emailed contacts and their domains (from the main run)
NEVER_EMAILED = [
    ("Jacob Faertz", "ogpartner.dk", 203715),
    ("Janie Karas", "px-6a518e690008", 203707),
    ("Rik De Veirman", "px-2a51e132bab4", 203711),
    ("Brian Price", "acqcom.com", 203708),
    ("Ranjan Damodar", "px-a8ca1565fdd1", 203709),
    ("Collette Savoie", "portsidemarketing.com", 203716),
    ("Al Scornaienchi", "agency59.ca", 203710),
    ("Paula Savage Hansen", "savagebrands.com", 203718),
    ("Michelle Payne-witten", "mischacommunications.com", 203713),
    ("Jennie Johnson", "mypersonalestatesale.com", 203714),
    ("Christine Xoinis", "ethoscreate.com", 203712),
    ("Jason Baker", "roaringmedia.co", 203717),
    ("Ray Kingman", "semcasting.com", 203719),
]


def main():
    ws = bison.bound_workspace()
    workspace_id = (ws or {}).get("id")
    print(f"Workspace: {workspace_id} ({(ws or {}).get('name', '?')})")
    print()

    domains_checked = {}
    allow = 0
    stop = 0
    hold = 0

    for name, domain, lead_id in NEVER_EMAILED:
        if domain not in domains_checked:
            try:
                account = collision.check_account(
                    domain, expect_workspace=workspace_id)
                verdict, why = collision.account_policy(account)
                domains_checked[domain] = (verdict, why)
            except collision.CollisionUnknown as e:
                domains_checked[domain] = (collision.HOLD, f"unreadable: {e}")
            except Exception as e:
                domains_checked[domain] = (collision.HOLD, f"error: {e}")
            time.sleep(0.2)

        verdict, why = domains_checked[domain]
        if verdict == collision.ALLOW:
            allow += 1
        elif verdict == collision.STOP:
            stop += 1
        else:
            hold += 1

        print(f"  {name:30} lead={lead_id} domain={domain:35} {verdict} - {why}")

    print()
    print(f"  SUMMARY:")
    print(f"    ALLOW: {allow}")
    print(f"    STOP:  {stop}")
    print(f"    HOLD:  {hold}")
    print(f"    Total: {allow + stop + hold}")


if __name__ == "__main__":
    main()
