#!/usr/bin/env python3
"""Who is READY right now, re-derived from state rather than from a file.

    py -3 scripts/batch_eligibility.py --client productive
    py -3 scripts/batch_eligibility.py --client productive --out work/stage/ready.json

OPERATOR AUTHORIZATION, 2026-09-21, condition 1, restated as the check that
proves it: **none of this may be assumed from an earlier run.** A candidate
list written an hour ago is a cached value on a safety path, which is the
shape of six separate rows in the problem register. So this walks every gate
again, from the journals the stages actually wrote, and prints what each one
removed.

THE GATES, in the order they are cheapest to ask:

    client approval   the account is `approved` for this client. Pending is
                      refused and unknown is pending. OPERATOR, 2026-09-21.
    ICP               S3 verdict `in`. Flagged is not in.
    MX                known_allowed or unknown_provider. known_blocked,
                      no_mx and dns_failure are excluded - dns_failure is
                      HELD because we could not ask, which is not the same
                      fact as no mail.
    verification      state `verified`, TWO confirmations, and a recorded
                      pair of two DIFFERENT providers. A supplier's
                      "Verified" column is not one of them.
    collision         the account cleared the recency rule and the contact
                      is not on a touched-and-replied account.
    store overlap     the 306 domains already in our store stay out: they
                      are the double-enrolment risk S1 found.

Nothing here writes anything. It prints a funnel and, with `--out`, the set.
"""
import argparse
import collections
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import clientapproval as ca                            # noqa: E402

STAGE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "work", "stage")
WORK = os.path.dirname(STAGE)

MX_ALLOWED = ("known_allowed", "unknown_provider")


def _jsonl(path):
    rows = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def icp_verdicts():
    """domain -> verdict, last write wins."""
    out = {}
    for row in _jsonl(os.path.join(STAGE, "s3-icp.jsonl")):
        out[str(row.get("domain", "")).lower()] = row
    return out


def mx_status():
    with open(os.path.join(WORK, "mx-cache.json"), encoding="utf-8") as handle:
        cache = json.load(handle)
    return {k.lower(): (v or {}).get("status") for k, v in cache.items()}


def verifications():
    """email -> the LATEST verdict. A re-ask supersedes an earlier hold."""
    out = {}
    for row in _jsonl(os.path.join(STAGE, "s5-verify.jsonl")):
        out[str(row.get("email", "")).lower()] = row
    return out


def store_domains():
    """The domains already in our own store - the 306 overlap, kept out."""
    path = os.path.join(WORK, "queue.jsonl")
    if not os.path.exists(path):
        return set()
    out = set()
    for row in _jsonl(path):
        for key in ("domain", "company_domain", "website"):
            value = row.get(key)
            if value:
                out.add(ca.account_of(value))
                break
    return out - {""}


def collision_cleared():
    """The accounts a collision walk cleared, or None if none has run.

    PREFERS THE FRESH WALK. `s6-collision-walk.json` is written by
    `scripts/s6_collision_walk.py`, carries a policy per account, and is the
    current answer. Only `collision.ALLOW` is supply: HOLD wants a person to
    look, STOP means the account is answered or in play, and a domain the
    provider could not be read for is REFUSED and is not cleared.

    FALLS BACK TO BATCH 1'S SET, which is what this read before the walker
    existed. That file is a list of ADDRESSES cleared on 2026-09-21 and it is
    a cached value on a safety path - the shape of six rows in the problem
    register. It stays as the fallback rather than the answer, so an estate
    with no fresh walk behaves exactly as it did, and one with a walk uses it.

    The two are UNIONED rather than replaced. Batch 1's accounts are all
    already in our store and the overlap gate removes them regardless, so the
    union adds no supply; it only means a re-run cannot go backwards.
    """
    cleared, found = set(), False

    walk = os.path.join(STAGE, "s6-collision-walk.json")
    if os.path.exists(walk):
        with open(walk, encoding="utf-8") as handle:
            accounts = (json.load(handle) or {}).get("accounts") or {}
        for domain, entry in accounts.items():
            if (entry or {}).get("policy") == "allow":
                cleared.add(ca.account_of(domain))
        found = found or bool(accounts)

    legacy = os.path.join(STAGE, "batch1-candidates.json")
    if os.path.exists(legacy):
        with open(legacy, encoding="utf-8") as handle:
            cleared |= {ca.account_of(e) for e in json.load(handle)}
        found = True

    if not found:
        return None
    return cleared - {""}


def eligible(client="productive", require_collision=True):
    """Walk every gate and report what each one removed."""
    icp, mx, verified = icp_verdicts(), mx_status(), verifications()
    overlap, cleared = store_domains(), collision_cleared()
    # Load the approval ledger ONCE. `is_approved` re-reads a 7.4MB journal on
    # every call when `rows` is None, so the walk was O(candidates x ledger) -
    # 9,140 x 24,711 rows, which does not finish. The gate is unchanged; it now
    # reads one consistent snapshot instead of re-reading a live file per
    # candidate, which is also the stricter reading of "walk every gate again".
    approvals = ca.load()
    funnel = collections.OrderedDict()
    dropped = collections.Counter()

    considered = sorted(verified)
    funnel["contacts with a verification verdict"] = len(considered)

    survivors = []
    for email in considered:
        row = verified[email]
        domain = ca.account_of(email)

        if not ca.is_approved(domain, client, rows=approvals):
            dropped["client approval not `approved`"] += 1
            continue
        verdict = (icp.get(domain) or {}).get("verdict")
        if verdict != "in":
            dropped[f"ICP verdict {verdict or 'unknown'}"] += 1
            continue
        status = mx.get(domain)
        if status not in MX_ALLOWED:
            dropped[f"MX {status or 'unknown'}"] += 1
            continue
        if row.get("state") != "verified":
            dropped[f"verification {row.get('state')}"] += 1
            continue
        pair = tuple(row.get("pair") or ())
        if len(set(pair)) < 2 or int(row.get("confirmations") or 0) < 2:
            dropped["fewer than two independent verifications"] += 1
            continue
        if domain in overlap:
            dropped["already in our store (the 306 overlap)"] += 1
            continue
        if require_collision:
            if cleared is None:
                dropped["collision not walked"] += 1
                continue
            if domain not in cleared:
                dropped["collision: account not cleared"] += 1
                continue
        survivors.append(email)

    funnel["READY"] = len(survivors)
    return survivors, funnel, dropped


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--client", default="productive")
    parser.add_argument("--out")
    parser.add_argument("--no-collision", action="store_true",
                        help="report the set BEFORE the collision walk")
    args = parser.parse_args(argv)

    survivors, funnel, dropped = eligible(args.client,
                                          require_collision=not args.no_collision)
    print(f"\nELIGIBILITY  client={args.client}\n")
    for name, value in funnel.items():
        print(f"  {name.ljust(42)} {value:>6}")
    print("\n  removed by")
    for reason, count in dropped.most_common():
        print(f"    {reason.ljust(40)} {count:>6}")
    accounts = {ca.account_of(e) for e in survivors}
    print(f"\n  READY contacts {len(survivors)} on {len(accounts)} accounts")
    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            json.dump(sorted(survivors), handle, indent=1)
        print(f"  written to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
