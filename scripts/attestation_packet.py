#!/usr/bin/env python3
"""The smallest set of ownership attestations that unlocks sender allocation.

    py -3 scripts/attestation_packet.py              # the packet, writes nothing
    py -3 scripts/attestation_packet.py --all        # every unresolved account

READ ONLY. No provider call, no attestation written, no canonical write. This
prints decisions for a person to take; `senderownership.attest` is the only
write path and it is deliberately not called from here.

## Why this exists

`senderownership.dry_run_report("productive")` answers with 257 accounts,
**zero resolved and 257 needing attestation**. That is a correct report and
an unusable decision surface: nobody attests 257 things, so it has sat at
zero since the module was written and `SAFE_FOR_PRODUCTIVE` has been 0 the
whole time.

The 2026-09-19 analysis found the useful shape and this script is that shape
made runnable: **a cohort does not need a pool. It needs ONE eligible mailbox
with room**, because `executionguard._sender_for` caps a campaign at exactly
one sender anyway. So the packet ranks candidates and shows the few that
would actually change what the allocator can produce.

## What this script REFUSES to do, and why it matters more than what it does

**It does not guess who owns an inbox, and it never pre-fills an answer.**

`scripts/sender_pool_census.py` groups its per-human table by
`row.get("name")` - the display name on the sender row. That grouping is a
convenience for reading a table and it is NOT ownership evidence.
`senderownership` says so in its own words: `resolve_owner` "answers from the
canonical roster rather than guessing from a display name". Checked
2026-09-20: no account in this estate carries a `sender_id`, and there are no
attestations, so all 257 resolve to None. **That is the module working, not a
defect** - and the census's twelve "humans" must not be mistaken for twelve
known owners. They are twelve distinct strings.

So the display name appears below as a HINT, labelled as unverified, and the
operator supplies the `sender_id` themselves. The standing rule is absolute:

    Do not attest a human to a mailbox to gain capacity. Attestation records
    who genuinely operates an inbox; inventing one fabricates the thing the
    gate exists to check.

## What one attestation actually buys, stated honestly

NOT a send today. 487, 489 and 605732 each already name their sender on the
canonical row, which is what `executionguard` checks - they do not go through
`assignment.allocate` and are unaffected by this.

What it buys is the ability for the ALLOCATOR to propose a mailbox for a
FUTURE cohort. Today it can propose nothing, so every new cohort has to have
its sender chosen by hand.
"""
import argparse
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from src import senderheadroom as sh                                   # noqa
from src import senderidentity as si, senderownership as so            # noqa

WORKSPACE = "productive"

# The campaigns that can book a mailbox. Asked of the provider rather than
# hardcoded - see `bison_forward_book_census.forward_booking_campaigns`, and
# the defect that convention replaced.
def _forward_booking():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "census", os.path.join(ROOT, "scripts", "bison_forward_book_census.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return tuple(str(c) for c in module.forward_booking_campaigns())


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--all", action="store_true",
                    help="every unresolved account, not just the candidates")
    ap.add_argument("--need", type=int, default=10,
                    help="cohort size the mailbox must have room for")
    args = ap.parse_args(argv)

    from src.providers import load_env
    load_env()

    report = so.dry_run_report(WORKSPACE)
    print("=" * 74)
    print("  OWNERSHIP ATTESTATION PACKET - nothing here is written")
    print("=" * 74)
    print(f"  workspace          {report['workspace']}")
    print(f"  total accounts     {report['total_accounts']}")
    print(f"  resolved owner     {report['resolved']}")
    print(f"  need attestation   {report['needs_attestation']}")
    print()
    print("  A campaign may name exactly ONE sender "
          "(executionguard._sender_for),")
    print("  so the useful number of decisions is small. One is enough.")
    print()

    rows = si.load()
    try:
        state = sh.load_state()
        active = _forward_booking()
        fresh = sh.freshness(state)
        covers = sh.coverage(state, active)
    except Exception as exc:                       # noqa: BLE001 - classified
        print(f"  NO HEADROOM EVIDENCE: {type(exc).__name__}: {exc}")
        print("  Candidates cannot be ranked by latency. Run the census first.")
        return 1

    print(f"  forward book: covers={covers[0]} fresh={fresh[0]} "
          f"({fresh[1]:.1f}h old)" if fresh[1] is not None else "  forward book: undated")
    if not covers[0]:
        print(f"  WALK DOES NOT COVER {', '.join(covers[1])} - "
              f"ROOM cannot be proven, so no candidate is offered.")
        return 1
    print()

    limits = {}
    for row in rows:
        if row.get("kind") == si.EMAIL_ACCOUNT:
            limits[str(row.get("provider_account_id"))] = row.get("daily_limit")

    candidates = []
    for acct in report["unresolved_accounts"]:
        if acct["channel"] != si.EMAIL:
            continue
        if not acct.get("active") or str(acct.get("health")) != "ok":
            continue
        pid = str(acct.get("provider_account_id") or "")
        limit = limits.get(pid)
        if not limit:
            continue
        day, why = sh.earliest_day(state, int(pid), int(limit),
                                   active_campaign_ids=active, need=args.need)
        if not day:
            continue
        candidates.append({**acct, "earliest": day, "why": why})

    candidates.sort(key=lambda c: (c["earliest"], str(c["account_id"])))

    print(f"  CANDIDATES - healthy, connected, and proven to have room for "
          f"{args.need}:")
    print(f"  {len(candidates)} of {report['needs_attestation']} unresolved "
          f"accounts qualify.\n")
    shown = candidates if args.all else candidates[:5]
    for c in shown:
        print(f"    account_id          {c['account_id']}")
        print(f"    provider_account_id {c['provider_account_id']}")
        print(f"    earliest free day   {c['earliest']}  ({c['why']})")
        print(f"    display name        UNVERIFIED HINT - not ownership "
              f"evidence, confirm before using")
        print(f"    to attest:")
        print(f"      py -3 -c \"import sys; sys.path.insert(0,'.'); "
              f"from src import senderownership as so; "
              f"so.attest('{WORKSPACE}', '{si.EMAIL}', "
              f"'{c['account_id']}', '<THE-REAL-SENDER-ID>', "
              f"'<who-is-vouching>')\"")
        print()
    if not args.all and len(candidates) > len(shown):
        print(f"    ... {len(candidates) - len(shown)} more, --all to see them")
        print()

    print("  WHAT THIS DOES NOT DO")
    print("    It does not unblock 487, 489 or 605732. Each already names its")
    print("    sender on the canonical row, which is what executionguard")
    print("    checks; none goes through assignment.allocate.")
    print("    It unblocks the ALLOCATOR proposing a mailbox for a FUTURE")
    print("    cohort, which today it cannot do at all.")
    print()
    print("  THE RULE THIS MUST NOT BREAK")
    print("    Do not attest a human to a mailbox to gain capacity.")
    print("    Attestation records who genuinely operates an inbox.")
    print("    <THE-REAL-SENDER-ID> is a decision, not a placeholder to fill")
    print("    with whatever makes the command run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
