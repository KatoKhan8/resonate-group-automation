#!/usr/bin/env python3
"""The TRUE LinkedIn READY cohort, using the gate ladder's own semantics.

    py -3 scripts/linkedin_ready_truth.py

READ-ONLY. Writes nothing, anywhere.

WHY THIS EXISTS. `stage_linkedin_ready_cohort.ready_cohort()` screens on
`collision.account_policy` alone, so it staged four contacts and called them
ready. At activation, `executionguard` gate 4 refused one of them: a profile
the ACCOUNT check cleared had FOUR prior LinkedIn messages from one of our own
seats, sent 2026-07-18, never replied to. The account gate reads the EMAIL
estate; the LinkedIn conversation lives somewhere it never looks.

THE ARGUMENTS ARE THE POINT. `executionguard` calls

    collision.check_linkedin_profile(contact.get("linkedin"),
                                     contact.get("name"),
                                     expect_workspace=campaign["client"])

- the RAW `linkedin` value and the CONTACT NAME, against the client SLUG.
  Screening with the canonicalised URL, no name, or the numeric workspace id
  returns `clear` on a profile the guard refuses: the first two lose the
  match, and the numeric id raises "no inventoried LinkedIn seats". Measured
  all three ways on 2026-09-16. So this script calls it exactly as the guard
  does, because a pre-screen that asks a different question than the gate is a
  pre-screen that certifies people the gate will reject.

RETRIES BECAUSE THE PROVIDER IS FLAKY TODAY. `/campaign/GetAll` timed out
three times this session, once mid-create. A read that fails is retried; a
read that keeps failing is reported as `unknown` and the contact is HELD,
never passed.
"""
import hashlib
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import collision, liststaging, store                     # noqa: E402
from src.providers import load_env                                # noqa: E402

REQUIRED_APPROVER = "operator-control-arm"
REQUIRED_STEPS = ("li1", "li2", "li3", "li4", "li5")
CLIENT = "productive"
WORKSPACE = 10
ATTEMPTS = 4


def h12(value):
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:12]


def retry(fn, *args, **kw):
    """Provider reads only. Raises the last error if every attempt fails."""
    last = None
    for attempt in range(ATTEMPTS):
        try:
            return fn(*args, **kw)
        except Exception as exc:                  # provider transport only
            last = exc
            time.sleep(1.5 * (attempt + 1))
    raise last


def approved_contacts(recs=None):
    """Every contact whose li1-li5 carry operator-control-arm approval."""
    out = []
    for rec in (store.load() if recs is None else recs):
        cadence = rec.get("cadence") or {}
        for contact in rec.get("contacts") or []:
            steps = cadence.get(contact.get("key")) or {}
            ok = all(((steps.get(s) or {}).get("approval") or {}).get("by")
                     == REQUIRED_APPROVER for s in REQUIRED_STEPS)
            url = liststaging.canonical_profile_url(contact.get("linkedin"))
            if ok and url:
                out.append((rec, contact, url))
    return out


def verdicts():
    """(ready, held) - held carries the exact reason, per contact."""
    ready, held = [], []
    for rec, contact, url in approved_contacts():
        phash = h12(url.lower())
        row = {"hash": phash, "url": url, "rec": rec["id"],
               "key": contact.get("key")}
        try:
            account = retry(collision.check_account, rec.get("domain"),
                            expect_workspace=WORKSPACE)
            row["account"], why = collision.account_policy(account)
            row["account_why"] = why
        except Exception as exc:
            row["account"] = "unknown"
            row["account_why"] = f"{type(exc).__name__}: {exc}"
        try:
            # EXACTLY the guard's call. See the module docstring.
            verdict, detail = retry(
                collision.check_linkedin_profile, contact.get("linkedin"),
                contact.get("name"), expect_workspace=CLIENT)
            row["profile"] = verdict
            row["messages"] = (detail or {}).get("total_messages")
            row["replied"] = (detail or {}).get("they_replied")
            row["seat"] = (detail or {}).get("our_seat")
            row["last"] = (detail or {}).get("last_message_at")
        except Exception as exc:
            row["profile"] = "unknown"
            row["messages"] = None
            row["profile_why"] = f"{type(exc).__name__}: {exc}"

        if row["account"] == "allow" and row["profile"] == collision.CLEAR:
            ready.append(row)
        else:
            held.append(row)
    return ready, held


def main():
    load_env(os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "config", ".env"))
    ready, held = verdicts()
    print("=== APPROVED CONTACTS, BOTH COLLISION GATES ===")
    for row in ready + held:
        print(f"  {row['hash']}  account={row['account']:<7} "
              f"profile={str(row['profile']):<9} "
              f"msgs={row['messages']} replied={row.get('replied')} "
              f"seat={row.get('seat')}")
    print()
    print(f"LINKEDIN_READY_COHORT = {len(ready)}")
    for row in ready:
        print(f"  READY {row['hash']}  {row['url']}")
    print(f"HELD = {len(held)}")
    for row in held:
        why = row.get("profile_why") or row.get("account_why") or ""
        print(f"  HELD  {row['hash']}  account={row['account']} "
              f"profile={row['profile']} msgs={row['messages']}  {why[:70]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
