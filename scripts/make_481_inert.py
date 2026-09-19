#!/usr/bin/env python3
"""Bring campaign 481's nine `sending_paused` rows to the state 485 is already in.

    py -3 scripts/make_481_inert.py                # DRY RUN, reads only
    py -3 scripts/make_481_inert.py --live         # canary one, then the rest

## What is actually there, read 2026-09-19

    481  paused  23 leads  0 sent   senders [2736, 2737]
         14 `stopped`  +  9 `sending_paused`
    485  draft   10 leads  0 sent   senders [2736]
         10 `stopped` - already inert, and the state this brings 481 to

**481's nine `sending_paused` rows are EXACTLY campaign 487's nine live
leads.** Not nine of them, the same nine, confirmed lead by lead. 485's ten
are `stopped` and nine of those are the same people again.

`docs/THE-LOADED-GUN-IS-SMALLER-THAN-IT-LOOKED-2026-09-18.md` measured the
exposure as nine and recommended exactly this: a campaign-scoped
`EMAIL_STOP_LEAD`, which is SUPPORTED and unconditional, rather than
archiving, for which no route exists in `WRITE_ROUTES` at all and which could
break the collision proof that excludes those leads from their own accounts'
history.

This re-verified that reading independently and answered the question it did
not ask: **489's four overlapping leads are already `stopped` in 481**, so
the newer cohort carries no exposure at all. The nine are the whole of it.

## Why `sending_paused` is the hazard and `stopped` is not

A `paused` campaign schedules nothing, and `executionguard`'s `_NEVER_ACTIVATE`
refuses 481 and 485 whatever canonical row names them. So the gun has a safety.

But `sending_paused` is a RESUMABLE state. `stopped` is not - and the provider
measured that a stopped membership cannot be restarted by re-attaching the
same campaign (422), so it cannot be silently undone by a routine re-stage.
This replaces a guard that depends on our own code with one the provider
enforces.

Nothing is deleted. The rows stay, their history stays, and the collision
proof reads them exactly as it already reads 485's ten.

## The risk this canaries, which nobody has measured

`EMAIL_STOP_LEAD`'s evidence is that stopping one lead leaves its SIBLINGS in
the same campaign untouched, measured twice on 2026-09-13. That is a
within-campaign result.

**Whether a stop in campaign 481 touches the same lead's membership in
campaign 487 has never been measured**, and 487 is live and holds these exact
people. If the provider models the stop per LEAD rather than per
(lead, campaign), this operation would silently kill the live cohort - the
precise opposite of its purpose.

So: **one lead first, then read 487 in full, and refuse to continue unless
all ten of 487's rows are unchanged.** `bison.stop_lead`'s own blast-radius
check samples 481; it cannot see 487, so that check is added here.

It can only ever reduce what somebody receives. It cannot cause a send.
"""
import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.providers import ProviderError, bison, load_env  # noqa: E402

DORMANT = 481
LIVE = 487
NEWER = 489
EXPECT_PAUSED = 9


def snapshot(campaign_id):
    """`{lead_id: status}` straight from the provider."""
    return bison.membership(campaign_id)


def compare(before, after, label):
    """Every lead whose status moved. Empty is the only acceptable answer."""
    moved = {}
    for lead_id, was in before.items():
        now = after.get(lead_id)
        if now != was:
            moved[lead_id] = (was, now)
    for lead_id in after:
        if lead_id not in before:
            moved[lead_id] = (None, after[lead_id])
    if moved:
        print(f"  !! {label} MOVED: {moved}")
    else:
        print(f"  {label}: all {len(before)} rows unchanged")
    return moved


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--live", action="store_true",
                        help="perform the stop. Without it, nothing is written")
    args = parser.parse_args(argv)
    load_env(os.path.join(ROOT, "config", ".env"))

    print("=== BEFORE, provider truth ===")
    dormant = snapshot(DORMANT)
    live = snapshot(LIVE)
    newer = snapshot(NEWER)
    paused = sorted(k for k, v in dormant.items() if v == "sending_paused")

    print(f"  {DORMANT}: {len(dormant)} rows, {len(paused)} sending_paused")
    print(f"  {LIVE}: {len(live)} rows, "
          f"{sum(1 for v in live.values() if v == 'in_sequence')} in_sequence")
    print(f"  {NEWER}: {len(newer)} rows, "
          f"{sum(1 for v in newer.values() if v == 'in_sequence')} in_sequence")

    # The nine must be exactly 487's live cohort. If that has changed, the
    # analysis this script rests on is stale and it must not write.
    overlap = sorted(set(paused) & set(live))
    stray = sorted(set(paused) - set(live))
    print(f"\n  sending_paused that are LIVE in {LIVE}: {len(overlap)}")
    print(f"  sending_paused in NEITHER live campaign: {len(stray)} {stray}")
    print(f"  {NEWER} leads also in {DORMANT}: "
          f"{sorted(set(newer) & set(dormant))}")
    print(f"    their {DORMANT} status: "
          f"{sorted({dormant[k] for k in set(newer) & set(dormant)})}")

    if len(paused) != EXPECT_PAUSED:
        print(f"\nREFUSING: expected {EXPECT_PAUSED} sending_paused rows and "
              f"found {len(paused)}. The campaign changed under the analysis; "
              f"re-read it before writing.")
        return 2

    if not args.live:
        print(f"\nDRY RUN. Nothing was written. {len(paused)} rows would be "
              f"stopped in campaign {DORMANT}, one first, then the rest only "
              f"if all {len(live)} of {LIVE}'s rows are unchanged.")
        return 0

    canary, rest = paused[0], paused[1:]

    print(f"\n=== CANARY: stopping ONE lead ({canary}) in {DORMANT} ===")
    try:
        result = bison.stop_lead(DORMANT, [canary])
    except ProviderError as exc:
        print(f"  REFUSED by the provider layer: {exc}")
        return 3
    print(f"  stopped: {result['stopped']}")

    print(f"\n=== THE CHECK THAT MATTERS: is {LIVE} untouched? ===")
    moved = compare(live, snapshot(LIVE), f"campaign {LIVE}")
    moved_newer = compare(newer, snapshot(NEWER), f"campaign {NEWER}")
    if moved or moved_newer:
        print(f"\nSTOPPING HERE. A stop in {DORMANT} changed a membership in "
              f"a LIVE campaign, so the verb is per-lead and not per "
              f"(lead, campaign). {len(rest)} rows were NOT touched. This is "
              f"a provider finding and it needs writing down before anything "
              f"else happens.")
        return 4

    print(f"\n=== The remaining {len(rest)} ===")
    try:
        result = bison.stop_lead(DORMANT, rest)
    except ProviderError as exc:
        print(f"  REFUSED: {exc}")
        print(f"  The canary IS stopped. {len(rest)} rows remain "
              f"sending_paused and the campaign is partially converted.")
        return 5
    print(f"  stopped: {len(result['stopped'])} rows")

    print("\n=== AFTER, readback of all three ===")
    after_dormant = snapshot(DORMANT)
    still = sorted(k for k, v in after_dormant.items()
                   if v == "sending_paused")
    print(f"  {DORMANT}: {len(after_dormant)} rows, "
          f"{len(still)} still sending_paused {still}")
    compare(live, snapshot(LIVE), f"campaign {LIVE}")
    compare(newer, snapshot(NEWER), f"campaign {NEWER}")

    if still:
        print(f"\nPARTIAL: {len(still)} rows did not reach `stopped`.")
        return 6
    print(f"\n{DORMANT} is now inert: every row `stopped`, matching 485. "
          f"Nothing was deleted and no email was sent.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
