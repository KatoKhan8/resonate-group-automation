#!/usr/bin/env python3
"""Ping every provider with the cheapest call it offers. Run before a batch.

BUILD-SPEC section 10, phase 3, extended to seven providers.

Three outcomes, and the third one matters:

  ok       a free, read-only call succeeded
  FAIL     configured but the provider refused, or nothing is configured
  SKIP     deliberately not called, because the call would cost money or
           because the wire contract is not confirmed

Nothing here spends a credit to turn a provider green. Reoon is configuration
only by default, because its only endpoint verifies an address; Deliverable is
the same until its contract is confirmed.

  python -m src.check
  python -m src.check --live-reoon      spends one Reoon credit, deliberately
"""
import argparse

from . import contamination
from .providers import (aiark, apify, bison, blitz, contactout, deliverable,
                        heyreach, reoon, slack)

PROVIDERS = ("ContactOut", "Blitz", "AI Ark", "Reoon", "Deliverable", "EmailBison",
             "HeyReach", "Apify", "Slack")


def run(live_reoon=False):
    """Every provider, in a fixed order, each with its own free health call."""
    return [
        contactout.check(),          # GET /stats, free
        blitz.check(),               # GET /v2/account/key-info, 0 records
        aiark.check(),               # tools/list, free
        reoon.check(live=live_reoon),  # configuration only unless asked
        deliverable.check(),         # configuration only: contract unconfirmed
        bison.check(),               # GET /campaigns, read-only
        heyreach.check(),            # GET /auth/CheckApiKey
        apify.check(),               # GET /users/me, read-only
        # Slack was absent from this sweep while the documentation counted
        # eight providers, so `python -m src.check` never touched the one
        # integration whose health nobody could otherwise see.
        slack.check(),               # auth.test, free and read-only
    ]


def mark(result):
    if result.get("skipped"):
        return "SKIP"
    return "ok  " if result.get("ok") else "FAIL"


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m src.check")
    p.add_argument("--live-reoon", action="store_true",
                   help="spend one Reoon verifier credit on a real check")
    a = p.parse_args(argv)

    results = run(live_reoon=a.live_reoon)
    # Not part of `run()`, which is the provider sweep and says so. Reported
    # here because this is the command an operator runs before a batch, and a
    # red team read fixture rows out of `work/replywatch.json` as a production
    # signal because nothing anywhere said the file was contaminated.
    state = contamination.check()
    for r in results + [state]:
        status = r["status"] if r.get("status") is not None else "-"
        print(f"{mark(r)} {r['provider']:<12} {str(status):<5} {r['note']}")

    green = sum(1 for r in results if r.get("ok"))
    skipped = sum(1 for r in results if r.get("skipped"))
    failed = len(results) - green - skipped
    # A contaminated state file fails the sweep. Reporting it and exiting zero
    # would make it a line nobody has to act on.
    if not state.get("ok"):
        failed += 1
    print(f"\n{green} ok, {skipped} skipped, {failed} failed, of {len(results)}")
    if skipped:
        print("skipped means not called on purpose: the call would cost money, "
              "or the contract is not confirmed.")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
