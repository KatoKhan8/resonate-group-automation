#!/usr/bin/env python3
"""Pause and resume 487, to test whether the scheduler re-enrols on resume.

    py -3 scripts/nudge_487_scheduler.py            # dry run
    py -3 scripts/nudge_487_scheduler.py --live      # pause, verify, resume

EXPOSURE IS UNCHANGED, AND THAT IS THE ARGUMENT FOR DOING IT. The campaign
holds the same ten approved leads, the same approved CONTROL copy, the same two
senders. Nobody new can be reached and nobody has been reached yet - 0 sent, 0
queue rows. Resuming a campaign that has sent nothing to ten people it was
already authorized to send to adds no exposure; it only changes WHEN.

WHY IT MIGHT WORK. 487 has been ACTIVE since 08:07Z and its `updated_at` has
not moved since - EmailBison's scheduler has not touched the record in three
and a half hours of an open 09:00-17:00 window. The standing hypothesis is that
the provider assigns "new leads for the day" on a cycle at or near the window
opening, and 487 was activated at 10:07 local, after it. A resume is the event
that made it active in the first place, so a fresh one is the cheapest probe of
whether enrolment happens on that transition rather than on a timer.

WHY IT MIGHT NOT, AND WHAT THAT WOULD TELL US. If the assignment is purely
time-based, this changes nothing and the first send is tomorrow at 09:00. That
is still a result: it removes the transition from the list of things that could
be wrong, and leaves exactly one hypothesis standing to be confirmed or killed
tomorrow.

WHAT IS RULED OUT ALREADY, so this is not a shot in the dark: the schedule
window (three ACTIVE campaigns with 173k sends read the same "Not Started"),
lead verification status (451's delivered lead reads `unverified` too), sender
health and caps, lead enrolment (all ten `in_sequence`), the `wait_in_days`
convention, and a field-by-field diff against campaign 327 - which is sending -
that found only our deliberately lower caps, `plain_text` and auto-reply stats.

BOTH VERBS ARE AUTHORIZED AND BOTH ARE READ BACK. `bison.pause_campaign` is a
stopping verb - it can only ever mean somebody receives less.
`bison.resume_campaign` is the one route here that reaches a person, takes an
`expect_leads` containment that refuses when the provider disagrees, and its
condition resolves to this campaign and no other.
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import providerwrites                                  # noqa: E402
from src.providers import bison, load_env                       # noqa: E402

CANONICAL = "productive-email-control-v3"
PROVIDER_ID = 487
EXPECT_LEADS = 10


def snapshot(label):
    row = bison.campaign(PROVIDER_ID) or {}
    queue = bison.scheduled_emails(PROVIDER_ID) or []
    print(f"  {label:9s} status={str(row.get('status')):8s} "
          f"sent={row.get('emails_sent')} "
          f"contacted={row.get('total_leads_contacted')} "
          f"queue={len(queue)} updated_at={row.get('updated_at')}")
    return row, queue


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--settle", type=float, default=20.0,
                        help="seconds to wait after resume before reading")
    args = parser.parse_args(argv)

    load_env(os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "config", ".env"))

    print("=== BEFORE ===")
    row, queue = snapshot("before")
    problems = []
    if str(row.get("status") or "").lower() != "active":
        problems.append(f"campaign is {row.get('status')!r}, not active; this "
                        f"script only nudges a running campaign")
    if int(row.get("emails_sent") or 0):
        problems.append(f"campaign has already sent "
                        f"{row.get('emails_sent')}; a nudge is for a campaign "
                        f"that has sent NOTHING, so that resuming adds no "
                        f"exposure anybody has not already had")
    if int(row.get("total_leads") or 0) != EXPECT_LEADS:
        problems.append(f"campaign holds {row.get('total_leads')} leads, "
                        f"expected {EXPECT_LEADS}")
    if problems:
        print("\nREFUSED. Nothing was changed:")
        for problem in problems:
            print(f"  - {problem}")
        return 2
    print("  preflight PASS - same 10 leads, same copy, 0 sent, so the only "
          "thing this can change is WHEN")

    if not args.live:
        print("\nDRY RUN: nothing was paused or resumed.")
        return 0

    print("\n=== 1. PAUSE ===")
    try:
        providerwrites.perform(
            providerwrites.EMAIL_PAUSE,
            provider_campaign_id=str(PROVIDER_ID),
            campaign=CANONICAL, tenant="productive",
            payload={"campaign_id": PROVIDER_ID},
            transport=lambda p: bison.pause_campaign(p["campaign_id"]),
            readback=lambda: {"status": str(
                (bison.campaign(PROVIDER_ID) or {}).get("status") or "")},
            expected={"status": "paused"}, by="operator")
    except Exception as exc:
        print(f"  REFUSED / FAILED: {type(exc).__name__}: {exc}")
        print("  READ PROVIDER TRUTH: bison.campaign(487)")
        return 3
    snapshot("paused")

    print("\n=== 2. RESUME ===")
    try:
        providerwrites.perform(
            providerwrites.EMAIL_ACTIVATE,
            provider_campaign_id=str(PROVIDER_ID),
            campaign=CANONICAL, tenant="productive",
            payload={"campaign_id": PROVIDER_ID,
                     "expect_leads": EXPECT_LEADS},
            transport=lambda p: bison.resume_campaign(
                p["campaign_id"], expect_leads=p["expect_leads"]),
            readback=lambda: {"status": str(
                (bison.campaign(PROVIDER_ID) or {}).get("status") or "")},
            expected=None, by="operator")
    except Exception as exc:
        print(f"  REFUSED / FAILED: {type(exc).__name__}: {exc}")
        print("\n  THE CAMPAIGN MAY BE LEFT PAUSED. That is the safe side, but "
              "it is not where it should stay - read provider truth and "
              "resume it deliberately:")
        print("    py -3 -c \"import sys;sys.path.insert(0,'.');"
              "from src.providers import load_env,bison;"
              "load_env('config/.env');print(bison.campaign(487))\"")
        return 3

    print(f"\n=== 3. AFTER (settling {args.settle:.0f}s) ===")
    time.sleep(args.settle)
    after, queue_after = snapshot("after")
    moved = (after.get("updated_at") != row.get("updated_at"))
    print(f"\n  updated_at moved : {moved}")
    print(f"  queue rows       : {len(queue)} -> {len(queue_after)}")
    if len(queue_after) > len(queue):
        print("  RESULT: the resume transition DID enrol sends. The "
              "hypothesis that assignment is purely time-based is wrong.")
    else:
        print("  RESULT: no change. The transition is not what enrols, so the "
              "time-based hypothesis stands and tomorrow's 09:00 window is "
              "the test that settles it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
